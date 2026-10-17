"""Vacancies in the federal courts, as the courts list them on uscourts.gov
(kyc/vacancies.py).

Fixtures are the three lists' tables, and the current list's summary, as
read on 2026-10-16."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import vacancies  # noqa: E402

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures", "vacancies")
ROOT = os.path.join(HERE, "..")
TODAY = "2026-10-16"


def fixture(name):
    with open(os.path.join(FIX, f"{name}.html"), encoding="utf-8") as handle:
        return handle.read()


def build(current=None, future=None, emergencies=None):
    return vacancies.build(current or fixture("current"), future or fixture("future"),
                           emergencies or fixture("emergencies"), TODAY)


class TestTheLists(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = build()

    def test_the_rows_add_up_to_the_lists_own_totals(self):
        self.assertEqual(self.cache["asOf"], "2026-10-16")
        self.assertEqual(len(self.cache["current"]), self.cache["totals"]["vacancies"])
        self.assertEqual(sum(1 for r in self.cache["current"] if r["nominee"]),
                         self.cache["totals"]["nominees"])

    def test_every_row_is_placed_by_its_code(self):
        self.assertEqual(self.cache["unplaced"], [])
        by_code = {r["code"]: r["court"] for r in self.cache["current"] + self.cache["future"]}
        self.assertEqual(by_code["02 - NY-S"], "ny-s")
        self.assertEqual(by_code["05 - CCA"], "ca5")
        self.assertEqual(by_code["09 - AK"], "ak")

    def test_dates_are_read_whole_and_tbd_is_none(self):
        engelhardt = next(r for r in self.cache["future"]
                          if r["vacatedBy"]["listedAs"] == "Engelhardt,Kurt D.")
        self.assertEqual((engelhardt["announced"], engelhardt["vacancyDate"],
                          engelhardt["nominated"]), ("2026-06-09", None, "2026-07-14"))

    def test_an_emergency_is_a_current_vacancy_the_courts_designate(self):
        self.assertEqual(self.cache["emergenciesUnmatched"], [])
        flagged = {r["vacatedBy"]["listedAs"] for r in self.cache["current"] if r.get("emergency")}
        self.assertIn("Hayes,William Q.", flagged)
        self.assertNotIn("Gorton,Nathaniel M.", flagged)


class TestCodesAndNames(unittest.TestCase):
    def test_court_codes(self):
        self.assertEqual(vacancies.court_of("01 - MA"), "ma")
        self.assertEqual(vacancies.court_of("05 - TX-S"), "tx-s")
        self.assertEqual(vacancies.court_of("DC - CCA"), "cadc")
        self.assertEqual(vacancies.court_of("FED - CCA"), "cafc")
        self.assertEqual(vacancies.court_of("DC - DC"), "dc")
        self.assertEqual(vacancies.court_of("09 - GU"), "gu")
        # A court the circuit does not hold, or one the table does not know.
        self.assertIsNone(vacancies.court_of("02 - TX-S"))
        self.assertIsNone(vacancies.court_of("FED - CL"))
        self.assertIsNone(vacancies.court_of("Texas"))

    def test_names_in_reading_order(self):
        self.assertEqual(vacancies.reading_name("Gorton,Nathaniel M."), "Nathaniel M. Gorton")
        self.assertEqual(vacancies.reading_name("Long,Jr.,Robert E."), "Robert E. Long, Jr.")
        self.assertEqual(vacancies.reading_name("Batten Sr.,Timothy C."), "Timothy C. Batten Sr.")
        self.assertEqual(vacancies.reading_name("St. John,Anna"), "Anna St. John")


class TestWhatIsRefused(unittest.TestCase):
    def test_a_table_that_does_not_add_up(self):
        page = fixture("current").replace("Total Vacancies: 28", "Total Vacancies: 29")
        with self.assertRaises(vacancies.VacanciesError):
            build(current=page)

    def test_a_date_in_another_format(self):
        page = fixture("current").replace("05/31/2025", "2025-05-31")
        with self.assertRaises(vacancies.VacanciesError):
            build(current=page)

    def test_a_page_with_no_table(self):
        with self.assertRaises(vacancies.VacanciesError):
            build(future="<html><body>Access denied</body></html>")

    def test_an_unknown_code_is_kept_and_reported(self):
        page = fixture("future").replace("04 -  NC-E", "FED -  CL", 1)
        cache = build(future=page)
        self.assertEqual(cache["unplaced"], ["FED - CL"])
        self.assertIn("vacancy-court-unknown",
                      [code for _l, code, _m, _d in vacancies.problems(cache, TODAY)])


class TestAgainstTheDirectory(unittest.TestCase):
    def test_a_senior_vacancy_whose_judge_is_not_senior_is_reported(self):
        cache = build()
        judiciary = {"judges": {"fjc-1": {"sortName": "Gorton, Nathaniel",
                                          "seats": [{"court": "ma", "seniorSince": "2025-05-31"}]}}}
        judiciary["judges"]["fjc-2"] = {"sortName": "Saylor, F. Dennis",
                                        "seats": [{"court": "ma"}]}
        found = {code: detail for _l, code, _m, detail in vacancies.problems(cache, TODAY, judiciary)}
        self.assertNotIn("01 - MA: Nathaniel M. Gorton", found["vacancy-judge-not-senior"])
        self.assertIn("01 - MA: F. Dennis Saylor", found["vacancy-judge-not-senior"])
        self.assertNotIn("01 - MA: F. Dennis Saylor", found.get("vacancy-judge-not-listed", []))

    def test_a_senior_vacancy_whose_judge_the_directory_lists_nowhere_is_reported_apart(self):
        """Browning (NM) and Proctor (AL-N): 'Took senior status' on the
        courts' list, and not on their court in the directory at all."""
        cache = build()
        judiciary = {"judges": {"fjc-1": {"sortName": "Gorton, Nathaniel",
                                          "seats": [{"court": "ma", "seniorSince": "2025-05-31"}]}}}
        found = {code: detail for _l, code, _m, detail in vacancies.problems(cache, TODAY, judiciary)}
        self.assertIn("01 - MA: F. Dennis Saylor", found["vacancy-judge-not-listed"])
        self.assertNotIn("01 - MA: F. Dennis Saylor", found.get("vacancy-judge-not-senior", []))

    def test_a_generational_suffix_does_not_hide_a_judge(self):
        """The list writes "Osteen Jr.,William L."; the directory "Osteen,
        William": the same surname, so he is not reported missing."""
        judges = {"fjc-1": {"sortName": "Osteen, William", "seats": [{"court": "nc-m"}]}}
        row = {"court": "nc-m", "reason": "Senior",
               "vacatedBy": {"listedAs": "Osteen Jr.,William L.", "name": "William L. Osteen Jr."}}
        self.assertEqual(len(vacancies.seats_held(row, judges)), 1)
        self.assertFalse(vacancies.judge_unlisted(row, judges, future=True))
        self.assertTrue(vacancies.judge_unlisted(dict(row, court="ne"), judges, future=True))

    def test_only_a_reason_that_leaves_the_judge_serving_is_checked(self):
        """A judge who died, retired or was elevated is expected to be gone."""
        row = {"court": "ma", "reason": "Deceased",
               "vacatedBy": {"listedAs": "Nobody,A.", "name": "A. Nobody"}}
        self.assertFalse(vacancies.judge_unlisted(row, {}))
        self.assertTrue(vacancies.judge_unlisted(dict(row, reason="Senior"), {}))
        self.assertTrue(vacancies.judge_unlisted(row, {}, future=True))
        self.assertFalse(vacancies.judge_unlisted(dict(row, vacatedBy=None, reason="Senior"), {}))


class TestTheCommittedCache(unittest.TestCase):
    def test_it_is_whole(self):
        cache = vacancies.load_cache(ROOT)
        if cache is None:
            self.skipTest("no vacancy cache committed")
        self.assertEqual(len(cache["current"]), cache["totals"]["vacancies"])
        self.assertEqual([p for p in vacancies.problems(cache, cache["read"]) if p[0] == "error"], [])


if __name__ == "__main__":
    unittest.main()
