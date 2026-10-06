"""Who runs each state: its governor, and which party holds each chamber.

The governor comes from the NGA's roster (kyc/executives.py). Chamber
control is counted from the legislators Open States lists
(``data/state_legislators.json``) against each chamber's seats as NCSL
counts them (kyc/government_maps.SEATS): a party holds a chamber when it has
more than half of *all* its seats, so a seat with nobody listed is never
counted for anyone, and never called vacant (rule 19).

NCSL's table of partisan composition is a second, independent count. It is
dated - NCSL updates it a few times a year - and where it and Open States
disagree about which party holds a chamber, the page shows neither and says
the sources disagree (rule 53). Neither is quietly preferred.

A majority of seats is not always a majority that governs. Alaska's two
chambers are run by coalitions across parties; COALITIONS records that,
with the evidence, and ``check`` reports the note once the seat counts no
longer fit it.
"""

import datetime
import html
import json
import os
import re
import urllib.request

from .government_maps import LOWER_CHAMBER, SEATS, STATES

NCSL_URL = "https://www.ncsl.org/about-state-legislatures/state-partisan-composition"
NCSL_SOURCE = "National Conference of State Legislatures, State Partisan Composition"
NCSL_CACHE = os.path.join("candidate_profiles_site", "data", "partisan_composition.json")
USER_AGENT = "Mozilla/5.0 (compatible; know-your-candidate/1.0)"

# Chambers whose majority of seats does not run them. The Legislature's own
# roster names a Republican as minority leader in both chambers although
# Republicans hold a majority of the seats in each: the majorities that elect
# the leaders are coalitions of members from both parties.
#
# A note holds for one legislature. *session* is read from the legislators'
# own links (Open States lists each Alaska member's akleg.gov page, whose
# address carries the legislature's number): once the members listed belong
# to a later legislature, or the seats stop fitting, the note is not shown
# and ``build`` reports it.
COALITIONS = {
    "AK": {
        "party": "R",
        "chambers": ("upper", "lower"),
        "session": 34,
        "sessionLink": r"akleg\.gov/basis/Member/Detail/(\d+)",
        "text": ("Republicans hold a majority of the seats in both chambers, but the "
                 "Legislature's roster lists a Republican as minority leader in each: both "
                 "chambers are run by coalitions of members from both parties."),
        "source": "https://www.akleg.gov/basis/mbr_info.asp?session=34",
        "checked": "2026-10-05",
    },
}


def coalition_holds(code, records, chambers):
    """``(holds, why)`` for a state's coalition note against the current
    records and seat counts."""
    note = COALITIONS[code]
    for which in note["chambers"]:
        if (chambers.get(which) or {}).get("majority") != note["party"]:
            return False, (f"the note says {note['party']} holds a majority of the {which} "
                           f"chamber's seats; it no longer does")
    sessions = [int(n) for r in records for link in r.get("links", ())
                for n in re.findall(note["sessionLink"], link)]
    if not sessions or max(sessions) != note["session"]:
        return False, (f"the note is about legislature {note['session']}; the members listed "
                       f"belong to {max(sessions) if sessions else 'an unknown one'}")
    return True, ""

# The NGA posts no smaller copy of its headshots, and a guessed size URL is
# a 404. Most are 0.3-0.9 MB; one is 7.6 MB, for a 72px circle. A headshot
# whose size is unknown or above this is left off the card.
HEADSHOT_MAX_BYTES = 1_000_000


class StateGovError(RuntimeError):
    """The NCSL table could not be read, or does not have the expected shape."""


# -------------------------------------------------------------------- NCSL

def _cells(row):
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]


_HEAD = ["State", "Total House", "House Dem", "House Rep", "House Third Party",
         "House Vacancies", "Total Senate", "Senate Dem", "Senate Rep", "Senate Third Party",
         "Senate Vacancies", "Legislative Control", "Governor Party", "State Control"]


def parse_ncsl(page):
    """``{"updated", "states": {code: {...}}}`` from NCSL's composition page."""
    from .normalize import US_STATES
    start = page.find('<table id="partisanComp"')
    if start < 0:
        raise StateGovError("NCSL's page has no partisanComp table")
    table = page[start:page.find("</table>", start)]
    heads = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())
             for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    if heads != _HEAD:
        raise StateGovError(f"NCSL's table changed its columns: {heads}")
    by_name = {name.title(): code for name, code in US_STATES.items()}
    states = {}

    def num(text):
        return int(text) if text.isdigit() else 0

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        cells = _cells(row)
        if not cells or cells[0] not in by_name:
            continue
        lower = {"seats": num(cells[1]), "D": num(cells[2]), "R": num(cells[3]),
                 "other": num(cells[4]), "vacant": num(cells[5])}
        upper = {"seats": num(cells[6]), "D": num(cells[7]), "R": num(cells[8]),
                 "other": num(cells[9]), "vacant": num(cells[10])}
        states[by_name[cells[0]]] = {"upper": upper, "lower": lower, "legislature": cells[11],
                                     "governor": cells[12], "control": cells[13]}
    updated = re.search(r"Updated\s+([A-Z][a-z]+ \d{1,2}, \d{4})", page)
    missing = [c for c in STATES if c not in states]
    if missing:
        raise StateGovError(f"NCSL's table has no row for {', '.join(missing)}")
    return {"updated": updated.group(1) if updated else "", "states": states}


def fetch_ncsl():
    request = urllib.request.Request(NCSL_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            page = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise StateGovError(f"could not fetch {NCSL_URL}: {exc}") from exc
    return parse_ncsl(page)


def save_ncsl(table, root="."):
    payload = dict(table, source=NCSL_SOURCE, url=NCSL_URL, fetched=datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec="seconds"))
    path = os.path.join(root, NCSL_CACHE)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def load_ncsl(root="."):
    path = os.path.join(root, NCSL_CACHE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ----------------------------------------------------------------- counting

def majority(counts, seats):
    """The party holding more than half of *seats*, else ``None``."""
    for key in ("D", "R"):
        if counts.get(key, 0) * 2 > seats:
            return key
    return None


def chamber(records, which, seats):
    """Party counts for one chamber from the Open States records."""
    counts = {"D": 0, "R": 0, "I": 0, "N": 0}
    for record in records:
        if record["chamber"] == which and not record.get("tribalSeat"):
            counts[record["partyKey"]] += 1
    listed = sum(counts.values())
    return dict(counts, seats=seats, listed=listed, majority=majority(counts, seats))


def _date(text):
    try:
        return datetime.datetime.strptime(text.strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def in_office_since(terms):
    """The first day of the governor's current unbroken run of terms, and how
    many terms it spans. A gap of more than a month starts a new run."""
    spans = []
    for term in terms:
        start, _, end = term.partition(" - ")
        spans.append((_date(start), None if end.strip() == "Current" else _date(end), start.strip()))
    if not spans or spans[-1][0] is None:
        return "", 0
    run = [spans[-1]]
    for earlier in reversed(spans[:-1]):
        if earlier[1] is None or run[0][0] is None or (run[0][0] - earlier[1]).days > 31:
            break
        run.insert(0, earlier)
    return run[0][2], len(run)


def _governor(gov, problems=None):
    """What the page shows of a governor. The first day in office is shown
    only when Wikidata records the same date for them in that office: the
    NGA's pages give Kay Ivey April 19, 2017 and Kim Reynolds May 27, 2017,
    and they were sworn in on April 10 and May 24."""
    since, terms = in_office_since(gov.get("terms", []))
    first = _date(since) if since else None
    confirmed = first is not None and first.isoformat() in (gov.get("wikidataStarts") or ())
    if since and not confirmed and problems is not None and gov.get("wikidataStarts"):
        problems.append(f"{gov.get('state', '?')}: the NGA says {gov['name']} took office on "
                        f"{since}; Wikidata records {', '.join(gov['wikidataStarts'])}")
    out = {"name": gov["name"], "party": gov["party"], "partyKey": gov["partyKey"],
           "since": since if confirmed else "", "terms": terms, "profile": gov["profile"]}
    for key in ("website", "phone", "address"):
        if gov.get(key):
            out[key] = gov[key]
    if gov.get("headshot") and 0 < (gov.get("headshotBytes") or 0) <= HEADSHOT_MAX_BYTES:
        out["headshot"] = gov["headshot"]
    return out


# -------------------------------------------------------------------- build

def build(root="."):
    """``(payload, problems)``: what ``data/stategov.js`` holds, and every
    disagreement between the sources."""
    from . import courts, executives, officers, statelegs
    exec_cache, leg_cache, ncsl, officer_cache = (
        executives.load_cache(root), statelegs.load_cache(root), load_ncsl(root),
        officers.load_cache(root))
    for cache, path, command in ((exec_cache, executives.CACHE_PATH, "executives"),
                                 (leg_cache, statelegs.CACHE_PATH, "statelegs"),
                                 (ncsl, NCSL_CACHE, "executives"),
                                 (officer_cache, officers.CACHE_PATH, "officers")):
        if not cache:
            raise StateGovError(f"no {path}; run '{command}'")
    governors = exec_cache["governors"]
    legislators = leg_cache["states"]
    problems = []
    disputes = officers.overlaps(officer_cache["sos"], officer_cache["lt"])
    # The courts' cache is optional: a state whose court was never read
    # simply has no court block, rather than the build failing.
    court_cache = courts.load_cache(root)
    for code, office, theirs, ours in disputes:
        problems.append(f"{code}: NASS lists {theirs} as {office}, NLGA {ours}; neither is shown")
    problems.extend(officers.ag_problems(officer_cache.get("ag", {})))
    states = {}
    for code in sorted(governors):
        entry = {"governor": _governor(dict(governors[code], state=code), problems)}
        entry.update(officers.for_state(code, officer_cache, disputes))
        entry.update(courts.for_state(code, court_cache))
        if code in STATES:
            entry.update(_legislature(code, legislators.get(code, []), ncsl["states"].get(code),
                                      entry["governor"]["partyKey"], problems))
            theirs = (ncsl["states"].get(code) or {}).get("governor", "")
            if theirs and theirs != entry["governor"]["partyKey"]:
                problems.append(f"{code}: the NGA lists a {entry['governor']['party']} governor; "
                                f"NCSL's table ({ncsl['updated']}) says {theirs}")
        states[code] = entry
    missing = [c for c in STATES if c not in states]
    if missing:
        problems.append(f"no governor for {', '.join(missing)}")
    payload = {
        "states": states,
        "sources": {
            "nga": [executives.SOURCE, executives.ROSTER_URL, exec_cache.get("fetched", "")[:10]],
            "openstates": [statelegs.SOURCE, "https://openstates.org/",
                           leg_cache.get("fetched", "")[:10]],
            "ncsl": [NCSL_SOURCE, NCSL_URL, ncsl.get("updated", "")],
            "nass": ["National Association of Secretaries of State, membership roster",
                     officers.NASS_URL, officer_cache.get("fetched", "")[:10]],
            "nlga": ["National Lieutenant Governors Association, members", officers.NLGA_URL,
                     officer_cache.get("fetched", "")[:10]],
            "raga": ["Republican Attorneys General Association, members", officers.RAGA_URL,
                     officer_cache.get("fetched", "")[:10]],
            "daga": ["Democratic Attorneys General Association, members", officers.DAGA_URL,
                     officer_cache.get("fetched", "")[:10]],
        },
    }
    return payload, problems


def _legislature(code, records, theirs, governor_key, problems):
    upper_seats, lower_seats = SEATS[code]
    out = {"upper": dict(chamber(records, "upper", upper_seats),
                         title="Legislature" if code == "NE" else "Senate")}
    if lower_seats:
        out["lower"] = dict(chamber(records, "lower", lower_seats),
                            title=LOWER_CHAMBER.get(code, "House of Representatives"))
    if code == "NE":
        out["legislature"] = "nonpartisan"
        out["trifecta"] = "nonpartisan"
        return out
    disputed = False
    for which in ("upper", "lower"):
        if not theirs:
            continue
        ncsl = majority(theirs[which], theirs[which]["seats"] or out[which]["seats"])
        if ncsl != out[which]["majority"]:
            disputed = True
            out[which]["ncsl"] = ncsl or "none"
            problems.append(f"{code} {which}: Open States gives "
                            f"{out[which]['majority'] or 'no majority'}, NCSL "
                            f"{ncsl or 'no majority'}")
    upper, lower = out["upper"]["majority"], out["lower"]["majority"]
    holds, why = coalition_holds(code, records, out) if code in COALITIONS else (False, "")
    if why:
        problems.append(f"{code}: coalition note not shown: {why}")
    if disputed:
        out["legislature"] = out["trifecta"] = "disputed"
    elif holds:
        out["legislature"] = "coalition"
        out["trifecta"] = "divided"
        out["note"] = COALITIONS[code]["text"]
        out["noteSource"] = COALITIONS[code]["source"]
    elif upper and upper == lower:
        out["legislature"] = upper
        out["trifecta"] = upper if governor_key == upper else "divided"
    else:
        out["legislature"] = "split"
        out["trifecta"] = "divided"
    return out


def stats(payload):
    states = [s for c, s in payload["states"].items() if c in STATES]
    count = {}
    for s in states:
        count[s["trifecta"]] = count.get(s["trifecta"], 0) + 1
    return {"governors": len(payload["states"]), "trifectas": count}
