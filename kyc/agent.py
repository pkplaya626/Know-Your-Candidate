"""Who this project's requests say they are from (rule 103).

Nine readers and one tool used to send a desktop Chrome browser's
User-Agent string, and two more sent one when a server refused the
honest one: a request dressed as a person's browser to be let in where
a script was not wanted. By the owner's decision of 2026-11-01 every
request says who sends it, from this one constant (rule 12), and a
refusal concludes nothing (rule 8): the reader keeps its last good read
and says so, and a person reads the page by hand where one is needed.

``tests/test_agent.py`` fails on a browser's product token in any
User-Agent string in ``kyc/``, ``tools/`` or ``.github/``.
"""

import html
import re
import urllib.parse

# The project and how to reach it: the public repository. Never a person's
# name or address.
USER_AGENT = ("know-your-candidate/2.1 (open-source civic data project; "
              "https://github.com/pkplaya626/Know-Your-Candidate)")

HEADERS = {"User-Agent": USER_AGENT}

# The product tokens a browser's string carries and a script's must not.
# "Mozilla/5.0 (compatible; ...)" is the crawlers' own convention, naming
# no browser and no operating system, and is not one of them.
BROWSER_TOKENS = ("Windows NT", "Macintosh", "Mac OS X", "X11; Linux", "Android",
                  "iPhone", "AppleWebKit", "KHTML", "like Gecko", "Gecko/",
                  "Chrome/", "Chromium/", "Safari/", "Firefox/", "Edg/", "OPR/")

_TOKEN = re.compile("|".join(re.escape(token) for token in BROWSER_TOKENS))


# The titles of the usual bot walls' and challenges' pages, which answer
# 200 (or 202) in a page's place and say nothing of it (rule 8). A phrase
# no page of a site would open its title with is matched at the start;
# one an ordinary page might ("One more step to register to vote", "Not
# allowed here: zoning") only as the whole title, or with a wall vendor's
# name after it (PR #185 review).
_WALL_OPENINGS = (r"Just a moment|Attention Required|Request Rejected|"
                  r"Pardon Our Interruption|Checking your browser|Are you a robot|"
                  r"Human Verification|Verifying you are human|Radware Bot Manager|"
                  r"Bot Verification|DDoS-Guard|Sucuri WebSite Firewall|Robot Check|"
                  r"Incapsula incident")
_WALL_WHOLE = r"Access Denied|Not allowed|Security Check|One more step|403 Forbidden|Please Wait"
_VENDORS = r"Cloudflare|Sucuri|Imperva|Incapsula|DDoS-Guard|Akamai|Radware"
_WALL_TITLE = re.compile(
    rf"^\s*(?:(?:{_WALL_OPENINGS})\b"
    rf"|(?:{_WALL_WHOLE})\b\s*[.!…]*\s*(?:[|:\-–—]\s*(?:{_VENDORS})\b.*)?$)",
    re.I | re.S)
_FIRST_TITLE = re.compile(r"<title[^>]*>(.*?)(?:</title|$)", re.I | re.S)
_BODY_OR_SVG = re.compile(r"<(?:body|svg)\b", re.I)

# The hosts of bot walls that answer a script with a 404 of their own after
# a redirect (Minnesota's Radware page, validate.perfdrive.com; DataDome's
# geo.captcha-delivery.com): a 404 there says nothing of the page asked for
# (rule 8). Any other host's 404 after a redirect is the page's own answer:
# a lapsed campaign domain sent to a registrar's "not found" is gone.
WALL_HOSTS = ("perfdrive.com", "captcha-delivery.com")


def turned_away(title):
    """Whether a page's title is a bot wall's or a challenge's."""
    return bool(_WALL_TITLE.search(html.unescape(title or "")))


def wall_host(url):
    """Whether *url* is on a bot wall's own host (:data:`WALL_HOSTS`)."""
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    return any(host == wall or host.endswith("." + wall) for wall in WALL_HOSTS)


def walled(page):
    """Whether a page that answered says nothing of what was asked: an empty
    body (coag.gov's firewall answered HTTP 202 and nothing else,
    2026-11-01) or a bot wall's or challenge's page, by the document's own
    title - the first ``<title>`` before its body, never an inline SVG's.
    *page* is markup, as text or as its first bytes."""
    if isinstance(page, (bytes, bytearray)):
        page = bytes(page).decode("utf-8", "replace")
    page = page or ""
    if not page.strip():
        return True
    cut = _BODY_OR_SVG.search(page)
    match = _FIRST_TITLE.search(page[:cut.start()] if cut else page)
    return bool(match) and turned_away(match.group(1)[:300])


def browser_tokens(agent):
    """The browser product tokens in *agent*, in order; empty when honest."""
    return _TOKEN.findall(agent or "")
