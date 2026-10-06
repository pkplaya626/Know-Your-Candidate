"""Tests for every state's district maps (kyc/districts.py) and the tool that
vendors them (tools/fetch_district_maps.py).

A page reads "TX-9" off these shapes and says who held it and who is running
in it. A shape that decodes, projects or numbers wrongly would put the right
name on the wrong piece of a state and look entirely normal, so the geometry
is checked against places whose district is on record.
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

from kyc import districts, emit, geo, validate  # noqa: E402

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


class TestEveryState(unittest.TestCase):
    """All 56 maps: built, numbered as the races are, and labelled."""

    @classmethod
    def setUpClass(cls):
        cls.maps = districts.build(ROOT)

    def test_every_state_and_territory_has_a_map(self):
        self.assertEqual(sorted(self.maps), districts.all_codes())
        self.assertEqual(len(self.maps), 56)

    def test_redrawn_states_have_two_maps_and_the_rest_one(self):
        for code, state in self.maps.items():
            self.assertEqual(len(state["plans"]), 2 if code in districts.REDRAWN else 1, code)

    def test_a_single_seat_is_numbered_zero_as_the_races_are(self):
        for code in ("AK", "DE", "ND", "SD", "VT", "WY", "DC", "PR", "GU", "VI", "AS", "MP"):
            state = self.maps[code]
            self.assertTrue(state["atLarge"], code)
            self.assertEqual(list(state["plans"][0]["districts"]), ["0"], code)

    def test_every_district_is_numbered_at_every_width(self):
        # Numbers were sized for a 620px map and scaled with it, so a phone
        # drew them 4px tall. They are 11px now, written where they fit, and
        # the insets are planned so that at any width from PHONE_PX up every
        # district is numbered somewhere - the page's own rule, simulated.
        widths = (districts.PHONE_PX, 302, 324, 364, 420, 500, 560, 620, 860)
        for code, state in self.maps.items():
            for plan in state["plans"]:
                for drawn in widths:
                    missing = set(plan["districts"]) - numbered(state, plan, drawn)
                    self.assertFalse(missing, f"{code} {plan['key']} at {drawn}px: "
                                              f"{sorted(missing, key=int)}")

    def test_room_is_clear_room(self):
        # The rule trusts "room": a disk that size around the label point is
        # inside the district, and for a new map inside the land it is drawn
        # clipped to. Two numbers that fit can then never overlap. (Within
        # the rounding of the emitted path, label point and room.)
        for code, state in self.maps.items():
            for plan in state["plans"]:
                for n, d in plan["districts"].items():
                    edge = geo.signed_distance(*d["at"], rings_of(d["d"]))
                    self.assertGreater(d["room"], 0, f"{code} {plan['key']} {n}")
                    self.assertLessEqual(d["room"], edge + 0.2, f"{code} {plan['key']} {n}")

    def test_no_number_sits_against_its_own_edge(self):
        # The tool moved a label point that fell at sea onto land by ranking
        # grid samples by their distance from samples off the district - with
        # no samples beyond the district's bounding box, so a point on the box
        # edge scored as roomy. FL-19 and OH-14 were numbered on their own
        # borders, 1.0 and 2.2 units from the edge; the pole of the
        # district's land puts them 15 and 95 units in. A pole is never this
        # close to an edge relative to the district's size.
        for code, state in self.maps.items():
            for plan in state["plans"]:
                for n, d in plan["districts"].items():
                    self.assertGreater(d["room"], 0.12 * math.sqrt(d["area"]),
                                       f"{code} {plan['key']} {n}")

    def test_a_closer_inset_is_planned_only_where_one_is_needed(self):
        for code, state in self.maps.items():
            for inset in districts.every_inset(state["insets"]):
                self.assertGreaterEqual(inset["width"], districts.INSET_MIN_PX)
                self.assertLessEqual(inset["width"], districts.DESIGN_PX)
                self.assertEqual("detail" in inset, inset["fits"] > districts.PHONE_PX,
                                 f"{code} {inset['title']}")
                for detail in inset.get("detail", []):
                    self.assertLess(detail["box"][2], inset["box"][2], f"{code} {inset['title']}")

    def test_no_inset_covers_a_large_part_of_its_state(self):
        # An inset grew to hold each member district's whole bounding box, so
        # one long thin district - TX-15, 335 units tall - stretched Houston's
        # until it swallowed San Antonio's: "Houston & San Antonio", half of
        # Texas. A member now brings only its label's neighbourhood.
        for code, state in self.maps.items():
            width, height = state["viewBox"][2], state["viewBox"][3]
            for inset in districts.every_inset(state["insets"]):
                self.assertLess(inset["box"][2], 0.35 * width, f"{code} {inset['title']}")
                self.assertLess(inset["box"][3], 0.35 * height, f"{code} {inset['title']}")

    def test_a_state_elected_at_large_has_no_insets(self):
        for code, state in self.maps.items():
            if state["atLarge"]:
                self.assertEqual(state["insets"], [], code)

    def test_every_label_point_is_inside_its_district(self):
        for code, state in self.maps.items():
            for plan in state["plans"]:
                for n, d in plan["districts"].items():
                    self.assertTrue(districts._contains(rings_of(d["d"]), *d["at"]),
                                    f"{code} {plan['key']} {n}")

    def test_redrawn_maps_account_for_every_old_district(self):
        for code in districts.REDRAWN:
            totals = {}
            for old, _new, _of_new, of_old in self.maps[code]["flows"]:
                totals[old] = totals.get(old, 0) + of_old
            self.assertTrue(all(t >= districts.MIN_COVERAGE for t in totals.values()), code)

    def test_the_maps_say_nothing_about_people(self):
        # The emitted files are a pure function of the geometry; the page
        # joins them to profiles.js. A name here would be a second source.
        text = emit._json(self.maps["CA"]) + emit._json(self.maps["TX"])
        for word in ("Bera", "Kiley", "Democrat", "Republican"):
            self.assertNotIn(word, text)


class TestRecordedPlaces(unittest.TestCase):
    """Places whose district is on record, so a projection or numbering
    error shows up as a town in the wrong district."""

    @classmethod
    def setUpClass(cls):
        cls.ca = districts.build(ROOT, ["CA"])["CA"]
        cls.towns = {p[0]: (p[1], p[2]) for p in cls.ca["places"]}

    def district_of(self, key, town):
        plan = next(p for p in self.ca["plans"] if p["key"] == key)
        x, y = self.towns[town]
        hits = [int(n) for n, d in plan["districts"].items()
                if districts._contains(rings_of(d["d"]), x, y)]
        self.assertEqual(len(hits), 1, f"{town} falls in {hits} on the {key} map")
        return hits[0]

    def test_north_is_up_and_east_is_right(self):
        self.assertGreater(self.towns["Folsom"][0], self.towns["Sacramento"][0])
        self.assertLess(self.towns["Truckee"][1], self.towns["Bishop"][1])

    def test_the_drawn_state_is_the_size_of_california(self):
        # The Census map stops at the coast but keeps inland water, so it
        # measures between California's land (403,466 km2) and its total
        # area (423,970 km2), per the Census Bureau.
        for plan in self.ca["plans"]:
            area = sum(d["area"] for d in plan["districts"].values()) * self.ca["unitKm"] ** 2
            self.assertTrue(403466 * 0.99 < area < 423970, (plan["key"], area))

    def test_the_old_third_and_sixth_hold_the_towns_on_record(self):
        # Wikipedia, "California's 3rd congressional district" (2023-2027):
        # Roseville, Folsom, Rocklin, Auburn and Lincoln, and Inyo, Mono and
        # Nevada counties. The 6th: Rancho Cordova and Citrus Heights.
        for town in ("Roseville", "Folsom", "Rocklin", "Auburn", "Lincoln",
                     "Truckee", "Grass Valley", "Bishop", "Mammoth Lakes"):
            self.assertEqual(self.district_of("current", town), 3, town)
        for town in ("Rancho Cordova", "Citrus Heights"):
            self.assertEqual(self.district_of("current", town), 6, town)

    def test_the_new_third_and_sixth_hold_the_towns_on_record(self):
        # KCRA and CBS Sacramento on the Proposition 50 lines: the new 3rd
        # takes Nevada County, Folsom and the Lake Tahoe Basin and drops the
        # eastern Sierra; the new 6th takes Roseville, Rocklin, Citrus
        # Heights and West Sacramento.
        for town in ("Truckee", "Grass Valley", "Nevada City", "Folsom", "South Lake Tahoe"):
            self.assertEqual(self.district_of("next", town), 3, town)
        for town in ("Roseville", "Rocklin", "Citrus Heights", "West Sacramento"):
            self.assertEqual(self.district_of("next", town), 6, town)
        self.assertNotEqual(self.district_of("next", "Bishop"), 3)

    def test_overlaps_agree_with_an_independent_measurement(self):
        # Measured separately with mapshaper's overlay: the new 3rd is 97%
        # old 3rd, 2.5% old 6th, 0.9% old 7th; the new 6th is 50% old 6th,
        # 37% old 3rd, 13% old 7th.
        came = {(f[0], f[1]): f[2] for f in self.ca["flows"]}
        expected = {(3, 3): 0.97, (6, 3): 0.025, (7, 3): 0.009,
                    (6, 6): 0.50, (3, 6): 0.37, (7, 6): 0.13}
        for pair, share in expected.items():
            self.assertAlmostEqual(came.get(pair, 0), share, delta=0.015, msg=pair)

    def test_manhattan_has_a_closer_inset_named_for_new_york(self):
        # Excluding the town an inset was already named for once titled
        # Manhattan "Yonkers & New Rochelle" and central Houston "Pasadena &
        # Pearland"; a closer view of the same town says so instead.
        ny = load_state("NY")
        city = next(i for i in ny["insets"] if i["title"] == "New York")
        self.assertEqual([d["title"] for d in city["detail"]], ["New York, closer"])
        x, y = dict((p[0], p[1:3]) for p in ny["places"])["New York"]
        self.assertTrue(any(b[0] < x < b[0] + b[2] and b[1] < y < b[1] + b[3]
                            for b in (d["box"] for d in city["detail"])))

    def test_san_francisco_is_labelled_in_san_francisco(self):
        # Its Census internal point is on the Farallon Islands, 52 km out.
        x, y = self.towns["San Francisco"]
        inset = next(i for i in self.ca["insets"] if "San Francisco" in i["title"])
        b = inset["box"]
        self.assertTrue(b[0] < x < b[0] + b[2] and b[1] < y < b[1] + b[3])


def numbered(state, plan, drawn):
    """The districts kyc-districts.js numbers in *plan* when the statewide
    map is drawn *drawn* pixels wide: wherever a district has LABEL_ROOM_PX
    of room around its label point - statewide, in an inset drawn at
    min(drawn, width), and in that inset's closer insets when it is drawn
    narrower than it fits."""
    if state["atLarge"]:
        return set(plan["districts"])
    rule = districts.LABEL_ROOM_PX
    px = drawn / state["viewBox"][2]
    out = {n for n, d in plan["districts"].items() if d["room"] * px >= rule}

    def visit(found):
        for inset in found:
            width = min(drawn, inset["width"])
            x, y, w, h = inset["box"]
            scale = width / w
            margin = 9 / scale
            out.update(n for n, d in plan["districts"].items()
                       if x + margin <= d["at"][0] <= x + w - margin
                       and y + margin <= d["at"][1] <= y + h - margin
                       and d["room"] * scale >= rule)
            if width < inset["fits"]:
                visit(inset.get("detail", []))

    visit(state["insets"])
    return out


_STATES = {}


def load_state(code):
    if code not in _STATES:
        _STATES[code] = districts.build_state(code, ROOT, districts.load_places(ROOT))
    return _STATES[code]


class TestProjection(unittest.TestCase):

    def test_it_is_equal_area(self):
        # A one-degree cell has area dlon * (sin lat2 - sin lat1) on the unit
        # sphere; an equal-area projection keeps it, wherever the cell is.
        albers = districts._Albers((34.0, 40.5), -120.0)
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

    def test_alaska_is_not_split_by_the_antimeridian(self):
        # The Aleutians reach past 180 degrees; they are west of Alaska.
        albers = districts.projection_for("AK", [(-150, 60), (179, 52), (-130, 55)])
        west, _ = albers.raw(179.5, 52)
        main, _ = albers.raw(-150, 61)
        self.assertLess(west, main)

    def test_web_mercator_and_lambert_are_undone(self):
        import fetch_district_maps as F

        mercator = ('PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",GEOGCS["GCS_WGS_1984",'
                    'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]]],'
                    'PROJECTION["Mercator_Auxiliary_Sphere"],PARAMETER["False_Easting",0.0],'
                    'PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",0.0],'
                    'UNIT["Meter",1.0]]')
        lon, lat = F.unprojector(mercator)(-13358338.895192828, 4865942.279503176)
        self.assertAlmostEqual(lon, -120.0, places=6)
        self.assertAlmostEqual(lat, 40.0, places=6)
        # NC State Plane (EPSG:2264, US feet): Raleigh's Capitol is at
        # roughly 2,106,000 ft E, 738,000 ft N.
        state_plane = ('PROJCS["NAD_1983_StatePlane_North_Carolina_FIPS_3200_Feet",'
                       'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
                       'SPHEROID["GRS_1980",6378137.0,298.257222101]]],'
                       'PROJECTION["Lambert_Conformal_Conic"],'
                       'PARAMETER["False_Easting",2000000.002616666],'
                       'PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",-79.0],'
                       'PARAMETER["Standard_Parallel_1",34.33333333333334],'
                       'PARAMETER["Standard_Parallel_2",36.16666666666666],'
                       'PARAMETER["Latitude_Of_Origin",33.75],UNIT["Foot_US",0.3048006096012192]]')
        lon, lat = F.unprojector(state_plane)(2106000, 738000)
        self.assertAlmostEqual(lon, -78.64, delta=0.02)
        self.assertAlmostEqual(lat, 35.78, delta=0.02)

    def test_an_unknown_projection_is_refused(self):
        import fetch_district_maps as F

        with self.assertRaises(SystemExit):
            F.unprojector('PROJCS["x",GEOGCS["g",DATUM["d",SPHEROID["s",6378137,298.25]]],'
                          'PROJECTION["Transverse_Mercator"],UNIT["Meter",1.0]]')


def _dbf(names, encoding):
    """A one-field dBase file holding *names*, encoded as *encoding*."""
    import struct
    width = 40
    header = struct.pack("<BBBBIHH20x", 3, 126, 1, 1, len(names), 32 + 32 + 1, width + 1)
    field = b"NAME".ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([width, 0]) + b"\0" * 14
    rows = b"".join(b" " + n.encode(encoding).ljust(width, b" ") for n in names)
    return header + field + b"\r" + rows + b"\x1a"


def _null_shp(count):
    import struct
    head = struct.pack(">I", 9994) + b"\0" * 20 + struct.pack(">I", 50 + 6 * count) + \
        struct.pack("<ii", 1000, 5) + b"\0" * 64
    return head + b"".join(struct.pack(">ii", i + 1, 2) + struct.pack("<i", 0) for i in range(count))


class TestText(unittest.TestCase):
    """A shapefile says its own encoding in its .cpg. Read as Latin-1, the
    Census's UTF-8 put "DoÃ±a Ana County" and sixteen Puerto Rico municipios
    on the page."""

    def layer(self, cpg, encoding):
        import fetch_district_maps as F
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("x.dbf", _dbf(["Doña Ana County", "Mayagüez Municipio"], encoding))
            archive.writestr("x.shp", _null_shp(2))
            if cpg is not None:
                archive.writestr("x.cpg", cpg)
        with mock.patch.object(F, "get", return_value=buffer.getvalue()):
            return [row["NAME"] for row, _ in F.read_layer("https://example.test/x.zip")]

    def test_a_layer_that_declares_utf8_is_read_as_utf8(self):
        self.assertEqual(self.layer("UTF-8", "utf-8"), ["Doña Ana County", "Mayagüez Municipio"])
        self.assertEqual(self.layer("utf8\n", "utf-8"), ["Doña Ana County", "Mayagüez Municipio"])

    def test_a_layer_that_declares_nothing_is_latin1(self):
        self.assertEqual(self.layer(None, "latin-1"), ["Doña Ana County", "Mayagüez Municipio"])

    def test_no_vendored_or_generated_file_carries_mojibake(self):
        # UTF-8 read as Latin-1 turns every accented letter into "Ã" or "Â"
        # followed by a character from U+0080-U+00BF.
        broken = re.compile("[\u00c2\u00c3][\u0080-\u00bf]")
        folders = ["district_maps", "legislative_maps", "local_maps", "local_governments",
                   os.path.join("candidate_profiles_site", "data")]
        found = []
        for folder in folders:
            for base, _, files in os.walk(os.path.join(ROOT, folder)):
                for name in files:
                    if not name.endswith((".json", ".js")):
                        continue
                    with open(os.path.join(base, name), encoding="utf-8") as handle:
                        hit = broken.search(handle.read())
                    if hit:
                        found.append(f"{os.path.relpath(os.path.join(base, name), ROOT)}: {hit.group(0)!r}")
        self.assertEqual(found, [])


def square(x0, y0, x1, y1):
    return [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]


class TestMeasure(unittest.TestCase):

    def test_overlaps_of_squares(self):
        old = {1: square(0, 0, 10, 10), 2: square(10, 0, 20, 10)}
        new = {1: square(5, 0, 15, 10), 2: square(0, 0, 5, 10) + square(15, 0, 20, 10)}
        areas, overlaps = districts.measure([old, new], 12)
        self.assertEqual(areas, [{1: 100.0, 2: 100.0}, {1: 100.0, 2: 100.0}])
        self.assertEqual(overlaps, {(1, 1): 50.0, (2, 1): 50.0, (1, 2): 50.0, (2, 2): 50.0})

    def test_one_plan_is_measured_alone(self):
        areas, overlaps = districts.measure([{1: square(0, 0, 4, 5)}], 12)
        self.assertEqual((areas, overlaps), ([{1: 20.0}], {}))

    def test_a_hole_is_not_area(self):
        donut = [[(0, 0), (10, 0), (10, 10), (0, 10)], [(4, 4), (6, 4), (6, 6), (4, 6)]]
        areas, _ = districts.measure([{1: donut}, {1: donut}], 12)
        self.assertEqual(areas[0][1], 96.0)

    def test_a_new_district_out_at_sea_is_sized_by_its_land(self):
        # The old map stops at the shore; the new one runs out over water.
        old = {1: square(0, 0, 10, 10)}
        new = {1: square(0, 0, 10, 20)}
        areas, overlaps = districts.measure([old, new], 22)
        self.assertEqual(districts.land_areas(areas, overlaps), {1: 100.0})
        self.assertEqual(districts.flows(areas, overlaps), [[1, 1, 1.0, 1.0]])

    def test_an_old_district_the_new_plan_misses_is_an_error(self):
        with self.assertRaises(districts.DistrictsError) as caught:
            districts.flows([{1: 100.0}, {1: 100.0}], {(1, 1): 90.0})
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
        self.assertEqual(districts.lines_to_path([[(0, 0), (1, 1), (3, 1)]]), "M0,0l1,1 2,0")


def _topology(numbers=(1, 2), points=None):
    """A two-district state, renumbered the other way round in its new map,
    with one county around both. Unquantised."""
    left = [[-121.0, 38.0], [-120.5, 38.0], [-120.5, 38.5], [-121.0, 38.5], [-121.0, 38.0]]
    right = [[-120.5, 38.0], [-120.0, 38.0], [-120.0, 38.5], [-120.5, 38.5], [-120.5, 38.0]]
    whole = [[-121.0, 38.0], [-120.0, 38.0], [-120.0, 38.5], [-121.0, 38.5], [-121.0, 38.0]]
    points = points or {1: [-120.75, 38.25], 2: [-120.25, 38.25]}

    def plan(first, second):
        return {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "arcs": [[first]], "properties": {"d": numbers[0]}},
            {"type": "Polygon", "arcs": [[second]], "properties": {"d": numbers[1]}}]}

    def pts(swap):
        return {"type": "GeometryCollection", "geometries": [
            {"type": "Point", "coordinates": points[2 if swap else 1], "properties": {"d": 1}},
            {"type": "Point", "coordinates": points[1 if swap else 2], "properties": {"d": 2}}]}

    return {"type": "Topology", "arcs": [left, right, whole], "objects": {
        "current": plan(0, 1), "next": plan(1, 0),
        "current_pts": pts(False), "next_pts": pts(True),
        "counties": {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "arcs": [[2]], "properties": {"name": "Test County"}}]}}}


class TestBuildState(unittest.TestCase):
    """The loud failures, on a two-district state."""

    def build(self, topo, redrawn=True):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, districts.MAPS_DIR))
            with open(districts.map_file("ZZ", tmp), "w", encoding="utf-8") as f:
                json.dump(topo, f)
            entry = {"ZZ": {"headline": "", "intro": ""}} if redrawn else {}
            with mock.patch.dict(districts.REDRAWN, entry), \
                    mock.patch.object(districts, "state_name", lambda c: "Zed"):
                return districts.build_state("ZZ", tmp, {"ZZ": [["Town", -120.6, 38.2, 9]]})

    def test_a_clean_state_builds(self):
        state = self.build(_topology())
        self.assertEqual([sorted(p["districts"]) for p in state["plans"]], [["1", "2"]] * 2)
        self.assertEqual(state["flows"], [[1, 2, 1.0, 1.0], [2, 1, 1.0, 1.0]])
        self.assertEqual(state["places"][0][0], "Town")
        self.assertEqual([p["label"] for p in state["plans"]], ["Before", "After"])

    def test_a_new_map_with_no_entry_is_an_error(self):
        with self.assertRaisesRegex(districts.DistrictsError, "REDRAWN has no entry"):
            self.build(_topology(), redrawn=False)

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


class TestInsets(unittest.TestCase):

    def test_small_districts_get_a_named_box_and_big_ones_do_not(self):
        plan = {"1": {"room": 300, "at": [500, 500], "box": [0, 0, 1000, 1000]},
                "2": {"room": 5, "at": [100, 100], "box": [95, 95, 105, 105]},
                "3": {"room": 5, "at": [110, 100], "box": [105, 95, 115, 105]}}
        places = [["Big City", 101, 101, 500000], ["Small Town", 112, 99, 1000]]
        boxes = districts.insets([plan], places, [0, 0, 1000, 1000])
        self.assertEqual(len(boxes), 1)
        self.assertEqual(boxes[0]["title"], "Big City")
        x, y, w, h = boxes[0]["box"]
        for n in ("2", "3"):
            self.assertTrue(x < plan[n]["at"][0] < x + w and y < plan[n]["at"][1] < y + h)
        self.assertNotIn("detail", boxes[0])

    def test_a_district_too_small_for_its_inset_gets_a_closer_one(self):
        # Seven districts around a town, one of them a sliver: the inset that
        # numbers the six on a phone cannot number the seventh, so it holds
        # a closer inset around it, named for the same town.
        plan = {str(n): {"room": 4.0, "at": [100 + 12 * n, 100], "box":
                         [96 + 12 * n, 96, 104 + 12 * n, 104]} for n in range(1, 7)}
        plan["7"] = {"room": 0.4, "at": [130, 112], "box": [129, 111, 131, 113]}
        boxes = districts.insets([plan], [["Town", 130, 105, 90000]], [0, 0, 1000, 1000])
        self.assertEqual(len(boxes), 1)
        self.assertGreater(boxes[0]["fits"], districts.PHONE_PX)
        self.assertEqual([d["title"] for d in boxes[0]["detail"]], ["Town, closer"])
        x, y, w, h = boxes[0]["detail"][0]["box"]
        self.assertTrue(x < 130 < x + w and y < 112 < y + h)


class TestEmitted(unittest.TestCase):

    def test_each_state_gets_its_own_file_and_signature(self):
        maps = {"ZZ": {"plans": [], "x": 1}, "YY": {"plans": [], "x": 2}}
        with tempfile.TemporaryDirectory() as tmp:
            written = emit.write_districts(maps, root=tmp)
            self.assertEqual(len(written), 2)
            self.assertEqual(emit.check_districts(maps, tmp), [])
            path = emit.district_file("ZZ", tmp)
            self.assertEqual(emit.read_signature(path=path), emit.districts_signature(maps["ZZ"]))
            with open(path, encoding="utf-8") as f:
                self.assertIn('window.kycDistricts = {"ZZ":', f.read())
            maps["ZZ"]["x"] = 3
            self.assertEqual([p for p, _ in emit.check_districts(maps, tmp)], [path])

    def test_the_build_metadata_lists_every_map(self):
        from kyc import summary
        index = summary.district_maps()
        self.assertEqual(len(index), 56)
        self.assertEqual(index["TX"], {"page": "districts/tx.html", "name": "Texas",
                                       "redrawn": True})
        self.assertFalse(index["MO"]["redrawn"])

    def test_the_redrawn_states_are_the_nine_on_record(self):
        # Verified against each enacting body's record on 2026-10-03.
        # Missouri's 2025 map was suspended by referendum and is not in effect.
        self.assertEqual(sorted(districts.REDRAWN),
                         ["AL", "CA", "FL", "LA", "NC", "OH", "TN", "TX", "UT"])


class TestValidation(unittest.TestCase):

    def races(self, code, count):
        return [{"chamber": "House", "state": code, "district": n} for n in range(1, count + 1)]

    def state(self, count):
        return {"plans": [{"districts": {str(n): {} for n in range(1, count + 1)}}]}

    def test_a_map_for_the_seats_on_the_ballot_passes(self):
        self.assertEqual(validate.check_district_maps(self.races("CA", 52),
                                                      {"CA": self.state(52)}), [])

    def test_a_map_numbering_other_seats_is_an_error(self):
        issues = validate.check_district_maps(self.races("CA", 53), {"CA": self.state(52)})
        self.assertEqual([(i.level, i.code) for i in issues], [("error", "district-map-seats")])

    def test_a_seat_with_no_race_has_nothing_to_match(self):
        self.assertEqual(validate.check_district_maps(self.races("CA", 1),
                                                      {"PR": {"plans": [{"districts": {"0": {}}}]}}),
                         [])

    def test_a_map_that_did_not_build_is_an_error(self):
        issues = validate.check_district_maps([], None, "label point is outside")
        self.assertEqual([(i.level, i.code) for i in issues], [("error", "district-map")])


class TestPlacesTool(unittest.TestCase):
    """tools/fetch_district_maps.py's places, offline."""

    def gazetteer(self, rows):
        header = ("USPS\tGEOID\tANSICODE\tNAME\tLSAD\tFUNCSTAT\tALAND\tAWATER\t"
                  "ALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG\n")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("2020_Gaz_place_national.txt", header + "".join(rows))
        return buffer.getvalue()

    def test_a_point_off_the_largest_piece_moves_onto_it(self):
        import fetch_district_maps as F

        # San Francisco: its internal point on a small island to the west.
        gaz = self.gazetteer([
            "CA\t0667000\t02411786\tSan Francisco city\t25\tA\t1\t0\t1\t0\t37.72\t-123.03\n",
            "CA\t0680000\t02413403\tTruckee town\t43\tA\t1\t0\t1\t0\t39.33\t-120.18\n"])
        est = ("SUMLEV,STATE,COUNTY,PLACE,NAME,POPESTIMATE2024\n"
               "162,06,000,67000,San Francisco city,827526\n"
               "162,06,000,80000,Truckee town,17240\n"
               "162,06,000,99999,Newtown city,40\n").encode("latin-1")
        mainland = [(-122.52, 37.70), (-122.36, 37.70), (-122.36, 37.81), (-122.52, 37.81)]
        island = [(-123.04, 37.71), (-123.02, 37.71), (-123.02, 37.73), (-123.04, 37.73)]
        truckee = [(-120.25, 39.30), (-120.10, 39.30), (-120.10, 39.38), (-120.25, 39.38)]
        shapes = {"0667000": [mainland, island], "0680000": [truckee]}
        payload = F.build_places(gaz, est, lambda fips: shapes)
        sf = payload["places"]["CA"][0]
        self.assertEqual(sf[0], "San Francisco")
        self.assertTrue(-122.52 < sf[1] < -122.36 and 37.70 < sf[2] < 37.81, sf)
        self.assertEqual([m[1] for m in payload["moved"]], ["San Francisco"])
        self.assertEqual(payload["places"]["CA"][1], ["Truckee", -120.18, 39.33, 17240])
        self.assertEqual(payload["unlocated"], ["Newtown city, CA"])

    def test_legal_forms_are_not_labels(self):
        import fetch_district_maps as F

        self.assertEqual(F._short_name("Truckee town"), "Truckee")
        self.assertEqual(F._short_name("Nashville-Davidson metropolitan government (balance)"),
                         "Nashville-Davidson")
        self.assertEqual(F._short_name("Juneau city and borough"), "Juneau")

    def test_the_committed_places_were_checked_against_their_boundaries(self):
        with open(os.path.join(ROOT, districts.PLACES_FILE), encoding="utf-8") as f:
            payload = json.load(f)
        self.assertIn("San Francisco", [m[1] for m in payload["moved"]])
        self.assertEqual(len(payload["places"]), 51)          # 50 states and D.C.


class TestTopology(unittest.TestCase):
    """The tool simplifies shared boundaries once, so neighbours still touch."""

    def test_neighbours_share_their_simplified_boundary(self):
        import fetch_district_maps as F

        wiggle = [(-120.5 + 0.0001 * (i % 2), 38.0 + i * 0.005) for i in range(101)]
        left = [(-121.0, 38.0)] + wiggle + [(-121.0, 38.5)]
        right = [wiggle[0], (-120.0, 38.0), (-120.0, 38.5)] + list(reversed(wiggle))[:-1]
        topo = F.Topology(38.25)
        topo.add("p", [({"d": 1}, [left]), ({"d": 2}, [right])], tolerance=250.0)
        shared = [a for a in topo.arcs if len(a) > 2]
        self.assertTrue(shared, "the wiggly boundary should be one shared arc")
        rings = [topo.ring(ids) for _, arcs in topo.objects["p"] for ids in arcs]
        self.assertTrue(set(rings[0]) & set(rings[1]))

    def test_a_new_district_is_labelled_on_the_old_map_s_land(self):
        # PR #34 moved polylabel into kyc/geo.py and deleted the helper this
        # path called, so the next refresh of a redrawn state would have
        # crashed. A new district reaching far out to sea is labelled on land.
        import fetch_district_maps as F

        land = [(-121.0, 38.0), (-120.9, 38.0), (-120.9, 38.1), (-121.0, 38.1)]
        sea = [(-121.0, 38.0), (-120.5, 38.0), (-120.5, 38.1), (-121.0, 38.1)]
        topo = F.Topology(38.05)
        topo.add("current", [({"d": 1}, [land])])
        topo.add("next", [({"d": 1}, [sea])])
        topo.label_points("next", "next_pts", land=topo.rings_m("current"))
        x, y = topo.points["next_pts"][0]["coordinates"]
        metres = (x * topo.kx, y * topo.ky)
        self.assertGreater(geo.signed_distance(*metres, topo.rings_m("current")), 0)


if __name__ == "__main__":
    unittest.main()
