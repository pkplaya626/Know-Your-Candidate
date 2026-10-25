"""A photograph beside each statewide candidate, by the routes rule 91 now
allows and no other (kyc/statewide_photos.py; rules 24, 33, 87)."""

import unittest
from unittest import mock

from kyc import official_photos, statewide_photos as sp

SMALL = {"bytes": 38_361, "width": 330, "height": 436}
HEAVY = {"bytes": 3_000_000, "width": 2000, "height": 2600}


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

    def test_a_guide_photograph_offered_only_above_the_caps_is_left_out(self):
        lists = {"CA": {"ag": [{"name": "Michael E. Gates"}]}}
        page = ('<div class="grid-parent clearfix"><img src="/img/gates.jpg" '
                'alt="Michael E. Gates"><h2>Michael E. Gates | REPUBLICAN</h2></div>')
        url = "https://voterguide.sos.ca.gov/img/gates.jpg"
        records, _, _ = sp.read_guides(lists, measure=measure_from({url: HEAVY}), pause=0,
                                       get=lambda u: page)
        self.assertEqual(records, {"CA|ag|Michael E. Gates": {"missing": official_photos.OVERSIZED,
                                                               "route": "guide"}})
        records, _, _ = sp.read_guides(lists, measure=measure_from({url: SMALL}), pause=0,
                                       get=lambda u: page)
        rec = records["CA|ag|Michael E. Gates"]
        self.assertEqual(rec["photo"], url)
        self.assertEqual(rec["by"], sp.CA_BY)
        self.assertEqual(official_photos.record_problems(rec, "x"), [])


class TestTheRacesOwnArticle(unittest.TestCase):
    ARTICLE = {"title": "Ty Masterson", "missing": False, "fragment": None,
               "image": "Ty Masterson 2025.jpg", "disambiguation": False}
    COMMONS = {"info": {"width": 614, "height": 864,
                        "url": ("https://upload.wikimedia.org/wikipedia/commons/a/ab/Ty_Masterson_2025.jpg"
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

    def test_a_photograph_offered_only_above_the_caps_is_left_out(self):
        rec, why = self.photo({"name": "Ty Masterson"}, measure=lambda u: (True, HEAVY))
        self.assertIsNone(rec)
        self.assertEqual(why, official_photos.OVERSIZED)

    def test_a_refused_file_is_never_taken(self):
        with mock.patch.object(sp, "_resolve", return_value=dict(self.ARTICLE)), \
                mock.patch.object(sp, "_commons", return_value=self.COMMONS):
            self.assertEqual(sp.wiki_photo("KS", "governor", {"name": "Ty Masterson"},
                                           self.LINKS, "x", refused={"File:Ty Masterson 2025.jpg"}),
                             (None, "not-a-portrait"))


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

    def test_a_cached_photograph_with_its_credit_and_the_left_out_counted(self):
        rows = self.rows()
        rec = official_photos.record("https://www.azcleanelections.gov/Custom/Picture/2427",
                                     sp.AZ_LIST, "the list pairs Picture/2427 with 'Andy Biggs'",
                                     SMALL, by=sp.AZ_BY, route="guide")
        cache = {"photos": {"AZ|governor|Andy Biggs": rec,
                            "AZ|governor|Alice Novoa": {"missing": official_photos.OVERSIZED}}}
        left_out = sp.attach("AZ", "governor", rows, self.LISTED, None, None, cache)
        self.assertEqual(left_out, 1)
        self.assertEqual(rows[0]["photoCredit"], {"by": sp.AZ_BY, "page": sp.AZ_LIST})
        self.assertNotIn("photo", rows[2])

    def test_a_cached_photograph_without_its_evidence_is_never_shown(self):
        rows = self.rows()
        rec = official_photos.record("https://www.azcleanelections.gov/Custom/Picture/2427",
                                     sp.AZ_LIST, "", SMALL, by=sp.AZ_BY, route="guide")
        cache = {"photos": {"AZ|governor|Andy Biggs": rec}}
        sp.attach("AZ", "governor", rows, self.LISTED, None, None, cache)
        self.assertNotIn("photo", rows[0])
        self.assertTrue(sp.problems(cache))

    def test_a_commons_file_with_no_author_says_so_and_is_kept(self):
        """David Jolly's file names no author: the credit says "author not
        recorded on Commons" and links the file (rule 87), so the record is
        whole; an official guide's record without whose it is is not."""
        rec = official_photos.record(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/J.jpg/250px-J.jpg",
            "https://en.wikipedia.org/wiki/2026_Florida_gubernatorial_election",
            "The race's article links [[David Jolly]]", SMALL, route="wikipedia",
            credit={"by": None, "licence": "CC BY 2.0", "authorUnrecorded": True,
                    "page": "https://commons.wikimedia.org/wiki/File:J.jpg",
                    "via": "Wikimedia Commons"})
        self.assertEqual(sp.problems({"photos": {"FL|governor|David Jolly": rec}}), [])
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
