"""Regression tests for the KYC data pipeline.

Standard library only:

    python -m unittest discover tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import overrides, validate, voteview  # noqa: E402
from kyc.normalize import (  # noqa: E402
    fmt_curr,
    office_label,
    parse_age,
    parse_district,
    parse_state_abbrev,
)
from kyc.photos import PLACEHOLDER, candidate_photos, member_photos  # noqa: E402
from kyc.profiles import build_profiles  # noqa: E402
from kyc.sources import load_all  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestStateParsing(unittest.TestCase):
    def test_west_virginia_is_not_virginia(self):
        """Substring order used to make "West Virginia" resolve to VA."""
        self.assertEqual(parse_state_abbrev("West Virginia"), "WV")
        self.assertEqual(parse_state_abbrev("WEST VIRGINIA"), "WV")
        self.assertEqual(parse_state_abbrev("Virginia"), "VA")

    def test_abbreviations_and_districts(self):
        self.assertEqual(parse_state_abbrev("TX"), "TX")
        self.assertEqual(parse_state_abbrev("TX-32"), "TX")
        self.assertEqual(parse_state_abbrev("KY-04"), "KY")

    def test_lowercase_words_are_not_states(self):
        """"in", "or", "me" must not be read as Indiana/Oregon/Maine."""
        self.assertEqual(parse_state_abbrev("running for me"), "N/A")
        self.assertEqual(parse_state_abbrev("undecided or pending"), "N/A")

    def test_missing_values(self):
        for val in (None, "", "  ", "nan", "Unknown", "N/A"):
            self.assertEqual(parse_state_abbrev(val), "N/A", val)

    def test_territories(self):
        self.assertEqual(parse_state_abbrev("Puerto Rico"), "PR")
        self.assertEqual(parse_state_abbrev("Northern Mariana Islands"), "MP")


class TestDistrictParsing(unittest.TestCase):
    def test_strips_the_word_district(self):
        self.assertEqual(parse_district("District 3", "AL"), (3, "3"))

    def test_strips_redundant_state_prefix(self):
        self.assertEqual(parse_district("TX-32", "TX"), (32, "32"))
        self.assertEqual(parse_district("KY-04", "KY"), (4, "4"))

    def test_at_large_forms(self):
        for val in ("At-Large", "at large", "AT-LARGE", "0"):
            self.assertEqual(parse_district(val, "AK"), (0, "AL"), val)

    def test_absent(self):
        for val in (None, "", "N/A", "nan", "Unknown"):
            self.assertEqual(parse_district(val, "TX"), (None, None), val)

    def test_office_labels(self):
        self.assertEqual(office_label("House", "TX", "32"), "House • TX-32")
        self.assertEqual(office_label("Senate (Candidate)", "MI", None), "Senate • MI")
        self.assertEqual(office_label("House", "AK", "AL"), "House • AK-AL")


class TestCurrency(unittest.TestCase):
    def test_zero_is_not_missing(self):
        """A filed zero and no filing at all are different claims."""
        self.assertEqual(fmt_curr(0), "$0.00")
        self.assertEqual(fmt_curr("0"), "$0.00")

    def test_missing(self):
        for val in (None, "", "nan", "N/A", "$nan"):
            self.assertEqual(fmt_curr(val), "N/A", val)

    def test_formatting(self):
        self.assertEqual(fmt_curr(1234.5), "$1,234.50")
        self.assertEqual(fmt_curr("2500000"), "$2,500,000.00")
        self.assertEqual(fmt_curr("$5,000"), "$5,000")


class TestAge(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_age("47"), 47)
        self.assertEqual(parse_age(47.0), 47)

    def test_invalid(self):
        for val in (None, "", "nan", "Unknown", "-3", "0", "150", "abc"):
            self.assertEqual(parse_age(val), "Unknown", val)


class TestPhotos(unittest.TestCase):
    def test_member_chain_prefers_bioguide(self):
        urls = member_photos("Jane Doe", "D000123")
        self.assertIn("congress.gov", urls[0])
        self.assertEqual(urls[-1], PLACEHOLDER)

    def test_member_without_bioguide_falls_back_to_wikipedia(self):
        urls = member_photos("Jane Doe", "")
        self.assertIn("wikipedia.org", urls[0])

    def test_middle_names_try_full_slug_first(self):
        urls = member_photos("Ben Ray Lujan", "")
        self.assertIn("Ben_Ray_Lujan", urls[0])
        self.assertTrue(any("Ben_Lujan" in u for u in urls))

    def test_override_is_scoped_by_state(self):
        """Two different people sharing a name must not share a portrait."""
        mi = candidate_photos("Mike Rogers", "MI")
        al = candidate_photos("Mike Rogers", "AL")
        self.assertIn("upload.wikimedia.org", mi[0])
        self.assertNotEqual(mi[0], al[0])


class TestBuild(unittest.TestCase):
    """End-to-end over the real rosters in the repository."""

    @classmethod
    def setUpClass(cls):
        cls.raw = load_all(ROOT)
        cls.profiles, cls.stats = build_profiles(cls.raw)
        cls.by_id = {p["id"]: p for p in cls.profiles}

    def test_builds_profiles(self):
        self.assertGreater(self.stats["total"], 500)
        self.assertEqual(
            self.stats["total"], self.stats["members"] + self.stats["candidates"]
        )

    def test_every_profile_has_required_keys(self):
        required = {
            "id", "name", "chamber", "party", "state", "district", "officeLabel",
            "status", "photos", "photo_url", "isCandidate", "seatUp2026",
            "isUpIn2026", "seekingReelection2026",
        }
        for profile in self.profiles:
            missing = required - set(profile)
            self.assertFalse(missing, f"{profile.get('name')} missing {missing}")

    def test_ids_are_unique(self):
        ids = [p["id"] for p in self.profiles]
        self.assertEqual(len(ids), len(set(ids)))

    def test_photo_url_matches_head_of_chain(self):
        for profile in self.profiles:
            self.assertEqual(profile["photo_url"], profile["photos"][0])

    def test_all_35_senate_seats_up_in_2026_are_matched(self):
        self.assertEqual(self.stats["senate_seats_up"], 35)
        matched = {
            p["state"] for p in self.profiles
            if p["seatUp2026"] and not p["isCandidate"] and "Senate" in p["chamber"]
        }
        self.assertEqual(matched, set(overrides.SENATE_SEATS_UP_2026))

    def test_every_house_seat_is_up_in_2026(self):
        """Two-year terms: the whole House is on the ballot, not just retirees."""
        house = [
            p for p in self.profiles
            if not p["isCandidate"] and "House" in p["chamber"]
        ]
        self.assertTrue(house)
        self.assertTrue(all(p["seatUp2026"] for p in house))

    def test_retiring_members_are_not_seeking_reelection(self):
        retiring = [
            p for p in self.profiles
            if not p["isCandidate"] and overrides.is_not_seeking(p["status"])
        ]
        self.assertTrue(retiring)
        for profile in retiring:
            self.assertFalse(profile["seekingReelection2026"], profile["name"])

    def test_durbin_retirement_override_applies(self):
        """The roster lists his legal name; the override keyed the nickname."""
        durbin = [p for p in self.profiles if p["name"] == "Richard Durbin"]
        self.assertEqual(len(durbin), 1)
        self.assertFalse(durbin[0]["seekingReelection2026"])
        self.assertIn("not running", durbin[0]["status"].lower())

    def test_labels_have_no_district_word_or_doubled_state(self):
        for profile in self.profiles:
            label = profile["officeLabel"]
            self.assertNotIn("District ", label, profile["name"])
            self.assertNotRegex(label, r"([A-Z]{2})-\1-", profile["name"])

    def test_same_name_different_people_stay_separate(self):
        rogers = [p for p in self.profiles if p["name"] == "Mike Rogers"]
        self.assertEqual(len(rogers), 2)
        states = {p["state"] for p in rogers}
        self.assertEqual(states, {"AL", "MI"})
        self.assertNotEqual(rogers[0]["photos"][0], rogers[1]["photos"][0])

    def test_distinct_people_are_not_cross_linked(self):
        """Rogers AL and Rogers MI share a name but nothing else."""
        for profile in self.profiles:
            if profile["name"] == "Mike Rogers":
                self.assertIsNone(profile.get("alsoRunningId"), profile["state"])
                self.assertIsNone(profile.get("incumbentId"), profile["state"])

    def test_dual_role_members_are_cross_linked_both_ways(self):
        self.assertGreater(self.stats["cross_linked"], 0)
        for profile in self.profiles:
            partner_id = profile.get("alsoRunningId")
            if not partner_id:
                continue
            partner = self.by_id[partner_id]
            self.assertEqual(partner.get("incumbentId"), profile["id"])
            self.assertEqual(partner["state"], profile["state"])
            self.assertNotEqual(partner["chamber"], profile["chamber"])

    def test_placeholder_nominees_kept_per_state(self):
        """Bare-name dedup used to collapse these into a single card."""
        nominees = [
            p for p in self.profiles if p["name"] == "Republican Nominee"
        ]
        self.assertGreater(len(nominees), 1)
        self.assertEqual(len({p["state"] for p in nominees}), len(nominees))

    def test_validation_reports_no_errors(self):
        issues = validate.run(self.profiles, self.raw)
        errors = [i for i in issues if i.level == "error"]
        self.assertEqual(errors, [], validate.format_report(errors, verbose=True))


class TestVoteview(unittest.TestCase):
    """Offline tests for the DW-NOMINATE transform."""

    def test_latest_congress_wins(self):
        rows = [
            {"bioguide_id": "A1", "congress": "117", "nominate_dim1": "0.20"},
            {"bioguide_id": "A1", "congress": "119", "nominate_dim1": "0.55"},
            {"bioguide_id": "A1", "congress": "118", "nominate_dim1": "0.40"},
        ]
        self.assertEqual(voteview.latest_scores(rows)["A1"], (119, 0.55))

    def test_unparseable_rows_are_skipped(self):
        rows = [
            {"bioguide_id": "", "congress": "119", "nominate_dim1": "0.5"},
            {"bioguide_id": "B2", "congress": "119", "nominate_dim1": ""},
            {"bioguide_id": "C3", "congress": "x", "nominate_dim1": "0.5"},
            {"bioguide_id": "D4", "congress": "119", "nominate_dim1": "-0.7"},
        ]
        self.assertEqual(set(voteview.latest_scores(rows)), {"D4"})

    def test_labels_span_the_spectrum(self):
        self.assertIn("Solidly Progressive", voteview.describe(-0.75))
        self.assertIn("Moderate Democrat", voteview.describe(-0.25))
        self.assertIn("Centrist", voteview.describe(0.0))
        self.assertIn("Moderate Republican", voteview.describe(0.25))
        self.assertIn("Solidly Conservative", voteview.describe(0.75))

    def test_centrists_are_labelled_independent_not_percentage(self):
        self.assertIn("Highly Independent", voteview.describe(0.05))
        self.assertNotIn("%", voteview.describe(0.05))

    def test_loyalty_is_capped(self):
        self.assertIn("~99%", voteview.describe(1.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
