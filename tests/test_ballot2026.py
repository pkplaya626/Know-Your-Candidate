"""Which state offices and legislative seats are on the 2026 ballot."""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import ballot2026  # noqa: E402
from kyc.government_maps import SEATS  # noqa: E402


class TestTable(unittest.TestCase):
    def test_the_table_keeps_its_own_rules(self):
        self.assertTrue(ballot2026.check())

    def test_every_state_and_no_territory(self):
        self.assertEqual(len(ballot2026.STATES), 50)
        self.assertNotIn("DC", ballot2026.STATES)
        self.assertNotIn("PR", ballot2026.STATES)

    def test_chamber_sizes_agree_with_the_seat_table(self):
        # Two sources of one count (rule 53): a slip in either is caught.
        for code, entry in ballot2026.STATES.items():
            self.assertEqual(entry["upper"][1], SEATS[code][0], code)
            self.assertEqual((entry["lower"] or (None, 0))[1], SEATS[code][1], code)

    def test_odd_year_states_elect_none_of_it(self):
        # Louisiana, Mississippi, New Jersey and Virginia elect their governors
        # and legislatures in odd years.
        for code in ("LA", "MS", "NJ", "VA"):
            entry = ballot2026.STATES[code]
            self.assertFalse(entry["governor"][1], code)
            self.assertEqual(entry["upper"][2], 0, code)
            self.assertEqual(entry["lower"][2], 0, code)

    def test_two_year_governors_are_up(self):
        for code in ("NH", "VT"):
            self.assertTrue(ballot2026.STATES[code]["governor"][1], code)

    def test_nebraska_has_one_chamber(self):
        self.assertIsNone(ballot2026.STATES["NE"]["lower"])
        self.assertEqual(ballot2026.STATES["NE"]["upper"][0], "Legislature")

    def test_counts_are_derived_not_typed(self):
        stats = ballot2026.stats()
        self.assertEqual(stats["governor"], sum(1 for e in ballot2026.STATES.values()
                                                if e["governor"][1]))
        self.assertEqual(stats["chambers"], 99)


class TestCheck(unittest.TestCase):
    def broken(self, mutate):
        states = copy.deepcopy(ballot2026.STATES)
        mutate(states)
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(states)
        return str(caught.exception)

    def test_a_missing_state_fails(self):
        self.assertIn("no entry for OH", self.broken(lambda s: s.pop("OH")))

    def test_an_appointed_office_cannot_be_on_the_ballot(self):
        def appoint(states):
            sel, up, note, src = states["TX"]["sos"]
            states["TX"]["sos"] = ("appointed", True, note, src)
        self.assertIn("appointed yet on the ballot", self.broken(appoint))

    def test_a_compiled_table_is_not_a_source(self):
        def cite(states):
            sel, up, note, _src = states["OH"]["ag"]
            states["OH"]["ag"] = (sel, up, note, "https://www.ncsl.org/elections")
        self.assertIn("compiled table", self.broken(cite))

    def test_a_chamber_size_that_disagrees_fails(self):
        def grow(states):
            name, total, up, basis, src = states["OH"]["upper"]
            states["OH"]["upper"] = (name, total + 1, up, basis, src)
        self.assertIn("government_maps.SEATS", self.broken(grow))

    def test_a_county_page_is_not_the_state_record(self):
        def cite(states):
            name, total, up, basis, _src = states["OH"]["upper"]
            states["OH"]["upper"] = (name, total, up, basis,
                                     "https://vote.franklincountyohio.gov/Candidates")
        self.assertIn("compiled table", self.broken(cite))

    def test_the_build_reports_a_broken_table(self):
        from kyc import validate
        self.assertEqual(validate.check_ballot2026(), [])
        original = ballot2026.STATES
        ballot2026.STATES = dict(original)
        ballot2026.STATES.pop("OH")
        try:
            issues = validate.check_ballot2026()
        finally:
            ballot2026.STATES = original
        self.assertEqual([i.level for i in issues], ["error"])

    def test_a_next_year_for_an_office_on_the_ballot_fails(self):
        nxt = dict(ballot2026.NEXT)
        nxt[("GA", "governor")] = (2030, "https://sos.ga.gov/2026-offices-appear-ballot")
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(next_=nxt)
        self.assertIn("on the 2026 ballot, so no next year", str(caught.exception))

    def test_a_next_year_must_follow_2026(self):
        nxt = dict(ballot2026.NEXT)
        nxt[("VA", "governor")] = (2025, nxt[("VA", "governor")][1])
        with self.assertRaises(ballot2026.Ballot2026Error):
            ballot2026.check(next_=nxt)

    def test_an_open_seat_must_be_on_the_ballot(self):
        seats = dict(ballot2026.OPEN_SEATS)
        seats[("VA", "governor")] = ("Abigail Spanberger", "not-listed", None,
                                     "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/",
                                     "a list")
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(open_seats=seats)
        self.assertIn("not on the 2026 ballot", str(caught.exception))

    def test_a_term_limit_says_how_many_terms(self):
        seats = dict(ballot2026.OPEN_SEATS)
        holder, _why, _terms, source, cite = seats[("FL", "governor")]
        seats[("FL", "governor")] = (holder, "term-limit", None, source, cite)
        with self.assertRaises(ballot2026.Ballot2026Error):
            ballot2026.check(open_seats=seats)

    def test_a_joint_ticket_is_elected_with_the_governor(self):
        def split(states):
            sel, up, note, src = states["OH"]["lt"]
            states["OH"]["lt"] = (sel, not up, note, src)
        self.assertIn("joint ticket", self.broken(split))


class TestTerritories(unittest.TestCase):
    """The governor2026 map called Guam, the Virgin Islands and the Northern
    Mariana Islands "not covered" while each elects its governor on Nov 3
    (audit 2026-10-17, RACES-07)."""

    def test_three_territories_elect_a_governor_on_november_3(self):
        up = sorted(c for c, e in ballot2026.TERRITORIES.items() if e["governor"][1])
        self.assertEqual(up, ["GU", "MP", "VI"])

    def test_american_samoa_and_puerto_rico_do_not(self):
        for code in ("AS", "PR"):
            self.assertFalse(ballot2026.TERRITORIES[code]["governor"][1], code)

    def test_a_territory_record_says_it_is_one(self):
        record = ballot2026.for_state("VI")
        self.assertTrue(record["territory"])
        self.assertEqual(sorted(record["offices"]), ["governor", "lt"])
        self.assertEqual(record["chambers"], {})
        # Guam's holds its attorney general too, elected under its own law
        # (5 GCA s.30101).
        self.assertEqual(sorted(ballot2026.for_state("GU")["offices"]), ["ag", "governor", "lt"])

    def test_a_missing_territory_fails(self):
        territories = dict(ballot2026.TERRITORIES)
        territories.pop("GU")
        with self.assertRaises(ballot2026.Ballot2026Error):
            ballot2026.check(territories=territories)


class TestTheDistrict(unittest.TestCase):
    """The District of Columbia elects a mayor and a council, not a governor
    and a legislature, so it had no record and every page named its
    attorney general among the contests "which this site does not list",
    while the Board of Elections' 2026 sample ballots printed two candidates
    for the office (rule 19; read 2026-11-11). Its record holds that office
    alone, and says it is the District's, never a state's or a territory's
    (rule 75)."""

    def test_its_record_is_its_attorney_general_alone(self):
        record = ballot2026.for_state("DC")
        self.assertTrue(record["district"])
        self.assertNotIn("territory", record)
        self.assertEqual(sorted(record["offices"]), ["ag"])
        self.assertEqual(record["chambers"], {})
        ag = record["offices"]["ag"]
        self.assertEqual((ag["selection"], ag["up"]), ("elected", True))
        self.assertTrue(ag["note"].startswith("4-year term;"), ag["note"])
        self.assertTrue(ag["source"].startswith("https://www.dcboe.org/"), ag["source"])
        self.assertNotIn("DC", ballot2026.STATES)
        self.assertNotIn("DC", ballot2026.TERRITORIES)
        self.assertIn("DC", ballot2026.every_jurisdiction())

    def test_never_a_governor_or_a_chamber(self):
        for extra in ({"governor": ("elected", True, "x", "https://www.dcboe.org/")},
                      {"upper": ("Council", 13, 7, "x", "https://www.dcboe.org/")}):
            district = {"DC": dict(ballot2026.DISTRICT["DC"], **extra)}
            with self.assertRaises(ballot2026.Ballot2026Error) as caught:
                ballot2026.check(district=district)
            self.assertIn("the District's record holds only", str(caught.exception))

    def test_an_office_it_holds_is_one_it_elects(self):
        district = {"DC": {"ag": ("appointed", False, "Appointed", "https://www.dcboe.org/")}}
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(district=district)
        self.assertIn("DC ag", str(caught.exception))


class TestNextElection(unittest.TestCase):
    """Virginia's page said "No regular elections in 2026" with no year
    (audit 2026-10-17, PERSONA-19). The year is the statute's, never a term
    length's: Virginia's governor is next elected in 2029, its legislature
    in 2027."""

    def test_virginia(self):
        record = ballot2026.for_state("VA")
        self.assertEqual(record["offices"]["governor"]["next"]["year"], 2029)
        self.assertEqual(record["chambers"]["upper"]["next"]["year"], 2027)
        self.assertEqual(record["chambers"]["lower"]["next"]["year"], 2027)

    def test_an_office_without_a_sourced_year_has_none(self):
        # Delaware's governor: no record read gives the year, so none is shown.
        self.assertNotIn("next", ballot2026.for_state("DE")["offices"]["governor"])

    def test_an_office_on_the_ballot_has_no_next_year(self):
        self.assertNotIn("next", ballot2026.for_state("GA")["offices"]["governor"])

    def test_louisianas_october_election_from_a_record_that_names_the_year(self):
        # R.S. 18:402 names no year and no legislator (PR #94 review); the
        # Secretary of State's 2027 calendar names the year, in October.
        for key in ("governor", "lt", "ag", "sos", "upper", "lower"):
            year, source, month = ballot2026.NEXT[("LA", key)]
            self.assertEqual((year, month), (2027, "October"), key)
            self.assertIn("elections-calendar-2027", source)
        record = ballot2026.for_state("LA")
        self.assertEqual(record["chambers"]["upper"]["next"]["month"], "October")
        self.assertNotIn("month", ballot2026.for_state("VA")["offices"]["governor"]["next"])

    def test_a_month_must_be_a_month(self):
        nxt = dict(ballot2026.NEXT)
        nxt[("VA", "governor")] = (2029, nxt[("VA", "governor")][1], "Novembre")
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(next_=nxt)
        self.assertIn("is not a month", str(caught.exception))


class TestOpenSeats(unittest.TestCase):
    """"On the Nov 3, 2026 ballot" sat under Brian Kemp, Gavin Newsom and Tim
    Walz, none of them on it (audit 2026-10-17, STATEGOV-01). An open seat
    is said only from a cited source, and only about the person who holds
    the office."""

    def test_a_term_limited_governor(self):
        seat, problem = ballot2026.open_seat("FL", "governor", "Ron DeSantis", 2)
        self.assertIsNone(problem)
        self.assertEqual(seat["text"], "Ron DeSantis is term-limited")
        self.assertTrue(seat["source"].startswith("http"))

    def test_someone_else_in_the_office_withholds_it(self):
        seat, problem = ballot2026.open_seat("FL", "governor", "Someone Else", 1)
        self.assertEqual(seat["why"], "unchecked")
        self.assertEqual(seat["holder"], "Someone Else")
        self.assertIn("withheld", problem)

    def test_fewer_terms_than_the_limit_withholds_it(self):
        seat, problem = ballot2026.open_seat("FL", "governor", "Ron DeSantis", 1)
        self.assertEqual(seat["why"], "unchecked")
        self.assertIn("NGA counts 1", problem)

    # The lists themselves are data/statewide_candidates.json now (rule 91);
    # an entry here may still give a list's answer where none is in hand.
    LIST = "https://sos.iowa.gov/a-list.pdf"

    def test_a_list_that_does_not_name_them(self):
        from unittest import mock
        with mock.patch.dict(ballot2026.OPEN_SEATS, {("IA", "governor"): (
                "Pat Holder", "not-listed", None, self.LIST, "a list")}):
            seat, problem = ballot2026.open_seat("IA", "governor", "Pat Holder", 2)
        self.assertIsNone(problem)
        self.assertEqual(seat["text"], "Pat Holder is not on the list of candidates for this office")

    def test_a_list_that_names_them(self):
        from unittest import mock
        with mock.patch.dict(ballot2026.OPEN_SEATS, {("IA", "ag"): (
                "Pat Holder", "listed", None, self.LIST, "a list")}):
            seat, problem = ballot2026.open_seat("IA", "ag", "Pat Holder")
        self.assertIsNone(problem)
        self.assertEqual(seat["why"], "listed")
        self.assertEqual(seat["text"], "Pat Holder is on the list of candidates for this office")

    def test_only_term_limits_remain_where_the_lists_answer(self):
        # Every office with an entry has a list in the statewide cache, so an
        # entry here is a reason beside the list, never a second copy of it.
        self.assertEqual({v[1] for v in ballot2026.OPEN_SEATS.values()}, {"term-limit"})

    def test_no_entry_says_it_was_not_checked(self):
        # Silence beside one office read as "running" once another office
        # said "Open seat" (PR #94 review, rule 19).
        seat, problem = ballot2026.open_seat("MN", "governor", "Tim Walz", 2)
        self.assertIsNone(problem)
        self.assertEqual(seat, {"holder": "Tim Walz", "why": "unchecked",
                                "text": "Whether Tim Walz is running for this office is "
                                        "not checked here"})

    def test_an_office_with_no_named_holder_says_nothing(self):
        self.assertEqual(ballot2026.open_seat("MN", "governor", None), (None, None))

    def test_the_build_attaches_them_and_withholds_a_stale_one(self):
        from kyc import stategov
        payload, problems = stategov.build(".")
        fl = payload["states"]["FL"]["ballot2026"]["offices"]["governor"]
        self.assertEqual(fl["holderStatus"]["holder"], payload["states"]["FL"]["governor"]["name"])
        self.assertEqual(fl["holderStatus"]["why"], "term-limit")
        self.assertFalse([p for p in problems if "OPEN_SEATS" in p], problems)
        # Every office on the ballot with a named holder says something
        # about them; no office off the ballot does.
        for code, state in payload["states"].items():
            for key, item in ((state.get("ballot2026") or {}).get("offices") or {}).items():
                holder = state["governor"] if key == "governor" else state.get(key) or {}
                if item["up"] and holder.get("name"):
                    self.assertIn("holderStatus", item, (code, key))
                if not item["up"]:
                    self.assertNotIn("holderStatus", item, (code, key))


class TestTermsHaveASourceThatSaysThem(unittest.TestCase):
    """South Dakota's governor, attorney general and secretary of state read
    "4-year term; last elected 2022", and both chambers "all (2-year terms)",
    each cited to the Secretary of State's candidate list, which names no
    term and no year (read 2026-11-14), and the legislature panel said
    "Members serve 2-year terms, as the state's record says" beside it. The
    terms are the constitution's as the Legislature publishes it (TERMS);
    the list still says who and which seats are on the ballot."""

    LIST = "https://vip.sdsos.gov/candidatelist.aspx?eid=774"

    def broken(self, states=None, terms=None):
        with self.assertRaises(ballot2026.Ballot2026Error) as caught:
            ballot2026.check(states=states, terms=terms)
        return str(caught.exception)

    def test_south_dakota_cites_its_constitution_for_each_term(self):
        sd = ballot2026.STATES["SD"]
        for key, cite, years in (("governor", "S.D. Const. art. IV, s. 2", 4),
                                 ("ag", "S.D. Const. art. IV, s. 7", 4),
                                 ("sos", "S.D. Const. art. IV, s. 7", 4),
                                 ("upper", "S.D. Const. art. III, s. 6", 2),
                                 ("lower", "S.D. Const. art. III, s. 6", 2)):
            source, got, words = ballot2026.TERMS[("SD", key)]
            self.assertEqual(got, cite, key)
            self.assertTrue(source.startswith("https://sdlegislature.gov/api/Statutes/0N-"), key)
            self.assertIn(years, ballot2026.provision_terms(words), key)
            # The list still says who and which seats are on the ballot.
            self.assertEqual(sd[key][-1], self.LIST, key)
            item = ballot2026.for_state("SD")["offices" if key in ballot2026.OFFICES else "chambers"][key]
            self.assertEqual(item["termSource"], {"url": source, "cite": cite}, key)
        # No year the list does not give.
        self.assertFalse([k for k in ballot2026.OFFICES if "last elected" in sd[k][2]])
        # Only an entry the table cites a provision for carries one.
        self.assertNotIn("termSource", ballot2026.for_state("SD")["offices"]["lt"])
        self.assertNotIn("termSource", ballot2026.for_state("AZ")["offices"]["governor"])

    def test_vermonts_two_year_terms_are_its_constitutions(self):
        vt = ballot2026.for_state("VT")
        for key, cite in (("governor", "Vt. Const. ch. II, s. 49"), ("lt", "Vt. Const. ch. II, s. 49"),
                          ("upper", "Vt. Const. ch. II, s. 46"), ("lower", "Vt. Const. ch. II, s. 46")):
            item = vt["offices" if key in ballot2026.OFFICES else "chambers"][key]
            self.assertEqual(item["termSource"]["cite"], cite, key)
            self.assertEqual(ballot2026.stated_terms(item.get("note") or item.get("basis")), {2}, key)
            self.assertIn(2, ballot2026.provision_terms(ballot2026.TERMS[("VT", key)][2]), key)
        # The attorney general's and secretary of state's terms have no
        # provision read for them: none is cited.
        self.assertNotIn("termSource", vt["offices"]["ag"])
        self.assertNotIn("termSource", vt["offices"]["sos"])

    def test_a_term_on_a_list_that_names_none_needs_its_provision(self):
        # Without the constitution's words, South Dakota's terms rest on the
        # candidate list alone.
        terms = {k: v for k, v in ballot2026.TERMS.items() if k != ("SD", "upper")}
        self.assertIn("SD upper: states a term its source, which names none, does not say",
                      self.broken(terms=terms))
        states = copy.deepcopy(ballot2026.STATES)
        sel, up, note, src = states["SD"]["sos"]
        states["SD"]["sos"] = (sel, up, note + "; last elected 2022", src)
        self.assertIn("SD sos: states the year it was last elected, which its source does not say",
                      self.broken(states=states))

    def test_the_provision_must_give_the_very_term(self):
        terms = dict(ballot2026.TERMS)
        source, cite, words = terms[("SD", "lower")]
        terms[("SD", "lower")] = (source, cite, words.replace("two years", "four years"))
        self.assertIn("term SD lower: the entry states 2-year terms, and S.D. Const. art. III, s. 6's "
                      "words give 4-year", self.broken(terms=terms))
        terms = dict(ballot2026.TERMS)
        terms[("SD", "lt")] = ballot2026.TERMS[("SD", "governor")]
        self.assertIn("term SD lt: the entry states no term", self.broken(terms=terms))
        terms = dict(ballot2026.TERMS)
        terms[("SD", "upper")] = ("https://ballotpedia.org/South_Dakota_State_Senate", cite, words)
        self.assertIn("compiled table", self.broken(terms=terms))

    def test_the_words_are_read_as_a_reader_reads_them(self):
        self.assertEqual(ballot2026.stated_terms("all (2-year terms)"), {2})
        self.assertEqual(ballot2026.stated_terms("4-year staggered terms"), {4})
        self.assertEqual(ballot2026.provision_terms("for a term of four years"), {4})
        self.assertEqual(ballot2026.provision_terms("shall continue for the term of two years"), {2})
        self.assertEqual(ballot2026.provision_terms(
            "The terms of office of the members of the Legislature shall be two years"), {2})
        self.assertEqual(ballot2026.provision_terms("a term of four (4) years"), {4})
        self.assertEqual(ballot2026.provision_terms("a 2-year term"), {2})
        self.assertEqual(ballot2026.provision_terms("the Legislature shall meet"), set())
        # Only a term of office's length counts: how often an election is
        # held, or a span that is not a term, gives none.
        self.assertEqual(ballot2026.provision_terms("every four years thereafter"), set())
        self.assertEqual(ballot2026.provision_terms("shall be two years"), set())
        self.assertEqual(ballot2026.provision_terms("shall be elected biennially"), set())
        self.assertEqual(ballot2026.provision_terms(
            "chosen at the general election of the Governor and every four years thereafter, who "
            "shall severally hold their offices for a term of four years"), {4})

    def test_an_election_every_four_years_is_no_four_year_term(self):
        # A provision whose words say only how often the office is elected
        # does not give the term the entry states (S.D. Const. art. IV, s. 7
        # says both, and only its "for a term of four years" counts).
        terms = dict(ballot2026.TERMS)
        source, cite, _words = terms[("SD", "ag")]
        terms[("SD", "ag")] = (source, cite, "There shall be chosen by the qualified electors of the "
                               "state at the general election of the Governor and every four years "
                               "thereafter the following constitutional officers: attorney general")
        self.assertIn("term SD ag: the entry states 4-year terms, and S.D. Const. art. IV, s. 7's words "
                      "give none", self.broken(terms=terms))
        # The real entries still pass.
        ballot2026.check()


if __name__ == "__main__":
    unittest.main()
