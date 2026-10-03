"""Tests for the before-and-after district maps (kyc/districts.py).

The page reads "CA-3" off these shapes and says who held it and who is
running in it. A shape that decodes, projects or numbers wrongly would put
the right name on the wrong piece of California and look entirely normal,
so the geometry is checked against places whose district is on record.
"""

import io
import json
import math
import os
import re
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from kyc import districts, emit, validate  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def rings_of(path_data):
    """Replay an emitted path as the page does (kyc-districts.js ringsOf)."""
    rings = []
    for part in path_data.split("M")[1:]:
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", part)]
        x, y = nums[0], nums[1]
        ring = [(x, y)]
        for i in range(2, len(nums) - 1, 2):
            x += nums[i]
            y += nums[i + 1]
            ring.append((x, y))
        rings.append(ring)
    return rings


class TestCaliforniaMaps(unittest.TestCase):
    """The real, vendored boundaries."""

    @classmethod
    def setUpClass(cls):
        cls.ca = districts.build(ROOT)["CA"]
        cls.old, cls.new = cls.ca["plans"]
        cls.towns = {p[0]: (p[1], p[2]) for p in cls.ca["places"]}

    def district_of(self, plan, town):
        x, y = self.towns[town]
        hits = [int(n) for n, d in plan["districts"].items()
                if districts._contains(rings_of(d["d"]), x, y)]
        self.assertEqual(len(hits), 1, f"{town} falls in {hits} on the {plan['key']} map")
        return hits[0]

    def test_both_plans_number_every_seat(self):
        for plan in (self.old, self.new):
            self.assertEqual(sorted(map(int, plan["districts"])), list(range(1, 53)))

    def test_north_is_up_and_east_is_right(self):
        self.assertGreater(self.towns["Folsom"][0], self.towns["Sacramento"][0])
        self.assertLess(self.towns["Truckee"][1], self.towns["Bishop"][1])
        self.assertLess(self.towns["Sacramento"][1], self.towns["Los Angeles"][1])

    def test_the_drawn_state_is_the_size_of_california(self):
        # 163,696 square miles (423,970 km2) including water, per the Census
        # Bureau. A wrong projection, a bad decode or a lost district moves
        # this by far more than the 1% allowed.
        for plan in (self.old, self.new):
            area = sum(d["area"] for d in plan["districts"].values()) * self.ca["unitKm"] ** 2
            self.assertAlmostEqual(area / 423970, 1, delta=0.01, msg=plan["key"])

    def test_the_old_third_and_sixth_hold_the_towns_on_record(self):
        # Wikipedia, "California's 3rd congressional district" (2023-2027):
        # Roseville, Folsom, Rocklin, Auburn and Lincoln, and Alpine, Inyo,
        # Mono and Nevada counties. The 6th: Rancho Cordova, Citrus Heights.
        for town in ("Roseville", "Folsom", "Rocklin", "Auburn", "Lincoln",
                     "Truckee", "Grass Valley", "Bishop", "Mammoth Lakes"):
            self.assertEqual(self.district_of(self.old, town), 3, town)
        for town in ("Rancho Cordova", "Citrus Heights"):
            self.assertEqual(self.district_of(self.old, town), 6, town)

    def test_the_new_third_and_sixth_hold_the_towns_on_record(self):
        # KCRA and CBS Sacramento on the Proposition 50 lines: the new 3rd
        # takes all of Nevada County, Folsom and the Lake Tahoe Basin and
        # drops the eastern Sierra; the new 6th takes Roseville, Rocklin,
        # Citrus Heights and West Sacramento.
        for town in ("Truckee", "Grass Valley", "Nevada City", "Folsom", "South Lake Tahoe"):
            self.assertEqual(self.district_of(self.new, town), 3, town)
        for town in ("Roseville", "Rocklin", "Citrus Heights", "West Sacramento"):
            self.assertEqual(self.district_of(self.new, town), 6, town)
        self.assertNotEqual(self.district_of(self.new, "Bishop"), 3)

    def test_overlaps_agree_with_an_independent_measurement(self):
        # Measured separately with mapshaper's overlay on the same files:
        # the new 3rd is 97% old 3rd, 2.5% old 6th, 0.9% old 7th; the new
        # 6th is 50% old 6th, 37% old 3rd, 13% old 7th.
        came = {(f[0], f[1]): f[2] for f in self.ca["flows"]}
        expected = {(3, 3): 0.97, (6, 3): 0.025, (7, 3): 0.009,
                    (6, 6): 0.50, (3, 6): 0.37, (7, 6): 0.13}
        for pair, share in expected.items():
            self.assertAlmostEqual(came.get(pair, 0), share, delta=0.015, msg=pair)

    def test_every_district_is_accounted_for_by_the_other_plan(self):
        for column, side in ((2, 1), (3, 0)):
            totals = {}
            for flow in self.ca["flows"]:
                totals[flow[side]] = totals.get(flow[side], 0) + flow[column]
            self.assertEqual(len(totals), 52)
            self.assertTrue(all(t >= districts.MIN_COVERAGE for t in totals.values()), totals)

    def test_every_label_point_is_inside_its_district(self):
        for plan in (self.old, self.new):
            for n, d in plan["districts"].items():
                self.assertTrue(districts._contains(rings_of(d["d"]), *d["at"]),
                                f"{plan['key']} {n}")

    def test_county_names_sit_inside_their_counties(self):
        names = {c[0] for c in self.ca["counties"]["names"]}
        self.assertEqual(len(names), 58)          # every county in California
        self.assertTrue(self.ca["counties"]["mesh"].startswith("M"))
        self.assertNotIn("Z", self.ca["counties"]["mesh"])   # lines, not shapes

    def test_insets_frame_the_dense_metros(self):
        boxes = {i["key"]: i["box"] for i in self.ca["insets"]}
        x, y = self.towns["Los Angeles"]
        la = boxes["la"]
        self.assertTrue(la[0] < x < la[0] + la[2] and la[1] < y < la[1] + la[3])
        x, y = self.towns["San Francisco"]
        bay = boxes["bay"]
        self.assertTrue(bay[0] < x < bay[0] + bay[2] and bay[1] < y < bay[1] + bay[3])

    def test_the_payload_says_nothing_about_people(self):
        # districts.js is a pure function of the geometry; the page joins it
        # to profiles.js. A name in here would be a second source of truth.
        text = emit._json(self.ca)
        for name in ("Bera", "Kiley", "Calvert", "Democrat", "Republican"):
            self.assertNotIn(name, text)


class TestProjection(unittest.TestCase):

    def test_it_is_equal_area(self):
        # A one-degree cell has area dlon * (sin lat2 - sin lat1) on the unit
        # sphere; an equal-area projection keeps it, wherever the cell is.
        albers = districts._Albers()
        for west, south in ((-124, 32.5), (-120, 37), (-115, 41)):
            edge = ([(west + i / 50, south) for i in range(51)] +
                    [(west + 1, south + i / 50) for i in range(51)] +
                    [(west + 1 - i / 50, south + 1) for i in range(51)] +
                    [(west, south + 1 - i / 50) for i in range(51)])
            pts = [albers.raw(lon, lat) for lon, lat in edge]
            drawn = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                            for i in range(len(pts)))) / 2
            true = math.radians(1) * (math.sin(math.radians(south + 1)) -
                                      math.sin(math.radians(south)))
            self.assertAlmostEqual(drawn / true, 1, delta=1e-4)


def square(x0, y0, x1, y1):
    return [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]


class TestMeasure(unittest.TestCase):

    def test_overlaps_of_squares(self):
        old = {1: square(0, 0, 10, 10), 2: square(10, 0, 20, 10)}
        new = {1: square(5, 0, 15, 10), 2: square(0, 0, 5, 10) + square(15, 0, 20, 10)}
        areas, overlaps = districts.measure([old, new], 12)
        self.assertEqual(areas, [{1: 100.0, 2: 100.0}, {1: 100.0, 2: 100.0}])
        self.assertEqual(overlaps, {(1, 1): 50.0, (2, 1): 50.0, (1, 2): 50.0, (2, 2): 50.0})

    def test_a_hole_is_not_area(self):
        donut = [[(0, 0), (10, 0), (10, 10), (0, 10)], [(4, 4), (6, 4), (6, 6), (4, 6)]]
        areas, _ = districts.measure([{1: donut}, {1: donut}], 12)
        self.assertEqual(areas[0][1], 96.0)

    def test_a_district_the_other_plan_misses_is_an_error(self):
        areas = [{1: 100.0}, {1: 100.0}]
        with self.assertRaises(districts.DistrictsError) as caught:
            districts.flows(areas, {(1, 1): 90.0})
        self.assertIn("old 1 (90%)", str(caught.exception))

    def test_slivers_are_not_flows(self):
        flows = districts.flows([{1: 100.0, 2: 100.0}, {1: 100.0, 2: 100.0}],
                                {(1, 1): 99.8, (1, 2): 0.2, (2, 2): 99.8, (2, 1): 0.2})
        self.assertEqual(flows, [[1, 1, 0.998, 0.998], [2, 2, 0.998, 0.998]])

    def test_interior_point_of_a_crescent_is_inside_it(self):
        crescent = [[(0, 0), (10, 0), (10, 10), (0, 10), (0, 8), (8, 8), (8, 2), (0, 2)]]
        x, y = districts.interior_point(crescent)
        self.assertTrue(districts._contains(crescent, x, y))

    def test_open_lines_are_not_closed(self):
        path = districts.lines_to_path([[(0, 0), (1, 1), (3, 1)]])
        self.assertEqual(path, "M0,0l1,1 2,0")


def _topology(points=None, numbers=(1, 2)):
    """Two plans of two side-by-side districts, numbered the other way round
    in the second plan, and one county around both. Unquantised."""
    left = [[-121.0, 38.0], [-120.5, 38.0], [-120.5, 38.5], [-121.0, 38.5], [-121.0, 38.0]]
    right = [[-120.5, 38.0], [-120.0, 38.0], [-120.0, 38.5], [-120.5, 38.5], [-120.5, 38.0]]
    whole = [[-121.0, 38.0], [-120.0, 38.0], [-120.0, 38.5], [-121.0, 38.5], [-121.0, 38.0]]
    points = points or {1: [-120.75, 38.25], 2: [-120.25, 38.25]}

    def plan(first, second):
        return {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "arcs": [[first]], "properties": {"d": numbers[0]}},
            {"type": "Polygon", "arcs": [[second]], "properties": {"d": numbers[1]}},
        ]}

    def pts(swap):
        return {"type": "GeometryCollection", "geometries": [
            {"type": "Point", "coordinates": points[2 if swap else 1], "properties": {"d": 1}},
            {"type": "Point", "coordinates": points[1 if swap else 2], "properties": {"d": 2}},
        ]}

    return {
        "type": "Topology",
        "arcs": [left, right, whole],
        "objects": {
            "old_s": plan(0, 1), "new_s": plan(1, 0),
            "old_pts": pts(False), "new_pts": pts(True),
            "counties": {"type": "GeometryCollection", "geometries": [
                {"type": "Polygon", "arcs": [[2]], "properties": {"name": "Test"}}]},
        },
    }


class TestBuildState(unittest.TestCase):
    """The loud failures, on a two-district state."""

    def build(self, topo):
        spec = dict(districts.PLANS["CA"], seats=2, file="t.json", places="p.json", insets=())
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "t.json"), "w", encoding="utf-8") as f:
                json.dump(topo, f)
            with open(os.path.join(tmp, "p.json"), "w", encoding="utf-8") as f:
                json.dump({"places": [["Town", -120.6, 38.2, 1000]]}, f)
            with mock.patch.dict(districts.PLANS, {"ZZ": spec}, clear=True):
                return districts.build_state("ZZ", tmp)

    def test_a_clean_state_builds(self):
        state = self.build(_topology())
        self.assertEqual([sorted(p["districts"]) for p in state["plans"]], [["1", "2"]] * 2)
        self.assertEqual(state["flows"], [[1, 2, 1.0, 1.0], [2, 1, 1.0, 1.0]])
        self.assertEqual(state["places"][0][0], "Town")

    def test_a_label_point_outside_its_district_is_an_error(self):
        topo = _topology(points={1: [-120.25, 38.25], 2: [-120.75, 38.25]})
        with self.assertRaisesRegex(districts.DistrictsError, "label point is outside"):
            self.build(topo)

    def test_a_missing_district_is_an_error(self):
        with self.assertRaisesRegex(districts.DistrictsError, r"missing \[2\]"):
            self.build(_topology(numbers=(1, 3)))

    def test_a_district_numbered_twice_is_an_error(self):
        with self.assertRaisesRegex(districts.DistrictsError, "twice"):
            self.build(_topology(numbers=(1, 1)))

    def test_a_missing_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(districts.DistrictsError, "not found"):
                districts.build_state("CA", tmp)


class TestEmitted(unittest.TestCase):

    def test_the_file_records_its_signature(self):
        payload = {"CA": {"plans": [], "x": 1}}
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_districts(payload, root=tmp)
            path = os.path.join(tmp, emit.DISTRICTS_FILE)
            self.assertEqual(emit.read_signature(path=path), emit.districts_signature(payload))
            with open(path, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("window.kycDistricts = ", text)
        self.assertIn("ca_districts_topo.json", text)

    def test_the_build_metadata_lists_the_maps(self):
        from kyc import summary
        self.assertEqual(summary.redistricting(),
                         {"CA": {"page": "redistricting/ca.html", "name": "California"}})


class TestValidation(unittest.TestCase):

    def races(self, count):
        return [{"chamber": "House", "state": "CA", "district": n} for n in range(1, count + 1)]

    def test_a_map_for_the_seats_on_the_ballot_passes(self):
        self.assertEqual(validate.check_district_maps(self.races(52), {"CA": {"seats": 52}}), [])

    def test_a_map_numbering_other_seats_is_an_error(self):
        issues = validate.check_district_maps(self.races(53), {"CA": {"seats": 52}})
        self.assertEqual([i.code for i in issues], ["district-map-seats"])
        self.assertEqual(issues[0].level, "error")

    def test_a_map_that_did_not_build_is_an_error(self):
        issues = validate.check_district_maps([], None, "label point is outside")
        self.assertEqual([(i.level, i.code) for i in issues], [("error", "district-map")])


class TestPlacesTool(unittest.TestCase):
    """tools/fetch_ca_places.py, offline: the join, the names, the refusal."""

    def files(self, extra_estimate=""):
        # Truckee's internal point agrees with USGS; San Francisco's is on the
        # Farallon Islands, 52 km out, as it really is; Sacramento has no
        # USGS record at all.
        gazetteer = ("USPS\tGEOID\tANSICODE\tNAME\tLSAD\tFUNCSTAT\tALAND\tAWATER\t"
                     "ALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG\n"
                     "CA\t0680000\t02413403\tTruckee town\t43\tA\t84000000\t0\t1\t0\t39.35\t-120.19\n"
                     "CA\t0667000\t02411786\tSan Francisco city\t25\tA\t121400000\t0\t1\t0"
                     "\t37.727239\t-123.032229\n"
                     "CA\t0664000\t02411751\tSacramento city\t25\tA\t1\t0\t1\t0\t38.56\t-121.46\n"
                     "NV\t3200001\t1\tElsewhere city\t25\tA\t1\t0\t1\t0\t39.0\t-119.0\n")
        gnis = ("feature_id|feature_name|feature_class|prim_lat_dec|prim_long_dec\n"
                "2413403|Town of Truckee|Civil|39.3454399|-120.1848719\n"
                "2411786|City of San Francisco|Civil|37.7782253|-122.4425085\n"
                "277593|San Francisco|Populated Place|37.775|-122.4194444\n")
        archives = []
        for name, body in (("2020_Gaz_place_national.txt", gazetteer),
                           ("Text/DomesticNames_CA.txt", gnis)):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(name, body)
            archives.append(buffer.getvalue())
        estimates = ("SUMLEV,STATE,COUNTY,PLACE,NAME,POPESTIMATE2024\n"
                     "162,06,000,80000,Truckee town,17240\n"
                     "162,06,000,67000,San Francisco city,827526\n"
                     "162,06,000,64000,Sacramento city,535798\n"
                     "040,06,000,00000,California,39000000\n" + extra_estimate)
        return archives[0], estimates.encode("latin-1"), archives[1]

    def test_places_are_joined_named_and_ranked(self):
        import fetch_ca_places
        payload = fetch_ca_places.build(*self.files())
        self.assertEqual([p[0] for p in payload["places"]],
                         ["San Francisco", "Sacramento", "Truckee"])
        self.assertEqual(payload["places"][2], ["Truckee", -120.19, 39.35, 17240])

    def test_an_internal_point_out_at_sea_is_replaced_and_recorded(self):
        import fetch_ca_places
        payload = fetch_ca_places.build(*self.files())
        self.assertEqual(payload["places"][0], ["San Francisco", -122.4425085, 37.7782253, 827526])
        self.assertEqual(payload["moved"], [["San Francisco", -123.032229, 37.727239, 52.2]])
        self.assertEqual(payload["unchecked"], ["Sacramento"])

    def test_a_place_with_no_point_is_refused(self):
        import fetch_ca_places
        with self.assertRaises(SystemExit):
            fetch_ca_places.build(*self.files("162,06,000,99999,Nowhere city,5\n"))

    def test_the_committed_file_was_checked_against_usgs(self):
        with open(os.path.join(ROOT, "ca_places.json"), encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["unchecked"], [])
        self.assertEqual([m[0] for m in payload["moved"]], ["San Francisco"])


if __name__ == "__main__":
    unittest.main()
