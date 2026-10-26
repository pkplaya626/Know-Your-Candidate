"""The candidates for governor and the statewide offices (kyc/statewide.py,
rule 91).

States marked 36 governorships and some 90 other offices "on the Nov 3,
2026 ballot" and named no one running for any of them (audit 2026-10-17,
FRESHNESS-05, STATEGOV-14, PERSONA-08, RACES-16). The lists are each
election office's own, and the office's holder is read from them for
whoever the rosters name today.
"""

import copy
import unittest
from unittest import mock

from kyc import ballot2026, stategov, statewide

LIST = "https://sos.ga.gov/a-list.pdf"


def office(**over):
    """A synthetic Georgia governor's list that keeps every rule."""
    out = {
        "title": "Governor", "certified": False,
        "list": {"url": LIST, "title": "A list", "quote": "Governor | Pat Example | R",
                 "by": "Georgia Secretary of State", "dated": None, "read": "2026-10-18",
                 "kind": "candidate list"},
        "holderResearched": "Brian Kemp", "holderOnList": False,
        "candidates": [
            {"name": "Pat Example", "surname": "Example", "party": "R", "runningMate": None,
             "writeIn": False, "holder": False},
            {"name": "Lee Sample", "surname": "Sample", "party": "D", "runningMate": None,
             "writeIn": False, "holder": False},
        ],
    }
    out.update(over)
    return out


class TestTheCache(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cache = statewide.load(".")

    def test_the_committed_cache_keeps_every_rule(self):
        self.assertEqual(statewide.problems(self.cache), [])

    def test_it_lists_exactly_the_offices_on_the_ballot(self):
        every = dict(ballot2026.STATES, **ballot2026.TERRITORIES)
        for code, entry in every.items():
            up = {k for k in ballot2026.OFFICES if k in entry and entry[k][1]}
            have = set(((self.cache["states"].get(code) or {}).get("offices")) or {})
            self.assertEqual(up, have, code)

    def broken(self, mutate):
        cache = copy.deepcopy(self.cache)
        mutate(cache)
        return " | ".join(statewide.problems(cache))

    def test_an_office_on_the_ballot_with_no_list_fails(self):
        self.assertIn("with no list", self.broken(
            lambda c: c["states"]["GA"]["offices"].pop("governor")))

    def test_a_list_for_an_office_not_on_the_ballot_fails(self):
        def add(c):
            c["states"]["VA"] = {"offices": {"governor": office()}}
        self.assertIn("does not put on the 2026 ballot", self.broken(add))

    def test_a_compiled_table_is_never_the_source(self):
        def wiki(c):
            c["states"]["GA"]["offices"]["lt"]["list"]["url"] = \
                "https://ballotpedia.org/Georgia_elections,_2026"
        self.assertIn("compiled table", self.broken(wiki))

    def test_another_jurisdictions_office_is_not_this_ones(self):
        def elsewhere(c):
            c["states"]["FL"]["offices"]["ag"]["list"]["url"] = LIST
        self.assertIn("not an election office's list", self.broken(elsewhere))

    def test_a_list_needs_its_quote_and_the_day_it_was_read(self):
        def bare(c):
            lst = c["states"]["GA"]["offices"]["lt"]["list"]
            lst["quote"] = ""
            lst["read"] = "yesterday"
        found = self.broken(bare)
        self.assertIn("no quote", found)
        self.assertIn("is not a date", found)

    def test_a_list_names_the_kind_of_document_it_is(self):
        self.assertIn("the source has no kind", self.broken(
            lambda c: c["states"]["GA"]["offices"]["lt"]["list"].pop("kind")))

    # "Certified" is the document's word, never the researcher's (PR #109
    # review: a county's sample ballot read "Certified by" the county).
    def test_certified_needs_the_documents_own_words(self):
        self.assertIn("needs the document's own words", self.broken(
            lambda c: c["states"]["GA"]["offices"]["lt"].update(certified=True)))

        def unrecorded(c):
            c["states"]["GA"]["offices"]["lt"].update(certified=True,
                                                      certifiedQuote="certified by nobody")
        self.assertIn("needs the document's own words", self.broken(unrecorded))

        def stray(c):
            c["states"]["CA"]["offices"]["lt"]["certified"] = False
        found = self.broken(stray)
        self.assertIn("'certifiedQuote' on a list not marked certified", found)
        self.assertIn("says certified; the list is not marked so", found)

    def test_a_county_list_is_never_the_states_certification(self):
        def county(c):
            o = c["states"]["AR"]["offices"]["governor"]
            o.update(certified=True, certifiedQuote="certified Notice")
            o["notes"] = (o.get("notes") or "") + " certified Notice"
        self.assertIn("is not the state's election office", self.broken(county))

    def test_a_list_that_is_not_the_states_says_why(self):
        self.assertIn("says why ('notStateList')", self.broken(
            lambda c: c["states"]["AR"]["offices"]["ag"].pop("notStateList")))
        self.assertIn("'notStateList' on the state's own list", self.broken(
            lambda c: c["states"]["GA"]["offices"]["ag"].update(notStateList="why")))

    def test_an_elsewhere_entry_no_list_uses_is_reported(self):
        with mock.patch.dict("kyc.overrides.STATEWIDE_LISTS_ELSEWHERE",
                             {"https://www.example-county.gov/": (("FL",), "A county", False,
                                                                  "evidence")}):
            found = " | ".join(statewide.problems(self.cache))
        self.assertIn("https://www.example-county.gov/ is no list's source", found)

    def test_a_party_code_with_no_words_is_refused(self):
        def code(c):
            c["states"]["GA"]["offices"]["lt"]["candidates"][0]["party"] = "XYZ"
        self.assertIn("party 'XYZ' is a code the page cannot spell out", self.broken(code))

    def test_a_record_of_ones_own_is_an_election_offices(self):
        def record(c):
            c["states"]["GA"]["offices"]["lt"]["candidates"][0]["record"] = \
                "https://ballotpedia.org/Someone"
        self.assertIn("is not an election office's", self.broken(record))

    def test_no_portrait_money_or_platform_for_these_people(self):
        def photo(c):
            c["states"]["GA"]["offices"]["lt"]["candidates"][0]["photo"] = "https://x/y.jpg"
        self.assertIn("fields a list does not print: photo", self.broken(photo))

    def test_two_holders_on_one_list_fail(self):
        def two(c):
            for p in c["states"]["GA"]["offices"]["lt"]["candidates"]:
                p["holder"] = True
        self.assertIn("marked as the holder", self.broken(two))

    def test_a_holder_said_off_the_list_whose_surname_is_on_it_fails(self):
        def namesake(c):
            o = c["states"]["GA"]["offices"]["governor"]
            o["candidates"][0]["name"] = "Pat Kemp"
            o["candidates"][0]["surname"] = "Kemp"
        self.assertIn("is said not to be on the list", self.broken(namesake))

    def test_a_namesake_needs_to_be_on_the_list_and_say_why(self):
        def stray(c):
            c["states"]["TN"]["offices"]["governor"]["namesakes"]["Nobody Here"] = ""
        found = self.broken(stray)
        self.assertIn("is not on the list", found)
        self.assertIn("says nothing of why", found)

    def test_every_list_not_the_states_says_so_and_is_never_certified(self):
        seen = 0
        for code, entry in self.cache["states"].items():
            for key, o in entry["offices"].items():
                if statewide.not_the_states(o["list"]):
                    seen += 1
                    self.assertTrue(o["notStateList"].strip(), (code, key))
                    self.assertFalse(o["certified"], (code, key))
                if o["certified"]:
                    self.assertIn("certif", o["certifiedQuote"].lower(), (code, key))
        self.assertTrue(seen)


class TestNames(unittest.TestCase):

    def test_surnames_as_lists_print_them(self):
        self.assertEqual(statewide.surname("Lombardo, Joseph"), "Lombardo")
        self.assertEqual(statewide.surname("Leland Jake Olinger, II"), "Olinger")
        self.assertEqual(statewide.surname("Brian P. Kemp"), "Kemp")
        self.assertEqual(statewide.surname('Kreiss-Tomkins, Jonathan S. “JKT”'), "Kreiss-Tomkins")
        self.assertEqual(statewide.surname("ROBERT E BROOKS SR"), "BROOKS")

    def test_a_short_given_name_is_the_same_one(self):
        self.assertTrue(statewide.same_given_name("Kim Driscoll", "Kimberley Driscoll"))
        self.assertTrue(statewide.same_given_name("Sarah Huckabee Sanders",
                                                  "Governor Sarah Huckabee Sanders"))
        self.assertTrue(statewide.same_given_name("Raúl Torrez", "RAUL TORREZ"))

    def test_a_hyphen_and_a_space_are_one_spelling(self):
        # Rule 77: "Kim-Varet" and "Kim Varet".
        self.assertTrue(statewide.has_surname("Kim-Varet", "Jane Kim Varet"))
        self.assertTrue(statewide.has_surname("Varet", "Jane Kim-Varet"))
        self.assertTrue(statewide.has_surname("Kreiss-Tomkins", "Kreiss-Tomkins, Jonathan S."))
        self.assertFalse(statewide.has_surname("Kim-Varet", "Varet Kim"))

    def test_names_shown_first_name_first_in_ordinary_capitals(self):
        shown = statewide.display_name
        self.assertEqual(shown("Ford, Aaron D."), "Aaron D. Ford")
        self.assertEqual(shown("JOSH SHAPIRO"), "Josh Shapiro")
        self.assertEqual(shown("JEFF McLAUGHLIN"), "Jeff McLaughlin")
        self.assertEqual(shown("SAMUEL ISAIAH KANE, SR"), "Samuel Isaiah Kane Sr.")
        self.assertEqual(shown("Leland Jake Olinger, II"), "Leland Jake Olinger II")
        self.assertEqual(shown("ADA, Vicente A."), "Vicente A. Ada")
        self.assertEqual(shown("Governor Sarah Huckabee Sanders"), "Sarah Huckabee Sanders")
        self.assertEqual(shown("State Senator Fred Love"), "Fred Love")
        self.assertEqual(shown("Greer, Ramadhani “Ram” (Registered Democrat)"),
                         "Ramadhani “Ram” Greer (Registered Democrat)")
        # Mixed case is the list's own: kept.
        self.assertEqual(shown("JB Pritzker"), "JB Pritzker")
        self.assertEqual(shown("Kreiss-Tomkins, Jonathan S. “JKT”"),
                         "Jonathan S. “JKT” Kreiss-Tomkins")
        self.assertEqual(shown("AMANDA LÓPEZ ASKIN"), "Amanda López Askin")
        # Florida's "Arias, V. Michael": a first initial, not a suffix (rule 77).
        self.assertEqual(shown("Arias, V. Michael"), "V. Michael Arias")

    def test_parties_in_words(self):
        words = statewide.party_words
        self.assertEqual(words("FL", "LPF"), "Libertarian Party of Florida")
        self.assertEqual(words("FL", "NPA"), "No Party Affiliation")
        # A list's own words are kept: Nevada's certified list spells out
        # "Independent American Party".
        self.assertEqual(words("NV", "Independent American Party"), "Independent American Party")
        self.assertEqual(words("PA", "DEM"), "Democratic")
        # One party, one word on every state page (wave 2d review).
        self.assertEqual(words("GU", "DEMOCRAT"), "Democratic")
        self.assertEqual(words("AL", "Democrat"), "Democratic")
        self.assertEqual(words("LA", "Registered Democrat"), "Registered Democrat")
        self.assertEqual(words("GA", "R"), "Republican")
        self.assertEqual(words("VT", "FREEDOM AND UNITY"), "Freedom and Unity")
        self.assertEqual(words("TX", "GREEN"), "Green")
        self.assertEqual(words("ND", "Democratic-NPL"), "Democratic-NPL")
        # PR #140 review: Nevada's list's "Democratic Party" sat under a
        # holder line reading "Democratic". The major parties read as one
        # word, each part of a fusion line alike; a minor party's own name,
        # or a state's branch of one, is the list's.
        self.assertEqual(words("NV", "Democratic Party"), "Democratic")
        self.assertEqual(words("NV", "Republican Party"), "Republican")
        self.assertEqual(words("CO", "Libertarian Party"), "Libertarian")
        self.assertEqual(words("NV", "Libertarian Party of Nevada"), "Libertarian Party of Nevada")
        self.assertEqual(words("CT", "Republican Party; Independent Party"),
                         "Republican; Independent Party")
        self.assertEqual(words("MI", "U.S. Taxpayers Party"), "U.S. Taxpayers Party")
        self.assertEqual(words("IN", "Write-In (National Socialist American Workers')", True),
                         "National Socialist American Workers'")
        self.assertIsNone(words("FL", "WRI", True))
        self.assertEqual(words("XX", "QQQ"), "QQQ")   # refused by problems()

    def test_a_different_given_name_is_not(self):
        # Rule 56: "Joe" is not a prefix of "Joseph"; that takes an evidenced
        # form (overrides.STATEWIDE_NAME_FORMS).
        self.assertFalse(statewide.same_given_name("Joe Lombardo", "Lombardo, Joseph"))
        self.assertFalse(statewide.same_given_name("Bill Lee", "Eddie Lee Murphy"))


class TestNevadasOwnList(unittest.TestCase):
    """Nevada's statewide offices cited Clark County's notice of the general
    election, "the Secretary of State's own certified list could not be
    read (nvsos.gov refused every request)": the office's site challenges
    every script and serves only a person's browser. Its certified list was
    read by hand from the office's own page on 2026-10-25 (rule 91, as rule
    57 reads a court's), and is now the source for all four offices."""

    # The list's rows: (Name on Ballot, Party), compared name by name and
    # party by party with Clark County's notice, which named the same.
    ROWS = {
        "governor": [("Ford, Aaron D.", "Democratic Party"),
                     ("Ford, Danielle", "No Political Party"),
                     ("Lombardo, Joseph", "Republican Party")],
        "lt": [("Anthony, Stavros", "Republican Party"),
               ("Hansen, Janine", "Independent American Party"),
               ("Jauregui, Sandra", "Democratic Party")],
        "sos": [('Aguilar, Francisco "Cisco"', "Democratic Party"),
                ("Barnhill, Brad Lee", "Independent American Party"),
                ("Kennedy, John T.", "Libertarian Party of Nevada"),
                ("Marchant, Jim", "Republican Party")],
        "ag": [("Cannizzaro, Nicole Jeanette", "Democratic Party"),
               ("Guzmán Fralick, Adriana", "Republican Party")],
    }
    URL = "https://www.nvsos.gov/home/showpublisheddocument/20105/639232733439300000"

    @classmethod
    def setUpClass(cls):
        cls.cache = statewide.load(".")
        cls.payload, cls.problems = stategov.build(".")

    def test_the_list_is_the_secretary_of_states_own_and_certified(self):
        from kyc import voting_dates
        for key in self.ROWS:
            o = statewide.office(self.cache, "NV", key)
            self.assertNotIn("notStateList", o, key)
            self.assertFalse(statewide.not_the_states(o["list"]), key)
            self.assertIsNone(statewide.elsewhere(o["list"]["url"]), key)
            self.assertEqual(o["list"]["url"], self.URL, key)
            self.assertEqual(o["list"]["by"], "Nevada Secretary of State", key)
            # On Nevada's own domain, not by an evidenced exception.
            self.assertTrue(voting_dates.official_source(o["list"]["url"], "NV")[0], key)
            self.assertTrue(o["certified"], key)
            self.assertIn("Certified", o["certifiedQuote"], key)
            self.assertEqual(o["list"]["read"], "2026-10-25", key)

    def test_the_four_offices_names_and_parties(self):
        for key, rows in self.ROWS.items():
            o = statewide.office(self.cache, "NV", key)
            self.assertEqual(sorted((p["name"], p["party"]) for p in o["candidates"]),
                             sorted(rows), key)
            for name, party in rows:
                self.assertIn(f"{name} | ", o["list"]["quote"], key)
            # The page reads the major parties as the holder line does.
            parties = {p["printed"]: p.get("party") for p in
                       self.payload["states"]["NV"]["ballot2026"]["offices"][key]
                       ["candidates"]["candidates"]}
            for name, party in rows:
                self.assertEqual(parties[name], {"Democratic Party": "Democratic",
                                                 "Republican Party": "Republican"}.get(party, party))
            shown = self.payload["states"]["NV"]["ballot2026"]["offices"][key]["candidates"]
            self.assertEqual(shown["source"],
                             "the Nevada Secretary of State’s certified list of candidates")
            self.assertNotIn("notStateList", shown)

    def test_the_holder_lines(self):
        offices = self.payload["states"]["NV"]["ballot2026"]["offices"]
        for key in ("governor", "lt", "sos"):
            status = offices[key]["holderStatus"]
            self.assertEqual(status["why"], "listed", key)
            self.assertEqual(status["source"], self.URL, key)
        self.assertEqual(offices["governor"]["holderStatus"]["name"], "Lombardo, Joseph")
        self.assertEqual(offices["lt"]["holderStatus"]["name"], "Anthony, Stavros")
        self.assertEqual(offices["sos"]["holderStatus"]["name"], 'Aguilar, Francisco "Cisco"')
        # The attorney general is on the governor's list, not his own.
        ag = offices["ag"]["holderStatus"]
        self.assertEqual(ag["why"], "not-listed")
        self.assertIn("Ford", ag["holder"])
        self.assertFalse([p for p in self.problems if p.startswith("NV ")], self.problems)

    def test_no_exception_stands_for_nevadas_own_office_or_its_county(self):
        from kyc import overrides
        self.assertFalse([p for p in overrides.STATEWIDE_LISTS_ELSEWHERE
                          if "clarkcountynv" in p or "nvsos" in p])
        self.assertFalse([p for p in overrides.MEASURE_SOURCES_ELSEWHERE if "nvsos" in p])


class TestHolderStatus(unittest.TestCase):
    """Rule 79: "not running" is the list's word, for whoever holds the
    office now; "on the list" only where the list's own holder is them."""

    def test_a_holder_the_list_does_not_name(self):
        status, problem = statewide.holder_status("GA", "governor", office(), "Brian Kemp")
        self.assertIsNone(problem)
        self.assertEqual(status["why"], "not-listed")
        self.assertEqual(status["text"], "Brian Kemp is not among the candidates for this office")
        # The document named as what it is.
        self.assertEqual((status["source"], status["cite"]),
                         (LIST, "the Georgia Secretary of State’s candidate list"))

    def test_a_holder_on_the_list_is_on_it_never_running_for_re_election(self):
        entry = office(holderResearched="Pat Example", holderOnList=True)
        entry["candidates"][0]["holder"] = True
        status, problem = statewide.holder_status("GA", "governor", entry, "Pat Example")
        self.assertIsNone(problem)
        self.assertEqual(status["why"], "listed")
        self.assertNotIn("re-election", status["text"])
        self.assertEqual(status["text"], "Pat Example is among the candidates for this office")

    def test_a_list_is_never_called_certified_by_the_holder_line(self):
        entry = office()
        entry["list"]["kind"] = "official sample ballot"
        status, _ = statewide.holder_status("GA", "governor", entry, "Brian Kemp")
        self.assertNotIn("certified", status["text"] + status["cite"])
        self.assertEqual(status["cite"], "the Georgia Secretary of State’s official sample ballot")

    def test_a_holder_spelled_with_a_hyphen_is_still_found(self):
        # A carrier the list writes "Kim-Varet" is never read as absent for
        # a holder the roster writes "Kim Varet": unsettled, not "not listed".
        entry = office(holderResearched="Jane Kim Varet")
        entry["candidates"][0].update(name="Jane Kim-Varet", surname="Kim-Varet")
        status, problem = statewide.holder_status("GA", "governor", entry, "Jane Kim Varet")
        self.assertIsNone(status)
        self.assertIn("may or may not be", problem)

    def test_a_holders_own_record_is_the_source(self):
        entry = office(holderResearched="Pat Example", holderOnList=True)
        entry["candidates"][0].update(holder=True, record="https://sos.ga.gov/record/1")
        status, _ = statewide.holder_status("GA", "governor", entry, "Pat Example")
        self.assertEqual(status["source"], "https://sos.ga.gov/record/1")

    def test_a_namesake_settles_nothing(self):
        # A candidate carrying the holder's surname whom the list does not
        # mark as the holder: never guessed either way (rule 25).
        entry = office()
        entry["candidates"][0]["name"] = "Pat Kemp"
        status, problem = statewide.holder_status("GA", "governor", entry, "Brian Kemp")
        self.assertIsNone(status)
        self.assertIn("may or may not be Brian Kemp", problem)

    def test_a_recorded_namesake_is_set_aside_for_that_holder_only(self):
        entry = office(namesakes={"Pat Kemp": "a different given name"})
        entry["candidates"][0]["name"] = "Pat Kemp"
        status, _ = statewide.holder_status("GA", "governor", entry, "Brian Kemp")
        self.assertEqual(status["why"], "not-listed")
        status, problem = statewide.holder_status("GA", "governor", entry, "Chris Kemp")
        self.assertIsNone(status)
        self.assertIn("read with Brian Kemp", problem)

    def test_a_marked_holder_with_another_given_name_needs_an_evidenced_form(self):
        entry = office(holderResearched="Joe Example", holderOnList=True)
        entry["candidates"][0].update(name="Example, Joseph", holder=True)
        status, problem = statewide.holder_status("GA", "governor", entry, "Joe Example")
        self.assertIsNone(status)
        self.assertTrue(problem)
        with mock.patch.dict("kyc.overrides.STATEWIDE_NAME_FORMS",
                             {("GA", "governor", "Joe Example"): ("Example, Joseph", "evidence")}):
            status, problem = statewide.holder_status("GA", "governor", entry, "Joe Example")
        self.assertEqual(status["why"], "listed")

    def test_a_new_holder_is_still_read_against_the_list(self):
        # The list was read for Brian Kemp; someone else holding the office
        # is not on it either, and the change is reported.
        status, problem = statewide.holder_status("GA", "governor", office(), "Chris Carr")
        self.assertEqual(status["why"], "not-listed")
        self.assertIn("read with Brian Kemp", problem)


class TestHolderLine(unittest.TestCase):

    def test_a_term_limit_stays_beside_the_list(self):
        status, problem = stategov.holder_line("FL", "governor", "Ron DeSantis", 2,
                                               office(holderResearched="Ron DeSantis"))
        self.assertIsNone(problem)
        self.assertEqual(status["why"], "term-limit")
        self.assertEqual(status["text"], "Ron DeSantis is term-limited")
        self.assertEqual(status["then"]["text"], "is not among the candidates for this office")

    def test_a_term_limited_holder_the_list_names_is_shown_as_neither(self):
        entry = office(holderResearched="Ron DeSantis", holderOnList=True)
        entry["candidates"][0].update(name="Ron DeSantis", surname="DeSantis", holder=True)
        status, problem = stategov.holder_line("FL", "governor", "Ron DeSantis", 2, entry)
        self.assertEqual(status["why"], "unchecked")
        self.assertIn("neither is shown", problem)

    def test_no_list_falls_back_to_the_table(self):
        status, _ = stategov.holder_line("MN", "governor", "Pat Holder", 2, None)
        self.assertEqual(status["why"], "unchecked")


class TestThePage(unittest.TestCase):

    def test_printed_names_first_then_write_ins_each_by_surname(self):
        entry = office()
        entry["candidates"] += [
            {"name": "Ann Zed", "surname": "Zed", "party": "WRI", "runningMate": None,
             "writeIn": True, "holder": False},
            {"name": "Bo Able", "surname": "Able", "party": None, "runningMate": None,
             "writeIn": True, "holder": False},
        ]
        page = statewide.for_page("GA", entry)
        self.assertEqual([p["name"] for p in page["candidates"]],
                         ["Pat Example", "Lee Sample", "Bo Able", "Ann Zed"])
        # A write-in's "party" that only says it is a write-in is dropped.
        self.assertNotIn("party", page["candidates"][3])
        self.assertEqual(page["candidates"][0]["party"], "Republican")
        self.assertEqual(page["by"], "Georgia Secretary of State")
        self.assertEqual(page["source"], "the Georgia Secretary of State’s candidate list")

    def test_the_lists_own_form_stays_beside_the_name_shown(self):
        entry = office()
        entry["candidates"][0].update(name="EXAMPLE, PAT", runningMate="DOE, JAN")
        entry["candidates"].append({"name": "James", "surname": "James", "party": None,
                                    "runningMate": None, "writeIn": False, "holder": False})
        rows = {p["name"]: p for p in statewide.for_page("GA", entry)["candidates"]}
        self.assertEqual(rows["Pat Example"]["printed"], "EXAMPLE, PAT")
        self.assertEqual(rows["Pat Example"]["runningMate"], "Jan Doe")
        self.assertNotIn("printed", rows["Lee Sample"])
        # Massachusetts prints its independent ticket by surnames only.
        self.assertTrue(rows["James"]["surnameOnly"])

    def test_the_build_lists_every_office_on_the_ballot(self):
        payload, problems = stategov.build(".")
        for code, state in payload["states"].items():
            for key, item in ((state.get("ballot2026") or {}).get("offices") or {}).items():
                if not item["up"]:
                    self.assertNotIn("candidates", item, (code, key))
                    continue
                self.assertTrue(item["candidates"]["candidates"], (code, key))
                for person in item["candidates"]["candidates"]:
                    # The list's words, and a photograph only with whose it is
                    # (rule 91, the owner's decision of 2026-10-19): never a
                    # figure or a profile id (rules 24, 25, 27). A heavy one is
                    # drawn as the smaller copy made here (rule 101,
                    # ``photoCopy``): an election office's guide's, hosted
                    # here, can be (kyc/guide_photos.py).
                    self.assertLessEqual(set(person), {"name", "party", "runningMate",
                                                       "ballotName", "writeIn", "holder",
                                                       "printed", "surnameOnly", "record",
                                                       "photo", "photoCredit", "photoCopy"})
                    if person.get("photoCopy"):
                        self.assertEqual(person["photoCopy"]["of"], person["photo"], person)
                    self.assertEqual("photo" in person, bool((person.get("photoCredit") or {})
                                                             .get("by") or (person.get(
                                                                 "photoCredit") or {}).get(
                                                                 "licence")), person)
                    self.assertFalse(person.get("writeIn") and person.get("photo"), person)
                    # Never a name in capitals (rule 77), never a party code.
                    self.assertNotEqual(person["name"], person["name"].upper(), person)
                    self.assertNotIn(",", person["name"].split("(")[0], person)
                # With a list in hand, "not checked" is said only where the
                # list did not settle the holder, and the build says why.
                status = item.get("holderStatus") or {}
                if status.get("why") == "unchecked":
                    self.assertTrue([p for p in problems if p.startswith(f"{code} {key}:")],
                                    (code, key))



class TestMembersOnAList(unittest.TestCase):
    """A sitting member whose name a statewide list carries is a lead, never
    a join (rule 25): Amy Klobuchar was on Minnesota's governor ballot while
    her profile said nothing of it (PR #109 review)."""

    MEMBER = {"bioguide": "X000001", "state": "GA", "name": "Pat Example",
              "nameParts": {"first": "Pat", "last": "Example", "official_full": "Pat Example"}}

    def cache(self):
        return {"states": {"GA": {"offices": {"governor": office()}}}}

    def test_a_member_on_a_list_with_no_note_is_a_lead(self):
        leads = statewide.member_leads(self.cache(), [self.MEMBER], set())
        self.assertEqual(len(leads), 1)
        self.assertIn("X000001", leads[0])

    def test_a_noted_member_or_another_state_is_not(self):
        self.assertEqual(statewide.member_leads(self.cache(), [self.MEMBER], {"X000001"}), [])
        self.assertEqual(statewide.member_leads(self.cache(), [dict(self.MEMBER, state="AL")],
                                                set()), [])

    def test_a_namesake_with_another_given_name_is_not(self):
        other = dict(self.MEMBER, name="Chris Example",
                     nameParts={"first": "Chris", "last": "Example"})
        self.assertEqual(statewide.member_leads(self.cache(), [other], set()), [])

    def test_every_member_on_the_lists_is_noted(self):
        import json
        from kyc import cycle, overrides
        with open("congress_snapshot.json", encoding="utf-8") as handle:
            snapshot = json.load(handle)
        if cycle.snapshot_congress(snapshot) >= cycle.electing_congress():
            self.skipTest("the lists are the 2026 campaign's")
        self.assertEqual(statewide.member_leads(statewide.load("."), snapshot["legislators"],
                                                set(overrides.OTHER_OFFICE_NOMINEES)), [])


if __name__ == "__main__":
    unittest.main()
