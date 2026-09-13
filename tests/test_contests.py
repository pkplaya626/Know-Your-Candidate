"""Tests for who is contesting which seat.

The roster seats a member at the district they hold; the FEC filing says
what they are running for; the state's results page says whether they are
on the ballot. These pin the derivations that reconcile the three, each of
which was a shipped error: thirteen members redistricted into new numbers
and shown as seeking re-election to the old ones, seven House members
running for the Senate shown the same way, and thirty-nine retirements the
roster never recorded.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import races, results, validate  # noqa: E402
from kyc.profiles import _apply_filings, _cross_link  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def member(pid, name, state, district, party="Democrat", fec=None, seat_up=True):
    return {
        "id": pid, "name": name, "chamber": "House", "state": state,
        "districtNum": district, "district": str(district),
        "officeLabel": f"House • {state}-{district}", "party": party,
        "isCandidate": False, "seatUp2026": seat_up,
        "seekingReelection2026": seat_up, "status": "Active Member",
        "fecCandidateId": fec,
    }


def candidate(pid, name, state, chamber="House", district=None, party="Democrat",
              fec=None, source=None):
    label = (f"Senate • {state}" if chamber == "Senate"
             else f"House • {state}-{district}")
    out = {
        "id": pid, "name": name, "chamber": f"{chamber} (Candidate)", "state": state,
        "districtNum": district, "district": str(district or "N/A"),
        "officeLabel": label, "party": party, "isCandidate": True,
        "seatUp2026": True, "seekingReelection2026": False,
        "status": "Filed with the FEC", "fecCandidateId": fec,
    }
    if source:
        out["source"] = source
    return out


def filing(cid, name, office="H", state="TX", district=None, party="DEM"):
    return {"candidate_id": cid, "name": name, "office": office, "state": state,
            "district_number": district, "party": party, "receipts": 100000.0}


class TestSeatFromFiling(unittest.TestCase):
    def test_a_member_filed_for_another_district_is_contesting_it(self):
        casar = member("C001131", "Gregorio Casar", "TX", 35, fec="H2TX35144")
        field = {"candidates": [filing("H2TX35144", "CASAR, GREG", district=37)]}
        moved, reseated = _apply_filings([casar], field, finance=None)
        self.assertEqual(casar["contestRaceId"], "H-TX-37-2026")
        self.assertEqual(casar["contestLabel"], "House • TX-37")
        self.assertFalse(casar["seekingReelection2026"])
        self.assertEqual(casar["officeLabel"], "House • TX-35")   # still holds it
        self.assertEqual(moved, [("Gregorio Casar", "House • TX-35", "House • TX-37")])
        self.assertEqual(reseated, [])

    def test_a_member_filed_for_their_own_seat_is_left_alone(self):
        fry = member("F000478", "Russell Fry", "SC", 7, fec="H2SC07280", party="Republican")
        field = {"candidates": [filing("H2SC07280", "FRY, RUSSELL", state="SC", district=7)]}
        _apply_filings([fry], field, finance=None)
        self.assertNotIn("contestRaceId", fry)
        self.assertTrue(fry["seekingReelection2026"])

    def test_a_roster_challenger_is_reseated_where_the_filing_says(self):
        allred = candidate("CAND_8", "Colin Allred", "TX", district=32, fec="H8TX32098")
        field = {"candidates": [filing("H8TX32098", "ALLRED, COLIN", district=33)]}
        _, reseated = _apply_filings([allred], field, finance=None)
        self.assertEqual(allred["districtNum"], 33)
        self.assertEqual(allred["officeLabel"], "House • TX-33")
        self.assertEqual(allred["rosterSeat"], "House • TX-32")
        self.assertEqual(reseated, [("Colin Allred", "House • TX-32", "House • TX-33")])

    def test_the_finance_cache_supplies_the_id_when_the_profile_lacks_one(self):
        from kyc import fec
        casar = member("C001131", "Gregorio Casar", "TX", 35)
        finance = {fec.profile_key(casar): {"candidate_id": "H2TX35144"}}
        field = {"candidates": [filing("H2TX35144", "CASAR, GREG", district=37)]}
        _apply_filings([casar], field, finance)
        self.assertEqual(casar["fecCandidateId"], "H2TX35144")
        self.assertEqual(casar["contestRaceId"], "H-TX-37-2026")

    def test_at_large_spellings_are_one_seat(self):
        # The FEC numbers the Northern Mariana Islands delegate 1 and Alaska's
        # 0; the roster says at-large. All of them are district 0.
        self.assertEqual(races.race_id("House", "MP", 0), "H-MP-00-2026")
        from kyc import candidates
        self.assertEqual(candidates.race_id(filing("H0MP00001", "X, Y", state="MP", district=1)),
                         "H-MP-00-2026")
        self.assertEqual(candidates.race_id(filing("H0AK00001", "X, Y", state="AK", district=0)),
                         "H-AK-00-2026")
        self.assertEqual(races.race_label("House", "AK", 0), "AK — At-Large")


class TestCrossLink(unittest.TestCase):
    def test_a_member_running_for_the_other_chamber_is_not_seeking_reelection(self):
        stevens = member("S001215", "Haley Stevens", "MI", 11)
        senate = candidate("FEC_S6MI00426", "Haley Stevens", "MI", chamber="Senate",
                           fec="S6MI00426", source="fec-field")
        self.assertEqual(_cross_link([stevens, senate]), 1)
        self.assertEqual(stevens["alsoRunningId"], "FEC_S6MI00426")
        self.assertEqual(stevens["contestRaceId"], "S-MI-2026")
        self.assertFalse(stevens["seekingReelection2026"])
        self.assertEqual(senate["incumbentId"], "S001215")

    def test_middle_names_do_not_break_the_link(self):
        carter = member("C001103", "Earl Carter", "GA", 1, party="Republican")
        senate = candidate("FEC_S6GA00374", "Earl Leroy Carter", "GA", chamber="Senate",
                           party="Republican", fec="S6GA00374")
        self.assertEqual(_cross_link([carter, senate]), 1)
        self.assertFalse(carter["seekingReelection2026"])

    def test_same_name_in_another_state_is_not_linked(self):
        rogers = member("R000575", "Mike Rogers", "AL", 3, party="Republican")
        other = candidate("FEC_S6MI00001", "Mike Rogers", "MI", chamber="Senate",
                          party="Republican")
        self.assertEqual(_cross_link([rogers, other]), 0)
        self.assertTrue(rogers["seekingReelection2026"])


class TestRacesWithContests(unittest.TestCase):
    def test_a_member_contesting_another_seat_is_in_both_races(self):
        casar = member("C001131", "Gregorio Casar", "TX", 35, fec="H2TX35144")
        casar["contestRaceId"] = "H-TX-37-2026"
        casar["contestLabel"] = "House • TX-37"
        casar["seekingReelection2026"] = False
        garcia = candidate("FEC_H6TX35095", "Johnny Garcia", "TX", district=35)
        race_list = {r["id"]: r for r in races.build([casar, garcia])}
        self.assertEqual(race_list["H-TX-35-2026"]["incumbentIds"], ["C001131"])
        self.assertTrue(race_list["H-TX-35-2026"]["openSeat"])
        self.assertEqual(race_list["H-TX-37-2026"]["candidateIds"], ["C001131"])
        self.assertTrue(race_list["H-TX-37-2026"]["openSeat"])   # nobody holds it
        self.assertEqual(race_list["H-TX-37-2026"]["label"], "TX-37 — U.S. House")

    def test_a_member_with_a_separate_candidacy_is_not_added_twice(self):
        stevens = member("S001215", "Haley Stevens", "MI", 11)
        senate = candidate("FEC_S6MI00426", "Haley Stevens", "MI", chamber="Senate")
        _cross_link([stevens, senate])
        race_list = {r["id"]: r for r in races.build([stevens, senate])}
        self.assertEqual(race_list["S-MI-2026"]["candidateIds"], ["FEC_S6MI00426"])


class TestResultsSettleMembers(unittest.TestCase):
    def cache(self, **races_):
        return {"asOf": "2026-09-13", "races": races_, "pending": [], "dates": {}}

    def race(self, status, decided=None, party=None, unsure=None):
        return {"status": status, "unmatched": {}, "ambiguous": [],
                "decided": decided or {"general": True, "parties": []},
                "party": party or {}, "unsure": unsure or []}

    def test_nominated_for_their_own_seat_means_seeking_reelection(self):
        fry = member("F000478", "Russell Fry", "SC", 7, fec="H2SC07280", party="Republican")
        fry["contestRaceId"], fry["seekingReelection2026"] = "S-SC-2026", False
        cache = self.cache(**{"H-SC-07-2026": self.race({"H2SC07280": "nominee"})})
        results.apply_cache([fry], cache)
        self.assertTrue(fry["seekingReelection2026"])
        self.assertIsNone(fry["contestRaceId"])
        self.assertEqual(fry["raceStatusRace"], "H-SC-07-2026")

    def test_named_on_another_seats_ballot_means_contesting_it(self):
        casar = member("C001131", "Gregorio Casar", "TX", 35, fec="H2TX35144")
        cache = self.cache(**{"H-TX-37-2026": self.race({"H2TX35144": "nominee"})})
        results.apply_cache([casar], cache)
        self.assertEqual(casar["contestRaceId"], "H-TX-37-2026")
        self.assertFalse(casar["seekingReelection2026"])

    def test_absent_from_a_decided_primary_means_not_on_the_ballot(self):
        pelosi = member("P000197", "Nancy Pelosi", "CA", 11)
        cache = self.cache(**{"H-CA-11-2026": self.race(
            {"H6CA11999": "nominee"}, decided={"general": False, "parties": ["all"]})})
        results.apply_cache([pelosi], cache)
        self.assertEqual(pelosi["raceStatus"], "unlisted")
        self.assertFalse(pelosi["seekingReelection2026"])

    def test_absence_from_an_undecided_primary_means_nothing(self):
        member_ = member("X000001", "Ann Able", "TX", 1, party="Republican")
        cache = self.cache(**{"H-TX-01-2026": self.race(
            {"H6TX01999": "nominee"}, decided={"general": False, "parties": ["democratic"]})})
        results.apply_cache([member_], cache)
        self.assertNotIn("raceStatus", member_)
        self.assertTrue(member_["seekingReelection2026"])

    def test_an_ambiguous_member_is_never_inferred_absent(self):
        # Alaska: the page's "Dan S. Sullivan" fitted two filings once.
        sullivan = member("S001198", "Dan Sullivan", "AK", 0, party="Republican",
                          fec="S4AK00214")
        sullivan["chamber"], sullivan["officeLabel"] = "Senate", "Senate • AK"
        cache = self.cache(**{"S-AK-2026": self.race(
            {"S6AK00001": "nominee"}, decided={"general": True, "parties": []},
            unsure=["S4AK00214", "S6AK00326"])})
        results.apply_cache([sullivan], cache)
        self.assertNotIn("raceStatus", sullivan)
        self.assertTrue(sullivan["seekingReelection2026"])

    def test_a_member_matched_through_their_bioguide_id(self):
        lalota = member("X000001", "Nicolas LaLota", "NY", 1, party="Republican",
                        fec="H2NY01234")
        cache = self.cache(**{"H-NY-01-2026": self.race({"X000001": "nominee"})})
        results.apply_cache([lalota], cache)
        self.assertEqual(lalota["raceStatus"], "nominee")

    def test_the_ballot_party_overrides_a_stale_fec_party_for_a_filer(self):
        bengs = candidate("FEC_S6SD00001", "Brian Bengs", "SD", chamber="Senate",
                          fec="S6SD00001", source="fec-field")
        cache = self.cache(**{"S-SD-2026": self.race(
            {"S6SD00001": "nominee"}, party={"S6SD00001": "independent"})})
        results.apply_cache([bengs], cache)
        self.assertEqual(bengs["party"], "Independent")
        self.assertEqual(bengs["fecParty"], "Democrat")
        # A roster row is reported, not rewritten.
        roster = candidate("CAND_1", "Brian Bengs", "SD", chamber="Senate", fec="S6SD00001")
        results.apply_cache([roster], cache)
        self.assertEqual(roster["party"], "Democrat")
        self.assertEqual(roster["ballotParty"], "independent")


class TestValidation(unittest.TestCase):
    def test_two_nominees_from_one_party_is_an_error(self):
        a = candidate("FEC_1", "Ann Able", "MT", chamber="Senate", fec="S1")
        b = candidate("FEC_2", "Bo Baker", "MT", chamber="Senate", fec="S2")
        for p in (a, b):
            p["raceStatus"], p["raceId"] = "nominee", "S-MT-2026"
        race = {"id": "S-MT-2026", "state": "MT", "settled": True,
                "incumbentIds": [], "candidateIds": ["FEC_1", "FEC_2"], "results": {}}
        codes = [i.code for i in validate.check_results([a, b], [race])]
        self.assertIn("multiple-nominees", codes)
        # ...unless they are independents, who have no primary to share.
        for p in (a, b):
            p["party"] = "Independent"
        codes = [i.code for i in validate.check_results([a, b], [race])]
        self.assertNotIn("multiple-nominees", codes)

    def test_one_person_registered_twice_is_one_nominee(self):
        a = candidate("FEC_1", "Hillary Herzig", "NJ", district=6, fec="H1", party="Republican")
        b = candidate("FEC_2", "Hillary Herzig", "NJ", district=6, fec="H2", party="Republican")
        for p in (a, b):
            p["raceStatus"], p["raceId"] = "nominee", "H-NJ-06-2026"
        race = {"id": "H-NJ-06-2026", "state": "NJ", "settled": True,
                "incumbentIds": [], "candidateIds": ["FEC_1", "FEC_2"], "results": {}}
        codes = [i.code for i in validate.check_results([a, b], [race])]
        self.assertNotIn("multiple-nominees", codes)

    def test_a_member_is_judged_in_the_race_they_contest(self):
        casar = member("C001131", "Gregorio Casar", "TX", 35)
        casar.update(raceId="H-TX-35-2026", contestRaceId="H-TX-37-2026",
                     raceStatus="nominee", seekingReelection2026=False)
        garcia = candidate("FEC_1", "Johnny Garcia", "TX", district=35, fec="H1")
        garcia.update(raceId="H-TX-35-2026", raceStatus="nominee")
        race = {"id": "H-TX-35-2026", "state": "TX", "settled": True,
                "incumbentIds": ["C001131"], "candidateIds": ["FEC_1"], "results": {}}
        codes = [i.code for i in validate.check_results([casar, garcia], [race])]
        self.assertNotIn("multiple-nominees", codes)

    def test_a_cross_party_link_is_an_error(self):
        a = member("M1", "Mike Rogers", "AL", 3, party="Republican")
        b = candidate("FEC_1", "Mike Rogers", "AL", chamber="Senate", party="Democrat")
        a["alsoRunningId"] = "FEC_1"
        codes = [i.code for i in validate.check_seats_contested([a, b])]
        self.assertIn("cross-party-link", codes)

    def test_a_reseated_roster_row_is_reported(self):
        allred = candidate("CAND_8", "Colin Allred", "TX", district=33)
        allred["rosterSeat"] = "House • TX-32"
        codes = [i.code for i in validate.check_seats_contested([allred])]
        self.assertIn("roster-seat-disagrees-with-fec", codes)


class TestAgainstTheRealBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kyc import candidates, fec, legislators
        from kyc.profiles import build_profiles
        from kyc.sources import load_all
        raw = load_all(ROOT)
        cls.profiles, _ = build_profiles(
            raw, snapshot=legislators.load_snapshot(ROOT),
            field=candidates.load_cache(ROOT), finance=fec.load_cache(ROOT))
        fec.apply_cache(cls.profiles, fec.load_cache(ROOT))
        results.apply_cache(cls.profiles, results.load_cache(ROOT))
        cls.races = {r["id"]: r for r in races.build(cls.profiles, results=results.load_cache(ROOT))}
        cls.by_id = {p["id"]: p for p in cls.profiles}

    def test_no_member_seeks_reelection_to_a_seat_they_are_not_contesting(self):
        for p in self.profiles:
            if not p["isCandidate"] and p.get("contestRaceId"):
                self.assertFalse(p["seekingReelection2026"], p["name"])

    def test_every_contested_race_exists_and_lists_the_member(self):
        for p in self.profiles:
            rid = p.get("contestRaceId")
            if rid and not p["isCandidate"] and not p.get("alsoRunningId"):
                self.assertIn(p["id"], self.races[rid]["candidateIds"], p["name"])

    def test_at_large_incumbents_share_a_race_with_their_challengers(self):
        for state in ("AK", "WY", "MP", "GU"):
            race = self.races.get(f"H-{state}-00-2026")
            self.assertIsNotNone(race, state)
            self.assertTrue(race["incumbentIds"], state)
            self.assertNotIn(f"H-{state}-01-2026", self.races)
            self.assertNotIn(f"H-{state}-AL-2026", self.races)

    def test_no_race_gives_one_party_two_nominees(self):
        issues = validate.check_results(self.profiles, list(self.races.values()))
        self.assertEqual([i for i in issues if i.level == "error"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
