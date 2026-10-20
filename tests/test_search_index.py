"""The home search's index of places and bodies (kyc/search_index.py, rule 97).

The grid's search found people by name, a state or a seat, and an office or
a place typed into it found nobody, or a challenger whose text mentioned the
word. ``assets/kyc-search.js`` answers such a query with a link to the page
about the thing named; this index holds what no file a page loads holds:
each legislature by its own name, each state's counties by Census code, the
Congress guide's committees with who leads each, and the tribal governments.
The render suite checks what the page does with it (``testSearchAnswers``).
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, pages, search_index  # noqa: E402
from kyc.government_maps import STATES, legislature_title  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def member(pid, name, seats, **kwargs):
    base = {"id": pid, "name": name, "chamber": "House", "state": "TX", "isCandidate": False,
            "committeeList": seats}
    base.update(kwargs)
    return base


COMMITTEES = {
    "HSAS": {"name": "House Committee on Armed Services", "chamber": "house"},
    "HSAS01": {"name": "Readiness", "chamber": "house", "parent": "HSAS"},
    "SSAS": {"name": "Senate Committee on Armed Services", "chamber": "senate"},
}

TRIBES = {"entries": [
    {"id": "1", "kind": "tribe", "name": "Cherokee Nation", "state": "OK",
     "leader": "Chuck Hoskin, Jr.", "title": "Principal Chief"},
    {"id": "2", "kind": "affiliate", "name": "A Band", "parent": "1", "state": "OK"},
    {"id": "3", "kind": "tribe", "name": "Navajo Nation", "state": "AZ", "disputed": True},
]}

LOCAL = {"TX": {"counties": {"48453": {"name": "Travis County"}, "48001": {"name": "Anderson County"}}},
         "LA": {"counties": {"22071": {"name": "Orleans Parish"}}}}


class TestTheIndex(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            member("R000001", "Chair Person", [{"code": "HSAS", "title": "Chairman", "side": "majority"},
                                               {"code": "HSAS01", "title": "Chairman", "side": "majority"}]),
            member("S000001", "Ranking Person", [{"code": "HSAS", "title": "Ranking Member",
                                                  "side": "minority"}]),
            # A candidate is not seated, and leads nothing (rule 67).
            member("H8TX00001", "Candidate Person", [{"code": "SSAS", "title": "Chairman",
                                                      "side": "majority"}], isCandidate=True),
        ]
        self.payload = search_index.build(LOCAL, self.profiles, COMMITTEES, TRIBES)

    def test_legislatures_by_their_own_names(self):
        legs = self.payload["legislatures"]
        self.assertEqual(sorted(legs), sorted(STATES))
        self.assertEqual(legs["MA"], ["Massachusetts General Court", "Senate", "House of Representatives"])
        self.assertEqual(legs["CA"], ["California Legislature", "Senate", "Assembly"])
        self.assertEqual(legs["VA"][0], "Virginia General Assembly")
        self.assertEqual(legs["VA"][2], "House of Delegates")
        # One chamber: no "Senate" of it to find.
        self.assertEqual(legs["NE"], ["Nebraska Legislature", None, None])

    def test_the_legislature_page_is_titled_the_same(self):
        for code in ("MA", "NE", "OH"):
            html = pages.render_legislature_page(code, "example.org")
            self.assertIn(f"<title>{legislature_title(code)} — ", html)

    def test_counties_by_census_code_in_the_page_words(self):
        self.assertEqual(self.payload["counties"]["TX"],
                         [["48001", "Anderson County"], ["48453", "Travis County"]])
        self.assertEqual(self.payload["counties"]["LA"], [["22071", "Orleans Parish"]])

    def test_committees_the_guide_lists_with_who_leads_them(self):
        rows = self.payload["committees"]
        # A subcommittee is not the guide's row; a committee only a
        # candidate "chairs" has no leader and is not listed.
        self.assertEqual(rows, [["HSAS", "House Committee on Armed Services", "house",
                                 [["R000001", "Chair Person", "Chairman"]],
                                 [["S000001", "Ranking Person", "Ranking Member"]]]])

    def test_the_guide_addresses_each_committee_row(self):
        html = pages.committees_html(self.profiles, COMMITTEES)
        self.assertEqual(re.findall(r'<tr id="committee-([A-Z0-9]+)">', html), ["HSAS"])

    def test_tribes_under_the_state_the_guide_lists_them_in(self):
        tribes = self.payload["tribes"]
        self.assertEqual(tribes["OK"], [["Cherokee Nation", "Chuck Hoskin, Jr.", "Principal Chief", 0, ""],
                                        ["A Band", "", "", 0, "Cherokee Nation"]])
        self.assertEqual(tribes["AZ"], [["Navajo Nation", "", "", 1, ""]])

    def test_problems_catch_a_wrong_answer(self):
        self.assertEqual(search_index.problems(self.payload), [])
        bad = dict(self.payload, counties={"TX": [["48001", "A County"], ["06001", "A County"]]})
        found = search_index.problems(bad)
        self.assertTrue(any("listed twice" in p for p in found), found)
        self.assertTrue(any("another state" in p for p in found), found)
        self.assertTrue(search_index.problems(dict(self.payload, counties={"TX": []})))


class TestTheCommittedFile(unittest.TestCase):
    """data/search.js as the build wrote it: signed, sound, and named by the
    home page for loading on demand, stamped (rules 18, 76)."""

    def setUp(self):
        path = os.path.join(ROOT, emit.SEARCH_FILE)
        with open(path, encoding="utf-8") as handle:
            self.text = handle.read()

    def test_it_is_signed_and_sound(self):
        import json
        match = re.search(r"window\.kycSearch = (\{.*\});\n", self.text)
        payload = json.loads(match.group(1))
        self.assertEqual(emit.read_signature(path=os.path.join(ROOT, emit.SEARCH_FILE)),
                         emit.search_signature(payload))
        self.assertEqual(search_index.problems(payload), [])
        # Every state with a county page has its counties in the index.
        self.assertEqual(sorted(payload["counties"]), sorted(STATES))

    def test_the_home_page_names_it_on_demand_with_the_module(self):
        with open(os.path.join(ROOT, emit.SITE_DIR, "index.html"), encoding="utf-8") as handle:
            html = handle.read()
        lazy = emit.on_demand_sources(html)
        self.assertIn("data/search.js", lazy)
        self.assertIn("data/measures.js", lazy)
        loaded = emit.script_sources(html)
        self.assertLess(loaded.index("assets/kyc-search.js"), loaded.index("assets/kyc-directory.js"))


if __name__ == "__main__":
    unittest.main()
