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

    def test_a_joint_ticket_is_elected_with_the_governor(self):
        def split(states):
            sel, up, note, src = states["OH"]["lt"]
            states["OH"]["lt"] = (sel, not up, note, src)
        self.assertIn("joint ticket", self.broken(split))


if __name__ == "__main__":
    unittest.main()
