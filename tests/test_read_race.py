"""read_race, the one reader of a race's November result, and the table of
who is elected, keyed on the state and the office (kyc/election_law.py).

results.build read each race inline in its loop, through closures over the
FEC rows and switches keyed by state alone: Maine's ranked-choice gate for
Congress would have held any other Maine office for ever. These tests make
the race they read - its people, its section, its law - and ask read_race,
and ask build of the same page, which must store what read_race answered.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import election_law, normalize, overrides, races as races_mod, results  # noqa: E402
from tests.test_results import (DEM, REP, NoGap, box, call_infobox, party_box,  # noqa: E402
                                row)

NIGHT = datetime.date(2026, 11, 4)
BEFORE = datetime.date(2026, 11, 3)


class TestReadRace(NoGap):
    """One race read whole, as build reads it, from people the test makes."""

    TITLE = "2026 United States House of Representatives elections in Ohio"
    RID = "H-OH-05-2026"
    DATES = {("OH", "H"): {"primary": "2026-05-05", "runoff": None}}
    PRIMARIES = "\n".join([
        party_box("Republican primary results", ("Pat Stone", REP, 58139, True),
                  ("Tony Hamil", REP, 9121, False)),
        party_box("Democratic primary results", ("Trina Swan", DEM, 54413, True),
                  ("Luke Gull", DEM, 11888, False))])
    ROWS = [row("H6OH05001", "STONE, PAT", "OH", "H", 5, "REP"),
            row("H6OH05002", "HAMIL, TONY", "OH", "H", 5, "REP"),
            row("H6OH05003", "SWAN, TRINA", "OH", "H", 5, "DEM"),
            row("H6OH05004", "GULL, LUKE", "OH", "H", 5, "DEM")]

    def section(self, *parts):
        return "\n\n".join(parts + (self.PRIMARIES,)) + "\n"

    def both(self, *parts, today=NIGHT, rid=None, rows=None, dates=None, title=None,
             state="OH", office="H"):
        """read_race's answer, and build's cache, for one page holding *parts*."""
        rid, rows = rid or self.RID, rows or self.ROWS
        dates, title = dates or self.DATES, title or self.TITLE
        section = self.section(*parts)
        page = ("\n==District 5==\n" + section) if office == "H" else section
        logged_read, logged_build = [], []
        law = results.race_law(state, office, dates[(state, office)], today)
        read = results.read_race(rid, title, section, results.RacePeople(rows), law, today,
                                 log=logged_read.append)
        cache = results.build({"candidates": rows}, dates, today=today, log=logged_build.append,
                              fetch=lambda t: page if t == title else
                              (_ for _ in ()).throw(results.PageMissing(t)))
        # What build stores for the race is what read_race answered, with the
        # route of the call where someone stands elected.
        stored = dict(cache["races"].get(rid) or {})
        called = stored.pop("calledBy", None)
        self.assertEqual(stored or None, read["race"])
        if "elected" in ((read["race"] or {}).get("status") or {}).values():
            self.assertEqual(called, read["call"])
        else:
            self.assertIsNone(called)
        for key in ("refusedMarks", "refusedNames", "refusedRows", "renamedRows",
                    "unsettledRows", "staleAliases"):
            self.assertEqual(cache[key].get(rid) or [], read[key], key)
        self.assertEqual([line for line in logged_build if f" {rid}:" in line], logged_read)
        return read, cache

    def status(self, read):
        return read["race"]["status"]

    def test_a_mark_elects_the_leader_and_defeats_the_rest(self):
        read, _cache = self.both(party_box("2026 Ohio's 5th congressional district election",
                                           ("Pat Stone", REP, 190744, True),
                                           ("Trina Swan", DEM, 168350, False)))
        self.assertEqual((self.status(read)["H6OH05001"], self.status(read)["H6OH05003"]),
                         ("elected", "defeated"))
        self.assertEqual(read["call"], results.CALLED_TABLE)
        self.assertEqual(read["refusedMarks"], [])

    def test_before_the_count_a_mark_decides_nothing(self):
        read, _cache = self.both(party_box("2026 Ohio's 5th congressional district election",
                                           ("Pat Stone", REP, 190744, True),
                                           ("Trina Swan", DEM, 168350, False)), today=BEFORE)
        self.assertEqual((self.status(read)["H6OH05001"], self.status(read)["H6OH05003"]),
                         ("nominee", "nominee"))

    def test_an_infobox_call_elects_where_no_table_marks(self):
        read, _cache = self.both(
            party_box("2026 Ohio's 5th congressional district election",
                      ("Pat Stone", REP, 190744, False), ("Trina Swan", DEM, 168350, False)),
            call_infobox(("Pat Stone", REP, 190744), ("Trina Swan", DEM, 168350),
                         declared="[[Pat Stone]]", reporting=99))
        self.assertEqual(self.status(read)["H6OH05001"], "elected")
        self.assertEqual(read["call"], results.CALLED_INFOBOX)

    def test_a_mark_on_a_name_nobody_filed_is_refused(self):
        read, cache = self.both(party_box("2026 Ohio's 5th congressional district election",
                                          ("Peter Griffin", REP, 190744, True),
                                          ("Trina Swan", DEM, 168350, False)))
        self.assertEqual([m["name"] for m in read["refusedMarks"]], ["Peter Griffin"])
        self.assertNotIn("elected", self.status(read).values())
        self.assertNotIn("defeated", self.status(read).values())
        self.assertEqual(cache["refusedMarks"][self.RID], read["refusedMarks"])

    def test_a_general_runoff_table_sends_the_top_two_to_it(self):
        title = "2026 United States Senate election in Georgia"
        rows = [{"candidate_id": "S8GA1", "name": "OSSOFF, JON", "state": "GA", "office": "S",
                 "party": "DEM"},
                {"candidate_id": "S6GA2", "name": "COLLINS, MIKE", "state": "GA", "office": "S",
                 "party": "REP"},
                {"candidate_id": "S6GA3", "name": "LIB, LENA", "state": "GA", "office": "S",
                 "party": "LIB"}]
        dates = {("GA", "S"): {"primary": "2026-05-19", "runoff": "2026-06-16"}}
        self.PRIMARIES = (box("Democratic primary results", ("Jon Ossoff", 900, True)) + "\n" +
                          box("Republican primary results", ("Mike Collins", 800, True)))
        read, _cache = self.both(
            box(title, ("Jon Ossoff", 490, False), ("Mike Collins", 480, False),
                ("Lena Lib", 30, False)),
            box("Runoff results", ("Jon Ossoff", 0, False), ("Mike Collins", 0, False)),
            rid="S-GA-2026", rows=rows, dates=dates, title=title, state="GA", office="S")
        status = self.status(read)
        self.assertEqual((status["S8GA1"], status["S6GA2"], status["S6GA3"]),
                         ("runoff", "runoff", "defeated"))


class TestReadRaceTakesAnyOfficesPeople(NoGap):
    """read_race reads the people it is given, whoever they are: here an
    office this site does not read (a made-up Maine governor's race), whose
    people are a list's, not the FEC's. Maine counts its races for Congress by
    ranked choice and elects its governor by plurality: the law is the
    office's, so Congress's entry never holds it."""

    TITLE = "2026 Maine gubernatorial election"
    ROWS = [{"candidate_id": "G-ME-2026:1", "name": "PINGREE, HANNAH"},
            {"candidate_id": "G-ME-2026:2", "name": "CHARLES, ROBERT"},
            {"candidate_id": "G-ME-2026:3", "name": "PAGE, ALEX"}]
    SECTION = party_box("2026 Maine gubernatorial election",
                        ("Hannah Pingree", DEM, 388721, True),
                        ("Robert Charles", REP, 267346, False),
                        ("Alex Page", "Independent politician", 157000, False))

    def read(self, office):
        law = results.race_law("ME", office, {"primary": "2026-06-09", "runoff": None}, NIGHT)
        return results.read_race("G-ME-2026", self.TITLE, self.SECTION,
                                 results.RacePeople(self.ROWS), law, NIGHT, log=lambda *_: None)

    def test_a_plurality_office_elects_the_marked_leader_short_of_a_majority(self):
        self.assertEqual(election_law.elected_by("ME", "G"), election_law.PLURALITY)
        status = self.read("G")["race"]["status"]
        self.assertEqual(status, {"G-ME-2026:1": "elected", "G-ME-2026:2": "defeated",
                                  "G-ME-2026:3": "defeated"})

    def test_congresss_ranked_choice_law_holds_the_same_count(self):
        # The same table under Maine's law for the House: 47.8% of the first
        # choices is a lead, not a win.
        self.assertTrue(election_law.ranked_choice("ME", "H"))
        status = self.read("H")["race"]["status"]
        self.assertNotIn("elected", status.values())


class TestRacePeople(unittest.TestCase):
    """The tests the reading asks of a race's people are the object's."""

    ROWS = [row("H6OH05003", "SWAN, TRINA", "OH", "H", 5, "DEM")]

    def test_a_filing_vouches_and_a_stranger_does_not(self):
        people = results.RacePeople(self.ROWS)
        self.assertTrue(people.vouched("Trina Swan"))
        self.assertFalse(people.vouched("Peter Griffin"))
        self.assertFalse(people.complete)

    def test_a_certified_list_names_people_with_no_filing(self):
        printed = {"entries": [{"name": "Lena Lib", "party": "Libertarian", "kind": "printed"}],
                   "complete": True}
        people = results.RacePeople(self.ROWS, printed=printed)
        self.assertTrue(people.on_a_list("Lena Lib"))
        self.assertTrue(people.vouched("Lena Lib"))
        self.assertTrue(people.complete)
        self.assertEqual(people.untied(), [("Lena Lib", "Libertarian")])

    def test_a_qualified_list_withdrawal_names_nobody(self):
        people = results.RacePeople(self.ROWS, qualified=[
            {"name": "Gone Candidate", "party": "Republican", "withdrew": True},
            {"name": "Ann Alpha", "party": "Republican", "withdrew": False}])
        self.assertFalse(people.on_a_list("Gone Candidate"))
        self.assertTrue(people.on_a_list("Ann Alpha"))
        self.assertEqual(people.listed_names(), {"Gone Candidate", "Ann Alpha"})


# The tables keyed by state that election_law replaced, as they stood: each
# question they answered must be answered the same for every office of
# Congress each state has.
OLD_RANKED_CHOICE = {"ME": "21-A M.R.S. 723-A", "AK": "AS 15.15.350"}
OLD_ALL_PARTY_PRIMARIES = {"CA": "top-two", "WA": "top-two", "AK": "top-four"}
OLD_GENERAL_RUNOFFS = {"GA": ("2026-12-01", "O.C.G.A. 21-2-501(a)"),
                       "GU": ("2026-11-17", "48 U.S.C. 1712"),
                       "VI": ("2026-11-17", "48 U.S.C. 1712")}


def congress_offices(state):
    """The offices of Congress a place elects: a senator only in a state."""
    return ("H",) if state in normalize.TERRITORIES else ("S", "H")


class TestElectionLaw(unittest.TestCase):

    def test_every_old_answer_is_the_offices_own(self):
        for state in sorted(normalize.STATE_CODES):
            for office in congress_offices(state):
                where = (state, office)
                self.assertEqual(election_law.ranked_choice(state, office),
                                 state in OLD_RANKED_CHOICE, where)
                if state in OLD_RANKED_CHOICE:
                    self.assertEqual(election_law.law(state, office)["law"],
                                     OLD_RANKED_CHOICE[state], where)
                primary = election_law.all_party_primary(state, office)
                self.assertEqual(primary and primary[0], OLD_ALL_PARTY_PRIMARIES.get(state), where)
                runoff = election_law.general_runoff(state, office)
                if state in OLD_GENERAL_RUNOFFS:
                    day, provision = OLD_GENERAL_RUNOFFS[state]
                    self.assertEqual(runoff[0], day, where)
                    self.assertIn(provision, runoff[1], where)
                    self.assertEqual(election_law.elected_by(state, office),
                                     election_law.MAJORITY_OR_RUNOFF, where)
                else:
                    self.assertIsNone(runoff, where)
                if state not in OLD_RANKED_CHOICE and state not in OLD_GENERAL_RUNOFFS:
                    self.assertEqual(election_law.elected_by(state, office),
                                     election_law.PLURALITY, where)

    def test_the_views_by_state_are_the_old_tables(self):
        self.assertEqual(results.RANKED_CHOICE, OLD_RANKED_CHOICE)
        self.assertEqual({s: k for s, (k, _law) in results.ALL_PARTY_PRIMARIES.items()},
                         OLD_ALL_PARTY_PRIMARIES)
        self.assertEqual({s: day for s, (day, _law) in overrides.GENERAL_RUNOFFS.items()},
                         {s: day for s, (day, _law) in OLD_GENERAL_RUNOFFS.items()})
        self.assertIs(results._general_runoffs(), overrides.GENERAL_RUNOFFS)

    def test_congresss_entries_only(self):
        # Phase 0 adds no office: every entry is Congress's, and a state's other
        # offices are plurality and hold a party primary until an entry says so.
        self.assertEqual({office for _state, office in election_law.ELECTION_LAWS}, {"S", "H"})
        for state in ("ME", "AK", "GA", "GU", "VI", "CA", "WA"):
            self.assertEqual(election_law.elected_by(state, "G"), election_law.PLURALITY)
            self.assertFalse(election_law.ranked_choice(state, "G"))
            self.assertIsNone(election_law.general_runoff(state, "G"))
            self.assertIsNone(election_law.all_party_primary(state, "G"))

    def test_every_entry_cites_its_law(self):
        for where, entry in election_law.ELECTION_LAWS.items():
            self.assertTrue(set(entry) <= {"elect", "runoff", "law", "primary"}, where)
            if "elect" in entry:
                self.assertIn(entry["elect"], election_law.RULES, where)
                self.assertTrue(entry.get("law"), where)
            if entry.get("elect") == election_law.MAJORITY_OR_RUNOFF:
                self.assertRegex(entry["runoff"], r"^\d{4}-\d\d-\d\d$", where)
            else:
                self.assertNotIn("runoff", entry, where)
            if "primary" in entry:
                kind, provision = entry["primary"]
                self.assertIn(kind, ("top-two", "top-four"), where)
                self.assertTrue(provision, where)

    def test_a_race_id_names_its_office(self):
        self.assertEqual(election_law.office_of("H-CA-03-2026"), ("CA", "H"))
        self.assertEqual(election_law.office_of("S-GA-2026"), ("GA", "S"))
        self.assertEqual(election_law.office_of("G-ME-2026"), ("ME", "G"))

    def test_the_runoff_days_are_the_tables(self):
        self.assertEqual(election_law.runoff_days(), ["2026-11-17", "2026-12-01"])
        self.assertFalse(results.general_runoff_held("GA", datetime.date(2026, 12, 1), "S"))
        self.assertTrue(results.general_runoff_held("GA", datetime.date(2026, 12, 2), "S"))
        self.assertTrue(results.general_runoff_held("GU", datetime.date(2026, 11, 18), "H"))
        self.assertFalse(results.general_runoff_held("GA", datetime.date(2026, 12, 2), "G"))

    def test_a_races_badge_reads_its_office(self):
        def kind(state, chamber):
            return races_mod.ballot_kind({"state": state, "chamber": chamber, "year": 2026})
        self.assertEqual(kind("GA", "Senate"), {"generalRunoff": "2026-12-01"})
        self.assertEqual(kind("GU", "House"), {"generalRunoff": "2026-11-17"})
        self.assertEqual(kind("AK", "House"), {"primaryKind": "top-four"})
        self.assertEqual(kind("OH", "House"), {})


class TestRaceLaw(unittest.TestCase):

    def test_the_law_of_a_race_is_its_calendars_and_its_offices(self):
        law = results.race_law("GA", "S", {"primary": "2026-05-19", "runoff": "2026-06-16"},
                               datetime.date(2026, 12, 2))
        self.assertEqual(law.kinds(), dict(has_runoff=True, open_primary=False, runoff_held=True,
                                           general_runoff=True, general_runoff_held=True,
                                           ranked_choice=False))
        self.assertEqual(law.late_round, "2026-12-01")
        law = results.race_law("LA", "H", {"primary": "2026-11-03", "runoff": "2026-12-12"},
                               NIGHT)
        self.assertTrue(law.open_primary)
        self.assertEqual(law.late_round, "2026-12-12")
        self.assertFalse(law.runoff_held)
        self.assertTrue(results.race_law("AK", "H", {}, NIGHT).ranked_choice)
        self.assertFalse(results.race_law("AK", "G", {}, NIGHT).ranked_choice)


if __name__ == "__main__":
    unittest.main()
