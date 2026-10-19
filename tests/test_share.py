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


class TestStatusTable(unittest.TestCase):
    """The words a page without scripts shows, for every case the status
    table has, are in tests/fixtures/share_status_words.json, which the
    render suite asks the page code (KYC.raceStatus) about, row by row: a
    word changed on one side fails the day it changes, not the night a
    November result is first read (PR #121 review)."""

    def test_the_fixture_is_this_codes(self):
        with open(share.STATUS_TABLE, encoding="utf-8", newline="") as handle:
            on_disk = handle.read()
        self.assertEqual(on_disk, share.status_table_text(),
                         'regenerate: python -c "from kyc import share; share.write_status_table()" '
                         "after making the same change in assets/kyc.js")

    def test_it_holds_every_status_and_the_november_words(self):
        table = share.status_table()
        labels = {row[-2] for row in table["statuses"]}
        for words in ("Elected in November", "Re-elected in November", "Lost re-election in November",
                      "In the general election runoff", "On the November ballot: awaiting result",
                      "Advanced to the November ballot", "Not on the November 3 open-primary ballot"):
            self.assertIn(words, labels)
        self.assertEqual({row[0] for row in table["statuses"]}, set(share._RACE_STATUS))


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
        # The seat in words, and who says where they stand (PR #121 review):
        # "member for House • TX-3" read as a glitch in an unfurl.
        self.assertIn('content="Test Member (Republican), member of the U.S. House for TX-3: '
                      'Renominated for 2026, per Wikipedia&#x27;s election results page."', page)
        self.assertIn('<p class="share-source faint">Source: Wikipedia&#x27;s election results '
                      'page.</p>', page)
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
        self.assertIn("(Republican), candidate for the U.S. House in TX-3",
                      self.page(person(id="FEC_1", isCandidate=True)))
        self.assertIn("former member of the U.S. House for TX-3",
                      self.page(person(formerMember={"left": "2026-12-01"})))
        self.assertIn("member of the U.S. Senate for Texas",
                      self.page(person(chamber="Senate", officeLabel="Senate • TX")))
        self.assertIn("member of the U.S. House for Alaska (at large)",
                      self.page(person(state="AK", officeLabel="House • AK-AL")))

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

    def test_where_a_member_leaving_is_going_and_when_a_seat_not_up_is_next(self):
        other = {"text": "Republican nominee for Governor of Texas",
                 "source": "https://en.wikipedia.org/wiki/2026_Texas_gubernatorial_election",
                 "checked": "2026-10-17"}
        leaving = person(raceStatus="unlisted", otherOffice=other)
        page = self.page(leaving)
        self.assertIn('<p class="share-other">Republican nominee for Governor of Texas.', page)
        self.assertIn("Not running for re-election in 2026, per Wikipedia&#x27;s election results "
                      "page; Republican nominee for Governor of Texas.", page)
        # Not a race he is in: the seat's.
        self.assertIn("The seat’s 2026 race: <a", page)
        after = share.render_profile(leaving, "example.org", {"X000001": leaving},
                                     {"H-TX-03-2026": race()}, post=True)
        self.assertIn("Was the Republican nominee for Governor of Texas", after)
        senator = person(chamber="Senate", officeLabel="Senate • TX", raceId=None, raceStatus=None,
                         seatUp2026=False, electionYear=2030)
        page = self.page(senator)
        self.assertIn('<p class="share-next">Seat up in 2030</p>', page)
        self.assertIn("member of the U.S. Senate for Texas: seat up in 2030.", page)
        self.assertNotIn("share-next", self.page(person(seatUp2026=True, electionYear=2026)))

    def test_each_status_credits_its_source(self):
        by_id = {}
        self.assertEqual(share.status_source(person(), by_id), "Wikipedia's election results page")
        self.assertEqual(share.status_source(person(raceStatusSource="certified",
                                                    raceStatusSourceName="the Test Division"), by_id),
                         "the Test Division")
        self.assertEqual(share.status_source(person(raceStatus="qualified", isCandidate=True,
                                                    raceStatusSource="qualified"), by_id),
                         "the Secretary of State's Candidate Inquiry")
        self.assertEqual(share.status_source(person(isCandidate=True, raceStatus=None,
                                                    unprinted={"kind": "write-in", "source": "the list"}),
                                             by_id), "the list")
        self.assertIsNone(share.status_source(person(isCandidate=True, raceStatus=None,
                                                     ballotUnknown=True), by_id))
        # A member running elsewhere: their filing's source.
        member = person(raceStatus="unlisted", contestRaceId="S-TX-2026",
                        contestLabel="Senate • TX", alsoRunningId="FEC_S1")
        filing = person(id="FEC_S1", isCandidate=True, raceId="S-TX-2026", raceStatus="nominee",
                        raceStatusSource="certified", raceStatusSourceName="the Texas list")
        self.assertEqual(share.status_source(member, {"FEC_S1": filing}), "the Texas list")
        self.assertIn("On the November ballot for the U.S. Senate in Texas, per the Texas list.",
                      share.describe(member, {"FEC_S1": filing, member["id"]: member}, {})[1])

    def test_a_race_marks_its_holder_and_says_who_says_where_each_stands(self):
        challenger = person(id="FEC_A", name="Ann Able", isCandidate=True, party="Democrat",
                            raceStatusSource="certified", raceStatusSourceName="the Texas list")
        holder = person(name="Test M. Member")
        r = race(candidateIds=["FEC_A"], special=True,
                 incumbent={"name": "Test Middle Member", "party": "Republican", "seated": True})
        by_id = {p["id"]: p for p in (holder, challenger)}
        page = share.render_race(r, "example.org", by_id, {r["id"]: r})
        self.assertIn('<a href="../p/X000001.html">Test M. Member</a> (Republican), '
                      '<span class="share-holder">holds the seat</span>: ', page)
        self.assertNotIn('Ann Able</a> (Democrat), <span class="share-holder">', page)
        self.assertIn("Where each stands: per Wikipedia&#x27;s election results page and the "
                      "Texas list.", page)
        self.assertIn("<h1>TX-3 — U.S. House: the 2026 special election</h1>", page)
        description = share.describe_race(r, by_id, {r["id"]: r})
        # The holder under the name the list gives them, not the record's.
        self.assertIn("Held by Test M. Member (Republican).", description)
        # Who says so comes before the list, where an unfurler's cut cannot
        # reach it (PR #123 review).
        self.assertIn("Where each stands, per Wikipedia's election results page and the Texas "
                      "list: ", description)
        self.assertTrue(description.endswith("."), description)

    def test_a_long_race_description_stops_and_says_how_many_more(self):
        ids = [f"FEC_{i:02d}" for i in range(12)]
        people = [person(id=i, name=f"Candidate Number {i} Longname", isCandidate=True,
                         party="Republican", raceStatusSource="certified",
                         raceStatusSourceName="the Texas list") for i in ids]
        r = race(candidateIds=ids)
        by_id = {p["id"]: p for p in people}
        description = share.describe_race(r, by_id, {r["id"]: r})
        self.assertLessEqual(len(description), share.DESCRIPTION_MAX, description)
        self.assertLess(description.index("Where each stands, per"), 200, description)
        shown = description.count("Candidate Number")
        self.assertGreaterEqual(shown, 1)
        self.assertTrue(description.endswith(f"; and {12 - shown} more in this race."), description)
        # A race that fits is listed whole.
        short = race(candidateIds=ids[:2])
        whole = share.describe_race(short, by_id, {short["id"]: short})
        self.assertEqual(whole.count("Candidate Number"), 2)
        self.assertNotIn("more in this race", whole)

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

    def test_a_page_shared_under_an_id_the_profile_no_longer_has_stays(self):
        # Filings fold (rule 25) and filers are seated: the id a link was
        # shared under stops being a profile's. Its page is kept, as the
        # profile's, pointing at its own page - never a 404 - and no page is
        # made for an id nobody shared.
        people = [person(), person(id="FEC_A", isCandidate=True, name="Ann Able",
                                   otherFecIds=["H6TX03999"], fecCandidateId="H6TX03111")]
        races = [race(candidateIds=["FEC_A"])]
        summary = {"states": {}}
        self.assertEqual(sorted(share.aliases(people)), ["FEC_H6TX03111", "FEC_H6TX03999"])
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.SITE_DIR, "p"))
            with open(os.path.join(tmp, emit.CNAME_FILE), "w", encoding="utf-8") as f:
                f.write("example.org\n")
            old = os.path.join(tmp, emit.SITE_DIR, "p", "FEC_H6TX03999.html")
            with open(old, "w", encoding="utf-8") as f:
                f.write("<!DOCTYPE html><title>Ann Able, before the fold</title>")
            emit.write_state_pages(people, tmp, summary=summary, stamp_from=ROOT, races=races)
            pages_dir = os.path.join(tmp, emit.SITE_DIR, "p")
            self.assertEqual(sorted(os.listdir(pages_dir)),
                             ["FEC_A.html", "FEC_H6TX03999.html", "X000001.html"])
            with open(old, encoding="utf-8") as f:
                kept = f.read()
            self.assertIn('<link rel="canonical" href="https://example.org/p/FEC_A.html">', kept)
            self.assertIn('<a id="shareView" href="../index.html#/profile/FEC_A">', kept)
            self.assertEqual(emit.check_state_pages(people, tmp, summary, ROOT, races), [])
            with open(os.path.join(tmp, emit.SITE_DIR, "sitemap.xml"), encoding="utf-8") as f:
                self.assertNotIn("FEC_H6TX03999", f.read())
            # A hand edit to it is seen like any other.
            with open(old, "a", encoding="utf-8") as f:
                f.write("<!-- by hand -->")
            self.assertEqual(emit.check_state_pages(people, tmp, summary, ROOT, races),
                             [(os.path.join(emit.SITE_DIR, "p", "FEC_H6TX03999.html"), "stale")])

    def test_the_share_folders_are_committed(self):
        # Whether the committed pages are this build's is verify's question,
        # asked of the real site in the CI gate (emit.check_state_pages);
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

    def test_the_statewide_questions_are_listed_too(self):
        # Rule 95's questions, from the record data/measures.js is written
        # from, in KYC.ballot's words: a page without scripts listed the races
        # and left the ballot's questions out (integration of #120 and #121).
        src = "https://www.sos.example.gov/q"
        listed = {"has": True, "by": "Texas Secretary of State", "read": "2026-10-19",
                  "list": {"url": src, "title": "Questions"},
                  "measures": [{"designation": "Proposition 1", "title": "Water", "text": "x",
                                "source": src + "/1"},
                               {"designation": "Proposition 2", "title": None, "text": "y",
                                "source": src + "/2"},
                               {"designation": "Question 3", "title": None, "text": "z",
                                "source": src + "/3", "local": True}]}
        profiles = [person()]
        html = pages.render_state("TX", "example.org", {"states": {}}, profiles, [race()],
                                  {"TX": listed})
        section = re.search(r'id="measures">(.*?)</section>', html, re.S).group(1)
        self.assertIn("Statewide questions on the Nov 3, 2026 ballot</h2>", section)
        self.assertIn("2 statewide questions are on the Nov 3, 2026 ballot, as the Texas "
                      "Secretary of State lists them", section)
        statewide = re.search(r'data-measures="statewide">(.*?)</ol>', section, re.S).group(1)
        self.assertEqual(re.findall(r'data-measure="(\d+)">([^(<]*) \(', statewide),
                         [("0", "Proposition 1: Water"), ("1", "Proposition 2")])
        self.assertIn('data-measures="local">', section)
        self.assertIn("One more question is on every ballot, but is not one statewide decision",
                      section)
        self.assertIn("does not say what a yes or a no vote does", section)
        self.assertLess(html.index('id="races"'), html.index('id="measures"'))
        # After Election Day, in the past tense, as the dialog's words are.
        past = pages.measures_static("TX", listed, True)
        self.assertIn("that were on the Nov 3, 2026 ballot</h2>", past)
        self.assertIn("This site does not read the results of ballot questions.", past)
        # "None" rests on what the record quotes; "not found" is never "none".
        none = pages.measures_static("GU", {"has": False, "by": "Guam Election Commission",
                                            "read": "2026-10-19", "none": {"from": "ballots"},
                                            "list": {"url": src, "title": "Sample ballot"}}, False)
        self.assertIn("Territory-wide questions on the Nov 3, 2026 ballot", none)
        self.assertIn("No territory-wide question is on the Nov 3, 2026 ballot.", none)
        self.assertIn("and it prints no territory-wide question", none)
        self.assertNotIn("county", none)
        unknown = pages.measures_static("ME", {"has": None, "by": "Maine Secretary of State",
                                               "read": "2026-10-19",
                                               "office": {"url": src, "name": "Elections"}}, False)
        self.assertIn("has not found an official list of statewide questions", unknown)
        self.assertNotIn("No statewide question", unknown)
        # Nothing recorded, or no election there that day (Puerto Rico).
        self.assertEqual(pages.measures_static("TX", None, False), "")
        no_vote = {"voting": {"_dates": {"states": {"PR": {"lines": [{"k": "none"}]}}}}}
        self.assertEqual(pages.measures_static("PR", {"has": None}, False, no_vote), "")

    def test_the_built_pages_list_the_questions_the_record_holds(self):
        from kyc import ballot_measures

        cache = ballot_measures.load(ROOT)
        if not cache:
            self.skipTest("no ballot measures cache")
        record = ballot_measures.for_page(cache)
        for code in ("CA", "TX", "ME", "NH"):
            with open(os.path.join(ROOT, emit.SITE_DIR, "states", code.lower() + ".html"),
                      encoding="utf-8") as f:
                html = f.read()
            rec = record[code]
            self.assertIn('id="measures">', html, code)
            got = re.findall(r'data-measure="(\d+)"', html)
            want = [str(i) for i, _ in enumerate(rec.get("measures") or [])]
            self.assertEqual(sorted(got, key=int), want, code)
        with open(os.path.join(ROOT, emit.SITE_DIR, "states", "pr.html"), encoding="utf-8") as f:
            self.assertNotIn('id="measures"', f.read())

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

    def test_a_page_that_lists_nothing_without_a_script_says_so(self):
        # The general line promised "what this page lists in plain text"
        # over a legislature or a county page that lists nobody without it.
        for html in (pages.render_legislature_page("NE", "example.org"),
                     pages.render_counties_page("LA", "example.org")):
            note = re.search(r"<noscript>(.*?)</noscript>", html).group(1)
            self.assertIn("this page lists none of them without it", note)
            self.assertNotIn("in plain text", note)
        self.assertIn("The map of parishes", pages.render_counties_page("LA", "example.org"))
        note = re.search(r"<noscript>(.*?)</noscript>",
                         pages.render_district_page("AK", "example.org")).group(1)
        self.assertIn('<a href="../states/ak.html">Alaska&#x27;s page</a> lists its members of '
                      "Congress and its races in plain text", note)

    def test_the_hand_maintained_pages_say_it_too(self):
        for name in ("index.html", "map.html"):
            with open(os.path.join(ROOT, emit.SITE_DIR, name), encoding="utf-8") as f:
                self.assertIn('<noscript><p class="noscript-note"', f.read(), name)


if __name__ == "__main__":
    unittest.main()
