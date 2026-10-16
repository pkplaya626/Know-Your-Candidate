"""The federal judiciary: every sitting Article III judge, and the Supreme
Court's members as the Court lists them.

``python build_profile_site.py judiciary`` reads:

- the Federal Judicial Center's Biographical Directory of Article III
  Federal Judges, exported nightly (28 U.S.C. 620 makes the FJC the
  judiciary's own research agency): every judge's service on every court,
  and their biography - birth, education, the FJC's own account of their
  career;
- the Supreme Court's own list of its justices (supremecourt.gov), which
  decides who is a member (rule 57). The directory's open Supreme Court
  rows also hold retired justices, who have taken senior status under 28
  U.S.C. 371 and are not members of the Court: read naively it seats
  eleven.

A judge is **sitting** on a court when their service there has a
commission and no termination; **senior** from the day senior status
began, and not before; the court's **chief** when their service as chief
judge has begun and not ended. A confirmed nominee with no commission yet
is not sitting.

Judges have no party. The directory's "Party of Appointing President"
columns describe the president, not the judge; they, and its gender and
race columns, are dropped when the file is read, so nothing later can show
them. A judge is "appointed by" a president, by name.

The result is ``data/judiciary.json``: sitting judges only, by the FJC's
own id (``nid``), which also builds the link to the judge's FJC page.
"""

import csv
import datetime
import html
import io
import json
import os
import re
import urllib.request

from . import federal_courts

SERVICE_URL = "https://www.fjc.gov/sites/default/files/history/federal-judicial-service.csv"
JUDGES_URL = "https://www.fjc.gov/sites/default/files/history/judges.csv"
EXPORT_PAGE = ("https://www.fjc.gov/history/judges/"
               "biographical-directory-article-iii-federal-judges-export")
JUDGE_PAGE = "https://www.fjc.gov/node/{nid}"
SCOTUS_URL = "https://www.supremecourt.gov/about/members_text.aspx"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "judiciary.json")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 know-your-candidate/1.0")
# A read listing fewer sitting judges than this share of the last one is a
# truncated file, not a wave of retirements: refused, and the last kept.
SHRINK = 0.9

# Columns never read. Party describes the appointing president; gender and
# race are not facts about the office. Dropped at parse time.
DROPPED = ("Party of Appointing President", "Party of Reappointing President", "Gender",
           "Race or Ethnicity")


class JudiciaryError(RuntimeError):
    """A source could not be read, or is not what the pipeline expects."""


def _get(url, timeout=120):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise JudiciaryError(f"could not fetch {url}: {exc}") from exc


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date(value, what):
    """A directory date, validated (rule 11): the export's documentation says
    mm/dd/yyyy and every date in it is yyyy-mm-dd."""
    value = (value or "").strip()
    if not value:
        return None
    if not _DATE.match(value):
        raise JudiciaryError(f"a {what} the parser does not read: {value!r}")
    return value


def _rows(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    for row in rows:
        for column in DROPPED:
            row.pop(column, None)
    return rows


# ---------------------------------------------------------------- the people

def read_judges(text):
    """``{nid: biography}`` from the directory's flat judges file."""
    out = {}
    for row in _rows(text):
        nid = row["nid"].strip()
        first, middle = row["First Name"].strip(), row["Middle Name"].strip()
        last, suffix = row["Last Name"].strip(), row["Suffix"].strip()
        name = " ".join(p for p in (first, middle, last) if p)
        education = []
        for n in range(1, 6):
            school = row.get(f"School ({n})", "").strip()
            if school:
                education.append({"school": school,
                                  "degree": row.get(f"Degree ({n})", "").strip() or None,
                                  "year": row.get(f"Degree Year ({n})", "").strip() or None})
        born = {k: row[f"Birth {k.title()}"].strip() for k in ("year", "city", "state")
                if row.get(f"Birth {k.title()}", "").strip()}
        out[nid] = {
            "name": f"{name}, {suffix}" if suffix else name,
            "sortName": f"{last}, {first}",
            "first": first, "last": last,
            "born": born or None,
            "education": education,
            "career": " ".join(row.get("Professional Career", "").split()) or None,
            "otherNominations": " ".join(row.get("Other Nominations/Recess Appointments", "")
                                        .split()) or None,
            "died": row.get("Death Year", "").strip() or None,
        }
    return out


def read_service(text):
    return _rows(text)


def _vote(row):
    kind = row.get("Senate Vote Type", "").strip()
    tally = row.get("Ayes/Nays", "").strip()
    if kind == "Roll Call" and re.fullmatch(r"\d+/\d+", tally):
        return tally
    return "voice vote" if kind == "Voice" else None


def _chief(row, today):
    for begin, end in (("Service as Chief Judge, Begin", "Service as Chief Judge, End"),
                       ("2nd Service as Chief Judge, Begin", "2nd Service as Chief Judge, End")):
        start, stop = row.get(begin, "").strip(), row.get(end, "").strip()
        if start and not stop and start <= today[:4]:
            return start
    return None


def sitting(rows, bios, today):
    """``(judges, courts, problems)`` from the service rows: every sitting
    judge by id, every court's counts, and what the read could not place.

    A court name the table does not know is returned as a problem for the
    caller to refuse on: a new or renamed court read as nothing would drop
    its judges with nothing said."""
    names = federal_courts.by_fjc_name()
    judges, unknown, pending, conflicts = {}, set(), [], []
    for row in rows:
        if _date(row.get("Termination Date"), "termination date"):
            continue
        commissioned = _date(row.get("Commission Date"), "commission date")
        name = row["Court Name"].strip()
        if not commissioned:
            if _date(row.get("Confirmation Date"), "confirmation date"):
                pending.append(f"{row['Judge Name']}: confirmed for {name}, not yet commissioned")
            continue
        if commissioned > today:
            continue
        court = names.get(name)
        if court is None:
            unknown.add(name)
            continue
        nid = row["nid"].strip()
        senior = _date(row.get("Senior Status Date"), "senior status date")
        seat = {
            "court": court,
            "title": row.get("Appointment Title", "").strip() or None,
            "appointedBy": row.get("Appointing President", "").strip() or None,
            "nominated": _date(row.get("Nomination Date"), "nomination date"),
            "confirmed": _date(row.get("Confirmation Date"), "confirmation date"),
            "vote": _vote(row),
            "commissioned": commissioned,
            "seniorSince": senior if senior and senior <= today else None,
            "chiefSince": _chief(row, today),
            "seat": row.get("Seat ID", "").strip() or None,
        }
        if seat["chiefSince"] and seat["seniorSince"]:
            # A chief judge must be in regular active service (28 U.S.C.
            # 136(a)): a record that has both cannot say who is chief, and
            # nobody is shown as chief until it is settled.
            conflicts.append(f"{row['Judge Name']}: chief judge of {name} since "
                             f"{seat['chiefSince']} and on senior status since {seat['seniorSince']}")
            seat["chiefSince"] = None
            seat["chiefUnsettled"] = True
        if row.get("Appointing President", "").strip().startswith("None ("):
            # A reassignment by statute (the Fifth Circuit's division in
            # 1981): the appointment is the earlier seat's, filled in below.
            seat["appointedBy"] = None
            seat["reassigned"] = commissioned
        bio = bios.get(nid) or {}
        judge = judges.setdefault(nid, {
            "id": f"fjc-{nid}", "nid": nid,
            "name": bio.get("name") or row["Judge Name"],
            "sortName": bio.get("sortName") or row["Judge Name"],
            "born": bio.get("born"), "education": bio.get("education") or [],
            "career": bio.get("career"), "otherNominations": bio.get("otherNominations"),
            "fjc": JUDGE_PAGE.format(nid=nid), "seats": [],
        })
        judge["seats"].append(seat)
    prior, ended_rows = {}, {}
    for row in rows:
        ended = _date(row.get("Termination Date"), "termination date")
        nid = row["nid"].strip()
        if ended and nid in judges:
            ended_rows.setdefault(nid, []).append(row)
            prior.setdefault(nid, []).append({
                "court": row["Court Name"].strip(),
                "title": row.get("Appointment Title", "").strip() or None,
                "from": _date(row.get("Commission Date"), "commission date"),
                "to": ended, "how": row.get("Termination", "").strip() or None})
    for nid, judge in judges.items():
        for seat in judge["seats"]:
            if seat.get("reassigned"):
                origin = _appointment(ended_rows.get(nid, []), seat["reassigned"])
                if origin:
                    seat.update(origin)
                else:
                    conflicts.append(f"{judge['name']}: reassigned to {seat['court']} with no "
                                     f"earlier appointment in the directory")
        judge["prior"] = sorted(prior.get(nid, []), key=lambda p: p["from"] or "")
        judge["seats"].sort(key=lambda s: s["commissioned"])
        judge["status"] = "senior" if all(s["seniorSince"] for s in judge["seats"]) else "active"
    problems = [f"a court the table does not know: {name}" for name in sorted(unknown)]
    return judges, pending, problems, sorted(conflicts)


def _appointment(rows, reassigned):
    """The appointment a statutory reassignment carried over: the judge's
    seat that ended by reassignment on that day, followed back through any
    earlier reassignment to the row that names the President."""
    for _ in range(len(rows)):
        row = next((r for r in rows
                    if _date(r.get("Termination Date"), "termination date") == reassigned
                    and r.get("Termination", "").strip() == "Reassignment"), None)
        if row is None:
            return None
        president = row.get("Appointing President", "").strip()
        commissioned = _date(row.get("Commission Date"), "commission date")
        if president and not president.startswith("None ("):
            return {"appointedBy": president,
                    "nominated": _date(row.get("Nomination Date"), "nomination date"),
                    "confirmed": _date(row.get("Confirmation Date"), "confirmation date"),
                    "vote": _vote(row), "commissioned": commissioned}
        reassigned = commissioned
    return None


# ------------------------------------------------------- the Supreme Court

_TABLES = re.compile(r">\s*(Chief Justices|Associate Justices)\s*<.*?<table[^>]*>(.*?)</table>", re.S)
_LONG_DATE = "%B %d, %Y"


def _long_date(text):
    text = " ".join(html.unescape(text).replace("\xa0", " ").split())
    if not text:
        return None
    try:
        return datetime.datetime.strptime(text, _LONG_DATE).date().isoformat()
    except ValueError as exc:
        raise JudiciaryError(f"a date on the Court's page the parser does not read: {text!r}") from exc


def parse_justices(page):
    """``[{name, role, state, appointedBy, oath}]`` for the sitting justices:
    the Court's own table rows with no end of service."""
    out = []
    tables = _TABLES.findall(page)
    if {t for t, _ in tables} != {"Chief Justices", "Associate Justices"}:
        raise JudiciaryError("the Court's members page no longer has its two tables")
    for heading, body in tables:
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).replace("\xa0", " ").split())
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(cells) != 5:
                continue
            name, state, appointed, oath, ended = cells
            if ended:
                continue
            out.append({"name": name, "role": heading[:-1], "state": state,
                        "appointedBy": appointed, "oath": _long_date(oath)})
    return out


def _fold(text):
    from .officers import _fold as fold
    return fold(text).strip()


def join_justices(justices, judges, bios):
    """``(members, retired, problems)``: the Court's justices joined to the
    directory's sitting Supreme Court service by surname and first name, each
    join unique, within that court's rows only. The directory's other open
    Supreme Court rows are retired justices."""
    on_court = {nid: j for nid, j in judges.items()
                if any(s["court"] == "scotus" for s in j["seats"])}
    members, problems = [], []
    for justice in justices:
        last, _, rest = justice["name"].partition(",")
        first = rest.strip().split()[0] if rest.strip() else ""
        hits = [nid for nid in on_court
                if _fold(bios.get(nid, {}).get("last", "")) == _fold(last)
                and _fold(bios.get(nid, {}).get("first", "")) == _fold(first)]
        if len(hits) != 1:
            problems.append(f"the Court lists {justice['name']}; the directory's sitting "
                            f"Supreme Court rows match {len(hits)}")
            continue
        members.append((justice, hits[0]))
    joined = {nid for _j, nid in members}
    retired = sorted(nid for nid in on_court if nid not in joined)
    return members, retired, problems


# ------------------------------------------------------------------ fetch

def build(service_text, judges_text, scotus_page, today):
    """The cache, or :class:`JudiciaryError` when a source is not what the
    pipeline knows."""
    bios = read_judges(judges_text)
    judges, pending, problems, conflicts = sitting(read_service(service_text), bios, today)
    if problems:
        raise JudiciaryError("; ".join(problems))
    members, retired, joins = join_justices(parse_justices(scotus_page), judges, bios)
    if joins or len(members) != federal_courts.SUPREME_COURT_SEATS:
        raise JudiciaryError("; ".join(joins) or f"the Court lists {len(members)} justices, "
                             f"not the {federal_courts.SUPREME_COURT_SEATS} of 28 U.S.C. 1")
    for justice, nid in members:
        judges[nid]["justice"] = {"role": justice["role"], "oath": justice["oath"],
                                  "stateAppointedFrom": justice["state"]}
    members.sort(key=lambda m: (m[0]["role"] != "Chief Justice", m[0]["oath"] or ""))
    for nid in retired:
        judges[nid]["retiredJustice"] = True
    courts = {}
    for cid, court in federal_courts.COURTS.items():
        seats = [(j, s) for j in judges.values() for s in j["seats"] if s["court"] == cid]
        if cid == "scotus":
            seats = [(j, s) for j, s in seats if not j.get("retiredJustice")]
        chiefs = sorted({j["id"] for j, s in seats if s["chiefSince"]})
        if len(chiefs) > 1:
            raise JudiciaryError(f"{court['name']} has {len(chiefs)} chief judges: {chiefs}")
        order = sorted(seats, key=lambda js: (js[1]["chiefSince"] is None,
                                              js[1]["seniorSince"] is not None,
                                              js[1]["commissioned"]))
        courts[cid] = {
            # A chief the directory's record contradicts (on senior status):
            # nobody is named, and the page says why.
            "chiefUnsettled": any(s.get("chiefUnsettled") for _j, s in seats) and not chiefs,
            "listed": court.get("fjc", court["name"]) is not None,
            "active": sum(1 for _j, s in seats if not s["seniorSince"]),
            "senior": sum(1 for _j, s in seats if s["seniorSince"]),
            "chief": chiefs[0] if chiefs else None,
            "judges": [j["id"] for j, _s in order],
        }
    courts["scotus"]["chief"] = next(judges[nid]["id"] for j, nid in members
                                     if j["role"] == "Chief Justice")
    courts["scotus"]["judges"] = [judges[nid]["id"] for _j, nid in members]
    courts["scotus"]["retired"] = [judges[nid]["id"] for nid in retired]
    return {
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "asOf": today,
        "reviewed": federal_courts.REVIEWED,
        "sources": {"directory": EXPORT_PAGE, "service": SERVICE_URL, "judges": JUDGES_URL,
                    "supremeCourt": SCOTUS_URL},
        "judges": {j["id"]: {k: v for k, v in j.items() if k != "nid"}
                   for j in sorted(judges.values(), key=lambda j: j["id"])},
        "courts": courts,
        "pending": sorted(pending),
        "conflicts": conflicts,
    }


def fetch(previous=None, today=None, read=None):
    read = read or _get
    today = today or datetime.date.today().isoformat()
    cache = build(read(SERVICE_URL), read(JUDGES_URL), read(SCOTUS_URL), today)
    if previous and len(cache["judges"]) < SHRINK * len(previous.get("judges") or {}):
        raise JudiciaryError(f"the directory lists {len(cache['judges'])} sitting judges, the "
                             f"last read {len(previous['judges'])}: a truncated file is refused")
    return cache


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=None, ensure_ascii=False, sort_keys=True,
                  separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _keys(value):
    """Every key anywhere in a nested record."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def problems(cache, today=None):
    """What a build says about the cache: ``[(level, code, message, detail)]``."""
    if cache is None:
        return []
    out = []
    courts = cache.get("courts") or {}
    missing = sorted(cid for cid in federal_courts.COURTS if cid not in courts)
    if missing:
        out.append(("error", "judiciary-court-missing",
                    f"{len(missing)} courts are not in the judiciary cache", missing))
    members = (courts.get("scotus") or {}).get("judges") or []
    if len(members) != federal_courts.SUPREME_COURT_SEATS:
        out.append(("error", "supreme-court-size",
                    f"the cache seats {len(members)} justices", members))
    judges = cache.get("judges") or {}
    retired = set((courts.get("scotus") or {}).get("retired") or [])
    if retired & set(members):
        out.append(("error", "retired-justice-seated", "a retired justice is listed as a member",
                    sorted(retired & set(members))))
    party = sorted(j for j, rec in judges.items() if "party" in _keys(rec))
    if party:
        out.append(("error", "judge-party", "a judge's record carries a party", party[:10]))
    if cache.get("pending"):
        out.append(("warn", "judges-not-commissioned",
                    f"{len(cache['pending'])} confirmed judges are not commissioned yet and are "
                    f"not listed as sitting", cache["pending"]))
    if cache.get("conflicts"):
        out.append(("warn", "judge-record-conflict",
                    f"{len(cache['conflicts'])} judges' directory records contradict themselves; "
                    f"what they cannot settle is not shown", cache["conflicts"]))
    age = None
    if cache.get("asOf"):
        today = today or datetime.date.today().isoformat()
        age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(cache["asOf"])).days
    if age is not None and age > 30:
        out.append(("warn", "judiciary-stale", f"the judiciary cache is {age} days old; "
                    f"run 'judiciary'", []))
    return out
