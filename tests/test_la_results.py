"""Louisiana's House results, from the Secretary of State's own files (rule 64).

Every feed here is made by the test, in the shape the office published on
2026-11-15 (kyc/la_results.py): nothing is read from the network.
"""

import copy
import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import la_results, results, share, validate  # noqa: E402

AFTER = datetime.date(2026, 11, 15)
DECEMBER_AFTER = datetime.date(2026, 12, 14)
CALENDAR = {("LA", "H"): {"primary": "2026-11-03", "runoff": "2026-12-12"}}
TITLE = "2026 United States House of Representatives elections in Louisiana"


def q(name, party="Republican", withdrew=False):
    return {"name": name, "party": party, "filed": "2026-08-05", "withdrew": withdrew}


# The qualified lists, as kyc/qualified.py reads them.
LISTS = {
    "H-LA-01-2026": [q("Randall Arrington"), q('E. "Liddy" Glass', "No Party"),
                     q("Lauren Jewett", "Democrat"), q("Steve Scalise")],
    "H-LA-05-2026": [q("Stewart Cathey Jr."), q("Gabe Firment"),
                     q('Patricia "Pat" Moore', "Democrat"), q("Michael Echols"),
                     q("Gone Candidate", withdrew=True)],
}

# The choices as the office prints them: (desc, votes, outcome).
LA1 = [("Randall Arrington (REP)", 9776, "Defeated"), ('E. "Liddy" Glass (NOPTY)', 4279, "Defeated"),
       ("Lauren Jewett (DEM)", 89440, "Defeated"), ("Steve Scalise (REP)", 159896, "Elected")]
LA5 = [("Stewart Cathey, Jr. (REP)", 28168, "Defeated"), ('"Gabe" Firment (REP)', 39126, "Runoff"),
       ('Patricia "Pat" Moore (DEM)', 40786, "Runoff"), ("Michael Echols (REP)", 32905, "Defeated")]
FULL = (791, 791, 24, 24)


def race_records(district, choices, reporting=FULL, runoff="1", elect="1", base=0):
    oid = str(70000 + base + district)
    desc = [{"ID": f"{oid}{i}", "Desc": d} for i, (d, _v, _o) in enumerate(choices)]
    votes = [{"ID": f"{oid}{i}", "VoteTotal": str(v), "Outcome": o}
             for i, (_d, v, o) in enumerate(choices)]
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(district, "th")
    race = {"ID": oid, "SpecificTitle": f"U. S. Representative -- {district}{suffix} Congressional "
                                        "District", "NumberToBeElected": elect,
            "CanHaveRunoff": runoff, "Choice": desc}
    pr, pe, ar, ae = reporting
    tally = {"ID": oid, "PrecinctsReporting": str(pr), "PrecinctsExpected": str(pe),
             "NumAbsenteeReporting": str(ar), "NumAbsenteeExpected": str(ae), "Choice": votes}
    return race, tally


def feeds(rounds, official=None):
    """``{file name: text}`` for *rounds* ``{"MM/DD/YYYY": {district: choices or
    (choices, reporting)}}``; *official* the dates the office marks official."""
    official = official or ()
    dates = [{"PKElectionID": str(344 + i), "ElectionDate": day,
              "ResultsOfficial": "1" if day in official else "0", "Order": str(i + 1)}
             for i, day in enumerate(sorted(rounds, reverse=True))]
    # Another election the reader must pass over: found by date, never by id.
    dates.append({"PKElectionID": "343", "ElectionDate": "06/27/2026", "ResultsOfficial": "1"})
    out = {la_results.DATES_FILE: json.dumps({"Dates": {"DefaultElectionDate": "11/03/2026",
                                                        "Date": dates}})}
    for day, seats in rounds.items():
        m, d, y = day.split("/")
        races = [{"ID": "67997", "SpecificTitle": "U. S. Senator", "NumberToBeElected": "1",
                  "CanHaveRunoff": "0", "Choice": [{"ID": "1", "Desc": "Julia Letlow (REP)"}]}]
        tallies = [{"ID": "67997", "PrecinctsReporting": "1", "PrecinctsExpected": "1",
                    "NumAbsenteeReporting": "1", "NumAbsenteeExpected": "1",
                    "Choice": [{"ID": "1", "VoteTotal": "5", "Outcome": "Elected"}]}]
        for district, spec in seats.items():
            choices, reporting = spec if isinstance(spec, tuple) else (spec, FULL)
            race, tally = race_records(district, choices, reporting,
                                       runoff="1" if day == "11/03/2026" else "0",
                                       base=100 if day != "11/03/2026" else 0)
            races.append(race)
            tallies.append(tally)
        out[f"{y}{m}{d}/RacesCandidates_Multiparish.htm"] = json.dumps(
            {"Races": {"WriteTime": f"{y}-{m}-{d}T18:55:18.130", "Race": races}})
        out[f"{y}{m}{d}/Votes_Multiparish.htm"] = json.dumps(
            {"Races": {"VersionDateTime": "1900-01-01T00:00:00", "Race": tallies}})
    return out


def read(rounds, official=None, today=AFTER, asked=None):
    files = feeds(rounds, official)

    def get(name):
        if asked is not None:
            asked.append(name)
        return files[name]
    return la_results.fetch(["2026-11-03", "2026-12-12"], today=today, get=get,
                            log=lambda *_: None)


def row(cid, name, district, party):
    return {"candidate_id": cid, "name": name, "state": "LA", "office": "H",
            "district_number": district, "party": party}


FIELD = {"candidates": [
    row("H0LA01087", "SCALISE, STEVE", 1, "REP"),
    row("H6LA01258", "JEWETT, LAUREN", 1, "DEM"),
    row("H4LA01162", "ARRINGTON, RANDALL", 1, "REP"),
    row("H6LA01999", "NOBODY, NOT ON THE LIST", 1, "DEM"),
    row("H6LA05317", "FIRMENT, GABE", 5, "REP"),
    row("H6LA05341", "MOORE, PATRICIA", 5, "DEM"),
    row("H6LA05103", "CATHEY, STEWART JR", 5, "REP"),
    row("H6LA05101", "ECHOLS, MICHAEL", 5, "REP"),
]}


def page_with(text="Nothing yet."):
    return f"\n==District 1==\n{text}\n==District 5==\nNothing yet.\n"


class NoGap(unittest.TestCase):
    def setUp(self):
        self._gap, results._GAP = results._GAP, 0

    def tearDown(self):
        results._GAP = self._gap

    def build(self, office, today=AFTER, previous=None, page=None, lists=LISTS, aliases=None):
        page = page or page_with()
        return results.build(FIELD, CALENDAR, today=today, log=lambda *_: None,
                             fetch=lambda t: page if t == TITLE else
                             (_ for _ in ()).throw(results.PageMissing(t)),
                             qualified=(copy.deepcopy(lists), {"source": "LA SoS"})
                             if lists is not None else None,
                             previous=previous, office_results=office, aliases=aliases)


# ------------------------------------------------------------------ reading

class TestTheFiles(unittest.TestCase):
    def test_the_election_is_found_by_its_date_and_only_house_races_kept(self):
        office = read({"11/03/2026": {1: LA1, 5: LA5}})
        self.assertEqual(sorted(office["elections"]), ["2026-11-03"])
        e = office["elections"]["2026-11-03"]
        self.assertEqual((e["id"], e["official"]), ("344", False))
        self.assertEqual(sorted(e["races"]), [1, 5])                 # the Senate is not kept
        self.assertEqual(e["races"][5]["title"],
                         "U. S. Representative -- 5th Congressional District")
        self.assertEqual(e["written"], "2026-11-03T18:55:18.130")
        self.assertIn(la_results.url("20261103/Votes_Multiparish.htm"), e["urls"])

    def test_a_round_still_to_come_is_not_asked_for(self):
        asked = []
        read({"11/03/2026": {5: LA5}, "12/12/2026": {5: LA5[1:3]}}, asked=asked)
        self.assertFalse([n for n in asked if n.startswith("20261212")], asked)
        asked = []
        office = read({"11/03/2026": {5: LA5}, "12/12/2026": {5: LA5[1:3]}},
                      today=DECEMBER_AFTER, asked=asked)
        self.assertIn("2026-12-12", office["elections"])
        self.assertTrue([n for n in asked if n.startswith("20261212")])

    def test_names_in_the_lists_form(self):
        self.assertEqual(la_results.list_form('"Clay" Higgins (REP)'), ("Clay Higgins", "REP"))
        self.assertEqual(la_results.list_form("Troy A. Carter, Sr. (DEM)"),
                         ("Troy A. Carter Sr.", "DEM"))
        self.assertEqual(la_results.list_form('Patricia "Pat" Moore (DEM)'),
                         ('Patricia "Pat" Moore', "DEM"))
        self.assertEqual(la_results.list_form("Larry Davis III (REP)"), ("Larry Davis III", "REP"))
        self.assertEqual(la_results.list_form("No Code Here"), (None, None))

    def test_a_feed_whose_shape_changed_concludes_nothing(self):
        good = feeds({"11/03/2026": {5: LA5}})
        broken = [
            (la_results.DATES_FILE, "<html><title>Just a moment...</title></html>"),
            (la_results.DATES_FILE, json.dumps({"Elections": []})),
            (la_results.DATES_FILE, good[la_results.DATES_FILE].replace('"ResultsOfficial": "0"',
                                                                        '"ResultsOfficial": "Y"')),
            ("20261103/RacesCandidates_Multiparish.htm", json.dumps({"Contests": []})),
            ("20261103/Votes_Multiparish.htm",
             good["20261103/Votes_Multiparish.htm"].replace('"VoteTotal"', '"Votes"')),
            ("20261103/Votes_Multiparish.htm",
             good["20261103/Votes_Multiparish.htm"].replace('"PrecinctsExpected"', '"Expected"')),
        ]
        for name, text in broken:
            files = dict(good, **{name: text})
            with self.assertRaises(la_results.OfficeResultsError, msg=name):
                la_results.fetch(["2026-11-03"], today=AFTER, get=files.__getitem__,
                                 log=lambda *_: None)

    def test_a_failure_never_carries_an_address(self):
        self.assertNotIn("10.2.3.4", la_results.failure(OSError("connect to 10.2.3.4 refused")))
        self.assertNotIn("fe80::1", la_results.failure(OSError("fe80::1 unreachable")))


# ------------------------------------------------------------------ the gates

def judge(choices, listed, reporting=FULL, official=False, before=None, runoff=True):
    race = la_results.parse_races(*[feeds({"11/03/2026": {9: (choices, reporting)}})[n]
                                    for n in ("20261103/RacesCandidates_Multiparish.htm",
                                              "20261103/Votes_Multiparish.htm")])["races"][9]
    race["canHaveRunoff"] = runoff
    return la_results.judge(race, listed, official, results.CLOSE_MARGIN, before=before)


class TestTheGates(unittest.TestCase):
    def test_a_majority_elected(self):
        verdict, why = judge(LA1, LISTS["H-LA-01-2026"])
        self.assertIsNone(why)
        self.assertEqual(verdict["Steve Scalise"], "elected")
        self.assertEqual(verdict['E. "Liddy" Glass'], "defeated")

    def test_the_top_two_in_the_runoff(self):
        verdict, why = judge(LA5, LISTS["H-LA-05-2026"])
        self.assertIsNone(why)
        self.assertEqual(sorted(n for n, s in verdict.items() if s == "runoff"),
                         ["Gabe Firment", 'Patricia "Pat" Moore'])
        self.assertNotIn("Gone Candidate", verdict)          # withdrew: not on the ballot

    def test_a_close_second_place_waits_for_the_official_results(self):
        # LA-6 as read on 2026-11-15: 956 votes, 0.36 points of 262,712,
        # between the second runoff place and the third.
        counts = [("Monique Appeaning", "REP", 8139, "Defeated"),
                  ("Chauna Banks", "DEM", 51004, "Runoff"),
                  ("Rufus Craig", "LBT", 3478, "Defeated"),
                  ("Larry Davis III", "REP", 11388, "Defeated"),
                  ('"Rick" Edmonds', "REP", 49420, "Defeated"),
                  ('Patrick "Pat" Forbes', "DEM", 23869, "Defeated"),
                  ('Lindsay "Rubia" Garcia', "DEM", 33632, "Defeated"),
                  ("Michael Mebruer", "REP", 3167, "Defeated"),
                  ("Blake Miguez", "REP", 50376, "Runoff"),
                  ("Stephen Wagley", "REP", 28239, "Defeated")]
        parties = {"REP": "Republican", "DEM": "Democrat", "LBT": "Libertarian"}
        listed = [q(la_results.list_form(f"{n} ({p})")[0], parties[p]) for n, p, _v, _o in counts]
        choices = [(f"{n} ({p})", v, o) for n, p, v, o in counts]
        verdict, why = judge(choices, listed)
        self.assertIsNone(verdict)
        self.assertIn("956 votes, 0.36 points", why)
        self.assertIn("not marked its results official", why)
        verdict, why = judge(choices, listed, official=True)
        self.assertIsNone(why)
        self.assertEqual(verdict["Blake Miguez"], "runoff")
        self.assertEqual(verdict["Rick Edmonds"], "defeated")

    def test_a_close_majority_waits_too(self):
        listed = [q("A Winner"), q("A Loser", "Democrat")]
        close = [("A Winner (REP)", 50300, "Elected"), ("A Loser (DEM)", 49700, "Defeated")]
        verdict, why = judge(close, listed)
        self.assertIsNone(verdict)
        self.assertIn("over half", why)
        self.assertIsNotNone(judge(close, listed, official=True)[0])

    def test_a_leader_close_to_a_majority_waits(self):
        listed = [q("A Leader"), q("A Second", "Democrat"), q("A Third")]
        near = [("A Leader (REP)", 49800, "Runoff"), ("A Second (DEM)", 30000, "Runoff"),
                ("A Third (REP)", 20200, "Defeated")]
        verdict, why = judge(near, listed)
        self.assertIsNone(verdict)
        self.assertIn("short of a majority", why)

    def test_every_precinct_and_absentee_batch_must_be_in(self):
        for reporting in ((790, 791, 24, 24), (791, 791, 23, 24), (0, 0, 0, 0)):
            verdict, why = judge(LA1, LISTS["H-LA-01-2026"], reporting=reporting)
            self.assertIsNone(verdict, reporting)
            self.assertIn("reporting", why)

    def test_an_outcome_it_does_not_know_concludes_nothing(self):
        for word in ("Advances", "", "Winner"):
            choices = [LA1[0], LA1[1], LA1[2], ("Steve Scalise (REP)", 159896, word)]
            verdict, why = judge(choices, LISTS["H-LA-01-2026"])
            self.assertIsNone(verdict, word)
            self.assertIn("Outcome", why)

    def test_a_name_the_list_lacks_holds_the_race(self):
        choices = LA1[:3] + [("Peter Griffin (REP)", 159896, "Elected")]
        verdict, why = judge(choices, LISTS["H-LA-01-2026"] + [q("Peter Griffon")])
        self.assertIsNone(verdict)
        self.assertIn("Peter Griffin", why)
        # Withdrawn from the list is not on it.
        listed = [dict(e, withdrew=e["name"] == "Steve Scalise") for e in LISTS["H-LA-01-2026"]]
        self.assertIsNone(judge(LA1, listed)[0])

    def test_a_list_name_the_results_lack_holds_the_race(self):
        verdict, why = judge(LA1, LISTS["H-LA-01-2026"] + [q("Missing Person")])
        self.assertIsNone(verdict)
        self.assertIn("Missing Person", why)

    def test_a_party_the_list_does_not_give_holds_the_race(self):
        choices = LA1[:3] + [("Steve Scalise (DEM)", 159896, "Elected")]
        self.assertIn("on the list", judge(choices, LISTS["H-LA-01-2026"])[1])
        choices = LA1[:3] + [("Steve Scalise (XYZ)", 159896, "Elected")]
        self.assertIn("party code", judge(choices, LISTS["H-LA-01-2026"])[1])

    def test_outcomes_the_counts_do_not_give_hold_the_race(self):
        listed = LISTS["H-LA-01-2026"]
        cases = [
            # Elected without a majority.
            [LA1[0], LA1[1], ("Lauren Jewett (DEM)", 159000, "Defeated"),
             ("Steve Scalise (REP)", 159896, "Elected")],
            # Two elected.
            [LA1[0], LA1[1], ("Lauren Jewett (DEM)", 89440, "Elected"), LA1[3]],
            # A runoff that is not the two highest.
            [("Randall Arrington (REP)", 9776, "Runoff"), LA1[1],
             ("Lauren Jewett (DEM)", 89440, "Runoff"), ("Steve Scalise (REP)", 100000, "Defeated")],
            # A runoff for someone holding a majority.
            [LA1[0], LA1[1], ("Lauren Jewett (DEM)", 89440, "Runoff"),
             ("Steve Scalise (REP)", 159896, "Runoff")],
            # Nobody called.
            [(d, v, "Defeated") for d, v, _o in LA1],
        ]
        for choices in cases:
            verdict, why = judge(choices, listed)
            self.assertIsNone(verdict, choices)
            self.assertTrue(why)

    def test_the_december_round_is_between_the_two(self):
        first, _ = judge(LA5, LISTS["H-LA-05-2026"])
        two = [('"Gabe" Firment (REP)', 90000, "Elected"),
               ('Patricia "Pat" Moore (DEM)', 80000, "Defeated")]
        verdict, why = judge(two, LISTS["H-LA-05-2026"], before=first, runoff=False)
        self.assertIsNone(why)
        self.assertEqual(verdict, {"Gabe Firment": "elected", 'Patricia "Pat" Moore': "defeated"})
        other = [('"Gabe" Firment (REP)', 90000, "Elected"), ("Michael Echols (REP)", 80000,
                                                                "Defeated")]
        self.assertIn("first round's two",
                      judge(other, LISTS["H-LA-05-2026"], before=first, runoff=False)[1])
        # A December "runoff" is no result.
        self.assertIsNone(judge([(d, v, "Runoff") for d, v, _o in two], LISTS["H-LA-05-2026"],
                                before=first, runoff=False)[0])


# ------------------------------------------------------------------ the race

class TestTheRace(NoGap):
    def test_an_elected_winner_is_the_races_result_and_credits_the_office(self):
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "office")
        self.assertEqual(race["calledBy"], "office")
        self.assertEqual(race["status"]["H0LA01087"], "elected")
        self.assertEqual(race["status"]["H6LA01258"], "defeated")
        self.assertEqual(race["unmatched"], {'E. "Liddy" Glass': "defeated"})
        self.assertEqual(race["decided"], {"general": True, "parties": ["all"]})
        self.assertFalse(race["office"]["official"])
        self.assertEqual(race["office"]["source"],
                         "the Louisiana Secretary of State's election results, unofficial until "
                         "its canvass")
        # What the read relied on is kept, in an entry of its own.
        record = cache["officeResults"]["races"]["H-LA-01-2026"]["2026-11-03"]
        self.assertEqual(record["choices"][3], {"name": "Steve Scalise (REP)", "votes": 159896,
                                                "outcome": "Elected"})
        self.assertEqual(record["reporting"], {"precincts": [791, 791], "absentee": [24, 24]})
        self.assertEqual(cache["officeResults"]["elections"]["2026-11-03"]["official"], False)
        people = [{"id": "FEC_" + cid, "fecCandidateId": cid, "isCandidate": True,
                   "source": "fec-field", "name": name, "party": party, "state": "LA",
                   "chamber": "House (Candidate)", "districtNum": 1}
                  for cid, name, party in (("H0LA01087", "Steve Scalise", "Republican"),
                                           ("H6LA01999", "Not Ontheist", "Democrat"))]
        results.apply_cache(people, cache, field=FIELD)
        scalise, other = people
        self.assertEqual((scalise["raceStatus"], scalise["raceStatusSource"]),
                         ("elected", "office"))
        self.assertIn("unofficial until its canvass", scalise["raceStatusSourceName"])
        # Not on the ballot is still the qualified list's word.
        self.assertEqual((other["raceStatus"], other["raceStatusSource"]),
                         ("unlisted", "qualified"))
        summary = results.race_summary(cache, "H-LA-01-2026")
        self.assertTrue(summary["fromOfficeResults"])
        self.assertFalse(summary["fromQualifiedList"])
        self.assertEqual(summary["sourceUrl"], la_results.PAGE)
        self.assertEqual(summary["otherDefeated"], ['E. "Liddy" Glass'])
        # The share pages credit the office, never Wikipedia.
        self.assertEqual(share._race_source("elected", "office", scalise["raceStatusSourceName"]),
                         scalise["raceStatusSourceName"])
        self.assertEqual(share.ballot_source({"results": summary}),
                         "per " + scalise["raceStatusSourceName"])
        scalise.update(officeLabel="House • LA-1", raceId="H-LA-01-2026")
        _lead, description, _words = share.describe(scalise, {scalise["id"]: scalise}, {},
                                                    share.ResultsDay(AFTER.isoformat()))
        self.assertIn("Elected in November, per the Louisiana Secretary of State's election "
                      "results, unofficial until its canvass.", description)
        self.assertNotIn("Wikipedia", description)
        self.assertEqual(validate.check_results_pages(cache) and
                         [i.code for i in validate.check_results_pages(cache)
                          if i.code.startswith("office")], [])

    def test_the_top_two_go_to_the_december_round(self):
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["status"]["H6LA05317"], "runoff")
        self.assertEqual(race["status"]["H6LA05341"], "runoff")
        self.assertEqual(race["status"]["H6LA05101"], "defeated")
        self.assertNotIn("calledBy", race)

    def test_a_held_race_keeps_what_it_had_and_says_why(self):
        partial = {1: (LA1, (500, 522, 8, 8)), 5: LA5}
        cache = self.build(read({"11/03/2026": partial}))
        self.assertEqual(cache["races"]["H-LA-01-2026"]["source"], "qualified")
        self.assertIn("reporting", cache["officeResults"]["held"]["H-LA-01-2026"])
        issues = {i.code: i for i in validate.check_results_pages(cache)}
        self.assertTrue(any("H-LA-01-2026" in d for d in issues["office-result-held"].detail))
        # A race a read decided keeps that read while a later one holds.
        decided = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        later = self.build(read({"11/03/2026": partial}), previous=decided)
        self.assertEqual(later["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        self.assertEqual(later["races"]["H-LA-01-2026"]["office"]["read"], AFTER.isoformat())
        self.assertIn("H-LA-01-2026", later["officeResults"]["kept"])

    def test_a_close_race_waits_and_is_released_when_official(self):
        close = [("Randall Arrington (REP)", 9776, "Defeated"),
                 ('E. "Liddy" Glass (NOPTY)', 1000, "Defeated"),
                 ("Lauren Jewett (DEM)", 120000, "Defeated"),
                 ("Steve Scalise (REP)", 132000, "Elected")]
        held = self.build(read({"11/03/2026": {1: close}}))
        self.assertEqual(held["races"]["H-LA-01-2026"]["source"], "qualified")
        self.assertIn("over half", held["officeResults"]["held"]["H-LA-01-2026"])
        released = self.build(read({"11/03/2026": {1: close}}, official=("11/03/2026",)))
        race = released["races"]["H-LA-01-2026"]
        self.assertEqual(race["status"]["H0LA01087"], "elected")
        self.assertTrue(race["office"]["official"])
        self.assertEqual(race["office"]["source"],
                         "the Louisiana Secretary of State's official election results")

    def test_a_failed_read_keeps_the_last(self):
        decided = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        failed = self.build({"unread": "URLError: timed out"}, previous=decided)
        self.assertEqual(failed["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        self.assertEqual(failed["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "runoff")
        self.assertTrue(failed["officeResults"]["carried"])
        self.assertEqual(failed["officeResults"]["read"], AFTER.isoformat())
        codes = [i.code for i in validate.check_results_pages(failed)]
        self.assertIn("office-results-unread", codes)
        # No read at all (none attempted) keeps it too; and with no previous,
        # a failed read leaves the qualified list.
        self.assertEqual(self.build(None, previous=decided)["races"]["H-LA-01-2026"]["source"],
                         "office")
        self.assertEqual(self.build({"unread": "x"})["races"]["H-LA-01-2026"]["source"],
                         "qualified")
        # A failed page never takes it away: the page is missing here.
        gone = results.build(FIELD, CALENDAR, today=AFTER, log=lambda *_: None,
                             fetch=lambda t: (_ for _ in ()).throw(OSError("timeout")),
                             qualified=None, previous=decided,
                             office_results={"unread": "x"})
        self.assertEqual(gone["races"]["H-LA-01-2026"]["source"], "office")

    def test_with_no_list_to_check_the_names_against_it_concludes_nothing(self):
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}), lists=None)
        self.assertNotIn("H-LA-01-2026", cache["races"])
        # With a last read, it keeps that read, and says why nothing new is.
        decided = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        later = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}), lists=None, previous=decided)
        self.assertEqual(later["races"]["H-LA-01-2026"]["source"], "office")
        self.assertIn("qualified list", later["officeResults"]["held"]["H-LA-01-2026"])

    def test_a_page_that_names_someone_else_shows_neither(self):
        box = "\n".join([
            "{{Election box begin no change", "| title = Nonpartisan primary results", "}}",
            "{{Election box winning candidate with party link no change",
            "| party = Democratic Party (United States)", "| candidate = Lauren Jewett",
            "| votes = 159,896", "}}",
            "{{Election box candidate with party link no change",
            "| party = Republican Party (United States)", "| candidate = Steve Scalise",
            "| votes = 89,440", "}}",
            "{{Election box total no change", "| votes = 249,336", "}}",
            "{{Election box end}}"])
        cache = self.build(read({"11/03/2026": {1: LA1}}), page=page_with(box))
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "qualified")
        self.assertIn("H-LA-01-2026", cache["officeResults"]["disagree"])
        codes = [i.code for i in validate.check_results_pages(cache)]
        self.assertIn("office-result-disagrees", codes)
        # A page that agrees is not a disagreement: the office's result stands.
        agrees = box.replace("Lauren Jewett", "X").replace("Steve Scalise", "Lauren Jewett") \
            .replace("X", "Steve Scalise")
        cache = self.build(read({"11/03/2026": {1: LA1}}), page=page_with(agrees))
        self.assertEqual(cache["races"]["H-LA-01-2026"]["source"], "office")
        self.assertFalse(cache["officeResults"]["disagree"])

    def test_the_december_round_decides_the_two(self):
        two = [('"Gabe" Firment (REP)', 90000, "Elected"),
               ('Patricia "Pat" Moore (DEM)', 80000, "Defeated")]
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}, "12/12/2026": {5: two}},
                                today=DECEMBER_AFTER), today=DECEMBER_AFTER)
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["status"]["H6LA05317"], "elected")
        self.assertEqual(race["status"]["H6LA05341"], "defeated")
        self.assertEqual(race["status"]["H6LA05101"], "defeated")        # the first round's
        self.assertEqual(race["decidedIn"], {"date": "2026-12-12", "open": True,
                                             "ids": ["H6LA05317", "H6LA05341"]})
        self.assertEqual(race["office"]["rounds"], ["2026-11-03", "2026-12-12"])
        profile = {"id": "FEC_H6LA05317", "fecCandidateId": "H6LA05317", "isCandidate": True,
                   "source": "fec-field", "name": "Gabe Firment", "party": "Republican",
                   "state": "LA", "chamber": "House (Candidate)", "districtNum": 5}
        results.apply_cache([profile], cache)
        self.assertEqual(profile["raceStatusDecided"], {"date": "2026-12-12", "open": True})
        # December still counting: the first round stands ...
        counting = self.build(read({"11/03/2026": {5: LA5},
                                    "12/12/2026": {5: (two, (10, 791, 0, 24))}},
                                   today=DECEMBER_AFTER), today=DECEMBER_AFTER)
        self.assertEqual(counting["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "runoff")
        self.assertIn("2026-12-12", counting["officeResults"]["held"]["H-LA-05-2026"])
        # ... unless the last read had December's result, which it keeps.
        kept = self.build(read({"11/03/2026": {5: LA5},
                                "12/12/2026": {5: (two, (10, 791, 0, 24))}},
                               today=DECEMBER_AFTER), today=DECEMBER_AFTER, previous=cache)
        self.assertEqual(kept["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "elected")

    def test_names_reach_filings_as_the_lists_do(self):
        # A roster alias ties a list name the matcher cannot fit to its filing.
        lists = dict(LISTS, **{"H-LA-01-2026": [
            q("Randall Arrington"), q('E. "Liddy" Glass', "No Party"),
            q("Lauren Jewett", "Democrat"), q("Buddy Scalise")]})
        choices = LA1[:3] + [("Buddy Scalise (REP)", 159896, "Elected")]
        cache = self.build(read({"11/03/2026": {1: choices}}), lists=lists,
                           aliases={"H-LA-01-2026": [("Buddy Scalise", "H0LA01087")]})
        self.assertEqual(cache["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")


if __name__ == "__main__":
    unittest.main()
