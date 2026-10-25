"""A photograph beside each statewide candidate, where one reaches them by
a route tied to the person (rules 24, 33, 87 and 91).

The state pages and Your ballot listed every candidate for governor,
lieutenant governor, attorney general and secretary of state by name only
(rule 91: no portrait). The owner allowed photographs on 2026-10-19, through
these routes, in this order, and no other:

1. **The holder's office photograph** the site already shows, for the
   candidate the list marks as the office's holder - the same person by
   rule 91's holder test (``statewide.holder_status``: surname and given
   name). Built from the caches, at build time.
2. **A member of Congress's own photograph**, by bioguide id, for a member
   an evidenced ``overrides.OTHER_OFFICE_NOMINEES`` entry puts on that
   office's ballot, where the list's name carries the member's surname and
   given name.
3. **An official guide's photograph**: the Arizona Citizens Clean Elections
   Commission's candidate profiles (each ``<li>`` pairs the picture with the
   candidate's name and office) and California's Official Voter Information
   Guide statements (each block pairs an image whose alt text is the name
   with the heading naming them - paired by block, never by nearness: the
   image comes before the heading, and a parser that took the next image
   gave Rob Bonta Michael Gates's face). Alaska's statements are encrypted
   PDFs and Oregon's pamphlet is JPEG 2000: a copy would have to be made and
   kept, which the owner ruled out, so neither is read.
4. **The race's own Wikipedia article** (``2026 Colorado gubernatorial
   election``, a title built from the race, never a person), the link it
   gives the candidate - matched on surname *and* given name within that
   one race, never a surname alone (Danielle Ford, Nevada, is not Aaron
   Ford, whose article the race page also links), and never a one-word
   name - and then, as rule 33 does for a ballot page's link, the article
   resolved without a section, a disambiguation or a title that is not
   theirs (``portraits.title_is_about``). The photograph is the race page's
   own infobox image beside the nominee, else the article's lead image,
   read with its Commons licence and author (rule 87); refused when it is
   non-free, landscape, its file name lacks the surname or says a scene, or
   it is public domain on no basis but an uploader's say-so (a "PD-author"
   or no PD category at all: the checker found Phillip Ensler's resting on
   an email relayed by Ballotpedia). An editor's crop of a group
   photograph is a person's to refuse (``overrides.COMMONS_NOT_A_PORTRAIT``).

Every photograph is a size its source offers within the caps (the owner's
decision of 2026-10-19: no resizing, no image service, no copy kept): for
Commons, one of Wikimedia's standard thumbnail widths (rule 42). One offered
only above the caps is left out and counted. Each is cached with its page,
the words naming the person beside it, the day read, its bytes and pixel
size (``official_photos.record``); a read that concludes nothing keeps the
last one (rule 8). A cached photograph reaches the page only while the
list still prints the same name for the same office.
"""

import datetime
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse

from . import official_photos

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "statewide_photos.json")
OFFICES = ("governor", "lt", "ag", "sos")

AZ_LIST = "https://www.azcleanelections.gov/Custom/CandidateList?location="
AZ_BY = "Arizona Citizens Clean Elections Commission"
AZ_OFFICES = {"Governor": "governor", "Lieutenant Governor": "lt",
              "Attorney General": "ag", "Secretary of State": "sos"}
CA_GUIDE = "https://voterguide.sos.ca.gov/candidates/{}-candidate-statements.htm"
CA_PAGES = {"governor": "governor", "lt": "lt-governor", "ag": "attorney-general", "sos": "sos"}
CA_BY = "California Secretary of State, Official Voter Information Guide"


class StatewidePhotoError(RuntimeError):
    pass


def key(code, office, name):
    return f"{code}|{office}|{name}"


# ---------------------------------------------------------------- names

def _fold(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _plain_name(text):
    """A name without a bracketed ticket or nickname: "Angela Harrolle Mohan
    (Hourihan)" is Angela Harrolle Mohan; "Donald P. (Don) Wagner" Donald
    P. Wagner."""
    return " ".join(re.sub(r"\([^)]*\)", " ", html.unescape(str(text or ""))).split())


def same_person(list_name, other):
    """Whether *other* names the list's candidate: their surname and their
    given name (or a short form of it), as rule 91 settles a holder. A
    one-word name settles nothing."""
    from . import statewide
    mine = statewide.display_name(list_name)
    if len(statewide.tokens(_plain_name(mine))) < 2 or len(statewide.tokens(_plain_name(other))) < 2:
        return False
    family = statewide.surname(_plain_name(mine))
    return (statewide.has_surname(family, _plain_name(other))
            and statewide.same_given_name(_plain_name(mine), _plain_name(other)))


def matches(candidates, found_name, ticket=None):
    """The one list candidate *found_name* names, or None: unique both ways.
    *ticket* is a running mate's governor the source names beside them
    ("(Hourihan)"), which must be the candidate's own ticket."""
    from . import statewide
    hits = [c for c in candidates if not c.get("writeIn") and same_person(c["name"], found_name)]
    if len(hits) != 1:
        return None
    hit = hits[0]
    if ticket:
        mate = hit.get("runningMate") or ""
        if not mate or not statewide.has_surname(statewide.surname(ticket), mate):
            return None
    return hit


# ------------------------------------------------------- official guides

def _get(url, timeout=40):
    from .courts import _get as get
    try:
        return get(url, timeout=timeout)
    except Exception as exc:                      # CourtsError or anything else
        raise StatewidePhotoError(f"could not read {url}: {exc}") from exc


def parse_arizona(page):
    """``[(office, name, ticket, picture url, words)]`` from the Clean
    Elections Commission's candidate list: each ``<li>`` of the state
    executive's sections pairs ``/Custom/Picture/<n>`` with ``<b>Name</b>``
    and the office. Picture 0 is the commission's silhouette (it answers
    200), so it is no one's photograph."""
    out = []
    for item in re.findall(r"<li>(.*?)</li>", page or "", re.S):
        pic = re.search(r'<img class="pic" src="(/Custom/Picture/(\d+))"', item)
        name = re.search(r"<b>(.*?)</b>", item, re.S)
        office = re.search(r'<span class="office">(.*?)</span>', item, re.S)
        if not (pic and name and office):
            continue
        office_text = " ".join(html.unescape(office.group(1)).split())
        if office_text not in AZ_OFFICES or pic.group(2) == "0":
            continue
        raw = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", name.group(1))).split())
        ticket = re.search(r"\(([^)]+)\)\s*$", raw)
        party = re.search(r'<span class="party">(.*?)</span>', item, re.S)
        words = (f"the list pairs Picture/{pic.group(2)} with '{raw}', '{office_text}'"
                 + (f", '{' '.join(party.group(1).split())}'" if party else ""))
        out.append((AZ_OFFICES[office_text], _plain_name(raw), ticket.group(1) if ticket else None,
                    urllib.parse.urljoin(AZ_LIST, pic.group(1)), words))
    return out


def parse_california(page, office):
    """``[(office, name, None, image url, words)]`` from one of the guide's
    statement pages: each candidate's block holds one image and one
    heading, "Name | PARTY"; the image is taken only where its alt text is
    the heading's name. "No Photo Submitted" is no photograph."""
    out = []
    blocks = re.split(r'<div class="grid-parent clearfix">', page or "")[1:]
    for block in blocks:
        heads = re.findall(r"<h2>(.*?)</h2>", block, re.S)
        imgs = re.findall(r"<img\b[^>]*>", block, re.I)
        if len(heads) != 1 or len(imgs) != 1:
            continue
        head = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", heads[0])).split())
        name = head.split("|", 1)[0].strip()
        alt = official_photos._attr(imgs[0], "alt")
        src = official_photos._attr(imgs[0], "src")
        if not src or "no-photo" in src or alt.strip().lower() == "no photo submitted":
            continue
        if " ".join(alt.split()) != name:
            continue
        url = urllib.parse.urljoin(CA_GUIDE.format(CA_PAGES[office]), src)
        out.append((office, _plain_name(name), None, url,
                    f"the statement's block pairs the image alt-texted '{alt}' with the heading "
                    f"'{head}'"))
    return out


def read_guides(lists, measure=None, pause=1.0, get=None):
    """``(records, problems, unknown)`` for Arizona's and California's
    guides: ``{key: record}`` for each candidate a guide pictures and the
    list names, ``unknown`` the keys a read concluded nothing about."""
    get = get or _get
    measure = measure or official_photos.weigh
    records, problems, unknown = {}, [], set()
    sources = []
    if "AZ" in lists:
        try:
            sources.append(("AZ", AZ_LIST, AZ_BY, parse_arizona(get(AZ_LIST))))
        except StatewidePhotoError as exc:
            problems.append(f"AZ: {exc}; the last photographs read are kept")
            unknown.add("AZ")
    if "CA" in lists:
        for office in OFFICES:
            if office not in lists["CA"]:
                continue
            url = CA_GUIDE.format(CA_PAGES[office])
            time.sleep(pause)
            try:
                sources.append(("CA", url, CA_BY, parse_california(get(url), office)))
            except StatewidePhotoError as exc:
                problems.append(f"CA {office}: {exc}; the last photographs read are kept")
                unknown.add(f"CA|{office}")
    for code, page, by, found in sources:
        for office, name, ticket, url, words in found:
            people = (lists.get(code) or {}).get(office) or []
            hit = matches(people, name, ticket)
            if not hit:
                if people:
                    problems.append(f"{code} {office}: the guide pictures {name!r}, whom the list "
                                    "does not name once; not used")
                continue
            time.sleep(pause)
            chosen, weight, why = official_photos.choose([(0, url)], measure, widest=1.0)
            k = key(code, office, hit["name"])
            if not chosen:
                if why == official_photos.UNKNOWN:
                    unknown.add(k)
                else:
                    problems.append(f"{code} {office}: {hit['name']}'s guide photograph: {why}")
                    records[k] = {"missing": why}
                continue
            records[k] = official_photos.record(chosen, page, f"{by}: {words}", weight,
                                                by=by, route="guide")
    return records, problems, unknown


# ------------------------------------------------------- members by id

def read_members(lists, snapshot, measure=None, pause=1.0):
    """``(records, problems, unknown)`` for members of Congress an
    ``overrides.OTHER_OFFICE_NOMINEES`` entry puts on a statewide ballot:
    their congress.gov portrait, by bioguide id, where the list's name for
    that office is theirs."""
    from .overrides import OTHER_OFFICE_NOMINEES
    from .pages import state_name
    from .photos import HOST_CREDITS, member_photos
    measure = measure or official_photos.weigh
    by_id = {m.get("bioguide"): m for m in (snapshot or {}).get("legislators") or ()}
    records, problems, unknown = {}, [], set()
    titles = {"Governor": "governor", "Lieutenant Governor": "lt", "Attorney General": "ag",
              "Secretary of State": "sos"}
    for bioguide, (what, source, _checked) in sorted(OTHER_OFFICE_NOMINEES.items()):
        member = by_id.get(bioguide)
        found = re.search(r"nominee for (Governor|Lieutenant Governor|Attorney General|"
                          r"Secretary of State) of (?:the )?(.+)$", what)
        if not member or not found:
            continue
        office = titles[found.group(1)]
        code = member.get("state")
        if _fold(state_name(code)).replace("u.s. ", "").replace("united states ", "") != \
                _fold(found.group(2)).replace("u.s. ", "").replace("united states ", ""):
            continue
        people = (lists.get(code) or {}).get(office) or []
        names = [member.get("name") or ""] + [
            f"{member.get('nameParts', {}).get(k)} {member.get('last')}"
            for k in ("first", "nickname") if (member.get("nameParts") or {}).get(k)]
        hits = {c["name"] for c in people if not c.get("writeIn")
                and any(same_person(c["name"], n) for n in names)}
        if len(hits) != 1:
            if people:
                problems.append(f"{code} {office}: {member.get('name')} ({bioguide}) is not named "
                                "once on the list; no photograph")
            continue
        listed = hits.pop()
        url = member_photos(member.get("name"), bioguide)[0]
        time.sleep(pause)
        chosen, weight, why = official_photos.choose([(0, url)], measure, widest=1.0)
        k = key(code, office, listed)
        if not chosen:
            (unknown.add(k) if why == official_photos.UNKNOWN else
             problems.append(f"{code} {office}: {listed}'s portrait by id: {why}"))
            continue
        host = urllib.parse.urlsplit(url).hostname
        records[k] = official_photos.record(
            chosen, f"https://bioguide.congress.gov/search/bio/{bioguide}",
            f"{member.get('name')} ({bioguide}), whom overrides.OTHER_OFFICE_NOMINEES records as "
            f"{what} ({source}); the list prints '{listed}'. The portrait is the member's by "
            "bioguide id.", weight, by=HOST_CREDITS.get(host, host), route="member",
            bioguide=bioguide)
    return records, problems, unknown


# ---------------------------------------------------------- Wikipedia

def race_titles(code, office):
    """The race's own article titles, built from the race (as
    ``results.page_titles`` builds a House race's), never from a person."""
    from .pages import state_name
    place = state_name(code)
    if code == "VI":
        place = "United States Virgin Islands"
    if office == "governor":
        return [f"2026 {place} gubernatorial election"]
    if office == "lt":
        return [f"2026 {place} lieutenant gubernatorial election",
                f"2026 {place} gubernatorial election"]
    if office == "ag":
        return [f"2026 {place} Attorney General election", f"2026 {place} attorney general election"]
    return [f"2026 {place} Secretary of State election", f"2026 {place} secretary of state election"]


_LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")


def _section(text, heading):
    found = re.search(rf"^(=+)\s*{heading}\s*\1\s*$", text, re.M | re.I)
    if not found:
        return ""
    level = len(found.group(1))
    rest = text[found.end():]
    stop = re.search(r"^={1,%d}[^=].*?={1,%d}\s*$" % (level, level), rest, re.M)
    return rest[:stop.start()] if stop else rest


def race_links(text):
    """``[(target, shown, image or None)]``: the race article's candidates
    as it links them - its infobox nominees with the image it sets beside
    each, the general election's result rows, and the bullets under its
    nominee and candidate headings (never the withdrawn or declined)."""
    from .results import template_fields
    out = []
    box = re.search(r"\{\{\s*Infobox election", text or "", re.I)
    if box:
        fields = dict((k.strip().lower(), v.strip()) for k, v in template_fields(
            text[box.start():box.start() + 20000]) if k)
        for name, value in fields.items():
            number = re.fullmatch(r"nominee(\d+)", name)
            if not number:
                continue
            link = _LINK.search(value)
            if link:
                image = fields.get(f"image{number.group(1)}") or ""
                image = re.sub(r"^\[\[(?:File|Image):([^|\]]+).*$", r"\1", image, flags=re.I).strip()
                out.append((link.group(1).strip(), (link.group(2) or link.group(1)).strip(),
                            image or None))
    general = _section(text or "", "General election")
    for match in re.finditer(r"\{\{\s*Election box (?:winning )?candidate[^}]*", general, re.I):
        cand = re.search(r"\|\s*candidate\s*=\s*([^|}\n]+)", match.group(0))
        for link in _LINK.finditer(cand.group(1) if cand else ""):
            out.append((link.group(1).strip(), (link.group(2) or link.group(1)).strip(), None))
    heads = list(re.finditer(r"^(=+)\s*([^=\n]+?)\s*\1\s*$", text or "", re.M))
    for i, head in enumerate(heads):
        title = head.group(2).lower()
        if not re.search(r"nominee|declared|qualified|on the ballot|^candidates$", title) \
                or re.search(r"withdr|declin|elimin|potential|publicly|lost", title):
            continue
        body = text[head.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        for line in re.findall(r"^\*+\s*(.*)$", body, re.M):
            link = _LINK.match(line.strip())
            if link:
                out.append((link.group(1).strip(), (link.group(2) or link.group(1)).strip(), None))
    return out


_SCENE = re.compile(r"\b(?:and|with|at|meeting|rally|ceremony|oath|event|conference|protest|"
                    r"debate|signing|visit|visits|speaks|speaking|group|press|roundtable|hearing|"
                    r"summit|parade|swearing|sworn|inauguration|award|interview|town hall|"
                    r"festival|tour|panel|son|daughter|wife|husband|family|center|pamphlet|"
                    r"page|cup)\b")
_UPLOADER_PD = re.compile(r"^PD[- ](?:author|user|self)", re.I)


def file_ok(file_title, name):
    """Whether a Commons file's own name may be this candidate's portrait:
    it carries their surname and says no scene ("Lt. Governor Susan
    Bysiewicz at Women's History Month panel ... (cropped)")."""
    from . import statewide
    stem = re.sub(r"^File:", "", file_title or "", flags=re.I).rsplit(".", 1)[0]
    if not statewide.has_surname(statewide.surname(_plain_name(name)), stem.replace("_", " ")):
        return False
    return not _SCENE.search(_fold(stem.replace("_", " ")))


def licence_basis(categories):
    """Why a "Public domain" file is public domain, by its categories: a
    government's or a statute's ("PD US Congress", "PD California"), or
    ``None`` when it rests on an uploader's word ("PD-author") or nothing."""
    pd = [c for c in categories if re.match(r"^(?:Category:)?(?:PD|CC-PD)[- ]", c)]
    good = [c for c in pd if not _UPLOADER_PD.match(re.sub(r"^Category:", "", c))]
    return good[0].removeprefix("Category:") if good else None


def _wiki(params):
    from .portraits import _api
    return _api(params)


def _wikitext(title):
    data = _wiki({"prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": title,
                  "redirects": "1"})
    page = ((data.get("query") or {}).get("pages") or [{}])[0]
    if page.get("missing") or not page.get("revisions"):
        return None, None
    return page["title"], page["revisions"][0]["slots"]["main"]["content"]


def _resolve(title):
    data = _wiki({"titles": title, "redirects": "1", "prop": "pageimages|pageprops",
                  "piprop": "name"})
    query = data.get("query") or {}
    page = (query.get("pages") or [{}])[0]
    redirects = query.get("redirects") or []
    return {"title": page.get("title"), "missing": bool(page.get("missing")),
            "fragment": (redirects[-1].get("tofragment") if redirects else None),
            "image": page.get("pageimage"),
            "disambiguation": "disambiguation" in (page.get("pageprops") or {})}


def _commons(file_name):
    """``{"info", "categories"}`` of a file, from Commons' API."""
    from .portraits import _api
    data = _api({"titles": "File:" + file_name, "prop": "imageinfo|categories",
                 "iiprop": "size|url|extmetadata", "cllimit": "max",
                 "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|AttributionRequired|NonFree"},
                endpoint="https://commons.wikimedia.org/w/api.php")
    page = ((data.get("query") or {}).get("pages") or [{}])[0]
    info = (page.get("imageinfo") or [None])[0]
    return {"info": info, "categories": [c["title"] for c in page.get("categories") or []]}


def wiki_photo(code, office, candidate, links, race_title, refused=(), measure=None):
    """``(record, why)`` for one candidate through the race's article
    (*links*, :func:`race_links`)."""
    from .portraits import commons_credit, credit_of, thumb_set, title_is_about
    measure = measure or official_photos.weigh
    name = candidate["name"]
    hits = {}
    for target, shown, image in links:
        if same_person(name, shown) or same_person(name, target.split(" (")[0]):
            hits.setdefault(target, image)
            hits[target] = hits[target] or image
    if len(hits) != 1:
        return None, ("ambiguous" if hits else "not-linked")
    target, infobox_image = next(iter(hits.items()))
    article = _resolve(target)
    resolved = article.get("title") or ""
    if article["missing"] or article["fragment"] or article["disambiguation"] \
            or not title_is_about(resolved, _plain_name(name)) \
            or not same_person(name, resolved.split(" (")[0]):
        return None, "article-not-theirs"
    file_name = infobox_image or article.get("image")
    if not file_name:
        return None, "no-image"
    file_name = urllib.parse.unquote(file_name).replace("_", " ")
    if ("File:" + file_name) in refused:
        return None, "not-a-portrait"
    if not file_ok(file_name, name):
        return None, "file-name"
    meta = _commons(file_name)
    info = meta["info"]
    if not info or not info.get("width"):
        return None, official_photos.UNKNOWN
    credit = credit_of(info)
    if credit.get("nonFree") or not credit.get("licence"):
        return None, "licence"
    basis = None
    if credit["licence"].lower().startswith("public domain"):
        basis = licence_basis(meta["categories"])
        if not basis:
            return None, "public-domain-unsupported"
    if not official_photos.portrait_shaped({"width": info["width"], "height": info["height"]}):
        return None, "shape"
    sizes = [(w, u) for w, u in thumb_set(info.get("url") or "", info["width"])]
    chosen, weight, why = official_photos.choose(sizes, measure)
    if not chosen:
        return None, why
    page = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(race_title.replace(" ", "_"))
    words = (f"The race's article '{race_title}' links [[{target}]] for the list's '{name}'; "
             f"the article '{resolved}' "
             + ("is the nominee's, and the race's infobox sets File:" + file_name + " beside them"
                if infobox_image else "leads with File:" + file_name))
    return official_photos.record(
        chosen, page, words, weight, by=credit.get("by"), route="wikipedia",
        credit=dict(commons_credit(credit), basis=basis) if basis else commons_credit(credit),
        article=resolved), ""


def read_wikipedia(lists, refused=(), measure=None, log=print):
    """``(records, problems, unknown, misses)`` through each race's own
    article, for every printed candidate of every office listed."""
    records, problems, unknown, misses = {}, [], set(), {}
    for code in sorted(lists):
        for office in OFFICES:
            people = (lists[code] or {}).get(office) or []
            if not people:
                continue
            text = title = None
            try:
                for candidate_title in race_titles(code, office):
                    title, text = _wikitext(candidate_title)
                    if text:
                        break
            except Exception as exc:
                problems.append(f"{code} {office}: the race's article could not be read ({exc})")
                unknown.update(key(code, office, p["name"]) for p in people)
                continue
            if not text:
                continue
            links = race_links(text)
            for person in people:
                if person.get("writeIn"):
                    continue
                k = key(code, office, person["name"])
                try:
                    found, why = wiki_photo(code, office, person, links, title, refused, measure)
                except Exception as exc:
                    found, why = None, official_photos.UNKNOWN
                    problems.append(f"{k}: {exc}")
                if found:
                    records[k] = found
                elif why == official_photos.UNKNOWN:
                    unknown.add(k)
                else:
                    misses[k] = why
                    if why == official_photos.OVERSIZED:
                        records[k] = {"missing": why}
            log(f"  {code} {office}: {title}")
    return records, problems, unknown, misses


# -------------------------------------------------------------- the run

def lists_of(statewide_cache):
    """``{code: {office: [candidate]}}`` from the statewide cache."""
    out = {}
    for code, entry in ((statewide_cache or {}).get("states") or {}).items():
        for office, item in ((entry or {}).get("offices") or {}).items():
            out.setdefault(code, {})[office] = list(item.get("candidates") or [])
    return out


def fetch(statewide_cache, snapshot, previous=None, wikipedia=True, log=print):
    """``(cache, problems)``: every route read again. A photograph a read
    concluded nothing about keeps the last one read for the same
    candidate (rule 8)."""
    from .overrides import COMMONS_NOT_A_PORTRAIT
    lists = lists_of(statewide_cache)
    problems = []
    records, more, unknown = read_members(lists, snapshot)
    problems += more
    guides, more, unknown_g = read_guides(lists)
    problems += more
    unknown |= unknown_g
    for k, rec in guides.items():
        records.setdefault(k, rec)
    misses = {}
    if wikipedia:
        wiki, more, unknown_w, misses = read_wikipedia(lists, set(COMMONS_NOT_A_PORTRAIT), log=log)
        problems += more
        unknown |= unknown_w
        for k, rec in wiki.items():
            records.setdefault(k, rec)
    before = (previous or {}).get("photos") or {}
    for k, rec in before.items():
        held = k in unknown or k.rsplit("|", 1)[0] in unknown or k.split("|", 1)[0] in unknown
        if k not in records and held and "photo" in rec:
            records[k] = rec
            problems.append(f"{k}: could not be read; the last photograph read is kept")
        elif not wikipedia and k not in records and rec.get("route") == "wikipedia":
            records[k] = rec
    for k in sorted(set(records) | set(before)):
        was, now = (before.get(k) or {}).get("photo"), (records.get(k) or {}).get("photo")
        if now and was != now:
            problems.append(f"{k}: photograph {'changed' if was else 'added'}: {now} (from "
                            f"{records[k]['page']}); look at it")
    cache = {"read": datetime.date.today().isoformat(),
             "photos": {k: records[k] for k in sorted(records)},
             "misses": {k: misses[k] for k in sorted(misses)}}
    return cache, problems


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def problems(cache):
    """Every cached photograph that lacks what a read one carries: an error
    the build stops on (rule 87)."""
    out = []
    for k, rec in sorted(((cache or {}).get("photos") or {}).items()):
        if "missing" in rec:
            continue
        out.extend(official_photos.record_problems(rec, f"statewide_photos {k}"))
        if not rec.get("by"):
            out.append(f"statewide_photos {k}: the photograph does not say whose it is")
        if rec.get("route") == "wikipedia" and not (rec.get("credit") or {}).get("licence"):
            out.append(f"statewide_photos {k}: a Commons photograph with no recorded licence")
    return out


# ------------------------------------------------------------- the page

def attach(code, office, rows, listed, holder, status, cache):
    """Give each of the page's candidate *rows* (``statewide.for_page``)
    its photograph, in place, by the routes in order. *listed* is the
    cache's office entry (its candidates, by the list's own names);
    *holder* the office's holder as the page shows them; *status* the
    holder line ``statewide.holder_status`` settled. Returns how many were
    left out, offered only above the caps."""
    photos = (cache or {}).get("photos") or {}
    by_shown = {}
    for person in listed.get("candidates") or ():
        from .statewide import display_name
        by_shown.setdefault(display_name(person["name"]), person["name"])
    left_out = 0
    for row in rows:
        if row.get("writeIn"):
            continue
        name = by_shown.get(row["name"])
        if not name:
            continue
        if status and status.get("why") == "listed" and status.get("name") == name and holder:
            field = "headshot" if office == "governor" else "photo"
            if holder.get(field):
                row["photo"] = holder[field]
                row["photoBy"] = holder.get(field + "By") or ""
                if holder.get(field + "Page") or holder.get("photoPage"):
                    row["photoPage"] = holder.get(field + "Page") or holder.get("photoPage")
                row["photoRoute"] = "holder"
                continue
        rec = photos.get(key(code, office, name))
        if not rec:
            continue
        if rec.get("missing") == official_photos.OVERSIZED:
            left_out += 1
            continue
        if "photo" not in rec or official_photos.record_problems(rec, name):
            continue
        row["photo"] = rec["photo"]
        row["photoRoute"] = rec.get("route")
        if rec.get("route") == "wikipedia":
            row["photoCredit"] = rec.get("credit")
        else:
            row["photoBy"] = rec.get("by")
            row["photoPage"] = rec.get("page")
    return left_out
