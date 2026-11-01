"""Rule 103: every request says who sends it, never a browser.

Ten readers and one tool sent a desktop Chrome User-Agent string until
2026-11-01, and two sent one again when a server refused the honest one.
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


if __name__ == "__main__":
    unittest.main()
