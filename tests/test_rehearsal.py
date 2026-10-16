"""The changeover rehearsal (tools/rehearse_changeover.py): fiction about
real people that must never land in the repository, and a membership that
seats one person in every seat."""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

import rehearse_changeover as rehearsal  # noqa: E402
from kyc import cycle, legislators, sources  # noqa: E402


class TestWhereItWrites(unittest.TestCase):
    def test_never_inside_the_repository(self):
        for inside in (ROOT, os.path.join(ROOT, "rehearsal"),
                       os.path.join(ROOT, "candidate_profiles_site", "x")):
            with self.assertRaises(rehearsal.RehearsalError):
                rehearsal.check_out(inside)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(rehearsal.check_out(tmp), os.path.realpath(tmp))

    def test_the_command_refuses_too(self):
        self.assertEqual(rehearsal.main(["--out", os.path.join(ROOT, "rehearsal")]), 2)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "rehearsal")))


class TestTheFictionalMemberships(unittest.TestCase):
    def test_january_seats_one_person_in_every_record_seat(self):
        made = rehearsal.january()
        if made is None:
            self.skipTest("the new Congress is sitting: the committed data is the case")
        snapshot, gone, _log = made
        self.assertEqual(cycle.phase(snapshot), "record")
        record = sources.load_all(ROOT)["record"]
        seats = {(p["chamber"], p["state"],
                  p.get("district") if p["chamber"] == "House" else p.get("senateClass"))
                 for p in snapshot["legislators"]}
        for rid, race in record["races"].items():
            key = (race["chamber"], race["state"],
                   race.get("district") if race["chamber"] == "House" else race.get("senateClass"))
            self.assertIn(key, seats, rid)
        # Everyone who left is in the historical file the departures read.
        before = legislators.by_bioguide(legislators.load_snapshot(ROOT))
        after = legislators.by_bioguide(snapshot)
        self.assertEqual({g["id"]["bioguide"] for g in gone}, set(before) - set(after))
        # Fiction is never a real id.
        self.assertTrue(all(b in before or b.startswith("Z9") for b in after))

    def test_december_replaces_one_appointee(self):
        for label in ("december-loses", "december-wins"):
            made = rehearsal.december(label)
            if made is None:
                self.skipTest("the specials' winners are seated")
            snapshot, historical = made
            self.assertEqual(len(historical), 1, label)
            self.assertEqual(sum(1 for p in snapshot["legislators"]
                                 if p["bioguide"].startswith("Z9")), 1, label)


if __name__ == "__main__":
    unittest.main()
