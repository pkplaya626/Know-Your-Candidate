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

    def test_the_words_the_page_quotes_are_the_provisions_own(self):
        # The page prints `words` in quotation marks after "counted from":
        # a paraphrase there is refused (the review of PR #230 found 19).
        paraphrase = {"AK": (dict(terms_begin.TERMS["AK"][0],
                                  words="noon on the first Monday in December following the "
                                        "election"),)}
        self.assertTrue(any("are not the provision's" in f
                            for f in terms_begin.problems(paraphrase, {})))
        # Curly quotes and line breaks fold; the words themselves do not.
        hawaii = terms_begin.TERMS["HI"][0]
        self.assertIn("’", hawaii["words"])
        folded = {"HI": (dict(hawaii, words=hawaii["words"].replace("’", "'").replace(" ", "\n", 1)),)}
        self.assertFalse(any("are not the provision's" in f
                             for f in terms_begin.problems(folded, {})))
        for code, records in terms_begin.TERMS.items():
            for record in records:
                quotes = [terms_begin._fold(q) for _s, qs in record["sources"] for q in qs]
                self.assertTrue(any(terms_begin._fold(record["words"]) in q for q in quotes),
                                (code, record["offices"], record["words"]))

    def test_a_term_at_noon_is_begun_from_the_next_day(self):
        # Alaska's noon on December 7 is 21:00 UTC: on the 7th, by the
        # reader's or the build's day, it may not have begun.
        alaska = terms_begin.for_page("AK", "governor")
        self.assertEqual((alaska["day"], alaska["from"]), ("2026-12-07", "2026-12-08"))
        self.assertFalse(terms_begin.begun(alaska, "2026-12-07"))
        self.assertTrue(terms_begin.begun(alaska, "2026-12-08"))
        # A provision that names noon carries `at`, and one that does not, none.
        unmarked = {"AK": (dict(terms_begin.TERMS["AK"][0], at=""),)}
        self.assertTrue(any("names noon" in f for f in terms_begin.problems(unmarked, {})))
        marked = {"ID": (dict(terms_begin.TERMS["ID"][0], at="noon"),)}
        self.assertTrue(any("does not name noon" in f for f in terms_begin.problems(marked, {})))
        # A day with no hour is begun on the day itself.
        idaho = terms_begin.for_page("ID", "governor")
        self.assertEqual(idaho["from"], idaho["day"])
        # "Still lists" only of a read on or after that first certain day.
        item = {"termBegins": alaska,
                "outgoing": leaving("Pat Example", "term-limit", read="2026-12-07")}
        self.assertIn("read Dec. 7, 2026, lists Pat Example",
                      terms_begin.past_term_text("governor", item, "2026-12-08"))

    def test_iowas_secretary_of_state_has_the_constitutions_day(self):
        # Iowa Const. art. IV, s.22 starts the secretary of state's term on
        # January 1; Iowa Code 39.8 gives way to it ("except when otherwise
        # provided by the Constitution"), and its January 2 is the attorney
        # general's alone, whose term art. V, s.12 leaves to law.
        sos = terms_begin.record_for("IA", "sos")
        ag = terms_begin.record_for("IA", "ag")
        self.assertIsNot(sos, ag)
        self.assertEqual((sos["day"], sos["cite"]), ("2027-01-01", "Iowa Const. art. IV, s.22"))
        self.assertIn("commencing on the first day of January next after their election",
                      " ".join(q for _s, qs in sos["sources"] for q in qs))
        self.assertEqual(ag["day"], "2027-01-02")
        self.assertTrue(ag["cite"].startswith("Iowa Code 39.8"))
        self.assertIn("whose term of office shall be four years",
                      " ".join(q for _s, qs in ag["sources"] for q in qs))

    def test_arizonas_first_lieutenant_governor_takes_office_on_one_day(self):
        # The guide's maps move Arizona out of the states with no lieutenant
        # governor on government_maps.AZ_LTGOV_FROM; this table dates the
        # term from the same provision. Two counts of one day (rule 12) are
        # held to each other, since neither module can import the other
        # (government_maps -> ... -> ballot2026 -> government_maps).
        from kyc import government_maps
        record = terms_begin.record_for("AZ", "lt")
        self.assertEqual(record["day"], government_maps.AZ_LTGOV_FROM)
        # The span quoted to readers names no 1971 (the second reader).
        self.assertNotIn("1971", record["words"])
        self.assertIn(record["words"], " ".join(q for _s, qs in record["sources"] for q in qs))

    def test_each_office_links_its_own_provision_first(self):
        # Nevada's secretary of state is NRS 225, never the Attorney
        # General's chapter, though NRS 282.010 sets both their days.
        self.assertTrue(terms_begin.for_page("NV", "sos")["source"].endswith("NRS-225.html"))
        self.assertTrue(terms_begin.for_page("NV", "ag")["source"].endswith("NRS-228.html"))

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
        # "The term the 2026 election chose", true where a territory's
        # runoff chose it (48 U.S.C. 1422, 1591), never "elected on Nov. 3".
        self.assertEqual(text, "The term the 2026 election chose for the governor began on Jan. 1, "
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


    def test_the_share_pages_render_all_writes_say_it(self):
        # render_all is what the build writes o/gov-<ST>.html with: given
        # the results' day as a bare True it compared nothing, and no
        # governor's page ever said the term had begun (the review of PR
        # #230). Made data: a Michigan-like governor term-limited.
        governor = {"id": "gov-MI", "name": "Lee Sample", "party": "Democratic",
                    "since": "January 1, 2019", "profile": "https://www.nga.org/governors/x/"}
        item = dict(payload()["states"]["BB"]["ballot2026"]["offices"]["governor"],
                    selection="elected", note="4-year term")

        def page(results_as_of, read="2026-11-10"):
            office = dict(item, outgoing=leaving("Lee Sample", "not-listed", read=read))
            data = {"sources": {"nga": ["NGA", "https://www.nga.org/governors/", read]},
                    "states": {"MI": {"governor": governor,
                                      "ballot2026": {"offices": {"governor": office}}}}}
            summary = {"election": {"resultsAsOf": results_as_of + "T12:00:00Z"}}
            return governor_share.render_all(data, "example.org", summary)["o/gov-MI.html"]

        # Results read on January 10: the term began on January 1.
        after = page("2027-01-10")
        self.assertIn('class="share-past-term"', after)
        self.assertIn("The term the 2026 election chose for the governor began on Jan. 1, 2027",
                      after)
        self.assertNotIn("In office since", after)
        # Results last read in November, the roster read again on January 8
        # and still naming them: the page says so, on the data's own day.
        later = page("2026-11-10", read="2027-01-08")
        self.assertIn("read Jan. 8, 2027, still lists Lee Sample", later)
        self.assertNotIn("In office since", later)
        # Results and roster both read in November: nothing has begun.
        november = page("2026-11-10")
        self.assertNotIn("share-past-term", november)
        self.assertIn("In office since January 1, 2019", november)

    def test_from_january_an_office_with_no_day_read_and_a_leaving_holder_is_named(self):
        # A gap cannot be told begun, so it is named for a person to read
        # the provision from UNREAD_FROM on: a warning, no page words.
        data = payload()
        data["states"]["EE"] = {"ballot2026": {"offices": {
            "governor": {"up": True, "outgoing": leaving("Gale Gap", "term-limit")},
            # On the ballot and listed: no `outgoing`, never named.
            "lt": {"up": True}}}}
        self.assertEqual(terms_begin.unread(data, DECEMBER), [])
        named = terms_begin.unread(data, JANUARY)
        self.assertEqual(len(named), 1)
        self.assertTrue(named[0].startswith("EE governor: no day read"), named)
        self.assertIn("names Gale Gap (term-limit)", named[0])
        self.assertEqual(terms_begin.past_term_text(
            "governor", data["states"]["EE"]["ballot2026"]["offices"]["governor"], "2027-02-01"), "")
        issues = validate.check_terms_begun(today=JANUARY, payload=data)
        self.assertEqual([(i.level, i.code) for i in issues],
                         [("warning", "holder-past-inauguration"), ("warning", "term-day-unread")])
        self.assertEqual([(i.level, i.code) for i in
                          validate.check_terms_begun(today=DECEMBER, payload=data)],
                         [("warning", "holder-past-inauguration")])

    def test_a_gap_says_what_was_read(self):
        # Oregon's constitution was readable: its gap says what it holds.
        why, source = terms_begin.GAPS[("OR", "governor")]
        self.assertIn("except the Governor", why)
        self.assertTrue(source.startswith("https://www.oregonlegislature.gov/"))


class TheBallotTable(unittest.TestCase):
    def test_it_dates_only_offices_the_ballot_table_holds(self):
        every = dict(ballot2026.STATES, **ballot2026.TERRITORIES)
        for code, records in terms_begin.TERMS.items():
            for record in records:
                for key in record["offices"]:
                    self.assertTrue(every[code][key][1], (code, key))


if __name__ == "__main__":
    unittest.main()
