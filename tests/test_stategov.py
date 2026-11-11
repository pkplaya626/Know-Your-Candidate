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

    def test_an_unreachable_wikidata_keeps_the_last_check(self):
        # Every first day in office would otherwise vanish from the page the
        # week Wikidata was down (rule 8).
        previous = {"governors": {"AL": {"name": "Kay Ivey", "wikidata": "Q1",
                                         "wikidataStarts": ["2017-04-10"]},
                                  "TX": {"name": "Greg Abbott", "wikidata": "Q2",
                                         "wikidataStarts": ["2015-01-20"]}}}
        now = {"AL": {"name": "Kay Ivey"}, "TX": {"name": "Someone New"}}
        self.assertEqual(executives.carry_over(now, previous), 1)
        self.assertEqual(now["AL"]["wikidataStarts"], ["2017-04-10"])
        self.assertNotIn("wikidataStarts", now["TX"])

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

    def test_a_member_listed_for_a_seat_ncsl_calls_vacant_is_reported(self):
        # Open States named someone for all 180 seats of Georgia's House
        # while NCSL listed one vacant: a member who has left may still be
        # shown as sitting. Reported, not changed on NCSL's word.
        theirs = {"upper": {"seats": 31, "D": 12, "R": 19, "other": 0, "vacant": 0},
                  "lower": {"seats": 150, "D": 61, "R": 88, "other": 0, "vacant": 1}}
        out, problems = self._state("TX", {"R": 19, "D": 12}, {"R": 88, "D": 62}, theirs)
        self.assertEqual(problems, ["TX lower: Open States lists 150 members, NCSL 149 with 1 vacant; "
                                    "check the chamber's own roster for a member who has left"])
        self.assertEqual(out["lower"]["D"], 62)
        # The other way round - nobody listed where NCSL has a member - is
        # Open States lagging, and the page already says "nobody listed".
        theirs["lower"] = {"seats": 150, "D": 62, "R": 88, "other": 0, "vacant": 0}
        _, problems = self._state("TX", {"R": 19, "D": 12}, {"R": 88, "D": 61}, theirs)
        self.assertEqual(problems, [])

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

    def test_a_heavy_headshot_is_shown_smaller_and_an_unmeasured_one_not_at_all(self):
        """TECH-13: 27 of the NGA's 55 headshots weighed 320 KB-7.6 MB, for a
        40-72px circle; a 1 MB cap let 25 of them through."""
        base = {"name": "A", "party": "Republican", "partyKey": "R", "profile": "p", "terms": [],
                "headshot": "https://www.nga.org/x.jpg"}
        light = {"bytes": 120_000, "width": 800, "height": 800}
        heavy = {"bytes": 981_392, "width": 2000, "height": 3000}
        small = ("https://i0.wp.com/www.nga.org/x.jpg?w=500&ssl=1",
                 {"bytes": 50_450, "width": 500, "height": 750})
        self.assertEqual(stategov._governor(dict(base, headshotWeight=light))["headshot"],
                         base["headshot"])
        self.assertNotIn("headshot", stategov._governor(dict(base, headshotWeight=heavy)))
        self.assertNotIn("headshot", stategov._governor(dict(base, headshotBytes=400_000)))
        self.assertNotIn("headshot", stategov._governor(dict(base, headshotBytes=None)))
        shown = stategov._governor(dict(base, headshotWeight=heavy, headshotSmall=small[0],
                                        headshotSmallWeight=small[1]))
        self.assertEqual(shown["headshot"], small[0])
        self.assertEqual(shown["headshotBy"], "National Governors Association")

    def test_a_headshot_is_weighed_and_found_smaller_in_the_same_file(self):
        from unittest import mock
        url = "https://www.nga.org/wp-content/uploads/2019/01/Gov-Mike-DeWine.jpg"
        photon = "https://i0.wp.com/www.nga.org/wp-content/uploads/2019/01/Gov-Mike-DeWine.jpg"
        weights = {url: {"bytes": 7_617_284, "width": 3930, "height": 4912},
                   photon + "?w=500&ssl=1": {"bytes": 47_104, "width": 500, "height": 624}}
        gov = {"headshot": url}
        with mock.patch.object(executives.time, "sleep"):
            executives.weigh_headshot(gov, weigh=weights.get)
        self.assertEqual(gov["headshotSmall"], photon + "?w=500&ssl=1")
        self.assertEqual(stategov.headshot(gov), photon + "?w=500&ssl=1")
        # Unreadable now: the last weights read of the same file stand (rule 8).
        again = {"headshot": url}
        with mock.patch.object(executives.time, "sleep"):
            executives.weigh_headshot(again, old=gov, weigh=lambda u: None)
        self.assertEqual(again["headshotSmall"], gov["headshotSmall"])
        # A resizer answering with some other picture is not taken.
        odd = {"headshot": url}
        with mock.patch.object(executives.time, "sleep"):
            executives.weigh_headshot(odd, weigh=lambda u: weights[url] if u == url else
                                      {"bytes": 9_000, "width": 500, "height": 500})
        self.assertNotIn("headshotSmall", odd)
        self.assertEqual(stategov.headshot(odd), "")


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

    # These hold for whatever the sources say this week: the weekly refresh
    # runs them on fresh data, so they assert how a disagreement is shown,
    # not which disagreements there are today.

    def test_every_state_has_a_governor(self):
        payload, problems = stategov.build(ROOT)
        self.assertEqual([c for c in STATES if c not in payload["states"]], [])
        self.assertFalse([p for p in problems if p.startswith("no governor")])

    def test_a_first_day_wikidata_disputes_is_not_shown(self):
        # On 2026-10-05: Kay Ivey (AL) and Kim Reynolds (IA), whose NGA pages
        # give the wrong day.
        payload, problems = stategov.build(ROOT)
        for problem in problems:
            if "took office on" in problem:
                self.assertEqual(payload["states"][problem[:2]]["governor"]["since"], "", problem)

    def test_a_chamber_the_sources_dispute_is_shown_as_disputed(self):
        payload, problems = stategov.build(ROOT)
        for problem in problems:
            if "Open States gives" in problem:
                self.assertEqual(payload["states"][problem[:2]]["legislature"], "disputed", problem)

    def test_trifectas_differ_from_ncsl_only_where_the_page_says_why(self):
        # Alaska, for its coalitions; or a state whose chambers the sources
        # dispute, shown as such.
        payload, _ = stategov.build(ROOT)
        ncsl = stategov.load_ncsl(ROOT)
        names = {"R": "R", "D": "D", "S": "divided", "N/A": "nonpartisan"}
        for code in STATES:
            ours = payload["states"][code]
            if names[ncsl["states"][code]["control"]] != ours["trifecta"]:
                self.assertTrue(ours.get("note") or ours["trifecta"] == "disputed", code)

    def test_no_headshot_on_the_page_is_heavier_than_the_cap(self):
        from kyc.photos import too_heavy
        cache = executives.load_cache(ROOT)["governors"]
        payload, _ = stategov.build(ROOT)
        for code, entry in payload["states"].items():
            # The NGA's; a governor's own office's is weighed in its
            # overrides.OFFICER_PHOTOS entry (TestOfficerPhotos).
            shown = entry["governor"].get("headshot")
            if shown and not entry["governor"].get("headshotPage"):
                gov = cache[code]
                weight = (gov.get("headshotWeight") if shown == gov["headshot"]
                          else gov.get("headshotSmallWeight"))
                self.assertIn(shown, (gov["headshot"], gov.get("headshotSmall")), code)
                self.assertEqual(too_heavy(weight), "", code)
                self.assertIsNotNone(weight, code)


class TestOfficeLinks(unittest.TestCase):
    """Five secretaries of state's biography links and Indiana's governor
    link answered 404; New Jersey's and Virginia's governors had no website
    (audit 2026-10-17, LINKS-08, LINKS-09)."""

    def test_a_dead_biography_is_dropped_and_the_office_page_kept(self):
        entry = {"sos": {"name": "Shenna Bellows", "bio": "https://www.maine.gov/sos/about/bio.html",
                         "website": "https://www.maine.gov/sos/"}}
        self.assertEqual(stategov.office_links("ME", entry), [])
        self.assertNotIn("bio", entry["sos"])
        self.assertEqual(entry["sos"]["website"], "https://www.maine.gov/sos/")

    def test_a_missing_website_is_filled_from_the_offices_own(self):
        entry = {"governor": {"name": "Mikie Sherrill"}}
        stategov.office_links("NJ", entry)
        self.assertEqual(entry["governor"]["website"], "https://nj.gov/governor/")

    def test_an_entry_the_roster_no_longer_needs_is_reported_not_applied(self):
        entry = {"governor": {"name": "Mike Braun", "website": "https://www.in.gov/gov/new.htm"}}
        problems = stategov.office_links("IN", entry)
        self.assertEqual(entry["governor"]["website"], "https://www.in.gov/gov/new.htm")
        self.assertTrue(problems and "may be unneeded" in problems[0])

    def test_the_build_applies_every_entry(self):
        _payload, problems = stategov.build(ROOT)
        self.assertFalse([p for p in problems if "OFFICE_LINKS" in p], problems)


class TestOfficerPhotos(unittest.TestCase):
    """STATEGOV-13: no attorney general had a photograph, and two governors,
    a lieutenant governor and six secretaries of state had none."""

    def entry(self, **who):
        from kyc.overrides import OFFICER_PHOTOS
        (code, office), photo = next((k, v) for k, v in sorted(OFFICER_PHOTOS.items())
                                     if k[1] == who.get("office", "sos"))
        return code, office, photo

    def test_a_photograph_is_given_while_the_roster_names_its_person(self):
        code, office, photo = self.entry()
        entry = {office: {"name": photo["name"]}}
        # The state's other offices' entries speak of their own holders.
        self.assertEqual([p for p in stategov.officer_photos(code, entry)
                          if p.startswith(f"{code} {office}:")], [])
        self.assertEqual(entry[office]["photo"], photo["photo"])
        self.assertEqual(entry[office]["photoBy"], photo["by"])
        self.assertEqual(entry[office]["photoPage"], photo["page"])

    def test_a_new_holder_gets_no_ones_photograph_and_it_is_said(self):
        code, office, _photo = self.entry()
        entry = {office: {"name": "Somebody Else"}}
        problems = stategov.officer_photos(code, entry)
        self.assertNotIn("photo", entry[office])
        self.assertTrue(problems and "no photograph is shown" in problems[0], problems)
        unconfirmed = {office: {"name": _photo["name"], "unconfirmed": True}}
        stategov.officer_photos(code, unconfirmed)
        self.assertNotIn("photo", unconfirmed[office])

    def test_a_governors_photograph_is_a_headshot_and_the_roster_s_own_stands(self):
        from unittest import mock

        from kyc import overrides
        code, photo = "ZZ", overrides._officer_photo(
            "Pat Doe", "https://gov.example.gov/doe.jpg", "https://gov.example.gov/",
            "Office of the Governor", (60_000, 320, 320), "The governor's home page.")
        patch = mock.patch.dict(overrides.OFFICER_PHOTOS, {(code, "governor"): photo})
        patch.start()
        self.addCleanup(patch.stop)
        entry = {"governor": {"name": photo["name"]}}
        stategov.officer_photos(code, entry)
        self.assertEqual(entry["governor"]["headshot"], photo["photo"])
        own = {"governor": {"name": photo["name"], "headshot": "https://www.nga.org/x.jpg"}}
        problems = stategov.officer_photos(code, own)
        self.assertEqual(own["governor"]["headshot"], "https://www.nga.org/x.jpg")
        self.assertTrue(problems and "may be unneeded" in problems[0], problems)

    def test_every_entry_is_a_light_photograph_carrying_its_evidence(self):
        from kyc.overrides import OFFICER_PHOTOS
        from kyc.photos import too_heavy
        for (code, office), photo in OFFICER_PHOTOS.items():
            with self.subTest(code=code, office=office):
                self.assertIn(office, ("governor", "lt", "ag", "sos"))
                self.assertTrue(photo["photo"].startswith("https://"))
                self.assertTrue(photo["page"].startswith("https://"))
                self.assertTrue(photo["by"] and photo["evidence"])
                self.assertRegex(photo["checked"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertEqual(too_heavy(photo["weight"]), "")
                self.assertLessEqual(photo["weight"]["bytes"], 300_000)

    def test_an_associations_card_is_matched_on_its_state_and_name_never_its_file(self):
        """NAAG's roster names each attorney general and the state beside
        the photograph; its files are not evidence (West Virginia's is
        "ag-WA-McCusker"). Every NAAG entry quotes a card naming its own
        state and the holder's surname, and is the card's own small size."""
        from kyc.overrides import OFFICER_PHOTOS
        from kyc.pages import state_name
        naag = {k: v for k, v in OFFICER_PHOTOS.items()
                if v["by"] == "National Association of Attorneys General"}
        self.assertTrue(naag)
        for (code, office), photo in naag.items():
            with self.subTest(code=code):
                self.assertEqual(office, "ag")
                card = photo["evidence"].split('card reads "', 1)[1].split('"', 1)[0]
                self.assertTrue(card.endswith(" " + state_name(code)), card)
                self.assertIn(photo["name"].split()[-1], card)
                self.assertLessEqual(max(photo["weight"]["width"], photo["weight"]["height"]), 300)
                # The file's own name is never the evidence: no entry's
                # state comes from it (West Virginia's card, filed
                # "ag-WA-McCusker", was dropped on 2026-10-25 once its
                # office's own photograph was shown smaller, rule 87).
                self.assertNotIn("card reads \"" + photo["photo"], photo["evidence"])

    def test_no_headshot_or_photograph_is_shown_uncredited(self):
        payload, _ = stategov.build(ROOT)
        for code, entry in payload["states"].items():
            gov = entry["governor"]
            if gov.get("headshot"):
                self.assertTrue(gov.get("headshotBy"), code)
            for office in ("lt", "ag", "sos"):
                person = entry.get(office) or {}
                if person.get("photo"):
                    self.assertTrue(person.get("photoBy"), (code, office))



class TestGovernorOverlayData(unittest.TestCase):
    """What the overlay shows of a governor and a candidate (rule 91): a date
    of birth only where the NGA and Wikidata agree (rule 54's pattern), the
    offices held only from the record read for this item or this article
    (rule 69), and the ids the overlay addresses them by (rule 27)."""

    def test_a_birth_date_is_shown_only_where_both_sources_give_the_same_day(self):
        self.assertEqual(stategov.agreed_birth("May 5, 1961", {"date": "1961-05-05", "precision": "day"}),
                         {"date": "1961-05-05", "nga": "May 5, 1961"})
        self.assertIsNone(stategov.agreed_birth("September 21, 1971", {"date": "1971-09-29", "precision": "day"}))
        self.assertIsNone(stategov.agreed_birth("May 5, 1961", {"date": "1961-05-05", "precision": "year"}))
        self.assertIsNone(stategov.agreed_birth(None, {"date": "1961-05-05", "precision": "day"}))
        self.assertIsNone(stategov.agreed_birth("May 5, 1961", None))

    def test_a_seat_in_congress_is_current_only_while_the_snapshot_seats_them(self):
        # The January sweep of 2026-11-11: six members of Congress who ran for
        # governor read "U.S. Representative since 2017" on their candidate
        # overlay and "2017-2027" on their own profile, and "A member of
        # Congress" after they had left.
        from kyc import overrides, statewide_photos
        bioguide = next(iter(overrides.OTHER_OFFICE_NOMINEES))
        span = {"office": "U.S. Representative", "state": "AZ", "district": 5, "from": "2017",
                "to": None, "end": "2027-01-03", "terms": 5, "current": True}
        cache = {"people": {"gov-AZ-pat-member": {
            "wikidata": "Q1", "wikipedia": "Pat Member", "asked": "Pat Member", "bioguide": bioguide,
            "congress": [span], "offices": [], "withheld": []}}}
        photos = {"photos": {statewide_photos.key("AZ", "governor", "Pat Member"): {
            "route": "member", "bioguide": bioguide}},
            "articles": {statewide_photos.key("AZ", "governor", "Pat Member"): {"article": "Pat Member"}}}

        def rows(as_of, sitting):
            entry = {"governor": {"name": "Gov", "party": "Republican", "partyKey": "R"},
                     "ballot2026": {"offices": {"governor": {"up": True, "candidates": {"candidates": [
                         {"name": "Pat Member", "party": "Republican"}]}}}}}
            stategov.attach_history("AZ", entry, {"name": "Gov"}, cache, photos, [], as_of, sitting)
            return entry["ballot2026"]["offices"]["governor"]["candidates"]["candidates"][0]

        seated = rows("2026-11-10", {bioguide})
        self.assertTrue(seated["politicalHistory"]["rows"][0]["current"])
        self.assertNotIn("memberFormer", seated)
        left = rows("2027-01-04", set())
        self.assertNotIn("current", left["politicalHistory"]["rows"][0])
        self.assertEqual(left["politicalHistory"]["rows"][0]["to"], "2027")
        self.assertTrue(left["memberFormer"])

    def test_the_history_attaches_only_for_the_rosters_item_and_the_linked_article(self):
        from kyc import statewide, statewide_photos
        raw = {"name": "Pat Governor", "wikidata": "Q777", "born": "November 2, 1963"}
        entry = {"governor": {"name": "Pat Governor", "party": "Republican", "partyKey": "R"},
                 "ballot2026": {"offices": {"governor": {"up": True, "candidates": {"candidates": [
                     {"name": "Jane Doe", "party": "Democratic"},
                     {"name": "Joe Roe", "party": "Republican", "printed": "ROE, JOE"},
                     {"name": "Sam Poe", "party": None, "writeIn": True}]}}}}}
        cache = {"people": {
            "gov-GA": {"wikidata": "Q777", "wikipedia": "Pat Governor",
                       "born": {"date": "1963-11-02", "precision": "day"}, "congress": [],
                       "offices": [{"office": "Governor of Georgia", "where": "Georgia", "district": None,
                                    "from": "2019", "to": None, "open": True, "agree": "exact"}],
                       "withheld": []},
            "gov-GA-jane-doe": {"wikidata": "Q500", "wikipedia": "Jane Doe (politician)",
                                "asked": "Jane Doe (politician)", "congress": [], "offices": [], "withheld": []},
            "gov-GA-joe-roe": {"wikidata": "Q501", "wikipedia": "Joe Roe", "asked": "Joe Roe (old)",
                               "congress": [], "offices": [], "withheld": []}}}
        photos = {"photos": {
            statewide_photos.key("GA", "governor", "Jane Doe"): {"route": "wikipedia", "article": "Jane Doe (politician)"},
            statewide_photos.key("GA", "governor", "ROE, JOE"): {"route": "wikipedia", "article": "Joe Roe"},
            statewide_photos.key("GA", "governor", "Sam Poe"): {"route": "wikipedia", "article": "Sam Poe"}}}
        problems = []
        stategov.attach_history("GA", entry, raw, cache, photos, problems)
        gov = entry["governor"]
        self.assertEqual(gov["id"], "gov-GA")
        self.assertEqual(gov["born"], {"date": "1963-11-02", "nga": "November 2, 1963"})
        self.assertEqual(gov["wikipedia"], "Pat Governor")
        self.assertEqual([r["office"] for r in gov["politicalHistory"]["rows"]], ["Governor of Georgia"])
        rows = {r["name"]: r for r in entry["ballot2026"]["offices"]["governor"]["candidates"]["candidates"]}
        self.assertEqual(rows["Jane Doe"]["id"], statewide.candidate_id("GA", "Jane Doe"))
        self.assertEqual(rows["Jane Doe"]["wikipedia"], "Jane Doe (politician)")
        self.assertIn("politicalHistory", rows["Jane Doe"])
        # Read from another article than the race's article links now: not shown, reported.
        self.assertEqual(rows["Joe Roe"]["wikipedia"], "Joe Roe")
        self.assertNotIn("politicalHistory", rows["Joe Roe"])
        self.assertTrue(any("Joe Roe" in p and "run 'history'" in p for p in problems))
        # A write-in gets an id and nothing else.
        self.assertEqual(set(rows["Sam Poe"]) & {"wikipedia", "politicalHistory"}, set())
        self.assertTrue(rows["Sam Poe"]["id"].startswith("gov-GA-"))
        # The roster's item moved: the record is not this item's.
        moved = {"governor": {"name": "Pat Governor", "party": "Republican", "partyKey": "R"}}
        problems = []
        stategov.attach_history("GA", moved, dict(raw, wikidata="Q999"), cache, photos, problems)
        self.assertNotIn("politicalHistory", moved["governor"])
        self.assertNotIn("born", moved["governor"])
        self.assertTrue(any("Q999" in p for p in problems))
        # A disagreement on the day is reported, never shown.
        differs = {"governor": {"name": "Pat Governor", "party": "Republican", "partyKey": "R"}}
        problems = []
        stategov.attach_history("GA", differs, dict(raw, born="November 3, 1963"), cache, photos, problems)
        self.assertNotIn("born", differs["governor"])
        self.assertTrue(any("was born" in p for p in problems))

    def test_the_build_gives_every_governor_an_id_and_a_candidate_a_record_only_with_its_article(self):
        payload, _problems = stategov.build(".")
        for code, state in payload["states"].items():
            self.assertEqual(state["governor"]["id"], f"gov-{code}")
            born = state["governor"].get("born")
            if born:
                self.assertEqual(set(born), {"date", "nga"})
            item = (state.get("ballot2026") or {}).get("offices", {}).get("governor") or {}
            for person in (item.get("candidates") or {}).get("candidates") or []:
                self.assertTrue(person["id"].startswith(f"gov-{code}-"))
                if "politicalHistory" in person:
                    self.assertIn("wikipedia", person)
            # Why no date is shown is recorded, a disagreement only where the
            # roster holds an item to compare with (rule 19; PR #195 review).
            gov = state["governor"]
            if not gov.get("since"):
                self.assertIn(gov.get("sinceWhy"), {"no-nga", "no-item", "no-date", "disagree"}, code)
            if not gov.get("born"):
                self.assertIn(gov.get("bornWhy"),
                              {"no-nga", "no-item", "not-read", "no-date", "disagree"}, code)
            if not gov.get("wikidata") and gov.get("bornWhy") == "disagree":
                self.fail(f"{code}: a disagreement claimed with no item read")

    def test_why_no_first_day_is_shown_is_said_in_rule_19s_terms(self):
        terms = ["January 14, 2019 - Current"]
        base = {"name": "Pat Governor", "party": "Republican", "partyKey": "R", "profile": "p",
                "terms": terms}
        # The roster holds no Wikidata item: nothing was compared.
        self.assertEqual(stategov._governor(dict(base))["sinceWhy"], "no-item")
        # An item with no start in the office.
        self.assertEqual(stategov._governor(dict(base, wikidata="Q1"))["sinceWhy"], "no-date")
        # Both dates, and they differ (Kay Ivey's, Kim Reynolds's).
        self.assertEqual(stategov._governor(dict(base, wikidata="Q1",
                                                 wikidataStarts=["2019-01-15"]))["sinceWhy"],
                         "disagree")
        agreed = stategov._governor(dict(base, wikidata="Q1", wikidataStarts=["2019-01-14"]))
        self.assertEqual((agreed["since"], agreed.get("sinceWhy")), ("January 14, 2019", None))
        self.assertEqual(stategov._governor(dict(base, terms=[]))["sinceWhy"], "no-nga")

    def test_why_no_date_of_birth_is_shown_is_said_in_rule_19s_terms(self):
        cache = {"people": {"gov-GA": {"wikidata": "Q777", "born": {"date": "1963-11-02",
                                                                     "precision": "day"},
                                       "congress": [], "offices": [], "withheld": []}}}

        def why(raw, people=cache):
            entry = {"governor": {"name": "Pat Governor", "party": "Republican", "partyKey": "R"}}
            stategov.attach_history("GA", entry, raw, people, {}, [])
            return entry["governor"].get("bornWhy"), entry["governor"].get("born")

        raw = {"name": "Pat Governor", "wikidata": "Q777", "born": "November 2, 1963"}
        self.assertEqual(why(raw)[0], None)
        self.assertEqual(why(dict(raw, born="November 3, 1963")), ("disagree", None))
        self.assertEqual(why(dict(raw, wikidata=None)), ("no-item", None))
        self.assertEqual(why(dict(raw, wikidata="Q888")), ("not-read", None))
        self.assertEqual(why(dict(raw, born=None)), ("no-nga", None))
        undated = {"people": {"gov-GA": dict(cache["people"]["gov-GA"], born=None)}}
        self.assertEqual(why(raw, undated), ("no-date", None))

    def test_a_candidates_article_member_and_finding_come_from_the_records(self):
        from kyc import statewide_photos
        entry = {"governor": {"name": "Pat Governor", "party": "Republican", "partyKey": "R"},
                 "ballot2026": {"offices": {"governor": {"up": True, "candidates": {"candidates": [
                     {"name": "Jane Doe", "party": "Democratic"},
                     {"name": "Tom Member", "party": "Republican"},
                     {"name": "Nobody Linked", "party": "Libertarian"},
                     {"name": "Not Read", "party": "Green"}]}}}}}
        k = lambda name: statewide_photos.key("GA", "governor", name)  # noqa: E731
        photos = {"articlesRead": "2026-11-03", "articles": {
            # Linked, though the photograph came by another route.
            k("Tom Member"): {"article": "Tom Member", "page": "2026 Georgia gubernatorial election"},
            k("Nobody Linked"): {"none": "not-linked", "page": "2026 Georgia gubernatorial election"}},
            "photos": {
                k("Jane Doe"): {"route": "wikipedia", "article": "Jane Doe (politician)"},
                k("Tom Member"): {"route": "member", "bioguide": "T000278"}}}
        stategov.attach_history("GA", entry, {"name": "Pat Governor"}, {"people": {}}, photos, [])
        rows = {r["name"]: r for r in entry["ballot2026"]["offices"]["governor"]["candidates"]["candidates"]}
        self.assertEqual(rows["Jane Doe"]["wikipedia"], "Jane Doe (politician)")
        self.assertEqual(rows["Tom Member"]["wikipedia"], "Tom Member")
        self.assertEqual(rows["Tom Member"]["member"], "T000278")
        self.assertEqual(rows["Nobody Linked"]["articleNone"], "not-linked")
        self.assertEqual(rows["Nobody Linked"]["articleRead"], "2026-11-03")
        # Nothing read: nothing claimed.
        self.assertEqual(set(rows["Not Read"]) & {"wikipedia", "articleNone", "articleRead", "member"},
                         set())


if __name__ == "__main__":
    unittest.main()
