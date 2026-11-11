"""Each federal judge's financial disclosure reports, as CourtListener holds
them, joined by the Federal Judicial Center's own id (FEDERAL-05).

Federal judges file annual financial disclosure reports under the Ethics in
Government Act (5 U.S.C. 13103); the Administrative Office of the U.S.
Courts releases them only on request, and the Free Law Project's
CourtListener publishes the ones it has obtained. Its REST API answers
anyone without an account "Authentication credentials were not provided."
(HTTP 401), but it publishes the same database as public bulk files, with
no account or token, every quarter:

- ``people-db-people-<date>.csv.bz2``: every person, with ``fjc_id``, the
  FJC's *judge id* (its ``jid``, not the ``nid`` this site keys judges on;
  the FJC's own judges file gives both on one row);
- ``financial-disclosures-<date>.csv.bz2``: every report, by ``person_id``
  and ``year``.

A judge is joined only through that id (rule 32), never by a name search,
and an id is not proof on its own (rule 82): the person's record must carry
the judge's surname as the directory writes it (accents, case and a
compound's other half aside: "DeArcy Hall" is CourtListener's "Hall"), and
a year of birth the directory's agrees with where both give one; where
either gives none, its first given name (or that name's initial) must be
one of the directory's given names, or a record carrying a namesake
colleague's id would pass on the surname alone. What disagrees gives
nothing and is reported. A joined judge with reports links their
CourtListener page at its "Financial Disclosures" section. One whose joined
record holds none is said to be exactly that - the record carrying their
FJC id lists no reports - and that record is linked so a reader can look:
CourtListener keeps duplicate records, and Judge Graber's fifteen reports
are filed under one that carries no FJC id. It never reads that
CourtListener holds none for the judge, let alone that none was filed
(rule 19), and a duplicate is never joined by its name (rule 32). A read
that fails, or comes back short, keeps the cache (rule 8).

The result is ``data/judge_disclosures.json``.
"""

import bz2
import collections
import csv
import datetime
import io
import json
import os
import re
import time
import unicodedata
import urllib.request

from . import agent, judiciary

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "judge_disclosures.json")
BUCKET = "https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/"
LISTING = BUCKET + "?list-type=2&prefix=bulk-data/"
PEOPLE = "people-db-people-"
REPORTS = "financial-disclosures-"
PERSON_RECORD = "https://www.courtlistener.com/person/{id}/{slug}/"
PERSON_PAGE = PERSON_RECORD + "#disclosures"
SITE = "https://www.courtlistener.com/"
USER_AGENT = agent.USER_AGENT   # rule 103: who sends it, never a browser
PAUSE = 1.0
# CourtListener exports quarterly; a file older than this has missed one.
EXPORT_STALE_DAYS = 200
READ_STALE_DAYS = 60
# A file with fewer rows than this is truncated, not the database.
MIN_PEOPLE = 10_000
MIN_REPORTS = 50_000
# Fewer joined judges than this share of the last read is refused.
SHRINK = 0.9

_DATED = re.compile(r"^bulk-data/(?P<family>[a-z-]+?-)(?P<date>\d{4}-\d{2}-\d{2})\.csv\.bz2$")


class JudgeDisclosuresError(RuntimeError):
    """A source could not be read, or is not what the pipeline expects."""


def _get(url, timeout=180):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except OSError as exc:
        raise JudgeDisclosuresError(f"could not fetch {url}: {exc}") from exc


# ------------------------------------------------------------ the files

def latest_export(*listings):
    """The newest date for which both files exist, from the bucket's
    listings. A truncated listing is refused: a newer file could be past it."""
    dates = collections.defaultdict(set)
    for listing_xml in listings:
        if "<IsTruncated>true</IsTruncated>" in listing_xml:
            raise JudgeDisclosuresError("the bucket's listing is truncated")
        for key in re.findall(r"<Key>([^<]+)</Key>", listing_xml):
            match = _DATED.match(key)
            if match:
                dates[match.group("family")].add(match.group("date"))
    both = dates[PEOPLE] & dates[REPORTS]
    if not both:
        raise JudgeDisclosuresError("the listing holds no people file and disclosures file "
                                    "of one date")
    return max(both)


def file_url(family, date):
    return f"{BUCKET}bulk-data/{family}{date}.csv.bz2"


def _csv(data):
    csv.field_size_limit(2 ** 31 - 1)
    text = bz2.decompress(data).decode("utf-8") if data[:3] == b"BZh" else data.decode("utf-8")
    return csv.DictReader(io.StringIO(text, newline=""))


def read_people(data):
    """``{fjc_id: person}`` for every person record carrying an FJC id, and
    the ids two records carry (neither is joined)."""
    rows = list(_csv(data))
    if len(rows) < MIN_PEOPLE:
        raise JudgeDisclosuresError(f"the people file holds {len(rows)} rows: truncated")
    by_id, twice = {}, set()
    for row in rows:
        fid = (row.get("fjc_id") or "").strip()
        if not fid:
            continue
        if fid in by_id:
            twice.add(fid)
        by_id[fid] = {"id": row["id"].strip(), "slug": row["slug"].strip(),
                      "last": row.get("name_last", "").strip(),
                      "first": row.get("name_first", "").strip(),
                      "middle": row.get("name_middle", "").strip(),
                      "dob": row.get("date_dob", "").strip(),
                      "alias": bool((row.get("is_alias_of_id") or "").strip())}
    return by_id, twice


def read_reports(data):
    """``{person id: [year, ...]}``: every report CourtListener holds."""
    out = collections.defaultdict(list)
    count = 0
    for row in _csv(data):
        count += 1
        pid = (row.get("person_id") or "").strip()
        year = (row.get("year") or "").strip()
        if pid and re.fullmatch(r"\d{4}", year):
            out[pid].append(year)
    if count < MIN_REPORTS:
        raise JudgeDisclosuresError(f"the disclosures file holds {count} rows: truncated")
    return out


def read_jids(text):
    """``{nid: jid}`` from the FJC's own judges file, one row per judge."""
    out, seen = {}, collections.Counter()
    for row in csv.DictReader(io.StringIO(text)):
        nid, jid = (row.get("nid") or "").strip(), (row.get("jid") or "").strip()
        if nid and jid:
            out[nid] = jid
            seen[jid] += 1
    # A judge id the file gives two judges joins neither.
    return {nid: jid for nid, jid in out.items() if seen[jid] == 1}


# ------------------------------------------------------------ the join

def _fold(text):
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z' ]", " ", plain.replace("-", " ")).split()


def surname_agrees(directory, theirs):
    """The directory's surname and CourtListener's are one: the same words,
    or one a part of the other's compound ("DeArcy Hall" and "Hall";
    "Quiñones Alejandro" and "Quinones Alejandro"). "Richman" and "Owen" are
    not, whatever the reason."""
    a, b = _fold(directory), _fold(theirs)
    if not a or not b:
        return False
    return a == b or set(a) <= set(b) or set(b) <= set(a)


def directory_surname(judge):
    return (judge.get("sortName") or "").split(",")[0].strip()


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _given_words(text):
    """A name's words, folded, with brackets dropped as the letters they
    hold ("R[obert]" is "Robert") and suffixes left out."""
    return [w for w in _fold(re.sub(r"[\[\]]", "", text or "")) if w not in _SUFFIXES]


def given_agrees(judge, person):
    """CourtListener's first given name is one of the directory's given
    names: the same word, or an initial of it ("W." for William), or the
    directory's initial for it. The directory's given names are its full
    name's words other than the surname's, and its sort name's."""
    theirs = _given_words(person.get("first"))
    if not theirs:
        return False
    first = theirs[0]
    surname = set(_given_words(directory_surname(judge)))
    given = (_given_words((judge.get("sortName") or "").partition(",")[2])
             + [w for w in _given_words(judge.get("name")) if w not in surname])
    return any(w == first or (len(first) == 1 and w[0] == first)
               or (len(w) == 1 and first[0] == w) for w in given)


def join(judges, jids, people, twice, reports):
    """``({nid: entry}, refused)``. An entry is ``{"person", "slug",
    "reports", "first", "last"}`` (``reports`` 0 and no years where the
    joined record lists none); a judge no person record carries is not an
    entry."""
    out, refused = {}, []
    for key, judge in sorted(judges.items()):
        nid = key.replace("fjc-", "")
        jid = jids.get(nid)
        person = people.get(jid) if jid else None
        if not person:
            continue
        name = judge.get("name") or key
        if jid in twice:
            refused.append(f"{name}: two CourtListener records carry FJC id {jid}")
            continue
        if person["alias"]:
            refused.append(f"{name}: CourtListener's record for FJC id {jid} is an alias")
            continue
        if not surname_agrees(directory_surname(judge), person["last"]):
            refused.append(f"{name}: CourtListener's record for FJC id {jid} has the surname "
                           f"{person['last']!r}, the directory {directory_surname(judge)!r}")
            continue
        born = ((judge.get("born") or {}).get("year") or "").strip()
        theirs = person["dob"][:4]
        both_years = bool(re.fullmatch(r"\d{4}", born) and re.fullmatch(r"\d{4}", theirs))
        if both_years and theirs != born:
            refused.append(f"{name}: CourtListener's record for FJC id {jid} gives a birth year "
                           f"of {theirs}, the directory {born}")
            continue
        # With no year to compare, the surname alone would join a record
        # carrying a namesake colleague's id: the given name must agree too.
        if not both_years and not given_agrees(judge, person):
            refused.append(f"{name}: CourtListener's record for FJC id {jid} has the given name "
                           f"{person['first']!r} and no year of birth to compare; the directory's "
                           f"given names do not include it")
            continue
        years = sorted(reports.get(person["id"]) or [])
        entry = {"person": person["id"], "slug": person["slug"], "reports": len(years)}
        if years:
            entry.update(first=years[0], last=years[-1])
        out[nid] = entry
    return out, refused


def fetch(judges, previous=None, read=None, today=None, log=print):
    """The cache, read afresh. Raises on anything short or unreadable, and
    the caller keeps *previous* (rule 8)."""
    live = read is None
    read = read or _get
    today = today or datetime.date.today().isoformat()
    export = latest_export(read(LISTING + PEOPLE).decode("utf-8"),
                           read(LISTING + REPORTS).decode("utf-8"))
    if live:
        time.sleep(PAUSE)
    jids = read_jids(read(judiciary.JUDGES_URL).decode("utf-8", errors="replace"))
    people, twice = read_people(read(file_url(PEOPLE, export)))
    reports = read_reports(read(file_url(REPORTS, export)))
    joined, refused = join(judges, jids, people, twice, reports)
    before = len((previous or {}).get("judges") or {})
    if before and len(joined) < SHRINK * before:
        raise JudgeDisclosuresError(f"{len(joined)} judges joined, the last read {before}: "
                                    f"refused")
    log(f"  CourtListener export of {export}: {len(joined)} of {len(judges)} judges joined by "
        f"FJC id, {sum(1 for e in joined.values() if e['reports'])} with reports; "
        f"{len(refused)} refused")
    return {"read": today, "export": export,
            "sources": {"people": file_url(PEOPLE, export), "reports": file_url(REPORTS, export),
                        "fjc": judiciary.JUDGES_URL, "site": SITE},
            "judges": joined, "refused": refused}


# ------------------------------------------------------------ the pages

def for_judge(cache, nid):
    """What a judge's dialog shows: ``{"url", "reports", "first", "last"}``
    (the record's "Financial Disclosures" section); ``{"record", "reports":
    0}`` for a joined judge whose record lists none, the record itself linked
    so a reader can look, since the words are about that record only; or
    None for a judge no record joins."""
    entry = ((cache or {}).get("judges") or {}).get(nid)
    if not entry:
        return None
    if not entry.get("reports"):
        return {"record": PERSON_RECORD.format(id=entry["person"], slug=entry["slug"]),
                "reports": 0}
    return {"url": PERSON_PAGE.format(id=entry["person"], slug=entry["slug"]),
            "reports": entry["reports"], "first": entry["first"], "last": entry["last"]}


def source(cache):
    """The export the dialog's note names, or None."""
    if not cache:
        return None
    return {"export": cache["export"], "read": cache["read"], "url": SITE}


def problems(cache, judges=None, today=None):
    """``[(level, code, message, detail)]`` for a build."""
    if cache is None:
        return [("warn", "judge-disclosures-unread",
                 f"no {CACHE_PATH}; run 'judiciary --disclosures-only'", [])]
    today = datetime.date.fromisoformat(today or datetime.date.today().isoformat())
    out = []
    bad = [nid for nid, e in (cache.get("judges") or {}).items()
           if e.get("reports") and not (e.get("person") and e.get("slug") and e.get("first"))]
    if bad:
        out.append(("error", "judge-disclosures-record",
                    f"{len(bad)} judge disclosure entries lack a person, slug or year", bad[:10]))
    if cache.get("refused"):
        out.append(("warn", "judge-disclosures-refused",
                    f"{len(cache['refused'])} CourtListener records carry a judge's FJC id but "
                    f"disagree with the directory; no link is shown", cache["refused"]))
    if judges is not None:
        gone = sorted(nid for nid in cache.get("judges") or {} if f"fjc-{nid}" not in judges)
        if gone:
            out.append(("warn", "judge-disclosures-unsitting",
                        f"{len(gone)} disclosure entries are for judges no longer sitting; run "
                        f"'judiciary --disclosures-only'", gone[:10]))
    export = (today - datetime.date.fromisoformat(cache["export"])).days
    read = (today - datetime.date.fromisoformat(cache["read"])).days
    if export > EXPORT_STALE_DAYS or read > READ_STALE_DAYS:
        out.append(("warn", "judge-disclosures-stale",
                    f"CourtListener's export of {cache['export']} was read {cache['read']}; run "
                    f"'judiciary --disclosures-only'", []))
    return out


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
