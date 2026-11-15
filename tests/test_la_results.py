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
        # The December election's record stays the baseline a stale file is
        # compared with.
        e = later["officeResults"]["elections"]["2026-12-12"]
        self.assertEqual(e["written"], "2026-12-12T18:55:18.130")
        self.assertEqual(e["unlistedOn"], DECEMBER_AFTER.isoformat())
        # And again the next day: still kept, from the kept record.
        again = self.build(read({"11/03/2026": {1: LA1, 5: LA5}}, today=DECEMBER_AFTER),
                           today=DECEMBER_AFTER, previous=later)
        self.assert_kept(again, "the office lists no results for 2026-12-12")

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
        # And a page that no longer decides the seat has no call to set aside.
        quiet = self.build({"unread": "x"}, previous=first)
        self.assertFalse(quiet["officeResults"]["disagree"])

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
        # Where the page no longer decides the seat, no hold is carried: the
        # failed read keeps none of the last read's own.
        quiet = self.build({"unread": "x"}, previous=first)
        self.assertNotIn("pageHeld", quiet["officeResults"])
        # So with no read made at all (none attempted): kept beside the page's
        # call, and none where the page makes none.
        self.assert_set_aside(self.build(None, page=SCALISE_CLOSE, previous=first), "pageHeld")
        self.assertNotIn("pageHeld", self.build(None, previous=first)["officeResults"])
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
