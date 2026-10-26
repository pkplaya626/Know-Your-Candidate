"""Tests for the statewide officers: the NASS, NLGA and RAGA roster readers
(kyc/officers.py) and what the page is given for each state.

Each roster is the authority on its own members; where two name the holder
of one office they must agree, or neither name is shown.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import officers, stategov  # noqa: E402
from kyc.government_maps import STATES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def nass_entry(state, name, title, extra="", photo="AL-Allen-2023.jpg"):
    return f"""
<article class="secretary {state.lower()}" id="{state.lower()}">
	<img src="/sites/default/files/styles/secretary/public/2023-01/{photo}?itok=x" alt="{state} state seal">
	<h2><a href="https://sos.example.gov/">{state}</a></h2>
	<p><strong><a href="https://sos.example.gov/bio">{name}</a></strong></p>
	<p>{title}</p>
	<p>PO Box 5616 Montgomery, AL 36103-5616</p>
	<p>(334) 242-7200</p>
	<p><a href="mailto:office@sos.example.gov">office@sos.example.gov</a></p>{extra}
</article>"""


def nlga_entry(state, heading, srcset="https://i0.wp.com/nlga.us/x.jpg?w=400 400w, "
                                      "https://i0.wp.com/nlga.us/x.jpg?resize=150%2C150 150w"):
    return f"""
<h2 class="elementor-heading-title elementor-size-default">{state}</h2></div></div>
<div><img loading="lazy" src="https://i0.wp.com/nlga.us/x.jpg" srcset="{srcset}" alt="" /></div>
<h3 class="elementor-heading-title elementor-size-default">{heading}</h3></div></div>
<ul class="elementor-icon-list-items"><li class="elementor-icon-list-item">
<a href="https://ltgov.example.gov/" target="_blank">
<span class="elementor-icon-list-text">Website (Bio &amp; Contact Info)</span></a></li></ul>"""


def raga_card(name, state):
    return f"""<div class="card-ags"><h2 class="entry-title text-uppercase mb-0">
<a href="https://republicanags.com/ags/x/">{name}</a></h2>
                      <p class="state mb-0 h1">{state}</p></div>"""


class TestRosters(unittest.TestCase):

    def test_a_nass_entry(self):
        page = nass_entry("Alabama (CEO)", "Wes Allen (R)", "Secretary of State - Elected")
        rows = officers.parse_nass(page * 1 + "".join(
            nass_entry(s, f"Someone {i} (D)", "Secretary of State - Appointed")
            for i, s in enumerate(["Texas", "Ohio"])) + "".join(
            nass_entry(name.title(), "A B (R)", "Secretary of State - Elected")
            for name in __import__("kyc.normalize", fromlist=["US_STATES"]).US_STATES
            if name.title() not in ("Alabama", "Texas", "Ohio")))
        al = rows["AL"]
        self.assertEqual((al["name"], al["party"], al["title"], al["selection"], al["electionChief"]),
                         ("Wes Allen", "R", "Secretary of State", "Elected", True))
        self.assertEqual(al["phone"], "(334) 242-7200")
        self.assertEqual(al["email"], "office@sos.example.gov")
        self.assertTrue(al["photo"].startswith("https://www.nass.org/sites/default/files/"))
        self.assertFalse(rows["TX"]["electionChief"])

    def test_names_and_parties(self):
        self.assertEqual(officers.name_and_party("Wes Allen (R)"), ("Wes Allen", "R"))
        self.assertEqual(officers.name_and_party("Hon. Rosachely Rivera Santana (R)"),
                         ("Rosachely Rivera Santana", "R"))
        self.assertEqual(officers.name_and_party("Vacant"), (None, None))

    def test_abbreviated_jurisdictions(self):
        self.assertEqual(officers.jurisdiction("Amer. Samoa*"), "AS")
        self.assertEqual(officers.jurisdiction("Dist. of Columbia"), "DC")
        self.assertEqual(officers.jurisdiction("N. Mariana Islands"), "MP")
        self.assertEqual(officers.jurisdiction("Alabama (CEO)"), "AL")
        with self.assertRaises(officers.OfficersError):
            officers.jurisdiction("Atlantis")

    def test_an_nlga_entry_takes_the_smallest_size_of_its_one_photo(self):
        from kyc.normalize import US_STATES
        photo = ("https://i0.wp.com/nlga.us/Will-Ainsworth.jpg?w=400 400w, "
                 "https://i0.wp.com/nlga.us/Will-Ainsworth.jpg?resize=150%2C150 150w")
        page = nlga_entry("Alabama", "Will Ainsworth (R), Lieutenant Governor", srcset=photo) + "".join(
            nlga_entry(n.title(), "A B (D), Lieutenant Governor") for n in US_STATES if n != "ALABAMA")
        rows = officers.parse_nlga(page)
        self.assertEqual(rows["AL"]["photo"], "https://i0.wp.com/nlga.us/Will-Ainsworth.jpg?resize=150%2C150")
        self.assertEqual(rows["AL"]["website"], "https://ltgov.example.gov/")

    def test_raga_placeholders_and_invisible_characters(self):
        cards = (raga_card("J.B. McCuskey", "West Virginia") +
                 raga_card("J.B. McCuskey​", "West Virginia") +
                 raga_card("Maryland", "Maryland") +
                 "".join(raga_card(f"Person {i}", s) for i, s in enumerate(
                     ["Texas", "Ohio", "Iowa", "Idaho", "Utah", "Kansas", "Kentucky", "Alabama",
                      "Alaska", "Arkansas", "Florida", "Georgia", "Indiana", "Louisiana",
                      "Missouri", "Montana", "Nebraska", "Oklahoma", "South Carolina",
                      "South Dakota"])))
        rows = officers.parse_raga(cards)
        self.assertEqual(rows["WV"]["name"], "J.B. McCuskey")
        self.assertNotIn("MD", rows)

    def test_two_people_for_one_state_stop_the_read(self):
        cards = raga_card("Ann One", "Texas") + raga_card("Bob Two", "Texas")
        with self.assertRaises(officers.OfficersError):
            officers.parse_raga(cards)


class TestForState(unittest.TestCase):

    CACHE = {
        "sos": {
            "AZ": {"name": "Adrian Fontes", "party": "D", "partyKey": "D", "title": "Secretary of State",
                   "selection": "Elected", "electionChief": True, "website": "https://azsos.gov/"},
            "HI": {"name": "Sylvia Luke", "party": "D", "partyKey": "D", "title": "Lieutenant Governor",
                   "selection": "Elected", "electionChief": False},
            "UT": {"name": "Deidre Henderson", "party": "R", "partyKey": "R",
                   "title": "Lieutenant Governor", "selection": "Elected", "electionChief": True},
            "PR": {"name": "High Chief Rosachely Rivera Santana", "party": "R", "partyKey": "R",
                   "title": "Secretary of State", "selection": "Appointed", "electionChief": False},
        },
        "lt": {
            "AZ": {"name": "Adrian Fontes", "party": "D", "partyKey": "D", "title": "Secretary of State"},
            "HI": {"name": "Keith Regan", "party": "D", "partyKey": "D",
                   "title": "Acting Lieutenant Governor"},
            "UT": {"name": "Deidre Henderson", "party": "R", "partyKey": "R",
                   "title": "Lieutenant Governor"},
            "NJ": {"title": "Lieutenant Governor", "vacant": True},
            "PR": {"name": "Rosachely Rivera Santana", "party": "R", "partyKey": "R",
                   "title": "Secretary of State"},
        },
    }

    def test_overlapping_rosters_must_name_the_same_person(self):
        disputes = officers.overlaps(self.CACHE["sos"], self.CACHE["lt"])
        self.assertEqual(disputes, [("HI", "Lieutenant Governor", "Sylvia Luke (D)", "Keith Regan (D)")])

    def test_what_the_page_is_given(self):
        disputes = officers.overlaps(self.CACHE["sos"], self.CACHE["lt"])
        hi = officers.for_state("HI", self.CACHE, disputes)
        self.assertEqual(hi["lt"], {"disputed": ["Sylvia Luke (D)", "Keith Regan (D)"]})
        self.assertNotIn("name", hi["lt"])
        self.assertEqual(hi["sos"], {"none": True, "electionChief": ""})
        az = officers.for_state("AZ", self.CACHE, disputes)
        self.assertTrue(az["lt"]["none"])
        self.assertEqual(az["lt"]["successor"]["title"], "Secretary of State")
        self.assertEqual(az["sos"]["name"], "Adrian Fontes")
        self.assertEqual(officers.for_state("NJ", self.CACHE, disputes)["lt"],
                         {"vacant": True, "title": "Lieutenant Governor"})
        ut = officers.for_state("UT", self.CACHE, disputes)
        self.assertEqual(ut["sos"]["electionChief"], "lieutenant governor")
        self.assertEqual(ut["lt"]["name"], "Deidre Henderson")

    def test_acting_titles_are_the_same_office(self):
        self.assertEqual(officers.office_of("Acting Lt. Governor"), "Lieutenant Governor")
        self.assertEqual(officers.office_of("Lieutenant Governor/Senate President"), "Lieutenant Governor")
        self.assertEqual(officers.office_of("Acting Secretary of State"), "Secretary of State")
        self.assertEqual(officers.office_of("Secretary of the Commonwealth"), "Secretary of State")
        self.assertIsNone(officers.office_of("Senate President"))

    def test_an_acting_lieutenant_governor_is_never_a_secretary_of_state(self):
        cache = {"sos": {"HI": dict(self.CACHE["sos"]["HI"], name="Keith Regan",
                                    title="Acting Lieutenant Governor")},
                 "lt": {"HI": self.CACHE["lt"]["HI"]}}
        hi = officers.for_state("HI", cache, officers.overlaps(cache["sos"], cache["lt"]))
        self.assertTrue(hi["sos"]["none"])
        self.assertEqual(officers.overlaps(cache["sos"], cache["lt"]), [])

    def test_an_acting_title_is_still_cross_checked(self):
        sos = {"AZ": dict(self.CACHE["sos"]["AZ"], name="Jane Doe", party="R", partyKey="R",
                          title="Acting Secretary of State")}
        disputes = officers.overlaps(sos, {"AZ": self.CACHE["lt"]["AZ"]})
        self.assertEqual([d[:2] for d in disputes], [("AZ", "Secretary of State")])
        az = officers.for_state("AZ", {"sos": sos, "lt": {"AZ": self.CACHE["lt"]["AZ"]}}, disputes)
        # Neither name stands for the office, so neither is first in line.
        self.assertEqual(az["lt"], {"none": True})
        self.assertIn("disputed", az["sos"])

    def test_a_vacant_office_first_in_line_is_not_a_vacant_lieutenant_governor(self):
        lt = {"OR": {"title": "Secretary of State", "vacant": True}}
        self.assertEqual(officers.for_state("OR", {"sos": {}, "lt": lt}, [])["lt"], {"none": True})

    def test_a_nass_entry_for_a_non_member_does_not_override_nlgas_member(self):
        # NASS's Hawaii entry, marked "* Currently Not a NASS Member", named
        # the lieutenant governor NLGA's member had replaced.
        sos = {"HI": dict(self.CACHE["sos"]["HI"], member=False)}
        disputes = officers.overlaps(sos, {"HI": self.CACHE["lt"]["HI"]})
        self.assertEqual(disputes, [])
        hi = officers.for_state("HI", {"sos": sos, "lt": {"HI": self.CACHE["lt"]["HI"]}}, disputes)
        self.assertEqual(hi["lt"]["name"], "Keith Regan")

    def test_a_secretary_listed_for_a_non_member_is_marked_so(self):
        sos = {"FL": {"name": "Cord Byrd", "party": "R", "partyKey": "R", "title": "Secretary of State",
                      "selection": "Appointed", "electionChief": True, "member": False}}
        self.assertTrue(officers.for_state("FL", {"sos": sos, "lt": {}}, [])["sos"]["notMember"])

    def test_an_nlga_logo_is_not_a_portrait(self):
        from kyc.normalize import US_STATES
        logo = ("https://i0.wp.com/nlga.us/wp-content/uploads/2025/04/NLGALogo-copy.png?w=400 400w, "
                "https://i0.wp.com/nlga.us/wp-content/uploads/2025/04/NLGALogo-copy.png?resize=150%2C150 150w")
        page = nlga_entry("New Jersey", "Jane Doe (D), Lieutenant Governor", srcset=logo) + "".join(
            nlga_entry(n.title(), "A B (D), Lieutenant Governor") for n in US_STATES if n != "NEW JERSEY")
        self.assertNotIn("photo", officers.parse_nlga(page)["NJ"])

    def test_an_nlga_card_with_only_a_src_keeps_its_photo(self):
        # Virginia's card carried a plain src, no srcset, and Ghazala
        # Hashmi lost her photograph (STATEGOV-13). The host's own resizer
        # gives the same file at 300px.
        from kyc.normalize import US_STATES
        card = nlga_entry("Virginia", "Ghazala Hashmi (D), Lieutenant Governor").replace(
            'src="https://i0.wp.com/nlga.us/x.jpg" srcset="'
            'https://i0.wp.com/nlga.us/x.jpg?w=400 400w, '
            'https://i0.wp.com/nlga.us/x.jpg?resize=150%2C150 150w"',
            'src="https://i0.wp.com/nlga.us/wp-content/uploads/2026/03/Hashmi1.jpg?w=800&#038;ssl=1"')
        page = card + "".join(nlga_entry(n.title(), "A B (D), Lieutenant Governor")
                              for n in US_STATES if n != "VIRGINIA")
        self.assertEqual(officers.parse_nlga(page)["VA"]["photo"],
                         "https://i0.wp.com/nlga.us/wp-content/uploads/2026/03/Hashmi1.jpg"
                         "?ssl=1&w=300")

    def test_a_roster_photograph_says_whose_it_is(self):
        cache = {"lt": {"AL": {"name": "Will Ainsworth", "party": "R", "partyKey": "R",
                               "title": "Lieutenant Governor",
                               "photo": "https://i0.wp.com/nlga.us/Will-Ainsworth.jpg"}},
                 "sos": {"AL": {"name": "Wes Allen", "party": "R", "partyKey": "R",
                                "title": "Secretary of State", "electionChief": True,
                                "photo": "https://www.nass.org/AL-Allen-2023.jpg"}},
                 "ag": {"AL": {"name": "Steve Marshall"}}}
        out = officers.for_state("AL", cache, [])
        self.assertEqual(out["lt"]["photoBy"], officers.NLGA_BY)
        self.assertEqual(out["sos"]["photoBy"], officers.NASS_BY)
        out["ag"]["photo"] = "x"
        self.assertNotIn("photo", cache["ag"]["AL"])   # the cache is not written through

    def test_a_nass_photo_must_carry_the_surname(self):
        self.assertTrue(officers._surname_in("Wes Allen", "https://x/AL-Allen-2023.jpg?itok=1"))
        self.assertFalse(officers._surname_in("Steve Simon", "https://x/MN-SOS-2023.jpg"))
        self.assertTrue(officers._surname_in("Pulu Ae Ae Jr.", "https://x/Pulu-Ae-Ae-Samoa.png"))


class TestAttorneysGeneral(unittest.TestCase):

    def test_a_name_counts_only_beside_the_title(self):
        page = ("Office of the New York Attorney General Letitia James. Kris Mayes, Attorney "
                "General. Attorney General Griffin Announces. AG Liz Murrill's Office. "
                "Secretary of the Commonwealth Candi Mundon King")
        for name in ("Letitia James", "Kris Mayes", "Tim Griffin", "Liz Murrill"):
            self.assertTrue(officers.names_attorney_general(name, page), name)
        # A nickname the office does not use, and a stranger, are not a match.
        self.assertFalse(officers.names_attorney_general("Tish James", page))
        self.assertFalse(officers.names_attorney_general("Dan Bishop", page))
        # The name far from the title is not a match.
        self.assertFalse(officers.names_attorney_general(
            "Jane Doe", "Jane Doe" + " lorem ipsum" * 20 + " Attorney General"))
        self.assertTrue(officers.names_holder("Candi Mundon King", page, "sos"))
        self.assertTrue(officers.names_holder("Sarah Godlewski", "Secretary Godlewski said", "sos"))

    def test_a_predecessor_or_neighbour_is_not_the_holder(self):
        # Each of these confirmed the wrong person with an 80-character window.
        cases = [
            ("Treg Taylor", "About the acting attorney general Cori Mills. Former attorney general "
                            "Treg Taylor asked if she would serve", "AK"),
            ("Josh Stein", "Governor Josh Stein and Attorney General Jeff Jackson announce", "NC"),
            ("Dan Bishop", "Jeff Jackson defeated Dan Bishop to become attorney general", "NC"),
            ("Dan Bishop", "Former Attorney General Dan Bishop", "NC"),
            ("Jane Smith", "Commissioner of Ag Jane Smith", "NC"),
        ]
        for name, page, code in cases:
            self.assertFalse(officers.names_attorney_general(name, page, code), name)
        # The state's own name and an ordinal may stand between name and title.
        self.assertTrue(officers.names_attorney_general(
            "Phil Weiser", "Phil Weiser Colorado Attorney General", "CO"))
        self.assertTrue(officers.names_attorney_general(
            "Alan Wilson", "Alan Wilson, South Carolina's 51st Attorney General", "SC"))

    def test_a_name_in_an_html_comment_is_not_on_the_page(self):
        # North Carolina's page keeps its previous holder commented out.
        page = ("<html><body><!-- <div>Attorney General Josh Stein</div> -->"
                "<p>Attorney General Jeff Jackson</p></body></html>")
        text = officers.visible_text(page)
        self.assertFalse(officers.names_attorney_general("Josh Stein", text, "NC"))
        self.assertTrue(officers.names_attorney_general("Jeff Jackson", text, "NC"))

    def test_acting_is_the_title_directly_before_the_name(self):
        self.assertFalse(officers.acting("Jeff Jackson", "A bill enacting Attorney General Jackson's proposals"))
        self.assertFalse(officers.acting("Ken Paxton", "Attorney General Paxton thanked Acting Attorney "
                                                       "General Angela Colmenero"))

    def test_acting_is_read_from_the_office(self):
        page = "About the Acting Attorney General Cori Mills"
        self.assertTrue(officers.acting("Cori Mills", page))
        self.assertFalse(officers.acting("Cori Mills", "Attorney General Cori Mills"))

    RAGA = {"NC": {"name": "Dan Bishop"}, "NH": {"name": "John Formella"},
            "TX": {"name": "Ken Paxton"}, "OH": {"name": "Andy Wilson"}}
    DAGA = {"NC": {"name": "Jeff Jackson"}, "NY": {"name": "Tish James"},
            "MA": {"name": "Andrea Campbell"}}

    def _rows(self, texts):
        return officers.attorneys_general(self.RAGA, self.DAGA, texts)

    def test_the_office_settles_which_association_is_right(self):
        # RAGA listed for North Carolina the Republican Jeff Jackson beat in
        # 2024; the office's page names Jackson.
        rows, problems = self._rows({"NC": ("https://ncdoj.gov/", "Attorney General Jeff Jackson")})
        self.assertEqual((rows["NC"]["name"], rows["NC"]["party"]), ("Jeff Jackson", "D"))
        self.assertTrue(any("Dan Bishop" in p for p in problems))

    def test_an_association_spelling_the_office_does_not_use_needs_a_form(self):
        rows, _ = self._rows({"NY": ("https://ag.ny.gov/", "Attorney General Letitia James")})
        self.assertEqual(rows["NY"]["name"], "Letitia James")

    def test_an_unreadable_office_leaves_the_listing_attributed(self):
        rows, problems = self._rows({"NH": ("https://www.doj.nh.gov/", None)})
        nh = rows["NH"]
        self.assertTrue(nh["unconfirmed"])
        self.assertEqual(nh["listedBy"], "Republican Attorneys General Association")
        self.assertEqual(nh["selection"], "Appointed by the governor and Executive Council")
        self.assertTrue(problems)

    def test_two_listings_and_an_unreadable_office_is_a_dispute(self):
        rows, _ = self._rows({"NC": ("https://ncdoj.gov/", None)})
        self.assertEqual(rows["NC"]["disputed"], ["Dan Bishop (R)", "Jeff Jackson (D)"])

    def test_two_listings_and_a_page_naming_neither_is_a_dispute(self):
        rows, _ = self._rows({"NC": ("https://ncdoj.gov/", "Welcome to the Department of Justice. " * 20)})
        self.assertEqual(rows["NC"]["disputed"], ["Dan Bishop (R)", "Jeff Jackson (D)"])
        self.assertNotIn("name", rows["NC"])

    def test_an_unconfirmed_listing_says_why(self):
        rows, _ = self._rows({"NH": ("https://www.doj.nh.gov/", None),
                              "TX": ("https://www.texasattorneygeneral.gov/", "Attorney General Someone Else")})
        self.assertTrue(rows["NH"]["unreadable"])
        self.assertNotIn("unreadable", rows["TX"])

    def test_a_state_neither_association_lists_says_so(self):
        rows, problems = self._rows({})
        self.assertTrue(rows["WY"]["unlisted"])
        self.assertTrue(any(p.startswith("WY:") for p in problems))

    def test_a_listing_the_office_does_not_name_is_not_shown_as_fact(self):
        rows, _ = self._rows({"TX": ("https://www.texasattorneygeneral.gov/", "Attorney General Someone Else")})
        self.assertTrue(rows["TX"]["unconfirmed"])

    def test_dagas_roster_and_usagovs_link(self):
        page = ('<a class="profile-card"\n   href="https://dems.ag/profile/raul-torrez/"\n   '
                'title="Ra&uacute;l  Torrez">\n<div><h1>Ra&uacute;l <br>Torrez</h1>'
                '<p class="profile-card__copy">New Mexico</p></div></a>') * 1
        filler = "".join(f'<a class="profile-card" href="https://dems.ag/p/{i}/" title="Person {i}">'
                         f'<p class="profile-card__copy">{s}</p></a>' for i, s in enumerate(
                             ["Arizona", "California", "Colorado", "Connecticut", "Delaware",
                              "Hawaii", "Illinois", "Maine", "Maryland", "Massachusetts",
                              "Michigan", "Minnesota", "Nevada", "New Jersey", "New York"]))
        rows = officers.parse_daga(page + filler)
        self.assertEqual(rows["NM"]["name"], "Raúl Torrez")
        usagov = ('<li class="field field--name-field-state-attorney-general field--type-link">\n'
                  '<a href="https://www.texasattorneygeneral.gov/">Office of the Attorney General</a></li>')
        self.assertEqual(officers.usagov_office(usagov), "https://www.texasattorneygeneral.gov/")
        with self.assertRaises(officers.OfficersError):
            officers.usagov_office("<p>nothing here</p>")

    def test_a_page_drawn_by_javascript_concludes_nothing(self):
        saved = officers._get
        officers._get = lambda url, timeout=60: "<html><body><div id=app></div></body></html>"
        try:
            self.assertIsNone(officers._office_text("https://example.gov/", 0))
        finally:
            officers._get = saved

    def test_a_non_member_secretary_the_office_names_is_confirmed(self):
        saved = officers._get
        officers._get = lambda url, timeout=60: ("<html><body>" + "Welcome. " * 40 +
                                                 "Secretary of State Cord Byrd</body></html>")
        try:
            sos = officers.confirm_non_members({"FL": {
                "name": "Cord Byrd", "party": "R", "partyKey": "R", "title": "Secretary of State",
                "member": False, "website": "https://dos.fl.gov/"}}, pause=0)
        finally:
            officers._get = saved
        self.assertTrue(sos["FL"]["officeConfirms"])
        page = officers.for_state("FL", {"sos": sos, "lt": {}}, [])
        self.assertNotIn("notMember", page["sos"])


class TestKeptConfirmations(unittest.TestCase):
    """A confirmation is the office's word on the day its page was read. On
    2026-10-20, -21 and -22 ncdoj.gov did not answer, and North Carolina's
    page said "The sources disagree: Dan Bishop (R); Jeff Jackson (D)" - RAGA
    still lists the man who lost the 2024 election - though the office had
    named Jeff Jackson on every read before. An office's site that
    concludes nothing (rule 8) keeps its last confirmation while nothing
    read since contradicts it."""

    RAGA = {"NC": {"name": "Dan Bishop"}, "NH": {"name": "John Formella"}}
    DAGA = {"NC": {"name": "Jeff Jackson"}}
    NC = {"listedBy": "Democratic Attorneys General Association", "name": "Jeff Jackson",
          "office": "https://ncdoj.gov/", "party": "D", "partyKey": "D",
          "title": "Attorney General", "photo": "https://ncdoj.gov/jackson.jpg",
          "photoPage": "https://ncdoj.gov/about/"}
    NH = {"listedBy": "Republican Attorneys General Association", "name": "John Formella",
          "office": "https://www.doj.nh.gov/", "party": "R", "partyKey": "R",
          "title": "Attorney General", "selection": "Appointed by the governor and Executive Council"}
    DOWN = {"NC": ("https://ncdoj.gov/", None), "NH": ("https://www.doj.nh.gov/", None)}

    def rows(self, texts, previous, day="2026-10-25", raga=None, daga=None, today="2026-10-26"):
        return officers.attorneys_general(self.RAGA if raga is None else raga,
                                          self.DAGA if daga is None else daga, texts,
                                          previous, day, today)

    def test_a_confirming_read_records_its_day_and_what_else_was_listed(self):
        rows, _ = self.rows({"NC": ("https://ncdoj.gov/", "Attorney General Jeff Jackson")}, None)
        self.assertEqual(rows["NC"]["confirmedOn"], "2026-10-26")
        self.assertEqual(rows["NC"]["alsoListed"], ["Dan Bishop (R)"])
        self.assertNotIn("confirmationKept", rows["NC"])
        rows, _ = self.rows({"NH": ("https://www.doj.nh.gov/", "Attorney General John Formella")}, None)
        self.assertEqual(rows["NH"]["alsoListed"], [])

    def test_north_carolina_is_kept_not_disputed(self):
        previous = {"NC": dict(self.NC, confirmedOn="2026-10-19", alsoListed=["Dan Bishop (R)"])}
        rows, problems = self.rows(self.DOWN, previous)
        nc = rows["NC"]
        self.assertNotIn("disputed", nc)
        self.assertEqual((nc["name"], nc["party"]), ("Jeff Jackson", "D"))
        self.assertEqual(nc["confirmedOn"], "2026-10-19")
        self.assertTrue(nc["confirmationKept"])
        self.assertTrue(any(p.startswith("NC: the office's site could not be read; its "
                                         "confirmation of Jeff Jackson on 2026-10-19 is kept")
                            for p in problems), problems)

    def test_a_two_listing_row_from_before_this_is_still_a_dispute(self):
        # No alsoListed: nobody recorded whether that read saw Dan Bishop.
        rows, _ = self.rows(self.DOWN, {"NC": dict(self.NC)})
        self.assertEqual(rows["NC"]["disputed"], ["Dan Bishop (R)", "Jeff Jackson (D)"])

    def test_a_one_listing_row_from_before_this_is_kept_on_the_caches_day(self):
        rows, problems = self.rows(self.DOWN, {"NH": dict(self.NH)}, day="2026-10-25")
        nh = rows["NH"]
        self.assertEqual(nh["name"], "John Formella")
        self.assertNotIn("unconfirmed", nh)
        self.assertEqual(nh["confirmedOn"], "2026-10-25")
        self.assertTrue(any("confirmation of John Formella on 2026-10-25 is kept" in p
                            for p in problems))
        # Without the cache's day it cannot be dated, and is not kept.
        rows, _ = self.rows(self.DOWN, {"NH": dict(self.NH)}, day=None)
        self.assertTrue(rows["NH"]["unconfirmed"] and rows["NH"]["unreadable"])

    def test_the_day_is_never_restamped(self):
        first, _ = self.rows(self.DOWN, {"NH": dict(self.NH)}, day="2026-10-25")
        second, _ = self.rows(self.DOWN, first, day="2026-10-26", today="2026-10-27")
        third, _ = self.rows(self.DOWN, second, day="2026-10-27", today="2026-10-28")
        self.assertEqual(third["NH"]["confirmedOn"], "2026-10-25")
        self.assertTrue(third["NH"]["confirmationKept"])
        # A read that answers confirms afresh, on its own day.
        fresh, _ = self.rows({"NH": ("https://www.doj.nh.gov/", "Attorney General John Formella")},
                             third, today="2026-10-29")
        self.assertEqual(fresh["NH"]["confirmedOn"], "2026-10-29")
        self.assertNotIn("confirmationKept", fresh["NH"])

    def test_anything_read_since_that_contradicts_it_is_not_kept(self):
        nc = {"NC": dict(self.NC, confirmedOn="2026-10-19", alsoListed=["Dan Bishop (R)"])}
        nh = {"NH": dict(self.NH, confirmedOn="2026-10-19", alsoListed=[])}
        # A new name at the association.
        rows, _ = self.rows(self.DOWN, nh, raga={"NH": {"name": "Jane Roe"}})
        self.assertTrue(rows["NH"]["unconfirmed"])
        self.assertEqual(rows["NH"]["name"], "Jane Roe")
        # The same name listed by the other association: another party.
        rows, _ = self.rows(self.DOWN, nh, raga={}, daga={"NH": {"name": "John Formella"}})
        self.assertTrue(rows["NH"]["unconfirmed"])
        self.assertEqual(rows["NH"]["party"], "D")
        # A listing the confirming read did not see.
        rows, _ = self.rows(self.DOWN, nh, daga={"NH": {"name": "Pat Doe"}})
        self.assertEqual(rows["NH"]["disputed"], ["John Formella (R)", "Pat Doe (D)"])
        rows, _ = self.rows(self.DOWN, nc, raga={"NC": {"name": "Someone New"}})
        self.assertIn("disputed", rows["NC"])
        # The same holder, through an evidenced spelling, is the same holder.
        ny = {"NY": {"listedBy": "Democratic Attorneys General Association",
                     "name": "Letitia James", "party": "D", "partyKey": "D",
                     "title": "Attorney General", "confirmedOn": "2026-10-19", "alsoListed": []}}
        rows, _ = self.rows({"NY": ("https://ag.ny.gov/", None)}, ny, raga={},
                            daga={"NY": {"name": "Tish James"}})
        self.assertEqual(rows["NY"]["name"], "Letitia James")
        self.assertTrue(rows["NY"]["confirmationKept"])

    def test_an_office_page_that_was_read_and_does_not_name_them_keeps_nothing(self):
        nc = {"NC": dict(self.NC, confirmedOn="2026-10-19", alsoListed=["Dan Bishop (R)"])}
        rows, _ = self.rows({"NC": ("https://ncdoj.gov/", "Welcome to the Department. " * 20)}, nc)
        self.assertIn("disputed", rows["NC"])
        nh = {"NH": dict(self.NH, confirmedOn="2026-10-19", alsoListed=[])}
        rows, _ = self.rows({"NH": ("https://www.doj.nh.gov/", "Attorney General Someone Else")}, nh)
        self.assertTrue(rows["NH"]["unconfirmed"])
        self.assertNotIn("unreadable", rows["NH"])

    def test_the_photograph_is_kept_as_the_last_read_had_it(self):
        previous = {"NC": dict(self.NC, confirmedOn="2026-10-19", alsoListed=["Dan Bishop (R)"],
                               photoWeight={"bytes": 1, "width": 200, "height": 250})}
        rows, _ = self.rows(self.DOWN, previous)

        def get(url, timeout=60):
            raise AssertionError("a kept row's photograph is not read again")

        def check(url, hinted):
            raise AssertionError("a kept row's photograph is not weighed again")
        problems = officers.add_ag_photos(rows, {}, previous, check=check, pause=0, get=get)
        for field in ("photo", "photoPage", "photoWeight"):
            self.assertEqual(rows["NC"][field], previous["NC"][field])
        self.assertFalse([p for p in problems if p.startswith("NC:")], problems)

    def test_the_page_shows_a_kept_or_dated_row_as_it_showed_a_confirmed_one(self):
        before = officers.for_state("NC", {"lt": {}, "sos": {}, "ag": {"NC": dict(self.NC)}}, [])
        for extra in ({"confirmedOn": "2026-10-19", "alsoListed": ["Dan Bishop (R)"]},
                      {"confirmedOn": "2026-10-19", "alsoListed": ["Dan Bishop (R)"],
                       "confirmationKept": True}):
            after = officers.for_state("NC", {"lt": {}, "sos": {}, "ag": {"NC": dict(self.NC, **extra)}},
                                       [])
            self.assertEqual(after, before)
        self.assertNotIn("confirmedOn", before["ag"])

    SOS = {"name": "Cord Byrd", "party": "R", "partyKey": "R", "title": "Secretary of State",
           "member": False, "website": "https://dos.fl.gov/"}

    def non_member(self, text, previous, day="2026-10-25"):
        from unittest import mock
        problems = []
        with mock.patch.object(officers, "_office_text", lambda url, pause: text):
            sos = officers.confirm_non_members({"FL": dict(self.SOS)}, pause=0, previous=previous,
                                               previous_day=day, today="2026-10-26",
                                               problems=problems)
        return sos["FL"], problems

    def test_a_secretary_of_states_confirmation_is_kept_the_same_way(self):
        fl, _ = self.non_member("Secretary of State Cord Byrd", None)
        self.assertEqual((fl["officeConfirms"], fl["confirmedOn"]), (True, "2026-10-26"))
        # A site that concludes nothing keeps it, on the cache's day for a
        # row written before confirmedOn, and never restamps it.
        old = {"FL": dict(self.SOS, officeConfirms=True)}
        fl, problems = self.non_member(None, old)
        self.assertTrue(fl["officeConfirms"] and fl["confirmationKept"])
        self.assertEqual(fl["confirmedOn"], "2026-10-25")
        self.assertNotIn("officeRead", fl)
        self.assertIn("its confirmation of Cord Byrd on 2026-10-25 is kept", problems[0])
        again, _ = self.non_member(None, {"FL": fl}, day="2026-10-26")
        self.assertEqual(again["confirmedOn"], "2026-10-25")
        page = officers.for_state("FL", {"sos": {"FL": again}, "lt": {}}, [])["sos"]
        self.assertNotIn("notMember", page)
        self.assertNotIn("officeRead", page)
        # A site read that does not name them is a finding: nothing is kept.
        fl, problems = self.non_member("Welcome to the Department of State. " * 20, old)
        self.assertEqual(fl["officeRead"], "not-named")
        self.assertNotIn("officeConfirms", fl)
        self.assertEqual(problems, [])
        # Nor is another person's confirmation.
        fl, _ = self.non_member(None, {"FL": dict(self.SOS, name="Laurel Lee", officeConfirms=True)})
        self.assertEqual(fl["officeRead"], "unreadable")

    def test_an_old_kept_confirmation_is_a_warning(self):
        import datetime
        from unittest import mock
        from kyc import validate
        cache = {"ag": {"NC": dict(self.NC, confirmedOn="2026-10-19", confirmationKept=True)},
                 "sos": {"FL": dict(self.SOS, officeConfirms=True, confirmationKept=True,
                                    confirmedOn="2026-10-19")}, "lt": {}}
        day = datetime.date(2026, 10, 19)
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", {}, clear=True):
            self.assertEqual(validate.check_officers_kept(
                cache, day + datetime.timedelta(days=officers.KEPT_STALE_DAYS)), [])
            issues = validate.check_officers_kept(
                cache, day + datetime.timedelta(days=officers.KEPT_STALE_DAYS + 1))
        self.assertEqual([i.code for i in issues], ["officer-confirmation-kept"])
        details = " ".join(issues[0].detail)
        for words in ("NC attorney general: Jeff Jackson", "FL secretary of state: Cord Byrd",
                      "2026-10-19", "15 days ago", "OFFICERS_READ_BY_HAND"):
            self.assertIn(words, details)
        # A confirmation read afresh is not kept, and is no warning.
        cache["ag"]["NC"].pop("confirmationKept")
        cache["sos"]["FL"].pop("confirmationKept")
        self.assertEqual(validate.check_officers_kept(cache, day + datetime.timedelta(days=99)), [])

    def test_a_kept_row_does_not_say_a_reading_by_hand_may_go(self):
        from unittest import mock
        entries = {("NC", "ag"): ("Jeff Jackson", "https://ncdoj.gov/", "2026-10-26",
                                  ("Attorney General Jeff Jackson",)),
                   ("FL", "sos"): ("Cord Byrd", "https://dos.fl.gov/", "2026-10-26",
                                   ("Secretary of State Cord Byrd",))}
        kept = {"ag": {"NC": dict(self.NC, confirmedOn="2026-10-19", confirmationKept=True)},
                "sos": {"FL": dict(self.SOS, officeConfirms=True, confirmationKept=True,
                                   confirmedOn="2026-10-19")}, "lt": {}}
        read = {"ag": {"NC": dict(self.NC, confirmedOn="2026-10-26")},
                "sos": {"FL": dict(self.SOS, officeConfirms=True, confirmedOn="2026-10-26")},
                "lt": {}}
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", entries, clear=True):
            self.assertEqual(officers.by_hand_unused(kept), [])
            self.assertEqual(len(officers.by_hand_unused(read)), 2)
            # The reading by hand is what the page then names, and the
            # kept confirmation, read by hand since, is no warning.
            ag = officers.for_state("NC", kept, [])["ag"]
            sos = officers.for_state("FL", kept, [])["sos"]
            self.assertEqual(officers.kept_stale(kept, __import__("datetime").date(2027, 1, 1)), [])
        self.assertEqual(ag["readByHand"]["read"], "2026-10-26")
        self.assertEqual(sos["readByHand"]["read"], "2026-10-26")


class TestAttorneyGeneralPhotos(unittest.TestCase):
    """STATEGOV-13: no attorney general had a photograph. Each is read from
    the office's own pages, the ones that confirmed the name, and only an
    image the page says is the holder's likeness is taken."""

    HOME = ("https://ag.example.gov/", """<html><body>
      <img src="/img/AG-Griffin-Logo.png" alt="Tim Griffin Attorney General of Arkansas">
      <img src="/img/Upcoming.png" alt="AG Griffin talking to a townhall crowd.">
      <img src="/img/peter1.jpg" alt="Attorney General Griffin discusses health care">
      <img src="/img/hero-bg.jpg" alt="AG Tim Griffin">
      <img src="data:image/gif;base64,R0lGOD" data-src="/img/Griffin-headshot.jpg" alt="">
      <a href="/meet-tim/">Meet Tim</a> <a href="/about-us/">About us</a>
      <a href="https://news.example.com/griffin">Griffin wins</a>
    </body></html>""")

    @staticmethod
    def weigh(table):
        """A stand-in for enrich.portrait_check from ``{url: weight}``."""
        def check(url, hinted):
            weight = table.get(url)
            return (None, None) if weight == "unknown" else (bool(weight), weight or None)
        return check

    def test_only_a_likeness_is_a_candidate(self):
        found = officers.likeness_candidates("Tim Griffin", "AR", [self.HOME])
        self.assertEqual([urls for urls, _, _ in found],
                         [["https://ag.example.gov/img/Griffin-headshot.jpg"]])

    def test_an_alt_that_is_only_the_name_and_title_is_taken(self):
        page = ("https://ag.example.gov/about", '<img src="/a/x1.jpg" alt="Attorney General '
                'Rob Bonta"><img src="/a/x2.jpg" alt="Attorney General Rob Bonta at a rally">'
                '<img src="/a/AG_Rob_Bonta_0007a.jpg" alt="">'
                # Another first name in the file is someone else of the name.
                '<img src="/a/AG_Marty_Bonta_0007a.jpg" alt="">')
        found = officers.likeness_candidates("Rob Bonta", "CA", [page])
        self.assertEqual([u[-1] for u, _, _ in found],
                         ["https://ag.example.gov/a/x1.jpg",
                          "https://ag.example.gov/a/AG_Rob_Bonta_0007a.jpg"])

    def test_a_heavy_original_gives_way_to_a_size_of_the_same_file(self):
        page = ("https://ag.example.gov/", '<img src="/u/Ellison-headshot.jpg" '
                'srcset="/u/Ellison-headshot-150x150.jpg 150w, /u/Ellison-headshot-300x375.jpg 300w,'
                ' /u/Ellison-headshot.jpg 2000w" alt="">')
        check = self.weigh({
            "https://ag.example.gov/u/Ellison-headshot-300x375.jpg":
                {"bytes": 30_000, "width": 300, "height": 375},
            "https://ag.example.gov/u/Ellison-headshot.jpg":
                {"bytes": 4_000_000, "width": 2000, "height": 2500}})
        photo, why = officers.ag_photo("Keith Ellison", "MN", [page], check=check)
        self.assertEqual(photo["photo"], "https://ag.example.gov/u/Ellison-headshot-300x375.jpg")
        self.assertEqual(photo["photoPage"], "https://ag.example.gov/")
        heavy = self.weigh({"https://ag.example.gov/u/Ellison-headshot-300x375.jpg":
                            {"bytes": 400_000, "width": 300, "height": 375},
                            "https://ag.example.gov/u/Ellison-headshot.jpg":
                            {"bytes": 4_000_000, "width": 2000, "height": 2500}})
        # Offered only above the caps: the lightest size, kept and said -
        # never left out for its weight (rule 87, the owner's decision of
        # 2026-10-25).
        photo, why = officers.ag_photo("Keith Ellison", "MN", [page], check=heavy,
                                       lighter=lambda url, weight, weigh: None)
        self.assertEqual(why, "")
        self.assertEqual(photo["photo"], "https://ag.example.gov/u/Ellison-headshot-300x375.jpg")
        self.assertTrue(photo["photoHeavy"][0]["kept"])

    def test_a_heavy_file_is_tried_through_its_hosts_resizer_or_photon(self):
        """California's portrait is a 6 MB original with no smaller size on
        the page: main's rule 87 step - the host's resizer, then Photon,
        weighed and checked to be the same shape - is tried before the file
        is kept heavy (PR #135 review)."""
        original = "https://www.oag.ca.gov/files/ag-bonta-official-2.jpg"
        photon = "https://i0.wp.com/www.oag.ca.gov/files/ag-bonta-official-2.jpg?w=500&ssl=1"
        table = {original: {"bytes": 6_040_317, "width": 3349, "height": 5025},
                 photon: {"bytes": 45_000, "width": 500, "height": 750}}
        page = ("https://www.oag.ca.gov/about", '<img src="/files/ag-bonta-official-2.jpg" '
                'alt="Attorney General Rob Bonta">')
        photo, why = officers.ag_photo("Rob Bonta", "CA", [page], check=self.weigh(table))
        self.assertEqual(why, "")
        self.assertEqual(photo["photo"], photon)
        self.assertEqual(photo["photoHeavy"], [{"url": original, "why": "6040 KB, over 300 KB",
                                                "kept": False}])
        # Where Photon serves nothing, the office's own file is kept, heavy.
        del table[photon]
        photo, _ = officers.ag_photo("Rob Bonta", "CA", [page], check=self.weigh(table))
        self.assertEqual(photo["photo"], original)
        self.assertTrue(photo["photoHeavy"][0]["kept"])

    def test_naags_lighter_card_goes_before_the_offices_heavy_file(self):
        """Both are tied to the person; the lighter goes first. An office
        photograph within the caps is still the office's own."""
        from kyc import overrides, stategov
        ((code, office), card), = [(k, v) for k, v in overrides.OFFICER_PHOTOS.items()
                                   if k[1] == "ag"][:1]
        heavy = {"name": card["name"], "photo": "https://ag.example.gov/big.jpg",
                 "photoBy": "the office's website", "photoPage": "https://ag.example.gov/",
                 "photoHeavy": [{"url": "https://ag.example.gov/big.jpg", "why": "6 MB",
                                 "kept": True}]}
        entry = {office: dict(heavy)}
        problems = stategov.officer_photos(code, entry)
        self.assertEqual(entry[office]["photo"], card["photo"])
        self.assertNotIn("photoHeavy", entry[office])
        self.assertFalse([p for p in problems if "may be unneeded" in p])
        light = dict(heavy, photoHeavy=[{"url": "https://ag.example.gov/big.jpg", "why": "6 MB",
                                         "kept": False}])
        entry = {office: light}
        problems = stategov.officer_photos(code, entry)
        self.assertEqual(entry[office]["photo"], "https://ag.example.gov/big.jpg")
        self.assertTrue([p for p in problems if "may be unneeded" in p])

    def test_a_picture_elements_sources_are_its_sizes(self):
        """Michigan's page offers the portrait at 320px only in a
        ``<source>`` beside a 1,400px ``<img>``."""
        page = ("https://www.michigan.gov/ag/team-listing-page/x",
                '<picture><source srcset="/ag/-/media/AG_Dana_Nessel_press.jpg?mw=320 320w, '
                '/ag/-/media/AG_Dana_Nessel_press.jpg?mw=480 480w" type="image/webp">'
                '<img src="/ag/-/media/AG_Dana_Nessel_press.jpg?mw=1400" '
                'alt="Attorney General Dana Nessel"></picture>')
        found = officers.likeness_candidates("Dana Nessel", "MI", [page])
        self.assertEqual(found[0][0][0],
                         "https://www.michigan.gov/ag/-/media/AG_Dana_Nessel_press.jpg?mw=320")

    def test_initials_middle_names_and_counters_do_not_hide_the_holder(self):
        def taken(name, code, tag):
            return [u[-1] for u, _, _ in officers.likeness_candidates(
                name, code, [("https://ag.example.gov/", tag)])]
        self.assertTrue(taken("Dave Sunday", "PA", '<img src="/u/sunday-in-office-image-scaled.jpg" '
                                                   'alt="Attorney General Dave W. Sunday">'))
        self.assertTrue(taken("J.B. McCuskey", "WV", '<img src="/f/AG%20McCuskey%20pic.jpeg" '
                                                     'alt="Attorney General JB McCuskey">'))
        self.assertTrue(taken("Anne Lopez", "HI", '<img src="/u/AG-Anne-Lopez-scaled.jpg" alt="">'))
        # A logo carrying the name is still refused, initials or not.
        self.assertFalse(taken("Dave Sunday", "PA", '<img src="/u/ag-sunday-logo-white-alt.png" '
                                                    'alt="AG Dave Sunday">'))
        # Another first name before the surname is still someone else.
        self.assertFalse(taken("J.B. McCuskey", "WV", '<img src="/f/x.jpg" '
                                                      'alt="Deputy Mary McCuskey headshot">'))

    def test_the_offices_own_biography_page_is_read_where_the_front_page_links_none(self):
        got = []
        bio = '<img src="/images/paxton.jpg" alt="Texas Attorney General Ken Paxton">'

        def get(url, timeout=60):
            got.append(url)
            return bio
        check = self.weigh({"https://www.texasattorneygeneral.gov/images/paxton.jpg":
                            {"bytes": 9_622, "width": 262, "height": 394}})
        rows = {"TX": {"name": "Ken Paxton"}}
        officers.add_ag_photos(rows, {"TX": [("https://www.texasattorneygeneral.gov/",
                                              "<p>Home</p>")]}, check=check, pause=0, get=get)
        self.assertEqual(got, [officers.BIO_PAGES["TX"][0]])
        self.assertEqual(rows["TX"]["photoPage"], officers.BIO_PAGES["TX"][0])
        self.assertNotIn("photoHeavy", rows["TX"])

    def test_a_biography_page_entry_says_when_it_has_gone_stale(self):
        """PR #135 review: several addresses carry the holder's name, and
        Arizona's attorney general is on the November ballot."""
        url, _, holder, _ = officers.BIO_PAGES["AZ"]
        self.assertEqual(officers.bio_page_problems({"AZ": {"name": holder, "photo": "x"}}), [])
        self.assertTrue(officers.bio_page_problems({"AZ": {"name": "Rodney Glassman"}}))
        self.assertTrue(officers.bio_page_problems({"AZ": {"name": holder}}))
        for code, entry in officers.BIO_PAGES.items():
            with self.subTest(code=code):
                self.assertEqual(len(entry), 4)
                self.assertTrue(entry[0].startswith("https://"))

    def test_a_landscape_or_tiny_image_is_not_a_portrait(self):
        page = ("https://ag.example.gov/", '<img src="/u/Jones-headshot.jpg" alt="">')
        for weight in ({"bytes": 70_000, "width": 425, "height": 283},
                       {"bytes": 5_000, "width": 90, "height": 120}):
            check = self.weigh({"https://ag.example.gov/u/Jones-headshot.jpg": weight})
            self.assertEqual(officers.ag_photo("Jay Jones", "VA", [page], check=check)[0], None)

    def test_the_attorney_generals_own_page_is_read_for_one(self):
        bio = ('<img src="/img/Mills.jpg" alt="Attorney General Griffin">')
        got = []
        rows = {"AR": {"name": "Tim Griffin", "party": "R"},
                "NC": {"name": "Dan Bishop", "unconfirmed": True}}
        check = self.weigh({"https://ag.example.gov/img/Griffin-headshot.jpg": None,
                            "https://ag.example.gov/img/Mills.jpg":
                                {"bytes": 28_000, "width": 200, "height": 250}})

        def get(url, timeout=60):
            got.append(url)
            return bio
        problems = officers.add_ag_photos(rows, {"AR": [self.HOME]}, check=check, pause=0, get=get)
        self.assertEqual(got, ["https://ag.example.gov/meet-tim/"])
        self.assertEqual(rows["AR"]["photo"], "https://ag.example.gov/img/Mills.jpg")
        self.assertEqual(rows["AR"]["photoPage"], "https://ag.example.gov/meet-tim/")
        self.assertNotIn("photo", rows["NC"])          # never an unconfirmed holder's
        self.assertEqual(len(problems), 1)
        self.assertIn("photograph added for Tim Griffin", problems[0])

    def test_a_read_that_concludes_nothing_keeps_the_same_persons_last_photo(self):
        check = self.weigh({"https://ag.example.gov/img/Griffin-headshot.jpg": "unknown"})
        old = {"AR": {"name": "Tim Griffin", "photo": "https://ag.example.gov/old.jpg",
                      "photoPage": "https://ag.example.gov/"}}

        def get(url, timeout=60):
            raise officers.OfficersError("refused")
        rows = {"AR": {"name": "Tim Griffin"}}
        problems = officers.add_ag_photos(rows, {"AR": [self.HOME]}, old, check=check, pause=0,
                                          get=get)
        self.assertEqual(rows["AR"]["photo"], "https://ag.example.gov/old.jpg")
        self.assertIn("kept", problems[0])
        # A new holder never inherits it.
        rows = {"AR": {"name": "Someone Else"}}
        officers.add_ag_photos(rows, {"AR": [self.HOME]}, old, check=check, pause=0, get=get)
        self.assertNotIn("photo", rows["AR"])

    def test_a_colleague_sharing_letters_or_a_surname_is_not_the_attorney_general(self):
        """A substring test took "Carrie-Smith-Headshot" for Chris Carr and
        "jane-stanford-portrait" for Aaron Ford, and nothing looked at a
        first name: "Solicitor General Jessica Ford headshot" passed too."""
        def taken(name, code, tag):
            return [u[-1] for u, _, _ in officers.likeness_candidates(
                name, code, [("https://ag.example.gov/", tag)])]
        self.assertEqual(taken("Chris Carr", "GA", '<img src="/uploads/Carrie-Smith-Headshot.jpg" '
                                                   'alt="Chief of Staff Carrie Smith">'), [])
        self.assertEqual(taken("Aaron Ford", "NV", '<img src="/img/jane-stanford-portrait.jpg" '
                                                   'alt="">'), [])
        self.assertEqual(taken("Aaron Ford", "NV", '<img src="/uploads/staff-07.jpg" '
                                                   'alt="Solicitor General Jessica Ford headshot">'),
                         [])
        self.assertEqual(taken("Aaron Ford", "NV", '<img src="/u/jessicafordheadshot.jpg" alt="">'),
                         [])
        # The holder, with a middle initial, in run-together words, or by an
        # evidenced short form (NAME_FORMS), is still found.
        self.assertTrue(taken("Aaron Ford", "NV", '<img src="/uploads/staff-07.jpg" '
                                                  'alt="Attorney General Aaron D. Ford headshot">'))
        self.assertTrue(taken("Liz Murrill", "LA", '<img src="/i/aglizmurrillheadshot.jpg" alt="">'))
        self.assertTrue(taken("Liz Murrill", "LA", '<img src="/i/AgLizMurrillHeadshot.jpg" alt="">'))
        self.assertTrue(taken("Letitia James", "NY", '<img src="/u/x.jpg" '
                                                     'alt="Attorney General Tish James headshot">'))

    def test_a_photograph_added_changed_or_dropped_is_said(self):
        old = {"name": "Tim Griffin", "photo": "https://ag.example.gov/old.jpg"}
        self.assertEqual(officers.photo_changes("AR", old, dict(old)), [])
        added = officers.photo_changes("AR", {}, {"name": "Tim Griffin", "photo": "https://a/x.jpg",
                                                  "photoPage": "https://a/"})
        self.assertIn("added", added[0])
        changed = officers.photo_changes("AR", old, {"name": "Tim Griffin",
                                                     "photo": "https://ag.example.gov/new.jpg"})
        self.assertIn("changed", changed[0])
        self.assertIn("old.jpg", changed[0])
        self.assertIn("dropped", officers.photo_changes("AR", old, {"name": "Tim Griffin"})[0])

    def test_the_page_is_told_whose_photograph_it_is(self):
        cache = {"lt": {}, "sos": {}, "ag": {"AR": {
            "name": "Tim Griffin", "photo": "https://ag.example.gov/img/g.jpg",
            "photoPage": "https://www.ag.example.gov/meet-tim/",
            "photoWeight": {"bytes": 1, "width": 200, "height": 250}}}}
        ag = officers.for_state("AR", cache, [])["ag"]
        self.assertEqual(ag["photoBy"], "the office's website (ag.example.gov)")
        self.assertNotIn("photoWeight", ag)
        self.assertIn("photoWeight", cache["ag"]["AR"])


class TestReadByHand(unittest.TestCase):
    """An officer confirmed from the office's own page, read by hand in a
    person's browser where the office's site refuses a script, or where the
    association does not speak for the office (overrides.OFFICERS_READ_BY_HAND,
    the owner's request of 2026-10-26: "The National Association of
    Secretaries of State lists Francisco V. Aguilar ... not confirmed. The
    office's site.")."""

    AG = {"name": "Andrea Campbell", "party": "D", "partyKey": "D", "unconfirmed": True,
          "unreadable": True, "listedBy": "Democratic Attorneys General Association",
          "office": "https://www.mass.gov/orgs/office-of-the-attorney-general"}
    SOS = {"name": "Francisco V. Aguilar", "party": "D", "partyKey": "D",
           "title": "Secretary of State", "selection": "Elected", "electionChief": True,
           "member": False, "website": "https://www.nvsos.gov/sos"}
    ENTRIES = {
        ("MA", "ag"): ("Andrea Campbell", "https://www.mass.gov/orgs/office-of-the-attorney-general",
                       "2026-10-26", ("Attorney General Andrea Joy Campbell’s Office is an advocate",)),
        ("NV", "sos"): ("Francisco V. Aguilar", "https://www.nvsos.gov/sos/about", "2026-10-26",
                        ("About Francisco V. Aguilar | Nevada Secretary of State",
                         "Francisco “Cisco” Aguilar was elected as Nevada Secretary of State")),
    }

    def cache(self, ag=None, sos=None):
        return {"ag": {"MA": dict(self.AG, **(ag or {}))},
                "sos": {"NV": dict(self.SOS, **(sos or {}))}, "lt": {}}

    def given(self, cache, entries=None):
        from unittest import mock
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", entries or self.ENTRIES,
                             clear=True):
            return (officers.for_state("MA", cache, [])["ag"],
                    officers.for_state("NV", cache, [])["sos"])

    def test_the_holder_the_office_names_is_confirmed_and_says_how(self):
        ag, sos = self.given(self.cache())
        for row in (ag, sos):
            self.assertNotIn("unconfirmed", row)
            self.assertNotIn("unreadable", row)
            self.assertNotIn("notMember", row)
            self.assertEqual(row["readByHand"]["read"], "2026-10-26")
            self.assertTrue(row["readByHand"]["url"].startswith("https://"))
        self.assertEqual(ag["title"], "Attorney General")
        self.assertEqual(sos["name"], "Francisco V. Aguilar")
        # The page read by hand names him, not his party: that is still the
        # non-member listing's, and credited to it (rule 55).
        self.assertEqual(sos["partyFrom"], officers.NASS_BY)
        self.assertNotIn("partyFrom", ag)

    def test_without_an_entry_nothing_changes(self):
        ag, sos = self.given(self.cache(), {("XX", "ag"): self.ENTRIES[("MA", "ag")]})
        self.assertTrue(ag["unconfirmed"] and ag["unreadable"])
        self.assertTrue(sos["notMember"])
        self.assertNotIn("readByHand", ag)

    def test_it_never_confirms_someone_the_roster_names_instead(self):
        # A new holder: the entry for the old one confirms nobody, and
        # validate says so (rule 3; CLAUDE.md "Curated data").
        cache = self.cache(ag={"name": "Jane Roe"}, sos={"name": "John Doe"})
        ag, sos = self.given(cache)
        self.assertTrue(ag["unconfirmed"])
        self.assertTrue(sos["notMember"])
        from unittest import mock
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", self.ENTRIES, clear=True):
            unused = officers.by_hand_unused(cache)
            issues = __import__("kyc.validate", fromlist=["x"]).check_officers_by_hand(cache)
        self.assertTrue(any(u.startswith("MA ag: the roster now names Jane Roe") for u in unused))
        self.assertTrue(any(u.startswith("NV sos: the roster now names John Doe") for u in unused))
        self.assertEqual([i.code for i in issues], ["officers-by-hand"])

    def test_words_that_do_not_name_them_beside_the_title_confirm_nobody(self):
        # "X was elected as ... Secretary of State" is not the name beside
        # the title (rule 56); without the page's title it confirms nothing.
        entries = {("NV", "sos"): self.ENTRIES[("NV", "sos")][:3] + (
            ("Francisco “Cisco” Aguilar was elected as Nevada Secretary of State",),)}
        _, sos = self.given(self.cache(), entries)
        self.assertTrue(sos["notMember"])
        from unittest import mock
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", entries, clear=True):
            self.assertEqual(officers.by_hand_errors(),
                             ["NV sos: the words quoted do not name Francisco V. Aguilar beside "
                              "the title"])

    def test_a_site_that_was_read_and_does_not_name_them_is_not_overruled(self):
        # Only a read that concluded nothing (rule 8) is consulted.
        ag, _ = self.given(self.cache(ag={"unreadable": False}))
        self.assertTrue(ag["unconfirmed"])
        _, sos = self.given(self.cache(sos={"member": True}))
        self.assertNotIn("readByHand", sos)

    def test_an_old_reading_is_a_warning(self):
        import datetime
        from unittest import mock
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", self.ENTRIES, clear=True):
            day = datetime.date(2026, 10, 26)
            self.assertEqual(officers.by_hand_stale(day + datetime.timedelta(
                days=officers.BY_HAND_STALE_DAYS)), [])
            stale = officers.by_hand_stale(day + datetime.timedelta(
                days=officers.BY_HAND_STALE_DAYS + 1))
        self.assertEqual(len(stale), 2)
        self.assertIn("read https://www.nvsos.gov/sos/about again", " ".join(stale))

    def test_a_malformed_entry_stops_the_build(self):
        from unittest import mock
        bad = {("MA", "ag"): ("Andrea Campbell", "http://mass.gov/", "26 October",
                              "Attorney General Andrea Campbell")}
        with mock.patch.dict("kyc.overrides.OFFICERS_READ_BY_HAND", bad, clear=True):
            errors = officers.by_hand_errors()
            with self.assertRaises(stategov.StateGovError):
                stategov.build(ROOT)
        self.assertEqual(len(errors), 3)

    def test_the_committed_entries_confirm_their_holders(self):
        # The owner's request: Nevada's secretary of state, and the
        # attorneys general whose sites refuse a script, read by hand on
        # 2026-10-26 (research/by-hand-2026-10-26/NOTES.md).
        # A refresh that changes a holder or confirms one itself makes the
        # entry unused, which validate reports; it must not hold the refresh.
        self.assertEqual(officers.by_hand_errors(), [])
        payload, problems = stategov.build(ROOT)
        cache = officers.load_cache(ROOT)
        unused = {tuple(u.split(":")[0].split()) for u in officers.by_hand_unused(cache)}
        for (code, office), entry in officers.by_hand().items():
            if (code, office) in unused:
                continue
            row = payload["states"][code][office]
            self.assertEqual(row["name"], entry["holder"], code)
            self.assertEqual(row["readByHand"], {"url": entry["page"], "read": entry["read"]})
            self.assertFalse(row.get("unconfirmed") or row.get("notMember"), code)
            self.assertFalse(any(p.startswith(f"{code}: {entry['holder']} is shown as")
                                 for p in problems), code)
        self.assertIn(("NV", "sos"), officers.by_hand())


class TestCommitted(unittest.TestCase):

    def test_every_state_has_both_offices_accounted_for(self):
        payload, _ = stategov.build(ROOT)
        for code in STATES:
            entry = payload["states"][code]
            self.assertIn("lt", entry, code)
            self.assertIn("sos", entry, code)

    def test_every_attorney_general_row_says_what_it_is(self):
        # Confirmed by the office, an attributed listing, a dispute, or no
        # listing at all - never a bare name.
        payload, _ = stategov.build(ROOT)
        for code in STATES:
            row = payload["states"][code]["ag"]
            kinds = [k for k in ("unconfirmed", "disputed", "unlisted") if row.get(k)]
            if not kinds:
                self.assertIn(row["partyKey"], ("D", "R"), code)
                self.assertTrue(row["listedBy"] and row["office"], code)
            if row.get("unconfirmed"):
                self.assertTrue(row["listedBy"], code)

    def test_every_disagreement_is_shown_as_one(self):
        # On 2026-10-05: Hawaii's lieutenant governor.
        payload, problems = stategov.build(ROOT)
        cache = officers.load_cache(ROOT)
        for code, office, _, _ in officers.overlaps(cache["sos"], cache["lt"]):
            key = "lt" if office == "Lieutenant Governor" else "sos"
            self.assertIn("disputed", payload["states"][code][key], code)
            self.assertTrue(any(p.startswith(code + ":") for p in problems), code)


if __name__ == "__main__":
    unittest.main()
