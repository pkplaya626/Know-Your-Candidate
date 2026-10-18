"""How members voted: the roll calls, read from the House Clerk's and the
Senate's own records and attributed by id (kyc/rollcalls.py, rule 89)."""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import emit, overrides, pages, rollcalls  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def house_xml(roll, date="9-Jan-2025", votes=(), question="On Passage", legis="H R 23",
              desc="Illegitimate Court Counteraction Act", result="Passed", congress=119,
              speaker=None):
    rows = "".join(
        f'<recorded-vote><legislator name-id="{vid}" sort-field="{name}" unaccented-name="{name}" '
        f'party="{party}" state="{state}" role="{"speaker" if vid == speaker else "legislator"}">'
        f"{name}</legislator><vote>{cast}</vote></recorded-vote>"
        for vid, name, party, state, cast in votes)
    return (f'<?xml version="1.0" encoding="utf-8"?><rollcall-vote><vote-metadata>'
            f"<majority>R</majority><congress>{congress}</congress><session>1st</session>"
            f"<chamber>U.S. House of Representatives</chamber><rollcall-num>{roll}</rollcall-num>"
            f"<legis-num>{legis}</legis-num><vote-question>{question}</vote-question>"
            f"<vote-type>YEA-AND-NAY</vote-type><vote-result>{result}</vote-result>"
            f'<action-date>{date}</action-date><action-time time-etz="13:26">1:26 PM</action-time>'
            f"<vote-desc>{desc}</vote-desc></vote-metadata><vote-data>{rows}</vote-data>"
            "</rollcall-vote>").encode("utf-8")


def senate_xml(vote, session=1, date="January 9, 2025,  02:54 PM", members=(), amendment=""):
    rows = "".join(
        f"<member><member_full>{last} ({party}-{state})</member_full><last_name>{last}</last_name>"
        f"<first_name>{first}</first_name><party>{party}</party><state>{state}</state>"
        f"<vote_cast>{cast}</vote_cast><lis_member_id>{lis}</lis_member_id></member>"
        for lis, first, last, party, state, cast in members)
    document = ("<document><document_congress>119</document_congress><document_type/>"
                "<document_number/><document_name/><document_title/><document_short_title/>"
                "</document>" if amendment else
                "<document><document_congress>119</document_congress><document_type>S.</document_type>"
                "<document_number>5</document_number><document_name>S. 5</document_name>"
                "<document_title>A bill to require the Secretary of Homeland Security to take "
                "into custody aliens who have been charged with theft.</document_title>"
                "<document_short_title/></document>")
    amend = (f"<amendment><amendment_number>{amendment}</amendment_number>"
             "<amendment_to_document_number>S. 5</amendment_to_document_number>"
             "<amendment_to_document_short_title>Laken Riley Act</amendment_to_document_short_title>"
             "<amendment_purpose>To expand the list of offenses.</amendment_purpose></amendment>"
             if amendment else
             "<amendment><amendment_number/><amendment_purpose>No Statement of Purpose on "
             "File.</amendment_purpose></amendment>")
    return (f'<?xml version="1.0" encoding="UTF-8"?><roll_call_vote><congress>119</congress>'
            f"<session>{session}</session><congress_year>{2024 + session}</congress_year>"
            f"<vote_number>{vote}</vote_number><vote_date>{date}</vote_date>"
            "<vote_question_text>On Cloture on the Motion to Proceed S. 5</vote_question_text>"
            "<vote_result_text>Cloture on the Motion to Proceed Agreed to (84-9, 3/5 majority "
            "required)</vote_result_text><question>On Cloture on the Motion to Proceed</question>"
            "<vote_title>Motion to Invoke Cloture: Motion to Proceed to S. 5</vote_title>"
            f"<vote_result>Agreed to</vote_result>{document}{amend}<members>{rows}</members>"
            "</roll_call_vote>").encode("utf-8")


ERROR_NOTE = b'<xml>Error sanitizing file "roll363.xml". Please try again.</xml>'


def member(name, last, chamber, state, start, end, lis=None):
    person = {"name": name, "last": last,
              "terms": [{"chamber": chamber, "state": state, "start": start, "end": end}]}
    if lis:
        person["lis"] = lis
    return person


class TestParsing(unittest.TestCase):
    def test_a_house_roll_call_as_the_clerk_writes_it(self):
        record, people = rollcalls.parse_house(house_xml(
            17, votes=[("A000370", "Adams", "D", "NC", "Nay"),
                       ("J000299", "Johnson (LA)", "R", "LA", "Yea")],
            speaker="J000299"), 2025, 17, 119)
        self.assertEqual((record["n"], record["year"], record["session"], record["date"]),
                         (17, 2025, 1, "2025-01-09"))
        self.assertEqual(record["measure"], "H R 23")
        self.assertEqual(record["title"], "Illegitimate Court Counteraction Act")
        self.assertEqual(record["votes"], {"Nay": "A000370", "Yea": "J000299"})
        self.assertEqual(record["speaker"], "J000299")
        self.assertEqual(people["J000299"]["state"], "LA")

    def test_the_clerks_note_for_a_number_not_posted_is_not_a_roll_call(self):
        # HTTP 200, and not a file (rule 52): it concludes nothing (rule 8).
        with self.assertRaises(rollcalls.NotARollCall):
            rollcalls.parse_house(ERROR_NOTE, 2025, 363, 119)

    def test_a_file_that_is_another_roll_call_is_refused(self):
        raw = house_xml(18, votes=[("A000370", "Adams", "D", "NC", "Nay")])
        with self.assertRaises(rollcalls.RollCallError):
            rollcalls.parse_house(raw, 2025, 17, 119)
        with self.assertRaises(rollcalls.RollCallError):
            rollcalls.parse_house(house_xml(17, congress=118, votes=[
                ("A000370", "Adams", "D", "NC", "Nay")]), 2025, 17, 119)

    def test_one_member_recorded_twice_is_refused(self):
        raw = house_xml(17, votes=[("A000370", "Adams", "D", "NC", "Nay"),
                                   ("A000370", "Adams", "D", "NC", "Yea")])
        with self.assertRaises(rollcalls.RollCallError):
            rollcalls.parse_house(raw, 2025, 17, 119)

    def test_a_senate_vote_and_an_amendments_measure(self):
        record, people = rollcalls.parse_senate(senate_xml(
            1, members=[("S428", "Angela", "Alsobrooks", "D", "MD", "Yea")]), 119, 1, 1)
        self.assertEqual((record["date"], record["time"]), ("2025-01-09", "14:54"))
        self.assertEqual(record["measure"], "S. 5")
        self.assertIn("Cloture", record["result"])
        self.assertEqual(people["S428"]["name"], "Alsobrooks, Angela")
        amended, _ = rollcalls.parse_senate(senate_xml(
            3, members=[("S428", "Angela", "Alsobrooks", "D", "MD", "Nay")],
            amendment="S.Amdt. 14"), 119, 1, 3)
        # The measure it would amend, and what the amendment is for.
        self.assertEqual(amended["measure"], "S. 5")
        self.assertEqual(amended["title"], "Laken Riley Act")
        self.assertEqual(amended["amendment"], "S.Amdt. 14 (To expand the list of offenses.)")

    def test_the_senate_vote_menu(self):
        raw = (b"<vote_summary><congress>119</congress><session>2</session><votes>"
               b"<vote><vote_number>00002</vote_number></vote>"
               b"<vote><vote_number>00001</vote_number></vote></votes></vote_summary>")
        self.assertEqual(rollcalls.parse_senate_menu(raw, 119, 2), [1, 2])
        with self.assertRaises(rollcalls.RollCallError):
            rollcalls.parse_senate_menu(raw, 119, 1)


class TestMembers(unittest.TestCase):
    def test_only_terms_in_this_congress(self):
        rows = [
            {"id": {"bioguide": "A000001", "lis": "S401"}, "name": {"first": "Ann", "last": "Able"},
             "terms": [{"type": "rep", "state": "OH", "start": "2023-01-03", "end": "2025-01-03"},
                       {"type": "sen", "state": "OH", "start": "2025-01-03", "end": "2031-01-03"}]},
            # Left on 2023-01-03: the last Congress's member, not this one's.
            {"id": {"bioguide": "B000002"}, "name": {"first": "Bo", "last": "Bee"},
             "terms": [{"type": "rep", "state": "TX", "start": "2021-01-03", "end": "2025-01-03"}]},
        ]
        table = rollcalls.build_members(rows, 119)
        self.assertEqual(set(table), {"A000001"})
        self.assertEqual(table["A000001"]["lis"], "S401")
        self.assertEqual([t["chamber"] for t in table["A000001"]["terms"]], ["Senate"])


def cache_with(house_rolls=(), senate_rolls=(), members=None):
    cache = rollcalls.empty_cache(119)
    cache["members"] = members or {}
    for raw, year, roll in house_rolls:
        rollcalls._add(cache["house"], *rollcalls.parse_house(raw, year, roll, 119))
    for raw, session, vote in senate_rolls:
        rollcalls._add(cache["senate"], *rollcalls.parse_senate(raw, 119, session, vote))
    return cache


class TestAttribution(unittest.TestCase):
    """Rule 17: a vote reaches a profile only by the member's id, inside a
    term they served; rule 67: a member who left keeps what they cast."""

    MEMBERS = {
        "A000370": member("Alma S. Adams", "Adams", "House", "NC", "2025-01-03", "2027-01-03"),
        # Seated after a special election on 2025-04-02.
        "P000622": member("Jimmy Patronis", "Patronis", "House", "FL", "2025-04-02", "2027-01-03"),
        # Died in office on 2025-03-05.
        "T000488": member("Sylvester Turner", "Turner", "House", "TX", "2025-01-03", "2025-03-05"),
        "G000600": member("Marie Gluesenkamp Perez", "Gluesenkamp Perez", "House", "WA",
                          "2025-01-03", "2027-01-03"),
        "J000299": member("Mike Johnson", "Johnson", "House", "LA", "2025-01-03", "2027-01-03"),
    }

    def build(self, rolls):
        problems = []
        cache = cache_with(house_rolls=rolls, members=json.loads(json.dumps(self.MEMBERS)))
        return rollcalls.chamber_payload(cache, "house", problems), problems

    def test_a_vote_before_a_member_was_seated_never_reaches_them(self):
        payload, problems = self.build([
            (house_xml(1, date="3-Jan-2025", votes=[("A000370", "Adams", "D", "NC", "Yea"),
                                                    ("P000622", "Patronis", "R", "FL", "Yea")]),
             2025, 1),
            (house_xml(2, date="3-Apr-2025", votes=[("A000370", "Adams", "D", "NC", "Nay"),
                                                    ("P000622", "Patronis", "R", "FL", "Nay")]),
             2025, 2)])
        self.assertEqual(payload["members"]["P000622"]["votes"], ".N")
        self.assertEqual(payload["members"]["P000622"]["listed"], 1)
        self.assertEqual(payload["members"]["A000370"]["votes"], "YN")
        self.assertIn("votes-outside-term", [p[1] for p in problems])

    def test_a_member_who_left_keeps_the_votes_they_cast(self):
        payload, _ = self.build([
            (house_xml(1, date="3-Feb-2025", votes=[("T000488", "Turner (TX)", "D", "TX", "Yea")]),
             2025, 1),
            (house_xml(2, date="3-Apr-2025", votes=[("A000370", "Adams", "D", "NC", "Nay")]),
             2025, 2)])
        self.assertEqual(payload["members"]["T000488"]["votes"], "Y.")

    def test_a_vote_under_another_members_id_is_given_to_nobody(self):
        # The record's words for the id are a Florida "Smith": not Alma Adams
        # of North Carolina, whose id it carries.
        payload, problems = self.build([
            (house_xml(1, votes=[("A000370", "Smith", "R", "FL", "Yea")]), 2025, 1)])
        self.assertNotIn("A000370", payload["members"])
        self.assertIn("votes-unattributed", [p[1] for p in problems])
        payload, problems = self.build([
            (house_xml(1, votes=[("A000370", "Smith", "D", "NC", "Yea")]), 2025, 1)])
        self.assertNotIn("A000370", payload["members"])

    def test_the_record_may_write_part_of_a_surname_or_a_state_beside_it(self):
        payload, problems = self.build([
            (house_xml(1, votes=[("G000600", "Perez", "D", "WA", "Yea"),
                                 ("J000299", "Johnson (LA)", "R", "LA", "Yea")]), 2025, 1)])
        self.assertEqual(set(payload["members"]), {"G000600", "J000299"})
        self.assertEqual(problems, [])

    def test_a_delegates_state_is_written_xx_and_only_a_delegates(self):
        # The Clerk writes "XX" for a delegate in the Committee of the
        # Whole's roll calls (roll call 79 of 2025).
        members = dict(self.MEMBERS, N000147=member(
            "Eleanor Holmes Norton", "Norton", "House", "DC", "2025-01-03", "2027-01-03"))
        cache = cache_with(house_rolls=[
            (house_xml(79, votes=[("N000147", "Norton", "D", "XX", "Aye"),
                                  ("A000370", "Adams", "D", "NC", "Aye")]), 2025, 79),
            (house_xml(80, votes=[("A000370", "Adams", "D", "NC", "No")]), 2025, 80)],
            members=members)
        problems = []
        payload = rollcalls.chamber_payload(cache, "house", problems)
        norton = payload["members"]["N000147"]
        self.assertEqual((norton["votes"], norton["unlisted"], norton["delegate"]), ("A.", 1, True))
        self.assertNotIn("delegate", payload["members"]["A000370"])
        self.assertEqual(payload["delegateRule"]["cite"], "House Rule III, clause 3(a)")
        self.assertEqual(problems, [])
        cache = cache_with(house_rolls=[
            (house_xml(79, votes=[("A000370", "Adams", "D", "XX", "Aye")]), 2025, 79)],
            members=members)
        self.assertNotIn("A000370", rollcalls.chamber_payload(cache, "house", [])["members"])

    def test_an_id_the_record_lists_for_no_member(self):
        payload, problems = self.build([
            (house_xml(1, votes=[("G000578", "Gaetz", "R", "FL", "Not Voting"),
                                 ("X000001", "Nobody", "R", "FL", "Yea")]), 2025, 1)])
        self.assertEqual(payload["members"], {})
        warned = [p for p in problems if p[1] == "votes-unattributed"]
        # Matt Gaetz is an evidenced entry, and is not warned about.
        self.assertIn("G000578", overrides.ROLL_CALL_NON_MEMBERS)
        self.assertEqual(len(warned), 1)
        self.assertTrue(all("X000001" in line for line in warned[0][3]))

    def test_not_voting_is_counted_and_present_is_not(self):
        payload, _ = self.build([
            (house_xml(n, date=f"{n}-Feb-2025", votes=[("A000370", "Adams", "D", "NC", cast)]),
             2025, n) for n, cast in ((1, "Yea"), (2, "Not Voting"), (3, "Present"), (4, "No"))])
        entry = payload["members"]["A000370"]
        self.assertEqual((entry["listed"], entry["notVoting"], entry["share"]), (4, 1, 25.0))
        self.assertEqual(entry["votes"], "YVPO")
        self.assertEqual(payload["notVoting"], "Not Voting")
        self.assertEqual(payload["codes"]["V"], "Not Voting")

    def test_the_speakers_roll_calls_are_counted_apart(self):
        payload, _ = self.build([
            (house_xml(1, date="3-Feb-2025", speaker="J000299",
                       votes=[("J000299", "Johnson (LA)", "R", "LA", "Not Voting")]), 2025, 1),
            (house_xml(2, date="4-Feb-2025", speaker="J000299",
                       votes=[("J000299", "Johnson (LA)", "R", "LA", "Yea")]), 2025, 2)])
        entry = payload["members"]["J000299"]
        self.assertEqual((entry["asSpeaker"], entry["speakerNotVoting"]), (2, 1))
        self.assertEqual(payload["speakerRule"]["cite"], "House Rule I, clause 7")

    def test_an_election_of_the_speaker_keeps_the_names_cast(self):
        payload, _ = self.build([
            (house_xml(2, date="3-Jan-2025", question="Election of the Speaker", legis="",
                       desc="", result="Johnson (LA)",
                       votes=[("A000370", "Adams", "D", "NC", "Jeffries"),
                              ("J000299", "Johnson (LA)", "R", "LA", "Johnson (LA)")]), 2025, 2)])
        codes = payload["codes"]
        self.assertEqual(codes[payload["members"]["A000370"]["votes"]], "Jeffries")
        self.assertEqual(codes[payload["members"]["J000299"]["votes"]], "Johnson (LA)")
        # No tally of yeas and nays for a vote that has none.
        self.assertEqual(payload["rolls"][0][6], "Johnson (LA)")

    def test_a_roll_row_links_the_official_record(self):
        payload, _ = self.build([
            (house_xml(17, votes=[("A000370", "Adams", "D", "NC", "Yea")]), 2025, 17)])
        row = payload["rolls"][0]
        self.assertEqual(row[0], "2025-17")
        self.assertEqual(row[7], "https://clerk.house.gov/Votes/202517")
        self.assertEqual(row[6], "Passed (1-0)")

    def test_senate_votes_are_attributed_through_the_lis_id(self):
        members = {"A000382": member("Angela D. Alsobrooks", "Alsobrooks", "Senate", "MD",
                                     "2025-01-03", "2031-01-03", lis="S428")}
        cache = cache_with(senate_rolls=[(senate_xml(1, members=[
            ("S428", "Angela", "Alsobrooks", "D", "MD", "Yea"),
            ("S999", "Nobody", "Known", "R", "MD", "Nay")]), 1, 1)], members=members)
        problems = []
        payload = rollcalls.chamber_payload(cache, "senate", problems)
        self.assertEqual(payload["members"]["A000382"]["votes"], "Y")
        self.assertEqual(payload["rolls"][0][7], "https://www.senate.gov/legislative/LIS/"
                         "roll_call_votes/vote1191/vote_119_1_00001.htm")
        self.assertEqual([p[1] for p in problems], ["votes-unattributed"])


class TestReading(unittest.TestCase):
    def reader(self, answers):
        asked = []

        def read(url):
            asked.append(url)
            answer = answers(url)
            if isinstance(answer, Exception):
                raise answer
            return answer
        return read, asked

    def test_the_house_is_read_up_to_the_clerks_note_and_resumed(self):
        posted = {1, 2, 3}

        def answers(url):
            year, roll = re.search(r"evs/(\d+)/roll(\d+)", url).groups()
            if year == "2025" and int(roll) in posted:
                return house_xml(int(roll), votes=[("A000370", "Adams", "D", "NC", "Yea")])
            return ERROR_NOTE
        read, asked = self.reader(answers)
        cache = rollcalls.empty_cache(119)
        today = rollcalls.datetime.date(2025, 6, 1)
        self.assertEqual(rollcalls.read_house(cache, today, read=read, pause=0, log=lambda *a: 0), 3)
        self.assertEqual([r["n"] for r in cache["house"]["rolls"]], [1, 2, 3])
        self.assertEqual(cache["house"]["read"], "2025-06-01")
        # A second run asks only for what comes next.
        asked.clear()
        posted.add(4)
        self.assertEqual(rollcalls.read_house(cache, today, read=read, pause=0, log=lambda *a: 0), 1)
        self.assertEqual(len(asked), 2)
        self.assertTrue(asked[0].endswith("roll004.xml"))

    def test_a_refusal_stops_the_run_and_keeps_what_was_read(self):
        def answers(url):
            roll = int(re.search(r"roll(\d+)", url).group(1))
            if roll == 3:
                return urllib.error.HTTPError(url, 503, "busy", {}, None)
            return house_xml(roll, votes=[("A000370", "Adams", "D", "NC", "Yea")])
        read, _ = self.reader(answers)
        cache = rollcalls.empty_cache(119)
        with self.assertRaises(rollcalls.RollCallError):
            rollcalls.read_house(cache, rollcalls.datetime.date(2025, 6, 1), read=read, pause=0,
                                 log=lambda *a: 0)
        self.assertEqual(len(cache["house"]["rolls"]), 2)
        # Not "read": a partial run never dates the record as complete.
        self.assertIsNone(cache["house"]["read"])

    def test_a_limit_stops_early_without_dating_the_read(self):
        read, _ = self.reader(lambda url: house_xml(
            int(re.search(r"roll(\d+)", url).group(1)), votes=[("A000370", "Adams", "D", "NC", "Yea")]))
        cache = rollcalls.empty_cache(119)
        rollcalls.read_house(cache, rollcalls.datetime.date(2025, 6, 1), read=read, pause=0,
                             limit=2, log=lambda *a: 0)
        self.assertEqual(len(cache["house"]["rolls"]), 2)
        self.assertIsNone(cache["house"]["read"])

    def test_the_senate_reads_what_its_menu_lists(self):
        menu = (b"<vote_summary><congress>119</congress><session>1</session><votes>"
                b"<vote><vote_number>00001</vote_number></vote></votes></vote_summary>")

        def answers(url):
            if "vote_menu" in url:
                return menu
            return senate_xml(1, members=[("S428", "Angela", "Alsobrooks", "D", "MD", "Yea")])
        read, asked = self.reader(answers)
        cache = rollcalls.empty_cache(119)
        self.assertEqual(rollcalls.read_senate(cache, rollcalls.datetime.date(2025, 6, 1),
                                               read=read, pause=0, log=lambda *a: 0), 1)
        self.assertEqual(len(asked), 2)


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def test_the_cache_is_one_roll_call_a_line_and_reads_back(self):
        cache = cache_with(house_rolls=[
            (house_xml(n, votes=[("A000370", "Adams", "D", "NC", "Yea")]), 2025, n)
            for n in (1, 2)], members=dict(TestAttribution.MEMBERS))
        path = rollcalls.save_cache(cache, self.root)
        self.assertEqual(rollcalls.load_cache(self.root), json.loads(json.dumps(cache)))
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual(sum(1 for line in lines if line.startswith("{") and '"votes":' in line), 2)

    def test_vote_files_are_written_only_when_they_change(self):
        payloads = rollcalls.payloads(None)
        written = emit.write_votes(payloads, self.root)
        self.assertEqual(len(written), 2)
        self.assertEqual(emit.write_votes(payloads, self.root), [])
        self.assertEqual(emit.check_votes(payloads, self.root), [])
        with open(emit.votes_file("house", self.root), encoding="utf-8") as handle:
            self.assertIn("window.kycVotesHouse = ", handle.read())

    def test_a_page_that_opens_profiles_names_the_vote_files(self):
        html = pages._scripts(("../data/profiles.js", "../assets/kyc-profile.js"))
        self.assertEqual(emit.on_demand_sources(html),
                         ["../data/votes/house.js", "../data/votes/senate.js"])
        # A page without the dialog names none.
        self.assertNotIn("onDemandData", pages._scripts(("../assets/kyc-guide.js",)))


class TestCommittedSite(unittest.TestCase):
    """Every page that opens a profile can load the votes, at their version."""

    def test_every_page_with_the_dialog_names_both_chambers(self):
        site = os.path.join(ROOT, "candidate_profiles_site")
        problems = [note for page, ok, note in emit.check_pages(ROOT)
                    if not ok and "onDemandData" in note]
        self.assertEqual(problems, [])
        with open(os.path.join(site, "index.html"), encoding="utf-8") as handle:
            lazy = re.findall(r'src="(data/votes/[a-z]+\.js\?v=[0-9a-f]{10})"', handle.read())
        self.assertEqual(len(lazy), 2)

    def test_the_committed_vote_files_match_the_cache(self):
        payloads = rollcalls.payloads(rollcalls.load_cache(ROOT))
        self.assertEqual(emit.check_votes(payloads, ROOT), [])


if __name__ == "__main__":
    unittest.main()
