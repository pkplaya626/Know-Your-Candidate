"""Tests for prediction-market prices and polling averages (kyc/odds.py).

A price or a poll shown against the wrong race looks entirely normal on the
page, so most of these pin attribution: which seat a market is about, which
people a label names, and which table on a page is the November matchup.
"""

import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, odds, validate  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

RACES = [
    {"id": "S-TX-2026", "chamber": "Senate", "state": "TX", "district": None},
    {"id": "S-KY-2026", "chamber": "Senate", "state": "KY", "district": None},
    {"id": "S-LA-2026", "chamber": "Senate", "state": "LA", "district": None},
    {"id": "S-VA-2026", "chamber": "Senate", "state": "VA", "district": None},
    {"id": "S-WV-2026", "chamber": "Senate", "state": "WV", "district": None},
    {"id": "H-CA-22-2026", "chamber": "House", "state": "CA", "district": 22},
    {"id": "H-CA-03-2026", "chamber": "House", "state": "CA", "district": 3},
    {"id": "H-AK-00-2026", "chamber": "House", "state": "AK", "district": 0},
]
INDEX = odds.race_index(RACES)


def kalshi_senate(ticker, question, rule_state, label, price, party="Republican party"):
    return {"ticker": ticker, "status": "active", "title": question,
            "rules_primary": f"If a representative of the {party} is sworn in as a Senator of "
                             f"{rule_state} for the term beginning in 2027, then the market "
                             "resolves to Yes.",
            "yes_sub_title": label, "subtitle": f"{party}:: {party}",
            "last_price_dollars": str(price), "yes_bid_dollars": None, "yes_ask_dollars": None,
            "volume_fp": "100"}


def kalshi_house(ticker, asked, ruled, label, price, party="Democratic"):
    return {"ticker": ticker, "status": "active",
            "title": f"Will {party} win the House race for {asked}?",
            "rules_primary": f"If the House member sworn in for {ruled} for the term beginning in "
                             f"2027 is a member of the {party} Party, then the market resolves to Yes.",
            "yes_sub_title": label, "subtitle": "", "last_price_dollars": str(price),
            "yes_bid_dollars": None, "yes_ask_dollars": None, "volume_fp": "100"}


class TestKalshiAttribution(unittest.TestCase):
    """A market belongs to the seat its own question and rules name."""

    def test_a_ticker_that_says_one_state_cannot_place_another_states_race(self):
        # SENATELA-26 is Kentucky's race on Kalshi, labelled with Kentucky's
        # nominees; Louisiana's lives under KXSENATELA.
        event = {"event_ticker": "SENATELA-26", "sub_title": "In 2026", "markets": [
            kalshi_senate("SENATELA-26-R", "Will Republicans win the Senate race in Kentucky?",
                          "Kentucky", "Andy Barr", 0.958),
            kalshi_senate("SENATELA-26-D", "Will Democratics win the Senate race in Kentucky?",
                          "Kentucky", "Charles Booker", 0.034, party="Democratic party")]}
        race, record = odds.kalshi_market(event, "SENATELA", INDEX)
        self.assertEqual(race, "S-KY-2026")
        self.assertEqual([(o["label"], o["party"]) for o in record["outcomes"]],
                         [("Andy Barr", "r"), ("Charles Booker", "d")])

    def test_a_question_and_rules_that_disagree_place_it_nowhere(self):
        market = kalshi_senate("X-26-R", "Will Republicans win the Senate race in Texas?",
                               "Louisiana", "Ken Paxton", 0.4)
        race, note = odds.kalshi_place(market, INDEX)
        self.assertIsNone(race)
        self.assertIn("asks about S-TX-2026 but resolves on S-LA-2026", note)

    def test_west_virginia_is_not_virginia(self):
        self.assertEqual(odds.senate_race("the Senate race in West Virginia", INDEX), "S-WV-2026")
        self.assertEqual(odds.senate_race("the Senate race in Virginia", INDEX), "S-VA-2026")

    def test_a_house_market_is_placed_by_the_district_its_question_and_rules_name(self):
        market = kalshi_house("HOUSECA3-26-D", "CA-3", "CA-03", "Ami Bera", 0.97)
        self.assertEqual(odds.kalshi_place(market, INDEX), ("H-CA-03-2026", None))
        moved = kalshi_house("X-26-D", "CA-22", "CA-03", "Someone", 0.5)
        race, note = odds.kalshi_place(moved, INDEX)
        self.assertIsNone(race)
        self.assertIn("asks about H-CA-22-2026 but resolves on H-CA-03-2026", note)

    def test_an_at_large_seat_answers_to_al_00_and_01(self):
        for code in ("AL", "00", "01"):
            self.assertEqual(odds.house_race("AK", code, INDEX), "H-AK-00-2026", code)
        self.assertIsNone(odds.house_race("CA", "99", INDEX))     # not on the ballot here

    def test_a_market_with_no_last_trade_takes_the_middle_of_its_spread(self):
        market = kalshi_senate("T-26-R", "Will Republicans win the Senate race in Texas?",
                               "Texas", "Ken Paxton", None)
        market.update(last_price_dollars=None, yes_bid_dollars="0.36", yes_ask_dollars="0.40")
        other = kalshi_senate("T-26-D", "Will Democratics win the Senate race in Texas?",
                              "Texas", "James Talarico", 0.62, party="Democratic party")
        race, record = odds.kalshi_market({"event_ticker": "T-26", "markets": [market, other]},
                                          "T", INDEX)
        self.assertEqual(record["outcomes"][1]["price"], 0.38)

    def test_only_the_2026_contest(self):
        self.assertTrue(odds._is_2026({"sub_title": "In 2026", "event_ticker": "SENATETX-26"}))
        self.assertTrue(odds._is_2026({"event_ticker": "KXSENATELA-26NOV"}))
        self.assertTrue(odds._is_2026({"sub_title": "AL-01", "event_ticker": "KXHOUSERACE-AL01-26"}))
        self.assertFalse(odds._is_2026({"sub_title": "In 2028", "event_ticker": "SENATEGA-28"}))

    def test_series_are_found_by_ticker_or_title_but_never_a_primary(self):
        self.assertTrue(odds._race_series({"ticker": "SENATEAL", "title": "Alabama"}))
        self.assertTrue(odds._race_series({"ticker": "HOUSECA3", "title": "House CA3"}))
        self.assertTrue(odds._race_series({"ticker": "KXHOUSERACE", "title": "House Race Winner?"}))
        self.assertFalse(odds._race_series({"ticker": "KXSENATEFLD",
                                            "title": "Florida Democratic Senate nominee"}))
        self.assertFalse(odds._race_series({"ticker": "KXHOUSEEXPEL",
                                            "title": "How many House members will be expelled?"}))


class TestPolymarket(unittest.TestCase):
    def market(self, title, question, price, active=True):
        return {"groupItemTitle": title, "question": question, "active": active,
                "closed": False, "outcomePrices": json.dumps([str(price), str(1 - price)])
                if price is not None else None, "bestBid": None, "bestAsk": None, "volume": "10"}

    def test_placeholders_are_not_outcomes_and_parties_are_read_from_the_market(self):
        event = {"slug": "texas-senate-election-winner", "title": "Texas Senate Election Winner",
                 "markets": [
                     self.market("James Talarico (D)", "Will the Democrats win the Texas Senate "
                                 "race in 2026?", 0.605),
                     self.market("Ken Paxton (R)", "Will the Republicans win the Texas Senate "
                                 "race in 2026?", 0.385),
                     self.market("Person A", "Will Person A win?", None, active=False)]}
        record = odds.polymarket_market(event)
        self.assertEqual([(o["label"], o["party"], o["price"]) for o in record["outcomes"]],
                         [("James Talarico (D)", "d", 0.605), ("Ken Paxton (R)", "r", 0.385)])
        self.assertEqual(record["url"], "https://polymarket.com/event/texas-senate-election-winner")

    def test_a_party_named_as_a_party_is_coloured_as_one(self):
        control = {"slug": "which-party-will-win-the-senate-in-2026", "title": "Which party?",
                   "markets": [self.market("Democratic Party", "Will the Democratic Party "
                                           "control the Senate?", 0.645),
                               self.market("Republican Party", "Will the Republican Party "
                                           "control the Senate?", 0.355)]}
        self.assertEqual([o["party"] for o in odds.polymarket_market(control)["outcomes"]],
                         ["d", "r"])

    def test_events_are_placed_when_title_and_description_agree(self):
        house = {"slug": "ca-22", "title": "CA-22 House Election Winner",
                 "description": "This market will resolve according to the party of the candidate "
                                "who wins the CA-22 congressional district seat."}
        self.assertEqual(odds.polymarket_place(house, INDEX), ("H-CA-22-2026", None))
        split = dict(house, description="... wins the CA-03 congressional district seat.")
        race, note = odds.polymarket_place(split, INDEX)
        self.assertIsNone(race)
        self.assertIn("do not name one seat", note)
        senate = {"slug": "texas", "title": "Texas Senate Election Winner",
                  "description": "the winner of the 2026 midterm Texas U.S. Senate election"}
        self.assertEqual(odds.polymarket_place(senate, INDEX), ("S-TX-2026", None))
        self.assertEqual(odds.polymarket_place({"title": "Which party wins?"}, INDEX), (None, None))


TABLE = """{| class="wikitable sortable"
!Source of poll<br>aggregation
! Dates<br />administered
! Dates<br />updated
! style="width:100px;" |Ken<br />Paxton (R)
! style="width:100px;" |James<br />Talarico (D)
! style="width:100px;" |Other/<br />Undecided{{Efn|name=calculated}}
! Margin
|-
|[[270toWin]]<ref name="270toWin">{{cite web|title=2026 Polls|url=https://www.270towin.com/2026-senate-polls/texas|website=[[270toWin]]}}</ref>
|September 15–28, 2026<!--publication dates-->
|October 2, 2026
|45.6%
|{{party shading/Democratic}} |'''48.6%'''
|5.8%
|{{party shading/Democratic}} |'''Talarico +3.0%'''
|-
|[[Silver Bulletin]]<ref name="silver"/>
|through September 30, 2026
|October 1, 2026
|45.3%
|{{party shading/Democratic}}|'''48.7%'''
|6.0%
|{{party shading/Democratic}}|'''Talarico +3.4%'''
|}"""

PAGE = ("== Republican primary ==\n=== Polling ===\n'''Aggregate polls'''\n"
        + TABLE.replace("Ken<br />Paxton (R)", "John<br />Cornyn").replace(
            "James<br />Talarico (D)", "Wesley<br />Hunt")
        + "\n== General election ==\n=== Polling ===\n'''Aggregate polls'''\n" + TABLE
        + "\n== References ==\n")

PEOPLE = [{"id": "FEC_P", "name": "Ken Paxton", "party": "Republican"},
          {"id": "FEC_T", "name": "James Talarico", "party": "Democrat"}]


class TestPollingAverages(unittest.TestCase):
    def test_the_general_election_table_is_read_as_the_page_wrote_it(self):
        table = odds.aggregate_table(odds.general_election(PAGE))
        rows, reason = odds.parse_aggregates(table, PEOPLE)
        self.assertIsNone(reason)
        self.assertEqual(rows[0]["aggregator"], "270toWin")
        self.assertEqual(rows[0]["url"], "https://www.270towin.com/2026-senate-polls/texas")
        self.assertEqual([(r["label"], r["party"], r["pct"]) for r in rows[0]["results"]],
                         [("Ken Paxton (R)", "r", 45.6), ("James Talarico (D)", "d", 48.6)])
        self.assertEqual((rows[0]["updated"], rows[0]["other"], rows[0]["margin"]),
                         ("October 2, 2026", 5.8, "Talarico +3.0%"))
        # A named reference with nothing in it gives no link, not a wrong one.
        self.assertEqual((rows[1]["aggregator"], rows[1]["url"]), ("Silver Bulletin", None))

    def test_a_table_about_other_people_is_not_this_race(self):
        primary = odds.aggregate_table(PAGE)       # the first table is the primary's
        rows, reason = odds.parse_aggregates(primary, PEOPLE)
        self.assertIsNone(rows)
        self.assertIn("names nobody in the race", reason)

    def test_no_general_election_section_no_table(self):
        self.assertEqual(odds.aggregate_table(odds.general_election("== Background ==\n")), "")


class TestCheckedOutcomes(unittest.TestCase):
    def test_a_label_naming_someone_else_of_a_known_party_is_a_conflict(self):
        # Kalshi's Louisiana page was Kentucky's: "Andy Barr" where this site
        # knows the Republican.
        people = PEOPLE
        out = odds.checked_outcomes({"outcomes": [
            {"label": "Andy Barr", "party": "r", "price": 0.96},
            {"label": "Republican party", "party": "r", "price": 0.5}]}, people)
        self.assertEqual((out[0]["label"], out[0]["marketLabel"], out[0]["mismatch"],
                          out[0]["conflict"]), ("Republican party", "Andy Barr", True, True))
        self.assertNotIn("mismatch", out[1])

    def test_a_nominee_too_small_for_a_profile_is_shown_as_the_party_not_flagged(self):
        out = odds.checked_outcomes({"outcomes": [
            {"label": "Robin Littau (R)", "party": "r", "price": 0.03}]},
            [{"id": "FEC_D", "name": "Audrey Denney", "party": "Democrat"}])
        self.assertEqual((out[0]["label"], out[0]["mismatch"], out[0]["conflict"]),
                         ("Republican party", True, False))

    def test_a_nominee_the_results_page_lists_counts_as_in_the_race(self):
        out = odds.checked_outcomes({"outcomes": [
            {"label": "Bernadette Greene-Placentia", "party": "d", "price": 0.2}]},
            PEOPLE + [{"name": "Bernadette Greene-Placentia"}])
        self.assertNotIn("mismatch", out[0])

    def test_a_label_naming_two_people_still_names_someone_in_the_race(self):
        # Alaska's race holds Dan Sullivan and a different Daniel J Sullivan.
        people = [{"id": "S001198", "name": "Dan Sullivan", "party": "Republican"},
                  {"id": "FEC_S6AK00326", "name": "Daniel J Sullivan", "party": "Republican"},
                  {"id": "FEC_X", "name": "Mary Peltola", "party": "Democrat"}]
        out = odds.checked_outcomes({"outcomes": [
            {"label": "Sen. Dan Sullivan", "party": None, "price": 0.28},
            {"label": "Mary Peltola", "party": None, "price": 0.71}]}, people)
        self.assertEqual([(o.get("mismatch"), o["party"]) for o in out],
                         [(None, "r"), (None, "d")])


class TestThePageFile(unittest.TestCase):
    CACHE = {"fetched": "2026-10-03T05:00:00+00:00", "notes": ["x"], "races": {
        "S-TX-2026": {"markets": [{"source": "kalshi", "event": "SENATETX-26", "title": "T",
                                   "url": "https://kalshi.com/markets/senatetx", "outcomes": [
                                       {"label": "Ken Paxton", "party": "r", "price": 0.38,
                                        "bid": 0.37, "ask": 0.38, "volume": 9.0,
                                        "question": "Will Republicans win?"}]}]},
        "H-CA-22-2026": {}},
        "control": {"house": [{"source": "kalshi", "outcomes": [
            {"label": "Democratic Party", "party": "d", "price": 0.92}]}]}}

    def test_the_page_gets_what_it_shows_and_nothing_else(self):
        page = odds.payload(self.CACHE)
        self.assertEqual(set(page), {"asOf", "races", "control"})
        self.assertEqual(list(page["races"]), ["S-TX-2026"])      # empty entries dropped
        outcome = page["races"]["S-TX-2026"]["markets"][0]["outcomes"][0]
        self.assertEqual(set(outcome), {"label", "party", "price", "question"})
        self.assertEqual(page["control"]["house"][0]["outcomes"][0]["price"], 0.92)

    def test_the_page_file_is_a_function_of_the_cache_alone(self):
        # A fresh fetch holds its rows in the order they were built; odds.json
        # holds them sorted. The first scheduled run wrote odds.js from the
        # one and verified it against the other, and failed.
        fresh = json.loads(json.dumps(self.CACHE))
        fresh["races"]["S-TX-2026"]["polls"] = {"page": "P", "url": "U", "rows": [
            {"aggregator": "270toWin", "url": None, "updated": "Oct 2", "results": [
                {"label": "Ken Paxton (R)", "party": "r", "pct": 45.6, "id": None}]}]}
        saved = json.loads(json.dumps(fresh, sort_keys=True))
        self.assertEqual(emit.odds_signature(odds.payload(fresh)),
                         emit.odds_signature(odds.payload(saved)))
        with tempfile.TemporaryDirectory() as root:
            path, _ = emit.write_odds(odds.payload(self.CACHE), root)
            self.assertEqual(emit.read_signature(path=path),
                             emit.odds_signature(odds.payload(self.CACHE)))
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("window.kycOdds = ", text)
            self.assertNotIn('"volume"', text)


class TestValidateOdds(unittest.TestCase):
    TODAY = datetime.date(2026, 10, 3)

    def codes(self, entries, races=None, fetched="2026-10-03T05:00:00+00:00"):
        races = races if races is not None else [{"id": rid, "chamber": "Senate"} for rid in entries]
        return {i.code: i for i in validate.check_odds(
            races, {"fetched": fetched, "races": entries}, today=self.TODAY)}

    def market(self, outcomes):
        return {"markets": [{"source": "kalshi", "outcomes": outcomes}]}

    def test_only_a_real_conflict_is_a_warning(self):
        found = self.codes({"S-LA-2026": self.market([
            {"label": "Republican party", "marketLabel": "Andy Barr", "mismatch": True,
             "conflict": True, "price": 0.92},
            {"label": "Democratic party", "marketLabel": "Robin Littau", "mismatch": True,
             "conflict": False, "price": 0.06},
            {"label": "Other", "marketLabel": "Ann Diener", "mismatch": True, "conflict": True,
             "price": 0.0005}])})
        self.assertEqual(len(found["odds-label-mismatch"].detail), 1)
        self.assertIn("Andy Barr", found["odds-label-mismatch"].detail[0])

    def test_uncovered_senate_races_incoherent_prices_stale_and_unknown_races(self):
        races = [{"id": "S-LA-2026", "chamber": "Senate"}, {"id": "S-TX-2026", "chamber": "Senate"},
                 {"id": "H-CA-22-2026", "chamber": "House"}]
        found = self.codes({"S-LA-2026": self.market([{"label": "A", "price": 0.3},
                                                      {"label": "B", "price": 0.2}]),
                            "H-ZZ-01-2026": self.market([{"label": "A", "price": 0.5},
                                                         {"label": "B", "price": 0.5}])},
                           races=races, fetched="2026-09-20T05:00:00+00:00")
        self.assertEqual(set(found), {"odds-incoherent", "odds-uncovered", "odds-stale",
                                      "odds-unknown-race"})
        self.assertEqual(found["odds-uncovered"].detail, ["S-TX-2026"])   # House is not listed


class TestTheCommittedCache(unittest.TestCase):
    def test_every_market_and_poll_is_attributed_and_priced(self):
        cache = odds.load_cache(ROOT)
        if not cache:
            self.skipTest("no odds cache committed")
        for rid, entry in cache["races"].items():
            self.assertRegex(rid, r"^(S-[A-Z]{2}|H-[A-Z]{2}-\d{2})-2026$", rid)
            for market in entry.get("markets") or []:
                self.assertIn(market["source"], odds.SOURCES, rid)
                self.assertGreaterEqual(len(market["outcomes"]), 2, rid)
                for outcome in market["outcomes"]:
                    self.assertTrue(0 <= outcome["price"] <= 1, (rid, outcome))
            for row in (entry.get("polls") or {}).get("rows", []):
                self.assertTrue(all(0 < r["pct"] < 100 for r in row["results"]), (rid, row))

    def test_the_committed_page_file_matches_the_cache(self):
        cache = odds.load_cache(ROOT)
        if not cache:
            self.skipTest("no odds cache committed")
        self.assertEqual(emit.read_signature(path=os.path.join(ROOT, emit.ODDS_FILE)),
                         emit.odds_signature(odds.payload(cache)))


if __name__ == "__main__":
    unittest.main()
