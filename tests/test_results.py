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


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "results")


def fixture(name):
    """Real wikitext, as read on 2026-10-01, trimmed to headings, candidate
    lists, results tables and infobox nominee fields."""
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return "\n" + handle.read()


def page_statuses(text, district=None, **kw):
    """Run one race's section through the same steps ``build`` does."""
    section = text if district is None else results.house_sections(text)[district]
    boxes = results.parse_boxes(section)
    nominees = results.infobox_nominees(section)
    if nominees:
        boxes.append((results.INFOBOX_TITLE, nominees))
    boxes.extend(results.candidate_lists(section))
    return results.resolve_race(boxes, **kw)


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
        self.assertEqual(list(results.house_sections("no headings here", at_large=True)), [0])

    def test_a_districted_page_without_district_headings_is_not_at_large(self):
        # California's main page after the 2026-09-20 split: no "District N"
        # headings, only {{main}} links. Reading it as one at-large race
        # silently dropped all 52 races.
        self.assertEqual(results.house_sections(fixture("ca_main.txt")), {})


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

    def test_a_nominee_on_another_line_gets_that_line_and_keeps_the_party(self):
        # NY-15 on 2026-10-02: Ritchie Torres is the Democratic nominee; Jose
        # Vega lost that primary and is on the "Speak The Truth" line. The
        # page showed two "Democrat - On the November ballot" rows.
        section = results.house_sections(fixture("ny_15.txt"))[15]
        boxes = results.parse_boxes(section)
        labels = results.ballot_labels(boxes)
        self.assertEqual(labels["Jose Vega"], "Speak The Truth")
        self.assertNotIn("Ritchie Torres", labels)        # a major party's line
        cache = {"races": {"H-NY-15-2026": {
            "status": {"H4NY15147": "nominee", "H0NY15160": "nominee",
                       "H0NY15194": "eliminated"},
            "party": {"H4NY15147": "speak the truth", "H0NY15160": "democratic",
                      "H0NY15194": "democratic"},
            "label": {"H4NY15147": labels["Jose Vega"]}}}}
        base = {"isCandidate": True, "state": "NY", "chamber": "House (Candidate)",
                "districtNum": 15, "source": "fec-field"}
        vega = dict(base, id="FEC_H4NY15147", fecCandidateId="H4NY15147",
                    name="Jose David Vega", party="Democrat")
        torres = dict(base, id="T000486", fecCandidateId="H0NY15160", isCandidate=False,
                      name="Ritchie Torres", party="Democrat", chamber="House")
        blake = dict(base, id="FEC_H0NY15194", fecCandidateId="H0NY15194",
                     name="Michael Blake", party="Democrat")
        results.apply_cache([vega, torres, blake], cache)
        self.assertEqual(vega["ballotLine"], "Speak The Truth")
        self.assertEqual(vega["party"], "Democrat")            # never overwritten
        self.assertNotIn("ballotLine", torres)
        self.assertNotIn("ballotLine", blake)                  # not a nominee

    def test_ballot_line_rules(self):
        line = results.ballot_line
        # A cache without the page's spelling still gives a readable label.
        self.assertEqual(line("Andre Clement Easton", "Independent",
                              "party for socialism and liberation"),
                         "Party for Socialism and Liberation")
        self.assertEqual(line("Wilneida Negron", "Independence Party", "for all of us"),
                         "For All of Us")
        # No line at all.
        self.assertIsNone(line("Brian McGinnis", "Independent", "none"))
        self.assertIsNone(line("Pat Doe", "Democrat", "write-in"))
        self.assertIsNone(line("Pat Doe", "Democrat", ""))
        # A line named after the candidate is an independent petition, not a
        # party: nothing when they are listed as independent already.
        self.assertIsNone(line("Karen Ortiz", "Independent", "karen ortiz"))
        self.assertEqual(line("Karen Ortiz", "Democrat", "karen ortiz", "Karen Ortiz"),
                         "Independent")
        # Their own party's line is no news.
        self.assertIsNone(line("Ritchie Torres", "Democrat", "democratic"))
        self.assertIsNone(line("Ritchie Torres", "DEM", "democratic"))

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
        # Louisiana is not here: its Senate race used closed primaries, and
        # its House races are an open primary the cache now holds as pending.
        top_two = {"CA", "WA", "AK"}
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


CA_TITLE = "2026 United States House of Representatives elections in California"
CA_PAGES = {
    CA_TITLE: "ca_main.txt",
    f"{CA_TITLE} (districts 1–26)": "ca_1_26.txt",
    f"{CA_TITLE} (districts 27–52)": "ca_27_52.txt",
}


def fake_fetch(pages):
    def fetch(title):
        if title not in pages:
            raise results.PageMissing(title)
        return fixture(pages[title])
    return fetch


def row(cid, name, state, office, district, party):
    return {"candidate_id": cid, "name": name, "state": state, "office": office,
            "district_number": district, "party": party}


class NoGap(unittest.TestCase):
    def setUp(self):
        self._gap, results._GAP = results._GAP, 0

    def tearDown(self):
        results._GAP = self._gap


class TestSplitPages(NoGap):
    """California's House page was split into two sub-articles on 2026-09-20."""

    field = {"candidates": [
        row("H6CA01285", "GALLAGHER, JAMES", "CA", "H", 1, "REP"),
        row("H6CA01269", "MCGUIRE, MIKE", "CA", "H", 1, "DEM"),
        row("H6CA01251", "DENNEY, AUDREY", "CA", "H", 1, "DEM"),
        row("H4CA27111", "WHITESIDES, GEORGE", "CA", "H", 27, "DEM"),
        row("H6CA27330", "NORWOOD, CALEB GABRIEL", "CA", "H", 27, "DEM"),
    ]}
    dates = {("CA", "H"): {"primary": "2026-06-02", "runoff": None}}

    def run_build(self, pages):
        logged = []
        cache = results.build(self.field, self.dates, today=datetime.date(2026, 10, 1),
                              log=logged.append, fetch=fake_fetch(pages))
        return cache, logged

    def test_sub_articles_are_found_from_main_links(self):
        self.assertEqual(results.sub_articles(fixture("ca_main.txt"), CA_TITLE),
                         [f"{CA_TITLE} (districts 1–26)", f"{CA_TITLE} (districts 27–52)"])

    def test_build_reads_districts_from_the_sub_articles(self):
        cache, _ = self.run_build(CA_PAGES)
        self.assertEqual(set(cache["races"]), {"H-CA-01-2026", "H-CA-27-2026"})
        one = cache["races"]["H-CA-01-2026"]
        self.assertEqual(one["page"], f"{CA_TITLE} (districts 1–26)")
        self.assertEqual(one["status"], {"H6CA01285": "nominee", "H6CA01269": "nominee",
                                         "H6CA01251": "eliminated"})
        self.assertEqual(cache["races"]["H-CA-27-2026"]["status"],
                         {"H4CA27111": "nominee", "H6CA27330": "eliminated"})
        self.assertEqual(cache["unparsedPages"], [])

    def test_a_districted_page_with_no_districts_fails_loudly(self):
        # The sub-articles are gone: the main page must not be read as one
        # at-large race, and the failure must be recorded for validate.
        cache, logged = self.run_build({CA_TITLE: "ca_main.txt"})
        self.assertEqual(cache["races"], {})
        self.assertEqual(cache["unparsedPages"], [f"CA-H: {CA_TITLE}"])
        self.assertTrue(any("[ERROR]" in line for line in logged))


class TestTerritoryTitles(NoGap):
    def test_the_definite_article_forms_are_asked_for(self):
        house = "2026 United States House of Representatives election in "
        self.assertIn(house + "the District of Columbia", results.page_titles("DC", "H"))
        self.assertIn(house + "the United States Virgin Islands", results.page_titles("VI", "H"))
        self.assertIn(house + "the Northern Mariana Islands", results.page_titles("MP", "H"))
        # A state's own title is still asked for first.
        self.assertEqual(results.page_titles("TX", "H")[0],
                         "2026 United States House of Representatives elections in Texas")

    def test_dc_is_read_and_norton_is_off_the_ballot(self):
        title = "2026 United States House of Representatives election in the District of Columbia"
        field = {"candidates": [
            row("H0DC00058", "NORTON, ELEANOR HOLMES", "DC", "H", 0, "DEM"),
            row("H6DC00111", "WHITE, ROBERT", "DC", "H", 0, "DEM"),
        ]}
        cache = results.build(field, {("DC", "H"): {"primary": "2026-06-16", "runoff": None}},
                              today=datetime.date(2026, 10, 1), log=lambda *_: None,
                              fetch=fake_fetch({title: "dc.txt"}))
        self.assertEqual(cache["missingPages"], [])
        race = cache["races"]["H-DC-00-2026"]
        self.assertEqual(race["page"], title)
        self.assertEqual(race["status"]["H0DC00058"], "withdrawn")
        self.assertEqual(race["status"]["H6DC00111"], "nominee")
        # Vote-tally lines are not people.
        self.assertNotIn("Overvotes", race["unmatched"])


class TestWithdrawals(unittest.TestCase):
    """Leaving a race is not losing it; losing is not leaving. Each case was
    read wrongly from the live page on 2026-10-01."""

    def test_nc11_primary_winner_who_ended_his_bid_is_withdrawn(self):
        out = page_statuses(fixture("nc_11.txt"), 11)
        self.assertEqual(out["Chuck Edwards"], "withdrawn")      # won with 70.1%
        self.assertEqual(out["Jennifer Balkcom"], "nominee")     # the replacement
        self.assertEqual(out["Adam Smith"], "eliminated")

    def test_maine_winner_withdrew_and_the_governor_lost(self):
        out = page_statuses(fixture("me_senate.txt"))
        self.assertEqual(out["Graham Platner"], "withdrawn")
        # Suspended her campaign but stayed on the ballot and lost: her row
        # says ''(withdrawn)'', she is listed under "Eliminated in primary".
        self.assertEqual(out["Janet Mills"], "eliminated")
        # Lost the primary; the later convention's "Withdrawn" list does not
        # undo that.
        self.assertEqual(out["David Costello"], "eliminated")
        self.assertEqual(out["Troy Jackson"], "nominee")
        self.assertEqual(out["Susan Collins"], "nominee")

    def test_nebraska_withdrawn_winner_and_struck_general_line(self):
        out = page_statuses(fixture("ne_senate.txt"))
        self.assertEqual(out["Cindy Burbank"], "withdrawn")
        self.assertEqual(out["Mike Marvin"], "withdrawn")       # ''(withdrawn)'' in the general box
        self.assertEqual(out["Dan Osborn"], "nominee")
        self.assertEqual(out["William Forbes"], "eliminated")

    def test_withdrew_after_nomination_lists(self):
        self.assertEqual(page_statuses(fixture("id_senate.txt"))["David Roth"], "withdrawn")
        self.assertEqual(page_statuses(fixture("sd_senate.txt"))["Julian Beaudion"], "withdrawn")
        self.assertEqual(page_statuses(fixture("oh_4.txt"), 4)["Tamie Wilson"], "withdrawn")

    def test_a_winner_missing_from_the_general_ballot_withdrew(self):
        text = "\n".join([
            box("Democratic primary results", ("Ann Winner", 9, True), ("Bob Loser", 5, False)),
            box("2026 Somewhere's 1st congressional district election", ("Cal Other", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out, {"Ann Winner": "withdrawn", "Bob Loser": "eliminated",
                               "Cal Other": "nominee"})

    def test_a_primary_loser_on_another_line_in_november_is_a_nominee(self):
        # NY-15: Jose Vega lost the Democratic primary and is on the ballot
        # on another party's line.
        out = page_statuses(fixture("ny_15.txt"), 15)
        self.assertEqual(out["Jose Vega"], "nominee")
        self.assertEqual(out["Michael Blake"], "eliminated")

    def test_a_generic_withdrawn_list_does_not_outrank_the_ballot(self):
        text = "\n".join([
            "===Democratic primary===", "====Withdrawn====", "* [[Dee Switcher]], lawyer",
            box("2026 Somewhere's 1st congressional district election", ("Dee Switcher", 0, False)),
        ])
        boxes = results.parse_boxes(text) + results.candidate_lists(text)
        self.assertEqual(results.resolve_race(boxes), {"Dee Switcher": "nominee"})

    def test_list_names_are_read_from_bullets(self):
        text = ("====Withdrew after nomination====\n"
                "* [[Graham Platner]], [[Sullivan, Maine|Sullivan]] harbor master<ref>x</ref>\n"
                "* David Costello, former deputy secretary\n"
                "====Declined====\n* [[Nobody Here]], ignored\n")
        lists = dict(results.candidate_lists(text))
        self.assertEqual([r["name"] for r in lists[results.WITHDREW_NOMINEE_LIST]],
                         ["Graham Platner", "David Costello"])
        self.assertEqual(len(lists), 1)


class TestEliminatedButRunningOn(unittest.TestCase):
    """An "Eliminated" list is about one party's contest. Connecticut's page,
    read on 2026-10-02, lists three Democratic convention losers marked
    ''(running as an independent)'' - and lists each again in the
    independents' section under "Filed paperwork", not "Declared"."""

    def test_ct_convention_losers_who_only_filed_paperwork_stay_eliminated(self):
        text = fixture("ct_3_5.txt")
        # Andrew Rice: moved from "Declared" to "Filed paperwork" and out of
        # the infobox on 2026-09-15; the annotation was never updated.
        self.assertEqual(page_statuses(text, 3)["Andrew Rice"], "eliminated")
        self.assertEqual(page_statuses(text, 4)["Joseph Perez-Caputo"], "eliminated")
        self.assertEqual(page_statuses(text, 5)["Jackson Taddeo-Waite"], "eliminated")
        self.assertEqual(page_statuses(text, 3)["Rosa DeLauro"], "nominee")

    def test_relisted_as_declared_elsewhere_is_not_eliminated(self):
        # The page as it stood on 2026-09-13: Rice under the independents'
        # "Declared" heading and in the infobox as the Independent nominee.
        text = fixture("ct_3_5.txt").replace(
            "=====Declared=====\n*Thomas Egan, attorney\n",
            "=====Declared=====\n*Thomas Egan, attorney\n"
            "*Andrew Rice, biologist ''(previously ran in the Democratic primary)''\n")
        self.assertNotIn("Andrew Rice", page_statuses(text, 3))
        text = text.replace("| party2 = Republican Party (United States)\n",
                            "| party2 = Republican Party (United States)\n"
                            "| nominee3 = Andrew Rice\n| party3 = [[Independent politician|Independent]]\n", 1)
        self.assertEqual(page_statuses(text, 3)["Andrew Rice"], "nominee")

    def test_the_annotation_decides_only_when_the_page_lists_them_nowhere_else(self):
        text = ("===Democratic primary===\n====Eliminated at convention====\n"
                "* Ann Onward, organiser ''(running as an independent)''\n"
                "* Bo Writein, teacher ''(running as a write-in)''\n"
                "* Cy Done, lawyer\n")
        out = page_statuses(text)
        self.assertNotIn("Ann Onward", out)
        self.assertEqual(out["Bo Writein"], "eliminated")   # not a ballot line
        self.assertEqual(out["Cy Done"], "eliminated")

    def test_a_second_listing_in_the_same_party_or_as_a_write_in_is_no_run(self):
        # Hampton Harris (AL-2): "Nominee" of the voided May Republican
        # primary, "Eliminated" in the special one. Rio Phillips (WV Senate):
        # eliminated in the Democratic primary, then a write-in candidate.
        text = ("===Nonbinding Republican primary===\n====Nominee====\n"
                "*Hampton Harris, attorney\n"
                "===Special Republican primary===\n=====Eliminated in primary=====\n"
                "*Hampton Harris, nominee in the May primary election\n"
                "==Democratic primary==\n====Eliminated in primary====\n*Rio Phillips\n"
                "==Write-in Candidates==\n===Candidates===\n"
                "*Rio Phillips, cybersecurity technician\n")
        out = page_statuses(text)
        self.assertEqual(out["Hampton Harris"], "eliminated")
        self.assertEqual(out["Rio Phillips"], "eliminated")


class TestNames(unittest.TestCase):
    def test_formatting_templates_are_unwrapped(self):
        self.assertEqual(results.clean_name("{{nowrap|John Salvesen}}"), "John Salvesen")
        self.assertEqual(results.clean_name("{{nowrap|[[Al Green (politician)|Al Green]]}}"),
                         "Al Green")
        self.assertEqual(results.clean_name("{{sortname|Jane|Doe}}"), "Jane Doe")
        self.assertEqual(results.clean_name("Jane Doe{{efn|a note}}"), "Jane Doe")

    def test_ga5_lists_salvesen_once(self):
        out = page_statuses(fixture("ga_5.txt"), 5)
        self.assertEqual(sorted(n for n in out if "Salvesen" in n), ["John Salvesen"])
        self.assertFalse(any("{" in n or "}" in n for n in out))


class TestOpenPrimary(unittest.TestCase):
    """Louisiana's 2026 House races: a nonpartisan primary on November 3."""

    november = "2026 Louisiana's 1st congressional district election"
    december = "2026 Louisiana's 1st congressional district runoff election"

    def resolve(self, *tables):
        return results.resolve_race(results.parse_boxes("\n".join(tables)),
                                    has_runoff=True, open_primary=True)

    def test_a_november_box_without_winners_decides_nothing(self):
        out = self.resolve(box(self.november, ("A One", 0, False), ("B Two", 0, False)))
        self.assertEqual(out, {})
        coverage = results.coverage(results.parse_boxes(box(self.november, ("A One", 0, False))),
                                    open_primary=True)
        self.assertEqual(coverage, {"general": False, "parties": []})

    def test_the_real_page_today_names_no_nominee(self):
        out = page_statuses(fixture("la_1.txt"), 1, has_runoff=True, open_primary=True)
        self.assertNotIn("nominee", out.values())
        self.assertNotIn("advanced", out.values())

    def test_marked_winners_advance_and_the_rest_are_out(self):
        out = self.resolve(box(self.november, ("A One", 40, True), ("B Two", 35, True),
                               ("C Three", 25, False)))
        self.assertEqual(out, {"A One": "advanced", "B Two": "advanced", "C Three": "eliminated"})

    def test_an_outright_majority_wins(self):
        out = self.resolve(box(self.november, ("A One", 60, True), ("B Two", 40, False)))
        self.assertEqual(out, {"A One": "nominee", "B Two": "eliminated"})

    def test_the_december_runoff_decides(self):
        out = self.resolve(
            box(self.november, ("A One", 40, True), ("B Two", 35, True), ("C Three", 25, False)),
            box(self.december, ("A One", 45, False), ("B Two", 55, True)))
        self.assertEqual(out, {"A One": "eliminated", "B Two": "nominee", "C Three": "eliminated"})

    def test_the_override_replaces_the_fec_calendar(self):
        fec = {("LA", "H"): {"primary": "2026-08-07", "runoff": None},
               ("LA", "S"): {"primary": "2026-05-16", "runoff": "2026-06-27"}}
        dates, notes = results.effective_dates(fec, {"LA"})
        self.assertEqual(dates[("LA", "H")], {"primary": "2026-11-03", "runoff": "2026-12-12"})
        self.assertEqual(dates[("LA", "S")], fec[("LA", "S")])     # closed primaries kept
        self.assertEqual([n["kind"] for n in notes], ["open-primary"])
        self.assertFalse(results.primary_settled(dates, "LA", "H", datetime.date(2026, 10, 1)))
        self.assertTrue(results.primary_settled(dates, "LA", "S", datetime.date(2026, 10, 1)))
        self.assertTrue(results.open_primary("LA", "H"))
        self.assertFalse(results.open_primary("LA", "S"))

    def test_an_older_cache_gives_up_its_louisiana_house_results(self):
        cache = {"asOf": "2026-10-01", "cycle": 2026, "pending": [],
                 "races": {"H-LA-01-2026": {"status": {"X": "nominee"}},
                           "S-LA-2026": {"status": {"Y": "nominee"}}},
                 "dates": {"LA-H": {"primary": "2026-08-07", "runoff": None}}}
        cache = results.respect_open_primaries(cache)
        self.assertEqual(set(cache["races"]), {"S-LA-2026"})
        self.assertEqual(cache["pending"], ["H-LA-01-2026"])
        self.assertEqual(cache["dates"]["LA-H"], {"primary": "2026-11-03", "runoff": "2026-12-12"})


class TestSenateDateFallback(unittest.TestCase):
    def test_a_senate_race_without_a_primary_date_takes_the_house_date(self):
        # The FEC calendar lists Rhode Island's House primary (2026-09-09)
        # and no Senate one; the primary was statewide, so S-RI-2026 settles.
        fec = {("RI", "H"): {"primary": "2026-09-09", "runoff": None},
               ("RI", "S"): {"primary": None, "runoff": None}}
        logged = []
        dates, notes = results.effective_dates(fec, {"RI"}, log=logged.append)
        self.assertEqual(dates[("RI", "S")]["primary"], "2026-09-09")
        self.assertTrue(results.primary_settled(dates, "RI", "S", datetime.date(2026, 10, 1)))
        self.assertEqual(notes[0]["kind"], "senate-from-house")
        self.assertIn("RI", logged[0])
        self.assertIn("2026-09-09", logged[0])

    def test_a_state_with_no_senate_election_borrows_nothing(self):
        # People file for Arizona's Senate seats, which are not up in 2026;
        # the FEC calendar has no AZ Senate slot, and none is invented.
        fec = {("AZ", "H"): {"primary": "2026-07-21", "runoff": None}}
        dates, notes = results.effective_dates(fec, {"AZ"})
        self.assertNotIn(("AZ", "S"), dates)
        self.assertEqual([n for n in notes if n["seat"] == "AZ-S"], [])

    def test_a_senate_date_of_its_own_is_kept(self):
        fec = {("RI", "H"): {"primary": "2026-09-09", "runoff": None},
               ("RI", "S"): {"primary": "2026-09-10", "runoff": None}}
        dates, notes = results.effective_dates(fec, {"RI"})
        self.assertEqual(dates[("RI", "S")]["primary"], "2026-09-10")
        self.assertEqual([n for n in notes if n["seat"].startswith("RI")], [])


class TestValidateResults(unittest.TestCase):
    """validate.check_results groups nominees by the line they are on."""

    race = {"id": "H-NY-15-2026", "state": "NY", "settled": True,
            "incumbentIds": [], "results": {}}

    def person(self, pid, name, party, ballot=None):
        p = {"id": pid, "name": name, "party": party, "raceStatus": "nominee",
             "raceId": "H-NY-15-2026", "isCandidate": True}
        if ballot:
            p["ballotParty"] = ballot
        return p

    def codes(self, people):
        from kyc import validate
        return [i.code for i in validate.check_results(people, [self.race])]

    def test_a_primary_loser_on_another_line_is_not_a_second_nominee(self):
        # NY-15 on 2026-10-01: Ritchie Torres (Democratic) and Jose Vega, who
        # lost that primary and is on the "Speak The Truth" line.
        people = [self.person("a", "Ritchie Torres", "Democrat", "democratic"),
                  self.person("b", "Jose Vega", "Democrat", "speak the truth")]
        self.assertNotIn("multiple-nominees", self.codes(people))

    def test_two_nominees_on_one_ballot_line_are_still_an_error(self):
        people = [self.person("a", "Ritchie Torres", "Democrat", "democratic"),
                  self.person("b", "Jose Vega", "Democrat", "democratic")]
        self.assertIn("multiple-nominees", self.codes(people))
        # Same with no ballot line at all: the roster party, normalised.
        people = [self.person("a", "Ritchie Torres", "Democrat"),
                  self.person("b", "Jose Vega", "DEM")]
        self.assertIn("multiple-nominees", self.codes(people))

    def test_independents_share_a_ballot(self):
        people = [self.person("a", "Ann One", "Independent"),
                  self.person("b", "Bob Two", "unaffiliated", "independent")]
        self.assertNotIn("multiple-nominees", self.codes(people))


class TestValidateResultsPages(unittest.TestCase):
    def issues(self, cache):
        from kyc import validate
        return {i.code: i for i in validate.check_results_pages(cache)}

    def test_an_unparsed_page_is_an_error(self):
        found = self.issues({"unparsedPages": ["CA-H: 2026 ... in California"]})
        self.assertEqual(found["results-page-unparsed"].level, "error")

    def test_a_missing_page_is_a_warning(self):
        found = self.issues({"missingPages": ["VI-H"], "fetchFailed": ["TX-H"]})
        self.assertEqual(found["results-page-missing"].level, "warn")
        self.assertEqual(list(found["results-page-missing"].detail), ["VI-H"])
        self.assertEqual(found["results-fetch-failed"].level, "warn")

    def test_an_override_the_fec_disagrees_with_is_reported(self):
        _, notes = results.effective_dates({("LA", "H"): {"primary": "2026-08-07", "runoff": None}})
        found = self.issues({"calendarNotes": notes})
        self.assertIn("2026-08-07", found["calendar-override-disagrees"].detail[0])

    def test_a_clean_run_reports_nothing(self):
        self.assertEqual(self.issues({"missingPages": [], "unparsedPages": []}), {})
        self.assertEqual(self.issues(None), {})
