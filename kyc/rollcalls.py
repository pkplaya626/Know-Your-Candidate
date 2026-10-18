"""How each member voted: the roll calls of a Congress, from the official
records.

A reader asks how their representative voted on a bill, and the profile
answered with one DW-NOMINATE score and three outbound links (PERSONA-15,
PROFILES-25). The votes are public, in two official records:

- the House: the Clerk's roll-call XML, one file a vote
  (``clerk.house.gov/evs/<year>/roll<NNN>.xml``), each recorded vote keyed
  by the member's bioguide id;
- the Senate: the Secretary's LIS XML (``senate.gov/legislative/LIS/
  roll_call_votes/vote<congress><session>/vote_<congress>_<session>_<NNNNN>.xml``),
  each vote keyed by the senator's LIS member id, which congress-legislators
  maps to their bioguide id.

``python build_profile_site.py votes`` reads them into
``data/roll_calls.json``: politely, one request a second, saving as it goes,
and resuming where the last run stopped. The House is read up the numbers of
each year until the Clerk answers with something that is not that roll
call - it answers a number it has not posted with HTTP 200 and an "Error
sanitizing file" note, which is not a file (rule 52), and concludes nothing
(rule 8): the next run asks again. The Senate is read from each session's
vote menu.

A vote reaches a profile only by an id the record holds (rule 17), and only
inside a term the member served in that chamber, by congress-legislators'
dates: a vote cast before a member was seated, or under another member's id,
never appears on their profile. Each id's own words in the record - the
state, the surname - are checked against the member the id names (rule 20);
an id that disagrees gives nobody its votes, and the build says so. A member
who left keeps the votes they cast (rule 67): the terms read include
legislators-historical's.

Nothing is chosen: no "key votes" list. The page shows the most recent votes
and searches all of a member's by bill title or number; which votes matter is
the reader's call, not this site's.
"""

import datetime
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from . import cycle

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "roll_calls.json")

HOUSE_XML = "https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"
HOUSE_PAGE = "https://clerk.house.gov/Votes/{year}{roll}"
HOUSE_INDEX = "https://clerk.house.gov/Votes"
SENATE_MENU = ("https://www.senate.gov/legislative/LIS/roll_call_lists/"
               "vote_menu_{congress}_{session}.xml")
SENATE_XML = ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/"
              "vote_{congress}_{session}_{vote:05d}.xml")
SENATE_PAGE = ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/"
               "vote_{congress}_{session}_{vote:05d}.htm")
SENATE_INDEX = "https://www.senate.gov/legislative/votes_new.htm"
LEGISLATORS_CURRENT = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
LEGISLATORS_HISTORICAL = ("https://unitedstates.github.io/congress-legislators/"
                          "legislators-historical.json")

# A Speaker who does not vote has not missed a vote the way a member has:
# the House's own rule, read from the Rules of the House for the 119th
# Congress (as amended) on 2026-10-18. The page quotes it beside the count of
# roll calls the Clerk's record names the member as Speaker in.
SPEAKER_RULE = {
    "cite": "House Rule I, clause 7",
    "words": ("The Speaker is not required to vote in ordinary legislative proceedings, "
              "except when such vote would be decisive or when the House is engaged in "
              "voting by ballot."),
    "url": ("https://rules.house.gov/sites/evo-subsites/rules.house.gov/files/documents/"
            "houserules119thupdated.pdf"),
    "read": "2026-10-18",
}

# A delegate, and Puerto Rico's Resident Commissioner, is listed only in the
# Committee of the Whole's roll calls: the House's rule, read from the same
# document on the same day. The page quotes it beside such a member's count.
DELEGATE_RULE = {
    "cite": "House Rule III, clause 3(a)",
    "words": ("In a Committee of the Whole House on the State of the Union, each Delegate "
              "and the Resident Commissioner shall possess the same powers and privileges "
              "as Members of the House."),
    "url": SPEAKER_RULE["url"],
    "read": "2026-10-18",
}

USER_AGENT = ("know-your-candidate/2.1 (open-source civic data project; "
              "https://github.com/pkplaya626/Know-Your-Candidate)")
# Neither office publishes a limit. One request a second to each, never
# faster, and a run that is refused stops and keeps what it has (rule 8).
PAUSE = 1.0
SAVE_EVERY = 25
# The build warns once the record is this old while its Congress sits.
STALE_DAYS = 21

# One character a vote, in the order of the chamber's roll calls, so a
# member's whole record is a short string. The record's own words for each;
# anything else it writes (the candidates in an election of the Speaker) is
# given a character of its own in the file's table.
CODES = {"Yea": "Y", "Nay": "N", "Aye": "A", "No": "O", "Present": "P",
         "Not Voting": "V", "Guilty": "G", "Not Guilty": "U"}
EXTRA_CODES = "abcdefghijklmnopqrstuvwxyz0123456789"
NOT_LISTED = "."
NOT_VOTING = "Not Voting"

CHAMBERS = ("house", "senate")
_BIOGUIDE = re.compile(r"^[A-Z]\d{6}$")
_LIS = re.compile(r"^S\d{3}$")


class RollCallError(RuntimeError):
    """A record that cannot be read as the roll call it was asked for."""


class NotARollCall(RollCallError):
    """An answer that is not a roll call at all: the Clerk's note for a
    number it has not posted, a bot wall. It concludes nothing (rule 8)."""


# ------------------------------------------------------------------ parsing

def _text(node, path):
    found = node.find(path) if node is not None else None
    return " ".join((found.text or "").split()) if found is not None and found.text else ""


def fold(text):
    """Lower case, accents and punctuation gone: "Ocasio-Cortez" and
    "ocasio cortez" alike."""
    normalized = unicodedata.normalize("NFD", str(text or ""))
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped.lower()).split())


def _house_date(value):
    try:
        return datetime.datetime.strptime(value.strip(), "%d-%b-%Y").date().isoformat()
    except ValueError as exc:
        raise RollCallError(f"an action date the record writes as {value!r}") from exc


def _senate_when(value):
    words = " ".join(str(value or "").split())
    try:
        moment = datetime.datetime.strptime(words, "%B %d, %Y, %I:%M %p")
    except ValueError as exc:
        raise RollCallError(f"a vote date the record writes as {value!r}") from exc
    return moment.date().isoformat(), moment.strftime("%H:%M")


def _root(raw, tag, what):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise NotARollCall(f"{what} is not XML ({exc})") from exc
    if root.tag != tag:
        words = " ".join("".join(root.itertext()).split())[:120]
        raise NotARollCall(f"{what} is not a roll call: <{root.tag}> {words}")
    return root


def parse_house(raw, year, roll, congress):
    """One Clerk roll call: ``(roll, people)``. *people* maps each id to the
    record's own words for them (name, state, party). Raises
    :class:`NotARollCall` for an answer that is not one, and
    :class:`RollCallError` for one that is not the roll call asked for."""
    what = f"House roll call {roll} of {year}"
    root = _root(raw, "rollcall-vote", what)
    meta = root.find("vote-metadata")
    if meta is None:
        raise RollCallError(f"{what} carries no vote-metadata")
    try:
        number = int(_text(meta, "rollcall-num"))
        found_congress = int(_text(meta, "congress"))
    except ValueError as exc:
        raise RollCallError(f"{what}: no roll-call number or Congress") from exc
    if number != roll or found_congress != congress:
        raise RollCallError(f"{what}: the file is roll call {number} of the "
                            f"{found_congress}th Congress")
    session = re.match(r"\d+", _text(meta, "session") or "0").group()
    date = _house_date(_text(meta, "action-date"))
    if not date.startswith(str(year)):
        raise RollCallError(f"{what}: dated {date}")
    clock = meta.find("action-time")
    # "Amendment 3 Scott of Virginia Amendment No. 3": the number and the
    # Clerk's words for whose it is (shown by _amendment_words).
    amendment = " ".join(x for x in (_text(meta, "amendment-num") and
                                     "Amendment " + _text(meta, "amendment-num"),
                                     _text(meta, "amendment-author")) if x)
    votes, people, speaker = {}, {}, None
    for recorded in root.iter("recorded-vote"):
        member = recorded.find("legislator")
        vid = ((member.get("name-id") if member is not None else "") or "").strip().upper()
        cast = _text(recorded, "vote")
        if not _BIOGUIDE.match(vid) or not cast:
            raise RollCallError(f"{what}: a recorded vote with no member id or no vote")
        if vid in people:
            raise RollCallError(f"{what}: {vid} is recorded twice")
        people[vid] = {"name": member.get("unaccented-name") or " ".join((member.text or "").split()),
                       "state": member.get("state") or "", "party": member.get("party") or ""}
        if member.get("role") == "speaker":
            speaker = vid
        votes.setdefault(cast, []).append(vid)
    if not people:
        raise RollCallError(f"{what} records no votes")
    record = {
        "n": roll, "year": int(year), "session": int(session), "date": date,
        "time": (clock.get("time-etz") if clock is not None else "") or "",
        "question": _text(meta, "vote-question"),
        "measure": _text(meta, "legis-num"),
        "title": _text(meta, "vote-desc"),
        "amendment": amendment,
        "result": _text(meta, "vote-result"),
        "votes": {cast: " ".join(sorted(ids)) for cast, ids in sorted(votes.items())},
    }
    if speaker:
        record["speaker"] = speaker
    return record, people


def parse_senate(raw, congress, session, vote):
    """One Senate roll call: ``(roll, people)``, as :func:`parse_house`."""
    what = f"Senate vote {vote} of session {session}"
    root = _root(raw, "roll_call_vote", what)
    try:
        found = (int(_text(root, "congress")), int(_text(root, "session")),
                 int(_text(root, "vote_number")))
    except ValueError as exc:
        raise RollCallError(f"{what}: no Congress, session or vote number") from exc
    if found != (congress, session, vote):
        raise RollCallError(f"{what}: the file is vote {found[2]} of session {found[1]} of "
                            f"the {found[0]}th Congress")
    date, clock = _senate_when(_text(root, "vote_date"))
    document = root.find("document")
    amendment = root.find("amendment")
    number = _text(amendment, "amendment_number")
    purpose = _text(amendment, "amendment_purpose")
    votes, people = {}, {}
    for member in root.iter("member"):
        vid = _text(member, "lis_member_id").upper()
        cast = _text(member, "vote_cast")
        if not _LIS.match(vid) or not cast:
            raise RollCallError(f"{what}: a vote with no member id or no vote")
        if vid in people:
            raise RollCallError(f"{what}: {vid} is recorded twice")
        # "Last, First", the surname first as the Clerk writes it.
        people[vid] = {"name": ", ".join(x for x in (_text(member, "last_name"),
                                                    _text(member, "first_name")) if x),
                       "state": _text(member, "state"), "party": _text(member, "party")}
        votes.setdefault(cast, []).append(vid)
    if not people:
        raise RollCallError(f"{what} records no votes")
    record = {
        "n": vote, "session": session,
        "year": int(_text(root, "congress_year") or date[:4]),
        "date": date, "time": clock,
        "question": _text(root, "question") or _text(root, "vote_question_text"),
        # An amendment's vote names the measure it would amend there.
        "measure": (_text(document, "document_name") or
                    _text(amendment, "amendment_to_document_number")),
        "title": (_text(document, "document_short_title") or _text(document, "document_title") or
                  _text(amendment, "amendment_to_document_short_title")),
        "voteTitle": _text(root, "vote_title"),
        "amendment": " ".join(x for x in (number, number and purpose and
                                          purpose != "No Statement of Purpose on File." and
                                          f"({purpose})") if x),
        "result": _text(root, "vote_result_text") or _text(root, "vote_result"),
        "votes": {cast: " ".join(sorted(ids)) for cast, ids in sorted(votes.items())},
    }
    return record, people


def parse_senate_menu(raw, congress, session):
    """The vote numbers a session's menu lists."""
    what = f"the Senate's vote menu for session {session}"
    root = _root(raw, "vote_summary", what)
    try:
        found = (int(_text(root, "congress")), int(_text(root, "session")))
    except ValueError as exc:
        raise RollCallError(f"{what} names no Congress or session") from exc
    if found != (congress, session):
        raise RollCallError(f"{what} is session {found[1]} of the {found[0]}th Congress")
    numbers = []
    for node in root.iter("vote_number"):
        try:
            numbers.append(int(node.text))
        except (TypeError, ValueError) as exc:
            raise RollCallError(f"{what} lists a vote number {node.text!r}") from exc
    return sorted(set(numbers))


# ------------------------------------------------------------------ members

def congress_dates(congress):
    """``(first day, first day of the next)`` as ISO dates."""
    return (cycle.congress_start(congress).isoformat(),
            cycle.congress_start(congress + 1).isoformat())


def build_members(rows, congress):
    """Everyone with a term in *congress*, either chamber, from
    congress-legislators' rows (current and historical together): their
    LIS id and each term's chamber, state and dates. The table every vote
    is attributed through."""
    start, end = congress_dates(congress)
    out = {}
    for entry in rows or []:
        ids = entry.get("id") or {}
        bioguide = str(ids.get("bioguide") or "").upper()
        if not _BIOGUIDE.match(bioguide):
            continue
        terms = []
        for term in entry.get("terms") or []:
            kind = term.get("type")
            first, last = str(term.get("start") or ""), str(term.get("end") or "")
            if kind not in ("rep", "sen") or not first or not last:
                continue
            # A term that ended on the day this Congress began is the last one's.
            if first < end and last > start:
                terms.append({"chamber": "Senate" if kind == "sen" else "House",
                              "state": term.get("state") or "",
                              "start": first, "end": last})
        if not terms:
            continue
        name = entry.get("name") or {}
        full = name.get("official_full") or " ".join(
            x for x in (name.get("first"), name.get("last")) if x)
        person = {"name": full, "last": name.get("last") or "",
                  "terms": sorted(terms, key=lambda t: t["start"])}
        if ids.get("lis"):
            person["lis"] = str(ids["lis"]).upper()
        out[bioguide] = person
    return out


# ------------------------------------------------------------------ reading

def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def empty_cache(congress):
    return {"congress": congress, "members": {},
            "house": {"rolls": [], "seen": {}, "read": None},
            "senate": {"rolls": [], "seen": {}, "read": None}}


def _note_people(seen, people, date):
    """Keep each id's own words in the record, with the first and last day
    they were written so: how an id that names two people is caught."""
    for vid, who in people.items():
        rows = seen.setdefault(vid, [])
        key = [who.get("name", ""), who.get("state", ""), who.get("party", "")]
        for row in rows:
            if row[:3] == key:
                row[3] = min(row[3], date)
                row[4] = max(row[4], date)
                break
        else:
            rows.append(key + [date, date])
            rows.sort()


def _add(chamber_cache, record, people):
    rolls = chamber_cache["rolls"]
    key = (record["session"], record["n"])
    rolls[:] = [r for r in rolls if (r["session"], r["n"]) != key]
    rolls.append(record)
    rolls.sort(key=lambda r: (r["session"], r["n"]))
    _note_people(chamber_cache["seen"], people, record["date"])


def _years(congress, today):
    start, _ = congress_dates(congress)
    first = int(start[:4])
    return [y for y in (first, first + 1) if y <= today.year]


def read_house(cache, today, read=_get, pause=PAUSE, limit=None, log=print, save=None):
    """Read the Clerk's roll calls this cache lacks, year by year, up each
    year's numbers until an answer that is not the next roll call. Returns
    the number read. A refusal or a failure stops the run with what it has."""
    congress = cache["congress"]
    house = cache["house"]
    count = 0
    for year in _years(congress, today):
        have = {r["n"] for r in house["rolls"] if r["year"] == year}
        top = max(have) if have else 0
        wanted = [n for n in range(1, top + 1) if n not in have]
        roll = top + 1
        while True:
            if limit is not None and count >= limit:
                return count
            number = wanted.pop(0) if wanted else roll
            url = HOUSE_XML.format(year=year, roll=number)
            try:
                record, people = parse_house(read(url), year, number, congress)
            except NotARollCall as exc:
                if number in have or number < top:
                    raise RollCallError(f"{url}: {exc}") from exc
                log(f"  House {year}: through roll call {number - 1} ({exc})")
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and number > top:
                    log(f"  House {year}: through roll call {number - 1} (404)")
                    break
                raise RollCallError(f"{url}: HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise RollCallError(f"{url}: {exc}") from exc
            _add(house, record, people)
            have.add(number)
            top = max(top, number)
            if not wanted:
                roll = top + 1
            count += 1
            if save and count % SAVE_EVERY == 0:
                save(cache)
            time.sleep(pause)
    house["read"] = today.isoformat()
    return count


def read_senate(cache, today, read=_get, pause=PAUSE, limit=None, log=print, save=None):
    """Read the Senate's roll calls this cache lacks, from each session's
    vote menu. Returns the number read."""
    congress = cache["congress"]
    senate = cache["senate"]
    count = 0
    for session, year in enumerate(_years(congress, today), start=1):
        url = SENATE_MENU.format(congress=congress, session=session)
        try:
            listed = parse_senate_menu(read(url), congress, session)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RollCallError(f"{url}: {exc}") from exc
        time.sleep(pause)
        have = {r["n"] for r in senate["rolls"] if r["session"] == session}
        missing = [n for n in listed if n not in have]
        log(f"  Senate session {session} ({year}): the menu lists {len(listed)} votes, "
            f"{len(missing)} not yet read")
        for number in missing:
            if limit is not None and count >= limit:
                return count
            url = SENATE_XML.format(congress=congress, session=session, vote=number)
            try:
                record, people = parse_senate(read(url), congress, session, number)
            except urllib.error.HTTPError as exc:
                raise RollCallError(f"{url}: HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise RollCallError(f"{url}: {exc}") from exc
            except NotARollCall as exc:
                raise RollCallError(f"{url}: {exc}") from exc
            _add(senate, record, people)
            count += 1
            if save and count % SAVE_EVERY == 0:
                save(cache)
            time.sleep(pause)
    senate["read"] = today.isoformat()
    return count


# ------------------------------------------------------------------ cache

def save_cache(cache, root="."):
    """One roll call a line, so a run that adds votes is a diff of those
    lines and nothing else."""
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dumps = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True,  # noqa: E731
                                     separators=(",", ":"))
    lines = ["{", f'"congress":{dumps(cache["congress"])},', '"members":{']
    members = sorted((cache.get("members") or {}).items())
    lines += [f"{dumps(k)}:{dumps(v)}" + ("," if i < len(members) - 1 else "")
              for i, (k, v) in enumerate(members)]
    lines.append("},")
    if cache.get("read"):
        lines.append(f'"read":{dumps(cache["read"])},')
    for c, chamber in enumerate(CHAMBERS):
        part = cache.get(chamber) or {}
        lines.append(f'{dumps(chamber)}:{{"read":{dumps(part.get("read"))},"rolls":[')
        rolls = part.get("rolls") or []
        lines += [dumps(r) + ("," if i < len(rolls) - 1 else "") for i, r in enumerate(rolls)]
        lines.append('],"seen":{')
        seen = sorted((part.get("seen") or {}).items())
        lines += [f"{dumps(k)}:{dumps(v)}" + ("," if i < len(seen) - 1 else "")
                  for i, (k, v) in enumerate(seen)]
        lines.append("}}" + ("," if c < len(CHAMBERS) - 1 else ""))
    lines.append("}")
    text = "\n".join(lines) + "\n"
    json.loads(text)                      # never write a file that does not read back
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------------ the page

def _surname_in(person, words):
    """The record's surname for an id is the member's: every word of it a
    word of their name. The record writes a surname, with a state or a
    first name where two members share it ("Johnson (LA)", "Davis, Danny
    K."), and sometimes only part of it ("Perez" for Marie Gluesenkamp
    Perez)."""
    surname = fold(re.sub(r"\([^)]*\)", " ", str(words or "")).split(",")[0])
    known = set(fold(person.get("name", "") + " " + person.get("last", "")).split())
    return bool(surname) and set(surname.split()) <= known


# The Clerk writes the state of a delegate and of the Resident Commissioner as
# "XX": they vote only in the Committee of the Whole, and roll call 79 of 2025
# (an amendment to H.R. 1048, 2025-03-27) lists 'Norton', 'Plaskett',
# 'Moylan', 'King-Hinds', 'Radewagen' and 'Hernandez' with state "XX" (read
# 2026-10-18). Only for a member who sits for one of these.
DELEGATE_STATE = "XX"
DELEGATIONS = frozenset({"AS", "DC", "GU", "MP", "PR", "VI"})


def _identity_problems(chamber, vid, bioguide, person, seen):
    """What is wrong with the record's words for *vid* as *person*: a state
    they never served for in this chamber, or a name without their surname."""
    states = {t["state"] for t in person["terms"] if t["chamber"] == chamber}
    if chamber == "House" and states & DELEGATIONS:
        states = states | {DELEGATE_STATE}
    out = []
    for name, state, _party, first, last in seen.get(vid) or []:
        if state not in states:
            out.append(f"{vid} ({name}, {state}, {first} to {last}) is {person['name']} "
                       f"({bioguide}), who served for {', '.join(sorted(states)) or 'no state'} "
                       f"in the {chamber}")
        elif not _surname_in(person, name):
            out.append(f"{vid} is written {name!r} ({first} to {last}); {bioguide} is "
                       f"{person['name']}")
    return out


def _serving(person, chamber, date):
    return any(t["chamber"] == chamber and t["start"] <= date <= t["end"]
               for t in person["terms"])


def _amendment_words(text):
    """A House amendment as the page says it: the Clerk's words for it
    ("Scott of Virginia Amendment No. 3") where they carry its number,
    else the number before them ("Amendment 1: Foxx of North Carolina
    Amendment")."""
    match = re.match(r"^Amendment (\S+) (.+)$", text or "")
    if not match:
        return text or ""
    number, words = match.groups()
    if re.search(r"\bNo\.? " + re.escape(number) + r"\b", words):
        return words
    return f"Amendment {number}: {words}"


def _roll_row(chamber, congress, roll):
    if chamber == "house":
        rid = f"{roll['year']}-{roll['n']}"
        url = HOUSE_PAGE.format(year=roll["year"], roll=roll["n"])
        result = roll["result"]
        votes = roll["votes"]
        yes = sum(len(votes.get(k, "").split()) for k in ("Yea", "Aye"))
        no = sum(len(votes.get(k, "").split()) for k in ("Nay", "No"))
        if result and (yes or no):
            # Counted from the record's own lines: the Clerk's totals are the
            # same lines added up.
            result = f"{result} ({yes}-{no})"
        detail = _amendment_words(roll.get("amendment"))
    else:
        rid = f"{roll['session']}-{roll['n']}"
        url = SENATE_PAGE.format(congress=congress, session=roll["session"], vote=roll["n"])
        result = roll["result"]
        detail = roll.get("amendment") or ""
        if roll.get("voteTitle") and fold(roll["voteTitle"]) != fold(roll.get("title")):
            detail = "; ".join(x for x in (roll["voteTitle"], detail) if x)
    return [rid, roll["date"], roll["question"], roll["measure"], roll["title"], detail,
            result, url]


def chamber_payload(cache, chamber, problems=None):
    """What ``data/votes/<chamber>.js`` carries, and what was refused.

    ``rolls`` are the chamber's roll calls in order, each ``[id, date,
    question, measure, title, detail, result, url]`` as the record gives
    them; ``members`` maps a bioguide id to a string with one character a
    roll call (``codes`` says which vote; ``.`` none recorded for them), the
    number of roll calls they are listed in and the number they did not vote
    in. Only votes attributed by id, inside a term (module docstring)."""
    problems = problems if problems is not None else []
    congress = cache["congress"]
    part = cache.get(chamber) or {}
    rolls = sorted(part.get("rolls") or [], key=lambda r: (r["session"], r["n"]))
    members = cache.get("members") or {}
    title = "House" if chamber == "house" else "Senate"
    by_lis = {p["lis"]: b for b, p in members.items() if p.get("lis")}

    def bioguide_of(vid):
        return vid if chamber == "house" else by_lis.get(vid)

    from .overrides import ROLL_CALL_NON_MEMBERS

    refused_ids, known = {}, set()
    for vid in sorted(part.get("seen") or {}):
        bioguide = bioguide_of(vid)
        person = members.get(bioguide) if bioguide else None
        if not person and vid in ROLL_CALL_NON_MEMBERS:
            known.add(vid)
            continue
        if not person:
            refused_ids[vid] = (f"{vid} ({'; '.join(r[0] + ', ' + r[1] for r in part['seen'][vid])})"
                                f" is not in congress-legislators' {title} for this Congress")
            continue
        if vid in ROLL_CALL_NON_MEMBERS:
            problems.append(("warn", "votes-override-stale",
                             f"overrides.ROLL_CALL_NON_MEMBERS names {vid}, whom "
                             f"congress-legislators now lists as {person['name']}",
                             [ROLL_CALL_NON_MEMBERS[vid]]))
        wrong = _identity_problems(title, vid, bioguide, person, part["seen"])
        if wrong:
            refused_ids[vid] = "; ".join(wrong)
    if refused_ids:
        problems.append(("warn", "votes-unattributed",
                         f"{len(refused_ids)} {title} member id(s) in the roll calls are given to "
                         "nobody: the record's words for them do not fit the member the id names",
                         sorted(refused_ids.values())))

    codes = dict(CODES)
    extra = sorted({cast for r in rolls for cast in r["votes"] if cast not in codes})
    if len(extra) > len(EXTRA_CODES):
        raise RollCallError(f"{len(extra)} kinds of {title} vote beyond the usual ones")
    codes.update(zip(extra, EXTRA_CODES))

    strings, outside, speaker_rolls = {}, {}, {}
    for index, roll in enumerate(rolls):
        for cast, ids in roll["votes"].items():
            for vid in ids.split():
                if vid in refused_ids or vid in known:
                    continue
                bioguide = bioguide_of(vid)
                person = members[bioguide]
                if not _serving(person, title, roll["date"]):
                    outside.setdefault(bioguide, []).append(roll["date"])
                    continue
                row = strings.setdefault(bioguide, [NOT_LISTED] * len(rolls))
                row[index] = codes[cast]
        if roll.get("speaker"):
            speaker_rolls.setdefault(bioguide_of(roll["speaker"]), set()).add(index)
    if outside:
        problems.append(("warn", "votes-outside-term",
                         f"{sum(len(v) for v in outside.values())} {title} vote(s) are dated "
                         "outside every term congress-legislators gives the member, and are not "
                         "shown", [f"{b} {members[b]['name']}: {len(d)} from {min(d)} to {max(d)}"
                                   for b, d in sorted(outside.items())]))

    not_voting = codes[NOT_VOTING]
    out_members = {}
    for bioguide, row in sorted(strings.items()):
        person = members[bioguide]
        listed = sum(1 for c in row if c != NOT_LISTED)
        missed = sum(1 for c in row if c == not_voting)
        entry = {"votes": "".join(row), "listed": listed, "notVoting": missed,
                 "share": round(100.0 * missed / listed, 1) if listed else 0.0}
        # Roll calls held while they served that the record does not list
        # them in at all: never counted as missed, and said on the page. The
        # Clerk lists a Speaker who does not vote nowhere; a member seated or
        # gone on the day of a roll call may be absent from it; a delegate
        # is listed only in the Committee of the Whole's.
        serving = sum(1 for r in rolls if _serving(person, title, r["date"]))
        if serving > listed:
            entry["unlisted"] = serving - listed
        if title == "House" and {t["state"] for t in person["terms"]} & DELEGATIONS:
            entry["delegate"] = True
        chair = speaker_rolls.get(bioguide) or set()
        if chair:
            entry["asSpeaker"] = len(chair)
            entry["speakerNotVoting"] = sum(1 for i in chair if row[i] == not_voting)
        out_members[bioguide] = entry

    payload = {
        "congress": congress,
        "chamber": title,
        "read": part.get("read"),
        "count": len(rolls),
        "first": rolls[0]["date"] if rolls else None,
        "last": rolls[-1]["date"] if rolls else None,
        "source": ({"name": "Office of the Clerk, U.S. House of Representatives",
                    "url": HOUSE_INDEX} if chamber == "house" else
                   {"name": "U.S. Senate, Legislative Information System", "url": SENATE_INDEX}),
        "codes": {code: words for words, code in sorted(codes.items(), key=lambda kv: kv[1])
                  if any(code in row for row in strings.values())},
        "notVoting": NOT_VOTING,
        "rolls": [_roll_row(chamber, congress, r) for r in rolls],
        "members": out_members,
    }
    if chamber == "house":
        payload["speakerRule"] = SPEAKER_RULE
        payload["delegateRule"] = DELEGATE_RULE
    return payload


def payloads(cache, problems=None):
    """``{chamber: payload}`` for both chambers (empty ones when there is no
    cache, so a page always has a file to load and says the record is not
    read)."""
    if not cache:
        cache = empty_cache(cycle.electing_congress() - 1)
    return {chamber: chamber_payload(cache, chamber, problems) for chamber in CHAMBERS}


def problems(cache, snapshot=None, today=None):
    """What a build says about the cache: ``[(level, code, message, detail)]``."""
    out = []
    if not cache:
        return [("warn", "votes-missing", f"no {CACHE_PATH}; run 'votes' to read the roll "
                 "calls (profiles show no votes until then)", [])]
    payloads(cache, out)
    today = today or datetime.date.today()
    start, end = congress_dates(cache["congress"])
    for chamber in CHAMBERS:
        read = (cache.get(chamber) or {}).get("read")
        sitting = today.isoformat() < end
        if not read:
            out.append(("warn", "votes-unread", f"the {chamber} roll calls have not been read; "
                        "run 'votes'", []))
        elif sitting and (today - datetime.date.fromisoformat(read)).days > STALE_DAYS:
            out.append(("warn", "votes-stale", f"the {chamber} roll calls were last read on "
                        f"{read}; run 'votes'", []))
    if snapshot:
        members = cache.get("members") or {}
        behind = [f"{p['bioguide']} {p.get('name')}" for p in snapshot.get("legislators") or []
                  if p.get("termStart", "") < end and p.get("bioguide") not in members]
        if behind:
            out.append(("warn", "votes-members-behind",
                        f"{len(behind)} sitting member(s) are not in the roll calls' table of "
                        "members, whose votes are given to nobody until 'votes' reads it again",
                        behind))
    return out


def fetch(previous=None, today=None, chambers=CHAMBERS, read=_get, pause=PAUSE, limit=None,
          log=print, save=None, members_rows=None):
    """Bring *previous* (or a new cache) up to date: the table of members,
    then each chamber's roll calls. A source that fails keeps what was read
    and raises :class:`RollCallError` after saving, naming it."""
    today = today or datetime.date.today()
    congress = cycle.electing_congress() - 1
    cache = previous if previous and previous.get("congress") == congress else \
        empty_cache(congress)
    if members_rows is None:
        try:
            members_rows = (json.loads(read(LEGISLATORS_CURRENT).decode("utf-8")) +
                            json.loads(read(LEGISLATORS_HISTORICAL).decode("utf-8")))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            if not cache["members"]:
                raise RollCallError(f"congress-legislators could not be read: {exc}") from exc
            log(f"  [warn] congress-legislators could not be read ({exc}); "
                "keeping the table of members read before")
            members_rows = None
    if members_rows is not None:
        table = build_members(members_rows, congress)
        if not table:
            raise RollCallError("congress-legislators lists nobody in this Congress")
        cache["members"] = table
    failures = []
    for chamber in chambers:
        reader = read_house if chamber == "house" else read_senate
        try:
            n = reader(cache, today, read=read, pause=pause, limit=limit, log=log, save=save)
            log(f"  {chamber}: {n} roll call(s) read, "
                f"{len(cache[chamber]['rolls'])} in all")
        except RollCallError as exc:
            failures.append(f"{chamber}: {exc}")
            log(f"  [warn] {chamber}: stopped ({exc}); what was read is kept")
    cache["read"] = today.isoformat()
    if save:
        save(cache)
    if failures:
        raise RollCallError("; ".join(failures))
    return cache
