"""The federal executive: who holds each office, read from the offices'
own sources and never guessed (kyc/federal.py, kyc/federal_offices.py).

Fixtures are trimmed copies of the real pages as read on 2026-10-16."""

import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import federal, federal_offices  # noqa: E402

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures", "federal")
ROOT = os.path.join(HERE, "..")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as handle:
        return handle.read()


class TestTheOfficeTable(unittest.TestCase):
    def test_it_is_sound(self):
        self.assertEqual(federal_offices.check(), [])

    def test_the_departments_are_in_the_order_of_succession(self):
        # 3 U.S.C. 19(d)(1): State, Treasury, Defense, Attorney General, ...,
        # Homeland Security last - from the statute, never a page's order.
        keys = [o["key"] for o in federal_offices.DEPARTMENTS]
        self.assertEqual(keys[:4], ["state", "treasury", "defense", "justice"])
        self.assertEqual(keys[-1], "homeland")

    def test_the_war_title_is_the_defense_office(self):
        # Executive Order 14347's secondary title; the statute says Defense.
        office = federal_offices.by_title()["Secretary of War"]
        self.assertEqual(office["office"], "Secretary of Defense")


class TestThePresidentAndVicePresident(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads(fixture("executive.json"))

    def test_the_current_terms_are_read(self):
        found = federal.parse_executive(self.rows, "2026-10-16")
        self.assertEqual(found["president"]["name"], "Donald J. Trump")
        self.assertEqual(found["president"]["termEnd"], "2029-01-20")
        self.assertEqual(found["vicePresident"]["ids"]["bioguide"], "V000137")

    def test_a_file_with_no_current_president_is_refused(self):
        with self.assertRaises(federal.FederalError):
            federal.parse_executive(self.rows, "2029-06-01")

    def test_the_white_house_names_the_same_two(self):
        admin = federal.parse_administration(fixture("administration.html"))
        self.assertEqual(admin["President"][0], "Donald J. Trump")
        self.assertTrue(admin["Vice President"][1].endswith("/administration/jd-vance/"))
        self.assertTrue(federal.same_person(admin["Vice President"][0], "J.D. Vance"))
        self.assertNotIn("First Lady", admin)


class TestTheCabinetPage(unittest.TestCase):
    def test_each_entry_is_a_name_a_title_and_a_portrait(self):
        entries = federal.parse_cabinet(fixture("cabinet.html"))
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0]["name"], "Scott Bessent")
        self.assertEqual(entries[0]["title"], "Secretary of the Treasury")
        self.assertTrue(entries[0]["photo"].startswith("https://www.whitehouse.gov/wp-content/"))

    def test_a_portrait_keeps_only_sizes_of_its_own_file(self):
        # The originals run to 6 MB; the White House serves smaller copies of
        # the same file, and nothing else is a size of it (rule 42).
        entries = federal.parse_cabinet(fixture("cabinet.html"))
        for entry in entries:
            self.assertTrue(entry["photoSet"], entry["name"])
            self.assertTrue(all(url.split("?")[0] == entry["photo"] for url, _w in entry["photoSet"]))
            widths = [w for _u, w in entry["photoSet"]]
            self.assertEqual(widths, sorted(widths))
            # The resized copies survive: their URLs hold commas, and a
            # srcset split on commas kept only the originals.
            self.assertTrue(any("?resize=" in url for url, _w in entry["photoSet"]), entry["name"])
        tag = ('<img src="https://www.whitehouse.gov/wp-content/uploads/a.jpg" srcset="'
               'https://www.whitehouse.gov/wp-content/uploads/a.jpg?resize=400,600 400w, '
               'https://www.whitehouse.gov/wp-content/uploads/b.jpg?resize=300,450 300w">')
        self.assertEqual(federal.photo_set(tag, "https://www.whitehouse.gov/wp-content/uploads/a.jpg"),
                         [["https://www.whitehouse.gov/wp-content/uploads/a.jpg?resize=400,600", 400]])

    def test_an_entry_the_parser_cannot_read_stops_it(self):
        page = fixture("cabinet.html").replace("<h3 class", "<h4 class", 1)
        with self.assertRaises(federal.FederalError):
            federal.parse_cabinet(page)

    def test_a_title_the_table_does_not_know_is_reported_never_dropped(self):
        held, unknown = federal.assign([{"name": "A Person", "title": "Secretary of Space"}])
        self.assertEqual(held, {})
        self.assertEqual(unknown, ["A Person: 'Secretary of Space'"])

    def test_two_people_in_one_office_stop_the_read(self):
        with self.assertRaises(federal.FederalError):
            federal.assign([{"name": "A B", "title": "Secretary of State"},
                            {"name": "C D", "title": "Secretary of State"}])


class TestTheOfficesOwnPage(unittest.TestCase):
    """Rule 56: a name is confirmed where the office names it beside its
    title, and only there."""

    office = {o["key"]: o for o in federal_offices.OFFICES}

    def holds(self, key, name, text):
        return federal.names_holder(name, text, self.office[key]["pageTitle"])

    def test_the_title_then_the_name(self):
        self.assertTrue(self.holds("interior", "Doug Burgum",
                                   "Secretary of the Interior Secretary Doug Burgum is the 55th"))
        self.assertTrue(self.holds("homeland", "Markwayne Mullin", "Secretary Markwayne Mullin"))

    def test_the_name_serving_as_the_title(self):
        self.assertTrue(self.holds("education", "Linda McMahon",
                                   "Linda E. McMahon serves as the 13th United States "
                                   "Secretary of Education"))

    def test_a_deputy_or_a_former_holder_is_not_the_head(self):
        self.assertFalse(self.holds("homeland", "Troy Edgar", "Deputy Secretary Troy Edgar"))
        self.assertFalse(self.holds("justice", "Pam Bondi", "former Attorney General Pam Bondi"))
        self.assertFalse(self.holds("state", "Marco Rubio", "Rubio, Marco"))

    def test_another_first_name_only_by_an_evidenced_form(self):
        text = "Douglas A. Collins Secretary of Veterans Affairs"
        self.assertFalse(self.holds("veterans", "Doug Collins", text))
        reader = {"https://department.va.gov/about/": text + " Office of the Secretary" * 30}
        found = federal.confirm_on_page(self.office["veterans"], "Doug Collins",
                                        read=lambda url: reader[url], pause=0)
        self.assertEqual(found["status"], "confirmed")

    def test_a_refused_page_concludes_nothing(self):
        def refuse(url):
            raise federal.FederalError(f"could not fetch {url}: HTTP Error 403: Forbidden")
        found = federal.confirm_on_page(self.office["defense"], "Pete Hegseth", read=refuse, pause=0)
        self.assertEqual(found, {"status": "unreadable"})
        self.assertEqual(federal.confirm_on_page(self.office["omb"], "Russ Vought"),
                         {"status": "none"})

    def test_an_acting_head_is_said_to_be_acting(self):
        self.assertTrue(federal.acting("Jane Roe", "Acting Secretary of Labor Jane Roe",
                                       self.office["labor"]["pageTitle"]))


class TestTheSenatesConfirmation(unittest.TestCase):
    def setUp(self):
        self.votes = federal.parse_vote_menu(fixture("vote_menu_119_1.xml"))
        self.office = {o["key"]: o for o in federal_offices.OFFICES}

    def test_dates_are_read_whole(self):
        self.assertTrue(all(len(v["date"]) == 10 and v["date"].startswith("2025-")
                            for v in self.votes))

    def test_the_office_and_the_surname_find_the_vote(self):
        found = federal.confirmation(self.office["state"], "Marco Rubio", self.votes)
        self.assertEqual((found["vote"], found["date"], found["yeas"], found["nays"]),
                         ("119-1-8", "2025-01-20", 99, 0))
        # The Senate names him Peter; the surname and the office agree.
        self.assertEqual(federal.confirmation(self.office["defense"], "Pete Hegseth",
                                              self.votes)["vote"], "119-1-15")
        self.assertIsNotNone(federal.confirmation(self.office["ustr"], "Jamieson Greer",
                                                  self.votes))

    def test_a_deputy_is_not_the_head_and_a_name_alone_finds_nothing(self):
        # Christopher Landau was confirmed Deputy Secretary of State.
        self.assertIsNone(federal.confirmation(self.office["state"], "Christopher Landau",
                                               self.votes))
        self.assertIsNone(federal.confirmation(self.office["treasury"], "Marco Rubio",
                                               self.votes))


class TestWhenTheSenateCannotBeRead(unittest.TestCase):
    """A vote menu that cannot be read concludes nothing (rule 8): the last
    run's finding stands for the same person, and anyone else is "not read",
    never "no roll call found" (rule 19)."""

    def fetch(self, previous):
        pages = {federal.EXECUTIVE_URL: fixture("executive.json"),
                 federal_offices.ADMINISTRATION_URL: fixture("administration.html"),
                 federal_offices.CABINET_URL: fixture("cabinet.html")}

        def read(url):
            if url in pages:
                return pages[url]
            raise federal.FederalError(f"HTTP Error 503 for {url}")

        with mock.patch.object(federal.time, "sleep", lambda _s: None):
            return federal.fetch(previous=previous, today="2026-10-16", read=read,
                                 log=lambda *_a: None)

    def test_nothing_read_is_never_none_found(self):
        holders = [o["holder"] for o in self.fetch(None)["offices"] if o["holder"]]
        self.assertTrue(holders)
        self.assertTrue(all(h["senateUnread"] and h["senate"] is None for h in holders))

    def test_the_last_finding_for_the_same_person_stands(self):
        previous = copy.deepcopy(self.fetch(None))
        office = next(o for o in previous["offices"] if o["holder"])
        office["holder"]["senate"] = {"vote": "119-1-8"}
        office["holder"].pop("senateUnread")
        kept = next(o for o in self.fetch(previous)["offices"]
                    if o["key"] == office["key"])["holder"]
        self.assertEqual(kept["senate"], {"vote": "119-1-8"})
        self.assertNotIn("senateUnread", kept)


class TestTheAgenciesOwnSites(unittest.TestCase):
    """FEDERAL-07: every office links its agency's own website, read from
    USA.gov's directory, whatever its head-name check concluded."""

    def test_the_website_and_contact_page_are_read(self):
        found = federal.parse_agency(fixture("usagov_defense.html"))
        self.assertEqual(found, {"url": "https://www.defense.gov/",
                                 "contact": "https://www.defense.gov/Contact/"})

    def test_a_page_with_no_website_concludes_nothing(self):
        self.assertIsNone(federal.parse_agency("<html><h1>Not found</h1></html>"))

    def test_only_a_government_host_is_linked(self):
        # A .com can lapse and be bought (rule 35); a .gov or .mil cannot.
        page = fixture("usagov_defense.html").replace("https://www.defense.gov/Contact/",
                                                       "https://defense-contact.example.com/")
        self.assertEqual(federal.parse_agency(page), {"url": "https://www.defense.gov/"})
        self.assertIsNone(federal.parse_agency(page.replace("https://www.defense.gov/\"",
                                                            "https://defense.example.com/\"")))

    def test_a_host_known_to_serve_https_is_linked_over_it(self):
        page = fixture("usagov_defense.html").replace("https://www.defense.gov/\"", "http://www.ustr.gov/\"")
        self.assertEqual(federal.parse_agency(page)["url"], "https://www.ustr.gov/")
        # Any other plain-http host keeps the address USA.gov gives.
        page = fixture("usagov_defense.html").replace("https://www.defense.gov/\"", "http://www.example.gov/\"")
        self.assertEqual(federal.parse_agency(page)["url"], "http://www.example.gov/")

    def test_no_committed_site_is_plain_http_where_https_is_served(self):
        cache = federal.load_cache(ROOT)
        for key, site in ((cache or {}).get("sites") or {}).items():
            for url in (site["url"], site.get("contact")):
                self.assertEqual(federal._secure(url), url, key)

    def test_every_committed_site_is_on_a_government_host(self):
        cache = federal.load_cache(ROOT)
        for key, site in ((cache or {}).get("sites") or {}).items():
            self.assertTrue(federal.government_host(site["url"]), key)
            if site.get("contact"):
                self.assertTrue(federal.government_host(site["contact"]), key)

    def test_an_unread_entry_keeps_the_last(self):
        def read(url):
            raise federal.FederalError("HTTP Error 503")
        before = {"state": {"url": "https://www.state.gov/", "source": "x"}}
        sites = federal.agency_sites(read, before, log=lambda *_a: None, pause=0)
        self.assertEqual(sites, before)

    def test_every_office_but_the_chief_of_staff_has_an_entry(self):
        missing = [o["key"] for o in federal_offices.OFFICES if not o.get("usagov")]
        self.assertEqual(missing, ["chief-of-staff"])


class TestTheLineOfSuccession(unittest.TestCase):
    """FEDERAL-23: the Speaker and the President pro tempore, by bioguide id,
    from congress-legislators' leadership roles; never typed in."""

    def rows(self):
        return json.loads(fixture("legislators_leadership.json"))

    def test_the_current_holders_are_read(self):
        found, problems = federal.parse_succession(self.rows(), "2026-10-17")
        self.assertEqual(problems, [])
        self.assertEqual(found["speaker"]["bioguide"], "J000299")
        self.assertEqual(found["presidentProTempore"]["bioguide"], "G000386")

    def test_an_earlier_holder_is_not_current(self):
        # Patty Murray held the office until 2025-01-03.
        found, _ = federal.parse_succession(self.rows(), "2024-06-01")
        self.assertEqual(found["presidentProTempore"]["bioguide"], "M001111")

    def test_two_holders_name_nobody(self):
        rows = self.rows()
        rows[0]["leadership_roles"] = rows[0]["leadership_roles"] + [
            {"title": "Speaker of the House", "chamber": "house", "start": "2026-01-01"}]
        rows[1]["leadership_roles"] = rows[1]["leadership_roles"] + [
            {"title": "Speaker of the House", "chamber": "house", "start": "2026-01-01"}]
        found, problems = federal.parse_succession(rows, "2026-10-17")
        self.assertNotIn("speaker", found)
        self.assertTrue(problems)

    @staticmethod
    def snapshot(term_start, members=("J000299", "G000386")):
        rows = [{"bioguide": b, "name": b, "state": "LA", "chamber": "House",
                 "termStart": term_start} for b in members]
        rows += [{"bioguide": f"H{i:06d}", "name": "x", "state": "TX", "chamber": "House",
                  "termStart": term_start} for i in range(10)]
        return {"legislators": rows}

    def executive(self):
        found, _ = federal.parse_succession(self.rows(), "2026-10-17")
        return {"succession": found}

    def test_the_speaker_of_the_sitting_congress_is_named(self):
        from kyc import federal_build
        officers, problems = federal_build.congressional_officers(
            self.executive(), self.snapshot("2025-01-03"))
        self.assertEqual(problems, [])
        self.assertEqual(officers["speaker"]["member"]["bioguide"], "J000299")

    def test_the_last_congresss_speaker_is_not_named_after_january_3(self):
        # congress-legislators records the 119th Congress's Speaker with no
        # end date; on January 3 the 120th sits and has chosen its own, which
        # the file may not record for two weeks (rule 68). Still seated in
        # the House, he is not shown as second in line.
        from kyc import federal_build
        officers, problems = federal_build.congressional_officers(
            self.executive(), self.snapshot("2027-01-03"))
        self.assertEqual(set(officers["speaker"]), {"missing"})
        self.assertEqual(set(officers["presidentProTempore"]), {"missing"})
        self.assertIn("120th Congress's Speaker", officers["speaker"]["missing"])
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("before the 120th Congress began" in p for p in problems))
        # And the build reports it: never silent.
        from kyc import validate
        issues = validate.check_succession(self.executive(), self.snapshot("2027-01-03"))
        self.assertEqual([i.code for i in issues], ["succession-unnamed"])

    def test_a_holder_not_seated_is_not_named(self):
        from kyc import federal_build
        officers, problems = federal_build.congressional_officers(
            self.executive(), self.snapshot("2025-01-03", members=("G000386",)))
        self.assertIn("missing", officers["speaker"])
        self.assertIn("member", officers["presidentProTempore"])
        self.assertEqual(len(problems), 1)


class TestTheBuildsWord(unittest.TestCase):
    def test_a_term_that_has_ended_is_an_error(self):
        cache = {"president": {"name": "P", "termStart": "2025-01-20", "termEnd": "2029-01-20"},
                 "vicePresident": {"name": "V", "termStart": "2025-01-20",
                                   "termEnd": "2029-01-20"},
                 "offices": [{"key": o["key"], "office": o["office"], "holder": None}
                             for o in federal_offices.DEPARTMENTS]}
        codes = {code: level for level, code, _m, _d in federal.problems(cache, "2029-01-21")}
        self.assertEqual(codes["federal-term-ended"], "error")
        self.assertEqual(codes["federal-office-unlisted"], "warn")
        self.assertNotIn("federal-term-ended",
                         {c for _l, c, _m, _d in federal.problems(cache, "2026-10-16")})

    def test_the_committed_cache_is_whole(self):
        cache = federal.load_cache(ROOT)
        if cache is None:
            self.skipTest("no federal cache committed")
        errors = [(c, m) for level, c, m, _d in federal.problems(cache) if level == "error"]
        self.assertEqual(errors, [])
        # No Cabinet officer is given a party: no source used states one.
        self.assertTrue(all("party" not in (o.get("holder") or {})
                            for o in cache["offices"]))


if __name__ == "__main__":
    unittest.main()
