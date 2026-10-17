"""The federal judiciary: sitting judges from the Federal Judicial Center's
directory, and the Supreme Court as the Court lists it (kyc/judiciary.py,
kyc/federal_courts.py).

Fixtures are the real directory's rows for the Supreme Court and a few
judges chosen for their edge cases, and the Court's own page, as read on
2026-10-16."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import federal_courts, judiciary  # noqa: E402

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures", "judiciary")
ROOT = os.path.join(HERE, "..")
TODAY = "2026-10-16"


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as handle:
        return handle.read()


class TestTheCourtTable(unittest.TestCase):
    def test_it_is_sound(self):
        # 1 Supreme Court, 13 courts of appeals, 91 Article III district
        # courts, 3 territorial ones, the Court of International Trade; every
        # state and territory but American Samoa in exactly one circuit.
        self.assertEqual(federal_courts.check(), [])

    def test_ids_and_names(self):
        self.assertEqual(federal_courts.fjc_name("tx-s"),
                         "U.S. District Court for the Southern District of Texas")
        self.assertIsNone(federal_courts.fjc_name("gu"))
        self.assertEqual(federal_courts.COURTS["mp"]["circuit"], "9")   # 48 U.S.C. 1821


class TestTheDirectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = judiciary.build(fixture("federal-judicial-service.csv"),
                                    fixture("judges.csv"), fixture("members.html"), TODAY)
        cls.judges = cls.cache["judges"]

    def test_the_supreme_court_is_the_courts_nine(self):
        scotus = self.cache["courts"]["scotus"]
        self.assertEqual(len(scotus["judges"]), 9)
        self.assertEqual(self.judges[scotus["chief"]]["justice"]["role"], "Chief Justice")
        self.assertEqual(scotus["judges"][0], scotus["chief"])

    def test_retired_justices_are_never_members(self):
        scotus = self.cache["courts"]["scotus"]
        self.assertEqual(len(scotus["retired"]), 2)
        self.assertFalse(set(scotus["retired"]) & set(scotus["judges"]))
        self.assertTrue(all(self.judges[i].get("retiredJustice") for i in scotus["retired"]))

    def test_a_confirmed_judge_without_a_commission_is_not_sitting(self):
        self.assertTrue(any("not yet commissioned" in p for p in self.cache["pending"]))
        self.assertFalse(any(j["name"].startswith("Angela") and "Colmenero" in j["name"]
                             for j in self.judges.values()))

    def test_a_judge_on_several_courts_is_one_person(self):
        roving = self.judges["fjc-8307871"]
        self.assertGreater(len(roving["seats"]), 1)
        self.assertEqual(len({s["court"] for s in roving["seats"]}), len(roving["seats"]))

    def test_a_judge_who_died_is_not_sitting(self):
        self.assertNotIn("fjc-1376976", self.judges)

    def test_a_chief_and_senior_status_come_from_the_rows(self):
        first = self.cache["courts"]["ca1"]
        self.assertEqual(first["chief"], "fjc-1394531")
        self.assertEqual(self.judges["fjc-1378781"]["status"], "senior")
        self.assertEqual(first["judges"][0], first["chief"])

    def test_earlier_service_is_kept_as_prior(self):
        elevated = self.judges["fjc-1377266"]
        self.assertTrue(any(p["how"] == "Appointment to Another Judicial Position"
                            for p in elevated["prior"]))

    def test_no_judge_carries_a_party_gender_or_race(self):
        text = json.dumps(self.judges)
        for word in ("party", "Party", "gender", "Gender", "Race or Ethnicity"):
            self.assertNotIn(f'"{word}"', text)
        self.assertEqual([p for p in judiciary.problems(self.cache, TODAY)
                          if p[0] == "error"], [])

    def test_the_fjc_link_is_built_from_the_id(self):
        kagan = next(j for j in self.judges.values() if j["name"] == "Elena Kagan")
        self.assertEqual(kagan["fjc"], "https://www.fjc.gov/node/1393281")
        self.assertEqual(kagan["seats"][0]["appointedBy"], "Barack Obama")


def service_row(**fields):
    """One row of the FJC's service file, with only what a test sets."""
    row = {"nid": "1", "Judge Name": "Doe, Jane",
           "Court Name": "U.S. Court of Appeals for the Eleventh Circuit",
           "Appointment Title": "Judge", "Appointing President": "Gerald Ford",
           "Nomination Date": "", "Confirmation Date": "", "Commission Date": "1975-11-21",
           "Senior Status Date": "", "Termination Date": "", "Termination": "",
           "Senate Vote Type": "", "Ayes/Nays": "", "Seat ID": "X",
           "Service as Chief Judge, Begin": "", "Service as Chief Judge, End": "",
           "2nd Service as Chief Judge, Begin": "", "2nd Service as Chief Judge, End": ""}
    row.update(fields)
    return row


class TestRecordsThatNeedReading(unittest.TestCase):
    def test_a_chief_on_senior_status_is_not_shown_as_chief(self):
        # Catherine Eagles's row: chief of the Middle District of North
        # Carolina since 2023 with no end, and senior since 2024-12-31. A
        # chief must be in regular active service (28 U.S.C. 136(a)).
        row = service_row(**{
            "Court Name": "U.S. District Court for the Middle District of North Carolina",
            "Commission Date": "2010-01-01", "Senior Status Date": "2024-12-31",
            "Service as Chief Judge, Begin": "2023"})
        judges, _pending, _problems, conflicts = judiciary.sitting([row], {}, TODAY)
        seat = judges["1"]["seats"][0]
        self.assertIsNone(seat["chiefSince"])
        self.assertTrue(seat["chiefUnsettled"])
        self.assertEqual(len(conflicts), 1)

    def test_a_reassignment_carries_the_appointment(self):
        # Gerald Tjoflat: commissioned to the Fifth Circuit in 1975 and
        # reassigned by statute to the Eleventh when it was created in 1981.
        rows = [service_row(**{"Court Name": "U.S. Court of Appeals for the Fifth Circuit",
                               "Termination Date": "1981-10-01", "Termination": "Reassignment",
                               "Nomination Date": "1975-11-03"}),
                service_row(**{"Appointing President": "None (reassignment)",
                               "Commission Date": "1981-10-01"})]
        judges, _pending, _problems, conflicts = judiciary.sitting(rows, {}, TODAY)
        seat = judges["1"]["seats"][0]
        self.assertEqual((seat["court"], seat["appointedBy"], seat["commissioned"],
                          seat["nominated"], seat["reassigned"]),
                         ("ca11", "Gerald Ford", "1975-11-21", "1975-11-03", "1981-10-01"))
        self.assertEqual(conflicts, [])

    def test_the_committed_cache_names_every_appointing_president(self):
        cache = judiciary.load_cache(ROOT)
        if cache is None:
            self.skipTest("no judiciary cache committed")
        self.assertEqual([j["name"] for j in cache["judges"].values()
                          if not all(s.get("appointedBy") for s in j["seats"])], [])
        # Nobody is a court's chief while on senior status.
        for cid, court in cache["courts"].items():
            chief = cache["judges"].get(court.get("chief") or "")
            if chief and cid != "scotus":
                seat = next(s for s in chief["seats"] if s["court"] == cid)
                self.assertIsNone(seat["seniorSince"], cid)


class TestTheJusticesPortraits(unittest.TestCase):
    """The Court's own portraits, joined only to the nine justices already
    joined to the directory: the page pictures retired justices too."""

    def build(self, page, image_ok=lambda url: True):
        return judiciary.build(fixture("federal-judicial-service.csv"), fixture("judges.csv"),
                               fixture("members.html"), TODAY, page, image_ok)

    def test_each_justice_has_their_own_portrait(self):
        cache = self.build(fixture("biographies.html"))
        members = cache["courts"]["scotus"]["judges"]
        urls = [cache["judges"][j]["portrait"]["url"] for j in members]
        self.assertEqual(len(set(urls)), 9)
        roberts = cache["judges"][cache["courts"]["scotus"]["chief"]]["portrait"]
        self.assertTrue(roberts["url"].endswith("justice_pictures/Roberts_8807-16_Crop.jpg"))
        self.assertTrue(any(u.endswith("Kavanaugh%2012221_005_crop.jpg") for u in urls))
        for jid in cache["courts"]["scotus"]["retired"]:
            self.assertNotIn("portrait", cache["judges"][jid])
        self.assertEqual(cache["portraitProblems"], [])

    def test_a_title_that_disagrees_with_the_role_shows_none(self):
        page = fixture("biographies.html").replace(
            "John G. Roberts, Chief Justice of the United States",
            "John G. Roberts, Associate Justice")
        cache = self.build(page)
        self.assertFalse(any("portrait" in j for j in cache["judges"].values()))
        self.assertIn("justice-portraits", [p[1] for p in judiciary.problems(cache, TODAY)])

    def test_a_missing_picture_shows_none(self):
        cache = self.build(fixture("biographies.html").replace("Clarence Thomas,", "Someone Else,"))
        self.assertFalse(any("portrait" in j for j in cache["judges"].values()))

    def test_a_portrait_that_does_not_load_shows_none_and_an_unread_check_concludes_nothing(self):
        broken = self.build(fixture("biographies.html"), image_ok=lambda url: "Thomas" not in url)
        self.assertFalse(any("portrait" in j for j in broken["judges"].values()))
        unread = self.build(fixture("biographies.html"), image_ok=lambda url: None)
        self.assertEqual(sum(1 for j in unread["judges"].values() if "portrait" in j), 9)


class TestWhatIsRefused(unittest.TestCase):
    def test_a_court_the_table_does_not_know(self):
        text = fixture("federal-judicial-service.csv").replace(
            "U.S. Court of Appeals for the First Circuit", "U.S. Court of Appeals for the Twelfth Circuit")
        with self.assertRaises(judiciary.JudiciaryError):
            judiciary.build(text, fixture("judges.csv"), fixture("members.html"), TODAY)

    def test_a_justice_the_directory_cannot_place(self):
        page = fixture("members.html").replace("Kagan, Elena", "Doe, Jane")
        with self.assertRaises(judiciary.JudiciaryError):
            judiciary.build(fixture("federal-judicial-service.csv"), fixture("judges.csv"),
                            page, TODAY)

    def test_a_date_in_another_format(self):
        text = fixture("federal-judicial-service.csv").replace("2010-08-06", "08/06/2010")
        with self.assertRaises(judiciary.JudiciaryError):
            judiciary.build(text, fixture("judges.csv"), fixture("members.html"), TODAY)

    def test_a_truncated_read(self):
        def read(url):
            return {judiciary.SERVICE_URL: fixture("federal-judicial-service.csv"),
                    judiciary.JUDGES_URL: fixture("judges.csv"),
                    judiciary.SCOTUS_URL: fixture("members.html"),
                    judiciary.PORTRAITS_URL: fixture("biographies.html")}[url]
        previous = {"judges": {f"fjc-{n}": {} for n in range(1000)}}
        with self.assertRaises(judiciary.JudiciaryError):
            judiciary.fetch(previous=previous, today=TODAY, read=read)


class TestTheCommittedCache(unittest.TestCase):
    def test_it_is_whole(self):
        cache = judiciary.load_cache(ROOT)
        if cache is None:
            self.skipTest("no judiciary cache committed")
        self.assertEqual(set(cache["courts"]), set(federal_courts.COURTS))
        self.assertEqual([p for p in judiciary.problems(cache) if p[0] == "error"], [])
        # Every Article III court has its judges; the territorial courts are
        # listed without them, and say why.
        for cid, court in cache["courts"].items():
            if federal_courts.COURTS[cid]["kind"] == "territorial":
                self.assertFalse(court["listed"])
            else:
                self.assertTrue(court["listed"] and court["judges"], cid)


class TestNamesAJudgeGoesBy(unittest.TestCase):
    def test_a_bracketed_given_name_is_shown_as_its_initial(self):
        self.assertEqual(judiciary.display_name("A[llen] Joe Fish"), "A. Joe Fish")
        self.assertEqual(judiciary.full_name("A[llen] Joe Fish"), "Allen Joe Fish")
        self.assertEqual(judiciary.display_name("R[obert] Lanier Anderson, III"),
                         "R. Lanier Anderson, III")

    def test_a_plain_name_is_unchanged(self):
        self.assertEqual(judiciary.display_name("John G. Roberts, Jr."), "John G. Roberts, Jr.")
        self.assertIsNone(judiciary.full_name("John G. Roberts, Jr."))
        self.assertEqual(judiciary.display_name(None), "")


if __name__ == "__main__":
    unittest.main()
