"""Tests for each seat's last election (kyc/seat_history.py): the Clerk of
the House's statistics read line by line, the result as the page shows it,
the check against a second compilation, and the race it is attached to.

A silent off-by-one between a name and a count would put one candidate's
votes beside another's name, so every block that does not pair is an
error. A district redrawn for 2026 never carries the old district's result
(rule 90), and a result the second source contradicts is withheld.
"""

import json
import re
import os
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import seat_history as sh  # noqa: E402
from kyc.courts import pdf_lines  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
L = "¶......................"     # a label's dot leader, as the reader gives it


def _house(*lines):
    return ["ALABAMA", "FOR UNITED STATES REPRESENTATIVE"] + list(lines) + \
        ["Recapitulation of Votes Cast in Alabama"]


class TestReading(unittest.TestCase):

    def test_labels_pair_with_counts_and_the_page_number_is_dropped(self):
        lines = _house("1.", "Barry Moore, Republican" + L, "Tom Holmes, Democrat" + L,
                       "Write-in" + L, "258,619", "70,929", "306",
                       "2.", "Caroleene Dobson, Republican" + L, "Shomari Figures, Democrat" + L,
                       "131,414", "158,041", "29", "ALABAMA—Continued",
                       "FOR UNITED STATES REPRESENTATIVE—Continued",
                       "3.", "Mike Rogers, Republican" + L, "243,848")
        states = sh.parse_statistics(lines, 2024)
        house = states["AL"]["house"]
        self.assertEqual([(r["name"], r["votes"]) for r in house[1]["rows"]],
                         [("Barry Moore", 258619), ("Tom Holmes", 70929)])
        self.assertEqual(house[1]["unnamed"], 306)
        # "29" was the page's number, not a third count.
        self.assertEqual([(r["name"], r["votes"]) for r in house[2]["rows"]],
                         [("Caroleene Dobson", 131414), ("Shomari Figures", 158041)])
        self.assertEqual(house[3]["rows"][0]["votes"], 243848)

    def test_names_and_counts_that_do_not_pair_are_an_error(self):
        lines = _house("1.", "Barry Moore, Republican" + L, "Tom Holmes, Democrat" + L,
                       "Ann Other, Green" + L, "258,619", "70,929")
        with self.assertRaises(sh.ClerkFormatError):
            sh.parse_statistics(lines, 2024)

    def test_fusion_lines_are_one_candidate(self):
        # New York's 1st district, and its 5th, where the second line names
        # two parties and no one.
        lines = ["NEW YORK", "FOR UNITED STATES REPRESENTATIVE",
                 "1.", "Nick LaLota, Republican" + L, "Conservative" + L,
                 "John P. Avlon, Democrat" + L, "Blank" + L,
                 "200,802", "25,483", "181,647", "19,984",
                 "5.", "Paul King, Republican" + L, "Conservative, Common Sense" + L,
                 "Gregory W. Meeks, Democrat" + L, "56,689", "5,840", "168,425",
                 "Recapitulation of Votes Cast in New York"]
        house = sh.parse_statistics(lines, 2024)["NY"]["house"]
        lalota = house[1]["rows"][0]
        self.assertEqual(lalota["votes"], 226285)
        self.assertEqual(lalota["lines"], [["Republican", 200802], ["Conservative", 25483]])
        self.assertEqual(house[1]["noVote"], 19984)
        self.assertEqual([(r["name"], r["votes"]) for r in house[5]["rows"]],
                         [("Paul King", 62529), ("Gregory W. Meeks", 168425)])

    def test_a_suffix_is_the_name_and_two_parties_are_both(self):
        self.assertEqual(sh.split_label("Michael J. LiPetri, Jr., Republican"),
                         ("Michael J. LiPetri, Jr.", "Republican"))
        self.assertEqual(sh.split_label("Mark Coester, Republican, Libertarian"),
                         ("Mark Coester", "Republican, Libertarian"))

    def test_an_unopposed_name_has_no_count_and_its_footnote_says_why(self):
        lines = ["FLORIDA", "FOR UNITED STATES REPRESENTATIVE",
                 "20.", "Sheila Cherfilus-McCormick, Democrat" + L, "(1)",
                 "21.", "Brian J. Mast, Republican" + L, "Thomas Witkop, Democrat" + L,
                 "277,435", "171,312",
                 "Recapitulation of Votes Cast in Florida", "1",
                 "According to Florida law, the names of those with no opposition are not "
                 "printed on the ballot.", "17", "GEORGIA"]
        florida = sh.parse_statistics(lines, 2024)["FL"]
        result = sh.result_of(florida["house"][20], florida["footnotes"], 2024, "FL")
        self.assertEqual(result["kind"], "unopposed")
        self.assertIn("no opposition", result["note"])
        self.assertNotIn("share", result["candidates"][0])

    def test_a_ranked_choice_final_round_counts_only_the_two_left(self):
        lines = ["MAINE", "FOR UNITED STATES REPRESENTATIVE", "2.",
                 "Austin Theriault, Republican" + L, "Jared F. Golden, Democrat" + L,
                 "Continuing Ballots" + L, "Exhausted Ballots" + L,
                 "194,445", "197,151", "391,596", "11,340", "29",
                 "Recapitulation of Votes Cast in Maine"]
        maine = sh.parse_statistics(lines, 2024)["ME"]
        result = sh.result_of(maine["house"][2], {}, 2024, "ME")
        self.assertEqual(result["kind"], "rcv-final")
        self.assertEqual(result["candidates"][0]["name"], "Jared F. Golden")
        self.assertEqual(result["candidates"][0]["share"], 50.3)
        self.assertEqual(result["total"], 194445 + 197151)

    def test_a_runoff_footnote_makes_the_result_the_runoffs(self):
        # 2020's Senate tables: each count after its name, a footnote marker
        # before a runoff's count, and the November vote of a third
        # candidate beside them.
        lines = ["GEORGIA", "FOR UNITED STATES SENATOR",
                 "(For full term beginning January 3, 2021)",
                 "Jon Ossoff, Democrat ......................", "2", "2,269,923",
                 "David Perdue, Republican ..................", "2", "2,214,979",
                 "Shane Hazel, Libertarian ..................", "115,039",
                 "Recapitulation of Votes Cast in Georgia", "2",
                 "This vote count is from Georgia's January 5, 2021, runoff election, which was "
                 "held because neither candidate received a majority of the vote in Georgia's",
                 "general election on November 3, 2020.", "HAWAII"]
        georgia = sh.parse_statistics(lines, 2020, ("senate",))["GA"]
        contest = georgia["senate"][0]
        self.assertEqual(contest["termEnds"], "2027-01-03")
        result = sh.result_of(contest, georgia["footnotes"], 2020, "GA")
        self.assertEqual(result["kind"], "runoff")
        self.assertEqual(result["date"], "2021-01-05")
        self.assertEqual([c["name"] for c in result["candidates"]], ["Jon Ossoff", "David Perdue"])
        self.assertEqual(result["total"], 2269923 + 2214979)

    def test_shares_leave_out_ballots_that_chose_no_one(self):
        contest = {"rows": [{"name": "A B", "party": "Democrat", "votes": 600, "lines": []},
                            {"name": "C D", "party": "Republican", "votes": 300, "lines": []}],
                   "unnamed": 100, "noVote": 5000, "rcvRound": False}
        result = sh.result_of(contest, {}, 2024, "VA")
        self.assertEqual(result["total"], 1000)
        self.assertEqual([c["share"] for c in result["candidates"]], [60.0, 30.0])
        self.assertEqual(result["margin"], 30.0)
        self.assertEqual(result["othersShare"], 10.0)

    def test_alaskas_counts_are_first_choices(self):
        contest = {"rows": [{"name": "Nick Begich", "party": "Republican", "votes": 159550,
                             "lines": []},
                            {"name": "Mary Sattler Peltola", "party": "Democrat",
                             "votes": 152828, "lines": []}],
                   "unnamed": 750, "noVote": 0, "rcvRound": False}
        self.assertEqual(sh.result_of(contest, {}, 2024, "AK")["rankedChoice"], "first-choices")
        self.assertNotIn("rankedChoice", sh.result_of(contest, {}, 2020, "AK"))

    def test_each_file_says_which_byte_is_which_accent(self):
        # 0x83 is "é" in 2020's and 2022's files and "í" in 2024's.
        data = (b"%PDF-1.6\n1 0 obj<</Type/Encoding/Differences[128/space 129/uacute "
                b"130/aacute 131/iacute 132/eacute 133/ntilde]>>endobj\n")
        decode = sh.clerk_decoder(data)
        self.assertEqual(decode(b"Jes\x81s Garc\x83a, Andr\x84 Villafa\x85e"),
                         "Jesús García, André Villafañe")
        with self.assertRaises(sh.ClerkFormatError):
            decode(b"\x86")

    def test_the_decoder_reads_a_differences_array_inside_an_object_stream(self):
        body = zlib.compress(b"<</Differences[129/uacute 130/aacute 131/eacute]>>")
        data = (b"%%PDF-1.6\n2 0 obj<</Type/ObjStm/Filter/FlateDecode/Length %d>>stream\n"
                % len(body)) + body + b"\nendstream\nendobj\n"
        self.assertEqual(sh.clerk_decoder(data)(b"Ang\x83lica"), "Angélica")

    def test_text_comes_out_of_the_pdf_with_the_leader_kept(self):
        stream = (b"BT /F1 9 Tf 1 0 0 1 72 700 Tm (Barry Moore, Republican\x80.......)Tj ET\n"
                  b"BT /F1 9 Tf 1 0 0 1 400 700 Tm (258,619)Tj ET\n")
        packed = zlib.compress(stream)
        pdf = (b"%%PDF-1.6\n1 0 obj\n<</Length %d/Filter/FlateDecode>>stream\n" % len(packed) +
               packed + b"\nendstream\nendobj\n")
        lines = pdf_lines(pdf, decode=sh.clerk_decoder(pdf))
        self.assertEqual(lines, ["Barry Moore, Republican¶.......", "258,619"])


def _result(*people, kind="general", year=2024):
    total = sum(v for _n, _p, v in people)
    return {"year": year, "kind": kind, "total": total,
            "candidates": [{"name": n, "party": p, "votes": v, "share": 0} for n, p, v in people]}


class TestSecondSource(unittest.TestCase):

    def test_a_count_a_vote_apart_agrees_and_the_difference_is_kept(self):
        # Iowa's 1st district: Wikipedia gives the runner-up one more vote.
        result = _result(("Mariannette Miller-Meeks", "Republican", 206955),
                         ("Christina Bohannan", "Democrat", 206156))
        rows = [{"name": "Mariannette Miller-Meeks", "votes": 206955, "won": True},
                {"name": "Christina Bohannan", "votes": 206157, "won": False}]
        verdict, differences = sh._check(result, rows)
        self.assertEqual(verdict, "agree")
        self.assertEqual(differences, [{"name": "Christina Bohannan", "clerk": 206156,
                                        "other": 206157}])

    def test_counts_read_against_the_wrong_names_disagree(self):
        result = _result(("Lizzie Fletcher", "Democrat", 149820),
                         ("Caroline Kane", "Republican", 94651))
        rows = [{"name": "Lizzie Fletcher", "votes": 94651}, {"name": "Caroline Kane", "votes": 149820}]
        self.assertEqual(sh._check(result, rows)[0], "disagree")

    def test_a_winner_the_other_source_does_not_mark_disagrees(self):
        result = _result(("Ann Able", "Democrat", 1000), ("Bob Baker", "Republican", 990))
        rows = [{"name": "Ann Able", "votes": 1000, "won": False},
                {"name": "Bob Baker", "votes": 990, "won": True}]
        self.assertEqual(sh._check(result, rows)[0], "disagree")

    def test_a_table_about_other_people_says_nothing(self):
        result = _result(("Ann Able", "Democrat", 1000), ("Bob Baker", "Republican", 990))
        self.assertEqual(sh._check(result, [{"name": "Carl Cole", "votes": 1000}])[0], None)

    def test_two_of_one_surname_are_told_apart_by_first_name(self):
        # South Dakota, 2024: Dusty Johnson and Sheryl Johnson.
        result = _result(("Dusty Johnson", "Republican", 303630),
                         ("Sheryl Johnson", "Democrat", 117818))
        rows = [{"name": "Dusty Johnson", "votes": 303630, "won": True},
                {"name": "Sheryl Johnson", "votes": 117818}]
        self.assertEqual(sh._check(result, rows)[0], "agree")

    def test_a_surname_a_letter_apart_is_matched_only_alone(self):
        result = _result(("Steve Cohen", "Democrat", 159522),
                         ("Charlotte Bergmann", "Republican", 57411))
        rows = [{"name": "Steve Cohen", "votes": 159522, "won": True},
                {"name": "Charlotte Bergman", "votes": 57411}]
        self.assertEqual(sh._check(result, rows)[0], "agree")

    def test_a_write_in_runner_up_checks_the_winner_alone(self):
        result = _result(("Thomas Massie", "Republican", 278386),
                         ("Benjamin August Middendorf", "Write-in", 1131))
        self.assertEqual(sh._check(result, [{"name": "Thomas Massie", "votes": 278386,
                                             "won": True}])[0], "agree")

    def test_an_open_primary_box_holds_the_general_after_its_marker(self):
        text = ("{{Election box open primary begin no change|title=California's 12th "
                "congressional district, 2024}}\n"
                "{{Election box candidate with party link no change|party=Democratic Party "
                "(United States)|candidate=[[Lateefah Simon]]|votes=86,031}}\n"
                "{{Election box open primary general election no change}}\n"
                "{{Election box winning candidate with party link no change|party=Democratic "
                "Party (United States)|candidate=[[Lateefah Simon]]|votes='''185,176'''}}\n"
                "{{Election box candidate with party link no change|party=Democratic Party "
                "(United States)|candidate=Jennifer Tran|votes=97,849}}\n{{Election box end}}")
        boxes = sh.wiki_boxes(text)
        self.assertEqual([stage for stage, _ in boxes], ["primary", "general"])
        self.assertEqual([(r["name"], r["votes"]) for r in boxes[1][1]],
                         [("Lateefah Simon", 185176), ("Jennifer Tran", 97849)])
        result = _result(("Lateefah Simon", "Democrat", 185176),
                         ("Jennifer Tran", "Democrat", 97849))
        self.assertEqual(sh.wiki_check(result, text)[0], "agree")

    def test_mit_rows_marked_unofficial_check_nothing(self):
        raw = ("year,state_po,special,stage,candidate,candidatevotes,unofficial\n"
               "2024,NE,True,GEN,PETE RICKETTS,585103.0,True\n")
        mit = sh.read_mit_senate(raw)
        result = _result(("Pete Ricketts", "Republican", 585103), ("Preston Love", "Democrat", 1))
        self.assertEqual(sh.mit_check(result, mit, "NE", True), (None, []))


class TestRaces(unittest.TestCase):

    def _cache(self):
        house = dict(_result(("Barry Moore", "Republican", 258619),
                             ("Tom Holmes", "Democrat", 70929)),
                     date="2024-11-05", margin=56.9, others=306, othersShare=0.1,
                     allCandidates=2, checked={"by": "wikipedia", "page": "P"})
        senate_2020 = dict(_result(("James M. Inhofe", "Republican", 979140),
                                   ("Abby Broyles", "Democrat", 509763), year=2020),
                           date="2020-11-03", margin=30.1, others=0, othersShare=0,
                           allCandidates=2, term="full", termEnds="2027-01-03",
                           checked={"by": "mit"})
        senate_2022 = dict(_result(("Markwayne Mullin", "Republican", 710643),
                                   ("Kendra Horn", "Democrat", 405389), year=2022),
                           date="2022-11-08", margin=26.6, others=0, othersShare=0,
                           allCandidates=2, term="unexpired", termEnds="2027-01-03",
                           checked={"by": "mit"})
        return {"read": "2026-10-18", "house": {"AL-1": house, "VA-1": house},
                "senate": {"OK-2020-full": senate_2020, "OK-2022-unexpired": senate_2022},
                "withheld": [{"seat": "NY-5", "year": 2024, "why": "disagree",
                              "result": house}]}

    def test_a_redrawn_district_never_carries_the_old_districts_result(self):
        # Alabama redrew its map for 2026: its 1st district's 2024 result is
        # other voters' (rule 90).
        races = [{"id": "H-AL-1-2026", "chamber": "House", "state": "AL", "district": 1}]
        sh.apply(races, self._cache())
        self.assertEqual(races[0]["lastElection"], {"redrawn": True, "year": 2024})

    def test_a_district_on_the_same_lines_shows_its_2024_result(self):
        races = [{"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}]
        self.assertEqual(sh.apply(races, self._cache()), 1)
        last = races[0]["lastElection"]
        self.assertEqual(last["candidates"][0]["name"], "Barry Moore")
        self.assertEqual(last["checkedBy"], "P")
        self.assertNotIn("differences", last)
        # The page cites the Clerk's file for that year, from one table.
        self.assertIn("statistics2024.pdf", sh.page_sources()["2024"]["url"])
        self.assertIn("November 5, 2024", sh.page_sources()["2024"]["title"])

    def test_a_withheld_result_says_so(self):
        races = [{"id": "H-NY-5-2026", "chamber": "House", "state": "NY", "district": 5}]
        sh.apply(races, self._cache())
        self.assertEqual(races[0]["lastElection"], {"withheld": "disagree", "year": 2024})

    def test_a_senate_seat_shows_its_latest_election_to_that_term(self):
        # Oklahoma's class II seat was last elected in 2022's special.
        races = [{"id": "S-OK-2026", "chamber": "Senate", "state": "OK", "senateClass": 2}]
        sh.apply(races, self._cache())
        self.assertEqual(races[0]["lastElection"]["year"], 2022)
        self.assertEqual(races[0]["lastElection"]["term"], "unexpired")

    # Who took a seat after its counted election (PR #110 review). The
    # people are the cache's fixtures and a record written here, so the
    # checks hold in every phase of the cycle (rule 68).
    def _record(self, **incumbents):
        return {"cycle": 2026, "electionDay": "2026-11-03", "incumbents": incumbents}

    def test_a_seat_filled_by_a_special_election_is_not_its_last_election(self):
        # VA-11: Gerald Connolly won in 2024, died in office, and James
        # Walkinshaw won the September 2025 special. "The last election to
        # this district" over Connolly's result was false.
        races = [{"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}]
        record = self._record(**{"H-VA-1-2026": {
            "name": "James R. Walkinshaw", "termStart": "2025-09-10", "appointed": False}})
        sh.apply(races, self._cache(), record=record)
        self.assertEqual(races[0]["lastElection"]["seatedSince"],
                         {"name": "James R. Walkinshaw", "since": "2025-09-10",
                          "how": "special-election"})

    def test_a_holder_of_the_winners_surname_is_still_someone_else(self):
        # AZ-7: Raúl M. Grijalva won in 2024; Adelita S. Grijalva won the
        # special after his death.
        races = [{"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}]
        record = self._record(**{"H-VA-1-2026": {
            "name": "Adelia S. Moore", "termStart": "2025-11-12"}})
        sh.apply(races, self._cache(), record=record)
        self.assertIn("seatedSince", races[0]["lastElection"])

    def test_the_winner_sworn_in_late_is_the_winner(self):
        # Seated after January 3 by the snapshot, under a fuller name: the
        # 2024 winner, not a special election's.
        races = [{"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}]
        snapshot = {"legislators": [
            {"name": "Barry Moore Jr.", "chamber": "House", "state": "VA", "district": 1,
             "termStart": "2025-03-01"},
            {"name": "Someone Else", "chamber": "House", "state": "VA", "district": 1,
             "termStart": "2025-01-20"}]}
        sh.apply(races, self._cache(), record=self._record(), snapshot=snapshot)
        self.assertNotIn("seatedSince", races[0]["lastElection"])

    def test_an_appointed_senator_is_said_as_an_appointment(self):
        races = [{"id": "S-OK-2026", "chamber": "Senate", "state": "OK", "senateClass": 2}]
        record = self._record(**{"S-OK-2026": {
            "name": "Alan Armstrong", "termStart": "2026-03-24", "appointed": True}})
        sh.apply(races, self._cache(), record=record)
        self.assertEqual(races[0]["lastElection"]["seatedSince"]["how"], "appointment")

    def test_a_member_seated_after_election_day_is_the_races_own_winner(self):
        # In January the snapshot seats the 2026 winners: their result is
        # the race's, not a special since the counted one.
        races = [{"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}]
        snapshot = {"legislators": [
            {"name": "New Member", "chamber": "House", "state": "VA", "district": 1,
             "termStart": "2027-01-03"}]}
        sh.apply(races, self._cache(), record=self._record(), snapshot=snapshot)
        self.assertNotIn("seatedSince", races[0]["lastElection"])

    def test_the_committed_record_marks_every_special_since_2024(self):
        # Every House seat on the same lines whose record incumbent was
        # seated after the 2024 winners is marked, and none other.
        cache = sh.load_cache(ROOT)
        if cache is None:
            self.skipTest("no seat history cache")
        with open(os.path.join(ROOT, "candidate_profiles_site", "data", "record_2026.json"),
                  encoding="utf-8") as handle:
            record = json.load(handle)
        races = [dict(r, id=k) for k, r in record["races"].items()]
        sh.apply(races, cache, record=record)
        from kyc.districts import REDRAWN
        for race in races:
            if race["chamber"] != "House" or race["state"] in REDRAWN:
                continue
            last = race["lastElection"]
            inc = record["incumbents"].get(race["id"]) or {}
            late = (inc.get("termStart") or "") > "2025-02-02"
            if "candidates" in last:
                self.assertEqual("seatedSince" in last, late, race["id"])

    def test_the_committed_cache_covers_every_race_it_can(self):
        cache = sh.load_cache(ROOT)
        if cache is None:
            self.skipTest("no seat history cache")
        with open(os.path.join(ROOT, "candidate_profiles_site", "data", "record_2026.json"),
                  encoding="utf-8") as handle:
            record = json.load(handle)
        races = [dict(r, id=k) for k, r in record["races"].items()]
        sh.apply(races, cache)
        # Every race has a result, a redrawn district's note, or a reason.
        self.assertFalse([r["id"] for r in races if "lastElection" not in r])
        from kyc.districts import REDRAWN
        for race in races:
            last = race["lastElection"]
            if race["chamber"] == "House" and race["state"] in REDRAWN:
                self.assertEqual(set(last), {"redrawn", "year"}, race["id"])
            elif "candidates" in last and last.get("kind") != "unopposed":
                shares = [c["share"] for c in last["candidates"]]
                self.assertEqual(shares, sorted(shares, reverse=True), race["id"])
                self.assertTrue(last.get("checkedBy"), race["id"])


class TestEarlierYears(unittest.TestCase):
    """The tables of 2018 to 2022 that 2024's did not have (VISUALS-33)."""

    def test_footnote_markers_among_a_districts_counts_mark_the_runoff(self):
        # Louisiana's 5th, 2020: the November open primary's counts, with the
        # two the December runoff left footnoted at the runoff's counts.
        lines = ["LOUISIANA", "FOR UNITED STATES REPRESENTATIVE", "5.",
                 "Sandra “Candy” Christophe, Democrat" + L, "Martin Lemelle, Jr., Democrat" + L,
                 "Luke J. Letlow, Republican" + L, "Lance Harris, Republican" + L,
                 "50,812", "32,186", "1", "49,183", "1", "30,124",
                 "Recapitulation of Votes Cast in Louisiana", "1",
                 "This vote count is from the runoff election held on December 5, 2020. Luke "
                 "J. Letlow received 67,118 votes in the general election held on November 3,",
                 "MAINE"]
        la = sh.parse_statistics(lines, 2020)["LA"]
        rows = la["house"][5]["rows"]
        self.assertEqual([(r["name"], r["votes"], r["note"]) for r in rows],
                         [("Sandra “Candy” Christophe", 50812, None),
                          ("Martin Lemelle, Jr.", 32186, None),
                          ("Luke J. Letlow", 49183, 1), ("Lance Harris", 30124, 1)])
        result = sh.result_of(la["house"][5], la["footnotes"], 2020, "LA")
        self.assertEqual(result["kind"], "runoff")
        self.assertEqual(result["date"], "2020-12-05")
        self.assertEqual([c["name"] for c in result["candidates"]], ["Luke J. Letlow", "Lance Harris"])

    def test_lone_digits_that_are_not_the_surplus_are_an_error(self):
        # Three surplus tokens, two of them lone digits: not markers alone.
        lines = _house("1.", "A B, Republican" + L, "C D, Democrat" + L,
                       "1", "100,000", "9", "7", "90,000", "Recapitulation of Votes Cast in Alabama")
        with self.assertRaises(sh.ClerkFormatError):
            sh.parse_statistics(lines, 2018)

    def test_a_later_ranked_choice_round_is_the_final_round_between_two(self):
        # Maine's 2nd, 2022: round 2's counts for the two it left, footnoted,
        # beside the others' first choices.
        lines = ["MAINE", "FOR UNITED STATES REPRESENTATIVE", "2.",
                 "Bruce Poliquin, Republican" + L, "Jared F. Golden, Democrat" + L,
                 "Tiffany Bond, Independent" + L, "Write-in" + L,
                 "1", "146,142", "1", "165,136", "21,655", "393",
                 "Recapitulation of Votes Cast in Maine", "1",
                 "This vote count is from round 2 of Maine's ranked-choice general election, "
                 "which was held because neither candidate received a majority", "NEW YORK"]
        maine = sh.parse_statistics(lines, 2022)["ME"]
        result = sh.result_of(maine["house"][2], maine["footnotes"], 2022, "ME")
        self.assertEqual(result["kind"], "rcv-final")
        self.assertEqual(result["total"], 146142 + 165136)
        self.assertEqual(result["candidates"][0]["name"], "Jared F. Golden")

    def test_one_runoff_footnote_per_candidate_is_one_runoff(self):
        # Mississippi's 2018 special: each runoff count has its own footnote.
        contest = {"rows": [
            {"name": "Cindy Hyde-Smith", "party": "Republican", "votes": 486769, "lines": [], "note": 3},
            {"name": "Mike Espy", "party": "Democrat", "votes": 420819, "lines": [], "note": 4},
            {"name": "Chris McDaniel", "party": "Republican", "votes": 146013, "lines": [],
             "note": None}], "unnamed": 0, "noVote": 0, "rcvRound": False}
        notes = {3: "This vote count is from the runoff election held on November 27, 2018. "
                    "Cindy Hyde-Smith received 389,995 votes in the general election",
                 4: "This vote count is from the runoff election held on November 27, 2018. "
                    "Mike Espy received 386,742 votes in the general election"}
        result = sh.result_of(contest, notes, 2018, "MS")
        self.assertEqual((result["kind"], result["date"]), ("runoff", "2018-11-27"))
        notes[4] = notes[4].replace("November 27", "December 4")
        with self.assertRaises(sh.ClerkFormatError):
            sh.result_of(contest, notes, 2018, "MS")

    def test_a_district_listed_with_no_count_is_recorded_as_such(self):
        # North Carolina's 9th, 2018: "See explanation below".
        lines = ["NORTH CAROLINA", "FOR UNITED STATES REPRESENTATIVE",
                 "8.", "Frank McNeill, Democrat" + L, "Richard Hudson, Republican" + L,
                 "114,119", "141,402", "9.", "See explanation below",
                 "10.", "David Wilson Brown, Democrat" + L, "Patrick T. McHenry, Republican" + L,
                 "128,385", "164,969", "Recapitulation of Votes Cast in North Carolina"]
        nc = sh.parse_statistics(lines, 2018)["NC"]
        self.assertEqual(sorted(nc["house"]), [8, 10])
        self.assertEqual(nc["houseEmpty"], [9])

    def test_a_senate_terms_class_is_read_from_when_it_ends(self):
        self.assertEqual(sh.senate_class_of("2025-01-03"), 1)
        self.assertEqual(sh.senate_class_of("2031-01-03"), 1)
        self.assertEqual(sh.senate_class_of("2021-01-03"), 2)
        self.assertEqual(sh.senate_class_of("2023-01-03"), 3)


def _cell_result(winner, runner, margin, year, **extra):
    return dict(_result((winner, "Republican", 600), (runner, "Democrat", 400), year=year),
                date=sh.ELECTION_DAYS[year], margin=margin, allCandidates=2,
                checked={"by": "wikipedia", "page": f"{year} page"}, **extra)


class TestStrip(unittest.TestCase):
    """A seat's elections since 2018, grouped by the lines they were fought on."""

    def _cache(self):
        seats = {str(y): {"VA": list(range(1, 12)), "NC": list(range(1, 14 if y < 2022 else 15)),
                          "MT": [0] if y < 2022 else [1, 2], "WY": [0], "AL": list(range(1, 8))}
                 for y in sh.YEARS}
        seats["2018"]["NC"] = [n for n in range(1, 14)]
        earlier = {str(y): {"VA-1": _cell_result("Rob Wittman", "Other", 10.0 + y - 2018, y),
                            "NC-9": _cell_result("Dan Bishop", "Dan McCready", 2.0, y),
                            "MT-0": _cell_result("Greg Gianforte", "Kathleen Williams", 4.6, y)}
                   for y in (2018, 2020, 2022)}
        del earlier["2018"]["NC-9"]
        del earlier["2022"]["MT-0"]
        earlier["2022"]["MT-1"] = _cell_result("Ryan Zinke", "Monica Tranel", 3.2, 2022)
        return {
            "read": "2026-11-01", "years": list(sh.YEARS), "seats": seats,
            "house": {"VA-1": _cell_result("Rob Wittman", "Leslie Mehta", 13.0, 2024),
                      "NC-9": _cell_result("Richard Hudson", "Nigel Bristow", 13.4, 2024),
                      "MT-1": _cell_result("Ryan Zinke", "Monica Tranel", 9.6, 2024)},
            "houseEarlier": earlier,
            "noResult": {"2018": ["NC-9"]},
            "senate": {"MN-2018-unexpired": dict(_cell_result("Tina Smith", "Karin Housley",
                                                              10.6, 2018),
                                                 term="unexpired", termEnds="2021-01-03"),
                       "MN-2020-full": dict(_cell_result("Tina Smith", "Jason Lewis", 5.2, 2020),
                                            term="full", termEnds="2027-01-03"),
                       "MN-2018-full": dict(_cell_result("Amy Klobuchar", "Jim Newberger",
                                                         24.1, 2018),
                                            term="full", termEnds="2025-01-03")},
            "withheld": [{"seat": "VA-1", "year": 2020, "why": "disagree",
                          "result": earlier["2020"].pop("VA-1")}],
            "terms": {"house": {
                "VA-1": [{"id": "W000804", "name": "Robert J. Wittman", "party": "Republican",
                          "start": "2019-01-03", "end": "2027-01-03"}],
                "NC-9": [{"id": "B001311", "name": "Dan Bishop", "party": "Republican",
                          "start": "2019-09-17", "end": "2023-01-03"}]},
                "senate": {"MN-2": [{"id": "S001203", "name": "Tina Smith", "party": "Democrat",
                                     "start": "2018-01-03", "end": "2027-01-03",
                                     "how": "appointment"}]}},
        }

    def _strip(self, race):
        sh.apply([race], self._cache())
        return race["seatHistory"]

    def test_a_district_on_one_map_since_2022_breaks_at_the_census(self):
        strip = self._strip({"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1})
        self.assertEqual(strip["eras"], [{"from": 2018, "to": 2020, "same": False},
                                         {"from": 2022, "to": 2024, "same": True}])
        self.assertEqual(strip["breaks"], [{"kind": "census", "year": 2022}])
        cells = {c["year"]: c for c in strip["cells"]}
        self.assertEqual(cells[2018]["era"], 0)
        self.assertEqual(cells[2024]["era"], 1)
        # The withheld year says why; the others carry their checked result.
        self.assertEqual(cells[2020]["withheld"], "disagree")
        self.assertNotIn("result", cells[2020])
        self.assertEqual(cells[2022]["result"]["checkedBy"], "2022 page")
        self.assertNotIn("votes", cells[2022]["result"]["candidates"][0])
        # The winner who served the term is not named twice.
        self.assertTrue(cells[2024]["holders"][0]["winner"])

    def test_every_mid_decade_map_breaks_the_strip(self):
        # North Carolina: S.L. 2019-249 for 2020, the census map for 2022,
        # S.L. 2023-145 for 2024, and S.L. 2025-95 for 2026.
        strip = self._strip({"id": "H-NC-9-2026", "chamber": "House", "state": "NC", "district": 9})
        self.assertEqual([b["year"] for b in strip["breaks"]], [2020, 2022, 2024, 2026])
        self.assertEqual([b["kind"] for b in strip["breaks"]],
                         ["enacted", "census", "enacted", "redrawn"])
        self.assertIn("2019-249", strip["breaks"][0]["drawnBy"])
        self.assertTrue(strip["breaks"][0]["url"].startswith("https://www.ncleg.gov/"))
        # Four maps in four years, none of them the 2026 map.
        self.assertEqual(len(strip["eras"]), 4)
        self.assertFalse(any(e["same"] for e in strip["eras"]))
        cells = {c["year"]: c for c in strip["cells"]}
        self.assertEqual(cells[2018]["none"], "no-result")
        # A member seated by a special election is named with the day.
        self.assertEqual(cells[2020]["holders"][0].get("from"), None)
        self.assertNotIn("winner", cells[2018].get("holders", [{}])[0] if cells[2018].get(
            "holders") else {})

    def test_a_state_elected_at_large_has_no_lines_to_change(self):
        strip = self._strip({"id": "H-WY-0-2026", "chamber": "House", "state": "WY", "district": 0})
        self.assertEqual(strip["breaks"], [])
        self.assertEqual(len(strip["eras"]), 1)
        self.assertTrue(strip["eras"][0]["same"])

    def test_a_district_that_did_not_exist_says_so_and_at_large_is_the_whole_state(self):
        # Montana elected one member at large until 2022.
        strip = self._strip({"id": "H-MT-1-2026", "chamber": "House", "state": "MT", "district": 1})
        cells = {c["year"]: c for c in strip["cells"]}
        self.assertTrue(cells[2018]["atLarge"])
        self.assertEqual(cells[2018]["district"], 0)
        self.assertEqual(cells[2018]["result"]["candidates"][0]["name"], "Greg Gianforte")
        self.assertEqual(cells[2022]["district"], 1)
        strip = self._strip({"id": "H-VA-11-2026", "chamber": "House", "state": "VA",
                             "district": 12})
        self.assertEqual({c["none"] for c in strip["cells"]}, {"no-district"})

    def test_a_senate_seats_strip_is_its_classs_elections_specials_included(self):
        strip = self._strip({"id": "S-MN-2026", "chamber": "Senate", "state": "MN",
                             "senateClass": 2})
        self.assertEqual([(c["year"], c["result"]["term"]) for c in strip["cells"]],
                         [(2018, "unexpired"), (2020, "full")])
        self.assertEqual(strip["breaks"], [])
        # Appointed before the special she won: named with how she came.
        holder = strip["cells"][0]["holders"][0]
        self.assertEqual((holder["name"], holder["how"]), ("Tina Smith", "appointment"))

    def test_the_house_last_election_is_still_2024s_whatever_the_strip_holds(self):
        race = {"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}
        sh.apply([race], self._cache())
        self.assertEqual(race["lastElection"]["year"], 2024)
        self.assertNotIn("withheld", race["lastElection"])

    def test_a_cache_without_the_strip_draws_none(self):
        race = {"id": "H-VA-1-2026", "chamber": "House", "state": "VA", "district": 1}
        cache = self._cache()
        del cache["seats"]
        sh.apply([race], cache)
        self.assertNotIn("seatHistory", race)

    def test_the_terms_are_read_by_seat_and_joined_per_person(self):
        current = [{"id": {"bioguide": "S001203"}, "name": {"official_full": "Tina Smith"},
                    "terms": [{"type": "sen", "state": "MN", "class": 2, "party": "Democrat",
                               "start": "2018-01-03", "end": "2018-11-28", "how": "appointment"},
                              {"type": "sen", "state": "MN", "class": 2, "party": "Democrat",
                               "start": "2018-11-28", "end": "2021-01-03"},
                              {"type": "sen", "state": "MN", "class": 2, "party": "Democrat",
                               "start": "2021-01-03", "end": "2027-01-03"}]},
                   {"id": {"bioguide": "X000001"}, "name": {"first": "Old", "last": "Member"},
                    "terms": [{"type": "rep", "state": "VA", "district": 1, "party": "Whig",
                               "start": "2015-01-03", "end": "2017-01-03"}]}]
        pages = {sh.LEGISLATORS_URLS[0]: json.dumps(current).encode(),
                 sh.LEGISLATORS_URLS[1]: b"[]"}
        terms = sh.read_terms(fetch=pages.__getitem__)
        self.assertEqual(terms["house"], {})
        # Her appointment and the terms she then won are two; the two she
        # won, one after the other, are one.
        self.assertEqual(terms["senate"]["MN-2"],
                         [{"id": "S001203", "name": "Tina Smith", "party": "Democrat",
                           "start": "2018-01-03", "end": "2018-11-28", "how": "appointment"},
                          {"id": "S001203", "name": "Tina Smith", "party": "Democrat",
                           "start": "2018-11-28", "end": "2027-01-03"}])

    def test_the_lines_table_is_the_census_bureaus_list(self):
        # Rule 50: the Census Bureau's pages are the lead, each state's
        # record the entry. 117th: North Carolina alone; 119th: five states.
        from kyc.districts import REDRAWN_BEFORE
        by_year = {}
        for state, changes in REDRAWN_BEFORE.items():
            for year, record in changes.items():
                by_year.setdefault(year, set()).add(state)
                self.assertTrue(record["url"].startswith("https://"), state)
                self.assertTrue(record["quote"] and record["drawnBy"] and record["title"], state)
        self.assertEqual(by_year, {2020: {"NC"}, 2024: {"AL", "GA", "LA", "NY", "NC"}})

    def test_the_committed_cache_gives_every_race_a_strip(self):
        cache = sh.load_cache(ROOT)
        if cache is None or "seats" not in cache:
            self.skipTest("no seat history strip in the cache")
        with open(os.path.join(ROOT, "candidate_profiles_site", "data", "record_2026.json"),
                  encoding="utf-8") as handle:
            record = json.load(handle)
        races = [dict(r, id=k) for k, r in record["races"].items()]
        sh.apply(races, cache)
        from kyc.districts import REDRAWN
        for race in races:
            strip = race.get("seatHistory")
            self.assertTrue(strip and strip["cells"], race["id"])
            for cell in strip["cells"]:
                era = strip["eras"][cell["era"]]
                self.assertTrue(era["from"] <= cell["year"] <= era["to"], race["id"])
                # A shown result was checked against a second compilation.
                if "result" in cell:
                    self.assertTrue(cell["result"].get("checkedBy"), (race["id"], cell["year"]))
            if race["chamber"] == "House":
                self.assertEqual(len(strip["cells"]), len(sh.YEARS), race["id"])
                # Nothing on a redrawn state's 2024 lines is this race's.
                if race["state"] in REDRAWN:
                    self.assertFalse(any(e["same"] for e in strip["eras"]), race["id"])


class TestTheStripsClassIsItsOwn(unittest.TestCase):
    """The strip was first drawn as <section class="seat-strip">, the class
    of the legislature pages' seat squares (KYC.seatStrip): its grid of one
    column per seat laid the heading, each era and each change of lines side
    by side, a word to a line, at 390px. Every class the strip draws is
    styled once, by its own rule."""

    def test_no_other_module_or_rule_uses_the_strips_classes(self):
        assets = os.path.join(ROOT, "candidate_profiles_site", "assets")
        css = _text(os.path.join(assets, "kyc.css"))
        self.assertEqual(len(re.findall(r"^\.seat-history\s*\{", css, re.M)), 1)
        for name in os.listdir(assets):
            if not name.endswith(".js"):
                continue
            text = _text(os.path.join(assets, name))
            if name != "kyc-cards.js":
                self.assertNotRegex(text, r"seat-history|strip-(?:cell|era|break|title)", name)
        self.assertNotRegex(_text(os.path.join(assets, "kyc-cards.js")),
                            r"class=\"seat-strip")


class TestTheFirstFullRead(unittest.TestCase):
    """What the first read of 2018-2022 got wrong (2026-11-01), each a
    count put beside the wrong name or a check that could not agree."""

    def test_a_party_alone_outside_a_fusion_state_is_nobodys_votes(self):
        # Virginia's 2nd, 2020: the Clerk prints "Independent" for David
        # Foster's 9,170 votes. Read as a fusion line they were Scott
        # Taylor's, and his 165,031 read 174,201.
        lines = ["VIRGINIA", "FOR UNITED STATES REPRESENTATIVE", "1.",
                 "Robert J. Wittman, Republican" + L, "Qasim Rashid, Independent" + L,
                 "260,614", "186,923", "2.",
                 "Elaine G. Luria, Democrat" + L, "Scott W. Taylor, Republican" + L,
                 "Independent" + L, "Write-in" + L, "185,733", "165,031", "9,170", "343",
                 "Recapitulation of Votes Cast in Virginia"]
        va = sh.parse_statistics(lines, 2020)["VA"]["house"][2]
        self.assertEqual([(r["name"], r["votes"]) for r in va["rows"]],
                         [("Elaine G. Luria", 185733), ("Scott W. Taylor", 165031)])
        self.assertEqual(va["unnamed"], 9513)

    def test_scattered_and_none_of_these_and_exhausted_are_nobodys(self):
        # New Hampshire's "Scatter" was added to the last candidate's count
        # (Chris Pappas, 2022: +342), Nevada's "None of These Candidates" to
        # a Senate candidate's, Maine's 2022 "Exhausted Ballot" (322,778) to
        # Tiffany Bond's, Puerto Rico's "Unadjudicated" to its last name's.
        lines = ["NEW HAMPSHIRE", "FOR UNITED STATES REPRESENTATIVE", "1.",
                 "Karoline Leavitt, Republican" + L, "Chris Pappas, Democrat" + L,
                 "Scatter" + L, "142,229", "167,391", "342",
                 "Recapitulation of Votes Cast in New Hampshire"]
        nh = sh.parse_statistics(lines, 2022)["NH"]["house"][1]
        self.assertEqual(nh["rows"][1]["votes"], 167391)
        self.assertEqual(nh["unnamed"], 342)
        for label in ("None of These Candidates", "Exhausted Ballot", "Unadjudicated"):
            self.assertTrue(sh.NOT_A_VOTE.match(label), label)

    def test_a_line_naming_no_one_and_no_known_party_is_an_error(self):
        lines = _house("1.", "Barry Moore, Republican" + L, "Tom Holmes, Democrat" + L,
                       "Somebody" + L, "258,619", "70,929", "306")
        with self.assertRaises(sh.ClerkFormatError):
            sh.parse_statistics(lines, 2020)

    def test_a_row_template_with_two_spaces_and_a_footnoted_name_are_read(self):
        # Alabama's 2nd in 2020 and Tennessee's 2022 districts write
        # "{{Election box  winning candidate"; Oregon's 4th in 2018 sets a
        # footnote in the name's field; the Northern Mariana Islands' 2020
        # box ends "{{end}}".
        text = ("{{Election box begin no change|title=General election}}\n"
                "{{Election box  winning candidate with party link no change|party=Republican "
                "Party (United States)|candidate=[[Barry Moore]]|votes=197,996}}\n"
                "{{Election box candidate with party link no change|party=Democratic Party "
                "(United States)|candidate=[[Art Robinson]]<ref>Co-nominated by Constitution "
                "Party.</ref>|votes=105,286}}\n{{end}}")
        boxes = sh.wiki_boxes(text)
        self.assertEqual([(r["name"], r["votes"], r["won"]) for r in boxes[0][1]],
                         [("Barry Moore", 197996, True), ("Art Robinson", 105286, False)])

    def test_a_surname_written_as_two_words_is_the_same(self):
        result = _result(("Harriet Hageman", "Republican", 132206),
                         ("Lynnette GreyBull", "Democrat", 47250))
        rows = [{"name": "Harriet Hageman", "votes": 132206, "won": True},
                {"name": "Lynnette Grey Bull", "votes": 47250}]
        self.assertEqual(sh._check(result, rows)[0], "agree")

    def test_a_house_runoff_is_checked_against_the_runoff(self):
        # Louisiana's 5th, 2020: the runoff's counts against the open
        # primary's table "disagreed".
        result = dict(_result(("Luke J. Letlow", "Republican", 49183),
                              ("Lance Harris", "Republican", 30124)), kind="runoff")
        section = ("{{Election box begin no change|title=Louisiana's 5th congressional district "
                   "general election, 2020}}\n{{Election box winning candidate with party link "
                   "no change|candidate=Luke Letlow|votes=67,118}}\n{{Election box candidate "
                   "with party link no change|candidate=Lance Harris|votes=60,876}}\n"
                   "{{Election box end}}\n{{Election box begin no change|title=Runoff results}}\n"
                   "{{Election box winning candidate with party link no change|candidate=Luke "
                   "Letlow|votes=49,183}}\n{{Election box candidate with party link no change|"
                   "candidate=Lance Harris|votes=30,124}}\n{{Election box end}}")
        self.assertEqual(sh.house_check(result, section)[0], "agree")

    def test_two_names_whose_counts_are_the_final_round_are_the_final_round(self):
        # Maine's 2nd, 2018: the Clerk prints Golden and Poliquin with the
        # final round's counts and no footnote; as first choices Golden
        # "led", which he did not.
        result = dict(_result(("Jared F. Golden", "Democrat", 142440),
                              ("Bruce Poliquin", "Republican", 138931), year=2018),
                      allCandidates=2, rankedChoice="first-choices")
        infobox = ("{{Infobox election\n| 1blank = First round\n| 2blank = Maximum round\n"
                   "| nominee1 = '''[[Jared Golden]]'''\n| 1data1 = 132,013\n"
                   "| 2data1 = '''142,440<br />50.62%'''\n| nominee2 = [[Bruce Poliquin]]\n"
                   "| 1data2 = 134,184\n| 2data2 = 138,931<br />49.38%\n}}")
        self.assertEqual(sh.house_check(result, infobox)[0], "agree")
        self.assertEqual(result["kind"], "rcv-final")
        self.assertNotIn("rankedChoice", result)
        self.assertEqual(result["roundFrom"], "second-compilation")
        # The first round's counts are first choices, and stay a lead.
        first = dict(_result(("Jared F. Golden", "Democrat", 132013),
                             ("Bruce Poliquin", "Republican", 134184), year=2018),
                     allCandidates=2, rankedChoice="first-choices")
        sh.house_check(first, infobox)
        self.assertEqual(first.get("rankedChoice"), "first-choices")

    def test_a_page_with_no_results_is_not_the_states_page(self):
        # "2022 ... elections in Delaware" leads to the national article.
        pages = {"2022 United States House of Representatives elections in Delaware":
                 "Elections were held in every state. ''See'' each state's page.",
                 "2022 United States House of Representatives election in Delaware":
                 "{{Infobox election\n| nominee1 = Lisa Blunt Rochester\n"
                 "| popular_vote1 = 178,416\n}}"}
        sections, page = sh.house_page_sections("DE", read=pages.get, year=2022)
        self.assertEqual(page, "2022 United States House of Representatives election in Delaware")


def _text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _term(name, start, end, how=None, ident=None, party="Republican"):
    term = {"id": ident or name, "name": name, "party": party, "start": start, "end": end}
    if how:
        term["how"] = how
    return term


class TestTheStripsReview(unittest.TestCase):
    """What the review of PR #187 found in who served, and in the words."""

    def _senate(self, terms, results, read="2026-11-01"):
        seats = {str(y): {} for y in sh.YEARS}
        cache = {"read": read, "years": list(sh.YEARS), "seats": seats, "house": {},
                 "houseEarlier": {}, "noResult": {}, "withheld": [],
                 "senate": results, "terms": {"house": {}, "senate": terms}}
        return cache

    def test_an_appointees_end_on_the_specials_day_is_not_a_day_they_left(self):
        # congress-legislators "ends" Ashley Moody's appointment on November
        # 3, 2026, the special's day, which is ahead of the read and, once
        # past, still not when she leaves: she serves until the winner is
        # seated (and is a candidate herself).
        terms = {"FL-3": [_term("Marco Rubio", "2023-01-03", "2025-01-20", ident="R1"),
                          _term("Ashley Moody", "2025-01-21", "2026-11-03", "appointment", "M1")]}
        results = {"FL-2022-full": dict(_cell_result("Marco Rubio", "Val Demings", 16.4, 2022),
                                        term="full", termEnds="2029-01-03")}
        for read in ("2026-11-01", "2026-11-20"):
            cell = sh.seat_strip({"chamber": "Senate", "state": "FL", "senateClass": 3},
                                 self._senate(terms, results, read))["cells"][0]
            moody = cell["holders"][1]
            self.assertNotIn("until", moody, read)
            self.assertTrue(moody["untilSeated"], read)
            self.assertEqual(cell["holders"][0]["until"], "2025-01-20")
        # A real end that is not an election day (Laphonza Butler's,
        # December 8, 2024) is a day the appointee left.
        terms = {"CA-1": [_term("Laphonza R. Butler", "2023-10-03", "2024-12-08", "appointment")]}
        self.assertEqual(sh._holders(terms["CA-1"], "2019-01-03", "2025-06-01"),
                         [{"id": "Laphonza R. Butler", "name": "Laphonza R. Butler",
                           "party": "Republican", "from": "2023-10-03", "until": "2024-12-08",
                           "how": "appointment"}])

    def test_one_persons_terms_one_after_the_other_are_one_line(self):
        # Pete Ricketts, appointed January 23, 2023, elected November 5, 2024.
        terms = [_term("Ben Sasse", "2021-01-03", "2023-01-08", ident="S1"),
                 _term("Pete Ricketts", "2023-01-23", "2024-11-05", "appointment", "R1"),
                 _term("Pete Ricketts", "2024-11-05", "2027-01-03", ident="R1")]
        holders = sh._holders(terms, "2021-01-03", "2027-01-03")
        self.assertEqual([h["name"] for h in holders], ["Ben Sasse", "Pete Ricketts"])
        self.assertEqual({k: v for k, v in holders[1].items() if k not in ("id", "party")},
                         {"name": "Pete Ricketts", "from": "2023-01-23", "how": "appointment",
                          "elected": "2024-11-05"})

    def test_a_specials_term_is_served_from_the_day_its_winner_took_the_seat(self):
        # Oklahoma's 2022 special: James Inhofe served until January 3, 2023
        # and is not among those who served the term it chose; Markwayne
        # Mullin, seated that day, is its winner.
        terms = {"OK-2": [_term("James M. Inhofe", "2021-01-03", "2023-01-03", ident="I1"),
                          _term("Markwayne Mullin", "2023-01-03", "2027-01-03", ident="M1")]}
        results = {"OK-2022-unexpired": dict(
            _cell_result("Markwayne Mullin", "Kendra Horn", 26.0, 2022),
            term="unexpired", termEnds="2027-01-03")}
        cell = sh.seat_strip({"chamber": "Senate", "state": "OK", "senateClass": 2},
                             self._senate(terms, results))["cells"][0]
        self.assertEqual(cell["holders"], [{"id": "M1", "name": "Markwayne Mullin",
                                            "party": "Republican", "winner": True}])

    def test_a_majority_of_first_choices_is_a_win_and_less_is_a_lead(self):
        pingree = dict(_result(("Chellie Pingree", "Democrat", 588), ("Other", "Republican", 325),
                               ("Third", "Independent", 87), year=2018),
                       rankedChoice="first-choices", margin=26.3)
        self.assertTrue(sh._strip_result(pingree, "House")["firstChoiceMajority"])
        lead = dict(_result(("Mary Peltola", "Democrat", 488), ("Sarah Palin", "Republican", 257),
                            ("Nick Begich", "Republican", 255), year=2022),
                    rankedChoice="first-choices", margin=23.1)
        self.assertNotIn("firstChoiceMajority", sh._strip_result(lead, "House"))
        cell = {"result": sh._strip_result(lead, "House"),
                "holders": [{"name": "Mary Peltola", "party": "Democrat"}]}
        sh._mark_winner(cell)
        self.assertNotIn("winner", cell["holders"][0])
        cell["result"] = sh._strip_result(pingree, "House")
        cell["holders"] = [{"name": "Chellie Pingree", "party": "Democrat"}]
        sh._mark_winner(cell)
        self.assertTrue(cell["holders"][0]["winner"])

    def test_an_unopposed_name_with_no_count_is_withheld_as_such(self):
        seats = {str(y): {"OK": [1, 2, 3, 4, 5]} for y in sh.YEARS}
        cache = {"read": "2026-11-01", "years": list(sh.YEARS), "seats": seats, "house": {},
                 "houseEarlier": {}, "noResult": {}, "senate": {}, "terms": {},
                 "withheld": [{"seat": "OK-3", "year": 2024, "why": "unchecked",
                               "result": {"kind": "unopposed", "year": 2024, "candidates": [
                                   {"name": "Frank D. Lucas", "party": "Republican"}]}}]}
        cell = sh.seat_strip({"chamber": "House", "state": "OK", "district": 3}, cache)["cells"][-1]
        self.assertEqual((cell["withheld"], cell.get("withheldUnopposed")), ("unchecked", True))

    def test_alabamas_2024_lines_cite_the_census_list_as_a_list(self):
        seats = {str(y): {"AL": list(range(1, 8))} for y in sh.YEARS}
        change = sh.house_breaks("AL", seats)[2024]
        self.assertTrue(change["lead"])
        self.assertNotIn("map", change["title"].lower())
        self.assertIn("census.gov", change["url"])

    def test_the_clerks_grave_inside_a_word_is_the_okina(self):
        self.assertEqual(sh.okina("Kaiali`i “Kai” Kahele, Democrat"),
                         "Kaialiʻi “Kai” Kahele, Democrat")
        with self.assertRaises(sh.ClerkFormatError):
            sh.okina("`quoted' text")


if __name__ == "__main__":
    unittest.main()
