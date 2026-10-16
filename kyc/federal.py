"""The federal executive: the President, the Vice President and the Cabinet.

``python build_profile_site.py federal`` reads four sources and writes
``data/federal_executive.json``:

- **The President and Vice President** from congress-legislators'
  ``executive.json`` - the project already behind the membership snapshot -
  whose terms carry dates, party and ids (rules 17 and 32). The White
  House's own administration page must name the same two people, or the
  build says so; their portraits come from their White House pages.
- **Who sits in each Cabinet office** from the White House's Cabinet page:
  the authority on which officials the President counts as Cabinet, and on
  nothing else (rule 55). Every title on it must map to an office in
  ``federal_offices``; a title the table does not know stops the read, so a
  person is never silently dropped.
- **The Senate's confirmation** of each holder, from its roll-call votes
  (senate.gov, no key): the vote, the date, the tally. A confirmation by
  voice vote has no roll call, and the page says it found none - never that
  the person was not confirmed (rule 19).
- **The office's own page** naming its head beside the title
  (``names_holder``, rule 56). A page that refuses the request - several
  departments answer every script with 403 - concludes nothing (rule 8):
  the office is shown as the White House lists it, attributed.

Nothing here is a party for a Cabinet officer: no source used states one.
The President and Vice President carry the party their term records.
"""

import datetime
import html
import json
import os
import re
import time
import urllib.request

from . import federal_offices
from .officers import _fold, same_person, visible_text

EXECUTIVE_URL = "https://unitedstates.github.io/congress-legislators/executive.json"
VOTE_MENU_URL = ("https://www.senate.gov/legislative/LIS/roll_call_lists/"
                 "vote_menu_{congress}_{session}.xml")
VOTE_URL = ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/"
            "vote_{congress}_{session}_{number}.htm")
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "federal_executive.json")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 know-your-candidate/1.0")


class FederalError(RuntimeError):
    """A source could not be read, or is not what the pipeline expects."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise FederalError(f"could not fetch {url}: {exc}") from exc


def _text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# ------------------------------------------------- the President and the VP

def _full_name(name):
    if name.get("official_full"):
        return name["official_full"]
    parts = [name.get("first"), name.get("middle"), name.get("last")]
    full = " ".join(p for p in parts if p)
    return f"{full}, {name['suffix']}" if name.get("suffix") else full


def parse_executive(rows, today):
    """``{"president": {...}, "vicePresident": {...}}``: whoever's term of
    each kind covers *today* (an ISO date). None current, or two, is an
    error - a stale file must fail, not show a past president."""
    found = {"prez": [], "viceprez": []}
    for row in rows or []:
        for term in row.get("terms") or []:
            kind = term.get("type")
            if kind in found and term.get("start", "") <= today < term.get("end", ""):
                found[kind].append((row, term))
    out = {}
    for kind, key in (("prez", "president"), ("viceprez", "vicePresident")):
        if len(found[kind]) != 1:
            raise FederalError(f"{len(found[kind])} current {kind} terms in executive.json "
                               f"on {today}; expected one")
        row, term = found[kind][0]
        ids = row.get("id") or {}
        out[key] = {
            "name": _full_name(row.get("name") or {}),
            "party": term.get("party"),
            "termStart": term.get("start"),
            "termEnd": term.get("end"),
            "ids": {k: ids[k] for k in ("bioguide", "wikidata", "wikipedia", "ballotpedia",
                                         "govtrack", "votesmart", "opensecrets")
                    if ids.get(k)},
        }
    return out


_LEADER = re.compile(r'<a[^>]+href="((?:https://www\.whitehouse\.gov)?/administration/[^"/]+/)"'
                     r'[^>]*>\s*(Vice President|President)\s+([^<]+?)\s*</a>')


def parse_administration(page):
    """``{"President": (name, url), "Vice President": (name, url)}`` from
    the White House's administration page: the links whose own text is the
    title and the name ("President Donald J. Trump")."""
    main = page[page.find("<main"):page.find("</main>")] if "<main" in page else page
    out = {}
    for url, title, name in _LEADER.findall(main):
        if url.startswith("/"):
            url = "https://www.whitehouse.gov" + url
        out.setdefault(title, (_text(name), url))
    return out


_IMG = re.compile(r'<img[^>]*\bsrc="(https://www\.whitehouse\.gov/wp-content/uploads/[^"?]+)'
                  r'[^"]*"[^>]*>')


def photo_set(tag, photo):
    """The sizes the White House serves of *photo*, from its img tag's
    srcset: ``[[url, width], ...]``, narrowest first. Only sizes of that one
    file (rule 42); the originals run to 6 MB, and a card draws 72px."""
    found = re.search(r'\bsrcset="([^"]+)"', tag)
    out = []
    # A candidate is "url widthw"; the URLs themselves hold commas
    # ("?resize=428,600"), so the list is read by its pairs, never split on
    # commas - which kept only the 6 MB originals.
    for url, width in re.findall(r"(\S+)\s+(\d+)w", found.group(1) if found else ""):
        url = html.unescape(url.lstrip(","))
        if url.split("?")[0] == photo:
            out.append([url, int(width)])
    return sorted(out, key=lambda pair: pair[1])


def portrait(page):
    """``(photo, sizes)``: the first image inside a White House page's main
    content and the sizes of it the page lists, or ``(None, [])``."""
    main = page[page.find("<main"):page.find("</main>")] if "<main" in page else ""
    match = _IMG.search(main)
    if not match:
        return None, []
    return match.group(1), photo_set(match.group(0), match.group(1))


# ------------------------------------------------------------- the Cabinet

_ENTRY = re.compile(
    r'<h2 class="wp-block-heading has-text-align-center">(.*?)</h2>.*?'
    r'<h3 class="wp-block-heading has-text-align-center">(.*?)</h3>(.*?)'
    r'(?=<h2 class="wp-block-heading has-text-align-center">|$)', re.S)


def parse_cabinet(page):
    """``[{name, title, photo}]`` from the White House's Cabinet page, in the
    page's order. Every name heading must be read, or the page is not what
    this parser knows, and it says so."""
    main = page[page.find("<main"):page.find("</main>")] if "<main" in page else ""
    headings = main.count('<h2 class="wp-block-heading has-text-align-center">')
    out = []
    for name, title, block in _ENTRY.findall(main):
        img = _IMG.search(block)
        out.append({"name": _text(name), "title": _text(title),
                    "photo": img.group(1) if img else None,
                    "photoSet": photo_set(img.group(0), img.group(1)) if img else []})
    if not out or len(out) != headings:
        raise FederalError(f"read {len(out)} of the Cabinet page's {headings} entries")
    return out


def assign(entries):
    """``({office key: entry}, unknown titles)``. One person per office."""
    titles = federal_offices.by_title()
    held, unknown = {}, []
    for entry in entries:
        office = titles.get(entry["title"])
        if office is None:
            unknown.append(f"{entry['name']}: {entry['title']!r}")
            continue
        if office["key"] in held:
            raise FederalError(f"the Cabinet page lists two people as {office['office']}")
        held[office["key"]] = entry
    return held, unknown


# --------------------------------------------------- the office's own page

_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}
# Before a title, a word that makes it someone else's: a former holder, a
# deputy, an under or assistant secretary, an acting one (read apart).
_NOT_HEAD = (r"(?<!former )(?<!then )(?<!past )(?<!previous )(?<!late )(?<!deputy )"
             r"(?<!under )(?<!assistant )(?<!acting )(?<!associate )")
# Words that may stand between a name and its title after it: "Linda E.
# McMahon serves as the 13th United States Secretary of Education".
_BETWEEN = {"of", "the", "s", "department", "office", "serves", "as", "is",
            "united", "states", "u", "current"}


def _words(name):
    return [w for w in _fold(re.sub(r'"[^"]*"', " ", name)).split() if w not in _SUFFIX]


def names_holder(name, text, title, forms=()):
    """Whether *text* (an office's visible page text) names *name* as the
    holder of the office whose title is *title* (a folded pattern): the title
    then the name, the name then the title with only a few plain words
    between, or the title then the surname. ``officers.names_holder`` for
    federal titles; *forms* are evidenced other spellings (NAME_FORMS)."""
    folded = _fold(text)
    for form in (name,) + tuple(forms):
        words = _words(form)
        if len(words) < 2:
            continue
        first, last = re.escape(words[0]), re.escape(words[-1])
        full = rf"\b{first}(?: [a-z]+){{0,2}} {last}\b"
        if re.search(rf"{_NOT_HEAD}(?:{title}) {full}", folded):
            return True
        if re.search(rf"{_NOT_HEAD}(?:{title}) {last}\b", folded):
            return True
        for match in re.finditer(rf"{full}((?: [a-z0-9]+){{0,6}}?) (?:{title})", folded):
            between = match.group(1).split()
            if all(w in _BETWEEN or re.fullmatch(r"\d+(st|nd|rd|th)", w) for w in between):
                return True
    return False


def acting(name, text, title):
    """Whether the page calls them acting: "Acting Secretary ... Smith"."""
    words = _words(name)
    if not words:
        return False
    return bool(re.search(rf"\bacting (?:{title}) (?:[a-z]+ ){{0,2}}{re.escape(words[-1])}\b",
                          _fold(text)))


def confirm_on_page(office, name, read=None, pause=0.5):
    """``{"status", "url"[, "acting"]}`` for *name* in *office*, from the
    office's own pages, tried in order:

    - ``confirmed`` - a page names them beside the title;
    - ``unconfirmed`` - every page that could be read names nobody so;
    - ``unreadable`` - no page could be read (a 403, a timeout, a page drawn
      by JavaScript): this concludes nothing (rule 8);
    - ``none`` - the office has no page that names its head (OMB).
    """
    read = read or _get
    if not office["pages"]:
        return {"status": "none"}
    forms = [form for (key, holder), (form, _why) in federal_offices.NAME_FORMS.items()
             if key == office["key"] and same_person(holder, name)]
    seen = None
    for url in office["pages"]:
        text = None
        # A failed request is tried once more before the page counts as
        # unreadable: one timeout must not read as "not named" (rule 8).
        for _attempt in range(2):
            try:
                text = visible_text(read(url))
                break
            except FederalError:
                time.sleep(pause)
        if text is None:
            continue
        if len(text) < 300:
            continue                 # an error page or a script-drawn shell
        seen = url
        if names_holder(name, text, office["pageTitle"], forms):
            found = {"status": "confirmed", "url": url}
            if acting(name, text, office["pageTitle"]):
                found["acting"] = True
            return found
    return {"status": "unconfirmed", "url": seen} if seen else {"status": "unreadable"}


# ------------------------------------------------------------ the Senate

_VOTE = re.compile(r"<vote>(.*?)</vote>", re.S)
_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _tag(block, tag):
    match = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    return " ".join(html.unescape(match.group(1)).split()) if match else ""


def parse_vote_menu(xml):
    """The roll-call votes in one session's menu, each with an ISO date."""
    congress, session = _tag(xml, "congress"), _tag(xml, "session")
    year = _tag(xml, "congress_year")
    out = []
    for block in _VOTE.findall(xml):
        day, _, month = _tag(block, "vote_date").partition("-")
        if not (day.isdigit() and month in _MONTHS and year.isdigit()):
            raise FederalError(f"a Senate vote date the parser does not read: "
                               f"{_tag(block, 'vote_date')!r}")
        out.append({
            "congress": int(congress), "session": int(session),
            "number": _tag(block, "vote_number"),
            "date": f"{year}-{_MONTHS[month]:02d}-{int(day):02d}",
            "issue": _tag(block, "issue"),
            "question": _tag(block, "question"),
            "result": _tag(block, "result"),
            "yeas": _tag(block, "yeas"), "nays": _tag(block, "nays"),
            "title": _tag(block, "title"),
        })
    return out


_CONFIRMATION = re.compile(r"^Confirmation: (.+?), of (?:the )?[A-Z][\w .'-]+?, to be (?:the )?(.+)$")


def confirmation(office, name, votes):
    """The latest roll call that confirmed someone of *name*'s surname to
    *office*, or None. The office is matched on the Senate's own wording of
    it, and the surname must agree - two signals, never a name alone."""
    want = _words(name)[-1:] if _words(name) else []
    found = None
    for vote in votes:
        if vote["question"] != "On the Nomination" or vote["result"] != "Confirmed":
            continue
        match = _CONFIRMATION.match(vote["title"])
        if not match or match.group(2) not in office["senate"]:
            continue
        nominee = match.group(1)
        if want and _words(nominee)[-1:] == want and (found is None or vote["date"] > found["date"]):
            found = dict(vote, nominee=nominee)
    if not found:
        return None
    return {
        "vote": f"{found['congress']}-{found['session']}-{int(found['number'])}",
        "date": found["date"], "yeas": int(found["yeas"] or 0), "nays": int(found["nays"] or 0),
        "issue": found["issue"], "nominee": found["nominee"],
        "url": VOTE_URL.format(congress=found["congress"], session=found["session"],
                               number=found["number"]),
    }


# ------------------------------------------------------------------ fetch

def senate_votes(congress, read=None):
    """Every roll call of *congress* and the one before, or None when a menu
    could not be read (inconclusive: the last run's confirmations stand)."""
    read = read or _get
    votes = []
    for number in (congress - 1, congress):
        for session in (1, 2):
            try:
                votes += parse_vote_menu(read(VOTE_MENU_URL.format(congress=number,
                                                                   session=session)))
            except FederalError as exc:
                if number == congress and session == 2 and "404" in str(exc):
                    continue         # a Congress's second session has not begun
                return None
    return votes


def fetch(previous=None, today=None, read=None, log=print, history_read=None):
    """The whole cache. Raises :class:`FederalError` when the White House's
    pages or the executive file cannot be read, so the last good cache
    stands."""
    from . import cycle

    read = read or _get
    today = today or datetime.date.today().isoformat()
    leaders = parse_executive(json.loads(read(EXECUTIVE_URL)), today)
    admin = parse_administration(read(federal_offices.ADMINISTRATION_URL))
    problems = []
    for key, title in (("president", "President"), ("vicePresident", "Vice President")):
        listed = admin.get(title)
        person = leaders[key]
        if not listed or not same_person(listed[0], person["name"]):
            problems.append(f"the White House's administration page names "
                            f"{listed[0] if listed else 'nobody'!r} as {title}, the executive file "
                            f"{person['name']!r}")
            continue
        person["page"] = listed[1]
        try:
            person["photo"], person["photoSet"] = portrait(read(listed[1]))
        except FederalError as exc:
            log(f"  [warn] {exc}")
    entries = parse_cabinet(read(federal_offices.CABINET_URL))
    held, unknown = assign(entries)
    if unknown:
        raise FederalError("the Cabinet page lists titles the office table does not know: "
                           + "; ".join(unknown))
    votes = senate_votes(cycle.congress_for_date(today), read)
    if votes is None:
        log("  [warn] the Senate's roll-call votes could not be read; the last run's "
            "confirmations are kept")
    before = {o["key"]: o for o in (previous or {}).get("offices") or []}
    offices = []
    for order, office in enumerate(federal_offices.OFFICES, 1):
        entry = held.get(office["key"])
        department = office in federal_offices.DEPARTMENTS
        if entry is None:
            if department:
                problems.append(f"the Cabinet page lists no {office['office']}")
                offices.append({"key": office["key"], "office": office["office"],
                                "body": office["body"], "kind": "department",
                                "order": order, "holder": None})
            continue
        holder = {"name": entry["name"], "title": entry["title"], "photo": entry["photo"],
                  "photoSet": entry.get("photoSet") or []}
        if votes is not None:
            holder["senate"] = confirmation(office, entry["name"], votes)
        else:
            # The Senate's votes could not be read: the last run's finding
            # for the same person stands; for anyone else nothing was looked
            # at, which is not "no roll call found" (rule 19).
            kept = (before.get(office["key"]) or {}).get("holder") or {}
            if same_person(kept.get("name", ""), entry["name"]) and not kept.get("senateUnread"):
                holder["senate"] = kept.get("senate")
            else:
                holder["senate"] = None
                holder["senateUnread"] = True
        holder["page"] = confirm_on_page(office, entry["name"], read)
        offices.append({"key": office["key"], "office": office["office"],
                        "body": office["body"],
                        "kind": "department" if department else "cabinet-level",
                        "order": order if department else None, "holder": holder})
        log(f"  {office['office']}: {entry['name']} - page {holder['page']['status']}, Senate "
            + ("votes not read" if holder.get("senateUnread")
               else (holder.get("senate") or {}).get("vote", "no roll call found")))
    cache = {
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "asOf": today,
        "reviewed": federal_offices.REVIEWED,
        "sources": {"executive": EXECUTIVE_URL, "administration": federal_offices.ADMINISTRATION_URL,
                    "cabinet": federal_offices.CABINET_URL},
        "president": leaders["president"],
        "vicePresident": leaders["vicePresident"],
        "offices": offices,
        "problems": problems,
    }
    # Who has held each office this term (kyc/cabinet.py). Without the
    # Senate's votes, or when Wikidata or Wikipedia cannot be read, the last
    # run's history stands (rule 8).
    from . import cabinet

    cache["changes"] = (previous or {}).get("changes")
    # Only a live run reads Wikidata and Wikipedia: a caller that passes its
    # own reader (a test) must pass history_read as well.
    if votes is not None and (history_read is not None or read is _get):
        try:
            cache["changes"] = cabinet.fetch(cache, votes, read=history_read,
                                             wiki_read=history_read)
        except cabinet.CabinetError as exc:
            log(f"  [warn] {exc}; the last history is kept")
    return cache


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


def problems(cache, today=None):
    """What a build must say about the cache: ``[(level, code, message,
    detail)]``."""
    today = today or datetime.date.today().isoformat()
    if not cache:
        return [("warn", "no-federal", "no federal executive cache; run 'federal'", [])]
    out = []
    for key, title in (("president", "President"), ("vicePresident", "Vice President")):
        person = cache.get(key) or {}
        if not person or not (person.get("termStart", "") <= today < person.get("termEnd", "")):
            out.append(("error", "federal-term-ended",
                        f"the {title}'s term in the cache does not cover {today}; run 'federal'",
                        [person.get("name", "?")]))
    keys = {o["key"] for o in cache.get("offices") or []}
    missing = [o["office"] for o in federal_offices.DEPARTMENTS if o["key"] not in keys]
    if missing:
        out.append(("error", "federal-department-missing",
                    f"{len(missing)} executive departments are not in the cache", missing))
    unlisted = [o["office"] for o in cache.get("offices") or [] if o.get("holder") is None]
    if unlisted:
        out.append(("warn", "federal-office-unlisted",
                    f"{len(unlisted)} departments have no head on the White House's Cabinet page",
                    unlisted))
    unconfirmed = [f"{o['office']}: {o['holder']['name']} ({o['holder']['page'].get('url')})"
                   for o in cache.get("offices") or []
                   if o.get("holder") and o["holder"]["page"]["status"] == "unconfirmed"]
    if unconfirmed:
        out.append(("warn", "federal-page-unconfirmed",
                    f"{len(unconfirmed)} offices' own pages could be read but do not name "
                    f"the White House's holder beside the title; update federal_offices", unconfirmed))
    if cache.get("problems"):
        out.append(("warn", "federal-sources-disagree",
                    f"{len(cache['problems'])} disagreements between federal sources",
                    cache["problems"]))
    return out
