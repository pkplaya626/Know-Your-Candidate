"""Each sitting federal judge's Wikipedia article and portrait, joined on
ids only (FEDERAL-04, FEDERAL-05).

The chain is ids, never a name:

1. The Federal Judicial Center's own page for a judge, ``fjc.gov/node/<nid>``
   (the id the directory's files carry), names its canonical address,
   ``fjc.gov/history/judges/<slug>``. That slug is read from the page and
   kept, so a judge's page is opened once. A slug for an accented name is
   percent-encoded (``p%C3%A9rez-myrna``), as Wikidata's copy of it is: the
   first reader took only plain letters, and ten judges' pages read as
   unreadable on every run.
2. Wikidata's "Biographical Directory of Federal Judges ID" (P2736) is that
   slug. One query reads every item that carries one, with its English
   label, its image (P18) and its English Wikipedia article.
3. A judge whose slug no item carries yet - the year's appointees - is
   found through the English Wikipedia article whose ``{{FJC Bio}}``
   template carries their nid: a search on the id, never on a name, whose
   answers are each read and taken only when exactly one carries that very
   nid as its ``nid=`` (the search also finds a list that cites the id). The article's own Wikidata item is then checked like any other,
   and the entry says so (``linkVia``), for the page's note on where the
   links came from. A search that answers no article or several is
   reported; one that fails keeps the judge's last entry (rule 8).

A name search would find a stranger - "Michael Smith" is several judges -
so there is none (rules 24, 32). What the join finds is still checked:

- two Wikidata items carrying one slug name nobody;
- the item's label and the article's title must each contain the judge's
  surname, as the directory spells it (rule 24's ``title_is_about``);
- the year of birth must be the directory's. An id can be put on the wrong
  item: Wikidata carried Judge Robert H. Whaley's FJC id (whaley-robert-h)
  on the basketball player Robert Whaley, born 1982 - the judge was born
  in 1943 - and the surname check passed his photograph and article. The
  item's year (P569) is checked, and the article's where it gives one; an
  item with no year is checked by its article's alone; where they disagree,
  or neither gives one, nothing is used. An article whose ``{{FJC Bio}}``
  names another judge's nid is not this judge's;
- an item with two articles gives neither;
- an image must be a photograph Wikimedia can scale (JPEG, PNG, WebP),
  no more than a fifth wider than it is tall (``WIDEST``: the Senate's
  near-square hearing stills pass; a group photograph, a courthouse or a
  16:9 frame is wider), not one ``overrides.NOT_A_PORTRAIT`` lists - save
  an entry whose only finding is other people in the frame: a hearing
  still's seated rows are not a reason to refuse a judge's portrait, the
  owner's decision of 2026-10-25 (``photos.applies``) - and
  not one whose licence ``overrides.PORTRAIT_LICENCE_DOUBTS`` holds for a
  person to decide. Where the item has no single portrait, one is taken
  only by these routes (the research of 2026-10-19, checked by a second
  reader):

  - an item with two images: the one its own article shows in its
    infobox (Wikidata's preferred rank is no tie-break: Lucy Koh's and
    Sarah Pitlyk's preferred files each depict two people);
  - an item whose image is a wide frame (a Senate hearing still): a crop on
    Commons that says it was extracted from that very file
    (``{{Extracted from}}``) and depicts the item and nothing else (P180).
    A crop without that statement is not taken: Don Willett's depicts a
    microphone, and is cut from a rally photograph with its banner in view;
  - an item with no image: its article's infobox image, where the
    article's lead image (PageImages) is the same file - one source, the
    article, read twice; an article with no lead image gives nothing.

A photograph is used only at sizes Wikimedia itself serves of that one
file (rule 42), up to the widest a page draws (``SHOWN_STEPS``), and only
where the largest kept weighs no more than ``CAP_BYTES`` and is no larger
than ``CAP_PX`` - weighed by reading it, one request a second. A size over
the cap gives way to the next smaller; a file offered only over it is left
out and counted (``oversized``). Nothing is resized here or copied into
the repository.

Each portrait records the route it came by, the evidence that names the
judge beside it, the day it was read and the bytes and pixels of its
largest size; ``problems`` fails one without them. Everything refused is
reported and shown as nothing: a judge without a portrait or an article is
the directory's record alone. A read that fails keeps the last cache
(rule 8); a judge's page that cannot be read is tried again on the next
run, and a portrait whose file could not be measured, weighed or matched
keeps the last one read of the same file. A portrait kept so is asked
again of the overrides (``held_back``), and the build fails any portrait
they withhold.
"""

import datetime
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.error
import urllib.request

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "judge_links.json")
# Wikidata's own API, not its query service: every item carrying the
# property is listed by its search index (haswbstatement), then read fifty
# at a time. The query service answers a whole-property query with 429 for
# minutes at a time.
API_URL = "https://www.wikidata.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia's user-agent policy asks for a way to reach the maker, and its
# image servers refuse a request without one (rule 42).
USER_AGENT = ("know-your-candidate/2.1 (https://github.com/pkplaya626/Know-Your-Candidate; "
              "open-source civic data project)")
# The FJC's pages, a request at a time (rule 37: pace to the source).
NODE_GAP = 1.0
API_GAP = 1.0
# Each photograph's largest size is weighed by reading it, one a second.
WEIGH_GAP = 1.0
PROPERTY = "P2736"   # Biographical Directory of Federal Judges ID
IMAGE = "P18"
BIRTH = "P569"
DEPICTS = "P180"
# The widest a portrait may be, as a multiple of its height.
WIDEST = 1.2
# Wikimedia's standard widths a page can ask for: the officials' dialog
# draws a judge 116px wide, and on a 2x screen KYC.cappedSrcset offers up to
# the first size at least 232px wide. Wider sizes would never be fetched.
SHOWN_STEPS = (120, 250)
# The owner's caps (2026-10-19): a photograph is used only where its source
# offers a size within them.
CAP_BYTES = 300_000
CAP_PX = 1200
FILEPATH = "http://commons.wikimedia.org/wiki/Special:FilePath/"
# What a page shows of a portrait; the rest is the record behind it.
PAGE_KEYS = ("url", "set", "credit", "source", "by", "licence", "licenceUrl", "year",
             "authorUnrecorded", "route")
# What every portrait must carry (rule 87, and the owner's 2026-10-19 rule).
RECORD_KEYS = ("source", "route", "evidence", "read", "bytes", "width", "height")

_CANONICAL = re.compile(r'<link rel="canonical" href="https://www\.fjc\.gov/history/judges/'
                        r'((?:[a-z0-9]|%[0-9A-Fa-f]{2})(?:[a-z0-9-]|%[0-9A-Fa-f]{2})*)"\s*/?>')


class JudgeLinksError(RuntimeError):
    """A source answered with something the reader does not know."""


def _get(url, accept=None, timeout=60):
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


# ------------------------------------------------------------ the FJC's slug

def slug_of(page):
    """The FJC slug a judge's page names as its canonical address, or None."""
    found = set(_CANONICAL.findall(page or ""))
    return found.pop() if len(found) == 1 else None


def slug_key(slug):
    """A slug as one string whichever way it was escaped: the FJC's page
    and Wikidata both write ``p%C3%A9rez-myrna``, but nothing promises it."""
    return urllib.parse.unquote(slug or "")


def read_slugs(nids, known=None, read=None, log=print, gap=NODE_GAP, limit=None):
    """``{nid: slug}``: *known* plus each judge's page not read before. A
    page that cannot be read, or names no single canonical slug, is left for
    the next run (rule 8)."""
    from .judiciary import JUDGE_PAGE

    live = read is None
    read = read or _get
    out = dict(known or {})
    todo = [n for n in sorted(nids) if n not in out]
    if limit is not None:
        todo = todo[:limit]
    unread = 0
    for i, nid in enumerate(todo):
        try:
            slug = slug_of(read(JUDGE_PAGE.format(nid=nid)))
        except Exception as exc:  # noqa: BLE001 - inconclusive, tried again later
            slug = None
            if log:
                log(f"    [warn] {nid}: {exc}")
        if slug:
            out[nid] = slug
        else:
            unread += 1
        if live and i < len(todo) - 1:
            time.sleep(gap)
        if log and (i + 1) % 100 == 0:
            log(f"    {i + 1} of {len(todo)} judges' pages read")
    return out, unread


# ------------------------------------------------------------- Wikidata

def file_name(name):
    """A Commons file's name as Wikidata writes it: spaces, no ``File:``,
    the first letter capital; ``""`` for nothing."""
    name = urllib.parse.unquote(str(name or "")).replace("_", " ").strip()
    name = re.sub(r"^(?:File|Image)\s*:\s*", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name)
    return name[:1].upper() + name[1:]


def file_ref(name):
    """A file in the form Wikidata's query service gives an image
    (``Special:FilePath/<name>``), or None."""
    name = file_name(name)
    return FILEPATH + urllib.parse.quote(name) if name else None


def ref_name(ref):
    """The file name behind a ``Special:FilePath`` form."""
    return file_name(ref[len(FILEPATH):]) if (ref or "").startswith(FILEPATH) else ""


def read_items(payload):
    """``{item: {"label", "images", "articles", "born", "slugs"}}`` from a
    ``wbgetentities`` answer."""
    out = {}
    for qid, entity in ((payload or {}).get("entities") or {}).items():
        if not re.fullmatch(r"Q\d+", qid or "") or entity.get("missing") is not None:
            continue
        claims = entity.get("claims") or {}

        def values(prop):
            return [((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                    for c in claims.get(prop) or [] if c.get("rank") != "deprecated"]

        # English, or the multilingual label Wikidata now keeps a name under
        # when it is the same in every language.
        labels = entity.get("labels") or {}
        label = (labels.get("en") or labels.get("mul") or {}).get("value")
        images = {file_ref(v) for v in values(IMAGE) if isinstance(v, str) and v.strip()}
        # The year of birth, as Wikidata's time value writes it
        # ("+1943-04-12T00:00:00Z"); a year it does not know is not one.
        born = {v["time"][1:5] for v in values(BIRTH)
                if isinstance(v, dict) and re.match(r"^\+\d{4}-", v.get("time") or "")}
        site = ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")
        articles = {"https://en.wikipedia.org/wiki/" + urllib.parse.quote(site.replace(" ", "_"))} \
            if site else set()
        out[qid] = {"label": label, "images": images, "articles": articles, "born": born,
                    "slugs": {v for v in values(PROPERTY) if isinstance(v, str)}}
    return out


def read_entities(payload):
    """``{slug: {item: {"label", "images": set, "articles": set, "born",
    "slugs"}}}`` from a ``wbgetentities`` answer, keyed by :func:`slug_key`.
    An image is kept in the form Wikidata's query service gives it
    (``Special:FilePath/<name>``), an article as its URL."""
    out = {}
    for qid, item in read_items(payload).items():
        for slug in item["slugs"]:
            entry = out.setdefault(slug_key(slug), {}).setdefault(
                qid, dict(item, images=set(), articles=set(), born=set()))
            entry["born"] |= item["born"]
            entry["images"] |= item["images"]
            entry["articles"] |= item["articles"]
    return out


def _api(params, read, live, endpoint=API_URL):
    url = endpoint + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion="2"))
    host = urllib.parse.urlsplit(endpoint).hostname
    for attempt in range(3):
        try:
            text = read(url)
            break
        except urllib.error.HTTPError as exc:
            # A busy API answers 429 and says how long to wait (rule 37).
            wait = exc.headers.get("Retry-After") if exc.headers else None
            if exc.code not in (429, 503) or attempt == 2:
                raise JudgeLinksError(f"{host}: {exc}") from exc
            if live:
                time.sleep(min(float(wait) if wait and wait.isdigit() else 30.0, 120.0))
        except OSError as exc:
            raise JudgeLinksError(f"{host}: {exc}") from exc
    if live:
        time.sleep(API_GAP)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise JudgeLinksError(f"{host} answered with something other than JSON: {exc}") from exc


def _search(query, read, live, endpoint=API_URL, limit=500):
    """Every page a wiki's search index lists for *query*, page by page."""
    items, offset, total = [], 0, None
    while offset is not None:
        answer = _api({"action": "query", "list": "search", "srnamespace": 0, "srlimit": limit,
                       "srsearch": query, "srprop": "", "sroffset": offset}, read, live, endpoint)
        found = answer.get("query") or {}
        items += [row["title"] for row in found.get("search") or []]
        total = (found.get("searchinfo") or {}).get("totalhits", total)
        offset = (answer.get("continue") or {}).get("sroffset")
    return items, total


def _item_search(query, read, live):
    items, total = _search(query, read, live)
    return sorted(set(i for i in items if re.fullmatch(r"Q\d+", i))), total


def fetch_items(qids, read, live, log=None):
    """``{item: ...}`` (:func:`read_items`) for each id, fifty at a time."""
    found = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 50):
        answer = _api({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                       "props": "labels|claims|sitelinks", "languages": "en|mul",
                       "sitefilter": "enwiki"}, read, live)
        found.update(read_items(answer))
        if log and (i // 50) % 20 == 19:
            log(f"    {i + 50} of {len(qids)} Wikidata items read")
    return found


def _entities(items, read, live, log=None):
    found = {}
    for qid, item in fetch_items(items, read, live, log).items():
        for slug in item["slugs"]:
            entry = found.setdefault(slug_key(slug), {}).setdefault(
                qid, dict(item, images=set(), articles=set(), born=set()))
            entry["born"] |= item["born"]
            entry["images"] |= item["images"]
            entry["articles"] |= item["articles"]
    return found


def fetch_wikidata(read=None, log=None, wanted=()):
    """``{slug: {item: ...}}`` (:func:`read_entities`) for every item the
    search index lists as carrying an FJC id. The index's paging is not
    exact - one read listed 4,032 of the 4,059 it counted - so each slug in
    *wanted* (the sitting judges') that the listing missed is then looked up
    exactly (``haswbstatement:P2736=<slug>``), as the FJC writes it and, if
    that finds nothing, unescaped."""
    live = read is None
    read = read or _get
    items, _total = _item_search(f"haswbstatement:{PROPERTY}", read, live)
    found = _entities(items, read, live, log)
    if len(found) < 1000:
        # Every Article III judge since 1789 carries one; a short answer is
        # a failure, not a finding.
        raise JudgeLinksError(f"Wikidata returned {len(found)} FJC ids; expected thousands")
    missed = sorted(s for s in set(wanted) if slug_key(s) not in found)
    extra = []
    for slug in missed:
        hits = _item_search(f'haswbstatement:"{PROPERTY}={slug}"', read, live)[0]
        if not hits and slug_key(slug) != slug:
            hits = _item_search(f'haswbstatement:"{PROPERTY}={slug_key(slug)}"', read, live)[0]
        extra += hits
    for slug, by_item in _entities(sorted(set(extra) - set(items)), read, live).items():
        for qid, entry in by_item.items():
            found.setdefault(slug, {})[qid] = entry
    if log and missed:
        log(f"    {len(missed)} sitting judges' ids looked up one by one; "
            f"{sum(1 for s in missed if slug_key(s) in found)} found")
    return found


def commons_url(image):
    """The upload URL of a Commons file, from Wikidata's
    ``Special:FilePath/<name>`` form; None for anything else."""
    match = re.match(r"^https?://commons\.wikimedia\.org/wiki/Special:FilePath/(.+)$", image or "")
    if not match:
        return None
    name = urllib.parse.unquote(match.group(1)).replace(" ", "_")
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return (f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/"
            + urllib.parse.quote(name, safe="()_-.,'!"))


def article_title(url):
    match = re.match(r"^https://en\.wikipedia\.org/wiki/(.+)$", url or "")
    return urllib.parse.unquote(match.group(1)).replace("_", " ") if match else None


def surname(judge):
    """The judge's surname as the directory's sort name gives it ("Varlan,
    Thomas" -> "Varlan")."""
    sort = judge.get("sortName") or ""
    if "," in sort:
        return sort.split(",")[0].strip()
    words = (judge.get("name") or "").split()
    return words[-1] if words else ""


# ------------------------------------------------------------- the articles

_REFS = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", re.S | re.I)
_YEAR = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")
_BORN_LEAD = re.compile(r"\(\s*born\b[^()]{0,60}?\b(1[89]\d\d|20[0-2]\d)\b", re.I)
# The template's ``nid=`` is the FJC's node id; a positional value is the
# directory's retired judge id ("{{FJC Bio|261|nid=1378271}}"), which the
# first reader took for the nid and refused 82 judges' own articles over.
_FJC_BIO = re.compile(r"\{\{\s*FJC[ _]Bio\b([^{}]*)\}\}", re.I)
_NID = re.compile(r"\|\s*nid\s*=\s*(\d+)", re.I)
_FILE_LINK = re.compile(r"\[\[\s*(?:File|Image)\s*:\s*([^|\]]+)", re.I)
_IMAGE_FILE = re.compile(r"\.(?:jpe?g|png|webp|gif|tiff?|svg)$", re.I)


def article_facts(text):
    """What a judge's article says that the join checks:
    ``{"born": year or None, "image": file name or None, "fjcBio": [nids]}``.

    The year is the infobox's ``birth_date``'s, or the lead's "(born ...
    1964)"; the image is the infobox's own ``image``; the nids are every
    ``{{FJC Bio}}`` the article carries."""
    from .cabinet import infobox

    text = text or ""
    box = infobox(text)
    born = None
    match = _YEAR.search(_REFS.sub("", box.get("birth_date") or ""))
    if match:
        born = match.group(1)
    else:
        lead = _REFS.sub("", re.split(r"\n==", text, maxsplit=1)[0])
        match = _BORN_LEAD.search(lead)
        born = match.group(1) if match else None
    raw = _REFS.sub("", box.get("image") or "").strip()
    linked = _FILE_LINK.search(raw)
    name = file_name((linked.group(1) if linked else raw.split("|")[0].split("\n")[0]).strip())
    return {"born": born, "image": name if _IMAGE_FILE.search(name) else None,
            "fjcBio": sorted({nid for body in _FJC_BIO.findall(text) for nid in _NID.findall(body)})}


def _query(endpoint, params, read, live):
    """``(pages by title, aliases)`` of one ``action=query`` request, with
    every continuation followed and its pages merged."""
    pages, aliases, extra = {}, {}, {}
    for _ in range(50):
        answer = _api(dict(params, action="query", **extra), read, live, endpoint)
        query = answer.get("query") or {}
        for row in (query.get("normalized") or []) + (query.get("redirects") or []):
            aliases[row["from"]] = row["to"]
        for page in query.get("pages") or []:
            have = pages.setdefault(page.get("title"), {})
            for key, value in page.items():
                if isinstance(value, list) and isinstance(have.get(key), list):
                    have[key] = have[key] + value
                elif not have.get(key):
                    have[key] = value
        extra = answer.get("continue") or {}
        if not extra:
            break
    return pages, aliases


def _resolve(title, aliases):
    for _ in range(3):
        title = aliases.get(title, title)
    return title


def _content(page):
    revisions = page.get("revisions") or [{}]
    return ((revisions[0].get("slots") or {}).get("main") or {}).get("content") \
        or revisions[0].get("content") or ""


def read_articles(pages, aliases, titles):
    """``{asked title: {"title", "item", "born", "image", "lead",
    "fjcBio"}}`` from :func:`_query`'s answer; a title the wiki does not
    hold is left out."""
    out = {}
    for asked in titles:
        page = pages.get(_resolve(asked, aliases))
        if not page or page.get("missing") or page.get("invalid"):
            continue
        facts = article_facts(_content(page))
        lead = page.get("pageimage")
        out[asked] = dict(facts, title=page.get("title"),
                          item=(page.get("pageprops") or {}).get("wikibase_item"),
                          lead=file_name(lead) if lead else None)
    return out


def fetch_articles(titles, read, live, log=None, batch=20):
    """:func:`read_articles` for each English Wikipedia title, a batch at a
    time (their text is long)."""
    titles = sorted(set(t for t in titles if t))
    out = {}
    for i in range(0, len(titles), batch):
        chunk = titles[i:i + batch]
        pages, aliases = _query(ENWIKI_API, {
            "titles": "|".join(chunk), "prop": "revisions|pageprops|pageimages",
            "rvprop": "content", "rvslots": "main", "ppprop": "wikibase_item",
            "piprop": "name", "redirects": 1}, read, live)
        out.update(read_articles(pages, aliases, chunk))
        if log and (i // batch) % 20 == 19:
            log(f"    {i + batch} of {len(titles)} articles read")
    return out


def fjc_bio_titles(nid, read, live):
    """The English Wikipedia articles whose ``{{FJC Bio}}`` carries *nid*:
    a search on the id alone, never a name."""
    titles, _ = _search(f'hastemplate:"FJC Bio" insource:"{nid}"', read, live,
                        endpoint=ENWIKI_API, limit=10)
    return titles


# ------------------------------------------------------------- crops

_EXTRACTED = re.compile(r"\{\{\s*Extracted[ _]from\s*\|\s*(?:1\s*=\s*)?([^|}]+)", re.I)


def extracted_from(text):
    """The files a Commons page says it was extracted from."""
    return [file_name(name) for name in _EXTRACTED.findall(_REFS.sub("", text or ""))]


def _depicts(entity):
    statements = entity.get("statements") or entity.get("claims") or {}
    if not isinstance(statements, dict):
        return []
    out = []
    for claim in statements.get(DEPICTS) or []:
        if claim.get("rank") == "deprecated":
            continue
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(value, dict) and value.get("id"):
            out.append(value["id"])
    return out


def fetch_crops(names, read, live, log=None):
    """``{file name: [{"file", "depicts"}]}``: the files on Commons that
    link to each wide frame and say they were extracted from it, with whom
    each depicts (P180, from the file's own structured data). A frame whose
    links were read and that has none is ``[]``."""
    names = sorted(set(n for n in names if n))
    links = {}
    for i in range(0, len(names), 50):
        chunk = names[i:i + 50]
        pages, aliases = _query(COMMONS_API, {
            "titles": "|".join("File:" + n for n in chunk), "prop": "linkshere",
            "lhnamespace": 6, "lhlimit": "max", "lhprop": "title"}, read, live)
        for name in chunk:
            page = pages.get(_resolve("File:" + name, aliases)) or {}
            links[name] = sorted({row["title"] for row in page.get("linkshere") or []})
    linking = sorted({t for ts in links.values() for t in ts})
    said, ids = {}, {}
    for i in range(0, len(linking), 50):
        chunk = linking[i:i + 50]
        pages, aliases = _query(COMMONS_API, {
            "titles": "|".join(chunk), "prop": "revisions", "rvprop": "content",
            "rvslots": "main"}, read, live)
        for title in chunk:
            page = pages.get(_resolve(title, aliases)) or {}
            if page.get("pageid"):
                said[title] = extracted_from(_content(page))
                ids[title] = f"M{page['pageid']}"
    depicts = {}
    wanted = sorted({ids[t] for t, froms in said.items() if froms})
    for i in range(0, len(wanted), 50):
        answer = _api({"action": "wbgetentities", "ids": "|".join(wanted[i:i + 50])},
                      read, live, COMMONS_API)
        for mid, entity in (answer.get("entities") or {}).items():
            depicts[mid] = _depicts(entity)
    out = {}
    for name, titles in links.items():
        out[name] = [{"file": file_name(t), "depicts": depicts.get(ids[t], [])}
                     for t in titles if name in said.get(t, [])]
    if log:
        log(f"    crops: {len(names)} wide frames, "
            f"{sum(len(v) for v in out.values())} files extracted from them")
    return out


# ------------------------------------------------------------- the join

def file_page(url):
    """The Commons page of an upload URL: what a portrait credits."""
    return ("https://commons.wikimedia.org/wiki/File:"
            + urllib.parse.quote(urllib.parse.unquote(url.rsplit("/", 1)[-1])))


def source_url(source):
    """The upload URL of a portrait's Commons page (:func:`file_page`)."""
    if "/wiki/File:" not in (source or ""):
        return None
    return commons_url(file_ref(source.split("/wiki/File:", 1)[1]))


def renditions(url, width):
    """``[[width, url], ...]``: the sizes Wikimedia serves of one file that
    a page can ask for (``SHOWN_STEPS``), smallest first - the original
    itself where it is no wider than the largest of them."""
    from .portraits import thumb_set
    return [step for step in thumb_set(url, width) if step[0] <= SHOWN_STEPS[-1]]


def credit_fields(credit):
    """What a portrait carries of its Commons file's credit (rule 87): the
    author and licence its description page gives, never typed in."""
    from .portraits import CREDIT_FORM

    out = {"licence": credit["licence"], "creditForm": credit.get("form") or CREDIT_FORM}
    if credit.get("by"):
        out["by"] = credit["by"]
    elif credit.get("attribution"):
        # The licence asks for the author; the file's page names none.
        out["authorUnrecorded"] = True
    if credit.get("licenceUrl"):
        out["licenceUrl"] = credit["licenceUrl"]
    return out


def dated(credit):
    """A judge's Commons portrait's year, as its file's page dates it
    (``portraits.year_of``): ``{"year": 2005}``, or ``{"yearUnstated":
    True}`` where the page gives no single four-digit year - then none is
    shown, never guessed. Five of the nine justices' official portraits are
    older than the Court's current ones (Roberts 2005, Thomas 2007, Alito
    2006, Sotomayor 2009, Gorsuch 2017: the photo research of 2026-10-25),
    and a reader should see that a photograph is not new; the owner's brief
    of 2026-10-25 gave every Commons photograph the same year."""
    return {"year": credit["year"]} if credit.get("year") else {"yearUnstated": True}


def credit_problem(name, url, credit):
    """Why a Commons file may not be shown with a credit, or ``""``."""
    if not credit or not credit.get("licence"):
        return f"{name}: {url} has no licence recorded on its Commons page; not shown"
    if credit.get("nonFree"):
        return f"{name}: {url} is not a free file (Wikipedia's fair use); not shown"
    return ""


def _within(weight):
    return (weight.get("bytes") or 0) <= CAP_BYTES and weight.get("width", 0) <= CAP_PX \
        and weight.get("height", 0) <= CAP_PX


def _born_from(born, said):
    return ("Wikidata and the article" if born and said else "Wikidata" if born else "the article")


def held_back(portrait):
    """Why a portrait must not be shown, from the overrides a person keeps,
    or None. Asked of every portrait kept from an earlier read as well as of
    every new one: a doubt added after a file was first read withholds it on
    the next run, whatever that run could read. A judge's portrait is not
    refused for other people in the frame (``photos.applies``, the owner's
    decision of 2026-10-25: "keep" the hearing stills)."""
    from .photos import refused
    return refused(source_url((portrait or {}).get("source")), judge=True) or None


def _keep(last_entry, name, problems):
    """*last_entry* as kept from the last read, without a portrait the
    overrides now withhold (said in *problems*)."""
    entry = dict(last_entry)
    why = held_back(entry.get("portrait"))
    if why:
        del entry["portrait"]
        problems.append(f"{name}: {why}; the kept portrait is not shown")
    return entry


def join(judges, slugs, wikidata, sizes, previous=None, credits=None, articles=None,
         crops=None, bio=None, weights=None, wanted=None, report=None, today=None,
         bio_missed=None):
    """``({nid: {"wikidata", "wikipedia"?, "portrait"?}}, problems)``.

    *judges* is ``{id: record}`` (judiciary.json's), *slugs* ``{nid:
    slug}``, *wikidata* :func:`fetch_wikidata`'s, *sizes* ``{upload url:
    (width, height)}``, *credits* ``{upload url: portraits.credit_of(...)}``
    - a portrait is shown only with its file's author and licence (rule
    87) - *articles* :func:`fetch_articles`' by title, *crops*
    :func:`fetch_crops`', *bio* ``{nid: (item, entry, article title)}`` for
    a judge found through ``{{FJC Bio}}``, *weights* ``{rendition url:
    {"bytes", "width", "height"}}`` and *previous* the last cache's
    ``judges``. A rendition not yet weighed is added to *wanted*. *report*,
    when given, receives ``oversized`` (the judges left out because their
    file is offered only over the caps), ``doubted`` (the
    ``PORTRAIT_LICENCE_DOUBTS`` entries met) and ``notPortraits`` (the
    ``NOT_A_PORTRAIT`` entries met, ``photos.not_a_portrait``). *bio_missed* is ``{nid:
    why}`` for a judge no item carries whose ``{{FJC Bio}}`` search was
    read and settled nothing (no article, or several).

    A size, an article or a weight that could not be read concludes
    nothing (rule 8): the last portrait read of the same file is kept, and
    a judge whose page was not read keeps the last entry whole - as does a
    judge no item carries whose ``{{FJC Bio}}`` search is neither in *bio*
    nor in *bio_missed*, since that search was not read."""
    from . import overrides
    from .photos import not_a_portrait
    from .portraits import thumb_set, title_is_about

    articles, crops, bio = articles or {}, crops or {}, bio or {}
    bio_missed = bio_missed or {}
    weights, credits = weights or {}, credits or {}
    today = today or datetime.date.today().isoformat()
    doubts = getattr(overrides, "PORTRAIT_LICENCE_DOUBTS", {})
    out, problems, oversized, doubted, passed_over = {}, [], [], set(), []
    for judge in judges.values():
        nid = judge.get("nid") or judge["id"].replace("fjc-", "")
        slug = slugs.get(nid)
        last_entry = (previous or {}).get(nid) or {}
        name = judge.get("name") or ""
        if not slug:
            # The FJC page was never read for an id: nothing concluded.
            if last_entry:
                out[nid] = _keep(last_entry, name, problems)
            continue
        items, via = wikidata.get(slug_key(slug)), None
        if items is None:
            if nid in bio_missed:
                problems.append(f"{name}: no Wikidata item carries the FJC id {slug}, and "
                                f"{bio_missed[nid]}; nothing linked")
                continue
            if nid not in bio:
                # The {{FJC Bio}} search was not read: nothing concluded (rule 8).
                problems.append(f"{name}: no Wikidata item carries the FJC id {slug}, and the "
                                f"search for an article whose {{{{FJC Bio}}}} names nid {nid} "
                                "was not read; "
                                + ("the last entry is kept" if last_entry else "nothing linked"))
                if last_entry:
                    out[nid] = _keep(last_entry, name, problems)
                continue
            qid, item, via = bio[nid]
            items = {qid: item}
        if len(items) != 1:
            problems.append(f"{name}: {len(items)} Wikidata items carry the FJC id {slug}; none used")
            continue
        (qid, item), = items.items()
        last = surname(judge)
        if not item["label"] or not title_is_about(item["label"], last):
            problems.append(f"{name}: Wikidata {qid} for {slug} is labelled {item['label']!r}; not used")
            continue
        if via and item.get("slugs"):
            problems.append(f"{name}: Wikidata {qid}, the item of the article carrying their FJC "
                            f"id, carries another FJC id ({', '.join(sorted(item['slugs']))}); not used")
            continue
        title = article = None
        if len(item["articles"]) == 1:
            title = article_title(next(iter(item["articles"])))
            article = articles.get(title)
        elif item["articles"]:
            problems.append(f"{name}: {qid} has {len(item['articles'])} English articles; none linked")
        if via and title != via:
            problems.append(f"{name}: the article carrying {{{{FJC Bio|nid={nid}}}}} is {via!r}, but its "
                            f"item {qid} links {title!r}; not used")
            continue
        if article and article.get("fjcBio") and nid not in article["fjcBio"]:
            problems.append(f"{name}: the article {title!r} carries another judge's FJC id "
                            f"({', '.join(article['fjcBio'])}); not used")
            continue
        # The id is the join; the year of birth checks the id is on the
        # right item (Robert H. Whaley's was on a basketball player's).
        year = (judge.get("born") or {}).get("year")
        born = item.get("born") or set()
        said = (article or {}).get("born")
        if born and (not year or year not in born):
            problems.append(f"{name}: Wikidata {qid} for {slug} gives a year of birth of "
                            f"{', '.join(sorted(born))}, the directory {year or 'none'}; not used")
            continue
        if not born and not said and title and title not in articles:
            # Its article was not read: nothing concluded (rule 8).
            problems.append(f"{name}: Wikidata {qid} for {slug} gives no year of birth and its "
                            f"article {title!r} was not read; "
                            + ("the last entry is kept" if last_entry else "nothing used"))
            if last_entry:
                out[nid] = _keep(last_entry, name, problems)
            continue
        if not born and not said:
            problems.append(f"{name}: Wikidata {qid} for {slug} gives no year of birth"
                            + (", nor does its article" if article else "")
                            + f", the directory {year or 'none'}; not used")
            continue
        if said and said != year:
            problems.append(f"{name}: the article {title!r} gives a year of birth of {said}, "
                            + ("Wikidata " + ", ".join(sorted(born)) + ", " if born else "")
                            + f"the directory {year or 'none'}; not used")
            continue
        entry = {"wikidata": qid}
        if via:
            # The page says how the article was found: by the template that
            # cites this judge's FJC record, not by an item carrying the id.
            entry["linkVia"] = "fjc-bio"
        linked = bool(title) and title_is_about(title, last)
        if title and linked:
            entry["wikipedia"] = title
        elif title:
            problems.append(f"{name}: the article {title!r} does not carry the surname; not linked")

        who = (f"the English Wikipedia article {via!r} carries {{{{FJC Bio|nid={nid}}}}} and "
               f"its Wikidata item is {qid}" if via else
               f"Wikidata {qid} carries the FJC id {slug} of fjc.gov/node/{nid}")
        who += f"; born {year} by {_born_from(born, said)}, as the directory"

        # ---- which file, by which route
        images = sorted(item["images"])
        official = getattr(overrides, "JUSTICE_PORTRAITS", {}).get(nid)
        # The infobox's file, where the article's lead image (PageImages)
        # does not name another; *led* where the lead names this very file.
        art_image = led = None
        if article and linked and article.get("image"):
            if not article.get("lead") or article["lead"] == article["image"]:
                art_image = file_ref(article["image"])
            led = article.get("lead") == article["image"]
        possible = set(images) | ({art_image} if art_image else set())
        for ref in images:
            for crop in crops.get(ref_name(ref)) or []:
                possible.add(file_ref(crop["file"]))
        candidate, why, unsure = None, None, None
        if official:
            # A justice's official portrait as Commons holds it, whatever
            # the item's image is (the owner's decision of 2026-10-20).
            possible.add(file_ref(official[0]))
            candidate = ("official", file_ref(official[0]),
                         f"overrides.JUSTICE_PORTRAITS names this file, by {official[1]}, as "
                         f"{official[3]} (checked {official[2]})")
        elif len(images) == 1:
            ref = images[0]
            url = commons_url(ref)
            size = sizes.get(url) if url else None
            if url and size and size[0] > size[1] * WIDEST:
                if ref_name(ref) not in crops:
                    unsure = f"{name}: {url} is wider than a portrait ({size[0]}x{size[1]}) and its crops were not read"
                else:
                    alone = [c for c in crops[ref_name(ref)] if c["depicts"] == [qid]]

                    def shape(crop):
                        return sizes.get(commons_url(file_ref(crop["file"]))) or (0, 0)
                    shaped = [c for c in alone if shape(c)[0] and shape(c)[0] <= shape(c)[1] * WIDEST]
                    if len(shaped) == 1:
                        candidate = ("crop", file_ref(shaped[0]["file"]),
                                     f"the item's image (P18), {ref_name(ref)!r}, is a wide frame; "
                                     f"this file says it is extracted from it ({{{{Extracted from}}}}) "
                                     f"and depicts {qid} alone (P180)")
                    elif any(not sizes.get(commons_url(file_ref(c["file"]))) for c in alone):
                        unsure = f"{name}: the size of a crop of {url} could not be read"
                    else:
                        why = (f"{name}: {url} is wider than a portrait ({size[0]}x{size[1]}) and "
                               + (f"{len(shaped)} crops of it depict {qid} alone"
                                  if shaped else f"no crop of it depicts {qid} alone")
                               + "; not shown as a portrait")
            else:
                candidate = ("item", ref, "the item's image (P18) is this file")
        elif images:
            if art_image in item["images"]:
                candidate = ("agree", art_image,
                             f"of the item's {len(images)} images (P18) this is the one its article "
                             f"{title!r} shows in its infobox")
            elif title and linked and title not in articles:
                unsure = f"{name}: {qid} has {len(images)} images and its article was not read"
            else:
                why = f"{name}: {qid} has {len(images)} images; none shown"
        elif art_image and led:
            candidate = ("article", art_image,
                         f"the item has no image; its article {title!r} shows this file in its "
                         f"infobox and leads with it")
        elif art_image:
            why = (f"{name}: the item has no image, and its article {title!r} gives no lead "
                   f"image to confirm its infobox's {ref_name(art_image)!r}; not shown")
        elif title and linked and title not in articles:
            unsure = f"{name}: the article {title!r} was not read"

        portrait = None
        if candidate:
            route, ref, how = candidate
            url = commons_url(ref)
            size = sizes.get(url) if url else None
            if not url or not thumb_set(url, 1):
                why = f"{name}: {ref} is not a photograph Wikimedia scales; not shown"
            elif not_a_portrait(url, passed_over=passed_over, judge=True):
                why = f"{name}: {url} is in overrides.NOT_A_PORTRAIT; not shown"
            elif url in doubts:
                doubted.add(url)
                why = (f"{name}: {url} is in overrides.PORTRAIT_LICENCE_DOUBTS "
                       f"({doubts[url][1]}); not shown until a person decides")
            elif not size:
                unsure = f"{name}: the size of {url} could not be read"
            elif size[0] > size[1] * WIDEST:
                why = (f"{name}: {url} is wider than a portrait ({size[0]}x{size[1]}); "
                       f"not shown as a portrait")
            elif credit_problem(name, url, credits.get(url)):
                why = credit_problem(name, url, credits.get(url))
            elif route == "official" and credits[url].get("by") != official[1]:
                # The file is the Court's portrait only as long as Commons
                # still credits whom the entry was checked against.
                why = (f"{name}: Commons names {credits[url].get('by') or 'no author'} as the "
                       f"author of {url}, not {official[1]!r} as overrides.JUSTICE_PORTRAITS "
                       f"recorded on {official[2]}; not shown")
            else:
                steps, kept = renditions(url, size[0]), None
                for i in range(len(steps) - 1, -1, -1):
                    weight = weights.get(steps[i][1])
                    if weight is None:
                        if wanted is not None:
                            wanted.add(steps[i][1])
                        unsure = f"{name}: {steps[i][1]} has not been weighed"
                        break
                    if _within(weight):
                        kept = (steps[:i + 1], weight)
                        break
                if kept:
                    shown, weight = kept
                    portrait = dict({
                        "url": shown[0][1], "set": shown,
                        "credit": "Wikimedia Commons",
                        "source": file_page(url),
                        "route": route, "evidence": f"{who}; {how}", "read": today,
                        "bytes": weight["bytes"], "width": weight["width"],
                        "height": weight["height"], "file": list(size),
                    }, **credit_fields(credits[url]))
                    portrait.update(dated(credits[url]))
                elif not unsure:
                    oversized.append(name)
                    why = (f"{name}: Wikimedia offers {url} only over {CAP_BYTES // 1000} KB or "
                           f"{CAP_PX}px at the sizes a page draws; left out")
        if portrait:
            entry["portrait"] = portrait
        elif unsure:
            kept = last_entry.get("portrait")
            sources = {file_page(commons_url(r)) for r in possible if commons_url(r)}
            if kept and kept.get("evidence") and kept.get("source") in sources \
                    and held_back(kept):
                problems.append(f"{unsure}; the last portrait read, {held_back(kept)}, is not shown")
            elif kept and kept.get("evidence") and kept.get("source") in sources:
                entry["portrait"] = kept
                problems.append(f"{unsure}; the last portrait read is kept")
            else:
                problems.append(f"{unsure}; not shown")
        elif why:
            problems.append(why)
        out[nid] = entry
    if report is not None:
        report["oversized"] = sorted(oversized)
        report["doubted"] = sorted(doubted)
        report["notPortraits"] = sorted(passed_over)
    return out, problems


def files_read(infos):
    """``(sizes, credits)`` from ``{url: imageinfo}`` (``portraits.file_info``)."""
    from .portraits import credit_of
    sizes = {url: (info["width"], info["height"]) for url, info in infos.items()}
    return sizes, {url: credit_of(info) for url, info in infos.items()}


def undated(portrait):
    """A portrait whose Commons year has not been read (``dated``)."""
    return "year" not in portrait and not portrait.get("yearUnstated")


def credit_portraits(cache, info_of=None, log=print):
    """Give each portrait in *cache* that carries no licence its file's
    author and licence, read from the file's Commons page; a portrait whose
    page records none, or that is not a free file, is withdrawn and said.
    Returns ``(credited, withdrawn)``. A file the read did not answer for
    keeps its portrait and is asked about again (rule 8) - ``validate``
    fails it meanwhile, since shown uncredited is the defect (rule 87)."""
    from .portraits import CREDIT_FORM
    if info_of is None:
        from .portraits import file_info as info_of
    judges = (cache or {}).get("judges") or {}
    # A credit read by an earlier form of the reading is read again: the
    # first printed Commons' hidden spans and uploaders' sentences.
    todo = {nid: entry["portrait"] for nid, entry in judges.items()
            if (entry.get("portrait") or {}).get("credit") == "Wikimedia Commons"
            and (not entry["portrait"].get("licence")
                 or entry["portrait"].get("creditForm") != CREDIT_FORM
                 or undated(entry["portrait"]))}
    if not todo:
        return 0, 0
    if log:
        log(f"  judges' portraits: reading {len(todo)} files' licences from Commons ...")
    _, credits = files_read(info_of([p["url"] for p in todo.values()]))
    credited = withdrawn = 0
    for nid, portrait in todo.items():
        credit = credits.get(portrait["url"])
        if credit is None:
            continue
        why = credit_problem(nid, portrait["url"], credit)
        if why:
            del judges[nid]["portrait"]
            cache.setdefault("problems", []).append(why)
            withdrawn += 1
        else:
            for key in ("by", "authorUnrecorded", "licenceUrl", "year", "yearUnstated"):
                portrait.pop(key, None)
            portrait.update(credit_fields(credit))
            portrait.update(dated(credit))
            credited += 1
    return credited, withdrawn


def measure(url, timeout=30):
    """``({"bytes", "width", "height"} or None, retry-after seconds or
    None)`` for one Wikimedia rendition, from its first 64 KB and the total
    its server reports - read again to 512 KB where a JPEG's metadata runs
    past 64 KB before its dimensions (four Northern District of California
    originals do). Wikimedia refuses an image request whose user agent
    names no way to reach its maker ("does not comply with our robot
    policy", HTTP 429): the first full run weighed 102 of 1,055 that way."""
    found, wait = _measure(url, 65535, timeout)
    if found is None and wait is None:
        time.sleep(WEIGH_GAP)
        found, wait = _measure(url, 524287, timeout)
    return found, wait


def _measure(url, span_end, timeout):
    from .portraits import image_size

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Range": f"bytes=0-{span_end}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if not (response.headers.get("Content-Type") or "").startswith("image/"):
                return None, None
            head = response.read(span_end + 1)
            span = response.headers.get("Content-Range") or ""
            total = int(span.rsplit("/", 1)[1]) if "/" in span and span.rsplit("/", 1)[1].isdigit() \
                else int(response.headers.get("Content-Length") or 0) if response.status == 200 else 0
    except urllib.error.HTTPError as exc:
        wait = exc.headers.get("Retry-After") if exc.headers else None
        return None, (float(wait) if wait and wait.isdigit() else 60.0) if exc.code == 429 else None
    except Exception:  # noqa: BLE001 - inconclusive (rule 8)
        return None, None
    size = image_size(head)
    if not total or not size:
        return None, None
    return {"bytes": total, "width": size[0], "height": size[1]}, None


def weigh(urls, log=print, gap=WEIGH_GAP, measure_one=None, trip=5):
    """``{url: {"bytes", "width", "height", "weighed"}}`` for each
    rendition, read one a second; one that could not be read is left out
    and asked about again (rule 8). A 429 waits out its ``Retry-After``;
    after *trip* of them in a row the run stops weighing rather than keep
    the burst going (rule 42)."""
    live = measure_one is None
    measure_one = measure_one or measure
    today = datetime.date.today().isoformat()
    out, refused = {}, 0
    for i, url in enumerate(urls):
        if i and live:
            time.sleep(gap)
        found, wait = measure_one(url)
        if found and found.get("bytes"):
            out[url] = dict(found, weighed=today)
            refused = 0
        elif wait is not None:
            refused += 1
            if refused >= trip:
                if log:
                    log(f"    [warn] Wikimedia refused {trip} in a row; {len(urls) - i - 1} "
                        f"photographs wait for the next run")
                break
            if live:
                time.sleep(min(wait, 120.0))
        if log and (i + 1) % 100 == 0:
            log(f"    {i + 1} of {len(urls)} photographs weighed")
    return out


def _last_weights(previous, sizes):
    """The weights the last cache recorded, for a file whose measured size
    is still the one it had then (a file uploaded again is weighed again)."""
    out = {}
    for entry in ((previous or {}).get("judges") or {}).values():
        portrait = entry.get("portrait") or {}
        if not portrait.get("bytes") or not portrait.get("set") or not portrait.get("file"):
            continue
        original = source_url(portrait.get("source"))
        if original and list(sizes.get(original) or ()) == list(portrait["file"]):
            url = portrait["set"][-1][1]
            out[url] = {"bytes": portrait["bytes"], "width": portrait["width"],
                        "height": portrait["height"]}
    return out


# The most articles one judge's id search may answer and still be read: the
# search matches the id anywhere in a page's source (a list of appointments
# cites it too), and each answer is then read for its own {{FJC Bio|nid=}}.
BIO_TITLES = 5


def find_by_fjc_bio(nids, read, live, log=None):
    """``(answers, missed)``: ``{nid: [article titles]}`` for each judge
    whose id search answered one to ``BIO_TITLES`` articles - which of them
    carries the nid as its ``{{FJC Bio}}``'s ``nid=`` is
    :func:`settle_fjc_bio`'s to say - and ``{nid: why}`` for each it
    answered with none or too many. A search that fails is in neither: it
    concludes nothing for that judge (rule 8), and :func:`join` keeps their
    last entry."""
    out, missed = {}, {}
    for nid in sorted(nids):
        try:
            titles = fjc_bio_titles(nid, read, live)
        except JudgeLinksError as exc:
            if log:
                log(f"    [warn] FJC Bio search for {nid}: {exc}")
            continue
        if 0 < len(titles) <= BIO_TITLES:
            out[nid] = sorted(titles)
        elif titles:
            missed[nid] = (f"{len(titles)} English Wikipedia articles answer the search for "
                           f"{{{{FJC Bio}}}} naming {nid} ({', '.join(sorted(titles)[:4])}, ...)")
        else:
            missed[nid] = f"no English Wikipedia article's {{{{FJC Bio}}}} names nid {nid}"
    if log and nids:
        log(f"    {len(nids)} judges no Wikidata item carries; {len(out)} answered by the "
            f"{{{{FJC Bio}}}} search, {len(missed)} not, {len(nids) - len(out) - len(missed)} not read")
    return out, missed


def settle_fjc_bio(answers, articles, missed):
    """``{nid: (item, title)}`` for each judge exactly one of whose answers,
    as read, carries their nid as its ``{{FJC Bio}}``'s ``nid=`` and has a
    Wikidata item; every other judge's reason goes into *missed*. The
    articles were read (a failed read raises), so what they lack is a
    finding."""
    found = {}
    for nid, titles in answers.items():
        carrying = [t for t in titles if t in articles and nid in articles[t]["fjcBio"]]
        if len(carrying) > 1:
            # A list may cite many judges' records; a judge's own article
            # cites theirs alone. Where two cite only this judge, nobody is
            # chosen: on 2026-10-20 "Donald Trump judicial appointment
            # controversies" cited Justin D. Smith's record alone, beside
            # his own article, and he is reported, not linked.
            alone = [t for t in carrying if articles[t]["fjcBio"] == [nid]]
            carrying = alone if len(alone) == 1 else carrying
        if len(carrying) > 1:
            missed[nid] = (f"{len(carrying)} English Wikipedia articles carry {{{{FJC Bio|nid={nid}}}}} "
                           f"({', '.join(carrying)})")
        elif not carrying:
            missed[nid] = (f"no article the search answered ({', '.join(titles)}) carries "
                           f"{{{{FJC Bio|nid={nid}}}}}")
        elif not articles[carrying[0]].get("item"):
            missed[nid] = (f"the article {carrying[0]!r}, whose {{{{FJC Bio}}}} names nid {nid}, "
                           "has no Wikidata item")
        else:
            found[nid] = (articles[carrying[0]]["item"], carrying[0])
    return found


def refresh(judiciary_cache, root=".", read=None, sizes_of=None, weigh_of=None, log=print,
            limit=None):
    """Read what is missing and join it; returns the cache written, or
    raises :class:`JudgeLinksError` and leaves the committed one."""
    from . import overrides

    previous = load_cache(root) or {}
    live = read is None
    reader = read or _get
    judges = judiciary_cache["judges"]
    nids = {j.get("nid") or j["id"].replace("fjc-", "") for j in judges.values()}
    slugs, unread = read_slugs(nids, previous.get("slugs"), read=read, log=log, limit=limit)
    # The slugs are kept at once: a Wikidata failure after an hour of the
    # FJC's pages does not cost the next run that hour.
    save_cache(dict(previous, slugs={k: slugs[k] for k in sorted(slugs)}), root)
    wikidata = fetch_wikidata(read, log, wanted={slugs[n] for n in nids if n in slugs})
    sitting = {}
    for nid in nids:
        if nid in slugs and slug_key(slugs[nid]) in wikidata:
            sitting.update(wikidata[slug_key(slugs[nid])])
    # A judge whose id no item carries: the article whose {{FJC Bio}} does.
    homeless = sorted(n for n in nids if n in slugs and slug_key(slugs[n]) not in wikidata)
    by_bio, bio_missed = find_by_fjc_bio(homeless, reader, live, log)
    titles = {article_title(a) for i in sitting.values() if len(i["articles"]) == 1
              for a in i["articles"]} | {t for ts in by_bio.values() for t in ts}
    articles = fetch_articles(titles, reader, live, log)
    found = settle_fjc_bio(by_bio, articles, bio_missed)
    items = fetch_items([q for q, _ in found.values()], reader, live)
    bio = {}
    for nid, (q, t) in found.items():
        if q in items:
            bio[nid] = (q, items[q], t)
        else:
            bio_missed[nid] = f"the item of the article {t!r}, {q}, is not on Wikidata"
    # Their items' articles are the same articles, already read.
    everyone = list(sitting.items()) + [(q, i) for q, i, _t in bio.values()]
    # A justice's official portrait, whatever their item's image is.
    refs = {file_ref(entry[0]) for entry in getattr(overrides, "JUSTICE_PORTRAITS", {}).values()}
    for _qid, item in everyone:
        refs |= item["images"]
        for url in item["articles"]:
            facts = articles.get(article_title(url)) or {}
            refs |= {file_ref(facts.get("image")), file_ref(facts.get("lead"))}
    # Each file's size and its credit, from one imageinfo read of its
    # Commons page (one request a batch of fifty, one a second).
    if sizes_of is None:
        from .portraits import file_info
        sizes_of = file_info
    sizes, credits = files_read(sizes_of(sorted({commons_url(r) for r in refs} - {None})))
    # A wide frame: the crops Commons holds of it, and their sizes.
    wide = sorted({ref_name(r) for _q, item in everyone if len(item["images"]) == 1
                   for r in item["images"]
                   if sizes.get(commons_url(r)) and
                   sizes[commons_url(r)][0] > sizes[commons_url(r)][1] * WIDEST})
    crops = {}
    if wide:
        try:
            crops = fetch_crops(wide, reader, live, log)
        except JudgeLinksError as exc:
            if log:
                log(f"    [warn] crops: {exc}; their portraits wait for the next run")
        more = sorted({commons_url(file_ref(c["file"])) for cs in crops.values() for c in cs}
                      - set(sizes) - {None})
        if more:
            extra_sizes, extra_credits = files_read(sizes_of(more))
            sizes.update(extra_sizes)
            credits.update(extra_credits)
    # Each photograph's largest size a page draws, weighed; one over the
    # caps gives way to the next smaller, so a second pass may ask again.
    if weigh_of is None:
        weigh_of = weigh
    weights, tried = _last_weights(previous, sizes), set()
    args = (judges, slugs, wikidata, sizes, previous.get("judges"), credits)
    for _ in range(len(SHOWN_STEPS) + 1):
        wanted = set()
        join(*args, articles=articles, crops=crops, bio=bio, weights=weights, wanted=wanted,
             bio_missed=bio_missed)
        todo = sorted(wanted - set(weights) - tried)
        if not todo:
            break
        if log:
            log(f"    weighing {len(todo)} photographs, one a second ...")
        weights.update(weigh_of(todo))
        tried |= set(todo)
    report = {}
    joined, problems = join(*args, articles=articles, crops=crops, bio=bio, weights=weights,
                            report=report, bio_missed=bio_missed)
    cache = {"read": datetime.date.today().isoformat(),
             "sources": {"fjc": "https://www.fjc.gov/history/judges",
                         "wikidata": "https://www.wikidata.org/wiki/Property:P2736",
                         "wikipedia": "https://en.wikipedia.org/wiki/Template:FJC_Bio",
                         "commons": "https://commons.wikimedia.org/wiki/Template:Extracted_from"},
             "slugs": {k: slugs[k] for k in sorted(slugs) if k in nids},
             "judges": {k: joined[k] for k in sorted(joined)},
             "problems": problems, "unread": unread,
             "oversized": report["oversized"], "doubted": report["doubted"],
             "notPortraits": report["notPortraits"]}
    # A portrait kept from an earlier read without its licence gets one.
    credit_portraits(cache, sizes_of, log)
    save_cache(cache, root)
    return cache


def problems(cache, elsewhere=()):
    """What a build says about the cache: ``[(level, code, message,
    detail)]`` - every link and portrait the checks withheld, the judges'
    pages still to be read, and any portrait shown without its record.
    *elsewhere* is the files other routes reach (a statewide candidate's
    Commons file): a ``PORTRAIT_LICENCE_DOUBTS`` entry one of them stands
    for is not stale."""
    if not cache:
        return []
    from . import overrides

    out = []
    judges = cache.get("judges") or {}
    # Rule 87: a Commons portrait shown without its author and licence is
    # the defect the credits fix; run 'judiciary' to read them.
    unlicensed = sorted(nid for nid, entry in judges.items()
                        if (entry.get("portrait") or {}).get("credit") == "Wikimedia Commons"
                        and not entry["portrait"].get("licence"))
    if unlicensed:
        out.append(("error", "judge-portrait-licence-missing",
                    f"{len(unlicensed)} judges' Wikimedia Commons portraits have no recorded "
                    "licence; run 'judiciary' to read their files' descriptions",
                    [f"FJC {nid}" for nid in unlicensed]))
    # A photograph is shown only with its source page, the evidence naming
    # the judge beside it, the day read and its weight (2026-10-19).
    unrecorded = sorted(nid for nid, entry in judges.items() if entry.get("portrait")
                        and any(entry["portrait"].get(k) in (None, "") for k in RECORD_KEYS))
    if unrecorded:
        out.append(("error", "judge-portrait-unevidenced",
                    f"{len(unrecorded)} judges' portraits carry no route, evidence, day read or "
                    "weight; run 'judiciary' to read them", [f"FJC {nid}" for nid in unrecorded]))
    heavy = sorted(nid for nid, entry in judges.items() if entry.get("portrait")
                   and entry["portrait"].get("bytes") is not None
                   and not _within(entry["portrait"]))
    if heavy:
        out.append(("error", "judge-portrait-heavy",
                    f"{len(heavy)} judges' portraits are over {CAP_BYTES // 1000} KB or {CAP_PX}px",
                    [f"FJC {nid}" for nid in heavy]))
    # A file a person withheld (NOT_A_PORTRAIT, PORTRAIT_LICENCE_DOUBTS)
    # never reaches a page, however the cache came to hold it.
    withheld = sorted(f"FJC {nid}: {held_back(entry['portrait'])}" for nid, entry in judges.items()
                      if entry.get("portrait") and held_back(entry["portrait"]))
    if withheld:
        out.append(("error", "judge-portrait-overridden",
                    f"{len(withheld)} judges' portraits are files the overrides withhold; run "
                    "'judiciary --links-only'", withheld))
    if cache.get("oversized"):
        out.append(("warn", "judge-portraits-oversized",
                    f"{len(cache['oversized'])} judges' photographs left out: Wikimedia offers "
                    f"them only over {CAP_BYTES // 1000} KB or {CAP_PX}px",
                    list(cache["oversized"])))
    if "doubted" in cache:
        stale = sorted(set(getattr(overrides, "PORTRAIT_LICENCE_DOUBTS", {}))
                       - set(cache["doubted"]) - set(elsewhere))
        if stale:
            out.append(("warn", "judge-licence-doubt-stale",
                        f"{len(stale)} overrides.PORTRAIT_LICENCE_DOUBTS entries name no file a "
                        f"judge's route reached (read {cache.get('read')})", stale))
    if cache.get("problems"):
        out.append(("warn", "judge-links-withheld",
                    f"{len(cache['problems'])} judges' Wikipedia links, Wikidata items or portraits "
                    f"are withheld by the checks in kyc/judge_links.py (read {cache.get('read')})",
                    list(cache["problems"])))
    # A justice's official portrait the table names but the read does not
    # hold, as that file credited to that author: the Court's own stands.
    unheld = sorted(f"FJC {nid}: {entry[0]}" for nid, entry
                    in getattr(overrides, "JUSTICE_PORTRAITS", {}).items()
                    if not official_portrait(cache, nid))
    if unheld:
        out.append(("warn", "justice-portrait-unread",
                    f"{len(unheld)} justices' official portraits in overrides.JUSTICE_PORTRAITS "
                    "are not what the judges' read holds, so the Court's own stands; run "
                    "'judiciary --links-only'", unheld))
    if cache.get("unread"):
        out.append(("warn", "judge-links-unread",
                    f"{cache['unread']} judges' FJC pages could not be read for their id; "
                    f"'judiciary' tries them again", []))
    return out


def official_portrait(cache, nid):
    """A sitting justice's official portrait as the judges' read took it from
    Commons (``overrides.JUSTICE_PORTRAITS``): the cached portrait when it is
    that very file and Commons credited the author recorded there, else
    ``None`` - and the Court's own portrait stands."""
    from . import overrides

    official = getattr(overrides, "JUSTICE_PORTRAITS", {}).get(nid)
    portrait = for_judge(cache, nid).get("portrait") or {}
    if not official or not portrait or held_back(portrait):
        return None
    if portrait.get("source") != file_page(commons_url(file_ref(official[0]))):
        return None
    if portrait.get("by") != official[1] or not portrait.get("licence"):
        return None
    return portrait


def for_judge(cache, nid):
    """What the pages show for one judge: ``{"wikidata", "wikipedia"?,
    "portrait"?}`` or ``{}``."""
    return ((cache or {}).get("judges") or {}).get(nid) or {}


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path
