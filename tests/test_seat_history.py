"""Tests for each seat's last election (kyc/seat_history.py): the Clerk of
the House's statistics read line by line, the result as the page shows it,
the check against a second compilation, and the race it is attached to.

A silent off-by-one between a name and a count would put one candidate's
votes beside another's name, so every block that does not pair is an
error. A district redrawn for 2026 never carries the old district's result
(rule 90), and a result the second source contradicts is withheld.
"""

import json
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


if __name__ == "__main__":
    unittest.main()
