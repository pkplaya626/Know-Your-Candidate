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

    def test_two_profiles_of_one_person_name_no_one(self):
        # A member's profile and their candidacy's, folded by the profiles
        # themselves (rule 30): one card, no line between them.
        a = member("B000001", "Andy Example", state="KY", fecCandidateId="H0KY06104")
        b = filer("FEC_S6KY00001", "Andy Example", state="KY", otherFecIds=["H0KY06104"])
        links = identity.build([a, b])
        identity.attach(links)
        self.assertEqual(roles(a), [])
        self.assertEqual(roles(b), [])

    def test_an_fec_id_joins(self):
        # A member's profile and their candidacy's share the FEC id; the
        # candidacy's article's item is a governor list's card's. The member's
        # card names the list through the FEC id alone.
        a = member("B000002", "Andy Example", state="KY", fecCandidateId="H0KY06105")
        b = filer("FEC_S6KY00002", "Andy Example", state="KY", otherFecIds=["H0KY06105"],
                  politicalHistory={"wikidata": "Q70", "rows": []})
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


if __name__ == "__main__":
    unittest.main()
