"""Who appears on this site in more than one role (kyc/identity.py, rule 105).

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
        self.assertEqual(candidate["also"][0]["words"], "Member of Congress, holding a U.S. Senate seat from Minnesota")
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
                         "Former U.S. Senator from Ohio; congress-legislators ends the term on "
                         "Jan. 9, 2025")
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
        self.assertEqual(governor["also"][0]["after"], "2026 race for the U.S. Senate in Maine")

    def test_a_governor_on_their_own_list_is_one_card(self):
        governor = {"id": "gov-ID", "name": "Brad Example", "wikidata": "Q3"}
        candidate = {"id": "gov-ID-brad-example", "name": "Brad Example", "holder": True,
                     "politicalHistory": {"wikidata": "Q3", "rows": []}}
        links = identity.build([], stategov=stategov("ID", governor=governor, candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(governor), [])
        self.assertEqual(roles(candidate), [])
        self.assertNotIn("identity-look-alike", codes(links))
        # One card is no person joined: the build's count leaves them out.
        self.assertEqual(identity.joined(links), [])
        self.assertNotIn("identity-joined", codes(links))

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


def official(oid, name, title, item=None, **extra):
    row = {"id": oid, "name": name, "title": title}
    if item:
        row["politicalHistory"] = {"wikidata": item, "rows": []}
    row.update(extra)
    return {"offices": [{"office": title, "holder": row}]}, row


class TestTheHistoryRoute(unittest.TestCase):
    """The bioguide congress-legislators gives for a record's own item, read
    from the history cache: the route that ties Rubio, Mullin, Sherrill."""

    def test_a_departed_member_and_an_official_tied_by_the_history_bioguide(self):
        row = {"id": "R000001", "name": "Marco Example", "chamber": "Senate", "state": "FL",
               "left": "2025-01-20"}
        fed, holder = official("x-marco-example", "Marco Example", "Secretary of State", item="Q11")
        history = {"people": {"x-marco-example": {"bioguide": "R000001", "wikidata": "Q11"}}}
        links = identity.build([], departed=[row], federal=fed, history=history)
        identity.attach(links)
        self.assertEqual(roles(holder), [("departed", "R000001")])
        self.assertEqual(roles(row), [("official", "x-marco-example")])
        # Undo the route (no entry) and nothing ties them.
        links = identity.build([], departed=[row], federal=fed, history={"people": {}})
        identity.attach(links)
        self.assertEqual(roles(holder), [])

    def test_a_stale_entry_is_refused_and_warned(self):
        # The entry was read for another item than the record's own.
        row = {"id": "T000999", "name": "Scott Example", "chamber": "House", "state": "TX",
               "district": 3, "left": "2019-01-03"}
        fed, holder = official("x-scott-example", "Scott Example", "Secretary of Housing",
                               item="Q20")
        history = {"people": {"x-scott-example": {"bioguide": "T000999", "wikidata": "Q21"}}}
        links = identity.build([], departed=[row], federal=fed, history=history)
        identity.attach(links)
        self.assertEqual(roles(holder), [])
        self.assertEqual(roles(row), [])
        self.assertIn("identity-history-stale", codes(links))

    def test_a_profiles_entry_read_from_another_article_is_refused(self):
        challenger = filer("FEC_H6TX00009", "Scott Example", state="TX", label="House • TX-3",
                           wikipedia="Scott Example (politician)",
                           politicalHistory={"wikidata": "Q30", "rows": []})
        row = {"id": "T000998", "name": "Scott Example", "chamber": "House", "state": "TX",
               "district": 3, "left": "2019-01-03"}
        history = {"people": {"FEC_H6TX00009": {"bioguide": "T000998", "wikidata": "Q30",
                                                "asked": "Scott Example"}}}
        links = identity.build([challenger], departed=[row], history=history)
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        history["people"]["FEC_H6TX00009"]["asked"] = "Scott Example (politician)"
        links = identity.build([challenger], departed=[row], history=history)
        identity.attach(links)
        self.assertEqual(roles(challenger), [("departed", "T000998")])

    def test_a_congress_biography_needs_the_records_own_item_and_a_congress_row(self):
        fed, holder = official("x-lee-example", "Lee Example", "Administrator", item="Q40")
        holder["politicalHistory"]["rows"] = [{"office": "U.S. Representative", "congress": True}]
        history = {"people": {"x-lee-example": {"bioguide": "Z000001", "wikidata": "Q41"}}}
        links = identity.build([], federal=fed, history=history)
        self.assertEqual(identity.congress_bios(links, history=history), 0)
        self.assertNotIn("congressBio", holder)
        history["people"]["x-lee-example"]["wikidata"] = "Q40"
        links = identity.build([], federal=fed, history=history)
        self.assertEqual(identity.congress_bios(links, history=history), 1)
        holder["politicalHistory"]["rows"] = [{"office": "Governor of New York"}]
        links = identity.build([], federal=fed, history=history)
        self.assertEqual(identity.congress_bios(links, history=history), 0)
        self.assertNotIn("congressBio", holder)


class TestTheGuards(unittest.TestCase):
    def officer(self, name="Ken Example"):
        return {"name": name, "title": "Attorney General", "party": "R", "partyKey": "R"}

    def held(self, office, where="Texas", **row):
        return dict({"office": office, "current": True}, **({"where": where} if where else {}),
                    **row)

    def joined(self, rows, state="TX", off=None):
        off = off or self.officer()
        person = filer("CAND_9", "Ken Example", state=state,
                       politicalHistory={"rows": rows})
        links = identity.build([person], stategov=stategov("TX", ag=off))
        identity.attach(links)
        return roles(off)

    def test_the_officer_row_must_be_the_office_in_that_state(self):
        self.assertEqual(self.joined([self.held("Texas Attorney General")]), [("profile", "CAND_9")])
        # Another state's office, by its where.
        self.assertEqual(self.joined([self.held("Attorney General of Oklahoma", "Oklahoma")]), [])
        # No where: the label must name the state in the office's slot.
        self.assertEqual(self.joined([self.held("Attorney General of Texas", None)]),
                         [("profile", "CAND_9")])
        self.assertEqual(self.joined([self.held("Oklahoma Attorney General", None)]), [])
        self.assertEqual(self.joined([self.held("Attorney General", None)]), [])

    def test_a_deputy_or_assistant_or_us_office_is_not_the_office(self):
        for office in ("Chief Deputy Attorney General of Texas", "Assistant Attorney General",
                       "United States Attorney General", "Acting Attorney General of Texas"):
            self.assertEqual(self.joined([self.held(office)]), [], office)

    def test_an_officer_is_joined_only_in_its_own_state(self):
        self.assertEqual(self.joined([self.held("Texas Attorney General")], state="OK"), [])

    def test_two_profiles_the_dialog_cross_links_name_no_one(self):
        # A member's profile and their candidacy's, which the profile dialog
        # cross-links itself (alsoRunningId, incumbentId; rule 30): one
        # card, no line between them.
        a = member("B000001", "Andy Example", state="KY", fecCandidateId="H0KY06104",
                   alsoRunningId="FEC_S6KY00001")
        b = filer("FEC_S6KY00001", "Andy Example", state="KY", otherFecIds=["H0KY06104"],
                  incumbentId="B000001")
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual(roles(a), [])
        self.assertEqual(roles(b), [])
        # Either field alone is the dialog's link.
        a.pop("alsoRunningId")
        identity.attach(identity.build([a, b]))
        self.assertEqual(roles(a), [])
        # Two profiles an id ties that no dialog links name each other, as
        # any two cards do: "one card, no line" was said of every pair.
        b.pop("incumbentId")
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual(roles(a), [("profile", "FEC_S6KY00001")])
        self.assertEqual(roles(b), [("profile", "B000001")])

    def test_an_fec_id_joins(self):
        # A member's profile and their candidacy's share the FEC id; the
        # candidacy's article's item is a governor list's card's. The member's
        # card names the list through the FEC id alone.
        a = member("B000002", "Andy Example", state="KY", fecCandidateId="H0KY06105",
                   alsoRunningId="FEC_S6KY00002")
        b = filer("FEC_S6KY00002", "Andy Example", state="KY", otherFecIds=["H0KY06105"],
                  incumbentId="B000002", politicalHistory={"wikidata": "Q70", "rows": []})
        candidate = {"id": "gov-KY-andy-example", "name": "Andy Example",
                     "politicalHistory": {"wikidata": "Q70", "rows": []}}
        links = identity.build([a, b], stategov=stategov("KY", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(a), [("candidate", "gov-KY-andy-example")])
        b["otherFecIds"] = []
        links = identity.build([a, b], stategov=stategov("KY", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(a), [])

    def test_one_item_on_two_states_cards_is_reported_not_joined(self):
        a = {"id": "gov-MN-pat-example", "name": "Pat Example",
             "politicalHistory": {"wikidata": "Q50", "rows": []}}
        b = {"id": "gov-WI-pat-example", "name": "Pat Example",
             "politicalHistory": {"wikidata": "Q50", "rows": []}}
        payload = {"states": {
            "MN": stategov("MN", candidates=[a])["states"]["MN"],
            "WI": stategov("WI", candidates=[b])["states"]["WI"]}}
        links = identity.build([], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(a), [])
        self.assertEqual(roles(b), [])
        self.assertIn("identity-states-disagree", codes(links))
        # A governor of one state on another's list, the same.
        governor = {"id": "gov-MN", "name": "Pat Example", "wikidata": "Q50"}
        payload["states"]["MN"] = stategov("MN", governor=governor)["states"]["MN"]
        links = identity.build([], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(governor), [])
        self.assertIn("identity-states-disagree", codes(links))

    def test_look_alikes_across_states_are_not_reported(self):
        senator = member("K000003", "Bob Sample", state="MN")
        candidate = {"id": "gov-WI-bob-sample", "name": "Bob Sample"}
        links = identity.build([senator], stategov=stategov("WI", candidates=[candidate]))
        self.assertNotIn("identity-look-alike", codes(links))

    def test_a_member_who_is_not_a_candidate_is_not_asked_of_the_legislature(self):
        senator = member("K000004", "Gina Example", state="TX", wikipedia="Gina Example")
        history = {"people": {"K000004": {"wikipedia": "Gina Example", "offices": [
            {"office": "Member of the Texas House of Representatives", "where": "Texas",
             "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/9", "name": "Gina Example", "chamber": "lower", "district": "49",
                "state": "TX"}
        links = identity.build([senator], history=history, legislators={"states": {"TX": [seat]}})
        identity.attach(links)
        self.assertEqual(roles(senator), [])
        senator["isCandidate"] = True
        links = identity.build([senator], history=history, legislators={"states": {"TX": [seat]}})
        identity.attach(links)
        self.assertEqual(roles(senator), [("legislator", "ocd-person/9")])

    def test_a_legislator_of_the_same_name_that_nothing_ties_is_reported(self):
        challenger = filer("FEC_H6GA00001", "Houston Example", state="GA", label="House • GA-10")
        seat = {"id": "ocd-person/7", "name": "Houston Example", "chamber": "lower",
                "district": "124", "state": "GA"}
        links = identity.build([challenger], legislators={"states": {"GA": [seat]}})
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        found = [p for p in identity.problems(links) if p[1] == "identity-legislator-look-alike"]
        self.assertEqual(len(found), 1)
        self.assertIn("ocd-person/7", found[0][3][0])
        # Another name: nothing to report.
        seat["name"] = "Hank Other"
        links = identity.build([challenger], legislators={"states": {"GA": [seat]}})
        self.assertNotIn("identity-legislator-look-alike", codes(links))

    def test_a_corroborated_seat_under_another_form_of_the_name_is_reported(self):
        challenger = filer("FEC_H6FL00001", 'Shevrin "Shev" Example', state="FL",
                           label="House • FL-24", wikipedia="Shev Example")
        history = {"people": {"FEC_H6FL00001": {"wikipedia": "Shev Example", "offices": [
            {"office": "Member of the Florida Senate", "where": "Florida", "open": True,
             "agree": "exact"}]}}}
        seat = {"id": "ocd-person/8", "name": "Shev Example", "chamber": "upper", "district": "34",
                "state": "FL"}
        links = identity.build([challenger], history=history,
                               legislators={"states": {"FL": [seat]}})
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        found = [p for p in identity.problems(links) if p[1] == "identity-legislator-look-alike"]
        self.assertEqual(len(found), 1)
        self.assertIn("writes the name another way", found[0][3][0])
        # A person's evidenced entry ties them.
        from kyc import overrides
        saved = dict(overrides.IDENTITY_JOINS)
        try:
            overrides.IDENTITY_JOINS[("profile:FEC_H6FL00001", "legislator:FL:ocd-person/8")] = {
                "same": True, "evidence": "the Senate's page for Shev Example", "read": "2026-11-15"}
            links = identity.build([challenger], history=history,
                                   legislators={"states": {"FL": [seat]}})
            identity.attach(links)
            self.assertEqual(roles(challenger), [("legislator", "ocd-person/8")])
            self.assertNotIn("identity-legislator-look-alike", codes(links))
        finally:
            overrides.IDENTITY_JOINS.clear()
            overrides.IDENTITY_JOINS.update(saved)


class TestNames(unittest.TestCase):
    def test_a_shared_surname_and_initial_is_not_one_person(self):
        self.assertFalse(identity.names_agree("John James", "Jane James"))
        self.assertFalse(identity.names_agree("J. James", "John James"))
        challenger = filer("FEC_S6MI00001", "John James", state="MI",
                           politicalHistory={"wikidata": "Q60", "rows": []})
        candidate = {"id": "gov-MI-jane-james", "name": "Jane James",
                     "politicalHistory": {"wikidata": "Q60", "rows": []}}
        links = identity.build([challenger], stategov=stategov("MI", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        self.assertIn("identity-names-disagree", codes(links))

    def test_a_members_sourced_aliases_are_their_names(self):
        senator = member("T000001", "Thomas Example", state="WI",
                         aliases=["Thomas P. Example", "Tom Example"])
        candidate = {"id": "gov-WI-tom-example", "name": "Tom Example", "member": "T000001"}
        links = identity.build([senator], stategov=stategov("WI", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(senator), [("candidate", "gov-WI-tom-example")])
        senator["aliases"] = []
        links = identity.build([senator], stategov=stategov("WI", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(roles(senator), [])

    def test_a_given_name_without_a_shared_surname_is_not_one_person(self):
        self.assertFalse(identity.names_agree("John Smith", "John Jones"))

    def test_the_lists_printed_form_and_an_evidenced_short_form(self):
        from kyc import overrides
        governor = {"id": "gov-NV", "name": "Joe Example", "wikidata": "Q80"}
        candidate = {"id": "gov-NV-joseph-example", "name": "Joseph Example",
                     "printed": "Example, Joseph", "holder": True,
                     "politicalHistory": {"wikidata": "Q80", "rows": []}}
        saved = dict(overrides.STATEWIDE_NAME_FORMS)
        try:
            overrides.STATEWIDE_NAME_FORMS[("NV", "governor", "Joe Example")] = (
                "Example, Joseph", "the office's own site writes Joe Example (made up)")
            links = identity.build([], stategov=stategov("NV", governor=governor,
                                                         candidates=[candidate]))
            self.assertNotIn("identity-names-disagree", codes(links))
            overrides.STATEWIDE_NAME_FORMS.clear()
            links = identity.build([], stategov=stategov("NV", governor=governor,
                                                         candidates=[candidate]))
            self.assertIn("identity-names-disagree", codes(links))
        finally:
            overrides.STATEWIDE_NAME_FORMS.clear()
            overrides.STATEWIDE_NAME_FORMS.update(saved)

    def test_a_filed_name_and_a_nickname_in_quotes(self):
        self.assertTrue(identity.names_agree(["Shevrin \"Shev\" Jones"], ["Shev Jones"]))
        self.assertTrue(identity.names_agree(["Janet Mills", "MILLS, JANET TRAFTON"],
                                             ["Janet T. Mills"]))
        self.assertTrue(identity.names_agree("Mike Simmons", "Mike Simmons-Gessesse"))


class TestSettledByAPerson(unittest.TestCase):
    def setUp(self):
        from kyc import overrides
        self.overrides = overrides
        self.saved = dict(overrides.IDENTITY_JOINS)

    def tearDown(self):
        self.overrides.IDENTITY_JOINS.clear()
        self.overrides.IDENTITY_JOINS.update(self.saved)

    def settle(self, pair, **entry):
        self.overrides.IDENTITY_JOINS.clear()
        self.overrides.IDENTITY_JOINS[pair] = entry

    def records(self):
        off = {"name": "Jo Example", "title": "Secretary of State", "party": "D", "partyKey": "D"}
        candidate = {"id": "gov-MI-jo-example", "name": "Jo Example"}
        return off, candidate, stategov("MI", candidates=[candidate], sos=off)

    def test_an_evidenced_entry_joins_and_silences_the_warning(self):
        off, candidate, payload = self.records()
        links = identity.build([], stategov=payload)
        self.assertIn("identity-look-alike", codes(links))
        self.settle(("officer:MI:sos", "candidate:gov-MI-jo-example"), same=True,
                    evidence="the office's page names her beside the list", read="2026-11-15")
        links = identity.build([], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(off), [("candidate", "gov-MI-jo-example")])
        self.assertNotIn("identity-look-alike", codes(links))

    def test_a_namesake_entry_silences_and_joins_nothing(self):
        off, candidate, payload = self.records()
        self.settle(("officer:MI:sos", "candidate:gov-MI-jo-example"), same=False,
                    evidence="two people", read="2026-11-15")
        links = identity.build([], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertNotIn("identity-look-alike", codes(links))
        self.assertNotIn("stale-identity-join", codes(links))

    def test_an_entry_is_stale_checked_and_must_be_evidenced(self):
        _off, _candidate, payload = self.records()
        self.settle(("officer:MI:sos", "candidate:gov-MI-nobody"), same=True,
                    evidence="x", read="2026-11-15")
        self.assertIn("stale-identity-join", codes(identity.build([], stategov=payload)))
        self.settle(("officer:MI:sos", "candidate:gov-MI-jo-example"), same=True, read="2026-11-15")
        links = identity.build([], stategov=payload)
        self.assertIn("identity-join-unevidenced", codes(links))
        self.assertIn("identity-look-alike", codes(links))
        # A "same" entry the records now join themselves is stale too.
        senator = member("K000005", "Ann Example")
        cand = {"id": "gov-MN-ann-example", "name": "Ann Example", "member": "K000005"}
        self.settle(("profile:K000005", "candidate:gov-MN-ann-example"), same=True,
                    evidence="x", read="2026-11-15")
        links = identity.build([senator], stategov=stategov("MN", candidates=[cand]))
        self.assertIn("stale-identity-join", codes(links))
        # And a "two people" entry an id contradicts is said.
        self.settle(("profile:K000005", "candidate:gov-MN-ann-example"), same=False,
                    evidence="x", read="2026-11-15")
        links = identity.build([senator], stategov=stategov("MN", candidates=[cand]))
        self.assertIn("identity-join-contradicted", codes(links))


class TestRoleWords(unittest.TestCase):
    def term(self):
        return {"from": "2027-01-01", "day": "2027-01-01", "kind": "on", "cite": "Tex. Const.",
                "source": "https://example.gov/", "words": "", "counted": False}

    def test_an_officers_role_ends_on_its_cards_clock(self):
        off = {"name": "Ken Example", "title": "Attorney General", "party": "R", "partyKey": "R"}
        person = filer("CAND_9", "Ken Example", state="TX", politicalHistory={"rows": [
            {"office": "Texas Attorney General", "where": "Texas", "current": True}]})
        entry = {"ag": off, "ballot2026": {"offices": {"ag": {
            "up": True, "termBegins": self.term(),
            "outgoing": {"holder": "Ken Example", "why": "not-listed", "roster": "RAGA's roster",
                         "read": "2026-11-10"}}}}}
        links = identity.build([person], stategov={"states": {"TX": entry}})
        identity.attach(links)
        role = person["also"][0]
        self.assertEqual(role["words"], "Attorney General of Texas")
        self.assertEqual(role["ends"], "2027-01-01")
        self.assertEqual(role["ended"], "Was Attorney General of Texas, until the term the 2026 "
                                        "election chose began on Jan. 1, 2027")
        self.assertIn(">Attorney General of Texas<", identity.share_html(person, post="2026-11-13"))
        self.assertIn(">Was Attorney General", identity.share_html(person, post="2027-01-08"))
        # A roster read after the term began says so even before the results
        # are read again (the governor's share page's rule).
        role["endsRead"] = "2027-01-09"
        self.assertIn(">Was Attorney General", identity.share_html(person, post="2026-11-13"))
        self.assertNotIn(">Was Attorney General", identity.share_html(person, post=False))
        # A holder on the ballot for the office keeps the words: no end.
        entry["ballot2026"]["offices"]["ag"].pop("outgoing")
        links = identity.build([person], stategov={"states": {"TX": entry}})
        identity.attach(links)
        self.assertNotIn("ends", person["also"][0])

    def test_a_governors_role_ends_too(self):
        governor = {"id": "gov-ME", "name": "Jan Example", "wikidata": "Q2", "since": "January 2, 2019"}
        challenger = filer("FEC_S6ME00001", "Jan Example", politicalHistory={"wikidata": "Q2", "rows": []})
        entry = {"governor": governor, "ballot2026": {"offices": {"governor": {
            "up": True, "termBegins": dict(self.term(), **{"from": "2027-01-06", "day": "2027-01-06"}),
            "outgoing": {"holder": "Jan Example", "why": "term-limit", "roster": "The NGA's roster",
                         "read": "2026-11-10"}}}}}
        links = identity.build([challenger], stategov={"states": {"ME": entry}})
        identity.attach(links)
        self.assertEqual(challenger["also"][0]["ended"],
                         "Was Governor of Maine, until the term the 2026 election chose began on "
                         "Jan. 6, 2027")

    def test_a_departed_members_words_are_their_rows(self):
        for row, words in (
                ({"chamber": "Senate", "state": "OH"}, "Former U.S. Senator from Ohio"),
                ({"chamber": "House", "state": "NJ", "district": 11}, "Former U.S. Representative, NJ-11"),
                ({"chamber": "House", "state": "VI", "district": 0},
                 "Former Delegate from the U.S. Virgin Islands")):
            row = dict(row, id="X000001", name="X Example", left="2025-01-09")
            role = identity.departed_role(row)
            self.assertTrue(role["words"].startswith(words + "; congress-legislators ends the term on "
                                                     "Jan. 9, 2025"), role["words"])
            self.assertFalse(role["words"].startswith("Left"))

    def test_a_judges_role_is_their_latest_seat_with_their_service(self):
        judge = {"id": "fjc-5", "name": "Pat Example", "status": "senior", "seats": [
            {"court": "txnd", "title": "Judge", "commissioned": "2001-01-01", "seniorSince": None},
            {"court": "ca5", "title": "Circuit Judge", "commissioned": "2010-01-01",
             "seniorSince": "2024-03-01"}]}
        two = dict(judge, status="active", seats=[
            {"court": "ca5", "title": "Judge", "commissioned": "2001-01-01"},
            {"court": "ca5", "title": "Circuit Judge", "commissioned": "2010-01-01"}])
        self.assertTrue(identity.judge_role(two, "ca5", "U.S. Court of Appeals")["words"]
                        .startswith("Circuit Judge of"))
        role = identity.judge_role(judge, "ca5", "U.S. Court of Appeals for the Fifth Circuit")
        self.assertEqual(role["words"], "Circuit Judge of the U.S. Court of Appeals for the Fifth "
                                        "Circuit, senior status since March 1, 2024")
        # Listed in two courts' files, a judge is noded where they sit now.
        courts = {"ca5": {"name": "U.S. Court of Appeals for the Fifth Circuit", "judges": [judge]},
                  "aaa": {"name": "U.S. District Court A", "judges": [judge]}}
        candidate = {"id": "gov-TX-pat-example", "name": "Pat Example",
                     "politicalHistory": {"wikidata": "Q9", "rows": []}}
        links = identity.build([], courts=courts, judge_links={"judges": {"5": {"wikidata": "Q9"}}},
                               stategov=stategov("TX", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(candidate["also"][0]["court"], "ca5")
        active = dict(judge, status="active", listedSenior={"since": "2026-10-05"},
                      seats=[dict(judge["seats"][1], seniorSince=None)])
        self.assertIn("senior status from Oct. 5, 2026 by the courts’ list of vacancies; the FJC "
                      "directory still lists active service",
                      identity.judge_role(active, "ca5", "U.S. Court of Appeals")["words"])

    def test_a_legislators_district_in_its_legislatures_words(self):
        self.assertEqual(identity.legislator_role("TX", {"district": "49"}, "House of Representatives")
                         ["words"], "Member of the Texas House of Representatives, district 49")
        self.assertEqual(identity.legislator_role("MA", {"district": "18th Essex"},
                                                  "House of Representatives")["words"],
                         "Member of the Massachusetts House of Representatives, for the 18th "
                         "Essex district")

    def test_a_territorys_one_seat_in_its_own_words(self):
        delegate = member("P000001", "Stacey Example", state="VI", chamber="House",
                          officeLabel="House • VI-AL")
        candidate = {"id": "gov-VI-stacey-example", "name": "Stacey Example", "member": "P000001"}
        links = identity.build([delegate], stategov=stategov("VI", candidates=[candidate]))
        identity.attach(links)
        self.assertEqual(candidate["also"][0]["words"],
                         "Member of Congress, holding the U.S. Virgin Islands’ seat in the U.S. House")
        # After Election Day a candidate's race is named, not their place in it.
        challenger = filer("FEC_S6ME00002", "Jan Other")
        role = identity.profile_role(challenger, {}, {}, "2026-11-13")
        self.assertEqual(role["words"], "Candidate for the U.S. Senate in Maine")
        self.assertEqual(role["after"], "2026 race for the U.S. Senate in Maine")


class SettledEntries(unittest.TestCase):
    """A base that puts ``overrides.IDENTITY_JOINS`` back."""

    def setUp(self):
        from kyc import overrides
        self.overrides = overrides
        self.saved = dict(overrides.IDENTITY_JOINS)
        overrides.IDENTITY_JOINS.clear()

    def tearDown(self):
        self.overrides.IDENTITY_JOINS.clear()
        self.overrides.IDENTITY_JOINS.update(self.saved)

    def settle(self, pair, **entry):
        self.overrides.IDENTITY_JOINS[pair] = dict({"evidence": "made up", "read": "2026-11-15"},
                                                   **entry)


def term(day="2027-01-12"):
    return {"from": day, "day": day, "kind": "on", "cite": "Made-up Const.",
            "source": "https://example.gov/", "words": "", "counted": False}


def outgoing(name):
    return {"holder": name, "why": "not-listed", "roster": "a roster", "read": "2026-11-10"}


class TestTheRecordPhase(SettledEntries):
    """January 3: a candidate's and a seated winner's open offices are said
    to have been open when the record was read (``openWhenRead``,
    ``history.for_page``'s *before_seat*), and no longer ``current``."""

    def officer(self, name="Phil Example"):
        return {"name": name, "title": "Attorney General", "party": "D", "partyKey": "D"}

    def payload(self, candidate, off):
        entry = {"ag": off, "ballot2026": {"offices": {
            "governor": {"up": True, "candidates": {"candidates": [candidate]}},
            "ag": {"up": True, "termBegins": term(), "outgoing": outgoing(off["name"])}}}}
        return {"states": {"CO": entry}}

    def candidate(self, **row):
        row = dict({"office": "Colorado Attorney General", "where": "Colorado", "from": "2019"}, **row)
        return {"id": "gov-CO-phil-example", "name": "Phil Example",
                "politicalHistory": {"wikidata": "Q4", "rows": [row]}}

    def test_an_office_open_when_read_still_joins_while_the_card_names_them(self):
        off, candidate = self.officer(), self.candidate(openWhenRead="2026-11-14")
        links = identity.build([], stategov=self.payload(candidate, off))
        identity.attach(links)
        self.assertEqual(roles(off), [("candidate", "gov-CO-phil-example")])
        self.assertNotIn("identity-look-alike", codes(links))
        # The role keeps its end on the card's own clock.
        role = candidate["also"][0]
        self.assertEqual((role["words"], role["ends"]), ("Attorney General of Colorado", "2027-01-12"))
        self.assertTrue(role["ended"].startswith("Was Attorney General of Colorado, until the term"))
        why = [w for _name, _keys, whys in identity.joined(links) for w in whys]
        self.assertEqual(why, ["Colorado Attorney General in the record, open when it was read on "
                               "2026-11-14; the officer card names them"])
        # A row that ended, or one read open for another office, is no second source.
        for row in ({"to": "2023"}, {"office": "Colorado Secretary of State",
                                     "openWhenRead": "2026-11-14"}):
            off, candidate = self.officer(), self.candidate(**row)
            links = identity.build([], stategov=self.payload(candidate, off))
            identity.attach(links)
            self.assertEqual(roles(off), [], row)
            self.assertIn("identity-look-alike", codes(links), row)

    def test_a_record_holding_the_office_under_another_given_name_is_said(self):
        # The record phase names a seated winner from Congress's record
        # ("Margaret Example"); the card writes the name they go by.
        off = self.officer("Peggy Example")
        candidate = dict(self.candidate(openWhenRead="2026-11-14"), name="Margaret Example")
        links = identity.build([], stategov=self.payload(candidate, off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        found = [p for p in identity.problems(links) if p[1] == "identity-names-disagree"]
        self.assertEqual([p[3] for p in found], [["officer:CO:ag", "candidate:gov-CO-phil-example"]])
        # A form of the name the record's own sources write joins them.
        candidate = dict(candidate, aliases=["Peggy Example"])
        links = identity.build([], stategov=self.payload(candidate, off))
        identity.attach(links)
        self.assertEqual(roles(off), [("candidate", "gov-CO-phil-example")])
        self.assertNotIn("identity-names-disagree", codes(links))
        # Another surname altogether says nothing.
        links = identity.build([], stategov=self.payload(dict(candidate, aliases=[]),
                                                         self.officer("Mia Other")))
        self.assertNotIn("identity-names-disagree", codes(links))

    def test_the_join_ends_when_the_card_names_someone_else(self):
        off, candidate = self.officer("Mia Other"), self.candidate(openWhenRead="2026-11-14")
        links = identity.build([], stategov=self.payload(candidate, off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertEqual(roles(candidate), [])
        self.assertNotIn("identity-look-alike", codes(links))

    def test_an_office_open_when_read_is_never_a_look_alike(self):
        # The card's name is theirs to a reader, though not by rule 56's test
        # (three words between first and last).
        name = "Phil Alpha Beta Gamma Example"
        self.assertFalse(identity.office_names("Phil Example", name))
        self.assertTrue(identity.look_alike("Phil Example", name))
        off, candidate = self.officer(name), self.candidate(openWhenRead="2026-11-14")
        links = identity.build([], stategov=self.payload(candidate, off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertNotIn("identity-look-alike", codes(links))
        # While the record calls the office current, the same pair is said.
        off, candidate = self.officer(name), self.candidate(current=True)
        links = identity.build([], stategov=self.payload(candidate, off))
        self.assertIn("identity-look-alike", codes(links))

    def seated(self, **extra):
        # A winner seated since Election Day (record.seated_winner), their
        # filing folded into the member's profile.
        row = member("E000001", "Gina Example", state="TX", chamber="House",
                     officeLabel="House • TX-37", raceRole="winner", fecCandidateId="H6TX00001",
                     wikipedia="Gina Example")
        row.update(extra)
        return row

    def roster(self):
        history = {"people": {"FEC_H6TX00001": {"asked": "Gina Example", "wikipedia": "Gina Example",
                                                "offices": [
            {"office": "Member of the Texas House of Representatives", "where": "Texas",
             "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/1", "name": "Gina Example", "chamber": "lower", "district": "49",
                "districtId": "049", "state": "TX"}
        return history, {"fetched": "2026-11-14T14:48:44+00:00", "states": {"TX": [seat]}}

    def test_a_seated_winner_the_roster_still_lists_is_no_look_alike(self):
        history, legislators = self.roster()
        winner = self.seated()
        links = identity.build([winner], history=history, legislators=legislators)
        identity.attach(links)
        self.assertEqual(roles(winner), [])              # nothing is linked
        found = {p[1]: p for p in identity.problems(links)}
        self.assertNotIn("identity-legislator-look-alike", found)
        behind = found["identity-legislator-roster-behind"]
        self.assertEqual(behind[0], "warn")
        self.assertIn("1 state legislator card of someone on this site is no current role", behind[2])
        self.assertIn("read 2026-11-14", behind[2])
        self.assertEqual(behind[3], ["profile Gina Example (E000001) and Gina Example (TX lower 49, "
                                     "ocd-person/1): seated in Congress since Election Day, in the "
                                     "seat rule 24's join tied them to as a candidate"])
        # As a candidate the very same records were joined (rule 24).
        running = filer("FEC_H6TX00001", "Gina Example", state="TX", label="House • TX-37",
                        wikipedia="Gina Example")
        links = identity.build([running], history=history, legislators=legislators)
        identity.attach(links)
        self.assertEqual(roles(running), [("legislator", "ocd-person/1")])

    def test_only_the_seat_rule_24_would_tie_is_the_rosters_lag(self):
        history, legislators = self.roster()
        # A member who was not just seated for a race they won: a namesake
        # in the legislature is a look-alike, as before.
        links = identity.build([self.seated(raceRole=None)], history=history,
                               legislators=legislators)
        self.assertEqual([c for c in codes(links) if c.startswith("identity-leg")],
                         ["identity-legislator-look-alike"])
        # A winner whose record holds no seat there (read from another
        # article than the profile links): a look-alike too.
        links = identity.build([self.seated(wikipedia="Gina Example (singer)")], history=history,
                               legislators=legislators)
        self.assertEqual([c for c in codes(links) if c.startswith("identity-leg")],
                         ["identity-legislator-look-alike"])
        # Said for what it is: a seated winner with no corroborated seat
        # there, never "not a candidate".
        line = [p for p in identity.problems(links) if p[1] == "identity-legislator-look-alike"]
        self.assertEqual(line[0][3], [
            "profile Gina Example (E000001) and Gina Example (TX lower 49, ocd-person/1): seated in "
            "Congress since Election Day, and no corroborated seat of theirs while they ran is "
            "this one"])
        # A second member of the name in the other chamber stays a look-alike
        # beside the seat that is behind.
        twin = {"id": "ocd-person/2", "name": "Gina Example", "chamber": "upper", "district": "14",
                "state": "TX"}
        legislators["states"]["TX"].append(twin)
        links = identity.build([self.seated()], history=history, legislators=legislators)
        found = {p[1]: p for p in identity.problems(links)}
        self.assertEqual(len(found["identity-legislator-roster-behind"][3]), 1)
        self.assertEqual(len(found["identity-legislator-look-alike"][3]), 1)
        self.assertIn("ocd-person/2", found["identity-legislator-look-alike"][3][0])
        self.assertTrue(found["identity-legislator-look-alike"][3][0].endswith(
            "seated in Congress since Election Day; the seat rule 24's join tied them to as a "
            "candidate is another"))

    def test_a_seated_winner_named_otherwise_by_congresss_record_is_still_the_rosters_lag(self):
        # Congress's record writes "Christopher M. Rabb"; the candidate, their
        # article and the roster "Chris Rabb".
        history = {"people": {"FEC_H6PA03001": {"asked": "Chris Rabb", "wikipedia": "Chris Rabb",
                                                "offices": [
            {"office": "Member of the Pennsylvania House of Representatives",
             "where": "Pennsylvania", "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/9", "name": "Chris Rabb", "chamber": "lower", "district": "200",
                "state": "PA"}
        legislators = {"fetched": "2026-11-14", "states": {"PA": [seat]}}
        winner = member("Z000081", "Christopher M. Rabb", state="PA", chamber="House",
                        officeLabel="House • PA-3", raceRole="winner", fecCandidateId="H6PA03001",
                        wikipedia="Chris Rabb")
        links = identity.build([winner], history=history, legislators=legislators)
        identity.attach(links)
        self.assertEqual(roles(winner), [])
        found = {p[1]: p for p in identity.problems(links)}
        self.assertNotIn("identity-legislator-look-alike", found)
        self.assertEqual(found["identity-legislator-roster-behind"][3], [
            "profile Christopher M. Rabb (Z000081) and Chris Rabb (PA lower 200, ocd-person/9): "
            "seated in Congress since Election Day, in the seat rule 24's join tied them to as a "
            "candidate"])
        # A member who was not just seated for a race they won says nothing of
        # a legislator of another given name.
        links = identity.build([dict(winner, raceRole=None)], history=history,
                               legislators=legislators)
        self.assertFalse([c for c in codes(links) if c.startswith("identity-leg")])
        # Another article than the one the record was read from ties nothing.
        links = identity.build([dict(winner, wikipedia="Chris Rabb (author)")], history=history,
                               legislators=legislators)
        self.assertFalse([c for c in codes(links) if c.startswith("identity-leg")])

    def test_an_entry_keyed_on_a_filing_follows_it_into_the_members_profile(self):
        off = {"name": "Marty Example", "title": "Attorney General", "party": "R", "partyKey": "R"}
        self.settle(("officer:SD:ag", "profile:FEC_H6SD00001"), same=True)
        running = filer("FEC_H6SD00001", "Marty Example", state="SD", label="House • SD-AL")
        links = identity.build([running], stategov=stategov("SD", ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [("profile", "FEC_H6SD00001")])
        # January 3: the same person under their bioguide id, the filing's
        # FEC id folded in - the entry follows it, and the officer card still
        # naming a member of Congress sitting now is the roster's lag, said
        # apart (TestAnOfficerCardBehindASeatInCongress).
        winner = member("J000001", "Marty Example", state="SD", chamber="House",
                        officeLabel="House • SD-AL", raceRole="winner", fecCandidateId="H6SD00001")
        links = identity.build([winner], stategov=stategov("SD", ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertEqual([c for c in codes(links) if "identity" in c],
                         ["identity-officer-roster-behind"])
        self.assertIn("profile Marty Example (J000001)",
                      [p for p in identity.problems(links)
                       if p[1] == "identity-officer-roster-behind"][0][3][0])
        # Nobody holds the filing: the entry is stale, in the words it was written in.
        links = identity.build([member("J000001", "Marty Example", state="SD")],
                               stategov=stategov("SD", ag=off))
        stale = [p for p in identity.problems(links) if p[1] == "stale-identity-join"]
        self.assertEqual(len(stale), 1)
        self.assertIn("profile:FEC_H6SD00001 is no card this build makes", stale[0][2])


class TestAFoldedCuratedRow(unittest.TestCase):
    def test_a_seated_winners_record_is_read_under_their_curated_rows_id_too(self):
        from kyc import history, record
        winner = member("Z900115", "Jan Example", state="IL", raceRole="winner",
                        fecCandidateId="S6IL00001", otherIds=["CAND_33"], wikipedia="Jan Example")
        self.assertEqual(record.filing_ids(winner), ["FEC_S6IL00001", "CAND_33"])
        people = {"CAND_33": {"asked": "Jan Example", "offices": [
            {"office": "Lieutenant Governor of Illinois", "where": "Illinois", "open": True,
             "agree": "exact", "from": "2019"}]}}
        self.assertIs(history.folded(winner, people), people["CAND_33"])
        # The history cache's bioguide is read under it too: the seated
        # winner and their other filing, the item and that id shared, are one
        # person and name each other, as they did while the winner ran.
        senate = filer("FEC_S4IL00001", "Jan Example", state="IL", wikipedia="Jan Example",
                       politicalHistory={"wikidata": "Q7", "rows": []})
        seated = dict(winner, politicalHistory={"wikidata": "Q7", "rows": []})
        cache = {"people": {"CAND_33": {"asked": "Jan Example", "wikidata": "Q7", "bioguide": "J000999"},
                            "FEC_S4IL00001": {"asked": "Jan Example", "wikidata": "Q7",
                                              "bioguide": "J000999"}}}
        links = identity.build([seated, senate], history=cache)
        identity.attach(links)
        self.assertEqual(roles(seated), [("profile", "FEC_S4IL00001")])
        self.assertNotIn("identity-item-shared", codes(links))
        # Its own id is never one of them, nor one twice.
        self.assertEqual(record.filing_ids(dict(winner, id="CAND_33")), ["FEC_S6IL00001"])
        self.assertEqual(record.filing_ids(dict(winner, otherIds=["CAND_33", "CAND_33"])),
                         ["FEC_S6IL00001", "CAND_33"])


class TestARosterBehindItsLegislature(SettledEntries):
    """A person's evidenced word that a legislator card is theirs but no
    current role: their legislature's own pages seat someone else, while
    the roster (Open States) still seats them - Florida's Senate District
    34 and House District 13 on 2026-11-17."""

    def records(self):
        running = filer("FEC_H6FL00001", "Shev Example", state="FL", label="House • FL-24",
                        wikipedia="Shevrin Example")
        seat = {"id": "ocd-person/9", "name": "Shev Example", "chamber": "upper", "district": "34",
                "districtId": "034", "state": "FL"}
        return running, {"fetched": "2026-11-14T14:48:44+00:00", "states": {"FL": [seat]}}

    def test_one_person_whose_card_is_behind_is_joined_to_nothing_and_said(self):
        running, legislators = self.records()
        pair = ("profile:FEC_H6FL00001", "legislator:FL:ocd-person/9")
        links = identity.build([running], legislators=legislators)
        self.assertIn("identity-legislator-look-alike", codes(links))
        self.settle(pair, same=True, behind="the Florida Senate's page for District 34 names "
                    "Senator Ann Other for 2026-2028")
        links = identity.build([running], legislators=legislators)
        identity.attach(links)
        self.assertEqual(roles(running), [])
        found = {p[1]: p for p in identity.problems(links)}
        self.assertNotIn("identity-legislator-look-alike", found)
        self.assertNotIn("identity-joined", found)
        self.assertNotIn("stale-identity-join", found)
        line = found["identity-legislator-roster-behind"]
        self.assertEqual(line[3], [
            "profile Shev Example (FEC_H6FL00001) and Shev Example (FL upper 34, ocd-person/9): "
            "the Florida Senate's page for District 34 names Senator Ann Other for 2026-2028 "
            "(overrides.IDENTITY_JOINS, read 2026-11-15)"])
        # The same entry without "behind" joins them, as any "same" entry does.
        self.settle(pair, same=True)
        links = identity.build([running], legislators=legislators)
        identity.attach(links)
        self.assertEqual(roles(running), [("legislator", "ocd-person/9")])
        self.assertNotIn("identity-legislator-roster-behind", codes(links))

    def test_a_behind_entry_must_be_one_persons_and_name_a_legislator(self):
        running, legislators = self.records()
        for pair, entry in (
                (("profile:FEC_H6FL00001", "legislator:FL:ocd-person/9"),
                 {"same": False, "behind": "seats another"}),
                (("profile:FEC_H6FL00001", "legislator:FL:ocd-person/9"),
                 {"same": True, "behind": " "}),
                (("profile:FEC_H6FL00001", "officer:FL:ag"), {"same": True, "behind": "x"})):
            self.overrides.IDENTITY_JOINS.clear()
            self.settle(pair, **entry)
            links = identity.build([running], legislators=legislators)
            self.assertIn("identity-join-unevidenced", codes(links), entry)
            self.assertNotIn("identity-legislator-roster-behind", codes(links), entry)

    def test_a_behind_entry_the_roster_has_caught_up_with_is_stale(self):
        running, legislators = self.records()
        self.settle(("profile:FEC_H6FL00001", "legislator:FL:ocd-person/9"), same=True,
                    behind="seats another")
        legislators["states"]["FL"] = [dict(legislators["states"]["FL"][0], id="ocd-person/10",
                                            name="Ann Other")]
        links = identity.build([running], legislators=legislators)
        self.assertIn("stale-identity-join", codes(links))
        self.assertNotIn("identity-legislator-roster-behind", codes(links))


class TestTheRecordedEntries(unittest.TestCase):
    def test_every_entry_is_evidenced_dated_and_copies_no_phone_or_address(self):
        import re
        from kyc import overrides
        phone = re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b|\b\d{10}\b")
        box = re.compile(r"\b(?:P\.?\s*O\.?\s*Box|Box:?)\s*\d", re.I)
        street = re.compile(r"\b\d{2,6}\s+(?:[NSEW]\.?\s+)?(?:[A-Z][a-z]+\.?\s+){1,3}(?:St|Street|Ave|"
                            r"Avenue|Blvd|Road|Rd|Drive|Dr|Hwy|Highway)\b")
        for pair, entry in overrides.IDENTITY_JOINS.items():
            self.assertEqual(len(pair), 2, pair)
            self.assertIn(entry.get("same"), (True, False), pair)
            self.assertRegex(entry.get("read") or "", r"^\d{4}-\d{2}-\d{2}$", pair)
            words = entry.get("evidence", "") + " " + entry.get("behind", "")
            self.assertTrue(entry.get("evidence"), pair)
            for test in (phone, box, street):
                self.assertIsNone(test.search(words), (pair, test.pattern))
        # The tests themselves catch what they look for.
        self.assertTrue(phone.search("call (318) 487-5377"))
        self.assertTrue(box.search("PO BOX 485, HELENA"))
        self.assertTrue(street.search("1040 W. Bryn Mawr Ave."))


class TestAnItemOnTwoProfiles(SettledEntries):
    def people(self):
        incumbent = member("J000307", "John James", state="MI", chamber="House",
                           officeLabel="House • MI-10",
                           politicalHistory={"wikidata": "Q1", "rows": []})
        challenger = filer("FEC_H6MI13999", "John James", state="MI", label="House • MI-13",
                           politicalHistory={"wikidata": "Q1", "rows": []})
        return incumbent, challenger

    def test_a_namesake_whose_article_is_the_members_takes_on_none_of_their_roles(self):
        incumbent, challenger = self.people()
        card = {"id": "gov-MI-john-james", "name": "John James", "member": "J000307"}
        links = identity.build([incumbent, challenger], stategov=stategov("MI", candidates=[card]))
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        self.assertEqual(roles(incumbent), [("candidate", "gov-MI-john-james")])
        self.assertEqual(roles(card), [("profile", "J000307")])
        shared = [p for p in identity.problems(links) if p[1] == "identity-item-shared"]
        self.assertEqual(len(shared), 1)
        for word in ("J000307", "FEC_H6MI13999", "Q1"):
            self.assertIn(word, shared[0][2])
        self.assertEqual(shared[0][3], ["profile:J000307", "profile:FEC_H6MI13999"])

    def test_the_item_joins_neither_profile_to_a_third_card(self):
        # A card that holds only the item: whose it is, no record says.
        incumbent, challenger = self.people()
        card = {"id": "gov-MI-john-james", "name": "John James",
                "politicalHistory": {"wikidata": "Q1", "rows": []}}
        links = identity.build([incumbent, challenger], stategov=stategov("MI", candidates=[card]))
        identity.attach(links)
        self.assertEqual((roles(incumbent), roles(challenger), roles(card)), ([], [], []))
        # With the challenger gone, the item is the member's again.
        links = identity.build([incumbent], stategov=stategov("MI", candidates=[card]))
        identity.attach(links)
        self.assertEqual(roles(card), [("profile", "J000307")])

    def test_two_filings_that_share_an_id_are_joined_by_their_item(self):
        a = filer("FEC_H6NJ07001", "Rand Example", state="NJ", label="House • NJ-7",
                  politicalHistory={"wikidata": "Q2", "rows": []})
        b = filer("FEC_H6VA07001", "Rand Example", state="VA", label="House • VA-7",
                  otherFecIds=["H6NJ07001"], politicalHistory={"wikidata": "Q2", "rows": []})
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual(roles(a), [("profile", "FEC_H6VA07001")])
        self.assertNotIn("identity-item-shared", codes(links))

    def two_filings(self):
        a = filer("FEC_H6NJ07001", "Rand Example", state="NJ", label="House • NJ-7",
                  politicalHistory={"wikidata": "Q2", "rows": []})
        b = filer("FEC_H6VA07001", "Rand Example", state="VA", label="House • VA-7",
                  politicalHistory={"wikidata": "Q2", "rows": []})
        return a, b

    def test_only_an_evidenced_entry_settles_them_and_then_they_name_each_other(self):
        a, b = self.two_filings()
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual((roles(a), roles(b)), ([], []))
        self.assertIn("identity-item-shared", codes(links))
        pair = ("profile:FEC_H6NJ07001", "profile:FEC_H6VA07001")
        self.settle(pair, same=True)
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual(roles(a), [("profile", "FEC_H6VA07001")])
        self.assertEqual(roles(b), [("profile", "FEC_H6NJ07001")])
        self.assertEqual(b["also"][0]["words"], "Candidate for the U.S. House in NJ-7")
        self.assertEqual([c for c in codes(links) if "identity" in c], ["identity-joined"])
        self.assertEqual(identity.joined(links)[0][2], ["an evidenced overrides.IDENTITY_JOINS entry"])
        # The item is then both filings', and ties them to a third card that
        # holds it; unsettled, it ties that card to neither.
        fed, holder = official("x-rand-example", "Rand Example", "Administrator", item="Q2")
        links = identity.build([a, b], federal=fed)
        identity.attach(links)
        self.assertEqual(roles(holder), [("profile", "FEC_H6NJ07001"), ("profile", "FEC_H6VA07001")])
        self.overrides.IDENTITY_JOINS.clear()
        links = identity.build([a, b], federal=fed)
        identity.attach(links)
        self.assertEqual(roles(holder), [])
        # Two people, by a person's word: silent, joined by nothing, not stale.
        self.settle(pair, same=False)
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual((roles(a), roles(b)), ([], []))
        self.assertEqual([c for c in codes(links) if "identity" in c], [])
        # Two forms of a name are still a pair to settle while the item is
        # on both; once it is on one only, the entry settles nothing.
        b["name"] = "Randall Example"
        self.assertFalse(identity.look_alike(a["name"], b["name"]))
        self.assertEqual([c for c in codes(identity.build([a, b])) if "identity" in c], [])
        b["politicalHistory"] = {"rows": []}
        self.assertIn("stale-identity-join", codes(identity.build([a, b])))

    def test_a_card_of_another_state_is_refused_whatever_the_id(self):
        texan = filer("FEC_H6TX00002", "Pat Example", state="TX", label="House • TX-3",
                      politicalHistory={"wikidata": "Q5", "rows": []})
        card = {"id": "gov-OK-pat-example", "name": "Pat Example",
                "politicalHistory": {"wikidata": "Q5", "rows": []}}
        links = identity.build([texan], stategov=stategov("OK", candidates=[card]))
        identity.attach(links)
        self.assertEqual((roles(texan), roles(card)), ([], []))
        found = [p for p in identity.problems(links) if p[1] == "identity-states-disagree"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][3], ["profile:FEC_H6TX00002", "candidate:gov-OK-pat-example"])
        # A bioguide id, and a departed member's row: the same.
        senator = member("E000002", "Pat Example", state="TX")
        card = {"id": "gov-OK-pat-example", "name": "Pat Example", "member": "E000002"}
        links = identity.build([senator], stategov=stategov("OK", candidates=[card]))
        identity.attach(links)
        self.assertEqual(roles(senator), [])
        self.assertIn("identity-states-disagree", codes(links))
        row = {"id": "E000003", "name": "Pat Example", "chamber": "House", "state": "OH",
               "district": 2, "left": "2025-01-03"}
        governor = {"id": "gov-IN", "name": "Pat Example", "wikidata": "Q6"}
        links = identity.build([], departed=[row],
                               departed_cache={"members": [{"bioguide": "E000003", "wikidata": "Q6"}]},
                               stategov=stategov("IN", governor=governor))
        identity.attach(links)
        self.assertEqual(roles(row), [])
        self.assertIn("identity-states-disagree", codes(links))
        # The same state joins; so do a profile and a departed row of two
        # states (a member who moved), neither being a state's card.
        governor = {"id": "gov-OH", "name": "Pat Example", "wikidata": "Q6"}
        links = identity.build([], departed=[row],
                               departed_cache={"members": [{"bioguide": "E000003", "wikidata": "Q6"}]},
                               stategov=stategov("OH", governor=governor))
        identity.attach(links)
        self.assertEqual(roles(row), [("governor", "gov-OH")])
        mover = filer("FEC_S6TX00009", "Pat Example", state="TX",
                      politicalHistory={"wikidata": "Q6", "rows": []})
        links = identity.build([mover], departed=[row],
                               departed_cache={"members": [{"bioguide": "E000003", "wikidata": "Q6"}]})
        identity.attach(links)
        self.assertEqual(roles(mover), [("departed", "E000003")])
        self.assertNotIn("identity-states-disagree", codes(links))


class TestEveryPairOfHolders(unittest.TestCase):
    def test_a_first_holder_who_disagrees_does_not_block_the_others(self):
        # One item on three records: a challenger named Jane James, whose
        # ballot page links her husband's article, comes first.
        jane = filer("FEC_H6MI13001", "Jane James", state="MI", label="House • MI-13",
                     politicalHistory={"wikidata": "Q1", "rows": []})
        fed, john = official("x-john-james", "John James", "Secretary of Commerce", item="Q1")
        card = {"id": "gov-MI-john-james", "name": "John James",
                "politicalHistory": {"wikidata": "Q1", "rows": []}}
        links = identity.build([jane], federal=fed, stategov=stategov("MI", candidates=[card]))
        identity.attach(links)
        self.assertEqual(roles(john), [("candidate", "gov-MI-john-james")])
        self.assertEqual(roles(card), [("official", "x-john-james")])
        self.assertEqual(roles(jane), [])
        disagree = [p[3] for p in identity.problems(links) if p[1] == "identity-names-disagree"]
        self.assertEqual(disagree, [["profile:FEC_H6MI13001", "official:x-john-james"],
                                    ["profile:FEC_H6MI13001", "candidate:gov-MI-john-james"]])


class TestMoreGuards(SettledEntries):
    def officer(self, name="Ken Example", title="Attorney General"):
        return {"name": name, "title": title, "party": "R", "partyKey": "R"}

    def test_a_label_with_no_where_is_the_whole_office_never_words_around_it(self):
        row = {"current": True}
        for office, held in (("Minnesota Attorney General", True),
                             ("Attorney General of Minnesota", True),
                             ("Former Minnesota Attorney General", False),
                             ("Minnesota Attorney General's chief of staff", False),
                             ("Solicitor to the Attorney General of Minnesota", False)):
            self.assertEqual(identity.office_in_state(dict(row, office=office), "ag", "MN"), held,
                             office)
        person = filer("CAND_7", "Ken Example", state="MN", politicalHistory={"rows": [
            dict(row, office="Former Minnesota Attorney General")]})
        off = self.officer()
        links = identity.build([person], stategov=stategov("MN", ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [])

    def test_a_governor_on_another_states_list_is_not_their_own_card(self):
        # Only a person's entry can tie two states' cards; tied, they name
        # each other: "the holder on their own list" is of one state.
        governor = {"id": "gov-MN", "name": "Pat Example"}
        card = {"id": "gov-WI-pat-example", "name": "Pat Example"}
        payload = {"states": {"MN": stategov("MN", governor=governor)["states"]["MN"],
                              "WI": stategov("WI", candidates=[card])["states"]["WI"]}}
        self.settle(("governor:gov-MN", "candidate:gov-WI-pat-example"), same=True)
        links = identity.build([], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(governor), [("candidate", "gov-WI-pat-example")])
        self.assertEqual(roles(card), [("governor", "gov-MN")])

    def test_a_role_ends_only_where_the_office_is_on_the_ballot(self):
        role = {"words": "Attorney General of Texas"}
        item = {"up": True, "termBegins": term("2027-01-01"), "outgoing": outgoing("Ken Example")}
        self.assertEqual(identity.term_end(dict(role), item, role["words"])["ends"], "2027-01-01")
        for without in ("up", "termBegins", "outgoing"):
            less = {k: v for k, v in item.items() if k != without}
            self.assertNotIn("ends", identity.term_end(dict(role), less, role["words"]), without)
        self.assertNotIn("ends", identity.term_end(dict(role), dict(item, up=False), role["words"]))

    def test_an_entrys_day_is_a_day(self):
        off = {"name": "Jo Example", "title": "Secretary of State", "party": "D", "partyKey": "D"}
        card = {"id": "gov-MI-jo-example", "name": "Jo Example"}
        payload = stategov("MI", candidates=[card], sos=off)
        for read in ("Nov. 15, 2026", "2026-11", "15/11/2026", ""):
            self.overrides.IDENTITY_JOINS.clear()
            self.settle(("officer:MI:sos", "candidate:gov-MI-jo-example"), same=True, read=read)
            links = identity.build([], stategov=payload)
            identity.attach(links)
            self.assertEqual(roles(off), [], read)
            self.assertIn("identity-join-unevidenced", codes(links), read)
            self.assertEqual([p[0] for p in identity.problems(links)
                              if p[1] == "identity-join-unevidenced"], ["error"])

    def test_a_write_in_candidates_role_says_so(self):
        # The cards' badge's words (KYC.stategov.candidateBadge) and the
        # office; the render suite holds the page to the same strings.
        listed = identity.candidate_role("MN", {"id": "gov-MN-a", "name": "A B"})
        self.assertEqual((listed["words"], listed["after"]),
                         ("On the Nov 3, 2026 ballot for Governor of Minnesota",
                          "Was on the Nov 3, 2026 ballot for Governor of Minnesota"))
        write_in = identity.candidate_role("MN", {"id": "gov-MN-b", "name": "C D", "writeIn": True})
        self.assertEqual((write_in["words"], write_in["after"]),
                         ("Write-in candidate for Governor of Minnesota",
                          "Was a write-in candidate for Governor of Minnesota"))
        # On a joined record, with its tense on the share page.
        challenger = filer("FEC_S6MN00007", "Cy Example", state="MN",
                           politicalHistory={"wikidata": "Q8", "rows": []})
        card = {"id": "gov-MN-cy-example", "name": "Cy Example", "writeIn": True,
                "politicalHistory": {"wikidata": "Q8", "rows": []}}
        links = identity.build([challenger], stategov=stategov("MN", candidates=[card]))
        identity.attach(links)
        self.assertEqual(challenger["also"][0]["words"], "Write-in candidate for Governor of Minnesota")
        self.assertIn(">Was a write-in candidate for Governor of Minnesota<",
                      identity.share_html(challenger, post="2026-11-13"))

    def joined_legislator(self):
        challenger = filer("FEC_H6NH00001", "Gina Example", state="NH", label="House • NH-1",
                           wikipedia="Gina Example")
        history = {"people": {"FEC_H6NH00001": {"wikipedia": "Gina Example", "offices": [
            {"office": "Member of the New Hampshire House of Representatives",
             "where": "New Hampshire", "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/3", "name": "Gina Example", "chamber": "lower",
                "district": "Strafford 4", "state": "NH"}
        return challenger, history, {"states": {"NH": [seat]}}

    def test_a_member_the_map_cannot_place_carries_the_line_too(self):
        challenger, history, legislators = self.joined_legislator()
        unplaced = {"id": "ocd-person/3", "name": "Gina Example", "chamber": "lower"}
        other = {"id": "ocd-person/4", "name": "Someone Else", "chamber": "lower", "also": ["stale"]}
        legislatures = {"NH": {"chambers": {"lower": {"title": "House of Representatives",
                                                      "members": {}}},
                               "unplaced": [unplaced, other]}}
        links = identity.build([challenger], history=history, legislators=legislators,
                               legislatures=legislatures)
        identity.attach(links)
        identity.attach_legislatures(links, legislatures)
        self.assertEqual(roles(unplaced), [("profile", "FEC_H6NH00001")])
        self.assertNotIn("also", other)

    def test_a_judge_listed_as_retired_in_another_courts_file_carries_the_line(self):
        judge = {"id": "fjc-9", "name": "Pat Example", "seats": [{"court": "ca5", "title": "Judge"}]}
        retired = dict(judge)
        courts = {"ca5": {"name": "U.S. Court of Appeals for the Fifth Circuit", "judges": [judge]},
                  "txnd": {"name": "U.S. District Court for the Northern District of Texas",
                           "judges": [], "retired": [retired, {"id": "fjc-10", "also": ["stale"]}]}}
        card = {"id": "gov-TX-pat-example", "name": "Pat Example",
                "politicalHistory": {"wikidata": "Q9", "rows": []}}
        links = identity.build([], courts=courts, judge_links={"judges": {"9": {"wikidata": "Q9"}}},
                               stategov=stategov("TX", candidates=[card]))
        identity.attach(links)
        identity.attach_courts(links, courts)
        self.assertEqual(roles(retired), [("candidate", "gov-TX-pat-example")])
        self.assertNotIn("also", courts["txnd"]["retired"][1])

    def test_a_departed_members_link_is_labelled_as_the_congress_biography(self):
        row = {"id": "V000002", "name": "J.D. Example", "chamber": "Senate", "state": "OH",
               "left": "2025-01-09"}
        role = identity.departed_role(row)
        self.assertEqual(role["link"], "Congress biography")
        self.assertEqual(role["href"], "https://bioguide.congress.gov/search/bio/V000002")
        text = identity.share_html({"also": [role]})
        self.assertIn("Jan. 9, 2025 (Congress biography)</a>", text)
        self.assertIn('href="https://bioguide.congress.gov/search/bio/V000002"', text)

    def test_only_candidates_are_asked_of_the_legislature_never_a_governor_or_an_official(self):
        office = {"office": "Member of the Texas Senate", "where": "Texas", "open": True,
                  "agree": "exact"}
        history = {"people": {
            "gov-TX": {"wikipedia": "Pat Example", "wikidata": "Q3", "offices": [office]},
            "x-pat-example": {"wikipedia": "Pat Example", "wikidata": "Q3", "offices": [office]}}}
        seat = {"id": "ocd-person/5", "name": "Pat Example", "chamber": "upper", "district": "14",
                "state": "TX"}
        governor = {"id": "gov-TX", "name": "Pat Example", "wikidata": "Q3",
                    "wikipedia": "Pat Example", "isCandidate": True}
        fed, holder = official("x-pat-example", "Pat Example", "Secretary of Energy", item="Q3",
                               state="TX", wikipedia="Pat Example", isCandidate=True)
        links = identity.build([], history=history, legislators={"states": {"TX": [seat]}},
                               stategov=stategov("TX", governor=governor), federal=fed)
        identity.attach(links)
        self.assertNotIn(("legislator", "ocd-person/5"), roles(governor) + roles(holder))
        self.assertFalse([c for c in codes(links) if c.startswith("identity-legislator")])
        self.assertFalse([k for k in links.nodes if k.startswith("legislator:")])

    def test_two_cards_of_one_kind_and_one_name_are_not_this_reports(self):
        # Two filers of one name in one state are rule 25's own report
        # (validate.check_duplicate_people), not a pair of roles.
        a = filer("FEC_H6FL19001", "Michael Example", state="FL", label="House • FL-19")
        b = filer("FEC_H6FL22001", "Michael Example", state="FL", label="House • FL-22")
        self.assertNotIn("identity-look-alike", codes(identity.build([a, b])))
        card = {"id": "gov-FL-michael-example", "name": "Michael Example"}
        links = identity.build([a, b], stategov=stategov("FL", candidates=[card]))
        self.assertEqual([p[3] for p in identity.problems(links) if p[1] == "identity-look-alike"],
                         [["profile:FEC_H6FL19001", "candidate:gov-FL-michael-example"],
                          ["profile:FEC_H6FL22001", "candidate:gov-FL-michael-example"]])

    def test_a_governor_who_holds_an_officers_office_is_joined_to_its_card(self):
        # A lieutenant governor who became governor, while the association's
        # roster still names them.
        governor = {"id": "gov-XX", "name": "Pat Example", "politicalHistory": {"rows": [
            {"office": "Lieutenant Governor of Iowa", "where": "Iowa", "current": True}]}}
        off = self.officer("Pat Example", "Lieutenant Governor")
        links = identity.build([], stategov=stategov("IA", governor=governor, lt=off))
        identity.attach(links)
        self.assertEqual(roles(off), [("governor", "gov-XX")])
        self.assertEqual(governor["also"][0]["words"], "Lieutenant Governor of Iowa")

    def test_a_lists_candidates_are_cards_only_where_the_office_is_on_the_ballot(self):
        senator = member("K000009", "Ann Example")
        card = {"id": "gov-MN-ann-example", "name": "Ann Example", "member": "K000009"}
        payload = stategov("MN", candidates=[card])
        payload["states"]["MN"]["ballot2026"]["offices"]["governor"]["up"] = False
        links = identity.build([senator], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(senator), [])
        self.assertNotIn("candidate:gov-MN-ann-example", links.nodes)
        payload["states"]["MN"]["ballot2026"]["offices"]["governor"]["up"] = True
        links = identity.build([senator], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(senator), [("candidate", "gov-MN-ann-example")])


class TestSeatAndChamberWords(unittest.TestCase):
    def test_a_chamber_by_its_own_name_where_its_own_site_gives_one(self):
        from kyc import legislature
        self.assertEqual(identity.legislator_role("NY", {"district": "73"}, "Assembly",
                                                  "New York State Assembly")["words"],
                         "Member of the New York State Assembly, district 73")
        self.assertEqual(identity.legislator_role("NV", {"district": "3"}, "Assembly")["words"],
                         "Member of the Nevada Assembly, district 3")
        # The legislature page's payload carries the name, and the join reads it.
        challenger = filer("FEC_H6NY12001", "Alex Example", state="NY", label="House • NY-12",
                           wikipedia="Alex Example")
        history = {"people": {"FEC_H6NY12001": {"wikipedia": "Alex Example", "offices": [
            {"office": "Member of the New York State Assembly", "where": "New York",
             "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/6", "name": "Alex Example", "chamber": "lower", "district": "73",
                "districtId": "073", "state": "NY"}
        # The payload's head, as legislature.build_state writes it.
        chamber = dict(legislature.chamber_head("NY", "lower"), members={})
        self.assertEqual(chamber["name"], "New York State Assembly")
        self.assertNotIn("name", legislature.chamber_head("NV", "lower"))
        self.assertEqual(legislature.chamber_head("NV", "lower"), {"title": "Assembly"})
        links = identity.build([challenger], history=history,
                               legislators={"states": {"NY": [seat]}},
                               legislatures={"NY": {"chambers": {"lower": chamber}}})
        identity.attach(links)
        self.assertEqual(challenger["also"][0]["words"],
                         "Member of the New York State Assembly, district 73")
        self.assertEqual(legislature.chamber_name("TX", "lower"), None)

    def test_every_recorded_chamber_name_is_its_own_sites_words(self):
        from kyc import legislature
        self.assertEqual(legislature.chamber_name_problems(), [])
        saved = dict(legislature.CHAMBER_NAMES)
        try:
            legislature.CHAMBER_NAMES[("TX", "upper")] = (
                "Texas State Senate", "https://senate.texas.gov/", "The Texas Senate", "2026-11-15")
            legislature.CHAMBER_NAMES[("NV", "lower")] = (
                "Nevada Assembly", "https://asm.leg.state.nv.us/", "Nevada Assembly", "2026-11-15")
            legislature.CHAMBER_NAMES[("OH", "upper")] = ("Ohio State Senate", "", "", "")
            found = legislature.chamber_name_problems()
            self.assertEqual(len(found), 3, found)
        finally:
            legislature.CHAMBER_NAMES.clear()
            legislature.CHAMBER_NAMES.update(saved)

    def test_a_legislators_share_link_opens_their_district(self):
        role = identity.legislator_role("VA", {"district": "2", "districtId": "002",
                                               "chamber": "lower", "id": "ocd-person/7"},
                                        "House of Delegates")
        self.assertEqual(role["href"], "legislature/va.html#/?chamber=lower&d=002")
        self.assertEqual(role["share"], role["href"])
        self.assertIn('href="../legislature/va.html#/?chamber=lower&amp;d=002"',
                      identity.share_html({"also": [role]}))

    def test_an_at_large_seat_in_the_sites_seat_words(self):
        for label, words, after in (
                ("House • WY-AL", "Candidate for the U.S. House in WY-AL",
                 "2026 race for the U.S. House in WY-AL"),
                ("House • TX-37", "Candidate for the U.S. House in TX-37",
                 "2026 race for the U.S. House in TX-37"),
                ("House • VI-AL", "Candidate for the U.S. Virgin Islands’ seat in the U.S. House",
                 "2026 race for the U.S. Virgin Islands’ seat in the U.S. House"),
                ("House • DC-AL", "Candidate for the District of Columbia’s seat in the U.S. House",
                 "2026 race for the District of Columbia’s seat in the U.S. House"),
                ("Senate • WY", "Candidate for the U.S. Senate in Wyoming",
                 "2026 race for the U.S. Senate in Wyoming")):
            state = label.partition(" • ")[2][:2]
            person = filer("FEC_H6XX00001", "Chuck Example", state=state, label=label,
                           chamber=label.partition(" • ")[0])
            role = identity.profile_role(person, {}, {}, "2026-11-13")
            self.assertEqual((role["words"], role["after"]), (words, after), label)
            self.assertNotIn("at large", role["words"] + role["after"])


class TestAnOfficerCardBehindASeatInCongress(SettledEntries):
    """From January 3 a member of Congress sitting now is never shown as a
    state officer on the officer roster's word alone: the card is the
    roster's lag, said apart (``identity-officer-roster-behind``)."""

    def officer(self, name="Marty Example"):
        return {"name": name, "title": "Attorney General", "party": "R", "partyKey": "R"}

    def winner(self, **extra):
        row = member("J000001", "Marty Example", state="SD", chamber="House",
                     officeLabel="House • SD-AL", raceRole="winner", fecCandidateId="H6SD00001",
                     term_start="2027-01-03 - 2029-01-03")
        row.update(extra)
        return row

    def payload(self, off, ends=None):
        entry = stategov("SD", ag=off)
        if ends:
            entry["states"]["SD"]["ballot2026"] = {"offices": {"ag": {
                "up": True, "termBegins": term(ends), "outgoing": outgoing(off["name"])}}}
        return entry

    def behind(self, links):
        return [p for p in identity.problems(links) if p[1] == "identity-officer-roster-behind"]

    def test_an_entry_for_a_seated_member_beside_a_card_with_no_end_links_nothing(self):
        self.settle(("officer:SD:ag", "profile:FEC_H6SD00001"), same=True)
        off, winner = self.officer(), self.winner()
        links = identity.build([winner], stategov=self.payload(off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertEqual(roles(winner), [])
        found = self.behind(links)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], "warn")
        self.assertEqual(found[0][3], [
            "profile Marty Example (J000001) and Marty Example (Attorney General of South Dakota): "
            "seated in Congress since 2027-01-03, but the officer card still names them, its term "
            "carrying no end this site reads (joined by an evidenced overrides.IDENTITY_JOINS "
            "entry)"])
        # Not a stale entry, and not a look-alike: one person, a roster behind.
        self.assertFalse({"stale-identity-join", "identity-look-alike"} & set(codes(links)))
        # While they ran, the same entry joins them.
        running = filer("FEC_H6SD00001", "Marty Example", state="SD", label="House • SD-AL")
        links = identity.build([running], stategov=self.payload(self.officer()))
        identity.attach(links)
        self.assertEqual(roles(running), [("officer", "SD-ag")])
        self.assertEqual(self.behind(links), [])

    def test_a_term_that_ends_after_the_seat_began_is_behind_one_that_ended_before_is_not(self):
        self.settle(("officer:SD:ag", "profile:FEC_H6SD00001"), same=True)
        for ends, joined in (("2027-01-04", False), ("2027-01-11", False),
                             ("2027-01-03", True), ("2027-01-01", True)):
            off, winner = self.officer(), self.winner()
            links = identity.build([winner], stategov=self.payload(off, ends=ends))
            identity.attach(links)
            self.assertEqual(roles(winner), [("officer", "SD-ag")] if joined else [], ends)
            self.assertEqual(bool(self.behind(links)), not joined, ends)
            if joined:
                self.assertEqual(winner["also"][0]["ends"], ends)
            else:
                self.assertIn(f"its term ending on {ends}", self.behind(links)[0][3][0])
        # A member whose profile gives no term's day is behind whatever the end.
        off, winner = self.officer(), self.winner(term_start="N/A")
        links = identity.build([winner], stategov=self.payload(off, ends="2027-01-01"))
        identity.attach(links)
        self.assertEqual(roles(winner), [])
        self.assertTrue(self.behind(links))

    def test_a_corroborated_record_beside_a_card_with_no_end_links_nothing(self):
        # The record's own row (open when read) and the card naming them: the
        # second-source join, which held for Weiser, holds for no seated member.
        off = self.officer()
        winner = self.winner(politicalHistory={"wikidata": "Q9", "rows": [
            {"office": "South Dakota Attorney General", "where": "South Dakota",
             "openWhenRead": "2026-11-14"}]})
        links = identity.build([winner], stategov=self.payload(off))
        identity.attach(links)
        self.assertEqual(roles(winner), [])
        self.assertEqual(roles(off), [])
        self.assertIn("South Dakota Attorney General in the record, open when it was read on "
                      "2026-11-14", self.behind(links)[0][3][0])
        self.assertNotIn("identity-look-alike", codes(links))
        # A candidate who is not seated keeps the join (Weiser's).
        running = filer("FEC_H6SD00001", "Marty Example", state="SD", label="House • SD-AL",
                        politicalHistory=winner["politicalHistory"])
        links = identity.build([running], stategov=self.payload(self.officer()))
        identity.attach(links)
        self.assertEqual(roles(running), [("officer", "SD-ag")])


class TestGuardsTheReaderUndid(SettledEntries):
    """Guards a reader's mutants survived (the review of the branch's head):
    each made state is one the guard decides."""

    def test_a_share_page_on_the_very_day_a_role_ends_says_it_ended(self):
        role = {"kind": "officer", "words": "Attorney General of Texas", "ends": "2027-01-01",
                "ended": "Was Attorney General of Texas, until the term began",
                "share": "states/tx.html", "href": "states/tx.html#state-government"}
        record = {"also": [role]}
        self.assertIn(">Was Attorney General", identity.share_html(record, post="2027-01-01"))
        self.assertIn(">Attorney General of Texas<", identity.share_html(record, post="2026-12-31"))
        # And on the roster's own read of that very day.
        self.assertIn(">Was Attorney General",
                      identity.share_html({"also": [dict(role, endsRead="2027-01-01")]},
                                          post="2026-11-13"))

    def test_an_entry_keyed_on_an_fec_id_two_profiles_hold_settles_nothing(self):
        off = {"name": "Marty Example", "title": "Attorney General", "party": "R", "partyKey": "R"}
        self.settle(("officer:SD:ag", "profile:FEC_H6SD00001"), same=True)
        one = filer("CAND_5", "Marty Example", state="SD", label="House • SD-AL",
                    fecCandidateId="H6SD00001")
        two = filer("CAND_6", "Marty Example", state="SD", label="Senate • SD",
                    fecCandidateId="S6SD00001", otherFecIds=["H6SD00001"])
        links = identity.build([one, two], stategov=stategov("SD", ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [])
        self.assertIn("stale-identity-join", codes(links))
        # Held by one profile alone, the entry follows it.
        links = identity.build([one], stategov=stategov("SD", ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [("profile", "CAND_5")])

    def test_a_lone_initial_is_no_given_name(self):
        self.assertFalse(identity.names_agree("J. James", "J. James"))
        self.assertFalse(identity.names_agree("J. James", "John James"))
        self.assertTrue(identity.names_agree("J.D. James", "JD James"))
        # On one item, two records naming only an initial and a surname are
        # withheld, never joined.
        challenger = filer("FEC_H6MI13002", "J. James", state="MI", label="House • MI-13",
                           politicalHistory={"wikidata": "Q11", "rows": []})
        card = {"id": "gov-MI-j-james", "name": "J. James",
                "politicalHistory": {"wikidata": "Q11", "rows": []}}
        links = identity.build([challenger], stategov=stategov("MI", candidates=[card]))
        identity.attach(links)
        self.assertEqual(roles(challenger), [])
        self.assertIn("identity-names-disagree", codes(links))

    def test_a_legislator_of_another_state_is_no_look_alike(self):
        challenger = filer("FEC_H6NH00002", "Gina Example", state="NH", label="House • NH-1")
        seat = {"id": "ocd-person/5", "name": "Gina Example", "chamber": "lower", "district": "3",
                "state": "VT"}
        links = identity.build([challenger], legislators={"states": {"VT": [seat]}})
        self.assertNotIn("identity-legislator-look-alike", codes(links))
        # In the challenger's own state, the same seat is one.
        links = identity.build([challenger], legislators={"states": {"NH": [dict(seat, state="NH")]}})
        self.assertIn("identity-legislator-look-alike", codes(links))

    def test_a_departed_row_is_not_counted_as_a_card_lacking_a_photograph(self):
        row = {"id": "V000002", "name": "Jo Example", "chamber": "Senate", "state": "OH",
               "left": "2025-01-09"}
        vp = {"id": "x-jo-example", "name": "Jo Example", "office": "Vice President of the United States",
              "links": {"bioguide": "V000002"}, "photo": "https://example.gov/jo.jpg"}
        links = identity.build([], departed=[row], federal={"vicePresident": vp})
        identity.attach(links)
        self.assertEqual(roles(vp), [("departed", "V000002")])
        self.assertEqual(identity.photo_differences(links), [])
        # A card that has no photograph is.
        senator = member("K000009", "Ann Example", photos=["placeholder"])
        card = {"id": "gov-MN-ann-example", "name": "Ann Example", "member": "K000009",
                "photo": "https://example.gov/ann.jpg"}
        links = identity.build([senator], stategov=stategov("MN", candidates=[card]))
        self.assertEqual(identity.photo_differences(links),
                         ["Ann Example: candidate pictured, profile not"])

    def test_a_disputed_officer_card_names_nobody(self):
        person = filer("CAND_8", "Ken Example", state="TX", politicalHistory={"rows": [
            {"office": "Texas Attorney General", "where": "Texas", "current": True}]})
        off = {"name": "Ken Example", "title": "Attorney General", "party": "R", "partyKey": "R"}
        links = identity.build([person], stategov=stategov("TX", ag=dict(off)))
        identity.attach(links)
        self.assertEqual(roles(person), [("officer", "TX-ag")])
        for flag in ("disputed", "unconfirmed", "unlisted", "vacant", "none", "notMember"):
            links = identity.build([person], stategov=stategov("TX", ag=dict(off, **{flag: True})))
            identity.attach(links)
            self.assertEqual(roles(person), [], flag)



class TestTheWholePersonBesideASeatInCongress(SettledEntries):
    """After every join, one pass over each person holding a seat in Congress
    now: no governor's, officer's or legislator's card of theirs is linked
    unless its role ends by the day their term began (the final review of
    PR #267's three paths past the joins' own checks)."""

    def winner(self, **extra):
        row = member("J000001", "Marty Example", state="SD", chamber="House",
                     officeLabel="House • SD-AL", raceRole="winner", fecCandidateId="H6SD00001",
                     term_start="2027-01-03 - 2029-01-03")
        row.update(extra)
        return row

    def found(self, links, code):
        return [p for p in identity.problems(links) if p[1] == code]

    def test_an_entry_joining_a_seated_winner_to_a_legislators_card_links_nothing(self):
        self.settle(("legislator:SD:ocd-person/8", "profile:J000001"), same=True)
        seat = {"id": "ocd-person/8", "name": "Marty Example", "chamber": "upper", "district": "8",
                "districtId": "008", "state": "SD"}
        winner = self.winner()
        links = identity.build([winner], legislators={"states": {"SD": [seat]}})
        identity.attach(links)
        self.assertEqual(roles(winner), [])
        line = self.found(links, "identity-legislator-roster-behind")
        self.assertEqual(line[0][3], [
            "profile Marty Example (J000001) and Marty Example (SD upper 8, ocd-person/8): seated "
            "in Congress since 2027-01-03, but joined to the legislator card, whose seat carries "
            "no end this site reads (joined by an evidenced overrides.IDENTITY_JOINS entry)"])
        self.assertFalse({"stale-identity-join", "identity-legislator-look-alike"} & set(codes(links)))
        # While they ran, the same entry links the two.
        running = filer("FEC_H6SD00001", "Marty Example", state="SD", label="House • SD-AL")
        self.settle(("legislator:SD:ocd-person/8", "profile:FEC_H6SD00001"), same=True)
        links = identity.build([running], legislators={"states": {"SD": [seat]}})
        identity.attach(links)
        self.assertEqual(roles(running), [("legislator", "ocd-person/8")])

    def test_a_governors_card_joined_by_an_item_to_a_seated_member_links_nothing(self):
        winner = self.winner(politicalHistory={"wikidata": "Q77", "rows": []})
        gov = {"id": "gov-SD", "name": "Marty Example", "wikidata": "Q77"}
        links = identity.build([winner], stategov=stategov("SD", governor=gov))
        identity.attach(links)
        self.assertEqual(roles(winner), [])
        self.assertEqual(roles(gov), [])
        line = self.found(links, "identity-officer-roster-behind")
        self.assertEqual(line[0][3], [
            "profile Marty Example (J000001) and Marty Example (Governor of South Dakota): seated "
            "in Congress since 2027-01-03, but the governor card still names them, its term "
            "carrying no end this site reads (joined by wikidata Q77)"])
        self.assertIn("state officer or governor card still names", line[0][2])
        # The pair is said once, never also a look-alike.
        self.assertNotIn("identity-look-alike", codes(links))
        # A governor's term that ended by the day the seat began is a past role.
        payload = stategov("SD", governor=dict(gov))
        payload["states"]["SD"]["ballot2026"] = {"offices": {"governor": {
            "up": True, "termBegins": term("2027-01-03"), "outgoing": outgoing("Marty Example")}}}
        winner = self.winner(politicalHistory={"wikidata": "Q77", "rows": []})
        links = identity.build([winner], stategov=payload)
        identity.attach(links)
        self.assertEqual(roles(winner), [("governor", "gov-SD")])
        self.assertFalse(self.found(links, "identity-officer-roster-behind"))

    def test_an_officer_joined_through_a_card_an_entry_joins_to_a_seated_member(self):
        off = {"name": "Marty Example", "title": "Attorney General", "party": "R", "partyKey": "R"}
        card = {"id": "gov-SD-marty-example", "name": "Marty Example",
                "politicalHistory": {"wikidata": "Q5", "rows": [
                    {"office": "South Dakota Attorney General", "where": "South Dakota",
                     "current": True}]}}
        self.settle(("candidate:gov-SD-marty-example", "profile:J000001"), same=True)
        winner = self.winner()
        links = identity.build([winner], stategov=stategov("SD", candidates=[card], ag=off))
        identity.attach(links)
        # The officer's card names nobody; the list's card and the profile
        # still name each other.
        self.assertEqual(roles(off), [])
        self.assertEqual(roles(winner), [("candidate", "gov-SD-marty-example")])
        self.assertEqual(roles(card), [("profile", "J000001")])
        line = self.found(links, "identity-officer-roster-behind")
        self.assertEqual(len(line[0][3]), 1)
        self.assertIn("(Attorney General of South Dakota): seated in Congress since 2027-01-03",
                      line[0][3][0])
        self.assertIn("South Dakota Attorney General in the record", line[0][3][0])
        # A member who does not sit now (a former member) is no such seat.
        former = self.winner(formerMember=True)
        links = identity.build([former], stategov=stategov("SD", candidates=[card], ag=off))
        identity.attach(links)
        self.assertEqual(roles(off), [("profile", "J000001"),
                                      ("candidate", "gov-SD-marty-example")])


class TestALegislatorsTermEnding(unittest.TestCase):
    """A legislator's role has no end this site reads: a joined legislator
    whose district is on the 2026 ballot while they ran for another office
    is said (``identity-legislator-term-ending``)."""

    def build(self, up):
        challenger = filer("FEC_H6TX00001", "Gina Example", state="TX", label="House • TX-37",
                           wikipedia="Gina Example")
        history = {"people": {challenger["id"]: {"wikipedia": "Gina Example", "offices": [
            {"office": "Member of the Texas House of Representatives", "where": "Texas",
             "open": True, "agree": "exact"}]}}}
        seat = {"id": "ocd-person/1", "name": "Gina Example", "chamber": "lower", "district": "49",
                "districtId": "049", "state": "TX"}
        legislatures = {"TX": {"chambers": {"lower": {"title": "House of Representatives",
                                                      "districts": {"049": {"up": up}}}}}}
        links = identity.build([challenger], history=history,
                               legislators={"states": {"TX": [seat]}}, legislatures=legislatures)
        identity.attach(links)
        return links, challenger

    def test_a_seat_on_the_ballot_beside_a_run_for_another_office_is_said(self):
        links, challenger = self.build(True)
        found = [p for p in identity.problems(links) if p[1] == "identity-legislator-term-ending"]
        self.assertEqual(found[0][0], "warn")
        self.assertIn("1 joined state legislator card is in a district the legislature page marks "
                      "on the 2026 ballot", found[0][2])
        self.assertEqual(found[0][3], [
            "Gina Example (Member of the Texas House of Representatives, district 49; TX lower 49, "
            "ocd-person/1) and profile Gina Example (Candidate for the U.S. House in TX-37)"])
        # The line still names the seat: the limit is said, not hidden.
        self.assertEqual(roles(challenger), [("legislator", "ocd-person/1")])

    def test_a_seat_not_on_the_ballot_or_not_known_is_not(self):
        for up in (False, None):
            links, _challenger = self.build(up)
            self.assertNotIn("identity-legislator-term-ending", codes(links), up)


class TestMoreGuardsTheReaderUndid(unittest.TestCase):
    """The final review's surviving mutants, each a made state."""

    def test_two_given_names_that_share_only_a_second_word_are_two_people(self):
        self.assertFalse(identity.names_agree("Mary Ann Example", "Jo Ann Example"))
        self.assertTrue(identity.names_agree("Mary Ann Example", "Mary Example"))
        one = filer("FEC_H6OH00001", "Mary Ann Example", state="OH", label="House • OH-1",
                    politicalHistory={"wikidata": "Q21", "rows": []})
        card = {"id": "gov-OH-jo-ann-example", "name": "Jo Ann Example",
                "politicalHistory": {"wikidata": "Q21", "rows": []}}
        links = identity.build([one], stategov=stategov("OH", candidates=[card]))
        identity.attach(links)
        self.assertEqual(roles(one), [])
        self.assertIn("identity-names-disagree", codes(links))

    def test_share_html_escapes_a_roles_words_and_address(self):
        record = {"also": [{"kind": "officer", "words": "Secretary of A&B <i>",
                            "share": "states/x.html?a=1&b=<2>"}]}
        out = identity.share_html(record)
        self.assertIn(">Secretary of A&amp;B &lt;i&gt;</a>", out)
        self.assertIn('href="../states/x.html?a=1&amp;b=&lt;2&gt;"', out)
        self.assertNotIn("<i>", out)

    def test_a_judge_on_two_courts_is_shown_on_the_later_one(self):
        judge = {"id": "fjc-5", "name": "Pat Example", "status": "active", "seats": [
            {"court": "txnd", "title": "District Judge", "commissioned": "2001-01-01"},
            {"court": "ca5", "title": "Circuit Judge", "commissioned": "2010-01-01"}]}
        entries = [("ca5", "U.S. Court of Appeals for the Fifth Circuit"),
                   ("txnd", "U.S. District Court for the Northern District of Texas")]
        self.assertEqual(identity.judge_court(judge, entries)[0], "ca5")
        self.assertEqual(identity.judge_court(judge, list(reversed(entries)))[0], "ca5")
        courts = {"txnd": {"name": entries[1][1], "judges": [judge]},
                  "ca5": {"name": entries[0][1], "judges": [judge]}}
        card = {"id": "gov-TX-pat-example", "name": "Pat Example",
                "politicalHistory": {"wikidata": "Q9", "rows": []}}
        links = identity.build([], courts=courts, judge_links={"judges": {"5": {"wikidata": "Q9"}}},
                               stategov=stategov("TX", candidates=[card]))
        identity.attach(links)
        self.assertEqual(card["also"][0]["court"], "ca5")
        self.assertTrue(card["also"][0]["words"].startswith("Circuit Judge of the U.S. Court of "
                                                            "Appeals for the Fifth Circuit"))

    def test_a_former_members_profile_role_is_in_the_past_tense(self):
        former = member("T000009", "Tom Example", state="AL", officeLabel="Senate • AL",
                        formerMember=True)
        role = identity.profile_role(former, {}, {}, "2026-11-13")
        self.assertTrue(role["words"].startswith(
            "Former member of Congress, who held a U.S. Senate seat from Alabama"), role["words"])
        sitting = member("T000009", "Tom Example", state="AL", officeLabel="Senate • AL")
        self.assertTrue(identity.profile_role(sitting, {}, {}, "2026-11-13")["words"].startswith(
            "Member of Congress, holding a U.S. Senate seat from Alabama"))

if __name__ == "__main__":
    unittest.main()
