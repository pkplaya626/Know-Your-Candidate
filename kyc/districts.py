"""House district maps before and after a redistricting, as plain SVG paths.

California redrew its congressional map mid-decade. Proposition 50, approved
on November 4, 2025, replaced the map the Citizens Redistricting Commission
drew after the 2020 census with one the Legislature passed as AB 604, for the
2026 through 2030 elections. Members followed the new lines: Ami Bera, who
holds the 6th, is running in the redrawn 3rd, and Kevin Kiley, who holds the
3rd, in the redrawn 6th. The roster seats people where they sit and the
filings say where they run (rule 30); this module draws the two maps those
numbers refer to, so a reader can see what "CA-3" meant then and means now.

Like ``geo.py``, the work happens here, once, at build time: the page gets
ready-to-render ``<path d="...">`` strings and needs no mapping library.
Unlike the national atlas, these boundaries arrive as longitude and latitude,
so they are projected here - with California's own equal-area projection,
which is also what makes the overlap figures below honest: on an equal-area
map, a share of the drawing is a share of the ground.

Sources, vendored at the repository root and never edited by hand:

* ``ca_districts_topo.json`` - both plans' 52 districts, from the Wikimedia
  Commons map data pages "Data:California's Nth congressional district
  (2023-).map" (the commission's map) and "(2027-).map" (the Proposition 50
  map), CC0; county lines from the Census Bureau via us-atlas. Built into one
  topology and simplified for display with mapshaper 0.7.72 on 2026-10-03;
  the exact simplification settings were not recorded. The boundaries are
  fixed by law until the 2030 census, so the file has no refresh command.
* ``ca_places.json`` - incorporated places, from ``tools/fetch_ca_places.py``.

Everything a reader is told about *people* comes from ``profiles.js``; this
file is a pure function of the geometry, and its signature says so.
"""

import json
import math
import os

from . import geo


class DistrictsError(RuntimeError):
    """Raised when a district map is missing or not the shape we expect."""


# EPSG:3310, "California Albers": standard parallels 34N and 40.5N, central
# meridian 120W - drawn on a sphere, as d3.geoConicEqualArea draws it.
PARALLELS = (34.0, 40.5)
CENTRAL_MERIDIAN = -120.0
EARTH_RADIUS_KM = 6371.0088

# The emitted coordinate space: 1,000 units across, which puts one unit near
# a kilometre and keeps the one-decimal rounding in geo.py below a pixel even
# in a close-up drawn at five times the statewide scale.
WIDTH = 1000
PAD = 10

# Scanline spacing, in emitted units, for measuring overlaps. Half a unit is
# a few hundred metres; halving it again moves no share by a tenth of a point.
SCAN_STEP = 0.5

# Overlaps smaller than this share of both districts are not shipped. Two
# plans simplified separately do not trace a shared county line identically,
# so the slivers between them are drawing artefacts, not territory.
MIN_FLOW = 0.005

# Every district of a plan, drawn from the plan's own two files, must be
# accounted for by the other plan to within this share. Anything less means
# a district is missing or mis-numbered, not merely simplified.
MIN_COVERAGE = 0.97

PLANS = {
    "CA": {
        "name": "California",
        "seats": 52,
        "file": "ca_districts_topo.json",
        "places": "ca_places.json",
        "page": "redistricting/ca.html",
        "headline": "California's House districts, before and after Proposition 50",
        # Each clause is in the measure's Wikipedia article: the date, the
        # map it replaced, the bill that set the lines, and how long they
        # last. Nothing here characterises the map or the people on it.
        "intro": (
            "Proposition 50, approved by voters on November 4, 2025, replaced the "
            "congressional map that the California Citizens Redistricting Commission drew "
            "after the 2020 census with one the Legislature passed as AB 604. The new map "
            "is used for the 2026, 2028 and 2030 elections; after the 2030 census the "
            "commission draws the next one. Every district changed shape, and some members "
            "are running in a district with a different number from the one they hold."
        ),
        "plans": (
            {
                "key": "old",
                "shapes": "old_s",
                "points": "old_pts",
                "label": "Before",
                "title": "2021 commission map",
                "used": "the 2022 and 2024 elections",
                "drawnBy": "the California Citizens Redistricting Commission, after the 2020 census",
            },
            {
                "key": "new",
                "shapes": "new_s",
                "points": "new_pts",
                "label": "After",
                "title": "Proposition 50 map",
                "used": "the 2026, 2028 and 2030 elections",
                "drawnBy": "the Legislature as AB 604, approved by voters as Proposition 50 "
                           "on November 4, 2025",
            },
        ),
        "counties": "counties",
        # Where districts are too small to number at statewide scale.
        "insets": (
            ("bay", "Bay Area", (-122.82, 36.95, -121.35, 38.40)),
            ("la", "Los Angeles & Orange County", (-118.95, 33.40, -116.95, 34.42)),
            ("sd", "San Diego", (-117.45, 32.53, -116.80, 33.30)),
        ),
        "sources": (
            "District boundaries: California Citizens Redistricting Commission final 2021 "
            "map, and the Proposition 50 (AB 604) map, from Wikimedia Commons map data "
            "(CC0), simplified for display.",
            "County lines: U.S. Census Bureau, via us-atlas. Town locations: U.S. Census "
            "Bureau 2020 Gazetteer, checked against USGS GNIS; populations, used only to "
            "choose which towns to label: Census Vintage 2024 estimates.",
            "Shares of area are measured on an equal-area projection of the simplified "
            "boundaries. They describe land, not people.",
        ),
    },
}


def plan_codes():
    """States with a before-and-after district map."""
    return sorted(PLANS)


def index():
    """``{code: {page, name}}`` for the build metadata the pages read."""
    return {code: {"page": PLANS[code]["page"], "name": PLANS[code]["name"]}
            for code in plan_codes()}


# --------------------------------------------------------------- projection

class _Albers:
    """Spherical Albers equal-area conic, fitted to a box later."""

    def __init__(self, parallels=PARALLELS, meridian=CENTRAL_MERIDIAN):
        phi0, phi1 = (math.radians(p) for p in parallels)
        self.n = (math.sin(phi0) + math.sin(phi1)) / 2
        self.c = 1 + math.sin(phi0) * (2 * self.n - math.sin(phi0))
        self.r0 = math.sqrt(self.c) / self.n
        self.meridian = meridian

    def raw(self, lon, lat):
        """Unscaled ``(x, y)`` with y pointing north, on the unit sphere."""
        lam = math.radians(lon - self.meridian) * self.n
        r = math.sqrt(self.c - 2 * self.n * math.sin(math.radians(lat))) / self.n
        return (r * math.sin(lam), self.r0 - r * math.cos(lam))


class _Fit:
    """Scale and flip raw coordinates into the emitted ``WIDTH``-wide box."""

    def __init__(self, raw_points):
        xs = [p[0] for p in raw_points]
        ys = [p[1] for p in raw_points]
        self.min_x, self.max_y = min(xs), max(ys)
        self.k = (WIDTH - 2 * PAD) / (max(xs) - self.min_x)
        self.height = int(math.ceil(self.k * (self.max_y - min(ys)) + 2 * PAD))

    def __call__(self, point):
        return (PAD + self.k * (point[0] - self.min_x),
                PAD + self.k * (self.max_y - point[1]))


# ------------------------------------------------------------------ loading

def _read_json(path, what):
    if not os.path.exists(path):
        raise DistrictsError(f"{what} not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError as exc:
        raise DistrictsError(f"{path} is not valid JSON: {exc}") from exc


def _decode_point(topo, coordinates):
    """A Point's position. Quantised topologies store points as integers on
    the same grid as the arcs, but absolute rather than delta-encoded."""
    transform = topo.get("transform")
    if not transform:
        return (float(coordinates[0]), float(coordinates[1]))
    (sx, sy), (tx, ty) = transform["scale"], transform["translate"]
    return (coordinates[0] * sx + tx, coordinates[1] * sy + ty)


def _numbered(topo, name, seats, kind):
    """``{district number: geometry}`` for one object, checked for 1..seats."""
    obj = (topo.get("objects") or {}).get(name)
    if not obj:
        raise DistrictsError(f"topology has no '{name}' object")
    found = {}
    for geometry in obj.get("geometries", []):
        number = (geometry.get("properties") or {}).get("d")
        if not isinstance(number, int) or isinstance(number, bool):
            raise DistrictsError(f"'{name}' has a {kind} with no district number")
        if number in found:
            raise DistrictsError(f"'{name}' numbers district {number} twice")
        found[number] = geometry
    expected = set(range(1, seats + 1))
    if set(found) != expected:
        missing = sorted(expected - set(found))
        extra = sorted(set(found) - expected)
        raise DistrictsError(
            f"'{name}' should number districts 1-{seats}"
            + (f"; missing {missing}" if missing else "")
            + (f"; unexpected {extra}" if extra else "")
        )
    return found


# ----------------------------------------------------------------- geometry

def _contains(rings, x, y):
    """Even-odd point-in-polygon over every ring, so holes count as outside."""
    inside = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, y0 = ring[i]
            x1, y1 = ring[(i + 1) % n]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


def _spans(rings, y):
    """The intervals of the horizontal line at *y* that lie inside *rings*."""
    xs = []
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, y0 = ring[i]
            x1, y1 = ring[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def interior_point(rings):
    """A point well inside *rings*, for a label.

    A centroid can fall outside a crescent-shaped county; the middle of the
    widest horizontal span through the shape cannot.
    """
    box = geo.bounds(rings)
    if box is None:
        return None
    best = None
    for step in range(1, 20):
        y = box[1] + (box[3] - box[1]) * step / 20
        for x0, x1 in _spans(rings, y):
            if best is None or x1 - x0 > best[0]:
                best = (x1 - x0, (x0 + x1) / 2, y)
    if best is None:
        return None
    return (geo._round(best[1]), geo._round(best[2]))


def lines_to_path(lines):
    """Open polylines as one SVG path, encoded as ``geo.rings_to_path`` is."""
    parts = []
    for line in lines:
        drawn = []
        for x, y in line:
            point = (geo._round(x), geo._round(y))
            if not drawn or drawn[-1] != point:
                drawn.append(point)
        if len(drawn) < 2:
            continue
        px, py = drawn[0]
        body = []
        for x, y in drawn[1:]:
            dx, dy = geo._round(x - px), geo._round(y - py)
            body.append(f"{geo._num(dx)}{'' if dy < 0 else ','}{geo._num(dy)}")
            px, py = x, y
        parts.append(f"M{geo._num(drawn[0][0])},{geo._num(drawn[0][1])}l" + " ".join(body))
    return "".join(parts)


def measure(plans, height, step=SCAN_STEP):
    """Area of every district and of every overlap between two plans.

    *plans* is two ``{district: rings}`` maps in emitted coordinates. Each
    horizontal scanline is cut where any district boundary crosses it, and
    every piece is credited to the districts that contain it - the even-odd
    rule per district, so holes and islands come out right. Returns
    ``(areas, overlaps)``: ``areas[p][d]`` and ``overlaps[(old, new)]``, in
    square emitted units.
    """
    rows = int(math.ceil(height / step))
    crossings = [[] for _ in range(rows)]
    for p, districts in enumerate(plans):
        for number, rings in districts.items():
            for ring in rings:
                n = len(ring)
                for i in range(n):
                    x0, y0 = ring[i]
                    x1, y1 = ring[(i + 1) % n]
                    if y0 == y1:
                        continue
                    lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
                    # Rows sit at (r + 0.5) * step; an edge owns the rows in
                    # [lo, hi), so a shared vertex is never counted twice.
                    first = max(0, int(math.ceil(lo / step - 0.5)))
                    last = min(rows, int(math.ceil(hi / step - 0.5)))
                    slope = (x1 - x0) / (y1 - y0)
                    for r in range(first, last):
                        crossings[r].append((x0 + ((r + 0.5) * step - y0) * slope, p, number))

    areas = [dict.fromkeys(districts, 0.0) for districts in plans]
    overlaps = {}
    for row in crossings:
        if not row:
            continue
        row.sort()
        inside = [set(), set()]
        last_x = row[0][0]
        for x, p, number in row:
            length = x - last_x
            if length > 0:
                for a in inside[0]:
                    areas[0][a] += length
                    for b in inside[1]:
                        overlaps[(a, b)] = overlaps.get((a, b), 0.0) + length
                for b in inside[1]:
                    areas[1][b] += length
            inside[p] ^= {number}
            last_x = x
    for plan_areas in areas:
        for number in plan_areas:
            plan_areas[number] *= step
    return areas, {key: value * step for key, value in overlaps.items()}


def flows(areas, overlaps):
    """``[[old, new, share of new, share of old], ...]`` for real overlaps.

    Raises when a district is not covered by the other plan: two maps of the
    same state must account for each other's every district.
    """
    out = []
    covered = [dict.fromkeys(areas[0], 0.0), dict.fromkeys(areas[1], 0.0)]
    for (old, new), area in sorted(overlaps.items()):
        of_new = area / areas[1][new] if areas[1][new] else 0.0
        of_old = area / areas[0][old] if areas[0][old] else 0.0
        covered[0][old] += of_old
        covered[1][new] += of_new
        if max(of_new, of_old) >= MIN_FLOW:
            out.append([old, new, round(of_new, 3), round(of_old, 3)])
    short = [(which, number, share)
             for which, shares in zip(("old", "new"), covered)
             for number, share in sorted(shares.items()) if share < MIN_COVERAGE]
    if short:
        raise DistrictsError(
            "districts the other plan does not cover: " + ", ".join(
                f"{which} {number} ({share:.0%})" for which, number, share in short))
    return out


# --------------------------------------------------------------------- build

def build_state(code, root="."):
    """Project one state's plans into the structure the page renders."""
    spec = PLANS[code]
    topo = _read_json(os.path.join(root, spec["file"]), "District map")
    if topo.get("type") != "Topology":
        raise DistrictsError(f"{spec['file']} is not a TopoJSON Topology")
    places = _read_json(os.path.join(root, spec["places"]), "Place list")

    arcs = geo.decode_arcs(topo)
    albers = _Albers()
    raw_arcs = [[albers.raw(lon, lat) for lon, lat in arc] for arc in arcs]

    seats = spec["seats"]
    shapes, points = [], []
    for plan in spec["plans"]:
        shapes.append(_numbered(topo, plan["shapes"], seats, "shape"))
        points.append(_numbered(topo, plan["points"], seats, "label point"))

    raw_rings = [
        {n: geo.geometry_rings(g, raw_arcs) for n, g in sorted(found.items())}
        for found in shapes
    ]
    fit = _Fit([p for plan in raw_rings for rings in plan.values()
                for ring in rings for p in ring])
    rings = [
        {n: [[fit(p) for p in ring] for ring in plan_rings] for n, plan_rings in plan.items()}
        for plan in raw_rings
    ]
    for plan, plan_rings in zip(spec["plans"], rings):
        empty = [n for n, r in plan_rings.items() if not geo.rings_to_path(r)]
        if empty:
            raise DistrictsError(f"{plan['key']} plan has no shape for {empty}")

    areas, overlaps = measure(rings, fit.height)
    out_plans = []
    for plan, plan_rings, plan_points, plan_areas in zip(spec["plans"], rings, points, areas):
        districts = {}
        for number, district_rings in plan_rings.items():
            at = fit(albers.raw(*_decode_point(topo, plan_points[number]["coordinates"])))
            if not _contains(district_rings, *at):
                # A number drawn over the wrong shape is a silent error.
                raise DistrictsError(
                    f"{plan['key']} plan: district {number}'s label point is outside it")
            districts[str(number)] = {
                "d": geo.rings_to_path(district_rings),
                "at": [geo._round(at[0]), geo._round(at[1])],
                "box": list(geo.bounds(district_rings)),
                "area": int(round(plan_areas[number])),
            }
        out_plans.append({
            "key": plan["key"], "label": plan["label"], "title": plan["title"],
            "used": plan["used"], "drawnBy": plan["drawnBy"], "districts": districts,
        })

    return {
        "name": spec["name"],
        "seats": seats,
        "page": spec["page"],
        "viewBox": [0, 0, WIDTH, fit.height],
        # Kilometres per map unit, so every "area" here has a stated unit.
        "unitKm": round(EARTH_RADIUS_KM / fit.k, 6),
        "plans": out_plans,
        "flows": flows(areas, overlaps),
        "counties": _counties(topo, raw_arcs, fit, spec["counties"]),
        "places": _places(places, albers, fit),
        "insets": [
            {"key": key, "title": title, "box": _box(albers, fit, lonlat)}
            for key, title, lonlat in spec["insets"]
        ],
        "sources": list(spec["sources"]),
    }


def _counties(topo, raw_arcs, fit, name):
    """County lines - inner borders and the state's edge - and name points."""
    obj = (topo.get("objects") or {}).get(name)
    if not obj:
        raise DistrictsError(f"topology has no '{name}' object")
    users = {}
    names = []
    for index, geometry in enumerate(obj.get("geometries", [])):
        for arc in _arc_indices(geometry.get("arcs", [])):
            users.setdefault(arc if arc >= 0 else ~arc, set()).add(index)
        county = (geometry.get("properties") or {}).get("name")
        rings = [[fit(p) for p in ring] for ring in geo.geometry_rings(geometry, raw_arcs)]
        at = interior_point(rings) if county else None
        if at:
            # The area decides which names win when two would collide.
            names.append([county, at[0], at[1], int(round(_rough_area(rings)))])
    inner = [[fit(p) for p in raw_arcs[a]] for a, who in sorted(users.items()) if len(who) > 1]
    edge = [[fit(p) for p in raw_arcs[a]] for a, who in sorted(users.items()) if len(who) == 1]
    names.sort(key=lambda n: (-n[3], n[0]))
    return {"mesh": lines_to_path(inner), "outline": lines_to_path(edge), "names": names}


def _rough_area(rings, step=2.0):
    """Area by coarse scanlines - enough to rank labels, nothing more."""
    box = geo.bounds(rings)
    if box is None:
        return 0.0
    total, y = 0.0, box[1] + step / 2
    while y < box[3]:
        total += sum(x1 - x0 for x0, x1 in _spans(rings, y)) * step
        y += step
    return total


def _arc_indices(nested):
    for item in nested:
        if isinstance(item, list):
            yield from _arc_indices(item)
        else:
            yield item


def _places(payload, albers, fit):
    out = []
    for name, lon, lat, population in payload.get("places", []):
        x, y = fit(albers.raw(lon, lat))
        if 0 <= x <= WIDTH and 0 <= y <= fit.height:
            out.append([name, geo._round(x), geo._round(y), population])
    if not out:
        raise DistrictsError("no town in the place list falls on the map")
    out.sort(key=lambda p: (-p[3], p[0]))
    return out


def _box(albers, fit, lonlat):
    """``[x, y, w, h]`` around a longitude/latitude box. On a conic map the
    parallels curve, so the edges' midpoints are included with the corners."""
    west, south, east, north = lonlat
    middle = (west + east) / 2
    corners = [fit(albers.raw(lon, lat)) for lon, lat in (
        (west, south), (west, north), (east, north), (east, south),
        (middle, south), (middle, north))]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return [geo._round(min(xs)), geo._round(min(ys)),
            geo._round(max(xs) - min(xs)), geo._round(max(ys) - min(ys))]


def build(root="."):
    """Every state with a before-and-after map, keyed by postal code."""
    return {code: build_state(code, root) for code in plan_codes()}


def stats(districts):
    return {
        "district_maps": len(districts),
        "district_bytes": sum(
            len(d["d"]) for state in districts.values()
            for plan in state["plans"] for d in plan["districts"].values()),
    }
