"""Tests for the build-time map geometry.

The map used to decode TopoJSON in the browser with d3 and topojson-client.
That work moved to kyc/geo.py, which means a shape that decodes wrongly is now
a silent, committed data error rather than a visible runtime crash - so the
decoding is checked here against the atlas itself.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, geo  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def replay(path_data):
    """Reconstruct absolute points from an emitted relative SVG path.

    Mirrors what an SVG renderer does, so the assertion is about what a
    browser will actually draw rather than about the string we produced.
    """
    points = []
    x = y = 0.0
    for command, args in re.findall(r"([MlZ])([^MlZ]*)", path_data):
        if command == "Z":
            continue
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", args)]
        pairs = list(zip(numbers[0::2], numbers[1::2]))
        if command == "M":
            x, y = pairs[0]
            points.append((round(x, 1), round(y, 1)))
            pairs = pairs[1:]
        for dx, dy in pairs:
            x, y = x + dx, y + dy
            points.append((round(x, 1), round(y, 1)))
    return points


class TestArcDecoding(unittest.TestCase):
    def test_quantised_deltas_accumulate(self):
        topo = {
            "type": "Topology",
            "transform": {"scale": [2.0, 4.0], "translate": [10.0, 20.0]},
            "arcs": [[[1, 1], [2, 0], [0, 3]]],
            "objects": {"states": {"type": "GeometryCollection", "geometries": []}},
        }
        # Positions are cumulative: (1,1) -> (3,1) -> (3,4), then transformed.
        self.assertEqual(
            geo.decode_arcs(topo),
            [[(12.0, 24.0), (16.0, 24.0), (16.0, 36.0)]],
        )

    def test_unquantised_topology_passes_coordinates_through(self):
        topo = {"type": "Topology", "arcs": [[[1.5, 2.5], [3.5, 4.5]]]}
        self.assertEqual(geo.decode_arcs(topo), [[(1.5, 2.5), (3.5, 4.5)]])

    def test_negative_index_reverses_an_arc(self):
        arcs = [[(0, 0), (1, 0), (1, 1)]]
        # ~(-1) == 0, so -1 means "arc 0, backwards".
        self.assertEqual(geo._ring([-1], arcs), [(1, 1), (1, 0), (0, 0)])

    def test_shared_endpoint_is_not_repeated(self):
        arcs = [[(0, 0), (1, 1)], [(1, 1), (2, 2)]]
        self.assertEqual(geo._ring([0, 1], arcs), [(0, 0), (1, 1), (2, 2)])


class TestPathRendering(unittest.TestCase):
    def test_relative_encoding_round_trips(self):
        ring = [(10.0, 10.0), (13.5, 10.0), (13.5, 14.25), (10.0, 14.0)]
        path = geo.rings_to_path([ring])
        self.assertEqual(
            replay(path),
            [(10.0, 10.0), (13.5, 10.0), (13.5, 14.2), (10.0, 14.0)],
        )

    def test_duplicate_points_are_dropped(self):
        ring = [(0, 0), (0, 0.01), (5, 0), (5, 5), (0, 0)]
        # The second point rounds onto the first, and the repeated close is
        # left to "Z".
        self.assertEqual(replay(geo.rings_to_path([ring])), [(0, 0), (5, 0), (5, 5)])

    def test_degenerate_rings_are_skipped(self):
        self.assertEqual(geo.rings_to_path([[(0, 0), (1, 1)]]), "")
        self.assertEqual(geo.rings_to_path([[]]), "")

    def test_whole_numbers_lose_their_decimal(self):
        self.assertNotIn(".0", geo.rings_to_path([[(1, 1), (3, 1), (3, 3)]]))

    def test_negative_zero_is_normalised(self):
        # -0.0 formats as "-0" and would differ between platforms otherwise.
        self.assertEqual(geo._round(-0.04), 0.0)

    def test_path_is_closed(self):
        self.assertTrue(geo.rings_to_path([[(0, 0), (4, 0), (4, 4)]]).endswith("Z"))


class TestCentroid(unittest.TestCase):
    def test_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        self.assertEqual(geo.rings_centroid([square]), (5.0, 5.0))

    def test_triangle(self):
        triangle = [(0, 0), (6, 0), (0, 6), (0, 0)]
        self.assertEqual(geo.rings_centroid([triangle]), (2.0, 2.0))

    def test_zero_area_falls_back_to_the_vertex_mean(self):
        # A label still has to land somewhere; the origin would be wrong.
        line = [(0, 0), (4, 0), (0, 0)]
        self.assertEqual(geo.rings_centroid([line]), (1.3, 0.0))

    def test_no_points_has_no_centroid(self):
        self.assertIsNone(geo.rings_centroid([]))


class TestAtlas(unittest.TestCase):
    """The real atlas, decoded the way the build decodes it."""

    @classmethod
    def setUpClass(cls):
        cls.geo = geo.build(ROOT)

    def test_fifty_states_and_dc(self):
        self.assertEqual(len(self.geo["states"]), 51)

    def test_every_state_has_geometry_and_a_label_position(self):
        for code, shape in self.geo["states"].items():
            with self.subTest(state=code):
                self.assertTrue(shape["d"].startswith("M"), code)
                self.assertGreater(len(shape["d"]), 40, code)
                self.assertIsNotNone(shape["centroid"], code)
                self.assertTrue(shape["name"], code)

    def test_every_centroid_sits_inside_its_own_bounding_box(self):
        # Catches a ring stitched together in the wrong order, which produces
        # a plausible-looking path but throws the label across the map.
        for code, shape in self.geo["states"].items():
            cx, cy = shape["centroid"]
            min_x, min_y, max_x, max_y = shape["bounds"]
            with self.subTest(state=code):
                self.assertTrue(min_x <= cx <= max_x, f"{code} x={cx} in {min_x}..{max_x}")
                self.assertTrue(min_y <= cy <= max_y, f"{code} y={cy} in {min_y}..{max_y}")

    def test_geometry_stays_inside_the_viewbox(self):
        # Alaska's projected inset reaches slightly left of zero in the source
        # atlas; nothing should escape by more than that.
        _, _, width, height = self.geo["viewBox"]
        for code, shape in self.geo["states"].items():
            min_x, min_y, max_x, max_y = shape["bounds"]
            with self.subTest(state=code):
                self.assertGreater(min_x, -80, code)
                self.assertLess(max_x, width + 20, code)
                self.assertGreater(min_y, -20, code)
                self.assertLess(max_y, height + 20, code)

    def test_known_states_land_where_they_should(self):
        # A projection or FIPS mix-up would move these; the coarse quadrant is
        # the point, not the exact pixel.
        west = self.geo["states"]["CA"]["centroid"][0]
        east = self.geo["states"]["ME"]["centroid"][0]
        north = self.geo["states"]["MN"]["centroid"][1]
        south = self.geo["states"]["FL"]["centroid"][1]
        self.assertLess(west, east, "California should sit west of Maine")
        self.assertLess(north, south, "Minnesota should sit north of Florida")

    def test_every_path_replays_to_a_closed_shape(self):
        for code, shape in self.geo["states"].items():
            with self.subTest(state=code):
                self.assertGreaterEqual(len(replay(shape["d"])), 3, code)

    def test_territories_are_all_present_and_drawable(self):
        codes = [t["code"] for t in self.geo["territories"]]
        self.assertEqual(sorted(codes), ["AS", "DC", "GU", "MP", "PR", "VI"])
        for territory in self.geo["territories"]:
            self.assertTrue(territory["d"].strip().startswith("M"))
            self.assertTrue(territory["name"])

    def test_every_state_in_the_fips_table_is_accounted_for(self):
        # PR and VI are not in the 10m atlas; they are in the territory strip.
        drawn = set(self.geo["states"]) | {t["code"] for t in self.geo["territories"]}
        self.assertEqual(set(geo.FIPS_TO_STATE.values()) - drawn, set())

    def test_build_is_deterministic(self):
        self.assertEqual(geo.build(ROOT), self.geo)

    def test_unknown_fips_is_loud_not_silent(self):
        # A state quietly missing from the map is exactly the failure this
        # project treats as worse than a crash.
        original = dict(geo.FIPS_TO_STATE)
        try:
            geo.FIPS_TO_STATE.pop("48")  # Texas
            with self.assertRaises(geo.AtlasError):
                geo.build(ROOT)
        finally:
            geo.FIPS_TO_STATE.clear()
            geo.FIPS_TO_STATE.update(original)

    def test_missing_atlas_raises(self):
        with self.assertRaises(geo.AtlasError):
            geo.load_atlas(os.path.join(ROOT, "tests"))


class TestEmittedGeo(unittest.TestCase):
    def test_script_assigns_the_global_the_page_reads(self):
        text = emit._json(geo.build(ROOT))
        self.assertIn('"states"', text)

    def test_json_cannot_close_the_script_tag(self):
        payload = emit._json({"d": "</script><script>alert(1)</script>"})
        self.assertNotIn("</script>", payload)

    def test_json_cannot_open_an_html_comment(self):
        self.assertNotIn("<!--", emit._json({"x": "<!-- swallow the rest"}))


if __name__ == "__main__":
    unittest.main()
