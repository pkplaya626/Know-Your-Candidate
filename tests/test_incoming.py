"""The seats elected so far to the Congress the 2026 election chooses
(kyc/incoming.py, rule 104), from races and people the tests make: a check
tests the rule, not the day's data."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import incoming  # noqa: E402
from kyc.normalize import STATE_CODES, TERRITORIES  # noqa: E402

STATES = sorted(STATE_CODES - TERRITORIES)


def senator(code, cls, party="Republican", pid=None):
    return {"id": pid or f"S-{code}-{cls}", "name": f"Senator {code} {cls}", "party": party,
            "state": code, "chamber": "Senate", "senateClass": cls, "isCandidate": False}


def house_race(code, district, **extra):
    race = {"id": f"H-{code}-{district:02d}-2026", "chamber": "House", "state": code,
            "district": district, "results": {}}
    race.update(extra)
    return race


def senate_race(code, cls, special=False, **extra):
    race = {"id": f"S-{code}-2026" + ("-special" if special else ""), "chamber": "Senate",
            "state": code, "district": None, "senateClass": cls, "results": {}}
    race.update(extra)
    return race


def winner(race, party="Republican", pid=None, status="elected"):
    return {"id": pid or "W-" + race["id"], "name": "Winner of " + race["id"], "party": party,
            "state": race["state"], "chamber": race["chamber"], "isCandidate": True,
            "raceId": race["id"], "raceStatus": status}


class Chamber:
    """A whole Congress the tests change: every state's two senators, a
    Senate race for each of 35 states' class-2 seats, and the House's 435
    voting seats (California holds them all; the count is the chamber's)."""

    def __init__(self):
        self.profiles = []
        self.races = []
        for code in STATES:
            self.profiles.append(senator(code, 1))
            self.profiles.append(senator(code, 2))
        for code in STATES[:35]:
            race = senate_race(code, 2)
            self.races.append(race)
            self.profiles.append(winner(race))
        for n in range(1, 436):
            race = house_race("CA", n)
            self.races.append(race)
            self.profiles.append(winner(race, "Democrat"))
        # The delegates: Guam's elected, Puerto Rico's not up in 2026.
        gu = house_race("GU", 0)
        self.races.append(gu)
        self.profiles.append(winner(gu, "Democrat"))
        self.profiles.append({"id": "RC-PR", "name": "Resident Commissioner", "party": "Republican",
                              "state": "PR", "chamber": "House", "isCandidate": False})

    def race(self, rid):
        return next(r for r in self.races if r["id"] == rid)

    def person_in(self, rid):
        return next(p for p in self.profiles if p.get("raceId") == rid)

    def build(self, **kw):
        return incoming.build(self.profiles, self.races, results={"asOf": "2026-11-14"}, **kw)


class TestElectedSoFar(unittest.TestCase):
    def test_a_whole_called_congress(self):
        built = Chamber().build()
        self.assertEqual(built["congress"], 120, "the Congress the cycle elects, from cycle.py")
        self.assertEqual(built["termStart"], "2027-01-03")
        self.assertEqual(built["resultsAsOf"], "2026-11-14")
        senate = built["senate"]
        self.assertEqual(senate["elected"], {"D": 0, "R": 35, "I": 0})
        self.assertEqual(senate["notUp"], {"D": 0, "R": 65, "I": 0, "vacant": 0})
        self.assertEqual(senate["uncalled"], 0)
        self.assertEqual(built["house"]["elected"], {"D": 435, "R": 0, "I": 0})
        self.assertEqual(built["house"]["seats"], 435)

    def test_an_uncalled_race_is_counted_apart_never_for_a_party(self):
        c = Chamber()
        c.person_in("H-CA-07-2026")["raceStatus"] = "nominee"
        built = c.build()
        self.assertEqual(built["house"]["elected"]["D"], 434)
        self.assertEqual(built["house"]["uncalled"], 1)
        seat = built["states"]["CA"]["house"]["seats"]["7"]
        self.assertEqual(seat, {"race": "H-CA-07-2026", "status": "uncalled"})

    def test_a_status_from_another_race_is_not_this_ones(self):
        c = Chamber()
        # A member who won another seat: their status is that race's.
        c.person_in("H-CA-07-2026")["raceStatusRace"] = "H-CA-08-2026"
        with self.assertRaises(incoming.IncomingError):
            c.build()  # CA-8 now has two winners

    def test_a_runoff_is_uncalled_and_said_with_its_day(self):
        c = Chamber()
        race = c.race("H-CA-09-2026")
        race.update(generalRunoff="2026-12-01")
        c.person_in("H-CA-09-2026")["raceStatus"] = "runoff"
        built = c.build()
        self.assertEqual(built["house"]["uncalled"], 1)
        self.assertEqual(built["house"]["runoff"], 1)
        self.assertEqual(built["house"]["rounds"], [{"date": "2026-12-01", "open": False, "seats": 1}])
        self.assertEqual(built["states"]["CA"]["house"]["seats"]["9"]["status"], "runoff")

    def test_an_open_primarys_december_round_says_it_is_one(self):
        c = Chamber()
        race = c.race("H-CA-10-2026")
        race.update(generalRunoff="2026-12-12", primaryKind="open",
                    results={"otherRunoff": ["Somebody Else"]})
        c.person_in("H-CA-10-2026")["raceStatus"] = "runoff"
        self.assertEqual(c.build()["house"]["rounds"], [{"date": "2026-12-12", "open": True, "seats": 1}])

    def test_a_winner_with_no_profile_counts_by_the_pages_party(self):
        c = Chamber()
        c.profiles.remove(c.person_in("H-CA-11-2026"))
        c.race("H-CA-11-2026")["results"] = {"otherElected": ["Pat Doe"],
                                             "otherParties": {"Pat Doe": "Republican"}}
        built = c.build()
        self.assertEqual(built["house"]["elected"], {"D": 434, "R": 1, "I": 0})
        self.assertEqual(built["states"]["CA"]["house"]["seats"]["11"],
                         {"party": "R", "name": "Pat Doe", "partyName": "Republican"})

    def test_a_winner_with_no_party_stops_the_build(self):
        c = Chamber()
        c.profiles.remove(c.person_in("H-CA-11-2026"))
        c.race("H-CA-11-2026")["results"] = {"otherElected": ["Pat Doe"]}
        with self.assertRaises(incoming.IncomingError):
            c.build()

    def test_two_winners_in_one_race_stop_the_build(self):
        c = Chamber()
        c.race("H-CA-12-2026")["results"] = {"otherElected": ["Pat Doe"],
                                             "otherParties": {"Pat Doe": "Republican"}}
        with self.assertRaises(incoming.IncomingError):
            c.build()

    def test_the_dfls_winners_are_democrats_an_independent_is_neither(self):
        c = Chamber()
        c.person_in("H-CA-13-2026")["party"] = "Democratic-Farmer Labor"
        c.person_in("H-CA-14-2026")["party"] = "Independent"
        c.person_in("H-CA-15-2026")["party"] = "Libertarian"
        built = c.build()
        self.assertEqual(built["house"]["elected"], {"D": 433, "R": 0, "I": 2})

    def test_a_vacant_seat_not_on_the_ballot(self):
        c = Chamber()
        code = STATES[-1]  # no race in its state
        c.profiles.remove(next(p for p in c.profiles if p["id"] == f"S-{code}-1"))
        built = c.build()
        self.assertEqual(built["senate"]["notUp"]["vacant"], 1)
        self.assertEqual(built["states"][code]["senate"]["notUp"]["vacant"], 1)
        self.assertEqual(sum(built["senate"]["notUp"].values()) + 35, 100)

    def test_a_special_election_takes_its_seat_off_the_not_up(self):
        c = Chamber()
        code = STATES[0]
        special = senate_race(code, 1, special=True)
        c.races.append(special)
        c.profiles.append(winner(special, "Democrat"))
        built = c.build()
        self.assertEqual(built["states"][code]["senate"]["notUp"], {"D": 0, "R": 0, "I": 0, "vacant": 0})
        self.assertEqual(built["senate"]["elected"], {"D": 1, "R": 35, "I": 0})
        self.assertEqual(built["senate"]["races"], 36)

    def test_the_territories_are_apart_from_the_house(self):
        built = Chamber().build()
        self.assertEqual(built["delegates"]["elected"], {"D": 1, "R": 0, "I": 0})
        self.assertEqual(built["delegates"]["notUp"]["R"], 1, "Puerto Rico's seat is not up in 2026")
        self.assertEqual(sum(built["house"]["notUp"].values()), 0)
        self.assertNotIn("senate", built["states"]["GU"])
        self.assertEqual(built["states"]["PR"]["house"]["step"], "allR")

    def test_the_senate_must_add_up_to_100(self):
        c = Chamber()
        c.profiles.append(senator(STATES[-1], 3, pid="extra"))
        with self.assertRaises(incoming.IncomingError):
            c.build()

    def test_the_house_must_be_435_voting_seats(self):
        c = Chamber()
        c.races = [r for r in c.races if r["id"] != "H-CA-435-2026"]
        with self.assertRaises(incoming.IncomingError):
            c.build()

    def test_a_senate_race_with_no_class_stops_the_build(self):
        c = Chamber()
        del c.races[0]["senateClass"]
        with self.assertRaises(incoming.IncomingError):
            c.build()

    def test_nothing_is_incoming_once_the_new_congress_sits(self):
        snapshot = {"fetched": "2027-01-04T00:00:00Z",
                    "legislators": [{"chamber": "House", "termStart": "2027-01-03"}] * 5}
        self.assertIsNone(Chamber().build(snapshot=snapshot))
        before = {"fetched": "2026-11-14T00:00:00Z",
                  "legislators": [{"chamber": "House", "termStart": "2025-01-03"}] * 5}
        self.assertIsNotNone(Chamber().build(snapshot=before))


class TestSteps(unittest.TestCase):
    """A state's step in the elected view is the one every way of deciding
    its uncalled seats leaves it at."""

    def test_a_step_its_uncalled_seats_cannot_change(self):
        self.assertEqual(incoming.decided_step({"D": 1, "R": 5, "I": 0}, 1, "house"), "majR")

    def test_a_step_they_can(self):
        self.assertEqual(incoming.decided_step({"D": 1, "R": 2, "I": 0}, 1, "house"), "undecided")
        self.assertEqual(incoming.decided_step({"D": 0, "R": 3, "I": 0}, 1, "house"), "undecided",
                         "all Republican only if the last seat is")

    def test_a_senate_state_with_a_race_not_called_is_not_decided(self):
        self.assertEqual(incoming.decided_step({"D": 0, "R": 1, "I": 0, "vacant": 0}, 1, "senate"),
                         "undecided")
        self.assertEqual(incoming.decided_step({"D": 1, "R": 1, "I": 0, "vacant": 0}, 0, "senate"),
                         "split")

    def test_the_steps_in_a_built_state(self):
        c = Chamber()
        for n in (1, 2, 3, 4, 5):
            c.person_in(f"H-CA-{n:02d}-2026")["party"] = "Republican"
        built = c.build()
        self.assertEqual(built["states"]["CA"]["house"]["step"], "majD")
        code = STATES[0]
        c.person_in(f"S-{code}-2026")["raceStatus"] = "nominee"
        self.assertEqual(c.build()["states"][code]["senate"]["step"], "undecided")
        self.assertEqual(c.build()["states"][code]["senate"]["uncalled"], 1)

    def test_an_independent_is_its_own_step(self):
        self.assertEqual(incoming.house_step(0, 0, 1, 1), "allI")
        self.assertEqual(incoming.senate_step(0, 0, 2, 0), "allI")
        self.assertEqual(incoming.senate_step(1, 0, 1, 0), "split")


class TestTiles(unittest.TestCase):
    def test_the_squares_are_the_2026_districts(self):
        built = Chamber().build()
        cells = {str(n): [0, 0] for n in range(1, 436)}
        layout = {"states": {"CA": {"cells": {"1": [0, 0]}, "cells2026": cells}}}
        self.assertEqual(incoming.tile_problems(layout, built), [])
        layout["states"]["CA"]["cells2026"] = {"1": [0, 0]}
        self.assertTrue(incoming.tile_problems(layout, built))


if __name__ == "__main__":
    unittest.main()
