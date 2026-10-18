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

    def test_a_legislature_is_called_by_its_constitutional_name(self):
        # Every page read "<State> Legislature": "Virginia Legislature",
        # "Massachusetts Legislature", "Oregon Legislature".
        from kyc import pages
        from kyc.government_maps import LEGISLATURE_NAME, STATES

        self.assertEqual(len(LEGISLATURE_NAME), 23)
        self.assertTrue(set(LEGISLATURE_NAME) <= set(STATES))
        for code, title in (("VA", "Virginia General Assembly"), ("MA", "Massachusetts General Court"),
                            ("OR", "Oregon Legislative Assembly"), ("TX", "Texas Legislature"),
                            ("NE", "Nebraska Legislature")):
            html = pages.render_legislature_page(code, "")
            self.assertIn(f'<h1 class="state-title">{title}</h1>', html)
            self.assertIn(f"<title>{title} — Know Your Candidate</title>", html)

    def test_states_whose_lines_changed_say_so(self):
        self.assertIn("2026", legislature.STATE_NOTES["MI"][0])
        self.assertIn("unsettled", legislature.STATE_NOTES["MS"][0])
        for text, url in legislature.STATE_NOTES.values():
            self.assertTrue(url.startswith("https://"))


class TestOfficialPage(unittest.TestCase):
    """One page per member on the legislature's own site, not every page
    Open States read (audit 2026-10-17, LINKS-04, STATEGOV-16)."""

    def test_one_member_page_from_eighteen_links(self):
        # Val Peterson (UT HD 56): a disclosure folder, three copies of his
        # House page, bill lists and a dozen PDFs.
        links = [
            "https://disclosures.utah.gov/Search/PublicSearch/FolderDetails/1409531",
            "https://house.utah.gov/rep/PETERVL", "https://house.utah.gov/rep/PETERVL/",
            "https://house.utleg.gov/rep/PETERVL/",
            "https://le.utah.gov/asp/billsintro/RepResults.asp?Listbox3=PETERVL",
            "https://le.utah.gov/Documents/demographic/profiles/2020/House_Dist59.pdf",
            "https://le.utah.gov/Documents/conflict/2024/PETERVL.pdf",
        ]
        self.assertEqual(legislature.official_page("UT", links, 2026),
                         "https://house.utah.gov/rep/PETERVL")

    def test_a_past_session_loses_to_the_current_one(self):
        idaho = ["https://legislature.idaho.gov/legislators/membership/2023/id2084/",
                 "https://legislature.idaho.gov/legislators/membership/2024/id2084/",
                 "https://legislature.idaho.gov/legislators/membership/2026/id2084/",
                 "https://legislature.idaho.gov/legislators/membership/?yr=2023&district=22"]
        self.assertEqual(legislature.official_page("ID", idaho, 2026), idaho[2])
        wyoming = ["https://wyoleg.gov/Legislators/2021/R/2006",
                   "https://www.wyoleg.gov/Legislators/2025/S/2006"]
        self.assertEqual(legislature.official_page("WY", wyoming, 2026), wyoming[1])
        arkansas = ["https://www.arkleg.state.ar.us/Legislators/Detail?member=M.+Johnson"
                    "&ddBienniumSession=2019%2F2020F",
                    "https://arkleg.state.ar.us/Legislators/Detail?member=M.+Johnson"]
        self.assertEqual(legislature.official_page("AR", arkansas, 2026), arkansas[1])
        # Of past pages only, the latest (Hawaii links no current one).
        hawaii = ["https://capitol.hawaii.gov/memberpage.aspx?member=wakai&year=2019",
                  "https://www.capitol.hawaii.gov/legislature/memberpage.aspx?member=217&year=2024"]
        self.assertEqual(legislature.official_page("HI", hawaii, 2026), hawaii[1])

    def test_illinois_links_only_the_latest_general_assembly(self):
        links = ["https://ilga.gov/house/Rep.asp?GA=101&MemberID=2583",
                 "https://ilga.gov/house/Rep.asp?GA=103&MemberID=3045",
                 "https://www.ilga.gov/house/Rep.asp?GA=104&MemberID=3278"]
        self.assertEqual(legislature.official_page("IL", links[:2], 2026, assembly=104), None)
        self.assertEqual(legislature.official_page("IL", links, 2026, assembly=104), links[2])

    def test_a_page_named_for_another_member_is_not_theirs(self):
        # Open States lists Rhode Island's Bob Phillips, and some twenty other
        # representatives, with Lauren Carson's page (2026-10-17). Its
        # ".../phillips/default.aspx" is his own page, not a chamber list.
        links = ["https://www.rilegislature.gov/representatives/carson/default.aspx",
                 "https://www.rilegislature.gov/representatives/phillips/default.aspx",
                 "https://www.rilin.state.ri.us/representatives/carson/"]
        others = {"carson", "phillips", "kazarian"}
        self.assertEqual(legislature.official_page("RI", links, 2026, name="Bob Phillips", others=others),
                         links[1])
        self.assertIsNone(legislature.official_page("RI", [links[0], links[2]], 2026,
                                                    name="Katie Kazarian", others=others))
        self.assertEqual(legislature.surname("Robert Smith Jr."), {"smith"})
        self.assertEqual(legislature.surname("Tracy Brown-May"), {"brown", "may"})

    def test_an_older_numbered_legislature_is_past(self):
        # Arizona links its 56th Legislature's page beside the 57th's.
        links = ["https://www.azleg.gov/house-member/?legislature=56&session=127&legislator=2174",
                 "https://www.azleg.gov/house-member/?legislature=57&session=129&legislator=2318"]
        latest = legislature.latest_assembly([{"links": links}])
        self.assertEqual(latest, {"legislature": 57})
        self.assertEqual(legislature.official_page("AZ", links, 2026, latest), links[1])

    def test_a_caucus_page_on_the_legislatures_host_is_not_its_page(self):
        links = ["https://legislature.maine.gov/housedems/kuhn",
                 "https://legislature.maine.gov/house/house/MemberProfiles/Details/1474"]
        self.assertEqual(legislature.official_page("ME", links, 2026, name="Amy Kuhn"), links[1])
        self.assertIsNone(legislature.official_page("ME", links[:1], 2026, name="Amy Kuhn"))

    def test_a_caucus_page_is_not_the_legislatures(self):
        self.assertIsNone(legislature.official_page("CT", ["https://www.housedems.ct.gov/Reyes"], 2026))
        self.assertIsNone(legislature.official_page("MI", ["https://gophouse.org/member/RepTomKunse"], 2026))
        self.assertIsNone(legislature.official_page("NH", ["https://lebanonnh.gov/1856/Councilor"], 2026))

    def test_a_chamber_list_or_a_file_is_not_a_members_page(self):
        self.assertIsNone(legislature.official_page("GA", ["https://www.legis.ga.gov/members/house"], 2026))
        self.assertIsNone(legislature.official_page(
            "NH", ["https://gencourt.state.nh.us/downloads/Members.txt"], 2026))
        nc = ["https://www.ncleg.gov/Members/Votes/H/665", "https://www.ncleg.gov/Members/Biography/H/665"]
        self.assertEqual(legislature.official_page("NC", nc, 2026), nc[1])

    def test_every_host_is_one_the_roster_links(self):
        # A host no member is linked from is a stale entry.
        from kyc.government_maps import STATES
        self.assertEqual(set(legislature.LEGISLATURE_HOSTS), set(STATES))
        cache = statelegs.load_cache(ROOT)
        if not cache:
            self.skipTest("no state_legislators.json")
        import urllib.parse
        for code, hosts in legislature.LEGISLATURE_HOSTS.items():
            seen = {(urllib.parse.urlsplit(link).hostname or "").lower().removeprefix("www.")
                    for r in cache["states"][code] for link in r.get("links", ())}
            self.assertFalse(set(hosts) - seen, code)


class TestPerson(unittest.TestCase):

    def record(self, **extra):
        return dict({"id": "ocd-person/1", "name": "A", "party": "Republican", "partyKey": "R",
                     "chamber": "upper", "district": "1"}, **extra)

    def test_search_thumbnails_are_not_portraits(self):
        # Audit 2026-10-17, LINKS-05: Google image-search thumbnails; news
        # and civic sites' images are the page's own and stay.
        for url in ("https://encrypted-tbn0.gstatic.com/images?q=tbn:x", "https://t2.gstatic.com/x",
                    "https://lh3.googleusercontent.com/x"):
            dropped = {}
            out = legislature._person(self.record(image=url), "ID", 2026, dropped=dropped)
            self.assertNotIn("image", out)
            self.assertEqual(dropped, {"thumbnail": 1})
        out = legislature._person(self.record(image="https://bloximages.townnews.com/a.jpg"), "ID", 2026)
        self.assertEqual(out["image"], "https://bloximages.townnews.com/a.jpg")

    def test_a_confirmed_missing_portrait_is_left_off_and_counted(self):
        dropped = {}
        out = legislature._person(self.record(image="https://x.gov/a.jpg", imageStatus="broken"),
                                  "KS", 2026, dropped=dropped)
        self.assertNotIn("image", out)
        self.assertEqual(dropped, {"broken": 1})
        # Not checked, or inconclusive: shown (rule 8), over https.
        out = legislature._person(self.record(image="http://x.gov/a.jpg"), "KS", 2026)
        self.assertEqual(out["image"], "https://x.gov/a.jpg")

    def test_a_district_office_phone_is_kept_and_raw_links_are_not(self):
        out = legislature._person(self.record(districtPhone="907-247-4672",
                                              links=["https://www.akleg.gov/basis/Member/Detail/34?code=byn",
                                                     "https://akhousemajority.com/bynum"],
                                              social={"twitter": "x"}), "AK", 2026)
        self.assertEqual(out["districtPhone"], "907-247-4672")
        self.assertEqual(out["page"], "https://www.akleg.gov/basis/Member/Detail/34?code=byn")
        self.assertNotIn("links", out)
        self.assertNotIn("social", out)

    def test_a_fusion_label_is_its_party_with_its_other_lines(self):
        out = legislature._person(self.record(party="Republican/Conservative/Independence"), "NY", 2026)
        self.assertEqual(out["party"], "Republican")
        self.assertEqual(out["lines"], ["Conservative", "Independence"])


class TestChamberCounts(unittest.TestCase):

    def test_parties_are_counted_by_party_not_ballot_line(self):
        # Audit 2026-10-17, STATEGOV-21: New York's Senate read "21
        # Democratic, 19 Democratic/Working Families, 16 Republican/
        # Conservative, ...".
        rows = [{"chamber": "upper", "party": p, "partyKey": statelegs.party_key(p)} for p in (
            ["Democratic"] * 2 + ["Democratic/Working Families"] * 3 + ["Republican/Conservative"]
            + ["Progressive", "Independent", "Progressive"])]
        self.assertEqual(legislature.parties(rows, "upper"), [
            ["Democratic", "D", 5], ["Progressive", "I", 2], ["Independent", "I", 1],
            ["Republican", "R", 1]])

    def test_the_legislature_pages_count_as_the_state_page_does(self):
        from kyc import stategov
        try:
            control = stategov.build(ROOT)[0]["states"]
            maps = legislature.build(ROOT, codes=["AK", "MN", "NY", "NH", "NE"])
        except (stategov.StateGovError, legislature.LegislatureError) as exc:
            self.skipTest(str(exc))
        for code, page in maps.items():
            for which, c in page["chambers"].items():
                theirs = control[code][which]
                self.assertEqual({k: c["count"][k] for k in ("D", "R", "I", "N", "listed", "majority")},
                                 {k: theirs[k] for k in ("D", "R", "I", "N", "listed", "majority")})
                by_key = {}
                for _name, key, n in c["parties"]:
                    by_key[key] = by_key.get(key, 0) + n
                self.assertEqual({k: v for k, v in by_key.items()},
                                 {k: theirs[k] for k in ("D", "R", "I", "N") if theirs[k]})
        # Alaska's coalitions travel with its page (rule 54, STATEGOV-05).
        self.assertEqual(maps["AK"].get("legislature"), control["AK"]["legislature"])
        if control["AK"].get("note"):
            self.assertEqual(maps["AK"]["note"], control["AK"]["note"])
        # New Hampshire's floterial members say which district they hold.
        floterial = [p for p in maps["NH"]["unplaced"] if p["chamber"] == "lower"]
        self.assertTrue(floterial and all(p["why"] == "floterial" and p["district"] for p in floterial))


class TestSeatsUp(unittest.TestCase):
    """Which districts' seats are on the 2026 regular ballot, read from the
    state's own record (kyc/ballot2026.py), or nothing (STATEGOV-18)."""

    def districts(self, names):
        return {f"{i:03d}": {"name": n} for i, n in enumerate(names, 1)}

    def test_a_listed_set_and_a_parity_rule(self):
        ak = legislature.seats_up("AK", "upper", self.districts("ABCDEFGHIJKLMNOPQRST"))
        self.assertEqual(sorted(k for k, v in ak.items() if v),
                         ["001", "003", "005", "007", "009", "011", "013", "015", "017", "019"])
        ca = legislature.seats_up("CA", "upper", self.districts([str(n) for n in range(1, 41)]))
        self.assertEqual(sum(ca.values()), 20)
        self.assertTrue(ca["002"] and not ca["001"])

    def test_all_and_none(self):
        self.assertTrue(all(legislature.seats_up("NH", "lower", self.districts(["Belknap 01"])).values()))
        ks = legislature.seats_up("KS", "upper", self.districts([str(n) for n in range(1, 41)]))
        self.assertFalse(any(ks.values()))      # districts 24 and 25 hold specials only

    def test_a_term_is_shown_only_where_the_record_states_one(self):
        self.assertEqual(legislature.term_years("NH", "lower"), 2)
        self.assertEqual(legislature.term_years("NE", "upper"), 4)   # not the 2-year special
        self.assertIsNone(legislature.term_years("MN", "upper"))     # a 2-4-4 cycle
        self.assertIsNone(legislature.term_years("TX", "upper"))     # the record does not say

    def test_words_that_do_not_resolve_mark_nothing(self):
        # "one of the two seats in each of the 17 districts"; "25 of 50".
        self.assertEqual(legislature.seats_up("WV", "upper", self.districts(
            [str(n) for n in range(1, 18)])), {})
        self.assertEqual(legislature.seats_up("MT", "upper", self.districts(
            [str(n) for n in range(1, 51)])), {})
        # A list naming a district the map does not have.
        self.assertEqual(legislature.seats_up("AK", "upper", self.districts("ABCDEFGHIJKLMNOPQRZT")), {})


class TestImageCheck(unittest.TestCase):
    """Legislators' portraits, checked the tristate way (STATEGOV-03)."""

    def test_a_refusal_concludes_nothing(self):
        # Only a 404 or 410 to a GET is "missing": an HTML page with status
        # 200, a bot wall's 403, a throttle or a dropped connection says
        # nothing (rules 8 and 52; Texas's host refused one machine every
        # connection). HEAD is never asked: Massachusetts answers it 404 for
        # portraits GET serves, South Dakota with an HTML page.
        import io
        import urllib.error
        from unittest import mock

        class Response(io.BytesIO):
            def __init__(self, ctype):
                super().__init__(b"")
                self.status, self.headers = 200, {"Content-Type": ctype}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def raising(code):
            def opener(req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b""))
            return opener
        cases = [(raising(404), False), (raising(410), False), (raising(403), None),
                 (raising(429), None), (raising(503), None),
                 (lambda req, timeout=None: Response("image/jpeg"), True),
                 (lambda req, timeout=None: Response("text/html; charset=utf-8"), None),
                 (mock.Mock(side_effect=OSError("refused")), None)]
        for opener, want in cases:
            with mock.patch("urllib.request.urlopen", opener):
                self.assertIs(statelegs.check_portrait("https://x.gov/a.jpg"), want)
        methods = []

        def recording(req, timeout=None):
            methods.append(req.get_method())
            return Response("image/jpeg")
        with mock.patch("urllib.request.urlopen", recording):
            statelegs.check_portrait("https://x.gov/a.jpg")
        self.assertEqual(methods, ["GET"])

    def test_only_a_definite_answer_marks_a_portrait(self):
        import datetime
        answers = {"https://a.gov/1.jpg": True, "https://a.gov/2.jpg": False, "https://a.gov/3.jpg": None,
                   "https://b.gov/4.jpg": True}
        by_state = {"KS": [{"id": "1", "image": "https://a.gov/1.jpg"},
                           {"id": "2", "image": "https://a.gov/2.jpg"},
                           {"id": "3", "image": "https://a.gov/3.jpg"},
                           {"id": "4", "image": "http://b.gov/4.jpg"},
                           {"id": "5", "image": "https://encrypted-tbn0.gstatic.com/x"}]}
        asked = []

        def check(url):
            asked.append(url)
            return answers[url]
        today = datetime.date(2026, 10, 17)
        counts = statelegs.check_images(by_state, today=today, check=check, pause=0)
        rows = by_state["KS"]
        self.assertEqual([r.get("imageStatus") for r in rows], ["ok", "broken", None, "ok", None])
        self.assertEqual(counts["KS"], {"ok": 2, "broken": 1, "unknown": 1})
        # The https copy of an http portrait is the one checked; a search
        # thumbnail is never asked about.
        self.assertIn("https://b.gov/4.jpg", asked)
        self.assertFalse(any("gstatic" in u for u in asked))

        # A recent answer stands; an inconclusive new one leaves the old.
        previous = {"states": {"KS": [dict(r) for r in rows]}}
        fresh = {"KS": [{"id": r["id"], "image": r["image"]} for r in rows]}
        asked.clear()
        statelegs.check_images(fresh, previous=previous, today=today, check=check, pause=0)
        self.assertEqual(asked, ["https://a.gov/3.jpg"])
        later = today + datetime.timedelta(days=statelegs.IMAGE_RECHECK_DAYS)
        answers["https://a.gov/2.jpg"] = None
        asked.clear()
        statelegs.check_images(fresh, previous={"states": {"KS": [dict(r) for r in fresh["KS"]]}},
                               today=later, check=check, pause=0)
        self.assertEqual(fresh["KS"][1]["imageStatus"], "broken")
        self.assertIn("https://a.gov/2.jpg", asked)


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
