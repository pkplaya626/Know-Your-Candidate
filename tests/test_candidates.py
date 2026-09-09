"""Tests for the FEC candidate field and the House disclosure links.

The roster carried 57 hand-curated challengers, which made the site report 436
of 474 races as having no declared challenger when only four of them actually
did. Both modules here exist to stop the site making claims about races and
about people's money that it cannot support.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import candidates, disclosures, validate  # noqa: E402
from kyc.photos import PLACEHOLDER  # noqa: E402
from kyc.profiles import build_profiles  # noqa: E402
from kyc.sources import load_all  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def filing(candidate_id="H6TX01234", name="DOE, JANE", office="H", state="TX",
           district=1, party="DEM", receipts=100000.0, challenge="C",
           coverage="2026-06-30"):
    return {
        "candidate_id": candidate_id, "name": name, "office": office,
        "state": state, "district_number": district, "party": party,
        "party_full": None, "receipts": receipts, "disbursements": 1000.0,
        "cash_on_hand_end_period": 500.0, "coverage_end_date": coverage,
        "incumbent_challenge": challenge, "candidate_status": "C",
        "has_raised_funds": True,
    }


class TestDisplayName(unittest.TestCase):
    """The FEC files people as "CARL, JERRY LEE, JR"."""

    def check(self, filed, expected):
        self.assertEqual(candidates.display_name(filed), expected)

    def test_surname_moves_to_the_end(self):
        self.check("WAHAB, AISHA", "Aisha Wahab")

    def test_a_trailing_suffix_stays_at_the_end(self):
        self.check("CARL, JERRY LEE, JR", "Jerry Lee Carl Jr.")
        self.check("DOE, JOHN JR.", "John Doe Jr.")
        self.check("KENNEDY, JOHN F III", "John F Kennedy III")

    def test_an_honorific_is_dropped(self):
        # "Brian J Mr. Burley" reads as noise, and Mr. is not part of a name.
        self.check("BURLEY, BRIAN J MR.", "Brian J Burley")

    def test_irish_and_scottish_prefixes(self):
        self.check("O'BRIEN, MARY", "Mary O'Brien")
        self.check("MCCARTHY, KEVIN", "Kevin McCarthy")
        self.check("MACDONALD, IAIN", "Iain MacDonald")

    def test_hyphenated_surnames(self):
        self.check("OCASIO-CORTEZ, ALEXANDRIA", "Alexandria Ocasio-Cortez")

    def test_particles_stay_lowercase_inside_a_name(self):
        self.check("VAN DER BERG, PIETER", "Pieter van der Berg")

    def test_professional_suffixes(self):
        self.check("SMITH, JANE MD", "Jane Smith M.D.")

    def test_empty_and_single_token(self):
        self.check("", "")
        self.check("SINGLE NAME", "Single Name")

    def test_nothing_but_an_honorific_is_ever_dropped(self):
        # Every other token survives, in some order and casing.
        filed = "ARENHOLZ, ASHLEY HINSON"
        rendered = candidates.display_name(filed).lower().split()
        for token in ("arenholz", "ashley", "hinson"):
            self.assertIn(token, rendered)


class TestCacheShape(unittest.TestCase):
    def test_one_row_per_candidate(self):
        # /candidates/totals/ returns a row per two-year period, so a repeat
        # filer arrives more than once and would inflate every filing count.
        rows = [filing(receipts=10.0, coverage=None), filing(receipts=500.0)]
        cache = candidates.build_cache(rows)
        self.assertEqual(cache["count"], 1)
        self.assertEqual(cache["candidates"][0]["receipts"], 500.0)

    def test_the_row_with_real_totals_wins(self):
        rows = [filing(receipts=900.0, coverage=None), filing(receipts=5.0)]
        self.assertEqual(
            candidates.build_cache(rows)["candidates"][0]["receipts"], 5.0
        )

    def test_rows_without_an_id_are_dropped(self):
        rows = [filing(), dict(filing(), candidate_id=None)]
        self.assertEqual(candidates.build_cache(rows)["count"], 1)

    def test_sorted_for_reviewable_diffs(self):
        rows = [filing(candidate_id="H9"), filing(candidate_id="H1")]
        ids = [r["candidate_id"] for r in candidates.build_cache(rows)["candidates"]]
        self.assertEqual(ids, ["H1", "H9"])

    def test_round_trips_through_disk(self):
        cache = candidates.build_cache([filing()])
        with tempfile.TemporaryDirectory() as tmp:
            candidates.save_cache(cache, tmp)
            self.assertEqual(candidates.load_cache(tmp), cache)

    def test_missing_cache_is_absence_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(candidates.load_cache(tmp))


class TestRaceMapping(unittest.TestCase):
    def test_house_race_id_matches_the_races_module(self):
        from kyc import races
        self.assertEqual(
            candidates.race_id(filing(office="H", state="TX", district=32)),
            races.race_id("House", "TX", 32),
        )

    def test_senate_race_id_matches(self):
        from kyc import races
        self.assertEqual(
            candidates.race_id(filing(office="S", state="IA")),
            races.race_id("Senate", "IA", None),
        )

    def test_at_large_is_district_zero(self):
        self.assertEqual(candidates.race_id(filing(state="WY", district=0)),
                         "H-WY-00-2026")

    def test_a_filing_with_no_district_has_no_race(self):
        self.assertIsNone(candidates.race_id(filing(district=None)))

    def test_filing_counts_include_everyone(self):
        # The whole point: a race is never called uncontested because the
        # people who filed for it happen to be under the money threshold.
        cache = candidates.build_cache([
            filing(candidate_id="H1", receipts=0.0),
            filing(candidate_id="H2", receipts=10.0),
            filing(candidate_id="H3", receipts=999999.0),
        ])
        self.assertEqual(candidates.filing_counts(cache), {"H-TX-01-2026": 3})


class TestEligibility(unittest.TestCase):
    def test_the_threshold_is_the_statutory_one(self):
        # 52 U.S.C. 30101(2). Not a number chosen to make a page look tidy.
        self.assertEqual(candidates.STATUTORY_THRESHOLD, 5000)

    def test_below_the_threshold_is_excluded(self):
        cache = candidates.build_cache([filing(receipts=4999.0)])
        self.assertEqual(candidates.eligible(cache), [])

    def test_at_the_threshold_is_included(self):
        cache = candidates.build_cache([filing(receipts=5000.0)])
        self.assertEqual(len(candidates.eligible(cache)), 1)

    def test_the_sitting_member_is_excluded(self):
        # They already have a profile built from the roster.
        cache = candidates.build_cache([filing(challenge="I", receipts=1e6)])
        self.assertEqual(candidates.eligible(cache), [])


class TestToProfiles(unittest.TestCase):
    def existing(self, **kwargs):
        base = {"id": "X1", "name": "Jane Doe", "state": "TX", "chamber": "House",
                "isCandidate": False}
        base.update(kwargs)
        return base

    def test_builds_a_profile(self):
        cache = candidates.build_cache([filing()])
        made, _ = candidates.to_profiles(cache, [])
        self.assertEqual(len(made), 1)
        person = made[0]
        self.assertEqual(person["id"], "FEC_H6TX01234")
        self.assertEqual(person["name"], "Jane Doe")
        self.assertEqual(person["state"], "TX")
        self.assertTrue(person["isCandidate"])
        self.assertEqual(person["financeSource"], "FEC")
        self.assertEqual(person["source"], "fec-field")

    def test_the_filed_name_is_kept(self):
        # The display name is derived; the source of it stays visible.
        made, _ = candidates.to_profiles(candidates.build_cache([filing()]), [])
        self.assertEqual(made[0]["filedName"], "DOE, JANE")

    def test_no_speculative_portrait_urls(self):
        # 1,979 guessed Wikipedia URLs is ~4,000 requests that 404 and took
        # the page's load event to 59 seconds.
        made, _ = candidates.to_profiles(candidates.build_cache([filing()]), [])
        self.assertEqual(made[0]["photos"], [PLACEHOLDER])

    def test_editorial_fields_are_left_empty_not_invented(self):
        made, _ = candidates.to_profiles(candidates.build_cache([filing()]), [])
        for field in ("education", "platforms", "committees", "net_worth",
                      "previous_professions", "funding_sources"):
            self.assertEqual(made[0][field], "", field)

    def test_deduped_against_an_existing_fec_id(self):
        cache = candidates.build_cache([filing()])
        have = [self.existing(fecCandidateId="H6TX01234")]
        made, skipped = candidates.to_profiles(cache, have)
        self.assertEqual((len(made), skipped), (0, 1))

    def test_deduped_against_an_existing_person(self):
        cache = candidates.build_cache([filing()])
        have = [self.existing(name="Jane Doe", state="TX", chamber="House (Candidate)")]
        made, skipped = candidates.to_profiles(cache, have)
        self.assertEqual((len(made), skipped), (0, 1))

    def test_the_same_name_in_another_chamber_is_a_different_person(self):
        # Rule 3: never key on name alone. A House candidate and a Senate
        # candidate sharing a name are two people until proven otherwise.
        cache = candidates.build_cache([filing(office="S", district=None)])
        have = [self.existing(name="Jane Doe", state="TX", chamber="House")]
        made, _ = candidates.to_profiles(cache, have)
        self.assertEqual(len(made), 1)

    def test_at_large_district_label(self):
        cache = candidates.build_cache([filing(state="WY", district=0)])
        made, _ = candidates.to_profiles(cache, [])
        self.assertEqual(made[0]["district"], "AL")

    def test_party_codes_become_names(self):
        for code, expected in (("DEM", "Democrat"), ("REP", "Republican"),
                               ("LIB", "Libertarian"), ("IND", "Independent")):
            self.assertEqual(candidates.party_label(filing(party=code)), expected)


class TestAgainstTheRealField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = candidates.load_cache(ROOT)

    def test_the_field_is_committed(self):
        self.assertIsNotNone(self.cache, "run: python build_profile_site.py field")

    def test_no_duplicate_candidate_ids(self):
        ids = [r["candidate_id"] for r in self.cache["candidates"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_eligible_filing_maps_to_a_race(self):
        for row in candidates.eligible(self.cache):
            self.assertIsNotNone(candidates.race_id(row), row["candidate_id"])

    def test_no_sitting_member_is_in_the_eligible_set(self):
        for row in candidates.eligible(self.cache):
            self.assertNotEqual(row.get("incumbent_challenge"), "I")

    def test_the_built_site_has_no_duplicate_ids(self):
        raw = load_all(ROOT)
        profiles, _ = build_profiles(raw, field=self.cache)
        ids = [p["id"] for p in profiles]
        self.assertEqual(len(ids), len(set(ids)))


class TestDuplicateDetection(unittest.TestCase):
    """Reported, never merged."""

    def person(self, pid, name, race="S-AK-2026"):
        return {"id": pid, "name": name, "raceId": race}

    def test_a_prefix_given_name_is_flagged(self):
        pair = [self.person("A", "Dan Sullivan"),
                self.person("B", "Daniel J Sullivan")]
        issues = validate.check_duplicate_people(pair)
        self.assertEqual([i.code for i in issues], ["possible-duplicate-person"])
        self.assertEqual(issues[0].level, "warn")

    def test_different_surnames_are_not_flagged(self):
        pair = [self.person("A", "Dan Sullivan"), self.person("B", "Dan Murkowski")]
        self.assertEqual(validate.check_duplicate_people(pair), [])

    def test_different_given_names_are_not_flagged(self):
        # Troy and Trever Nehls are brothers, both real candidates.
        pair = [self.person("A", "Troy Nehls"), self.person("B", "Trever Nehls")]
        self.assertEqual(validate.check_duplicate_people(pair), [])

    def test_different_races_are_not_compared(self):
        pair = [self.person("A", "Dan Sullivan", "S-AK-2026"),
                self.person("B", "Daniel Sullivan", "S-TX-2026")]
        self.assertEqual(validate.check_duplicate_people(pair), [])

    def test_profiles_outside_a_race_are_ignored(self):
        pair = [{"id": "A", "name": "Dan Sullivan", "raceId": None},
                {"id": "B", "name": "Daniel Sullivan", "raceId": None}]
        self.assertEqual(validate.check_duplicate_people(pair), [])

    def test_nothing_is_removed(self):
        pair = [self.person("A", "Dan Sullivan"), self.person("B", "Daniel Sullivan")]
        validate.check_duplicate_people(pair)
        self.assertEqual(len(pair), 2)


class TestDisclosures(unittest.TestCase):
    def member(self, name="Robert Aderholt", state="AL", district=4, pid="A000055"):
        return {"id": pid, "name": name, "state": state, "chamber": "House",
                "districtNum": district, "isCandidate": False}

    def filing(self, last="Aderholt", first="Robert", seat="AL04", kind="O",
               year="2025", filed="5/12/2026", doc="123"):
        return {"last": last, "first": first, "seat": seat, "type": kind,
                "year": year, "filed": filed, "doc": doc}

    def test_seat_code(self):
        self.assertEqual(disclosures.seat_code(self.member()), "AL04")
        self.assertEqual(
            disclosures.seat_code(dict(self.member(), districtNum=None)), "AL00"
        )

    def test_senators_have_no_seat_code(self):
        senator = dict(self.member(), chamber="Senate")
        self.assertIsNone(disclosures.seat_code(senator))

    def test_matches_an_annual_report(self):
        found = disclosures.match([self.member()], [self.filing()])
        self.assertIn("A000055", found)
        self.assertTrue(found["A000055"]["url"].endswith("/2025/123.pdf"))

    def test_ignores_non_annual_filings(self):
        # Periodic transaction reports and extensions are not what a reader
        # following a link from "net worth" is looking for.
        for kind in ("P", "X", "C", "W", "T"):
            self.assertEqual(disclosures.match([self.member()],
                                               [self.filing(kind=kind)]), {})

    def test_requires_the_first_initial_to_agree(self):
        # A district can hold a member and a same-surname candidate.
        other = self.filing(first="Sandra")
        self.assertEqual(disclosures.match([self.member()], [other]), {})

    def test_requires_the_seat_to_agree(self):
        self.assertEqual(
            disclosures.match([self.member()], [self.filing(seat="AL05")]), {}
        )

    def test_the_most_recently_filed_report_wins(self):
        old = self.filing(doc="111", filed="5/01/2026")
        new = self.filing(doc="222", filed="8/13/2026", kind="A")
        found = disclosures.match([self.member()], [old, new])
        self.assertEqual(found["A000055"]["doc"], "222")

    def test_candidates_are_skipped(self):
        candidate = dict(self.member(), isCandidate=True)
        self.assertEqual(disclosures.match([candidate], [self.filing()]), {})

    def test_apply_cache_attaches_the_link(self):
        member = self.member()
        found = disclosures.match([member], [self.filing()])
        self.assertEqual(disclosures.apply_cache([member], found), 1)
        self.assertTrue(member["disclosureUrl"].startswith("https://"))
        self.assertEqual(member["disclosureYear"], "2025")

    def test_no_net_worth_is_ever_derived(self):
        # Disclosures report assets in bands; a single figure from one would
        # be an estimate presented as a fact.
        member = self.member()
        disclosures.apply_cache([member], disclosures.match([member], [self.filing()]))
        self.assertNotIn("net_worth", member)


class TestDisclosuresAgainstRealData(unittest.TestCase):
    def test_only_house_members_are_linked(self):
        raw = load_all(ROOT)
        profiles, _ = build_profiles(raw)
        cache = disclosures.load_cache(ROOT)
        if not cache:
            self.skipTest("no disclosure cache committed")
        disclosures.apply_cache(profiles, cache)
        wrong = [
            p["name"] for p in profiles
            if p.get("disclosureUrl") and p["chamber"] != "House"
        ]
        self.assertEqual(wrong, [])

    def test_every_link_points_at_the_house_clerk(self):
        for record in (disclosures.load_cache(ROOT) or {}).values():
            self.assertTrue(
                record["url"].startswith("https://disclosures-clerk.house.gov/"),
                record["url"],
            )


if __name__ == "__main__":
    unittest.main()
