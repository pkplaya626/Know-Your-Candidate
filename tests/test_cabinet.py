"""Who has held each Cabinet office since the term began (kyc/cabinet.py):
confirmations from the Senate, holders from Wikidata, dates only where
Wikidata and the person's own Wikipedia infobox agree.

The infobox text below is copied from the articles as read on 2026-10-16,
trimmed to the fields read."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import cabinet, federal_offices  # noqa: E402

BONDI = """{{Infobox officeholder
| name               = Pam Bondi
| office             = 87th [[United States Attorney General]]
| term_start         = February 5, 2025
| term_end           = April 2, 2026
| predecessor        = [[Merrick Garland]]
| successor          = [[Todd Blanche]]
| order1             = 37th [[Florida Attorney General]]
| term_start1        = January 4, 2011
| term_end1          = January 8, 2019
}}
'''Pamela Jo Bondi''' is an American lawyer."""

BLANCHE = """{{Infobox officeholder
| order              = 88th
| office             = United States Attorney General
| term_start         = April 2, 2026{{efn|Acting: April 2, 2026 – August 10, 2026}}
| term_end           =
| office1            = United States Deputy Attorney General
| term_start1        = March 6, 2025
| term_end1          = August 10, 2026
}}"""

VOUGHT = """{{Infobox officeholder
| office       = 42nd and 44th Director of the [[Office of Management and Budget]]
| term_start   = February 7, 2025
| term_end     =
| term_start1  = January 2, 2019{{efn|Acting: January 2, 2019 – July 22, 2020}}
| term_end1    = January 20, 2021
| office5      = Deputy Director of the [[Office of Management and Budget]]
| term_start5  = March 14, 2018
| term_end5    = July 22, 2020
}}"""

HEGSETH = """{{Infobox officeholder
| office             = 29th [[United States Secretary of Defense]]{{efn|Also known as '''Secretary of War''' following an [[executive order]] {{lang|en|of 2025}}.}}
| term_start         = January 25, 2025
| term_end           =
}}"""

SALESSES = """{{Infobox officeholder
| office2             = Acting [[United States Secretary of Defense]]
| term_start2         = January 20, 2025
| term_end2           = January 25, 2025
}}"""

SINCE = "2025-01-20"


def vote(nominee, office, date, yeas=50, nays=49, number=1):
    return {"question": "On the Nomination", "result": "Confirmed",
            "title": f"Confirmation: {nominee}, of Florida, to be {office}",
            "date": date, "yeas": str(yeas), "nays": str(nays), "congress": "119",
            "session": "1" if date < "2026" else "2", "number": str(number), "issue": "PN1"}


def day(date):
    return {"date": date, "precision": "day"}


class TestTheInfobox(unittest.TestCase):
    def test_dates_in_every_form(self):
        self.assertEqual(cabinet.parse_date("February 5, 2025"), day("2025-02-05"))
        self.assertEqual(cabinet.parse_date("5 February 2025"), day("2025-02-05"))
        self.assertEqual(cabinet.parse_date("June 2026"), {"date": "2026-06", "precision": "month"})
        self.assertEqual(cabinet.parse_date("{{start date|2025|2|5}}"), day("2025-02-05"))
        self.assertEqual(cabinet.parse_date("April 2, 2026{{efn|Acting: April 2, 2026}}"),
                         day("2026-04-02"))
        self.assertIsNone(cabinet.parse_date(""))

    def test_the_office_is_matched_exactly_never_contained(self):
        names = ["Director of the Office of Management and Budget"]
        terms = cabinet.office_terms(cabinet.infobox(VOUGHT), names)
        # "Deputy Director of the ..." is not its Director.
        self.assertEqual([t["start"] for t in terms], [day("2025-02-07")])

    def test_an_ordinal_a_footnote_and_acting_are_read_past(self):
        defense = ["United States Secretary of Defense"]
        self.assertEqual(cabinet.office_terms(cabinet.infobox(HEGSETH), defense)[0]["start"],
                         day("2025-01-25"))
        acting = cabinet.office_terms(cabinet.infobox(SALESSES), defense)[0]
        self.assertTrue(acting["acting"])
        blanche = cabinet.office_terms(cabinet.infobox(BLANCHE), ["United States Attorney General"])
        self.assertEqual(blanche[0]["actingNote"], "Acting: April 2, 2026 – August 10, 2026")

    def test_dates_are_shown_only_as_far_as_the_sources_agree(self):
        self.assertEqual(cabinet.agree(day("2025-02-05"), day("2025-02-05")), day("2025-02-05"))
        self.assertEqual(cabinet.agree(day("2026-06-30"), day("2026-06-19")),
                         {"date": "2026-06", "precision": "month"})
        # Hegseth: Wikidata 2025-09-05, his article January 25, 2025.
        self.assertEqual(cabinet.agree(day("2025-09-05"), day("2025-01-25")),
                         {"date": "2025", "precision": "year"})
        self.assertIsNone(cabinet.agree(day("2025-09-05"), day("2024-01-25")))
        self.assertIsNone(cabinet.agree(day("2025-09-05"), None))


class TestTheHistory(unittest.TestCase):
    def build(self, holders, votes, texts, current="Todd Blanche"):
        executive = {"president": {"termStart": SINCE},
                     "offices": [{"key": "justice", "holder": {"name": current}}]}
        justice = next(o for o in federal_offices.OFFICES if o["key"] == "justice")
        return cabinet.build(executive, votes, {justice["wikidata"]: {
            "title": "United States Attorney General", "holders": holders}}, texts)["justice"]

    def holder(self, q, title, start, end=None):
        return {"wikidata": q, "title": title, "start": day(start), "end": end and day(end),
                "open": end is None}

    def test_who_was_confirmed_who_left_and_who_holds_it(self):
        out = self.build(
            {"Q1": self.holder("Q1", "Pam Bondi", "2025-02-05", "2026-04-02"),
             "Q2": self.holder("Q2", "Todd Blanche", "2026-08-08")},
            [vote("Pamela Jo Bondi", "Attorney General", "2025-02-04", 54, 46),
             vote("Todd Blanche", "Attorney General", "2026-08-08", number=230),
             vote("Someone Else", "Deputy Attorney General", "2025-03-05")],
            {"Pam Bondi": BONDI, "Todd Blanche": BLANCHE})
        bondi, blanche = out["holders"]
        # The common name is the article's; the Senate's rides with the vote.
        self.assertEqual((bondi["name"], bondi["confirmed"]["nominee"]), ("Pam Bondi", "Pamela Jo Bondi"))
        self.assertEqual(bondi["end"]["shown"], day("2026-04-02"))
        self.assertFalse(bondi["current"])
        self.assertTrue(blanche["current"])
        # Wikidata 2026-08-08 (his confirmation), his article April 2, 2026.
        self.assertEqual(blanche["start"]["shown"], {"date": "2026", "precision": "year"})
        self.assertEqual(out["problems"], [])

    def test_a_deputys_confirmation_is_not_the_offices(self):
        out = self.build({"Q2": self.holder("Q2", "Todd Blanche", "2026-08-08")},
                         [vote("Todd Blanche", "Deputy Attorney General", "2025-03-05")],
                         {"Todd Blanche": BLANCHE})
        self.assertIsNone(out["holders"][0]["confirmed"])

    def test_a_confirmation_wikidata_lacks_is_listed_and_reported(self):
        out = self.build({}, [vote("Pamela Jo Bondi", "Attorney General", "2025-02-04")], {},
                         current="Pam Bondi")
        self.assertEqual(out["holders"][0]["name"], "Pamela Jo Bondi")
        self.assertTrue(out["problems"])

    def test_an_open_holder_who_is_not_the_white_houses_is_reported(self):
        out = self.build({"Q1": self.holder("Q1", "Pam Bondi", "2025-02-05")},
                         [vote("Pamela Jo Bondi", "Attorney General", "2025-02-04")],
                         {"Pam Bondi": BONDI}, current="Todd Blanche")
        self.assertTrue(any("White House lists Todd Blanche" in p for p in out["problems"]))
        self.assertFalse(out["holders"][0]["current"])


class TestTheOfficeTable(unittest.TestCase):
    def test_every_office_has_its_own_item(self):
        self.assertEqual(federal_offices.check(), [])
        items = [o["wikidata"] for o in federal_offices.OFFICES]
        self.assertEqual(len(items), len(set(items)))


if __name__ == "__main__":
    unittest.main()
