"""Tests for contact details, reference ids, committees and campaign sites.

A voter's next question after "who represents me" is "how do I reach them",
and the answer must come from a source that knows: the member's own term
record in congress-legislators, the committee rosters, and the campaign's
own Form 1 at the FEC. Nothing here is guessed from a name.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import campaigns, legislators, overrides  # noqa: E402
from kyc.profiles import _build_member  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def entry(**overrides):
    base = {
        "id": {"bioguide": "C001131", "govtrack": 456945, "opensecrets": "N00049855",
               "votesmart": 161953, "wikipedia": "Greg Casar", "fec": ["H2TX35144"]},
        "name": {"first": "Greg", "last": "Casar", "official_full": "Greg Casar"},
        "bio": {"birthday": "1989-05-04"},
        "terms": [{"type": "rep", "state": "TX", "district": 35, "party": "Democrat",
                   "start": "2025-01-03", "end": "2027-01-03",
                   "url": "https://casar.house.gov", "phone": "202-225-5645",
                   "office": "446 Cannon House Office Building",
                   "contact_form": "https://casar.house.gov/contact"}],
    }
    base.update(overrides)
    return base


class TestSnapshotContacts(unittest.TestCase):
    def test_contact_fields_and_ids_are_kept(self):
        person = legislators.trim(entry())
        self.assertEqual(person["url"], "https://casar.house.gov")
        self.assertEqual(person["phone"], "202-225-5645")
        self.assertEqual(person["office"], "446 Cannon House Office Building")
        self.assertEqual(person["contactForm"], "https://casar.house.gov/contact")
        self.assertEqual(person["govtrack"], 456945)
        self.assertEqual(person["opensecrets"], "N00049855")
        self.assertNotIn("social", person)

    def test_social_handles_are_joined_on_bioguide(self):
        social = [{"id": {"bioguide": "c001131"},
                   "social": {"twitter": "RepCasar", "facebook": "RepCasar",
                              "twitter_id": "1", "youtube_id": "UC123"}}]
        snapshot = legislators.build_snapshot([entry()], social=social, fetched="x")
        person = snapshot["legislators"][0]
        self.assertEqual(person["social"],
                         {"twitter": "RepCasar", "facebook": "RepCasar", "youtube_id": "UC123"})

    def test_a_missing_social_file_is_an_absence(self):
        snapshot = legislators.build_snapshot([entry()], social=None, fetched="x")
        self.assertNotIn("social", snapshot["legislators"][0])


class TestCommittees(unittest.TestCase):
    membership = {
        "HSAG": [{"name": "A", "party": "majority", "rank": 1, "title": "Chair",
                  "bioguide": "A000001"},
                 {"name": "B", "party": "minority", "rank": 1, "title": "Ranking Member",
                  "bioguide": "B000002"}],
        "HSAG15": [{"name": "B", "party": "minority", "rank": 2, "bioguide": "B000002"}],
    }
    committees = [{"name": "House Committee on Agriculture", "thomas_id": "HSAG",
                   "type": "house", "url": "https://agriculture.house.gov/",
                   "subcommittees": [{"name": "Forestry", "thomas_id": "15"}]}]

    def test_assignments_carry_name_title_and_parent(self):
        data = legislators.build_committees(self.membership, self.committees, fetched="x")
        seats = legislators.assignments(data, "b000002")
        self.assertEqual([s["name"] for s in seats],
                         ["House Committee on Agriculture", "Forestry"])
        self.assertEqual(seats[0]["title"], "Ranking Member")
        self.assertFalse(seats[0]["sub"])
        self.assertTrue(seats[1]["sub"])
        self.assertEqual(seats[1]["parent"], "House Committee on Agriculture")
        self.assertEqual(seats[1]["url"], "https://agriculture.house.gov/")

    def test_full_committees_sort_before_subcommittees(self):
        data = legislators.build_committees(self.membership, self.committees, fetched="x")
        seats = legislators.assignments(data, "B000002")
        self.assertEqual([s["sub"] for s in seats], [False, True])

    def test_unknown_member_has_no_assignments(self):
        data = legislators.build_committees(self.membership, self.committees, fetched="x")
        self.assertEqual(legislators.assignments(data, "Z999999"), [])
        self.assertEqual(legislators.assignments(None, "A000001"), [])


class TestMemberProfile(unittest.TestCase):
    row = {"Bioguide ID": "C001131", "Name": "Gregorio Casar", "Chamber": "House",
           "Party": "Democrat", "State": "TX", "District": "District 35",
           "Term Start": "2025-01-03", "Committee Assignments": "Typed by hand"}

    def test_contact_and_refs_come_from_the_snapshot(self):
        person = legislators.trim(entry())
        person["social"] = {"twitter": "RepCasar"}
        profile = _build_member(self.row, 0, person=person)
        self.assertEqual(profile["website"], "https://casar.house.gov")
        self.assertEqual(profile["phone"], "202-225-5645")
        self.assertEqual(profile["wikipedia"], "Greg Casar")
        self.assertEqual(profile["refs"]["govtrack"], 456945)
        self.assertEqual(profile["social"], {"twitter": "RepCasar"})

    def test_an_id_keyed_status_says_who_is_leaving(self):
        # Eleanor Holmes Norton announced her retirement in January 2026, but
        # the DC results page was never read, so the site said she was running.
        row = {"Bioguide ID": "N000147", "Name": "Eleanor Norton", "Chamber": "House",
               "Party": "Democrat", "State": "DC", "District": "District 0",
               "Status": "Active Member", "Term Start": "2025-01-03"}
        profile = _build_member(row, 0)
        self.assertFalse(profile["seekingReelection2026"])
        self.assertIn("Not running", profile["status"])
        # Keyed on the id, not the name: someone else called Norton is untouched.
        other = dict(row, **{"Bioguide ID": "X000001"})
        self.assertTrue(_build_member(other, 1)["seekingReelection2026"])

    # Members whose note says they are on the ballot, not leaving the seat:
    # the special elections for the rest of Rubio's and Vance's terms.
    ON_THE_BALLOT = {"M001244", "H001104"}

    def test_every_id_keyed_status_is_sourced_and_parses(self):
        for member_id, (status, source) in overrides.MEMBER_STATUS_BY_ID.items():
            self.assertRegex(member_id, r"^[A-Z]\d{6}$")
            # Every note cites where it was checked; none rests on memory.
            self.assertTrue(source.startswith("https://"), member_id)
            self.assertEqual(overrides.is_not_seeking(status),
                             member_id not in self.ON_THE_BALLOT, member_id)

    def test_status_notes_are_never_matched_on_a_name(self):
        # STATUS_OVERRIDES matched "Richard Durbin" as a substring of the
        # member's name, so a second "Richard Durbin" - or a roster respelling
        # to "Dick Durbin" - would have moved the note to the wrong person or
        # dropped it. Only the bioguide id selects a note now.
        self.assertFalse(hasattr(overrides, "STATUS_OVERRIDES"))
        row = {"Bioguide ID": "X000001", "Name": "Richard Durbin", "Chamber": "Senate",
               "Party": "Democrat", "State": "IL", "Status": "Active Member",
               "Term Start": "2021-01-03"}
        self.assertEqual(_build_member(row, 0)["status"], "Active Member")
        held = dict(row, **{"Bioguide ID": "D000563", "Name": "Dick Durbin"})
        self.assertIn("not running", _build_member(held, 1)["status"])
        self.assertEqual(overrides.status_override(None, "Active Member"), "Active Member")

    def test_nothing_is_written_without_a_source(self):
        profile = _build_member(self.row, 0)
        for key in ("website", "phone", "office", "contactForm", "refs", "social",
                    "committeeList", "committeesSource"):
            self.assertNotIn(key, profile)
        self.assertEqual(profile["committees"], "Typed by hand")

    def test_authoritative_committees_replace_the_roster_column(self):
        seats = [
            {"code": "HSAG", "name": "House Committee on Agriculture", "title": "Chair",
             "rank": 1, "sub": False, "parent": None, "url": None},
            {"code": "HSAG15", "name": "Forestry", "title": None, "rank": 3,
             "sub": True, "parent": "House Committee on Agriculture", "url": None},
            {"code": "HSGO", "name": "House Committee on Oversight", "title": None,
             "rank": 9, "sub": False, "parent": None, "url": None},
        ]
        profile = _build_member(self.row, 0, assignments=seats)
        self.assertEqual(profile["committees"],
                         "House Committee on Agriculture (Chair); House Committee on Oversight")
        self.assertEqual(profile["committeeList"],
                         [{"code": "HSAG", "title": "Chair"}, {"code": "HSAG15"}, {"code": "HSGO"}])
        self.assertEqual(profile["committeesSource"], "congress-legislators")

    def test_the_build_metadata_names_every_committee_used(self):
        from kyc import summary
        committees = {"committees": {
            "HSAG": {"name": "House Committee on Agriculture", "url": "https://ag.house.gov/"},
            "HSAG15": {"name": "Forestry", "parent": "HSAG"},
            "SSAF": {"name": "Senate Agriculture"}}}
        profiles = [{"committeeList": [{"code": "HSAG", "title": "Chair"}, {"code": "HSAG15"}]}]
        table = summary.committee_table(committees, profiles)
        self.assertEqual(table, {
            "HSAG": {"name": "House Committee on Agriculture", "url": "https://ag.house.gov/"},
            "HSAG15": {"name": "Forestry", "url": "https://ag.house.gov/", "parent": "HSAG"},
        })


class TestCampaignSites(unittest.TestCase):
    def test_urls_are_normalised_from_the_treasurers_typing(self):
        self.assertEqual(campaigns.normalise_url("WWW.KENPAXTON.COM"), "https://www.kenpaxton.com")
        self.assertEqual(campaigns.normalise_url("JAMESTALARICO.COM"), "https://jamestalarico.com")
        self.assertEqual(campaigns.normalise_url("http://Example.org/Path"), "http://example.org/Path")
        self.assertEqual(campaigns.normalise_url("https://a.b.c/"), "https://a.b.c/")

    def test_junk_is_not_a_website(self):
        for junk in (None, "", "N/A", "NONE", "TBD", "treasurer@example.com",
                     "no website", "localhost", "two words.com", "http://bad host.com"):
            self.assertIsNone(campaigns.normalise_url(junk), junk)

    def test_only_people_on_a_ballot_are_looked_up_nominees_first(self):
        people = [
            {"name": "Zed", "fecCandidateId": "H1", "isCandidate": True, "raceStatus": None},
            {"name": "Amy", "fecCandidateId": "H2", "isCandidate": True, "raceStatus": "eliminated"},
            {"name": "Bob", "fecCandidateId": "H3", "isCandidate": True, "raceStatus": "nominee"},
            {"name": "Cy", "fecCandidateId": "H4", "isCandidate": False, "raceStatus": None},
            {"name": "Di", "fecCandidateId": None, "isCandidate": True, "raceStatus": "nominee"},
        ]
        self.assertEqual([p["name"] for p in campaigns.wanted(people)], ["Bob", "Cy", "Zed"])

    def test_apply_attaches_site_and_committee_by_candidate_id(self):
        cache = {"H1": {"found": True, "committee_id": "C1", "name": "BOB FOR CONGRESS",
                        "url": "https://bob.example"},
                 "H2": {"found": True, "committee_id": "C2", "name": "AMY FOR CONGRESS",
                        "url": None},
                 "H3": {"found": False}}
        people = [{"fecCandidateId": "H1"}, {"fecCandidateId": "H2"}, {"fecCandidateId": "H3"},
                  {"fecCandidateId": "H9"}]
        self.assertEqual(campaigns.apply_cache(people, cache), 1)
        self.assertEqual(people[0]["campaignSite"], "https://bob.example")
        self.assertEqual(people[0]["campaignCommittee"], "BOB FOR CONGRESS")
        self.assertNotIn("campaignSite", people[1])
        self.assertEqual(people[1]["campaignCommittee"], "AMY FOR CONGRESS")
        self.assertNotIn("campaignCommittee", people[2])

    def test_a_lapsed_or_hijacked_domain_is_never_linked(self):
        # On 2026-10-01 seven registered campaign domains served gambling
        # pages under the candidate's name. The committee is still named; only
        # the link goes.
        cache = {"H1": {"found": True, "committee_id": "C1", "name": "WATERS",
                        "url": "https://www.maxinewatersforcongress.com/about"},
                 "H2": {"found": True, "committee_id": "C2", "name": "LIEU",
                        "url": "https://tedlieu.com"},
                 "H3": {"found": True, "committee_id": "C3", "name": "FINE",
                        "url": "https://fine.example"}}
        people = [{"fecCandidateId": "H1"}, {"fecCandidateId": "H2"}, {"fecCandidateId": "H3"}]
        self.assertEqual(campaigns.apply_cache(people, cache), 1)
        self.assertNotIn("campaignSite", people[0])
        self.assertNotIn("campaignSite", people[1])
        self.assertEqual(people[0]["campaignCommittee"], "WATERS")
        self.assertEqual(people[2]["campaignSite"], "https://fine.example")
        self.assertEqual([c for c, _, _ in campaigns.blocked_sites(cache)], ["H1", "H2"])

    def test_a_dead_www_host_does_not_block_its_bare_domain(self):
        # Only "www." failed to resolve; the bare domain may be a working site
        # the committee files later, so the block is no wider than the evidence.
        self.assertEqual(overrides.blocked_campaign_host("https://www.plaskettforcongress.org"),
                         "www.plaskettforcongress.org")
        self.assertIsNone(overrides.blocked_campaign_host("https://plaskettforcongress.org"))
        self.assertEqual(overrides.blocked_campaign_host("https://WWW.LukeBronin.com/"),
                         "lukebronin.com")
        for junk in (None, "", "not a url", "http://[bad"):
            self.assertIsNone(overrides.blocked_campaign_host(junk))

    def test_every_blocklist_entry_says_why(self):
        for host, (kind, checked, seen) in overrides.BLOCKED_CAMPAIGN_HOSTS.items():
            self.assertIn(kind, ("hijacked", "dead"), host)
            self.assertRegex(checked, r"^\d{4}-\d{2}-\d{2}$", host)
            self.assertTrue(seen, host)
            self.assertEqual(host, host.lower(), host)


class TestArticleLinks(unittest.TestCase):
    def test_the_ballot_line_link_is_kept_per_filing(self):
        from kyc import results
        text = "\n".join([
            "{{Election box begin no change | title=Democratic primary results}}",
            "{{Election box winning candidate with party link|party=Democratic Party "
            "|candidate=[[Colin Allred]]|votes=10|percentage=60}}",
            "{{Election box candidate with party link|party=Democratic Party "
            "|candidate=Julie Johnson (incumbent)|votes=5|percentage=40}}",
            "{{Election box end}}",
        ])
        boxes = results.parse_boxes(text)
        self.assertEqual(results.ballot_articles(boxes), {"Colin Allred": "Colin Allred"})
        self.assertEqual(results.link_target("[[File:x.jpg]] [[Bo Baker (politician)|Bo]]"),
                         "Bo Baker (politician)")

    def test_a_filed_candidate_takes_the_article_and_a_member_keeps_theirs(self):
        from kyc import results
        cache = {"races": {"H-TX-33-2026": {
            "status": {"H8TX32098": "nominee", "H4TX32089": "eliminated"},
            "article": {"H8TX32098": "Colin Allred", "H4TX32089": "Julie Johnson (politician)"},
            "decided": {"general": True, "parties": []}}}}
        allred = {"fecCandidateId": "H8TX32098", "isCandidate": True, "source": "fec-field",
                  "state": "TX", "chamber": "House (Candidate)", "districtNum": 33}
        johnson = {"id": "J000310", "fecCandidateId": "H4TX32089", "isCandidate": False,
                   "wikipedia": "Julie Johnson", "chamber": "House", "state": "TX",
                   "districtNum": 32, "seatUp2026": True, "seekingReelection2026": True}
        results.apply_cache([allred, johnson], cache)
        self.assertEqual(allred["wikipedia"], "Colin Allred")
        self.assertEqual(allred["wikipediaVia"], "election-page")
        self.assertEqual(johnson["wikipedia"], "Julie Johnson")


class TestPortraitTitleCheck(unittest.TestCase):
    def test_suffixes_and_double_surnames(self):
        from kyc.portraits import title_is_about
        self.assertTrue(title_is_about("Briscoe Cain", "Briscoe Rowell Cain III"))
        self.assertTrue(title_is_about("Valentina Gomez", "Valentina Gomez Noriega"))
        self.assertFalse(title_is_about("Protests against the 2026 Iran war", "Brian McGinnis"))
        self.assertFalse(title_is_about("Brian Smith", "Brian McGinnis"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
