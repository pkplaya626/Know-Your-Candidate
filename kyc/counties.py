"""Each state's counties on a map, and every local government in each.

The county lines come from ``legislative_maps/<st>.json`` (the Census county
file, each county with its GEOID); the governments from
``local_governments/<st>.json`` (the Census Government Units listing,
``localgov``). They are joined on the county's Census code, never its name.

A government whose county code is not on the map - Connecticut's listing
uses the counties the state abolished in 1960, its map the planning regions
that replaced them in Census geography in 2022 - is listed under its county
area's name, never dropped and never moved to a county it is not in.

Cities and towns come from ``local_maps/<st>.json`` (the Census place
boundaries, one point each, ``tools/fetch_local_maps.py``). The listing
carries no usable place code - its FIPS_PLACE for Texarkana, Texas is
68810, the boundary file's 72368 - so a place is joined to its government
by name, within the state, and only where the join is one to one: a name
that one place and one municipal government share, or, where a name is
shared, the one government of that name in the county the place's point
lies in. Anything else is reported and left unjoined (rule 51): the place
is still drawn, the government still listed under its county.
"""

import json
import os
import re
import unicodedata
from collections import defaultdict

from . import districts as D
from . import geo, localgov, statelegs
from .government_maps import STATES
from .pages import state_name

FOLDER = "counties"
CITIES_DIR = "local_maps"

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


<<<<<<< HEAD
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
=======
def load_cities(code, root="."):
    path = os.path.join(root, CITIES_DIR, f"{code.lower()}.json")
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


<<<<<<< HEAD
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
=======
# A government's legal form before its name in the listing ("CITY OF ...")
# and, for a consolidated government's remainder, after it in the boundary
# file ("Nashville-Davidson metropolitan government").
_FORMS = (r"(?:city and county|city and borough|unified government|consolidated government|"
          r"metropolitan government|metro government|metro township|urban county government|"
          r"urban county|city|town|village|borough|municipality|township|corporation|county)")
# The legal forms both sources print, the boundary file after a place's name
# and the listing before a government's: the city and the village of
# Pewaukee, Wisconsin share a name and a county and nothing else.
_SHARED_FORMS = ("city", "town", "village", "borough")


def listing_form(census_name):
    """``"city"`` for the listing's "CITY OF PEWAUKEE", else ``""``."""
    match = re.match(r"^(city|town|village|borough) of ", (census_name or "").lower())
    return match.group(1) if match else ""


def city_key(name, trailing=False):
    """A place's or government's name reduced for comparison: no accents,
    case, legal form, leading "The", alternate name in brackets ("El Paso
    de Robles (Paso Robles)"), punctuation or spaces; Saint, Mount and Fort
    as St, Mt and Ft. With *trailing*, legal forms after the name go too:
    the listing calls Cathedral City "CITY OF CATHEDRAL"."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()
    previous = None
    while previous != s:                 # "TOWN OF CITY OF CREEDE"
        previous = s
        s = re.sub(rf"^(?:the )?{_FORMS} of (?:the )?", "", s).strip()
    s = re.sub(r"^the\s+", "", s)
    if trailing:
        s = re.sub(rf"(?:\s+{_FORMS})+$", "", s)
    s = s.replace("&", " and ")
    s = re.sub(r"\bsaint\b|\bst\b\.?", "st", s)
    s = re.sub(r"\bmount\b|\bmt\b\.?", "mt", s)
    s = re.sub(r"\bfort\b|\bft\b\.?", "ft", s)
    return re.sub(r"[^a-z0-9]", "", s)


def match_cities(places, governments):
    """``{place id: government ref}`` joining *places* ``[(id, key,
    county)]`` to *governments* ``[(ref, key, county)]`` where the join is
    one to one: a key one place and one government share; or, for a key
    shared, the one government of it in the place's county when no other
    place of that key is in the county. Never a nearest or a likeliest."""
    places_by, govs_by = defaultdict(list), defaultdict(list)
    for item in places:
        places_by[item[1]].append(item)
    for item in governments:
        govs_by[item[1]].append(item)
    joined = {}
    for key, mine in places_by.items():
        theirs = govs_by.get(key, [])
        if len(mine) == 1 and len(theirs) == 1:
            joined[mine[0][0]] = theirs[0][0]
            continue
        for pid, _, county in mine:
            here = [g for g in theirs if county and g[2] == county]
            rivals = [p for p in mine if p[2] == county]
            if len(here) == 1 and len(rivals) == 1:
                joined[pid] = here[0][0]
    return joined


def _county_of(point, fitted):
    """The county whose drawn shape holds *point*, else None."""
    x, y = point
    for fips, (rings, box) in fitted.items():
        if box[0] <= x <= box[2] and box[1] <= y <= box[3] and D._contains(rings, x, y):
            return fips
    return None


def build_cities(code, cities, listing, albers, fit, fitted):
    """``(rows, problems)``: every incorporated place the map draws, as
    ``{GEOID: [x, y, kind, name, county, ref]}`` where *ref* is ``[county
    code, index]`` of its government's row in the listing, or None."""
    points, rows = [], {}
    for place in cities["places"]:
        at = fit(albers.raw(*place["point"]))
        if not (0 <= at[0] <= D.WIDTH and 0 <= at[1] <= fit.height):
            raise CountiesError(f"{code}: {place['name']} ({place['id']}) is off the state's map")
        county = _county_of(at, fitted)
        rows[place["id"]] = [geo._round(at[0]), geo._round(at[1]), place["kind"], place["name"],
                             county or "", None]
        points.append((place["id"], city_key(place["name"], place["kind"] == "balance"), county))
    census = {(fips, i): g["census"] for fips, entry in listing["counties"].items()
              for i, g in enumerate(entry["governments"]) if g["type"] == "municipal"}
    governments = [(ref, city_key(name), ref[0]) for ref, name in sorted(census.items())]
    kinds = {pid: rows[pid][2] for pid in rows}
    names = {pid: rows[pid][3] for pid in rows}
    # Three passes, each one to one over what the passes before it left:
    # name and legal form; name; name without the forms after it ("Phenix
    # City" and "CITY OF PHENIX").
    joined = match_cities(
        [(pid, (kinds[pid], key), county) for pid, key, county in points if kinds[pid] in _SHARED_FORMS],
        [(ref, (listing_form(census[ref]), key), county) for ref, key, county in governments
         if listing_form(census[ref])])
    for pass_places, pass_governments in (
            (lambda pid, key: key, lambda ref, key: key),
            (lambda pid, key: city_key(names[pid], True),
             lambda ref, key: city_key(census[ref], True))):
        used = set(joined.values())
        joined.update(match_cities(
            [(pid, pass_places(pid, key), county) for pid, key, county in points if pid not in joined],
            [(ref, pass_governments(ref, key), county) for ref, key, county in governments
             if ref not in used]))
    for pid, (fips, i) in joined.items():
        rows[pid][5] = [fips, i]
    problems = []
    unjoined = sorted(rows[p][3] for p in rows if rows[p][5] is None)
    if unjoined:
        problems.append(f"{code}: {len(unjoined)} place(s) joined to no government in the listing: "
                        + ", ".join(unjoined[:12]) + (" ..." if len(unjoined) > 12 else ""))
    used = set(joined.values())
    left = sorted(listing["counties"][f]["governments"][i]["name"] for (f, i), _, _ in governments
                  if (f, i) not in used)
    if left:
        problems.append(f"{code}: {len(left)} municipal government(s) on no place's point: "
                        + ", ".join(left[:12]) + (" ..." if len(left) > 12 else ""))
    outside = sorted(rows[p][3] for p in rows if not rows[p][4])
    if outside:
        problems.append(f"{code}: {len(outside)} place point(s) outside every drawn county: "
                        + ", ".join(outside[:12]))
    return rows, problems
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd


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

    found, drawn = {}, {}
    for fips, rings in sorted(raw.items()):
        fitted = [[fit(p) for p in ring] for ring in rings]
        drawn[fips] = (fitted, geo.bounds(fitted))
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
<<<<<<< HEAD

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
=======
    cities = load_cities(code, root)
    if not cities:
        raise CountiesError(f"no {CITIES_DIR}/{code.lower()}.json; run tools/fetch_local_maps.py")
    city_rows, city_problems = build_cities(code, cities, listing, albers, fit, drawn)
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
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
<<<<<<< HEAD
        # [x, y, kind, name, county fips, "fips:row" of its government or ""]
        "cities": cities,
        # Municipal governments no city point took: "fips:row".
        "unplacedCities": unplaced_cities,
        "sources": {"maps": "U.S. Census Bureau, cartographic boundary file of counties (1:5,000,000)",
                    "places": "U.S. Census Bureau, 2025 cartographic boundary files: places (1:500,000)",
=======
        "cities": city_rows,
        "problems": city_problems,
        "sources": {"maps": "U.S. Census Bureau, cartographic boundary file of counties (1:5,000,000)",
                    "cities": cities["source"],
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
                    "governments": localgov.SOURCE},
    }


def build(root=".", codes=None, problems=None):
    """Every state's page data. What the city join left undone is no part
    of the page: it is added to *problems* for the build to report."""
    places = D.load_places(root)
    maps = {}
    for code in codes or STATES:
        maps[code] = build_state(code, root, places)
        found = maps[code].pop("problems")
        if problems is not None:
            problems.extend(found)
    return maps


def stats(maps):
    return {
        "states": len(maps),
        "counties": sum(len(m["counties"]) for m in maps.values()),
        "governments": sum(len(r) for m in maps.values() for r in m["governments"].values()),
        "unmatched": sum(len(u["governments"]) for m in maps.values() for u in m["unmatched"]),
        "cities": sum(len(m["cities"]) for m in maps.values()),
        "cities_joined": sum(1 for m in maps.values() for c in m["cities"].values() if c[5]),
    }
