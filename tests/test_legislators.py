"""Tests for reconciliation against the authoritative membership.

The rosters are accurate but cannot stay current on their own. These tests
cover the machinery that notices, because "the site quietly lists the wrong
person as your representative" is the failure this project cares about most
and the one least likely to announce itself.
"""

import csv
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import fec, legislators, overrides, sources, validate  # noqa: E402
from kyc.profiles import build_profiles  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def entry(bioguide="X000001", last="Smith", first="Pat", chamber="sen",
          state="TX", district=None, party="Republican",
          start="2025-01-03", end="2031-01-03", senate_class=1,
          birthday="1970-01-01", fec=None):
    """A raw congress-legislators record, in the shape the dataset uses."""
    term = {"type": chamber, "start": start, "end": end,
            "state": state, "party": party}
    if chamber == "sen":
        term["class"] = senate_class
    else:
        term["district"] = district if district is not None else 1
    return {
        "id": {"bioguide": bioguide, "fec": fec if fec is not None else []},
        "name": {"first": first, "last": last, "official_full": f"{first} {last}"},
        "bio": {"birthday": birthday},
        "terms": [term],
    }


def snapshot_of(*entries):
    return legislators.build_snapshot(list(entries), fetched="2026-09-08T00:00:00+00:00")


class TestTrim(unittest.TestCase):
    def test_keeps_the_current_term_not_the_first(self):
        person = entry()
        person["terms"].insert(0, {"type": "rep", "start": "2019-01-03",
                                   "end": "2021-01-03", "state": "TX",
                                   "district": 5, "party": "Republican"})
        trimmed = legislators.trim(person)
        self.assertEqual(trimmed["chamber"], "Senate")
        self.assertEqual(trimmed["termStart"], "2025-01-03")

    def test_house_records_carry_a_district(self):
        trimmed = legislators.trim(entry(chamber="rep", district=32))
        self.assertEqual(trimmed["district"], 32)
        self.assertIsNone(trimmed["senateClass"])

    def test_senate_records_carry_a_class_and_no_district(self):
        trimmed = legislators.trim(entry(chamber="sen", senate_class=2))
        self.assertEqual(trimmed["senateClass"], 2)
        self.assertIsNone(trimmed["district"])

    def test_an_entry_without_a_bioguide_is_dropped(self):
        person = entry()
        person["id"]["bioguide"] = None
        self.assertIsNone(legislators.trim(person))

    def test_an_entry_without_terms_is_dropped(self):
        person = entry()
        person["terms"] = []
        self.assertIsNone(legislators.trim(person))

    def test_name_falls_back_when_official_full_is_absent(self):
        self.assertEqual(
            legislators.full_name({"first": "Pat", "last": "Smith"}), "Pat Smith"
        )

    def test_fec_ids_are_scoped_to_the_current_chamber(self):
        # A senator who served in the House carries both. Attaching the old
        # House campaign's money to a Senate profile would be a plausible,
        # invisible error.
        senator = entry(chamber="sen", fec=["S8WA00194", "H2WA01054"])
        self.assertEqual(legislators.trim(senator)["fec"], ["S8WA00194"])
        rep = entry(chamber="rep", fec=["S8WA00194", "H2WA01054"])
        self.assertEqual(legislators.trim(rep)["fec"], ["H2WA01054"])

    def test_fec_ids_are_kept_when_none_match_the_chamber(self):
        # Dropping them would lose real information; a caller can still check.
        person = entry(chamber="sen", fec=["H2WA01054"])
        self.assertEqual(legislators.trim(person)["fec"], ["H2WA01054"])


class TestSnapshot(unittest.TestCase):
    def test_build_sorts_by_bioguide_so_diffs_stay_reviewable(self):
        snap = snapshot_of(entry(bioguide="Z000001"), entry(bioguide="A000001"))
        self.assertEqual([p["bioguide"] for p in snap["legislators"]],
                         ["A000001", "Z000001"])

    def test_build_refuses_an_empty_dataset(self):
        with self.assertRaises(legislators.LegislatorsError):
            legislators.build_snapshot([{"id": {}, "terms": []}])

    def test_round_trips_through_disk(self):
        snap = snapshot_of(entry())
        with tempfile.TemporaryDirectory() as tmp:
            legislators.save_snapshot(snap, tmp)
            self.assertEqual(legislators.load_snapshot(tmp), snap)

    def test_missing_snapshot_is_absence_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(legislators.load_snapshot(tmp))

    def test_corrupt_snapshot_is_absence_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(legislators.snapshot_path(tmp), "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertIsNone(legislators.load_snapshot(tmp))

    def test_age_in_days(self):
        snap = snapshot_of(entry())
        now = datetime.datetime(2026, 9, 18, tzinfo=datetime.timezone.utc)
        self.assertEqual(legislators.snapshot_age_days(snap, now), 10)

    def test_age_is_unknown_without_a_stamp(self):
        self.assertIsNone(legislators.snapshot_age_days({"legislators": []}))


class TestSeatsUp(unittest.TestCase):
    """Which Senate seats are on the 2026 ballot, from real term dates."""

    def test_the_regular_class_is_up(self):
        snap = snapshot_of(entry(bioguide="A", state="TX", end="2027-01-03"))
        self.assertEqual(legislators.seats_up_ids(snap, 2026), {"A"})

    def test_later_classes_are_not(self):
        snap = snapshot_of(
            entry(bioguide="B", state="CA", end="2029-01-03"),
            entry(bioguide="C", state="NY", end="2031-01-03"),
        )
        self.assertEqual(legislators.seats_up_ids(snap, 2026), set())

    def test_an_appointed_seat_ending_on_election_day_is_up(self):
        # Seats filled after a resignation end on election day itself, not in
        # the following January; a single-date test would miss them.
        snap = snapshot_of(entry(bioguide="D", state="OH", end="2026-11-03"))
        self.assertEqual(legislators.seats_up_ids(snap, 2026), {"D"})

    def test_a_term_ending_this_january_is_not_up_again(self):
        snap = snapshot_of(entry(bioguide="E", state="FL", end="2026-01-03"))
        self.assertEqual(legislators.seats_up_ids(snap, 2026), set())

    def test_house_members_are_not_senate_seats(self):
        snap = snapshot_of(entry(bioguide="F", chamber="rep", end="2027-01-03"))
        self.assertEqual(legislators.seats_up_ids(snap, 2026), set())

    def test_state_to_surname_shape_matches_the_curated_table(self):
        snap = snapshot_of(entry(bioguide="G", state="SC", last="Nordone",
                                 end="2027-01-03"))
        self.assertEqual(legislators.seats_up(snap, 2026), {"SC": "Nordone"})

    def test_term_end_year(self):
        snap = snapshot_of(entry(bioguide="H", end="2029-01-03"))
        self.assertEqual(legislators.term_end_year(snap, "h"), 2029)
        self.assertIsNone(legislators.term_end_year(snap, "NOPE"))


class TestReconcile(unittest.TestCase):
    def roster(self, **kwargs):
        row = {
            "Bioguide ID": "X000001", "Name": "Pat Smith", "Chamber": "Senate",
            "Party": "Republican", "State": "TX", "District": "",
            "Birthdate": "1970-01-01",
        }
        row.update(kwargs)
        return row

    def test_a_clean_roster_reports_no_drift(self):
        drift = legislators.reconcile([self.roster()], snapshot_of(entry()))
        self.assertTrue(drift.clean, drift.summary())
        self.assertEqual(drift.checked, 1)

    def test_a_newly_seated_member_is_missing(self):
        snap = snapshot_of(entry(bioguide="A"), entry(bioguide="B"))
        drift = legislators.reconcile([self.roster(**{"Bioguide ID": "A"})], snap)
        self.assertEqual([p["bioguide"] for p in drift.missing], ["B"])

    def test_someone_who_left_is_departed(self):
        snap = snapshot_of(entry(bioguide="A"))
        rows = [self.roster(**{"Bioguide ID": "A"}),
                self.roster(**{"Bioguide ID": "GONE", "Name": "Former Member"})]
        drift = legislators.reconcile(rows, snap)
        self.assertEqual([p["bioguide"] for p in drift.departed], ["GONE"])

    def test_a_party_switch_is_reported(self):
        drift = legislators.reconcile([self.roster(Party="Democrat")],
                                      snapshot_of(entry(party="Republican")))
        self.assertEqual([c["field"] for c in drift.changed], ["party"])

    def test_democrat_and_democratic_are_the_same_party(self):
        drift = legislators.reconcile([self.roster(Party="Democratic")],
                                      snapshot_of(entry(party="Democrat")))
        self.assertTrue(drift.clean)

    def test_a_vacant_row_is_not_a_party_disagreement(self):
        drift = legislators.reconcile([self.roster(Party="Vacant")],
                                      snapshot_of(entry(party="Republican")))
        self.assertEqual(drift.changed, [])

    def test_a_redistricting_is_reported(self):
        rows = [self.roster(Chamber="House", District="District 5")]
        snap = snapshot_of(entry(chamber="rep", district=7))
        drift = legislators.reconcile(rows, snap)
        self.assertEqual([c["field"] for c in drift.changed], ["district"])

    def test_district_spellings_are_normalised_before_comparing(self):
        # The roster says "District 7"; the dataset says 7.
        rows = [self.roster(Chamber="House", District="District 7")]
        drift = legislators.reconcile(rows, snapshot_of(entry(chamber="rep", district=7)))
        self.assertTrue(drift.clean, drift.changed)

    def test_a_missing_roster_value_is_a_gap_not_a_contradiction(self):
        # The provenance layer already reports absences; re-reporting them
        # here would bury the real disagreements.
        drift = legislators.reconcile([self.roster(Birthdate="")], snapshot_of(entry()))
        self.assertTrue(drift.clean)

    def test_a_wrong_birthdate_is_reported(self):
        drift = legislators.reconcile([self.roster(Birthdate="1980-05-05")],
                                      snapshot_of(entry(birthday="1970-01-01")))
        self.assertEqual([c["field"] for c in drift.changed], ["birthday"])


class TestApply(unittest.TestCase):
    HEADER = ["Bioguide ID", "Name", "Chamber", "Party", "State", "District",
              "Term Start", "Age", "Birthdate", "Education", "Estimated Net Worth",
              "Status"]

    def make_roster(self, tmp):
        path = os.path.join(tmp, "Cleaned_House_119th.csv")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.HEADER)
            writer.writeheader()
        return path

    def test_adds_a_row_with_only_sourced_fields(self):
        drift = legislators.Drift()
        drift.missing = [legislators.trim(
            entry(bioguide="B001328", first="Everton", last="Blair",
                  chamber="rep", state="GA", district=13, party="Democrat",
                  start="2026-09-01", birthday="1992-04-23")
        )]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_roster(tmp)
            added = legislators.apply_missing(drift, tmp,
                                              today=datetime.date(2026, 9, 8))
            with open(path, encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(added, {"Cleaned_House_119th.csv": ["Everton Blair"]})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["Bioguide ID"], "B001328")
        self.assertEqual(row["State"], "GA")
        self.assertEqual(row["District"], "District 13")
        self.assertEqual(row["Birthdate"], "1992-04-23")
        self.assertEqual(row["Age"], "34")
        self.assertEqual(row["Status"], "Active Member")
        # Editorial fields are left empty rather than invented.
        self.assertEqual(row["Education"], "")
        self.assertEqual(row["Estimated Net Worth"], "")

    def test_at_large_districts_use_the_roster_spelling(self):
        drift = legislators.Drift()
        drift.missing = [legislators.trim(
            entry(bioguide="A", chamber="rep", state="AK", district=0)
        )]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_roster(tmp)
            legislators.apply_missing(drift, tmp)
            with open(path, encoding="utf-8", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["District"], "At-Large")

    def test_nothing_to_add_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_roster(tmp)
            self.assertEqual(legislators.apply_missing(legislators.Drift(), tmp), {})

    def test_age_arithmetic(self):
        today = datetime.date(2026, 9, 8)
        self.assertEqual(legislators.age_on("1992-04-23", today), "34")
        # Birthday not yet reached this year.
        self.assertEqual(legislators.age_on("1992-12-31", today), "33")
        self.assertEqual(legislators.age_on("", today), "")
        self.assertEqual(legislators.age_on("not a date", today), "")


class TestAuthoritativeFecIds(unittest.TestCase):
    """Incumbent finance is looked up by id, not by name.

    The FEC files people under their legal name - Ashley Hinson appears as
    "ARENHOLZ, ASHLEY HINSON" - so the search has to match loosely, and a
    loose match that lands on the wrong person puts someone else's money on a
    profile with nothing looking out of place.
    """

    def test_ids_are_keyed_by_bioguide(self):
        snap = snapshot_of(entry(bioguide="A", chamber="sen", fec=["S1AA00001"]))
        self.assertEqual(fec.known_ids(snap), {"A": "S1AA00001"})

    def test_a_member_with_no_filed_id_is_absent(self):
        self.assertEqual(fec.known_ids(snapshot_of(entry(fec=[]))), {})

    def test_no_snapshot_means_no_shortcuts(self):
        self.assertEqual(fec.known_ids(None), {})

    def test_the_real_snapshot_covers_almost_everyone(self):
        snapshot = legislators.load_snapshot(ROOT)
        ids = fec.known_ids(snapshot)
        self.assertGreater(len(ids), 500)

    def test_every_id_is_scoped_to_the_seat_now_held(self):
        # A senator who served in the House carries both ids.
        snapshot = legislators.load_snapshot(ROOT)
        ids = fec.known_ids(snapshot)
        wrong = [
            (p["bioguide"], p["chamber"], ids[p["bioguide"]])
            for p in snapshot["legislators"]
            if p["bioguide"] in ids
            and not ids[p["bioguide"]].startswith("S" if p["chamber"] == "Senate" else "H")
        ]
        self.assertEqual(wrong, [])


class TestValidation(unittest.TestCase):
    def rows(self, bioguide="X000001"):
        return [{"Bioguide ID": bioguide, "Name": "Pat Smith", "Chamber": "Senate",
                 "Party": "Republican", "State": "TX", "District": "",
                 "Birthdate": "1970-01-01"}]

    def test_no_snapshot_is_a_warning_not_silence(self):
        issues = validate.check_snapshot([], {"members": []}, None)
        self.assertEqual([i.code for i in issues], ["no-snapshot"])
        self.assertEqual(issues[0].level, "warn")

    def test_a_missing_member_is_an_error(self):
        snap = snapshot_of(entry(bioguide="X000001"), entry(bioguide="NEW"))
        codes = [i.code for i in validate.check_snapshot([], {"members": self.rows()}, snap)]
        self.assertIn("missing-member", codes)

    def test_a_departed_member_is_an_error(self):
        snap = snapshot_of(entry(bioguide="OTHER"))
        issues = validate.check_snapshot([], {"members": self.rows()}, snap)
        codes = [i.code for i in issues]
        self.assertIn("departed-member", codes)
        self.assertIn("missing-member", codes)

    def test_an_already_excluded_member_is_not_reported_again(self):
        rows = self.rows()
        rows[0]["Name"] = sorted(overrides.EXCLUDED_MEMBERS)[0]
        snap = snapshot_of(entry(bioguide="OTHER"))
        codes = [i.code for i in validate.check_snapshot([], {"members": rows}, snap)]
        self.assertNotIn("departed-member", codes)

    def test_a_stale_snapshot_is_reported(self):
        snap = snapshot_of(entry(bioguide="X000001"))
        snap["fetched"] = "2020-01-01T00:00:00+00:00"
        codes = [i.code for i in validate.check_snapshot([], {"members": self.rows()}, snap)]
        self.assertIn("stale-snapshot", codes)


class TestAgainstTheRealSnapshot(unittest.TestCase):
    """The committed snapshot and the committed rosters must agree."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = legislators.load_snapshot(ROOT)
        cls.raw = sources.load_all(ROOT)

    def test_the_snapshot_is_committed(self):
        self.assertIsNotNone(self.snapshot, "run: python build_profile_site.py congress")

    def test_the_roster_matches_the_authoritative_membership(self):
        drift = legislators.reconcile(self.raw["members"], self.snapshot)
        self.assertEqual(drift.missing, [], "people serving but absent from the roster")
        self.assertEqual(drift.changed, [], "roster fields that disagree")

    def test_the_snapshot_holds_a_whole_congress(self):
        senate = [p for p in self.snapshot["legislators"] if p["chamber"] == "Senate"]
        self.assertEqual(len(senate), 100)

    def test_thirty_five_senate_seats_are_on_the_2026_ballot(self):
        self.assertEqual(len(legislators.seats_up_ids(self.snapshot, 2026)), 35)

    def test_the_derived_and_curated_senate_tables_cover_the_same_states(self):
        derived = legislators.seats_up(self.snapshot, 2026)
        self.assertEqual(set(derived), set(overrides.SENATE_SEATS_UP_2026))

    def test_building_with_the_snapshot_changes_nothing_today(self):
        # The curated table and the real term dates agree right now, so this
        # is a safe swap; the point is that the snapshot keeps agreeing after
        # a seat changes hands and the hand-typed surname stops being right.
        without, _ = build_profiles(self.raw)
        with_snap, _ = build_profiles(self.raw, snapshot=self.snapshot)
        up = lambda ps: sorted(
            p["id"] for p in ps
            if not p["isCandidate"] and "Senate" in p["chamber"] and p["seatUp2026"]
        )
        self.assertEqual(up(without), up(with_snap))

    def test_every_senator_has_a_term_end_year(self):
        profiles, _ = build_profiles(self.raw, snapshot=self.snapshot)
        senators = [p for p in profiles
                    if not p["isCandidate"] and "Senate" in p["chamber"]]
        self.assertTrue(all(p["termEndYear"] for p in senators))

    def test_the_snapshot_is_json_and_sorted(self):
        with open(legislators.snapshot_path(ROOT), encoding="utf-8") as handle:
            raw = json.load(handle)
        ids = [p["bioguide"] for p in raw["legislators"]]
        self.assertEqual(ids, sorted(ids))


if __name__ == "__main__":
    unittest.main()
