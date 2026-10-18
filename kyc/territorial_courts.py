"""The judges of the three territorial district courts, as each court lists
them (FEDERAL-06).

Guam's, the Northern Mariana Islands' and the Virgin Islands' district
judges are nominated by the President and confirmed by the Senate, but they
serve ten-year terms under Article IV, so the Federal Judicial Center's
directory of Article III judges - which every other court page is built
from - does not list them. No other source lists them either, so, as for a
state's highest court (rule 57), each court's own website is read through a
recipe of its own, and nothing is taken from Wikipedia or a search:

- Guam: the court's "Judicial Officers" page, a name ("Hon. ...") and its
  title, line by line;
- the Northern Mariana Islands: the court's own banner on its home page,
  "Hon. <name>, <title>" between bullets;
- the Virgin Islands: each judge's page linked from "Judges' Info", which
  opens with the name and "United States [Chief|District] Judge for the
  District Court of the Virgin Islands".

Only a district judge is kept: a magistrate judge, a bankruptcy judge or a
clerk the page also names is not one. A roster with more judges than the
statute gives the court seats, or two chiefs, is refused; fewer is
"nobody else listed by the court", never "vacant" (rule 19). A page that
cannot be read keeps the last roster read (rule 8), and a court never read
says so.
"""

import datetime
import html
import re
import time
import urllib.request

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 know-your-candidate/1.0")
PAUSE = 2.0

# The seats and the term each court's statute gives it.
COURTS = {
    "gu": {"url": "https://www.gud.uscourts.gov/judicial-officers", "recipe": "lines",
           "seats": 1, "statute": "48 U.S.C. 1424b(a)"},
    "mp": {"url": "https://www.nmid.uscourts.gov/", "recipe": "banner",
           "seats": 1, "statute": "48 U.S.C. 1821(b)"},
    "vi": {"url": "https://www.vid.uscourts.gov/judges-info", "recipe": "pages",
           "seats": 2, "statute": "48 U.S.C. 1614(a)"},
}
TERM = "ten years"

_NOT_DISTRICT = re.compile(r"magistrate|bankruptcy|clerk|visiting|senior", re.I)
_DISTRICT = re.compile(r"\b(?:chief|district)\s+judge\b|^judge$", re.I)


class TerritorialCourtError(RuntimeError):
    """A court's page is not what its recipe knows."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise TerritorialCourtError(f"could not fetch {url}: {exc}") from exc


def _text_lines(page):
    """The page's visible text, a line per element, without scripts,
    styles, comments or navigation."""
    page = re.sub(r"(?s)<!--.*?-->", " ", page)
    page = re.sub(r"(?is)<(script|style|nav|noscript)\b[^>]*>.*?</\1>", " ", page)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page)).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if line.strip()]


def _name(text):
    """A judge's name without the honorific."""
    return re.sub(r"^(?:The\s+)?(?:Hon\.?|Honorable)\s+", "", text.strip(), flags=re.I).strip(" ,")


def _judge(name, title):
    """``{"name", "title", "chief"}`` for a district judge, or None."""
    if not name or _NOT_DISTRICT.search(title) or not _DISTRICT.search(title):
        return None
    return {"name": _name(name), "title": title.strip(), "chief": bool(re.search(r"\bchief\b", title, re.I))}


def read_lines(page):
    """Guam: ``Hon. <name>`` then its title on the next line."""
    lines = _text_lines(page)
    out = []
    for i, line in enumerate(lines[:-1]):
        if re.match(r"^(?:Hon\.?|Honorable)\s+\S", line):
            judge = _judge(line, lines[i + 1])
            if judge:
                out.append(judge)
    return out


def read_banner(page):
    """The Northern Mariana Islands: "Hon. <name>, <title>" between
    bullets, in the site's banner (its ``site-slogan``)."""
    match = re.search(r'(?is)class="site-slogan"[^>]*>(.*?)</h1>', page)
    if not match:
        raise TerritorialCourtError("the court's banner naming its judges is not on the page")
    text = html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
    out = []
    for part in re.split(r"\s*[•|]\s*", text):
        found = re.match(r"^\s*((?:Hon\.?|Honorable)\s+.+?),\s*(.+?)\s*$", part)
        if found:
            judge = _judge(found.group(1), found.group(2))
            if judge:
                out.append(judge)
    return out


def judge_pages(page):
    """The Virgin Islands: each judge's own page, linked from Judges' Info."""
    return sorted(set(re.findall(r'href="(/content/honorable-[a-z0-9-]+)"', page)))


def read_judge_page(page):
    """One Virgin Islands judge: the name, then "United States ... Judge for
    the District Court of the Virgin Islands"."""
    main = re.search(r'(?s)id="main-content".*', page)
    lines = _text_lines(main.group(0) if main else page)
    for i, line in enumerate(lines[:-1]):
        if re.match(r"^(?:Hon\.?|Honorable)\s+\S", line) and re.search(
                r"Judge for the District Court of the Virgin Islands", lines[i + 1]):
            title = re.sub(r"^United States\s+", "", lines[i + 1])
            title = re.sub(r"\s+for the District Court of the Virgin Islands$", "", title)
            return _judge(line, title)
    return None


def check(cid, judges):
    """Rule 57's refusals: more judges than seats, or two chiefs."""
    seats = COURTS[cid]["seats"]
    if len(judges) > seats:
        raise TerritorialCourtError(f"{cid}: the page names {len(judges)} district judges for "
                                    f"{seats} seat(s)")
    if sum(1 for j in judges if j["chief"]) > 1:
        raise TerritorialCourtError(f"{cid}: the page names two chief judges")
    if len({j["name"] for j in judges}) != len(judges):
        raise TerritorialCourtError(f"{cid}: the page names one judge twice")
    # The chief first, as every court page lists its judges.
    return sorted(judges, key=lambda j: not j["chief"])


def read_court(cid, read=None, live=False):
    """One court's district judges, as its own site lists them."""
    read = read or _get
    court = COURTS[cid]
    page = read(court["url"])
    if court["recipe"] == "lines":
        judges = read_lines(page)
    elif court["recipe"] == "banner":
        judges = read_banner(page)
    else:
        links = judge_pages(page)
        if not links:
            raise TerritorialCourtError(f"{cid}: no judge's page is linked from {court['url']}")
        base = re.match(r"^https://[^/]+", court["url"]).group(0)
        judges = []
        for link in links:
            if live:
                time.sleep(PAUSE)
            judge = read_judge_page(read(base + link))
            if judge:
                judges.append(dict(judge, page=base + link))
    return check(cid, judges)


def fetch(previous=None, read=None, today=None, log=print):
    """``({court id: entry}, problems)``. An entry is ``{"judges", "source",
    "read", "seats", "statute"}``; a court whose page cannot be read keeps
    *previous*'s entry, or is ``{"unread": True}`` if it never was."""
    live = read is None
    today = today or datetime.date.today().isoformat()
    out, problems = {}, []
    for i, cid in enumerate(COURTS):
        if live and i:
            time.sleep(PAUSE)
        court = COURTS[cid]
        try:
            judges = read_court(cid, read, live)
        except TerritorialCourtError as exc:
            problems.append(str(exc))
            old = (previous or {}).get(cid)
            out[cid] = old if old else {"unread": True, "source": court["url"]}
            continue
        out[cid] = {"judges": judges, "source": court["url"], "read": today,
                    "seats": court["seats"], "statute": court["statute"]}
    return out, problems
