"""Tests for primary results: who is still in each race.

The FEC's register says who filed; it does not say who lost. These tests pin
the parts of the resolver that would silently mislabel a real person if they
regressed: the winner marker, the runoff/general precedence, name matching,
and the two gates (calendar, exact-match-only) that keep it conservative.
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import results  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def box(title, *rows):
    """Wikitext for one results table.

    Each row is ``(name, votes, won)`` or ``(name, votes, won, "withdrawn")``.
    """
    out = ["{{Election box begin no change", f"| title = {title}", "}}"]
    for row in rows:
        name, votes, won = row[0], row[1], row[2]
        kind = "winning candidate" if won else "candidate"
        marker = " ''(withdrawn)''" if len(row) > 3 else ""
        out += [
            f"{{{{Election box {kind} with party link no change",
            "| party = Democratic Party (United States)",
            f"| candidate = {name}{marker}",
            f"| votes = {votes:,}",
            "| percentage = 50.0",
            "}}",
        ]
    out += ["{{Election box total no change", "| votes = 1", "}}", "{{Election box end}}"]
    return "\n".join(out)


class TestParsing(unittest.TestCase):
    def test_winner_comes_from_the_template_name_not_the_count(self):
        # Two winners with fewer votes than a loser would be nonsense; the
        # point is that we never look at the numbers to decide.
        text = box("Democratic primary results",
                   ("Alice Low", 10, True), ("Bob High", 999, False))
        (_, rows), = results.parse_boxes(text)
        self.assertEqual([(r["name"], r["won"]) for r in rows],
                         [("Alice Low", True), ("Bob High", False)])

    def test_one_line_rows_are_split_on_parameter_pipes_only(self):
        # Michigan's Senate page writes every row on one line. The old
        # line-based field regex read the whole remainder as the name.
        text = "\n".join([
            "{{Election box begin no change | title=Democratic primary results}}",
            "{{Election box winning candidate with party link|party=Democratic Party "
            "|candidate=[[Abdul El-Sayed]]|votes=744,952|percentage=48.45}}",
            "{{Election box candidate with party link|party=Democratic Party "
            "|candidate=[[Haley Stevens|Stevens]]|votes=731,160|percentage=47.55}}",
            "{{Election box end}}",
        ])
        rows = results.parse_boxes(text)[0][1]
        self.assertEqual([r["name"] for r in rows], ["Abdul El-Sayed", "Stevens"])
        self.assertEqual([r["won"] for r in rows], [True, False])
        self.assertEqual(rows[0]["votes"], 744952)

    def test_piped_wiki_links_keep_the_display_name(self):
        # "[[Al Green (politician)|Al Green]]" used to truncate at the pipe.
        text = box("Democratic primary results",
                   ("[[Al Green (politician)|Al Green]] (incumbent)", 5, True))
        (_, rows), = results.parse_boxes(text)
        self.assertEqual(rows[0]["name"], "Al Green")

    def test_plain_links_and_annotations_are_stripped(self):
        self.assertEqual(results.clean_name("[[Christian Menefee]] (incumbent)"),
                         "Christian Menefee")
        self.assertEqual(results.clean_name("Gretchen Brown"), "Gretchen Brown")

    def test_withdrawn_marker_is_read(self):
        text = box("Democratic primary results",
                   ("Amanda Edwards", 7, False, "withdrawn"))
        (_, rows), = results.parse_boxes(text)
        self.assertTrue(rows[0]["withdrawn"])

    def test_a_ref_tag_in_the_title_is_ignored(self):
        self.assertEqual(
            results._clean_title('Republican primary results<ref name="x">{{cite web'),
            "Republican primary results",
        )

    def test_house_sections_split_by_district(self):
        text = "intro\n== District 1 ==\nA\n== District 12 ==\nB\n== See also ==\nC"
        sections = results.house_sections(text)
        self.assertEqual(set(sections), {1, 12})
        self.assertIn("A", sections[1])
        self.assertIn("B", sections[12])

    def test_an_at_large_page_is_one_section(self):
        self.assertEqual(list(results.house_sections("no headings here")), [0])


class TestResolving(unittest.TestCase):
    def test_primary_winner_is_the_nominee(self):
        boxes = results.parse_boxes(
            box("Republican primary results", ("Ann Win", 9, True), ("Bo Lose", 4, False))
        )
        self.assertEqual(results.resolve_race(boxes),
                         {"Ann Win": "nominee", "Bo Lose": "eliminated"})

    def test_a_table_with_no_winner_decides_nothing(self):
        text = box("Democratic primary results", ("Ann Able", 10, False), ("Bo Baker", 5, False))
        self.assertEqual(results.resolve_race(results.parse_boxes(text)), {})
        # A withdrawal is still read from it.
        text = box("Democratic primary results",
                   ("Ann Able", 10, False), ("Bo Baker", 5, False, "withdrawn"))
        self.assertEqual(results.resolve_race(results.parse_boxes(text)),
                         {"Bo Baker": "withdrawn"})

    def test_coverage_names_the_contests_the_page_has_decided(self):
        text = (box("Republican primary results", ("Ann Able", 10, True)) + "\n" +
                box("Democratic primary results", ("Bo Baker", 5, False)))
        self.assertEqual(results.coverage(results.parse_boxes(text)),
                         {"general": False, "parties": ["republican"]})
        text += "\n" + box("General election", ("Ann Able", 1, False), ("Cy Cole", 1, False))
        self.assertTrue(results.coverage(results.parse_boxes(text))["general"])
        text = box("Nonpartisan primary results", ("Ann Able", 10, True))
        self.assertEqual(results.coverage(results.parse_boxes(text))["parties"], ["all"])

    def test_party_keys_agree_across_sources(self):
        self.assertEqual(results.party_key("DEM"), "democratic")
        self.assertEqual(results.party_key("Democrat"), "democratic")
        self.assertEqual(results.party_key("Minnesota Democratic–Farmer–Labor"), "democratic")
        self.assertEqual(results.party_key("REP"), results.party_key("Republican"))
        self.assertEqual(results.party_key("Top-two"), "all")

    def test_runoff_supersedes_the_primary(self):
        # Both runoff qualifiers are marked as winning the first round; only
        # the runoff's winner is the nominee.
        text = "\n".join([
            box("Democratic primary results",
                ("Christian Menefee", 43, True), ("Al Green", 42, True), ("Gretchen Brown", 1, False)),
            box("Democratic primary runoff results",
                ("Christian Menefee", 34, True), ("Al Green", 15, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out["Christian Menefee"], "nominee")
        self.assertEqual(out["Al Green"], "eliminated")
        self.assertEqual(out["Gretchen Brown"], "eliminated")

    def test_the_general_election_table_is_the_authority(self):
        # No runoff table on the page, but the general ballot names the
        # nominee - so the other first-round "winner" is out.
        text = "\n".join([
            box("Republican primary results",
                ("Jace Yarbrough", 33, True), ("Ryan Binkley", 15, True), ("Paul Bondar", 9, False)),
            box("2026 Texas's 32nd congressional district election",
                ("Jace Yarbrough", 0, False), ("Dan Barrios", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text), has_runoff=True)
        self.assertEqual(out["Jace Yarbrough"], "nominee")
        self.assertEqual(out["Ryan Binkley"], "eliminated")
        self.assertEqual(out["Paul Bondar"], "eliminated")
        # On the general ballot without a primary table of their own.
        self.assertEqual(out["Dan Barrios"], "nominee")

    def test_two_first_round_winners_in_a_runoff_state_are_only_advanced(self):
        # The runoff has not been reported; nobody is the nominee yet.
        text = box("Republican primary results", ("A One", 9, True), ("B Two", 8, True))
        out = results.resolve_race(results.parse_boxes(text), has_runoff=True)
        self.assertEqual(out, {"A One": "advanced", "B Two": "advanced"})

    def test_top_two_states_send_both_winners_forward(self):
        # California has no runoff; two marked winners are two nominees.
        text = box("Nonpartisan primary results", ("A One", 9, True), ("B Two", 8, True))
        out = results.resolve_race(results.parse_boxes(text), has_runoff=False)
        self.assertEqual(out, {"A One": "nominee", "B Two": "nominee"})

    def test_withdrawn_beats_everything(self):
        text = box("Democratic primary results",
                   ("Amanda Edwards", 7, True, "withdrawn"), ("Some One", 5, False))
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out["Amanda Edwards"], "withdrawn")

    def test_one_person_spelled_two_ways_is_one_person(self):
        # "Norma J. Torres" in the primary table, "Norma Torres" on the ballot.
        text = "\n".join([
            box("Democratic primary results", ("Norma J. Torres", 9, True)),
            box("2026 California's 35th congressional district election",
                ("Norma Torres", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out, {"Norma J. Torres": "nominee"})


class TestMatching(unittest.TestCase):
    def rows(self, *names):
        return [{"candidate_id": f"H{i}", "name": n} for i, n in enumerate(names)]

    def test_exact_surname_and_given_name_prefix(self):
        m, amb = results.match_names(["Dan Miressi"], self.rows("MIRESSI, DANIEL"))
        self.assertEqual(m, {"Dan Miressi": ["H0"]})
        self.assertEqual(amb, [])

    def test_a_different_given_name_does_not_match(self):
        # Alaska's Senate race: Senator Dan Sullivan and a different
        # Daniel J Sullivan. "Dan" is a prefix of "Daniel", so a Wikipedia
        # row naming the senator must not land on the challenger.
        m, _ = results.match_names(["Trever Nehls"], self.rows("NEHLS, TROY"))
        self.assertEqual(m, {})

    def test_two_filings_that_fit_are_ambiguous_not_guessed(self):
        m, amb = results.match_names(
            ["Dan Sullivan"], self.rows("SULLIVAN, DAN", "SULLIVAN, DANIEL J"))
        self.assertEqual(m, {})
        self.assertEqual(amb, ["Dan Sullivan"])

    def test_surname_anywhere_in_the_filed_name_with_exact_given_name(self):
        # ARENHOLZ, ASHLEY HINSON -> "Ashley Hinson"
        m, _ = results.match_names(["Ashley Hinson"], self.rows("ARENHOLZ, ASHLEY HINSON"))
        self.assertEqual(m, {"Ashley Hinson": ["H0"]})
        # ...but only with the exact given name, so the looser rule buys
        # no false matches.
        m, _ = results.match_names(["Ash Hinson"], self.rows("ARENHOLZ, ASHLEY HINSON"))
        self.assertEqual(m, {})

    def test_suffixes_do_not_hide_the_surname(self):
        self.assertEqual(results._tokens("Warren Kenneth Paxton Jr."),
                         ["warren", "kenneth", "paxton"])

    def test_a_roster_alias_bridges_a_name_no_rule_can(self):
        rows = self.rows("HAYES, KATHLEEN")
        m, _ = results.match_names(["Kitty Hayes"], rows)
        self.assertEqual(m, {})
        m, _ = results.match_names(["Kitty Hayes"], rows, aliases=[("Kitty Hayes", "H0")])
        self.assertEqual(m, {"Kitty Hayes": ["H0"]})

    def test_a_nickname_fits_any_given_name(self):
        # "Ken" is Paxton's *middle* name shortened; "French" is Hill's.
        m, _ = results.match_names(["Ken Paxton"], self.rows("PAXTON, WARREN KENNETH JR."))
        self.assertEqual(m, {"Ken Paxton": ["H0"]})
        m, _ = results.match_names(["French Hill"], self.rows("HILL, JAMES FRENCH"))
        self.assertEqual(m, {"French Hill": ["H0"]})
        m, _ = results.match_names(["Nick Begich III"], self.rows("BEGICH, NICHOLAS III"))
        self.assertEqual(m, {"Nick Begich III": ["H0"]})

    def test_honorifics_and_quoted_nicknames_are_words_not_obstacles(self):
        m, _ = results.match_names(["Hank Johnson"], self.rows("JOHNSON, HENRY C. 'HANK'"))
        self.assertEqual(m, {"Hank Johnson": ["H0"]})
        m, _ = results.match_names(["Chuck Uribe"], self.rows("URIBE, CHARLES MR. JR."))
        self.assertEqual(m, {"Chuck Uribe": ["H0"]})
        m, _ = results.match_names(['Joseph "Joe" Shea'], self.rows("SHEA, JOE"))
        self.assertEqual(m, {'Joseph "Joe" Shea': ["H0"]})

    def test_an_initial_is_not_a_prefix(self):
        # "C MARCEL DAVIS" is not Chris Davis on the strength of one letter.
        m, _ = results.match_names(["Chris Davis"], self.rows("DAVIS, C MARCEL"))
        self.assertEqual(m, {})

    def test_one_person_registered_twice_takes_the_status_twice(self):
        m, amb = results.match_names(["Aaron Baker"], self.rows("BAKER, AARON", "BAKER, AARON"))
        self.assertEqual(m, {"Aaron Baker": ["H0", "H1"]})
        self.assertEqual(amb, [])
        # ...but a shorter name inside a longer one is still two people.
        m, amb = results.match_names(["Mitch Clemmons"],
                                     self.rows("CLEMMONS, MITCHELL", "CLEMMONS, MITCHELL LEE"))
        self.assertEqual(m, {})
        self.assertEqual(amb, ["Mitch Clemmons"])

    def test_single_token_names_are_skipped(self):
        m, _ = results.match_names(["Write-in"], self.rows("SMITH, JANE"))
        self.assertEqual(m, {})


class TestCalendarGate(unittest.TestCase):
    def test_a_future_primary_is_not_settled(self):
        dates = {("LA", "H"): {"primary": "2026-11-03", "runoff": None}}
        self.assertFalse(results.primary_settled(dates, "LA", "H", datetime.date(2026, 9, 13)))

    def test_a_past_primary_with_a_future_runoff_is_not_settled(self):
        dates = {("TX", "H"): {"primary": "2026-03-03", "runoff": "2026-12-01"}}
        self.assertFalse(results.primary_settled(dates, "TX", "H", datetime.date(2026, 9, 13)))

    def test_past_primary_and_runoff_is_settled(self):
        dates = {("TX", "H"): {"primary": "2026-03-03", "runoff": "2026-05-26"}}
        self.assertTrue(results.primary_settled(dates, "TX", "H", datetime.date(2026, 9, 13)))

    def test_unknown_state_is_never_settled(self):
        self.assertFalse(results.primary_settled({}, "ZZ", "H", datetime.date(2026, 9, 13)))


class TestApplying(unittest.TestCase):
    def cache(self):
        return {"asOf": "2026-09-13", "races": {
            "H-TX-18-2026": {"status": {"H6TX18232": "nominee", "H6TX18471": "eliminated"},
                             "unmatched": {"Ronald Whitfield": "nominee"}, "ambiguous": []},
        }, "dates": {"TX-H": {"primary": "2026-03-03", "runoff": "2026-05-26"}}}

    def profile(self, cid, **kw):
        base = {"id": "FEC_" + cid, "fecCandidateId": cid, "isCandidate": True,
                "state": "TX", "chamber": "House (Candidate)", "districtNum": 18}
        base.update(kw)
        return base

    def test_status_is_attached_by_candidate_id(self):
        people = [self.profile("H6TX18232"), self.profile("H6TX18471")]
        self.assertEqual(results.apply_cache(people, self.cache()), 2)
        self.assertEqual(people[0]["raceStatus"], "nominee")
        self.assertEqual(people[1]["raceStatus"], "eliminated")

    def test_a_filer_absent_from_a_settled_race_is_unlisted(self):
        # Filed with the FEC, never on the primary ballot. Not "eliminated",
        # and not an inference about why - just what the results show.
        people = [self.profile("H6TX18999")]
        results.apply_cache(people, self.cache())
        self.assertEqual(people[0]["raceStatus"], "unlisted")

    def test_unlisted_needs_the_page_to_have_decided_that_party(self):
        cache = self.cache()
        cache["races"]["H-TX-18-2026"]["decided"] = {"general": False,
                                                     "parties": ["republican"]}
        dem = self.profile("H6TX18999", party="Democrat")
        rep = self.profile("H6TX18998", party="Republican")
        results.apply_cache([dem, rep], cache)
        self.assertNotIn("raceStatus", dem)
        self.assertEqual(rep["raceStatus"], "unlisted")
        cache["races"]["H-TX-18-2026"]["decided"] = {"general": True, "parties": []}
        results.apply_cache([dem], cache)
        self.assertEqual(dem["raceStatus"], "unlisted")

    def test_a_filer_in_an_unsettled_race_is_left_alone(self):
        people = [self.profile("H6LA01001", state="LA", districtNum=1)]
        results.apply_cache(people, self.cache())
        self.assertNotIn("raceStatus", people[0])

    def test_an_eliminated_incumbent_is_not_seeking_reelection(self):
        member = self.profile("H6TX18471", isCandidate=False, seekingReelection2026=True)
        results.apply_cache([member], self.cache())
        self.assertFalse(member["seekingReelection2026"])

    def test_nothing_is_deleted(self):
        people = [self.profile("H6TX18471")]
        results.apply_cache(people, self.cache())
        self.assertEqual(len(people), 1)

    def test_on_ballot(self):
        self.assertTrue(results.on_ballot({"raceStatus": "nominee"}))
        self.assertTrue(results.on_ballot({}))
        for st in ("eliminated", "withdrawn", "unlisted"):
            self.assertFalse(results.on_ballot({"raceStatus": st}))

    def test_race_summary_counts_and_unfiled_nominees(self):
        summary = results.race_summary(self.cache(), "H-TX-18-2026")
        self.assertEqual(summary["nominees"], 1)
        self.assertEqual(summary["eliminated"], 1)
        self.assertEqual(summary["otherNominees"], ["Ronald Whitfield"])

    def test_dates_round_trip_through_the_cache(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            results.save_cache(self.cache(), tmp)
            self.assertEqual(results.load_dates(tmp),
                             {("TX", "H"): {"primary": "2026-03-03", "runoff": "2026-05-26"}})


class TestAgainstTheRealCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = results.load_cache(ROOT)

    def test_the_cache_is_committed(self):
        self.assertIsNotNone(self.cache, "run: python build_profile_site.py results")

    def test_no_race_was_resolved_before_its_primary(self):
        dates = results.load_dates(ROOT)
        as_of = datetime.date.fromisoformat(self.cache["asOf"])
        for rid in self.cache["races"]:
            parts = rid.split("-")
            state, office = parts[1], "S" if parts[0] == "S" else "H"
            self.assertTrue(results.primary_settled(dates, state, office, as_of), rid)

    def test_every_status_is_a_known_value(self):
        allowed = {results.NOMINEE, results.ELIMINATED, results.WITHDRAWN, results.ADVANCED}
        for race in self.cache["races"].values():
            for status in race["status"].values():
                self.assertIn(status, allowed)

    def test_no_party_has_two_nominees_outside_top_two_states(self):
        from kyc import candidates
        field = candidates.load_cache(ROOT)
        by_id = {r["candidate_id"]: r for r in field["candidates"]}
        top_two = {"CA", "WA", "LA", "AK"}
        for rid, race in self.cache["races"].items():
            if rid.split("-")[1] in top_two:
                continue
            parties = {}
            for cid, status in race["status"].items():
                if status == results.NOMINEE and cid in by_id:
                    # The ballot's party wins over the filing's: Tamie Wilson
                    # filed as a Democrat and is on Ohio's 4th ballot as an
                    # independent beside the Democratic nominee.
                    party = (race.get("party") or {}).get(cid) or                         results.party_key(by_id[cid].get("party"))
                    if party in ("democratic", "republican"):
                        # One person registered twice is one nominee.
                        parties.setdefault(party, set()).add(
                            results._fold(by_id[cid].get("name")))
            for party, names in parties.items():
                self.assertLessEqual(len(names), 1, f"{rid}: {party} nominees {sorted(names)}")


if __name__ == "__main__":
    unittest.main()
