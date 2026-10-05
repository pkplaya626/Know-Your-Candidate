"""Rebuild legislative_maps/: every state's state senate and house districts.

The state legislature pages draw each state's legislative districts, the way
the district pages draw its congressional ones. The boundaries are vendored
here from the Census Bureau and projected by the build (kyc/legislature.py);
nothing in this tool is a judgement about geography, and everything it writes
can be rebuilt by running it again.

Source: the Census Bureau's 2025 cartographic boundary files at 1:500,000,
one per state and chamber - cb_2025_<fips>_sldu_500k (upper chambers) and
cb_2025_<fips>_sldl_500k (lower chambers; Nebraska has none). Each district
keeps the Census code (SLDUST/SLDLST), its name (NAME) and the legislative
session year the boundaries are for (LSY), so a state whose lines changed
after the Census captured them is visible rather than silently drawn wrong.
The Bureau's boundaries are shared exactly between neighbours, so they are
simplified along shared arcs, never shape by shape. County lines come from
the same 1:5,000,000 county file as the district maps, for orientation.

Each state's file is a TopoJSON topology with objects ``upper``,
``upper_pts`` (one label point per district, its pole of inaccessibility),
``lower`` and ``lower_pts`` (absent for Nebraska), and ``counties``.

    python tools/fetch_legislative_maps.py                # every state
    python tools/fetch_legislative_maps.py --states TX,NH # some states
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fetch_district_maps as maps  # noqa: E402
from kyc.geo import FIPS_TO_STATE  # noqa: E402

CENSUS_2025 = "https://www2.census.gov/geo/tiger/GENZ2025/shp/"
CHAMBER_URL = CENSUS_2025 + "cb_2025_{fips}_{layer}_500k.zip"
OUT_DIR = "legislative_maps"
VINTAGE = "U.S. Census Bureau, 2025 cartographic boundary files (1:500,000)"
FALLBACK_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_{fips}_{layer}_500k.zip"
FALLBACK_VINTAGE = "U.S. Census Bureau, 2024 cartographic boundary files (1:500,000)"
# Legislative districts are far smaller than congressional ones - a Boston
# house district is a few kilometres across - so they keep more detail: 120 m,
# rising with the state's size (an eight-thousandth of its diagonal), so
# Alaska's coast does not cost what Massachusetts's districts need.
TOLERANCE_M = 120.0
MAX_TOLERANCE_M = 300.0


def tolerance_for(items):
    import math
    lons = [p[0] for _, rings in items for r in rings for p in r]
    lats = [p[1] for _, rings in items for r in rings for p in r]
    mid = math.radians((min(lats) + max(lats)) / 2)
    width = (max(lons) - min(lons)) * 111320.0 * math.cos(mid)
    height = (max(lats) - min(lats)) * 110574.0
    # Capped: Alaska's Aleutians cross the 180th meridian, so its "width"
    # spans the globe, and Anchorage's districts are a few kilometres across.
    return min(MAX_TOLERANCE_M, max(TOLERANCE_M, math.hypot(width, height) / 8000.0))
UNICAMERAL = ("NE",)


def _serves_zip(url):
    """Whether *url* answers with a zip, from its first bytes. A refused file
    answers at once with a "Request Rejected" page, and is not worth the
    downloader's minutes of retries. A cached file is taken as served."""
    import hashlib
    import urllib.request
    name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    if os.path.exists(os.path.join(maps.cache_dir(), name)):
        return True
    request = urllib.request.Request(url, headers={"User-Agent": maps.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(4) == b"PK\x03\x04"
    except OSError:
        return False


def chamber(code, layer):
    """``[(properties, rings)]`` for one chamber of one state."""
    fips = next(f for f, c in FIPS_TO_STATE.items() if c == code)
    field = "SLDUST" if layer == "sldu" else "SLDLST"
    items = []
    url = CHAMBER_URL.format(fips=fips, layer=layer)
    vintage = VINTAGE
    try:
        if not _serves_zip(url):
            raise RuntimeError(f"{url} is refused")
        maps.get(url, pause=2.0)        # paced: a burst gets "Request Rejected"
    except RuntimeError:
        # The Census server refuses some 2025 files outright (New Mexico's
        # senate map, on 2026-10-05) though its listing shows them. The 2024
        # release holds the same districts, those set for the 2024 elections.
        url = FALLBACK_URL.format(fips=fips, layer=layer)
        maps.get(url, pause=2.0)
        vintage = FALLBACK_VINTAGE
    for row, rings in maps.read_layer(url):
        district = (row.get(field) or "").strip()
        if not district or district.upper().startswith("ZZ"):
            continue                    # "ZZZ": water and land in no district
        items.append(({"id": district, "name": (row.get("NAME") or "").strip(),
                       "lsy": (row.get("LSY") or "").strip()}, rings))
    if not items:
        raise SystemExit(f"{code}: no {layer} districts in the Census file")
    for props, _ in items:
        props["vintage"] = vintage
    ids = [p["id"] for p, _ in items]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{code}: a {layer} district appears twice")
    return sorted(items, key=lambda item: item[0]["id"])


def state_maps(codes):
    os.makedirs(OUT_DIR, exist_ok=True)
    counties = {}
    for row, rings in maps.read_layer(maps.COUNTIES_URL):
        code = FIPS_TO_STATE.get(row["STATEFP"])
        if code in codes:
            counties.setdefault(code, []).append(({"name": row["NAMELSAD"]}, rings))
    for code in codes:
        layers = {"upper": chamber(code, "sldu")}
        if code not in UNICAMERAL:
            layers["lower"] = chamber(code, "sldl")
        lats = [p[1] for _, rings in layers["upper"] for r in rings for p in r]
        topo = maps.Topology((min(lats) + max(lats)) / 2)
        sources = {}
        tolerance = tolerance_for(layers["upper"])
        for name, items in layers.items():
            topo.add(name, items, tolerance=tolerance)
            topo.label_points(name, f"{name}_pts")
            years = sorted({p["lsy"] for p, _ in items if p["lsy"]})
            sources[name] = {"cite": items[0][0]["vintage"], "lsy": years}
            for props, _ in items:
                props.pop("vintage", None)
        topo.add("counties", sorted(counties.get(code, []), key=lambda i: i[0]["name"]))
        payload = topo.topojson()
        payload["sources"] = sources
        path = os.path.join(OUT_DIR, f"{code.lower()}.json")
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
        os.replace(path + ".tmp", path)
        sizes = {k: len(v) for k, v in layers.items()}
        print(f"{code}: {os.path.getsize(path) // 1024} KB at {tolerance:.0f} m, districts {sizes}, "
              f"session years {[s['lsy'] for s in sources.values()]}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--states", help="comma-separated postal codes (default: all 50)")
    args = parser.parse_args(argv)
    from kyc.government_maps import STATES
    codes = [c.strip().upper() for c in args.states.split(",")] if args.states else STATES
    state_maps(codes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
