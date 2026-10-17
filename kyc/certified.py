"""Who is on the November ballot, from the states' certified candidate lists.

A results page says who won a primary. It does not say who is on the
November ballot: a minor party's convention nominee, an unaffiliated
candidate who petitioned on, a top-four finisher promoted when four others
withdrew. Audited on 2026-10-17 against the states' own lists, the site
showed Alaska's at-large seat with two people on the ballot over a
certified four - and said the two it left out had withdrawn - left Alaska's
certified Daniel J. Sullivan Jr. "Not on the 2026 primary ballot", missed
thirteen qualified Florida candidates and seventeen Colorado ones, and
called American Samoa's seat uncontested over six certified names.

Once a state has certified its general-election candidates, its list is the
ballot (rule 77). Each reader below reads one state's published list:

* Alaska: the Division of Elections' candidate list for the general
  election. A "Certified Write-In" is not printed on the ballot and is not
  read as on it.
* Florida: the Division of Elections' candidate listing for the general
  election, federal offices. "Qualified" is on the ballot; "Defeated" in
  the primary is out; a write-in ("WRI") is not printed; a candidate
  unopposed in November is not printed either (Florida does not print an
  uncontested race) and is left as the results page has them.
* Colorado: the Secretary of State's official candidate list. A name
  struck through has withdrawn; "Write in? Y" is not printed.
* American Samoa: the Election Office's list of candidates the
  Commissioner of Elections has certified. The territory holds no primary.

Lists published only as a PDF (Iowa, Nebraska) are transcribed in
``overrides.CERTIFIED_BALLOTS``, with the document and the day it was read;
the standard library cannot read a PDF, and a guessed layout is worse than a
reviewed transcription.

Only what the ballot says is kept: the name as printed, the party, the
office and district, and whether the person is printed, withdrew, lost the
primary or is a write-in. The lists also carry addresses, phone numbers and
email addresses; none of it is read into anything (rule 64). A list that
cannot be read, or reads as something it should not (no rows, a status word
this reader does not know, fewer seats than the state has), is refused, and
the last list read is kept (rule 8).
"""

import datetime
import html
import re
import time
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; know-your-candidate/1.0)"
TIMEOUT = 60
GAP = 2.0           # seconds between requests to one state's server

# What a list entry can say about a person.
BALLOT = "ballot"               # printed on the November ballot
WITHDRAWN = "withdrawn"         # certified, then withdrew (struck through)
LOST_PRIMARY = "lost-primary"   # the list itself says they lost the primary
WRITE_IN = "write-in"           # a certified write-in: not printed
UNOPPOSED = "unopposed"         # Florida: unopposed in November, not printed
KINDS = (BALLOT, WITHDRAWN, LOST_PRIMARY, WRITE_IN, UNOPPOSED)

YEAR = 2026


class CertifiedError(RuntimeError):
    pass


def _text(fragment):
    """Visible text of an HTML fragment, whitespace collapsed."""
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = html.unescape(text).replace(" ", " ").replace("�", "")
    return re.sub(r"\s+", " ", text).strip()


_SUFFIX = re.compile(r"^(?:jr|sr|ii|iii|iv|v)\.?$", re.I)


def _quotes(name):
    return re.sub(r"[“”„″]", '"', name).replace("’", "'")


def last_first(name):
    """ "Sullivan, Daniel J. Jr." -> "Daniel J. Sullivan Jr."; a suffix
    written among the given names goes after the surname, as ballots and
    results pages write it."""
    name = _quotes(name).strip()
    if "," not in name:
        return re.sub(r"\s+", " ", name)
    last, given = (part.strip() for part in name.split(",", 1))
    words = given.split()
    suffix = [w for w in words if _SUFFIX.match(w)]
    words = [w for w in words if not _SUFFIX.match(w)]
    return " ".join(words + [last] + suffix).strip()


def entry(name, party, kind):
    if kind not in KINDS:
        raise CertifiedError(f"unknown kind {kind!r} for {name!r}")
    if len(name.split()) < 2:
        raise CertifiedError(f"unreadable name {name!r}")
    return {"name": name, "party": party, "kind": kind}


def senate(state):
    return f"S-{state}-{YEAR}"


def house(state, district):
    return f"H-{state}-{int(district):02d}-{YEAR}"


# ------------------------------------------------------------------ Alaska

AK_URL = "https://www.elections.alaska.gov/candidates/?election=26genr"
AK_SOURCE = "Alaska Division of Elections, 2026 General Election candidate list"
_AK_SECTIONS = (("us-senate", senate("AK")), ("us-house", house("AK", 0)))
_AK_CELL = re.compile(r"Candidate Name on Ballot[^>]*>(.*?)</td>", re.S)
_AK_PARTY = re.compile(r"^\((?:Registered )?([^()]+)\)\s*\(([^()]+)\)$")


def parse_alaska(page):
    """``{race_id: [entry]}`` from the Division of Elections' list."""
    if "General Election" not in page:
        raise CertifiedError("the Alaska page is not a general-election list")
    races = {}
    for anchor, rid in _AK_SECTIONS:
        start = page.find(f'id="{anchor}"')
        if start < 0:
            raise CertifiedError(f"the Alaska list has no {anchor} section")
        end = page.find("<h4", start + 10)
        section = page[start:end if end > 0 else None]
        out = []
        for cell in _AK_CELL.findall(section):
            strong = re.search(r"<strong>(.*?)</strong>", cell, re.S)
            small = re.search(r"<small>(.*?)</small>", cell, re.S)
            if not strong or not small:
                raise CertifiedError(f"unreadable Alaska row {_text(cell)[:80]!r}")
            note = _AK_PARTY.match(_text(small.group(1)))
            if not note:
                raise CertifiedError(f"unreadable Alaska party/status {_text(small.group(1))!r}")
            party, status = note.group(1).strip(), note.group(2).strip().lower()
            name = last_first(_text(strong.group(1)))
            if status == "certified":
                kind = WRITE_IN if "write-in" in _text(cell).lower() else BALLOT
            elif status.startswith("withdr"):
                kind = WITHDRAWN
            else:
                raise CertifiedError(f"unknown Alaska status {status!r} for {name}")
            out.append(entry(name, party, kind))
        if not any(e["kind"] == BALLOT for e in out):
            raise CertifiedError(f"the Alaska list prints nobody for {rid}")
        races[rid] = out
    return races


# ----------------------------------------------------------------- Florida

FL_URL = ("https://dos.elections.myflorida.com/candidates/CanList.asp"
          "?elecid=20261103-GEN&OfficeGroup=FED")
FL_SOURCE = "Florida Division of Elections, candidate listing for the 2026 General Election"
FL_HOUSE_SEATS = 28
# The Division's own party codes (dos.fl.gov, "Political Parties", read
# 2026-10-17). NPA is no party; WRI marks a write-in, not a party.
FL_PARTIES = {
    "DEM": "Democratic", "REP": "Republican", "NPA": "No Party Affiliation",
    "AMF": "America First Party of Florida", "ASP": "American Solidarity Party of Florida",
    "BPP": "Boricua Party", "CPP": "Coalition With A Purpose Party",
    "CSV": "Conservative Party of Florida", "CPF": "Constitution Party of Florida",
    "ECO": "Ecology Party of Florida", "FFP": "Florida Forward Party",
    "GRE": "Green Party of Florida", "IND": "Independent Party of Florida",
    "JEF": "Jeffersonian Party of Florida", "LPF": "Libertarian Party of Florida",
    "MGT": "MGTOW Party", "PSL": "Party for Socialism and Liberation - Florida",
    "WPF": "We the People Florida",
}
_FL_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_FL_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_FL_NAME = re.compile(r"^(.*?)\s*\((\w+)\)\s*(\*\s*Incumbent)?$")
_FL_HEADS = (("United States Senator", "S"), ("United States Representative", "H"))


def _fl_kind(status, primary, general, party, name):
    if party == "WRI":
        return WRITE_IN
    if status == "Qualified":
        return BALLOT
    if status == "Unopposed":
        return UNOPPOSED
    if status in ("Elected", "Defeated") and general:
        return BALLOT                       # after the count: they were on it
    if status == "Defeated" and primary == "Eliminated":
        return LOST_PRIMARY
    if status.startswith("Withdr"):
        return WITHDRAWN
    raise CertifiedError(f"unknown Florida status {status!r}/{primary!r} for {name}")


def parse_florida(page):
    """``{race_id: [entry]}`` from the Division's candidate listing."""
    marks = []
    for label, office in _FL_HEADS:
        at = page.find(f"<b>{label}")
        if at < 0:
            raise CertifiedError(f"the Florida listing has no {label} section")
        marks.append((at, office))
    marks.sort()
    races = {}
    for i, (at, office) in enumerate(marks):
        section = page[at:marks[i + 1][0] if i + 1 < len(marks) else None]
        district = None
        for row in _FL_ROW.findall(section):
            cells = [_text(c) for c in _FL_CELL.findall(row)]
            if len(cells) < 4 or cells[-4:] == ["Candidate", "Status", "Primary", "General"]:
                continue
            if office == "H":
                if len(cells) != 5:
                    continue
                if cells[0]:
                    if not cells[0].isdigit():
                        raise CertifiedError(f"unreadable Florida district {cells[0]!r}")
                    district = int(cells[0])
                if district is None:
                    raise CertifiedError("a Florida House row before any district")
                rid = house("FL", district)
            else:
                if len(cells) != 4:
                    continue
                rid = senate("FL")
            who, status, primary, general = cells[-4:]
            m = _FL_NAME.match(who)
            if not m:
                raise CertifiedError(f"unreadable Florida candidate {who!r}")
            raw, code = m.group(1), m.group(2).upper()
            name = last_first(re.sub(r"\s+,", ",", raw))
            party = FL_PARTIES.get(code, code if code != "WRI" else "")
            races.setdefault(rid, []).append(
                entry(name, party, _fl_kind(status, primary, general, code, name)))
    seats = sorted(int(rid.split("-")[2]) for rid in races if rid.startswith("H-"))
    if seats != list(range(1, FL_HOUSE_SEATS + 1)) or senate("FL") not in races:
        raise CertifiedError(f"the Florida listing covers House seats {seats} and "
                             f"{'a' if senate('FL') in races else 'no'} Senate race")
    return races


# ---------------------------------------------------------------- Colorado

CO_URL = "https://www.coloradosos.gov/pubs/elections/vote/generalCandidates.html"
CO_SOURCE = "Colorado Secretary of State, 2026 General Election Official Candidate List"
CO_HOUSE_SEATS = 8
_CO_HEAD = ["Candidate name", "Office", "District", "Party", "Write in?"]


def parse_colorado(page):
    """``{race_id: [entry]}`` from the Secretary of State's official list."""
    if "Official Candidate List" not in page:
        raise CertifiedError("the Colorado page is not the official candidate list")
    rows = _FL_ROW.findall(page)
    heads = [[_text(c) for c in _FL_CELL.findall(r)] for r in rows]
    if _CO_HEAD not in heads:
        raise CertifiedError("the Colorado list's columns have changed")
    races = {}
    for row, cells in zip(rows, heads):
        if len(cells) != 5 or cells == _CO_HEAD:
            continue
        name, office, district, party, write_in = cells
        if office == "US Senate":
            rid = senate("CO")
        elif office == "US House of Representatives":
            if not district.isdigit():
                raise CertifiedError(f"unreadable Colorado district {district!r}")
            rid = house("CO", district)
        else:
            continue
        if write_in not in ("Y", "N"):
            raise CertifiedError(f"unreadable write-in mark {write_in!r} for {name}")
        kind = (WITHDRAWN if "line-through" in row
                else WRITE_IN if write_in == "Y" else BALLOT)
        races.setdefault(rid, []).append(entry(_quotes(name), party, kind))
    seats = sorted(int(rid.split("-")[2]) for rid in races if rid.startswith("H-"))
    if seats != list(range(1, CO_HOUSE_SEATS + 1)) or senate("CO") not in races:
        raise CertifiedError(f"the Colorado list covers House seats {seats}")
    return races


# ---------------------------------------------------------- American Samoa

AS_URL = ("https://www.aselectionoffice.gov/candidates-information/"
          "candidates-for-the-2026-midterm-election")
AS_SOURCE = "American Samoa Election Office, Candidates for the 2026 Midterm Election"
_AS_HEAD = "DELEGATE TO THE UNITED STATES CONGRESS"
_AS_CERTIFIED = re.compile(r"certified the following candidates for the Midterm Election "
                           r"scheduled for November 3, 2026", re.I)


def _lines(page):
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S | re.I)
    page = re.sub(r"</p>|<br[^>]*>|</h\d>|</li>|</div>", "\n", page, flags=re.I)
    out = []
    for line in html.unescape(re.sub(r"<[^>]+>", "", page)).split("\n"):
        line = re.sub(r"\s+", " ", line.replace(" ", " ").replace("�", "")).strip()
        if line:
            out.append(line)
    return out


def parse_american_samoa(page):
    """``{race_id: [entry]}``: the delegate's race, from the certified list."""
    lines = _lines(page)
    if not any(_AS_CERTIFIED.search(line) for line in lines):
        raise CertifiedError("the American Samoa page does not say its list is certified")
    try:
        start = [line.upper() for line in lines].index(_AS_HEAD)
    except ValueError:
        raise CertifiedError("the American Samoa list has no delegate section") from None
    out = []
    for line in lines[start + 1:]:
        if line.upper() == line and re.search(r"[A-Z]", line):
            break                               # the next office's heading
        out.append(entry(line, "", BALLOT))
    if not out:
        raise CertifiedError("the American Samoa list names no delegate candidate")
    return {house("AS", 0): out}


# -------------------------------------------------------------------- read

READERS = (
    ("AK", AK_URL, AK_SOURCE, parse_alaska),
    ("FL", FL_URL, FL_SOURCE, parse_florida),
    ("CO", CO_URL, CO_SOURCE, parse_colorado),
    ("AS", AS_URL, AS_SOURCE, parse_american_samoa),
)


def _read(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", "replace")


def curated(today=None):
    """The lists transcribed in ``overrides.CERTIFIED_BALLOTS``, in the
    shape :func:`fetch` returns."""
    from .overrides import CERTIFIED_BALLOTS

    lists = {}
    for state, spec in sorted(CERTIFIED_BALLOTS.items()):
        races = {rid: [entry(name, party, BALLOT) for name, party in people]
                 for rid, people in spec["races"].items()}
        lists[state] = {"source": spec["source"], "url": spec["url"],
                        "fetched": spec["read"], "complete": spec["complete"],
                        "curated": True, "races": races}
    return lists


def fetch(read=_read, log=print, sleep=time.sleep, today=None):
    """``({state: list}, [states that failed])`` read from the states now,
    the curated lists included. A list is ``{source, url, fetched,
    complete, races: {race_id: [entry]}}``; a failed state is reported and
    left out, never read as nobody being certified (rule 8)."""
    today = today or datetime.date.today()
    lists, failed = {}, []
    for i, (state, url, source, parse) in enumerate(READERS):
        if i:
            sleep(GAP)
        try:
            races = parse(read(url))
        except Exception as exc:          # inconclusive: say so, conclude nothing
            log(f"    [warn] {state}'s certified list could not be read: {exc}")
            failed.append(state)
            continue
        lists[state] = {"source": source, "url": url, "fetched": today.isoformat(),
                        "complete": True, "races": races}
        printed = sum(1 for es in races.values() for e in es if e["kind"] == BALLOT)
        log(f"    {state}: {printed} printed on the ballot in {len(races)} races ({source})")
    lists.update(curated(today))
    return lists, failed


def carry(lists, failed, previous):
    """Keep the last list read for a state whose read failed this time."""
    kept = []
    for state in failed:
        old = ((previous or {}).get("certified") or {}).get(state)
        if old:
            lists[state] = dict(old, carried=True)
            kept.append(state)
    return kept
