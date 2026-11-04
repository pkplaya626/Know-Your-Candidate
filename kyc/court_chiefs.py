"""A court's chief judge as the court's own website names its chief, where
the Federal Judicial Center's directory cannot say (FEDERAL-17).

The directory's record of a chief judge can contradict itself: it lists
Catherine Caldwell Eagles as the Middle District of North Carolina's chief
judge since 2023 *and* on senior status since 2024-12-31, while a chief
judge must be in regular active service (28 U.S.C. 136(a)). The build then
names nobody as chief from the directory (``judiciary.sitting``,
``judge-record-conflict``). Picking one half of the record would be a
guess; so, as for a state's highest court (rule 57), the court's own site is
read through a recipe of its own, and the page shows what it says *beside*
the directory's record, attributed to the court, never in place of it
(rule 82: two sources side by side, neither picked silently).

Rule 57's checks hold: a page naming two chiefs is refused, and so is a
chief the directory does not list on that court by surname *and* first
given name (``vacancies.judge_of``'s test: a surname alone would point at a
colleague of that name); one chief named in two headings is one chief. A
page that cannot be read, or reads in a shape the recipe does not know (no
judge's heading, none titled chief), keeps the last read (rule 8), each
read carries its own day, and a read older than
``STALE_DAYS`` is a build warning. A recipe for a court whose directory
record is settled is read all the same but not shown, and the build says
the recipe can go.

The result is the judiciary cache's ``courtChiefs``:
``{court id: {"chief", "title", "words", "source", "read"}}``, or
``{"unread": True, "source"}`` for a court never read, or ``{"refused":
reason, "source", "read"}`` for a page that did not pass the checks.
"""

import datetime
import html
import re
import time
import urllib.request

from . import agent, vacancies

# Who sends it, never a browser (rule 103): a page that refuses it
# concludes nothing.
USER_AGENT = agent.USER_AGENT
PAUSE = 2.0
STALE_DAYS = 45

# Each court's own page of its judges, and the recipe that reads it. Read
# 2026-11-01: the Middle District of North Carolina lists each judge as a
# heading, "<a>Catherine C. Eagles</a>, Chief District Judge".
RECIPES = {
    "nc-m": {"url": "https://www.ncmd.uscourts.gov/judges-middle-district-north-carolina",
             "recipe": "headings"},
}

_HEADING = re.compile(r"(?is)<h([2-6])\b[^>]*>(.*?)</h\1>")
_TITLED = re.compile(r"^(?:The\s+)?(?:Hon\.?|Honorable)?\s*(.+?),\s*((?:Chief\s+|Senior\s+)?"
                     r"(?:U\.\s?S\.\s+|United\s+States\s+)?"
                     r"(?:District|Circuit|Magistrate|Bankruptcy)?\s*Judge)\s*$", re.I)
_CHIEF = re.compile(r"^Chief\b", re.I)
_SUFFIX = re.compile(r",?\s+(?:Jr\.?|Sr\.?|II|III|IV)$", re.I)


class CourtChiefError(RuntimeError):
    """A court's page could not be read, or did not pass the checks."""


class CourtChiefUnread(CourtChiefError):
    """A court's page is not in a shape its recipe knows: no judge's heading,
    or none titled chief. That concludes nothing (rule 8; the review of PR
    #138): a renamed title ("Chief United States District Judge") would
    otherwise replace a good read with a refusal while nothing had changed."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            page = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise CourtChiefUnread(f"could not fetch {url}: {exc}") from exc
    # A bot wall's or challenge's page, or an empty body, says nothing of
    # the court (rules 8 and 103: one test, agent.walled).
    if agent.walled(page):
        raise CourtChiefUnread(f"{url} answered with a bot wall's page or nothing")
    return page


def _text(fragment):
    fragment = re.sub(r"(?s)<!--.*?-->", " ", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip().replace(" ,", ",")


def read_headings(page):
    """``[{"name", "title", "words"}]``: every heading of the page that is a
    judge's name and title ("Catherine C. Eagles, Chief District Judge"),
    in the page's order. A magistrate or bankruptcy judge is kept as the
    page writes them; only a chief district or circuit judge counts as the
    court's chief."""
    page = re.sub(r"(?is)<(script|style|nav|noscript)\b[^>]*>.*?</\1>", " ", page)
    out = []
    for _level, inner in _HEADING.findall(page):
        words = _text(inner)
        match = _TITLED.match(words)
        if match:
            out.append({"name": match.group(1).strip(), "title": match.group(2).strip(),
                        "words": words})
    return out


def sort_form(name):
    """``"William L. Osteen, Jr."`` -> ``"Osteen, William L."``: the
    directory's own order, for ``vacancies``' surname and given-name test."""
    plain = _SUFFIX.sub("", (name or "").strip()).strip(" ,")
    words = plain.split()
    if len(words) < 2:
        return plain
    return f"{words[-1]}, {' '.join(words[:-1])}"


def directory_judge(name, cid, judges):
    """The one judge the directory lists on court *cid* whose surname and
    first given name are *name*'s, or None."""
    listed = sort_form(name)
    surname, given = vacancies._surname(listed), vacancies._given(listed)
    if not surname or not given:
        return None
    fits = [jid for jid, judge in (judges or {}).items()
            if vacancies._surname(judge.get("sortName")) == surname
            and vacancies._given(judge.get("sortName")) == given
            and any(s.get("court") == cid for s in judge.get("seats") or [])]
    return fits[0] if len(fits) == 1 else None


def read_court(cid, page, judges):
    """The chief court *cid*'s page names, checked: ``{"chief", "title",
    "words", "judge"}``. Raises ``CourtChiefError`` on two different chiefs
    and on a chief the directory does not list on this court, and
    ``CourtChiefUnread`` on a page in a shape the recipe does not know (no
    judge's heading, none titled chief), which concludes nothing."""
    recipe = RECIPES[cid]["recipe"]
    if recipe != "headings":
        raise CourtChiefError(f"{cid}: no reader for recipe {recipe!r}")
    rows = read_headings(page)
    if not rows:
        raise CourtChiefUnread(f"{cid}: the page lists no judge as its recipe knows")
    chiefs = []
    for row in rows:
        if not _CHIEF.match(row["title"]) or re.search(r"magistrate|bankruptcy", row["title"], re.I):
            continue
        # One chief named in two headings is one chief.
        if sort_form(row["name"]).lower() not in [sort_form(c["name"]).lower() for c in chiefs]:
            chiefs.append(row)
    if len(chiefs) > 1:
        raise CourtChiefError(f"{cid}: the page names {len(chiefs)} chief judges: "
                              + "; ".join(r["words"] for r in chiefs))
    if not chiefs:
        raise CourtChiefUnread(f"{cid}: the page names no chief judge as its recipe knows")
    chief = chiefs[0]
    jid = directory_judge(chief["name"], cid, judges)
    if not jid:
        raise CourtChiefError(f"{cid}: the page's chief, {chief['name']}, is not a judge the "
                              f"directory lists on this court by surname and given name")
    return {"chief": chief["name"], "title": chief["title"], "words": chief["words"],
            "judge": jid}


def fetch(judges, previous=None, read=None, today=None):
    """``({court id: entry}, problems)`` for every court with a recipe. A
    page that cannot be read, or that reads in a shape the recipe does not
    know, keeps *previous*'s entry (rule 8); a page that reads but
    contradicts the checks (two chiefs, a chief the directory does not list
    here) is refused, and nothing from it is shown."""
    live = read is None
    read = read or _get
    today = today or datetime.date.today().isoformat()
    out, problems = {}, []
    for i, cid in enumerate(sorted(RECIPES)):
        if live and i:
            time.sleep(PAUSE)
        url = RECIPES[cid]["url"]
        try:
            page = read(url)
            entry = read_court(cid, page, judges)
        except CourtChiefUnread as exc:
            # A page not read, or read in a shape the recipe does not know,
            # concludes nothing: the last read stands.
            problems.append(str(exc))
            old = (previous or {}).get(cid)
            out[cid] = old if old else {"unread": True, "source": url}
            continue
        except CourtChiefError as exc:
            problems.append(str(exc))
            out[cid] = {"refused": str(exc), "source": url, "read": today}
            continue
        out[cid] = dict(entry, source=url, read=today)
    return out, problems


def shown(cache, cid):
    """The court's own word on its chief, for the pages: only for a court
    whose directory record cannot say who is chief, only a read that passed,
    and only while the judge it names still sits on that court."""
    court = ((cache or {}).get("courts") or {}).get(cid) or {}
    entry = ((cache or {}).get("courtChiefs") or {}).get(cid) or {}
    if not court.get("chiefUnsettled") or not entry.get("chief"):
        return None
    if entry.get("judge") not in (court.get("judges") or []):
        return None
    return {"name": entry["chief"], "title": entry["title"], "words": entry["words"],
            "source": entry["source"], "read": entry["read"], "judge": entry["judge"]}


def problems(cache, today=None):
    """What a build says: ``[(level, code, message, detail)]``."""
    if cache is None:
        return []
    today = today or datetime.date.today().isoformat()
    courts = cache.get("courts") or {}
    reads = cache.get("courtChiefs") or {}
    out = []
    unsettled = sorted(cid for cid, court in courts.items() if court.get("chiefUnsettled"))
    no_recipe = [cid for cid in unsettled if cid not in RECIPES]
    if no_recipe:
        out.append(("warn", "court-chief-no-recipe",
                    f"{len(no_recipe)} court(s) whose directory record cannot say who is chief "
                    f"have no recipe to read the court's own site (kyc/court_chiefs.py)",
                    no_recipe))
    unused = sorted(cid for cid in RECIPES if cid not in unsettled)
    if unused:
        out.append(("warn", "court-chief-recipe-unused",
                    f"{len(unused)} court chief recipe(s) are for courts whose directory record "
                    f"is settled; the court's read is not shown, and the recipe can go", unused))
    unread, refused, stale, gone = [], [], [], []
    for cid in unsettled:
        if cid not in RECIPES:
            continue
        entry = reads.get(cid)
        if not entry or entry.get("unread"):
            unread.append(cid)
            continue
        if entry.get("refused"):
            refused.append(entry["refused"])
            continue
        if entry.get("judge") not in (courts[cid].get("judges") or []):
            gone.append(f"{cid}: {entry.get('chief')}")
        age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(entry["read"])).days
        if age > STALE_DAYS:
            stale.append(f"{cid}: read {entry['read']} ({age} days)")
    if unread:
        out.append(("warn", "court-chief-unread",
                    f"{len(unread)} court(s)' own sites have not been read for their chief; run "
                    f"'judiciary --chiefs-only'", unread))
    if refused:
        out.append(("warn", "court-chief-refused",
                    f"{len(refused)} court page(s) did not pass the chief's checks; nothing from "
                    f"them is shown", refused))
    if gone:
        out.append(("warn", "court-chief-not-sitting",
                    f"{len(gone)} court page(s) name a chief the directory no longer lists on "
                    f"that court; not shown until read again", gone))
    if stale:
        out.append(("warn", "court-chief-stale",
                    f"{len(stale)} court chief read(s) are over {STALE_DAYS} days old; run "
                    f"'judiciary --chiefs-only'", stale))
    return out
