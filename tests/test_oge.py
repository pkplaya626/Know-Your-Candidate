"""Financial disclosures from the Office of Government Ethics (kyc/oge.py):
attributed by office, never by a name alone, and each report OGE generates
checked against the filer it names.

The index rows below are copied from OGE's API as read on 2026-10-16."""

import os
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import federal_offices, oge  # noqa: E402

FILE = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/{}/$FILE/{}.pdf"


def row(name, agency, title, date, label, unid=None):
    if unid:
        cell = f"<a href='{FILE.format(unid, 'report')}'>{label}</a>"
    else:
        cell = (f"{label} (<a href='https:\\/\\/extapps2.oge.gov\\/201\\/Presiden.nsf\\/201%20Request"
                f"?OpenForm&Filer=X'>Request this Document</a>)")
    return {"type": cell, "name": name, "agency": agency, "title": title,
            "level": "n/a", "docDate": date + "T04:30:00", "amended": ""}


U = lambda n: f"{n:032X}"  # noqa: E731

BLANCHE = [
    row("Blanche, Todd", "Department of Justice", "Deputy Attorney General", "2025-02-13",
        "Nominee 278", U(1)),
    row("Blanche, Todd", "Department of Justice", "Deputy Attorney General", "2026-09-15",
        "Annual (2026)", U(2)),
    row("Blanche, Todd", "Department of Justice", "Attorney General", "2026-07-03",
        "Ethics Agreement", U(3)),
    row("Blanche, Todd", "Department of Justice", "Attorney General", "2026-07-03",
        "Nominee 278", U(4)),
    row("Blanche, Robert", "Department of Energy", "Secretary", "2001-01-01", "Annual (2001)", U(5)),
]
VOUGHT = [
    row("Vought, Russell", "Office of Management and Budget", "Director 2", "2026-08-06",
        "Annual (2026)", U(6)),
    row("Vought, Russell", "Office of Management and Budget", "Director 2", "2025-07-01",
        "278 Transaction", U(7)),
    row("Vought, Russell", "Office of Management and Budget", "Director 2", "2025-09-01",
        "278 Transaction", U(8)),
    row("Vought, Russell", "Office of Management and Budget", "Director 2", "2025-10-01",
        "278 Transaction"),
]


def report(*strings):
    """A PDF as OGE's filing system draws one: literal strings in a
    Flate-compressed content stream."""
    body = "\n".join(f"({s})Tj\n0 0 Td" for s in strings).encode("latin-1")
    stream = zlib.compress(body)
    return b"%PDF-1.4\n1 0 obj<</Filter/FlateDecode>>stream\n" + stream + b"\nendstream\nendobj\n"


class TestTheIndex(unittest.TestCase):
    def test_a_file_is_linked_and_a_request_is_counted(self):
        filed = oge.document(BLANCHE[1])
        self.assertEqual((filed["kind"], filed["year"], filed["request"]), ("annual", 2026, False))
        self.assertTrue(filed["url"].startswith("https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/"))
        asked = oge.document(VOUGHT[3])
        # The request form is never linked as though it were the report.
        self.assertEqual((asked["kind"], asked["url"], asked["request"]), ("transaction", None, True))
        self.assertEqual(asked["label"], "278 Transaction")

    def test_a_link_to_anywhere_else_is_not_a_report(self):
        odd = dict(BLANCHE[1], type="<a href='https://example.com/x.pdf'>Annual (2026)</a>")
        self.assertIsNone(oge.document(odd)["url"])

    def test_an_amended_report_says_so(self):
        amended = dict(BLANCHE[0], type=f"<a href='{FILE.format(U(9), 'x')}'>Nominee 278</a> (Amended 02/01/2025)")
        doc = oge.document(amended)
        self.assertTrue(doc["amended"])
        self.assertEqual(doc["kind"], "nominee")


class TestWhoseRowsTheyAre(unittest.TestCase):
    def test_the_office_and_the_surname(self):
        filed, mine, other, trouble = oge.attribute(
            BLANCHE, ("Department of Justice", "Attorney General"), "Todd Blanche")
        self.assertEqual((filed, len(mine), trouble), ("Blanche, Todd", 2, []))
        # His annual report as Deputy Attorney General is his; Robert
        # Blanche at Energy, a different agency, is not.
        self.assertEqual({r["title"] for r in other}, {"Deputy Attorney General"})

    def test_case_and_ogEs_record_number(self):
        filed, mine, _other, _t = oge.attribute(
            [dict(r, agency="OFFICE OF MANAGEMENT AND BUDGET") for r in VOUGHT],
            ("Office of Management and Budget", "Director"), "Russ Vought")
        self.assertEqual((filed, len(mine)), ("Vought, Russell", 4))

    def test_two_people_of_one_surname_are_neither(self):
        rows = [row("Smith, Jane", "Department of Labor", "Secretary", "2025-01-01", "Nominee 278", U(10)),
                row("Smith, John", "Department of Labor", "Secretary", "2013-01-01", "Nominee 278", U(11))]
        filed, mine, _other, trouble = oge.attribute(rows, ("Department of Labor", "Secretary"), "Jane Smith")
        self.assertIsNone(filed)
        self.assertEqual(mine, [])
        self.assertTrue(trouble)

    def test_a_suffix_is_not_a_surname(self):
        self.assertEqual(oge.surname("Robert F. Kennedy, Jr."), "kennedy")
        self.assertEqual(oge.filed_surname("Kennedy Jr, Robert F"), "kennedy")


class TestTheReportNamesItsFiler(unittest.TestCase):
    def test_named(self):
        pdf = report("Filer's Information", "Rubio, Marco", " ", "Secretary, Department of State")
        self.assertEqual(oge.filer_named(pdf, "Rubio, Marco"), "named")

    def test_someone_else(self):
        pdf = report("Filer's Information", "Smith, John", "Secretary, Department of Labor")
        self.assertEqual(oge.filer_named(pdf, "Smith, Jane")[:5], "named")
        self.assertEqual(oge.filer_named(pdf, "Rubio, Marco"), "other: Smith, John")

    def test_a_scan_concludes_nothing(self):
        self.assertEqual(oge.filer_named(b"%PDF-1.4 no text", "Rubio, Marco"), "unreadable")
        self.assertEqual(oge.filer_named(None, "Rubio, Marco"), "unreadable")


class TestTheRead(unittest.TestCase):
    def test_every_row_or_none(self):
        pages = [{"recordsFiltered": 3, "data": VOUGHT[:2]}, {"recordsFiltered": 3, "data": VOUGHT[2:3]}]
        self.assertEqual(len(oge.search("Vought", read=lambda url: pages.pop(0))), 3)
        short = [{"recordsFiltered": 5, "data": VOUGHT[:2]}, {"recordsFiltered": 5, "data": []}]
        with self.assertRaises(oge.OGEError):
            oge.search("Vought", read=lambda url: short.pop(0))

    def test_a_report_naming_someone_else_is_not_linked_and_checks_are_kept(self):
        executive = {"president": {}, "vicePresident": {},
                     "offices": [{"key": "omb", "holder": {"name": "Russ Vought"}}]}
        opened = []

        def read_pdf(url):
            opened.append(url)
            if U(7) in url:
                return report("Filer's Information", "Someone, Else")
            return report("Filer's Information", "Vought, Russell")
        index = lambda url: {"recordsFiltered": len(VOUGHT), "data": VOUGHT}  # noqa: E731
        cache = oge.build(executive, read=index, read_pdf=read_pdf, today="2026-10-16")
        docs = cache["people"]["omb"]["documents"]
        self.assertNotIn(U(7), " ".join(d["url"] or "" for d in docs))
        self.assertTrue(any("names Someone, Else" in p for p in cache["problems"]))
        self.assertEqual(len(opened), 3)
        # A second read opens nothing it has read before.
        opened.clear()
        oge.build(executive, read=index, read_pdf=read_pdf, previous=cache, today="2026-10-17")
        self.assertEqual(opened, [FILE.format(U(7), "report")])


class TestWhatThePageIsGiven(unittest.TestCase):
    def test_the_latest_of_each_kind(self):
        person = {"holder": "Russ Vought", "filed": "Vought, Russell",
                  "agency": "Office of Management and Budget", "position": "Director",
                  "documents": sorted([dict(oge.document(r), title="Director", office=True,
                                            check="named") for r in VOUGHT],
                                      key=lambda d: d["date"], reverse=True)}
        page = oge.for_page(person)
        kinds = [d["kind"] for d in page["documents"]]
        self.assertEqual(kinds, ["annual", "transaction"])
        transaction = page["documents"][1]
        self.assertEqual((transaction["count"], transaction["date"]), (2, "2025-09-01"))
        self.assertEqual(page["documents"][0]["words"], "Annual report, 2026")
        self.assertEqual(page["onRequest"], 1)

    def test_a_report_under_another_post_says_which(self):
        person = {"holder": "Todd Blanche", "filed": "Blanche, Todd", "agency": "Department of Justice",
                  "position": "Attorney General",
                  "documents": [dict(oge.document(BLANCHE[1]), title="Deputy Attorney General",
                                     office=False, check="unreadable")]}
        doc = oge.for_page(person)["documents"][0]
        self.assertEqual(doc["as"], "Deputy Attorney General")
        self.assertTrue(doc["unchecked"])


class TestTheTables(unittest.TestCase):
    def test_every_office_has_ogEs_words(self):
        self.assertEqual(oge.check([o["key"] for o in federal_offices.OFFICES]), [])

    def test_a_new_holder_since_the_read_is_reported(self):
        cache = {"read": "2026-10-16", "problems": [], "people": {
            "omb": {"holder": "Russ Vought", "documents": []}}}
        executive = {"offices": [{"key": "omb", "holder": {"name": "Someone New"}}]}
        codes = {c for _l, c, _m, _d in oge.problems(cache, executive, today="2026-10-16")}
        self.assertIn("oge-stale", codes)


if __name__ == "__main__":
    unittest.main()
