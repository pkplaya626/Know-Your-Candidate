"""Each jurisdiction's key dates for November 3, 2026 (kyc/voting_dates.py).

Seventeen days out the state pages offered "Register to vote" where the
deadline had passed and gave no early-voting or mail-ballot date (audit
2026-10-17, STATEGOV-11, PERSONA-03, FRESHNESS-11, VISUALS-25). The dates
are a hand-editable cache, every value shown sourced to the jurisdiction's
own page; a compiled table is a lead, never a source (rule 50).
"""

import copy
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import overrides, validate, voting, voting_dates  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = voting_dates.load(ROOT)


def record(code):
    return copy.deepcopy(DATA["states"][code])


def with_state(code, rec):
    data = copy.deepcopy(DATA)
    data["states"][code] = rec
    return data


class TestTheCommittedCache(unittest.TestCase):
    def test_every_jurisdiction_and_no_problems(self):
        self.assertEqual(set(DATA["states"]), voting_dates.JURISDICTIONS)
        self.assertEqual(voting_dates.problems(DATA), [])
        self.assertEqual(validate.check_voting_dates(DATA), [])

    def test_every_jurisdiction_reaches_the_page(self):
        page = voting_dates.for_page(DATA)
        self.assertEqual(set(page["states"]), voting_dates.JURISDICTIONS)

    def test_the_three_receipt_dates_the_research_left_unsourced_now_cite_the_office(self):
        # MP, WI and WY's mail.returnDeadline.receivedBy had no source entry
        # of their own in the research; each is re-sourced to the office's
        # page or statute (re-read 2026-10-18).
        for code in ("MP", "WI", "WY"):
            rec = DATA["states"][code]
            sources = [s for s in rec["sources"] if s["field"] == "mail.returnDeadline.receivedBy"]
            self.assertTrue(sources, code)
            self.assertTrue(all(voting_dates.official_source(s["url"], code)[0] for s in sources), code)

    def test_no_source_is_a_compiled_table(self):
        for code, rec in DATA["states"].items():
            for source in rec["sources"]:
                self.assertFalse(voting_dates.compiled(source["url"]), f"{code}: {source['url']}")

    def test_the_december_dates_agree_with_the_results_reader(self):
        # Two sources of one date must agree (rule 53).
        self.assertEqual(DATA["states"]["GA"]["runoff"]["date"], overrides.GENERAL_RUNOFFS["GA"][0])
        self.assertEqual(DATA["states"]["LA"]["runoff"]["date"],
                         overrides.OPEN_PRIMARY_SEATS[("LA", "H", 2026)]["runoff"])


class TestSources(unittest.TestCase):
    def test_compiled_tables_are_refused_even_on_a_gov_domain(self):
        for url in ("https://vote.gov/register/texas", "https://www.ncsl.org/elections/x",
                    "https://ballotpedia.org/Texas", "https://en.wikipedia.org/wiki/X",
                    "https://www.vote.org/voter-registration-deadlines/",
                    "http://web.archive.org/web/20261001000000/https://ballotpedia.org/Texas"):
            ok, why = voting_dates.official_source(url, "TX")
            self.assertFalse(ok, url)
            self.assertIn("rule 50", why)

    def test_another_states_domain_is_refused(self):
        self.assertFalse(voting_dates.official_source("https://www.sos.state.tx.us/x", "OK")[0])
        self.assertTrue(voting_dates.official_source("https://www.sos.state.tx.us/x", "TX")[0])
        self.assertFalse(voting_dates.official_source("https://www.votecnmi.gov.mp/x", "GU")[0])
        self.assertFalse(voting_dates.official_source("https://example.com/x", "TX")[0])

    def test_a_gov_host_counts_only_for_its_own_jurisdiction(self):
        # PR #102 review: any .gov host passed for every jurisdiction -
        # another state's office, a county, a federal guide.
        for url, code in (("https://sos.ga.gov/x", "FL"), ("https://www.sos.la.gov/x", "TX"),
                          ("https://effinghamcountyil.gov/x.pdf", "IL"),
                          ("https://www.clarkcountynv.gov/x", "NV"),
                          ("https://www.govinfo.gov/content/pkg/USCODE-2024-title48/x", "TX")):
            self.assertFalse(voting_dates.official_source(url, code)[0], (url, code))
        for url in ("https://www.fvap.gov/texas", "https://www.usa.gov/how-to-vote"):
            ok, why = voting_dates.official_source(url, "TX")
            self.assertFalse(ok, url)
            self.assertIn("rule 50", why)
        for url, code in (("https://sos.ga.gov/x", "GA"), ("https://dos.fl.gov/x", "FL"),
                          ("https://www.leg.state.nv.us/NRS/x", "NV"),
                          ("https://www.govinfo.gov/content/pkg/USCODE-2024-title48/x", "GU")):
            self.assertTrue(voting_dates.official_source(url, code)[0], (url, code))

    def test_nevadas_secretary_of_state_is_on_its_own_domain(self):
        # nvsos.gov is the Secretary of State's own site; it once needed an
        # override entry (overrides.MEASURE_SOURCES_ELSEWHERE) to count for
        # Nevada at all. It counts for Nevada alone, and a county's page
        # still does not.
        url = "https://www.nvsos.gov/elections/election-information/2026-election-information"
        self.assertEqual(voting_dates.official_source(url, "NV"), (True, "nvsos.gov"))
        self.assertFalse(voting_dates.official_source(url, "AZ")[0])
        self.assertFalse(voting_dates.official_source("https://www.clarkcountynv.gov/x", "NV")[0])
        self.assertFalse(voting_dates.official_source("https://nvsos.gov.example.com/x", "NV")[0])

    def test_nevadas_early_voting_cites_the_offices_own_words_first(self):
        record = voting_dates.load(".")["states"]["NV"]
        for field in ("earlyVoting.start", "earlyVoting.end"):
            first = next(s for s in record["sources"] if s["field"] == field)
            self.assertTrue(first["url"].startswith("https://www.nvsos.gov/"), field)
            self.assertIn("October 17th through October 30th", first["quote"])
        self.assertNotIn("Verify against nvsos.gov", record["notes"])

    def test_a_source_read_later_says_its_own_day(self):
        # PR #140 review: the note under the dates said every date was "read
        # on 2026-10-17 and checked again on 2026-10-18" over nvsos.gov's
        # early-voting words, read by hand on 2026-10-25.
        data = voting_dates.load(".")
        page = voting_dates.for_page(data)
        self.assertEqual(page["states"]["NV"]["reread"],
                         [{"d": "2026-10-25", "labels": ["nvsos.gov"]}])
        # A record with no source read later carries nothing (Georgia's
        # calendar was read again on 2026-11-11 for its runoff's dates).
        self.assertNotIn("reread", page["states"]["TX"])
        self.assertEqual(page["states"]["GA"]["reread"],
                         [{"d": "2026-11-11", "labels": ["sos.ga.gov"]}])
        # A read day must be a day of the cycle.
        record = copy.deepcopy(data["states"]["NV"])
        record["sources"][0]["read"] = "Oct 25"
        self.assertTrue(any("is not a day" in p for p in
                            voting_dates.state_problems("NV", record, {})))

    def test_every_jurisdiction_has_its_own_domains(self):
        self.assertEqual(set(voting_dates.JURISDICTION_DOMAINS), voting_dates.JURISDICTIONS)

    def test_an_archived_official_page_counts_and_says_so(self):
        ok, label = voting_dates.official_source(
            "http://web.archive.org/web/20261004203000/https://gec.guam.gov/2026-important-dates/", "GU")
        self.assertTrue(ok)
        # In brackets: the page separates sources with semicolons, and a
        # comma inside a label ran one source into the next.
        self.assertEqual(label, "gec.guam.gov (archived 2026-10-04)")

    def test_a_file_on_a_shared_host_counts_only_for_the_office_it_is_listed_for(self):
        url = next(iter(voting_dates.OFFICIAL_ELSEWHERE))
        owner = voting_dates.OFFICIAL_ELSEWHERE[url][0][0]
        self.assertTrue(voting_dates.official_source(url + "view", owner)[0])
        self.assertFalse(voting_dates.official_source(url + "view", "TX")[0])
        self.assertFalse(voting_dates.official_source("https://drive.google.com/file/d/other/view", owner)[0])


class TestProblems(unittest.TestCase):
    def assertProblem(self, data, text):
        found = voting_dates.problems(data)
        self.assertTrue(any(text in p for p in found), found)

    def test_a_value_shown_without_its_own_source_fails(self):
        rec = record("TX")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "earlyVoting.start"]
        self.assertProblem(with_state("TX", rec), "TX earlyVoting.start: shown with no source")

    def test_a_qualifier_may_stand_on_its_values_source(self):
        rec = record("GA")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "mail.returnDeadline.time"]
        self.assertEqual(voting_dates.problems(with_state("GA", rec)), [])

    def test_a_compiled_source_fails_the_build(self):
        rec = record("TX")
        rec["sources"][0] = dict(rec["sources"][0], url="https://www.ncsl.org/elections-and-campaigns/x")
        data = with_state("TX", rec)
        self.assertProblem(data, "rule 50")
        issues = validate.check_voting_dates(data)
        self.assertEqual([i.level for i in issues], ["error"])

    def test_a_source_with_no_quote_fails(self):
        rec = record("TX")
        rec["sources"][0] = dict(rec["sources"][0], quote=" ")
        self.assertProblem(with_state("TX", rec), "a source with no quote")

    def test_dates_must_run_forwards_and_before_the_election(self):
        rec = record("TX")
        rec["earlyVoting"]["end"] = "2026-10-01"
        self.assertProblem(with_state("TX", rec), "does not run forwards")
        rec = record("TX")
        rec["registration"]["mail"]["deadline"] = "2026-11-05"
        self.assertProblem(with_state("TX", rec), "after the election")
        rec = record("TX")
        rec["mail"]["requestDeadline"]["date"] = "October 23"
        self.assertProblem(with_state("TX", rec), "is not a date")

    def test_a_postmark_deadline_whose_ballots_must_arrive_that_day_fails(self):
        rec = record("TX")
        rec["mail"]["returnDeadline"]["receivedBy"] = rec["mail"]["returnDeadline"]["date"]
        self.assertProblem(with_state("TX", rec), "postmarked, yet received the same day")

    def test_a_runoff_needs_words_and_must_agree_with_the_overrides(self):
        rec = record("GA")
        rec["runoff"]["date"] = "2026-12-08"
        self.assertProblem(with_state("GA", rec), "must agree (rule 53)")
        rec = record("TX")
        rec["runoff"]["date"] = "2026-12-12"
        rec["sources"].append({"field": "runoff.date", "url": "https://www.sos.texas.gov/x", "quote": "x"})
        self.assertProblem(with_state("TX", rec), "no RUNOFF_WORDS")

    def test_a_missing_jurisdiction_fails(self):
        data = copy.deepcopy(DATA)
        del data["states"]["OH"]
        self.assertProblem(data, "OH: no record")

    def test_a_record_that_breaks_a_rule_is_not_sent_to_the_page(self):
        rec = record("TX")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "earlyVoting.start"]
        page = voting_dates.for_page(with_state("TX", rec))
        self.assertNotIn("TX", page["states"])
        self.assertIn("GA", page["states"])

    def test_a_postmark_or_receipt_rule_needs_words_that_say_it(self):
        # PR #102 review: South Dakota's "the form must arrive by then"
        # stood on a quote that gave only the date.
        rec = record("TX")
        for s in rec["sources"]:
            if s["field"] in ("registration.mail.deadline", "registration.mail.rule"):
                s["quote"] = "Voter registration deadline: October 5, 2026"
        self.assertProblem(with_state("TX", rec), "no quote it stands on says so")
        rec["registration"]["mail"]["rule"] = None
        self.assertEqual(voting_dates.problems(with_state("TX", rec)), [])

    def test_where_same_day_registration_happens_is_the_offices_words(self):
        # The research's summary was shown as if it were the office's.
        rec = record("WI")
        rec["registration"]["sameDay"]["where"] = "at the voter's polling place on Election Day"
        self.assertProblem(with_state("WI", rec), "is not in the office's words")

    def test_no_cache_is_an_error(self):
        self.assertEqual([i.code for i in validate.check_voting_dates(None)], ["voting-dates-missing"])


class TestThePage(unittest.TestCase):
    page = voting_dates.for_page(DATA)

    def lines(self, code, kind=None):
        return [l for l in self.page["states"][code]["lines"] if kind is None or l["k"] == kind]

    def test_every_line_cites_a_page(self):
        for code, entry in self.page["states"].items():
            for line in entry["lines"]:
                self.assertTrue(line["src"], f"{code} {line['k']}")
                for i in line["src"]:
                    self.assertTrue(voting_dates.official_source(entry["urls"][i], code)[0])

    def test_registration_deadlines_are_grouped_by_date_and_say_how(self):
        georgia = self.lines("GA", "register")
        self.assertEqual([l["d"] for l in georgia], ["2026-10-05"])
        self.assertEqual(georgia[0]["t"], "Last day to register to vote online, by mail or in person")
        louisiana = self.lines("LA", "register")
        self.assertEqual([l["d"] for l in louisiana], ["2026-10-05", "2026-10-13"])
        self.assertEqual(self.page["states"]["LA"]["register"], {"by": "2026-10-13", "how": "online",
                                                                  "sameDay": False})

    def test_same_day_registration_is_said_where_offered(self):
        self.assertTrue(self.page["states"]["NC"]["register"]["sameDay"])
        self.assertTrue(self.lines("NC", "sameday"))
        self.assertFalse(self.lines("GA", "sameday"))

    def test_a_same_day_states_deadline_is_never_the_last_chance(self):
        # PR #102 review: Illinois read "Today is the last day to register"
        # while grace-period registration ran to November 3, and every
        # same-day state's earlier deadlines read "Last day to register".
        for code, entry in self.page["states"].items():
            if not (entry.get("register") or {}).get("sameDay"):
                continue
            for line in entry["lines"]:
                if line["k"] == "register" and line["d"] < voting_dates.ELECTION:
                    self.assertTrue(line["t"].startswith("Regular deadline to register"), (code, line))
                    self.assertNotIn("closes", line["s"], code)
        illinois = self.page["states"]["IL"]["register"]
        self.assertEqual((illinois["by"], illinois["sameDay"]), ("2026-10-18", True))

    def test_the_same_day_words_are_quoted_from_the_linked_source(self):
        entry = self.page["states"]["WI"]
        line = self.lines("WI", "sameday")[0]
        self.assertIn("“Voters can register to vote at their polling place on Election Day", line["t"])
        self.assertEqual([entry["urls"][i] for i in line["src"]],
                         ["https://myvote.wi.gov/en-us/Voter-Deadlines"])

    def test_nevada_registers_online_through_election_day(self):
        # NRS 293.560(1)(a)(3); October 20 is only the last day to be mailed
        # a ballot (NRS 293.5837(2)).
        register = self.page["states"]["NV"]["register"]
        self.assertEqual((register["by"], register["how"]), ("2026-11-03", "online"))
        self.assertEqual([l["d"] for l in self.lines("NV", "mailreg")], ["2026-10-20"])

    def test_north_carolinas_same_day_registration_ends_with_early_voting(self):
        self.assertEqual(self.page["states"]["NC"]["register"]["through"], "2026-10-31")
        self.assertEqual(self.lines("NC", "sameday")[0]["d"], "2026-10-31")

    def test_a_ballot_still_arriving_after_election_day_is_kept(self):
        # PR #102 review: the Virgin Islands count ballots received by
        # November 13, and the line went at midnight on Election Day.
        line = self.lines("VI", "return")[0]
        self.assertEqual(line["d"], "2026-11-13")
        self.assertTrue(line["keep"])
        self.assertNotIn("keep", self.lines("GA", "return")[0])

    def test_a_local_runoffs_strip_label_says_so_and_turns_past(self):
        self.assertTrue(self.lines("MS", "runoff")[0]["s"].startswith("Judicial"))
        self.assertTrue(self.lines("AR", "runoff")[0]["s"].startswith("Local"))
        self.assertEqual(self.lines("GA", "runoff")[0]["sp"], "Runoff date")

    def test_wisconsins_early_voting_is_set_by_each_clerk(self):
        early = self.lines("WI", "early")[0]
        self.assertIn("each local election office sets", early["t"])

    def test_late_arriving_mail_ballots_are_kept_after_election_day(self):
        arrive = self.lines("CA", "arrive")
        self.assertEqual(arrive[0]["d"], "2026-11-10")
        self.assertTrue(arrive[0]["keep"])
        self.assertTrue(arrive[0]["p"].startswith("The last day"))
        # A state that counts only ballots received by Election Day has no
        # such line.
        self.assertFalse(self.lines("GA", "arrive"))

    def test_runoffs_say_what_they_decide_and_what_the_date_was(self):
        for code in ("GA", "LA", "AR", "MS", "GU", "VI", "MP"):
            runoff = self.lines(code, "runoff")
            self.assertEqual(len(runoff), 1, code)
            self.assertTrue(runoff[0]["p"].startswith("The date set for"), code)
            self.assertTrue(runoff[0]["keep"])
        self.assertIn("not for federal offices", self.lines("AR", "runoff")[0]["t"])
        self.assertIn("open primary", self.lines("LA", "runoff")[0]["t"])

    def test_no_election_and_no_registration_are_said_from_their_sources(self):
        self.assertEqual([l["k"] for l in self.page["states"]["PR"]["lines"]], ["none"])
        self.assertEqual(self.lines("ND", "noreg")[0]["t"], "North Dakota has no voter registration")
        self.assertNotIn("register", self.page["states"]["ND"])

    def test_a_time_of_day_is_shown_only_when_it_is_one(self):
        self.assertIn("by 7:00 pm on this day", self.lines("GA", "return")[0]["t"])
        # Texas's "7:00 pm (postmark); received by 5:00 pm November 4" is said
        # by its two dates instead.
        self.assertFalse(any("5:00 pm" in l["t"] for l in self.page["states"]["TX"]["lines"]))


class TestTheNorthernMarianaIslandsRunoff(unittest.TestCase):
    """The record said the Commonwealth's runoff date "depends on
    certification and is not yet set"; the Commonwealth Election Commission
    certified the results on November 6 and its 2026 Run-Off Election
    Important Dates give November 20 (read 2026-11-11). The date is the
    office's, not counted (rule 84), and the words say what 1 CMC 6509 holds
    a runoff for, never which race went to one: no Commission page says so,
    and this site reads no territory's result (rule 91)."""

    CALENDAR = "https://www.votecnmi.gov.mp/downloads/2026/2026_Run-Off-Election_Important_Dates.pdf"
    record = DATA["states"]["MP"]

    def sources(self, field):
        return [s for s in self.record["sources"] if s["field"] == field]

    def test_the_date_is_the_commissions_own(self):
        self.assertEqual(self.record["runoff"]["date"], "2026-11-20")
        first, *rest = self.sources("runoff.date")
        self.assertEqual(first["url"], self.CALENDAR)
        self.assertIn("NOVEMBER 20 2026 Run-Off Election", first["quote"])
        self.assertIn("NOVEMBER 06 Certification of the 2026 General Election results", first["quote"])
        self.assertEqual(first["read"], "2026-11-11")
        self.assertTrue(any("2026 Run-Off Election Day" in s["quote"] for s in rest))
        for source in self.sources("runoff.date") + self.sources("runoff.note"):
            self.assertEqual(voting_dates.official_source(source["url"], "MP"),
                             (True, "votecnmi.gov.mp"), source["url"])
        self.assertNotIn("not yet set", self.record["runoff"]["note"])

    def test_it_is_the_fourteenth_day_after_certification_as_the_law_counts_it(self):
        import datetime
        quotes = " ".join(s["quote"] for s in self.sources("runoff.note"))
        self.assertIn("The General Election results were certified on November 6, 2026.", quotes)
        self.assertIn("fourteen days after the Commonwealth Election Commission has certified", quotes)
        certified = datetime.date(2026, 11, 6)
        self.assertEqual((certified + datetime.timedelta(days=14)).isoformat(),
                         self.record["runoff"]["date"])

    def test_the_words_name_the_laws_offices_and_no_race_or_person(self):
        from kyc import statewide
        line = next(l for l in voting_dates.for_page(DATA)["states"]["MP"]["lines"] if l["k"] == "runoff")
        for words in (line["t"], line["p"], line["s"], line["sp"]):
            self.assertNotRegex(words, r"(?i)if (one is )?needed|Delegate|Congress")
        for words in (line["t"], line["p"]):
            self.assertIn("Governor and Lieutenant Governor, or for Attorney General", words)
            self.assertIn("Commonwealth Election Commission", words)
        self.assertTrue(line["keep"])
        self.assertEqual((line["s"], line["sp"]), ("Governor or attorney general runoff",
                                                   "Governor or attorney general runoff date"))
        cache = statewide.load(ROOT)
        names = [p["name"] for key in ("governor", "lt", "ag")
                 for p in (statewide.office(cache, "MP", key) or {}).get("candidates") or []]
        self.assertTrue(names)
        for name in names:
            surname = name.split(",")[0].strip().lower()
            for words in (line["t"], line["p"]):
                self.assertNotIn(surname, words.lower(), name)

    def test_the_line_links_the_calendar_and_says_the_day_it_was_read(self):
        entry = voting_dates.for_page(DATA)["states"]["MP"]
        line = next(l for l in entry["lines"] if l["k"] == "runoff")
        self.assertEqual([entry["urls"][i] for i in line["src"]], [self.CALENDAR])
        self.assertEqual(entry["reread"], [{"d": "2026-11-11", "labels": ["votecnmi.gov.mp"]}])

    def test_words_without_the_date_or_a_date_without_words_fail(self):
        rec = record("MP")
        rec["runoff"]["date"] = None
        self.assertTrue(any("RUNOFF_WORDS for a runoff the record does not hold" in p
                            for p in voting_dates.problems(with_state("MP", rec))))
        rec = record("MP")
        rec["sources"] = [s for s in rec["sources"] if s["field"] != "runoff.date"]
        self.assertTrue(any("MP runoff.date: shown with no source" in p
                            for p in voting_dates.problems(with_state("MP", rec))))


class TestARunoffsOwnDates(unittest.TestCase):
    """A runoff's own early voting and mail-ballot dates, kept as the
    general election's are (``runoff.earlyVoting``, ``runoff.mail``). The
    record gave a runoff only its date, so the Northern Mariana Islands'
    page never said that early voting for its November 20 runoff opened on
    November 13, though the Commission's runoff calendar says so (read
    2026-11-11). Each value is the office's own and sourced (rule 84); a
    null is a gap; the words never name which race went to a runoff, or who
    is in it (rule 91)."""

    CALENDAR = "https://www.votecnmi.gov.mp/downloads/2026/2026_Run-Off-Election_Important_Dates.pdf"
    GA_CALENDAR = "https://sos.ga.gov/sites/default/files/forms/2026%20Short%20Calendar%20.pdf"
    FIELDS = ("runoff.earlyVoting.start", "runoff.earlyVoting.end",
              "runoff.mail.requestDeadline.date", "runoff.mail.returnDeadline.date",
              "runoff.mail.returnDeadline.receivedBy")

    def page_lines(self, data, code):
        return voting_dates.for_page(data)["states"][code]["lines"]

    def assertProblem(self, data, text):
        found = voting_dates.problems(data)
        self.assertTrue(any(text in p for p in found), found)

    # ------------------------------------------------------------ the CNMI
    def test_the_commonwealths_runoff_dates_are_the_commissions_own(self):
        rec = DATA["states"]["MP"]["runoff"]
        self.assertEqual((rec["earlyVoting"]["start"], rec["earlyVoting"]["end"]),
                         ("2026-11-13", "2026-11-19"))
        self.assertEqual(rec["mail"]["requestDeadline"],
                         {"date": "2026-11-12", "rule": "received", "how": "in person"})
        self.assertEqual(rec["mail"]["returnDeadline"],
                         {"date": "2026-11-20", "time": None, "rule": "postmarked",
                          "receivedBy": "2026-12-04"})
        sources = DATA["states"]["MP"]["sources"]
        words = {"runoff.earlyVoting.start": "NOVEMBER 13 First day of early voting",
                 "runoff.earlyVoting.end": "NOVEMBER 19 Last day of (Run-Off) Early Voting",
                 "runoff.mail.requestDeadline.date":
                     "NOVEMBER 12 Last day to receive absentee ballot applications over the counter",
                 "runoff.mail.returnDeadline.receivedBy":
                     "DECEMBER 04 Last day to receive run-off election absentee ballots"}
        for field, quote in words.items():
            first, *rest = [s for s in sources if s["field"] == field]
            self.assertEqual(first["url"], self.CALENDAR, field)
            self.assertIn(quote, first["quote"], field)
            self.assertEqual(first["read"], "2026-11-11", field)
            # The home page's "Important Dates for Election 2026" give the
            # same days.
            self.assertTrue(any(s["url"] == "https://www.votecnmi.gov.mp/" for s in rest), field)
        postmark = [s for s in sources if s["field"] == "runoff.mail.returnDeadline.date"]
        self.assertIn("postmarked not later than the day of the runoff election", postmark[0]["quote"])
        for source in sources:
            if source["field"].startswith("runoff."):
                self.assertEqual(voting_dates.official_source(source["url"], "MP"),
                                 (True, "votecnmi.gov.mp"), source["url"])
        # The note no longer says the cache cannot hold them.
        self.assertNotIn("no fields for a runoff's own", rec["note"])

    def test_the_commonwealths_lines_follow_the_runoff_in_the_order_of_their_days(self):
        lines = [l for l in self.page_lines(DATA, "MP") if l["k"].startswith("runoff")]
        self.assertEqual([(l["k"], l["d"]) for l in lines], [
            ("runoff", "2026-11-20"), ("runoff-request", "2026-11-12"),
            ("runoff-early", "2026-11-13"), ("runoff-postmark", "2026-11-20"),
            ("runoff-arrive", "2026-12-04")])
        by = {l["k"]: l for l in lines}
        self.assertEqual(by["runoff-early"]["e"], "2026-11-19")
        self.assertEqual(by["runoff-early"]["t"], "In-person early voting for the runoff")
        self.assertEqual(by["runoff-request"]["t"],
                         "Last day to apply in person for an absentee ballot for the runoff")
        self.assertEqual(by["runoff-postmark"]["t"],
                         "Mail ballots for the runoff must be postmarked by this day")
        self.assertEqual(by["runoff-arrive"]["t"], "Mail ballots for the runoff postmarked by "
                                                   "November 20 are counted if they arrive by this day")
        # Each is kept after Election Day, until its own day has passed.
        self.assertTrue(all(l["keep"] for l in lines))
        entry = voting_dates.for_page(DATA)["states"]["MP"]
        self.assertEqual([entry["urls"][i] for i in by["runoff-early"]["src"]], [self.CALENDAR])
        # The arrive line says "postmarked", and stays after the postmark line
        # is gone: it links a quote that says so (rule 84), the law, never
        # the calendar alone, which gives the day and not the word (the second
        # reader of PR #237).
        linked = [entry["urls"][i] for i in by["runoff-arrive"]["src"]]
        self.assertTrue(linked)
        quotes = [s.get("quote") or "" for s in DATA["states"]["MP"]["sources"]
                  if s["url"] in linked and s["field"].startswith("runoff.mail.returnDeadline")]
        self.assertTrue(any("postmarked" in q for q in quotes), (linked, quotes))

    def test_the_words_name_no_race_and_nobody_and_the_runoff_is_set(self):
        from kyc import statewide
        lines = [l for l in self.page_lines(DATA, "MP") if l["k"].startswith("runoff-")]
        cache = statewide.load(ROOT)
        names = [p["name"] for key in ("governor", "lt", "ag")
                 for p in (statewide.office(cache, "MP", key) or {}).get("candidates") or []]
        self.assertTrue(names)
        for line in lines:
            for words in (line["t"], line["s"], line.get("p", "")):
                # The Commission has set it: never "if one is held".
                self.assertNotRegex(words, r"(?i)if (one is )?(held|needed)|Delegate|Congress|Governor")
                for name in names:
                    self.assertNotIn(name.split(",")[0].strip().lower(), words.lower(), name)

    # ------------------------------------------------------------ Georgia
    def test_georgias_advance_voting_for_a_runoff_may_begin_before_its_date(self):
        rec = DATA["states"]["GA"]["runoff"]
        self.assertEqual(rec["earlyVoting"]["start"], "2026-11-23")
        self.assertIs(rec["earlyVoting"]["startsBy"], True)
        source = next(s for s in DATA["states"]["GA"]["sources"]
                      if s["field"] == "runoff.earlyVoting.start")
        self.assertEqual(source["url"], self.GA_CALENDAR)
        self.assertIn("Runoff 12/01/2026 As soon as possible, but no later than 11/23/26 – 11/25/26",
                      source["quote"])
        early = [l for l in self.page_lines(DATA, "GA") if l["k"] == "runoff-early"]
        self.assertEqual(len(early), 1)
        self.assertEqual((early[0]["d"], early[0]["e"]), ("2026-11-23", "2026-11-25"))
        # A runoff Georgia holds only if one is needed: said so, and that
        # November 23 is the latest start, not the first day.
        self.assertEqual(early[0]["t"], "In-person early voting for a runoff, if one is held; it "
                                        "begins as soon as possible, and no later than November 23")
        self.assertEqual(early[0]["s"], "Runoff early voting, if needed")

    def test_georgias_null_mail_dates_add_no_line(self):
        # No Secretary of State page gives the runoff's own absentee dates:
        # null, a gap, and nothing on the page.
        mail = DATA["states"]["GA"]["runoff"]["mail"]
        self.assertTrue(all(v is None for part in mail.values() if isinstance(part, dict)
                            for v in part.values()))
        kinds = [l["k"] for l in self.page_lines(DATA, "GA")]
        self.assertEqual([k for k in kinds if k.startswith("runoff")], ["runoff", "runoff-early"])
        # And without the early voting, Georgia's lines are the ones it had.
        rec = record("GA")
        del rec["runoff"]["earlyVoting"], rec["runoff"]["mail"]
        before = self.page_lines(with_state("GA", rec), "GA")
        self.assertEqual(before, [l for l in self.page_lines(DATA, "GA") if l["k"] != "runoff-early"])
        rec = record("GA")
        rec["runoff"]["earlyVoting"] = {"start": None, "end": None, "startsBy": None}
        self.assertEqual(self.page_lines(with_state("GA", rec), "GA"), before)

    # ------------------------------------------------------------ check()
    def test_each_value_needs_its_own_source(self):
        for field in self.FIELDS:
            rec = record("MP")
            rec["sources"] = [s for s in rec["sources"] if s["field"] != field]
            self.assertProblem(with_state("MP", rec), f"MP {field}: shown with no source")

    def test_a_compiled_table_is_no_source_for_them_either(self):
        rec = record("MP")
        for s in rec["sources"]:
            if s["field"] == "runoff.earlyVoting.start":
                s["url"] = "https://ballotpedia.org/Northern_Mariana_Islands"
        self.assertProblem(with_state("MP", rec), "rule 50")

    def test_the_days_fall_between_the_election_and_the_runoff(self):
        cases = [
            ("earlyVoting", "end", "2026-11-20", "does not run forwards between the election and "
                                                 "the runoff"),
            ("earlyVoting", "start", "2026-11-03", "does not run forwards"),
            ("earlyVoting", "end", None, "a window with one end"),
            ("earlyVoting", "start", "2026-11-31", "is not a date"),
        ]
        for part, key, value, text in cases:
            rec = record("MP")
            rec["runoff"][part][key] = value
            self.assertProblem(with_state("MP", rec), text)
        rec = record("MP")
        rec["runoff"]["mail"]["requestDeadline"]["date"] = "2026-11-21"
        self.assertProblem(with_state("MP", rec), "runoff.mail.requestDeadline.date: 2026-11-21 is "
                                                  "not between the election and the runoff")
        rec = record("MP")
        rec["runoff"]["mail"]["returnDeadline"]["date"] = "2026-11-03"
        self.assertProblem(with_state("MP", rec), "runoff.mail.returnDeadline.date: 2026-11-03 is "
                                                  "not between")
        rec = record("MP")
        rec["runoff"]["mail"]["returnDeadline"]["receivedBy"] = "2026-11-19"
        self.assertProblem(with_state("MP", rec), "received by 2026-11-19, before 2026-11-20")
        rec = record("MP")
        rec["runoff"]["mail"]["returnDeadline"]["receivedBy"] = "2026-11-20"
        self.assertProblem(with_state("MP", rec), "postmarked, yet received the same day")
        rec = record("MP")
        rec["runoff"]["mail"]["returnDeadline"]["receivedBy"] = "2027-01-04"
        self.assertProblem(with_state("MP", rec), "outside the cycle")

    def test_none_stands_without_the_runoffs_date(self):
        rec = record("TX")
        rec["runoff"]["earlyVoting"] = {"start": "2026-11-28", "end": "2026-12-08"}
        rec["sources"] += [{"field": "runoff.earlyVoting.start", "url": "https://www.sos.texas.gov/x",
                            "quote": "x"},
                           {"field": "runoff.earlyVoting.end", "url": "https://www.sos.texas.gov/x",
                            "quote": "x"}]
        self.assertProblem(with_state("TX", rec), "TX runoff.earlyVoting.start: a runoff's own date, "
                                                  "with no runoff date in the record")
        # And a record that breaks a rule is not sent to the page at all.
        self.assertNotIn("TX", voting_dates.for_page(with_state("TX", rec))["states"])

    def test_a_qualifier_is_said_in_a_quote_it_stands_on(self):
        # A latest start needs the office's words that early voting may begin
        # sooner ("as soon as possible, but no later than").
        rec = record("GA")
        for s in rec["sources"]:
            if s["field"] == "runoff.earlyVoting.start":
                s["quote"] = "General Election/Special Election Runoff 12/01/2026 11/23/26 – 11/25/26"
        self.assertProblem(with_state("GA", rec),
                           "GA runoff.earlyVoting.startsBy: shown, but no quote it stands on says so")
        rec = record("GA")
        rec["runoff"]["earlyVoting"]["start"] = rec["runoff"]["earlyVoting"]["end"] = None
        self.assertProblem(with_state("GA", rec), "a latest start with no start")
        # An application taken in person alone needs words that say so.
        rec = record("MP")
        for s in rec["sources"]:
            if s["field"] == "runoff.mail.requestDeadline.date":
                s["quote"] = s["quote"].replace("over the counter", "")
        self.assertProblem(with_state("MP", rec), "MP runoff.mail.requestDeadline.how: shown, but no "
                                                  "quote it stands on says so")
        rec = record("MP")
        rec["runoff"]["mail"]["requestDeadline"]["how"] = "by fax"
        self.assertProblem(with_state("MP", rec), "'by fax' is not one of")
        # "Postmarked" stands on a quote that says so, as the general's does.
        rec = record("MP")
        rec["sources"] = [s for s in rec["sources"]
                          if not (s["field"] == "runoff.mail.returnDeadline.date")]
        rec["sources"].append({"field": "runoff.mail.returnDeadline.date", "url": self.CALENDAR,
                               "quote": "NOVEMBER 20 2026 Run-Off Election"})
        self.assertProblem(with_state("MP", rec), "MP runoff.mail.returnDeadline.rule: 'postmarked', "
                                                  "but no quote it stands on says so")

    def test_a_received_by_runoff_ballot_and_an_application_by_mail_read_as_the_generals(self):
        rec = record("GA")
        rec["runoff"]["mail"] = {"requestDeadline": {"date": "2026-11-20", "rule": "received"},
                                 "returnDeadline": {"date": "2026-12-01", "time": "7:00 pm",
                                                    "rule": "received", "receivedBy": "2026-12-01"}}
        rec["sources"] += [
            {"field": "runoff.mail.requestDeadline.date", "url": self.GA_CALENDAR,
             "quote": "must be received 11 days before the runoff"},
            {"field": "runoff.mail.returnDeadline.date", "url": self.GA_CALENDAR,
             "quote": "must be received by the close of the polls on the day of the runoff"},
            {"field": "runoff.mail.returnDeadline.receivedBy", "url": self.GA_CALENDAR,
             "quote": "must be received by the close of the polls on the day of the runoff"}]
        data = with_state("GA", rec)
        self.assertEqual(voting_dates.problems(data), [])
        by = {l["k"]: l for l in self.page_lines(data, "GA")}
        self.assertEqual(by["runoff-request"]["t"], "Last day to apply for a mail ballot for a runoff, "
                                                    "if one is held (the application must arrive by then)")
        self.assertEqual(by["runoff-return"]["t"], "Mail ballots for a runoff, if one is held, must "
                                                   "arrive at the election office by 7:00 pm on this day")
        self.assertEqual(by["runoff-return"]["s"], "Runoff mail ballots due, if needed")


class TestMoreRunoffsOwnDates(unittest.TestCase):
    """The other runoffs' own dates, each the office's own words for that
    runoff, read 2026-11-12 (rule 84): the Virgin Islands' November 17
    runoff (the Elections System's 2026 calendar), Louisiana's December 12
    general election for U.S. House seats (the Secretary of State's
    election-dates page), Arkansas's and Mississippi's December 1 runoffs
    (each Secretary of State's 2026 calendar). Guam's Election Commission
    publishes none: null, a gap, and nothing on the page. The words never
    name which race went to one, or who is in it (rule 91)."""

    VI_CAL = "https://vivote.gov/wp-content/uploads/2026/07/2026-Elections-Calendar-Amended-06.10.2026.pdf"
    LA_DATES = "https://www.sos.la.gov/elections-voting/election-dates"
    AR_CAL = "http://www.sos.arkansas.gov/uploads/elections/2026_Election_Calendar_Rev._7-2026_.pdf"
    MS_CAL = "https://www.sos.ms.gov/content/documents/elections/2026%20Elections%20Calendar.pdf"
    page = voting_dates.for_page(DATA)

    def own(self, code):
        """The runoff's own lines (not the runoff's), by kind."""
        return {l["k"]: l for l in self.page["states"][code]["lines"] if l["k"].startswith("runoff-")}

    def linked(self, code, line):
        entry = self.page["states"][code]
        return [entry["urls"][i] for i in line["src"]]

    def first(self, code, field):
        return next(s for s in DATA["states"][code]["sources"] if s["field"] == field)

    def test_the_virgin_islands_dates_are_the_elections_systems_calendar(self):
        rec = DATA["states"]["VI"]["runoff"]
        self.assertEqual((rec["earlyVoting"]["start"], rec["earlyVoting"]["end"]),
                         ("2026-11-14", "2026-11-15"))
        self.assertEqual(rec["mail"]["requestDeadline"],
                         {"date": "2026-11-10", "rule": "received", "how": None})
        # No page gives the day a runoff's mailed ballot must arrive: null.
        self.assertTrue(all(v is None for v in rec["mail"]["returnDeadline"].values()))
        start = self.first("VI", "runoff.earlyVoting.start")
        self.assertEqual(start["url"], self.VI_CAL)
        # Between the general election's certification and the runoff: the
        # runoff's early voting, in the calendar's own words.
        for words in ("13-November (Friday) CERTIFICATION OF THE GENERAL ELECTION RESULTS",
                      "14-November (Saturday) FIRST DAY OF EARLY VOTING", "RUN-OFF ELECTION DAY"):
            self.assertIn(words, start["quote"])
        self.assertIn("15-November (Sunday) LAST DAY OF EARLY VOTING",
                      self.first("VI", "runoff.earlyVoting.end")["quote"])
        self.assertIn("DEADLINE for receipt by the Supervisor of Elections of applications for "
                      "Mail Out ABSENTEE BALLOTS for the RUN OFF ELECTION",
                      self.first("VI", "runoff.mail.requestDeadline.date")["quote"])
        for source in DATA["states"]["VI"]["sources"]:
            if source["field"].startswith(("runoff.earlyVoting", "runoff.mail")):
                self.assertEqual(source["read"], "2026-11-12", source["field"])
                self.assertEqual(voting_dates.official_source(source["url"], "VI"),
                                 (True, "vivote.gov"), source["url"])
        own = self.own("VI")
        self.assertEqual(sorted(own), ["runoff-early", "runoff-request"])
        self.assertEqual(own["runoff-early"]["t"], "In-person early voting for a runoff, if one is held")
        self.assertEqual(own["runoff-early"]["s"], "Runoff early voting, if needed")
        self.assertEqual(own["runoff-request"]["t"], "Last day to apply for a mail ballot for a runoff, "
                                                     "if one is held (the application must arrive by then)")
        self.assertEqual(self.linked("VI", own["runoff-early"]), [self.VI_CAL])

    def test_louisianas_december_12_is_a_general_election_not_a_runoff(self):
        rec = DATA["states"]["LA"]["runoff"]
        self.assertEqual((rec["earlyVoting"]["start"], rec["earlyVoting"]["end"]),
                         ("2026-11-28", "2026-12-05"))
        self.assertEqual(rec["mail"]["requestDeadline"]["date"], "2026-12-08")
        # No quoted word says the request must arrive by then, as November 3's.
        self.assertIsNone(rec["mail"]["requestDeadline"]["rule"])
        self.assertEqual(rec["mail"]["returnDeadline"], {"date": "2026-12-11", "time": "4:30 pm",
                                                         "rule": "received", "receivedBy": "2026-12-11"})
        for field, words in (("runoff.earlyVoting.start", "Early voting is November 28-December 5 "
                                                          "(excluding Sunday, November 29)"),
                             ("runoff.mail.requestDeadline.date", "The deadline to request an "
                                                                  "absentee ballot is December 8"),
                             ("runoff.mail.returnDeadline.receivedBy", "to receive a voted absentee "
                                                                       "ballot is December 11 by 4:30")):
            source = self.first("LA", field)
            self.assertEqual(source["url"], self.LA_DATES)
            self.assertIn("important information for the Saturday, December 12, 2026 Election",
                          source["quote"])
            self.assertIn(words, source["quote"])
        own = self.own("LA")
        self.assertEqual([(k, own[k]["d"]) for k in ("runoff-early", "runoff-request", "runoff-return")],
                         [("runoff-early", "2026-11-28"), ("runoff-request", "2026-12-08"),
                          ("runoff-return", "2026-12-11")])
        self.assertEqual(own["runoff-early"]["t"],
                         "In-person early voting for a U.S. House general election, if one is held")
        self.assertEqual(own["runoff-return"]["t"],
                         "Mail ballots for a U.S. House general election, if one is held, must arrive "
                         "at the election office by 4:30 pm on this day")
        for line in own.values():
            # Its own words call it a general election, never a runoff.
            self.assertNotRegex(line["t"] + " " + line["s"], r"(?i)runoff")
            self.assertTrue(line["s"].startswith("House general "), line["s"])
            self.assertEqual(self.linked("LA", line), [self.LA_DATES])

    def test_arkansas_and_mississippi_dates_say_whose_runoff_on_the_strip(self):
        ar = DATA["states"]["AR"]["runoff"]
        self.assertEqual((ar["earlyVoting"]["start"], ar["earlyVoting"]["end"]),
                         ("2026-11-24", "2026-11-30"))
        self.assertEqual(ar["mail"]["returnDeadline"], {"date": "2026-12-01", "time": "7:30 pm",
                                                        "rule": "received", "receivedBy": "2026-12-01"})
        # The calendar puts in-person applications under November 27 and calls
        # them due "the day before the election": the days disagree, so null.
        self.assertIsNone(ar["mail"]["requestDeadline"]["date"])
        self.assertIn("Early voting for the general runoff election shall be available",
                      self.first("AR", "runoff.earlyVoting.start")["quote"])
        self.assertIn("“instant runoff” ballots", self.first("AR", "runoff.mail.returnDeadline.date")["quote"])
        ms = DATA["states"]["MS"]["runoff"]
        # Mississippi has no early voting; its runoff none either.
        self.assertIsNone(ms["earlyVoting"]["start"])
        self.assertEqual(ms["mail"]["returnDeadline"], {"date": "2026-12-01", "time": None,
                                                        "rule": "postmarked", "receivedBy": "2026-12-08"})
        self.assertIn("8th Absentee Ballots Returned by Mail Receipt Deadline for the General Election "
                      "Runoff", self.first("MS", "runoff.mail.returnDeadline.receivedBy")["quote"])
        self.assertEqual(sorted(self.own("AR")), ["runoff-early", "runoff-return"])
        self.assertEqual(sorted(self.own("MS")), ["runoff-arrive", "runoff-postmark"])
        self.assertEqual(self.own("MS")["runoff-arrive"]["t"],
                         "Mail ballots for a runoff, if one is held, postmarked by December 1 are counted "
                         "if they arrive by this day")
        # Neither is a runoff for Congress, so no strip cell says a bare
        # "Runoff" (PR #102 review): each names whose runoff it is, as the
        # runoff's own cell does.
        for code, name in (("AR", "Local runoff "), ("MS", "Judicial, school board runoff ")):
            for line in self.own(code).values():
                self.assertTrue(line["s"].startswith(name), line["s"])
                self.assertTrue(line["keep"])
        self.assertEqual(self.linked("AR", self.own("AR")["runoff-early"]), [self.AR_CAL])

    def test_guams_commission_publishes_none_so_nothing_is_shown(self):
        rec = DATA["states"]["GU"]["runoff"]
        self.assertTrue(all(v is None for v in rec["earlyVoting"].values()))
        self.assertTrue(all(v is None for part in rec["mail"].values() for v in part.values()))
        self.assertIn("No Guam Election Commission page read on 2026-11-12", rec["note"])
        self.assertEqual(self.own("GU"), {})
        self.assertEqual([l["k"] for l in self.page["states"]["GU"]["lines"] if l["k"].startswith("runoff")],
                         ["runoff"])

    def test_every_strip_label_names_the_runoff_as_the_record_does(self):
        for code, entry in self.page["states"].items():
            what, name = voting_dates.RUNOFF_OWN.get(code, voting_dates.RUNOFF_OWN_DEFAULT)
            held = code in voting_dates.RUNOFF_SET
            for line in self.own(code).values():
                self.assertTrue(line["s"].startswith(name + " "), (code, line["s"]))
                if not held:
                    self.assertIn(f"for {what}, if one is held", line["t"], code)

    def test_the_words_name_no_race_and_nobody(self):
        from kyc import statewide
        cache = statewide.load(ROOT)
        for code in ("VI", "LA", "AR", "MS", "GA", "MP"):
            names = [p["name"] for key in ("governor", "lt", "ag", "sos")
                     for p in (statewide.office(cache, code, key) or {}).get("candidates") or []]
            for line in self.own(code).values():
                words = " ".join((line["t"], line["s"], line.get("p", "")))
                self.assertNotRegex(words, r"(?i)\b(?:District|Delegate|Senate|Governor)\b", code)
                for name in names:
                    surname = name.split(",")[0].split()[-1].strip().lower()
                    self.assertNotRegex(words.lower(), rf"\b{re.escape(surname)}\b", (code, name))


class TestArriveLinesSayPostmarked(unittest.TestCase):
    """A line that says ballots "postmarked by" one day count if they arrive
    by another links a quote that says "postmarked" (rule 84), on the general
    election's line as on a runoff's. The general election's line linked the
    arrival day's source alone, and in Illinois, Mississippi, Nevada and
    Virginia that quote gives the day and never the word (the reader of PR
    #237); from the day after the election the postmark line that linked one
    is gone."""

    page = voting_dates.for_page(DATA)
    PARTS = {"arrive": "mail.returnDeadline", "runoff-arrive": "runoff.mail.returnDeadline",
             "postmark": "mail.returnDeadline", "runoff-postmark": "runoff.mail.returnDeadline"}

    def test_every_arrive_lines_linked_quote_says_postmarked_in_every_jurisdiction(self):
        seen = set()
        for code, entry in self.page["states"].items():
            sources = DATA["states"][code]["sources"]
            for line in entry["lines"]:
                part = self.PARTS.get(line["k"])
                if not part:
                    continue
                seen.add((code, line["k"]))
                fields = (f"{part}.receivedBy", f"{part}.date", f"{part}.rule")
                self.assertTrue(line["src"], (code, line["k"]))
                for i in line["src"]:
                    url = entry["urls"][i]
                    quotes = [s["quote"] for s in sources if s["url"] == url and s["field"] in fields]
                    self.assertTrue(any(voting_dates.RULE_WORDS["postmarked"].search(q) for q in quotes),
                                    (code, line["k"], url, quotes))
        # Every postmarked state's and runoff's arrive line was asked.
        self.assertTrue({("IL", "arrive"), ("MS", "arrive"), ("NV", "arrive"), ("VA", "arrive"),
                         ("MP", "runoff-arrive"), ("MS", "runoff-arrive")} <= seen, seen)

    def test_the_arrival_days_own_quote_is_linked_only_where_it_says_postmarked(self):
        # Made, not the day's data: the arrival day's source on one page says
        # only the day, the postmark day's on another says the word.
        rec = record("IL")
        rec["sources"] = [s for s in rec["sources"] if not s["field"].startswith("mail.returnDeadline")]
        rec["sources"] += [
            {"field": "mail.returnDeadline.date", "url": "https://www.elections.il.gov/postmark",
             "quote": "Ballots must be postmarked on or before November 3."},
            {"field": "mail.returnDeadline.receivedBy", "url": "https://www.elections.il.gov/arrive",
             "quote": "They must arrive by November 17 to be counted."}]
        data = with_state("IL", rec)
        self.assertEqual(voting_dates.problems(data), [])
        entry = voting_dates.for_page(data)["states"]["IL"]
        arrive = next(l for l in entry["lines"] if l["k"] == "arrive")
        self.assertEqual([entry["urls"][i] for i in arrive["src"]], ["https://www.elections.il.gov/postmark"])
        # Where the arrival day's own quote says it, that one is linked first.
        rec["sources"][-1]["quote"] = "Ballots postmarked by November 3 must arrive by November 17."
        entry = voting_dates.for_page(with_state("IL", rec))["states"]["IL"]
        arrive = next(l for l in entry["lines"] if l["k"] == "arrive")
        self.assertEqual([entry["urls"][i] for i in arrive["src"]], ["https://www.elections.il.gov/arrive"])

    def test_mississippis_line_links_the_calendar_that_says_both(self):
        # Its absentee page's receipt quote gives November 10 and never the
        # word; the calendar's gives the day and "postmarked on or before
        # Election Day".
        entry = self.page["states"]["MS"]
        arrive = next(l for l in entry["lines"] if l["k"] == "arrive")
        self.assertEqual([entry["urls"][i] for i in arrive["src"]],
                         ["https://www.sos.ms.gov/content/documents/elections/2026%20Elections%20Calendar.pdf"])


class TestVoteGov(unittest.TestCase):
    def test_vote_gov_deadlines_only_where_the_record_has_none(self):
        cache = voting.load_cache(ROOT)
        shown = voting.for_page(cache, DATA)
        self.assertNotIn("deadlines", shown["TX"])
        self.assertNotIn("deadlines", shown["ND"])
        self.assertNotIn("deadlines", shown["GU"])
        self.assertIn("deadlines", shown["NH"])          # no deadline in its record
        self.assertIn("TX", shown["_dates"]["states"])
        # Without the record, every jurisdiction keeps vote.gov's page.
        self.assertIn("deadlines", voting.for_page(cache)["TX"])


if __name__ == "__main__":
    unittest.main()
