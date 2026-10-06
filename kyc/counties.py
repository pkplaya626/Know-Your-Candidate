"""Each state's counties on a map, and every local government in each.

The county lines come from ``legislative_maps/<st>.json`` (the Census county
file, each county with its GEOID); the governments from
``local_governments/<st>.json`` (the Census Government Units listing,
``localgov``). They are joined on the county's Census code, never its name.

A government whose county code is not on the map - Connecticut's listing
uses the counties the state abolished in 1960, its map the planning regions
that replaced them in Census geography in 2022 - is listed under its county
area's name, never dropped and never moved to a county it is not in.
"""

import re

from . import districts as D
from . import geo, localgov, statelegs
from .government_maps import STATES
from .pages import state_name

FOLDER = "counties"

# Compact rows for the page: [type, name, city, web, size, function, flags].
KIND_ORDER = ("county", "municipal", "township", "school", "special", "dependent")


class CountiesError(RuntimeError):
    """A state's county map or listing is not what the page needs."""


def page_path(code):
    """``counties/tx.html``."""
    return f"{FOLDER}/{code.lower()}.html"


def web_address(url):
    """The listing writes many addresses in capitals. A scheme and a host are
    not case-sensitive, so they are lowered; a path can be, so it is kept as
    published."""
    match = re.match(r"^(https?)://([^/?#]+)(.*)$", url or "", re.I)
    if not match:
        return ""
    return f"{match.group(1).lower()}://{match.group(2).lower()}{match.group(3)}"


def _row(gov):
    size = gov.get("population", gov.get("enrollment"))
    return [gov["type"], gov["name"], gov.get("city", ""), web_address(gov.get("web", "")),
            size if size is not None else "", gov.get("function", ""),
            "inactive" if gov.get("inactive") else ""]


# ------------------------------------------------------------------ cities
#
# The Census listing's place code is not the Census Bureau's place code
# (Texarkana is 68810 in one, 72368 in the other), so a city's government is
# matched to its point by name, within the state, both reduced the same way
# - and where a name is shared, by the county the point falls in. On
# 2026-10-06 that matched 99% of cities in Texas, Ohio, California and
# Nebraska; what is left is listed, never guessed (rule 51).

_PREFIX = re.compile(r"^(?:city and county of|(?:city|town|village|borough|township|municipality)"
                     r" of)\s+")
_SUFFIX = re.compile(r"\s+(?:city|town|village|borough)$")


def city_key(name):
    """A city's name reduced for matching the listing to the map: "CITY OF
    ST. LOUIS" and "St. Louis city" both become "stlouis"."""
    import unicodedata
    plain = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    plain = _SUFFIX.sub("", _PREFIX.sub("", plain.strip()))
    plain = re.sub(r"\bsaint\b", "st", plain)
    plain = re.sub(r"\bmount\b", "mt", plain)
    return re.sub(r"[^a-z0-9]", "", plain)


def load_places_points(code, root="."):
    import json
    import os
    path = os.path.join(root, "local_maps", f"{code.lower()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def match_cities(points, listing, county_of):
    """``(matched, unplaced)``: ``{place id: (county fips, row index)}`` for
    each city point whose name names one municipal government - or, when
    several share the name, the one in the county the point falls in - and
    the governments no point took."""
    governments = {}
    for fips, entry in listing["counties"].items():
        for i, gov in enumerate(entry["governments"]):
            if gov["type"] == "municipal":
                governments.setdefault(city_key(gov["census"]), []).append((fips, i))
    matched, taken = {}, set()
    for place in points:
        options = governments.get(city_key(place["name"]), [])
        if len(options) > 1:
            options = [o for o in options if o[0] == county_of.get(place["id"])]
        if len(options) == 1 and options[0] not in taken:
            matched[place["id"]] = options[0]
            taken.add(options[0])
    unplaced = [(fips, i) for refs in governments.values() for fips, i in refs if (fips, i) not in taken]
    return matched, unplaced


def build_state(code, root=".", places=None):
    topo = statelegs.load_map(code, root)
    if not topo or "counties" not in (topo.get("objects") or {}):
        raise CountiesError(f"no county map for {code}; run tools/fetch_legislative_maps.py")
    listing = localgov.load(code, root)
    if not listing:
        raise CountiesError(f"no {localgov.OUT_DIR}/{code.lower()}.json; run 'localgov'")
    arcs = geo.decode_arcs(topo)
    shapes = {g["properties"]["id"]: g for g in topo["objects"]["counties"]["geometries"]}
    points = {g["properties"]["id"]: g for g in topo["objects"]["counties_pts"]["geometries"]}
    if set(shapes) != set(points) or not shapes:
        raise CountiesError(f"{code}: county label points do not match the counties")

    lonlat = [p for g in shapes.values() for ring in geo.geometry_rings(g, arcs) for p in ring]
    albers = D.projection_for(code, lonlat)
    raw_arcs = [[albers.raw(lon, lat) for lon, lat in arc] for arc in arcs]
    raw = {i: geo.geometry_rings(g, raw_arcs) for i, g in shapes.items()}
    fit = D._Fit([p for rings in raw.values() for ring in rings for p in ring])
    viewbox = [0, 0, D.WIDTH, fit.height]
    towns = D._places((places or {}).get(code, []), albers, fit)

    found = {}
    for fips, rings in sorted(raw.items()):
        fitted = [[fit(p) for p in ring] for ring in rings]
        at = fit(albers.raw(*D._decode_point(topo, points[fips]["coordinates"])))
        if not D._contains(fitted, *at):
            raise CountiesError(f"{code} county {fips}: label point outside it")
        found[fips] = {
            "d": geo.rings_to_path(fitted),
            "name": shapes[fips]["properties"]["name"],
            "label": "",
            "at": [geo._round(at[0]), geo._round(at[1])],
            "box": list(geo.bounds(fitted)),
            "room": geo._round(geo.signed_distance(at[0], at[1], fitted)),
        }

    governments, unmatched = {}, []
    for fips, entry in sorted(listing["counties"].items()):
        rows = [_row(g) for g in entry["governments"]]
        if fips in found:
            governments[fips] = rows
        else:
            unmatched.append({"name": entry["name"], "fips": fips, "governments": rows})
    statewide = [_row(g) for g in listing.get("statewide", [])]

    # Cities and towns: each incorporated place a point, in the county it
    # falls in, with the government it is.
    city_points = (load_places_points(code, root) or {}).get("places")
    if city_points is None:
        raise CountiesError(f"no local_maps/{code.lower()}.json; run tools/fetch_local_maps.py")
    fitted_counties = {fips: [[fit(p) for p in ring] for ring in rings] for fips, rings in raw.items()}
    cities, county_of = {}, {}
    for place in city_points:
        x, y = fit(albers.raw(*place["point"]))
        home = next((fips for fips, rings in fitted_counties.items() if D._contains(rings, x, y)), "")
        county_of[place["id"]] = home
        cities[place["id"]] = [geo._round(x), geo._round(y), place["kind"], place["name"], home, ""]
    matched, unplaced = match_cities(city_points, listing, county_of)
    for pid, (fips, index) in matched.items():
        if fips in governments:
            cities[pid][5] = f"{fips}:{index}"
    unplaced_cities = [f"{fips}:{index}" for fips, index in sorted(unplaced) if fips in governments]
    return {
        "name": state_name(code),
        "page": page_path(code),
        "viewBox": viewbox,
        "counties": found,
        "outline": D._counties(topo, raw_arcs, fit)["outline"],
        "places": towns,
        # No close-ups: they make room for labels, and counties carry none.
        # A county too small to tap is in the list under the map.
        "insets": [],
        "governments": governments,
        "unmatched": unmatched,
        "statewide": statewide,
        # [x, y, kind, name, county fips, "fips:row" of its government or ""]
        "cities": cities,
        # Municipal governments no city point took: "fips:row".
        "unplacedCities": unplaced_cities,
        "sources": {"maps": "U.S. Census Bureau, cartographic boundary file of counties (1:5,000,000)",
                    "places": "U.S. Census Bureau, 2025 cartographic boundary files: places (1:500,000)",
                    "governments": localgov.SOURCE},
    }


def build(root=".", codes=None):
    places = D.load_places(root)
    return {code: build_state(code, root, places) for code in (codes or STATES)}


def stats(maps):
    return {
        "states": len(maps),
        "counties": sum(len(m["counties"]) for m in maps.values()),
        "governments": sum(len(r) for m in maps.values() for r in m["governments"].values()),
        "unmatched": sum(len(u["governments"]) for m in maps.values() for u in m["unmatched"]),
    }
