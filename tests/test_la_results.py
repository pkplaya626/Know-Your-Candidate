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
        # Elected while another leads.
        cases.append([LA1[0], LA1[1], ("Lauren Jewett (DEM)", 159896, "Defeated"),
                      ("Steve Scalise (REP)", 89440, "Elected")])
        for choices in cases:
            # Official or not: no margin gate stands in for these.
            for official in (False, True):
                verdict, why = judge(choices, listed, official=official)
                self.assertIsNone(verdict, (choices, official))
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

    def test_a_withdrawal_is_the_lists_word_beside_a_like_name(self):
        # The list says John Smith withdrew; a John Smyth with no filing is on
        # the ballot. As on the qualified list's own race, the withdrawal
        # stands: the office's results are not a page that may have missed him.
        lists = dict(LISTS, **{"H-LA-05-2026": LISTS["H-LA-05-2026"] + [
            q("John Smith", withdrew=True), q("John Smyth")]})
        field = {"candidates": FIELD["candidates"] + [row("H6LA05555", "SMITH, JOHN", 5, "REP")]}
        choices = LA5 + [("John Smyth (REP)", 1000, "Defeated")]
        cache = results.build(field, CALENDAR, today=AFTER, log=lambda *_: None,
                              fetch=lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                              qualified=(lists, {"source": "LA SoS"}),
                              office_results=read({"11/03/2026": {5: choices}}))
        self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "office")
        smith = {"id": "FEC_H6LA05555", "fecCandidateId": "H6LA05555", "isCandidate": True,
                 "source": "fec-field", "name": "John Smith", "party": "Republican",
                 "state": "LA", "chamber": "House (Candidate)", "districtNum": 5}
        results.apply_cache([smith], cache, field=field)
        self.assertEqual(smith.get("raceStatus"), "withdrawn")
        self.assertNotIn("maybeNamed", smith)
        self.assertEqual(smith["raceStatusSource"], "qualified")

    def test_names_reach_filings_as_the_lists_do(self):
        # A roster alias ties a list name the matcher cannot fit to its filing.
        lists = dict(LISTS, **{"H-LA-01-2026": [
            q("Randall Arrington"), q('E. "Liddy" Glass', "No Party"),
            q("Lauren Jewett", "Democrat"), q("Buddy Scalise")]})
        choices = LA1[:3] + [("Buddy Scalise (REP)", 159896, "Elected")]
        cache = self.build(read({"11/03/2026": {1: choices}}), lists=lists,
                           aliases={"H-LA-01-2026": [("Buddy Scalise", "H0LA01087")]})
        self.assertEqual(cache["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")


# ------------------------------------------------------------------ the review's follow-ups

def read_files(files, today=AFTER):
    return la_results.fetch(["2026-11-03", "2026-12-12"], today=today, get=files.__getitem__,
                            log=lambda *_: None)


def restamp(files, day, written=None, version=None, drop_written=False):
    """*files* with *day*'s races file's WriteTime, or votes file's
    VersionDateTime, set as given (or the WriteTime taken out)."""
    files = dict(files)
    races_name, votes_name = (f"{day}/RacesCandidates_Multiparish.htm",
                              f"{day}/Votes_Multiparish.htm")
    races = json.loads(files[races_name])
    if drop_written:
        races["Races"].pop("WriteTime")
    elif written is not None:
        races["Races"]["WriteTime"] = written
    files[races_name] = json.dumps(races)
    if version is not None:
        votes = json.loads(files[votes_name])
        votes["Races"]["VersionDateTime"] = version
        files[votes_name] = json.dumps(votes)
    return files


# LA-1 the other way round: a result a stale file could carry.
LA1_SWAPPED = [LA1[0], LA1[1], ("Lauren Jewett (DEM)", 159896, "Elected"),
               ("Steve Scalise (REP)", 89440, "Defeated")]


class TestAFileOlderThanTheLastRead(NoGap):
    """The three files are fetched one by one: a cached races or votes file
    beside a fresh ElectionDates.htm would pair old counts with a new
    official flag. A file written before the one the last read relied on
    concludes nothing for its round (rule 8)."""

    def test_an_older_write_time_keeps_the_last_read(self):
        decided = self.build(read_files(restamp(feeds({"11/03/2026": {1: LA1}}), "20261103",
                                                written="2026-11-14T18:55:18.130")))
        self.assertEqual(decided["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        older = restamp(feeds({"11/03/2026": {1: LA1_SWAPPED}}, official=("11/03/2026",)),
                        "20261103", written="2026-11-01T18:55:18.130")
        later = self.build(read_files(older), previous=decided)
        race = later["races"]["H-LA-01-2026"]
        self.assertEqual(race["status"]["H0LA01087"], "elected")       # the last read stands
        self.assertNotEqual(race["status"].get("H6LA01258"), "elected")
        self.assertIn("H-LA-01-2026", later["officeResults"]["kept"])
        why = later["officeResults"]["held"]["H-LA-01-2026"]
        self.assertIn("before the 2026-11-14T18:55:18.130 of the last read", why)
        # The newer read stays the baseline, and the stale stamp is recorded.
        e = later["officeResults"]["elections"]["2026-11-03"]
        self.assertEqual(e["written"], "2026-11-14T18:55:18.130")
        self.assertFalse(e["official"])
        self.assertEqual(e["staleRead"]["written"], "2026-11-01T18:55:18.130")
        # The older file's counts are not kept as this read's.
        record = later["officeResults"]["races"]["H-LA-01-2026"]["2026-11-03"]
        self.assertEqual(record["choices"][3]["outcome"], "Elected")
        issues = {i.code: i for i in validate.check_results_pages(later)}
        self.assertTrue(any("H-LA-01-2026" in d for d in issues["office-result-held"].detail))
        # And again on the next run with the same old file: still held.
        again = self.build(read_files(older), previous=later)
        self.assertEqual(again["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        # A newer file is read as ever.
        newer = restamp(feeds({"11/03/2026": {1: LA1_SWAPPED}}, official=("11/03/2026",)),
                        "20261103", written="2026-11-20T10:00:00")
        fresh = self.build(read_files(newer), previous=again)
        self.assertEqual(fresh["races"]["H-LA-01-2026"]["status"]["H6LA01258"], "elected")

    def test_a_close_race_is_not_released_by_an_old_file_beside_the_official_flag(self):
        close = [("Randall Arrington (REP)", 9776, "Defeated"),
                 ('E. "Liddy" Glass (NOPTY)', 1000, "Defeated"),
                 ("Lauren Jewett (DEM)", 120000, "Defeated"),
                 ("Steve Scalise (REP)", 132000, "Elected")]
        held = self.build(read_files(restamp(feeds({"11/03/2026": {1: close}}), "20261103",
                                             written="2026-11-14T18:55:18.130")))
        self.assertEqual(held["races"]["H-LA-01-2026"]["source"], "qualified")
        stale = restamp(feeds({"11/03/2026": {1: close}}, official=("11/03/2026",)), "20261103",
                        written="2026-11-04T09:00:00")
        later = self.build(read_files(stale), previous=held)
        self.assertEqual(later["races"]["H-LA-01-2026"]["source"], "qualified")
        self.assertIn("before the", later["officeResults"]["held"]["H-LA-01-2026"])

    def test_an_older_votes_version_or_a_lost_write_time_concludes_nothing(self):
        first = restamp(feeds({"11/03/2026": {1: LA1}}), "20261103",
                        version="2026-11-14T00:00:00")
        decided = self.build(read_files(first))
        older = restamp(feeds({"11/03/2026": {1: LA1_SWAPPED}}), "20261103",
                        version="1900-01-01T00:00:00")
        later = self.build(read_files(older), previous=decided)
        self.assertEqual(later["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        self.assertIn("VersionDateTime", later["officeResults"]["held"]["H-LA-01-2026"])
        lost = restamp(feeds({"11/03/2026": {1: LA1_SWAPPED}}), "20261103", drop_written=True)
        later = self.build(read_files(lost), previous=decided)
        self.assertEqual(later["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        self.assertIn("WriteTime", later["officeResults"]["held"]["H-LA-01-2026"])

    def test_an_older_december_file_keeps_decembers_last_read(self):
        two = [('"Gabe" Firment (REP)', 90000, "Elected"),
               ('Patricia "Pat" Moore (DEM)', 80000, "Defeated")]
        swapped = [('"Gabe" Firment (REP)', 80000, "Defeated"),
                   ('Patricia "Pat" Moore (DEM)', 90000, "Elected")]
        decided = self.build(read_files(restamp(
            feeds({"11/03/2026": {5: LA5}, "12/12/2026": {5: two}}), "20261212",
            written="2026-12-13T08:00:00"), today=DECEMBER_AFTER), today=DECEMBER_AFTER)
        self.assertEqual(decided["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "elected")
        later = self.build(read_files(restamp(
            feeds({"11/03/2026": {5: LA5}, "12/12/2026": {5: swapped}}), "20261212",
            written="2026-12-12T23:00:00"), today=DECEMBER_AFTER), today=DECEMBER_AFTER,
            previous=decided)
        race = later["races"]["H-LA-05-2026"]
        self.assertEqual(race["status"]["H6LA05317"], "elected")
        self.assertEqual(race["status"]["H6LA05341"], "defeated")
        self.assertIn("2026-12-12", later["officeResults"]["held"]["H-LA-05-2026"])
        self.assertEqual(later["officeResults"]["races"]["H-LA-05-2026"]["2026-12-12"]
                         ["choices"][0]["outcome"], "Elected")

    def test_stamps_compared(self):
        self.assertIsNone(la_results.older("2026-11-14T18:55:18.130", None, "x"))
        self.assertIsNone(la_results.older("2026-11-14T18:55:18.130",
                                           "2026-11-14T18:55:18.130", "x"))
        self.assertIsNone(la_results.older("2026-11-15T01:00:00", "2026-11-14T18:55:18.130", "x"))
        self.assertIn("before", la_results.older("2026-11-13T00:00:00", "2026-11-14T00:00:00", "x"))
        self.assertIn("nothing to tell", la_results.older(None, "2026-11-14T00:00:00", "x"))
        self.assertIn("nothing to tell", la_results.older("soon", "2026-11-14T00:00:00", "x"))


class TestTheGatesNoTestHeld(unittest.TestCase):
    """Gates the first tests passed without: each is undone and caught."""

    def race(self, choices, **change):
        race = la_results.parse_races(*[feeds({"11/03/2026": {9: choices}})[n] for n in (
            "20261103/RacesCandidates_Multiparish.htm", "20261103/Votes_Multiparish.htm")])[
            "races"][9]
        race.update(change)
        return race

    def test_a_race_that_elects_two_concludes_nothing(self):
        verdict, why = la_results.judge(self.race(LA1, toElect="2"), LISTS["H-LA-01-2026"],
                                        True, results.CLOSE_MARGIN)
        self.assertIsNone(verdict)
        self.assertIn("elects '2'", why)

    def test_a_first_round_that_cannot_go_to_a_runoff_concludes_nothing(self):
        verdict, why = la_results.judge(self.race(LA1, canHaveRunoff=False),
                                        LISTS["H-LA-01-2026"], True, results.CLOSE_MARGIN)
        self.assertIsNone(verdict)
        self.assertIn("cannot go to a runoff", why)

    def test_two_choices_of_one_name_say_so(self):
        # '"Steve" Scalise' and "Steve Scalise" are one list name: the read
        # says why it holds, not only that the outcomes do not add up.
        choices = [('"Steve" Scalise (REP)', 10, "Defeated")] + LA1
        verdict, why = la_results.judge(self.race(choices), LISTS["H-LA-01-2026"], True,
                                        results.CLOSE_MARGIN)
        self.assertIsNone(verdict)
        self.assertEqual(why, "two choices carry one name")


class TestTheOfficesResultBesideOtherSources(NoGap):
    def test_a_certified_list_naming_the_seat_leaves_the_offices_result_alone(self):
        certified = {"LA": {"source": "LA", "url": "https://x", "fetched": "2026-11-14",
                            "complete": True,
                            "races": {"H-LA-01-2026": [{"name": "Lauren Jewett",
                                                        "party": "Democratic",
                                                        "kind": "ballot"}]}}}
        cache = results.build(FIELD, CALENDAR, today=AFTER, log=lambda *_: None,
                              fetch=lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                              qualified=(copy.deepcopy(LISTS), {"source": "LA SoS"}),
                              certified=certified,
                              office_results=read({"11/03/2026": {1: LA1, 5: LA5}}))
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "office")
        self.assertEqual(race["status"]["H0LA01087"], "elected")
        self.assertEqual(race["status"]["H6LA01258"], "defeated")
        self.assertNotIn("certifiedIds", race)

    def runoff_page(self, second):
        rows = [("Gabe Firment", "Republican", "39,126", True),
                (second, "Democratic", "40,786", True),
                ("Michael Echols", "Republican", "32,905", False),
                ("Stewart Cathey Jr.", "Republican", "28,168", False)]
        box = ["{{Election box begin no change", "| title = Nonpartisan primary results", "}}"]
        for name, party, votes, won in rows:
            box += ["{{Election box " + ("winning candidate" if won else "candidate") +
                    " with party link no change", f"| party = {party} Party (United States)",
                    f"| candidate = {name}", f"| votes = {votes}", "}}"]
        box += ["{{Election box total no change", "| votes = 140,985", "}}",
                "{{Election box end}}"]
        return "\n==District 1==\nNothing yet.\n==District 5==\n" + "\n".join(box) + "\n"

    def test_a_page_writing_a_list_names_short_form_agrees(self):
        # The page writes the runoff's "Bubba Moore", which the matcher fits
        # to no filing (no nickname table holds it); the office's list name
        # for her filing, MOORE, PATRICIA, is 'Patricia "Bubba" Moore'. One
        # person: the office's result stands.
        lists = dict(LISTS, **{"H-LA-05-2026": [
            dict(e, name='Patricia "Bubba" Moore') if e["name"].endswith("Moore") else e
            for e in LISTS["H-LA-05-2026"]]})
        choices = [('Patricia "Bubba" Moore (DEM)', v, o) if d.endswith("Moore (DEM)") else
                   (d, v, o) for d, v, o in LA5]
        office = read({"11/03/2026": {5: choices}})
        page = self.build(None, page=self.runoff_page("Bubba Moore"), lists=lists)
        self.assertEqual(page["races"]["H-LA-05-2026"]["unmatched"], {"Bubba Moore": "runoff"})
        cache = self.build(office, page=self.runoff_page("Bubba Moore"), lists=lists)
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["source"], "office")
        self.assertEqual(race["status"]["H6LA05341"], "runoff")
        self.assertFalse(cache["officeResults"]["disagree"])
        # Someone else in her place is still a disagreement: neither is shown.
        cache = self.build(office, page=self.runoff_page("Bubba Smith"), lists=lists)
        self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "qualified")
        self.assertIn("H-LA-05-2026", cache["officeResults"]["disagree"])


# -------------------------------------------------- the second review's follow-ups

def box(rows, title="Nonpartisan primary results", total=249336):
    """A page's election box: *rows* ``(name, party, votes, marked)``."""
    out = ["{{Election box begin no change", f"| title = {title}", "}}"]
    for name, party, votes, won in rows:
        out += ["{{Election box " + ("winning candidate" if won else "candidate") +
                " with party link no change", f"| party = {party} Party (United States)",
                f"| candidate = {name}", f"| votes = {votes}", "}}"]
    out += ["{{Election box total no change", f"| votes = {total:,}", "}}",
            "{{Election box end}}"]
    return "\n".join(out)


TWO = [('"Gabe" Firment (REP)', 90000, "Elected"),
       ('Patricia "Pat" Moore (DEM)', 80000, "Defeated")]


class TestDecemberIsNotUndoneByAReadThatLacksIt(NoGap):
    """Rule 8: a dates file that lists no December election, or a December
    file with no race for the seat, after a read that had December's result,
    concludes nothing for December. It undid LA-5's result without a word."""

    def decided(self):
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}, "12/12/2026": {5: TWO}},
                                today=DECEMBER_AFTER), today=DECEMBER_AFTER)
        self.assertEqual(cache["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "elected")
        return cache

    def assert_kept(self, later, why):
        race = later["races"]["H-LA-05-2026"]
        self.assertEqual(race["status"]["H6LA05317"], "elected")
        self.assertEqual(race["status"]["H6LA05341"], "defeated")
        self.assertEqual(race["decidedIn"]["date"], "2026-12-12")
        self.assertIn("H-LA-05-2026", later["officeResults"]["kept"])
        held = later["officeResults"]["held"]["H-LA-05-2026"]
        self.assertIn(why, held)
        self.assertTrue(held.startswith("2026-12-12: "), held)
        # The December record the result stands on is kept with it.
        self.assertEqual(later["officeResults"]["races"]["H-LA-05-2026"]["2026-12-12"]
                         ["choices"][0]["outcome"], "Elected")
        issues = {i.code: i for i in validate.check_results_pages(later)}
        self.assertTrue(any(d.startswith("H-LA-05-2026: 2026-12-12")
                            for d in issues["office-result-held"].detail))
        # LA-1, which December does not touch, is read as ever.
        self.assertNotIn("H-LA-01-2026", later["officeResults"]["held"])
        self.assertEqual(later["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")

    def test_a_dates_file_without_december_keeps_decembers_result(self):
        decided = self.decided()
        later = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, previous=decided)
        self.assert_kept(later, "the office lists no results for 2026-12-12")
        # The December record is said to be the last read's, not this one's.
        found = decided["officeResults"]["read"]
        self.assertTrue(found)
        self.assertEqual(later["officeResults"]["races"]["H-LA-05-2026"]["2026-12-12"]
                         ["keptFrom"], found)
        # The December election's record stays the baseline a stale file is
        # compared with.
        e = later["officeResults"]["elections"]["2026-12-12"]
        self.assertEqual(e["written"], "2026-12-12T18:55:18.130")
        self.assertEqual(e["unlistedOn"], DECEMBER_AFTER.isoformat())
        # And again the next day: still kept, from the kept record.
        again = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, previous=later)
        self.assert_kept(again, "the office lists no results for 2026-12-12")
        self.assertEqual(again["officeResults"]["races"]["H-LA-05-2026"]["2026-12-12"]
                         ["keptFrom"], found)

    def test_a_december_file_without_the_seat_keeps_decembers_result(self):
        decided = self.decided()
        later = self.build(read({"11/03/2026": {1: LA1, 5: LA5}, "12/12/2026": {}},
                                today=DECEMBER_AFTER), today=DECEMBER_AFTER, previous=decided)
        self.assert_kept(later, "the office's 2026-12-12 results hold no race for district 5")

    def test_with_no_december_result_before_a_missing_december_changes_nothing(self):
        # No December verdict was ever read: the first round's runoff stands,
        # and nothing is held.
        nov = self.build(read({"11/03/2026": {5: LA5}}, today=DECEMBER_AFTER),
                         today=DECEMBER_AFTER)
        later = self.build(read({"11/03/2026": {5: LA5}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, previous=nov)
        self.assertEqual(later["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "runoff")
        self.assertNotIn("H-LA-05-2026", later["officeResults"]["held"])


CLOSE = [("Randall Arrington (REP)", 9000, "Defeated"),
         ('E. "Liddy" Glass (NOPTY)', 4000, "Defeated"),
         ("Lauren Jewett (DEM)", 110000, "Defeated"),
         ("Steve Scalise (REP)", 125000, "Elected")]


class TestAPageBesideAHeldRound(NoGap):
    """Where the office's files are read whole but a gate holds the seat, its
    counts still say who leads: a page's call they contradict is a
    disagreement, and a page's call of a seat held for its close margin waits
    for the office's official results. A page that marked Lauren Jewett beside
    the office's 50.4% for Scalise was shown, credited to Wikipedia."""

    def page(self, rows, five=None, total=248000):
        one = box(rows, total=total) if rows else "Nothing yet."
        return f"\n==District 1==\n{one}\n==District 5==\n{five or 'Nothing yet.'}\n"

    def test_a_page_winner_the_close_counts_do_not_lead_shows_neither(self):
        cache = self.build(read({"11/03/2026": {1: CLOSE}}),
                           page=self.page([("Lauren Jewett", "Democratic", "125,000", True),
                                           ("Steve Scalise", "Republican", "110,000", False)]))
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "qualified")
        self.assertNotEqual(race["status"].get("H6LA01258"), "elected")
        self.assertIn("H-LA-01-2026", cache["officeResults"]["disagree"])
        self.assertIn("over half", cache["officeResults"]["held"]["H-LA-01-2026"])
        codes = [i.code for i in validate.check_results_pages(cache)]
        self.assertIn("office-result-disagrees", codes)

    def test_a_page_call_of_a_close_seat_waits_for_the_official_results(self):
        agrees = [("Steve Scalise", "Republican", "125,000", True),
                  ("Lauren Jewett", "Democratic", "110,000", False)]
        # The page's call alone, with no office read: shown, as ever.
        alone = self.build(None, page=self.page(agrees))
        self.assertEqual(alone["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        cache = self.build(read({"11/03/2026": {1: CLOSE}}), page=self.page(agrees))
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "qualified")
        self.assertNotEqual(race["status"].get("H0LA01087"), "elected")
        self.assertIn("H-LA-01-2026", cache["officeResults"]["pageHeld"])
        self.assertFalse(cache["officeResults"]["disagree"])
        held = cache["officeResults"]["held"]["H-LA-01-2026"]
        self.assertIn("over half", held)
        self.assertIn("the page's call", held)
        issues = {i.code: i for i in validate.check_results_pages(cache)}
        self.assertTrue(any("the page's call" in d
                            for d in issues["office-result-held"].detail))
        # Once official, the office's result is shown, its own.
        released = self.build(read({"11/03/2026": {1: CLOSE}}, official=("11/03/2026",)),
                              page=self.page(agrees))
        self.assertEqual(released["races"]["H-LA-01-2026"]["source"], "office")
        self.assertEqual(released["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")

    def test_a_page_winner_partial_counts_do_not_lead_shows_neither(self):
        partial = {1: (LA1, (100, 522, 8, 8))}
        cache = self.build(read({"11/03/2026": partial}),
                           page=self.page([("Lauren Jewett", "Democratic", "159,896", True),
                                           ("Steve Scalise", "Republican", "89,440", False)],
                                          total=249336))
        self.assertEqual(cache["races"]["H-LA-01-2026"]["source"], "qualified")
        self.assertIn("H-LA-01-2026", cache["officeResults"]["disagree"])
        self.assertIn("lead Steve Scalise 159,896",
                      cache["officeResults"]["disagree"]["H-LA-01-2026"]["officeSays"])
        # A page whose winner the partial counts lead is shown, as before: the
        # reporting gate is the office's own, not a doubt about the page.
        cache = self.build(read({"11/03/2026": partial}),
                           page=self.page([("Steve Scalise", "Republican", "159,896", True),
                                           ("Lauren Jewett", "Democratic", "89,440", False)],
                                          total=249336))
        race = cache["races"]["H-LA-01-2026"]
        self.assertNotIn(race.get("source"), ("qualified", "office"))
        self.assertEqual(race["status"]["H0LA01087"], "elected")
        self.assertFalse(cache["officeResults"]["disagree"])
        self.assertNotIn("pageHeld", cache["officeResults"])

    def test_a_page_runoff_that_is_not_the_counts_top_two_shows_neither(self):
        partial = {5: (LA5, (100, 522, 8, 8))}

        def five(second, third):
            return box([("Gabe Firment", "Republican", "39,126", True),
                        (second, "Republican" if "Echols" in second else "Democratic",
                         "32,905", True),
                        (third, "Republican" if "Echols" in third else "Democratic",
                         "30,786", False),
                        ("Stewart Cathey Jr.", "Republican", "28,168", False)], total=130985)
        cache = self.build(read({"11/03/2026": partial}),
                           page=self.page([], five=five("Michael Echols", "Patricia Moore")))
        self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "qualified")
        self.assertIn("H-LA-05-2026", cache["officeResults"]["disagree"])
        self.assertIn("to the runoff",
                      cache["officeResults"]["disagree"]["H-LA-05-2026"]["officeSays"])
        cache = self.build(read({"11/03/2026": partial}),
                           page=self.page([], five=five("Patricia Moore", "Michael Echols")))
        self.assertFalse(cache["officeResults"]["disagree"])
        self.assertEqual(cache["races"]["H-LA-05-2026"]["status"]["H6LA05341"], "runoff")

    def test_the_ranking(self):
        race = TestTheGatesNoTestHeld().race(LA5)
        self.assertEqual([n for n, _v in la_results.ranking(race, LISTS["H-LA-05-2026"])],
                         ['Patricia "Pat" Moore', "Gabe Firment", "Michael Echols",
                          "Stewart Cathey Jr."])
        self.assertIsNone(la_results.ranking(race, LISTS["H-LA-01-2026"]))


class TestARefusedPageMarkLeavesTheOfficesResult(NoGap):
    """carry_refused put the last read back over a race this read took from
    the office's results whenever the page's mark was refused: a vandal's name
    on the page took LA-1's correct result off the site, and would put a
    December race the office decided back to its runoff."""

    VANDAL = page_with(box([("Peter Griffin", "Democratic", "159,896", True),
                            ("Steve Scalise", "Republican", "89,440", False)]))

    def test_a_refused_mark_keeps_the_offices_november_result(self):
        before = self.build(None)
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}), page=self.VANDAL,
                           previous=before)
        self.assertIn("H-LA-01-2026", cache["refusedMarks"])
        self.assertEqual(results.carry_refused(cache, before), [])
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "office")
        self.assertEqual(race["status"]["H0LA01087"], "elected")

    def test_a_refused_mark_keeps_the_offices_december_result(self):
        nov = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        vandal = ("\n==District 1==\nNothing yet.\n==District 5==\n" +
                  box([("Peter Griffin", "Democratic", "90,000", True),
                       ("Gabe Firment", "Republican", "80,000", False)], total=170000) + "\n")
        cache = self.build(read({"11/03/2026": {1: LA1, 5: LA5}, "12/12/2026": {5: TWO}},
                                today=DECEMBER_AFTER), today=DECEMBER_AFTER, page=vandal,
                           previous=nov)
        self.assertIn("H-LA-05-2026", cache["refusedMarks"])
        results.carry_refused(cache, nov)
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["status"]["H6LA05317"], "elected")
        self.assertEqual(race["decidedIn"]["date"], "2026-12-12")


class TestAPageCallOfDecemberWaitsForTheOffice(NoGap):
    """Once December 12 is held, a page that marks its winner before the office
    has counted was a disagreement with the office's runoff: LA-5 went back to
    the qualified list, its first round's eight losers "qualified" again. The
    office's runoff stands while its December count is not posted or a gate
    holds it, and the page's call waits; a winner the counts do not lead is
    still a disagreement."""

    FIRMENT, MOORE = ("Gabe Firment", "Republican"), ("Patricia Moore", "Democratic")

    def page(self, winner, loser):
        first = TestTheOfficesResultBesideOtherSources().runoff_page("Patricia Moore") \
            .split("==District 5==\n")[1]
        december = box([(winner[0], winner[1], "90,000", True),
                        (loser[0], loser[1], "80,000", False)], title="Runoff results",
                       total=170000)
        return f"\n==District 1==\nNothing yet.\n==District 5==\n{first}\n{december}\n"

    def build_december(self, rounds, page):
        return self.build(read(rounds, today=DECEMBER_AFTER), page=page, today=DECEMBER_AFTER)

    def assert_waits(self, cache, why):
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["source"], "office")
        self.assertEqual(race["status"]["H6LA05317"], "runoff")
        self.assertEqual(race["status"]["H6LA05341"], "runoff")
        self.assertEqual(race["status"]["H6LA05101"], "defeated")
        self.assertIn("H-LA-05-2026", cache["officeResults"]["pageHeld"])
        self.assertFalse(cache["officeResults"]["disagree"])
        held = cache["officeResults"]["held"]["H-LA-05-2026"]
        self.assertIn(why, held)
        self.assertIn("the page's call", held)

    def test_a_page_call_beside_a_december_count_under_way_waits(self):
        page = self.page(self.FIRMENT, self.MOORE)
        alone = self.build(None, page=page, today=DECEMBER_AFTER)
        self.assertEqual(alone["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "elected")
        cache = self.build_december({"11/03/2026": {1: LA1, 5: LA5},
                                     "12/12/2026": {5: (TWO, (10, 791, 0, 24))}}, page)
        self.assert_waits(cache, "10 of 791 precincts")
        # Once the office's count is in, its result is shown.
        done = self.build_december({"11/03/2026": {1: LA1, 5: LA5}, "12/12/2026": {5: TWO}},
                                   page)
        self.assertEqual(done["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "elected")
        self.assertNotIn("pageHeld", done["officeResults"])

    def test_a_page_call_before_the_office_posts_december_waits(self):
        cache = self.build_december({"11/03/2026": {1: LA1, 5: LA5}},
                                    self.page(self.FIRMENT, self.MOORE))
        self.assert_waits(cache, "posted no December count")

    def test_a_page_winner_the_december_counts_do_not_lead_shows_neither(self):
        cache = self.build_december({"11/03/2026": {1: LA1, 5: LA5},
                                     "12/12/2026": {5: (TWO, (10, 791, 0, 24))}},
                                    self.page(self.MOORE, self.FIRMENT))
        self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "qualified")
        self.assertIn("H-LA-05-2026", cache["officeResults"]["disagree"])


class TestAPageBehindDecemberLeavesTheOfficesResult(NoGap):
    """Once the office's December count elects one of LA-5's two, a page that
    still marks only November's runoff - both in "runoff", with or without an
    unmarked December box an editor prepared - says nothing of December. It
    was a disagreement: LA-5 went back to the qualified list, its eight
    first-round losers "qualified" again, on the night between the office's
    count and an editor's mark. The office's result is shown, with a note; a
    December winner the office does not elect, or a runoff that is not the
    office's two, still disagrees."""

    DECEMBER = {"11/03/2026": {1: LA1, 5: LA5}, "12/12/2026": {5: TWO}}
    FIRST = [("Gabe Firment", "Republican", "39,126"), ("Patricia Moore", "Democratic", "40,786"),
             ("Michael Echols", "Republican", "32,905"),
             ("Stewart Cathey Jr.", "Republican", "28,168")]

    def page(self, runoff=("Gabe Firment", "Patricia Moore"), december=None):
        first = box([(n, p, v, n in runoff) for n, p, v in self.FIRST], total=140985)
        text = f"\n==District 1==\nNothing yet.\n==District 5==\n{first}\n"
        if december is not None:
            text += box([(n, p, v, won) for n, p, v, won in december],
                        title="Runoff results", total=0 if not any(
                            v for _n, _p, v, _w in december) else 170000) + "\n"
        return text

    def decide(self, page, office=None, previous=None):
        office = read(self.DECEMBER, today=DECEMBER_AFTER) if office is None else office
        return self.build(office, page=page, today=DECEMBER_AFTER, previous=previous)

    def assert_office(self, cache, behind=True):
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["source"], "office")
        self.assertEqual(race["status"]["H6LA05317"], "elected")
        self.assertEqual(race["status"]["H6LA05341"], "defeated")
        self.assertEqual(race["status"]["H6LA05101"], "defeated")
        self.assertEqual(race["status"]["H6LA05103"], "defeated")
        self.assertNotIn("qualified", race["status"].values())
        office = cache["officeResults"]
        self.assertFalse(office["disagree"])
        codes = {i.code: i for i in validate.check_results_pages(cache)}
        self.assertNotIn("office-result-disagrees", codes)
        if behind:
            item = office["pageBehind"]["H-LA-05-2026"]
            self.assertEqual(item["pageSays"], "runoff H6LA05317, H6LA05341")
            self.assertEqual(item["officeSays"], "elected H6LA05317")
            self.assertEqual(codes["office-result-page-behind"].level, "info")
        else:
            self.assertNotIn("pageBehind", office)
            self.assertNotIn("office-result-page-behind", codes)

    def assert_disagrees(self, cache):
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["source"], "qualified")
        self.assertIn("H-LA-05-2026", cache["officeResults"]["disagree"])
        self.assertNotIn("H-LA-05-2026", cache["officeResults"].get("pageBehind") or {})

    def test_a_page_marking_only_novembers_runoff_leaves_the_offices_december_result(self):
        page = self.page()
        alone = self.build(None, page=page, today=DECEMBER_AFTER)
        self.assertEqual(alone["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "runoff")
        self.assert_office(self.decide(page))

    def test_an_unmarked_december_box_says_nothing_of_december_either(self):
        page = self.page(december=[("Gabe Firment", "Republican", "", False),
                                   ("Patricia Moore", "Democratic", "", False)])
        self.assert_office(self.decide(page))

    def test_a_kept_december_result_beside_a_lagging_page_stands(self):
        decided = self.decide(self.page())
        for office in ({"unread": "HTTP 403"}, None):
            with self.subTest(office=office):
                later = self.build(office, page=self.page(), today=DECEMBER_AFTER,
                                   previous=decided)
                self.assertIn("H-LA-05-2026", later["officeResults"]["kept"])
                self.assert_office(later)
                # Once the page marks December's winner the note goes, on a
                # read that concludes nothing as on one made.
                caught_up = self.build(office, today=DECEMBER_AFTER, previous=later,
                                       page=self.page(december=[
                                           ("Gabe Firment", "Republican", "90,000", True),
                                           ("Patricia Moore", "Democratic", "80,000", False)]))
                self.assert_office(caught_up, behind=False)

    def test_a_december_winner_the_office_elects_agrees(self):
        page = self.page(december=[("Gabe Firment", "Republican", "90,000", True),
                                   ("Patricia Moore", "Democratic", "80,000", False)])
        self.assert_office(self.decide(page), behind=False)

    def test_a_december_winner_the_office_does_not_elect_still_disagrees(self):
        page = self.page(december=[("Patricia Moore", "Democratic", "90,000", True),
                                   ("Gabe Firment", "Republican", "80,000", False)])
        self.assert_disagrees(self.decide(page))

    def test_only_an_entry_decided_in_december_is_one_a_page_can_lag(self):
        # The helper asked directly, of a made-up entry: the same page and
        # first-round verdict, the entry decided in the first round alone.
        page = {"status": {"H6LA05317": "runoff", "H6LA05341": "runoff"}, "unmatched": {}}
        verdict = {"Gabe Firment": "runoff", 'Patricia "Pat" Moore': "runoff",
                   "Michael Echols": "defeated", "Stewart Cathey Jr.": "defeated"}
        rows = [r for r in FIELD["candidates"] if r["district_number"] == 5]
        entry = {"status": {"H6LA05317": "elected", "H6LA05341": "defeated"},
                 "office": {"rounds": ["2026-11-03", "2026-12-12"]}}
        self.assertTrue(results._page_behind_december(page, entry, verdict, "2026-12-12",
                                                      rows, None, {}))
        entry["office"]["rounds"] = ["2026-11-03"]
        self.assertFalse(results._page_behind_december(page, entry, verdict, "2026-12-12",
                                                       rows, None, {}))

    def test_a_runoff_that_is_not_the_offices_two_still_disagrees(self):
        page = self.page(runoff=("Gabe Firment", "Michael Echols"))
        alone = self.build(None, page=page, today=DECEMBER_AFTER)
        self.assertEqual(alone["races"]["H-LA-05-2026"]["status"]["H6LA05101"], "runoff")
        self.assert_disagrees(self.decide(page))


# -------------------------------------------------- the third review's follow-ups

EARLY = datetime.date(2026, 11, 14)
JEWETT_WINS = page_with(box([("Lauren Jewett", "Democratic", "159,896", True),
                             ("Steve Scalise", "Republican", "89,440", False)]))
SCALISE_CLOSE = TestAPageBesideAHeldRound().page([("Steve Scalise", "Republican", "125,000", True),
                                                   ("Lauren Jewett", "Democratic", "110,000",
                                                    False)])


class TestAReadThatConcludesNothingKeepsTheLastHold(NoGap):
    """Rule 8: where the last read set the page's call aside - the office's
    counts contradicting it, or its close margin holding it - a read that
    concludes nothing for the seat (the office unread, a round's file older
    than the last read's, no qualified list, a December round held) undid
    that: the page's call went live, credited to Wikipedia, with no warning
    (the last verifier of PR #265)."""

    def disagreed(self):
        cache = self.build(read_files(restamp(feeds({"11/03/2026": {1: LA1}}), "20261103",
                                              written="2026-11-14T18:55:18.130"), today=EARLY),
                           today=EARLY, page=JEWETT_WINS)
        self.assertIn("H-LA-01-2026", cache["officeResults"]["disagree"])
        return cache

    def assert_set_aside(self, cache, kind, since=EARLY):
        race = cache["races"]["H-LA-01-2026"]
        self.assertEqual(race["source"], "qualified")
        self.assertNotEqual(race["status"].get("H6LA01258"), "elected")
        self.assertNotEqual(race["status"].get("H0LA01087"), "elected")
        self.assertNotIn("calledBy", race)
        item = cache["officeResults"][kind]["H-LA-01-2026"]
        self.assertEqual(item["keptFrom"], since.isoformat())
        issues = {i.code: i for i in validate.check_results_pages(cache)}
        if kind == "disagree":
            self.assertTrue(any(d.startswith("H-LA-01-2026") and f"as the read of {since}" in d
                                for d in issues["office-result-disagrees"].detail))
        else:
            self.assertFalse(cache["officeResults"]["disagree"])
            self.assertTrue(any(d.startswith("H-LA-01-2026") and "the page's call" in d
                                and f"as the read of {since}" in d
                                for d in issues["office-result-held"].detail))

    def test_a_disagreement_is_kept_while_the_office_is_unread(self):
        first = self.disagreed()
        later = self.build({"unread": "HTTPError: HTTP Error 403: Forbidden"}, page=JEWETT_WINS,
                           previous=first)
        self.assert_set_aside(later, "disagree")
        self.assertEqual(later["officeResults"]["disagree"]["H-LA-01-2026"]["officeSays"],
                         first["officeResults"]["disagree"]["H-LA-01-2026"]["officeSays"])
        # Kept again on the next failed read, from the read it was first found by.
        again = self.build({"unread": "x"}, page=JEWETT_WINS, previous=later)
        self.assert_set_aside(again, "disagree")
        # A read that decides settles it: here the office's result is shown.
        agrees = page_with(box([("Steve Scalise", "Republican", "159,896", True),
                                ("Lauren Jewett", "Democratic", "89,440", False)]))
        newer = restamp(feeds({"11/03/2026": {1: LA1}}), "20261103", written="2026-11-20T10:00:00")
        read_again = self.build(read_files(newer), page=agrees, previous=again)
        self.assertEqual(read_again["races"]["H-LA-01-2026"]["source"], "office")
        self.assertFalse(read_again["officeResults"]["disagree"])
        # A page that no longer decides the seat has no call to set aside this
        # run, but the hold is carried, silent, until a read decides the seat.
        quiet = self.build({"unread": "x"}, previous=first)
        self.assertEqual(quiet["officeResults"]["disagree"]["H-LA-01-2026"]["pageSilentOn"],
                         AFTER.isoformat())
        codes = [i.code for i in validate.check_results_pages(quiet)]
        self.assertNotIn("office-result-disagrees", codes)
        self.assertIn("office-result-set-aside", codes)

    def test_a_disagreement_is_kept_beside_an_older_file(self):
        first = self.disagreed()
        older = restamp(feeds({"11/03/2026": {1: LA1}}), "20261103",
                        written="2026-11-01T18:55:18.130")
        later = self.build(read_files(older), page=JEWETT_WINS, previous=first)
        self.assert_set_aside(later, "disagree")
        self.assertIn("before the", later["officeResults"]["held"]["H-LA-01-2026"])

    def test_a_disagreement_is_kept_with_no_list_read(self):
        first = self.disagreed()
        newer = restamp(feeds({"11/03/2026": {1: LA1}}), "20261103", written="2026-11-20T10:00:00")
        later = self.build(read_files(newer), page=JEWETT_WINS, previous=first, lists=None)
        self.assertNotIn("staleRead", later["officeResults"]["elections"]["2026-11-03"])
        self.assertNotIn("H-LA-01-2026", later["races"])        # the page's call set aside
        self.assertEqual(results.carry_qualified(later, first)[:1], ["H-LA-01-2026"])
        self.assert_set_aside(later, "disagree")
        self.assertIn("qualified list", later["officeResults"]["held"]["H-LA-01-2026"])

    def test_a_december_disagreement_is_kept_while_december_is_held(self):
        page = TestAPageCallOfDecemberWaitsForTheOffice().page(
            TestAPageCallOfDecemberWaitsForTheOffice.MOORE,
            TestAPageCallOfDecemberWaitsForTheOffice.FIRMENT)
        first = self.build(read({"11/03/2026": {5: LA5}, "12/12/2026": {5: TWO}},
                                today=DECEMBER_AFTER), today=DECEMBER_AFTER, page=page)
        self.assertIn("H-LA-05-2026", first["officeResults"]["disagree"])
        self.assertEqual(first["races"]["H-LA-05-2026"]["source"], "qualified")
        later = self.build(read({"11/03/2026": {5: LA5}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, page=page, previous=first)
        race = later["races"]["H-LA-05-2026"]
        self.assertEqual(race["source"], "qualified")
        self.assertNotEqual(race["status"].get("H6LA05341"), "elected")
        self.assertNotIn("calledBy", race)
        item = later["officeResults"]["disagree"]["H-LA-05-2026"]
        self.assertEqual(item["keptFrom"], DECEMBER_AFTER.isoformat())
        self.assertIn("2026-12-12", later["officeResults"]["held"]["H-LA-05-2026"])
        codes = [i.code for i in validate.check_results_pages(later)]
        self.assertIn("office-result-disagrees", codes)

    def held(self):
        cache = self.build(read_files(restamp(feeds({"11/03/2026": {1: CLOSE}}), "20261103",
                                              written="2026-11-14T18:55:18.130"), today=EARLY),
                           today=EARLY, page=SCALISE_CLOSE)
        self.assertIn("H-LA-01-2026", cache["officeResults"]["pageHeld"])
        return cache

    def test_a_close_margins_hold_is_kept_while_the_office_is_unread(self):
        first = self.held()
        later = self.build({"unread": "HTTPError: HTTP Error 403: Forbidden"},
                           page=SCALISE_CLOSE, previous=first)
        self.assert_set_aside(later, "pageHeld")
        self.assertIn("could not be read", later["officeResults"]["held"]["H-LA-01-2026"])
        # Where the page no longer decides the seat, the hold is carried
        # silent, its held line the seat's reasons without the page's call.
        quiet = self.build({"unread": "x"}, previous=first)
        self.assertTrue(quiet["officeResults"]["pageHeld"]["H-LA-01-2026"]["pageSilentOn"])
        self.assertNotIn("the page's call", quiet["officeResults"]["held"]["H-LA-01-2026"])
        # So with no read made at all (none attempted): kept beside the page's
        # call, and carried silent where the page makes none.
        self.assert_set_aside(self.build(None, page=SCALISE_CLOSE, previous=first), "pageHeld")
        self.assertTrue(self.build(None, previous=first)["officeResults"]["pageHeld"]
                        ["H-LA-01-2026"]["pageSilentOn"])
        # Nor does a read that decides: once official, the office's result.
        released = self.build(read_files(restamp(
            feeds({"11/03/2026": {1: CLOSE}}, official=("11/03/2026",)), "20261103",
            written="2026-11-20T10:00:00")), page=SCALISE_CLOSE, previous=later)
        self.assertEqual(released["races"]["H-LA-01-2026"]["source"], "office")
        self.assertNotIn("pageHeld", released["officeResults"])

    def test_a_close_margins_hold_is_kept_beside_an_older_file(self):
        first = self.held()
        stale = restamp(feeds({"11/03/2026": {1: CLOSE}}, official=("11/03/2026",)), "20261103",
                        written="2026-11-04T09:00:00")
        later = self.build(read_files(stale), page=SCALISE_CLOSE, previous=first)
        self.assert_set_aside(later, "pageHeld")
        self.assertIn("before the", later["officeResults"]["held"]["H-LA-01-2026"])

    def test_a_close_margins_hold_is_kept_with_no_list_read(self):
        first = self.held()
        newer = restamp(feeds({"11/03/2026": {1: CLOSE}}), "20261103",
                        written="2026-11-20T10:00:00")
        later = self.build(read_files(newer), page=SCALISE_CLOSE, previous=first, lists=None)
        results.carry_qualified(later, first)
        self.assert_set_aside(later, "pageHeld")


class TestAKeptDecemberResultKeepsItsRecord(NoGap):
    def test_a_december_file_back_to_partial_counts_keeps_the_record_beside_it(self):
        decided = self.build(read({"11/03/2026": {5: LA5}, "12/12/2026": {5: TWO}},
                                  today=DECEMBER_AFTER), today=DECEMBER_AFTER)
        later = self.build(read({"11/03/2026": {5: LA5},
                                 "12/12/2026": {5: (TWO, (10, 791, 0, 24))}},
                                today=DECEMBER_AFTER), today=DECEMBER_AFTER, previous=decided)
        self.assertEqual(later["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "elected")
        record = later["officeResults"]["races"]["H-LA-05-2026"]["2026-12-12"]
        self.assertEqual(record["verdict"], decided["officeResults"]["races"]["H-LA-05-2026"]
                         ["2026-12-12"]["verdict"])
        self.assertTrue(record["verdict"])
        self.assertEqual(record["reporting"]["precincts"][0], 791)
        # This read's facts are kept beside it, dated.
        self.assertEqual(record["heldRead"]["reporting"]["precincts"][0], 10)
        self.assertIsNone(record["heldRead"]["verdict"])
        self.assertEqual(record["heldRead"]["on"], DECEMBER_AFTER.isoformat())


class TestAFirstRoundALaterFileDrops(NoGap):
    def test_it_is_never_said_to_be_yet_to_come(self):
        nov = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}))
        later = self.build(read({"12/12/2026": {5: TWO}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, previous=nov)
        why = later["officeResults"]["held"]["H-LA-01-2026"]
        self.assertEqual(why, "the office lists no results for 2026-11-03, where its last "
                              "read had them")
        self.assertEqual(later["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        # Its record stays the baseline a later file is compared with.
        e = later["officeResults"]["elections"]["2026-11-03"]
        self.assertEqual(e["written"], "2026-11-03T18:55:18.130")
        self.assertEqual(e["unlistedOn"], DECEMBER_AFTER.isoformat())
        # With no read of it before, it is not listed yet.
        first = self.build(read({}))
        self.assertEqual(first["officeResults"]["held"]["H-LA-01-2026"],
                         "the office lists no results for 2026-11-03 yet")


# -------------------------------------------------- the fourth review's follow-ups

def day_after(day, n=1):
    return day + datetime.timedelta(days=n)


class TestAHoldKeepsTheRecordItStandsOn(NoGap):
    """Rule 8: a seat whose page call was set aside lost the office's round
    record whenever a read concluded nothing before one was written (no list,
    an older first round, a first round the dates file dropped, no race for
    the district), so the next read no longer knew the office had counted
    December and said "the office has posted no December count for the seat
    yet" of a seat whose page its own count had contradicted; and a December
    file gone back to partial counts overwrote the record the disagreement
    stood on, and made it a runoff the page's call merely waited on."""

    RID = "H-LA-05-2026"
    BOTH = {"11/03/2026": {5: LA5}, "12/12/2026": {5: TWO}}
    D0, D1, D2 = DECEMBER_AFTER, day_after(DECEMBER_AFTER), day_after(DECEMBER_AFTER, 2)

    def moore_page(self):
        waits = TestAPageCallOfDecemberWaitsForTheOffice
        return waits().page(waits.MOORE, waits.FIRMENT)

    def disagreed(self):
        # The office's December count elects Firment; the page marks Moore.
        cache = self.build(read(self.BOTH, today=self.D0), today=self.D0, page=self.moore_page())
        self.assertIn(self.RID, cache["officeResults"]["disagree"])
        self.assertEqual(cache["races"][self.RID]["source"], "qualified")
        self.assertTrue(cache["officeResults"]["races"][self.RID]["2026-12-12"]["verdict"])
        return cache

    def assert_still_disagrees(self, cache, first, kind="disagree"):
        race = cache["races"][self.RID]
        self.assertEqual(race["source"], "qualified")
        self.assertNotIn("elected", race["status"].values())
        self.assertNotIn("runoff", race["status"].values())
        self.assertNotIn("calledBy", race)
        item = cache["officeResults"][kind][self.RID]
        self.assertEqual(item["keptFrom"], self.D0.isoformat())
        self.assertEqual(item["officeSays"],
                         first["officeResults"]["disagree"][self.RID]["officeSays"])
        self.assertIn("elected H6LA05317", item["officeSays"])
        other = "pageHeld" if kind == "disagree" else "disagree"
        self.assertFalse(cache["officeResults"].get(other))
        self.assertNotIn("posted no December count", cache["officeResults"]["held"][self.RID])

    def assert_record_kept(self, cache, first):
        """December's record is the one the hold stands on: its verdict and
        its full counts, said to be kept from the read that wrote it."""
        record = cache["officeResults"]["races"][self.RID]["2026-12-12"]
        was = first["officeResults"]["races"][self.RID]["2026-12-12"]
        self.assertEqual(record["verdict"], was["verdict"])
        self.assertTrue(record["verdict"])
        self.assertEqual(record["reporting"]["precincts"][0], 791)
        self.assertEqual(record["choices"], was["choices"])
        self.assertEqual(record["keptFrom"], self.D0.isoformat())
        return record

    def nothing_for_the_seat(self):
        """Reads that write no record for the seat: ``{what: (office read,
        lists, a word of why)}``."""
        older = restamp(feeds(self.BOTH), "20261103", written="2026-11-01T18:55:18.130")
        return {
            "no list": (read(self.BOTH, today=self.D1), None, "qualified list"),
            "an older first round": (read_files(older, today=self.D1), LISTS, "before the"),
            "the first round dropped": (read({"12/12/2026": {5: TWO}}, today=self.D1), LISTS,
                                        "lists no results for 2026-11-03"),
            "no race for the district": (read({"11/03/2026": {1: LA1}, "12/12/2026": {5: TWO}},
                                              today=self.D1), LISTS,
                                         "no race for district 5"),
        }

    def test_a_read_that_writes_no_record_keeps_the_last_reads(self):
        page = self.moore_page()
        for what, (office, lists, why) in self.nothing_for_the_seat().items():
            with self.subTest(what):
                first = self.disagreed()
                second = self.build(office, today=self.D1, page=page, previous=first, lists=lists)
                results.carry_qualified(second, first)
                self.assertIn(why, second["officeResults"]["held"][self.RID])
                self.assert_still_disagrees(second, first)
                self.assert_record_kept(second, first)
                # The first round's record is kept with it, as that read's.
                november = second["officeResults"]["races"][self.RID]["2026-11-03"]
                self.assertEqual(november["keptFrom"], self.D0.isoformat())
                self.assertEqual(second["officeResults"]["read"], self.D1.isoformat())
                # Then a dates file that lists no December: the office's last
                # read had its count, and the read says so.
                third = self.build(read({"11/03/2026": {5: LA5}}, today=self.D2), today=self.D2,
                                   page=page, previous=second)
                self.assert_still_disagrees(third, first)
                self.assert_record_kept(third, first)
                held = third["officeResults"]["held"][self.RID]
                self.assertTrue(held.startswith(
                    "2026-12-12: the office lists no results for 2026-12-12, where its last "
                    "read had them"), held)
                self.assertNotIn("the page's call", held)
                # This read's own first round is its own, not a kept one.
                self.assertNotIn("keptFrom",
                                 third["officeResults"]["races"][self.RID]["2026-11-03"])
                issues = {i.code: i for i in validate.check_results_pages(third)}
                self.assertTrue(any(d.startswith(self.RID) and f"as the read of {self.D0}" in d
                                    for d in issues["office-result-disagrees"].detail))

    def test_a_kept_record_says_the_read_that_wrote_it_through_two_reads(self):
        first = self.disagreed()
        second = self.build(read(self.BOTH, today=self.D1), today=self.D1,
                            page=self.moore_page(), previous=first, lists=None)
        results.carry_qualified(second, first)
        third = self.build(read(self.BOTH, today=self.D2), today=self.D2,
                           page=self.moore_page(), previous=second, lists=None)
        results.carry_qualified(third, second)
        self.assertEqual(third["officeResults"]["read"], self.D2.isoformat())
        self.assert_record_kept(third, first)
        self.assert_still_disagrees(third, first)

    def test_a_seat_no_page_call_touches_keeps_its_record_too(self):
        # A seat held for its close margin, no page call beside it: an older
        # file's read writes no record, and the last read's stays.
        first = self.build(read_files(restamp(feeds({"11/03/2026": {1: CLOSE}}), "20261103",
                                              written="2026-11-14T18:55:18.130"), today=EARLY),
                           today=EARLY)
        self.assertIsNone(first["officeResults"]["races"]["H-LA-01-2026"]["2026-11-03"]["verdict"])
        older = restamp(feeds({"11/03/2026": {1: CLOSE}}), "20261103",
                        written="2026-11-04T09:00:00")
        later = self.build(read_files(older), previous=first)
        record = later["officeResults"]["races"]["H-LA-01-2026"]["2026-11-03"]
        self.assertEqual(record["keptFrom"], EARLY.isoformat())
        self.assertEqual(record["total"], sum(v for _d, v, _o in CLOSE))

    def partial(self, firment, moore):
        return {"11/03/2026": {5: LA5},
                "12/12/2026": {5: ([('"Gabe" Firment (REP)', firment, "Elected"),
                                    ('Patricia "Pat" Moore (DEM)', moore, "Defeated")],
                                   (10, 791, 0, 24))}}

    def test_a_december_file_back_to_partial_counts_keeps_the_disagreement(self):
        page = self.moore_page()
        # Partial counts that lead the page's winner made the contradicted
        # call one that waits; partial counts that do not, a new disagreement
        # with a runoff: either way the count the hold stood on was dropped.
        for what, counts in (("leading the page's winner", (100, 200)),
                             ("leading the office's", (200, 100))):
            with self.subTest(what):
                first = self.disagreed()
                later = self.build(read(self.partial(*counts), today=self.D1), today=self.D1,
                                   page=page, previous=first)
                self.assert_still_disagrees(later, first)
                record = self.assert_record_kept(later, first)
                self.assertEqual(record["heldRead"]["reporting"]["precincts"][0], 10)
                self.assertIsNone(record["heldRead"]["verdict"])
                self.assertEqual(record["heldRead"]["on"], self.D1.isoformat())
                held = later["officeResults"]["held"][self.RID]
                self.assertTrue(held.startswith("2026-12-12: "), held)
                self.assertIn("10 of 791 precincts", held)
                self.assertNotIn("the page's call", held)
                # And again the next day, from the kept record.
                again = self.build(read(self.partial(*counts), today=self.D2), today=self.D2,
                                   page=page, previous=later)
                self.assert_still_disagrees(again, first)
                record = self.assert_record_kept(again, first)
                self.assertEqual(record["heldRead"]["on"], self.D2.isoformat())
                # A full count settles it afresh: still a disagreement, this read's.
                full = self.build(read(self.BOTH, today=self.D2), today=self.D2, page=page,
                                  previous=again)
                self.assertNotIn("keptFrom", full["officeResults"]["disagree"][self.RID])
                self.assertNotIn("heldRead",
                                 full["officeResults"]["races"][self.RID]["2026-12-12"])
                self.assertNotIn("keptFrom",
                                 full["officeResults"]["races"][self.RID]["2026-12-12"])

    def test_an_older_december_file_keeps_the_disagreement(self):
        first = self.disagreed()
        older = restamp(feeds(self.partial(100, 200)), "20261212",
                        written="2026-12-01T09:00:00")
        later = self.build(read_files(older, today=self.D1), today=self.D1,
                           page=self.moore_page(), previous=first)
        self.assert_still_disagrees(later, first)
        record = self.assert_record_kept(later, first)
        self.assertNotIn("heldRead", record)     # an older file's counts are not kept
        self.assertIn("before the", later["officeResults"]["held"][self.RID])

    def test_a_first_round_a_gate_holds_keeps_decembers_record_and_the_hold(self):
        # The November file back to partial counts: the read never reaches
        # December. Its first-round counts lead Moore, the page's December
        # winner, and say nothing of the runoff the office's count gave Firment.
        first = self.disagreed()
        later = self.build(read({"11/03/2026": {5: (LA5, (10, 791, 0, 24))},
                                 "12/12/2026": {5: TWO}}, today=self.D1), today=self.D1,
                           page=self.moore_page(), previous=first)
        self.assert_still_disagrees(later, first)
        self.assert_record_kept(later, first)
        # The last read's full first round stays the record, this read's
        # partial counts beside it (as a December file's are).
        november = later["officeResults"]["races"][self.RID]["2026-11-03"]
        self.assertEqual(november["reporting"]["precincts"][0], 791)
        self.assertTrue(november["verdict"])
        self.assertEqual(november["keptFrom"], first["officeResults"]["read"])
        self.assertEqual(november["heldRead"]["reporting"]["precincts"][0], 10)
        self.assertEqual(november["heldRead"]["on"], self.D1.isoformat())
        self.assertIn("10 of 791 precincts", later["officeResults"]["held"][self.RID])
        # With no December verdict before, a held first round is read against
        # the page as ever: here its counts lead the page's two.
        runoff_page = TestTheOfficesResultBesideOtherSources().runoff_page("Patricia Moore")
        nov = self.build(read({"11/03/2026": {5: (LA5, (10, 791, 0, 24))}}), page=runoff_page)
        self.assertFalse(nov["officeResults"]["disagree"])
        self.assertEqual(nov["races"][self.RID]["status"]["H6LA05341"], "runoff")

    def test_a_page_call_that_waited_beside_decembers_verdict_is_kept_the_same_way(self):
        # The state made: the last read's hold is a ``pageHeld``, its December
        # record holding a verdict.
        first = self.disagreed()
        made = copy.deepcopy(first)
        made["officeResults"]["pageHeld"] = {
            self.RID: made["officeResults"]["disagree"].pop(self.RID)}
        later = self.build(read(self.partial(100, 200), today=self.D1), today=self.D1,
                           page=self.moore_page(), previous=made)
        self.assert_still_disagrees(later, first, kind="pageHeld")
        record = self.assert_record_kept(later, first)
        self.assertEqual(record["heldRead"]["reporting"]["precincts"][0], 10)

    def test_with_no_december_verdict_before_a_partial_december_is_read_as_ever(self):
        # No read had December's result: the page's call waits on the count
        # under way, as before (nothing is kept that was never read).
        waits = TestAPageCallOfDecemberWaitsForTheOffice
        page = waits().page(waits.MOORE, waits.FIRMENT)
        nov = self.build(read({"11/03/2026": {5: LA5}}, today=self.D0), today=self.D0, page=page)
        self.assertIn(self.RID, nov["officeResults"]["pageHeld"])
        later = self.build(read(self.partial(100, 200), today=self.D1), today=self.D1,
                           page=page, previous=nov)
        self.assertEqual(later["races"][self.RID]["source"], "office")
        self.assertEqual(later["races"][self.RID]["status"]["H6LA05341"], "runoff")
        self.assertIn(self.RID, later["officeResults"]["pageHeld"])
        self.assertNotIn("keptFrom", later["officeResults"]["pageHeld"][self.RID])
        record = later["officeResults"]["races"][self.RID]["2026-12-12"]
        self.assertEqual(record["reporting"]["precincts"][0], 10)
        self.assertNotIn("heldRead", record)


class TestAKeptHoldSaysTheReadThatFoundIt(NoGap):
    """``keptFrom`` is the day of the read that set the page's call aside,
    through any number of reads that conclude nothing: taken from the last
    read's own day, a second older file's read said "as the read of
    2026-11-15 found" of a disagreement the read of the 14th found - the
    15th's read had concluded nothing."""

    RID = "H-LA-01-2026"
    D1, D2 = day_after(EARLY), day_after(EARLY, 2)

    def chain(self, first, page, files, lists=LISTS):
        """Two reads of *files* after *first*, a day apart, as the cli makes
        them: ``(second, third)``."""
        second = self.build(read_files(files, today=self.D1), today=self.D1, page=page,
                            previous=first, lists=lists)
        results.carry_qualified(second, first)
        self.assertEqual(second["officeResults"]["read"], self.D1.isoformat())
        third = self.build(read_files(files, today=self.D2), today=self.D2, page=page,
                           previous=second, lists=lists)
        results.carry_qualified(third, second)
        self.assertEqual(third["officeResults"]["read"], self.D2.isoformat())
        return second, third

    def files(self, choices):
        return {"an older file": (restamp(feeds({"11/03/2026": {1: choices}}), "20261103",
                                          written="2026-11-01T18:55:18.130"), LISTS),
                "no list": (restamp(feeds({"11/03/2026": {1: choices}}), "20261103",
                                    written="2026-11-20T10:00:00"), None)}

    def test_a_disagreement_kept_twice_names_the_read_that_found_it(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        for what, (files, lists) in self.files(LA1).items():
            with self.subTest(what):
                first = keeps.disagreed(self)
                for cache in self.chain(first, JEWETT_WINS, files, lists):
                    keeps.assert_set_aside(self, cache, "disagree")
                    # The record the disagreement stands on, kept the same way.
                    record = cache["officeResults"]["races"][self.RID]["2026-11-03"]
                    self.assertEqual(record["keptFrom"], EARLY.isoformat())
                    self.assertTrue(record["verdict"])

    def test_a_close_margins_hold_kept_twice_names_the_read_that_found_it(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        for what, (files, lists) in self.files(CLOSE).items():
            with self.subTest(what):
                first = keeps.held(self)
                for cache in self.chain(first, SCALISE_CLOSE, files, lists):
                    keeps.assert_set_aside(self, cache, "pageHeld")
                    self.assertEqual(cache["officeResults"]["races"][self.RID]["2026-11-03"]
                                     ["keptFrom"], EARLY.isoformat())


class TestWithNoReadAHeldLineSaysNoCallThePageNoLongerMakes(NoGap):
    """With no read of the office attempted, the last read's record stands -
    and its held line for a seat whose page call waited went on saying "the
    page's call (...) waits" after the page had stopped making the call."""

    CLAUSE = "the page's call"

    def lines(self, cache):
        held = [d for i in validate.check_results_pages(cache) if i.code == "office-result-held"
                for d in i.detail]
        return cache["officeResults"].get("held") or {}, held

    def test_a_close_margins_line_goes_back_to_the_offices_reason(self):
        rid = "H-LA-01-2026"
        first = TestAReadThatConcludesNothingKeepsTheLastHold.held(self)
        before = copy.deepcopy(first)
        self.assertIn(self.CLAUSE, first["officeResults"]["held"][rid])
        self.assertIn("over half", first["officeResults"]["pageHeld"][rid]["why"])
        # The page makes no call now, and no read is made: the hold is
        # carried, silent.
        quiet = self.build(None, previous=first)
        self.assertTrue(quiet["officeResults"]["pageHeld"][rid]["pageSilentOn"])
        held, named = self.lines(quiet)
        self.assertIn("over half", held[rid])
        self.assertNotIn(self.CLAUSE, held[rid])
        self.assertFalse(any(self.CLAUSE in d for d in named), named)
        self.assertTrue(any(d.startswith(rid) and "over half" in d for d in named), named)
        # The page still makes it: said once, as the read that found it found.
        still = self.build(None, page=SCALISE_CLOSE, previous=first)
        self.assertEqual(still["officeResults"]["held"][rid].count(self.CLAUSE), 1)
        self.assertIn("over half", still["officeResults"]["pageHeld"][rid]["why"])
        # ... and then stops: the line is the office's reason again.
        after = self.build(None, previous=still)
        self.assertTrue(after["officeResults"]["pageHeld"][rid]["pageSilentOn"])
        self.assertIn("over half", after["officeResults"]["held"][rid])
        self.assertNotIn(self.CLAUSE, after["officeResults"]["held"][rid])
        # Nothing of the last read's own record was written over.
        self.assertEqual(first, before)

    def test_a_record_written_before_the_reason_was_kept_apart_reads_the_same(self):
        rid = "H-LA-01-2026"
        first = TestAReadThatConcludesNothingKeepsTheLastHold.held(self)
        del first["officeResults"]["pageHeld"][rid]["why"]
        quiet = self.build(None, previous=first)
        self.assertIn("over half", quiet["officeResults"]["held"][rid])
        self.assertNotIn(self.CLAUSE, quiet["officeResults"]["held"][rid])

    def test_after_an_unread_office_the_line_is_that_reads_reason(self):
        rid = "H-LA-01-2026"
        first = TestAReadThatConcludesNothingKeepsTheLastHold.held(self)
        unread = self.build({"unread": "HTTPError: HTTP Error 403: Forbidden"},
                            page=SCALISE_CLOSE, previous=first)
        self.assertIn("could not be read", unread["officeResults"]["pageHeld"][rid]["why"])
        # No read made, the page silent: every seat's line is the unread
        # read's, this seat's with them - beside the seat's own reason, the
        # close margin the read that held the call found - and none speaks of
        # a call.
        quiet = self.build(None, previous=unread)
        self.assertTrue(quiet["officeResults"]["pageHeld"][rid]["pageSilentOn"])
        line = quiet["officeResults"]["held"][rid]
        self.assertTrue(line.startswith("the office's results could not be read: HTTPError: "
                                        "HTTP Error 403: Forbidden; as the read of "
                                        f"{EARLY.isoformat()} found, "), line)
        self.assertIn("over half", line)
        self.assertEqual(line.count("over half"), 1)
        self.assertNotIn(self.CLAUSE, line)
        # The page calls again, with no read made: the line keeps both
        # reasons, once each, and the page's call once.
        again = self.build(None, page=SCALISE_CLOSE, previous=quiet)
        line = again["officeResults"]["held"][rid]
        self.assertEqual((line.count("over half"), line.count("could not be read"),
                          line.count(self.CLAUSE)), (1, 1, 1), line)
        self.assertNotIn("pageSilentOn", again["officeResults"]["pageHeld"][rid])

    def december_wait(self):
        waits = TestAPageCallOfDecemberWaitsForTheOffice
        page = waits().page(waits.FIRMENT, waits.MOORE)
        first = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, page=page)
        self.assertIn("H-LA-05-2026", first["officeResults"]["pageHeld"])
        self.assertIsNone(first["officeResults"]["pageHeld"]["H-LA-05-2026"]["why"])
        return first, page

    def test_a_december_wait_held_for_the_call_alone_drops_its_line(self):
        rid = "H-LA-05-2026"
        for old in (False, True):
            with self.subTest(written_before_the_reason_was_kept_apart=old):
                first, page = self.december_wait()
                if old:
                    del first["officeResults"]["pageHeld"][rid]["why"]
                # The seat was held for the page's call alone: with no call, no line.
                quiet = self.build(None, today=DECEMBER_AFTER, previous=first)
                self.assertNotIn("pageHeld", quiet["officeResults"])
                self.assertNotIn(rid, quiet["officeResults"]["held"])
                self.assertEqual(quiet["races"][rid]["status"]["H6LA05317"], "runoff")
                self.assertFalse(any(d.startswith(rid) for d in self.lines(quiet)[1]))
                # The page still calls it: it waits, said once.
                still = self.build(None, today=DECEMBER_AFTER, page=page, previous=first)
                self.assertIn(rid, still["officeResults"]["pageHeld"])
                self.assertEqual(still["officeResults"]["held"][rid].count(self.CLAUSE), 1)
                self.assertEqual(still["races"][rid]["status"]["H6LA05317"], "runoff")


class TestARefusedRowLeavesTheOfficesLoss(unittest.TestCase):
    def test_the_second_loop_leaves_an_office_race_alone(self):
        # A November row refused for its name, unmarked, in a race the office
        # decided: the office's statuses stand, the last read's loss not laid
        # over them.
        rid = "H-LA-01-2026"
        cache = {"races": {rid: {"source": "office", "status": {"A": "elected", "B": "nominee"}}},
                 "refusedRows": {rid: [{"ids": ["B"], "marked": False}]}}
        previous = {"races": {rid: {"source": "table", "status": {"B": "defeated"}}}}
        self.assertEqual(results.carry_refused(cache, previous), [])
        self.assertEqual(cache["races"][rid]["status"]["B"], "nominee")
        # Any other race takes the loss, as ever.
        cache["races"][rid]["source"] = "table"
        self.assertEqual(results.carry_refused(cache, previous), [rid])
        self.assertEqual(cache["races"][rid]["status"]["B"], "defeated")


# -------------------------------------------------- the fifth review's follow-ups

# LA-1's first round with 40 of 791 precincts in, the partial counts leading
# Lauren Jewett, or Steve Scalise.
PARTIAL = (40, 791, 2, 24)
LA1_JEWETT_LEADS = [("Randall Arrington (REP)", 300, "Defeated"),
                    ('E. "Liddy" Glass (NOPTY)', 100, "Defeated"),
                    ("Lauren Jewett (DEM)", 6000, "Defeated"),
                    ("Steve Scalise (REP)", 4000, "Defeated")]
LA1_SCALISE_LEADS = [("Randall Arrington (REP)", 300, "Defeated"),
                     ('E. "Liddy" Glass (NOPTY)', 100, "Defeated"),
                     ("Lauren Jewett (DEM)", 4000, "Defeated"),
                     ("Steve Scalise (REP)", 6000, "Defeated")]
SCALISE_WINS = page_with(box([("Steve Scalise", "Republican", "159,896", True),
                              ("Lauren Jewett", "Democratic", "89,440", False)]))


class TestAHoldOutlivesAPageThatFallsSilent(NoGap):
    """Rule 8: a hold was dropped on any run whose page made no call (its
    fetch failed with the office's, or an editor blanked the table), so the
    next run whose read concluded nothing let the call the office's counts
    contradicted go live, credited to Wikipedia, with no warning - or, with no
    list read, with no line at all (the verifier of the fix that keeps a
    hold). The hold is carried, silent, and clears only on a read that decides
    the seat. Each run is made as the cli makes it, the qualified list and a
    refused mark's race carried after it."""

    D1, D2, D3 = day_after(EARLY), day_after(EARLY, 2), day_after(EARLY, 3)
    RID = "H-LA-01-2026"

    def step(self, office, page, previous, today, lists=LISTS):
        cache = self.build(office, today=today, page=page, previous=previous, lists=lists)
        results.carry_qualified(cache, previous)
        results.carry_refused(cache, previous)
        return cache

    def newer(self, choices=LA1, today=None, official=None, reporting=None):
        seats = {1: (choices, reporting) if reporting else choices}
        files = restamp(feeds({"11/03/2026": seats}, official=official), "20261103",
                        written="2026-11-20T10:00:00")
        return read_files(files, today=today or self.D2)

    def silent_reads(self):
        """What a run that concludes nothing is, by name: ``(office, lists)``."""
        return {"unread": ({"unread": "URLError: timed out"}, LISTS),
                "no list": (self.newer(), None),
                "no read made": (None, LISTS)}

    def assert_live_set_aside(self, cache, kind, since=EARLY):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        keeps.assert_set_aside(self, cache, kind, since)
        self.assertNotIn("pageSilentOn", cache["officeResults"][kind][self.RID])
        codes = [i.code for i in validate.check_results_pages(cache)]
        self.assertNotIn("office-result-set-aside", codes)

    def assert_silent(self, cache, kind, since=EARLY):
        item = cache["officeResults"][kind][self.RID]
        self.assertEqual(item["keptFrom"], since.isoformat())
        self.assertTrue(item["pageSilentOn"])
        issues = {i.code: i for i in validate.check_results_pages(cache)}
        # Not warned as a live disagreement: no call is set aside this run.
        self.assertFalse(any(d.startswith(self.RID) for d in
                             getattr(issues.get("office-result-disagrees"), "detail", [])))
        self.assertFalse(any(d.startswith(self.RID) and "the page's call" in d for d in
                             getattr(issues.get("office-result-held"), "detail", [])))
        # Said, as what it is.
        self.assertEqual(issues["office-result-set-aside"].level, "info")
        self.assertTrue(any(d.startswith(self.RID) and f"the read of {since}" in d
                            for d in issues["office-result-set-aside"].detail))

    def test_a_disagreement_outlives_a_silent_page(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        for quiet_what, (quiet_office, quiet_lists) in self.silent_reads().items():
            for call_what, (call_office, call_lists) in self.silent_reads().items():
                with self.subTest(silent=quiet_what, then=call_what):
                    first = keeps.disagreed(self)
                    quiet = self.step(quiet_office, None, first, self.D1, quiet_lists)
                    self.assertNotEqual(quiet["races"][self.RID]["status"].get("H6LA01258"),
                                        "elected")
                    self.assert_silent(quiet, "disagree")
                    later = self.step(call_office, JEWETT_WINS, quiet, self.D2, call_lists)
                    self.assert_live_set_aside(later, "disagree")
                    self.assertEqual(later["officeResults"]["disagree"][self.RID]["officeSays"],
                                     "elected H0LA01087")
                    # And on another silent run after it, still carried.
                    again = self.step(quiet_office, None, later, self.D3, quiet_lists)
                    self.assert_silent(again, "disagree")

    def test_a_close_margins_hold_outlives_a_silent_page(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        for quiet_what, (quiet_office, quiet_lists) in self.silent_reads().items():
            with self.subTest(silent=quiet_what):
                first = keeps.held(self)
                quiet = self.step(quiet_office, None, first, self.D1, quiet_lists)
                self.assert_silent(quiet, "pageHeld")
                # Its seat's own reason, the close margin, stays on its line.
                self.assertIn("over half", quiet["officeResults"]["held"][self.RID])
                later = self.step({"unread": "x"}, SCALISE_CLOSE, quiet, self.D2)
                self.assert_live_set_aside(later, "pageHeld")
                line = later["officeResults"]["held"][self.RID]
                self.assertIn("over half", line)
                self.assertIn("could not be read", line)
                # Two older files and no list after it: still set aside.
                stale = restamp(feeds({"11/03/2026": {1: CLOSE}}), "20261103",
                                written="2026-11-04T09:00:00")
                for day in (self.D3, day_after(EARLY, 4)):
                    later = self.step(read_files(stale, today=day), SCALISE_CLOSE, later, day)
                    self.assert_live_set_aside(later, "pageHeld")
                later = self.step(self.newer(CLOSE, today=day_after(EARLY, 5)), SCALISE_CLOSE,
                                  later, day_after(EARLY, 5), lists=None)
                self.assert_live_set_aside(later, "pageHeld")

    def test_a_read_that_decides_clears_a_silent_hold(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        first = keeps.disagreed(self)
        quiet = self.step({"unread": "x"}, None, first, self.D1)
        self.assertIn(self.RID, quiet["officeResults"]["disagree"])
        decided = self.step(self.newer(), None, quiet, self.D2)
        self.assertEqual(decided["races"][self.RID]["source"], "office")
        self.assertEqual(decided["races"][self.RID]["status"]["H0LA01087"], "elected")
        self.assertFalse(decided["officeResults"]["disagree"])
        self.assertNotIn("office-result-set-aside",
                         [i.code for i in validate.check_results_pages(decided)])
        # So does one made beside the close margin, once official.
        held = keeps.held(self)
        quiet = self.step({"unread": "x"}, None, held, self.D1)
        self.assertIn(self.RID, quiet["officeResults"]["pageHeld"])
        released = self.step(self.newer(CLOSE, official=("11/03/2026",)), None, quiet, self.D2)
        self.assertEqual(released["races"][self.RID]["source"], "office")
        self.assertNotIn("pageHeld", released["officeResults"])

    def test_a_kept_disagreement_says_where_the_page_now_agrees(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        first = keeps.disagreed(self)
        later = self.step({"unread": "x"}, SCALISE_WINS, first, self.D1)
        item = later["officeResults"]["disagree"][self.RID]
        self.assertEqual(item["pageSays"], item["officeSays"])
        self.assertTrue(item["pageAgrees"])
        named = [d for i in validate.check_results_pages(later)
                 if i.code == "office-result-disagrees" for d in i.detail]
        self.assertTrue(any(d.startswith(self.RID) and "the page now agrees" in d
                            for d in named), named)
        # The page names someone else again: no longer said to agree.
        back = self.step({"unread": "x"}, JEWETT_WINS, later, self.D2)
        self.assertNotIn("pageAgrees", back["officeResults"]["disagree"][self.RID])


class TestADecemberHoldOutlivesASilentPage(NoGap):
    """The same of a December disagreement: LA-5's page silent for a run with
    the office unread, then calling Moore again on a run with the office
    unread, made her "elected" over the office's December count for Firment
    (the verifier of the fix that keeps a hold)."""

    holds = TestAHoldKeepsTheRecordItStandsOn
    RID, BOTH, D0, D1, D2 = holds.RID, holds.BOTH, holds.D0, holds.D1, holds.D2
    moore_page = holds.moore_page
    disagreed = holds.disagreed
    assert_still_disagrees = holds.assert_still_disagrees
    step = TestAHoldOutlivesAPageThatFallsSilent.step

    def test_a_december_disagreement_outlives_a_silent_page(self):
        holds = self
        rid = self.RID
        first = self.disagreed()
        quiet = self.step({"unread": "x"}, None, first, holds.D1)
        self.assertTrue(quiet["officeResults"]["disagree"][rid]["pageSilentOn"])
        later = self.step({"unread": "x"}, self.moore_page(), quiet, holds.D2)
        self.assert_still_disagrees(later, first)
        self.assertNotIn("pageSilentOn", later["officeResults"]["disagree"][rid])
        named = [d for i in validate.check_results_pages(later)
                 if i.code == "office-result-disagrees" for d in i.detail]
        self.assertTrue(any(d.startswith(rid) and f"as the read of {holds.D0}" in d
                            for d in named), named)
        # The December record the disagreement stands on, kept with it.
        self.assertTrue(later["officeResults"]["races"][rid]["2026-12-12"]["verdict"])


class TestAFirstRoundBackToPartialCountsKeepsItsRecord(NoGap):
    """A first-round file gone back to partial counts after a November
    disagreement overwrote the full count's record, and where the partial
    counts led the page's call, the call went live, credited to Wikipedia,
    with no warning (the verifier of the fix that keeps a hold). The last
    read's full record stays the record, this read's counts beside it
    (``heldRead``), and the hold stands, as a December file's does."""

    RID = "H-LA-01-2026"
    D1, D2, D3 = day_after(EARLY), day_after(EARLY, 2), day_after(EARLY, 3)

    def partial(self, choices, today):
        files = restamp(feeds({"11/03/2026": {1: (choices, PARTIAL)}}), "20261103",
                        written=f"{today.isoformat()}T10:00:00")
        return read_files(files, today=today)

    def assert_kept(self, cache, today):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        keeps.assert_set_aside(self, cache, "disagree")
        self.assertEqual(cache["officeResults"]["disagree"][self.RID]["officeSays"],
                         "elected H0LA01087")
        record = cache["officeResults"]["races"][self.RID]["2026-11-03"]
        self.assertEqual(record["reporting"]["precincts"], [791, 791])
        self.assertTrue(record["verdict"])
        self.assertEqual(record["keptFrom"], EARLY.isoformat())
        self.assertEqual(record["heldRead"]["reporting"]["precincts"], [40, 791])
        self.assertEqual(record["heldRead"]["on"], today.isoformat())
        self.assertIn("40 of 791 precincts", cache["officeResults"]["held"][self.RID])

    def test_partial_counts_after_a_disagreement_keep_the_record_and_the_hold(self):
        keeps = TestAReadThatConcludesNothingKeepsTheLastHold
        for leads in (LA1_JEWETT_LEADS, LA1_SCALISE_LEADS):
            with self.subTest(leads=leads[2][1] > leads[3][1] and "Jewett" or "Scalise"):
                first = keeps.disagreed(self)
                later = self.build(self.partial(leads, self.D1), today=self.D1,
                                   page=JEWETT_WINS, previous=first)
                self.assert_kept(later, self.D1)
                again = self.build(self.partial(leads, self.D2), today=self.D2,
                                   page=JEWETT_WINS, previous=later)
                self.assert_kept(again, self.D2)
                # A full count settles it afresh: a disagreement, this read's own.
                full = restamp(feeds({"11/03/2026": {1: LA1}}), "20261103",
                               written=f"{self.D3.isoformat()}T10:00:00")
                done = self.build(read_files(full, today=self.D3), today=self.D3,
                                  page=JEWETT_WINS, previous=again)
                self.assertNotIn("keptFrom", done["officeResults"]["disagree"][self.RID])
                record = done["officeResults"]["races"][self.RID]["2026-11-03"]
                self.assertNotIn("heldRead", record)
                self.assertNotIn("keptFrom", record)

    def test_partial_counts_with_no_verdict_before_are_read_as_ever(self):
        # No full count was read before: the partial counts are the record,
        # and a page call they lead stands, as it always has.
        cache = self.build(self.partial(LA1_JEWETT_LEADS, self.D1), today=self.D1,
                           page=JEWETT_WINS)
        record = cache["officeResults"]["races"][self.RID]["2026-11-03"]
        self.assertEqual(record["reporting"]["precincts"], [40, 791])
        self.assertNotIn("heldRead", record)
        self.assertFalse(cache["officeResults"]["disagree"])


# ------------------------------------------------------------------ the real-cache checks

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_contests  # noqa: E402
import test_results  # noqa: E402


def with_office_results(today, rounds):
    """The committed results cache with Louisiana's seats as the office's
    results decide them on *today* (rule 64), as the refresh's next read
    writes them: the checks it runs on what it read must pass on them."""
    gap, results._GAP = results._GAP, 0
    try:
        built = results.build(FIELD, CALENDAR, today=today, log=lambda *_: None,
                              fetch=lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                              qualified=(copy.deepcopy(LISTS), {"source": "LA SoS"}),
                              office_results=read(rounds, today=today))
    finally:
        results._GAP = gap
    cache = copy.deepcopy(results.load_cache(test_results.ROOT))
    for rid in ("H-LA-01-2026", "H-LA-05-2026"):
        assert built["races"][rid]["source"] == "office", rid
        cache["races"][rid] = built["races"][rid]
    cache["officeResults"] = built["officeResults"]
    cache["asOf"] = today.isoformat()
    return cache


class OfficeCache:
    """The made caches, made once, when a class that reads them is set up."""
    made = {}

    @classmethod
    def office_cache(cls):
        key = cls.ROUND
        if key not in OfficeCache.made:
            rounds = {"11/03/2026": {1: LA1, 5: LA5}}
            if key == "december":
                rounds["12/12/2026"] = {5: TWO}
            OfficeCache.made[key] = with_office_results(
                DECEMBER_AFTER if key == "december" else AFTER, rounds)
        return copy.deepcopy(OfficeCache.made[key])


class TestTheRealCacheChecksReadNovembersOfficeResults(OfficeCache,
                                                       test_results.RealCacheChecks,
                                                       unittest.TestCase):
    """The refresh's first office read failed its own unit step: a check of the
    real cache read Louisiana's elected seats as resolved before the December
    runoff date."""
    ROUND = "november"

    @classmethod
    def setUpClass(cls):
        cls.cache = cls.office_cache()

    def test_the_cache_holds_what_it_tests(self):
        self.assertEqual(self.cache["races"]["H-LA-01-2026"]["status"]["H0LA01087"], "elected")
        self.assertEqual(self.cache["races"]["H-LA-05-2026"]["status"]["H6LA05317"], "runoff")


class TestTheRealCacheChecksReadDecembersOfficeResults(OfficeCache,
                                                       test_results.RealCacheChecks,
                                                       unittest.TestCase):
    ROUND = "december"

    @classmethod
    def setUpClass(cls):
        cls.cache = cls.office_cache()

    def test_the_cache_holds_what_it_tests(self):
        race = self.cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["status"]["H6LA05317"], "elected")
        self.assertEqual(race["decidedIn"]["date"], "2026-12-12")


class TestTheRealBuildReadsNovembersOfficeResults(OfficeCache, test_contests.RealBuildChecks,
                                                  unittest.TestCase):
    ROUND = "november"

    @classmethod
    def results_cache(cls):
        return cls.office_cache()


class TestTheRealBuildReadsDecembersOfficeResults(OfficeCache, test_contests.RealBuildChecks,
                                                  unittest.TestCase):
    ROUND = "december"

    @classmethod
    def results_cache(cls):
        return cls.office_cache()


if __name__ == "__main__":
    unittest.main()
