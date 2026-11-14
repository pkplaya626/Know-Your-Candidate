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


def two_days(url, read):
    """What the cache keeps after the same read on two days."""
    entry = gs.merge(None, read, "2026-11-14", url)
    return gs.merge(entry, read, "2026-11-21", url)


class TestWhatAPageSaysOfItself(unittest.TestCase):
    """The review of 2026-11-14: an error page, a script shell, a lapsed
    domain's page, a statute numbered 404 and a sign-in page, each read as
    what it is. Each makes the page it tests."""

    NAV = ("Skip to Content Home Publications Feedback Information For Voters Running for Office "
           "Candidate Filing and Results Press Room Forms About The Board ")

    def test_an_error_page_that_answers_200_concludes_nothing(self):
        """Illinois's CandidatesFiled.aspx answered 200 titled "Error
        Display" (2026-11-14) and the first cache called it ok; Louisiana's
        Law.aspx for a bad id answers 200 under its usual title."""
        il = "https://www.elections.il.gov/ElectionOperations/CandidatesFiled.aspx"
        la = "https://legis.la.gov/legis/Law.aspx?d=99999999"
        pages = (
            (il, "Error Display", self.NAV + "An error has occurred. The State Board of Elections "
                                             "has been automatically notified of this error."),
            (la, "Louisiana Laws - Louisiana State Legislature",
             self.NAV + "An Error Occurred on This Page The Document ID parameter ('d') is missing or "
                        "invalid. Please contact this site's web-master."),
            (CODE, "Runtime Error", "Server Error in '/' Application. Runtime Error Description: An "
                                    "application error occurred on the server."),
            (CODE, "Site Maintenance", "We are performing scheduled maintenance. " * 12),
            (CODE, "Error", self.NAV * 3),
            (CODE, "An error has occurred | Example", self.NAV * 3),
            (CODE, "Service Unavailable", self.NAV * 3),
            (CODE, "Example State", self.NAV + "The site is currently down for maintenance. " * 8),
        )
        for url, title, text in pages:
            body = (f"<html><head><title>{title}</title></head><body><p>{text}</p></body>"
                    f"</html>").encode("utf-8")
            read = gs.assess(url, seen(200, body, chain=[url]))
            self.assertEqual(read[0], gs.NOTHING, title)
            self.assertIn("says an error occurred", read[1], title)
            self.assertEqual(two_days(url, read)["verdict"], gs.UNREAD, title)
        # A statute that speaks of errors, or of maintenance, is a statute;
        # the Code's own notice that features are "temporarily unavailable"
        # is the Code's page.
        rcw = "https://app.leg.wa.gov/RCW/default.aspx?cite=29A.60.210"
        for url, title, text in (
                (rcw, "RCW 29A.60.210: Errors in ballots", "If the canvassing board finds that an error "
                                                          "has occurred in the count, it shall recount. "
                                                          * 10),
                (rcw, "Maintenance of effort - Department of Education", "Text of the page. " * 40),
                (CODE, "2 U.S.C. § 8: Vacancies",
                 "Notice: The uscode.house.gov website is currently operating in a temporary format. "
                 "Some website features and functionality are temporarily unavailable. " * 5)):
            body = page(title, text)
            self.assertEqual(gs.assess(url, seen(200, body, chain=[url]))[0], gs.OPEN, title)

    def test_a_script_shell_concludes_nothing(self):
        """uscode.house.gov has served this project only a script shell (the
        notes on 48 U.S.C. 1422 and 1591, 2026-10-18): read as a page whose
        title names no section, it made all eighty-one Code sources
        "elsewhere" on the second day."""
        shell = (b"<!DOCTYPE html><html><head><title>US Code</title><script src='/app.js'></script>"
                 b"</head><body><div id=root></div></body></html>")
        read = gs.assess(CODE, seen(200, shell))
        self.assertEqual(read[0], gs.NOTHING)
        self.assertIn("almost no text", read[1])
        self.assertEqual(two_days(CODE, read)["verdict"], gs.UNREAD)
        cited = {CODE: [("guide congress#vacancies", "usc-2-8")]}
        self.assertEqual(gs.problems({"sources": {CODE: two_days(CODE, read)}}, cited,
                                     today="2026-11-21"), [])
        # Anywhere: an empty title over no text is no page of the source.
        url = "https://www.house.gov/the-house-explained"
        self.assertEqual(gs.assess(url, seen(200, b"<title></title><div id=app></div>",
                                             chain=[url]))[0], gs.NOTHING)
        # A page with words of its own, titled with another section, is still
        # not the source; so is the site's own "Page Not Found", short or not.
        other = gs.assess(CODE, seen(200, page("2 U.S.C. § 9: Another section")))
        self.assertEqual(other[0], gs.ELSEWHERE_ANSWER)
        self.assertEqual(two_days(CODE, other)["verdict"], gs.ELSEWHERE)
        short = b"<title>Page Not Found - US Code</title><p>Not here.</p>"
        self.assertEqual(gs.assess(CODE, seen(200, short))[0], gs.ELSEWHERE_ANSWER)

    def test_a_lapsed_domains_page_is_not_the_source(self):
        """Rules 35 and 39, read as kyc/localsites.py reads them: thirty-one
        cited addresses are on hosts outside .gov and .us, ncsl.org's four
        among them, and a lapsed domain is bought."""
        url = "https://www.ncsl.org/elections-and-campaigns/state-primary-election-types"
        for chain, title in (
                ([url, "https://www.hugedomains.com/domain_profile.cfm?d=ncsl.org"],
                 "NCSL.org is for sale | HugeDomains"),
                ([url, "https://ww25.ncsl.org/elections-and-campaigns/?subid1=x"], "ncsl.org"),
                ([url, "https://www.ncsl.org/lander"], "ncsl.org"),
                ([url], "ncsl.org - This website is for sale!"),
                ([url], "ncsl.org - Buy this domain"),
                ([url, "https://www.example.org/"], "Example Domain"),
                ([url, "https://slots.example/situs/gacor"], "Situs Slot Gacor Hari Ini")):
            read = gs.assess(url, seen(200, page(title), chain=chain))
            self.assertEqual(read[0], gs.ELSEWHERE_ANSWER, (chain[-1], title))
            entry = two_days(url, read)
            self.assertEqual(entry["verdict"], gs.ELSEWHERE, title)
            self.assertNotIn("subid1", str(entry))
        # A parked page on the domain itself, said in its own words.
        parked = (b"<title>ncsl.org</title><meta name='description' content='Find the best information "
                  b"and most relevant links on all topics related to ncsl.org.'>")
        self.assertEqual(gs.assess(url, seen(200, parked, chain=[url]))[0], gs.ELSEWHERE_ANSWER)
        # A web server's placeholder says nothing of whose it is.
        nginx = page("Welcome to nginx!", "If you see this page, the nginx web server is working.")
        read = gs.assess(url, seen(200, nginx, chain=[url]))
        self.assertEqual(read[0], gs.NOTHING)
        self.assertIn("placeholder", read[1])
        # Its own site's moved page is still the source.
        moved = [url, "https://www.ncsl.org/elections-and-campaigns/primary-types"]
        self.assertEqual(gs.assess(url, seen(200, page("State Primary Election Types"),
                                             chain=moved))[0], gs.OPEN)

    def test_a_statute_numbered_404_is_not_a_not_found_page(self):
        for title in ("RCW 29A.04.404: Definitions", "Sec. 404 - Terms of office",
                      "5 U.S.C. § 404: Records", "§ 24.2-404. Duties of the Department"):
            self.assertFalse(gs._NOT_FOUND_TITLE.search(title), title)
        for title in ("404 - File or directory not found", "404 Not Found", "Error 404",
                      "Oops! 404 error", "Page not found (404)", "That page can’t be found"):
            self.assertTrue(gs._NOT_FOUND_TITLE.search(title), title)
        url = "https://uscode.house.gov/us/usc/t5/s404/"
        self.assertEqual(gs.assess(url, seen(200, page("5 U.S.C. § 404: Records"), chain=[url]))[0],
                         gs.OPEN)

    def test_a_virginia_section_opens_where_its_title_names_it(self):
        """On 2026-11-14 the address of § 24.2-214 answered once under "§
        55.1-1257. Who may recover rent or possession", and the first cache
        called it ok; an address for a section that does not exist is sent
        to its chapter's page."""
        url = "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-214/"
        self.assertEqual(gs.va_section(url), "24.2-214")
        self.assertEqual(gs.assess(url, seen(200, page("§ 24.2-214. Election and term of Senators"),
                                             chain=[url]))[0], gs.OPEN)
        for title, chain in (("§ 55.1-1257. Who may recover rent or possession", [url]),
                             ("§ 24.2-214.1. Another section", [url]),
                             ("§ 24.2-2140. Another section", [url]),
                             ("Code of Virginia Code - Chapter 2. Federal, Commonwealth, and Local "
                              "Officers", [url, "https://law.lis.virginia.gov/vacode/title24.2/chapter2/"])):
            read = gs.assess(url, seen(200, page(title), chain=chain))
            self.assertEqual(read[0], gs.ELSEWHERE_ANSWER, title)
            self.assertIn("does not name Va. Code 24.2-214", read[1])
        dotted = "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-214.1/"
        self.assertEqual(gs.assess(dotted, seen(200, page("§ 24.2-214.1. A section"),
                                                chain=[dotted]))[0], gs.OPEN)
        self.assertIsNone(gs.va_section("https://law.lis.virginia.gov/constitution/article4/section2/"))

    def test_a_redirect_to_the_sites_own_sign_in_page_concludes_nothing(self):
        url = "https://www.example.gov/elections/login"
        sign_in = "https://www.example.gov/signin?returnUrl=/elections/login"
        for title in ("Sign In", "Example State Portal"):
            read = gs.assess(url, seen(200, page(title), chain=[url, sign_in]))
            self.assertEqual(read[0], gs.NOTHING, title)
            self.assertIn("sign-in", read[1])
        for title in ("Log in | Example State", "Please sign in to continue", "Example | Sign In"):
            self.assertEqual(gs.assess(CODE, seen(200, page(title)))[0], gs.NOTHING, title)
        for title in ("Signing statements", "Logan County", "Login.gov", "Sign-on bonuses for poll "
                                                                          "workers"):
            self.assertFalse(gs._SIGN_IN_TITLE.search(title), title)


class TestTheThirdReadersCases(unittest.TestCase):
    """The third read of the source check (2026-11-14): another host's page
    taken for its front page, a domain's own "is for sale" title, betting
    words in a law's text, a statute numbered 404, a Code of Virginia
    section inserted as ":1", a file answered with a page, a front page
    drawn by script, and an error said in a long page's main content. Each
    makes the page it tests."""

    LAW = "https://law.example.gov/statutes/sec-5"

    def test_another_hosts_page_with_a_query_is_not_its_front_page(self):
        """The front-page test read the address as the cache keeps it, with
        another host's query cut off, so ".../index.php?section=5" read as
        that host's front page and a source that moved became elsewhere."""
        for end in ("https://www.newlaws.gov/index.php?section=5", "https://www.newlaws.gov/?p=123",
                    "https://www.newlaws.gov/default.aspx?cite=5"):
            read = gs.assess(self.LAW, seen(200, page("Section 5 - Terms of office"),
                                            chain=[self.LAW, end]))
            self.assertEqual(read[0], gs.OPEN, end)
            # The cache still keeps no other host's query (shown).
            self.assertNotIn("?", read[1] + read[2], end)
            self.assertEqual(two_days(self.LAW, read)["verdict"], gs.OK, end)
        for end in ("https://www.newlaws.gov/", "https://www.newlaws.gov/index.php",
                    "https://newlaws.gov"):
            read = gs.assess(self.LAW, seen(200, page("New Laws"), chain=[self.LAW, end]))
            self.assertEqual(read[0], gs.ELSEWHERE_ANSWER, end)
            self.assertIn("another site's front page", read[1])
            self.assertEqual(two_days(self.LAW, read)["verdict"], gs.ELSEWHERE, end)

    def test_a_domains_own_title_saying_it_is_for_sale(self):
        """"ncsl.org is for sale", a marketplace's title on the lapsed
        domain itself, read open over two days."""
        url = "https://www.ncsl.org/elections-and-campaigns/state-primary-election-types"
        for title in ("ncsl.org is for sale", "NCSL.ORG may be for sale", "www.ncsl.org is for sale!"):
            read = gs.assess(url, seen(200, page(title), chain=[url]))
            self.assertEqual(read[0], gs.ELSEWHERE_ANSWER, title)
            self.assertIn("a domain for sale", read[1])
            self.assertEqual(two_days(url, read)["verdict"], gs.ELSEWHERE, title)
        # A sale that is not a domain's is no lapsed domain.
        for title in ("Parcel 12.5 is for sale", "The fire engine at 12 Main St. is for sale",
                      "Surplus property is for sale - Example County"):
            self.assertFalse(gs.localsites._FOR_SALE.search(title), title)

    def test_betting_words_in_a_laws_text_are_not_a_gambling_page(self):
        """A constitution, statute or ballot question about online betting
        says its words as often as a slot site; only spam's own words, a
        title or heading, or another host a redirect sent it to, say
        gambling (the review made the Florida Constitution "elsewhere")."""
        url = "https://www.flsenate.gov/Laws/Constitution"
        law = ("Section 30. Gaming. The legislature may not authorize online casinos, sportsbooks and "
               "slot machines except as provided herein. " * 6
               + "Sweepstakes casinos, casino sites and online slots are prohibited. " * 3)
        read = gs.assess(url, seen(200, page("The Florida Constitution - The Florida Senate", law),
                                   chain=[url]))
        self.assertEqual(read[0], gs.OPEN, read)
        self.assertEqual(two_days(url, read)["verdict"], gs.OK)
        self.assertEqual(gs.localsites.brand_spam(law), 0)
        # Spam is still spam: in the title, throughout the text in its own
        # words, or on another host a redirect sent the source to.
        spam = "Daftar situs slot gacor terpercaya, togel online, pgbet888 maxwin. " * 2
        for chain, title, text in (
                ([url], "Situs Slot Gacor Hari Ini", ""),
                ([url], "The Florida Constitution", spam),
                ([url, "https://casinos.example/best"], "Best Picks", law)):
            read = gs.assess(url, seen(200, page(title, text), chain=chain))
            self.assertEqual(read[0], gs.ELSEWHERE_ANSWER, title)
            self.assertIn("gambling", read[1])
        self.assertGreaterEqual(gs.localsites.brand_spam(spam), 3)

    def test_a_statute_numbered_404_at_its_titles_start(self):
        for title in ("404.020 Definitions", "404.1 Scope of chapter", "4040 Election code"):
            self.assertFalse(gs._NOT_FOUND_TITLE.search(title), title)
            url = "https://revisor.example.gov/statutes/404.020"
            self.assertEqual(gs.assess(url, seen(200, page(title), chain=[url]))[0], gs.OPEN, title)
        for title in ("404 Not Found", "404", "Error 404 - Example", "404 - Page missing"):
            self.assertTrue(gs._NOT_FOUND_TITLE.search(title), title)

    def test_a_virginia_section_inserted_after_another(self):
        """§ 24.2-946.1:1 is a section of its own: its title does not name
        § 24.2-946.1, and its own address names it."""
        url = "https://law.lis.virginia.gov/vacode/title24.2/chapter9.3/section24.2-946.1/"
        read = gs.assess(url, seen(200, page("§ 24.2-946.1:1. Another section"), chain=[url]))
        self.assertEqual(read[0], gs.ELSEWHERE_ANSWER)
        self.assertIn("does not name Va. Code 24.2-946.1", read[1])
        inserted = "https://law.lis.virginia.gov/vacode/title24.2/chapter9.3/section24.2-946.1:1/"
        self.assertEqual(gs.va_section(inserted), "24.2-946.1:1")
        self.assertEqual(gs.assess(inserted, seen(200, page("§ 24.2-946.1:1. Its own title"),
                                                  chain=[inserted]))[0], gs.OPEN)
        self.assertEqual(gs.assess(url, seen(200, page("§ 24.2-946.1. Its own title"),
                                             chain=[url]))[0], gs.OPEN)

    def test_a_file_is_judged_by_its_first_bytes_whatever_its_type(self):
        """Rule 52: a "Request Rejected" page served under application/pdf
        read open; so would a spreadsheet's or an archive's address that
        answered a page."""
        rejected = (b"<html><head><title>Request Rejected</title></head>"
                    b"<body>The requested URL was rejected.</body></html>")
        error = page("Server Error", "Something went wrong.")
        for url, kind, body in (
                ("https://www.example.gov/a/b.pdf", "application/pdf", rejected),
                ("https://www.example.gov/a/b.PDF", "application/octet-stream", error),
                ("https://www.example.gov/a/list.xlsx",
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", error),
                ("https://www.example.gov/a/tables.zip", "application/zip", b"\x00\x01not a zip"),
                ("https://www.example.gov/media/460/download?inline=", "application/pdf", error)):
            read = gs.assess(url, seen(200, body, kind=kind, chain=[url]))
            self.assertEqual(read[0], gs.NOTHING, url)
            self.assertEqual(two_days(url, read)["verdict"], gs.UNREAD, url)
        # The files themselves open, whatever their type says.
        for url, kind, body in (
                ("https://www.example.gov/a/b.pdf", "text/html", b"%PDF-1.7\n"),
                ("https://www.example.gov/a/list.xlsx", "application/octet-stream", b"PK\x03\x04\x14\x00"),
                ("https://www.example.gov/a/tables.zip", "", b"PK\x03\x04\x14\x00"),
                ("https://www.example.gov/media/460/download?inline=", "application/pdf", b"%PDF-1.4\n")):
            self.assertEqual(gs.assess(url, seen(200, body, kind=kind, chain=[url]))[0], gs.OPEN, url)

    def test_a_deep_link_sent_to_a_front_page_drawn_by_script(self):
        """The front page answered as a script shell concluded nothing,
        because the test of almost no text ran first; the deep link is not
        there either way."""
        url = "https://www.example.gov/elections/candidates/2026"
        shell = (b"<html><head><title>Example</title><script src='/app.js'></script></head>"
                 b"<body><div id=root></div></body></html>")
        read = gs.assess(url, seen(200, shell, chain=[url, "https://www.example.gov/"]))
        self.assertEqual(read[0], gs.ELSEWHERE_ANSWER)
        self.assertIn("its site's front page", read[1])
        self.assertEqual(two_days(url, read)["verdict"], gs.ELSEWHERE)
        # The address itself drawn by script still says nothing.
        self.assertEqual(gs.assess(url, seen(200, shell, chain=[url]))[0], gs.NOTHING)

    def test_an_error_in_a_long_pages_main_content(self):
        """Louisiana's Law.aspx for a bad id says "An Error Occurred on This
        Page" in its <main> (576 characters of text today); past 4,000
        characters of navigation it read open."""
        url = "https://legis.la.gov/legis/Law.aspx?d=99999999"
        nav = TestWhatAPageSaysOfItself.NAV * 60
        self.assertGreater(len(nav), gs.ERROR_TEXT_MAX)
        for inner in ("<main><div><span>An Error Occurred on This Page</span> The Document ID "
                      "parameter ('d') is missing or invalid.</div></main>",
                      "<div><h2>An error has occurred</h2><p>Please try again later.</p></div>"):
            body = (f"<html><head><title>Louisiana Laws - Louisiana State Legislature</title></head>"
                    f"<body><nav>{nav}</nav>{inner}<footer>{nav}</footer></body></html>").encode()
            read = gs.assess(url, seen(200, body, chain=[url]))
            self.assertEqual(read[0], gs.NOTHING, inner)
            self.assertIn("says an error occurred", read[1])
        # A long statute in its <main> that says the words mid-text is a
        # statute.
        law = ("An error has occurred in the canvass when the totals do not agree, and the board "
               "shall recount. " * 60)
        body = (f"<html><head><title>RS 18:1431 - Louisiana State Legislature</title></head><body>"
                f"<nav>{nav}</nav><main><h1>RS 18:1431</h1><p>{law}</p></main></body></html>").encode()
        self.assertEqual(gs.assess(url, seen(200, body, chain=[url]))[0], gs.OPEN)


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
        # A try that concluded nothing is a look (and is said otherwise:
        # test_a_source_confirmed_once_and_turned_away_since_warns).
        tried = dict(entry, tried=later)
        self.assertEqual([d for _l, code, _m, details in gs.problems(self.cache(tried, look),
                                                                     self.CITED, today=later)
                          if code == "guide-source-stale" for d in details],
                         [f"{CONSTITUTION}: last looked at 2026-11-14"])
        self.assertEqual(gs.WARN_DAYS, 30)

    def test_a_source_confirmed_once_and_turned_away_since_warns(self):
        """Opened on 2026-11-14, then a challenge every day: its "ok" is a
        read that old, and past WARN_DAYS it is said - the Law Revision
        Counsel's eighty-one sections behind a challenge would otherwise
        read "ok" for months (the review of 2026-11-14)."""
        refused = (gs.NOTHING, "HTTP 403, a bot wall's or a challenge's page ('Just a moment...')",
                   CODE)
        entry = gs.merge(None, TestTheDays.OPENED, "2026-11-14", CODE)
        day = datetime.date(2026, 11, 15)
        while day <= datetime.date(2027, 1, 30):
            entry = gs.merge(entry, refused, day.isoformat(), CODE)
            day += datetime.timedelta(days=1)
        self.assertEqual((entry["verdict"], entry["checked"], entry["tried"]),
                         (gs.OK, "2026-11-14", "2027-01-30"))
        constitution = {"checked": "2027-01-30", "verdict": gs.UNREAD, "evidence": "HTTP 403"}
        found = gs.problems(self.cache(entry, constitution), self.CITED, today="2027-01-30")
        self.assertEqual([c for _l, c, _m, _d in found], ["guide-source-unconfirmed"])
        self.assertEqual(found[0][0], "warn")
        detail = found[0][3]
        self.assertEqual(len(detail), 1)
        for words in (CODE, "not confirmed since 2026-11-14 (then ok)", "the last on 2027-01-30",
                      "Just a moment"):
            self.assertIn(words, detail[0])
        self.assertIn("Open each by hand", found[0][2])
        # Within WARN_DAYS of its verdict it is not yet said.
        thirty = (datetime.date(2026, 11, 14) + datetime.timedelta(days=gs.WARN_DAYS)).isoformat()
        self.assertFalse(gs.unconfirmed(dict(entry, tried=thirty), thirty))
        self.assertTrue(gs.unconfirmed(entry, "2027-01-30"))
        # One day's 404 that every read since has turned away is said too.
        missing = gs.merge(None, TestTheDays.NOT_FOUND, "2026-11-14", CODE)
        missing = gs.merge(missing, refused, "2027-01-30", CODE)
        self.assertTrue(gs.unconfirmed(missing, "2027-01-30"))
        # A gone or elsewhere source is said as that; an unread one is
        # counted on the info line, its cache claiming nothing.
        gone = {"checked": "2026-11-21", "verdict": gs.GONE, "evidence": "HTTP 404",
                "tried": "2027-01-30"}
        self.assertEqual([c for _l, c, _m, _d in gs.problems(self.cache(gone, constitution),
                                                             self.CITED, today="2027-01-30")],
                         ["guide-source-gone"])
        self.assertFalse(gs.unconfirmed(dict(constitution, tried="2027-01-30"), "2027-03-30"))
        # A read that concludes something clears it.
        self.assertFalse(gs.unconfirmed(gs.merge(entry, TestTheDays.OPENED, "2027-01-31", CODE),
                                        "2027-01-31"))

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
            # Another site's address is kept without its query (shown).
            final = entry.get("final", "")
            if final and not gs._same_site(gs.urllib.parse.urlsplit(url).hostname or "",
                                           gs.urllib.parse.urlsplit(final).hostname or ""):
                self.assertNotIn("?", final, url)

    def test_no_cache_keeps_a_bot_walls_query(self):
        """Radware's wall writes the reader's own IP address, base64-encoded,
        into its redirect's query ("ssr="): no committed cache may hold a
        wall's address with a query, or that parameter anywhere."""
        wall = re.compile(r"(?:" + "|".join(re.escape(h) for h in agent.WALL_HOSTS)
                          + r")[^\"\s]*\?|[?&]ssr=", re.I)
        folder = os.path.join(ROOT, "candidate_profiles_site", "data")
        for name in sorted(os.listdir(folder)):
            if name.endswith(".json"):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    self.assertIsNone(wall.search(handle.read()), name)
        self.assertTrue(wall.search('"https://validate.perfdrive.com/?ssa=1"'))


if __name__ == "__main__":
    unittest.main()
