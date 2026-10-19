"""Share pages and the state pages' plain lists (rule 96; TECH-09, TECH-10).

A profile or a race lives behind a fragment that crawlers drop, so every
shared person unfurled as the home page's card; and a state page with
scripts off read "Loading..." for ever. The words each page gives a person
are the profile dialog's, which the render suite compares for every profile
(``testSharePages``); these check the pipeline's side.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, pages, share  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def person(**kwargs):
    base = {"id": "X000001", "name": "Test Member", "chamber": "House", "party": "Republican",
            "state": "TX", "district": "District 3", "districtNum": 3,
            "officeLabel": "House • TX-3", "status": "Active Member", "isCandidate": False,
            "raceId": "H-TX-03-2026", "raceStatus": "nominee", "quality": {}}
    base.update(kwargs)
    return base


def race(**kwargs):
    base = {"id": "H-TX-03-2026", "chamber": "House", "state": "TX", "district": 3,
            "label": "TX-3 — U.S. House", "year": 2026, "incumbentIds": ["X000001"],
            "candidateIds": [], "primaryDate": "2026-03-03", "results": {},
            "incumbent": {"name": "Test Member", "party": "Republican", "seated": True}}
    base.update(kwargs)
    return base


def words(item, *others, races=(), post=False):
    by_id = {p["id"]: p for p in (item,) + others}
    return share.status_words(item, by_id, {r["id"]: r for r in races}, post)


class TestStatusWords(unittest.TestCase):
    """The profile dialog's words (KYC.standing, "long"), status by status."""

    def test_a_member_renominated_and_a_challenger_on_the_ballot(self):
        self.assertEqual(words(person()), "Renominated for 2026")
        self.assertEqual(words(person(isCandidate=True, id="FEC_1")), "On the November ballot")

    def test_a_member_leaving_and_an_appointee_leaving(self):
        self.assertEqual(words(person(raceStatus="unlisted")), "Not running for re-election in 2026")
        self.assertEqual(words(person(raceStatus="withdrawn")), "Not running for re-election in 2026")
        self.assertEqual(words(person(raceStatus="unlisted", appointed=True)), "Not running in 2026")

    def test_an_independent_nominee_did_not_win_a_primary(self):
        self.assertEqual(words(person(isCandidate=True, party="Independent")), "On the November ballot")

    def test_an_all_party_primary_and_a_certified_list(self):
        self.assertEqual(words(person(allPartyPrimary="top-two")), "Advanced to the November ballot")
        self.assertEqual(words(person(raceStatusSource="certified")), "On the November ballot")
        self.assertEqual(words(person(isCandidate=True, raceStatus="unlisted",
                                      raceStatusSource="certified")), "Not on the November ballot")

    def test_louisianas_qualified_list(self):
        self.assertEqual(words(person(isCandidate=True, raceStatus="qualified",
                                      raceStatusSource="qualified")),
                         "On the November 3 open-primary ballot")
        self.assertEqual(words(person(isCandidate=True, raceStatus="unlisted",
                                      raceStatusSource="qualified")),
                         "Not on the November 3 open-primary ballot")

    def test_after_election_day_a_nominee_awaits_the_result(self):
        self.assertEqual(words(person(), post=True), "On the November ballot: awaiting result")
        self.assertEqual(words(person(raceStatus="elected"), post=True), "Re-elected in November")
        self.assertEqual(words(person(isCandidate=True, raceStatus="defeated"), post=True),
                         "Lost the November election")

    def test_a_filer_the_results_do_not_settle(self):
        self.assertEqual(words(person(isCandidate=True, raceStatus=None, maybeNamed=["A B"])),
                         "Result not matched")
        self.assertEqual(words(person(isCandidate=True, raceStatus=None, ballotUnknown=True)),
                         "Ballot status not known")
        self.assertEqual(words(person(isCandidate=True, raceStatus=None,
                                      unprinted={"kind": "write-in"})), "Write-in candidate")
        # No primary in the calendar and no results read: not known either.
        none = race(primaryDate=None, results=None)
        self.assertEqual(words(person(isCandidate=True, raceStatus=None), races=[none]),
                         "Ballot status not known")
        self.assertIsNone(words(person(isCandidate=True, raceStatus=None), races=[race()]))

    def test_a_member_running_for_another_seat_reads_as_that_race(self):
        member = person(raceStatus="unlisted", contestRaceId="S-TX-2026",
                        contestLabel="Senate • TX", alsoRunningId="FEC_S1")
        filing = person(id="FEC_S1", isCandidate=True, raceId="S-TX-2026", raceStatus="nominee")
        self.assertEqual(words(member, filing), "On the November ballot for Senate • TX")

    def test_a_ballot_line_not_the_partys(self):
        self.assertEqual(words(person(isCandidate=True, ballotLine="Speak The Truth")),
                         "On the November ballot – Speak The Truth line")

    def test_a_senator_whose_seat_is_not_up_has_none(self):
        self.assertIsNone(words(person(chamber="Senate", raceId=None, raceStatus=None)))

    def test_post_election_is_the_day_the_results_were_read(self):
        self.assertFalse(share.post_election({"election": {"resultsAsOf": "2026-11-03"}}))
        self.assertTrue(share.post_election({"election": {"resultsAsOf": "2026-11-04"}}))
        self.assertFalse(share.post_election({}))


class TestSharePhoto(unittest.TestCase):
    """A share image is a photograph that came by a sourced route (rule 24),
    or the site's card: never a URL from a fallback chain."""

    def test_the_articles_own_sizes_the_clerks_and_a_credited_campaigns(self):
        sized = person(photoSet=[[120, "https://u.test/120px-a.jpg"], [330, "https://u.test/330px-a.jpg"],
                                 [960, "https://u.test/960px-a.jpg"]],
                       photo_url="https://u.test/960px-a.jpg", photoSource="wikipedia")
        self.assertEqual(share.og_photo(sized), "https://u.test/330px-a.jpg")
        clerk = person(photo_url="https://clerk.house.gov/images/members/X000001.jpg",
                       photoSource="clerk.house.gov")
        self.assertEqual(share.og_photo(clerk), clerk["photo_url"])
        campaign = person(photo_url="https://site.test/me.jpg", photoSource="campaign-site",
                          photoCredit={"by": "The campaign"})
        self.assertEqual(share.og_photo(campaign), campaign["photo_url"])

    def test_anything_else_is_the_card(self):
        for item in (person(photo_url="https://site.test/me.jpg", photoSource="campaign-site"),
                     person(photo_url="https://upload.wikimedia.org/x.jpg", photoSource="wikipedia"),
                     person(photo_url="https://en.wikipedia.org/wiki/Special:FilePath/Test_Member.jpg",
                            photoSource="clerk.house.gov"),
                     person(photo_url="http://clerk.house.gov/images/members/X.jpg",
                            photoSource="clerk.house.gov"),
                     person(photos=["https://clerk.house.gov/images/members/X.jpg"])):
            self.assertIsNone(share.og_photo(item), item)
        page = share.render_profile(person(), "example.org", {}, {})
        self.assertIn('<meta property="og:image" content="https://example.org/assets/social-card.png">', page)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', page)


class TestSharePages(unittest.TestCase):

    def page(self, item=None, **kwargs):
        item = item or person(**kwargs)
        return share.render_profile(item, "example.org", {item["id"]: item},
                                    {"H-TX-03-2026": race()})

    def test_its_own_address_title_description_and_view(self):
        page = self.page()
        self.assertIn('<link rel="canonical" href="https://example.org/p/X000001.html">', page)
        self.assertIn('<meta property="og:url" content="https://example.org/p/X000001.html">', page)
        self.assertIn("<title>Test Member — Know Your Candidate</title>", page)
        self.assertIn('content="Test Member (Republican), member for House • TX-3: Renominated for 2026."',
                      page)
        self.assertIn('<a id="shareView" href="../index.html#/profile/X000001">', page)
        self.assertIn('<a href="../r/H-TX-03-2026.html">TX-3 — U.S. House</a>', page)
        self.assertIn('<script src="../assets/kyc-share.js"></script>', page)

    def test_no_inline_script_nothing_dated_and_small(self):
        page = self.page()
        self.assertEqual(emit.inline_script_problems(page), [])
        self.assertNotIn('http-equiv="refresh"', page)
        self.assertIsNone(re.search(r"20\d\d-\d\d-\d\d", page))
        self.assertLess(len(page.encode("utf-8")), 4000)

    def test_a_candidate_and_a_former_member_say_so(self):
        self.assertIn("(Republican), candidate for House • TX-3",
                      self.page(person(id="FEC_1", isCandidate=True)))
        self.assertIn("former member for House • TX-3",
                      self.page(person(formerMember={"left": "2026-12-01"})))

    def test_a_territory_is_not_the_state(self):
        page = self.page(person(state="GU", officeLabel="House • GU-AL"))
        self.assertIn("Guam&#x27;s page</a>", page)
        self.assertNotIn("the state", page)

    def test_a_races_page_splits_its_people_as_the_state_page_does(self):
        moved = person(contestRaceId="H-TX-04-2026", contestLabel="House • TX-4", renumbered=True)
        running = person(id="FEC_A", name="Ann Able", isCandidate=True, party="Democrat")
        out = person(id="FEC_B", name="Bo Bee", isCandidate=True, raceStatus="eliminated")
        r = race(candidateIds=["FEC_A", "FEC_B"],
                 results={"otherNominees": ["Cy Dee"], "otherParties": {"Cy Dee": "Green"}})
        by_id = {p["id"]: p for p in (moved, running, out)}
        page = share.render_race(r, "example.org", by_id, {r["id"]: r})
        self.assertIn('Held by <a href="../p/X000001.html">Test Member</a>, who is running in TX-4 '
                      "under the state’s new district map.", page)
        self.assertIn('<li data-id="FEC_A"><a href="../p/FEC_A.html">Ann Able</a> (Democrat): '
                      '<span class="share-standing">On the November ballot</span></li>', page)
        self.assertIn('data-race-out="H-TX-03-2026">\n    <li data-id="FEC_B">', page)
        self.assertIn("with no FEC filing over $5,000 and so no profile here: Cy Dee (Green).", page)
        self.assertIn('href="../states/tx.html#race-H-TX-03-2026"', page)
        description = re.search(r'<meta name="description" content="([^"]*)"', page).group(1)
        self.assertIn("Ann Able (Democrat): On the November ballot.", description)
        self.assertNotIn("Bo Bee", description)

    def test_a_holder_who_has_left_holds_nothing(self):
        r = race(incumbent={"name": "Gone Member", "party": "Republican", "seated": False},
                 incumbentIds=[])
        self.assertNotIn("Held by", share.describe_race(r, {}, {}))

    def test_the_pages_do_not_carry_the_builds_time(self):
        profiles = [person(), person(id="FEC_A", isCandidate=True)]
        races = [race(candidateIds=["FEC_A"])]
        before = os.environ.get("SOURCE_DATE_EPOCH")
        try:
            os.environ["SOURCE_DATE_EPOCH"] = "1000000000"
            first = share.render_all(profiles, races, "example.org")
            os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
            second = share.render_all(profiles, races, "example.org")
        finally:
            if before is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = before
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), ["p/FEC_A.html", "p/X000001.html", "r/H-TX-03-2026.html"])


class TestSharePagesAreBuiltAndVerified(unittest.TestCase):
    """Generated on every build, and checked by verify like every other
    generated page (rule 18): a hand edit, a missing page and a page for
    someone the data no longer holds are each reported."""

    def test_written_checked_and_cleaned_up(self):
        people = [person(), person(id="FEC_A", isCandidate=True, name="Ann Able")]
        races = [race(candidateIds=["FEC_A"])]
        summary = {"states": {}}
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.SITE_DIR))
            with open(os.path.join(tmp, emit.CNAME_FILE), "w", encoding="utf-8") as f:
                f.write("example.org\n")
            emit.write_state_pages(people, tmp, summary=summary, stamp_from=ROOT, races=races)
            site = os.path.join(tmp, emit.SITE_DIR)
            self.assertEqual(sorted(os.listdir(os.path.join(site, "p"))),
                             ["FEC_A.html", "X000001.html"])
            self.assertEqual(os.listdir(os.path.join(site, "r")), ["H-TX-03-2026.html"])
            with open(os.path.join(site, "sitemap.xml"), encoding="utf-8") as f:
                xml = f.read()
            self.assertIn("<loc>https://example.org/p/FEC_A.html</loc>", xml)
            self.assertIn("<loc>https://example.org/r/H-TX-03-2026.html</loc>", xml)
            with open(os.path.join(site, "states", "tx.html"), encoding="utf-8") as f:
                state = f.read()
            self.assertIn('<h1 class="state-title">Texas</h1>', state)
            self.assertIn('<a href="../p/FEC_A.html">Ann Able</a>', state)
            self.assertEqual(emit.check_state_pages(people, tmp, summary, ROOT, races), [])

            with open(os.path.join(site, "p", "FEC_A.html"), "a", encoding="utf-8") as f:
                f.write("<!-- by hand -->")
            with open(os.path.join(site, "p", "GONE.html"), "w", encoding="utf-8") as f:
                f.write("<!DOCTYPE html>")
            found = {os.path.basename(rel): why
                     for rel, why in emit.check_state_pages(people, tmp, summary, ROOT, races)}
            self.assertEqual(found, {"FEC_A.html": "stale", "GONE.html": "orphaned"})
            # The data changed: the state page and the sitemap with it.
            fewer = people[:1]
            found = {os.path.basename(rel)
                     for rel, _ in emit.check_state_pages(fewer, tmp, summary, ROOT, [race()])}
            self.assertTrue({"tx.html", "sitemap.xml", "FEC_A.html", "GONE.html"} <= found, found)

            emit.write_state_pages(people, tmp, summary=summary, stamp_from=ROOT, races=races)
            self.assertFalse(os.path.exists(os.path.join(site, "p", "GONE.html")))
            self.assertEqual(emit.check_state_pages(people, tmp, summary, ROOT, races), [])

    def test_the_committed_share_pages_are_this_builds(self):
        # verify's own comparison, over the real site, is in the CI gate;
        # here, only that the folders exist and hold pages.
        site = os.path.join(ROOT, emit.SITE_DIR)
        self.assertGreater(len(os.listdir(os.path.join(site, "p"))), 500)
        self.assertGreater(len(os.listdir(os.path.join(site, "r"))), 400)


class TestPlainStatePages(unittest.TestCase):
    """TECH-10: a state page is written with its facts, the script draws
    over them, and every page says what needs JavaScript."""

    def test_the_lists_come_from_the_build(self):
        profiles = [person(chamber="Senate", id="S1", name="Sen One", officeLabel="Senate • TX",
                           raceId=None, raceStatus=None),
                    person(id="H2", name="Rep Two", districtNum=2, officeLabel="House • TX-2"),
                    person(), person(id="FEC_A", isCandidate=True, name="Ann Able"),
                    person(id="OLD", formerMember={"left": "2026-01-01"}, name="Gone")]
        races = [race(candidateIds=["FEC_A"]), race(id="H-CA-01-2026", state="CA")]
        html = pages.render_state("TX", "example.org",
                                  {"states": {"TX": {"vacancies": [{"district": 9}]}}},
                                  profiles, races)
        senators = re.search(r'id="senators">(.*?)</section>', html, re.S).group(1)
        house = re.search(r'id="delegation">(.*?)</section>', html, re.S).group(1)
        self.assertEqual(re.findall(r'data-id="([^"]+)"', senators), ["S1"])
        # By district, a former member left out (rule 67), a vacancy said.
        self.assertEqual(re.findall(r'data-id="([^"]+)"', house), ["H2", "X000001"])
        self.assertIn("District 9: vacant", house)
        self.assertEqual(re.findall(r'<h3 class="race-title" id="race-([^"]+)">', html), ["H-TX-03-2026"])
        self.assertIn('<a href="../r/H-TX-03-2026.html">', html)
        self.assertNotIn("Loading&hellip;", html)

    def test_without_the_build_data_the_heading_still_names_the_state(self):
        html = pages.render_state("TX", "example.org")
        self.assertIn('<h1 class="state-title">Texas</h1>', html)
        self.assertIn("Loading&hellip;", html)

    def test_the_directory_of_states_lists_each_page(self):
        html = pages.render_states_index("example.org", ["TX", "AK"])
        self.assertIn('<li><a href="ak.html">Alaska</a></li>', html)
        self.assertLess(html.index("ak.html"), html.index("tx.html"))

    def test_every_generated_page_says_what_needs_javascript(self):
        for html in (pages.render_state("TX", "example.org"), pages.render_404("example.org"),
                     pages.render_court_page("ca9", "example.org")):
            self.assertIn('<noscript><p class="noscript-note" role="note">The maps, filters and '
                          "search on this site need JavaScript", html)
        ballot = pages.render_ballot_page("example.org")
        self.assertEqual(ballot.count("<noscript>"), 1)
        self.assertIn("looks your ZIP code up in your browser", ballot)

    def test_the_hand_maintained_pages_say_it_too(self):
        for name in ("index.html", "map.html"):
            with open(os.path.join(ROOT, emit.SITE_DIR, name), encoding="utf-8") as f:
                self.assertIn('<noscript><p class="noscript-note"', f.read(), name)


if __name__ == "__main__":
    unittest.main()
