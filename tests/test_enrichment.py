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
            "wikipedia": "A B (politician)", "wikipediaVia": "election-page",
        }
        cache = {
            portraits.profile_key(profile): {"url": "https://new/2.jpg", "via": "wikipedia",
                                             "title": "A B", "linked": "A B (politician)"}
        }
        portraits.apply_cache([profile], cache)
        self.assertEqual(profile["photos"][0], "https://new/2.jpg")
        self.assertEqual(profile["photo_url"], "https://new/2.jpg")
        self.assertEqual(profile["photoSource"], "wikipedia")

    def test_a_portrait_by_a_route_rule_24_forbids_is_not_applied(self):
        """The cache held portraits found by guessing "<Name> (politician)"
        and by searching a name: Kansas's Senate nominee Adam Hamilton, a
        pastor his ballot page links, carried a 1930s photograph of another
        Adam Hamilton. A cached record is applied only by an id or the
        article the profile links."""
        def profile(**extra):
            return dict({"id": "CAND_18", "isCandidate": True, "name": "Adam Hamilton",
                         "state": "KS", "chamber": "Senate (Candidate)",
                         "photos": ["placeholder"]}, **extra)
        linked = {"wikipedia": "Adam Hamilton (pastor)", "wikipediaVia": "election-page"}
        guessed = {"url": "https://x/1930s.jpg", "via": "wikipedia",
                   "title": "Adam Hamilton (politician)"}
        searched = {"url": "https://x/s.jpg", "via": "wikipedia-search",
                    "title": "Adam Hamilton (pastor)"}
        right = {"url": "https://x/pastor.jpg", "via": "wikipedia",
                 "title": "Adam Hamilton (pastor)", "linked": "Adam Hamilton (pastor)"}
        for record, ok in ((guessed, False), (searched, False), (right, True)):
            person = profile(**linked)
            portraits.apply_cache([person], {portraits.profile_key(person): record})
            self.assertEqual(person["photos"][0] != "placeholder", ok, record)
        # The right article, but the profile no longer links it.
        person = profile()
        portraits.apply_cache([person], {portraits.profile_key(person): right})
        self.assertEqual(person["photos"], ["placeholder"])
        self.assertIsNone(person["photoSource"])
        # A redirect that lands on another subject is refused even when linked.
        person = profile(wikipedia="Brian McGinnis", wikipediaVia="election-page",
                         name="Brian McGinnis")
        protest = {"url": "https://x/p.jpg", "via": "wikipedia", "linked": "Brian McGinnis",
                   "title": "Protests against the 2026 Iran war"}
        self.assertFalse(portraits.route_ok(person, protest))
        # A member's: by bioguide id, or the article the mapping names.
        member = {"id": "G000553", "isCandidate": False, "name": "Al Green", "state": "TX",
                  "wikipedia": "Al Green (politician)"}
        self.assertTrue(portraits.route_ok(member, {"url": "u", "via": "clerk.house.gov"}))
        self.assertTrue(portraits.route_ok(member, {"url": "u", "via": "wikipedia",
                                                    "title": "Al Green (politician)"}))
        self.assertFalse(portraits.route_ok(member, {"url": "u", "via": "wikipedia",
                                                     "title": "Al Green"}))


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
                  "photos": ["placeholder"], "alsoRunningId": "C1", "wikipedia": "A B"}
        running = {"id": "C1", "isCandidate": True, "name": "A B", "state": "AZ",
                   "photos": ["placeholder"], "incumbentId": "M1"}
        plain = {"id": "M2", "isCandidate": False, "name": "C D", "state": "AZ",
                 "photos": ["placeholder"]}
        cache = {
            portraits.profile_key(member): {"url": self.THUMB, "via": "wikipedia", "set": sizes,
                                            "title": "A B", "credit": {"licence": "CC0"}},
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
                "candidate_loans": 0, "coverage_end": "2026-06-30",
                "candidate_id": "H0TX00001",
            }
        }
        fec.apply_cache([profile], cache)
        self.assertEqual(profile["receipts"], "$100.00")
        self.assertEqual(profile["financeSource"], "FEC")
        self.assertEqual(profile["financeAsOf"], "2026-06-30")
        self.assertNotIn("receipts", profile["quality"])
        self.assertIn("Individual 75%", profile["funding_sources"])

    def test_a_candidates_own_loan_is_self_funding_and_shares_are_of_receipts(self):
        """Jefferson Shreve (IN-6) lent his campaign $2,000,000 of the
        $2,532,230 it received, and read "PACs 70%, Individual 30%": the
        shares were of four contribution types, and his loan was none."""
        record = {
            "receipts": 2532230.0, "individual_contributions": 145824.0,
            "pac_contributions": 375750.0, "party_contributions": 0,
            "self_funding": 0, "candidate_loans": 2000000.0, "other_loans": 0,
            "transfers": 10000.0, "offsets": 556.0, "other_receipts": 100.0,
        }
        breakdown, line = fec.funding(record)
        self.assertEqual(line, "Self-funded (incl. loans) 79%, PACs 15%, Individual 6%, "
                               "Transfers from other committees <1%, Other <1%")
        self.assertEqual(breakdown["Self-funded (incl. loans)"], 2000000.0)
        self.assertNotIn("Party", breakdown)
        self.assertIsNone(fec.funding_base(record, breakdown))
        # Only a loan earns the words; a gift alone is "Self-funded".
        _parts, gift = fec.funding({"receipts": 100.0, "individual_contributions": 90.0,
                                    "self_funding": 10.0, "candidate_loans": 0})
        self.assertEqual(gift, "Individual 90%, Self-funded 10%")
        # No label holds the ", " the page splits pairs on.
        self.assertFalse([label for label, _f in fec.FUNDING_PARTS if ", " in label])
        self.assertNotIn(", ", fec.SELF_WITH_LOANS)

    def test_a_negative_adjustment_says_what_the_shares_are_of(self):
        """Shri Thanedar: loans $2,970,000 of $3,194,222 received, with other
        receipts of -$774,378. The shares are of the positive parts, and the
        profile says that sum, since it is not the receipts shown."""
        record = {"receipts": 3194222.05, "individual_contributions": 912720.0,
                  "pac_contributions": 85880.0, "party_contributions": 0,
                  "self_funding": 0, "candidate_loans": 2970000.0, "other_loans": 0,
                  "transfers": 0, "offsets": 0, "other_receipts": -774377.68}
        breakdown, line = fec.funding(record)
        self.assertNotIn("Other", breakdown)
        self.assertEqual(fec.funding_base(record, breakdown), 3968600.0)
        self.assertTrue(line.startswith("Self-funded (incl. loans) 75%"), line)
        profile = {"name": "Shri Thanedar", "state": "MI", "chamber": "House", "quality": {}}
        fec.apply_cache([profile], {fec.profile_key(profile): dict(record, candidate_id="H2MI13204")})
        self.assertEqual(profile["fundingBase"], "$3,968,600.00")
        self.assertEqual(profile["receipts"], "$3,194,222.05")

    def test_a_record_read_before_loans_were_has_no_split(self):
        # Its shares would be of the wrong total; finance reads it again.
        self.assertEqual(fec.funding({"receipts": 10.0, "individual_contributions": 10.0}),
                         (None, None))

    def test_refunds_never_push_a_share_past_the_whole(self):
        breakdown, line = fec.funding({"receipts": 50.0, "individual_contributions": 80.0,
                                       "candidate_loans": 20.0})
        self.assertEqual(line, "Individual 80%, Self-funded (incl. loans) 20%")

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
        cls.record = raw["record"]
        cls.profiles, _ = build_profiles(raw)
        cls.races = races.build(cls.profiles, record=cls.record)
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

        # Every House seat on the ballot is a race, held or not: the record
        # froze them all, a vacant seat (TX-23, FL-20) among them. Every
        # seat a member holds is one of them.
        frozen = {rid for rid, r in self.record["races"].items()
                  if r["chamber"] == "House" and r["state"] not in TERRITORIES}
        self.assertEqual({r["id"] for r in voting}, frozen)
        held = {races.race_id("House", p["state"], p["districtNum"]) for p in self.profiles
                if not p["isCandidate"] and p["chamber"] == "House"
                and p["state"] not in TERRITORIES and p.get("raceRole") != "winner"}
        self.assertLessEqual(held, frozen)
        self.assertLessEqual(len(voting), 435)

    def test_senators_not_up_belong_to_no_race(self):
        from kyc.record import seated

        senators = [p for p in self.profiles if seated(p) and "Senate" in p["chamber"]]
        up = [p for p in senators if p["seatUp2026"]]
        won = [p for p in senators if p.get("raceRole") == "winner"]
        idle = [p for p in senators if not p["seatUp2026"] and p not in won]
        self.assertTrue(idle)
        self.assertTrue(all(p["raceId"] is None for p in idle))
        # Every Senate race's holder is a sitting senator or a former member.
        former = [p for p in self.profiles if p.get("formerMember")
                  and "Senate" in p["chamber"] and p["seatUp2026"]]
        self.assertEqual(len(up) + len(former),
                         sum(1 for rid in self.record["races"] if rid.startswith("S-")))

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


class TestPhotoCredits(unittest.TestCase):
    """Rule 87: every photograph says whose it is, and a Commons file on
    what licence. 148 of 381 Wikimedia portraits were CC BY or CC BY-SA and
    none was credited (TRUST-08)."""

    FILE = ("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/"
            "Thomas_Feely.jpg/960px-Thomas_Feely.jpg")
    INFO = {
        "width": 2000, "height": 2500,
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Thomas_Feely.jpg",
        "extmetadata": {
            "Artist": {"value": '<a href="//www.flickr.com/people/gageskidmore">Gage '
                                'Skidmore</a> from Peoria, AZ, United States of America'},
            "LicenseShortName": {"value": "CC BY-SA 3.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/3.0"},
            "AttributionRequired": {"value": "true"},
        },
    }

    def test_the_credit_is_the_files_own_description_with_its_markup_gone(self):
        credit = portraits.credit_of(self.INFO)
        self.assertEqual(credit["by"], "Gage Skidmore from Peoria, AZ, United States of America")
        self.assertEqual(credit["licence"], "CC BY-SA 3.0")
        self.assertEqual(credit["licenceUrl"], "https://creativecommons.org/licenses/by-sa/3.0")
        self.assertEqual(credit["file"], self.INFO["descriptionurl"])
        self.assertTrue(credit["attribution"])
        self.assertFalse(credit["nonFree"])
        self.assertIsNone(portraits.credit_of({})["licence"])
        self.assertEqual(portraits.plain_text("A &amp; <b>B</b>\n C"), "A & B C")

    def test_only_uncredited_wikimedia_files_are_asked_about(self):
        cache = {"a": {"url": self.FILE}, "b": {"url": self.FILE.replace("7f", "8e"),
                                               "credit": {"licence": "CC0", "form": portraits.CREDIT_FORM}},
                 "c": {"url": "https://clerk.house.gov/images/members/S001156.jpg"},
                 "d": {"url": None}}
        with mock.patch.object(portraits, "file_info",
                               return_value={self.FILE: self.INFO}) as info:
            self.assertEqual(portraits.credit_all(cache, log=lambda *a: None), 1)
        self.assertEqual(info.call_args[0][0], [self.FILE])
        self.assertEqual(cache["a"]["credit"]["licence"], "CC BY-SA 3.0")
        self.assertNotIn("credit", cache["c"])

    def test_what_commons_hides_or_says_of_no_one_is_not_printed_as_an_author(self):
        """The first credits printed "Unknown author Unknown author" (a
        hidden duplicate span), an uploader's sentence about not knowing the
        photographer, a file name and a bare address as authors."""
        author = portraits.author_of
        self.assertIsNone(author('Unknown author<span style="display: none;">Unknown '
                                 'author</span>'))
        self.assertIsNone(author("<p>I do not know the name of the photographer, but do know "
                                 "that the photo was taken by a Federal \n</p>\nemployee."))
        self.assertIsNone(author("Unidentified. Likely a governmental picture, which would "
                                 "amount to a protected use."))
        self.assertIsNone(author("unidentified photographer"))
        self.assertIsNone(author('<a href="https://www.ilnd.uscourts.gov/x.pdf">'
                                 'https://www.ilnd.uscourts.gov/x.pdf</a>'))
        self.assertIsNone(author(None))
        self.assertEqual(author(
            '<ul><li><a href="//commons.wikimedia.org/wiki/File:Warner_Keenan_Webb.jpg">'
            'Warner_Keenan_Webb.jpg</a>: <a href="https://www.flickr.com/people/x">Mark Warner'
            '</a></li>\n<li>derivative work: <a href="//commons.wikimedia.org/wiki/User:A">'
            'Athenchen</a> (<a href="//commons.wikimedia.org/wiki/User_talk:A"><span '
            'class="signature-talk">talk</span></a>)</li></ul>'),
            "Mark Warner; derivative work: Athenchen")
        self.assertEqual(author("United States Department of Justice. Billyboy01 at English "
                                "Wikipedia . Later version(s) were uploaded by Jeremyb at "
                                "English Wikipedia ."), "United States Department of Justice")
        self.assertEqual(author("United States Department of Justice The original uploader "
                                "was Billyboy01 at English Wikipedia ."),
                         "United States Department of Justice")
        # An uploader who is the author keeps their name; an initial its stop.
        self.assertEqual(author("Billyboy01 at English Wikipedia"),
                         "Billyboy01 at English Wikipedia")
        self.assertEqual(author("U.S. Government -- Judiciary -- S.D.N.Y."),
                         "U.S. Government -- Judiciary -- S.D.N.Y.")
        self.assertEqual(author("en:United States District Court for the Southern District "
                                "of Ohio"),
                         "United States District Court for the Southern District of Ohio")
        # A link labelled "source" names no one (Sotomayor's official portrait).
        self.assertEqual(author('Collection of the Supreme Court of the United States, Steve '
                                'Petteway <a rel="nofollow" class="external text" '
                                'href="http://www.nydailynews.com/x.html">source</a>'),
                         "Collection of the Supreme Court of the United States, Steve Petteway")
        # A user's page is a person, whatever their name (the PR #133 review).
        self.assertEqual(author('<a href="//commons.wikimedia.org/wiki/User:Link" '
                                'title="User:Link">Link</a>'), "Link")
        self.assertEqual(author('<a href="/wiki/User:Here">here</a>'), "here")
        self.assertEqual(portraits.licence_name("PDM-owner"), "Public Domain Mark")
        self.assertEqual(portraits.licence_name("CC BY-SA 4.0"), "CC BY-SA 4.0")

    def test_a_licence_asking_for_an_author_the_file_does_not_name_says_so(self):
        info = {"descriptionurl": "https://commons.wikimedia.org/wiki/File:Judge_Moore.jpg",
                "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "AttributionRequired": {"value": "true"}}}
        credit = portraits.commons_credit(portraits.credit_of(info))
        self.assertIsNone(credit["by"])
        self.assertTrue(credit["authorUnrecorded"])
        self.assertEqual(credit["page"], info["descriptionurl"])
        public = dict(info, extmetadata={"LicenseShortName": {"value": "Public domain"},
                                         "AttributionRequired": {"value": "false"}})
        self.assertNotIn("authorUnrecorded",
                         portraits.commons_credit(portraits.credit_of(public)))

    def test_a_credit_read_by_an_earlier_form_is_read_again(self):
        cache = {"a": {"url": self.FILE, "credit": {"licence": "CC BY-SA 3.0",
                                                    "by": "Unknown author Unknown author"}}}
        with mock.patch.object(portraits, "file_info",
                               return_value={self.FILE: self.INFO}):
            self.assertEqual(portraits.credit_all(cache, log=lambda *a: None), 1)
        self.assertEqual(cache["a"]["credit"]["form"], portraits.CREDIT_FORM)
        self.assertEqual(cache["a"]["credit"]["by"],
                         "Gage Skidmore from Peoria, AZ, United States of America")

    def test_a_commons_portrait_whose_credit_is_unread_waits_rather_than_hold_the_build(self):
        """A 429 from Commons left a new portrait without its licence, and
        validate's error held the whole refresh, results included."""
        member = {"id": "F000001", "isCandidate": False, "name": "Thomas Feely", "state": "AZ",
                  "photos": ["placeholder"], "wikipedia": "Thomas Feely"}
        key = portraits.profile_key(member)
        record = {"url": self.FILE, "via": "wikipedia", "title": "Thomas Feely"}
        portraits.apply_cache([member], {key: record})
        self.assertEqual(member["photos"], ["placeholder"])
        self.assertNotIn("photoCredit", member)
        self.assertEqual(validate.check_photo_credits([member]), [])

    def test_a_profile_carries_its_portraits_credit_and_a_fair_use_file_is_not_shown(self):
        member = {"id": "F000001", "isCandidate": False, "name": "Thomas Feely", "state": "AZ",
                  "photos": ["placeholder"], "wikipedia": "Thomas Feely"}
        key = portraits.profile_key(member)
        record = {"url": self.FILE, "via": "wikipedia", "title": "Thomas Feely",
                  "credit": portraits.credit_of(self.INFO)}
        portraits.apply_cache([member], {key: record})
        self.assertEqual(member["photoCredit"], {
            "by": "Gage Skidmore from Peoria, AZ, United States of America",
            "licence": "CC BY-SA 3.0",
            "licenceUrl": "https://creativecommons.org/licenses/by-sa/3.0",
            "page": "https://commons.wikimedia.org/wiki/File:Thomas_Feely.jpg",
            "via": "Wikimedia Commons"})
        unfree = dict(member, photos=["placeholder"])
        unfree.pop("photoCredit")
        portraits.apply_cache([unfree], {key: dict(record, credit={"nonFree": True})})
        self.assertEqual(unfree["photos"], ["placeholder"])
        self.assertIsNone(unfree["photoSource"])

    def test_government_and_campaign_photographs_say_whose(self):
        house = {"id": "S001156", "name": "Linda Sanchez", "photoSource": "clerk.house.gov",
                 "photos": ["https://clerk.house.gov/images/members/S001156.jpg", "placeholder"]}
        nobody = {"id": "X", "name": "No One", "photos": ["placeholder"],
                  "photoCredit": {"by": "stale"}}
        campaign = {"id": "C", "name": "Jane Smith", "photoSource": "campaign-site",
                    "photos": ["https://janesmith.com/jane.jpg", "placeholder"],
                    "photoCredit": photos.campaign_credit("https://www.janesmith.com/")}
        self.assertEqual(photos.assign_credits([house, nobody, campaign]), 2)
        self.assertEqual(house["photoCredit"], {"by": "U.S. House of Representatives"})
        self.assertNotIn("photoCredit", nobody)
        self.assertEqual(campaign["photoCredit"]["by"], "the campaign's website (janesmith.com)")
        self.assertEqual(campaign["photoCredit"]["page"], "https://www.janesmith.com/")
        # Every first photograph a member's chain can start with is credited.
        for url in photos.member_photos("Linda Sanchez", "S001156")[:-1]:
            self.assertIsNotNone(photos.host_credit(url), url)

    def test_an_uncredited_photograph_or_an_unlicensed_commons_file_fails(self):
        shown = {"id": "A", "name": "A B", "photos": [self.FILE, "placeholder"],
                 "photoCredit": portraits.commons_credit(portraits.credit_of(self.INFO))}
        self.assertEqual(validate.check_photo_credits([shown]), [])
        unlicensed = dict(shown, photoCredit=portraits.commons_credit(None))
        bare = {"id": "C", "name": "C D", "photos": ["https://janesmith.com/x.jpg"]}
        silhouette = {"id": "E", "name": "E F", "photos": ["placeholder"]}
        issues = validate.check_photo_credits([unlicensed, bare, silhouette])
        self.assertEqual(sorted(i.code for i in issues),
                         ["photo-licence-missing", "photo-uncredited"])
        self.assertTrue(all(i.level == "error" for i in issues))

    def test_the_campaign_site_portrait_is_credited_to_the_site(self):
        profile = _challenger(campaignSite="https://janesmith.com")
        enrich.apply_cache([profile], TestApplyEnrichment().cache(
            site=TestApplyEnrichment.SAFE_SITE), as_of=TestApplyEnrichment.AS_OF)
        self.assertEqual(profile["photoCredit"], {"by": "the campaign's website (janesmith.com)",
                                                  "page": "https://janesmith.com"})


class TestPortraitWeights(unittest.TestCase):
    """TECH-13: a 1.3 MB campaign PNG was downloaded for a 165px card."""

    def test_the_caps(self):
        self.assertEqual(photos.too_heavy(None), "")          # unknown is not too big
        self.assertEqual(photos.too_heavy({"bytes": 120_000, "width": 600, "height": 750}), "")
        self.assertIn("KB", photos.too_heavy({"bytes": 1_330_007, "width": 876, "height": 1024}))
        self.assertIn("px", photos.too_heavy({"bytes": 90_000, "width": 1638, "height": 2048}))

    def test_a_heavy_picture_is_taken_lighter_and_said(self):
        heavy = "https://smith.com/wp-content/uploads/smith-big.png"
        photon = "https://i0.wp.com/smith.com/wp-content/uploads/smith-big.png?w=500&ssl=1"
        weights = {heavy: (True, {"bytes": 1_300_000, "width": 876, "height": 1024}),
                   photon: (True, {"bytes": 160_000, "width": 500, "height": 584})}
        record = {}
        with mock.patch.object(enrich, "portrait_check", side_effect=lambda u, h: weights[u]):
            enrich.take_portrait(record, [(heavy, True)])
        self.assertEqual(record["portrait"], photon)
        self.assertEqual(record["portraitWeight"]["bytes"], 160_000)
        self.assertEqual(record["portraitHeavy"],
                         [{"url": heavy, "why": "1300 KB, over 300 KB", "kept": False}])

    def test_a_nominees_only_likeness_is_not_withheld_for_its_weight(self):
        """Eleven November nominees showed the silhouette once their only
        portrait was refused as heavy; the reviewer's diff found them."""
        heavy = "https://cdn.example.com/a/smith.png?v=3"     # no resizer, a query string
        weights = {heavy: (True, {"bytes": 306_000, "width": 800, "height": 913})}
        record = {}
        with mock.patch.object(enrich, "portrait_check", side_effect=lambda u, h: weights[u]):
            enrich.take_portrait(record, [(heavy, True)])
        self.assertEqual(record["portrait"], heavy)
        self.assertTrue(record["portraitHeavy"][0]["kept"])
        site = dict(TestApplyEnrichment.SAFE_SITE, portrait=heavy,
                    portraitWeight=weights[heavy][1])
        profile = _challenger(campaignSite="https://janesmith.com")
        counts = enrich.apply_cache([profile], TestApplyEnrichment().cache(site=site),
                                    as_of=TestApplyEnrichment.AS_OF)
        self.assertEqual(profile["photos"][0], heavy)
        self.assertEqual(counts["portrait_heavy"], 1)

    def test_a_resizer_answering_with_another_picture_is_not_taken(self):
        heavy = "https://smith.com/smith.jpg"
        weights = {heavy: (True, {"bytes": 900_000, "width": 1600, "height": 2000}),
                   # A square "image not found" card, not the portrait scaled.
                   photos.photon_form(heavy, 500): (True, {"bytes": 9_000, "width": 500,
                                                           "height": 500}),
                   photos.photon_form(heavy, 330): (False, None)}
        record = {}
        with mock.patch.object(enrich, "portrait_check", side_effect=lambda u, h: weights[u]):
            enrich.take_portrait(record, [(heavy, True)])
        self.assertEqual(record["portrait"], heavy)
        self.assertTrue(record["portraitHeavy"][0]["kept"])

    def test_smaller_forms_come_from_the_same_file(self):
        big = ("https://images.squarespace-cdn.com/content/v1/abc/def/Jane+Smith+Headshot.png"
               "?format=1500w")
        self.assertEqual(photos.smaller_forms(big), [
            "https://images.squarespace-cdn.com/content/v1/abc/def/Jane+Smith+Headshot.png"
            "?format=500w",
            # Squarespace serves 300w, not 330w.
            "https://images.squarespace-cdn.com/content/v1/abc/def/Jane+Smith+Headshot.png"
            "?format=300w"])
        self.assertIn("w=500", photos.smaller_form("https://run.imgix.net/a/b.jpg?w=2048&q=75"))
        self.assertEqual(photos.smaller_form("https://smith.com/wp-content/smith-876x1024.png"),
                         "https://i0.wp.com/smith.com/wp-content/smith-876x1024.png?w=500&ssl=1")
        # Photon drops a query string, which could name another file; and it
        # is never asked for a page, plain http or another resizer's URL.
        for url in ("https://smith.com/smith.png?1784490997", "https://smith.com/about",
                    "http://smith.com/smith.jpg",
                    "https://i0.wp.com/smith.com/smith.jpg?w=500"):
            self.assertIsNone(photos.photon_form(url), url)
        self.assertTrue(photos.same_shape({"width": 800, "height": 913},
                                          {"width": 499, "height": 570}))
        self.assertFalse(photos.same_shape({"width": 800, "height": 913},
                                           {"width": 500, "height": 500}))
        self.assertFalse(photos.same_shape({"width": 400, "height": 500},
                                           {"width": 400, "height": 500}))

    def test_a_portrait_refused_for_its_weight_is_weighed_again_and_never_read_from_the_site(self):
        heavy = "https://smith.com/wp-content/uploads/smith.png"
        photon = photos.photon_form(heavy, 500)
        cache = {"people": {"FEC_H6XX01001": {"name": "Jane Smith", "site": {
            "url": "https://smith.com", "safe": True,
            "portraitHeavy": [{"url": heavy, "why": "1330 KB, over 300 KB"}]}}}}
        weights = {heavy: (True, {"bytes": 1_330_000, "width": 876, "height": 1024}),
                   photon: (True, {"bytes": 120_000, "width": 500, "height": 584})}
        with mock.patch.object(enrich, "portrait_check", side_effect=lambda u, h: weights[u]), \
                mock.patch.object(enrich, "fetch", side_effect=AssertionError("site read")), \
                mock.patch.object(enrich.time, "sleep"):
            self.assertEqual(enrich.measure_portraits(cache, log=lambda *a: None), 1)
        record = cache["people"]["FEC_H6XX01001"]["site"]
        self.assertEqual(record["portrait"], photon)
        self.assertFalse(record["portraitHeavy"][0]["kept"])

    def test_a_gzipped_image_is_read_through_its_encoding(self):
        """Missouri's attorney general's headshot came gzipped and read as
        'not an image'."""
        import gzip

        jpeg = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                b"\xff\xc0\x00\x11\x08" + (500).to_bytes(2, "big") + (400).to_bytes(2, "big")
                + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\x00" * 64)
        body = gzip.compress(jpeg)

        class Response:
            status = 200
            headers = {"Content-Type": "image/jpeg", "Content-Encoding": "gzip",
                       "Content-Length": str(len(body))}

            def read(self, n):
                return body[:n]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(enrich.urllib.request, "urlopen", return_value=Response()):
            shape, weight = enrich.portrait_check("https://ago.mo.gov/hanaway.jpg", True)
        self.assertTrue(shape)
        self.assertEqual(weight, {"bytes": len(body), "width": 400, "height": 500})

    def test_a_portrait_is_measured_from_its_first_bytes_and_the_size_the_server_gives(self):
        png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (335).to_bytes(4, "big")
               + (410).to_bytes(4, "big") + b"\x00" * 64)

        class Response:
            status = 206
            headers = {"Content-Type": "image/png", "Content-Range": "bytes 0-65535/103089"}

            def read(self, n):
                return png

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(portraits.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(portraits.measure("https://clerk.house.gov/images/members/G000607.jpg"),
                             {"bytes": 103089, "width": 335, "height": 410})
        with mock.patch.object(portraits.urllib.request, "urlopen", side_effect=OSError):
            self.assertIsNone(portraits.measure("https://clerk.house.gov/x.jpg"))

    def test_wikimedia_is_asked_only_for_standard_widths(self):
        standard = {20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840}
        self.assertIn(portraits._THUMB_SIZE, standard)
        self.assertGreaterEqual(portraits._api_gap, 1.0)   # one request a second


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
        results.apply_cache(cls.profiles, results.load_cache(ROOT))
        portraits.apply_cache(cls.profiles, portraits.load_cache(ROOT))
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

    def test_no_portrait_is_reached_by_a_name(self):
        """Rule 24, for every profile: the NJ and OR Republican Senate
        nominees showed a rugby player and an Olympic kayaker from
        Special:FilePath/<Name>.jpg, and Rep. Al Green's chain ended in the
        singer's photograph."""
        by_id = {p["id"]: p for p in self.profiles}
        self.assertEqual(validate.check_guessed_photos(self.profiles), [])
        self.assertEqual(by_id["CAND_40"]["photos"], ["placeholder"])
        self.assertFalse([u for u in by_id["G000553"]["photos"] if "wikipedia.org/wiki/" in u])
        # Oregon's nominee has the photograph of the article his ballot page
        # links ("David Brock Smith"), checked to be about him (rule 33).
        self.assertIn("David_Brock_Smith", by_id["CAND_43"]["photos"][0])
        self.assertEqual(by_id["CAND_43"]["photoSource"], "wikipedia")
        # Kansas's Adam Hamilton is the pastor his ballot page links, not the
        # 1930s "Adam Hamilton (politician)" a title guess found.
        self.assertNotIn("1930s", by_id["CAND_18"]["photos"][0])
        self.assertNotIn("wikipedia-search", {p.get("photoSource") for p in self.profiles})

    def test_a_guessed_photo_fails_the_build(self):
        bad = {"id": "CAND_40", "name": "Justin Murphy",
               "photos": ["https://en.wikipedia.org/wiki/Special:FilePath/Justin_Murphy.jpg",
                          "placeholder"]}
        issues = validate.check_guessed_photos([bad])
        self.assertEqual([i.code for i in issues], ["photo-guessed"])
        self.assertEqual(issues[0].level, "error")

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


class TestPeopleDataAudit(unittest.TestCase):
    """The 2026-10-17 reader audit's findings about people's links and money."""

    def running(self, **extra):
        return dict({"id": "FEC_H6NC02213", "isCandidate": True, "source": "fec-field",
                     "name": "Brian McGinnis", "state": "NC", "chamber": "House (Candidate)",
                     "raceStatus": "nominee", "photos": ["placeholder"]}, **extra)

    # --- Wikipedia links (LINKS-10, PROFILES-13)
    def test_a_ballot_link_must_lead_to_the_persons_own_article(self):
        about = enrich.link_is_about
        self.assertFalse(about({"to": "Protests against the 2026 Iran war",
                                "fragment": "Washington D.C."}, "Brian McGinnis"))
        self.assertFalse(about({"to": "2016 Green Party presidential primaries"},
                               "Elijah Manley"))
        self.assertFalse(about({"to": "Cascade Party of Washington"}, "Antony Barran"))
        self.assertFalse(about({"to": "2026 United States House of Representatives elections "
                                      "in Georgia", "fragment": "District 11"}, "John Cowan"))
        self.assertFalse(about({"missing": True}, "Jane Doe"))
        self.assertTrue(about({"to": "David Brock Smith"}, "David Smith"))
        self.assertTrue(about({"to": "Adam Hamilton (pastor)"}, "Adam Hamilton"))
        # A living person's article under another name is theirs only by an
        # evidenced alias: a redirect to a living spouse or namesake is one too.
        self.assertFalse(about({"to": "Uncle Luke", "living": True}, "Luther Campbell"))
        self.assertFalse(about({"to": "Jill Biden", "living": True}, "Joe Smith"))
        self.assertTrue(about({"to": "Uncle Luke", "living": True}, "Luther Campbell",
                              alias="Uncle Luke"))
        self.assertFalse(about({"to": "Uncle Luke", "fragment": "Career"}, "Luther Campbell",
                               alias="Uncle Luke"))
        self.assertFalse(about({"to": "2016 Green Party presidential primaries",
                                "living": True}, "Elijah Manley"))

    def test_link_targets_follow_redirects_and_keep_the_section(self):
        payload = {"query": {
            "normalized": [{"from": "brian McGinnis", "to": "Brian McGinnis"}],
            "redirects": [{"from": "Brian McGinnis", "to": "Protests against the 2026 Iran war",
                           "tofragment": "Washington D.C."}],
            "pages": [{"title": "Protests against the 2026 Iran war"},
                      {"title": "Nobody Here", "missing": True},
                      {"title": "Roy Cooper",
                       "categories": [{"ns": 14, "title": "Category:Living people"}]}]}}
        with mock.patch.object(portraits, "_api", return_value=payload):
            found = enrich.link_targets(["brian McGinnis", "Nobody Here", "Roy Cooper"],
                                        log=lambda *a: None)
        self.assertEqual(found["brian McGinnis"], {"to": "Protests against the 2026 Iran war",
                                                   "fragment": "Washington D.C.",
                                                   "living": False})
        self.assertEqual(found["Nobody Here"], {"missing": True})
        self.assertEqual(found["Roy Cooper"], {"to": "Roy Cooper", "fragment": None,
                                               "living": True})
        # A failed batch concludes nothing (rule 8).
        with mock.patch.object(portraits, "_api", side_effect=OSError("429")):
            self.assertEqual(enrich.link_targets(["Roy Cooper"], log=lambda *a: None), {})

    def test_a_link_to_another_subject_is_withheld_from_anyone(self):
        cache = {"people": {}, "links": {
            "Brian McGinnis": {"to": "Protests against the 2026 Iran war",
                               "fragment": "Washington D.C."},
            "Roy Cooper": {"to": "Roy Cooper", "fragment": None}}}
        withdrawn = self.running(wikipedia="Brian McGinnis", wikipediaVia="election-page",
                                 raceStatus="withdrawn")
        fine = self.running(id="CAND_1", name="Roy Cooper", wikipedia="Roy Cooper",
                            wikipediaVia="election-page")
        unchecked = self.running(id="X2", name="Jo Doe", wikipedia="Jo Doe",
                                 wikipediaVia="election-page")
        counts = enrich.apply_cache([withdrawn, fine, unchecked], cache)
        self.assertNotIn("wikipedia", withdrawn)
        self.assertEqual(withdrawn["wikipediaWithheld"]["landsOn"],
                         "Protests against the 2026 Iran war#Washington D.C.")
        self.assertEqual(fine["wikipedia"], "Roy Cooper")
        self.assertEqual(unchecked["wikipedia"], "Jo Doe")
        self.assertEqual(counts["wikipedia_withheld"], 1)
        issues = validate.check_wikipedia_withheld([withdrawn, fine])
        self.assertEqual([i.code for i in issues], ["wikipedia-not-about"])

    def test_the_alias_is_one_answer_for_link_portrait_infobox_and_history(self):
        from kyc import overrides
        profile = {"id": "FEC_H4FL20098", "name": "Luther Campbell"}
        self.assertEqual(overrides.article_alias("FEC_H4FL20098"), "Uncle Luke")
        self.assertTrue(portraits.article_is_theirs("Uncle Luke", profile))
        self.assertFalse(portraits.article_is_theirs("Uncle Luke",
                                                     {"id": "X", "name": "Luther Campbell"}))
        self.assertTrue(portraits.article_is_theirs("Luther Campbell (politician)",
                                                    {"id": "X", "name": "Luther Campbell"}))
        kept = self.running(id="FEC_H4FL20098", name="Luther Campbell",
                            wikipedia="Luther Campbell", wikipediaVia="election-page")
        enrich.withhold_links([kept], {"links": {"Luther Campbell": {
            "to": "Uncle Luke", "fragment": None, "living": True}}})
        self.assertEqual(kept["wikipedia"], "Luther Campbell")

    def test_a_withheld_link_delivers_no_portrait(self):
        # A redirect to a section of an article whose title carries the
        # surname passes title_is_about; the link check withholds it, and it
        # must do so before the portrait is applied.
        profile = self.running(id="FEC_H6XX00001", name="Jane Doe", wikipedia="Jane Doe",
                               wikipediaVia="election-page", photos=["placeholder"])
        record = {"url": "https://upload.wikimedia.org/doe-family.jpg", "via": "wikipedia",
                  "title": "Doe family", "linked": "Jane Doe", "name": "Jane Doe"}
        cache = {portraits.profile_key(profile): record}
        self.assertTrue(portraits.route_ok(profile, record))  # the hole, before withholding
        withheld = enrich.withhold_links([profile], {"links": {"Jane Doe": {
            "to": "Doe family", "fragment": "Jane Doe", "living": False}}})
        self.assertEqual(withheld, 1)
        portraits.apply_cache([profile], cache)
        self.assertNotIn(record["url"], profile["photos"])
        # And every command that applies portraits withholds first.
        import inspect
        from kyc import cli
        for command in (cli._build, cli._enrich, cli._verify, cli._portraits):
            source = inspect.getsource(command)
            first = min(i for i in (source.find("portraits.apply_cache"),
                                    source.find("portraits.resolve_all")) if i >= 0)
            self.assertLess(source.find("enrich.withhold_links"), first, command.__name__)
            self.assertGreaterEqual(source.find("enrich.withhold_links"), 0, command.__name__)

    # --- campaign sites (LINKS-11)
    def test_other_form_adds_or_drops_www(self):
        self.assertEqual(enrich.other_form("https://www.martyjackley.com/"),
                         "https://martyjackley.com/")
        self.assertEqual(enrich.other_form("https://landsmanforcongress.com"),
                         "https://www.landsmanforcongress.com")
        self.assertIsNone(enrich.other_form("not a url"))

    def test_an_unreachable_site_is_tried_in_its_other_form(self):
        profile = self.running(name="Marty Jackley")
        good = {"url": "https://martyjackley.com/", "final": "https://martyjackley.com/",
                "status": 200, "safe": True, "reason": "ok"}
        dead = {"url": "https://www.martyjackley.com/", "final": "https://www.martyjackley.com/",
                "status": None, "safe": None, "reason": "unreachable"}
        with mock.patch.object(enrich, "_read_one", side_effect=[dead, good]), \
                mock.patch.object(enrich.time, "sleep"):
            record = enrich.read_site(profile, "https://www.martyjackley.com/")
        self.assertEqual(record["url"], "https://www.martyjackley.com/")
        self.assertEqual(record["working"], "https://martyjackley.com/")
        # The other form must itself name the candidate, or nothing changes.
        unnamed = dict(good, safe=False, reason=enrich.UNNAMED)
        with mock.patch.object(enrich, "_read_one", side_effect=[dead, unnamed]), \
                mock.patch.object(enrich.time, "sleep"):
            record = enrich.read_site(profile, "https://www.martyjackley.com/")
        self.assertNotIn("working", record)
        # A hijacked answer is a verdict, never retried.
        hijacked = dict(dead, status=200, safe=False, reason=enrich.HIJACKED)
        with mock.patch.object(enrich, "_read_one", side_effect=[hijacked]) as read:
            enrich.read_site(profile, "https://www.martyjackley.com/")
        self.assertEqual(read.call_count, 1)

    def test_the_working_form_is_linked(self):
        profile = self.running(id="J000301", isCandidate=False, source=None,
                               name="Dusty Johnson", campaignSite="https://www.example-dj.com/")
        site = {"url": "https://www.example-dj.com/", "working": "https://example-dj.com/",
                "final": "https://example-dj.com/", "status": 200, "safe": True}
        counts = enrich.apply_cache([profile], {"people": {"J000301": {"site": site}}})
        self.assertEqual(profile["campaignSite"], "https://example-dj.com/")
        self.assertEqual(counts["site_form"], 1)

    def test_the_hijacked_hosts_of_the_audit_are_blocked(self):
        from kyc import overrides
        for url in ("https://www.trevordforme.com", "https://www.rickwallenforcongress.com/",
                    "http://zabelforcongress.com"):
            self.assertTrue(overrides.blocked_campaign_host(url), url)

    # --- outbound addresses (LINKS-V1, PROFILES-15)
    def test_an_address_a_browser_cannot_open_fails_the_build(self):
        bad = {"id": "F000484", "name": "Randy Fine",
               "contactForm": "hhttps://fine.house.gov/address_authentication?form=/contact/email-me",
               "photos": ["https://clerk.house.gov/x.jpg", "placeholder"]}
        issues = validate.check_outbound_urls([bad])
        self.assertEqual([i.code for i in issues], ["url-malformed"])
        self.assertEqual(issues[0].level, "error")
        good = dict(bad, contactForm="https://fine.house.gov/contact/")
        self.assertEqual(validate.check_outbound_urls([good]), [])
        for url in ("www.example.com", "https://localhost/x", "javascript:alert(1)",
                    "https://exa mple.com"):
            self.assertTrue(validate.bad_url(url), url)

    def test_fines_contact_form_is_corrected_only_while_the_typo_stands(self):
        from kyc import profiles as profiles_mod
        typo = "hhttps://fine.house.gov/address_authentication?form=/contact/email-me"
        out = profiles_mod._contact({"bioguide": "F000484", "contactForm": typo})
        self.assertEqual(out["contactForm"], "https://fine.house.gov/contact/")
        later = "https://fine.house.gov/contact/form"
        out = profiles_mod._contact({"bioguide": "F000484", "contactForm": later})
        self.assertEqual(out["contactForm"], later)

    # --- social accounts (LINKS-02, PROFILES-23, LINKS-03)
    def test_youtube_values_are_linked_by_their_shape(self):
        from kyc.profiles import social_handles
        channel = social_handles({"youtube": "UCjy0W7sksMz37IYY27tAZNQ"}, "A000379")
        self.assertEqual(channel, {"youtube_id": "UCjy0W7sksMz37IYY27tAZNQ"})
        self.assertEqual(social_handles({"youtube": "@RepAlford"}, "A000379"),
                         {"youtube": "@RepAlford"})
        # Legacy names as checked: a handle now, still /user/, or gone.
        self.assertEqual(social_handles({"youtube": "repcarbajal"}, "C001112"),
                         {"youtube": "@repcarbajal"})
        self.assertEqual(social_handles({"youtube": "adamschiff"}, "S001150"),
                         {"youtube": "adamschiff"})
        self.assertEqual(social_handles({"youtube": "RepJackBergman"}, "B001301"), {})
        # An @handle YouTube answers 404 for: the one the member's office links.
        self.assertEqual(social_handles({"youtube": "@RepJeffHurd03"}, "H001100"),
                         {"youtube": "@RepJeffHurd"})
        self.assertEqual(social_handles({"youtube": "@RepJeffHurd03"}, "X000000"),
                         {"youtube": "@RepJeffHurd03"})

    def test_an_x_account_is_linked_by_its_id_and_a_dead_handle_dropped(self):
        from kyc.profiles import social_handles
        johnson = social_handles({"twitter": "RepMikeJohnson",
                                  "twitter_id": "827279765287559171"}, "J000299")
        self.assertEqual(johnson["twitter_id"], "827279765287559171")
        self.assertEqual(social_handles({"twitter": "JMoylanforGuam"}, "M001219"), {})
        # With an id the account is followed, not dropped.
        self.assertIn("twitter", social_handles({"twitter": "JMoylanforGuam",
                                                 "twitter_id": "1"}, "M001219"))

    def test_the_link_corrections_match_the_snapshot(self):
        from kyc import legislators
        snapshot = legislators.load_snapshot(ROOT)
        self.assertEqual(validate.check_member_link_overrides(snapshot), [])
        moved = {"legislators": [{"bioguide": "M001219", "social": {"twitter": "NewHandle"}}]}
        codes = [i.code for i in validate.check_member_link_overrides(moved)]
        self.assertIn("stale-link-override", codes)
        fixed = {"legislators": [{"bioguide": "H001100", "social": {"youtube": "@RepJeffHurd"}}]}
        issues = validate.check_member_link_overrides(fixed)
        self.assertTrue(any("YOUTUBE_HANDLE_CORRECTIONS H001100" in line
                            for i in issues for line in i.detail))

    # --- money (PROFILES-11)
    def test_a_negative_amount_puts_the_sign_first(self):
        self.assertEqual(normalize.fmt_curr(-582.63), "-$582.63")
        self.assertEqual(fec._money(-582.63), "-$582.63")
        self.assertEqual(normalize.fmt_curr(0), "$0.00")

    def test_coverage_after_the_build_is_listed(self):
        import datetime
        people = [{"id": "FEC_H4IA01127", "name": "A", "financeAsOf": "2026-12-31"},
                  {"id": "B", "name": "B", "financeAsOf": "2026-09-30"}]
        issues = validate.check_future_coverage(people, today=datetime.date(2026, 10, 17))
        self.assertEqual([i.code for i in issues], ["finance-future-coverage"])
        self.assertEqual(len(issues[0].detail), 1)

    # --- each challenger's own totals (PROFILES-10, TRUST-13, PERSONA-13)
    def test_a_challengers_split_comes_from_their_own_filing(self):
        profile = {"id": "FEC_H6IN09242", "isCandidate": True, "source": "fec-field",
                   "fecCandidateId": "H6IN09242", "name": "Bradley Meyer", "state": "IN",
                   "chamber": "House (Candidate)", "quality": {}}
        figures = {"election_year": 2026, "receipts": 200000.0,
                   "individual_contributions": 182793.12, "party_contributions": 930.0,
                   "candidate_loans": 11339.03, "self_funding": 0, "pac_contributions": 0,
                   "coverage_end": "2026-09-30"}
        saved = {}
        with mock.patch.object(fec, "totals", return_value=figures) as asked, \
                mock.patch.object(fec, "load_cache", return_value={}), \
                mock.patch.object(fec, "save_cache", side_effect=lambda c, r: saved.update(c)):
            fec.resolve_field([profile], log=lambda *a: None)
        asked.assert_called_once_with("H6IN09242")
        self.assertIn("fec:H6IN09242", saved)
        fec.apply_cache([profile], saved)
        self.assertEqual(profile["funding_sources"],
                         "Individual 91%, Self-funded (incl. loans) 6%, Party <1%")
        self.assertTrue(saved["fec:H6IN09242"]["read"])

    def test_a_refresh_rereads_only_old_challenger_totals_a_batch_at_a_time(self):
        # The daily refresh must not re-read ~590 challengers every day.
        import datetime
        today = datetime.date(2026, 10, 17)
        people = [{"id": f"FEC_H6XX{n:05d}", "source": "fec-field",
                   "fecCandidateId": f"H6XX{n:05d}", "name": f"P{n}", "state": "XX",
                   "chamber": "House (Candidate)"} for n in range(fec.FIELD_PER_RUN + 40)]
        cache = {}
        for n, person in enumerate(people):
            age = 2 if n < 20 else 10 + n  # the first twenty were read this week
            cache[fec.profile_key(person)] = {
                "candidate_id": person["fecCandidateId"], "candidate_loans": 0,
                "receipts": 1.0, "read": (today - datetime.timedelta(days=age)).isoformat()}
        new = {"id": "FEC_H6XX99999", "source": "fec-field", "fecCandidateId": "H6XX99999",
               "name": "New", "state": "XX", "chamber": "House (Candidate)"}
        asked = []
        with mock.patch.object(fec, "totals",
                               side_effect=lambda cid: asked.append(cid) or None), \
                mock.patch.object(fec, "load_cache", return_value=cache), \
                mock.patch.object(fec, "save_cache"):
            fec.resolve_field(people + [new], log=lambda *a: None, today=today)
            self.assertEqual(asked, ["H6XX99999"])  # without --refresh, only the unread
            asked.clear()
            fec.resolve_field(people + [new], refresh=True, log=lambda *a: None, today=today)
        self.assertEqual(asked[0], "H6XX99999")
        self.assertEqual(len(asked), 1 + fec.FIELD_PER_RUN)
        # Oldest first; nobody read this week.
        self.assertEqual(asked[1], people[-1]["fecCandidateId"])
        self.assertFalse({p["fecCandidateId"] for p in people[:20]} & set(asked))

    def test_a_stopped_finance_run_does_not_fail_the_refresh(self):
        # refresh.yml runs the field and the results after this step.
        from types import SimpleNamespace
        from kyc import cli
        args = SimpleNamespace(root=ROOT, limit=None, refresh=True, field_only=False)
        with mock.patch.object(cli, "_load", return_value={}), \
                mock.patch.object(cli.legislators, "load_snapshot", return_value={}), \
                mock.patch.object(cli, "build_profiles", return_value=([], {})), \
                mock.patch.object(cli.candidates, "load_cache", return_value={}), \
                mock.patch.object(fec, "resolve_all", return_value=({}, {"stopped": 1})):
            self.assertEqual(cli._finance(args), 0)
        with mock.patch.object(cli, "_load", return_value={}), \
                mock.patch.object(cli.legislators, "load_snapshot", return_value={}), \
                mock.patch.object(cli, "build_profiles", return_value=([], {})), \
                mock.patch.object(cli.candidates, "load_cache", return_value={}), \
                mock.patch.object(fec, "load_cache", return_value={}), \
                mock.patch.object(cli.results_mod, "load_cache", return_value={}), \
                mock.patch.object(fec, "resolve_field", return_value=({}, {"stopped": 1})):
            self.assertEqual(cli._finance(SimpleNamespace(**{**vars(args),
                                                             "field_only": True})), 0)
