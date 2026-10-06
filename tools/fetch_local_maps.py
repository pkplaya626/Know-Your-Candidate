"""Rebuild local_maps/: every incorporated city, town and village, as a point.

The counties pages draw each state's cities and towns over its counties, so a
reader can find a city on the map and open its government. At a state's
scale most places are smaller than a pixel, so each is drawn as a dot at its
label point - the pole of inaccessibility of its largest piece, inside it and
as far from its edges as it allows (``geo.polylabel``) - and not as an
outline nobody could see or click.

Source: the Census Bureau's 2025 cartographic boundary files of places at
1:500,000, one per state (cb_2025_<fips>_place_500k). Only incorporated
places are kept: a census-designated place (LSAD 57) is a statistical area
with no government of its own. Each keeps the Census code (GEOID), its name,
its legal description (city, town, village, borough...) and its land area.

Each state's file is ``local_maps/<st>.json``:
``{"places": [{"id", "name", "kind", "point": [lon, lat], "land"}], "source"}``.

    python tools/fetch_local_maps.py                # every state
    python tools/fetch_local_maps.py --states TX,OH # some states
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fetch_district_maps as maps  # noqa: E402
from kyc.geo import FIPS_TO_STATE, polylabel  # noqa: E402

PLACE_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_{fips}_place_500k.zip"
OUT_DIR = "local_maps"
SOURCE = "U.S. Census Bureau, 2025 cartographic boundary files: places (1:500,000)"
# The Census's legal/statistical area descriptions for places. 57 is a
# census-designated place: no government, so not drawn.
CDP = "57"
KINDS = {"25": "city", "43": "town", "47": "village", "21": "borough", "37": "municipality",
         "53": "city", "54": "town", "55": "village", "28": "city", "39": "municipality",
         "00": "place"}


def _area(ring):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))) / 2


def label_point(rings):
    """The pole of the place's largest outer ring (with its holes)."""
    outer = max(rings, key=_area)
    return polylabel([outer])


def places(code):
    fips = next(f for f, c in FIPS_TO_STATE.items() if c == code)
    url = PLACE_URL.format(fips=fips)
    maps.get(url, pause=2.0)            # paced: a burst gets "Request Rejected"
    out = []
    for row, rings in maps.read_layer(url):
        lsad = (row.get("LSAD") or "").strip()
        if lsad == CDP or not rings:
            continue
        lon, lat = label_point(rings)
        out.append({"id": row["GEOID"].strip(), "name": row["NAME"].strip(),
                    "kind": KINDS.get(lsad, "place"), "lsad": lsad,
                    "point": [round(lon, 5), round(lat, 5)],
                    "land": int(row.get("ALAND") or 0)})
    ids = [p["id"] for p in out]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{code}: a place appears twice")
    return sorted(out, key=lambda p: p["id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--states", help="comma-separated postal codes (default: all 50 and D.C.)")
    args = parser.parse_args(argv)
    from kyc.government_maps import STATES
    codes = [c.strip().upper() for c in args.states.split(",")] if args.states else STATES
    os.makedirs(OUT_DIR, exist_ok=True)
    for code in codes:
        found = places(code)
        path = os.path.join(OUT_DIR, f"{code.lower()}.json")
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"state": code, "source": SOURCE, "places": found}, handle,
                      separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
        os.replace(path + ".tmp", path)
        kinds = {}
        for p in found:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        print(f"{code}: {len(found)} places, {os.path.getsize(path) // 1024} KB, {kinds}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
