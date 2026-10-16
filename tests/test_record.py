"""The cycle, the sitting Congress, and the frozen record of the 2026 races
(kyc/cycle.py, kyc/record.py; audit CG-7)."""

import copy
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import cycle, legislators, races, record, sources, validate  # noqa: E402
from kyc.profiles import build_profiles, screen_field  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestCycleArithmetic(unittest.TestCase):
    def test_the_congress_changes_on_january_3(self):
        self.assertEqual(cycle.congress_for_date(datetime.date(2026, 10, 16)), 119)
        self.assertEqual(cycle.congress_for_date(datetime.date(2027, 1, 2)), 119)
        self.assertEqual(cycle.congress_for_date(datetime.date(2027, 1, 3)), 120)
        self.assertEqual(cycle.congress_for_date("2029-01-03"), 121)
        self.assertEqual(cycle.congress_start(120), datetime.date(2027, 1, 3))

    def test_election_day_and_the_congress_it_elects(self):
        self.assertEqual(cycle.general_election_day(2026), datetime.date(2026, 11, 3))
        self.assertEqual(cycle.general_election_day(2028), datetime.date(2028, 11, 7))
        self.assertEqual(cycle.electing_congress(2026), 120)

    def test_ordinals(self):
        self.assertEqual([cycle.ordinal(n) for n in (119, 120, 121, 122, 123, 111, 112)],
                         ["119th", "120th", "121st", "122nd", "123rd", "111th", "112th"])


class TestTheCommittedSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = legislators.load_snapshot(ROOT)

    def test_it_is_the_119th_in_the_campaign(self):
        self.assertEqual(cycle.snapshot_congress(self.snapshot), 119)
        self.assertEqual(cycle.phase(self.snapshot), "campaign")

    def test_a_snapshot_of_mixed_congresses_fails_loudly(self):
        mixed = copy.deepcopy(self.snapshot)
        house = [p for p in mixed["legislators"] if p["chamber"] == "House"]
        for person in house[: len(house) // 2]:
            person["termStart"] = "2027-01-03"
        with self.assertRaises(cycle.CycleError):
            cycle.snapshot_congress(mixed)

    def test_the_record_begins_only_after_noon_on_january_3(self):
        new = copy.deepcopy(self.snapshot)
        for person in new["legislators"]:
            if person["chamber"] == "House":
                person["termStart"] = "2027-01-03"
        new["fetched"] = "2027-01-03T16:59:00+00:00"       # before noon Eastern
        self.assertEqual(cycle.phase(new), "campaign")
        new["fetched"] = "2027-01-04T07:20:00+00:00"
        self.assertEqual(cycle.phase(new), "record")

    def test_the_snapshot_keeps_every_fec_id_and_how_terms_began(self):
        by_id = legislators.by_bioguide(self.snapshot)
        # Appointees are marked as such by the source.
        appointed = {p["state"] for p in self.snapshot["legislators"]
                     if p["chamber"] == "Senate" and p.get("how") == "appointment"}
        self.assertTrue({"FL", "OH"} <= appointed)
        # fecAll holds ids for both chambers where the source lists them.
        self.assertTrue(any(len({i[0] for i in p.get("fecAll", [])}) > 1
                            for p in by_id.values()))


class TestTheRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = sources.load_all(ROOT)
        cls.record = cls.raw["record"]
        cls.snapshot = legislators.load_snapshot(ROOT)

    def test_it_is_committed_and_matches_its_pinned_signature(self):
        self.assertIsNotNone(self.record, "run: python build_profile_site.py record --freeze")
        self.assertEqual(cycle.record_signature(self.record), cycle.RECORD_SIGNATURES[2026])

    def test_its_senate_races_are_classed_and_the_specials_marked(self):
        senate = {rid: r for rid, r in self.record["races"].items() if r["chamber"] == "Senate"}
        self.assertTrue(senate)
        self.assertTrue(all(r["senateClass"] in (2, 3) for r in senate.values()))
        self.assertEqual(sorted(rid for rid, r in senate.items() if r["special"]),
                         ["S-FL-2026", "S-OH-2026"])
        self.assertTrue(all(senate[rid]["senateClass"] == 3 for rid in ("S-FL-2026", "S-OH-2026")))

    def test_appointees_are_marked_never_to_read_reelected(self):
        held = self.record["incumbents"]
        self.assertTrue(held["S-FL-2026"]["appointed"])
        self.assertTrue(held["S-OH-2026"]["appointed"])
        self.assertTrue(all(isinstance(inc["appointed"], bool) for inc in held.values() if inc))

    def test_every_house_seat_today_is_in_the_record(self):
        profiles, _ = build_profiles(dict(self.raw, record=None), snapshot=self.snapshot)
        live = races.contestable(profiles)
        self.assertEqual(live, record.race_ids(self.record))

    def test_freeze_refuses_a_snapshot_of_the_next_congress(self):
        new = copy.deepcopy(self.snapshot)
        for person in new["legislators"]:
            if person["chamber"] == "House":
                person["termStart"] = "2027-01-03"
        profiles, _ = build_profiles(dict(self.raw, record=None), snapshot=self.snapshot)
        with self.assertRaises(record.RecordError):
            record.freeze(profiles, new)

    def test_save_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            record.save(self.record, tmp)
            with self.assertRaises(record.RecordError):
                record.save(self.record, tmp)
            record.save(self.record, tmp, force=True)

    def test_verify_fails_when_a_race_is_removed(self):
        broken = copy.deepcopy(self.record)
        broken["races"].pop("S-GA-2026")
        self.assertNotEqual(cycle.record_signature(broken), cycle.RECORD_SIGNATURES[2026])


def specials_seated(snapshot):
    """The committed membership as it will read once the Florida and Ohio
    special elections' winners are seated: a fictional senator (Z900001) in
    the appointee's place in Florida, and Ohio's appointee re-seated for the
    term to 2029. Built in the test, never committed."""
    after = copy.deepcopy(snapshot)
    people = after["legislators"]
    florida = next(p for p in people if p["chamber"] == "Senate" and p["state"] == "FL"
                   and p["termEnd"] == "2026-11-03")
    people.remove(florida)
    people.append(dict(florida, bioguide="Z900001", name="Zora Example", last="Example",
                       termStart="2026-12-08", termEnd="2029-01-03", how=None,
                       endType=None, fec=[], fecAll=[]))
    ohio = next(p for p in people if p["chamber"] == "Senate" and p["state"] == "OH"
                and p["termEnd"] == "2026-11-03")
    ohio.update(termStart="2026-12-08", termEnd="2029-01-03", how=None, endType=None)
    after["fetched"] = "2026-12-09T07:20:00+00:00"
    return after, florida["bioguide"], ohio["bioguide"]


class TestTheSpecialsSeated(unittest.TestCase):
    """The December time bomb: once the special elections' winners are seated,
    their terms end in 2029, so the seats stop looking "up" and the Florida and
    Ohio Senate races - with their results - would have dropped off the site."""

    @classmethod
    def setUpClass(cls):
        cls.raw = sources.load_all(ROOT)
        cls.snapshot, cls.florida, cls.ohio = specials_seated(legislators.load_snapshot(ROOT))
        cls.profiles, _ = build_profiles(cls.raw, snapshot=cls.snapshot)

    def test_the_two_races_are_kept(self):
        contests = races.contestable(self.profiles, record=self.raw["record"])
        self.assertIn("S-FL-2026", contests)
        self.assertIn("S-OH-2026", contests)

    def test_their_filings_are_not_screened_out(self):
        from kyc import candidates
        field = candidates.load_cache(ROOT)
        screened = screen_field(field, self.profiles, self.raw["record"])
        phantom = {r.get("candidate_id") for r in screened["screened"]["phantom"]}
        senate = [r for r in field["candidates"] if r.get("office") == "S"
                  and r.get("state") in ("FL", "OH")]
        self.assertTrue(senate)
        self.assertFalse(phantom & {r["candidate_id"] for r in senate})

    def test_the_record_incumbent_is_up_and_the_new_senator_is_not(self):
        by_id = {p["id"]: p for p in self.profiles}
        self.assertTrue(by_id[self.ohio]["seatUp2026"])
        # The new senator joins the roster only through congress --apply; and
        # Florida's other senator, whose term runs to 2031, is not up.
        self.assertFalse((by_id.get("Z900001") or {}).get("seatUp2026"))
        florida = [p for p in self.profiles if not p["isCandidate"] and p["state"] == "FL"
                   and "Senate" in p["chamber"] and p["id"] != self.florida]
        self.assertTrue(florida and not any(p["seatUp2026"] for p in florida))

    def test_the_record_checks_stay_quiet(self):
        issues = validate.check_record(self.profiles, self.raw["record"], self.snapshot)
        self.assertEqual([i.code for i in issues], [])

    def test_a_seat_that_stops_being_up_for_no_reason_is_an_error(self):
        # Georgia's seat leaving today's set without its term ending is drift.
        odd = copy.deepcopy(self.snapshot)
        georgia = next(p for p in odd["legislators"] if p["chamber"] == "Senate"
                       and p["state"] == "GA" and p["termEnd"] == "2027-01-03")
        georgia["termEnd"] = "2031-01-03"
        profiles, _ = build_profiles(dict(self.raw, record=None), snapshot=odd)
        live = races.contestable(profiles)
        self.assertIn("S-GA-2026: in the record, not among today's seats",
                      record.drift(self.raw["record"], live, odd))


if __name__ == "__main__":
    unittest.main()
