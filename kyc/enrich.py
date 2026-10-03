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
from .portraits import surname_of, title_is_about
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


# ---------------------------------------------------------------- campaign site

class _Page(html.parser.HTMLParser):
    """Title, a few meta tags, images, links, headings and text of one page."""

    _HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
    _SKIP = ("script", "style", "noscript", "template", "svg")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.meta, self.images, self.links, self.headings = "", {}, [], [], []
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
_PARKING_CODE = re.compile(r"parking-lander|LANDER_SYSTEM|sedoparking|parkingcrew|bodis\.com|"
                           r"park\.godaddy|domainmarket|dan\.com/", re.I)
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


def image_size(data):
    """``(width, height)`` of a PNG, JPEG, GIF or WebP from its bytes, or None."""
    import struct

    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8 " and len(data) >= 30:
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == b"VP8X" and len(data) >= 30:
            return (int.from_bytes(data[24:27], "little") + 1,
                    int.from_bytes(data[27:30], "little") + 1)
        return None
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


def portrait_shape(url, hinted=False):
    """``True`` when the image is head-and-shoulders shaped, ``False`` when it
    is not (a banner, a wordmark, an icon), ``None`` when it could not be read.

    A head-and-shoulders photograph is taller than it is wide - 4:5, 2:3.
    Logos, share cards, merchandise and group shots are square or wide: of
    nineteen images the first full run took that were not portraits, fifteen
    were. An image whose own name says it is a headshot may be square.
    """
    try:
        req = urllib.request.Request(url, headers=dict(
            _UA_WEB, Accept="image/jpeg,image/png,image/webp,image/*;q=0.8"))
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
            if response.status != 200:
                return False
            if not (response.headers.get("Content-Type") or "").startswith("image/"):
                return False
            data = response.read(MAX_BODY)
    except urllib.error.HTTPError as exc:
        return None if exc.code in (403, 429) or exc.code >= 500 else False
    except Exception:
        return None
    size = image_size(data)
    if not size or not all(size):
        return None
    width, height = size
    widest = 1.35 if hinted else 0.9
    return min(width, height) >= 200 and 0.5 <= width / height <= widest


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
    scored = []
    images = [(page.meta.get("og:image", ""), ""), (page.meta.get("twitter:image", ""), "")]
    for src, alt in images + page.images:
        src = (src or "").strip()
        if not src or src.startswith("data:"):
            continue
        url = urllib.parse.urljoin(base, src)
        if not url.startswith("https://"):
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
        in_file = surname in name_words or any(
            w.startswith(first) and w.endswith(surname) and len(w) <= len(first + surname)
            for w in name_words if first)
        in_alt = surname in alt_words
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


def read_site(profile, url, pause=1.0, extract=True, rivals=()):
    """Everything a campaign site gives, as a cache record."""
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
    pictures = portrait(page, final, profile)
    # Kept so validate can tell a NOT_A_PORTRAIT entry still means something.
    refused = [u for u, _ in pictures if u in overrides.NOT_A_PORTRAIT]
    if refused:
        record["notPortraits"] = refused
    for picture, hinted in [p for p in pictures if p[0] not in refused][:3]:
        if portrait_shape(picture, hinted) is True:
            record["portrait"] = picture
            break
    return record


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
    return new


def resolve_all(profiles, root=".", refresh=False, limit=None, log=print, workers=6,
                today=None):
    """Read Wikipedia infoboxes and campaign sites for everyone still running.

    Returns ``(cache, counts)``. A person read within STALE_DAYS is skipped
    unless *refresh*; an interrupted run resumes from the cache.
    """
    cache = load_cache(root) or {}
    people = cache.setdefault("people", {})
    today = today or datetime.date.today()
    cutoff = (today - datetime.timedelta(days=STALE_DAYS)).isoformat()
    wanted = [p for p in profiles if running(p) or checked_site(p)]
    todo = [p for p in wanted
            if refresh or (people.get(p["id"]) or {}).get("checked", "") < cutoff]
    if limit:
        todo = todo[:limit]
    log(f"  enrich: {len(todo)} of {len(wanted)} people to read "
        f"({sum(running(p) for p in wanted)} challengers still running)")

    linked = [p for p in todo if running(p) and p.get("wikipedia")]
    articles = fetch_articles([p["wikipedia"] for p in linked], log=log) if linked else {}
    for profile in linked:
        got = articles.get(profile["wikipedia"])
        if not got:
            continue
        title, text = got
        entry = people.setdefault(profile["id"], {})
        if not title_is_about(title, profile["name"]):
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
    for profile in profiles:
        entry = people.get(profile.get("id"))
        if not entry:
            continue
        committee = entry.get("site")
        if committee and withdrawn(committee) and profile.get("campaignSite") == committee["url"]:
            profile.pop("campaignSite", None)
            counts["withdrawn"] += 1
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
            continue
        if shown.get("description"):
            profile["campaignQuote"] = shown["description"]
            counts["quote"] += 1
        if shown.get("issuesUrl"):
            profile["campaignIssuesUrl"] = shown["issuesUrl"]
        if shown.get("issues") and fill_field(profile, "platforms", "; ".join(shown["issues"]),
                                              "campaign-site"):
            counts["issues"] += 1
        if shown.get("portrait") and not profile.get("photoSource") \
                and profile.get("source") == "fec-field" \
                and shown["portrait"] not in overrides.NOT_A_PORTRAIT:
            photos = [u for u in profile.get("photos") or [] if u != shown["portrait"]]
            profile["photos"] = [shown["portrait"]] + photos
            profile["photo_url"] = shown["portrait"]
            profile["photoSource"] = "campaign-site"
            counts["portrait"] += 1
    return counts


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
