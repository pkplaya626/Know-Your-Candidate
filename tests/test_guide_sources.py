"""Whether the guide's sources still open (kyc/guide_sources.py, rule 48).

Some eighty of the guide's sources are uscode.house.gov/us/usc/tN/sM/ pages,
on a site that says it runs in a "temporary format" and whose previous
addresses already answer 404; nothing opened an external link (PR #255's
review). Each check here makes the state it tests (CLAUDE.md, "Conventions"):
a read's answer, a run of days, a cache, never the day's live answers.
"""

import datetime
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from kyc import agent, ballot2026, cli, government_maps, government_text, validate  # noqa: E402
from kyc import guide_sources as gs  # noqa: E402
from kyc.localsites import _Gate  # noqa: E402

CODE = "https://uscode.house.gov/us/usc/t2/s8/"
CONSTITUTION = "https://constitution.congress.gov/constitution/article-1/"
# What constitution.congress.gov answered this project on 2026-11-14.
CHALLENGE = (b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title>'
             b'<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"></head>'
             b'<body><div>Enable JavaScript and cookies to continue</div></body></html>')


def page(title, extra=""):
    return (f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{title}</title></head>"
            f"<body><h1>{title}</h1><p>{'Text of the page. ' * 40}{extra}</p></body></html>"
            ).encode("utf-8")


def seen(status, body=b"", kind="text/html", chain=None, error="", dns=""):
    return {"chain": chain or [CODE], "status": status, "type": kind, "body": body,
            "error": error, "dnsHost": dns}


class TestOneRead(unittest.TestCase):
    """What one read concludes, and what it never does (rule 8)."""

    def test_a_code_section_opens_where_its_title_names_it(self):
        answer, evidence, _final = gs.assess(CODE, seen(200, page("2 U.S.C. § 8: Vacancies")))
        self.assertEqual(answer, gs.OPEN)
        self.assertIn("2 U.S.C. s. 8: Vacancies", evidence)
        url = "https://uscode.house.gov/us/usc/t42/s300aa-12/"
        # The Counsel writes the section's dash as an en dash.
        self.assertEqual(gs.assess(url, seen(200, page("42 U.S.C. § 300aa–12: Court jurisdiction"),
                                             chain=[url]))[0], gs.OPEN)

    def test_a_code_address_opening_another_section_is_not_it(self):
        url = "https://uscode.house.gov/us/usc/t42/s300aa-12/"
        for title in ("42 U.S.C. § 300aa–1: Short title", "42 U.S.C. § 300aa–123: Other",
                      "2 U.S.C. § 300aa–12: Not this title", "Browse the United States Code",
                      ""):
            answer, evidence, _final = gs.assess(url, seen(200, page(title), chain=[url]))
            self.assertEqual(answer, gs.ELSEWHERE_ANSWER, title)
            self.assertIn("does not name 42 U.S.C. 300aa-12", evidence)
        self.assertEqual(gs.code_section(CODE), ("2", "8"))
        self.assertIsNone(gs.code_section("https://uscode.house.gov/browse.html"))
        self.assertIsNone(gs.code_section("https://www.govinfo.gov/app/collection/uscode"))

    def test_404_and_410_are_not_found(self):
        for status in (404, 410):
            answer, evidence, _final = gs.assess(CODE, seen(status, page("Page Not Found - US Code")))
            self.assertEqual(answer, gs.NOTFOUND)
            self.assertEqual(evidence, f"HTTP {status}")
        # Through a redirect on its own site, still the address's answer.
        chain = [CODE, "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title2-section8"]
        self.assertEqual(gs.assess(CODE, seen(404, chain=chain))[0], gs.NOTFOUND)

    def test_a_bot_walls_own_404_concludes_nothing(self):
        chain = [CODE, "https://validate.perfdrive.com/?ssa=1"]
        self.assertEqual(gs.assess(CODE, seen(404, chain=chain))[0], gs.NOTHING)

    def test_a_bot_walls_redirect_is_kept_without_its_query(self):
        """Radware's wall wrote the reader's own IP address, base64-encoded,
        into its redirect's query ("ssr="), and the first cache kept it in
        the evidence (Minnesota's sample-ballot page, 2026-11-14)."""
        url = "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"
        wall = "https://validate.perfdrive.com/?ssa=1&ssr=MTkyLjAuMi4x&sst=know-your-candidate"
        for status in (302, 200, 404):
            answer, evidence, final = gs.assess(url, seen(status, page("Radware"), chain=[url, wall]))
            self.assertEqual(answer, gs.NOTHING, status)
            self.assertIn("bot wall", evidence)
            self.assertNotIn("ssr=", evidence + final)
            entry = gs.merge(None, (answer, evidence, final), "2026-11-14", url)
            self.assertNotIn("ssr=", str(entry))
        # Any other host's query is left out too; the source's own site's
        # is kept.
        self.assertEqual(gs.shown(url, "https://www.example.org/p?token=x"),
                         "https://www.example.org/p")
        self.assertEqual(gs.shown(url, "https://sos.mn.gov/p?cite=1"), "https://sos.mn.gov/p?cite=1")

    def test_ecfrs_bot_wall_is_not_its_front_page(self):
        """The first run read eCFR's 25 CFR 11.201, sent to the Federal
        Register's "Request Access" page, as a deep link sent home."""
        url = ("https://www.ecfr.gov/current/title-25/chapter-I/subchapter-B/part-11/subpart-B/"
               "section-11.201")
        chain = [url, "https://unblock.federalregister.gov/"]
        answer, evidence, _final = gs.assess(url, seen(200, page("Federal Register :: Request Access"),
                                                       chain=chain))
        self.assertEqual(answer, gs.NOTHING)
        self.assertIn("bot wall", evidence)
        # Nor is another host's front page this site's.
        other = [url, "https://www.example.org/"]
        self.assertEqual(gs.assess(url, seen(200, page("Example"), chain=other))[0], gs.OPEN)

    def test_a_refusal_a_challenge_or_a_timeout_concludes_nothing(self):
        for status in (401, 403, 406, 429, 451, 500, 502, 503):
            self.assertEqual(gs.assess(CODE, seen(status, page("Forbidden")))[0], gs.NOTHING, status)
        self.assertEqual(gs.assess(CODE, seen(None, error="timed out"))[0], gs.NOTHING)
        self.assertEqual(gs.assess(CODE, seen(200, b""))[0], gs.NOTHING)
        self.assertEqual(gs.assess(CODE, seen(202, b"  "))[0], gs.NOTHING)
        answer, evidence, _final = gs.assess(CODE, seen(200, CHALLENGE))
        self.assertEqual(answer, gs.NOTHING)
        self.assertIn("challenge", evidence)
        # A redirect to a sign-in page says nothing of the source.
        chain = [CODE, "https://accounts.google.com/ServiceLogin?continue=x"]
        self.assertEqual(gs.assess(CODE, seen(200, page("Sign in"), chain=chain))[0], gs.NOTHING)
        # A page where a PDF was asked for may be a rejection page (rule 52).
        pdf = "https://tile.loc.gov/storage-services/x/usrep005137.pdf"
        self.assertEqual(gs.assess(pdf, seen(200, page("Request"), chain=[pdf]))[0], gs.NOTHING)

    def test_constitution_congress_gov_never_reads_as_gone(self):
        """It answers this project with Cloudflare's challenge, 403: no number
        of such reads, on any number of days, is a verdict."""
        answer, evidence, final = gs.assess(CONSTITUTION, seen(403, CHALLENGE, kind="text/html; "
                                                               "charset=UTF-8", chain=[CONSTITUTION]))
        self.assertEqual(answer, gs.NOTHING)
        self.assertIn("Just a moment", evidence)
        entry = None
        for day in range(1, 60):
            entry = gs.merge(entry, (answer, evidence, final), f"2026-11-{day:02d}"
                             if day <= 30 else f"2026-12-{day - 30:02d}", CONSTITUTION)
            self.assertEqual(entry["verdict"], gs.UNREAD)
        self.assertEqual(gs.problems({"sources": {CONSTITUTION: entry}},
                                     {CONSTITUTION: [("guide congress#powers", "const-art1")]},
                                     today="2026-12-29"), [])

    def test_a_page_titled_not_found_is_not_the_source(self):
        url = "https://www.house.gov/the-house-explained"
        answer, evidence, _final = gs.assess(url, seen(200, page("Page Not Found | house.gov"),
                                                       chain=[url]))
        self.assertEqual(answer, gs.ELSEWHERE_ANSWER)
        self.assertIn("Page Not Found", evidence)
        for title in ("404 - File or directory not found", "Error 404", "Not Found",
                      "The page you requested could not be found"):
            self.assertTrue(gs._NOT_FOUND_TITLE.search(title), title)
        for title in ("U.S. House of Representatives: The House Explained",
                      "Finding aids for the 404th session", "Lost and found"):
            self.assertFalse(gs._NOT_FOUND_TITLE.search(title), title)

    def test_a_deep_address_sent_to_its_front_page_is_not_the_source(self):
        url = "https://www.nh.gov/glance/state-constitution/executive-power-governor"
        answer, evidence, _final = gs.assess(url, seen(200, page("NH.gov"),
                                                       chain=[url, "https://www.nh.gov/"]))
        self.assertEqual(answer, gs.ELSEWHERE_ANSWER)
        self.assertIn("front page", evidence)
        # A front page cited as one is itself.
        self.assertEqual(gs.assess("https://vote.gov/", seen(200, page("Vote.gov"),
                                                             chain=["https://vote.gov/"]))[0],
                         gs.OPEN)
        # A query is deep: "?cite=29A.52.112" sent to "/" is not the statute.
        rcw = "https://app.leg.wa.gov/RCW/default.aspx?cite=29A.52.112"
        self.assertEqual(gs.assess(rcw, seen(200, page("Washington State Legislature"),
                                             chain=[rcw, "https://app.leg.wa.gov/"]))[0],
                         gs.ELSEWHERE_ANSWER)

    def test_a_file_opens_on_its_first_bytes(self):
        pdf = "https://www.supremecourt.gov/opinions/boundvolumes/567BV.pdf"
        answer, evidence, _final = gs.assess(pdf, seen(200, b"%PDF-1.6\n%\xe2\xe3", "application/pdf",
                                                       chain=[pdf]))
        self.assertEqual(answer, gs.OPEN)
        self.assertIn("application/pdf", evidence)


class TestAGetAsThisProject(unittest.TestCase):
    """Rule 103 and rule 51: a GET, saying who sends it, reading only the
    first bytes; HEAD lies."""

    def capture(self, kind, size):
        asked = {}

        class Response:
            status = 200

            def __init__(self):
                self.headers = {"Content-Type": kind}

            def read(self, amount=-1):
                asked["read"] = amount
                return b"%PDF-1.4" + b"x" * (min(amount, size) - 8)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class Opener:
            def open(self, req, timeout=None):
                asked["method"] = req.get_method()
                asked["agent"] = req.get_header("User-agent")
                return Response()

        saved = gs.urllib.request.build_opener
        gs.urllib.request.build_opener = lambda *handlers: Opener()
        try:
            status, _kind, body, _where = gs._request("https://www.supremecourt.gov/x.pdf", None)
        finally:
            gs.urllib.request.build_opener = saved
        return asked, status, body

    def test_a_large_file_is_read_only_in_its_first_bytes(self):
        asked, status, body = self.capture("application/pdf", 40_000_000)
        self.assertEqual(status, 200)
        self.assertEqual(asked["method"], "GET")
        self.assertEqual(asked["agent"], agent.USER_AGENT)
        self.assertEqual(asked["read"], gs.FILE_BYTES)
        self.assertEqual(len(body), gs.FILE_BYTES)
        asked, _status, _body = self.capture("text/html; charset=utf-8", 40_000_000)
        self.assertEqual(asked["read"], gs.PAGE_BYTES)

    def test_paced_one_request_at_a_time_per_host(self):
        self.assertGreaterEqual(gs.HOST_INTERVAL, 1.0)
        self.assertEqual(agent.browser_tokens(gs._HEADERS["User-Agent"]), [])


class TestTheResolvers(unittest.TestCase):
    """A host is gone only where it fails here and at both public
    resolvers (rule 35)."""

    def read(self, answers, resolves=False):
        dns = seen(None, error="x does not resolve here", dns="uscode.house.gov")
        return gs.read_one(CODE, None, visit_fn=lambda url, gate: dns,
                           doh_fn=lambda host, gate: answers, resolves=lambda host: resolves)

    def test_a_host_gone_at_both_resolvers_is_dead(self):
        answer, evidence, _final, _answered = self.read(("nxdomain", "nxdomain"))
        self.assertEqual(answer, gs.DEAD)
        self.assertIn("NXDOMAIN here, at dns.google and at Cloudflare", evidence)
        self.assertEqual(gs.merge(None, (answer, evidence, CODE), "2026-11-14", CODE)["verdict"],
                         gs.GONE)

    def test_a_host_one_resolver_finds_or_cannot_answer_for_is_not(self):
        for answers in (("exists",), ("nxdomain", "exists"), ("servfail",), (None,),
                        ("nxdomain", None)):
            self.assertEqual(self.read(answers)[0], gs.NOTHING, answers)
        self.assertIn("not confirmed gone", self.read(("servfail",))[1])

    def test_a_lookup_that_fails_once_is_read_again(self):
        reads = []

        def visit(url, gate):
            reads.append(url)
            return (seen(None, error="x", dns="uscode.house.gov") if len(reads) == 1
                    else seen(200, page("2 U.S.C. § 8: Vacancies")))
        answer = gs.read_one(CODE, None, visit_fn=visit, doh_fn=lambda h, g: (),
                             resolves=lambda host: True)[0]
        self.assertEqual((answer, len(reads)), (gs.OPEN, 2))


class TestTheDays(unittest.TestCase):
    """Gone is two reads on different days; a read that concludes nothing
    undoes nothing (rule 8)."""

    NOT_FOUND = (gs.NOTFOUND, "HTTP 404", CODE)
    OPENED = (gs.OPEN, "HTTP 200, titled '2 U.S.C. s. 8: Vacancies'", CODE)
    REFUSED = (gs.NOTHING, "HTTP 403", CODE)
    FRONT = (gs.ELSEWHERE_ANSWER, "redirects to its site's front page, https://uscode.house.gov/",
             "https://uscode.house.gov/")

    def run_days(self, *reads):
        entry = None
        for day, read in reads:
            entry = gs.merge(entry, read, day, CODE)
        return entry

    def test_one_404_is_missing_and_a_second_the_same_day_too(self):
        self.assertEqual(self.run_days(("2026-11-14", self.NOT_FOUND))["verdict"], gs.MISSING)
        twice = self.run_days(("2026-11-14", self.NOT_FOUND), ("2026-11-14", self.NOT_FOUND))
        self.assertEqual(twice["verdict"], gs.MISSING)
        self.assertEqual(len(twice["misses"]), 1)

    def test_404_on_two_days_is_gone(self):
        entry = self.run_days(("2026-11-14", self.NOT_FOUND), ("2026-11-21", self.NOT_FOUND))
        self.assertEqual(entry["verdict"], gs.GONE)
        self.assertEqual(entry["evidence"], "HTTP 404 on 2026-11-14 and 2026-11-21")
        self.assertEqual(entry["checked"], "2026-11-21")

    def test_a_refusal_between_two_404s_neither_confirms_nor_clears(self):
        entry = self.run_days(("2026-11-14", self.NOT_FOUND), ("2026-11-15", self.REFUSED))
        self.assertEqual(entry["verdict"], gs.MISSING)
        self.assertEqual((entry["tried"], entry["triedEvidence"]), ("2026-11-15", "HTTP 403"))
        entry = gs.merge(entry, self.NOT_FOUND, "2026-11-16", CODE)
        self.assertEqual(entry["verdict"], gs.GONE)
        self.assertNotIn("tried", entry)

    def test_a_refusal_never_undoes_a_verdict(self):
        for reads in ((("2026-11-14", self.OPENED),),
                      (("2026-11-14", self.NOT_FOUND), ("2026-11-15", self.NOT_FOUND))):
            before = self.run_days(*reads)
            after = gs.merge(before, self.REFUSED, "2026-11-30", CODE)
            self.assertEqual(after["verdict"], before["verdict"])
            self.assertEqual(after["checked"], before["checked"])
            self.assertEqual(after["tried"], "2026-11-30")

    def test_a_source_that_opens_again_is_ok(self):
        entry = self.run_days(("2026-11-14", self.NOT_FOUND), ("2026-11-15", self.NOT_FOUND),
                              ("2026-11-22", self.OPENED))
        self.assertEqual(entry["verdict"], gs.OK)
        self.assertNotIn("misses", entry)
        # And one 404 after it starts a new run of days.
        self.assertEqual(gs.merge(entry, self.NOT_FOUND, "2026-11-29", CODE)["verdict"], gs.MISSING)

    def test_another_page_on_two_days_is_elsewhere_and_two_404s_among_them_gone(self):
        self.assertEqual(self.run_days(("2026-11-14", self.FRONT),
                                       ("2026-11-21", self.FRONT))["verdict"], gs.ELSEWHERE)
        mixed = self.run_days(("2026-11-14", self.NOT_FOUND), ("2026-11-21", self.FRONT))
        self.assertEqual(mixed["verdict"], gs.ELSEWHERE)
        self.assertEqual(mixed["final"], "https://uscode.house.gov/")
        again = gs.merge(mixed, self.NOT_FOUND, "2026-11-28", CODE)
        self.assertEqual(again["verdict"], gs.GONE)
        self.assertEqual(again["evidence"], "HTTP 404 on 2026-11-14 and 2026-11-28")

    def test_what_is_due(self):
        today = "2026-11-21"
        self.assertTrue(gs.due(None, today))
        self.assertTrue(gs.due({"checked": "2026-11-15", "verdict": gs.OK}, today))
        self.assertFalse(gs.due({"checked": "2026-11-16", "verdict": gs.OK}, today))
        self.assertTrue(gs.due({"checked": "2026-11-16", "verdict": gs.OK}, today, refresh=True))
        # A missing or unread one is read on any later day, never twice in one.
        for verdict in (gs.MISSING, gs.UNREAD):
            self.assertTrue(gs.due({"checked": "2026-11-20", "verdict": verdict}, today))
            self.assertFalse(gs.due({"checked": today, "verdict": verdict}, today))
        # A try that concluded nothing counts as a look.
        self.assertFalse(gs.due({"checked": "2026-11-01", "tried": "2026-11-20", "verdict": gs.OK},
                                today))


class TestTheBuildWarns(unittest.TestCase):
    """By name and section, and never an error."""

    CITED = {CODE: [("guide congress#vacancies", "usc-2-8: 2 U.S.C. 8 (when a House vacancy is "
                                                 "filled)"),
                    ("guide elections#vacancies", "usc-2-8: 2 U.S.C. 8 (when a House vacancy is "
                                                  "filled)")],
             CONSTITUTION: [("guide congress#powers", "const-art1: U.S. Constitution, Article I")]}

    def cache(self, code_entry, constitution=None):
        return {"sources": {CODE: code_entry,
                            CONSTITUTION: constitution or {"checked": "2026-11-14",
                                                           "verdict": gs.UNREAD,
                                                           "evidence": "HTTP 403"}}}

    def test_a_gone_source_is_named_with_every_section_citing_it(self):
        gone = {"checked": "2026-11-21", "verdict": gs.GONE,
                "evidence": "HTTP 404 on 2026-11-14 and 2026-11-21"}
        found = gs.problems(self.cache(gone), self.CITED, today="2026-11-21")
        self.assertEqual([(level, code) for level, code, _m, _d in found],
                         [("warn", "guide-source-gone")])
        message, detail = found[0][2], found[0][3]
        for words in (CODE, "usc-2-8: 2 U.S.C. 8", "is gone", "HTTP 404 on 2026-11-14 and 2026-11-21",
                      "guide congress#vacancies", "guide elections#vacancies"):
            self.assertIn(words, message)
        self.assertEqual(len(detail), 2)

    def test_another_page_warns_and_one_day_or_a_refusal_does_not(self):
        elsewhere = {"checked": "2026-11-21", "verdict": gs.ELSEWHERE, "evidence": "x"}
        self.assertEqual([c for _l, c, _m, _d in gs.problems(self.cache(elsewhere), self.CITED,
                                                              today="2026-11-21")],
                         ["guide-source-elsewhere"])
        for verdict in (gs.OK, gs.MISSING, gs.UNREAD):
            self.assertEqual(gs.problems(self.cache({"checked": "2026-11-21", "verdict": verdict}),
                                         self.CITED, today="2026-11-21"), [], verdict)

    def test_a_source_never_opened_warns(self):
        found = gs.problems({"sources": {CODE: {"checked": "2026-11-21", "verdict": gs.OK}}},
                            self.CITED, today="2026-11-21")
        self.assertEqual([c for _l, c, _m, _d in found], ["guide-source-unopened"])
        self.assertIn(CONSTITUTION, found[0][3][0])
        self.assertIn("guide congress#powers", found[0][3][0])

    def test_a_source_not_looked_at_in_thirty_days_warns(self):
        entry = {"checked": "2026-11-14", "verdict": gs.OK}
        look = {"checked": "2026-11-14", "verdict": gs.UNREAD}
        thirty = (datetime.date(2026, 11, 14) + datetime.timedelta(days=gs.WARN_DAYS)).isoformat()
        later = (datetime.date(2026, 11, 14) + datetime.timedelta(days=gs.WARN_DAYS + 1)).isoformat()
        self.assertEqual(gs.problems(self.cache(entry, look), self.CITED, today=thirty), [])
        found = gs.problems(self.cache(entry, look), self.CITED, today=later)
        self.assertEqual([c for _l, c, _m, _d in found], ["guide-source-stale"])
        self.assertEqual(len(found[0][3]), 2)
        # A try that concluded nothing is a look.
        tried = dict(entry, tried=later)
        self.assertEqual([d for _l, _c, _m, details in gs.problems(self.cache(tried, look),
                                                                   self.CITED, today=later)
                          for d in details], [f"{CONSTITUTION}: last looked at 2026-11-14"])
        self.assertEqual(gs.WARN_DAYS, 30)

    def test_the_build_never_fails_on_it(self):
        """Every cited address gone: warnings, not one error (the refresh
        must not fail on someone else's site)."""
        cited = gs.citations(ROOT)
        cache = {"sources": {u: {"checked": "2026-11-21", "verdict": gs.GONE, "evidence": "x"}
                             for u in cited}}
        issues = validate.run([], {}, guide_sources=cache, root=ROOT)
        mine = [i for i in issues if i.code.startswith("guide-source")]
        self.assertEqual(len(mine), len(cited))
        self.assertEqual({i.level for i in mine}, {"warn"})
        # validate.run with no cache says nothing of it (a caller that did
        # not supply it); the build supplies the committed one.
        self.assertFalse([i for i in validate.run([], {}) if i.code.startswith("guide-source")])
        with open(os.path.join(ROOT, "kyc", "cli.py"), encoding="utf-8") as handle:
            self.assertIn("guide_sources=guide_sources_mod.load_cache(args.root)", handle.read())

    def test_what_no_read_could_open_is_said_as_neither(self):
        cache = self.cache({"checked": "2026-11-21", "verdict": gs.OK})
        issues = validate.check_guide_sources(cache, ROOT, today="2026-11-21")
        info = [i for i in issues if i.code == "guide-sources-unread"]
        self.assertEqual([i.level for i in info], ["info"])
        self.assertIn("constitution.congress.gov 1", info[0].message)


class TestWhatIsCited(unittest.TestCase):
    """Every address the guide, its maps, the ballot table and the page
    code's statute links cite, each with where."""

    @classmethod
    def setUpClass(cls):
        cls.cited = gs.citations(ROOT)

    def where(self, url):
        return {w for w, _n in self.cited[gs.address(url)]}

    def test_every_guide_source_with_its_sections(self):
        for page in government_text.PAGES:
            for section in page["sections"]:
                for key in section["sources"]:
                    title, url = government_text.SOURCES[key]
                    self.assertIn((f"guide {page['slug']}#{section['id']}", f"{key}: {title}"),
                                  self.cited[gs.address(url)])
        # A link in a section's own words too: the Freedom of Information
        # Act's portal, linked from executive#taking-part.
        self.assertIn("guide executive#taking-part", self.where("https://www.foia.gov/"))

    def test_every_map_source(self):
        for key, (_title, url) in government_maps.SOURCES.items():
            if key not in government_text.SOURCES:
                self.assertTrue(any(w.startswith("guide map ") for w in self.where(url)), key)

    def test_every_ballot_table_source(self):
        for code, entry in ballot2026.every_jurisdiction().items():
            for key in ballot2026.OFFICES + ("upper", "lower"):
                item = ballot2026._item(entry, key)
                if item:
                    url = item[3] if key in ballot2026.OFFICES else item[4]
                    self.assertIn(f"2026 ballot table {code} {key}", self.where(url))
        for table, at in ((ballot2026.NEXT, 1), (ballot2026.TERMS, 0), (ballot2026.OPEN_SEATS, 3)):
            for (code, key), value in table.items():
                self.assertIn(f"2026 ballot table {code} {key}", self.where(value[at]))

    def test_a_fragment_is_not_part_of_the_address(self):
        self.assertIn("https://www.supremecourt.gov/opinions/boundvolumes/567BV.pdf", self.cited)
        self.assertFalse([u for u in self.cited if "#" in u])
        self.assertIn("2026 ballot table AK ag", self.where("https://www.akleg.gov/basis/statutes.asp"))

    def test_the_page_codes_statute_links(self):
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, gs.ASSETS))
            with open(os.path.join(tmp, gs.ASSETS, "kyc-x.js"), "w", encoding="utf-8") as handle:
                handle.write('a = \'<a href="https://uscode.house.gov/us/usc/t48/s891/">\' + '
                             'source("https://constitution.congress.gov/constitution/amendment-25/",'
                             ' "x") + "https://www.wikipedia.org/";\n')
            cited = gs.citations(tmp)
            self.assertEqual(cited["https://uscode.house.gov/us/usc/t48/s891/"],
                             [("page code kyc-x.js", "a statute it links")])
            self.assertIn(("page code kyc-x.js", "a statute it links"),
                          cited["https://constitution.congress.gov/constitution/amendment-25/"])
            self.assertNotIn("https://www.wikipedia.org/", cited)
        finally:
            shutil.rmtree(tmp)
        # The committed page code's: the territories' delegate terms.
        self.assertIn("page code kyc-state.js", self.where("https://uscode.house.gov/us/usc/t48/s891/"))


class TestTheRun(unittest.TestCase):
    """Saved once, inside its budget, a silent host left for the next run."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_every_cited_address_is_kept_and_nothing_else(self):
        old = {"sources": {"https://example.org/no-longer-cited": {"checked": "2026-11-01",
                                                                 "verdict": gs.OK}}}
        gs.save_cache(old, self.tmp)
        cache = gs.check_all(self.tmp, read=lambda url, gate: (gs.OPEN, "HTTP 200", url, True),
                             gate=_Gate(interval=0), log=lambda *a: None, today="2026-11-14")
        cited = gs.citations(self.tmp)
        self.assertEqual(sorted(cache["sources"]), sorted(cited))
        saved = gs.load_cache(self.tmp)
        self.assertEqual(saved["sources"], cache["sources"])
        with open(os.path.join(self.tmp, gs.CACHE_PATH), encoding="utf-8") as handle:
            self.assertEqual(len(handle.read().splitlines()), len(cited) + 5)

    def test_the_budget_ends_the_run_cleanly(self):
        ticks = [0.0]

        def clock():
            return ticks[0]

        def read(url, gate):
            ticks[0] += 10
            return gs.OPEN, "HTTP 200", url, True
        said = []
        cache = gs.check_all(self.tmp, read=read, gate=_Gate(interval=0), log=said.append,
                             today="2026-11-14", workers=1, max_seconds=55, clock=clock)
        self.assertEqual(len(cache["sources"]), 6)
        self.assertEqual(gs.load_cache(self.tmp)["sources"], cache["sources"])
        self.assertTrue(any("left for the next run" in line for line in said), said)

    def test_a_host_that_answers_nothing_is_left_for_the_next_run(self):
        asked = []

        def read(url, gate):
            asked.append(url)
            if "uscode.house.gov" in url:
                return gs.NOTHING, "timed out", url, False
            return gs.OPEN, "HTTP 200", url, True
        cache = gs.check_all(self.tmp, read=read, gate=_Gate(interval=0), log=lambda *a: None,
                             today="2026-11-14", workers=1)
        code = [u for u in gs.citations(self.tmp) if "uscode.house.gov" in u]
        self.assertGreater(len(code), gs.HOST_FAILURES)
        self.assertEqual(len([u for u in asked if "uscode.house.gov" in u]), gs.HOST_FAILURES)
        self.assertEqual(len([u for u in code if u in cache["sources"]]), gs.HOST_FAILURES)

    def test_a_second_run_the_same_day_opens_only_what_is_due(self):
        reads = []

        def read(url, gate):
            reads.append(url)
            return ((gs.NOTFOUND, "HTTP 404", url, True) if url == CODE
                    else (gs.OPEN, "HTTP 200", url, True))
        gs.check_all(self.tmp, read=read, gate=_Gate(interval=0), log=lambda *a: None,
                     today="2026-11-14")
        reads.clear()
        gs.check_all(self.tmp, read=read, gate=_Gate(interval=0), log=lambda *a: None,
                     today="2026-11-14")
        self.assertEqual(reads, [])
        cache = gs.check_all(self.tmp, read=read, gate=_Gate(interval=0), log=lambda *a: None,
                             today="2026-11-15")
        self.assertEqual(reads, [CODE])
        self.assertEqual(cache["sources"][CODE]["verdict"], gs.GONE)


class TestTheRefreshAndTheCommand(unittest.TestCase):

    def test_the_command_takes_a_budget(self):
        args = cli.build_parser().parse_args(["guidesources", "--max-minutes", "12"])
        self.assertEqual((args.command, args.max_minutes), ("guidesources", 12))
        self.assertTrue(cli.build_parser().parse_args(["guidesources", "--check"]).check)

    def test_the_refresh_opens_them_in_its_full_run_inside_a_budget(self):
        with open(os.path.join(ROOT, ".github", "workflows", "refresh.yml"), encoding="utf-8") as fh:
            text = fh.read()
        start = text.index("- name: Open the guide's sources again")
        step = text[start:text.index("\n\n", start)]
        self.assertIn("continue-on-error: true", step)          # rule 8
        self.assertIn("if: ${{ !inputs.results_only }}", step)
        command = re.search(r"run: (.+)", step).group(1)
        self.assertTrue(command.startswith("exec python build_profile_site.py guidesources"),
                        command)                                # rule 78
        budget = float(re.search(r"--max-minutes (\d+(?:\.\d+)?)", command).group(1))
        limit = float(re.search(r"timeout-minutes: (\d+)", step).group(1))
        self.assertLessEqual(budget, limit - 5)
        self.assertLess(start, text.index("- name: Rebuild the site data"))


class TestTheCommittedCache(unittest.TestCase):

    def test_it_is_well_formed(self):
        cache = gs.load_cache(ROOT)
        self.assertTrue(cache.get("sources"))
        for url, entry in cache["sources"].items():
            self.assertIn(entry.get("verdict"), gs.VERDICTS, url)
            self.assertRegex(entry.get("checked", ""), r"^\d{4}-\d{2}-\d{2}$", url)
            self.assertTrue(entry.get("evidence"), url)
            self.assertEqual(gs.address(url), url)
            for miss in entry.get("misses") or ():
                self.assertIn(miss["answer"], (gs.NOTFOUND, gs.ELSEWHERE_ANSWER), url)
            if entry["verdict"] == gs.GONE and entry.get("misses"):
                self.assertEqual(gs.settle(entry["misses"]), gs.GONE, url)


if __name__ == "__main__":
    unittest.main()
