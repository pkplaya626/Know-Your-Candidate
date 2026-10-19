"""A sitting member's education, careers, platform, contact page and
district offices, each from a source tied to them by id (kyc/members.py,
rule 86).

The rosters' typed Education, Previous Professions and "Policy Focus &
Platforms" columns reached 537 member profiles with no source and in uneven
words: one member's platform read "Anti-abortion legislation", four others'
"Pro-life advocacy" (TRUST-05). The markup below is trimmed from the pages
as read on 2026-10-18, keeping the shapes that broke a first reading: an
"On The Issues" link that leads to /legislative-work, whose own children are
a voting record and legislation (Matsui); an issues index with sub-issues
one level further down; a site whose only list of issues is its menu
(Boozman); a banner linked under the issues path that names the President
(Van Hollen)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import enrich, members, validate  # noqa: E402
from kyc.normalize import UNKNOWN  # noqa: E402

OTHERS = {"full": {"donald trump", "bill cassidy", "al green"},
          "surnames": {"trump", "cassidy", "green"}, "bare": {"trump"}}

DIRECTORY = (
    "<html><body><pre>\r\n SECOND DISTRICT\r\n\r\n"
    "RICK LARSEN, Democrat, of Everett, WA; born in Arlington, WA, June 15, \r\n"
    "1965; education: B.A., Pacific Lutheran University, Tacoma, WA, 1987; \r\n"
    "M.P.A., University of Minnesota, Minneapolis, MN, 1990; professional \r\n"
    "history: economic development official, Port of Everett, WA, 1990-\r\n"
    "91; member, Snohomish County Council, 1998-2001; military service: U.S. \r\n"
    "Army Reserve, 1985-89; election history: elected to the 107th Congress \r\n"
    "on November 7, 2000; reelected to each succeeding Congress.\r\n\r\n"
    "                          Congressional Office\r\n"
    "                        https://larsen.house.gov\r\n \r\n"
    "2163 Rayburn House Office Building, Washington, DC        (202) 225-2605\r\n"
    "\r\n*  *  *\r\n\r\n THIRD DISTRICT\r\n\r\n"
    "MARIO DIAZ-BALART, Republican, of Miami, FL; born in Fort Lauderdale, FL, \r\n"
    "September 25, 1961; education: University of South Florida; election \r\n"
    "history: elected to the 108th Congress.\r\n\r\n"
    "                          Congressional Office\r\n"
    "                        https://mariodiazbalart.house.gov\r\n"
    "\r\n*  *  *\r\n\r\n"
    "SOMEONE ELSE, Democrat, of Nowhere; born in Nowhere; education: B.A., X \r\n"
    "College; election history: elected.\r\n\r\n"
    "                          Congressional Office\r\n"
    "                        https://pou.house.gov\r\n</pre></body></html>"
)


def member(**extra):
    profile = {"id": "L000560", "name": "Rick Larsen", "chamber": "House", "state": "WA",
               "officeLabel": "House • WA-2", "isCandidate": False,
               "website": "https://larsen.house.gov", "wikipedia": "Rick Larsen",
               "education": "", "previous_professions": "", "platforms": "",
               "quality": {"education": UNKNOWN, "previous_professions": UNKNOWN,
                           "platforms": UNKNOWN}}
    profile.update(extra)
    return profile


class TestTheDirectory(unittest.TestCase):
    """The Official Congressional Directory prints each member's education
    and professional history under labels, and the office web address under
    the paragraph - the join to congress-legislators' record, never a name."""

    def test_an_entry_is_read_in_its_own_words(self):
        entries = members.directory_entries(DIRECTORY)
        self.assertEqual([e[0] for e in entries], ["https://larsen.house.gov",
                                                   "https://mariodiazbalart.house.gov",
                                                   "https://pou.house.gov"])
        site, name, fields = entries[0]
        self.assertEqual(name, "RICK LARSEN")
        self.assertEqual(fields["education"], "B.A., Pacific Lutheran University, Tacoma, WA, "
                                              "1987; M.P.A., University of Minnesota, "
                                              "Minneapolis, MN, 1990")
        # A range broken at its hyphen across two lines is one range.
        self.assertIn("Port of Everett, WA, 1990-91;", fields["professional history"])
        facts = members.directory_facts(fields)
        self.assertTrue(facts["careers"].endswith("military service: U.S. Army Reserve, 1985-89"))
        self.assertNotIn("elected", facts["careers"])

    def test_an_entry_joins_on_the_official_site_and_must_carry_the_surname(self):
        entries = members.directory_entries(DIRECTORY)
        people = [member(), member(id="D000600", name="Mario Diaz-Balart",
                                   website="https://mariodiazbalart.house.gov"),
                  member(id="P000621", name="Nellie Pou", website="https://pou.house.gov"),
                  member(id="X000001", name="Nobody Listed", website="https://nobody.house.gov")]
        found, problems, report = members.match_directory(people, entries)
        self.assertEqual(set(found), {"L000560", "D000600"})
        self.assertEqual(found["D000600"]["education"], "University of South Florida")
        self.assertNotIn("careers", found["D000600"])
        # The address is Pou's and the paragraph is someone else's: nothing taken.
        self.assertEqual(len(problems), 1)
        self.assertIn("P000621", problems[0])
        # Who joined nothing is reported, not silently left without careers.
        self.assertEqual(report["absent"], ["X000001 (Nobody Listed)"])
        self.assertEqual(report["unclaimed"], ["https://pou.house.gov (SOMEONE ELSE)"])

    def test_a_label_the_directory_prints_without_its_semicolon(self):
        # Sam Graves's entry runs "... 1994-2000 election history: elected
        # to the 107th Congress ..." with no "; " before the label, and the
        # election record ran into his careers.
        text = ("SAM GRAVES, Republican, of Tarkio, MO; born in Tarkio, November 7, 1963;\r\n"
                "education: B.S., University of Missouri, Columbia, MO, 1986;\r\n"
                "professional history: farmer; member, Missouri House of Representatives, \r\n"
                "1992-93; member, Missouri State Senate, 1994-2000 election history: elected \r\n"
                "to the 107th Congress on November 7, 2000; reelected to each succeeding \r\n"
                "Congress.\r\n\r\n                          Congressional Office\r\n"
                "                        https://graves.house.gov\r\n")
        _, _, fields = members.directory_entries(text)[0]
        facts = members.directory_facts(fields)
        self.assertEqual(facts["careers"], "farmer; member, Missouri House of Representatives, "
                                           "1992-93; member, Missouri State Senate, 1994-2000")
        self.assertTrue(fields["election history"].startswith("elected to the 107th Congress"))

    def test_an_address_that_leads_to_the_members_site_joins(self):
        # The Directory prints dingell.house.gov, which leads to the
        # debbiedingell.house.gov congress-legislators lists (2026-10-18).
        text = ("DEBBIE DINGELL, Democrat, of Dearborn, MI; born in Detroit, MI; education: "
                "B.S., Georgetown University; professional history: president, General Motors "
                "Foundation; election history: elected.\r\n\r\n"
                "                          Congressional Office\r\n"
                "                        https://dingell.house.gov\r\n")
        entries = members.directory_entries(text)
        dingell = member(id="D000624", name="Debbie Dingell",
                         website="https://debbiedingell.house.gov")
        found, _, report = members.match_directory([dingell], entries)
        self.assertEqual(found, {})
        self.assertEqual(report["absent"], ["D000624 (Debbie Dingell)"])
        found, _, report = members.match_directory(
            [dingell], entries, resolve=lambda url: "https://debbiedingell.house.gov/")
        self.assertEqual(found["D000624"]["careers"], "president, General Motors Foundation")
        self.assertEqual(found["D000624"]["leadsTo"], "https://debbiedingell.house.gov/")
        self.assertEqual(report, {"absent": [], "unclaimed": []})
        members.apply_cache([dingell], {"directory": {"byId": found}})
        self.assertEqual(dingell["fieldSources"]["previous_professions"], "congressional-directory")
        # An address that leads somewhere else joins no one.
        found, _, _ = members.match_directory(
            [dingell], entries, resolve=lambda url: "https://example.com/")
        self.assertEqual(found, {})

    def test_a_spanish_form_name_is_printed_with_its_first_family_name(self):
        self.assertTrue(members.printed_as("Pablo José Hernández Rivera", "PABLO JOSE HERNANDEZ"))
        self.assertTrue(members.printed_as("Cindy Hyde-Smith", "CINDY HYDE-SMITH"))
        self.assertFalse(members.printed_as("Nellie Pou", "SOMEONE ELSE"))


ISSUES_INDEX = """<html><body><nav><a href="/issues">Issues</a>
<a href="/issues/health">Health</a></nav><main><h1>Issues</h1>
<a href="/issues/health">Health Care</a>
<a href="/issues/health/medicare">Medicare</a>
<a href="/issues/veterans">Veterans</a>
<a href="/issues/trumps-betrayal">News Alert: Fact Sheet on Trump’s Betrayal</a>
<a href="/issues/green-energy">Green Energy</a>
<a href="/issues/ricks-work">Rick's Legislation</a>
<a href="/issues/sponsored">Links to Sponsored Legislation</a>
<a href="/issues/women">Women's Issues</a>
<a href="#main">Skip to Content</a>
<a href="https://elsewhere.example/issues/x">Elsewhere</a>
</main></body></html>"""

MATSUI = """<html><body><h1>Legislative Work</h1>
<a href="/legislative-work/voting-record">Voting Record</a>
<a href="/legislative-work/legislation">Legislation</a>
<a href="/legislative-work/infrastructure-act">Infrastructure Investment and Jobs Act</a>
<a href="/legislative-work/flood">Flood Protection Funding</a>
<a href="/legislative-work/appropriations">Appropriations and Community Project Funding</a>
<a href="/issues/economy-and-jobs">Economy and Jobs</a>
<a href="/issues/health-care">Health Care</a>
<a href="/issues/flood-protection">Flood Protection</a>
</body></html>"""

BOOZMAN = """<html><body><ul class="nav">
<li><a href="/public/index.cfm/about">About</a><ul>
  <li><a href="/public/index.cfm/biography">Biography</a></li>
  <li><a href="/public/index.cfm/voting-record">Voting Record</a></li></ul></li>
<li><a href="/public/index.cfm/issues">Issues <span>Toggle submenu</span></a><ul>
  <li><a href="/public/index.cfm/agriculture_1">Agriculture</a></li>
  <li><a href="/public/index.cfm/energy_1">Energy &amp; Conservation</a></li>
  <li><a href="/public/index.cfm/health-care-reform">Health Care</a></li>
  <li><a href="https://elsewhere.example/x">Elsewhere</a></li>
  <li><a href="/public/index.cfm/veterans-affairs1">Veterans Affairs</a></li></ul></li>
</ul></body></html>"""


class TestTheIssuesTheirSiteLists(unittest.TestCase):
    """Rule 38's reading, on an official site: one level, the page's own
    words, nothing that names the member or anyone else."""

    def page(self, markup):
        return enrich.parse_page(markup)

    def test_an_index_lists_its_issue_pages_one_level_down_once_each(self):
        items = members.listed_issues(self.page(ISSUES_INDEX), "https://larsen.house.gov/issues",
                                      "Rick Larsen", OTHERS)
        # "Health" and "Health Care" are one page; Medicare is a sub-point;
        # the banner names the President, "Rick's" the member, and the
        # sponsored-legislation link is furniture. "Green Energy" names no one.
        self.assertEqual(items, ["Health", "Veterans", "Green Energy", "Women's Issues"])

    def test_pages_filed_under_an_issues_path_beat_pages_merely_below_the_index(self):
        items = members.listed_issues(self.page(MATSUI),
                                      "https://matsui.house.gov/legislative-work",
                                      "Doris Matsui", OTHERS)
        self.assertEqual(items, ["Economy and Jobs", "Health Care", "Flood Protection"])

    def test_a_site_whose_only_list_is_its_menu(self):
        items = members.menu_issues(BOOZMAN, "https://www.boozman.senate.gov/public/",
                                    "https://www.boozman.senate.gov/public", "John Boozman", OTHERS)
        self.assertEqual(items, ["Agriculture", "Energy & Conservation", "Health Care",
                                 "Veterans Affairs"])

    def test_a_menu_built_of_divs(self):
        # Senator Blackburn's "Issues" is a link in a toggle beside a
        # collapsed panel of issue links; no list element anywhere.
        markup = (
            '<div class="menu-item"><a href="/about">About Marsha</a></div>'
            '<div class="menu-item dropdown"><div class="menu-toggle"><a href="/issues">Issues</a>'
            '<button>Toggle Submenu</button></div><div class="collapse"><div class="panel">'
            '<div class="menu-item"><a href="/agriculture">Agriculture</a></div>'
            '<div class="menu-item"><a href="/china">China</a></div>'
            '<div class="menu-item"><a href="/health-care">Health Care</a></div>'
            '<div class="menu-item"><a href="/protecting-life">Protecting Life</a></div>'
            '</div></div></div>'
            '<div class="menu-item"><a href="/news">Newsroom</a></div>')
        site = "https://www.blackburn.senate.gov"
        self.assertEqual(members.menu_issues(markup, site + "/", site, "Marsha Blackburn", OTHERS),
                         ["Agriculture", "China", "Health Care", "Protecting Life"])
        # A menu labelled "Policy Issues" (Ocasio-Cortez's), and one whose
        # toggle reads "Open/Close Issues" (Jeffries's).
        for label in ("Policy Issues", "Open/Close Issues"):
            menu = (f'<ul><li><a href="#">{label}</a><ul>'
                    '<li><a href="/legislation/climate">Climate</a></li>'
                    '<li><a href="/legislation/housing">Housing</a></li>'
                    '<li><a href="/legislation/healthcare">Healthcare</a></li></ul></li></ul>')
            self.assertEqual(members.menu_issues(menu, site + "/", site, "Marsha Blackburn", OTHERS),
                             ["Climate", "Housing", "Healthcare"], label)
        # A flat bar is not a menu of its first item.
        flat = ('<nav><a href="/issues">Issues</a><a href="/news">News</a>'
                '<a href="/media">Media</a><a href="/videos">Videos</a></nav>')
        self.assertEqual(members.menu_issues(flat, site + "/", site, "Marsha Blackburn", OTHERS), [])

    def test_headings_the_home_page_carries_too_are_the_sites_frame(self):
        # Senator Kennedy's issues page ends in his offices' cities, under
        # headings, as every page of his site does: no list of issues.
        frame = "".join(f"<h3>{c}</h3><p>{'x ' * 10}</p>" for c in
                        ("Washington D.C", "Alexandria", "Baton Rouge", "Monroe"))
        home = members.parse("<h1>Home</h1>" + frame)
        issues = members.parse("<h1>Issues</h1>" + frame)
        self.assertEqual(members.heading_issues(issues, "John Kennedy", OTHERS, home=home), [])
        listed = members.parse("<h1>Issues</h1>" + "".join(
            f"<h3>{t}</h3><p>{'y ' * 30}</p>" for t in ("Agriculture", "Energy", "Veterans"))
            + frame)
        self.assertEqual(members.heading_issues(listed, "John Kennedy", OTHERS, home=home),
                         ["Agriculture", "Energy", "Veterans"])
        # A line break is a space ("Honoring<br>Veterans").
        self.assertEqual(members.parse("<h3>Honoring<br>Veterans</h3>").headings,
                         [("h3", "Honoring Veterans")])
        self.assertTrue(members.furniture("Des Moines Office"))
        self.assertTrue(members.furniture("Annual Report"))

    def test_the_senates_firewall_is_no_page(self):
        page = members.parse("<title>Senate.gov - Unauthorized</title><p>Sorry, a potential "
                             "security risk was detected in your submitted request." + "x " * 200)
        self.assertFalse(members.readable(200, page))

    def test_fewer_than_three_is_not_a_list(self):
        markup = '<a href="/issues/a">Agriculture</a><a href="/issues/b">Energy</a>'
        self.assertEqual(members.listed_issues(self.page(markup), "https://x.house.gov/issues",
                                               "Rick Larsen", OTHERS), [])

    def test_a_line_names_someone_only_as_a_name(self):
        for text, named in (("Trump Tariffs", True), ("Senator Cassidy's Plan", True),
                            ("Cassidy's plan", True), ("Green Energy", False),
                            ("Small Business", False), ("Women's Health", False),
                            ("Larsen Legislation", True), ("Rick's priorities", True)):
            self.assertEqual(members.names_someone(text, "Rick Larsen", OTHERS), named, text)

    def test_a_card_is_labelled_by_its_title_not_its_blurb(self):
        # Senator Cruz's issues are cards: an icon, a title, a blurb. Read
        # as one run of words "Tax Reform Promote jobs, growth, and
        # opportunity" passed as an issue, and the cards whose blurbs ran
        # longer were dropped - a partial list that looked whole.
        card = ('<a href="/about/issues/{slug}"><div class="icon"><img alt="{t} icon"></div>'
                '<div class="label">{t}</div><div class="description"><p>{blurb}</p></div></a>')
        markup = "".join(card.format(slug=s, t=t, blurb=b) for s, t, b in (
            ("ai", "AI", "Keep America first in artificial intelligence"),
            ("tax-reform", "Tax Reform", "Promote jobs, growth, and opportunity"),
            ("constitution", "Constitution and Bill of Rights",
             "Protect life, liberty, and the pursuit of happiness for every American"),
            ("veterans", "Veterans", "Honor those who served")))
        page = members.parse(markup)
        items = members.listed_issues(page, "https://www.cruz.senate.gov/about/issues",
                                      "Ted Cruz", OTHERS)
        self.assertEqual(items, ["AI", "Tax Reform", "Constitution and Bill of Rights", "Veterans"])
        # A link written inline keeps all its words.
        self.assertEqual(members.anchors('<a href="/x">Health <b>&amp;</b> Human Services</a>'),
                         [("/x", "Health & Human Services")])

    def test_the_sites_furniture_is_not_an_issue(self):
        # Filed under the House template's Issues menu, and not an issue.
        for text in ("Community Project Funding", "CPF Requests", "Legislative Process",
                     "Bill Search", "How Congress Works", "Grants", "Ethics Approval",
                     "COVID-19 Resources", "Congressionally Directed Spending Requests",
                     "Fiscal Year 2027 NDAA Community Project Funding Requests",
                     "Project Requests", "Member-Designated Transportation Project Disclosure Page",
                     "My Caucuses", "Committee Work", "Travel Abroad", "2019 in Review",
                     "Bills I've Sponsored/Co-Sponsored", "Legislative Action",
                     "Military Academy Nomination Application Form",
                     "Appropriations Request Disclosures", "Constituent Services",
                     "2025 End of Year Report", "FY 2026 Requested Community Projects",
                     "Coronavirus Updates", "Current Legislation", "COVID and Community Resources"):
            self.assertTrue(members.furniture(text), text)
            self.assertEqual(members.topic(text, "Rick Larsen", OTHERS), "", text)
        for text in ("Natural Resources", "Water Resources", "Appropriations", "Small Business"):
            self.assertEqual(members.topic(text, "Rick Larsen", OTHERS), text, text)

    def test_a_home_page_that_links_its_issue_pages(self):
        # The home page's own links to its /issues/... pages, read when the
        # site has no issues page at all.
        markup = ('<a href="/#issues-front">Issues</a>'
                  '<a href="/issues/federal-employees">Federal Employees</a>'
                  '<a href="/issues/jobs-economy">Jobs &amp; the Economy</a>'
                  '<a href="/media/press-releases/x">Hoyer Statement</a>'
                  '<a href="/issues/environment">Environment</a>')
        self.assertEqual(members.home_issues(members.parse(markup), "https://hoyer.house.gov",
                                             "Steny Hoyer", OTHERS),
                         ["Federal Employees", "Jobs & the Economy", "Environment"])

    def test_the_sites_furniture_cut_lines_and_titles(self):
        # Reviews of PR #106 (2026-10-18), each from a built profile.
        for text in ("Sponsored &", "AI, Social Media,", "Know More About the Senator",
                     "Mobile Office Hours", "Grant Opportunities", "Community issues and events",
                     "Paycheck Protection Program Portal Opening", "Government Shutdown Resources",
                     "FY27 Appropriations Requests", "Past Appropriations Requests", "Congress",
                     "About the Congresswoman", "Important Government Shutdown Information",
                     "Telephone Townhall Questions & Answers", "Local Resources",
                     "FY2027 MILITARY CONSTRUCTION AUTHORIZATION REQUESTS",
                     "Hurricanes Laura, Delta and Zeta Resources", "Resources for Homeowners",
                     "9th District", "District"):
            self.assertEqual(members.topic(text, "Rick Larsen", OTHERS), "", text)
            self.assertTrue(members.furniture(text), text)
        self.assertEqual(members.topic("President's Administration", "Rick Larsen", OTHERS), "")
        for text in ("LGBTQ+ Equality", "Economic Opportunity", "Natural Resources",
                     "Jobs, Economy, and Fiscal Responsibility", "Congressional Reform",
                     "Disaster Recovery"):
            self.assertEqual(members.topic(text, "Rick Larsen", OTHERS), text, text)

    def test_a_line_break_inside_a_heading_is_a_space(self):
        # Hoeven's "Sponsored &amp;</br>Co-Sponsored Legislation" (a
        # malformed end tag) and Curtis's "AI, Social Media, <br>and youth
        # Safety" were each cut at the break.
        page = members.parse('<h5 class="elementor-heading-title">Sponsored &amp;</br>'
                             'Co-Sponsored Legislation</h5><h3>AI, Social Media, <br>and youth '
                             'Safety</h3><h3>Veterans<br/>Affairs</h3>')
        self.assertEqual([t for _, t in page.headings],
                         ["Sponsored & Co-Sponsored Legislation",
                          "AI, Social Media, and youth Safety", "Veterans Affairs"])
        self.assertEqual(members.topic("Sponsored & Co-Sponsored Legislation", "John Hoeven",
                                       OTHERS), "")

    def test_one_issue_spelled_twice_is_listed_once(self):
        self.assertEqual(members.dedupe(["Jobs, Economy, and Fiscal Responsibility", "Agriculture",
                                         "Jobs, Economy, Fiscal Responsibility",
                                         "Energy & Environment", "Energy and Environment"]),
                         ["Jobs, Economy, and Fiscal Responsibility", "Agriculture",
                          "Energy & Environment"])

    def test_the_templates_stock_categories_are_not_a_platform(self):
        # figures.house.gov/issues, as the House template ships it: six
        # categories, each over "Learn about news and information related
        # to ...".
        stock = "".join(
            f'<div class="issue"><a href="/issues/{s.lower()}"><h2>{s}</h2></a><p>Learn about news '
            f'and information related to {s}.</p></div>'
            for s in ("Congress", "Economy", "Education", "Energy", "Health", "Veterans"))
        items = members.listed_issues(members.parse(stock), "https://figures.house.gov/issues",
                                      "Shomari Figures", OTHERS)
        self.assertEqual(items, ["Economy", "Education", "Energy", "Health", "Veterans"])
        self.assertTrue(members.stock_list(items))
        self.assertFalse(members.stock_list(items + ["Immigration"]))
        self.assertFalse(members.stock_list([]))

    def test_a_menus_link_is_its_index_or_the_page_its_on(self):
        site = "https://lynch.house.gov"
        # Lynch's "Issues" links its first issue, not a list of them.
        menu = ('<ul><li><a href="/civil-rights">Issues</a><ul>'
                '<li><a href="/civil-rights">Civil Rights</a></li>'
                '<li><a href="/economy">Economy</a></li>'
                '<li><a href="/education">Education</a></li>'
                '<li><a href="/veterans">Veterans</a></li></ul></li></ul>')
        items, at = members.menu_read(menu, site + "/", site, "Stephen Lynch", OTHERS)
        self.assertEqual(items, ["Civil Rights", "Economy", "Education", "Veterans"])
        self.assertIsNone(at)
        items, at = members.menu_read(BOOZMAN, "https://www.boozman.senate.gov/public/",
                                      "https://www.boozman.senate.gov/public", "John Boozman", OTHERS)
        self.assertEqual(at, "https://www.boozman.senate.gov/public/index.cfm/issues")

    def test_a_former_president_is_someone_else_too(self):
        others = members.people_named([], {"president": {"name": "Donald J. Trump"},
                                           "vicePresident": {"name": "J.D. Vance"}})
        for text, named in (("Biden's Border Crisis", True), ("Repeal Obamacare", True),
                            ("Bidenomics", True), ("Trump Accounts", True),
                            ("President Clinton's Legacy", True), ("Harris County Flooding", False),
                            ("Clinton River Restoration", False), ("Advance Directives", False)):
            self.assertEqual(members.names_someone(text, "Rick Larsen", others), named, text)

    def test_the_index_is_the_link_that_says_issues_before_one_that_says_priorities(self):
        home = self.page('<a href="/about/priorities">Priorities</a>'
                         '<a href="/issues/">On the Issues</a>'
                         '<a href="https://other.house.gov/issues">Issues</a>')
        self.assertEqual(members.index_links(home, "https://larsen.house.gov/",
                                             "https://larsen.house.gov"),
                         ["https://larsen.house.gov/issues/",
                          "https://larsen.house.gov/about/priorities"])


class TestTheContactPage(unittest.TestCase):
    """PROFILES-16: a contact page is linked only once a fetch shows it holds
    a form to write to the office, or leads to one - not a soft 200."""

    SEARCH = '<form role="search" action="/search"><input name="q"></form>'

    def test_a_form_to_write_with_is_not_a_search_or_a_sign_up(self):
        site = "https://crank.house.gov"
        self.assertFalse(members.holds_form(self.SEARCH, site + "/contact", site))
        self.assertFalse(members.holds_form(
            '<form class="signup-form" action="/forms/emailsignup"><input name="email"></form>',
            site + "/contact", site))
        self.assertTrue(members.holds_form(
            '<form class="zip-auth-form" action="/zip_authentication">'
            '<input name="zip_lookup"></form>', site + "/contact", site))
        self.assertTrue(members.holds_form('<form><textarea name="m"></textarea></form>',
                                           site + "/contact", site))
        # The office's own forms host, in a frame.
        self.assertTrue(members.holds_form('<iframe src="https://Crankforms.house.gov/contact/">',
                                           site + "/contact", site))
        self.assertFalse(members.holds_form('<iframe src="https://forms.example.com/contact">',
                                            site + "/contact", site))
        # The House's shared constituent-mail form, framed on the member's
        # own page (Clyburn's "Get In Touch").
        self.assertTrue(members.holds_form(
            '<iframe\n title="Get In Touch"\n src="https://iqconnect.house.gov/iqextranet/'
            'EForm.aspx?__cid=SC06JC&amp;__fid=100020&amp;iframe=Y">', site + "/get-in-touch/", site))

    def test_a_newsletter_form_is_not_a_way_to_write(self):
        site = "https://aguilar.house.gov"
        # Aguilar's /contact/ (2026-10-18): its only form, a newsletter
        # sign-up whose attributes never say so.
        aguilar = ('<h3>Newsletter Sign Up</h3><p>Receive email newsletter updates.</p>'
                   '<form class="wpcf7-form init" action="/contact/#wpcf7-f1-o1">'
                   '<p>Sign up to receive updates</p>'
                   '<input type="hidden" name="_wpcf7" value="1">'
                   '<input type="text" name="first-name-footer"><input type="text" '
                   'name="last-name-footer"><input type="email" name="email-footer">'
                   '<input type="submit" value="Submit"></form>')
        self.assertFalse(members.holds_form(aguilar, site + "/contact/", site))
        # Mfume's /contact/offices: webform_225, which the page's settings
        # name as its newsletter; the form's own words say nothing.
        mfume = ('<script>var drupalSettings = {"newsletter_webform_id":"webform_225"};</script>'
                 '<form class="webform-submission-form" id="webform-submission-webform-225-add-form">'
                 '<input name="first_name"><input name="last_name"><input name="email">'
                 '<input name="zip_code"></form>')
        self.assertFalse(members.holds_form(mfume, "https://mfume.house.gov/contact/offices",
                                            "https://mfume.house.gov"))
        # A name and an email alone are a sign-up whatever the form says.
        self.assertFalse(members.holds_form(
            '<form><input name="first"><input name="last"><input name="email_address"></form>',
            site + "/contact/", site))
        # A message form that offers the newsletter too is a message form.
        self.assertTrue(members.holds_form(
            '<form><input name="email"><textarea name="msg"></textarea>'
            '<label><input type="checkbox" name="optin"> Subscribe to my newsletter</label></form>',
            site + "/contact/", site))
        # A message form in steps: a name first, the message on the next page
        # (Adam Smith's /contact, 2026-10-18).
        self.assertTrue(members.holds_form(
            '<form class="webform-submission-webform-222-add-form"><select name="honorific_2">'
            '</select><input name="first_name_2"><input name="last_name_2">'
            '<input class="webform-button--next" data-drupal-selector="edit-wizard-next" '
            'type="submit" name="op" value="Next Page"></form>', site + "/contact/", site))
        # The address check before the message.
        self.assertTrue(members.holds_form(
            '<form id="address-verify"><input name="street_address"><input name="city">'
            '<input name="zip5"></form>', site + "/contact/", site))

    def test_a_contact_link_is_found_by_the_words_a_site_uses(self):
        site = "https://hoyer.house.gov"
        home = enrich.parse_page('<a href="//hoyer.house.gov/help/contact-stenys-office">Contact Steny</a>'
                                 '<a href="/contact/newsletter-subscribe">Signup For Newsletter</a>'
                                 '<a href="/contact/offices">Office Contact Information</a>'
                                 '<a href="/get-in-touch/">Get In Touch</a>')
        self.assertEqual(members.contact_links(home, site + "/", site),
                         ["https://hoyer.house.gov/help/contact-stenys-office",
                          "https://hoyer.house.gov/get-in-touch/"])

    def test_a_contact_index_is_followed_to_its_form(self):
        site = "https://pocan.house.gov"
        pages = {
            site + "/contact": (site + "/contact", 200,
                                "<title>Contact</title>" + self.SEARCH +
                                '<a href="/contact/email-me">Email Me</a>'),
            site + "/contact/email-me": (site + "/contact/email-me", 200,
                                         '<form action="/zip"><input name="zip5"></form>'),
        }
        home = enrich.parse_page('<a href="/contact">Contact</a>')
        found = members.contact_page(home, site + "/", site, pause=0,
                                     fetch=lambda url: pages[url])
        self.assertEqual(found, (site + "/contact/email-me", "checked"))

    def test_a_refusal_concludes_nothing(self):
        site = "https://x.senate.gov"
        home = enrich.parse_page('<a href="/contact/">Contact</a>')
        found = members.contact_page(home, site + "/", site, pause=0,
                                     fetch=lambda url: (url, 403, ""))
        self.assertEqual(found, (None, None))
        found = members.contact_page(home, site + "/", site, pause=0,
                                     fetch=lambda url: (url, 200, "<title>Contact</title>"))
        self.assertEqual(found, (None, "none"))

    def test_only_the_offices_own_hosts_count(self):
        self.assertTrue(members.own_host("https://www.larsen.house.gov/x", "https://larsen.house.gov"))
        self.assertTrue(members.own_host("https://larsenforms.house.gov/", "https://larsen.house.gov"))
        self.assertFalse(members.own_host("https://larsenx.house.gov/", "https://larsen.house.gov"))
        self.assertFalse(members.own_host("https://larsen.senate.gov/", "https://larsen.house.gov"))


class TestAReadThatIsTurnedAway(unittest.TestCase):
    """Rule 8: a bot wall or a page drawn by script is no verdict until
    headless Chrome has tried it, and none after if Chrome fails too."""

    def setUp(self):
        self.real = enrich.fetch

    def tearDown(self):
        enrich.fetch = self.real

    def test_a_refusal_is_tried_in_chrome(self):
        enrich.fetch = lambda url, hops=2: (url, 403, "")
        body = "<title>Senator X</title><p>" + "Senator X works for the state. " * 20 + "</p>"
        final, status, page, how, markup = members.get("https://x.senate.gov", pause=0,
                                                       render=lambda url: body)
        self.assertEqual((status, how), (200, "chrome"))
        _, status, _, how, _ = members.get("https://x.senate.gov", pause=0,
                                           render=lambda url: "<title>Just a moment...</title>")
        self.assertEqual((status, how), (403, None))

    def test_a_missing_page_is_not_tried_again(self):
        enrich.fetch = lambda url, hops=2: (url, 404, "")
        tried = []
        members.get("https://x.house.gov/issues", pause=0, render=lambda url: tried.append(url))
        self.assertEqual(tried, [])

    def serve(self, pages):
        enrich.fetch = lambda url, hops=2: pages.get(url.rstrip("/"), (url, 404, ""))

    HOME = ("<title>Congressman Steny Hoyer</title><p>" + "Steny Hoyer serves Maryland. " * 20
            + '</p><a href="/#issues-front">Issues</a>'
            '<a href="/issues/federal-employees">Federal Employees</a>'
            '<a href="/issues/jobs-economy">Jobs &amp; the Economy</a>'
            '<a href="/issues/environment">Environment</a>')

    def test_an_issues_page_the_home_page_does_not_link_is_read(self):
        # Hoyer's /issues lists more than the five his home page features.
        site = "https://hoyer.house.gov"
        index = ("<title>Issues | Steny Hoyer</title><p>" + "Issues. " * 60 + "</p>" + "".join(
            f'<a href="/issues/{s}">{t}</a>' for s, t in (
                ("federal-employees", "Federal Employees"), ("budget", "Budget & Fiscal "
                 "Responsibility"), ("education", "Education"), ("environment", "Environment"),
                ("transportation", "Transportation and Infrastructure"))))
        self.serve({site: (site, 200, self.HOME), site + "/issues": (site + "/issues", 200, index)})
        record = members.read_site(member(id="H000874", name="Steny Hoyer", website=site), OTHERS,
                                   pause=0, render=None, fetch=lambda url: (url, 404, ""))
        self.assertEqual(record["how"], "index")
        self.assertEqual(record["issuesUrl"], site + "/issues")
        self.assertEqual(len(record["issues"]), 5)
        # No issues page at all: the home page's links, said to be what it
        # features.
        self.serve({site: (site, 200, self.HOME)})
        record = members.read_site(member(id="H000874", name="Steny Hoyer", website=site), OTHERS,
                                   pause=0, render=None, fetch=lambda url: (url, 404, ""))
        self.assertEqual((record["how"], record["issuesUrl"]), ("home", site))
        hoyer = member(id="H000874", name="Steny Hoyer", website=site)
        members.apply_cache([hoyer], {"sites": {"H000874": record}})
        self.assertTrue(hoyer["platformFeatured"])
        # A soft 200 that serves the home page again is not an issues page.
        self.serve({site: (site, 200, self.HOME), site + "/issues": (site + "/issues", 200,
                                                                     self.HOME)})
        record = members.read_site(member(id="H000874", name="Steny Hoyer", website=site), OTHERS,
                                   pause=0, render=None, fetch=lambda url: (url, 404, ""))
        self.assertEqual(record["how"], "home")

    def test_an_inconclusive_read_keeps_the_last_good_one(self):
        old = {"url": "https://x.house.gov", "verdict": "listed", "issues": ["A", "B", "C"],
               "read": "2026-10-01"}
        new = {"url": "https://x.house.gov", "verdict": None, "reason": "HTTP 403",
               "read": "2026-10-18"}
        kept = members._keep(old, new)
        self.assertEqual(kept["issues"], ["A", "B", "C"])
        self.assertEqual(kept["lastTry"], {"read": "2026-10-18", "reason": "HTTP 403"})
        # A site that moved is a new read, not a failed one.
        self.assertIs(members._keep(old, dict(new, url="https://y.house.gov")).get("issues"), None)


class TestApplied(unittest.TestCase):
    CACHE = {
        "read": "2026-10-18",
        "offices": {"read": "2026-10-18", "byId": {"L000560": [
            {"address": "2930 Wetmore Avenue", "suite": "Suite 9F", "city": "Everett",
             "state": "WA", "zip": "98201", "phone": "425-252-3188"}]}},
        "directory": {"edition": "CDIR-2026-02-20", "byId": {"L000560": {
            "site": "https://larsen.house.gov", "education": "B.A., Pacific Lutheran University",
            "careers": "member, Snohomish County Council, 1998-2001"}}},
        "articles": {"L000560": {"requested": "Rick Larsen", "title": "Rick Larsen",
                                 "education": "Pacific Lutheran University (BA)"},
                     "C000001": {"requested": "Pat Case", "title": "Pat Case",
                                 "education": "Yale University (BA)"}},
        "sites": {"L000560": {"url": "https://larsen.house.gov", "verdict": "listed",
                              "issues": ["Agriculture", "Health Care", "Veterans"],
                              "issuesUrl": "https://larsen.house.gov/issues/",
                              "contact": "https://larsen.house.gov/contact/", "read": "2026-10-18"},
                  "C000001": {"url": "https://case.house.gov", "verdict": "none",
                              "read": "2026-10-18"}},
    }

    def test_each_field_comes_from_its_source_and_says_so(self):
        larsen = member()
        case = member(id="C000001", name="Pat Case", website="https://case.house.gov",
                      wikipedia="Pat Case", contactForm="https://case.house.gov/write")
        counts = members.apply_cache([larsen, case], self.CACHE)
        self.assertEqual(larsen["education"], "B.A., Pacific Lutheran University")
        self.assertEqual(larsen["fieldSources"], {"education": "congressional-directory",
                                                  "previous_professions": "congressional-directory",
                                                  "platforms": "official-site"})
        self.assertEqual(larsen["platforms"], "Agriculture; Health Care; Veterans")
        self.assertEqual(larsen["officialIssuesUrl"], "https://larsen.house.gov/issues/")
        self.assertEqual(larsen["contactForm"], "https://larsen.house.gov/contact/")
        self.assertEqual(larsen["contactFormVia"], "official-site")
        self.assertEqual(larsen["districtOffices"][0]["city"], "Everett")
        # Not in the Directory: the article's education, and no careers.
        self.assertEqual(case["education"], "Yale University (BA)")
        self.assertEqual(case["fieldSources"], {"education": "member-wikipedia"})
        self.assertEqual(case["quality"]["previous_professions"], UNKNOWN)
        # Read, and the site lists no issues: said as that.
        self.assertEqual(case["quality"]["platforms"], "not_listed")
        # congress-legislators' own form stays.
        self.assertEqual(case["contactForm"], "https://case.house.gov/write")
        self.assertEqual(counts["platform"], 1)

    def test_a_record_of_another_address_or_article_is_not_applied(self):
        moved = member(website="https://larsen.house.gov/new", wikipedia="Rick Larsen (politician)")
        members.apply_cache([moved], dict(self.CACHE, directory={"byId": {"L000560": {
            "site": "https://old.house.gov", "education": "Old"}}}))
        self.assertEqual(moved["education"], "")
        self.assertNotIn("fieldSources", moved)
        self.assertNotIn("contactForm", moved)

    def test_furniture_is_dropped_from_a_cached_read(self):
        # A filter added after a read reaches the page at the next build.
        larsen = member()
        sites = {"L000560": dict(self.CACHE["sites"]["L000560"],
                                 issues=["Agriculture", "Project Requests", "Health Care",
                                         "Veterans"])}
        members.apply_cache([larsen], dict(self.CACHE, sites=sites))
        self.assertEqual(larsen["platforms"], "Agriculture; Health Care; Veterans")
        # Fewer than three left is no list, but the page is there: linked,
        # never called empty.
        larsen = member()
        sites = {"L000560": dict(self.CACHE["sites"]["L000560"],
                                 issues=["Agriculture", "Project Requests", "Committee Work"])}
        members.apply_cache([larsen], dict(self.CACHE, sites=sites))
        self.assertEqual(larsen["quality"]["platforms"], "see_site")
        self.assertEqual(larsen["officialIssuesUrl"], "https://larsen.house.gov/issues/")
        self.assertNotIn("platforms", larsen.get("fieldSources", {}))

    def test_the_stock_categories_and_two_spellings_from_a_cached_read(self):
        # Seventeen members' cached lists were the House template's six
        # stock categories; Figures's identical page read "not listed".
        # Both now link the page.
        for issues in (["Congress", "Economy", "Education", "Energy", "Health", "Veterans"],
                       ["Congress", "Economy", "Education", "Energy", "Health", "Veterans",
                        "FY 2027 CPF Requests"]):
            larsen = member()
            sites = {"L000560": dict(self.CACHE["sites"]["L000560"], issues=issues)}
            members.apply_cache([larsen], dict(self.CACHE, sites=sites))
            self.assertEqual(larsen["quality"]["platforms"], "see_site")
            self.assertEqual(larsen["officialIssuesUrl"], "https://larsen.house.gov/issues/")
        # A member who added issues of their own lists them, without "Congress".
        larsen = member()
        sites = {"L000560": dict(self.CACHE["sites"]["L000560"], issues=[
            "Congress", "Economy", "Energy", "Health", "National Security", "Veterans",
            "Jobs, Economy, and Fiscal Responsibility", "Jobs, Economy, Fiscal Responsibility"])}
        members.apply_cache([larsen], dict(self.CACHE, sites=sites))
        self.assertEqual(larsen["platforms"], "Economy; Energy; Health; National Security; "
                                              "Veterans; Jobs, Economy, and Fiscal Responsibility")
        self.assertNotIn("platformFeatured", larsen)

    def test_a_page_recorded_as_no_list_is_linked_instead(self):
        from kyc import overrides
        larsen = member()
        url = self.CACHE["sites"]["L000560"]["issuesUrl"]
        saved = dict(overrides.OFFICIAL_ISSUES_NOT_A_LIST)
        try:
            members.OFFICIAL_ISSUES_NOT_A_LIST["L000560"] = ("2026-10-18", url, "fragments")
            members.apply_cache([larsen], self.CACHE)
            self.assertEqual(larsen["quality"]["platforms"], "see_site")
            self.assertEqual(larsen["officialIssuesUrl"], url)
            # Once the site is read from another page, the entry is reported.
            moved = dict(self.CACHE, sites={"L000560": dict(self.CACHE["sites"]["L000560"],
                                                            issuesUrl=url + "new")})
            codes = [p[1] for p in members.problems([member()], moved)]
            self.assertIn("members-override-stale", codes)
        finally:
            members.OFFICIAL_ISSUES_NOT_A_LIST.clear()
            members.OFFICIAL_ISSUES_NOT_A_LIST.update(saved)

    def test_an_issues_page_with_no_list_read_is_linked_not_called_empty(self):
        # Senator Sanders's issues page is prose under tabs: there is a
        # page, and no list this reader can take in its words.
        larsen = member()
        sites = {"L000560": {"url": "https://larsen.house.gov", "verdict": "none",
                             "pageRead": "https://larsen.house.gov/issues/", "read": "2026-10-18"}}
        members.apply_cache([larsen], dict(self.CACHE, sites=sites))
        self.assertEqual(larsen["quality"]["platforms"], "see_site")
        self.assertEqual(larsen["officialIssuesUrl"], "https://larsen.house.gov/issues/")

    def test_a_challenger_is_never_touched(self):
        challenger = member(id="H6WA02123", isCandidate=True)
        members.apply_cache([challenger], {"articles": {"H6WA02123": {
            "requested": "Rick Larsen", "title": "Rick Larsen", "education": "X"}}})
        self.assertEqual(challenger["education"], "")

    def test_district_offices_keep_what_a_reader_needs(self):
        rows = [{"id": {"bioguide": "L000560"}, "offices": [
            {"id": "L000560-everett", "address": "2930 Wetmore  Avenue", "city": "Everett",
             "state": "WA", "zip": "98201", "phone": "425-252-3188", "fax": "425-252-6606",
             "latitude": 47.9, "longitude": -122.2, "hours": "M-F 9-5"},
            {"id": "L000560-nowhere", "city": "Nowhere"}]}]
        self.assertEqual(members.district_offices(rows), {"L000560": [
            {"address": "2930 Wetmore Avenue", "city": "Everett", "state": "WA", "zip": "98201",
             "phone": "425-252-3188", "hours": "M-F 9-5"}]})


class TestTheRosterColumnsAreNeverShown(unittest.TestCase):
    """Rule 86: the curated columns never reach a profile, and validate
    fails a biography field that has no source the page can name."""

    def test_a_members_typed_columns_are_never_read(self):
        from kyc.profiles import _build_member, apply_quality

        row = {"Bioguide ID": "A000001", "Name": "Jane Doe", "Chamber": "House",
               "State": "TX", "District": "District 3", "Education": "Somewhere (BA)",
               "Previous Professions": "Lawyer",
               "Policy Focus & Platforms": "Anti-abortion legislation, border security"}
        profile = apply_quality(_build_member(row, 0))
        for field in ("education", "previous_professions", "platforms"):
            self.assertEqual(profile[field], "No data", field)
            self.assertEqual(profile["quality"][field], UNKNOWN, field)

    def test_an_unsourced_biography_field_fails_the_build(self):
        typed = member(education="Somewhere (BA)", quality={})
        codes = [i.code for i in validate.check_bio_sources([typed]) if i.level == "error"]
        self.assertEqual(codes, ["bio-unsourced"])
        sourced = member(education="Somewhere (BA)", quality={},
                         fieldSources={"education": "congressional-directory"})
        absent = member()
        self.assertEqual(validate.check_bio_sources([sourced, absent]), [])


if __name__ == "__main__":
    unittest.main()
