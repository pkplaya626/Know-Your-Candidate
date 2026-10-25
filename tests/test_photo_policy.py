"""The owner's photograph decisions of 2026-10-25: nobody else in the frame
on any route (rule 38), one test of what a person refused (rule 12), and a
Commons photograph's year in its credit (rule 87)."""

import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import (judge_links, legislature, officers, overrides, photos, portraits,  # noqa: E402
                 stategov, statewide_photos, validate)

ROOT = os.path.join(os.path.dirname(__file__), "..")
REFUSED = "https://example.org/crowd.jpg"
TABLE = {REFUSED: ("2026-10-25", "Pat Doe: people behind her")}


class TestOneRefusalTest(unittest.TestCase):
    """Every page-time reader asks photos.not_a_portrait, which records what
    it refused for validate's staleness check."""

    def test_it_names_the_first_refused_and_records_it_once(self):
        passed = []
        self.assertEqual(photos.not_a_portrait("https://ok.org/a.jpg", REFUSED, table=TABLE,
                                               passed_over=passed), REFUSED)
        photos.not_a_portrait(REFUSED, table=TABLE, passed_over=passed)
        self.assertEqual(passed, [REFUSED])
        self.assertEqual(photos.not_a_portrait("https://ok.org/a.jpg", None, table=TABLE), "")

    def test_no_reader_keeps_its_own_membership_test(self):
        # Rule 12: one implementation. The readers name the list only in
        # words, never as "in overrides.NOT_A_PORTRAIT".
        import re
        for name in ("enrich", "court_photos", "officers", "statewide_photos", "judge_links"):
            with open(os.path.join(ROOT, "kyc", name + ".py"), encoding="utf-8") as handle:
                code = handle.read()
            self.assertIsNone(re.search(r"\bin overrides\.NOT_A_PORTRAIT\b(?!;)", code), name)
            self.assertNotIn("import NOT_A_PORTRAIT", code, name)

    def test_an_attorney_generals_office_photograph_refused_is_recorded(self):
        page = ("https://ag.example.gov/about", '<img src="/img/doe-headshot.jpg" '
                'alt="Attorney General Pat Doe headshot">')
        url = "https://ag.example.gov/img/doe-headshot.jpg"
        passed = []
        found, _why = officers.ag_photo("Pat Doe", "XX", [page], check=lambda u, h: (True, {
            "bytes": 1000, "width": 200, "height": 250}), refused={url: ("d", "w")},
            passed_over=passed)
        self.assertIsNone(found)
        self.assertEqual(passed, [url])

    def test_a_statewide_guide_photograph_refused_is_recorded(self):
        passed = []
        with unittest.mock.patch.object(statewide_photos, "parse_arizona",
                                        return_value=[("governor", "PAT DOE", None, REFUSED, "")]):
            records, problems, _ = statewide_photos.read_guides(
                {"AZ": {"governor": [{"name": "PAT DOE"}]}}, get=lambda u: "", pause=0,
                refused=TABLE, passed_over=passed)
        self.assertEqual(records, {})
        self.assertEqual(passed, [REFUSED])
        self.assertIn(REFUSED, statewide_photos.doubted({"notPortraits": passed}))


class TestEveryRouteAsksAtBuildTime(unittest.TestCase):
    """A file refused since it was read is not shown, on any route."""

    def test_a_profiles_article_portrait(self):
        upload = "https://upload.wikimedia.org/wikipedia/commons/d/de/Pat_Doe.jpg"
        record = {"via": "wikipedia", "title": "Pat Doe", "linked": "Pat Doe",
                  "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Pat_Doe.jpg/"
                         "330px-Pat_Doe.jpg",
                  "credit": {"licence": "CC BY 4.0", "by": "X", "year": 2019,
                             "file": "https://commons.wikimedia.org/wiki/File:Pat_Doe.jpg"}}
        profile = {"id": "B000001", "isCandidate": False, "name": "Pat Doe", "state": "XX",
                   "wikipedia": "Pat Doe", "photos": ["placeholder"]}
        key = portraits.profile_key(profile)
        self.assertEqual(portraits.addresses(record)[-1], upload)
        self.assertEqual(portraits.apply_cache([dict(profile)], {key: record}), 1)
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {upload: ("d", "w")}):
            shown = dict(profile)
            self.assertEqual(portraits.apply_cache([shown], {key: record}), 0)
            self.assertEqual(shown["photos"], ["placeholder"])

    def test_an_officers_roster_card_and_an_attorney_generals_photograph(self):
        card = "https://www.nass.org/sites/default/files/MA-Galvin-2023.jpg"
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {card: ("d", "w")}):
            self.assertNotIn("photo", officers._credited({"name": "William Galvin",
                                                          "photo": card}, officers.NASS_BY))
            cache = {"lt": {}, "sos": {}, "ag": {"XX": {"name": "Pat Doe", "photo": card,
                                                        "photoPage": "https://ag.example.gov/"}}}
            self.assertNotIn("photo", officers.for_state("XX", cache, [])["ag"])
        self.assertEqual(officers._credited({"name": "W", "photo": card}, "N")["photoBy"], "N")

    def test_a_curated_association_card(self):
        entry = {"ag": {"name": "Pat Doe"}}
        curated = {("XX", "ag"): {"name": "Pat Doe", "photo": REFUSED, "by": "NAAG",
                                  "page": "https://www.naag.org/"}}
        with unittest.mock.patch.dict(overrides.OFFICER_PHOTOS, curated), \
                unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            problems = stategov.officer_photos("XX", entry)
        self.assertNotIn("photo", entry["ag"])
        self.assertTrue(any("NOT_A_PORTRAIT" in p for p in problems))

    def test_a_legislators_card_falls_to_the_legislatures_own_or_says_why(self):
        # Gregg Haddad's caucus file shows two colleagues at the next desks.
        member = {"id": "ocd-person/haddad", "name": "Gregg Haddad", "chamber": "lower",
                  "district": "54", "party": "Democratic", "partyKey": "D",
                  "image": "http://www2.housedems.ct.gov/Haddad/images/Haddad_19.jpg"}
        self.assertIn("https://www2.housedems.ct.gov/Haddad/images/Haddad_19.jpg",
                      overrides.NOT_A_PORTRAIT)
        self.assertEqual(legislature.photo_kind(member, {"people": {}}), "notAPortrait")
        self.assertNotIn("image", legislature._person(member, "CT", 2026, pages={member["id"]: None},
                                                      photos={"people": {}}))

    def test_a_judges_file_is_withheld_and_recorded(self):
        cache = judge_links.load_cache(ROOT)
        refused = set(cache.get("notPortraits") or ())
        self.assertTrue(refused)
        self.assertTrue(refused <= set(overrides.NOT_A_PORTRAIT))
        shown = {judge_links.source_url(e["portrait"]["source"])
                 for e in cache["judges"].values() if e.get("portrait")}
        self.assertFalse(shown & set(overrides.NOT_A_PORTRAIT))


class TestTheStalenessCheckSeesEveryRoute(unittest.TestCase):

    def test_no_entry_reads_as_stale_against_the_committed_caches(self):
        from kyc import cli, enrich
        issues = validate.check_portrait_overrides(enrich.load_cache(ROOT),
                                                   cli._photo_routes(ROOT))
        self.assertEqual([i for i in issues if i.code == "stale-portrait-override"], [])


class TestACommonsPhotographsYear(unittest.TestCase):
    """Tad Jude's (MN) black-and-white legislature portrait is from 1981
    and read as current: every Commons credit says the year its file's own
    page gives, and none where it gives no single one."""

    def test_the_credit_carries_the_files_own_year_only(self):
        self.assertEqual(portraits.commons_credit({"licence": "CC0", "year": 1981})["year"], 1981)
        self.assertNotIn("year", portraits.commons_credit({"licence": "CC0", "year": None}))
        self.assertNotIn("year", portraits.commons_credit({"licence": "CC0"}))

    def test_a_statewide_credit_read_before_years_is_dated_once(self):
        upload = "https://upload.wikimedia.org/wikipedia/commons/1/1d/Portrait_of_Tad_Jude.jpg"
        rec = {"route": "wikipedia", "photo": upload,
               "credit": {"licence": "Public domain", "via": "Wikimedia Commons",
                          "page": "https://commons.wikimedia.org/wiki/File:Portrait_of_Tad_Jude.jpg"}}
        cache = {"photos": {"MN|sos|TAD JUDE": rec}}
        asked = []

        def info_of(urls):
            asked.extend(urls)
            return {u: {"width": 400, "height": 500, "extmetadata": {
                "DateTimeOriginal": {"value": "1981"},
                "LicenseShortName": {"value": "Public domain"}}} for u in urls}
        self.assertEqual(statewide_photos.date_credits(cache, info_of, log=None), 1)
        self.assertEqual(rec["credit"]["year"], 1981)
        self.assertEqual(statewide_photos.date_credits(cache, info_of, log=None), 0)
        self.assertEqual(len(asked), 1)
        # A page that gives no single year is said once and never guessed.
        undated = statewide_photos.dated_credit({"licence": "CC0"}, {"year": None})
        self.assertEqual(undated, {"licence": "CC0", "yearUnstated": True})

    def test_the_committed_credits_are_dated(self):
        cache = statewide_photos.load_cache(ROOT)
        for key, rec in cache["photos"].items():
            if rec.get("route") == "wikipedia":
                self.assertTrue({"year", "yearUnstated"} & set(rec["credit"]), key)
        jude = [r for k, r in cache["photos"].items() if "TAD JUDE" in k.upper()]
        self.assertEqual([r["credit"]["year"] for r in jude], [1981])
        # A file Commons no longer describes (Todd Achilles's was deleted)
        # keeps its last credit until a read answers (rule 8): a few, never
        # the many read before credits carried a year.
        commons = [r for r in portraits.load_cache(ROOT).values()
                   if r.get("url") and portraits.wikimedia_file(r["url"]) and r.get("credit")]
        stale = [r.get("name") for r in commons if r["credit"].get("form") != portraits.CREDIT_FORM]
        self.assertLess(len(stale), len(commons) / 50, stale)


if __name__ == "__main__":
    unittest.main()
