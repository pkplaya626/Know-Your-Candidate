"""The site's words since Election Day (the sweep of 2026-11-11).

Each check makes the state it tests - a held election, a new Congress, a
place that is not a state - and asks the code that writes the words: the
build's side of one test of the phase (``share.post_election``, the day
after ``cycle.general_election_day``; ``cycle.phase`` for the record). The
page's side is in tests/render_test.js (testWordsSinceElectionDay and
testTheJanuaryPage).
"""

import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import (federal_build, fec, governor_share, pages, share, stategov, statewide,  # noqa: E402
                 summary, validate)
from kyc.normalize import NOT_READ_NEW_TERM, STATUS_LABELS  # noqa: E402

# The results read after Election Day, and before it.
AFTER = {"election": {"resultsAsOf": "2026-11-10"}}
BEFORE = {"election": {"resultsAsOf": "2026-10-30"}}
# A membership snapshot of the Congress the cycle elects, read after noon
# on January 3 (cycle.phase "record"), and one of the sitting Congress.
RECORD = {"fetched": "2027-01-04T15:00:00Z",
          "legislators": [{"chamber": "House", "termStart": "2027-01-03", "bioguide": "Z900001"}]}
CAMPAIGN = {"fetched": "2026-11-10T15:00:00Z",
            "legislators": [{"chamber": "House", "termStart": "2025-01-03", "bioguide": "Z900001"}]}


class TestAPlaceInASentence(unittest.TestCase):
    """Rule 75: "the District of Columbia" in a sentence, never "District of
    Columbia"; a territory is never "the state"."""

    def test_a_seat_at_large_names_the_place_in_its_own_words(self):
        self.assertEqual(share.seat_phrase("House • DC-AL"),
                         "the U.S. House in the District of Columbia (at large)")
        self.assertEqual(share.seat_phrase("House • VI-AL"),
                         "the U.S. House in the U.S. Virgin Islands (at large)")
        self.assertEqual(share.seat_phrase("House • WY-AL"), "the U.S. House in Wyoming (at large)")
        self.assertEqual(share.seat_phrase("Senate • AL"), "the U.S. Senate in Alabama")

    def test_a_profile_page_names_the_district_with_its_article(self):
        person = {"id": "N000147", "name": "Pat Example", "party": "Democrat", "state": "DC",
                  "chamber": "House", "officeLabel": "House • DC-AL"}
        html = share.render_profile(person, "example.org", {"N000147": person}, {})
        self.assertIn("for the District of Columbia (at large)", html)
        self.assertIn("the District of Columbia&#x27;s page</a>", html)
        self.assertNotIn("for District of Columbia", html)

    def test_a_link_to_a_state_page_names_it_as_the_page_names_itself(self):
        # Rule 75: one name in the navigation, the title and the links. The
        # page is titled "U.S. Virgin Islands" (the owner's decision of
        # 2026-11-13); while it was titled "Virgin Islands", "the U.S. Virgin
        # Islands’ page" named it otherwise (the review of PR #229).
        from kyc import pages
        person = {"id": "P000610", "name": "Pat Example", "party": "Democrat", "state": "VI",
                  "chamber": "House", "officeLabel": "House • VI-AL"}
        html = share.render_profile(person, "example.org", {"P000610": person}, {})
        self.assertIn("the U.S. Virgin Islands&#x27; page</a>", html)
        self.assertNotIn("the Virgin Islands&#x27; page", html)
        self.assertEqual(share.page_place("VI"), "the " + pages.state_name("VI"))
        self.assertEqual(share.page_place("TX"), "Texas")

    def test_the_virgin_islands_have_one_name_and_sources_another(self):
        # What a page shows, and what sources write: a roster's "Virgin
        # Islands", a Wikidata label, an association's address are matched by
        # the short name, never by the page's (kyc/pages.short_name).
        from kyc import normalize, pages, voting_dates
        self.assertEqual(pages.state_name("VI"), "U.S. Virgin Islands")
        self.assertEqual(pages.short_name("VI"), "Virgin Islands")
        self.assertEqual(normalize.US_STATES["VIRGIN ISLANDS"], "VI")
        self.assertEqual(voting_dates.place("VI"), "the U.S. Virgin Islands")
        # Every other place is shown by the name sources write.
        for code in pages.STATE_NAMES:
            if code != "VI":
                self.assertEqual(pages.state_name(code), pages.short_name(code), code)
        self.assertEqual(pages.short_name("ZZ"), "ZZ")
        # The page's own headline, and a territory in a sentence (rule 75).
        headline, intro = pages.district_page_text("VI", 1)
        self.assertEqual(headline, "U.S. Virgin Islands' seat in the House")
        self.assertTrue(intro.startswith("The U.S. Virgin Islands elects a non-voting delegate"), intro)
        self.assertTrue(pages.district_page_text("DC", 1)[1].startswith("The District of Columbia elects"))
        self.assertTrue(pages.district_page_text("GU", 1)[1].startswith("Guam elects"))
        # Text is matched by the short name: a label naming the territory in
        # either form is found, and never by a longer state's name.
        from kyc import nominee_photos
        self.assertIn("Virgin Islands", nominee_photos.states_named(
            "Delegate to the U.S. House from the United States Virgin Islands"))

    def test_a_sentence_names_a_place_with_its_article_and_islands_take_no_second_s(self):
        # Rule 75, found on PR #246's own built pages: "Open their record on
        # U.S. Virgin Islands’s page", "2026 races for Congress in U.S. Virgin
        # Islands", "also hears appeals from New Jersey, Pennsylvania and U.S.
        # Virgin Islands". Each predates the rename (main: "Northern Mariana
        # Islands’s page", "in District of Columbia").
        from kyc import government_maps, governor_share, pages, voting_dates
        for code, words in voting_dates.PLACES.items():
            self.assertEqual(pages.sentence_place(code), words)
            self.assertTrue(words.startswith("the "), words)
        self.assertEqual(pages.sentence_place("TX"), "Texas")
        self.assertEqual(pages._opening(pages.sentence_place("DC")), "The District of Columbia")
        # A governor's share page names the state page it opens.
        for code, words in (("VI", "the U.S. Virgin Islands’ page"), ("MP", "the Northern Mariana Islands’ page"),
                            ("GU", "Guam’s page"), ("GA", "Georgia’s page")):
            for kind in ("governor", "candidate"):
                _href, label, plain = governor_share._view({"code": code, "kind": kind}, "gov-" + code)
                self.assertTrue(label.endswith(" on " + words), label)
                self.assertIn(">" + words + "</a>", plain)
                self.assertNotIn("Islands’s", label + plain)
        # A district page: its headline is the page's name, its sentences the place's.
        for code, opening in (("VI", "The U.S. Virgin Islands' "), ("MP", "The Northern Mariana Islands' "),
                              ("DC", "The District of Columbia's "), ("GU", "Guam's "), ("TX", "Texas's ")):
            html = pages.render_district_page(code, "example.org")
            description = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
            self.assertTrue(description.replace("&#x27;", "'").startswith(opening + "House districts"), description)
            self.assertNotIn("Islands&#x27;s", html)
            self.assertNotIn("Islands's", html)
        self.assertIn("the District of Columbia&#x27;s page</a> lists its",
                      pages.render_district_page("DC", "example.org"))
        # A state page's description, and its races' heading.
        for code, opening in (("VI", "The U.S. Virgin Islands' delegate"), ("DC", "The District of Columbia's delegate"),
                              ("GU", "Guam's delegate")):
            html = pages.render_state(code, "example.org")
            description = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
            self.assertTrue(description.replace("&#x27;", "'").startswith(opening), description)
        # The circuits' sentences on the guide's map.
        facts = government_maps._circuits()["facts"]
        self.assertTrue(facts["PA"].endswith("Delaware, New Jersey and the U.S. Virgin Islands."), facts["PA"])
        self.assertIn("Hawaii and the Northern Mariana Islands.", facts["CA"])
        for code, text in facts.items():
            self.assertIsNone(re.search(
                r"\b(?:from|and|,) (?:U\.S\. Virgin Islands|Northern Mariana Islands|District of Columbia)\b", text),
                (code, text))

    def test_the_governor_overlays_never_call_a_territory_a_state(self):
        self.assertNotIn("state", governor_share.PAST)
        self.assertEqual(governor_share.PAST,
                         "This site does not read the election’s results and names no winner")


class TestAPlaceInASentenceWhereverItIsWritten(unittest.TestCase):
    """What the second read of PR #246 found the suites did not hold: the
    plain races heading, the guide's typed sentences, and the one table and
    one rule a sentence's place comes from."""

    def test_the_plain_races_heading_names_the_place_as_a_sentence_does(self):
        # pages.state_static, the heading a reader without scripts and a
        # crawler see (rule 96): "2026 races for Congress in the District of
        # Columbia". The check makes the race it needs; it asks no day's data.
        from kyc import pages, voting_dates
        for code in list(voting_dates.PLACES) + ["GU", "TX"]:
            person = {"id": "Z1", "name": "Pat Example", "party": "Democrat", "state": code,
                      "chamber": "House", "district": 0, "officeLabel": f"House • {code}-AL",
                      "raceId": f"H-{code}-00-2026"}
            race = {"id": f"H-{code}-00-2026", "state": code, "chamber": "House", "district": 0,
                    "label": f"{code} at large", "incumbentIds": ["Z1"], "candidateIds": []}
            html = pages.render_state(code, "example.org", profiles=[person], races=[race])
            heading = re.search(r'<section class="state-section" id="races">\s*<h2[^>]*>([^<]*)</h2>', html)
            self.assertIsNotNone(heading, code)
            self.assertTrue(heading.group(1).endswith(" races for Congress in " + pages.sentence_place(code)),
                            heading.group(1))

    def test_one_table_names_a_place_in_a_sentence(self):
        # share.page_place kept a list of its own beside voting_dates.PLACES.
        from kyc import pages, voting_dates
        for code in pages.STATE_NAMES:
            self.assertEqual(share.page_place(code), pages.sentence_place(code), code)
            self.assertEqual(voting_dates.place(code), pages.sentence_place(code), code)
        self.assertFalse(hasattr(share, "_WITH_THE"))

    def test_one_rule_writes_a_possessive_with_its_sentences_apostrophe(self):
        # pages._possessive wrote the plain apostrophe alone, and the page
        # text's "’" was a second copy of the Islands rule in governor_share.
        from kyc import pages
        self.assertEqual(pages._possessive("Texas"), "Texas's")
        self.assertEqual(pages._possessive("Guam", "’"), "Guam’s")
        self.assertEqual(pages._possessive("the U.S. Virgin Islands"), "the U.S. Virgin Islands'")
        self.assertEqual(pages._possessive("the Northern Mariana Islands", "’"), "the Northern Mariana Islands’")
        import inspect
        self.assertNotIn('endswith("Islands")', inspect.getsource(governor_share))

    def test_the_guide_names_the_territory_as_the_pages_do(self):
        # government_text is typed prose: outside a quoted title and the name
        # of a body ("District Court of the Virgin Islands", "Legislature of
        # the Virgin Islands"), the territory is "the U.S. Virgin Islands".
        from kyc import government_text

        def strings(node):
            if isinstance(node, str):
                yield node
            elif isinstance(node, dict):
                for value in node.values():
                    yield from strings(value)
            elif isinstance(node, (list, tuple)):
                for value in node:
                    yield from strings(value)

        bare = re.compile(r"(?<!U\.S\. )(?<!United States )Virgin Islands")
        body = re.compile(r"(?:Court|Legislature|System|Government|Governor|Constitution|Code|Act|Board|University) "
                          r"of the Virgin Islands")
        # Reserved for the owner's own read (the November 17 runoff's
        # paragraph and its source label), and the editor's note that says
        # so: take each out of this list as it is read.
        reserved = ("The Delegates from Guam and the Virgin Islands are elected by a majority",
                    "48 U.S.C. 1712 (the Delegates from Guam and the Virgin Islands)",
                    "its paragraph's second read is the owner's")
        found, looked = set(), 0
        for name in dir(government_text):
            value = getattr(government_text, name)
            if name.startswith("_") or not isinstance(value, (dict, list, tuple)):
                continue
            for text in strings(value):
                looked += "Virgin Islands" in text
                if any(words in text for words in reserved):
                    continue
                plain = re.sub(r"“[^”]*”", "", body.sub("", text))
                if bare.search(plain):
                    found.add(text[:160])
        self.assertEqual(sorted(found), [])
        self.assertGreater(looked, 0)        # the guide names the territory: something was read


class TestSourcesAreReadByTheNameSourcesWrite(unittest.TestCase):
    """Rule 75: what a page shows (pages.state_name) and what sources write
    (pages.short_name) are two names. Each check gives a state the readers
    do reach a page name no source writes, and asks the reader the same
    question: a call site that went back to the page's name answers
    otherwise, whichever place's names differ that day (the second read of
    PR #246: nothing noticed any of the six call sites going back)."""

    def shown(self, code):
        from kyc import pages
        return mock.patch.dict(pages.STATE_NAMES, {code: "Shown Only"})

    def test_a_wikidata_label_ties_a_nominee_by_the_name_sources_write(self):
        from kyc import nominee_photos
        profile = {"state": "OH"}
        with self.shown("OH"):
            tie, why = nominee_photos.second_tie(
                profile, [{"election": "2026 United States Senate election in Ohio"}])
            self.assertIsNotNone(tie, why)
            self.assertIn("P3602", tie)
            tie, why = nominee_photos.second_tie(
                profile, [{"office": "member of the Ohio House of Representatives", "district": ""}])
            self.assertIsNotNone(tie, why)
        # And for the one place whose two names differ today.
        self.assertEqual(nominee_photos.second_tie(
            {"state": "VI"}, [{"office": "Governor of Virgin Islands", "district": ""}])[1], "")

    def test_a_seat_held_is_placed_by_the_name_sources_write(self):
        # held_seats compared the history record's place, a source's label,
        # with the page's name.
        from kyc import nominee_photos
        profile = {"id": "Z1", "state": "OH", "wikipedia": "Pat Example"}
        history = {"people": {"Z1": {"asked": "Pat Example", "offices": [
            {"office": "member of the Ohio Senate", "where": "Ohio", "open": True, "agree": "exact"}]}}}
        self.assertEqual(nominee_photos.held_seats(profile, history), {("OH", "upper")})
        with self.shown("OH"):
            self.assertEqual(nominee_photos.held_seats(profile, history), {("OH", "upper")})

    def test_an_office_page_names_its_holder_past_the_name_sources_write(self):
        from kyc import officers
        text = "Phil Weiser Colorado Attorney General"
        self.assertTrue(officers.names_holder("Phil Weiser", text, "ag", "CO"))
        with self.shown("CO"):
            self.assertTrue(officers.names_holder("Phil Weiser", text, "ag", "CO"))
        self.assertTrue(officers.names_holder(
            "Pat Example", "Pat Example Virgin Islands Attorney General", "ag", "VI"))

    def test_a_likeness_is_named_by_the_name_sources_write(self):
        from kyc import officers
        page = '<img src="/files/ag.jpg" alt="Colorado Attorney General Phil Weiser">'
        pages_read = [("https://coag.gov/about/", page)]
        self.assertEqual(len(officers.likeness_candidates("Phil Weiser", "CO", pages_read)), 1)
        with self.shown("CO"):
            self.assertEqual(len(officers.likeness_candidates("Phil Weiser", "CO", pages_read)), 1)

    def test_the_roster_address_is_built_from_the_name_sources_write(self):
        from kyc import government_maps, officers, pages

        class Stop(Exception):
            pass

        asked = []

        def get(url, *args, **kwargs):
            asked.append(url)
            if "usa.gov" in url:
                raise Stop(url)
            return ""

        every = {code: "Shown Only " + code for code in pages.STATE_NAMES}
        with mock.patch.dict(pages.STATE_NAMES, every), mock.patch.object(officers, "_get", get), \
                mock.patch.object(officers, "parse_raga", lambda page: {}), \
                mock.patch.object(officers, "parse_daga", lambda page: {}), \
                mock.patch.object(officers.time, "sleep", lambda s: None):
            with self.assertRaises(Stop):
                officers.fetch_attorneys_general(pause=0)
        first = next(iter(government_maps.STATES))
        slug = re.sub(r"[^a-z]+", "-", pages.short_name(first).lower()).strip("-")
        self.assertEqual(asked[-1], officers.USAGOV_URL.format(slug=slug))

    def test_a_court_page_is_read_for_the_name_sources_write(self):
        from kyc import court_photos, courts, pages
        code = next(c for c, recipe in sorted(courts.COURTS.items())
                    if len(c) == 2 and not recipe.get("browser") and recipe.get("format") != "pdf")
        seen = []

        def photo_for(name, members, read_pages, place, measure, passed_over=None):
            seen.append(set(place))
            return None, "none"

        with self.shown(code), mock.patch.object(court_photos, "photo_for", photo_for), \
                mock.patch.object(court_photos, "bio_pages", lambda *a, **k: {}):
            court_photos.add_justice_photos({code: {"members": ["Pat Example"]}}, {code: "<html></html>"},
                                            get=lambda url: "", pause=0)
        self.assertEqual(len(seen), 1)
        self.assertTrue(set(court_photos._split(pages.short_name(code))) <= seen[0], seen[0])
        self.assertFalse(set(court_photos._split("Shown Only")) & seen[0], seen[0])

    def test_a_legislature_is_named_by_its_own_name_on_its_page_and_its_credit(self):
        # Two helpers claim the body's own name: the legislature page's title
        # and the photograph's credit. Both build it from the same table.
        from kyc import government_maps, legphotos
        with self.shown("MT"):
            self.assertEqual(legphotos.legislature_name("MT"), "Montana Legislature")
            self.assertEqual(government_maps.legislature_title("MT"), "Montana Legislature")
        for code in government_maps.STATES:
            if code != "NE":
                self.assertEqual(government_maps.legislature_title(code), legphotos.legislature_name(code), code)

    def test_a_races_article_is_asked_for_by_the_name_sources_write(self):
        # statewide_photos built Wikipedia's title from the page's name, and
        # was right for the Virgin Islands only through its own special case.
        from kyc import statewide_photos
        with self.shown("OH"):
            self.assertEqual(statewide_photos.race_titles("OH", "governor"), ["2026 Ohio gubernatorial election"])
        self.assertEqual(statewide_photos.race_titles("VI", "governor"),
                         ["2026 United States Virgin Islands gubernatorial election"])

    def test_no_reader_of_sources_asks_for_the_page_name(self):
        # As CI greps for onclick=: a reader that matches a source's words,
        # or builds a source's address, calls short_name, never state_name.
        import inspect
        from kyc import court_photos, legphotos, nominee_photos, officers, statewide_photos
        for module in (court_photos, legphotos, nominee_photos, officers, statewide_photos):
            self.assertNotRegex(inspect.getsource(module), r"\bstate_name\b", module.__name__)


class TestSeatUpInOneReading(unittest.TestCase):
    """share.seat_up and KYC.seatUpYear: a member seated for a term begun
    after Election Day says when their seat is next up, re-elected or new."""

    def member(self, **extra):
        return dict({"id": "Z1", "name": "Pat Example", "chamber": "House", "electionYear": 2028,
                     "term_start": "2027-01-03 - 2029-01-03"}, **extra)

    def test_a_reelected_holder_and_a_newcomer_on_one_term_read_alike(self):
        self.assertEqual(share.seat_up(self.member(seatUp2026=True)), "Seat up in 2028")
        self.assertEqual(share.seat_up(self.member(seatUp2026=False)), "Seat up in 2028")

    def test_a_seat_on_the_2026_ballot_before_the_new_term_says_nothing(self):
        self.assertIsNone(share.seat_up(self.member(
            seatUp2026=True, electionYear=2026, term_start="2025-01-03 - 2027-01-03")))

    def test_a_former_member_has_no_seat_up(self):
        self.assertIsNone(share.seat_up(self.member(formerMember={"left": "2027-01-03"})))

    def test_a_winner_seated_in_december_for_the_old_term_says_nothing(self):
        # The review of PR #229: a term begun after Election Day that ends
        # with the cycle's Congress read "Seat up in 2026", a day gone by.
        self.assertIsNone(share.seat_up(self.member(
            seatUp2026=True, electionYear=2026, term_start="2026-12-08 - 2027-01-03")))


class TestThePagesWrittenOnce(unittest.TestCase):
    """about.html and districts/index.html, written by the build, in the
    tense of the results it holds (share.post_election)."""

    def test_the_about_page_names_its_datasets_in_the_past_tense_after_the_election(self):
        before = pages.render_about("example.org", {})
        after = pages.render_about("example.org", {}, post=True)
        self.assertIn("Who is running, and their money", before)
        self.assertIn("who is on the ballot", before)
        self.assertIn("Who ran, and their money", after)
        self.assertIn("Primary and November results, and who was on the ballot", after)
        self.assertNotIn("Who is running", after)
        self.assertNotIn("who is on the ballot", after)
        # The "Last read" words are the dataset's, whatever its name.
        self.assertIn("Each profile gives the date its figures run through", after)

    def test_the_districts_directory_too(self):
        self.assertIn("who is on the November ballot",
                      pages.render_districts_index("example.org", BEFORE))
        after = pages.render_districts_index("example.org", AFTER)
        self.assertIn("who was on the November ballot", after)
        self.assertNotIn("who is on the November ballot", after)


class TestTheHolderLineAfterTheElection(unittest.TestCase):
    """statewide.holder_status's "may or may not be" is a line the page
    shows only until the election: after it, it is no problem to settle."""

    LISTED = {"list": {"url": "https://sos.example.gov/list", "by": "Secretary of State",
                       "kind": "candidate list"},
              "candidates": [{"name": "Pat Lee", "surname": "Lee"},
                             {"name": "Sam Lee", "surname": "Lee"}]}

    def test_an_unsettled_holder_is_a_problem_until_the_election(self):
        status, problem = stategov.holder_line("TN", "governor", "Bill Lee", None, self.LISTED)
        self.assertEqual(status["why"], "unchecked")
        self.assertIn("may or may not be Bill Lee", problem)
        status, problem = stategov.holder_line("TN", "governor", "Bill Lee", None, self.LISTED,
                                               after=True)
        self.assertEqual(status["why"], "unchecked")
        self.assertIsNone(problem)


class TestACandidatesOfficesOnceTheCongressSits(unittest.TestCase):
    """A governor candidate's other office the record found open is not said
    to be held once the new Congress sits (history.for_page's before_seat)."""

    def entry(self):
        return {"governor": {"name": "Gov Example"},
                "ballot2026": {"offices": {"governor": {"candidates": {"candidates": [
                    {"name": "Pat Example"}]}}}}}

    def history(self):
        cid = statewide.candidate_id("ZZ", "Pat Example")
        return {"read": "2026-10-30", "people": {cid: {
            "asked": "Pat Example", "congress": [],
            "offices": [{"office": "Member of the State Senate", "where": "Examplestate",
                         "district": None, "from": "2014", "to": None, "open": True,
                         "agree": "exact"}]}}}

    def rows(self, record):
        entry = self.entry()
        with mock.patch("kyc.stategov.candidate_member", return_value=None), \
                mock.patch("kyc.statewide_photos.article_of",
                           return_value={"article": "Pat Example", "read": "2026-10-30"}):
            stategov.attach_history("ZZ", entry, {}, self.history(), {}, [], "2027-01-04",
                                    set(), record)
        row = entry["ballot2026"]["offices"]["governor"]["candidates"]["candidates"][0]
        return row["politicalHistory"]["rows"]

    def test_open_while_the_campaign_runs_and_open_when_read_once_it_sits(self):
        self.assertTrue(self.rows(False)[0].get("current"))
        sat = self.rows(True)[0]
        self.assertFalse(sat.get("current"))
        self.assertEqual(sat.get("openWhenRead"), "2026-10-30")


class TestTheStrictCheckInJanuary(unittest.TestCase):

    def member(self, **extra):
        return dict({"id": "F000478", "name": "Pat Fry", "isCandidate": False, "chamber": "House",
                     "state": "SC", "officeLabel": "House • SC-7", "party": "Republican",
                     "status": "Active Member", "alsoRunningSeat": "Senate • SC"}, **extra)

    def codes(self, profiles, snapshot):
        return [i for i in validate.check_overrides(profiles, {"members": [], "candidates": []},
                                                    snapshot) if i.code == "dual-role"]

    def test_a_dual_role_is_a_campaign_note_and_says_one_member_as_one(self):
        found = self.codes([self.member()], CAMPAIGN)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].message, "1 sitting member is also a 2026 candidate")
        self.assertEqual(self.codes([self.member()], RECORD), [])

    def test_a_member_off_the_ballot_who_has_left_is_not_called_sitting(self):
        former = self.member(id="B000001", name="Vern Example", alsoRunningSeat=None,
                             raceStatus="unlisted", formerMember={"left": "2027-01-03"},
                             status="Former member: left office 2027-01-03")
        sitting = self.member(id="B000002", name="Sam Example", alsoRunningSeat=None,
                              raceStatus="unlisted")
        issue = [i for i in validate.check_results([former, sitting], [])
                 if i.code == "member-not-on-ballot"][0]
        self.assertTrue(issue.message.startswith(
            "1 sitting member and 1 member who has since left Congress are absent"), issue.message)
        self.assertTrue(any("Vern Example" in d and "has left Congress" in d for d in issue.detail))
        only = [i for i in validate.check_results([former], []) if i.code == "member-not-on-ballot"][0]
        self.assertTrue(only.message.startswith("1 member who has since left Congress is absent"),
                        only.message)


class TestLeadersNotYetRecorded(unittest.TestCase):
    """The search's "Leaders in Congress" in the first days of a Congress
    says the federal page's words (federal_build.not_yet_recorded)."""

    def test_the_words_are_the_federal_pages(self):
        self.assertEqual(federal_build.not_yet_recorded(120, "Speaker"),
                         "congress-legislators has not yet recorded the 120th Congress's Speaker")

    def test_said_only_where_no_sitting_member_holds_a_post(self):
        member = {"id": "Z900001", "name": "Pat Example", "isCandidate": False, "chamber": "House",
                  "state": "OH", "party": "Republican", "officeLabel": "House • OH-1"}
        built = summary.build([dict(member)], snapshot=RECORD)
        self.assertEqual(built["leadersUnrecorded"],
                         "congress-legislators has not yet recorded the 120th Congress's leaders; "
                         "this site names them once it does.")
        led = summary.build([dict(member, leadership=list(summary.PRINCIPAL_POSTS))], snapshot=RECORD)
        self.assertNotIn("leadersUnrecorded", led)

    def test_asked_post_by_post(self):
        # The review of PR #229: a record holding the Speaker and not the
        # Senate's leaders said nothing, and "Senate majority leader" fell
        # back to career text without a word.
        member = {"id": "Z900001", "name": "Pat Example", "isCandidate": False, "chamber": "House",
                  "state": "OH", "party": "Republican", "officeLabel": "House • OH-1"}
        some = summary.build([dict(member, leadership=["Speaker of the House", "House Majority Leader",
                                                       "House Minority Leader"])], snapshot=RECORD)
        self.assertEqual(some["leadersUnrecorded"],
                         "congress-legislators has not yet recorded the 120th Congress's President "
                         "Pro Tempore of the Senate, Senate Majority Leader, or Senate Minority Leader; "
                         "this site names them once it does.")


class TestASeatedWinnersMoneyNotReadYet(unittest.TestCase):
    """A winner seated for a new term whose money nothing read holds: said as
    that (rule 19), never "No data"."""

    def winner(self, **extra):
        return dict({"id": "Z900002", "name": "Pat Newcomer", "isCandidate": False,
                     "chamber": "House", "state": "OH", "district": "District 1",
                     "raceRole": "winner", "receipts": "No data", "disbursements": "No data",
                     "quality": {"receipts": "unknown", "disbursements": "unknown"}}, **extra)

    def test_unread_is_said_as_unread(self):
        person = self.winner()
        fec.apply_cache([person], {})
        self.assertEqual(person["quality"]["receipts"], NOT_READ_NEW_TERM)
        self.assertEqual(person["receipts"], STATUS_LABELS[NOT_READ_NEW_TERM])
        self.assertEqual(person["receipts"], "No FEC figures held yet")
        # One absence in the dialog, not two (rule 19).
        self.assertEqual(person["quality"]["funding_sources"], NOT_READ_NEW_TERM)

    def test_a_real_funding_line_is_never_replaced_by_the_absence(self):
        person = self.winner(funding_sources="Individual 80%")
        fec.apply_cache([person], {})
        self.assertEqual(person["funding_sources"], "Individual 80%")

    def test_totals_cached_under_a_curated_rows_name_are_found_by_the_id(self):
        # The review of PR #229: Andy Barr's Senate campaign is cached as
        # "andy barr|KY|S"; seated, his profile is keyed by the roster's
        # "Garland Barr", and a fold that asked only "fec:<id>" keys told the
        # page this site held no totals for a campaign it held at $12.5m.
        person = self.winner(name="Andy Barr", rosterName="Garland Barr", chamber="Senate",
                             state="KY", district=None, fecCandidateId="S6KY00286",
                             rosterFecId="H0KY06104")
        cache = {
            "andy barr|KY|S": {"found": True, "name": "Andy Barr", "candidate_id": "S6KY00286",
                               "receipts": 12541350.16, "disbursements": 9000000.0,
                               "cash_on_hand": 3000000.0, "election_year": 2026,
                               "coverage_start": "2025-01-01", "coverage_end": "2026-09-30"},
            "garland barr|KY|H": {"found": True, "name": "Garland Barr",
                                  "candidate_id": "H0KY06104", "receipts": 10.0},
        }
        fec.apply_cache([person], cache)
        self.assertNotIn("receipts", person.get("quality") or {})
        self.assertEqual(person["receipts"], "$12,541,350.16")
        self.assertEqual(person["fecCandidateId"], "S6KY00286")

    def test_one_id_under_two_keys_is_read_through_the_later_date(self):
        cache = {"a|KY|S": {"candidate_id": "S1", "receipts": 1.0, "coverage_end": "2026-06-30"},
                 "fec:S1": {"candidate_id": "S1", "receipts": 2.0, "coverage_end": "2026-09-30"},
                 "b|KY|S": {"candidate_id": "S2", "receipts": None}}
        index = fec.totals_by_candidate_id(cache)
        self.assertEqual(index["S1"]["receipts"], 2.0)
        self.assertNotIn("S2", index)

    def test_a_folded_filing_still_gives_its_totals(self):
        person = self.winner(fecCandidateId="H6OH01001")
        fec.apply_cache([person], {"fec:H6OH01001": {
            "candidate_id": "H6OH01001", "receipts": 1000.0, "disbursements": 500.0,
            "cash_on_hand": 500.0, "election_year": 2026,
            "coverage_start": "2025-01-01", "coverage_end": "2026-11-23"}})
        self.assertNotIn("receipts", person.get("quality") or {})
        self.assertNotEqual(person["receipts"], STATUS_LABELS[NOT_READ_NEW_TERM])

    def test_a_member_who_did_not_win_a_new_seat_is_untouched(self):
        person = self.winner(raceRole=None)
        fec.apply_cache([person], {})
        self.assertEqual(person["receipts"], "No data")


if __name__ == "__main__":
    unittest.main()
