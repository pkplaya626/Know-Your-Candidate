"""Rebuild lookup_maps/: where a ZIP code or a location falls, for "Find who
represents me".

A reader types a ZIP code or shares a location, and the page names who
represents them at every level the site holds. It does that on the device,
from one state's file (kyc/lookup.py emits it as data/lookup/<st>.js); nothing
the reader types is sent anywhere. This tool vendors what those files are
built from. Nothing in it is a judgement about geography, and everything it
writes can be rebuilt by running it again.

ZIP codes. The Census Bureau maps ZIP codes as ZIP Code Tabulation Areas
(ZCTAs), built from the addresses in each census block. A ZIP used only for
post office boxes, or by one building, has no area and so no ZCTA. Each
ZCTA's share of every district it touches is a share of its land:

* the districts members were elected in (the 119th Congress): the Bureau's
  own relationship file, tab20_cd11920_zcta520_natl, AREALAND_PART over the
  ZCTA's AREALAND - exact, from the blocks;
* state senate and house districts: tab20_sldu202420_zcta520_natl and
  tab20_sldl202420_zcta520_natl, the 2024 districts - the session year every
  state's legislative map on this site carries (legislative_maps/, LSY);
* counties: tab20_zcta520_county20_natl, except where a state's
  county-equivalents changed after 2020 (COUNTIES_CHANGED), which are
  measured instead, as below;
* a redrawn state's 2026 map (kyc.districts.REDRAWN): no relationship file
  exists, so the share is measured - the Census 2020 ZCTA boundaries at
  1:500,000 (cb_2020_us_zcta520_500k) overlaid on the enacted plan, from the
  same file district_maps/ is built from, by scanlines on the state's own
  equal-area projection, STEP_KM apart. The same measurement of the 119th
  map is compared with the relationship file for every such state, and the
  agreement is written into the file and printed, so how far a measured
  share can be trusted is on the record, not assumed.

Locations. A reader's point is placed on boundaries finer than the district
pages draw: the 119th districts at 1:500,000 (cb_2024_us_cd119_500k), the
2026 plan from the state's own file, and the counties at 1:500,000
(cb_2025_us_county_500k), each simplified along shared arcs to TOLERANCE_M.
The district pages' maps are 1:5,000,000, and within 3 km of a line they
could not tell a reader which side they were on (RACES-01).

Each state's file is a TopoJSON topology with objects ``current`` and, for a
redrawn state, ``next`` (properties ``d``, the district number, 0 at large)
and ``counties`` (``id``, the Census GEOID, and ``name``), plus ``zips``:
``{zcta: {"cd": [[district, share]], "next": [...], "su": [[code, share]],
"sl": [...], "co": [[geoid, share]]}}``.

    python tools/fetch_lookup_maps.py                # every state
    python tools/fetch_lookup_maps.py --states OH,CT # some states
"""

import argparse
import io
import json
import math
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fetch_district_maps as maps  # noqa: E402
from kyc import districts  # noqa: E402
from kyc.geo import FIPS_TO_STATE  # noqa: E402

REL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/"
REL_CD = REL + "cd-sld/tab20_cd11920_zcta520_natl.txt"
REL_SLDU = REL + "cd-sld/tab20_sldu202420_zcta520_natl.txt"
REL_SLDL = REL + "cd-sld/tab20_sldl202420_zcta520_natl.txt"
REL_COUNTY = REL + "zcta520/tab20_zcta520_county20_natl.txt"
CD_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip"
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip"
ZCTA_URL = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip"

OUT_DIR = "lookup_maps"
# Simplification of the lookup boundaries, in metres: below the 1:500,000
# files' own generalisation, so it adds little to their error. It rises with
# the state's size (a thirty-thousandth of its diagonal) up to MAX_TOLERANCE_M:
# Alaska's coast at 25 m came to 1.4 MB, for a state elected at large.
TOLERANCE_M = 30.0
MAX_TOLERANCE_M = 200.0
# Scanline spacing for a measured share, in kilometres.
STEP_KM = 0.015
# Territories with a delegate: their Census codes are not in FIPS_TO_STATE.
TERRITORY_FIPS = {"60": "AS", "66": "GU", "69": "MP"}

# States whose county-equivalents are not the 2020 relationship file's.
# Connecticut's nine planning regions replaced its eight counties as
# county-equivalents in 2022 (Federal Register 87 FR 31636, June 6, 2022);
# the county pages draw the planning regions (cb_2025 counties), so the
# 2020 file's county codes name nothing on them.
COUNTIES_CHANGED = {"CT"}


def tolerance_for(layer):
    """The simplification for one state, from its districts' extent. The
    longitudes are spread about their own middle, so the Aleutians' crossing
    of the 180th meridian does not make Alaska the width of the globe."""
    lons = [p[0] for rings in layer.values() for r in rings for p in r]
    lats = [p[1] for rings in layer.values() for r in rings for p in r]
    mid = math.radians((min(lats) + max(lats)) / 2)
    east = [lon % 360 for lon in lons]
    span = min(max(lons) - min(lons), max(east) - min(east))
    width = span * 111320.0 * math.cos(mid)
    height = (max(lats) - min(lats)) * 110574.0
    return min(MAX_TOLERANCE_M, max(TOLERANCE_M, math.hypot(width, height) / 30000.0))


def state_of(fips):
    return FIPS_TO_STATE.get(fips) or TERRITORY_FIPS.get(fips)


# ------------------------------------------------------------ relationships

def relationship(url, target):
    """``{state: {zcta: {id: share}}}`` from a Census relationship file.

    *target* is the prefix of the other geography's columns ("CD119_20",
    "SLDU2024_20", "COUNTY_20"). A share is the part's land over the ZCTA's
    land; a ZCTA with no land at all (a few are water) is shared by water.
    Rows with no ZCTA - the parts of a district that hold none - are skipped.
    """
    text = maps.get(url).decode("utf-8-sig")
    lines = text.splitlines()
    head = lines[0].split("|")
    col = {name: i for i, name in enumerate(head)}
    out = {}
    for line in lines[1:]:
        row = line.split("|")
        zcta = row[col["GEOID_ZCTA5_20"]]
        geoid = row[col["GEOID_" + target]]
        # "ZZ" and "ZZZ": water the Census assigns to no district.
        if not zcta or not geoid or geoid.endswith("ZZ"):
            continue
        land, water = int(row[col["AREALAND_ZCTA5_20"]]), int(row[col["AREAWATER_ZCTA5_20"]])
        part_land, part_water = int(row[col["AREALAND_PART"]]), int(row[col["AREAWATER_PART"]])
        share = part_land / land if land else (part_water / water if water else 0.0)
        if share <= 0:
            continue
        code = state_of(geoid[:2])
        if not code:
            continue
        out.setdefault(code, {}).setdefault(zcta, {})[geoid] = share
    return out


# --------------------------------------------------------------- shapefiles

def read_selected(url, keep):
    """``{key: rings}`` for the records whose dBase row *keep* maps to a key
    (``keep(row) -> key or None``). Only those shapes are decoded: the
    national ZCTA file holds 33,791 of them."""
    archive = zipfile.ZipFile(io.BytesIO(maps.get(url, archive=True)))
    names = [n for n in archive.namelist() if "__MACOSX" not in n]
    rows = maps.read_dbf(archive.read([n for n in names if n.lower().endswith(".dbf")][0]),
                         "utf-8")
    wanted = {i: keep(row) for i, row in enumerate(rows)}
    wanted = {i: k for i, k in wanted.items() if k is not None}
    data = archive.read([n for n in names if n.lower().endswith(".shp")][0])
    out, pos, index = {}, 100, 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0] * 2
        if index in wanted:
            content = data[pos + 8: pos + 8 + length]
            rings = []
            if struct.unpack("<i", content[:4])[0] != 0:
                parts, points = struct.unpack("<ii", content[36:44])
                starts = struct.unpack(f"<{parts}i", content[44:44 + 4 * parts]) + (points,)
                base = 44 + 4 * parts
                flat = struct.unpack(f"<{2 * points}d", content[base: base + 16 * points])
                coords = list(zip(flat[0::2], flat[1::2]))
                rings = [coords[starts[i]:starts[i + 1]] for i in range(parts)]
            out.setdefault(wanted[index], []).extend(rings)
        pos += 8 + length
        index += 1
    if index != len(rows):
        raise SystemExit(f"{url}: {len(rows)} records but {index} shapes")
    return out


# ----------------------------------------------------------------- measuring

def overlap_shares(zctas, targets, step=STEP_KM):
    """``{zcta: {target: share}}``: each ZCTA's area inside each target, over
    the ZCTA's whole area. Both are ``{id: rings}`` in kilometres on an
    equal-area plane. One sweep of horizontal scanlines *step* apart; each
    line is cut wherever a boundary crosses it, and every piece is credited
    to the shapes holding it (even-odd, so holes are holes)."""
    edges = []
    for side, polys in ((0, zctas), (1, targets)):
        for pid, rings in polys.items():
            for ring in rings:
                for i in range(len(ring)):
                    (x0, y0), (x1, y1) = ring[i - 1], ring[i]
                    if y0 == y1:
                        continue
                    if y0 > y1:
                        x0, y0, x1, y1 = x1, y1, x0, y0
                    edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), side, pid))
    if not edges:
        return {}
    edges.sort(key=lambda e: e[0])
    bottom = edges[0][0]
    top = max(e[1] for e in edges)
    area = dict.fromkeys(zctas, 0.0)
    overlap = {}
    active, k = [], 0
    rows = int(math.ceil((top - bottom) / step))
    for r in range(rows):
        y = bottom + (r + 0.5) * step
        while k < len(edges) and edges[k][0] <= y:
            active.append(edges[k])
            k += 1
        active = [e for e in active if e[1] > y]
        cuts = sorted((e[2] + (y - e[0]) * e[3], e[4], e[5]) for e in active)
        inside = (set(), set())
        last = None
        for x, side, pid in cuts:
            if last is not None and x > last and inside[0]:
                length = (x - last) * step
                for a in inside[0]:
                    area[a] += length
                    for b in inside[1]:
                        overlap[(a, b)] = overlap.get((a, b), 0.0) + length
            inside[side].symmetric_difference_update((pid,))
            last = x
    out = {}
    for (a, b), value in overlap.items():
        if area[a] > 0:
            out.setdefault(a, {})[b] = value / area[a]
    return out


def planar(code, layers):
    """Every layer's rings in kilometres on the state's equal-area projection
    (kyc.districts.projection_for, fitted to the first layer)."""
    first = [p for rings in layers[0].values() for r in rings for p in r]
    albers = districts.projection_for(code, first)
    k = districts.EARTH_RADIUS_KM

    def one(rings):
        out = []
        for ring in rings:
            pts = []
            for lon, lat in ring:
                x, y = albers.raw(lon, lat)
                pts.append((x * k, y * k))
            out.append(pts)
        return out
    return [{key: one(rings) for key, rings in layer.items()} for layer in layers]


def agreement(measured, official):
    """How a measured share compares with the relationship file's, over the
    ZCTAs both hold: the mean and 95th-percentile largest difference, and
    how often both say "wholly in one district" (99% or more) alike."""
    diffs, same = [], 0
    for zcta, shares in official.items():
        mine = measured.get(zcta, {})
        keys = set(shares) | set(mine)
        diffs.append(max(abs(shares.get(key, 0.0) - mine.get(key, 0.0)) for key in keys))
        whole = [key for key, v in shares.items() if v >= 0.99]
        mine_whole = [key for key, v in mine.items() if v >= 0.99]
        same += whole == mine_whole
    diffs.sort()
    n = len(diffs)
    return {"zips": n,
            "meanDiff": round(sum(diffs) / n, 4) if n else 0.0,
            "p95Diff": round(diffs[int(0.95 * (n - 1))], 4) if n else 0.0,
            "sameWhole": round(same / n, 4) if n else 1.0}


# ------------------------------------------------------------------ writing

def _pairs(shares, key=None):
    """``{id: share}`` -> ``[[id, share], ...]``, largest first, to three
    places; a part that rounds to nothing is kept as 0.001 - it is there."""
    out = [[key(i) if key else i, max(0.001, round(v, 3))] for i, v in shares.items()]
    out.sort(key=lambda p: (-p[1], str(p[0])))
    return out


def number(code):
    return maps.district_number(code)


def build_state(code, cd_layer, county_layer, rel, zcta_shapes, sld_ids):
    """One state's payload."""
    lats = [p[1] for rings in cd_layer.values() for r in rings for p in r]
    topo = maps.Topology((min(lats) + max(lats)) / 2)
    seats = sorted(cd_layer)
    tolerance = tolerance_for(cd_layer)
    topo.add("current", [({"d": n}, cd_layer[n]) for n in seats], tolerance=tolerance)
    sources = {"current": "U.S. Census Bureau, cb_2024_us_cd119_500k (119th Congress, 1:500,000)",
               "counties": "U.S. Census Bureau, cb_2025_us_county_500k (1:500,000)",
               "zips": "U.S. Census Bureau, 2020 ZIP Code Tabulation Areas: relationship files "
                       "to the 119th Congress's districts, the 2024 state legislative "
                       "districts and the 2020 counties"}
    checks = {}
    plan = None
    spec = districts.REDRAWN.get(code)
    if spec:
        lons = [p[0] for rings in cd_layer.values() for r in rings for p in r]
        extent = (min(lons), min(lats), max(lons), max(lats))
        if spec.get("shapefile"):
            plan, cite = maps.official_plan(spec["shapefile"], len(seats), extent)
        else:
            plan, cited = maps.commons_plan(spec["commons"], len(seats))
            cite = sorted(set(cited))[0]
        topo.add("next", [({"d": n}, plan[n]) for n in sorted(plan)], tolerance=tolerance)
        sources["next"] = districts._plain(cite) if "[" in cite else cite
    counties = sorted(county_layer.items())
    topo.add("counties", [({"id": geoid, "name": name}, rings)
                          for (geoid, name), rings in counties], tolerance=tolerance)

    zips = {}
    for zcta, shares in rel["cd"].get(code, {}).items():
        zips.setdefault(zcta, {})["cd"] = _pairs(shares, lambda g: number(g[2:]))
    for key in ("su", "sl"):
        if key not in sld_ids:
            # D.C.'s wards and Puerto Rico's districts have no page here.
            continue
        for zcta, shares in rel[key].get(code, {}).items():
            unknown = {g[2:] for g in shares} - sld_ids.get(key, set())
            if unknown:
                raise SystemExit(f"{code} {key}: the relationship file's districts "
                                 f"{sorted(unknown)} are not on legislative_maps/")
            zips.setdefault(zcta, {})[key] = _pairs(shares, lambda g: g[2:])
    county_ids = {geoid for geoid, _ in county_layer}
    if code not in COUNTIES_CHANGED:
        for zcta, shares in rel["co"].get(code, {}).items():
            unknown = set(shares) - county_ids
            if unknown:
                raise SystemExit(f"{code}: the 2020 relationship file's counties {sorted(unknown)} "
                                 "are not in the 2025 boundaries; list the state in "
                                 "COUNTIES_CHANGED, with the record of the change")
            zips.setdefault(zcta, {})["co"] = _pairs(shares)

    measured_layers = []
    if spec:
        measured_layers.append(("next", {n: plan[n] for n in plan}))
    if code in COUNTIES_CHANGED:
        measured_layers.append(("co", {geoid: rings for (geoid, _), rings in counties}))
    if measured_layers:
        mine = set(rel["cd"].get(code, {}))
        shapes = {z: zcta_shapes[z] for z in mine if z in zcta_shapes}
        missing = sorted(mine - set(shapes))
        if missing:
            raise SystemExit(f"{code}: ZCTAs {missing[:5]} have no boundary in {ZCTA_URL}")
        layers = planar(code, [cd_layer, shapes] + [layer for _, layer in measured_layers])
        cd_km, zcta_km = layers[0], layers[1]
        if spec:
            # How far a measured share is from an exact one: the same
            # measurement of the 119th map, against the relationship file.
            exact = {z: {number(g[2:]): v for g, v in shares.items()}
                     for z, shares in rel["cd"].get(code, {}).items()}
            checks["measured"] = agreement(overlap_shares(zcta_km, cd_km), exact)
        for (key, _), layer in zip(measured_layers, layers[2:]):
            found = overlap_shares(zcta_km, layer)
            for zcta in shapes:
                if found.get(zcta):
                    zips.setdefault(zcta, {})[key] = _pairs(
                        found[zcta])
        if code in COUNTIES_CHANGED:
            sources["zipCounties"] = ("measured by overlaying the Census 2020 ZCTA "
                                      "boundaries (1:500,000) on the 2025 county boundaries")
        if spec:
            sources["zipNext"] = ("measured by overlaying the Census 2020 ZCTA "
                                  "boundaries (1:500,000) on the 2026 map")
    payload = topo.topojson()
    payload["zips"] = {z: zips[z] for z in sorted(zips)}
    payload["sources"] = sources
    payload["toleranceM"] = round(tolerance)
    if checks:
        payload["checks"] = checks
    return payload


def legislative_ids(code):
    """``{"su": ids, "sl": ids}`` from legislative_maps/<st>.json."""
    path = os.path.join("legislative_maps", f"{code.lower()}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        topo = json.load(handle)
    out = {}
    for key, name in (("su", "upper"), ("sl", "lower")):
        obj = topo["objects"].get(name)
        if obj:
            out[key] = {g["properties"]["id"] for g in obj["geometries"]}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--states", help="comma-separated postal codes (default: all)")
    args = parser.parse_args(argv)
    codes = [c.strip().upper() for c in args.states.split(",")] if args.states \
        else districts.all_codes()

    rel = {"cd": relationship(REL_CD, "CD119_20"),
           "su": relationship(REL_SLDU, "SLDU2024_20"),
           "sl": relationship(REL_SLDL, "SLDL2024_20"),
           "co": relationship(REL_COUNTY, "COUNTY_20")}
    cd = {}
    for row, rings in maps.read_layer(CD_URL):
        code = state_of(row["STATEFP"])
        if code in codes:
            cd.setdefault(code, {})[number(row["CD119FP"])] = rings
    county = {}
    for row, rings in maps.read_layer(COUNTY_URL):
        code = state_of(row["STATEFP"])
        if code in codes:
            county.setdefault(code, {})[(row["GEOID"], row["NAMELSAD"])] = rings
    measured = [c for c in codes if c in districts.REDRAWN or c in COUNTIES_CHANGED]
    wanted = {z for c in measured for z in rel["cd"].get(c, {})}
    zcta_shapes = (read_selected(ZCTA_URL, lambda row: row["ZCTA5CE20"]
                                 if row["ZCTA5CE20"] in wanted else None)
                   if wanted else {})

    os.makedirs(OUT_DIR, exist_ok=True)
    for code in codes:
        if code not in cd:
            raise SystemExit(f"{code}: no districts in {CD_URL}")
        payload = build_state(code, cd[code], county.get(code, {}), rel, zcta_shapes,
                              legislative_ids(code))
        path = os.path.join(OUT_DIR, f"{code.lower()}.json")
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
        os.replace(path + ".tmp", path)
        line = f"{code}: {os.path.getsize(path) // 1024} KB, {len(payload['zips'])} ZIP areas"
        if payload.get("checks"):
            line += f"; measured vs exact on the 119th map: {payload['checks']['measured']}"
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
