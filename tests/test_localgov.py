"""Tests for counties and local governments: the Census listing reader
(kyc/localgov.py) and the county pages' data (kyc/counties.py).

Two Census products are held to agree - the Government Units listing and the
published table of counts - and governments are joined to counties on the
Census code, never a name.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import census, counties, localgov  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestNames(unittest.TestCase):

    def test_capitals_read_as_names(self):
        cases = {
            "COUNTY OF AUTAUGA": "County of Autauga",
            "CITY OF MCALLEN": "City of McAllen",
            "ALDINE ISD": "Aldine ISD",
            "O'FALLON FIRE PROTECTION DISTRICT": "O'Fallon Fire Protection District",
            "HARRIS COUNTY MUNICIPAL UTILITY DISTRICT NO 400":
                "Harris County Municipal Utility District No 400",
            "WEST-HARRIS COUNTY REGIONAL WATER AUTHORITY": "West-Harris County Regional Water Authority",
            "BOARD OF EDUCATION OF THE CITY OF ST. LOUIS": "Board of Education of the City of St. Louis",
            "TOWNSHIP OF II": "Township of II",
        }
        for raw, shown in cases.items():
            self.assertEqual(localgov.display_name(raw), shown, raw)


class TestAgreement(unittest.TestCase):

    def test_a_listing_that_disagrees_with_the_table_is_refused(self):
        listing = {"TX": {"counties": {"48001": {"name": "Anderson", "governments": [
            {"type": "county"}, {"type": "municipal"}]}}, "statewide": []}}
        table = {"states": {"TX": {"county": 1, "municipal": 2, "township": None,
                                   "special": 0, "school": 0}}}
        problems = localgov.check_against_table(listing, table)
        self.assertEqual(problems, ["TX municipal: listing 1, table 2"])

    def test_school_systems_another_government_runs_are_not_counted(self):
        listing = {"MD": {"counties": {"24001": {"name": "Allegany", "governments": [
            {"type": "county"}, {"type": "dependent"}]}}, "statewide": []}}
        table = {"states": {"MD": {"county": 1, "municipal": 0, "township": None,
                                   "special": 0, "school": None}}}
        self.assertEqual(localgov.check_against_table(listing, table), [])

    def test_the_committed_listing_agrees_with_the_table_everywhere(self):
        table = census.load_cache(ROOT)
        states = {}
        for name in sorted(os.listdir(os.path.join(ROOT, localgov.OUT_DIR))):
            code = name[:-5].upper()
            data = localgov.load(code, ROOT)
            states[code] = {"counties": data["counties"], "statewide": data["statewide"]}
        self.assertEqual(localgov.check_against_table(states, table), [])


class TestCountyPages(unittest.TestCase):

    def test_governments_join_their_county_by_census_code(self):
        page = counties.build_state("DE", ROOT, {})
        self.assertEqual(sorted(page["counties"]), ["10001", "10003", "10005"])
        listing = localgov.load("DE", ROOT)
        for fips, entry in listing["counties"].items():
            self.assertEqual(len(page["governments"][fips]), len(entry["governments"]))
        self.assertEqual(page["unmatched"], [])

    def test_an_address_in_capitals_keeps_its_path(self):
        self.assertEqual(counties.web_address("HTTP://WWW.KATYISD.ORG/"), "http://www.katyisd.org/")
        self.assertEqual(counties.web_address("HTTPS://WWW.EXAMPLE.ORG/Harris-County/MUD-558/"),
                         "https://www.example.org/Harris-County/MUD-558/")
        self.assertEqual(counties.web_address("www.example.org"), "")

    def test_a_row_says_what_the_page_shows(self):
        row = counties._row({"type": "special", "name": "Fire District No 1", "city": "Dover",
                             "web": "https://example.org", "function": "Local Fire Protection",
                             "inactive": True})
        self.assertEqual(row, ["special", "Fire District No 1", "Dover", "https://example.org", "",
                               "Local Fire Protection", "inactive"])


if __name__ == "__main__":
    unittest.main()
