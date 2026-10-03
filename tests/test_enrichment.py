"""Tests for the enrichment layers: provenance, portraits, FEC and races.

Standard library only, no network:

    python -m unittest discover tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock  # noqa: E402

from kyc import fec, normalize, photos, portraits, races, validate  # noqa: E402
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


class TestPortraitSizes(unittest.TestCase):
    """Sizes of one photograph for a srcset, and where a member's comes from.

    Measured 2026-10-03: congress.gov's member portraits are 175px wide and
    Wikimedia's first choices were 960px thumbnails or originals up to 2364px,
    shown in 38px circles. The Clerk, congress.gov and the unitedstates
    project held a different photograph of seven of ten members sampled.
    """

    ORIGINAL = ("https://upload.wikimedia.org/wikipedia/commons/7/7f/"
                "Rep._Yassamin_Ansari_official_photo%2C_119th_Congress.jpg")
    THUMB = ("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/"
             "Rep._Yassamin_Ansari_official_photo%2C_119th_Congress.jpg/960px-"
             "Rep._Yassamin_Ansari_official_photo%2C_119th_Congress.jpg")

    def test_a_thumbnail_and_its_original_are_one_photograph(self):
        file = ("upload", "wikipedia/commons", "7/7f",
                "Rep._Yassamin_Ansari_official_photo%2C_119th_Congress.jpg")
        self.assertEqual(portraits.wikimedia_file(self.ORIGINAL), file)
        self.assertEqual(portraits.wikimedia_file(self.THUMB), file)
        other_host = self.THUMB.replace("://upload.", "://thumb.")
        self.assertEqual(portraits.wikimedia_file(other_host)[0], "thumb")
        local = "https://upload.wikimedia.org/wikipedia/en/a/ab/Someone.jpg"
        self.assertEqual(portraits.wikimedia_file(local)[1], "wikipedia/en")

    def test_only_wikimedia_rasters_have_sizes(self):
        self.assertIsNone(portraits.wikimedia_file(
            "https://www.congress.gov/img/member/s001156_200.jpg"))
        self.assertIsNone(portraits.wikimedia_file(
            "https://clerk.house.gov/images/members/S001156.jpg"))
        # An SVG's thumbnails are PNGs under another name; not a portrait.
        self.assertIsNone(portraits.wikimedia_file(
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/Seal.svg"))

    def test_sizes_are_standard_and_narrower_than_the_original(self):
        # Wikimedia refuses any other width with HTTP 400 (https://w.wiki/GHai).
        standard = {20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840}
        self.assertLessEqual(set(portraits.THUMB_STEPS), standard)
        big = portraits.thumb_set(self.THUMB, 2364)
        self.assertEqual([w for w, _ in big], [120, 250, 330, 500])
        for width, url in big:
            self.assertTrue(url.endswith(f"/{width}px-Rep._Yassamin_Ansari_official_photo"
                                         "%2C_119th_Congress.jpg"), url)
            self.assertEqual(portraits.wikimedia_file(url)[1:],
                             portraits.wikimedia_file(self.THUMB)[1:])
        # Wikimedia will not enlarge: a small original is itself the top size.
        small = portraits.thumb_set(self.ORIGINAL, 400)
        self.assertEqual([w for w, _ in small], [120, 250, 330, 400])
        self.assertEqual(small[-1][1], self.ORIGINAL)
        self.assertEqual(portraits.thumb_set(self.ORIGINAL, None), [])

    def test_a_comma_or_space_cannot_end_a_srcset_entry(self):
        url = "https://upload.wikimedia.org/wikipedia/commons/7/7f/A,_B C.jpg"
        for _width, entry in portraits.thumb_set(url, 2000):
            self.assertNotIn(",", entry)
            self.assertNotIn(" ", entry)

    def _file(self, n):
        return self.THUMB.replace("7/7f", f"{n % 10}/{n % 10}{n % 10}").replace("Ansari", f"A{n}")

    def test_one_fetch_confirms_a_file_and_only_a_refusal_empties_its_set(self):
        ok, refused, unclear = self._file(1), self._file(2), self._file(3)
        unmeasured = self._file(4)
        cache = {"ok": {"url": ok}, "refused": {"url": refused}, "unclear": {"url": unclear},
                 "unmeasured": {"url": unmeasured},
                 "clerk": {"url": "https://clerk.house.gov/images/members/S001156.jpg"}}
        verdict = {ok: True, refused: False, unclear: None}
        asked = []

        def render(url):
            asked.append(url)
            return next(v for base, v in verdict.items()
                        if url.split("/thumb/")[1].split("/")[2] == base.split("/thumb/")[1].split("/")[2])

        with mock.patch.object(portraits, "image_sizes",
                               return_value={u: (2364, 3395) for u in (ok, refused, unclear)}), \
                mock.patch.object(portraits, "_render", side_effect=render):
            self.assertEqual(portraits.size_all(cache, log=lambda *a: None), 3)
        self.assertEqual(len(asked), 3)  # one fetch a file, never one a size
        self.assertTrue(all("/120px-" in url for url in asked), asked)
        self.assertEqual([w for w, _ in cache["ok"]["set"]], [120, 250, 330, 500])
        self.assertEqual((cache["ok"]["width"], cache["ok"]["height"]), (2364, 3395))
        self.assertEqual(cache["refused"]["set"], [])
        # Could not tell: the sizes are valid by construction, so they stay.
        self.assertEqual(len(cache["unclear"]["set"]), 4)
        self.assertNotIn("set", cache["unmeasured"])  # tried again next run
        self.assertNotIn("set", cache["clerk"])  # not Wikimedia: one URL, no sizes

    def test_checking_stops_when_wikimedia_stops_answering(self):
        files = [self._file(n) for n in range(12)]
        cache = {str(n): {"url": url} for n, url in enumerate(files)}
        with mock.patch.object(portraits, "image_sizes",
                               return_value={u: (2364, 3395) for u in files}), \
                mock.patch.object(portraits, "_render", return_value=None) as render:
            self.assertEqual(portraits.size_all(cache, log=lambda *a: None), 12)
        self.assertEqual(render.call_count, portraits._render_trip)
        self.assertTrue(all(len(record["set"]) == 4 for record in cache.values()))

    def test_apply_cache_and_cross_links_carry_the_sizes(self):
        sizes = [[120, self.THUMB.replace("960px", "120px")]]
        member = {"id": "M1", "isCandidate": False, "name": "A B", "state": "AZ",
                  "photos": ["placeholder"], "alsoRunningId": "C1"}
        running = {"id": "C1", "isCandidate": True, "name": "A B", "state": "AZ",
                   "photos": ["placeholder"], "incumbentId": "M1"}
        plain = {"id": "M2", "isCandidate": False, "name": "C D", "state": "AZ",
                 "photos": ["placeholder"]}
        cache = {
            portraits.profile_key(member): {"url": self.THUMB, "via": "wikipedia", "set": sizes},
            portraits.profile_key(plain): {"url": "https://clerk.house.gov/x.jpg", "via": "clerk.house.gov"},
        }
        portraits.inherit_cross_links([member, running, plain], cache)
        portraits.apply_cache([member, running, plain], cache)
        self.assertEqual(member["photoSet"], sizes)
        self.assertEqual(running["photoSet"], sizes)
        self.assertNotIn("photoSet", plain)

    def test_house_members_get_the_clerks_portrait_senators_the_articles(self):
        house = {"id": "H000001", "isCandidate": False, "name": "Hal House", "state": "TX",
                 "chamber": "House", "photos": ["placeholder"]}
        senate = {"id": "S000001", "isCandidate": False, "name": "Sue Senate", "state": "TX",
                  "chamber": "Senate", "photos": ["placeholder"]}
        bare = {"id": "S000002", "isCandidate": False, "name": "Sam Bare", "state": "OK",
                "chamber": "Senate", "photos": ["placeholder"]}
        article = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Sue_Senate.jpg"
        asked = []

        def check(url):
            asked.append(url)
            return True

        saved = {}
        with mock.patch.object(portraits, "load_cache", return_value={}), \
                mock.patch.object(portraits, "save_cache", side_effect=lambda c, r: saved.update(c)), \
                mock.patch.object(portraits, "check_image", side_effect=check), \
                mock.patch.object(portraits, "fetch_legislator_titles",
                                  return_value={"S000001": "Sue Senate", "S000002": "Sam Bare"}), \
                mock.patch.object(portraits, "wiki_page_images",
                                  return_value={"Sue Senate": ("Sue Senate", article)}), \
                mock.patch.object(portraits, "wiki_search_title", return_value=None), \
                mock.patch.object(portraits, "size_all", return_value=0):
            portraits.resolve_all([house, senate, bare], refresh=True, log=lambda *a: None)
        self.assertEqual(saved[portraits.profile_key(house)]["url"],
                         "https://clerk.house.gov/images/members/H000001.jpg")
        self.assertEqual(saved[portraits.profile_key(senate)]["url"], article)
        # No article portrait: the official one, small as it is.
        self.assertEqual(saved[portraits.profile_key(bare)]["url"],
                         "https://www.congress.gov/img/member/s000002_200.jpg")
        # A senator's congress.gov portrait is not even asked for when the
        # article has one.
        self.assertNotIn("https://www.congress.gov/img/member/s000001_200.jpg", asked)

    def test_no_chain_links_the_lapsed_photo_domain(self):
        # theunitedstates.io lapsed and was parked by 2026-10-03 (rule 35).
        chain = photos.member_photos("Linda Sanchez", "S001156")
        self.assertFalse([u for u in chain if "theunitedstates.io" in u], chain)
        self.assertIn("https://unitedstates.github.io/images/congress/450x550/S001156.jpg", chain)

    def test_a_srcset_from_another_file_is_an_error(self):
        mine = [[120, self.THUMB.replace("960px", "120px")],
                [250, self.THUMB.replace("960px", "250px").replace("%2C", ",")]]
        profile = {"name": "Yassamin Ansari", "state": "AZ", "photos": [self.THUMB],
                   "photoSet": mine}
        self.assertEqual(validate.check_photo_sets([profile]), [])
        profile["photoSet"] = mine + [[330, "https://upload.wikimedia.org/wikipedia/"
                                            "commons/thumb/1/1a/Other.jpg/330px-Other.jpg"]]
        issues = validate.check_photo_sets([profile])
        self.assertEqual([i.code for i in issues], ["photo-set-mixes-photographs"])
        self.assertEqual(issues[0].level, "error")


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


# ------------------------------------------------- filling gaps (kyc/enrich.py)

from kyc import enrich  # noqa: E402


def _page(html_text):
    return enrich.parse_page(html_text)


def _challenger(**extra):
    profile = {
        "id": "H6TX01234", "name": "Jane Q Smith", "isCandidate": True,
        "source": "fec-field", "raceStatus": "nominee", "chamber": "House (Candidate)",
        "state": "TX", "districtNum": 1, "officeLabel": "House • TX-1",
        "age": "Unknown", "birthdate": "", "education": "", "previous_professions": "",
        "platforms": "", "photos": ["placeholder"],
    }
    profile.update(extra)
    return apply_quality(profile)


class TestFillField(unittest.TestCase):
    """The one way an empty field is filled: never over a value, always credited."""

    def test_an_empty_field_is_filled_and_credited(self):
        profile = _challenger()
        self.assertTrue(normalize.fill_field(profile, "education", "Rice University (BA)",
                                             "wikipedia"))
        self.assertEqual(profile["education"], "Rice University (BA)")
        self.assertNotIn("education", profile["quality"])
        self.assertEqual(profile["fieldSources"], {"education": "wikipedia"})

    def test_a_roster_value_is_never_overwritten(self):
        profile = apply_quality({"education": "Yale (JD)"})
        self.assertFalse(normalize.fill_field(profile, "education", "Harvard", "wikipedia"))
        self.assertEqual(profile["education"], "Yale (JD)")
        self.assertNotIn("fieldSources", profile)

    def test_a_sources_own_placeholder_is_not_promoted_to_a_finding(self):
        profile = _challenger()
        self.assertFalse(normalize.fill_field(profile, "education", "N/A", "wikipedia"))
        self.assertEqual(profile["quality"]["education"], "unknown")


class TestInfobox(unittest.TestCase):
    ARTICLE = """{{Short description|American politician}}
{{Infobox officeholder
| name = Jane Smith
| birth_date = {{birth date and age|mf=yes|1975|4|12}}<ref>{{cite web|url=x}}</ref>
| alma_mater = {{plainlist|
* [[Rice University]] ([[Bachelor of Arts|BA]])
* [[University of Texas School of Law|University of Texas]] ([[Juris Doctor|JD]])
}}
| occupation = {{hlist|Attorney|[[Teacher|teacher]]}}
| party = {{nowrap|[[Democratic Party (United States)|Democratic]]}}
}}
'''Jane Smith''' (born April 12, 1975) is ..."""

    def test_the_infobox_gives_birth_education_and_occupation(self):
        self.assertEqual(enrich.wiki_facts(self.ARTICLE), {
            "born": "1975-04-12",
            "education": "Rice University (BA); University of Texas (JD)",
            "occupation": "Attorney; teacher",
        })

    def test_a_year_alone_or_an_impossible_date_is_not_a_birthdate(self):
        self.assertEqual(enrich.birth_date("{{birth year and age|1975}}"), "")
        self.assertEqual(enrich.birth_date("{{birth date and age|1975|2|30}}"), "")
        self.assertEqual(enrich.birth_date("{{Birth date and age|1961|8|4|df=yes}}"),
                         "1961-08-04")

    def test_line_breaks_and_lists_become_one_semicolon_list(self):
        self.assertEqual(enrich.list_text("[[Yale University|Yale]] (BA)<br />Oxford (MSc)"),
                         "Yale (BA); Oxford (MSc)")
        self.assertEqual(enrich.list_text("{{ubl|Lawyer|lawyer|Farmer}}"), "Lawyer; Farmer")

    def test_no_infobox_no_facts(self):
        self.assertEqual(enrich.wiki_facts("'''Jane Smith''' is a teacher."), {})


class TestCampaignSiteVerdict(unittest.TestCase):
    """May this page stand for the candidate's campaign?"""

    PROFILE = {"name": "Mike France"}
    GOOD = ("<title>Mike France for Congress</title><h1>Meet Mike</h1>"
            "<p>Mike France is running to lower costs. Casino workers deserve a raise.</p>")

    def verdict(self, markup, status=200, url="https://votemikefrance.com/",
                final="https://votemikefrance.com/"):
        return enrich.assess(self.PROFILE, url, final, status, _page(markup))

    def test_a_page_that_names_the_candidate_is_safe(self):
        self.assertEqual(self.verdict(self.GOOD), (True, "ok"))

    def test_a_hijacked_page_is_refused_even_under_the_candidates_name(self):
        # votemikefrance.com served a gambling page under his name (rule 35).
        spam = "<title>Mike France - Slot Gacor Hari Ini</title><p>situs slot maxwin</p>"
        self.assertEqual(self.verdict(spam), (False, enrich.HIJACKED))

    def test_a_parked_domain_is_refused(self):
        self.assertEqual(self.verdict("<title>votemikefrance.com is for sale</title>"
                                      "<p>Buy this domain today. Mike France</p>"),
                         (False, enrich.PARKED))

    def test_the_name_in_the_address_alone_proves_nothing(self):
        shop = "<title>Abudahbisa</title><p>" + "Electronics for everyone. " * 30 + "</p>"
        self.assertEqual(self.verdict(shop), (False, enrich.ELSEWHERE))
        self.assertEqual(self.verdict("<title>Coming Soon</title><p>We're under construction."
                                      " Please check back for an update soon.</p>"),
                         (False, enrich.UNBUILT))

    def test_a_parking_script_is_parked_whatever_the_page_says(self):
        lander = ('<html><head><script src="/parking-lander/static/js/main.js"></script>'
                  "<script>window.LANDER_SYSTEM='PW'</script></head></html>")
        self.assertEqual(self.verdict(lander), (False, enrich.PARKED))

    def test_spam_hidden_in_the_campaigns_own_page_is_reported_not_unlinked(self):
        # ronjohnsonforsenate.com, 2026-10-02: his own page, with casino links
        # in a display:none block and an off-screen div.
        page = (self.GOOD + '<div id="hidden-post" style="display:none">Claim free spins at '
                '<a href="http://x.pl/">Casino Bonus</a></div>'
                '<div style="position: absolute; left: -8046px;">online casino reviews</div>')
        self.assertEqual(self.verdict(page), (True, enrich.COMPROMISED))
        visible = self.GOOD + "<p>" + "Best online casinos and free spins. " * 5 + "</p>"
        self.assertEqual(self.verdict(visible), (False, enrich.HIJACKED))

    def test_a_site_that_cannot_be_read_concludes_nothing(self):
        # Rule 8: unreachable, a bot wall (403, or 202 with a challenge), a
        # server error, and a page with nothing but a video are not evidence.
        for status in (None, 403, 202, 429, 503):
            self.assertIsNone(self.verdict("", status=status)[0], status)
        self.assertIsNone(self.verdict("<title>Where's Ya Fatha?</title><video></video>")[0])
        self.assertEqual(self.verdict("", status=404), (False, "HTTP 404"))
        self.assertFalse(self.verdict("", status=301, final="https://moneyslim.nl/")[0])

    def test_a_single_mention_of_gambling_is_not_hijacking(self):
        self.assertTrue(self.verdict(self.GOOD)[0])

    def test_the_names_a_campaign_actually_uses_count(self):
        def named(name, text, host):
            return enrich.names_candidate({"name": name}, text, host)
        self.assertTrue(named("Kristi Burke", "Kristi for Congress", "votekristiburke.com"))
        self.assertFalse(named("Kristi Burke", "Kristi for Congress", "example.com"))
        self.assertTrue(named("Darline Graham Nordone", "Darline Graham for Senate", "x.com"))
        self.assertTrue(named("Maad Abu-Ghazalah", "Maad Abu-Ghazalah for NC", "getmaad.org"))
        self.assertFalse(named("Mike Smith", "Smithfield Foods", "smithfield.com"))

    def test_a_compressed_body_is_read_and_a_parking_script_followed(self):
        import gzip
        page = b"<title>Jane Smith</title>" * 100
        body = gzip.compress(page)
        self.assertEqual(enrich._decoded(body, "gzip"), page)
        # A body read only up to MAX_BODY is cut off before the gzip trailer.
        self.assertEqual(enrich._decoded(body[:-8], "gzip"), page)
        self.assertIsNone(enrich._decoded(b"\x1b\x00", "br"))
        jump = enrich._SCRIPT_REDIRECT.search(
            '<script>window.onload=function(){window.location.href="/lander"}</script>')
        self.assertEqual(jump.group(1), "/lander")


class TestCampaignWords(unittest.TestCase):
    """What a campaign says about itself, quoted rather than paraphrased."""

    def describe(self, text, name="Jane Smith"):
        return enrich.description(_page(f'<meta name="description" content="{text}">'), name)

    def test_a_label_is_not_a_description(self):
        self.assertEqual(self.describe("Jane Smith for Congress - Official Campaign Website"), "")
        self.assertEqual(self.describe(
            "Jane is running for U.S. Congress in Pennsylvania's 9th Congressional District."), "")

    def test_a_truncated_description_is_cut_back_to_whole_sentences(self):
        self.assertEqual(self.describe(
            "Jane Smith has spent 14 years as the county's top prosecutor, protecting families. "
            "She has never backed down from a fight and she"),
            "Jane Smith has spent 14 years as the county's top prosecutor, protecting families.")

    def test_calls_to_action_and_title_bars_are_dropped(self):
        self.assertEqual(self.describe(
            "Learn about Jane Smith's campaign and her values. Get involved today."), "")
        self.assertEqual(self.describe(
            "Jane Smith for Congress | Nurse, mother, fighter for affordable care"), "")
        self.assertEqual(self.describe(
            "campaign for real change and a better future! learn more about Jane"), "")

    def test_what_a_full_run_found_is_not_a_description(self):
        # Each of these reached a profile on the first full run.
        for text in (
            "Let's make things work for Hardworking Alaskans DONATE WITH ANEDOT "
            "https://youtu.be/voLhcztE0a8 Bill is endorsed by: 0 Organizations",
            "Gerald Malloy and Howie Carr discuss upcoming debates, and 25 years of "
            "Vermont Federal legislators effect on Vermonters.",
            "An official campaign website for Bridgford for Iowa, providing information "
            "about the candidate, their platform, and ways to get involved.",
            "Meet Julie Fortier, Democrat for U.S. House in Illinois District 12. Learn her "
            "vision, issues, and how to donate or get involved.",
            "Laura Jones wants to represent all of the people, not just some of the people in U.S.",
            "Please stay engaged! YOU are the most important part of #RussIsForUS.",
        ):
            self.assertEqual(self.describe(text, "Jane Smith"), "", text)

    def test_abbreviations_do_not_end_sentences(self):
        self.assertEqual(self.describe(
            "Bill Redpath for US Senate Donate Now. I'm Bill Redpath, running in the special "
            "election for the U.S. Senate in Ohio for 2026. My platform combines conservative "
            "economics with liberal positions on social issues.", "William Redpath"),
            "I'm Bill Redpath, running in the special election for the U.S. Senate in Ohio for "
            "2026. My platform combines conservative economics with liberal positions on social "
            "issues.")
        self.assertEqual(self.describe(
            "Sarah Trone Garriott is a mom, State Senator, and Lutheran Minister running to flip "
            "IA-03. She's running to lower costs for working families...", "Sarah Trone Garriott"),
            "Sarah Trone Garriott is a mom, State Senator, and Lutheran Minister running to flip "
            "IA-03.")

    def test_a_real_description_is_kept_verbatim(self):
        text = ("Retired Air Force officer Jane Smith is running to fight for affordability, "
                "accountability, and the state's most vulnerable.")
        self.assertEqual(self.describe(text), text)

    def test_the_issues_link_is_the_index_not_the_privacy_policy(self):
        page = _page('<a href="/privacy-policy">Privacy Policy</a>'
                     '<a href="/issue-energy/">Energy</a><a href="/meet-jane">Meet</a>'
                     '<a href="/key-issues">Where Jane Stands</a>')
        self.assertEqual(enrich.issues_link(page, "https://janesmith.com/"),
                         "https://janesmith.com/key-issues")
        page = _page('<a href="/policies">Privacy policies</a><a href="/platform">Platform</a>')
        self.assertEqual(enrich.issues_link(page, "https://janesmith.com/"),
                         "https://janesmith.com/platform")

    def test_issue_headings_are_one_level_of_issues_and_nothing_else(self):
        page = _page(
            "<h1>On the Issues</h1><h2>Jane's Top Issues</h2>"
            "<h3>#1 Healthcare</h3><h4>Lower premiums</h4>"
            "<h3>Rob Wittman has let prices skyrocket</h3>"
            "<h3>Lower Costs, Raise Wages</h3><h3>Promote</h3><h3>{{ card.title }}</h3>"
            "<h3>Public Schools</h3><h3>Ready to vote?</h3><h3>Donate Today</h3>")
        self.assertEqual(enrich.issue_headings(page, "Jane Smith", rivals={"wittman"}),
                         ["Healthcare", "Lower Costs, Raise Wages", "Public Schools"])

    def test_furniture_fragments_and_addresses_are_not_issues(self):
        page = _page("".join(f"<h2>{t}</h2>" for t in (
            "\U0001fa99 Cost of living", "Healthcare »", "Housing​", "Housing",
            "WE ARE FIGHTING FOR", "and It's Running Out", "This website uses cookies",
            "Bill 1 of 6", "Checks can be mailed to", "Sam for Montana PO Box 7224",
            "(Paid for by hardworking Americans)", "Amy's complete Ballotpedia survey",
            "Get the latest updates from the campaign trail", "Public Schools",
            "Clean Water", "Fair Taxes", "Veterans")))
        self.assertEqual(enrich.issue_headings(page, "Amy Chai"),
                         ["Cost of living", "Healthcare", "Housing", "Public Schools",
                          "Clean Water", "Fair Taxes", "Veterans"])

    def test_a_page_that_is_mostly_furniture_gives_no_list(self):
        page = _page("".join(f"<h2>{t}</h2>" for t in (
            "What We Can Achieve Together", "Clean Water", "Fair Taxes", "Campaign News",
            "Follow Us", "Become a Volunteer", "Keep Up with the Campaign", "Donate",
            "Contact", "Privacy Policy")))
        self.assertEqual(enrich.issue_headings(page, "Ron Russell"), [])

    def test_a_ballot_question_page_is_never_the_issues_page(self):
        page = _page('<a href="/ballot-questions/">Where Tyler Stands</a>'
                     '<a href="/the-issues">The Issues</a>')
        self.assertEqual(enrich.issues_link(page, "https://macallister4congress.com/"),
                         "https://macallister4congress.com/the-issues")

    def test_a_page_of_issues_set_in_h1s_is_read(self):
        page = _page("".join(f"<h1>{t}</h1>" for t in
                             ("Health Care", "Public Education", "Rural Investment")))
        self.assertEqual(enrich.issue_headings(page, "James Talarico"),
                         ["Health Care", "Public Education", "Rural Investment"])

    def test_fewer_than_three_issues_is_not_a_list(self):
        self.assertEqual(enrich.issue_headings(_page("<h2>Healthcare</h2><h2>Jobs</h2>"),
                                               "Jane Smith"), [])


class TestCampaignPortraits(unittest.TestCase):
    """A campaign image is a portrait only when it is named for the candidate
    and shaped like one (rule 24)."""

    PROFILE = {"name": "Shannon Leigh Taylor"}

    def picks(self, *tags):
        return enrich.portrait(_page("".join(tags)), "https://shannontaylorva.com/", self.PROFILE)

    def test_a_file_named_for_the_candidate_is_considered(self):
        self.assertEqual(self.picks('<img src="/up/Shannon_Taylor_Headshot-1024x1024.jpg">'),
                         [("https://shannontaylorva.com/up/Shannon_Taylor_Headshot-1024x1024.jpg",
                           True)])

    def test_an_image_named_only_in_its_alt_text_is_considered(self):
        self.assertEqual(self.picks('<img src="https://cdn.x.com/4f9a2c.png" alt="Shannon Taylor">'),
                         [("https://cdn.x.com/4f9a2c.png", False)])

    def test_what_a_full_run_took_that_was_not_a_portrait(self):
        # Each of these reached a profile before the portrait rules tightened.
        self.assertEqual(self.picks(
            '<img src="/Taylor-Website-Icons-2.png">',
            '<img src="/Taylor_SocialShare_SQ.png">',
            '<img src="/taylor_collage.jpg">',
            '<img src="/webclip-shannon-taylor.png">',
            '<img src="/Taylors Mom.png" alt="Shannon Taylor">',
            '<img src="/ts.jpg" alt="Shannon Taylor merch shirt">'), [])
        # "Photo" is not a headshot, so "Photo Edit Purple" is three words about
        # something other than the person: a group photograph, on the first run.
        self.assertEqual(self.picks('<img src="/Taylor_Photo_Edit_Purple.png">'), [])

    def test_logos_crowds_slogans_and_strangers_are_not(self):
        self.assertEqual(self.picks(
            '<img src="/taylor-logo.png">',
            '<img src="/Taylor+for+Congress.png">',
            '<img src="/taylor-with-supporters.jpg">',
            '<img src="/taylor_website_loyal_to_you.png">',
            '<img src="/headshot.jpg" alt="Senator Kaine">',
            '<img src="http://insecure.example/taylor.jpg">'), [])

    def test_image_sizes_are_read_from_the_header_bytes(self):
        png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (300).to_bytes(4, "big") + \
            (400).to_bytes(4, "big")
        gif = b"GIF89a" + (640).to_bytes(2, "little") + (200).to_bytes(2, "little")
        jpeg = (b"\xff\xd8\xff\xe0\x00\x10" + b"\x00" * 14 + b"\xff\xc0\x00\x11\x08"
                + (480).to_bytes(2, "big") + (360).to_bytes(2, "big") + b"\x03" + b"\x00" * 9)
        webp = (b"RIFF\x00\x00\x00\x00WEBPVP8X" + b"\x00" * 8
                + (499).to_bytes(3, "little") + (599).to_bytes(3, "little"))
        self.assertEqual(enrich.image_size(png), (300, 400))
        self.assertEqual(enrich.image_size(gif), (640, 200))
        self.assertEqual(enrich.image_size(jpeg), (360, 480))
        self.assertEqual(enrich.image_size(webp), (500, 600))
        self.assertIsNone(enrich.image_size(b"not an image"))


class TestApplyEnrichment(unittest.TestCase):
    AS_OF = __import__("datetime").date(2026, 9, 30)

    def cache(self, **entry):
        return {"people": {"H6TX01234": entry}}

    SAFE_SITE = {"url": "https://janesmith.com", "final": "https://janesmith.com/",
                 "status": 200, "safe": True, "reason": "ok",
                 "description": "A nurse running to make care affordable for every family.",
                 "issues": ["Healthcare", "Lower costs", "Public schools"],
                 "issuesUrl": "https://janesmith.com/issues",
                 "portrait": "https://janesmith.com/jane-smith-headshot.jpg"}

    def test_infobox_facts_fill_empty_fields_with_the_age_at_the_build_date(self):
        profile = _challenger()
        counts = enrich.apply_cache([profile], self.cache(wiki={
            "born": "1975-10-15", "education": "Rice University (BA)", "occupation": "Nurse"}),
            as_of=self.AS_OF)
        self.assertEqual(profile["birthdate"], "1975-10-15")
        self.assertEqual(profile["age"], 50)          # not yet 51 on 2026-09-30
        self.assertEqual(profile["previous_professions"], "Nurse")
        self.assertEqual(profile["fieldSources"], {"birthdate": "wikipedia",
                                                   "education": "wikipedia",
                                                   "previous_professions": "wikipedia"})
        self.assertEqual(counts["born"], 1)

    def test_what_the_election_page_already_said_is_kept(self):
        profile = _challenger()
        normalize.fill_field(profile, "previous_professions", "state senator", "election-page")
        enrich.apply_cache([profile], self.cache(wiki={"occupation": "Politician"}),
                           as_of=self.AS_OF)
        self.assertEqual(profile["previous_professions"], "state senator")
        self.assertEqual(profile["fieldSources"]["previous_professions"], "election-page")

    def test_the_campaign_site_gives_a_quote_a_platform_and_a_portrait(self):
        profile = _challenger(campaignSite="https://janesmith.com")
        enrich.apply_cache([profile], self.cache(site=self.SAFE_SITE), as_of=self.AS_OF)
        self.assertEqual(profile["campaignQuote"], self.SAFE_SITE["description"])
        self.assertEqual(profile["platforms"], "Healthcare; Lower costs; Public schools")
        self.assertEqual(profile["fieldSources"]["platforms"], "campaign-site")
        self.assertEqual(profile["campaignIssuesUrl"], "https://janesmith.com/issues")
        self.assertEqual(profile["photos"][0], self.SAFE_SITE["portrait"])
        self.assertEqual(profile["photoSource"], "campaign-site")

    def test_an_existing_portrait_and_a_members_photo_are_never_replaced(self):
        pictured = _challenger(campaignSite="https://janesmith.com", photoSource="wikipedia",
                               photos=["https://upload.wikimedia.org/jane.jpg"])
        roster = _challenger(campaignSite="https://janesmith.com", source=None)
        enrich.apply_cache([pictured], self.cache(site=self.SAFE_SITE), as_of=self.AS_OF)
        enrich.apply_cache([roster], self.cache(site=self.SAFE_SITE), as_of=self.AS_OF)
        self.assertEqual(pictured["photos"], ["https://upload.wikimedia.org/jane.jpg"])
        self.assertNotIn("photoSource", roster)

    def test_an_election_page_site_is_linked_only_when_it_checked_out(self):
        listed = dict(self.SAFE_SITE, url="https://smith2026.com")
        profile = _challenger()
        enrich.apply_cache([profile], self.cache(listed=listed), as_of=self.AS_OF)
        self.assertEqual(profile["campaignSite"], "https://smith2026.com")
        self.assertEqual(profile["campaignSiteVia"], "election-page")

        unsure = _challenger()
        enrich.apply_cache([unsure], self.cache(listed=dict(listed, safe=None)),
                           as_of=self.AS_OF)
        self.assertNotIn("campaignSite", unsure)

        # A committee site that checks out wins over the page's.
        filed = _challenger(campaignSite="https://janesmith.com")
        enrich.apply_cache([filed], self.cache(site=self.SAFE_SITE, listed=listed),
                           as_of=self.AS_OF)
        self.assertEqual(filed["campaignSite"], "https://janesmith.com")
        self.assertNotIn("campaignSiteVia", filed)

    def test_a_hijacked_committee_site_is_withdrawn_whoever_filed_it(self):
        bad = {"url": "https://votemikefrance.com", "safe": False, "reason": enrich.HIJACKED}
        member = {"id": "H6TX01234", "name": "Mike France", "isCandidate": False,
                  "raceStatus": "nominee", "campaignSite": "https://votemikefrance.com"}
        counts = enrich.apply_cache([member], self.cache(site=bad), as_of=self.AS_OF)
        self.assertNotIn("campaignSite", member)
        self.assertEqual(counts["withdrawn"], 1)

    def test_a_site_that_did_not_name_the_candidate_stays_but_is_reported(self):
        unnamed = {"url": "https://janesmith.com", "safe": False, "reason": enrich.UNNAMED}
        profile = _challenger(campaignSite="https://janesmith.com")
        enrich.apply_cache([profile], self.cache(site=unnamed), as_of=self.AS_OF)
        self.assertEqual(profile["campaignSite"], "https://janesmith.com")
        self.assertNotIn("campaignQuote", profile)
        issues = validate.check_campaign_sites([profile], self.cache(site=unnamed))
        self.assertEqual([i.code for i in issues], ["campaign-site-unconfirmed"])

    def test_each_kind_of_site_problem_is_reported_once_and_decided_ones_not_at_all(self):
        def person(pid, url, safe, reason):
            return ({"id": pid, "name": pid, "officeLabel": "House • TX-1"},
                    {"site": {"url": url, "safe": safe, "reason": reason}})
        rows = [person("A", "https://a.com", False, enrich.PARKED),
                person("B", "https://b.com", False, enrich.ELSEWHERE),
                person("C", "https://c.com", True, enrich.COMPROMISED),
                person("D", "https://joshweil.us", False, enrich.HIJACKED),
                person("E", "https://e.com", True, "ok")]
        cache = {"people": {p["id"]: entry for p, entry in rows}}
        issues = validate.check_campaign_sites([p for p, _ in rows], cache)
        self.assertEqual({i.code: len(i.detail) for i in issues},
                         {"campaign-site-withdrawn": 1, "campaign-site-unconfirmed": 1,
                          "campaign-site-compromised": 1})

    def test_an_unreachable_site_keeps_only_its_own_earlier_verdict(self):
        old = {"url": "https://janesmith.com", "safe": True, "reason": "ok"}
        again = {"url": "https://janesmith.com", "safe": None, "reason": "unreachable"}
        moved = {"url": "https://smith2026.com", "safe": None, "reason": "unreachable"}
        self.assertEqual(enrich._keep(old, again)["safe"], True)
        self.assertIsNone(enrich._keep(old, moved)["safe"])
        self.assertIsNone(enrich._keep(old, None))

    def test_someone_out_of_the_race_is_left_alone(self):
        profile = _challenger(raceStatus="eliminated", campaignSite="https://janesmith.com")
        enrich.apply_cache([profile], self.cache(site=self.SAFE_SITE,
                                                 wiki={"born": "1975-10-15"}), as_of=self.AS_OF)
        self.assertNotIn("campaignQuote", profile)
        self.assertEqual(profile["quality"]["birthdate"], "unknown")


class TestEnrichmentAgainstTheRealCache(unittest.TestCase):
    """The committed cache, applied the way the build applies it."""

    @classmethod
    def setUpClass(cls):
        import datetime

        from kyc import campaigns, candidates, legislators, results

        cache = enrich.load_cache(ROOT)
        if not cache:
            raise unittest.SkipTest("no enrichment cache committed")
        finance = fec.load_cache(ROOT)
        cls.profiles, stats = build_profiles(
            load_all(ROOT), snapshot=legislators.load_snapshot(ROOT),
            field=candidates.load_cache(ROOT), finance=finance)
        fec.apply_cache(cls.profiles, finance)
        campaigns.apply_cache(cls.profiles, campaigns.load_cache(ROOT))
        portraits.apply_cache(cls.profiles, portraits.load_cache(ROOT))
        results.apply_cache(cls.profiles, results.load_cache(ROOT))
        cls.cache = cache
        enrich.apply_cache(cls.profiles, cache,
                           as_of=datetime.date.fromisoformat(stats["ageAsOf"]))

    def test_every_filled_field_names_a_known_source(self):
        known = {"wikipedia", "election-page", "campaign-site"}
        seen = {s for p in self.profiles for s in (p.get("fieldSources") or {}).values()}
        self.assertLessEqual(seen, known)

    def test_campaign_portraits_and_quotes_belong_to_challengers_still_running(self):
        for profile in self.profiles:
            if profile.get("photoSource") == "campaign-site" or profile.get("campaignQuote"):
                self.assertTrue(enrich.running(profile), profile["name"])
            if profile.get("photoSource") == "campaign-site":
                self.assertEqual(profile.get("source"), "fec-field", profile["name"])
                self.assertTrue(profile["photos"][0].startswith("https://"), profile["name"])

    def test_no_profile_links_a_site_the_cache_found_hijacked(self):
        for profile in self.profiles:
            site = (self.cache["people"].get(profile["id"]) or {}).get("site")
            if enrich.withdrawn(site):
                self.assertNotEqual(profile.get("campaignSite"), site["url"], profile["name"])


class TestPortraitOverrides(unittest.TestCase):
    """A person's look at an image outlasts the weekly re-read."""

    URL = "https://kaileebuller.com/wp-content/uploads/2026/03/Buller.jpg"

    def test_an_image_ruled_out_by_hand_never_reaches_the_profile(self):
        profile = _challenger(campaignSite="https://kaileebuller.com")
        cache = {"people": {"H6TX01234": {"site": {
            "url": "https://kaileebuller.com", "safe": True, "reason": "ok",
            "portrait": self.URL}}}}
        enrich.apply_cache([profile], cache)
        self.assertNotIn("photoSource", profile)
        stale = [u for i in validate.check_portrait_overrides(cache) for u in i.detail]
        self.assertNotIn(self.URL, stale)       # the site still offers it

    def test_the_rules_skip_it_and_remember_that_they_did(self):
        page = _page(f'<img src="{self.URL}">')
        pictures = enrich.portrait(page, "https://kaileebuller.com/", {"name": "Kailee Buller"})
        self.assertEqual([u for u, _ in pictures], [self.URL])
        self.assertIn(self.URL, enrich.overrides.NOT_A_PORTRAIT)

    def test_an_entry_no_site_offers_any_more_is_reported(self):
        issues = validate.check_portrait_overrides({"people": {}})
        self.assertEqual([i.code for i in issues], ["stale-portrait-override"])
