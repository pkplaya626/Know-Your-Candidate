"""What the job pays (PROFILES-25): kyc/pay.py's table and who gets a figure."""

import datetime
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import cycle, legislators, pay  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def member(bioguide="A000001", **extra):
    return dict({"id": bioguide, "name": "A Member", "isCandidate": False}, **extra)


class TestTable(unittest.TestCase):
    def test_every_figure_is_in_the_words_read(self):
        quote = pay.SOURCES[0]["quote"]
        for amount in {pay.MEMBER, *pay.POSTS.values()}:
            self.assertIn(f"${amount:,}", quote)
        self.assertIn(f"in {pay.YEAR}", quote)
        # The Senate's own page agrees on its members' and leaders' rates.
        self.assertIn(f"{pay.YEAR} ${pay.MEMBER:,}", pay.SOURCES[1]["quote"])
        self.assertIn(f"${pay.POSTS['Senate Majority Leader']:,}", pay.SOURCES[1]["quote"])
        for source in pay.SOURCES:
            self.assertTrue(source["url"].startswith("https://"))
            datetime.date.fromisoformat(source["read"])

    def test_the_year_is_the_congress_sitting_in_it(self):
        self.assertEqual(cycle.congress_for_date(datetime.date(pay.YEAR, 6, 1)), pay.CONGRESS)

    def test_a_post_sets_the_rate_and_the_highest_wins(self):
        self.assertEqual(pay.rate([]), (174000, None))
        self.assertEqual(pay.rate(["House Majority Whip"]), (174000, None))
        self.assertEqual(pay.rate(["Senate Majority Leader"]), (193400, "Senate Majority Leader"))
        self.assertEqual(pay.rate(["House Republican Conference Chair", "Speaker of the House"]),
                         (223500, "Speaker of the House"))

    def test_what_reads_as_a_post_paid_more(self):
        for title in pay.POSTS:
            self.assertTrue(pay.is_paid_kind(title), title)
        for title in ("Assistant House Minority Leader", "Senate Majority Whip",
                      "House Democratic Caucus Chair", "Deputy Minority Leader"):
            self.assertFalse(pay.is_paid_kind(title), title)


class TestWhoIsShownOne(unittest.TestCase):
    def test_only_a_sitting_member_in_the_tables_congress(self):
        people = [member("A000001"), member("B000002", leadership=["Speaker of the House"]),
                  member("C000003", formerMember={"left": "2026-01-20"}),
                  {"id": "H6XX00001", "name": "A Challenger", "isCandidate": True}]
        pay.apply(people, pay.CONGRESS)
        self.assertEqual([p.get("pay") for p in people],
                         [{"amount": 174000}, {"amount": 223500, "post": "Speaker of the House"},
                          None, None])
        # A membership of the next Congress: its leaders may not be recorded
        # on January 3, so nobody has a figure, not a member's rate for the
        # Speaker (rule 68).
        pay.apply(people, pay.CONGRESS + 1)
        self.assertFalse([p for p in people if "pay" in p])
        self.assertIsNone(pay.for_page(pay.CONGRESS + 1))
        self.assertEqual(pay.for_page(pay.CONGRESS)["member"], pay.MEMBER)

    def test_a_renamed_post_paid_more_fails_the_build(self):
        people = [member(leadership=["Speaker of the U.S. House"])]
        pay.apply(people, pay.CONGRESS)
        codes = {(s, c) for s, c, _m, _i in pay.problems(people, pay.CONGRESS,
                                                          datetime.date(pay.YEAR, 10, 1))}
        self.assertIn(("error", "pay-post-unknown"), codes)

    def test_a_past_year_warns(self):
        later = datetime.date(pay.YEAR + 1, 1, 2)
        codes = [c for _s, c, _m, _i in pay.problems([], pay.CONGRESS, later)]
        self.assertEqual(codes, ["pay-stale"])

    def test_the_committed_snapshots_posts_are_all_known(self):
        snapshot = legislators.load_snapshot(ROOT)
        sitting = cycle.snapshot_congress(snapshot)
        posts = {post for person in snapshot["legislators"]
                 for post in legislators.held_posts(person, sitting)}
        self.assertFalse(sorted(p for p in posts if pay.is_paid_kind(p) and p not in pay.POSTS))
        if sitting != pay.CONGRESS:
            self.skipTest("the membership is of another Congress than the table's")
        # Every post the table names is held by someone now.
        self.assertEqual(sorted(set(pay.POSTS) - posts), [])

    def test_the_page_names_no_figure_of_its_own(self):
        with open(os.path.join(ROOT, "candidate_profiles_site", "assets", "kyc-profile.js"),
                  encoding="utf-8") as handle:
            script = handle.read()
        self.assertFalse(re.findall(r"1[79]\d,\d00|223,500", script))


if __name__ == "__main__":
    unittest.main()
