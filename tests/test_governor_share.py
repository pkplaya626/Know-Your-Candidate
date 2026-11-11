"""Share pages for the governors and the candidates for governor (rules 91, 96).

The governor cards open an overlay behind "#/official/gov-<ST>", which
crawlers drop. Each governor and each candidate on an election office's list
now has o/<id>.html, in the overlay's words (``shareWords`` in
kyc-governor.js), which the render suite compares for every one of them
(``testGovernorSharePages``) and asks every case of this fixture about on
both clocks; these check the pipeline's side.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, federal_build, governor_share, guide_photos, official_share  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
HOST = "example.org"
LIST = {"url": "https://sos.example.gov/list.pdf", "source": "the Secretary of State’s list",
        "read": "2026-10-18"}
STATUS = {"holder": "Brian Kemp", "source": "https://sos.example.gov/list.pdf", "cite": "the list",
          "why": "not-listed", "text": "Brian Kemp is not among the candidates for this office"}
SOURCES = {"nga": ["National Governors Association, current governors",
                   "https://www.nga.org/governors/", "2026-11-02"]}


def payload(people=None, up=True, governor=None):
    gov = governor or {"id": "gov-GA", "name": "Brian Kemp", "party": "Republican", "partyKey": "R",
                       "since": "January 14, 2019", "profile": "https://www.nga.org/governors/georgia/",
                       "headshot": "https://www.nga.org/wp-content/uploads/kemp.jpg",
                       "headshotBy": "National Governors Association"}
    item = {"selection": "elected", "up": up, "note": "4-year term; term begins 01/2027",
            "source": "https://sos.example.gov/offices", "holderStatus": STATUS}
    if up:
        item["candidates"] = dict(LIST, candidates=people if people is not None else [
            {"id": "gov-GA-keisha-lance-bottoms", "name": "Keisha Lance Bottoms", "party": "Democratic",
             "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/K.jpg/250px-K.jpg",
             "photoCredit": {"by": "Executive Office of the President", "licence": "Public domain",
                             "page": "https://commons.wikimedia.org/wiki/File:K.jpg",
                             "via": "Wikimedia Commons", "year": 2022}},
            {"id": "gov-GA-david-c-byrne", "name": "David C. Byrne", "writeIn": True,
             "photo": "https://example.org/nope.jpg", "photoCredit": {"by": "Nobody"}},
        ])
    else:
        item.pop("holderStatus")
        item["next"] = {"year": 2029, "source": "https://law.example.gov/"}
    return {"states": {"GA": {"governor": gov, "ballot2026": {"offices": {"governor": item}}}},
            "sources": SOURCES}


def found(oid, data=None):
    return governor_share.governors(data or payload())[oid]


class TestWordsTable(unittest.TestCase):
    """Every case is in tests/fixtures/governor_share_words.json, which the
    render suite asks ``KYC.governor.shareWords`` about on both clocks."""

    def test_the_fixture_is_this_codes(self):
        with open(governor_share.WORDS_TABLE, encoding="utf-8", newline="") as handle:
            on_disk = handle.read()
        self.assertEqual(on_disk, governor_share.words_table_text(),
                         'regenerate: python -c "from kyc import governor_share; '
                         'governor_share.write_words_table()" after making the same change in '
                         "assets/kyc-governor.js")

    def test_it_holds_both_kinds_both_clocks_and_every_mark(self):
        rows = governor_share.words_table()["cases"]
        # Three clocks: the campaign's, after Election Day, and a January day
        # after the terms the 2026 election chose have begun (kyc/terms_begin.py).
        self.assertEqual({(row[0], row[2]) for row in rows},
                         {(False, "governor"), (True, "governor"), (False, "candidate"), (True, "candidate"),
                          ("2027-01-10", "governor"), ("2027-01-10", "candidate")})
        marks = {row[7]["mark"] for row in rows}
        for words in ("This office is on the Nov 3, 2026 ballot", "This office was on the Nov 3, 2026 ballot",
                      "Not elected in 2026 Next elected: November 2029",
                      "Not elected in 2026 Next election: October 2027", "Not elected in 2026"):
            self.assertIn(words, marks)
        statuses = {row[7]["status"] for row in rows}
        self.assertEqual(statuses - {""}, {"On the Nov 3, 2026 ballot", "Was on the Nov 3, 2026 ballot",
                                           "Write-in candidate", "Was a write-in candidate"})


class TestWords(unittest.TestCase):

    def test_a_governor_in_the_overlays_words(self):
        words = governor_share.share_words(found("gov-GA"), False, SOURCES)
        self.assertEqual(words["kind"], "Governor")
        self.assertEqual(words["office"], "Governor of Georgia")
        self.assertEqual(words["since"], "In office since January 14, 2019")
        self.assertEqual(words["mark"], "This office is on the Nov 3, 2026 ballot")
        self.assertEqual(words["holder"], "Open seat: Brian Kemp is not among the candidates for this "
                                          "office (the list).")
        self.assertEqual(words["source"],
                         "Governor: National Governors Association, current governors, read Nov. 2, 2026.")
        self.assertEqual(words["past"], "")

    def test_a_candidate_in_the_lists_words_alone(self):
        words = governor_share.share_words(found("gov-GA-keisha-lance-bottoms"), False, SOURCES)
        self.assertEqual((words["kind"], words["seeking"], words["office"]),
                         ("Governor (Candidate)", "Running for", "Governor • GA"))
        self.assertEqual(words["status"], "On the Nov 3, 2026 ballot")
        self.assertEqual(words["term"], "Term 4 years (if elected)")
        self.assertEqual(words["source"], "Source: the Secretary of State’s list (read Oct. 18, 2026).")
        # Never a party's money, a platform or a profile (rules 25, 27).
        self.assertEqual(words["record"], "")

    def test_after_election_day_the_past_tense_the_results_and_no_winner(self):
        words = governor_share.share_words(found("gov-GA-keisha-lance-bottoms"), True, SOURCES,
                                           "https://results.example.gov/")
        self.assertEqual(words["seeking"], "Ran for")
        self.assertEqual(words["status"], "Was on the Nov 3, 2026 ballot")
        self.assertEqual(words["term"], "Term 4 years")
        self.assertEqual(words["past"], governor_share.PAST)
        self.assertEqual(words["results"], "https://results.example.gov/")
        gov = governor_share.share_words(found("gov-GA"), True, SOURCES, "https://results.example.gov/")
        self.assertEqual(gov["mark"], "This office was on the Nov 3, 2026 ballot")
        self.assertEqual(gov["holder"], "", "after the election the office has a winner, unnamed here")
        page = governor_share.render_governor("gov-GA-keisha-lance-bottoms",
                                              found("gov-GA-keisha-lance-bottoms"), HOST, True, SOURCES,
                                              "https://results.example.gov/")
        self.assertIn('names no winner: <a href="https://results.example.gov/"', page)
        self.assertIn("ran for governor of Georgia", page)
        self.assertNotRegex(page.replace("names no winner", ""), r"(?i)\b(won|winner)\b")

    def test_after_election_day_a_governors_description_says_no_winner_is_named(self):
        # The integration of PR #180 on results-day data: the governor's
        # unfurl read "This office was on the Nov 3, 2026 ballot." and
        # stopped, while the candidates' said this site names no winner.
        f = found("gov-GA")
        words = governor_share.share_words(f, True, SOURCES, "https://results.example.gov/")
        _, description = governor_share.describe(f, words)
        self.assertIn("This office was on the Nov 3, 2026 ballot. " + governor_share.PAST, description)
        _, before = governor_share.describe(f, governor_share.share_words(f, False, SOURCES))
        self.assertNotIn(governor_share.PAST, before)
        data = payload(up=False)
        f = found("gov-GA", data)
        _, off = governor_share.describe(f, governor_share.share_words(f, True, SOURCES, "https://r.example.gov/"))
        self.assertNotIn(governor_share.PAST, off, "an office not on the ballot has no result to point to")

    def test_a_governor_not_on_this_ballot_says_when_next(self):
        data = payload(up=False)
        words = governor_share.share_words(found("gov-GA", data), True, SOURCES, "https://r.example.gov/")
        self.assertEqual(words["mark"], "Not elected in 2026 Next elected: November 2029")
        self.assertEqual((words["past"], words["results"]), ("", ""))
        self.assertEqual(list(governor_share.governors(data)), ["gov-GA"])

    def test_the_description_writes_the_marks_two_parts_as_two_sentences(self):
        # PR #180 review: "Not elected in 2026 Next elected: November 2029."
        # ran the mark's two parts together in the unfurl. The overlay's
        # words (the mark) stay as they are; the description punctuates them.
        data = payload(up=False)
        f = found("gov-GA", data)
        words = governor_share.share_words(f, False, SOURCES)
        _, description = governor_share.describe(f, words)
        self.assertIn("Not elected in 2026. Next elected: November 2029.", description)
        self.assertNotIn("2026 Next", description)
        data["states"]["GA"]["ballot2026"]["offices"]["governor"]["next"] = {
            "year": 2027, "month": "October", "source": "https://law.example.gov/"}
        f = found("gov-GA", data)
        _, description = governor_share.describe(f, governor_share.share_words(f, False, SOURCES))
        self.assertIn("Not elected in 2026. Next election: October 2027.", description)
        page = governor_share.render_governor("gov-GA", f, HOST, False, SOURCES)
        self.assertIn("Not elected in 2026. Next election: October 2027.", page)

    def test_a_write_in_cites_the_list_of_write_ins_that_names_them(self):
        # PR #180 review: Georgia's, Maine's, Texas's and Wisconsin's
        # write-ins were cited to the printed list, which does not hold
        # their names; the office keeps their own list apart (rules 19, 91).
        data = payload()
        data["states"]["GA"]["ballot2026"]["offices"]["governor"]["candidates"]["writeIns"] = {
            "url": "https://sos.example.gov/writeins.pdf", "by": "the Secretary of State",
            "read": "2026-10-28", "source": "the Secretary of State’s list of certified write-in candidates"}
        byrne = found("gov-GA-david-c-byrne", data)
        words = governor_share.share_words(byrne, False, SOURCES)
        self.assertEqual(words["source"], "Source: the Secretary of State’s list of certified write-in "
                                          "candidates (read Oct. 28, 2026).")
        page = governor_share.render_governor("gov-GA-david-c-byrne", byrne, HOST, False, SOURCES)
        self.assertIn('<a href="https://sos.example.gov/writeins.pdf"', page)
        self.assertNotIn("https://sos.example.gov/list.pdf", page.split('class="share-source')[1])
        # A printed candidate keeps the printed list; with no list of
        # write-ins apart, a write-in keeps it too.
        printed = governor_share.share_words(found("gov-GA-keisha-lance-bottoms", data), False, SOURCES)
        self.assertEqual(printed["source"], "Source: the Secretary of State’s list (read Oct. 18, 2026).")
        alone = governor_share.share_words(found("gov-GA-david-c-byrne"), False, SOURCES)
        self.assertEqual(alone["source"], "Source: the Secretary of State’s list (read Oct. 18, 2026).")
        # The fixture the render suite asks the page code about holds such a case.
        self.assertTrue(any(row[3].get("writeIn") and "write-in candidates" in row[7]["source"]
                            for row in governor_share.words_table()["cases"]))


class TestPicture(unittest.TestCase):

    def test_the_ngas_headshot_with_its_credit(self):
        image, credit = governor_share.picture(found("gov-GA"), HOST)
        self.assertEqual(image, "https://www.nga.org/wp-content/uploads/kemp.jpg")
        self.assertEqual(credit["by"], "National Governors Association")
        no_credit = payload(governor={"id": "gov-GA", "name": "X", "headshot": "https://e.org/x.jpg"})
        self.assertEqual(governor_share.picture(found("gov-GA", no_credit), HOST), (None, None))

    def test_a_copy_and_a_hosted_file_on_the_sites_host(self):
        heavy = dict(found("gov-GA")["person"], photoCopy={
            "src": "photos/0123456789abcdef0123.jpg", "of": "https://www.nga.org/wp-content/uploads/kemp.jpg",
            "ofBytes": 2_250_000})
        image, credit = governor_share.picture({"kind": "governor", "code": "GA", "person": heavy}, HOST)
        self.assertEqual(image, "https://example.org/photos/0123456789abcdef0123.jpg")
        self.assertIn("2.3 MB", official_share.credit_html(credit, HOST))
        hosted = {"kind": "candidate", "code": "GA", "person": {
            "name": "X", "photo": "photos/abcdefabcdefabcdefab.png",
            "photoCredit": {"by": "Washington Secretary of State", "page": "https://voter.example.gov/x"}}}
        self.assertEqual(governor_share.picture(hosted, HOST)[0],
                         "https://example.org/photos/abcdefabcdefabcdefab.png")
        self.assertEqual(governor_share.picture(hosted, None), (None, None))

    def test_a_write_in_shows_none(self):
        self.assertEqual(governor_share.picture(found("gov-GA-david-c-byrne"), HOST), (None, None))
        page = governor_share.render_governor("gov-GA-david-c-byrne", found("gov-GA-david-c-byrne"), HOST)
        self.assertIn("assets/social-card.png", page)
        self.assertNotIn("share-photo-credit", page)


class TestPages(unittest.TestCase):

    def test_its_own_address_and_the_overlay_it_opens(self):
        page = governor_share.render_governor("gov-GA", found("gov-GA"), HOST, False, SOURCES)
        self.assertIn('<link rel="canonical" href="https://example.org/o/gov-GA.html">', page)
        self.assertIn('href="../states/ga.html#/official/gov-GA"', page)
        self.assertIn('<a href="../states/ga.html#governor">Georgia’s page</a> names the governor', page)
        self.assertIn('data-share="governor"', page)
        cand = governor_share.render_governor("gov-GA-keisha-lance-bottoms",
                                              found("gov-GA-keisha-lance-bottoms"), HOST, False, SOURCES)
        self.assertIn('href="../states/ga.html#/official/gov-GA-keisha-lance-bottoms"', cand)
        self.assertIn('<a href="https://sos.example.gov/list.pdf"', cand)
        self.assertIn("Keisha Lance Bottoms (Democratic): running for governor of Georgia.", cand)
        self.assertNotIn(" • GA.", cand.split("<body")[0], "no card's bullet in the description")

    def test_everyone_the_overlay_answers_to_and_no_profile(self):
        data = guide_photos.read_stategov(ROOT)
        everyone = governor_share.governors(data)
        self.assertTrue(all(governor_share.is_governor_id(gid) for gid in everyone))
        for code, state in data["states"].items():
            self.assertIn(f"gov-{code}", everyone)
            item = governor_share.office_item(state) or {}
            for person in ((item.get("candidates") or {}).get("candidates") or []) if item.get("up") else []:
                self.assertEqual(everyone[person["id"]]["kind"], "candidate")


class TestBuiltAndVerified(unittest.TestCase):
    """Written beside the officials' pages, checked by verify, cleaned up
    when a candidate is no longer listed, never rewritten unchanged, and
    left alone - with the officials' - when data/stategov.js is missing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        os.makedirs(os.path.join(root, emit.SITE_DIR))
        with open(os.path.join(root, emit.CNAME_FILE), "w", encoding="utf-8") as f:
            f.write("example.org\n")
        self.root = root
        self.site = os.path.join(root, emit.SITE_DIR)
        self.folder = os.path.join(self.site, official_share.OFFICIAL_DIR)

    def tearDown(self):
        self.tmp.cleanup()

    def patched(self, data):
        broken = mock.patch.object(federal_build, "build",
                                   side_effect=federal_build.FederalBuildError("no caches"))
        return broken, mock.patch.object(guide_photos, "read_stategov", lambda root: data)

    def write(self, data):
        a, b = self.patched(data)
        with a, b:
            return emit.write_state_pages([], self.root, summary={"states": {}}, stamp_from=ROOT, races=[])

    def check(self, data):
        a, b = self.patched(data)
        with a, b:
            return emit.check_state_pages([], self.root, {"states": {}}, ROOT, [])

    def test_written_checked_cleaned_up_and_kept(self):
        data = payload()
        self.write(data)
        self.assertEqual(sorted(os.listdir(self.folder)),
                         ["gov-GA-david-c-byrne.html", "gov-GA-keisha-lance-bottoms.html", "gov-GA.html"])
        with open(os.path.join(self.site, "sitemap.xml"), encoding="utf-8") as f:
            self.assertIn("<loc>https://example.org/o/gov-GA.html</loc>", f.read())
        self.assertEqual([p for p in self.check(data) if "gov-" in p[0]], [])
        page = os.path.join(self.folder, "gov-GA.html")
        os.utime(page, (1_000_000_000, 1_000_000_000))
        self.assertNotIn(page, self.write(data))
        # An official's page stays while the federal build cannot run.
        with open(os.path.join(self.folder, "x-someone.html"), "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>")
        # A candidate no longer on the list is an orphan, and removed.
        smaller = payload(people=[])
        stale = {os.path.basename(rel): why for rel, why in self.check(smaller)
                 if os.path.dirname(rel).endswith(os.sep + "o")}
        self.assertEqual(stale, {"gov-GA-david-c-byrne.html": "orphaned",
                                 "gov-GA-keisha-lance-bottoms.html": "orphaned"})
        self.write(smaller)
        self.assertEqual(sorted(os.listdir(self.folder)), ["gov-GA.html", "x-someone.html"])
        # Without data/stategov.js none is written and none removed.
        self.write({})
        self.assertEqual(sorted(os.listdir(self.folder)), ["gov-GA.html", "x-someone.html"])
        self.assertEqual([p for p in self.check({}) if "o" + os.sep in p[0]], [])


if __name__ == "__main__":
    unittest.main()
