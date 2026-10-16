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

    def test_the_phase_is_the_snapshots(self):
        # The 119th until the 120th is sitting and read after noon on
        # January 3, 2027; then the record.
        sitting = cycle.snapshot_congress(self.snapshot)
        self.assertIn(sitting, (119, 120))
        self.assertEqual(cycle.phase(self.snapshot), "campaign" if sitting == 119 else "record")

    def test_a_snapshot_of_mixed_congresses_fails_loudly(self):
        mixed = copy.deepcopy(self.snapshot)
        house = [p for p in mixed["legislators"] if p["chamber"] == "House"]
        other = "2027-01-03" if cycle.snapshot_congress(self.snapshot) == 119 else "2025-01-03"
        for person in house[: len(house) // 2]:
            person["termStart"] = other
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
    the Florida appointee's place, her roster row archived as `congress
    --apply` would archive it (left 2026-12-08), and Ohio's appointee
    re-seated for the term to 2029. Found through the record's bioguide ids,
    so it holds whatever today's snapshot already shows. Never committed."""
    held = raw["record"]["incumbents"]
    florida, ohio = held["S-FL-2026"]["bioguide"], held["S-OH-2026"]["bioguide"]
    # Once the real winners are seated the committed data is the rehearsal,
    # and a fixture built on it would rehearse a world that never happened.
    sitting = legislators.by_bioguide(snapshot)
    for rid in ("S-FL-2026", "S-OH-2026"):
        appointee = held[rid]
        if (sitting.get(appointee["bioguide"]) or {}).get("termEnd") != appointee["termEnd"]:
            raise unittest.SkipTest(f"{rid}'s special election's winner has been seated")
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
    gone = [r for r in raw["members"] if (r.get("Bioguide ID") or "").upper() == florida]
    # The winner's row, as `congress --apply` writes it.
    fields = [k for k in raw["members"][0] if k != "_source"]
    winner = next(p for p in people if p["bioguide"] == "Z900001")
    members = [r for r in raw["members"] if r not in gone]
    if not any((r.get("Bioguide ID") or "").upper() == "Z900001" for r in members):
        members.append(legislators.row_for(winner, fields))
    roster = dict(raw, members=members,
                  former=list(raw.get("former") or []) + [
                      dict(r, **{"Left Office": "2026-12-08",
                                 "Left Via": "legislators-historical",
                                 "Last Congress": "119"}) for r in gone])
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
        # Florida's other senator, whose term runs to 2031, is not up, and
        # neither is the winner seated in December.
        florida = [p for p in self.profiles if record.seated(p) and p["state"] == "FL"
                   and "Senate" in p["chamber"] and p["id"] != "Z900001"]
        self.assertTrue(florida and not any(p["seatUp2026"] for p in florida))

    def test_the_record_checks_stay_quiet_once_the_term_has_ended(self):
        issues = validate.check_record(self.profiles, self.record, self.snapshot)
        self.assertEqual([i.code for i in issues], [])

    def test_the_appointee_who_left_keeps_her_race(self):
        florida = next(p for p in self.profiles if p["id"] == self.florida)
        self.assertEqual(florida["formerMember"]["left"], "2026-12-08")
        self.assertEqual(florida["term_start"], "2025-01-21 - 2026-12-08")
        self.assertEqual(florida["committees"], "No data")
        self.assertNotIn("phone", florida)
        built = {r["id"]: r for r in races.build(self.profiles, record=self.record)}
        self.assertEqual(built["S-FL-2026"]["incumbentIds"], [self.florida])
        self.assertEqual(built["S-FL-2026"]["incumbent"]["seated"], False)
        self.assertEqual(built["S-FL-2026"]["winnerId"], "Z900001")
        # Never counted as a sitting senator: the Senate is still 100.
        self.assertNotIn("senate-size",
                         [i.code for i in validate.check_chamber_sizes(self.profiles)])

    def test_the_winner_is_never_an_incumbent_or_up(self):
        winner = next(p for p in self.profiles if p["id"] == "Z900001")
        self.assertEqual((winner["raceRole"], winner["raceId"], winner["seatUp2026"]),
                         ("winner", "S-FL-2026", False))
        built = {r["id"]: r for r in races.build(self.profiles, record=self.record)}
        self.assertNotIn("Z900001", built["S-FL-2026"]["incumbentIds"])
        self.assertIn("Z900001", built["S-FL-2026"]["candidateIds"])

    def test_an_incumbent_with_no_profile_is_an_error(self):
        # Neither on the roster nor archived: the race would lose its holder.
        bare = dict(self.raw, former=[])
        profiles, _ = build_profiles(bare, snapshot=self.snapshot)
        codes = [i.code for i in validate.check_record(profiles, self.record, self.snapshot)]
        self.assertIn("record-incumbent-missing", codes)

    def test_drift_allows_only_an_ended_term(self):
        live = record.race_ids(self.record) - {"S-FL-2026"}
        self.assertEqual(record.drift(self.record, live, self.snapshot), [])
        early = dict(self.snapshot, fetched="2026-10-01T07:20:00+00:00")
        self.assertEqual(record.drift(self.record, live, early),
                         ["S-FL-2026: in the record, not among today's seats"])


class TestWhoWonASeat(unittest.TestCase):
    """Seated in a 2026 seat since Election Day is not the same as having won
    it: a special election for the rest of the old term, or an appointment
    after a winner leaves, seats someone else (record.seat_changes). All
    people here are fictional (Z8...), in real seats."""

    @classmethod
    def setUpClass(cls):
        cls.record = sources.load_all(ROOT)["record"]

    def seat(self, rid, **term):
        race = self.record["races"][rid]
        person = {"bioguide": "Z800001", "chamber": race["chamber"], "state": race["state"],
                  "district": race.get("district"), "senateClass": race.get("senateClass"),
                  "how": None}
        person.update(term)
        return record.seat_changes(self.record, {"legislators": [person]})

    def test_the_term_the_race_decided_is_a_win(self):
        self.assertEqual(self.seat("H-TX-23-2026", termStart="2027-01-03",
                                   termEnd="2029-01-03")["winners"], {"Z800001": "H-TX-23-2026"})
        # Florida's special: the rest of the class's term, seated in December.
        self.assertEqual(self.seat("S-FL-2026", termStart="2026-12-08", termEnd="2029-01-03",
                                   how="special-election")["winners"],
                         {"Z800001": "S-FL-2026"})

    def test_a_special_for_the_old_term_is_not(self):
        # Texas's 23rd, filled the same day for the rest of the 119th: the
        # regular race may have another winner (TX-18 in 2024).
        found = self.seat("H-TX-23-2026", termStart="2026-11-12", termEnd="2027-01-03",
                          how="special-election")
        self.assertEqual(found["winners"], {})
        self.assertEqual(found["successors"], {"Z800001": "H-TX-23-2026"})

    def test_an_appointment_is_not(self):
        found = self.seat("S-KY-2026", termStart="2027-06-10", termEnd="2028-11-07",
                          how="appointment")
        self.assertEqual(found["winners"], {})
        self.assertEqual(found["successors"], {"Z800001": "S-KY-2026"})

    def test_a_special_in_the_new_term_is_not(self):
        found = self.seat("H-TX-23-2026", termStart="2027-09-01", termEnd="2029-01-03",
                          how="special-election")
        self.assertEqual(found["winners"], {})


class TestAnIncumbentWhoWonAnotherSeat(unittest.TestCase):
    """January 3: a representative who held a 2026 House seat and won the
    state's Senate seat is still the House race's incumbent, contesting the
    Senate race - not its incumbent, and its winner. Hypothetical: KY-6's and
    Kentucky's Senate seat, by id only."""

    @classmethod
    def setUpClass(cls):
        raw = sources.load_all(ROOT)
        if cycle.phase(legislators.load_snapshot(ROOT)) != "campaign":
            raise unittest.SkipTest("January 3 has happened: the committed data is the case")
        cls.record = raw["record"]
        cls.house = cls.record["incumbents"]["H-KY-06-2026"]["bioguide"]
        senator = cls.record["incumbents"]["S-KY-2026"]["bioguide"]
        snapshot = copy.deepcopy(legislators.load_snapshot(ROOT))
        people = [p for p in snapshot["legislators"] if p["bioguide"] != senator]
        for p in people:
            if p["bioguide"] == cls.house:
                p.update(chamber="Senate", district=None, senateClass=2,
                         termStart="2027-01-03", termEnd="2033-01-03", how=None)
        snapshot["legislators"] = people
        snapshot["fetched"] = "2027-01-04T07:20:00+00:00"
        members = []
        gone = []
        for row in raw["members"]:
            bid = (row.get("Bioguide ID") or "").upper()
            if bid == senator:
                gone.append(dict(row, **{"Left Office": "2027-01-03", "Last Congress": "119",
                                         "Left Via": "legislators-historical"}))
            elif bid == cls.house:
                members.append(dict(row, Chamber="Senate", District="",
                                    **{"Term Start": "2027-01-03"}))
            else:
                members.append(row)
        roster = dict(raw, members=members, former=list(raw.get("former") or []) + gone)
        cls.profiles, _ = build_profiles(roster, snapshot=snapshot)
        cls.races = {r["id"]: r for r in races.build(cls.profiles, record=cls.record)}
        cls.person = next(p for p in cls.profiles if p["id"] == cls.house)

    def test_they_won_the_senate_race(self):
        self.assertEqual((self.person["raceRole"], self.person["raceId"]),
                         ("winner", "S-KY-2026"))
        self.assertEqual(self.races["S-KY-2026"]["winnerId"], self.house)
        self.assertNotIn(self.house, self.races["S-KY-2026"]["incumbentIds"])

    def test_and_still_held_the_house_seat(self):
        self.assertEqual(self.person["heldRaceId"], "H-KY-06-2026")
        self.assertEqual(self.person["contestRaceId"], "S-KY-2026")
        self.assertTrue(self.person["seatUp2026"])
        self.assertFalse(self.person["seekingReelection2026"])
        house = self.races["H-KY-06-2026"]
        self.assertEqual(house["incumbentIds"], [self.house])
        self.assertTrue(house["openSeat"])

    def test_counted_once_among_the_seats_up(self):
        from kyc import summary
        built = summary.build(self.profiles, races=list(self.races.values()))
        self.assertEqual(built["election"]["senateSeatsUp"],
                         sum(1 for rid in self.record["races"] if rid.startswith("S-")))


class TestTheWinnersFiling(unittest.TestCase):
    """A special election's winner seated in December has a filing in the
    field, with its own FEC_ profile. One person: folded into the member
    only by the FEC id Congress's record lists for them (rule 25)."""

    @classmethod
    def setUpClass(cls):
        from kyc import candidates

        cls.raw = sources.load_all(ROOT)
        cls.field = candidates.load_cache(ROOT)
        cls.roster, cls.after, cls.florida, _ = specials_seated(
            cls.raw, legislators.load_snapshot(ROOT))
        # A real filer for Florida's seat stands in for the winner's filing.
        filers = [r for r in screen_field(cls.field, build_profiles(cls.raw)[0],
                                          cls.raw["record"])["candidates"]
                  if candidates.race_id(r) == "S-FL-2026"
                  and (r.get("receipts") or 0) >= candidates.STATUTORY_THRESHOLD
                  and r.get("incumbent_challenge") != "I"]
        if not filers:
            raise unittest.SkipTest("no Florida Senate filer past the threshold")
        cls.filing = max(filers, key=lambda r: r["receipts"])["candidate_id"]
        # The profile the filing has today: curated (CAND_) or the field's.
        base = build_profiles(cls.raw, field=cls.field)[0]
        cls.held_by = next(p["id"] for p in base if cls.filing in (
            p.get("fecCandidateId"), p.get("rosterFecId")) or p["id"] == "FEC_" + cls.filing)

    def build(self, fec_ids):
        after = copy.deepcopy(self.after)
        for person in after["legislators"]:
            if person["bioguide"] == "Z900001":
                person["fec"] = person["fecAll"] = fec_ids
        profiles, _ = build_profiles(self.roster, snapshot=after, field=self.field)
        return {p["id"]: p for p in profiles}, races.build(profiles, record=self.raw["record"])

    def test_linked_by_the_records_id_it_is_one_profile(self):
        people, built = self.build([self.filing])
        self.assertNotIn(self.held_by, people)
        self.assertEqual(people["Z900001"]["fecCandidateId"], self.filing)
        if not self.held_by.startswith("FEC_"):
            # A curated id answers for the member.
            self.assertIn(self.held_by, people["Z900001"]["otherIds"])
        race = next(r for r in built if r["id"] == "S-FL-2026")
        self.assertEqual(race["winnerId"], "Z900001")
        self.assertIn("Z900001", race["candidateIds"])
        self.assertNotIn("Z900001", race["incumbentIds"])

    def test_without_the_id_neither_is_merged(self):
        # Different names, no id: both stay, and nothing is guessed.
        people, built = self.build([])
        self.assertIn(self.held_by, people)
        self.assertNotIn("fecCandidateId", people["Z900001"])
        race = next(r for r in built if r["id"] == "S-FL-2026")
        self.assertIn(self.held_by, race["candidateIds"])
        # Marked elected, the filing beside the seated winner is reported.
        people[self.held_by]["raceStatus"] = "elected"
        codes = [i.code for i in validate.check_winners(list(people.values()), built)]
        self.assertEqual(codes, ["seated-unlinked"])


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
        roster = dict(self.raw, members=self.members, former=self.former)
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
        # Drift is checked only in the campaign phase (validate.check_record).
        if cycle.phase(cls.snapshot) != "campaign":
            raise unittest.SkipTest("drift is a campaign-phase check")

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
