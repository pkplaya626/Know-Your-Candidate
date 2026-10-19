"""Who is on the November 3, 2026 ballot for governor, lieutenant governor,
attorney general and secretary of state, from each election office's own
list (rule 91).

The site marked 36 governorships and some 90 other statewide offices "on the
Nov 3, 2026 ballot" and named no one running for any of them (audit
2026-10-17, FRESHNESS-05, STATEGOV-14, PERSONA-08, RACES-16). No source keyed
by an id lists state candidates, so the lists are a hand-edited cache,
``data/statewide_candidates.json``: researched jurisdiction by jurisdiction
from the election office's certified or qualified list - a Secretary of
State's, a board of elections', or a county election office's where the
state publishes none it could read - and every list re-opened by a second
reader. Ballotpedia, Wikipedia, news and party sites were leads, never
sources (rule 50).

What reaches the page is the list's: each name and party as it prints them
(rule 77), the running mate on a joint ticket, write-in candidates apart,
and the list's address and the day it was read. Nothing else: no portrait
(rule 24), no money and no platform, and a statewide candidate is never a
profile (rule 27) nor joined to one by name (rule 25).

The list also answers whether the office's holder is running for it
(rule 79): ``holder_status`` reads it for whoever the rosters name today,
so "not checked" goes away wherever a list is in hand, and an entry whose
holder no longer fits is withheld and reported.
"""

import datetime
import json
import os
import re
import unicodedata

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "statewide_candidates.json")

# What a candidate's row may hold: the list's words and two markers. A
# portrait, a figure or a platform is refused, not ignored.
CANDIDATE_KEYS = frozenset({"name", "surname", "party", "runningMate", "writeIn", "holder",
                            "ballotName"})
OFFICE_KEYS = frozenset({"title", "certified", "uncertified", "list", "writeInList",
                         "holderResearched", "holderOnList", "holderNote", "holderSource",
                         "holderUnconfirmed", "namesakes", "candidates", "otherSources",
                         "notes"})
LIST_KEYS = ("url", "title", "by", "read")

# A write-in's "party" that only says it is a write-in: under the page's
# "Write-in candidates" heading it says nothing more.
_WRITE_IN_LABEL = re.compile(r"^(?:WRI|WRITE-?IN|Write-?In Candidate)$", re.I)
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_NICKNAME = re.compile(r"[\"“”][^\"“”]*[\"“”]")
_TOKEN = re.compile(r"[a-z0-9]+(?:['’-][a-z0-9]+)*")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StatewideError(ValueError):
    """The cache breaks its rules."""


def load(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------- names

def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or ""))
                   if not unicodedata.combining(c)).lower()


def tokens(text):
    return _TOKEN.findall(fold(_NICKNAME.sub(" ", str(text or ""))))


def surname(name):
    """The family name in *name*, as a list or a roster writes it: "Lombardo,
    Joseph", "Leland Jake Olinger, II", "Brian P. Kemp". Only a sort key and
    a cross-check, never shown."""
    text = _NICKNAME.sub(" ", str(name or ""))
    if "," in text:
        before, after = text.split(",", 1)
        if fold(after).strip(" .") not in _SUFFIXES:
            words = before.split()
            return words[-1] if words else ""
        text = before
    words = [w for w in text.split() if fold(w).strip(".") not in _SUFFIXES]
    return words[-1].strip(".,") if words else ""


def _first(name):
    """The given name: the first word that is not the surname (a list that
    writes "Lombardo, Joseph" puts it second)."""
    family = fold(surname(name))
    for word in tokens(name):
        if word != family:
            return word
    return ""


def same_given_name(a, b):
    """Do two forms of a name share a given name, or one the short form of
    the other ("Kim" and "Kimberley", "Joe" and "Joseph")? Titles printed on
    a ballot ("Governor Sarah Huckabee Sanders") are words of *b*."""
    first = _first(a)
    if len(first) < 2:
        return False
    return any(len(w) >= 2 and (w.startswith(first) or first.startswith(w))
               for w in tokens(b) if w != fold(surname(b)))


# --------------------------------------------------------------- sources

def official(url, code):
    """``(True, label)`` when *url* is *code*'s own election office's page,
    or an evidenced list elsewhere (``overrides.STATEWIDE_LISTS_ELSEWHERE``);
    else ``(False, why)``. A compiled table never counts (rule 50)."""
    from . import overrides, voting_dates

    if voting_dates.compiled(str(url or "")):
        return False, "a compiled table, a lead and never a source (rule 50)"
    for prefix, (owners, label, _evidence) in overrides.STATEWIDE_LISTS_ELSEWHERE.items():
        if str(url or "").startswith(prefix):
            return (code in owners), (label if code in owners
                                      else f"{'/'.join(owners)}'s list, not {code}'s")
    return voting_dates.official_source(url, code)


def _list_problems(where, code, source, quoted=True):
    out = []
    if not isinstance(source, dict):
        return [f"{where}: no source"]
    missing = [k for k in LIST_KEYS if not str(source.get(k) or "").strip()]
    if quoted and not str(source.get("quote") or "").strip():
        missing.append("quote")
    if missing:
        out.append(f"{where}: the source has no {', '.join(missing)}")
    ok, why = official(source.get("url"), code)
    if not ok:
        out.append(f"{where}: {source.get('url')!r} is not an election office's list: {why}")
    read = str(source.get("read") or "")
    if not _DATE.match(read):
        out.append(f"{where}: read {read!r} is not a date")
    else:
        from .ballot2026 import ELECTION
        if not f"{ELECTION[:4]}-01-01" <= read <= datetime.date.today().isoformat():
            out.append(f"{where}: read {read} is outside the cycle or in the future")
    return out


# ---------------------------------------------------------------- checks

def problems(cache):
    """Every rule the cache breaks, as sentences; [] when it keeps them all.

    The offices listed must be exactly those ``kyc/ballot2026.py`` puts on
    the 2026 ballot, jurisdiction by jurisdiction: a list for an office not
    on it, or an office on it with no list, is a claim the other table
    contradicts."""
    from . import ballot2026

    if not isinstance(cache, dict) or not isinstance(cache.get("states"), dict):
        return [f"{CACHE_PATH}: no states"]
    states = cache["states"]
    every = dict(ballot2026.STATES, **ballot2026.TERRITORIES)
    out = []
    for code in sorted(set(states) - set(every)):
        out.append(f"{code}: not a jurisdiction kyc/ballot2026.py covers")
    for code, entry in sorted(every.items()):
        up = {k for k in ballot2026.OFFICES if k in entry and entry[k][1]}
        have = set(((states.get(code) or {}).get("offices")) or {})
        for key in sorted(up - have):
            out.append(f"{code} {key}: on the 2026 ballot (kyc/ballot2026.py) with no list of "
                       "its candidates")
        for key in sorted(have - up):
            out.append(f"{code} {key}: a list of candidates for an office kyc/ballot2026.py "
                       "does not put on the 2026 ballot")
    for code, entry in sorted(states.items()):
        for key, office in sorted(((entry or {}).get("offices") or {}).items()):
            out.extend(office_problems(code, key, office))
    return out


def office_problems(code, key, office):
    where = f"{code} {key}"
    out = []
    if not isinstance(office, dict):
        return [f"{where}: not a record"]
    extra = sorted(set(office) - OFFICE_KEYS)
    if extra:
        out.append(f"{where}: unknown fields {', '.join(extra)}")
    if not str(office.get("title") or "").strip():
        out.append(f"{where}: no title")
    if not isinstance(office.get("certified"), bool):
        out.append(f"{where}: 'certified' must be true or false")
    elif not office["certified"] and not str(office.get("uncertified") or "").strip():
        out.append(f"{where}: a list that is not certified must say why ('uncertified')")
    out.extend(_list_problems(where, code, office.get("list")))
    if office.get("writeInList") is not None:
        out.extend(_list_problems(f"{where} write-ins", code, office["writeInList"], quoted=False))
    people = office.get("candidates")
    if not isinstance(people, list) or not people:
        return out + [f"{where}: no candidates"]
    if all(isinstance(p, dict) and p.get("writeIn") for p in people):
        out.append(f"{where}: only write-in candidates; no one printed on the ballot")
    seen = set()
    for person in people:
        if not isinstance(person, dict):
            out.append(f"{where}: a candidate that is not a record")
            continue
        name = str(person.get("name") or "").strip()
        label = f"{where} {name or '?'}"
        extra = sorted(set(person) - CANDIDATE_KEYS)
        if extra:
            # No portrait, money or platform for these people (rules 24, 26).
            out.append(f"{label}: fields a list does not print: {', '.join(extra)}")
        if not name:
            out.append(f"{where}: a candidate with no name")
        if fold(name) in seen:
            out.append(f"{label}: listed twice")
        seen.add(fold(name))
        family = str(person.get("surname") or "")
        if not family or fold(family) not in tokens(name):
            out.append(f"{label}: surname {family!r} is not a word of the name")
        for flag in ("writeIn", "holder"):
            if not isinstance(person.get(flag), bool):
                out.append(f"{label}: '{flag}' must be true or false")
        for field in ("party", "runningMate", "ballotName"):
            value = person.get(field)
            if value is not None and not (isinstance(value, str) and value.strip()):
                out.append(f"{label}: '{field}' must be text or null")
    out.extend(_holder_problems(where, office, people))
    return out


def _holder_problems(where, office, people):
    """The researcher's reading of the holder must agree with itself: one
    candidate marked as the holder exactly when the holder is on the list,
    and that candidate's name carries the holder's."""
    out = []
    marked = [p for p in people if isinstance(p, dict) and p.get("holder")]
    researched = office.get("holderResearched")
    on_list = office.get("holderOnList")
    if len(marked) > 1:
        out.append(f"{where}: {len(marked)} candidates marked as the holder")
    if on_list is None:
        if marked or (researched and not office.get("holderUnconfirmed")):
            out.append(f"{where}: whether the holder is on the list is unknown, but nothing "
                       "says why ('holderUnconfirmed')")
        return out
    if not isinstance(on_list, bool):
        return out + [f"{where}: 'holderOnList' must be true, false or null"]
    if on_list != bool(marked):
        out.append(f"{where}: holderOnList is {on_list} but {len(marked)} candidate(s) are "
                   "marked as the holder")
    if not researched:
        return out + [f"{where}: holderOnList without the holder it was read for"]
    family = fold(surname(researched))
    if marked and family not in tokens(marked[0]["name"]):
        out.append(f"{where}: {marked[0]['name']} is marked as the holder, "
                   f"{researched}, whose surname it does not carry")
    namesakes = office.get("namesakes") or {}
    names = {p.get("name") for p in people if isinstance(p, dict)}
    for name, why in sorted(namesakes.items()):
        if name not in names:
            out.append(f"{where}: namesake {name!r} is not on the list")
        if not str(why or "").strip():
            out.append(f"{where}: namesake {name!r} says nothing of why it is not the holder")
        if any(p.get("name") == name and p.get("holder") for p in marked):
            out.append(f"{where}: {name} is marked both as the holder and as a namesake")
    if not on_list:
        carriers = [p["name"] for p in _carriers(people, family) if p["name"] not in namesakes]
        if carriers:
            out.append(f"{where}: {researched} is said not to be on the list, which names "
                       f"{', '.join(carriers)} (a namesake goes in 'namesakes', with why)")
    return out


def _carriers(people, family):
    """The candidates whose name, running mate or printed ticket carries the
    word *family*."""
    return [p for p in people if isinstance(p, dict) and family in tokens(" ".join(
        str(p.get(k) or "") for k in ("name", "runningMate", "ballotName")))]


def check(cache):
    found = problems(cache)
    if found:
        raise StatewideError("; ".join(found))
    return True


# ------------------------------------------------------------- the page

def office(cache, code, key):
    return ((((cache or {}).get("states") or {}).get(code) or {}).get("offices") or {}).get(key)


def holder_status(code, key, entry, holder):
    """``(record, problem)``: what the office's list says about *holder*,
    whoever the rosters name today, in the shape ``ballot2026.open_seat``
    gives.

    "not-listed" when no one on the list - names, running mates, the
    printed ticket - carries the holder's surname; "listed" when exactly
    one does, the researcher marked that one as the holder, and the given
    names agree. Anything else (a namesake, a holder the list was not read
    for) is not settled here: the record is None and the problem says why,
    so the caller says "not checked" rather than guess (rules 3, 25). None,
    None when there is no list or no named holder."""
    if not entry or not holder:
        return None, None
    lst = entry["list"]
    certified = "certified " if entry.get("certified") else ""
    base = {"holder": holder, "source": lst["url"], "cite": lst["by"],
            "certified": bool(entry.get("certified"))}
    family = fold(surname(holder))
    researched = entry.get("holderResearched")
    stale = None
    if researched and (fold(surname(researched)) != family
                       or not same_given_name(holder, researched)):
        stale = (f"{code} {key}: the list was read with {researched} as the holder; the "
                 f"rosters name {holder}")
    carriers = _carriers(entry["candidates"], family)
    if not stale:
        # A namesake recorded for this holder, with why it is not them; for
        # anyone else the rosters name, it settles nothing.
        carriers = [p for p in carriers if p["name"] not in (entry.get("namesakes") or {})]
    if not carriers:
        return dict(base, why="not-listed",
                    text=f"{holder} is not on the {certified}list of candidates for this office"), stale
    person = carriers[0]
    from .overrides import STATEWIDE_NAME_FORMS
    form = (STATEWIDE_NAME_FORMS.get((code, key, holder)) or (None,))[0]
    if (len(carriers) == 1 and person.get("holder") and not stale
            and family in tokens(person["name"])
            and (same_given_name(holder, person["name"]) or form == person["name"])):
        words = (f"{holder} is on the {certified}list as a write-in candidate for this office"
                 if person.get("writeIn")
                 else f"{holder} is on the {certified}list of candidates for this office")
        return dict(base, why="listed", text=words, name=person["name"]), None
    return None, (f"{code} {key}: the list names {', '.join(p['name'] for p in carriers)}, "
                  f"which may or may not be {holder}; not settled here"
                  + (f" ({stale.split(': ', 1)[1]})" if stale else ""))


def for_page(entry, holder_name=None):
    """What the page shows of one office's list: the candidates printed on
    the ballot, then the write-ins, each part in order of surname (the
    lists' own orders differ - Minnesota rotates its ballot by precinct -
    and the page says it uses this one); the list's address, who publishes
    it and the day it was read. *holder_name* is the list's name for the
    office's holder where ``holder_status`` settled it, so the search can
    leave them to their holder row."""
    def row(person):
        out = {"name": person["name"]}
        party = person.get("party")
        if party and not (person.get("writeIn") and _WRITE_IN_LABEL.match(party.strip())):
            out["party"] = party
        for field in ("runningMate", "ballotName"):
            if person.get(field):
                out[field] = person[field]
        if person.get("writeIn"):
            out["writeIn"] = True
        if holder_name and person["name"] == holder_name:
            out["holder"] = True
        return out

    def order(person):
        return (bool(person.get("writeIn")), fold(person["surname"]), fold(person["name"]))

    lst = entry["list"]
    page = {"certified": bool(entry.get("certified")), "url": lst["url"], "by": lst["by"],
            "read": lst["read"],
            "candidates": [row(p) for p in sorted(entry["candidates"], key=order)]}
    if not entry.get("certified"):
        page["uncertified"] = entry["uncertified"]
    more = entry.get("writeInList")
    if more and any(p.get("writeIn") for p in entry["candidates"]):
        page["writeIns"] = {"url": more["url"], "by": more["by"], "read": more["read"]}
    return page


def stats(cache):
    """Counts for the build log: never typed in."""
    offices = [o for e in ((cache or {}).get("states") or {}).values()
               for o in (e.get("offices") or {}).values()]
    people = [p for o in offices for p in o.get("candidates") or ()]
    return {"offices": len(offices),
            "candidates": sum(1 for p in people if not p.get("writeIn")),
            "writeIns": sum(1 for p in people if p.get("writeIn")),
            "uncertified": sum(1 for o in offices if not o.get("certified"))}
