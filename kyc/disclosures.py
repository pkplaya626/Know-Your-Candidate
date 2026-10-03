"""Official financial disclosures, from the Clerk of the House.

The site shows an "Estimated Net Worth" for 144 of 539 sitting members and
nothing for the rest, and the figures it does show carry no source at all. A
number about a named person's private wealth, with no filing behind it, is the
weakest thing on the page.

No free service publishes a computed net worth for members of Congress, and
inventing one from a disclosure is not a small step: the forms report assets in
broad value *bands*, so any single figure derived from them is an estimate
dressed as a fact. **This module therefore does not fill in net worth.** It
attaches the primary document instead, so a reader can see what was actually
filed.

    python build_profile_site.py disclosures          # refresh
    python build_profile_site.py disclosures --check  # report from the cache

The Clerk publishes one ZIP per year containing an XML index of every filing,
which is clean, complete and free. The Senate's equivalent sits behind a
session-based search that has to be agreed to before it returns anything;
scraping it would be fragile and against the spirit of that gate, so senators
have no disclosure link and the README says so.
"""

import http.cookiejar
import io
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "disclosures.json")

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP"
PDF_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}/{doc}.pdf"

_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 60

# The annual report is the filing that covers a member's whole financial
# position. "O" is the original and "A" an amendment to it; everything else in
# the index is a periodic transaction report, an extension request, a
# withdrawal or a candidate filing, none of which is what a reader following a
# link from "net worth" is looking for.
ANNUAL_TYPES = ("O", "A")


class DisclosureError(RuntimeError):
    pass


def fetch_year(year):
    """Every filing the Clerk indexed for *year*."""
    url = INDEX_URL.format(year=year)
    try:
        request = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            blob = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise DisclosureError(f"Could not download {url}: {exc}") from exc

    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
        name = next(n for n in archive.namelist() if n.lower().endswith(".xml"))
        # The Clerk's XML carries a byte-order mark.
        root = ET.fromstring(archive.read(name).decode("utf-8-sig"))
    except (zipfile.BadZipFile, StopIteration, ET.ParseError, UnicodeDecodeError) as exc:
        raise DisclosureError(f"{url} is not the expected ZIP of XML: {exc}") from exc

    return [
        {
            "last": (row.findtext("Last") or "").strip(),
            "first": (row.findtext("First") or "").strip(),
            "seat": (row.findtext("StateDst") or "").strip().upper(),
            "type": (row.findtext("FilingType") or "").strip(),
            "year": (row.findtext("Year") or "").strip(),
            "filed": (row.findtext("FilingDate") or "").strip(),
            "doc": (row.findtext("DocID") or "").strip(),
        }
        for row in root
    ]


def _filed_key(filing):
    """Sort key putting the most recently filed report last."""
    parts = filing["filed"].split("/")
    if len(parts) == 3:
        month, day, year = parts
        return (year.zfill(4), month.zfill(2), day.zfill(2))
    return ("", "", "")


def seat_code(profile):
    """``"AL04"`` - the Clerk's state+district form, or ``None``."""
    if profile.get("chamber") != "House":
        return None
    district = profile.get("districtNum")
    return f"{profile['state']}{0 if district is None else district:02d}"


def match(profiles, filings):
    """``{bioguide: disclosure}`` for members with an annual report on file.

    Matched on surname *and* seat *and* first initial. Surname and seat alone
    would be enough almost always, which is exactly the sort of "almost" that
    puts one person's finances under another person's name - a district can
    hold a sitting member and a same-surname candidate in the same year.
    """
    index = {}
    for filing in filings:
        if filing["type"] not in ANNUAL_TYPES or not filing["doc"]:
            continue
        key = (filing["last"].lower(), filing["seat"],
               filing["first"][:1].lower())
        index.setdefault(key, []).append(filing)

    found = {}
    for profile in profiles:
        seat = seat_code(profile)
        if not seat or profile.get("isCandidate"):
            continue
        words = profile["name"].split()
        if not words:
            continue
        key = (words[-1].lower(), seat, words[0][:1].lower())
        candidates = index.get(key)
        if not candidates:
            continue
        latest = sorted(candidates, key=_filed_key)[-1]
        found[profile["id"]] = {
            "name": profile["name"],
            "year": latest["year"],
            "filed": latest["filed"],
            "doc": latest["doc"],
            "url": PDF_URL.format(year=latest["year"], doc=latest["doc"]),
        }
    return found


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
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return {}


def apply_cache(profiles, cache):
    """Attach the disclosure link to each member who has one."""
    applied = 0
    for profile in profiles:
        record = cache.get(profile["id"])
        if not record or not record.get("url"):
            continue
        profile["disclosureUrl"] = record["url"]
        profile["disclosureYear"] = record.get("year")
        profile["disclosureFiled"] = record.get("filed")
        profile["disclosureSource"] = record.get("source") or HOUSE_SOURCE
        applied += 1
    return applied


# --------------------------------------------------------------------- Senate
#
# Senators file with the Secretary of the Senate, whose search (eFD) asks a
# visitor to accept its terms - the reports may not be used commercially or
# to solicit money - before it answers. A civic directory linking the filings
# is within those terms, so the pipeline accepts them once per run, as a
# reader would, and asks for each sitting senator's annual reports by state
# and surname. The match is then checked like an FEC figure (rule 20): the
# filer must be a senator for that state whose name fits the member, and
# anything that fits two people is left alone.

EFD_ROOT = "https://efdsearch.senate.gov"
EFD_HOME = EFD_ROOT + "/search/home/"
EFD_DATA = EFD_ROOT + "/search/report/data/"
SENATE_SOURCE = "senate-efd"
HOUSE_SOURCE = "house-clerk"

_CSRF_FORM = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
_HREF = re.compile(r'href="([^"]+)"')
_TAGS = re.compile(r"<[^>]+>")
_CY = re.compile(r"\bCY\s*(\d{4})\b")


def _fold(text):
    normal = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower().strip()


def senate_session(pause=1.0):
    """``(opener, csrf)`` after accepting the eFD terms once."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(urllib.request.Request(EFD_HOME, headers=_UA), timeout=_TIMEOUT) as r:
            page = r.read().decode("utf-8", "replace")
        token = _CSRF_FORM.search(page)
        if not token:
            raise DisclosureError("the Senate eFD home page carried no terms form")
        time.sleep(pause)
        body = urllib.parse.urlencode({"prohibition_agreement": "1",
                                       "csrfmiddlewaretoken": token.group(1)}).encode()
        agree = urllib.request.Request(EFD_HOME, data=body,
                                       headers=dict(_UA, Referer=EFD_HOME))
        with opener.open(agree, timeout=_TIMEOUT) as r:
            r.read()
    except urllib.error.URLError as exc:
        raise DisclosureError(f"Senate eFD unreachable: {exc}") from exc
    csrf = next((c.value for c in jar if c.name == "csrftoken"), "")
    if not csrf:
        raise DisclosureError("the Senate eFD did not open a session")
    return opener, csrf


def senate_rows(opener, csrf, state, surname, since="01/01/2025 00:00:00"):
    """Raw eFD result rows for a senator's annual reports (report type 7)."""
    body = urllib.parse.urlencode({
        "start": "0", "length": "25", "report_types": "[7]", "filer_types": "[1]",
        "submitted_start_date": since, "submitted_end_date": "", "candidate_state": "",
        "senator_state": state, "office_id": "", "first_name": "", "last_name": surname,
    }).encode()
    req = urllib.request.Request(EFD_DATA, data=body, headers=dict(
        _UA, Referer=EFD_ROOT + "/search/", **{"X-CSRFToken": csrf,
                                                "X-Requested-With": "XMLHttpRequest"}))
    try:
        with opener.open(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8")).get("data") or []
    except (urllib.error.URLError, ValueError) as exc:
        raise DisclosureError(f"Senate eFD search failed for {surname} ({state}): {exc}") from exc


def parse_senate_rows(rows):
    """``[{first, last, filer, title, year, url, filed, amendment}]`` from eFD rows.

    An electronic report names its year ("Annual Report for CY 2025"). A paper
    one - scanned, filed by Richard Durbin and Richard Blumenthal - says only
    "Annual Report", and its year is the one before it was filed: the report
    covers the previous calendar year, due in May with extensions to August.
    Skipping those left both senators with no link at all.
    """
    out = []
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        first, last, filer, title_html, filed = (str(c or "") for c in row[:5])
        link = _HREF.search(title_html)
        title = _TAGS.sub("", title_html).strip()
        year = _CY.search(title)
        if year:
            year = year.group(1)
        elif link and "/paper/" in link.group(1) and title.lower().startswith("annual report"):
            filed_year = re.search(r"(\d{4})\s*$", filed.strip())
            year = str(int(filed_year.group(1)) - 1) if filed_year else None
        if not link or not year:
            continue
        out.append({"first": _TAGS.sub("", first).strip(), "last": _TAGS.sub("", last).strip(),
                    "filer": _TAGS.sub("", filer).strip(), "title": title,
                    "year": year, "filed": filed.strip(),
                    "amendment": "amendment" in title.lower(),
                    "url": urllib.parse.urljoin(EFD_ROOT, link.group(1))})
    return out


def _filed_sort(report):
    """Latest year first; within it the original report over an amendment."""
    month, day, year = (report["filed"].split("/") + ["0", "0", "0"])[:3]
    return (report["year"], not report.get("amendment"), year.zfill(4), month.zfill(2),
            day.zfill(2))


def _is_senator(filer):
    """eFD's label for a senator filing: "Cruz, Ted (Senator)", or on a paper
    report just "Senator"."""
    label = _fold(filer).strip()
    return "(senator)" in label or label == "senator"


def _legal_name(report):
    first = _fold(report["first"]).replace(".", " ").split()
    return f"{first[0] if first else ''} {_fold(report['last']).strip()}"


def _filers(reports):
    """The distinct people who filed *reports*.

    An electronic report's label names its filer ("Smith, Mike R. (Senator)"),
    and two labels are two people. A paper report says only "Senator"; it
    belongs to the one labelled filer with the same legal name, or stands for
    a filer of its own when there is none - or more than one.
    """
    labelled = {}
    for report in reports:
        label = _fold(report["filer"]).strip()
        if "(" in label:
            labelled.setdefault(_legal_name(report), set()).add(label)
    people = set()
    for report in reports:
        label = _fold(report["filer"]).strip()
        if "(" in label:
            people.add(label)
            continue
        owners = labelled.get(_legal_name(report), set())
        people.add(next(iter(owners)) if len(owners) == 1 else "paper: " + _legal_name(report))
    return people


_SUFFIXES = ("jr", "sr", "ii", "iii", "iv")


def _given_names(report):
    """Every first name eFD gives for a filer: the legal one and the filer label's."""
    names = set(_fold(report["first"]).replace(".", " ").split())
    filer = _fold(report["filer"])
    if "," in filer:
        names |= set(filer.split(",", 1)[1].split("(")[0].replace(".", " ").split())
    return {n for n in names if len(n) > 1 and n not in _SUFFIXES}


# Standard English short forms. Only ever used to confirm a filer the query
# has already pinned to one state, one surname and a senator - never to find
# a person: "Jim" Banks files as "Banks, James E.".
NICKNAMES = {
    "jim": "james", "jimmy": "james", "bill": "william", "billy": "william",
    "bob": "robert", "bobby": "robert", "dick": "richard", "rick": "richard",
    "chuck": "charles", "jack": "john", "ted": "edward", "tom": "thomas",
    "tommy": "thomas", "liz": "elizabeth", "beth": "elizabeth", "peggy": "margaret",
    "kathy": "katherine", "katie": "katherine", "joe": "joseph", "ben": "benjamin",
}


def _name_fits(a, b):
    if a == b or NICKNAMES.get(a) == b or NICKNAMES.get(b) == a:
        return True
    return min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a))


def pick_senate(profile, reports):
    """The member's latest annual report, or ``None`` when it is not certain.

    The filer must be a senator (eFD's own "(Senator)" label), carry the
    member's surname, and have a first name the member also goes by - the
    roster's legal name, or an alias from the bioguide-keyed record. Two
    different people fitting is ambiguity, never a choice.
    """
    words = _fold(profile.get("rosterName") or profile["name"]).replace(".", "").split()
    if not words:
        return None
    surname = words[-1] if words[-1] not in ("jr", "sr", "ii", "iii", "iv") else words[-2]
    given = {words[0]}
    for alias in profile.get("aliases") or []:
        parts = _fold(alias).replace(".", "").split()
        if parts:
            given.add(parts[0])
    fits = []
    for report in reports:
        if not _is_senator(report["filer"]) or surname not in _fold(report["last"]):
            continue
        # eFD carries the legal name ("Rafael E") and the name the filer goes
        # by ("Cruz, Ted"); a nickname may also be a prefix ("Mitch" of "A.
        # Mitchell", "Jeff" of "Jeffrey").
        if not any(_name_fits(g, f) for g in given for f in _given_names(report)):
            continue
        fits.append(report)
    people = _filers(fits)
    if len(people) != 1:
        return None
    best = max(fits, key=_filed_sort)
    return {"url": best["url"], "year": best["year"], "filed": best["filed"],
            "name": profile["name"], "title": best["title"], "source": SENATE_SOURCE}


def match_senate(profiles, log=print, pause=1.0):
    """``{bioguide: record}`` for every sitting senator with an annual report."""
    senators = [p for p in profiles if not p.get("isCandidate") and p.get("chamber") == "Senate"]
    opener, csrf = senate_session(pause)
    found, unclear = {}, []
    for profile in senators:
        words = _fold(profile.get("rosterName") or profile["name"]).replace(".", "").split()
        surname = words[-1] if words[-1] not in ("jr", "sr", "ii", "iii", "iv") else words[-2]
        time.sleep(pause)
        reports = parse_senate_rows(senate_rows(opener, csrf, profile["state"], surname))
        if not reports:
            # Tammy Duckworth's reports carry no state, so a search filtered on
            # Illinois finds nothing. The name checks below still apply.
            time.sleep(pause)
            reports = parse_senate_rows(senate_rows(opener, csrf, "", surname))
        record = pick_senate(profile, reports)
        if record:
            found[profile["id"]] = record
        elif reports:
            unclear.append(f"{profile['name']} ({profile['state']})")
    if unclear:
        log(f"  [warn] left alone, the filer did not certainly match: {', '.join(unclear)}")
    return found
