"""Tests for the state legislatures: the Open States pipeline (kyc/statelegs.py),
the page data (kyc/legislature.py) and the boundary tool's downloader.

A legislator put on the wrong district looks entirely normal on a map, so the
matching is tested on the real forms states use, and anyone it cannot place
must be reported, never guessed.
"""

import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from kyc import legislature, statelegs  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
HEAD = ("id,name,current_party,current_district,current_chamber,given_name,family_name,"
        "email,image,links,capitol_voice,twitter,wikidata")


def csv_text(*rows):
    return HEAD + "\n" + "\n".join(rows) + "\n"


def topo(upper=(), lower=()):
    """A topology with only the district names the matcher reads."""
    def obj(names):
        return {"geometries": [{"properties": {"id": f"{i:03d}", "name": n}}
                               for i, n in enumerate(names, 1)]}
    out = {"objects": {"upper": obj(upper)}}
    if lower:
        out["objects"]["lower"] = obj(lower)
    return out


class TestParties(unittest.TestCase):

    def test_fusion_lines_and_dfl_are_their_party(self):
        self.assertEqual(statelegs.party_key("Democratic/Working Families"), "D")
        self.assertEqual(statelegs.party_key("Democratic-Farmer-Labor"), "D")
        self.assertEqual(statelegs.party_key("Republican/Conservative/Independence"), "R")
        self.assertEqual(statelegs.party_key("Nonpartisan"), "N")
        self.assertEqual(statelegs.party_key("Forward"), "I")
        self.assertEqual(statelegs.party_key(""), "I")


class TestDistrictNames(unittest.TestCase):

    def test_both_sources_reduce_to_the_same_name(self):
        pairs = [
            ("10th Bristol District", "10th Bristol"),                          # MA house
            ("Hampshire-Franklin-Worcester", "Hampshire, Franklin and Worcester"),  # MA senate
            ("Chittenden South East", "Chittenden Southeast"),                  # VT senate
            ("State House District Merrimack 08", "Merrimack 8"),               # NH house
            ("Addison-1 State House District", "Addison-1"),                    # VT house
            ("State Senate District 7", "7"),
            ("State Legislative Subdistrict 1A", "1A"),                         # MD
        ]
        for census, openstates in pairs:
            self.assertEqual(statelegs.norm(census), statelegs.norm(openstates), census)

    def test_different_districts_stay_different(self):
        self.assertNotEqual(statelegs.norm("1st Bristol"), statelegs.norm("10th Bristol"))
        self.assertNotEqual(statelegs.norm("Merrimack 1"), statelegs.norm("Merrimack 10"))
        self.assertNotEqual(statelegs.norm("Hampden"), statelegs.norm("Hampden and Hampshire"))

    def test_idahos_seats_belong_to_their_district(self):
        self.assertEqual(statelegs.seat_district("ID", "lower", "10A"), "10")
        self.assertEqual(statelegs.seat_district("ID", "lower", "10 B"), "10")
        self.assertEqual(statelegs.seat_district("MN", "lower", "10A"), "10A")   # a district
        self.assertEqual(statelegs.seat_district("ID", "upper", "10"), "10")


class TestRecords(unittest.TestCase):

    def test_maines_tribal_representatives_are_not_a_district(self):
        rows = statelegs.parse(csv_text(
            "ocd-person/1,Aaron Dana,Independent,Passamaquoddy Tribe,lower,,,,,,,,",
            "ocd-person/2,Jane Roe,Democratic,12,lower,,,,,,,,"), "ME")
        tribal = [r for r in rows if r.get("tribalSeat")]
        self.assertEqual([r["name"] for r in tribal], ["Aaron Dana"])
        unplaced = statelegs.match("ME", rows, topo(lower=["State House District 12"]))
        self.assertEqual(unplaced, [])                   # listed, not a failure
        self.assertNotIn("districtId", tribal[0])

    def test_nebraskas_one_chamber_is_its_upper_house(self):
        rows = statelegs.parse(csv_text("ocd-person/3,A B,Nonpartisan,5,legislature,,,,,,,,"), "NE")
        self.assertEqual(rows[0]["chamber"], "upper")
        self.assertTrue(rows[0]["unicameral"])

    def test_a_malformed_file_is_refused(self):
        with self.assertRaises(statelegs.StateLegislatorsError):
            statelegs.parse("id,name\nx,y\n", "TX")
        with self.assertRaises(statelegs.StateLegislatorsError):
            statelegs.parse(csv_text("ocd-person/1,A,Republican,1,lower,,,,,,,,",
                                     "ocd-person/1,A,Republican,1,lower,,,,,,,,"), "TX")
        with self.assertRaises(statelegs.StateLegislatorsError):
            statelegs.parse(csv_text("ocd-person/1,A,Republican,1,cabinet,,,,,,,,"), "TX")

    def test_only_the_sources_links_are_kept(self):
        rows = statelegs.parse(csv_text(
            'ocd-person/1,A,Republican,1,lower,,,,,"https://a.example/;javascript:alert(1);'
            'https://b.example/",,,'), "TX")
        self.assertEqual(rows[0]["links"], ["https://a.example/", "https://b.example/"])


class TestMatching(unittest.TestCase):

    def test_an_unmatched_member_is_reported_never_guessed(self):
        rows = statelegs.parse(csv_text(
            "ocd-person/1,A,Republican,Rockingham 33,lower,,,,,,,,",
            "ocd-person/2,B,Democratic,Rockingham 3,lower,,,,,,,,"), "NH")
        unplaced = statelegs.match("NH", rows, topo(lower=["State House District Rockingham 03"]))
        self.assertEqual([r["name"] for r, _ in unplaced], ["A"])
        self.assertIn("floterial", unplaced[0][1])
        self.assertEqual(rows[1]["districtId"], "001")

    def test_the_committed_roster_places_everyone_but_whom_it_names(self):
        cache = statelegs.load_cache(ROOT)
        if not cache:
            self.skipTest("no state_legislators.json")
        for code, roster in cache["states"].items():
            topo_ = statelegs.load_map(code, ROOT)
            if not topo_:
                continue
            unplaced = statelegs.match(code, roster, topo_)
            # Only New Hampshire's floterial members are off the map.
            self.assertTrue(all(code == "NH" and "floterial" in why for _, why in unplaced),
                            f"{code}: {[(r['district'], why) for r, why in unplaced][:5]}")

    def test_seats_with_nobody_listed_are_not_counted_as_members(self):
        report = statelegs.seats_report({"ME": [
            {"chamber": "lower", "tribalSeat": True}, {"chamber": "lower"}, {"chamber": "upper"}]})
        self.assertEqual(report["ME"]["lower"], (1, 151))


class TestLegislaturePage(unittest.TestCase):

    def test_only_short_codes_are_written_on_the_map(self):
        self.assertEqual(legislature.label_text("12"), "12")
        self.assertEqual(legislature.label_text("10A"), "10A")
        self.assertEqual(legislature.label_text("B"), "B")
        self.assertEqual(legislature.label_text("10th Bristol"), "")
        self.assertEqual(legislature.label_text("Belknap 1"), "")

    def test_a_built_state_puts_every_label_inside_its_district(self):
        cache = statelegs.load_cache(ROOT)
        if not cache or not statelegs.load_map("NE", ROOT):
            self.skipTest("no committed data")
        roster = cache["states"]["NE"]
        statelegs.match("NE", roster, statelegs.load_map("NE", ROOT))
        page = legislature.build_state("NE", ROOT, {}, roster)
        self.assertEqual(list(page["chambers"]), ["upper"])
        upper = page["chambers"]["upper"]
        self.assertEqual(len(upper["districts"]), 49)
        self.assertEqual(sum(len(v) for v in upper["members"].values()), upper["listed"])

    def test_states_whose_lines_changed_say_so(self):
        self.assertIn("2026", legislature.STATE_NOTES["MI"][0])
        self.assertIn("unsettled", legislature.STATE_NOTES["MS"][0])
        for text, url in legislature.STATE_NOTES.values():
            self.assertTrue(url.startswith("https://"))


class TestDownloader(unittest.TestCase):
    """The Census server answers a burst with a "Request Rejected" page and
    status 200. Cached, it stood in for New Mexico's senate map on every run."""

    def test_a_rejection_page_is_not_a_file(self):
        import fetch_district_maps as maps
        page = b"<html><head><title>Request Rejected</title></head></html>"
        self.assertFalse(maps._whole("https://x/cb_2025_35_sldu_500k.zip", page))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("a.txt", "x")
        self.assertTrue(maps._whole("https://x/a.zip", out.getvalue()))
        self.assertTrue(maps._whole("https://x/page.html", page))


if __name__ == "__main__":
    unittest.main()
