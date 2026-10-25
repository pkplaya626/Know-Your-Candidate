"""Portraits of the people on the November ballot by the routes
``kyc/nominee_photos.py`` adds: Wikidata by the person's own FEC id, and the
state legislature's own page for a sitting member of it (rule 24, the owner's
decision of 2026-10-19).

Standard library only, no network:

    python -m unittest tests.test_nominee_photos -v
"""

import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import nominee_photos, photos, portraits, validate  # noqa: E402

JPEG = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xc0\x00\x11\x08" + (440).to_bytes(2, "big") + (330).to_bytes(2, "big")
        + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\x00" * 64)


def jpeg(width, height):
    return (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
            + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\x00" * 64)


def nominee(**extra):
    profile = {"id": "FEC_H6TX01352", "name": "Yolanda Rena Prince", "isCandidate": True,
               "source": "fec-field", "raceStatus": "nominee", "chamber": "House (Candidate)",
               "state": "TX", "districtNum": 1, "fecCandidateId": "H6TX01352",
               "photos": ["placeholder"]}
    profile.update(extra)
    return profile


def row(item="Q139698851", label="Yolanda Prince", image="Yolanda%20Prince.jpg", birth=None):
    return {"item": item, "label": label, "human": True, "birth": birth,
            "image": "http://commons.wikimedia.org/wiki/Special:FilePath/" + image if image else None}


INFO = {"width": 4266, "height": 5689, "descriptionurl":
        "https://commons.wikimedia.org/wiki/File:Yolanda_Prince.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/6/65/Yolanda_Prince.jpg",
        "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Yolanda_Prince.jpg/"
                    "330px-Yolanda_Prince.jpg?utm_source=commons.wikimedia.org",
        "extmetadata": {"LicenseShortName": {"value": "CC0"}, "Artist": {"value": "WikiBunny2K1"}}}


class Getter:
    """Answers by address: ``{url: (status, headers, body)}``."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def __call__(self, url, accept="*/*", limit=None):
        self.asked.append(url)
        status, headers, body = self.answers.get(url, (None, {}, b""))
        return status, url, headers, body


def image(body):
    return (200, {"Content-Type": "image/jpeg", "Content-Length": str(len(body))}, body)


class TestWikidataByFecId(unittest.TestCase):
    """An item carrying the person's own FEC candidate id (P1839)."""

    def test_the_one_item_with_the_id_gives_its_image(self):
        choice, why = nominee_photos.wikidata_choice(nominee(), [row()])
        self.assertEqual(choice, {"item": "Q139698851", "label": "Yolanda Prince",
                                  "file": "Yolanda Prince.jpg"})

    def test_an_item_naming_someone_else_or_two_items_or_another_birth_year_give_nothing(self):
        for rows, birthdate in (([row(label="Yolanda Adams")], ""),
                                ([row(), row(item="Q1")], ""),
                                ([row(birth="1961-01-01T00:00:00Z")], "1970-05-02"),
                                ([dict(row(), human=False)], ""),
                                ([row(image=None)], "")):
            choice, why = nominee_photos.wikidata_choice(nominee(birthdate=birthdate), rows)
            self.assertIsNone(choice, rows)
            self.assertTrue(why)

    def test_resolved_at_a_standard_width_with_its_licence_and_evidence(self):
        cache = {}
        thumb = INFO["thumburl"].split("?")[0]
        getter = Getter({thumb: image(JPEG)})
        nominee_photos.resolve_all([nominee()], cache, sparql=lambda q: [],
                                   api=lambda params, endpoint: {}, getter=getter,
                                   log=lambda *a: None)
        self.assertEqual(cache, {})                    # no item: nothing
        with unittest.mock.patch.object(nominee_photos, "wikidata_items",
                                        return_value={"H6TX01352": [row()]}), \
                unittest.mock.patch.object(nominee_photos, "commons_file", return_value=INFO):
            counts = nominee_photos.resolve_all([nominee()], cache, getter=getter,
                                                log=lambda *a: None)
        self.assertEqual(counts["wikidata"], 1)
        record = cache[portraits.profile_key(nominee())]
        self.assertEqual(record["url"], thumb)         # no tracking query, 330px
        self.assertEqual(record["via"], "wikidata-fec")
        self.assertEqual((record["bytes"], record["shownWidth"], record["shownHeight"]),
                         (len(JPEG), 330, 440))
        self.assertIn("H6TX01352 (P1839)", record["evidence"])
        self.assertEqual(record["page"], "https://www.wikidata.org/wiki/Q139698851")
        self.assertEqual(record["credit"]["licence"], "CC0")
        self.assertTrue(all("Special:FilePath" not in u for _, u in record["set"]))
        self.assertTrue(portraits.route_ok(nominee(), record))
        # Another person's FEC id, or a renamed profile, does not carry it.
        self.assertFalse(portraits.route_ok(nominee(fecCandidateId="H6TX09999"), record))
        self.assertFalse(portraits.route_ok(nominee(name="Jane Doe"), record))
        profile = nominee()
        portraits.apply_cache([profile], cache)
        self.assertEqual(profile["photoSource"], "wikidata-fec")
        self.assertEqual(profile["photos"][0], thumb)
        self.assertEqual(profile["photoCredit"]["licence"], "CC0")
        self.assertEqual(validate.check_photo_sets([profile]), [])

    def test_an_image_offered_only_oversized_is_left_out_and_counted(self):
        cache = {}
        thumb = INFO["thumburl"].split("?")[0]
        heavy = jpeg(330, 440) + b"\x00" * 400_000
        with unittest.mock.patch.object(nominee_photos, "wikidata_items",
                                        return_value={"H6TX01352": [row()]}), \
                unittest.mock.patch.object(nominee_photos, "commons_file", return_value=INFO):
            counts = nominee_photos.resolve_all([nominee()], cache,
                                                getter=Getter({thumb: image(heavy)}),
                                                log=lambda *a: None)
        self.assertEqual(counts["leftOut"], 1)
        record = cache[portraits.profile_key(nominee())]
        self.assertIsNone(record["url"])
        self.assertIn("over 300 KB", record["leftOut"]["why"])
        profile = nominee()
        portraits.apply_cache([profile], cache)
        self.assertEqual(profile["photos"], ["placeholder"])
        self.assertEqual(nominee_photos.left_out([profile], cache), 1)

    def test_a_failed_read_keeps_the_last_good_record(self):
        good = {"via": "wikidata-fec", "url": "https://upload.wikimedia.org/x.jpg", "name": "Y"}
        cache = {portraits.profile_key(nominee()): dict(good)}

        def broken(query):
            raise RuntimeError("503")
        nominee_photos.resolve_all([nominee()], cache, sparql=broken, log=lambda *a: None)
        self.assertEqual(cache[portraits.profile_key(nominee())], good)


HISTORY = {"people": {"FEC_H6NM03083": {
    "asked": "Martin R. Zamora", "wikipedia": "Martin R. Zamora", "offices": [
        {"office": "Member of the New Mexico House of Representatives", "open": True,
         "where": "New Mexico", "agree": "year-off"}]}}}
ROSTER = {"states": {"NM": [
    {"id": "ocd-person/zamora", "name": "Martin Zamora", "chamber": "lower", "district": "63",
     "state": "NM", "image": "https://www.nmlegis.gov/Images/Legislators/House/HZAMO.jpg",
     "links": ["https://www.nmlegis.gov/Members/Legislator?SponCode=HZAMO"]},
    {"id": "ocd-person/other", "name": "Ana Garcia", "chamber": "lower", "district": "62",
     "state": "NM", "links": ["https://www.nmlegis.gov/Members/Legislator?SponCode=HGARC"]}]}}
PAGE = ("<html><head><title>Representative Martin R. Zamora</title></head><body>"
        "<h1>Representative Martin R. Zamora (R)</h1>"
        '<img src="../Images/seal.png" alt="New Mexico Legislature seal">'
        '<img src="../Images/Legislators/House/HZAMO.jpg" alt="Zamora">'
        "<p>District 63, Clovis</p></body></html>")
PAGE_URL = "https://www.nmlegis.gov/Members/Legislator?SponCode=HZAMO"
IMAGE_URL = "https://www.nmlegis.gov/Images/Legislators/House/HZAMO.jpg"


def zamora(**extra):
    return nominee(id="FEC_H6NM03083", name="Martin R Zamora", state="NM",
                   fecCandidateId="H6NM03083", wikipedia="Martin R. Zamora",
                   wikipediaVia="election-page", **extra)


class TestStateLegislature(unittest.TestCase):
    """A nominee who sits in their state's legislature, by the record of
    offices their own article gives and the legislature's roster."""

    def resolve(self, page=PAGE, body=None, history=HISTORY, roster=ROSTER):
        cache = {}
        getter = Getter({PAGE_URL: (200, {"Content-Type": "text/html"}, page.encode()),
                         IMAGE_URL: image(body or jpeg(300, 375))})
        with unittest.mock.patch.object(nominee_photos, "wikidata_items", return_value={}):
            counts = nominee_photos.resolve_all([zamora()], cache, history=history,
                                                legislators=roster, getter=getter,
                                                log=lambda *a: None)
        return cache.get(portraits.profile_key(zamora())), counts

    def test_the_legislatures_own_photograph_of_its_member(self):
        record, counts = self.resolve()
        self.assertEqual(counts["legislature"], 1)
        self.assertEqual(record["url"], IMAGE_URL)
        self.assertEqual(record["page"], PAGE_URL)
        self.assertIn('alt text "Zamora"', record["evidence"])
        self.assertEqual((record["width"], record["height"]), (300, 375))
        self.assertEqual(record["credit"], {"by": "New Mexico Legislature", "page": PAGE_URL})
        profile = zamora()
        portraits.apply_cache([profile], {portraits.profile_key(profile): record},
                              legislators=ROSTER)
        self.assertEqual(profile["photoSource"], "state-legislature")
        self.assertEqual(profile["photoCredit"]["by"], "New Mexico Legislature")
        self.assertEqual(validate.check_photo_evidence(
            [profile], {portraits.profile_key(profile): record}), [])

    def test_a_page_whose_image_names_someone_else_gives_nothing(self):
        other = PAGE.replace('src="../Images/Legislators/House/HZAMO.jpg" alt="Zamora"',
                             'src="../Images/Legislators/House/HGARC.jpg" alt="Garcia"')
        roster = {"states": {"NM": [dict(ROSTER["states"]["NM"][0], image=None),
                                    ROSTER["states"]["NM"][1]]}}
        record, counts = self.resolve(page=other, roster=roster)
        self.assertIsNone(record)
        self.assertEqual(counts["legislature"], 0)
        url, why = nominee_photos.image_on_page(PAGE.replace("Zamora", "Garcia"), PAGE_URL,
                                                "Martin Zamora", IMAGE_URL)
        self.assertIsNone(url)
        self.assertEqual(why, "the page does not name them")

    def test_no_corroborated_seat_or_two_of_the_name_give_nothing(self):
        bare = {"people": {"FEC_H6NM03083": dict(HISTORY["people"]["FEC_H6NM03083"],
                                                 offices=[])}}
        self.assertIsNone(self.resolve(history=bare)[0])
        twin = {"states": {"NM": ROSTER["states"]["NM"] + [
            dict(ROSTER["states"]["NM"][0], id="ocd-person/twin", district="7")]}}
        member, why = nominee_photos.legislator_for(zamora(), HISTORY, twin)
        self.assertIsNone(member)
        # A name in another state is never theirs (rule 3).
        elsewhere = {"states": {"AZ": [dict(ROSTER["states"]["NM"][0], state="AZ")]}}
        self.assertIsNone(nominee_photos.legislator_for(zamora(), HISTORY, elsewhere)[0])

    def test_a_photograph_offered_only_oversized_is_left_out(self):
        record, counts = self.resolve(body=jpeg(2964, 2964) + b"\x00" * 3_900_000)
        self.assertIsNone(record["url"])
        self.assertEqual(counts["leftOut"], 1)
        self.assertIn("over 300 KB", record["leftOut"]["why"])

    def test_withheld_once_the_roster_seats_someone_else(self):
        record, _ = self.resolve()
        moved = {"states": {"NM": [dict(ROSTER["states"]["NM"][0], id="ocd-person/new",
                                        name="Pat Lee")]}}
        profile = zamora()
        portraits.apply_cache([profile], {portraits.profile_key(profile): record},
                              legislators=moved)
        self.assertEqual(profile["photos"], ["placeholder"])
        self.assertIsNone(profile["photoSource"])

    def test_a_record_without_its_evidence_fails_validate(self):
        record, _ = self.resolve()
        profile = zamora()
        bare = {portraits.profile_key(profile): dict(record, evidence=None)}
        # Not shown at all: route_ok refuses a record with no evidence.
        self.assertFalse(portraits.route_ok(profile, bare[portraits.profile_key(profile)]))
        profile.update(photoSource="state-legislature", photos=[record["url"]])
        issues = validate.check_photo_evidence([profile], bare)
        self.assertEqual([i.code for i in issues], ["photo-unevidenced"])

    def test_chambers_are_read_from_the_office_and_nebraska_is_not_guessed(self):
        self.assertEqual(nominee_photos.chamber_of("Member of the State Senate of Missouri"),
                         "upper")
        self.assertEqual(nominee_photos.chamber_of("Member of the Virginia House of Delegates"),
                         "lower")
        self.assertIsNone(nominee_photos.chamber_of("Member of the Nebraska Legislature"))


class TestRoutesByName(unittest.TestCase):
    def test_a_cached_portrait_from_any_other_route_is_still_refused(self):
        for via in ("wikipedia-search", "voters-guide", "guessed"):
            self.assertFalse(portraits.route_ok(nominee(), {"via": via, "url": "https://x/y.jpg"}))
        self.assertEqual(set(nominee_photos.ROUTES), {"wikidata-fec", "state-legislature"})

    def test_the_election_offices_that_offer_no_file_are_said_why(self):
        for code in ("WA", "AK", "OR"):
            self.assertIn(code, nominee_photos.ELECTION_OFFICES)

    def test_both_routes_keep_their_credit(self):
        for via, credit in (("state-legislature", {"by": "New Mexico Legislature"}),
                            ("wikidata-fec", {"by": "A", "licence": "CC0"})):
            profile = nominee(photoSource=via, photos=["https://x.example/y.jpg"],
                              photoCredit=credit)
            self.assertEqual(photos.assign_credits([profile]), 1)
            self.assertEqual(profile["photoCredit"], credit)


if __name__ == "__main__":
    unittest.main()
