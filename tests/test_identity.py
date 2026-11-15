"""Who appears on this site in more than one role (kyc/identity.py, rule 104).

Each test makes the records it joins: a check of the rule, not of the day's
data (CLAUDE.md, Conventions)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kyc import identity  # noqa: E402


def member(bioguide, name, state="MN", **extra):
    row = {"id": bioguide, "name": name, "state": state, "chamber": "Senate",
           "officeLabel": f"Senate • {state}", "isCandidate": False, "seatUp2026": False,
           "seekingReelection2026": False, "party": "Democratic", "photos": ["placeholder"]}
    row.update(extra)
    return row


def filer(pid, name, state="ME", label=None, **extra):
    row = {"id": pid, "name": name, "state": state, "chamber": "Senate",
           "officeLabel": label or f"Senate • {state}", "isCandidate": True, "seatUp2026": True,
           "party": "Democratic", "photos": ["placeholder"], "fecCandidateId": pid[4:]
           if pid.startswith("FEC_") else None}
    row.update(extra)
    return row


def stategov(code, governor=None, candidates=(), **officers):
    entry = {}
    if governor:
        entry["governor"] = governor
    if candidates:
        entry["ballot2026"] = {"offices": {"governor": {"up": True, "candidates": {
            "candidates": list(candidates)}}}}
    entry.update(officers)
    return {"states": {code: entry}}


def roles(record):
    return [(r["kind"], r["id"]) for r in record.get("also") or []]


def codes(links):
    return [p[1] for p in identity.problems(links)]


class TestJoinByIds(unittest.TestCase):
    def test_a_member_on_a_governors_list_by_bioguide(self):
        senator = member("K000001", "Ann Example")
        candidate = {"id": "gov-MN-ann-example", "name": "Ann Example", "party": "Democratic",
                     "member": "K000001"}
        links = identity.build([senator], stategov=stategov("MN", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(senator), [("candidate", "gov-MN-ann-example")])
        self.assertEqual(roles(candidate), [("profile", "K000001")])
        words = senator["also"][0]
        self.assertEqual(words["words"], "On the Nov 3, 2026 ballot for Governor of Minnesota")
        self.assertEqual(words["after"], "Was on the Nov 3, 2026 ballot for Governor of Minnesota")
        self.assertEqual(words["href"], "states/mn.html#/official/gov-MN-ann-example")
        self.assertEqual(candidate["also"][0]["words"], "Member of the U.S. Senate for Minnesota")
        self.assertEqual(candidate["also"][0]["view"], "#/profile/K000001")
        # Undo the id and nothing joins.
        candidate.pop("member")
        links = identity.build([senator], stategov=stategov("MN", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(senator), [])
        self.assertEqual(roles(candidate), [])

    def test_a_name_alone_joins_nobody_and_is_reported(self):
        senator = member("K000002", "Bob Sample")
        candidate = {"id": "gov-MN-bob-sample", "name": "Bob Sample", "party": "Democratic"}
        links = identity.build([senator], stategov=stategov("MN", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(senator), [])
        self.assertEqual(roles(candidate), [])
        self.assertIn("identity-look-alike", codes(links))

    def test_an_id_whose_names_disagree_is_withheld(self):
        challenger = filer("FEC_S6MN00001", "Carl Jones", state="MN",
                           politicalHistory={"wikidata": "Q1", "rows": []})
        candidate = {"id": "gov-MN-dana-smith", "name": "Dana Smith", "party": "Republican",
                     "politicalHistory": {"wikidata": "Q1", "rows": []}}
        links = identity.build([challenger], stategov=stategov("MN", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        self.assertEqual(roles(candidate), [])
        self.assertIn("identity-names-disagree", codes(links))
        # The same id with names that agree joins.
        candidate["name"] = "Carl R. Jones"
        links = identity.build([challenger], stategov=stategov("MN", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(challenger), [("candidate", "gov-MN-dana-smith")])

    def test_a_departed_member_now_an_official(self):
        row = {"id": "V000001", "name": "J.D. Example", "chamber": "Senate", "state": "OH",
               "left": "2025-01-09"}
        vp = {"id": "x-jd-example", "name": "JD Example", "office": "Vice President of the United States",
              "links": {"bioguide": "V000001"}}
        links = identity.build([], departed=[row], federal={"vicePresident": vp})
        identity.attach(links)
        self.assertEqual(roles(row), [("official", "x-jd-example")])
        self.assertEqual(row["also"][0]["words"], "Vice President of the United States")
        self.assertEqual(row["also"][0]["href"], "federal/index.html#/official/x-jd-example")
        self.assertEqual(vp["also"][0]["kind"], "departed")
        self.assertEqual(vp["also"][0]["words"],
                         "Left the U.S. Senate on Jan. 9, 2025, as the member for Ohio")
        self.assertTrue(vp["also"][0]["href"].endswith("/V000001"))

    def test_a_departed_member_by_the_records_wikidata_item(self):
        row = {"id": "S000001", "name": "Mia Example", "chamber": "House", "state": "NJ",
               "district": 11, "left": "2025-11-20"}
        governor = {"id": "gov-NJ", "name": "Mia Example", "wikidata": "Q7", "since": "January 20, 2026"}
        cache = {"members": [{"bioguide": "S000001", "wikidata": "Q7"}]}
        links = identity.build([], departed=[row], departed_cache=cache,
                               stategov=stategov("NJ", governor=governor))
        identity.attach(links)
        self.assertEqual(roles(row), [("governor", "gov-NJ")])
        self.assertEqual(row["also"][0]["words"],
                         "Governor of New Jersey, in office since January 20, 2026")
        self.assertIn("NJ-11", governor["also"][0]["words"])
        links = identity.build([], departed=[row], departed_cache={"members": []},
                               stategov=stategov("NJ", governor=governor))
        identity.attach(links)
        self.assertEqual(roles(row), [])

    def test_a_governor_running_for_congress(self):
        governor = {"id": "gov-ME", "name": "Jan Example", "wikidata": "Q2", "since": "January 2, 2019"}
        challenger = filer("FEC_S6ME00001", "Jan Trafton Example",
                           politicalHistory={"wikidata": "Q2", "rows": []})
        links = identity.build([challenger], stategov=stategov("ME", governor=governor))
        identity.attach(links)
        self.assertEqual(roles(challenger), [("governor", "gov-ME")])
        self.assertEqual(governor["also"][0]["words"], "Candidate for the U.S. Senate in Maine")
        self.assertEqual(governor["also"][0]["after"], "In the 2026 race for the U.S. Senate in Maine")

    def test_a_governor_on_their_own_list_is_one_card(self):
        governor = {"id": "gov-ID", "name": "Brad Example", "wikidata": "Q3"}
        candidate = {"id": "gov-ID-brad-example", "name": "Brad Example", "holder": True,
                     "politicalHistory": {"wikidata": "Q3", "rows": []}}
        links = identity.build([], stategov=stategov("ID", governor=governor, candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(governor), [])
        self.assertEqual(roles(candidate), [])
        self.assertNotIn("identity-look-alike", codes(links))

    def test_a_judge_by_the_wikidata_item_carrying_their_fjc_id(self):
        judge = {"id": "fjc-123", "name": "Pat Example", "seats": [{"court": "ca5", "title": "Judge"}]}
        courts = {"ca5": {"name": "U.S. Court of Appeals for the Fifth Circuit", "judges": [judge]}}
        candidate = {"id": "gov-TX-pat-example", "name": "Pat Example",
                     "politicalHistory": {"wikidata": "Q9", "rows": []}}
        links = identity.build([], courts=courts, judge_links={"judges": {"123": {"wikidata": "Q9"}}},
                               stategov=stategov("TX", candidates=[candidate]))
        identity.attach(links)
        identity.attach_courts(links, courts)
        self.assertEqual(roles(judge), [("candidate", "gov-TX-pat-example")])
        self.assertEqual(candidate["also"][0]["words"],
                         "Judge of the U.S. Court of Appeals for the Fifth Circuit")
        self.assertEqual(candidate["also"][0]["href"], "courts/ca5.html#/official/fjc-123")
        links = identity.build([], courts=courts, judge_links={"judges": {"123": {"wikidata": "Q8"}}},
                               stategov=stategov("TX", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(judge), [])


class TestTwoSources(unittest.TestCase):
    def officer(self):
        return {"name": "Phil Example", "title": "Attorney General", "party": "D", "partyKey": "D"}

    def test_an_officer_on_a_governors_list(self):
        off = self.officer()
        candidate = {"id": "gov-CO-phil-example", "name": "Phil Example", "politicalHistory": {
            "wikidata": "Q4", "rows": [{"office": "Colorado Attorney General", "where": "Colorado",
                                        "from": "2019", "current": True}]}}
        links = identity.build([], stategov=stategov("CO", candidates=[candidate], ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [("candidate", "gov-CO-phil-example")])
        self.assertEqual(candidate["also"][0]["words"], "Attorney General of Colorado")
        self.assertEqual(candidate["also"][0]["href"], "states/co.html#state-government")

    def test_an_officer_with_no_corroborated_record_is_reported_not_joined(self):
        off = self.officer()
        candidate = {"id": "gov-CO-phil-example", "name": "Phil Example",
                     "politicalHistory": {"rows": [{"office": "Colorado Attorney General",
                                                    "where": "Colorado", "from": "2019", "to": "2023"}]}}
        links = identity.build([], stategov=stategov("CO", candidates=[candidate], ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertIn("identity-look-alike", codes(links))

    def test_the_card_must_name_them_by_rule_56(self):
        off = dict(self.officer(), name="Philip Other")
        candidate = {"id": "gov-CO-phil-example", "name": "Phil Example", "politicalHistory": {
            "rows": [{"office": "Colorado Attorney General", "where": "Colorado", "current": True}]}}
        links = identity.build([], stategov=stategov("CO", candidates=[candidate], ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        # An unconfirmed association listing is not the office's word.
        off = dict(self.officer(), unconfirmed=True)
        links = identity.build([], stategov=stategov("CO", candidates=[candidate], ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [])

    def test_a_legislator_running_for_congress(self):
        challenger = filer("FEC_H6TX00001", "Gina Example", state="TX", label="House • TX-37",
                           wikipedia="Gina Example")
        history = {"people": {"FEC_H6TX00001": {"wikipedia": "Gina Example", "offices": [
            {"office": "Member of the Texas House of Representatives", "where": "Texas",
             "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/1", "name": "Gina Example", "chamber": "lower", "district": "49",
                "districtId": "049", "state": "TX"}
        page = {"id": "ocd-person/1", "name": "Gina Example", "district": "49"}
        legislatures = {"TX": {"chambers": {"lower": {"title": "House of Representatives",
                                                      "members": {"049": [page]}}}}}
        links = identity.build([challenger], history=history, legislators={"states": {"TX": [seat]}},
                               legislatures=legislatures)
        identity.attach(links)
        identity.attach_legislatures(links, legislatures)
        self.assertEqual(roles(challenger), [("legislator", "ocd-person/1")])
        self.assertEqual(challenger["also"][0]["words"],
                         "Member of the Texas House of Representatives, district 49")
        self.assertEqual(challenger["also"][0]["href"], "legislature/tx.html#/?chamber=lower&d=049")
        self.assertEqual(roles(page), [("profile", "FEC_H6TX00001")])
        # A second member of the same name in the chamber: nobody is joined.
        twin = dict(seat, id="ocd-person/2", districtId="050", district="50")
        links = identity.build([challenger], history=history,
                               legislators={"states": {"TX": [seat, twin]}}, legislatures=legislatures)
        identity.attach(links)
        identity.attach_legislatures(links, legislatures)
        self.assertEqual(roles(challenger), [])
        self.assertEqual(roles(page), [])


class TestWords(unittest.TestCase):
    def test_share_html_takes_the_tense_of_the_results_day(self):
        record = {"also": [{"kind": "candidate", "words": "On the ballot", "after": "Was on the ballot",
                            "share": "o/gov-MN-x.html", "href": "states/mn.html#/official/gov-MN-x"}]}
        self.assertIn(">On the ballot<", identity.share_html(record, post=False))
        self.assertIn(">Was on the ballot<", identity.share_html(record, post="2026-11-05"))
        self.assertIn('href="../o/gov-MN-x.html"', identity.share_html(record))
        self.assertEqual(identity.share_html({}), "")

    def test_a_congress_biography_only_where_no_card_holds_that_service(self):
        official = {"id": "x-sean-example", "name": "Sean Example", "title": "Secretary of Transportation",
                    "politicalHistory": {"wikidata": "Q5", "rows": [
                        {"office": "U.S. Representative", "congress": True}]}}
        history = {"people": {"x-sean-example": {"bioguide": "D000001", "wikidata": "Q5"}}}
        fed = {"offices": [{"office": "Secretary of Transportation", "holder": official}]}
        links = identity.build([], federal=fed, history=history)
        self.assertEqual(identity.congress_bios(links, history=history), 1)
        self.assertEqual(official["congressBio"], "D000001")
        self.assertIn("D000001", identity.congress_bio_html(official))
        # A departed row of that member holds the service: no second link.
        row = {"id": "D000001", "name": "Sean Example", "chamber": "House", "state": "WI",
               "district": 7, "left": "2019-09-23"}
        links = identity.build([], federal=fed, history=history, departed=[row])
        identity.congress_bios(links, history=history)
        self.assertNotIn("congressBio", official)

    def test_names_agree(self):
        self.assertTrue(identity.names_agree("Janet Trafton Mills", "Janet Mills"))
        self.assertTrue(identity.names_agree("J.D. Vance", "JD Vance"))
        self.assertTrue(identity.names_agree("Kathy C. Hochul", "Kathy Hochul"))
        self.assertFalse(identity.names_agree("Carl Jones", "Dana Smith"))
        self.assertFalse(identity.names_agree("Mike Rogers", "Tom Rogers"))


if __name__ == "__main__":
    unittest.main()
