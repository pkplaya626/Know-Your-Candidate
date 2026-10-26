"""Each state's official voting pages, from NASS's "Can I Vote".

Nothing on the site told a reader how, when or where to vote (audit
2026-10-13, CG-5). The links are the states' own; NASS is the directory, and
a page that does not list every state and D.C. once is refused. NASS's
directory is not always current, so every link is opened, a dead one is
replaced through an evidenced override or not shown, and a bot wall
concludes nothing (rule 8).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import overrides, validate, voting  # noqa: E402
from kyc.normalize import US_STATES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
NAMES = {code: name.title() for name, code in US_STATES.items() if code in voting.JURISDICTIONS}


def page(rows, attrs=""):
    return "<select>" + "".join(
        f'<option{attrs} value="{url}">{name}</option>' for name, url in rows) + "</select>"


def every_state(**change):
    rows = {code: (NAMES[code], f"https://vote.{code.lower()}.gov/check") for code in NAMES}
    rows.update(change)
    return [row for row in rows.values() if row]


def cache_of(**states):
    base = {code: {kind: f"https://vote.{code.lower()}.gov/{kind}" for kind in voting.PAGES}
            for code in voting.JURISDICTIONS}
    for code, links in states.items():
        base[code].update(links)
    return {"source": voting.SOURCE, "states": base, "fetched": "2026-10-14T00:00:00+00:00"}


class TestParse(unittest.TestCase):
    def test_every_state_and_dc_once(self):
        found = voting.parse(page(every_state()))
        self.assertEqual(set(found), voting.JURISDICTIONS)
        self.assertEqual(found["DC"], "https://vote.dc.gov/check")

    def test_a_missing_state_refuses_the_page(self):
        with self.assertRaisesRegex(voting.VotingError, "no link for WY"):
            voting.parse(page(every_state(WY=None)))

    def test_a_state_twice_is_refused(self):
        rows = every_state() + [("Texas", "https://elsewhere.texas.gov/")]
        with self.assertRaisesRegex(voting.VotingError, "TX is listed twice"):
            voting.parse(page(rows))

    def test_an_option_that_is_not_a_web_address_is_refused(self):
        with self.assertRaisesRegex(voting.VotingError, "not a web address"):
            voting.parse(page(every_state(OH=("Ohio", "javascript:alert(1)"))))
        with self.assertRaisesRegex(voting.VotingError, "not a web address"):
            voting.parse(page(every_state(OH=("Ohio", "https://vote.oh.gov/ x"))))

    def test_an_option_that_is_not_a_state_is_refused(self):
        rows = every_state() + [("Narnia", "https://www.nass.org/")]
        with self.assertRaisesRegex(voting.VotingError, "not a state"):
            voting.parse(page(rows))

    def test_the_value_is_read_never_a_data_value(self):
        text = page(every_state()).replace(
            '<option value="https://vote.tx.gov/check">',
            '<option value="https://vote.tx.gov/check" data-value="https://evil.example/">')
        self.assertEqual(voting.parse(text)["TX"], "https://vote.tx.gov/check")

    def test_a_link_off_the_states_own_domain_is_refused(self):
        with self.assertRaisesRegex(voting.VotingError, "own election domain"):
            voting.parse(page(every_state(OH=("Ohio", "https://ohio-votes.example.com/"))))
        # An allowed non-.gov domain is allowed for its own state only.
        self.assertTrue(voting.official("https://my.arizona.vote/x", "AZ"))
        self.assertFalse(voting.official("https://my.arizona.vote/x", "NM"))

    def test_a_stale_aspnet_session_is_stripped(self):
        # Hawaii's link froze "(S(vb2rc...))" into its path and ended on an error page.
        rows = every_state(HI=("Hawaii", "https://olvr.hawaii.gov/%28S%28vb2rcnebimyjd%29%29/Default.aspx"))
        self.assertEqual(voting.parse(page(rows))["HI"], "https://olvr.hawaii.gov/Default.aspx")


class TestLiveness(unittest.TestCase):
    def check(self, answers):
        seen = []

        def status(url):
            seen.append(url)
            return answers[url].pop(0)
        return voting.check_links(list(answers), status=status, pause=0, sleep=lambda s: None)

    def test_dead_only_on_a_404_from_the_links_own_host_twice(self):
        u = "https://vote.ia.gov/absentee"
        self.assertEqual(self.check({u: [(404, u), (404, u)]})[u], voting.DEAD)
        self.assertEqual(self.check({u: [(404, u), (200, u)]})[u], voting.UNKNOWN)

    def test_a_bot_wall_concludes_nothing(self):
        # Minnesota redirects a script to a Radware check that answers 404.
        u = "https://www.sos.mn.gov/register/"
        wall = "https://validate.perfdrive.com/?ssc=x"
        self.assertEqual(self.check({u: [(404, wall), (404, wall)]})[u], voting.UNKNOWN)
        for code in (403, 429, 503, None):
            self.assertEqual(self.check({u: [(code, u)]})[u], voting.UNKNOWN)

    def test_a_name_that_does_not_resolve_is_dead(self):
        u = "https://lapsed.example.gov/"
        self.assertEqual(self.check({u: [("nxdomain", u), ("nxdomain", u)]})[u], voting.DEAD)


class TestOverrides(unittest.TestCase):
    def test_a_dead_nass_link_is_replaced_and_kept_replaced(self):
        nass, url, _label, _why = overrides.VOTING_LINKS[("IA", "absentee")]
        shown = voting.effective(cache_of(IA={"absentee": nass}))["IA"]["absentee"]
        self.assertEqual(shown["url"], url)

    def test_north_dakota_is_not_told_to_register(self):
        nd = {"register": overrides.VOTING_LINKS[("ND", "register")][0],
              "status": overrides.VOTING_LINKS[("ND", "status")][0]}
        page_links = voting.for_page(cache_of(ND=nd))
        self.assertNotIn("status", page_links["ND"])
        self.assertEqual(page_links["_labels"]["ND"]["register"], "Voting in North Dakota")

    def test_an_override_stops_once_nass_changes_its_entry(self):
        cache = cache_of(IA={"absentee": "https://sos.iowa.gov/new-absentee"})
        self.assertEqual(voting.effective(cache)["IA"]["absentee"]["url"],
                         "https://sos.iowa.gov/new-absentee")
        self.assertTrue(any(s.startswith("IA absentee") for s in voting.stale_overrides(cache)))

    def test_a_dead_link_is_not_sent_to_a_reader(self):
        cache = cache_of()
        cache["links"] = {"https://vote.oh.gov/polling": voting.DEAD}
        self.assertNotIn("polling", voting.for_page(cache)["OH"])
        self.assertEqual(voting.dead_links(cache), ["OH polling: https://vote.oh.gov/polling"])

    def test_oregons_walled_lookup_is_reached_through_its_my_vote_page(self):
        # On 2026-10-18 GitHub's runner got 404 twice from ORESTAR's bot
        # wall, the lookup was called dead, and the daily refresh stopped.
        nass, url, _label, _why = overrides.VOTING_LINKS[("OR", "status")]
        cache = cache_of(OR={"status": nass})
        cache["links"] = {nass: voting.DEAD, url: voting.LIVE}
        self.assertEqual(voting.effective(cache)["OR"]["status"],
                         {"url": "https://sos.oregon.gov/elections/pages/myvote.aspx",
                          "from": voting.OFFICE})
        self.assertEqual(voting.dead_links(cache), [])
        self.assertEqual(voting.for_page(cache)["OR"]["status"], url)


class TestOpenedByHand(unittest.TestCase):
    """Links the weekly check could not open, opened by hand in a person's
    browser on 2026-10-26, or found behind a portal's check for people
    (overrides.VOTING_LINKS_BY_HAND): counted as such, and only while the
    entry fits the link shown."""

    ENTRIES = {
        ("AZ", "polling"): ("https://vote.az.gov/polling", "2026-10-26", "opened", "",
                            "Search by address"),
        ("NH", "polling"): ("https://vote.nh.gov/polling", "2026-10-26", "human-check",
                            "https://vote.nh.gov/captcha/challenge", "Verification"),
    }

    def run_with(self, cache, today=None):
        import datetime
        from unittest import mock
        with mock.patch.dict(overrides.VOTING_LINKS_BY_HAND, self.ENTRIES, clear=True):
            return (voting.for_page(cache),
                    voting.by_hand_problems(cache, today or datetime.date(2026, 10, 27)),
                    validate.check_voting_links(cache))

    def unknown(self, **status):
        cache = cache_of()
        cache["links"] = {"https://vote.az.gov/polling": voting.UNKNOWN,
                          "https://vote.nh.gov/polling": voting.UNKNOWN, **status}
        cache["linksChecked"] = "2026-10-25"
        return cache

    def test_each_is_given_to_the_page_with_its_day(self):
        page, problems, issues = self.run_with(self.unknown())
        self.assertEqual(page["_byHand"], {"AZ": {"polling": ["2026-10-26", "opened"]},
                                           "NH": {"polling": ["2026-10-26", "human-check"]}})
        self.assertEqual(page["_byHandDays"], voting.BY_HAND_DAYS)
        # Still unreached by the weekly check: the page decides, on the
        # reader's day, whether the reading by hand still counts.
        self.assertIn("polling", page["_unreached"]["AZ"])
        self.assertEqual(problems, [])
        unchecked = [i for i in issues if i.code == "voting-links-unchecked"]
        self.assertFalse(any(d.startswith(("AZ polling", "NH polling"))
                             for i in unchecked for d in i.detail))

    def test_a_link_the_weekly_check_now_opens_needs_no_entry(self):
        page, problems, _ = self.run_with(self.unknown(**{
            "https://vote.az.gov/polling": voting.LIVE}))
        self.assertNotIn("AZ", page["_byHand"])
        self.assertEqual(problems, ["AZ polling: the weekly check found "
                                    "https://vote.az.gov/polling live; the entry may go"])

    def test_an_entry_for_another_address_counts_for_nothing(self):
        cache = self.unknown()
        cache["states"]["AZ"]["polling"] = "https://vote.az.gov/new-polling"
        page, problems, issues = self.run_with(cache)
        self.assertNotIn("AZ", page["_byHand"])
        self.assertTrue(any(p.startswith("AZ polling: the page now shows") for p in problems))
        self.assertIn("voting-by-hand-stale", [i.code for i in issues])

    def test_a_mistyped_word_counts_for_nothing(self):
        # Only "opened" or "human-check" reaches the page: a typo in a
        # curated value must never make the page say a link was opened.
        import datetime
        from unittest import mock
        typo = {("AZ", "polling"): ("https://vote.az.gov/polling", "2026-10-26", "openned", "",
                                    "Search by address")}
        with mock.patch.dict(overrides.VOTING_LINKS_BY_HAND, typo, clear=True):
            page = voting.for_page(self.unknown())
            problems = voting.by_hand_problems(self.unknown(), datetime.date(2026, 10, 27))
        self.assertEqual(page["_byHand"], {})
        self.assertIn("polling", page["_unreached"]["AZ"])
        self.assertTrue(any("is neither" in p for p in problems))

    def test_an_old_reading_is_reported_and_listed_unchecked_again(self):
        import datetime
        late = datetime.date(2026, 10, 26) + datetime.timedelta(days=voting.BY_HAND_DAYS + 1)
        _, problems, _ = self.run_with(self.unknown(), late)
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("the page no longer counts it" in p for p in problems))

    def test_the_committed_entries_fit_the_links_shown(self):
        # research/by-hand-2026-10-26/NOTES.md: thirty-three opened in two
        # rounds (New York's and Georgia's lookups each stand for two kinds),
        # and three whose portal asked first that the visitor show they are a
        # person. Alaska's registration page opened with no check: only its
        # early-voting page asked.
        cache = voting.load_cache(ROOT)
        what = [entry[2] for entry in overrides.VOTING_LINKS_BY_HAND.values()]
        self.assertEqual((what.count(voting.OPENED_BY_HAND), what.count(voting.HUMAN_CHECK)),
                         (33, 3))
        self.assertEqual(sorted(key for key, entry in overrides.VOTING_LINKS_BY_HAND.items()
                                if entry[2] == voting.HUMAN_CHECK),
                         [("AK", "absentee"), ("NH", "polling"), ("NH", "status")])
        # A refresh that opens a link itself, or a later day, makes an entry
        # one validate reports (voting-by-hand-stale), never a failed test:
        # only a malformed entry fails here.
        self.assertEqual([p for p in voting.by_hand_problems(cache)
                          if "is neither" in p or "is not YYYY-MM-DD" in p], [])
        page = voting.for_page(cache)
        for code, kinds in page["_byHand"].items():
            for kind, (day, seen) in kinds.items():
                entry = overrides.VOTING_LINKS_BY_HAND[(code, kind)]
                self.assertEqual((day, seen), (entry[1], entry[2]))
                self.assertEqual(page[code][kind], entry[0])


class TestValidate(unittest.TestCase):
    def codes(self, cache):
        return sorted(i.code for i in validate.check_voting_links(cache))

    def test_a_gap_is_an_error(self):
        cache = cache_of()
        del cache["states"]["NV"]["polling"]
        self.assertIn("voting-links-incomplete", self.codes(cache))

    def test_a_foreign_host_is_an_error(self):
        self.assertIn("voting-links-not-official",
                      self.codes(cache_of(OH={"polling": "https://ohio-votes.example.com/"})))

    def test_no_cache_is_a_warning(self):
        self.assertEqual(self.codes({}), ["voting-links-missing"])

    def test_the_committed_cache_is_complete_official_and_alive(self):
        cache = voting.load_cache(ROOT)
        self.assertIsNotNone(cache)
        errors = [i for i in validate.check_voting_links(cache) if i.level == "error"]
        self.assertEqual(errors, [])
        self.assertEqual(voting.dead_links(cache), [])


class TestMorePages(unittest.TestCase):
    """What NASS does not list (audit 2026-10-17): where the state publishes
    its count (RACES-20), a sample ballot where the office links one
    (RACES-16), vote.gov's registration deadlines (STATEGOV-11), the
    territories' own offices (RACES-07) and the December rounds (PERSONA-06)."""

    def test_every_state_and_dc_has_a_results_page_and_vote_gov_deadlines(self):
        self.assertEqual(set(voting.RESULTS), voting.JURISDICTIONS)
        self.assertTrue(voting.JURISDICTIONS <= set(voting.DEADLINES))

    def test_every_curated_link_is_on_its_states_own_domain(self):
        for table in (voting.RESULTS, voting.SAMPLE_BALLOTS, voting.DEADLINES):
            for code, url in table.items():
                self.assertTrue(voting.official(url, code), f"{code}: {url}")
        for code, links in voting.TERRITORY_LINKS.items():
            for kind, (url, _label) in links.items():
                self.assertTrue(voting.official(url, code), f"{code} {kind}: {url}")

    def test_deadlines_are_vote_govs_pages_only(self):
        self.assertTrue(all(url.startswith(voting.VOTE_GOV + "/") for url in voting.DEADLINES.values()))

    def test_the_page_gets_them(self):
        shown = voting.for_page(cache_of())
        self.assertEqual(shown["TX"]["results"], voting.RESULTS["TX"])
        self.assertEqual(shown["TX"]["deadlines"], "https://vote.gov/register/texas")
        self.assertNotIn("sample", shown["TX"])
        self.assertEqual(shown["MI"]["sample"], voting.SAMPLE_BALLOTS["MI"])

    def test_the_territories_get_their_offices_pages(self):
        shown = voting.for_page(cache_of())
        for code in ("GU", "VI", "MP", "AS", "PR"):
            self.assertIn(code, shown)
            self.assertEqual(shown[code]["deadlines"], voting.DEADLINES[code])
            self.assertIn(code, shown["_territories"])
        self.assertEqual(shown["_labels"]["MP"]["sample"], "Specimen ballot (PDF)")

    def test_a_curated_link_found_dead_is_not_shown(self):
        cache = cache_of()
        cache["links"] = {voting.RESULTS["OH"]: voting.DEAD}
        self.assertNotIn("results", voting.for_page(cache)["OH"])

    def test_a_missing_results_page_fails(self):
        original = dict(voting.RESULTS)
        voting.RESULTS.pop("OH")
        try:
            codes = sorted(i.code for i in validate.check_voting_links(cache_of()))
        finally:
            voting.RESULTS.clear()
            voting.RESULTS.update(original)
        self.assertIn("voting-links-incomplete", codes)

    def test_unopened_links_are_reported(self):
        codes = sorted(i.code for i in validate.check_voting_links(cache_of()))
        self.assertIn("voting-links-unchecked", codes)

    def test_dc_mail_ballots_and_wyoming_has_no_lookup(self):
        dc = overrides.VOTING_LINKS[("DC", "absentee")]
        wy = overrides.VOTING_LINKS[("WY", "status")]
        shown = voting.for_page(cache_of(DC={"absentee": dc[0]}, WY={"status": wy[0]}))
        self.assertIn("mail-ballot", shown["DC"]["absentee"])
        self.assertNotIn("status", shown["WY"])

    def test_each_link_says_where_it_came_from(self):
        # "The first four from NASS" credited NASS with eleven states'
        # sample-ballot pages, Wyoming's results page and D.C.'s override
        # (PR #94 review): the page now credits NASS only with what NASS lists.
        dc = overrides.VOTING_LINKS[("DC", "absentee")]
        wy = overrides.VOTING_LINKS[("WY", "status")]
        shown = voting.for_page(cache_of(DC={"absentee": dc[0]}, WY={"status": wy[0]}))
        self.assertEqual(shown["_nass"]["TX"], sorted(voting.PAGES))
        self.assertEqual(shown["_nass"]["MN"], sorted(voting.PAGES))
        self.assertNotIn("sample", shown["_nass"]["MN"])
        self.assertNotIn("absentee", shown["_nass"]["DC"])
        self.assertEqual(shown["_nass"]["WY"], ["absentee", "polling", "register"])
        self.assertEqual(shown["_nass"]["GU"], [])
        effective = voting.effective(cache_of())
        self.assertEqual(effective["TX"]["deadlines"]["from"], voting.VOTE_GOV_FROM)
        self.assertEqual(effective["TX"]["results"]["from"], voting.OFFICE)
        self.assertEqual(effective["VI"]["polling"]["from"], voting.OFFICE)

    def test_a_link_not_found_live_is_never_called_opened(self):
        # Guam's only link could not be reached on 2026-10-17, and the page
        # said "each link opened" over it.
        cache = cache_of()
        shown_urls = {link["url"] for links in voting.effective(cache).values()
                      for link in links.values()}
        cache["links"] = {url: voting.LIVE for url in shown_urls}
        cache["links"][voting.TERRITORY_LINKS["GU"]["info"][0]] = voting.UNKNOWN
        cache["links"][voting.DEADLINES["TX"]] = voting.UNKNOWN
        shown = voting.for_page(cache)
        self.assertEqual(shown["_unreached"], {"GU": ["info"], "TX": ["deadlines"]})
        unchecked = [i for i in validate.check_voting_links(cache) if i.code == "voting-links-unchecked"]
        self.assertEqual(len(unchecked), 1)
        self.assertEqual(len(unchecked[0].detail), 2)
        self.assertTrue(all("(unknown)" in line for line in unchecked[0].detail))


if __name__ == "__main__":
    unittest.main()
