"""Tests for the enrichment layers: provenance, portraits, FEC and races.

Standard library only, no network:

    python -m unittest discover tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import fec, normalize, portraits, races, validate  # noqa: E402
from kyc.normalize import TERRITORIES, classify  # noqa: E402
from kyc.profiles import apply_quality, build_profiles  # noqa: E402
from kyc.sources import load_all  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestProvenance(unittest.TestCase):
    """Placeholder prose must never be presented as researched data."""

    def test_real_values_pass_through(self):
        self.assertEqual(classify("$3,161,009"), ("$3,161,009", normalize.OK))
        self.assertEqual(classify("Harvard Law School")[1], normalize.OK)

    def test_na_prose_is_not_disclosed(self):
        """The exact string that was being rendered verbatim to users."""
        value, status = classify("N/A (No net worth disclosure provided in sources)")
        self.assertEqual(status, normalize.NOT_DISCLOSED)
        self.assertEqual(value, "Not disclosed")

    def test_pending_is_not_disclosed(self):
        self.assertEqual(
            classify("Pending primary certification")[1], normalize.NOT_DISCLOSED
        )

    def test_empty_is_unknown(self):
        for val in (None, "", "nan", "N/A"):
            self.assertEqual(classify(val)[1], normalize.UNKNOWN, val)

    def test_generic_filler_is_flagged(self):
        for val in ("Individual/PAC contributions", "General legislative priorities",
                    "Public service", "Nominee Candidate"):
            self.assertEqual(classify(val)[1], normalize.GENERIC, val)

    def test_quality_map_only_records_problems(self):
        profile = {
            "net_worth": "$1,000", "funding_sources": "Individual/PAC contributions",
            "platforms": "", "committees": "Armed Services", "education": "Yale",
            "previous_professions": "Attorney",
            "voting_alignment": "DW-NOMINATE: +0.30",
            "receipts": "$5.00", "disbursements": "$1.00", "birthdate": "1970-01-01",
        }
        apply_quality(profile)
        self.assertNotIn("net_worth", profile["quality"])
        self.assertEqual(profile["quality"]["funding_sources"], normalize.GENERIC)
        self.assertEqual(profile["quality"]["platforms"], normalize.UNKNOWN)

    def test_non_date_birthdate_becomes_unknown(self):
        """Placeholder rows park a race marker in the Birthdate column."""
        profile = {"birthdate": "2026 Primary"}
        apply_quality(profile)
        self.assertEqual(profile["quality"]["birthdate"], normalize.UNKNOWN)
        self.assertEqual(profile["birthdate"], "No data")

    def test_missing_finance_is_unknown_not_undisclosed(self):
        """No filing on hand differs from a filing that disclosed nothing."""
        profile = {"receipts": "N/A", "disbursements": "N/A"}
        apply_quality(profile)
        self.assertEqual(profile["quality"]["receipts"], normalize.UNKNOWN)
        self.assertFalse(profile["hasRealFinance"])


class TestPortraits(unittest.TestCase):
    """Offline tests; the network paths run under the portraits command."""

    def test_check_image_is_tristate(self):
        """None means 'could not tell' - treating it as failure cost ~160 photos."""
        self.assertIs(portraits.check_image(None), False)
        self.assertIs(portraits.check_image(""), False)

    def test_profile_key_separates_same_name_people(self):
        al = {"id": "R000575", "isCandidate": False, "name": "Mike Rogers", "state": "AL"}
        mi = {"id": "CAND_21", "isCandidate": True, "name": "Mike Rogers", "state": "MI"}
        self.assertNotEqual(portraits.profile_key(al), portraits.profile_key(mi))

    def test_topic_pages_are_rejected(self):
        self.assertTrue(portraits._BAD_TITLE.search("2026 United States Senate elections"))
        self.assertTrue(portraits._BAD_TITLE.search("List of United States senators"))
        self.assertTrue(portraits._BAD_TITLE.search("Mercury (disambiguation)"))
        self.assertIsNone(portraits._BAD_TITLE.search("Dan Osborn"))

    def test_thumbnail_query_string_is_stripped(self):
        self.assertEqual(
            portraits._clean_thumb("https://x/y.jpg?utm_source=en.wikipedia.org"),
            "https://x/y.jpg",
        )

    def test_cross_link_inheritance(self):
        profiles = [
            {"id": "M1", "isCandidate": False, "name": "Ashley Hinson",
             "state": "IA", "alsoRunningId": "C1"},
            {"id": "C1", "isCandidate": True, "name": "Ashley Hinson",
             "state": "IA", "incumbentId": "M1"},
        ]
        cache = {
            portraits.profile_key(profiles[0]): {
                "url": "https://x/y.jpg", "via": "congress.gov",
            }
        }
        self.assertEqual(portraits.inherit_cross_links(profiles, cache), 1)
        self.assertEqual(
            cache[portraits.profile_key(profiles[1])]["url"], "https://x/y.jpg"
        )

    def test_apply_cache_puts_resolved_url_first(self):
        profile = {
            "id": "X1", "isCandidate": True, "name": "A B", "state": "TX",
            "photos": ["https://old/1.jpg", "placeholder"],
        }
        cache = {
            portraits.profile_key(profile): {"url": "https://new/2.jpg", "via": "wikipedia"}
        }
        portraits.apply_cache([profile], cache)
        self.assertEqual(profile["photos"][0], "https://new/2.jpg")
        self.assertEqual(profile["photo_url"], "https://new/2.jpg")
        self.assertEqual(profile["photoSource"], "wikipedia")


class TestFec(unittest.TestCase):
    def test_surname_extraction(self):
        self.assertEqual(fec._surname("Ashley Hinson"), "hinson")
        self.assertEqual(fec._surname("Ben Ray Lujan"), "lujan")

    def test_profile_key_splits_chamber(self):
        house = {"name": "A B", "state": "TX", "chamber": "House"}
        senate = {"name": "A B", "state": "TX", "chamber": "Senate (Candidate)"}
        self.assertNotEqual(fec.profile_key(house), fec.profile_key(senate))

    def test_money_formatting(self):
        self.assertEqual(fec._money(1022664.06), "$1,022,664.06")
        self.assertIsNone(fec._money(None))

    def test_apply_cache_replaces_estimates_and_clears_flags(self):
        profile = {
            "name": "A B", "state": "TX", "chamber": "House",
            "quality": {"receipts": "unknown", "funding_sources": "generic"},
        }
        cache = {
            fec.profile_key(profile): {
                "receipts": 100.0, "disbursements": 40.0, "cash_on_hand": 60.0,
                "individual_contributions": 75.0, "pac_contributions": 25.0,
                "coverage_end": "2026-06-30", "candidate_id": "H0TX00001",
            }
        }
        fec.apply_cache([profile], cache)
        self.assertEqual(profile["receipts"], "$100.00")
        self.assertEqual(profile["financeSource"], "FEC")
        self.assertEqual(profile["financeAsOf"], "2026-06-30")
        self.assertNotIn("receipts", profile["quality"])
        self.assertIn("Individual 75%", profile["funding_sources"])

    def test_profiles_without_fec_data_are_untouched(self):
        profile = {"name": "A B", "state": "TX", "chamber": "House",
                   "receipts": "No data", "quality": {"receipts": "unknown"}}
        fec.apply_cache([profile], {fec.profile_key(profile): {"found": False}})
        self.assertEqual(profile["receipts"], "No data")
        self.assertEqual(profile["quality"]["receipts"], "unknown")


def _period(year, start, end, receipts):
    """One /candidate/{id}/totals/?election_full=true row, as the API sends it."""
    return {"candidate_election_year": str(year), "cycle": None, "election_full": True,
            "coverage_start_date": start + "T00:00:00", "coverage_end_date": end + "T00:00:00",
            "receipts": receipts, "disbursements": 1.0,
            "last_cash_on_hand_end_period": 2.0}


class TestFinancePeriod(unittest.TestCase):
    """Members and challengers are measured over the same period.

    The member lookup asked for cycle=2026 and got the endpoint's default,
    election_full=false: Chris Coons's 2025-26 cycle, $4,168,081. The field
    query for every challenger beside him returns the 2026 *election period*,
    which for a senator starts in 2021: $6,897,138 for Coons himself. Measured
    live, 21 of 21 Senate incumbents in both caches differed this way.
    """

    def _totals(self, rows):
        calls = []

        def fake_get(path, params):
            calls.append((path, params))
            return {"results": rows}

        original = fec._get
        fec._get = fake_get
        try:
            return fec.totals("S0DE00092"), calls
        finally:
            fec._get = original

    def test_member_lookup_asks_for_the_election_period(self):
        _, calls = self._totals([])
        self.assertEqual(len(calls), 1)
        path, params = calls[0]
        self.assertEqual(path, "/candidate/S0DE00092/totals/")
        self.assertEqual(params.get("election_full"), "true")
        # cycle=2026 with election_full returns nothing for a senator next up
        # in 2028, so the period is chosen from the rows, not filtered for.
        self.assertNotIn("cycle", params)
        self.assertGreaterEqual(params.get("per_page", 0), 20)

    def test_the_2026_period_is_taken_with_its_start_date(self):
        figures, _ = self._totals([
            _period(2020, "2015-01-01", "2020-12-31", 7217773.49),
            _period(2026, "2021-01-01", "2026-08-26", 6897138.12),
        ])
        self.assertEqual(figures["receipts"], 6897138.12)
        self.assertEqual(figures["election_year"], 2026)
        self.assertEqual(figures["coverage_start"], "2021-01-01")
        self.assertEqual(figures["coverage_end"], "2026-08-26")

    def test_a_senator_not_up_in_2026_gets_their_current_period_never_a_past_one(self):
        figures, _ = self._totals([
            _period(2022, "2020-01-01", "2022-12-31", 12026093.21),
            _period(2028, "2023-01-01", "2026-06-30", 2256851.26),
        ])
        self.assertEqual(figures["election_year"], 2028)
        self.assertEqual(figures["receipts"], 2256851.26)

    def test_only_past_periods_is_no_filing(self):
        figures, _ = self._totals([_period(2024, "2023-01-01", "2024-12-31", 5.0)])
        self.assertIsNone(figures)

    def test_the_field_lookup_is_the_same_election_period(self):
        """/candidates/totals/?election_year= is election-period by definition."""
        from kyc import candidates
        captured = []
        original = fec.fetch_pages

        def fake_pages(path, params, sort, **kw):
            captured.append((path, params))
            return [{"candidate_id": "S4NE00207", "cycle": 2026}], 1

        fec.fetch_pages = fake_pages
        try:
            rows = candidates.fetch(log=lambda *a: None)
        finally:
            fec.fetch_pages = original
        self.assertEqual({p for p, _ in captured}, {"/candidates/totals/"})
        for _, params in captured:
            self.assertEqual(params["election_year"], fec.CYCLE)
            self.assertNotIn("cycle", params)
        # The start of the period is kept so the page can show it.
        self.assertIn("coverage_start_date", rows[0])

    def test_apply_cache_records_the_period(self):
        profile = {"name": "Chris Coons", "state": "DE", "chamber": "Senate", "quality": {}}
        cache = {fec.profile_key(profile): {
            "receipts": 6897138.12, "candidate_id": "S0DE00092", "found": True,
            "coverage_start": "2021-01-01", "coverage_end": "2026-08-26",
            "election_year": 2026}}
        fec.apply_cache([profile], cache)
        self.assertEqual(profile["financeSince"], "2021-01-01")
        self.assertEqual(profile["financeAsOf"], "2026-08-26")
        self.assertEqual(profile["financePeriod"], "election")
        self.assertEqual(profile["financeElection"], 2026)

    def test_a_record_cached_before_the_change_is_called_a_cycle_total(self):
        """Old member records measured the 2025-26 cycle; never relabel them."""
        profile = {"name": "Chris Coons", "state": "DE", "chamber": "Senate", "quality": {}}
        cache = {fec.profile_key(profile): {
            "receipts": 4168081.31, "candidate_id": "S0DE00092", "found": True,
            "coverage_end": "2026-08-26"}}
        fec.apply_cache([profile], cache)
        self.assertEqual(profile["financePeriod"], "cycle")
        self.assertNotIn("financeElection", profile)
        self.assertIsNone(profile["financeSince"])  # not invented
        self.assertEqual(profile["financeAsOf"], "2026-08-26")

    def test_period_fields_never_invent_a_start(self):
        self.assertIsNone(fec.period_fields(2026, "", "2026-06-30")["financeSince"])
        self.assertIsNone(fec.period_fields(2026, None, None)["financeAsOf"])
        self.assertEqual(
            fec.period_fields("2026", "2024-10-01T00:00:00", "2025-01-28")["financeSince"],
            "2024-10-01")


class TestNoFilingIsNotNoData(unittest.TestCase):
    """Four kinds of absence, and only one of them reports work we did.

    "No data" is a claim about us: it says nobody looked. Once the pipeline
    queries the FEC for every profile, using that label for a member the FEC
    was asked about and holds no filing for throws away the more informative
    fact - and several of them are sitting members running for a different
    seat, whose money is simply in another committee.
    """

    def profile(self, **kwargs):
        base = {"name": "A B", "state": "TX", "chamber": "House",
                "receipts": "No data", "disbursements": "No data",
                "quality": {"receipts": "unknown", "disbursements": "unknown"}}
        base.update(kwargs)
        return base

    def test_checked_but_no_filing_is_its_own_status(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {
            "found": False, "candidate_id": "H4TX01234", "via": "congress-legislators"}}
        fec.apply_cache([profile], cache)
        self.assertEqual(profile["quality"]["receipts"], normalize.NO_FILING)
        self.assertEqual(profile["receipts"], "No filing this cycle")
        self.assertEqual(profile["financeCycle"], fec.CYCLE)

    def test_never_looked_up_stays_unknown(self):
        # No candidate_id means we never identified them at the FEC at all.
        profile = self.profile()
        fec.apply_cache([profile], {fec.profile_key(profile): {"found": False}})
        self.assertEqual(profile["quality"]["receipts"], "unknown")
        self.assertEqual(profile["receipts"], "No data")

    def test_a_profile_with_totals_is_untouched_by_the_new_branch(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {
            "found": True, "candidate_id": "H4TX01234", "receipts": 100.0}}
        fec.apply_cache([profile], cache)
        self.assertEqual(profile["receipts"], "$100.00")
        self.assertNotIn("receipts", profile["quality"])

    def test_the_label_is_defined_once(self):
        self.assertEqual(normalize.STATUS_LABELS[normalize.NO_FILING],
                         "No filing this cycle")


class TestFecAttribution(unittest.TestCase):
    """Money shown against the wrong person would look entirely normal."""

    def profile(self, **kwargs):
        base = {"name": "A B", "state": "TX", "chamber": "House",
                "officeLabel": "House - TX-1", "quality": {}}
        base.update(kwargs)
        return base

    def test_an_id_from_another_state_is_an_error(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {"candidate_id": "H4CA01234",
                                            "receipts": 1.0, "filed_name": "SOMEONE ELSE"}}
        issues = validate.check_finance([profile], cache)
        self.assertEqual([i.code for i in issues], ["fec-attribution"])
        self.assertEqual(issues[0].level, "error")

    def test_a_senate_id_on_a_house_profile_is_an_error(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {"candidate_id": "S4TX00123", "receipts": 1.0}}
        codes = [i.code for i in validate.check_finance([profile], cache)]
        self.assertIn("fec-attribution", codes)

    def test_a_matching_id_passes(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {"candidate_id": "H4TX01234", "receipts": 1.0,
                                            "via": "congress-legislators"}}
        self.assertEqual(validate.check_finance([profile], cache), [])

    def test_an_unreadable_id_is_reported(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {"candidate_id": "???", "receipts": 1.0}}
        codes = [i.code for i in validate.check_finance([profile], cache)]
        self.assertIn("fec-unparsed-id", codes)

    def test_name_matched_profiles_are_surfaced(self):
        profile = self.profile()
        cache = {fec.profile_key(profile): {"candidate_id": "H4TX01234", "receipts": 1.0,
                                            "via": "fec-search"}}
        codes = [i.code for i in validate.check_finance([profile], cache)]
        self.assertIn("fec-name-matched", codes)

    def test_no_cache_means_no_findings(self):
        self.assertEqual(validate.check_finance([self.profile()], None), [])

    def test_the_real_data_attributes_every_figure_correctly(self):
        raw = load_all(ROOT)
        profiles, _ = build_profiles(raw)
        issues = validate.check_finance(profiles, fec.load_cache(ROOT))
        errors = [f"{i.code}: {i.detail}" for i in issues if i.level == "error"]
        self.assertEqual(errors, [])


class TestRaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = load_all(ROOT)
        cls.profiles, _ = build_profiles(raw)
        cls.races = races.build(cls.profiles)
        cls.by_id = {p["id"]: p for p in cls.profiles}

    def test_the_race_list_is_every_seat_we_know_an_occupant_for(self):
        # This used to assert a bare 472 against a comment that said
        # "435 + 6 + 35" - which is 476. The gap was never explained, and the
        # number moved the moment two vacant seats were filled. Assert the
        # structure and account for the shortfall instead of typing a total.
        senate = [r for r in self.races if r["chamber"] == "Senate"]
        house = [r for r in self.races if r["chamber"] == "House"]
        delegates = [r for r in house if r["isTerritory"]]
        voting = [r for r in house if not r["isTerritory"]]

        self.assertEqual(len(senate), 35, "Senate seats on the 2026 ballot")
        # Six delegates sit; five are on the ballot. Puerto Rico's Resident
        # Commissioner serves four years (48 U.S.C. 891) and is next elected
        # in 2028.
        self.assertEqual(len(delegates), len(TERRITORIES) - 1, "territory delegates")
        self.assertNotIn("PR", {r["state"] for r in delegates})
        self.assertEqual(len(self.races), len(senate) + len(house))

        # Every one of the 435 House seats is on the ballot, but a seat nobody
        # currently holds has no roster row and so produces no race. The
        # shortfall is exactly the vacancies, and never anything else.
        seated = {
            (p["state"], p["districtNum"]) for p in self.profiles
            if not p["isCandidate"] and p["chamber"] == "House"
            and p["state"] not in TERRITORIES
        }
        self.assertEqual(len(voting), len(seated))
        self.assertLessEqual(len(voting), 435)

    def test_senators_not_up_belong_to_no_race(self):
        idle = [
            p for p in self.profiles
            if not p["isCandidate"] and "Senate" in p["chamber"] and not p["seatUp2026"]
        ]
        self.assertEqual(len(idle), 65)
        self.assertTrue(all(p["raceId"] is None for p in idle))

    def test_race_ids_are_stable_and_unique(self):
        ids = [r["id"] for r in self.races]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(races.race_id("Senate", "IA", None), "S-IA-2026")
        self.assertEqual(races.race_id("House", "TX", 32), "H-TX-32-2026")

    def test_open_seats_are_seats_the_incumbent_is_leaving(self):
        open_races = [r for r in self.races if r["openSeat"]]
        self.assertTrue(open_races)
        for race in open_races:
            for pid in race["incumbentIds"]:
                self.assertFalse(
                    self.by_id[pid]["seekingReelection2026"], self.by_id[pid]["name"]
                )

    def test_contested_flag_matches_challenger_count(self):
        for race in self.races:
            self.assertEqual(race["contested"], race["candidateCount"] > 0)

    def test_most_contested_races_sort_first(self):
        counts = [r["candidateCount"] for r in self.races]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_dual_role_member_appears_in_two_races(self):
        """A House member running for Senate contests two different seats."""
        hinson = [
            p for p in self.profiles if p["name"] == "Ashley Hinson"
        ]
        self.assertEqual(len(hinson), 2)
        race_ids = {p["raceId"] for p in hinson}
        self.assertEqual(len(race_ids), 2)
        self.assertIn("S-IA-2026", race_ids)

    def test_every_profile_in_a_race_is_a_real_profile(self):
        known = set(self.by_id)
        for race in self.races:
            for pid in race["incumbentIds"] + race["candidateIds"]:
                self.assertIn(pid, known)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestFecRateLimit(unittest.TestCase):
    """The key allows 60 requests a minute (X-RateLimit-Limit: 60).

    A GitHub runner's low latency let `finance --refresh` send 61 requests in
    well under a minute; the FEC answered 429, a 1.5 s backoff never outlasted
    the window, and the weekly refresh failed at the field fetch after it.
    """

    def setUp(self):
        self.saved = dict(fec._RATE)

    def tearDown(self):
        fec._RATE.clear()
        fec._RATE.update(self.saved)

    def test_requests_are_spaced_whatever_the_latency(self):
        clock, slept = [100.0], []

        def sleep(seconds):
            slept.append(round(seconds, 3))
            clock[0] += seconds

        fec._RATE.update(interval=1.05, last=0.0)
        fec._pace(lambda: clock[0], sleep)
        fec._pace(lambda: clock[0], sleep)
        self.assertEqual(slept, [1.05])

    def test_the_advertised_limit_widens_the_spacing_and_never_narrows_it(self):
        fec._RATE.update(interval=1.05)
        fec._learn_limit({"X-RateLimit-Limit": "30"})
        self.assertAlmostEqual(fec._RATE["interval"], 2.1)
        for header in ({"X-RateLimit-Limit": "1000"}, {"X-RateLimit-Limit": "junk"}, {}, None):
            fec._learn_limit(header)
            self.assertAlmostEqual(fec._RATE["interval"], 2.1)

    def test_a_429_waits_out_what_it_asks_then_succeeds(self):
        import io
        import urllib.error
        from unittest import mock

        calls, slept = [], []

        class Response:
            headers = {"X-RateLimit-Limit": "60"}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"results": []}'

        def urlopen(req, timeout=None):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests",
                                             {"Retry-After": "7"}, io.BytesIO(b""))
            return Response()

        fec._RATE.update(interval=0.0, last=0.0)
        with mock.patch.object(fec.urllib.request, "urlopen", urlopen), \
                mock.patch.object(fec.time, "sleep", slept.append), \
                mock.patch.object(fec, "api_key", lambda root=".": "TESTKEY"), \
                mock.patch.object(fec, "using_demo_key", lambda root=".": False):
            self.assertEqual(fec._get("/x/", {}), {"results": []})
        self.assertEqual(len(calls), 2)
        self.assertIn(7.0, slept)

    def test_a_429_that_names_no_wait_waits_the_whole_window(self):
        silent = type("Silent429", (), {"headers": {}})()
        self.assertEqual(fec._retry_after(silent), fec.RATE_WINDOW)


class TestPinnedFinanceRefresh(unittest.TestCase):
    """A pin fixes who a profile is, not what they have raised.

    Darline Graham Nordone filed as "GRAHAM, DARLINE", so her FEC id is
    pinned by hand. resolve_all skipped pinned records outright, which froze
    her July figures through every refresh and left them labelled a two-year
    total.
    """

    PERSON = {"id": "G000608", "name": "Darline Graham Nordone", "state": "SC",
              "chamber": "Senate"}
    PIN = {"candidate_id": "S6SC04437", "pinned": True, "via": "pinned", "found": True,
           "note": "Filed as GRAHAM, DARLINE", "receipts": 1.0, "name": "Darline Graham Nordone"}

    def run_with(self, figures):
        from unittest import mock
        cache = {fec.profile_key(self.PERSON): dict(self.PIN)}
        asked = []

        def totals(candidate_id, election_year=fec.CYCLE):
            asked.append(candidate_id)
            return figures

        def no_search(*args, **kwargs):
            raise AssertionError("a pinned profile must not be searched for by name")

        with mock.patch.object(fec, "load_cache", lambda root=".": cache), \
                mock.patch.object(fec, "save_cache", lambda c, root=".": None), \
                mock.patch.object(fec, "totals", totals), \
                mock.patch.object(fec, "find_candidate", no_search), \
                mock.patch.object(fec, "using_demo_key", lambda root=".": False), \
                mock.patch.object(fec, "known_ids", lambda *a, **k: {}), \
                mock.patch.object(fec.time, "sleep", lambda s: None):
            out, stats = fec.resolve_all([self.PERSON], refresh=True, log=lambda *a: None)
        return out[fec.profile_key(self.PERSON)], asked, stats

    def test_a_pinned_record_is_refreshed_through_its_pinned_id(self):
        figures = {"election_year": 2026, "coverage_start": "2026-07-23",
                   "coverage_end": "2026-09-30", "receipts": 500000.0}
        record, asked, stats = self.run_with(figures)
        self.assertEqual(asked, ["S6SC04437"])
        self.assertEqual(record["receipts"], 500000.0)
        self.assertEqual(record["election_year"], 2026)
        self.assertTrue(record["pinned"])
        self.assertEqual(record["note"], "Filed as GRAHAM, DARLINE")
        self.assertEqual(stats["found"], 1)

    def test_an_empty_answer_for_a_pinned_id_discards_nothing(self):
        record, asked, _ = self.run_with(None)
        self.assertEqual(asked, ["S6SC04437"])
        self.assertEqual(record, self.PIN)


class TestFinancePeriodWarning(unittest.TestCase):
    def test_a_two_year_total_left_after_a_refresh_is_reported(self):
        people = [{"name": "A", "officeLabel": "Senate • SC", "financePeriod": "cycle"},
                  {"name": "B", "officeLabel": "Senate • DE", "financePeriod": "election"},
                  {"name": "C", "officeLabel": "House • TX-1"}]
        issues = validate.check_finance_periods(people)
        self.assertEqual([i.code for i in issues], ["finance-cycle-period"])
        self.assertEqual(issues[0].detail, ["A (Senate • SC)"])
        self.assertEqual(validate.check_finance_periods(people[1:]), [])
