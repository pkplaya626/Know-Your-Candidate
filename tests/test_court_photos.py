"""Each state justice's photograph, from their own court's pages (rule 87;
kyc/court_photos.py, kyc/official_photos.py)."""

import unittest

from kyc import court_photos, official_photos

ROSTER = "https://courts.example.gov/supreme-court/justices"


def image(src, alt="", title="", caption=""):
    return {"src": src, "alt": alt, "title": title, "caption": caption,
            "offered": [(0, src)]}


def measure_from(table):
    """A stand-in for official_photos.weigh: *table* maps an address to a
    weight, None (could not be read) or False (not an image)."""
    def measure(url):
        value = table.get(url, False)
        if value is None:
            return None, None
        if value is False:
            return False, None
        return True, value
    return measure


SMALL = {"bytes": 20_000, "width": 240, "height": 300}
HEAVY = {"bytes": 3_511_449, "width": 1920, "height": 2560}
MEMBERS = ["Joan K. Alexander", "Nora Dannehy", "Steven Ecker", "James E. Edmondson",
           "Noma Gurich", "Dana Kuehn", "C. Haley Bunn", "Rebeca Aizpuru Huddle"]


class TestTheWordsSayWhoseItIs(unittest.TestCase):
    def ok(self, name, img, members=MEMBERS):
        return court_photos.judge(name, members, img)[0]

    def test_the_justices_own_portrait_passes(self):
        self.assertTrue(self.ok("Steven Ecker", image(ROSTER + "/Ecker.jpg", "Justice Steven Ecker")))
        # Run together with a title: West Virginia's "justiceBunn".
        self.assertTrue(self.ok("C. Haley Bunn", image(ROSTER + "/bunn.jpg", "justiceBunn")))
        # A photographer's counter and a size: Georgia's "Bethel0945_8x10".
        self.assertTrue(self.ok("Charles J. Bethel", image(ROSTER + "/Bethel0945_8x10-400x500.jpg"),
                                ["Charles J. Bethel"]))

    def test_a_page_whose_image_names_someone_else_is_refused(self):
        """Two of Connecticut's justices' own pages carry a former justice's
        alt text; the image is not taken for the page's justice."""
        img = image(ROSTER + "/Justice_Alexander.jpg", "Justice Christine E. Keller")
        self.assertFalse(self.ok("Joan K. Alexander", img))
        # Another member of the court named in the file.
        self.assertFalse(self.ok("Noma Gurich", image(ROSTER + "/hargrave-and-gurich-487x630.jpg")))
        self.assertFalse(self.ok("Dana Kuehn", image(ROSTER + "/kuehn-and-gurich.jpg")))

    def test_a_scene_is_refused(self):
        img = image(ROSTER + "/edmondson-pinning.jpg", caption=(
            "Justice James Edmondson is pinned by his brother, former Attorney General "
            "Drew Edmondson"))
        self.assertFalse(self.ok("James E. Edmondson", img))
        self.assertFalse(self.ok("Dana Kuehn", image(ROSTER + "/kuehn-ok-nonprofit-conference-ocu.jpg")))

    def test_a_resizing_scripts_file_is_read_from_its_query(self):
        """Ohio's pages serve each portrait through timthumb.php; the file
        it names carries the surname, the script's name does not."""
        src = ("https://www.supremecourt.ohio.gov/assets/inc/timthumb.php?w=350"
               "&src=/docs/images/justices/kennedy_highres.jpg")
        self.assertEqual(official_photos.file_name(src), "kennedy_highres.jpg")
        self.assertTrue(self.ok("Sharon L. Kennedy", image(src, "Sharon Kennedy photo"),
                                ["Sharon L. Kennedy", "Patrick F. Fischer"]))

    def test_a_content_hash_and_a_possessive_are_not_other_words(self):
        """Iowa's roster files each portrait under a hash and alt-texts it
        "View David May's profile"; split at its digits the hash left "cf",
        and "May's" read as a word beyond the name."""
        members = ["Dana Oxley", "David May", "Christopher McDonald"]
        self.assertTrue(self.ok("Dana Oxley", image(
            ROSTER + "/Justice_Dana_Oxley_web_3CF35263E46B0.jpg",
            "Image of Dana Oxley. View Dana Oxley's profile"), members))
        self.assertTrue(self.ok("David May", image(
            ROSTER + "/J_May_website_A8AC15EE628CC.jpg",
            "Image of David May. View David May's profile"), members))
        # The hash goes; another member's name in the file still refuses it.
        self.assertFalse(self.ok("Dana Oxley", image(
            ROSTER + "/Justice_Christopher_McDonald_web_8AAB946804A8C.jpg"), members))

    def test_an_image_without_the_surname_is_refused(self):
        self.assertFalse(self.ok("Nora Dannehy", image(ROSTER + "/a1b2c3d4e5f6a7b8.jpg")))




class TestTheBioPage(unittest.TestCase):
    def test_the_page_linked_from_the_justices_name(self):
        page = ('<a href="/justices/ecker">Justice Steven D. Ecker</a>'
                '<a href="/justices/dannehy">Nora Dannehy</a>')
        found = court_photos.bio_pages(ROSTER, page, ["Steven Ecker", "Nora Dannehy"])
        self.assertEqual(found["Steven Ecker"], "https://courts.example.gov/justices/ecker")

    def test_a_bio_link_in_the_justices_own_row(self):
        page = ('<tr><td>Justice C. Haley Bunn</td><td><a href="/bio-1">Bio</a></td></tr>'
                '<tr><td>Justice James W. Flanigan</td><td><a href="/bio-2">Bio</a></td></tr>')
        found = court_photos.bio_pages(ROSTER, page, ["C. Haley Bunn", "James W. Flanigan"])
        self.assertEqual(found, {"C. Haley Bunn": "https://courts.example.gov/bio-1",
                                 "James W. Flanigan": "https://courts.example.gov/bio-2"})

    def test_never_another_site_or_a_pdf(self):
        page = ('<a href="https://news.example.com/ecker">Steven Ecker</a>'
                '<a href="/ecker.pdf">Steven Ecker</a>')
        self.assertEqual(court_photos.bio_pages(ROSTER, page, ["Steven Ecker"]), {})


class TestTheSizeThePageOffers(unittest.TestCase):
    def test_an_image_offered_only_above_the_caps_is_left_out(self):
        page = '<img src="/kari-gray.jpg" alt="Justice Kari Gray">'
        measure = measure_from({"https://courts.example.gov/kari-gray.jpg": HEAVY})
        found, why = court_photos.photo_for("Kari Gray", ["Kari Gray"], [(ROSTER, page)],
                                            measure=measure)
        self.assertIsNone(found)
        self.assertEqual(why, official_photos.OVERSIZED)

    def test_a_smaller_size_the_page_offers_is_taken(self):
        page = ('<img src="/gray.jpg" srcset="/gray-240x300.jpg 240w, /gray.jpg 1920w" '
                'alt="Justice Kari Gray">')
        measure = measure_from({"https://courts.example.gov/gray.jpg": HEAVY,
                                "https://courts.example.gov/gray-240x300.jpg": SMALL})
        found, _ = court_photos.photo_for("Kari Gray", ["Kari Gray"], [(ROSTER, page)],
                                          measure=measure)
        self.assertEqual(found["photo"], "https://courts.example.gov/gray-240x300.jpg")
        self.assertEqual(official_photos.record_problems(found, "x"), [])
        self.assertIn("Justice Kari Gray", found["evidence"])

    def test_a_landscape_image_is_not_a_portrait(self):
        page = '<img src="/gray.jpg" alt="Justice Kari Gray">'
        measure = measure_from({"https://courts.example.gov/gray.jpg":
                                {"bytes": 20_000, "width": 570, "height": 380}})
        found, _ = court_photos.photo_for("Kari Gray", ["Kari Gray"], [(ROSTER, page)],
                                          measure=measure)
        self.assertIsNone(found)


class TestARunThatConcludesNothing(unittest.TestCase):
    def test_the_last_photograph_read_is_kept(self):
        before = {"XX": {"photos": {"Kari Gray": official_photos.record(
            "https://courts.example.gov/gray.jpg", ROSTER, "alt 'Justice Kari Gray'", SMALL,
            read="2026-10-19")}}}
        courts = {"XX": {"members": ["Kari Gray"]}}
        page = '<img src="/gray.jpg" alt="Justice Kari Gray">'
        from kyc import courts as court_module
        court_module.COURTS["XX"] = {"url": ROSTER}
        try:
            problems = court_photos.add_justice_photos(
                courts, {"XX": page}, before, get=lambda url, **k: "", pause=0,
                measure=measure_from({"https://courts.example.gov/gray.jpg": None}))
        finally:
            del court_module.COURTS["XX"]
        self.assertEqual(courts["XX"]["photos"]["Kari Gray"]["read"], "2026-10-19")
        self.assertTrue(any("could not be read" in p for p in problems))


class TestEveryCachedPhotographIsWhole(unittest.TestCase):
    def test_a_record_without_its_evidence_or_weight_is_refused(self):
        rec = official_photos.record("https://courts.example.gov/a.jpg", ROSTER, "", SMALL)
        self.assertTrue(official_photos.record_problems(rec, "x"))
        rec = official_photos.record("https://courts.example.gov/a.jpg", ROSTER, "alt 'A'",
                                     HEAVY)
        self.assertTrue(any("caps" in p for p in official_photos.record_problems(rec, "x")))

    def test_the_committed_cache_and_overrides_carry_every_field(self):
        from kyc import courts
        cache = courts.load_cache(".") or {}
        for code, read in (cache.get("courts") or {}).items():
            for name, rec in (read.get("photos") or {}).items():
                with self.subTest(code=code, name=name):
                    self.assertEqual(official_photos.record_problems(rec, name), [])
                    self.assertIn(name, read["members"])
        members = {c: r.get("members") or [] for c, r in (cache.get("courts") or {}).items()}
        errors, _ = court_photos.curated_problems(members)
        self.assertEqual(errors, [])

    def test_the_page_is_given_only_a_whole_record(self):
        read = {"members": ["Kari Gray", "Lynne Boomgaarden"], "photos": {
            "Kari Gray": official_photos.record("https://courts.example.gov/a.jpg", ROSTER,
                                                "alt 'Justice Kari Gray'", SMALL),
            "Lynne Boomgaarden": {"photo": "https://courts.example.gov/b.jpg"}}}
        shown = court_photos.for_page("WY", read)
        self.assertEqual(list(shown), ["Kari Gray"])
        self.assertEqual(shown["Kari Gray"]["page"], ROSTER)


if __name__ == "__main__":
    unittest.main()
