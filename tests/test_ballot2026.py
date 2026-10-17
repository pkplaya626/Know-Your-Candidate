"""Which state offices and legislative seats are on the 2026 ballot."""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import ballot2026  # noqa: E402
from kyc.government_maps import SEATS  # noqa: E402


class TestTable(unittest.TestCase):
    def test_the_table_keeps_its_own_rules(self):
        self.assertTrue(ballot2026.check())

    def test_every_state_and_no_territory(self):
        self.assertEqual(len(ballot2026.STATES), 50)
        self.assertNotIn("DC", ballot2026.STATES)
        self.assertNotIn("PR", ballot2026.STATES)

    def test_chamber_sizes_agree_with_the_seat_table(self):
        # Two sources of one count (rule 53): a slip in either is caught.
        for code, entry in ballot2026.STATES.items():
            self.assertEqual(entry["upper"][1], SEATS[code][0], code)
            self.assertEqual((entry["lower"] or (None, 0))[1], SEATS[code][1], code)

    def test_odd_year_states_elect_none_of_it(self):
        # Louisiana, Mississippi, New Jersey and Virginia elect their governors
        # and legislatures in odd years.
        for code in ("LA", "MS", "NJ", "VA"):
            entry = ballot2026.STATES[code]
            self.assertFalse(entry["governor"][1], code)
            self.assertEqual(entry["upper"][2], 0, code)
            self.assertEqual(entry["lower"][2], 0, code)

    def test_two_year_governors_are_up(self):
        for code in ("NH", "VT"):
            self.assertTrue(ballot2026.STATES[code]["governor"][1], code)

    def test_nebraska_has_one_chamber(self):
        self.assertIsNone(ballot2026.STATES["NE"]["lower"])
        self.assertEqual(ballot2026.STATES["NE"]["upper"][0], "Legislature")

    def test_counts_are_derived_not_typed(self):
        stats = ballot2026.stats()
        self.assertEqual(stats["governor"], sum(1 for e in ballot2026.STATES.values()
                                                if e["governor"][1]))
        self.assertEqual(stats["chambers"], 99)


class TestCheck(unittest.TestCase):
    def broken(self, mutate):
        states = copy.deepcopy(ballot2026.STATES)
        mutate(states)
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(states)
        return str(caught.exception)

    def test_a_missing_state_fails(self):
        self.assertIn("no entry for OH", self.broken(lambda s: s.pop("OH")))

    def test_an_appointed_office_cannot_be_on_the_ballot(self):
        def appoint(states):
            sel, up, note, src = states["TX"]["sos"]
            states["TX"]["sos"] = ("appointed", True, note, src)
        self.assertIn("appointed yet on the ballot", self.broken(appoint))

    def test_a_compiled_table_is_not_a_source(self):
        def cite(states):
            sel, up, note, _src = states["OH"]["ag"]
            states["OH"]["ag"] = (sel, up, note, "https://www.ncsl.org/elections")
        self.assertIn("compiled table", self.broken(cite))

    def test_a_chamber_size_that_disagrees_fails(self):
        def grow(states):
            name, total, up, basis, src = states["OH"]["upper"]
            states["OH"]["upper"] = (name, total + 1, up, basis, src)
        self.assertIn("government_maps.SEATS", self.broken(grow))

    def test_a_county_page_is_not_the_state_record(self):
        def cite(states):
            name, total, up, basis, _src = states["OH"]["upper"]
            states["OH"]["upper"] = (name, total, up, basis,
                                     "https://vote.franklincountyohio.gov/Candidates")
        self.assertIn("compiled table", self.broken(cite))

    def test_the_build_reports_a_broken_table(self):
        from kyc import validate
        self.assertEqual(validate.check_ballot2026(), [])
        original = ballot2026.STATES
        ballot2026.STATES = dict(original)
        ballot2026.STATES.pop("OH")
        try:
            issues = validate.check_ballot2026()
        finally:
            ballot2026.STATES = original
        self.assertEqual([i.level for i in issues], ["error"])

    def test_a_next_year_for_an_office_on_the_ballot_fails(self):
        nxt = dict(ballot2026.NEXT)
        nxt[("GA", "governor")] = (2030, "https://sos.ga.gov/2026-offices-appear-ballot")
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(next_=nxt)
        self.assertIn("on the 2026 ballot, so no next year", str(caught.exception))

    def test_a_next_year_must_follow_2026(self):
        nxt = dict(ballot2026.NEXT)
        nxt[("VA", "governor")] = (2025, nxt[("VA", "governor")][1])
        with self.assertRaises(ballot2026.Ballot2026Error):
            ballot2026.check(next_=nxt)

    def test_an_open_seat_must_be_on_the_ballot(self):
        seats = dict(ballot2026.OPEN_SEATS)
        seats[("VA", "governor")] = ("Abigail Spanberger", "not-listed", None,
                                     "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/",
                                     "a list")
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(open_seats=seats)
        self.assertIn("not on the 2026 ballot", str(caught.exception))

    def test_a_term_limit_says_how_many_terms(self):
        seats = dict(ballot2026.OPEN_SEATS)
        holder, _why, _terms, source, cite = seats[("FL", "governor")]
        seats[("FL", "governor")] = (holder, "term-limit", None, source, cite)
        with self.assertRaises(ballot2026.Ballot2026Error):
            ballot2026.check(open_seats=seats)

    def test_a_joint_ticket_is_elected_with_the_governor(self):
        def split(states):
            sel, up, note, src = states["OH"]["lt"]
            states["OH"]["lt"] = (sel, not up, note, src)
        self.assertIn("joint ticket", self.broken(split))


class TestTerritories(unittest.TestCase):
    """The governor2026 map called Guam, the Virgin Islands and the Northern
    Mariana Islands "not covered" while each elects its governor on Nov 3
    (audit 2026-10-17, RACES-07)."""

    def test_three_territories_elect_a_governor_on_november_3(self):
        up = sorted(c for c, e in ballot2026.TERRITORIES.items() if e["governor"][1])
        self.assertEqual(up, ["GU", "MP", "VI"])

    def test_american_samoa_and_puerto_rico_do_not(self):
        for code in ("AS", "PR"):
            self.assertFalse(ballot2026.TERRITORIES[code]["governor"][1], code)

    def test_a_territory_record_says_it_is_one(self):
        record = ballot2026.for_state("GU")
        self.assertTrue(record["territory"])
        self.assertEqual(sorted(record["offices"]), ["governor", "lt"])
        self.assertEqual(record["chambers"], {})

    def test_a_missing_territory_fails(self):
        territories = dict(ballot2026.TERRITORIES)
        territories.pop("GU")
        with self.assertRaises(ballot2026.Ballot2026Error):
            ballot2026.check(territories=territories)

    def test_dc_has_no_record(self):
        self.assertEqual(ballot2026.for_state("DC"), {})


class TestNextElection(unittest.TestCase):
    """Virginia's page said "No regular elections in 2026" with no year
    (audit 2026-10-17, PERSONA-19). The year is the statute's, never a term
    length's: Virginia's governor is next elected in 2029, its legislature
    in 2027."""

    def test_virginia(self):
        record = ballot2026.for_state("VA")
        self.assertEqual(record["offices"]["governor"]["next"]["year"], 2029)
        self.assertEqual(record["chambers"]["upper"]["next"]["year"], 2027)
        self.assertEqual(record["chambers"]["lower"]["next"]["year"], 2027)

    def test_an_office_without_a_sourced_year_has_none(self):
        # Delaware's governor: no record read gives the year, so none is shown.
        self.assertNotIn("next", ballot2026.for_state("DE")["offices"]["governor"])

    def test_an_office_on_the_ballot_has_no_next_year(self):
        self.assertNotIn("next", ballot2026.for_state("GA")["offices"]["governor"])


class TestOpenSeats(unittest.TestCase):
    """"On the Nov 3, 2026 ballot" sat under Brian Kemp, Gavin Newsom and Tim
    Walz, none of them on it (audit 2026-10-17, STATEGOV-01). An open seat
    is said only from a cited source, and only about the person who holds
    the office."""

    def test_a_term_limited_governor(self):
        seat, problem = ballot2026.open_seat("FL", "governor", "Ron DeSantis", 2)
        self.assertIsNone(problem)
        self.assertEqual(seat["text"], "Ron DeSantis is term-limited")
        self.assertTrue(seat["source"].startswith("http"))

    def test_someone_else_in_the_office_withholds_it(self):
        seat, problem = ballot2026.open_seat("FL", "governor", "Someone Else", 1)
        self.assertIsNone(seat)
        self.assertIn("withheld", problem)

    def test_fewer_terms_than_the_limit_withholds_it(self):
        seat, problem = ballot2026.open_seat("FL", "governor", "Ron DeSantis", 1)
        self.assertIsNone(seat)
        self.assertIn("NGA counts 1", problem)

    def test_a_list_that_does_not_name_them(self):
        seat, problem = ballot2026.open_seat("IA", "governor", "Kim Reynolds", 2)
        self.assertIsNone(problem)
        self.assertEqual(seat["text"], "Kim Reynolds is not on the list of candidates for this office")

    def test_no_entry_says_nothing(self):
        self.assertEqual(ballot2026.open_seat("GA", "governor", "Brian Kemp", 2), (None, None))

    def test_the_build_attaches_them_and_withholds_a_stale_one(self):
        from kyc import stategov
        payload, problems = stategov.build(".")
        fl = payload["states"]["FL"]["ballot2026"]["offices"]["governor"]
        self.assertEqual(fl["openSeat"]["holder"], payload["states"]["FL"]["governor"]["name"])
        self.assertFalse([p for p in problems if "OPEN_SEATS" in p], problems)


if __name__ == "__main__":
    unittest.main()
