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

    def test_the_snapshot_keeps_every_fec_id_both_chambers(self):
        # fecAll holds ids for both chambers where the source lists them.
        by_id = legislators.by_bioguide(self.snapshot)
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

    def test_todays_seats_are_the_records(self):
        # Allowing only a seat whose appointee's term has ended (record.drift),
        # so this stays true once the specials are seated.
        profiles, _ = build_profiles(dict(self.raw, record=None), snapshot=self.snapshot)
        self.assertEqual(record.drift(self.record, record.live_races(profiles, self.snapshot),
                                      self.snapshot), [])

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


def specials_seated(raw, snapshot):
    """The roster and membership as they will read once the Florida and Ohio
    special elections' winners are seated: a fictional senator (Z900001) in
    the Florida appointee's place, her roster row gone, and Ohio's appointee
    re-seated for the term to 2029. Found through the record's bioguide ids,
    so it holds whatever today's snapshot already shows. Never committed."""
    held = raw["record"]["incumbents"]
    florida, ohio = held["S-FL-2026"]["bioguide"], held["S-OH-2026"]["bioguide"]
    after = copy.deepcopy(snapshot)
    people = [p for p in after["legislators"] if p["bioguide"] != florida]
    if not any(p["bioguide"] == "Z900001" for p in people):
        people.append({"bioguide": "Z900001", "name": "Zora Example", "last": "Example",
                       "nameParts": {"first": "Zora", "last": "Example"}, "chamber": "Senate",
                       "state": "FL", "district": None, "party": "Independent",
                       "termStart": "2026-12-08", "termEnd": "2029-01-03", "senateClass": 3,
                       "fec": [], "fecAll": [], "how": None, "endType": None})
    for person in people:
        if person["bioguide"] == ohio:
            person.update(termStart="2026-12-08", termEnd="2029-01-03", how=None, endType=None)
    after["legislators"] = people
    after["fetched"] = "2026-12-09T07:20:00+00:00"
    roster = dict(raw, members=[r for r in raw["members"]
                                if (r.get("Bioguide ID") or "").upper() != florida])
    return roster, after, florida, ohio


class TestTheSpecialsSeated(unittest.TestCase):
    """The December time bomb: once the special elections' winners are seated,
    their terms end in 2029, so the seats stop looking "up" and the Florida and
    Ohio Senate races - with their results - would have dropped off the site."""

    @classmethod
    def setUpClass(cls):
        raw = sources.load_all(ROOT)
        cls.record = raw["record"]
        cls.raw, cls.snapshot, cls.florida, cls.ohio = specials_seated(
            raw, legislators.load_snapshot(ROOT))
        cls.profiles, _ = build_profiles(cls.raw, snapshot=cls.snapshot)

    def test_the_two_races_are_kept_as_specials(self):
        built = {r["id"]: r for r in races.build(self.profiles, record=self.record)}
        for rid in ("S-FL-2026", "S-OH-2026"):
            self.assertIn(rid, built)
            self.assertTrue(built[rid]["special"])
        self.assertIn(self.ohio, built["S-OH-2026"]["incumbentIds"])

    def test_their_filings_are_not_screened_out(self):
        from kyc import candidates
        field = candidates.load_cache(ROOT)
        screened = screen_field(field, self.profiles, self.record)
        phantom = {r.get("candidate_id") for r in screened["screened"]["phantom"]}
        senate = [r for r in field["candidates"] if r.get("office") == "S"
                  and r.get("state") in ("FL", "OH")]
        self.assertTrue(senate)
        self.assertFalse(phantom & {r["candidate_id"] for r in senate})

    def test_the_reseated_incumbent_keeps_the_race_and_the_new_term(self):
        ohio = next(p for p in self.profiles if p["id"] == self.ohio)
        self.assertTrue(ohio["seatUp2026"])
        self.assertEqual(ohio["termEndYear"], 2029)
        self.assertTrue(ohio["term_start"].endswith("2029-01-03"), ohio["term_start"])
        # Florida's other senator, whose term runs to 2031, is not up.
        florida = [p for p in self.profiles if not p["isCandidate"] and p["state"] == "FL"
                   and "Senate" in p["chamber"]]
        self.assertTrue(florida and not any(p["seatUp2026"] for p in florida))

    def test_the_record_checks_stay_quiet_once_the_term_has_ended(self):
        issues = validate.check_record(self.profiles, self.record, self.snapshot)
        self.assertEqual([i.code for i in issues], [])

    def test_an_incumbent_gone_before_the_term_ended_is_an_error(self):
        early = dict(self.snapshot, fetched="2026-10-20T07:20:00+00:00")
        early["legislators"] = [p for p in self.snapshot["legislators"]
                                if p["bioguide"] != "Z900001"]
        codes = [i.code for i in validate.check_record(self.profiles, self.record, early)]
        self.assertIn("unmatched-senate-seat", codes)

    def test_drift_allows_only_an_ended_term(self):
        live = record.race_ids(self.record) - {"S-FL-2026"}
        self.assertEqual(record.drift(self.record, live, self.snapshot), [])
        early = dict(self.snapshot, fetched="2026-10-01T07:20:00+00:00")
        self.assertEqual(record.drift(self.record, live, early),
                         ["S-FL-2026: in the record, not among today's seats"])


class TestTheSpecialsSeatedThroughApply(unittest.TestCase):
    """The December refresh end to end, on copies of the committed rosters:
    the specials' membership, what `congress --apply` does with it, then the
    build's own checks. Florida's appointee leaves by the term the previous
    snapshot gave her, with no name list and no hand edit."""

    @classmethod
    def setUpClass(cls):
        import shutil

        cls.raw = sources.load_all(ROOT)
        _, cls.after, cls.florida, cls.ohio = specials_seated(
            cls.raw, legislators.load_snapshot(ROOT))
        if cls.florida not in legislators.roster_ids(cls.raw["members"]):
            raise unittest.SkipTest("Florida's appointee has left the committed roster: "
                                    "what this rehearses has happened")
        # legislators-historical as it will read once she has left: her last
        # day is the day her successor was seated, not the special election.
        historical = [{"id": {"bioguide": cls.florida},
                       "terms": [{"start": "2025-01-21", "end": "2026-12-08"}]}]
        with tempfile.TemporaryDirectory() as tmp:
            for name in sources.MEMBER_ROSTERS + (sources.FORMER_ROSTER,):
                shutil.copy(os.path.join(ROOT, name), tmp)
            rows = sources.load_rosters(sources.MEMBER_ROSTERS, tmp)[0]
            absent = legislators.roster_ids(rows) - set(legislators.by_bioguide(cls.after))
            ended = legislators.departures(absent, cls.after, historical=historical)
            cls.drift = legislators.reconcile(rows, cls.after, ended=ended)
            legislators.apply(cls.drift, tmp, today=datetime.date(2026, 12, 9))
            cls.members = sources.load_rosters(sources.MEMBER_ROSTERS, tmp)[0]
            cls.former = sources.read_csv(os.path.join(tmp, sources.FORMER_ROSTER))

    def test_the_appointee_leaves_on_the_day_the_record_gives(self):
        self.assertEqual([(p["bioguide"], p["via"]) for p in self.drift.expected],
                         [(self.florida, "legislators-historical")])
        self.assertEqual(self.drift.departed, [])
        self.assertEqual([(r["Bioguide ID"], r["Left Office"], r["Last Congress"])
                          for r in self.former], [(self.florida, "2026-12-08", "119")])

    def test_the_winners_are_written_in(self):
        ids = {r["Bioguide ID"] for r in self.members}
        self.assertIn("Z900001", ids)
        self.assertNotIn(self.florida, ids)
        ohio = next(r for r in self.members if r["Bioguide ID"] == self.ohio)
        # Renewed to the fixture's term - unless the committed roster already
        # holds a later one, once the real winner has been seated.
        was = next(r for r in self.raw["members"] if r["Bioguide ID"] == self.ohio)
        self.assertEqual(ohio["Term Start"], max(was["Term Start"], "2026-12-08"))
        self.assertEqual(ohio["Term End Date"], "2029-01-03")

    def test_the_build_finds_nothing_wrong(self):
        roster = dict(self.raw, members=self.members)
        when = datetime.datetime(2026, 12, 9, 8)
        errors = [i.code for i in validate.check_snapshot([], roster, self.after, now=when)
                  if i.level == "error"]
        self.assertEqual(errors, [])
        profiles, _ = build_profiles(roster, snapshot=self.after)
        self.assertEqual([i.code for i in validate.check_record(
            profiles, self.raw["record"], self.after)], [])
        ohio = next(p for p in profiles if p["id"] == self.ohio)
        self.assertEqual(ohio["term_start"], "2026-12-08 - 2029-01-03")


class TestRecordDrift(unittest.TestCase):
    """The drift check reads today's Senate seats from the snapshot, so it is
    never the record compared with itself."""

    @classmethod
    def setUpClass(cls):
        cls.raw = sources.load_all(ROOT)
        cls.record = cls.raw["record"]
        cls.snapshot = legislators.load_snapshot(ROOT)

    def codes(self, snapshot):
        profiles, _ = build_profiles(self.raw, snapshot=snapshot)
        return [i.code for i in validate.check_record(profiles, self.record, snapshot)]

    def test_a_seat_that_stops_being_up_for_no_reason_is_an_error(self):
        odd = copy.deepcopy(self.snapshot)
        georgia = next(p for p in odd["legislators"] if p["chamber"] == "Senate"
                       and p["state"] == "GA" and p["termEnd"] == "2027-01-03")
        georgia["termEnd"] = "2031-01-03"
        self.assertIn("record-drift", self.codes(odd))

    def test_a_new_special_the_record_lacks_is_an_error(self):
        odd = copy.deepcopy(self.snapshot)
        california = next(p for p in odd["legislators"] if p["chamber"] == "Senate"
                          and p["state"] == "CA")
        california["termEnd"] = "2026-11-03"
        self.assertIn("record-drift", self.codes(odd))

    def test_a_successor_in_a_record_seat_is_no_unseated_incumbent(self):
        # An early resignation and an appointee: the seat is still on the
        # ballot, and the departure is the roster's business.
        odd = copy.deepcopy(self.snapshot)
        georgia = next(p for p in odd["legislators"] if p["chamber"] == "Senate"
                       and p["state"] == "GA" and p["termEnd"] == "2027-01-03")
        odd["legislators"].remove(georgia)
        odd["legislators"].append(dict(georgia, bioguide="Z900002", name="Gale Example",
                                       termStart="2026-12-01", how="appointment"))
        roster = dict(self.raw, members=[r for r in self.raw["members"] if (
            r.get("Bioguide ID") or "").upper() != georgia["bioguide"]])
        profiles, _ = build_profiles(roster, snapshot=odd)
        codes = [i.code for i in validate.check_record(profiles, self.record, odd)]
        self.assertNotIn("unmatched-senate-seat", codes)
        self.assertNotIn("record-drift", codes)


if __name__ == "__main__":
    unittest.main()
