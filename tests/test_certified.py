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


class TestReaders(unittest.TestCase):
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
                            (certified.parse_american_samoa, AS)):
            for entries in parse(page).values():
                for e in entries:
                    self.assertEqual(set(e), {"name", "party", "kind"})
                    self.assertNotIn("PO Box", e["name"])

    def test_a_failed_read_is_reported_and_the_last_list_kept(self):
        def read(url):
            if "alaska" in url:
                raise OSError("timeout")
            return {certified.FL_URL: fl_page(), certified.CO_URL: co_page(),
                    certified.AS_URL: AS}[url]
        lists, failed = certified.fetch(read=read, log=lambda *_: None, sleep=lambda s: None,
                                        today=datetime.date(2026, 10, 17))
        self.assertEqual(failed, ["AK"])
        self.assertNotIn("AK", lists)
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
        # The party in the list's own words: Alaska prints "Democrat".
        self.assertEqual(below, [{"id": "H4AK00164", "name": "Eric Hafner",
                                  "status": "nominee", "party": "Democrat"}])

    def test_an_unaffiliated_candidate_is_not_called_independent(self):
        rows = [row("H6CO07130", "KRZECZKOWSKI, JOE", "CO", 7, "IND")]
        race = results.certify_race(None, spec([("Joe Krzeczkowski", "Unaffiliated", "ballot")]),
                                    rows)
        cache = {"races": {"H-CO-07-2026": race}}
        filed = {"H6CO07130": {"candidate_id": "H6CO07130", "name": "KRZECZKOWSKI, JOE",
                               "party": "IND"}}
        below = races._below_threshold(cache, "H-CO-07-2026", filed, set())
        self.assertEqual(below[0]["party"], "Unaffiliated")


if __name__ == "__main__":
    unittest.main()
