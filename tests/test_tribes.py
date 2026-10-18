"""The BIA's Tribal Leaders Directory as the guide's tribal map reads it
(kyc/tribes.py): every row once, each placed in the state of its office,
a band under its tribe only by the directory's own names (GUIDE-18)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import government_maps, tribes  # noqa: E402


def row(oid, name, component="Tribe", state="Nevada", mailing=None, first="Ann", last="Lee",
        title="Chairman", gid=None, **extra):
    out = {"OBJECTID": oid, "GlobalID": gid or "{%08d-0000-0000-0000-000000000000}" % oid,
           "tribefullname": name, "tribalcomponent": component, "firstname": first,
           "middlename": None, "lastname": last, "suffix": None, "jobtitle": title,
           "state": state, "mailingaddressstate": mailing, "biaregion": "Western",
           # What is never kept.
           "phone": "555-0100", "email": "a@example.org", "physicaladdress": "1 Main St"}
    out.update(extra)
    return out


AFFILIATE = "Affiliate (band, community, village, island, etc...)"


class TestParse(unittest.TestCase):
    def test_keeps_no_phone_email_address_or_website(self):
        entry = tribes.parse([row(1, "Yomba Shoshone Tribe", website="http://lapsed.example")])[0]
        self.assertEqual(set(entry), {"id", "name", "kind", "leader", "title", "state", "region"})

    def test_a_blank_office_state_falls_back_to_the_mailing_state_and_says_so(self):
        entry = tribes.parse([row(1, "Native Village of Akhiok", state=None, mailing="Alaska")])[0]
        self.assertEqual((entry["state"], entry["stateFrom"]), ("AK", "mailing"))

    def test_an_unknown_state_is_an_error_not_a_guess(self):
        with self.assertRaises(tribes.TribesError):
            tribes.parse([row(1, "X Tribe", state="Nevda")])

    def test_one_id_twice_is_an_error(self):
        with self.assertRaises(tribes.TribesError):
            tribes.parse([row(1, "A Tribe", gid="g"), row(2, "B Tribe", gid="g")])

    def test_a_band_sits_under_the_tribe_whose_own_name_lists_it(self):
        rows = [
            row(1, "Te-Moak Tribe of Western Shoshone Indians of Nevada (Four constituent bands: "
                   "Battle Mountain Band; Elko Band; South Fork Band; and Wells Band)"),
            row(2, "Te-Moak Tribe of Western Shoshone Indians of Nevada (Elko Band)",
                component=AFFILIATE, state=None),
            row(3, "Passamaquoddy Tribe", state="Maine"),
            row(4, "Passamaquoddy Tribe - Pleasant Point", component=AFFILIATE, state="Maine"),
            # Named in no tribe row's list: stands on its own.
            row(5, "Te-Moak Tribe of Western Shoshone Indians of Nevada (Ruby Valley Band)",
                component=AFFILIATE, state="Nevada"),
        ]
        cache = {"entries": tribes.parse(rows)}
        found, unplaced = tribes.placed(cache)
        self.assertEqual(unplaced, [])
        nv = {e["name"]: [a["name"] for a in e["affiliates"]] for e in found["NV"]}
        self.assertEqual(len(nv), 2)
        self.assertIn("Te-Moak Tribe of Western Shoshone Indians of Nevada (Elko Band)",
                      next(v for k, v in nv.items() if "Four constituent" in k))
        self.assertEqual([a["name"] for a in found["ME"][0]["affiliates"]],
                         ["Passamaquoddy Tribe - Pleasant Point"])

    def test_a_band_with_no_state_and_no_tribe_is_reported_never_placed(self):
        cache = {"entries": tribes.parse([row(1, "Lost Band (Somewhere)", component=AFFILIATE,
                                              state=None)])}
        found, unplaced = tribes.placed(cache)
        self.assertEqual(found, {})
        self.assertEqual(tribes.problems(cache), ["no state for Lost Band (Somewhere)"])

    def test_two_tribes_that_could_hold_a_band_hold_neither(self):
        rows = [row(1, "Twin Tribe"), row(2, "Twin Tribe", gid="other"),
                row(3, "Twin Tribe - East", component=AFFILIATE)]
        entries = tribes.parse(rows)
        self.assertNotIn("parent", next(e for e in entries if e["kind"] == tribes.AFFILIATE))

    def test_the_leader_is_named_without_the_salutation(self):
        entry = tribes.parse([row(1, "A Tribe", first="John", last="Smith", suffix="Jr.",
                                  salutation="The Honorable")])[0]
        self.assertEqual(entry["leader"], "John Smith, Jr.")


class TestFetch(unittest.TestCase):
    def fake(self, rows, count=None, page=2):
        calls = []

        def get(url):
            calls.append(url)
            if "returnCountOnly" in url:
                return {"count": len(rows) if count is None else count}
            if "/query?" in url:
                offset = int(url.split("resultOffset=")[1].split("&")[0])
                got = rows[offset:offset + page]
                return {"features": [{"attributes": r} for r in got],
                        "exceededTransferLimit": offset + page < len(rows)}
            return {"editingInfo": {"dataLastEditDate": 1792144828481}}
        return get, calls

    def test_pages_on_objectid_and_counts_what_came_back(self):
        rows = [row(i, f"Tribe {i}") for i in range(1, 6)]
        old, tribes.PAGE = tribes.PAGE, 2
        try:
            get, calls = self.fake(rows)
            cache = tribes.fetch(get=get, sleep=lambda s: None)
        finally:
            tribes.PAGE = old
        self.assertEqual(len(cache["entries"]), 5)
        self.assertTrue(all("orderByFields=OBJECTID" in u for u in calls if "outFields" in u))
        self.assertEqual(cache["edited"], "2026-10-16")

    def test_a_short_read_writes_nothing(self):
        get, _ = self.fake([row(1, "A Tribe")], count=2)
        with self.assertRaises(tribes.TribesError):
            tribes.fetch(get=get, sleep=lambda s: None)


class TestTheMap(unittest.TestCase):
    """The committed cache, as the guide's tribal map draws it."""

    @classmethod
    def setUpClass(cls):
        cls.cache = tribes.load_cache()
        if not cls.cache:
            raise unittest.SkipTest("no data/tribal_leaders.json")
        cls.mode = government_maps._tribes(cls.cache)

    def test_every_state_has_a_value_and_a_fact(self):
        self.assertEqual(sorted(self.mode["values"]), government_maps.STATES)
        self.assertEqual(sorted(self.mode["facts"]), government_maps.STATES)

    def test_a_state_with_none_says_where_the_directory_lists_a_nation(self):
        none = [c for c, v in self.mode["values"].items() if v == "none"]
        self.assertTrue(none)
        for code in none:
            self.assertIn("the one state its office is in", self.mode["facts"][code])
            self.assertNotIn(code, self.mode["lists"])

    def test_the_lists_hold_every_placed_row_once_and_give_no_total(self):
        found, unplaced = tribes.placed(self.cache)
        self.assertEqual(unplaced, [])
        listed = [r[0] for rows in self.mode["lists"].values() for r in rows]
        listed += [s[0] for rows in self.mode["lists"].values() for r in rows for s in r[3]]
        self.assertEqual(len(listed), len(self.cache["entries"]))
        self.assertEqual(len(set(listed)), len(listed))
        self.assertNotRegex(self.mode["about"], r"\d{3}")

    def test_each_count_in_a_fact_is_its_list(self):
        for code, rows in self.mode["lists"].items():
            self.assertIn(f"lists {len(rows)} tribal", self.mode["facts"][code])


if __name__ == "__main__":
    unittest.main()
