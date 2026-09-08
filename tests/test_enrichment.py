"""Tests for the enrichment layers: provenance, portraits, FEC and races.

Standard library only, no network:

    python -m unittest discover tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import fec, normalize, portraits, races  # noqa: E402
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
        self.assertEqual(len(delegates), 6, "territory delegates")
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
