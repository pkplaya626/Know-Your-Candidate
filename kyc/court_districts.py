"""Which federal district court - and which of its divisions - covers each
county, from the statute that draws them: 28 U.S.C. 81-131.

``tools/fetch_court_districts.py`` reads chapter 5 of title 28 as govinfo
publishes the United States Code and writes, for each state, the statute's
own words reduced to lists (``data/court_districts.json``): each district,
its divisions, the counties (parishes, cities) each comprises and the
places court is held. Nothing is typed in from memory, and nothing is
taken from a court's website.

The build joins those names to the Census Bureau's counties
(``legislative_maps/<st>.json``) by name within the state - never across
one - and fails on any county of a state with more than one district that
the statute does not place, or places twice (rule 49: a map of every
county is a claim about every county). Where the Code's text and the
Census name differ - a spelling the Code keeps from 1948 ("Accomac"), a
typo in the Code ("Brisco") - the difference is an entry in ``ALIASES``
with what was checked. Virginia's independent cities are not named by the
statute: section 127(c) puts a city in the district of the counties it lies
within or was incorporated from, and the build places one only where every
county or already-placed city it borders is in one district; any other is
reported, never guessed (rule 51).

A county the statute splits (part of Durham County, North Carolina, is in
the Eastern District, for the Federal Correctional Institution at Butner)
is placed by the statute's main rule and carries the exception in the
statute's words.
"""

import html
import json
import os
import re
import unicodedata

SOURCE_URL = ("https://www.govinfo.gov/content/pkg/USCODE-2024-title28/html/"
              "USCODE-2024-title28-partI-chap5.htm")
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "court_districts.json")

DIRECTIONS = {"Northern": "n", "Southern": "s", "Eastern": "e", "Western": "w", "Middle": "m",
              "Central": "c"}

# The Code's name for a county -> the Census Bureau's, by state; each read
# against the Census county list on 2026-10-17. A list value is a Code
# entry that names two counties (a missing comma).
ALIASES = {
    # Spellings the Code keeps from 1948, or misspells, against the Census
    # Bureau's name of the same county (the only county of either spelling
    # in that state).
    "AR": {"hot springs": "hot spring"},
    "FL": {"dade": "miami dade"},           # renamed Miami-Dade in 1997
    "IN": {"vermilion": "vermillion", "davies": "daviess"},
    "KY": {"breckenridge": "breckinridge"},
    "MO": {"saint genevieve": "ste genevieve"},
    "OH": {"woods": "wood"},
    # Shannon County became Oglala Lakota County in 2015 (Census FIPS 46102).
    "SD": {"edmonds": "edmunds", "shannon": "oglala lakota"},
    "TX": {"brisco": "briscoe", "shackleford": "shackelford", "cook": "cooke",
           "zavalla": "zavala"},
    "VA": {"accomac": "accomack"},
    "OK": {"le flore love": ["le flore", "love"]},  # 28 U.S.C. 116(b): a missing comma
}

# Counties the Code still names that no longer exist, each merged into an
# independent city that the Census lists (Virginia's consolidations of
# 1952-1975). The city takes the county's district (28 U.S.C. 127(c): a
# city is in the district of the territory it was incorporated from).
FORMER_COUNTIES = {
    "VA": {"elizabeth city": "hampton city", "nansemond": "suffolk city",
           "norfolk": "chesapeake city", "princess anne": "virginia beach city",
           "warwick": "newport news city"},
}


# Amendments enacted after the edition SOURCE_URL publishes, applied on top
# of it: (state, district, division or None) -> where court is held, in the
# amended words. Every section 81-131 was read in Cornell LII's current
# text on 2026-10-17 for a Public Law later than the edition's; sections 84
# and 124 had one (Pub. L. 119-109, Sept. 16, 2026, 140 Stat. 1022). Neither
# moved a county.
AMENDMENTS = {
    # Sec. 3 inserted "and El Centro" after "at San Diego" in 28 U.S.C. 84(d).
    ("CA", "Southern", None): "San Diego and El Centro",
    # Inserted "and College Station" after "held at Houston" in 124(b)(2).
    ("TX", "Southern", "Houston"): "Houston and College Station",
}


class CourtDistrictsError(RuntimeError):
    """The statute's text is not what the parser knows."""


# ------------------------------------------------------------ the statute

def statute_text(page):
    """The chapter's HTML as plain lines."""
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page)).replace("\xa0", " ")
    return re.sub(r"\n\s*\n+", "\n", text)


def sections(text):
    """``{state name: body}`` for sections 81-131, each body ending before
    its source credit, notes and amendments."""
    out = {}
    # "§81A. Alaska": a section added between two others carries a letter.
    heads = list(re.finditer(r"^§(\d+)[A-Z]?\. (.+)$", text, re.M))
    for i, head in enumerate(heads):
        number = int(head.group(1))
        if not 81 <= number <= 131:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[head.end():end]
        # The source credit: "(June 25, 1948, ...)" for a section of the
        # 1948 Code, "(Added Pub. L. ...)" for one added since (Alaska's and
        # North Dakota's), whose notes otherwise ran into where court is held.
        cut = re.search(r"^\((?:Added\b|(?:June|July|Aug|Sept|Oct|Nov|Dec|Jan|Feb|Mar|Apr|May)"
                        r"\w*\.? \d)", body, re.M)
        out[head.group(2).strip()] = (number, body[:cut.start()] if cut else body)
    return out


def _flat(body):
    """One line, without the footnote numbers the HTML sets on their own
    lines ("Plattsburgh,\\n1\\n Syracuse")."""
    lines = [l.strip() for l in body.split("\n")]
    return " ".join(l for l in lines if l and not re.fullmatch(r"\d{1,2}", l))


_LIST_OF = r"(?:the )?(?:[Cc]ounties|[Cc]ounty|[Pp]arishes|[Pp]arish) of "


def names(listed):
    """``"Colbert, Franklin, and Lauderdale"`` -> the three names; the
    statute's own words in a parenthesis (an exception) are kept apart."""
    exceptions = re.findall(r"\(([^)]*)\)", listed)
    plain = re.sub(r"\s*\([^)]*\)", "", listed)
    # "A, B, and C": the "and" goes; "King and Queen" is one county, and
    # "Riverside and San Bernardino" two - which, the join decides.
    out = [re.sub(r"^and\s+", "", n.strip()) for n in plain.split(",") if n.strip()]
    return out, exceptions


def _places(units):
    """``(counties, cities, exceptions, portions)`` of a "comprises ..."
    clause: "the counties of A, B and C, and the city of D"."""
    units = re.sub(r"\s+and concurrently with .*$", "", units)
    # "those portions of Hoke, Moore ... counties encompassing Fort Bragg":
    # part of a county another district holds; that county's own entry
    # carries the exception in the statute's words, and this district's
    # words say where the part is.
    portion = re.search(r",?\s+(?:and )?((?:those|that) portions? of [^()]*)$", units)
    portions = [portion.group(1).strip()] if portion else []
    if portion:
        units = units[:portion.start()]
    city = re.search(r",?\s+and the [Cc]ity of (.+)$", units)
    cities = []
    if city:
        cities = [city.group(1).strip()]
        units = units[:city.start()]
    units = re.sub(r"^" + _LIST_OF, "", units.strip())
    single = re.fullmatch(r"([A-Z][\w .'-]+?) County", units.strip())
    if single:
        return [single.group(1)], cities, [], portions
    counties, exceptions = names(units)
    return counties, cities, exceptions, portions


_NEXT = (r"(?= Court (?:for|shall)\b| \(\w+\) | (?:Northern|Southern|Eastern|Western|Middle|"
         r"Central) District | The |$)")
_COMPRISES = re.compile(r"The ([A-Za-z][\w .'-]*?) ([Dd]istrict|[Dd]ivision) comprises (.+?)\." + _NEXT)
_DIVISIONS = re.compile(r"^(?:\w+|\d+) divisions?$")
_HELD = re.compile(r"Court (?:for the ([A-Za-z][\w .'-]*?) ([Dd]istrict|[Dd]ivision) )?shall be "
                   r"held at (.+?)\." + _NEXT)


def _title(name):
    return " ".join(w[:1].upper() + w[1:] for w in name.split())


def _unit(name=None):
    return {"name": name, "divisions": [], "counties": [], "cities": [], "exceptions": [],
            "portions": [], "held": ""}


def parse_state(body):
    """``{"single": bool, "districts": [{"name", "divisions": [...],
    "counties", "cities", "exceptions", "held"}]}`` from one section, read
    in the statute's order: a "Court ... shall be held" sentence belongs to
    the district or division it names, the last one named before it (two
    districts can each have a "Northern Division")."""
    flat = _flat(body)
    single = bool(re.search(r"constitutes? one judicial district", flat))
    events = sorted([(m.start(), "comprises", m) for m in _COMPRISES.finditer(flat)] +
                    [(m.start(), "held", m) for m in _HELD.finditer(flat)], key=lambda e: e[0])
    districts, current, last = [], None, {}
    for _at, kind, match in events:
        if kind == "comprises":
            name, level, what = match.groups()
            name, level = _title(name), level.lower()
            if level == "district":
                current = _unit(name)
                districts.append(current)
                last[("district", name)] = current
                if not _DIVISIONS.match(what):
                    (current["counties"], current["cities"], current["exceptions"],
                     current["portions"]) = _places(what)
            else:
                if current is None:
                    current = _unit()
                    districts.append(current)
                division = _unit(name)
                del division["divisions"]
                (division["counties"], division["cities"], division["exceptions"],
                 division["portions"]) = _places(what)
                current["divisions"].append(division)
                last[("division", name)] = division
        else:
            name, level, where = match.groups()
            if name is None:
                if current is None:
                    current = _unit()
                    districts.append(current)
                target = current
            else:
                target = last.get((level.lower(), _title(name)))
            if target is not None and not target["held"]:
                target["held"] = _held(where)
    if single and not districts:
        districts.append(_unit())
    return {"single": single, "districts": districts}


def _held(where):
    """Where court is held, in the statute's own words (one string: some
    name "a suitable site" rather than a city, so it is never split)."""
    return re.sub(r"\s+", " ", where).strip().rstrip(".")


def parse(page):
    """``{state code: parsed}`` from the chapter's HTML."""
    from .normalize import US_STATES

    codes = {k.title(): v for k, v in US_STATES.items()}
    codes["District Of Columbia"] = "DC"
    out = {}
    for name, (number, body) in sections(statute_text(page)).items():
        code = codes.get(name.title())
        if code is None:
            raise CourtDistrictsError(f"28 U.S.C. {number} names a place the table does not know: {name}")
        out[code] = dict(parse_state(body), section=number)
        for district in out[code]["districts"]:
            for unit, division in [(district, None)] + [(d, d["name"]) for d in district["divisions"]]:
                amended = AMENDMENTS.get((code, district["name"], division))
                if amended:
                    unit["held"] = amended
    # The fifty states, the District of Columbia and Puerto Rico.
    if len(out) != 52:
        raise CourtDistrictsError(f"read {len(out)} sections of 28 U.S.C. 81-131, not 52")
    return out


# --------------------------------------------------------- the join

def fold(name):
    """A county name for comparison: no accents, case, punctuation, county
    word or spaces; "Saint" as "St"."""
    plain = unicodedata.normalize("NFKD", name or "")
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    plain = re.sub(r"\b(county|parish|borough|census area|municipality|municipio)\b", " ", plain)
    plain = re.sub(r"\bsaint\b", "st", plain)
    return re.sub(r"[^a-z]", "", plain)


def court_id(code, district):
    """This site's court id for a state's district ("Southern" in Texas ->
    ``tx-s``; a state's only district -> ``tx``)."""
    if district is None:
        return code.lower()
    return f"{code.lower()}-{DIRECTIONS[district]}"


def census_counties(code, root="."):
    """``{fips: name}`` for a state's counties and county equivalents, from
    the Census boundaries the county pages draw (legislative_maps)."""
    path = os.path.join(root, "legislative_maps", f"{code.lower()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        layer = json.load(handle)["objects"].get("counties") or {}
    return {g["properties"]["id"]: g["properties"]["name"] for g in layer.get("geometries") or []}


def _wanted(code, name):
    """The Census names (folded) a statute name stands for."""
    key = name.lower().strip()
    alias = ALIASES.get(code, {}).get(key)
    if alias is not None:
        return [fold(a) for a in (alias if isinstance(alias, list) else [alias])]
    former = FORMER_COUNTIES.get(code, {}).get(key)
    if former is not None:
        return ["city:" + fold(former.replace(" city", ""))]
    return [fold(name)]


def join(code, parsed, counties, neighbours=None):
    """``({fips: {"court", "division", "held", "except"}}, problems)``: each
    Census county placed where the statute puts it. A name that matches no
    county, or a county two entries claim, is a problem; so, in a state of
    several districts, is a county nobody places."""
    by_fold, problems = {}, []
    for fips, name in counties.items():
        city = name.lower().endswith(" city") and code in ("VA", "MO", "MD", "NV")
        key = ("city:" if city else "") + fold(re.sub(r"(?i)\s+city$", "", name) if city else name)
        by_fold.setdefault(key, []).append(fips)
    out = {}

    def place(names, cities, cid, division, held, exceptions):
        for name in names:
            keys = _wanted(code, name)
            if " and " in name and not any(by_fold.get(k) for k in keys):
                # "Riverside and San Bernardino": two counties, where no
                # county bears the whole phrase ("King and Queen" does).
                place(name.split(" and "), [], cid, division, held, exceptions)
                continue
            for key in keys:
                hits = by_fold.get(key) or []
                if len(hits) != 1:
                    problems.append(f"{code}: 28 U.S.C. names {name!r} ({cid}); the Census "
                                    f"lists {len(hits)} counties of that name")
                    continue
                fips = hits[0]
                if fips in out:
                    problems.append(f"{code}: {counties[fips]} is placed twice "
                                    f"({out[fips]['court']} and {cid})")
                    continue
                note = [e for e in exceptions if fold(name) in fold(e)]
                out[fips] = {"court": cid, "division": division, "held": held,
                             **({"except": note[0]} if note else {})}
        for name in cities:
            hits = by_fold.get("city:" + fold(name)) or []
            if len(hits) != 1:
                problems.append(f"{code}: 28 U.S.C. names the city of {name!r}; the Census "
                                f"lists {len(hits)}")
                continue
            out[hits[0]] = {"court": cid, "division": division, "held": held}

    for district in parsed["districts"]:
        cid = court_id(code, None if parsed["single"] else district["name"])
        place(district["counties"], district["cities"], cid, None, district["held"],
              district["exceptions"])
        for division in district["divisions"]:
            place(division["counties"], division["cities"], cid, division["name"],
                  division["held"] or district["held"], division["exceptions"])
    # Where an excepted part goes: the one other district whose own words
    # ("that portion of Durham County encompassing ...") name the county.
    holders = {}
    for district in parsed["districts"]:
        cid = court_id(code, None if parsed["single"] else district["name"])
        for unit in [district] + district["divisions"]:
            for words in unit.get("portions") or []:
                holders.setdefault(cid, []).append(fold(words))
    for fips, entry in out.items():
        if not entry.get("except"):
            continue
        county = fold(counties[fips])
        to = [cid for cid, texts in holders.items()
              if cid != entry["court"] and any(county in t for t in texts)]
        if len(to) == 1:
            entry["exceptTo"] = to[0]
        else:
            problems.append(f"{code}: 28 U.S.C. keeps part of {counties[fips]} out of {entry['court']} "
                            f"and names {len(to)} other districts for it")
    if parsed["single"]:
        cid = code.lower()
        held = parsed["districts"][0]["held"] if parsed["districts"] else ""
        for fips in counties:
            out.setdefault(fips, {"court": cid, "division": None, "held": held})
        return out, problems
    # Virginia's independent cities (28 U.S.C. 127(c)): placed with the
    # district of every county or placed city they border, repeated until
    # nothing changes; one bordering both districts is reported.
    if neighbours:
        changed = True
        while changed:
            changed = False
            for fips in counties:
                if fips in out:
                    continue
                around = {out[n]["court"] for n in neighbours.get(fips, ()) if n in out}
                if len(around) == 1:
                    out[fips] = {"court": around.pop(), "division": None, "held": "",
                                 "byNeighbours": True}
                    changed = True
    missing = sorted(f"{counties[f]} ({f})" for f in counties if f not in out)
    if missing:
        problems.append(f"{code}: 28 U.S.C. {parsed['section']} places no district for "
                        f"{len(missing)} counties: {', '.join(missing[:8])}")
    return out, problems


def neighbours(code, root="."):
    """``{fips: {fips}}``: counties that share a boundary in the Census
    layer (a shared arc of the TopoJSON)."""
    path = os.path.join(root, "legislative_maps", f"{code.lower()}.json")
    with open(path, encoding="utf-8") as handle:
        layer = json.load(handle)["objects"]["counties"]
    arcs = {}

    def walk(item, fips):
        if isinstance(item, list):
            for x in item:
                walk(x, fips)
        elif isinstance(item, int):
            arcs.setdefault(item if item >= 0 else ~item, set()).add(fips)

    for geometry in layer["geometries"]:
        walk(geometry.get("arcs") or [], geometry["properties"]["id"])
    out = {}
    for owners in arcs.values():
        for a in owners:
            out.setdefault(a, set()).update(owners - {a})
    return out


def table(cache, root="."):
    """``({fips: entry}, problems)`` for every state the cache holds."""
    out, problems = {}, []
    held_states = set((cache or {}).get("states", {}))
    mapped = {f[:-5].upper() for f in os.listdir(os.path.join(root, "legislative_maps"))
              if f.endswith(".json")} if os.path.isdir(os.path.join(root, "legislative_maps")) else set()
    if mapped - held_states:
        problems.append(f"no district court is read for the counties of {sorted(mapped - held_states)}")
    for code, parsed in sorted((cache or {}).get("states", {}).items()):
        counties = census_counties(code, root)
        if counties is None:
            continue
        near = neighbours(code, root) if code in FORMER_COUNTIES or code == "VA" else None
        placed, trouble = join(code, parsed, counties, near)
        held = {e["court"]: e["held"] for e in placed.values() if e["held"] and not e["division"]}
        for fips, entry in placed.items():
            entry["name"], entry["state"] = counties[fips], code
            if entry.get("byNeighbours"):
                entry["held"] = held.get(entry["court"], "")
        out.update(placed)
        problems += trouble
    return out, problems


def area_words(code, fips_list):
    """``"13 parishes"``, ``"50 counties and 14 independent cities"``: a
    count of a state's areas in the words the state uses for them (rule 75,
    kyc/county_areas.py), an independent city counted as a city."""
    from . import county_areas

    one, many, _button = county_areas.words(code)
    cities = sum(1 for f in fips_list if (county_areas.AREAS.get(f) or (None, None))[1]
                 == county_areas.INDEPENDENT)
    rest = len(fips_list) - cities
    parts = ([f"{rest} {one if rest == 1 else many}"] if rest else []) + \
        ([f"{cities} independent {'city' if cities == 1 else 'cities'}"] if cities else [])
    return " and ".join(parts)


def for_courts(placed):
    """``{court id: [{"division", "held", "counties": [names], "areas"}]}``:
    each court's divisions (one unnamed unit for a court with none), with
    the areas in each by the names their state gives them, and their count
    in its words (:func:`area_words`), for the court's page."""
    from . import county_areas

    out, fips_of = {}, {}
    for fips, entry in sorted(placed.items(), key=lambda kv: kv[1]["name"]):
        units = out.setdefault(entry["court"], [])
        unit = next((u for u in units if u["division"] == entry["division"]), None)
        if unit is None:
            unit = {"division": entry["division"], "held": entry["held"], "counties": []}
            units.append(unit)
        fips_of.setdefault(id(unit), []).append(fips)
        unit["counties"].append(county_areas.local_name(fips, entry["name"]) +
                                (" (part: " + entry["except"] + ")" if entry.get("except") else ""))
    for cid, units in out.items():
        code = placed[fips_of[id(units[0])][0]]["state"]
        for unit in units:
            unit["areas"] = area_words(code, fips_of[id(unit)])
    return out


def covers(placed):
    """``{court id: "64 counties and 31 independent cities"}``: everything a
    court covers, in :func:`area_words`."""
    by_court = {}
    for fips, entry in placed.items():
        by_court.setdefault(entry["court"], (entry["state"], []))[1].append(fips)
    return {cid: area_words(code, fips_list) for cid, (code, fips_list) in by_court.items()}


def for_state(code, placed, names):
    """One state's entry in ``data/courtcounties.js``: ``{"names": {court
    id: short name}, "counties": {fips: [court id, division?, exception?]}}``,
    trailing empty parts dropped. A state that is one district with no
    divisions and no county kept elsewhere is ``{"names", "all": [court
    id]}``: the same answer for every county, said once. *names* is ``{court
    id: name}``."""
    rows, used = {}, {}
    for fips, entry in sorted(placed.items()):
        if entry["state"] != code:
            continue
        row = [entry["court"], entry["division"] or "", entry.get("except") or "",
               entry.get("exceptTo") or "", "neighbours" if entry.get("byNeighbours") else ""]
        while row[-1] == "":
            row.pop()
        rows[fips] = row
        for cid in (entry["court"], entry.get("exceptTo")):
            if cid:
                used[cid] = names[cid].replace("U.S. District Court for the ", "")
    out = {"names": dict(sorted(used.items()))}
    shapes = {tuple(row) for row in rows.values()}
    if len(shapes) == 1 and len(next(iter(shapes))) == 1:
        out["all"] = list(next(iter(shapes)))
    else:
        out["counties"] = rows
    return out


def county_courts(root="."):
    """``{state: entry}`` (:func:`for_state`) for every state: what
    ``data/courtcounties.js`` holds, the one small file the county pages
    load to say which federal court covers each county (FEDERAL-08)."""
    from .federal_courts import COURTS

    placed, _trouble = table(load_cache(root), root)
    names = {cid: court["name"] for cid, court in COURTS.items()}
    states = sorted({entry["state"] for entry in placed.values()})
    return {code: for_state(code, placed, names) for code in states}


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path
