"""The seat's last election: each House seat's 2024 result, each Senate
seat's last election, from the Clerk of the House's official statistics.

The audit of 2026-10-17 found no past result anywhere on the site: a reader
deciding how close their race is had only the market prices (RACES-15,
PERSONA-12, VISUALS-33). The source is the official compilation, "Statistics
of the Presidential and Congressional Election", which the Clerk publishes
every two years "from official sources" - each state's certified count. The
FEC's own compilation, "Federal Elections 2024", was not yet published when
this was written; its 2024 page lists only the presidential results.

The Clerk's file is a PDF typeset for print. Its text comes out of
:func:`kyc.courts.pdf_lines` one label or one count per line, the labels of
a district in a run and their counts after them (or, in 2020's Senate
tables, each count after its label), with the page number after the last
count on a page and the runoff counts footnoted. :func:`parse_statistics`
reads all of that and refuses a block whose labels and counts do not pair:
a silent off-by-one would put one candidate's votes beside another's name.

What it reads is checked against a second compilation before it is shown
(rule 50: a compiled table is a lead, rule 53: two sources of one count must
agree, or neither is shown). MIT Election Data and Science Lab's Senate
returns check the Senate; its House returns sit behind a download form that
asks for a name and an email address, so the House is checked against each
state's Wikipedia page of 2024 House results - the winner and runner-up, by
surname, with the very same counts. A result the second source contradicts
is withheld and says so; one no second source covers is withheld too.

A district redrawn for 2026 (``districts.REDRAWN``) is not the district
that voted in 2024. Its race says so and shows no 2024 figure: the old
district's result is about other people's votes (rule 90).

    python build_profile_site.py seats            # refresh (network)
    python build_profile_site.py seats --check    # report from the cache
"""

import csv
import datetime
import io
import json
import os
import re
import time
import unicodedata
import urllib.request

from .normalize import US_STATES

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "seat_history.json")

CLERK_URL = "https://clerk.house.gov/member_info/electionInfo/{year}/statistics{year}.pdf"
CLERK_TITLE = ("Clerk of the House, “Statistics of the Presidential and Congressional "
               "Election of {day}”")
ELECTION_DAYS = {2020: "2020-11-03", 2022: "2022-11-08", 2024: "2024-11-05"}
HOUSE_YEAR = 2024
YEARS = (2020, 2022, 2024)

# MIT Election Data and Science Lab, "U.S. Senate statewide 1976-2024"
# (Harvard Dataverse, doi:10.7910/DVN/PEJ5QU).
MIT_SENATE_DOI = "doi:10.7910/DVN/PEJ5QU"
MIT_SENATE_FILE = "1976-2024-senate-state.tab"
MIT_SENATE_PAGE = "https://doi.org/10.7910/DVN/PEJ5QU"
DATAVERSE = "https://dataverse.harvard.edu/api"

_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 90
WIKI_GAP = 1.5   # Wikimedia throttles unregistered clients (results._GAP)

# Where a general election counts ranked choices, the Clerk's counts may be
# the first choices (Alaska's at-large seat, 2024) or a final round (Maine's
# 2nd district, 2024), and the page says which. Maine: the 2016 citizen
# initiative (Question 5), used for federal general elections from 2018.
# Alaska: Ballot Measure 2 (2020), first used in 2022.
RANKED_CHOICE = {"ME": 2018, "AK": 2022}


def ranked_choice(state, year):
    return year >= RANKED_CHOICE.get(state, 9999)

# The Clerk's PDFs set names in a font whose accented letters are numbered
# afresh in every file: 0x83 is "é" in 2020 and 2022 and "í" in 2024, and
# 0x85 "ó", "í" and "ñ" in the three. Each file says which in its font's
# /Differences array (``clerk_decoder``). The rest are Adobe's standard
# encoding: the leader byte (a space glyph, kept apart so a label with no
# dots after it is still a label), the quotes and the dash. A byte neither
# names fails the read (``ClerkFormatError``): a name is never guessed at.
CLERK_BYTES = {0x80: "¶", 0xAA: "“", 0xBA: "”", 0xD0: "—"}

_ACCENTS = {"acute": "ACUTE", "grave": "GRAVE", "circumflex": "CIRCUMFLEX", "tilde": "TILDE",
            "dieresis": "DIAERESIS", "cedilla": "CEDILLA", "ring": "RING ABOVE",
            "caron": "CARON"}


class ClerkFormatError(ValueError):
    """The statistics file says something this reader does not understand."""


def _glyph(name):
    """``"eacute"`` -> ``"é"``; None for a glyph that is not an accented letter."""
    match = re.fullmatch(r"([A-Za-z])(acute|grave|circumflex|tilde|dieresis|cedilla|ring|caron)",
                         name)
    if not match:
        return None
    letter, accent = match.groups()
    case = "SMALL" if letter.islower() else "CAPITAL"
    try:
        return unicodedata.lookup(f"LATIN {case} LETTER {letter.upper()} WITH {_ACCENTS[accent]}")
    except KeyError:
        return None


def clerk_decoder(data):
    """A decoder for one statistics file's text, from the /Differences
    arrays its fonts carry (in object streams or not)."""
    import zlib
    chunks = [data]
    for match in re.finditer(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", data, re.S):
        head, body = match.groups()
        if b"/FlateDecode" in head:
            try:
                chunks.append(zlib.decompress(body))
            except zlib.error:
                continue
    table = {}
    for chunk in chunks:
        for array in re.finditer(rb"/Differences\s*\[([^\]]*)\]", chunk):
            code = None
            for token in re.findall(rb"\d+|/[A-Za-z0-9.]+", array.group(1)):
                if token[:1].isdigit():
                    code = int(token)
                    continue
                if code is None:
                    continue
                char = _glyph(token[1:].decode("ascii"))
                if char and code >= 0x80:
                    if table.get(code, char) != char:
                        raise ClerkFormatError(f"byte 0x{code:02X} is both {table[code]} and {char}")
                    table[code] = char
                code += 1
    for code in table:
        if code in CLERK_BYTES:
            raise ClerkFormatError(f"byte 0x{code:02X} is an accented letter and {CLERK_BYTES[code]!r}")
    table.update(CLERK_BYTES)

    def decode(raw):
        out = []
        for byte in raw:
            if byte in table:
                out.append(table[byte])
            elif byte < 0x80:
                out.append(chr(byte))
            else:
                raise ClerkFormatError(f"unknown byte 0x{byte:02X} in the Clerk's text")
        return "".join(out)
    return decode


# ------------------------------------------------------------------ reading

_STATE_HEADING = re.compile(r"^(?P<name>[A-Z][A-Z .]+?)(?:—Continued)?$")
_SECTION = re.compile(r"^FOR (?P<what>PRESIDENTIAL ELECTORS|UNITED STATES SENATOR|"
                      r"UNITED STATES REPRESENTATIVE|DELEGATE|RESIDENT COMMISSIONER)"
                      r"(?P<cont>—Continued)?$")
_DISTRICT = re.compile(r"^(\d{1,2})\.$")
_NUMBER = re.compile(r"^\d{1,3}(?:,\d{3})*$")
_LEADER = re.compile(r"\s?¶|\s?\.{4,}")
_TERM = re.compile(r"^\(For (?P<kind>unexpired|full) term (?:ending|beginning) "
                   r"(?P<date>[A-Z][a-z]+ \d{1,2}, \d{4})\)$")
_RECAP = re.compile(r"^Recapitulation of Votes Cast in ")
_MARK = re.compile(r"^\((\d)\)$")


def _sentence(line):
    """A line of a footnote's prose, not a table's label or count."""
    return (len(line) >= 30 and "¶" not in line and "...." not in line
            and len(line.split()) >= 6 and any(c.islower() for c in line)
            and not _RECAP.match(line))

# Lines that count ballots for no one, or for nobody named: they are not a
# candidate, and a share is never taken of the ballots that chose nobody.
NOT_A_VOTE = re.compile(r"^(?:blank|blanks|blank votes|void|invalid|over ?votes|under ?votes|"
                        r"continuing ballots|exhausted ballots|total)$", re.I)
# Votes for someone the table does not name: counted in the total.
UNNAMED = re.compile(r"^(?:write-in|write-ins|scattering|all others|other write-ins|"
                     r"miscellaneous|others|other|write-in \(.*\))$", re.I)
# The rows a ranked-choice tabulation's final round adds (Maine's 2nd
# district in 2024): what the counts above them are.
RCV_ROUND = re.compile(r"^(?:continuing ballots|exhausted ballots)$", re.I)


def _label(line):
    """The text before a dot leader, or None for a line with no leader."""
    if not _LEADER.search(line):
        return None
    text = _LEADER.split(line, 1)[0]
    return " ".join(text.split()) or None


def _state_code(line):
    if line in US_STATES:
        return US_STATES[line]
    match = _STATE_HEADING.match(line)
    if match and match.group("name") in US_STATES and line.endswith("—Continued"):
        return US_STATES[match.group("name")]
    return None


def _pair(tokens, where):
    """Pair a block's labels with their counts.

    *tokens* is the block in the file's order, each ``("L", label)`` or
    ``("N", count, raw)``, with ``("P",)`` where a page broke. A run of
    labels is followed by a run of counts of the same length; a single label
    followed by two counts carries a footnote marker before its count
    (2020's Georgia runoff), and a page's last run may end in its page
    number. Anything else is an error, never a guess."""
    pairs = []
    runs = []
    for token in tokens:
        kind = token[0]
        if kind == "P":
            runs.append(("P", None))
            continue
        if runs and runs[-1][0] == kind:
            runs[-1][1].append(token)
        else:
            runs.append((kind, [token]))
    i = 0
    while i < len(runs):
        kind, items = runs[i]
        if kind == "P":
            i += 1
            continue
        if kind == "U":
            # A name with no count: unopposed, its footnote says so.
            for token in items:
                pairs.append((token[1], None, ("unopposed", token[2])))
            i += 1
            continue
        if kind == "N":
            # Counts with no label before them: a page number alone.
            if all(len(t[2]) <= 3 and "," not in t[2] for t in items) and len(items) == 1:
                i += 1
                continue
            raise ClerkFormatError(f"{where}: counts with no names before them: "
                                   f"{[t[2] for t in items]}")
        labels = items
        counts = runs[i + 1][1] if i + 1 < len(runs) and runs[i + 1][0] == "N" else []
        ends_page = (i + 2 >= len(runs)) or runs[i + 2][0] == "P"
        notes = [None] * len(labels)
        if len(counts) == len(labels) + 1 and ends_page and "," not in counts[-1][2] \
                and len(counts[-1][2]) <= 3 and len(labels) > 1:
            counts = counts[:-1]                      # the page number
        elif len(labels) == 1 and len(counts) == 2 and "," not in counts[0][2] \
                and len(counts[0][2]) <= 2:
            if ends_page and "," not in counts[1][2] and len(counts[1][2]) <= 3 \
                    and counts[0][1] > 9:
                counts = counts[:1]                   # votes, then the page number
            else:
                notes = [counts[0][1]]                # footnote marker, then votes
                counts = counts[1:]
        elif len(labels) == 1 and len(counts) == 2 and ends_page \
                and "," not in counts[1][2] and len(counts[1][2]) <= 3:
            counts = counts[:1]
        if len(counts) != len(labels):
            raise ClerkFormatError(
                f"{where}: {len(labels)} names and {len(counts)} counts: "
                f"{[t[1] for t in labels]} / {[t[2] for t in counts]}")
        for label, count, note in zip(labels, counts, notes):
            pairs.append((label[1], count[1], note))
        i += 2
    return pairs


def _candidates(pairs, where, parties=frozenset()):
    """The block's people, one row each, with the ballots that named no one
    and the unnamed votes apart. A label that names a party and no one is
    another line of the candidate above it (New York's and Connecticut's
    fusion lines: "Nick LaLota, Republican" then "Conservative"; New York's
    5th district: "Paul King, Republican" then "Conservative, Common Sense").
    *parties* is every party the file names after a candidate's name."""
    rows, unnamed, blank, rcv = [], 0, 0, False
    for label, votes, note in pairs:
        if votes is None:
            if "," not in label:
                raise ClerkFormatError(f"{where}: an unopposed line {label!r} names no one")
            name, party = split_label(label)
            rows.append({"name": name, "party": party, "votes": None,
                         "lines": [], "note": None, "unopposed": note[1]})
            continue
        if NOT_A_VOTE.match(label):
            blank += votes if label.lower() != "total" else 0
            rcv = rcv or bool(RCV_ROUND.match(label))
            continue
        if UNNAMED.match(label):
            unnamed += votes
            continue
        if "," not in label or label.split(",")[0].strip() in parties:
            if not rows:
                raise ClerkFormatError(f"{where}: a party line {label!r} with no candidate")
            rows[-1]["lines"].append([label, votes])
            rows[-1]["votes"] += votes
            continue
        name, party = split_label(label)
        same = [r for r in rows if r["name"] == name and r.get("unopposed") is None]
        if same:
            # One person on two lines, each with their own name: one
            # candidate, counted once.
            same[0]["lines"].append([party, votes])
            same[0]["votes"] += votes
            continue
        rows.append({"name": name, "party": party, "votes": votes,
                     "lines": [[party, votes]], "note": note})
    return {"rows": rows, "unnamed": unnamed, "noVote": blank, "rcvRound": rcv}


_SUFFIX = re.compile(r"^(?:Jr|Sr|II|III|IV|V)\.?$")


def split_label(label):
    """``"Michael J. LiPetri, Jr., Republican"`` -> the name with its
    suffix and the party; a candidate two parties nominated is both
    ("Mark Coester, Republican, Libertarian", Vermont)."""
    parts = [p.strip() for p in label.split(",")]
    name = [parts[0]]
    rest = parts[1:]
    while rest and _SUFFIX.match(rest[0]):
        name.append(rest.pop(0))
    if not rest:
        raise ClerkFormatError(f"a candidate line with no party: {label!r}")
    return ", ".join(name), ", ".join(rest)


def party_names(lines):
    """Every party the file names: what follows a candidate's name on a
    line, and the lines that name a party alone."""
    found = set()
    for line in lines:
        label = _label(line.strip())
        if not label or NOT_A_VOTE.match(label) or UNNAMED.match(label):
            continue
        if "," not in label:
            found.add(label)
            continue
        try:
            found.update(p.strip() for p in split_label(label)[1].split(","))
        except ClerkFormatError:
            continue
    return frozenset(found)


def parse_statistics(lines, year, chambers=("house", "senate")):
    """The House and Senate contests in one year's statistics, of the
    *chambers* asked for (the others are not read at all).

    Returns ``{state: {"house": {district: contest}, "senate": [contest],
    "footnotes": {n: text}}}``; a contest is :func:`_candidates`' dict with
    its ``term`` ("full" or "unexpired") and ``termEnds`` for the Senate.
    """
    states = {}
    state = section = None
    block = None            # (key, tokens)
    district = None
    term = None
    recap = False
    footnote = None
    parties = party_names(lines)

    def close():
        nonlocal block
        if block is None:
            return
        key, tokens = block
        block = None
        if not tokens:
            return
        where = f"{year} {state} {key}"
        contest = _candidates(_pair(tokens, where), where, parties)
        entry = states.setdefault(state, {"house": {}, "senate": [], "footnotes": {}})
        if key[0] == "house":
            if key[1] in entry["house"]:
                old = entry["house"][key[1]]
                # The same district resumed after a page break.
                old["rows"] += contest["rows"]
                old["unnamed"] += contest["unnamed"]
                old["noVote"] += contest["noVote"]
                old["rcvRound"] = old["rcvRound"] or contest["rcvRound"]
            else:
                entry["house"][key[1]] = contest
        else:
            contest.update(term=key[1], termEnds=key[2])
            same = [c for c in entry["senate"] if c["term"] == key[1] and c["termEnds"] == key[2]]
            if same:
                same[0]["rows"] += contest["rows"]
                same[0]["unnamed"] += contest["unnamed"]
                same[0]["noVote"] += contest["noVote"]
            else:
                entry["senate"].append(contest)

    for raw in lines:
        line = raw.strip()
        code = _state_code(line)
        if code:
            if code != state:
                close()
                state, section, district, term, recap, footnote = code, None, None, None, False, None
            elif block is not None:
                block[1].append(("P",))
            continue
        if state is None:
            continue
        if recap:
            # After the recapitulation: only the footnotes are read, a
            # number on its own line and the sentences after it.
            if re.fullmatch(r"\d{1,2}", line):
                footnote = (int(line), False)
                continue
            if footnote is not None and _sentence(line):
                notes = states.setdefault(state, {"house": {}, "senate": [], "footnotes": {}})["footnotes"]
                number, started = footnote
                if started or number not in notes:
                    notes[number] = (notes.get(number, "") + " " + line).strip()
                    footnote = (number, True)
                continue
            footnote = None
            continue
        if _RECAP.match(line):
            close()
            recap = True
            continue
        match = _SECTION.match(line)
        if match:
            if match.group("cont") and block is not None:
                block[1].append(("P",))
                continue
            close()
            what = match.group("what")
            section = {"UNITED STATES SENATOR": "senate", "PRESIDENTIAL ELECTORS": None}.get(
                what, "house")
            if section not in chambers:
                section = None
            district = 0 if what in ("DELEGATE", "RESIDENT COMMISSIONER") else None
            term = None
            if section == "senate":
                block = (("senate", "full", None), [])
            elif section == "house" and district == 0:
                block = (("house", 0), [])
            continue
        if section is None:
            continue
        if section == "senate":
            match = _TERM.match(line)
            if match:
                close()
                when = datetime.datetime.strptime(match.group("date"), "%B %d, %Y").date()
                if match.group("kind") == "unexpired":
                    term = ("unexpired", when.isoformat())
                else:
                    term = ("full", None)
                block = (("senate",) + term, [])
                continue
        if section == "house":
            match = _DISTRICT.match(line)
            if match or line == "AT LARGE":
                close()
                district = int(match.group(1)) if match else 0
                block = (("house", district), [])
                continue
        if block is None:
            continue
        if _NUMBER.match(line):
            block[1].append(("N", int(line.replace(",", "")), line))
            continue
        match = _MARK.match(line)
        if match:
            # "(1)" straight after a name: no count, and footnote 1 says why
            # (Florida and Oklahoma print no unopposed candidate). Anywhere
            # else it is the first page's number.
            if block[1] and block[1][-1][0] == "L":
                block[1][-1] = ("U", block[1][-1][1], int(match.group(1)))
            continue
        label = _label(line)
        if label is not None:
            block[1].append(("L", label))
            continue
        # Anything else ends the block: the tables at the end of the file.
        close()
    close()
    for code, entry in states.items():
        for contest in entry["senate"]:
            if contest["term"] == "full":
                contest["termEnds"] = f"{year + 7}-01-03"
    return states


# ------------------------------------------------------------------ results

def _date_of(text):
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", text or "")
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def result_of(contest, footnotes, year, state=None):
    """The contest as the page shows it: who won, with what share, by what
    margin, all computed from the Clerk's counts.

    Shares are of the votes cast for a candidate, named or written in;
    blank, void, over- and under-votes chose no one. Where the Clerk
    footnotes counts as a runoff's (Georgia's January 5, 2021 runoff), the
    result is the runoff's, between the people it lists, dated from the
    footnote. A ranked-choice tabulation's final round (Maine's 2nd district
    in 2024) is shown as that round."""
    rows = list(contest["rows"])
    kind = "general"
    date = ELECTION_DAYS[year]
    unnamed = contest["unnamed"]
    unopposed = [r for r in rows if r.get("unopposed") is not None]
    if unopposed:
        if len(rows) != 1:
            raise ClerkFormatError(f"{year}: an unopposed name beside others: {rows}")
        person = unopposed[0]
        note = footnotes.get(person["unopposed"])
        if not note:
            raise ClerkFormatError(f"{year}: {person['name']} has no count and no footnote")
        return {"year": year, "date": date, "kind": "unopposed", "note": note,
                "candidates": [{"name": person["name"], "party": person["party"]}]}
    noted = [r for r in rows if r.get("note")]
    if noted:
        texts = {footnotes.get(r["note"], "") for r in noted}
        if len(texts) != 1 or "runoff" not in next(iter(texts)):
            raise ClerkFormatError(f"{year}: footnoted counts that are not one runoff's: {texts}")
        text = next(iter(texts))
        found = re.search(r"from \w+'s (\w+ \d{1,2}, \d{4}),", text)
        date = _date_of(found.group(1)) if found else None
        if not date:
            raise ClerkFormatError(f"{year}: a runoff footnote with no date: {text}")
        rows, unnamed, kind = noted, 0, "runoff"
    elif contest.get("rcvRound"):
        kind = "rcv-final"
    rows.sort(key=lambda r: -r["votes"])
    total = sum(r["votes"] for r in rows) + unnamed
    if not rows or total <= 0:
        return None

    def share(votes):
        return round(100.0 * votes / total, 1)

    people = [{"name": r["name"], "party": r["party"], "votes": r["votes"],
               "share": share(r["votes"]),
               **({"lines": r["lines"]} if len(r["lines"]) > 1 else {})} for r in rows]
    top = people[0]
    second = people[1] if len(people) > 1 else None
    if second and second["votes"] == top["votes"]:
        raise ClerkFormatError(f"{year}: a tie at the top: {top['name']}, {second['name']}")
    out = {
        "year": year,
        "date": date,
        "kind": kind,
        "total": total,
        "candidates": people[:2],
        "others": total - top["votes"] - (second["votes"] if second else 0),
        "othersShare": share(total - top["votes"] - (second["votes"] if second else 0)),
        "allCandidates": len(people),
        # The margin is of the votes, as the shares are, not the difference
        # of two rounded shares.
        "margin": round(100.0 * (top["votes"] - (second["votes"] if second else 0)) / total, 1),
    }
    if not second:
        out["unopposedByName"] = True
    if state and ranked_choice(state, year) and kind == "general":
        # Counts with no final round under them are the first choices.
        out["rankedChoice"] = "first-choices"
    return out


# ------------------------------------------------------------- second sources

def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z ]", " ", text.lower().replace("’", "").replace("'", ""))


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def surname(name):
    """The last word of a name that is not a suffix ("Michael J. LiPetri,
    Jr." is LiPetri)."""
    words = [w for w in _fold(name).split() if w not in SUFFIXES]
    return words[-1] if words else ""


# How far a second compilation's count may be from the Clerk's and still
# agree. The check is of attribution - that the Clerk's counts were read
# against the right names - and a name read against another's count is off
# by far more. Compilations do differ in the last digits: Wikipedia gives
# Iowa's 1st district runner-up 206,157 votes and the Clerk 206,156, and
# Texas's 7th 148,406 and 149,820 for its winner (an earlier canvass). The
# page shows the Clerk's count, says what was checked, and the cache keeps
# each difference for a reviewer (``differences``).
TOLERANCE = 0.01


def _check(result, rows):
    """Does a second source's table *rows* (``[{"name", "votes", "won"?}]``)
    name the Clerk's winner and runner-up, in that order, with counts within
    :data:`TOLERANCE` of the Clerk's? Returns ``(verdict, differences)``:
    ``"agree"``, ``"disagree"``, or ``None`` when the table is not about
    these people."""
    wanted = result["candidates"]
    # A write-in runner-up (Kentucky's 4th: 1,131 votes) is a name the
    # other compilations do not list: the winner alone is checked.
    if len(wanted) == 2 and re.search(r"write-in", wanted[1].get("party") or "", re.I):
        wanted = wanted[:1]
    found = []
    for person in wanted:
        match = _find(person["name"], rows)
        if match is None:
            return None, []
        found.append(match)
    differences = []
    for person, row in zip(wanted, found):
        theirs = row.get("votes")
        if theirs is None:
            return None, []
        if theirs != person["votes"]:
            differences.append({"name": person["name"], "clerk": person["votes"], "other": theirs})
            if abs(theirs - person["votes"]) > TOLERANCE * person["votes"]:
                return "disagree", differences
    if len(found) == 2 and found[1]["votes"] >= found[0]["votes"]:
        return "disagree", differences
    winners = [r for r in rows if r.get("won")]
    if winners and found[0] not in winners:
        return "disagree", differences
    return "agree", differences


def _one_apart(a, b):
    """Is *a* one letter added, dropped or changed from *b*?"""
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _find(name, rows):
    """The one row of *rows* that is *name*: by surname; among two of one
    surname (South Dakota's Dusty and Sheryl Johnson) by the first name
    too; and only where no surname matches, a surname a letter apart
    (Tennessee's 9th: "Bergmann" and "Bergman"), so long as one row has it."""
    last = surname(name)
    if not last:
        return None
    first = _fold(name).split()[0]
    matches = [r for r in rows if last in _fold(r["name"]).split()]
    if len(matches) > 1:
        matches = [r for r in matches if _fold(r["name"]).split()[:1] == [first]]
    if not matches and len(last) >= 6:
        matches = [r for r in rows if any(_one_apart(last, w) for w in _fold(r["name"]).split())]
    return matches[0] if len(matches) == 1 else None


def _summed(rows):
    """A table's rows, one per person: New York's fusion lines are rows of
    one name, and a "Total" row, where a page gives one, is that sum."""
    by_name = {}
    totals = {}
    for row in rows:
        words = _fold(row["name"]).split()
        key = surname(row["name"]) + "|" + (words[0] if words else "")
        if (row.get("party") or "").lower() == "total":
            totals[key] = dict(row)
            continue
        if key in by_name:
            by_name[key]["votes"] = (by_name[key]["votes"] or 0) + (row.get("votes") or 0)
            by_name[key]["won"] = by_name[key].get("won") or row.get("won")
        else:
            by_name[key] = dict(row)
    for key, row in totals.items():
        if key in by_name:
            by_name[key]["votes"] = row["votes"]
            by_name[key]["won"] = by_name[key].get("won") or row.get("won")
    return list(by_name.values())


_WBOX = re.compile(r"\{\{\s*Election box (?:open primary )?begin[^}]*?\|\s*title\s*=\s*([^\n|}]+)"
                   r".*?\{\{\s*Election box end\s*\}\}", re.S | re.I)
_OPEN_GENERAL = re.compile(r"\{\{\s*Election box open primary general election[^}]*\}\}", re.I)
_COUNT = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")


def _votes(raw):
    """A votes field as a number, whatever markup it is set in
    ("'''213,916'''" on Ohio's 1st district), or None."""
    text = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|\{\{[^{}]*\}\}|'{2,}", "", raw or "", flags=re.S)
    match = _COUNT.search(text)
    return int(match.group().replace(",", "")) if match else None


def wiki_boxes(text):
    """``[(stage, rows)]`` from a page's results boxes. An open primary's
    box holds both rounds (California's top two); the part after its
    "general election" marker is the general's."""
    from .results import _ROW, _stage, clean_name, template_fields
    out = []
    for match in _WBOX.finditer(text or ""):
        body = match.group(0)
        parts = [(_stage(match.group(1)) or "general", body)]
        split = _OPEN_GENERAL.search(body)
        if split:
            parts = [("primary", body[:split.start()]), ("general", body[split.end():])]
        for stage, part in parts:
            rows = []
            for row in _ROW.finditer(part):
                fields = template_fields(row.group("body"))
                name = clean_name(fields.get("candidate", ""))
                if not name:
                    continue
                rows.append({"name": name, "votes": _votes(fields.get("votes")),
                             "won": row.group("kind").lower().startswith("winning"),
                             "party": clean_name(fields.get("party", "")) or None})
            if rows:
                out.append((stage, rows))
    return out


_INFOBOX = re.compile(r"\{\{\s*Infobox election\b", re.I)


def infobox_rows(text):
    """The first ``{{Infobox election}}``'s candidates and popular votes."""
    from .results import clean_name, template_body, template_fields
    match = _INFOBOX.search(text or "")
    if not match:
        return []
    fields = template_fields("|" + template_body(text, match.start()).split("|", 1)[-1])
    rows = []
    for key, value in fields.items():
        found = re.fullmatch(r"(?:candidate|nominee)(\d+)", key)
        if not found:
            continue
        name = clean_name(value)
        number = found.group(1)
        # A ranked-choice election's infobox gives each round instead
        # ("1data1" the first, as Alaska's 2024 page does): the first
        # round is what the Clerk lists.
        votes = _votes(fields.get(f"popular_vote{number}")) or _votes(fields.get(f"1data{number}"))
        if name:
            rows.append({"name": name, "votes": votes,
                         "party": clean_name(fields.get(f"party{found.group(1)}", "")) or None})
    return rows


def wiki_check(result, text, stage="general"):
    """Check *result* against a Wikipedia page's results boxes (*text*: the
    district's section, or a Senate election's page). Returns ``(verdict,
    differences)``. An unopposed winner, whom Florida and Oklahoma print on
    no ballot, agrees where the section names them and says "unopposed"."""
    if result.get("kind") == "unopposed":
        last = surname(result["candidates"][0]["name"])
        plain = _fold(text)
        said = "unopposed" in plain or "uncontested" in plain
        return ("agree" if last and last in plain.split() and said else None), []
    verdicts, differences = [], []
    boxes = wiki_boxes(text)
    if stage == "general" and not any(s == "general" for s, _ in boxes):
        # Pages that set the general's result only in the infobox
        # (American Samoa's 2024 delegate election).
        boxes = [("general", infobox_rows(text))]
    for box_stage, rows in boxes:
        if box_stage != stage:
            continue
        verdict, diff = _check(result, _summed(rows))
        if verdict:
            verdicts.append(verdict)
            if verdict == "agree" and not differences:
                differences = diff
    if "agree" in verdicts:
        return "agree", differences
    return ("disagree" if verdicts else None), []


def read_mit_senate(raw):
    """MIT's Senate returns as ``{(year, state, special, stage): [rows]}``."""
    out = {}
    reader = csv.DictReader(io.StringIO(raw))
    for row in reader:
        try:
            year = int(row["year"])
        except (KeyError, ValueError):
            continue
        if year not in YEARS:
            continue
        stage = (row.get("stage") or "").lower()
        stage = "runoff" if "runoff" in stage else "general" if stage == "gen" or stage.startswith("gen") else stage
        key = (year, row.get("state_po"), (row.get("special") or "").lower() == "true", stage)
        try:
            votes = int(float(row.get("candidatevotes") or 0))
        except ValueError:
            continue
        out.setdefault(key, []).append({
            "name": row.get("candidate") or "", "votes": votes,
            "unofficial": (row.get("unofficial") or "").lower() == "true",
        })
    return out


def mit_check(result, mit, state, special):
    rows = mit.get((result["year"], state, special, "runoff" if result["kind"] == "runoff" else "general"))
    if not rows or any(r["unofficial"] for r in rows):
        return None, []
    return _check(result, _summed(rows))


# ------------------------------------------------------------------ fetching

def _download(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
        return response.read()


def read_clerk(year, fetch=_download, chambers=("house", "senate")):
    from .courts import pdf_lines
    data = fetch(CLERK_URL.format(year=year))
    if not data.startswith(b"%PDF"):
        raise ClerkFormatError(f"the Clerk's {year} statistics are not a PDF")
    return parse_statistics(pdf_lines(data, decode=clerk_decoder(data)), year, chambers)


def read_mit(fetch=_download):
    """MIT's Senate file, found by name in the dataset's current version."""
    meta = json.loads(fetch(f"{DATAVERSE}/datasets/:persistentId/?persistentId={MIT_SENATE_DOI}"))
    files = meta["data"]["latestVersion"]["files"]
    ids = [f["dataFile"]["id"] for f in files if f["dataFile"]["filename"] == MIT_SENATE_FILE]
    if len(ids) != 1:
        raise ValueError(f"MIT's Senate dataset has no single {MIT_SENATE_FILE}")
    raw = fetch(f"{DATAVERSE}/access/datafile/{ids[0]}?format=original")
    return read_mit_senate(raw.decode("utf-8"))


def _wiki_page(title):
    from .results import fetch_wikitext, PageMissing
    try:
        return fetch_wikitext(title)
    except PageMissing:
        return None


def house_page_sections(state, read=_wiki_page):
    """``{district: section}`` from a state's 2024 House results page(s)."""
    from .results import page_titles, house_sections, sub_articles
    for title in page_titles(state, "H", cycle=HOUSE_YEAR):
        text = read(title)
        if text is None:
            continue
        sections = house_sections(text, at_large=True)
        if set(sections) == {0} and sub_articles(text, title):
            sections = {}
        for sub in sub_articles(text, title):
            sections.update(house_sections(read(sub) or ""))
        return sections, title
    return {}, None


def build(race_list, log=print, fetch=_download, read_wiki=_wiki_page, today=None):
    """Read the Clerk's statistics and the second sources; the cache."""
    today = today or datetime.date.today().isoformat()
    clerk = {}
    for year in YEARS:
        # Only 2024's House: the other years are read for their Senate seats.
        clerk[year] = read_clerk(year, fetch=fetch, chambers=(
            ("house", "senate") if year == HOUSE_YEAR else ("senate",)))
        log(f"  read the Clerk's {year} statistics: {len(clerk[year])} states and territories")
    try:
        mit = read_mit(fetch=fetch)
        log(f"  read MIT's Senate returns ({sum(len(v) for v in mit.values())} rows, {len(mit)} contests)")
    except Exception as exc:     # a failed read checks nothing (rule 8)
        log(f"  [warn] MIT's Senate returns unreadable ({exc}); the Senate is checked "
            "against Wikipedia alone")
        mit = {}

    cache = {"read": today, "years": list(YEARS), "house": {}, "senate": {}, "withheld": []}
    wiki_cache = {}

    def wiki(title):
        if title not in wiki_cache:
            wiki_cache[title] = read_wiki(title)
            time.sleep(WIKI_GAP)
        return wiki_cache[title]

    def keep(store, key, result, verdict, differences, checked, page=None):
        if verdict == "agree":
            result["checked"] = checked
            if differences:
                result["differences"] = differences
            store[key] = result
        else:
            cache["withheld"].append({"seat": key, "year": result["year"],
                                      "why": verdict or "unchecked",
                                      **({"page": page} if page else {}), "result": result})

    house_states = sorted({r["state"] for r in race_list if r["chamber"] == "House"})
    for state in house_states:
        contests = (clerk[HOUSE_YEAR].get(state) or {}).get("house") or {}
        sections, page = house_page_sections(state, read=wiki)
        for district, contest in sorted(contests.items()):
            result = result_of(contest, clerk[HOUSE_YEAR][state]["footnotes"], HOUSE_YEAR, state)
            if not result:
                continue
            section = sections.get(district) or (sections.get(0) if len(contests) == 1 else None)
            verdict, differences = wiki_check(result, section) if section else (None, [])
            keep(cache["house"], f"{state}-{district}", result, verdict, differences,
                 {"by": "wikipedia", "page": page}, page)
        log(f"  {state}: {len(contests)} House contest(s) read")

    # Only the elections to the seats on the ballot: a seat's term ends when
    # its class's does (senate_last).
    wanted = {(r["state"], SENATE_TERM_ENDS.get(r.get("senateClass")))
              for r in race_list if r["chamber"] == "Senate"}
    from .results import page_titles
    for state, ends in sorted(wanted):
        for year in YEARS:
            entry = clerk[year].get(state) or {}
            for contest in entry.get("senate") or []:
                if contest["termEnds"] != ends:
                    continue
                result = result_of(contest, entry.get("footnotes") or {}, year, state)
                if not result:
                    continue
                special = contest["term"] == "unexpired"
                result.update(term=contest["term"], termEnds=contest["termEnds"])
                verdict, differences = mit_check(result, mit, state, special)
                checked, page = {"by": "mit"}, None
                if verdict is None:
                    titles = page_titles(state, "S", cycle=year)
                    page = titles[1] if special else titles[0]
                    text = wiki(page)
                    stage = "runoff" if result["kind"] == "runoff" else "general"
                    verdict, differences = (wiki_check(result, text, stage=stage) if text
                                            else (None, []))
                    checked = {"by": "wikipedia", "page": page}
                keep(cache["senate"], f"{state}-{year}-{contest['term']}", result, verdict,
                     differences, checked, page)
    return cache


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


# ------------------------------------------------------------------ the page

SENATE_TERM_ENDS = {1: "2031-01-03", 2: "2027-01-03", 3: "2029-01-03"}


def page_sources():
    """The sources a race's last election cites, once for the page
    (``kycBuildMeta.lastElectionSources``) rather than on every race."""
    out = {str(year): {"title": CLERK_TITLE.format(day=_long_day(ELECTION_DAYS[year])),
                       "url": CLERK_URL.format(year=year)} for year in YEARS}
    out["mit"] = {"title": "MIT Election Data and Science Lab’s U.S. Senate returns",
                  "url": MIT_SENATE_PAGE}
    return out


def _shown(result, chamber):
    """The page's copy of a cached result: what a race block draws. Its
    sources are the page's table (:func:`page_sources`), by year."""
    keys = ("year", "date", "kind", "total", "margin", "others", "othersShare",
            "allCandidates", "note", "unopposedByName", "rankedChoice")
    out = {k: result[k] for k in keys if k in result}
    out["candidates"] = [{k: c[k] for k in ("name", "party", "votes", "share") if k in c}
                         for c in result["candidates"]]
    if chamber == "Senate":
        out["term"] = result.get("term")
    checked = result.get("checked") or {}
    if checked.get("by") == "mit":
        out["checkedBy"] = "mit"
    elif checked.get("page"):
        # A Wikipedia article's title; the page links it.
        out["checkedBy"] = checked["page"]
    return out


def _long_day(iso):
    day = datetime.date.fromisoformat(iso)
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def senate_last(cache, state, senate_class):
    """The latest election in the cache to the seat of *senate_class*: the
    one whose term ends when the seat's does. Oklahoma's class II seat was
    last elected in 2022's special election, not 2020's, and Nebraska's in
    2024's."""
    ends = SENATE_TERM_ENDS.get(senate_class)
    if not ends:
        return None
    best = None
    for key, result in (cache.get("senate") or {}).items():
        if not key.startswith(state + "-") or result.get("termEnds") != ends:
            continue
        if best is None or result["year"] > best["year"]:
            best = result
    withheld = [w for w in cache.get("withheld") or []
                if w["seat"].startswith(state + "-") and
                (w.get("result") or {}).get("termEnds") == ends and
                (best is None or w["year"] > best["year"])]
    return best, withheld


def apply(races, cache):
    """Attach ``lastElection`` to each race: the seat's last result as the
    page shows it, ``{"redrawn": True}`` for a district redrawn since, or
    ``{"withheld": why}`` where the sources disagree or one is missing.
    Returns how many races carry a result."""
    from .districts import REDRAWN
    if not cache:
        return 0
    shown = 0
    withheld = {w["seat"]: w for w in cache.get("withheld") or []}
    for race in races:
        race.pop("lastElection", None)
        if race["chamber"] == "House":
            if race["state"] in REDRAWN:
                race["lastElection"] = {"redrawn": True, "year": HOUSE_YEAR}
                continue
            key = f"{race['state']}-{race['district'] or 0}"
            result = (cache.get("house") or {}).get(key)
            if result:
                race["lastElection"] = _shown(result, "House")
                shown += 1
            elif key in withheld:
                race["lastElection"] = {"withheld": withheld[key]["why"], "year": HOUSE_YEAR}
        else:
            best, held = senate_last(cache, race["state"], race.get("senateClass"))
            if held:
                race["lastElection"] = {"withheld": held[0]["why"], "year": held[0]["year"]}
            elif best:
                race["lastElection"] = _shown(best, "Senate")
                shown += 1
    return shown


def problems(cache, races):
    """What a build says about the cache: each race whose result is
    withheld, and each race the cache does not cover at all."""
    if not cache:
        return [("warn", "seat-history-missing",
                 f"no {CACHE_PATH}; run: python build_profile_site.py seats", [])]
    out = []
    held = sorted(f"{r['id']}: {r['lastElection']['withheld']} against the second source"
                  for r in races if (r.get("lastElection") or {}).get("withheld"))
    if held:
        out.append(("warn", "seat-history-withheld",
                    f"{len(held)} races show no last result: the Clerk's and the second "
                    "source's disagree or no second source covers it", held))
    missing = sorted(r["id"] for r in races if "lastElection" not in r)
    if missing:
        out.append(("warn", "seat-history-uncovered",
                    f"{len(missing)} races have no last election in the cache", missing))
    return out
