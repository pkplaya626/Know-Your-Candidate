"""Tests for primary results: who is still in each race.

The FEC's register says who filed; it does not say who lost. These tests pin
the parts of the resolver that would silently mislabel a real person if they
regressed: the winner marker, the runoff/general precedence, name matching,
and the two gates (calendar, exact-match-only) that keep it conservative.
"""

import datetime
import json
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

    def test_an_unreported_runoff_eliminates_nobody(self):
        # An editor posts the runoff box before the count: no winner marked.
        # Both qualifiers are still in the race, not both beaten.
        text = "\n".join([
            box("Democratic primary results",
                ("Christian Menefee", 43, True), ("Al Green", 42, True), ("Gretchen Brown", 1, False)),
            box("Democratic primary runoff results",
                ("Christian Menefee", 0, False), ("Al Green", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text), has_runoff=True)
        self.assertEqual(out["Christian Menefee"], "advanced")
        self.assertEqual(out["Al Green"], "advanced")
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

    def test_a_letter_apart_misspelling_on_the_ballot_is_the_primary_winner(self):
        # NM-1, 2026-10-14: the Republican primary table and the infobox say
        # "Didi Okpareke"; the November table says "Didi Okapareke".
        text = "\n".join([
            box("Republican primary results", ("Didi Okpareke", 31809, True)),
            box("2026 New Mexico's 1st congressional district election",
                ("Melanie Stansbury", 0, False), ("Didi Okapareke", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out, {"Didi Okpareke": "nominee", "Melanie Stansbury": "nominee"})

    def test_two_near_names_in_one_table_stay_two_people(self):
        text = box("Republican primary results", ("Michael Johnson", 9, True),
                   ("Michael Johnston", 4, False))
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out, {"Michael Johnson": "nominee", "Michael Johnston": "eliminated"})
        # Nor are different given names, or surnames under five letters,
        # ever folded.
        self.assertEqual(results._near_spellings([
            ("A", [{"name": "Ann Okpareke"}]), ("B", [{"name": "Bea Okapareke"}]),
            ("C", [{"name": "Jo Rice"}]), ("D", [{"name": "Jo Rise"}])]), {})

    def test_a_five_letter_surname_a_letter_apart_is_the_primary_winner(self):
        # GA-9, 2026-10-17: the Democratic primary's marked winner is
        # "Caitlyn Gegen" and the November table says "Caitlyn Gegan". Read
        # as two people, the winner was "withdrawn" and her profile folded
        # away under "no longer in this race".
        text = "\n".join([
            box("Democratic primary results", ("Caitlyn Gegen", 25570, True),
                ("Nick Alex", 17056, False)),
            box("2026 Georgia's 9th congressional district election",
                ("Andrew Clyde", 0, False), ("Caitlyn Gegan", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text))
        self.assertEqual(out["Caitlyn Gegen"], "nominee")
        self.assertNotIn("Caitlyn Gegan", out)

    def ut1(self, infobox_name, general_name="Riley Owen", mcadams_won=False,
            infobox_party="Republican Party (United States)"):
        """A UT-1 page as it stood on results night (2026-11-04): the
        infobox spells the Republican nominee one way, everything else
        another."""
        infobox = "\n".join([
            "{{Infobox election", "| election_name = 2026 Utah's 1st congressional district election",
            f"| nominee1 = {infobox_name}", f"| party1 = {infobox_party}",
            "| nominee2 = Ben McAdams", "| party2 = Democratic Party (United States)", "}}"])
        primary = box("Republican primary results", (general_name, 900, True),
                      ("Blake Moore", 800, False))
        primary = primary.replace("Democratic Party (United States)",
                                  "Republican Party (United States)")
        general = box("2026 Utah's 1st congressional district election",
                      (general_name, 140, False), ("Ben McAdams", 160, mcadams_won))
        general = general.replace("| party = Democratic Party (United States)\n"
                                  f"| candidate = {general_name}",
                                  "| party = Republican Party (United States)\n"
                                  f"| candidate = {general_name}")
        return page_statuses("\n".join([infobox, primary, general]), general_held=True)

    def test_an_infobox_misspelling_is_the_november_tables_nominee(self):
        # UT-1, results night: "nominee1 = Riley Owens" over a page writing
        # "Riley Owen" everywhere else. Read as two people, the infobox's
        # spelling was a second Republican on the ballot who matched no
        # filing, and stayed "nominee" beside the marked winner.
        out = self.ut1("Riley Owens")
        self.assertEqual(out, {"Riley Owen": "nominee", "Ben McAdams": "nominee",
                               "Blake Moore": "eliminated"})
        out = self.ut1("Riley Owens", mcadams_won=True)
        self.assertEqual(out, {"Riley Owen": "defeated", "Ben McAdams": "elected",
                               "Blake Moore": "eliminated"})
        # MO-8's infobox swaps two letters: "Riechard" over "Reichard".
        out = self.ut1("Christopher Riechard", "Christopher Reichard", mcadams_won=True)
        self.assertEqual(out["Christopher Reichard"], "defeated")
        self.assertNotIn("Christopher Riechard", out)

    def test_with_no_november_table_an_infobox_misspelling_is_the_primary_winner(self):
        # MO-8 on results night had no November table at all: its infobox's
        # "Christopher Riechard" stood beside the Democratic primary's
        # marked winner "Christopher Reichard", and the state page listed
        # "Riechard (Democratic)" as also on the November ballot.
        text = "\n".join([
            "{{Infobox election", "| nominee1 = Jason Smith",
            "| party1 = Republican Party (United States)",
            "| nominee2 = Christopher Riechard", "| party2 = Democratic Party (United States)",
            "}}",
            box("Democratic primary results", ("Christopher Reichard", 900, True),
                ("Frank Barnitz", 800, False)),
            box("Republican primary results", ("Jason Smith", 900, True)).replace(
                "Democratic Party (United States)", "Republican Party (United States)"),
        ])
        out = page_statuses(text, general_held=True)
        self.assertEqual(out, {"Christopher Reichard": "nominee", "Frank Barnitz": "eliminated",
                               "Jason Smith": "nominee"})
        # A primary's loser a letter apart is no nominee to fold into.
        dem = "Democratic Party (United States)"
        info = (results.INFOBOX_TITLE, [{"name": "Jo Owens", "party": dem, "won": False,
                                         "withdrawn": False, "votes": None}])
        primary = ("Democratic primary results", [
            {"name": "Jo Owen", "party": dem, "won": False, "withdrawn": False, "votes": 1},
            {"name": "Al Smith", "party": dem, "won": True, "withdrawn": False, "votes": 2}])
        self.assertEqual(results._infobox_spellings([primary, info]), {})
        primary[1][0]["won"] = True
        self.assertEqual(results._infobox_spellings([primary, info]), {"Jo Owens": "Jo Owen"})

    def test_an_infobox_name_is_folded_only_into_its_own_partys_one_row(self):
        # Another party's row a letter apart is another person, and so is
        # one whose party neither side gives.
        out = self.ut1("Riley Owens", infobox_party="Democratic Party (United States)")
        self.assertEqual(out["Riley Owens"], "nominee")
        out = self.ut1("Riley Owens", infobox_party="")
        self.assertEqual(out["Riley Owens"], "nominee")
        # Two rows that fit, a different given name, or a row the infobox
        # names too: nothing is folded.
        rep = "Republican Party (United States)"
        info = (results.INFOBOX_TITLE, [{"name": "Jo Owens", "party": rep, "won": False,
                                         "withdrawn": False, "votes": None}])
        general = ("2026 Utah's 1st congressional district election", [
            {"name": "Jo Owen", "party": rep, "won": False, "withdrawn": False, "votes": 1},
            {"name": "Jo Owes", "party": rep, "won": False, "withdrawn": False, "votes": 1}])
        self.assertEqual(results._infobox_spellings([general, info]), {})
        general[1][1]["name"] = "Al Owens"
        self.assertEqual(results._infobox_spellings([general, info]), {"Jo Owens": "Jo Owen"})
        info[1].append({"name": "Jo Owen", "party": rep, "won": False, "withdrawn": False,
                        "votes": None})
        self.assertEqual(results._infobox_spellings([general, info]), {})
        self.assertTrue(results._one_edit("riechard", "reichard"))
        self.assertTrue(results._one_edit("owen", "owens"))
        self.assertFalse(results._one_edit("owen", "owen"))
        self.assertFalse(results._one_edit("rice", "rise ") or results._one_edit("abcd", "badc"))

    def test_a_surname_with_a_space_and_with_a_hyphen_is_one_person(self):
        # CA-40: the page lists "Esther Kim Varet" among those eliminated and
        # its results box says "Esther Kim-Varet". Two spellings fitted her
        # one filing (VARET, ESTHER KIM), and a primary loser read "Not on
        # the November ballot (unconfirmed)".
        boxes = results.parse_boxes(box("Primary results", ("Young Kim", 100, True),
                                        ("Esther Kim-Varet", 50, False)))
        boxes.append((results.ELIMINATED_LIST, [{"name": "Esther Kim Varet", "won": False,
                                                 "withdrawn": False, "votes": None,
                                                 "party": None, "article": None}]))
        out = results.resolve_race(boxes)
        # One name, the one without the hyphen: each spelling is in one
        # table, and the hyphenated one links a redirect to her article.
        self.assertEqual(out, {"Young Kim": "nominee", "Esther Kim Varet": "eliminated"})
        rows = [{"candidate_id": "H6CA40309", "name": "VARET, ESTHER KIM"},
                {"candidate_id": "H8CA39240", "name": "KIM, YOUNG"}]
        found, ambiguous = results.match_names(list(out), rows)
        self.assertEqual(found["Esther Kim Varet"], ["H6CA40309"])
        # A page that writes the hyphen in more tables keeps it.
        boxes = results.parse_boxes(box("Primary results", ("Young Kim", 100, True),
                                        ("Ann Greene-Placentia", 50, True)) + "\n" +
                                    box("General election", ("Ann Greene-Placentia", 0, False)))
        boxes.append((results.ELIMINATED_LIST, [{"name": "Ann Greene Placentia", "won": False,
                                                 "withdrawn": False, "votes": None,
                                                 "party": None, "article": None}]))
        self.assertIn("Ann Greene-Placentia", results.resolve_race(boxes))
        self.assertEqual(ambiguous, [])
        self.assertTrue(results._same_spelling("Esther Kim Varet", "Esther Kim-Varet"))
        # The given name must still fit.
        self.assertFalse(results._same_spelling("Ann Kim Varet", "Esther Kim-Varet"))

    def test_two_people_in_one_table_are_never_one(self):
        # Alaska's top-four primary lists Senator "Dan S. Sullivan" and
        # "Daniel J. Sullivan Jr."; folded into one, the second - certified
        # for November - vanished from the race.
        text = "\n".join([
            box("Nonpartisan primary results", ("Dan S. Sullivan", 90000, True),
                ("Daniel J. Sullivan Jr.", 4107, True), ("Ann Smith", 10, False)),
            box("2026 United States Senate election in Alaska",
                ("Dan S. Sullivan", 0, False)),
        ])
        out = results.resolve_race(results.parse_boxes(text))
        self.assertIn("Daniel J. Sullivan Jr.", out)
        self.assertEqual(out["Dan S. Sullivan"], "nominee")
        # Two middle initials that disagree are two people anywhere.
        self.assertFalse(results._same_spelling("Dan S. Sullivan", "Daniel J. Sullivan Jr."))
        self.assertTrue(results._same_spelling("Norma J. Torres", "Norma Torres"))

    def test_a_row_with_a_nested_template_on_its_own_line_is_read(self):
        # 2022 Georgia Senate: "{{nowrap|...}}" in the candidate and change
        # fields made both runoff candidates' November rows vanish.
        text = "\n".join([
            "{{Election box begin no change", "| title = 2022 United States Senate election in Georgia",
            "}}",
            "{{Election box winning candidate with party link no change",
            " |party      = Democratic Party (United States)",
            " |candidate  = {{nowrap|[[Raphael Warnock]] (incumbent)}}",
            " |votes      = 1,946,117", " |change = {{nowrap|N/A}}", "}}",
            "{{Election box candidate with party link no change",
            " |party      = Republican Party (United States)",
            " |candidate  = [[Herschel Walker]]", " |votes = 1,908,442",
            " |change = {{nowrap|{{small|N/A}}}}", "}}",
            "{{Election box end}}",
        ])
        rows = [r for _t, rs in results.parse_boxes(text) for r in rs]
        self.assertEqual([(r["name"], r["won"]) for r in rows],
                         [("Raphael Warnock", True), ("Herschel Walker", False)])

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

    def test_a_seat_with_its_own_primary_keeps_its_own_date(self):
        # Alabama's 1st, 2nd, 6th and 7th districts were postponed to an
        # August 11 special primary; every Alabama House race read "Primary
        # held 2026-05-19" because the calendar is kept per state.
        dates = {("AL", "H"): {"primary": "2026-05-19", "runoff": "2026-06-16"}}
        for n in (1, 2, 6, 7):
            slot = results.seat_slot(dates, f"H-AL-0{n}-2026")
            self.assertEqual(slot, {"primary": "2026-08-11", "runoff": None})
            # Read before August 11, its results would have been the May
            # primary's.
            self.assertFalse(results.primary_settled({("AL", "H"): slot}, "AL", "H",
                                                     datetime.date(2026, 8, 1)))
        self.assertEqual(results.seat_slot(dates, "H-AL-03-2026"),
                         {"primary": "2026-05-19", "runoff": "2026-06-16"})
        self.assertEqual(results.seat_slot(dates, "S-AL-2026"), {})

    def test_every_seat_date_names_its_source(self):
        from kyc import overrides
        for rid, slot in overrides.SEAT_PRIMARY_DATES.items():
            self.assertRegex(slot["primary"], r"^2026-\d{2}-\d{2}$", rid)
            self.assertIn("read 20", slot["source"], rid)


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


class TestNamesThePageMayUse(unittest.TestCase):
    """36 filers the results page names under a nickname or a reversed
    filing were told "Not on the 2026 primary ballot", six of them November
    nominees: Max Ganorkar (NC-4) is filed as Mahesh, Lisa Carlquist as
    "LISA, CARLQUIST", Bernadette Greene-Placentia without the hyphen."""

    def cache(self, unmatched):
        return {"asOf": "2026-10-05", "races": {
            "H-NC-04-2026": {"status": {"H6NC04001": "nominee"}, "unmatched": dict(unmatched),
                             "ambiguous": []}}}

    def filer(self, cid, name, filed=None):
        return {"id": "FEC_" + cid, "fecCandidateId": cid, "isCandidate": True,
                "source": "fec-field", "name": name, "filedName": filed or name,
                "state": "NC", "chamber": "House (Candidate)", "districtNum": 4}

    def test_the_same_words_in_another_order_are_the_same_name(self):
        for page, name, filed in (("Lisa Carlquist", "Carlquist Lisa", "LISA, CARLQUIST"),
                                  ("Jay J. Bowman", "Bowman J Jay", "JAY, BOWMAN J"),
                                  ("Bernadette Greene-Placentia", "Bernadette Greene Placentia",
                                   "GREENE PLACENTIA, BERNADETTE")):
            person = self.filer("H6NC04999", name, filed)
            cache = self.cache({page: "nominee"})
            results.apply_cache([person], cache)
            self.assertEqual(person["raceStatus"], "nominee", page)
            self.assertEqual(person["name"], page)               # the ballot's spelling
            self.assertIn(name, person["aliases"])               # the filed one still found
            self.assertNotIn(page, cache["races"]["H-NC-04-2026"]["unmatched"])

    def test_an_evidenced_alias_settles_a_nickname(self):
        from kyc import overrides
        self.assertIn("H4NC02150", overrides.RESULT_NAMES)
        person = self.filer("H4NC02150", "Mahesh Ganorkar", "GANORKAR, MAHESH")
        results.apply_cache([person], self.cache({"Max Ganorkar": "nominee"}))
        self.assertEqual((person["raceStatus"], person["name"]), ("nominee", "Max Ganorkar"))

    def test_every_alias_cites_the_campaigns_own_committee(self):
        from kyc import overrides
        for cid, (name, why) in overrides.RESULT_NAMES.items():
            self.assertRegex(cid, r"^[HS]\d[A-Z]{2}\d{5}$")
            self.assertGreaterEqual(len(name.split()), 2, cid)
            self.assertRegex(why, r"committee C\d{8}", cid)

    def test_a_possible_name_that_lost_keeps_them_off_the_ballot(self):
        # "Mark Su" may be "SU, DONGBO". Either way he is not on the November
        # ballot, and with no status at all he read as still running.
        person = self.filer("H6NC04998", "Dongbo Su", "SU, DONGBO")
        cache = self.cache({"Mark Su": "eliminated"})
        results.apply_cache([person], cache)
        self.assertEqual(person["raceStatus"], "unlisted")
        self.assertTrue(person["raceStatusUnconfirmed"])     # said as "not on the November ballot"
        self.assertEqual(cache["unclear"], [("Dongbo Su", "H-NC-04-2026", ["Mark Su"])])

    def test_a_possible_name_on_the_ballot_leaves_them_undecided(self):
        person = self.filer("H6NC04998", "Ndidiamaka Okpareke", "OKPAREKE, NDIDIAMAKA")
        cache = self.cache({"Didi Okapareke": "nominee", "Didi Okpareke": "withdrawn"})
        results.apply_cache([person], cache)
        self.assertNotIn("raceStatus", person)
        self.assertEqual(person["maybeNamed"], ["Didi Okapareke", "Didi Okpareke"])

    def test_near_is_one_letter_on_long_words_only(self):
        self.assertTrue(results._near("okpareke", "okapareke"))
        self.assertTrue(results._near("gilespie", "gillespie"))
        self.assertFalse(results._near("su", "sy"))
        self.assertFalse(results._near("williams", "williamson"))

    def test_another_filer_with_the_same_words_blocks_the_claim(self):
        person = self.filer("H6NC04999", "Carlquist Lisa", "LISA, CARLQUIST")
        field = {"candidates": [
            {"candidate_id": "H6NC04999", "name": "LISA, CARLQUIST", "office": "H",
             "state": "NC", "district_number": 4},
            {"candidate_id": "H0NC04000", "name": "CARLQUIST, LISA", "office": "H",
             "state": "NC", "district_number": 4}]}
        cache = self.cache({"Lisa Carlquist": "nominee"})
        results.apply_cache([person], cache, field=field)
        self.assertNotEqual(person.get("raceStatus"), "nominee")

    def test_a_name_the_matcher_found_ambiguous_is_left_alone(self):
        person = self.filer("H6NC04999", "Carlquist Lisa", "LISA, CARLQUIST")
        cache = self.cache({"Lisa Carlquist": "nominee"})
        cache["races"]["H-NC-04-2026"]["ambiguous"] = ["Lisa Carlquist"]
        results.apply_cache([person], cache)
        self.assertNotEqual(person.get("raceStatus"), "nominee")

    def test_a_hyphen_alone_is_not_a_new_name(self):
        person = self.filer("H6NC04999", "Melissa Conyears-Ervin", "CONYEARS-ERVIN, MELISSA")
        results.apply_cache([person], self.cache({"Melissa Conyears Ervin": "eliminated"}))
        self.assertEqual(person["raceStatus"], "eliminated")
        self.assertEqual(person["name"], "Melissa Conyears-Ervin")

    def test_a_different_surname_is_still_absent(self):
        person = self.filer("H6NC04997", "Jane Roe")
        results.apply_cache([person], self.cache({"Mark Su": "eliminated"}))
        self.assertEqual(person["raceStatus"], "unlisted")

    def test_a_name_ambiguous_only_between_one_persons_registrations_is_theirs(self):
        # "Dan Miressi" fitted "MIRESSI, DAN" and "MIRESSI, DANIEL", one
        # committee's two registrations, so the fetch left it ambiguous and
        # he read as a challenger whose primary had not been held.
        person = self.filer("H6CT04150", "Daniel Miressi", "MIRESSI, DANIEL")
        person.update(state="CT", districtNum=4, otherFecIds=["H4CT04189"])
        field = {"candidates": [
            {"candidate_id": "H6CT04150", "name": "MIRESSI, DANIEL", "office": "H",
             "state": "CT", "district_number": 4},
            {"candidate_id": "H4CT04189", "name": "MIRESSI, DAN", "office": "H",
             "state": "CT", "district_number": 4}]}
        cache = {"asOf": "2026-10-05", "races": {"H-CT-04-2026": {
            "status": {}, "unmatched": {"Dan Miressi": "eliminated"},
            "ambiguous": ["Dan Miressi"], "unsure": ["H4CT04189", "H6CT04150"]}}}
        results.apply_cache([person], cache, field=field)
        self.assertEqual(person["raceStatus"], "eliminated")
        # Another filer the name fits still leaves it alone.
        other = dict(person, name="Daniel Miressi")     # as filed, before the rename
        other.pop("raceStatus", None)
        field["candidates"].append({"candidate_id": "H6CT04999", "name": "MIRESSI, DANIELLE",
                                    "office": "H", "state": "CT", "district_number": 4})
        cache["races"]["H-CT-04-2026"].update(unmatched={"Dan Miressi": "eliminated"}, status={})
        results.apply_cache([other], cache, field=field)
        self.assertNotEqual(other.get("raceStatus"), "eliminated")

    def test_unsure_and_every_possible_name_out_is_off_the_ballot(self):
        # Josh Weil withdrew; a second Weil filing made the fetch unsure,
        # and he was counted on Florida's Senate ballot with no status.
        person = self.filer("H6NC04998", "Joshua Joseph Weil", "WEIL, JOSHUA JOSEPH")
        cache = self.cache({"Josh Weil": "withdrawn"})
        cache["races"]["H-NC-04-2026"].update(ambiguous=["Josh Weil"],
                                              unsure=["H2NC04466", "H6NC04998"])
        results.apply_cache([person], cache)
        self.assertEqual(person["raceStatus"], "unlisted")
        self.assertTrue(person["raceStatusUnconfirmed"])

    def test_a_filer_whose_party_held_no_primary_is_not_said_to_await_one(self):
        # FL-18's Deva Simmons, no party: the page names both parties'
        # nominees and not her. Whether she is on the November ballot is
        # not known here, and she is not counted as on it.
        person = self.filer("H6NC04994", "Deva Simmons", "SIMMONS, DEVA")
        person["party"] = "No Party Affiliation"
        cache = self.cache({})
        cache["races"]["H-NC-04-2026"]["decided"] = {"general": False, "parties": []}
        results.apply_cache([person], cache)
        self.assertNotIn("raceStatus", person)
        self.assertTrue(person["ballotUnknown"])

    def test_through_an_all_party_primary_is_not_a_party_nomination(self):
        # California's top two: nobody is a party's nominee.
        ca = {"id": "FEC_H6CA11001", "fecCandidateId": "H6CA11001", "isCandidate": True,
              "state": "CA", "chamber": "House (Candidate)", "districtNum": 11}
        tx = dict(ca, id="FEC_H6TX11001", fecCandidateId="H6TX11001", state="TX")
        cache = {"asOf": "2026-10-05", "races": {
            "H-CA-11-2026": {"status": {"H6CA11001": "nominee"}, "unmatched": {}, "ambiguous": []},
            "H-TX-11-2026": {"status": {"H6TX11001": "nominee"}, "unmatched": {}, "ambiguous": []}}}
        results.apply_cache([ca, tx], cache)
        self.assertEqual(ca["allPartyPrimary"], "top-two")
        self.assertNotIn("allPartyPrimary", tx)
        self.assertEqual(results.ALL_PARTY_PRIMARIES["AK"][0], "top-four")

    def test_one_name_two_filings_settles_neither(self):
        a = self.filer("H6NC04996", "Carlquist Lisa")
        b = self.filer("H6NC04995", "Lisa Carlquist")
        cache = self.cache({"Lisa Carlquist": "nominee"})
        results.apply_cache([a, b], cache)
        self.assertNotEqual(a.get("raceStatus"), "nominee")
        self.assertNotEqual(b.get("raceStatus"), "nominee")
        self.assertIn("Lisa Carlquist", cache["races"]["H-NC-04-2026"]["unmatched"])

    def test_a_bracketed_nickname_is_not_part_of_the_filed_words(self):
        # IN-6: the filing is "WIRTH, CYNTHIA (CINDE)"; the page names
        # "Cynthia Wirth" the nominee and "Cinde Wirth" elsewhere, so the
        # matcher found both ambiguous and her profile had no status at all.
        person = self.filer("H6IN06230", "Cynthia (Cinde) Wirth", "WIRTH, CYNTHIA (CINDE)")
        person.update(state="IN", districtNum=6)
        field = {"candidates": [
            {"candidate_id": "H6IN06230", "name": "WIRTH, CYNTHIA (CINDE)", "office": "H",
             "state": "IN", "district_number": 6},
            {"candidate_id": "H4IN06185", "name": "SHREVE, JEFFERSON", "office": "H",
             "state": "IN", "district_number": 6}]}
        cache = {"asOf": "2026-10-17", "races": {"H-IN-06-2026": {
            "status": {"H4IN06185": "nominee"},
            "unmatched": {"Cinde Wirth": "withdrawn", "Cynthia Wirth": "nominee"},
            "ambiguous": ["Cinde Wirth", "Cynthia Wirth"], "unsure": ["H6IN06230"]}}}
        results.apply_cache([person], cache, field=field)
        self.assertEqual(person["raceStatus"], "nominee")
        # The nickname never stands in for the name it follows.
        self.assertIn("Cinde Wirth", cache["races"]["H-IN-06-2026"]["unmatched"])

    def test_an_ambiguous_name_is_claimed_only_with_the_whole_register(self):
        # Alaska: "Daniel J. Sullivan Jr." fits both Sullivans' filings, and
        # is word for word "SULLIVAN, DANIEL J" - unique among every filer.
        person = self.filer("S6AK00326", "Daniel J Sullivan", "SULLIVAN, DANIEL J")
        person.update(state="AK", chamber="Senate (Candidate)", districtNum=None)
        field = {"candidates": [
            {"candidate_id": "S6AK00326", "name": "SULLIVAN, DANIEL J", "office": "S",
             "state": "AK"},
            {"candidate_id": "S4AK00214", "name": "SULLIVAN, DAN", "office": "S", "state": "AK"}]}

        def cache():
            return {"asOf": "2026-10-17", "races": {"S-AK-2026": {
                "status": {"S4AK00214": "nominee"},
                "unmatched": {"Daniel J. Sullivan Jr.": "nominee"},
                "ambiguous": ["Daniel J. Sullivan Jr."],
                "unsure": ["S4AK00214", "S6AK00326"]}}}
        results.apply_cache([person], cache(), field=field)
        self.assertEqual(person["raceStatus"], "nominee")
        # Without the register no one can say no other filer has the words.
        alone = dict(person)
        alone.pop("raceStatus")
        results.apply_cache([alone], cache())
        self.assertNotEqual(alone.get("raceStatus"), "nominee")

    def test_a_surname_written_as_two_words_is_one_surname(self):
        # Montana: the page's "Michael Black Wolf" lost the Democratic
        # primary; the FEC files "BLACKWOLF, MICHAEL JAMES MR.".
        rows = [{"candidate_id": "S6MT00246", "name": "BLACKWOLF, MICHAEL JAMES MR."},
                {"candidate_id": "S6MT00253", "name": "WALSH, REILLY"}]
        found, ambiguous = results.match_names(["Michael Black Wolf"], rows)
        self.assertEqual(found, {"Michael Black Wolf": ["S6MT00246"]})
        # The letters of the surname must still be the same.
        found, _ = results.match_names(["Michael Black Wolfe"], rows)
        self.assertEqual(found, {})

    def test_a_first_name_the_page_lists_as_beaten_only_weakens_unlisted(self):
        # CA-2: Nicolette Hahn was on the June ballot as Nicolette Hahn
        # Niman; the page writes "Nicolette Niman", eliminated. Not a match,
        # but "Not on the 2026 primary ballot" was not true either.
        # She files as No Party Affiliation, and California's page titles
        # its table "Primary results": a top-two primary holds everyone, so
        # her contest was decided whatever her party (not "ballot unknown").
        person = self.filer("H6CA02317", "Nicolette G. Hahn", "HAHN, NICOLETTE G.")
        person.update(state="CA", districtNum=2, party="No Party Affiliation")
        cache = {"asOf": "2026-10-17", "races": {"H-CA-02-2026": {
            "status": {}, "unmatched": {"Nicolette Niman": "eliminated"}, "ambiguous": [],
            "decided": {"general": True, "parties": ["primary results"]}}}}
        results.apply_cache([person], cache)
        self.assertEqual(person["raceStatus"], "unlisted")
        self.assertTrue(person["raceStatusUnconfirmed"])     # "Not on the November ballot"
        # A nominee of that first name changes nothing: no claim is made.
        other = self.filer("H6CA02317", "Nicolette G. Hahn", "HAHN, NICOLETTE G.")
        other.update(state="CA", districtNum=2)
        cache["races"]["H-CA-02-2026"]["unmatched"] = {"Nicolette Niman": "nominee"}
        results.apply_cache([other], cache)
        self.assertEqual(other["raceStatus"], "unlisted")
        self.assertNotIn("raceStatusUnconfirmed", other)

    def test_a_minor_party_filer_missing_from_the_november_table_is_unknown(self):
        # Colorado's pages list the major parties' nominees; its certified
        # list adds Libertarian, Unity and unaffiliated candidates in every
        # district. Shimon Blau (unaffiliated, $184,749) read "Not on the
        # 2026 primary ballot".
        person = self.filer("H6CO01356", "Shimon Blau", "BLAU, SHIMON")
        person.update(state="CO", districtNum=1, party="Unaffiliated")
        cache = {"asOf": "2026-10-17", "races": {"H-CO-01-2026": {
            "status": {"H6CO01001": "nominee"}, "unmatched": {}, "ambiguous": [],
            "decided": {"general": True, "parties": ["democratic", "republican"]}}}}
        results.apply_cache([person], cache)
        self.assertNotIn("raceStatus", person)
        self.assertTrue(person["ballotUnknown"])
        # A major party's filer the November table leaves out is still out.
        dem = self.filer("H6CO01999", "Jane Roe", "ROE, JANE")
        dem.update(state="CO", districtNum=1, party="Democrat")
        results.apply_cache([dem], cache)
        self.assertEqual(dem["raceStatus"], "unlisted")

    def test_a_withdrawal_read_from_a_near_name_on_the_ballot_is_not_settled(self):
        # Whatever the folding misses, a primary winner the page calls
        # "withdrawn" while its November table holds a name that may be
        # theirs is undecided, never "Withdrew from the 2026 race".
        person = self.filer("H6GA09284", "Caitlyn Gegen", "GEGEN, CAITLYN")
        person.update(state="GA", districtNum=9)
        cache = {"asOf": "2026-10-17", "races": {"H-GA-09-2026": {
            "status": {"H6GA09284": "withdrawn"}, "unmatched": {"Caitlyn Gegan": "nominee"},
            "ambiguous": []}}}
        results.apply_cache([person], cache)
        self.assertNotIn("raceStatus", person)
        self.assertEqual(person["maybeNamed"], ["Caitlyn Gegan"])

    def test_a_nickname_the_page_settled_is_the_name_shown(self):
        # PA-1: the page and the markets say "Bob Harvie"; the FEC files
        # "HARVIE, ROBERT J". The page's name is shown and the filed one
        # kept, for "Files with the FEC as".
        person = self.filer("H6PA01001", "Robert J Harvie", "HARVIE, ROBERT J")
        cache = self.cache({})
        cache["races"]["H-NC-04-2026"].update(status={"H6PA01001": "nominee"},
                                              names={"H6PA01001": "Bob Harvie"})
        results.apply_cache([person], cache)
        self.assertEqual((person["name"], person["fecName"]), ("Bob Harvie", "Robert J Harvie"))
        # A middle initial dropped is not another name.
        same = self.filer("H6PA01001", "Robert J Harvie", "HARVIE, ROBERT J")
        cache["races"]["H-NC-04-2026"]["names"] = {"H6PA01001": "Robert Harvie"}
        results.apply_cache([same], cache)
        self.assertEqual(same["name"], "Robert J Harvie")

    def test_the_formal_name_on_a_page_does_not_replace_the_campaigns(self):
        # The results tables write "Matthew Dunlap" and "Michael Sacks";
        # they campaign, and filed, as Matt Dunlap and Mike Sacks. A page's
        # formal form finds them and is not shown in their place.
        person = self.filer("H6ME02171", "Matt Dunlap", "DUNLAP, MATT")
        cache = self.cache({})
        cache["races"]["H-NC-04-2026"].update(status={"H6ME02171": "nominee"},
                                              names={"H6ME02171": "Matthew Dunlap"})
        results.apply_cache([person], cache)
        self.assertEqual(person["name"], "Matt Dunlap")
        self.assertNotIn("fecName", person)
        self.assertIn("Matthew Dunlap", person["aliases"])

    def test_a_page_name_the_filer_goes_by_is_the_name_shown(self):
        # A later given name, its short form, or the nickname the filing
        # itself brackets is the name a campaign uses.
        for page, filed_as in (("Ashtyn Kennedy", "Kimberly Ashtyn Kennedy"),
                               ("Jay Feely", "Thomas James Feely"),
                               ("Zuhdi Jasser", "M. Zuhdi Jasser"),
                               ("J.D. Ford", "James (J.d.) David Ford"),
                               ("Quico Canseco", "Francisco 'Quico' Raul Canseco")):
            person = self.filer("H6AL06168", filed_as)
            cache = self.cache({})
            cache["races"]["H-NC-04-2026"].update(status={"H6AL06168": "nominee"},
                                                  names={"H6AL06168": page})
            results.apply_cache([person], cache)
            self.assertEqual((person["name"], person["fecName"]), (page, filed_as))
        # An initial is not a name anyone goes by.
        person = self.filer("H6AL06168", "Kimberly Ashtyn Kennedy")
        cache = self.cache({})
        cache["races"]["H-NC-04-2026"].update(status={"H6AL06168": "nominee"},
                                              names={"H6AL06168": "K. Kennedy"})
        results.apply_cache([person], cache)
        self.assertEqual(person["name"], "Kimberly Ashtyn Kennedy")

    def test_a_name_the_matcher_settled_keeps_the_pages_hyphen(self):
        # Once the matcher folded surnames (Black Wolf / BLACKWOLF), it
        # settled "Bernadette Greene-Placentia" itself, and the rename that
        # ran only for claimed names put back the FEC's unhyphenated form.
        for page, filed_as in (("Bernadette Greene-Placentia", "Bernadette Greene Placentia"),
                               ("Priscilla Williams-Till", "Priscilla Williams Till")):
            person = self.filer("H4AZ08082", filed_as)
            cache = self.cache({})
            cache["races"]["H-NC-04-2026"].update(status={"H4AZ08082": "nominee"},
                                                  names={"H4AZ08082": page})
            results.apply_cache([person], cache)
            self.assertEqual((person["name"], person["fecName"]), (page, filed_as))
        # And a hyphen the page drops is not taken from the person.
        kept = self.filer("H6GA13001", "Keisha Conyears-Ervin")
        cache = self.cache({})
        cache["races"]["H-NC-04-2026"].update(status={"H6GA13001": "nominee"},
                                              names={"H6GA13001": "Keisha Conyears Ervin"})
        results.apply_cache([kept], cache)
        self.assertEqual(kept["name"], "Keisha Conyears-Ervin")

    def test_an_evidenced_alias_the_matcher_used_is_the_name_shown(self):
        # Florida's "Yen Bailey" is an overrides.RESULT_NAMES alias for
        # "BAILEY, HUY-YEN CAM"; settled by id, it lost the claimed path
        # that used to show it.
        person = self.filer("H4FL02138", "Huy-Yen Cam Bailey", "BAILEY, HUY-YEN CAM")
        cache = self.cache({})
        cache["races"]["H-NC-04-2026"].update(status={"H4FL02138": "nominee"},
                                              names={"H4FL02138": "Yen Bailey"})
        results.apply_cache([person], cache)
        self.assertEqual((person["name"], person["nameVia"]), ("Yen Bailey", "election-page"))

    def test_an_apostrophe_is_part_of_a_surname(self):
        # Florida certifies "Tony D'Arrigo"; the FEC files "D'ARRIGO, TONY
        # C". Split at the apostrophe, "D" read as a middle initial that
        # disagreed with "C", and he matched no one.
        rows = [{"candidate_id": "H4FL13234", "name": "D'ARRIGO, TONY C"},
                {"candidate_id": "H6FL13001", "name": "LUNA, ANNA PAULINA"}]
        found, _ = results.match_names(["Tony D'Arrigo"], rows)
        self.assertEqual(found, {"Tony D'Arrigo": ["H4FL13234"]})
        found, _ = results.match_names(["Tony D’Arrigo"], rows)
        self.assertEqual(found, {"Tony D’Arrigo": ["H4FL13234"]})
        # Only after a one-letter prefix: TX-37's page writes "Ge'Neill
        # Gary", the FEC "GARY, GE'NELL". Joined, the given names disagreed
        # and a primary loser lost her result (it held on "Ge" before).
        rows = [{"candidate_id": "H6TX37026", "name": "GARY, GE'NELL"},
                {"candidate_id": "H6TX37001", "name": "PENA, LAUREN B"}]
        found, _ = results.match_names(["Ge'Neill Gary"], rows)
        self.assertEqual(found, {"Ge'Neill Gary": ["H6TX37026"]})
        self.assertEqual(results._tokens("Megan O’Rourke"), ["megan", "orourke"])
        # A quoted nickname still stands on its own.
        self.assertEqual(results._tokens("HENRY C. 'HANK' SMITH"),
                         ["henry", "c", "hank", "smith"])

    def test_validate_lists_what_is_unsettled(self):
        from kyc import validate
        issues = validate.check_results_pages(
            {"unclear": [("Dongbo Su", "H-IL-09-2026", ["Mark Su"])]})
        self.assertEqual([i.code for i in issues], ["results-name-unresolved"])


class TestAgainstTheRealCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = results.load_cache(ROOT)

    def test_the_cache_is_committed(self):
        self.assertIsNotNone(self.cache, "run: python build_profile_site.py results")

    def test_no_race_was_resolved_before_its_primary(self):
        dates = results.load_dates(ROOT)
        as_of = datetime.date.fromisoformat(self.cache["asOf"])
        for rid, race in self.cache["races"].items():
            if race.get("source") in ("qualified", "certified"):
                continue        # a state's list is the ballot, with or without a primary
            parts = rid.split("-")
            state, office = parts[1], "S" if parts[0] == "S" else "H"
            slot = results.seat_slot(dates, rid)
            self.assertTrue(results.primary_settled({(state, office): slot}, state, office,
                                                    as_of), rid)

    def test_every_status_is_a_known_value(self):
        # Every status the reader writes: the primary's, November's (from the
        # day after Election Day), a qualified list's, and "unlisted" where a
        # state's certified list leaves out someone the page put on the
        # November ballot (rule 77).
        allowed = {results.NOMINEE, results.ELIMINATED, results.WITHDRAWN, results.ADVANCED,
                   results.ELECTED, results.DEFEATED, results.RUNOFF, results.QUALIFIED,
                   results.UNLISTED}
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


class TestAMarkNeedsAFilingAndACount(unittest.TestCase):
    """The read publishes without a person (rules 29, 63). On the night of
    2026-11-04 South Carolina's page named "Peter Griffin" for a minute, Iowa's
    and Colorado's named a winner at 0 reporting and Massachusetts' at 15, and
    North Carolina's and South Carolina's November tables carried a mark over
    empty count columns, their counts only in the infobox."""

    TITLE = "2026 United States Senate election in North Carolina"
    RACE = "S-NC-2026"
    PRIMARIES = (box("Democratic primary results", ("Roy Cooper", 900, True)) + "\n" +
                 box("Republican primary results", ("Michael Whatley", 800, True)))

    def setUp(self):
        self.field = {"candidates": [
            {"candidate_id": "S6NC1", "name": "COOPER, ROY", "state": "NC", "office": "S",
             "party": "DEM"},
            {"candidate_id": "S6NC2", "name": "WHATLEY, MICHAEL", "state": "NC", "office": "S",
             "party": "REP"}]}
        self.dates = {("NC", "S"): {"primary": "2026-03-03", "runoff": None}}

    def infobox(self, *rows, ongoing=None, reporting=None):
        out = ["{{Infobox election", "| election_name = x"]
        if ongoing is not None:
            out.append(f"| ongoing = {ongoing}")
        if reporting is not None:
            out.append(f"| reporting = {reporting}")
        for i, (name, votes) in enumerate(rows, 1):
            out += [f"| nominee{i} = '''[[{name}]]'''",
                    f"| party{i} = Democratic Party (United States)",
                    f"| popular_vote{i} = '''{votes}'''"]
        return "\n".join(out + ["}}"])

    def table(self, *rows):
        """A November table; a row's count may be None, printed empty."""
        out = ["{{Election box begin no change", f"| title = {self.TITLE}", "}}"]
        for name, votes, won in rows:
            kind = "winning candidate" if won else "candidate"
            out += [f"{{{{Election box {kind} with party link no change",
                    "| party = Democratic Party (United States)", f"| candidate = {name}",
                    f"| votes = {'' if votes is None else votes}", "}}"]
        return "\n".join(out + ["{{Election box end}}"])

    def read(self, *parts, today=datetime.date(2026, 11, 4), certified=None, aliases=None,
             logged=None):
        page = "\n\n".join((self.PRIMARIES,) + parts)
        return results.build(self.field, self.dates, today=today,
                             log=(logged.append if logged is not None else lambda *_: None),
                             fetch=lambda t: page if t == self.TITLE else
                             (_ for _ in ()).throw(results.PageMissing(t)),
                             certified=certified, aliases=aliases)

    def status(self, cache):
        return cache["races"][self.RACE]["status"]

    def refused(self, cache):
        return (cache.get("refusedMarks") or {}).get(self.RACE) or []

    AWAITING = {"S6NC1": "nominee", "S6NC2": "nominee"}
    ELECTED = {"S6NC1": "elected", "S6NC2": "defeated"}

    # ---- the name

    def test_a_mark_on_a_name_with_no_filing_concludes_nothing(self):
        logged = []
        cache = self.read(self.table(("Peter Griffin", 900, True), ("Michael Whatley", 800, False)),
                          logged=logged)
        race = cache["races"][self.RACE]
        # The vandal's name wins nothing and stands on no ballot, and the
        # nominee whose row it took is not "withdrawn".
        self.assertEqual(self.status(cache), self.AWAITING)
        self.assertNotIn("Peter Griffin", race["unmatched"])
        self.assertEqual(results.race_summary(cache, self.RACE)["otherElected"], [])
        self.assertEqual([m["name"] for m in self.refused(cache)], ["Peter Griffin"])
        self.assertIn("no filing", self.refused(cache)[0]["why"])
        self.assertTrue(any("[REFUSED]" in line and "Peter Griffin" in line and self.RACE in line
                            for line in logged), logged)

    def test_the_name_may_be_the_filings_in_any_spelling_rule_62_allows(self):
        cache = self.read(self.table(("Roy A. Cooper", 900, True), ("Michael Whatley", 800, False)))
        self.assertEqual(self.status(cache), self.ELECTED)
        self.field["candidates"][0]["name"] = "COOPER, ROY ASBERRY III"
        cache = self.read(self.table(("Roy Cooper", 900, True), ("Michael Whatley", 800, False)))
        self.assertEqual(self.status(cache), self.ELECTED)

    def test_an_alias_from_the_roster_is_a_filing(self):
        self.PRIMARIES = (box("Democratic primary results", ("Buddy Cooper", 900, True)) + "\n" +
                          box("Republican primary results", ("Michael Whatley", 800, True)))
        cache = self.read(self.table(("Buddy Cooper", 900, True), ("Michael Whatley", 800, False)),
                          aliases={self.RACE: [("Buddy Cooper", "S6NC1")]})
        self.assertEqual(self.status(cache), self.ELECTED)

    def test_a_certified_list_entry_stands_for_a_filing(self):
        # American Samoa's delegate: the list names them, no filing does.
        lists = {"NC": {"source": "NC State Board", "url": "https://x", "fetched": "2026-10-17",
                        "complete": False,
                        "races": {self.RACE: [
                            {"name": "Samuel Nofiling", "party": "Green", "kind": "ballot"},
                            {"name": "Michael Whatley", "party": "Republican", "kind": "ballot"}]}}}
        cache = self.read(self.table(("Samuel Nofiling", 900, True), ("Michael Whatley", 800, False)),
                          certified=lists)
        self.assertEqual(results.race_summary(cache, self.RACE)["otherElected"], ["Samuel Nofiling"])
        self.assertEqual(self.refused(cache), [])

    def test_a_list_entry_who_withdrew_stands_for_nothing(self):
        lists = {"NC": {"source": "NC State Board", "url": "https://x", "fetched": "2026-10-17",
                        "complete": False,
                        "races": {self.RACE: [
                            {"name": "Samuel Nofiling", "party": "Green", "kind": "withdrawn"}]}}}
        cache = self.read(self.table(("Samuel Nofiling", 900, True), ("Michael Whatley", 800, False)),
                          certified=lists)
        self.assertEqual(results.race_summary(cache, self.RACE)["otherElected"], [])
        self.assertEqual([m["name"] for m in self.refused(cache)], ["Samuel Nofiling"])

    def test_a_fitting_name_that_fits_two_people_is_refused(self):
        self.field["candidates"].append({"candidate_id": "S6NC3", "name": "COOPER, ROY B",
                                         "state": "NC", "office": "S", "party": "REP"})
        self.field["candidates"][0]["name"] = "COOPER, ROY A"
        cache = self.read(self.table(("Roy Cooper", 900, True), ("Michael Whatley", 800, False)))
        self.assertEqual(results.race_summary(cache, self.RACE)["otherElected"], [])
        self.assertNotIn("elected", self.status(cache).values())
        self.assertEqual([m["name"] for m in self.refused(cache)], ["Roy Cooper"])

    # ---- the count

    def test_a_mark_the_tables_counts_lead_with_stands(self):
        cache = self.read(self.table(("Roy Cooper", 900, True), ("Michael Whatley", 800, False)))
        self.assertEqual(self.status(cache), self.ELECTED)
        self.assertEqual(self.refused(cache), [])

    def test_a_mark_on_someone_the_counts_do_not_lead_with_is_refused(self):
        for votes in ((700, 800), (800, 800)):
            cache = self.read(self.table(("Roy Cooper", votes[0], True),
                                         ("Michael Whatley", votes[1], False)))
            self.assertEqual(self.status(cache), self.AWAITING, votes)
            self.assertIn("do not lead", self.refused(cache)[0]["why"])

    def test_two_marks_are_refused_and_reported(self):
        cache = self.read(self.table(("Roy Cooper", 900, True), ("Michael Whatley", 800, True)))
        self.assertEqual(self.status(cache), self.AWAITING)
        self.assertEqual(sorted(m["name"] for m in self.refused(cache)),
                         ["Michael Whatley", "Roy Cooper"])

    NO_COUNTS = (("Roy Cooper", None, True), ("Michael Whatley", None, False))
    ZERO_COUNTS = (("Roy Cooper", 0, True), ("Michael Whatley", 0, False))

    def test_no_counts_stand_on_the_infobox_when_it_leads_with_them(self):
        # North Carolina's, 2026-11-04: Cooper 2,431,822 to Whatley 1,624,770.
        for rows in (self.NO_COUNTS, self.ZERO_COUNTS):
            cache = self.read(self.table(*rows),
                              self.infobox(("Roy Cooper", "2,431,822"), ("Michael Whatley", "1,624,770")))
            self.assertEqual(self.status(cache), self.ELECTED, rows)

    def test_no_counts_and_no_infobox_counts_conclude_nothing(self):
        for parts in ((self.table(*self.NO_COUNTS),),
                      (self.table(*self.NO_COUNTS), self.infobox(("Roy Cooper", ""), ("Michael Whatley", ""))),
                      (self.table(*self.ZERO_COUNTS), self.infobox(("Roy Cooper", "0"), ("Michael Whatley", "0"))),
                      (self.table(*self.NO_COUNTS), self.infobox(("Roy Cooper", "100"), ("Michael Whatley", "")))):
            cache = self.read(*parts)
            self.assertEqual(self.status(cache), self.AWAITING)
            self.assertIn("no counts", self.refused(cache)[0]["why"])

    def test_an_infobox_leading_with_someone_else_refuses(self):
        cache = self.read(self.table(*self.NO_COUNTS),
                          self.infobox(("Roy Cooper", "100"), ("Michael Whatley", "200")))
        self.assertEqual(self.status(cache), self.AWAITING)

    def test_an_infobox_count_at_little_reporting_or_marked_ongoing_is_no_count(self):
        counts = (("Roy Cooper", "270,896"), ("Michael Whatley", "105,431"))
        for kwargs in ({"reporting": "0"}, {"reporting": "15"}, {"ongoing": "yes"}):
            cache = self.read(self.table(*self.NO_COUNTS), self.infobox(*counts, **kwargs))
            self.assertEqual(self.status(cache), self.AWAITING, kwargs)
        cache = self.read(self.table(*self.NO_COUNTS), self.infobox(*counts, reporting="95", ongoing="no"))
        self.assertEqual(self.status(cache), self.ELECTED)

    def test_a_count_in_a_comment_is_not_shown_and_counts_for_nothing(self):
        box_text = self.infobox(("Roy Cooper", "100"), ("Michael Whatley", "<!-- 200 -->"))
        cache = self.read(self.table(*self.NO_COUNTS), box_text)
        self.assertEqual(self.status(cache), self.AWAITING)

    def test_a_table_with_one_count_and_another_row_blank_is_not_a_count(self):
        cache = self.read(self.table(("Roy Cooper", 900, True), ("Michael Whatley", None, False)))
        self.assertEqual(self.status(cache), self.AWAITING)

    # ---- one person on the whole ballot

    def unopposed(self, kind="unopposed", *others):
        return {"NC": {"source": "NC", "url": "https://x", "fetched": "2026-10-17", "complete": True,
                       "races": {self.RACE: [{"name": "Roy Cooper", "party": "Democratic", "kind": kind},
                                             *others]}}}

    def test_a_list_naming_one_person_needs_no_count(self):
        # Florida prints no unopposed candidate, so no count may ever come.
        self.PRIMARIES = box("Democratic primary results", ("Roy Cooper", 900, True))
        self.field["candidates"].pop()
        cache = self.read(self.table(("Roy Cooper", None, True)), certified=self.unopposed())
        self.assertEqual(self.status(cache)["S6NC1"], "elected")
        self.assertEqual(self.refused(cache), [])

    def test_a_list_naming_anyone_else_needs_a_count(self):
        self.PRIMARIES = box("Democratic primary results", ("Roy Cooper", 900, True))
        for other in ({"name": "Ann Other", "party": "Green", "kind": "ballot"},
                      {"name": "Ann Other", "party": "", "kind": "write-in"}):
            cache = self.read(self.table(("Roy Cooper", None, True)),
                              certified=self.unopposed("ballot", other))
            self.assertNotEqual(self.status(cache).get("S6NC1"), "elected", other)
            self.assertIn("no counts", self.refused(cache)[0]["why"])

    def test_the_page_alone_names_one_person_only_when_nobody_else_is_its_nominee(self):
        self.PRIMARIES = box("Democratic primary results", ("Roy Cooper", 900, True))
        cache = self.read(self.table(("Roy Cooper", None, True)), self.infobox(("Roy Cooper", "")))
        self.assertEqual(self.status(cache)["S6NC1"], "elected")
        # Another party's nominee the November table left off: not alone.
        self.PRIMARIES = (box("Democratic primary results", ("Roy Cooper", 900, True)) + "\n" +
                          box("Republican primary results", ("Michael Whatley", 800, True)))
        cache = self.read(self.table(("Roy Cooper", None, True)))
        self.assertNotEqual(self.status(cache).get("S6NC1"), "elected")
        # Anyone else the infobox names: not alone.
        self.PRIMARIES = box("Democratic primary results", ("Roy Cooper", 900, True))
        cache = self.read(self.table(("Roy Cooper", None, True)),
                          self.infobox(("Roy Cooper", ""), ("Michael Whatley", "")))
        self.assertNotEqual(self.status(cache).get("S6NC1"), "elected")

    # ---- beside the other gates

    def test_before_the_day_after_a_mark_is_not_read_or_refused(self):
        cache = self.read(self.table(("Peter Griffin", None, True), ("Michael Whatley", None, False)),
                          today=datetime.date(2026, 11, 3))
        self.assertEqual(self.refused(cache), [])

    def test_a_refused_read_keeps_the_last_read_of_that_race(self):
        cache = self.read(self.table(*self.NO_COUNTS))
        previous = {"races": {self.RACE: {"status": self.ELECTED}}}
        self.assertEqual(results.carry_refused(cache, previous), [self.RACE])
        self.assertEqual(cache["races"][self.RACE]["status"], self.ELECTED)
        self.assertEqual(results.carry_refused({"refusedMarks": {}}, previous), [])

    def test_validate_names_each_refused_race_to_a_person(self):
        from kyc import validate
        cache = self.read(self.table(("Peter Griffin", 900, True), ("Michael Whatley", 800, False)))
        issues = [i for i in validate.check_results_pages(cache) if i.code == "result-mark-refused"]
        self.assertEqual([i.level for i in issues], ["warn"])
        self.assertIn(self.RACE, issues[0].detail[0])
        self.assertIn("Peter Griffin", issues[0].detail[0])
        self.assertFalse([i for i in validate.check_results_pages(
            self.read(self.table(("Roy Cooper", 900, True), ("Michael Whatley", 800, False))))
            if i.code == "result-mark-refused"])

    def test_the_counts_are_not_the_majority_gates_to_weaken(self):
        # A ranked-choice seat's lead short of a majority stays unread though
        # it leads the table: this guard asks first and the gate still asks.
        boxes = results.parse_boxes(self.table(("Roy Cooper", 45, True), ("Michael Whatley", 30, False),
                                               ("Ann Other", 25, False)))
        kept, refused = results.refuse_marks(boxes, open_primary=False)
        self.assertEqual(refused, [])
        status = results.resolve_race(kept, general_held=True, ranked_choice=True)
        self.assertNotIn(results.ELECTED, status.values())

    def test_a_december_mark_needs_a_count_too(self):
        boxes = results.parse_boxes(box("Runoff results", ("Roy Cooper", 0, True),
                                        ("Michael Whatley", 0, False)))
        kept, refused = results.refuse_marks(boxes, general_runoff=True, round_held=True)
        self.assertEqual([m["name"] for m in refused], ["Roy Cooper"])
        self.assertFalse(any(r["won"] for _t, rows in kept for r in rows))
        # An open primary's two marks must be the two highest counts.
        first = results.parse_boxes(self.table(("Roy Cooper", 40, True), ("Michael Whatley", 20, True),
                                               ("Ann Other", 30, False)))
        kept, refused = results.refuse_marks(first, open_primary=True)
        self.assertEqual(len(refused), 2)
        top = results.parse_boxes(self.table(("Roy Cooper", 40, True), ("Michael Whatley", 30, True),
                                             ("Ann Other", 20, False)))
        self.assertEqual(results.refuse_marks(top, open_primary=True)[1], [])

    # ---- the second reader's findings on the first version (PR #199)

    def lists(self, *names, complete=True):
        return {"NC": {"source": "NC", "url": "https://x", "fetched": "2026-10-17",
                       "complete": complete, "races": {self.RACE: [
                           {"name": n, "party": "Democratic", "kind": "ballot"} for n in names]}}}

    def with_loser(self):
        self.field["candidates"].append(
            {"candidate_id": "S6NC4", "name": "LOSER, LARRY", "state": "NC", "office": "S",
             "party": "DEM"})

    def test_a_whole_lists_ballot_refuses_a_filer_it_does_not_print(self):
        # A vandal who renames a row to a real filer's name passes the filing
        # test: the list is the ballot (rule 77).
        self.with_loser()
        cache = self.read(self.table(("Larry Loser", 900, True), ("Roy Cooper", 800, False),
                                     ("Michael Whatley", 700, False)),
                          certified=self.lists("Roy Cooper", "Michael Whatley"))
        self.assertNotEqual(self.status(cache).get("S6NC4"), "elected")
        self.assertEqual(self.refused(cache)[0]["name"], "Larry Loser")
        self.assertIn("certified list", self.refused(cache)[0]["why"])
        self.assertNotIn("elected", self.status(cache).values())

    def test_a_primary_loser_on_the_same_line_is_refused_a_mark(self):
        self.with_loser()
        self.PRIMARIES = (box("Democratic primary results", ("Roy Cooper", 900, True),
                              ("Larry Loser", 100, False)) + "\n" +
                          box("Republican primary results", ("Michael Whatley", 800, True)))
        cache = self.read(self.table(("Larry Loser", 900, True), ("Roy Cooper", 800, False)))
        self.assertEqual(self.refused(cache)[0]["name"], "Larry Loser")
        self.assertIn("eliminated", self.refused(cache)[0]["why"])
        self.assertNotIn("elected", self.status(cache).values())

    def test_a_primary_loser_on_another_line_may_win(self):
        # New York's fusion lines, a sore loser's own party: another ballot line.
        self.with_loser()
        self.PRIMARIES = (box("Democratic primary results", ("Roy Cooper", 900, True),
                              ("Larry Loser", 100, False)) + "\n" +
                          box("Republican primary results", ("Michael Whatley", 800, True)))
        other = "\n".join([
            "{{Election box begin no change", f"| title = {self.TITLE}", "}}",
            "{{Election box winning candidate with party link no change",
            "| party = Independent politician", "| candidate = Larry Loser", "| votes = 900", "}}",
            "{{Election box candidate with party link no change",
            "| party = Democratic Party (United States)", "| candidate = Roy Cooper", "| votes = 800", "}}",
            "{{Election box end}}"])
        cache = self.read(other)
        self.assertEqual(self.refused(cache), [])
        self.assertEqual(self.status(cache)["S6NC4"], "elected")

    def test_an_infobox_name_with_no_filing_and_no_list_adds_nobody_after_the_count(self):
        logged = []
        cache = self.read(self.infobox(("Peter Griffin", "900"), ("Michael Whatley", "800")),
                          self.table(("Roy Cooper", None, False), ("Michael Whatley", None, False)),
                          logged=logged)
        race = cache["races"][self.RACE]
        self.assertNotIn("Peter Griffin", race["unmatched"])
        self.assertEqual(self.status(cache), self.AWAITING)
        self.assertEqual(cache["refusedNames"][self.RACE][0]["name"], "Peter Griffin")
        self.assertTrue(any("[REFUSED]" in line and "Peter Griffin" in line for line in logged), logged)
        from kyc import validate
        issues = [i for i in validate.check_results_pages(cache) if i.code == "result-name-refused"]
        self.assertEqual([i.level for i in issues], ["warn"])
        self.assertIn("Peter Griffin", issues[0].detail[0])

    def test_an_infobox_name_a_table_or_a_list_holds_stands(self):
        cache = self.read(self.infobox(("Sam Nofiling", "900"), ("Michael Whatley", "800")),
                          self.table(("Sam Nofiling", None, False), ("Michael Whatley", None, False)))
        self.assertIn("Sam Nofiling", cache["races"][self.RACE]["unmatched"])
        cache = self.read(self.infobox(("Sam Nofiling", "900"), ("Michael Whatley", "800")),
                          self.table(("Roy Cooper", None, False), ("Michael Whatley", None, False)),
                          certified=self.lists("Roy Cooper", "Michael Whatley", "Sam Nofiling"))
        self.assertFalse(cache.get("refusedNames"))

    def test_before_the_count_an_infobox_name_is_left_as_it_was(self):
        cache = self.read(self.infobox(("Peter Griffin", "900")), self.table(("Roy Cooper", None, False)),
                          today=datetime.date(2026, 11, 2))
        self.assertFalse(cache.get("refusedNames"))

    def test_reporting_is_the_fields_first_number_whatever_is_around_it(self):
        for said in ("15%<ref>AP</ref>", "15<ref name=x/>", "{{percent|15}}", "~15%", "under 15%", "15 percent"):
            cache = self.read(self.infobox(("Roy Cooper", "900"), ("Michael Whatley", "800"), reporting=said),
                              self.table(("Roy Cooper", None, True), ("Michael Whatley", None, False)))
            self.assertEqual(self.status(cache), self.AWAITING, said)
            self.assertIn("15 reporting", self.refused(cache)[0]["why"], said)
        cache = self.read(self.infobox(("Roy Cooper", "900"), ("Michael Whatley", "800"), reporting="most"),
                          self.table(("Roy Cooper", None, True), ("Michael Whatley", None, False)))
        self.assertEqual(self.status(cache), self.AWAITING)
        self.assertIn("cannot be read", self.refused(cache)[0]["why"])
        self.assertEqual(results._reporting(""), (None, False))

    def test_an_ongoing_count_may_say_so_in_other_words(self):
        for said in ("y", "true", "Yes"):
            cache = self.read(self.infobox(("Roy Cooper", "900"), ("Michael Whatley", "800"), ongoing=said),
                              self.table(("Roy Cooper", None, True), ("Michael Whatley", None, False)))
            self.assertEqual(self.status(cache), self.AWAITING, said)

    def fusion(self, *rows):
        out = ["{{Election box begin no change", f"| title = {self.TITLE}", "}}"]
        for name, party, votes, won in rows:
            kind = "winning candidate" if won else "candidate"
            out += [f"{{{{Election box {kind}", f"| party = {party}", f"| candidate = {name}",
                    f"| votes = {votes}", "}}"]
        return "\n".join(out + ["{{Election box end}}"])

    def test_a_fusion_table_is_led_by_a_persons_total_or_the_sum_of_their_lines(self):
        lines = [("Roy Cooper", "Democratic", 100000, True), ("Roy Cooper", "Working Families", 10000, True),
                 ("Michael Whatley", "Republican", 90000, False), ("Michael Whatley", "Conservative", 12000, False)]
        self.assertEqual(self.status(self.read(self.fusion(*lines))), self.ELECTED)
        # A mark on the larger last line, over fewer votes in all, does not stand.
        wrong = [("Roy Cooper", "Democratic", 100000, False), ("Roy Cooper", "Working Families", 10000, False),
                 ("Michael Whatley", "Republican", 90000, True), ("Michael Whatley", "Conservative", 12000, True)]
        cache = self.read(self.fusion(*wrong))
        self.assertEqual(self.status(cache), self.AWAITING)
        self.assertIn("do not lead", self.refused(cache)[0]["why"])
        # A filled Total row is the person's count.
        total = lines + [("Roy Cooper", "Total", 110000, False), ("Michael Whatley", "Total", 102000, False)]
        self.assertEqual(self.status(self.read(self.fusion(*total))), self.ELECTED)

    def test_a_lone_row_is_not_alone_beside_another_partys_unmarked_primary(self):
        self.PRIMARIES = (box("Democratic primary results", ("Roy Cooper", 900, True)) + "\n" +
                          box("Republican primary results", ("Michael Whatley", 800, False)))
        cache = self.read(self.table(("Roy Cooper", None, True)))
        self.assertNotIn("elected", self.status(cache).values())
        self.assertEqual(self.refused(cache)[0]["name"], "Roy Cooper")
        # One who withdrew is nobody else on the ballot.
        self.PRIMARIES = (box("Democratic primary results", ("Roy Cooper", 900, True)) + "\n" +
                          box("Republican primary results", ("Michael Whatley", 800, False, "withdrawn")))
        self.assertEqual(self.status(self.read(self.table(("Roy Cooper", None, True))))["S6NC1"], "elected")

    def test_a_name_fitting_two_filings_says_so_and_never_no_filing(self):
        self.field["candidates"] += [
            {"candidate_id": "S2NC8", "name": "CLEMMONS, MITCHELL", "state": "NC", "office": "S", "party": "DEM"},
            {"candidate_id": "S6NC9", "name": "CLEMMONS, MITCHELL LEE", "state": "NC", "office": "S", "party": "DEM"}]
        cache = self.read(self.table(("Mitch Clemmons", 900, True), ("Roy Cooper", 800, False)))
        self.assertNotIn("elected", self.status(cache).values())
        self.assertIn("more than one filing", self.refused(cache)[0]["why"])

    def test_a_bold_or_referenced_count_is_a_count(self):
        for votes in ("\'\'\'700\'\'\'", "700<ref>x</ref>", "700"):
            cache = self.read(self.fusion(("Roy Cooper", "Democratic", votes, True),
                                          ("Michael Whatley", "Republican", 600, False)))
            self.assertEqual(self.status(cache), self.ELECTED, votes)



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


class TestSeatsWithNoPrimary(NoGap):
    """American Samoa's and the Northern Mariana Islands' seats hold no
    primary, so the calendar gate had no date to open them on: on results
    night (2026-11-04) neither page was read, and no result could ever reach
    either seat."""

    field = {"candidates": [row("H6AS00101", "ALPHA, ANN", "AS", "H", 0, "REP"),
                            row("H6AS00102", "DELTA, DEE", "AS", "H", 0, "DEM"),
                            row("H6MP00101", "BETA, BEA", "MP", "H", 0, "IND"),
                            row("H6MP00102", "GAMMA, GUS", "MP", "H", 0, "REP")]}
    dates = {("AS", "H"): {"primary": None, "runoff": None},
             ("MP", "H"): {"primary": None, "runoff": None}}
    pages = {
        "AS": box("2026 American Samoa's at-large congressional district election",
                  ("Ann Alpha", 6000, True), ("Dee Delta", 3000, False)),
        "MP": box("2026 Northern Mariana Islands's at-large congressional district election",
                  ("Bea Beta", 3441, False), ("Gus Gamma", 2057, False)),
    }

    def run_build(self, today):
        def fetch(title):
            for state in ("AS", "MP"):
                if title in results.page_titles(state, "H"):
                    return self.pages[state]
            raise results.PageMissing(title)
        return results.build(self.field, self.dates, today=today, log=lambda *_: None,
                             fetch=fetch)

    def test_the_seats_are_listed_with_their_evidence(self):
        from kyc import overrides
        self.assertEqual(set(overrides.NO_PRIMARY_SEATS), {("AS", "H"), ("MP", "H")})
        self.assertTrue(all(overrides.NO_PRIMARY_SEATS.values()))

    def test_on_election_day_neither_page_is_read(self):
        cache = self.run_build(datetime.date(2026, 11, 3))
        self.assertNotIn("H-AS-00-2026", cache["races"])
        self.assertNotIn("H-MP-00-2026", cache["races"])

    def test_from_the_day_after_the_november_table_decides(self):
        cache = self.run_build(datetime.date(2026, 11, 4))
        self.assertEqual(cache["races"]["H-AS-00-2026"]["status"],
                         {"H6AS00101": "elected", "H6AS00102": "defeated"})
        # No mark yet: both are on the ballot, awaiting the count, never
        # "ballot status not known".
        self.assertEqual(cache["races"]["H-MP-00-2026"]["status"],
                         {"H6MP00101": "nominee", "H6MP00102": "nominee"})
        self.assertNotIn("H-MP-00-2026", cache.get("pending") or [])

    def test_other_seats_still_wait_for_their_primary_date(self):
        self.assertFalse(results.primary_settled(self.dates | {("GU", "H"): {"primary": None}},
                                                 "GU", "H", datetime.date(2026, 11, 4)))


class TestTerritoryDelegatesNeedAMajority(unittest.TestCase):
    """48 U.S.C. 1712 elects the Delegates from Guam and the Virgin Islands
    by a majority, with a runoff on the fourteenth day after. Read by
    plurality, a leader marked short of a majority would have been
    "elected" a fortnight before the runoff (results night, 2026-11-04)."""

    def table(self, votes):
        return box("2026 Guam's at-large congressional district election",
                   ("Ann Alpha", votes[0], True), ("Dee Delta", votes[1], False),
                   ("Ed Epsilon", votes[2], False))

    def resolve(self, state, votes):
        return results.resolve_race(results.parse_boxes(self.table(votes)), general_held=True,
                                    general_runoff=state in results._general_runoffs())

    def test_a_guam_or_virgin_islands_leader_short_of_a_majority_is_not_elected(self):
        for state in ("GU", "VI"):
            self.assertEqual(self.resolve(state, (48, 47, 5))["Ann Alpha"], "nominee", state)
            self.assertEqual(self.resolve(state, (51, 47, 2))["Ann Alpha"], "elected", state)
        # Where a plurality elects, the same mark does.
        self.assertEqual(self.resolve("AS", (48, 47, 5))["Ann Alpha"], "elected")

    def test_the_runoff_dates_are_the_voting_dates_records(self):
        from kyc import overrides
        with open(os.path.join(ROOT, "candidate_profiles_site", "data", "voting_dates.json"),
                  encoding="utf-8") as handle:
            dates = json.load(handle)["states"]
        for state in ("GU", "VI"):
            self.assertEqual(overrides.GENERAL_RUNOFFS[state][0], dates[state]["runoff"]["date"])


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

    def test_two_headings_withdrawn_lists_are_not_one_table(self):
        # New Jersey's Senate page, read 2026-10-17: "Natalie Rivera" under
        # the Republican primary's Withdrawn heading, "Natalie Lynn Rivera"
        # under the independents'. Gathered into one "Withdrawn list" they
        # shared a table, so they were two people who both fitted her one
        # filing (RIVERA, NATALIE) and the filing read "ambiguous" - where
        # main had it "eliminated".
        text = "\n".join([
            "===Republican convention===",
            box("Atlantic County Republican Convention", ("Alex Zdan", 50, True),
                ("Natalie Rivera", 5, False)),
            "====Withdrawn====", "* Natalie Rivera, activist",
            "===Independents===", "====Withdrawn====",
            "* Natalie Lynn Rivera (Together for NJ), activist",
        ])
        boxes = results.parse_boxes(text) + results.candidate_lists(text)
        out = results.resolve_race(boxes)
        # A county convention awards a ballot line, not the primary: losing
        # one does not outrank the Withdrawn list (main read her
        # "eliminated", "Lost the primary", and NJ-7's Megan O'Rourke too).
        self.assertEqual(out, {"Alex Zdan": "nominee", "Natalie Rivera": "withdrawn"})
        rows = [{"candidate_id": "S6NJ00396", "name": "RIVERA, NATALIE"},
                {"candidate_id": "S6NJ00412", "name": "ZDAN, ALEX"}]
        found, ambiguous = results.match_names(list(out), rows)
        self.assertEqual((found["Natalie Rivera"], ambiguous), (["S6NJ00396"], []))
        # A primary's loss still stands over a Withdrawn list.
        text = "\n".join([
            box("Republican primary results", ("Alex Zdan", 50, True), ("Pat Late", 5, False)),
            "====Withdrawn====", "* Pat Late, after the count",
        ])
        boxes = results.parse_boxes(text) + results.candidate_lists(text)
        self.assertEqual(results.resolve_race(boxes)["Pat Late"], "eliminated")
        # Two alike names under one heading are still two people.
        text = "====Withdrawn====\n* Dan Sullivan, a\n* Daniel Sullivan, b\n"
        boxes = results.candidate_lists(text)
        self.assertEqual(results._canonical(boxes)[0][1][1]["name"], "Daniel Sullivan")

    def test_a_piped_link_names_the_article_over_a_bare_one(self):
        # NM-3's primary table links "[[Martin R. Zamora|Martin Zamora]]" and
        # its November box a bare "[[Martin Zamora]]", a redirect. Taking the
        # bare one moved his profile off the article his offices were read
        # from (history-stale).
        text = "\n".join([
            "{{Election box begin no change | title=Republican primary results}}",
            "{{Election box winning candidate with party link|party=Republican Party "
            "|candidate=[[Martin R. Zamora|Martin Zamora]]|votes=10|percentage=100}}",
            "{{Election box end}}",
            "{{Election box begin no change | title=2026 New Mexico's 3rd congressional "
            "district election}}",
            "{{Election box candidate with party link|party=Republican Party "
            "|candidate=[[Martin Zamora]]|votes=0|percentage=0}}",
            "{{Election box end}}",
        ])
        self.assertEqual(results.ballot_articles(results.parse_boxes(text)),
                         {"Martin Zamora": "Martin R. Zamora"})
        # Two bare links: the one titled as the spelling kept (CA-40).
        text = "\n".join([
            "{{Election box begin no change | title=Primary results}}",
            "{{Election box candidate with party link|party=Democratic Party "
            "|candidate=[[Esther Kim-Varet]]|votes=10|percentage=10}}",
            "{{Election box end}}",
        ])
        boxes = results.parse_boxes(text)
        boxes.append((results.ELIMINATED_LIST, [{"name": "Esther Kim Varet", "won": False,
                                                 "withdrawn": False, "votes": None,
                                                 "party": None, "article": "Esther Kim Varet",
                                                 "list": 0}]))
        self.assertEqual(results.ballot_articles(boxes), {"Esther Kim Varet": "Esther Kim Varet"})


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


LA_TITLE = "2026 United States House of Representatives elections in Louisiana"
LA5_NOVEMBER = "2026 Louisiana's 5th congressional district election"
LA5_DECEMBER = "2026 Louisiana's 5th congressional district runoff election"
LA_CALENDAR = {("LA", "H"): {"primary": "2026-11-03", "runoff": "2026-12-12"}}

# (as the page writes them, party, FEC name, FEC id)
LA5_PEOPLE = {
    "echols": ("[[Michael Echols]]", "Republican", "ECHOLS, MICHAEL", "H6LA05101"),
    "moore": ("[[Pat Moore (Louisiana politician)|Patricia Moore]]", "Democratic",
              "MOORE, PATRICIA", "H6LA05102"),
    "cathey": ("[[Stewart Cathey Jr.]]", "Republican", "CATHEY, STEWART JR", "H6LA05103"),
    "cordell": ("Misti Cordell", "Republican", "CORDELL, MISTI", "H6LA05104"),
    "mckay": ("Dan McKay", "Democratic", "MCKAY, DAN", "H6LA05105"),
}
# Filed with the FEC, never on the November ballot.
LA5_ABSENT = ("SMITH, JOHN", "H6LA05199")


def la5_box(title, *rows, total=None):
    """A results box shaped like the real LA-5 one on 2026-10-02.

    Each row is ``(key, votes, won)``; ``votes=None`` is the blank count the
    box carries until election night. *total* is the box's own total line,
    blank by default.
    """
    out = ["{{Election box begin no change", f"| title={title}", "}}"]
    for key, votes, won in rows:
        shown, party = LA5_PEOPLE[key][:2]
        kind = "winning candidate" if won else "candidate"
        out += [f"{{{{Election box {kind} with party link no change",
                f" | party      = {party} Party (United States)",
                f" | candidate  = {shown}",
                f" | votes      = {'' if votes is None else format(votes, ',')}",
                " | percentage = ",
                "}}"]
    out += ["{{Election box total no change",
            f"| votes = {'' if total is None else format(total, ',')}", "}}",
            "{{Election box end}}"]
    return "\n".join(out)


VOTELESS = [(key, None, False) for key in LA5_PEOPLE]
TOP_TWO = [("echols", 40000, True), ("moore", 30000, True), ("cathey", 15000, False),
           ("cordell", 10000, False), ("mckay", 5000, False)]


class TestOpenPrimaryElectionNight(NoGap):
    """LA's House seats from November 3 to December 12 and after.

    The calendar gate used to wait for the runoff date, as it does for a
    party primary, so the site would have shown every Louisiana candidate as
    still running for six weeks after the first round had decided who
    advanced.
    """

    def ids(self, *keys):
        return {LA5_PEOPLE[k][3] for k in keys}

    def run_build(self, today, *tables, log=None):
        field = {"candidates": [row(p[3], p[2], "LA", "H", 5, "DEM" if p[1] == "Democratic"
                                    else "REP") for p in LA5_PEOPLE.values()]
                 + [row(LA5_ABSENT[1], LA5_ABSENT[0], "LA", "H", 5, "DEM")]}
        page = "\n==District 5==\n" + "\n".join(tables) + "\n"
        return results.build(field, LA_CALENDAR, today=today,
                             log=(log.append if log is not None else lambda *_: None),
                             fetch=lambda title: page if title == LA_TITLE else
                             (_ for _ in ()).throw(results.PageMissing(title)))

    def statuses(self, cache):
        status = cache["races"]["H-LA-05-2026"]["status"]
        out = {}
        for key, person in LA5_PEOPLE.items():
            out[key] = status.get(person[3])
        return out

    # -- the calendar
    def test_the_gate_opens_after_the_primary_for_an_open_seat_only(self):
        dates = {**LA_CALENDAR, ("TX", "H"): {"primary": "2026-03-03", "runoff": "2026-12-01"}}
        nov3, nov4 = datetime.date(2026, 11, 3), datetime.date(2026, 11, 4)
        self.assertFalse(results.primary_settled(dates, "LA", "H", nov3, open_seat=True))
        self.assertTrue(results.primary_settled(dates, "LA", "H", nov4, open_seat=True))
        # The party-primary gate is unchanged: the runoff must have happened.
        self.assertFalse(results.primary_settled(dates, "LA", "H", nov4))
        self.assertFalse(results.primary_settled(dates, "TX", "H", nov4))
        self.assertFalse(results.runoff_held(dates, "LA", "H", nov4))
        self.assertFalse(results.runoff_held(dates, "LA", "H", datetime.date(2026, 12, 12)))
        self.assertTrue(results.runoff_held(dates, "LA", "H", datetime.date(2026, 12, 13)))
        self.assertFalse(results.runoff_held({}, "LA", "H", nov4))

    def test_on_primary_day_the_seat_is_still_pending(self):
        cache = self.run_build(datetime.date(2026, 11, 3), la5_box(LA5_NOVEMBER, *TOP_TWO))
        self.assertEqual(cache["races"], {})
        self.assertIn("H-LA-05-2026", cache["pending"])

    # -- November 4: the first round
    def test_before_any_winner_is_marked_nobody_has_a_status(self):
        logged = []
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *VOTELESS),
                               log=logged)
        self.assertEqual(cache["races"], {})          # not settled: no absence inference
        self.assertNotIn("H-LA-05-2026", cache["pending"])
        self.assertFalse(any("[warn]" in line for line in logged))

    def test_the_marked_top_two_go_to_the_runoff_and_the_rest_lost(self):
        # The first round is the November election itself: its top two meet in
        # December, and the rest lost in November (not "lost a primary").
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *TOP_TWO))
        self.assertEqual(self.statuses(cache), {
            "echols": "runoff", "moore": "runoff", "cathey": "defeated",
            "cordell": "defeated", "mckay": "defeated"})
        race = cache["races"]["H-LA-05-2026"]
        self.assertEqual(race["decided"], {"general": False, "parties": ["all"]})
        summary = results.race_summary(cache, "H-LA-05-2026")
        self.assertEqual((summary["nominees"], summary["runoff"], summary["defeated"]),
                         (0, 2, 3))

    def test_a_vote_less_runoff_box_put_up_early_eliminates_nobody(self):
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *TOP_TWO),
                               la5_box(LA5_DECEMBER, ("echols", None, False),
                                       ("moore", None, False)))
        self.assertEqual(self.statuses(cache)["echols"], "runoff")
        self.assertEqual(self.statuses(cache)["moore"], "runoff")

    def test_a_runoff_winner_before_the_runoff_date_is_not_read(self):
        cache = self.run_build(datetime.date(2026, 11, 20), la5_box(LA5_NOVEMBER, *TOP_TWO),
                               la5_box(LA5_DECEMBER, ("echols", 1, True), ("moore", 0, False)))
        self.assertEqual(self.statuses(cache)["moore"], "runoff")

    def test_one_winner_with_a_majority_is_elected_outright(self):
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(
            LA5_NOVEMBER, ("echols", 55000, True), ("moore", 30000, False),
            ("cathey", 15000, False)))
        out = self.statuses(cache)
        self.assertEqual((out["echols"], out["moore"], out["cathey"]),
                         ("elected", "defeated", "defeated"))

    def test_a_majority_is_of_every_vote_the_table_counts(self):
        # Louisiana elects outright only with a majority of the votes cast.
        # A table that names three of its candidates and counts the rest in
        # its total gives the leader 55% of the named rows and 46% of the
        # vote: that is a December 12 general election, not a win.
        rows = [("echols", 55000, True), ("moore", 30000, False), ("cathey", 15000, False)]
        logged = []
        cache = self.run_build(datetime.date(2026, 11, 4),
                               la5_box(LA5_NOVEMBER, *rows, total=120000), log=logged)
        self.assertEqual(cache["races"], {})
        self.assertTrue(any("[warn] H-LA-05-2026" in line for line in logged))
        # The same table whose total is its rows' sum elects the leader.
        cache = self.run_build(datetime.date(2026, 11, 4),
                               la5_box(LA5_NOVEMBER, *rows, total=100000))
        out = self.statuses(cache)
        self.assertEqual((out["echols"], out["moore"], out["cathey"]),
                         ("elected", "defeated", "defeated"))

    def test_a_marked_top_two_is_in_the_december_round_whatever_the_total(self):
        cache = self.run_build(datetime.date(2026, 11, 4),
                               la5_box(LA5_NOVEMBER, *TOP_TWO, total=100000))
        out = self.statuses(cache)
        self.assertEqual((out["echols"], out["moore"], out["cathey"]),
                         ("runoff", "runoff", "defeated"))

    def test_the_december_round_reads_as_louisianas_general_election(self):
        # The status the results give the two is "runoff"; the words a
        # reader sees are the race's own (share.py and KYC.raceStatus): the
        # December 12 general election, never Georgia's runoff (rule 75).
        from kyc import races as races_mod, share
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *TOP_TWO))
        race = {"id": "H-LA-05-2026", "state": "LA", "chamber": "House", "year": 2026}
        race.update(races_mod.ballot_kind(race))
        self.assertEqual((race["primaryKind"], race["generalRunoff"]), ("open", "2026-12-12"))
        filer = {"id": LA5_PEOPLE["moore"][3], "fecCandidateId": LA5_PEOPLE["moore"][3],
                 "isCandidate": True, "state": "LA", "chamber": "House", "districtNum": 5,
                 "party": "Democrat", "raceId": "H-LA-05-2026"}
        winner = {"id": LA5_PEOPLE["echols"][3], "fecCandidateId": LA5_PEOPLE["echols"][3],
                  "isCandidate": True, "state": "LA", "chamber": "House", "districtNum": 5,
                  "party": "Republican", "raceId": "H-LA-05-2026"}
        results.apply_cache([filer, winner], cache)
        self.assertEqual(filer["raceStatus"], "runoff")
        races = {race["id"]: race}
        self.assertEqual(share.status_words(filer, {}, races, "2026-11-05"),
                         "In the December 12 general election")
        self.assertEqual(share.status_words(filer, {}, races, "2026-12-13"),
                         "Ran in the December 12 general election: awaiting result")
        # A majority on November 3 is a win in November.
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(
            LA5_NOVEMBER, ("echols", 55000, True), ("moore", 45000, False), total=100000))
        results.apply_cache([winner], cache)
        self.assertEqual(share.status_words(winner, {}, races, "2026-11-05"),
                         "Elected in November")
        self.assertNotIn("decidedIn", cache["races"]["H-LA-05-2026"])
        self.assertNotIn("raceStatusDecided", winner)

    def test_the_december_general_elections_result_is_said_as_its_own(self):
        # The review of PR #170: once the December 12 table marks its
        # winner, the two read "Elected in November" and "Lost the November
        # election". The cache says which two the December round decided,
        # and its date; the rest lost on November 3.
        from kyc import races as races_mod, share
        cache = self.run_build(datetime.date(2026, 12, 13), la5_box(LA5_NOVEMBER, *TOP_TWO),
                               la5_box(LA5_DECEMBER, ("echols", 60000, True),
                                       ("moore", 40000, False)))
        out = self.statuses(cache)
        self.assertEqual((out["echols"], out["moore"], out["cathey"]),
                         ("elected", "defeated", "defeated"))
        late = cache["races"]["H-LA-05-2026"]["decidedIn"]
        self.assertEqual((late["date"], late["open"]), ("2026-12-12", True))
        self.assertEqual(sorted(late["ids"]),
                         sorted([LA5_PEOPLE["echols"][3], LA5_PEOPLE["moore"][3]]))
        race = {"id": "H-LA-05-2026", "state": "LA", "chamber": "House", "year": 2026}
        race.update(races_mod.ballot_kind(race))
        people = [{"id": LA5_PEOPLE[key][3], "fecCandidateId": LA5_PEOPLE[key][3],
                   "isCandidate": True, "state": "LA", "chamber": "House", "districtNum": 5,
                   "party": LA5_PEOPLE[key][1].replace("Democratic", "Democrat"),
                   "raceId": "H-LA-05-2026"}
                  for key in ("echols", "moore", "cathey")]
        results.apply_cache(people, cache)
        self.assertEqual(people[0]["raceStatusDecided"], {"date": "2026-12-12", "open": True})
        self.assertEqual([share.status_words(p, {}, {race["id"]: race}, "2026-12-13")
                          for p in people],
                         ["Elected on December 12", "Lost the December 12 general election",
                          "Lost the November election"])

    def test_winners_that_are_not_a_complete_result_decide_nothing(self):
        for rows in (
            [("echols", 45000, True), ("moore", 35000, False), ("cathey", 20000, False)],
            [("echols", None, True), ("moore", None, False)],
            [("echols", 40, True), ("moore", 30, True), ("cathey", 30, True)],
        ):
            logged = []
            cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *rows),
                                   log=logged)
            self.assertEqual(cache["races"], {}, rows)
            # Short of a count, the mark is refused before this reads it.
            self.assertTrue(any("H-LA-05-2026" in line and ("[warn]" in line or "[REFUSED]" in line)
                                for line in logged), rows)

    def test_a_filer_absent_from_the_first_round_is_unlisted(self):
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *TOP_TWO))
        filer = {"id": LA5_ABSENT[1], "fecCandidateId": LA5_ABSENT[1], "isCandidate": True,
                 "state": "LA", "chamber": "House", "districtNum": 5, "party": "Democrat"}
        member = {"id": "L000999", "fecCandidateId": LA5_PEOPLE["echols"][3],
                  "isCandidate": False, "state": "LA", "chamber": "House", "districtNum": 5,
                  "party": "Republican", "seatUp2026": True, "seekingReelection2026": False}
        results.apply_cache([filer, member], cache)
        self.assertEqual(filer["raceStatus"], "unlisted")
        self.assertTrue(results.on_ballot(member))
        self.assertTrue(member["seekingReelection2026"])     # in the runoff for their seat

    # -- December 13: the runoff
    def test_after_the_runoff_its_table_decides(self):
        cache = self.run_build(datetime.date(2026, 12, 13), la5_box(LA5_NOVEMBER, *TOP_TWO),
                               la5_box(LA5_DECEMBER, ("echols", 52000, True),
                                       ("moore", 48000, False)))
        self.assertEqual(self.statuses(cache), {
            "echols": "elected", "moore": "defeated", "cathey": "defeated",
            "cordell": "defeated", "mckay": "defeated"})

    def test_after_the_runoff_an_unreported_runoff_leaves_both_in_it(self):
        cache = self.run_build(datetime.date(2026, 12, 13), la5_box(LA5_NOVEMBER, *TOP_TWO),
                               la5_box(LA5_DECEMBER, ("echols", None, False),
                                       ("moore", None, False)))
        out = self.statuses(cache)
        self.assertEqual((out["echols"], out["moore"], out["mckay"]),
                         ("runoff", "runoff", "defeated"))

    # -- the cache
    def test_a_cache_built_after_the_first_round_keeps_its_results(self):
        cache = self.run_build(datetime.date(2026, 11, 4), la5_box(LA5_NOVEMBER, *TOP_TWO))
        kept = results.respect_open_primaries(cache)
        self.assertIn("H-LA-05-2026", kept["races"])

    def test_a_cache_built_without_the_override_still_gives_them_up(self):
        cache = {"asOf": "2026-11-04", "cycle": 2026, "pending": [],
                 "races": {"H-LA-05-2026": {"status": {"X": "nominee"}}},
                 "dates": {"LA-H": {"primary": "2026-08-07", "runoff": None}}}
        cache = results.respect_open_primaries(cache)
        self.assertEqual(cache["races"], {})
        self.assertEqual(cache["pending"], ["H-LA-05-2026"])


class TestResultsCommandUsesTheScreenedField(unittest.TestCase):
    """``results`` matches against the field the build uses, not the raw one.

    The raw FEC register lists Senate filings from states with no 2026 seat
    up (Arizona, California, New York ...); read raw, each became a phantom
    "race" in the cache's pending list.
    """

    def test_phantom_races_never_reach_the_resolver(self):
        import contextlib
        import io
        import types
        from unittest import mock

        from kyc import candidates, cli
        from kyc.profiles import build_profiles, screen_field
        from kyc import legislators, sources

        raw_field = candidates.load_cache(ROOT)
        raw_races = {candidates.race_id(r) for r in raw_field["candidates"]} - {None}
        raw = sources.load_all(ROOT)
        profiles, _ = build_profiles(raw, snapshot=legislators.load_snapshot(ROOT))
        screened = screen_field(raw_field, profiles, raw["record"])
        real = {candidates.race_id(r) for r in screened["candidates"]} - {None}
        phantom = raw_races - real
        self.assertTrue(phantom, "the committed field has no phantom races to screen")

        seen = {}

        def fake_build(field, dates, **kw):
            seen["field"] = field
            return {"races": {}, "pending": []}

        args = types.SimpleNamespace(root=ROOT, check=False, verbose=False)
        with mock.patch.object(results, "fetch_dates", return_value={}), \
                mock.patch.object(results, "build", side_effect=fake_build), \
                mock.patch.object(results, "save_cache", return_value="(not written)"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli._results(args), 0)
        given = {candidates.race_id(r) for r in seen["field"]["candidates"]} - {None}
        self.assertEqual(given & phantom, set())
        self.assertEqual(given, real)
        self.assertEqual([r["candidate_id"] for r in seen["field"]["candidates"]],
                         [r["candidate_id"] for r in screened["candidates"]])


class TestPartyRunoffGateUnchanged(NoGap):
    """A Georgia/Texas-style party runoff still waits for the runoff date."""

    title = "2026 United States House of Representatives elections in Georgia"
    dates = {("GA", "H"): {"primary": "2026-05-19", "runoff": "2026-06-16"}}
    field = {"candidates": [row("H6GA05201", "ALPHA, ANN", "GA", "H", 5, "REP"),
                            row("H6GA05202", "BETA, BEA", "GA", "H", 5, "REP"),
                            row("H6GA05203", "GAMMA, CY", "GA", "H", 5, "REP")]}
    first = box("Republican primary results", ("Ann Alpha", 40, True),
                ("Bea Beta", 35, True), ("Cy Gamma", 25, False))
    runoff = box("Republican primary runoff results", ("Ann Alpha", 45, False),
                 ("Bea Beta", 55, True))

    def run_build(self, today, *tables):
        page = "\n==District 5==\n" + "\n".join(tables) + "\n"
        return results.build(self.field, self.dates, today=today, log=lambda *_: None,
                             fetch=lambda t: page if t == self.title else
                             (_ for _ in ()).throw(results.PageMissing(t)))

    def test_between_primary_and_runoff_the_race_is_pending(self):
        self.assertFalse(results.open_primary("GA", "H"))
        cache = self.run_build(datetime.date(2026, 6, 1), self.first)
        self.assertEqual(cache["races"], {})
        self.assertEqual(cache["pending"], ["H-GA-05-2026"])

    def test_after_the_runoff_the_runoff_table_decides(self):
        cache = self.run_build(datetime.date(2026, 6, 17), self.first, self.runoff)
        self.assertEqual(cache["races"]["H-GA-05-2026"]["status"],
                         {"H6GA05201": "eliminated", "H6GA05202": "nominee",
                          "H6GA05203": "eliminated"})

    def test_after_the_runoff_date_an_untabulated_runoff_leaves_both_advanced(self):
        cache = self.run_build(datetime.date(2026, 6, 17), self.first)
        self.assertEqual(cache["races"]["H-GA-05-2026"]["status"],
                         {"H6GA05201": "advanced", "H6GA05202": "advanced",
                          "H6GA05203": "eliminated"})


class TestGeneralElectionNight(NoGap):
    """After Election Day the November table decides, and only its marked winner."""

    title = "2026 United States House of Representatives elections in Georgia"
    dates = {("GA", "H"): {"primary": "2026-05-19", "runoff": "2026-06-16"}}
    field = {"candidates": [row("H6GA05201", "ALPHA, ANN", "GA", "H", 5, "REP"),
                            row("H6GA05202", "BETA, BEA", "GA", "H", 5, "REP"),
                            row("H6GA05204", "DELTA, DEE", "GA", "H", 5, "DEM"),
                            row("H6GA05205", "EPSILON, ED", "GA", "H", 5, "LIB")]}
    primaries = "\n".join([
        box("Republican primary results", ("Ann Alpha", 60, True), ("Bea Beta", 40, False)),
        box("Democratic primary results", ("Dee Delta", 100, True)),
    ])
    GENERAL = "2026 Georgia's 5th congressional district election"

    def general(self, alpha=False, delta=False, votes=None):
        # Georgia elects by a majority (O.C.G.A. 21-2-501): the one marked
        # holds one, unless the case sets the count.
        a, d = votes or ((52, 45) if alpha and not delta else (45, 52) if delta and not alpha
                         else (49, 48))
        return box(self.GENERAL, ("Ann Alpha", a, alpha), ("Dee Delta", d, delta),
                   ("Ed Epsilon", 100 - a - d, False))

    def test_a_georgia_leader_marked_short_of_a_majority_is_not_elected(self):
        # The review of PR #168: a mark on 49.4% beside a Libertarian's
        # 2.5% is a December runoff to come, not a win - nobody is elected
        # or defeated until the runoff's table appears.
        cache = self.run_build(datetime.date(2026, 11, 4),
                               self.general(alpha=True, votes=(49, 48)))
        self.assertEqual(self.statuses(cache), {
            "alpha": "nominee", "beta": "eliminated", "delta": "nominee", "epsilon": "nominee"})
        # A write-in line of its own counts toward the whole: 50 of 101.
        text = (self.general(alpha=True, votes=(50, 47)).replace(
            "{{Election box end}}",
            "{{Election box write-in with party link|votes=1}}\n{{Election box end}}"))
        out = results.resolve_race(results.parse_boxes(text), general_held=True,
                                   general_runoff=True)
        self.assertEqual(out["Ann Alpha"], "nominee")
        # Once its runoff table is up, the November table's two are in it.
        cache = self.run_build(datetime.date(2026, 11, 4),
                               self.general(alpha=True, votes=(49, 48)),
                               box("Runoff results", ("Ann Alpha", 0, False),
                                   ("Dee Delta", 0, False)))
        self.assertEqual((self.statuses(cache)["alpha"], self.statuses(cache)["epsilon"]),
                         ("runoff", "defeated"))

    def run_build(self, today, *tables):
        page = "\n==District 5==\n" + self.primaries + "\n" + "\n".join(tables) + "\n"
        return results.build(self.field, self.dates, today=today, log=lambda *_: None,
                             fetch=lambda t: page if t == self.title else
                             (_ for _ in ()).throw(results.PageMissing(t)))

    def statuses(self, cache):
        names = {"H6GA05201": "alpha", "H6GA05202": "beta", "H6GA05204": "delta",
                 "H6GA05205": "epsilon"}
        return {names[c]: s for c, s in cache["races"]["H-GA-05-2026"]["status"].items()}

    def test_general_day_is_the_tuesday_after_the_first_monday(self):
        self.assertEqual(results.general_day(2026), datetime.date(2026, 11, 3))
        self.assertEqual(results.general_day(2027), datetime.date(2027, 11, 2))
        self.assertFalse(results.general_held(datetime.date(2026, 11, 3)))
        self.assertTrue(results.general_held(datetime.date(2026, 11, 4)))

    def test_on_election_day_a_marked_winner_is_not_read(self):
        # Polls are still open somewhere; an early mark is not a result.
        cache = self.run_build(datetime.date(2026, 11, 3), self.general(alpha=True))
        self.assertEqual(self.statuses(cache), {
            "alpha": "nominee", "beta": "eliminated", "delta": "nominee", "epsilon": "nominee"})

    def test_the_marked_winner_is_elected_and_the_rest_of_the_ballot_lost(self):
        cache = self.run_build(datetime.date(2026, 11, 4), self.general(alpha=True))
        # The primary loser keeps their primary result; they were never on it.
        self.assertEqual(self.statuses(cache), {
            "alpha": "elected", "beta": "eliminated", "delta": "defeated",
            "epsilon": "defeated"})
        summary = results.race_summary(cache, "H-GA-05-2026")
        self.assertEqual((summary["elected"], summary["defeated"], summary["nominees"]),
                         (1, 2, 0))

    def test_with_no_marked_winner_the_count_is_continuing(self):
        cache = self.run_build(datetime.date(2026, 11, 4), self.general())
        self.assertEqual(self.statuses(cache), {
            "alpha": "nominee", "beta": "eliminated", "delta": "nominee", "epsilon": "nominee"})

    def test_two_marked_winners_decide_nothing(self):
        cache = self.run_build(datetime.date(2026, 11, 4), self.general(alpha=True, delta=True))
        self.assertEqual(self.statuses(cache)["alpha"], "nominee")
        self.assertEqual(self.statuses(cache)["delta"], "nominee")

    def test_a_general_runoff_holds_the_top_two_and_the_rest_lost(self):
        cache = self.run_build(datetime.date(2026, 11, 4), self.general(),
                               box("Runoff results", ("Ann Alpha", 0, False),
                                   ("Dee Delta", 0, False)))
        self.assertEqual(self.statuses(cache), {
            "alpha": "runoff", "beta": "eliminated", "delta": "runoff", "epsilon": "defeated"})
        self.assertEqual(results.race_summary(cache, "H-GA-05-2026")["runoff"], 2)

    def test_a_runoff_winner_before_the_runoff_date_is_not_read(self):
        cache = self.run_build(datetime.date(2026, 12, 1), self.general(),
                               box("Runoff results", ("Ann Alpha", 0, False),
                                   ("Dee Delta", 1, True)))
        self.assertEqual((self.statuses(cache)["alpha"], self.statuses(cache)["delta"]),
                         ("runoff", "runoff"))

    def test_after_the_runoff_its_winner_is_elected(self):
        cache = self.run_build(datetime.date(2026, 12, 2), self.general(),
                               box("Runoff results", ("Ann Alpha", 40, False),
                                   ("Dee Delta", 60, True)))
        self.assertEqual(self.statuses(cache), {
            "alpha": "defeated", "beta": "eliminated", "delta": "elected", "epsilon": "defeated"})

    def test_a_result_the_runoff_decided_says_so_never_november(self):
        # The review of PR #170: the runoff's winner read "Elected in
        # November" and its loser "Lost the November election". The cache
        # says which two the December 1 runoff decided; November's loser
        # (Epsilon) lost in November.
        from kyc import share
        cache = self.run_build(datetime.date(2026, 12, 2), self.general(),
                               box("Runoff results", ("Ann Alpha", 40, False),
                                   ("Dee Delta", 60, True)))
        race = cache["races"]["H-GA-05-2026"]
        self.assertEqual(race["decidedIn"], {"date": "2026-12-01", "open": False,
                                             "ids": ["H6GA05201", "H6GA05204"]})
        people = [{"id": cid, "fecCandidateId": cid, "isCandidate": True, "state": "GA",
                   "chamber": "House", "districtNum": 5, "party": "Democrat",
                   "raceId": "H-GA-05-2026"} for cid in ("H6GA05201", "H6GA05204", "H6GA05205")]
        results.apply_cache(people, cache)
        alpha, delta, epsilon = people
        self.assertEqual(delta["raceStatusDecided"], {"date": "2026-12-01", "open": False})
        self.assertNotIn("raceStatusDecided", epsilon)
        words = [share.status_words(p, {}, {}, "2026-12-02") for p in people]
        self.assertEqual(words, ["Lost the December 1 runoff", "Won the December 1 runoff",
                                 "Lost the November election"])
        # A win in November is November's.
        cache = self.run_build(datetime.date(2026, 11, 4), self.general(alpha=True))
        self.assertNotIn("decidedIn", cache["races"]["H-GA-05-2026"])

    def test_a_party_runoff_titled_without_its_party_is_not_the_general_runoff(self):
        # June's Republican runoff between Alpha and Beta, boxed as "Runoff
        # results". Beta was never on the November ballot, so it is not one.
        cache = self.run_build(datetime.date(2026, 11, 4), self.general(alpha=True),
                               box("Runoff results", ("Ann Alpha", 55, True),
                                   ("Bea Beta", 45, False)))
        self.assertEqual(self.statuses(cache), {
            "alpha": "elected", "beta": "eliminated", "delta": "defeated", "epsilon": "defeated"})

    def test_a_nominee_who_withdrew_after_nomination_stays_withdrawn(self):
        text = "\n".join([
            box("Democratic primary results", ("Dee Delta", 9, True)),
            box(self.GENERAL, ("Ann Alpha", 9, True), ("Dee Delta", 4, False)),
            "===Withdrew after nomination===", "*Dee Delta",
        ])
        section = text
        boxes = results.parse_boxes(section) + results.candidate_lists(section)
        before = results.resolve_race(boxes)
        after = results.resolve_race(boxes, general_held=True)
        self.assertEqual(before["Dee Delta"], "withdrawn")
        self.assertEqual(after["Dee Delta"], "withdrawn")
        self.assertEqual(after["Ann Alpha"], "elected")

    def test_only_a_state_with_general_runoffs_reads_one(self):
        self.assertIn("GA", results._general_runoffs())
        boxes = results.parse_boxes(self.general() + "\n" + box(
            "Runoff results", ("Ann Alpha", 0, False), ("Dee Delta", 0, False)))
        out = results.resolve_race(boxes, general_held=True, general_runoff=False)
        self.assertNotIn("runoff", out.values())

    def test_a_member_who_won_or_lost_was_seeking_reelection(self):
        cache = self.run_build(datetime.date(2026, 11, 4), self.general(delta=True))
        member = {"id": "m", "name": "Ann Alpha", "party": "Republican", "state": "GA",
                  "chamber": "House", "district": "GA-5", "districtNum": 5,
                  "raceId": "H-GA-05-2026", "isCandidate": False,
                  "seatUp2026": True, "seekingReelection2026": False,
                  "fecCandidateId": "H6GA05201",
                  "status": "Incumbent"}
        results.apply_cache([member], cache)
        self.assertEqual(member["raceStatus"], "defeated")
        self.assertTrue(member["seekingReelection2026"])


NOVEMBER_2024 = os.path.join(FIXTURES, "november_2024")


def november_2024(name):
    """A 2024 page's results tables for one seat, as fetched for the
    November rehearsal of 2026-11-01 (the revision is in the file's first
    line)."""
    with open(os.path.join(NOVEMBER_2024, name), encoding="utf-8") as handle:
        return "\n" + handle.read()


def as_2024():
    """Read a 2024 page as that cycle's: a table titled with another year
    than the cycle's is another election's."""
    from unittest import mock
    return mock.patch.object(results, "CYCLE", 2024)


class TestNovember2024Rehearsal(unittest.TestCase):
    """The November reading run over 2024's pages, as they stood the morning
    after Election Day and once certified."""

    def test_a_november_table_titled_by_its_seat_is_read(self):
        # "Alabama's 1st congressional district, 2024": no word "election",
        # so the table was never read - 83 seats of the 2024 pages, in
        # eleven states, whose winners were marked on the certified revision.
        with as_2024():
            statuses = page_statuses(november_2024("al_1_certified.txt"), 1,
                                     has_runoff=True, general_held=True)
            self.assertEqual(results._stage("Florida's 7th congressional district, 2024"),
                             "general")
            self.assertEqual(results._stage("2024 Delaware's at-large congressional district"),
                             "general")
        self.assertEqual(statuses, {"Barry Moore": "elected", "Tom Holmes": "defeated",
                                    "Jerry Carl": "eliminated"})
        # A primary or a runoff for the seat stays what it is.
        self.assertEqual(results._stage(
            "Alabama's 2nd congressional district Republican primary runoff, 2026"), "runoff")
        self.assertEqual(results._stage(
            "Alabama's 2nd congressional district Democratic primary, 2026"), "primary")
        self.assertEqual(results._stage("Florida's 7th congressional district, 2026"), "general")
        self.assertIsNone(results._stage("Statehood Green results"))
        # A past seat's own page is read by its words (kyc/seat_history.py).
        self.assertEqual(results._stage(
            "Alabama's 2nd congressional district Republican primary runoff, 2024",
            cycle=None), "runoff")

    def test_a_table_titled_with_another_year_is_another_election(self):
        # The review of PR #168: a 2024-titled table left above TX-28's
        # unmarked 2026 table was read as this November's, and its mark
        # elected the 2024 winner.
        for title in ("Texas's 28th congressional district, 2024",
                      "2024 Texas's 28th congressional district election",
                      "2024 United States Senate election in Texas",
                      "Republican primary results, 2024"):
            self.assertIsNone(results._stage(title), title)
        # A party's assembly places names on the primary ballot; neither it
        # nor a seat-titled one is the general.
        self.assertIsNone(results._stage(
            "Colorado's 5th congressional district Republican assembly"))
        self.assertIsNone(results._stage("Republican assembly results"))
        old = box("Texas's 28th congressional district, 2024",
                  ("Henry Cuellar", 100, True), ("Jay Furman", 80, False))
        new = box("2026 Texas's 28th congressional district election",
                  ("Henry Cuellar", 0, False), ("Tano Tijerina", 0, False))
        out = results.resolve_race(results.parse_boxes(old + "\n" + new), general_held=True)
        self.assertEqual(out, {"Henry Cuellar": "nominee", "Tano Tijerina": "nominee"})

    def test_a_ranked_choice_final_round_with_a_majority_is_read(self):
        # Maine's 2nd district, as certified: one table, the final round,
        # Golden 50.35%.
        with as_2024():
            statuses = page_statuses(november_2024("me_2_certified.txt"), 2,
                                     general_held=True, ranked_choice=True)
        self.assertEqual((statuses["Jared Golden"], statuses["Austin Theriault"]),
                         ("elected", "defeated"))

    def test_ranked_choice_first_choices_are_a_lead_not_a_win(self):
        # Maine's 2nd district in 2018: Poliquin led the first choices with
        # 46.3% and Golden won the tabulated rounds. A page that marks the
        # first-choice leader before the rounds decides nothing.
        first = box("Maine's 2nd congressional district, 2026",
                    ("Bruce Poliquin", 134184, True), ("Jared Golden", 132013, False),
                    ("Tiffany Bond", 16552, False), ("Will Hoar", 6875, False))
        boxes = results.parse_boxes(first)
        self.assertEqual(results.resolve_race(boxes, general_held=True)["Bruce Poliquin"],
                         "elected")                       # elsewhere a plurality wins
        statuses = results.resolve_race(boxes, general_held=True, ranked_choice=True)
        self.assertEqual(set(statuses.values()), {"nominee"})
        # A table with no counts at all (marked the morning after) is no
        # majority either.
        unknown = results.parse_boxes(first.replace("134,184", "").replace("132,013", ""))
        self.assertEqual(results.resolve_race(unknown, general_held=True,
                                              ranked_choice=True)["Bruce Poliquin"], "nominee")
        # Once the final round is up, the same mark on the first choices is
        # read beside it.
        final = box("Maine's 2nd congressional district, 2026 (final round)",
                    ("Jared Golden", 142440, True), ("Bruce Poliquin", 138931, False))
        both = results.parse_boxes(first.replace("winning candidate", "candidate") + "\n" + final)
        statuses = results.resolve_race(both, general_held=True, ranked_choice=True)
        self.assertEqual((statuses["Jared Golden"], statuses["Bruce Poliquin"],
                          statuses["Tiffany Bond"]), ("elected", "defeated", "defeated"))

    def test_a_withdrawn_bullet_is_read_to_the_name(self):
        # Two bullets on 2026's pages, read on 2026-11-01, that reach the
        # November reading once Louisiana's page decides: no comma before the
        # words about LA-5's Dixon McMakin, a comma inside KY-6's aside.
        text = "\n".join([
            "===Withdrawn===",
            "*[[Dixon McMakin]] (Republican) [[Louisiana State House of Representatives|"
            "state representative]] from the 68th district (2024–present)<ref>x</ref>",
            "*Adam Perez Arquette ''(endorsed Alvarado, remained on ballot)''<ref>y</ref>",
            "*[[John Smith (politician)|John Smith]] Jr., businessman",
            "*[[Jane Roe]] (Democratic)",
        ])
        names = [r["name"] for title, rows in results.candidate_lists(text) for r in rows]
        self.assertEqual(names, ["Dixon McMakin", "Adam Perez Arquette", "John Smith Jr.",
                                 "Jane Roe"])

    def test_the_build_counts_maine_and_alaska_by_ranked_choice(self):
        self.assertEqual(set(results.RANKED_CHOICE), {"ME", "AK"})

    def test_ranked_choice_counts_every_vote_and_every_nominee(self):
        # The review of PR #168, on the shape of Alaska's at-large table on
        # 2026-11-01: two named rows and two "TBD" slots. A mark on Begich
        # beside Hill alone, with no count for the slots, is no majority.
        tbd = ("{{Election box candidate with party link|party=TBD|candidate=TBD|votes=}}\n"
               "{{Election box candidate with party link|party=TBD|candidate=TBD|votes=}}\n")
        table = box("2026 Alaska's at-large congressional district election",
                    ("Nick Begich", 120000, True), ("Bill Hill", 10000, False))
        slots = table.replace("{{Election box end}}", tbd + "{{Election box end}}")
        out = results.resolve_race(results.parse_boxes(slots), general_held=True,
                                   ranked_choice=True)
        self.assertEqual(set(out.values()), {"nominee"})
        # Maine, a Senate table: Collins 300,000, Platner 290,000 and 20,000
        # write-ins in a line of its own - 49.2% of the ballots counted.
        maine = box("2026 United States Senate election in Maine",
                    ("Susan Collins", 300000, True), ("Graham Platner", 290000, False))
        write_in = maine.replace(
            "{{Election box end}}",
            "{{Election box write-in with party link|votes=20,000}}\n{{Election box end}}")
        out = results.resolve_race(results.parse_boxes(write_in), general_held=True,
                                   ranked_choice=True)
        self.assertEqual(out["Susan Collins"], "nominee")
        # Its own total says the same where the write-ins are not a line.
        total = maine.replace(
            "{{Election box end}}",
            "{{Election box total no change|votes=610,000|percentage=100}}\n"
            "{{Election box end}}")
        out = results.resolve_race(results.parse_boxes(total), general_held=True,
                                   ranked_choice=True)
        self.assertEqual(out["Susan Collins"], "nominee")
        # Elsewhere a plurality wins: the same table elects her.
        self.assertEqual(results.resolve_race(results.parse_boxes(total),
                                              general_held=True)["Susan Collins"], "elected")
        # A November table that leaves out a nominee the infobox names
        # decides nothing either, whatever the count.
        boxes = results.parse_boxes(table) + [(results.INFOBOX_TITLE, [
            {"name": n, "won": False, "withdrawn": False, "votes": None, "party": None,
             "article": None} for n in ("Nick Begich", "Eric Hafner")])]
        out = results.resolve_race(boxes, general_held=True, ranked_choice=True)
        self.assertEqual(out["Nick Begich"], "nominee")
        # With every nominee counted and a majority of the whole, it does.
        whole = table.replace("{{Election box end}}",
                              "{{Election box total no change|votes=140,000}}\n"
                              "{{Election box end}}")
        out = results.resolve_race(results.parse_boxes(whole), general_held=True,
                                   ranked_choice=True)
        self.assertEqual((out["Nick Begich"], out["Bill Hill"]), ("elected", "defeated"))

    def test_before_election_day_the_seat_titled_table_is_the_ballot(self):
        with as_2024():
            statuses = page_statuses(november_2024("al_1_certified.txt"), 1, has_runoff=True)
        self.assertEqual(statuses, {"Barry Moore": "nominee", "Tom Holmes": "nominee",
                                    "Jerry Carl": "eliminated"})


class TestAnotherSpellingOnThePage(NoGap):
    """ID-1, 2026-10-14: the November table writes "Sarah Zabel Peterson", the
    infobox "Sarah Zabel"; the filing is ZABEL, SARAH."""

    title = "2026 United States House of Representatives elections in Idaho"
    dates = {("ID", "H"): {"primary": "2026-05-19", "runoff": None}}
    field = {"candidates": [row("H8ID01124", "FULCHER, RUSS", "ID", "H", 1, "REP"),
                            row("H2ID01192", "PETERSON, KAYLEE", "ID", "H", 1, "DEM"),
                            row("H6ID01318", "ZABEL, SARAH", "ID", "H", 1, "IND")]}

    def run_build(self, page):
        return results.build(self.field, self.dates, today=datetime.date(2026, 10, 14),
                             log=lambda *_: None,
                             fetch=lambda t: page if t == self.title else
                             (_ for _ in ()).throw(results.PageMissing(t)))

    def test_the_infobox_spelling_finds_the_filing(self):
        page = "\n".join([
            "\n==District 1==",
            "{{Infobox election", "| nominee1 = [[Russ Fulcher]]",
            "| party1 = Republican Party (United States)", "| nominee2 = Kaylee Peterson",
            "| party2 = Democratic Party (United States)", "| nominee3 = Sarah Zabel",
            "| party3 = Independent politician", "}}",
            box("Republican primary results", ("Russ Fulcher", 9, True)),
            box("Democratic primary results", ("Kaylee Peterson", 9, True)),
            box("2026 Idaho's 1st congressional district election", ("Russ Fulcher", 0, False),
                ("Kaylee Peterson", 0, False), ("Sarah Zabel Peterson", 0, False)),
        ])
        race = self.run_build(page)["races"]["H-ID-01-2026"]
        self.assertEqual(race["status"], {"H8ID01124": "nominee", "H2ID01192": "nominee",
                                          "H6ID01318": "nominee"})
        self.assertEqual(race["unmatched"], {})


class TestValidateUncalled(unittest.TestCase):
    def codes(self, as_of, statuses):
        from kyc import validate
        cache = {"asOf": as_of, "races": {"S-AK-2026": {
            "decided": {"general": True, "parties": ["all"]}, "status": statuses}}}
        return [i.code for i in validate.check_results_pages(cache)]

    def test_a_race_still_uncalled_days_later_is_reported(self):
        self.assertIn("general-uncalled", self.codes("2026-11-07", {"a": "nominee", "b": "nominee"}))
        self.assertNotIn("general-uncalled", self.codes("2026-11-05", {"a": "nominee"}))
        self.assertNotIn("general-uncalled",
                         self.codes("2026-11-07", {"a": "elected", "b": "defeated"}))


class TestValidateElected(unittest.TestCase):
    race = {"id": "H-GA-05-2026", "state": "GA", "settled": True, "incumbentIds": [],
            "candidateIds": ["a", "b"], "results": {}}

    def codes(self, statuses, other=()):
        from kyc import validate
        people = [{"id": pid, "name": name, "party": "Democrat", "raceStatus": status,
                   "raceId": "H-GA-05-2026", "isCandidate": True}
                  for pid, name, status in statuses]
        race = dict(self.race, results={"otherElected": list(other)})
        return [i.code for i in validate.check_results(people, [race])]

    def test_one_winner_is_fine(self):
        codes = self.codes([("a", "Ann One", "elected"), ("b", "Bo Two", "defeated")])
        self.assertNotIn("multiple-elected", codes)
        self.assertNotIn("settled-race-without-nominee", codes)

    def test_two_winners_are_an_error(self):
        self.assertIn("multiple-elected",
                      self.codes([("a", "Ann One", "elected"), ("b", "Bo Two", "elected")]))
        self.assertIn("multiple-elected",
                      self.codes([("a", "Ann One", "elected")], other=["Cy Three"]))

    def test_a_nominee_beside_a_result_is_reported(self):
        # The November rehearsal of 2026-11-01: a certified list's candidate
        # the page's November table left out read "Awaiting result" under
        # "Won by".
        self.assertIn("nominee-beside-result",
                      self.codes([("a", "Ann One", "elected"), ("b", "Bo Two", "nominee")]))
        self.assertIn("nominee-beside-result",
                      self.codes([("a", "Ann One", "runoff"), ("b", "Bo Two", "nominee")]))
        self.assertNotIn("nominee-beside-result",
                         self.codes([("a", "Ann One", "nominee"), ("b", "Bo Two", "nominee")]))
        # A name the results hold with no profile here counts as much.
        from kyc import validate
        people = [{"id": "a", "name": "Ann One", "party": "Democrat", "raceStatus": "elected",
                   "raceId": "H-GA-05-2026", "isCandidate": True},
                  {"id": "b", "name": "Bo Two", "party": "Democrat", "raceStatus": "defeated",
                   "raceId": "H-GA-05-2026", "isCandidate": True}]
        race = dict(self.race, results={"otherNominees": ["Cy Unprofiled"]})
        found = [i for i in validate.check_results(people, [race])
                 if i.code == "nominee-beside-result"]
        self.assertEqual(len(found), 1)
        self.assertIn("Cy Unprofiled", " ".join(found[0].detail))

    def test_a_loser_with_no_profile_is_not_awaiting_the_result(self):
        # Results night 2026-11-04: otherNominees names everyone on the
        # November ballot with no profile, the defeated included, and the
        # check called Bray (NC) and Hackett (SC) still waiting.
        from kyc import validate
        people = [{"id": "a", "name": "Ann One", "party": "Democrat", "raceStatus": "elected",
                   "raceId": "H-GA-05-2026", "isCandidate": True}]
        for key in ("otherDefeated", "otherElected"):
            race = dict(self.race, results={"otherNominees": ["Cy Unprofiled"],
                                            key: ["Cy Unprofiled"]})
            codes = [i.code for i in validate.check_results(people, [race])]
            self.assertNotIn("nominee-beside-result", codes)
        race = dict(self.race, results={"otherNominees": ["Cy Unprofiled", "Di Waiting"],
                                        "otherDefeated": ["Cy Unprofiled"]})
        found = [i for i in validate.check_results(people, [race])
                 if i.code == "nominee-beside-result"]
        self.assertEqual(len(found), 1)
        self.assertNotIn("Cy Unprofiled", " ".join(found[0].detail))
        self.assertIn("Di Waiting", " ".join(found[0].detail))

    def test_the_summary_names_unprofiled_losers(self):
        cache = {"races": {"S-SC-2026": {"status": {}, "unmatched": {
            "Mark Hackett": "defeated", "Eve Won": "elected", "Fay Wait": "nominee"}}}}
        summary = results.race_summary(cache, "S-SC-2026")
        self.assertEqual(summary["otherDefeated"], ["Mark Hackett"])
        self.assertIn("Mark Hackett", summary["otherNominees"])


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


class TestElectionPageWords(unittest.TestCase):
    """What a race's own page says about each candidate, and where their
    campaign lives: read from the page, never inferred."""

    SECTION = "\n".join([
        "==Democratic primary==",
        "===Candidates===",
        "====Nominee====",
        "* [[Jane Doe (politician)|Jane Doe]], molecular biologist and "
        "[[Democratic Socialists of America|DSA]] member<ref>{{cite web|url=x}}</ref>",
        "====Eliminated in primary====",
        "* John Roe, attorney",
        "====Withdrawn====",
        "* Sam Poe, businessman",
        "====Declined====",
        "* Pat Moe, state senator",
        "===Independents===",
        "====Declared====",
        "* Alex Lowe, retired teacher ''(running as an independent)''",
        "* Rio Phillips, cybersecurity technician ''(previously ran as a [[Democratic Party "
        "(United  States)|Democrat]])''<ref>{{Cite web |title=Candidates|url=x}}</ref>",
        "* Chris Bowe",
        "== External links ==",
        "'''Official campaign websites for candidates'''",
        "*[https://www.janedoe.com/ Jane Doe (D)]",
        '*[https://lowe2026.org/ Alex "Al" Lowe (I)]',
        "*[https://example.com/ Official site]",
    ])

    def test_only_ballot_headings_are_read_and_only_what_follows_the_name(self):
        self.assertEqual(results.candidate_descriptors(self.SECTION), {
            "Jane Doe": "molecular biologist and DSA member",
            "Alex Lowe": "retired teacher",
            # A note whose link holds a bracket is dropped whole, link and all.
            "Rio Phillips": "cybersecurity technician",
        })

    def test_a_citation_cut_off_at_the_line_end_is_not_a_career(self):
        # MI-13 and TN-9: the <ref> runs on to the next line, so the bullet's
        # own line holds a template that never closes; it showed on the page.
        section = "\n".join([
            "===Candidates===",
            "====Declared====",
            "* Ann Coe, state representative from the 11th district (2023–present)"
            "<ref>{{cite news |last=Kamisar |first=Ben |title=Rep. loses",
            "|url=x}}</ref>",
            "* Bo Doe, state senator and candidate in 2002{{cite web|title=Run for office",
            "* Cy Foe, farmer<ref name=a/> and {{nowrap|county commissioner}}",
        ])
        self.assertEqual(results.candidate_descriptors(section), {
            "Ann Coe": "state representative from the 11th district (2023–present)",
            "Bo Doe": "state senator and candidate in 2002",
            "Cy Foe": "farmer and county commissioner",
        })

    def test_the_external_links_list_gives_each_candidates_site(self):
        sites = results.campaign_sites(self.SECTION)
        self.assertEqual(sites["Jane Doe"], "https://www.janedoe.com/")
        # Keyed as the page spells the name, which is how its ballot lines are
        # matched to filings; a label that is no one's name attaches to no one.
        self.assertEqual(sites['Alex "Al" Lowe'], "https://lowe2026.org/")

    def cache(self):
        return {"asOf": "2026-09-13", "races": {"H-TX-18-2026": {
            "status": {"H6TX18232": "nominee", "H2TX18001": "nominee"},
            "about": {"H6TX18232": "molecular biologist", "H2TX18001": "incumbent"},
            "site": {"H6TX18232": "https://www.janedoe.com/"},
        }}}

    def test_a_filed_candidate_gets_the_description_credited_to_the_page(self):
        filed = {"id": "H6TX18232", "fecCandidateId": "H6TX18232", "isCandidate": True,
                 "source": "fec-field", "state": "TX", "chamber": "House (Candidate)",
                 "districtNum": 18, "previous_professions": "No data",
                 "quality": {"previous_professions": "unknown"}}
        results.apply_cache([filed], self.cache())
        self.assertEqual(filed["previous_professions"], "molecular biologist")
        self.assertEqual(filed["fieldSources"], {"previous_professions": "election-page"})
        # The page's site is held back until `enrich` has read it.
        self.assertEqual(filed["electionPageSite"], "https://www.janedoe.com/")
        self.assertNotIn("campaignSite", filed)

    def test_a_members_roster_fields_are_never_touched(self):
        member = {"id": "H2TX18001", "fecCandidateId": "H2TX18001", "isCandidate": False,
                  "state": "TX", "chamber": "House", "districtNum": 18,
                  "previous_professions": "Attorney", "quality": {}}
        results.apply_cache([member], self.cache())
        self.assertEqual(member["previous_professions"], "Attorney")
        self.assertNotIn("fieldSources", member)


class TestNamedMinorParty(unittest.TestCase):
    """The FEC files Joseph Tache as "Other"; the ballot names his party."""

    def cache(self, key, label):
        return {"asOf": "2026-09-13", "races": {"S-MA-2026": {
            "status": {"S6MA00288": "nominee"}, "party": {"S6MA00288": key},
            "label": {"S6MA00288": label}}}}

    def profile(self, party="Other"):
        return {"id": "FEC_S6MA00288", "fecCandidateId": "S6MA00288", "isCandidate": True,
                "source": "fec-field", "name": "Joseph Tache", "party": party,
                "state": "MA", "chamber": "Senate (Candidate)", "districtNum": None}

    def test_the_ballot_party_replaces_a_party_the_filing_never_named(self):
        tache = self.profile()
        results.apply_cache([tache], self.cache("party for socialism and liberation",
                                                "Party for Socialism and Liberation"))
        self.assertEqual(tache["party"], "Party for Socialism and Liberation")
        self.assertEqual(tache["fecParty"], "Other")
        self.assertNotIn("ballotLine", tache)     # it is his party, not a second line

    def test_a_named_party_is_never_replaced_by_a_minor_line(self):
        # Jose Vega is a Democrat on the "Speak The Truth" line: shown as a
        # line beside the nomination, never as his party.
        vega = self.profile(party="Democrat")
        results.apply_cache([vega], self.cache("speak the truth", "Speak The Truth"))
        self.assertEqual(vega["party"], "Democrat")
        self.assertEqual(vega["ballotLine"], "Speak The Truth")


class TestAGeneralRunoffNeedsTheNovemberCount(NoGap):
    """Georgia's general runoff: rule 63's marks test did not reach it. A name
    with no filing stood in the runoff with a real nominee defeated, and a table
    an editor prepared settled a race with no count behind it."""

    TITLE = "2026 United States Senate election in Georgia"
    RACE = "S-GA-2026"
    PRIMARIES = (box("Democratic primary results", ("Jon Ossoff", 900, True)) + "\n" +
                 box("Republican primary results", ("Mike Collins", 800, True)))

    def setUp(self):
        super().setUp()
        self.field = {"candidates": [
            {"candidate_id": "S8GA1", "name": "OSSOFF, JON", "state": "GA", "office": "S", "party": "DEM"},
            {"candidate_id": "S6GA2", "name": "COLLINS, MIKE", "state": "GA", "office": "S", "party": "REP"},
            {"candidate_id": "S6GA3", "name": "LIB, LENA", "state": "GA", "office": "S", "party": "LIB"}]}
        self.dates = {("GA", "S"): {"primary": "2026-05-19", "runoff": "2026-06-16"}}

    def read(self, *tables, logged=None):
        page = "\n\n".join((self.PRIMARIES,) + tables)
        return results.build(self.field, self.dates, today=datetime.date(2026, 11, 4),
                             log=(logged.append if logged is not None else lambda *_: None),
                             fetch=lambda t: page if t == self.TITLE else
                             (_ for _ in ()).throw(results.PageMissing(t)))

    def refused(self, cache):
        return (cache.get("refusedMarks") or {}).get(self.RACE) or []

    def test_a_runoff_the_november_counts_send_them_to_stands(self):
        cache = self.read(box(self.TITLE, ("Jon Ossoff", 490, False), ("Mike Collins", 480, False),
                              ("Lena Lib", 30, False)),
                          box("Runoff results", ("Jon Ossoff", 0, False), ("Mike Collins", 0, False)))
        self.assertEqual(self.refused(cache), [])
        status = cache["races"][self.RACE]["status"]
        self.assertEqual((status["S8GA1"], status["S6GA2"], status["S6GA3"]),
                         ("runoff", "runoff", "defeated"))

    def test_a_name_with_no_filing_stands_in_no_runoff(self):
        cache = self.read(box(self.TITLE, ("Jon Ossoff", 490, False), ("Peter Griffin", 480, False),
                              ("Lena Lib", 30, False)),
                          box("Runoff results", ("Jon Ossoff", 0, False), ("Peter Griffin", 0, False)))
        race = cache["races"][self.RACE]
        self.assertNotIn("Peter Griffin", race["unmatched"])
        self.assertNotIn(race["status"]["S6GA2"], ("defeated", "runoff"))
        self.assertIn("Peter Griffin", [m["name"] for m in self.refused(cache)])

    def test_an_empty_runoff_table_settles_nothing(self):
        logged = []
        cache = self.read(box(self.TITLE, ("Jon Ossoff", 0, False), ("Mike Collins", 0, False),
                              ("Lena Lib", 0, False)),
                          box("Runoff results", ("Jon Ossoff", 0, False), ("Mike Collins", 0, False)),
                          logged=logged)
        status = cache["races"][self.RACE]["status"]
        self.assertNotIn("runoff", status.values())
        self.assertNotIn("defeated", status.values())
        self.assertEqual(len(self.refused(cache)), 2)
        self.assertTrue(any("[REFUSED]" in line for line in logged), logged)

    def test_a_runoff_beside_a_majority_settles_nothing(self):
        cache = self.read(box(self.TITLE, ("Jon Ossoff", 600, False), ("Mike Collins", 300, False),
                              ("Lena Lib", 100, False)),
                          box("Runoff results", ("Jon Ossoff", 0, False), ("Mike Collins", 0, False)))
        self.assertNotIn("runoff", cache["races"][self.RACE]["status"].values())
        # Nor the two who are not the highest.
        cache = self.read(box(self.TITLE, ("Jon Ossoff", 400, False), ("Mike Collins", 300, False),
                              ("Lena Lib", 350, False)),
                          box("Runoff results", ("Jon Ossoff", 0, False), ("Mike Collins", 0, False)))
        self.assertNotIn("runoff", cache["races"][self.RACE]["status"].values())


class TestAQualifiedListVouchesForAName(NoGap):
    """Rule 64's list has a certified list's standing: Louisiana's holds people
    with no FEC filing, and refusing one who reached the top two would have held
    a true call for ever, with a false reason."""

    def read(self, *rows):
        field = {"candidates": [row("H6LA2A", "CARTER, TROY", "LA", "H", 2, "DEM")]}
        page = "\n==District 2==\n" + box("2026 Louisiana's 2nd congressional district election", *rows)
        listed = {"H-LA-02-2026": [
            {"name": "Troy Carter", "party": "Democratic", "filed": "", "withdrew": False},
            {"name": 'Renada "Honey" Collins', "party": "Republican", "filed": "", "withdrew": False},
            {"name": "Gone Candidate", "party": "Republican", "filed": "", "withdrew": True}]}
        return results.build(field, LA_CALENDAR, today=datetime.date(2026, 11, 4), log=lambda *_: None,
                             fetch=lambda t: page if t == LA_TITLE else
                             (_ for _ in ()).throw(results.PageMissing(t)),
                             qualified=(listed, {"source": "LA SoS"}))

    def test_someone_on_the_list_may_reach_the_top_two_with_no_filing(self):
        cache = self.read(("Troy Carter", 120000, True), ('Renada "Honey" Collins', 60000, True),
                          ("Third Person", 10000, False))
        self.assertFalse(cache["refusedMarks"], cache["refusedMarks"])
        race = cache["races"]["H-LA-02-2026"]
        self.assertEqual(race["status"]["H6LA2A"], "runoff")

    def test_someone_off_the_list_may_not(self):
        cache = self.read(("Troy Carter", 120000, True), ("Peter Griffin", 60000, True))
        self.assertIn("no filing", cache["refusedMarks"]["H-LA-02-2026"][0]["why"])

    def test_someone_the_list_says_withdrew_may_not(self):
        cache = self.read(("Troy Carter", 120000, True), ("Gone Candidate", 60000, True))
        self.assertTrue(cache["refusedMarks"]["H-LA-02-2026"])


if __name__ == "__main__":
    unittest.main()
