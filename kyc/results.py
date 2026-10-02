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

# A total order for /election-dates/ rows (see fec.fetch_pages).
CALENDAR_SORT = ("election_state", "office_sought", "election_type_id",
                 "election_district", "election_date", "create_date")


def fetch_dates(cycle=CYCLE):
    """``{(state, office): {"primary": date, "runoff": date}}`` from the FEC."""
    from . import fec

    # Unsorted, the three calendar pages shuffled between requests and Rhode
    # Island's Senate primary was never returned. This order is unique except
    # for rows the FEC itself lists twice, which are identical.
    rows, count = fec.fetch_pages("/election-dates/", {"election_year": cycle}, CALENDAR_SORT)
    if len(rows) != count:
        raise ResultsError(f"the FEC calendar returned {len(rows)} of {count} rows")
    out = {}
    for row in rows:
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
    if not out:
        raise ResultsError("the FEC returned no election dates")
    return out


def effective_dates(dates, senate_states=(), log=None):
    """The FEC calendar with the curated corrections laid over it.

    Returns ``(dates, notes)``. Two corrections:

    * ``overrides.OPEN_PRIMARY_SEATS`` replaces a seat's slot outright. The
      FEC's "primary" for Louisiana's House seats in 2026 is the end of
      qualifying, not an election, and reading it as one crowned every person
      Wikipedia listed in a vote-less November box as the nominee.
    * A state with a Senate race whose Senate slot has no primary date takes
      its House primary date. State primaries are held statewide on one day;
      the FEC listed Rhode Island's House primary (2026-09-09) and no Senate
      one, so S-RI-2026 could never settle.

    Each correction is described in ``notes``, and *log* (when given) is
    told, so a borrowed date is never silent.
    """
    from .overrides import OPEN_PRIMARY_SEATS

    out = {key: dict(slot) for key, slot in (dates or {}).items()}
    notes = []
    for state in sorted(set(senate_states)):
        # Only where the FEC lists a 2026 Senate election at all. People
        # file for Senate seats that are not up this cycle (Arizona,
        # California, New York ...); those states have no Senate slot, and
        # borrowing a date for them would "settle" a race that does not exist.
        slot = out.get((state, "S"))
        house = (out.get((state, "H")) or {}).get("primary")
        if slot is not None and not slot.get("primary") and house:
            out[(state, "S")] = dict(slot, primary=house)
            notes.append({"kind": "senate-from-house", "seat": f"{state}-S",
                          "text": f"{state} Senate: the FEC calendar has no primary date; "
                                  f"using {state}'s House primary date {house} "
                                  f"(state primaries are statewide)"})
    for (state, office, cycle), fixed in sorted(OPEN_PRIMARY_SEATS.items()):
        if cycle != CYCLE:
            continue
        fec_slot = (dates or {}).get((state, office)) or {}
        out[(state, office)] = {"primary": fixed["primary"], "runoff": fixed.get("runoff")}
        if (fec_slot.get("primary"), fec_slot.get("runoff")) != (fixed["primary"], fixed.get("runoff")):
            notes.append({"kind": "open-primary", "seat": f"{state}-{office}",
                          "text": f"{state}-{office}: open primary {fixed['primary']}, runoff "
                                  f"{fixed.get('runoff')} per overrides.OPEN_PRIMARY_SEATS; "
                                  f"the FEC calendar says primary {fec_slot.get('primary')}, "
                                  f"runoff {fec_slot.get('runoff')}"})
    for note in notes:
        if log:
            log(f"    [note] {note['text']}")
    return out, notes


def open_primary(state, office, cycle=CYCLE):
    """True for a seat whose first round is a nonpartisan primary in November."""
    from .overrides import OPEN_PRIMARY_SEATS

    return (state, office, cycle) in OPEN_PRIMARY_SEATS


def primary_settled(dates, state, office, today, open_seat=False):
    """True when this seat's results can be read.

    For a party primary that is once the primary - and its runoff, if any -
    has happened: a first round alone cannot say who the nominee is, and the
    page may never tabulate the runoff (TX-32's Ryan Binkley).

    *open_seat* is a seat whose first round is a nonpartisan primary on
    general-election day (:func:`open_primary`). That first round is itself a
    result - who advanced, who is out, or who won outright - so the seat
    opens once the primary has happened. Waiting for the runoff, as the
    party-primary gate does, kept every Louisiana House candidate "still
    running" for the six weeks between November 3 and the December 12
    runoff. :func:`resolve_race` reads the runoff table only once
    :func:`runoff_held`.
    """
    slot = dates.get((state, office))
    if not slot or not slot.get("primary"):
        return False
    latest = slot["primary"] if open_seat else (slot.get("runoff") or slot["primary"])
    return latest < today.isoformat()


def runoff_held(dates, state, office, today):
    """True when this seat has a runoff date and it has passed."""
    runoff = (dates.get((state, office)) or {}).get("runoff")
    return bool(runoff) and runoff < today.isoformat()


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
        # Territories and DC take "the" and some a longer name: on 2026-10-01
        # the delegates' articles were "... election in the District of
        # Columbia", "... in the United States Virgin Islands" and "... in the
        # Northern Mariana Islands". Asking only for the bare name read no
        # outcome for Norton or Plaskett at all.
        names = [name] + [f"the {n}" for n in (TITLE_NAMES.get(state, name),)]
        titles = []
        for n in names:
            titles += [
                f"{cycle} United States House of Representatives elections in {n}",
                f"{cycle} United States House of Representatives election in {n}",
            ]
        return titles
    return [
        f"{cycle} United States Senate election in {name}",
        f"{cycle} United States Senate special election in {name}",
    ]


# The name a territory goes by in an article title, where it is not the
# roster's. "Virgin Islands" alone is the British territory too.
TITLE_NAMES = {"VI": "United States Virgin Islands"}


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
    r"scattering|blank|no candidate|nominee|over-?votes?|under-?votes?)\b", re.I)


def link_target(raw):
    """The article a ballot line links to, or ``None``.

    ``[[Al Green (politician)|Al Green]]`` -> ``Al Green (politician)``. The
    state's election page linking a candidate to an article is the same kind
    of authority as the bioguide -> Wikipedia mapping for members: an editor
    asserted that this article is about this person on this ballot. It is
    what lets a filed candidate carry a portrait (rule 24 forbids guessing
    one) and a link to their article.
    """
    for match in _LINK.finditer(raw or ""):
        target = match.group(1).split("#")[0].strip()
        if target and ":" not in target:   # skip File:, Category:, wikt: ...
            return target[0].upper() + target[1:]
    return None


_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")

# Templates whose parameters are the words of a name, in order.
_NAME_TEMPLATES = {"sortname", "sort name"}


def _unwrap_template(match):
    """``{{nowrap|John Salvesen}}`` -> ``John Salvesen``.

    A formatting template wrapped around a name is still the name: GA-5's
    infobox wrote ``{{nowrap|John Salvesen}}`` and the race listed him twice,
    once under each spelling. ``{{sortname|First|Last}}`` is the name's two
    halves. Anything else - a citation, a flag - is not part of the name.
    """
    parts = list(template_fields_positional(match.group(1)))
    head = parts[0].strip().lower() if parts else ""
    args = [p.strip() for p in parts[1:] if "=" not in p]
    if head in _NAME_TEMPLATES:
        return " ".join(args[:2])
    if head in ("nowrap", "nobr", "nowrap begin", "small", "big", "nobold",
                "noitalic", "abbr", "lang", "nowr", "no wrap"):
        return args[-1] if head == "lang" else (args[0] if args else "")
    return ""


def template_fields_positional(body):
    """A template's parts split on its top-level pipes, name first."""
    depth, start, i = 0, 0, 0
    text = body or ""
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
            yield text[start:i]
            start = i + 1
        i += 1
    yield text[start:]


def clean_name(raw):
    """``[[Al Green (politician)|Al Green]] (incumbent)`` -> ``Al Green``."""
    text = raw or ""
    for _ in range(4):                      # innermost templates first
        unwrapped = _TEMPLATE.sub(_unwrap_template, text)
        if unwrapped == text:
            break
        text = unwrapped
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = _MARKUP.sub("", text)
    text = text.replace("{{", "").replace("}}", "")
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
                "article": link_target(raw),
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
                     "votes": None, "party": party, "article": link_target(value)})
    return rows


WITHDRAWN_LIST = "Withdrawn list"
WITHDREW_NOMINEE_LIST = "Withdrew after nomination list"
ELIMINATED_LIST = "Eliminated list"
# Pseudo-tables built from a page's candidate lists or infobox: they name
# people, but no one was counted in them.
LIST_TITLES = (WITHDRAWN_LIST, WITHDREW_NOMINEE_LIST, ELIMINATED_LIST)

_HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$", re.M)


def _list_kind(heading):
    lowered = clean_name(heading).lower()
    if re.fullmatch(r"withdrew after (?:nomination|winning)[^=]*", lowered):
        return WITHDREW_NOMINEE_LIST
    if re.fullmatch(r"withdrawn|withdrew(?: (?:from|before|during|prior)\b[^=]*)?", lowered):
        return WITHDRAWN_LIST
    if re.fullmatch(r"eliminated (?:in|at) [^=]*", lowered):
        return ELIMINATED_LIST
    return None


def _bullet_name(line):
    """``* [[Janet Mills]], governor of Maine ...`` -> raw ``[[Janet Mills]]``."""
    text = re.split(r"<ref|<!--", line, 1)[0]
    depth, i = 0, 0
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
        if text[i] in ",;:" and depth == 0:
            return text[:i]
        i += 1
    return text


# A heading that lists people who are on, or running for, a ballot line, and
# one that lists people who are not. A person an "Eliminated" list names is
# out only of the contest that list belongs to; where the page lists them a
# second time decides whether they carry on.
_BALLOT_HEADING = re.compile(
    r"(?:presumptive )?nominees?|declared|candidates|on the ballot|qualified|certified")
_OFF_BALLOT_HEADING = re.compile(
    r"filed(?: paperwork)?|potential|publicly expressed interest|declined|"
    r"withdrawn|withdrew\b.*|eliminated\b.*|disqualified|failed to qualify|"
    r"removed from (?:the )?ballot|lost\b.*|endorsements?|fundraising|polling|results")
# ''(running as an independent)'', ''(filed to run as an independent)'',
# ''(running on the Working Families line)''. A write-in is not a ballot line.
_CONTINUES = re.compile(r"''\((?![^)]*write-in)[^)]*\b(?:running|run) (?:as|on)\b[^)]*\)''", re.I)


def _list_bullets(text):
    """Every bullet under every heading, with the contest it belongs to.

    The contest is the nearest enclosing heading that is not a bare
    "Candidates": "Democratic primary", "Independents", "Write-in candidates".
    """
    out = []
    headings = list(_HEADING.finditer(text or ""))
    for n, heading in enumerate(headings):
        level, contest = len(heading.group(1)), ""
        for parent in reversed(headings[:n]):
            label = clean_name(parent.group(2)).lower()
            if len(parent.group(1)) < level and label != "candidates":
                contest = label
                break
            level = min(level, len(parent.group(1)))
        end = headings[n + 1].start() if n + 1 < len(headings) else len(text)
        for line in text[heading.end():end].splitlines():
            line = line.strip()
            if not line.startswith("*"):
                continue
            raw = _bullet_name(line.lstrip("*").strip())
            name = clean_name(raw)
            if len(name.split()) < 2 or _PLACEHOLDER.match(name):
                continue
            out.append({"heading": heading, "contest": contest, "name": name,
                        "raw": raw, "line": line})
    return out


def _continues_elsewhere(bullet, bullets):
    """Does the page say this person, on an "Eliminated" list, runs on?

    Andrew Rice (CT-3) sits under the Democrats' "Eliminated at convention"
    marked ''(running as an independent)''. Where the page lists him again
    decides it: a "Declared" heading in the independents' section is a run,
    a "Filed paperwork" heading is not. On 2026-09-13 the page had him under
    "Declared" and in the infobox; on 2026-09-15 an editor moved him to
    "Filed paperwork" and out of the infobox, noting he had not qualified for
    the ballot by petition. The annotation was never updated, so it decides
    only for someone the page lists nowhere else.

    A second listing counts as a run only in another party's contest and not
    as a write-in. Hampton Harris (AL-2) is a "Nominee" of the voided May
    Republican primary and "Eliminated" in the special Republican primary
    that replaced it; the first does not undo the second.
    """
    mine = party_key(bullet["contest"])
    for other in bullets:
        if (other["heading"].start() == bullet["heading"].start()
                or not _same_spelling(other["name"], bullet["name"])):
            continue
        heading = clean_name(other["heading"].group(2)).lower()
        if _OFF_BALLOT_HEADING.fullmatch(heading):
            return False
        if (_BALLOT_HEADING.fullmatch(heading) and "write-in" not in other["contest"]
                and party_key(other["contest"]) != mine):
            return True
    return bool(_CONTINUES.search(re.split(r"<ref", bullet["line"], maxsplit=1)[0]))


def candidate_lists(text):
    """The people a page files under "Withdrawn" or "Eliminated" headings.

    Returned as ``(title, rows)`` in the shape :func:`parse_boxes` uses, with
    one of :data:`LIST_TITLES` as the title. A results table records a vote;
    these lists record what happened afterwards. Chuck Edwards won NC-11's
    Republican primary with 70% and ended his bid on 2026-08-05, and the only
    place the page said so in a form a parser can read was the heading he was
    moved under: "Withdrew after nomination".

    An "Eliminated" list belongs to one party's contest. Someone the page
    says carries on under another line (:func:`_continues_elsewhere`) is left
    out of it, so the November ballot, the infobox or nothing decides them.
    """
    out = {}
    bullets = _list_bullets(text)
    for bullet in bullets:
        kind = _list_kind(bullet["heading"].group(2))
        if not kind:
            continue
        if kind == ELIMINATED_LIST and _continues_elsewhere(bullet, bullets):
            continue
        out.setdefault(kind, []).append({
            "name": bullet["name"], "won": False, "withdrawn": kind != ELIMINATED_LIST,
            "votes": None, "party": None, "article": link_target(bullet["raw"])})
    return [(kind, rows) for kind, rows in out.items()]


def house_sections(text, at_large=False):
    """``{district_number: section_text}`` from a state's House page.

    Only an at-large seat's page is read whole. A state with districts whose
    page has no "District N" headings is a page this cannot read - California's
    was split into two sub-articles on 2026-09-20 - and treating it as one
    at-large race silently dropped all 52 of its races.
    """
    sections = {}
    parts = re.split(r"\n==+\s*District (\d+)\s*==+", text or "")
    # parts = [preamble, num, body, num, body, ...]
    for i in range(1, len(parts) - 1, 2):
        try:
            sections[int(parts[i])] = parts[i + 1]
        except ValueError:
            continue
    if not sections and text and at_large:
        # At-large states have no district headings; the whole page is it.
        sections[0] = text
    return sections


_MAIN = re.compile(r"\{\{\s*(?:main|main article)\s*\|([^{}]*)\}\}", re.I)


def sub_articles(text, title):
    """Articles a page hands its districts to: ``{{main|<title> (districts 1–26)}}``."""
    found = []
    for match in _MAIN.finditer(text or ""):
        for target in template_fields_positional(match.group(1)):
            target = target.strip()
            if "=" in target:
                continue
            target = target[0].upper() + target[1:] if target else target
            if target.startswith(f"{title} (") and target not in found:
                found.append(target)
    return found


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


def resolve_race(boxes, has_runoff=False, open_primary=False, runoff_held=True):
    """Who is still standing, from a race's results tables.

    Returns ``{name: status}`` for everyone named in a primary-stage table,
    on the general ballot, in the infobox, or in a Withdrawn / Eliminated
    candidate list.

    The general-election table, when the page has one, is the authority: the
    people in it are the nominees and everyone else named in a primary or
    runoff table is out. It exists for exactly this purpose and it is the
    table editors update first. Without one, a party's runoff table decides
    for the people in it. Without that either, a primary's marked winner is
    the nominee - unless the state holds runoffs and the primary marked two
    winners, in which case they only *advanced* and the page has not caught
    up with the runoff yet.

    Leaving the race is not losing it. A marked primary winner who is not on
    the general ballot withdrew (Chuck Edwards, NC-11; Graham Platner, Maine
    Senate); a primary loser is eliminated however the page annotates their
    row (Janet Mills suspended her campaign, stayed on the ballot and lost).

    *open_primary* is a seat whose first round is a nonpartisan primary on
    general-election day (Louisiana's House seats in 2026). Its November table
    is that primary: nobody has any status until it marks a result (see
    :func:`_open_rounds`), the two marked winners only advance and everyone
    else in it is out, one marked winner with a majority of the counted vote
    is elected outright, and once *runoff_held* a December runoff table that
    marks a winner decides it.
    """
    if open_primary:
        boxes = _open_rounds(boxes, runoff_held)
        if not any(r["won"] for title, rows in boxes
                   if title in (OPEN_PRIMARY_TITLE, OPEN_RUNOFF_TITLE) for r in rows):
            # Election night before the page has a result: no statuses at
            # all, so nothing is inferred from anyone's absence either.
            return {}
    primaries, runoffs, generals, infobox, lists = {}, {}, [], [], {}
    for raw_title, rows in _canonical(boxes):
        title = _clean_title(raw_title)
        if title == INFOBOX_TITLE:
            infobox.extend(rows)
            continue
        if title in LIST_TITLES:
            lists.setdefault(title, []).extend(rows)
            continue
        stage = _stage(title)
        if stage == "runoff":
            runoffs.setdefault(title, []).extend(rows)
        elif stage == "primary":
            primaries.setdefault(title, []).extend(rows)
        elif stage == "general":
            generals.extend(rows)

    status = _resolve_tables(primaries, runoffs, generals, has_runoff or open_primary)

    # Who lost a decided contest. Nothing below may turn them into anything
    # else: a convention's "Withdrawn" list naming a primary loser, or a
    # ''(withdrawn)'' on their primary row, does not undo the count.
    lost = _losers(primaries, runoffs) - {r["name"] for r in generals if not r["withdrawn"]}
    for name in lost:
        status[name] = ELIMINATED

    ballot = {r["name"] for r in generals if not r["withdrawn"]}
    after_nomination = {r["name"] for r in lists.get(WITHDREW_NOMINEE_LIST, [])}
    withdrew = {r["name"] for r in lists.get(WITHDRAWN_LIST, [])}
    for name in after_nomination | withdrew:
        if name in lost:
            continue
        # A generic "Withdrawn" list does not outrank the November ballot -
        # someone can leave a party's primary and run as an independent. A
        # "Withdrew after nomination" list is about the nominee and does.
        if name in ballot and name not in after_nomination:
            continue
        status[name] = WITHDRAWN
    for row in lists.get(ELIMINATED_LIST, []):
        status.setdefault(row["name"], ELIMINATED)

    # The infobox names the November ballot and is kept current before the
    # tables are. It adds nominees the tables do not know about and settles a
    # runoff the runoff table has not caught up with. It never overrules a
    # table's verdict: an infobox still showing a presumptive nominee who
    # then lost the primary would otherwise put them back on the ballot, and
    # an infobox showing only the incumbent must not strike out a challenger
    # the primary table has crowned. An open primary has no nominees to name.
    if not open_primary:
        for row in infobox:
            if status.get(row["name"]) in (None, ADVANCED):
                status[row["name"]] = NOMINEE
    return status


OPEN_PRIMARY_TITLE = "Nonpartisan primary results"
OPEN_RUNOFF_TITLE = "Nonpartisan runoff results"


def _open_rounds(boxes, runoff_held=True):
    """An open-primary seat's tables, rewritten as its two rounds.

    The November box is titled like a general election ("2026 Louisiana's
    5th congressional district election") and is the first round; it becomes
    one ``OPEN_PRIMARY_TITLE`` table. Its marked winners count only when they
    are a result the rules allow: the top two, or one candidate holding a
    majority of the counted vote (Louisiana elects outright with a majority).
    Anything else - one winner with no vote count, three winners - is a page
    mid-edit, and its markers are dropped rather than read as a verdict.

    A runoff box becomes ``OPEN_RUNOFF_TITLE``, and is kept only once the
    runoff has been held and it marks a winner. A vote-less December box put
    up the morning after the first round would otherwise eliminate both
    people still running.

    Infobox, candidate-list and party-primary tables pass through untouched.
    """
    out, first, at = [], [], None
    for raw_title, rows in boxes:
        title = _clean_title(raw_title)
        if title == INFOBOX_TITLE or title in LIST_TITLES:
            out.append((raw_title, rows))
            continue
        stage = _stage(title)
        if stage == "general":
            if at is None:
                at = len(out)
                out.append(None)
            first.extend(rows)
        elif stage == "runoff":
            if runoff_held and any(r["won"] for r in rows):
                out.append((OPEN_RUNOFF_TITLE, rows))
        else:
            out.append((raw_title, rows))
    if at is not None:
        if not _first_round_decided(first):
            first = [dict(r, won=False) for r in first]
        out[at] = (OPEN_PRIMARY_TITLE, first)
    return out


def _first_round_decided(rows):
    """True when an open primary's marked winners are a complete result."""
    winners = {r["name"] for r in rows if r["won"] and not r["withdrawn"]}
    if len(winners) == 2:
        return True
    if len(winners) != 1:
        return False
    votes = [r.get("votes") for r in rows]
    if any(v is None for v in votes) or not sum(votes):
        return False
    top = max(r["votes"] for r in rows if r["name"] in winners)
    return 2 * top > sum(votes)


def _losers(primaries, runoffs):
    """Everyone the count put out: unmarked in a table that marked a winner."""
    out = set()
    later = {r["name"] for rows in runoffs.values() for r in rows}
    for title, rows in list(primaries.items()) + list(runoffs.items()):
        if not any(r["won"] for r in rows):
            continue
        is_runoff = title in runoffs
        for row in rows:
            if not row["won"] and (is_runoff or row["name"] not in later):
                out.add(row["name"])
    return out


def _resolve_tables(primaries, runoffs, generals, has_runoff):

    named = set()
    for rows in list(primaries.values()) + list(runoffs.values()):
        named.update(r["name"] for r in rows)
    withdrawn = {r["name"] for rows in list(primaries.values()) + list(runoffs.values())
                 for r in rows if r["withdrawn"]}

    status = {}
    if generals:
        ballot = {r["name"] for r in generals if not r["withdrawn"]}
        struck = {r["name"] for r in generals if r["withdrawn"]}
        won_final = _final_winners(primaries, runoffs, has_runoff)
        for name in named:
            if name in withdrawn or name in struck:
                status[name] = WITHDRAWN
            elif name in ballot:
                status[name] = NOMINEE
            elif name in won_final:
                # Won their party's nomination and is not on the November
                # ballot: they left the race. Calling that "eliminated" told
                # readers Graham Platner lost a primary he won by 40 points.
                status[name] = WITHDRAWN
            else:
                status[name] = ELIMINATED
        # Someone on the general ballot who skipped the primary (a
        # convention nominee, a party-switcher) is still a nominee - unless
        # the ballot itself marks them withdrawn.
        for name in ballot - named:
            status[name] = NOMINEE
        for name in struck - named:
            status[name] = WITHDRAWN
        return status

    runoff_names = set()
    for rows in runoffs.values():
        # A runoff table nobody has marked is a runoff the page has not
        # reported yet, not one everybody lost: reading it that way knocked
        # both runoff candidates out of a race the moment an editor posted the
        # empty box. They are still in it until a winner is marked.
        decided = any(r["won"] for r in rows)
        for row in rows:
            runoff_names.add(row["name"])
            if row["withdrawn"]:
                status[row["name"]] = WITHDRAWN
            elif not decided:
                status[row["name"]] = ADVANCED
            else:
                status[row["name"]] = NOMINEE if row["won"] else ELIMINATED

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


def _final_winners(primaries, runoffs, has_runoff):
    """People whose last contest on the page marked them as its winner.

    A first-round winner in a runoff state whose runoff the page does not
    show is left out: they may have lost a runoff nobody tabulated (TX-32's
    Ryan Binkley), and the absence cannot tell which.
    """
    out = set()
    in_runoff = {r["name"] for rows in runoffs.values() for r in rows}
    for rows in runoffs.values():
        out.update(r["name"] for r in rows if r["won"])
    for rows in primaries.values():
        winners = [r for r in rows if r["won"]]
        if has_runoff and len(winners) > 1:
            continue
        out.update(r["name"] for r in winners if r["name"] not in in_runoff)
    return out


def ballot_articles(boxes):
    """``{name: article title}`` for every ballot line that links one."""
    articles = {}
    for _, rows in _canonical(boxes):
        for row in rows:
            if row.get("article"):
                articles.setdefault(row["name"], row["article"])
    return articles


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


def ballot_labels(boxes):
    """``{name: line}`` as the November ballot spells a minor-party line.

    :func:`ballot_parties` folds a label into a key for comparison, which is
    the wrong form to show: "speak the truth" is "Speak The Truth" on the
    page. Only lines that are not a major party's are kept, and only from the
    general-election table or the infobox - a primary row is not a November
    line.
    """
    out = {}
    for raw_title, rows in _canonical(boxes):
        title = _clean_title(raw_title)
        if title != INFOBOX_TITLE and _stage(title) != "general":
            continue
        for row in rows:
            label = re.sub(r"\s*\([^()]*\)\s*$", "", row.get("party") or "").strip()
            if label and party_key(label) not in BALLOT_LABELS:
                out.setdefault(row["name"], label)
    return out


# Ballot "parties" that are not a line a voter sees.
_NOT_A_LINE = ("", "none", "all", "write-in", "n/a", "nan")
_SMALL_WORDS = {"a", "an", "and", "for", "in", "of", "on", "the", "to"}
LINE_LABELS = {"democratic": "Democratic", "republican": "Republican",
               "libertarian": "Libertarian", "green": "Green",
               "independent": "Independent"}


def _line_title(key):
    words = key.split()
    return " ".join(w if i and w in _SMALL_WORDS else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


def ballot_line(name, party, key, label=None):
    """The November line to show beside a nominee, or ``None``.

    Jose Vega (NY-15) lost the Democratic primary and is on the ballot on the
    "Speak The Truth" line; the roster still calls him a Democrat, which put
    two Democratic nominees side by side on the page. The line is shown, the
    party is never overwritten. Nothing is returned when the line is the
    person's own party's, is no line at all ("none", a write-in), or is the
    person's own name - New York's independent petitions name a line after
    the candidate (Karen Ortiz, NY-12), which is an independent nomination,
    not a party.
    """
    key = str(key or "").strip().lower()
    if key in _NOT_A_LINE:
        return None
    words, own = set(_tokens(key)), _tokens(name or "")
    if len(own) >= 2 and own[-1] in words and words <= set(own):
        key, label = "independent", None
    if key == party_key(party):
        return None
    if label and party_key(label) == key:
        return label
    return LINE_LABELS.get(key) or _line_title(key)


def coverage(boxes, open_primary=False, runoff_held=True):
    """What the page has actually decided, for people it does not name.

    ``{"general": bool, "parties": [keys]}`` - whether a general-election
    table exists, and which parties' primaries (or a nonpartisan primary,
    keyed ``"all"``) have a marked winner. Someone the page never mentions is
    only out of the race when the page has decided the contest they were in:
    a Democrat is not eliminated because the Republican table is complete.
    """
    if open_primary:
        # Louisiana's November table is a nonpartisan primary, read by the
        # same rules resolve_race applies to it.
        boxes = _open_rounds(boxes, runoff_held)
    general, parties = False, set()
    for raw_title, rows in boxes:
        title = _clean_title(raw_title)
        if title == INFOBOX_TITLE or title in LIST_TITLES:
            continue          # names people; decides nothing about the rest
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
    "abraham": ("abe",), "albert": ("al", "bert"), "alexander": ("alex", "al", "sandy", "xander"),
    "alexandra": ("alex", "lexy", "lexi", "sasha", "sandy"), "alexandria": ("alex", "lexi"),
    "alexis": ("lexi",), "alfred": ("al", "fred"), "andrew": ("andy", "drew"),
    "angela": ("angie",), "anthony": ("tony",), "arthur": ("art",), "augustus": ("gus",),
    "barbara": ("barb", "barbie"), "benjamin": ("ben", "benny", "benji"),
    "bernard": ("bernie", "berney", "bern"), "beverly": ("bev",), "bradley": ("brad",),
    "calvin": ("cal",), "cameron": ("cam",), "caroline": ("carrie",), "carolyn": ("carrie",),
    "catherine": ("cathy", "kate", "katie", "cat"), "charles": ("chuck", "charlie", "chas"),
    "charlotte": ("charlie", "lottie"), "christina": ("chris", "tina"),
    "christine": ("chris", "chrissy"), "christopher": ("chris", "kit"), "clifford": ("cliff",),
    "clinton": ("clint",), "cynthia": ("cindy",), "daniel": ("dan", "danny"),
    "danielle": ("dani",), "david": ("dave", "davey"), "deborah": ("debbie", "deb"),
    "debra": ("debbie", "deb"), "dennis": ("denny",), "dominic": ("dom",),
    "donald": ("don", "donnie"), "dorothy": ("dot", "dottie"), "douglas": ("doug",),
    "edmund": ("ed", "ned"), "edward": ("ed", "eddie", "ted", "ned"), "edwin": ("ed",),
    "eleanor": ("ellie", "nell"), "elinor": ("ellie",),
    "elizabeth": ("liz", "beth", "betsy", "eliza", "lisa", "libby", "betty"),
    "emanuel": ("manny",), "ernest": ("ernie",), "eugene": ("gene",), "ezekiel": ("zeke",),
    "frances": ("fran", "frankie"), "francis": ("frank",), "francisco": ("frank", "paco"),
    "franklin": ("frank",), "frederick": ("fred", "rick"), "gabriel": ("gabe",),
    "gabriela": ("gabby",), "gabriella": ("gabby",), "geoffrey": ("geoff", "jeff"),
    "gerald": ("jerry", "gerry"), "gerard": ("gerry",), "gilbert": ("gil",),
    "gregory": ("greg",), "gregorio": ("greg",), "harold": ("hal", "harry"),
    "harrison": ("harry",), "henry": ("hank", "harry"), "herbert": ("herb",),
    "howard": ("howie",), "irving": ("irv",), "isaac": ("ike",), "jacob": ("jake",),
    "jacqueline": ("jackie",), "james": ("jim", "jimmy", "jamie", "jay"), "janet": ("jan",),
    "janice": ("jan",), "jeffrey": ("jeff",), "jennifer": ("jen", "jenny", "jennie"),
    "jeremiah": ("jerry",), "jerome": ("jerry",), "jessica": ("jess", "jessie"),
    "joanne": ("jo",), "john": ("jack", "johnny", "jon"), "jonathan": ("jon", "jonny"),
    "joseph": ("joe", "joey"), "josephine": ("jo", "josie"), "joshua": ("josh",),
    "judith": ("judy",), "julius": ("jules",), "katherine": ("kathy", "kate", "katie", "kat"),
    "kathleen": ("kathy", "kate", "katie"), "kathryn": ("kathy", "kate", "katie"),
    "kenneth": ("ken", "kenny"), "kimberly": ("kim",), "lawrence": ("larry",),
    "leonard": ("len", "lenny", "leo"), "lester": ("les",), "louis": ("lou",),
    "louise": ("lou",), "lucille": ("lucy",), "madeline": ("maddie",), "malcolm": ("mal",),
    "manuel": ("manny",), "marcus": ("mark", "marc"), "margaret": ("peggy", "meg", "maggie", "marge"),
    "marjorie": ("margie",), "martha": ("marty",), "martin": ("marty",),
    "matthew": ("matt",), "maximilian": ("max",), "maxwell": ("max",), "melissa": ("mel", "missy"),
    "melvin": ("mel",), "michael": ("mike", "mikey", "mick"), "mitchell": ("mitch",),
    "montgomery": ("monty",), "nancy": ("nan",), "natalie": ("nat",), "nathan": ("nate",),
    "nathaniel": ("nate",), "nicholas": ("nick",), "nicole": ("nikki",), "norman": ("norm",),
    "oliver": ("ollie",), "pamela": ("pam",), "patricia": ("pat", "patty", "tricia", "trish"),
    "patrick": ("pat", "paddy"), "penelope": ("penny",), "peter": ("pete",),
    "philip": ("phil",), "phillip": ("phil",), "randall": ("randy",), "randolph": ("randy",),
    "raymond": ("ray",), "rebecca": ("becky", "becca"), "reginald": ("reggie",),
    "regina": ("gina",), "ricardo": ("rick",), "richard": ("rick", "dick", "rich", "richie", "ricky"),
    "robert": ("bob", "rob", "bobby", "robby", "robbie"), "roberta": ("bobbie",),
    "roderick": ("rod",), "rodney": ("rod",), "ronald": ("ron", "ronnie"),
    "rosemary": ("rosie",), "rudolph": ("rudy",), "russell": ("russ",),
    "salvatore": ("sal",), "samuel": ("sam", "sammy"), "sandra": ("sandy",),
    "sebastian": ("seb",), "sidney": ("sid",), "solomon": ("sol",), "stanley": ("stan",),
    "stephanie": ("steph",), "stephen": ("steve",), "steven": ("steve",),
    "susan": ("sue", "susie"), "suzanne": ("sue", "suzy", "suzie"), "tamara": ("tammy", "tamie"),
    "terrence": ("terry",),
    "terence": ("terry",), "theresa": ("terry", "tess"), "theodore": ("ted", "teddy"),
    "thaddeus": ("tad", "thad"), "thomas": ("tom", "tommy"), "timothy": ("tim",),
    "tobias": ("toby",), "valerie": ("val",), "vernon": ("vern",), "victor": ("vic",),
    "victoria": ("vicky", "tori"), "vincent": ("vince",), "virginia": ("ginny",),
    "wallace": ("wally",), "walter": ("walt",), "wesley": ("wes",),
    "william": ("bill", "will", "billy", "willie", "liam"), "woodrow": ("woody",),
    "zachary": ("zach", "zack"), "zachariah": ("zach",),
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
    text = text.replace("(", " ").replace(")", " ")     # "(RANDY)", "(J.D.)"
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
    # Only a bare initial on the ballot side counts: 'Ergin "Batman" Tek'
    # against "TEK, ERGIN AKA BATMAN" is not a conflict, and a quoted
    # nickname of two initials ('LaShonda "L.J." Holloway') is not a middle
    # name at all.
    if len(ballot) != 3 or len(filed) < 3 or len(ballot[1]) != 1 or len(ballot[0]) == 1:
        return False                      # "J.D. Ford" is two initials, not a middle
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

    senate_states = {row.get("state") for rows in by_race.values() for row in rows[:1]
                     if row.get("office") == "S"}
    dates, calendar_notes = effective_dates(dates, senate_states, log=log)

    races, pending, missing_pages, failed, unparsed = {}, [], [], [], []
    pages = {}

    def fetch_first(titles):
        """``(title, text)`` for the first title that exists, and whether a
        request failed on the way (rule 8: that is not evidence of absence)."""
        trouble = False
        for title in titles:
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
                return title, text, trouble
        return None, None, trouble

    for state, office in states:
        if not primary_settled(dates, state, office, today,
                               open_seat=open_primary(state, office)):
            pending.extend(rid for rid, rows in by_race.items()
                           if rows[0].get("state") == state and rows[0].get("office") == office)
            continue
        used, text, trouble = fetch_first(page_titles(state, office))
        if not text:
            (failed if trouble else missing_pages).append(f"{state}-{office}")
            continue
        if office == "S":
            pages[(state, office)] = {0: (used, text)}
            continue
        districts = {int(rid.split("-")[2]) for rid, rows in by_race.items()
                     if rows[0].get("state") == state and rows[0].get("office") == "H"}
        at_large = districts <= {0}
        sections = {n: (used, body) for n, body in house_sections(text, at_large).items()}
        # A page split into sub-articles hands its districts to them through
        # {{main|...}}: California's on 2026-09-20.
        for sub in sub_articles(text, used):
            sub_used, sub_text, sub_trouble = fetch_first([sub])
            if not sub_text:
                (failed if sub_trouble else missing_pages).append(f"{state}-{office}: {sub}")
                continue
            for n, body in house_sections(sub_text).items():
                sections.setdefault(n, (sub_used, body))
        if not sections:
            # Never fall back to reading the page as one at-large race: that
            # silently dropped every California seat.
            log(f"    [ERROR] {used!r} has no 'District N' sections for {state}'s "
                f"{len(districts)} seats; its results were not read")
            unparsed.append(f"{state}-{office}: {used}")
            continue
        pages[(state, office)] = sections

    for rid, rows in sorted(by_race.items()):
        state, office = rows[0].get("state"), rows[0].get("office")
        if (state, office) not in pages:
            continue
        key = int(rid.split("-")[2]) if office == "H" else 0
        title, section = pages[(state, office)].get(key, (None, None))
        if not section:
            continue
        slot = dates.get((state, office)) or {}
        is_open = open_primary(state, office)
        boxes = parse_boxes(section)
        nominees = infobox_nominees(section)
        if nominees:
            boxes.append((INFOBOX_TITLE, nominees))
        boxes.extend(candidate_lists(section))
        held = runoff_held(dates, state, office, today)
        outcome = resolve_race(boxes, has_runoff=bool(slot.get("runoff")),
                               open_primary=is_open, runoff_held=held)
        if not outcome:
            if is_open and any(r.get("won") for _, rs in boxes for r in rs):
                # Winners are marked, but not as a result the open-primary
                # rules allow (the top two, or one with a majority of the
                # counted vote). Left unread, and said so.
                log(f"    [warn] {rid}: the page marks winners that are not a "
                    f"complete open-primary result; left unsettled")
            continue
        matched, ambiguous = match_names(list(outcome), rows, (aliases or {}).get(rid))
        status, party, article, label = {}, {}, {}, {}
        listed = ballot_parties(boxes)
        linked = ballot_articles(boxes)
        spelled = ballot_labels(boxes)
        for name, cids in matched.items():
            for cid in cids:
                status[cid] = outcome[name]
                if listed.get(name):
                    party[cid] = listed[name]
                if linked.get(name):
                    article[cid] = linked[name]
                if spelled.get(name):
                    label[cid] = spelled[name]
        races[rid] = {
            "page": title,
            "status": status,
            "party": party,
            # A minor-party November line as the page spells it, per filing.
            "label": label,
            # The article the ballot line links to, per filing.
            "article": article,
            # Ids a Wikipedia name fitted but could not be told apart. No
            # status, and no inference from their absence either.
            "unsure": match_names.unsure,
            # Named on the page but matching no filing. Their status is kept:
            # a nominee with no FEC filing over $5,000 is still on the ballot,
            # and a race header that omits them is wrong.
            "unmatched": {name: outcome[name] for name in sorted(set(outcome) - set(matched))},
            "ambiguous": ambiguous,
            "decided": coverage(boxes, open_primary=is_open, runoff_held=held),
        }

    log(f"    settled races with results: {len(races)}   "
        f"pending primaries: {len(pending)}   pages missing: {len(missing_pages)}   "
        f"fetches failed: {len(failed)}   unparsed: {len(unparsed)}")
    return {
        "asOf": today.isoformat(),
        "cycle": CYCLE,
        "races": races,
        "pending": sorted(pending),
        "missingPages": sorted(missing_pages),
        "fetchFailed": sorted(failed),
        # Pages that exist but whose districts could not be found. Every
        # race on them is unread, so validate makes this an error.
        "unparsedPages": sorted(unparsed),
        # Every place the calendar above is not the FEC's, and why.
        "calendarNotes": calendar_notes,
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
    if cache.get("races") is None:
        return None
    return respect_open_primaries(cache)


def respect_open_primaries(cache):
    """Withdraw results a cache holds for an open-primary seat not yet decided.

    A cache written before ``OPEN_PRIMARY_SEATS`` existed read Louisiana's
    vote-less November boxes as a ballot of nominees. The seat's first round
    is that November election, so as of the cache's own date nothing about
    it was settled; its races go back to pending rather than being shown.
    """
    from .overrides import OPEN_PRIMARY_SEATS

    as_of = cache.get("asOf")
    try:
        day = datetime.date.fromisoformat(as_of) if as_of else None
    except ValueError:
        day = None
    for (state, office, cycle), fixed in OPEN_PRIMARY_SEATS.items():
        if cycle != cache.get("cycle", CYCLE):
            continue
        slot = {"primary": fixed["primary"], "runoff": fixed.get("runoff")}
        # Results for the seat are kept only from a run that used this
        # calendar - it travels with the cache - and only once its first
        # round had happened by that run's date.
        built_with = (cache.get("dates") or {}).get(f"{state}-{office}")
        if (day and built_with == slot
                and primary_settled({(state, office): slot}, state, office, day,
                                    open_seat=True)):
            continue
        prefix = f"{office}-{state}-"
        stale = [rid for rid in cache["races"] if rid.startswith(prefix)]
        for rid in stale:
            del cache["races"][rid]
        if stale:
            cache["pending"] = sorted(set(cache.get("pending") or []) | set(stale))
        if f"{state}-{office}" in (cache.get("dates") or {}):
            cache["dates"][f"{state}-{office}"] = slot
    return cache


def load_dates(root="."):
    """The calendar as cached by the last ``results`` run, overrides applied."""
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
    by_id, party_of, article_of, label_of, unsure = {}, {}, {}, {}, set()
    races = cache.get("races", {})
    for rid, race in races.items():
        for cid, status in race.get("status", {}).items():
            by_id[cid] = (rid, status)
        party_of.update(race.get("party") or {})
        article_of.update(race.get("article") or {})
        label_of.update(race.get("label") or {})
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
            if candidate_id in article_of and not profile.get("wikipedia"):
                # A member's title comes from the bioguide mapping; for a
                # filed candidate the ballot's own link is the authority.
                profile["wikipedia"] = article_of[candidate_id]
                profile["wikipediaVia"] = "election-page"
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
            if status == NOMINEE:
                # Shown beside "On the November ballot"; never a new party.
                line = ballot_line(profile.get("name"), profile.get("party"),
                                   party_of.get(candidate_id), label_of.get(candidate_id))
                if line:
                    profile["ballotLine"] = line
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
