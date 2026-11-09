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

    def test_a_guide_page_that_says_nothing_concludes_nothing(self):
        """coag.gov answered a script HTTP 202 with no body (2026-11-01). A
        guide answering so, with a bot wall, a page drawn by script or a
        redesign is not a guide that pictures no one: its key is unknown,
        and fetch keeps the last photographs read (rules 8 and 24)."""
        lists = {"AZ": {"governor": [{"name": "Katie Hobbs"}]},
                 "CA": {"ag": [{"name": "Michael E. Gates"}]}}
        for said in ("", "<html><head><title>Just a moment...</title></head></html>",
                     "<html><body><div id=app></div><script>render()</script></body></html>",
                     "<html><body><main>" + "<p>The 2026 guide.</p>" * 40 + "</main></body></html>",
                     # A redesign that keeps some of the markup: the list's
                     # pictures for other offices only, statement blocks
                     # whose names are no longer <h2> headings.
                     '<li><img class="pic" src="/Custom/Picture/12"><b>Jo Roe</b>'
                     '<span class="office">State Senator</span></li>'
                     '<div class="grid-parent clearfix"><img src="/img/gates.jpg" '
                     'alt="Michael E. Gates"><h3>Michael E. Gates | REPUBLICAN</h3></div>'):
            records, problems, unknown = sp.read_guides(lists, measure=measure_from({}), pause=0,
                                                        get=lambda u: said)
            self.assertEqual(records, {})
            self.assertEqual(unknown, {"AZ", "CA|ag"}, said)
            self.assertTrue(all("the last photographs read are kept" in p for p in problems),
                            problems)
        # Statements read, none with a photograph: read, not unknown.
        page = ('<div class="grid-parent clearfix"><img src="/img/no-photo.png" '
                'alt="No Photo Submitted"><h2>Rob Bonta | DEMOCRATIC</h2></div>')
        self.assertEqual(sp.parse_california(page, "ag"), [])

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

    def test_the_candidates_own_article_is_recorded_whatever_route_pictures_them(self):
        """The race's article's link to a candidate is a finding of its own:
        recorded where it links their article, said where it links none, and
        nothing where the article was not read (rule 19; PR #195 review)."""
        lists = {"KS": {"governor": [{"name": "Ty Masterson"}, {"name": "Nobody Linked"},
                                     {"name": "Sam Poe", "writeIn": True}]},
                 "WY": {"governor": [{"name": "Not Read"}]}}

        def wikitext(title):
            if "Wyoming" in title:
                raise RuntimeError("timed out")
            return title, "text"

        with mock.patch.object(sp, "race_links", return_value=self.LINKS):
            found, unknown = sp.read_articles(lists, wikitext=wikitext,
                                              resolve=lambda t: dict(self.ARTICLE), log=lambda m: None)
        k = lambda code, name: sp.key(code, "governor", name)  # noqa: E731
        self.assertEqual(found[k("KS", "Ty Masterson")]["article"], "Ty Masterson")
        self.assertEqual(found[k("KS", "Nobody Linked")]["none"], "not-linked")
        self.assertNotIn(k("KS", "Sam Poe"), found)
        self.assertNotIn(k("WY", "Not Read"), found)
        self.assertIn(k("WY", "Not Read"), unknown)
        # The last read stands for a race this read concluded nothing about.
        kept = sp.kept_articles(found, {k("WY", "Not Read"): {"article": "Not Read"}}, unknown)
        self.assertEqual(kept[k("WY", "Not Read")], {"article": "Not Read"})
        cache = {"articles": kept, "articlesRead": "2026-11-03", "photos": {}}
        self.assertEqual(sp.article_of(cache, "KS", "governor", "Nobody Linked")["none"], "not-linked")
        self.assertIsNone(sp.article_of(cache, "KS", "governor", "Someone Else"))

    def test_an_evidenced_short_form_is_a_name_the_races_link_may_give(self):
        """Nevada's article links [[Joe Lombardo]] for the list's "Lombardo,
        Joseph": the evidenced STATEWIDE_NAME_FORMS entry is a name the link
        may give, and only for the state and office it is recorded for
        (PR #195's second review)."""
        from kyc import overrides
        entry = ("ZZ", "governor", "Joe Testperson")
        overrides.STATEWIDE_NAME_FORMS[entry] = ("Testperson, Joseph", "a test")
        links = [("Joe Testperson", "Joe Testperson", None, None)]
        article = dict(self.ARTICLE, title="Joe Testperson")
        candidate = {"name": "Testperson, Joseph"}
        try:
            found, why = sp.linked_article("governor", candidate, links,
                                           resolve=lambda t: dict(article), code="ZZ")
            self.assertEqual((found[2]["title"], why), ("Joe Testperson", ""))
            # Another state's list, or no state, takes no short form.
            for code in ("YY", None):
                self.assertEqual(sp.linked_article("governor", candidate, links,
                                                   resolve=lambda t: dict(article), code=code),
                                 (None, "not-linked"))
        finally:
            del overrides.STATEWIDE_NAME_FORMS[entry]

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


class TestWhatTheMondayReadFound(unittest.TestCase):
    """The faults the read of 2026-11-09 showed, record by record."""

    ARTICLE = dict(TestTheRacesOwnArticle.ARTICLE, image="Pat Doe official portrait.jpg",
                   title="Pat Doe")
    LINKS = [("Pat Doe", "Pat Doe", "Pat Doe greets supporters at a rally.jpg", None)]

    def commons(self, file_name, width=614, height=864):
        name = file_name.replace(" ", "_")
        page = f"https://commons.wikimedia.org/wiki/File:{name}"
        upload = official_photos.commons_upload({"credit": {"page": page}})
        return {"info": {"width": width, "height": height,
                         # The API's own forms: the upload percent-encoded, the
                         # file page as it reads.
                         "url": upload.replace("(", "%28").replace(")", "%29"),
                         "descriptionurl": page,
                         "extmetadata": {"Artist": {"value": "Jane Photographer"},
                                         "LicenseShortName": {"value": "CC BY-SA 4.0"}}},
                "categories": []}

    def photo(self, links=None, article=None, commons=None, measure=None, **kw):
        with mock.patch.object(sp, "_resolve", return_value=dict(article or self.ARTICLE)), \
                mock.patch.object(sp, "_commons", side_effect=commons or self.commons):
            return sp.wiki_photo("XX", "governor", {"name": "Pat Doe"}, links or self.LINKS,
                                 "2026 race", measure=measure or (lambda u: (True, SMALL)), **kw)

    def test_a_scene_beside_the_nominee_gives_way_to_their_articles_portrait(self):
        """Ned Lamont: the race's infobox set a bridge visit beside him, over
        his own article's official portrait."""
        rec, why = self.photo()
        self.assertEqual(why, "")
        self.assertIn("Pat_Doe_official_portrait", rec["photo"])
        self.assertIn("leads with File:Pat Doe official portrait.jpg", rec["evidence"])
        # The infobox's own portrait still comes first.
        links = [("Pat Doe", "Pat Doe", "Pat Doe 2026.jpg", None)]
        rec, _ = self.photo(links=links)
        self.assertIn("Pat_Doe_2026", rec["photo"])
        # A scene in both (Tad Jude's) gives none, and says why.
        article = dict(self.ARTICLE, image="Pat Doe greets supporters at a rally.jpg")
        self.assertEqual(self.photo(article=article), (None, "file-name"))

    def test_a_persons_refusal_promotes_nothing(self):
        """Mayes Middleton's refused crop would have given way to the
        uncropped photograph it was cut from (rule 38)."""
        from kyc import overrides
        links = [("Pat Doe", "Pat Doe", "Pat Doe (cropped).jpg", None)]
        article = dict(self.ARTICLE, image="Pat Doe.jpg")
        crop = "https://upload.wikimedia.org/wikipedia/commons/8/87/Pat_Doe_(cropped).jpg"
        for table, why in ((overrides.NOT_A_PORTRAIT, "not-a-portrait"),
                           (overrides.PORTRAIT_LICENCE_DOUBTS, sp.LISTED_DOUBT)):
            with self.subTest(why=why), mock.patch.dict(table, {crop: ("2026-10-25", "a test")}):
                self.assertEqual(self.photo(links=links, article=article), (None, why))

    def test_a_file_that_concludes_nothing_gives_way_to_nothing(self):
        links = [("Pat Doe", "Pat Doe", "Pat Doe 2026.jpg", None)]

        def commons(file_name):
            return {"info": None, "categories": []} if "2026" in file_name else self.commons(file_name)
        self.assertEqual(self.photo(links=links, commons=commons),
                         (None, official_photos.UNKNOWN))

    def test_a_size_wikimedia_did_not_answer_for_is_not_passed_over(self):
        """Eleven photographs moved to another width of the same file on
        2026-11-09, Lisa Demuth's to 120px, on transient refusals."""
        def measure(url):
            return (None, None) if "/250px-" in url else (True, SMALL)
        self.assertEqual(self.photo(measure=measure), (None, official_photos.UNKNOWN))
        sizes = [(250, "a"), (330, "b"), (120, "c")]
        self.assertEqual(official_photos.choose(sizes, measure_from({"a": None, "b": SMALL}))[0],
                         "b")
        self.assertEqual(official_photos.choose(sizes, measure_from({"a": None, "b": SMALL}),
                                                strict=True)[2], official_photos.UNKNOWN)
        self.assertEqual(official_photos.choose(sizes, measure_from({"a": SMALL}), strict=True)[0],
                         "a")

    def test_a_persons_lists_are_asked_in_the_form_they_are_keyed(self):
        """The API writes "%28cropped%29", the lists "(cropped)": Mayes
        Middleton's refused file and three doubted licences were taken on
        every Monday and dropped on Tuesday."""
        from kyc import overrides
        links = [("Pat Doe", "Pat Doe", "Pat Doe (cropped).jpg", None)]
        article = dict(self.ARTICLE, image=None)
        keyed = "https://upload.wikimedia.org/wikipedia/commons/8/87/Pat_Doe_(cropped).jpg"
        for table, why in ((overrides.NOT_A_PORTRAIT, "not-a-portrait"),
                           (overrides.PORTRAIT_LICENCE_DOUBTS, sp.LISTED_DOUBT)):
            with self.subTest(why=why), mock.patch.dict(table, {keyed: ("2026-10-25", "a test")}):
                refusals, doubts = [], []
                self.assertEqual(self.photo(links=links, article=article, passed_over=refusals,
                                            doubted=doubts), (None, why))
                self.assertEqual(refusals + doubts, [keyed])
        # Through the whole read: never cached, and the refusal kept for
        # validate's staleness check.
        lists = {"states": {"XX": {"offices": {"governor": {"candidates": [{"name": "Pat Doe"}]}}}}}
        with mock.patch.dict(overrides.PORTRAIT_LICENCE_DOUBTS, {keyed: ("2026-10-25", "a test")}), \
                mock.patch.object(sp, "read_members", return_value=({}, [], set())), \
                mock.patch.object(sp, "read_guides", return_value=({}, [], set())), \
                mock.patch.object(sp, "_wikitext", lambda t: (t, "text")), \
                mock.patch.object(sp, "race_links", return_value=links), \
                mock.patch.object(sp, "_resolve", return_value=dict(article)), \
                mock.patch.object(sp, "_commons", side_effect=self.commons), \
                mock.patch.object(official_photos, "weigh", lambda u: (True, SMALL)):
            cache, _ = sp.fetch(lists, {}, None, log=lambda line: None)
        self.assertEqual(cache["photos"], {})
        self.assertEqual(cache["licenceDoubts"], {"XX|governor|Pat Doe": [keyed]})


class TestTheMondayReadEndsInsideItsStep(unittest.TestCase):
    """The refresh of 2026-11-09: the races' articles' read ran past its
    step's fifty minutes, printing nothing (Python buffers a pipe). It now
    has a budget (``--max-minutes``, rule 78), and keeps every race it did
    not reach as last read (rule 8), the oldest first next time."""

    TODAY = sp.datetime.date.today().isoformat()
    KS = "KS|governor|Ty Masterson"
    WY = "WY|governor|Pat Doe"
    WY_SOS = "WY|sos|Lee Roe"
    REFUSED = "https://upload.wikimedia.org/wikipedia/commons/1/1a/Lee_Roe_rally.jpg"

    def lists(self):
        return {"states": {
            "KS": {"offices": {"governor": {"candidates": [{"name": "Ty Masterson"}]}}},
            "WY": {"offices": {"governor": {"candidates": [{"name": "Pat Doe"}]},
                               "sos": {"candidates": [{"name": "Lee Roe"}]}}}}}

    def kept(self, name):
        return {"route": "wikipedia", "read": "2026-11-02", "bytes": 38_037,
                "photo": f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/{name}.jpg/"
                         f"250px-{name}.jpg",
                "page": "https://en.wikipedia.org/wiki/2026_race", "evidence": "the race links",
                "width": 250, "height": 314, "by": "A Legislature",
                "credit": {"by": "A Legislature", "licence": "CC BY 4.0", "year": 1981,
                           "yearForm": 4, "via": "Wikimedia Commons",
                           "page": f"https://commons.wikimedia.org/wiki/File:{name}.jpg"}}

    def previous(self):
        return {"read": "2026-11-02",
                "photos": {self.WY: self.kept("Pat_Doe")},
                "misses": {self.WY_SOS: "not-a-portrait"},
                "notPortraits": {self.WY_SOS: [self.REFUSED]},
                "articles": {self.WY: {"article": "Pat Doe", "page": "2026 Wyoming race"}},
                "articlesRead": "2026-11-02",
                # Kansas was read longest ago, so it is read first.
                "racesRead": {"KS|governor": "2026-10-26", "WY|governor": "2026-11-02",
                              "WY|sos": "2026-11-02"}}

    def run_fetch(self, budget, asked):
        """``fetch`` over Kansas and Wyoming with every network read made
        here; *asked* lists the race articles read, in order."""
        def wikitext(title):
            asked.append(title)
            return title, "text"

        def wiki_photo(code, office, candidate, links, title, *args, **kwargs):
            rec = self.kept(candidate["name"].replace(" ", "_"))
            rec["read"] = self.TODAY
            return rec, ""

        with mock.patch.object(sp, "read_members", return_value=({}, [], set())), \
                mock.patch.object(sp, "read_guides", return_value=({}, [], set())), \
                mock.patch.object(sp, "_wikitext", wikitext), \
                mock.patch.object(sp, "_resolve", return_value=dict(TestTheRacesOwnArticle.ARTICLE)), \
                mock.patch.object(sp, "race_links", return_value=TestTheRacesOwnArticle.LINKS), \
                mock.patch.object(sp, "wiki_photo", wiki_photo), \
                mock.patch.object(sp, "date_credits", return_value=0):
            return sp.fetch(self.lists(), {}, self.previous(), log=None, budget=budget)

    def test_a_race_not_reached_keeps_its_last_read(self):
        clock = iter([0, 0, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]).__next__
        budget = sp.Budget(60, clock=clock)
        asked = []
        cache, problems = self.run_fetch(budget, asked)
        # Kansas, read longest ago, was read; neither Wyoming race was begun.
        self.assertEqual(asked, ["2026 Kansas gubernatorial election"])
        self.assertEqual(cache["photos"][self.KS]["read"], self.TODAY)
        self.assertEqual(cache["photos"][self.WY], self.kept("Pat_Doe"))
        self.assertEqual(cache["misses"], {self.WY_SOS: "not-a-portrait"})
        self.assertEqual(cache["notPortraits"], {self.WY_SOS: [self.REFUSED]})
        # Wyoming's article record is kept with the day it was read.
        self.assertEqual(cache["articles"][self.WY]["read"], "2026-11-02")
        self.assertEqual(sp.article_of(cache, "WY", "governor", "Pat Doe")["read"], "2026-11-02")
        self.assertIsNone(cache["articles"][self.KS].get("read"))
        self.assertEqual(sp.article_of(cache, "KS", "governor", "Ty Masterson")["read"], self.TODAY)
        # The race read is dated, the others keep their day; and it is said.
        self.assertEqual(cache["racesRead"], {"KS|governor": self.TODAY,
                                              "WY|governor": "2026-11-02", "WY|sos": "2026-11-02"})
        said = [p for p in problems if "not reached within the time budget" in p]
        self.assertEqual(len(said), 2, problems)
        self.assertIn("WY|governor, WY|sos", said[0])

    def test_a_read_with_time_to_spare_reads_every_race_once(self):
        asked = []
        cache, problems = self.run_fetch(sp.Budget(None), asked)
        # The candidates' articles' read asks for no article the photographs'
        # read already read.
        self.assertEqual(sorted(asked), ["2026 Kansas gubernatorial election",
                                         "2026 Wyoming Secretary of State election",
                                         "2026 Wyoming gubernatorial election"])
        self.assertEqual(set(cache["racesRead"].values()), {self.TODAY})
        self.assertEqual(cache["photos"][self.WY]["read"], self.TODAY)
        self.assertNotIn("notPortraits", cache)
        self.assertFalse([p for p in problems if "time budget" in p])

    def test_the_race_read_longest_ago_comes_first(self):
        lists = {"AK": {"governor": [1]}, "KS": {"governor": [1], "sos": [1]}, "WY": {"lt": [1]}}
        order = sp.race_order(lists, {"AK|governor": "2026-11-02", "KS|governor": "2026-10-26",
                                      "WY|lt": "2026-11-02"})
        self.assertEqual(order, [("KS", "sos"), ("KS", "governor"), ("AK", "governor"),
                                 ("WY", "lt")])

    def test_an_answer_or_a_failure_is_asked_once(self):
        calls = []

        def reader(title):
            calls.append(title)
            if title == "bad":
                raise RuntimeError("timed out")
            return title.upper()

        read = sp.once(reader)
        self.assertEqual((read("a"), read("a")), ("A", "A"))
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                read("bad")
        self.assertEqual(calls, ["a", "bad"])

    def test_the_command_takes_a_budget_and_the_refresh_gives_one_inside_its_step(self):
        import os
        import re
        from kyc import cli
        args = cli.build_parser().parse_args(["ballotphotos", "--max-minutes", "38"])
        self.assertEqual(args.max_minutes, 38)
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, ".github", "workflows", "refresh.yml"), encoding="utf-8") as fh:
            text = fh.read()
        step = text[text.index("- name: Refresh the statewide candidates' photographs"):]
        step = step[:step.index("\n\n")]
        budget = float(re.search(r"ballotphotos --max-minutes (\d+(?:\.\d+)?)", step).group(1))
        limit = float(re.search(r"timeout-minutes: (\d+)", step).group(1))
        # Room for a race begun as the budget ran out, its 429s and the save.
        self.assertLessEqual(budget, limit - 10)
        # Python is the step's own process, so an ended step ends the read.
        for line in step.splitlines():
            if "build_profile_site.py ballotphotos" in line:
                self.assertTrue(line.strip().startswith("exec python "), line)
        # And a step ended at its limit keeps what it printed.
        job = text[text.index("\n  refresh:"):text.index("    steps:", text.index("\n  refresh:"))]
        self.assertRegex(job, r'PYTHONUNBUFFERED: "1"')


if __name__ == "__main__":
    unittest.main()
