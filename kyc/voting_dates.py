"""Each jurisdiction's key dates for the November 3, 2026 election.

Seventeen days out, every state page offered "Register to vote" with no
word that most states' deadlines had passed, gave no early-voting or
mail-ballot date, and left Georgia's December 1 runoff and Louisiana's
December 12 House round off the voting block (audit 2026-10-17,
STATEGOV-11, PERSONA-03, FRESHNESS-11, VISUALS-25). ``kyc/voting.py``
deliberately typed no date, because a date typed from memory drifts.

So the dates are a hand-editable cache, ``data/voting_dates.json``, read
jurisdiction by jurisdiction from each election office's own pages,
calendars and statutes on 2026-10-17, and every value re-opened at its
source by a second researcher (``verified``). Each value the page shows
carries, in ``sources``, the official page's address and its words. A null
is a gap, never a guess, and the page says nothing where the record is
null: the state's own links stay beside it.

``check`` holds the cache to that:

- a value the page shows needs a source entry for its own field (a
  qualifier - a time of day, "postmarked", where same-day registration
  happens - may stand on its value's source), on the jurisdiction's own
  domains (``JURISDICTION_DOMAINS``) or an evidenced page elsewhere
  (``OFFICIAL_ELSEWHERE``): any .gov host is not enough, since another
  state's office, a county and a federal guide are all on .gov;
- "postmarked" and "received" must be said in a quote they stand on
  (``RULE_WORDS``), and where same-day registration happens is the office's
  own words, quoted (``where_problems``);
- a compiled table is a lead, never a source (rule 50): NCSL, Ballotpedia,
  Wikipedia, vote.gov, Vote.org and the like are refused wherever they
  appear;
- every date parses and falls in the cycle, windows run forwards, and no
  deadline falls after the election it is for;
- a December date the results reader also holds (``overrides.GENERAL_RUNOFFS``,
  ``OPEN_PRIMARY_SEATS``) must be the same date here (rule 53).

``for_page`` turns a record into the lines the page shows, in words, each
with its links; the page decides only what the reader's own calendar day
makes of each date (upcoming, today, passed), as ``KYC.electionStatus``
does. The researchers' notes stay in the cache for the next editor and are
never shown: they are a researcher's words, not the office's.
"""

import datetime
import json
import os
import re
import urllib.parse

from .normalize import US_STATES

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "voting_dates.json")
ELECTION = "2026-11-03"
# Every date in the record falls between these: the cycle's registration
# windows open in the summer, and the last ballot counted arrives in
# December.
EARLIEST, LATEST = "2026-06-01", "2026-12-31"

# Every jurisdiction with a state page: the fifty states, D.C. and the five
# territories.
JURISDICTIONS = frozenset(US_STATES.values())

# Compiled tables, and directories of other people's pages: leads, never
# the cited source (rule 50). vote.gov is a .gov site, so it is refused by
# name before any domain test could accept it.
COMPILED_HOSTS = ("ncsl.org", "ballotpedia.org", "wikipedia.org", "vote.gov", "vote.org",
                  "usvotefoundation.org", "canivote.org", "nass.org", "eac.gov",
                  "votinginfoproject.org", "rockthevote.org", "headcount.org",
                  # The federal government's state-by-state guides: fvap.gov's
                  # for voters abroad, usa.gov's for everyone.
                  "fvap.gov", "usa.gov")

# Official pages on a domain that is not the jurisdiction's own, each by its
# address and with what makes it the jurisdiction's: {url prefix: (codes,
# label, evidence)}. A county's page or a federal one counts only here,
# for the jurisdictions listed: being on .gov makes a page a government's,
# not this jurisdiction's (PR #102 review: sos.ga.gov passed for Florida).
OFFICIAL_ELSEWHERE = {
    "https://drive.google.com/file/d/1h6Rb8t-XaocN-TfM7Q2CVHgExEXO2ARS/": (
        ("AS",), "American Samoa Election Office's 2026 calendar",
        "the calendar embedded on https://www.aselectionoffice.gov/calendar"),
    "https://drive.google.com/file/d/1KsY2DpP753FVksT3Yg_EF6JI476E9hdI/": (
        ("AS",), "American Samoa Election Office's absentee ballot form",
        "ASG Form EO-08, linked from https://www.aselectionoffice.gov/absentee-voting"),
    "https://docs.google.com/forms/d/e/1FAIpQLSeH9yVWrIrhA2dcHdCrF-a0g2c8qFBpCZe5CwxA2Kch-ZAwpw/": (
        ("GU",), "Guam Election Commission's online registration form",
        "embedded on the Commission's 'Register online' page, https://gec.guam.gov/register/"),
    # Title 48 of the U.S. Code is the territories' organic law: Guam's
    # Organic Act sets its governor's runoff (48 U.S.C. 1422), and chapter
    # 16 its Delegate's and American Samoa's (48 U.S.C. 1712, 1731).
    "https://www.govinfo.gov/content/pkg/USCODE-2024-title48/": (
        ("AS", "GU"), "govinfo.gov (48 U.S.C.)",
        "the Code as the Government Publishing Office publishes it; Title 48 governs elections "
        "in the territories"),
    # The Court's opinion on counting mail ballots that arrive after
    # Election Day, cited only in the researchers' notes, never shown.
    "https://www.supremecourt.gov/opinions/25pdf/24-1260_": (
        ("AK", "CA"), "supremecourt.gov",
        "the Supreme Court's slip opinion on counting mail ballots received after Election Day"),
}

# Each jurisdiction's own government domains: its election office's, its
# legislature's and its general state domain. A host counts for a
# jurisdiction only when it is one of these or under one (a state.<xx>.us
# host counts for <xx>), or is listed in voting.OFFICIAL_HOSTS for it.
JURISDICTION_DOMAINS = {
    "AK": ("alaska.gov",), "AL": ("alabama.gov", "alabamavotes.gov"),
    "AR": ("arkansas.gov",), "AS": ("aselectionoffice.gov", "americansamoa.gov"),
    "AZ": ("azsos.gov", "azleg.gov", "az.gov"), "CA": ("ca.gov",),
    "CO": ("coloradosos.gov", "colorado.gov"), "CT": ("ct.gov",), "DC": ("dc.gov",),
    "DE": ("delaware.gov",), "FL": ("fl.gov", "registertovoteflorida.gov", "flsenate.gov"),
    "GA": ("ga.gov", "georgia.gov"), "GU": ("guam.gov", "guamcourts.gov"),
    "HI": ("hawaii.gov",), "IA": ("iowa.gov",), "ID": ("idaho.gov", "voteidaho.gov"),
    "IL": ("il.gov", "illinois.gov", "ilga.gov"), "IN": ("in.gov",),
    "KS": ("ks.gov", "ksrevisor.gov", "kssos.org"), "KY": ("ky.gov",), "LA": ("la.gov",),
    "MA": ("mass.gov", "malegislature.gov"), "MD": ("maryland.gov",), "ME": ("maine.gov",),
    "MI": ("michigan.gov",), "MN": ("mn.gov",), "MO": ("mo.gov",), "MP": ("gov.mp",),
    "MS": ("ms.gov",), "MT": ("mt.gov", "votemt.gov", "sosmt.gov", "legmt.gov"),
    "NC": ("nc.gov", "ncsbe.gov", "ncleg.gov"), "ND": ("nd.gov",), "NE": ("nebraska.gov",),
    "NH": ("nh.gov",), "NJ": ("nj.gov",), "NM": ("nm.gov", "nmlegis.gov"), "NV": ("nv.gov",),
    "NY": ("ny.gov",), "OH": ("ohiosos.gov", "ohio.gov"), "OK": ("oklahoma.gov", "ok.gov"),
    "OR": ("oregon.gov", "oregonlegislature.gov"), "PA": ("pa.gov",), "PR": ("pr.gov",),
    "RI": ("ri.gov",), "SC": ("sc.gov", "scvotes.gov", "scstatehouse.gov"),
    "SD": ("sd.gov", "sdsos.gov", "sdlegislature.gov"), "TN": ("tn.gov",),
    "TX": ("texas.gov", "votetexas.gov"), "UT": ("utah.gov",), "VA": ("virginia.gov",),
    "VI": ("vivote.gov", "vi.gov"), "VT": ("vermont.gov",), "WA": ("wa.gov",),
    "WI": ("wi.gov", "wisconsin.gov"), "WV": ("wv.gov",), "WY": ("wyo.gov", "wyoming.gov"),
}

# A value the page shows, and the source fields that may stand for it: a
# qualifier stands on its value's source; everything else needs its own.
SHOWN = {
    "noElection": (),
    "registration.none": (),
    "registration.online.deadline": (),
    "registration.online.time": ("registration.online.deadline",),
    "registration.mail.deadline": (),
    "registration.mail.rule": ("registration.mail.deadline",),
    "registration.inPerson.deadline": (),
    # The last day a new registrant is still mailed a ballot, where
    # registration itself runs on (Nevada's online registration runs
    # through Election Day; from the fourteenth day before, a new
    # registrant votes in person).
    "registration.mailedBallotBy": (),
    "registration.sameDay.available": (),
    # The office's own words, quoted (``where_problems``), never a summary.
    "registration.sameDay.where": ("registration.sameDay.available",),
    # The last day same-day registration is offered, where it ends before
    # Election Day (North Carolina's is at early-voting sites only).
    "registration.sameDay.through": (),
    "earlyVoting.start": (),
    "earlyVoting.end": (),
    # Each local office sets its own days within the window (Wisconsin's
    # "possibly through November 1").
    "earlyVoting.setLocally": (),
    "mail.allMail": (),
    # Where every voter is mailed a ballot, nobody needs an excuse.
    "mail.noExcuse": ("mail.allMail",),
    "mail.requestDeadline.date": (),
    "mail.requestDeadline.rule": ("mail.requestDeadline.date",),
    "mail.returnDeadline.date": (),
    "mail.returnDeadline.time": ("mail.returnDeadline.date",),
    "mail.returnDeadline.rule": ("mail.returnDeadline.date", "mail.returnDeadline.receivedBy"),
    "mail.returnDeadline.receivedBy": (),
    "runoff.date": (),
}
# Flags shown only when true: false says nothing on the page.
SHOWN_WHEN_TRUE = {"noElection", "registration.none", "registration.sameDay.available",
                   "mail.allMail", "earlyVoting.setLocally"}

# "Postmarked by then" and "must arrive by then" are claims of their own:
# each must be said in a quote the value stands on (its own source or a
# stand-in's), not merely beside a date (PR #102 review: South Dakota's
# "received" stood on a quote that said only the date).
RULE_WORDS = {
    "postmarked": re.compile(r"postmark", re.I),
    "received": re.compile(r"receiv|receipt|arriv|\breach|in the hands of|in (?:the )?possession"
                           r"|deliver(?:y|ed) to", re.I),
}
RULES = ("registration.mail.rule", "mail.requestDeadline.rule", "mail.returnDeadline.rule")

# What a runoff in the record decides, in words the page shows beside its
# date, each from the record's runoff source and note: Arkansas's and
# Mississippi's December 1 are not runoffs for Congress, and a line that
# said only "Runoff" would read as one. {code: (before, after the date)}.
# Georgia's and Louisiana's words are those the page used since #94.
RUNOFF_WORDS = {
    "AR": ("Runoff, if one is needed, for county and municipal offices (and, after a tie, "
           "certain state or township offices); not for federal offices",
           "The date set for runoffs for county and municipal offices"),
    "GA": ("If no candidate for an office wins a majority of the votes on November 3, the top "
           "two meet in a runoff on this date",
           "The date set for a runoff in any race no candidate won with a majority of the "
           "votes on November 3"),
    "GU": ("Runoff between the top two, if no ticket for Governor and Lieutenant Governor or no "
           "candidate for Delegate wins a majority: the fourteenth day after the election, "
           "as federal law sets it",
           "The date set for any runoff for Governor and Lieutenant Governor or for Delegate"),
    "LA": ("The U.S. House vote on November 3 is an open primary; a seat no candidate wins "
           "with a majority is decided at a general election on this date",
           "The date set for a general election for any U.S. House seat no candidate won "
           "with a majority in the November 3 open primary"),
    "MS": ("Runoff, if one is needed, for judges and school board members only",
           "The date set for runoffs for judges and school board members"),
    "VI": ("Runoff, if one is needed, for Governor and Lieutenant Governor or for Delegate",
           "The date set for any runoff for Governor and Lieutenant Governor or for Delegate"),
}
# The calendar strip's labels for a runoff, before and after its date: a
# strip that said only "Runoff, if needed" over Mississippi's judges'
# runoff read as a runoff for Congress (PR #102 review).
RUNOFF_SHORT = {
    "AR": ("Local runoff, if needed", "Local runoff date"),
    "LA": ("House general, if needed", "House general date"),
    "MS": ("Judicial, school board runoff, if needed", "Judicial, school board runoff date"),
}
RUNOFF_SHORT_DEFAULT = ("Runoff, if needed", "Runoff date")

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A time of day as the record gives it; anything longer ("7:00 pm (postmark);
# received by 5:00 pm November 4") is not shown, the dates saying it.
_TIME = re.compile(r"^(\d{1,2}:\d{2} [ap]m)(?: \(noon\))?$")


class VotingDatesError(RuntimeError):
    """The cache breaks its rules."""


def load(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def get(record, path):
    for part in path.split("."):
        if not isinstance(record, dict):
            return None
        record = record.get(part)
    return record


def _host(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def _unarchived(url):
    """An Internet Archive capture's original address, else None."""
    m = re.match(r"^https?://web\.archive\.org/web/(\d{8,14})[a-z_]*/(https?://.+)$", url)
    return (m.group(2), m.group(1)) if m else None


def compiled(url):
    """Is *url* (or the page an archive captured) a compiled table?"""
    inner = _unarchived(url)
    host = _host(inner[0] if inner else url)
    return any(host == h or host.endswith("." + h) for h in COMPILED_HOSTS)


def official_source(url, code):
    """``(True, label)`` when *url* is *code*'s own official page, else
    ``(False, why)``. A capture in the Internet Archive counts as the page it
    captured (Guam's Election Commission refused connections on 2026-10-17)."""
    from . import voting

    if not re.match(r"^https?://", str(url or "")):
        return False, "not a web address"
    if compiled(url):
        return False, "a compiled table, a lead and never a source (rule 50)"
    inner = _unarchived(url)
    if inner:
        ok, label = official_source(inner[0], code)
        stamp = inner[1]
        return ok, (f"{label} (archived {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]})" if ok else label)
    for prefix, (owners, label, _evidence) in OFFICIAL_ELSEWHERE.items():
        if url.startswith(prefix):
            return (code in owners), (label if code in owners
                                      else f"{'/'.join(owners)}'s page, not {code}'s")
    host = _host(url)
    label = host[4:] if host.startswith("www.") else host
    state = re.search(r"\.state\.([a-z]{2})\.us$", host)
    if state:
        return (state.group(1) == code.lower()), label
    domains = list(JURISDICTION_DOMAINS.get(code, ())) + [
        d for d, owner in voting.OFFICIAL_HOSTS.items() if owner == code]
    if any(host == d or host.endswith("." + d) for d in domains):
        return True, label
    return False, f"{host} is not {code}'s own domain"


def _sources(record, field):
    return [s for s in record.get("sources") or [] if s.get("field") == field]


def _shown(record, path):
    value = get(record, path)
    if value in (None, ""):
        return None
    if path in SHOWN_WHEN_TRUE and value is not True:
        return None
    return value


def problems(data, runoffs=None):
    """Every way *data* breaks the cache's rules, as strings."""
    if runoffs is None:
        runoffs = override_runoffs()
    states = (data or {}).get("states") or {}
    out = [f"{code}: no record" for code in sorted(JURISDICTIONS - set(states))]
    out += [f"{code}: not a jurisdiction" for code in sorted(set(states) - JURISDICTIONS)]
    for code, record in sorted(states.items()):
        out += state_problems(code, record, runoffs)
    return out


def state_problems(code, record, runoffs):
    """What is wrong with one jurisdiction's record, as strings."""
    out = []
    if record.get("election") != ELECTION:
        out.append(f"{code}: election {record.get('election')!r}, not {ELECTION}")
    for source in record.get("sources") or []:
        ok, why = official_source(source.get("url"), code)
        if not ok:
            out.append(f"{code} {source.get('field')}: {source.get('url')} - {why}")
        if not str(source.get("quote") or "").strip():
            out.append(f"{code} {source.get('field')}: a source with no quote")
    fields = {s.get("field") for s in record.get("sources") or []}
    for path, stand_ins in SHOWN.items():
        if _shown(record, path) is None:
            continue
        if path not in fields and not fields & set(stand_ins):
            out.append(f"{code} {path}: shown with no source")
    for path in RULES:
        rule = get(record, path)
        if rule is None:
            continue
        if rule not in RULE_WORDS:
            out.append(f"{code} {path}: {rule!r} is neither 'postmarked' nor 'received'")
            continue
        quotes = [s.get("quote") or "" for s in record.get("sources") or []
                  if s.get("field") in (path,) + SHOWN[path]]
        if not any(RULE_WORDS[rule].search(q) for q in quotes):
            out.append(f"{code} {path}: {rule!r}, but no quote it stands on says so")
    out += where_problems(code, record)
    out += _date_problems(code, record)
    date = get(record, "runoff.date")
    if date and code not in RUNOFF_WORDS:
        out.append(f"{code}: a runoff on {date} with no RUNOFF_WORDS saying what it decides")
    if not date and code in RUNOFF_WORDS:
        out.append(f"{code}: RUNOFF_WORDS for a runoff the record does not hold")
    if code in runoffs and runoffs[code] != date:
        out.append(f"{code}: the overrides hold a December date of {runoffs[code]}, the record "
                   f"{date}; two sources of one date must agree (rule 53)")
    return out


def _plain(text):
    """Text compared as words: case, spacing, curly quotes and dashes aside."""
    text = str(text or "").translate({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',
                                      0x2013: "-", 0x2014: "-", 0xA0: " "})
    return re.sub(r"\s+", " ", text).strip().lower()


def where_excerpts(where):
    """The office's words a ``sameDay.where`` quotes: excerpts joined by " ... "."""
    return [part.strip() for part in str(where or "").split(" ... ") if part.strip()]


def _where_sources(record):
    return [s for s in record.get("sources") or []
            if s.get("field") in ("registration.sameDay.where", "registration.sameDay.available")]


def where_problems(code, record):
    """Where same-day registration happens is shown in the office's words:
    each excerpt of ``where`` must be in a quote of a same-day source. The
    first record held a researcher's summary there, and the page showed it
    (PR #102 review)."""
    where = _shown(record, "registration.sameDay.where")
    if not where:
        return []
    quotes = [_plain(s.get("quote")) for s in _where_sources(record)]
    return [f"{code} registration.sameDay.where: {part!r} is not in the office's words quoted "
            f"for same-day registration" for part in where_excerpts(where)
            if not any(_plain(part) in q for q in quotes)]


def _date_problems(code, record):
    out = []

    def day(path):
        value = get(record, path)
        if value is None:
            return None
        if not (isinstance(value, str) and _DATE.match(value)):
            out.append(f"{code} {path}: {value!r} is not a date")
            return None
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            out.append(f"{code} {path}: {value!r} is not a date")
            return None
        if not EARLIEST <= value <= LATEST:
            out.append(f"{code} {path}: {value} is outside the cycle")
        return value

    for path in ("registration.online.deadline", "registration.mail.deadline",
                 "registration.inPerson.deadline", "registration.mailedBallotBy",
                 "registration.sameDay.through", "mail.requestDeadline.date"):
        value = day(path)
        if value and value > ELECTION:
            out.append(f"{code} {path}: {value} is after the election")
    start, end = day("earlyVoting.start"), day("earlyVoting.end")
    if (start is None) != (end is None):
        out.append(f"{code} earlyVoting: a window with one end")
    elif start and not start <= end <= ELECTION:
        out.append(f"{code} earlyVoting: {start} to {end} does not run forwards to the election")
    returned, received = day("mail.returnDeadline.date"), day("mail.returnDeadline.receivedBy")
    if returned and returned > ELECTION:
        out.append(f"{code} mail.returnDeadline.date: {returned} is after the election")
    if returned and received and received < returned:
        out.append(f"{code} mail.returnDeadline: received by {received}, before {returned}")
    if get(record, "mail.returnDeadline.rule") == "postmarked" and received == returned:
        # A postmark deadline whose ballots must also arrive that day is a
        # receipt deadline; the page would promise days that do not exist.
        out.append(f"{code} mail.returnDeadline: postmarked, yet received the same day")
    runoff = day("runoff.date")
    if runoff and runoff <= ELECTION:
        out.append(f"{code} runoff.date: {runoff} is not after the election")
    if get(record, "registration.online.deadline") and get(
            record, "registration.online.available") is not True:
        out.append(f"{code} registration.online: a deadline for registration not offered online")
    if get(record, "registration.sameDay.through") and get(
            record, "registration.sameDay.available") is not True:
        out.append(f"{code} registration.sameDay.through: an end to same-day registration not offered")
    return out


def override_runoffs():
    """The December dates the results reader holds: {code: date}."""
    from .overrides import GENERAL_RUNOFFS, OPEN_PRIMARY_SEATS

    out = {code: date for code, (date, _evidence) in GENERAL_RUNOFFS.items()}
    for (code, _office, _cycle), seat in OPEN_PRIMARY_SEATS.items():
        if seat.get("runoff"):
            out[code] = seat["runoff"]
    return out


def check(data, runoffs=None):
    found = problems(data, runoffs)
    if found:
        raise VotingDatesError("; ".join(found))


# ------------------------------------------------------------------ the page

def _time(value):
    m = _TIME.match(str(value or ""))
    return m.group(1) if m else None


def _join(words):
    words = [w for w in words if w]
    return words[0] if len(words) < 2 else ", ".join(words[:-1]) + " or " + words[-1]


class _Links:
    """A record's source addresses, numbered once each for the page."""

    def __init__(self, code, record):
        self.code, self.record, self.urls, self.labels = code, record, [], []

    def of(self, *fields, want=None):
        out = []
        for field in fields:
            for source in _sources(self.record, field):
                if want is not None and not want(source):
                    continue
                url = source["url"]
                ok, label = official_source(url, self.code)
                if not ok:
                    continue
                if url not in self.urls:
                    self.urls.append(url)
                    self.labels.append(label)
                index = self.urls.index(url)
                # One link per label: two pages of one office read as one
                # site twice.
                if index not in out and all(self.labels[i] != label for i in out):
                    out.append(index)
            if out:
                break
        return out


def lines(code, record, place):
    """The page's lines for one record: ``(lines, register, links)``.

    Each line is ``{"k": kind, "d": date, "e"?: end of a window, "t": words,
    "p"?: words once the date has passed, "s": a short label for the
    calendar, "src": [link numbers], "keep"?: still shown after Election
    Day}``; a line with no date is a standing fact. ``register`` is when
    registration for November 3 closes, for the page's lead sentence and the
    "Register to vote" button; ``links`` numbers the sources the lines cite.
    """
    links = _Links(code, record)
    out = []
    if _shown(record, "noElection"):
        out.append({"k": "none", "t": f"No election is held in {place} on November 3, 2026",
                    "src": links.of("noElection")})
        return out, None, links

    reg = record.get("registration") or {}
    if _shown(record, "registration.none"):
        out.append({"k": "noreg", "t": f"{place[:1].upper() + place[1:]} has no voter registration",
                    "src": links.of("registration.none")})
    by_date = {}
    online = _shown(record, "registration.online.deadline")
    if online:
        time = _time(get(record, "registration.online.time"))
        by_date.setdefault(online, []).append(
            ("online", "online" + (f" (until {time})" if time else ""),
             "registration.online.deadline"))
    mailed = _shown(record, "registration.mail.deadline")
    if mailed:
        rule = get(record, "registration.mail.rule")
        by_date.setdefault(mailed, []).append(
            ("mail", "by mail" + {"postmarked": " (postmarked by then)",
                                  "received": " (the form must arrive by then)"}.get(rule, ""),
             "registration.mail.deadline"))
    person = _shown(record, "registration.inPerson.deadline")
    if person:
        by_date.setdefault(person, []).append(("in person", "in person",
                                               "registration.inPerson.deadline"))
    # Whether a reader who misses a deadline can still register and vote at
    # once: True, False, or None where the record does not say. In a
    # same-day state a deadline before Election Day is the *regular*
    # deadline, never the last chance: the first page told Illinois readers
    # "Today is the last day to register" on a day grace-period
    # registration ran on to November 3 (PR #102 review).
    same = True if _shown(record, "registration.sameDay.available") else (
        False if get(reg, "sameDay.available") is False else None)
    every = len(by_date) == 1 and len(next(iter(by_date.values()))) == 3
    for date, methods in sorted(by_date.items()):
        how = _join([m[1] for m in methods])
        short = " / ".join(m[0] if m[0] != "mail" else "by mail" for m in methods)
        if same and date < ELECTION:
            words = (f"Regular deadline to register {how}; after it you can still register "
                     f"and vote at the same time (below)")
            label = "Regular deadline to register" + ("" if every else f": {short}")
        elif same is None:
            words = f"Deadline to register to vote {how}"
            label = "Registration deadline" if every else f"Register {short}"
        else:
            words = f"Last day to register to vote {how}"
            label = "Registration closes" if every else f"Register {short}"
        out.append({"k": "register", "d": date, "t": words, "s": label,
                    "src": links.of(*[m[2] for m in methods])})
    mailed_by = _shown(record, "registration.mailedBallotBy")
    if mailed_by:
        out.append({"k": "mailreg", "d": mailed_by,
                    "t": "Last day to register and still be mailed a ballot; a voter who "
                         "registers after it votes in person",
                    "s": "Register to be mailed a ballot",
                    "src": links.of("registration.mailedBallotBy")})
    register = None
    if by_date:
        last = max(by_date)
        register = {"by": last, "how": _join([m[0] if m[0] != "mail" else "by mail"
                                              for m in by_date[last]])}
    if same:
        where = _shown(record, "registration.sameDay.where")
        excerpts = where_excerpts(where)
        through = _shown(record, "registration.sameDay.through")
        # The office's own words, quoted; never a summary of them.
        quote = ("; in the office's words, " + " … ".join(
            f"“{part.rstrip('.')}”" for part in excerpts)) if excerpts else ""
        line = {"k": "sameday",
                "t": "Same-day registration: you can register and vote at the same time" +
                     (", until this day" if through else "") + quote}
        if through:
            line.update({"d": through, "s": "Same-day registration ends",
                         "p": "Same-day registration ended on this day" + quote})
        quoted = [_plain(p) for p in excerpts]
        line["src"] = links.of(
            "registration.sameDay.where", "registration.sameDay.available",
            want=(lambda s: any(p in _plain(s.get("quote")) for p in quoted)) if quoted else None)
        out.append(line)
        register = dict(register or {}, sameDay=True)
        if through:
            register["through"] = through
    elif register is not None and same is False:
        register["sameDay"] = False

    start, end = _shown(record, "earlyVoting.start"), _shown(record, "earlyVoting.end")
    if start and end:
        # Wisconsin's window is the earliest and latest a municipal clerk may
        # offer, not days every clerk is open (PR #102 review).
        local = _shown(record, "earlyVoting.setLocally")
        out.append({"k": "early", "d": start, "e": end,
                    "t": "In-person early voting" + (
                        ", on the days and hours each local election office sets: it may start "
                        "later or end sooner than these dates" if local else ""),
                    "s": "Early voting" + (" (local days)" if local else ""),
                    "src": links.of("earlyVoting.start", "earlyVoting.end")
                    + (links.of("earlyVoting.setLocally") if local else [])})

    if _shown(record, "mail.allMail"):
        out.append({"k": "allmail", "t": "Every registered voter is mailed a ballot without "
                                         "asking for one",
                    "src": links.of("mail.allMail")})
    elif _shown(record, "mail.noExcuse") is True:
        out.append({"k": "excuse", "t": "Any voter may vote by mail; no reason is needed",
                    "src": links.of("mail.noExcuse")})
    elif _shown(record, "mail.noExcuse") is False:
        out.append({"k": "excuse", "t": "Voting by mail is open only to voters with a reason "
                                        "the law accepts",
                    "src": links.of("mail.noExcuse")})
    request = _shown(record, "mail.requestDeadline.date")
    if request:
        received = get(record, "mail.requestDeadline.rule") == "received"
        out.append({"k": "request", "d": request,
                    "t": "Last day to apply for a mail ballot" +
                         (" (the application must arrive by then)" if received else ""),
                    "s": "Mail ballot application due",
                    "src": links.of("mail.requestDeadline.date")})
    returned = _shown(record, "mail.returnDeadline.date")
    received = _shown(record, "mail.returnDeadline.receivedBy")
    time = _time(get(record, "mail.returnDeadline.time"))
    if get(record, "mail.returnDeadline.rule") == "postmarked" and returned:
        out.append({"k": "postmark", "d": returned,
                    "t": "Mail ballots must be postmarked by this day",
                    "s": "Postmark deadline",
                    "src": links.of("mail.returnDeadline.date", "mail.returnDeadline.rule")})
        if received:
            out.append({"k": "arrive", "d": received, "keep": True,
                        "t": f"Mail ballots postmarked by {_long(returned)} are counted if they "
                             f"arrive by this day",
                        "p": f"The last day for mail ballots postmarked by {_long(returned)} to "
                             f"arrive",
                        "s": "Mailed ballots arrive by",
                        "src": links.of("mail.returnDeadline.receivedBy")})
    elif get(record, "mail.returnDeadline.rule") == "received" and (returned or received):
        due = returned or received
        line = {"k": "return", "d": due,
                "t": "Mail ballots must arrive at the election office by " +
                     (time + " on " if time else "") + "this day",
                "s": "Mail ballots due",
                "src": links.of("mail.returnDeadline.date" if returned
                                else "mail.returnDeadline.receivedBy",
                                "mail.returnDeadline.receivedBy")}
        if due > ELECTION:
            # Ballots still arriving after Election Day are still news then
            # (the Virgin Islands count those received by November 13).
            line.update({"keep": True,
                         "p": "The last day for mail ballots to arrive at the election office"})
        out.append(line)

    runoff = _shown(record, "runoff.date")
    if runoff and code in RUNOFF_WORDS:
        before, after = RUNOFF_WORDS[code]
        short, short_past = RUNOFF_SHORT.get(code, RUNOFF_SHORT_DEFAULT)
        out.append({"k": "runoff", "d": runoff, "t": before, "p": after, "keep": True,
                    "s": short, "sp": short_past, "src": links.of("runoff.date")})
    return out, register, links


_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")


def _long(iso):
    year, month, day = (int(x) for x in iso.split("-"))
    return f"{_MONTHS[month - 1]} {day}"


# A place's own name where its short name is not one (rule 75).
PLACES = {"DC": "the District of Columbia", "MP": "the Northern Mariana Islands",
          "VI": "the U.S. Virgin Islands"}


def place(code):
    from .pages import state_name
    return PLACES.get(code) or state_name(code)


def for_page(data, runoffs=None):
    """The build meta's ``voting._dates``: ``{"states": {code: {"lines",
    "urls", "labels", "register"?}}, ...}``, with when the record was read and
    checked. A record that breaks the cache's rules is not sent at all:
    validate fails the build over it, and the page keeps its links."""
    if not data:
        return {}
    if runoffs is None:
        runoffs = override_runoffs()
    states = data.get("states") or {}
    out = {}
    for code, record in sorted(states.items()):
        if code not in JURISDICTIONS or state_problems(code, record, runoffs):
            continue
        found, register, links = lines(code, record, place(code))
        if not found:
            continue
        entry = {"lines": found, "urls": links.urls, "labels": links.labels}
        if register:
            entry["register"] = register
        out[code] = entry
    return {"states": out, "election": data.get("election") or ELECTION,
            "read": data.get("read") or "", "checked": data.get("checked") or ""}


def deadlines_known(data, code):
    """Does the record say when *code*'s registration closes, or that it has
    none to close? Then vote.gov's page, a compiled table that states the
    rule in its own words, is not shown beside it (rules 50 and 53)."""
    record = ((data or {}).get("states") or {}).get(code) or {}
    return bool(_shown(record, "noElection") or _shown(record, "registration.none") or any(
        _shown(record, f"registration.{m}.deadline") for m in ("online", "mail", "inPerson")))
