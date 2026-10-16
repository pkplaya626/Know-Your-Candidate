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

    def test_no_other_chambers_ids_stand_in_for_this_one(self):
        # A senator with only a House id has no Senate filing to look up:
        # the House id would put their House money on a Senate profile
        # (rule 20). It is kept among every id, for links.
        trimmed = legislators.trim(entry(chamber="sen", fec=["H2WA01054"]))
        self.assertEqual(trimmed["fec"], [])
        self.assertEqual(trimmed["fecAll"], ["H2WA01054"])

    def test_an_evidenced_id_congress_legislators_lacks_is_added(self):
        # Ashley Hinson's Senate filing, under her legal name (overrides).
        bioguide, (filing, _why) = next(iter(overrides.MEMBER_FEC_IDS.items()))
        trimmed = legislators.trim(entry(bioguide=bioguide, chamber="sen",
                                         fec=["H0IA01174"]))
        self.assertIn(filing, trimmed["fecAll"])
        self.assertEqual(trimmed["fec"], [filing])


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
              "Term Start", "Age", "Birthdate", "Education", "Previous Professions",
              "Status"]

    def make_roster(self, tmp):
        path = os.path.join(tmp, "Cleaned_House.csv")
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
            report = legislators.apply(drift, tmp, today=datetime.date(2026, 9, 8))
            with open(path, encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(report["added"], {"Cleaned_House.csv": ["Everton Blair"]})
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
        self.assertEqual(row["Previous Professions"], "")

    def test_at_large_districts_use_the_roster_spelling(self):
        drift = legislators.Drift()
        drift.missing = [legislators.trim(
            entry(bioguide="A", chamber="rep", state="AK", district=0)
        )]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_roster(tmp)
            legislators.apply(drift, tmp)
            with open(path, encoding="utf-8", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["District"], "At-Large")

    def test_nothing_to_add_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_roster(tmp)
            self.assertEqual(legislators.apply(legislators.Drift(), tmp),
                             {"added": {}, "reseated": {}, "archived": []})

    FULL = ["Bioguide ID", "Name", "Chamber", "Party", "State", "District", "Term Start",
            "Age", "Birthdate", "Education", "Committee Assignments", "Term End Date",
            "Status"]

    @staticmethod
    def write(tmp, name, rows):
        with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TestApply.FULL)
            writer.writeheader()
            writer.writerows(rows)

    def read(self, tmp, name):
        path = os.path.join(tmp, name)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def raw(tmp, name):
        with open(os.path.join(tmp, name), "rb") as handle:
            return handle.read()

    def member(self, bioguide="X000001", **kwargs):
        row = dict.fromkeys(self.FULL, "")
        row.update({"Bioguide ID": bioguide, "Name": "Pat Smith", "Chamber": "House",
                    "Party": "Republican", "State": "TX", "District": "District 5",
                    "Term Start": "2025-01-03", "Birthdate": "1970-01-01",
                    "Education": "BA, Rice University",
                    "Committee Assignments": "House Committee on Agriculture",
                    "Term End Date": "2027-01-03", "Status": "Retiring in 2026"})
        row.update(kwargs)
        return row

    def rosters(self, tmp, house=(), senate=()):
        self.write(tmp, "Cleaned_House.csv", list(house))
        self.write(tmp, "Cleaned_Senate.csv", list(senate))

    def drift_of(self, tmp, snap, ended=None):
        rows = sources.load_rosters(sources.MEMBER_ROSTERS, tmp)[0]
        return legislators.reconcile(rows, snap, ended=ended)

    def test_a_new_term_rewrites_the_seat_and_keeps_the_person(self):
        snap = snapshot_of(entry(chamber="rep", district=5, start="2027-01-03",
                                 end="2029-01-03"))
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp, house=[self.member()])
            report = legislators.apply(self.drift_of(tmp, snap), tmp)
            row, = self.read(tmp, "Cleaned_House.csv")
        self.assertEqual(report["reseated"], {"Cleaned_House.csv": ["Pat Smith"]})
        self.assertEqual((row["Term Start"], row["Term End Date"]), ("2027-01-03", "2029-01-03"))
        # The status note was about the term that ended.
        self.assertEqual(row["Status"], "Active Member")
        self.assertEqual(row["Education"], "BA, Rice University")
        self.assertEqual(row["Committee Assignments"], "House Committee on Agriculture")

    def test_a_move_to_the_senate_moves_the_row_and_clears_its_committees(self):
        snap = snapshot_of(entry(chamber="sen", state="TX", start="2027-01-03",
                                 end="2033-01-03", senate_class=2))
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp, house=[self.member()])
            legislators.apply(self.drift_of(tmp, snap), tmp)
            house, senate = self.read(tmp, "Cleaned_House.csv"), self.read(tmp, "Cleaned_Senate.csv")
        self.assertEqual(house, [])
        row, = senate
        self.assertEqual((row["Chamber"], row["District"], row["Term Start"]),
                         ("Senate", "", "2027-01-03"))
        # They described the House seat.
        self.assertEqual(row["Committee Assignments"], "")
        self.assertEqual(row["Education"], "BA, Rice University")

    def test_a_moved_row_is_written_into_its_new_file_first(self):
        # Interrupted between the two writes, the member is in both files
        # (member-twice, which the next run finishes), never in neither.
        snap = snapshot_of(entry(chamber="sen", state="TX", start="2027-01-03",
                                 end="2033-01-03", senate_class=2))
        order, write = [], legislators._write_rows
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp, house=[self.member()])
            drift = self.drift_of(tmp, snap)
            legislators._write_rows = lambda path, *a: (order.append(os.path.basename(path)),
                                                        write(path, *a))
            try:
                legislators.apply(drift, tmp)
            finally:
                legislators._write_rows = write
        self.assertEqual(order, ["Cleaned_Senate.csv", "Cleaned_House.csv"])

    def test_a_member_the_records_say_left_is_archived_whole(self):
        snap = snapshot_of(entry(bioguide="STAYS", chamber="rep", district=6))
        ended = {"X000001": {"left": "2027-01-03", "via": "legislators-historical"}}
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp, house=[self.member(), self.member("STAYS", District="District 6")])
            report = legislators.apply(self.drift_of(tmp, snap, ended), tmp)
            house = self.read(tmp, "Cleaned_House.csv")
            former = self.read(tmp, legislators.FORMER_ROSTER)
        self.assertEqual(report["archived"], ["Pat Smith"])
        self.assertEqual([r["Bioguide ID"] for r in house], ["STAYS"])
        row, = former
        self.assertEqual((row["Left Office"], row["Left Via"], row["Last Congress"]),
                         ("2027-01-03", "legislators-historical", "119"))
        self.assertEqual(row["Education"], "BA, Rice University")

    def test_a_departure_with_no_record_is_left_for_somebody_to_see(self):
        snap = snapshot_of(entry(bioguide="STAYS", chamber="rep", district=6))
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp, house=[self.member()])
            drift = self.drift_of(tmp, snap)
            report = legislators.apply(drift, tmp)
            house = self.read(tmp, "Cleaned_House.csv")
            former = self.read(tmp, legislators.FORMER_ROSTER)
        self.assertEqual([p["bioguide"] for p in drift.departed], ["X000001"])
        self.assertEqual(report["archived"], [])
        self.assertEqual([r["Bioguide ID"] for r in house], ["X000001", "STAYS"])
        self.assertEqual(former, [])

    def test_new_rows_hold_only_what_the_source_knows(self):
        snap = snapshot_of(entry(bioguide="NEW", chamber="rep", district=9,
                                 start="2027-01-03", end="2029-01-03"))
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp)
            legislators.apply(self.drift_of(tmp, snap), tmp)
            row, = self.read(tmp, "Cleaned_House.csv")
        self.assertEqual({k for k, v in row.items() if v} - set(legislators.WRITABLE), {"Age"})

    def test_running_it_twice_changes_nothing(self):
        snap = snapshot_of(
            entry(bioguide="X000001", chamber="rep", district=5, start="2027-01-03",
                  end="2029-01-03"),
            entry(bioguide="MOVER", chamber="sen", start="2027-01-03", end="2033-01-03",
                  senate_class=2),
            entry(bioguide="NEW", chamber="rep", district=7, start="2027-01-03",
                  end="2029-01-03"))
        ended = {"GONE": {"left": "2027-01-03", "via": "legislators-historical"}}
        with tempfile.TemporaryDirectory() as tmp:
            self.rosters(tmp, house=[self.member(), self.member("MOVER", District="District 6"),
                                     self.member("GONE", District="District 7")])
            legislators.apply(self.drift_of(tmp, snap, ended), tmp)
            names = ("Cleaned_House.csv", "Cleaned_Senate.csv", legislators.FORMER_ROSTER)
            first = [self.raw(tmp, n) for n in names]
            again = self.drift_of(tmp, snap, ended)
            report = legislators.apply(again, tmp)
            second = [self.raw(tmp, n) for n in names]
        self.assertTrue(again.clean, again.summary())
        self.assertEqual(report, {"added": {}, "reseated": {}, "archived": []})
        self.assertEqual(first, second)

    def test_age_arithmetic(self):
        today = datetime.date(2026, 9, 8)
        self.assertEqual(legislators.age_on("1992-04-23", today), "34")
        # Birthday not yet reached this year.
        self.assertEqual(legislators.age_on("1992-12-31", today), "33")
        self.assertEqual(legislators.age_on("", today), "")
        self.assertEqual(legislators.age_on("not a date", today), "")


def roster_row(bioguide="X000001", **kwargs):
    row = {"Bioguide ID": bioguide, "Name": f"Member {bioguide}", "Chamber": "House",
           "Party": "Republican", "State": "TX", "District": "District 5",
           "Birthdate": "1970-01-01", "Term Start": "2025-01-03"}
    row.update(kwargs)
    return row


class TestDepartures(unittest.TestCase):
    """Who has left is decided by bioguide id from Congress's own records -
    never from a list of names (the one that stood in overrides matched on
    them, rule 17), and never from an absence alone (rule 16)."""

    def setUp(self):
        self.now = snapshot_of(entry(bioguide="STAYS"))
        self.now["fetched"] = "2027-01-04T07:20:00+00:00"

    def historical(self, bioguide, end):
        return [{"id": {"bioguide": bioguide},
                 "terms": [{"start": "2025-01-03", "end": end}]}]

    def test_a_resignation_legislators_historical_lists_is_expected(self):
        out = legislators.departures({"GONE"}, self.now,
                                     historical=self.historical("GONE", "2026-11-14"))
        self.assertEqual(out, {"GONE": {"left": "2026-11-14", "via": "legislators-historical"}})

    def test_the_day_a_term_ends_counts(self):
        self.now["fetched"] = "2027-01-03T23:00:00+00:00"
        self.assertIn("GONE", legislators.departures(
            {"GONE"}, self.now, historical=self.historical("GONE", "2027-01-03")))

    def test_a_term_that_has_ended_is_not_evidence_on_its_own(self):
        # On January 3 every House term has ended. A current file that
        # dropped somebody by mistake, with a historical file read that does
        # not list them, must leave them departed: an error, not an archive.
        self.assertEqual(legislators.departures({"GONE"}, self.now, historical=[]), {})

    def test_no_historical_file_archives_nobody(self):
        # A failed download concludes nothing (rule 8).
        self.assertEqual(legislators.departures({"GONE"}, self.now, historical=None), {})

    def test_an_appointee_leaves_on_the_day_the_record_gives(self):
        # Not the special election's date: they serve until the winner is
        # seated, and legislators-historical records that day.
        out = legislators.departures({"GONE"}, self.now,
                                     historical=self.historical("GONE", "2026-12-08"))
        self.assertEqual(out["GONE"]["left"], "2026-12-08")

    def test_a_record_of_a_term_still_running_is_not(self):
        # Listed as historical with a term ending in 2029: an upstream fault.
        out = legislators.departures({"GONE"}, self.now,
                                     historical=self.historical("GONE", "2029-01-03"))
        self.assertEqual(out, {})

    def test_reconcile_tells_the_expected_from_the_departed(self):
        rows = [roster_row("STAYS", Chamber="Senate", District=""),
                roster_row("GONE"), roster_row("LOST")]
        ended = {"GONE": {"left": "2027-01-03", "via": "legislators-historical"}}
        drift = legislators.reconcile(rows, self.now, ended=ended)
        self.assertEqual([p["bioguide"] for p in drift.expected], ["GONE"])
        self.assertEqual(drift.expected[0]["left"], "2027-01-03")
        self.assertEqual([p["bioguide"] for p in drift.departed], ["LOST"])

    def test_the_build_calls_every_absence_departed(self):
        # The build has no previous snapshot to ask: `congress --apply`
        # archives the expected ones before it runs.
        rows = [roster_row("STAYS", Chamber="Senate", District=""), roster_row("GONE")]
        codes = [i.code for i in validate.check_snapshot(
            [], {"members": rows}, self.now, now=datetime.datetime(2027, 1, 4))]
        self.assertIn("departed-member", codes)


class TestNewTerms(unittest.TestCase):
    """On January 3 every re-elected member starts a new term. The roster's
    Term Start is the old one, and the seat columns of a representative
    elected to the Senate, or seated in a renumbered district, are the old
    seat's: ``reseated``, for ``congress --apply`` to write."""

    def reseat(self, row, **term):
        term.setdefault("start", "2027-01-03")
        term.setdefault("end", "2029-01-03")
        return legislators.reconcile([row], snapshot_of(entry(**term)))

    def test_a_reelected_member_is_reseated_and_nothing_else(self):
        drift = self.reseat(roster_row(), chamber="rep", district=5)
        self.assertEqual([(s["bioguide"], s["moved"]) for s in drift.reseated],
                         [("X000001", [])])
        self.assertEqual(drift.changed, [])

    def test_a_representative_elected_to_the_senate(self):
        drift = self.reseat(roster_row(), chamber="sen", end="2033-01-03", senate_class=2)
        self.assertEqual([c["field"] for c in drift.reseated[0]["moved"]], ["chamber"])
        self.assertEqual(drift.changed, [])

    def test_a_renumbered_district(self):
        drift = self.reseat(roster_row(), chamber="rep", district=7)
        self.assertEqual([c["field"] for c in drift.reseated[0]["moved"]], ["district"])

    def test_the_same_change_inside_a_term_is_a_disagreement(self):
        drift = self.reseat(roster_row(), chamber="rep", district=7, start="2025-01-03",
                            end="2027-01-03")
        self.assertEqual(drift.reseated, [])
        self.assertEqual([c["field"] for c in drift.changed], ["district"])

    def test_a_new_term_never_changes_a_party(self):
        drift = self.reseat(roster_row(), chamber="rep", district=5, party="Democrat")
        self.assertEqual([c["field"] for c in drift.changed], ["party"])
        self.assertEqual(drift.reseated[0]["moved"], [])

    def test_puerto_ricos_second_congress_is_not_a_new_term(self):
        # congress-legislators records the four-year term one Congress at a
        # time; it began in 2025 and ends in 2029 (48 U.S.C. 891).
        row = roster_row(State="PR", District="At-Large")
        self.assertEqual(self.reseat(row, chamber="rep", state="PR", district=0).reseated, [])
        later = self.reseat(row, chamber="rep", state="PR", district=0, start="2029-01-03",
                            end="2031-01-03")
        self.assertEqual(len(later.reseated), 1)

    def test_one_person_on_two_rows_is_an_error(self):
        rows = [roster_row(), roster_row(Chamber="Senate", District="")]
        snap = snapshot_of(entry(chamber="rep", district=5))
        self.assertEqual(legislators.reconcile(rows, snap).twice, ["Member X000001 (X000001)"])
        codes = [i.code for i in validate.check_snapshot([], {"members": rows}, snap)]
        self.assertIn("member-twice", codes)

    def test_a_seat_not_yet_written_is_an_error_and_a_date_a_warning(self):
        def issues(**term):
            snap = snapshot_of(entry(start="2027-01-03", end="2029-01-03", **term))
            return {i.code: i.level for i in validate.check_snapshot(
                [], {"members": [roster_row()]}, snap, now=datetime.datetime(2027, 1, 4))}
        self.assertEqual(issues(chamber="rep", district=7).get("roster-disagrees"), "error")
        found = issues(chamber="rep", district=5)
        self.assertEqual(found.get("term-not-renewed"), "warn")
        self.assertNotIn("roster-disagrees", found)


class TestTermDates(unittest.TestCase):
    """The term on a profile is the one the snapshot says is being served."""

    def term(self, row, **term):
        snap = snapshot_of(entry(**term))
        profiles, _ = build_profiles({"members": [row], "candidates": []}, snapshot=snap)
        return profiles[0]

    def test_a_reelected_representative_reads_the_new_term(self):
        # Not the roster's 2025 start against a 2029 end: a four-year House term.
        found = self.term(roster_row(), chamber="rep", district=5, start="2027-01-03",
                          end="2029-01-03")
        self.assertEqual((found["term_start"], found["termEndYear"]),
                         ("2027-01-03 - 2029-01-03", 2029))

    def test_an_appointees_term_ends_at_the_special_election(self):
        raw = entry(chamber="sen", start="2025-01-21", end="2026-11-03", senate_class=3)
        raw["terms"][-1].update({"how": "appointment", "end-type": "special-election"})
        snap = legislators.build_snapshot([raw], fetched="2026-10-16T00:00:00+00:00")
        row = roster_row(Chamber="Senate", District="", **{"Term Start": "2025-01-21"})
        profiles, _ = build_profiles({"members": [row], "candidates": []}, snapshot=snap)
        self.assertEqual(profiles[0]["term_start"], "2025-01-21 - 2026-11-03 (special election)")

    def test_puerto_ricos_term_is_the_statutes(self):
        found = self.term(roster_row(State="PR", District="At-Large"), chamber="rep",
                          state="PR", district=0, start="2025-01-03", end="2027-01-03")
        self.assertEqual((found["term_start"], found["termEndYear"]),
                         ("2025-01-03 - 2029-01-03", 2029))


class TestANewCongress(unittest.TestCase):
    """What January 3 changes about a member who stays: their committee
    seats and their 2026 status note were the old Congress's."""

    def build(self, start, committees=None, **row):
        snap = snapshot_of(entry(chamber="rep", district=5, start=start,
                                 end="2029-01-03" if start >= "2027" else "2027-01-03"))
        base = roster_row(**{"Committee Assignments": "House Committee on Agriculture"})
        base.update(row)
        profiles, _ = build_profiles({"members": [base], "candidates": []}, snapshot=snap,
                                     committees=committees)
        return profiles[0]

    def test_the_old_congresss_committees_are_not_shown_as_current(self):
        found = self.build("2027-01-03")
        self.assertEqual(found["committeesPending"], 120)
        self.assertEqual(found["committees"], "No data")
        # While the 119th sits, the roster's column is shown.
        self.assertNotIn("committeesPending", self.build("2025-01-03"))

    def test_rosters_of_people_who_left_are_a_previous_congresss(self):
        snap = snapshot_of(entry(bioguide="STAYS"))
        fresh = {"members": {"STAYS": [{"code": "HSAG"}]}, "committees": {}}
        stale = {"members": {"STAYS": [{"code": "HSAG"}], "GONE1": [], "GONE2": []},
                 "committees": {}}
        self.assertIs(legislators.committees_current(fresh, snap), fresh)
        self.assertIsNone(legislators.committees_current(stale, snap))
        self.assertIsNone(legislators.committees_current({"members": {}}, snap))

    def test_a_2026_status_note_does_not_outlive_the_term(self):
        overrides.MEMBER_STATUS_BY_ID["X000001"] = ("Retiring in 2026", "a test")
        try:
            noted = self.build("2025-01-03")
            renewed = self.build("2027-01-03")
        finally:
            del overrides.MEMBER_STATUS_BY_ID["X000001"]
        self.assertEqual(noted["status"], "Retiring in 2026")
        self.assertFalse(noted["seekingReelection2026"])
        self.assertEqual(renewed["status"], "Active Member")

    def test_the_summary_names_the_congress_from_the_terms(self):
        from kyc import summary

        snap = snapshot_of(entry(chamber="rep", district=5, start="2027-01-03",
                                 end="2029-01-03"))
        self.assertEqual(summary.build([], snapshot=snap)["congress"], 120)
        self.assertIsNone(summary.build([])["congress"])


class TestOneRowPerPerson(unittest.TestCase):
    """Members were deduplicated on their seat. A member whose row still
    carried an old district number and a newcomer seated at that number
    shared a key, and one of them vanished from the site with nothing said."""

    def test_a_stale_district_and_a_newcomer_both_survive(self):
        from kyc.profiles import _dedup_members

        rows = [roster_row("OLD"), roster_row("NEW")]
        self.assertEqual(len(_dedup_members(rows)), 2)

    def test_a_vacant_seat_still_keys_on_the_seat(self):
        from kyc.profiles import _dedup_members

        rows = [roster_row("", Name="Vacant"), roster_row("", Name="Vacant")]
        self.assertEqual(len(_dedup_members(rows)), 1)

    def test_the_collision_is_loud_until_apply_writes_the_new_term(self):
        snap = snapshot_of(entry(bioguide="OLD", chamber="rep", district=7,
                                 start="2027-01-03", end="2029-01-03"),
                           entry(bioguide="NEW", chamber="rep", district=5,
                                 start="2027-01-03", end="2029-01-03"))
        snap["fetched"] = "2027-01-04T07:20:00+00:00"
        rows = [roster_row("OLD"), roster_row("NEW", **{"Term Start": "2027-01-03"})]
        before = [i.code for i in validate.check_snapshot(
            [], {"members": rows}, snap, now=datetime.datetime(2027, 1, 4))]
        self.assertIn("roster-disagrees", before)
        drift = legislators.reconcile(rows, snap)
        with tempfile.TemporaryDirectory() as tmp:
            TestApply.write(tmp, "Cleaned_House.csv",
                            [dict(dict.fromkeys(TestApply.FULL, ""), **r) for r in rows])
            TestApply.write(tmp, "Cleaned_Senate.csv", [])
            legislators.apply(drift, tmp)
            after = sources.load_rosters(sources.MEMBER_ROSTERS, tmp)[0]
        codes = [i.code for i in validate.check_snapshot(
            [], {"members": after}, snap, now=datetime.datetime(2027, 1, 4))]
        self.assertEqual(codes, [])


class TestSnapshotBehind(unittest.TestCase):
    """CI and the deploy compare committed files with each other, so a
    refresh failing every day from January 3 would leave them green on the
    old Congress's data. Three days on, it is an error everywhere."""

    def codes(self, when):
        snapshot = legislators.load_snapshot(ROOT)
        raw = sources.load_all(ROOT)
        return [i.code for i in validate.check_snapshot([], raw, snapshot, now=when)]

    def test_a_119th_snapshot_on_january_6_is_an_error(self):
        from kyc import cycle

        snapshot = legislators.load_snapshot(ROOT)
        if cycle.snapshot_congress(snapshot) != 119:
            self.skipTest("the committed snapshot is no longer of the 119th Congress")
        self.assertIn("snapshot-behind", self.codes(datetime.datetime(2027, 1, 6)))
        self.assertNotIn("snapshot-behind", self.codes(datetime.datetime(2027, 1, 5, 23)))


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

    def test_a_stale_snapshot_is_reported(self):
        snap = snapshot_of(entry(bioguide="X000001"))
        snap["fetched"] = "2020-01-01T00:00:00+00:00"
        codes = [i.code for i in validate.check_snapshot([], {"members": self.rows()}, snap)]
        self.assertIn("stale-snapshot", codes)


class TestSenateClass(unittest.TestCase):
    """Each senator's class and the year their seat is next on the ballot,
    from the term actually being served - never a hand table."""

    def cycle(self, **kw):
        snap = snapshot_of(entry(bioguide="A", **kw))
        return legislators.senate_cycle(legislators.by_bioguide(snap)["A"])

    def test_class_two_is_up_in_2026(self):
        self.assertEqual(self.cycle(senate_class=2, end="2027-01-03"),
                         {"senateClass": 2, "nextElection": 2026, "senateSpecial": False})

    def test_class_three_is_up_in_2028(self):
        self.assertEqual(self.cycle(senate_class=3, end="2029-01-03"),
                         {"senateClass": 3, "nextElection": 2028, "senateSpecial": False})

    def test_class_one_is_up_in_2030(self):
        self.assertEqual(self.cycle(senate_class=1, end="2031-01-03"),
                         {"senateClass": 1, "nextElection": 2030, "senateSpecial": False})

    def test_an_appointed_class_three_seat_is_a_2026_special(self):
        # Jon Husted's appointment ends on election day 2026: the seat is on
        # this year's ballot two years before its class's own cycle.
        self.assertEqual(self.cycle(senate_class=3, state="OH", end="2026-11-03"),
                         {"senateClass": 3, "nextElection": 2026, "senateSpecial": True})

    def test_a_house_member_has_no_class(self):
        snap = snapshot_of(entry(bioguide="H", chamber="rep", end="2027-01-03"))
        self.assertIsNone(legislators.senate_class(legislators.by_bioguide(snap)["H"]))

    def test_an_unreadable_term_end_is_none_not_a_guess(self):
        self.assertIsNone(legislators.next_election({"termEnd": ""}))
        self.assertIsNone(legislators.next_election(None))
        self.assertIsNone(legislators.senate_class({"senateClass": 4}))


class TestSenateClassValidation(unittest.TestCase):

    def senator(self, pid, state, cls, nxt, up=False, name=None):
        return {"id": pid, "name": name or pid, "chamber": "Senate", "state": state,
                "party": "Republican", "isCandidate": False, "senateClass": cls,
                "nextElection": nxt, "seatUp2026": up}

    def codes(self, profiles, snapshot=True):
        return {(i.level, i.code) for i in validate.check_senate_classes(
            profiles, {"legislators": []} if snapshot else None)}

    def test_a_clean_pair_reports_nothing(self):
        self.assertEqual(self.codes([self.senator("A", "OH", 1, 2030),
                                     self.senator("B", "OH", 3, 2026, up=True)]), set())

    def test_a_missing_class_is_an_error(self):
        self.assertIn(("error", "senate-class-missing"),
                      self.codes([self.senator("A", "TX", None, 2026, up=True)]))

    def test_two_senators_of_one_class_is_an_error(self):
        self.assertIn(("error", "senate-class-clash"),
                      self.codes([self.senator("A", "TX", 2, 2026, up=True),
                                  self.senator("B", "TX", 2, 2026, up=True)]))

    def test_next_election_disagreeing_with_seat_up_is_reported(self):
        self.assertIn(("warn", "senate-next-election"),
                      self.codes([self.senator("A", "TX", 2, 2026, up=False)]))

    def test_without_a_snapshot_it_says_it_did_not_look(self):
        self.assertEqual(self.codes([self.senator("A", "TX", None, 2026)], snapshot=False),
                         {("warn", "senate-class-unchecked")})


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

    def test_the_record_and_todays_term_dates_agree(self):
        # The frozen record's Senate races are the senators whose terms end
        # at the 2026 election - or, once a special election's winner is
        # seated, a seat whose appointee's term has ended (record.drift).
        from kyc import races, record
        profiles, _ = build_profiles(dict(self.raw, record=None), snapshot=self.snapshot)
        live = races.contestable(profiles)
        self.assertEqual(record.drift(self.raw["record"], live, self.snapshot), [])

    def test_the_senate_seats_up_are_the_records_incumbents(self):
        from kyc import record
        profiles, _ = build_profiles(self.raw, snapshot=self.snapshot)
        # By the seat they held, whatever they sit in now (heldRaceId).
        up = {p["id"] for p in profiles
              if not p["isCandidate"] and (p.get("heldRaceId") or "").startswith("S-")}
        self.assertEqual(up, record.senate_incumbents(self.raw["record"]))

    def test_every_senator_has_a_term_end_year(self):
        profiles, _ = build_profiles(self.raw, snapshot=self.snapshot)
        senators = [p for p in profiles
                    if not p["isCandidate"] and "Senate" in p["chamber"]]
        self.assertTrue(all(p["termEndYear"] for p in senators))

    def test_every_senator_has_a_class_and_next_election(self):
        from kyc.record import seated
        profiles, _ = build_profiles(self.raw, snapshot=self.snapshot)
        senators = [p for p in profiles if seated(p) and "Senate" in p["chamber"]]
        self.assertTrue(all(p["senateClass"] in (1, 2, 3) for p in senators))
        # The 2026 ballot by this route is the seatUp2026 set, except a
        # record incumbent re-seated since Election Day (a special
        # election's winner), whose next election is their new term's.
        from kyc import cycle
        election = cycle.general_election_day(cycle.CYCLE).isoformat()
        people = legislators.by_bioguide(self.snapshot)
        reseated = {p["id"] for p in senators
                    if (people.get(p["id"]) or {}).get("termStart", "") > election}
        self.assertEqual({p["id"] for p in senators if p["nextElection"] == 2026},
                         {p["id"] for p in senators if p["seatUp2026"]} - reseated)
        # Every special is a seat whose class is not the 2026 class.
        for p in senators:
            if p["senateSpecial"]:
                self.assertEqual(p["nextElection"], 2026)
                self.assertNotEqual(p["senateClass"], 2)
        self.assertEqual(validate.check_senate_classes(profiles, self.snapshot), [])

    def test_the_snapshot_is_json_and_sorted(self):
        with open(legislators.snapshot_path(ROOT), encoding="utf-8") as handle:
            raw = json.load(handle)
        ids = [p["bioguide"] for p in raw["legislators"]]
        self.assertEqual(ids, sorted(ids))


def person_named(wikipedia=None, **name):
    """A trimmed snapshot record carrying only what the name helpers read."""
    return {"bioguide": "X000001", "wikipedia": wikipedia,
            "nameParts": legislators.name_parts(name)}


class TestNames(unittest.TestCase):
    """The roster holds legal names; voters type the names members go by.

    56 sitting members could not be found under their Wikipedia name ("Jim
    Clyburn", "Hank Johnson"), and five displayed as a bare initial and a
    surname ("C. Franklin" for Scott Franklin)."""

    def test_trim_keeps_the_recorded_name_parts(self):
        raw = entry()
        raw["name"] = {"first": "Earl", "middle": "L.", "last": "Carter",
                       "nickname": "Buddy", "official_full": 'Earl L. "Buddy" Carter'}
        parts = legislators.trim(raw)["nameParts"]
        self.assertEqual(parts["nickname"], "Buddy")
        self.assertNotIn("suffix", parts)

    def test_official_full_loses_its_quoted_nickname(self):
        person = person_named(first="Earl", middle="L.", last="Carter", nickname="Buddy",
                              official_full='Earl L. "Buddy" Carter', wikipedia="Buddy Carter")
        self.assertEqual(legislators.aliases(person, "Earl Carter"),
                         ["Earl L. Carter", "Buddy Carter"])

    def test_nickname_carries_the_suffix(self):
        person = person_named(first="Henry", middle="C.", last="Johnson", suffix="Jr.",
                              nickname="Hank", official_full='Henry C. "Hank" Johnson, Jr.',
                              wikipedia="Hank Johnson")
        found = legislators.aliases(person, "Henry Johnson")
        self.assertEqual(found, ["Henry C. Johnson, Jr.", "Hank Johnson, Jr.", "Hank Johnson"])

    def test_wikipedia_disambiguator_is_dropped(self):
        person = person_named(first="John", last="Reed", nickname="Jack",
                              official_full="Jack Reed",
                              wikipedia="Jack Reed (Rhode Island politician)")
        self.assertEqual(legislators.aliases(person, "John Reed"), ["Jack Reed"])

    def test_aliases_that_fold_to_the_display_name_are_dropped(self):
        person = person_named(first="Mario", last="Díaz-Balart",
                              official_full="Mario Díaz-Balart",
                              wikipedia="Mario Díaz-Balart")
        self.assertEqual(legislators.aliases(person, "Mario Diaz-Balart"), [])

    def test_no_record_means_no_aliases(self):
        self.assertEqual(legislators.aliases(None, "Pat Smith"), [])

    def test_goes_by_prefers_the_nickname(self):
        person = person_named(first="J.", middle="Luis", last="Correa", nickname="Lou")
        self.assertEqual(legislators.goes_by(person), "Lou Correa")

    def test_goes_by_falls_back_to_a_real_middle_name(self):
        person = person_named(first="W.", middle="Gregory", last="Steube")
        self.assertEqual(legislators.goes_by(person), "Gregory Steube")

    def test_goes_by_never_returns_another_initial(self):
        person = person_named(first="C.", middle="S.", last="Franklin")
        self.assertIsNone(legislators.goes_by(person))
        self.assertIsNone(legislators.goes_by(None))

    def test_fold_name_ignores_case_and_accents(self):
        self.assertEqual(legislators.fold_name("Jesús GARCÍA"), "jesus garcia")


class TestNamesOnTheRealRoster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = legislators.load_snapshot(ROOT)
        raw = sources.load_all(ROOT)
        profiles, _ = build_profiles(raw, snapshot=cls.snapshot)
        from kyc.record import seated
        cls.members = {p["id"]: p for p in profiles if seated(p)}
        cls.roster = {r.get("Bioguide ID"): r.get("Name") for r in raw["members"]}

    def test_the_snapshot_carries_name_parts(self):
        people = self.snapshot["legislators"]
        self.assertTrue(all(p.get("nameParts", {}).get("last") for p in people))

    def test_no_member_displays_as_a_bare_initial(self):
        initial_first = [p["name"] for p in self.members.values()
                         if legislators.is_initial(p["name"].split()[0])]
        self.assertEqual(initial_first, [])

    def test_only_initial_first_names_are_redisplayed(self):
        changed = 0
        for member_id, profile in self.members.items():
            roster = self.roster.get(member_id)
            if profile["name"] == roster:
                self.assertNotIn("rosterName", profile)
                continue
            changed += 1
            self.assertTrue(legislators.is_initial(roster.split()[0]), roster)
            self.assertEqual(profile["rosterName"], roster)
            self.assertIn(roster, profile["aliases"])
        self.assertGreater(changed, 0)

    def test_scott_franklin_and_french_hill(self):
        self.assertEqual(self.members["F000472"]["name"], "Scott Franklin")
        self.assertEqual(self.members["H001072"]["name"], "French Hill")

    def test_the_finance_cache_still_keys_on_the_roster_spelling(self):
        # A changed key would read as "nobody has looked" for every
        # re-displayed member.
        self.assertEqual(fec.profile_key(self.members["F000472"]), "c. franklin|FL|H")

    def test_voters_names_are_aliases(self):
        self.assertIn("Jim Clyburn", self.members["C000537"]["aliases"])
        self.assertIn("Hank Johnson", self.members["J000288"]["aliases"])
        self.assertIn("Lou Correa", self.members["C001110"]["aliases"])

    def test_aliases_never_repeat_the_display_name(self):
        for profile in self.members.values():
            found = profile.get("aliases", [])
            folded = {legislators.fold_name(a) for a in found}
            self.assertNotIn(legislators.fold_name(profile["name"]), folded)
            self.assertEqual(len(folded), len(found))


if __name__ == "__main__":
    unittest.main()
