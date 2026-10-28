"""Fill the gaps on the people still running in November.

Most filed candidates arrive with nothing but a name, a party and a dollar
figure. Two sources can say more, and each is tied to the person by something
the pipeline already holds rather than by a search on a name (rules 24, 32,
33):

* The candidate's **Wikipedia article**, where the state's election page links
  one from the ballot line. Its infobox gives a birth date, education and
  occupation, and the resolved title must still name the person.
* The candidate's **campaign website**, from their committee's own FEC Form 1
  or the election page's "Campaign websites" list. What the site says the
  campaign is about, the headings of its issues page, and a portrait only when
  the image is named for the candidate.

Nothing is summarised or paraphrased: what reaches the page is the source's
own words, credited to it. A site that does not name the candidate on the
page, or reads as parked or hijacked, is not used - and a committee site that
reads as hijacked or parked is withdrawn from the profile and reported,
because a lapsed campaign domain linked under a candidate's name is how seven
profiles ended up pointing at gambling pages (rule 35). Every committee site
linked for anyone still in a race is read, members' included; it is the only
thing that notices a domain lapse between one person's look and the next.
"""

import collections
import datetime
import html
import html.parser
import http.cookiejar
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

from . import overrides
from .legislators import age_on
from .normalize import fill_field, looks_like_date
from .photos import campaign_credit, lighter_rendition, parse_srcset, too_heavy
from .photos import not_a_portrait
from .photos import refused as withheld_by_a_person
from .portraits import article_is_theirs, image_size, surname_of, title_is_about
from .results import OFF_BALLOT

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "enrichment.json")

_UA_WEB = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0 Safari/537.36 "
                   "know-your-candidate/2.1 (open-source civic data project)"),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    # Brotli needs a third-party package; ask for what the standard library reads.
    "Accept-Encoding": "gzip, deflate",
}
_TIMEOUT = 20
MAX_BODY = 1_500_000
MAX_TEXT = 200_000
# The refresh runs Mondays and Thursdays: six days makes every Monday run
# re-read what the previous Monday read, so a lapsed domain waits a week at most.
STALE_DAYS = 6

# Site verdicts. ``None`` - could not tell - is the third state (rule 8).
SAFE, REFUSED = True, False
HIJACKED = "reads as hijacked"
PARKED = "reads as parked or expired"
UNNAMED = "does not name the candidate"
ELSEWHERE = "is about something else"
UNBUILT = "is a placeholder: coming soon"
# Linked, but worth a person's attention: the campaign's own page, with
# gambling links hidden in it by whoever compromised the site.
COMPROMISED = "hides gambling links in its page"


def running(profile):
    """A challenger still in the race: on the November ballot, or not yet
    decided (Louisiana's open primary is on Election Day itself)."""
    return bool(profile.get("isCandidate")) and profile.get("raceStatus") not in OFF_BALLOT


def checked_site(profile):
    """Anyone still in the race whose committee site is linked: members too,
    because a lapsed domain is a hazard whoever it was filed for."""
    return bool(profile.get("campaignSite")) and profile.get("raceStatus") not in OFF_BALLOT


def fold(text):
    normal = unicodedata.normalize("NFD", str(text or "").replace("\u2019", "'"))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _words(text):
    return re.findall(r"[a-z0-9]+", fold(text))


# ------------------------------------------------------------------ Wikipedia

_BIRTH = re.compile(
    r"\{\{\s*(?:birth[ _-]date(?:[ _]and[ _]age)?|bda|dob)\s*"
    r"(?:\|\s*[a-z]+\s*=[^|}]*)*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\b", re.I)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_LIST_TEMPLATE = re.compile(
    r"\{\{\s*(?:ubl|unbulleted[ _]list|plain[ _]?list|flat[ _]?list|hlist|bulleted[ _]list)"
    r"\s*\|([^{}]*)\}\}", re.I)
_NOWRAP = re.compile(r"\{\{\s*(?:nowrap|small|nobr|nbsp)\s*\|([^{}]*)\}\}", re.I)
_REFS = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", re.S | re.I)
_PIPED = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")


def infobox(wikitext):
    """``{param: raw value}`` of the article's first Infobox template."""
    from .results import template_fields

    text = wikitext or ""
    start = re.search(r"\{\{\s*Infobox", text, re.I)
    if not start:
        return {}
    depth, i = 0, start.start()
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i):
            depth -= 1
            i += 2
            if depth == 0:
                break
        else:
            i += 1
    return template_fields(text[start.start() + 2:i - 2])


def birth_date(value):
    """An ISO date from an infobox ``birth_date``, or ``""``.

    A year alone (``{{birth year and age|1975}}``) is not taken: the age it
    implies is wrong for part of every year.
    """
    value = _REFS.sub("", value or "")
    m = _BIRTH.search(value)
    if m:
        y, mo, d = m.groups()
        iso = f"{y}-{int(mo):02d}-{int(d):02d}"
    else:
        m = _ISO_DATE.search(value)
        iso = m.group(0) if m else ""
    if not iso or not looks_like_date(iso):
        return ""
    try:
        datetime.date.fromisoformat(iso)
    except ValueError:
        return ""
    return iso


def list_text(value):
    """An infobox list (ubl, plainlist, ``<br>``) as ``"; "``-joined text."""
    from .results import plain_text

    v = _REFS.sub("", value or "")
    v = _PIPED.sub(r"\1", v)
    v = _NOWRAP.sub(r"\1", v)
    v = re.sub(r"<br\s*/?>", "\n", v, flags=re.I)
    v = _LIST_TEMPLATE.sub(lambda m: "\n".join(m.group(1).split("|")), v)
    parts = []
    for line in re.split(r"\n+|\s*;\s*", v):
        text = plain_text(line.strip().lstrip("*#").strip())
        if len(text) > 1 and text.lower() not in (p.lower() for p in parts):
            parts.append(text)
    return "; ".join(parts)[:240].rstrip("; ")


def wiki_facts(wikitext):
    """``{born, education, occupation}`` from an article's infobox."""
    box = infobox(wikitext)
    facts = {}
    born = birth_date(box.get("birth_date", ""))
    if born:
        facts["born"] = born
    education = list_text(box.get("alma_mater") or box.get("education") or "")
    if education:
        facts["education"] = education
    occupation = list_text(box.get("occupation") or box.get("profession") or "")
    if occupation:
        facts["occupation"] = occupation
    return facts


def fetch_articles(titles, log=print):
    """``{requested title: (resolved title, wikitext)}``, 50 titles a request.

    Through the portrait resolver's client, which serialises calls and backs
    off on 429. A batch that still fails is reported and skipped: nothing is
    concluded about the people in it.
    """
    from .portraits import _api

    out = {}
    titles = list(dict.fromkeys(t for t in titles if t))
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        params = {"prop": "revisions", "rvprop": "content", "rvslots": "main",
                  "redirects": "1", "titles": "|".join(batch)}
        back = {}
        while True:
            try:
                data = _api(params)
            except Exception as exc:
                log(f"    [warn] Wikipedia batch of {len(batch)} failed: {exc}")
                break
            query = data.get("query") or {}
            for hop in (query.get("normalized") or []) + (query.get("redirects") or []):
                back[hop["to"]] = back.get(hop["from"], hop["from"])
            for page in query.get("pages") or []:
                revisions = page.get("revisions") or []
                if page.get("missing") or page.get("invalid") or not revisions:
                    continue
                main = (revisions[0].get("slots") or {}).get("main") or {}
                out[back.get(page["title"], page["title"])] = (
                    page["title"], main.get("content") or "")
            more = data.get("continue")
            if not more:
                break
            params = dict(params, **more)
    return out


# Titles that are about a topic, not a person: a list, an election, a party.
_TOPIC_TITLE = re.compile(
    r"^(?:list of|\d{4}\b)|\belections?\b|\bprimar(?:y|ies)\b|\bparty\b|\bcaucus(?:es)?\b",
    re.I)


def link_targets(titles, log=print):
    """``{title: {"to": title it lands on, "fragment": section or None,
    "living": in Category:Living people}}``.

    Where a Wikipedia title actually leads, through every redirect; a title
    with no article is ``{"missing": True}``. A batch that fails is reported
    and skipped: nothing is concluded about the titles in it (rule 8).
    """
    from .portraits import _api

    out = {}
    titles = list(dict.fromkeys(t for t in titles if t))
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        try:
            data = _api({"prop": "info|categories", "redirects": "1",
                         "clcategories": "Category:Living people", "cllimit": "max",
                         "titles": "|".join(batch)})
        except Exception as exc:
            log(f"    [warn] Wikipedia batch of {len(batch)} titles failed: {exc}")
            continue
        query = data.get("query") or {}
        back, fragment = {}, {}
        for hop in query.get("normalized") or []:
            back[hop["to"]] = back.get(hop["from"], hop["from"])
        for hop in query.get("redirects") or []:
            origin = back.get(hop["from"], hop["from"])
            back[hop["to"]] = origin
            if hop.get("tofragment"):
                fragment[origin] = hop["tofragment"]
        for page in query.get("pages") or []:
            if page.get("invalid"):
                continue
            origin = back.get(page["title"], page["title"])
            if page.get("missing"):
                out[origin] = {"missing": True}
            else:
                out[origin] = {"to": page["title"], "fragment": fragment.get(origin),
                               "living": bool(page.get("categories"))}
    return out


def link_is_about(target, name, alias=None):
    """True when a linked title leads to an article about this person: not
    to a section of another article, not to a list, election or party
    article, and to a title carrying their surname. "Brian McGinnis" leads
    to "Protests against the 2026 Iran war#Washington D.C.", "Elijah
    Manley" to "2016 Green Party presidential primaries", and "John Cowan
    (Georgia politician)" to the district's section of the state's 2026
    House elections article; one candidate's link was the Cascade Party of
    Washington's own article. A title without the surname is theirs only as
    *alias*, an evidenced ``overrides.ARTICLE_UNDER_ANOTHER_NAME`` entry
    ("Luther Campbell" redirects to "Uncle Luke"): being a living person's
    article is not enough, since a redirect to a spouse or a namesake is
    one too."""
    if not target or target.get("missing") or target.get("fragment"):
        return False
    title = target.get("to") or ""
    return (bool(title) and not _TOPIC_TITLE.search(title)
            and (title_is_about(title, name) or (alias is not None and title == alias)))


# ---------------------------------------------------------------- campaign site

class _Page(html.parser.HTMLParser):
    """Title, a few meta tags, images, links, headings and text of one page."""

    _HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
    _SKIP = ("script", "style", "noscript", "template", "svg")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.meta, self.images, self.links, self.headings = "", {}, [], [], []
        # Each image's own srcset, by its src: the renditions the page
        # itself offers of it (photos.lighter_rendition).
        self.srcsets = {}
        self.text, self._size = [], 0
        self._open, self._buffer, self._href, self._skip = None, [], None, 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "title" and not self.title:
            self._open, self._buffer = "title", []
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("description", "og:description", "og:image", "og:title",
                       "twitter:image", "twitter:description"):
                self.meta.setdefault(key, a.get("content", ""))
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or a.get("data-lazy-src") or ""
            self.images.append((src, a.get("alt", "")))
            srcset = a.get("srcset") or a.get("data-srcset") or a.get("data-lazy-srcset")
            if src and srcset:
                self.srcsets.setdefault(src, srcset)
        elif tag == "a":
            self._open, self._buffer, self._href = "a", [], a.get("href", "")
        elif tag in self._HEADINGS:
            self._open, self._buffer = tag, []

    def handle_data(self, data):
        if self._skip:
            return
        if self._open:
            self._buffer.append(data)
        if self._size < MAX_TEXT:
            self.text.append(data)
            self._size += len(data)

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(self._skip - 1, 0)
            return
        if self._open != tag:
            return
        text = " ".join("".join(self._buffer).split())
        if tag == "title":
            self.title = text
        elif tag == "a":
            self.links.append((self._href, text))
        else:
            self.headings.append((tag, text))
        self._open = None

    @property
    def body(self):
        return " ".join(" ".join(self.text).split())


# Text a visitor never sees: where a compromised site keeps its spam.
_HIDDEN = re.compile(
    r"<(div|span|p|section)\b[^>]*\bstyle\s*=\s*([\"'])[^\"']*?"
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden|(?:left|top)\s*:\s*-\d{3,}px|"
    r"height\s*:\s*[01]px|font-size\s*:\s*0)[^\"']*\2[^>]*>(.*?)</\1\s*>", re.I | re.S)


def parse_page(markup):
    """The page as a visitor sees it; ``.hidden`` holds the text they do not."""
    markup = markup or ""
    hidden = [m.group(3) for m in _HIDDEN.finditer(markup)]
    page = _Page()
    try:
        page.feed(_HIDDEN.sub(" ", markup) if hidden else markup)
        page.close()
    except Exception:            # a malformed page still yields what it had
        pass
    page.hidden = " ".join(re.sub(r"<[^>]+>", " ", h) for h in hidden)
    page.small = markup if len(markup) < 20000 else ""
    return page


def host_of(url):
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _decoded(raw, encoding):
    """The body undone from gzip or deflate; ``None`` for anything else."""
    encoding = (encoding or "identity").lower().strip()
    if encoding == "identity":
        return raw
    if encoding in ("gzip", "x-gzip", "deflate"):
        for wbits in ((16 + zlib.MAX_WBITS,) if "gzip" in encoding
                      else (zlib.MAX_WBITS, -zlib.MAX_WBITS)):
            try:
                # A decompressor object tolerates the cut-off end of a body
                # read only up to MAX_BODY.
                return zlib.decompressobj(wbits).decompress(raw)
            except zlib.error:
                continue
    return None


_SCRIPT_REDIRECT = re.compile(
    r"(?:window\.|document\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"']|"
    r"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[\"']?[^>]+url\s*=\s*([^\"'>\s]+)", re.I)


def fetch(url, hops=2):
    """``(final url, HTTP status or None, markup)``; never raises.

    Cookies are kept across redirects: some sites set one and bounce the
    visitor back, which is a loop without them. A redirect chain urllib gives
    up on, and a page that does nothing but send the browser elsewhere in
    script, are followed by hand a couple of hops - a parked domain's page is
    a one-line script to "/lander", and a hijacked one is a chain of 301s to
    a gambling site.
    """
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    try:
        req = urllib.request.Request(url, headers=_UA_WEB)
        with opener.open(req, timeout=_TIMEOUT) as response:
            final, status = response.geturl(), response.status
            if "html" not in (response.headers.get("Content-Type") or "html"):
                return final, status, ""
            raw = _decoded(response.read(MAX_BODY), response.headers.get("Content-Encoding"))
            if raw is None:
                return final, None, ""       # an encoding we cannot read: no verdict
            charset = response.headers.get_content_charset() or "utf-8"
            markup = raw.decode(charset, "replace")
    except urllib.error.HTTPError as exc:
        final = getattr(exc, "url", None) or url
        where = exc.headers.get("Location") if exc.headers else None
        if 300 <= exc.code < 400 and where and hops:
            return fetch(urllib.parse.urljoin(final, where), hops - 1)
        return final, exc.code, ""
    except Exception:
        return url, None, ""
    if len(markup) < 3000 and hops:
        jump = _SCRIPT_REDIRECT.search(markup)
        if jump:
            target = urllib.parse.urljoin(final, (jump.group(1) or jump.group(2)).strip())
            if target.startswith("http") and target.rstrip("/") != final.rstrip("/"):
                return fetch(target, hops - 1)
    return final, status, markup


# Words no campaign uses - the spam that fills a lapsed domain.
_SPAM = re.compile(r"slot\s*gacor|situs\s+(?:slot|judi|toto)|\btogel\b|\bjudi\s+(?:online|bola|slot)|"
                   r"\bsbobet\b|\bmaxwin\b|\brtp\s+(?:live|slot)|\bbandar\s+(?:togel|judi|bola)|"
                   r"\bslot\s+(?:online|dana|thailand|depo)\b", re.I)
# Words a campaign might use once, which a hijacked page uses everywhere.
_GAMBLING = re.compile(r"\b(?:online\s+casinos?|casino\s+online|sportsbooks?|poker\s+online|"
                       r"free\s+spins|no[\s-]deposit\s+bonus|betting\s+sites?|slots?\s+games?|"
                       r"best\s+casinos?|casino\s+(?:bonus|reviews?))\b", re.I)
_PARKED = re.compile(r"domain\s+(?:name\s+)?(?:is|may\s+be)\s+for\s+sale|buy\s+this\s+domain|"
                     r"hugedomains|sedoparking|afternic|parkingcrew|bodis\.com|domain\s+parking|"
                     r"website\s+(?:has\s+)?expired|site\s+(?:is\s+)?not\s+(?:yet\s+)?connected|"
                     r"connect\s+your\s+domain|account\s+(?:has\s+been\s+)?suspended|"
                     r"this\s+domain\s+(?:has\s+been\s+)?registered|"
                     r"future\s+home\s+of\s+something", re.I)
# The machinery of a parking page, in its markup rather than its words.
# privacykeeper: trevordforme.com's parking chain sent one browser on
# 2026-10-17 to a "Security Check" page offering a software download.
_PARKING_CODE = re.compile(r"parking-lander|LANDER_SYSTEM|sedoparking|parkingcrew|bodis\.com|"
                           r"park\.godaddy|domainmarket|dan\.com/|privacykeeper", re.I)
_UNBUILT = re.compile(r"\b(?:coming\s+soon|under\s+construction|check\s+back\s+soon|"
                      r"launching\s+soon)\b", re.I)
_GENERATIONAL = {"jr", "sr", "ii", "iii", "iv", "v"}


def names_candidate(profile, text, host):
    """Does this text name the candidate?

    The surname, as a word; or, for a filing in three names, the middle one
    ("Darline Graham Nordone" campaigns as Darline Graham); or the first name
    when the site's own address carries it too - "Kristi for Congress" at
    votekristiburke.com, "Meet Grace" at gracefornewyork.com.
    """
    seen = fold(text)
    surname = fold(surname_of(profile["name"]))
    if surname and re.search(r"(?<![a-z0-9])" + re.escape(surname) + r"(?![a-z0-9])", seen):
        return True
    names = [w for w in _words(profile["name"]) if w not in _GENERATIONAL]
    words = set(_words(seen))
    if len(names) >= 3 and len(names[-2]) > 2 and names[-2] in words:
        return True
    first = names[0] if names else ""
    return len(first) >= 4 and first in words and first in host.replace("-", "")


def assess(profile, url, final, status, page):
    """``(verdict, reason)``: may this page stand for the candidate's campaign?

    ``None`` - inconclusive - when the site could not be reached, turned the
    request away (a bot wall answers 403, or 202 with a JavaScript challenge,
    to a perfectly good site), or shows too little text to say; nothing is
    concluded from that (rule 8).
    """
    if status is None:
        return None, "unreachable"
    if status in (401, 403, 429) or status >= 500 or 200 < status < 300:
        return None, f"HTTP {status}"
    if 300 <= status < 400:
        return REFUSED, f"redirects in a loop through {host_of(final)}"
    if status >= 400:
        return REFUSED, f"HTTP {status}"
    head = " ".join([page.title] + [page.meta.get(k, "") for k in
                     ("description", "og:description", "og:title")]
                    + [h for t, h in page.headings if t in ("h1", "h2")])
    body = page.body
    if (_SPAM.search(head) or _SPAM.search(body) or _GAMBLING.search(head)
            or len(_GAMBLING.findall(body)) >= 5):
        return REFUSED, HIJACKED
    if (_PARKED.search(head) or (len(body) < 2000 and _PARKED.search(body))
            or _PARKING_CODE.search(page.small)):
        return REFUSED, PARKED
    text = " ".join([head, body, page.hidden] + [h for _, h in page.headings])
    # On the page, not in the address: a lapsed "janesmith2026.com" still has
    # her name in it.
    if not names_candidate(profile, text, host_of(final)):
        if _UNBUILT.search(head + " " + body[:2000]):
            return REFUSED, UNBUILT
        if len(body) < 200:
            return None, "too little text to tell"
        return REFUSED, ELSEWHERE if len(body) >= 500 else UNNAMED
    if _SPAM.search(page.hidden) or _GAMBLING.search(page.hidden):
        return SAFE, COMPROMISED
    if host_of(final) != host_of(url):
        return SAFE, f"moved to {host_of(final)}, still names the candidate"
    return SAFE, "ok"


_FILLER = set("""
    a an and as at be by for from he her his i in is it its me my of on or our she so
    that the their they this to us we who will with you your
    are was were has have had not but all more most can just been into out up about
    than then them these those what when where which while why how also very every
    each any some such only own same other there here now get let
    official website web site campaign home page elect vote re congress congressional
    senate house representative representatives district state committee welcome
    candidate running run nominee seat seeking republican democrat democratic
    independent progressive conservative u s rep sen
    alabama alaska arizona arkansas california colorado connecticut delaware florida
    georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland
    massachusetts michigan minnesota mississippi missouri montana nebraska nevada new
    hampshire jersey mexico york carolina north south dakota ohio oklahoma oregon
    pennsylvania rhode island tennessee texas utah vermont virginia washington west
    wisconsin wyoming
""".split())
_BOILERPLATE = re.compile(
    r"just another wordpress|coming soon|under construction|lorem ipsum|paid for by|"
    r"cookie|javascript|your browser|skip to (?:main )?content|log ?in|sign ?in|"
    r"page not found|\b404\b", re.I)


# A sentence that asks for something rather than saying anything.
_CALL = re.compile(r"^(?:learn\s+(?:more|about)|get\s+involved|join\b|sign\s+up|donate|"
                   r"visit\b|click\b|follow\b|chip\s+in|contribute|volunteer|stay\b|"
                   r"subscribe|explore\b|find\s+(?:out|your)|please\b|see\b)", re.I)
_ASKING = re.compile(r"\b(?:donat(?:e|ion)|get\s+involved|join\s+(?:us|our|the)\b|sign\s+up|"
                     r"connect\s+on\s+social|be\s+the\s+first\s+to\s+know|latest\s+updates|"
                     r"campaign\s+news|voter\s+guide|provides?\s+(?:updates|information)|"
                     r"information\s+about\s+the\s+candidate|ways\s+to\s+get\s+involved|"
                     r"stay\s+(?:up\s+to\s+date|informed|connected))\b", re.I)
# "The official campaign website of ..." says where you are, not what for.
_SIGNPOST = re.compile(r"^(?:this\s+is\s+)?(?:the\s+|an\s+|a\s+)?official\s+(?:campaign\s+)?"
                       r"(?:web\s*site|home\s*page|page|site)\b", re.I)
# A post or a clip the home page is showing, not the campaign describing itself.
_MEDIA = re.compile(r"\b(?:discuss(?:es|ed)?|interview(?:s|ed)?|podcast|episode)\b", re.I)
# Not the end of a sentence: "U.S.", "Dr.", "Lt."
_ABBREVIATION = re.compile(r"(?:\b(?:[A-Z]\.){1,3}|\b(?:Dr|Mr|Mrs|Ms|Lt|Col|Gen|Sgt|Capt|Cmdr|"
                           r"St|Jr|Sr|Rep|Sen|Gov|No|Mt|Ft|vs|etc)\.)$")
# A description that stops on one of these was cut off: "...the people in
# U.S." "Washington, D.C." and "Jr." end sentences often enough to be left be.
_CUT_OFF = re.compile(r"(?:\bU\.S\.|\b(?:Dr|Mr|Mrs|Ms|Lt|Col|Gen|Sgt|Capt|Cmdr|St|Rep|Sen|"
                      r"Gov|No|Mt|Ft|vs)\.)$")
_ELLIPSIS = re.compile(r"(?:\.\.\.|…)[\"'”’)]*$")


def _sentences(text):
    """*text* in sentences, not broken after "U.S." or "Dr."."""
    out = []
    for piece in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘(])", text.strip()):
        if out and _ABBREVIATION.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return [p for p in out if p]


def _without_calls(text):
    """*text* without its calls to action and signposts: "Get involved today."."""
    return " ".join(p for p in _sentences(text)
                    if not (_CALL.match(p) or _ASKING.search(p) or _SIGNPOST.match(p)))


def whole_sentences(text):
    """*text* cut back to its last complete sentence, or ``""``.

    Search plugins truncate a meta description at about 160 characters, and
    "She's never backed down from a fight - she's locked up" is not what the
    campaign said; nor is "the people in U.S." the end of one. A description
    the site itself cuts off with an ellipsis keeps it, unless a whole
    sentence comes before it.
    """
    parts = _sentences(text)
    if not parts:
        return ""
    last = parts[-1]
    if _ELLIPSIS.search(last):
        whole = [q for q in parts[:-1] if re.search(r"[.!?][\"'”’)]*$", q)]
        return " ".join(whole) if whole else " ".join(parts)
    if re.search(r"[.!?][\"'”’)]*$", last) and not _CUT_OFF.search(last):
        return " ".join(parts)
    return " ".join(parts[:-1])


def description(page, name):
    """What the campaign says it is about, in its own words, or ``""``.

    The site's own summary of itself (its meta description), taken only when
    it says something beyond the candidate's name and the office: "Jane Smith
    for Congress - Official Website" is a label, not a description.
    """
    name_words = set(_words(name))
    for key in ("description", "og:description", "twitter:description"):
        text = " ".join(html.unescape(page.meta.get(key) or "").split())
        if not (40 <= len(text) <= 400) or _BOILERPLATE.search(text):
            continue
        if ("|" in text or re.search(r"https?://|www\.|#\w", text) or _MEDIA.search(text)
                or not (text[0].isupper() or text[0] in "\"“'‘0123456789")):
            continue    # a title bar, a scrape of the page, a post, a clip, a fragment
        text = whole_sentences(_without_calls(text))
        if len(text) < 40:
            continue
        said = [w for w in _words(text) if w not in _FILLER and w not in name_words
                and len(w) > 2 and not w[0].isdigit()]
        if len(said) >= 4:
            return text
    return ""


_ISSUES_LINK = re.compile(r"\b(?:issues?|priorities|platform|policies|agenda|positions|"
                          r"where\s+(?:i|she|he|they|we)\s+stands?|"
                          r"what\s+(?:i|we)\s+stand\s+for)\b", re.I)
# The last part of an issues index's address: /issues, /key-issues,
# /priorities-2, /where-i-stand - not /issue-energy, one issue's own page.
_INDEX_PAGE = re.compile(r"^(?:the-|key-|my-|our-|on-the-|top-)?(?:issues|priorities|platform|"
                         r"policies|agenda|positions)(?:-\d+)?(?:\.html?)?$|"
                         r"^where-(?:i|she|he|they|we)-stands?$")
# "Privacy policy" says "policy"; so do the terms of the text-message list.
# A ballot-question page lists measures with "Tyler votes NO" beneath them;
# its headings are not the candidate's platform.
_NOT_ISSUES = re.compile(r"privacy|cookie|terms|legal|disclaim|accessib|sms|text-?message|"
                         r"refund|login|sign-?in|donat|volunteer|contact|shop|store|events?\b|"
                         r"ballot|question|measure|proposition|voter-?guide|endorse|news|blog|"
                         r"press", re.I)
_NOT_AN_ISSUE = re.compile(
    r"^(?:donate|volunteer|contribute|contact|get\s+(?:involved|in\s+touch|updates?)|join|"
    r"sign\s+up|subscribe|share|menu|search|news|events?|about|home|paid\s+for|follow|"
    r"connect|stay\s+(?:connected|in\s+touch|informed|updated)|newsletter|privacy|terms|"
    r"meet\b|learn\s+more|read\s+more|endorse|press|media|shop|store|vote\b|elect\b|"
    r"chip\s+in|support\b|quick\s+links|navigation|footer|spread\s+the\s+word|"
    r"our\s+campaign|my\s+story|recent|latest|more\b|related|copyright|all\s+rights|skip|"
    r"toggle|close|open\b|tweet|email|text\b|phone|address|location|office|"
    r"social(?:\s+media)?\s*$|"
    r"we\s+need\s+you|help\b|together\b|thank|welcome|sign\b|play\b|watch\b|video|"
    r"make\s+a\s+(?:contribution|donation)|contributions?\b|ready\s+to|paid\b|"
    r"(?:effective|last)\s+(?:date|updated)|information\b|\d+(?:\.\d+)+\s)", re.I)
# A section title, not an issue: "On the issues", "Claire's top issues",
# "What we stand for", "Sean's plan for Michigan".
_SECTION_TITLE = re.compile(r"\b(?:issues?|priorities|platform|agenda|positions|stands?|"
                            r"stand\s+for|plan\s+for|believes?\s+in)\b", re.I)
# The election itself, and the site's own furniture, anywhere in a heading.
_CALL_TO_ACTION = re.compile(
    r"\b(?:november|election\s+day|early\s+voting|polls?|useful\s+links|links|resources|"
    r"downloads?|let'?s\s+(?:go|win)|finish\s+the\s+job|cookies?|news|volunteers?|keep\s+up|"
    r"latest\s+updates|campaign\s+trail|ballotpedia|survey|frequently\s+asked|faq|"
    r"p\.?\s*o\.?\s+box|mailed|summary|rated|be\s+part\s+of|fuel\s+the\s+fight|go\s+vote|"
    r"\d+\s+of\s+\d+|requested\s+information)\b", re.I)
# A heading that is half of a phrase the page split in two: "and It's Running
# Out", "Protecting Democracy and", "What We Are Fighting For".
_DANGLING = re.compile(r"^(?:and|or|but|for|to|of|with|by|in|on|at|from|here)\b|"
                       r"\b(?:and|or|for|to|of|with|by|in|on|at|from|the|a|an|our|your)$", re.I)
_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
# A heading of one word that is a verb or an adverb is half of a sentence the
# page split across two headings.
_LONE_VERBS = set("""
    promote protect defend fight build restore invest lower support strengthen secure
    expand end stop save create grow bring keep make put deliver reform cut fix improve
    ensure empower unite lead serve champion advance demand reduce raise stand
""".split())
_NUMBERING = re.compile(r"^(?:#?\d{1,2}[.):]?\s+|[ivx]{1,4}[.)]\s+)", re.I)


def issues_link(page, base):
    """The same-site page the campaign links as its issues or platform.

    A link that *says* "Issues" beats one whose address merely contains the
    word, and nothing that is a privacy policy, a shop or a donation form.
    """
    by_text, by_path = "", ""
    for href, text in page.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target = urllib.parse.urljoin(base, href).split("#")[0]
        if host_of(target) != host_of(base) or target.rstrip("/") == base.rstrip("/"):
            continue
        path = urllib.parse.unquote(urllib.parse.urlsplit(target).path)
        if _NOT_ISSUES.search(path) or _NOT_ISSUES.search(text or ""):
            continue
        if not by_text and len((text or "").split()) <= 4 and _ISSUES_LINK.search(text or ""):
            by_text = target
        last = path.rstrip("/").rsplit("/", 1)[-1].lower()
        if not by_path and _INDEX_PAGE.match(last):
            by_path = target
    return by_text or by_path


def issue_headings(page, name, rivals=(), limit=12):
    """The issues page's own section headings - "Healthcare", "Lower costs".

    Taken at the one heading level the page uses most, so a sub-point is not
    listed as an issue of its own; never the site's furniture (Donate, Sign
    up, Paid for by), a section title ("On the issues"), a question or a
    slogan with an exclamation mark, or a line that names the candidate or
    anyone else in the race - which is what an attack line does.
    """
    first = next(iter(w for w in _words(name) if len(w) >= 3), "")
    names = {fold(surname_of(name)), first} | {fold(r) for r in rivals if r}
    names.discard("")
    # Most pages have one h1, their title; some set every issue in one.
    titled = sum(1 for tag, _ in page.headings if tag == "h1") < 3
    by_level = collections.defaultdict(list)
    seen = collections.Counter()
    for tag, text in page.headings:
        text = _INVISIBLE.sub("", text)
        text = re.sub(r"^[^\w\"'“‘(]+|[\s»›→>]+$", "", text, flags=re.U)
        text = _NUMBERING.sub("", text.strip(" :.-–—|•#*")).strip(" :.-–—|•")
        if (tag == "h1" and titled) or not (3 <= len(text) <= 60) or len(text.split()) > 8:
            continue
        seen[tag] += 1
        if text.startswith("(") or _DANGLING.search(text):
            continue
        if "{" in text or "}" in text or text.endswith(("?", "!")):
            continue
        if (_NOT_AN_ISSUE.search(text) or _SECTION_TITLE.search(text)
                or _CALL_TO_ACTION.search(text)):
            continue
        words = _words(text)
        if set(words) & names:
            continue
        if len(words) == 1 and (words[0] in _LONE_VERBS or words[0].endswith("ly")):
            continue
        if re.search(r"\bfor\s+(?:congress|senate)\b|https?:|@|\d{3}[-.)\s]\d{3}", text, re.I):
            continue
        key = " ".join(w for w in _words(text) if w != "and")
        if key not in (" ".join(w for w in _words(o) if w != "and") for o in by_level[tag]):
            by_level[tag].append(text)
    if not by_level:
        return []
    level = max(sorted(by_level), key=lambda t: len(by_level[t]))
    items = by_level[level]
    # A page whose headings are mostly furniture is not an issues page, even
    # if three survive: Ron Russell's "issues" page was Campaign News, Follow
    # Us, Become a Volunteer and Keep Up with the Campaign.
    if len(items) < 3 or len(items) > 20 or len(items) * 3 < seen[level]:
        return []
    return items[:limit]


_NOT_A_PORTRAIT = {
    "logo", "icon", "icons", "banner", "sprite", "favicon", "flag", "seal", "badge", "button",
    "arrow", "social", "socialshare", "share", "og", "webclip", "facebook", "twitter",
    "instagram", "youtube", "donate", "background", "bg", "placeholder", "signature", "map",
    "endorse", "endorsement", "endorsed", "team", "rally", "crowd", "event", "events",
    "volunteer", "volunteers", "with", "and", "supporters", "group", "yard", "sign", "mailer",
    "flyer", "graphic", "text", "wordmark", "header", "footer", "vote", "ballot", "qr", "hero",
    "collage", "announcement", "announce", "merch", "shirt", "tshirt", "ts", "store", "shop",
    # Someone else in the picture: "Mikes Mom.png" carried his name in its alt text.
    "family", "families", "kids", "children", "child", "son", "daughter", "wife", "husband",
    "spouse", "mom", "mother", "dad", "father", "grandma", "grandpa", "baby", "moms", "dads",
}
# A file named for the campaign is usually its logo or a slogan card.
_BRANDING = {"congress", "senate", "campaign", "elect", "slogan", "change", "fight"}
# Words that say an image is a picture of a person's face. "Photo" alone does
# not: "Chew_Photo_Edit_Purple.png" was a group photograph.
_PORTRAIT_HINT = {"headshot", "headshots", "portrait", "profile"}
_PORTRAIT_PAIRS = (("head", "shot"), ("candidate", "photo"), ("official", "photo"))


def _hinted(words):
    words = list(words)
    return bool(set(words) & _PORTRAIT_HINT) or any(
        a in words and b in words for a, b in _PORTRAIT_PAIRS)


def portrait_shape(url, hinted=False):
    """``True`` when the image is head-and-shoulders shaped, ``False`` when it
    is not (a banner, a wordmark, an icon), ``None`` when it could not be read.

    A head-and-shoulders photograph is taller than it is wide - 4:5, 2:3.
    Logos, share cards, merchandise and group shots are square or wide: of
    nineteen images the first full run took that were not portraits, fifteen
    were. An image whose own name says it is a headshot may be square.
    """
    return portrait_check(url, hinted)[0]


def portrait_check(url, hinted=False):
    """``(shape, weight)``: :func:`portrait_shape`'s verdict, and the
    image's ``{"bytes", "width", "height"}`` when it was read (``None``
    otherwise). A file larger than the read limit weighs at least that."""
    try:
        req = urllib.request.Request(url, headers=dict(
            _UA_WEB, Accept="image/jpeg,image/png,image/webp,image/*;q=0.8"))
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
            if response.status != 200:
                return False, None
            if not (response.headers.get("Content-Type") or "").startswith("image/"):
                return False, None
            data = response.read(MAX_BODY + 1)
            length = response.headers.get("Content-Length") or ""
            encoding = response.headers.get("Content-Encoding")
    except urllib.error.HTTPError as exc:
        return (None if exc.code in (403, 429) or exc.code >= 500 else False), None
    except Exception:
        return None, None
    # Some servers gzip an image when asked for gzip at all (Missouri's
    # attorney general's headshot): its size is read from the image, its
    # weight is what crossed the wire.
    size = image_size(_decoded(data, encoding) or b"")
    if not size or not all(size):
        return None, None
    width, height = size
    weight = {"bytes": int(length) if length.isdigit() else len(data),
              "width": width, "height": height}
    widest = 1.35 if hinted else 0.9
    return min(width, height) >= 200 and 0.5 <= width / height <= widest, weight


def portrait(page, base, profile):
    """``[(url, hinted)]``: campaign images named for the candidate, best
    first (rule 24).

    Only an image whose file name or alt text carries the candidate's surname
    is considered - "jane-smith-headshot.jpg", alt="Jane Smith" - and never
    one whose name says it is a logo, a crowd or the candidate with someone
    else. The caller then checks its shape: a campaign's wordmark carries the
    candidate's name too.
    """
    surname = fold(surname_of(profile["name"]))
    if len(surname) < 3:
        return []
    first = (_words(profile["name"]) or [""])[0]
    person = set(_words(profile["name"]))
    chosen = (overrides.CAMPAIGN_PORTRAITS.get(profile.get("id")) or {}).get("url")
    scored = []
    images = [(page.meta.get("og:image", ""), ""), (page.meta.get("twitter:image", ""), "")]
    for src, alt in images + page.images:
        src = (src or "").strip()
        if not src or src.startswith("data:"):
            continue
        url = urllib.parse.urljoin(base, src)
        if not url.startswith("https://"):
            continue
        if url == chosen:
            # Looked at by a person, and drawn by this very page.
            scored.append((9, url, True))
            continue
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
        if not re.search(r"\.(?:jpe?g|png|webp)$", path, re.I):
            continue
        name_words = _words(os.path.basename(path).rsplit(".", 1)[0])
        alt_words = _words(alt)
        words = set(name_words) | set(alt_words)
        if words & _NOT_A_PORTRAIT:
            continue
        hinted = _hinted(name_words) or _hinted(alt_words)
        if words & _BRANDING and not hinted:
            continue
        def run_together(words):
            # "BrianMiller-5.jpg": the first name and surname as one word.
            return any(w.startswith(first) and w.endswith(surname)
                       and len(w) <= len(first + surname) for w in words if first)

        in_file = surname in name_words or run_together(name_words)
        in_alt = surname in alt_words or run_together(alt_words)
        if not (in_file or in_alt):
            continue
        # Whatever named them must be about little else: "ellman_website_
        # loyal_to_you.png" is a slogan card with her name on it.
        said = name_words if in_file else alt_words
        extra = [w for w in said if w not in person and w not in _PORTRAIT_HINT
                 and not any(c.isdigit() for c in w)]
        if len(extra) > 2 and not hinted:
            continue
        score = 1 + (first in words) + 2 * hinted
        if url not in (u for _, u, _ in scored):
            scored.append((score, url, hinted))
    return [(u, hinted) for _, u, hinted in sorted(scored, key=lambda row: -row[0])]


def evidence_of(page, base, url, profile=None):
    """What on *page* names the person beside the image at *url*: its alt
    text, else its file name - the words :func:`portrait` took it by, kept
    with the portrait so a reader of the cache can see why (rule 24)."""
    surname = fold(surname_of(profile["name"])) if profile else ""
    chosen = overrides.CAMPAIGN_PORTRAITS.get((profile or {}).get("id")) or {}
    if chosen.get("url") == url:
        return chosen["evidence"]
    images = [(page.meta.get("og:image", ""), ""), (page.meta.get("twitter:image", ""), "")]
    alts = [alt for src, alt in images + page.images
            if src and urllib.parse.urljoin(base, src.strip()) == url and alt.strip()]
    name = urllib.parse.unquote(os.path.basename(urllib.parse.urlsplit(url).path))
    if surname:
        # The words that named them: an alt text that does not ("Hero
        # image") is no evidence, even beside a file name that does.
        first = (_words(profile["name"]) or [""])[0]
        naming = [alt for alt in alts if surname in _words(alt) or any(
            w.startswith(first) and w.endswith(surname) for w in _words(alt))]
        if naming:
            return f'alt text "{" ".join(naming[0].split())[:120]}"'
        return f'file name "{name[:120]}"'
    if alts:
        return f'alt text "{" ".join(alts[0].split())[:120]}"'
    return f'file name "{name[:120]}"'


def page_forms(page, base):
    """``{image url: [(rendition url, width)]}``: the renditions the page's
    own ``srcset`` offers of each image it draws."""
    out = {}
    for src, srcset in page.srcsets.items():
        url = urllib.parse.urljoin(base, src.strip())
        forms = [(u, w) for u, w in parse_srcset(srcset, base) if u.startswith("https://")]
        if forms:
            out.setdefault(url, forms)
    return out


# A link to the page where a campaign says who the candidate is. Their
# portrait is often there and not on the home page: of thirty nominees'
# sites with none on the home page, the research of 2026-10-19 found one on
# the About page of four.
_ABOUT_TEXT = re.compile(r"^(?:about(?:\s+\w+){0,2}|meet\s+\w+(?:\s+\w+)?|(?:my|her|his|our)\s+story|"
                         r"biography|bio|who\s+is\s+\w+(?:\s+\w+)?\??|get\s+to\s+know\s+\w+)$", re.I)
_ABOUT_PATH = re.compile(r"^/(?:about|meet|bio|biography|who-is|get-to-know|my-story)"
                         r"(?:[-_][\w-]*)?/?$", re.I)


def about_link(page, base):
    """The address of the campaign's About or Meet page on its own host, or
    ``None``: a link whose path or words say it is one ("/about", "Meet
    Jena"), never another site's page."""
    host = host_of(base)
    for href, text in page.links:
        url = urllib.parse.urljoin(base, (href or "").strip()).split("#", 1)[0]
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or host_of(url) != host or parts.path in ("", "/"):
            continue
        if _ABOUT_PATH.search(parts.path) or _ABOUT_TEXT.search(" ".join(text.split())):
            return url
    return None


def other_form(url):
    """The same address with "www." added or taken away, or None."""
    try:
        parts = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return None
    host = parts.hostname or ""
    if not host or host.count(".") < 1:
        return None
    flipped = host[4:] if host.startswith("www.") else "www." + host
    if flipped.count(".") < 1:
        return None
    return urllib.parse.urlunsplit(parts._replace(netloc=flipped))


def read_site(profile, url, pause=1.0, extract=True, rivals=()):
    """Everything a campaign site gives, as a cache record.

    When the address as filed cannot be reached at all - no DNS record, a
    TLS failure, a host error - the same site is tried with "www." added or
    taken away, and that form is kept only if it passes every check here,
    naming the candidate included (rule 38): Sen. Dan Sullivan's and Marty
    Jackley's filed www. hosts failed on 2026-10-17 while their bare
    domains served their campaigns, and Greg Landsman's was the reverse.
    The record keeps the filed address as ``url`` and the one that works as
    ``working``. A hijacked or parked answer is never retried: it is a
    verdict, not a failure.
    """
    record = _read_one(profile, url, pause, extract, rivals)
    unreachable = record["status"] is None or (record["safe"] is None
                                               and (record["status"] or 0) >= 500)
    alternate = other_form(url) if unreachable else None
    if alternate and not overrides.blocked_campaign_host(alternate):
        time.sleep(pause)
        other = _read_one(profile, alternate, pause, extract, rivals)
        if other["safe"] is SAFE:
            other["working"] = alternate
            other["url"] = url
            return other
    return record


def _read_one(profile, url, pause=1.0, extract=True, rivals=()):
    final, status, markup = fetch(url)
    page = parse_page(markup)
    verdict, reason = assess(profile, url, final, status, page)
    record = {"url": url, "final": final, "status": status, "safe": verdict, "reason": reason}
    if verdict is not SAFE or not extract:
        return record
    quote = description(page, profile["name"])
    if quote:
        record["description"] = quote
    link = issues_link(page, final)
    if link:
        time.sleep(pause)
        issues_final, issues_status, issues_markup = fetch(link)
        issues_page = parse_page(issues_markup)
        heading = " ".join([issues_page.title] + [h for t, h in issues_page.headings if t == "h1"])
        if (issues_status == 200 and host_of(issues_final) == host_of(final)
                and not _NOT_ISSUES.search(heading)):
            record["issuesUrl"] = issues_final
            items = issue_headings(issues_page, profile["name"], rivals)
            if items:
                record["issues"] = items
    look_for_portrait(record, profile, page, final, pause)
    return record


def look_for_portrait(record, profile, page, final, pause=1.0):
    """Put the campaign's portrait of the candidate in *record*: from the
    page read (*page*, at *final*), or else from the campaign's About or
    Meet page on the same host (:func:`about_link`), which must itself read
    as the campaign's and name the candidate (:func:`assess`, rule 38).

    The record keeps the page the image was on (``portraitPage``), the
    words that named them beside it (``portraitEvidence``) and the day it
    was read (``portraitRead``). A portrait over the caps is taken in a
    rendition its source offers, else at full size, and said in
    ``portraitHeavy`` (:func:`lighten`)."""
    refused_all = []
    where, base = page, final
    for step in ("home", "about"):
        if step == "about":
            about = about_link(page, final)
            if not about:
                break
            time.sleep(pause)
            about_final, about_status, about_markup = fetch(about)
            where, base = parse_page(about_markup), about_final
            verdict, _reason = assess(profile, about, about_final, about_status, where)
            if verdict is None:
                # It concluded nothing: what the last good read refused
                # there is kept (_keep, rule 8).
                record["portraitUnread"] = about
            if verdict is not SAFE or host_of(about_final) != host_of(final):
                break
        pictures = portrait(where, base, profile)
        # What is refused is kept so validate can tell a NOT_A_PORTRAIT
        # entry still means something (photos.not_a_portrait).
        taken = take_portrait(record, [p for p in pictures
                                       if not not_a_portrait(p[0], passed_over=refused_all)],
                              offers=page_forms(where, base))
        if taken:
            original = (record.get("portraitHeavy") or [{}])[0].get("url") or taken
            record["portraitPage"] = base
            record["portraitEvidence"] = evidence_of(where, base, original, profile)
            record["portraitRead"] = datetime.date.today().isoformat()
            break
    if refused_all:
        record["notPortraits"] = refused_all
    return record.get("portrait")


def _weigh(url):
    """An image's weight, for ``photos.lighter_rendition``; ``None`` unread."""
    return portrait_check(url, True)[1]


_PORTRAIT_FIELDS = ("portrait", "portraitWeight", "portraitHeavy", "portraitForms",
                    "portraitPage", "portraitEvidence", "portraitRead")


def lighten(record, picture, weight, offered=()):
    """Put *picture* in *record* as its portrait: as it is when within the
    caps, else a lighter rendition of the same file
    (``photos.lighter_rendition``: one its page's srcset lists, its host's
    own resizer, or Photon), else at full size. Returns what was taken.

    A heavy file with no lighter rendition is still taken - a nominee's
    only likeness is not withheld for its weight; eleven were, and showed
    the silhouette beside an opponent's photograph, and the first version
    of PR #134 left six more out again under the brief of 2026-10-19 - and
    the weight is said in ``portraitHeavy`` either way (``kept``: shown at
    full size). The owner's decision of 2026-10-25 relaxed that brief: a
    weight cap costs coverage and guards no fact about a person."""
    why = too_heavy(weight)
    record.pop("portraitForms", None)
    if not why:
        record.pop("portraitHeavy", None)
        record["portrait"] = picture
        if weight:
            record["portraitWeight"] = weight
        else:
            record.pop("portraitWeight", None)
        return picture
    found = lighter_rendition(picture, weight, _weigh, offered)
    record["portraitHeavy"] = [{"url": picture, "why": why, "kept": not found}]
    if offered:
        record["portraitForms"] = [[url, width] for url, width in offered]
    record["portrait"], record["portraitWeight"] = found or (picture, weight)
    return record["portrait"]


def take_portrait(record, pictures, tries=3, offers=None):
    """Put the first of *pictures* that is head-and-shoulders shaped in
    *record*, with its measured weight, in a lighter rendition of it when it
    is too heavy (:func:`lighten`). *offers* maps an image to the
    renditions its page lists."""
    for key in _PORTRAIT_FIELDS:
        record.pop(key, None)
    for picture, hinted in pictures[:tries]:
        verdict, weight = portrait_check(picture, hinted)
        if verdict is True:
            return lighten(record, picture, weight, (offers or {}).get(picture, ()))
    return None


def measure_portraits(cache, log=print, pause=1.0):
    """Weigh each cached campaign-site portrait that has no recorded weight,
    and take a lighter rendition of one that is too heavy (:func:`lighten`).
    Returns how many were weighed.

    Only the image and its renditions are fetched, never the site: a
    picture is chosen by the full read (``_read_one``), which first checks
    that the page names the candidate (rule 38) and is not spam or parking
    (rule 39). A heavy one kept at full size is weighed again each run, and
    so is one an earlier version left out for its weight (``leftOut``):
    it is shown again, lighter where it can be."""
    people = (cache or {}).get("people") or {}
    weighed = 0
    for entry in people.values():
        for key in ("site", "listed", "drawn"):
            record = entry.get(key) or {}
            heavy = (record.get("portraitHeavy") or [{}])[0].get("url")
            shown = record.get("portrait")
            if shown and "portraitWeight" in record and not too_heavy(record["portraitWeight"]):
                continue
            picture = heavy or shown
            if not picture:
                continue
            time.sleep(pause)
            weight = _weigh(picture)
            if not weight:
                continue                       # could not tell: kept (rule 8)
            weighed += 1
            kept = {k: record[k] for k in ("portraitPage", "portraitEvidence", "portraitRead")
                    if k in record}
            offered = [tuple(form) for form in record.get("portraitForms") or ()]
            lighten(record, picture, weight, offered)
            record.update(kept)
            if record.get("portraitHeavy"):
                state = ("kept at full size" if record["portraitHeavy"][0]["kept"]
                         else "taken smaller")
                log(f"    {entry.get('name')}: {picture} is {too_heavy(weight)}; {state}")
    return weighed


# ------------------------------------------------------------ drawn pages
#
# Many campaign sites draw their images with JavaScript (Wix, Squarespace's
# lazy loading, site builders' galleries), and some answer a script with a
# bot wall (HTTP 202 or 403) that a browser passes: the research of
# 2026-10-19 found a nominee's headshot on the About page only as the page
# was drawn. These pages are read once more in a headless Chrome of our own
# (``tools/read_court_pages.mjs``, the courts' reader), with every rule of
# the static read: the drawn page must read as the campaign's and name the
# candidate, and the image must be named for them and shaped like a portrait
# (rule 38), within the caps or in a size the page offers.

RENDER_LIMIT = 40          # sites drawn a run: about 10 seconds each
RENDER_DAYS = 14           # a drawn read stands this long
RENDER_BATCH = 12          # pages a browser run


def _code(i):
    """A page code the browser reader accepts (letters only)."""
    letters = ""
    i += 1
    while i:
        i, rest = divmod(i - 1, 26)
        letters = chr(65 + rest) + letters
    return "CAMPAIGN-" + letters


def render_wanted(profiles, cache, today=None, limit=RENDER_LIMIT):
    """``[(profile, key, site record)]``: the people still running with no
    portrait by any route whose site's static read found none - it read as
    theirs, or could not tell (a bot wall) - and that no drawn read covers
    from the last :data:`RENDER_DAYS` days. Most recently unread first."""
    people = (cache or {}).get("people") or {}
    today = today or datetime.date.today()
    cutoff = (today - datetime.timedelta(days=RENDER_DAYS)).isoformat()
    out = []
    for profile in profiles:
        if not running(profile) or profile.get("photoSource"):
            continue
        entry = people.get(profile.get("id")) or {}
        for key in ("site", "listed"):
            record = entry.get(key) or {}
            url = record.get("working") or record.get("url") or ""
            if (not url.startswith("https://") or record.get("safe") is False
                    or record.get("portrait") or record.get("portraitHeavy")
                    or overrides.blocked_campaign_host(url)):
                continue
            drawn = entry.get("drawn") or {}
            if drawn.get("url") == url and drawn.get("read", "") >= cutoff:
                continue
            out.append((profile, key, url, drawn.get("read", "")))
            break
    out.sort(key=lambda row: row[3])
    return [(p, key, url) for p, key, url, _read in out[:limit]]


def _drawn_read(profile, url, markup, today):
    """A drawn page's record: its verdict, and a portrait from it."""
    page = parse_page(markup)
    verdict, reason = assess(profile, url, url, 200, page)
    record = {"url": url, "safe": verdict, "reason": reason, "read": today}
    if verdict is not SAFE:
        return record, page
    found = portrait(page, url, profile)
    # What is refused is kept so validate can tell a NOT_A_PORTRAIT entry
    # still means something (photos.not_a_portrait).
    refused = []
    pictures = [p for p in found if not not_a_portrait(p[0], passed_over=refused)]
    if refused:
        record["notPortraits"] = refused
    if take_portrait(record, pictures, offers=page_forms(page, url)):
        original = (record.get("portraitHeavy") or [{}])[0].get("url") or record["portrait"]
        record.update(portraitPage=url, portraitEvidence=evidence_of(page, url, original, profile),
                      portraitRead=today)
    return record, page


def render_portraits(profiles, cache, root=".", limit=RENDER_LIMIT, log=print, reader=None,
                     today=None):
    """Read the sites :func:`render_wanted` names as a browser draws them -
    the home page, then its About page when the home page has no portrait -
    and keep what each gives as the person's ``drawn`` record. Returns how
    many portraits were found. No Chrome, or a page the browser could not
    read, keeps every earlier drawn record (rule 8)."""
    from .courts import read_with_browser

    one_run = reader or (lambda pages: read_with_browser(pages, root=root))

    def reader(pages):
        # A few pages a browser run: the reader gives a run fifteen minutes,
        # and a slow site takes most of a minute to load and settle.
        found, problems, codes = {}, [], sorted(pages)
        for i in range(0, len(codes), RENDER_BATCH):
            got, said = one_run({c: pages[c] for c in codes[i:i + RENDER_BATCH]})
            found.update(got)
            problems += said
        return found, problems

    today = (today or datetime.date.today()).isoformat()
    people = cache.setdefault("people", {})
    wanted = render_wanted(profiles, cache, limit=limit)
    if not wanted:
        return 0
    log(f"  enrich: drawing {len(wanted)} campaign site(s) in a headless browser ...")
    homes = {_code(i): url for i, (_p, _k, url) in enumerate(wanted)}
    drawn, problems = reader(homes)
    for line in problems[:5]:
        log(f"    [drawn] {line}")
    found, abouts = 0, {}
    for i, (profile, _key, url) in enumerate(wanted):
        markup = drawn.get(_code(i))
        if markup is None:
            continue                                     # kept as it was (rule 8)
        record, page = _drawn_read(profile, url, markup, today)
        before = people.setdefault(profile["id"], {}).get("drawn")
        people[profile["id"]]["drawn"] = record
        if record.get("portrait"):
            found += 1
        elif record["safe"] is SAFE:
            about = about_link(page, url)
            if about:
                abouts[_code(i)] = (profile, url, about, before)
    if abouts:
        from .photos import keep_refused
        more, problems = reader({code: about for code, (_p, _u, about, _b) in abouts.items()})
        for line in problems[:5]:
            log(f"    [drawn] {line}")
        for code, (profile, url, about, before) in abouts.items():
            if more.get(code) is None:
                # Not drawn: what the last good read refused stays (rule 8).
                if (before or {}).get("url") == url:
                    keep_refused(people[profile["id"]]["drawn"], before)
                continue
            record, _page = _drawn_read(profile, about, more[code], today)
            # What either page refused stays with the record kept: the
            # About page's portrait, or else the home page's record.
            if record.get("portrait"):
                record["url"] = url                      # the site it stands for
                people[profile["id"]]["drawn"] = keep_refused(record,
                                                              people[profile["id"]]["drawn"])
                found += 1
            else:
                keep_refused(people[profile["id"]]["drawn"], record)
    log(f"  enrich: {found} portrait(s) found on drawn pages")
    return found


# --------------------------------------------------------------------- cache

def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def _keep(old, new):
    """An unreachable site this time keeps what an earlier visit to the same
    address found (rule 8); a site no longer linked keeps no record at all."""
    if new is None:
        return None
    if new.get("safe") is None and old and old.get("url") == new.get("url"):
        return dict(old, lastTry={"status": new.get("status"), "reason": new.get("reason")})
    if new.get("portraitUnread") and not new.get("portrait") and old \
            and old.get("url") == new.get("url"):
        # The About page concluded nothing: the refusals its last good read
        # recorded stay (rule 8).
        from .photos import keep_refused
        keep_refused(new, old)
    return new


def unreachable(entry):
    """True when the last read of a committee site reached nothing at all."""
    site = (entry or {}).get("site") or {}
    last = site.get("lastTry") or site
    status = last.get("status")
    return bool(site) and (status is None or status >= 500)


def resolve_all(profiles, root=".", refresh=False, limit=None, log=print, workers=6,
                today=None, only_unreachable=False):
    """Read Wikipedia infoboxes and campaign sites for everyone still running.

    Returns ``(cache, counts)``. A person read within STALE_DAYS is skipped
    unless *refresh*; an interrupted run resumes from the cache. With
    *only_unreachable*, only people whose committee site the last read could
    not reach are read again (and every ballot link is checked).
    """
    cache = load_cache(root) or {}
    people = cache.setdefault("people", {})
    today = today or datetime.date.today()
    cutoff = (today - datetime.timedelta(days=STALE_DAYS)).isoformat()
    wanted = [p for p in profiles if running(p) or checked_site(p)]
    if only_unreachable:
        todo = [p for p in wanted if unreachable(people.get(p["id"]))]
    else:
        todo = [p for p in wanted
                if refresh or (people.get(p["id"]) or {}).get("checked", "") < cutoff]
    if limit:
        todo = todo[:limit]
    log(f"  enrich: {len(todo)} of {len(wanted)} people to read "
        f"({sum(running(p) for p in wanted)} challengers still running)")

    # Where every ballot-page link leads, for anyone it names, in or out of
    # the race: a link that lands on a protest, a party or an election list
    # is not their article (:func:`link_is_about`). One request per 50.
    ballot_links = sorted({p["wikipedia"] for p in profiles
                           if p.get("wikipediaVia") == "election-page" and p.get("wikipedia")})
    if ballot_links:
        found = link_targets(ballot_links, log=log)
        links = cache.setdefault("links", {})
        for title in ballot_links:
            if title in found:
                links[title] = dict(found[title], checked=today.isoformat())
        for title in [t for t in links if t not in ballot_links]:
            del links[title]

    linked = [p for p in todo if running(p) and p.get("wikipedia")]
    articles = fetch_articles([p["wikipedia"] for p in linked], log=log) if linked else {}
    for profile in linked:
        got = articles.get(profile["wikipedia"])
        if not got:
            continue
        title, text = got
        entry = people.setdefault(profile["id"], {})
        if not article_is_theirs(title, profile):
            entry.pop("wiki", None)       # redirected to an article about someone else
            continue
        facts = wiki_facts(text)
        if facts:
            entry["wiki"] = dict(facts, title=title)
        else:
            entry.pop("wiki", None)

    from .races import race_id

    def race_of(p):
        return p.get("contestRaceId") or race_id(p["chamber"], p["state"], p.get("districtNum"))

    field = collections.defaultdict(set)
    for p in profiles:
        if p.get("state") not in (None, "", "N/A"):
            field[race_of(p)].add(surname_of(p["name"]))

    def one(profile):
        extract = running(profile)
        rivals = field[race_of(profile)] - {surname_of(profile["name"])}
        fec_url = profile.get("campaignSite")
        listed = profile.get("electionPageSite") if extract else None
        if listed and (overrides.blocked_campaign_host(listed)
                       or (fec_url and host_of(listed) == host_of(fec_url))):
            listed = None
        site = read_site(profile, fec_url, extract=extract, rivals=rivals) if fec_url else None
        other = read_site(profile, listed, rivals=rivals) if listed else None
        return profile, site, other

    # Nobody keeps a record once they are out of the race with nothing linked:
    # a stale verdict on a site the page no longer shows is noise in the report.
    keep_ids = {p["id"] for p in wanted}
    for pid in [pid for pid in people if pid not in keep_ids]:
        del people[pid]

    stamp = today.isoformat()
    with ThreadPoolExecutor(workers) as pool:
        for done, (profile, site, other) in enumerate(pool.map(one, todo), start=1):
            entry = people.setdefault(profile["id"], {})
            entry["name"] = profile["name"]
            for key, record in (("site", site), ("listed", other)):
                kept = _keep(entry.get(key), record)
                if kept is None:
                    entry.pop(key, None)
                else:
                    entry[key] = kept
            entry["checked"] = stamp
            if done % 50 == 0:
                save_cache(cache, root)
                log(f"    {done}/{len(todo)} read")
    cache["checked"] = stamp
    # A portrait taken before weights were recorded, by a read not yet due
    # again, is weighed now (TECH-13).
    weighed = measure_portraits(cache, log=log)
    if weighed:
        log(f"    weighed {weighed} campaign-site portrait(s)")
    save_cache(cache, root)

    counts = collections.Counter()
    for entry in people.values():
        counts["wiki"] += bool(entry.get("wiki"))
        for key in ("site", "listed"):
            site = entry.get(key) or {}
            counts[f"{key}_safe"] += site.get("safe") is True
            counts[f"{key}_refused"] += site.get("safe") is False
            counts["description"] += bool(site.get("description"))
            counts["issues"] += bool(site.get("issues"))
            counts["portrait"] += bool(site.get("portrait"))
    log(f"  enrich: {counts['wiki']} infoboxes; committee sites {counts['site_safe']} usable, "
        f"{counts['site_refused']} refused; election-page sites {counts['listed_safe']} usable; "
        f"{counts['description']} descriptions, {counts['issues']} issue lists, "
        f"{counts['portrait']} portraits")
    return cache, counts


# --------------------------------------------------------------------- apply

def withdrawn(site):
    """True when a committee site must come off the page: it serves spam."""
    return bool(site) and site.get("safe") is False and site.get("reason") in (HIJACKED, PARKED)


def withhold_links(profiles, cache):
    """Withhold each ballot link that leads somewhere not this person's
    article (:func:`link_is_about`); return how many were withheld.

    Run before anything follows the link: :func:`kyc.portraits.apply_cache`
    (and ``portraits`` resolving) take a challenger's portrait from the
    article ``wikipedia`` names, so a link withheld after them had already
    delivered the lead image of the article it was withheld for - a section
    of another person's article whose title carries the surname, say. It is
    safe to run twice: a withheld profile no longer has the link.
    """
    links = (cache or {}).get("links") or {}
    withheld = 0
    for profile in profiles:
        title = profile.get("wikipedia")
        if (title and profile.get("wikipediaVia") == "election-page" and title in links
                and not link_is_about(links[title], profile["name"],
                                      alias=overrides.article_alias(profile.get("id")))):
            # Withheld, not followed; validate lists it. A title not yet
            # checked stays (rule 8).
            target = links[title]
            profile["wikipediaWithheld"] = {
                "title": title,
                "landsOn": None if target.get("missing") else (
                    target.get("to", "") + (f"#{target['fragment']}"
                                            if target.get("fragment") else "")),
            }
            profile.pop("wikipedia", None)
            profile.pop("wikipediaVia", None)
            withheld += 1
    return withheld


def apply_cache(profiles, cache, as_of=None):
    """Fill empty fields of challengers still running from the cache.

    Every filled field says where it came from (``fieldSources``), and nothing
    already known is overwritten. A committee site that reads as hijacked or
    parked is withdrawn from the profile; one that merely failed to name the
    candidate stays, and ``validate`` lists it. Ages are computed at *as_of*,
    the date every other age on the site is computed at.
    """
    people = (cache or {}).get("people") or {}
    counts = collections.Counter()
    withheld = withhold_links(profiles, cache)
    if withheld:
        counts["wikipedia_withheld"] += withheld
    for profile in profiles:
        entry = people.get(profile.get("id"))
        if not entry:
            continue
        committee = entry.get("site")
        if committee and withdrawn(committee) and profile.get("campaignSite") == committee["url"]:
            profile.pop("campaignSite", None)
            counts["withdrawn"] += 1
        working = (committee or {}).get("working")
        if (working and committee.get("safe") is True
                and profile.get("campaignSite") == committee["url"]
                and not overrides.blocked_campaign_host(working)):
            # The filed address fails and the same site answers, naming the
            # candidate, with "www." added or taken away (read_site).
            profile["campaignSite"] = working
            committee = dict(committee, url=working)
            counts["site_form"] += 1
        if not running(profile):
            continue

        wiki = entry.get("wiki") or {}
        if wiki.get("born") and fill_field(profile, "birthdate", wiki["born"], "wikipedia"):
            age = age_on(wiki["born"], as_of)
            if age != "":
                profile["age"] = int(age)
            counts["born"] += 1
        if wiki.get("education") and fill_field(profile, "education", wiki["education"],
                                                "wikipedia"):
            counts["education"] += 1
        if wiki.get("occupation") and fill_field(profile, "previous_professions",
                                                 wiki["occupation"], "wikipedia"):
            counts["occupation"] += 1

        # The site the profile shows: the committee's own when it checks out;
        # the election page's when there is none, or the committee's did not.
        listed = entry.get("listed")
        shown = committee if committee and committee.get("url") == profile.get("campaignSite") \
            else None
        if (listed and listed.get("safe") is True
                and not overrides.blocked_campaign_host(listed["url"])
                and (shown is None or shown.get("safe") is False)):
            if not profile.get("campaignSite"):
                counts["site"] += 1
            profile["campaignSite"] = listed["url"]
            profile["campaignSiteVia"] = "election-page"
            shown = listed
        if not shown or shown.get("safe") is not True:
            # A site whose static read could not tell (a bot wall) may still
            # give the portrait a browser drew from it, read by every rule.
            if shown and shown.get("safe") is None and not profile.get("photoSource"):
                take_campaign_portrait(profile, entry, shown, counts)
            continue
        if shown.get("description"):
            profile["campaignQuote"] = shown["description"]
            counts["quote"] += 1
        if shown.get("issuesUrl"):
            profile["campaignIssuesUrl"] = shown["issuesUrl"]
        if shown.get("issues") and fill_field(profile, "platforms", "; ".join(shown["issues"]),
                                              "campaign-site"):
            counts["issues"] += 1
        if not profile.get("photoSource"):
            take_campaign_portrait(profile, entry, shown, counts)
    return counts


def portrait_record(entry, site):
    """The record a profile's campaign portrait comes from: the site's own
    read when it found one, else the drawn
    read of that same site (:func:`render_portraits`) when it read as the
    campaign's."""
    if site.get("portrait") or site.get("portraitHeavy"):
        return site
    drawn = (entry or {}).get("drawn") or {}
    if drawn.get("safe") is True and drawn.get("url") in (site.get("url"), site.get("working")):
        return drawn
    return site


def take_campaign_portrait(profile, entry, site, counts):
    """Put the campaign's portrait at the head of *profile*'s chain, from
    :func:`portrait_record`; count one shown at full size over the caps.
    Only for a challenger: a member's portrait comes by their bioguide id
    (rule 24), and a campaign's photograph is never put in front of it."""
    if not profile.get("isCandidate") or profile.get("bioguide"):
        return False
    record = portrait_record(entry, site)
    picture = campaign_portrait(record)
    if picture is None:
        return False
    if too_heavy(record.get("portraitWeight")):
        # No lighter rendition is offered: shown all the same, lazily, and
        # counted for the build's report (TECH-13, rule 87).
        counts["portrait_heavy"] += 1
    # A curated row is a candidate as much as a filer (rule 24): Brian
    # Bengs's own campaign portrait sat in this cache while his profile
    # showed the silhouette, because only FEC filers were given one.
    photos = [u for u in profile.get("photos") or [] if u != picture]
    profile["photos"] = [picture] + photos
    profile["photo_url"] = picture
    profile["photoSource"] = "campaign-site"
    # The credit names the host of the page it links, the one the image
    # was on: a filed address that redirects (michaelquirk4congress.com to
    # michaelquirkforcongress.com) read as one site and linked another.
    page = record.get("portraitPage") or profile.get("campaignSite")
    profile["photoCredit"] = campaign_credit(page)
    counts["portrait"] += 1
    return True


def campaign_portrait(site):
    """The portrait a campaign-site record shows, or ``None``: not on
    ``NOT_A_PORTRAIT`` or ``PORTRAIT_LICENCE_DOUBTS`` (``photos.refused``,
    the one test every route asks), nor a rendition of a file that is. One
    over the caps is shown all the same (:func:`lighten`, rule 87)."""
    picture = (site or {}).get("portrait")
    heavy = (site or {}).get("portraitHeavy") and site["portraitHeavy"][0].get("url")
    # A rendition of a refused image is that image: the entry names the file
    # the page draws, the cache may hold a smaller form its srcset lists.
    if not picture or withheld_by_a_person(picture, heavy):
        return None
    return picture


def problems(profiles, cache):
    """Committee sites a person should look at, as report lines by kind.

    ``withdrawn`` - taken off the page as hijacked or parked; ``unconfirmed``
    - still linked, but the page did not confirm the candidate; and
    ``compromised`` - the campaign's own page, with gambling links hidden in
    it, which is the campaign's problem to know about rather than a reason to
    unlink it.
    """
    people = (cache or {}).get("people") or {}
    out = {"withdrawn": [], "unconfirmed": [], "compromised": []}
    for profile in profiles:
        site = (people.get(profile.get("id")) or {}).get("site")
        if not site or overrides.blocked_campaign_host(site.get("url")):
            continue                    # a person already decided this one
        kind = ("withdrawn" if withdrawn(site)
                else "unconfirmed" if site.get("safe") is False
                else "compromised" if site.get("reason") == COMPROMISED else None)
        if kind:
            out[kind].append(f"{profile['name']} ({profile.get('officeLabel') or profile.get('state')}): "
                             f"{site['url']} - {site.get('reason')}")
    return {kind: sorted(lines) for kind, lines in out.items()}
