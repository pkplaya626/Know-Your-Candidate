"""Each state's legislature on a map: its districts, and who sits for them.

The build projects ``legislative_maps/<st>.json`` (Census boundaries, from
``tools/fetch_legislative_maps.py``) the way ``districts`` projects the
congressional maps - the state's own Albers projection, label points at each
district's pole, close-up insets wherever a district is too small to find on
a phone - and attaches the legislators from ``data/state_legislators.json``
(Open States, ``statelegs``), matched to districts by name there.

Nothing about a person is typed here. A district whose seat Open States lists
nobody for is drawn as "nobody listed", never as vacant: Open States may be
behind a special election (rule 19). A legislator who could not be placed on
a district (New Hampshire's floterial seats, Maine's tribal representatives)
is listed on the page, never dropped.
"""

import math
import os

from . import districts as D
from . import geo, statelegs
from .government_maps import LOWER_CHAMBER, SEATS, STATES
from .pages import state_name

FOLDER = "legislature"

# States whose lines changed after the Census captured them (it holds the
# districts set for the 2024 elections), checked on 2026-10-05. A map that
# silently drew the wrong lines would look entirely normal, so the page says
# what it draws and why.
STATE_NOTES = {
    "MI": ("Michigan's Senate districts in the Detroit area were redrawn by court order "
           "(Agee v. Benson, approved July 26, 2024). The new lines take effect with the "
           "November 3, 2026 election; this map shows the districts the sitting senators "
           "were elected in.",
           "https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan"),
    "MS": ("After a court-ordered redraw, Mississippi held special elections in November 2025 "
           "under new lines in Senate districts 1, 2, 11, 19, 34, 41, 42, 44 and 45 and House "
           "districts 16, 22, 36, 39 and 41. In May 2026 the Supreme Court vacated that order, "
           "and which lines apply is unsettled. This map draws those districts as they were "
           "before the redraw.",
           "https://redistricting.lls.edu/states-MS.php"),
}


class LegislatureError(RuntimeError):
    """A state's map or roster is not what the page needs."""


def page_path(code):
    """``legislature/tx.html``."""
    return f"{FOLDER}/{code.lower()}.html"


def chamber_title(code, chamber):
    if code == "NE":
        return "Legislature"
    if chamber == "upper":
        return "Senate"
    return LOWER_CHAMBER.get(code) or "House of Representatives"


def label_text(name):
    """What is written on a district: its number or short code ("12",
    "10A", "B"). A district known by a name ("10th Bristol", "Belknap 1") is
    not written on the map - the name would not fit - and is found by
    pointing at it or in the list."""
    short = name.replace(" ", "")
    return short if len(short) <= 4 and short.isalnum() else ""


def _person(record):
    keep = ("id", "name", "party", "partyKey", "district", "email", "phone", "image",
            "links", "social", "wikidata", "tribalSeat", "unicameral")
    return {k: record[k] for k in keep if k in record}


def build_state(code, root=".", places=None, roster=None):
    """One state's legislature page data."""
    topo = statelegs.load_map(code, root)
    if not topo:
        raise LegislatureError(f"no {statelegs.MAPS_DIR}/{code.lower()}.json; "
                               f"run tools/fetch_legislative_maps.py")
    arcs = geo.decode_arcs(topo)
    objects = topo.get("objects") or {}
    chambers = [c for c in ("upper", "lower") if c in objects]

    shapes, points = {}, {}
    for chamber in chambers:
        shapes[chamber] = {g["properties"]["id"]: g for g in objects[chamber]["geometries"]}
        points[chamber] = {g["properties"]["id"]: g for g in objects[f"{chamber}_pts"]["geometries"]}
        if set(points[chamber]) != set(shapes[chamber]):
            raise LegislatureError(f"{code} {chamber}: label points do not match the districts")

    lonlat = [p for chamber in chambers for g in shapes[chamber].values()
              for ring in geo.geometry_rings(g, arcs) for p in ring]
    albers = D.projection_for(code, lonlat)
    raw_arcs = [[albers.raw(lon, lat) for lon, lat in arc] for arc in arcs]
    raw = {chamber: {i: geo.geometry_rings(g, raw_arcs) for i, g in shapes[chamber].items()}
           for chamber in chambers}
    fit = D._Fit([p for chamber in chambers for rings in raw[chamber].values()
                  for ring in rings for p in ring])
    viewbox = [0, 0, D.WIDTH, fit.height]
    towns = D._places((places or {}).get(code, []), albers, fit)

    people = list(roster or [])
    out_chambers = {}
    for chamber in chambers:
        found = {}
        for district_id, rings in sorted(raw[chamber].items()):
            fitted = [[fit(p) for p in ring] for ring in rings]
            path = geo.rings_to_path(fitted)
            if not path:
                raise LegislatureError(f"{code} {chamber} district {district_id} has no shape")
            props = shapes[chamber][district_id]["properties"]
            at = fit(albers.raw(*D._decode_point(topo, points[chamber][district_id]["coordinates"])))
            if not D._contains(fitted, *at):
                # A label over the wrong district is a silent error.
                raise LegislatureError(f"{code} {chamber} {district_id}: label point outside it")
            found[district_id] = {
                "d": path,
                "name": props["name"],
                "label": label_text(props["name"]),
                "at": [geo._round(at[0]), geo._round(at[1])],
                "box": list(geo.bounds(fitted)),
                "room": geo._round(geo.signed_distance(at[0], at[1], fitted)),
            }
        members = {}
        for record in people:
            if record["chamber"] == chamber and record.get("districtId") in found:
                members.setdefault(record["districtId"], []).append(_person(record))
        for listed in members.values():
            listed.sort(key=lambda p: (p["district"], p["name"]))
        seats = SEATS[code][0 if chamber == "upper" else 1]
        out_chambers[chamber] = {
            "title": chamber_title(code, chamber),
            "seats": seats,
            "listed": sum(1 for r in people if r["chamber"] == chamber and not r.get("tribalSeat")),
            "districts": found,
            "members": members,
            "insets": D.insets([found], towns, viewbox) if len(found) > 1 else [],
            "lsy": (topo.get("sources") or {}).get(chamber, {}).get("lsy", []),
        }

    placed = {r["id"] for c in out_chambers.values() for listed in c["members"].values()
              for r in listed}
    unplaced = [dict(_person(r), chamber=r["chamber"]) for r in people if r["id"] not in placed]
    unplaced.sort(key=lambda p: (p["chamber"], p["district"], p["name"]))
    return {
        "name": state_name(code),
        "page": page_path(code),
        "viewBox": viewbox,
        "unitKm": round(D.EARTH_RADIUS_KM / fit.k, 6),
        "counties": D._counties(topo, raw_arcs, fit),
        "places": towns,
        "chambers": out_chambers,
        "unplaced": unplaced,
        "sources": {"maps": "U.S. Census Bureau, 2025 cartographic boundary files (1:500,000)",
                    "people": statelegs.SOURCE},
    }


def build(root=".", codes=None):
    """``{code: payload}`` for every state with a map and a roster."""
    cache = statelegs.load_cache(root)
    if not cache:
        raise LegislatureError(f"no {statelegs.CACHE_PATH}; run 'statelegs'")
    places = D.load_places(root)
    out = {}
    for code in codes or STATES:
        roster = cache["states"].get(code) or []
        topo = statelegs.load_map(code, root)
        if topo:
            statelegs.match(code, roster, topo)
        out[code] = build_state(code, root, places, roster)
    return out


def stats(maps):
    districts = sum(len(c["districts"]) for m in maps.values() for c in m["chambers"].values())
    people = sum(len(v) for m in maps.values() for c in m["chambers"].values()
                 for v in c["members"].values())
    unplaced = sum(len(m["unplaced"]) for m in maps.values())
    return {"states": len(maps), "districts": districts, "placed": people, "unplaced": unplaced}
