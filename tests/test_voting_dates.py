"""Each jurisdiction's key dates for November 3, 2026 (kyc/voting_dates.py).

Seventeen days out the state pages offered "Register to vote" where the
deadline had passed and gave no early-voting or mail-ballot date (audit
2026-10-17, STATEGOV-11, PERSONA-03, FRESHNESS-11, VISUALS-25). The dates
are a hand-editable cache, every value shown sourced to the jurisdiction's
own page; a compiled table is a lead, never a source (rule 50).
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import overrides, validate, voting, voting_dates  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = voting_dates.load(ROOT)


def record(code):
    return copy.deepcopy(DATA["states"][code])


def with_state(code, rec):
    data = copy.deepcopy(DATA)
    data["states"][code] = rec
    return data


class TestTheCommittedCache(unittest.TestCase):
    def test_every_jurisdiction_and_no_problems(self):
        self.assertEqual(set(DATA["states"]), voting_dates.JURISDICTIONS)
        self.assertEqual(voting_dates.problems(DATA), [])
        self.assertEqual(validate.check_voting_dates(DATA), [])

    def test_every_jurisdiction_reaches_the_page(self):
        page = voting_dates.for_page(DATA)
        self.assertEqual(set(page["states"]), voting_dates.JURISDICTIONS)

    def test_the_three_receipt_dates_the_research_left_unsourced_now_cite_the_office(self):
        # MP, WI and WY's mail.returnDeadline.receivedBy had no source entry
        # of their own in the research; each is re-sourced to the office's
        # page or statute (re-read 2026-10-18).
        for code in ("MP", "WI", "WY"):
            rec = DATA["states"][code]
            sources = [s for s in rec["sources"] if s["field"] == "mail.returnDeadline.receivedBy"]
            self.assertTrue(sources, code)
            self.assertTrue(all(voting_dates.official_source(s["url"], code)[0] for s in sources), code)

    def test_no_source_is_a_compiled_table(self):
        for code, rec in DATA["states"].items():
            for source in rec["sources"]:
                self.assertFalse(voting_dates.compiled(source["url"]), f"{code}: {source['url']}")

    def test_the_december_dates_agree_with_the_results_reader(self):
        # Two sources of one date must agree (rule 53).
        self.assertEqual(DATA["states"]["GA"]["runoff"]["date"], overrides.GENERAL_RUNOFFS["GA"][0])
        self.assertEqual(DATA["states"]["LA"]["runoff"]["date"],
                         overrides.OPEN_PRIMARY_SEATS[("LA", "H", 2026)]["runoff"])


class TestSources(unittest.TestCase):
    def test_compiled_tables_are_refused_even_on_a_gov_domain(self):
        for url in ("https://vote.gov/register/texas", "https://www.ncsl.org/elections/x",
                    "https://ballotpedia.org/Texas", "https://en.wikipedia.org/wiki/X",
                    "https://www.vote.org/voter-registration-deadlines/",
                    "http://web.archive.org/web/20261001000000/https://ballotpedia.org/Texas"):
            ok, why = voting_dates.official_source(url, "TX")
            self.assertFalse(ok, url)
            self.assertIn("rule 50", why)

    def test_another_states_domain_is_refused(self):
        self.assertFalse(voting_dates.official_source("https://www.sos.state.tx.us/x", "OK")[0])
        self.assertTrue(voting_dates.official_source("https://www.sos.state.tx.us/x", "TX")[0])
        self.assertFalse(voting_dates.official_source("https://www.votecnmi.gov.mp/x", "GU")[0])
        self.assertFalse(voting_dates.official_source("https://example.com/x", "TX")[0])

    def test_an_archived_official_page_counts_and_says_so(self):
        ok, label = voting_dates.official_source(
            "http://web.archive.org/web/20261004203000/https://gec.guam.gov/2026-important-dates/", "GU")
        self.assertTrue(ok)
        self.assertEqual(label, "gec.guam.gov, as archived 2026-10-04")

    def test_a_file_on_a_shared_host_counts_only_for_the_office_it_is_listed_for(self):
        url = next(iter(voting_dates.OFFICIAL_ELSEWHERE))
        owner = voting_dates.OFFICIAL_ELSEWHERE[url][0]
        self.assertTrue(voting_dates.official_source(url + "view", owner)[0])
        self.assertFalse(voting_dates.official_source(url + "view", "TX")[0])
        self.assertFalse(voting_dates.official_source("https://drive.google.com/file/d/other/view", owner)[0])


class TestProblems(unittest.TestCase):
    def assertProblem(self, data, text):
        found = voting_dates.problems(data)
        self.assertTrue(any(text in p for p in found), found)

    def test_a_value_shown_without_its_own_source_fails(self):
        rec = record("TX")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "earlyVoting.start"]
        self.assertProblem(with_state("TX", rec), "TX earlyVoting.start: shown with no source")

    def test_a_qualifier_may_stand_on_its_values_source(self):
        rec = record("GA")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "mail.returnDeadline.time"]
        self.assertEqual(voting_dates.problems(with_state("GA", rec)), [])

    def test_a_compiled_source_fails_the_build(self):
        rec = record("TX")
        rec["sources"][0] = dict(rec["sources"][0], url="https://www.ncsl.org/elections-and-campaigns/x")
        data = with_state("TX", rec)
        self.assertProblem(data, "rule 50")
        issues = validate.check_voting_dates(data)
        self.assertEqual([i.level for i in issues], ["error"])

    def test_a_source_with_no_quote_fails(self):
        rec = record("TX")
        rec["sources"][0] = dict(rec["sources"][0], quote=" ")
        self.assertProblem(with_state("TX", rec), "a source with no quote")

    def test_dates_must_run_forwards_and_before_the_election(self):
        rec = record("TX")
        rec["earlyVoting"]["end"] = "2026-10-01"
        self.assertProblem(with_state("TX", rec), "does not run forwards")
        rec = record("TX")
        rec["registration"]["mail"]["deadline"] = "2026-11-05"
        self.assertProblem(with_state("TX", rec), "after the election")
        rec = record("TX")
        rec["mail"]["requestDeadline"]["date"] = "October 23"
        self.assertProblem(with_state("TX", rec), "is not a date")

    def test_a_postmark_deadline_whose_ballots_must_arrive_that_day_fails(self):
        rec = record("TX")
        rec["mail"]["returnDeadline"]["receivedBy"] = rec["mail"]["returnDeadline"]["date"]
        self.assertProblem(with_state("TX", rec), "postmarked, yet received the same day")

    def test_a_runoff_needs_words_and_must_agree_with_the_overrides(self):
        rec = record("GA")
        rec["runoff"]["date"] = "2026-12-08"
        self.assertProblem(with_state("GA", rec), "must agree (rule 53)")
        rec = record("TX")
        rec["runoff"]["date"] = "2026-12-12"
        rec["sources"].append({"field": "runoff.date", "url": "https://www.sos.texas.gov/x", "quote": "x"})
        self.assertProblem(with_state("TX", rec), "no RUNOFF_WORDS")

    def test_a_missing_jurisdiction_fails(self):
        data = copy.deepcopy(DATA)
        del data["states"]["OH"]
        self.assertProblem(data, "OH: no record")

    def test_a_record_that_breaks_a_rule_is_not_sent_to_the_page(self):
        rec = record("TX")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "earlyVoting.start"]
        page = voting_dates.for_page(with_state("TX", rec))
        self.assertNotIn("TX", page["states"])
        self.assertIn("GA", page["states"])

    def test_no_cache_is_an_error(self):
        self.assertEqual([i.code for i in validate.check_voting_dates(None)], ["voting-dates-missing"])


class TestThePage(unittest.TestCase):
    page = voting_dates.for_page(DATA)

    def lines(self, code, kind=None):
        return [l for l in self.page["states"][code]["lines"] if kind is None or l["k"] == kind]

    def test_every_line_cites_a_page(self):
        for code, entry in self.page["states"].items():
            for line in entry["lines"]:
                self.assertTrue(line["src"], f"{code} {line['k']}")
                for i in line["src"]:
                    self.assertTrue(voting_dates.official_source(entry["urls"][i], code)[0])

    def test_registration_deadlines_are_grouped_by_date_and_say_how(self):
        georgia = self.lines("GA", "register")
        self.assertEqual([l["d"] for l in georgia], ["2026-10-05"])
        self.assertEqual(georgia[0]["t"], "Last day to register to vote online, by mail or in person")
        louisiana = self.lines("LA", "register")
        self.assertEqual([l["d"] for l in louisiana], ["2026-10-05", "2026-10-13"])
        self.assertEqual(self.page["states"]["LA"]["register"], {"by": "2026-10-13", "how": "online",
                                                                  "sameDay": False})

    def test_same_day_registration_is_said_where_offered(self):
        self.assertTrue(self.page["states"]["NC"]["register"]["sameDay"])
        self.assertTrue(self.lines("NC", "sameday"))
        self.assertFalse(self.lines("GA", "sameday"))

    def test_late_arriving_mail_ballots_are_kept_after_election_day(self):
        arrive = self.lines("CA", "arrive")
        self.assertEqual(arrive[0]["d"], "2026-11-10")
        self.assertTrue(arrive[0]["keep"])
        self.assertTrue(arrive[0]["p"].startswith("The last day"))
        # A state that counts only ballots received by Election Day has no
        # such line.
        self.assertFalse(self.lines("GA", "arrive"))

    def test_runoffs_say_what_they_decide_and_what_the_date_was(self):
        for code in ("GA", "LA", "AR", "MS", "GU", "VI"):
            runoff = self.lines(code, "runoff")
            self.assertEqual(len(runoff), 1, code)
            self.assertTrue(runoff[0]["p"].startswith("The date set for"), code)
            self.assertTrue(runoff[0]["keep"])
        self.assertIn("not for federal offices", self.lines("AR", "runoff")[0]["t"])
        self.assertIn("open primary", self.lines("LA", "runoff")[0]["t"])

    def test_no_election_and_no_registration_are_said_from_their_sources(self):
        self.assertEqual([l["k"] for l in self.page["states"]["PR"]["lines"]], ["none"])
        self.assertEqual(self.lines("ND", "noreg")[0]["t"], "North Dakota has no voter registration")
        self.assertNotIn("register", self.page["states"]["ND"])

    def test_a_time_of_day_is_shown_only_when_it_is_one(self):
        self.assertIn("by 7:00 pm on this day", self.lines("GA", "return")[0]["t"])
        # Texas's "7:00 pm (postmark); received by 5:00 pm November 4" is said
        # by its two dates instead.
        self.assertFalse(any("5:00 pm" in l["t"] for l in self.page["states"]["TX"]["lines"]))


class TestVoteGov(unittest.TestCase):
    def test_vote_gov_deadlines_only_where_the_record_has_none(self):
        cache = voting.load_cache(ROOT)
        shown = voting.for_page(cache, DATA)
        self.assertNotIn("deadlines", shown["TX"])
        self.assertNotIn("deadlines", shown["ND"])
        self.assertNotIn("deadlines", shown["GU"])
        self.assertIn("deadlines", shown["NH"])          # no deadline in its record
        self.assertIn("TX", shown["_dates"]["states"])
        # Without the record, every jurisdiction keeps vote.gov's page.
        self.assertIn("deadlines", voting.for_page(cache)["TX"])


if __name__ == "__main__":
    unittest.main()
