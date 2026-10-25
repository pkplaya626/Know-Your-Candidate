"""Portraits of the people on the November ballot by the routes
``kyc/nominee_photos.py`` adds: Wikidata by the person's own FEC id, and the
state legislature's photograph of a sitting member of it (rule 24).

Standard library only, no network:

    python -m unittest tests.test_nominee_photos -v
"""

import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import legislature, nominee_photos, overrides, photos, portraits, validate  # noqa: E402


def jpeg(width, height):
    return (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
            + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\x00" * 64)


JPEG = jpeg(330, 440)
ELECTION = "2026 Texas's 1st congressional district election"


def nominee(**extra):
    profile = {"id": "FEC_H6TX01352", "name": "Yolanda Rena Prince", "isCandidate": True,
               "source": "fec-field", "raceStatus": "nominee", "chamber": "House (Candidate)",
               "state": "TX", "districtNum": 1, "fecCandidateId": "H6TX01352",
               "photos": ["placeholder"]}
    profile.update(extra)
    return profile


def row(item="Q139698851", label="Yolanda Prince", image="Yolanda%20Prince.jpg", birth=None,
        election=ELECTION, website=None, office=None, district=None, article=None):
    return {"item": item, "label": label, "human": True, "birth": birth,
            "election": election, "website": website, "office": office,
            "district": district, "article": article,
            "image": "http://commons.wikimedia.org/wiki/Special:FilePath/" + image if image else None}


INFO = {"width": 4266, "height": 5689, "descriptionurl":
        "https://commons.wikimedia.org/wiki/File:Yolanda_Prince.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/6/65/Yolanda_Prince.jpg",
        "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Yolanda_Prince.jpg/"
                    "330px-Yolanda_Prince.jpg?utm_source=commons.wikimedia.org",
        "extmetadata": {"LicenseShortName": {"value": "CC0"}, "Artist": {"value": "WikiBunny2K1"}}}
THUMB = INFO["thumburl"].split("?")[0]


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


def resolve_wikidata(cache, rows=None, getter=None, profile=None):
    with unittest.mock.patch.object(nominee_photos, "wikidata_items",
                                    return_value={"H6TX01352": rows or [row()]}), \
            unittest.mock.patch.object(nominee_photos, "commons_file", return_value=INFO):
        return nominee_photos.resolve_all([profile or nominee()], cache,
                                          getter=getter or Getter({THUMB: image(JPEG)}),
                                          log=lambda *a: None)


class TestWikidataByFecId(unittest.TestCase):
    """An item carrying the person's own FEC candidate id (P1839), and a
    second tie of its own (rule 82: an id is not proof on its own)."""

    def test_the_one_item_with_the_id_gives_its_image(self):
        choice, why = nominee_photos.wikidata_choice(nominee(), [row()])
        self.assertEqual(choice, {"item": "Q139698851", "label": "Yolanda Prince",
                                  "file": "Yolanda Prince.jpg",
                                  "tie": f'its candidacy in election (P3602) is "{ELECTION}"'})

    def test_an_item_naming_someone_else_or_two_items_or_another_birth_year_give_nothing(self):
        for rows, birthdate in (([row(label="Yolanda Adams")], ""),
                                ([row(), row(item="Q1")], ""),
                                ([row(birth="1961-01-01T00:00:00Z")], "1970-05-02"),
                                ([dict(row(), human=False)], ""),
                                ([row(image=None)], "")):
            choice, why = nominee_photos.wikidata_choice(nominee(birthdate=birthdate), rows)
            self.assertIsNone(choice, rows)
            self.assertTrue(why)

    def test_a_namesake_with_another_given_name_gives_nothing(self):
        """The reviewers' probe: "Robert Williams" carrying John Andrew
        Williams's FEC id passed on the surname alone, and none of the
        three nominees pictured had a birth date to compare. The label must
        carry a given name as the profile or the filing writes it - no
        nickname table, no prefix - and a nickname only by an evidenced
        entry."""
        drew = nominee(id="FEC_H6KY01169", name="John Andrew Williams", state="KY",
                       filedName="WILLIAMS, JOHN ANDREW", birthdate="No data")
        ky = "2026 United States House of Representatives elections in Kentucky"
        for label, fits in (('John "Drew" Williams', True), ("J. Andrew Williams", True),
                            ("John Williams", True), ("Andrew Williams", True),
                            ("Drew Williams", False), ("Jo Williams", False),
                            ("Jack Williams", False), ("Robert Williams", False),
                            ("Robert Andrew Williams", False), ("Williams", False),
                            ("John Andrews", False)):
            choice, why = nominee_photos.wikidata_choice(drew, [row(label=label, election=ky)])
            self.assertEqual(bool(choice), fits, (label, why))
            if not fits:
                self.assertIn("label", why)
        # A nickname the item uses stands only by an evidenced entry naming
        # that very label for this profile.
        entry = {"FEC_H6KY01169": {"label": "Drew Williams", "evidence": "his campaign's site "
                                   "calls him Drew (read 2026-10-25)"}}
        with unittest.mock.patch.dict(overrides.PORTRAIT_NAME_FORMS, entry):
            choice, _ = nominee_photos.wikidata_choice(drew, [row(label="Drew Williams", election=ky)])
            self.assertTrue(choice)
            choice, _ = nominee_photos.wikidata_choice(
                nominee(name="Drew Smith Williams", state="KY", id="FEC_H6KY09999"),
                [row(label="Robert Williams", election=ky)])
            self.assertIsNone(choice)
        # The filing's own given names count: a profile written "Bob Smith"
        # filed as "SMITH, ROBERT" is the item "Robert Smith", and the
        # reverse; a prefix ("Rob") is not.
        bob = nominee(name="Bob Smith", filedName="SMITH, ROBERT", state="TX")
        for label, fits in (("Robert Smith", True), ("Bob Smith", True), ("Rob Smith", False),
                            ("Robert Smithers", False), ("Bob Smith Jr.", True)):
            choice, why = nominee_photos.wikidata_choice(bob, [row(label=label)])
            self.assertEqual(bool(choice), fits, (label, why))
        # A double surname the filing writes: either word ends the label.
        vgn = nominee(name="Valentina Gomez Noriega", filedName="GOMEZ NORIEGA, VALENTINA")
        for label, fits in (("Valentina Gomez", True), ("Valentina Gomez Noriega", True),
                            ("Valentina Noriega", True), ("Valentina Garcia", False)):
            choice, why = nominee_photos.wikidata_choice(vgn, [row(label=label)])
            self.assertEqual(bool(choice), fits, (label, why))

    def test_a_bot_added_id_on_a_namesake_with_no_tie_gives_nothing(self):
        """A crafted case: an item labelled with the person's very name that
        carries their FEC id - as a bot adds one - and nothing else of
        theirs, no birth year to compare (the profile has none), a 2024
        candidacy, an office in another state, someone else's website and
        another article, is not taken: the id is not proof on its own
        (rule 82), and neither is a name."""
        profile = nominee(birthdate="No data", campaignSite="https://prince4congress.com",
                          wikipedia="Yolanda Prince", wikipediaVia="election-page")
        rows = [row(election="2024 Texas's 1st congressional district election",
                    office="member of the Louisiana House of Representatives",
                    website="https://yolandaprince-art.example/",
                    article="Yolanda Prince (artist)")]
        choice, why = nominee_photos.wikidata_choice(profile, rows)
        self.assertIsNone(choice)
        self.assertIn("nothing on the item but the id", why)
        # Through resolve_all, it leaves no record.
        cache = {}
        resolve_wikidata(cache, rows=rows, profile=profile)
        self.assertEqual(cache, {})

    def test_an_office_for_their_state_or_the_article_their_ballot_links_is_a_tie(self):
        choice, _ = nominee_photos.wikidata_choice(
            nominee(), [row(election=None, office="member of the Texas House of Representatives")])
        self.assertIn("office for Texas", choice["tie"])
        choice, _ = nominee_photos.wikidata_choice(
            nominee(), [row(election=None, office="United States representative",
                            district="Texas's 1st congressional district")])
        self.assertIn("Texas's 1st congressional district", choice["tie"])
        linked = nominee(wikipedia="Yolanda Prince", wikipediaVia="election-page")
        choice, _ = nominee_photos.wikidata_choice(
            linked, [row(election=None, article="Yolanda Prince")])
        self.assertIn("ballot page links", choice["tie"])
        # An article the profile holds by any other way is no tie.
        choice, _ = nominee_photos.wikidata_choice(
            nominee(wikipedia="Yolanda Prince"), [row(election=None, article="Yolanda Prince")])
        self.assertIsNone(choice)
        self.assertEqual(nominee_photos._article_title(
            "https://en.wikipedia.org/wiki/Fred_Wellman"), "Fred Wellman")

    def test_a_place_named_after_a_state_is_no_tie_to_it(self):
        """The verifier of PR #134 crafted these: a namesake's item with a
        bot-added id and no year of birth, whose office or election names
        the state's word for a city, a country, D.C. or another state's
        town, was taken as tied to the state. A tie is a label of a whole
        shape with the state in its slot (rule 5)."""
        probes = (
            ("KS", dict(office="Mayor of Kansas City, Missouri")),
            ("MO", dict(office="Mayor of Kansas City, Missouri")),
            ("GA", dict(office="United States Ambassador to Georgia")),
            ("GA", dict(office="member of the Parliament of Georgia")),
            ("WA", dict(office="member of the Council of the District of Columbia",
                        district="Washington, D.C.")),
            ("WA", dict(office="member of the Washington House of Representatives",
                        district="Washington, D.C.")),
            ("IN", dict(office="Mayor of Indiana, Pennsylvania")),
            ("NY", dict(election="2026 New York City Council election")),
            ("IA", dict(office="Mayor of Iowa City")),
            ("VA", dict(office="member of the West Virginia Senate")),
            ("VA", dict(office="Mayor of Virginia Beach")),
            ("TX", dict(office="United States representative",
                        district="Oklahoma's 1st congressional district")),
            ("MO", dict(election="2026 Missouri gubernatorial election")),
        )
        for state, extra in probes:
            extra.setdefault("election", None)
            profile = nominee(state=state, name="John Williams", filedName="WILLIAMS, JOHN",
                              birthdate="No data")
            choice, why = nominee_photos.wikidata_choice(
                profile, [row(label="John Williams", **extra)])
            self.assertIsNone(choice, (state, extra))
            self.assertIn("nothing on the item but the id", why)
        # The shapes the state's own offices and races take still tie.
        for state, extra in (
                ("KS", dict(office="member of the Kansas House of Representatives")),
                ("MO", dict(office="Missouri State Senate")),
                ("GA", dict(office="Secretary of State of Georgia")),
                ("GA", dict(office="United States senator", district="Georgia")),
                ("WA", dict(office="Washington State Treasurer")),
                ("NY", dict(office="United States representative",
                            district="New York's 12th congressional district")),
                ("AK", dict(office="United States representative",
                            district="Alaska's at-large congressional district")),
                ("NY", dict(election="2026 United States House of Representatives "
                                     "elections in New York")),
                ("OH", dict(election="2026 United States Senate special election in Ohio")),
                ("TX", dict(election=ELECTION))):
            extra.setdefault("election", None)
            profile = nominee(state=state, name="John Williams", filedName="WILLIAMS, JOHN",
                              birthdate="No data")
            choice, why = nominee_photos.wikidata_choice(
                profile, [row(label="John Williams", **extra)])
            self.assertTrue(choice, (state, extra, why))

    def test_an_item_with_nothing_but_the_id_gives_nothing(self):
        for rows in ([row(election=None)],
                     [row(election="2024 Texas's 1st congressional district election")],
                     [row(election="2026 United States House of Representatives elections in "
                                   "Oklahoma")]):
            choice, why = nominee_photos.wikidata_choice(nominee(), rows)
            self.assertIsNone(choice, rows)
            self.assertIn("nothing on the item but the id", why)
        # West Virginia is not Virginia (rule 5).
        choice, _ = nominee_photos.wikidata_choice(
            nominee(state="VA"),
            [row(election="2026 United States House of Representatives elections in "
                          "West Virginia")])
        self.assertIsNone(choice)
        # A year of birth the profile's agrees with, or the campaign's own
        # site as the item's official website, is a tie.
        choice, _ = nominee_photos.wikidata_choice(
            nominee(birthdate="1970-05-02"), [row(election=None, birth="1970-05-02T00:00:00Z")])
        self.assertIn("year of birth", choice["tie"])
        choice, _ = nominee_photos.wikidata_choice(
            nominee(campaignSite="https://www.prince4congress.com"),
            [row(election=None, website="https://prince4congress.com/")])
        self.assertIn("official website", choice["tie"])

    def test_every_one_of_the_persons_ids_is_asked_and_two_items_refused(self):
        profile = nominee(otherFecIds=["H6TX01999"])
        cache = {}
        items = {"H6TX01352": [row(image=None)], "H6TX01999": [row()]}
        with unittest.mock.patch.object(nominee_photos, "wikidata_items", return_value=items), \
                unittest.mock.patch.object(nominee_photos, "commons_file", return_value=INFO):
            nominee_photos.resolve_all([profile], cache, getter=Getter({THUMB: image(JPEG)}),
                                       log=lambda *a: None)
        record = cache[portraits.profile_key(profile)]
        self.assertEqual(record["url"], THUMB)      # the first id's row had no image
        self.assertIn(record["fec"], ("H6TX01352", "H6TX01999"))
        # The person's ids on two items: one of them is someone else's (rule 25).
        cache = {}
        items = {"H6TX01352": [row()], "H6TX01999": [row(item="Q2")]}
        with unittest.mock.patch.object(nominee_photos, "wikidata_items", return_value=items), \
                unittest.mock.patch.object(nominee_photos, "commons_file", return_value=INFO):
            nominee_photos.resolve_all([profile], cache, getter=Getter({THUMB: image(JPEG)}),
                                       log=lambda *a: None)
        self.assertEqual(cache, {})

    def test_resolved_at_a_standard_width_with_its_licence_and_evidence(self):
        cache = {}
        nominee_photos.resolve_all([nominee()], cache, sparql=lambda q: [],
                                   api=lambda params, endpoint: {},
                                   getter=Getter({THUMB: image(JPEG)}), log=lambda *a: None)
        self.assertEqual(cache, {})                    # no item: nothing
        counts = resolve_wikidata(cache)
        self.assertEqual(counts["wikidata"], 1)
        record = cache[portraits.profile_key(nominee())]
        self.assertEqual(record["url"], THUMB)         # no tracking query, 330px
        self.assertEqual(record["via"], "wikidata-fec")
        self.assertEqual((record["bytes"], record["shownWidth"], record["shownHeight"]),
                         (len(JPEG), 330, 440))
        self.assertIn("H6TX01352 (P1839)", record["evidence"])
        self.assertIn(ELECTION, record["evidence"])    # the second tie, said
        self.assertEqual(record["original"], INFO["url"])
        self.assertEqual(record["page"], "https://www.wikidata.org/wiki/Q139698851")
        self.assertEqual(record["credit"]["licence"], "CC0")
        self.assertTrue(all("Special:FilePath" not in u for _, u in record["set"]))
        self.assertTrue(portraits.route_ok(nominee(), record))
        # Another person's FEC id, or a renamed profile, does not carry it;
        # nor a record from before the second tie was asked.
        self.assertFalse(portraits.route_ok(nominee(fecCandidateId="H6TX09999"), record))
        self.assertFalse(portraits.route_ok(nominee(name="Jane Doe"), record))
        self.assertFalse(portraits.route_ok(nominee(name="Rena Prince"), dict(
            record, label="Robert Prince")))
        self.assertFalse(portraits.route_ok(nominee(), dict(record, label="Yo Prince")))
        self.assertFalse(portraits.route_ok(nominee(), dict(record, tie=None)))
        profile = nominee()
        portraits.apply_cache([profile], cache)
        self.assertEqual(profile["photoSource"], "wikidata-fec")
        self.assertEqual(profile["photos"][0], THUMB)
        self.assertEqual(profile["photoCredit"]["licence"], "CC0")
        self.assertEqual(validate.check_photo_sets([profile]), [])

    def test_a_file_a_person_refused_or_a_wide_frame_is_not_shown(self):
        """No override reached these routes in the first version (the
        reviewers): NOT_A_PORTRAIT and PORTRAIT_LICENCE_DOUBTS now do."""
        cache = {}
        resolve_wikidata(cache)
        record = cache[portraits.profile_key(nominee())]
        for table in ("NOT_A_PORTRAIT", "PORTRAIT_LICENCE_DOUBTS"):
            with unittest.mock.patch.dict(getattr(overrides, table),
                                          {INFO["url"]: ("2026-10-25", "a crowd")}):
                self.assertFalse(portraits.route_ok(nominee(), record), table)
                again = {}
                resolve_wikidata(again)
                self.assertEqual(again, {}, table)
        wide = {}
        resolve_wikidata(wide, getter=Getter({THUMB: image(jpeg(330, 220))}))
        self.assertEqual(wide, {})

    def test_the_srcset_offers_its_widest_size_only_once_weighed_within_the_caps(self):
        wide = THUMB.replace("/330px-", "/500px-")
        for answer, offered in ((image(jpeg(500, 667)), True),
                                (image(jpeg(500, 667) + b"\x00" * 400_000), False),
                                ((None, {}, b""), False)):
            cache = {}
            resolve_wikidata(cache, getter=Getter({THUMB: image(JPEG), wide: answer}))
            record = cache[portraits.profile_key(nominee())]
            self.assertEqual(record["url"], THUMB)
            self.assertEqual(wide in [u for _, u in record["set"]], offered, answer[0])
            self.assertEqual(max(w for w, _ in record["set"]), 500 if offered else 330)

    def test_a_file_gone_takes_the_record_away(self):
        key = portraits.profile_key(nominee())
        cache = {key: {"via": "wikidata-fec", "url": "https://example.org/x.jpg"}}
        resolve_wikidata(cache, getter=Getter({THUMB: (404, {}, b"")}))
        self.assertIsNone(cache[key]["url"])

    def test_a_heavy_image_is_shown_and_said(self):
        """Never the silhouette for its weight (rule 87, the owner's
        decision of 2026-10-25)."""
        cache = {}
        heavy = jpeg(330, 440) + b"\x00" * 400_000
        counts = resolve_wikidata(cache, getter=Getter({THUMB: image(heavy)}))
        self.assertEqual(counts["heavy"], 1)
        record = cache[portraits.profile_key(nominee())]
        self.assertEqual(record["url"], THUMB)
        self.assertIn("over 300 KB", record["heavy"])
        profile = nominee()
        portraits.apply_cache([profile], cache)
        self.assertEqual(profile["photos"][0], THUMB)
        self.assertEqual(nominee_photos.heavy_shown([profile], cache), 1)
        self.assertEqual(nominee_photos.problems(cache), [])
        self.assertEqual(len(nominee_photos.problems({"k": dict(record, heavy=None)})), 1)

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
PAGE_URL = "https://www.nmlegis.gov/Members/Legislator?SponCode=HZAMO"
IMAGE_URL = "https://www.nmlegis.gov/Images/Legislators/House/HZAMO.jpg"
ZAMORA = {"id": "ocd-person/zamora", "name": "Martin Zamora", "chamber": "lower",
          "district": "63", "state": "NM", "image": IMAGE_URL, "links": [PAGE_URL]}
ROSTER = {"fetched": "2026-10-24T12:00:00+00:00", "states": {"NM": [
    ZAMORA,
    {"id": "ocd-person/other", "name": "Ana Garcia", "chamber": "lower", "district": "62",
     "state": "NM", "links": ["https://www.nmlegis.gov/Members/Legislator?SponCode=HGARC"]}]}}


def zamora(**extra):
    return nominee(id="FEC_H6NM03083", name="Martin R Zamora", state="NM",
                   fecCandidateId="H6NM03083", wikipedia="Martin R. Zamora",
                   wikipediaVia="election-page", **extra)


def roster_with(**member):
    return {"fetched": ROSTER["fetched"],
            "states": {"NM": [dict(ZAMORA, **member)] + ROSTER["states"]["NM"][1:]}}


class TestStateLegislature(unittest.TestCase):
    """A nominee who sits in their state's legislature, by the record of
    offices their own article gives and the legislature's roster: shown the
    photograph this site's legislature page shows on their card."""

    def resolve(self, body=None, history=HISTORY, roster=ROSTER, photos=None, url=IMAGE_URL):
        cache = {}
        getter = Getter({url: image(body or jpeg(300, 375))})
        with unittest.mock.patch.object(nominee_photos, "wikidata_items", return_value={}):
            counts = nominee_photos.resolve_all([zamora()], cache, history=history,
                                                legislators=roster, getter=getter,
                                                legislator_photos=photos, log=lambda *a: None)
        self.assertNotIn(PAGE_URL, getter.asked)       # the card's choice, never a re-read page
        return cache.get(portraits.profile_key(zamora())), counts

    def test_the_legislatures_own_photograph_of_its_member(self):
        record, counts = self.resolve()
        self.assertEqual(counts["legislature"], 1)
        self.assertEqual(record["url"], IMAGE_URL)
        self.assertEqual(record["page"], PAGE_URL)
        self.assertEqual(record["evidence"], "the file Open States lists for Martin Zamora "
                                             "(ocd-person/zamora), served by the New Mexico "
                                             "Legislature")
        self.assertEqual((record["width"], record["height"]), (300, 375))
        self.assertEqual(record["credit"], {"by": "New Mexico Legislature", "page": PAGE_URL})
        # The very photograph the legislature page's card shows (rule 12).
        card = legislature.card_photo(ZAMORA, "NM", {"kind": "member", "url": PAGE_URL})
        self.assertEqual((card["image"], card["imageCredit"]), (record["url"], record["credit"]))
        profile = zamora()
        portraits.apply_cache([profile], {portraits.profile_key(profile): record},
                              legislators=ROSTER, legislator_photos={"people": {}})
        self.assertEqual(profile["photoSource"], "state-legislature")
        self.assertEqual(profile["photoCredit"]["by"], "New Mexico Legislature")
        self.assertEqual(validate.check_photo_evidence(
            [profile], {portraits.profile_key(profile): record}), [])

    def test_the_legislatures_own_record_where_open_states_has_none(self):
        own = "https://www.nmlegis.gov/Images/Legislators/House/HZAMO-2025.jpg"
        photos_cache = {"people": {"ocd-person/zamora": {
            "image": own, "credit": "New Mexico Legislature", "page": PAGE_URL,
            "evidence": 'alt text "Representative Martin R. Zamora"', "read": "2026-10-19",
            "chamber": "lower", "district": "63"}}}
        record, _ = self.resolve(roster=roster_with(image=None), photos=photos_cache, url=own)
        self.assertEqual(record["url"], own)
        self.assertIn('alt text "Representative Martin R. Zamora"', record["evidence"])
        profile = zamora()
        cache = {portraits.profile_key(profile): record}
        self.assertTrue(portraits.route_ok(profile, record, roster_with(image=None), photos_cache))
        # Once the card shows another file, the nominee is not shown this one.
        moved = {"people": {"ocd-person/zamora": dict(photos_cache["people"]["ocd-person/zamora"],
                                                      image=own + "?v=2")}}
        portraits.apply_cache([profile], cache, legislators=roster_with(image=None),
                              legislator_photos=moved)
        self.assertEqual(profile["photos"], ["placeholder"])

    def test_a_file_the_card_does_not_show_or_off_the_legislatures_host_gives_nothing(self):
        for member in ({"image": None},                                   # nothing listed
                       {"imageShared": True},                             # another member's too
                       {"image": "https://senatedems.example/zamora.jpg"},  # a caucus's host
                       {"image": "https://www.bing.com/th?id=OIP.zamora"}):  # a search's
            record, counts = self.resolve(roster=roster_with(**member),
                                          url=member.get("image") or IMAGE_URL)
            self.assertIsNone(record, member)
            self.assertEqual(counts["legislature"], 0)
        # An "oversized" legphotos entry's file was offered before the
        # checks a seat-keyed file needs (legphotos.settle), so it is not
        # yet known to be theirs: not shown, for that and not its weight.
        offered = "https://www.nmlegis.gov/Images/Legislators/House/district63.jpg"
        photos_cache = {"people": {"ocd-person/zamora": {
            "oversized": True, "offered": offered, "credit": "New Mexico Legislature",
            "page": PAGE_URL, "evidence": 'file "district63.jpg" named by the seat',
            "read": "2026-10-19", "chamber": "lower", "district": "63",
            "bytes": 1_900_000, "width": 1200, "height": 1500}}}
        record, counts = self.resolve(roster=roster_with(image=None), photos=photos_cache,
                                      url=offered)
        self.assertIsNone(record)
        self.assertEqual(counts["legislature"], 0)
        image, _credit, why = nominee_photos.card_photo(
            dict(ZAMORA, image=None), "NM", {"kind": "member", "url": PAGE_URL}, photos_cache)
        self.assertIsNone(image)
        self.assertIn("oversized", why)

    def test_a_wide_frame_or_a_refused_file_is_not_shown(self):
        record, _ = self.resolve(body=jpeg(600, 400))
        self.assertIsNone(record)
        record, _ = self.resolve()
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                      {IMAGE_URL: ("2026-10-25", "a group photograph")}):
            self.assertFalse(portraits.route_ok(zamora(), record, ROSTER))
            self.assertIsNone(self.resolve()[0])
        # A file named a headshot may be square or wider (rule 38).
        self.assertFalse(nominee_photos.wide_frame("https://x.gov/zamora-headshot.jpg",
                                                   {"width": 600, "height": 400}))

    def test_no_corroborated_seat_or_two_of_the_name_give_nothing(self):
        bare = {"people": {"FEC_H6NM03083": dict(HISTORY["people"]["FEC_H6NM03083"],
                                                 offices=[])}}
        self.assertIsNone(self.resolve(history=bare)[0])
        twin = {"states": {"NM": ROSTER["states"]["NM"] + [
            dict(ZAMORA, id="ocd-person/twin", district="7")]}}
        member, why = nominee_photos.legislator_for(zamora(), HISTORY, twin)
        self.assertIsNone(member)
        # A name in another state is never theirs (rule 3).
        elsewhere = {"states": {"AZ": [dict(ZAMORA, state="AZ")]}}
        self.assertIsNone(nominee_photos.legislator_for(zamora(), HISTORY, elsewhere)[0])

    def test_a_heavy_photograph_is_shown_and_said(self):
        """Nevada's 3.9 MB headshot of Carrie Buck was left out; it is
        shown, at full size where no resizer serves it smaller, and counted
        (rule 87)."""
        record, counts = self.resolve(body=jpeg(2964, 2964) + b"\x00" * 3_900_000)
        self.assertEqual(record["url"], IMAGE_URL)
        self.assertEqual(counts["heavy"], 1)
        self.assertIn("over 300 KB", record["heavy"])
        self.assertEqual(nominee_photos.problems({"k": record}), [])

    def test_a_heavy_photograph_is_shown_smaller_from_the_same_file(self):
        """Rule 87 for every route: Photon serves the card's very file
        scaled, and the record shows that, with the file the card shows kept
        as its original, so it still stands only while the card shows it."""
        photon = "https://i0.wp.com/www.nmlegis.gov/Images/Legislators/House/HZAMO.jpg?w=500&ssl=1"
        cache = {}
        getter = Getter({IMAGE_URL: image(jpeg(2964, 2964) + b"\x00" * 3_900_000),
                         photon: image(jpeg(500, 500))})
        with unittest.mock.patch.object(nominee_photos, "wikidata_items", return_value={}):
            nominee_photos.resolve_all([zamora()], cache, history=HISTORY, legislators=ROSTER,
                                       getter=getter, log=lambda *a: None)
        record = cache[portraits.profile_key(zamora())]
        self.assertEqual((record["url"], record["original"]), (photon, IMAGE_URL))
        self.assertEqual((record["width"], record["height"]), (500, 500))
        self.assertIn("shown smaller", record["heavy"])
        self.assertEqual(nominee_photos.problems({"k": record}), [])
        self.assertTrue(portraits.route_ok(zamora(), record, ROSTER, {"people": {}}))
        # A card that shows another file no longer carries it.
        self.assertFalse(portraits.route_ok(zamora(), record,
                                            roster_with(image=IMAGE_URL + "?v=2"),
                                            {"people": {}}))

    def test_withheld_once_the_roster_seats_someone_else(self):
        record, _ = self.resolve()
        moved = {"states": {"NM": [dict(ZAMORA, id="ocd-person/new", name="Pat Lee")]}}
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


class EveryRouteAsksBothLists(unittest.TestCase):
    """PRs #134 and #135 each built a check against NOT_A_PORTRAIT and
    PORTRAIT_LICENCE_DOUBTS; merged, every route asks the one test,
    ``photos.refused`` (rule 12), and a campaign site's reader asks both
    lists where it had asked one."""

    def test_one_test_for_every_route(self):
        from kyc import enrich, judge_links, official_photos

        page = "https://commons.wikimedia.org/wiki/File:Someone_Official.jpg"
        upload = judge_links.source_url(page)
        for table in ("NOT_A_PORTRAIT", "PORTRAIT_LICENCE_DOUBTS"):
            with unittest.mock.patch.dict(getattr(overrides, table),
                                          {upload: ("2026-10-25", "a crowd")}):
                why = photos.refused(upload)
                self.assertIn(table, why)
                self.assertEqual(nominee_photos.refused_file(None, upload), why)
                self.assertEqual(judge_links.held_back({"source": page}), why)
                self.assertEqual(official_photos.held_back(
                    {"photo": upload, "credit": {"page": page}}), why)
                self.assertIsNone(enrich.campaign_portrait({"portrait": upload}))
                self.assertIsNone(enrich.campaign_portrait(
                    {"portrait": "https://example.org/small.jpg",
                     "portraitHeavy": [{"url": upload}]}))
        self.assertEqual(photos.refused(upload, None), "")
        self.assertIsNone(judge_links.held_back({"source": page}))
        self.assertIsNone(official_photos.held_back({"photo": upload}))
        self.assertEqual(enrich.campaign_portrait({"portrait": upload}), upload)


if __name__ == "__main__":
    unittest.main()
