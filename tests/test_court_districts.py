"""Which federal court covers each county (FEDERAL-08), and how to reach
each court (LINKS-13, FEDERAL-21, FEDERAL-24): kyc/court_districts.py,
kyc/court_info.py.

The statute fixture is 28 U.S.C. 81, 81A, 113 and 116 as govinfo's 2024
edition prints them; the counties are the Census boundaries the county
pages draw (legislative_maps/)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import court_districts as cd, court_info, federal_courts  # noqa: E402

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")


def statute():
    path = os.path.join(HERE, "fixtures", "courts", "usc28_chapter5_excerpt.html")
    with open(path, encoding="utf-8") as handle:
        return cd.sections(cd.statute_text(handle.read()))


class TestTheStatute(unittest.TestCase):
    def setUp(self):
        self.sections = statute()

    def test_a_lettered_section_is_read(self):
        # Alaska is section 81A; the first read missed it, and every
        # Alaskan borough with it.
        self.assertIn("Alaska", self.sections)
        self.assertTrue(cd.parse_state(self.sections["Alaska"][1])["single"])

    def test_a_section_added_since_1948_ends_at_its_source_credit(self):
        # "(Added Pub. L. 85-508 ...)" and the notes after it ran into where
        # court is held in Alaska and North Dakota, and were shown.
        alaska = cd.parse_state(self.sections["Alaska"][1])
        self.assertEqual(alaska["districts"][0]["held"],
                         "Anchorage, Fairbanks, Juneau, Ketchikan, and Nome")

    def test_divisions_are_read_in_order_with_where_court_sits(self):
        alabama = cd.parse_state(self.sections["Alabama"][1])
        northern = alabama["districts"][0]
        self.assertEqual(northern["name"], "Northern")
        # Pub. L. 118-179 (2024) moved Lawrence County to the Northwestern Division.
        self.assertEqual(northern["divisions"][0]["name"], "Northwestern")
        self.assertIn("Lawrence", northern["divisions"][0]["counties"])
        self.assertEqual(northern["divisions"][0]["held"], "Florence")
        # Two districts each have a Northern Division: each keeps its own place.
        middle = alabama["districts"][1]
        self.assertEqual((middle["divisions"][0]["name"], middle["divisions"][0]["held"]),
                         ("Northern", "Montgomery"))

    def test_part_of_a_county_kept_elsewhere_is_said_in_the_statutes_words(self):
        north_carolina = cd.parse_state(self.sections["North Carolina"][1])
        eastern, middle = north_carolina["districts"][:2]
        # The Eastern District's "those portions of Hoke, Moore ... counties
        # encompassing Fort Bragg" is not a list of counties.
        self.assertNotIn("Moore", eastern["counties"])
        self.assertIn("Durham", middle["counties"])
        self.assertTrue(any("Butner" in e for e in middle["exceptions"]))
        # ... and are kept apart, in the statute's words, to say where the
        # excepted part is.
        self.assertTrue(any("Durham" in p and "Butner" in p for p in eastern["portions"]))
        self.assertEqual(middle["portions"], [])

    def test_a_missing_comma_in_the_code_is_an_evidenced_alias(self):
        oklahoma = cd.parse_state(self.sections["Oklahoma"][1])
        eastern = oklahoma["districts"][1]
        self.assertIn("Le Flore Love", eastern["counties"])
        self.assertEqual(cd._wanted("OK", "Le Flore Love"), ["leflore", "love"])


class TestTheJoin(unittest.TestCase):
    PARSED = {"single": False, "section": 999, "districts": [
        {"name": "Northern", "counties": ["Alpha", "Saint Clair"], "cities": [], "exceptions": [],
         "held": "Here", "divisions": []},
        {"name": "Southern", "counties": ["Beta", "Nowhere"], "cities": [], "exceptions": [],
         "held": "There", "divisions": []}]}

    def test_every_county_is_placed_once_or_the_join_says_so(self):
        counties = {"01001": "Alpha County", "01003": "St. Clair County", "01005": "Beta County",
                    "01007": "Gamma County"}
        placed, problems = cd.join("AL", self.PARSED, counties)
        self.assertEqual(placed["01003"]["court"], "al-n")       # "Saint" is "St."
        self.assertEqual(placed["01005"]["court"], "al-s")
        self.assertTrue(any("'Nowhere'" in p for p in problems))
        self.assertTrue(any("Gamma County" in p for p in problems))
        self.assertNotIn("01007", placed)

    def test_a_city_is_placed_by_its_neighbours_only_when_they_agree(self):
        counties = {"51001": "Alpha County", "51003": "Beta County", "51510": "One city",
                    "51520": "Two city"}
        near = {"51510": {"51001"}, "51520": {"51001", "51003"}}
        parsed = dict(self.PARSED, districts=[dict(d) for d in self.PARSED["districts"]])
        parsed["districts"][1] = dict(parsed["districts"][1], counties=["Beta"])
        placed, problems = cd.join("VA", parsed, counties, near)
        self.assertEqual(placed["51510"]["court"], "va-n")
        self.assertNotIn("51520", placed)       # borders both: reported, never guessed
        self.assertTrue(any("Two city" in p for p in problems))


class TestTheCommittedTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.placed, cls.problems = cd.table(cd.load_cache(ROOT), ROOT)

    def test_every_county_in_every_state_is_placed(self):
        self.assertEqual(self.problems, [])
        expected = sum(len(cd.census_counties(code.upper()[:2], ROOT))
                       for code in (f[:2] for f in os.listdir(os.path.join(ROOT, "legislative_maps"))
                                    if f.endswith(".json")))
        self.assertEqual(len(self.placed), expected)

    def test_every_court_named_is_a_court_of_that_state(self):
        for fips, entry in self.placed.items():
            court = federal_courts.COURTS[entry["court"]]
            self.assertIn(entry["state"], court["states"], fips)

    def test_known_places(self):
        # Harris County is the Southern District's Houston Division, held
        # at College Station too since Pub. L. 119-109 (2026).
        self.assertEqual((self.placed["48201"]["court"], self.placed["48201"]["division"]),
                         ("tx-s", "Houston"))
        self.assertIn("College Station", self.placed["48201"]["held"])
        self.assertEqual(self.placed["37063"]["court"], "nc-m")          # Durham, in part
        self.assertIn("Butner", self.placed["37063"]["except"])
        self.assertEqual(self.placed["51650"]["court"], "va-e")          # Hampton (Elizabeth City)
        self.assertEqual(self.placed["51680"]["court"], "va-w")          # Lynchburg, by its neighbours
        self.assertEqual(self.placed["40079"]["court"], "ok-e")          # Le Flore
        self.assertEqual(self.placed["46102"]["court"], "sd")            # Oglala Lakota (Shannon)
        self.assertEqual(self.placed["12086"]["court"], "fl-s")          # Miami-Dade ("Dade")

    def test_where_court_is_held_is_the_statutes_sentence_only(self):
        cache = cd.load_cache(ROOT)
        for code, parsed in cache["states"].items():
            for district in parsed["districts"]:
                for unit in [district] + district["divisions"]:
                    held = unit.get("held") or ""
                    self.assertNotRegex(held, r"Pub\. L\.|Stat\.|Notes|Amendment", (code, unit["name"]))
                    self.assertLess(len(held), 200, (code, unit["name"]))

    def test_the_county_pages_file_answers_for_every_county(self):
        # FEDERAL-08: data/courtcounties.js, the one small file the county
        # pages load. A state of one district with no divisions says it once.
        payload = cd.county_courts(ROOT)
        tx = payload["TX"]
        self.assertEqual(tx["counties"]["48201"], ["tx-s", "Houston"])
        self.assertEqual(tx["names"]["tx-s"], "Southern District of Texas")
        self.assertEqual(payload["KS"], {"names": {"ks": "District of Kansas"}, "all": ["ks"]})
        self.assertIn("Butner", payload["NC"]["counties"]["37063"][2])
        for code, entry in payload.items():
            rows = [entry["all"]] if "all" in entry else list(entry["counties"].values())
            self.assertTrue(all(row[0] in entry["names"] for row in rows), code)
            if "counties" in entry:
                self.assertEqual(set(entry["counties"]),
                                 {f for f, e in self.placed.items() if e["state"] == code}, code)

    def test_the_district_holding_an_excepted_part_is_named(self):
        # Durham's Butner part and four counties' Fort Bragg parts are in the
        # Eastern District, which the statute's own words say; the county
        # page names it (it said only "another district").
        for fips in ("37063", "37093", "37125", "37153", "37165"):
            self.assertEqual(self.placed[fips]["exceptTo"], "nc-e", fips)
        nc = cd.county_courts(ROOT)["NC"]
        self.assertEqual(nc["counties"]["37063"][3], "nc-e")
        self.assertEqual(nc["names"]["nc-e"], "Eastern District of North Carolina")
        self.assertFalse([f for f, e in self.placed.items() if e.get("exceptTo") and not e.get("except")])

    def test_a_city_placed_by_its_neighbours_says_so(self):
        va = cd.county_courts(ROOT)["VA"]["counties"]
        self.assertEqual(va["51680"][-1], "neighbours")           # Lynchburg
        self.assertNotEqual(va["51650"][-1], "neighbours")        # Hampton: Elizabeth City, by name

    def test_a_courts_areas_in_its_states_words(self):
        # Rule 75: "13 counties" for Louisiana's parishes, "30 counties" for
        # Alaska's boroughs and census areas.
        covers = cd.covers(self.placed)
        self.assertRegex(covers["la-e"], r"^\d+ parishes$")
        self.assertRegex(covers["ak"], r"^\d+ boroughs and census areas$")
        self.assertRegex(covers["va-e"], r"^\d+ counties and \d+ independent cities$")
        self.assertRegex(covers["mo-e"], r"^\d+ counties and 1 independent city$")
        self.assertRegex(covers["ct"], r"^\d+ planning regions$")
        for cid, text in covers.items():
            total = sum(int(n) for n in __import__("re").findall(r"\d+", text))
            self.assertEqual(total, sum(1 for e in self.placed.values() if e["court"] == cid), cid)
        names = [n for u in cd.for_courts(self.placed)["va-e"] for n in u["counties"]]
        self.assertIn("City of Alexandria", names)
        self.assertNotIn("Alexandria city", names)

    def test_a_courts_divisions_hold_its_counties(self):
        courts = cd.for_courts(self.placed)
        self.assertEqual(sum(len(u["counties"]) for u in courts["tx-s"]),
                         sum(1 for e in self.placed.values() if e["court"] == "tx-s"))
        self.assertTrue(all(u["division"] for u in courts["tx-s"]))


class TestTheCourtsOwnSites(unittest.TestCase):
    def test_every_court_has_one_on_the_judiciarys_own_host(self):
        self.assertEqual(court_info.check(), [])
        self.assertEqual(court_info.SITES["ca-n"], "https://www.cand.uscourts.gov")  # not "ca-n"

    def test_a_lapsed_or_foreign_host_is_refused(self):
        kept = court_info.SITES["ak"]
        try:
            court_info.SITES["ak"] = "https://akd-uscourts.example.com"
            self.assertTrue(court_info.check())
            # And every build says so, not only this test.
            from kyc import validate
            self.assertIn("court-sites", [i.code for i in validate.check_judiciary(None)])
        finally:
            court_info.SITES["ak"] = kept

    def test_the_article_i_courts_are_named(self):
        names = [c["name"] for c in court_info.OTHER_COURTS]
        self.assertEqual(len(names), 4)
        self.assertIn("U.S. Court of Appeals for Veterans Claims", names)
        self.assertIn("U.S. Court of Appeals for the Armed Forces", names)


if __name__ == "__main__":
    unittest.main()
