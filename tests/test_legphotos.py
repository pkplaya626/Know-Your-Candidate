"""Tests for the state legislators' portraits read from each legislature's
own records (kyc/legphotos.py) and how the legislature pages use them.

A photograph of the wrong person under a legislator's name looks entirely
normal, so every route is tested on the forms the legislatures serve, with a
page that names someone else refused, a seat's file that may be the
predecessor's withheld, and a file offered only over the caps left out.
"""

import datetime
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import legislature, legphotos  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
TODAY = "2026-10-19"


def png(width, height, size=4000):
    """Bytes a reader takes for a PNG of this size, *size* bytes long."""
    head = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    return head + b"\0" * max(0, size - len(head))


class FakeHttp:
    """Answers from a table: ``{url: (status, body, headers)}``; anything
    else is a failed connection."""

    def __init__(self, table):
        self.table = table
        self.asked = []

    def get(self, url, limit=None, browser=False):
        self.asked.append(url)
        if url not in self.table:
            return legphotos.Answer(None, {}, b"", url)
        status, body, headers = self.table[url]
        if isinstance(body, str):
            body = body.encode("utf-8")
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        truncated = limit is not None and len(body) > limit
        return legphotos.Answer(status, headers, body[:limit + 1] if truncated else body, url, truncated)


def image(width, height, size=4000, modified=None):
    headers = {"Content-Type": "image/png", "Content-Length": str(size)}
    if modified:
        headers["Last-Modified"] = modified
    return (200, png(width, height, size), headers)


def rec(name, chamber="lower", district="1", pid=None, **extra):
    return dict({"id": pid or f"ocd-person/{name.replace(' ', '-').lower()}", "name": name,
                 "chamber": chamber, "district": district, "party": "Democratic", "partyKey": "D"},
                **extra)


class TestNames(unittest.TestCase):

    def test_surnames_and_given_names(self):
        self.assertTrue(legphotos.names_surname("Reddington-Hughes, Karen", "Karen Reddington-Hughes"))
        self.assertTrue(legphotos.names_surname("OLaughlin18", "Cindy O'Laughlin"))
        self.assertFalse(legphotos.names_surname("Senator Black", "Rusty Blackwell"))
        self.assertTrue(legphotos.names_member("Representative Rob North", "Rob North"))
        self.assertTrue(legphotos.names_member("Deborah \"Debbie\" Dolgin", "Debbie Dolgin"))
        # A templated alt with only the surname does not name the member.
        self.assertFalse(legphotos.names_member("Representative Boyles Photo", "Nathan Boyles"))
        # An article or a possessive's "s" is no initial (the reviewers of
        # PR #125); an initial written as one is.
        self.assertFalse(legphotos.names_member("A photo of Representative Smith", "Andy Smith"))
        self.assertFalse(legphotos.names_member("Representative Smith's office", "Sarah Smith"))
        self.assertTrue(legphotos.names_member("Rep. A. Smith", "Andy Smith"))
        self.assertTrue(legphotos.names_member("Senator S Smith", "Sarah Smith"))

    def test_only_the_legislatures_hosts_and_never_a_party(self):
        self.assertTrue(legphotos.official_host("NJ", "https://pub.njleg.state.nj.us/x.jpg"))
        self.assertTrue(legphotos.official_host("OK", "https://dgbf0g52sf9l0.cloudfront.net/x.jpg"))
        self.assertFalse(legphotos.official_host("MI", "https://gophouse.org/x.jpg"))
        self.assertFalse(legphotos.official_host("IN", "https://www.indianahouserepublicans.com/x.jpg"))
        self.assertFalse(legphotos.official_host("NJ", "https://njleg.state.nj.us.evil.com/x.jpg"))
        # New Jersey's newer file host and Ohio's legislature site, which
        # the legislatures' own pages name (the PR #133 review).
        self.assertTrue(legphotos.official_host("NJ", "https://pub.njleg.gov/publications/members/x.jpg"))
        self.assertTrue(legphotos.official_host(
            "OH", "https://www.legislature.ohio.gov/assets/people/x/headshots/x.jpg"))
        self.assertFalse(legphotos.official_host("NJ", "https://pub.njleg.gov.evil.com/x.jpg"))

    def test_the_credit_is_the_legislatures_own_name(self):
        self.assertEqual(legphotos.legislature_name("MT"), "Montana Legislature")
        self.assertEqual(legphotos.legislature_name("CT"), "Connecticut General Assembly")

    def test_a_given_name_written_two_ways(self):
        # North Dakota's "TJ Brown" is T.J. Brown; its "Daniel R. Vollmer"
        # is Dan Vollmer.
        self.assertTrue(legphotos.names_member("TJ Brown", "T.J. Brown"))
        self.assertTrue(legphotos.names_member("Daniel R. Vollmer", "Dan Vollmer"))
        # Never a longer name that may be another of the family.
        self.assertFalse(legphotos.names_member("Danielle Vollmer", "Dan Vollmer"))
        self.assertFalse(legphotos.names_member("Pat Vollmer", "Dan Vollmer"))

    def test_a_name_written_in_full_in_the_text(self):
        self.assertTrue(legphotos.names_in_full("HOUSE DAVID NELSON. Representative David R. Nelson",
                                                "David Nelson"))
        self.assertFalse(legphotos.names_in_full("Rep. Nelson, with David Smith", "David Nelson"))

    def test_new_mexicos_sponsor_code_carries_the_chamber(self):
        # Five senators were linked to their House pages, headed "Former
        # Representative", and their House photographs taken from them.
        self.assertEqual(legislature.chamber_of(
            "NM", "https://www.nmlegis.gov/Members/Legislator?SponCode=HFIGU"), "lower")
        self.assertEqual(legislature.chamber_of(
            "NM", "https://www.nmlegis.gov/Members/Legislator?SponCode=SFIGU"), "upper")
        senator = rec("Natalie Figueroa", chamber="upper", district="18", links=[
            "https://www.nmlegis.gov/Members/Legislator?SponCode=HFIGU",
            "https://www.nmlegis.gov/Members/Legislator?SponCode=SFIGU"])
        page = legislature.page_for("NM", senator, 2026)
        self.assertEqual(page and page.get("url"), "https://www.nmlegis.gov/Members/Legislator?SponCode=SFIGU")


class TestRecipes(unittest.TestCase):

    def test_montana_joins_on_the_legislatures_ids_and_checks_the_seat(self):
        api = "https://www.legmt.gov/wp-json/legmt/v1/people/legislators"
        people = {"content": [
            {"id": 1331, "lawsId": 96, "firstName": "Neil", "lastName": "Duram", "chamber": "House",
             "district": "HOUSE DISTRICT 1", "isActive": True, "jobTitle": "Representative",
             "links": {"profileUrl": "https://legislators.legmt.gov/#/legislator/96"},
             "photo": {"sizes": {"avatar": "https://www.legmt.gov/a/1331-200x250.jpg",
                                 "lowres": "https://www.legmt.gov/a/1331-400x500.jpg"}}},
            # The lawsId Open States lists for Tezak is someone else's.
            {"id": 9, "lawsId": 1606, "firstName": "Other", "lastName": "Person", "chamber": "House",
             "district": "HOUSE DISTRICT 7", "isActive": True, "photo": {"sizes": {"avatar": "x"}}},
            {"id": 1277, "lawsId": 155, "firstName": "Tony", "lastName": "Tezak", "chamber": "House",
             "district": "HOUSE DISTRICT 2", "isActive": True, "jobTitle": "Representative",
             "photo": {"sizes": {"avatar": "https://www.legmt.gov/a/1277-200x250.jpg"}}},
        ]}
        http = FakeHttp({api: (200, people, {"Content-Type": "application/json"})})
        duram = rec("Neil Duram", links=["https://legislators.legmt.gov/#/legislator/96"])
        tezak = rec("Tony Tezak", district="2", links=["https://www.legmt.gov/legislators/1277/",
                                                         "https://legislators.legmt.gov/#/legislator/1606"])
        wrong = rec("Pat Smith", district="3", links=["https://legislators.legmt.gov/#/legislator/96"])
        out = legphotos.read_montana(http, "MT", [duram, tezak, wrong])
        self.assertEqual(out[duram["id"]]["candidate"]["renditions"][0], "https://www.legmt.gov/a/1331-200x250.jpg")
        self.assertIn("Neil Duram", out[duram["id"]]["candidate"]["evidence"])
        # The WordPress id first: Tezak is 1277, not lawsId 1606's stranger.
        self.assertIn("1277", out[tezak["id"]]["candidate"]["key"])
        self.assertIn("refused", out[wrong["id"]])

    def test_new_jersey_takes_the_picture_its_record_names_beside_the_member(self):
        bio = "https://www.njleg.state.nj.us/api/legislatorData/legislatorBio/{}"
        record = [[{"First_Name": "Antwan", "Last_Name": "McClellan", "Roster_House": ["A", "A"],
                    "Roster_District": 1, "Legislator_Status": "A",
                    "Picture": "/publications/members/mcclellan_antwan_2020_250.jpg",
                    "PictureText": "Assemblyman Antwan L. McClellan (R)",
                    "BioLink": "/legislative-roster/425/assemblyman-mcclellan"}]]
        stranger = [[dict(record[0][0], Last_Name="Someone", PictureText="Assemblyman Some One (R)")]]
        http = FakeHttp({bio.format(425): (200, record, {}), bio.format(426): (200, stranger, {})})
        mine = rec("Antwan McClellan", links=["https://www.njleg.state.nj.us/legislative-roster/425/x"])
        theirs = rec("Pat Jones", links=["https://www.njleg.state.nj.us/legislative-roster/426/x"])
        out = legphotos.read_new_jersey(http, "NJ", [mine, theirs])
        cand = out[mine["id"]]["candidate"]
        self.assertEqual(cand["renditions"], ["https://pub.njleg.state.nj.us/publications/members/"
                                              "mcclellan_antwan_2020_250.jpg"])
        self.assertIn("PictureText \"Assemblyman Antwan L. McClellan (R)\"", cand["evidence"])
        self.assertNotIn(theirs["id"], out)        # the record is someone else's: nothing taken

    def test_oklahoma_takes_only_the_portrait_slot_and_its_smallest_fitting_rendition(self):
        page = "https://www.okhouse.gov/representatives/eddy-dempsey"
        portrait = {"name": "Dempsey, Eddy.jpg", "url": "https://dgbf0g52sf9l0.cloudfront.net/Dempsey_Eddy_1.jpg",
                    "formats": {"small": {"url": "https://dgbf0g52sf9l0.cloudfront.net/small_Dempsey_Eddy_1.jpg",
                                          "width": 400},
                                "thumbnail": {"url": "https://dgbf0g52sf9l0.cloudfront.net/thumbnail_Dempsey_Eddy_1.jpg",
                                              "width": 125}}}
        html = ('<h1 class="x">Representative Eddy Dempsey</h1><a href="/district/1"></a>'
                '<img src="https://dgbf0g52sf9l0.cloudfront.net/Dempsey_Lina_2.jpg" alt="press">'
                '<script>{"portrait":' + json.dumps(portrait) + '}</script>')
        http = FakeHttp({page: (200, html, {"Content-Type": "text/html"})})
        member = rec("Eddy Dempsey", links=[page])
        cand = legphotos.read_oklahoma(http, "OK", [member])[member["id"]]["candidate"]
        self.assertEqual(cand["renditions"][0], "https://dgbf0g52sf9l0.cloudfront.net/thumbnail_Dempsey_Eddy_1.jpg")
        self.assertNotIn("Dempsey_Lina", " ".join(cand["renditions"]))
        # A page whose heading is someone else's is refused.
        other = rec("Pat Jones", links=[page])
        self.assertIn("refused", legphotos.read_oklahoma(http, "OK", [other])[other["id"]])

    def test_a_seats_page_that_names_someone_else_is_refused(self):
        page = "https://house.louisiana.gov/H_Reps/members?ID=1"
        html = ('<img class="NO-CACHE" src="/H_Reps/RepPics/rep1.jpg" alt="Member Picture">'
                '<span id="body_FormView1111_FULLNAME1Label">Danny McCormick</span>')
        http = FakeHttp({page: (200, html, {})})
        ok = legphotos.read_louisiana(http, "LA", [rec("Danny McCormick")])
        cand = ok["ocd-person/danny-mccormick"]["candidate"]
        self.assertTrue(cand["seatKeyed"])
        self.assertEqual(cand["renditions"], ["https://house.louisiana.gov/H_Reps/RepPics/rep1.jpg"])
        refused = legphotos.read_louisiana(http, "LA", [rec("New Member")])
        self.assertIn("McCormick", refused["ocd-person/new-member"]["refused"])

    def test_connecticut_reads_the_lists_name_and_the_pages_heading(self):
        hlist = "<tr><td>127</td><td><a href='x'>Brown, Marcus</a></td></tr>"
        page = "https://www.cga.ct.gov/asp/CGABillStatus/CGAMemberBills.asp?dist_code=%27127%27"
        html = ('<h2>Representative Marcus Brown of the 127th</h2>'
                '<img src="/legpics/127.png?ver=3" alt="">')
        http = FakeHttp({"https://www.cga.ct.gov/asp/menu/hlist.asp": (200, hlist, {}),
                         page: (200, html, {})})
        brown = rec("Marcus Brown", district="127")
        cand = legphotos.read_connecticut(http, "CT", [brown])[brown["id"]]["candidate"]
        self.assertEqual(cand["renditions"], ["https://www.cga.ct.gov/legpics/127.png"])
        self.assertTrue(cand["seatKeyed"])
        self.assertIn("Brown, Marcus", cand["evidence"])
        # The list names someone else for the seat: refused, nothing read.
        other = rec("Pat Jones", district="127")
        self.assertIn("Brown, Marcus", legphotos.read_connecticut(http, "CT", [other])[other["id"]]["refused"])

    def test_indiana_builds_the_address_from_its_own_key_once_its_app_says_so(self):
        years = {"years": [{"active": True, "special": False, "lpid": "session_2026", "year": "2026",
                            "assembly_id": 124}]}
        app = 'x="/images/legislators/").concat(a)'
        api = ("https://iga.in.gov/api/getLegislatorDetails?session_lpid=session_2026"
               "&legislator_lpid=legislator_carolyn_jackson_1")
        table = {"https://iga.in.gov/api/getSessionYears": (200, years, {}),
                 "https://iga.in.gov/": (200, '<script src="/static/js/main.abc123.js"></script>', {}),
                 "https://iga.in.gov/static/js/main.abc123.js": (200, app, {}),
                 api: (200, {"honorific": "Representative", "firstname": "Carolyn", "lastname": "Jackson",
                             "district_id": 1}, {})}
        jackson = rec("Carolyn Jackson", links=["https://iga.in.gov/legislative/2026/legislators/"
                                                "legislator_carolyn_jackson_1"])
        cand = legphotos.read_indiana(FakeHttp(table), "IN", [jackson])[jackson["id"]]["candidate"]
        self.assertEqual(cand["renditions"], ["https://iga.in.gov/images/legislators/124/2026/house/"
                                              "legislator_carolyn_jackson_1.jpg"])
        self.assertIn("Representative Carolyn Jackson", cand["evidence"])
        # The record is someone else's, in another district: refused.
        moved = rec("Carolyn Jackson", district="2", links=jackson["links"], pid="ocd-person/x")
        self.assertIn("refused", legphotos.read_indiana(FakeHttp(table), "IN", [moved])["ocd-person/x"])
        # Without the app's own template, nothing is built.
        table["https://iga.in.gov/static/js/main.abc123.js"] = (200, "nothing", {})
        self.assertEqual(legphotos.read_indiana(FakeHttp(table), "IN", [jackson]), {})

    def test_colorado_takes_its_lists_own_smaller_rendition(self):
        src = ("https://leg.colorado.gov/rails/active_storage/representations/redirect/abc/def/"
               "Barron,%20Carlos.jpg")
        html = f'<img class="leg-mem-picture" src="{src}" alt="Carlos Barron">'
        http = FakeHttp({"https://leg.colorado.gov/legislators": (200, html, {})})
        barron = rec("Carlos Barron", district="48")
        original = legislature.pages_for
        legislature.pages_for = lambda code, roster, year: ({}, 0)
        try:
            out = legphotos.read_colorado(http, "CO", [barron])
        finally:
            legislature.pages_for = original
        self.assertEqual(out[barron["id"]]["candidate"]["renditions"], [src])

    @staticmethod
    def ohio_card(name, district, image=None):
        # The directory's markup as served on 2026-10-19.
        return ('<div class="media-container media-container-portrait last-item-row-1  democrat ">'
                '<a target="_self" href="x"><div class="media-thumbnail"><div class="media-overlay-caption">'
                f'<div class="media-overlay-caption-text-line-1">{name}</div>'
                f'<div class="media-overlay-caption-text-line-2">District {district} '
                "<span class='vertical-bar'>&nbsp;</span> D</div></div>"
                + (f'<div style="background-image:url({image})" class="media-thumbnail-image" ></div>'
                   if image else "")
                + '</div></a></div><div class="media-grid-clear-row-1 "></div>')

    def test_ohio_lists_a_vacant_seat_as_nobody(self):
        house = (self.ohio_card("Vacant", 89, "/assets/people/headshots/medium/0.jpg")
                 + self.ohio_card("Brian Stewart", 12, "/assets/people/headshots/medium/2955.jpg"))
        http = FakeHttp({"https://ohiohouse.gov/members/directory": (200, house, {})})
        out = legphotos.read_ohio(http, "OH", [rec("D.J. Swearingen", district="89"),
                                               rec("Brian Stewart", district="12")])
        self.assertIn("vacant", out["ocd-person/d.j.-swearingen"]["refused"])
        # The legislature's word that the roster's member has left is kept
        # for the build to say (rules 16 and 51).
        self.assertIn("vacant", out["ocd-person/d.j.-swearingen"]["notSeated"])
        cand = out["ocd-person/brian-stewart"]["candidate"]
        self.assertEqual(cand["renditions"][0], "https://ohiohouse.gov/assets/people/headshots/small/2955.jpg")

    def test_an_ohio_card_without_a_headshot_never_takes_the_next_cards(self):
        house = (self.ohio_card("Ann Lee", 3)
                 + self.ohio_card("Brian Stewart", 12, "/assets/people/headshots/medium/2955.jpg"))
        http = FakeHttp({"https://ohiohouse.gov/members/directory": (200, house, {})})
        out = legphotos.read_ohio(http, "OH", [rec("Ann Lee", district="3"),
                                               rec("Brian Stewart", district="12")])
        self.assertNotIn("ocd-person/ann-lee", out)
        self.assertEqual(out["ocd-person/brian-stewart"]["candidate"]["renditions"][-1],
                         "https://ohiohouse.gov/assets/people/headshots/medium/2955.jpg")


class TestMemberPage(unittest.TestCase):

    def pick(self, html, name="Nathan Boyles", url="https://www.flhouse.gov/details.aspx?MemberId=5063",
             code="FL", district="3", others=()):
        doc = legphotos.parse_page(html)
        return legphotos.pick_member_image(code, rec(name, district=district), doc, url, others)

    def test_an_alt_naming_the_member_in_full(self):
        found = self.pick('<title>Rob North</title><img src="/Documents/Legislators/North,Rob.jpg" '
                          'alt="Representative Rob North">', name="Rob North", code="VT",
                          url="https://legislature.vermont.gov/people/single/2026/40396")
        self.assertEqual(found[0], ["https://legislature.vermont.gov/Documents/Legislators/North,Rob.jpg"])
        self.assertFalse(found[2])

    def test_floridas_album_photograph_is_never_taken_beside_the_members_own(self):
        html = ('<title>Nathan Boyles</title>'
                '<img src="/FileStores/Web/Imaging/Member/cutout%2f5063.png" alt="Representative Boyles Photo">'
                '<img src="/FileStores/Web/Imaging/PhotoAlbums/HousePhotoSized8414.jpg" '
                'alt="Representative Boyles Photo">')
        images, why, _ = self.pick(html)
        self.assertEqual(images, ["https://www.flhouse.gov/FileStores/Web/Imaging/Member/cutout%2f5063.png"])
        self.assertIn("5063", why)

    def test_a_file_with_another_members_name_is_refused(self):
        html = '<title>Pat Black</title><img src="/WebPhotos/Smith12.jpg" alt="Senator">'
        self.assertIsNone(self.pick(html, name="Pat Black", code="MO", others={"smith"},
                                    url="https://www.senate.mo.gov/Senators/Member?id=270"))

    def test_a_map_or_seal_is_not_a_likeness(self):
        html = ('<title>Representative Bill Lucas</title><img src="maps/2023/115.png" alt="District 115 Map">'
                '<img src="https://images.house.mo.gov/MemberPhoto.aspx?id=2516" alt="Representative Bill Lucas">')
        images, _, _ = self.pick(html, name="Bill Lucas", code="MO", district="115",
                                 url="https://house.mo.gov/MemberDetails.aspx?district=115")
        self.assertEqual(images, ["https://images.house.mo.gov/MemberPhoto.aspx?id=2516"])

    def test_a_logo_named_by_the_seat_is_not_a_likeness(self):
        # California's Senate pages carry "sd29_logo_white.png" under a
        # heading naming the senator.
        html = ('<h1>Senator Eloise Reyes</h1>'
                '<img src="https://sd29.senate.ca.gov/files/sd29_logo_white.png" alt="">')
        self.assertIsNone(self.pick(html, name="Eloise Reyes", code="CA", district="29",
                                    url="https://sd29.senate.ca.gov/biography"))

    def test_a_file_named_by_the_seat_is_seat_keyed(self):
        html = ('<title>Assembly Member Rogers</title>'
                '<img src="https://www.assembly.ca.gov/media/assembly_member_02.jpg" alt="picture of Rogers, Chris">')
        images, _, seat_keyed = self.pick(html, name="Chris Rogers", code="CA", district="2",
                                          url="https://www.assembly.ca.gov/assemblymembers/02")
        self.assertTrue(seat_keyed)

    def test_an_album_photograph_alone_is_never_the_portrait(self):
        # Florida's album photograph carries a templated alt naming each
        # page's member, and the member-uploaded photographs sit in a folder
        # named by the member's id: neither is their portrait.
        html = ('<title>Brian Hodgers</title>'
                '<img src="/FileStores/Web/Imaging/PhotoAlbums/HousePhotoSized8414.jpg" '
                'alt="Representative Hodgers Photo">'
                '<img src="/api/Member/get-member-uploaded-photo/5064/MemberPhotoSized8529.JPG/image" alt="">')
        self.assertIsNone(self.pick(html, name="Brian Hodgers",
                                    url="https://www.flhouse.gov/details.aspx?MemberId=5064"))

    def test_a_key_in_a_folder_is_not_the_files_name(self):
        html = ('<title>Brian Hodgers</title>'
                '<img src="/api/Member/photos/5064/image.jpg" alt="Representative Hodgers">')
        self.assertIsNone(self.pick(html, name="Brian Hodgers",
                                    url="https://www.flhouse.gov/details.aspx?MemberId=5064"))

    def test_alaskas_member_code_and_its_nested_heading(self):
        # Alaska nests an empty <h1> in the one naming the member, and its
        # portrait is named by the member's code in the page's address.
        html = ('<h1>HOUSE<br />DAVID NELSON<br><div><h1></h1></div></h1>'
                '<span class="formal_name">Representative David Nelson</span>'
                '<img src="//akleg.gov/images/legislators/450x600/NED.jpg" class="legpic" />'
                '<img src="//akleg.gov/images/logo.png" alt="The Seal of the State of Alaska">')
        doc = legphotos.parse_page(html)
        self.assertIn("HOUSE DAVID NELSON", doc.headings)
        images, why, seat_keyed = self.pick(html, name="David Nelson", code="AK", district="18",
                                            url="https://www.akleg.gov/basis/Member/Detail/32?code=ned")
        self.assertEqual(images, ["https://akleg.gov/images/legislators/450x600/NED.jpg"])
        self.assertIn("(ned)", why)
        self.assertFalse(seat_keyed)
        # The same file on a page that names someone else is not taken.
        other = html.replace("DAVID NELSON", "PAT JONES").replace("David Nelson", "Pat Jones")
        self.assertIsNone(self.pick(other, name="David Nelson", code="AK", district="18",
                                    url="https://www.akleg.gov/basis/Member/Detail/32?code=ned"))

    def test_a_seats_file_under_a_heading_naming_the_member(self):
        html = ('<h2>Sen. Bob Hallstrom</h2>'
                '<img src="https://www.nebraskalegislature.gov/media/images/senators/dist01/highres/dist01.jpg">')
        images, why, seat_keyed = self.pick(html, name="Bob Hallstrom", code="NE", district="1",
                                            url="https://nebraskalegislature.gov/senators/landing-pages/"
                                                "index.php?District=1")
        self.assertTrue(seat_keyed)
        self.assertIn("named by the seat", why)
        # Under another senator's heading, nothing.
        self.assertIsNone(self.pick(html.replace("Bob Hallstrom", "Pat Jones"), name="Bob Hallstrom",
                                    code="NE", district="1",
                                    url="https://nebraskalegislature.gov/senators/landing-pages/"
                                        "index.php?District=1"))

    def test_a_file_named_by_surname_and_seat_is_dated_like_a_seats(self):
        html = ('<title>Senator Angela Mosley</title>'
                '<img src="/WebPhotos/SenatorPortraits/Mosley13.jpg" alt="Senator Mosley">')
        images, _, seat_keyed = self.pick(html, name="Angela Mosley", code="MO", district="13",
                                          url="https://www.senate.mo.gov/Senators/Member?id=270")
        self.assertEqual(images, ["https://www.senate.mo.gov/WebPhotos/SenatorPortraits/Mosley13.jpg"])
        self.assertTrue(seat_keyed)

    def test_kentuckys_seat_files_are_seat_keyed(self):
        # Kentucky numbers its Senate seats from 101 (senate137.jpg on
        # ?DistrictNumber=137 is seat 37) and its House files house<n>.jpg.
        html = ('<title>Senator Gary Clemons (D)</title>'
                '<img src="/Legislators%20Thumbnail%20Images/senate137.jpg" alt="Gary Clemons photo">')
        url = "https://legislature.ky.gov/Legislators/Pages/Legislator-Profile.aspx?DistrictNumber=137"
        doc = legphotos.parse_page(html)
        images, _, seat_keyed = legphotos.pick_member_image(
            "KY", rec("Gary Clemons", chamber="upper", district="37"), doc, url)
        self.assertEqual(images, ["https://legislature.ky.gov/Legislators%20Thumbnail%20Images/senate137.jpg"])
        self.assertTrue(seat_keyed)
        self.assertTrue(legphotos.seat_key("senate137", "37", "KY", "upper"))
        self.assertFalse(legphotos.seat_key("senate137", "37", "KY", "lower"))
        self.assertFalse(legphotos.seat_key("senate137", "37"))
        for key in ("house12", "rep12", "sen12", "senate12", "hd012", "assembly_12"):
            self.assertTrue(legphotos.seat_key(key, "12"), key)
        self.assertFalse(legphotos.seat_key("house12", "2"))

    def test_a_page_for_a_former_member_gives_no_photograph(self):
        # New Mexico heads a departed member's page "Former Representative"
        # and redirects their sponsor code to Former_Legislator.
        reeb = rec("Andi Reeb", district="64", links=["https://www.nmlegis.gov/Members/Legislator?SponCode=HREEB"])
        page = ('<title>Former Representative Andrea Reeb - (R)</title>'
                '<img src="/Images/Legislators/HA/HREEB.jpg" alt="Reeb">')
        for url, answered in ((reeb["links"][0], reeb["links"][0]),
                              (reeb["links"][0], "https://www.nmlegis.gov/Members/Former_Legislator?SponCode=HREEB")):
            http = FakeHttp({url: (200, page if answered == url else page.replace("Former ", ""), {})})
            original_get = http.get

            def get(u, limit=None, browser=False, original_get=original_get, answered=answered):
                ans = original_get(u, limit, browser)
                ans.url = answered
                return ans
            http.get = get
            original = legislature.pages_for
            legislature.pages_for = lambda code, roster, year: (
                {r["id"]: {"url": r["links"][0], "kind": "member"} for r in roster}, 0)
            try:
                out = legphotos.read_member_pages(http, "NM", [reeb])
            finally:
                legislature.pages_for = original
            self.assertIn("refused", out[reeb["id"]], answered)
            self.assertIn("former", out[reeb["id"]]["notSeated"].lower())
        # A sitting member's page is read as before.
        self.assertEqual(legphotos.former_page(legphotos.parse_page("<title>Senator Natalie Figueroa</title>"),
                                               "https://www.nmlegis.gov/Members/Legislator?SponCode=SFIGU",
                                               "Natalie Figueroa"), "")

    def test_one_file_on_two_members_pages_is_neithers(self):
        album = '<img src="/FileStores/Web/Imaging/Member/shared.jpg" alt="Photo of Representative {}">'
        a = rec("Nathan Boyles", district="3", links=["https://www.flhouse.gov/details.aspx?MemberId=5063"])
        b = rec("Brian Hodgers", district="4", links=["https://www.flhouse.gov/details.aspx?MemberId=5064"])
        c = rec("Rob Long", district="5", links=["https://www.flhouse.gov/details.aspx?MemberId=5067"])
        table = {}
        for member, key in ((a, 5063), (b, 5064), (c, 5067)):
            surname = member["name"].split()[-1]
            page = f'<title>{member["name"]}</title>' + album.format(surname)
            if member is c:
                page = f'<title>{member["name"]}</title><img src="/Imaging/Member/5067.jpg" alt="x">'
            table[member["links"][0]] = (200, page, {})
        original = legislature.pages_for
        legislature.pages_for = lambda code, roster, year: (
            {r["id"]: {"url": r["links"][0], "kind": "member"} for r in roster}, 0)
        try:
            out = legphotos.read_member_pages(FakeHttp(table), "FL", [a, b, c])
        finally:
            legislature.pages_for = original
        self.assertIn("2 members' pages", out[a["id"]]["refused"])
        self.assertIn("refused", out[b["id"]])
        self.assertEqual(out[c["id"]]["candidate"]["renditions"],
                         ["https://www.flhouse.gov/Imaging/Member/5067.jpg"])

    def test_another_hosts_image_is_not_the_legislatures(self):
        html = ('<title>Rob North</title><img src="https://www.vthousegop.org/North,Rob.jpg" '
                'alt="Representative Rob North">')
        self.assertIsNone(self.pick(html, name="Rob North", code="VT",
                                    url="https://legislature.vermont.gov/people/single/2026/40396"))


class TestSettle(unittest.TestCase):

    def candidate(self, *renditions, **extra):
        return dict({"page": "https://www.legmt.gov/legislators/1/", "evidence": "the roster record: Neil Duram",
                     "renditions": list(renditions), "key": "legmt.gov id 1"}, **extra)

    def settle(self, table, cand, record=None, seat_files=None):
        return legphotos.settle(FakeHttp(table), "MT", record or rec("Neil Duram"), cand,
                                seat_files or {}, TODAY, {})

    def test_the_smallest_rendition_wide_enough_for_the_card(self):
        a, b = "https://www.legmt.gov/a.jpg", "https://www.legmt.gov/b.jpg"
        entry = self.settle({a: image(200, 250, 7000), b: image(400, 500, 25000)}, self.candidate(a, b))
        self.assertEqual(entry["image"], a)
        self.assertEqual((entry["width"], entry["height"], entry["bytes"]), (200, 250, 7000))
        self.assertEqual(entry["credit"], "Montana Legislature")
        self.assertEqual(entry["read"], TODAY)

    def test_a_file_offered_only_over_the_caps_is_taken_marked_heavy(self):
        # Rule 101 (the owner, 2026-10-25): shown as a smaller copy made
        # here, after the checks a heavy file used to skip.
        big = "https://www.legmt.gov/big.jpg"
        entry = self.settle({big: image(3000, 4200, 2_500_000)}, self.candidate(big))
        self.assertNotIn("oversized", entry)
        self.assertEqual((entry["image"], entry["heavy"]), (big, True))
        # The lightest of several heavy renditions.
        bigger = "https://www.legmt.gov/bigger.jpg"
        entry = self.settle({bigger: image(3000, 4200, 6_000_000), big: image(3000, 4200, 2_500_000)},
                            self.candidate(bigger, big))
        self.assertEqual(entry["image"], big)
        # Too many pixels, however light.
        wide = "https://www.legmt.gov/wide.jpg"
        self.assertTrue(self.settle({wide: image(1200, 1600, 90_000)}, self.candidate(wide))["heavy"])
        # Checked as theirs like any other: a landscape frame is still not a
        # portrait (rule 38).
        land = "https://www.legmt.gov/land.jpg"
        self.assertIn("landscape", self.settle({land: image(4000, 3000, 2_000_000)},
                                               self.candidate(land))["withheld"])
        # A smaller rendition the source offers is taken instead.
        small = "https://www.legmt.gov/small.jpg"
        entry = self.settle({big: image(3000, 4200, 2_500_000), small: image(400, 500, 30_000)},
                            self.candidate(big, small))
        self.assertEqual(entry["image"], small)

    def test_a_landscape_frame_is_not_a_portrait(self):
        url = "https://www.legmt.gov/office.jpg"
        entry = self.settle({url: image(313, 250)}, self.candidate(url))
        self.assertIn("landscape", entry["withheld"])

    def test_an_unanswered_read_concludes_nothing(self):
        self.assertIsNone(self.settle({}, self.candidate("https://www.legmt.gov/a.jpg")))

    def test_an_image_off_the_legislatures_host_is_withheld(self):
        url = "https://example.com/a.jpg"
        self.assertIn("not on the legislature", self.settle({url: image(200, 250)}, self.candidate(url))["withheld"])

    def test_a_seat_keyed_file_older_than_the_members_arrival_is_withheld(self):
        url = "https://www.legmt.gov/rep1.jpg"
        yaml = "id: x\nroles:\n- start_date: 2025-01-08\n  type: lower\n  district: '1'\n"
        table = {url: image(200, 250, modified="Fri, 03 Mar 2023 10:00:00 GMT"),
                 "https://api.github.com/repos/openstates/people/contents/data/mt/legislature":
                     (200, [{"name": "Neil-Duram-" + "a" * 36 + ".yml", "download_url": "https://raw/y.yml"}], {}),
                 "https://raw/y.yml": (200, yaml, {})}
        member = rec("Neil Duram", pid="ocd-person/" + "a" * 36)
        entry = self.settle(table, self.candidate(url, seatKeyed=True), record=member)
        self.assertIn("before the member arrived", entry["withheld"])
        self.assertFalse(entry.get("image"))
        # Dated after the arrival: theirs.
        table[url] = image(200, 250, modified="Thu, 06 Mar 2025 10:00:00 GMT")
        entry = self.settle(table, self.candidate(url, seatKeyed=True), record=member)
        self.assertEqual(entry["image"], url)
        self.assertEqual(entry["holderSince"], "2025-01-08")
        # A file that has not changed since it showed the predecessor.
        shown = {url: {"holder": "ocd-person/old", "name": "Old Member", "sha": entry["sha"]}}
        again = self.settle(table, self.candidate(url, seatKeyed=True), record=member, seat_files=shown)
        self.assertIn("Old Member", again["withheld"])

    def test_a_heavy_seat_file_unchanged_since_it_showed_another_is_withheld(self):
        # A file over the caps is read only to the byte cap (rule 101): it is
        # told apart by its first bytes and its length, so a seat's heavy
        # file that has not changed since it showed the predecessor is still
        # never shown, or copied, as the successor's (the reviewers of PR
        # #137 broke the fingerprint and no test noticed).
        url = "https://www.legmt.gov/rep1.jpg"
        modified = "Thu, 06 Mar 2025 10:00:00 GMT"
        yaml = "id: x\nroles:\n- start_date: 2025-01-08\n  type: lower\n  district: '1'\n"
        github = {"https://api.github.com/repos/openstates/people/contents/data/mt/legislature":
                  (200, [{"name": "Neil-Duram-" + "a" * 36 + ".yml", "download_url": "https://raw/y.yml"}], {}),
                  "https://raw/y.yml": (200, yaml, {})}
        heavy = image(3000, 4200, 2_500_000, modified=modified)
        table = dict(github, **{url: heavy})
        a = rec("Pat Old", pid="ocd-person/" + "b" * 36)
        b = rec("Neil Duram", pid="ocd-person/" + "a" * 36)
        first = self.settle(table, self.candidate(url, seatKeyed=True), record=b)
        self.assertTrue(first["heavy"])
        self.assertTrue(first["sha"].startswith("h"))
        # Read twice, the same bytes give the same fingerprint.
        self.assertEqual(self.settle(table, self.candidate(url, seatKeyed=True), record=b)["sha"],
                         first["sha"])
        shown = {url: {"holder": a["id"], "name": "Pat Old", "sha": first["sha"]}}
        again = self.settle(table, self.candidate(url, seatKeyed=True), record=b, seat_files=shown)
        self.assertIn("has not changed since it showed Pat Old", again["withheld"])
        self.assertFalse(again.get("image"))
        # New bytes within what is read, dated after B arrived: B's.
        body = bytearray(heavy[1])
        body[1000] = 0x7F
        changed = self.settle(dict(github, **{url: (200, bytes(body), heavy[2])}),
                              self.candidate(url, seatKeyed=True), record=b, seat_files=shown)
        self.assertNotEqual(changed["sha"], first["sha"])
        self.assertEqual(changed["image"], url)
        # A new length past what is read is a new file too.
        longer = image(3000, 4200, 2_600_000, modified=modified)
        grown = self.settle(dict(github, **{url: longer}), self.candidate(url, seatKeyed=True),
                            record=b, seat_files=shown)
        self.assertNotEqual(grown["sha"], first["sha"])
        self.assertEqual(grown["image"], url)

    def test_a_host_that_dates_files_by_its_deploys_is_undated(self):
        # California's Assembly answers one Last-Modified for every seat's
        # file: the deploy's, not the photograph's.
        url = "https://webapi.assembly.ca.gov/district-media/assets/members/assembly_member_02.jpg"
        entry = {"image": url, "seatKeyed": True, "holderSince": "2024-12-02",
                 "lastModified": "2026-09-30", "lastModifiedAt": "2026-09-30T18:09:20"}
        self.assertIn("deploy", legphotos.seat_problem(entry, "ocd-person/x", {}))

    def test_seat_files_copied_together_are_dated_only_near_the_arrival(self):
        # Louisiana's House wrote some fifty seat files within twenty
        # seconds on 2024-05-15, for members seated since 2016 and 2020.
        def seat(n, at, since):
            return {"image": f"https://house.louisiana.gov/H_Reps/RepPics/rep{n}.jpg", "seatKeyed": True,
                    "holderSince": since, "lastModified": at[:10], "lastModifiedAt": at, "state": "LA",
                    "name": f"Member {n}", "chamber": "lower", "district": str(n)}
        people = {"a": seat(1, "2024-05-15T19:58:45", "2020-01-13"),
                  "b": seat(2, "2024-05-15T19:58:50", "2024-01-08"),
                  "c": seat(3, "2024-05-15T19:59:02", "2016-01-11"),
                  "d": seat(4, "2025-10-13T14:02:00", "2025-09-01")}
        found = legphotos.batches(people)
        self.assertIn("a copy", legphotos.batch_problem(people["a"], found))
        self.assertIn("a copy", legphotos.batch_problem(people["c"], found))
        # The copy fell near this member's arrival: a new member's
        # photograph going up.
        self.assertEqual(legphotos.batch_problem(people["b"], found), "")
        # A file written on its own is dated by its own stamp.
        self.assertEqual(legphotos.batch_problem(people["d"], found), "")
        # Two files together are not a batch.
        del people["c"]
        self.assertEqual(legphotos.batch_problem(people["a"], legphotos.batches(people)), "")

    def test_an_undated_seat_keyed_file_is_withheld(self):
        url = "https://www.legmt.gov/rep1.jpg"
        entry = self.settle({url: image(200, 250)}, self.candidate(url, seatKeyed=True))
        self.assertIn("cannot be dated", entry["withheld"])

    def test_a_file_the_source_no_longer_serves_is_not_shown(self):
        # Kansas's new site names /static/li_pics/<key>.jpg and answers 404.
        url = "https://www.legmt.gov/gone.jpg"
        entry = self.settle({url: (404, b"", {})}, self.candidate(url))
        self.assertIn("gone", entry["withheld"])
        self.assertNotIn("image", entry)

    def test_a_host_that_answers_nothing_is_not_asked_all_run(self):
        http = legphotos.Http(pause=0)
        calls = []
        http._get = lambda url, limit, browser: calls.append(url) or legphotos.Answer(None, {}, b"", url)
        original = legphotos.time.sleep
        legphotos.time.sleep = lambda s: None
        try:
            for i in range(10):
                self.assertIsNone(http.get(f"https://legislature.maine.gov/p/{i}").status)
        finally:
            legphotos.time.sleep = original
        self.assertEqual(len(calls), 2 * legphotos.DOWN_AFTER)

    def test_open_states_role_start(self):
        text = ("id: x\nroles:\n- start_date: 2019-01-07\n  end_date: 2021-01-04\n  type: lower\n"
                "- start_date: 2023-01-09\n  type: upper\n  district: '4'\noffices:\n- x: y\n")
        self.assertEqual(legphotos.role_start(text, "upper"), "2023-01-09")
        self.assertIsNone(legphotos.role_start(text, "lower"))


class TestRefreshAndBuild(unittest.TestCase):

    def test_a_failed_read_keeps_the_last_good_photograph(self):
        member = rec("Neil Duram")
        previous = {"people": {member["id"]: {"image": "https://www.legmt.gov/a.jpg", "read": "2026-01-01",
                                              "evidence": "Neil Duram", "name": "Neil Duram"}},
                    "seatFiles": {}}
        cache, counts = legphotos.refresh({"MT": [member]}, previous, http=FakeHttp({}), today=TODAY,
                                          log=lambda *a: None)
        self.assertEqual(cache["people"][member["id"]]["image"], "https://www.legmt.gov/a.jpg")
        self.assertEqual(counts["MT"]["kept"], 1)
        # Someone no longer on the roster leaves the cache.
        cache, _ = legphotos.refresh({"MT": []}, previous, http=FakeHttp({}), today=TODAY, log=lambda *a: None)
        self.assertEqual(cache["people"], {})

    def entry(self, **extra):
        return dict({"name": "Neil Duram", "image": "https://www.legmt.gov/a.jpg",
                     "page": "https://www.legmt.gov/legislators/1331/", "evidence": "the roster: Neil Duram",
                     "key": "legmt.gov id 1331", "credit": "Montana Legislature", "read": TODAY,
                     "bytes": 7000, "width": 200, "height": 250}, **extra)

    def test_the_build_shows_it_credited_where_open_states_has_none(self):
        member = rec("Neil Duram")
        photos = {"people": {member["id"]: self.entry()}}
        out = legislature._person(member, "MT", 2026, photos=photos)
        self.assertEqual(out["image"], "https://www.legmt.gov/a.jpg")
        self.assertEqual(out["imageCredit"], {"by": "Montana Legislature",
                                              "page": "https://www.legmt.gov/legislators/1331/"})
        # Open States's own portrait stands where it has one.
        out = legislature._person(dict(member, image="https://x.gov/n.jpg"), "MT", 2026, photos=photos)
        self.assertEqual(out["image"], "https://x.gov/n.jpg")
        # Said to be where Open States found it, never whose it is (PR #137).
        self.assertEqual(out["imageCredit"], {"host": "x.gov", "listedBy": "Open States"})
        # Evidence for another person is never shown on this one.
        wrong = {"people": {member["id"]: self.entry(evidence="the roster: Pat Smith")}}
        self.assertNotIn("image", legislature._person(member, "MT", 2026, photos=wrong))

    def test_an_oversized_only_photograph_is_counted_not_shown(self):
        member = rec("Tim Yocum")
        photos = {"people": {member["id"]: {"oversized": True, "offered": "https://iga.in.gov/x.jpg",
                                            "bytes": 15660420, "width": 4000, "height": 6000}}}
        dropped = {}
        out = legislature._person(member, "IN", 2026, dropped=dropped, photos=photos)
        self.assertNotIn("image", out)
        self.assertEqual(dropped, {"oversized": 1})
        self.assertEqual(legphotos.report(photos, {"IN": [member]}), {"oversized": {"IN": 1}})

    def test_a_seat_file_read_for_another_seat_is_not_shown(self):
        member = rec("Neil Duram", district="4")
        seat = self.entry(seatKeyed=True, chamber="lower", district="3", holderSince="2025-01-06",
                          lastModified="2025-02-01", lastModifiedAt="2025-02-01T10:00:00")
        self.assertIsNone(legphotos.entry_for(member, {"people": {member["id"]: seat}}))
        self.assertIsNotNone(legphotos.entry_for(member, {"people": {member["id"]: dict(seat, district="4")}}))

    def test_a_portrait_the_legislature_serves_is_credited_to_it(self):
        member = rec("Matt Birong", image="https://legislature.vermont.gov/Documents/Legislators/Birong.Matt.jpg",
                     links=["https://legislature.vermont.gov/people/single/2026/40396"])
        page = {"url": member["links"][0], "kind": "member"}
        out = legislature._person(member, "VT", 2026, pages={member["id"]: page}, photos={"people": {}})
        self.assertEqual(out["imageCredit"], {"by": "Vermont General Assembly", "page": member["links"][0]})
        # Off the legislature's host, no one is credited with it: the card
        # says only where Open States found it (the reviewers of PR #137:
        # "Photo: <host>" read as whose photograph it is).
        other = dict(member, image="https://s3.amazonaws.com/ballotpedia-api4/files/thumbs/x.jpg")
        out = legislature._person(other, "VT", 2026, pages={member["id"]: page}, photos={"people": {}})
        self.assertEqual(out["imageCredit"], {"host": "s3.amazonaws.com", "listedBy": "Open States"})
        self.assertNotIn("by", out["imageCredit"])

    MCCANN = "https://senatedems.com/mccann/wp-content/uploads/sites/20/2022/12/MDS_McCann_DSC5430.jpg"

    def test_a_caucuss_photograph_of_its_own_member_is_credited_to_the_caucus(self):
        # The owner, 2026-10-25: "we can credit caucus". Michigan's
        # legislators' only photographs are their caucuses' (rule 100).
        member = rec("Sean McCann", chamber="upper", district="19", image=self.MCCANN,
                     links=["https://senatedems.com/mccann"])
        page = {"url": "https://senatedems.com/mccann", "kind": "caucus",
                "caucus": "Michigan Senate Democrats"}
        out = legislature._person(member, "MI", 2026, pages={member["id"]: page},
                                  photos={"people": {}})
        self.assertEqual(out["image"], self.MCCANN)
        self.assertEqual(out["imageCredit"], {"by": "Michigan Senate Democrats", "caucus": True,
                                              "page": "https://senatedems.com/mccann"})
        # Linked only to the member's own page on that caucus's site.
        out = legislature._person(member, "MI", 2026, pages={member["id"]: None},
                                  photos={"people": {}})
        self.assertEqual(out["imageCredit"], {"by": "Michigan Senate Democrats", "caucus": True})
        # A subdomain of a caucus's host is the caucus's (Washington's
        # members' sites), and "www." is the host itself.
        wa = rec("Rob Chase", image="https://robchase.houserepublicans.wa.gov/wp-content/uploads/"
                 "2025/01/Rep-Chase_Rob-2025_900x1200.jpg", party="Republican", partyKey="R")
        self.assertEqual(legislature.caucus_photo("WA", wa, wa["image"]),
                         "Washington State House Republicans")
        gop = rec("Joe Bellino", chamber="upper", party="Republican", partyKey="R",
                  image="https://www.misenategop.com/wp-content/uploads/2023/01/Bellino-580x770.jpg")
        self.assertEqual(legislature.caucus_photo("MI", gop, gop["image"]),
                         "Michigan Senate Republicans")
        # And its page there is the caucus's page of them, by the same test
        # (the PR #139 review: the 18 cards on www.misenategop.com were
        # credited to the caucus with no link to its page of them).
        self.assertEqual(legislature._caucus_site("MI", "www.misenategop.com", "/bellino/",
                                                  "upper"), "Michigan Senate Republicans")
        self.assertIsNone(legislature._caucus_site("MI", "notmisenategop.com", "/bellino/",
                                                   "upper"))
        self.assertTrue(legislature.on_caucus_host("www.misenategop.com", "misenategop.com"))
        self.assertTrue(legislature.on_caucus_host("a14.asmdc.org", ".asmdc.org"))
        self.assertFalse(legislature.on_caucus_host("evilmisenategop.com", "misenategop.com"))

    def test_another_partys_or_chambers_caucus_or_a_shared_file_is_not_credited_to_it(self):
        image = "https://www.indianahouserepublicans.com/clientuploads/directory/members/Main_List/X.jpg"
        independent = rec("Pat Smith", party="Independent", partyKey="I", image=image)
        self.assertIsNone(legislature.caucus_photo("IN", independent, image))
        out = legislature._person(independent, "IN", 2026, pages={independent["id"]: None},
                                  photos={"people": {}})
        self.assertEqual(out["imageCredit"], {"host": "www.indianahouserepublicans.com",
                                              "listedBy": "Open States"})
        # The House caucus's file of a senator is not the Senate caucus's.
        senator = rec("Pat Smith", chamber="upper", party="Republican", partyKey="R", image=image)
        self.assertIsNone(legislature.caucus_photo("IN", senator, image))
        # Another state's caucus of the same name is not this state's.
        mccann = rec("Sean McCann", chamber="upper", image=self.MCCANN)
        self.assertIsNone(legislature.caucus_photo("OH", mccann, self.MCCANN))
        # A file Open States gives two members is neither's (rule 100),
        # and one whose name calls it a group's or a leader's is not one
        # member's own.
        self.assertIsNone(legislature.caucus_photo("MI", dict(mccann, imageShared=True),
                                                   self.MCCANN))
        for name in ("Senate-Democratic-Leadership-2025.jpg", "caucus_group_photo.jpg",
                     "Leader-Brinks-banner.jpg"):
            url = "https://senatedems.com/wp-content/uploads/2025/01/" + name
            self.assertIsNone(legislature.caucus_photo("MI", dict(mccann, image=url), url), name)

    def test_a_host_not_in_the_table_reads_as_where_open_states_found_it(self):
        # New Hampshire's House Dems Victory Committee is a campaign
        # committee, not the caucus: never credited as one.
        member = rec("Terri O'Rorke", image="https://nhhousedems.org/wp-content/uploads/2024/10/"
                     "Terri-ORorke-768x1024.jpeg")
        out = legislature._person(member, "NH", 2026, pages={member["id"]: None},
                                  photos={"people": {}})
        self.assertEqual(out["imageCredit"], {"host": "nhhousedems.org", "listedBy": "Open States"})

    def test_every_caucus_in_the_table_says_its_party_and_its_evidence(self):
        for code, sites in legislature.CAUCUS_SITES.items():
            for host, prefix, chamber, name, party, evidence in sites:
                self.assertIn(chamber, ("upper", "lower"), host)
                self.assertIn(party, ("D", "R"), host)
                self.assertTrue(prefix.startswith("/") and name, host)
                # Its own page's title, or why none could be read, and the day.
                self.assertRegex(evidence, r"2026-\d\d-\d\d", host)
                # The caucus's name names its party.
                self.assertRegex(name, {"D": "Democrat", "R": "Republican"}[party], host)

    def test_the_build_names_a_member_the_legislature_says_has_left(self):
        member = rec("D.J. Swearingen", district="89")
        cache = {"people": {member["id"]: {"withheld": "the chamber's directory lists the seat as vacant",
                                           "notSeated": "the chamber's directory lists the seat as vacant",
                                           "read": TODAY}}}
        found = [(level, c, m) for level, c, m in legphotos.problems(cache, {"OH": [member]})]
        self.assertEqual([(level, c) for level, c, _ in found], [("warn", "legislator-not-seated")])
        self.assertIn("Swearingen", found[0][2])

    def test_one_photograph_shown_for_two_members_fails_the_build(self):
        a, b = rec("Neil Duram"), rec("Pat Duram", pid="ocd-person/pat")
        cache = {"people": {a["id"]: self.entry(), b["id"]: self.entry(name="Pat Duram")}}
        found = [c for level, c, _ in legphotos.problems(cache, {"MT": [a, b]}) if level == "error"]
        self.assertEqual(found, ["legislator-photo-shared"])

    def test_one_open_states_file_for_two_members_is_shown_for_neither(self):
        # Open States gave Arkansas's Ashley Hudson (House 75) the file the
        # legislature serves for Andrew Collins (House 73), and the card
        # credited a man's portrait to the Arkansas General Assembly as
        # hers (the PR #133 review).
        from kyc import statelegs
        image = "https://www.arkleg.state.ar.us/Content/photos/2023/House/566_sm.jpg"
        hudson = rec("Ashley Hudson", district="75", image=image)
        collins = rec("Andrew Collins", district="73", image=image.replace("https://", "http://"))
        other = rec("Pat Smith", district="1", image="https://www.arkleg.state.ar.us/Content/photos/x.jpg")
        states = statelegs.mark_shared_images({"AR": [hudson, collins, other]})
        self.assertTrue(hudson["imageShared"] and collins["imageShared"])
        self.assertNotIn("imageShared", other)
        self.assertFalse(legphotos.open_states_image_ok(hudson))
        self.assertTrue(legphotos.open_states_image_ok(other))
        dropped = {}
        out = legislature._person(hudson, "AR", 2026, dropped=dropped, photos={"people": {}})
        self.assertNotIn("image", out)
        self.assertNotIn("imageCredit", out)
        self.assertEqual(dropped, {"sharedImage": 1})
        # The legislature's own photograph of her, read by legphotos,
        # stands in its place.
        own = self.entry(name="Ashley Hudson", image="https://arkleg.state.ar.us/Content/photos/2025/House/597_sm.jpg",
                         page="https://arkleg.state.ar.us/Legislators/Detail?member=Hudson",
                         evidence="alt \"Photo of Representative Hudson\"", credit="Arkansas General Assembly")
        out = legislature._person(hudson, "AR", 2026, photos={"people": {hudson["id"]: own}})
        self.assertEqual(out["image"], own["image"])
        # It is said, and the flag never reaches the committed cache.
        found = [c for level, c, _ in legphotos.problems({"people": {}}, states) if level == "warn"]
        self.assertIn("legislator-openstates-photo-shared", found)
        self.assertIn(hudson, legphotos.needing(states)["AR"])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, os.path.dirname(statelegs.CACHE_PATH)))
            statelegs.save_cache(states, tmp, fetched="2026-10-25T00:00:00+00:00")
            with open(os.path.join(tmp, statelegs.CACHE_PATH), encoding="utf-8") as handle:
                self.assertNotIn("imageShared", handle.read())
            self.assertTrue(any(r.get("imageShared") for r in statelegs.load_cache(tmp)["states"]["AR"]))

    def test_no_committed_open_states_portrait_is_shown_for_two_members(self):
        from kyc import statelegs
        roster = statelegs.load_cache(ROOT)
        if not roster:
            self.skipTest("no state_legislators.json")
        photos = legphotos.load_cache(ROOT)
        seen = {}
        for code, rows in roster["states"].items():
            for r in rows:
                out = legislature._person(r, code, 2026, photos=photos, pages={})
                if out.get("image"):
                    seen.setdefault(out["image"].lower(), []).append(f"{code} {r['name']}")
        self.assertEqual({k: v for k, v in seen.items() if len(v) > 1}, {})

    def test_validate_fails_a_photograph_without_its_evidence_weight_or_host(self):
        member = rec("Neil Duram")
        states = {"MT": [member]}
        self.assertEqual(legphotos.problems({"people": {member["id"]: self.entry()}}, states), [])
        for broken, code in ((self.entry(evidence=""), "legislator-photo-unsourced"),
                             (self.entry(evidence="the roster: Pat Smith"), "legislator-photo-unnamed"),
                             (self.entry(image="https://example.com/a.jpg"), "legislator-photo-host"),
                             (self.entry(bytes=400_000), "legislator-photo-heavy"),
                             (self.entry(seatKeyed=True), "legislator-photo-seat")):
            found = [c for level, c, _ in legphotos.problems({"people": {member["id"]: broken}}, states)
                     if level == "error"]
            self.assertIn(code, found, broken)

    def test_the_committed_cache_passes_its_own_checks(self):
        cache = legphotos.load_cache(ROOT)
        from kyc import statelegs
        roster = statelegs.load_cache(ROOT)
        if not cache.get("people") or not roster:
            self.skipTest("no legislator_photos.json")
        errors = [m for level, _, m in legphotos.problems(cache, roster["states"]) if level == "error"]
        self.assertEqual(errors, [])
        today = datetime.date.today().isoformat()
        for entry in cache["people"].values():
            if entry.get("image"):
                self.assertLessEqual(entry["read"], today)
