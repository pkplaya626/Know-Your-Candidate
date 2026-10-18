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

ROOT = os.path.join(os.path.dirname(__file__), "..")

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

    def test_a_surname_of_several_words(self):
        rows = [row("De La Cruz, Monica", "Department of Labor", "Secretary", "2025-01-01",
                    "Nominee 278", U(12))]
        filed, mine, _o, _t = oge.attribute(rows, ("Department of Labor", "Secretary"),
                                            "Monica De La Cruz")
        self.assertEqual((filed, len(mine)), ("De La Cruz, Monica", 1))
        # "Cruz" alone is someone else's surname.
        self.assertEqual(oge.attribute(rows, ("Department of Labor", "Secretary"), "Ted Cruz")[0],
                         None)

    def test_a_suffix_is_not_a_surname(self):
        self.assertEqual(oge.surname("Robert F. Kennedy, Jr."), "kennedy")
        self.assertEqual(oge.filed_surname("Kennedy Jr, Robert F"), "kennedy")


class TestTheReportNamesItsFiler(unittest.TestCase):
    def test_named(self):
        pdf = report("Filer's Information", "Rubio, Marco", " ", "Secretary, Department of State")
        self.assertEqual(oge.filer_named(pdf, "Rubio, Marco"), "named")

    def test_someone_else(self):
        pdf = report("Filer's Information", "Smith, John", "Secretary, Department of Labor")
        # One surname is not one person: Jane Smith's row, John Smith's report.
        self.assertEqual(oge.filer_named(pdf, "Smith, Jane"), "other: Smith, John")
        self.assertEqual(oge.filer_named(pdf, "Rubio, Marco"), "other: Smith, John")

    def test_a_suffix_written_on_the_report(self):
        pdf = report("Filer's Information", "Kennedy Jr, Robert F")
        self.assertEqual(oge.filer_named(pdf, "Kennedy, Robert F"), "named")

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


class TestThisAdministration(unittest.TestCase):
    def test_a_report_from_an_earlier_tenure_is_not_the_officers_now(self):
        rows = VOUGHT + [row("Vought, Russell", "Office of Management and Budget", "Director",
                             "2021-02-03", "Termination", U(13))]
        executive = {"president": {"termStart": "2025-01-20"}, "vicePresident": {},
                     "offices": [{"key": "omb", "holder": {"name": "Russ Vought"}}]}
        cache = oge.build(executive, read=lambda url: {"recordsFiltered": len(rows), "data": rows},
                          read_pdf=lambda url: report("Filer's Information", "Vought, Russell"),
                          today="2026-10-16")
        kinds = {d["kind"] for d in cache["people"]["omb"]["documents"]}
        self.assertNotIn("termination", kinds)
        self.assertIn("annual", kinds)


class TestWhatThePageIsGiven(unittest.TestCase):
    def test_read_and_nothing_found_is_not_a_filing_by_no_one(self):
        empty = {"holder": "Pat Nobody", "filed": None, "agency": "Department of Labor",
                 "position": "Secretary", "documents": []}
        page = oge.for_page(empty)
        self.assertTrue(page["none"])
        self.assertNotIn("filed", page)
        self.assertTrue(oge.for_page(dict(empty, refused=True))["refused"])

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


def report(*strings):
    """A report's first page as OGE's generator draws it: each string a Tj."""
    body = b" ".join(b"(" + s.replace("(", "\\(").replace(")", "\\)").encode("latin-1") + b") Tj"
                     for s in strings)
    return b"stream\n" + zlib.compress(body) + b"\nendstream"


class TestOtherFederalPositions(unittest.TestCase):
    """FEDERAL-18: Keith Sonderling's record showed only Secretary of Labor;
    his own nomination report, linked beside it, lists the acting posts he
    held in the year before. They are quoted from the report, attributed,
    and never merged into the offices two sources agree on (rule 69)."""

    HEAD = ("Filer's Information", "Sonderling, Keith E", "", "Secretary, Department of Labor",
            "Other Federal Government Positions Held During the Preceding 12 Months:", "")

    def test_each_entry_is_read_with_its_dates_in_the_reports_words(self):
        data = report(*self.HEAD, "Acting Director, Institute of Museum and Library Services "
                      "(3/2025 - 11/2025)", "", "Acting Secretary of Labor, Department of Labor",
                      "(4/2026 - Present)", "Names of Congressional Committees Considering Nomination:")
        self.assertEqual(oge.other_positions(data), [
            "Acting Director, Institute of Museum and Library Services (3/2025 - 11/2025)",
            "Acting Secretary of Labor, Department of Labor (4/2026 - Present)"])

    def test_none_listed_is_an_empty_list_and_a_list_not_read_whole_is_nothing(self):
        self.assertEqual(oge.other_positions(report(*self.HEAD, "None", "Electronic Signature - x")), [])
        unread = report(*self.HEAD, "Acting Director, Somewhere", "Electronic Signature - x")
        self.assertIsNone(oge.other_positions(unread))
        self.assertIsNone(oge.other_positions(report("Filer's Information", "Doe, Jane")))
        self.assertIsNone(oge.other_positions(None))

    def test_only_a_report_that_names_its_filer_is_quoted(self):
        named = dict(oge.document(LABOR_NOMINEE), title="Secretary", office=True, check="named")
        other = dict(named, url=named["url"].replace("A", "B"), check="other: Someone, Else",
                     date="2026-09-01")
        person = {"holder": "Keith Sonderling", "filed": "Sonderling, Keith",
                  "agency": "Department of Labor", "position": "Secretary",
                  "documents": [other, named]}
        positions = {named["url"]: ["Acting Director, X (3/2025 - 11/2025)"],
                     other["url"]: ["Not his (1/2025 - 2/2025)"]}
        listed = oge.for_page(person, positions)["otherPositions"]
        self.assertEqual(listed["rows"], ["Acting Director, X (3/2025 - 11/2025)"])
        self.assertEqual(listed["url"], named["url"])
        unchecked = dict(person, documents=[dict(named, check="unreadable")])
        self.assertNotIn("otherPositions", oge.for_page(unchecked, positions))

    def test_the_office_held_now_is_not_another_post(self):
        # Sonderling, confirmed Secretary of Labor on 2026-09-30, read as
        # "Acting Secretary of Labor ... (4/2026 - Present)" under "Other
        # federal posts"; Mullin's "United States Senator, US Congress
        # (1/2023 - Present)" is another post, and stays - the page says
        # "Present" is the report's day.
        named = dict(oge.document(LABOR_NOMINEE), title="Secretary", office=True, check="named")
        person = {"holder": "Keith Sonderling", "filed": "Sonderling, Keith",
                  "agency": "Department of Labor", "position": "Secretary", "documents": [named]}
        rows = ["Acting Director, Office of Government Ethics (6/2026 - Present)",
                "Acting Secretary of Labor, Department of Labor (4/2026 - Present)",
                "United States Senator, US Congress (1/2023 - Present)"]
        listed = oge.for_page(person, {named["url"]: rows}, ("Secretary of Labor",))["otherPositions"]
        self.assertEqual(listed["rows"], [rows[0], rows[2]])
        self.assertFalse(oge.holds_now("Deputy Attorney General, Department of Justice (1/2025 - 4/2026)",
                                       ("Attorney General",)))
        self.assertTrue(oge.holds_now("Acting Attorney General, Department of Justice (4/2026 - Present)",
                                      ("Attorney General",)))

    def test_the_built_page_never_lists_the_office_held_now(self):
        try:
            from kyc import federal_build
            payload = federal_build.build(ROOT)[0]
        except Exception as exc:  # noqa: BLE001 - no caches committed
            self.skipTest(str(exc))
        for office in payload["offices"]:
            holder = office.get("holder") or {}
            listed = (holder.get("disclosures") or {}).get("otherPositions") or {}
            for row in listed.get("rows") or []:
                self.assertFalse(oge.holds_now(row, (office["office"], holder.get("title"))), row)


LABOR_NOMINEE = row("Sonderling, Keith", "Department of Labor", "Secretary", "2026-07-17",
                    "Nominee 278", U(41))


class TestTheTables(unittest.TestCase):
    def test_every_office_has_ogEs_words(self):
        self.assertEqual(oge.check([o["key"] for o in federal_offices.OFFICES]), [])

    def test_a_new_holder_since_the_read_is_reported(self):
        cache = {"read": "2026-10-16", "problems": [], "people": {
            "omb": {"holder": "Russ Vought", "documents": []}}}
        executive = {"offices": [{"key": "omb", "holder": {"name": "Someone New"}}]}
        codes = {c for _l, c, _m, _d in oge.problems(cache, executive, today="2026-10-16")}
        self.assertIn("oge-stale", codes)

    def test_an_office_never_read_is_reported(self):
        cache = {"read": "2026-10-16", "problems": [], "people": {}}
        executive = {"offices": [{"key": "un", "holder": {"name": "Michael Waltz"}}]}
        found = [d for _l, c, _m, d in oge.problems(cache, executive, today="2026-10-16")
                 if c == "oge-stale"]
        self.assertEqual(found, [["un: Michael Waltz (not read)"]])


if __name__ == "__main__":
    unittest.main()
