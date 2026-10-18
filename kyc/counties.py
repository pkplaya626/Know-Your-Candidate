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

Towns and townships - county subdivisions that govern, in twenty states -
are joined the other way round, on the Census code the listing gives them
(``cousub``), which is the subdivision's own: 16,167 of 16,214 in 2022. The
name is a cross-check, never the join: a code whose names disagree is
reported and not drawn, and a government whose code is on no subdivision is
never placed by its name (rule 60). Only subdivisions joined to a township
government are drawn.
"""

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

from . import county_areas
from . import districts as D
from . import geo, localgov, localsites, statelegs
from .government_maps import STATES
from .pages import state_name

FOLDER = "counties"
CITIES_DIR = "local_maps"

# Compact rows for the page: [type, name, city, web, size, function, flags,
# site, listed]. *site* is what the website check found ("ok 2026-10-17",
# "unread 2026-10-17", or a withdrawal - "dead 2026-10-17" with *web*
# empty - kyc/localsites.py), "" when never checked; *listed* the
# listing's own abbreviated name where the page writes it out.
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


# The Census's function codes that read as its own filing categories,
# in plain words (the rest - "Local Fire Protection", "Libraries" - read
# as they are).
FUNCTIONS = {
    "Other Single Function Districts": "Single-purpose district",
    "Other Multi-Function Districts": "Multi-purpose district",
    "Miscellaneous Commercial Activities": "Commercial activities",
    "Other Natural Resources": "Natural resources",
    "Other Public Welfare": "Public welfare",
    "Other Corrections": "Corrections",
    "Water Supply Utility": "Water supply",
    "Public Mass Transit Utility": "Public transit",
    "Electric Power Utility": "Electric power",
    "Gas Supply Utility": "Gas supply",
}


def _row(gov, sites=None):
    size = gov.get("population", gov.get("enrollment"))
    web, site = localsites.status(web_address(gov.get("web", "")), sites)
    function = gov.get("function", "")
    return [gov["type"], gov["name"], gov.get("city", ""), web,
            size if size is not None else "", FUNCTIONS.get(function, function),
            "inactive" if gov.get("inactive") else "", site, ""]


def _for_reading(rows):
    """Each row's name with the listing's abbreviations written out, the
    listing's form kept beside it. Done last: every join and check reads
    the listing's own names."""
    for row in rows:
        written = localgov.expand_name(row[1])
        if written != row[1]:
            row[1], row[8] = written, row[1]
    return rows


# A map label's size on screen, in pixels: 11px text on a backing
# (kyc-regionmap.js, .map-label). LABEL_CHAR_PX is the measured average
# advance of a county name's letters at 11px, LABEL_PAD_PX the backing's
# padding either side, LABEL_HEIGHT_PX the backing's height.
LABEL_CHAR_PX = 7.4
LABEL_PAD_PX = 2.5
LABEL_HEIGHT_PX = 14
_AREA_SUFFIX = re.compile(r"\s+(?:County|Parish|Borough|Census Area|City and Borough|Municipality|"
                          r"Planning Region)$")


def map_label(name):
    """A county's name on the map: "Milwaukee", not "Milwaukee County"."""
    return _AREA_SUFFIX.sub("", name) or name


def label_aspect(label):
    """How many times wider than tall a label's backing is."""
    return (len(label) * LABEL_CHAR_PX + 2 * LABEL_PAD_PX) / LABEL_HEIGHT_PX


def load_cities(code, root="."):
    path = os.path.join(root, CITIES_DIR, f"{code.lower()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# A government's legal form before its name in the listing ("CITY OF ...")
# and, for a consolidated government's remainder, after it in the boundary
# file ("Nashville-Davidson metropolitan government").
_FORMS = (r"(?:city and county|city and borough|city-parish|unified government|consolidated government|"
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


# The forms a town or township's name carries, in the listing ("CHARTER
# TOWNSHIP OF ORION", "PLANTATION OF THE FORKS") or after it in the boundary
# file ("Orion charter township"; New Jersey's "City of Orange township" is
# the listing's "TOWNSHIP OF ORANGE CITY"). Kept apart from _FORMS: a city
# may be named Grant or Location, and a township's name is only ever a
# cross-check of two names that already share a code.
_TOWN_FORMS = (r"(?:charter township|civil township|metro township|township|town|plantation|"
               r"gore|grant|location|purchase|city|village|borough)")


def city_key(name, trailing=False, forms=_FORMS):
    """A place's or government's name reduced for comparison: no accents,
    case, legal form, leading "The", alternate name in brackets ("El Paso
    de Robles (Paso Robles)"), punctuation or spaces; Saint, Ste., Mount and
    Fort as St, St, Mt and Ft. With *trailing*, legal forms after the name go too:
    the listing calls Cathedral City "CITY OF CATHEDRAL"."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()
    previous = None
    while previous != s:                 # "TOWN OF CITY OF CREEDE"
        previous = s
        s = re.sub(rf"^(?:the )?{forms} of (?:the )?", "", s).strip()
    s = re.sub(r"^the\s+", "", s)
    if trailing:
        s = re.sub(rf"(?:\s+{forms})+$", "", s)
    s = s.replace("&", " and ")
    s = re.sub(r"\bsaint\b|\bste?\b\.?", "st", s)
    s = re.sub(r"\bmount\b|\bmt\b\.?", "mt", s)
    s = re.sub(r"\bfort\b|\bft\b\.?", "ft", s)
    return re.sub(r"[^a-z0-9]", "", s)


def town_key(name):
    """A town or township's name reduced for the cross-check: as city_key,
    with the township forms, and a numbered township ("Township 3", the
    listing's "TOWNSHIP OF NUMBER 3") reduced to its number."""
    s = city_key(name, True, _TOWN_FORMS)
    s = re.sub(r"^(?:township|town)(?=\d+$)", "", s)
    return re.sub(r"^(?:number|no)(?=\d+$)", "", s)


def same_town(listed, drawn):
    """Whether the listing's name and the boundary file's name for one
    Census code name the same town: equal once reduced, or one the start of
    the other ("CENTER" and "Center-District 1"; "SULLIVAN" and Sullivant,
    as the Census spells it). Only ever asked of two names that already
    share a code."""
    a, b = town_key(listed), town_key(drawn)
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 4 and long_.startswith(short)


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
    """``(rows, problems, consolidated)``: every incorporated place the map draws, as
    ``{GEOID: [x, y, kind, name, county, ref, status]}`` where *ref* is
    ``[county code, index]`` of its government's row in the listing, or None,
    and *status* the Census's functional status where it is not "A".

    A place's county is the one the tool found at 1:500,000; only where that
    is not a drawn county is the point tested against the drawn 1:5,000,000
    lines, which put four small boroughs and cities on county lines in the
    county next door."""
    points, rows = [], {}
    for place in cities["places"]:
        at = fit(albers.raw(*place["point"]))
        if not (0 <= at[0] <= D.WIDTH and 0 <= at[1] <= fit.height):
            raise CountiesError(f"{code}: {place['name']} ({place['id']}) is off the state's map")
        county = place.get("county") if place.get("county") in fitted else _county_of(at, fitted)
        rows[place["id"]] = [geo._round(at[0]), geo._round(at[1]), place["kind"], place["name"],
                             county or "", None, place.get("status", "")]
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
    consolidated = {}
    curated, problems = curated_joins(code, rows, listing, joined)
    for pid, (ref, how) in curated.items():
        joined[pid] = ref
        if how == "consolidated":
            consolidated[pid] = ref[0]
    for pid, (fips, i) in joined.items():
        rows[pid][5] = [fips, i]
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
    return rows, problems, consolidated


def curated_joins(code, rows, listing, joined):
    """``({place id: ((county, index), how)}, problems)``: the joins no name
    can make, each with its evidence. *how* is "consolidated" for a city a
    consolidated government in county_areas.AREAS governs (its row is the
    one AREAS names in that area), else "listed" for an entry of
    overrides.PLACE_GOVERNMENTS (its row found by the listing's own id).
    An entry whose row is missing, named otherwise, in another county or
    already joined is refused and reported; one the join no longer needs
    is reported too (a stale override is invisible and quietly wrong)."""
    from . import overrides

    by_id = {g["id"]: ((fips, i), g) for fips, entry in listing["counties"].items()
             for i, g in enumerate(entry["governments"])}
    wanted = {}
    for pid, area in county_areas.CONSOLIDATED_PLACES.items():
        if pid in rows:
            name = county_areas.AREAS[area][2]
            found = [((area, i), g) for i, g in enumerate(
                (listing["counties"].get(area) or {}).get("governments", [])) if g["name"] == name]
            wanted[pid] = (found[0] if len(found) == 1 else None, name, "consolidated")
    for pid, (gid, name, _why) in overrides.PLACE_GOVERNMENTS.items():
        if pid in rows:
            wanted[pid] = (by_id.get(gid), name, "listed")
    used = set(joined.values())
    out, problems = {}, []
    for pid, (hit, name, how) in sorted(wanted.items()):
        place = rows[pid][3]
        if pid in joined:
            problems.append(f"{code}: {place} ({pid}) is joined by name now; its curated join "
                            f"to {name} is no longer needed")
            continue
        if hit is None or hit[1]["name"] != name:
            problems.append(f"{code}: {place} ({pid}): the listing holds no {name!r} where the "
                            f"curated join says; not joined")
            continue
        ref, gov = hit
        if ref[0] != rows[pid][4]:
            problems.append(f"{code}: {place} ({pid}) is in {rows[pid][4]}, {name} under {ref[0]}; "
                            f"not joined")
            continue
        if ref in used or gov["type"] not in ("municipal", "township", "county"):
            problems.append(f"{code}: {place} ({pid}): {name} is joined elsewhere or is not a "
                            f"general government; not joined")
            continue
        used.add(ref)
        out[pid] = (ref, how)
    return out, problems


# The functional statuses of a subdivision that governs (census.gov
# functional status codes): active (A), partially consolidated (B),
# consolidated (C), subordinate (G), inactive (I). A subdivision the Census
# calls statistical (S), fictitious (F) or nonfunctioning (N) is not a
# government's, whatever the listing says: Mitchell, South Dakota is
# unorganized territory in every Gazetteer since 2015.
GOVERNING = {"A", "B", "C", "G", "I"}


def build_towns(code, cities, listing, albers, fit, drawn, on_places=frozenset()):
    """``(rows, problems)``: every county subdivision joined to a town or
    township government, as ``{GEOID: [x, y, kind, name, county, ref,
    status]}``, joined on the listing's own code for it, cross-checked by
    name and by the subdivision's own functional status."""
    subdivisions = {s["id"]: s for s in cities.get("subdivisions") or []}
    by_code = defaultdict(list)
    for sub in subdivisions.values():
        by_code[sub["code"]].append(sub)
    claims = defaultdict(list)
    unplaced, disputed, misfiled, idle = [], [], [], []
    for fips, entry in sorted(listing["counties"].items()):
        for i, gov in enumerate(entry["governments"]):
            if gov["type"] != "township":
                continue
            sub = subdivisions.get(fips + gov["cousub"]) if gov.get("cousub") else None
            if not sub and (fips, i) in on_places:
                continue                 # on a place's point (overrides.PLACE_GOVERNMENTS)
            if not sub:
                # The code may be in another county: the listing files the
                # Town of Pomfret under the wrong Connecticut planning region.
                elsewhere = [s for s in by_code.get(gov.get("cousub"), [])
                             if same_town(gov["census"], s["name"])]
                if len(elsewhere) == 1:
                    misfiled.append(f"{gov['name']} (listed under {fips}, its subdivision is in "
                                    f"{elsewhere[0]['county']})")
                else:
                    unplaced.append(gov["name"])
            elif not same_town(gov["census"], sub["name"]):
                disputed.append(f"{gov['name']} (code {sub['code']} is {sub['name']} {sub['kind']})")
            elif sub.get("status", "A") not in GOVERNING:
                idle.append(f"{gov['name']} ({sub['name']}: status {sub['status']})")
            else:
                claims[sub["id"]].append((fips, i))
    rows, problems = {}, []
    shared = sorted(sid for sid, refs in claims.items() if len(refs) > 1)
    for sid, refs in sorted(claims.items()):
        if len(refs) > 1:
            continue                     # two governments on one code: neither is placed
        sub = subdivisions[sid]
        at = fit(albers.raw(*sub["point"]))
        if not (0 <= at[0] <= D.WIDTH and 0 <= at[1] <= fit.height):
            raise CountiesError(f"{code}: {sub['name']} ({sid}) is off the state's map")
        county = sub["county"] if sub["county"] in drawn else (_county_of(at, drawn) or "")
        rows[sid] = [geo._round(at[0]), geo._round(at[1]), sub["kind"], sub["name"], county,
                     list(refs[0]), sub.get("status", "")]
    if unplaced:
        problems.append(f"{code}: {len(unplaced)} town or township government(s) with no county "
                        f"subdivision of their code: " + ", ".join(sorted(unplaced)[:12]) +
                        (" ..." if len(unplaced) > 12 else ""))
    if disputed:
        problems.append(f"{code}: {len(disputed)} town or township code(s) whose names disagree, "
                        f"not placed: " + "; ".join(sorted(disputed)[:12]))
    if misfiled:
        problems.append(f"{code}: {len(misfiled)} town or township government(s) listed under another "
                        f"county than their subdivision, not placed: " + "; ".join(sorted(misfiled)[:12]))
    if idle:
        problems.append(f"{code}: {len(idle)} town or township government(s) on a subdivision the "
                        f"Census records as not governing, not placed: " + "; ".join(sorted(idle)[:12]))
    if shared:
        problems.append(f"{code}: {len(shared)} county subdivision(s) claimed by two governments, "
                        f"not placed: " + ", ".join(subdivisions[s]["name"] for s in shared[:12]))
    return rows, problems


def build_state(code, root=".", places=None, sites=None):
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

    if sites is None:
        sites = localsites.load_cache(root)
    governments, unmatched = {}, []
    for fips, entry in sorted(listing["counties"].items()):
        rows = [_row(g, sites) for g in entry["governments"]]
        if fips in found:
            governments[fips] = rows
        else:
            unmatched.append({"name": entry["name"], "fips": fips, "governments": rows})
    statewide = [_row(g, sites) for g in listing.get("statewide", [])]
    # A county area with no county government says why, from the Census
    # Bureau's own list of them; one it cannot explain fails the build.
    lacking = county_areas.check(code, found, governments)
    if lacking:
        raise CountiesError("; ".join(lacking))
    # Checked against the Census's names; shown in the state's own words
    # ("City of Alexandria", not "Alexandria city"), and labelled on the map
    # where the name fits (rule 43): written 11px tall at whatever width the
    # page draws, the label goes in where a box its shape fits round its
    # point, and the list under the map names every one.
    for fips, county in found.items():
        county["name"] = county_areas.local_name(fips, county["name"])
        county["label"] = map_label(county["name"])
        county["labelRoom"] = geo._round(geo.box_room(
            county["at"][0], county["at"][1], drawn[fips][0], label_aspect(county["label"])))
    cities = load_cities(code, root)
    if not cities:
        raise CountiesError(f"no {CITIES_DIR}/{code.lower()}.json; run tools/fetch_local_maps.py")
    city_rows, city_problems, consolidated = build_cities(code, cities, listing, albers, fit, drawn)
    town_rows, town_problems = build_towns(code, cities, listing, albers, fit, drawn,
                                           {tuple(r[5]) for r in city_rows.values() if r[5]})
    # One government, one mark: a row a place is joined to (by name or a
    # curated join) and a ring both claim would show it twice.
    refs = Counter(tuple(r[5]) for r in list(city_rows.values()) + list(town_rows.values()) if r[5])
    twice = sorted(r for r, n in refs.items() if n > 1)
    if twice:
        raise CountiesError(f"{code}: government rows joined twice: {twice[:6]}")
    for rows in list(governments.values()) + [u["governments"] for u in unmatched] + [statewide]:
        _for_reading(rows)
    return {
        "name": state_name(code),
        "page": page_path(code),
        "viewBox": viewbox,
        "counties": found,
        "outline": D._counties(topo, raw_arcs, fit)["outline"],
        "places": towns,
        # No close-ups: 254 Texas names will not fit at 11px on a phone
        # (rule 43), so a county without room for its name is named in the
        # list under the map, which a filter searches, and on hover.
        "insets": [],
        "governments": governments,
        **county_areas.for_state(code, found, governments),
        "unmatched": unmatched,
        "statewide": statewide,
        "cities": city_rows,
        # {place id: county area}: a city whose government is the
        # consolidated one that also does the county's work.
        "consolidatedPlaces": consolidated,
        "towns": town_rows,
        "problems": city_problems + town_problems,
        "sources": {"maps": "U.S. Census Bureau, cartographic boundary file of counties (1:5,000,000)",
                    "cities": cities["source"],
                    "towns": cities.get("subdivisionSource", ""),
                    "governments": localgov.SOURCE},
    }


def build(root=".", codes=None, problems=None):
    """Every state's page data. What the city join left undone is no part
    of the page: it is added to *problems* for the build to report."""
    places = D.load_places(root)
    sites = localsites.load_cache(root)
    maps = {}
    for code in codes or STATES:
        maps[code] = build_state(code, root, places, sites)
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
        "towns": sum(len(m["towns"]) for m in maps.values()),
    }
