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

    def test_credentials_and_titles_are_dropped_wherever_they_sit(self):
        # Treasurers type them into the given-name field, in any position:
        # the field held "Rudolph Dr. Moise", "M.D. Jd Razack Nizam" and
        # "Joseph Dr. Joe Ph.d. Arminio" before this.
        self.check("SMITH, JANE MD", "Jane Smith")
        self.check("MOISE, RUDOLPH DR.", "Rudolph Moise")
        self.check("RAZACK, MD JD, NIZAM", "Nizam Razack")
        self.check("ARMINIO, JOSEPH DR. JOE PH.D.", "Joseph Joe Arminio")
        self.check("GOOD, ROBERT G. HON.", "Robert G. Good")
        # A generational suffix is part of the name and stays.
        self.check("DAVIS, PAUL R DR. JR.", "Paul R Davis Jr.")
        # A name that is nothing but titles is not rendered down to nothing.
        self.check("DR. WHO", "Who")

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

    def test_the_election_period_is_carried(self):
        row = dict(filing(office="S", district=None), coverage_start_date="2021-01-01T00:00:00")
        made, _ = candidates.to_profiles(candidates.build_cache([row]), [])
        self.assertEqual(made[0]["financeSince"], "2021-01-01")
        self.assertEqual(made[0]["financeAsOf"], "2026-06-30")
        self.assertEqual(made[0]["financePeriod"], "election")
        self.assertEqual(made[0]["financeElection"], candidates.CYCLE)

    def test_a_field_cached_without_a_start_date_invents_none(self):
        # Caches written before coverage_start_date was kept.
        made, _ = candidates.to_profiles(candidates.build_cache([filing()]), [])
        self.assertIsNone(made[0]["financeSince"])
        self.assertEqual(made[0]["financePeriod"], "election")

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


class TestScreen(unittest.TestCase):
    """Registrations that list 2026 are not all 2026 candidacies."""

    CONTESTS = {"S-OK-2026", "H-TX-01-2026", "H-GA-14-2026", "H-NM-03-2026"}

    def test_the_current_period_wins_over_a_larger_earlier_one(self):
        # Ranking on receipts first put a previous period's money on a 2026
        # profile and made an active filer look stale.
        rows = [filing(receipts=900000.0, coverage="2024-12-31"),
                filing(receipts=12000.0, coverage="2026-06-30")]
        row = candidates.build_cache(rows)["candidates"][0]
        self.assertEqual((row["receipts"], row["coverage_end_date"]), (12000.0, "2026-06-30"))

    def test_a_registration_with_no_report_since_the_cycle_began_is_stale(self):
        # Jim Inhofe, S4OK00083: last report through 2022-12-31, shown as a
        # 2026 Oklahoma Senate candidate with his 2022 receipts.
        inhofe = filing("S4OK00083", "INHOFE, JAMES M. SEN.", "S", "OK", 0,
                        receipts=154687.18, coverage="2022-12-31")
        current = filing("S6OK00001", "ROE, RICHARD", "S", "OK", 0, coverage="2026-06-30")
        unreported = filing("S6OK00002", "POE, ED", "S", "OK", 0, receipts=0, coverage=None)
        cache = candidates.build_cache([inhofe, current, unreported])
        screened = candidates.screen(cache, self.CONTESTS)

        kept = {r["candidate_id"] for r in screened["candidates"]}
        self.assertEqual(kept, {"S6OK00001", "S6OK00002"})
        self.assertEqual([r["candidate_id"] for r in screened["screened"]["stale"]],
                         ["S4OK00083"])
        # Counted consistently: a stale registration is not a 2026 filing.
        self.assertEqual(candidates.filing_counts(screened), {"S-OK-2026": 2})
        profiles, _ = candidates.to_profiles(screened, [])
        self.assertEqual([p["fecCandidateId"] for p in profiles], ["S6OK00001"])
        # The input is not modified.
        self.assertEqual(cache["count"], 3)

    def test_the_first_day_of_the_cycle_is_current(self):
        row = filing(coverage="2025-01-01")
        screened = candidates.screen(candidates.build_cache([row]), self.CONTESTS)
        self.assertEqual(screened["count"], 1)

    def test_filings_for_races_that_do_not_exist_are_dropped(self):
        rows = [
            filing("S6CA00001", office="S", state="CA", district=0),   # no CA seat up
            filing("H6GA23001", state="GA", district=23),             # GA has 14
            filing("H6NM66001", state="NM", district=66),             # NM has 3
            filing("H6GA14001", state="GA", district=14),
            filing("H6NM03001", state="NM", district=3),
        ]
        screened = candidates.screen(candidates.build_cache(rows), self.CONTESTS)
        self.assertEqual({r["candidate_id"] for r in screened["candidates"]},
                         {"H6GA14001", "H6NM03001"})
        self.assertEqual(len(screened["screened"]["phantom"]), 3)
        self.assertEqual(set(candidates.filing_counts(screened)),
                         {"H-GA-14-2026", "H-NM-03-2026"})

    def test_validate_names_every_dropped_filing(self):
        import datetime

        rows = [filing("S4OK00083", "INHOFE, JAMES M. SEN.", "S", "OK", 0,
                       coverage="2022-12-31"),
                filing("H6GA23001", state="GA", district=23),
                filing("H6OR05234", state="OR", district=5, coverage="2026-12-31")]
        screened = candidates.screen(candidates.build_cache(rows), self.CONTESTS | {"H-OR-05-2026"})
        issues = validate.check_field_screen(screened, today=datetime.date(2026, 10, 1))
        by_code = {i.code: i for i in issues}
        self.assertEqual(set(by_code), {"field-stale", "field-phantom-race",
                                        "field-future-coverage"})
        self.assertTrue(all(i.level == "warn" for i in issues))
        self.assertIn("S4OK00083", by_code["field-stale"].detail[0])
        self.assertIn("H-GA-23-2026", by_code["field-phantom-race"].detail[0])
        self.assertIn("H6OR05234", by_code["field-future-coverage"].detail[0])


class TestContestable(unittest.TestCase):
    """Races exist only for real seats, counted from the roster."""

    @classmethod
    def setUpClass(cls):
        from kyc import races

        cls.profiles, cls.stats = build_profiles(load_all(ROOT))
        cls.contests = races.contestable(cls.profiles)

    def test_senate_races_are_exactly_the_seats_up(self):
        senate = {c for c in self.contests if c.startswith("S-")}
        up = {f"S-{p['state']}-2026" for p in self.profiles
              if not p["isCandidate"] and "Senate" in p["chamber"] and p["seatUp2026"]}
        self.assertEqual(senate, up)
        self.assertEqual(len(senate), validate.EXPECTED_SENATE_UP_2026)
        for state in ("CA", "NY", "PA", "AZ"):
            self.assertNotIn(f"S-{state}-2026", self.contests)

    def test_house_districts_are_the_states_seats(self):
        held = {}
        for p in self.profiles:
            if not p["isCandidate"] and p["chamber"] == "House":
                held.setdefault(p["state"], set()).add(p["districtNum"])
        for state, districts in held.items():
            ours = {c for c in self.contests if c.startswith(f"H-{state}-")}
            if state == "PR":
                self.assertEqual(ours, set())
            elif max(districts) == 0:
                self.assertEqual(ours, {f"H-{state}-00-2026"})
            else:
                self.assertEqual(len(ours), max(districts), state)
        self.assertNotIn("H-GA-23-2026", self.contests)
        self.assertNotIn("H-NM-66-2026", self.contests)
        self.assertIn("H-GA-14-2026", self.contests)

    def test_the_built_site_has_no_phantom_race(self):
        from kyc import races

        field = candidates.load_cache(ROOT)
        profiles, _ = build_profiles(load_all(ROOT), field=field)
        built = {r["id"] for r in races.build(profiles)}
        self.assertLessEqual(built, races.contestable(profiles))


class TestAgainstTheRealField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = candidates.load_cache(ROOT)

    def test_no_stale_registration_becomes_a_profile(self):
        raw = load_all(ROOT)
        profiles, _ = build_profiles(raw, field=self.cache)
        ids = {p.get("fecCandidateId") for p in profiles if p.get("source") == "fec-field"}
        self.assertNotIn("S4OK00083", ids)   # Jim Inhofe, last report 2022-12-31
        for p in profiles:
            if p.get("source") == "fec-field":
                self.assertGreaterEqual(p["financeAsOf"], candidates.cycle_start(), p["id"])

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


class TestFieldPagination(unittest.TestCase):
    """The FEC pages with LIMIT/OFFSET; a sort with ties shuffles between pages.

    Sorted on "-receipts", one fetch returned 3,754 rows of which only 3,342
    were distinct: about one filing in nine was silently missing, a different
    set each refresh, and a sitting member's filing went with it.
    """

    def setUp(self):
        from kyc import fec
        self.fec = fec
        self.real = fec.fetch_pages

    def tearDown(self):
        self.fec.fetch_pages = self.real

    @staticmethod
    def rows(n, office="H"):
        return [{"candidate_id": f"{office}{i:04d}", "cycle": 2026, "office": office,
                 "name": f"P{i}"} for i in range(n)]

    def test_the_field_is_paged_on_a_unique_key(self):
        self.assertEqual(candidates.FIELD_SORT, ("candidate_id", "cycle"))

    def test_a_shuffled_fetch_is_retried_until_every_row_arrives_once(self):
        calls = []

        def fake(path, params, sort):
            calls.append(params["office"])
            good = self.rows(5, params["office"])
            if calls.count(params["office"]) == 1:
                return good[:4] + good[:1], 5     # one row twice, one missing
            return good, 5

        self.fec.fetch_pages = fake
        log = []
        out = candidates.fetch(log=log.append)
        self.assertEqual(len(out), 10)
        self.assertEqual(len({r["candidate_id"] for r in out}), 10)
        self.assertTrue(any("fetching again" in line for line in log))

    def test_a_field_that_never_arrives_whole_is_refused(self):
        self.fec.fetch_pages = lambda path, params, sort: (self.rows(3) + self.rows(1), 4)
        with self.assertRaises(candidates.FieldError):
            candidates.fetch(log=lambda *_: None, attempts=2)

    def test_fetch_pages_sends_the_sort_and_reads_every_page(self):
        from kyc import fec
        real_get = fec._get
        seen = []

        def fake_get(path, params, retries=4):
            seen.append(params)
            page = params["page"]
            return {"results": [{"n": page}], "pagination": {"count": 2, "pages": 2}}

        fec._get = fake_get
        try:
            rows, count = fec.fetch_pages("/x/", {"a": 1}, ("k", "j"), pause=0)
        finally:
            fec._get = real_get
        self.assertEqual((rows, count), ([{"n": 1}, {"n": 2}], 2))
        self.assertEqual([p["sort"] for p in seen], [["k", "j"], ["k", "j"]])

    def test_a_short_election_calendar_is_refused(self):
        from kyc import results
        self.fec.fetch_pages = lambda path, params, sort: ([{"election_state": "RI"}], 2)
        with self.assertRaises(results.ResultsError):
            results.fetch_dates()
        row = {"election_state": "RI", "office_sought": "S", "election_type_id": "P",
               "election_date": "2026-09-09T00:00:00"}
        self.fec.fetch_pages = lambda path, params, sort: ([row], 1)
        self.assertEqual(results.fetch_dates()[("RI", "S")]["primary"], "2026-09-09")


class TestRegistrations(unittest.TestCase):
    """One person, several FEC ids - and two people, one name (rule 25)."""

    @staticmethod
    def filing(cid, district, receipts, f2, name="DOE, JANE", disb=100.0, end="2026-06-30"):
        return {"candidate_id": cid, "name": name, "office": "H", "state": "NV",
                "district_number": district, "receipts": receipts, "disbursements": disb,
                "coverage_end_date": end, "last_f2_date": f2, "incumbent_challenge": "C"}

    def test_one_committee_under_two_ids_is_one_person_in_the_latest_seat(self):
        # Ronda Kennedy: NV-3 statement in 2025, NV-4 statement in 2026.
        rows = [self.filing("H6NV03238", 3, 350000.0, "2025-06-09"),
                self.filing("H6NV04137", 4, 350000.0, "2026-03-18")]
        self.assertEqual(candidates.registrations(rows), {"H6NV04137": ["H6NV03238"]})

    def test_a_shared_name_with_different_money_is_two_people(self):
        # Two Michael Thompsons in Florida: FL-1 in 2025, FL-22 in 2026.
        rows = [self.filing("H6FL01275", 1, 86975.7, "2024-11-15", end="2025-06-30"),
                self.filing("H6FL22180", 22, 23613.0, "2026-05-08", end="2026-07-29")]
        self.assertEqual(candidates.registrations(rows), {})

    def test_the_choice_is_stable_when_statements_tie(self):
        rows = [self.filing("H6TX10262", 10, 9000.0, "2026-01-02"),
                self.filing("H6TX10254", 10, 9000.0, "2026-01-02")]
        self.assertEqual(candidates.registrations(rows), {"H6TX10254": ["H6TX10262"]})

    def test_a_curated_pair_folds_registrations_whose_totals_differ(self):
        from kyc import overrides
        other, (target, _why) = next(iter(overrides.SAME_PERSON_FILINGS.items()))
        rows = [self.filing(target, 3, 4026577.61, "2026-08-10", name="O'DONNELL, MARTY"),
                self.filing(other, 3, 4055410.28, "2026-05-06", name="O'DONNELL, MARTY")]
        self.assertEqual(candidates.registrations(rows), {target: [other]})

    def test_profiles_keep_strangers_apart_and_remember_folded_ids(self):
        cache = {"candidates": [
            self.filing("H6NV03238", 3, 350000.0, "2025-06-09", name="KENNEDY, RONDA"),
            self.filing("H6NV04137", 4, 350000.0, "2026-03-18", name="KENNEDY, RONDA"),
            self.filing("H6NV01001", 1, 8000.0, "2026-02-01", name="SMITH, JOHN"),
            self.filing("H6NV02002", 2, 9000.0, "2026-02-01", name="SMITH, JOHN"),
        ]}
        out, skipped = candidates.to_profiles(cache, [])
        by_id = {p["id"]: p for p in out}
        self.assertEqual(sorted(by_id), ["FEC_H6NV01001", "FEC_H6NV02002", "FEC_H6NV04137"])
        self.assertEqual(by_id["FEC_H6NV04137"]["otherFecIds"], ["H6NV03238"])
        self.assertNotIn("otherFecIds", by_id["FEC_H6NV01001"])
        self.assertEqual(skipped, 1)

    def test_validate_names_people_registered_for_two_seats(self):
        field = {"candidates": [
            self.filing("H2FL21108", 25, 1.0, "2026-05-08"),
            self.filing("H6FL22149", 22, 1.0, "2026-01-02"),
        ]}
        for row in field["candidates"]:
            row["state"] = "FL"
        profiles = [{"name": "Daniel John Franzese", "fecCandidateId": "H2FL21108",
                     "otherFecIds": ["H6FL22149"]}]
        codes = [i.code for i in validate.check_registrations(profiles, field)]
        self.assertIn("registrations-disagree", codes)
