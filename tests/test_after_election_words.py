"""The site's words since Election Day (the sweep of 2026-11-11).

Each check makes the state it tests - a held election, a new Congress, a
place that is not a state - and asks the code that writes the words: the
build's side of one test of the phase (``share.post_election``, the day
after ``cycle.general_election_day``; ``cycle.phase`` for the record). The
page's side is in tests/render_test.js (testWordsSinceElectionDay and
testTheJanuaryPage).
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import (federal_build, fec, governor_share, pages, share, stategov, statewide,  # noqa: E402
                 summary, validate)
from kyc.normalize import NOT_READ_NEW_TERM, STATUS_LABELS  # noqa: E402

# The results read after Election Day, and before it.
AFTER = {"election": {"resultsAsOf": "2026-11-10"}}
BEFORE = {"election": {"resultsAsOf": "2026-10-30"}}
# A membership snapshot of the Congress the cycle elects, read after noon
# on January 3 (cycle.phase "record"), and one of the sitting Congress.
RECORD = {"fetched": "2027-01-04T15:00:00Z",
          "legislators": [{"chamber": "House", "termStart": "2027-01-03", "bioguide": "Z900001"}]}
CAMPAIGN = {"fetched": "2026-11-10T15:00:00Z",
            "legislators": [{"chamber": "House", "termStart": "2025-01-03", "bioguide": "Z900001"}]}


class TestAPlaceInASentence(unittest.TestCase):
    """Rule 75: "the District of Columbia" in a sentence, never "District of
    Columbia"; a territory is never "the state"."""

    def test_a_seat_at_large_names_the_place_in_its_own_words(self):
        self.assertEqual(share.seat_phrase("House • DC-AL"),
                         "the U.S. House in the District of Columbia (at large)")
        self.assertEqual(share.seat_phrase("House • VI-AL"),
                         "the U.S. House in the U.S. Virgin Islands (at large)")
        self.assertEqual(share.seat_phrase("House • WY-AL"), "the U.S. House in Wyoming (at large)")
        self.assertEqual(share.seat_phrase("Senate • AL"), "the U.S. Senate in Alabama")

    def test_a_profile_page_names_the_district_with_its_article(self):
        person = {"id": "N000147", "name": "Pat Example", "party": "Democrat", "state": "DC",
                  "chamber": "House", "officeLabel": "House • DC-AL"}
        html = share.render_profile(person, "example.org", {"N000147": person}, {})
        self.assertIn("for the District of Columbia (at large)", html)
        self.assertIn("the District of Columbia&#x27;s page</a>", html)
        self.assertNotIn("for District of Columbia", html)

    def test_a_link_to_a_state_page_names_it_as_the_page_names_itself(self):
        # Rule 75: one name in the navigation, the title and the links. The
        # page is titled "Virgin Islands"; "the U.S. Virgin Islands’ page"
        # named it otherwise (the review of PR #229).
        person = {"id": "P000610", "name": "Pat Example", "party": "Democrat", "state": "VI",
                  "chamber": "House", "officeLabel": "House • VI-AL"}
        html = share.render_profile(person, "example.org", {"P000610": person}, {})
        self.assertIn("the Virgin Islands&#x27; page</a>", html)
        self.assertNotIn("U.S. Virgin Islands&#x27; page", html)
        self.assertEqual(share.page_place("VI"), "the Virgin Islands")
        self.assertEqual(share.page_place("TX"), "Texas")

    def test_the_governor_overlays_never_call_a_territory_a_state(self):
        self.assertNotIn("state", governor_share.PAST)
        self.assertEqual(governor_share.PAST,
                         "This site does not read the election’s results and names no winner")


class TestSeatUpInOneReading(unittest.TestCase):
    """share.seat_up and KYC.seatUpYear: a member seated for a term begun
    after Election Day says when their seat is next up, re-elected or new."""

    def member(self, **extra):
        return dict({"id": "Z1", "name": "Pat Example", "chamber": "House", "electionYear": 2028,
                     "term_start": "2027-01-03 - 2029-01-03"}, **extra)

    def test_a_reelected_holder_and_a_newcomer_on_one_term_read_alike(self):
        self.assertEqual(share.seat_up(self.member(seatUp2026=True)), "Seat up in 2028")
        self.assertEqual(share.seat_up(self.member(seatUp2026=False)), "Seat up in 2028")

    def test_a_seat_on_the_2026_ballot_before_the_new_term_says_nothing(self):
        self.assertIsNone(share.seat_up(self.member(
            seatUp2026=True, electionYear=2026, term_start="2025-01-03 - 2027-01-03")))

    def test_a_former_member_has_no_seat_up(self):
        self.assertIsNone(share.seat_up(self.member(formerMember={"left": "2027-01-03"})))

    def test_a_winner_seated_in_december_for_the_old_term_says_nothing(self):
        # The review of PR #229: a term begun after Election Day that ends
        # with the cycle's Congress read "Seat up in 2026", a day gone by.
        self.assertIsNone(share.seat_up(self.member(
            seatUp2026=True, electionYear=2026, term_start="2026-12-08 - 2027-01-03")))


class TestThePagesWrittenOnce(unittest.TestCase):
    """about.html and districts/index.html, written by the build, in the
    tense of the results it holds (share.post_election)."""

    def test_the_about_page_names_its_datasets_in_the_past_tense_after_the_election(self):
        before = pages.render_about("example.org", {})
        after = pages.render_about("example.org", {}, post=True)
        self.assertIn("Who is running, and their money", before)
        self.assertIn("who is on the ballot", before)
        self.assertIn("Who ran, and their money", after)
        self.assertIn("Primary and November results, and who was on the ballot", after)
        self.assertNotIn("Who is running", after)
        self.assertNotIn("who is on the ballot", after)
        # The "Last read" words are the dataset's, whatever its name.
        self.assertIn("Each profile gives the date its figures run through", after)

    def test_the_districts_directory_too(self):
        self.assertIn("who is on the November ballot",
                      pages.render_districts_index("example.org", BEFORE))
        after = pages.render_districts_index("example.org", AFTER)
        self.assertIn("who was on the November ballot", after)
        self.assertNotIn("who is on the November ballot", after)


class TestTheHolderLineAfterTheElection(unittest.TestCase):
    """statewide.holder_status's "may or may not be" is a line the page
    shows only until the election: after it, it is no problem to settle."""

    LISTED = {"list": {"url": "https://sos.example.gov/list", "by": "Secretary of State",
                       "kind": "candidate list"},
              "candidates": [{"name": "Pat Lee", "surname": "Lee"},
                             {"name": "Sam Lee", "surname": "Lee"}]}

    def test_an_unsettled_holder_is_a_problem_until_the_election(self):
        status, problem = stategov.holder_line("TN", "governor", "Bill Lee", None, self.LISTED)
        self.assertEqual(status["why"], "unchecked")
        self.assertIn("may or may not be Bill Lee", problem)
        status, problem = stategov.holder_line("TN", "governor", "Bill Lee", None, self.LISTED,
                                               after=True)
        self.assertEqual(status["why"], "unchecked")
        self.assertIsNone(problem)


class TestACandidatesOfficesOnceTheCongressSits(unittest.TestCase):
    """A governor candidate's other office the record found open is not said
    to be held once the new Congress sits (history.for_page's before_seat)."""

    def entry(self):
        return {"governor": {"name": "Gov Example"},
                "ballot2026": {"offices": {"governor": {"candidates": {"candidates": [
                    {"name": "Pat Example"}]}}}}}

    def history(self):
        cid = statewide.candidate_id("ZZ", "Pat Example")
        return {"read": "2026-10-30", "people": {cid: {
            "asked": "Pat Example", "congress": [],
            "offices": [{"office": "Member of the State Senate", "where": "Examplestate",
                         "district": None, "from": "2014", "to": None, "open": True,
                         "agree": "exact"}]}}}

    def rows(self, record):
        entry = self.entry()
        with mock.patch("kyc.stategov.candidate_member", return_value=None), \
                mock.patch("kyc.statewide_photos.article_of",
                           return_value={"article": "Pat Example", "read": "2026-10-30"}):
            stategov.attach_history("ZZ", entry, {}, self.history(), {}, [], "2027-01-04",
                                    set(), record)
        row = entry["ballot2026"]["offices"]["governor"]["candidates"]["candidates"][0]
        return row["politicalHistory"]["rows"]

    def test_open_while_the_campaign_runs_and_open_when_read_once_it_sits(self):
        self.assertTrue(self.rows(False)[0].get("current"))
        sat = self.rows(True)[0]
        self.assertFalse(sat.get("current"))
        self.assertEqual(sat.get("openWhenRead"), "2026-10-30")


class TestTheStrictCheckInJanuary(unittest.TestCase):

    def member(self, **extra):
        return dict({"id": "F000478", "name": "Pat Fry", "isCandidate": False, "chamber": "House",
                     "state": "SC", "officeLabel": "House • SC-7", "party": "Republican",
                     "status": "Active Member", "alsoRunningSeat": "Senate • SC"}, **extra)

    def codes(self, profiles, snapshot):
        return [i for i in validate.check_overrides(profiles, {"members": [], "candidates": []},
                                                    snapshot) if i.code == "dual-role"]

    def test_a_dual_role_is_a_campaign_note_and_says_one_member_as_one(self):
        found = self.codes([self.member()], CAMPAIGN)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].message, "1 sitting member is also a 2026 candidate")
        self.assertEqual(self.codes([self.member()], RECORD), [])

    def test_a_member_off_the_ballot_who_has_left_is_not_called_sitting(self):
        former = self.member(id="B000001", name="Vern Example", alsoRunningSeat=None,
                             raceStatus="unlisted", formerMember={"left": "2027-01-03"},
                             status="Former member: left office 2027-01-03")
        sitting = self.member(id="B000002", name="Sam Example", alsoRunningSeat=None,
                              raceStatus="unlisted")
        issue = [i for i in validate.check_results([former, sitting], [])
                 if i.code == "member-not-on-ballot"][0]
        self.assertTrue(issue.message.startswith(
            "1 sitting member and 1 member who has since left Congress are absent"), issue.message)
        self.assertTrue(any("Vern Example" in d and "has left Congress" in d for d in issue.detail))
        only = [i for i in validate.check_results([former], []) if i.code == "member-not-on-ballot"][0]
        self.assertTrue(only.message.startswith("1 member who has since left Congress is absent"),
                        only.message)


class TestLeadersNotYetRecorded(unittest.TestCase):
    """The search's "Leaders in Congress" in the first days of a Congress
    says the federal page's words (federal_build.not_yet_recorded)."""

    def test_the_words_are_the_federal_pages(self):
        self.assertEqual(federal_build.not_yet_recorded(120, "Speaker"),
                         "congress-legislators has not yet recorded the 120th Congress's Speaker")

    def test_said_only_where_no_sitting_member_holds_a_post(self):
        member = {"id": "Z900001", "name": "Pat Example", "isCandidate": False, "chamber": "House",
                  "state": "OH", "party": "Republican", "officeLabel": "House • OH-1"}
        built = summary.build([dict(member)], snapshot=RECORD)
        self.assertEqual(built["leadersUnrecorded"],
                         "congress-legislators has not yet recorded the 120th Congress's leaders; "
                         "this site names them once it does.")
        led = summary.build([dict(member, leadership=list(summary.PRINCIPAL_POSTS))], snapshot=RECORD)
        self.assertNotIn("leadersUnrecorded", led)

    def test_asked_post_by_post(self):
        # The review of PR #229: a record holding the Speaker and not the
        # Senate's leaders said nothing, and "Senate majority leader" fell
        # back to career text without a word.
        member = {"id": "Z900001", "name": "Pat Example", "isCandidate": False, "chamber": "House",
                  "state": "OH", "party": "Republican", "officeLabel": "House • OH-1"}
        some = summary.build([dict(member, leadership=["Speaker of the House", "House Majority Leader",
                                                       "House Minority Leader"])], snapshot=RECORD)
        self.assertEqual(some["leadersUnrecorded"],
                         "congress-legislators has not yet recorded the 120th Congress's President "
                         "Pro Tempore of the Senate, Senate Majority Leader, or Senate Minority Leader; "
                         "this site names them once it does.")


class TestASeatedWinnersMoneyNotReadYet(unittest.TestCase):
    """A winner seated for a new term whose money nothing read holds: said as
    that (rule 19), never "No data"."""

    def winner(self, **extra):
        return dict({"id": "Z900002", "name": "Pat Newcomer", "isCandidate": False,
                     "chamber": "House", "state": "OH", "district": "District 1",
                     "raceRole": "winner", "receipts": "No data", "disbursements": "No data",
                     "quality": {"receipts": "unknown", "disbursements": "unknown"}}, **extra)

    def test_unread_is_said_as_unread(self):
        person = self.winner()
        fec.apply_cache([person], {})
        self.assertEqual(person["quality"]["receipts"], NOT_READ_NEW_TERM)
        self.assertEqual(person["receipts"], STATUS_LABELS[NOT_READ_NEW_TERM])
        self.assertEqual(person["receipts"], "No FEC figures held yet")
        # One absence in the dialog, not two (rule 19).
        self.assertEqual(person["quality"]["funding_sources"], NOT_READ_NEW_TERM)

    def test_a_real_funding_line_is_never_replaced_by_the_absence(self):
        person = self.winner(funding_sources="Individual 80%")
        fec.apply_cache([person], {})
        self.assertEqual(person["funding_sources"], "Individual 80%")

    def test_totals_cached_under_a_curated_rows_name_are_found_by_the_id(self):
        # The review of PR #229: Andy Barr's Senate campaign is cached as
        # "andy barr|KY|S"; seated, his profile is keyed by the roster's
        # "Garland Barr", and a fold that asked only "fec:<id>" keys told the
        # page this site held no totals for a campaign it held at $12.5m.
        person = self.winner(name="Andy Barr", rosterName="Garland Barr", chamber="Senate",
                             state="KY", district=None, fecCandidateId="S6KY00286",
                             rosterFecId="H0KY06104")
        cache = {
            "andy barr|KY|S": {"found": True, "name": "Andy Barr", "candidate_id": "S6KY00286",
                               "receipts": 12541350.16, "disbursements": 9000000.0,
                               "cash_on_hand": 3000000.0, "election_year": 2026,
                               "coverage_start": "2025-01-01", "coverage_end": "2026-09-30"},
            "garland barr|KY|H": {"found": True, "name": "Garland Barr",
                                  "candidate_id": "H0KY06104", "receipts": 10.0},
        }
        fec.apply_cache([person], cache)
        self.assertNotIn("receipts", person.get("quality") or {})
        self.assertEqual(person["receipts"], "$12,541,350.16")
        self.assertEqual(person["fecCandidateId"], "S6KY00286")

    def test_one_id_under_two_keys_is_read_through_the_later_date(self):
        cache = {"a|KY|S": {"candidate_id": "S1", "receipts": 1.0, "coverage_end": "2026-06-30"},
                 "fec:S1": {"candidate_id": "S1", "receipts": 2.0, "coverage_end": "2026-09-30"},
                 "b|KY|S": {"candidate_id": "S2", "receipts": None}}
        index = fec.totals_by_candidate_id(cache)
        self.assertEqual(index["S1"]["receipts"], 2.0)
        self.assertNotIn("S2", index)

    def test_a_folded_filing_still_gives_its_totals(self):
        person = self.winner(fecCandidateId="H6OH01001")
        fec.apply_cache([person], {"fec:H6OH01001": {
            "candidate_id": "H6OH01001", "receipts": 1000.0, "disbursements": 500.0,
            "cash_on_hand": 500.0, "election_year": 2026,
            "coverage_start": "2025-01-01", "coverage_end": "2026-11-23"}})
        self.assertNotIn("receipts", person.get("quality") or {})
        self.assertNotEqual(person["receipts"], STATUS_LABELS[NOT_READ_NEW_TERM])

    def test_a_member_who_did_not_win_a_new_seat_is_untouched(self):
        person = self.winner(raceRole=None)
        fec.apply_cache([person], {})
        self.assertEqual(person["receipts"], "No data")


if __name__ == "__main__":
    unittest.main()
