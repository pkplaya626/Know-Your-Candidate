"""A photograph beside each statewide candidate, by the routes rule 91 now
allows and no other (kyc/statewide_photos.py; rules 24, 33, 87)."""

import unittest
from unittest import mock

from kyc import official_photos, statewide_photos as sp

SMALL = {"bytes": 38_361, "width": 330, "height": 436}
HEAVY = {"bytes": 3_000_000, "width": 2000, "height": 2600}


def no_lighter(url, weight, weigh):
    return None


def measure_from(table):
    def measure(url):
        value = table.get(url, False)
        if value is None:
            return None, None
        if value is False:
            return False, None
        return True, value
    return measure


class TestNames(unittest.TestCase):
    def test_surname_and_given_name_both(self):
        self.assertTrue(sp.same_person("Aaron D. Ford", "Aaron Ford"))
        # Danielle Ford is not Aaron Ford: the race page links both.
        self.assertFalse(sp.same_person("Danielle Ford", "Aaron Ford (Nevada politician)"))
        # A one-word name settles nothing (Massachusetts prints "JAMES").
        self.assertFalse(sp.same_person("JAMES", "Andrea C. James"))

    def test_a_running_mate_only_on_their_own_ticket(self):
        people = [{"name": "Sine Kerr", "runningMate": "Andy Biggs"},
                  {"name": "John Giles", "runningMate": "Katie Hobbs"}]
        self.assertEqual(sp.matches(people, "Sine Kerr", "Biggs")["name"], "Sine Kerr")
        self.assertIsNone(sp.matches(people, "Sine Kerr", "Hobbs"))

    def test_the_ticket_decides_which_links_a_lieutenant_governor_is_matched_among(self):
        links = [("Phil Weiser", "Phil Weiser", None, None),
                 ("Jane Doe (politician)", "Jane Doe", None, "Phil Weiser"),
                 ("Jane Doe (activist)", "Jane Doe", None, "Barbara Kirkmeyer")]
        mine = sp.ticket_links("lt", {"name": "Jane Doe", "runningMate": "Phil Weiser"}, links)
        self.assertEqual([l[0] for l in mine], ["Jane Doe (politician)"])
        # A governor is never matched among the running mates.
        self.assertEqual([l[0] for l in sp.ticket_links("governor", {"name": "Jane Doe"}, links)],
                         ["Phil Weiser"])


class TestTheOfficialGuides(unittest.TestCase):
    def test_arizonas_list_pairs_picture_name_and_office_and_never_picture_zero(self):
        page = ('<li><img class="pic" src="/Custom/Picture/6435"><b>Sine Kerr (Biggs)</b>'
                '<span class="office">Lieutenant Governor</span>'
                '<span class="party">Republican</span></li>'
                '<li><img class="pic" src="/Custom/Picture/0"><b>Alice Novoa</b>'
                '<span class="office">Governor</span></li>'
                '<li><img class="pic" src="/Custom/Picture/12"><b>Jo Roe</b>'
                '<span class="office">State Senator</span></li>')
        found = sp.parse_arizona(page)
        self.assertEqual(len(found), 1)
        office, name, ticket, url, words = found[0]
        self.assertEqual((office, name, ticket), ("lt", "Sine Kerr", "Biggs"))
        self.assertTrue(url.endswith("/Custom/Picture/6435"))
        self.assertIn("Sine Kerr (Biggs)", words)

    def test_californias_statements_are_paired_by_block_never_by_nearness(self):
        """The image comes before the heading: a parser that took the next
        image gave Rob Bonta Michael Gates's face."""
        page = ('<div class="grid-parent clearfix"><img src="/img/no-photo.png" '
                'alt="No Photo Submitted"><h2>Rob Bonta | DEMOCRATIC</h2></div>'
                '<div class="grid-parent clearfix"><img src="/img/gates.jpg" '
                'alt="Michael E. Gates"><h2>Michael E. Gates | REPUBLICAN</h2></div>')
        found = sp.parse_california(page, "ag")
        self.assertEqual([(f[1], f[3].rsplit("/", 1)[1]) for f in found],
                         [("Michael E. Gates", "gates.jpg")])

    def test_an_alt_text_naming_someone_else_is_refused(self):
        page = ('<div class="grid-parent clearfix"><img src="/img/x.jpg" alt="Fiona Ma">'
                '<h2>Gloria Romero | DEMOCRATIC</h2></div>')
        self.assertEqual(sp.parse_california(page, "lt"), [])

    def test_a_guide_photograph_offered_only_above_the_caps_is_shown_and_said(self):
        """The owner's decision of 2026-10-25 (rule 87): never left out for
        its weight; smaller from the same file where Photon serves it."""
        lists = {"CA": {"ag": [{"name": "Michael E. Gates"}]}}
        page = ('<div class="grid-parent clearfix"><img src="/img/gates.jpg" '
                'alt="Michael E. Gates"><h2>Michael E. Gates | REPUBLICAN</h2></div>')
        url = "https://voterguide.sos.ca.gov/img/gates.jpg"
        records, _, _ = sp.read_guides(lists, measure=measure_from({url: HEAVY}), pause=0,
                                       get=lambda u: page)
        rec = records["CA|ag|Michael E. Gates"]
        self.assertEqual(rec["photo"], url)
        self.assertEqual(rec["portraitHeavy"][0], {"url": url, "why": "3000 KB, over 300 KB",
                                                   "kept": True})
        self.assertEqual(official_photos.record_problems(rec, "x"), [])
        smaller = "https://i0.wp.com/voterguide.sos.ca.gov/img/gates.jpg?w=500&ssl=1"
        records, _, _ = sp.read_guides(lists, measure=measure_from({
            url: HEAVY, smaller: {"bytes": 50_000, "width": 500, "height": 650}}), pause=0,
            get=lambda u: page)
        rec = records["CA|ag|Michael E. Gates"]
        self.assertEqual(rec["photo"], smaller)
        self.assertFalse(rec["portraitHeavy"][0]["kept"])
        records, _, _ = sp.read_guides(lists, measure=measure_from({url: SMALL}), pause=0,
                                       get=lambda u: page)
        rec = records["CA|ag|Michael E. Gates"]
        self.assertEqual(rec["photo"], url)
        self.assertNotIn("portraitHeavy", rec)
        self.assertEqual(rec["by"], sp.CA_BY)
        self.assertEqual(official_photos.record_problems(rec, "x"), [])

    def test_a_guide_photograph_a_person_refused_is_not_used(self):
        lists = {"CA": {"ag": [{"name": "Michael E. Gates"}]}}
        page = ('<div class="grid-parent clearfix"><img src="/img/gates.jpg" '
                'alt="Michael E. Gates"><h2>Michael E. Gates | REPUBLICAN</h2></div>')
        url = "https://voterguide.sos.ca.gov/img/gates.jpg"
        records, problems, _ = sp.read_guides(lists, measure=measure_from({url: SMALL}), pause=0,
                                              get=lambda u: page, refused={url: ("x", "y")})
        self.assertEqual(records, {})
        self.assertTrue(any("NOT_A_PORTRAIT" in p for p in problems))


class TestTheRacesOwnArticle(unittest.TestCase):
    ARTICLE = {"title": "Ty Masterson", "missing": False, "fragment": None,
               "image": "Ty Masterson 2025.jpg", "disambiguation": False}
    COMMONS = {"info": {"width": 614, "height": 864,
                        "url": ("https://upload.wikimedia.org/wikipedia/commons/2/24/Ty_Masterson_2025.jpg"
                                "?utm_source=commons.wikimedia.org&utm_content=original"),
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Ty_Masterson_2025.jpg",
                        "extmetadata": {"Artist": {"value": "Jane Photographer"},
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                                        "AttributionRequired": {"value": "true"}}},
               "categories": []}
    LINKS = [("Ty Masterson", "Ty Masterson", None, None)]

    def photo(self, candidate, links=None, article=None, commons=None, measure=None):
        with mock.patch.object(sp, "_resolve", return_value=dict(article or self.ARTICLE)), \
                mock.patch.object(sp, "_commons", return_value=commons or self.COMMONS):
            return sp.wiki_photo("KS", "governor", candidate, links or self.LINKS,
                                 "2026 Kansas gubernatorial election",
                                 measure=measure or (lambda u: (True, SMALL)))

    def test_the_linked_articles_lead_image_at_a_standard_width(self):
        rec, why = self.photo({"name": "Ty Masterson"})
        self.assertEqual(why, "")
        self.assertIn("/250px-", rec["photo"])
        self.assertEqual(rec["credit"]["licence"], "CC BY-SA 4.0")
        self.assertEqual(rec["route"], "wikipedia")
        self.assertIn("2026 Kansas gubernatorial election", rec["evidence"])

    def test_a_list_that_writes_the_surname_first_is_read_as_the_page_shows_it(self):
        """Alaska's list prints "Masterson, Ty": the article title and the
        file name are checked against the name first name first."""
        rec, why = self.photo({"name": "Masterson, Ty"})
        self.assertEqual(why, "")
        self.assertTrue(rec["photo"])

    def test_a_surname_alone_is_never_enough(self):
        links = [("Aaron Ford (Nevada politician)", "Aaron Ford", None, None)]
        self.assertEqual(self.photo({"name": "Danielle Ford"}, links), (None, "not-linked"))

    def test_an_article_that_is_not_theirs_is_refused(self):
        article = dict(self.ARTICLE, title="2026 Kansas elections")
        self.assertEqual(self.photo({"name": "Ty Masterson"}, article=article),
                         (None, "article-not-theirs"))
        article = dict(self.ARTICLE, fragment="Candidates")
        self.assertEqual(self.photo({"name": "Ty Masterson"}, article=article),
                         (None, "article-not-theirs"))

    def test_a_scene_or_a_file_without_the_surname_is_refused(self):
        self.assertFalse(sp.file_ok("Lt. Governor Susan Bysiewicz at Women's History Month panel "
                                    "(cropped).jpg", "Susan Bysiewicz"))
        self.assertFalse(sp.file_ok("Ohio Senate pamphlet 2013 page 2.jpg", "Keith Faber"))
        self.assertTrue(sp.file_ok("Ty Masterson 2025.jpg", "Ty Masterson"))

    def test_public_domain_on_an_uploaders_word_alone_is_refused(self):
        commons = dict(self.COMMONS, info=dict(self.COMMONS["info"], extmetadata={
            "Artist": {"value": "Unknown"}, "LicenseShortName": {"value": "Public domain"}}),
            categories=["Category:PD-author"])
        self.assertEqual(self.photo({"name": "Ty Masterson"}, commons=commons),
                         (None, "public-domain-unsupported"))
        self.assertEqual(sp.licence_basis(["Category:PD US Congress"]), "PD US Congress")

    def test_a_photograph_offered_only_above_the_caps_is_shown_and_said(self):
        with mock.patch("kyc.photos.lighter_form", no_lighter):
            rec, why = self.photo({"name": "Ty Masterson"}, measure=lambda u: (True, HEAVY))
        self.assertEqual(why, "")
        self.assertTrue(rec["portraitHeavy"][0]["kept"])
        self.assertEqual(official_photos.record_problems(rec, "x"), [])

    def test_a_refused_file_is_never_taken(self):
        """One list for every route (rule 38): NOT_A_PORTRAIT, keyed on the
        Commons upload address as for a judge's portrait."""
        upload = "https://upload.wikimedia.org/wikipedia/commons/2/24/Ty_Masterson_2025.jpg"
        with mock.patch.object(sp, "_resolve", return_value=dict(self.ARTICLE)), \
                mock.patch.object(sp, "_commons", return_value=self.COMMONS):
            self.assertEqual(sp.wiki_photo("KS", "governor", {"name": "Ty Masterson"},
                                           self.LINKS, "x", refused={upload: ("x", "y")}),
                             (None, "not-a-portrait"))
        from kyc import overrides
        overrides.NOT_A_PORTRAIT[upload] = ("2026-10-25", "a test")
        try:
            rec, _ = self.photo({"name": "Ty Masterson"})
            self.assertIsNone(rec)
            # And a record cached before the entry was made is withheld.
            del overrides.NOT_A_PORTRAIT[upload]
            rec, _ = self.photo({"name": "Ty Masterson"})
            overrides.NOT_A_PORTRAIT[upload] = ("2026-10-25", "a test")
            self.assertIn("NOT_A_PORTRAIT", sp.withheld_why("KS|governor|Ty Masterson", rec))
            self.assertIn(upload, sp.doubted({"photos": {"k": rec}}))
        finally:
            overrides.NOT_A_PORTRAIT.pop(upload, None)

    def test_a_licence_doubt_withholds_the_file(self):
        upload = "https://upload.wikimedia.org/wikipedia/commons/2/24/Ty_Masterson_2025.jpg"
        from kyc import overrides
        rec, _ = self.photo({"name": "Ty Masterson"})
        overrides.PORTRAIT_LICENCE_DOUBTS[upload] = ("2026-10-25", "a test")
        try:
            self.assertIn("PORTRAIT_LICENCE_DOUBTS",
                          sp.withheld_why("KS|governor|Ty Masterson", rec))
        finally:
            del overrides.PORTRAIT_LICENCE_DOUBTS[upload]

    def test_rule_82s_one_test_for_a_declared_licence(self):
        """PR #135 review: public domain on an uploader's word was refused
        while CC0 and "Copyrighted free use" on the same word were taken."""
        doubt = sp.licence_doubt
        # No author named at all (David Jolly's file).
        self.assertTrue(doubt({"by": None, "licence": "Public domain", "basis": "PD US Congress"},
                              "David Jolly (cropped).jpg"))
        # An official portrait under a user account's own CC0 (Kris Kobach's).
        self.assertTrue(doubt({"by": "WilliamJHendrixKS", "licence": "CC0"},
                              "Kris Kobach official portrait, 2024 (cropped).jpg"))
        # Public domain with no basis recorded.
        self.assertTrue(doubt({"by": "Someone", "licence": "Public domain"}, "A B.jpg"))
        # A government office's own release stands, as does a campaign's
        # CC0 of a file that does not call itself official.
        self.assertEqual(doubt({"by": "Zach Pippin, Office of the Governor of South Carolina",
                                "licence": "CC0"}, "Mark Hammond cropped.jpg"), "")
        self.assertEqual(doubt({"by": "Maryland State Government", "licence": "Attribution"},
                               "Aruna Miller Official Portrait.jpg"), "")
        self.assertEqual(doubt({"by": "Rob Sand for Governor", "licence": "CC0"},
                               "Rob Sand campaign headshot (cropped 1).jpg"), "")
        self.assertTrue(doubt({"by": "Rob Sand for Governor", "licence": "CC0"},
                              "Rob Sand official portrait.jpg"))
        self.assertEqual(doubt({"by": "Jane Photographer", "licence": "CC BY-SA 4.0"},
                               "Ty Masterson 2025.jpg"), "")

    def test_a_doubted_licence_is_not_read_and_a_cached_one_is_withheld(self):
        commons = dict(self.COMMONS, info=dict(self.COMMONS["info"], extmetadata={
            "Artist": {"value": "SomeUser"}, "LicenseShortName": {"value": "CC0"}}))
        article = dict(self.ARTICLE, image="Ty Masterson official portrait.jpg")
        self.assertEqual(self.photo({"name": "Ty Masterson"}, commons=commons, article=article),
                         (None, "licence-doubt"))

    def test_an_event_crop_is_refused(self):
        """PR #135 review: an editor's crop of "Nevada Attorney General Aaron
        Ford addresses the United Nations Human Rights Committee"."""
        self.assertFalse(sp.file_ok("Nevada Attorney General Aaron Ford addresses the United "
                                    "Nations Human Rights Committee, October 17-18, 2023 1 "
                                    "(cropped).jpg", "Aaron D. Ford"))


class TestThePage(unittest.TestCase):
    LISTED = {"candidates": [{"name": "Katie Hobbs", "holder": True},
                             {"name": "Andy Biggs"}, {"name": "Alice Novoa"}]}

    def rows(self):
        return [{"name": "Andy Biggs"}, {"name": "Katie Hobbs", "holder": True},
                {"name": "Alice Novoa"}]

    def test_the_holder_takes_the_cards_photograph_and_its_credit(self):
        rows = self.rows()
        holder = {"name": "Katie Hobbs", "headshot": "https://nga.example/hobbs.jpg",
                  "headshotBy": "National Governors Association"}
        status = {"why": "listed", "name": "Katie Hobbs"}
        sp.attach("AZ", "governor", rows, self.LISTED, holder, status, {})
        self.assertEqual(rows[1]["photo"], "https://nga.example/hobbs.jpg")
        self.assertEqual(rows[1]["photoCredit"]["by"], "National Governors Association")
        self.assertNotIn("photo", rows[0])

    def test_a_holder_the_card_does_not_picture_gives_none(self):
        rows = self.rows()
        holder = {"name": "Katie Hobbs", "photo": "https://x.example/h.jpg", "photoBy": "X",
                  "unconfirmed": True}
        sp.attach("AZ", "ag", rows, self.LISTED, holder, {"why": "listed", "name": "Katie Hobbs"},
                  {})
        self.assertNotIn("photo", rows[1])

    def test_a_cached_photograph_with_its_credit_and_a_heavy_one_shown_and_counted(self):
        rows = self.rows()
        rec = official_photos.record("https://www.azcleanelections.gov/Custom/Picture/2427",
                                     sp.AZ_LIST, "the list pairs Picture/2427 with 'Andy Biggs'",
                                     SMALL, by=sp.AZ_BY, route="guide")
        heavy = official_photos.record(
            "https://www.azcleanelections.gov/Custom/Picture/99", sp.AZ_LIST,
            "the list pairs Picture/99 with 'Alice Novoa'", HEAVY, by=sp.AZ_BY, route="guide",
            portraitHeavy=[{"url": "https://www.azcleanelections.gov/Custom/Picture/99",
                            "why": "3000 KB, over 300 KB", "kept": True}])
        cache = {"photos": {"AZ|governor|Andy Biggs": rec, "AZ|governor|Alice Novoa": heavy}}
        shown_heavy = sp.attach("AZ", "governor", rows, self.LISTED, None, None, cache)
        self.assertEqual(shown_heavy, 1)
        self.assertEqual(rows[0]["photoCredit"], {"by": sp.AZ_BY, "page": sp.AZ_LIST})
        self.assertEqual(rows[2]["photo"], "https://www.azcleanelections.gov/Custom/Picture/99")
        self.assertEqual(sp.counts(cache)["heavy"], 1)

    def test_a_cached_photograph_without_its_evidence_is_never_shown(self):
        rows = self.rows()
        rec = official_photos.record("https://www.azcleanelections.gov/Custom/Picture/2427",
                                     sp.AZ_LIST, "", SMALL, by=sp.AZ_BY, route="guide")
        cache = {"photos": {"AZ|governor|Andy Biggs": rec}}
        sp.attach("AZ", "governor", rows, self.LISTED, None, None, cache)
        self.assertNotIn("photo", rows[0])
        self.assertTrue(sp.problems(cache))

    def test_a_commons_file_with_no_author_is_whole_but_withheld(self):
        """David Jolly's file names no author: the record is whole (rule 87:
        the credit would say "author not recorded on Commons"), but rule
        82's one test doubts a file that names no author, so the page does
        not show it; an official guide's record without whose it is is not
        whole."""
        rec = official_photos.record(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/J.jpg/250px-J.jpg",
            "https://en.wikipedia.org/wiki/2026_Florida_gubernatorial_election",
            "The race's article links [[David Jolly]]", SMALL, route="wikipedia",
            credit={"by": None, "licence": "CC BY 2.0", "authorUnrecorded": True,
                    "page": "https://commons.wikimedia.org/wiki/File:J.jpg",
                    "via": "Wikimedia Commons"})
        self.assertEqual(sp.problems({"photos": {"FL|governor|David Jolly": rec}}), [])
        self.assertIn("names no author", sp.withheld_why("FL|governor|David Jolly", rec))
        rows = [{"name": "David Jolly"}]
        sp.attach("FL", "governor", rows, {"candidates": [{"name": "David Jolly"}]}, None, None,
                  {"photos": {"FL|governor|David Jolly": rec}})
        self.assertNotIn("photo", rows[0])
        guide = official_photos.record("https://www.azcleanelections.gov/Custom/Picture/1",
                                       sp.AZ_LIST, "the list pairs Picture/1 with 'A B'", SMALL,
                                       route="guide")
        self.assertTrue(sp.problems({"photos": {"AZ|governor|A B": guide}}))

    def test_the_committed_cache_is_whole(self):
        cache = sp.load_cache(".")
        if cache is None:
            self.skipTest("no statewide photographs cached")
        self.assertEqual(sp.problems(cache), [])


if __name__ == "__main__":
    unittest.main()
