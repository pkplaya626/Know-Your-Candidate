"""The federal government's pages: what kyc/federal_build.py writes for them
(data/federal.js, one file per court, the judges' search index) and the
pages kyc/pages.py generates (federal/index.html, courts/<id>.html)."""

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, federal_build, federal_courts, pages  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def built():
    try:
        return federal_build.build(ROOT)
    except federal_build.FederalBuildError as exc:
        raise unittest.SkipTest(str(exc))


class TestTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.courts, cls.search, cls.problems = built()

    def test_the_caches_have_no_errors(self):
        self.assertEqual(self.problems, [])

    def test_every_court_has_a_file(self):
        self.assertEqual(set(self.courts), set(federal_courts.COURTS))
        for cid, court in self.courts.items():
            listed = federal_courts.COURTS[cid]["kind"] != "territorial"
            self.assertEqual(court["listed"], listed, cid)

    def test_no_official_is_a_profile(self):
        # Officials are never counted among the members of Congress (rule
        # 27): their ids cannot be a profile's.
        ids = [self.payload["president"]["id"], self.payload["vicePresident"]["id"]]
        ids += [o["holder"]["id"] for o in self.payload["offices"] if o["holder"]]
        ids += [j["id"] for c in self.courts.values() for j in c["judges"]]
        self.assertTrue(all(re.match(r"^(x|fjc)-[a-z0-9-]+$", i) for i in ids))

    def test_a_judge_and_a_cabinet_officer_carry_no_party(self):
        self.assertNotIn('"party"', json.dumps(self.courts))
        self.assertNotIn('"party"', json.dumps(self.payload["supremeCourt"]))
        self.assertNotIn('"party"', json.dumps(self.payload["offices"]))
        # The President and the Vice President were elected on a ticket.
        self.assertTrue(self.payload["president"]["party"])

    def test_the_departments_are_in_the_order_of_succession(self):
        orders = [o["order"] for o in self.payload["offices"] if o["kind"] == "department"]
        self.assertEqual(sorted(orders), list(range(1, len(orders) + 1)))

    def test_the_search_lists_each_judge_under_each_court_they_sit_on(self):
        expected = sorted((j["id"], cid) for cid, c in self.courts.items() for j in c["judges"])
        self.assertEqual(sorted((row[0], row[2]) for row in self.search), expected)
        names = [(row[1], row[2]) for row in self.search]
        self.assertEqual(names, sorted(names))

    def test_a_retired_justice_is_never_a_member(self):
        scotus = self.payload["supremeCourt"]
        self.assertEqual(len(scotus["members"]), federal_courts.SUPREME_COURT_SEATS)
        self.assertFalse({j["id"] for j in scotus["members"]} & {j["id"] for j in scotus["retired"]})


class TestTheFiles(unittest.TestCase):
    """Each file is rewritten only when what it says changed, and verify
    names a stale one (rule 18)."""

    def test_written_files_carry_their_signature(self):
        payload, courts, search, _ = built()
        with tempfile.TemporaryDirectory() as tmp:
            written = emit.write_federal(payload, courts, search, tmp)
            self.assertEqual(len(written), len(courts) + 2)
            self.assertEqual(emit.check_federal(payload, courts, search, tmp), [])
            self.assertEqual(emit.write_federal(payload, courts, search, tmp), [])
            changed = dict(courts, ca1=dict(courts["ca1"], judges=courts["ca1"]["judges"][1:]))
            stale = emit.check_federal(payload, changed, search, tmp)
            self.assertEqual([os.path.basename(p) for p, _ in stale], ["ca1.js"])
            self.assertEqual(len(emit.write_federal(payload, changed, search, tmp)), 1)

    def test_a_court_file_adds_itself_to_the_courts_loaded(self):
        payload, courts, search, _ = built()
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_federal(payload, courts, search, tmp)
            with open(os.path.join(tmp, emit.JUDICIARY_DIR, "ca1.js"), encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn("window.kycCourt = window.kycCourt || {};", text)
        self.assertIn('window.kycCourt["ca1"] = ', text)


class TestThePages(unittest.TestCase):
    def test_a_court_page_loads_its_own_court_and_carries_no_names(self):
        html = pages.render_court_page("ca1", "example.org")
        self.assertIn('src="../data/judiciary/ca1.js"', html)
        self.assertIn('data-court="ca1"', html)
        # A court id in data-state would be remembered as the reader's state.
        self.assertIn('data-state=""', html)
        payload, courts, _, _ = built()
        for judge in courts["ca1"]["judges"]:
            self.assertNotIn(judge["name"], html)

    def test_the_hub_carries_no_names(self):
        html = pages.render_federal_page("example.org")
        payload, _, _, _ = built()
        self.assertNotIn(payload["president"]["name"], html)
        self.assertIn('src="../data/judiciary/index.js"', html)

    def test_every_federal_page_loads_its_scripts_in_order(self):
        found = {page: (ok, note) for page, ok, note in emit.check_pages(ROOT)
                 if page.startswith(("federal/", "courts/"))}
        self.assertEqual(len(found), len(federal_courts.COURTS) + 1)
        self.assertEqual({p: n for p, (ok, n) in found.items() if not ok}, {})

    def test_the_sitemap_lists_every_court(self):
        text = pages.sitemap("example.org", ["TX"], courts=tuple(federal_courts.COURTS))
        self.assertIn("https://example.org/federal/index.html", text)
        for cid in federal_courts.COURTS:
            self.assertIn(f"https://example.org/courts/{cid}.html", text)


if __name__ == "__main__":
    unittest.main()
