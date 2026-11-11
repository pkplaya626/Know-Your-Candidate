"""Share pages, and the plain lists the state pages are written with (rule 96).

A profile or a race is a view behind a fragment (``index.html#/profile/<id>``),
and a crawler drops the fragment: every person or race anyone shared
unfurled as the home page's card. So the build writes one small page per
profile (``p/<id>.html``) and per race (``r/<raceId>.html``), each with its
own title, description, canonical address and image, and the facts in
plain text. A reader with scripts is sent on to the view at once
(``assets/kyc-share.js``, never an inline script); a reader without, and a
crawler, stay and read the facts.

Where someone stands in their race is said in the words the profile dialog
uses (``KYC.standing`` in ``assets/kyc.js``, the one table of rule 63). A
page written without JavaScript cannot call it, so :func:`status_words` is
that function's "long" form read the same way, and the render suite
compares the two for every profile on every build (``testSharePages``): a
word changed in one and not the other fails, as two copies of the table
once drifted unnoticed.

Nothing here is dated, and nothing here carries the build's time: a refresh
that changes nobody's status rewrites none of these 3,000 files (rule 18).
"""

import html
import itertools
import json
import os
from urllib.parse import urlparse

PROFILE_DIR = "p"
RACE_DIR = "r"
# The longest a race page's description runs (describe_race): unfurlers cut
# at 200-300 characters.
DESCRIPTION_MAX = 300


def _e(text):
    return html.escape(str(text), quote=True)


def profile_path(pid):
    """``p/<id>.html``, relative to the site's root."""
    return f"{PROFILE_DIR}/{pid}.html"


def race_path(rid):
    """``r/<raceId>.html``, relative to the site's root."""
    return f"{RACE_DIR}/{rid}.html"


# ------------------------------------------------------------- the words

# KYC.raceStatus's "long" words, status by status, with the member's own
# wording (`member`) and whether the status takes someone out of the race
# (`off`). Only the "long" form: it is the one the profile dialog shows.
def _leaving():
    return {"long": "Not running for re-election in 2026", "leaving": "member"}


_RACE_STATUS = {
    "nominee": {"long": "On the November ballot", "member": {"long": "Renominated for 2026"}},
    "elected": {"long": "Elected in November", "member": {"long": "Re-elected in November"}},
    "runoff": {"long": "In the general election runoff"},
    "advanced": {"long": "In a primary runoff"},
    "qualified": {"long": "On the November 3 open-primary ballot"},
    "defeated": {"long": "Lost the November election",
                 "member": {"long": "Lost re-election in November"}},
    "eliminated": {"long": "Lost the 2026 primary", "off": True},
    "withdrawn": {"long": "Withdrew from the 2026 race", "off": True, "member": _leaving()},
    "unlisted": {"long": "Not on the 2026 primary ballot", "off": True, "member": _leaving()},
}
_APPOINTEE_LEAVING = {"long": "Not running in 2026", "leaving": "appointee"}
# KYC's LEFT: the same once the Congress the cycle elects sits (the record
# phase), when whoever they badge has left the seat.
_LEFT = {"member": {"long": "Did not run for re-election in 2026"},
         "appointee": {"long": "Did not run in 2026"}}
_UNCONFIRMED = {"long": "Not on the November ballot", "off": True}
_AWAITING = {"long": "On the November ballot: awaiting result"}
_MINOR_NOMINEE = {"long": "On the November ballot"}
_ALL_PARTY = {"long": "Advanced to the November ballot",
              "member": {"long": "Advanced to the November ballot"}}
_LISTED = {
    "unlisted": {"long": "Not on the November 3 open-primary ballot", "off": True,
                 "member": _leaving()},
    "withdrawn": {"long": "Withdrew from the 2026 race", "off": True, "member": _leaving()},
}
_CERTIFIED = {
    "nominee": {"member": {"long": "On the November ballot"}},
    "unlisted": {"long": "Not on the November ballot", "off": True, "member": _leaving()},
    "withdrawn": {},
    "eliminated": {},
}
NOVEMBER = frozenset({"nominee", "elected", "defeated", "runoff", "qualified"})
OFF_BALLOT = frozenset({"eliminated", "withdrawn", "unlisted"})

# KYC.raceStatus's openRound: an open primary's December round is its general
# election, never a runoff (rule 75). The Louisiana Secretary of State calls
# the House's rounds of 2026 the "Open U.S. Representative Primary" (November
# 3) and the "Open U.S. Representative General" (December 12): Election
# Dates, https://www.sos.la.gov/elections-voting/election-dates, and its 2026
# elections calendar, https://www.sos.la.gov/media/p31j4zkc/elections-calendar-2026.pdf,
# "Type of Election" (read 2026-11-01). The date is the race's own
# (``generalRunoff``); once results read after it still mark no winner, the
# words are in the past tense and awaiting one (rule 63).
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")


def _open_round(date, held=False):
    """The long words of an open primary's December round on *date*."""
    try:
        _year, month, day = (int(part) for part in str(date).split("-"))
        words = f"{_MONTHS[month - 1]} {day}"
    except (ValueError, IndexError):
        return None
    if held:
        return {"long": f"Ran in the {words} general election: awaiting result"}
    return {"long": f"In the {words} general election"}


def _decided_round(status, decided):
    """KYC.decidedRound's long words: a result the December round decided
    (``raceStatusDecided``, ``{date, open}``) in that round's words, never
    "in November" - an open primary's general election, else a general
    election runoff (Georgia's). None for any other status, or no date."""
    if status not in ("elected", "defeated") or not decided:
        return None
    try:
        _year, month, day = (int(part) for part in str(decided.get("date") or "").split("-"))
        words = f"{_MONTHS[month - 1]} {day}"
    except (ValueError, IndexError):
        return None
    won = status == "elected"
    if decided.get("open"):
        return {"long": f"Elected on {words}" if won else f"Lost the {words} general election",
                "member": {"long": f"Re-elected on {words}" if won
                           else f"Lost re-election on {words}"}}
    return {"long": f"Won the {words} runoff" if won else f"Lost the {words} runoff",
            "member": {"long": f"Re-elected in the {words} runoff" if won
                       else f"Lost re-election in the {words} runoff"}}


def december_round(race):
    """The date of *race*'s December round when it is an open primary's
    general election (``primaryKind`` "open"), else None: Georgia's runoff
    keeps the runoff's words."""
    race = race or {}
    return race.get("generalRunoff") if race.get("primaryKind") == "open" else None


def party_key(person):
    """KYC.partyKey: "d", "r", "vacant" or "i"."""
    party = str((person or {}).get("party"))
    if party == "Vacant" or (person or {}).get("status") == "Vacant":
        return "vacant"
    if "Democrat" in party:
        return "d"
    if party == "Republican":
        return "r"
    return "i"


def _runs_elsewhere(item):
    return (not item.get("isCandidate") and bool(item.get("contestRaceId"))
            and item.get("contestRaceId") != item.get("raceId"))


def _own_record(item):
    return not _runs_elsewhere(item) or item.get("raceStatusRace") == item.get("contestRaceId")


def contest_status(item, by_id):
    """KYC.contestStatus: the result that describes what *item* does in 2026."""
    if _own_record(item):
        return item.get("raceStatus") or ""
    filing = by_id.get(item.get("alsoRunningId") or "")
    if filing and filing.get("raceId") == item.get("contestRaceId"):
        return filing.get("raceStatus") or ""
    return ""


def ballot_line(item, by_id):
    """KYC.ballotLine: a nominee's November line when it is not their party's."""
    if contest_status(item, by_id) not in NOVEMBER:
        return ""
    if _own_record(item):
        return str(item.get("ballotLine") or "")
    filing = by_id.get(item.get("alsoRunningId") or "")
    if filing and filing.get("raceId") == item.get("contestRaceId"):
        return str(filing.get("ballotLine") or "")
    return ""


def _race_status(status, own=False, unconfirmed=False, appointed=False, source=None,
                 all_party=None, minor=False, post_election=False, open_round=None,
                 round_held=False, decided=None, record=False):
    """KYC.raceStatus(status, "long", opts): ``(words, off)`` or None.
    *open_round* is the date of an open primary's December round
    (``opts.round``), *round_held* whether it has passed; *decided* the
    December round that decided a result (``opts.decided``); *record* the
    record phase (``opts.record``), whose words for a member who did not
    run are in the past tense (``_LEFT``)."""
    spec = _RACE_STATUS.get(status)
    if not spec:
        return None
    if status == "nominee" and all_party:
        spec = _ALL_PARTY
    if status == "runoff" and open_round:
        spec = _open_round(open_round, round_held) or spec
    if decided:
        spec = _decided_round(status, decided) or spec
    if source == "qualified" and status in _LISTED:
        spec = _LISTED[status]
    certified = _CERTIFIED.get(status) if source == "certified" else None
    if certified is not None:
        merged = dict(spec)
        merged.update(certified)
        if "member" not in certified and spec.get("member"):
            merged["member"] = dict(spec["member"])
        spec = merged
    if status == "unlisted" and unconfirmed and certified is None:
        spec = _UNCONFIRMED
    mine = (own and spec.get("member")) or {}
    if own and appointed and spec.get("member") and spec.get("off"):
        mine = _APPOINTEE_LEAVING
    if record and mine.get("leaving"):
        mine = _LEFT[mine["leaving"]]
    if status == "nominee" and spec is _RACE_STATUS["nominee"] and minor and not own:
        spec = _MINOR_NOMINEE
    if status in ("nominee", "qualified") and post_election:
        spec, mine = _AWAITING, {}
    return (mine.get("long") or spec.get("long"), bool(spec.get("off")))


# Where the dialog's long title says a status came from (its " Source: ..."),
# by the same steps as KYC.raceStatus.
# Never "the state's": a territory's, or D.C.'s, is not (rule 75).
_WIKIPEDIA = "Wikipedia's election results page"
_INQUIRY = "the Secretary of State's Candidate Inquiry"
_CERTIFIED_LIST = "the certified list of candidates"
# A November winner, or loser, called from the national summary where the
# state's page held no result (rule 63's national route), in the owner's words.
NATIONAL_SOURCE = ("Wikipedia's national summary of the House elections, which gives no "
                   "vote count; the state's page had none when read")
# The same, where the state's page, read with the summary, gave counts that put
# the same person first and named no winner (raceStatusSource "national-counts").
NATIONAL_COUNTS_SOURCE = ("Wikipedia's national summary of the House elections, which marks "
                          "the winner and gives no vote count; the state's page, read the same "
                          "day, counts that winner ahead and names no winner")


def _race_source(status, source=None, source_name=None):
    """KYC.raceStatus's source for *status*: the words after "Source:" in
    the dialog's long title, or None for no status."""
    if status not in _RACE_STATUS:
        return None
    if status == "qualified" or source == "qualified":
        return _INQUIRY
    if source == "certified" and status in _CERTIFIED:
        return source_name or _CERTIFIED_LIST
    if source == "national" and status in ("elected", "defeated"):
        return NATIONAL_SOURCE
    if source == "national-counts" and status in ("elected", "defeated"):
        return NATIONAL_COUNTS_SOURCE
    return _WIKIPEDIA


def status_source(item, by_id):
    """Who says where *item* stands, as the profile dialog's badge credits
    it: a results page, a state's certified list, the Secretary of State's
    list, or a certified list's write-in line; None where the dialog names
    no source (a filer the results do not settle)."""
    if not item:
        return None
    record = item if _own_record(item) else (by_id.get(item.get("alsoRunningId") or "") or {})
    status = contest_status(item, by_id)
    if status in _RACE_STATUS:
        return _race_source(status, record.get("raceStatusSource"),
                            record.get("raceStatusSourceName"))
    unprinted = item.get("unprinted") or {}
    if (item.get("isCandidate") and not item.get("raceStatus") and not item.get("maybeNamed")
            and unprinted.get("kind") and unprinted.get("source")):
        return str(unprinted["source"])
    return None


# Every case the status table has, for the render suite to compare with
# KYC.raceStatus and KYC.standing (tests/fixtures/share_status_words.json):
# a word changed on one side fails on the day it changes, not on the night
# the first November result is read.
STATUS_TABLE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                            "share_status_words.json")
_FILERS = (
    {"maybeNamed": ["A Similar Name"]},
    {"unprinted": {"kind": "write-in", "source": "the Texas Secretary of State"}},
    {"unprinted": {"kind": "unopposed", "source": "the Florida Division of Elections"}},
    {"unprinted": {"kind": "write-in"}},
    {"ballotUnknown": True},
)


# The December round the table's open-primary rows are asked about: any date
# in December does, the cycle's own (overrides.OPEN_PRIMARY_SEATS) reads best.
_TABLE_ROUND = "2026-12-12"
# A result each kind of December round decided (_decided_round): an open
# primary's general election, and a general election runoff (Georgia's).
_TABLE_DECIDED = ({"date": _TABLE_ROUND, "open": True}, {"date": "2026-12-01", "open": False})


# The day the table's post-election rows are asked about.
_TABLE_AFTER = "2026-11-05"


def _member_elsewhere(status, renumbered, decided, unconfirmed):
    """A sitting member running for another seat, in the shape both sides
    read: the render suite builds the same record from a "contest" row."""
    item = {"id": "FAKE", "isCandidate": False, "name": "A Member", "party": "Republican",
            "contestLabel": "House • AL-1" if renumbered else "Senate • AL",
            "officeLabel": "House • AL-2", "raceId": "H-AL-02-2026",
            "contestRaceId": "H-AL-01-2026" if renumbered else "S-AL-2026",
            "raceStatusRace": "H-AL-01-2026" if renumbered else "S-AL-2026",
            "raceStatus": status}
    if renumbered:
        item["renumbered"] = True
    if decided:
        item["raceStatusDecided"] = decided
    if unconfirmed:
        item["raceStatusUnconfirmed"] = True
    return item


def _moved_holder(won, renumbered, labelled, sits):
    """A race's record holder whose run went elsewhere, and the race, in the
    shape both sides read: the render suite builds the same from a "moved"
    row. *won*: seated since for the seat they won (``raceRole``); *labelled*:
    their profile still holds the run (``contestLabel``); *sits*: they sit in
    this race's seat (else they have left it, or sit for the one they won)."""
    other = "H-AL-01-2026" if renumbered else "S-AL-2026"
    from .races import seat_label

    item = {"id": "FAKE", "isCandidate": False, "name": "A Member", "party": "Republican",
            "officeLabel": seat_label(other) if won else "House • AL-2",
            "raceId": other if won else "H-AL-02-2026", "raceStatusRace": other,
            "raceStatus": "elected" if won else "defeated"}
    if won:
        item["raceRole"] = "winner"
    if labelled:
        item["contestLabel"] = seat_label(other)
        item["contestRaceId"] = other
    if renumbered:
        item["renumbered"] = True
    if not sits and not won:
        item["formerMember"] = {"left": "2027-01-03"}
    race = {"id": "H-AL-02-2026", "incumbentIds": ["FAKE"],
            "incumbent": {"profileId": "FAKE", "seated": bool(sits)}}
    return race, item


def status_table():
    """``{"statuses": [...], "contest": [...], "moved": [...], "filers":
    [...]}``: what
    :func:`_race_status` and :func:`_race_source` say for every combination
    of status and option, what :func:`contest_clause` says of a member's other
    run in every status, what :func:`moved_sentence` says of a seat's holder
    whose run went elsewhere (seated in it or not, a member seated since for
    the seat they won or not), what :func:`standing` says for each kind
    of filer the results do not settle, and (``record``) what
    :func:`_race_status` says in the record phase."""
    words = []
    # A race whose December round is an open primary's general election
    # (_open_round), before that day and after it; the render suite reads
    # "held" as the day after it, so only after Election Day.
    # And a result each kind of December round decided ("decided"), asked
    # after the open primary's day.
    rounds = ((None, 0, None), (_TABLE_ROUND, 0, None), (_TABLE_ROUND, 1, None),
              (_TABLE_ROUND, 1, _TABLE_DECIDED[0]), (None, 0, _TABLE_DECIDED[1]))
    for status in sorted(_RACE_STATUS):
        # A top-four primary's words are a top-two's in the long form.
        for all_party in (None, "top-two"):
            for source in (None, "certified", "qualified"):
                for round_date, held, decided in rounds:
                    if (round_date or decided) and all_party:
                        continue
                    if decided and status not in ("elected", "defeated"):
                        continue
                    for flags in itertools.product((0, 1), repeat=5):
                        own, appointed, unconfirmed, minor, post = flags
                        if (held or decided) and not post:
                            continue
                        label, off = _race_status(
                            status, own=bool(own), unconfirmed=bool(unconfirmed),
                            appointed=bool(appointed), source=source, all_party=all_party,
                            minor=bool(minor), post_election=bool(post), open_round=round_date,
                            round_held=bool(held), decided=decided)
                        words.append([status, all_party, source, round_date, held, decided]
                                     + list(flags) + [label, int(off)])
    # The record phase, after Election Day: only a member who did not run
    # reads differently (_LEFT), and every other word is asked too, to show
    # it does not.
    record = []
    for status in sorted(_RACE_STATUS):
        for all_party in (None, "top-two"):
            for source in (None, "certified", "qualified"):
                for own, appointed, unconfirmed in itertools.product((0, 1), repeat=3):
                    label, off = _race_status(
                        status, own=bool(own), unconfirmed=bool(unconfirmed),
                        appointed=bool(appointed), source=source, all_party=all_party,
                        post_election=True, record=True)
                    record.append([status, all_party, source, own, appointed, unconfirmed,
                                   label, int(off)])
    credits = [[status, source, name, _race_source(status, source, name)]
               for status in sorted(_RACE_STATUS)
               for source, name in ((None, None), ("certified", None),
                                    ("certified", "the Test Division of Elections"),
                                    ("qualified", None), ("national", None),
                                    ("national-counts", None))]
    contest = []
    for status in ("", *sorted(_RACE_STATUS)):
        for renumbered in (0, 1):
            for post in (0, 1):
                for decided in (None, *_TABLE_DECIDED):
                    if decided and (status not in ("elected", "defeated") or not post):
                        continue
                    for unconfirmed in (0, 1):
                        if unconfirmed and status != "unlisted":
                            continue
                        item = _member_elsewhere(status, renumbered, decided, unconfirmed)
                        contest.append([status, renumbered, post, decided, unconfirmed,
                                        contest_clause(item, {}, {}, _TABLE_AFTER if post else False)])
    moved = []
    for won in (0, 1):
        for renumbered in (0, 1):
            for labelled in (0, 1):
                for post in (0, 1):
                    for sits in (0, 1):
                        # Seated since for the seat they won: their profile
                        # holds no other run, and they sit for that seat.
                        if won and (labelled or sits):
                            continue
                        race, item = _moved_holder(won, renumbered, labelled, sits)
                        moved.append([won, renumbered, labelled, post, sits, moved_sentence(
                            race, item, {}, {}, _TABLE_AFTER if post else False)])
    filers = []
    for fake in _FILERS:
        item = dict(fake, isCandidate=True, id="FAKE")
        spec = standing(item, {}, {})
        filers.append([fake, spec[0] if spec else None, status_source(item, {})])
    # A former member (formerMember), before and after Election Day, in the
    # record phase or not: from the day after it they have left, whatever the
    # phase (past_tense, KYC.pastTense).
    former = []
    for status in sorted(_RACE_STATUS):
        for appointed, post, in_record in itertools.product((0, 1), repeat=3):
            if in_record and not post:
                continue
            item = _former_member(status, appointed)
            day = ResultsDay(_TABLE_AFTER, record=bool(in_record)) if post else False
            spec = standing(item, {}, {}, day)
            former.append([status, appointed, post, in_record, spec[0] if spec else None,
                           int(spec[1]) if spec else 0])
    return {"words": ["status", "allParty", "source", "round", "held", "decided", "own",
                      "appointed", "unconfirmed", "minor", "post", "label", "off"],
            "statuses": words, "credits": credits, "contest": contest, "moved": moved,
            "filers": filers, "record": record, "former": former}


def _former_member(status, appointed):
    """A record incumbent archived as a former member, for :func:`status_table`
    (the render suite builds the same)."""
    item = {"id": "FAKE", "isCandidate": False, "name": "A Member", "party": "Republican",
            "raceId": "H-AL-02-2026", "raceStatus": status,
            "formerMember": {"left": "2026-12-15", "via": "legislators-historical",
                             "congress": 119}}
    if appointed:
        item["appointed"] = True
    return item


def status_table_text():
    """The fixture's text: one row a line, so a change reads as a diff."""
    table = status_table()
    lines = ["{", f'"words": {json.dumps(table["words"])},']
    keys = ("statuses", "credits", "contest", "moved", "filers", "record", "former")
    for key in keys:
        rows = table[key]
        lines.append(f'"{key}": [')
        lines += [json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                  + ("," if i < len(rows) - 1 else "") for i, row in enumerate(rows)]
        lines.append("]," if key != keys[-1] else "]")
    lines += ["}", ""]
    return "\n".join(lines)


def write_status_table(path=STATUS_TABLE):
    """Rewrite the fixture after a change to the words here (and the same
    change in kyc.js): ``python -c "from kyc import share; share.write_status_table()"``."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(status_table_text())


def _no_primary_race(race_id, races_by_id):
    """KYC's noPrimaryRace: a race whose calendar names no primary (null,
    not absent) and for which no results were read."""
    race = races_by_id.get(race_id)
    return bool(race) and "primaryDate" in race and race["primaryDate"] is None \
        and race.get("results") is None


def _unsettled(item, races_by_id):
    """KYC's unsettled(): a filer the results do not settle."""
    if not item.get("isCandidate") or item.get("raceStatus"):
        return None
    if item.get("maybeNamed"):
        return "Result not matched"
    unprinted = item.get("unprinted") or {}
    if unprinted.get("kind"):
        return ("Unopposed in November, not printed" if unprinted["kind"] == "unopposed"
                else "Write-in candidate")
    no_primary = not item.get("ballotUnknown") and _no_primary_race(item.get("raceId"), races_by_id)
    if item.get("ballotUnknown") or no_primary:
        return "Ballot status not known"
    return None


def standing(item, by_id, races_by_id, post_election=False):
    """KYC.standing(item, "long"): ``(words, off)``, or None for no status.
    *post_election* is :func:`post_election`'s: False, or the day the
    results were read."""
    if not item:
        return None
    record = item if _own_record(item) else (by_id.get(item.get("alsoRunningId") or "") or {})
    status = contest_status(item, by_id)
    # The race that status is about, for its December round's words (as
    # KYC.raceStatusOf finds it); held once the results were read after it.
    open_round = None
    if status == "runoff":
        race_id = record.get("raceStatusRace") or (
            item.get("contestRaceId") if _runs_elsewhere(item) else item.get("raceId"))
        open_round = december_round(races_by_id.get(race_id or ""))
    spec = _race_status(
        status,
        own=(not item.get("isCandidate") and not item.get("contestLabel")
             and not item.get("raceRole") and not (item.get("appointed") and status != "unlisted")),
        unconfirmed=bool(item.get("raceStatusUnconfirmed")),
        appointed=bool(item.get("appointed")),
        source=record.get("raceStatusSource"),
        all_party=record.get("allPartyPrimary"),
        minor=party_key(item) == "i",
        post_election=post_election,
        open_round=open_round,
        # *post_election* is the day the results were read (post_election()).
        round_held=bool(open_round and isinstance(post_election, str)
                        and open_round < post_election),
        decided=record.get("raceStatusDecided"),
        # The past tense (_LEFT): in the record phase, which post_election()
        # carries (ResultsDay), and for a former member once the election
        # has passed, as KYC.pastTense says: one who left in December read
        # "Not running for re-election in 2026" until January 3 (PR #226).
        record=past_tense(item, post_election))
    if spec:
        return spec
    words = _unsettled(item, races_by_id)
    return (words, False) if words else None


def past_tense(item, post_election=False):
    """KYC.pastTense: whether *item*'s own words are in the past tense - in
    the record phase (*post_election*'s ``record``), and for a former member
    whenever the results were read after Election Day."""
    if getattr(post_election, "record", False):
        return True
    return bool(post_election) and bool((item or {}).get("formerMember"))


def status_words(item, by_id, races_by_id, post_election=False, seat=None):
    """Where *item* stands, as the profile dialog's badge says it: the
    standing, "for <seat>" when a member runs for another, and the ballot
    line when it is not their party's. None for someone with no 2026 race
    (a senator whose seat is not up). *seat* writes the other seat's label
    for prose (:func:`seat_phrase`); the dialog's own is the label."""
    spec = standing(item, by_id, races_by_id, post_election)
    if not spec:
        return None
    words = spec[0]
    if not item.get("isCandidate") and item.get("contestLabel"):
        words += " for " + ((seat or (lambda label: label))(item["contestLabel"]))
    line = ballot_line(item, by_id)
    if line:
        words += " – " + line + " line"
    return words


def post_election(summary):
    """Whether the results the build holds were read after Election Day:
    KYC.electionStatus's "post-election" on the day they were read. The
    page's own clock is the reader's; a page written once is the data's.

    After Election Day it is that day itself ("2026-11-05", true as a
    test), so that :func:`standing` can say whether a December round had
    passed when the results were read, as the page says on the reader's
    day; before it, False. Once the Congress the cycle elects sits (the
    summary's phase "record", KYC.recordPhase), the day carries that too
    (:class:`ResultsDay`), so every page written from it says what the
    dialog does in that phase."""
    from . import cycle

    election = (summary or {}).get("election") or {}
    as_of = (election.get("resultsAsOf") or "")[:10]
    if not as_of:
        return False
    if as_of <= cycle.general_election_day(cycle.CYCLE).isoformat():
        return False
    return ResultsDay(as_of, record=election.get("phase") == "record")


class ResultsDay(str):
    """:func:`post_election`'s day, which is the day the results were read
    as a string, and says whether the build is in the record phase
    (``record``): one value for every share and state page to pass on, as
    the page reads one clock."""

    def __new__(cls, day, record=False):
        value = super().__new__(cls, day)
        value.record = bool(record)
        return value


def ballot_source(race):
    """KYC.ballotSource: who named the people on a race's November ballot."""
    res = (race or {}).get("results") or {}
    if res.get("fromQualifiedList"):
        return "per the Secretary of State's list of qualified candidates"
    if res.get("certifiedBy"):
        return ("per the " + res["certifiedBy"] if res.get("certifiedComplete")
                else "per Wikipedia's results page and the " + res["certifiedBy"])
    return "per Wikipedia's results page"


# ------------------------------------------------------------ portraits

def og_photo(person, host=None):
    """The share image of *person*: a photograph that reached the profile
    by a sourced route (rule 24), or None for the site's card. Only the
    sizes of the article's own file (``photoSet``, rule 42), the House
    Clerk's portrait, or a campaign's, a state legislature's or a person's
    chosen portrait (``overrides.CANDIDATE_PHOTOS``) with its credit - never
    a URL from a fallback chain. A heavy portrait
    the site made a smaller copy of (rule 101) is shared as that copy, at
    its absolute address on the site's one hostname (rule 21)."""
    sizes = [s for s in person.get("photoSet") or []
             if isinstance(s, (list, tuple)) and len(s) == 2 and _https(s[1])]
    if sizes:
        fits = [s for s in sizes if s[0] <= 640]
        width, url = max(fits) if fits else min(sizes)
        return url
    url = person.get("photo_url") or ""
    source = person.get("photoSource")
    from .photocopies import is_hosted
    if source == "curated" and is_hosted(url) and person.get("photoCredit"):
        # An office's photograph this site hosts unmodified, a person's
        # choice (the Tennessee General Assembly's, drawn on its page with
        # no address of its own): at its address on the site's hostname.
        copy = person.get("photoCopy") or {}
        shown = copy["src"] if copy.get("of") == url and copy.get("src") else url
        return f"https://{host}/{shown}" if host else None
    if not _https(url) or "Special:" in url:
        return None
    if source in ("clerk.house.gov", "cross-link") and urlparse(url).hostname == "clerk.house.gov":
        return url
    if source in ("campaign-site", "state-legislature", "curated") and person.get("photoCredit"):
        copy = person.get("photoCopy") or {}
        if host and copy.get("of") == url and copy.get("src"):
            return f"https://{host}/{copy['src']}"
        return url
    return None


def _https(url):
    return isinstance(url, str) and url.startswith("https://") and bool(urlparse(url).hostname)


# ----------------------------------------------------------------- pages

_SHARE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="{canonical}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
{image_size}<meta property="og:image:alt" content="{image_alt}">
<meta property="og:site_name" content="Know Your Candidate">
<meta name="twitter:card" content="{card}">
<meta name="referrer" content="no-referrer">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
<style>
body {{ margin: 0 auto; max-width: 40rem; padding: 1.5rem 1rem; line-height: 1.5;
       font-family: system-ui, sans-serif; background: Canvas; color: CanvasText; }}
ul {{ padding-left: 1.25rem; }}
.faint {{ opacity: .75; font-size: .9em; }}
</style>
</head>
<body data-share="{kind}">
<p class="faint"><a href="../index.html">Know Your Candidate</a></p>
<main>
<h1>{heading}</h1>
{body}
<p><a id="shareView" href="{view}">{view_words}</a></p>
<p class="faint">That view needs JavaScript. Without it, {fallback}</p>
</main>
<script src="../assets/kyc-share.js"></script>
</body>
</html>
"""

_SITE_CARD = "assets/social-card.png"


def _page(host, path, canonical_path=None, **fields):
    canonical_path = canonical_path or path
    canonical = f"https://{host}/{canonical_path}" if host else canonical_path
    image = fields.pop("image", None)
    if image:
        size, card, alt = "", "summary", fields.pop("image_alt")
    else:
        image = f"https://{host}/{_SITE_CARD}" if host else "../" + _SITE_CARD
        size = ('<meta property="og:image:width" content="1200">\n'
                '<meta property="og:image:height" content="630">\n')
        card, alt = "summary_large_image", "Know Your Candidate"
        fields.pop("image_alt", None)
    return _SHARE.format(canonical=_e(canonical), image=_e(image), image_size=size,
                         image_alt=_e(alt), card=card, **fields)


def _state_page(code):
    return f"../states/{str(code).lower()}.html"


def _seat_parts(label):
    """``"House • AL-4"`` -> ``("U.S. House", "AL-4")``; ``"Senate • AL"`` ->
    ``("U.S. Senate", "Alabama")``; an at-large seat -> ``"Alaska (at
    large)"``. None for a label of another shape. The label is read, never
    rebuilt (rule 4): only the bullet a card uses is put into words."""
    from .pages import state_name

    chamber, _, seat = str(label or "").partition(" • ")
    if chamber not in ("House", "Senate") or not seat:
        return None
    if chamber == "Senate":
        return "U.S. Senate", state_name(seat)
    if seat.endswith("-AL"):
        return "U.S. House", f"{state_name(seat[:-3])} (at large)"
    return "U.S. House", seat


def seat_phrase(label):
    """A seat in prose, for a sentence an unfurl shows: "the U.S. Senate in
    Alabama", "the U.S. House in AL-4". "Senate • AL" is a card's label; in
    a sentence in Slack or iMessage the bullet read as a glitch."""
    parts = _seat_parts(label)
    return f"the {parts[0]} in {parts[1]}" if parts else str(label or "")


def _role(person, post=False):
    from .record import seated

    parts = _seat_parts(person.get("officeLabel"))
    if not parts:
        office = person.get("officeLabel") or ""
        return (("in the 2026 race for " if post else "candidate for ") if person.get("isCandidate")
                else "member for " if seated(person) else "former member for ") + office
    body, where = parts
    if person.get("isCandidate"):
        # "Candidate for the U.S. Senate ...: Elected in November" was both.
        return (f"in the 2026 race for the {body} in {where}" if post
                else f"candidate for the {body} in {where}")
    return ("member" if seated(person) else "former member") + f" of the {body} for {where}"


def other_office(person, post=False):
    """KYC.otherOffice's words: where a member leaving their seat is going,
    from the curated, sourced ``otherOffice``; in the past tense once the
    results read are November's (``post``), as the dialog is from the day
    after Election Day. None for anyone else."""
    other = (not person.get("isCandidate") and person.get("otherOffice")) or None
    if not other or not other.get("text"):
        return None
    return ("Was the " if post else "") + other["text"]


def seat_up(person):
    """The dialog's "Seat up in <year>": a seated member whose seat is not
    on the 2026 ballot, said of the seat, never the person (rule 61)."""
    from .record import seated

    if seated(person) and not person.get("seatUp2026") and person.get("electionYear"):
        return f"Seat up in {person['electionYear']}"
    return None


def describe(person, by_id, races_by_id, post=False):
    """``(og title, description, status words)`` for a profile's share page:
    "<Name> (<party>), candidate for the U.S. House in AK-AL: Not on the
    2026 primary ballot, per Wikipedia's election results page."
    The status words are the dialog's (:func:`status_words`), with the
    source its badge credits; the seat is in words, since a card's bullet
    reads as a glitch in an unfurl."""
    name, party = person.get("name") or "", person.get("party") or ""
    status = status_words(person, by_id, races_by_id, post)
    prose = status_words(person, by_id, races_by_id, post, seat=seat_phrase)
    lead = f"{name} ({party})" if party else name
    said = []
    if prose:
        source = status_source(person, by_id)
        said.append(prose + (f", per {source}" if source else ""))
    other = other_office(person, post)
    if other:
        said.append(other)
    if not said and seat_up(person):
        said.append("seat up in " + str(person["electionYear"]))
    description = f"{lead}, {_role(person, post)}" + (": " + "; ".join(said) + "." if said else ".")
    return lead, description, status


def _race_link_words(person, race, by_id, races_by_id, post):
    """"The race" for someone in it; "The seat's 2026 race" for a member
    who is not (Byron Donalds's FL-19, which he is leaving to run for
    governor), and for a former member."""
    spec = standing(person, by_id, races_by_id, post)
    running = person.get("isCandidate") or race["id"] == person.get("contestRaceId")
    if running or (spec and not spec[1] and not person.get("formerMember")):
        return "The race"
    return f"The seat’s {race.get('year') or 2026} race"


def race_name(race):
    """A race's label, and that it is a special election where it is one
    (Florida's and Ohio's Senate seats, for the rest of a term)."""
    label = race.get("label") or race["id"]
    return label + (" (special election)" if race.get("special") else "")


def render_profile(person, host, by_id, races_by_id, post=False, alias=None):
    """``p/<id>.html``; with *alias*, the same page at ``p/<alias>.html``
    for an id the person's profile once had (rule 25's merged filings, a
    filer since seated), its canonical address their own page's."""
    from .pages import _possessive, state_name

    pid = person["id"]
    lead, description, status = describe(person, by_id, races_by_id, post)
    body = [f"<p>{_e(person.get('party') or '')} &middot; {_e(person.get('officeLabel') or '')}</p>"]
    if status:
        body.append(f'<p class="share-status"><strong>{_e(status)}</strong></p>')
        source = status_source(person, by_id)
        if source:
            body.append(f'<p class="share-source faint">Source: {_e(source)}.</p>')
    other = other_office(person, post)
    if other:
        found = person["otherOffice"]
        body.append(f'<p class="share-other">{_e(other)}. <span class="faint">Source: '
                    f'<a href="{_e(found.get("source") or "")}">the election&#x27;s Wikipedia page</a>, '
                    f"which marks the primary&#x27;s winner (read {_e(found.get('checked') or '')}).</span></p>")
    if seat_up(person):
        body.append(f'<p class="share-next">{_e(seat_up(person))}</p>')
    race = races_by_id.get(person.get("contestRaceId") or person.get("raceId") or "")
    if race:
        body.append(f'<p>{_e(_race_link_words(person, race, by_id, races_by_id, post))}: '
                    f'<a href="../{_e(race_path(race["id"]))}">{_e(race_name(race))}</a></p>')
    photo = og_photo(person, host)
    return _page(
        host, profile_path(alias or pid),
        canonical_path=profile_path(pid),
        title=_e(f"{person.get('name')} — Know Your Candidate"),
        description=_e(description),
        og_type="profile",
        og_title=_e(lead),
        image=photo,
        image_alt=f"Portrait of {person.get('name')}",
        kind="profile",
        heading=_e(person.get("name") or ""),
        body="\n".join(body),
        view=_e(f"../index.html#/profile/{pid}"),
        view_words=_e(f"Open {person.get('name')}'s full profile"),
        fallback=(f'<a href="{_e(_state_page(person.get("state")))}">'
                  f'{_e(_possessive(state_name(person.get("state"))))} page</a> '
                  "lists its members and races in plain text."),
    )


def race_people(race, by_id):
    """The people a race lists, in its order (rule 63): the seat's holder,
    then everyone filed for it, as ``KYC.cards.raceSection`` takes them."""
    out, seen = [], set()
    for pid in list(race.get("incumbentIds") or []) + list(race.get("candidateIds") or []):
        if pid in seen or pid not in by_id:
            continue
        seen.add(pid)
        out.append(by_id[pid])
    return out


def moved_from(race, person):
    """``KYC.movedFrom``: *race*'s record holder whose 2026 run was another
    race - the race they won and sit for now (``raceRole`` "winner"), or the
    race they ran in (``contestRaceId``, else ``raceStatusRace``). Once the
    new Congress sits a member seated for the seat they won has no other run
    on their profile, and the test of ``contestRaceId`` alone kept Andy Barr
    on KY-6's share page, "holds the seat: Elected in November", while he
    sat in the Senate (the January rehearsal of 2026-11-10)."""
    if person.get("isCandidate") or person["id"] not in (race.get("incumbentIds") or []):
        return False
    if person.get("raceRole") == "winner" and person.get("raceId") and person["raceId"] != race["id"]:
        return True
    run = person.get("contestRaceId") or person.get("raceStatusRace")
    return bool(run) and run != race["id"]


def sits_in(race, person):
    """``KYC.sitsIn``: *person* sits in *race*'s seat now - the race's record
    of its holder (``incumbent.seated``, races._sits_in), else a member whose
    seat is this race's; never sitting anywhere (rule 67)."""
    from .record import seated

    if not seated(person):
        return False
    inc = race.get("incumbent") or {}
    if inc.get("profileId") == person["id"]:
        return bool(inc.get("seated"))
    return person.get("raceId") == race["id"]


def seat_words(rid):
    """``KYC``'s seatWords: "Senate KY", "CA-40", "WY-AL"."""
    from .races import seat_label

    seat = seat_label(rid).replace(" • ", " ", 1)
    return seat[len("House "):] if seat.startswith("House ") else seat


def moved_clause(race, person, by_id, races_by_id=None, post=False):
    """``KYC.movedLine``'s clause for a holder :func:`moved_from` names: their
    own :func:`contest_clause` where their profile still holds the run, else
    the record's words - "was re-elected in CA-40 under the state's new
    district map", "won the race for Senate KY" - or "ran for" the race their
    result is for."""
    if person.get("contestLabel") and not person.get("isCandidate"):
        return contest_clause(person, by_id, races_by_id, post)
    won = (person.get("raceRole") == "winner" and bool(person.get("raceId"))
           and person["raceId"] != race["id"])
    seat = seat_words(person["raceId"] if won else
                      (person.get("contestRaceId") or person.get("raceStatusRace")))
    where = f"{seat} under the state’s new district map"
    moved = bool(person.get("renumbered"))
    if won:
        return f"was re-elected in {where}" if moved else f"won the race for {seat}"
    return ("ran " if post else "is running ") + (f"in {where}" if moved else f"for {seat}")


def moved_sentence(race, person, by_id, races_by_id=None, post=False):
    """``KYC.movedSentence``: "Held by X, who ..." while they sit in the seat,
    "X, who held this seat, ..." once they do not."""
    clause = moved_clause(race, person, by_id, races_by_id, post)
    name = person.get("name") or ""
    return (f"Held by {name}, who {clause}." if sits_in(race, person)
            else f"{name}, who held this seat, {clause}.")


def split_people(race, by_id):
    """``(held elsewhere, holder off its ballot, still in the race, no longer
    in it)``, as ``KYC.cards.racePeople`` splits a race: the holder running
    for another seat apart, the holder off this ballot apart (Thom Tillis did
    not run, and is nobody who "lost the primary, withdrew, or were not on the
    primary ballot", rule 92), and anyone else a result takes out of it
    (``offBallot`` of their own status) folded under the rest."""
    people = race_people(race, by_id)
    moved = [p for p in people if moved_from(race, p)]
    rest = [p for p in people if p not in moved]
    gone = [p for p in rest if p.get("raceStatus") in OFF_BALLOT]
    holders = [p for p in gone if not p.get("isCandidate")
               and p["id"] in (race.get("incumbentIds") or [])]
    return (moved, holders, [p for p in rest if p.get("raceStatus") not in OFF_BALLOT],
            [p for p in gone if p not in holders])


def contest_clause(person, by_id, races_by_id=None, post=False):
    """KYC.contestLine's clause, the words after "who": "is running for
    CA-6", "was elected to Senate KY in November", "ran for Senate IA and
    lost in November". The render suite asks the page code for every case
    (tests/fixtures/share_status_words.json), and *post* is
    :func:`post_election`'s."""
    seat = str(person.get("contestLabel")).replace(" • ", " ", 1)
    if seat.startswith("House "):
        seat = seat[len("House "):]
    status = contest_status(person, by_id)
    spec = standing(person, by_id, races_by_id or {}, post)
    stage = ("won" if status == "elected" else "lost" if status == "defeated"
             else "out" if status in OFF_BALLOT
             else "awaiting" if spec and "awaiting result" in spec[0]
             else "ran" if not status and post else "running")
    record = person if _own_record(person) else (by_id.get(person.get("alsoRunningId") or "") or {})
    december = _decided_round(status, record.get("raceStatusDecided"))
    when = "in November"
    lost = "lost in November"
    if december:
        long = december["long"]
        when = "in " + long[4:] if long.startswith("Won ") else long[len("Elected "):] \
            if long.startswith("Elected ") else when
        lost = "l" + long[1:]
    absent = ("was" if post else "is") + " not on its November ballot"
    ending = lost if stage == "lost" else absent if stage == "out" else ""
    waiting = "; the result is awaited" if stage == "awaiting" else ""
    if person.get("renumbered"):
        where = f"{seat} under the state’s new district map"
        if stage == "won":
            return f"was re-elected in {where} {when}"
        if stage == "running":
            return f"is running in {where}"
        return f"ran in {where}" + (f", and {ending}" if ending else waiting)
    if stage == "won":
        return f"was elected to {seat} {when}"
    if stage == "running":
        return f"is running for {seat}"
    return f"ran for {seat}" + (f" and {ending}" if ending else waiting)


def unprofiled(race):
    """``(names with no profile, [(name, profile id)] maybe a profile's)``,
    as KYC.cards.unprofiledNames splits the results' other nominees."""
    res = (race or {}).get("results") or {}
    maybe = res.get("maybeProfiled") or {}
    names = res.get("otherNominees") or []
    return [n for n in names if not maybe.get(n)], [(n, maybe[n]) for n in names if maybe.get(n)]


HOLDER_MARK = "holds the seat"


def holds(race, person):
    """*person* holds the seat *race* is for, and sits in it now (rule 67:
    a record incumbent who has left holds nothing, and one sitting for the
    seat they won elsewhere - Blake Moore, re-elected in UT-2 under the new
    map - does not hold UT-1: :func:`sits_in`)."""
    return person["id"] in (race.get("incumbentIds") or []) and sits_in(race, person)


def _item(person, by_id, races_by_id, post, root, indent, race=None):
    status = status_words(person, by_id, races_by_id, post)
    party = f" ({_e(person['party'])})" if person.get("party") else ""
    mark = f', <span class="share-holder">{HOLDER_MARK}</span>' if race and holds(race, person) else ""
    return (f'{indent}<li data-id="{_e(person["id"])}"><a href="{root}'
            f'{_e(profile_path(person["id"]))}">{_e(person.get("name") or "")}</a>{party}{mark}'
            + (f': <span class="share-standing">{_e(status)}</span>' if status else "") + "</li>")


def race_sources(race, by_id):
    """Who says where the people a race lists stand, each once, in the
    order they are first met: the credit the dialog's badge gives each."""
    moved, holders, running, out = split_people(race, by_id)
    seen = []
    for person in moved + holders + running + out:
        source = status_source(person, by_id)
        if source and source not in seen:
            seen.append(source)
    return seen


def _and(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def race_list_html(race, by_id, races_by_id, post=False, root="../", indent=""):
    """A race's people as plain lists, each linked to their share page with
    where they stand, split as the race's section on a state page splits
    them: the holder running elsewhere or off this ballot, the people still
    in it (the holder marked), those no longer in it, the November names with
    no profile here, and who says where each stands."""
    moved, holders, running, out = split_people(race, by_id)
    rows = [f'{indent}<p class="share-count">{_e(head_count(race, post))}.</p>']
    for person in moved:
        link = (f'<a href="{root}{_e(profile_path(person["id"]))}">'
                f'{_e(person.get("name") or "")}</a>')
        clause = _e(moved_clause(race, person, by_id, races_by_id, post))
        rows.append(f'{indent}<p class="race-held">'
                    + (f"Held by {link}, who {clause}." if sits_in(race, person)
                       else f"{link}, who held this seat, {clause}.") + "</p>")
    for person in holders:
        link = (f'<a href="{root}{_e(profile_path(person["id"]))}">'
                f'{_e(person.get("name") or "")}</a>')
        words = status_words(person, by_id, races_by_id, post)
        rows.append(f'{indent}<p class="race-held share-holder-off" data-id="{_e(person["id"])}">'
                    + (f"Held by {link}" if sits_in(race, person)
                       else f"{link} held this seat in the 2026 race")
                    + (f': <span class="share-standing">{_e(words)}</span>' if words else "") + ".</p>")
    rows.append(f'{indent}<ul class="share-list" data-race="{_e(race["id"])}">')
    rows += [_item(p, by_id, races_by_id, post, root, indent + "    ", race) for p in running]
    rows.append(f"{indent}</ul>")
    none, maybe = unprofiled(race)
    parties = ((race.get("results") or {}).get("otherParties")) or {}
    notes = []
    if none:
        notes.append("Also on the November ballot, " + _e(ballot_source(race)) +
                     ", with no FEC filing over $5,000 and so no profile here: " +
                     ", ".join(_e(n) + (f" ({_e(parties[n])})" if parties.get(n) else "")
                               for n in none) + ".")
    for name, pid in maybe:
        who = (by_id.get(pid) or {}).get("name") or "a candidate with a profile here"
        notes.append(f"Also named, {_e(ballot_source(race))}: {_e(name)}, who may be {_e(who)} "
                     "under another spelling; this site has not confirmed it.")
    if notes:
        rows.append(f'{indent}<p class="share-note">' + " ".join(notes) + "</p>")
    if out:
        rows += [f"{indent}<p>{len(out)} no longer in this race &mdash; lost the primary, "
                 "withdrew, or were not on the primary ballot:</p>",
                 f'{indent}<ul class="share-list share-out" data-race-out="{_e(race["id"])}">']
        rows += [_item(p, by_id, races_by_id, post, root, indent + "    ") for p in out]
        rows.append(f"{indent}</ul>")
    sources = race_sources(race, by_id)
    if sources:
        rows.append(f'{indent}<p class="share-source faint">Where each stands: per '
                    f"{_e(_and(sources))}.</p>")
    return "\n".join(rows)


def head_count(race, post=False):
    """KYC.cards' count badge: who is on a race's ballot, in the head's own
    words and number, in the past tense once the results read are November's
    (*post*). The render suite compares the two for every race."""
    res = race.get("results") or None
    unprofiled_names = len((res or {}).get("otherNominees") or [])
    count = race.get("candidateCount") or 0
    if race.get("contested") and not (count + unprofiled_names) and race.get("ballotUnknown"):
        return f"{race['ballotUnknown']} filed, ballot status not known"
    if race.get("contested"):
        running = count + unprofiled_names
        word = "candidate" if race.get("openSeat") or not (race.get("incumbentIds") or []) else "challenger"
        verb = ("" if not post else " was" if running == 1 else " were")
        return (f"{running} {word}{'' if running == 1 else 's'}"
                + (f"{verb} on the ballot" if race.get("settled") else ""))
    if race.get("settled") and res:
        gone = (res.get("eliminated") or 0) + (res.get("withdrawn") or 0) + (res.get("unlisted") or 0)
        return (("No challenger was on the ballot" if post else "No challenger on the ballot")
                + (f" · {gone} out" if gone else ""))
    if race.get("filedCount"):
        return f"{race['filedCount']} filed, none past $5k"
    return "Nobody has filed"


def _what(race):
    year = race.get("year") or ""
    return f"the {year} special election" if race.get("special") else f"the {year} race"


def describe_race(race, by_id, races_by_id, post=False):
    """A race's share description: the seat, who holds it, who is still in
    it with where each stands, and who says so."""
    label = race.get("label") or race["id"]
    moved, holders, running, _out = split_people(race, by_id)
    held = ""
    # The seat's holder only while they sit in it (rule 67): a record
    # incumbent who has left holds nothing.
    for person in moved:
        held = moved_sentence(race, person, by_id, races_by_id, post)
    inc = race.get("incumbent") or {}
    if not held and inc.get("seated") and inc.get("name"):
        # Under their profile's name where they have one, as the list
        # below names them: "David G. Valadao" beside "David Valadao".
        holder = next((p for p in running + holders if holds(race, p)), None)
        name = (holder or {}).get("name") or inc["name"]
        held = f"Held by {name}" + (f" ({inc['party']})." if inc.get("party") else ".")
    people = []
    for person in running:
        status = status_words(person, by_id, races_by_id, post, seat=seat_phrase)
        people.append(f"{person.get('name')}" + (f" ({person['party']})" if person.get("party")
                                                  else "") + (f": {status}" if status else ""))
    sources = race_sources(race, by_id)
    lead = " ".join(filter(None, [f"{_what(race)[0].upper()}{_what(race)[1:]} for {label}.", held]))
    if not people:
        return lead
    # Who says where each stands comes before the list, and the list stops
    # at DESCRIPTION_MAX with how many more it leaves for the page: an
    # unfurler cuts a description at 200-300 characters, and on 62 race
    # pages it cut the later candidates mid-sentence and the source credit
    # always (PR #123 review). The first person is always named.
    head = lead + (f" Where each stands, per {_and(sources)}: " if sources else " ")
    shown = people[:1]
    for i, words in enumerate(people[1:], start=1):
        rest = len(people) - i - 1
        tail = f"; and {rest} more in this race." if rest else "."
        if len(head + "; ".join(shown + [words]) + tail) > DESCRIPTION_MAX:
            break
        shown.append(words)
    more = len(people) - len(shown)
    return head + "; ".join(shown) + (f"; and {more} more in this race." if more else ".")


def render_race(race, host, by_id, races_by_id, post=False):
    """``r/<raceId>.html``."""
    from .pages import _possessive, state_name

    label = race.get("label") or race["id"]
    year = race.get("year") or ""
    state = race.get("state") or ""
    whose = _possessive(state_name(state))
    what = _what(race)
    return _page(
        host, race_path(race["id"]),
        title=_e(f"{label}, {year}{' special election' if race.get('special') else ''} — Know Your Candidate"),
        description=_e(describe_race(race, by_id, races_by_id, post)),
        og_type="website",
        og_title=_e(f"{label}: {what}"),
        image=None,
        kind="race",
        heading=_e(f"{label}: {what}"),
        body=race_list_html(race, by_id, races_by_id, post),
        view=_e(f"{_state_page(state)}#race-{race['id']}"),
        view_words=_e(f"Open this race on {whose} page"),
        fallback=(f'<a href="{_e(_state_page(state))}">{_e(whose)} page</a> '
                  "lists every race there in plain text."),
    )


def render_all(profiles, races, host, summary=None):
    """``{path relative to the site: html}`` for every profile and race."""
    by_id = {p["id"]: p for p in profiles}
    races = list(races or [])
    races_by_id = {r["id"]: r for r in races}
    post = post_election(summary)
    out = {}
    for person in profiles:
        out[profile_path(person["id"])] = render_profile(person, host, by_id, races_by_id, post)
    for race in races:
        out[race_path(race["id"])] = render_race(race, host, by_id, races_by_id, post)
    return out


def aliases(profiles):
    """``{old id: profile}``: the ids a profile answers to besides its own,
    as ``KYC.byId`` resolves them - every merged filing (``otherFecIds``,
    rule 25), a member's own filing (a filer since seated), a curated id
    (``otherIds``) - first come first served, and never a real profile's
    id."""
    real = {p["id"] for p in profiles}
    out = {}
    for person in profiles:
        fec = person.get("fecCandidateId")
        own = [fec] if fec and person["id"] != "FEC_" + fec else []
        names = (["FEC_" + other for other in (person.get("otherFecIds") or []) + own]
                 + list(person.get("otherIds") or []))
        for alias in names:
            if alias not in real and alias not in out:
                out[alias] = person
    return out


def render_aliases(profiles, races, host, summary=None):
    """``{p/<old id>.html: html}``: a profile's share page at every id it
    answers to besides its own. Written only over a page already there
    (``emit.write_state_pages``): when filings fold or a filer is seated,
    the id a link was shared under stops being a profile's, and its page
    would have become a 404. Its canonical address is the profile's own
    page, and it is not in the sitemap."""
    by_id = {p["id"]: p for p in profiles}
    races_by_id = {r["id"]: r for r in races or []}
    post = post_election(summary)
    return {profile_path(alias): render_profile(person, host, by_id, races_by_id, post, alias=alias)
            for alias, person in aliases(profiles).items()}
