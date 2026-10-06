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

    def test_a_nass_photo_must_carry_the_surname(self):
        self.assertTrue(officers._surname_in("Wes Allen", "https://x/AL-Allen-2023.jpg?itok=1"))
        self.assertFalse(officers._surname_in("Steve Simon", "https://x/MN-SOS-2023.jpg"))
        self.assertTrue(officers._surname_in("Pulu Ae Ae Jr.", "https://x/Pulu-Ae-Ae-Samoa.png"))


class TestCommitted(unittest.TestCase):

    def test_every_state_has_both_offices_accounted_for(self):
        payload, _ = stategov.build(ROOT)
        for code in STATES:
            entry = payload["states"][code]
            self.assertIn("lt", entry, code)
            self.assertIn("sos", entry, code)

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
