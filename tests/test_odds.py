"""Tests for prediction-market prices and polling averages (kyc/odds.py).

A price or a poll shown against the wrong race looks entirely normal on the
page, so most of these pin attribution: which state a market is about, which
people a label names, and which table on a page is the November matchup.
"""

import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import odds, validate  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
NAMES = {"texas": "TX", "kentucky": "KY", "louisiana": "LA", "virginia": "VA",
         "west virginia": "WV", "alaska": "AK"}


def kalshi_market(ticker, question, rule_state, label, price, party="Republican party"):
    return {"ticker": ticker, "status": "active", "title": question,
            "rules_primary": f"If a representative of the {party} is sworn in as a Senator of "
                             f"{rule_state} for the term beginning in 2027, then the market "
                             "resolves to Yes.",
            "yes_sub_title": label, "subtitle": f"{party}:: {party}",
            "last_price_dollars": str(price), "yes_bid_dollars": None, "yes_ask_dollars": None,
            "volume_fp": "100"}


class TestKalshiAttribution(unittest.TestCase):
    """A market belongs to the state its own question and rules name."""

    def test_a_ticker_that_says_one_state_cannot_place_another_states_race(self):
        # SENATELA-26 is Kentucky's race on Kalshi, labelled with Kentucky's
        # nominees; Louisiana's lives under KXSENATELA.
        event = {"event_ticker": "SENATELA-26", "sub_title": "In 2026", "markets": [
            kalshi_market("SENATELA-26-R", "Will Republicans win the Senate race in Kentucky?",
                          "Kentucky", "Andy Barr", 0.958),
            kalshi_market("SENATELA-26-D", "Will Democratics win the Senate race in Kentucky?",
                          "Kentucky", "Charles Booker", 0.034, party="Democratic party")]}
        state, record = odds.kalshi_market(event, "SENATELA", NAMES)
        self.assertEqual(state, "KY")
        self.assertEqual([(o["label"], o["party"]) for o in record["outcomes"]],
                         [("Andy Barr", "r"), ("Charles Booker", "d")])

    def test_a_question_and_rules_that_disagree_place_it_nowhere(self):
        event = {"event_ticker": "X-26", "sub_title": "In 2026", "markets": [
            kalshi_market("X-26-R", "Will Republicans win the Senate race in Texas?",
                          "Louisiana", "Ken Paxton", 0.4)]}
        state, note = odds.kalshi_market(event, "X", NAMES)
        self.assertIsNone(state)
        self.assertIn("asks about TX but resolves on LA", note)

    def test_west_virginia_is_not_virginia(self):
        self.assertEqual(odds._state_in("the Senate race in West Virginia", NAMES), "WV")
        self.assertEqual(odds._state_in("the Senate race in Virginia", NAMES), "VA")

    def test_a_market_with_no_last_trade_takes_the_middle_of_its_spread(self):
        market = kalshi_market("T-26-R", "Will Republicans win the Senate race in Texas?",
                               "Texas", "Ken Paxton", None)
        market.update(last_price_dollars=None, yes_bid_dollars="0.36", yes_ask_dollars="0.40")
        other = kalshi_market("T-26-D", "Will Democratics win the Senate race in Texas?",
                              "Texas", "James Talarico", 0.62, party="Democratic party")
        state, record = odds.kalshi_market({"event_ticker": "T-26", "markets": [market, other]},
                                           "T", NAMES)
        self.assertEqual(record["outcomes"][1]["price"], 0.38)

    def test_only_the_2026_contest(self):
        self.assertTrue(odds._is_2026({"sub_title": "In 2026", "event_ticker": "SENATETX-26"}))
        self.assertTrue(odds._is_2026({"event_ticker": "KXSENATELA-26NOV"}))
        self.assertFalse(odds._is_2026({"sub_title": "In 2028", "event_ticker": "SENATEGA-28"}))


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
        record = odds.polymarket_market(control)
        self.assertEqual([o["party"] for o in record["outcomes"]], ["d", "r"])


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
    def test_a_label_naming_nobody_in_the_race_is_shown_as_its_party(self):
        market = {"outcomes": [{"label": "Andy Barr", "party": "r", "price": 0.96},
                               {"label": "Republican party", "party": "r", "price": 0.5}]}
        out = odds.checked_outcomes(market, PEOPLE)
        self.assertEqual((out[0]["label"], out[0]["marketLabel"], out[0]["mismatch"]),
                         ("Republican party", "Andy Barr", True))
        self.assertNotIn("mismatch", out[1])

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

    def test_apply_attaches_odds_to_senate_races_only(self):
        races = [{"id": "S-TX-2026", "chamber": "Senate", "incumbentIds": [],
                  "candidateIds": ["FEC_P", "FEC_T"]},
                 {"id": "H-TX-01-2026", "chamber": "House", "incumbentIds": [], "candidateIds": []}]
        cache = {"fetched": "2026-10-03T05:00:00+00:00", "races": {
            "S-TX-2026": {"markets": [{"source": "kalshi", "outcomes": [
                {"label": "Ken Paxton", "party": "r", "price": 0.38}]}]},
            "H-TX-01-2026": {"markets": []}}}
        self.assertEqual(odds.apply(races, cache, {p["id"]: p for p in PEOPLE}), 1)
        self.assertEqual(races[0]["odds"]["asOf"], "2026-10-03T05:00:00+00:00")
        self.assertNotIn("odds", races[1])


class TestValidateOdds(unittest.TestCase):
    TODAY = datetime.date(2026, 10, 3)

    def race(self, outcomes, rid="S-LA-2026"):
        return {"id": rid, "chamber": "Senate", "odds": {"markets": [
            {"source": "kalshi", "outcomes": outcomes}]}}

    def codes(self, races, fetched="2026-10-03T05:00:00+00:00"):
        return {i.code: i for i in validate.check_odds(races, {"fetched": fetched},
                                                       today=self.TODAY)}

    def test_a_mislabelled_outcome_is_reported_and_a_penny_one_is_not(self):
        found = self.codes([self.race([
            {"label": "Republican party", "marketLabel": "Andy Barr", "mismatch": True,
             "price": 0.96},
            {"label": "Other", "marketLabel": "Ann Diener", "mismatch": True, "price": 0.0005},
            {"label": "Jamie Davis", "price": 0.04}])])
        self.assertEqual(len(found["odds-label-mismatch"].detail), 1)
        self.assertIn("Andy Barr", found["odds-label-mismatch"].detail[0])

    def test_uncovered_incoherent_and_stale(self):
        found = self.codes([self.race([{"label": "A", "price": 0.3}, {"label": "B", "price": 0.2}]),
                            {"id": "S-TX-2026", "chamber": "Senate"}],
                           fetched="2026-09-20T05:00:00+00:00")
        self.assertEqual(set(found), {"odds-incoherent", "odds-uncovered", "odds-stale"})


class TestTheCommittedCache(unittest.TestCase):
    def test_every_market_and_poll_is_attributed_and_priced(self):
        cache = odds.load_cache(ROOT)
        if not cache:
            self.skipTest("no odds cache committed")
        for rid, entry in cache["races"].items():
            self.assertTrue(rid.startswith("S-"), rid)
            for market in entry.get("markets") or []:
                self.assertIn(market["source"], odds.SOURCES, rid)
                self.assertGreaterEqual(len(market["outcomes"]), 2, rid)
                for outcome in market["outcomes"]:
                    self.assertTrue(0 <= outcome["price"] <= 1, (rid, outcome))
            for row in (entry.get("polls") or {}).get("rows", []):
                self.assertTrue(all(0 < r["pct"] < 100 for r in row["results"]), (rid, row))


if __name__ == "__main__":
    unittest.main()
