"""The day the term the 2026 election chooses begins (kyc/terms_begin.py),
and the warning when a roster still names a holder past it (the January
sweep, state-exec-past-inauguration). Made states on each clock - the
campaign's, December 15, January 10 - never the day's data."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import ballot2026, governor_share, terms_begin, validate  # noqa: E402

CAMPAIGN = datetime.date(2026, 10, 20)
DECEMBER = datetime.date(2026, 12, 15)
JANUARY = datetime.date(2027, 1, 10)


def term(day, kind="on", counted=True):
    record = {"day": day, "kind": kind, "counted": counted, "words": "the first Monday",
              "cite": "Made Const. art. V", "source": "https://law.example.gov/", "read": "2026-11-11"}
    begins = datetime.date.fromisoformat(day) + datetime.timedelta(days=1 if kind == "by" else 0)
    record["from"] = begins.isoformat()
    return record


def leaving(holder="Pat Example", why="term-limit", read="2026-11-10"):
    return {"holder": holder, "why": why, "read": read,
            "roster": "The National Governors Association’s roster"}


def payload(**offices):
    """A made state government: Alaska-like (a December term) and
    Michigan-like (a January term) governors the roster still names, and an
    Arizona-like new office no one holds yet."""
    return {"sources": {"nlga": ["NLGA", "https://nlga.example/", "2026-11-10"]},
            "states": {
                "AA": {"ballot2026": {"offices": {
                    "governor": dict({"up": True, "termBegins": term("2026-12-07"),
                                      "outgoing": leaving()}, **offices.get("AA", {}))}}},
                "BB": {"ballot2026": {"offices": {
                    "governor": {"up": True, "termBegins": term("2027-01-01", counted=False),
                                 "outgoing": leaving("Lee Sample", "not-listed")},
                    "sos": {"up": True, "termBegins": term("2027-01-04", kind="by"),
                            "outgoing": leaving("Kim Third", "not-listed")}}}},
                "CC": {"lt": {"none": True},
                       "ballot2026": {"offices": {"lt": {"up": True,
                                                         "termBegins": term("2027-01-04")}}}},
                # On the ballot, holder listed: no `outgoing`, never warned.
                "DD": {"ballot2026": {"offices": {"governor": {"up": True,
                                                               "termBegins": term("2026-12-07")}}}},
            }}


class TheTable(unittest.TestCase):
    def test_the_table_keeps_its_rules(self):
        self.assertEqual(terms_begin.problems(), [])

    def test_every_office_on_the_ballot_has_a_day_or_a_gap_and_none_has_both(self):
        dated = {(c, k) for c, records in terms_begin.TERMS.items()
                 for r in records for k in r["offices"]}
        self.assertEqual(dated | set(terms_begin.GAPS), set(terms_begin.up_offices()))
        self.assertFalse(dated & set(terms_begin.GAPS))
        # Every gap says why, and is listed for the build log.
        self.assertTrue(all(why for why, _src in terms_begin.GAPS.values()))
        self.assertEqual(len(terms_begin.gaps()), len(terms_begin.GAPS))

    def test_rules_are_counted_on_the_calendar(self):
        count = terms_begin.count
        # 2026's first Monday in December, and 2027's January days.
        self.assertEqual(count(("nth", 1, "Monday", 12)), datetime.date(2026, 12, 7))
        self.assertEqual(count(("nth", 1, "Monday", 1)), datetime.date(2027, 1, 4))
        self.assertEqual(count(("nth", 2, "Monday", 1)), datetime.date(2027, 1, 11))
        self.assertEqual(count(("nth", 3, "Tuesday", 1)), datetime.date(2027, 1, 19))
        self.assertEqual(count(("after", "Thursday", ("nth", 1, "Wednesday", 1))),
                         datetime.date(2027, 1, 7))
        self.assertEqual(count(("after", "Wednesday", ("nth", 2, "Tuesday", 1))),
                         datetime.date(2027, 1, 13))
        # "The first Tuesday after the first Monday": the day after, never
        # the Monday itself.
        self.assertEqual(count(("after", "Tuesday", ("nth", 1, "Monday", 1))),
                         datetime.date(2027, 1, 5))
        # Iowa's "first day of January ... which is not a Sunday or legal
        # holiday": New Year's Day is one, so Saturday the 2nd.
        self.assertEqual(count(("not-sunday-or", ("day", 1, 1), ((1, 1),))),
                         datetime.date(2027, 1, 2))
        self.assertEqual(count(("day", 1, 1)), datetime.date(2027, 1, 1))
        self.assertFalse(terms_begin.counted(("day", 1, 1)))
        self.assertTrue(terms_begin.counted(("nth", 1, "Monday", 1)))
        self.assertTrue(terms_begin.counted(("not-sunday-or", ("day", 1, 1), ((1, 1),))))

    def test_a_wrong_day_a_compiled_table_and_a_missing_office_are_refused(self):
        made = {"AK": (dict(terms_begin.TERMS["AK"][0], day="2026-12-01"),)}
        found = terms_begin.problems(made, {})
        self.assertTrue(any("the rule counts 2026-12-07" in f for f in found), found)
        self.assertTrue(any("neither a day nor a gap" in f for f in found))
        ncsl = {"AK": (dict(terms_begin.TERMS["AK"][0], sources=(
            ("https://www.ncsl.org/terms", ("words",)),)),)}
        self.assertTrue(any("not an official host" in f for f in terms_begin.problems(ncsl, {})))
        # An office not on the 2026 ballot (Virginia's governor) has no day.
        off = dict(terms_begin.TERMS, VA=(dict(terms_begin.TERMS["AK"][0]),))
        self.assertTrue(any("VA governor: not on the 2026 ballot" in f
                            for f in terms_begin.problems(off)))

    def test_every_record_quotes_its_source_on_an_official_host(self):
        for code, records in terms_begin.TERMS.items():
            for record in records:
                for url, quotes in record["sources"]:
                    self.assertTrue(url.startswith("https://"), url)
                    self.assertTrue(quotes and all(q.strip() for q in quotes), (code, url))
                self.assertIn(record["kind"], terms_begin.KINDS)


class WhoIsLeaving(unittest.TestCase):
    def test_only_a_holder_off_the_list_or_term_limited_is_leaving(self):
        holder = {"name": "Pat Example"}
        for why in ("not-listed", "term-limit"):
            out = terms_begin.outgoing("governor", holder, {"why": why}, "2026-11-10")
            self.assertEqual(out["holder"], "Pat Example")
            self.assertEqual(out["roster"], terms_begin.ROSTERS["governor"])
        for why in ("listed", "unchecked"):
            self.assertIsNone(terms_begin.outgoing("governor", holder, {"why": why}, "2026-11-10"))
        self.assertIsNone(terms_begin.outgoing("governor", {}, {"why": "not-listed"}, "x"))
        ag = terms_begin.outgoing("ag", {"name": "Lee", "listedBy": "Democratic Attorneys General "
                                         "Association"}, {"why": "not-listed"}, "2026-11-10")
        self.assertEqual(ag["roster"], "The Democratic Attorneys General Association’s roster")


class OnEachClock(unittest.TestCase):
    def test_the_warning_names_each_office_once_its_term_has_begun(self):
        data = payload()
        self.assertEqual(terms_begin.lagging(data, CAMPAIGN), [])
        december = terms_begin.lagging(data, DECEMBER)
        self.assertEqual(len(december), 1)
        self.assertIn("AA governor", december[0])
        self.assertIn("still names Pat Example (term-limit)", december[0])
        self.assertIn("began on Dec. 7, 2026", december[0])
        january = terms_begin.lagging(data, JANUARY)
        self.assertEqual([line.split(":")[0] for line in january],
                         ["AA governor", "BB governor", "BB secretary of state",
                          "CC lieutenant governor"])
        self.assertIn("began no later than Jan. 4, 2027", january[2])
        self.assertIn("lists none", january[3])
        # A "by" day counts as begun only from the day after it.
        self.assertFalse(any("BB secretary" in line for line in
                             terms_begin.lagging(data, datetime.date(2027, 1, 4))))

    def test_validate_warns_never_errs(self):
        data = payload()
        self.assertEqual(validate.check_terms_begun(today=CAMPAIGN, payload=data), [])
        issues = validate.check_terms_begun(today=JANUARY, payload=data)
        self.assertEqual([(i.level, i.code) for i in issues],
                         [("warning", "holder-past-inauguration")])
        self.assertEqual(len(issues[0].detail), 4)

    def test_the_page_sentence_waits_for_the_day_and_says_the_roster_read(self):
        item = payload()["states"]["BB"]["ballot2026"]["offices"]["governor"]
        self.assertEqual(terms_begin.past_term_text("governor", item, "2026-12-15"), "")
        text = terms_begin.past_term_text("governor", item, "2027-01-10")
        self.assertEqual(text, "The term of the governor elected on Nov. 3, 2026 began on Jan. 1, "
                               "2027 (Made Const. art. V). The National Governors Association’s "
                               "roster, read Nov. 10, 2026, lists Lee Sample, who was not among "
                               "the candidates for this office.")
        # A roster read after the day "still lists" them.
        later = dict(item, outgoing=leaving("Lee Sample", "not-listed", read="2027-01-08"))
        self.assertIn("read Jan. 8, 2027, still lists Lee Sample",
                      terms_begin.past_term_text("governor", later, "2027-01-10"))
        # No holder leaving, or no day read: nothing.
        self.assertEqual(terms_begin.past_term_text(
            "governor", dict(item, outgoing=None), "2027-01-10"), "")
        self.assertEqual(terms_begin.past_term_text(
            "governor", dict(item, termBegins=None), "2027-01-10"), "")

    def test_the_share_page_withholds_in_office_since_on_its_clock(self):
        item = dict(payload()["states"]["BB"]["ballot2026"]["offices"]["governor"],
                    selection="elected", note="4-year term")
        governor = {"id": "gov-BB", "name": "Lee Sample", "party": "Democratic",
                    "since": "January 1, 2019"}
        found = {"kind": "governor", "code": "MI", "person": governor,
                 "state": {"governor": governor, "ballot2026": {"offices": {"governor": item}}}}
        for post, past in ((False, False), (True, False), ("2026-12-15", False),
                           ("2027-01-10", True)):
            words = governor_share.share_words(found, post)
            self.assertEqual(bool(words["pastTerm"]), past, post)
            self.assertEqual(words["since"], "" if past else "In office since January 1, 2019")
        # The results last read in November, the roster read again on
        # January 8 and still naming them: the page written then says so.
        item["outgoing"] = leaving("Lee Sample", "not-listed", read="2027-01-08")
        words = governor_share.share_words(found, "2026-11-10")
        self.assertIn("read Jan. 8, 2027, still lists Lee Sample", words["pastTerm"])
        self.assertEqual(words["since"], "")


class TheBallotTable(unittest.TestCase):
    def test_it_dates_only_offices_the_ballot_table_holds(self):
        every = dict(ballot2026.STATES, **ballot2026.TERRITORIES)
        for code, records in terms_begin.TERMS.items():
            for record in records:
                for key in record["offices"]:
                    self.assertTrue(every[code][key][1], (code, key))


if __name__ == "__main__":
    unittest.main()
