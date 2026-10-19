"""Each sitting federal judge's Wikipedia article and portrait, joined on
ids only (FEDERAL-04, FEDERAL-05).

The chain is two ids, never a name:

1. The Federal Judicial Center's own page for a judge, ``fjc.gov/node/<nid>``
   (the id the directory's files carry), names its canonical address,
   ``fjc.gov/history/judges/<slug>``. That slug is read from the page and
   kept, so a judge's page is opened once.
2. Wikidata's "Biographical Directory of Federal Judges ID" (P2736) is that
   slug. One query reads every item that carries one, with its English
   label, its image (P18) and its English Wikipedia article.

A name search would find a stranger - "Michael Smith" is several judges -
so there is none (rules 24, 32). What the join finds is still checked:

- two Wikidata items carrying one slug name nobody;
- the item's label and the article's title must each contain the judge's
  surname, as the directory spells it (rule 24's ``title_is_about``);
- the item's year of birth (P569) must be the directory's. An id can be
  put on the wrong item: Wikidata carried Judge Robert H. Whaley's FJC id
  (whaley-robert-h) on the basketball player Robert Whaley, born 1982 - the
  judge was born in 1943 - and the surname check passed his photograph
  and article. An item with no year of birth cannot be checked, and gives
  nothing;
- an item with two images, or two articles, gives neither;
- an image must be a photograph Wikimedia can scale (JPEG, PNG, WebP),
  no more than a fifth wider than it is tall (``WIDEST``: the Senate's
  near-square hearing stills pass; a group photograph, a courthouse or a
  16:9 frame is wider), and
  not one ``overrides.NOT_A_PORTRAIT`` lists. Its ``photoSet`` holds only
  Wikimedia's standard sizes of that one file (rule 42).

Everything refused is reported (``problems``) and shown as nothing: a judge
without a portrait or an article is the directory's record alone. A read
that fails keeps the last cache (rule 8); a judge's page that cannot be read
is tried again on the next run.
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
USER_AGENT = "know-your-candidate/2.1 (open-source civic data project)"
# The FJC's pages, a request at a time (rule 37: pace to the source).
NODE_GAP = 1.0
API_GAP = 1.0
PROPERTY = "P2736"   # Biographical Directory of Federal Judges ID
IMAGE = "P18"
BIRTH = "P569"
# The widest a portrait may be, as a multiple of its height.
WIDEST = 1.2

_CANONICAL = re.compile(r'<link rel="canonical" href="https://www\.fjc\.gov/history/judges/'
                        r'([a-z0-9][a-z0-9-]*)"\s*/?>')


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

def read_entities(payload):
    """``{slug: {item: {"label", "images": set, "articles": set}}}`` from a
    ``wbgetentities`` answer. An image is kept in the form Wikidata's query
    service gives it (``Special:FilePath/<name>``), an article as its URL."""
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
        images = {"http://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(v)
                  for v in values(IMAGE) if isinstance(v, str)}
        # The year of birth, as Wikidata's time value writes it
        # ("+1943-04-12T00:00:00Z"); a year it does not know is not one.
        born = {v["time"][1:5] for v in values(BIRTH)
                if isinstance(v, dict) and re.match(r"^\+\d{4}-", v.get("time") or "")}
        site = ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")
        articles = {"https://en.wikipedia.org/wiki/" + urllib.parse.quote(site.replace(" ", "_"))} \
            if site else set()
        for slug in values(PROPERTY):
            if isinstance(slug, str):
                entry = out.setdefault(slug, {}).setdefault(qid, {"label": label, "images": set(),
                                                                  "articles": set(), "born": set()})
                entry["born"] |= born
                entry["images"] |= images
                entry["articles"] |= articles
    return out


def _api(params, read, live):
    url = API_URL + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion="2"))
    for attempt in range(3):
        try:
            text = read(url)
            break
        except urllib.error.HTTPError as exc:
            # A busy API answers 429 and says how long to wait (rule 37).
            wait = exc.headers.get("Retry-After") if exc.headers else None
            if exc.code not in (429, 503) or attempt == 2:
                raise JudgeLinksError(f"Wikidata: {exc}") from exc
            if live:
                time.sleep(min(float(wait) if wait and wait.isdigit() else 30.0, 120.0))
        except OSError as exc:
            raise JudgeLinksError(f"Wikidata: {exc}") from exc
    if live:
        time.sleep(API_GAP)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise JudgeLinksError(f"Wikidata answered with something other than JSON: {exc}") from exc


def _search(query, read, live):
    """Every item Wikidata's search index lists for *query*, page by page."""
    items, offset, total = [], 0, None
    while offset is not None:
        answer = _api({"action": "query", "list": "search", "srnamespace": 0, "srlimit": 500,
                       "srsearch": query, "srprop": "", "sroffset": offset}, read, live)
        found = answer.get("query") or {}
        items += [row["title"] for row in found.get("search") or []]
        total = (found.get("searchinfo") or {}).get("totalhits", total)
        offset = (answer.get("continue") or {}).get("sroffset")
    return sorted(set(i for i in items if re.fullmatch(r"Q\d+", i))), total


def _entities(items, read, live, log=None):
    found = {}
    for i in range(0, len(items), 50):
        answer = _api({"action": "wbgetentities", "ids": "|".join(items[i:i + 50]),
                       "props": "labels|claims|sitelinks", "languages": "en|mul",
                       "sitefilter": "enwiki"}, read, live)
        for slug, by_item in read_entities(answer).items():
            for qid, entry in by_item.items():
                found.setdefault(slug, {})[qid] = entry
        if log and (i // 50) % 20 == 19:
            log(f"    {i + 50} of {len(items)} Wikidata items read")
    return found


def fetch_wikidata(read=None, log=None, wanted=()):
    """``{slug: {item: ...}}`` (:func:`read_entities`) for every item the
    search index lists as carrying an FJC id. The index's paging is not
    exact - one read listed 4,032 of the 4,059 it counted - so each slug in
    *wanted* (the sitting judges') that the listing missed is then looked up
    exactly (``haswbstatement:P2736=<slug>``)."""
    live = read is None
    read = read or _get
    items, _total = _search(f"haswbstatement:{PROPERTY}", read, live)
    found = _entities(items, read, live, log)
    if len(found) < 1000:
        # Every Article III judge since 1789 carries one; a short answer is
        # a failure, not a finding.
        raise JudgeLinksError(f"Wikidata returned {len(found)} FJC ids; expected thousands")
    missed = sorted(set(wanted) - set(found))
    extra = []
    for slug in missed:
        extra += _search(f'haswbstatement:"{PROPERTY}={slug}"', read, live)[0]
    for slug, by_item in _entities(sorted(set(extra) - set(items)), read, live).items():
        for qid, entry in by_item.items():
            found.setdefault(slug, {})[qid] = entry
    if log and missed:
        log(f"    {len(missed)} sitting judges' ids looked up one by one; "
            f"{sum(1 for s in missed if s in found)} found")
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


# ------------------------------------------------------------- the join

def file_page(url):
    """The Commons page of an upload URL: what a portrait credits."""
    return ("https://commons.wikimedia.org/wiki/File:"
            + urllib.parse.quote(urllib.parse.unquote(url.rsplit("/", 1)[-1])))


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


def credit_problem(name, url, credit):
    """Why a Commons file may not be shown with a credit, or ``""``."""
    if not credit or not credit.get("licence"):
        return f"{name}: {url} has no licence recorded on its Commons page; not shown"
    if credit.get("nonFree"):
        return f"{name}: {url} is not a free file (Wikipedia's fair use); not shown"
    return ""


def join(judges, slugs, wikidata, sizes, previous=None, credits=None):
    """``({nid: {"wikidata", "wikipedia"?, "portrait"?}}, problems)``.

    *judges* is ``{id: record}`` (judiciary.json's), *slugs* ``{nid:
    slug}``, *wikidata* :func:`read_wikidata`'s, *sizes* ``{upload url:
    (width, height)}``, *credits* ``{upload url: portraits.credit_of(...)}``
    - a portrait is shown only with its file's author and licence (rule
    87) - and *previous* the last cache's ``judges``. A size that could not
    be read concludes nothing (rule 8): the last portrait read of the same
    file is kept, and a judge whose page was not read keeps the last entry
    whole."""
    from . import overrides
    from .portraits import thumb_set, title_is_about

    out, problems = {}, []
    for judge in judges.values():
        nid = judge.get("nid") or judge["id"].replace("fjc-", "")
        slug = slugs.get(nid)
        if not slug:
            # The FJC page was never read for an id: nothing concluded.
            if (previous or {}).get(nid):
                out[nid] = previous[nid]
            continue
        if slug not in wikidata:
            continue
        items = wikidata[slug]
        name = judge.get("name") or ""
        if len(items) != 1:
            problems.append(f"{name}: {len(items)} Wikidata items carry the FJC id {slug}; none used")
            continue
        (qid, item), = items.items()
        last = surname(judge)
        if not item["label"] or not title_is_about(item["label"], last):
            problems.append(f"{name}: Wikidata {qid} for {slug} is labelled {item['label']!r}; not used")
            continue
        # The id is the join; the year of birth checks the id is on the
        # right item (Robert H. Whaley's was on a basketball player's).
        year = (judge.get("born") or {}).get("year")
        born = item.get("born") or set()
        if not year or year not in born:
            problems.append(f"{name}: Wikidata {qid} for {slug} gives "
                            + (f"a year of birth of {', '.join(sorted(born))}" if born
                               else "no year of birth")
                            + f", the directory {year or 'none'}; not used")
            continue
        entry = {"wikidata": qid}
        if len(item["articles"]) == 1:
            title = article_title(next(iter(item["articles"])))
            if title and title_is_about(title, last):
                entry["wikipedia"] = title
            else:
                problems.append(f"{name}: the article {title!r} does not carry the surname; not linked")
        elif item["articles"]:
            problems.append(f"{name}: {qid} has {len(item['articles'])} English articles; none linked")
        if len(item["images"]) == 1:
            image = next(iter(item["images"]))
            url = commons_url(image)
            size = sizes.get(url) if url else None
            if not url or not thumb_set(url, 1):
                problems.append(f"{name}: {image} is not a photograph Wikimedia scales; not shown")
            elif url in overrides.NOT_A_PORTRAIT:
                problems.append(f"{name}: {url} is in overrides.NOT_A_PORTRAIT; not shown")
            elif not size:
                kept = ((previous or {}).get(nid) or {}).get("portrait")
                if kept and kept.get("source") == file_page(url):
                    entry["portrait"] = kept
                    problems.append(f"{name}: the size of {url} could not be read; "
                                    f"the last portrait read is kept")
                else:
                    problems.append(f"{name}: the size of {url} could not be read; not shown")
            elif size[0] > size[1] * WIDEST:
                problems.append(f"{name}: {url} is wider than a portrait ({size[0]}x{size[1]}); "
                                f"not shown as a portrait")
            elif credit_problem(name, url, (credits or {}).get(url)):
                problems.append(credit_problem(name, url, (credits or {}).get(url)))
            else:
                photo_set = thumb_set(url, size[0])
                entry["portrait"] = dict({
                    "url": photo_set[0][1], "set": photo_set,
                    "credit": "Wikimedia Commons",
                    "source": file_page(url),
                }, **credit_fields(credits[url]))
        elif item["images"]:
            problems.append(f"{name}: {qid} has {len(item['images'])} images; none shown")
        out[nid] = entry
    return out, problems


def files_read(infos):
    """``(sizes, credits)`` from ``{url: imageinfo}`` (``portraits.file_info``)."""
    from .portraits import credit_of
    sizes = {url: (info["width"], info["height"]) for url, info in infos.items()}
    return sizes, {url: credit_of(info) for url, info in infos.items()}


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
                 or entry["portrait"].get("creditForm") != CREDIT_FORM)}
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
            for key in ("by", "authorUnrecorded", "licenceUrl"):
                portrait.pop(key, None)
            portrait.update(credit_fields(credit))
            credited += 1
    return credited, withdrawn


def refresh(judiciary_cache, root=".", read=None, sizes_of=None, log=print, limit=None):
    """Read what is missing and join it; returns the cache written, or
    raises :class:`JudgeLinksError` and leaves the committed one."""
    previous = load_cache(root) or {}
    judges = judiciary_cache["judges"]
    nids = {j.get("nid") or j["id"].replace("fjc-", "") for j in judges.values()}
    slugs, unread = read_slugs(nids, previous.get("slugs"), read=read, log=log, limit=limit)
    # The slugs are kept at once: a Wikidata failure after an hour of the
    # FJC's pages does not cost the next run that hour.
    save_cache(dict(previous, slugs={k: slugs[k] for k in sorted(slugs)}), root)
    wikidata = fetch_wikidata(read, log, wanted={slugs[n] for n in nids if n in slugs})
    wanted = sorted({commons_url(next(iter(i["images"])))
                     for nid in nids if slugs.get(nid) in wikidata
                     for i in wikidata[slugs[nid]].values() if len(i["images"]) == 1} - {None})
    # Each file's size and its credit, from one imageinfo read of its
    # Commons page (one request a batch of fifty, one a second).
    if sizes_of is None:
        from .portraits import file_info
        sizes_of = file_info
    sizes, credits = files_read(sizes_of(wanted))
    joined, problems = join(judges, slugs, wikidata, sizes, previous.get("judges"), credits)
    cache = {"read": datetime.date.today().isoformat(),
             "sources": {"fjc": "https://www.fjc.gov/history/judges",
                         "wikidata": "https://www.wikidata.org/wiki/Property:P2736"},
             "slugs": {k: slugs[k] for k in sorted(slugs) if k in nids},
             "judges": {k: joined[k] for k in sorted(joined)},
             "problems": problems, "unread": unread}
    # A portrait kept from an earlier read without its licence gets one.
    credit_portraits(cache, sizes_of, log)
    save_cache(cache, root)
    return cache


def problems(cache):
    """What a build says about the cache: ``[(level, code, message,
    detail)]`` - every link and portrait the checks withheld, and the
    judges' pages still to be read."""
    if not cache:
        return []
    out = []
    # Rule 87: a Commons portrait shown without its author and licence is
    # the defect the credits fix; run 'judiciary' to read them.
    unlicensed = sorted(nid for nid, entry in (cache.get("judges") or {}).items()
                        if (entry.get("portrait") or {}).get("credit") == "Wikimedia Commons"
                        and not entry["portrait"].get("licence"))
    if unlicensed:
        out.append(("error", "judge-portrait-licence-missing",
                    f"{len(unlicensed)} judges' Wikimedia Commons portraits have no recorded "
                    "licence; run 'judiciary' to read their files' descriptions",
                    [f"FJC {nid}" for nid in unlicensed]))
    if cache.get("problems"):
        out.append(("warn", "judge-links-withheld",
                    f"{len(cache['problems'])} judges' Wikipedia links, Wikidata items or portraits "
                    f"are withheld by the checks in kyc/judge_links.py (read {cache.get('read')})",
                    list(cache["problems"])))
    if cache.get("unread"):
        out.append(("warn", "judge-links-unread",
                    f"{cache['unread']} judges' FJC pages could not be read for their id; "
                    f"'judiciary' tries them again", []))
    return out


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
