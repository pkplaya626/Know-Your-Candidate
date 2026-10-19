"""Tests for outside spending (kyc/outside.py): independent expenditures for
and against each candidate, read from the FEC by candidate id, paged on a
unique key and counted, and attributed only to the profile whose id, office
and state they carry (rule 20). Each side is its own total, never a net.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import outside  # noqa: E402


def _row(cid, committee, side, total, cycle=2026):
    return {"candidate_id": cid, "committee_id": committee, "committee_name": committee + " PAC",
            "support_oppose_indicator": side, "total": total, "count": 1, "cycle": cycle}


class FakeFec:
    """Answers like OpenFEC: one page of the rows for the ids asked."""

    def __init__(self, rows, shuffle_pages=False):
        self.rows = rows
        self.calls = []
        self.shuffle_pages = shuffle_pages

    def __call__(self, path, params):
        self.calls.append(params)
        ids = params["candidate_id"]
        rows = [r for r in self.rows if r["candidate_id"] in ids]
        side = params.get("support_oppose_indicator")
        if side:
            rows = [r for r in rows if r["support_oppose_indicator"] == side]
        if params.get("sort") == "committee_id" and not self.shuffle_pages:
            rows = sorted(rows, key=lambda r: r["committee_id"])
        per, page = params["per_page"], params["page"]
        start = (page - 1) * per
        chunk = rows[start:start + per]
        if self.shuffle_pages and page > 1:
            chunk = rows[:per][: len(chunk)]          # ties reshuffled: repeats
        pages = max(1, -(-len(rows) // per))
        return {"pagination": {"count": len(rows), "pages": pages}, "results": chunk}


class TestFetch(unittest.TestCase):

    def test_rows_arrive_by_candidate_and_side(self):
        get = FakeFec([_row("S6NC00407", "C1", "S", 100.0), _row("S6NC00407", "C2", "O", 50.5),
                       _row("H6TX32001", "C3", "O", 7.0)])
        cache = outside.fetch(["S6NC00407", "H6TX32001", None, "nonsense"], get=get,
                              today="2026-10-18")
        self.assertEqual(cache["asked"], 2)
        self.assertEqual(cache["candidates"]["S6NC00407"]["support"][0]["total"], 100.0)
        self.assertEqual(cache["candidates"]["S6NC00407"]["oppose"][0]["committeeId"], "C2")
        self.assertEqual(cache["read"], "2026-10-18")
        # The 2025-26 cycle alone, not a senator's six-year period.
        self.assertTrue(all(c["election_full"] == "false" for c in get.calls))

    def test_a_batch_over_a_page_is_split(self):
        rows = [_row("H6TX%05d" % i, "C%03d" % j, "S", 1.0) for i in range(3) for j in range(60)]
        get = FakeFec(rows)
        cache = outside.fetch(["H6TX%05d" % i for i in range(3)], get=get)
        self.assertEqual(sum(len(v["support"]) for v in cache["candidates"].values()), 180)

    def test_one_candidate_over_a_page_is_paged_side_by_side_and_counted(self):
        rows = [_row("S8GA00180", "C%03d" % j, "S", 1.0) for j in range(150)]
        cache = outside.fetch(["S8GA00180"], get=FakeFec(rows))
        self.assertEqual(len(cache["candidates"]["S8GA00180"]["support"]), 150)

    def test_rows_that_repeat_across_pages_are_refused(self):
        # Sorted on a key with ties, the API repeated rows across pages and
        # skipped as many (rule 36).
        rows = [_row("S8GA00180", "C%03d" % j, "S", 1.0) for j in range(150)]
        with self.assertRaises(outside.OutsideError):
            outside.fetch(["S8GA00180"], get=FakeFec(rows, shuffle_pages=True))


class TestApply(unittest.TestCase):

    def _cache(self):
        return {"read": "2026-10-18", "cycle": 2026, "asked": 3, "candidates": {
            "S6NC00407": {"support": [{"committeeId": "C1", "committee": "ONE", "total": 300.0,
                                       "count": 2}],
                          "oppose": [{"committeeId": "C2", "committee": "TWO", "total": 900.0,
                                      "count": 1},
                                     {"committeeId": "C3", "committee": "THREE", "total": 100.0,
                                      "count": 1}]},
            "H6NC04001": {"support": [{"committeeId": "C9", "committee": "NINE", "total": 5.0,
                                       "count": 1}], "oppose": []},
        }}

    def test_each_side_is_its_own_total_and_its_committees_are_listed(self):
        profile = {"name": "Roy Cooper", "chamber": "Senate", "state": "NC",
                   "fecCandidateId": "S6NC00407", "officeLabel": "Senate • NC"}
        applied, refused = outside.apply([profile], self._cache())
        self.assertEqual((applied, refused), (1, []))
        out = profile["outsideSpending"]
        self.assertEqual((out["support"], out["oppose"]), (300.0, 1000.0))
        self.assertEqual([c["committee"] for c in out["opposeTop"]], ["TWO", "THREE"])
        self.assertNotIn("net", out)
        self.assertIn("candidate_id=S6NC00407", out["url"])
        self.assertEqual(out["asOf"], "2026-10-18")

    def test_an_id_for_another_seat_is_refused(self):
        # A House id on a Senate profile, and an id from another state.
        senate = {"name": "Someone", "chamber": "Senate", "state": "NC",
                  "fecCandidateId": "H6NC04001", "officeLabel": "Senate • NC"}
        elsewhere = {"name": "Another", "chamber": "Senate", "state": "VA",
                     "fecCandidateId": "S6NC00407", "officeLabel": "Senate • VA"}
        applied, refused = outside.apply([senate, elsewhere], self._cache())
        self.assertEqual(applied, 0)
        self.assertEqual(len(refused), 2)
        self.assertNotIn("outsideSpending", senate)
        problems = outside.problems(self._cache(), refused)
        self.assertEqual(problems[0][:2], ("error", "outside-attribution"))

    def test_one_committee_under_two_of_a_persons_ids_is_one_group(self):
        # Tricia Pridemore's GOPAC money, filed under both her House ids,
        # read "3 groups" for two and was listed twice.
        cache = {"read": "2026-10-18", "cycle": 2026, "candidates": {
            "H4GA11087": {"support": [{"committeeId": "C7", "committee": "GOPAC", "total": 200.0,
                                       "count": 1}], "oppose": []},
            "H6GA11207": {"support": [{"committeeId": "C7", "committee": "GOPAC", "total": 90.0,
                                       "count": 2},
                                      {"committeeId": "C8", "committee": "WFW", "total": 100.0,
                                       "count": 1}], "oppose": []}}}
        profile = {"name": "Tricia Pridemore", "chamber": "House", "state": "GA",
                   "fecCandidateId": "H4GA11087", "otherFecIds": ["H6GA11207"]}
        outside.apply([profile], cache)
        out = profile["outsideSpending"]
        self.assertEqual(out["supportCommittees"], 2)
        self.assertEqual(out["supportTop"], [{"committee": "GOPAC", "total": 290},
                                             {"committee": "WFW", "total": 100}])
        self.assertEqual(out["support"], 390.0)

    def test_a_members_other_candidacy_is_labelled_and_never_summed(self):
        # Andy Barr's House id carries outside money for a House race he is
        # not running; his Senate filing carries its own. Each stays where
        # the FEC filed it, and the Senate campaign carries the other apart.
        member = {"id": "M1", "name": "Andy Barr", "chamber": "House", "state": "NC",
                  "fecCandidateId": "H6NC04001", "alsoRunningId": "C1"}
        running = {"id": "C1", "name": "Andy Barr", "chamber": "Senate", "state": "NC",
                   "fecCandidateId": "S6NC00407"}
        outside.apply([member, running], self._cache())
        self.assertEqual(member["outsideSpending"]["runningElsewhere"], "C1")
        self.assertEqual(member["outsideSpending"]["candidacy"], "House")
        self.assertEqual(running["outsideSpending"]["support"], 300.0)
        self.assertEqual(running["outsideSpendingOther"]["support"], 5.0)
        self.assertEqual(running["outsideSpendingOther"]["candidacy"], "House")
        self.assertNotIn("runningElsewhere", running["outsideSpendingOther"])

    def test_a_profile_with_no_id_is_never_matched_by_name(self):
        profile = {"name": "Roy Cooper", "chamber": "Senate", "state": "NC",
                   "officeLabel": "Senate • NC"}
        self.assertEqual(outside.apply([profile], self._cache()), (0, []))
        self.assertNotIn("outsideSpending", profile)


if __name__ == "__main__":
    unittest.main()
