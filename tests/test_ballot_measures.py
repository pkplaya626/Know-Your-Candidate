"""The statewide questions on the November 3, 2026 ballot
(kyc/ballot_measures.py, rule 95).

Every state page said the ballot also held "ballot measures, which this
site does not list" (audit 2026-10-17, RACES-16, STATEGOV-14, PERSONA-08).
The questions are a hand-edited cache, each measure and each list an
official page's, quoted and dated; a "none" only with what shows it, and
"not found" never said as "none" (rule 19).
"""

import copy
import json
import os
import re
import unittest

from kyc import ballot_measures, emit, pages

ROOT = os.path.join(os.path.dirname(__file__), "..")


def measure(**over):
    out = {
        "designation": "Question 1", "title": "A Title", "question": "Shall the thing be done?",
        "kind": "constitutional amendment", "origin": "legislature",
        "voterGuide": "https://www.sos.ca.gov/guide/q1",
        "source": {"url": "https://www.sos.ca.gov/measures", "quote": "Question 1 A Title",
                   "pageUpdated": None},
    }
    out.update(over)
    return out


def record(**over):
    out = {
        "hasMeasures": True, "by": "California Secretary of State", "read": "2026-10-19",
        "listSource": {"url": "https://www.sos.ca.gov/measures", "title": "Qualified measures",
                       "quote": "Question 1", "pageUpdated": None},
        "voterGuide": {"url": "https://voterguide.sos.ca.gov/", "title": "Official guide"},
        "measures": [measure()],
        "notes": "", "verified": "VERIFIED",
    }
    out.update(over)
    return out


def none_record(**over):
    out = record(hasMeasures=False, measures=[], noneFrom="statement", voterGuide=None,
                 noneWords="There are no statewide questions.")
    out["listSource"] = {"url": "https://votersguide.elections.il.gov/Questions.aspx",
                         "title": "Questions of Public Policy",
                         "quote": "Questions: There are no statewide questions."}
    out.update(over)
    return out


def problems_of(code, rec):
    return ballot_measures.record_problems(code, rec)


class TestTheCommittedCache(unittest.TestCase):
    def setUp(self):
        self.data = ballot_measures.load(ROOT)

    def test_it_keeps_every_rule(self):
        self.assertEqual(ballot_measures.problems(self.data), [])

    def test_every_jurisdiction_says_one_of_three_things(self):
        records = self.data["jurisdictions"]
        self.assertEqual(set(records), ballot_measures.jurisdictions())
        for code, rec in records.items():
            self.assertIn(rec["hasMeasures"], (True, False, None), code)
            if rec["hasMeasures"] is None:
                # Not found is never "none" (rule 19): the page sends the
                # reader to the office.
                self.assertTrue(rec["office"]["url"], code)

    def test_no_measure_names_a_compiled_table_or_news(self):
        text = json.dumps({c: {k: v for k, v in r.items() if k not in ("notes", "verified")}
                           for c, r in self.data["jurisdictions"].items()})
        for host in ("ballotpedia.org", "ncsl.org", "wikipedia.org"):
            self.assertNotIn(host, text)

    def test_the_page_file_is_the_caches(self):
        payload = ballot_measures.for_page(self.data)
        self.assertEqual(emit.read_signature(path=os.path.join(ROOT, emit.MEASURES_FILE)),
                         emit.measures_signature(payload))


class TestSources(unittest.TestCase):
    def test_a_compiled_table_is_never_a_source(self):
        for url in ("https://ballotpedia.org/California_2026_ballot_propositions",
                    "https://www.ncsl.org/elections-and-campaigns/ballot-measures",
                    "https://en.wikipedia.org/wiki/2026_California_Proposition_1"):
            rec = record(measures=[measure(source={"url": url, "quote": "x"})])
            self.assertTrue(any("not an official source" in p for p in problems_of("CA", rec)), url)

    def test_news_or_an_advocate_is_never_a_source(self):
        for url in ("https://calmatters.org/politics/2026/prop-1", "https://yesonprop1.org/"):
            rec = record(measures=[measure(source={"url": url, "quote": "x"})])
            self.assertTrue(problems_of("CA", rec), url)

    def test_another_states_office_is_not_this_ones(self):
        rec = record(measures=[measure(source={"url": "https://www.sos.ca.gov/x", "quote": "x"})])
        self.assertTrue(any("not an official source" in p for p in problems_of("NV", rec)))

    def test_a_county_counts_only_for_its_own_state(self):
        url = "https://www.gtcountysc.gov/DocumentCenter/View/4203/ballots"
        sc = none_record(noneFrom="ballots", noneWords=None)
        sc.pop("noneWords")
        sc["listSource"] = {"url": url, "title": "Georgetown County sample ballots", "quote": "x"}
        self.assertEqual(problems_of("SC", sc), [])
        self.assertTrue(problems_of("NC", sc))

    def test_a_measure_without_a_source_or_a_quote_is_refused(self):
        self.assertTrue(problems_of("CA", record(measures=[measure(source=None)])))
        self.assertTrue(problems_of("CA", record(measures=[
            measure(source={"url": "https://www.sos.ca.gov/x", "quote": ""})])))

    def test_a_voter_guide_off_the_states_domains_is_refused(self):
        rec = record(measures=[measure(voterGuide="https://www.vote411.org/ballot")])
        self.assertTrue(any("voter guide" in p for p in problems_of("CA", rec)))


class TestNoneAndNotFound(unittest.TestCase):
    def test_a_none_needs_its_quoted_statement(self):
        self.assertEqual(problems_of("IL", none_record()), [])
        unquoted = none_record()
        unquoted["listSource"] = dict(unquoted["listSource"], quote="")
        self.assertTrue(problems_of("IL", unquoted))
        self.assertTrue(problems_of("IL", none_record(noneWords="Nothing at all.")))
        self.assertTrue(problems_of("IL", none_record(noneFrom=None)))
        missing = none_record()
        missing.pop("listSource")
        self.assertTrue(problems_of("IL", missing))

    def test_a_none_lists_nothing(self):
        self.assertTrue(problems_of("IL", none_record(measures=[measure()])))

    def test_not_found_lists_nothing_and_names_the_office(self):
        rec = record(hasMeasures=None, measures=[], voterGuide=None,
                     office={"url": "https://www.maine.gov/sos/elections", "name": "Maine SOS"})
        rec.pop("listSource")
        self.assertEqual(problems_of("ME", rec), [])
        self.assertTrue(problems_of("ME", dict(rec, measures=[measure()])))
        no_office = dict(rec)
        no_office.pop("office")
        self.assertTrue(problems_of("ME", no_office))
        self.assertTrue(problems_of("ME", dict(rec, noneFrom="ballots")))

    def test_measures_with_none_listed_is_refused(self):
        self.assertTrue(problems_of("CA", record(measures=[])))


class TestTheRecord(unittest.TestCase):
    def test_a_date_outside_the_cycle_is_refused(self):
        self.assertTrue(problems_of("CA", record(read="2025-10-19")))
        self.assertTrue(problems_of("CA", record(read="last week")))
        old = measure(source={"url": "https://www.sos.ca.gov/x", "quote": "x",
                              "pageUpdated": "2022-08-01 (server Last-Modified)"})
        self.assertTrue(any("outside the cycle" in p for p in problems_of("CA", record(measures=[old]))))
        data = {"election": "2024-11-05", "jurisdictions": {}}
        self.assertTrue(any("not 2026-11-03" in p for p in ballot_measures.problems(data)))

    def test_a_yes_vote_in_the_sites_own_words_has_no_field(self):
        rec = record(measures=[measure(yesMeans="A yes vote raises taxes")])
        self.assertTrue(any("unknown field" in p for p in problems_of("CA", rec)))

    def test_a_kind_or_origin_the_page_cannot_word_says_its_own(self):
        self.assertTrue(problems_of("CA", record(measures=[measure(kind="other")])))
        self.assertEqual(problems_of("CA", record(measures=[
            measure(kind="other", kindWords="Statutory question")])), [])
        self.assertTrue(problems_of("CA", record(measures=[measure(origin="constitution")])))
        self.assertTrue(problems_of("CA", record(measures=[measure(kind="initiative")])))

    def test_a_measure_listed_twice_is_refused(self):
        self.assertTrue(problems_of("CA", record(measures=[measure(), measure()])))

    def test_every_jurisdiction_needs_a_record(self):
        found = ballot_measures.problems({"election": "2026-11-03", "jurisdictions": {
            "CA": record(), "ZZ": record()}})
        self.assertIn("TX: no record", found)
        self.assertIn("ZZ: not a jurisdiction", found)


class TestThePageWords(unittest.TestCase):
    def test_the_legislature_is_named_as_its_constitution_names_it(self):
        self.assertEqual(ballot_measures.origin_words("MA", measure()), "the General Court")
        self.assertEqual(ballot_measures.origin_words("GA", measure()), "the General Assembly")
        self.assertEqual(ballot_measures.origin_words("CA", measure()), "the Legislature")
        self.assertEqual(ballot_measures.origin_words("CA", measure(origin="citizens")),
                         "a citizens' petition")
        self.assertIsNone(ballot_measures.origin_words("MP", measure(origin=None)))

    def test_a_title_the_designation_holds_is_said_once(self):
        m = measure(designation="Question 2 (Statutory Question required by HB 1300)",
                    title="Statutory Question required by HB 1300")
        self.assertIsNone(ballot_measures._measure("NH", m)["title"])

    def test_a_cut_text_is_marked(self):
        self.assertTrue(ballot_measures._measure("MA", measure(question="Do you ... approve?"))["cut"])
        self.assertNotIn("cut", ballot_measures._measure("MA", measure()))

    def test_the_page_never_holds_the_researchers_words_or_quotes(self):
        data = copy.deepcopy(ballot_measures.load(ROOT))
        data["jurisdictions"]["CA"]["notes"] = "a researcher's note"
        data["jurisdictions"]["IL"] = none_record()
        page = ballot_measures.for_page(data)
        text = json.dumps(page)
        self.assertNotIn("researcher", text)
        self.assertNotIn("VERIFIED", text)
        self.assertNotIn('"quote"', text)
        self.assertEqual(page["IL"]["none"], {"from": "statement",
                                              "words": "There are no statewide questions."})

    def test_a_cache_that_breaks_a_rule_is_never_written(self):
        data = copy.deepcopy(ballot_measures.load(ROOT))
        data["jurisdictions"]["TX"]["measures"] = [measure()]
        with self.assertRaises(ValueError):
            ballot_measures.for_page(data)


class TestTheReview(unittest.TestCase):
    """What the PR #120 review found."""

    def test_a_shown_title_is_the_documents_own_name(self):
        # The researchers' asides were rendered as link text: "(...; linked
        # as '...' from https://www.michigan.gov/sos/elections)".
        for title in ("Ballot questions (Bureau; linked from https://www.michigan.gov/sos)",
                      "Voter Pamphlet; Spanish edition: archive.voteidaho.gov/x.pdf",
                      "Vermont Voter Guide (described as 'voting instructions')",
                      "Database (Division of Elections), query: Year 2026",
                      "2026 Voter Guide, pages 73-74: amendments"):
            rec = record()
            rec["listSource"] = dict(rec["listSource"], title=title)
            self.assertTrue(any("not the document's own name" in p for p in problems_of("CA", rec)),
                            title)
            guide = record(voterGuide={"url": "https://voterguide.sos.ca.gov/", "title": title})
            self.assertTrue(any("not the document's own name" in p
                                for p in problems_of("CA", guide)), title)
        self.assertEqual(problems_of("CA", record()), [])

    def test_no_title_on_the_page_carries_a_note_or_an_address(self):
        page = ballot_measures.for_page(ballot_measures.load(ROOT))
        for code, rec in page.items():
            for key in ("list", "guide"):
                if rec.get(key):
                    self.assertNotRegex(rec[key]["title"], r"https?:|\blinked\b|described as",
                                        f"{code} {key}")
            if rec.get("office"):
                self.assertNotRegex(rec["office"]["name"], r"https?:|\blinked\b", code)

    def test_a_proclamation_for_offices_is_not_a_none(self):
        # It would not name a constitutional amendment election, which that
        # election's own resolution sets: Texas's "none" rested on one.
        call = none_record(noneFrom="call",
                           noneWords="There are no statewide questions.")
        self.assertTrue(any("not said on what" in p for p in problems_of("IL", call)))
        tx = ballot_measures.load(ROOT)["jurisdictions"]["TX"]
        self.assertEqual(tx["noneFrom"], "ballots")
        self.assertNotIn("noneWords", tx)

    def test_a_question_decided_locally_says_how_each_ballot_words_it(self):
        local = measure(designation="Question 2", local=True,
                        textNote="Each town's ballot names the town.")
        self.assertEqual(problems_of("CA", record(measures=[measure(), local])), [])
        unnoted = dict(local)
        unnoted.pop("textNote")
        self.assertTrue(problems_of("CA", record(measures=[measure(), unnoted])))
        self.assertTrue(problems_of("CA", record(measures=[measure(), dict(local, local="yes")])))
        self.assertTrue(ballot_measures._measure("CA", local)["local"])
        self.assertNotIn("local", ballot_measures._measure("CA", measure()))

    def test_only_local_questions_are_no_statewide_ones(self):
        local = measure(local=True, textNote="Each town's ballot names the town.")
        self.assertTrue(any("decided locally" in p
                            for p in problems_of("CA", record(measures=[local]))))

    def test_new_hampshires_hb_1300_question_is_marked_local(self):
        # Each town or city votes on it for itself: not one statewide
        # decision, and not counted as one.
        nh = ballot_measures.load(ROOT)["jurisdictions"]["NH"]["measures"]
        self.assertEqual([bool(m.get("local")) for m in nh], [False, True])
        self.assertIsNone(nh[0]["title"])
        stats = ballot_measures.stats(ballot_measures.load(ROOT))
        self.assertGreaterEqual(stats["local"], 1)

    def test_a_missing_cache_is_an_error_under_check_too(self):
        import inspect
        from kyc import cli, validate
        self.assertIsNone(ballot_measures.load(os.path.join(ROOT, "no-such-root")))
        issues = validate.check_ballot_measures({})
        self.assertEqual([(i.level, i.code) for i in issues],
                         [("error", "ballot-measures-missing")])
        # cli hands validate {} for a missing cache, never None, which
        # validate.run would skip.
        self.assertIn("measures=measures_mod.load(args.root) or {}", inspect.getsource(cli._build))


class TestTheSourcesAreNamed(unittest.TestCase):
    """A state page that shows the questions names where they come from, in
    its footer and on the About page (PR #120 review)."""

    def read(self, page):
        with open(os.path.join(ROOT, "candidate_profiles_site", page), encoding="utf-8") as fh:
            return fh.read()

    def test_a_state_page_footer_names_the_questions_source(self):
        self.assertIn("statewide\n                    questions from the election office's own list",
                      self.read("states/ca.html"))
        self.assertIn("District-wide\n", self.read("states/dc.html"))
        self.assertIn("territory-wide\n", self.read("states/gu.html"))
        # Puerto Rico holds no election that day, and its page lists none.
        self.assertNotIn("questions from the election office", self.read("states/pr.html"))

    def test_the_about_page_lists_them(self):
        about = self.read("about.html")
        self.assertIn("Statewide ballot questions", about)
        self.assertIn("Each election office's own list, voter guide or official sample ballots",
                      about)


class TestThePagesLoadThem(unittest.TestCase):
    def test_state_pages_and_your_ballot_load_the_questions(self):
        self.assertIn("../data/measures.js", pages._state_scripts("CA"))
        self.assertNotIn("../data/measures.js", pages._state_scripts(None))
        self.assertIn("data/measures.js", emit.BALLOT_PAGE_REQUIREMENTS)
        self.assertNotIn("../data/measures.js", emit.STATES_INDEX_REQUIREMENTS)
        for page in ("states/ca.html", "ballot.html"):
            with open(os.path.join(ROOT, "candidate_profiles_site", page), encoding="utf-8") as fh:
                self.assertTrue(re.search(r'src="(\.\./)?data/measures\.js\?v=[0-9a-f]{10}"',
                                          fh.read()), page)


if __name__ == "__main__":
    unittest.main()
