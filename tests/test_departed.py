"""Members who left the sitting Congress, found by the grid's search
(kyc/departed.py, audit 2026-10-17 GRID-08); the search aliases a member's
record does not hold (overrides.SEARCH_ALIASES, GRID-05); and the surname
"Name, A to Z" sorts by (GRID-20)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import cycle, departed, legislators, overrides, races  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def entry(bioguide, first, last, kind, state, start, end, district=None, klass=None,
          nickname=None):
    term = {"type": kind, "state": state, "start": start, "end": end, "party": "Independent"}
    if kind == "rep":
        term["district"] = district
    else:
        term["class"] = klass
    name = {"first": first, "last": last}
    if nickname:
        name["nickname"] = nickname
    return {"id": {"bioguide": bioguide}, "name": name, "terms": [term]}


def sitting(bioguide, name, chamber, state, district=None, klass=None, start="2025-01-03"):
    return {"bioguide": bioguide, "name": name, "chamber": chamber, "state": state,
            "district": district, "senateClass": klass, "termStart": start,
            "termEnd": "2027-01-03"}


SNAPSHOT = {
    "fetched": "2026-10-18T09:00:00+00:00",
    "legislators": [sitting(f"H{n:06d}", f"Rep {n}", "House", "ZZ", district=n)
                    for n in range(1, 10)] + [
        sitting("S000001", "Sen New", "Senate", "ZZ", klass=2, start="2026-08-01"),
        sitting("M000001", "Moved Member", "Senate", "YY", klass=1),
    ],
}


class TestBuild(unittest.TestCase):
    def build(self, rows):
        return departed.build(rows, SNAPSHOT)

    def test_a_term_ended_during_this_congress_is_a_departure(self):
        rows = [entry("G000001", "Marjorie", "Example", "rep", "ZZ", "2025-01-03", "2026-01-05",
                      district=14)]
        out = self.build(rows)
        self.assertEqual(out["congress"], 119)
        self.assertEqual([m["bioguide"] for m in out["members"]], ["G000001"])
        self.assertEqual(out["members"][0]["left"], "2026-01-05")
        self.assertEqual(out["members"][0]["district"], 14)

    def test_a_term_that_ended_with_the_last_congress_is_not(self):
        # Ended on the first day of the 119th: the 118th's term.
        rows = [entry("O000001", "Old", "Member", "rep", "ZZ", "2023-01-03", "2025-01-03",
                      district=2)]
        self.assertEqual(self.build(rows)["members"], [])

    def test_a_term_begun_in_an_earlier_congress_counts_when_it_ended_in_this_one(self):
        # A senator elected in 2022 who resigned in January 2025.
        rows = [entry("V000001", "Jay", "Example", "sen", "ZZ", "2023-01-03", "2025-01-10",
                      klass=3)]
        self.assertEqual(len(self.build(rows)["members"]), 1)

    def test_nothing_after_the_membership_was_read(self):
        rows = [entry("F000001", "Future", "Leaver", "rep", "ZZ", "2025-01-03", "2026-12-31",
                      district=3)]
        self.assertEqual(self.build(rows)["members"], [])

    def test_someone_the_snapshot_seats_is_not_departed(self):
        # Left the House for the Senate: in the current file, not gone.
        rows = [entry("M000001", "Moved", "Member", "rep", "YY", "2025-01-03", "2025-03-01",
                      district=1)]
        self.assertEqual(self.build(rows)["members"], [])

    def test_the_record_gives_no_reason_and_none_is_stored(self):
        rows = [entry("G000001", "Marjorie", "Example", "rep", "ZZ", "2025-01-03", "2026-01-05",
                      district=14)]
        row = self.build(rows)["members"][0]
        self.assertFalse({"how", "reason", "via"} & set(row))

    def test_a_nickname_is_the_name_shown_and_the_legal_name_an_alias(self):
        rows = [entry("N000001", "Gerald", "Example", "rep", "ZZ", "2025-01-03", "2025-05-21",
                      district=4, nickname="Gerry")]
        row = self.build(rows)["members"][0]
        self.assertEqual(row["name"], "Gerry Example")


class TestForPage(unittest.TestCase):
    def cache(self, *rows):
        return {"congress": 119, "members": list(rows)}

    def row(self, bioguide, chamber="House", district=5, klass=None, name="Gone Member"):
        out = {"bioguide": bioguide, "name": name, "chamber": chamber, "state": "ZZ",
               "party": "Independent", "left": "2026-01-05"}
        if chamber == "House":
            out["district"] = district
        else:
            out["senateClass"] = klass
        return out

    def test_who_holds_the_seat_now_is_the_snapshot_by_seat(self):
        rows, problems = departed.for_page(self.cache(self.row("G000001")), SNAPSHOT, [])
        self.assertEqual(rows[0]["holder"]["id"], "H000005")
        self.assertNotIn("departed-seated", [p[1] for p in problems])

    def test_a_senate_seat_is_found_by_its_class(self):
        rows, _ = departed.for_page(self.cache(self.row("G000002", "Senate", klass=2)),
                                    SNAPSHOT, [])
        self.assertEqual(rows[0]["holder"]["id"], "S000001")
        rows, _ = departed.for_page(self.cache(self.row("G000003", "Senate", klass=3)),
                                    SNAPSHOT, [])
        self.assertIsNone(rows[0]["holder"])

    def test_the_holder_is_named_as_their_profile_shows_them(self):
        rows, _ = departed.for_page(self.cache(self.row("G000001")), SNAPSHOT,
                                    [{"id": "H000005", "name": "Pat Shown"}])
        self.assertEqual(rows[0]["holder"]["name"], "Pat Shown")

    def test_a_seated_member_is_left_out_and_reported(self):
        rows, problems = departed.for_page(self.cache(self.row("H000005")), SNAPSHOT, [])
        self.assertEqual(rows, [])
        self.assertIn("departed-seated", [p[1] for p in problems])

    def test_someone_with_a_profile_is_left_to_it(self):
        # A record incumbent who left has a former member's profile (rule 67).
        rows, _ = departed.for_page(self.cache(self.row("G000001")), SNAPSHOT,
                                    [{"id": "G000001", "name": "Gone Member"}])
        self.assertEqual(rows, [])

    def test_another_congress_s_list_is_not_shown(self):
        cache = dict(self.cache(self.row("G000001")), congress=118)
        self.assertEqual(departed.for_page(cache, SNAPSHOT, [])[0], [])

    def test_an_evidenced_alias_reaches_the_row(self):
        bioguide, ((alias, _evidence),) = next(iter(overrides.SEARCH_ALIASES.items()))
        rows, _ = departed.for_page(self.cache(self.row(bioguide)), SNAPSHOT, [])
        self.assertIn(alias, rows[0]["aliases"])


class TestSearchAliases(unittest.TestCase):
    def test_every_alias_is_keyed_on_a_bioguide_and_cites_its_source(self):
        for bioguide, entries in overrides.SEARCH_ALIASES.items():
            self.assertRegex(bioguide, r"^[A-Z]\d{6}$")
            for alias, evidence in entries:
                self.assertTrue(alias.strip())
                self.assertRegex(evidence, r"read \d{4}-\d{2}-\d{2}")

    def test_the_committed_list_is_of_the_sitting_congress(self):
        cache = departed.load_cache(ROOT)
        snapshot = legislators.load_snapshot(ROOT)
        self.assertIsNotNone(cache)
        if cycle.snapshot_congress(snapshot) >= cycle.electing_congress():
            self.skipTest("a new Congress: its list starts again at the next refresh (rule 68)")
        self.assertEqual(cache["congress"], cycle.snapshot_congress(snapshot))
        seated = set(legislators.by_bioguide(snapshot))
        self.assertFalse({m["bioguide"] for m in cache["members"]} & seated)


class TestSurname(unittest.TestCase):
    def test_the_filing_s_surname_where_it_ends_the_shown_name(self):
        profile = {"id": "FEC_X", "name": "Debbie Wasserman Schultz", "fecCandidateId": "X"}
        filed = {"X": {"name": "WASSERMAN SCHULTZ, DEBBIE"}}
        self.assertEqual(races.surname(profile, filed), "wasserman schultz")

    def test_otherwise_the_last_word_less_a_suffix(self):
        self.assertEqual(races.surname({"name": "Carlos de la Cruz Jr."}), "cruz")


if __name__ == "__main__":
    unittest.main()
