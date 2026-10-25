"""The federal government's pages: what kyc/federal_build.py writes for them
(data/federal.js, one file per court, the judges' search index) and the
pages kyc/pages.py generates (federal/index.html, courts/<id>.html)."""

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, federal_build, federal_courts, judiciary, pages, vacancies  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def built():
    try:
        return federal_build.build(ROOT)
    except federal_build.FederalBuildError as exc:
        raise unittest.SkipTest(str(exc))


class TestTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.courts, cls.search, cls.problems = built()

    def test_the_caches_have_no_errors(self):
        problems = self.problems
        from kyc import cycle, legislators
        if cycle.snapshot_congress(legislators.load_snapshot(ROOT)) >= cycle.electing_congress():
            # A new Congress whose officers congress-legislators has not yet
            # recorded: the line of succession names nobody for them, and
            # says so (rule 68). Only that is allowed.
            problems = [p for p in problems if not p.startswith("the line of succession names no")]
        self.assertEqual(problems, [])

    def test_every_court_has_a_file(self):
        self.assertEqual(set(self.courts), set(federal_courts.COURTS))
        for cid, court in self.courts.items():
            listed = federal_courts.COURTS[cid]["kind"] != "territorial"
            self.assertEqual(court["listed"], listed, cid)

    def test_no_official_is_a_profile(self):
        # Officials are never counted among the members of Congress (rule
        # 27): their ids cannot be a profile's.
        ids = [self.payload["president"]["id"], self.payload["vicePresident"]["id"]]
        ids += [o["holder"]["id"] for o in self.payload["offices"] if o["holder"]]
        ids += [j["id"] for c in self.courts.values() for j in c["judges"]]
        self.assertTrue(all(re.match(r"^(x|fjc)-[a-z0-9-]+$", i) for i in ids))

    def test_a_judge_and_a_cabinet_officer_carry_no_party(self):
        self.assertNotIn('"party"', json.dumps(self.courts))
        self.assertNotIn('"party"', json.dumps(self.payload["supremeCourt"]))
        self.assertNotIn('"party"', json.dumps(self.payload["offices"]))
        # The President and the Vice President were elected on a ticket.
        self.assertTrue(self.payload["president"]["party"])

    def test_the_departments_are_in_the_order_of_succession(self):
        orders = [o["order"] for o in self.payload["offices"] if o["kind"] == "department"]
        self.assertEqual(sorted(orders), list(range(1, len(orders) + 1)))

    def test_the_search_lists_each_judge_once_with_every_court(self):
        # A judge on several courts (a roving judgeship) is one person.
        expected = {}
        for cid, court in self.courts.items():
            for judge in court["judges"]:
                expected.setdefault(judge["id"], []).append(cid)
        self.assertEqual({row[0]: row[2] for row in self.search}, expected)
        self.assertEqual(len(self.search), len({row[0] for row in self.search}))
        names = [(row[1], row[0]) for row in self.search]
        self.assertEqual(names, sorted(names))

    def test_the_count_is_of_sitting_judges(self):
        # The retired justices are listed apart, never counted as sitting.
        self.assertEqual(self.payload["judges"], len(self.search))

    def test_vacancies_are_on_the_courts_their_codes_name(self):
        from kyc import vacancies

        cache = vacancies.load_cache(ROOT)
        self.assertEqual(sum(len(c["vacancies"]) for c in self.courts.values()),
                         sum(1 for r in cache["current"] if r.get("court")))
        index = {c["id"]: c for c in self.payload["courts"]}
        for cid, court in self.courts.items():
            self.assertEqual(index[cid]["vacancies"], len(court["vacancies"]), cid)
            self.assertEqual(index[cid]["future"], len(court["future"]), cid)
        self.assertEqual(self.payload["vacancies"]["totals"], cache["totals"])

    def test_the_circuit_map_has_one_table_and_neighbours_never_share_a_colour(self):
        from kyc import geo, government_maps

        # The guide's map and the hub's read one table (rule 12).
        self.assertEqual(government_maps.CIRCUITS, federal_courts.circuits())
        tokens = {c["circuit"]: c["token"] for c in self.payload["courts"] if c.get("token")}
        self.assertEqual(set(tokens), set(federal_courts.circuits()))
        of = {code: key for key, codes in federal_courts.circuits().items() for code in codes}
        for code, others in geo.neighbours().items():
            for other in others:
                if code in of and other in of and of[code] != of[other]:
                    self.assertNotEqual(tokens[of[code]], tokens[of[other]], (code, other))
        # Every state and territory with a district court is in exactly one
        # circuit; American Samoa, which has none, in none.
        self.assertNotIn("AS", of)
        self.assertEqual(sum(len(codes) for codes in federal_courts.circuits().values()), len(of))

    def test_a_retired_justice_is_never_a_member(self):
        scotus = self.payload["supremeCourt"]
        self.assertEqual(len(scotus["members"]), federal_courts.SUPREME_COURT_SEATS)
        self.assertFalse({j["id"] for j in scotus["members"]} & {j["id"] for j in scotus["retired"]})

    def test_a_justices_portrait_is_the_official_one_commons_holds_else_the_courts(self):
        """The owner's decision of 2026-10-20: the Court's official portraits
        as Wikimedia Commons holds them, credited to their photographers;
        the Court's own only for a justice Commons holds none of."""
        from kyc import judge_links, overrides

        links = judge_links.load_cache(ROOT)
        held = 0
        for justice in self.payload["supremeCourt"]["members"]:
            nid = justice["id"].replace("fjc-", "")
            portrait = justice.get("portrait") or {}
            official = judge_links.official_portrait(links, nid)
            if official:
                held += 1
                self.assertEqual(portrait["source"], official["source"], justice["name"])
                self.assertEqual((portrait["by"], portrait["licence"]),
                                 (overrides.JUSTICE_PORTRAITS[nid][1], official["licence"]))
                self.assertNotIn("supremecourt.gov", portrait["url"])
            elif portrait:
                # Never another Commons file passed off as the Court's
                # portrait: Sotomayor's item shows a 2009 White House photo,
                # so only the table's file is ever hers.
                self.assertEqual(portrait["credit"], judiciary.PORTRAIT_CREDIT, justice["name"])
                self.assertIn("supremecourt.gov", portrait["url"])
        if links and links.get("read", "") >= "2026-10-25":
            # Read on 2026-10-25: all nine, Sotomayor's and Kagan's
            # official portraits by the table's files.
            self.assertGreaterEqual(held, len(overrides.JUSTICE_PORTRAITS))


class TestAJusticesFallback(unittest.TestCase):
    """A justice the table names whose official file the read did not take
    as recorded keeps the Court's own portrait, and is marked so the page
    says the read did not confirm the file - never that Commons does not
    hold it (the PR #133 review)."""

    RECORD = {"id": "fjc-100", "name": "Ann B. Example", "justice": {"role": "Associate Justice"},
              "portrait": {"url": "https://www.supremecourt.gov/about/justice_pictures/Example.jpg",
                           "credit": judiciary.PORTRAIT_CREDIT}}

    def test_an_unconfirmed_official_file_keeps_the_courts_and_says_so(self):
        from unittest import mock
        from kyc import overrides
        entry = ("Ann Example official portrait.jpg", "Steve Petteway", "2026-10-20", "official")
        with mock.patch.dict(overrides.JUSTICE_PORTRAITS, {"100": entry}, clear=True):
            out = federal_build._judge(dict(self.RECORD), {"judges": {}})
        self.assertIn("supremecourt.gov", out["portrait"]["url"])
        self.assertTrue(out.get("portraitUnconfirmed"))
        # A justice the table does not name: the Court's own, unmarked.
        with mock.patch.dict(overrides.JUSTICE_PORTRAITS, {}, clear=True):
            out = federal_build._judge(dict(self.RECORD), {"judges": {}})
        self.assertNotIn("portraitUnconfirmed", out)
        # A judge who is not a justice is never marked.
        with mock.patch.dict(overrides.JUSTICE_PORTRAITS, {"100": entry}, clear=True):
            out = federal_build._judge({k: v for k, v in self.RECORD.items() if k != "justice"},
                                       {"judges": {}})
        self.assertNotIn("portraitUnconfirmed", out)


class TestTheFiles(unittest.TestCase):
    """Each file is rewritten only when what it says changed, and verify
    names a stale one (rule 18)."""

    def test_written_files_carry_their_signature(self):
        payload, courts, search, _ = built()
        with tempfile.TemporaryDirectory() as tmp:
            written = emit.write_federal(payload, courts, search, tmp)
            self.assertEqual(len(written), len(courts) + 2)
            self.assertEqual(emit.check_federal(payload, courts, search, tmp), [])
            self.assertEqual(emit.write_federal(payload, courts, search, tmp), [])
            changed = dict(courts, ca1=dict(courts["ca1"], judges=courts["ca1"]["judges"][1:]))
            stale = emit.check_federal(payload, changed, search, tmp)
            self.assertEqual([os.path.basename(p) for p, _ in stale], ["ca1.js"])
            self.assertEqual(len(emit.write_federal(payload, changed, search, tmp)), 1)

    def test_a_court_file_adds_itself_to_the_courts_loaded(self):
        payload, courts, search, _ = built()
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_federal(payload, courts, search, tmp)
            with open(os.path.join(tmp, emit.JUDICIARY_DIR, "ca1.js"), encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn("window.kycCourt = window.kycCourt || {};", text)
        self.assertIn('window.kycCourt["ca1"] = ', text)


class TestCabinetHistory(unittest.TestCase):
    def test_an_acting_end_after_the_successor_began_is_not_shown(self):
        """Neither date is moved; the end is withheld and says why."""
        from kyc import cabinet, federal
        payload, _, _, _ = built()
        cache = federal.load_cache(ROOT)
        offices = (cache.get("changes") or {}).get("offices") or {}
        for office in payload["offices"]:
            held = (offices.get(office["key"]) or {}).get("holders") or []
            found = cabinet.overlaps(held)
            for i, row in enumerate(office.get("history") or []):
                if i in found:
                    self.assertIsNone(row["end"]["shown"])
                    self.assertTrue(row["end"]["overlap"])
                else:
                    self.assertNotIn("overlap", row.get("end") or {})


class TestJudgesNames(unittest.TestCase):
    def test_no_name_shown_carries_the_directorys_brackets(self):
        """FJC writes "A[llen] Joe Fish": shown as "A. Joe Fish", with the
        full name beside it in the dialog and in the search."""
        payload, courts, search, _ = built()
        shown = [j for c in courts.values() for j in c["judges"] + c.get("retired", [])]
        shown += payload["supremeCourt"]["members"] + payload["supremeCourt"]["retired"]
        self.assertEqual([j["name"] for j in shown if "[" in j["name"]], [])
        self.assertEqual([c["chief"]["name"] for c in payload["courts"]
                          if c.get("chief") and "[" in c["chief"]["name"]], [])
        self.assertEqual([row[1] for row in search if "[" in row[1]], [])
        bracketed = [j for j in shown if j.get("fullName")]
        for judge in bracketed:
            self.assertNotIn("[", judge["fullName"])
            self.assertEqual(judge["name"].split()[-1], judge["fullName"].split()[-1])
        rows = {row[0]: row for row in search}
        for judge in bracketed:
            if judge["id"] in rows:
                self.assertEqual(rows[judge["id"]][4], judge["fullName"])
        self.assertTrue(all(len(row) == 4 for row in search if row[0] not in
                            {j["id"] for j in bracketed}))


class TestVacanciesAgainstTheDirectory(unittest.TestCase):
    def test_a_vacancy_whose_judge_the_directory_does_not_list_is_marked(self):
        """The courts' list says a judge took senior status; a judge on
        senior status still serves, so one the directory lists nowhere on
        that court is marked on the row, and only then."""
        _payload, courts, _, _ = built()
        judges = judiciary.load_cache(ROOT)["judges"]
        cache = vacancies.load_cache(ROOT)
        for cid, court in courts.items():
            for key, future in (("vacancies", False), ("future", True)):
                rows = [r for r in cache["future" if future else "current"] if r.get("court") == cid]
                self.assertEqual(len(rows), len(court[key]))
                for raw, shown in zip(rows, court[key]):
                    expected = bool(court["listed"]) and vacancies.judge_unlisted(raw, judges, future)
                    self.assertEqual(bool(shown.get("notInDirectory")), expected, (cid, raw))


def _judge(jid, sort, court, senior=None):
    return jid, {"id": jid, "sortName": sort, "status": "senior" if senior else "active",
                 "seats": [{"court": court, "seniorSince": senior}]}


class TestWhoSits(unittest.TestCase):
    """FEDERAL-01, -V1, -16 and -25: the two sources disagree about Judge
    Varlan; announced vacancies have not happened; a confirmed judge with
    no commission is not sitting."""

    CACHE = {"asOf": "2026-10-17", "current": [
        {"court": "tn-e", "reason": "Senior", "since": "2026-10-05",
         "vacatedBy": {"listedAs": "Varlan,Thomas A.", "name": "Thomas A. Varlan"}},
        # After the list's own date: not yet senior by either source.
        {"court": "tn-m", "reason": "Senior", "since": "2026-11-01",
         "vacatedBy": {"listedAs": "Later,Ann", "name": "Ann Later"}},
        {"court": "ca8", "reason": "Senior", "since": "2026-01-01",
         "nominee": {"listedAs": "Rudofsky,Lee Philip", "name": "Lee Philip Rudofsky"},
         "vacatedBy": {"listedAs": "Shepherd,Bobby E.", "name": "Bobby E. Shepherd"}},
    ], "future": [
        {"court": "ar-e", "reason": "Elevated",
         "vacatedBy": {"listedAs": "Rudofsky,Lee P.", "name": "Lee P. Rudofsky"}},
        {"court": "co", "reason": "Elevated",
         "vacatedBy": {"listedAs": "Nobody,Named", "name": "Named Nobody"}},
    ]}

    def test_a_judge_senior_by_the_list_and_active_by_the_directory_is_found(self):
        judges = dict([_judge("fjc-1", "Varlan, Thomas", "tn-e"),
                       _judge("fjc-2", "Later, Ann", "tn-m"),
                       _judge("fjc-3", "Shepherd, Bobby", "ca8", senior="2026-01-01")])
        found = vacancies.listed_senior(self.CACHE, judges)
        self.assertEqual(list(found), [("tn-e", "fjc-1")])

    def test_two_judges_of_one_name_settle_nothing(self):
        judges = dict([_judge("fjc-1", "Varlan, Thomas", "tn-e"),
                       _judge("fjc-9", "Varlan, Thomas", "tn-e")])
        self.assertEqual(vacancies.listed_senior(self.CACHE, judges), {})

    def test_a_colleague_of_the_same_surname_is_never_moved(self):
        # Rule 17: the judge the list has leaving is missing from the
        # directory (as two are now), and an active colleague shares the
        # surname. A surname match would have counted the colleague senior.
        judges = dict([_judge("fjc-9", "Varlan, Margaret", "tn-e")])
        self.assertEqual(vacancies.listed_senior(self.CACHE, judges), {})
        both = dict(judges, **dict([_judge("fjc-1", "Varlan, Thomas", "tn-e")]))
        self.assertEqual(list(vacancies.listed_senior(self.CACHE, both)), [("tn-e", "fjc-1")])

    def test_an_elevation_names_the_court_the_judge_is_nominated_to(self):
        self.assertEqual(vacancies.nominated_to(self.CACHE["future"][0], self.CACHE), "ca8")
        self.assertIsNone(vacancies.nominated_to(self.CACHE["future"][1], self.CACHE))

    def test_the_nominated_judges_own_record_names_the_court(self):
        # Domenico's dialog said only "Active service" while his court's
        # table had him nominated to the Tenth Circuit.
        judges = dict([_judge("fjc-5", "Rudofsky, Lee", "ar-e"), _judge("fjc-6", "Rudofsky, Ann", "ar-w")])
        self.assertEqual(vacancies.pending_elevations(self.CACHE, judges),
                         {"fjc-5": {"court": "ca8", "nominated": None}})

    def test_the_committed_data_carries_each_pending_elevation(self):
        _payload, courts, _, _ = built()
        for cid, court in courts.items():
            moving = {r["vacatedBy"]["name"] for r in court["future"] if r.get("nominatedTo")}
            for judge in court["judges"]:
                if judge.get("nominatedTo"):
                    self.assertNotEqual(judge["nominatedTo"]["id"], cid)
                    self.assertTrue(moving, (cid, judge["name"]))

    def test_the_committed_data_counts_varlan_senior_and_says_so(self):
        payload, courts, search, _ = built()
        cache = vacancies.load_cache(ROOT)
        judges = judiciary.load_cache(ROOT)["judges"]
        listed = vacancies.listed_senior(cache, judges)
        held = judiciary.load_cache(ROOT)["courts"]
        for (cid, jid), row in listed.items():
            court = next(c for c in payload["courts"] if c["id"] == cid)
            self.assertEqual(court["active"], held[cid]["active"] - court["listedSenior"])
            judge = next(j for j in courts[cid]["judges"] if j["id"] == jid)
            self.assertEqual(judge["listedSenior"], {"since": row["since"]})
            self.assertEqual(next(r for r in search if r[0] == jid)[3], "listed-senior")
        # Nobody else is moved.
        moved = {jid for (_c, jid) in listed}
        self.assertFalse([j for c in courts.values() for j in c["judges"]
                          if j.get("listedSenior") and j["id"] not in moved])

    def test_announced_rows_are_marked_future_and_carry_the_other_court(self):
        _payload, courts, _, _ = built()
        for court in courts.values():
            self.assertTrue(all(r.get("future") for r in court["future"]))
            self.assertFalse(any(r.get("future") for r in court["vacancies"]))
            for row in court["future"]:
                if row.get("nominatedTo"):
                    self.assertEqual(row["reason"], "Elevated")
                    self.assertIn(row["nominatedTo"]["id"], federal_courts.COURTS)

    def test_a_confirmed_judge_without_a_commission_is_listed_apart(self):
        payload, courts, search, _ = built()
        pending = [p for p in judiciary.load_cache(ROOT).get("pending") or [] if isinstance(p, dict)]
        for row in pending:
            listed = courts[row["court"]].get("pending") or []
            self.assertIn(row["name"], [p["name"] for p in listed])
            self.assertNotIn(row["name"], [j["name"] for j in courts[row["court"]]["judges"]])
            self.assertNotIn(row["name"], [r[1] for r in search])

    def test_the_hub_lists_every_vacancy_with_its_court(self):
        payload, _courts, _, _ = built()
        cache = vacancies.load_cache(ROOT)
        rows = payload["vacancies"]["rows"]
        placed = [r for r in cache["current"] + cache["future"] if r.get("court")]
        self.assertEqual(len(rows), len(placed))
        self.assertEqual(payload["vacancies"]["futureNominees"],
                         sum(1 for r in cache["future"] if r.get("nominee")))


class TestThePages(unittest.TestCase):
    def test_a_court_page_loads_its_own_court_and_carries_no_names(self):
        html = pages.render_court_page("ca1", "example.org")
        self.assertIn('src="../data/judiciary/ca1.js"', html)
        self.assertIn('data-court="ca1"', html)
        # A court id in data-state would be remembered as the reader's state.
        self.assertIn('data-state=""', html)
        payload, courts, _, _ = built()
        for judge in courts["ca1"]["judges"]:
            self.assertNotIn(judge["name"], html)

    def test_a_court_page_describes_what_its_kind_holds(self):
        """A territorial court's judges are not in the directory, and a
        justice takes no senior status: neither page promises them."""
        def description(cid):
            html = pages.render_court_page(cid, "example.org")
            return re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        for cid in ("gu", "mp", "vi"):
            text = description(cid)
            self.assertIn("Article IV", text)
            self.assertIn("not listed", text)
            self.assertNotIn("Every sitting judge", text)
        self.assertNotIn("senior status", description("scotus"))
        self.assertIn("justice", description("scotus"))
        self.assertIn("Every sitting judge", description("ca1"))

    @staticmethod
    def committed(path):
        with open(os.path.join(ROOT, "candidate_profiles_site", path), encoding="utf-8") as handle:
            return handle.read()

    def test_a_territorial_page_credits_the_court_it_lists_judges_from(self):
        # FEDERAL-06 listed the judges; the footer and the description still
        # said they were not listed, and named no source for them.
        _payload, courts, _, _ = built()
        for cid in ("gu", "mp", "vi"):
            own = courts[cid].get("courtList") or {}
            if not own.get("judges"):
                continue
            html = self.committed(f"courts/{cid}.html")
            footer = html[html.index("<strong>Sources:</strong>"):]
            footer = footer[:footer.index("</p>")]
            self.assertIn(f'href="{own["source"]}"', footer, cid)
            self.assertNotIn("judges are not listed", footer, cid)
            text = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
            self.assertNotIn("not listed", text, cid)
            chief = next((j["name"] for j in own["judges"] if j.get("chief")), None)
            if chief:
                self.assertIn(f"Chief judge: {chief}", text.replace("&#x27;", "'"), cid)

    def test_the_plain_lists_say_which_source_says_what_and_date_in_words(self):
        # The pre-rendered table named Varlan "Senior status" with no word on
        # the directory, which still lists him active.
        _payload, courts, _, _ = built()
        iso = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
        for cid, court in courts.items():
            moved = [j for j in court["judges"] if j.get("listedSenior")]
            html = self.committed(f"courts/{cid}.html")
            static = html[html.index('<div class="fed-prerendered">'):]
            static = static[:static.index("</div>")]
            for judge in moved:
                self.assertIn("Senior status by the courts&#8217; list (the FJC directory still "
                              "lists active service)", static, cid)
            self.assertNotRegex(static.replace('datetime="', ""), iso, cid)
            if court["listed"] and court["judges"]:
                self.assertIn('data-label="Appointed by"', static, cid)
            description = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
            self.assertNotRegex(description, iso, cid)
            self.assertNotIn("needs JavaScript", static, cid)

    def test_no_page_calls_the_courts_it_links_the_article_iii_courts(self):
        """The hub's courts section holds the Article IV territorial courts."""
        for html in (pages.render_court_page("gu", "example.org"),
                     pages.render_court_page("ca1", "example.org"),
                     pages.render_federal_page("example.org")):
            self.assertNotIn("The Article III courts", html)
            self.assertIn('href="../federal/index.html#courts"', html)

    def test_the_hub_carries_no_names(self):
        html = pages.render_federal_page("example.org")
        payload, _, _, _ = built()
        self.assertNotIn(payload["president"]["name"], html)
        self.assertIn('src="../data/judiciary/index.js"', html)

    def test_every_federal_page_loads_its_scripts_in_order(self):
        found = {page: (ok, note) for page, ok, note in emit.check_pages(ROOT)
                 if page.startswith(("federal/", "courts/"))}
        # Every court, the hub, and the folder's own directory of courts.
        self.assertEqual(len(found), len(federal_courts.COURTS) + 2)
        self.assertEqual({p: n for p, (ok, n) in found.items() if not ok}, {})

    def test_the_sitemap_lists_every_court(self):
        text = pages.sitemap("example.org", ["TX"], courts=tuple(federal_courts.COURTS))
        self.assertIn("https://example.org/federal/index.html", text)
        for cid in federal_courts.COURTS:
            self.assertIn(f"https://example.org/courts/{cid}.html", text)


if __name__ == "__main__":
    unittest.main()
