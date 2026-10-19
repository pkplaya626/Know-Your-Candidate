"""The tile layouts (kyc/tiles.py) and the balance figures the charts draw
(kyc/summary.py): audit 2026-10-17, VISUALS-21, -27 and -35."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import districts, summary, tiles  # noqa: E402
from kyc.normalize import TERRITORIES  # noqa: E402
from kyc.pages import STATE_NAMES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestStateGrid(unittest.TestCase):
    def test_every_place_with_a_page_has_one_tile(self):
        self.assertEqual(set(tiles.STATE_GRID), set(STATE_NAMES))
        spots = list(tiles.STATE_GRID.values())
        self.assertEqual(len(spots), len(set(spots)), "two places on one tile")

    def test_the_territories_have_a_row_of_their_own(self):
        # D.C. is with the states; the five territories sit apart below them.
        last = max(r for r, _c in tiles.STATE_GRID.values())
        below = {c for c, (r, _col) in tiles.STATE_GRID.items() if r == last}
        self.assertEqual(below, set(TERRITORIES) - {"DC"})


class TestBlocks(unittest.TestCase):
    def test_block_shapes_hold_their_seats_and_stay_short(self):
        for seats in range(1, 60):
            cols, rows = tiles.block_shape(seats)
            self.assertGreaterEqual(cols * rows, seats)
            self.assertLessEqual(rows, tiles.MAX_ROWS)
            # Never a whole empty column or row.
            self.assertLess(cols * rows - seats, max(cols, rows))
        self.assertEqual(tiles.block_shape(1), (1, 1))
        self.assertEqual(tiles.block_shape(2), (2, 1))
        with self.assertRaises(tiles.TileError):
            tiles.block_shape(0)

    def test_districts_are_placed_north_to_south_then_west_to_east(self):
        # (lon, lat): 1 north-west, 2 north-east, 3 south-west, 4 south-east.
        points = {1: (-100, 40), 2: (-90, 41), 3: (-99, 30), 4: (-91, 31)}
        self.assertEqual(tiles.place(points, 2, 2), {1: [0, 0], 2: [1, 0], 3: [0, 1], 4: [1, 1]})

    def test_a_short_last_row_spreads_across_the_block(self):
        points = {1: (-100, 40), 2: (-95, 40), 3: (-90, 40), 4: (-100, 30), 5: (-90, 30)}
        placed = tiles.place(points, 3, 2)
        self.assertEqual(placed[4], [0, 1])
        self.assertEqual(placed[5], [2, 1], "the eastern district stays east")

    def test_check_finds_two_districts_on_one_square_and_overlapping_blocks(self):
        layout = {"states": {
            "AA": {"x": 0, "y": 2, "cols": 2, "rows": 1, "cells": {"1": [0, 0], "2": [0, 0]}},
            "BB": {"x": 1, "y": 2, "cols": 2, "rows": 1, "cells": {"1": [0, 0], "2": [1, 0]}},
        }}
        problems = tiles.check(layout, {"AA": 2, "BB": 3})
        self.assertTrue(any("two districts on one square" in p for p in problems))
        self.assertTrue(any("overlap" in p for p in problems))
        self.assertTrue(any("2 squares for 3 seats" in p for p in problems))


class TestHouseLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = tiles.house(ROOT)

    def test_one_square_per_voting_seat_and_nothing_overlaps(self):
        states = self.layout["states"]
        self.assertFalse(set(states) & TERRITORIES, "a delegate has no floor vote")
        # As many squares as each state's map has districts: the layout is
        # read from the same files the district pages draw.
        for code, block in states.items():
            topo = districts._read_json(districts.map_file(code, ROOT), "map")
            expected = len(topo["objects"]["current"]["geometries"])
            self.assertEqual(len(block["cells"]), expected, code)
        self.assertEqual(sum(len(b["cells"]) for b in states.values()), summary.HOUSE_SEATS)
        self.assertEqual(tiles.check(self.layout), [])

    def test_a_redrawn_state_carries_its_2026_plan_too(self):
        for code, block in self.layout["states"].items():
            self.assertEqual("cells2026" in block, code in districts.REDRAWN, code)
            if "cells2026" in block:
                self.assertEqual(set(block["cells2026"]), set(block["cells"]), code)

    def test_every_block_is_inside_the_layout(self):
        for code, b in self.layout["states"].items():
            self.assertGreaterEqual(b["y"] - self.layout["band"], 0, code)
            self.assertLessEqual(b["x"] + b["cols"], self.layout["width"] + 1e-6, code)
            self.assertLessEqual(b["y"] + b["rows"], self.layout["height"] + 1e-6, code)


def senator(pid, party, state, cls):
    return {"id": pid, "name": pid, "chamber": "Senate", "party": party, "state": state,
            "senateClass": cls, "isCandidate": False}


class TestSeatsUp(unittest.TestCase):
    def test_seats_on_the_ballot_are_matched_by_state_and_class(self):
        races = [{"chamber": "Senate", "state": "OH", "senateClass": 3, "special": True},
                 {"chamber": "Senate", "state": "TX", "senateClass": 2},
                 {"chamber": "House", "state": "TX", "district": 1}]
        senators = [senator("A", "Republican", "OH", 3),   # an appointee in a special
                    senator("B", "Republican", "OH", 1),
                    senator("C", "Republican", "TX", 2),
                    senator("D", "Democrat", "TX", 1),
                    senator("E", "Independent", "VT", 2)]
        up = summary.seated_up(senators, races)
        self.assertEqual((up["R"], up["D"], up["I"], up["total"]), (2, 0, 0, 2))

    def test_the_bar_hatches_nothing_once_the_cycle_is_a_record(self):
        races = [{"chamber": "Senate", "state": "TX", "senateClass": 2, "id": "S-TX-2026"}]
        people = [senator("C", "Republican", "TX", 2)]
        built = summary.build(people, races=races)
        self.assertEqual(built["senate"]["up"]["R"], 1)
        # The Congress the cycle elects, read after noon on January 3
        # (kyc/cycle.phase): no seat in it is "on the 2026 ballot" now.
        from kyc import legislators
        new = {"id": {"bioguide": "C000001", "fec": []},
               "name": {"first": "Pat", "last": "Smith", "official_full": "Pat Smith"},
               "bio": {"birthday": "1970-01-01"},
               "terms": [{"type": "rep", "start": "2027-01-03", "end": "2029-01-03",
                          "state": "TX", "district": 5, "party": "Republican"}]}
        record = legislators.build_snapshot([new], fetched="2027-01-04T07:20:00+00:00")
        later = summary.build(people, races=races, snapshot=record)
        self.assertEqual(later["election"]["phase"], "record")
        self.assertNotIn("up", later["senate"])

    def test_the_state_grid_ships_with_the_summary(self):
        built = summary.build([])
        self.assertEqual(built["stateGrid"]["TX"], list(tiles.STATE_GRID["TX"]))
        self.assertNotIn("houseTiles", built, "laid out only when the build names its root")


class TestLocalBar(unittest.TestCase):
    """The counties directory's bar per state (VISUALS-32, rule 49)."""

    KINDS = [("county", "County governments", ""), ("municipal", "Municipal governments", ""),
             ("township", "Town and township governments", ""),
             ("school", "Independent school districts", ""), ("special", "Special districts", "")]

    def test_a_kind_the_state_does_not_have_is_a_word_never_a_zero_part(self):
        from kyc.pages import local_bar
        hawaii = {"county": 3, "municipal": 1, "school": None, "special": 17, "total": 21, "township": None}
        html = local_bar("Hawaii", hawaii, self.KINDS)
        self.assertEqual(html.count('class="lg-seg'), 3)
        self.assertNotIn("lg-township", html)
        self.assertIn("None: town and township governments, independent school districts", html)
        self.assertIn('aria-label="Hawaii: 21 local governments: 3 county governments, 1 municipal '
                      'governments, 17 special districts; none of:', html)

    def test_the_parts_are_shares_of_the_total(self):
        from kyc.pages import local_bar
        html = local_bar("X", {"county": 1, "municipal": 3, "total": 4}, self.KINDS[:2])
        self.assertIn("width:25.000%", html)
        self.assertIn("width:75.000%", html)
        self.assertEqual(local_bar("X", {"total": 0}, self.KINDS), "")

    def test_the_directory_draws_a_bar_for_every_state_it_counts(self):
        import json
        from kyc import pages
        with open(os.path.join(ROOT, "candidate_profiles_site", "data", "census_governments.json"),
                  encoding="utf-8") as handle:
            census = json.load(handle)
        html = pages.render_counties_index("example.org", census=census)
        counted = [c for c, v in census["states"].items() if v.get("total") and c != "DC"]
        self.assertEqual(html.count('class="lg-bar"'), len(counted))
        self.assertIn('class="lg-key"', html)


if __name__ == "__main__":
    unittest.main()
