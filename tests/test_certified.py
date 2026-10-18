"""The states' certified November ballots (kyc/certified.py, rule 77).

Audited on 2026-10-17, the site showed Alaska's at-large seat with two
people on the ballot over a certified four - and said the two it left out
had withdrawn - left Alaska's certified Daniel J. Sullivan Jr. "Not on the
2026 primary ballot", missed thirteen qualified Florida candidates and
seventeen Colorado ones, and called American Samoa's seat uncontested over
six certified names. These tests pin the readers to each list's real markup
(trimmed, contact details removed) and the overlay to what each list says.
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import certified, overrides, races, results  # noqa: E402

# ------------------------------------------------------------------ markup


def ak_cell(name, party, write_in=False, status="Certified"):
    flag = "Certified Write-In" if write_in else ""
    return ('<tr><td style=\'--v-responsive-table-label:"Candidate Name on Ballot";\'>'
            '<div class="candidates-table-content">\n'
            f'<span style="color: #e50000; font-weight: bold;">{flag}</span><br>\n'
            f'<span></span> <a id="x"></a><strong>{name}</strong><br> \n'
            f'<small>({party}) \n({status})</small>\n</div></td>'
            '<td style=\'--v-responsive-table-label:"Campaign Address";\'>'
            '<div class="candidates-table-content">PO Box 1</div></td></tr>')


def ak_page(senate, house):
    return ('<div class="election-info"><h2>2026 General Election</h2></div>'
            '<h4><a id="us-senate"></a>UNITED STATES SENATOR</h4><table><tbody>' +
            "".join(senate) + "</tbody></table>"
            '<h4><a id="us-house"></a>UNITED STATES REPRESENTATIVE</h4><table><tbody>' +
            "".join(house) + "</tbody></table><h4>STATE SENATE</h4>")


AK = ak_page(
    [ak_cell("Heikes, Gerald L.", "Registered Republican"),
     ak_cell("Hill, Sidney &#x201C;Sid&#x201D;", "Undeclared", write_in=True),
     ak_cell("McElwain, Heather", "Registered Libertarian", write_in=True),
     ak_cell("Peltola, Mary", "Registered Democrat"),
     ak_cell("Sullivan, Dan S.", "Registered Republican"),
     ak_cell("Sullivan, Daniel J. Jr.", "Registered Republican")],
    [ak_cell("Begich, Nick", "Registered Republican"),
     ak_cell("Dutchess, Lady Donna", "Nonpartisan", write_in=True),
     ak_cell("Hafner, Eric", "Registered Democrat"),
     ak_cell("Hill, Bill", "Nonpartisan"),
     ak_cell("McDermott, James C. &#x201C;Jim&#x201D;", "Registered Libertarian")])


def fl_row(name, code, status, primary="", general="", district=None):
    first = "" if district is None else (
        f'<td align=center><b>{district if district else "&nbsp;"}</b></td>')
    return (f'<tr bgcolor="#D7DBFD">{first}<td align=left><a href="x">{name}</a>\n'
            f'({code})\n</td><td align=center>{status}  </td>'
            f'<td align=center>{primary or "&nbsp;"}</td>'
            f'<td align=center>{general or "&nbsp;"}</td></tr>')


def fl_page(drop=None):
    rows = ['<font><b>United States Senator   </b></font><table>',
            "<tr><th>Candidate</th><th>Status</th><th>Primary</th><th>General</th></tr>",
            fl_row("Moody , Ashley", "REP) *Incumbent (REP", "Qualified", "Won"),
            fl_row("Gillespie , Neil J.", "NPA", "Qualified"),
            fl_row("Vindman , Alex", "DEM", "Defeated", "Eliminated"),
            "</table>",
            '<font><b>United States Representative </b></font><table>',
            "<tr><th>District</th><th>Candidate</th><th>Status</th><th>Primary</th>"
            "<th>General</th></tr>"]
    for n in range(1, 29):
        if n == drop:
            continue
        if n == 4:
            rows += [fl_row("Bean , Aaron", "REP", "Qualified", "Unopposed", district=4),
                     fl_row("Schaefer , Todd", "NPA", "Qualified", district=0),
                     fl_row("Sell , Mike", "FFP", "Qualified", district=0),
                     fl_row("Robinson , Brit", "DEM", "Defeated", "Eliminated", district=0),
                     fl_row("Doe , Jane", "WRI", "Qualified", district=0)]
        elif n == 10:
            rows.append(fl_row("Frost , Maxwell Alejandro", "DEM", "Unopposed", "Unopposed",
                               "Unopposed", district=10))
        else:
            rows.append(fl_row(f"Person{n} , Pat", "REP", "Qualified", district=n))
    return "".join(rows) + "</table>"


def co_row(name, office, district, party, write_in="N", struck=False):
    cell = (lambda t: f'<td><span style="text-decoration: line-through;">{t}</span></td>'
            if struck else f"<td>{t}</td>")
    return "<tr>" + "".join(cell(t) for t in (name, office, district, party, write_in)) + "</tr>"


def co_page(seats=8):
    rows = [co_row("Mark Baisley", "US Senate", "State", "Republican Party"),
            co_row("Will Powers", "US Senate", "State", "Republican Party", "Y")]
    for n in range(1, seats + 1):
        rows.append(co_row(f"Rep{n} Person", "US House of Representatives", str(n),
                           "Democratic Party"))
    rows += [co_row("Shimon Blau", "US House of Representatives", "1", "Unaffiliated"),
             co_row("Gone Away", "US House of Representatives", "1", "Libertarian Party",
                    struck=True),
             co_row("Duane L Gurule", "State Senate", "35", "Democratic Party")]
    return ('<p class="pageTitle">2026 General Election Official Candidate List</p><table>'
            "<thead><tr><th>Candidate name</th><th>Office</th><th>District</th><th>Party</th>"
            "<th>Write in?</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


AS = ("<p>Candidates for the 2026 Midterm Election</p>"
      "<p>The Commissioner of Elections has certified the following candidates for the Midterm "
      "Election scheduled for November 3, 2026.</p>"
      "<p><span>DELEGATE TO THE UNITED STATES CONGRESS</span></p>"
      "<div><p><span>��</span><span>Aumua Amata</span></p></div>"
      "<p>Fualaau Rosie Tago Lancaster</p><p>Samana Semo Veavea</p>"
      "<p>HOUSE OF REPRESENTATIVES</p><p>Fetui F. Fetu Jr.</p>")


def tx_row(office, name, party, cand_type=None, declared="A", filing="CG", active="A",
           election="2026 NOVEMBER GENERAL ELECTION"):
    """One row of the Texas service's answer, as read on 2026-10-17, with
    the address, email and occupation it also carries left out."""
    return {"cdCandType": cand_type, "cdParty": party, "cdStatus": active,
            "cdDeclarationStatus": declared, "cdFilingStatus": filing,
            "txFullNameBallot": name, "txOfficeName": office + " ",
            "txElectionName": election}


def tx_page(drop=None, extra=()):
    import json
    rows = [tx_row("U. S. SENATOR", "KEN PAXTON", "R", active=None),
            tx_row("U. S. SENATOR", "JAMES TALARICO", "D", "RGCAN"),
            tx_row("U. S. SENATOR", "TED BROWN", "L", active=None),
            tx_row("U. S. SENATOR", "AVERY AYERS", "W", "WRTIN"),
            # Rejected as an independent, then a write-in: neither printed.
            tx_row("U. S. SENATOR", "JADE SIMMONS", "I", "RGCAN", declared="R", filing=None),
            tx_row("U. S. SENATOR", "JADE SIMMONS", "W", "WRTIN", active=None)]
    for n in [n for n in range(1, 39) if n != drop]:
        office = f"U. S. REPRESENTATIVE DISTRICT {n}"
        rows += [tx_row(office, f"REP NUMBER{n}", "R"), tx_row(office, f"DEM NUMBER{n}", "D")]
    # TX-38's Green nominee: the record is marked inactive, and Harris
    # County's ballot order prints him all the same.
    rows.append(tx_row("U. S. REPRESENTATIVE DISTRICT 38", "ALEX MCMENEMY", "G", "RGCAN",
                       active="I"))
    rows.append(tx_row("STATE SENATOR, DISTRICT 18", "LOIS W. KOLKHORST", "R"))
    return json.dumps(rows + list(extra))


class TestReaders(unittest.TestCase):
    def test_texas_reads_the_secretary_of_states_qualified_list(self):
        out = certified.parse_texas(tx_page())
        senate = [(e["name"], e["party"], e["kind"]) for e in out["S-TX-2026"]]
        self.assertIn(("TED BROWN", "Libertarian", "ballot"), senate)
        self.assertIn(("AVERY AYERS", "", "write-in"), senate)
        self.assertIn(("JADE SIMMONS", "", "write-in"), senate)
        self.assertNotIn(("JADE SIMMONS", "Independent", "ballot"), senate)   # rejected
        self.assertEqual(sum(1 for e in senate if e[2] == "ballot"), 3)
        self.assertIn(("ALEX MCMENEMY", "Green", "ballot"),
                      [(e["name"], e["party"], e["kind"]) for e in out["H-TX-38-2026"]])
        self.assertEqual(len([r for r in out if r.startswith("H-")]), 38)     # no state seats

    def test_texas_refuses_what_it_does_not_know(self):
        for page in (tx_page(drop=5),                       # a district missing
                     tx_page(extra=[tx_row("U. S. SENATOR", "A B", "R", declared="P",
                                           filing=None)]),  # a status not known
                     tx_page(extra=[tx_row("U. S. SENATOR", "A B", "X")]),
                     tx_page(extra=[tx_row("U. S. SENATOR", "A B", "R",
                                           election="2026 REPUBLICAN PRIMARY ELECTION")]),
                     "<html>maintenance</html>", "[]"):
            with self.assertRaises(certified.CertifiedError):
                certified.parse_texas(page)
        withdrew = certified.parse_texas(tx_page(extra=[
            tx_row("U. S. SENATOR", "SAM QUIT", "L", declared="WDE", filing=None)]))
        self.assertIn({"name": "SAM QUIT", "party": "Libertarian", "kind": "withdrawn"},
                      withdrew["S-TX-2026"])

    def test_texas_is_read_with_a_post_and_credited_to_its_page(self):
        self.assertEqual(certified.POSTS[certified.TX_URL]["electionId"], certified.TX_ELECTION)
        self.assertEqual(certified.SHOWN[certified.TX_URL], certified.TX_PAGE)
        # Texas's own list replaced the party's; a curated list would
        # overwrite the one read (fetch applies them last).
        self.assertNotIn("TX", overrides.CERTIFIED_BALLOTS)

    def test_alaska_prints_six_and_reads_write_ins_as_write_ins(self):
        out = certified.parse_alaska(AK)
        senate = {e["name"]: e["kind"] for e in out["S-AK-2026"]}
        self.assertEqual(senate["Daniel J. Sullivan Jr."], "ballot")
        self.assertEqual(senate["Dan S. Sullivan"], "ballot")
        self.assertEqual(senate["Heather McElwain"], "write-in")
        self.assertEqual(senate['Sidney "Sid" Hill'], "write-in")
        house = [(e["name"], e["party"], e["kind"]) for e in out["H-AK-00-2026"]]
        self.assertIn(('James C. "Jim" McDermott', "Libertarian", "ballot"), house)
        self.assertIn(("Eric Hafner", "Democrat", "ballot"), house)
        self.assertEqual(sum(1 for e in house if e[2] == "ballot"), 4)

    def test_alaska_refuses_a_status_it_does_not_know(self):
        page = AK.replace("(Certified)</small>", "(Pending)</small>", 1)
        with self.assertRaises(certified.CertifiedError):
            certified.parse_alaska(page)

    def test_florida_reads_qualified_minor_parties_and_skips_what_is_not_printed(self):
        out = certified.parse_florida(fl_page())
        fl4 = {e["name"]: (e["party"], e["kind"]) for e in out["H-FL-04-2026"]}
        self.assertEqual(fl4["Todd Schaefer"], ("No Party Affiliation", "ballot"))
        self.assertEqual(fl4["Mike Sell"], ("Florida Forward Party", "ballot"))
        self.assertEqual(fl4["Brit Robinson"][1], "lost-primary")
        self.assertEqual(fl4["Jane Doe"][1], "write-in")
        self.assertEqual(out["H-FL-10-2026"][0]["kind"], "unopposed")
        self.assertEqual(len([r for r in out if r.startswith("H-FL-")]), 28)
        self.assertIn("S-FL-2026", out)

    def test_florida_refuses_a_listing_missing_a_seat(self):
        with self.assertRaises(certified.CertifiedError):
            certified.parse_florida(fl_page(drop=17))

    def test_colorado_reads_struck_names_as_withdrawn(self):
        out = certified.parse_colorado(co_page())
        co1 = {e["name"]: e["kind"] for e in out["H-CO-01-2026"]}
        self.assertEqual(co1, {"Rep1 Person": "ballot", "Shimon Blau": "ballot",
                               "Gone Away": "withdrawn"})
        self.assertEqual(out["S-CO-2026"][1]["kind"], "write-in")
        self.assertNotIn("Duane L Gurule", str(out))           # not a federal office
        with self.assertRaises(certified.CertifiedError):
            certified.parse_colorado(co_page(seats=7))

    def test_american_samoa_reads_the_delegate_section_only(self):
        out = certified.parse_american_samoa(AS)
        self.assertEqual([e["name"] for e in out["H-AS-00-2026"]],
                         ["Aumua Amata", "Fualaau Rosie Tago Lancaster", "Samana Semo Veavea"])
        with self.assertRaises(certified.CertifiedError):
            certified.parse_american_samoa(AS.replace("has certified", "will publish"))

    def test_names_turn_round_with_the_suffix_last(self):
        self.assertEqual(certified.last_first("Sullivan, Daniel J. Jr."), "Daniel J. Sullivan Jr.")
        self.assertEqual(certified.last_first("Rivera , Ernest “Ernie”".replace(" ,", ",")),
                         'Ernest "Ernie" Rivera')

    def test_nothing_but_name_party_and_kind_is_kept(self):
        for parse, page in ((certified.parse_alaska, AK), (certified.parse_florida, fl_page()),
                            (certified.parse_colorado, co_page()),
                            (certified.parse_american_samoa, AS),
                            (certified.parse_texas, tx_page())):
            for entries in parse(page).values():
                for e in entries:
                    self.assertEqual(set(e), {"name", "party", "kind"})
                    self.assertNotIn("PO Box", e["name"])

    def test_a_failed_read_is_reported_and_the_last_list_kept(self):
        def read(url):
            if "alaska" in url:
                raise OSError("timeout")
            return {certified.FL_URL: fl_page(), certified.CO_URL: co_page(),
                    certified.AS_URL: AS, certified.TX_URL: tx_page()}[url]
        lists, failed = certified.fetch(read=read, log=lambda *_: None, sleep=lambda s: None,
                                        today=datetime.date(2026, 10, 17))
        self.assertEqual(failed, ["AK"])
        self.assertNotIn("AK", lists)
        # A list read from a service links the page a reader can open.
        self.assertEqual(lists["TX"]["url"], certified.TX_PAGE)
        previous = {"certified": {"AK": {"source": "x", "fetched": "2026-10-10",
                                         "complete": True, "races": {}}}}
        self.assertEqual(certified.carry(lists, failed, previous), ["AK"])
        self.assertTrue(lists["AK"]["carried"])
        self.assertEqual(lists["AK"]["fetched"], "2026-10-10")

    def test_every_curated_list_names_its_document_and_day(self):
        for state, spec in overrides.CERTIFIED_BALLOTS.items():
            self.assertRegex(spec["url"], r"^https://", state)
            datetime.date.fromisoformat(spec["read"])
            self.assertIsInstance(spec["complete"], bool)
            for rid, people in spec["races"].items():
                self.assertRegex(rid, rf"^(S-{state}-2026|H-{state}-\d\d-2026)$")
                for name, party in people:
                    self.assertGreaterEqual(len(name.split()), 2, name)
        # Rick Stewart (IA-2) and Mike Marvin (Nebraska's Senate race) are
        # on their states' certified ballots.
        self.assertIn(("Rick Stewart", "Libertarian"),
                      overrides.CERTIFIED_BALLOTS["IA"]["races"]["H-IA-02-2026"])
        self.assertIn("Mike Marvin", str(overrides.CERTIFIED_BALLOTS["NE"]["races"]["S-NE-2026"]))


# ----------------------------------------------------------------- overlay


def row(cid, name, state, district, party, office="H"):
    return {"candidate_id": cid, "name": name, "state": state, "office": office,
            "district_number": district, "party": party}


def spec(entries, complete=True, source="Alaska Division of Elections"):
    return {"source": source, "url": "https://example.gov", "fetched": "2026-10-17",
            "complete": complete,
            "entries": [{"name": n, "party": p, "kind": k} for n, p, k in entries]}


def filer(cid, name, state, district, party, chamber="House (Candidate)"):
    return {"id": "FEC_" + cid, "fecCandidateId": cid, "isCandidate": True,
            "source": "fec-field", "name": name, "filedName": name, "party": party,
            "state": state, "chamber": chamber, "districtNum": district}


class TestOverlay(unittest.TestCase):
    def ak_house(self):
        # As the page left it: McDermott and Hafner "withdrawn", Schultz,
        # who withdrew after the primary, still the page's nominee.
        page = {"page": "x", "status": {"H2AK01083": "nominee", "H6AK01092": "nominee",
                                        "H2AK00143": "withdrawn", "H6AK01084": "nominee"},
                "party": {}, "unmatched": {"Eric Hafner": "withdrawn",
                                           "Clay Strickland": "nominee"},
                "ambiguous": [], "decided": {"general": True, "parties": ["all"]}}
        rows = [row("H2AK01083", "BEGICH, NICHOLAS III", "AK", 0, "REP"),
                row("H6AK01092", "HILL, BILL", "AK", 0, "IND"),
                row("H2AK00143", "MCDERMOTT, JIM C", "AK", 0, "LIB"),
                row("H4AK00164", "ERIC, HAFNER", "AK", 0, "DEM"),
                row("H6AK01084", "SCHULTZ, MATTHEW DAMIAN", "AK", 0, "DEM"),
                row("H2AK01182", "DUTCHESS, LADY DONNA", "AK", 0, "N")]
        listed = spec([("Nick Begich", "Republican", "ballot"),
                       ("Lady Donna Dutchess", "Nonpartisan", "write-in"),
                       ("Eric Hafner", "Democrat", "ballot"),
                       ("Bill Hill", "Nonpartisan", "ballot"),
                       ('James C. "Jim" McDermott', "Libertarian", "ballot")])
        return results.certify_race(page, listed, rows)

    def test_the_list_puts_back_the_people_the_page_called_withdrawn(self):
        race = self.ak_house()
        self.assertEqual(race["status"]["H2AK00143"], "nominee")       # McDermott
        self.assertEqual(race["status"]["H4AK00164"], "nominee")       # Hafner, filed reversed
        self.assertEqual(race["names"]["H4AK00164"], "Eric Hafner")
        self.assertNotIn("Eric Hafner", race["unmatched"])             # one person, one status
        self.assertEqual(race["certifiedIds"]["H2AK00143"], "nominee")
        self.assertNotIn("H2AK01083", race["certifiedIds"])            # the page already agreed

    def test_a_page_nominee_the_complete_list_leaves_out_is_not_on_the_ballot(self):
        race = self.ak_house()
        self.assertEqual(race["status"]["H6AK01084"], "unlisted")      # Schultz withdrew
        self.assertEqual(race["unmatched"]["Clay Strickland"], "unlisted")
        self.assertNotIn("H2AK01182", race["status"])                  # a write-in: untouched
        summary = results.race_summary({"races": {"H-AK-00-2026": race}}, "H-AK-00-2026")
        self.assertEqual(summary["otherNominees"], [])
        self.assertEqual(summary["certifiedBy"], "Alaska Division of Elections")
        self.assertTrue(summary["certifiedComplete"])

    def test_the_profile_credits_the_list(self):
        race = self.ak_house()
        mcd = filer("H2AK00143", "Jim C Mcdermott", "AK", 0, "Libertarian")
        schultz = filer("H6AK01084", "Matthew Damian Schultz", "AK", 0, "Democrat")
        nobody = filer("H6AK09999", "Pat Nobody", "AK", 0, "Democrat")
        results.apply_cache([mcd, schultz, nobody], {"races": {"H-AK-00-2026": race}})
        self.assertEqual((mcd["raceStatus"], mcd["raceStatusSource"]), ("nominee", "certified"))
        self.assertEqual(mcd["raceStatusSourceName"], "Alaska Division of Elections")
        self.assertEqual((schultz["raceStatus"], schultz["raceStatusSource"]),
                         ("unlisted", "certified"))
        # A filer neither the page nor the list names: not on the ballot,
        # on the list's word, whatever their party.
        self.assertEqual((nobody["raceStatus"], nobody["raceStatusSource"]),
                         ("unlisted", "certified"))
        self.assertNotIn("ballotUnknown", nobody)
        # The ballot's name, with the filing's kept.
        self.assertEqual(mcd["name"], 'James C. "Jim" McDermott')
        self.assertEqual(mcd["fecName"], "Jim C Mcdermott")
        self.assertEqual(mcd["nameVia"], "certified-list")

    def test_a_name_on_the_list_that_may_be_a_filer_holds_them_undecided(self):
        page = {"page": "x", "status": {"H6AS00056": "nominee"}, "unmatched": {},
                "ambiguous": [], "decided": {"general": True, "parties": []}}
        rows = [row("H6AS00056", "VEAVEA, SEMANA", "AS", 0, "N")]
        race = results.certify_race(page, spec([("Samana Semo Veavea", "", "ballot")]), rows)
        self.assertEqual(race["status"]["H6AS00056"], "nominee")       # not struck off
        self.assertEqual(race["certifiedHeld"], ["H6AS00056"])

    def test_a_seat_with_no_primary_is_the_list(self):
        rows = [row("H4AS00036", "AMATA, AUMUA", "AS", 0, "REP"),
                row("H4AS00093", "SUITONU-CHAPMAN, MELEAGI", "AS", 0, "N"),
                row("H6AS01021", "KING YOUNG, SANDRA S", "AS", 0, "DEM")]
        race = results.certify_race(None, spec(
            [("Aumua Amata", "", "ballot"), ("Meleagi Suitonu Chapman", "", "ballot"),
             ("Sandra King Young", "", "ballot"), ("Samana Semo Veavea", "", "ballot")],
            source="American Samoa Election Office"), rows)
        self.assertEqual(race["source"], "certified")
        self.assertEqual(race["status"], {"H4AS00036": "nominee", "H4AS00093": "nominee",
                                          "H6AS01021": "nominee"})
        self.assertEqual(race["unmatched"], {"Samana Semo Veavea": "nominee"})
        self.assertTrue(race["decided"]["general"])
        # A list that prints no party says nothing about one: read as
        # "Independent", it relabelled a Democratic filer.
        self.assertEqual(race["party"], {})
        self.assertEqual(race["label"], {})

    def test_a_party_named_independent_keeps_its_name(self):
        rows = [row("H6FL20119", "MAXIME, KEDNER", "FL", 20, "IND"),
                row("H6FL21109", "COOKE, ALEXANDER", "FL", 21, "NNE")]
        race = results.certify_race(None, spec(
            [("Kedner Maxime", "Independent Party of Florida", "ballot")]), rows[:1])
        self.assertEqual(race["party"], {"H6FL20119": "independent"})
        self.assertEqual(race["label"], {"H6FL20119": "Independent Party of Florida"})
        race = results.certify_race(None, spec(
            [("Alexander Cooke", "No Party Affiliation", "ballot")]), rows[1:])
        self.assertEqual(race["party"], {"H6FL21109": "independent"})
        self.assertEqual(race["label"], {})

    def test_a_partial_list_only_adds(self):
        page = {"page": "x", "status": {"H4TX26149": "nominee", "H6TX26144": "nominee"},
                "unmatched": {}, "ambiguous": [],
                "decided": {"general": True, "parties": ["democratic", "republican"]}}
        rows = [row("H4TX26149", "GILL, BRANDON", "TX", 26, "REP"),
                row("H6TX26144", "DOE, JANE", "TX", 26, "DEM"),
                row("H6TX01261", "GRAY, PHIL", "TX", 26, "LIB")]
        race = results.certify_race(page, spec([("Phil Gray", "Libertarian", "ballot")],
                                               complete=False, source="LP Texas"), rows)
        self.assertEqual(race["status"], {"H4TX26149": "nominee", "H6TX26144": "nominee",
                                          "H6TX01261": "nominee"})
        other = filer("H6TX26999", "Pat Other", "TX", 26, "Green")
        results.apply_cache([other], {"races": {"H-TX-26-2026": race}})
        self.assertNotEqual(other.get("raceStatusSource"), "certified")

    def test_after_the_count_a_result_stands(self):
        page = {"page": "x", "status": {"S6NE00129": "elected", "S6NE00152": "defeated"},
                "unmatched": {}, "ambiguous": [], "decided": {"general": True, "parties": []}}
        rows = [row("S6NE00129", "RICKETTS, PETE", "NE", 0, "REP", "S"),
                row("S6NE00152", "MARVIN, MIKE", "NE", 0, "LMN", "S")]
        race = results.certify_race(page, spec([("Pete Ricketts", "Republican", "ballot"),
                                                ("Mike Marvin", "Legal Marijuana NOW",
                                                 "ballot")]), rows)
        self.assertEqual(race["status"], {"S6NE00129": "elected", "S6NE00152": "defeated"})

    def test_the_build_lays_the_list_over_the_page_and_keeps_it_in_the_cache(self):
        field = {"candidates": [row("H4AS00036", "AMATA, AUMUA", "AS", 0, "REP")]}
        lists = {"AS": {"source": "American Samoa Election Office", "url": "https://x",
                        "fetched": "2026-10-17", "complete": True,
                        "races": {"H-AS-00-2026": [{"name": "Aumua Amata", "party": "",
                                                    "kind": "ballot"}]}}}
        cache = results.build(field, {}, today=datetime.date(2026, 10, 17), log=lambda *_: None,
                              fetch=lambda t: (_ for _ in ()).throw(results.PageMissing(t)),
                              certified=lists)
        self.assertNotIn("H-AS-00-2026", cache["pending"])
        self.assertEqual(cache["races"]["H-AS-00-2026"]["status"], {"H4AS00036": "nominee"})
        self.assertEqual(cache["certified"]["AS"]["races"]["H-AS-00-2026"][0]["name"],
                         "Aumua Amata")

    def test_a_nominee_with_no_profile_carries_the_ballots_name_and_party(self):
        race = self.ak_house()
        cache = {"races": {"H-AK-00-2026": race}}
        filed = {r: {"candidate_id": r, "name": n, "party": p} for r, n, p in (
            ("H4AK00164", "ERIC, HAFNER", "DEM"),)}
        below = races._below_threshold(cache, "H-AK-00-2026", filed, set())
        # Alaska prints "Democrat"; beside the name it reads as every other
        # race note does, "Democratic" (one vocabulary, not each list's).
        self.assertEqual(below, [{"id": "H4AK00164", "name": "Eric Hafner",
                                  "status": "nominee", "party": "Democratic"}])

    def test_an_unaffiliated_candidate_is_not_called_independent(self):
        rows = [row("H6CO07130", "KRZECZKOWSKI, JOE", "CO", 7, "IND")]
        race = results.certify_race(None, spec([("Joe Krzeczkowski", "Unaffiliated", "ballot")]),
                                    rows)
        cache = {"races": {"H-CO-07-2026": race}}
        filed = {"H6CO07130": {"candidate_id": "H6CO07130", "name": "KRZECZKOWSKI, JOE",
                               "party": "IND"}}
        below = races._below_threshold(cache, "H-CO-07-2026", filed, set())
        self.assertEqual(below[0]["party"], "Unaffiliated")

    def test_one_vocabulary_of_parties_beside_names(self):
        # Alaska "Democrat", Colorado "Libertarian Party", Florida
        # "Libertarian Party of Florida": three spellings of two parties
        # beside cards that say "Democratic" and "Libertarian".
        for printed, shown in (("Democrat", "Democratic"), ("Republican Party", "Republican"),
                               ("Libertarian Party of Florida", "Libertarian"),
                               ("Green", "Green"), ("Unity Party", "Unity Party"),
                               ("Independent Party of Florida", "Independent Party of Florida"),
                               ("Unaffiliated", "Unaffiliated"), ("", "")):
            self.assertEqual(results.list_party_words(printed), shown, printed)

    def test_a_list_that_prints_no_party_gives_none(self):
        # American Samoa prints five names and no party; the filing's
        # "Democratic" beside one of them read as the list's.
        rows = [row("H6AS00099", "YOUNG, SANDRA KING", "AS", 0, "DEM")]
        race = results.certify_race(None, spec([("Sandra King Young", "", "ballot")],
                                               source="American Samoa Election Office"), rows)
        filed = {"H6AS00099": {"candidate_id": "H6AS00099", "name": "YOUNG, SANDRA KING",
                               "party": "DEM"}}
        below = races._below_threshold({"races": {"H-AS-00-2026": race}}, "H-AS-00-2026",
                                       filed, set())
        self.assertEqual(below[0]["party"], "")

    def test_a_list_in_capitals_never_replaces_a_name(self):
        # Texas prints "ALEX MCMENEMY"; the page's "Alex McMenemy" is how
        # his name is written, and a profile keeps its own spelling.
        page = {"page": "x", "status": {"H6TX38001": "nominee"},
                "names": {"H6TX38001": "Jon Bonck"}, "party": {},
                "unmatched": {"Alex McMenemy": "nominee"}, "ambiguous": [],
                "decided": {"general": True, "parties": ["republican", "democratic"]}}
        rows = [row("H6TX38001", "BONCK, JON", "TX", 38, "REP")]
        race = results.certify_race(page, spec([("JON BONCK", "Republican", "ballot"),
                                                ("ALEX MCMENEMY", "Green", "ballot")],
                                               source="Texas Secretary of State"), rows)
        self.assertEqual(race["names"]["H6TX38001"], "Jon Bonck")
        self.assertEqual(race["listNames"]["H6TX38001"], "JON BONCK")
        self.assertEqual(race["unmatched"], {"Alex McMenemy": "nominee"})
        self.assertEqual(race["unmatchedParty"], {"Alex McMenemy": "Green"})
        person = filer("H6TX38001", "Jon Bonck", "TX", 38, "Republican")
        results.apply_cache([person], {"races": {"H-TX-38-2026": race}})
        self.assertEqual((person["name"], person["raceStatus"]), ("Jon Bonck", "nominee"))
        self.assertNotIn("fecName", person)
        # With no page spelling to keep, written as a name is written.
        alone = results.certify_race(None, spec([("ALEX MCMENEMY", "Green", "ballot"),
                                                 ("TONY D'ARRIGO", "Independent", "ballot"),
                                                 ("JOHN Q. PUBLIC III", "Green", "ballot")]), [])
        self.assertEqual(sorted(alone["unmatched"]),
                         ["Alex McMenemy", "John Q. Public III", "Tony D'Arrigo"])

    def test_the_list_gives_the_name_it_prints(self):
        # Alaska's Senate race: two Republicans the site showed as "Dan
        # Sullivan" and "Daniel J Sullivan"; the ballot tells them apart.
        rows = [row("S6AK00326", "SULLIVAN, DANIEL J", "AK", None, "REP", office="S"),
                row("S4AK00214", "SULLIVAN, DAN", "AK", None, "REP", office="S")]
        page = {"page": "x", "status": {"S4AK00214": "nominee"}, "party": {},
                "unmatched": {}, "ambiguous": [], "decided": {"general": True, "parties": []}}
        race = results.certify_race(page, spec([("Dan S. Sullivan", "Republican", "ballot"),
                                                ("Daniel J. Sullivan Jr.", "Republican",
                                                 "ballot")]), rows)
        person = filer("S6AK00326", "Daniel J Sullivan", "AK", None, "Republican",
                       chamber="Senate (Candidate)")
        results.apply_cache([person], {"races": {"S-AK-2026": race}})
        self.assertEqual((person["name"], person["fecName"], person["nameVia"]),
                         ("Daniel J. Sullivan Jr.", "Daniel J Sullivan", "certified-list"))
        # The FEC misspells Florida's Senate nominee "GILESPIE"; the list and
        # his committee say Gillespie (overrides.RESULT_NAMES).
        rows = [row("S6FL00863", "GILESPIE, NEIL JOSEPH", "FL", None, "NPA", office="S")]
        race = results.certify_race(None, spec([("Neil J. Gillespie", "No Party Affiliation",
                                                 "ballot")]), rows)
        neil = filer("S6FL00863", "Neil Joseph Gilespie", "FL", None, "No Party Affiliation",
                     chamber="Senate (Candidate)")
        results.apply_cache([neil], {"races": {"S-FL-2026": race}})
        self.assertEqual((neil["name"], neil["fecName"]), ("Neil J. Gillespie",
                                                           "Neil Joseph Gilespie"))
        # Only case and full stops apart is the same name.
        same = filer("S6AK00326", "Daniel J Sullivan", "AK", None, "Republican",
                     chamber="Senate (Candidate)")
        race["listNames"] = {"S6AK00326": "Daniel J. Sullivan"}
        results.apply_cache([same], {"races": {"S-AK-2026": dict(
            race, status={"S6AK00326": "nominee"})}})
        self.assertEqual(same["name"], "Daniel J Sullivan")

    def test_a_list_names_everyone_it_holds_not_only_the_printed(self):
        # Florida's list holds FL-2's primary losers too. It writes "Yen
        # Bailey", the FEC "BAILEY, HUY-YEN CAM"; the list's entry took the
        # page's spelling away, and recording only printed names left her
        # under the FEC's form, where main had shown "Yen Bailey".
        rows = [row("H4FL02138", "BAILEY, HUY-YEN CAM", "FL", 2, "DEM"),
                row("H6FL02299", "GREEN, AMANDA MARIE", "FL", 2, "DEM")]
        page = {"page": "x", "status": {"H6FL02299": "nominee"}, "party": {},
                "unmatched": {"Yen Bailey": "eliminated"}, "ambiguous": [],
                "decided": {"general": True, "parties": ["democratic"]}}
        race = results.certify_race(page, spec([("Yen Bailey", "Democratic", "lost-primary"),
                                                ("Amanda Marie Green", "Democratic", "ballot")],
                                               source="Florida Division of Elections"), rows)
        self.assertEqual(race["status"]["H4FL02138"], "eliminated")
        self.assertNotIn("Yen Bailey", race["unmatched"])
        self.assertNotIn("H4FL02138", race["listParty"])       # printed beside no one
        bailey = filer("H4FL02138", "Huy-Yen Cam Bailey", "FL", 2, "Democrat")
        results.apply_cache([bailey], {"races": {"H-FL-02-2026": race}})
        self.assertEqual((bailey["name"], bailey["fecName"], bailey["raceStatus"]),
                         ("Yen Bailey", "Huy-Yen Cam Bailey", "eliminated"))

    def test_a_certified_write_in_is_neither_on_nor_off_the_ballot(self):
        rows = [row("H4CO01187", "WREN, JOHN", "CO", 1, "IND")]
        race = results.certify_race(None, spec([("Jane Doe", "Democratic Party", "ballot"),
                                                ("John Wren", "Unaffiliated", "write-in")],
                                               source="Colorado Secretary of State"), rows)
        person = filer("H4CO01187", "John Wren", "CO", 1, "Independent")
        results.apply_cache([person], {"races": {"H-CO-01-2026": race}})
        self.assertNotIn("raceStatus", person)        # not "not on the certified list"
        self.assertTrue(person["ballotUnknown"])

    def test_an_unprinted_name_may_be_a_page_nominee(self):
        # Florida prints no uncontested race. A page nominee the list names
        # as unopposed under another spelling is not struck off; nor is a
        # page name the list holds as unopposed.
        page = {"page": "x", "status": {"H6FL10001": "nominee"}, "party": {},
                "unmatched": {"Pat Alone": "nominee"}, "ambiguous": [],
                "decided": {"general": True, "parties": []}}
        rows = [row("H6FL10001", "FROST, MAXWELL ALEJANDRO", "FL", 10, "DEM")]
        race = results.certify_race(page, spec([("Maxwell Alejandro Frostt", "Democratic",
                                                 "unopposed"),
                                                ("Pat Alone", "Republican", "unopposed")],
                                               source="Florida Division of Elections"), rows)
        self.assertEqual(race["status"]["H6FL10001"], "nominee")
        self.assertEqual(race["certifiedHeld"], ["H6FL10001"])
        self.assertEqual(race["unmatched"]["Pat Alone"], "nominee")


if __name__ == "__main__":
    unittest.main()
