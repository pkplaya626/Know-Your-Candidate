"""Rule 103: every request says who sends it, never a browser.

Nine readers and one tool sent a desktop Chrome User-Agent string until
2026-11-01, and two more sent one when a server refused the honest one.
This fails on a browser's product token in a User-Agent string anywhere in
kyc/, tools/ or .github/ (as CI greps for onclick=), on a module constant
that would send one, and on a headless Chrome told to pose as another.
"""

import importlib
import os
import pkgutil
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import kyc  # noqa: E402
from kyc import agent  # noqa: E402

# A browser's string as it is written: a platform in Mozilla's brackets
# ("Mozilla/5.0 (Windows NT 10.0; ..."), or an engine's or a browser's
# versioned token. "Mozilla/5.0 (compatible; ...)" is the crawlers' own
# convention, naming no browser and no platform.
BROWSER_STRING = re.compile(
    r"Mozilla/\d+\.\d+ \((?!compatible;)|AppleWebKit/\d|KHTML, like Gecko|Gecko/\d|"
    r"Chrome/\d|Chromium/\d|Safari/\d|Firefox/\d|Edg/\d|OPR/\d|Windows NT \d|Macintosh;|"
    r"Mac OS X \d|CPU iPhone OS")
# A headless Chrome told to send another user agent than its own.
POSING = re.compile(r"setUserAgent|userAgentOverride|--user-agent", re.I)
SCANNED = ("kyc", "tools", ".github")
TEXT = (".py", ".mjs", ".js", ".cjs", ".yml", ".yaml", ".sh", ".json", ".txt", ".md")


def scanned_files():
    for top in SCANNED:
        for folder, dirs, files in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules")]
            for name in files:
                if name.endswith(TEXT):
                    yield os.path.join(folder, name)


class TestEveryRequestSaysWhoSendsIt(unittest.TestCase):

    def test_the_one_constant_names_the_project_and_no_browser(self):
        self.assertEqual(agent.browser_tokens(agent.USER_AGENT), [])
        self.assertIn("know-your-candidate", agent.USER_AGENT)
        self.assertIn("https://github.com/", agent.USER_AGENT)
        self.assertNotIn("@", agent.USER_AGENT)           # never a person's address
        self.assertEqual(agent.HEADERS, {"User-Agent": agent.USER_AGENT})

    def test_the_guard_knows_a_browsers_string(self):
        chrome = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/154.0 Safari/537.36")
        self.assertTrue(BROWSER_STRING.search(chrome))
        self.assertTrue(agent.browser_tokens(chrome))
        for honest in (agent.USER_AGENT, "Mozilla/5.0 (compatible; know-your-candidate/1.0)",
                       "C:/Program Files/Google/Chrome/Application/chrome.exe"):
            self.assertIsNone(BROWSER_STRING.search(honest), honest)

    def test_no_file_carries_a_browsers_user_agent(self):
        found = []
        for path in scanned_files():
            with open(path, encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    if BROWSER_STRING.search(line) or POSING.search(line):
                        found.append(f"{os.path.relpath(path, ROOT)}:{number}: {line.strip()[:100]}")
        self.assertEqual(found, [], "a request must say who sends it (rule 103)")

    def test_no_module_constant_would_send_one(self):
        for info in pkgutil.iter_modules(kyc.__path__):
            module = importlib.import_module(f"kyc.{info.name}")
            for name, value in vars(module).items():
                if not re.search(r"(^|_)(UA|USER_AGENT|AGENT|HEADERS)(_|$)", name):
                    continue
                strings = [value] if isinstance(value, str) else \
                    [v for v in value.values() if isinstance(v, str)] if isinstance(value, dict) else []
                for text in strings:
                    self.assertEqual(agent.browser_tokens(text), [], f"kyc.{info.name}.{name}")

    def test_a_bot_walls_page_says_nothing(self):
        for page in ("", "   ", b"", "<html><head><title>Just a moment...</title>",
                     "<title>Access Denied</title>", b"<TITLE>Attention Required! | Cloudflare</TITLE>",
                     "<title data-x>Request Rejected</title>"):
            self.assertTrue(agent.walled(page), page)
        for page in ("<title>Secretary of State</title><p>Marco Rubio</p>",
                     "<title>Denied access to records, a court rules</title>"):
            self.assertFalse(agent.walled(page), page)

    def test_a_wall_is_known_by_the_documents_own_title(self):
        # PR #185 review: an ordinary page may open its title with a phrase a
        # wall uses, and an inline SVG's <title> is not the document's.
        for title in ("Robot Check", "Incapsula incident ID: 123", "Please Wait... | Cloudflare",
                      "One more step", "Security Check - Sucuri", "403 Forbidden",
                      "Access Denied", "Just a moment...", "Not allowed."):
            self.assertTrue(agent.turned_away(title), title)
        for title in ("One more step to register to vote", "Not allowed here: zoning",
                      "Security Checklist for Polling Places", "Access Denied: a history",
                      "Please Wait for Your Ballot", ""):
            self.assertFalse(agent.turned_away(title), title)
        self.assertFalse(agent.walled(
            "<html><head><title>Find Your Polling Place</title></head><body>"
            "<svg><title>Access Denied</title></svg>"))
        self.assertFalse(agent.walled("<svg><title>Just a moment</title></svg><p>Election day</p>"))
        self.assertFalse(agent.walled("<head><title>Polls</title><title>Access Denied</title>"))
        self.assertTrue(agent.walled("<!doctype html><head><title>\n Just a moment...\n</title>"))
        self.assertTrue(agent.walled(b"<title>Attention Required! &#124; Cloudflare"))

    def test_a_walls_host_is_its_own(self):
        for url in ("https://validate.perfdrive.com/?ssa=1", "https://geo.captcha-delivery.com/c/"):
            self.assertTrue(agent.wall_host(url), url)
        for url in ("https://www.godaddy.com/notfound", "https://notperfdrive.com/", "", None):
            self.assertFalse(agent.wall_host(url), url)


class TestARefusalConcludesNothing(unittest.TestCase):
    """What each switched reader makes of a refusal (rules 8, 39, 78, 103):
    nothing, while a site's own answer is still its answer."""

    PROFILE = {"name": "Mike France"}
    SITE = "https://votemikefrance.com/"

    def campaign(self, status, final=SITE, markup=""):
        from kyc import enrich
        return enrich.assess(self.PROFILE, self.SITE, final, status, enrich.parse_page(markup))

    def test_a_campaign_site_that_turns_a_script_away_keeps_its_last_verdict(self):
        for status in (401, 403, 406, 429, 451):
            self.assertEqual(self.campaign(status), (None, f"HTTP {status}"), status)
        self.assertEqual(self.campaign(404, "https://validate.perfdrive.com/?ssa=1"),
                         (None, "HTTP 404 from validate.perfdrive.com"))
        verdict, why = self.campaign(200, markup="<title>Just a moment...</title><p>checking</p>")
        self.assertIsNone(verdict)
        self.assertIn("bot wall", why)

    def test_a_campaign_sites_own_404_is_still_gone(self):
        # The first fix excused a 404 from any other host: a lapsed domain sent
        # to a registrar's "not found" page would have stayed linked as safe.
        from kyc import enrich
        for final in (self.SITE, "https://www.votemikefrance.com/x",
                      "https://www.godaddy.com/notfound"):
            self.assertIs(self.campaign(404, final)[0], enrich.REFUSED, final)

    def test_a_parking_chains_security_check_is_still_parking(self):
        from kyc import enrich
        lander = ('<html><head><title>Security Check</title>'
                  '<script src="/parking-lander/static/js/main.js"></script></head></html>')
        self.assertEqual(self.campaign(200, markup=lander), (enrich.REFUSED, enrich.PARKED))

    def test_a_local_governments_bot_wall_is_unread_never_elsewhere(self):
        from kyc import localsites
        start = "http://www.clintonct.com/"
        for chain in ([start], [start, "https://validate.perfdrive.com/?ssa=1"]):
            seen = {"chain": chain, "status": 200, "error": "", "dnsHost": "", "insecure": False,
                    "markup": "<title>Pardon Our Interruption</title><p>As you were browsing</p>"}
            verdict, why, _final = localsites.assess(["Town of Clinton"], start, seen)
            self.assertEqual(verdict, localsites.UNREAD, chain)
            self.assertIn("bot wall", why)

    def test_an_official_photographs_404_is_gone_unless_a_wall_gave_it(self):
        import io
        import urllib.error
        from unittest import mock
        from kyc import official_photos
        cases = (("https://ag.example.gov/a.jpg", "https://ag.example.gov/a.jpg", False),
                 ("https://ag2.example.gov/a.jpg", "https://www.ag2.example.gov/gone", False),
                 ("https://ag3.example.gov/a.jpg", "https://validate.perfdrive.com/?ssa=1", None))
        for url, final, verdict in cases:
            def opener(request, timeout=None, final=final):
                raise urllib.error.HTTPError(final, 404, "Not Found", {}, io.BytesIO(b""))
            with mock.patch("urllib.request.urlopen", opener):
                self.assertEqual(official_photos.weigh(url), (verdict, None), final)
        for code in (401, 403, 406, 429):
            def refuse(request, timeout=None, code=code):
                raise urllib.error.HTTPError(request.full_url, code, "No", {}, io.BytesIO(b""))
            with mock.patch("urllib.request.urlopen", refuse):
                self.assertEqual(official_photos.weigh(f"https://r{code}.example.gov/a.jpg"),
                                 (None, None), code)


if __name__ == "__main__":
    unittest.main()
