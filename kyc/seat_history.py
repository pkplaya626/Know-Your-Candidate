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
ELECTION_DAYS = {2018: "2018-11-06", 2020: "2020-11-03", 2022: "2022-11-08", 2024: "2024-11-05"}
HOUSE_YEAR = 2024
# The seat's strip (VISUALS-33): every House election and every election to
# a Senate seat's class from 2018 to 2024, each read and checked as the last
# one is. The last election (``lastElection``) stays 2024's for the House.
YEARS = (2018, 2020, 2022, 2024)

# congress-legislators, for who held each seat after each election: by
# bioguide id, never by a name (rule 17).
LEGISLATORS_URLS = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json",
    "https://unitedstates.github.io/congress-legislators/legislators-historical.json",
)
# The strip's terms: those served from 2018's election day (a special's
# winner is seated within days) to the day the 119th's House terms end.
TERMS_FROM = "2018-11-06"
TERMS_TO = "2027-01-03"

# A House seat the Clerk lists every other cycle: Puerto Rico's Resident
# Commissioner serves four years (48 U.S.C. 891), elected in 2020 and 2024.
FOUR_YEAR_SEATS = {"PR": (2020, 2024)}

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
# Nevada's "None of These Candidates" is a choice on its ballot that elects
# no one (NRS 293.269), and Puerto Rico's 2020 "Unadjudicated" ballots
# were not counted for anyone; Maine's 2022 table says "Exhausted Ballot".
NOT_A_VOTE = re.compile(r"^(?:blank|blanks|blank votes|void|invalid|over ?votes|under ?votes|"
                        r"continuing ballots?|exhausted ballots?|none of these candidates|"
                        r"unadjudicated|total)$", re.I)
# Votes for someone the table does not name: counted in the total. New
# Hampshire's tables say "Scatter".
UNNAMED = re.compile(r"^(?:write-in|write-ins|scattering|scatter|all others|other write-ins|"
                     r"miscellaneous|others|other|write-in \(.*\))$", re.I)
# The rows a ranked-choice tabulation's final round adds (Maine's 2nd
# district in 2024): what the counts above them are.
RCV_ROUND = re.compile(r"^(?:continuing ballots?|exhausted ballots?)$", re.I)
# The states whose tables print a candidate's other parties' lines under
# them, a party and no one ("Nick LaLota, Republican" then "Conservative"):
# New York's and Connecticut's fusion lines, every year from 2018 to 2024.
# Anywhere else a party alone is a candidate the Clerk did not name -
# Virginia's 2nd district in 2020 printed "Independent" for David Foster's
# 9,170 votes, and Arizona's 2018 Senate table "Green" for Angela Green's -
# whose votes count in the total and are nobody's we name. Read as fusion,
# Foster's votes were added to Scott Taylor's.
FUSION_STATES = frozenset({"NY", "CT"})
# A footnote saying the counts it marks are a ranked-choice count's later
# round ("This vote count is from round 2 of Maine's ranked-choice general
# election", 2022).
RCV_NOTE = re.compile(r"round \d of \w+'s ranked-choice", re.I)


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
        elif len(labels) > 1 and len(counts) > len(labels):
            counts, notes = _marked(counts, len(labels), ends_page, where)
        if len(counts) != len(labels):
            raise ClerkFormatError(
                f"{where}: {len(labels)} names and {len(counts)} counts: "
                f"{[t[1] for t in labels]} / {[t[2] for t in counts]}")
        for label, count, note in zip(labels, counts, notes):
            pairs.append((label[1], count[1], note))
        i += 2
    return pairs


def _marked(counts, wanted, ends_page, where):
    """A run of counts for *wanted* names that carries footnote markers: a
    lone digit before the count it marks. Louisiana's 2020 5th district
    footnotes the two runoff candidates' counts ("1", "49,183", "1",
    "30,124") among seven unmarked ones, and Maine's 2022 2nd district the
    final ranked-choice round's. The markers are read only where the lone
    digits before a count are exactly the extra tokens (with the page
    number after the last count, where a page ends there); any other
    surplus is an error, never a guess. Returns ``(counts, notes)``."""
    def lone(token):
        return "," not in token[2] and len(token[2]) == 1 and token[1] > 0

    def markers(run):
        found = []
        for j in range(len(run) - 1):
            if lone(run[j]) and (not found or found[-1] != j - 1) and not lone(run[j + 1]):
                found.append(j)
        return found

    runs = [counts]
    last = counts[-1]
    if ends_page and "," not in last[2] and len(last[2]) <= 3:
        runs.append(counts[:-1])                       # the page number after it
    for run in runs:
        found = markers(run)
        if found and len(run) - len(found) == wanted:
            notes, kept, pending = [], [], None
            for j, token in enumerate(run):
                if j in found:
                    pending = token[1]
                    continue
                kept.append(token)
                notes.append(pending)
                pending = None
            return kept, notes
    raise ClerkFormatError(f"{where}: {wanted} names and {len(counts)} counts that are not "
                           f"footnoted counts: {[t[2] for t in counts]}")


def _party_only(label, parties, fusion=None):
    """Does *label* name only parties, and no one ("Conservative",
    "Conservative, Common Sense")? In a fusion state (*fusion*: the lines
    the file prints with no comma, a party alone) a line with no comma is
    one of the candidate's lines, whatever party it names (New York's
    "Independence" line follows no candidate's name anywhere in 2020's
    file), and so is one whose every part is such a line or a party;
    elsewhere a label that is not a candidate's line and names no party
    the file prints after a name is an error, never a guess."""
    parts = [p.strip() for p in label.split(",")]
    known = parties | fusion if fusion is not None else parties
    if all(p in known for p in parts) or (fusion is not None and "," not in label):
        return True
    if "," not in label:
        raise ClerkFormatError(f"a line {label!r} that names no one and no party")
    return False


def _candidates(pairs, where, parties=frozenset(), state=None, alone=frozenset()):
    """The block's people, one row each, with the ballots that named no one
    and the unnamed votes apart. In :data:`FUSION_STATES` a label that names
    a party and no one is another line of the candidate above it (New York's
    and Connecticut's fusion lines: "Nick LaLota, Republican" then
    "Conservative"; New York's 5th district: "Paul King, Republican" then
    "Conservative, Common Sense"); anywhere else it is a candidate the Clerk
    does not name, counted in the total (``unnamed``) and nobody's.
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
        try:
            party_only = _party_only(label, parties, alone if state in FUSION_STATES else None)
        except ClerkFormatError as exc:
            raise ClerkFormatError(f"{where}: {exc}") from None
        if party_only and state not in FUSION_STATES:
            unnamed += votes
            continue
        if party_only:
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
    """Every party the file names after a candidate's name on a line. A
    line that names a party alone is read as one only where the party is
    among these: "Scatter" was once taken for a party, and New Hampshire's
    scattered write-ins added to the last candidate's count."""
    found = set()
    for line in lines:
        label = _label(line.strip())
        if not label or NOT_A_VOTE.match(label) or UNNAMED.match(label) or "," not in label:
            continue
        try:
            found.update(p.strip() for p in split_label(label)[1].split(","))
        except ClerkFormatError:
            continue
    return frozenset(found)


def party_lines(lines):
    """The labels the file prints with no comma that are not a ballot for
    no one or votes for someone unnamed: a fusion state's party lines."""
    return frozenset(label for label in (_label(line.strip()) for line in lines)
                     if label and "," not in label and not NOT_A_VOTE.match(label)
                     and not UNNAMED.match(label))


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
    alone = party_lines(lines)

    def close():
        nonlocal block
        if block is None:
            return
        key, tokens = block
        block = None
        if not tokens:
            if key[0] == "house":
                # A district listed with no count: North Carolina's 9th in
                # 2018, "See explanation below" (no result was certified).
                entry = states.setdefault(state, {"house": {}, "senate": [], "footnotes": {}})
                entry.setdefault("houseEmpty", []).append(key[1])
            return
        where = f"{year} {state} {key}"
        contest = _candidates(_pair(tokens, where), where, parties, state, alone)
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


def _runoff_day(text):
    """The day of the runoff a footnote says its counts are from, or None."""
    if "runoff" not in (text or ""):
        return None
    found = (re.search(r"from \w+'s (\w+ \d{1,2}, \d{4}),", text) or
             re.search(r"from the runoff election held on (\w+ \d{1,2}, \d{4})", text))
    return _date_of(found.group(1)) if found else None


def result_of(contest, footnotes, year, state=None, round_=None):
    """The contest as the page shows it: who won, with what share, by what
    margin, all computed from the Clerk's counts.

    Shares are of the votes cast for a candidate, named or written in;
    blank, void, over- and under-votes chose no one. Where the Clerk
    footnotes counts as a runoff's (Georgia's January 5, 2021 runoff), the
    result is the runoff's, between the people it lists, dated from the
    footnote. A ranked-choice tabulation's final round (Maine's 2nd district
    in 2024) is shown as that round.

    *round_* is an ``overrides.SEAT_HISTORY_ROUNDS`` entry: counts the
    Clerk prints with no footnote that the jurisdiction's own official
    results give as a later round's (Guam's November 17, 2020 runoff). It
    applies only where the file prints exactly its names and counts and no
    other; anything else is an error a person must look at, never a reading
    kept on a file that has changed (rule 8's loud side)."""
    rows = list(contest["rows"])
    kind = "general"
    date = ELECTION_DAYS[year]
    unnamed = contest["unnamed"]
    if round_ is not None:
        printed = {r["name"]: r["votes"] for r in rows}
        # A footnote or a round the file names is the file's own word, and
        # an entry beside it is stale.
        if printed != round_["counts"] or unnamed or len(printed) != len(rows) or \
                contest.get("rcvRound") or \
                any(r.get("note") or r.get("unopposed") is not None for r in rows):
            raise ClerkFormatError(
                f"{year}: overrides.SEAT_HISTORY_ROUNDS names counts the Clerk's file does not "
                f"print as its only ones: {round_['counts']} against {printed} "
                f"(and {unnamed} unnamed)")
        if round_["kind"] not in ("runoff", "rcv-final") or \
                (round_["kind"] == "runoff") != bool(round_.get("date")):
            raise ClerkFormatError(f"{year}: a SEAT_HISTORY_ROUNDS entry of kind "
                                   f"{round_['kind']!r} with date {round_.get('date')!r}")
        kind = round_["kind"]
        date = round_.get("date") or date
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
        text = next(iter(texts))
        if len(texts) == 1 and RCV_NOTE.search(text) and len(noted) == 2:
            # Maine's 2022 2nd district: the two the final round left, with
            # that round's counts, beside the others' first choices. The
            # result is the final round's, between the two.
            rows, unnamed, kind = noted, 0, "rcv-final"
        else:
            # One footnote for the runoff (Georgia's 2020 Senate seats), or
            # one per candidate naming the same runoff (Mississippi's 2018
            # special: "This vote count is from the runoff election held on
            # November 27, 2018. Mike Espy received ...").
            dates = {_runoff_day(t) for t in texts}
            if len(dates) != 1 or None in dates:
                raise ClerkFormatError(f"{year}: footnoted counts that are not one runoff's: {texts}")
            date = dates.pop()
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
    if round_ is not None:
        # Whose word the round is: the page names the document and links it.
        title, url = round_["source"]
        out["roundFrom"] = "official"
        out["roundSource"] = {"title": title, "url": url}
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


def name_forms(seat, year):
    """``{the Clerk's name: [the second compilation's name]}`` for the
    contest the cache keys *seat* in *year*: what an evidenced
    ``overrides.SEAT_HISTORY_NAMES`` entry says the second source writes
    for a name the Clerk prints otherwise (the legal name Pennsylvania's
    returns print, "Madeleine Dean Cunnane", beside "Madeleine Dean")."""
    from .overrides import SEAT_HISTORY_NAMES
    out = {}
    for (where, when, clerk), (form, _evidence) in SEAT_HISTORY_NAMES.items():
        if where == seat and when == year:
            out.setdefault(clerk, []).append(form)
    return out


def round_of(seat, year):
    """The ``overrides.SEAT_HISTORY_ROUNDS`` entry for the contest the cache
    keys *seat* in *year*, or None: the Clerk's counts that its file prints
    without a footnote and the jurisdiction's own results give as a runoff's
    or a final round's (:func:`result_of`)."""
    from .overrides import SEAT_HISTORY_ROUNDS
    return SEAT_HISTORY_ROUNDS.get((seat, year))


def _check(result, rows, forms=None):
    """Does a second source's table *rows* (``[{"name", "votes", "won"?}]``)
    name the Clerk's winner and runner-up, in that order, with counts within
    :data:`TOLERANCE` of the Clerk's? Returns ``(verdict, differences)``:
    ``"agree"``, ``"disagree"``, or ``None`` when the table is not about
    these people. *forms* is :func:`name_forms`'s for the contest: another
    form of a Clerk's name that the second source writes, by evidence."""
    wanted = result["candidates"]
    # A write-in runner-up (Kentucky's 4th: 1,131 votes) is a name the
    # other compilations do not list: the winner alone is checked.
    if len(wanted) == 2 and re.search(r"write-in", wanted[1].get("party") or "", re.I):
        wanted = wanted[:1]
    found = []
    for person in wanted:
        match = _find(person["name"], rows, (forms or {}).get(person["name"], ()))
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


def _find(name, rows, forms=()):
    """The one row of *rows* that is *name*: by surname; among two of one
    surname (South Dakota's Dusty and Sheryl Johnson) by the first name
    too; and only where no surname matches, a surname a letter apart
    (Tennessee's 9th: "Bergmann" and "Bergman"), so long as one row has it.

    *forms* are other names the same person goes by, from an evidenced
    ``overrides.SEAT_HISTORY_NAMES`` entry ("Madeleine Dean" for the Clerk's
    "Madeleine Dean Cunnane"): a row whose whole name is one of them is the
    person too, never a row sharing only a word of it, and two rows that
    either way finds are nobody's."""
    found = _find_by_name(name, rows)
    if not forms:
        return found
    wanted = {tuple(_fold(form).split()) for form in forms}
    exact = [r for r in rows if tuple(_fold(r["name"]).split()) in wanted]
    either = {id(r): r for r in ([found] if found is not None else []) + exact}
    return next(iter(either.values())) if len(either) == 1 else None


def _find_by_name(name, rows):
    last = surname(name)
    if not last:
        return None
    first = _fold(name).split()[0]
    def words(row):
        # A surname written as two words is one spelling: the Clerk's
        # "Lynnette GreyBull" is Wikipedia's "Lynnette Grey Bull".
        found = _fold(row["name"]).split()
        return found + [a + b for a, b in zip(found, found[1:])]
    matches = [r for r in rows if last in words(r)]
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


# A box ends with "{{Election box end}}" or, on some pages, a bare
# "{{end}}" (the Northern Mariana Islands' 2020 page).
_WBOX = re.compile(r"\{\{\s*Election box (?:open primary )?begin[^}]*?\|\s*title\s*=\s*([^\n|}]+)"
                   r".*?\{\{\s*(?:Election box end|end)\s*\}\}", re.S | re.I)
# "{{Election box  winning candidate ..." with two spaces (Alabama's 2nd in
# 2020, Tennessee's districts in 2022) is the same template; read as
# written, the winner's or the runner-up's row was not read at all.
_BOX_SPACES = re.compile(r"\{\{\s*Election box\s+", re.I)
# A footnote set in a name's field ("[[Art Robinson]]<ref>Co-nominated by
# Constitution Party.</ref>", Oregon's 4th in 2018) is not the name.
_REFS = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)


def _name(raw):
    from .results import clean_name
    return clean_name(_REFS.sub("", raw or ""))
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
    from .results import _ROW, _stage, template_fields
    out = []
    text = _BOX_SPACES.sub("{{Election box ", text or "")
    for match in _WBOX.finditer(text):
        body = match.group(0)
        parts = [(_stage(match.group(1), cycle=None) or "general", body)]
        split = _OPEN_GENERAL.search(body)
        if split:
            parts = [("primary", body[:split.start()]), ("general", body[split.end():])]
        for stage, part in parts:
            rows = []
            for row in _ROW.finditer(part):
                fields = template_fields(row.group("body"))
                name = _name(fields.get("candidate", ""))
                if not name:
                    continue
                rows.append({"name": name, "votes": _votes(fields.get("votes")),
                             "won": row.group("kind").lower().startswith("winning"),
                             "party": _name(fields.get("party", "")) or None})
            if rows:
                out.append((stage, rows))
    return out


_INFOBOX = re.compile(r"\{\{\s*Infobox election\b", re.I)


def _infobox_fields(text):
    from .results import template_body, template_fields
    match = _INFOBOX.search(text or "")
    if not match:
        return None
    return template_fields("|" + template_body(text, match.start()).split("|", 1)[-1])


def infobox_rows(text, round_=None):
    """The first ``{{Infobox election}}``'s candidates and popular votes;
    with *round_*, that round's counts (``"2data1"``) of a ranked-choice
    election's infobox."""
    fields = _infobox_fields(text)
    if fields is None:
        return []
    rows = []
    for key, value in fields.items():
        found = re.fullmatch(r"(?:candidate|nominee)(\d+)", key)
        if not found:
            continue
        name = _name(value)
        number = found.group(1)
        if round_:
            votes = _votes(fields.get(f"{round_}data{number}"))
        else:
            # A ranked-choice election's infobox gives each round instead
            # ("1data1" the first, as Alaska's 2024 page does): the first
            # round is what the Clerk lists.
            votes = _votes(fields.get(f"popular_vote{number}")) or \
                _votes(fields.get(f"1data{number}"))
        if name:
            rows.append({"name": name, "votes": votes,
                         "party": _name(fields.get(f"party{found.group(1)}", "")) or None})
    return rows


def infobox_rounds(text):
    """The rounds a ranked-choice election's infobox gives (``1blank =
    First round``, ``2blank = Maximum round``): their numbers, in order."""
    fields = _infobox_fields(text) or {}
    return sorted(int(m.group(1)) for k, v in fields.items()
                  for m in [re.fullmatch(r"(\d)blank", k)]
                  if m and re.search(r"round", v or "", re.I))


def final_round_check(result, text, forms=None):
    """Is a ranked-choice contest the Clerk prints with two names and no
    footnote its final round? Maine's 2nd district in 2018: the Clerk lists
    Golden 142,440 and Poliquin 138,931, the counts of the final round
    between the two the tabulation left, where four were on the ballot and
    Poliquin led the first round; read as first choices, Golden "led first
    choices", which he did not. It is the final round only where the second
    compilation's own final round (its infobox's last round, of more than
    one) names the same two with the same counts, and its first round does
    not. Returns ``(verdict, differences)``: "agree" only then, else None.
    (Maine's own certified tabulation now says so of that contest, through
    ``overrides.SEAT_HISTORY_ROUNDS``, which this reading stands behind.)"""
    rounds = infobox_rounds(text)
    if len(rounds) < 2 or len(result["candidates"]) != 2 or result.get("allCandidates") != 2:
        return None, []
    if _check(result, _summed(infobox_rows(text, rounds[0])), forms)[0] == "agree":
        return None, []
    verdict, differences = _check(result, _summed(infobox_rows(text, rounds[-1])), forms)
    return ("agree", differences) if verdict == "agree" else (None, [])


def wiki_check(result, text, stage="general", forms=None):
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
        # (American Samoa's 2024 delegate election). A ranked-choice
        # tabulation's final round (Maine's 2nd in 2022) is checked
        # against the infobox's last round.
        rounds = infobox_rounds(text)
        last = rounds[-1] if result.get("kind") == "rcv-final" and len(rounds) > 1 else None
        boxes = [("general", infobox_rows(text, last))]
    for box_stage, rows in boxes:
        if box_stage != stage:
            continue
        verdict, diff = _check(result, _summed(rows), forms)
        if verdict:
            verdicts.append(verdict)
            if verdict == "agree" and not differences:
                differences = diff
    if "agree" in verdicts:
        return "agree", differences
    return ("disagree" if verdicts else None), []


def house_check(result, section, forms=None):
    """A House result against its district's section of the state's page.
    A runoff's counts (Louisiana's 5th in 2020) are checked against the
    runoff's table, never the first round's: against the open primary's,
    Letlow's runoff count "disagreed". A ranked-choice contest the Clerk
    prints with two names and no footnote that is the final round
    (:func:`final_round_check`) becomes the final round's result, and says
    the second compilation is what gives it as such (``roundFrom``)."""
    stage = "runoff" if result["kind"] == "runoff" else "general"
    verdict, differences = wiki_check(result, section, stage=stage, forms=forms)
    if verdict != "agree" and result.get("rankedChoice") == "first-choices":
        final, diff = final_round_check(result, section, forms)
        if final == "agree":
            result["kind"] = "rcv-final"
            result.pop("rankedChoice")
            result["roundFrom"] = "second-compilation"
            return final, diff
    return verdict, differences


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


def mit_check(result, mit, state, special, forms=None):
    rows = mit.get((result["year"], state, special, "runoff" if result["kind"] == "runoff" else "general"))
    if not rows or any(r["unofficial"] for r in rows):
        return None, []
    return _check(result, _summed(rows), forms)


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
    lines = [okina(line) for line in pdf_lines(data, decode=clerk_decoder(data))]
    return parse_statistics(lines, year, chambers)


_GRAVE_IN_WORD = re.compile(r"(?<=[^\W\d_])`(?=[^\W\d_])")


def okina(line):
    """The Clerk's spacing grave accent inside a word is the Hawaiian
    ʻokina (U+02BB): its fonts name byte 0x60 "grave", and the one name it
    is printed in is "Kaiali`i “Kai” Kahele" (Hawaii's 2nd, 2020), whose
    name is Kaialiʻi. A grave anywhere else is not read as anything
    (ClerkFormatError), as a byte no font names is not."""
    line = _GRAVE_IN_WORD.sub("ʻ", line)
    if "`" in line:
        raise ClerkFormatError(f"a grave accent outside a word in the Clerk's text: {line!r}")
    return line


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


def house_page_sections(state, read=_wiki_page, year=HOUSE_YEAR):
    """``{district: section}`` from a state's House results page(s) for
    *year*."""
    from .results import page_titles, house_sections, sub_articles
    for title in page_titles(state, "H", cycle=year):
        text = read(title)
        if text is None:
            continue
        if not _WBOX.search(_BOX_SPACES.sub("{{Election box ", text)) and \
                not _INFOBOX.search(text):
            # Not a results page: "2022 ... elections in Delaware" leads to
            # the national article, which holds no state's boxes.
            continue
        sections = house_sections(text, at_large=True)
        if set(sections) == {0} and sub_articles(text, title):
            sections = {}
        for sub in sub_articles(text, title):
            sections.update(house_sections(read(sub) or ""))
        return sections, title
    return {}, None


def senate_class_of(term_ends):
    """The class of the Senate seat a term ending on *term_ends* belongs to:
    a class's terms end every six years (class I in 2025 and 2031)."""
    try:
        year = int(str(term_ends)[:4])
    except ValueError:
        return None
    for senate_class, ends in SENATE_TERM_ENDS.items():
        if (year - int(ends[:4])) % 6 == 0:
            return senate_class
    return None


def read_terms(fetch=_download):
    """Who served in each seat from :data:`TERMS_FROM` to :data:`TERMS_TO`,
    from congress-legislators' terms, keyed by the seat and never by a name:
    ``{"house": {"TX-35": [term]}, "senate": {"GA-3": [term]}}``, each term
    ``{"id", "name", "party", "start", "end", "how"?}``. One person's terms
    in a row in one seat, come by the same way, are one; an appointment and
    the term its appointee then won stay two."""
    out = {"house": {}, "senate": {}}
    for url in LEGISLATORS_URLS:
        for person in json.loads(fetch(url)):
            ids = person.get("id") or {}
            bioguide = ids.get("bioguide")
            names = person.get("name") or {}
            name = names.get("official_full") or " ".join(
                n for n in (names.get("first"), names.get("last")) if n)
            if not bioguide or not name:
                continue
            for term in person.get("terms") or []:
                start, end = term.get("start") or "", term.get("end") or ""
                if not start or not end or end <= TERMS_FROM or start >= TERMS_TO:
                    continue
                if term.get("type") == "rep":
                    store, key = out["house"], f"{term.get('state')}-{term.get('district') or 0}"
                elif term.get("type") == "sen" and term.get("class") in SENATE_TERM_ENDS:
                    store, key = out["senate"], f"{term.get('state')}-{term['class']}"
                else:
                    continue
                record = {"id": bioguide, "name": name, "party": term.get("party") or "",
                          "start": start, "end": end}
                if term.get("how") == "appointment":
                    record["how"] = "appointment"
                store.setdefault(key, []).append(record)
    for store in out.values():
        for key, terms in store.items():
            terms.sort(key=lambda t: (t["start"], t["id"]))
            joined = []
            for term in terms:
                last = joined[-1] if joined else None
                if last and last["id"] == term["id"] and term["start"] <= last["end"] \
                        and last.get("how") == term.get("how"):
                    last["end"] = max(last["end"], term["end"])
                    continue
                joined.append(dict(term))
            store[key] = joined
    return out


def build(race_list, log=print, fetch=_download, read_wiki=_wiki_page, today=None):
    """Read the Clerk's statistics for every year of :data:`YEARS`, the
    second sources and the seats' terms; the cache.

    ``house`` holds 2024's House results (the race's last election) and
    ``houseEarlier`` the earlier years' by year; ``senate`` every election
    to the class of a Senate seat on the ballot; ``seats`` the districts the
    Clerk lists each year (0 for a seat elected at large), ``noResult`` the
    districts it lists with no count, and ``terms`` who served each seat."""
    today = today or datetime.date.today().isoformat()
    clerk = {}
    for year in YEARS:
        clerk[year] = read_clerk(year, fetch=fetch)
        log(f"  read the Clerk's {year} statistics: {len(clerk[year])} states and territories")
    try:
        mit = read_mit(fetch=fetch)
        log(f"  read MIT's Senate returns ({sum(len(v) for v in mit.values())} rows, {len(mit)} contests)")
    except Exception as exc:     # a failed read checks nothing (rule 8)
        log(f"  [warn] MIT's Senate returns unreadable ({exc}); the Senate is checked "
            "against Wikipedia alone")
        mit = {}
    terms = read_terms(fetch=fetch)
    log(f"  read congress-legislators' terms: {len(terms['house'])} House seats, "
        f"{len(terms['senate'])} Senate seats")

    cache = {"read": today, "years": list(YEARS), "house": {}, "senate": {}, "withheld": [],
             "houseEarlier": {str(y): {} for y in YEARS if y != HOUSE_YEAR},
             "seats": {}, "noResult": {}, "terms": terms}
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
    for year in YEARS:
        store = cache["house"] if year == HOUSE_YEAR else cache["houseEarlier"][str(year)]
        seats = cache["seats"].setdefault(str(year), {})
        for state in house_states:
            entry = clerk[year].get(state) or {}
            contests = entry.get("house") or {}
            empty = entry.get("houseEmpty") or []
            if not contests and not empty:
                if year in FOUR_YEAR_SEATS.get(state, YEARS):
                    raise ClerkFormatError(f"the Clerk's {year} statistics list no House "
                                           f"election in {state}")
                continue
            seats[state] = sorted(set(contests) | set(empty))
            for district in empty:
                cache["noResult"].setdefault(str(year), []).append(f"{state}-{district}")
            sections, page = house_page_sections(state, read=wiki, year=year)
            for district, contest in sorted(contests.items()):
                key = f"{state}-{district}"
                result = result_of(contest, entry["footnotes"], year, state,
                                   round_=round_of(key, year))
                if not result:
                    continue
                section = sections.get(district) or (sections.get(0) if len(contests) == 1 else None)
                verdict, differences = (house_check(result, section, name_forms(key, year))
                                        if section else (None, []))
                keep(store, key, result, verdict, differences,
                     {"by": "wikipedia", "page": page}, page)
            log(f"  {year} {state}: {len(contests)} House contest(s) read")

    # The elections to the classes of the seats on the ballot: a seat's
    # term ends when its class's does (senate_last), and the strip holds
    # every election to that class from 2018, specials included.
    wanted = {(r["state"], r.get("senateClass")) for r in race_list if r["chamber"] == "Senate"}
    from .results import page_titles
    for state, senate_class in sorted(wanted, key=lambda w: (w[0], w[1] or 0)):
        for year in YEARS:
            entry = clerk[year].get(state) or {}
            for contest in entry.get("senate") or []:
                if senate_class_of(contest["termEnds"]) != senate_class:
                    continue
                key = f"{state}-{year}-{contest['term']}"
                result = result_of(contest, entry.get("footnotes") or {}, year, state,
                                   round_=round_of(key, year))
                if not result:
                    continue
                special = contest["term"] == "unexpired"
                result.update(term=contest["term"], termEnds=contest["termEnds"])
                forms = name_forms(key, year)
                verdict, differences = mit_check(result, mit, state, special, forms)
                checked, page = {"by": "mit"}, None
                if verdict is None:
                    titles = page_titles(state, "S", cycle=year)
                    page = titles[1] if special else titles[0]
                    text = wiki(page)
                    stage = "runoff" if result["kind"] == "runoff" else "general"
                    verdict, differences = (wiki_check(result, text, stage=stage, forms=forms)
                                            if text else (None, []))
                    checked = {"by": "wikipedia", "page": page}
                keep(cache["senate"], key, result, verdict, differences, checked, page)
    for key in cache["noResult"]:
        cache["noResult"][key].sort()
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
            "allCandidates", "note", "unopposedByName", "rankedChoice", "roundFrom",
            "roundSource")
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


# How long after the counted election's term began a holder may have been
# sworn in and still be that election's winner: Jim Justice took the Senate
# seat he won in 2024 on January 14, 2025.
SEATING_GRACE = 30


def _same_person(a, b):
    """The counted winner and the seat's holder, by first given name and
    surname. Used only to leave a holder unremarked, never to attribute a
    result: Raúl M. Grijalva won Arizona's 7th in 2024, and Adelita S.
    Grijalva, who shares his surname, holds it after a special election."""
    def key(name):
        words = [w for w in _fold(name).split() if w not in SUFFIXES]
        return (words[0], surname(name)) if words else ("", "")
    return key(a) == key(b)


def _seat_holders(race, record, snapshot):
    """Everyone who held the race's seat before Election Day by the
    record (frozen, so it keeps the special election's winner past January
    3) or the membership snapshot: ``[{"name", "since", "appointed"}]``."""
    from . import cycle as cycle_mod
    day = (record or {}).get("electionDay") or cycle_mod.general_election_day(
        (record or {}).get("cycle") or cycle_mod.CYCLE).isoformat()
    out = []
    inc = ((record or {}).get("incumbents") or {}).get(race["id"])
    if inc and inc.get("termStart"):
        out.append({"name": inc["name"], "since": inc["termStart"],
                    "appointed": bool(inc.get("appointed"))})
    for person in (snapshot or {}).get("legislators") or []:
        start = person.get("termStart") or ""
        if not start or start >= day or person.get("chamber") != race["chamber"] or \
                person.get("state") != race["state"]:
            continue
        if race["chamber"] == "Senate":
            if person.get("senateClass") != race.get("senateClass"):
                continue
        elif (person.get("district") or 0) != (race.get("district") or 0):
            continue
        out.append({"name": person["name"], "since": start,
                    "appointed": person.get("how") == "appointment"})
    return out


def seated_since(race, result, record, snapshot):
    """Who has held the seat since the counted election without having won
    it, or None: ``{"name", "since", "how"}``, *how* "appointment" or
    "special-election". Five House seats on the 2026 ballot were filled by
    special elections after 2024's (VA-11, AZ-7, NJ-11, GA-14, GA-13), and
    "the last election to this district" over Gerald Connolly's 2024 result
    named a man who died in office as the seat's last winner, beside the
    member who won it after him (rule 90). A House vacancy is filled only by
    election; a Senate one by appointment until one is held."""
    if not result or not result.get("candidates"):
        return None
    date = result["date"]
    year = int(date[:4])
    # The counted election's term began on January 3 after a November
    # election; a January runoff's winner is seated within days.
    began = f"{year + 1}-01-03" if date[5:7] in ("11", "12") else date
    late = (datetime.date.fromisoformat(began) +
            datetime.timedelta(days=SEATING_GRACE)).isoformat()
    winner = result["candidates"][0]["name"]
    found = None
    for holder in _seat_holders(race, record, snapshot):
        since = holder["since"]
        if since <= date or _same_person(holder["name"], winner):
            continue
        if not holder["appointed"] and since <= late:
            continue
        if found is None or since > found["since"]:
            found = {"name": holder["name"], "since": since,
                     "how": "appointment" if holder["appointed"] else "special-election"}
    return found


# ------------------------------------------------------------- the strip

# How long after a Congress's first day a member may have been sworn in and
# still be the one the election chose to begin it, and how long before its
# end they may leave and still have served it out (SEATING_GRACE's reason).
STRIP_GRACE = SEATING_GRACE


def _strip_result(result, chamber):
    """A cell's copy of a result: who won, by what, as the strip draws it."""
    keys = ("year", "date", "kind", "margin", "rankedChoice", "allCandidates", "roundFrom",
            "roundSource")
    out = {k: result[k] for k in keys if k in result}
    out["candidates"] = [{k: c[k] for k in ("name", "party", "share") if k in c}
                         for c in result["candidates"]]
    if chamber == "Senate":
        out["term"] = result.get("term")
    if result.get("rankedChoice") == "first-choices" and result.get("total") and \
            2 * result["candidates"][0]["votes"] > result["total"]:
        # More than half of every vote counted for a candidate: elected in
        # the first round (Chellie Pingree in each year), not only ahead.
        out["firstChoiceMajority"] = True
    checked = result.get("checked") or {}
    if checked.get("by") == "mit":
        out["checkedBy"] = "mit"
    elif checked.get("page"):
        out["checkedBy"] = checked["page"]
    return out


def _general_day(iso):
    """Whether *iso* is a November general election day: the Tuesday after
    the first Monday of November in an even year."""
    day = datetime.date.fromisoformat(iso)
    return day.year % 2 == 0 and day.month == 11 and day.weekday() == 1 and 2 <= day.day <= 8


def _next_day(end, start):
    """Whether a term beginning *start* follows one ending *end*: the same
    day (Pete Ricketts's, November 5, 2024) or the next (Cindy
    Hyde-Smith's, November 27 and 28, 2018)."""
    gap = (datetime.date.fromisoformat(start) - datetime.date.fromisoformat(end)).days
    return 0 <= gap <= 1


def _scheduled_end(term, following):
    """Whether an appointee's term end is the date congress-legislators
    gives until the special election's winner is seated, not a day they
    left: Ashley Moody's and Jon Husted's appointments "end" on November 3,
    2026, the specials' day, before it came and after it alike, and an
    appointee serves until the winner takes the seat (Moody is a candidate
    in hers). An appointee's term ending on a November election day is the
    record's word only where the same person's next term begins then (Pete
    Ricketts, appointed, then elected on November 5, 2024). One ending with
    the term itself (Alan Armstrong's, January 3, 2027) is the window's end
    and carries no date either way."""
    return term.get("how") == "appointment" and not following and _general_day(term["end"])


def _holders(terms, start, end):
    """Who served the seat between *start* and *end*, by congress-legislators'
    terms: ``[{"id", "name", "party", "from"?, "until"?, "how"?,
    "elected"?, "untilSeated"?}]``, a date only where it is not the
    window's own (a member seated late, a death). One person's terms one
    after the other are one line (Pete Ricketts, appointed on January 23,
    2023 and elected on November 5, 2024: ``elected``); an appointee whose
    term ends on the special election's date with nothing after it is
    serving until its winner is seated (``untilSeated``), never "until"
    that day (:func:`_scheduled_end`). Whether an "until" has come is the
    page's to say, on the reader's day."""
    late = (datetime.date.fromisoformat(start) +
            datetime.timedelta(days=STRIP_GRACE)).isoformat()
    early = (datetime.date.fromisoformat(end) -
             datetime.timedelta(days=STRIP_GRACE)).isoformat()
    ordered = sorted(terms or [], key=lambda t: (t["start"], t["end"]))
    out = []
    for i, term in enumerate(ordered):
        if term["end"] <= start or term["start"] >= end:
            continue
        if term["start"] <= start and term["end"] <= late:
            # Whoever held it until the winner was seated: Kelly Loeffler
            # until January 20, 2021, under the special Raphael Warnock won
            # on January 5.
            continue
        following = [t for t in ordered[i + 1:]
                     if t["id"] == term["id"] and _next_day(term["end"], t["start"])]
        before = out[-1] if out else None
        if before and before["id"] == term["id"] and _next_day(before["_end"], term["start"]):
            # The same person again from the day the last term ended.
            if term.get("how") != before.get("how") and "elected" not in before:
                before["elected"] = term["start"]
            before["_end"] = term["end"]
            before.pop("until", None)
            before.pop("untilSeated", None)
            holder = before
        else:
            holder = {"id": term["id"], "name": term["name"], "party": term["party"],
                      "_end": term["end"]}
            if term["start"] > late:
                holder["from"] = term["start"]
            if term.get("how"):
                holder["how"] = term["how"]
            out.append(holder)
        if _scheduled_end(term, following):
            holder["untilSeated"] = True
        elif term["end"] < early:
            holder["until"] = term["end"]
    for holder in out:
        holder.pop("_end", None)
    return out


def _mark_winner(cell, forms=None):
    """Mark the holder who is the counted winner, seated with the term
    (``winner``), so the page need not name them twice. Only someone who
    served the whole term from its first day is compared, and by surname
    alone, since the Clerk prints the ballot's name ("Rob Wittman") and
    congress-legislators the member's ("Robert J. Wittman"): a comparison
    that leaves a holder unremarked, never one that attributes a result.
    Anyone seated late, or who left early, is named with their dates
    whoever they are (Adelita Grijalva after Raúl Grijalva). *forms* is
    :func:`name_forms`'s for the contest: the Clerk's "Madeleine Dean
    Cunnane" is the "Madeleine Dean" who served, by the evidence there, and
    is not named a second time as though someone else had."""
    result = cell.get("result") or {}
    if not result.get("candidates"):
        return
    winner = result["candidates"][0]["name"]
    if result.get("rankedChoice") == "first-choices" and not result.get("firstChoiceMajority"):
        return                       # a lead in first choices is not a win
    # A form is the whole name the evidence ties to the winner, so it is
    # compared whole: by its surname, a full-term holder "Howard Dean"
    # would have been marked the winner of PA-4 2020 (the second reader of
    # PR #242).
    whole = {" ".join(_fold(f).split()) for f in (forms or {}).get(winner, ())}
    for holder in cell.get("holders") or []:
        if "from" not in holder and "until" not in holder and (
                surname(holder["name"]) == surname(winner)
                or " ".join(_fold(holder["name"]).split()) in whole):
            holder["winner"] = True


def house_breaks(state, seats):
    """``{year: change}``: each election from 2020 to 2026 that *state*
    held on lines other than the election's before it. The map drawn after
    the 2020 census was used from 2022 wherever a state has more than one
    seat (a state elected at large in every year of *seats* has no lines to
    change); every other change is ``districts.REDRAWN_BEFORE``'s, and 2026's
    ``REDRAWN``'s. A change is ``{"kind": "census"}``, or ``{"kind":
    "enacted" | "redrawn", "title", "drawnBy", "url"?}``."""
    from .districts import REDRAWN, REDRAWN_BEFORE
    out = {}
    known = [seats.get(str(y), {}).get(state) for y in YEARS]
    at_large = all(s == [0] for s in known if s is not None)
    for year in (2020, 2022, 2024):
        record = REDRAWN_BEFORE.get(state, {}).get(year)
        if record:
            out[year] = {"kind": "enacted", "title": record["title"],
                         "drawnBy": record["drawnBy"], "url": record["url"]}
            if record.get("lead"):
                out[year]["lead"] = True
        elif year == 2022 and not at_large:
            out[year] = {"kind": "census"}
    if state in REDRAWN:
        after = REDRAWN[state]["after"]
        out[2026] = {"kind": "redrawn", "title": after["title"],
                     "drawnBy": after.get("drawnBy") or ""}
    return out


def _house_strip(race, cache):
    state, district = race["state"], race.get("district") or 0
    seats = cache.get("seats") or {}
    terms = (cache.get("terms") or {}).get("house") or {}
    breaks = house_breaks(state, seats)
    withheld = {(w["seat"], w["year"]): w for w in cache.get("withheld") or []}
    # Each year's lines: the eras between the breaks, the last one the
    # 2026 map's unless 2026 broke it.
    eras, current = [], None
    for year in YEARS:
        if current is None or year in breaks:
            current = {"from": year, "to": year}
            eras.append(current)
        current["to"] = year
    for era in eras:
        era["same"] = not any(era["from"] < y <= 2026 for y in breaks)
    cells = []
    for year in YEARS:
        era = next(i for i, e in enumerate(eras) if e["from"] <= year <= e["to"])
        cell = {"year": year, "era": era}
        listed = (seats.get(str(year)) or {}).get(state)
        if listed is None:
            cell["none"] = "no-election"
            cells.append(cell)
            continue
        number = district if district in listed else (0 if listed == [0] else None)
        if number is None:
            cell["none"] = "no-district"
            cells.append(cell)
            continue
        if number != district:
            cell["atLarge"] = True
        key = f"{state}-{number}"
        cell["district"] = number
        store = cache.get("house") if year == HOUSE_YEAR else \
            (cache.get("houseEarlier") or {}).get(str(year))
        result = (store or {}).get(key)
        if result:
            cell["result"] = _strip_result(result, "House")
        elif (key, year) in withheld:
            cell["withheld"] = withheld[(key, year)]["why"]
            if (withheld[(key, year)].get("result") or {}).get("kind") == "unopposed":
                # The Clerk printed a name and no count (Oklahoma's 3rd in
                # 2024): there is no count for the cell to call unconfirmed.
                cell["withheldUnopposed"] = True
        elif key in ((cache.get("noResult") or {}).get(str(year)) or []):
            cell["none"] = "no-result"
        else:
            cell["withheld"] = "unchecked"
        cell["holders"] = _holders(terms.get(key), f"{year + 1}-01-03", f"{year + 3}-01-03")
        _mark_winner(cell, name_forms(key, year))
        cells.append(cell)
    changes = [dict(change, year=year) for year, change in sorted(breaks.items())]
    return {"eras": eras, "cells": cells, "breaks": changes}


def _special_start(terms, result, date):
    """The day a special election's winner took the seat: the first term
    of the seat's that begins on or after the election, within
    SEATING_GRACE of it or of the January 3 after it, held by someone of
    the winner's surname - Markwayne Mullin on January 3, 2023, after
    November 8, 2022's special, so James Inhofe, who served until then, is
    not among those who served the term it chose. The election day itself
    where nothing fits (a result withheld, no term yet)."""
    if not result or not result.get("candidates"):
        return date
    year = int(date[:4])
    day = datetime.date.fromisoformat(date)
    if date[5:7] in ("11", "12"):
        day = datetime.date(year + 1, 1, 3)
    last = (day + datetime.timedelta(days=SEATING_GRACE)).isoformat()
    winner = surname(result["candidates"][0]["name"])
    starts = [t["start"] for t in terms or []
              if date <= t["start"] <= last and surname(t["name"]) == winner]
    return min(starts) if starts else date


def _senate_strip(race, cache):
    state, senate_class = race["state"], race.get("senateClass")
    terms = (cache.get("terms") or {}).get("senate") or {}
    found = []
    for key, result in (cache.get("senate") or {}).items():
        if key.startswith(state + "-") and senate_class_of(result.get("termEnds")) == senate_class:
            found.append((result["date"], {"result": _strip_result(result, "Senate"),
                                           "ends": result["termEnds"], "key": key}))
    for item in cache.get("withheld") or []:
        result = item.get("result") or {}
        if item["seat"].startswith(state + "-") and result.get("termEnds") and \
                senate_class_of(result["termEnds"]) == senate_class:
            found.append((result["date"], {"withheld": item["why"], "ends": result["termEnds"],
                                           "term": result.get("term")}))
    cells = []
    for date, item in sorted(found, key=lambda f: f[0]):
        # The Clerk's year, not the day's: Georgia's 2020 special was
        # decided in its runoff of January 5, 2021.
        year = (item.get("result") or {}).get("year") or int(date[:4])
        cell = {"year": year, "era": 0}
        ends = item.pop("ends")
        key = item.pop("key", None)
        cell.update(item)
        # Who served the term it chose: from January 3 after a regular
        # election; after a special, from the day its winner took the seat
        # (_special_start), so whoever held it until then is not among them.
        seat_terms = terms.get(f"{state}-{senate_class}")
        if (item.get("result") or {}).get("term") == "unexpired" or \
                item.get("term") == "unexpired":
            start = _special_start(seat_terms, item.get("result"), date)
        else:
            start = f"{year + 1}-01-03"
        cell["holders"] = _holders(seat_terms, start, ends)
        _mark_winner(cell, name_forms(key, year) if key else None)
        cells.append(cell)
    return {"eras": [{"from": YEARS[0], "to": YEARS[-1], "same": True}],
            "cells": cells, "breaks": []}


def seat_strip(race, cache):
    """The seat's elections from 2018 to 2024 (VISUALS-33), as a race's
    seat fold draws them: ``{"eras", "cells", "breaks"}``, or None where the
    cache holds no strip (one read before the strip was).

    A House district's elections are grouped by the lines they were fought
    on (``eras``), each era saying whether it is the lines this district is
    elected on in 2026 (``same``): a result on other lines is the district
    of that number on that map, labelled as such, never this district's
    (rule 90). A cell is ``{"year", "era", "district"?, "result" |
    "withheld" | "none", "holders"}``; *none* is "no-election" (Puerto
    Rico's four-year seat), "no-district" (no district of that number on
    that map) or "no-result" (the Clerk lists none: North Carolina's 9th in
    2018). A Senate seat's lines never change; its cells are the elections
    to its class, specials included."""
    if not cache or "seats" not in cache:
        return None
    if race["chamber"] == "House":
        return _house_strip(race, cache)
    return _senate_strip(race, cache)


def apply(races, cache, record=None, snapshot=None):
    """Attach ``lastElection`` to each race: the seat's last result as the
    page shows it, ``{"redrawn": True}`` for a district redrawn since, or
    ``{"withheld": why}`` where the sources disagree or one is missing.
    A result whose seat has been filled since by a special election or an
    appointment carries ``seatedSince`` (:func:`seated_since`): the result
    is then the last *regular* election, and the page says so.
    Each race also carries ``seatHistory``, the seat's elections from 2018
    (:func:`seat_strip`), where the cache holds them.
    Returns how many races carry a result."""
    from .districts import REDRAWN
    if not cache:
        return 0
    shown = 0
    # The House's withheld results by seat are 2024's; the earlier years'
    # are the strip's (Senate keys carry their year).
    withheld = {w["seat"]: w for w in cache.get("withheld") or []
                if w.get("year") == HOUSE_YEAR or not re.fullmatch(r"[A-Z]{2}-\d+", w["seat"])}
    for race in races:
        race.pop("lastElection", None)
        race.pop("seatHistory", None)
        strip = seat_strip(race, cache)
        if strip:
            race["seatHistory"] = strip
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
            result = None
            if held:
                race["lastElection"] = {"withheld": held[0]["why"], "year": held[0]["year"]}
            elif best:
                result = best
                race["lastElection"] = _shown(best, "Senate")
                shown += 1
        since = seated_since(race, result, record, snapshot) if result else None
        if since:
            race["lastElection"]["seatedSince"] = since
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
    if "seats" not in cache:
        out.append(("warn", "seat-history-strip-missing",
                    "the cache holds no elections before the last; run: python "
                    "build_profile_site.py seats", []))
        return out
    strip_held = sorted(f"{r['id']} {c['year']}: {c['withheld']}"
                        for r in races for c in (r.get("seatHistory") or {}).get("cells") or []
                        if c.get("withheld") and not (r["chamber"] == "House" and
                                                      c["year"] == HOUSE_YEAR))
    if strip_held:
        out.append(("warn", "seat-history-strip-withheld",
                    f"{len(strip_held)} earlier results in the seats' strips are not shown: the "
                    "Clerk's and the second source's disagree or no second source covers them",
                    strip_held))
    stale = stale_overrides(cache)
    if stale:
        out.append(("warn", "seat-history-override-stale",
                    f"{len(stale)} overrides.SEAT_HISTORY_NAMES or SEAT_HISTORY_ROUNDS entries "
                    "the cache does not bear out: read again (python build_profile_site.py "
                    "seats), and if they still do not, the Clerk's file or the second source "
                    "has changed and a person must look", stale))
    return out


def _cached(cache, seat, year):
    """Every result the cache holds for the contest it keys *seat* in
    *year*, shown or withheld: ``[(result, shown)]``."""
    if re.fullmatch(r"[A-Z]{2}-\d+", seat):
        store = cache.get("house") if year == HOUSE_YEAR else \
            (cache.get("houseEarlier") or {}).get(str(year))
    else:
        store = cache.get("senate")
    out = [(store[seat], True)] if seat in (store or {}) else []
    out += [(w.get("result") or {}, False) for w in cache.get("withheld") or []
            if w.get("seat") == seat and w.get("year") == year]
    return out


def stale_overrides(cache):
    """The ``overrides.SEAT_HISTORY_NAMES`` and ``SEAT_HISTORY_ROUNDS``
    entries the cache does not bear out, as the build reports any curated
    entry that matches nothing (CLAUDE.md, "Curated data"): a name form
    whose contest is not shown, or does not name that Clerk's name; a round
    whose contest is not shown as that round on the official document's
    word. A stale override is invisible on the page and quietly wrong."""
    from .overrides import SEAT_HISTORY_NAMES, SEAT_HISTORY_ROUNDS
    out = []
    for (seat, year, clerk), (form, _evidence) in sorted(SEAT_HISTORY_NAMES.items()):
        found = _cached(cache, seat, year)
        if not any(shown and any(c.get("name") == clerk for c in r.get("candidates") or [])
                   for r, shown in found):
            out.append(f"{seat} {year} {clerk!r} as {form!r}: "
                       + ("not shown" if found else "no such contest in the cache"))
    for (seat, year), entry in sorted(SEAT_HISTORY_ROUNDS.items()):
        found = _cached(cache, seat, year)
        if not any(shown and r.get("kind") == entry["kind"] and r.get("roundFrom") == "official"
                   for r, shown in found):
            what = "the runoff" if entry["kind"] == "runoff" else "the final round"
            out.append(f"{seat} {year} as {what}: "
                       + ("not shown as that round" if found else "no such contest in the cache"))
    return out
