"""Rebuild local_maps/: every state's incorporated places - its cities, towns,
villages and boroughs - and, in the twenty states with town or township
governments, its county subdivisions, as a point each, for the county pages.

Source: the Census Bureau's 2025 cartographic boundary files of places at
1:500,000, one per state (cb_2025_<fips>_place_500k). Census-designated
places (LSAD 57) are left out: a CDP is a statistical area, not a government,
and the county pages are about governments. Each place keeps its Census code
(GEOID), its name (NAME) and its legal form as the Census writes it after the
name (NAMELSAD less NAME: "city", "town", "village", "borough", ...) - never a
form inferred from the name.

A place is drawn as one point: the pole of inaccessibility of its largest
piece of land, so a city with an outlying island or annexed strip is placed
where most of it is (the Census's own internal point for San Francisco is on
the Farallon Islands). The build (kyc/counties.py) joins each place to its
government in the Census listing; nothing here is a judgement, and
everything it writes can be rebuilt by running it again.

County subdivisions come from the same release's cartographic boundary files
(cb_2025_<fips>_cousub_500k), for the states whose Census table counts town
or township governments (data/census_governments.json). Every subdivision is
kept with its code (COUSUBFP), its county and one point, cities and CCDs
too: the build draws only those it joins to a township government on that
code, so nothing here decides which subdivisions govern. A subdivision
coded 00000 is water the Census assigns to no subdivision, and is skipped.

    python tools/fetch_local_maps.py                # every state
    python tools/fetch_local_maps.py --states TX,DE # some states
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fetch_district_maps as maps  # noqa: E402
from kyc.geo import FIPS_TO_STATE, polylabel  # noqa: E402

PLACES_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_{fips}_place_500k.zip"
COUSUB_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_{fips}_cousub_500k.zip"
OUT_DIR = "local_maps"
SOURCE = "U.S. Census Bureau, 2025 cartographic boundary files of places (1:500,000)"
COUSUB_SOURCE = "U.S. Census Bureau, 2025 cartographic boundary files of county subdivisions (1:500,000)"
CDP = "57"
# Every place the Census draws in Hawaii is a CDP: its counties are its only
# general-purpose local governments (Honolulu's is a consolidated city and
# county). Anywhere else, a file with no incorporated place is refused.
NO_PLACES = {"HI"}


def _area(ring):
    return sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1])) / 2


def point_of(rings):
    """``[lon, lat]``: the pole of inaccessibility of the largest piece,
    found in local metres so a degree of longitude is not taken for a
    degree of latitude."""
    lat0 = sum(p[1] for r in rings for p in r) / sum(len(r) for r in rings)
    kx, ky = math.cos(math.radians(lat0)) * 111320.0, 110574.0
    metres = [[(x * kx, y * ky) for x, y in ring] for ring in rings]
    largest = max(metres, key=lambda r: abs(_area(r)))
    # Holes inside the largest piece (an unincorporated island) count too.
    holes = [r for r in metres if r is not largest and _inside_ring(largest, *r[0])]
    x, y = polylabel([largest] + holes)
    return [round(x / kx, 6), round(y / ky, 6)]


def _inside_ring(ring, x, y):
    hit = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
    return hit


BALANCE = " (balance)"


def legal_form(row):
    """``("Abbott", "city")`` from NAME "Abbott" and NAMELSAD "Abbott city".
    The part of a consolidated government outside its other places is named
    "Milford city (balance)" in both fields; it is ``("Milford city",
    "balance")``. A place named with no form ("Macon-Bibb County") has an
    empty one; a form written before the name (Illinois's "Precinct 17") is
    read from there."""
    name, full = row["NAME"].strip(), row["NAMELSAD"].strip()
    if name.endswith(BALANCE):
        return name[: -len(BALANCE)], "balance"
    if full.startswith(name):
        # "Macon-Bibb County" names no form at all; none is inferred.
        return name, full[len(name):].strip()
    if full.endswith(name):
        return name, full[: -len(name)].strip()      # Illinois's "Precinct 17"
    raise SystemExit(f"{row['GEOID']}: {full!r} does not contain its name {name!r}")


def state_places(code):
    fips = next(f for f, c in FIPS_TO_STATE.items() if c == code)
    url = PLACES_URL.format(fips=fips)
    out = []
    for row, rings in maps.read_layer(url):
        if row["LSAD"] == CDP or not rings:
            continue
        name, kind = legal_form(row)
        out.append({"id": row["GEOID"], "name": name, "kind": kind,
                    "point": point_of(rings), "land": int(row["ALAND"] or 0)})
    if not out and code not in NO_PLACES:
        raise SystemExit(f"{code}: no incorporated places in {url}")
    ids = [p["id"] for p in out]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{code}: a place appears twice in {url}")
    return url, sorted(out, key=lambda p: p["id"])


def township_states(root="."):
    """The states whose Census table counts town or township governments."""
    from kyc import census
    table = census.load_cache(root)
    if not table:
        raise SystemExit(f"no {census.CACHE_PATH}; run 'python build_profile_site.py census'")
    return sorted(code for code, counts in table["states"].items() if counts.get("township"))


def state_subdivisions(code):
    fips = next(f for f, c in FIPS_TO_STATE.items() if c == code)
    url = COUSUB_URL.format(fips=fips)
    out = []
    for row, rings in maps.read_layer(url):
        if row["COUSUBFP"] == "00000" or not rings:
            continue
        name, kind = legal_form(row)
        out.append({"id": row["GEOID"], "county": row["STATEFP"] + row["COUNTYFP"],
                    "code": row["COUSUBFP"], "name": name, "kind": kind,
                    "point": point_of(rings), "land": int(row["ALAND"] or 0)})
    if not out:
        raise SystemExit(f"{code}: no county subdivisions in {url}")
    ids = [p["id"] for p in out]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{code}: a county subdivision appears twice in {url}")
    return url, sorted(out, key=lambda p: p["id"])


def dump(code, url, places, cousub_url=None, subdivisions=None):
    """One place per line, so a refresh diffs place by place."""
    def compact(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    head = {"state": code, "source": SOURCE, "url": url}
    if subdivisions is not None:
        head.update(subdivisionSource=COUSUB_SOURCE, subdivisionUrl=cousub_url)
    text = ("{\n" + ",\n".join(f"{compact(k)}:{compact(v)}" for k, v in head.items()) +
            ',\n"places":[\n' + ",\n".join(compact(p) for p in places) + "\n]")
    if subdivisions is not None:
        text += ',\n"subdivisions":[\n' + ",\n".join(compact(p) for p in subdivisions) + "\n]"
    return text + "}\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--states", help="comma-separated postal codes (default: all 50)")
    args = parser.parse_args(argv)
    from kyc.government_maps import STATES
    codes = [c.strip().upper() for c in args.states.split(",")] if args.states else STATES
    towns = set(township_states())
    os.makedirs(OUT_DIR, exist_ok=True)
    for code in codes:
        url, places = state_places(code)
        cousub_url, subdivisions = state_subdivisions(code) if code in towns else (None, None)
        path = os.path.join(OUT_DIR, f"{code.lower()}.json")
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            handle.write(dump(code, url, places, cousub_url, subdivisions))
        os.replace(path + ".tmp", path)
        kinds = {}
        for p in places:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        print(f"{code}: {len(places)} places" +
              (f", {len(subdivisions)} county subdivisions" if subdivisions is not None else "") +
              f", {os.path.getsize(path) // 1024} KB, {kinds}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
