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

What reaches the page is the list's: each name as it prints it, written
first name first and in ordinary capitals without a ballot title (rule
77: "Lombardo, Joseph" is Joseph Lombardo, "JOSH SHAPIRO" Josh Shapiro,
"Governor Sarah Huckabee Sanders" Sarah Huckabee Sanders), each party in
words where the list abbreviates it, the running mate on a joint ticket,
write-in candidates apart, and the list's address, what kind of document
it is and the day it was read. "Certified" is said only of a document whose
own words say it certifies the candidates, by the state's own office
(PR #109 review: a county's sample ballot and a commission's voter guide
were credited as "Certified by" them). Nothing else: no portrait (rule 24),
no money and no platform, and a statewide candidate is never a profile
(rule 27) nor joined to one by name (rule 25).

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
                            "ballotName", "record"})
OFFICE_KEYS = frozenset({"title", "certified", "certifiedQuote", "notStateList", "list",
                         "writeInList", "holderResearched", "holderOnList", "holderNote",
                         "holderSource", "holderUnconfirmed", "namesakes", "candidates",
                         "otherSources", "notes"})
# "kind" names the document in the page's words: "sample ballot", "candidate
# listing", "certified list of candidates".
LIST_KEYS = ("url", "title", "by", "read", "kind")

# A write-in's "party" that only says it is a write-in: under the page's
# "Write-in candidates" heading it says nothing more.
_WRITE_IN_LABEL = re.compile(r"^(?:WRI|WRITE-?IN|Write-?In Candidate)$", re.I)
# ... and Indiana's "Write-In (National Socialist American Workers')", whose
# party is what the brackets hold.
_WRITE_IN_PARTY = re.compile(r"^Write-?In\s*\((.+)\)$", re.I)
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_NICKNAME = re.compile(r"[\"“”][^\"“”]*[\"“”]")
_TOKEN = re.compile(r"[a-z0-9]+(?:['’-][a-z0-9]+)*")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# A party a list abbreviates, in words, from the list's own key or the
# statute that sets the labels; {jurisdiction or "*": {as printed: words}}.
# Anything else that reads as a code is refused by ``problems``, so no
# reader is left with "(IAP)".
PARTY_CODES = {
    # "Democrat" is the noun some lists print where others print "DEM" or
    # "Democratic": one party, so one word for it on every state page (wave
    # 2d review: Guam's and Alabama's read "(Democrat)", Georgia's
    # "(Democratic)"). A longer name a list gives ("Democratic-NPL",
    # "Registered Democrat") is that list's own and kept.
    "*": {"D": "Democratic", "DEM": "Democratic", "R": "Republican", "REP": "Republican",
          "LIB": "Libertarian", "Democrat": "Democratic", "DEMOCRAT": "Democratic"},
    # The Division of Elections' listing: "REP, DEM, LPF (Libertarian Party
    # of Florida), NPA (no party affiliation)" (the cache's notes, read
    # 2026-10-18).
    "FL": {"LPF": "Libertarian Party of Florida", "NPA": "No Party Affiliation"},
    # Clark County's 2026 sample ballot key ("IAP = Independent American
    # Party, LPN = Libertarian Party of Nevada, NPP = No Political Party"),
    # and NRS 293.267: "the words 'no political party' or the abbreviation
    # 'NPP'". Read 2026-10-18.
    "NV": {"IAP": "Independent American Party", "LPN": "Libertarian Party of Nevada",
           "NPP": "No Political Party"},
    # The Secretary of State's file labels a candidate both the Democratic
    # and Progressive parties nominated "DEM/PROG" (the cache's notes).
    "VT": {"DEM/PROG": "Democratic/Progressive"},
}
# A code: up to four capitals ("IAP", "NPA"), or codes joined by "/". A
# longer word in capitals is a party's name ("GREEN") and only recased.
_CODE = re.compile(r"^[A-Z]{1,4}(?:/[A-Z]{1,5})*$|^[A-Z]{1,5}(?:/[A-Z]{1,5})+$")
_SMALL = {"and", "of", "the", "for", "a"}

# A title a ballot prints before a name (Arkansas allows one), left off the
# name shown: "Governor Sarah Huckabee Sanders" is Sarah Huckabee Sanders.
_TITLE = re.compile(r"^(?:State\s+Senator|Senator|State\s+Representative|Representative|"
                    r"Lieutenant\s+Governor|Lt\.?\s+Governor|Governor|Attorney\s+General|"
                    r"Secretary\s+of\s+State|Judge|Mayor|Dr\.|Hon\.)\s+", re.I)
_NAME_SUFFIX = re.compile(r"^(?:jr|sr|ii|iii|iv)\.?$", re.I)
_ROMAN = re.compile(r"^(?:II|III|IV)$")


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


def _words(text):
    """The name's words with a hyphen read as a space: rule 77's "Kim-Varet"
    and "Kim Varet" are one spelling."""
    return [part for word in tokens(text) for part in word.split("-") if part]


def has_surname(family, text):
    """Does *text* carry the surname *family*, its words in order, however
    either side writes a hyphenated name?"""
    want = _words(family)
    have = _words(text)
    if not want:
        return False
    return any(have[i:i + len(want)] == want for i in range(len(have) - len(want) + 1))


def _shouting(word):
    letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", word)
    if word.startswith("Mc") and len(letters) > 3:
        letters = letters[2:]
    return len(letters) >= 1 and letters.upper() == letters


def display_name(name):
    """The name shown for a list's name (rule 77): first name first, in
    ordinary capitals, without a title the ballot prints before it. "Ford,
    Aaron D." -> "Aaron D. Ford"; "SAMUEL ISAIAH KANE, SR" -> "Samuel Isaiah
    Kane Sr."; "ADA, Vicente A." -> "Vicente A. Ada"; "Greer, Ramadhani
    “Ram” (Registered Democrat)" -> "Ramadhani “Ram” Greer (Registered
    Democrat)". A name the list writes in mixed case keeps its own capitals
    ("JB Pritzker", "DeWitt"); the list's own form stays beside it on the
    page (``printed``)."""
    from .candidates import _cap

    text = re.sub(r"\s+", " ", str(name or "")).strip()
    bare = _TITLE.sub("", text)
    if len(bare.split()) >= 2:
        text = bare
    tail = ""
    bracket = re.search(r"\s*(\([^()]*\))$", text)
    if bracket and bracket.start() > 0:
        tail, text = " " + bracket.group(1), text[:bracket.start()].strip()
    if "," in text:
        last, given = (part.strip() for part in text.split(",", 1))
        words = given.split()
        suffix = [w for w in words if _NAME_SUFFIX.match(w)]
        words = [w for w in words if not _NAME_SUFFIX.match(w)]
        text = " ".join(words + last.split() + suffix) if words else f"{last} {given}"
    words = text.split()
    loud = [w for w in words if re.search(r"[A-Za-z]", w) and not _ROMAN.match(w)]
    whole = bool(loud) and all(_shouting(w) for w in loud)

    def case(word):
        if _ROMAN.match(word) or not _shouting(word):
            return word
        letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", word)
        if not whole and (len(letters) < 3 or word[:1] in "\"“'"):
            return word          # "JB Pritzker", a nickname “JKT”
        return _cap(word)

    return " ".join(case(w) for w in words) + tail


def party_words(code, party, write_in=False):
    """A party as the page shows it: a code the list abbreviates, in words
    (``PARTY_CODES``); a party written in capitals, in ordinary ones
    ("FREEDOM AND UNITY" -> "Freedom and Unity"); a write-in's label that
    says only that it is a write-in, nothing (None)."""
    text = str(party or "").strip()
    if not text:
        return None
    inner = _WRITE_IN_PARTY.match(text)
    if inner:
        text = inner.group(1).strip()
    elif write_in and _WRITE_IN_LABEL.match(text):
        return None
    table = PARTY_CODES.get(code) or {}
    if text in table or text in PARTY_CODES["*"]:
        return table.get(text) or PARTY_CODES["*"][text]
    if _CODE.match(text):
        return text           # an unexplained code: ``problems`` refuses it
    if text.upper() == text and re.search(r"[A-Z]", text):
        words = text.lower().split()
        return " ".join(w if i and w in _SMALL else w[:1].upper() + w[1:]
                        for i, w in enumerate(words))
    return text


def possessive(by):
    return by + ("’" if by.endswith("s") else "’s")


def source_words(lst):
    """The document, as the page names it: "the Florida Division of
    Elections’ candidate listing"."""
    return f"the {possessive(lst['by'])} {lst['kind']}"


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

def elsewhere(url):
    """The ``overrides.STATEWIDE_LISTS_ELSEWHERE`` entry *url* falls under,
    as ``(prefix, codes, publisher, own, evidence)``, or None."""
    from . import overrides

    for prefix, (owners, label, own, evidence) in overrides.STATEWIDE_LISTS_ELSEWHERE.items():
        if str(url or "").startswith(prefix):
            return prefix, owners, label, own, evidence
    return None


def official(url, code):
    """``(True, label)`` when *url* is *code*'s own election office's page,
    or an evidenced list elsewhere (``overrides.STATEWIDE_LISTS_ELSEWHERE``);
    else ``(False, why)``. A compiled table never counts (rule 50)."""
    from . import voting_dates

    if voting_dates.compiled(str(url or "")):
        return False, "a compiled table, a lead and never a source (rule 50)"
    found = elsewhere(url)
    if found:
        _prefix, owners, label, _own, _evidence = found
        return (code in owners), (label if code in owners
                                  else f"{'/'.join(owners)}'s list, not {code}'s")
    return voting_dates.official_source(url, code)


def not_the_states(lst):
    """Is the list published by someone other than the state's own election
    office - a county, or a commission that certifies no one?"""
    found = elsewhere((lst or {}).get("url"))
    return bool(found) and not found[3]


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
    used = set()
    for code, entry in sorted(states.items()):
        for key, office in sorted(((entry or {}).get("offices") or {}).items()):
            out.extend(office_problems(code, key, office))
            for lst in ((office or {}).get("list"), (office or {}).get("writeInList")):
                found = elsewhere((lst or {}).get("url")) if isinstance(lst, dict) else None
                if found:
                    used.add(found[0])
    from .overrides import STATEWIDE_LISTS_ELSEWHERE
    for prefix in sorted(set(STATEWIDE_LISTS_ELSEWHERE) - used):
        # A stale entry would let a later list from that host through unread.
        out.append(f"overrides.STATEWIDE_LISTS_ELSEWHERE: {prefix} is no list's source")
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
    out.extend(_certified_problems(where, office))
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
        if not family or not has_surname(family, name):
            out.append(f"{label}: surname {family!r} is not a word of the name")
        for flag in ("writeIn", "holder"):
            if not isinstance(person.get(flag), bool):
                out.append(f"{label}: '{flag}' must be true or false")
        for field in ("party", "runningMate", "ballotName", "record"):
            value = person.get(field)
            if value is not None and not (isinstance(value, str) and value.strip()):
                out.append(f"{label}: '{field}' must be text or null")
        shown = party_words(code, person.get("party"), person.get("writeIn"))
        if shown and _CODE.match(shown):
            out.append(f"{label}: party {shown!r} is a code the page cannot spell out; add "
                       "its words to statewide.PARTY_CODES from the list's own key")
        if person.get("record"):
            ok, why = official(person["record"], code)
            if not ok:
                out.append(f"{label}: record {person['record']!r} is not an election office's: "
                           f"{why}")
    out.extend(_holder_problems(where, office, people))
    return out


def _certified_problems(where, office):
    """"Certified" is the document's word, never the researcher's: a list
    marked certified carries the document's own words saying it certifies
    the candidates (``certifiedQuote``, found in what the cache records of
    the document), is published by the state's own office, and is the only
    kind of list whose name says so. A list published by anyone else (a
    county, a commission) says why the state's own was not used
    (``notStateList``). PR #109 review: a county's sample ballot read
    "Certified by the Miami-Dade County Supervisor of Elections"."""
    out = []
    certified = office.get("certified")
    lst = office.get("list") if isinstance(office.get("list"), dict) else {}
    if not isinstance(certified, bool):
        return [f"{where}: 'certified' must be true or false"]
    words = str(office.get("certifiedQuote") or "").strip()
    if certified:
        recorded = " ".join(str(x or "") for x in (lst.get("title"), lst.get("quote"),
                                                    lst.get("dated"), office.get("notes")))
        if "certif" not in fold(words) or words not in recorded:
            out.append(f"{where}: a list marked certified needs the document's own words saying "
                       "so ('certifiedQuote'), as its title, quote, date or notes record them")
        if not_the_states(lst):
            out.append(f"{where}: {lst.get('by')} is not the state's election office; its list "
                       "is not the state's certification")
    elif words:
        out.append(f"{where}: 'certifiedQuote' on a list not marked certified")
    if "certif" in fold(lst.get("kind")) and not certified:
        out.append(f"{where}: the list's kind {lst.get('kind')!r} says certified; the list is "
                   "not marked so")
    why = str(office.get("notStateList") or "").strip()
    if not_the_states(lst) and not why:
        out.append(f"{where}: a list that is not the state's own election office's says why "
                   "('notStateList')")
    if why and not not_the_states(lst):
        out.append(f"{where}: 'notStateList' on the state's own list")
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
    if marked and not has_surname(family, marked[0]["name"]):
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
    return [p for p in people if isinstance(p, dict) and has_surname(family, " ".join(
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
    # The source names the document as what it is ("the Clark County
    # Registrar of Voters’ notice of general election"), never "the
    # certified list" for one that is not (PR #109 review).
    base = {"holder": holder, "source": lst["url"], "cite": source_words(lst),
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
                    text=f"{holder} is not among the candidates for this office"), stale
    person = carriers[0]
    from .overrides import STATEWIDE_NAME_FORMS
    form = (STATEWIDE_NAME_FORMS.get((code, key, holder)) or (None,))[0]
    if (len(carriers) == 1 and person.get("holder") and not stale
            and has_surname(family, person["name"])
            and (same_given_name(holder, person["name"]) or form == person["name"])):
        words = (f"{holder} is a write-in candidate for this office" if person.get("writeIn")
                 else f"{holder} is among the candidates for this office")
        more = entry.get("writeInList")
        if person.get("writeIn") and more:
            base = dict(base, source=more["url"], cite=source_words(more))
        if person.get("record"):
            # Pennsylvania's lieutenant governors: each candidate's own
            # record, which names them, rather than another candidate's.
            base = dict(base, source=person["record"])
        return dict(base, why="listed", text=words, name=person["name"]), None
    return None, (f"{code} {key}: the list names {', '.join(p['name'] for p in carriers)}, "
                  f"which may or may not be {holder}; not settled here"
                  + (f" ({stale.split(': ', 1)[1]})" if stale else ""))


def for_page(code, entry, holder_name=None):
    """What the page shows of one office's list: the candidates printed on
    the ballot, then the write-ins, each part in order of surname (the
    lists' own orders differ - Minnesota rotates its ballot by precinct -
    and the page says it uses this one); the list's address, the document
    named as what it is (``source``) and the day it was read. Each name is
    shown as ``display_name`` writes it, with the list's own form beside it
    (``printed``) where they differ; each party in words (``party_words``).
    *holder_name* is the list's name for the office's holder where
    ``holder_status`` settled it, so the search can leave them to their
    holder row."""
    def row(person):
        out = {"name": display_name(person["name"])}
        if out["name"] != person["name"]:
            out["printed"] = person["name"]
        if len(_words(person["name"])) < 2:
            # Massachusetts prints a joint ticket by surnames only: "JAMES
            # AND KITTREDGE". No first name is invented.
            out["surnameOnly"] = True
        party = party_words(code, person.get("party"), person.get("writeIn"))
        if party:
            out["party"] = party
        if person.get("runningMate"):
            out["runningMate"] = display_name(person["runningMate"])
        for field in ("ballotName", "record"):
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
            "source": source_words(lst), "read": lst["read"],
            "candidates": [row(p) for p in sorted(entry["candidates"], key=order)]}
    if entry.get("notStateList"):
        page["notStateList"] = entry["notStateList"]
    more = entry.get("writeInList")
    if more and any(p.get("writeIn") for p in entry["candidates"]):
        page["writeIns"] = {"url": more["url"], "by": more["by"], "read": more["read"],
                            "source": source_words(more)}
    return page


def member_leads(cache, legislators, noted):
    """Sitting members of Congress whose name and state a statewide list
    carries, with no ``overrides.OTHER_OFFICE_NOMINEES`` entry (*noted*, a
    set of bioguide ids) saying so. A lead for a person to confirm and record
    with evidence, never a join (rule 25): Amy Klobuchar was on Minnesota's
    governor ballot while her profile, her Senate seat not up, said nothing
    of it (PR #109 review)."""
    out = []
    for member in legislators or ():
        bioguide, code = member.get("bioguide"), member.get("state")
        if not bioguide or bioguide in noted:
            continue
        parts = member.get("nameParts") or {}
        last = parts.get("last") or member.get("last") or surname(member.get("name"))
        full = str(parts.get("official_full") or member.get("name") or "").split()
        firsts = [f for f in (parts.get("first"), parts.get("nickname"),
                              full[0] if full else None) if f]
        for key, entry in sorted(((((cache or {}).get("states") or {}).get(code) or {})
                                  .get("offices") or {}).items()):
            for person in entry.get("candidates") or ():
                for field in ("name", "runningMate"):
                    text = person.get(field)
                    if not text or not has_surname(last, text):
                        continue
                    if any(same_given_name(f"{first} {last}", text) for first in firsts):
                        out.append(f"{code} {key}: the list's {text!r} has the name of "
                                   f"{member.get('name')} ({bioguide}), whose profile does not "
                                   "say so (overrides.OTHER_OFFICE_NOMINEES)")
    return sorted(set(out))


def stats(cache):
    """Counts for the build log: never typed in."""
    offices = [o for e in ((cache or {}).get("states") or {}).values()
               for o in (e.get("offices") or {}).values()]
    people = [p for o in offices for p in o.get("candidates") or ()]
    return {"offices": len(offices),
            "candidates": sum(1 for p in people if not p.get("writeIn")),
            "writeIns": sum(1 for p in people if p.get("writeIn")),
            "certified": sum(1 for o in offices if o.get("certified")),
            "notState": sum(1 for o in offices if o.get("notStateList"))}
