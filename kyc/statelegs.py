"""Every sitting state legislator, from Open States.

The site covers Congress through the ``congress-legislators`` dataset; this
is its state-level counterpart. ``python build_profile_site.py statelegs``
downloads Open States' per-state file of current legislators (public domain,
https://data.openstates.org/people/current/<st>.csv) for all fifty states,
keeps what the site shows, and writes ``data/state_legislators.json``.

Each legislator keeps Open States' own id (``ocd-person/...``), so a record
is never matched on a name (rules 3 and 17), and the links, portrait and
contact details come from that record (rule 32).

A legislator is placed on the map by matching their district to a Census
boundary (``legislative_maps/<st>.json``). Names differ in form - Open States
writes "Hampshire, Franklin and Worcester", the Census "Hampshire-Franklin-
Worcester"; Idaho's "10A" is seat A of district 10 - so both are normalised
the same way, and anyone who still does not match is reported, never
guessed (rule 16). New Hampshire's floterial representatives sit for an
overlay of several districts that a map of non-overlapping districts cannot
draw; they are listed, not placed.
"""

import csv
import datetime
import io
import json
import os
import re
import time
import urllib.request

OPENSTATES_URL = "https://data.openstates.org/people/current/{st}.csv"
SOURCE = "Open States (Plural Policy), current legislators"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "state_legislators.json")
MAPS_DIR = "legislative_maps"

REQUIRED = ("id", "name", "current_party", "current_district", "current_chamber")


class StateLegislatorsError(RuntimeError):
    """The data could not be fetched, or is not what the pipeline expects."""


# ------------------------------------------------------------------ parties

def party_key(label):
    """"D", "R", "I" or "N" (nonpartisan) for a party label as Open States
    writes it. Fusion lines name the party first ("Democratic/Working
    Families"); Minnesota's Democrats are the Democratic-Farmer-Labor Party."""
    first = (label or "").split("/")[0].strip().lower()
    if first.startswith("democratic"):
        return "D"
    if first.startswith("republican"):
        return "R"
    if first == "nonpartisan":
        return "N"
    return "I"


# ---------------------------------------------------------------- districts

_WORDS = ("state legislative subdistrict", "state legislative district", "state senate district",
          "state house district", "senatorial district", "state house", "district")


def norm(name):
    """A district name reduced to what both sources agree on: "10th Bristol
    District" and "10th Bristol"; "Hampshire-Franklin-Worcester" and
    "Hampshire, Franklin and Worcester"; "Chittenden South East" and
    "Chittenden Southeast"; "Merrimack 08" and "Merrimack 8"."""
    text = (name or "").lower()
    for word in _WORDS:
        text = text.replace(word, " ")
    text = re.sub(r"[-,.]", " ", text)
    tokens = [str(int(t)) if t.isdigit() else t for t in text.split() if t != "and"]
    return "".join(tokens)


def seat_district(code, chamber, district):
    """The Census district a seat belongs to, where a state numbers seats
    within a district: Idaho elects representatives to seats A and B of each
    legislative district."""
    if code == "ID" and chamber == "lower":
        return re.sub(r"^(\d+)\s*[AB]$", r"\1", district.strip(), flags=re.I)
    return district


def load_map(code, root="."):
    path = os.path.join(root, MAPS_DIR, f"{code.lower()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def boundary_index(topo):
    """``{chamber: {normalised name: Census code}}`` from a state's map."""
    out = {}
    for chamber in ("upper", "lower"):
        obj = (topo.get("objects") or {}).get(chamber)
        if not obj:
            continue
        index = {}
        for geometry in obj["geometries"]:
            props = geometry["properties"]
            index[norm(props["name"])] = props["id"]
        out[chamber] = index
    return out


def match(code, records, topo):
    """Give each record the Census code of its district (``districtId``).

    Returns the records that could not be placed, with the reason."""
    index = boundary_index(topo)
    unplaced = []
    for record in records:
        chamber = record["chamber"]
        names = index.get(chamber) or {}
        key = norm(seat_district(code, chamber, record["district"]))
        found = names.get(key)
        if found:
            record["districtId"] = found
        elif record.get("tribalSeat"):
            record.pop("districtId", None)          # elected by a nation, not a district
        else:
            record.pop("districtId", None)
            why = ("a floterial district, which overlays others and is not drawn"
                   if code == "NH" and chamber == "lower" else
                   "no boundary of that name")
            unplaced.append((record, why))
    return unplaced


# ------------------------------------------------------------------- record

def _split(value):
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def record(row, code):
    """What the site keeps of one Open States row."""
    chamber = row["current_chamber"].strip()
    out = {
        "id": row["id"].strip(),
        "name": row["name"].strip(),
        "party": row["current_party"].strip(),
        "partyKey": party_key(row["current_party"]),
        # Nebraska's one chamber is its upper house in the Census files.
        "chamber": "upper" if chamber == "legislature" else chamber,
        "district": row["current_district"].strip(),
        "state": code,
    }
    if chamber == "legislature":
        out["unicameral"] = True
    # Maine's House seats non-voting representatives of tribal nations,
    # elected by the nation, not a district (Open States names the nation).
    if code == "ME" and re.search(r"\b(tribe|band|nation)\b", out["district"], re.I):
        out["tribalSeat"] = True
    for key, field in (("email", "email"), ("image", "image"), ("phone", "capitol_voice"),
                       ("address", "capitol_address"), ("districtPhone", "district_voice"),
                       ("wikidata", "wikidata")):
        value = (row.get(field) or "").strip()
        if value:
            out[key] = value
    links = [u for u in _split(row.get("links")) if u.startswith("https://") or u.startswith("http://")]
    if links:
        out["links"] = links
    social = {k: row[k].strip() for k in ("twitter", "facebook", "instagram", "youtube")
              if (row.get(k) or "").strip()}
    if social:
        out["social"] = social
    return out


# -------------------------------------------------------------------- fetch

def parse(text, code):
    reader = csv.DictReader(io.StringIO(text))
    missing = [f for f in REQUIRED if f not in (reader.fieldnames or [])]
    if missing:
        raise StateLegislatorsError(f"{code}: the file has no {', '.join(missing)} column")
    rows = [record(row, code) for row in reader if (row.get("id") or "").strip()]
    if not rows:
        raise StateLegislatorsError(f"{code}: the file lists nobody")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise StateLegislatorsError(f"{code}: a legislator is listed twice")
    for r in rows:
        if r["chamber"] not in ("upper", "lower"):
            raise StateLegislatorsError(f"{code}: {r['name']} is in an unknown chamber")
    return rows


def fetch(codes, pause=0.5, timeout=60):
    """``{code: [records]}`` for each state."""
    out = {}
    for code in codes:
        url = OPENSTATES_URL.format(st=code.lower())
        request = urllib.request.Request(url, headers={"User-Agent": "know-your-candidate"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8")
        except OSError as exc:
            raise StateLegislatorsError(f"{code}: could not fetch {url}: {exc}") from exc
        out[code] = parse(text, code)
        time.sleep(pause)
    return out


def save_cache(by_state, root="."):
    payload = {
        "source": SOURCE,
        "url": OPENSTATES_URL.format(st="<st>"),
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "states": {code: sorted(by_state[code], key=lambda r: (r["chamber"], r["district"], r["name"]))
                   for code in sorted(by_state)},
    }
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------------- report

def seats_report(by_state):
    """``{code: {chamber: (listed, seats)}}`` against NCSL's seat counts. A
    seat with nobody listed is "not listed": Open States may be behind a
    special election, so the site does not call it vacant."""
    from .government_maps import SEATS
    out = {}
    for code, records in by_state.items():
        senate, house = SEATS[code]
        counts = {"upper": 0, "lower": 0}
        for r in records:
            if not r.get("tribalSeat"):         # not among NCSL's voting seats
                counts[r["chamber"]] += 1
        out[code] = {"upper": (counts["upper"], senate), "lower": (counts["lower"], house)}
    return out
