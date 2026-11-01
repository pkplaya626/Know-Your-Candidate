"""A court's own word on its chief where the directory's record cannot say
(kyc/court_chiefs.py, FEDERAL-17), and each judge's financial disclosures
as CourtListener holds them, joined by the FJC's judge id
(kyc/judge_disclosures.py, FEDERAL-05).

Every case is made here (the Conventions): a page naming one chief, two, a
stranger, none; a CourtListener record whose surname or year of birth
disagrees, an alias, an id two records carry; a page that cannot be read.
"""

import bz2
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import court_chiefs, federal_build, judge_disclosures  # noqa: E402

TODAY = "2026-11-01"

# The Middle District of North Carolina's page as read on 2026-11-01, cut
# to its headings.
NCMD = """<html><body><nav><h4><a href="/">Judges</a>, Chief Judge of the menu</h4></nav>
<h1 id="page-title">Judges for the Middle District of North Carolina</h1>
<h4><a href="/court-info/court-locations/greensboro">Catherine C. Eagles</a>, Chief District Judge</h4>
<h4><a href="/court-info/court-locations/greensboro">William L. Osteen, Jr.</a>, District Judge</h4>
<h4><a href="/court-info/court-locations/greensboro">N. Carlton Tilley, Jr.</a>, Senior District Judge</h4>
<h4><a href="/court-info/court-locations/greensboro">L. Patrick Auld</a>, Magistrate Judge</h4>
</body></html>"""


def judges():
    seat = lambda **kw: [dict({"court": "nc-m"}, **kw)]  # noqa: E731
    return {
        "fjc-1": {"name": "Catherine Caldwell Eagles", "sortName": "Eagles, Catherine",
                  "seats": seat(seniorSince="2024-12-31", chiefUnsettled=True)},
        "fjc-2": {"name": "William Lindsay Osteen, Jr.", "sortName": "Osteen, William",
                  "seats": seat()},
        "fjc-3": {"name": "Ann Eagles", "sortName": "Eagles, Ann", "seats": [{"court": "nc-e"}]},
    }


def cache(entry=None, unsettled=True):
    out = {"judges": judges(),
           "courts": {"nc-m": {"chiefUnsettled": unsettled, "judges": ["fjc-1", "fjc-2"]}}}
    if entry is not None:
        out["courtChiefs"] = {"nc-m": entry}
    return out


class TestTheCourtsWordOnItsChief(unittest.TestCase):
    def test_reads_the_chief_and_ties_them_to_the_directory(self):
        read = court_chiefs.read_court("nc-m", NCMD, judges())
        self.assertEqual(read, {"chief": "Catherine C. Eagles", "title": "Chief District Judge",
                                "words": "Catherine C. Eagles, Chief District Judge",
                                "judge": "fjc-1"})

    def test_nothing_from_navigation(self):
        rows = court_chiefs.read_headings(NCMD)
        self.assertNotIn("Judges", [r["name"] for r in rows])
        self.assertEqual(len(rows), 4)

    def test_two_chiefs_are_refused(self):
        page = NCMD.replace("William L. Osteen, Jr.</a>, District Judge",
                            "William L. Osteen, Jr.</a>, Chief District Judge")
        with self.assertRaisesRegex(court_chiefs.CourtChiefError, "2 chief judges"):
            court_chiefs.read_court("nc-m", page, judges())

    def test_a_chief_magistrate_is_not_the_courts_chief(self):
        page = NCMD.replace("L. Patrick Auld</a>, Magistrate Judge",
                            "L. Patrick Auld</a>, Chief Magistrate Judge")
        self.assertEqual(court_chiefs.read_court("nc-m", page, judges())["judge"], "fjc-1")

    def test_a_chief_the_directory_does_not_list_here_is_refused(self):
        page = NCMD.replace("Catherine C. Eagles", "Pat Stranger")
        with self.assertRaisesRegex(court_chiefs.CourtChiefError, "not a judge the directory"):
            court_chiefs.read_court("nc-m", page, judges())

    def test_a_surname_alone_is_not_the_judge(self):
        # Another court's Ann Eagles, and a given name that is not Catherine.
        page = NCMD.replace("Catherine C. Eagles", "Ann Eagles")
        with self.assertRaises(court_chiefs.CourtChiefError):
            court_chiefs.read_court("nc-m", page, judges())

    def test_no_chief_is_refused_not_guessed(self):
        page = NCMD.replace("Chief District Judge", "District Judge")
        with self.assertRaisesRegex(court_chiefs.CourtChiefError, "no chief"):
            court_chiefs.read_court("nc-m", page, judges())

    def test_a_page_not_read_keeps_the_last_read(self):
        old = {"chief": "Catherine C. Eagles", "read": "2026-10-01", "judge": "fjc-1"}

        def fail(url):
            raise court_chiefs.CourtChiefError("timed out")
        reads, trouble = court_chiefs.fetch(judges(), {"nc-m": old}, read=fail, today=TODAY)
        self.assertEqual(reads["nc-m"], old)
        self.assertTrue(trouble)
        reads, _ = court_chiefs.fetch(judges(), None, read=fail, today=TODAY)
        self.assertTrue(reads["nc-m"]["unread"])

    def test_a_refused_page_shows_nothing(self):
        reads, trouble = court_chiefs.fetch(judges(), None, today=TODAY,
                                            read=lambda url: NCMD.replace("Catherine C.", "Pat"))
        self.assertIn("refused", reads["nc-m"])
        self.assertIsNone(court_chiefs.shown(cache(reads["nc-m"]), "nc-m"))
        codes = [p[1] for p in court_chiefs.problems(cache(reads["nc-m"]), TODAY)]
        self.assertIn("court-chief-refused", codes)

    def test_shown_only_where_the_directory_cannot_say(self):
        reads, _ = court_chiefs.fetch(judges(), None, read=lambda url: NCMD, today=TODAY)
        entry = reads["nc-m"]
        self.assertEqual(entry["read"], TODAY)
        self.assertEqual(court_chiefs.shown(cache(entry), "nc-m")["name"], "Catherine C. Eagles")
        self.assertIsNone(court_chiefs.shown(cache(entry, unsettled=False), "nc-m"))
        codes = [p[1] for p in court_chiefs.problems(cache(entry, unsettled=False), TODAY)]
        self.assertIn("court-chief-recipe-unused", codes)

    def test_a_chief_who_has_left_the_court_is_not_shown(self):
        entry = dict(court_chiefs.read_court("nc-m", NCMD, judges()), source="x", read=TODAY)
        left = cache(entry)
        left["courts"]["nc-m"]["judges"] = ["fjc-2"]
        self.assertIsNone(court_chiefs.shown(left, "nc-m"))
        self.assertIn("court-chief-not-sitting",
                      [p[1] for p in court_chiefs.problems(left, TODAY)])

    def test_stale_and_unread_and_unrecipied_are_warned(self):
        entry = dict(court_chiefs.read_court("nc-m", NCMD, judges()), source="x", read="2026-08-01")
        self.assertIn("court-chief-stale", [p[1] for p in court_chiefs.problems(cache(entry), TODAY)])
        self.assertIn("court-chief-unread", [p[1] for p in court_chiefs.problems(cache(), TODAY)])
        other = cache()
        other["courts"]["xx"] = {"chiefUnsettled": True}
        self.assertIn("court-chief-no-recipe", [p[1] for p in court_chiefs.problems(other, TODAY)])

    def test_every_recipe_names_a_court_and_its_own_host(self):
        from kyc import court_info
        for cid, recipe in court_chiefs.RECIPES.items():
            self.assertTrue(recipe["url"].startswith(court_info.SITES[cid]), cid)


# ----------------------------------------------------------- disclosures

PEOPLE_HEAD = "id,fjc_id,slug,name_first,name_last,date_dob,is_alias_of_id\n"
REPORTS_HEAD = "id,year,person_id\n"


def people_file(rows, pad=judge_disclosures.MIN_PEOPLE):
    body = PEOPLE_HEAD + "".join(",".join(r) + "\n" for r in rows)
    body += "".join(f"{9_000_000 + i},,filler-{i},A,B,,\n" for i in range(pad))
    return bz2.compress(body.encode("utf-8"))


def reports_file(rows, pad=judge_disclosures.MIN_REPORTS):
    body = REPORTS_HEAD + "".join(",".join(r) + "\n" for r in rows)
    body += "".join(f"{8_000_000 + i},2001,999999999\n" for i in range(pad))
    return bz2.compress(body.encode("utf-8"))


FJC = ('"nid","jid","Last Name"\n"100","10","Smith"\n"200","20","Hall"\n"300","30","Richman"\n'
       '"400","40","Lee"\n"500","50","Alias"\n"600","60","Twice"\n"700","70","Quinones"\n')

DIRECTORY = {
    "fjc-100": {"name": "Jane Smith", "sortName": "Smith, Jane", "born": {"year": "1960"}},
    "fjc-200": {"name": "LaShann DeArcy Hall", "sortName": "DeArcy Hall, LaShann",
                "born": {"year": "1970"}},
    "fjc-300": {"name": "Priscilla Richman", "sortName": "Richman, Priscilla"},
    "fjc-400": {"name": "Ann Lee", "sortName": "Lee, Ann", "born": {"year": "1951"}},
    "fjc-500": {"name": "Al Alias", "sortName": "Alias, Al"},
    "fjc-600": {"name": "Tom Twice", "sortName": "Twice, Tom"},
    "fjc-700": {"name": "Nitza Quiñones Alejandro", "sortName": "Quiñones Alejandro, Nitza"},
    "fjc-800": {"name": "Not Joined", "sortName": "Joined, Not"},
}

PEOPLE = [
    ["1", "10", "jane-smith", "Jane", "Smith", "1960-04-02", ""],
    ["2", "20", "lashann-hall", "LaShann", "Hall", "", ""],
    ["3", "30", "priscilla-owen", "Priscilla", "Owen", "", ""],
    ["4", "40", "ann-lee", "Ann", "Lee", "1952-01-01", ""],
    ["5", "50", "al-alias", "Al", "Alias", "", "77"],
    ["6", "60", "tom-twice", "Tom", "Twice", "", ""],
    ["16", "60", "tom-twice-2", "Tom", "Twice", "", ""],
    ["7", "70", "nitza-quinones-alejandro", "Nitza", "Quinones Alejandro", "", ""],
]

REPORTS = [["1", "2019", "1"], ["2", "2020", "1"], ["3", "2018", "1"]]


def listing(*keys, truncated=False):
    return ("<ListBucketResult><IsTruncated>" + ("true" if truncated else "false") +
            "</IsTruncated>" + "".join(f"<Contents><Key>bulk-data/{k}</Key></Contents>"
                                       for k in keys) + "</ListBucketResult>")


def reader(people=None, reports=None, listings=None):
    files = {
        judge_disclosures.LISTING + judge_disclosures.PEOPLE: (listings or (
            listing("people-db-people-2026-06-30.csv.bz2", "people-db-people-2026-09-30.csv.bz2",
                    "people-db-people-2026-12-31.csv.bz2"),))[0],
        judge_disclosures.LISTING + judge_disclosures.REPORTS: (listings or (None, listing(
            "financial-disclosures-2026-06-30.csv.bz2", "financial-disclosures-2026-09-30.csv.bz2",
            "financial-disclosures-gifts-2026-12-31.csv.bz2")))[1],
        judge_disclosures.file_url("people-db-people-", "2026-09-30"): people or people_file(PEOPLE),
        judge_disclosures.file_url("financial-disclosures-", "2026-09-30"):
            reports or reports_file(REPORTS),
        judge_disclosures.judiciary.JUDGES_URL: FJC,
    }

    def read(url):
        value = files[url]
        return value.encode("utf-8") if isinstance(value, str) else value
    return read


class TestJudgesDisclosures(unittest.TestCase):
    def setUp(self):
        self.cache = judge_disclosures.fetch(DIRECTORY, read=reader(), today=TODAY,
                                             log=lambda *a: None)

    def test_the_newest_export_both_files_share(self):
        # 2026-12-31 has a people file but only a gifts table, not the reports.
        self.assertEqual(self.cache["export"], "2026-09-30")

    def test_joined_by_the_fjc_judge_id_with_reports_and_years(self):
        self.assertEqual(self.cache["judges"]["100"], {
            "person": "1", "slug": "jane-smith", "reports": 3, "first": "2018", "last": "2020"})
        shown = judge_disclosures.for_judge(self.cache, "100")
        self.assertEqual(shown["url"],
                         "https://www.courtlistener.com/person/1/jane-smith/#disclosures")

    def test_a_compound_surname_and_accents_agree(self):
        self.assertIn("200", self.cache["judges"])
        self.assertIn("700", self.cache["judges"])

    def test_joined_with_none_reads_lists_none_not_a_link(self):
        self.assertEqual(judge_disclosures.for_judge(self.cache, "200"), {"reports": 0})

    def test_a_disagreeing_surname_or_birth_year_gives_nothing(self):
        self.assertNotIn("300", self.cache["judges"])
        self.assertNotIn("400", self.cache["judges"])
        refused = " ".join(self.cache["refused"])
        self.assertIn("'Owen'", refused)
        self.assertIn("birth year of 1952, the directory 1951", refused)

    def test_an_alias_or_an_id_two_records_carry_gives_nothing(self):
        self.assertNotIn("500", self.cache["judges"])
        self.assertNotIn("600", self.cache["judges"])

    def test_a_judge_no_record_carries_is_said_nothing_of(self):
        self.assertIsNone(judge_disclosures.for_judge(self.cache, "800"))

    def test_a_short_file_is_refused(self):
        with self.assertRaisesRegex(judge_disclosures.JudgeDisclosuresError, "truncated"):
            judge_disclosures.fetch(DIRECTORY, read=reader(people=people_file(PEOPLE, pad=5)),
                                    today=TODAY, log=lambda *a: None)
        with self.assertRaisesRegex(judge_disclosures.JudgeDisclosuresError, "truncated"):
            judge_disclosures.fetch(DIRECTORY, read=reader(reports=reports_file(REPORTS, pad=5)),
                                    today=TODAY, log=lambda *a: None)

    def test_a_truncated_listing_is_refused(self):
        lists = (listing("people-db-people-2026-09-30.csv.bz2", truncated=True),
                 listing("financial-disclosures-2026-09-30.csv.bz2"))
        with self.assertRaisesRegex(judge_disclosures.JudgeDisclosuresError, "truncated"):
            judge_disclosures.fetch(DIRECTORY, read=reader(listings=lists), today=TODAY,
                                    log=lambda *a: None)

    def test_a_read_that_joins_far_fewer_is_refused(self):
        previous = {"judges": {str(i): {} for i in range(50)}}
        with self.assertRaisesRegex(judge_disclosures.JudgeDisclosuresError, "refused"):
            judge_disclosures.fetch(DIRECTORY, previous, read=reader(), today=TODAY,
                                    log=lambda *a: None)

    def test_the_build_warns_stale_refused_and_departed(self):
        codes = [p[1] for p in judge_disclosures.problems(self.cache, DIRECTORY, TODAY)]
        self.assertIn("judge-disclosures-refused", codes)
        self.assertNotIn("judge-disclosures-stale", codes)
        codes = [p[1] for p in judge_disclosures.problems(self.cache, DIRECTORY, "2027-06-01")]
        self.assertIn("judge-disclosures-stale", codes)
        gone = {k: v for k, v in DIRECTORY.items() if k != "fjc-100"}
        codes = [p[1] for p in judge_disclosures.problems(self.cache, gone, TODAY)]
        self.assertIn("judge-disclosures-unsitting", codes)
        codes = [p[1] for p in judge_disclosures.problems(None, DIRECTORY, TODAY)]
        self.assertEqual(codes, ["judge-disclosures-unread"])

    def test_the_judges_record_carries_it_to_the_page(self):
        record = {"id": "fjc-100", "name": "Jane Smith", "status": "active", "seats": []}
        self.assertEqual(federal_build._judge(record, None, self.cache)["disclosures"]["reports"], 3)
        self.assertEqual(federal_build._judge(dict(record, id="fjc-200"), None,
                                              self.cache)["disclosures"], {"reports": 0})
        self.assertNotIn("disclosures", federal_build._judge(dict(record, id="fjc-800"), None,
                                                             self.cache))


class TestTheCommittedReads(unittest.TestCase):
    """The committed caches pass their own checks (no error)."""

    def test_no_errors(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        from kyc import judiciary
        directory = judiciary.load_cache(root)
        held = judge_disclosures.load_cache(root)
        if directory is None or held is None:
            self.skipTest("no committed caches")
        self.assertFalse([p for p in judge_disclosures.problems(held, directory["judges"])
                          if p[0] == "error"])
        self.assertFalse([p for p in court_chiefs.problems(directory) if p[0] == "error"])


if __name__ == "__main__":
    unittest.main()
