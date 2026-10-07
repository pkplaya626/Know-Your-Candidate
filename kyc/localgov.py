"""Every local government, county by county: the Census Bureau's own listing.

``python build_profile_site.py localgov`` downloads the 2022 Census of
Governments' Government Units listing (one row per government, with its
county), reads its four sheets with the standard library, and writes
``local_governments/<st>.json``: each county's governments - its county
government, cities and towns, townships, school districts and special
districts - with the website, city, population or enrollment, and the title
of the contact official the Census records.

Two Census products must agree before anything is written: per state and
type, the listing's count has to equal the published table
(``data/census_governments.json``, table CG2200ORG02). A listing that does
not add up is refused, not shown.

The listing's names are in capitals ("COUNTY OF AUTAUGA"). They are shown in
title case for reading - acronyms such as ISD and MUD kept, McX and O'X
handled - and the published form is kept beside it (``census``).

A town or township keeps the listing's FIPS_PLACE as ``cousub``: for these
it is the county subdivision's own Census code, which is how the county
pages place it on the map. A city's FIPS_PLACE is not its place code in the
boundary files (Texarkana, Texas: 68810 against 72368), so it is not kept.
"""

import datetime
import io
import json
import os
import re
import urllib.request
import zipfile

from . import census
from .geo import FIPS_TO_STATE

URL = "https://www2.census.gov/programs-surveys/gus/datasets/2022/govt_units_2022.ZIP"
WORKBOOK = "Govt_Units_2022_Final.xlsx"
SOURCE = "U.S. Census Bureau, 2022 Census of Governments: Government Units listing"
OUT_DIR = "local_governments"

# Sheet number -> what its rows are. The fourth holds school systems run by a
# state, county or city: listed, but not counted as governments.
SHEETS = {1: "general", 2: "special", 3: "school", 4: "dependent"}
GENERAL_TYPES = {"1": "county", "2": "municipal", "3": "township"}
COUNTED = ("county", "municipal", "township", "special", "school")


class LocalGovError(RuntimeError):
    """The listing could not be fetched, or does not agree with the table."""


# ------------------------------------------------------------------- names

# Kept in capitals: districts' own abbreviations and Roman numerals.
_ACRONYMS = {
    "ISD", "CISD", "USD", "CSD", "SD", "MUD", "PUD", "SUD", "WCID", "FWSD", "ESD", "RFPD",
    "FPD", "CDD", "UD", "MD", "ID", "WSC", "RWD", "PWSD", "SWCD", "NRD", "REAA", "BOCES",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "LLC", "USA", "TVA", "CDA",
    "WID", "LID", "MWD", "RWA", "JPA", "TIF", "TIRZ", "EMS", "EMD", "HD", "PFD", "UTD",
}
_SMALL = {"of", "the", "and", "for", "in", "at", "on", "to", "by", "a", "an"}


def _word(word, first):
    if not word:
        return word
    core = re.sub(r"[^A-Za-z0-9']", "", word)
    if core.upper() in _ACRONYMS or any(ch.isdigit() for ch in core):
        return word.upper()
    lower = word.lower()
    if not first and lower in _SMALL:
        return lower
    out = lower[:1].upper() + lower[1:]
    out = re.sub(r"^(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    out = re.sub(r"^(O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out


def display_name(name):
    """Title case for reading; the published capitals stay in the data."""
    parts = re.split(r"(\s+|-|/|\()", (name or "").strip())
    out, first = [], True
    for part in parts:
        if not part or part.isspace() or part in "-/(":
            out.append(part)
            continue
        out.append(_word(part, first))
        first = False
    return "".join(out)


# ------------------------------------------------------------------ parsing

def _num(text):
    text = (text or "").strip()
    return int(text) if text.isdigit() else None


def _row_dict(head, row):
    row = row + [""] * (len(head) - len(row))
    return {h: (row[i] or "").strip() for i, h in enumerate(head)}


def parse(workbook_bytes):
    """``{code: {"counties": {fips: [government]}, "statewide": [...]}}``."""
    by_state = {}
    for sheet, kind in SHEETS.items():
        rows = census.sheet_rows(workbook_bytes, sheet)
        try:
            head = next(rows)
        except StopIteration:
            raise LocalGovError(f"sheet {sheet} is empty")
        for raw in rows:
            r = _row_dict(head, raw)
            code = FIPS_TO_STATE.get(r.get("FIPS_STATE", ""))
            if not code:
                continue
            if kind == "general":
                kind_here = GENERAL_TYPES.get(r.get("UNIT_TYPE", "")[:1])
                if not kind_here:
                    raise LocalGovError(f"unknown unit type {r.get('UNIT_TYPE')!r}")
            else:
                kind_here = kind
            gov = {"name": display_name(r["UNIT_NAME"]), "census": r["UNIT_NAME"],
                   "type": kind_here, "id": r.get("CENSUS_ID_GIDID") or r.get("CENSUS_ID_PID6")}
            for key, field in (("function", "FUNCTION_NAME"), ("title", "TITLE"),
                               ("city", "CITY")):
                if r.get(field):
                    gov[key] = (re.sub(r"^\d+\s*-\s*", "", r[field]) if key == "function"
                                else r[field])
            if gov.get("city"):
                gov["city"] = display_name(gov["city"])
            if gov.get("function"):
                gov["function"] = display_name(gov["function"]).replace(" and ", " and ")
            web = r.get("WEB_ADDRESS", "")
            if web.lower().startswith(("http://", "https://")):
                gov["web"] = web
            population = _num(r.get("POPULATION"))
            if population is not None:
                gov["population"] = population
            enrollment = _num(r.get("ENROLLMENT"))
            if enrollment is not None:
                gov["enrollment"] = enrollment
            if r.get("IS_ACTIVE") == "N":
                gov["inactive"] = True
            if kind_here == "township" and re.fullmatch(r"\d{5}", r.get("FIPS_PLACE", "")):
                gov["cousub"] = r["FIPS_PLACE"]
            state = by_state.setdefault(code, {"counties": {}, "statewide": []})
            county = r.get("FIPS_COUNTY", "")
            if county:
                fips = r["FIPS_STATE"] + county
                entry = state["counties"].setdefault(fips, {"name": display_name(
                    r.get("COUNTY_AREA_NAME", "")), "governments": []})
                entry["governments"].append(gov)
            else:
                state["statewide"].append(gov)
    for state in by_state.values():
        for entry in state["counties"].values():
            entry["governments"].sort(key=lambda g: (COUNTED.index(g["type"]) if g["type"] in COUNTED
                                                     else len(COUNTED), g["name"]))
        state["statewide"].sort(key=lambda g: g["name"])
    return by_state


def check_against_table(by_state, table):
    """Per state and type, the listing's count against the published table.
    Returns the disagreements; the fetch refuses any."""
    problems = []
    for code, counts in (table or {}).get("states", {}).items():
        state = by_state.get(code, {"counties": {}, "statewide": []})
        listed = {kind: 0 for kind in COUNTED}
        for entry in state["counties"].values():
            for gov in entry["governments"]:
                if gov["type"] in listed:
                    listed[gov["type"]] += 1
        for gov in state["statewide"]:
            if gov["type"] in listed:
                listed[gov["type"]] += 1
        for kind in COUNTED:
            if listed[kind] != (counts.get(kind) or 0):
                problems.append(f"{code} {kind}: listing {listed[kind]}, table {counts.get(kind) or 0}")
    return problems


def fetch(timeout=300):
    request = urllib.request.Request(URL, headers={"User-Agent": "know-your-candidate"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            archive = response.read()
        workbook = zipfile.ZipFile(io.BytesIO(archive)).read(WORKBOOK)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise LocalGovError(f"could not fetch {URL}: {exc}") from exc
    return parse(workbook)


def save(by_state, root="."):
    os.makedirs(os.path.join(root, OUT_DIR), exist_ok=True)
    fetched = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    paths = []
    for code, state in sorted(by_state.items()):
        payload = {"state": code, "source": SOURCE, "url": URL, "fetched": fetched,
                   "counties": {f: state["counties"][f] for f in sorted(state["counties"])},
                   "statewide": state["statewide"]}
        path = os.path.join(root, OUT_DIR, f"{code.lower()}.json")
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
        os.replace(path + ".tmp", path)
        paths.append(path)
    return paths


def load(code, root="."):
    path = os.path.join(root, OUT_DIR, f"{code.lower()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
