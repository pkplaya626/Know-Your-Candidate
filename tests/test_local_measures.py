"""The local questions of the most populous counties (kyc/local_measures.py,
rule 102).

Every county page and Your ballot said local questions were "not listed
here". They are now a hand-edited cache for the 50 most populous counties:
each question and each list an official page's - the county's, a covered
city's or the state election office's - quoted and dated; a "none" only on
a document's own words, and "not found" never said as "none" (rule 19).
Each test makes the state it tests (the Conventions): a constructed cache,
never the day's data.
"""

import copy
import json
import os
import unittest

from kyc import emit, local_measures, overrides, pages

ROOT = os.path.join(os.path.dirname(__file__), "..")
LIST = "https://votetravis.gov/wp-content/uploads/ballot.pdf"


def measure(**over):
    out = {
        "jurisdiction": {"kind": "city", "name": "City of Austin", "place": "4805000"},
        "designation": "Proposition A", "title": None,
        "text": "The issuance of $100,000,000 general obligation bonds for parks?",
        "kind": "bond",
        "source": {"url": LIST, "title": "November 3rd, 2026 Consolidated Ballot",
                   "quote": "City of Austin Proposition A"},
        "read": "2026-11-01",
    }
    out.update(over)
    return out


def basis(**over):
    out = {"from": "ballots",
           "source": {"url": LIST, "title": "November 3rd, 2026 Consolidated Ballot",
                      "quote": "This sample ballot shows ALL contests in this election"},
           "found": "prints no question of Travis County", "complete": "shows ALL contests"}
    out.update(over)
    return out


def county(fips, rank, **over):
    out = {
        "state": "TX", "name": f"County {fips}", "rank": rank,
        "office": {"name": "Travis County Clerk", "url": "https://votetravis.gov/"},
        "read": "2026-11-01",
        "own": {"status": "none", "basis": basis()},
        "cities": [{"name": "City of Austin", "place": "4805000", "status": "listed"}],
        "measures": [measure()],
    }
    out.update(over)
    return out


def cache(**counties):
    """A cache of 50 counties, every one on votetravis.gov (allowed for all
    of them below), *counties* replacing the first ones."""
    fips = [f"48{n:03d}" for n in range(1, 51)]
    out = {fips[i]: county(fips[i], i + 1) for i in range(50)}
    for key, rec in counties.items():
        out[key] = rec
    return {
        "election": "2026-11-03",
        "coverage": {"counties": 50, "cityPopulation": 250000,
                     "ranking": {"title": "County Population Totals", "by": "U.S. Census Bureau",
                                 "url": "https://www.census.gov/data/tables/x.html"}},
        "counties": out,
    }


class Hosts:
    """Lets votetravis.gov speak for the constructed counties."""

    def setUp(self):
        self._saved = dict(overrides.LOCAL_MEASURE_SOURCES)
        overrides.LOCAL_MEASURE_SOURCES["votetravis.gov"] = (
            tuple(f"48{n:03d}" for n in range(1, 51)), "Travis County Clerk", "a test")

    def tearDown(self):
        overrides.LOCAL_MEASURE_SOURCES.clear()
        overrides.LOCAL_MEASURE_SOURCES.update(self._saved)


class TheRules(Hosts, unittest.TestCase):

    def test_a_cache_that_keeps_every_rule_passes(self):
        self.assertEqual(local_measures.problems(cache()), [])

    def test_a_host_speaks_only_for_the_counties_it_names(self):
        data = cache()
        data["counties"]["48001"]["measures"][0]["source"]["url"] = "https://www.sdvote.com/x.pdf"
        found = local_measures.problems(data)
        self.assertTrue(any("not an official source" in p and "48001" in p for p in found), found)

    def test_a_dot_gov_host_not_recorded_is_refused(self):
        # Being on .gov is not enough (rule 84): another county's office is.
        data = cache()
        data["counties"]["48002"]["measures"][0]["source"]["url"] = "https://www.harriscountytx.gov/x"
        self.assertTrue(any("48002" in p and "not an official" in p
                            for p in local_measures.problems(data)))

    def test_the_state_election_offices_own_domain_needs_no_entry(self):
        data = cache()
        data["counties"]["48003"]["measures"][0]["source"]["url"] = "https://www.sos.state.tx.us/x.pdf"
        self.assertEqual(local_measures.problems(data), [])

    def test_a_compiled_table_or_news_is_never_a_source(self):
        for url in ("https://ballotpedia.org/Austin", "https://www.texastribune.org/x"):
            data = cache()
            data["counties"]["48004"]["measures"][0]["source"]["url"] = url
            self.assertTrue(any("48004" in p for p in local_measures.problems(data)), url)

    def test_an_unquoted_source_is_refused(self):
        data = cache()
        data["counties"]["48005"]["measures"][0]["source"]["quote"] = ""
        self.assertTrue(any("not quoted" in p for p in local_measures.problems(data)))

    def test_a_yes_vote_in_the_sites_own_words_has_no_field(self):
        data = cache()
        data["counties"]["48006"]["measures"][0]["yesMeans"] = "The city may borrow"
        self.assertTrue(any("unknown field" in p and "yesMeans" in p
                            for p in local_measures.problems(data)))

    def test_a_none_needs_the_documents_own_words(self):
        # A list that merely holds none is "unlisted", never "none" (rule 19).
        data = cache()
        b = data["counties"]["48007"]["own"]["basis"]
        b.pop("complete")
        found = local_measures.problems(data)
        self.assertTrue(any("'unlisted'" in p for p in found), found)
        data["counties"]["48007"]["own"] = {"status": "unlisted", "basis": b}
        self.assertEqual(local_measures.problems(data), [])

    def test_the_complete_words_must_be_the_quotes(self):
        data = cache()
        data["counties"]["48008"]["own"]["basis"]["complete"] = "every contest in the county"
        self.assertTrue(any("'complete' words are not in" in p for p in local_measures.problems(data)))

    def test_every_ballot_style_read_whole_is_a_basis(self):
        data = cache()
        b = data["counties"]["48009"]["own"]["basis"]
        b.pop("complete")
        b["every"] = True
        self.assertEqual(local_measures.problems(data), [])

    def test_a_statement_needs_its_words(self):
        data = cache()
        data["counties"]["48010"]["own"]["basis"] = basis(from_=None)
        data["counties"]["48010"]["own"]["basis"].pop("from_")
        data["counties"]["48010"]["own"]["basis"].update({"from": "statement"})
        data["counties"]["48010"]["own"]["basis"].pop("complete")
        self.assertTrue(any("statement with no words" in p for p in local_measures.problems(data)))

    def test_not_found_says_why_and_lists_nothing(self):
        data = cache()
        data["counties"]["48011"]["own"] = {"status": "notFound", "why": ""}
        self.assertTrue(any("not said why" in p for p in local_measures.problems(data)))
        data["counties"]["48011"]["own"] = {"status": "notFound", "why": "Its site could not be read."}
        data["counties"]["48011"]["measures"].append(measure(
            jurisdiction={"kind": "county", "name": "County 48011"}))
        self.assertTrue(any("'notFound', yet 1" in p for p in local_measures.problems(data)))

    def test_listed_lists_something(self):
        data = cache()
        data["counties"]["48012"]["own"] = {"status": "listed"}
        self.assertTrue(any("'listed', and no county" in p for p in local_measures.problems(data)))

    def test_a_city_question_needs_its_city_covered(self):
        data = cache()
        data["counties"]["48013"]["cities"] = []
        self.assertTrue(any("does not cover" in p for p in local_measures.problems(data)))

    def test_a_city_listed_elsewhere_must_be_listed_there(self):
        data = cache()
        rec = data["counties"]["48014"]
        rec["measures"] = []
        rec["cities"] = [{"name": "City of Austin", "place": "4805000", "status": "elsewhere",
                          "listedIn": "48015"}]
        self.assertEqual(local_measures.problems(data), [])
        data["counties"]["48015"]["cities"][0] = {"name": "City of Austin", "place": "4805000",
                                                  "status": "notFound", "why": "Not read."}
        data["counties"]["48015"]["measures"] = []
        self.assertEqual(local_measures.problems(data), [])
        rec["cities"][0]["listedIn"] = "99999"
        self.assertTrue(any("not another covered county" in p for p in local_measures.problems(data)))

    def test_a_text_or_why_it_is_not_shown(self):
        data = cache()
        m = data["counties"]["48016"]["measures"][0]
        m["text"] = None
        self.assertTrue(any("textMissing" in p for p in local_measures.problems(data)))
        m["textMissing"] = "A scan this site could not read."
        self.assertEqual(local_measures.problems(data), [])

    def test_a_date_outside_the_cycle_is_refused(self):
        data = cache()
        data["counties"]["48017"]["measures"][0]["read"] = "2024-11-01"
        self.assertTrue(any("outside the cycle" in p for p in local_measures.problems(data)))

    def test_fifty_counties_ranked_once_each(self):
        data = cache()
        data["counties"]["48018"]["rank"] = 1
        self.assertTrue(any("ranked 1 to 50" in p for p in local_measures.problems(data)))
        data = cache()
        del data["counties"]["48050"]
        self.assertTrue(any("ranked 1 to 50" in p for p in local_measures.problems(data)))

    def test_a_title_that_is_a_note_is_refused(self):
        data = cache()
        data["counties"]["48019"]["measures"][0]["source"]["title"] = "Ballot, linked from https://x"
        self.assertTrue(any("not the document's own name" in p for p in local_measures.problems(data)))

    def test_a_question_its_source_marks_withdrawn_is_refused(self):
        # Sacramento's list printed "WITHDRAWN -- Measure F: City of
        # Sacramento" over a question the first cache listed as on the ballot.
        for field, words in (("quote", "WITHDRAWN -- Proposition A: City of Austin"),
                             ("text", "Removed from the ballot by order of the court.")):
            data = cache()
            m = data["counties"]["48025"]["measures"][0]
            if field == "quote":
                m["source"]["quote"] = words
            else:
                m["text"] = words
            found = local_measures.problems(data)
            self.assertTrue(any("48025" in p and "taken off the ballot" in p for p in found),
                            (field, found))

    def test_complete_words_that_are_only_the_title_are_refused(self):
        # Tarrant's "Districts in Election" was the PDF's name, not words
        # saying the list was whole.
        data = cache()
        b = data["counties"]["48026"]["own"]["basis"]
        b["source"]["title"] = "This sample ballot shows ALL contests"
        found = local_measures.problems(data)
        self.assertTrue(any("only its source's title" in p for p in found), found)

    def test_no_government_is_said_of_a_county_never_a_city(self):
        data = cache()
        rec = data["counties"]["48027"]
        rec["own"] = {"status": "none", "basis": basis(**{"from": "noGovernment"})}
        rec["own"]["basis"].pop("complete")
        self.assertEqual(local_measures.problems(data), [])
        rec["measures"] = []
        rec["cities"] = [{"name": "City of Austin", "place": "4805000", "status": "none",
                          "basis": dict(rec["own"]["basis"])}]
        found = local_measures.problems(data)
        self.assertTrue(any("never of a city" in p for p in found), found)

    def test_another_countys_host_stands_only_through_its_one_document(self):
        # Keyed on Alameda's host, any Alameda page passed for Santa Clara.
        overrides.LOCAL_MEASURE_SOURCES["sdvote.com"] = (("48028",), "San Diego", "a test")
        overrides.LOCAL_MEASURE_SOURCES["https://www.sdvote.com/joint.pdf"] = (
            ("48029",), "San Diego", "the joint notice, a test")
        data = cache()
        for fips in ("48028", "48029"):
            data["counties"][fips]["measures"][0]["source"]["url"] = "https://www.sdvote.com/joint.pdf"
        self.assertEqual(local_measures.problems(data), [])
        data["counties"]["48029"]["measures"][0]["source"]["url"] = "https://www.sdvote.com/other.pdf"
        found = local_measures.problems(data)
        self.assertTrue(any("48029" in p and "not an official source" in p for p in found), found)

    def test_an_unused_host_is_reported(self):
        self.assertNotIn("votetravis.gov", local_measures.unused_hosts(cache()))
        self.assertIn("sdvote.com", local_measures.unused_hosts(cache()))


class ThePage(Hosts, unittest.TestCase):

    def test_a_city_elsewhere_is_drawn_from_its_own_county(self):
        data = cache()
        rec = data["counties"]["48020"]
        rec["measures"] = []
        rec["cities"] = [{"name": "City of Austin", "place": "4805000", "status": "elsewhere",
                          "listedIn": "48021"}]
        page = local_measures.for_state(data)["TX"]["48020"]
        city = page["cities"][0]
        self.assertEqual(city["status"], "listed")
        self.assertEqual(city["from"]["fips"], "48021")
        self.assertEqual(city["measures"][0]["designation"], "Proposition A")

    def test_the_page_holds_no_researchers_notes(self):
        data = cache()
        data["counties"]["48022"]["measures"][0]["notes"] = "a researcher's aside"
        data["counties"]["48022"]["notes"] = "another"
        text = json.dumps(local_measures.for_state(data))
        self.assertNotIn("researcher", text)
        self.assertNotIn("another", text)

    def test_a_summary_and_a_missing_text_are_said(self):
        data = cache()
        data["counties"]["48023"]["measures"] = [
            measure(summary=True),
            measure(designation="Proposition B", text=None, textMissing="A scan."),
        ]
        out = local_measures.for_state(data)["TX"]["48023"]["cities"][0]["measures"]
        self.assertTrue(out[0]["summary"])
        self.assertEqual(out[1]["missing"], "A scan.")
        self.assertNotIn("text", out[1])

    def test_a_cache_that_breaks_a_rule_is_never_written(self):
        data = cache()
        data["counties"]["48024"]["measures"][0]["source"]["quote"] = ""
        with self.assertRaises(ValueError):
            local_measures.for_state(data)
        with self.assertRaises(ValueError):
            local_measures.index(data)

    def test_the_index_carries_each_states_sample_ballot(self):
        # A county page loads no build figures, so the index carries the
        # sample-ballot link KYC.sampleBallotLine words for both pages.
        voting = {"TX": {"sample": "https://www.votetexas.gov/sample", "results": "x"},
                  "WY": {"results": "y"},
                  "_labels": {"TX": {"sample": "Look up your ballot"}},
                  "_siteLinked": {"TX": ["sample"]}}
        samples = local_measures.samples(voting)
        self.assertEqual(samples, {"TX": {"url": "https://www.votetexas.gov/sample",
                                          "linked": True, "label": "Look up your ballot"}})
        self.assertEqual(local_measures.index(cache(), samples)["samples"], samples)

    def test_the_index_names_each_county_and_its_state(self):
        idx = local_measures.index(cache())
        self.assertEqual(idx["counties"]["48001"], ["TX", "County 48001"])
        self.assertEqual(len(idx["counties"]), 50)


class TheCommittedCache(unittest.TestCase):

    def setUp(self):
        self.data = local_measures.load(ROOT)

    def test_it_keeps_every_rule(self):
        self.assertEqual(local_measures.problems(self.data), [])

    def test_every_host_entry_is_cited(self):
        self.assertEqual(local_measures.unused_hosts(self.data), [])

    def test_the_counties_are_the_fifty_most_populous(self):
        ranks = sorted(rec["rank"] for rec in self.data["counties"].values())
        self.assertEqual(ranks, list(range(1, 51)))

    def test_the_page_files_are_the_caches(self):
        payloads = emit.local_measures_payloads(self.data, local_measures.load_samples(ROOT))
        self.assertEqual(emit.check_local_measures(payloads, ROOT), [])

    def test_no_none_rests_on_a_list_that_does_not_say_it_is_whole(self):
        for fips, rec in self.data["counties"].items():
            for part in [rec["own"]] + rec["cities"]:
                if part["status"] == "none":
                    b = part["basis"]
                    self.assertTrue(b["from"] == "noGovernment" or b.get("complete") or b.get("every"),
                                    fips)


class ThePages(unittest.TestCase):

    def test_your_ballot_loads_the_index_and_names_each_state_on_demand(self):
        self.assertIn("data/localmeasures/index.js", emit.BALLOT_PAGE_REQUIREMENTS)
        self.assertIn("assets/kyc-localmeasures.js", emit.BALLOT_PAGE_REQUIREMENTS)
        html = pages.render_ballot_page("example.org", ["TX", "CA"])
        lazy = html.split('<template id="onDemandData">', 1)[1].split("</template>", 1)[0]
        self.assertIn("data/localmeasures/tx.js", lazy)
        self.assertIn("data/localmeasures/ca.js", lazy)

    def test_a_county_page_loads_its_states_file_only_where_covered(self):
        tx = pages.render_counties_page("TX", "example.org", local=True)
        wy = pages.render_counties_page("WY", "example.org", local=False)
        self.assertIn("../data/localmeasures/tx.js", tx)
        self.assertNotIn("../data/localmeasures/wy.js", wy)
        for html in (tx, wy):
            self.assertIn("../data/localmeasures/index.js", html)
            self.assertLess(html.index("../data/localmeasures/index.js"),
                            html.index("../assets/kyc-localmeasures.js"))
            self.assertLess(html.index("../assets/kyc-localmeasures.js"),
                            html.index("../assets/kyc-local.js"))

    def test_the_people_index_holds_no_local_question(self):
        # Rule 94: loaded only where shown.
        path = os.path.join(ROOT, "candidate_profiles_site", "data", "people", "index.js")
        with open(path, encoding="utf-8") as handle:
            self.assertNotIn("kycLocalMeasures", handle.read())


if __name__ == "__main__":
    unittest.main()
