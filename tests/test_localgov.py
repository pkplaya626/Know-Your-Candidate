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



class TestCities(unittest.TestCase):
    """A place is joined to its government by name only where the join is
    one to one; anything else is reported and left unjoined (rule 51)."""

    def test_names_reduce_alike_on_both_sides(self):
        same = [("CITY OF JERSEY CITY", "Jersey City"), ("CITY OF THE COLONY", "The Colony"),
                ("TOWN OF CITY OF CREEDE", "City of Creede"), ("CITY OF ST. GEORGE", "St. George"),
                ("CITY OF SAINT PAUL", "St. Paul"),
                ("CITY OF EL PASO DE ROBLES", "El Paso de Robles (Paso Robles)"),
                ("CITY OF LA CANADA FLINTRIDGE", "La Cañada Flintridge")]
        for listed, drawn in same:
            self.assertEqual(counties.city_key(listed), counties.city_key(drawn), (listed, drawn))
        # Forms after the name count only in the looser pass.
        self.assertNotEqual(counties.city_key("CITY OF PHENIX"), counties.city_key("Phenix City"))
        self.assertEqual(counties.city_key("CITY OF PHENIX", True), counties.city_key("Phenix City", True))
        self.assertEqual(counties.city_key("UNIFIED GOVERNMENT OF ATHENS-CLARKE COUNTY", True),
                         counties.city_key("Athens-Clarke County unified government", True))

    def test_a_join_is_one_to_one_or_not_made(self):
        places = [("p1", "springfield", "c1"), ("p2", "springfield", "c2"),
                  ("p3", "salem", "c1"), ("p4", "salem", "c1"), ("p5", "dover", "c3")]
        governments = [("g1", "springfield", "c1"), ("g2", "springfield", "c2"),
                       ("g3", "salem", "c1"), ("g5", "dover", "c9")]
        joined = counties.match_cities(places, governments)
        # A shared name is told apart by the county the point lies in; a
        # name and a county shared by two places is not told apart at all;
        # a name one place and one government share is joined wherever its
        # government is filed.
        self.assertEqual(joined, {"p1": "g1", "p2": "g2", "p5": "g5"})

    def test_two_governments_of_one_name_in_one_county_join_neither(self):
        joined = counties.match_cities([("p1", "pewaukee", "55133")],
                                       [("g1", "pewaukee", "55133"), ("g2", "pewaukee", "55133")])
        self.assertEqual(joined, {})

    def test_the_legal_form_tells_a_city_from_a_village_of_one_name(self):
        self.assertEqual(counties.listing_form("CITY OF PEWAUKEE"), "city")
        self.assertEqual(counties.listing_form("VILLAGE OF PEWAUKEE"), "village")
        self.assertEqual(counties.listing_form("METRO TOWNSHIP OF KEARNS"), "")
        page = counties.build_state("WI", ROOT, {})
        listing = localgov.load("WI", ROOT)
        pewaukee = {c[2]: listing["counties"][c[5][0]]["governments"][c[5][1]]["census"]
                    for c in page["cities"].values() if c[3] == "Pewaukee" and c[5]}
        self.assertEqual(pewaukee, {"city": "CITY OF PEWAUKEE", "village": "VILLAGE OF PEWAUKEE"})

    def test_every_join_in_every_state_names_a_municipal_government_once(self):
        from kyc.government_maps import STATES
        problems = []
        maps = counties.build(ROOT, problems=problems)
        self.assertEqual(sorted(maps), sorted(STATES))
        for code, page in maps.items():
            refs = [tuple(c[5]) for c in page["cities"].values() if c[5]]
            self.assertEqual(len(refs), len(set(refs)), code)
            listing = localgov.load(code, ROOT)
            for fips, i in refs:
                self.assertEqual(listing["counties"][fips]["governments"][i]["type"], "municipal",
                                 (code, fips, i))
            width, height = page["viewBox"][2], page["viewBox"][3]
            for pid, (x, y, kind, name, county, ref) in page["cities"].items():
                self.assertTrue(0 <= x <= width and 0 <= y <= height, (code, name))
                self.assertTrue(not county or county in page["counties"], (code, name))
            # Every place left unjoined is in what the build reports.
            unjoined = [c[3] for c in page["cities"].values() if not c[5]]
            if unjoined:
                report = " ".join(p for p in problems if p.startswith(f"{code}: "))
                for name in unjoined[:12]:
                    self.assertIn(name, report, code)
        self.assertNotIn("problems", maps["TX"])

    def test_hawaii_has_counties_and_no_incorporated_place(self):
        page = counties.build_state("HI", ROOT, {})
        self.assertEqual(page["cities"], {})
        self.assertTrue(page["counties"])

    def test_a_consolidated_remainder_keeps_its_own_name(self):
        import json
        with open(os.path.join(ROOT, counties.CITIES_DIR, "ct.json"), encoding="utf-8") as handle:
            places = {p["id"]: p for p in json.load(handle)["places"]}
        self.assertEqual((places["0947515"]["name"], places["0947515"]["kind"]), ("Milford city", "balance"))

    def test_the_place_file_names_its_legal_forms_from_the_census(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fetch_local_maps as F
        self.assertEqual(F.legal_form({"GEOID": "1", "NAME": "Abbott", "NAMELSAD": "Abbott city"}),
                         ("Abbott", "city"))
        self.assertEqual(F.legal_form({"GEOID": "2", "NAME": "Milford city (balance)",
                                       "NAMELSAD": "Milford city (balance)"}), ("Milford city", "balance"))
        self.assertEqual(F.legal_form({"GEOID": "3", "NAME": "Macon-Bibb County",
                                       "NAMELSAD": "Macon-Bibb County"}), ("Macon-Bibb County", ""))
        with self.assertRaises(SystemExit):
            F.legal_form({"GEOID": "4", "NAME": "Abbott", "NAMELSAD": "City of Abbott"})
        # The point is inside the largest piece, not an outlying island.
        main = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)]
        island = [(1.0, 1.0), (1.001, 1.0), (1.001, 1.001), (1.0, 1.001)]
        lon, lat = F.point_of([island, main])
        self.assertTrue(0 < lon < 0.1 and 0 < lat < 0.1, (lon, lat))

if __name__ == "__main__":
    unittest.main()
