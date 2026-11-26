"""The day each legislative chamber's new term begins (rule 106), and what
the pages say once it has begun while the roster may not have caught up."""

import copy
import datetime
import unittest

from kyc import ballot2026, legislative_terms as L, terms_begin


def made_up(rule, day, words="the first day of December following their election",
            quote="The terms of members begin on the first day of December following their "
                  "election.", kind="on", chambers=("upper", "lower"), at="",
            source="https://www.ndlegis.gov/constit/a04.pdf"):
    return L._record(chambers, rule, words, day, "Made-up Const. art. 1", ((source, (quote,)),),
                     kind=kind, at=at)


def one_state(code, record, gaps=None):
    """A table of one state's record and every other chamber a gap, so the
    coverage check passes and only *record* is under test."""
    terms = {code: (record,)}
    gaps = dict(gaps or {})
    for pair in L.up_chambers():
        if pair[0] != code or pair[1] not in record["chambers"]:
            gaps.setdefault(pair, ("made up", None))
    return terms, gaps


class TheTable(unittest.TestCase):
    def test_the_table_keeps_its_rules(self):
        self.assertEqual(L.problems(), [])
        self.assertTrue(L.check())

    def test_every_chamber_on_the_ballot_has_a_day_or_a_gap_and_none_both(self):
        covered = {(code, which) for code, records in L.TERMS.items() for r in records
                   for which in r["chambers"]}
        self.assertEqual(covered | set(L.GAPS), set(L.up_chambers()))
        self.assertFalse(covered & set(L.GAPS))
        # The chambers the ballot table puts on the ballot, counted from it.
        self.assertEqual(len(L.up_chambers()), ballot2026.stats()["chambersUp"])

    def test_the_counts_are_what_the_table_holds(self):
        stats = L.stats()
        self.assertEqual(stats["on"] + stats["by"] + stats["gaps"], len(L.up_chambers()))
        self.assertEqual(stats["by"], sum(len(r["chambers"]) for rs in L.TERMS.values()
                                          for r in rs if r["kind"] == "by"))

    def test_the_rules_are_counted_on_the_calendar(self):
        self.assertEqual(L.count(L.ELECTION_DAY), datetime.date(2026, 11, 3))
        self.assertEqual(L.count(L.DAY_AFTER), datetime.date(2026, 11, 4))
        # The Monday after the election (South Carolina), the first Monday in
        # December (California's leads), the third Tuesday in January.
        self.assertEqual(L.count(("after", "Monday", L.ELECTION_DAY)), datetime.date(2026, 11, 9))
        self.assertEqual(L.count(("nth", 1, "Monday", 12)), datetime.date(2026, 12, 7))
        self.assertEqual(L.count(("nth", 3, "Tuesday", 1)), datetime.date(2027, 1, 19))
        self.assertEqual(L.count(L.FIRST_DAY_DECEMBER), datetime.date(2026, 12, 1))
        self.assertFalse(L.counted(L.ELECTION_DAY))
        self.assertTrue(L.counted(L.DAY_AFTER))
        self.assertFalse(L.counted(L.FIRST_DAY_JANUARY))

    def test_florida_takes_office_upon_election_and_alaska_by_statute(self):
        fl = L.for_page("FL", "upper")
        self.assertEqual((fl["day"], fl["from"], fl["words"]), ("2026-11-03", "2026-11-04",
                                                                "upon election"))
        ak = L.for_page("AK", "lower")
        # AS 24.05.080 is the law that "otherwise provides" than the
        # constitution's fourth Monday.
        self.assertEqual(ak["day"], "2027-01-19")
        self.assertIn("24.05.080", ak["source"])
        self.assertEqual(L.for_page("PA", "lower")["day"], "2026-12-01")
        self.assertEqual(L.for_page("CO", "upper")["kind"], "by")
        self.assertEqual(L.for_page("CO", "upper")["from"], "2027-01-14")
        # Texas's day is the session's, at noon: begun only from the next day.
        self.assertEqual(L.for_page("TX", "lower")["from"], "2027-01-13")
        # California's terms commence on the first Monday in December
        # (art. IV, s.2(a)(3)), counted: December 7, 2026.
        ca = L.for_page("CA", "lower")
        self.assertEqual((ca["day"], ca["from"], ca["counted"]), ("2026-12-07", "2026-12-07", True))
        self.assertEqual(L.for_page("CA", "upper")["day"], "2026-12-07")
        self.assertIsNone(L.for_page("LA", "lower"))
        self.assertIsNone(L.for_page("NH", "lower"))
        self.assertIn("Access Denied", L.gap_for("NH", "lower")["why"])

    def test_a_wrong_day_is_refused(self):
        terms, gaps = one_state("ND", made_up(L.FIRST_DAY_DECEMBER, "2026-12-02"))
        self.assertTrue(any("the rule counts 2026-12-01" in p for p in L.problems(terms, gaps)))
        terms, gaps = one_state("ND", made_up(L.FIRST_DAY_DECEMBER, "2026-12-01"))
        self.assertEqual(L.problems(terms, gaps), [])

    def test_an_entry_without_its_words_address_or_day_read_is_refused(self):
        record = made_up(L.FIRST_DAY_DECEMBER, "2026-12-01")
        for field, value, needle in (("words", "", "no citation or no words"),
                                     ("cite", "", "no citation or no words"),
                                     ("read", "", "no day read"),
                                     ("sources", (), "no source")):
            broken = dict(record, **{field: value})
            terms, gaps = one_state("ND", broken)
            self.assertTrue(any(needle in p for p in L.problems(terms, gaps)), field)
        no_quote = dict(record, sources=(("https://www.ndlegis.gov/constit/a04.pdf", ()),))
        terms, gaps = one_state("ND", no_quote)
        self.assertTrue(any("quotes nothing" in p for p in L.problems(terms, gaps)))

    def test_the_words_are_the_provisions_own(self):
        record = made_up(L.FIRST_DAY_DECEMBER, "2026-12-01", words="December 1")
        terms, gaps = one_state("ND", record)
        self.assertTrue(any("not the provision's" in p for p in L.problems(terms, gaps)))

    def test_a_compiled_copy_of_the_law_is_no_source(self):
        for host in ("https://www.law.cornell.edu/x", "https://law.justia.com/x",
                     "https://ballotpedia.org/x", "http://www.ndlegis.gov/constit/a04.pdf"):
            record = made_up(L.FIRST_DAY_DECEMBER, "2026-12-01", source=host)
            terms, gaps = one_state("ND", record)
            self.assertTrue(any("not an official host" in p or "not an https link" in p
                                for p in L.problems(terms, gaps)), host)

    def test_a_chamber_with_neither_a_day_nor_a_gap_fails(self):
        gaps = dict(L.GAPS)
        gaps.pop(("TN", "lower"))
        self.assertIn("TN lower: on the 2026 ballot with neither a day nor a gap",
                      L.problems(L.TERMS, gaps))
        gaps = {**L.GAPS, ("TN", "lower"): ("", None)}
        self.assertTrue(any("a gap without why" in p for p in L.problems(L.TERMS, gaps)))

    def test_a_chamber_not_on_the_ballot_and_two_records_fail(self):
        terms = dict(L.TERMS, LA=(made_up(L.FIRST_DAY_DECEMBER, "2026-12-01"),))
        self.assertTrue(any("LA upper: not on the 2026 ballot" in p
                            for p in L.problems(terms, L.GAPS)))
        terms = dict(L.TERMS)
        terms["FL"] = terms["FL"] + (made_up(L.FIRST_DAY_DECEMBER, "2026-12-01",
                                             chambers=("upper",)),)
        self.assertIn("FL upper: two records", L.problems(terms, L.GAPS))
        gaps = {**L.GAPS, ("FL", "upper"): ("made up", None)}
        self.assertIn("FL upper: both a day and a gap", L.problems(L.TERMS, gaps))

    def test_noon_is_recorded_where_the_provision_names_it(self):
        record = made_up(L.FIRST_DAY_DECEMBER, "2026-12-01",
                         quote="The terms of members begin at noon on the first day of December "
                               "following their election.")
        terms, gaps = one_state("ND", record)
        self.assertTrue(any("names noon" in p for p in L.problems(terms, gaps)))
        terms, gaps = one_state("ND", dict(record, at="noon"))
        self.assertEqual(L.problems(terms, gaps), [])

    def test_a_gap_that_was_not_read_names_where_a_person_reads_it(self):
        for (code, which), (why, source) in L.GAPS.items():
            self.assertTrue(source or "https://" in why, (code, which))

    def test_a_day_before_the_election_is_refused(self):
        record = made_up(("election", -1), "2026-11-02")
        terms, gaps = one_state("ND", record)
        self.assertTrue(any("before the election" in p for p in L.problems(terms, gaps)))


class TheRosterBehind(unittest.TestCase):
    TERM = {"day": "2026-11-03", "from": "2026-11-04"}

    def test_behind_until_a_person_records_it_caught_up(self):
        self.assertTrue(L.roster_behind("FL", "upper", self.TERM, "2026-11-17", current={}))
        seen = {("FL", "upper"): {"rosterRead": "2026-11-20", "seen": "x", "source": "y",
                                  "day": "2026-11-21"}}
        # Caught up for the read the person looked at and every later one.
        self.assertFalse(L.roster_behind("FL", "upper", self.TERM, "2026-11-20", current=seen))
        self.assertFalse(L.roster_behind("FL", "upper", self.TERM, "2026-11-24", current=seen))
        # An older roster is not the one they looked at.
        self.assertTrue(L.roster_behind("FL", "upper", self.TERM, "2026-11-19", current=seen))
        # A look at a roster read before the term began says nothing of it.
        early = {("FL", "upper"): dict(seen[("FL", "upper")], rosterRead="2026-11-03")}
        self.assertTrue(L.roster_behind("FL", "upper", self.TERM, "2026-11-24", current=early))
        self.assertFalse(L.roster_behind("FL", "upper", None, "2026-11-24", current={}))

    def test_a_caught_up_entry_needs_its_evidence_and_a_day(self):
        good = {("FL", "upper"): {"rosterRead": "2026-11-20", "seen": "x", "source": "y",
                                  "day": "2026-11-21"}}
        self.assertEqual(L.current_problems(good), [])
        bad = {("FL", "upper"): {"rosterRead": "2026-11-03"}, ("TN", "lower"): {}}
        found = L.current_problems(bad)
        self.assertTrue(any("TN lower: no day in kyc/legislative_terms.py" in p for p in found))
        self.assertTrue(any("FL upper: no seen" in p for p in found))
        self.assertTrue(any("before the term began" in p for p in found))
        self.assertEqual(L.current_problems(), [])

    def test_begun_on_each_clock(self):
        for code, which, before, after in (("AL", "upper", "2026-11-04", "2026-11-05"),
                                          ("PA", "lower", "2026-11-30", "2026-12-01"),
                                          ("OH", "lower", "2026-12-31", "2027-01-01")):
            term = L.for_page(code, which)
            self.assertFalse(L.begun(term, before) and before < term["from"], code)
            self.assertTrue(L.begun(term, after), code)
        fl = L.for_page("FL", "upper")
        self.assertFalse(L.begun(fl, "2026-11-03"))
        self.assertTrue(L.begun(fl, "2026-11-04"))

    def test_lagging_names_each_chamber_once_its_term_has_begun(self):
        payload = {"states": {
            "FL": {"upper": {"title": "Senate", "seats": 40, "upSeats": 20, "rosterBehind": True,
                             "termBegins": L.for_page("FL", "upper")},
                   "lower": {"title": "House of Representatives", "seats": 120, "upSeats": 120,
                             "rosterBehind": False, "termBegins": L.for_page("FL", "lower")}},
            "OH": {"lower": {"title": "House of Representatives", "seats": 99, "upSeats": 99,
                             "rosterBehind": True, "termBegins": L.for_page("OH", "lower")}}}}
        found = L.lagging(payload, "2026-11-25", "2026-11-17")
        self.assertEqual([(c, w) for c, w, _ in found], [("FL", "upper")])
        self.assertIn("20 of its 40 seats", found[0][2])
        self.assertIn("Nov. 17, 2026", found[0][2])
        later = L.lagging(payload, "2027-01-02", "2026-11-17")
        self.assertEqual([(c, w) for c, w, _ in later], [("FL", "upper"), ("OH", "lower")])

    def test_the_table_is_terms_begins_shape(self):
        for code, records in L.TERMS.items():
            for record in records:
                self.assertTrue(set(record) >= {"chambers", "rule", "words", "day", "cite",
                                                "sources", "kind", "read"}, code)
                self.assertIn(record["kind"], terms_begin.KINDS)


class ThePipeline(unittest.TestCase):
    def test_a_chamber_on_the_ballot_carries_its_day_and_the_roster_behind(self):
        from kyc import stategov
        fl = stategov.legislative_term("FL", "upper", "2026-11-17")
        self.assertEqual(fl["upSeats"], 20)
        self.assertEqual(fl["termBegins"]["day"], "2026-11-03")
        self.assertTrue(fl["rosterBehind"])
        # A gap: its seats on the ballot, no day to say anything from, and
        # the mark that this site has not read it, with the provision a
        # person should read where the gap names one.
        tn = stategov.legislative_term("TN", "lower", "2026-11-17")
        self.assertEqual(tn, {"upSeats": 99, "termUnknown": {}})
        az = stategov.legislative_term("AZ", "lower", "2026-11-17")
        self.assertEqual(az["termUnknown"], {"source": L.gap_for("AZ", "lower")["source"]})
        self.assertNotIn("termBegins", az)
        self.assertNotIn("rosterBehind", az)
        # A chamber not on the 2026 ballot carries nothing.
        self.assertEqual(stategov.legislative_term("LA", "lower", "2026-11-17"), {})
        self.assertEqual(stategov.legislative_term("KS", "upper", "2026-11-17"), {})

    def test_a_person_recorded_caught_up_reads_as_caught_up(self):
        from kyc import overrides, stategov
        saved = dict(overrides.LEGISLATURE_ROSTERS_CURRENT)
        try:
            overrides.LEGISLATURE_ROSTERS_CURRENT[("FL", "upper")] = {
                "rosterRead": "2026-11-20", "seen": "made up", "source": "https://www.flsenate.gov/",
                "day": "2026-11-21"}
            self.assertFalse(stategov.legislative_term("FL", "upper", "2026-11-20")["rosterBehind"])
            self.assertTrue(stategov.legislative_term("FL", "upper", "2026-11-17")["rosterBehind"])
        finally:
            overrides.LEGISLATURE_ROSTERS_CURRENT.clear()
            overrides.LEGISLATURE_ROSTERS_CURRENT.update(saved)

    def test_validate_warns_never_errs(self):
        from kyc import validate
        payload = {"sources": {"openstates": ["Open States", "https://openstates.org/", "2026-11-17"]},
                   "states": {"FL": {"upper": dict(title="Senate", seats=40, upSeats=20,
                                                   rosterBehind=True,
                                                   termBegins=L.for_page("FL", "upper"))}}}
        before = validate.check_legislative_terms(payload, datetime.date(2026, 11, 3))
        after = validate.check_legislative_terms(payload, datetime.date(2026, 11, 4))
        self.assertEqual([i.code for i in before], ["legislature-term-unknown"])
        self.assertEqual([i.code for i in after], ["legislature-roster-behind",
                                                   "legislature-term-unknown"])
        self.assertTrue(all(i.level == "warn" for i in after))
        self.assertEqual(len(after[1].detail), len(L.GAPS))
        self.assertIn("FL Senate", after[0].detail[0])
        caught = copy.deepcopy(payload)
        caught["states"]["FL"]["upper"]["rosterBehind"] = False
        self.assertEqual([i.code for i in validate.check_legislative_terms(caught, datetime.date(2026, 12, 1))],
                         ["legislature-term-unknown"])

    def test_the_build_asks_both_tables_on_one_build(self):
        # validate's build step asks the offices' check and the chambers'
        # on one state-government build (check_state_terms), and the
        # offices' check alone says nothing of the chambers.
        from unittest import mock
        from kyc import stategov, validate
        payload = {"sources": {"openstates": ["Open States", "https://openstates.org/", "2026-11-17"]},
                   "states": {"FL": {"upper": dict(title="Senate", seats=40, upSeats=20,
                                                   rosterBehind=True,
                                                   termBegins=L.for_page("FL", "upper"))}}}
        with mock.patch.object(stategov, "build", return_value=(payload, [])) as built:
            codes = [i.code for i in validate.check_state_terms(".", datetime.date(2026, 11, 4))]
        self.assertEqual(built.call_count, 1)
        self.assertIn("legislature-roster-behind", codes)
        self.assertIn("legislature-term-unknown", codes)
        alone = [i.code for i in validate.check_terms_begun(".", datetime.date(2026, 11, 4), payload)]
        self.assertFalse([c for c in alone if c.startswith("legislature-")])

    def test_the_warnings_reach_the_report(self):
        # The first version wrote these as level "warning", which the
        # report neither counts nor prints: every build's summary left them
        # out with nothing failing. An unknown level is refused at once.
        from kyc import validate
        with self.assertRaises(ValueError):
            validate.Issue("warning", "made-up", "a level the report does not know")
        payload = {"sources": {"openstates": ["Open States", "https://openstates.org/", "2026-11-17"]},
                   "states": {"FL": {"upper": dict(title="Senate", seats=40, upSeats=20,
                                                   rosterBehind=True,
                                                   termBegins=L.for_page("FL", "upper"))}}}
        report = validate.format_report(
            validate.check_legislative_terms(payload, datetime.date(2026, 11, 4)))
        self.assertIn("0 error(s), 2 warning(s)", report)
        self.assertIn("[warn ] legislature-roster-behind:", report)
        self.assertIn("[warn ] legislature-term-unknown:", report)


if __name__ == "__main__":
    unittest.main()
