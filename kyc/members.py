"""What a sitting member's own record says about them, by id (rule 86).

The rosters' Education, Previous Professions and "Policy Focus & Platforms"
columns were typed by hand with no source, and in wording that was not
even-handed: one member's platform read "Anti-abortion legislation" while
four others' read "Pro-life advocacy" (TRUST-05). None of it reaches a
profile now. In its place, each from a source tied to the member by the
bioguide id congress-legislators records, never by a search on a name
(rules 24, 32):

* **Platform** - the issues the member's official website lists, from the
  .house.gov / .senate.gov address congress-legislators holds. The issues
  index is the page the home page links as "Issues" (or "Priorities"); its
  items are the links to its own issue pages, in the site's own words - one
  level, as rule 38 takes a campaign's headings - or, on a page that lists
  none, its headings at one level. Nothing that names the member or anyone
  else ("Trump's One Big Beautiful Betrayal") is taken. A site with no such
  page is "Not listed on their official site", never the curated text. A
  site that turns the request away, or draws itself with script, concludes
  nothing (rule 8) until headless Chrome has tried it too.
* **Contact page** - the page the home page links as "Contact" (or "Email
  me"), linked only once a fetch shows it holds a form to write to the
  office, or leads to one (the verifier's soft-200 caveat on PROFILES-16).
* **District offices** - congress-legislators' legislators-district-offices
  file, keyed by bioguide id (PERSONA-14).
* **Education and careers** - the infobox of the Wikipedia article
  congress-legislators maps the bioguide id to, in its words, through
  :func:`kyc.normalize.fill_field` so the page badges the source. The
  Biographical Directory itself answers HTTP 403 to a script (2026-10-18).

Each read is dated in ``data/members.json``; a read that fails keeps the
last one (rule 8).
"""

import collections
import datetime
import html
import html.parser
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

from . import enrich
from .normalize import fill_field

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "members.json")
OFFICES_URL = ("https://unitedstates.github.io/congress-legislators/"
               "legislators-district-offices.json")
# Between two requests to official sites, all of which sit behind the same
# two chambers' infrastructure: one at a time, and never faster than this.
PAUSE = 1.5
# A member's site is read again after this many days; offices and articles
# on every run (one request, and one per fifty members).
STALE_DAYS = 27
MAX_ISSUES = 30

# Badges the page shows beside a field (assets/kyc.js FIELD_SOURCES).
SITE_SOURCE = "official-site"
ARTICLE_SOURCE = "member-wikipedia"

_BIOGUIDE = re.compile(r"^[A-Z]\d{6}$")
_OWN_HOST = re.compile(r"(?:^|\.)(?:house|senate)\.gov$")


def is_member(profile):
    """A profile keyed on a bioguide id: a member, sitting or archived."""
    return not profile.get("isCandidate") and bool(_BIOGUIDE.match(profile.get("id") or ""))


def own_host(url, website):
    """True when *url* is on the member's own site: the host of the address
    congress-legislators lists, or another host of the same chamber's
    domain that carries the same office name (``crankforms.house.gov`` for
    ``crank.house.gov``)."""
    host, home = enrich.host_of(url), enrich.host_of(website)
    if not host or not home:
        return False
    if host == home:
        return True
    if not (_OWN_HOST.search(host) and _OWN_HOST.search(home)):
        return False
    label, _, rest = home.partition(".")
    other, _, other_rest = host.partition(".")
    return other_rest == rest and other == label + "forms"


# ----------------------------------------------------------------- fetching

def chrome_path():
    """The Chrome or Chromium binary to render a page with, or None."""
    env = os.environ.get("CHROME")
    for path in (env, r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if path and os.path.exists(path):
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def chrome_dom(url, timeout=90):
    """The page as headless Chrome renders it, or ``""``; never raises."""
    exe = chrome_path()
    if not exe:
        return ""
    with tempfile.TemporaryDirectory() as profile_dir:
        args = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions",
                f"--user-data-dir={profile_dir}", "--virtual-time-budget=10000",
                "--dump-dom", url]
        try:
            done = subprocess.run(args, capture_output=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            return ""
    if done.returncode != 0:
        return ""
    return done.stdout.decode("utf-8", "replace")


# A page that is a gate, not the site: a bot wall's challenge, a refusal.
_GATE = re.compile(r"access\s+denied|request\s+rejected|just\s+a\s+moment|attention\s+required|"
                   r"verify\s+you\s+are\s+(?:a\s+)?human|are\s+you\s+a\s+robot|"
                   r"enable\s+javascript\s+(?:and\s+cookies\s+)?to\s+continue", re.I)


def readable(status, page):
    """True when a fetch gave a page to read: HTTP 200 and enough text."""
    return (status == 200 and len(page.body) >= 300
            and not _GATE.search(page.title + " " + page.body[:400]))


class _Anchors(html.parser.HTMLParser):
    """Each link's ``(href, label)``, where a link whose words are laid out
    in blocks - a card's title over its blurb, Senator Cruz's "Tax Reform"
    over "Promote jobs, growth, and opportunity" - is labelled by its first
    block alone. Read as one run of words, the card was an "issue" eight
    words long, and the cards whose blurbs ran longer were dropped, leaving
    a partial list that looked whole."""

    _BLOCKS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "br", "li")
    _SKIP = ("script", "style", "noscript", "template", "svg")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self._href, self._chunks, self._skip = [], None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "a":
            self._href, self._chunks = dict(attrs).get("href") or "", [[]]
        elif self._chunks is not None and tag in self._BLOCKS:
            self._chunks.append([])

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._chunks is not None:
            self._chunks.append([])

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(self._skip - 1, 0)
        elif tag == "a" and self._chunks is not None:
            blocks = [" ".join("".join(c).split()) for c in self._chunks]
            blocks = [b for b in blocks if b]
            self.links.append((self._href, blocks[0] if blocks else ""))
            self._href, self._chunks = None, None
        elif self._chunks is not None and tag in self._BLOCKS:
            self._chunks.append([])

    def handle_data(self, data):
        if not self._skip and self._chunks is not None:
            self._chunks[-1].append(data)


def anchors(markup):
    """``[(href, label)]`` for every link of *markup* (see :class:`_Anchors`)."""
    parser = _Anchors()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:            # a malformed page still yields what it had
        pass
    return parser.links


def parse(markup):
    """:func:`kyc.enrich.parse_page`, with each link labelled as
    :func:`anchors` reads it."""
    page = enrich.parse_page(markup)
    page.links = anchors(markup)
    return page


def get(url, pause=PAUSE, render=chrome_dom):
    """``(final url, status, page, how, markup)`` for one official page.

    Read plainly first; when that is turned away (401, 403, 429, a 2xx that
    is not 200, a server error), reaches nothing, or shows too little text
    to read - a page drawn by script - headless Chrome reads it. ``how`` is
    ``"http"`` or ``"chrome"``, or None when neither gave a page to read: no
    verdict (rule 8).
    """
    final, status, markup = enrich.fetch(url)
    page = parse(markup)
    if readable(status, page):
        return final, status, page, "http", markup
    if status is not None and 400 <= status < 500 and status not in (401, 403, 429):
        return final, status, page, None, markup
    time.sleep(pause)
    rendered = render(url) if render else ""
    shown = parse(rendered)
    if rendered and readable(200, shown):
        return url, 200, shown, "chrome", rendered
    return final, status, page, None, markup


# ------------------------------------------------------------- issues pages

# What a link to an issues index says, best first: "Issues", "On the
# Issues", "Key Issues"; then "Priorities", "Legislative priorities".
_INDEX_TEXT = (
    re.compile(r"^(?:(?:on|the|key|my|our|top)\s+)*issues(?:\s*(?:&|and)\s*legislation)?$", re.I),
    re.compile(r"^(?:(?:my|our|key|legislative|top)\s+)*priorities$", re.I),
)
_INDEX_PATH = re.compile(r"^(?:issues|key-issues|priorities|legislative-priorities)$", re.I)
# A link on the index that is a label of the list, not an item of it.
_LIST_LABEL = re.compile(
    r"^(?:(?:more|all|key|other|view\s+all|see\s+all|my|our|the|on\s+the|top|legislative)\s+)*"
    r"(?:issues?|priorities|platform|agenda|positions)$", re.I)
# A banner or a post linked under the issues path, not an issue.
_NOT_A_TOPIC = re.compile(r"\b(?:news\s+alert|press\s+releases?|fact\s+sheet|faq|"
                          r"frequently\s+asked|click\s+here|read\s+more|learn\s+more|"
                          r"(?:co-?)?sponsored\s+(?:legislation|bills)|voting\s+record|"
                          r"votes?\s+and\s+legislation|links?\s+to|committee\s+assignments|"
                          r"caucus\s+memberships?|committees\s+and\s+caucuses|"
                          r"community\s+project\s+funding|funding\s+requests?|"
                          r"legislative\s+process|how\s+congress\s+works|bill\s+search|"
                          r"ethics\s+approval|covid(?:-19)?\s+resources|"
                          r"congressionally\s+directed\s+spending)\b|"
                          r"^(?:legislation|cpf(?:\s+requests?)?|grants?)$",
                          re.I)
_TITLES = r"(?:president|vice\s+president|senator|sen|rep|representative|congressman|" \
          r"congresswoman|speaker|leader|governor|gov|secretary)\.?"


def index_links(page, base, website):
    """The issues index the home page links, best first (at most two)."""
    ranked = collections.defaultdict(list)
    for href, text in page.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target = urllib.parse.urljoin(base, href).split("#")[0]
        if not own_host(target, website) or target.rstrip("/") == base.rstrip("/"):
            continue
        text = " ".join((text or "").split())
        path = urllib.parse.unquote(urllib.parse.urlsplit(target).path).rstrip("/")
        last = path.rsplit("/", 1)[-1]
        for rank, pattern in enumerate(_INDEX_TEXT):
            if pattern.match(text):
                ranked[rank].append(target)
                break
        else:
            if _INDEX_PATH.match(last):
                ranked[len(_INDEX_TEXT)].append(target)
    out = []
    for rank in sorted(ranked):
        for target in ranked[rank]:
            if target.rstrip("/").lower() not in (o.rstrip("/").lower() for o in out):
                out.append(target)
    return out[:2]


def names_someone(text, own, others):
    """True when *text* names the member or anyone in *others*.

    *own* is the member's name; *others* is ``{"full": {folded full names},
    "surnames": {folded surnames}, "bare": {surnames that name someone
    alone}}``. A surname counts as a name when it is possessive ("Trump's"),
    follows a title ("Senator Cassidy"), or is one of the few that name
    someone on their own (the President's and the Vice President's) - so
    "Green Energy" is not about Al Green, and "Small Business" not about
    anyone.
    """
    seen = " ".join(enrich._words(text))
    words = set(seen.split())
    name = enrich._words(own)
    surname = enrich.fold(enrich.surname_of(own)) if own else ""
    first = next((w for w in name if len(w) >= 3), "")
    if (surname and surname in words) or (first and re.search(
            r"(?<![a-z])" + re.escape(first) + r"\s*'?s\b", enrich.fold(text))):
        return True
    for full in others.get("full", ()):
        if full and re.search(r"(?<![a-z0-9])" + re.escape(full) + r"(?![a-z0-9])", seen):
            return True
    folded = enrich.fold(text)
    for word in words & set(others.get("surnames", ())):
        if word in others.get("bare", ()):
            return True
        if re.search(r"(?<![a-z])" + re.escape(word) + r"\s*(?:'|\u2019)s?\b", folded) or re.search(
                r"\b" + _TITLES + r"\s+(?:[a-z]+\s+)?" + re.escape(word) + r"\b", folded):
            return True
    return False


def _clean(text):
    text = enrich._INVISIBLE.sub("", text or "")
    text = " ".join(text.split())
    text = re.sub(r"^[^\w\"'“‘(]+|[\s»›→>]+$", "", text, flags=re.U)
    return enrich._NUMBERING.sub("", text.strip(" :.-–—|•#*")).strip(" :.-–—|•")


def topic(text, own, others):
    """*text* as an issue, or ``""`` when it is furniture, a label of the
    list, a banner, a sentence, or names someone."""
    text = _clean(text)
    short = len(text) == 2 and text.isalpha() and text.isupper()     # "AI"
    if not (3 <= len(text) <= 60 or short) or len(text.split()) > 8:
        return ""
    if "{" in text or "}" in text or text.endswith(("?", "!")) or enrich._DANGLING.search(text):
        return ""
    if _LIST_LABEL.match(text) or _NOT_A_TOPIC.search(text) or enrich._NOT_AN_ISSUE.search(text):
        return ""
    if re.search(r"https?:|@|\d{3}[-.)\s]\d{3}", text):
        return ""
    if names_someone(text, own, others):
        return ""
    return text


class _Menus(html.parser.HTMLParser):
    """Each list item that holds a list of its own: its label, its link and
    its direct children's ``(href, text)`` - a site's menus, one level."""

    _SKIP = ("script", "style", "noscript", "template", "svg")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.lists, self.found, self._skip = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "li":
            self.stack.append({"label": [], "href": None, "children": [], "open": 0,
                               "parent": self.lists[-1] if self.lists else None})
        elif tag in ("ul", "ol"):
            owner = self.stack[-1] if self.stack else None
            if owner is not None:
                owner["open"] += 1
            self.lists.append(owner)
        elif tag == "a" and self.stack and not self.stack[-1]["open"] \
                and self.stack[-1]["href"] is None:
            self.stack[-1]["href"] = dict(attrs).get("href") or ""

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(self._skip - 1, 0)
        elif tag in ("ul", "ol") and self.lists:
            owner = self.lists.pop()
            if owner is not None:
                owner["open"] = max(owner["open"] - 1, 0)
        elif tag == "li" and self.stack:
            frame = self.stack.pop()
            text = " ".join("".join(frame["label"]).split())
            parent = frame["parent"]
            if parent is not None and any(parent is f for f in self.stack):
                parent["children"].append((frame["href"], text))
            if frame["children"]:
                self.found.append((text, frame["href"], frame["children"]))

    def handle_data(self, data):
        if not self._skip and self.stack and not self.stack[-1]["open"]:
            self.stack[-1]["label"].append(data)


_MENU_WORDS = re.compile(r"\b(?:toggle|sub-?menu|expand|collapse|show|open|menu|dropdown|"
                         r"navigation)\b", re.I)


def menus(markup):
    """``[(label, href, [(href, text)])]``: every menu with a list under it."""
    parser = _Menus()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:            # a malformed page still yields what it had
        pass
    return [(" ".join(_MENU_WORDS.sub(" ", label).split()), href, children)
            for label, href, children in parser.found]


def menu_issues(markup, base, website, own, others):
    """The issues a site's own "Issues" menu lists, one item per page it
    links, in the menu's words: Senator Boozman's site has no issues index
    to read, and lists its nine issues under that menu."""
    for label, href, children in menus(markup):
        last = urllib.parse.urlsplit(urllib.parse.urljoin(base, href or "")).path
        last = last.rstrip("/").rsplit("/", 1)[-1]
        if not (any(p.match(label) for p in _INDEX_TEXT) or (href and _INDEX_PATH.match(last))):
            continue
        items, targets = [], set()
        for child_href, text in children:
            if not child_href or child_href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            target = urllib.parse.urljoin(base, child_href).split("#")[0]
            if not own_host(target, website):
                continue
            key = target.rstrip("/").lower()
            item = topic(text, own, others)
            if key in targets or not item or item.lower() in (i.lower() for i in items):
                continue
            targets.add(key)
            items.append(item)
        if len(items) >= 3:
            return items[:MAX_ISSUES]
    return []


def listed_issues(page, index_url, own, others):
    """The issues an official site's index lists: its links to its own issue
    pages one level below it (``/issues/health``, or the House template's
    ``/issues/issue/?IssueID=14895``), one item per page, in the link's
    words. A page under one of those (``/issues/health/medicare``) is a
    sub-point, not an issue of its own, as rule 38 keeps to one level."""
    under = urllib.parse.urlsplit(index_url).path.rstrip("/").lower() + "/"
    found = {"issue": ({}, []), "child": ({}, [])}
    for href, text in page.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target = urllib.parse.urljoin(index_url, href).split("#")[0]
        parts = urllib.parse.urlsplit(target)
        if enrich.host_of(target) != enrich.host_of(index_url):
            continue
        path = parts.path.lower().rstrip("/")
        rest = path[len(under):] if path.startswith(under) else None
        segments = path.split("/")
        if "issueid=" in parts.query.lower() or (
                len(segments) >= 3 and segments[-2] in ("issues", "issue", "priorities")):
            kind = "issue"
        elif rest and "/" not in rest:
            kind = "child"
        else:
            continue
        by_target, order = found[kind]
        key = (path, parts.query.lower())
        item = topic(text, own, others)
        if key not in by_target:
            order.append(key)
            by_target[key] = item
        elif not by_target[key] and item:
            by_target[key] = item
    # Pages filed under an issues path say what they are; a page that is
    # merely below the index (Matsui's "On The Issues" is /legislative-work,
    # whose children are her voting record and legislation) counts only
    # where there are none.
    for kind in ("issue", "child"):
        by_target, order = found[kind]
        items = []
        for key in order:
            item = by_target[key]
            if item and item.lower() not in (i.lower() for i in items):
                items.append(item)
        if len(items) >= 3:
            return items[:MAX_ISSUES]
    return []


def home_issues(page, home_url, own, others):
    """The issue pages a home page links directly under its own ``/issues/``
    (or ``/priorities/``) path, one item per page, in the links' words."""
    for path in ("/issues", "/priorities"):
        items = listed_issues(page, urllib.parse.urljoin(home_url, path), own, others)
        if items:
            return items
    return []


def page_issues(page, index_url, home, own, others):
    """An issues page whose issue pages sit at the top of the site
    (DesJarlais's /issues lists /agriculture, /health-care): the links that
    page carries and the home page does not - its own list, not the site's
    navigation - at no deeper a level than the index itself."""
    def targets(shown, base):
        for href, text in shown.links:
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            target = urllib.parse.urljoin(base, href).split("#")[0]
            if enrich.host_of(target) == enrich.host_of(index_url):
                yield target.rstrip("/").lower(), text
    on_home = {t for t, _ in targets(home, index_url)}
    depth = urllib.parse.urlsplit(index_url).path.strip("/").count("/") + 1
    items, seen = [], set()
    for target, text in targets(page, index_url):
        path = urllib.parse.urlsplit(target).path.strip("/")
        if (target in on_home or target in seen or not path or path.count("/") + 1 > depth
                or target == index_url.rstrip("/").lower()):
            continue
        seen.add(target)
        item = topic(text, own, others)
        if item and item.lower() not in (i.lower() for i in items):
            items.append(item)
    return items[:MAX_ISSUES] if 3 <= len(items) <= MAX_ISSUES else []


def heading_issues(page, own, others):
    """An issues page that links no issue pages: its section headings at one
    level, read as a campaign's are (rule 38)."""
    rivals = sorted(others.get("surnames", ()))
    return [i for i in enrich.issue_headings(page, own, rivals=rivals, limit=MAX_ISSUES)
            if topic(i, own, others)]


# ------------------------------------------------------------- contact pages

# "Contact", "Contact Steny", "Contact Steny's Office", "Email Chris": a
# link's words name a way to write; whether it leads to one is checked by
# fetching it (holds_form), never assumed from the words.
_CONTACT_TEXT = re.compile(
    r"^(?:contact(?:\s+[\w'’.]+){0,3}|e-?mail(?:\s+[\w'’.]+){1,2}|"
    r"write\s+(?:to\s+)?(?:me|us|the\s+\w+|[\w'’.]+)|"
    r"send\s+(?:me\s+)?(?:an\s+)?(?:e-?mail|message)|get\s+in\s+touch)$", re.I)
# Words that make a "Contact ..." link something other than a way to write.
_CONTACT_NOT = re.compile(r"\b(?:information|info|tracing|lenses?|sign\s*up|newsletter|"
                          r"subscribe|press|media)\b", re.I)
_CONTACT_PATH = re.compile(r"^(?:contact(?:-[\w-]+)?|email-me|write-to-[\w-]+|e-?mail|get-in-touch)$",
                           re.I)
_FORM = re.compile(r"<form\b([^>]*)>(.*?)</form\s*>", re.I | re.S)
_FIELD = re.compile(r"<textarea\b|<(?:input|select)\b[^>]*\b(?:name|id)\s*=\s*[\"'][^\"']*"
                    r"(?:zip|postal|address|email|message|subject|first|last|phone|topic)", re.I)
_NOT_A_MESSAGE = re.compile(r"\bsearch\b|signup|sign-up|newsletter|subscribe", re.I)
_FORM_FRAME = re.compile(r"<iframe\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
_LOST = re.compile(r"page\s+not\s+found|\b404\b|no\s+longer\s+available", re.I)


def contact_links(page, base, website):
    """The contact page the home page links, best first (at most two)."""
    by_text, by_path = [], []
    for href, text in page.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target = urllib.parse.urljoin(base, href).split("#")[0]
        if not own_host(target, website) or target.rstrip("/") == base.rstrip("/"):
            continue
        text = " ".join((text or "").split())
        last = urllib.parse.urlsplit(target).path.rstrip("/").rsplit("/", 1)[-1]
        if _CONTACT_TEXT.match(text) and not _CONTACT_NOT.search(text) and target not in by_text:
            by_text.append(target)
        elif _CONTACT_PATH.match(last) and target not in by_path:
            by_path.append(target)
    out = []
    for target in by_text + by_path:
        if target.rstrip("/").lower() not in (o.rstrip("/").lower() for o in out):
            out.append(target)
    return out[:2]


def holds_form(markup, url, website):
    """True when the page holds a form to write to the office: a form that
    is not a site search or a newsletter sign-up and asks for a message, an
    address, a ZIP code or an email - or a frame of the office's own forms
    host (``crankforms.house.gov``)."""
    for attrs, body in _FORM.findall(markup or ""):
        if _NOT_A_MESSAGE.search(attrs):
            continue
        if _FIELD.search(body):
            return True
    for src in _FORM_FRAME.findall(markup or ""):
        target = urllib.parse.urljoin(url, src)
        if own_host(target, website) and "form" in enrich.host_of(target) + target.lower():
            return True
        # The House's shared constituent-mail form (Clyburn's "Get In Touch"
        # frames iqconnect.house.gov/iqextranet/EForm.aspx), on a page of the
        # member's own site.
        if enrich.host_of(target) == "iqconnect.house.gov" and "/eform" in target.lower():
            return True
    return False


def _markup_of(url):
    final, status, markup = enrich.fetch(url)
    return final, status, markup


def contact_page(page, base, website, pause=PAUSE, fetch=_markup_of):
    """``(url, status)``: the office's checked contact page, or None.

    A page the home page links as Contact that holds a form, or links one
    ("Email me") that does. ``status`` is ``"checked"`` when one was found,
    ``"none"`` when every candidate was read and none held a form, None when
    a read was inconclusive (rule 8).
    """
    inconclusive = False
    for link in contact_links(page, base, website):
        time.sleep(pause)
        final, status, markup = fetch(link)
        if status != 200 or not own_host(final, website):
            inconclusive = inconclusive or status is None or status in (401, 403, 429) \
                or (status or 0) >= 500
            continue
        shown = parse(markup)
        if _LOST.search(shown.title):
            continue
        if holds_form(markup, final, website):
            return link, "checked"
        # A contact index ("Email me", "Write to me") that leads to the form.
        for href, text in shown.links:
            target = urllib.parse.urljoin(final, href or "").split("#")[0]
            text = " ".join((text or "").split())
            if (not href or href.startswith(("#", "mailto:", "tel:"))
                    or not own_host(target, website) or not _CONTACT_TEXT.match(text)
                    or _CONTACT_NOT.search(text)
                    or target.rstrip("/") == final.rstrip("/")):
                continue
            time.sleep(pause)
            final2, status2, markup2 = fetch(target)
            if status2 == 200 and own_host(final2, website) and holds_form(markup2, final2, website):
                return target, "checked"
            inconclusive = inconclusive or status2 is None or status2 in (401, 403, 429)
            break
    return None, (None if inconclusive else "none")


# ------------------------------------------------------------- one member

def read_site(profile, others, pause=PAUSE, render=chrome_dom, fetch=_markup_of, today=None):
    """Everything a member's official site gives, as a cache record."""
    website = profile.get("website") or ""
    today = (today or datetime.date.today()).isoformat()
    record = {"url": website, "read": today}
    final, status, page, how, markup = get(website, pause, render)
    record["status"] = status
    if not how:
        record["verdict"] = None
        record["reason"] = f"HTTP {status}" if status else "unreachable"
        return record
    record["via"] = how
    if not own_host(final, website):
        record["verdict"] = None
        record["reason"] = f"moved to {enrich.host_of(final)}"
        return record
    if not enrich.names_candidate(profile, page.title + " " + page.body, enrich.host_of(final)):
        record["verdict"] = None
        record["reason"] = "the page does not name the member"
        return record
    name = profile["name"]
    inconclusive, pages = False, []
    for link in index_links(page, final, website):
        time.sleep(pause)
        final2, status2, issues, how2, _ = get(link, pause, render)
        if not how2:
            inconclusive = inconclusive or status2 is None or status2 in (401, 403, 429)                 or (status2 or 0) >= 500
            continue
        if not own_host(final2, website):
            continue
        pages.append((final2, issues))
        items = listed_issues(issues, final2, name, others)
        if items:
            record.update(issues=items, issuesUrl=final2, how="index")
            break
    if not record.get("issues"):
        # No index to read, or one that links nothing: the site's own
        # "Issues" menu, then an index page's headings.
        items = menu_issues(markup, final, website, name, others)
        if items:
            record.update(issues=items, issuesUrl=pages[0][0] if pages else final, how="menu")
    if not record.get("issues"):
        for where, shown in pages:
            items = page_issues(shown, where, page, name, others)
            if items:
                record.update(issues=items, issuesUrl=where, how="page")
                break
    if not record.get("issues"):
        for where, shown in pages:
            items = heading_issues(shown, name, others)
            if items:
                record.update(issues=items, issuesUrl=where, how="headings")
                break
    if not record.get("issues") and not pages:
        # No issues index at all, but the home page links its own issue
        # pages (Hoyer's "Issues" section is an anchor on the home page over
        # /issues/federal-employees, /issues/environment ...): those links.
        items = home_issues(page, final, name, others)
        if items:
            record.update(issues=items, issuesUrl=final, how="home")
    if record.get("issues"):
        record["verdict"] = "listed"
    elif inconclusive:
        record["verdict"] = None
        record["reason"] = "an issues page could not be read"
    else:
        record["verdict"] = "none"
        record["reason"] = "no page or menu of the site lists issues"
        if pages:
            # The page that was read and lists none (a priorities page in
            # prose): the reader is pointed to it, not told it is empty.
            record["pageRead"] = pages[0][0]
    contact, found = contact_page(page, final, website, pause, fetch)
    record["contactStatus"] = found
    if contact:
        record["contact"] = contact
    return record


def people_named(profiles, executive=None):
    """The names a platform line may not carry: every member's, and the
    President's, the Vice President's and the Cabinet's (``others`` for
    :func:`names_someone`)."""
    full, surnames, bare = set(), set(), set()
    names = [p.get("name") for p in profiles if is_member(p)]
    executive = executive or {}
    top = [(executive.get(k) or {}).get("name") for k in ("president", "vicePresident")]
    cabinet = [((o.get("holder") or {}).get("name")) for o in executive.get("offices") or []]
    for name in names + top + cabinet:
        if not name:
            continue
        words = enrich._words(name)
        if len(words) >= 2:
            full.add(" ".join(words))
        surname = enrich.fold(enrich.surname_of(name))
        if len(surname) >= 3:
            surnames.add(surname)
    for name in top:
        if name:
            bare.add(enrich.fold(enrich.surname_of(name)))
    return {"full": full, "surnames": surnames, "bare": bare}


# ------------------------------------------------------------ the articles

_NOT_A_CAREER = re.compile(r"^(?:politician|legislator|public\s+servant|statesman|"
                           r"stateswoman|congress(?:man|woman|person))$", re.I)


def article_facts(wikitext):
    """``{education, occupation}`` from a member's infobox, in its words.

    "Politician" alone is not a previous career: it is the office the
    profile is about. An occupation that says nothing else is left out, not
    reworded.
    """
    facts = enrich.wiki_facts(wikitext)
    out = {}
    if facts.get("education"):
        out["education"] = facts["education"]
    occupation = "; ".join(p for p in (facts.get("occupation") or "").split("; ")
                           if p and not _NOT_A_CAREER.match(p.strip()))
    if occupation:
        out["occupation"] = occupation
    return out


def read_articles(profiles, log=print, fetch=enrich.fetch_articles):
    """``{bioguide: {title, requested, education?, occupation?}}`` for every
    member whose id congress-legislators maps to an article. A batch that
    fails is absent from the result: nothing is concluded (rule 8)."""
    from .portraits import article_is_theirs

    members = [p for p in profiles if is_member(p) and p.get("wikipedia")]
    got = fetch([p["wikipedia"] for p in members], log=log)
    out = {}
    for profile in members:
        found = got.get(profile["wikipedia"])
        if not found:
            continue
        title, text = found
        entry = {"requested": profile["wikipedia"], "title": title}
        if article_is_theirs(title, profile):
            entry.update(article_facts(text))
        else:
            entry["refused"] = "the article it leads to does not carry their surname"
        out[profile["id"]] = entry
    return out


# ------------------------------------------------- the Congressional Directory

GOVINFO = "https://api.govinfo.gov"
DIRECTORY_SOURCE = "congressional-directory"
_ENTRY_END = re.compile(r"\n[ \t]*Congressional Office[ \t]*\n[ \t]*(https?://\S+)")
_LABEL = re.compile(r"(?:^|;\s+)([a-z][a-z ]+?):\s+")


def directory_entries(text):
    """``[(official site, name, {label: text})]`` from the Congressional
    Directory's plain text: each member's paragraph ("RICK LARSEN, Democrat,
    of Everett, WA; born ...; education: ...; professional history: ...;
    election history: ...") and the office web address printed under it,
    which is how an entry is tied to a member - the address
    congress-legislators lists for their bioguide id - never the name."""
    out = []
    # GovInfo serves the text with CRLF line ends, inside a <pre>.
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "<pre" in text[:2000].lower():
        text = html.unescape(re.sub(r"</?(?:html|head|body|pre|title|meta)[^>]*>", "", text,
                                    flags=re.I))
    for match in _ENTRY_END.finditer(text):
        paragraph = re.split(r"\n[ \t]*\n", text[:match.start()].rstrip())[-1]
        joined = ""
        for line in (l.strip() for l in paragraph.splitlines()):
            # "school board member, 1985-" / "89": a range broken at the hyphen.
            joined = joined + line if joined.endswith("-") else (
                f"{joined} {line}" if joined else line)
        if "; born" not in joined and "education:" not in joined:
            continue
        name = joined.split(",", 1)[0].strip()
        fields, marks = {}, list(_LABEL.finditer(joined))
        for i, mark in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(joined)
            value = joined[mark.end():end].strip().rstrip(".").strip()
            if value:
                fields[mark.group(1).strip()] = value
        out.append((match.group(1).rstrip(".,"), name, fields))
    return out


def directory_facts(fields):
    """``{education, careers}`` from one entry, in the Directory's words:
    its education, and its professional history with any military service
    after it, labelled as the Directory labels it."""
    out = {}
    if fields.get("education"):
        out["education"] = fields["education"]
    careers = fields.get("professional history") or ""
    if fields.get("military service"):
        careers = "; ".join(p for p in (careers, "military service: " + fields["military service"])
                            if p)
    if careers:
        out["careers"] = careers
    return out


def printed_as(name, printed):
    """True when the Directory's printed name carries the member's surname
    ("MARIO DIAZ-BALART"), or, for a name in the Spanish form, one of the
    family names after the first name ("PABLO JOSE HERNANDEZ" for Pablo
    José Hernández Rivera)."""
    seen = set(enrich._words(printed))
    surname = enrich._words(enrich.surname_of(name))
    if surname and all(w in seen for w in surname):
        return True
    rest = [w for w in enrich._words(name)[1:] if len(w) >= 4 and w not in enrich._GENERATIONAL]
    return any(w in seen for w in rest)


def match_directory(profiles, entries):
    """``({bioguide: entry}, [problem])``: each entry joined to the member
    whose official site congress-legislators lists at the same address, and
    kept only when the entry's name carries that member's surname too."""
    by_host = collections.defaultdict(list)
    for site, name, fields in entries:
        by_host[enrich.host_of(site)].append((site, name, fields))
    out, problems_found = {}, []
    for profile in profiles:
        if not is_member(profile) or not profile.get("website"):
            continue
        found = by_host.get(enrich.host_of(profile["website"])) or []
        if len(found) != 1:
            if len(found) > 1:
                problems_found.append(f"{profile['id']}: {len(found)} entries at {profile['website']}")
            continue
        site, name, fields = found[0]
        if not printed_as(profile["name"], name):
            problems_found.append(f"{profile['id']} ({profile['name']}): the entry at {site} "
                                  f"is printed as {name}")
            continue
        facts = directory_facts(fields)
        if facts:
            out[profile["id"]] = dict(facts, site=site, printedAs=name)
    return out, problems_found


def read_directory(congress, key, log=print, get=None):
    """``(edition, text)`` of the latest Congressional Directory GovInfo
    publishes for *congress*, or ``(None, "")`` when it cannot be read."""
    def fetch_text(url):
        sep = "&" if "?" in url else "?"
        request = urllib.request.Request(f"{url}{sep}api_key={key}",
                                         headers={"User-Agent": "know-your-candidate/2.1"})
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read().decode("utf-8", "replace")

    get = get or fetch_text
    first_year = 1789 + 2 * (int(congress) - 1)
    try:
        listing = json.loads(get(f"{GOVINFO}/published/{first_year}-01-01?collection=CDIR"
                                 "&pageSize=100&offsetMark=*"))
        editions = sorted((p for p in listing.get("packages") or []
                           if str(p.get("congress")) == str(congress)),
                          key=lambda p: p.get("dateIssued") or "")
        if not editions:
            log(f"  [warn] GovInfo lists no Congressional Directory for the {congress}th Congress")
            return None, ""
        edition = editions[-1]["packageId"]
        return edition, get(f"{GOVINFO}/packages/{edition}/txt")
    except Exception as exc:             # nothing is concluded from a failed read
        log(f"  [warn] the Congressional Directory could not be read: {exc}")
        return None, ""


# ---------------------------------------------------------- district offices

_OFFICE_KEYS = ("building", "address", "suite", "city", "state", "zip", "phone", "hours")


def district_offices(rows):
    """``{bioguide: [office]}`` from legislators-district-offices, each office
    only the fields a reader needs (no coordinates, no fax)."""
    out = {}
    for entry in rows or []:
        bioguide = ((entry.get("id") or {}).get("bioguide") or "").upper()
        if not _BIOGUIDE.match(bioguide):
            continue
        offices = []
        for office in entry.get("offices") or []:
            kept = {k: " ".join(str(office[k]).split()) for k in _OFFICE_KEYS
                    if office.get(k) not in (None, "")}
            if kept.get("city") and (kept.get("phone") or kept.get("address")):
                offices.append(kept)
        if offices:
            out[bioguide] = offices
    return out


# --------------------------------------------------------------- the cache

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
    """A read that concludes nothing keeps what the last good read of the
    same address found (rule 8), with this attempt noted."""
    if new.get("verdict") is None and old and old.get("url") == new.get("url") \
            and old.get("verdict") is not None:
        return dict(old, lastTry={"read": new.get("read"), "reason": new.get("reason")})
    if new.get("contactStatus") is None and old and old.get("url") == new.get("url") \
            and old.get("contact"):
        new = dict(new, contact=old["contact"], contactStatus=old.get("contactStatus"))
    return new


def refresh(profiles, root=".", executive=None, today=None, limit=None, sites=True,
            ids=None, log=print, fetch_json=None, articles=read_articles,
            site_reader=read_site, pause=PAUSE, congress=None, key=None,
            directory=read_directory):
    """Read every source into the cache and save it; returns the cache."""
    from .legislators import LegislatorsError, fetch_json as _fetch_json

    fetch_json = fetch_json or _fetch_json
    today = today or datetime.date.today()
    stamp = today.isoformat()
    cache = load_cache(root) or {}
    members = [p for p in profiles if is_member(p) and not p.get("formerMember")]

    if congress and key:
        edition, text = directory(congress, key, log=log)
        entries = directory_entries(text)
        if edition and len(entries) >= 400:
            matched, issues = match_directory(members, entries)
            cache["directory"] = {"edition": edition, "read": stamp, "entries": len(entries),
                                  "byId": matched, "unmatched": issues}
            log(f"  members: {len(matched)} of {len(members)} members in the Congressional "
                f"Directory ({edition}, {len(entries)} entries)")
        elif edition:
            # A directory that parsed short is a changed format, not a
            # Congress that lost its members: the last read stands (rule 8).
            log(f"  [warn] {edition} gave {len(entries)} entries; the last read kept")

    try:
        rows = fetch_json(OFFICES_URL)
        cache["offices"] = {"source": OFFICES_URL, "read": stamp,
                            "byId": district_offices(rows)}
        log(f"  members: district offices for {len(cache['offices']['byId'])} members")
    except LegislatorsError as exc:
        log(f"  [warn] district offices not read, the last read kept: {exc}")

    found = articles(members, log=log)
    if found:
        kept = cache.setdefault("articles", {})
        for bioguide, entry in found.items():
            kept[bioguide] = dict(entry, read=stamp)
        log(f"  members: {sum(1 for e in found.values() if e.get('education'))} educations, "
            f"{sum(1 for e in found.values() if e.get('occupation'))} occupations "
            f"from {len(found)} articles")

    if sites:
        others = people_named(profiles, executive)
        read = cache.setdefault("sites", {})
        cutoff = (today - datetime.timedelta(days=STALE_DAYS)).isoformat()
        todo = [p for p in members if p.get("website")
                and (ids is None or p["id"] in ids)
                and (ids is not None or (read.get(p["id"]) or {}).get("read", "") < cutoff
                     or (read.get(p["id"]) or {}).get("url") != p["website"])]
        if limit:
            todo = todo[:limit]
        log(f"  members: {len(todo)} official sites to read")
        for done, profile in enumerate(todo, start=1):
            record = site_reader(profile, others, pause=pause, today=today)
            read[profile["id"]] = _keep(read.get(profile["id"]), record)
            if done % 25 == 0:
                save_cache(cache, root)
                log(f"    {done}/{len(todo)} read")
            time.sleep(pause)
        for bioguide in [b for b in read if b not in {p["id"] for p in members}]:
            del read[bioguide]
    cache["read"] = stamp
    save_cache(cache, root)
    return cache


# ---------------------------------------------------------------- apply

def fields_from(profile, source):
    """The fields of *profile* filled from *source*."""
    return [f for f, s in (profile.get("fieldSources") or {}).items() if s == source]


def apply_cache(profiles, cache):
    """Fill each member's education, careers and platform from the cache,
    with the source recorded for the page; attach district offices and a
    checked contact page. A site record applies only while the profile
    links the address it was read from, an article's only while it links
    that article."""
    counts = collections.Counter()
    cache = cache or {}
    offices = (cache.get("offices") or {}).get("byId") or {}
    offices_read = (cache.get("offices") or {}).get("read")
    articles = cache.get("articles") or {}
    sites = cache.get("sites") or {}
    directory = (cache.get("directory") or {}).get("byId") or {}
    directory_edition = (cache.get("directory") or {}).get("edition")
    for profile in profiles:
        if not is_member(profile):
            continue
        bioguide = profile["id"]
        if bioguide in offices and not profile.get("formerMember"):
            profile["districtOffices"] = offices[bioguide]
            profile["districtOfficesRead"] = offices_read
            counts["offices"] += 1
        listed = directory.get(bioguide) or {}
        if listed and enrich.host_of(listed.get("site")) == enrich.host_of(profile.get("website")):
            # The Congressional Directory first: Congress's own printed
            # record, compiled from each member's office.
            if listed.get("education") and fill_field(profile, "education", listed["education"],
                                                      DIRECTORY_SOURCE):
                counts["education"] += 1
            if listed.get("careers") and fill_field(profile, "previous_professions",
                                                    listed["careers"], DIRECTORY_SOURCE):
                counts["careers"] += 1
            if fields_from(profile, DIRECTORY_SOURCE):
                profile["directoryEdition"] = directory_edition
        article = articles.get(bioguide) or {}
        if article.get("requested") and article["requested"] == profile.get("wikipedia") \
                and not article.get("refused"):
            if article.get("education") and fill_field(profile, "education",
                                                        article["education"], ARTICLE_SOURCE):
                counts["education"] += 1
            if article.get("occupation") and fill_field(profile, "previous_professions",
                                                         article["occupation"], ARTICLE_SOURCE):
                counts["occupation"] += 1
        site = sites.get(bioguide) or {}
        if not site or site.get("url") != profile.get("website") or profile.get("formerMember"):
            continue
        if site.get("issues") and fill_field(profile, "platforms", "; ".join(site["issues"]),
                                             SITE_SOURCE):
            profile["officialIssuesUrl"] = site["issuesUrl"]
            profile["platformRead"] = site.get("read")
            counts["platform"] += 1
        elif site.get("verdict") == "none" and profile.get("quality", {}).get("platforms"):
            # Read, and the site lists no issues: said as that, not as "No
            # data", which is a claim that nobody looked (rule 19).
            profile["quality"]["platforms"] = "not_listed"
            profile["platformRead"] = site.get("read")
            counts["platform_not_listed"] += 1
        if site.get("contact") and not profile.get("contactForm"):
            profile["contactForm"] = site["contact"]
            profile["contactFormVia"] = SITE_SOURCE
            profile["contactFormChecked"] = site.get("read")
            counts["contact"] += 1
    return counts


def problems(profiles, cache):
    """``[(level, code, message, detail)]`` for the build to report."""
    if not cache:
        return [("warn", "members-unread",
                 f"no {CACHE_PATH}; run 'members' for members' platforms, education, "
                 "careers, contact pages and district offices", [])]
    out = []
    sites = cache.get("sites") or {}
    seated = [p for p in profiles if is_member(p) and not p.get("formerMember")]
    unread = [f"{p['id']} ({p['name']})" for p in seated if p["id"] not in sites]
    if unread:
        out.append(("warn", "members-site-unread",
                    f"{len(unread)} members' official sites have not been read; run 'members'",
                    unread))
    unsure = [f"{p['id']} ({p['name']}): {p.get('website')} - {sites[p['id']].get('reason')}"
              for p in seated if (sites.get(p["id"]) or {}).get("verdict") is None
              and p["id"] in sites]
    if unsure:
        out.append(("warn", "members-site-inconclusive",
                    f"{len(unsure)} members' official sites could not be read, so their "
                    "platform reads \"No data\"", unsure))
    refused = [f"{b}: {e.get('requested')} -> {e.get('title')}"
               for b, e in sorted((cache.get("articles") or {}).items()) if e.get("refused")]
    if refused:
        out.append(("warn", "members-article-refused",
                    f"{len(refused)} members' mapped articles lead to a title without their "
                    "surname; nothing was taken from them", refused))
    return out
