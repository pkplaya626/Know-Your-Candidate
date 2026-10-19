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
from .overrides import OFFICIAL_ISSUES_NOT_A_LIST

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
                   r"enable\s+javascript\s+(?:and\s+cookies\s+)?to\s+continue|"
                   # The Senate's firewall: "Senate.gov - Unauthorized ... a
                   # potential security risk was detected" (2026-10-18).
                   r"\bunauthorized\b|potential\s+security\s+risk", re.I)


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

    _BLOCKS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li")
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


# "<br>", "<br/>" and the malformed "</br>" alike: Senator Hoeven's heading
# is "Sponsored &amp;</br>Co-Sponsored Legislation", which an end tag cut
# to "Sponsored &".
_BREAK = re.compile(r"</?\s*br\b[^>]*>", re.I)


def parse(markup):
    """:func:`kyc.enrich.parse_page`, with each link labelled as
    :func:`anchors` reads it. A line break is a space: Senator Whitehouse's
    headings are "Honoring<br>Veterans", which read as "HonoringVeterans",
    and Senator Curtis's "AI, Social Media, <br>and youth Safety" as its
    first line alone."""
    markup = _BREAK.sub(" ", markup or "")
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
    # "Policy Issues" (Ocasio-Cortez's, over /legislation/climate ...).
    re.compile(r"^(?:(?:on|the|key|my|our|top|policy)\s+)*issues(?:\s*(?:&|and)\s*legislation)?$",
               re.I),
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
                          r"congressionally\s+directed\s+spending|project\s+requests?|"
                          r"disclosure\s+page|legislative\s+action|committee\s+work|"
                          r"my\s+caucuses|travel\s+abroad|passports?|academy\s+nominations?|"
                          r"application\s+form|bills?\s+i\S*\s+(?:co-?)?sponsored|"
                          r"sponsored\s*/\s*co-?sponsored|\d{4}\s+in\s+review|annual\s+report|"
                          r"year\s+report|request\s+disclosures?|constituent\s+services|"
                          r"community\s+projects|"
                          # Services and notices filed among the issues
                          # (reviews of PR #106, 2026-10-18): Boebert's
                          # "Mobile Office Hours", Pingree's "Grant
                          # Opportunities", Malliotakis's 2020 "Paycheck
                          # Protection Program Portal Opening", Norcross's
                          # "FY27 Appropriations Requests" and "Government
                          # Shutdown Resources", Gillibrand's "Know More
                          # About the Senator", Mfume's "Community issues
                          # and events".
                          r"office\s+hours|grant\s+opportunities|portal|"
                          r"appropriations\s+requests?|cpf\s+requests?|authorization\s+requests?|"
                          r"know\s+more\s+about|shutdown\s+information|"
                          r"tele(?:phone)?-?\s*town\s*halls?|"
                          r"about\s+(?:the\s+)?(?:senator|congressman|congresswoman|"
                          r"representative|member|delegate|commissioner)|"
                          r"(?:shutdown|covid(?:-19)?|coronavirus|disaster)\s+resources)\b|"
                          r"\bcommunity\b.*\bevents$|"
                          # A help page after a storm, and the district as
                          # a page of its own ("9th District").
                          r"^(?:hurricanes?|storms?|floods?|wildfires?|derailment)\b.*\bresources\b|"
                          r"^(?:local\s+)?resources(?:\s+for\b.*)?$|"
                          r"^(?:the\s+)?(?:\d+(?:st|nd|rd|th)\s+)?district$|"
                          r"\boffices?$|\bupdates?$|current\s+legislation|^covid\b.*\bresources$|"
                          # The House template's stock category "Congress",
                          # whose page is "news and information related to
                          # Congress": not an issue a member chose.
                          r"^(?:legislation|cpf(?:\s+requests?)?|grants?|congress)$",
                          re.I)
# A line cut short: "Sponsored &", "AI, Social Media,".
_CUT = re.compile(r"[&,;/(]\s*$|\b(?:and|or)\s*$", re.I)
# A title's possessive names its holder: Scott Peters's "President's
# Administration" is about a person, as "Trump's" would be.
_TITLE_POSSESSIVE = re.compile(r"\b(?:president|vice\s+president|speaker|governor|senator|"
                               r"congress(?:man|woman))\s*(?:'|’)s?(?![a-z])", re.I)
# The House template's stock issue categories, each over the blurb "Learn
# about news and information related to ...": a site that lists these and
# nothing of its own has not chosen a platform (figures.house.gov/issues,
# 2026-10-18).
STOCK_CATEGORIES = frozenset(("congress", "economy", "education", "energy", "health", "veterans"))


def stock_list(items):
    """True when *items* are only the House template's stock categories."""
    return bool(items) and all(" ".join(i.split()).lower() in STOCK_CATEGORIES for i in items)


def same_issue(text):
    """A key under which two spellings of one item meet: Hoeven's "Jobs,
    Economy, and Fiscal Responsibility" and "Jobs, Economy, Fiscal
    Responsibility" are one issue."""
    words = re.findall(r"[a-z0-9]+", enrich.fold(text or ""))
    return " ".join(w for w in words if w not in ("and", "the", "of", "amp"))


def dedupe(items):
    """*items* with each issue once, in the first spelling given."""
    out, seen = [], set()
    for item in items:
        key = same_issue(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out
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
    if _TITLE_POSSESSIVE.search(text):
        return True
    for full in others.get("full", ()):
        if full and re.search(r"(?<![a-z0-9])" + re.escape(full) + r"(?![a-z0-9])", seen):
            return True
    folded = enrich.fold(text)
    for name in others.get("bare", ()):
        # A coinage on a name that stands alone: "Obamacare", "Bidenomics".
        if name and re.search(r"(?<![a-z])" + re.escape(name) + r"[a-z]+", folded):
            return True
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


def furniture(text):
    """True when *text* is a site's furniture filed among its issues - a
    label of the list, a funding-request page, a constituent service - not
    an issue."""
    text = _clean(text)
    return bool(_LIST_LABEL.match(text) or _NOT_A_TOPIC.search(text) or _CUT.search(text))


def topic(text, own, others):
    """*text* as an issue, or ``""`` when it is furniture, a label of the
    list, a banner, a sentence, or names someone."""
    text = _clean(text)
    short = len(text) == 2 and text.isalpha() and text.isupper()     # "AI"
    if not (3 <= len(text) <= 60 or short) or len(text.split()) > 8:
        return ""
    if ("{" in text or "}" in text or text.endswith(("?", "!")) or enrich._DANGLING.search(text)
            or _CUT.search(text)):
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


# A menu's own controls, read with its label: Jeffries's "Open/Close Issues".
_MENU_WORDS = re.compile(r"\b(?:toggle|sub-?menu|expand|collapse|show|open|close|menu|dropdown|"
                         r"navigation)\b|/", re.I)


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


def _menu_label(text):
    """A menu link's words without the menu's own controls."""
    return " ".join(_MENU_WORDS.sub(" ", text or "").split())


class _Tree(html.parser.HTMLParser):
    """The page's elements as a tree, enough to find a link's submenu: each
    node is ``[tag, children]`` and a link ``["a", children, href, text]``."""

    _VOID = ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "source", "track", "wbr")
    _SKIP = ("script", "style", "noscript", "template", "svg")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ["root", []]
        self.stack, self._skip, self._link = [self.root], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip or tag in self._VOID:
            return
        node = [tag, []]
        if tag == "a":
            node += [dict(attrs).get("href") or "", []]
            self._link = node
        self.stack[-1][1].append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(self._skip - 1, 0)
            return
        if self._skip:
            return
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth][0] == tag:
                for node in self.stack[depth:]:
                    if node[0] == "a":
                        self._link = None
                del self.stack[depth:]
                break

    def handle_data(self, data):
        if not self._skip and self._link is not None:
            self._link[3].append(data)


def _links_under(node, depth=0):
    """``[(depth, href, text)]`` of every link under *node*, in order."""
    out = []
    for child in node[1]:
        if child[0] == "a":
            out.append((depth + 1, child[2], " ".join("".join(child[3]).split())))
        out += _links_under(child, depth + 1)
    return out


def nested_menus(markup, wanted=lambda href, text: True):
    """``[(label, href, [(href, text)])]``: each link and the submenu built
    of ``<div>``s under it, which :func:`menus` reads only from lists.
    Senator Blackburn's "Issues" is a link in a toggle, beside a collapsed
    panel of nineteen issue links. The submenu is the links of the nearest
    element around the link that holds other links, kept only when every
    one of them comes after the link and sits deeper than it - a flat bar
    of "Home | Issues | Media" is not a menu of Issues."""
    parser = _Tree()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:            # a malformed page still yields what it had
        pass
    out = []

    def walk(node, ancestors):
        for child in node[1]:
            if child[0] == "a":
                text = " ".join("".join(child[3]).split())
                if not wanted(child[2], text):
                    continue
                for ancestor in reversed(ancestors + [node]):
                    links = _links_under(ancestor)
                    if len(links) < 4:
                        continue
                    mine = next((i for i, l in enumerate(links)
                                 if l[1] == child[2] and l[2] == text), None)
                    if mine == 0:
                        own_depth = links[0][0]
                        rest = links[1:]
                        # A submenu, not the rest of the page under one wrapper.
                        if len(rest) <= 2 * MAX_ISSUES and all(d > own_depth for d, _, _ in rest):
                            out.append((text, child[2], [(h, t) for _, h, t in rest]))
                    break
            else:
                walk(child, ancestors + [node])

    walk(parser.root, [])
    return out


def menu_issues(markup, base, website, own, others):
    """The issues a site's own "Issues" menu lists, one item per page it
    links, in the menu's words: Senator Boozman's site has no issues index
    to read, and lists its nine issues under that menu."""
    return menu_read(markup, base, website, own, others)[0]


def menu_read(markup, base, website, own, others):
    """``(items, index)``: :func:`menu_issues`'s items, and the address of
    the menu's own index page when its link leads to one (an ``/issues``
    path), else None - Lynch's "Issues" links its first issue,
    /civil-rights, which is not the list."""
    def is_index(href, label):
        last = urllib.parse.urlsplit(urllib.parse.urljoin(base, href or "")).path
        last = last.rstrip("/").rsplit("/", 1)[-1]
        label = _menu_label(label)
        return any(p.match(label) for p in _INDEX_TEXT) or bool(href and _INDEX_PATH.match(last))

    for label, href, children in menus(markup) + nested_menus(markup, is_index):
        if not is_index(href, label):
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
            if key in targets or not item or same_issue(item) in map(same_issue, items):
                continue
            targets.add(key)
            items.append(item)
        if len(items) >= 3:
            index = urllib.parse.urljoin(base, href or "").split("#")[0] if href else ""
            last = urllib.parse.urlsplit(index).path.rstrip("/").rsplit("/", 1)[-1]
            at = index if index and own_host(index, website) and _INDEX_PATH.match(last) else None
            return items[:MAX_ISSUES], at
    return [], None


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
            if item and same_issue(item) not in map(same_issue, items):
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
        if item and same_issue(item) not in map(same_issue, items):
            items.append(item)
    return items[:MAX_ISSUES] if 3 <= len(items) <= MAX_ISSUES else []


def heading_issues(page, own, others, home=None):
    """An issues page that links no issue pages: its section headings at one
    level, read as a campaign's are (rule 38). A heading the home page
    carries too is the site's frame, not the page's list: Senators Kennedy's
    and Murkowski's issues pages end in their offices' cities, under
    headings, as every page of their sites does."""
    rivals = sorted(others.get("surnames", ()))
    framed = {" ".join(t.split()).lower() for _, t in (home.headings if home else ())}
    items = dedupe([i for i in enrich.issue_headings(page, own, rivals=rivals, limit=MAX_ISSUES)
                    if topic(i, own, others) and " ".join(i.split()).lower() not in framed])
    return items if len(items) >= 3 else []


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
_INPUT = re.compile(r"<(?:input|select)\b([^>]*)>", re.I)
_ATTR = re.compile(r"\b(type|name|id)\s*=\s*[\"']([^\"']*)[\"']", re.I)
# A field that only a message, or the address check before one, asks for.
# A name, an email and a phone alone are what a newsletter sign-up asks:
# Aguilar's /contact/ held only "first-name-footer", "last-name-footer" and
# "email-footer" under "Newsletter Sign Up", and Mfume's /contact/offices
# only webform_225, his newsletter (reviews of PR #106, 2026-10-18).
_MESSAGE_FIELD = re.compile(r"zip|postal|message|subject|topic|comment|inquiry", re.I)
_NOT_A_MESSAGE = re.compile(r"\bsearch\b|signup|sign-up|newsletter|subscribe", re.I)
_SIGN_UP_WORDS = re.compile(r"newsletter|sign\s*-?\s*up|subscribe|e-?mail\s+updates|"
                            r"get\s+(?:regular\s+)?updates|receive\s+(?:\w+\s+)?updates", re.I)
_NEWSLETTER_ID = re.compile(r"newsletter[\w-]*?\"?\s*:\s*\"([\w-]+)\"", re.I)
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
    """True when the page holds a form to write to the office: a form with a
    box for the message (a ``<textarea>``), or one that is not a site search
    or a newsletter sign-up - by its attributes, its words, or the id the
    page's settings give its newsletter - and asks for a message, a subject,
    a ZIP code or a street address (the House's address check comes before
    the message); or a frame of the office's own forms host
    (``crankforms.house.gov``) or of the House's shared mail form."""
    newsletters = {re.sub(r"[_-]", "", n).lower()
                   for n in _NEWSLETTER_ID.findall(markup or "") if "form" in n.lower()}
    for attrs, body in _FORM.findall(markup or ""):
        if _NOT_A_MESSAGE.search(attrs):
            continue
        form_id = re.sub(r"[_-]", "", attrs).lower()
        if any(n and n in form_id for n in newsletters):
            continue
        if re.search(r"<textarea\b", body, re.I):
            return True
        if _SIGN_UP_WORDS.search(re.sub(r"<[^>]+>", " ", body)):
            continue
        # A message form in steps: Adam Smith's webform asks for a name on
        # its first page and the message on the next ("Next Page").
        if re.search(r"wizard-next|webform-wizard|\bvalue\s*=\s*[\"']next(?:\s+page)?[\"']",
                     body, re.I):
            return True
        for field in _INPUT.findall(body):
            found = {k.lower(): v for k, v in _ATTR.findall(field)}
            if found.get("type", "").lower() in ("hidden", "submit", "button"):
                continue
            label = f"{found.get('name', '')} {found.get('id', '')}"
            if _MESSAGE_FIELD.search(label) or (
                    re.search(r"address", label, re.I) and not re.search(r"e-?mail", label, re.I)):
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
            inconclusive = (inconclusive or status2 is None or status2 in (401, 403, 429)
                            or (status2 or 0) >= 500)
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
        # The link is the menu's own index page where it has one, else the
        # page the menu is on - never the first page an "Issues" link led
        # to, which for Lynch was one issue's page.
        items, at = menu_read(markup, final, website, name, others)
        if items:
            record.update(issues=items, issuesUrl=at or final, how="menu")
    if not record.get("issues"):
        for where, shown in pages:
            items = page_issues(shown, where, page, name, others)
            if items:
                record.update(issues=items, issuesUrl=where, how="page")
                break
    if not record.get("issues"):
        for where, shown in pages:
            items = heading_issues(shown, name, others, home=page)
            if items:
                record.update(issues=items, issuesUrl=where, how="headings")
                break
    if not record.get("issues") and not pages:
        # The home page links no issues index, but the site may have one
        # all the same: Hoyer's "Issues" is an anchor on his home page, over
        # five of the nine issues his /issues page lists, and Figures's
        # template page is linked from nowhere. Only a list of issue pages
        # read from such a page counts - never its headings, since a page
        # nobody links may be anything - and a page that is the home page
        # again (a soft 200) is not one.
        for path in ("/issues", "/priorities"):
            time.sleep(pause)
            final2, _, shown, how2, _ = get(urllib.parse.urljoin(final, path), pause, None)
            if (not how2 or not own_host(final2, website)
                    or not urllib.parse.urlsplit(final2).path.strip("/")
                    or shown.body[:3000] == page.body[:3000]):
                continue
            items = listed_issues(shown, final2, name, others)
            if items:
                record.update(issues=items, issuesUrl=final2, how="index", unlinked=True)
                break
    if not record.get("issues") and not pages:
        # No issues page at all, but the home page links issue pages of its
        # own: those links, which are what the home page features and may
        # not be the whole list, and the page says so (platformFeatured).
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


# The recent Presidents and Vice Presidents, whom a banner filed among a
# member's issues names as often as the sitting ones ("Biden's Border
# Crisis"). Biden and Obama name someone alone, and in coinages
# ("Obamacare"); the others only as a name, since Harris, Clinton and Bush
# are also counties and a plant.
FORMER = ("Joe Biden", "Kamala Harris", "Barack Obama", "Mike Pence",
          "George W. Bush", "Dick Cheney", "Bill Clinton", "Hillary Clinton", "Al Gore")
FORMER_BARE = ("biden", "obama")


def people_named(profiles, executive=None):
    """The names a platform line may not carry: every member's, the
    President's, the Vice President's and the Cabinet's, and recent former
    ones' (``others`` for :func:`names_someone`)."""
    full, surnames, bare = set(), set(), set(FORMER_BARE)
    names = [p.get("name") for p in profiles if is_member(p)] + list(FORMER)
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
# A label opens each section after "; ". The Directory's own four also open
# one after a bare space: Sam Graves's and Mitch McConnell's entries print no
# semicolon before "election history:", which ran into their careers.
_KNOWN_LABELS = r"education|professional\s+history|military\s+service|election\s+history"
_LABEL = re.compile(r"(?:(?:^|;\s+)([a-z][a-z ]+?)|\s(" + _KNOWN_LABELS + r")):\s+")


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
            value = joined[mark.end():end].strip().rstrip(";.").strip()
            if value:
                fields[" ".join((mark.group(1) or mark.group(2)).split())] = value
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


def match_directory(profiles, entries, resolve=None):
    """``({bioguide: entry}, [problem], {absent, unclaimed})``: each entry
    joined to the member whose official site congress-legislators lists at
    the same address, and kept only when the entry's name carries that
    member's surname too.

    An address the Directory prints that is no member's is opened with
    *resolve* (``url -> final url``), and joined where it leads to a
    member's listed site: the Directory prints dingell.house.gov, which
    leads to the debbiedingell.house.gov congress-legislators lists, and
    gregmurphy.house.gov leads to murphy.house.gov (2026-10-18). Never by
    the name (rule 17). ``absent`` lists the members with no entry and
    ``unclaimed`` the entries joined to no one, for the build to report."""
    by_host = collections.defaultdict(list)
    for site, name, fields in entries:
        by_host[enrich.host_of(site)].append((site, name, fields))
    out, problems_found = {}, []
    seated = [p for p in profiles if is_member(p) and p.get("website")]
    hosts = {enrich.host_of(p["website"]) for p in seated}
    if resolve:
        for host in [h for h in by_host if h not in hosts]:
            for site, name, fields in by_host[host]:
                final = resolve(site)
                led = enrich.host_of(final) if final else ""
                if led and led != host and led in hosts:
                    by_host[led].append((site, name, fields, final))
    claimed = set()
    for profile in seated:
        found = by_host.get(enrich.host_of(profile["website"])) or []
        if len(found) != 1:
            if len(found) > 1:
                problems_found.append(f"{profile['id']}: {len(found)} entries at {profile['website']}")
            continue
        site, name, fields = found[0][:3]
        if not printed_as(profile["name"], name):
            problems_found.append(f"{profile['id']} ({profile['name']}): the entry at {site} "
                                  f"is printed as {name}")
            continue
        claimed.add(site)
        facts = directory_facts(fields)
        if facts:
            out[profile["id"]] = dict(facts, site=site, printedAs=name)
            if len(found[0]) > 3:
                out[profile["id"]]["leadsTo"] = found[0][3]
    report = {
        "absent": sorted(f"{p['id']} ({p['name']})" for p in seated
                         if p["id"] not in out and not any(p["id"] in x for x in problems_found)),
        "unclaimed": sorted(f"{site} ({name})" for site, name, _ in entries if site not in claimed),
    }
    return out, problems_found, report


def directory_site_is(listed, website):
    """True when a Directory entry is about the member at *website*: printed
    at that address, or at one that led to it when it was read."""
    host = enrich.host_of(website)
    return bool(host) and host in (enrich.host_of(listed.get("site")),
                                   enrich.host_of(listed.get("leadsTo")))


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
            def resolve(url):
                time.sleep(pause)
                final, status, _ = enrich.fetch(url)
                return final if status == 200 else None

            matched, issues, report = match_directory(members, entries, resolve=resolve)
            cache["directory"] = {"edition": edition, "read": stamp, "entries": len(entries),
                                  "byId": matched, "unmatched": issues,
                                  "absent": report["absent"], "unclaimed": report["unclaimed"]}
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
        if listed and directory_site_is(listed, profile.get("website")):
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
        # What the furniture filter now refuses is dropped from a cached read
        # too, so a filter added after a read reaches the page without
        # waiting 27 days for the site to be read again.
        issues = dedupe(i for i in site.get("issues") or [] if not furniture(i))
        withheld = OFFICIAL_ISSUES_NOT_A_LIST.get(bioguide)
        if withheld and withheld[1] == site.get("issuesUrl"):
            issues = []             # read as a list, and not one (overrides)
        if stock_list(issues):
            # The House template's stock categories and nothing of the
            # member's own: the page is there, and is linked, as it is for
            # every member whose site carries it.
            issues = []
            counts["platform_stock"] += 1
        listed = len(issues) >= 3
        if listed and fill_field(profile, "platforms", "; ".join(issues), SITE_SOURCE):
            profile["officialIssuesUrl"] = site["issuesUrl"]
            profile["platformRead"] = site.get("read")
            if site.get("how") == "home":
                # What the home page features, not an issues page's list.
                profile["platformFeatured"] = True
            counts["platform"] += 1
        elif (site.get("verdict") == "none" or (site.get("verdict") == "listed" and not listed)) \
                and profile.get("quality", {}).get("platforms"):
            # Read, and the site lists no issues: said as that, not as "No
            # data", which is a claim that nobody looked (rule 19). A site
            # with an issues page that gave no list this reader could take
            # in its own words (Senator Sanders's is prose under tabs,
            # Kiggans's is drawn by script) is not "not listed": the page
            # is linked for the reader instead.
            profile["platformRead"] = site.get("read")
            page = site.get("pageRead") or (site.get("issuesUrl")
                                             if site.get("verdict") == "listed" else None)
            if page:
                profile["quality"]["platforms"] = "see_site"
                profile["officialIssuesUrl"] = page
                counts["platform_see_site"] += 1
            else:
                profile["quality"]["platforms"] = "not_listed"
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
    stale = [f"{b}: {url} (the site was last read from "
             f"{(sites.get(b) or {}).get('issuesUrl') or 'no issues page'})"
             for b, (_, url, _) in sorted(OFFICIAL_ISSUES_NOT_A_LIST.items())
             if (sites.get(b) or {}).get("issuesUrl") != url]
    if stale:
        out.append(("warn", "members-override-stale",
                    f"{len(stale)} entries in overrides.OFFICIAL_ISSUES_NOT_A_LIST no longer "
                    "match the page read; check the site and drop or update them", stale))
    directory = cache.get("directory") or {}
    seated_ids = {p["id"] for p in seated}
    absent = [a for a in directory.get("absent") or [] if a.split(" ", 1)[0] in seated_ids]
    if absent or directory.get("unclaimed"):
        out.append(("warn", "members-directory-unjoined",
                    f"{len(absent)} seated members have no entry joined from the Congressional "
                    f"Directory ({directory.get('edition')}), and "
                    f"{len(directory.get('unclaimed') or [])} of its entries joined no member; "
                    "their education and careers come from the article, if at all",
                    [f"no entry: {a}" for a in absent]
                    + [f"no member: {u}" for u in directory.get("unclaimed") or []]))
    refused = [f"{b}: {e.get('requested')} -> {e.get('title')}"
               for b, e in sorted((cache.get("articles") or {}).items()) if e.get("refused")]
    if refused:
        out.append(("warn", "members-article-refused",
                    f"{len(refused)} members' mapped articles lead to a title without their "
                    "surname; nothing was taken from them", refused))
    return out
