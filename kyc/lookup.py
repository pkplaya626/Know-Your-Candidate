"""Where a ZIP code or a location falls: the data behind "Find who represents me".

A reader types a ZIP code or shares a location, and the page names who
represents them - in the House, the Senate, the state legislature and the
county - and the 2026 race on their ballot. The page does that on the device
(assets/kyc-findrep.js), from one state's file; what the reader typed is
never sent anywhere. This module turns the vendored ``lookup_maps/<st>.json``
(``tools/fetch_lookup_maps.py``) into ``data/lookup/<st>.js``, and writes
``data/lookup/index.js``: which states each ZIP code's first three digits
reach, each state's box, and the versioned address of every file the lookup
loads (rule 76), the state legislature files among them.

Everything here is geography and a pure function of the vendored files; who
holds a seat comes from profiles.js and the legislature files, so a roster
refresh never changes a lookup file.

A ZIP code is not a place. The Census Bureau maps ZIP codes as ZIP Code
Tabulation Areas, from the addresses in each census block; a ZIP used only for
post office boxes has none, and a ZIP can cross any line. So a ZIP's answer
is every district its land touches, with the share in each, and only one
holding WHOLE of it or more is named outright (rule 85).
"""

import json
import os

from . import districts as D
from .pages import state_name

LOOKUP_DIR = "lookup_maps"
# The share of a ZIP area's land in one district that names it outright.
# The page holds the same figure (kyc-findrep.js WHOLE), and tests pin both.
WHOLE = 0.99


# D.C. and the territories have no county page, so their county-equivalents
# are called what the Census Bureau's Geographic Areas Reference Manual calls
# them there (rule 75): Puerto Rico's municipios, American Samoa's three
# districts and two islands, the Northern Mariana Islands' municipalities and
# the Virgin Islands' islands. D.C. and Guam are each one county-equivalent,
# the place itself, so the answer shows no row for it (None).
TERRITORY_AREAS = {"PR": "municipio", "AS": "district or island", "MP": "municipality",
                   "VI": "island", "DC": None, "GU": None}


class LookupMapError(RuntimeError):
    """Raised when a lookup file is missing or disagrees with the maps."""




def source_file(code, root="."):
    return os.path.join(root, LOOKUP_DIR, f"{code.lower()}.json")


def _read(code, root):
    path = source_file(code, root)
    if not os.path.exists(path):
        raise LookupMapError(f"no {path}; run tools/fetch_lookup_maps.py")
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except ValueError as exc:
            raise LookupMapError(f"{path} is not valid JSON: {exc}") from exc


def _object(topo, name):
    obj = (topo.get("objects") or {}).get(name)
    return obj["geometries"] if obj else None


def _flat(arc):
    """``[[x, y], [dx, dy], ...]`` -> ``[x, y, dx, dy, ...]``."""
    return [v for point in arc for v in point]


def build_state(code, root=".", local=None, legislature=None, seats=None):
    """One state's lookup payload.

    *local* is the state's county page data (``counties.build``), whose
    names and words the answer uses; *legislature* its legislature page data,
    whose district ids every ZIP's state districts must be among; *seats* the
    district numbers of the state's maps (``districts.build``), as
    ``[current, next]``. Any disagreement is an error: a ZIP answered with a
    district the pages do not draw is exactly the silent error to refuse.
    """
    topo = _read(code, root)
    transform = topo.get("transform") or {}
    if transform.get("translate") != [0, 0] or len(set(transform.get("scale", []))) != 1:
        raise LookupMapError(f"{source_file(code, root)}: unexpected transform {transform}")
    quantum = transform["scale"][0]

    plans = {"current": _object(topo, "current"), "next": _object(topo, "next")}
    if plans["current"] is None:
        raise LookupMapError(f"{code}: lookup map has no 'current' districts")
    if (plans["next"] is not None) != (code in D.REDRAWN):
        raise LookupMapError(f"{code}: lookup map's 2026 plan does not match districts.REDRAWN")
    numbered = {}
    for key, geoms in plans.items():
        if geoms is None:
            continue
        numbered[key] = {g["properties"]["d"]: g for g in geoms}
        if seats is not None:
            want = set(seats[0 if key == "current" else 1])
            if set(numbered[key]) != want:
                raise LookupMapError(f"{code} {key}: lookup districts {sorted(numbered[key])} "
                                  f"are not the district page's {sorted(want)}")
    counties = {g["properties"]["id"]: g for g in (_object(topo, "counties") or [])}
    if not counties:
        raise LookupMapError(f"{code}: lookup map has no counties")
    names = {geoid: g["properties"]["name"] for geoid, g in counties.items()}
    area, no_county = TERRITORY_AREAS.get(code, "county"), {}
    if local is not None:
        if set(local["counties"]) != set(counties):
            raise LookupMapError(f"{code}: lookup counties and the county page's differ: "
                              f"{sorted(set(counties) ^ set(local['counties']))[:6]}")
        # The county page's own names and words (rule 75).
        names = {geoid: c["name"] for geoid, c in local["counties"].items()}
        area = (local.get("areaWords") or {}).get("one") or area
        no_county = {geoid: n["short"] for geoid, n in (local.get("noCounty") or {}).items()}

    chambers = {}
    if legislature is not None:
        chambers = {"su": set(legislature["chambers"].get("upper", {}).get("districts", {})),
                    "sl": set(legislature["chambers"].get("lower", {}).get("districts", {}))}
    at_large = set(numbered["current"]) == {0}
    zips = topo.get("zips") or {}
    for zcta, entry in zips.items():
        if len(zcta) != 5 or not zcta.isdigit():
            raise LookupMapError(f"{code}: {zcta!r} is not a ZIP code")
        for key, ids in (("cd", numbered["current"]), ("next", numbered.get("next")),
                         ("co", counties), ("su", chambers.get("su")),
                         ("sl", chambers.get("sl"))):
            parts = entry.get(key)
            if parts is None:
                continue
            if ids is None:
                if key in ("su", "sl") and legislature is None:
                    continue            # checked when the legislature is at hand
                raise LookupMapError(f"{code} ZIP {zcta}: {key} shares, and no such map")
            unknown = [p[0] for p in parts if p[0] not in ids]
            if unknown:
                raise LookupMapError(f"{code} ZIP {zcta}: {key} {unknown} not on the map")
            if sum(p[1] for p in parts) > 1.02:
                raise LookupMapError(f"{code} ZIP {zcta}: {key} shares add to more than the whole")
        if "cd" not in entry:
            raise LookupMapError(f"{code} ZIP {zcta}: no congressional district")

    used = set()

    def rings(geometry):
        out = []
        for ring in geometry["arcs"]:
            for a in ring:
                used.add(a if a >= 0 else ~a)
            out.append(ring)
        return out

    payload = {"name": state_name(code), "q": quantum, "atLarge": at_large}
    # A state elected at large is one district: the counties say whether a
    # point is in it, and Alaska's coast is not shipped twice.
    for key, out_key in (("current", "cd"), ("next", "next")):
        if key in numbered and not at_large:
            payload[out_key] = {str(n): rings(g) for n, g in sorted(numbered[key].items())}
    payload["co"] = {geoid: rings(g) for geoid, g in sorted(counties.items())}
    payload["names"] = names
    if area:
        payload["area"] = area
    # D.C. and the territories have no county page to link.
    payload["countyPages"] = local is not None
    if no_county:
        payload["noCounty"] = no_county
    # Only the arcs drawn, renumbered in order.
    order = sorted(used)
    renumber = {old: new for new, old in enumerate(order)}

    def remap(polys):
        return {k: [[renumber[a] if a >= 0 else ~renumber[~a] for a in ring] for ring in rs]
                for k, rs in polys.items()}
    for key in ("cd", "next", "co"):
        if key in payload:
            payload[key] = remap(payload[key])
    arcs = topo["arcs"]
    payload["arcs"] = [_flat(arcs[a]) for a in order]
    payload["box"] = _box([arcs[a] for a in order], quantum)
    payload["zips"] = {z: zips[z] for z in sorted(zips)}
    payload["sources"] = _sources(topo)
    return payload


def _box(arcs, quantum):
    """``[west, south, east, north]`` in degrees, from delta-encoded arcs."""
    xs, ys = [], []
    for arc in arcs:
        x = y = 0
        for i, (dx, dy) in enumerate(arc):
            x, y = (dx, dy) if i == 0 else (x + dx, y + dy)
            xs.append(x)
            ys.append(y)
    return [round(min(xs) * quantum, 4), round(min(ys) * quantum, 4),
            round(max(xs) * quantum, 4), round(max(ys) * quantum, 4)]


def _sources(topo):
    src = topo.get("sources") or {}
    lines = ["ZIP codes: " + src.get("zips", "U.S. Census Bureau relationship files") + "."]
    if src.get("zipNext"):
        check = (topo.get("checks") or {}).get("measured") or {}
        line = ("The 2026 map's shares are " + src["zipNext"] + ".")
        if check:
            line += (f" Measured the same way, the 119th Congress's shares differ from the "
                     f"Census relationship file's by {check['meanDiff'] * 100:.1f} percentage "
                     f"points on average across {check['zips']:,} ZIP areas.")
        lines.append(line)
    if src.get("zipCounties"):
        lines.append("Counties by ZIP are " + src["zipCounties"] + ".")
    lines.append("A location is placed on: " + src.get("current", "") + "; " +
                 src.get("counties", "") +
                 (("; the 2026 map, " + src["next"]) if src.get("next") else "") + ".")
    return [line.replace("..", ".") for line in lines]


def build(root=".", codes=None, local=None, legislatures=None, district_maps=None):
    """``{code: payload}`` for every state, D.C. and territory."""
    out = {}
    for code in codes or D.all_codes():
        seats = None
        if district_maps and code in district_maps:
            plans = district_maps[code]["plans"]
            seats = [[int(n) for n in p["districts"]] for p in plans]
            if len(seats) == 1:
                seats.append([])
        out[code] = build_state(code, root, (local or {}).get(code),
                                (legislatures or {}).get(code), seats)
    return out


def place_info(codes, voting=None):
    """``{code: {name, map?, check?}}``: what the answer says of each state
    on any page, profiles.js loaded or not - the legislature and county
    pages load none (PR #104 review): its name, its district map page
    (``districts.index``) and its own lookup page from *voting*
    (``voting.for_page``), the one "Check with Ohio's own lookup" links."""
    maps = D.index()
    out = {}
    for code in sorted(codes):
        entry = {"name": state_name(code)}
        if code in maps:
            entry["map"] = {"page": maps[code]["page"], "redrawn": bool(maps[code]["redrawn"])}
        links = (voting or {}).get(code) or {}
        check = links.get("status") or links.get("polling")
        if check:
            entry["check"] = check
        out[code] = entry
    return out


def index(payloads, stamps, voting=None):
    """``data/lookup/index.js``'s payload: which states each ZIP's first
    three digits reach, each state's box and words (``place_info``), and
    the versioned path of each file the lookup loads. *stamps* is ``{code:
    {"lookup": path, "legislature": path}}``, paths relative to the site's
    root; *voting* is ``voting.for_page``'s."""
    zip3 = {}
    for code, payload in sorted(payloads.items()):
        for zcta in payload["zips"]:
            states = zip3.setdefault(zcta[:3], [])
            if code not in states:
                states.append(code)
    return {"whole": WHOLE,
            "zip3": {k: zip3[k] for k in sorted(zip3)},
            "boxes": {code: p["box"] for code, p in sorted(payloads.items())},
            "states": place_info(payloads, voting),
            "files": {code: stamps[code] for code in sorted(stamps)}}


def stats(payloads):
    return {"lookup_states": len(payloads),
            "lookup_zips": len({z for p in payloads.values() for z in p["zips"]})}
