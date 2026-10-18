"""Financial disclosures of the President, the Vice President and the
Cabinet, from the Office of Government Ethics.

OGE publishes the reports of the President, the Vice President and the
officers the Senate confirms: the financial report each nominee files (the
"Nominee 278"), the annual report, periodic transaction reports, the ethics
agreement and its certifications of compliance. Its index is one table
behind an API, a row per document: the filer's name as OGE files it
("Turner, Eric Scott" for Scott Turner, legal names as the FEC's are), the
agency and position as OGE writes them, the date, and the document.

A row is attributed to an office, never to a name alone (rules 17, 20):

- the office's agency and position as OGE writes them (:data:`OFFICES`,
  checked by hand against the index): the agency compared without regard
  to case, the position past OGE's number for a second record of one post
  ("Director 2");
- the holder's surname, as a cross-check on that office's rows; first
  names are never compared, because OGE files legal names. Two different
  OGE names of the holder's surname on one office are refused and
  reported, never merged (rule 25);
- the holder's other rows in the same agency under the very same OGE name
  are theirs too: Todd Blanche's 2026 annual report is filed as Deputy
  Attorney General.

Only a document OGE serves as a file is linked (``PAS+Index/<id>/$FILE/``).
A document released on request is counted and the page says so; the
request form is never linked as though it were the report. Each 278 report
OGE generates from its filing system names its filer under "Filer's
Information", and each is opened and read: a report that names someone
else is refused and reported (rule 20); one that cannot be read concludes
nothing (rule 8), and is linked and reported. A report's check is kept with
its address, which never changes, so a weekly read opens only new ones.

A holder with no row reads "OGE's index lists no report under this office",
never "not filed" (rule 19): OGE's collection is not every report, and an
acting officer files under their own post. A read that fails, or comes back
with fewer rows than it says it holds (rule 36), keeps the committed cache.
"""

import datetime
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import zlib

API_URL = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest"
INDEX_URL = "https://extapps2.oge.gov/201/Presiden.nsf/"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "oge_disclosures.json")
USER_AGENT = "KnowYourCandidate/1.0 (https://github.com/pkplaya626/Know-Your-Candidate; civic data)"
PAUSE = 0.5
PAGE = 500
# A report OGE generates is some 16 KB; a file past this is a scan, whose
# filer's name cannot be read, so it is not downloaded to find that out.
PDF_LIMIT = 2_000_000

# Each office as OGE files it: (agency, position). Read from OGE's index on
# 2026-10-16; the index writes some agencies in title case ("Department of
# The Treasury") and is compared without regard to case.
OFFICES = {
    "president": ("White House Office", "President"),
    "vicePresident": ("Office of the Vice President", "Vice President"),
    "state": ("Department of State", "Secretary"),
    "treasury": ("Department of the Treasury", "Secretary"),
    "defense": ("Department of Defense/Office of the Secretary", "Secretary"),
    "justice": ("Department of Justice", "Attorney General"),
    "interior": ("Department of the Interior", "Secretary"),
    "agriculture": ("Department of Agriculture", "Secretary"),
    "commerce": ("Department of Commerce", "Secretary"),
    "labor": ("Department of Labor", "Secretary"),
    "hhs": ("Department of Health and Human Services", "Secretary"),
    "hud": ("Department of Housing and Urban Development", "Secretary"),
    "transportation": ("Department of Transportation", "Secretary"),
    "energy": ("Department of Energy", "Secretary"),
    "education": ("Department of Education", "Secretary"),
    "veterans": ("Department of Veterans Affairs", "Secretary"),
    "homeland": ("Department of Homeland Security", "Secretary"),
    "epa": ("Environmental Protection Agency", "Administrator"),
    "omb": ("Office of Management and Budget", "Director"),
    "ustr": ("Office of the US Trade Representative", "U.S. Trade Representative"),
    "dni": ("Office of Director of National Intelligence", "Director"),
    "cia": ("Central Intelligence Agency", "Director"),
    "sba": ("Small Business Administration", "Administrator"),
    "un": ("Department of State", "U.S. Representative to United Nations w/rank of AMB & "
           "U.S. Representative in Security Council of United Nations"),
    "chief-of-staff": ("White House Office", "Assistant to the President & Chief of Staff"),
}

# What each kind of document is, in the page's words, and whether OGE
# generates it from its filing system (and so names its filer inside).
KINDS = (
    ("annual", r"^annual\b", "Annual report", True),
    ("nominee", r"^nominee 278\b", "Report on nomination", True),
    ("entrant", r"^new entrant\b", "Report on entering office", True),
    ("transaction", r"^278 transaction\b", "Periodic transaction report", True),
    ("termination", r"^termination\b", "Report on leaving office", True),
    ("ethics", r"^ethics agreement\b", "Ethics agreement", False),
    ("certification", r"^certification of ethics agreement compliance\b",
     "Certification of ethics agreement compliance", False),
    ("waiver", r"^conflict of interest waiver\b", "Conflict of interest waiver", False),
    ("divestiture", r"^certificate of divestiture\b", "Certificate of divestiture", False),
)
_FILE = re.compile(r"^https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/[0-9A-F]{32}/\$FILE/[^\s'\"<>]+$")


class OGEError(RuntimeError):
    """The index could not be read, or is not what the pipeline expects."""


def _get(url, timeout=60, raw=False):
    """JSON, or with *raw* a file's bytes - None for a file past
    :data:`PDF_LIMIT`."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(PDF_LIMIT + 1) if raw else response.read()
    except OSError as exc:
        raise OGEError(f"could not read {url.split('?')[0]}: {exc}") from exc
    if raw:
        return None if len(body) > PDF_LIMIT else body
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise OGEError(f"{url.split('?')[0]} did not answer with JSON") from exc


def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().split())


def surname(name):
    """The holder's surname: "Robert F. Kennedy, Jr." -> "kennedy"."""
    name = re.sub(r",?\s+(?:jr|sr|ii|iii|iv)\.?$", "", (name or "").strip(), flags=re.I)
    return _fold(name.split()[-1]) if name.split() else ""


def filed_surname(listed):
    """OGE's "Last, First Middle" -> "last"; a report may write "Kennedy Jr,
    Robert F", where the index writes "Kennedy, Robert F"."""
    return re.sub(r"\s+(?:jr|sr|ii|iii|iv)\.?$", "", _fold(listed.split(",")[0]))


def given(listed):
    """OGE's "Last, First Middle" -> "first"."""
    rest = listed.split(",", 1)[1] if "," in (listed or "") else ""
    words = _fold(rest).replace(".", " ").split()
    return words[0] if words else ""


def same_filer(a, b):
    """Two names OGE writes - the index's and a report's - name one filer:
    the same surname past a suffix ("Kennedy Jr, Robert F" and "Kennedy,
    Robert F") and the same first name. A Jane Smith's index row and a John
    Smith's report are two people."""
    return bool(given(a)) and filed_surname(a) == filed_surname(b) and given(a) == given(b)


def holder_named(listed, holder):
    """The index's "Last, First" is the holder's: their name, past a
    suffix, ends with its surname - every word of it, so "De La Cruz,
    Monica" is Monica De La Cruz."""
    name = _fold(re.sub(r",?\s+(?:jr|sr|ii|iii|iv)\.?$", "", (holder or "").strip(), flags=re.I))
    last = filed_surname(listed)
    return bool(last) and (name == last or name.endswith(" " + last))


def position(title):
    """OGE's position past its record number: "Director 2" -> "director"."""
    return _fold(re.sub(r"\s+\d+$", "", title or ""))


def document(row):
    """``{kind, label, date, url, request}`` for one index row."""
    cell = row.get("type") or ""
    link = re.search(r"<a\s+href='([^']+)'>([^<]*)</a>", cell)
    url = html.unescape(link.group(1)) if link else None
    if link and _FILE.match(url or ""):
        label = html.unescape(link.group(2)).strip()
        rest = html.unescape(re.sub(r"<[^>]+>", "", cell[link.end():])).strip()
        on_request = False
    else:
        # "278 Transaction (<a ...201 Request...>Request this Document</a>)".
        label = html.unescape(re.sub(r"\(?<a\b.*?</a>\)?", "", cell)).strip()
        rest, url, on_request = "", None, True
    label = " ".join((label + " " + rest).split())
    kind = next((k for k, pattern, _words, _gen in KINDS if re.search(pattern, label, re.I)), "other")
    year = re.search(r"\((\d{4})\)", label)
    # The date is the day OGE's index posted the document, not the day it
    # was signed: Linda McMahon's July 2025 report was posted in April 2026.
    return {"kind": kind, "label": label, "date": (row.get("docDate") or "")[:10],
            "url": url, "request": on_request,
            "year": int(year.group(1)) if kind == "annual" and year else None,
            "amended": bool(re.search(r"amended", label, re.I))}


def search(term, read=None):
    """Every index row the API returns for *term*; refused unless it returns
    every row it says it holds (rule 36)."""
    read = read or _get
    rows, start, total = [], 0, None
    while total is None or start < total:
        data = read(f"{API_URL}?{urllib.parse.urlencode({'start': start, 'length': PAGE, 'search[value]': term})}")
        if not isinstance(data, dict) or "data" not in data:
            raise OGEError(f"the index answered {term!r} without rows")
        total = int(data.get("recordsFiltered") or 0)
        page = data["data"]
        rows += page
        if not page:
            break
        start += len(page)
        if read is _get:
            time.sleep(PAUSE)
    if len(rows) != total:
        raise OGEError(f"the index said {total} rows for {term!r} and returned {len(rows)}")
    return rows


# --------------------------------------------------------------- the PDF

def pdf_strings(data):
    """The literal strings drawn in a PDF's content streams, in order."""
    out = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            text = zlib.decompress(match.group(1))
        except zlib.error:
            text = match.group(1)
        for string in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", text):
            out.append(re.sub(rb"\\(.)", rb"\1", string).decode("latin-1"))
    return out


def filer_named(data, listed):
    """``"named"`` when the report's Filer's Information gives the filer's
    surname, ``"other: <name>"`` when it gives someone else's, and
    ``"unreadable"`` when the report has no such section to read (a scan,
    or a file too large to be one OGE generated: *data* None)."""
    if data is None:
        return "unreadable"
    strings = [s.strip() for s in pdf_strings(data)]
    try:
        at = next(i for i, s in enumerate(strings) if s.lower().startswith("filer's information"))
    except StopIteration:
        return "unreadable"
    name = next((s for s in strings[at + 1:at + 6] if s and "," in s), None)
    if not name:
        return "unreadable"
    return "named" if same_filer(name, listed) else f"other: {name}"


_POSITIONS = "other federal government positions held during the preceding 12 months"
# Where the list ends: the next section of the report's first page.
_POSITIONS_END = re.compile(r"(?i)^(?:names of congressional committees|electronic signature|"
                            r"agency ethics official|date of|report year|.*\bpage$|\d+\.\s)")
_SPAN = re.compile(r"\S.*?\(\s*\d{1,2}/\d{4}\s*[-–]\s*(?:\d{1,2}/\d{4}|present)\s*\)", re.I)
# The reports whose first page carries the section.
POSITION_KINDS = ("annual", "nominee", "entrant", "termination")


def other_positions(data):
    """The report's "Other Federal Government Positions Held During the
    Preceding 12 Months", each entry in its own words with its dates
    ("Acting Director, Institute of Museum and Library Services (3/2025 -
    11/2025)"). None when the report has no such section or cannot be read
    (rule 8); an empty list when it lists none."""
    if data is None:
        return None
    strings = [s.strip() for s in pdf_strings(data)]
    at = next((i for i, s in enumerate(strings) if s.lower().rstrip(": ") == _POSITIONS), None)
    if at is None:
        return None
    text = []
    for s in strings[at + 1:at + 60]:
        if _POSITIONS_END.match(s):
            break
        if s:
            text.append(s)
    joined = " ".join(text)
    # Words the entries-with-dates do not account for: the list is not read
    # whole, so nothing is shown from it (rule 8) - never a partial list.
    left = _SPAN.sub(" ", joined).strip(" ,;")
    if left and left.lower() not in ("none", "n/a", "not applicable"):
        return None
    return [" ".join(m.group(0).split()) for m in _SPAN.finditer(joined)]


# ------------------------------------------------------------------ build

def attribute(rows, office, holder):
    """``(filed name, rows of the office, the holder's other rows in its
    agency, problems)`` for one holder of one office."""
    agency, title = office
    same_agency = [r for r in rows if _fold(r.get("agency")) == _fold(agency)]
    mine = [r for r in same_agency if position(r.get("title")) == position(title)
            and holder_named(r.get("name") or "", holder)]
    names = sorted({r["name"] for r in mine})
    if len(names) > 1:
        return None, [], [], [f"{holder}: OGE files {' and '.join(names)} under this office; "
                              "neither is shown (two people of one surname)"]
    if not names:
        return None, [], [], []
    filed = names[0]
    other = [r for r in same_agency if r["name"] == filed and r not in mine]
    return filed, mine, other, []


def holders(executive):
    """``[(key, name, since)]``: the President, the Vice President and each
    office's holder, as the executive cache names them."""
    out = []
    for key in ("president", "vicePresident"):
        person = executive.get(key) or {}
        if person.get("name"):
            out.append((key, person["name"]))
    for office in executive.get("offices") or []:
        if (office.get("holder") or {}).get("name"):
            out.append((office["key"], office["holder"]["name"]))
    return out


# A nominee files before the term begins: reports posted this long before
# the administration's first day are its own; older ones belong to another
# tenure - Donald Trump's report on leaving office in 2021 is not about the
# office he holds now.
TRANSITION_DAYS = 120


def build(executive, read=None, read_pdf=None, previous=None, today=None):
    """The whole cache; :class:`OGEError` when the index cannot be read."""
    read = read or _get
    read_pdf = read_pdf or (lambda url: _get(url, raw=True))
    checked = dict((previous or {}).get("checked") or {})
    # Each filer-checked report's other federal positions, by its address,
    # read once like its check (other_positions).
    positions = dict((previous or {}).get("positions") or {})
    people, problems, searched = {}, [], {}
    since = ((executive.get("president") or {}).get("termStart") or "")[:10]
    bound = ((datetime.date.fromisoformat(since) - datetime.timedelta(days=TRANSITION_DAYS))
             .isoformat() if since else "")
    for key, name in holders(executive):
        office = OFFICES.get(key)
        if office is None:
            problems.append(f"{key}: no OGE agency and position for this office")
            continue
        term = surname(name)
        if term not in searched:
            searched[term] = search(term, read)
        filed, mine, other, trouble = attribute(searched[term], office, name)
        problems += trouble
        docs = []
        for row in mine + [r for r in other if document(r)["kind"] == "annual"]:
            doc = dict(document(row), title=re.sub(r"\s+\d+$", "", row.get("title") or ""),
                       office=row in mine)
            if bound and doc["date"] < bound:
                continue
            generated = next((g for k, _p, _w, g in KINDS if k == doc["kind"]), False)
            if doc["url"] and generated:
                # A file at an address never changes: a check is kept, a
                # scan's "unreadable" too, and so is what it lists.
                wants = doc["kind"] in POSITION_KINDS and doc["url"] not in positions \
                    and checked.get(doc["url"]) in (None, "named")
                if doc["url"] not in checked or wants:
                    try:
                        data = read_pdf(doc["url"])
                        checked[doc["url"]] = filer_named(data, filed)
                        if doc["kind"] in POSITION_KINDS and checked[doc["url"]] == "named":
                            positions[doc["url"]] = other_positions(data)
                    except OGEError:
                        # Unread is not unnamed (rule 8): link it, check it next time.
                        checked.pop(doc["url"], None)
                    if read is _get:
                        time.sleep(PAUSE)
                doc["check"] = checked.get(doc["url"])
                if (doc["check"] or "").startswith("other"):
                    problems.append(f"{name}: {doc['label']} of {doc['date']} names "
                                    f"{doc['check'][7:]}, not {filed}; not linked")
                    continue
            docs.append(doc)
        docs.sort(key=lambda d: (d["date"], d["label"]), reverse=True)
        people[key] = {"holder": name, "filed": filed, "agency": office[0], "position": office[1],
                       "documents": docs, "refused": bool(trouble) or None}
    return {"read": today or datetime.date.today().isoformat(),
            "source": INDEX_URL, "people": people, "problems": problems,
            # Only the checks of documents still listed are kept.
            "checked": {u: v for u, v in sorted(checked.items())
                        if any(d["url"] == u for p in people.values() for d in p["documents"])},
            "positions": {u: v for u, v in sorted(positions.items())
                          if checked.get(u) == "named" and
                          any(d["url"] == u for p in people.values() for d in p["documents"])}}


def for_page(person, positions=None):
    """What the officials' dialog draws: the latest of each kind, linked,
    newest first; transaction reports counted with the latest linked; what
    OGE releases only on request counted."""
    if not person:
        return None
    if not person.get("filed"):
        # Read, and nothing is the holder's: never "filed as" no one.
        return {"none": True, "refused": person.get("refused") or None,
                "agency": person["agency"], "position": person["position"]}
    docs = person["documents"]
    linked = [d for d in docs if d["url"] and not (d.get("check") or "").startswith("other")]
    shown, seen = [], set()
    for doc in linked:
        if doc["kind"] in seen and doc["kind"] != "other":
            continue
        seen.add(doc["kind"])
        same = [d for d in linked if d["kind"] == doc["kind"]]
        words = next((w for k, _p, w, _g in KINDS if k == doc["kind"]), doc["label"])
        if doc["kind"] == "annual" and doc.get("year"):
            words += f", {doc['year']}"
        shown.append({k: v for k, v in {
            "kind": doc["kind"], "words": words, "date": doc["date"], "url": doc["url"],
            "count": len(same) if len(same) > 1 else None,
            # A report filed under another post in the same agency says so.
            "as": None if doc["office"] else doc["title"],
            "amended": doc["amended"] or None,
            "unchecked": doc.get("check") in (None, "unreadable") and doc["kind"] in
            {k for k, _p, _w, g in KINDS if g} or None,
        }.items() if v is not None})
    # The federal posts their latest filer-checked report lists for the
    # year before it, in its words (FEDERAL-18): quoted beside, never
    # merged into, the offices two sources agree on (rule 69).
    listed = None
    for doc in linked:
        found = (positions or {}).get(doc["url"])
        if doc.get("check") == "named" and doc["kind"] in POSITION_KINDS and found is not None:
            listed = {"rows": [re.sub(r"\s+,", ",", r) for r in found],
                      "date": doc["date"], "url": doc["url"],
                      "words": next(w for k, _p, w, _g in KINDS if k == doc["kind"])}
            break
    return {k: v for k, v in {
        "filed": person["filed"], "agency": person["agency"], "position": person["position"],
        "documents": shown,
        "onRequest": sum(1 for d in docs if d["request"]) or None,
        "otherPositions": listed,
    }.items() if v is not None}


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def check(office_keys):
    """Problems with :data:`OFFICES`: an office the federal table has and this
    one lacks, or one it names that the federal table does not."""
    out = [f"no OGE agency and position for {k}" for k in office_keys if k not in OFFICES]
    out += [f"OGE table names an office the federal table lacks: {k}" for k in OFFICES
            if k not in set(office_keys) | {"president", "vicePresident"}]
    return out


def problems(cache, executive=None, today=None):
    """What a build says about the cache: ``[(level, code, message, detail)]``."""
    from . import federal_offices

    out = []
    table = check([o["key"] for o in federal_offices.OFFICES])
    if table:
        out.append(("error", "oge-table", "the OGE office table does not match the federal one", table))
    if not cache:
        return out
    if cache.get("problems"):
        out.append(("warn", "oge-attribution",
                    f"{len(cache['problems'])} OGE filings are not shown: they could not be "
                    "attributed to the officer", cache["problems"]))
    generated = {k for k, _p, _w, g in KINDS if g}
    unread = {}
    for person in cache["people"].values():
        for doc in person["documents"]:
            if doc["url"] and doc["kind"] in generated and doc.get("check") in (None, "unreadable"):
                unread[person["holder"]] = unread.get(person["holder"], 0) + 1
    if unread:
        out.append(("warn", "oge-unchecked", f"{sum(unread.values())} OGE reports are linked "
                    "without their filer's name having been read in them (scans, or not yet read)",
                    [f"{name}: {n}" for name, n in sorted(unread.items())]))
    if executive:
        # Every holder the executive lists who was not read: a new holder of
        # a read office, or one of an office never read. The page says the
        # index was not read for them, never that it lists nothing.
        moved = [f"{key}: {name}" + (f" (the cache read {cache['people'][key]['holder']})"
                                     if key in cache["people"] else " (not read)")
                 for key, name in holders(executive) if key in OFFICES and
                 (cache["people"].get(key) or {}).get("holder") != name]
        if moved:
            out.append(("warn", "oge-stale", f"{len(moved)} officers' filings were not read for "
                        "them; their dialogs say so; run 'oge'", moved))
    today = today or datetime.date.today().isoformat()
    age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(cache["read"])).days
    if age > 21:
        out.append(("warn", "oge-old", f"OGE's index was last read {age} days ago", []))
    return out
