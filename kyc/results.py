"""Primary election results: who is still in each race.

The FEC's register says who *filed*. It does not say who lost. TX-18 held its
primary on 3 March 2026 and a runoff on 26 May, and in September every
candidate who lost was still ``candidate_status=C, candidate_inactive=False``
- the only person the FEC had marked inactive was one who had died. So a page
built from the FEC alone showed twelve people for a seat with two nominees,
which is misleading in the opposite direction from the problem it fixed.

No free, structured, authoritative source of primary results exists. What does
exist is Wikipedia's per-state election pages, whose results tables are built
from a small family of templates with the winner marked *by template name*:

    {{Election box winning candidate with party link no change
    | candidate = [[Christian Menefee]] (incumbent)
    | votes = 43,750

That explicit marker is what makes this usable. Nothing here infers a result
from a vote count, and nothing is ever deleted: a candidate the page says lost
gets ``raceStatus = "eliminated"`` on their profile and is hidden from the
default view behind a toggle, which is reversible and visible.

Two gates keep it conservative:

* The FEC's own election calendar decides whether a primary has happened. A
  race whose primary is in the future is never touched, however Wikipedia has
  drafted its tables.
* A Wikipedia name is matched to a filing only within one race, on an exact
  folded surname plus a given-name prefix, and only when exactly one filing
  matches. Anything ambiguous is reported and left alone.

    python build_profile_site.py results          # refresh
    python build_profile_site.py results --check  # report from the cache
"""

import datetime
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "primary_results.json")

WIKI_API = "https://en.wikipedia.org/w/api.php"
_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 45
_GAP = 1.5  # Wikimedia throttles unregistered clients hard; a full run is ~85 pages

CYCLE = 2026

NOMINEE = "nominee"
ELIMINATED = "eliminated"
WITHDRAWN = "withdrawn"
ADVANCED = "advanced"   # through to a runoff that has not happened yet

# Filed with the FEC, but absent from the primary results for a race whose
# primary has happened. This is not "eliminated" - the page never listed them
# as running - and it is not an inference about why. Primary tables are copied
# from official returns, which name everyone who was on the ballot, so it means
# what it says: they filed, and they were not listed.
UNLISTED = "unlisted"

OFF_BALLOT = (ELIMINATED, WITHDRAWN, UNLISTED)


class ResultsError(RuntimeError):
    pass


# ------------------------------------------------------------------ calendar

def fetch_dates(cycle=CYCLE):
    """``{(state, office): {"primary": date, "runoff": date}}`` from the FEC."""
    from . import fec

    out = {}
    page = 1
    while True:
        payload = fec._get("/election-dates/", {
            "election_year": cycle, "per_page": 100, "page": page,
        })
        for row in payload.get("results") or []:
            state = row.get("election_state")
            office = row.get("office_sought")
            kind = row.get("election_type_id") or ""
            when = (row.get("election_date") or "")[:10]
            if not (state and office in ("H", "S") and when):
                continue
            slot = out.setdefault((state, office), {"primary": None, "runoff": None})
            # Some states list a date per district; keep the earliest primary
            # and the latest runoff, which brackets the whole process.
            if kind == "P" and (slot["primary"] is None or when < slot["primary"]):
                slot["primary"] = when
            elif kind == "R" and (slot["runoff"] is None or when > slot["runoff"]):
                slot["runoff"] = when
        pagination = payload.get("pagination") or {}
        if page >= pagination.get("pages", 1):
            break
        page += 1
        time.sleep(0.25)
    if not out:
        raise ResultsError("the FEC returned no election dates")
    return out


def primary_settled(dates, state, office, today):
    """True when this seat's primary - and its runoff, if any - has happened."""
    slot = dates.get((state, office))
    if not slot or not slot.get("primary"):
        return False
    latest = slot.get("runoff") or slot["primary"]
    return latest < today.isoformat()


# ----------------------------------------------------------------- wikipedia

_STATE_NAMES = None


def state_name(code):
    """``"TX"`` -> ``"Texas"``, in the casing Wikipedia titles use."""
    global _STATE_NAMES
    if _STATE_NAMES is None:
        from .normalize import US_STATES

        small = {"of"}
        _STATE_NAMES = {}
        for name, abbr in US_STATES.items():
            words = [w.lower() if w.lower() in small else w.capitalize()
                     for w in name.split()]
            _STATE_NAMES[abbr] = " ".join(words)
    return _STATE_NAMES.get(code)


def page_titles(state, office, cycle=CYCLE):
    """Candidate article titles for a state's races, most likely first."""
    name = state_name(state)
    if not name:
        return []
    if office == "H":
        return [
            f"{cycle} United States House of Representatives elections in {name}",
            f"{cycle} United States House of Representatives election in {name}",
        ]
    return [
        f"{cycle} United States Senate election in {name}",
        f"{cycle} United States Senate special election in {name}",
    ]


class PageMissing(Exception):
    """The article definitely does not exist - a fact, not a failure."""


def fetch_wikitext(title):
    """The article's source, following redirects.

    Raises :class:`PageMissing` when Wikipedia says the page does not exist,
    and :class:`~kyc.portraits.PortraitError` when the request could not be
    completed. The distinction is rule 8: a throttled request (Wikipedia
    returns 429 freely) is not evidence the page is absent, and treating it as
    such silently emptied results for 55 states on the first full run.
    """
    from .portraits import _get  # the backoff that honours Retry-After

    params = {
        "action": "query", "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "titles": title, "redirects": "1",
        "format": "json", "formatversion": "2",
    }
    url = f"{WIKI_API}?{urllib.parse.urlencode(params)}"
    payload = json.loads(_get(url, timeout=_TIMEOUT).decode("utf-8"))
    page = (payload.get("query", {}).get("pages") or [{}])[0]
    if page.get("missing") or "revisions" not in page:
        raise PageMissing(title)
    return page["revisions"][0]["slots"]["main"]["content"]


# ------------------------------------------------------------------- parsing

_BOX = re.compile(r"\{\{Election box begin[^}]*?\|\s*title\s*=\s*([^\n|}]+).*?\{\{Election box end\}\}",
                  re.S | re.I)
_ROW = re.compile(
    r"\{\{Election box (?P<kind>winning candidate|candidate)[^|}]*"
    r"(?P<body>(?:\|[^{}]*|\{\{[^{}]*\}\})*)\}\}",
    re.S | re.I,
)
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MARKUP = re.compile(r"'{2,}|<[^>]+>|\([^)]*\)")


def template_fields(body):
    """``{name: value}`` from the ``|name=value`` parameters of one template.

    Splits on the pipes that separate parameters and on nothing else. A value
    routinely contains its own pipes - every piped link does,
    ``[[Al Green (politician)|Al Green]]`` - so a naive split truncated names
    at the link's display text; the line-based regex that replaced it then
    swallowed whole one-line rows, so Michigan's Senate page yielded a
    candidate named ``"Haley Stevens|party=Democratic Party |votes=731,160"``
    and every one of that state's primary results went unread.
    """
    fields, depth, start = {}, 0, 0
    text = body or ""
    parts = []
    i = 0
    while i < len(text):
        two = text[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            i += 2
            continue
        if two in ("]]", "}}"):
            depth = max(depth - 1, 0)
            i += 2
            continue
        if text[i] == "|" and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    for part in parts:
        name, eq, value = part.partition("=")
        if eq and name.strip():
            fields[name.strip().lower()] = value.strip()
    return fields


# A ballot line that is not a person: an undecided slot or the write-in tally.
_PLACEHOLDER = re.compile(
    r"^(tbd|tba|to be (determined|announced)|none|vacant|write-?ins?|others?|"
    r"scattering|blank|no candidate|nominee)\b", re.I)


def clean_name(raw):
    """``[[Al Green (politician)|Al Green]] (incumbent)`` -> ``Al Green``."""
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), raw or "")
    text = _MARKUP.sub("", text)
    return " ".join(text.split())


def _is_withdrawn(raw):
    return "withdrawn" in (raw or "").lower() or "withdrew" in (raw or "").lower()


def parse_boxes(text):
    """Every results table in *text*, as ``(title, rows)``.

    A row is ``{"name", "won", "withdrawn", "votes"}``. ``won`` comes only from
    the template's own name - "winning candidate" - never from the count.
    """
    boxes = []
    for match in _BOX.finditer(text or ""):
        title = match.group(1).strip()
        rows = []
        for row in _ROW.finditer(match.group(0)):
            fields = template_fields(row.group("body"))
            raw = fields.get("candidate", "")
            name = clean_name(raw)
            if not name or _PLACEHOLDER.match(name):
                continue
            votes = fields.get("votes", "").replace(",", "")
            rows.append({
                "name": name,
                "won": row.group("kind").lower().startswith("winning"),
                "withdrawn": _is_withdrawn(raw),
                "votes": int(votes) if votes.isdigit() else None,
                # "Democratic Party (United States)", "[[Independent
                # politician|Independent]]" - the ballot's word on party.
                "party": clean_name(fields.get("party", "")) or None,
            })
        if rows:
            boxes.append((title, rows))
    return boxes


_INFOBOX = re.compile(r"\{\{\s*Infobox election\b", re.I)
_NOMINEE_FIELD = re.compile(r"^(?:nominee|candidate)\d+$")
_PARTY_FIELD = re.compile(r"^party(\d+)$")

INFOBOX_TITLE = "Infobox nominees"


def template_body(text, start):
    """The text inside the template that opens at *start*, balanced."""
    depth, i = 0, start
    while i < len(text):
        two = text[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
        elif two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start + 2:i - 2]
        else:
            i += 1
    return text[start + 2:]


def infobox_nominees(text):
    """Who the section's infobox puts on the November ballot.

    ``{{Infobox election}}`` carries ``nominee1``, ``nominee2``... and it is
    the one thing on a page editors keep current: Washington's 3rd had Marie
    Gluesenkamp Perez in its infobox while the general-election table below
    still listed only her opponent. Returned as rows in the shape
    :func:`parse_boxes` uses, so they merge with everything else.
    """
    match = _INFOBOX.search(text or "")
    if not match:
        return []
    fields = template_fields("|" + template_body(text, match.start()).split("|", 1)[-1])
    rows = []
    for key, value in fields.items():
        if not _NOMINEE_FIELD.match(key):
            continue
        name = clean_name(value)
        if not name or _PLACEHOLDER.match(name):
            continue
        number = re.sub(r"\D", "", key)
        party = clean_name(fields.get(f"party{number}", "")) or None
        rows.append({"name": name, "won": False, "withdrawn": False,
                     "votes": None, "party": party})
    return rows


def house_sections(text):
    """``{district_number: section_text}`` from a state's House page."""
    sections = {}
    parts = re.split(r"\n==+\s*District (\d+)\s*==+", text or "")
    # parts = [preamble, num, body, num, body, ...]
    for i in range(1, len(parts) - 1, 2):
        try:
            sections[int(parts[i])] = parts[i + 1]
        except ValueError:
            continue
    if not sections and text:
        # At-large states have no district headings; the whole page is it.
        sections[0] = text
    return sections


# ---------------------------------------------------------------- resolving

def _stage(title):
    lowered = title.lower()
    if "runoff" in lowered or "run-off" in lowered:
        return "runoff"
    if "primary" in lowered or "convention" in lowered or "caucus" in lowered:
        return "primary"
    if "election" in lowered or "general" in lowered:
        return "general"
    return None


def _clean_title(title):
    # "Republican primary results<ref name=...>{{cite web" -> the title only.
    return re.split(r"<ref|\{\{", title)[0].strip()


def _same_spelling(a, b):
    """Two spellings on one page that name one person.

    "Norma J. Torres" / "Norma Torres", "Dave Dawson" / "David Dawson",
    'John "Drew" Williams' / "Drew Williams", "Terri Yarbrough" / "Terri
    Yarbrough Green". The surname must match or sit inside the other name,
    and some given-name word must fit. This is applied within one race's
    page only, where two different people whose names nest like that do not
    occur - it is never used to decide between two FEC filings.
    """
    a, b = _tokens(a), _tokens(b)
    if len(a) < 2 or len(b) < 2:
        return False
    if a[-1] != b[-1] and a[-1] not in b and b[-1] not in a:
        return False
    return any(_given_fits(x, y) for x in a[:-1] for y in b[:-1])


def _canonical(boxes):
    """Rewrite every row's name to the first spelling seen for that person.

    Pages routinely write a candidate one way in the primary table and
    another on the general ballot ("Norma J. Torres" / "Norma Torres").
    Treating those as two people made both ambiguous and left the real one
    unlabelled.
    """
    seen = []
    out = []
    for title, rows in boxes:
        fixed = []
        for row in rows:
            name = row["name"]
            if name not in seen:
                same = [s for s in seen if _same_spelling(s, name)]
                if len(same) == 1:
                    name = same[0]
                else:
                    seen.append(name)
            fixed.append(dict(row, name=name))
        out.append((title, fixed))
    return out


def resolve_race(boxes, has_runoff=False):
    """Who is still standing, from a race's results tables.

    Returns ``{name: status}`` for everyone named in a primary-stage table.

    The general-election table, when the page has one, is the authority: the
    people in it are the nominees and everyone else named in a primary or
    runoff table is out. It exists for exactly this purpose and it is the
    table editors update first. Without one, a party's runoff table decides
    for the people in it. Without that either, a primary's marked winner is
    the nominee - unless the state holds runoffs and the primary marked two
    winners, in which case they only *advanced* and the page has not caught
    up with the runoff yet.
    """
    primaries, runoffs, generals, infobox = {}, {}, [], []
    for raw_title, rows in _canonical(boxes):
        title = _clean_title(raw_title)
        if title == INFOBOX_TITLE:
            infobox.extend(rows)
            continue
        stage = _stage(title)
        if stage == "runoff":
            runoffs.setdefault(title, []).extend(rows)
        elif stage == "primary":
            primaries.setdefault(title, []).extend(rows)
        elif stage == "general":
            generals.extend(rows)

    status = _resolve_tables(primaries, runoffs, generals, has_runoff)
    # The infobox names the November ballot and is kept current before the
    # tables are. It adds nominees the tables do not know about and settles a
    # runoff the runoff table has not caught up with. It never overrules a
    # table's verdict: an infobox still showing a presumptive nominee who
    # then lost the primary would otherwise put them back on the ballot, and
    # an infobox showing only the incumbent must not strike out a challenger
    # the primary table has crowned.
    for row in infobox:
        if status.get(row["name"]) in (None, ADVANCED):
            status[row["name"]] = NOMINEE
    return status


def _resolve_tables(primaries, runoffs, generals, has_runoff):

    named = set()
    for rows in list(primaries.values()) + list(runoffs.values()):
        named.update(r["name"] for r in rows)
    withdrawn = {r["name"] for rows in list(primaries.values()) + list(runoffs.values())
                 for r in rows if r["withdrawn"]}

    status = {}
    if generals:
        ballot = {r["name"] for r in generals}
        for name in named:
            if name in withdrawn:
                status[name] = WITHDRAWN
            elif name in ballot:
                status[name] = NOMINEE
            else:
                status[name] = ELIMINATED
        # Someone on the general ballot who skipped the primary (a
        # convention nominee, a party-switcher) is still a nominee.
        for name in ballot - named:
            status[name] = NOMINEE
        return status

    runoff_names = set()
    for rows in runoffs.values():
        for row in rows:
            runoff_names.add(row["name"])
            status[row["name"]] = (
                WITHDRAWN if row["withdrawn"] else NOMINEE if row["won"] else ELIMINATED
            )

    for title, rows in primaries.items():
        party_runoff = any(_party_of(title) == _party_of(rt) for rt in runoffs)
        winners = [r for r in rows if r["won"] and not r["withdrawn"]]
        for row in rows:
            if row["name"] in runoff_names:
                continue
            if row["withdrawn"]:
                status[row["name"]] = WITHDRAWN
            elif not winners and not party_runoff:
                # A table with nobody marked as winning is a table the page
                # has not filled in - a candidate list, not a result. Reading
                # it as "everyone lost" turned an unreported primary into a
                # field of eliminated candidates.
                continue
            elif not row["won"]:
                status[row["name"]] = ELIMINATED
            elif party_runoff:
                status[row["name"]] = ELIMINATED   # marked, but absent from the runoff
            elif has_runoff and len(winners) > 1:
                status[row["name"]] = ADVANCED     # runoff not reported yet
            else:
                status[row["name"]] = NOMINEE
    return status


def ballot_parties(boxes):
    """``{name: party key}`` as the page lists each person.

    The general-election table wins over a primary's, because that is where
    a party switch shows: Seth Bodnar is in no Montana primary table and on
    the November ballot as an independent, while a roster row called him a
    Democrat.
    """
    parties, general = {}, {}
    for raw_title, rows in _canonical(boxes):
        title = _clean_title(raw_title)
        stage = "general" if title == INFOBOX_TITLE else _stage(title)
        for row in rows:
            if not row.get("party"):
                continue
            key = party_key(row["party"])
            if stage == "general":
                general[row["name"]] = key
            else:
                parties.setdefault(row["name"], key)
    parties.update(general)
    return parties


def coverage(boxes):
    """What the page has actually decided, for people it does not name.

    ``{"general": bool, "parties": [keys]}`` - whether a general-election
    table exists, and which parties' primaries (or a nonpartisan primary,
    keyed ``"all"``) have a marked winner. Someone the page never mentions is
    only out of the race when the page has decided the contest they were in:
    a Democrat is not eliminated because the Republican table is complete.
    """
    general, parties = False, set()
    for raw_title, rows in boxes:
        title = _clean_title(raw_title)
        if title == INFOBOX_TITLE:
            continue          # names nominees; decides nothing about the rest
        stage = _stage(title)
        if stage == "general":
            general = True
        elif stage in ("primary", "runoff") and any(r["won"] for r in rows):
            parties.add(party_key(_party_of(title)))
    return {"general": general, "parties": sorted(parties)}


def _party_of(title):
    return title.lower().split(" primary")[0].split(" runoff")[0].strip()


_PARTY_KEYS = (
    ("democrat", "democratic"), ("dfl", "democratic"), ("farmer", "democratic"),
    ("republican", "republican"), ("libertarian", "libertarian"),
    ("green", "green"),
    ("nonpartisan", "all"), ("non-partisan", "all"), ("top-two", "all"),
    ("top two", "all"), ("top-four", "all"), ("top four", "all"),
    ("blanket", "all"), ("jungle", "all"), ("open", "all"), ("unified", "all"),
    ("independent", "independent"), ("unaffiliated", "independent"),
    ("no party", "independent"), ("nonpartisan", "independent"),
)

_FEC_PARTY_KEYS = {"DEM": "democratic", "DFL": "democratic", "REP": "republican",
                   "LIB": "libertarian", "GRE": "green", "GRN": "green",
                   "IND": "independent", "NON": "independent", "NNE": "independent",
                   "UNK": "independent", "NOP": "independent", "UN": "independent"}


def party_key(label):
    """One key for a party however a page, the FEC or the roster spells it."""
    text = str(label or "").strip()
    if text.upper() in _FEC_PARTY_KEYS:
        return _FEC_PARTY_KEYS[text.upper()]
    lowered = text.lower()
    if lowered in ("", "primary", "results"):
        return "all"
    for marker, key in _PARTY_KEYS:
        if marker in lowered:
            return key
    return lowered


# ----------------------------------------------------------------- matching

def _fold(text):
    normal = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v", "md", "phd", "esq"}
# Honorifics and credentials the FEC lets a filer type into the name field:
# "URIBE, CHARLES MR. JR.", "RAZACK, MD JD, NIZAM", "BAIRD, JAMES R DR.".
_TITLE_TOKENS = {"mr", "mrs", "ms", "miss", "dr", "hon", "rev", "sen", "rep",
                 "md", "jd", "phd", "esq", "dds", "cpa", "ret", "usaf", "usmc",
                 "usn", "usa", "col", "capt", "maj", "lt", "sgt"}

# Formal name -> the short forms people campaign under. The Wikipedia ballot
# says "Nick Begich III"; the FEC files "BEGICH, NICHOLAS III", and "nick" is
# not a prefix of "nicholas". Only the common English pairs are listed, and
# the pairing is used one way: a filed name and a ballot name match when
# either is the other's nickname, never on a guess about an unlisted one.
NICKNAMES = {
    "abraham": ("abe",), "albert": ("al", "bert"), "alexander": ("alex", "al"),
    "alexandra": ("alex", "lexy", "lexi", "sasha"), "alfred": ("al", "fred"),
    "andrew": ("andy", "drew"), "anthony": ("tony",), "arthur": ("art",),
    "benjamin": ("ben", "benny"), "bernard": ("bernie", "berney", "bern"),
    "catherine": ("cathy", "kate", "katie", "cat"), "charles": ("chuck", "charlie", "chas"),
    "christopher": ("chris",), "christine": ("chris", "chrissy"),
    "daniel": ("dan", "danny"), "david": ("dave", "davey"), "deborah": ("debbie", "deb"),
    "dennis": ("denny",), "donald": ("don", "donnie"), "douglas": ("doug",),
    "edward": ("ed", "eddie", "ted", "ned"), "eleanor": ("ellie", "nell"),
    "elinor": ("ellie",), "elizabeth": ("liz", "beth", "betsy", "eliza", "lisa", "libby"),
    "eugene": ("gene",), "francis": ("frank",), "franklin": ("frank",),
    "frederick": ("fred", "rick"), "gerald": ("jerry", "gerry"), "gregory": ("greg",),
    "gregorio": ("greg",), "harold": ("hal", "harry"), "henry": ("hank", "harry"),
    "herbert": ("herb",), "howard": ("howie",), "jacob": ("jake",),
    "james": ("jim", "jimmy", "jamie"), "jeffrey": ("jeff",), "jennifer": ("jen", "jenny", "jennie"),
    "jessica": ("jess", "jessie"), "john": ("jack", "johnny", "jon"), "jonathan": ("jon", "jonny"),
    "joseph": ("joe", "joey"), "joshua": ("josh",), "judith": ("judy",),
    "katherine": ("kathy", "kate", "katie", "kat"), "kathryn": ("kathy", "kate", "katie"),
    "kenneth": ("ken", "kenny"), "kimberly": ("kim",), "lawrence": ("larry",),
    "leonard": ("len", "lenny", "leo"), "margaret": ("peggy", "meg", "maggie", "marge"),
    "martin": ("marty",), "matthew": ("matt",), "michael": ("mike", "mikey", "mick"),
    "mitchell": ("mitch",), "nathan": ("nate",), "nathaniel": ("nate",),
    "nicholas": ("nick",), "patricia": ("pat", "patty", "tricia", "trish"),
    "patrick": ("pat", "paddy"), "peter": ("pete",), "philip": ("phil",),
    "phillip": ("phil",), "raymond": ("ray",), "rebecca": ("becky", "becca"),
    "richard": ("rick", "dick", "rich", "richie", "ricky"), "robert": ("bob", "rob", "bobby", "robby", "robbie"),
    "ronald": ("ron", "ronnie"), "rudolph": ("rudy",), "russell": ("russ",),
    "samuel": ("sam", "sammy"), "stephen": ("steve",), "steven": ("steve",),
    "susan": ("sue", "susie"), "theodore": ("ted", "teddy"), "thomas": ("tom", "tommy"),
    "timothy": ("tim",), "vincent": ("vince",), "walter": ("walt",),
    "william": ("bill", "will", "billy", "willie", "liam"), "zachary": ("zach", "zack"),
}
_FORMAL = {}
for _formal, _shorts in NICKNAMES.items():
    for _short in _shorts:
        _FORMAL.setdefault(_short, set()).add(_formal)


def _tokens(name):
    """Folded name words, without suffixes, honorifics or quote marks.

    "Warren Kenneth Paxton Jr." must end in "paxton", not "jr", or the surname
    test fails for everyone the FEC files with a suffix. A quoted nickname -
    ``HENRY C. 'HANK'`` - stays as a word of its own, because it is the name
    the ballot uses.
    """
    text = _fold(name).replace(".", " ").replace('"', " ").replace("'", " ")
    words = [w for w in text.split() if w]
    while len(words) > 1 and words[-1] in _SUFFIX_TOKENS:
        words.pop()
    kept = [w for w in words if w not in _TITLE_TOKENS]
    return kept if len(kept) >= 2 else words


def _given_fits(ballot, filed):
    """Does one given-name word fit another - exactly, as a nickname, or as
    a prefix of at least two letters ("Dan" / "Daniel"; never "C" / "Chris")."""
    if ballot == filed:
        return True
    if filed in NICKNAMES.get(ballot, ()) or ballot in NICKNAMES.get(filed, ()):
        return True
    if _FORMAL.get(ballot, set()) & _FORMAL.get(filed, set()):
        return True      # "Bob" and "Rob" are both Robert
    if len(ballot) >= 2 and len(filed) >= 2:
        return filed.startswith(ballot) or ballot.startswith(filed)
    return False


def _middle_conflict(ballot, filed):
    """A middle initial on both sides that disagrees.

    Alaska's Senate page writes the senator "Dan S. Sullivan"; the FEC holds
    "SULLIVAN, DAN" and a different "SULLIVAN, DANIEL J". The J rules the
    second one out, which is what lets the first stand as the only fit.
    """
    if len(ballot) < 3 or len(filed) < 3:
        return False
    return ballot[1][0] != filed[1][0]


def _same_person(a, b):
    """Two filed names that can only be one person registered twice.

    Identical after folding - "BAKER, AARON" twice, "CLEMMONS, MITCHELL" and
    "CLEMMONS, MITCHELL" - and nothing looser. "SULLIVAN, DAN" and "SULLIVAN,
    DANIEL J" look like one person and are not: Alaska's Senate race holds
    Senator Dan Sullivan and a different Daniel J Sullivan (rule 25), so a
    shorter name inside a longer one stays ambiguous.
    """
    return a == b


def match_names(wiki_names, field_rows, aliases=None):
    """``{wiki_name: [candidate_ids]}`` where the filings that fit are one person.

    Exact folded surname plus a given name that fits, inside one race only. A
    Wikipedia name that fits two different people is left unmatched and
    reported, as is a filing that two Wikipedia names fit. Two filings under
    one identical name - a duplicate registration - both take the status,
    which is how the page shows it either way.

    *aliases* are ``(display name, candidate_id)`` pairs from the curated
    roster, tried first on an exact folded match. They cover the names no
    rule can: the FEC files someone under a legal name that shares nothing
    with the one they campaign under.
    """
    from .candidates import display_name

    matches, ambiguous = {}, []
    claimed, unsure = {}, set()
    known = {_fold(name): cid for name, cid in (aliases or []) if name and cid}
    # An alias is one more spelling of a person, matched by the same rules
    # as a filed name. The roster's "Nicolas LaLota", the snapshot's "Nick
    # LaLota" and a filing all point at one id, and several spellings that
    # agree are one fit, not an ambiguity.
    pool = [(row["candidate_id"], _tokens(display_name(row.get("name"))))
            for row in field_rows]
    pool += [(cid, _tokens(name)) for name, cid in (aliases or []) if name and cid]
    for wiki in wiki_names:
        w = _tokens(wiki)
        if len(w) < 2:
            continue
        exact = known.get(_fold(wiki))
        if exact and exact not in claimed:
            matches[wiki] = [exact]
            claimed[exact] = wiki
            continue
        fits = {}
        for cid, f in pool:
            if len(f) < 2:
                continue
            # The surname may not be the last token: the FEC files Ashley
            # Hinson as "ARENHOLZ, ASHLEY HINSON". Accept it anywhere in the
            # filed name, but then require the given name to match exactly
            # rather than loosely, so the looser rule buys no false matches.
            if f[-1] == w[-1]:
                given_ok = any(_given_fits(b, g) for b in w[:-1] for g in f[:-1])
                if given_ok and _middle_conflict(w, f):
                    given_ok = False
            elif w[-1] in f[1:]:
                given_ok = f[0] == w[0]
            else:
                continue
            if given_ok:
                fits.setdefault(cid, f)
        fits = list(fits.items())
        if len(fits) > 1 and all(_same_person(fits[0][1], other) for _, other in fits[1:]):
            fits = [(cid, fits[0][1]) for cid, _ in fits]   # one person, several ids
        elif len(fits) > 1:
            ambiguous.append(wiki)
            unsure.update(cid for cid, _ in fits)
            continue
        if not fits:
            continue
        ids = [cid for cid, _ in fits]
        holder = next((claimed[cid] for cid in ids if cid in claimed), None)
        if holder:
            ambiguous.append(wiki)
            ambiguous.append(holder)
            unsure.update(ids)
            unsure.update(matches.pop(holder, []))
            continue
        matches[wiki] = ids
        for cid in ids:
            claimed[cid] = wiki
    for wiki in set(ambiguous):
        matches.pop(wiki, None)
    match_names.unsure = sorted(unsure)
    return matches, sorted(set(ambiguous))


# --------------------------------------------------------------------- build

def build(field, dates, today=None, log=print, fetch=fetch_wikitext, aliases=None):
    """Resolve every settled race. Returns the cache structure.

    ``{"asOf": date, "races": {race_id: {"status": {candidate_id: status},
    "unmatched": [names], "page": title}}, "pending": [race_ids]}``
    """
    from .candidates import race_id

    today = today or datetime.date.today()
    by_race = {}
    for row in (field or {}).get("candidates", []):
        rid = race_id(row)
        if rid:
            by_race.setdefault(rid, []).append(row)

    states = sorted({(row.get("state"), row.get("office"))
                     for rows in by_race.values() for row in rows[:1]})

    races, pending, missing_pages, failed = {}, [], [], []
    pages = {}
    for state, office in states:
        if not primary_settled(dates, state, office, today):
            pending.extend(rid for rid, rows in by_race.items()
                           if rows[0].get("state") == state and rows[0].get("office") == office)
            continue
        text, used, trouble = None, None, False
        for title in page_titles(state, office):
            try:
                text = fetch(title)
            except PageMissing:
                text = None          # a fact: try the next spelling
            except Exception as exc:  # inconclusive: say so, do not conclude
                log(f"    [warn] could not fetch {title!r}: {exc}")
                trouble = True
                text = None
            time.sleep(_GAP)
            if text:
                used = title
                break
        if text:
            pages[(state, office)] = (used, text)
        elif trouble:
            failed.append(f"{state}-{office}")
        else:
            missing_pages.append(f"{state}-{office}")

    for rid, rows in sorted(by_race.items()):
        state, office = rows[0].get("state"), rows[0].get("office")
        if (state, office) not in pages:
            continue
        title, text = pages[(state, office)]
        if office == "H":
            district = int(rid.split("-")[2])
            section = house_sections(text).get(district)
        else:
            section = text
        if not section:
            continue
        slot = dates.get((state, office)) or {}
        boxes = parse_boxes(section)
        nominees = infobox_nominees(section)
        if nominees:
            boxes.append((INFOBOX_TITLE, nominees))
        outcome = resolve_race(boxes, has_runoff=bool(slot.get("runoff")))
        if not outcome:
            continue
        matched, ambiguous = match_names(list(outcome), rows, (aliases or {}).get(rid))
        status, party = {}, {}
        listed = ballot_parties(boxes)
        for name, cids in matched.items():
            for cid in cids:
                status[cid] = outcome[name]
                if listed.get(name):
                    party[cid] = listed[name]
        races[rid] = {
            "page": title,
            "status": status,
            "party": party,
            # Ids a Wikipedia name fitted but could not be told apart. No
            # status, and no inference from their absence either.
            "unsure": match_names.unsure,
            # Named on the page but matching no filing. Their status is kept:
            # a nominee with no FEC filing over $5,000 is still on the ballot,
            # and a race header that omits them is wrong.
            "unmatched": {name: outcome[name] for name in sorted(set(outcome) - set(matched))},
            "ambiguous": ambiguous,
            "decided": coverage(boxes),
        }

    log(f"    settled races with results: {len(races)}   "
        f"pending primaries: {len(pending)}   pages missing: {len(missing_pages)}   "
        f"fetches failed: {len(failed)}")
    return {
        "asOf": today.isoformat(),
        "cycle": CYCLE,
        "races": races,
        "pending": sorted(pending),
        "missingPages": sorted(missing_pages),
        "fetchFailed": sorted(failed),
        # The calendar travels with the results so `build` needs no network
        # to know whether a race's primary has happened.
        "dates": {f"{state}-{office}": slot for (state, office), slot in sorted(dates.items())},
    }


# --------------------------------------------------------------------- cache

def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            cache = json.load(handle)
    except (ValueError, OSError):
        return None
    return cache if cache.get("races") is not None else None


def load_dates(root="."):
    """The FEC calendar as cached by the last ``results`` run."""
    cache = load_cache(root)
    out = {}
    for key, slot in ((cache or {}).get("dates") or {}).items():
        state, _, office = key.rpartition("-")
        if state and office:
            out[(state, office)] = slot
    return out


def apply_cache(profiles, cache):
    """Set ``raceStatus`` on every filed candidate the results name.

    Nothing is removed. A candidate the page says lost keeps their profile and
    gains a status the page can badge and hide behind a toggle.
    """
    if not cache:
        return 0
    by_id, party_of, unsure = {}, {}, set()
    races = cache.get("races", {})
    for rid, race in races.items():
        for cid, status in race.get("status", {}).items():
            by_id[cid] = (rid, status)
        party_of.update(race.get("party") or {})
        unsure.update(race.get("unsure") or [])
    from .candidates import race_id
    from .races import race_id as seat_id, seat_label

    applied = 0
    for profile in profiles:
        candidate_id = profile.get("fecCandidateId")
        if candidate_id not in by_id and profile.get("id") in by_id:
            candidate_id = profile["id"]     # matched through a roster alias
        if candidate_id and candidate_id in by_id:
            rid, status = by_id[candidate_id]
            profile["raceStatus"] = status
            profile["raceStatusRace"] = rid
            if candidate_id in party_of:
                profile["ballotParty"] = party_of[candidate_id]
                # The FEC record's party is what the person typed when they
                # first filed; the ballot line is what voters will see. For a
                # filed candidate the ballot wins, and the original stays on
                # the profile. A roster row that disagrees is reported by
                # ``validate`` for a person to correct.
                label = BALLOT_LABELS.get(party_of[candidate_id])
                if (profile.get("source") == "fec-field" and label
                        and party_key(profile.get("party")) != party_of[candidate_id]):
                    profile["fecParty"] = profile["party"]
                    profile["party"] = label
            applied += 1
            if not profile.get("isCandidate"):
                seat = seat_id(profile["chamber"], profile["state"], profile.get("districtNum"))
                if rid != seat:
                    # Named on another seat's ballot: that is the seat they
                    # are contesting, whatever the filing said.
                    profile["contestRaceId"] = rid
                    profile["contestLabel"] = seat_label(rid)
                    if profile.get("seatUp2026"):
                        profile["seekingReelection2026"] = False
                elif status in (NOMINEE, ADVANCED):
                    # On their own seat's ballot. That outranks a roster
                    # status line and a candidacy elsewhere: Russell Fry lost
                    # South Carolina's special Senate primary and is still the
                    # House nominee for SC-7.
                    profile["contestRaceId"] = None
                    profile["contestLabel"] = None
                    if profile.get("seatUp2026"):
                        profile["seekingReelection2026"] = True
                elif status in (ELIMINATED, WITHDRAWN):
                    # A sitting member who lost the primary is not on the
                    # November ballot, whatever the roster's status column
                    # says. The seat is open in every sense that matters.
                    profile["seekingReelection2026"] = False
        elif not profile.get("isCandidate") and profile.get("seatUp2026"):
            # The page has decided this member's own party's primary, or
            # shows the November ballot, and does not name them: they are not
            # running. The roster said "Active Member" for thirty-nine
            # retiring representatives, and a roster cannot notice a
            # retirement (rule 16). Their name, the snapshot's name and the
            # Wikipedia title all fed the matcher, so an absence is a
            # finding; ``validate`` lists every one so a miss would be seen.
            rid = seat_id(profile["chamber"], profile["state"], profile.get("districtNum"))
            if candidate_id in unsure or profile.get("id") in unsure:
                continue
            if rid in races and decided_for(races[rid], profile.get("party")):
                profile["raceStatus"] = UNLISTED
                profile["raceStatusRace"] = rid
                profile["seekingReelection2026"] = False
                applied += 1
        elif profile.get("isCandidate") and candidate_id not in unsure:
            rid = profile.get("contestRaceId") or race_id({
                "state": profile.get("state"),
                "office": "S" if "Senate" in profile.get("chamber", "") else "H",
                "district_number": profile.get("districtNum"),
            })
            if rid in races and decided_for(races[rid], profile.get("party")):
                profile["raceStatus"] = UNLISTED
                applied += 1
    return applied


BALLOT_LABELS = {"democratic": "Democrat", "republican": "Republican",
                 "libertarian": "Libertarian", "green": "Green",
                 "independent": "Independent"}


def decided_for(race, party):
    """Has the page settled the contest this person was in?

    True when it carries the general-election ballot, or a marked winner for
    a nonpartisan primary or for this person's own party's primary. A cache
    written before coverage was recorded answers yes for everyone, which is
    what it always did.
    """
    decided = race.get("decided")
    if decided is None:
        return True
    if decided.get("general"):
        return True
    parties = set(decided.get("parties") or [])
    return "all" in parties or party_key(party) in parties


def on_ballot(profile):
    """True unless the primary has settled this person out of the race."""
    return profile.get("raceStatus") not in OFF_BALLOT


def race_summary(cache, race_id):
    """``{"nominees": n, "eliminated": n, "withdrawn": n}`` or ``None``."""
    race = (cache or {}).get("races", {}).get(race_id)
    if not race:
        return None
    counts = {NOMINEE: 0, ELIMINATED: 0, WITHDRAWN: 0, ADVANCED: 0}
    for status in race.get("status", {}).values():
        counts[status] = counts.get(status, 0) + 1
    unmatched = race.get("unmatched") or {}
    if isinstance(unmatched, list):        # a cache written before statuses were kept
        unmatched = {}
    return {"nominees": counts[NOMINEE], "eliminated": counts[ELIMINATED],
            "withdrawn": counts[WITHDRAWN], "advanced": counts[ADVANCED],
            "otherNominees": sorted(n for n, st in unmatched.items() if st == NOMINEE)}
