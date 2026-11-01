"""Who this project's requests say they are from (rule 103).

Ten readers and one tool used to send a desktop Chrome browser's
User-Agent string, and two of them sent one again when a server refused
the honest one: a request dressed as a person's browser to be let in where
a script was not wanted. By the owner's decision of 2026-11-01 every
request says who sends it, from this one constant (rule 12), and a
refusal concludes nothing (rule 8): the reader keeps its last good read
and says so, and a person reads the page by hand where one is needed.

``tests/test_agent.py`` fails on a browser's product token in any
User-Agent string in ``kyc/``, ``tools/`` or ``.github/``.
"""

import re

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
# 200 (or 202) in a page's place and say nothing of it (rule 8).
WALL_TITLES = (r"(?:Access Denied|Just a moment|Not allowed|Attention Required|"
               r"Request Rejected|Pardon Our Interruption|Security Check|"
               r"Checking your browser|Are you a robot|Human Verification|"
               r"One more step|Verifying you are human|Radware Bot Manager|"
               r"Bot Verification|DDoS-Guard|Sucuri WebSite Firewall)\b")
_WALL_TITLE = re.compile(r"^\s*" + WALL_TITLES, re.I)


def turned_away(title):
    """Whether a page's title is a bot wall's or a challenge's."""
    return bool(_WALL_TITLE.search(title or ""))


def browser_tokens(agent):
    """The browser product tokens in *agent*, in order; empty when honest."""
    return _TOKEN.findall(agent or "")
