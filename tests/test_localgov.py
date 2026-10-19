"""Tests for counties and local governments: the Census listing reader
(kyc/localgov.py) and the county pages' data (kyc/counties.py).

Two Census products are held to agree - the Government Units listing and the
published table of counts - and governments are joined to counties on the
Census code, never a name.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import census, counties, county_areas, localgov, localsites, overrides  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def localgov_states():
    """``{state code: its two-digit FIPS code}``."""
    from kyc.geo import FIPS_TO_STATE
    return {code: fips for fips, code in FIPS_TO_STATE.items()}


class TestNames(unittest.TestCase):

    def test_capitals_read_as_names(self):
        cases = {
            "COUNTY OF AUTAUGA": "County of Autauga",
            "CITY OF MCALLEN": "City of McAllen",
            "ALDINE ISD": "Aldine ISD",
            "O'FALLON FIRE PROTECTION DISTRICT": "O'Fallon Fire Protection District",
            "HARRIS COUNTY MUNICIPAL UTILITY DISTRICT NO 400":
                "Harris County Municipal Utility District No 400",
            "WEST-HARRIS COUNTY REGIONAL WATER AUTHORITY": "West-Harris County Regional Water Authority",
            "BOARD OF EDUCATION OF THE CITY OF ST. LOUIS": "Board of Education of the City of St. Louis",
            "TOWNSHIP OF II": "Township of II",
        }
        for raw, shown in cases.items():
            self.assertEqual(localgov.display_name(raw), shown, raw)


class TestAgreement(unittest.TestCase):

    def test_a_listing_that_disagrees_with_the_table_is_refused(self):
        listing = {"TX": {"counties": {"48001": {"name": "Anderson", "governments": [
            {"type": "county"}, {"type": "municipal"}]}}, "statewide": []}}
        table = {"states": {"TX": {"county": 1, "municipal": 2, "township": None,
                                   "special": 0, "school": 0}}}
        problems = localgov.check_against_table(listing, table)
        self.assertEqual(problems, ["TX municipal: listing 1, table 2"])

    def test_school_systems_another_government_runs_are_not_counted(self):
        listing = {"MD": {"counties": {"24001": {"name": "Allegany", "governments": [
            {"type": "county"}, {"type": "dependent"}]}}, "statewide": []}}
        table = {"states": {"MD": {"county": 1, "municipal": 0, "township": None,
                                   "special": 0, "school": None}}}
        self.assertEqual(localgov.check_against_table(listing, table), [])

    def test_the_committed_listing_agrees_with_the_table_everywhere(self):
        table = census.load_cache(ROOT)
        states = {}
        for name in sorted(os.listdir(os.path.join(ROOT, localgov.OUT_DIR))):
            code = name[:-5].upper()
            data = localgov.load(code, ROOT)
            states[code] = {"counties": data["counties"], "statewide": data["statewide"]}
        self.assertEqual(localgov.check_against_table(states, table), [])


class TestCountyPages(unittest.TestCase):

    def test_governments_join_their_county_by_census_code(self):
        page = counties.build_state("DE", ROOT, {})
        self.assertEqual(sorted(page["counties"]), ["10001", "10003", "10005"])
        listing = localgov.load("DE", ROOT)
        for fips, entry in listing["counties"].items():
            self.assertEqual(len(page["governments"][fips]), len(entry["governments"]))
        self.assertEqual(page["unmatched"], [])

    def test_an_address_in_capitals_keeps_its_path(self):
        self.assertEqual(counties.web_address("HTTP://WWW.KATYISD.ORG/"), "http://www.katyisd.org/")
        self.assertEqual(counties.web_address("HTTPS://WWW.EXAMPLE.ORG/Harris-County/MUD-558/"),
                         "https://www.example.org/Harris-County/MUD-558/")
        self.assertEqual(counties.web_address("www.example.org"), "")

    def test_a_row_says_what_the_page_shows(self):
        row = counties._row({"type": "special", "name": "Fire District No 1", "city": "Dover",
                             "web": "https://example.org", "function": "Local Fire Protection",
                             "inactive": True}, {"sites": {}})
        self.assertEqual(row, ["special", "Fire District No 1", "Dover", "https://example.org", "",
                               "Local Fire Protection", "inactive", "", ""])

    def test_a_census_filing_category_reads_in_plain_words(self):
        # STATEGOV-09: "Other Single Function Districts" is the Census's
        # function code, not a description.
        row = counties._row({"type": "special", "name": "X", "function": "Other Single Function Districts"},
                            {"sites": {}})
        self.assertEqual(row[5], "Single-purpose district")


class TestReadableNames(unittest.TestCase):
    """STATEGOV-09, PERSONA-17: 6,500 names on the county pages read in the
    Census's abbreviations ("Fairfax Co Schs", "Amador Co Spl Schs Oper by
    Co Supt"). They are written out from a closed table, and the listing's
    own form is kept beside them."""

    def test_the_listings_abbreviations_are_written_out(self):
        cases = {
            "Fairfax Co Schs": "Fairfax County Schools",
            "Amador Co Spl Schs Oper by Co Supt":
                "Amador County Special Schools Operated by County Superintendent",
            "Covina Val Unif Sch Dist": "Covina Valley Unified School District",
            "Los Angeles Co Off of Education": "Los Angeles County Office of Education",
            "Bethpage Uf Sch Dist": "Bethpage Union Free School District",
            "Trion Ind Sch Dist": "Trion Independent School District",
            "School Admin Dist 52": "School Administrative District 52",
            "Cayuga Co Comm Coll": "Cayuga County Community College",
        }
        for listed, written in cases.items():
            self.assertEqual(localgov.expand_name(listed), written, listed)

    def test_a_word_that_means_two_things_is_read_from_its_neighbours(self):
        # "Ind" is Indiana here, "Val" a name, "Comm" a commission.
        self.assertEqual(localgov.expand_name("Northern Ind Commuter Trans District"),
                         "Northern Ind Commuter Transportation District")
        self.assertEqual(localgov.expand_name("Val Verde Co"), "Val Verde County")
        self.assertEqual(localgov.expand_name("W Contra Costa Transp Adv Comm (Wcctac)"),
                         "W Contra Costa Transportation Adv Comm (Wcctac)")
        self.assertEqual(localgov.expand_name("South California Cmty Co Districts"),
                         "South California Community College Districts")
        # "Co" ending a name after "Improvement" may be a company: as filed.
        self.assertEqual(localgov.expand_name("Pine Flat District Improvement Co"),
                         "Pine Flat District Improvement Co")
        self.assertEqual(localgov.expand_name("Drainage District 31 Stoddard Co"),
                         "Drainage District 31 Stoddard County")
        # A 911 dispatch center, a reclamation authority, an aquifer's
        # storage and recovery, a collaborative: as filed, never renamed
        # into a community center, a recreation authority or a college.
        for name, written in (
                ("Island Co Emergency Svcs Comm Ctr", "Island County Emergency Services Comm Ctr"),
                ("West Cities Comm Ctr JPA (Westcomm)", "West Cities Comm Ctr JPA (Westcomm)"),
                ("Colton-San Bernardino Regional Tertiary Trtmnt & Water Rec Auth",
                 "Colton-San Bernardino Regional Tertiary Trtmnt & Water Rec Authority"),
                ("Corpus Christi Aquifer Storage & Rec Cons Dist",
                 "Corpus Christi Aquifer Storage & Rec Cons District"),
                ("Marshall County Family Services and Childrens Mental Health Coll",
                 "Marshall County Family Services and Childrens Mental Health Coll"),
                ("Ridgecrest Ranchos Rec Park Dist", "Ridgecrest Ranchos Recreation Park District"),
                ("Northwest Miss Community Coll", "Northwest Miss Community College"),
                ("Desert Ctr Unif Sch Dist", "Desert Center Unified School District"),
                ("Buckeye Cent Loc Sch Dist", "Buckeye Central Local School District"),
                ("Three Cent Flat Community Services District", "Three Cent Flat Community Services District"),
                ("Hoosic Vlly Cntrl Sch Dist at Schaghticoke",
                 "Hoosic Valley Central School District at Schaghticoke"),
                ("Cheyenne Mtn Sch Dist 12", "Cheyenne Mountain School District 12")):
            self.assertEqual(localgov.expand_name(name), written, name)

    def test_a_name_without_abbreviations_is_left_alone(self):
        for name in ("City of St. Louis", "Town of Mt Vernon", "County of Fairfax", ""):
            self.assertEqual(localgov.expand_name(name), name)

    def test_the_page_keeps_the_listings_name_beside_the_written_one(self):
        rows = counties._for_reading([["dependent", "Fairfax Co Schs", "", "", "", "", "", "", ""],
                                      ["county", "County of Fairfax", "", "", "", "", "", "", ""]])
        self.assertEqual(rows[0][1], "Fairfax County Schools")
        self.assertEqual(rows[0][8], "Fairfax Co Schs")
        self.assertEqual(rows[1][8], "")

    def test_the_built_page_writes_virginias_school_system_out(self):
        page = counties.build_state("VA", ROOT, {})
        rows = page["governments"]["51059"]
        schools = [r for r in rows if r[8] == "Fairfax Co Schs"]
        self.assertEqual([r[1] for r in schools], ["Fairfax County Schools"])


class TestSiteCheck(unittest.TestCase):
    """LINKS-07, TRUST-07: the 39,452 websites the Census listed in 2022 were
    linked unchecked; about one in a hundred led to gambling, parked or
    for-sale domains under a public body's name (rule 78)."""

    NAMES = ["Town of Clinton"]

    def seen(self, chain, status=200, markup="", error=""):
        return {"chain": chain, "status": status, "markup": markup, "error": error,
                "dnsHost": "", "insecure": False}

    def test_a_redirect_to_a_slot_site_is_gambling(self):
        verdict, evidence, _final = localsites.assess(self.NAMES, "http://clintonct.com/", self.seen(
            ["http://clintonct.com/", "https://id-pgdemoslot.com/"],
            markup="<title>Demo Slot Fury of Anubis</title><p>main slot demo gratis</p>"))
        self.assertEqual(verdict, localsites.GAMBLING)
        self.assertIn("id-pgdemoslot.com", evidence)

    def test_the_lander_script_is_parking(self):
        verdict, _e, _f = localsites.assess(["Town of Providence Village"], "http://townofprovidencevillage.com/",
                                            self.seen(["http://townofprovidencevillage.com/",
                                                       "http://townofprovidencevillage.com/lander"]))
        self.assertEqual(verdict, localsites.PARKED)

    def test_a_marketplace_is_for_sale(self):
        verdict, _e, _f = localsites.assess(["City of Imperial"], "http://www.imperialne.com", self.seen(
            ["http://www.imperialne.com", "https://www.hugedomains.com/domain_profile.cfm?d=imperialne.com"]))
        self.assertEqual(verdict, localsites.FOR_SALE)

    def test_a_parking_page_of_links_is_parked(self):
        markup = ('<title>rutlandcity.com</title><meta name="description" content="Find the best '
                  'information and most relevant links on all topics related to rutlandcity.com.">')
        verdict, _e, _f = localsites.assess(["City of Rutland"], "http://www.rutlandcity.com",
                                            self.seen(["http://www.rutlandcity.com"], markup=markup))
        self.assertEqual(verdict, localsites.PARKED)

    def test_a_move_to_a_page_naming_the_government_is_kept(self):
        markup = "<title>Home - Town of Peacham, Vermont</title><p>" + "Selectboard minutes. " * 30 + "</p>"
        verdict, _e, final = localsites.assess(["Town of Peacham"], "http://www.peacham.net",
                                               self.seen(["http://www.peacham.net", "https://peachamvt.org/"],
                                                         markup=markup))
        self.assertEqual((verdict, final), (localsites.MOVED, "https://peachamvt.org/"))

    def test_a_move_to_a_business_that_names_the_place_is_a_business(self):
        # Ringtown's municipal authority's address opens a funeral home in
        # Ringtown; Haverhill's an estate agent's Haverhill listings.
        markup = ("<title>Funeral Home &amp; Cremation Ringtown, PA</title><p>" +
                  "Serving families of Ringtown borough and Schuylkill County. " * 10 + "</p>")
        verdict, _e, _f = localsites.assess(["Ringtown Borough Municipal Authority"],
                                            "http://www.ringtownborough.com",
                                            self.seen(["http://www.ringtownborough.com",
                                                       "https://www.ringtownfuneral.com/"], markup=markup))
        self.assertEqual(verdict, localsites.BUSINESS)

    def moved_to(self, names, start, end, title, body="Board minutes and agendas. " * 20):
        markup = f"<title>{title}</title><p>{body}</p>"
        return localsites.assess(names, start, self.seen([start, end], markup=markup))[0]

    def test_a_new_site_titled_with_the_place_and_its_kind_is_the_government_moved(self):
        # The first full run withdrew 115 addresses as "elsewhere"; most were
        # school districts and authorities on new domains whose titles say
        # "Pettisville Schools" or "Chattanooga Airport", not the listing's
        # full name.
        for names, start, end, title in (
                (["Pettisville Local School District"], "http://blackbirds.pettisville.k12.oh.us",
                 "https://pettisvilleschools.org/", "Pettisville Schools"),
                (["Chattanooga Metropolitan Airport Authority"], "http://chattairport.com",
                 "https://flycha.com/", "Chattanooga Airport"),
                (["Aspen Valley Hospital District"], "http://www.aspenhospital.org",
                 "https://aspenvalleyhealth.org/", "Aspen Valley Health | For You. For Life."),
                (["Bend-La Pine Admin School District 1", "Bend-La Pine Admin Sch Dist 1"],
                 "http://www.bend.k12.or.us", "https://blschools.org/", "Home - Bend-La Pine Schools"),
                (["Town of Salisbury"], "http://www.salisburyma.gov.example",
                 "https://ma-salisbury.civicplus.com/", "Salisbury, MA | Official Website"),
                (["Thurston County Public Utility District"], "http://www.thurstonpud.com",
                 "https://thurstonpud.org/", "Official site of Thurston PUD"),
                # The listing's own initials for a school district, and
                # Washington's "benefit area" for a transit authority.
                (["North Santiam SD 29 J"], "http://www.nsantiam.k12.or.us/",
                 "https://www.nssd29j.org/", "Home - North Santiam School District"),
                (["Kitsap County Public Transportation Benefit Area Authority"],
                 "http://www.kitsaptransit.org", "https://www.kitsaptransit.com/",
                 "Kitsap Transit | Kitsap Transit")):
            self.assertEqual(self.moved_to(names, start, end, title), localsites.MOVED, title)

    def test_a_title_naming_the_place_but_not_the_government_is_not_kept(self):
        # A business says what it is; a page that names nothing of the
        # government, at an address that names nothing of it, is elsewhere.
        for names, start, end, title, verdict in (
                (["City of Alma"], "http://www.almawisconsin.com/", "https://almawisconsin.org/",
                 "Alma Chamber of Commerce | Alma, Wisconsin", localsites.BUSINESS),
                (["Town of Haverhill"], "http://www.haverhillnh.com", "https://beangroup.com/x",
                 "Haverhill, New Hampshire Real Estate | Homes for Sale", localsites.BUSINESS),
                (["Town of Sullivan"], "http://www.townofsullivan.com", "https://stlaw.example.com/",
                 "Welcome! | St. Lawrence County", localsites.ELSEWHERE)):
            self.assertEqual(self.moved_to(names, start, end, title), verdict, title)

    def test_a_gov_host_that_spells_the_name_is_the_government(self):
        # Only a government can hold a .gov name.
        self.assertEqual(self.moved_to(["County of De Witt"], "http://www.dewittcountyill.com",
                                       "https://dewittcountyil.gov/", "Home"), localsites.MOVED)
        # Another host that spells it may be its own, and is not withdrawn.
        self.assertEqual(self.moved_to(["County of De Witt"], "http://www.dewittcountyill.com",
                                       "https://dewitt.example.com/", "Home"), localsites.UNREAD)

    def test_a_move_whose_page_names_the_body_its_own_way_is_never_elsewhere(self):
        # The first run withdrew these as "elsewhere" and the page said the
        # new site did not name the government. Some are the body's own
        # site under the name it uses, some are written as the listing
        # misspells or abbreviates them; a failed match concludes nothing.
        kept = (
            (["Des Plaines Valley Mosquito Abatement District"], "http://www.desplainesvalleymad.com",
             "https://dvmad.org/", "Home - DesPlaines Valley Mosquito Abatement District"),
            (["Hoosic Vlly Cntrl Sch Dist at Schaghticoke"], "http://www.hoosicvalley.k12.ny.us",
             "https://hoosicvalley.org/", "Homepage | Hoosic Valley Central School District at Schaghticoke"),
            (["Las Virgenes Muncipal Water District"], "http://www.lvmwd.com", "https://www.lvmwd.gov/",
             "Homepage Las Virgenes Municipal Water District"),
            (["Kinneola Irrigation District"], "http://www.kinneloairrigationdistrict.info",
             "https://www.kinneloairrigationdistrictca.gov/", "Homepage Kinneloa Irrigation District"),
            (["Davenport Commmunity School District"], "http://www.davenport.k12.ia.us/",
             "https://www.davenportschools.org/", "Home - Davenport Community School District"),
            (["Twenty-Nine Palms Water District"], "http://www.29palmswater.org", "http://29palmswater.com",
             "Twentynine Palms Water District"),
            (["City of Oneill"], "http://www.cityofoneill.com", "https://cityofoneillnebraska.com/",
             "City of O'Neill, Nebraska - Home"),
            (["Buckeye Cent Loc Sch Dist"], "http://www.buckeye-central.k12.oh.us/",
             "https://www.buckeye-central.org", "Home - Buckeye Central Local School District"),
            (["High Plains Uwcd 1"], "http://www.hpwd.com/", "https://www.hpwd.org/",
             "Homepage High Plains Underground Water Conservation District"),
        )
        for names, start, end, title in kept:
            self.assertEqual(self.moved_to(names, start, end, title), localsites.MOVED, title)
        unsure = (
            (["Bartlett-Countryside Fire Protection District"], "http://www.bartlettfire.com",
             "https://www.bartlettilfd.gov/", "Bartlett Fire District, IL | Official Website"),
            (["Town of Greenfield"], "http://www.greenfieldtn.com", "https://www.greenfieldtn.org/",
             "City of Greenfield - Home"),
            (["City of Miamisburg"], "http://www.ci.miamisburg.oh.us/", "https://cityofmiamisburg.com/",
             "Welcome - Miamisburg, OH"),
            (["Cheyenne Mtn Sch Dist 12"], "http://www.cmsd.k12.co.us/", "https://www.cmsd12.org/",
             "Home | Cheyenne Mountain"),
        )
        for names, start, end, title in unsure:
            self.assertIn(self.moved_to(names, start, end, title), (localsites.MOVED, localsites.UNREAD), title)
            self.assertNotIn(self.moved_to(names, start, end, title), localsites.WITHDRAWN, title)

    def test_one_slip_in_a_long_word_is_the_same_word(self):
        self.assertTrue(localsites.near("kinneola", "kinneloa"))
        self.assertTrue(localsites.near("commmunity", "community"))
        self.assertTrue(localsites.near("muncipal", "municipal"))
        self.assertFalse(localsites.near("alma", "alms"))          # too short to say
        self.assertFalse(localsites.near("hamilton", "hampton"))
        # A misspelt generic word is not a word to look for.
        self.assertEqual(localsites.distinctive("Las Virgenes Muncipal Water District"), ["las", "virgenes"])

    def test_the_listings_abbreviations_are_not_words_to_look_for(self):
        self.assertEqual(localsites.distinctive("Central Ind Sch Dist"), [])
        self.assertEqual(localsites.distinctive("Covina Val Unif Sch Dist"), ["covina"])
        # A name with nothing distinctive concludes nothing on a page that
        # does not carry it whole.
        self.assertEqual(self.moved_to(["Central Independent School District", "Central Ind Sch Dist"],
                                       "http://central.k12.mn.us", "https://isd108.org/",
                                       "Central Public Schools"), localsites.UNREAD)

    def test_a_slot_booked_online_is_not_gambling(self):
        # Both shipped as "now leads to a gambling site" on 2026-10-17, and
        # the verdict could never be cleared.
        for names, url, sentence in (
                (["Keansburg Borough School District"], "http://www.keansburg.k12.nj.us",
                 "Blood drive on Friday. Appointments encouraged, though walk-ins are welcome! "
                 "Schedule your slot online: https://tinyurl.com/KeansburgHSBloodDr"),
                (["Landfill of North Iowa"], "http://www.landfillnorthiowa.org/",
                 "Appointments For Saturday Drop Off. Secure your 15-minute slot online to guarantee "
                 "your weekend disposal.")):
            markup = (f"<title>Home - {names[0]}</title><p>{sentence}</p>" +
                      "<p>Board meeting agendas and minutes.</p>" * 30)
            verdict, _e, _f = localsites.assess(names, url, self.seen([url], markup=markup))
            self.assertEqual(verdict, localsites.OK, names[0])

    def test_gambling_once_in_a_page_is_withdrawn_but_waits_for_a_person(self):
        markup = ("<title>City of White Hall</title><p>Situs tiger227 Min Depo 20.000 Maxwin</p>" +
                  "<p>Council minutes.</p>" * 30)

        def visit(url, gate):
            return {"chain": [url], "status": 200, "markup": markup, "error": "", "dnsHost": "",
                    "insecure": False}
        entry = localsites.check_one("http://www.whitehallcitygov.com", ["City of White Hall"], self.gate(),
                                     visit_fn=visit, today="2026-10-18")
        self.assertEqual((entry["verdict"], entry["seen"]), (localsites.GAMBLING, "once"))
        self.assertFalse(localsites.sticky(entry))
        # Looked at again with the rest, and cleared if the page is clean.
        self.assertTrue(localsites.due(entry, "2026-10-19", recheck=("gambling",)))
        clean = {"checked": "2026-10-19", "verdict": "ok"}
        self.assertEqual(localsites.merge(entry, clean, "2026-10-19"), clean)
        # And reported for a person to confirm.
        # (White Hall's own host is now in BLOCKED_LOCAL_HOSTS: another's.)
        found = localsites.problems({"sites": {"http://www.townofx.example": entry}},
                                    {"http://www.townofx.example"}, today="2026-10-18")
        self.assertTrue(any("one passage" in p for p in found), found)

    def test_gambling_in_a_title_or_on_a_redirect_is_plain(self):
        title = localsites.gambling_at("Situs Slot Gacor Hari Ini", "", False)
        redirect = localsites.gambling_at("Home", "slot gacor maxwin", True)
        self.assertEqual((title, redirect), ("head", "redirect"))
        for seen in (title, redirect):
            self.assertTrue(localsites.sticky({"verdict": "gambling", "seen": seen}))
        # Recorded before ``seen`` was: stays until a person looks.
        self.assertTrue(localsites.sticky({"verdict": "gambling"}))

    def test_gambling_brands_built_on_a_lucky_number_are_gambling(self):
        verdict, _e, _f = localsites.assess(["Campbell County Fire Protection District"], "http://ccfd1ky.com/",
                                            self.seen(["http://ccfd1ky.com/", "https://texasluxuryhomeremodeling.com/"],
                                                      markup="<title>PGBET888</title><p>" + "x " * 300 + "</p>"))
        self.assertEqual(verdict, localsites.GAMBLING)

    def test_a_sign_in_wall_and_a_bot_wall_conclude_nothing(self):
        verdict, _e, _f = localsites.assess(["SAU 13"], "http://sites.google.com/view/sau-13/home", self.seen(
            ["http://sites.google.com/view/sau-13/home", "https://accounts.google.com/v3/signin/identifier"],
            markup="<title>Sign in</title>"))
        self.assertEqual(verdict, localsites.UNREAD)
        for status in (403, 429, 503):
            verdict, _e, _f = localsites.assess(self.NAMES, "http://x.org", self.seen(["http://x.org"], status))
            self.assertEqual(verdict, localsites.UNREAD, status)
        verdict, _e, _f = localsites.assess(self.NAMES, "http://x.org",
                                            self.seen(["http://x.org"], None, error="timed out"))
        self.assertEqual(verdict, localsites.UNREAD)

    def test_a_site_moved_onto_a_platform_under_its_own_address_has_not_left(self):
        verdict, _e, _f = localsites.assess(["Rollinsford School District"], "http://www.rollinsford.k12.nh.us/",
                                            self.seen(["http://www.rollinsford.k12.nh.us/",
                                                       "https://sites.google.com/a/rollinsford.k12.nh.us/x/"],
                                                      markup="<title>Home</title>" + "<p>School news</p>" * 40))
        self.assertEqual(verdict, localsites.OK)

    def gate(self):
        return localsites._Gate(interval=0, sleep=lambda s: None)

    def test_dead_only_when_two_public_resolvers_confirm_it(self):
        def visit(url, gate):
            return {"chain": [url], "status": None, "markup": "", "error": "x does not resolve",
                    "dnsHost": "www.daytonny.org", "insecure": False}
        dead = localsites.check_one("http://www.daytonny.org", ["Town of Dayton"], self.gate(), visit_fn=visit,
                                    doh_fn=lambda h, g: ("nxdomain", "nxdomain"), resolves=lambda h: False,
                                    today="2026-10-17")
        self.assertEqual(dead["verdict"], localsites.DEAD)
        for answers in (("nxdomain", None), ("exists",), ("nxdomain", "exists"), ("servfail",)):
            entry = localsites.check_one("http://www.daytonny.org", ["Town of Dayton"], self.gate(),
                                         visit_fn=visit, doh_fn=lambda h, g, a=answers: a,
                                         resolves=lambda h: False, sleep=lambda s: None, today="2026-10-17")
            self.assertEqual(entry["verdict"], localsites.UNREAD, answers)
        # A lame delegation (SERVFAIL) is said as such, and is not a death.
        self.assertIn("name servers do not answer", entry["evidence"])
        # It resolves on a second look here: nothing is concluded.
        entry = localsites.check_one("http://www.daytonny.org", ["Town of Dayton"], self.gate(), visit_fn=visit,
                                     doh_fn=lambda h, g: ("nxdomain", "nxdomain"), resolves=lambda h: True,
                                     sleep=lambda s: None, today="2026-10-17")
        self.assertEqual(entry["verdict"], localsites.UNREAD)

    def test_a_lookup_this_machine_dropped_is_tried_again(self):
        # 48 checks at once lost about 4,700 lookups at this machine's
        # resolver that dns.google answered: such an address is read again,
        # not left unread.
        visits = []

        def visit(url, gate):
            visits.append(url)
            if len(visits) == 1:
                return {"chain": [url], "status": None, "markup": "", "error": "x does not resolve",
                        "dnsHost": "www.daytonny.org", "insecure": False}
            return {"chain": [url], "status": 200, "markup": "<title>Town of Dayton</title>" + "<p>x</p>" * 50,
                    "error": "", "dnsHost": "", "insecure": False}
        looks = iter([False, True])
        entry = localsites.check_one("http://www.daytonny.org", ["Town of Dayton"], self.gate(), visit_fn=visit,
                                     doh_fn=lambda h, g: ("exists",), resolves=lambda h: next(looks),
                                     sleep=lambda s: None, today="2026-10-17")
        self.assertEqual((entry["verdict"], len(visits)), (localsites.OK, 2))

    def test_a_page_not_found_is_gone_only_when_seen_twice(self):
        answers = iter([404, 200])

        def visit(url, gate):
            return {"chain": [url], "status": next(answers), "markup": "<title>Town of X</title>" + "<p>x</p>" * 50,
                    "error": "", "dnsHost": "", "insecure": False}
        entry = localsites.check_one("http://x.org/a", ["Town of X"], self.gate(), visit_fn=visit,
                                     sleep=lambda s: None, today="2026-10-17")
        self.assertEqual(entry["verdict"], localsites.UNREAD)
        answers = iter([404, 404])
        entry = localsites.check_one("http://x.org/a", ["Town of X"], self.gate(), visit_fn=visit,
                                     sleep=lambda s: None, today="2026-10-17")
        self.assertEqual(entry["verdict"], localsites.GONE)

    def test_the_build_withdraws_what_the_check_refused_and_dates_the_rest(self):
        cache = {"sites": {
            "http://a.org": {"checked": "2026-10-17", "verdict": "gambling", "evidence": "x"},
            "http://b.org": {"checked": "2026-10-17", "verdict": "moved", "final": "https://c.gov/"},
            "http://d.org": {"checked": "2026-10-16", "verdict": "unread", "evidence": "HTTP 403"},
            "http://e.org": {"checked": "2026-10-17", "verdict": "dead"},
        }}
        self.assertEqual(localsites.status("http://a.org", cache), ("", "gambling 2026-10-17"))
        self.assertEqual(localsites.status("http://b.org", cache), ("http://b.org", "ok 2026-10-17"))
        self.assertEqual(localsites.status("http://d.org", cache), ("http://d.org", "unread 2026-10-16"))
        self.assertEqual(localsites.status("http://e.org", cache), ("", "dead 2026-10-17"))
        self.assertEqual(localsites.status("http://never.org", cache), ("http://never.org", ""))
        # A person's look outranks the cache.
        self.assertEqual(localsites.status("http://www.clintonct.com/", cache)[0], "")

    def test_a_gambling_verdict_is_never_cleared_by_a_later_check(self):
        old = {"checked": "2026-10-01", "verdict": "gambling", "seen": "head"}
        self.assertFalse(localsites.due(old, "2026-12-01"))
        kept = localsites.merge(old, {"checked": "2026-12-01", "verdict": "ok"}, "2026-12-01")
        # The verdict keeps its own day: the later look did not see it.
        self.assertEqual((kept["verdict"], kept["checked"], kept["tried"]),
                         ("gambling", "2026-10-01", "2026-12-01"))
        self.assertTrue(localsites.due({"checked": "2026-10-17", "verdict": "unread"}, "2026-10-17"))
        self.assertFalse(localsites.due({"checked": "2026-10-17", "verdict": "ok"}, "2026-10-20"))
        self.assertTrue(localsites.due({"checked": "2026-09-01", "verdict": "dead"}, "2026-10-17"))

    def test_a_look_that_concludes_nothing_never_undoes_a_withdrawal(self):
        old = {"checked": "2026-10-17", "verdict": "parked", "evidence": "parked domain"}
        kept = localsites.merge(old, {"checked": "2026-11-20", "verdict": "unread",
                                      "evidence": "HTTP 403"}, "2026-11-20")
        self.assertEqual((kept["verdict"], kept["checked"], kept["tried"]),
                         ("parked", "2026-10-17", "2026-11-20"))
        # The try counts as a look: not due again the next day.
        self.assertFalse(localsites.due(kept, "2026-11-21"))
        # A conclusive look replaces it.
        fresh = {"checked": "2026-11-20", "verdict": "ok"}
        self.assertEqual(localsites.merge(old, fresh, "2026-11-20"), fresh)

    def test_a_capped_run_looks_at_the_oldest_first(self):
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, os.path.dirname(localsites.CACHE_PATH)))
            sites = {"http://a.org": {"checked": "2026-01-02", "verdict": "ok"},
                     "http://b.org": {"checked": "2025-12-01", "verdict": "ok"},
                     "http://c.org": {"checked": "2026-01-01", "verdict": "unread"}}
            localsites.save_cache({"sites": sites}, tmp)
            looked = []
            real = localsites.targets
            localsites.targets = lambda root, codes=None: {u: ["Town of X"] for u in sites}
            try:
                localsites.check_all(tmp, workers=1, limit=2, log=lambda *a: None,
                                     check=lambda url, names, gate, today: (
                                         looked.append(url) or {"checked": today, "verdict": "ok"}))
            finally:
                localsites.targets = real
            self.assertEqual(sorted(looked), ["http://b.org", "http://c.org"])
        finally:
            shutil.rmtree(tmp)

    def test_a_run_stops_itself_on_its_time_budget(self):
        # The refresh of 2026-10-19: the check ran to its step's 45-minute
        # limit and was killed; threads still finishing saved the cache
        # after the next step had read it, and verify found 17 county files
        # stale. Now no address is opened once the budget is spent, and the
        # cache is saved once, with what was done.
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, os.path.dirname(localsites.CACHE_PATH)))
            sites = {f"http://{c}.org": {"checked": f"2026-01-0{i + 1}", "verdict": "ok"}
                     for i, c in enumerate("abcde")}
            localsites.save_cache({"sites": sites}, tmp)
            now = [0.0]
            looked, said = [], []

            def check(url, names, gate, today):
                looked.append(url)
                now[0] += 60.0           # each look takes a minute
                return {"checked": today, "verdict": "parked"}
            real = localsites.targets
            localsites.targets = lambda root, codes=None: {u: ["Town of X"] for u in sites}
            try:
                localsites.check_all(tmp, workers=1, log=said.append, check=check,
                                     max_seconds=150, clock=lambda: now[0], refresh=True)
            finally:
                localsites.targets = real
            # Opened at 0, 60 and 120 seconds; at 180 the budget is spent.
            self.assertEqual(looked, ["http://a.org", "http://b.org", "http://c.org"])
            saved = localsites.load_cache(tmp)["sites"]
            self.assertEqual([u for u, e in sorted(saved.items()) if e["verdict"] == "parked"],
                             looked)
            self.assertEqual(saved["http://d.org"], sites["http://d.org"])
            self.assertTrue(any("2 left for the next run" in line for line in said), said)
        finally:
            shutil.rmtree(tmp)

    def test_the_refresh_gives_the_check_a_budget_inside_its_step(self):
        import re
        with open(os.path.join(ROOT, ".github", "workflows", "refresh.yml"), encoding="utf-8") as handle:
            text = handle.read()
        step = text[text.index("- name: Look again at local governments' listed websites"):]
        step = step[:step.index("\n\n")]
        budget = float(re.search(r"--max-minutes (\d+(?:\.\d+)?)", step).group(1))
        limit = float(re.search(r"timeout-minutes: (\d+)", step).group(1))
        # Room for the looks already open when the budget is spent.
        self.assertLessEqual(budget, limit - 8)

    def test_the_build_warns_when_the_checks_grow_old(self):
        cache = {"sites": {"http://a.org": {"checked": "2026-10-17", "verdict": "ok"}}}
        self.assertFalse([p for p in localsites.problems(cache, {"http://a.org"}, today="2026-12-01")
                          if "days ago" in p])
        self.assertTrue([p for p in localsites.problems(cache, {"http://a.org"}, today="2026-12-20")
                         if "days ago" in p])

    def test_the_refresh_looks_at_the_local_sites_again(self):
        # Rule 39: domains keep lapsing; a one-off sweep goes stale.
        with open(os.path.join(ROOT, ".github", "workflows", "refresh.yml"), encoding="utf-8") as handle:
            self.assertIn("localgov --check-sites --limit", handle.read())

    def test_one_request_at_a_time_per_host(self):
        clock = [0.0]
        waits = []
        gate = localsites._Gate(interval=1.0, sleep=lambda s: (waits.append(s), clock.__setitem__(0, clock[0] + s)),
                                clock=lambda: clock[0])
        with gate.hold("www.a.org"):
            pass
        with gate.hold("a.org"):          # the same host, but for "www."
            pass
        with gate.hold("b.org"):
            pass
        self.assertEqual(waits, [1.0])

    def test_every_blocked_host_is_a_listed_website(self):
        addresses = set(localsites.targets(ROOT))
        self.assertEqual(localsites.stale_blocks(addresses), [])
        for key, (kind, day, seen) in overrides.BLOCKED_LOCAL_HOSTS.items():
            self.assertIn(kind, localsites.WITHDRAWN, key)
            self.assertRegex(day, r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(seen, key)

    def test_the_committed_cache_is_well_formed(self):
        cache = localsites.load_cache(ROOT)
        for url, entry in cache["sites"].items():
            self.assertIn(entry.get("verdict"), localsites.VERDICTS, url)
            self.assertRegex(entry.get("checked", ""), r"^\d{4}-\d{2}-\d{2}$", url)
            if entry["verdict"] in localsites.WITHDRAWN:
                self.assertTrue(entry.get("evidence"), url)

    def test_no_withdrawn_address_is_linked_on_a_county_page(self):
        cache = localsites.load_cache(ROOT)
        refused = {u for u, e in cache["sites"].items() if e["verdict"] in localsites.WITHDRAWN}
        page = counties.build_state("CT", ROOT, {})
        rows = [r for rows in page["governments"].values() for r in rows] + page["statewide"]
        rows += [r for u in page["unmatched"] for r in u["governments"]]
        self.assertFalse([r[3] for r in rows if r[3] in refused or localsites.blocked(r[3])])
        clinton = [r for r in rows if r[1] == "Town of Clinton"]
        self.assertTrue(clinton and clinton[0][3] == "" and clinton[0][7].startswith("gambling "))



class TestAreaNames(unittest.TestCase):
    """STATEGOV-20: Virginia's independent cities were headed in the
    Census's casing ("Alexandria city") and counted as counties."""

    def test_an_independent_city_is_named_as_its_state_names_it(self):
        self.assertEqual(county_areas.local_name("51510", "Alexandria city"), "City of Alexandria")
        self.assertEqual(county_areas.local_name("24510", "Baltimore city"), "Baltimore City")
        self.assertEqual(county_areas.local_name("29510", "St. Louis city"), "City of St. Louis")
        self.assertEqual(county_areas.local_name("32510", "Carson City"), "Carson City")
        self.assertEqual(county_areas.local_name("51059", "Fairfax County"), "Fairfax County")

    def test_virginia_counts_its_counties_and_its_cities_apart(self):
        page = counties.build_state("VA", ROOT, {})
        self.assertEqual(page["areaWords"]["count"], "95 counties and 38 independent cities")
        self.assertEqual(page["counties"]["51510"]["name"], "City of Alexandria")
        self.assertIn("City of Alexandria is an independent city", page["noCounty"]["51510"]["note"])
        self.assertEqual(counties.build_state("DE", ROOT, {})["areaWords"]["count"], "3 counties")

    def test_a_sentence_names_the_city_with_its_article_and_once(self):
        page = counties.build_state("MO", ROOT, {})
        note = page["noCounty"]["29510"]["note"]
        self.assertTrue(note.startswith("The City of St. Louis is an independent city"), note)
        self.assertNotIn("St Louis", note)
        self.assertTrue(page["stateNote"].startswith("The City of St. Louis "), page["stateNote"])
        self.assertIn("the City of St. Louis is", county_areas.directory_note("MO"))

    def test_a_county_named_like_a_city_keeps_its_county_word_on_the_map(self):
        # A bare "Richmond" on the Northern Neck read as the City of
        # Richmond; "Baltimore" beside Baltimore City as the city.
        labels = {st: {c["label"] for c in counties.build_state(st, ROOT, {})["counties"].values()}
                  for st in ("VA", "MD", "MO")}
        for st, want in (("VA", "Richmond County"), ("VA", "Fairfax County"), ("MD", "Baltimore County"),
                         ("MO", "St. Louis County"), ("VA", "Loudoun")):
            self.assertIn(want, labels[st], want)
        for st, bare in (("VA", "Richmond"), ("MD", "Baltimore"), ("MO", "St. Louis")):
            self.assertNotIn(bare, labels[st], bare)

    def test_a_county_is_named_on_the_map_only_where_its_name_fits(self):
        page = counties.build_state("WI", ROOT, {})
        for fips, county in page["counties"].items():
            self.assertEqual(county["label"], county["name"].replace(" County", ""))
            self.assertGreaterEqual(county["labelRoom"], 0)
        # A long name needs more room than a short one at the same point.
        self.assertGreater(counties.label_aspect("Fond du Lac"), counties.label_aspect("Iron"))


class TestCountyAreas(unittest.TestCase):
    """A county area with no county government says why (rule 71): the
    counties directory said Rhode Island had none while its page drew five
    counties and said nothing."""

    MAP = {"44001": {"name": "Bristol County"}, "44003": {"name": "Kent County"},
           "44005": {"name": "Newport County"}, "44007": {"name": "Providence County"},
           "44009": {"name": "Washington County"}}

    def test_an_area_without_a_county_government_must_be_explained(self):
        rows = {f: [["township", "Town of X"]] for f in self.MAP}
        self.assertEqual(county_areas.check("RI", self.MAP, rows), [])
        # Texas has a county government in every county: one missing is a
        # build error, not a blank.
        problems = county_areas.check("TX", {"48201": {"name": "Harris County"}},
                                      {"48201": [["special", "Harris County MUD 1"]]})
        self.assertEqual(len(problems), 1)
        self.assertIn("does not say why", problems[0])

    def test_an_explanation_that_no_longer_fits_fails(self):
        # The listing holds a county government after all.
        rows = {f: [["county", "County of X"]] if f == "44001" else [] for f in self.MAP}
        self.assertTrue(any("listing holds one" in p
                            for p in county_areas.check("RI", self.MAP, rows)))
        # The area is renamed on the map, or gone from it.
        renamed = dict(self.MAP, **{"44001": {"name": "Bristol Region"}})
        self.assertTrue(any("the map calls it" in p
                            for p in county_areas.check("RI", renamed, {})))
        self.assertTrue(any("not on the map" in p for p in county_areas.check(
            "RI", {f: v for f, v in self.MAP.items() if f != "44009"}, {})))
        # The government said to do the county's work is not in the listing.
        sf = {"06075": {"name": "San Francisco County"}}
        self.assertTrue(any("holds no 'City and County of San Francisco'" in p
                            for p in county_areas.check("CA", sf, {"06075": [["special", "X"]]})))

    def test_real_states_build_with_every_area_explained(self):
        for code in ("RI", "NY", "VA", "AK", "CT", "MA", "HI"):
            page = counties.build_state(code, ROOT, {})
            lacking = [f for f in page["counties"]
                       if not any(r[0] == "county" for r in page["governments"].get(f, []))]
            self.assertEqual(sorted(page["noCounty"]), sorted(lacking), code)
            self.assertTrue(page["stateNote"], code)
        tx = counties.build_state("TX", ROOT, {})
        self.assertEqual(tx["noCounty"], {})
        self.assertEqual(tx["stateNote"], "")

    def test_a_borough_with_no_governments_points_to_where_they_are_listed(self):
        page = counties.build_state("NY", ROOT, {})
        bronx = page["noCounty"]["36005"]
        self.assertEqual(bronx["filed"], "36061")
        self.assertIn("the Bronx", bronx["note"])
        self.assertIn("under New York County (Manhattan)", bronx["note"])
        self.assertEqual(page["governments"].get("36005", []), [])

    def test_a_state_names_its_own_areas(self):
        self.assertEqual(county_areas.words("LA")[:2], ("parish", "parishes"))
        self.assertEqual(county_areas.words("CT")[2], "Planning regions")
        self.assertEqual(county_areas.words("TX"), county_areas.DEFAULT_WORDS)

    def test_the_guide_counts_what_the_table_holds(self):
        from kyc import government_text
        text = " ".join(b[1] for s in government_text.LOCAL["sections"] if s["id"] == "counties"
                        for b in s["blocks"] if b[0] == "p")
        ma = [f for f in county_areas.AREAS if f.startswith("25")]
        va = [f for f, e in county_areas.AREAS.items()
              if f.startswith("51") and e[1] == county_areas.INDEPENDENT]
        self.assertEqual((len(ma), len(va)), (9, 38))
        self.assertIn("nine of Massachusetts's fourteen counties", text)
        self.assertIn("Virginia's 38", text)

    def test_virginias_one_school_district_is_the_one_the_guide_names(self):
        # The guide said Virginia had only dependent systems while its own
        # map and the directory counted one independent school district.
        from kyc import government_maps, government_text
        schools = [(fips, g["name"]) for fips, e in localgov.load("VA", ROOT)["counties"].items()
                   for g in e["governments"] if g["type"] == "school"]
        self.assertEqual(schools, [("51710", "Eastern Virginia Medical School")])
        self.assertEqual(census.load_cache(ROOT)["states"]["VA"]["school"], 1)
        text = " ".join(b[1] for s in government_text.LOCAL["sections"] if s["id"] == "schools"
                        for b in s["blocks"] if b[0] == "p")
        self.assertNotIn("North Carolina, Virginia", text)
        self.assertIn("Eastern Virginia Medical School", text)
        self.assertIn("Eastern Virginia Medical School", government_maps.COUNT_NOTES[("VA", "school")])


class TestCities(unittest.TestCase):
    """A place is joined to its government by name only where the join is
    one to one; anything else is reported and left unjoined (rule 51)."""

    def test_names_reduce_alike_on_both_sides(self):
        same = [("CITY OF JERSEY CITY", "Jersey City"), ("CITY OF THE COLONY", "The Colony"),
                ("TOWN OF CITY OF CREEDE", "City of Creede"), ("CITY OF ST. GEORGE", "St. George"),
                ("CITY OF SAINT PAUL", "St. Paul"),
                ("CITY OF EL PASO DE ROBLES", "El Paso de Robles (Paso Robles)"),
                ("CITY OF LA CANADA FLINTRIDGE", "La Cañada Flintridge")]
        for listed, drawn in same:
            self.assertEqual(counties.city_key(listed), counties.city_key(drawn), (listed, drawn))
        # Forms after the name count only in the looser pass.
        self.assertNotEqual(counties.city_key("CITY OF PHENIX"), counties.city_key("Phenix City"))
        self.assertEqual(counties.city_key("CITY OF PHENIX", True), counties.city_key("Phenix City", True))
        self.assertEqual(counties.city_key("UNIFIED GOVERNMENT OF ATHENS-CLARKE COUNTY", True),
                         counties.city_key("Athens-Clarke County unified government", True))

    def test_a_join_is_one_to_one_or_not_made(self):
        places = [("p1", "springfield", "c1"), ("p2", "springfield", "c2"),
                  ("p3", "salem", "c1"), ("p4", "salem", "c1"), ("p5", "dover", "c3")]
        governments = [("g1", "springfield", "c1"), ("g2", "springfield", "c2"),
                       ("g3", "salem", "c1"), ("g5", "dover", "c9")]
        joined = counties.match_cities(places, governments)
        # A shared name is told apart by the county the point lies in; a
        # name and a county shared by two places is not told apart at all;
        # a name one place and one government share is joined wherever its
        # government is filed.
        self.assertEqual(joined, {"p1": "g1", "p2": "g2", "p5": "g5"})

    def test_two_governments_of_one_name_in_one_county_join_neither(self):
        joined = counties.match_cities([("p1", "pewaukee", "55133")],
                                       [("g1", "pewaukee", "55133"), ("g2", "pewaukee", "55133")])
        self.assertEqual(joined, {})

    def test_the_legal_form_tells_a_city_from_a_village_of_one_name(self):
        self.assertEqual(counties.listing_form("CITY OF PEWAUKEE"), "city")
        self.assertEqual(counties.listing_form("VILLAGE OF PEWAUKEE"), "village")
        self.assertEqual(counties.listing_form("METRO TOWNSHIP OF KEARNS"), "")
        page = counties.build_state("WI", ROOT, {})
        listing = localgov.load("WI", ROOT)
        pewaukee = {c[2]: listing["counties"][c[5][0]]["governments"][c[5][1]]["census"]
                    for c in page["cities"].values() if c[3] == "Pewaukee" and c[5]}
        self.assertEqual(pewaukee, {"city": "CITY OF PEWAUKEE", "village": "VILLAGE OF PEWAUKEE"})

    def test_every_join_in_every_state_names_a_municipal_government_once(self):
        from kyc.government_maps import STATES
        problems = []
        maps = counties.build(ROOT, problems=problems)
        self.assertEqual(sorted(maps), sorted(STATES))
        for code, page in maps.items():
            refs = [tuple(c[5]) for c in page["cities"].values() if c[5]]
            self.assertEqual(len(refs), len(set(refs)), code)
            listing = localgov.load(code, ROOT)
            # A curated join may name the town or county government the
            # listing files the place's government as (Mount Lebanon's
            # township, Echols County); every other is a municipal one.
            from kyc import overrides
            curated = {tuple(c[5]) for pid, c in page["cities"].items()
                       if c[5] and pid in overrides.PLACE_GOVERNMENTS}
            for fips, i in refs:
                kind = listing["counties"][fips]["governments"][i]["type"]
                self.assertEqual(kind, "municipal" if (fips, i) not in curated else kind,
                                 (code, fips, i))
            width, height = page["viewBox"][2], page["viewBox"][3]
            for pid, (x, y, kind, name, county, ref, status) in page["cities"].items():
                self.assertIn(status, ("", "I", "N", "B", "F"), (code, name))
                self.assertTrue(0 <= x <= width and 0 <= y <= height, (code, name))
                self.assertTrue(not county or county in page["counties"], (code, name))
            # Every place left unjoined is in what the build reports.
            unjoined = [c[3] for c in page["cities"].values() if not c[5]]
            if unjoined:
                report = " ".join(p for p in problems if p.startswith(f"{code}: "))
                for name in unjoined[:12]:
                    self.assertIn(name, report, code)
        self.assertNotIn("problems", maps["TX"])

    def test_a_city_its_consolidated_government_governs_is_joined_to_it(self):
        # Kansas City and Baton Rouge read "a place incorporated since 2022
        # is not in it" though both are 19th-century cities whose government
        # is the one county_areas.AREAS names.
        for code, pid, area in (("KS", "2036000", "20209"), ("LA", "2205000", "22033"),
                                ("GA", "1332528", "13239")):
            page = counties.build_state(code, ROOT, {})
            fips, i = page["cities"][pid][5]
            self.assertEqual(page["governments"][fips][i][1], county_areas.AREAS[area][2], code)
            self.assertEqual(page["consolidatedPlaces"].get(pid), area)
        # Not every place in such an area: St. George incorporated in 2024.
        la = counties.build_state("LA", ROOT, {})
        self.assertIsNone(la["cities"]["2267303"][5])

    def test_every_curated_join_holds_in_the_committed_data(self):
        from kyc import overrides
        by_state = {}
        for pid in overrides.PLACE_GOVERNMENTS:
            code = next(c for c, s in localgov_states().items() if pid[:2] == s)
            by_state.setdefault(code, []).append(pid)
        for code, pids in by_state.items():
            problems = []
            page = counties.build(ROOT, [code], problems)[code]
            listing = localgov.load(code, ROOT)
            for pid in pids:
                ref = page["cities"][pid][5]
                self.assertIsNotNone(ref, (code, pid, problems))
                gov = listing["counties"][ref[0]]["governments"][ref[1]]
                self.assertEqual((gov["id"], gov["name"]), overrides.PLACE_GOVERNMENTS[pid][:2])
            self.assertFalse([p for p in problems if "curated" in p], problems)
        # A government the place replaced is never joined (rule 59).
        for code, name in (("WI", "Rib Mountain"), ("WI", "Lisbon"), ("MN", "Baldwin"), ("MN", "Empire")):
            page = counties.build_state(code, ROOT, {})
            self.assertTrue(all(c[5] is None for c in page["cities"].values() if c[3] == name), name)

    def test_a_curated_join_that_no_longer_fits_is_refused(self):
        listing = {"counties": {"56007": {"governments": [
            {"id": "X1", "name": "Town of Grand Encampment", "type": "municipal"}]}}}
        rows = {"5624750": [0, 0, "town", "Encampment", "56007", None, ""]}
        out, problems = counties.curated_joins("WY", rows, listing, {})
        self.assertEqual(out, {})                     # the listing's id is not the one recorded
        self.assertIn("not joined", problems[0])
        listing["counties"]["56007"]["governments"][0]["id"] = "51200400500000"
        out, problems = counties.curated_joins("WY", rows, listing, {})
        self.assertEqual((out, problems), ({"5624750": (("56007", 0), "listed")}, []))
        rows["5624750"][4] = "56001"                  # the place in another county
        out, problems = counties.curated_joins("WY", rows, listing, {})
        self.assertEqual(out, {})
        rows["5624750"][4] = "56007"
        out, problems = counties.curated_joins("WY", rows, listing, {"5624750": ("56007", 0)})
        self.assertIn("no longer needed", problems[0])  # the name join found it on its own

    def test_hawaii_has_counties_and_no_incorporated_place(self):
        page = counties.build_state("HI", ROOT, {})
        self.assertEqual(page["cities"], {})
        self.assertTrue(page["counties"])

    def test_a_consolidated_remainder_keeps_its_own_name(self):
        import json
        with open(os.path.join(ROOT, counties.CITIES_DIR, "ct.json"), encoding="utf-8") as handle:
            places = {p["id"]: p for p in json.load(handle)["places"]}
        self.assertEqual((places["0947515"]["name"], places["0947515"]["kind"]), ("Milford city", "balance"))

    def test_the_place_file_names_its_legal_forms_from_the_census(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fetch_local_maps as F
        self.assertEqual(F.legal_form({"GEOID": "1", "NAME": "Abbott", "NAMELSAD": "Abbott city"}),
                         ("Abbott", "city"))
        self.assertEqual(F.legal_form({"GEOID": "2", "NAME": "Milford city (balance)",
                                       "NAMELSAD": "Milford city (balance)"}), ("Milford city", "balance"))
        self.assertEqual(F.legal_form({"GEOID": "3", "NAME": "Macon-Bibb County",
                                       "NAMELSAD": "Macon-Bibb County"}), ("Macon-Bibb County", ""))
        # Illinois writes some subdivisions' form before the name.
        self.assertEqual(F.legal_form({"GEOID": "4", "NAME": "17", "NAMELSAD": "Precinct 17"}),
                         ("Precinct 17", "Precinct"))
        with self.assertRaises(SystemExit):
            F.legal_form({"GEOID": "5", "NAME": "Abbott", "NAMELSAD": "Elm city"})
        # The point is inside the largest piece, not an outlying island.
        main = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)]
        island = [(1.0, 1.0), (1.001, 1.0), (1.001, 1.001), (1.0, 1.001)]
        lon, lat = F.point_of([island, main])
        self.assertTrue(0 < lon < 0.1 and 0 < lat < 0.1, (lon, lat))


class TestReviewOfTheCities(unittest.TestCase):
    """What the review of the cities layer found (PR #48)."""

    def test_a_place_on_a_county_line_is_in_the_county_the_census_puts_it(self):
        # Against the drawn 1:5,000,000 lines these four sat in the county
        # next door; the tool now finds the county at 1:500,000.
        expected = {"PA": {"4249504": "42045", "4227112": "42031", "4271976": "42005"},
                    "ID": {"1642760": "16057"}}
        for code, places in expected.items():
            page = counties.build_state(code, ROOT, {})
            for pid, county in places.items():
                self.assertEqual(page["cities"][pid][4], county, (code, pid))

    def test_a_city_parish_is_a_legal_form(self):
        self.assertEqual(counties.city_key("CITY-PARISH OF LAFAYETTE"), counties.city_key("Lafayette"))
        page = counties.build_state("LA", ROOT, {})
        listing = localgov.load("LA", ROOT)
        ref = page["cities"]["2240735"][5]
        self.assertEqual(listing["counties"][ref[0]]["governments"][ref[1]]["census"],
                         "CITY-PARISH OF LAFAYETTE")

    def test_a_place_carries_the_census_functional_status(self):
        page = counties.build_state("KY", ROOT, {})
        self.assertEqual(page["cities"]["2148000"][6], "N")        # Louisville, since 2003
        self.assertIsNone(page["cities"]["2148000"][5])
        self.assertEqual(counties.build_state("TX", ROOT, {})["cities"]["4835000"][6], "")   # Houston

    def test_a_hole_touching_the_outer_line_is_still_a_hole(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fetch_local_maps as F
        # A square town with a pocket of unincorporated land that touches
        # its outer line at the pocket's first vertex (Triadelphia, WV). As
        # in a shapefile, the outer ring runs clockwise and the hole counter.
        outer = [(0.0, 0.0), (0.0, 0.01), (0.01, 0.01), (0.01, 0.0)]
        pocket = [(0.0, 0.0), (0.008, 0.002), (0.008, 0.008), (0.002, 0.008)]
        lon, lat = F.point_of([outer, pocket])
        inside_town = F._inside_ring(outer, lon, lat) and not F._inside_ring(pocket, lon, lat)
        self.assertTrue(inside_town, (lon, lat))

    def test_every_place_point_has_a_county(self):
        import json
        from kyc.government_maps import STATES
        for code in STATES:
            with open(os.path.join(ROOT, counties.CITIES_DIR, f"{code.lower()}.json"), encoding="utf-8") as handle:
                for place in json.load(handle)["places"]:
                    self.assertTrue(place.get("county", "").startswith(place["id"][:2]), (code, place["name"]))

class TestTowns(unittest.TestCase):
    """A town or township is joined on the Census code the listing gives it,
    the name only a cross-check; never placed by its name alone (rule 60)."""

    def test_names_that_share_a_code_agree(self):
        same = [("CHARTER TOWNSHIP OF ORION", "Orion"), ("TOWNSHIP OF NUMBER 3", "Township 3"),
                ("TOWNSHIP OF CENTER", "Center-District 1"), ("TOWNSHIP OF SULLIVAN", "Sullivant"),
                ("TOWNSHIP OF ST MARIE", "Ste. Marie"), ("PLANTATION OF THE FORKS", "The Forks"),
                ("TOWN OF HARTS LOCATION", "Hart's Location"), ("TOWNSHIP OF MT JOY", "Mount Joy"),
                ("TOWNSHIP OF BRANDYWINE CIVIL", "Brandywine"),
                ("TOWNSHIP OF ORANGE CITY", "City of Orange")]
        for listed, drawn in same:
            self.assertTrue(counties.same_town(listed, drawn), (listed, drawn))
        for listed, drawn in [("TOWN OF MADISON", "Fitchburg"), ("TOWNSHIP OF NUMBER 3", "Township 13"),
                              ("TOWN OF ADA", "Adams")]:
            self.assertFalse(counties.same_town(listed, drawn), (listed, drawn))

    def _build(self, governments, subdivisions):
        listing = {"counties": {"55073": {"name": "Marathon", "governments": governments}}}
        cities = {"subdivisions": subdivisions}

        class Fit:
            height = 100
            def __call__(self, p):
                return (p[0], p[1])

        class Albers:
            def raw(self, lon, lat):
                return (lon, lat)

        drawn = {"55073": ([[(0, 0), (100, 0), (100, 100), (0, 100)]], (0, 0, 100, 100))}
        return counties.build_towns("WI", cities, listing, Albers(), Fit(), drawn)

    def test_a_town_joins_on_its_code_and_is_never_placed_by_name(self):
        subs = [{"id": "5507367320", "county": "55073", "code": "67320", "name": "Rib Mountain",
                 "kind": "village", "point": [10, 10]},
                {"id": "5507300100", "county": "55073", "code": "00100", "name": "Bern",
                 "kind": "town", "point": [20, 20]}]
        govs = [{"type": "township", "name": "Town of Rib Mountain", "census": "TOWN OF RIB MOUNTAIN",
                 "cousub": "67325"},
                {"type": "township", "name": "Town of Bern", "census": "TOWN OF BERN", "cousub": "00100"},
                {"type": "municipal", "name": "City of Wausau", "census": "CITY OF WAUSAU"}]
        rows, problems = self._build(govs, subs)
        # The Town of Rib Mountain's code is on no subdivision: the village
        # that replaced it shares its name and is not its government.
        self.assertEqual(sorted(rows), ["5507300100"])
        self.assertEqual(rows["5507300100"][3:], ["Bern", "55073", ["55073", 1], ""])
        self.assertIn("Town of Rib Mountain", " ".join(problems))

    def test_a_code_whose_names_disagree_is_not_placed(self):
        subs = [{"id": "5502548000", "county": "55073", "code": "48000", "name": "Madison",
                 "kind": "city", "point": [10, 10]}]
        govs = [{"type": "township", "name": "Town of Burke", "census": "TOWN OF BURKE", "cousub": "48000"}]
        rows, problems = self._build(govs, [dict(subs[0], id="5507348000")])
        self.assertEqual(rows, {})
        self.assertIn("names disagree", " ".join(problems))

    def test_two_governments_on_one_code_place_neither(self):
        subs = [{"id": "5507300100", "county": "55073", "code": "00100", "name": "Bern",
                 "kind": "town", "point": [20, 20]}]
        govs = [{"type": "township", "name": "Town of Bern", "census": "TOWN OF BERN", "cousub": "00100"},
                {"type": "township", "name": "Town of Bern", "census": "TOWN OF BERN", "cousub": "00100"}]
        rows, problems = self._build(govs, subs)
        self.assertEqual(rows, {})
        self.assertIn("claimed by two governments", " ".join(problems))

    def test_every_town_in_every_state_is_its_governments_own_code(self):
        from kyc.government_maps import STATES
        problems = []
        maps = counties.build(ROOT, problems=problems)
        placed = 0
        for code in STATES:
            page = maps[code]
            listing = localgov.load(code, ROOT)
            refs = [tuple(t[5]) for t in page["towns"].values()]
            self.assertEqual(len(refs), len(set(refs)), code)
            width, height = page["viewBox"][2], page["viewBox"][3]
            for sid, (x, y, kind, name, county, ref, status) in page["towns"].items():
                self.assertIn(status, ("", "B", "C", "G", "I"), (code, sid))
                gov = listing["counties"][ref[0]]["governments"][ref[1]]
                self.assertEqual(gov["type"], "township", (code, sid))
                self.assertEqual(ref[0] + gov["cousub"], sid, (code, sid))
                self.assertTrue(counties.same_town(gov["census"], name), (code, sid))
                self.assertTrue(0 <= x <= width and 0 <= y <= height, (code, name))
                placed += 1
            # A state with town governments places nearly all of them, on a
            # ring or on a place's point (overrides.PLACE_GOVERNMENTS); what
            # it does not place is in what the build reports.
            towns = [g for e in listing["counties"].values() for g in e["governments"]
                     if g["type"] == "township"]
            on_places = sum(1 for c in page["cities"].values() if c[5] and
                            listing["counties"][c[5][0]]["governments"][c[5][1]]["type"] == "township")
            if len(towns) != len(page["towns"]) + on_places:
                self.assertTrue(any(p.startswith(f"{code}: ") and "town or township" in p
                                    for p in problems), code)
            if not towns:
                self.assertEqual(page["towns"], {}, code)
        self.assertGreater(placed, 0)


class TestReviewOfTheTowns(unittest.TestCase):
    """What the review of the towns layer found (PR #49)."""

    def _tools(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fetch_district_maps as M
        import fetch_local_maps as F
        return M, F

    def test_a_form_before_the_name_stays_in_it(self):
        _, F = self._tools()
        self.assertEqual(F.legal_form({"GEOID": "1", "NAME": "1", "NAMELSAD": "Township 1"}),
                         ("Township 1", "Township"))
        # "Precinct P" starts with "P": only a whole word is a name.
        self.assertEqual(F.legal_form({"GEOID": "2", "NAME": "P", "NAMELSAD": "Precinct P"}),
                         ("Precinct P", "Precinct"))
        page = counties.build_state("KS", ROOT, {})
        numbered = [t[3] for t in page["towns"].values() if t[3][:1].isdigit()]
        self.assertEqual(numbered, [])

    def test_a_hole_is_decided_by_its_winding(self):
        M, _ = self._tools()
        outer = [(0, 0), (0, 10), (10, 10), (10, 0)]                 # clockwise
        piece = [(10, 0), (10, 5), (15, 5), (15, 0)]                 # clockwise: a separate piece
        hole = [(0, 0), (8, 2), (8, 8), (2, 8)]                      # counter-clockwise: a hole
        largest, holes = M.largest_piece([outer, piece, hole])
        self.assertEqual((largest, holes), (outer, [hole]))

    def test_a_label_point_in_a_hole_is_moved_out(self):
        M, _ = self._tools()
        outer = [(0.0, 0.0), (0.0, 0.01), (0.01, 0.01), (0.01, 0.0)]
        pocket = [(0.004, 0.004), (0.006, 0.004), (0.006, 0.006), (0.004, 0.006)]
        lon, lat, moved = M.main_piece_point([outer, pocket], 0.005, 0.005)
        self.assertTrue(moved)
        self.assertFalse(0.004 < lon < 0.006 and 0.004 < lat < 0.006, (lon, lat))

    def test_a_subdivision_the_census_says_does_not_govern_gets_no_government(self):
        page = counties.build_state("SD", ROOT, {})
        self.assertNotIn("4603543140", page["towns"])               # Mitchell, unorganized territory
        problems = []
        counties.build(ROOT, ["SD"], problems=problems)
        self.assertIn("Township of Mitchell", " ".join(problems))

    def test_a_town_listed_under_another_county_is_reported_so(self):
        problems = []
        counties.build(ROOT, ["CT"], problems=problems)
        report = " ".join(problems)
        self.assertIn("Town of Pomfret (listed under 09180, its subdivision is in 09150)", report)
        self.assertNotIn("no county subdivision of their code: Town of Pomfret", report)

    def test_a_town_carries_its_functional_status(self):
        page = counties.build_state("KS", ROOT, {})
        self.assertEqual(page["towns"]["2011924200"][6], "I")         # Fowler Township, inactive

if __name__ == "__main__":
    unittest.main()
