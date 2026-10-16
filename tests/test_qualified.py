"""Louisiana's November 3 House ballot, from the Secretary of State's list."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import qualified, results  # noqa: E402

HEADER = ('"Election","OfficeTitle","OfficeTitleDescription","NumberToBeElected",'
          '"BallotFirstName","BallotLastName","BallotSuffix","Address","City","State","Zip",'
          '"Address Mismatch","Phone","Email Address","Party","Race","Gender","Filed Date",'
          '"Outcome"')


def line(office, district, first, last, suffix="", party="Republican", filed="08/05/2026",
         outcome=""):
    return ",".join(f'"{v}"' for v in (
        "11/03/2026", office, district, "1", first, last, suffix, "1 Main St.", "Monroe",
        "LA", "71201", "No", "(318) 555-0100", "someone@example.com", party, "White",
        "Female", filed, outcome))


EXPORT = "﻿" + "\n".join([
    HEADER,
    line("U. S. Senator", "", "Julia", "Letlow"),
    line("U. S. Representative", "5th Congressional District", "Michael", "Echols"),
    line("U. S. Representative", "5th Congressional District", "Stewart", "Cathey", "Jr."),
    line("U. S. Representative", "5th Congressional District", "Patricia", "'Pat' Moore",
         party="Democrat", filed="08/07/2026"),
    line("U. S. Representative", "3rd Congressional District", "'Clay'", "Higgins"),
    line("U. S. Representative", "3rd Congressional District", "Tia", "LeBrun",
         party="No Party", outcome="Withdrew"),
]) + "\n"


class TestExport(unittest.TestCase):
    def test_the_house_seats_and_only_what_the_ballot_says(self):
        races = qualified.parse_export(EXPORT)
        self.assertEqual(sorted(races), ["H-LA-03-2026", "H-LA-05-2026"])     # no Senate
        self.assertEqual(races["H-LA-05-2026"][0],
                         {"name": "Michael Echols", "party": "Republican",
                          "filed": "2026-08-05", "withdrew": False})
        # Nothing about where anyone lives or how to reach them is kept.
        kept = {k for entries in races.values() for e in entries for k in e}
        self.assertEqual(kept, {"name", "party", "filed", "withdrew"})
        self.assertNotIn("Main St", repr(races))
        self.assertNotIn("555", repr(races))

    def test_names_as_the_ballot_prints_them(self):
        races = qualified.parse_export(EXPORT)
        names = [e["name"] for e in races["H-LA-05-2026"] + races["H-LA-03-2026"]]
        self.assertIn("Stewart Cathey Jr.", names)
        self.assertIn('Patricia "Pat" Moore', names)        # a nickname inside keeps quotes
        self.assertIn("Clay Higgins", names)                # one standing in for a name does not

    def test_a_withdrawal_is_marked(self):
        lebrun = qualified.parse_export(EXPORT)["H-LA-03-2026"][1]
        self.assertTrue(lebrun["withdrew"])

    def test_an_outcome_it_does_not_know_is_refused(self):
        text = EXPORT.replace('"Withdrew"', '"Elected"')
        with self.assertRaises(qualified.QualifiedError):
            qualified.parse_export(text)

    def test_a_renamed_column_fails_loudly(self):
        with self.assertRaises(qualified.QualifiedError):
            qualified.parse_export(EXPORT.replace('"BallotLastName"', '"LastName"'))

    def test_the_portal_pages(self):
        page = ('<select id="ElectionId"><option value="345">12/12/2026</option>'
                '<option selected="selected" value="344">11/03/2026</option></select>')
        self.assertEqual(qualified.election_id(page, "11/03/2026"), "344")
        with self.assertRaises(qualified.QualifiedError):
            qualified.election_id(page, "11/05/2024")
        offices = ('<input type="checkbox" id="cb_67997" /> <label>U. S. Senator</label>'
                   '<input type="checkbox" id="cb_70195" /> <a>U. S. Representative, 1st '
                   'Congressional District</a><input type="checkbox" id="cb_1" /> Mayor')
        self.assertEqual(qualified.house_offices(offices), ["70195"])


def row(cid, name, district, party):
    return {"candidate_id": cid, "name": name, "state": "LA", "office": "H",
            "district_number": district, "party": party}


class NoGap(unittest.TestCase):
    def setUp(self):
        self._gap, results._GAP = results._GAP, 0

    def tearDown(self):
        results._GAP = self._gap


class TestTheBallotBeforeTheCount(NoGap):
    """Before November 3 the qualified list is the race; after it, the page."""

    title = "2026 United States House of Representatives elections in Louisiana"
    dates = {("LA", "H"): {"primary": "2026-11-03", "runoff": "2026-12-12"}}
    field = {"candidates": [row("H6LA05101", "ECHOLS, MICHAEL", 5, "REP"),
                            row("H6LA05103", "CATHEY, STEWART JR", 5, "REP"),
                            row("H6LA05199", "SMITH, JOHN", 5, "DEM")]}

    def run_build(self, today, page="\n==District 5==\nNothing yet.\n"):
        listed = qualified.parse_export(EXPORT)
        return results.build(self.field, self.dates, today=today, log=lambda *_: None,
                             fetch=lambda t: page if t == self.title else
                             (_ for _ in ()).throw(results.PageMissing(t)),
                             qualified=(listed, {"source": qualified.SOURCE}))

    def test_before_the_count_the_list_is_the_ballot(self):
        cache = self.run_build(datetime.date(2026, 10, 16))
        race = cache["races"]["H-LA-05-2026"]
        self.assertNotIn("H-LA-05-2026", cache["pending"])
        self.assertEqual(race["source"], "qualified")
        self.assertEqual(race["status"], {"H6LA05101": "qualified", "H6LA05103": "qualified"})
        # A qualified candidate with no filing over $5,000 is named on the race.
        self.assertEqual(race["unmatched"], {'Patricia "Pat" Moore': "qualified"})
        self.assertEqual(race["decided"], {"general": True, "parties": ["all"]})
        self.assertEqual(race["party"]["H6LA05101"], "republican")

    def test_a_filer_not_on_it_is_not_on_the_ballot(self):
        cache = self.run_build(datetime.date(2026, 10, 16))
        smith = {"id": "FEC_H6LA05199", "fecCandidateId": "H6LA05199", "isCandidate": True,
                 "source": "fec-field", "name": "John Smith", "party": "Democrat",
                 "state": "LA", "chamber": "House (Candidate)", "districtNum": 5}
        results.apply_cache([smith], cache)
        self.assertEqual(smith["raceStatus"], "unlisted")

    def test_a_cache_reloaded_before_the_count_keeps_the_list(self):
        cache = self.run_build(datetime.date(2026, 10, 16))
        kept = results.respect_open_primaries(cache)
        self.assertIn("H-LA-05-2026", kept["races"])

    def test_after_the_count_the_page_decides(self):
        page = "\n".join([
            "\n==District 5==",
            "{{Election box begin no change", "| title=2026 Louisiana's 5th congressional "
            "district election", "}}",
            "{{Election box winning candidate with party link no change",
            " | party = Republican Party (United States)", " | candidate = Michael Echols",
            " | votes = 60,000", "}}",
            "{{Election box candidate with party link no change",
            " | party = Republican Party (United States)", " | candidate = Stewart Cathey Jr.",
            " | votes = 40,000", "}}",
            "{{Election box total no change", "| votes = 100,000", "}}",
            "{{Election box end}}", ""])
        cache = self.run_build(datetime.date(2026, 11, 4), page)
        race = cache["races"]["H-LA-05-2026"]
        self.assertNotEqual(race.get("source"), "qualified")
        self.assertEqual(race["status"]["H6LA05101"], "elected")

    def test_after_the_count_an_unmarked_page_leaves_the_list(self):
        cache = self.run_build(datetime.date(2026, 11, 4))
        self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "qualified")

    def test_another_state_read_first_does_not_lose_the_list(self):
        # results.build names a race's ballot parties ``listed`` in its loop;
        # that once overwrote the qualified list, and on the real run every
        # Louisiana seat stayed pending with Wyoming's names in the metadata.
        wy = dict(row("H6WY00001", "HAGEMAN, HARRIET", 0, "REP"), state="WY")
        field = {"candidates": self.field["candidates"] + [wy]}
        dates = {**self.dates, ("WY", "H"): {"primary": "2026-08-18", "runoff": None}}
        wy_page = "\n".join([
            "{{Election box begin no change", "| title = Republican primary results", "}}",
            "{{Election box winning candidate with party link no change",
            "| party = Republican Party (United States)", "| candidate = Harriet Hageman",
            "| votes = 9", "}}", "{{Election box end}}", ""])

        def fetch(title):
            if "Wyoming" in title:
                return wy_page
            raise results.PageMissing(title)
        cache = results.build(field, dates, today=datetime.date(2026, 10, 16), log=lambda *_: None,
                              fetch=fetch, qualified=(qualified.parse_export(EXPORT),
                                                      {"source": qualified.SOURCE}))
        self.assertIn("H-WY-00-2026", cache["races"])
        self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "qualified")
        self.assertNotIn("H-LA-05-2026", cache["pending"])
        self.assertEqual(cache["qualified"]["races"], ["H-LA-03-2026", "H-LA-05-2026"])

    def test_after_the_count_a_failed_page_does_not_take_the_list_away(self):
        # From November 4 the seat is no longer pending; a page that cannot be
        # fetched, is missing or has no section for it must not drop the list.
        for fetch in (lambda t: (_ for _ in ()).throw(OSError("timeout")),
                      lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                      lambda t: "\nNo district sections here.\n"):
            cache = results.build(self.field, self.dates, today=datetime.date(2026, 11, 5),
                                  log=lambda *_: None, fetch=fetch,
                                  qualified=(qualified.parse_export(EXPORT),
                                             {"source": qualified.SOURCE}))
            self.assertEqual(cache["races"]["H-LA-05-2026"]["source"], "qualified")

    def test_a_failed_read_of_the_list_keeps_the_last_one(self):
        before = self.run_build(datetime.date(2026, 10, 16))
        before["qualified"] = {"source": qualified.SOURCE, "fetched": "2026-10-16",
                               "races": ["H-LA-03-2026", "H-LA-05-2026"]}
        after = results.build(self.field, self.dates, today=datetime.date(2026, 10, 20),
                              log=lambda *_: None,
                              fetch=lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                              qualified=None)
        self.assertIn("H-LA-05-2026", after["pending"])
        kept = results.carry_qualified(after, before)
        self.assertEqual(kept, ["H-LA-03-2026", "H-LA-05-2026"])
        self.assertEqual(after["races"]["H-LA-05-2026"]["source"], "qualified")
        self.assertNotIn("H-LA-05-2026", after["pending"])
        self.assertTrue(after["qualified"]["carried"])
        self.assertEqual(after["qualified"]["fetched"], "2026-10-16")
        from kyc import validate
        codes = [i.code for i in validate.check_results_pages(after)]
        self.assertIn("qualified-list-stale", codes)

    def test_a_status_from_the_list_says_where_it_came_from(self):
        cache = self.run_build(datetime.date(2026, 10, 16))
        smith = {"id": "FEC_H6LA05199", "fecCandidateId": "H6LA05199", "isCandidate": True,
                 "source": "fec-field", "name": "John Smith", "party": "Democrat",
                 "state": "LA", "chamber": "House (Candidate)", "districtNum": 5}
        echols = {"id": "FEC_H6LA05101", "fecCandidateId": "H6LA05101", "isCandidate": True,
                  "source": "fec-field", "name": "Michael Echols", "party": "Republican",
                  "state": "LA", "chamber": "House (Candidate)", "districtNum": 5}
        results.apply_cache([smith, echols], cache)
        self.assertEqual((smith["raceStatus"], smith["raceStatusSource"]), ("unlisted", "qualified"))
        self.assertEqual((echols["raceStatus"], echols["raceStatusSource"]),
                         ("qualified", "qualified"))

    def test_a_seat_still_on_the_list_days_after_the_count_is_reported(self):
        from kyc import validate
        cache = self.run_build(datetime.date(2026, 11, 7))
        issues = {i.code: i for i in validate.check_results_pages(cache)}
        self.assertIn("H-LA-05-2026", issues["general-uncalled"].detail)

    def test_a_failed_read_leaves_the_seat_pending(self):
        cache = results.build(self.field, self.dates, today=datetime.date(2026, 10, 16),
                              log=lambda *_: None,
                              fetch=lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                              qualified=None)
        self.assertIn("H-LA-05-2026", cache["pending"])
        self.assertNotIn("H-LA-05-2026", cache["races"])


class TestValidate(unittest.TestCase):
    def test_qualified_is_a_status_the_build_knows(self):
        from kyc import validate
        race = {"id": "H-LA-05-2026", "state": "LA", "settled": True, "incumbentIds": [],
                "candidateIds": ["a", "b"], "results": {"fromQualifiedList": True}}
        people = [{"id": pid, "name": name, "party": "Republican", "raceStatus": "qualified",
                   "raceId": "H-LA-05-2026", "isCandidate": True}
                  for pid, name in (("a", "Michael Echols"), ("b", "Stewart Cathey Jr."))]
        codes = [i.code for i in validate.check_results(people, [race])]
        # Would fail if "qualified" left RACE_STATUSES or NOVEMBER_STATUSES.
        self.assertNotIn("unknown-race-status", codes)
        self.assertNotIn("settled-race-without-nominee", codes)
        self.assertIn("qualified", validate.RACE_STATUSES)


class TestUnsureSurvivesSpellings(unittest.TestCase):
    def test_a_second_match_does_not_overwrite_the_first_ones_doubts(self):
        # _match_spellings calls match_names again; the race must keep the
        # ids the first call could not tell apart (rule 30).
        def ia(cid, name, party):
            return dict(row(cid, name, 1, party), state="IA")
        field = {"candidates": [ia("H6IA01001", "DOE, JOHN MICHAEL", "REP"),
                                ia("H6IA01002", "DOE, JOHN PATRICK", "REP"),
                                ia("H6IA01003", "ROE, RICHARD", "DEM")]}
        page = "\n".join([
            "\n==District 1==",
            "{{Election box begin no change", "| title = Republican primary results", "}}",
            "{{Election box winning candidate with party link no change",
            "| party = Republican Party (United States)", "| candidate = John Doe",
            "| votes = 9", "}}", "{{Election box end}}",
            "{{Election box begin no change", "| title = Democratic primary results", "}}",
            "{{Election box winning candidate with party link no change",
            "| party = Democratic Party (United States)", "| candidate = Rick Roe Smith",
            "| votes = 9", "}}", "{{Election box end}}",
            "{{Infobox election", "| nominee2 = Richard Roe", "}}", ""])
        dates = {("IA", "H"): {"primary": "2026-06-02", "runoff": None}}
        old = results._GAP
        results._GAP = 0
        try:
            cache = results.build(field, dates, today=datetime.date(2026, 10, 16),
                                  log=lambda *_: None,
                                  fetch=lambda t: page if "Iowa" in t else
                                  (_ for _ in ()).throw(results.PageMissing(t)))
        finally:
            results._GAP = old
        race = cache["races"]["H-IA-01-2026"]
        self.assertEqual(race["status"].get("H6IA01003"), "nominee")   # matched by its other spelling
        self.assertEqual(sorted(race["unsure"]), ["H6IA01001", "H6IA01002"])


if __name__ == "__main__":
    unittest.main()
