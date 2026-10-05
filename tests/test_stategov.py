"""Tests for who runs each state: the NGA roster reader (kyc/executives.py)
and the governors, chamber control and trifectas built from it, Open States
and NCSL (kyc/stategov.py).

Chamber control is counted from two independent sources and shown only
where they agree; a seat with nobody listed counts for no one.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import executives, stategov  # noqa: E402
from kyc.government_maps import STATES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

ROSTER = """
<p><a href="https://www.nga.org/governors/ngaleadership/">NGA leadership</a>
<img src="https://www.nga.org/wp-content/themes/nga/images/branding/logo.svg" alt=""></p>
<ul class="current-governors__list">
  <li class="current-governors__item">
    <div class="current-governors__wrapper">
      <a href="https://www.nga.org/governors/alabama/" target="_blank">
        <div class="current-governors__item__image">
          <img decoding="async" src="https://www.nga.org/wp-content/uploads/ivey.jpg" alt="Kay Ivey" />
        </div>
        <div class="current-governors__item__link">
          <small class="state">Alabama</small>
          Gov. Kay Ivey                </div>
      </a>
    </div>
  </li>
  <li class="current-governors__item">
    <div class="current-governors__wrapper">
      <a href="https://www.nga.org/governors/puerto-rico/" target="_blank">
        <div class="current-governors__item__image">
          <img decoding="async" src="https://www.nga.org/wp-content/uploads/gonzalez.jpg" alt="" />
        </div>
        <div class="current-governors__item__link">
          <small class="state">Puerto Rico</small>
          Gov. Jenniffer Gonz&aacute;lez-Col&oacute;n                </div>
      </a>
    </div>
  </li>
</ul>
"""

PROFILE = """
<ul>
<li><label class="label">Terms</label> January 14, 2019 - January 9, 2023<br/>January 9, 2023 - Current</li>
<li><label class="label">Party</label> Democrat</li>
<li><label class="label">Born</label> January 19, 1965</li>
</ul>
<h4 class="title">Contact Information</h4>
<ul>
<li class="item item--has-label">
  <small class="content-block__item__description">
    Address  </small>
  Office of the Governor<br>401 S. Spring St.<br>Springfield, IL 62704
</li>
<li class="item item--has-label">
  <small class="content-block__item__description">
    Phone  </small>
   217-782-6830
</li>
</ul>
<h4 class="title">Additional Information</h4>
<ul>
  <li class="item"><a href="https://www.illinois.gov/">State Website</a></li>
  <li class="item"><a href="https://gov.illinois.gov/">Governor's Website</a></li>
</ul>
"""


class TestRoster(unittest.TestCase):

    def test_only_the_list_is_read(self):
        # The page's own links and logo come before the list, and once put
        # the NGA's leadership page and logo on Alabama's governor.
        rows = executives.parse_roster(ROSTER)
        self.assertEqual([r["state"] for r in rows], ["AL", "PR"])
        self.assertEqual(rows[0]["profile"], "https://www.nga.org/governors/alabama/")
        self.assertEqual(rows[0]["headshot"], "https://www.nga.org/wp-content/uploads/ivey.jpg")
        self.assertEqual(rows[1]["name"], "Jenniffer González-Colón")

    def test_an_entry_that_cannot_be_read_stops_the_fetch(self):
        broken = ROSTER.replace("Gov. Kay Ivey", "Kay Ivey")
        with self.assertRaises(executives.ExecutivesError):
            executives.parse_roster(broken)

    def test_a_profile_says_what_the_page_labels(self):
        facts = executives.parse_profile(PROFILE)
        self.assertEqual(facts["terms"], ["January 14, 2019 - January 9, 2023", "January 9, 2023 - Current"])
        self.assertEqual(facts["party"], "Democratic")
        self.assertEqual(facts["address"], "Office of the Governor, 401 S. Spring St., Springfield, IL 62704")
        self.assertEqual(facts["phone"], "217-782-6830")

    def test_the_office_site_is_not_the_state_portal(self):
        self.assertEqual(executives.parse_profile(PROFILE)["website"], "https://gov.illinois.gov/")
        territory = PROFILE.replace(">Governor's Website<", ">Website<").replace(
            '<li class="item"><a href="https://www.illinois.gov/">State Website</a></li>', "")
        self.assertEqual(executives.parse_profile(territory)["website"], "https://gov.illinois.gov/")
        portal_only = PROFILE.replace(
            '<li class="item"><a href="https://gov.illinois.gov/">Governor\'s Website</a></li>', "")
        self.assertNotIn("website", executives.parse_profile(portal_only))

    def test_contact_labels_are_read_by_meaning(self):
        # Alaska's "Office Phone", North Carolina's address block headed
        # "Office of the Governor", the Virgin Islands' "Government House",
        # and Florida's "Governer's Website" all went unread.
        page = (PROFILE
                .replace("Phone  </small>", "Office Phone  </small>")
                .replace("Address  </small>\n  Office of the Governor<br>",
                         "Government House  </small>\n  ")
                .replace(">Governor's Website<", ">Governer's Website<"))
        facts = executives.parse_profile(page)
        self.assertEqual(facts["phone"], "217-782-6830")
        self.assertEqual(facts["address"], "Government House, 401 S. Spring St., Springfield, IL 62704")
        self.assertEqual(facts["website"], "https://gov.illinois.gov/")
        self.assertNotIn("unread", facts)

    def test_a_contact_field_that_cannot_be_read_is_reported(self):
        page = PROFILE.replace("Phone  </small>", "Fax  </small>")
        self.assertEqual(executives.parse_profile(page)["unread"], ["Fax"])

    def test_wikidata_names_are_compared_by_person(self):
        self.assertTrue(executives.same_person("Mike Dunleavy", "Michael J. Dunleavy"))
        self.assertTrue(executives.same_person("JB Pritzker", "J. B. Pritzker"))
        self.assertFalse(executives.same_person("Mike Dunleavy", "Wilford Bacon Hoggatt"))

    def test_a_cross_check_never_overwrites_the_roster(self):
        governors = {"AK": {"name": "Mike Dunleavy"}, "TX": {"name": "Greg Abbott"}}
        agree, disagree = executives.cross_check(
            governors, {"AK": ("Mike Dunleavy", "Q1", ["2018-12-03"]),
                        "TX": ("Someone Else", "Q2", [])})
        self.assertEqual(governors["AK"]["wikidataStarts"], ["2018-12-03"])
        self.assertEqual(agree, ["AK"])
        self.assertEqual(disagree, [("TX", "Greg Abbott", "Someone Else")])
        self.assertEqual(governors["TX"]["name"], "Greg Abbott")
        self.assertNotIn("wikidata", governors["TX"])


class TestControl(unittest.TestCase):

    def test_a_majority_is_more_than_half_of_all_seats(self):
        self.assertEqual(stategov.majority({"D": 68, "R": 66}, 134), "D")
        self.assertIsNone(stategov.majority({"D": 67, "R": 67}, 134))
        # 67 of 134 listed, one seat with nobody: no majority, and not a
        # Democratic one because a missing Republican was left uncounted.
        self.assertIsNone(stategov.majority({"D": 67, "R": 66}, 134))

    def test_a_seat_with_nobody_listed_counts_for_no_one(self):
        records = [{"chamber": "upper", "partyKey": "R"}] * 10 + [
            {"chamber": "upper", "partyKey": "D"}] * 9
        counts = stategov.chamber(records, "upper", 20)
        self.assertEqual((counts["listed"], counts["seats"], counts["majority"]), (19, 20, None))

    def test_a_tribal_seat_is_not_counted(self):
        records = [{"chamber": "lower", "partyKey": "D", "tribalSeat": True},
                   {"chamber": "lower", "partyKey": "D"}]
        self.assertEqual(stategov.chamber(records, "lower", 2)["D"], 1)

    def _state(self, code, upper, lower, theirs=None, governor="R"):
        records = ([{"chamber": "upper", "partyKey": k} for k, n in upper.items() for _ in range(n)] +
                   [{"chamber": "lower", "partyKey": k} for k, n in lower.items() for _ in range(n)])
        problems = []
        out = stategov._legislature(code, records, theirs, governor, problems)
        return out, problems

    def test_a_trifecta_needs_the_governor_and_both_chambers(self):
        out, problems = self._state("TX", {"R": 19, "D": 12}, {"R": 88, "D": 62})
        self.assertEqual((out["legislature"], out["trifecta"], problems), ("R", "R", []))
        out, _ = self._state("TX", {"R": 19, "D": 12}, {"R": 88, "D": 62}, governor="D")
        self.assertEqual((out["legislature"], out["trifecta"]), ("R", "divided"))
        out, _ = self._state("TX", {"R": 19, "D": 12}, {"R": 70, "D": 80})
        self.assertEqual((out["legislature"], out["trifecta"]), ("split", "divided"))

    def test_when_the_sources_disagree_neither_is_shown(self):
        theirs = {"upper": {"seats": 31, "D": 12, "R": 19}, "lower": {"seats": 150, "D": 76, "R": 74}}
        out, problems = self._state("TX", {"R": 19, "D": 12}, {"R": 88, "D": 62}, theirs)
        self.assertEqual((out["legislature"], out["trifecta"]), ("disputed", "disputed"))
        self.assertEqual(out["lower"]["ncsl"], "D")
        self.assertEqual(len(problems), 1)

    def test_nebraska_cannot_be_a_trifecta(self):
        out, _ = self._state("NE", {"N": 49}, {})
        self.assertEqual((out["legislature"], out["trifecta"]), ("nonpartisan", "nonpartisan"))
        self.assertNotIn("lower", out)

    def _alaska(self, upper, lower, session):
        link = f"https://www.akleg.gov/basis/Member/Detail/{session}?code=x"
        records = ([{"chamber": "upper", "partyKey": k, "links": [link]}
                    for k, n in upper.items() for _ in range(n)] +
                   [{"chamber": "lower", "partyKey": k, "links": [link]}
                    for k, n in lower.items() for _ in range(n)])
        problems = []
        return stategov._legislature("AK", records, None, "R", problems), problems

    def test_a_coalition_majority_is_not_party_control(self):
        out, problems = self._alaska({"R": 11, "D": 9}, {"R": 21, "D": 14, "I": 5}, 34)
        self.assertEqual(out["upper"]["majority"], "R")
        self.assertEqual((out["legislature"], out["trifecta"]), ("coalition", "divided"))
        self.assertIn("coalitions", out["note"])
        self.assertEqual(problems, [])

    def test_a_coalition_note_lapses_with_its_legislature(self):
        # The note is about the 34th Legislature; the 35th may organise
        # differently, so it is not shown once the members listed are its.
        out, problems = self._alaska({"R": 11, "D": 9}, {"R": 21, "D": 14, "I": 5}, 35)
        self.assertNotIn("note", out)
        self.assertEqual(out["trifecta"], "R")
        self.assertIn("legislature 34", problems[0])

    def test_a_coalition_note_lapses_when_the_seats_stop_fitting_it(self):
        out, problems = self._alaska({"D": 11, "R": 9}, {"D": 21, "R": 19}, 34)
        self.assertNotIn("note", out)
        self.assertEqual(out["legislature"], "D")
        self.assertTrue(problems)

    def test_in_office_since_follows_unbroken_terms(self):
        terms = ["January 20, 2015 - January 7, 2019", "January 8, 2019 - January 17, 2023",
                 "January 17, 2023 - Current"]
        self.assertEqual(stategov.in_office_since(terms), ("January 20, 2015", 3))
        # Jerry Brown's first two terms ended in 1983; a return is a new run.
        gap = ["January 6, 1975 - January 3, 1983", "January 3, 2011 - Current"]
        self.assertEqual(stategov.in_office_since(gap), ("January 3, 2011", 1))

    def test_a_first_day_is_shown_only_when_wikidata_agrees(self):
        base = {"name": "Kay Ivey", "party": "Republican", "partyKey": "R", "profile": "p",
                "state": "AL", "terms": ["April 19, 2017 - January 13, 2019",
                                         "January 14, 2019 - January 16, 2023",
                                         "January 16, 2023 - Current"]}
        problems = []
        self.assertEqual(stategov._governor(dict(base, wikidataStarts=["2017-04-10"]), problems)["since"], "")
        self.assertIn("April 19, 2017", problems[0])
        agreed = dict(base, terms=["April 10, 2017 - Current"], wikidataStarts=["2017-04-10"])
        self.assertEqual(stategov._governor(agreed)["since"], "April 10, 2017")
        self.assertEqual(stategov._governor(dict(base, terms=["April 10, 2017 - Current"]))["since"], "")

    def test_a_missing_cache_stops_the_build(self):
        import tempfile
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(stategov.StateGovError):
                stategov.build(empty)

    def test_a_heavy_or_unmeasured_headshot_is_left_off(self):
        base = {"name": "A", "party": "Republican", "partyKey": "R", "profile": "p", "terms": [],
                "headshot": "https://www.nga.org/x.jpg"}
        self.assertIn("headshot", stategov._governor(dict(base, headshotBytes=400_000)))
        self.assertNotIn("headshot", stategov._governor(dict(base, headshotBytes=7_617_284)))
        self.assertNotIn("headshot", stategov._governor(dict(base, headshotBytes=None)))


class TestNcsl(unittest.TestCase):

    HEAD = "".join(f"<th>{h}</th>" for h in stategov._HEAD)

    def test_a_changed_table_is_refused(self):
        page = '<table id="partisanComp"><tr><th>State</th><th>Seats</th></tr></table>'
        with self.assertRaises(stategov.StateGovError):
            stategov.parse_ncsl(page)

    def test_a_missing_state_is_refused(self):
        page = (f'<table id="partisanComp"><thead><tr>{self.HEAD}</tr></thead><tr><td>Alabama</td>'
                + "<td>105</td><td>29</td><td>76</td><td></td><td></td><td>35</td><td>8</td>"
                + "<td>27</td><td></td><td></td><td>R</td><td>R</td><td>R</td></tr></table>")
        with self.assertRaises(stategov.StateGovError) as caught:
            stategov.parse_ncsl(page)
        self.assertIn("AK", str(caught.exception))


class TestCommitted(unittest.TestCase):

    def test_the_sources_agree_everywhere(self):
        # The only disagreements are the NGA's two wrong first days, which
        # are left off the page.
        payload, problems = stategov.build(ROOT)
        self.assertEqual(sorted(p[:3] for p in problems), ["AL:", "IA:"])
        self.assertEqual(payload["states"]["AL"]["governor"]["since"], "")
        self.assertEqual([c for c in STATES if c not in payload["states"]], [])

    def test_trifectas_agree_with_ncsl_except_where_a_note_says_why(self):
        payload, _ = stategov.build(ROOT)
        ncsl = stategov.load_ncsl(ROOT)
        names = {"R": "R", "D": "D", "S": "divided", "N/A": "nonpartisan"}
        differ = sorted(c for c in STATES
                        if names[ncsl["states"][c]["control"]] != payload["states"][c]["trifecta"])
        self.assertEqual(differ, sorted(stategov.COALITIONS))

    def test_no_headshot_on_the_page_is_heavier_than_the_cap(self):
        cache = executives.load_cache(ROOT)["governors"]
        payload, _ = stategov.build(ROOT)
        for code, entry in payload["states"].items():
            if entry["governor"].get("headshot"):
                self.assertLessEqual(cache[code]["headshotBytes"], stategov.HEADSHOT_MAX_BYTES, code)


if __name__ == "__main__":
    unittest.main()
