"""Vacancies in the federal judiciary, as the courts list them.

The Administrative Office of the U.S. Courts publishes three lists on
uscourts.gov, each a table:

- current vacancies: the court, the judge whose seat is vacant, why
  (senior status, retirement, death, elevation, resignation), since when,
  and any nominee with the nomination date. The page's own summary gives
  the totals, and a read whose rows do not add up to them is refused;
- future vacancies: judges who have announced they will leave, with the
  date where one is set;
- judicial emergencies: vacancies the courts designate as emergencies.

A row is placed on a court by the list's own court code ("05 - TX-S", "05 -
CCA"), never by a name: the code names the circuit and the court, and must
agree with :mod:`kyc.federal_courts`. A code the table does not know is kept
and reported (``unplaced``), never dropped and never guessed at. The names
are the list's, shown as it writes them turned to reading order ("Gorton,
Nathaniel M." -> "Nathaniel M. Gorton"); they are never matched to a profile
or a judge's record (rule 17).
"""

import datetime
import html
import json
import os
import re
import urllib.request

from . import federal_courts

BASE = "https://www.uscourts.gov/data-news/judicial-vacancies/"
CURRENT_URL = BASE + "current-judicial-vacancies"
FUTURE_URL = BASE + "future-judicial-vacancies"
EMERGENCIES_URL = BASE + "judicial-emergencies"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "judicial_vacancies.json")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 know-your-candidate/1.0")
STALE_DAYS = 14


class VacanciesError(RuntimeError):
    """A list could not be read, or is not what the pipeline expects."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise VacanciesError(f"could not fetch {url}: {exc}") from exc


def _cell(text):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def tables(page):
    """Every table on *page* as ``[header, rows]``, rows as dicts."""
    out = []
    for table in re.findall(r"<table.*?</table>", page, re.S | re.I):
        rows = [[_cell(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S | re.I)]
                for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I)]
        rows = [r for r in rows if r]
        if rows:
            out.append((rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]))
    return out


def _date(value, what):
    """``"05/31/2025"`` -> ``"2025-05-31"``; ``"TBD"`` or empty -> None."""
    value = (value or "").strip()
    if not value or value.upper() == "TBD":
        return None
    try:
        return datetime.datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        raise VacanciesError(f"a {what} the parser does not read: {value!r}") from None


_SUFFIX = re.compile(r"^(Jr\.?|Sr\.?|II|III|IV|V)$")


def reading_name(listed):
    """``"Gorton,Nathaniel M."`` -> ``"Nathaniel M. Gorton"``;
    ``"Long,Jr.,Robert E."`` -> ``"Robert E. Long, Jr."``."""
    parts = [p.strip() for p in (listed or "").split(",") if p.strip()]
    if len(parts) < 2:
        return " ".join(parts)
    last, rest = parts[0], parts[1:]
    suffix = rest.pop(0) if len(rest) > 1 and _SUFFIX.match(rest[0]) else None
    name = " ".join(rest + [last])
    return f"{name}, {suffix}" if suffix else name


_CODE = re.compile(r"^(\d{2}|DC|FED)\s*-\s*([A-Z]{2,3}(?:-[A-Z])?)$")


def court_of(code):
    """The court id a list's code names, or None when the table does not know
    it: ``"05 - TX-S"`` -> ``"tx-s"``; ``"05 - CCA"`` -> ``"ca5"``."""
    match = _CODE.match((code or "").strip())
    if not match:
        return None
    circuit, unit = match.groups()
    circuit = str(int(circuit)) if circuit.isdigit() else {"DC": "DC", "FED": "Federal"}[circuit]
    if unit == "CCA":
        cid = {"DC": "cadc", "Federal": "cafc"}.get(circuit, f"ca{circuit}")
    elif unit == "IT":
        cid = "cit"
    else:
        cid = unit.lower()
    court = federal_courts.COURTS.get(cid)
    if court is None or (cid != "cit" and court.get("circuit") != circuit):
        return None
    return cid


def _person(listed):
    return {"name": reading_name(listed), "listedAs": listed} if listed else None


def _table(page, first_column, name):
    for header, rows in tables(page):
        if header and header[0] == first_column:
            return header, rows
    raise VacanciesError(f"the {name} page has no table headed {first_column!r}")


_TOTALS = re.compile(r"as of (\d{2}/\d{2}/\d{4})\s*Total Vacancies:\s*(\d+)\s*"
                     r"Total Nominees Pending:\s*(\d+)")


def parse_current(page):
    """``(as of, totals, rows)``; the rows must add up to the page's totals."""
    found = _TOTALS.search(" ".join(html.unescape(page).split()))
    if not found:
        raise VacanciesError("the current vacancies page gives no 'as of' and totals")
    as_of = _date(found.group(1), "as-of date")
    totals = {"vacancies": int(found.group(2)), "nominees": int(found.group(3))}
    _header, rows = _table(page, "Court", "current vacancies")
    out = []
    for row in rows:
        out.append({
            "code": row.get("Court", ""),
            "vacatedBy": _person(row.get("Incumbent")),
            "reason": row.get("Vacancy Reason") or None,
            "since": _date(row.get("Vacancy Date"), "vacancy date"),
            "nominee": _person(row.get("Nominee")),
            "nominated": _date(row.get("Nomination Date"), "nomination date"),
        })
    nominees = sum(1 for r in out if r["nominee"])
    if len(out) != totals["vacancies"] or nominees != totals["nominees"]:
        raise VacanciesError(f"the current vacancies page says {totals['vacancies']} vacancies "
                             f"and {totals['nominees']} nominees; its table holds {len(out)} and "
                             f"{nominees}: a partial read is refused")
    return as_of, totals, out


def parse_future(page):
    _header, rows = _table(page, "Court", "future vacancies")
    return [{
        "code": row.get("Court", ""),
        "vacatedBy": _person(row.get("Incumbent")),
        "reason": row.get("Vacancy Reason") or None,
        "announced": _date(row.get("Vacancy Notification Date"), "notification date"),
        "vacancyDate": _date(row.get("Vacancy Date"), "vacancy date"),
        "nominee": _person(row.get("Nominee")),
        "nominated": _date(row.get("Nomination Date"), "nomination date"),
    } for row in rows]


def parse_emergencies(page):
    _header, rows = _table(page, "Court", "judicial emergencies")
    return [{
        "code": row.get("Court", ""),
        "vacatedBy": row.get("Vacancy Created By") or None,
        "since": _date(row.get("Vacancy Date"), "vacancy date"),
    } for row in rows]


def build(current_page, future_page, emergencies_page, today):
    """The cache, or :class:`VacanciesError`."""
    as_of, totals, current = parse_current(current_page)
    future = parse_future(future_page)
    emergencies = parse_emergencies(emergencies_page)
    unplaced = []
    for row in current + future:
        row["court"] = court_of(row["code"])
        if row["court"] is None:
            unplaced.append(row["code"])
    # An emergency is a current vacancy the courts designate one: the same
    # court, the same departing judge as listed, the same date.
    keys = {(r["code"], (r["vacatedBy"] or {}).get("listedAs"), r["since"]): r for r in current}
    unmatched = []
    for emergency in emergencies:
        row = keys.get((emergency["code"], emergency["vacatedBy"], emergency["since"]))
        if row is None:
            unmatched.append(f"{emergency['code']}: {emergency['vacatedBy']} ({emergency['since']})")
        else:
            row["emergency"] = True
    return {
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "asOf": as_of,
        "read": today,
        "sources": {"current": CURRENT_URL, "future": FUTURE_URL, "emergencies": EMERGENCIES_URL},
        "totals": totals,
        "current": current,
        "future": future,
        "unplaced": sorted(set(unplaced)),
        "emergenciesUnmatched": unmatched,
    }


def fetch(today=None, read=None):
    read = read or _get
    today = today or datetime.date.today().isoformat()
    return build(read(CURRENT_URL), read(FUTURE_URL), read(EMERGENCIES_URL), today)


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


# Generational suffixes: the courts' list writes them into the surname
# ("Osteen Jr.,William L."), the directory after the given names.
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def _surname(text):
    """A surname folded for comparison: no accents, case, punctuation or
    generational suffix. ``"Osteen Jr.,William L."`` -> ``"osteen"``."""
    import unicodedata
    plain = unicodedata.normalize("NFKD", (text or "").split(",")[0])
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    words = re.sub(r"[^a-z' -]", " ", plain).replace("-", " ").split()
    return " ".join(w for w in words if w not in _SUFFIXES)


def seats_held(row, judges):
    """The directory's seats on a vacancy's court held by a judge of the
    surname the courts' list gives, or None when the row names no judge or
    no court. A name is used here only to report a disagreement between
    the two sources, never to join a record to anything (rule 17)."""
    if not row.get("court") or not row.get("vacatedBy"):
        return None
    surname = _surname(row["vacatedBy"].get("listedAs") or "")
    if not surname:
        return None
    return [seat for judge in judges.values() if _surname(judge.get("sortName")) == surname
            for seat in judge.get("seats") or [] if seat.get("court") == row["court"]]


def judge_unlisted(row, judges, future=False):
    """True when the courts' list implies the judge still serves - a seat
    left for senior status, or a vacancy only announced - and the directory
    lists nobody of that surname on that court at all. Nothing is inferred
    about why (rule 19): the page says only that the directory does not
    list them."""
    if not future and row.get("reason") != "Senior":
        return False
    seats = seats_held(row, judges)
    return seats is not None and not seats


def listed_senior(cache, judges):
    """``{(court, judge id): row}``: the judges the courts' list has on
    senior status by its own as-of date, whom the directory still lists in
    active service on that court. Neither source is chosen silently: the
    pages keep the judge out of the active count and say on their row which
    source says what. A name only points at the row to annotate - exactly
    one judge of that surname on that court, active there - and never
    joins anything else (rule 17)."""
    out = {}
    for row in (cache or {}).get("current") or []:
        if row.get("reason") != "Senior" or not row.get("since") or not row.get("court") \
                or not row.get("vacatedBy") or row["since"] > (cache.get("asOf") or ""):
            continue
        jid = judge_of(row, judges)
        if jid is None:
            continue
        seat = next(s for s in judges[jid]["seats"] if s.get("court") == row["court"])
        if not seat.get("seniorSince"):
            out[(row["court"], jid)] = row
    return out


def judge_of(row, judges):
    """The one judge on the row's court with the surname *and* first given
    name the list writes for the judge leaving, or None. A surname alone
    would point at a colleague of that name when the judge who left is
    missing from the directory (rule 17), so both must agree, and only
    one judge may fit."""
    listed = (row.get("vacatedBy") or {}).get("listedAs") or ""
    surname, given = _surname(listed), _given(listed)
    if not surname or not given or not row.get("court"):
        return None
    named = [jid for jid, judge in judges.items()
             if _surname(judge.get("sortName")) == surname and _given(judge.get("sortName")) == given
             and any(s.get("court") == row["court"] for s in judge.get("seats") or [])]
    return named[0] if len(named) == 1 else None


def _given(listed):
    """The first given name a list writes: ``"Rudofsky,Lee Philip"`` ->
    ``"lee"``."""
    parts = [p.strip() for p in (listed or "").split(",") if p.strip()]
    rest = [p for p in parts[1:] if not _SUFFIX.match(p)]
    words = rest[0].split() if rest else []
    return _surname(words[0]) if words else ""


def pending_elevations(cache, judges):
    """``{judge id: {"court", "nominated"}}``: sitting judges the announced
    list has leaving for another court ("Elevated"), with the court and the
    day of the nomination the lists give, for the judge's own record. The
    judge is found by :func:`judge_of`, the other court by
    :func:`nomination_of`."""
    out = {}
    for row in (cache or {}).get("future") or []:
        other = nomination_of(row, cache)
        jid = judge_of(row, judges) if other else None
        if jid:
            out[jid] = {"court": other["court"], "nominated": other.get("nominated")}
    return out


def nominated_to(row, cache):
    """The court of :func:`nomination_of`, or None."""
    other = nomination_of(row, cache)
    return other["court"] if other else None


def nomination_of(row, cache):
    """The nomination of a judge leaving for another court ("Elevated"),
    from the same lists: the one row, current or announced, on another
    court, whose nominee has the judge's surname and first given name. None
    when no row, or more than one, names them - the page then says only
    that the judge was nominated to another court."""
    if row.get("reason") != "Elevated" or not row.get("vacatedBy"):
        return None
    listed = row["vacatedBy"].get("listedAs") or ""
    key = (_surname(listed), _given(listed))
    found = [other for other in (cache.get("current") or []) + (cache.get("future") or [])
             if other.get("nominee") and other.get("court") and other["court"] != row.get("court")
             and (_surname(other["nominee"].get("listedAs")),
                  _given(other["nominee"].get("listedAs"))) == key]
    return found[0] if len(found) == 1 else None


def problems(cache, today=None, judiciary=None):
    """What a build says about the cache: ``[(level, code, message, detail)]``.

    With the judiciary cache, a check of the two sources against each other:
    a vacancy for senior status should leave a judge of that surname on
    senior status on that court in the FJC's directory. A name is used only
    to report a disagreement, never to join anything (rule 17)."""
    if cache is None:
        return []
    out = []
    if cache.get("unplaced"):
        out.append(("warn", "vacancy-court-unknown",
                    f"{len(cache['unplaced'])} vacancy court codes name no court in "
                    f"kyc/federal_courts.py; their vacancies are not shown on a court page",
                    cache["unplaced"]))
    if cache.get("emergenciesUnmatched"):
        out.append(("warn", "emergency-unmatched",
                    f"{len(cache['emergenciesUnmatched'])} judicial emergencies match no current "
                    f"vacancy", cache["emergenciesUnmatched"]))
    today = today or datetime.date.today().isoformat()
    if cache.get("read"):
        age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(cache["read"])).days
        if age > STALE_DAYS:
            out.append(("warn", "vacancies-stale", f"the vacancy lists were read {age} days ago; "
                        f"run 'vacancies'", []))
    if judiciary:
        judges = judiciary.get("judges") or {}
        disagree, absent = [], []
        for row in cache.get("current") or []:
            if row.get("reason") != "Senior":
                continue
            seats = seats_held(row, judges)
            if seats is None:
                continue
            if not seats:
                absent.append(f"{row['code']}: {row['vacatedBy']['name']}")
            elif not any(s.get("seniorSince") for s in seats):
                disagree.append(f"{row['code']}: {row['vacatedBy']['name']}")
        for row in cache.get("future") or []:
            if judge_unlisted(row, judges, future=True):
                absent.append(f"{row['code']}: {row['vacatedBy']['name']} (announced)")
        if disagree:
            out.append(("warn", "vacancy-judge-not-senior",
                        f"{len(disagree)} vacancies for senior status name a judge the FJC's "
                        f"directory does not list as senior on that court", disagree))
        if absent:
            out.append(("warn", "vacancy-judge-not-listed",
                        f"{len(absent)} vacancies name a judge the FJC's directory does not list "
                        f"on that court at all, though the courts' list implies they still serve; "
                        f"the court page says so beside the row. Check each judge's FJC page",
                        absent))
    return out
