"""Louisiana's House results, as its Secretary of State publishes them (rule 64).

Louisiana's House seats vote first in an open primary on general-election
day, and its December general election decides any seat nobody won outright
(``overrides.OPEN_PRIMARY_SEATS``). Until the count the Secretary of State's
qualified list is the ballot (kyc/qualified.py); after it the state's
Wikipedia page was to decide. Twelve days after the 2026 count all six seats
still stood on the list: the page's infobox declared four majority winners
over tables with no counts, named a runoff in prose that no table marked, and
said nothing of the sixth.

The office publishes its own results as JSON, the files its results page
(https://voterportal.sos.la.gov/graphical) reads, at
``.../ElectionResults/ElectionResults/Data?blob=<file>``:

* ``ElectionDates.htm`` - every election, with its id, its date and whether
  its results are official (``ResultsOfficial``);
* ``<yyyyMMdd>/RacesCandidates_Multiparish.htm`` - each race's title, how
  many it elects, whether it can go to a runoff, and its choices, each one
  the name as the ballot prints it and the party's code ("Steve Scalise
  (REP)");
* ``<yyyyMMdd>/Votes_Multiparish.htm`` - each race's precincts and absentee
  batches reporting and expected, and each choice's count and ``Outcome``.

An election is found in the list by its date, never by a typed id; a race is
a seat's by "U. S. Representative" and the district number in its title
alone. Only those races are kept, and of them only what the cache needs to
show and check a result: the names and party codes as the office prints
them, the counts, the outcomes, the reporting, the day the files were
written. A file in another shape than this reader knows concludes nothing
(rule 8): :class:`OfficeResultsError`, and every seat keeps what it had.

The office's own page shows no outcome until the election's results are
official (its script draws ``Outcome`` only where ``isOfficial``); before
that it says "Unofficial Results" over the counts. So a result read before
the canvass is the counts' own - every precinct and absentee batch in, the
outcomes the feed carries agreeing with them - and :func:`judge` holds any
whose deciding margin is under ``results.CLOSE_MARGIN`` until the office
marks the election official. The page credits it as unofficial until then.
"""

import datetime
import json
import re
import time
import urllib.request

from . import agent

DATA = "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data"
# The office's results page, which reads these files: what a reader opens.
PAGE = "https://voterportal.sos.la.gov/graphical"
SOURCE = "the Louisiana Secretary of State's election results"
DATES_FILE = "ElectionDates.htm"
RACES_FILE = "{day}/RacesCandidates_Multiparish.htm"
VOTES_FILE = "{day}/Votes_Multiparish.htm"
TIMEOUT = 60
_GAP = 1.0           # one request at a time, a second apart

# The office's word for each status, and nothing else: its script also knows
# "Advances" (a party primary's) and "Approved" (a proposition's), which an
# open primary's House race never carries, and a blank is a race not called.
OUTCOMES = {"Elected": "elected", "Defeated": "defeated", "Runoff": "runoff"}

# The party codes the results print, as the office's own qualified list for
# the same candidates spells the party (read 2026-11-15: every House choice
# of the November 3 election, beside its Candidate Inquiry export). A code
# not here holds the race: this reader does not guess at one.
PARTY_CODES = {"REP": "Republican", "DEM": "Democrat", "LBT": "Libertarian",
               "NOPTY": "No Party"}

_HOUSE = re.compile(r"^U\. S\. Representative -- (\d+)(?:st|nd|rd|th) Congressional District$")
_DESC = re.compile(r"^(.*\S)\s+\(([A-Z]+)\)$")
_SUFFIX = re.compile(r",\s+(?=(?:Jr|Sr)\.?$|(?:II|III|IV|V)$)")


class OfficeResultsError(RuntimeError):
    """A file this reader cannot read as the office's results: concludes nothing."""


def url(name):
    """The address of one of the office's results files."""
    return f"{DATA}?blob={name}"


def _iso(us_date):
    try:
        return datetime.datetime.strptime(str(us_date).strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        raise OfficeResultsError(f"unreadable election date {us_date!r}") from None


def _json(text, what):
    try:
        return json.loads(str(text).lstrip("﻿"))
    except ValueError:
        raise OfficeResultsError(f"{what} is not JSON") from None


def parse_dates(text):
    """``{iso date: {"id", "official"}}`` from ``ElectionDates.htm``."""
    data = _json(text, DATES_FILE)
    try:
        rows = data["Dates"]["Date"]
    except (KeyError, TypeError):
        raise OfficeResultsError(f"{DATES_FILE} holds no Dates.Date list") from None
    if isinstance(rows, dict):
        rows = [rows]
    out = {}
    for row in rows if isinstance(rows, list) else ():
        try:
            eid, day, flag = row["PKElectionID"], row["ElectionDate"], row["ResultsOfficial"]
        except (KeyError, TypeError):
            raise OfficeResultsError(f"{DATES_FILE}: an election without its id, date or "
                                     "official flag") from None
        if str(flag) not in ("0", "1"):
            raise OfficeResultsError(f"{DATES_FILE}: ResultsOfficial {flag!r} for {day}")
        iso = _iso(day)
        if iso in out:
            raise OfficeResultsError(f"{DATES_FILE} lists two elections on {day}")
        out[iso] = {"id": str(eid), "official": str(flag) == "1"}
    if not out:
        raise OfficeResultsError(f"{DATES_FILE} lists no election")
    return out


def _list(value):
    return [value] if isinstance(value, dict) else value if isinstance(value, list) else None


def _count(value, what):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise OfficeResultsError(f"{what} is not a count: {value!r}") from None
    if number < 0:
        raise OfficeResultsError(f"{what} is negative: {value!r}")
    return number


def parse_races(races_text, votes_text):
    """``{"written", "version", "races": {district: race}}`` for the House
    races of one election: each race's office id and title, how many it
    elects, whether it can have a runoff, its reporting, and its choices
    (``id``, ``desc`` as printed, ``votes``, ``outcome`` as printed)."""
    races_doc = _json(races_text, "the races file")
    votes_doc = _json(votes_text, "the votes file")
    try:
        races = _list(races_doc["Races"]["Race"])
        votes = _list(votes_doc["Races"]["Race"])
        written = races_doc["Races"].get("WriteTime")
        version = votes_doc["Races"].get("VersionDateTime")
    except (KeyError, TypeError, AttributeError):
        raise OfficeResultsError("the races or votes file holds no Races.Race list") from None
    if races is None or votes is None:
        raise OfficeResultsError("the races or votes file holds no Races.Race list")
    counted = {}
    for race in votes:
        if not isinstance(race, dict) or "ID" not in race:
            raise OfficeResultsError("the votes file holds a race without an id")
        counted[str(race["ID"])] = race
    out = {}
    for race in races:
        if not isinstance(race, dict):
            raise OfficeResultsError("the races file holds a race that is not a record")
        title = re.sub(r"\s+", " ", str(race.get("SpecificTitle") or "")).strip()
        m = _HOUSE.match(title)
        if not m:
            continue
        district = int(m.group(1))
        if district in out:
            raise OfficeResultsError(f"two races for the {title!r}")
        rid = str(race.get("ID") or "")
        tally = counted.get(rid)
        if tally is None:
            raise OfficeResultsError(f"no counts for race {rid} ({title})")
        choices = _list(race.get("Choice"))
        counts = _list(tally.get("Choice"))
        if not choices or counts is None:
            raise OfficeResultsError(f"race {rid} ({title}) lists no choices")
        by_choice = {}
        for c in counts:
            if not isinstance(c, dict) or "ID" not in c or "VoteTotal" not in c:
                raise OfficeResultsError(f"race {rid}: a count without its choice or total")
            by_choice[str(c["ID"])] = c
        if len(by_choice) != len(choices):
            raise OfficeResultsError(f"race {rid}: {len(choices)} choices, "
                                     f"{len(by_choice)} counts")
        listed = []
        for c in choices:
            cid = str((c or {}).get("ID") or "")
            got = by_choice.get(cid)
            if got is None or not (c or {}).get("Desc"):
                raise OfficeResultsError(f"race {rid}: choice {cid} has no count or no name")
            listed.append({"id": cid, "desc": str(c["Desc"]).strip(),
                           "votes": _count(got["VoteTotal"], f"race {rid}'s count for {cid}"),
                           "outcome": str(got.get("Outcome") or "").strip()})
        try:
            reporting = {k: _count(tally[k], f"race {rid}'s {k}") for k in (
                "PrecinctsReporting", "PrecinctsExpected", "NumAbsenteeReporting",
                "NumAbsenteeExpected")}
        except KeyError as exc:
            raise OfficeResultsError(f"race {rid} gives no {exc.args[0]}") from None
        out[district] = {
            "officeId": rid, "title": title,
            "toElect": str(race.get("NumberToBeElected") or ""),
            "canHaveRunoff": str(race.get("CanHaveRunoff") or "") == "1",
            "reporting": {"precincts": [reporting["PrecinctsReporting"],
                                        reporting["PrecinctsExpected"]],
                          "absentee": [reporting["NumAbsenteeReporting"],
                                       reporting["NumAbsenteeExpected"]]},
            "choices": listed,
        }
    return {"written": written, "version": version, "races": out}


def list_form(desc):
    """``(name, party code)`` of a choice as printed ("\\"Clay\\" Higgins
    (REP)"), the name in the qualified list's form: a quoted nickname that
    stands in for the first name loses its quotes ("Clay Higgins", as
    ``qualified.ballot_name`` writes it), a comma before a suffix goes
    ("Troy A. Carter Sr."). ``(None, None)`` where it carries no party code."""
    m = _DESC.match(str(desc or "").strip())
    if not m:
        return None, None
    name, code = m.groups()
    name = re.sub(r'^"([^"]+)"(?= )', r"\1", name)
    name = _SUFFIX.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip(), code


def fetch(rounds, today=None, get=None, log=print):
    """The office's results for each date of *rounds* that has come: ``{"read",
    "page", "source", "elections": {iso: {"id", "official", "written",
    "version", "urls", "races": {district: race}}}}``.

    *rounds* are the seats' election dates (ISO); one the office does not
    list, or that is still to come, is simply absent. *get* fetches one
    file's text by name (tests); by default the office is asked once per
    file, one request at a time, as this project (rule 103). Any file it
    cannot read as the office's results raises :class:`OfficeResultsError`
    or the request's own error: the caller concludes nothing (rule 8).
    """
    today = today or datetime.date.today()
    if get is None:
        def get(name):
            request = urllib.request.Request(url(name), headers=dict(agent.HEADERS))
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read().decode("utf-8", "replace")
            time.sleep(_GAP)
            return body
    listed = parse_dates(get(DATES_FILE))
    elections = {}
    for day in sorted(set(rounds)):
        if day > today.isoformat():
            continue
        if day not in listed:
            log(f"    [note] the Secretary of State lists no election on {day} yet")
            continue
        stamp = day.replace("-", "")
        names = (RACES_FILE.format(day=stamp), VOTES_FILE.format(day=stamp))
        read = parse_races(get(names[0]), get(names[1]))
        elections[day] = dict(listed[day], written=read["written"], version=read["version"],
                              urls=[url(DATES_FILE)] + [url(n) for n in names],
                              races=read["races"])
    return {"read": today.isoformat(), "page": PAGE, "source": SOURCE, "elections": elections}


def _stamp(text):
    try:
        return datetime.datetime.fromisoformat(str(text).strip())
    except (TypeError, ValueError):
        return None


def older(now, then, what):
    """Why a file read now concludes nothing beside the last read: its
    *what* stamp (the races file's ``WriteTime``, the votes file's
    ``VersionDateTime``) is before the one the last read relied on, or
    missing where that read had one. None where it is no older, or where
    the last read had no stamp to compare. The three files are fetched one
    by one, and a cached copy of one beside a fresh other would pair old
    counts with a new official flag."""
    last = _stamp(then) if then else None
    if last is None:
        return None
    current = _stamp(now) if now else None
    if current is None:
        return (f"the office's {what} is {now!r}, and the last read relied on one of {then}: "
                "nothing to tell whether this file is the newer")
    if current < last:
        return f"the office's {what} is {now}, before the {then} of the last read"
    return None


def judge(race, listed, official, close_margin, before=None):
    """``(verdict, why)`` for one seat's race in one round.

    *verdict* is ``{list name: "elected" | "runoff" | "defeated"}``, the
    names in the qualified list's form, or None with *why* saying what held
    it. *listed* is the office's qualified list for the seat (kyc/qualified.py
    entries); *official* whether the office marks the election's results
    official; *before* the first round's verdict, for the December round,
    which may hold only its two.

    Every gate concludes nothing where it fails: every precinct and
    absentee batch in; one to elect; every outcome a word whose meaning is
    known; every name on the list, of the party the list gives, and in the
    first round every name on the list (not withdrawn) in the results; the
    outcomes the counts' own result - one elected with a majority of every
    vote the race counts, or (a first round that can go to a runoff) the two
    highest in the runoff with nobody at a majority, everyone else defeated;
    and a deciding margin under *close_margin* - the winner's share over
    half, the leader's short of it, the second runoff place's over the
    third's - held until the office marks the results official.
    """
    pr, pe = race["reporting"]["precincts"]
    ar, ae = race["reporting"]["absentee"]
    if not (pe > 0 and pr == pe and ae > 0 and ar == ae):
        return None, (f"{pr} of {pe} precincts and {ar} of {ae} absentee batches "
                      "reporting, not all of them")
    if race.get("toElect") != "1":
        return None, f"the race elects {race.get('toElect')!r}, not one"
    first = before is None
    if first and not race.get("canHaveRunoff"):
        return None, "the race cannot go to a runoff, which an open primary's first round can"
    choices = race["choices"]
    for c in choices:
        if c["outcome"] not in OUTCOMES:
            return None, f"an Outcome this reader does not know, {c['outcome']!r}, for {c['desc']!r}"
    on_list = {q["name"]: q for q in listed if not q.get("withdrew")}
    names = []
    for c in choices:
        name, code = list_form(c["desc"])
        if not name:
            return None, f"{c['desc']!r} carries no party code"
        if name not in on_list:
            return None, (f"{name!r} is not on the Secretary of State's list of candidates "
                          "qualified for this seat")
        if code not in PARTY_CODES:
            return None, f"a party code this reader does not know, {code!r}, for {name!r}"
        if PARTY_CODES[code] != on_list[name].get("party"):
            return None, (f"{name!r} is {code} in the results and {on_list[name].get('party')!r} "
                          "on the list")
        names.append(name)
    if len(set(names)) != len(names):
        return None, "two choices carry one name"
    if first:
        missing = sorted(set(on_list) - set(names))
        if missing:
            return None, f"the list's {', '.join(missing)} not among the results' choices"
    else:
        two = sorted(n for n, st in before.items() if st == "runoff")
        if sorted(names) != two:
            return None, (f"the December race's choices ({', '.join(sorted(names))}) are not the "
                          f"first round's two ({', '.join(two)})")
    total = sum(c["votes"] for c in choices)
    if total <= 0:
        return None, "no votes counted"
    ranked = sorted(zip(names, choices), key=lambda nc: -nc[1]["votes"])
    marked = {name: OUTCOMES[c["outcome"]] for name, c in zip(names, choices)}
    elected = [n for n, st in marked.items() if st == "elected"]
    runoff = [n for n, st in marked.items() if st == "runoff"]
    defeated = [n for n, st in marked.items() if st == "defeated"]
    top = ranked[0][1]["votes"]
    hold = None if official else close_margin
    if len(elected) == 1 and not runoff and len(defeated) == len(choices) - 1:
        if ranked[0][0] != elected[0] or 2 * top <= total:
            return None, f"{elected[0]!r} is marked elected without a majority of {total:,} votes"
        lead = top / total - 0.5
        if hold is not None and lead < hold:
            return None, (f"{elected[0]!r}'s majority is {100 * lead:.2f} points over half, under "
                          f"{100 * hold:.1f}, and the office has not marked its results official")
        return marked, None
    if first and len(runoff) == 2 and not elected and len(defeated) == len(choices) - 2:
        second = ranked[1][1]["votes"]
        third = ranked[2][1]["votes"] if len(ranked) > 2 else 0
        if {ranked[0][0], ranked[1][0]} != set(runoff) or second <= third:
            return None, "the two in the runoff are not the two highest counts"
        if 2 * top > total:
            return None, f"{ranked[0][0]!r} holds a majority and is marked for a runoff"
        if hold is not None:
            if (second - third) / total < hold:
                return None, (f"the second runoff place is {second - third:,} votes, "
                              f"{100 * (second - third) / total:.2f} points, ahead of the third, "
                              f"under {100 * hold:.1f}, and the office has not marked its "
                              "results official")
            if 0.5 - top / total < hold:
                return None, (f"{ranked[0][0]!r} is {100 * (0.5 - top / total):.2f} points short "
                              f"of a majority, under {100 * hold:.1f}, and the office has not "
                              "marked its results official")
        return marked, None
    return None, ("the outcomes are not a complete result: "
                  f"{len(elected)} elected, {len(runoff)} in a runoff, {len(defeated)} defeated "
                  f"of {len(choices)}")


def failure(exc):
    """Why a read failed, short, for the cache: never an address of the
    machine that asked (an error's text can carry one)."""
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b|\b(?:[0-9a-f]{1,4}:){3,7}[0-9a-f]{1,4}\b"
                  r"|[0-9a-f:]*::[0-9a-f:]+",
                  "<address>", f"{type(exc).__name__}: {exc}", flags=re.I)
    return text[:200]


def credit(official):
    """The words a status read from these results is credited with."""
    return (f"{SOURCE.replace('election results', 'official election results')}" if official
            else f"{SOURCE}, unofficial until its canvass")
