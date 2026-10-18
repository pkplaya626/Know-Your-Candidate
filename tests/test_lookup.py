"""Tests for "Find who represents me": the vendored lookup files
(tools/fetch_lookup_maps.py), the per-state files built from them
(kyc/lookup.py) and their index (rule 85).

A ZIP code answered with the wrong district names the wrong person and looks
entirely normal, so what a ZIP code says is checked against the Census
Bureau's own relationship files, and the threshold that lets a ZIP code name
one district outright is pinned on both sides of the page.
"""

import io
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from kyc import districts, emit, lookup  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def square(x0, y0, size):
    return [[(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]]


class TestMeasuredShares(unittest.TestCase):
    """The scanline overlay that measures a ZIP area's share of a 2026
    district, where no relationship file exists."""

    def setUp(self):
        import fetch_lookup_maps as F
        self.F = F

    def test_a_zip_area_split_down_the_middle_is_half_in_each(self):
        zctas = {"00001": square(0, 0, 2)}
        targets = {1: [[(-5, -5), (1, -5), (1, 5), (-5, 5)]],
                   2: [[(1, -5), (7, -5), (7, 5), (1, 5)]]}
        shares = self.F.overlap_shares(zctas, targets, step=0.01)
        self.assertAlmostEqual(shares["00001"][1], 0.5, places=2)
        self.assertAlmostEqual(shares["00001"][2], 0.5, places=2)

    def test_a_share_is_of_the_whole_zip_area_even_where_part_is_outside(self):
        # A ZIP area crossing a state line: the part outside the state's
        # districts is in none of them, and the shares say so.
        zctas = {"00002": square(0, 0, 2)}
        targets = {1: [[(1, -5), (7, -5), (7, 5), (1, 5)]]}
        shares = self.F.overlap_shares(zctas, targets, step=0.01)
        self.assertAlmostEqual(shares["00002"][1], 0.5, places=2)
        self.assertEqual(set(shares["00002"]), {1})

    def test_a_hole_is_not_part_of_the_district(self):
        zctas = {"00003": square(0, 0, 4)}
        donut = [[(-1, -1), (5, -1), (5, 5), (-1, 5)], [(1, 1), (3, 1), (3, 3), (1, 3)]]
        shares = self.F.overlap_shares(zctas, {1: donut}, step=0.01)
        self.assertAlmostEqual(shares["00003"][1], 0.75, places=2)

    def test_agreement_reports_the_largest_difference_and_the_whole_calls(self):
        exact = {"1": {1: 1.0}, "2": {1: 0.5, 2: 0.5}}
        measured = {"1": {1: 0.995}, "2": {1: 0.52, 2: 0.48}}
        found = self.F.agreement(measured, exact)
        self.assertEqual(found["zips"], 2)
        self.assertAlmostEqual(found["meanDiff"], (0.005 + 0.02) / 2, places=4)
        self.assertEqual(found["sameWhole"], 1.0)


class TestRelationshipFiles(unittest.TestCase):
    HEAD = ("OID_CD119_20|GEOID_CD119_20|NAMELSAD_CD119_20|AREALAND_CD119_20|AREAWATER_CD119_20|"
            "MTFCC_CD119_20|FUNCSTAT_CD119_20|OID_ZCTA5_20|GEOID_ZCTA5_20|NAMELSAD_ZCTA5_20|"
            "AREALAND_ZCTA5_20|AREAWATER_ZCTA5_20|MTFCC_ZCTA5_20|CLASSFP_ZCTA5_20|FUNCSTAT_ZCTA5_20|"
            "AREALAND_PART|AREAWATER_PART")

    def rows(self, *rows):
        return (self.HEAD + "\n" + "\n".join(rows) + "\n").encode("utf-8")

    def test_a_share_is_land_over_land_and_rows_without_a_zip_area_are_skipped(self):
        import fetch_lookup_maps as F
        body = self.rows(
            "1|3901|D1|0|0|G5200|N|||||||||500|0",                        # no ZCTA
            "1|3912|D12|0|0|G5200|N|9|45701|Z|1000|50|G6350|B5|S|900|50",
            "1|3902|D2|0|0|G5200|N|9|45701|Z|1000|50|G6350|B5|S|100|0",
            "1|39ZZ|water|0|0|G5200|N|9|45701|Z|1000|50|G6350|B5|S|0|0",  # water, no district
            "1|3903|D3|0|0|G5200|N|9|43999|Z|0|80|G6350|B5|S|0|80")      # all water
        with mock.patch.object(F.maps, "get", return_value=body):
            found = F.relationship("x", "CD119_20")
        self.assertEqual(found["OH"]["45701"], {"3912": 0.9, "3902": 0.1})
        self.assertEqual(found["OH"]["43999"], {"3903": 1.0})


class TestArchivesAreArchives(unittest.TestCase):
    def test_a_download_that_is_not_a_zip_is_refused_where_a_zip_is_read(self):
        # Utah's service answered "being generated" (status 202, JSON) at a
        # URL ending in "?layers=0", and that was cached as the shapefile.
        import fetch_district_maps as F
        pending = b'{"message":"Up to date download file is being generated.","status":"Pending"}'
        url = "https://example.test/items/x/shapefile?layers=0"
        self.assertTrue(F._whole(url, pending))
        self.assertFalse(F._whole(url, pending, archive=True))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.txt", "x")
        self.assertTrue(F._whole(url, buf.getvalue(), archive=True))


def topo(objects, zips, arcs=None):
    return {"type": "Topology", "transform": {"scale": [1e-5, 1e-5], "translate": [0, 0]},
            "arcs": arcs or [[[0, 0], [100, 0], [0, 100], [-100, 0], [0, -100]]],
            "objects": {k: {"type": "GeometryCollection", "geometries": v}
                        for k, v in objects.items()},
            "zips": zips, "sources": {"current": "c", "counties": "k", "zips": "z"}}


class TestBuildState(unittest.TestCase):
    """kyc/lookup.build_state refuses a lookup file that disagrees with the
    maps the pages draw."""

    def write(self, code, payload):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, lookup.LOOKUP_DIR))
        with open(lookup.source_file(code, root), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return root

    def base(self, zips=None, current=(1, 2)):
        geoms = [{"type": "Polygon", "arcs": [[0]], "properties": {"d": n}} for n in current]
        county = [{"type": "Polygon", "arcs": [[0]], "properties": {"id": "39009", "name": "Athens County"}}]
        return topo({"current": geoms, "counties": county},
                    zips if zips is not None else {"45701": {"cd": [[1, 1.0]], "co": [["39009", 1.0]]}})

    def test_a_good_file_builds_with_only_the_arcs_it_draws(self):
        root = self.write("IA", self.base())
        payload = lookup.build_state("IA", root, seats=[[1, 2], []])
        self.assertEqual(sorted(payload["cd"]), ["1", "2"])
        self.assertEqual(len(payload["arcs"]), 1)
        self.assertEqual(payload["arcs"][0][:2], [0, 0])
        self.assertEqual(payload["box"], [0.0, 0.0, 0.001, 0.001])
        self.assertEqual(payload["zips"]["45701"]["cd"], [[1, 1.0]])

    def test_a_zip_naming_a_district_the_map_does_not_draw_is_refused(self):
        root = self.write("IA", self.base({"45701": {"cd": [[7, 1.0]]}}))
        with self.assertRaisesRegex(lookup.LookupMapError, "not on the map"):
            lookup.build_state("IA", root, seats=[[1, 2], []])

    def test_districts_other_than_the_pages_are_refused(self):
        root = self.write("IA", self.base())
        with self.assertRaisesRegex(lookup.LookupMapError, "district page"):
            lookup.build_state("IA", root, seats=[[1, 2, 3], []])

    def test_a_2026_map_only_where_districts_says_one_was_drawn(self):
        payload = self.base()
        payload["objects"]["next"] = payload["objects"]["current"]
        with self.assertRaisesRegex(lookup.LookupMapError, "REDRAWN"):
            lookup.build_state("IA", self.write("IA", payload))

    def test_shares_adding_to_more_than_the_whole_are_refused(self):
        root = self.write("IA", self.base({"45701": {"cd": [[1, 0.8], [2, 0.5]]}}))
        with self.assertRaisesRegex(lookup.LookupMapError, "more than the whole"):
            lookup.build_state("IA", root)

    def test_counties_must_be_the_county_pages_and_take_their_words(self):
        root = self.write("IA", self.base())
        local = {"counties": {"39009": {"name": "Athens County"}},
                 "areaWords": {"one": "parish"}, "noCounty": {"39009": {"short": "x"}}}
        payload = lookup.build_state("IA", root, local=local)
        self.assertEqual(payload["area"], "parish")
        self.assertEqual(payload["noCounty"], {"39009": "x"})
        self.assertTrue(payload["countyPages"])
        with self.assertRaisesRegex(lookup.LookupMapError, "county page"):
            lookup.build_state("IA", root, local={"counties": {"39011": {"name": "x"}}})

    def test_state_districts_must_be_the_legislature_pages(self):
        root = self.write("IA", self.base({"45701": {"cd": [[1, 1.0]], "su": [["030", 1.0]]}}))
        legislature = {"chambers": {"upper": {"districts": {"029": {}}}}}
        with self.assertRaisesRegex(lookup.LookupMapError, "not on the map"):
            lookup.build_state("IA", root, legislature=legislature)
        # Without the legislature at hand (build --check) they are not judged.
        lookup.build_state("IA", root)

    def test_a_state_elected_at_large_ships_its_counties_not_its_outline_twice(self):
        root = self.write("WY", self.base({"82001": {"cd": [[0, 1.0]]}}, current=(0,)))
        payload = lookup.build_state("WY", root, seats=[[0], []])
        self.assertTrue(payload["atLarge"])
        self.assertNotIn("cd", payload)
        self.assertIn("co", payload)


class TestIndex(unittest.TestCase):
    def test_a_zip_prefix_reaches_every_state_its_areas_are_in(self):
        payloads = {"NY": {"zips": {"06390": {}}, "box": [0, 0, 1, 1]},
                    "CT": {"zips": {"06390": {}, "06101": {}}, "box": [1, 1, 2, 2]}}
        index = lookup.index(payloads, {"NY": {"lookup": "a"}, "CT": {"lookup": "b"}})
        self.assertEqual(index["zip3"]["063"], ["CT", "NY"])
        self.assertEqual(index["zip3"]["061"], ["CT"])
        self.assertEqual(index["whole"], lookup.WHOLE)

    def test_the_page_holds_the_same_threshold(self):
        with open(os.path.join(ROOT, emit.SITE_DIR, "assets", "kyc-findrep.js"),
                  encoding="utf-8") as handle:
            found = re.search(r"var WHOLE = ([0-9.]+);", handle.read())
        self.assertEqual(float(found.group(1)), lookup.WHOLE)
        self.assertEqual(lookup.WHOLE, 0.99)

    def test_written_files_check_and_the_index_stamps_them(self):
        root = tempfile.mkdtemp()
        payloads = {"IA": {"zips": {"50010": {"cd": [[4, 1.0]]}}, "box": [0, 0, 1, 1]}}
        emit.write_lookup(payloads, root)
        self.assertEqual(emit.write_lookup(payloads, root), [])          # unchanged
        stamps = emit.lookup_stamps(payloads, root)
        sig = emit.read_signature(path=emit.lookup_file("IA", root))
        self.assertEqual(stamps["IA"]["lookup"], f"data/lookup/ia.js?v={sig[:10]}")
        self.assertNotIn("legislature", stamps["IA"])
        self.assertTrue(emit.check_lookup(payloads, root))               # no index yet
        emit.write_lookup_index(lookup.index(payloads, stamps), root)
        self.assertEqual(emit.check_lookup(payloads, root), [])
        payloads["IA"]["zips"]["50010"]["cd"] = [[3, 1.0]]
        self.assertEqual(emit.check_lookup(payloads, root)[0][1], "stale")
        with open(emit.lookup_file("IA", root), encoding="utf-8") as handle:
            text = handle.read()
        # Two states on one page: each adds itself, neither replaces the other.
        self.assertIn("window.kycLookup = window.kycLookup || {};", text)
        self.assertIn('window.kycLookup["IA"] = ', text)


class TestVendoredLookup(unittest.TestCase):
    """The committed lookup_maps/: every state builds against the maps, and
    what it says is what the Census Bureau's files say."""

    @classmethod
    def setUpClass(cls):
        cls.maps = districts.build(ROOT)
        cls.payloads = lookup.build(ROOT, district_maps=cls.maps)

    def source(self, code):
        with open(lookup.source_file(code, ROOT), encoding="utf-8") as handle:
            return json.load(handle)

    def test_every_state_and_territory_has_a_lookup(self):
        self.assertEqual(set(self.payloads), set(districts.all_codes()))

    def test_every_zip_area_names_its_districts_and_their_shares_fit(self):
        for code, payload in self.payloads.items():
            for zcta, entry in payload["zips"].items():
                self.assertIn("cd", entry, (code, zcta))
                for key in ("cd", "next", "co", "su", "sl"):
                    total = sum(p[1] for p in entry.get(key, []))
                    self.assertLessEqual(total, 1.02, (code, zcta, key))

    def test_a_redrawn_state_has_both_maps_and_every_zip_both_shares(self):
        for code in districts.REDRAWN:
            payload = self.payloads[code]
            self.assertIn("next", payload)
            missing = [z for z, e in payload["zips"].items() if "next" not in e]
            self.assertEqual(missing, [], code)

    def test_measured_shares_are_checked_against_the_exact_ones(self):
        # The 2026 shares are measured; the same measurement of the 119th
        # map agrees with the Census relationship file, and is on record.
        for code in districts.REDRAWN:
            check = self.source(code)["checks"]["measured"]
            self.assertLess(check["meanDiff"], 0.005, code)
            self.assertGreaterEqual(check["sameWhole"], 0.99, code)

    def test_athens_ohio_is_in_oh_12_and_votes_in_oh_2(self):
        # PERSONA-01's reader: Athens County is OH-12 under the 2022 lines and
        # OH-2 under the commission's 2025 map.
        entry = self.payloads["OH"]["zips"]["45701"]
        self.assertEqual(entry["cd"], [[12, 1.0]])
        self.assertEqual(entry["next"][0][0], 2)
        self.assertGreaterEqual(entry["next"][0][1], lookup.WHOLE)

    def test_connecticut_answers_with_its_planning_regions(self):
        counties = {c for e in self.payloads["CT"]["zips"].values() for c, _ in e.get("co", [])}
        self.assertTrue(counties)
        self.assertTrue(all(c.startswith("091") for c in counties), sorted(counties)[:5])

    def test_the_legislature_files_carry_their_projection(self):
        path = os.path.join(ROOT, emit.LEGISLATURE_DIR, "oh.js")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertRegex(text, r'"projection":\{"parallels":\[')


if __name__ == "__main__":
    unittest.main()
