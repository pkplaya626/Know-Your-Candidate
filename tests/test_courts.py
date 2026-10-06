"""Tests for each state's highest court (kyc/courts.py): the roster read from
the court's own page by its recipe, the names as a reader should see them,
and the court as the page shows it.

A court's members come only from the court. A page that cannot be read by a
script lists the court without members, and says why.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import courts, stategov  # noqa: E402
from kyc.government_maps import HIGH_COURTS, STATES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestNames(unittest.TestCase):

    def test_titles_seats_and_honorifics_are_not_names(self):
        cases = {
            "Chief Justice Karen R. Baker, Position 1": "Karen R. Baker",
            "Associate Justice Cody Hiland, Position 3": "Cody Hiland",
            "Justice Mark S. Massa (107)": "Mark S. Massa",
            "Hon. Andrew M. Mead ": "Andrew M. Mead",
            "The Honorable Wesley G. Russell Jr.": "Wesley G. Russell Jr.",
            "Gary L. Lumpkin – Presiding Judge": "Gary L. Lumpkin",
            "P. Scott Neville, Jr., Chief Justice": "P. Scott Neville, Jr.",
            "Vice Chief Justice John R. Lopez IV": "John R. Lopez IV",
            "Honorable Matthew Fader, Chief Justice": "Matthew Fader",
            "Debra  Todd": "Debra Todd",
        }
        for raw, shown in cases.items():
            self.assertEqual(courts.clean_name(raw), shown, raw)

    def test_a_name_printed_last_first_is_turned_round(self):
        self.assertEqual(courts.clean_name("Rabner, Stuart"), "Stuart Rabner")
        self.assertEqual(courts.clean_name("William H. Bright, Jr."), "William H. Bright, Jr.")

    def test_capitals_read_as_the_person_writes_them(self):
        self.assertEqual(courts.clean_name("NELS S.D. PETERSON"), "Nels S.D. Peterson")
        self.assertEqual(courts.clean_name("CARLA WONG MCMILLIAN"), "Carla Wong McMillian")
        self.assertEqual(courts.clean_name("SHAWN ELLEN LAGRUA"), "Shawn Ellen LaGrua")
        # Nearly all capitals is capitals: Washington's page writes "McCLOUD".
        self.assertEqual(courts.clean_name("JUSTICE SHERYL GORDON McCLOUD"), "Sheryl Gordon McCloud")


class TestChief(unittest.TestCase):

    def test_only_the_chief_is_chief(self):
        import re
        for title in ("Chief Justice", "Chief Judge", "Presiding Judge", "CHIEF JUSTICE"):
            self.assertTrue(re.search(courts.CHIEF, title, re.I), title)
        # Arizona's Vice Chief Justice, Utah's and Washington's Associate Chief
        # Justice, Kentucky's Deputy Chief Justice, Oklahoma's Vice Presiding
        # Judge, Mississippi's Presiding Justices.
        for title in ("Vice Chief Justice", "Associate Chief Justice", "ASSOCIATE CHIEF JUSTICE",
                      "Deputy Chief Justice", "Vice Presiding Judge", "Presiding Justice"):
            self.assertFalse(re.search(courts.CHIEF, title, re.I), title)


class TestRecipes(unittest.TestCase):

    def test_a_recipe_reads_its_slice_and_skips_comments(self):
        page = ("<h2>Alaska Supreme Court Justices</h2><table>"
                "<tr><td class='x'><a href='a.pdf'>Susan M. Carney</a><br>Chief Justice</td></tr>"
                "<tr><td class='x'>Aimee A. Oravec <!-- <a href='b.pdf'>Aimee Oravec</a> --></td></tr>"
                "</table><table><tr><td>Court of Appeals Judge</td></tr></table>")
        got = courts.extract(page, courts.COURTS["AK"])
        self.assertEqual(got, [("Susan M. Carney", True), ("Aimee A. Oravec", False)])

    def test_a_json_recipe(self):
        page = ('{"value": [{"FullName": "<div>Meagan A Flynn</div>", "Job_x0020_Title": '
                '"Supreme Court Chief Justice"}, {"FullName": "<div>Stephen K Bushong</div>", '
                '"Job_x0020_Title": "Supreme Court Justice"}]}')
        got = courts.extract(page, courts.COURTS["OR"])
        self.assertEqual(got, [("Meagan A. Flynn", True), ("Stephen K. Bushong", False)])

    def test_a_vacant_seat_card_is_not_a_person(self):
        page = ('<a href="/about-court/justices-court/chief-justice-patricia-guerrero">Chief Justice '
                'Patricia Guerrero</a><div class="usa-card__brow-color"><div>Kelli M. Evans</div></div>'
                '<div class="usa-card__brow-color"><div>Vacant Seat</div></div>')
        got = courts.extract(page, courts.COURTS["CA"])
        self.assertEqual([n for n, _ in got], ["Patricia Guerrero", "Kelli M. Evans"])

    def test_a_page_that_does_not_fit_its_court_is_refused(self):
        saved = courts._get
        try:
            courts._get = lambda url, headers=None, timeout=60: (
                "<h2><a>Chief Justice A B</a></h2><h2><a>Chief Justice C D</a></h2>")
            recipe = {"url": "https://example.gov/", "item": r"<h2><a>(?P<name>[^<]+)</a></h2>"}
            with self.assertRaises(courts.CourtsError):
                courts.read_court("XX", recipe, 7)          # two chiefs
            with self.assertRaises(courts.CourtsError):
                courts.read_court("XX", recipe, 1)          # more names than seats
            courts._get = lambda url, headers=None, timeout=60: "<p>nothing</p>"
            with self.assertRaises(courts.CourtsError):
                courts.read_court("XX", recipe, 7)          # no names
        finally:
            courts._get = saved

    def test_every_recipe_names_a_page_and_a_way_to_read_it(self):
        for code, recipe in courts.COURTS.items():
            self.assertTrue(recipe["url"].startswith("https://"), code)
            self.assertTrue(recipe.get("item") or recipe.get("items"), code)
            self.assertNotIn(code, courts.UNREADABLE, code)


class TestForState(unittest.TestCase):

    def test_an_unreadable_court_says_why_and_has_no_members(self):
        court = courts.for_state("AL", {"courts": {}})["court"]
        self.assertIn("reset", court["unreadable"])
        self.assertNotIn("members", court)
        self.assertEqual(court["seats"], HIGH_COURTS["AL"][1])

    def test_texas_and_oklahoma_have_two_highest_courts(self):
        cache = {"courts": {
            "TX": {"members": ["A B"], "chief": "A B", "listed": 1, "seats": 9, "url": "u"},
            "TX-CCA": {"members": ["C D"], "chief": "C D", "listed": 1, "seats": 9, "url": "v"}}}
        out = courts.for_state("TX", cache)
        self.assertEqual(out["criminalCourt"]["name"], "Court of Criminal Appeals")
        self.assertEqual(out["criminalCourt"]["word"], "judges")
        self.assertEqual(out["court"]["word"], "justices")


class TestCommitted(unittest.TestCase):

    def test_every_state_has_its_court_read_or_says_why_not(self):
        cache = courts.load_cache(ROOT)
        for code in STATES:
            self.assertTrue(code in cache["courts"] or code in courts.UNREADABLE, code)

    def test_every_roster_fits_its_court(self):
        for code, court in courts.load_cache(ROOT)["courts"].items():
            self.assertLessEqual(court["listed"], court["seats"], code)
            self.assertEqual(court["listed"], len(court["members"]), code)
            self.assertTrue(not court["chief"] or court["chief"] in court["members"], code)

    def test_the_page_gets_each_states_court(self):
        payload, _ = stategov.build(ROOT)
        for code in STATES:
            court = payload["states"][code]["court"]
            self.assertTrue(court.get("members") or court.get("unreadable"), code)


if __name__ == "__main__":
    unittest.main()
