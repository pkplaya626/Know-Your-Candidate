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
  official domain (``official_source``);
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
                  "votinginfoproject.org", "rockthevote.org", "headcount.org")

# Official pages on a domain that is not the office's own, each by its
# address and with what makes it the office's: {url prefix: (code, label,
# evidence)}. Read 2026-10-17 and 2026-10-18 by the researchers.
OFFICIAL_ELSEWHERE = {
    "https://drive.google.com/file/d/1h6Rb8t-XaocN-TfM7Q2CVHgExEXO2ARS/": (
        "AS", "American Samoa Election Office's 2026 calendar",
        "the calendar embedded on https://www.aselectionoffice.gov/calendar"),
    "https://drive.google.com/file/d/1KsY2DpP753FVksT3Yg_EF6JI476E9hdI/": (
        "AS", "American Samoa Election Office's absentee ballot form",
        "ASG Form EO-08, linked from https://www.aselectionoffice.gov/absentee-voting"),
    "https://docs.google.com/forms/d/e/1FAIpQLSeH9yVWrIrhA2dcHdCrF-a0g2c8qFBpCZe5CwxA2Kch-ZAwpw/": (
        "GU", "Guam Election Commission's online registration form",
        "embedded on the Commission's 'Register online' page, https://gec.guam.gov/register/"),
}
# Election offices whose own domain is neither .gov nor state.<xx>.us.
# voting.OFFICIAL_HOSTS holds the rest (the CNMI's and Puerto Rico's).
OFFICIAL_DOMAINS = {
    "kssos.org": "KS",          # the Kansas Secretary of State's publications host
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
    "registration.sameDay.available": (),
    "registration.sameDay.where": ("registration.sameDay.available",),
    "earlyVoting.start": (),
    "earlyVoting.end": (),
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
                   "mail.allMail"}

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
RUNOFF_SHORT = {"LA": "House general, if needed"}

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
        return ok, (f"{label}, as archived {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}" if ok else label)
    for prefix, (owner, label, _evidence) in OFFICIAL_ELSEWHERE.items():
        if url.startswith(prefix):
            return (owner == code), (label if owner == code else f"{owner}'s page, not {code}'s")
    host = _host(url)
    label = host[4:] if host.startswith("www.") else host
    state = re.search(r"\.state\.([a-z]{2})\.us$", host)
    if state:
        return (state.group(1) == code.lower()), label
    if host.endswith(".gov"):
        return True, label
    for domain, owner in list(OFFICIAL_DOMAINS.items()) + list(voting.OFFICIAL_HOSTS.items()):
        if host == domain or host.endswith("." + domain):
            return (owner == code), label
    return False, f"{host} is not an election office's own domain"


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
                 "registration.inPerson.deadline", "mail.requestDeadline.date"):
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

    def of(self, *fields):
        out = []
        for field in fields:
            for source in _sources(self.record, field):
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
    every = len(by_date) == 1 and len(next(iter(by_date.values()))) == 3
    for date, methods in sorted(by_date.items()):
        out.append({"k": "register", "d": date,
                    "t": "Last day to register to vote " + _join([m[1] for m in methods]),
                    "s": "Registration closes" if every
                    else "Register " + " / ".join(m[0] if m[0] != "mail" else "by mail"
                                                  for m in methods),
                    "src": links.of(*[m[2] for m in methods])})
    register = None
    if by_date:
        last = max(by_date)
        register = {"by": last, "how": _join([m[0] if m[0] != "mail" else "by mail"
                                              for m in by_date[last]])}
    if _shown(record, "registration.sameDay.available"):
        where = _shown(record, "registration.sameDay.where")
        out.append({"k": "sameday",
                    "t": "Same-day registration: you can register and vote at the same time" +
                         (f" - {where}" if where else ""),
                    "src": links.of("registration.sameDay.available", "registration.sameDay.where")})
        register = dict(register or {}, sameDay=True)
    elif register is not None and get(reg, "sameDay.available") is False:
        register["sameDay"] = False

    start, end = _shown(record, "earlyVoting.start"), _shown(record, "earlyVoting.end")
    if start and end:
        out.append({"k": "early", "d": start, "e": end, "t": "In-person early voting",
                    "s": "Early voting", "src": links.of("earlyVoting.start", "earlyVoting.end")})

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
        out.append({"k": "return", "d": returned or received,
                    "t": "Mail ballots must arrive at the election office by " +
                         (time + " on " if time else "") + "this day",
                    "s": "Mail ballots due",
                    "src": links.of("mail.returnDeadline.date" if returned
                                    else "mail.returnDeadline.receivedBy",
                                    "mail.returnDeadline.receivedBy")})

    runoff = _shown(record, "runoff.date")
    if runoff and code in RUNOFF_WORDS:
        before, after = RUNOFF_WORDS[code]
        out.append({"k": "runoff", "d": runoff, "t": before, "p": after, "keep": True,
                    "s": RUNOFF_SHORT.get(code, "Runoff, if needed"), "src": links.of("runoff.date")})
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
