"""Who is on Louisiana's November 3 ballot for the House, from the Secretary of State.

Louisiana's House seats are an open primary on general-election day in 2026
(``overrides.OPEN_PRIMARY_SEATS``), so until the count no results page can
say who is running, and the site showed the FEC's register in its place:
"3 filed, none past $5k" for LA-2, whose ballot holds five (audit ACC-7).
The Secretary of State's Candidate Inquiry lists everyone who qualified, by
office, and exports it as CSV; qualifying closed on August 7.

Only what the ballot says is read: the name as printed, the party, the day
they qualified, and the Outcome column, which the office uses to mark a
withdrawal ("Withdrew") and, measured on the 2024 export after its count,
for nothing else. The export also carries each candidate's address, phone,
email, race and gender; none of it is kept, here or anywhere else.

The names are matched to FEC filings by ``results`` with the same matcher
and aliases as the results pages, so a qualified candidate is a profile's
status ("qualified") or, with no filing over $5,000, a name on the race.
"""

import csv
import datetime
import http.cookiejar
import io
import re
import urllib.parse
import urllib.request

PORTAL = "https://voterportal.sos.la.gov/CandidateInquiry"
OFFICE_LIST = PORTAL + "/StatewideCandidate/OfficeList"
EXPORT = PORTAL + "/StatewideCandidate/Export"
SOURCE = "Louisiana Secretary of State, Candidate Inquiry"
USER_AGENT = "Mozilla/5.0 (compatible; know-your-candidate/1.0)"
ELECTION = "11/03/2026"
TIMEOUT = 60

# The office the export names each House seat with.
HOUSE_OFFICE = "U. S. Representative"
_ELECTION_OPTION = re.compile(r'<option[^>]*value="(\d+)"[^>]*>\s*([\d/]+)\s*</option>')
_OFFICE = re.compile(r'<input type="checkbox" id="cb_(\d+)" />(.*?)(?=<input type="checkbox"|$)', re.S)
_DISTRICT = re.compile(r"^(\d+)(?:st|nd|rd|th) Congressional District$")
_WITHDREW = re.compile(r"^withdr", re.I)
COLUMNS = ("OfficeTitle", "OfficeTitleDescription", "BallotFirstName", "BallotLastName",
           "BallotSuffix", "Party", "Filed Date", "Outcome")


class QualifiedError(RuntimeError):
    pass


def ballot_name(row):
    """The name as the ballot prints it, in the results pages' style: a
    nickname inside a name keeps its quotes (Walter "Rocky" Beach), one that
    stands in for the first name loses them ('Clay' Higgins -> Clay Higgins)."""
    parts = (row.get("BallotFirstName"), row.get("BallotLastName"), row.get("BallotSuffix"))
    name = " ".join(p.strip() for p in parts if p and p.strip())
    name = re.sub(r"^'([^']+)'(?= )", r"\1", name)
    return re.sub(r"'([^']+)'", r'"\1"', name)


def parse_export(text):
    """``{race_id: [{name, party, filed, withdrew}]}`` for the House seats.

    Every column read is checked for; a renamed one fails loudly rather than
    reading as nobody qualified. An Outcome other than a withdrawal is
    refused: the office has never used it for a result, and a word this
    reader does not know is not one it may guess at.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise QualifiedError(f"the export has no {', '.join(missing)} column")
    races = {}
    for row in reader:
        if row["OfficeTitle"].strip() != HOUSE_OFFICE:
            continue
        m = _DISTRICT.match(row["OfficeTitleDescription"].strip())
        if not m:
            raise QualifiedError(f"unreadable district {row['OfficeTitleDescription']!r}")
        outcome = row["Outcome"].strip()
        if outcome and not _WITHDREW.match(outcome):
            raise QualifiedError(f"unknown Outcome {outcome!r} for {ballot_name(row)}")
        filed = datetime.datetime.strptime(row["Filed Date"].strip(), "%m/%d/%Y").date()
        races.setdefault(f"H-LA-{int(m.group(1)):02d}-2026", []).append({
            "name": ballot_name(row),
            "party": row["Party"].strip(),
            "filed": filed.isoformat(),
            "withdrew": bool(outcome),
        })
    return races


def election_id(page, date=ELECTION):
    """The portal's id for the election held on *date* (MM/DD/YYYY)."""
    for value, text in _ELECTION_OPTION.findall(page):
        if text == date:
            return value
    raise QualifiedError(f"the portal lists no election on {date}")


def house_offices(page):
    """``[office id]`` of the House seats in the office list."""
    return [oid for oid, label in _OFFICE.findall(page)
            if re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", label)).strip()
            .startswith(HOUSE_OFFICE + ",")]


def fetch(date=ELECTION, opener=None):
    """``({race_id: [entry]}, meta)`` read from the portal now.

    Three requests, as the portal's own page makes them: the page (for its
    session cookie and the election's id), the list of offices on that
    ballot, and the CSV export for the House seats among them. The number of
    districts read must equal the number of House offices listed.
    """
    if opener is None:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    headers = {"User-Agent": USER_AGENT}

    def read(url, data=None):
        request = urllib.request.Request(url, data=data, headers=headers)
        with opener.open(request, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")

    eid = election_id(read(PORTAL), date)
    offices = house_offices(read(OFFICE_LIST + "?" + urllib.parse.urlencode({"electionId": eid})))
    if not offices:
        raise QualifiedError(f"no {HOUSE_OFFICE} offices on the {date} ballot")
    body = urllib.parse.urlencode({"officeIds": ",".join(offices), "electionId": eid,
                                   "electionDate": date}).encode()
    races = parse_export(read(EXPORT, body))
    if len(races) != len(offices):
        raise QualifiedError(f"{len(offices)} House offices listed, {len(races)} read")
    return races, {"source": SOURCE, "url": PORTAL, "election": date,
                   "fetched": datetime.date.today().isoformat()}
