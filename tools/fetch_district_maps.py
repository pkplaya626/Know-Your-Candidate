"""Rebuild district_maps/: every state's House districts, and the towns to label.

The district pages draw each state's congressional districts - and, where the
map for the 2026 election is new, the map it replaced. The boundaries are
vendored here, once, from official and openly licensed sources, and the build
projects them (kyc/districts.py). Nothing in this tool is a judgement about
geography; everything it writes can be rebuilt by running it again.

Sources:

* The districts members were elected in (the 119th Congress) and the county
  lines: the Census Bureau's 2024 cartographic boundary files at 1:5,000,000
  (cb_2024_us_cd119_5m, cb_2024_us_county_5m). The Bureau generalises them so
  that neighbouring shapes still share their boundaries exactly; they are used
  as published.
* A new map for 2026, for each state in kyc.districts.REDRAWN: the Wikimedia
  Commons map data pages "Data:<State>'s Nth congressional district
  (2027-).map" (CC0), each converted from the official shapefile it names.
  Their boundaries are shared exactly between neighbours too, so they are
  simplified here along shared arcs - never shape by shape, which would open
  slivers between districts - to roughly the Census file's level of detail.
* Towns: every incorporated place's Census Gazetteer internal point, ranked by
  the Census Vintage 2024 population estimates. An internal point is inside
  its place but not always inside the part anyone means - San Francisco's is
  on the Farallon Islands - so a point outside the place's largest piece of
  land (from the Census 2024 place boundaries) is replaced by that piece's
  interior point, and recorded.

Each state's file is a TopoJSON topology with objects ``current``,
``current_pts`` (one label point per district, the pole of inaccessibility),
``counties``, and for a redrawn state ``next`` and ``next_pts``.

    python tools/fetch_district_maps.py                # everything
    python tools/fetch_district_maps.py --states CA,TX # some states' maps
    python tools/fetch_district_maps.py --places       # only places.json
"""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import struct
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import districts, geo  # noqa: E402
from kyc.geo import FIPS_TO_STATE  # noqa: E402

CENSUS = "https://www2.census.gov/geo/tiger/GENZ2024/shp/"
DISTRICTS_URL = CENSUS + "cb_2024_us_cd119_5m.zip"
COUNTIES_URL = CENSUS + "cb_2024_us_county_5m.zip"
GAZETTEER_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                 "2020_Gazetteer/2020_Gaz_place_national.zip")
ESTIMATES_URL = ("https://www2.census.gov/programs-surveys/popest/datasets/"
                 "2020-2024/cities/totals/sub-est2024.csv")
PLACE_SHAPES_URL = CENSUS + "cb_2024_{}_place_500k.zip"
COMMONS_URL = "https://commons.wikimedia.org/w/index.php?"
USER_AGENT = "know-your-candidate-district-maps/1.0 (https://github.com/pkplaya626/Know-Your-Candidate)"

OUT_DIR = "district_maps"
PLACES_FILE = os.path.join(OUT_DIR, "places.json")

# Quantisation: 2e-5 degrees, about two metres - far below anything drawn.
QUANTUM = 2e-5
# Douglas-Peucker tolerance for the Commons maps, in metres. At 250 m Texas's
# new map comes out near the Census file's vertex count for the old one.
TOLERANCE_M = 250.0
# Census district codes that mean "the one seat": at-large states ("00") and
# the non-voting delegates of D.C. and Puerto Rico ("98"). The site numbers
# them 0, as the races do.
AT_LARGE = ("00", "98")


# ------------------------------------------------------------------- fetching

def cache_dir():
    path = os.path.join(tempfile.gettempdir(), "kyc-district-maps")
    os.makedirs(path, exist_ok=True)
    return path


def _whole(url, body):
    """Whether *body* is what *url* promised. The Census server answers a
    burst with a "Request Rejected" page and status 200; cached, that page
    would stand in for the file on every later run."""
    if url.lower().endswith(".zip"):
        return zipfile.is_zipfile(io.BytesIO(body))
    return True


def get(url, pause=0.0):
    """Download *url*, caching it so a re-run does not fetch it again."""
    name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    path = os.path.join(cache_dir(), name)
    if os.path.exists(path):
        with open(path, "rb") as handle:
            body = handle.read()
        if _whole(url, body):
            return body
        os.remove(path)                 # a rejection cached by an older run
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
            if not _whole(url, body):
                raise OSError(f"{url} did not return the file (the server rejected the request)")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            time.sleep(5 * (attempt + 1))
        except OSError:
            # A rejection page or a dropped connection: wait longer each time.
            time.sleep(15 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {url}")
    with open(path + ".tmp", "wb") as handle:
        handle.write(body)
    os.replace(path + ".tmp", path)
    time.sleep(pause)
    return body


# ------------------------------------------------------------- shapefiles

def read_dbf(data, encoding="latin-1"):
    """Records as dicts of text. *encoding* is the layer's own (its .cpg);
    dBase's default is Latin-1, but the Census writes UTF-8 and says so, and
    reading it as Latin-1 put "DoÃ±a Ana County" on the page."""
    count = struct.unpack("<I", data[4:8])[0]
    header, record = struct.unpack("<HH", data[8:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        fields.append((data[pos:pos + 11].split(b"\0")[0].decode(), data[pos + 16]))
        pos += 32
    rows = []
    for i in range(count):
        raw = data[header + i * record + 1: header + (i + 1) * record]
        row, offset = {}, 0
        for name, width in fields:
            row[name] = raw[offset:offset + width].decode(encoding).strip()
            offset += width
        rows.append(row)
    return rows


def read_shp(data):
    """Polygon shapes as lists of rings of (lon, lat)."""
    shapes, pos = [], 100
    while pos < len(data):
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0] * 2
        content = data[pos + 8: pos + 8 + length]
        pos += 8 + length
        if struct.unpack("<i", content[:4])[0] == 0:
            shapes.append([])
            continue
        parts, points = struct.unpack("<ii", content[36:44])
        starts = struct.unpack(f"<{parts}i", content[44:44 + 4 * parts]) + (points,)
        base = 44 + 4 * parts
        flat = struct.unpack(f"<{2 * points}d", content[base: base + 16 * points])
        coords = list(zip(flat[0::2], flat[1::2]))
        shapes.append([coords[starts[i]:starts[i + 1]] for i in range(parts)])
    return shapes


def read_layer(url):
    archive = zipfile.ZipFile(io.BytesIO(get(url)))
    # macOS archives carry "__MACOSX/._x.shp" resource forks; they are not data.
    names = [n for n in archive.namelist() if "__MACOSX" not in n]
    cpg = [n for n in names if n.lower().endswith(".cpg")]
    declared = archive.read(cpg[0]).decode("ascii", "replace").strip().lower() if cpg else ""
    encoding = "utf-8" if declared.replace("-", "") in ("utf8", "65001") else "latin-1"
    rows = read_dbf(archive.read([n for n in names if n.lower().endswith(".dbf")][0]), encoding)
    shapes = read_shp(archive.read([n for n in names if n.lower().endswith(".shp")][0]))
    if len(rows) != len(shapes):
        raise SystemExit(f"{url}: {len(rows)} records but {len(shapes)} shapes")
    return list(zip(rows, shapes))


def district_number(code):
    if code in AT_LARGE:
        return 0
    if not code.isdigit():
        raise SystemExit(f"unexpected district code {code!r}")
    return int(code)


# ----------------------------------------------------------------- commons

def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _rings(geometry):
    kind = geometry.get("type")
    if kind == "Polygon":
        return geometry["coordinates"]
    if kind == "MultiPolygon":
        return [ring for polygon in geometry["coordinates"] for ring in polygon]
    if kind == "GeometryCollection":
        return [ring for g in geometry["geometries"] for ring in _rings(g)]
    return []                       # markers and lines carry no area


def _wkt_values(prj):
    """The parameters of a .prj: projection, spheroid, linear unit, PARAMETERs."""
    import re

    out = {"projection": (re.search(r'PROJECTION\["([^"]+)"', prj) or [None, None])[1]}
    spheroid = re.search(r'SPHEROID\["[^"]*",([\d.]+),([\d.]+)', prj)
    out["a"], out["inv_f"] = float(spheroid[1]), float(spheroid[2])
    for name, value in re.findall(r'PARAMETER\["([^"]+)",(-?[\d.]+)\]', prj):
        out[name.lower()] = float(value)
    unit = re.findall(r'UNIT\["([^"]+)",([\d.]+)\]', prj)
    # The last UNIT of a PROJCS is its linear unit (metre, or US survey foot).
    out["unit"] = float(unit[-1][1]) if prj.lstrip().startswith("PROJCS") else 1.0
    return out


def unprojector(prj):
    """A function ``(x, y) -> (lon, lat)`` for the .prj's coordinate system.

    Geographic files pass through. The two projections the official files
    use are undone here: spherical Web Mercator, and the ellipsoidal Lambert
    conformal conic (Snyder, Map Projections - A Working Manual, 15-7 to
    15-11). Anything else is refused rather than guessed at.
    """
    if prj.lstrip().startswith("GEOGCS"):
        return lambda x, y: (x, y)
    p = _wkt_values(prj)
    kind = p["projection"]
    unit = p["unit"]
    fe, fn = p.get("false_easting", 0.0) * unit, p.get("false_northing", 0.0) * unit
    if kind in ("Mercator_Auxiliary_Sphere", "Popular_Visualisation_Pseudo_Mercator"):
        radius = p["a"]

        def mercator(x, y):
            x, y = x * unit - fe, y * unit - fn
            return (math.degrees(x / radius) + p.get("central_meridian", 0.0),
                    math.degrees(2 * math.atan(math.exp(y / radius)) - math.pi / 2))
        return mercator
    if kind == "Lambert_Conformal_Conic":
        a = p["a"]
        f = 1 / p["inv_f"]
        e = math.sqrt(2 * f - f * f)
        rad = math.radians
        phi1 = rad(p["standard_parallel_1"])
        phi2 = rad(p.get("standard_parallel_2", p["standard_parallel_1"]))
        phi0, lam0 = rad(p["latitude_of_origin"]), rad(p["central_meridian"])

        def m(phi):
            return math.cos(phi) / math.sqrt(1 - (e * math.sin(phi)) ** 2)

        def t(phi):
            s = e * math.sin(phi)
            return math.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (e / 2)

        n = ((math.log(m(phi1)) - math.log(m(phi2))) / (math.log(t(phi1)) - math.log(t(phi2)))
             if phi1 != phi2 else math.sin(phi1))
        big_f = m(phi1) / (n * t(phi1) ** n)
        rho0 = a * big_f * t(phi0) ** n

        def lambert(x, y):
            x, y = x * unit - fe, y * unit - fn
            sign = 1 if n > 0 else -1
            rho = sign * math.hypot(x, rho0 - y)
            theta = math.atan2(sign * x, sign * (rho0 - y))
            tt = (rho / (a * big_f)) ** (1 / n)
            phi = math.pi / 2 - 2 * math.atan(tt)
            for _ in range(15):
                s = e * math.sin(phi)
                phi = math.pi / 2 - 2 * math.atan(tt * ((1 - s) / (1 + s)) ** (e / 2))
            return (math.degrees(theta / n + lam0), math.degrees(phi))
        return lambert
    raise SystemExit(f"unsupported projection {kind!r}; not guessing")


def official_plan(spec, seats, extent):
    """``({district: rings}, cite)`` from the state's own shapefile.

    Projected files are unprojected, and every point must then land inside
    *extent* - the state's own box from the Census map, with a margin - or
    the file is refused: a wrong projection draws the right districts in the
    wrong place, which is exactly what must never look normal.
    """
    archive = zipfile.ZipFile(io.BytesIO(get(spec["url"])))
    names = archive.namelist()
    prj = [n for n in names if n.lower().endswith(".prj") and "__MACOSX" not in n]
    if not prj:
        raise SystemExit(f"{spec['url']}: no .prj, so no known coordinate system")
    to_lonlat = unprojector(archive.read(prj[0]).decode("latin-1"))
    west, south, east, north = extent
    margin = 0.25
    plan = {}
    for row, rings in read_layer(spec["url"]):
        value = row[spec["field"]].lstrip("0") or "0"
        if not value.isdigit():
            raise SystemExit(f"{spec['url']}: district {value!r} is not a number")
        for ring in rings:
            ring = [to_lonlat(x, y) for x, y in ring]
            for lon, lat in ring:
                if not (west - margin <= lon <= east + margin and
                        south - margin <= lat <= north + margin):
                    raise SystemExit(f"{spec['url']}: point {lon:.4f},{lat:.4f} is outside "
                                     f"the state; the projection is wrong")
            plan.setdefault(int(value), []).append(ring)
    if sorted(plan) != list(range(1, seats + 1)):
        raise SystemExit(f"{spec['url']}: districts {sorted(plan)}, expected 1-{seats}")
    return plan, spec["cite"]


def commons_plan(state_name, seats, years="2027"):
    """``({district: rings}, [source text per page])`` from the Commons pages."""
    plan, sources = {}, []
    for n in range(1, seats + 1):
        title = f"Data:{state_name}'s {ordinal(n)} congressional district ({years}–).map"
        url = COMMONS_URL + urllib.parse.urlencode({"title": title, "action": "raw"})
        body = json.loads(get(url, pause=0.5))
        if body.get("license") != "CC0-1.0":
            raise SystemExit(f"{title}: licence is {body.get('license')!r}, not CC0")
        data = body["data"]
        features = (data["features"] if data.get("type") == "FeatureCollection"
                    else [data] if data.get("type") == "Feature"
                    else [{"geometry": data}])
        rings = [ring for f in features if f.get("geometry") for ring in _rings(f["geometry"])]
        if not rings:
            raise SystemExit(f"{title}: no polygon in the map data")
        plan[n] = rings
        sources.append(body.get("sources", ""))
    return plan, sources


# ----------------------------------------------------------------- topology

class Topology:
    """Quantise, cut rings into arcs shared between neighbours, simplify each
    arc once, and write TopoJSON. Simplifying shared arcs - not each shape on
    its own - is what keeps neighbouring districts touching."""

    def __init__(self, lat0):
        self.arcs = []                  # lists of quantised (x, y)
        self.index = {}                 # tuple(points) -> arc id
        self.objects = {}
        self.kx = math.cos(math.radians(lat0)) * 111320.0 * QUANTUM
        self.ky = 110574.0 * QUANTUM

    @staticmethod
    def quantise(ring):
        out = []
        for x, y in ring:
            point = (int(round(x / QUANTUM)), int(round(y / QUANTUM)))
            if not out or out[-1] != point:
                out.append(point)
        if len(out) > 1 and out[0] == out[-1]:
            out.pop()
        return out if len(set(out)) >= 3 else None

    def _arc(self, points):
        key = tuple(points)
        if key in self.index:
            return self.index[key]
        back = tuple(reversed(points))
        if back in self.index:
            return ~self.index[back]
        self.index[key] = len(self.arcs)
        self.arcs.append(list(points))
        return len(self.arcs) - 1

    def add(self, name, items, tolerance=0.0):
        """*items*: ``[(properties, rings in lon/lat)]``. Rings are cut at the
        points where the set of rings sharing a boundary changes."""
        shapes = []
        for props, rings in items:
            quantised = [q for q in (self.quantise(r) for r in rings) if q]
            shapes.append((props, quantised))
        pairs = {}
        for _, rings in shapes:
            for ring in rings:
                n = len(ring)
                for i, point in enumerate(ring):
                    pair = frozenset((ring[i - 1], ring[(i + 1) % n]))
                    pairs.setdefault(point, set()).add(pair)
        junction = {p for p, s in pairs.items() if len(s) > 1}
        start = len(self.arcs)
        geometries = []
        for props, rings in shapes:
            arcs_of = []
            for ring in rings:
                cuts = [i for i, p in enumerate(ring) if p in junction]
                if not cuts:
                    k = ring.index(min(ring))
                    arcs_of.append([self._arc(ring[k:] + ring[:k] + [ring[k]])])
                    continue
                ids = []
                for j, first in enumerate(cuts):
                    last = cuts[(j + 1) % len(cuts)]
                    run = ring[first:last + 1] if last > first else ring[first:] + ring[:last + 1]
                    ids.append(self._arc(run))
                arcs_of.append(ids)
            geometries.append((props, arcs_of))
        if tolerance:
            for a in range(start, len(self.arcs)):
                self.arcs[a] = self._simplify(self.arcs[a], tolerance)
            self._repair(geometries, tolerance)
        self.objects[name] = geometries

    def _metres(self, point):
        return (point[0] * self.kx, point[1] * self.ky)

    def _simplify(self, arc, tolerance):
        """Douglas-Peucker with both ends fixed; a closed arc is split at the
        point farthest from its start, so it keeps a body."""
        if len(arc) <= 2:
            return arc
        pts = [self._metres(p) for p in arc]
        if arc[0] == arc[-1]:
            far = max(range(len(pts)), key=lambda i: math.dist(pts[0], pts[i]))
            keep = (_dp(pts[:far + 1], tolerance) +
                    [far + i for i in _dp(pts[far:], tolerance)][1:])
        else:
            keep = _dp(pts, tolerance)
        return [arc[i] for i in keep]

    def _repair(self, geometries, tolerance):
        """A ring whose arcs simplified to a sliver gets its arcs back at a
        finer tolerance, so no district loses a piece of itself."""
        for _, arcs_of in geometries:
            for ids in arcs_of:
                finer = tolerance
                for _ in range(6):
                    ring = self.ring(ids)
                    if len(set(ring)) >= 4 and abs(_area(ring)) > 0:
                        break
                    finer /= 4
                    for a in ids:
                        a = a if a >= 0 else ~a
                        self.arcs[a] = self._simplify(self._original(a), finer)

    def _original(self, a):
        for key, value in self.index.items():
            if value == a:
                return list(key)
        raise KeyError(a)

    def ring(self, ids):
        out = []
        for a in ids:
            arc = self.arcs[a] if a >= 0 else list(reversed(self.arcs[~a]))
            out.extend(arc if not out else arc[1:])
        return out

    def rings_m(self, name):
        """Every ring of an object, in local metres."""
        return [[self._metres(p) for p in self.ring(ids)]
                for _, arcs_of in self.objects[name] for ids in arcs_of]

    def label_points(self, name, out_name, land=None):
        """The pole of inaccessibility of every district: a label point
        well inside, never on a crescent's empty middle. With *land* (the
        rings of the Census map, which is clipped to the shore), it is the
        pole of the district's land - the part the page draws - so a
        district that runs out to sea is labelled where it can be seen,
        and no number sits against a coast it does not show."""
        points = []
        coast = geo.outline_distance(land) if land is not None else None
        for props, arcs_of in self.objects[name]:
            rings = [[self._metres(p) for p in self.ring(ids)] for ids in arcs_of]
            x, y = polylabel(rings, within=coast)
            points.append({"type": "Point", "properties": props,
                           "coordinates": [int(round(x / self.kx)), int(round(y / self.ky))]})
        self.points = getattr(self, "points", {})
        self.points[out_name] = points

    def topojson(self):
        def encode(arc):
            out, px, py = [], 0, 0
            for i, (x, y) in enumerate(arc):
                out.append([x, y] if i == 0 else [x - px, y - py])
                px, py = x, y
            return out
        objects = {}
        for name, geometries in self.objects.items():
            objects[name] = {"type": "GeometryCollection", "geometries": [
                {"type": "Polygon", "arcs": arcs_of, "properties": props}
                for props, arcs_of in geometries]}
        for name, points in getattr(self, "points", {}).items():
            objects[name] = {"type": "GeometryCollection", "geometries": points}
        return {"type": "Topology",
                "transform": {"scale": [QUANTUM, QUANTUM], "translate": [0, 0]},
                "objects": objects, "arcs": [encode(a) for a in self.arcs]}


def _dp(pts, tolerance):
    """Indices Douglas-Peucker keeps, iteratively (no recursion limit)."""
    keep = {0, len(pts) - 1}
    stack = [(0, len(pts) - 1)]
    while stack:
        first, last = stack.pop()
        (ax, ay), (bx, by) = pts[first], pts[last]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, worst = -1.0, None
        for i in range(first + 1, last):
            px, py = pts[i]
            d = (abs(dx * (ay - py) - dy * (ax - px)) / norm if norm
                 else math.hypot(px - ax, py - ay))
            if d > best:
                best, worst = d, i
        if worst is not None and best > tolerance:
            keep.add(worst)
            stack.extend(((first, worst), (worst, last)))
    return sorted(keep)


def _area(ring):
    return sum(ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1]
               for i in range(len(ring))) / 2


# One implementation of the label point, shared with the national map.
polylabel = geo.polylabel


# -------------------------------------------------------------- the states

def state_maps(codes):
    """Write district_maps/<st>.json for each postal code in *codes*."""
    os.makedirs(OUT_DIR, exist_ok=True)
    by_state = {}
    for row, rings in read_layer(DISTRICTS_URL):
        code = FIPS_TO_STATE.get(row["STATEFP"]) or {"60": "AS", "66": "GU", "69": "MP"}.get(
            row["STATEFP"])
        if code:
            by_state.setdefault(code, {}).setdefault("current", []).append(
                ({"d": district_number(row["CD119FP"])}, rings))
    for row, rings in read_layer(COUNTIES_URL):
        code = FIPS_TO_STATE.get(row["STATEFP"]) or {"60": "AS", "66": "GU", "69": "MP"}.get(
            row["STATEFP"])
        if code in by_state:
            by_state[code].setdefault("counties", []).append(({"name": row["NAMELSAD"]}, rings))

    report = []
    for code in codes:
        layers = by_state.get(code)
        if not layers:
            raise SystemExit(f"{code}: no districts in the Census file")
        lats = [p[1] for _, rings in layers["current"] for r in rings for p in r]
        topo = Topology((min(lats) + max(lats)) / 2)
        current = sorted(layers["current"], key=lambda item: item[0]["d"])
        topo.add("current", current)
        topo.label_points("current", "current_pts")
        sources = {"current": "U.S. Census Bureau, cb_2024_us_cd119_5m (119th Congress)"}
        spec = districts.REDRAWN.get(code)
        if spec:
            if spec.get("shapefile"):
                extent = (min(p[0] for _, rings in current for r in rings for p in r),
                          min(lats),
                          max(p[0] for _, rings in current for r in rings for p in r),
                          max(lats))
                plan, cite = official_plan(spec["shapefile"], len(current), extent)
                sources["next"] = {"via": "official", "cite": cite}
            else:
                plan, cited = commons_plan(spec["commons"], len(current))
                distinct = sorted(set(cited))
                if len(distinct) != 1:
                    raise SystemExit(f"{code}: the Commons pages cite different sources")
                sources["next"] = {"via": "commons", "cite": distinct[0]}
            topo.add("next", [({"d": n}, plan[n]) for n in sorted(plan)], tolerance=TOLERANCE_M)
            # The new maps run out over water; the Census map stops at the
            # shore, and the page clips the new map to it.
            topo.label_points("next", "next_pts", land=topo.rings_m("current"))
        topo.add("counties", sorted(layers.get("counties", []), key=lambda i: i[0]["name"]))
        payload = topo.topojson()
        payload["sources"] = sources
        path = os.path.join(OUT_DIR, f"{code.lower()}.json")
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
        os.replace(path + ".tmp", path)
        counts = {name: sum(len(topo.ring(ids)) for _, arcs in geos for ids in arcs)
                  for name, geos in topo.objects.items()}
        report.append(f"{code}: {os.path.getsize(path) // 1024} KB, vertices {counts}")
        print(report[-1], flush=True)
    return report


# ------------------------------------------------------------------ places

_SUFFIXES = (" metropolitan government", " metro government", " unified government",
             " consolidated government", " city and borough", " municipality", " borough",
             " village", " plantation", " city", " town")


def _short_name(name):
    """``"Truckee town"`` -> ``"Truckee"``; ``"Nashville-Davidson metropolitan
    government (balance)"`` -> ``"Nashville-Davidson"``. The legal form is
    not a label."""
    if name.endswith(" (balance)"):
        name = name[: -len(" (balance)")]
    for suffix in _SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _inside(ring, x, y):
    hit = False
    n = len(ring)
    for i in range(n):
        (ax, ay), (bx, by) = ring[i], ring[(i + 1) % n]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
    return hit


def main_piece_point(rings, lon, lat):
    """``(lon, lat, moved)``: the internal point when it lies in the place's
    largest piece of land, else that piece's pole of inaccessibility.

    The Census guarantees its internal point is inside the place, not inside
    the part of it anyone means: San Francisco's is on the Farallon Islands.
    The largest piece decides, not a second source - the USGS civil points
    disagree with the Census by kilometres for dozens of ordinary towns, and
    for Alvin, Texas it is the USGS point that is out of town.
    """
    scale = math.cos(math.radians(lat))
    largest = max(rings, key=lambda r: abs(_area([(x * scale, y) for x, y in r])))
    if _inside(largest, lon, lat):
        return lon, lat, False
    metres = [(x * scale * 111320.0, y * 110574.0) for x, y in largest]
    x, y = polylabel([metres])
    return x / (scale * 111320.0), y / 110574.0, True


def build_places(gazetteer_zip, estimates_csv, shapes_for):
    """The places payload. *shapes_for(state fips)* returns ``{GEOID:
    rings}`` from that state's Census place boundaries, or None."""
    archive = zipfile.ZipFile(io.BytesIO(gazetteer_zip))
    lines = archive.read(archive.namelist()[0]).decode("latin-1").splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    points = {}
    for line in lines[1:]:
        row = dict(zip(header, (f.strip() for f in line.split("\t"))))
        points[row["GEOID"]] = row

    places, unmatched, moved, unchecked = {}, [], [], []
    shapes_by_state = {}
    for row in csv.DictReader(io.StringIO(estimates_csv.decode("latin-1"))):
        if row["SUMLEV"] != "162":
            continue
        code = FIPS_TO_STATE.get(row["STATE"])
        geoid = row["STATE"] + row["PLACE"]
        point = points.get(geoid)
        if not code:
            raise SystemExit(f"unknown state code {row['STATE']} for {row['NAME']}")
        if point is None:
            # Incorporated since the 2020 Gazetteer: there is no official
            # point to draw it at, so it is listed, not guessed.
            unmatched.append(f"{row['NAME']}, {code}")
            continue
        if row["STATE"] not in shapes_by_state:
            shapes_by_state[row["STATE"]] = shapes_for(row["STATE"]) or {}
        name = _short_name(row["NAME"])
        lat, lon = float(point["INTPTLAT"]), float(point["INTPTLONG"])
        rings = shapes_by_state[row["STATE"]].get(geoid)
        if not rings:
            unchecked.append(f"{name}, {code}")
        else:
            new_lon, new_lat, shifted = main_piece_point(rings, lon, lat)
            if shifted:
                moved.append([code, name, lon, lat])
                lon, lat = round(new_lon, 6), round(new_lat, 6)
        places.setdefault(code, []).append([name, lon, lat, int(row["POPESTIMATE2024"])])
    for code in places:
        places[code].sort(key=lambda p: (-p[3], p[0]))
    return {
        "source": ("U.S. Census Bureau: 2020 Gazetteer place internal points, 2024 place "
                   "boundaries (cb_2024_<state>_place_500k) and Vintage 2024 population "
                   "estimates (SUB-EST2024)"),
        "urls": [GAZETTEER_URL, ESTIMATES_URL, PLACE_SHAPES_URL.format("<state fips>")],
        "fields": ["name", "lon", "lat", "population2024"],
        # Internal points outside the place's largest piece, replaced by that
        # piece's interior point: [state, name, internal lon, internal lat].
        "moved": sorted(moved),
        # No 2024 boundary to check the point against.
        "unchecked": sorted(unchecked),
        # Incorporated after the 2020 Gazetteer, so with no official point.
        "unlocated": sorted(unmatched),
        "places": dict(sorted(places.items())),
    }


def dump_places(payload):
    """One place per line, so a refresh diffs place by place."""
    def compact(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    head = [f"{compact(k)}:{compact(v)}" for k, v in payload.items() if k != "places"]
    states = [f"{compact(code)}:[\n" + ",\n".join(compact(p) for p in rows) + "\n]"
              for code, rows in payload["places"].items()]
    return "{\n" + ",\n".join(head) + ',\n"places":{\n' + ",\n".join(states) + "\n}}\n"


def write_places():
    def shapes_for(fips):
        try:
            layer = read_layer(PLACE_SHAPES_URL.format(fips))
        except urllib.error.HTTPError:
            return None
        return {row["GEOID"]: rings for row, rings in layer if rings}

    payload = build_places(get(GAZETTEER_URL), get(ESTIMATES_URL), shapes_for)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(PLACES_FILE + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(dump_places(payload))
    os.replace(PLACES_FILE + ".tmp", PLACES_FILE)
    total = sum(len(v) for v in payload["places"].values())
    print(f"wrote {PLACES_FILE}: {total} places in {len(payload['places'])} states; "
          f"{len(payload['moved'])} labelled on their largest piece instead of an outlying "
          f"internal point ({', '.join(m[1] + ', ' + m[0] for m in payload['moved'])}); "
          f"{len(payload['unchecked'])} with no boundary to check against; "
          f"{len(payload['unlocated'])} incorporated since 2020 with no Gazetteer point")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--states", help="comma-separated postal codes (default: all)")
    parser.add_argument("--places", action="store_true", help="only rebuild places.json")
    args = parser.parse_args(argv)
    if not args.places:
        codes = (args.states.split(",") if args.states else districts.all_codes())
        state_maps([c.strip().upper() for c in codes])
    if args.places or not args.states:
        write_places()
    return 0


if __name__ == "__main__":
    sys.exit(main())
