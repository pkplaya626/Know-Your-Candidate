"""Regression tests for the KYC data pipeline.

Standard library only:

    python -m unittest discover tests -v
"""

import os
import sys
import unittest
from unittest import mock

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

    def test_member_without_bioguide_has_the_silhouette(self):
        # Nothing is looked for by name (rule 24).
        self.assertEqual(member_photos("Jane Doe", ""), [PLACEHOLDER])

    def test_no_chain_guesses_a_file_from_a_name(self):
        """Special:FilePath/<Name>.jpg is whoever uploaded under the name:
        "Justin_Murphy.jpg" is a rugby league player (CAND_40, the NJ
        Republican Senate nominee), "David_Smith.jpg" an Olympic kayaker
        (CAND_43, OR), and "Al_Green.jpg" the singer, behind Rep. Al Green's
        official photographs (G000553)."""
        chains = [candidate_photos("Justin Murphy", "NJ"), candidate_photos("David Smith", "OR"),
                  member_photos("Al Green", "G000553"), member_photos("Ben Ray Lujan", "L000570")]
        for chain in chains:
            self.assertFalse([u for u in chain if "wikipedia.org/wiki/" in u], chain)
            self.assertEqual(chain[-1], PLACEHOLDER)
        self.assertEqual(candidate_photos("Justin Murphy", "NJ"), [PLACEHOLDER])

    def test_the_directorys_photograph_replaces_its_dead_host(self):
        # bioguideretro.congress.gov answered 404 for every member (2026-10-17).
        chain = member_photos("Al Green", "G000553")
        self.assertIn("https://bioguide.congress.gov/photo/G000553.jpg", chain)
        self.assertFalse([u for u in chain if "bioguideretro" in u], chain)

    def test_a_chosen_photo_is_keyed_on_the_profile_id(self):
        """Two different people who share a name must not share a portrait:
        a name-keyed override put the Michigan Senate candidate Mike Rogers's
        photograph on Rep. Mike Rogers (AL-3). An entry is keyed on the
        profile's id (rules 3 and 17), and only a candidate's."""
        from kyc import photos
        entry = {"url": "https://example.gov/rogers.jpg"}
        mi = {"id": "CAND_1", "name": "Mike Rogers", "state": "MI", "isCandidate": True}
        al = {"id": "FEC_H2AL03032", "name": "Mike Rogers", "state": "AL", "isCandidate": True}
        member = {"id": "R000575", "name": "Mike Rogers", "state": "AL", "isCandidate": False,
                  "bioguide": "R000575"}
        with mock.patch.dict("kyc.overrides.CANDIDATE_PHOTOS",
                             {"CAND_1": entry, "R000575": entry}, clear=True):
            self.assertIs(photos.curated(mi), entry)
            self.assertIsNone(photos.curated(al))
            self.assertIsNone(photos.curated(member))
        self.assertEqual(candidate_photos("Mike Rogers", "MI"), [PLACEHOLDER])

    def test_no_hand_chosen_photo_is_a_made_up_file_name(self):
        # 24 of the 25 "hand-chosen" URLs named Commons files that do not
        # exist, made up from the person's name (2026-10-17). An entry now
        # names a served file and the page naming the person beside it, with
        # the day it was read, why it is this person, and what was seen.
        from kyc import overrides, photos
        for key, entry in overrides.CANDIDATE_PHOTOS.items():
            self.assertEqual(photos.curated_problems(entry), [], key)
            self.assertFalse(photos.is_guessed(entry["url"]), key)

    def test_an_entry_without_its_evidence_is_named(self):
        from kyc import photos
        good = {"url": "https://example.gov/a.jpg", "page": "https://example.gov/a",
                "words": "Attorney General A", "tie": "the office", "seen": "alone",
                "read": "2026-10-25", "by": "Office of A"}
        self.assertEqual(photos.curated_problems(good), [])
        self.assertIn("no credit (by)", photos.curated_problems(dict(good, by="")))
        self.assertIn("no seen", photos.curated_problems(dict(good, seen="")))
        self.assertIn("a read date that is not a date",
                      photos.curated_problems(dict(good, read="October")))
        commons = dict(good, url="https://upload.wikimedia.org/wikipedia/commons/a/ab/A.jpg",
                       by="")
        self.assertEqual(photos.curated_problems(commons),
                         ["a Commons file whose page is not its description page"])
        self.assertEqual(photos.curated_problems(
            dict(commons, page="https://commons.wikimedia.org/wiki/File:A.jpg")), [])
        self.assertTrue(photos.curated_problems(
            dict(good, url="https://commons.wikimedia.org/wiki/Special:FilePath/A.jpg")))


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
            self.stats["total"],
            self.stats["members"] + self.stats["former"] + self.stats["candidates"]
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

    def test_every_senate_seat_in_the_record_is_matched(self):
        # The frozen record's Senate races (35 in 2026), each to its sitting
        # incumbent - no count typed here.
        senate = {r["state"] for r in self.raw["record"]["races"].values()
                  if r["chamber"] == "Senate"}
        self.assertEqual(self.stats["senate_seats_up"], len(senate))
        matched = {
            p["state"] for p in self.profiles
            if p["seatUp2026"] and not p["isCandidate"] and "Senate" in p["chamber"]
        }
        self.assertEqual(matched, senate)

    def test_every_house_seat_is_up_in_2026(self):
        """Two-year terms: the whole House is on the ballot, not just retirees."""
        house = [
            p for p in self.profiles
            if not p["isCandidate"] and "House" in p["chamber"]
        ]
        self.assertTrue(house)
        self.assertTrue(all(p["seatUp2026"] for p in house if p["state"] != "PR"))

    def test_puerto_ricos_resident_commissioner_is_not_up_in_2026(self):
        """A four-year term (48 U.S.C. 891): elected 2024, next on the ballot in 2028.

        The site showed H-PR-00-2026 with him "seeking re-election", though the
        FEC's 2026 calendar has no PR House primary.
        """
        from kyc import races

        pr = [p for p in self.profiles
              if not p["isCandidate"] and "House" in p["chamber"] and p["state"] == "PR"]
        self.assertEqual(len(pr), 1)
        self.assertFalse(pr[0]["seatUp2026"])
        self.assertFalse(pr[0]["seekingReelection2026"])
        self.assertEqual(pr[0]["termEndYear"], 2029)
        self.assertNotIn("H-PR-00-2026", races.contestable(self.profiles))
        self.assertTrue(races.house_seat_up("PR", 2028))
        self.assertTrue(races.house_seat_up("GU", 2026))
        race_ids = {r["id"] for r in races.build(self.profiles)}
        self.assertNotIn("H-PR-00-2026", race_ids)
        self.assertIn("H-GU-00-2026", race_ids)

    def test_ages_are_computed_from_the_birthdate(self):
        """The CSV's Age column was typed once; 70 were stale at build time."""
        import datetime
        from kyc.profiles import _age, age_as_of

        as_of = datetime.date(2026, 10, 1)
        self.assertEqual(_age({"Birthdate": "1965-10-01", "Age": "40"}, as_of), 61)
        self.assertEqual(_age({"Birthdate": "1965-10-02", "Age": "40"}, as_of), 60)
        # The CSV only when there is no usable birthdate.
        self.assertEqual(_age({"Birthdate": "2026 Primary", "Age": "58"}, as_of), 58)
        self.assertEqual(_age({"Birthdate": "", "Age": ""}, as_of), "Unknown")
        # Anchored on the data's fetch date, not the wall clock, so verify is
        # stable and SOURCE_DATE_EPOCH builds do not make everyone 25 years younger.
        self.assertEqual(age_as_of({"fetched": "2026-09-13T22:14:22+00:00"}),
                         datetime.date(2026, 9, 13))
        for p in self.profiles:
            if p["birthdate"][:4].isdigit() and isinstance(p["age"], int):
                born = datetime.date.fromisoformat(p["birthdate"][:10])
                self.assertIn(self.stats["ageAsOf"][:4], {str(born.year + p["age"]),
                                                          str(born.year + p["age"] + 1)})

    def test_retiring_members_are_not_seeking_reelection(self):
        # The roster's or the override's status line: a former member's is
        # replaced on the page by when they left, and still decided this.
        retiring = [
            p for p in self.profiles
            if not p["isCandidate"] and overrides.is_not_seeking(
                overrides.status_override(p["id"], p["status"]))
        ]
        self.assertTrue(retiring)
        for profile in retiring:
            self.assertFalse(profile["seekingReelection2026"], profile["name"])

    def test_durbin_retirement_override_applies(self):
        """The roster lists his legal name; the override keyed the nickname."""
        durbin = [p for p in self.profiles if p["name"] == "Richard Durbin"]
        self.assertEqual(len(durbin), 1)
        self.assertFalse(durbin[0]["seekingReelection2026"])
        status = durbin[0]["status"] if not durbin[0].get("formerMember") else \
            overrides.status_override(durbin[0]["id"], "")
        self.assertIn("not running", status.lower())

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

    def test_same_name_in_two_states_is_two_people(self):
        """Bare-name dedup used to collapse these into a single card.

        The roster once carried a "Republican Nominee" placeholder per state
        and lost all but one of them; the placeholders are gone now that the
        primaries have named real people, so the rule is pinned directly.
        """
        from kyc.profiles import _dedup_candidates
        rows = [
            {"Name": "Mike Rogers", "Chamber": "Senate (Candidate)", "Office / District": "MI"},
            {"Name": "Mike Rogers", "Chamber": "House (Candidate)", "Office / District": "AL-3"},
            {"Name": "Mike Rogers", "Chamber": "Senate (Candidate)", "Office / District": "MI"},
        ]
        kept = _dedup_candidates(rows)
        self.assertEqual(len(kept), 2)
        self.assertEqual({r["Office / District"] for r in kept}, {"MI", "AL-3"})

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

    def test_labels_span_the_spectrum_in_the_scales_own_words(self):
        self.assertIn("well left of centre", voteview.describe(-0.75))
        self.assertIn("(left of centre", voteview.describe(-0.25))
        self.assertIn("near the centre", voteview.describe(0.0))
        self.assertIn("(right of centre", voteview.describe(0.25))
        self.assertIn("well right of centre", voteview.describe(0.75))

    def test_no_label_names_a_party(self):
        # "Moderate Republican" was on Kevin Kiley, an independent, and
        # "Moderate Democrat" on Angus King.
        for score in (-1.0, -0.4, -0.25, -0.1, 0.0, 0.1, 0.25, 0.4, 1.0):
            text = voteview.describe(score, 119)
            for word in ("Democrat", "Republican", "Progressive", "Conservative", "Swing"):
                self.assertNotIn(word, text)

    def test_the_congress_goes_with_the_score(self):
        self.assertEqual(voteview.describe(0.41, 119),
                         "DW-NOMINATE: +0.41 (well right of centre; 119th Congress)")
        self.assertIn("101st Congress", voteview.describe(0.0, 101))
        self.assertIn("112th Congress", voteview.describe(0.0, 112))
        rows = [{"bioguide_id": "K1", "congress": "119", "nominate_dim1": "0.25"}]
        self.assertEqual(voteview.build_alignment_map(rows)["K1"],
                         "DW-NOMINATE: +0.25 (right of centre; 119th Congress)")

    def test_nothing_is_derived_from_the_score(self):
        # "~92% Party Loyalty" was 80 + 30 x |score|, shown as a statistic and
        # given even to independents. A party-unity rate is counted from roll
        # calls; the score says only where a member sits.
        for score in (-1.0, -0.25, 0.05, 0.41, 1.0):
            text = voteview.describe(score)
            self.assertNotIn("%", text)
            self.assertNotIn("Loyalty", text)
            self.assertNotIn("Independent", text)
        self.assertEqual(voteview.describe(0.41), "DW-NOMINATE: +0.41 (well right of centre)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
