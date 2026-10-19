"""The candidates for governor and the statewide offices (kyc/statewide.py,
rule 91).

States marked 36 governorships and some 90 other offices "on the Nov 3,
2026 ballot" and named no one running for any of them (audit 2026-10-17,
FRESHNESS-05, STATEGOV-14, PERSONA-08, RACES-16). The lists are each
election office's own, and the office's holder is read from them for
whoever the rosters name today.
"""

import copy
import unittest
from unittest import mock

from kyc import ballot2026, stategov, statewide

LIST = "https://sos.ga.gov/a-list.pdf"


def office(**over):
    """A synthetic Georgia governor's list that keeps every rule."""
    out = {
        "title": "Governor", "certified": True,
        "list": {"url": LIST, "title": "A list", "quote": "Governor | Pat Example | R",
                 "by": "Georgia Secretary of State", "dated": None, "read": "2026-10-18"},
        "holderResearched": "Brian Kemp", "holderOnList": False,
        "candidates": [
            {"name": "Pat Example", "surname": "Example", "party": "R", "runningMate": None,
             "writeIn": False, "holder": False},
            {"name": "Lee Sample", "surname": "Sample", "party": "D", "runningMate": None,
             "writeIn": False, "holder": False},
        ],
    }
    out.update(over)
    return out


class TestTheCache(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cache = statewide.load(".")

    def test_the_committed_cache_keeps_every_rule(self):
        self.assertEqual(statewide.problems(self.cache), [])

    def test_it_lists_exactly_the_offices_on_the_ballot(self):
        every = dict(ballot2026.STATES, **ballot2026.TERRITORIES)
        for code, entry in every.items():
            up = {k for k in ballot2026.OFFICES if k in entry and entry[k][1]}
            have = set(((self.cache["states"].get(code) or {}).get("offices")) or {})
            self.assertEqual(up, have, code)

    def broken(self, mutate):
        cache = copy.deepcopy(self.cache)
        mutate(cache)
        return " | ".join(statewide.problems(cache))

    def test_an_office_on_the_ballot_with_no_list_fails(self):
        self.assertIn("with no list", self.broken(
            lambda c: c["states"]["GA"]["offices"].pop("governor")))

    def test_a_list_for_an_office_not_on_the_ballot_fails(self):
        def add(c):
            c["states"]["VA"] = {"offices": {"governor": office()}}
        self.assertIn("does not put on the 2026 ballot", self.broken(add))

    def test_a_compiled_table_is_never_the_source(self):
        def wiki(c):
            c["states"]["GA"]["offices"]["lt"]["list"]["url"] = \
                "https://ballotpedia.org/Georgia_elections,_2026"
        self.assertIn("compiled table", self.broken(wiki))

    def test_another_jurisdictions_office_is_not_this_ones(self):
        def elsewhere(c):
            c["states"]["FL"]["offices"]["ag"]["list"]["url"] = LIST
        self.assertIn("not an election office's list", self.broken(elsewhere))

    def test_a_list_needs_its_quote_and_the_day_it_was_read(self):
        def bare(c):
            lst = c["states"]["GA"]["offices"]["lt"]["list"]
            lst["quote"] = ""
            lst["read"] = "yesterday"
        found = self.broken(bare)
        self.assertIn("no quote", found)
        self.assertIn("is not a date", found)

    def test_a_list_that_is_not_certified_says_why(self):
        self.assertIn("must say why", self.broken(
            lambda c: c["states"]["GA"]["offices"]["lt"].update(certified=False)))

    def test_no_portrait_money_or_platform_for_these_people(self):
        def photo(c):
            c["states"]["GA"]["offices"]["lt"]["candidates"][0]["photo"] = "https://x/y.jpg"
        self.assertIn("fields a list does not print: photo", self.broken(photo))

    def test_two_holders_on_one_list_fail(self):
        def two(c):
            for p in c["states"]["GA"]["offices"]["lt"]["candidates"]:
                p["holder"] = True
        self.assertIn("marked as the holder", self.broken(two))

    def test_a_holder_said_off_the_list_whose_surname_is_on_it_fails(self):
        def namesake(c):
            o = c["states"]["GA"]["offices"]["governor"]
            o["candidates"][0]["name"] = "Pat Kemp"
            o["candidates"][0]["surname"] = "Kemp"
        self.assertIn("is said not to be on the list", self.broken(namesake))

    def test_a_namesake_needs_to_be_on_the_list_and_say_why(self):
        def stray(c):
            c["states"]["TN"]["offices"]["governor"]["namesakes"]["Nobody Here"] = ""
        found = self.broken(stray)
        self.assertIn("is not on the list", found)
        self.assertIn("says nothing of why", found)

    def test_every_list_that_is_not_certified_says_so(self):
        for code, entry in self.cache["states"].items():
            for key, o in entry["offices"].items():
                if not o["certified"]:
                    self.assertTrue(o["uncertified"].strip(), (code, key))


class TestNames(unittest.TestCase):

    def test_surnames_as_lists_print_them(self):
        self.assertEqual(statewide.surname("Lombardo, Joseph"), "Lombardo")
        self.assertEqual(statewide.surname("Leland Jake Olinger, II"), "Olinger")
        self.assertEqual(statewide.surname("Brian P. Kemp"), "Kemp")
        self.assertEqual(statewide.surname('Kreiss-Tomkins, Jonathan S. “JKT”'), "Kreiss-Tomkins")
        self.assertEqual(statewide.surname("ROBERT E BROOKS SR"), "BROOKS")

    def test_a_short_given_name_is_the_same_one(self):
        self.assertTrue(statewide.same_given_name("Kim Driscoll", "Kimberley Driscoll"))
        self.assertTrue(statewide.same_given_name("Sarah Huckabee Sanders",
                                                  "Governor Sarah Huckabee Sanders"))
        self.assertTrue(statewide.same_given_name("Raúl Torrez", "RAUL TORREZ"))

    def test_a_different_given_name_is_not(self):
        # Rule 56: "Joe" is not a prefix of "Joseph"; that takes an evidenced
        # form (overrides.STATEWIDE_NAME_FORMS).
        self.assertFalse(statewide.same_given_name("Joe Lombardo", "Lombardo, Joseph"))
        self.assertFalse(statewide.same_given_name("Bill Lee", "Eddie Lee Murphy"))


class TestHolderStatus(unittest.TestCase):
    """Rule 79: "not running" is the list's word, for whoever holds the
    office now; "on the list" only where the list's own holder is them."""

    def test_a_holder_the_list_does_not_name(self):
        status, problem = statewide.holder_status("GA", "governor", office(), "Brian Kemp")
        self.assertIsNone(problem)
        self.assertEqual(status["why"], "not-listed")
        self.assertEqual(status["text"],
                         "Brian Kemp is not on the certified list of candidates for this office")
        self.assertEqual((status["source"], status["cite"]), (LIST, "Georgia Secretary of State"))

    def test_a_holder_on_the_list_is_on_it_never_running_for_re_election(self):
        entry = office(holderResearched="Pat Example", holderOnList=True)
        entry["candidates"][0]["holder"] = True
        status, problem = statewide.holder_status("GA", "governor", entry, "Pat Example")
        self.assertIsNone(problem)
        self.assertEqual(status["why"], "listed")
        self.assertNotIn("re-election", status["text"])
        self.assertEqual(status["text"],
                         "Pat Example is on the certified list of candidates for this office")

    def test_a_list_not_certified_does_not_say_certified(self):
        status, _ = statewide.holder_status(
            "GA", "governor", office(certified=False, uncertified="a county's"), "Brian Kemp")
        self.assertEqual(status["text"], "Brian Kemp is not on the list of candidates for this office")

    def test_a_namesake_settles_nothing(self):
        # A candidate carrying the holder's surname whom the list does not
        # mark as the holder: never guessed either way (rule 25).
        entry = office()
        entry["candidates"][0]["name"] = "Pat Kemp"
        status, problem = statewide.holder_status("GA", "governor", entry, "Brian Kemp")
        self.assertIsNone(status)
        self.assertIn("may or may not be Brian Kemp", problem)

    def test_a_recorded_namesake_is_set_aside_for_that_holder_only(self):
        entry = office(namesakes={"Pat Kemp": "a different given name"})
        entry["candidates"][0]["name"] = "Pat Kemp"
        status, _ = statewide.holder_status("GA", "governor", entry, "Brian Kemp")
        self.assertEqual(status["why"], "not-listed")
        status, problem = statewide.holder_status("GA", "governor", entry, "Chris Kemp")
        self.assertIsNone(status)
        self.assertIn("read with Brian Kemp", problem)

    def test_a_marked_holder_with_another_given_name_needs_an_evidenced_form(self):
        entry = office(holderResearched="Joe Example", holderOnList=True)
        entry["candidates"][0].update(name="Example, Joseph", holder=True)
        status, problem = statewide.holder_status("GA", "governor", entry, "Joe Example")
        self.assertIsNone(status)
        self.assertTrue(problem)
        with mock.patch.dict("kyc.overrides.STATEWIDE_NAME_FORMS",
                             {("GA", "governor", "Joe Example"): ("Example, Joseph", "evidence")}):
            status, problem = statewide.holder_status("GA", "governor", entry, "Joe Example")
        self.assertEqual(status["why"], "listed")

    def test_a_new_holder_is_still_read_against_the_list(self):
        # The list was read for Brian Kemp; someone else holding the office
        # is not on it either, and the change is reported.
        status, problem = statewide.holder_status("GA", "governor", office(), "Chris Carr")
        self.assertEqual(status["why"], "not-listed")
        self.assertIn("read with Brian Kemp", problem)


class TestHolderLine(unittest.TestCase):

    def test_a_term_limit_stays_beside_the_list(self):
        status, problem = stategov.holder_line("FL", "governor", "Ron DeSantis", 2,
                                               office(holderResearched="Ron DeSantis"))
        self.assertIsNone(problem)
        self.assertEqual(status["why"], "term-limit")
        self.assertEqual(status["text"], "Ron DeSantis is term-limited")
        self.assertEqual(status["then"]["text"],
                         "is not on the certified list of candidates for this office")

    def test_a_term_limited_holder_the_list_names_is_shown_as_neither(self):
        entry = office(holderResearched="Ron DeSantis", holderOnList=True)
        entry["candidates"][0].update(name="Ron DeSantis", surname="DeSantis", holder=True)
        status, problem = stategov.holder_line("FL", "governor", "Ron DeSantis", 2, entry)
        self.assertEqual(status["why"], "unchecked")
        self.assertIn("neither is shown", problem)

    def test_no_list_falls_back_to_the_table(self):
        status, _ = stategov.holder_line("MN", "governor", "Pat Holder", 2, None)
        self.assertEqual(status["why"], "unchecked")


class TestThePage(unittest.TestCase):

    def test_printed_names_first_then_write_ins_each_by_surname(self):
        entry = office()
        entry["candidates"] += [
            {"name": "Ann Zed", "surname": "Zed", "party": "WRI", "runningMate": None,
             "writeIn": True, "holder": False},
            {"name": "Bo Able", "surname": "Able", "party": None, "runningMate": None,
             "writeIn": True, "holder": False},
        ]
        page = statewide.for_page(entry)
        self.assertEqual([p["name"] for p in page["candidates"]],
                         ["Pat Example", "Lee Sample", "Bo Able", "Ann Zed"])
        # A write-in's "party" that only says it is a write-in is dropped.
        self.assertNotIn("party", page["candidates"][3])
        self.assertEqual(page["candidates"][0]["party"], "R")
        self.assertEqual(page["by"], "Georgia Secretary of State")

    def test_the_build_lists_every_office_on_the_ballot(self):
        payload, problems = stategov.build(".")
        for code, state in payload["states"].items():
            for key, item in ((state.get("ballot2026") or {}).get("offices") or {}).items():
                if not item["up"]:
                    self.assertNotIn("candidates", item, (code, key))
                    continue
                self.assertTrue(item["candidates"]["candidates"], (code, key))
                for person in item["candidates"]["candidates"]:
                    # The list's words only: never a portrait, a figure or a
                    # profile id (rules 24, 25, 27).
                    self.assertLessEqual(set(person), {"name", "party", "runningMate",
                                                       "ballotName", "writeIn", "holder"})
                # With a list in hand, "not checked" is said only where the
                # list did not settle the holder, and the build says why.
                status = item.get("holderStatus") or {}
                if status.get("why") == "unchecked":
                    self.assertTrue([p for p in problems if p.startswith(f"{code} {key}:")],
                                    (code, key))


if __name__ == "__main__":
    unittest.main()
