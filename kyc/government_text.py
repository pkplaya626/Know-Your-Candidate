"""The words of the guide to how government works (rendered by ``government``).

Editorial text, like ``overrides``: every section names the sources it was
checked against, and ``REVIEWED`` is the day it was last checked. The site
owner supplied the outline (a report on the institutions of American
government); each claim in it was checked against the primary sources listed
here before it was written down, and where the report was wrong, out of date
or took a side, the text says what the sources say instead.

Markup, kept deliberately small (``government.inline``):
    [label](target)   a link; the target is #section, guide:page#section,
                      site:path-from-the-root, state:TX, or an https URL.

Blocks: ("p", text) ("note", text) ("h3", text[, id]) ("ul", [text, ...])
        ("roles", [(term, text), ...]) ("table", {caption, head, rows})
        ("chart", {top, items: [(title, text)], caption}) ("cards", [(title,
        target, text), ...]) ("live", key, fallback text)

Never name a person who holds an office here: who holds one comes from the
data, on the page (``assets/kyc-guide.js``), so it cannot go stale.
"""

REVIEWED = "2026-10-05"

# key -> (title, URL). Primary sources wherever one exists.
SOURCES = {
    # The Constitution
    "const-art1": ("U.S. Constitution, Article I",
                   "https://constitution.congress.gov/constitution/article-1/"),
    "const-art2": ("U.S. Constitution, Article II",
                   "https://constitution.congress.gov/constitution/article-2/"),
    "const-art3": ("U.S. Constitution, Article III",
                   "https://constitution.congress.gov/constitution/article-3/"),
    "const-art4": ("U.S. Constitution, Article IV",
                   "https://constitution.congress.gov/constitution/article-4/"),
    "const-art6": ("U.S. Constitution, Article VI",
                   "https://constitution.congress.gov/constitution/article-6/"),
    "const-amdt10": ("U.S. Constitution, Tenth Amendment",
                     "https://constitution.congress.gov/constitution/amendment-10/"),
    "const-amdt17": ("U.S. Constitution, Seventeenth Amendment",
                     "https://constitution.congress.gov/constitution/amendment-17/"),
    "const-amdt22": ("U.S. Constitution, Twenty-second Amendment",
                     "https://constitution.congress.gov/constitution/amendment-22/"),
    "const-amdt25": ("U.S. Constitution, Twenty-fifth Amendment",
                     "https://constitution.congress.gov/constitution/amendment-25/"),

    # Federal statutes
    "usc-3-19": ("3 U.S.C. 19 (presidential succession)",
                 "https://www.law.cornell.edu/uscode/text/3/19"),
    "usc-5-101": ("5 U.S.C. 101 (the executive departments)",
                  "https://www.law.cornell.edu/uscode/text/5/101"),
    "usc-5-3105": ("5 U.S.C. 3105 (administrative law judges)",
                   "https://www.law.cornell.edu/uscode/text/5/3105"),
    "usc-10-111": ("10 U.S.C. 111 (the Department of Defense)",
                   "https://www.law.cornell.edu/uscode/text/10/111"),
    "usc-10-942": ("10 U.S.C. 942 (Court of Appeals for the Armed Forces)",
                   "https://www.law.cornell.edu/uscode/text/10/942"),
    "usc-12-242": ("12 U.S.C. 242 (Federal Reserve Board)",
                   "https://www.law.cornell.edu/uscode/text/12/242"),
    "usc-15-41": ("15 U.S.C. 41 (Federal Trade Commission)",
                  "https://www.law.cornell.edu/uscode/text/15/41"),
    "usc-20-3411": ("20 U.S.C. 3411 (Department of Education)",
                    "https://www.law.cornell.edu/uscode/text/20/3411"),
    "usc-26-7443": ("26 U.S.C. 7443 (Tax Court)",
                    "https://www.law.cornell.edu/uscode/text/26/7443"),
    "usc-28-1": ("28 U.S.C. 1 (the Supreme Court)",
                 "https://www.law.cornell.edu/uscode/text/28/1"),
    "usc-28-41": ("28 U.S.C. 41 (the circuits)",
                  "https://www.law.cornell.edu/uscode/text/28/41"),
    "usc-28-45": ("28 U.S.C. 45 (chief judges of the circuits)",
                  "https://www.law.cornell.edu/uscode/text/28/45"),
    "usc-28-151": ("28 U.S.C. 151 (bankruptcy courts)",
                   "https://www.law.cornell.edu/uscode/text/28/151"),
    "usc-28-152": ("28 U.S.C. 152 (bankruptcy judges)",
                   "https://www.law.cornell.edu/uscode/text/28/152"),
    "usc-28-171": ("28 U.S.C. 171 (Court of Federal Claims)",
                   "https://www.law.cornell.edu/uscode/text/28/171"),
    "usc-28-251": ("28 U.S.C. 251 (Court of International Trade)",
                   "https://www.law.cornell.edu/uscode/text/28/251"),
    "usc-28-331": ("28 U.S.C. 331 (Judicial Conference)",
                   "https://www.law.cornell.edu/uscode/text/28/331"),
    "usc-28-371": ("28 U.S.C. 371 (senior status)",
                   "https://www.law.cornell.edu/uscode/text/28/371"),
    "usc-28-621": ("28 U.S.C. 621 (Federal Judicial Center)",
                   "https://www.law.cornell.edu/uscode/text/28/621"),
    "usc-28-631": ("28 U.S.C. 631 (magistrate judges)",
                   "https://www.law.cornell.edu/uscode/text/28/631"),
    "usc-28-1295": ("28 U.S.C. 1295 (Federal Circuit)",
                    "https://www.law.cornell.edu/uscode/text/28/1295"),
    "usc-28-1441": ("28 U.S.C. 1441 (removal of civil actions)",
                    "https://www.law.cornell.edu/uscode/text/28/1441"),
    "usc-28-1442": ("28 U.S.C. 1442 (removal: federal officers)",
                    "https://www.law.cornell.edu/uscode/text/28/1442"),
    "usc-31-502": ("31 U.S.C. 502 (Office of Management and Budget)",
                   "https://www.law.cornell.edu/uscode/text/31/502"),
    "usc-31-703": ("31 U.S.C. 703 (Comptroller General)",
                   "https://www.law.cornell.edu/uscode/text/31/703"),
    "usc-38-7253": ("38 U.S.C. 7253 (Court of Appeals for Veterans Claims)",
                    "https://www.law.cornell.edu/uscode/text/38/7253"),
    "usc-39-201": ("39 U.S.C. 201 (Postal Service)",
                   "https://www.law.cornell.edu/uscode/text/39/201"),
    "usc-49-24301": ("49 U.S.C. 24301 (Amtrak)",
                     "https://www.law.cornell.edu/uscode/text/49/24301"),
    "usc-50-1803": ("50 U.S.C. 1803 (Foreign Intelligence Surveillance Court)",
                    "https://www.law.cornell.edu/uscode/text/50/1803"),
    "usc-18-1153": ("18 U.S.C. 1153 (Major Crimes Act)",
                    "https://www.law.cornell.edu/uscode/text/18/1153"),
    "usc-18-1162": ("18 U.S.C. 1162 (Public Law 280: criminal jurisdiction)",
                    "https://www.law.cornell.edu/uscode/text/18/1162"),
    "usc-28-1360": ("28 U.S.C. 1360 (Public Law 280: civil actions)",
                    "https://www.law.cornell.edu/uscode/text/28/1360"),
    "usc-25-1302": ("25 U.S.C. 1302 (Indian Civil Rights Act)",
                    "https://www.law.cornell.edu/uscode/text/25/1302"),
    "usc-25-1304": ("25 U.S.C. 1304 (special Tribal criminal jurisdiction)",
                    "https://www.law.cornell.edu/uscode/text/25/1304"),
    "usc-25-1911": ("25 U.S.C. 1911 (Indian Child Welfare Act)",
                    "https://www.law.cornell.edu/uscode/text/25/1911"),
    "usc-25-3601": ("25 U.S.C. 3601 (Indian Tribal Justice Act)",
                    "https://www.law.cornell.edu/uscode/text/25/3601"),
    "usc-25-5123": ("25 U.S.C. 5123 (tribal constitutions)",
                    "https://www.law.cornell.edu/uscode/text/25/5123"),
    "usc-25-5301": ("25 U.S.C. 5301 (Indian Self-Determination Act)",
                    "https://www.law.cornell.edu/uscode/text/25/5301"),
    "usc-25-5361": ("25 U.S.C. 5361 (Tribal Self-Governance)",
                    "https://www.law.cornell.edu/uscode/text/25/5361"),
    "cfr-25-11": ("25 C.F.R. 11.201 (Courts of Indian Offenses: magistrates)",
                  "https://www.ecfr.gov/current/title-25/chapter-I/subchapter-B/part-11/subpart-B/section-11.201"),

    # Court decisions
    "marbury": ("Marbury v. Madison, 5 U.S. 137 (1803)",
                "https://www.law.cornell.edu/supremecourt/text/5/137"),
    "johnson": ("Johnson v. M'Intosh, 21 U.S. 543 (1823)",
                "https://www.law.cornell.edu/supremecourt/text/21/543"),
    "cherokee": ("Cherokee Nation v. Georgia, 30 U.S. 1 (1831)",
                 "https://www.law.cornell.edu/supremecourt/text/30/1"),
    "worcester": ("Worcester v. Georgia, 31 U.S. 515 (1832)",
                  "https://www.law.cornell.edu/supremecourt/text/31/515"),
    "youngstown": ("Youngstown Sheet & Tube Co. v. Sawyer, 343 U.S. 579 (1952)",
                   "https://www.law.cornell.edu/supremecourt/text/343/579"),
    "bryan": ("Bryan v. Itasca County, 426 U.S. 373 (1976)",
              "https://www.law.cornell.edu/supremecourt/text/426/373"),
    "oliphant": ("Oliphant v. Suquamish Indian Tribe, 435 U.S. 191 (1978)",
                 "https://www.law.cornell.edu/supremecourt/text/435/191"),
    "michigan-long": ("Michigan v. Long, 463 U.S. 1032 (1983)",
                      "https://www.law.cornell.edu/supremecourt/text/463/1032"),
    "dole": ("South Dakota v. Dole, 483 U.S. 203 (1987)",
             "https://www.law.cornell.edu/supremecourt/text/483/203"),
    "printz": ("Printz v. United States, 521 U.S. 898 (1997)",
               "https://www.law.cornell.edu/supremecourt/text/521/898"),
    "nfib": ("NFIB v. Sebelius, 567 U.S. 519 (2012)",
             "https://www.law.cornell.edu/supremecourt/text/11-393"),
    "wilcox": ("Trump v. Wilcox, No. 24A966 (order of May 22, 2025)",
               "https://www.supremecourt.gov/opinions/24pdf/24a966_1b8e.pdf"),
    "slaughter": ("Trump v. Slaughter, 609 U.S. 422 (2026)",
                  "https://www.supremecourt.gov/opinions/25pdf/609us2r62_g314.pdf"),
    "cook": ("Trump v. Cook, 609 U.S. 528 (2026)",
             "https://www.supremecourt.gov/opinions/25pdf/609us2r63_e2pg.pdf"),

    # Congress
    "house-explained": ("U.S. House of Representatives: The House Explained",
                        "https://www.house.gov/the-house-explained"),
    "house-leadership": ("U.S. House of Representatives: Leadership",
                         "https://www.house.gov/leadership"),
    "house-officers": ("U.S. House of Representatives: Officers and Organizations",
                       "https://www.house.gov/the-house-explained/officers-and-organizations"),
    "senate-leadership": ("U.S. Senate: Leadership & Officers",
                          "https://www.senate.gov/senators/leadership.htm"),
    "senate-officers": ("U.S. Senate: Officers & Staff",
                        "https://www.senate.gov/about/officers-staff.htm"),
    "congress-committees": ("Congress.gov: Committees of the U.S. Congress",
                            "https://www.congress.gov/committees"),
    "congress-legislators": ("congress-legislators: committee membership",
                             "https://github.com/unitedstates/congress-legislators"),
    "gao": ("Government Accountability Office: About", "https://www.gao.gov/about"),
    "cbo": ("Congressional Budget Office: Overview", "https://www.cbo.gov/about/overview"),
    "crs": ("2 U.S.C. 166 (Congressional Research Service)",
            "https://www.law.cornell.edu/uscode/text/2/166"),
    "aoc": ("Architect of the Capitol: About", "https://www.aoc.gov/about-us"),

    # The executive
    "eo-8248": ("Executive Order 8248 (1939), establishing the Executive Office of the President",
                "https://www.archives.gov/federal-register/codification/executive-order/08248.html"),
    "usc-50-3021": ("50 U.S.C. 3021 (National Security Council)",
                    "https://www.law.cornell.edu/uscode/text/50/3021"),
    "eo-14347": ("Executive Order 14347, 90 FR 43893 (Sept. 10, 2025)",
                 "https://www.govinfo.gov/content/pkg/FR-2025-09-10/pdf/2025-17508.pdf"),
    "senate-2026-07-14": ("U.S. Senate floor log, July 14, 2026",
                          "https://www.dailypress.senate.gov/tuesday-july-14-2026/"),
    "crs-in12704": ("Congressional Research Service, Insight IN12704",
                    "https://www.congress.gov/crs-product/IN12704"),
    "ed-2025-11": ("U.S. Department of Education: six new agency partnerships (Nov. 18, 2025)",
                   "https://www.ed.gov/about/news/press-release/us-department-of-education-announces-six-new-agency-partnerships-break-federal-bureaucracy"),
    "ed-treasury": ("U.S. Department of Education: Education–Treasury interagency agreement",
                    "https://www.ed.gov/media/document/ed-treasury-interagency-agreement-federal-student-assistance-partnership-march-19-2026-113468.pdf"),
    "ed-2026-06": ("U.S. Department of Education: additional partnerships (June 16, 2026)",
                   "https://www.ed.gov/about/news/press-release/us-department-of-education-announces-additional-partnerships-strengthen-coordination-individuals-disabilities-programs-bolster-civil-rights"),

    # The courts
    "uscourts-structure": ("U.S. Courts: Court Role and Structure",
                           "https://www.uscourts.gov/about-federal-courts/court-role-and-structure"),
    "uscourts-judgeships": ("U.S. Courts: Authorized Judgeships, 1789 to present",
                            "https://www.uscourts.gov/sites/default/files/2025-01/allauth.pdf"),

    # Governments and their counts
    "cog-report": ("U.S. Census Bureau: Government Organization Summary Report, 2022 and 2025",
                   "https://www.census.gov/library/publications/2026/econ/govtorg2225.html"),
    "cog-isd": ("U.S. Census Bureau: 2022 Census of Governments, Individual State Descriptions",
                "https://www.census.gov/content/dam/Census/library/publications/2024/econ/2022ISD.pdf"),
    "bia-list": ("Bureau of Indian Affairs: Indian Entities Recognized (91 FR 4102, Jan. 30, 2026)",
                 "https://www.govinfo.gov/content/pkg/FR-2026-01-30/html/2026-01899.htm"),
    "bia-faq": ("Bureau of Indian Affairs: What is a federally recognized tribe?",
                "https://www.bia.gov/faqs/what-federally-recognized-tribe"),

    # States
    "wex-police": ("Legal Information Institute: police powers",
                   "https://www.law.cornell.edu/wex/police_powers"),
    "nebraska": ("Nebraska Legislature: History of the Unicameral",
                 "https://nebraskalegislature.gov/about/history_unicameral.php"),
    "tx-322": ("Texas Government Code, chapter 322 (Legislative Budget Board)",
               "https://statutes.capitol.texas.gov/Docs/GV/htm/GV.322.htm"),
    "tx-lbb": ("Texas Legislative Budget Board: About", "https://www.lbb.texas.gov/About_LBB.aspx"),
    "ncsl-veto": ("NCSL: Separation of Powers, Executive Veto Powers",
                  "https://www.ncsl.org/about-state-legislatures/separation-of-powers-executive-veto-powers"),
    "ncsl-leaders": ("NCSL: Roles and Responsibilities of Selected Leadership Positions",
                     "https://www.ncsl.org/resources/details/roles-and-responsibilities-of-selected-leadership-positions"),
    "ncsl-elections": ("NCSL: Election Administration at State and Local Levels",
                       "https://www.ncsl.org/elections-and-campaigns/election-administration-at-state-and-local-levels"),
    "nh-council": ("New Hampshire Executive Council", "https://www.council.nh.gov/"),
    "nh-const": ("New Hampshire Constitution (Justia)",
                 "https://law.justia.com/constitution/new-hampshire/"),
    "ma-council": ("Massachusetts Governor's Council", "https://www.mass.gov/orgs/governors-council"),
    "nc-const-3": ("North Carolina Constitution, Article III",
                   "https://www.ncleg.gov/Laws/Constitution/Article3"),
    "nc-143c-4-4": ("N.C. Gen. Stat. 143C-4-4 (Contingency and Emergency Fund)",
                    "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_143C/GS_143C-4-4.html"),
    "nc-146-22": ("N.C. Gen. Stat. 146-22 (state land acquisitions)",
                  "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_146/GS_146-22.html"),
    "nc-146-29": ("N.C. Gen. Stat. 146-29 (state land dispositions)",
                  "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_146/GS_146-29.html"),
    "tx-courts": ("Texas Judicial Branch: Court Structure",
                  "https://www.txcourts.gov/about-texas-courts/"),
    "ok-occa": ("Oklahoma Court of Criminal Appeals: 2016 OK CR 24 (Rule 7.1, juvenile appeals)",
                "https://okcca.net/cases/2016/OK-CR-24/"),
    "ok-const-7": ("Oklahoma Constitution, Article VII",
                   "https://www.oksenate.gov/sites/default/files/2022-05/oc7.pdf"),
    "nycourts": ("New York State Unified Court System: Court Structure",
                 "https://www.nycourts.gov/courts/8th-judicial-district/court-structure"),
    "mo-plan": ("Missouri Courts: the Missouri Nonpartisan Court Plan",
                "https://www.courts.mo.gov/page.jsp?id=297"),
    "tx-glo": ("Texas General Land Office: About the GLO", "https://www.glo.texas.gov/about-glo"),
    "tx-rrc": ("Railroad Commission of Texas: About", "https://www.rrc.texas.gov/about-us/"),

    # Local governments
    "nlc-delegation": ("National League of Cities: Cities 101, Delegation of Power",
                       "https://www.nlc.org/resource/cities-101-delegation-of-power/"),
    "nlc-forms": ("National League of Cities: Cities 101, Forms of Local Government",
                  "https://www.nlc.org/resource/cities-101-forms-of-local-government/"),
    "naco-primer": ("National Association of Counties: County Government Primer (2024)",
                    "https://www.naco.org/sites/default/files/2025-03/2024%20County%20Government%20Primer_update_v8_FINAL.pdf"),
    "icma-2018": ("ICMA: 2018 Municipal Form of Government Survey",
                  "https://icma.org/sites/default/files/2018%20Municipal%20Form%20of%20Government%20Survey%20Report.pdf"),
    "naco-structure": ("National Association of Counties: County Structure, Authority and Finances",
                       "https://www.naco.org/page/county-structure-authority-and-finances"),
    "nsa-faq": ("National Sheriffs' Association: FAQ", "https://www.sheriffs.org/about-nsa/faq"),
    "unc-prosecutors": ("UNC School of Law: National Study of Prosecutor Elections, 2020 to 2024",
                        "https://law.unc.edu/wp-content/uploads/2026/05/National-Study-of-Prosecutor-Elections-2020-to-2024.pdf"),
    "dc-oag": ("D.C. Office of the Attorney General: Prosecution",
               "https://oag.dc.gov/public-safety/prosecution"),
    "portland": ("City of Portland: Transition to the new form of government",
                 "https://www.portland.gov/transition/overview"),
    "doj-vawa": ("U.S. Department of Justice: 2013 and 2022 Reauthorizations of VAWA",
                 "https://www.justice.gov/tribal/2013-and-2022-reauthorizations-violence-against-women-act-vawa"),
    "bia-pl280": ("Bureau of Indian Affairs: What is Public Law 280?",
                  "https://www.bia.gov/faqs/what-public-law-280-and-where-does-it-apply"),
}


# ------------------------------------------------------------------- pages

INDEX = {
    "slug": "index",
    "nav": "Overview",
    "title": "How American government is organized",
    "description": ("A plain-language guide to American government: Congress, the president and "
                    "the federal courts; state governments; counties, cities, townships, school "
                    "and special districts; and tribal nations, with the sources each part was "
                    "checked against."),
    "lede": ("Every American lives under several governments at once: the federal government, a "
             "state, and in most places a county, a city or town, a school district and other "
             "special districts. Many are also citizens of a tribal nation. This guide explains "
             "who does what at each level and how the levels fit together."),
    "sections": [
        {
            "id": "levels",
            "heading": "The levels at a glance",
            "blocks": [
                ("p", "The Constitution divides power two ways. It splits the national government "
                      "into three branches: Congress makes the laws, the president carries them "
                      "out, and the courts decide cases. And it leaves to the states, or to the "
                      "people, the powers it does not give the national government (the Tenth "
                      "Amendment). Each state, in turn, creates its own local governments."),
                ("table", {
                    "caption": ("Counts from the Census Bureau's 2022 Census of Governments, and "
                                "the Bureau of Indian Affairs' list of January 30, 2026."),
                    "head": ["Level", "Makes the laws", "Runs the government", "Decides cases",
                             "How many"],
                    "rows": [
                        ["Federal",
                         "[Congress](guide:congress): the Senate and the House of Representatives",
                         "[The president](guide:executive), 15 executive departments and many "
                         "agencies",
                         "[The federal courts](guide:courts): the Supreme Court, 13 courts of "
                         "appeals, 94 district courts",
                         "1"],
                        ["[States](guide:states)",
                         "A legislature of two chambers (one in Nebraska)",
                         "A governor and, in most states, other officials elected statewide",
                         "A supreme court (two highest courts in Texas and Oklahoma), appeals "
                         "courts and trial courts",
                         "50"],
                        ["[Counties](guide:local#counties)",
                         "A board of commissioners or supervisors, or a county council",
                         "The board itself, an administrator it appoints, or an elected county "
                         "executive",
                         "State trial courts, usually organized county by county",
                         "3,031"],
                        ["[Cities, towns and villages](guide:local#municipalities)",
                         "A city council or board of aldermen, or a commission",
                         "A mayor, a manager the council appoints, or the commissioners",
                         "Municipal courts in many places",
                         "19,491"],
                        ["[Towns and townships](guide:local#townships)",
                         "A township board, or a town meeting of the voters",
                         "The board, or an elected select board",
                         "State courts",
                         "16,214, in 20 states"],
                        ["[School districts](guide:local#schools)",
                         "An elected school board",
                         "A superintendent the board appoints",
                         "State courts",
                         "12,546"],
                        ["[Special districts](guide:local#special)",
                         "A board of directors, trustees or commissioners",
                         "A general manager or executive director",
                         "State courts",
                         "39,555"],
                        ["[Tribal nations](guide:tribal)",
                         "A tribal council, or a general council of all adult citizens",
                         "A chair, president, governor or principal chief",
                         "Tribal courts and peacemaking; Courts of Indian Offenses where a tribe "
                         "has no court of its own",
                         "575"],
                    ],
                }),
                ("p", "In all, the Census Bureau counted 90,837 local governments in 2022. Its "
                      "count for 2025, published in May 2026, is 91,438, mostly because of new "
                      "special districts."),
                ("cards", [
                    ("How Congress works", "guide:congress",
                     "The Senate and the House: what each does, who runs them, and who chairs "
                     "each committee now."),
                    ("The president and the executive branch", "guide:executive",
                     "The presidency, the Executive Office, the 15 departments and the "
                     "independent agencies."),
                    ("The federal courts", "guide:courts",
                     "The Supreme Court, the courts of appeals and district courts, and the "
                     "courts Congress has created outside Article III."),
                    ("State governments", "guide:states",
                     "Legislatures, governors and the other officials states elect, executive "
                     "councils, and state courts."),
                    ("Local governments", "guide:local",
                     "Counties, cities, towns and townships, school districts and special "
                     "districts."),
                    ("Tribal nations", "guide:tribal",
                     "Sovereignty, tribal governments and courts, and who has jurisdiction in "
                     "Indian country."),
                ]),
                ("p", "Know Your Candidate follows one part of all this: the members of the "
                      "119th Congress, and everyone who has filed to run for their seats in "
                      "November 2026. Start from the [profile grid](site:index.html), the "
                      "[partisan map](site:map.html) or [your state's page](site:states/index.html)."),
            ],
            "sources": ["const-art1", "const-art2", "const-art3", "const-amdt10", "cog-report",
                        "bia-list"],
        },
        {
            "id": "together",
            "heading": "How the levels fit together",
            "blocks": [
                ("h3", "Checks within the federal government"),
                ("p", "No money may be drawn from the Treasury except as Congress appropriates it "
                      "by law (Article I, Section 9), which gives Congress control over what "
                      "every agency may spend. The courts can set aside a law or an official act "
                      "that conflicts with the Constitution, a power the Supreme Court asserted in "
                      "Marbury v. Madison (1803)."),
                ("h3", "The federal government and the states"),
                ("p", "Federal law made under the Constitution overrides conflicting state law "
                      "(Article VI). But the federal government has only the powers the "
                      "Constitution grants, and it may not order state officers to carry out "
                      "federal programs (Printz v. United States, 1997). Instead, Congress often "
                      "attaches conditions to money it offers the states, for highways, schools "
                      "or health care. The Supreme Court has set limits on those conditions too "
                      "(South Dakota v. Dole, 1987; NFIB v. Sebelius, 2012)."),
                ("h3", "Two court systems"),
                ("p", "State courts have the final word on what state law means. The U.S. Supreme "
                      "Court may review a state court decision that turns on federal law, but not "
                      "one that rests on an adequate and independent ground in state law "
                      "(Michigan v. Long, 1983). A civil case filed in state court can be moved "
                      "(“removed”) to federal court if it could have been filed there in the "
                      "first place: because it arises under federal law, for example, or is "
                      "between citizens of different states (28 U.S.C. 1441). A criminal case can "
                      "be removed only in narrow circumstances, chiefly when the defendant is a "
                      "federal officer (28 U.S.C. 1442)."),
                ("h3", "States and their local governments"),
                ("p", "Local governments are created by their state and have only the powers it "
                      "gives them. Under Dillon's Rule, named for an Iowa judge's 1868 opinion, a "
                      "local government may exercise only the powers granted to it expressly, "
                      "those necessarily or fairly implied in them, and those essential to its "
                      "purposes. Many states instead give some or all of their cities and "
                      "counties home rule: the power to act on local matters without specific "
                      "permission. Either way, the legislature can limit or override local "
                      "ordinances, and state law generally prevails on matters of statewide "
                      "concern. [More on local governments](guide:local#powers)."),
                ("p", "Executive power is divided inside most states too: the attorney general, "
                      "secretary of state and other officials are often elected separately from "
                      "the governor, and may belong to a different party ([state "
                      "governments](guide:states#executive)). County sheriffs and prosecutors, "
                      "elected in most states, enforce state law inside and outside city limits "
                      "alike."),
                ("h3", "Tribal nations"),
                ("p", "Tribal nations are neither states nor parts of states. They deal with the "
                      "federal government government-to-government, and criminal jurisdiction in "
                      "Indian country is divided among tribal, federal and state governments by "
                      "statutes and court decisions. [Who has jurisdiction](guide:tribal#jurisdiction)."),
            ],
            "sources": ["const-art1", "const-art6", "marbury", "printz", "dole", "nfib",
                        "michigan-long", "usc-28-1441", "usc-28-1442", "nlc-delegation",
                        "naco-primer"],
        },
    ],
}


CONGRESS = {
    "slug": "congress",
    "nav": "Congress",
    "people": True,
    "title": "How Congress works",
    "description": ("What Congress does, how the Senate and the House differ, who runs each "
                    "chamber, the officers and agencies that serve them, and who chairs each "
                    "committee today."),
    "lede": ("Article I of the Constitution gives the power to make federal law to Congress: a "
             "Senate, in which every state has two votes, and a House of Representatives, in "
             "which seats follow population. Who sits there now is on the [profile "
             "grid](site:index.html) and the [partisan map](site:map.html)."),
    "sections": [
        {
            "id": "powers",
            "heading": "What Congress does",
            "blocks": [
                ("p", "All federal legislative power belongs to Congress (Article I, Section 1). "
                      "Section 8 lists its powers: among them to tax and spend, to borrow, to "
                      "regulate commerce with foreign nations, among the states and with Indian "
                      "tribes, to declare war, and to raise and support the armed forces. No "
                      "money may be spent from the Treasury unless Congress has appropriated it "
                      "(Section 9), which gives Congress control over how much each agency may "
                      "spend."),
                ("p", "A bill becomes law when both chambers pass it in the same words and the "
                      "president signs it, or does not return it within ten days (Sundays "
                      "excepted) while Congress is in session. If the president vetoes it, "
                      "Congress can override the veto by a two-thirds vote in each chamber "
                      "(Section 7)."),
                ("p", "Congress also oversees how the laws are carried out, through hearings, "
                      "investigations and reports, and it can remove federal officers: the House "
                      "impeaches by a majority vote, and the Senate tries the case, where "
                      "conviction takes two-thirds of the senators present (Article I, Sections 2 "
                      "and 3; Article II, Section 4)."),
            ],
            "sources": ["const-art1", "const-art2"],
        },
        {
            "id": "senate",
            "heading": "The Senate",
            "blocks": [
                ("p", "The Senate has 100 members, two from each state, elected by the state's "
                      "voters (Seventeenth Amendment) to six-year terms. The terms are staggered, "
                      "so about a third of the seats are up every two years. [Which seats are up "
                      "in 2026](site:index.html#/?view=senate)."),
                ("p", "The Senate alone gives or withholds its advice and consent: a treaty needs "
                      "two-thirds of the senators present, and the president's nominations of "
                      "ambassadors, judges, cabinet secretaries and other officers need a "
                      "majority (Article II, Section 2). It also tries impeachments."),
                ("h3", "Who runs it"),
                ("roles", [
                    ("President of the Senate",
                     "The vice president of the United States, who may preside and votes only "
                     "to break a tie (Article I, Section 3)."),
                    ("President pro tempore",
                     "Elected by the Senate to preside when the vice president is absent; by "
                     "custom, the longest-serving senator of the majority party. Third in the "
                     "line of presidential succession, after the vice president and the Speaker "
                     "of the House (3 U.S.C. 19)."),
                    ("Majority leader",
                     "Chosen by the majority party's senators. By the Senate's precedents the "
                     "presiding officer recognizes the majority leader first, which lets the "
                     "leader decide what the Senate takes up and when, move to end debate "
                     "(cloture), and negotiate the unanimous-consent agreements under which "
                     "most of its business is done."),
                    ("Minority leader",
                     "Chosen by the minority party's senators to lead their side in debate and "
                     "in negotiation with the majority."),
                    ("Whips",
                     "Each party's assistant leader, who counts votes and keeps senators "
                     "informed of what is coming."),
                    ("Committee chairs and ranking members",
                     "The majority party chairs every committee and controls its agenda: "
                     "hearings, investigations, markups of bills and, in the Senate, "
                     "confirmation hearings for nominees. The senior member of the minority is "
                     "the ranking member. [Who holds each post now](#committees)."),
                ]),
                ("h3", "Officers who are not senators"),
                ("roles", [
                    ("Secretary of the Senate",
                     "Elected by the Senate. Keeps its journal and records, receives its bills, "
                     "and manages its finances and payroll."),
                    ("Sergeant at Arms",
                     "The Senate's chief law enforcement and protocol officer: keeps order, "
                     "oversees security with the Capitol Police, and can be directed to compel "
                     "absent senators to attend."),
                    ("Parliamentarian",
                     "Advises the presiding officer, without regard to party, on the Senate's "
                     "rules and precedents, including what a budget reconciliation bill may "
                     "contain under the Congressional Budget Act."),
                    ("Legal and legislative counsel",
                     "The Office of Senate Legal Counsel represents the Senate in court; the "
                     "Office of the Legislative Counsel drafts bills and amendments for "
                     "senators."),
                ]),
            ],
            "sources": ["const-art1", "const-art2", "const-amdt17", "usc-3-19",
                        "senate-leadership", "senate-officers"],
        },
        {
            "id": "house",
            "heading": "The House of Representatives",
            "blocks": [
                ("p", "The House has 435 voting members, each elected from a district to a "
                      "two-year term. Seats are divided among the states by population after "
                      "each census, and every state has at least one (Article I, Section 2). "
                      "Since every term ends together, all 435 voting seats are on the ballot "
                      "every two years. Six more members can serve and vote on committees but "
                      "not on the House floor: delegates from the District of Columbia, Guam, "
                      "the U.S. Virgin Islands, American Samoa and the Northern Mariana Islands, "
                      "and Puerto Rico's resident commissioner, who serves four years. "
                      "[Each state's districts](site:states/index.html)."),
                ("p", "Bills for raising revenue must start in the House (Article I, Section 7), "
                      "and the House alone can impeach (Article I, Section 2)."),
                ("h3", "Who runs it"),
                ("roles", [
                    ("Speaker",
                     "Elected by the whole House, and in practice the leader of its majority. "
                     "Presides and refers bills to committees, and through the majority's "
                     "control of the Rules Committee, which sets the terms of debate for most "
                     "major bills, largely decides what reaches the floor. Second in the line "
                     "of presidential succession (3 U.S.C. 19)."),
                    ("Majority and minority leaders",
                     "Chosen by each party. The majority leader schedules the House's business "
                     "with the Speaker; the minority leader leads the other side."),
                    ("Whips",
                     "Count and gather votes for each party's position."),
                    ("Committee chairs and ranking members",
                     "As in the Senate, the majority chairs every committee and the ranking "
                     "member leads the minority's side. [Who holds each post now](#committees)."),
                ]),
                ("h3", "Officers who are not members"),
                ("roles", [
                    ("Clerk",
                     "Keeps the House's records, receives and certifies its bills, runs its "
                     "electronic voting and publishes the roll calls."),
                    ("Sergeant at Arms",
                     "Keeps order on the floor under the Speaker's direction and oversees "
                     "security with the Capitol Police."),
                    ("Chief Administrative Officer",
                     "Runs the House's finances, payroll, technology and purchasing."),
                    ("Parliamentarian",
                     "Advises, without regard to party, on the House's rules and precedents, "
                     "including whether an amendment is germane."),
                    ("Chaplain",
                     "Opens each day's session with a prayer and offers pastoral care."),
                ]),
            ],
            "sources": ["const-art1", "usc-3-19", "house-explained", "house-leadership",
                        "house-officers"],
        },
        {
            "id": "committees",
            "heading": "Committees, and who leads them now",
            "blocks": [
                ("p", "Most of Congress's work is done in committees. Standing committees are "
                      "permanent and each covers a set of subjects; select and special "
                      "committees are created for a particular purpose; joint committees have "
                      "members from both chambers. A committee holds hearings, investigates, and "
                      "“marks up” bills, revising them before the full chamber votes."),
                ("live", "committees",
                 "With JavaScript on, this page lists who chairs every committee now and who "
                 "leads its minority. Each member's committee posts are also on their profile."),
                ("p", "Each name opens that member's profile. The posts come from the committee "
                      "rosters kept by the congress-legislators project, the same source as every "
                      "profile's committee list. The Senate and the House each list their party "
                      "leaders: [Senate leadership](https://www.senate.gov/senators/leadership.htm), "
                      "[House leadership](https://www.house.gov/leadership)."),
            ],
            "sources": ["congress-committees", "congress-legislators", "senate-leadership",
                        "house-leadership"],
        },
        {
            "id": "support",
            "heading": "Congress's own agencies",
            "blocks": [
                ("roles", [
                    ("Government Accountability Office",
                     "Audits and investigates how federal agencies spend money and run "
                     "programs, mostly at Congress's request. It is led by the Comptroller "
                     "General, appointed by the president with the Senate's consent to a "
                     "15-year term (31 U.S.C. 703)."),
                    ("Congressional Budget Office",
                     "Produces nonpartisan budget and economic projections and estimates what "
                     "bills would cost, known as scores."),
                    ("Congressional Research Service",
                     "Part of the Library of Congress. Provides confidential, nonpartisan "
                     "research and analysis to members and committees."),
                    ("Architect of the Capitol",
                     "Maintains and preserves the Capitol and the buildings and grounds around "
                     "it."),
                ]),
            ],
            "sources": ["usc-31-703", "gao", "cbo", "crs", "aoc"],
        },
    ],
}


EXECUTIVE = {
    "slug": "executive",
    "nav": "The executive",
    "title": "The president and the executive branch",
    "description": ("What the president and vice president do, the Executive Office of the "
                    "President, the 15 executive departments, and the independent agencies, "
                    "commissions and government corporations."),
    "lede": ("Article II vests the executive power in one person, the president. The federal "
             "government elects only the president and vice president; most states elect "
             "several executive officials separately ([state governments](guide:states#executive))."),
    "sections": [
        {
            "id": "president",
            "heading": "The president and vice president",
            "blocks": [
                ("p", "The president is elected to a four-year term and may be elected no more "
                      "than twice (Twenty-second Amendment). The president commands the armed "
                      "forces; may grant reprieves and pardons for federal offenses, except in "
                      "cases of impeachment; makes treaties with the consent of two-thirds of the "
                      "senators present; and appoints ambassadors, judges and other officers with "
                      "the Senate's consent (Article II, Section 2). The president signs or "
                      "vetoes the bills Congress passes (Article I, Section 7) and must “take "
                      "Care that the Laws be faithfully executed” (Article II, Section 3)."),
                ("p", "Executive orders are the president's directions to the executive branch. "
                      "The Constitution does not mention them: each must rest on the president's "
                      "own constitutional powers or on authority Congress has given by law, and "
                      "courts can set aside one that rests on neither (Youngstown Sheet & Tube "
                      "Co. v. Sawyer, 1952)."),
                ("p", "The vice president becomes president if the office falls vacant "
                      "(Twenty-fifth Amendment), and presides over the Senate, breaking ties "
                      "there. After the vice president, the line of succession runs to the "
                      "Speaker of the House, the Senate's president pro tempore, and then the "
                      "cabinet secretaries in the order their departments were created (3 U.S.C. "
                      "19)."),
            ],
            "sources": ["const-art1", "const-art2", "const-amdt22", "const-amdt25", "usc-3-19",
                        "youngstown"],
        },
        {
            "id": "eop",
            "heading": "The Executive Office of the President",
            "blocks": [
                ("p", "The president's own staff and advisers make up the Executive Office of the "
                      "President. Among them:"),
                ("roles", [
                    ("White House chief of staff",
                     "Runs the president's staff and schedule, and is often a principal "
                     "negotiator with Congress."),
                    ("Office of Management and Budget",
                     "Prepares the budget the president sends Congress, oversees how agencies "
                     "manage and spend, and through its Office of Information and Regulatory "
                     "Affairs reviews significant regulations before they are issued. Its "
                     "director is confirmed by the Senate (31 U.S.C. 502)."),
                    ("National Security Council",
                     "The president's forum for defense, intelligence and foreign policy, run "
                     "by the national security advisor."),
                    ("White House Counsel",
                     "Advises the president and the White House on legal questions, including "
                     "nominations, pardons and requests from congressional investigators."),
                ]),
            ],
            "sources": ["eo-8248", "usc-31-502", "usc-50-3021"],
        },
        {
            "id": "departments",
            "heading": "The executive departments",
            "blocks": [
                ("p", "There are 15 executive departments (5 U.S.C. 101). Each is headed by a "
                      "secretary, except Justice, which is headed by the attorney general; all "
                      "are nominated by the president and confirmed by the Senate. With the vice "
                      "president they make up the cabinet, to which presidents also add other "
                      "officials. They are listed here in the order of presidential succession."),
                ("table", {
                    "head": ["Department", "Headed by", "What it does, for example"],
                    "rows": [
                        ["State", "Secretary of State",
                         "Foreign relations, embassies and passports"],
                        ["Treasury", "Secretary of the Treasury",
                         "Taxes (the Internal Revenue Service), the national debt, sanctions, "
                         "and printing and minting money"],
                        ["Defense", "Secretary of Defense",
                         "The armed forces. Since 2025 it may also use the title Department of "
                         "War ([see below](#changes))."],
                        ["Justice", "Attorney General",
                         "Federal prosecutions, the government's lawsuits, civil rights "
                         "enforcement, the FBI and federal prisons"],
                        ["Interior", "Secretary of the Interior",
                         "Federal lands (the Bureau of Land Management and National Park "
                         "Service), water projects, and the Bureau of Indian Affairs"],
                        ["Agriculture", "Secretary of Agriculture",
                         "Farm programs, meat and poultry inspection, food assistance (SNAP) and "
                         "the Forest Service"],
                        ["Commerce", "Secretary of Commerce",
                         "The census, patents (USPTO), weather and oceans (NOAA) and measurement "
                         "standards (NIST)"],
                        ["Labor", "Secretary of Labor",
                         "Workplace safety (OSHA), wage and hour laws, and employment statistics"],
                        ["Health and Human Services", "Secretary of Health and Human Services",
                         "Medicare and Medicaid, drug approval (FDA), disease control (CDC) and "
                         "medical research (NIH)"],
                        ["Housing and Urban Development",
                         "Secretary of Housing and Urban Development",
                         "Public housing, mortgage insurance (FHA), community development grants "
                         "and fair housing"],
                        ["Transportation", "Secretary of Transportation",
                         "Aviation (FAA), highways, railroads, transit and shipping"],
                        ["Energy", "Secretary of Energy",
                         "Nuclear weapons (NNSA), the national laboratories and energy research"],
                        ["Education", "Secretary of Education",
                         "Student aid, grants to schools, and civil rights in education. Some "
                         "of its programs are now run by other departments ([see "
                         "below](#changes))."],
                        ["Veterans Affairs", "Secretary of Veterans Affairs",
                         "Veterans' health care, disability benefits and national cemeteries"],
                        ["Homeland Security", "Secretary of Homeland Security",
                         "Border and immigration enforcement (CBP and ICE), disasters (FEMA), "
                         "cybersecurity (CISA) and airport screening (TSA)"],
                    ],
                }),
                ("h3", "Changes since 2025", "changes"),
                ("p", "Executive Order 14347 of September 5, 2025 lets the Department of Defense "
                      "and its secretary use “Department of War” and “Secretary of War” as "
                      "secondary titles, in correspondence, public communications, ceremonies "
                      "and documents other than statutes. The department's name in law is still "
                      "the Department of Defense (10 U.S.C. 111). On July 22, 2026 the House "
                      "passed a defense authorization bill that would rename it; on July 14 the "
                      "Senate had declined, 50-46, to take up its own version, and the rename "
                      "has not become law."),
                ("p", "The Department of Education still exists in law (20 U.S.C. 3411), and "
                      "Congress has not passed a bill to abolish it. Since 2025 it has handed "
                      "the day-to-day running of many of its programs to other departments "
                      "under interagency agreements. Among them: career, technical and adult "
                      "education, and from November 2025 Title I and other school and college "
                      "grant programs, to Labor; Indian education to Interior; student loans to "
                      "Treasury (March 2026); and, from June 2026, special education to Health "
                      "and Human Services and civil rights enforcement to Justice."),
            ],
            "sources": ["usc-5-101", "usc-3-19", "usc-10-111", "eo-14347", "senate-2026-07-14",
                        "crs-in12704", "usc-20-3411", "ed-2025-11", "ed-treasury", "ed-2026-06"],
        },
        {
            "id": "agencies",
            "heading": "Independent agencies, commissions and corporations",
            "blocks": [
                ("roles", [
                    ("Independent agencies",
                     "Agencies outside the 15 departments, each led by a single administrator "
                     "who serves at the president's pleasure: the Environmental Protection "
                     "Agency, NASA and the Central Intelligence Agency, for example."),
                    ("Regulatory commissions",
                     "Boards of several members serving staggered terms, often with a limit "
                     "on how many may belong to one party: the Federal Trade Commission, the "
                     "Securities and Exchange Commission, the Federal Communications Commission "
                     "and the Federal Reserve Board, for example."),
                    ("Government corporations",
                     "Enterprises the government owns or created: the U.S. Postal Service, an "
                     "independent establishment of the executive branch governed by a Board of "
                     "Governors, and Amtrak, which by law is not a federal agency."),
                ]),
                ("h3", "Can the president remove a commissioner?", "removal"),
                ("p", "Congress has written into some agencies' laws that their members may be "
                      "removed only “for cause”: for the Federal Trade Commission, for "
                      "“inefficiency, neglect of duty, or malfeasance in office” (15 U.S.C. 41). "
                      "In Trump v. Slaughter, decided on June 29, 2026, the Supreme Court held "
                      "6-3 that the FTC's protection violates the separation of powers, and "
                      "overruled whatever remained of Humphrey's Executor v. United States "
                      "(1935), the case that had upheld it. The Court said it was not deciding "
                      "the Federal Reserve's case, or that of judges on courts outside Article "
                      "III ([such as the Tax Court](guide:courts#other-courts))."),
                ("p", "The Federal Reserve's governors may also be removed only for cause (12 "
                      "U.S.C. 242). The same day, in Trump v. Cook, the Court refused 5-4 to let "
                      "the president remove a governor while her lawsuit continues, and said "
                      "that the governors' protection is consistent with the Constitution; that "
                      "case has not been finally decided. A year earlier, in Trump v. Wilcox "
                      "(May 22, 2025), the Court had let the president remove members of the "
                      "National Labor Relations Board and the Merit Systems Protection Board "
                      "while their cases went on, describing the Federal Reserve as a "
                      "“uniquely structured, quasi-private entity”."),
            ],
            "sources": ["usc-15-41", "usc-12-242", "usc-39-201", "usc-49-24301", "slaughter",
                        "cook", "wilcox"],
        },
    ],
}


COURTS = {
    "slug": "courts",
    "nav": "Federal courts",
    "title": "The federal courts",
    "description": ("The Supreme Court, the 13 courts of appeals and 94 district courts, the "
                    "courts Congress has created outside Article III, and how federal judges "
                    "are chosen."),
    "lede": ("Article III vests the judicial power of the United States in one Supreme Court "
             "and the lower courts Congress creates. Federal courts hear cases under federal "
             "law and the Constitution, and many disputes between citizens of different "
             "states; [state courts](guide:states#courts) hear most of the rest."),
    "sections": [
        {
            "id": "judges",
            "heading": "Article III judges",
            "blocks": [
                ("p", "Supreme Court justices, and the judges of the courts of appeals, the "
                      "district courts and the Court of International Trade, are nominated by the "
                      "president and confirmed by the Senate. They hold office “during good "
                      "Behaviour”: in effect for life, unless they resign, retire, or are "
                      "impeached and removed. Their pay cannot be cut while they serve (Article "
                      "III, Section 1)."),
                ("p", "A judge who meets the law's test of age and years of service may take "
                      "senior status: the judge keeps the office and hears a reduced caseload, "
                      "and the seat can be filled by a new appointment (28 U.S.C. 371)."),
            ],
            "sources": ["const-art3", "usc-28-371", "uscourts-structure"],
        },
        {
            "id": "supreme-court",
            "heading": "The Supreme Court",
            "blocks": [
                ("p", "The Court has nine members, the Chief Justice of the United States and "
                      "eight associate justices. The number is set by law (28 U.S.C. 1), not by "
                      "the Constitution. A few cases, such as disputes between states, can begin "
                      "there (Article III, Section 2). Nearly all the rest come from the federal "
                      "courts of appeals and from state supreme courts on questions of federal "
                      "law, and the Court chooses which to hear by granting a petition for a "
                      "writ of certiorari."),
                ("p", "The Chief Justice presides over the Judicial Conference of the United "
                      "States, which sets policy for the federal courts, and chairs the board of "
                      "the Federal Judicial Center, their research and education agency (28 "
                      "U.S.C. 331, 621). When a president is tried on impeachment, the Chief "
                      "Justice presides in the Senate (Article I, Section 3)."),
            ],
            "sources": ["const-art3", "const-art1", "usc-28-1", "usc-28-331", "usc-28-621"],
        },
        {
            "id": "appeals",
            "heading": "The courts of appeals",
            "blocks": [
                ("p", "There are 13 courts of appeals. Eleven numbered circuits and the D.C. "
                      "Circuit each hear appeals from the district courts in their region. The "
                      "Court of Appeals for the Federal Circuit hears appeals from across the "
                      "country in particular kinds of case, such as patents, international trade "
                      "and claims for money against the United States (28 U.S.C. 41, 1295). "
                      "Congress has authorized 179 judgeships on the courts of appeals: 167 on "
                      "the regional circuits and 12 on the Federal Circuit."),
                ("p", "Appeals are usually decided by panels of three judges. A court may rehear "
                      "a case en banc, with all its active judges, or in the Ninth Circuit a panel "
                      "of eleven. Each circuit's chief judge is chosen by seniority: the "
                      "longest-serving active judge who is 64 or younger, has served at least a "
                      "year and has not been chief judge before (28 U.S.C. 45)."),
            ],
            "sources": ["usc-28-41", "usc-28-1295", "usc-28-45", "uscourts-structure",
                        "uscourts-judgeships"],
        },
        {
            "id": "district",
            "heading": "District courts and other trial courts",
            "blocks": [
                ("p", "The district courts are the federal trial courts. There are 94: 89 in the "
                      "50 states, one each for the District of Columbia and Puerto Rico, and "
                      "three territorial courts, for Guam, the Northern Mariana Islands and the "
                      "U.S. Virgin Islands, whose judges serve ten-year terms. Every state has at "
                      "least one. Congress has authorized 673 district judgeships, and 4 more in "
                      "the territorial courts."),
                ("p", "The Court of International Trade, in New York, hears civil cases about "
                      "tariffs, customs and trade laws from anywhere in the country (28 U.S.C. "
                      "251)."),
                ("roles", [
                    ("Magistrate judges",
                     "Appointed by each district court's judges, for eight years if full-time "
                     "and four if part-time (28 U.S.C. 631). They handle warrants, first "
                     "appearances, bail and pretrial matters, and can try misdemeanors and, if "
                     "the parties agree, civil cases."),
                    ("Bankruptcy judges",
                     "The 90 bankruptcy courts are units of the district courts (28 U.S.C. "
                     "151). Their judges are appointed by the court of appeals for the circuit "
                     "to 14-year terms (28 U.S.C. 152)."),
                ]),
            ],
            "sources": ["uscourts-structure", "uscourts-judgeships", "usc-28-251", "usc-28-631",
                        "usc-28-151", "usc-28-152"],
        },
        {
            "id": "other-courts",
            "heading": "Courts outside Article III",
            "blocks": [
                ("p", "Under its other powers, Congress has created courts whose judges serve "
                      "fixed terms, without Article III's protections:"),
                ("roles", [
                    ("U.S. Tax Court",
                     "Nineteen judges, appointed by the president with the Senate's consent to "
                     "15-year terms. Taxpayers can dispute a tax deficiency there before paying "
                     "it (26 U.S.C. 7443)."),
                    ("U.S. Court of Federal Claims",
                     "Sixteen judges with 15-year terms. Hears claims for money against the "
                     "United States, challenges to federal contract awards, and vaccine-injury "
                     "petitions (28 U.S.C. 171)."),
                    ("U.S. Court of Appeals for Veterans Claims",
                     "Reviews decisions of the Board of Veterans' Appeals. The law provides for "
                     "up to seven permanent judges, each with a 15-year term (38 U.S.C. 7253)."),
                    ("U.S. Court of Appeals for the Armed Forces",
                     "Five civilian judges with 15-year terms. The highest court for "
                     "courts-martial below the Supreme Court (10 U.S.C. 942)."),
                    ("Foreign Intelligence Surveillance Court",
                     "Eleven district judges, designated by the Chief Justice for terms of up to "
                     "seven years, decide the government's applications for surveillance and "
                     "searches for foreign intelligence. A Court of Review of three judges "
                     "hears appeals (50 U.S.C. 1803)."),
                    ("Territorial courts",
                     "The district courts of Guam, the Northern Mariana Islands and the Virgin "
                     "Islands were created under Congress's power over the territories "
                     "(Article IV), not Article III, so their judges serve ten-year terms."),
                    ("Administrative law judges",
                     "Officers inside agencies such as the Social Security Administration, the "
                     "National Labor Relations Board and the Securities and Exchange "
                     "Commission, who hold hearings and decide cases under the Administrative "
                     "Procedure Act (5 U.S.C. 3105). Their decisions can generally be appealed "
                     "within the agency and then to a court."),
                ]),
                ("p", "When the Supreme Court held in 2026 that Federal Trade Commissioners cannot "
                      "be protected from removal by the president, it left open whether "
                      "Congress may protect the judges of courts like these ([removal "
                      "protection](guide:executive#removal))."),
            ],
            "sources": ["usc-26-7443", "usc-28-171", "usc-38-7253", "usc-10-942", "usc-50-1803",
                        "const-art4", "usc-5-3105", "uscourts-structure", "slaughter"],
        },
    ],
}


STATES = {
    "slug": "states",
    "nav": "State governments",
    "title": "State governments",
    "description": ("How state governments are organized: legislatures and who presides over "
                    "them, governors and the other officials states elect, executive councils, "
                    "and state courts."),
    "lede": ("Each state has its own constitution, legislature, governor and courts. The Tenth "
             "Amendment reserves to the states, or to the people, the powers the Constitution "
             "does not give the federal government, so much of the law of daily life, from most "
             "criminal law to family law, contracts, property, schools and licensing, is state "
             "law. [Your state's page](site:states/index.html) lists who represents it in "
             "Congress."),
    "sections": [
        {
            "id": "powers",
            "heading": "What states can do",
            "blocks": [
                ("p", "States hold what courts call the police power: broad authority to make "
                      "laws for public health, safety and welfare, limited by the U.S. "
                      "Constitution, federal law and the state's own constitution. Each state "
                      "constitution sets up a legislature, an executive and courts, and many go "
                      "into far more detail than the federal one, on taxes, debt, education and "
                      "local government."),
            ],
            "sources": ["const-amdt10", "wex-police"],
        },
        {
            "id": "legislatures",
            "heading": "Legislatures",
            "blocks": [
                ("p", "Every state but Nebraska has a legislature of two chambers. The upper "
                      "chamber is the Senate. The lower is the House of Representatives in most "
                      "states; the Assembly in California, Nevada, New York and Wisconsin; the "
                      "General Assembly in New Jersey; and the House of Delegates in Maryland, "
                      "Virginia and West Virginia. Nebraska's single chamber has 49 members, "
                      "called senators, elected without party labels on the ballot."),
                ("p", "Who presides varies. In about 26 states the lieutenant governor is the "
                      "president of the senate; elsewhere the senate elects its own president. "
                      "Lower chambers elect a speaker, who usually controls committee "
                      "assignments, the referral of bills and the floor calendar. In Texas the "
                      "lieutenant governor presides over the Senate and, with the Speaker of the "
                      "House, jointly chairs the Legislative Budget Board (Tex. Gov't Code "
                      "322.001)."),
                ("p", "Nonpartisan staff support the legislators: legislative counsel or revisors "
                      "draft bills and keep the state's code of laws; fiscal offices estimate what "
                      "bills cost; auditors review state agencies; and each chamber's clerk or "
                      "secretary keeps its journal and records its votes."),
            ],
            "sources": ["nebraska", "ncsl-leaders", "tx-322", "tx-lbb"],
        },
        {
            "id": "executive",
            "heading": "Governors, and the other officials states elect",
            "blocks": [
                ("p", "The federal government elects one executive. Most states elect several: "
                      "besides the governor, voters choose some combination of a lieutenant "
                      "governor, attorney general, secretary of state, treasurer, auditor or "
                      "comptroller, and in some states a superintendent of schools or "
                      "commissioners of agriculture, insurance, labor or public utilities. Each "
                      "answers to the voters rather than to the governor, and they need not "
                      "belong to the governor's party. This is often called a plural executive."),
                ("chart", {
                    "top": "Voters statewide",
                    "items": [
                        ("Governor", "Chief executive; appoints most agency heads"),
                        ("Lieutenant governor", "First in line to succeed the governor"),
                        ("Attorney general", "The state's chief legal officer"),
                        ("Secretary of state", "State records and business filings; elections in "
                                               "many states"),
                        ("Treasurer", "Holds and invests the state's money"),
                    ],
                    "caption": ("A common arrangement. Which officers are elected, and what "
                                "each does, differs from state to state."),
                }),
                ("h3", "The governor"),
                ("p", "The governor is the state's chief executive and commands its National "
                      "Guard when the Guard is not in federal service. Governors sign or veto "
                      "bills, and 44 of them can also veto individual items in spending bills, a "
                      "line-item veto. The six who cannot are the governors of Indiana, Nevada, "
                      "New Hampshire, North Carolina, Rhode Island and Vermont. Some governors can "
                      "reduce an appropriation instead of striking it, or return a bill with "
                      "changes for the legislature to accept (an amendatory veto). Governors also "
                      "issue executive orders, declare emergencies, and grant pardons and other "
                      "clemency, in many states together with a board."),
                ("h3", "Other statewide officials"),
                ("roles", [
                    ("Lieutenant governor",
                     "Usually first in line to succeed the governor, and in about 26 states the "
                     "president of the senate. A few states have none."),
                    ("Attorney general",
                     "The state's chief legal officer: represents the state and its agencies in "
                     "court, defends its laws, enforces consumer-protection and other laws, and "
                     "issues legal opinions. Elected in most states."),
                    ("Secretary of state",
                     "Keeps the state's official records and business filings, and in most "
                     "states is the chief election official: elected to that role in 31 "
                     "states and appointed to it in several more. In Alaska and Utah the "
                     "elected lieutenant governor runs elections instead, and elsewhere a "
                     "board or another appointed official does."),
                    ("Treasurer, comptroller and auditor",
                     "Hold and invest the state's money, pay its bills, and audit how it was "
                     "spent. Which of these offices exist, and which are elected, varies."),
                    ("Superintendent of public instruction",
                     "Oversees the public schools and state school aid. Elected in some states; "
                     "appointed, or replaced by a board, in most."),
                    ("Commissioners",
                     "Some states elect commissioners of agriculture, insurance or labor, or "
                     "the members of the commission that regulates utilities."),
                ]),
                ("p", "Texas also elects a commissioner of the General Land Office, which manages "
                      "state lands and mineral rights whose income supports public schools, and "
                      "the three members of the Railroad Commission, which, despite its name, "
                      "regulates the state's oil and gas industry and pipelines."),
            ],
            "sources": ["ncsl-veto", "ncsl-leaders", "ncsl-elections", "tx-glo", "tx-rrc"],
        },
        {
            "id": "councils",
            "heading": "Executive councils",
            "blocks": [
                ("p", "Three states give a separately elected council a check on the governor:"),
                ("roles", [
                    ("New Hampshire",
                     "Five executive councilors, elected every two years from districts, must "
                     "consent before the governor appoints judges, the attorney general and "
                     "other officers, grants a pardon, or pays money out of the treasury "
                     "(Constitution, Part Second, Articles 46, 52 and 56). Under the state's "
                     "procedures manual, the Governor and Council also approve state contracts "
                     "over $10,000."),
                    ("Massachusetts",
                     "The eight elected members of the Governor's Council approve judicial "
                     "appointments, pardons and commutations, and the warrants for the state's "
                     "payments."),
                    ("North Carolina",
                     "The Council of State is the state's ten elected executive officers, the "
                     "governor and lieutenant governor among them. Its approval is needed for "
                     "the state to buy, sell or lease land, and to spend from the Contingency "
                     "and Emergency Fund."),
                ]),
            ],
            "sources": ["nh-const", "nh-council", "ma-council", "nc-const-3", "nc-146-22",
                        "nc-146-29", "nc-143c-4-4"],
        },
        {
            "id": "courts",
            "heading": "State courts",
            "blocks": [
                ("p", "State courts hear the great majority of the country's cases, criminal and "
                      "civil. Most states have these levels:"),
                ("table", {
                    "head": ["Level", "Judges", "What it hears"],
                    "rows": [
                        ["Court of last resort, usually called the supreme court",
                         "A chief justice and associate justices",
                         "The final word on the state's constitution and laws: appeals it must "
                         "hear, such as death sentences in many states, and others it chooses to"],
                        ["Intermediate appeals courts, in most states",
                         "Appellate judges, sitting in panels",
                         "Appeals from the trial courts, on whether the law was applied "
                         "correctly; they do not retry the facts"],
                        ["Trial courts of general jurisdiction",
                         "Called district, circuit, superior or common pleas courts; in New York, "
                         "the Supreme Court",
                         "Felonies and larger civil cases"],
                        ["Courts of limited jurisdiction",
                         "Municipal judges, magistrates, justices of the peace",
                         "Misdemeanors, traffic cases, small claims and first appearances"],
                        ["Specialized courts",
                         "Probate, surrogate's, family and juvenile judges",
                         "Wills and estates, guardianships, divorce, custody and juvenile cases"],
                    ],
                }),
                ("p", "Texas and Oklahoma each have two highest courts: a Supreme Court for civil "
                      "cases and a Court of Criminal Appeals for criminal ones. Juvenile cases go "
                      "to the Supreme Court in Texas, but juvenile delinquency appeals go to the "
                      "Court of Criminal Appeals in Oklahoma, where the Supreme Court settles any "
                      "dispute between the two over which should hear a case."),
                ("p", "States choose their judges in several ways: partisan elections, "
                      "nonpartisan elections, appointment by the governor, election by the "
                      "legislature, or merit selection. Under merit selection a commission "
                      "nominates candidates, the governor appoints one, and the judge later "
                      "stands in a retention election; Missouri adopted it in 1940, and it is "
                      "often called the Missouri Plan."),
            ],
            "sources": ["nycourts", "tx-courts", "ok-occa", "ok-const-7", "mo-plan"],
        },
    ],
}


LOCAL = {
    "slug": "local",
    "nav": "Local governments",
    "title": "Local governments",
    "description": ("Counties, cities, towns and townships, school districts and special "
                    "districts: where their powers come from, how they are organized, who runs "
                    "them, and how many there are."),
    "lede": ("Counties, cities and towns, townships, school districts and special districts "
             "are created by their states and exercise the powers their states give them. In "
             "2022 the Census Bureau counted 90,837 of them."),
    "sections": [
        {
            "id": "powers",
            "heading": "Where local power comes from",
            "blocks": [
                ("p", "Local governments are not sovereign: each is a political subdivision of "
                      "its state. Under Dillon's Rule, named for an Iowa judge's 1868 opinion, a "
                      "local government may exercise only the powers granted to it expressly, "
                      "those necessarily or fairly implied in them, and those essential to its "
                      "purposes. It still applies in many states. By the National Association "
                      "of Counties' count, Dillon's Rule governs every county in 14 states, "
                      "every county has home rule in 13, and the other 21 states with county "
                      "governments mix the two."),
                ("p", "Over the twentieth century many states adopted home rule instead, by "
                      "constitution or by statute: a city or county, often one that adopts its "
                      "own charter, may act on local matters without specific permission. In "
                      "every state, though, the legislature can limit or override local "
                      "ordinances, and state law generally prevails on matters of statewide "
                      "concern."),
            ],
            "sources": ["nlc-delegation", "naco-structure", "naco-primer"],
        },
        {
            "id": "counties",
            "heading": "Counties",
            "blocks": [
                ("p", "There were 3,031 county governments in 2022. Louisiana calls its counties "
                      "parishes, and Alaska's organized boroughs are counted as counties. "
                      "Connecticut (since 1960), Rhode Island and the District of Columbia have "
                      "no county governments, and seven of Massachusetts's counties have none."),
                ("p", "Counties carry out state duties, such as running courthouses and jails, "
                      "recording deeds, conducting elections and assessing property, and provide "
                      "local services such as roads, public health and, outside cities, policing. "
                      "They are governed in one of three main forms:"),
                ("table", {
                    "head": ["Form", "Who makes policy", "Who runs the county"],
                    "rows": [
                        ["Commission",
                         "An elected board of commissioners or supervisors, most often of three "
                         "or five members",
                         "The board itself, its members often overseeing departments directly"],
                        ["Council–administrator or council–manager",
                         "An elected board or council",
                         "An administrator or manager the board appoints"],
                        ["Council–executive",
                         "An elected county council",
                         "An elected county executive or mayor, who can usually veto the "
                         "council's ordinances"],
                    ],
                }),
                ("h3", "Officers elected in their own right"),
                ("p", "Many counties also elect officers who answer to the voters rather than to "
                      "the board, under the state constitution or state law. Which offices exist, "
                      "and whether they are elected, varies by state and sometimes by county:"),
                ("roles", [
                    ("Sheriff",
                     "Runs the county jail, serves court papers, secures the courthouse, and "
                     "polices areas outside cities. Elected in 46 states. Alaska and "
                     "Connecticut have no county sheriffs, and in Hawaii and Rhode Island "
                     "sheriffs are state officers."),
                    ("Prosecutor",
                     "Called the district attorney, state's attorney, prosecuting attorney or "
                     "county attorney. Prosecutes crimes under state law and advises county "
                     "officials. Elected in 45 states. Alaska, Connecticut and New Jersey "
                     "appoint theirs, and in Delaware and Rhode Island the elected attorney "
                     "general prosecutes. In the District of Columbia most adult crimes are "
                     "prosecuted by the U.S. Attorney, and some by the District's elected "
                     "attorney general."),
                    ("Clerk or register of deeds",
                     "Records deeds, mortgages and other public documents, and in many states "
                     "runs elections."),
                    ("Treasurer",
                     "Collects property taxes and holds and invests the county's money, often "
                     "passing tax revenue on to schools and other local governments."),
                    ("Assessor",
                     "Sets the value of property for taxation."),
                    ("Coroner or medical examiner",
                     "Investigates sudden, violent or unexplained deaths and certifies their "
                     "cause. Autopsies are done by physicians, usually forensic pathologists; in "
                     "most states a coroner need not be a physician."),
                    ("Auditor or controller",
                     "Checks the county's accounts and approves its payments."),
                ]),
            ],
            "sources": ["cog-report", "cog-isd", "naco-primer", "nsa-faq", "unc-prosecutors",
                        "dc-oag"],
        },
        {
            "id": "municipalities",
            "heading": "Cities, towns and villages",
            "blocks": [
                ("p", "Municipalities, called cities, towns, villages or boroughs depending on the "
                      "state, are incorporated under state law to provide services such as police "
                      "and fire protection, zoning, water and sewers, streets and parks. There "
                      "were 19,491 in 2022. Most are governed in one of these forms:"),
                ("roles", [
                    ("Council–manager",
                     "The elected council, often with a mayor who chairs it, sets policy and the "
                     "budget and appoints a professional manager to run the departments. It was "
                     "the most common form in a 2018 survey by the International City/County "
                     "Management Association: 48 percent of responding municipalities, against "
                     "38 percent for mayor–council."),
                    ("Mayor–council, strong mayor",
                     "An elected mayor is the chief executive, appoints and removes department "
                     "heads, proposes the budget and can veto the council. Common in the "
                     "largest cities and in the smallest towns."),
                    ("Mayor–council, weak mayor",
                     "The mayor chairs the council and represents the city, but the council "
                     "holds most executive power and oversees the departments directly."),
                    ("Commission",
                     "Voters elect commissioners who together act as the council, and each runs "
                     "a department. Devised in Galveston, Texas, after the hurricane of 1900, "
                     "and now uncommon: 3.2 percent of the municipalities in the same survey. "
                     "Portland, Oregon, the largest city still using it, replaced it with a "
                     "mayor and a larger council on January 1, 2025."),
                    ("Town meeting",
                     "In much of New England the town's voters meet, usually once a year, to "
                     "adopt the budget and local laws, and an elected select board runs the "
                     "town in between. Some towns elect members to a representative town "
                     "meeting instead."),
                ]),
                ("h3", "City officials"),
                ("roles", [
                    ("City manager or chief administrative officer",
                     "Runs the city day to day: its staff, budget, projects and services."),
                    ("City attorney",
                     "The city's lawyer: handles its lawsuits, drafts ordinances and advises on "
                     "zoning and liability."),
                    ("Police and fire chiefs",
                     "Lead the police and fire departments; usually appointed."),
                    ("Public works director",
                     "Runs the streets, storm drains, vehicles and often the water and sewer "
                     "systems."),
                    ("City clerk",
                     "Keeps the city's records and the council's minutes; in many places also "
                     "handles local elections and campaign filings."),
                ]),
                ("p", "Many cities have a municipal court for violations of city ordinances, "
                      "traffic and parking cases and, in some states, misdemeanors. Some use "
                      "hearing officers to decide building, housing and health code cases "
                      "instead."),
            ],
            "sources": ["cog-report", "nlc-forms", "icma-2018", "portland"],
        },
        {
            "id": "townships",
            "heading": "Towns and townships",
            "blocks": [
                ("p", "In 20 states, all in the Midwest and Northeast, the Census Bureau counts "
                      "town or township governments below the county: Connecticut, Illinois, "
                      "Indiana, Kansas, Maine, Massachusetts, Michigan, Minnesota, Missouri, "
                      "Nebraska, New Hampshire, New Jersey, New York, North Dakota, Ohio, "
                      "Pennsylvania, Rhode Island, South Dakota, Vermont and Wisconsin. There "
                      "were 16,214 in 2022."),
                ("p", "They range widely. In the Midwest a township may keep up rural roads and "
                      "cemeteries, assess property and give aid to the poor, under an elected "
                      "board of trustees or supervisors and a clerk. In New England, New York, "
                      "New Jersey and Pennsylvania, towns and townships can be full municipal "
                      "governments, some serving dense suburbs."),
            ],
            "sources": ["cog-isd", "cog-report"],
        },
        {
            "id": "schools",
            "heading": "School districts",
            "blocks": [
                ("p", "There were 12,546 independent school districts in 2022: governments in "
                      "their own right, each with an elected board that adopts the budget, sets "
                      "the property tax rate where state law allows, and appoints a "
                      "superintendent to run the schools."),
                ("p", "Elsewhere the schools are run by a city, county or state government, and "
                      "the Census Bureau counts them as part of that government, a dependent "
                      "school system. Alaska, Hawaii, Maryland, North Carolina, Virginia and the "
                      "District of Columbia have only dependent systems."),
            ],
            "sources": ["cog-report", "cog-isd"],
        },
        {
            "id": "special",
            "heading": "Special districts",
            "blocks": [
                ("p", "Special districts are the most numerous kind of local government: 39,555 "
                      "in 2022, and 40,199 by 2025. Each is created under state law, often with a "
                      "local vote, to provide one service or a few across a defined area, and many "
                      "can levy taxes or charge fees and issue bonds."),
                ("table", {
                    "head": ["Kind", "Usually governed by", "Run by", "What it does"],
                    "rows": [
                        ["Transit authority",
                         "A board, often appointed by the governments it serves",
                         "A general manager or chief executive",
                         "Buses, subways and commuter rail across city and county lines"],
                        ["Water, sewer and utility district",
                         "An elected or appointed board",
                         "A general manager or chief engineer",
                         "Water supply, wastewater treatment, flood control, sometimes power"],
                        ["Port authority",
                         "A board appointed by the governments it serves",
                         "An executive director",
                         "Shipping terminals, and in some places airports, bridges and tunnels"],
                        ["Hospital district",
                         "An elected board of trustees",
                         "A hospital chief executive",
                         "Public hospitals and clinics, often paid for in part by a property tax"],
                        ["Fire district",
                         "An elected board of fire commissioners",
                         "A fire chief",
                         "Fire protection, rescue and emergency medical services"],
                    ],
                }),
            ],
            "sources": ["cog-report", "cog-isd"],
        },
    ],
}


TRIBAL = {
    "slug": "tribal",
    "nav": "Tribal nations",
    "title": "Tribal nations",
    "description": ("How tribal nations govern themselves: their sovereignty and recognition, "
                    "tribal governments and courts, and how jurisdiction in Indian country is "
                    "shared with the federal government and the states."),
    "lede": ("There are 575 federally recognized tribes. They are not states, parts of states "
             "or foreign nations: the Supreme Court has called them “domestic dependent "
             "nations”, self-governing communities whose sovereignty predates the "
             "Constitution."),
    "sections": [
        {
            "id": "sovereignty",
            "heading": "Sovereignty and recognition",
            "blocks": [
                ("p", "Tribal sovereignty is inherent: it was not granted by the United States. "
                      "In three early cases, Johnson v. M'Intosh (1823), Cherokee Nation v. "
                      "Georgia (1831) and Worcester v. Georgia (1832), known together as the "
                      "Marshall Trilogy, the Supreme Court described tribes as “domestic "
                      "dependent nations” (Cherokee Nation) and as distinct political communities "
                      "in which state law has no force (Worcester). Congress's broad power over "
                      "Indian affairs rests on the Indian Commerce Clause (Article I, Section 8) "
                      "and the treaty power, and Congress and the courts have since limited "
                      "tribal powers in some respects."),
                ("p", "Federally recognized tribes have a government-to-government relationship "
                      "with the United States, chiefly through the Bureau of Indian Affairs in the "
                      "Department of the Interior. Congress recognized the Lumbee Tribe of North "
                      "Carolina in December 2025, and the Bureau's list of January 30, 2026 has "
                      "575 tribes, up from 574."),
                ("p", "Under the Indian Self-Determination and Education Assistance Act (1975) "
                      "and the Tribal Self-Governance Act (1994), tribes can run federally funded "
                      "programs, such as health care and schools, themselves."),
            ],
            "sources": ["johnson", "cherokee", "worcester", "const-art1", "bia-list", "bia-faq",
                        "usc-25-5301", "usc-25-5361"],
        },
        {
            "id": "governments",
            "heading": "Tribal governments",
            "blocks": [
                ("p", "Tribes organize their governments in many ways: under constitutions of "
                      "their own, under constitutions adopted through the Indian Reorganization "
                      "Act of 1934, or in traditional forms. Many have a council that makes the "
                      "laws, an executive, and courts."),
                ("chart", {
                    "top": "Tribal citizens",
                    "items": [
                        ("Tribal council", "Elected; makes tribal law, the budget, and policy on "
                                           "land and resources"),
                        ("Chair, president, governor or chief",
                         "Elected by the citizens or by the council; leads the government and "
                         "deals with federal, state and local governments"),
                        ("Tribal courts", "Interpret and apply tribal law; some also use "
                                          "traditional peacemaking"),
                    ],
                    "caption": "A common pattern. Many tribes are organized differently.",
                }),
                ("roles", [
                    ("Tribal council or general council",
                     "The lawmaking body, elected by district, clan or at large. In some tribes "
                     "the general council is every adult citizen. It passes the tribe's codes "
                     "and budget and sets policy on land, natural resources, gaming and "
                     "business."),
                    ("Chair, president, governor or principal chief",
                     "The chief executive and the tribe's spokesperson. Runs its departments, "
                     "and negotiates with federal agencies, states (gaming compacts among them) "
                     "and local governments."),
                    ("Vice chair or vice president",
                     "Stands in for the chief executive and often leads parts of the "
                     "administration."),
                    ("Tribal administrator",
                     "A professional manager who runs the tribe's programs, grants and "
                     "enterprises day to day."),
                    ("Tribal police",
                     "Enforce tribal law under the tribe's own authority, often alongside "
                     "federal and state officers."),
                ]),
            ],
            "sources": ["usc-25-5123", "bia-faq"],
        },
        {
            "id": "courts",
            "heading": "Tribal courts",
            "blocks": [
                ("p", "Many tribes run their own justice systems, which the Indian Tribal Justice "
                      "Act (1993) supports with federal funding."),
                ("roles", [
                    ("Tribal trial courts",
                     "Hear cases under tribal law: crimes, family and child-custody matters "
                     "(including cases under the Indian Child Welfare Act), probate and "
                     "contracts."),
                    ("Tribal appeals courts",
                     "Review trial decisions and decide disputes under the tribe's "
                     "constitution."),
                    ("Peacemaking",
                     "Some tribes resolve disputes through traditional peacemaking, in which "
                     "respected members help the parties reach agreement rather than a judge "
                     "deciding."),
                    ("Courts of Indian Offenses",
                     "Where a tribe keeps jurisdiction but has no court of its own, the Bureau "
                     "of Indian Affairs runs a Court of Indian Offenses, often called a CFR "
                     "court (25 C.F.R. Part 11). Its magistrates are appointed by the Assistant "
                     "Secretary for Indian Affairs, subject to confirmation by the tribe's "
                     "governing body, for four-year terms."),
                ]),
                ("p", "The Indian Civil Rights Act of 1968 applies most of the Bill of Rights' "
                      "protections to tribal governments and limits the sentences tribal courts "
                      "can impose, to one year for an offense. The Tribal Law and Order Act of "
                      "2010 raised the limit to three years for one offense and nine years in "
                      "all, for a tribe that provides added protections, among them a licensed "
                      "defense lawyer and a law-trained judge."),
            ],
            "sources": ["usc-25-3601", "usc-25-1911", "cfr-25-11", "usc-25-1302"],
        },
        {
            "id": "jurisdiction",
            "heading": "Who has jurisdiction in Indian country",
            "blocks": [
                ("p", "Which government can prosecute a crime in Indian country depends on where "
                      "it happened, who committed it and who the victim was."),
                ("ul", [
                    "Federal: the Major Crimes Act (18 U.S.C. 1153) gives federal courts "
                    "jurisdiction over a list of serious crimes, among them murder, kidnapping, "
                    "felony assault and sexual abuse, committed by an Indian in Indian country. "
                    "It generally does not apply in the six Public Law 280 states below. Tribes "
                    "can also prosecute Indian defendants, within the sentencing limits above.",
                    "Tribal: in Oliphant v. Suquamish Indian Tribe (1978), the Supreme Court held "
                    "that tribes cannot prosecute non-Indians unless Congress authorizes it. "
                    "Congress did so in the Violence Against Women Act of 2013 for domestic and "
                    "dating violence and violations of protection orders, and in 2022 widened "
                    "the list to include sexual violence, stalking, sex trafficking, child "
                    "violence, obstruction of justice and assaults on tribal justice personnel. "
                    "A tribe must choose to exercise this jurisdiction and give defendants the "
                    "protections the law requires, among them a licensed defense lawyer and a "
                    "jury that does not systematically exclude non-Indians.",
                    "State: Public Law 280 (1953) gave six states criminal jurisdiction over most "
                    "of the Indian country within them, in place of the federal government: "
                    "Alaska (where the Metlakatla Indian Community also keeps criminal "
                    "jurisdiction), California, Minnesota "
                    "(except the Red Lake reservation), Nebraska, Oregon (except the Warm Springs "
                    "reservation) and Wisconsin. It also opened their courts to private civil "
                    "suits arising there, but did not let states regulate or tax tribes (Bryan "
                    "v. Itasca County, 1976). Ten more states later took on some jurisdiction by "
                    "choice: Arizona, Florida, Idaho, Iowa, Montana, Nevada, North Dakota, South "
                    "Dakota, Utah and Washington. Some jurisdiction has since been returned to "
                    "the federal government and the tribes.",
                ]),
            ],
            "sources": ["usc-18-1153", "oliphant", "usc-25-1304", "doj-vawa", "usc-18-1162",
                        "usc-28-1360", "bia-pl280", "bryan"],
        },
    ],
}


PAGES = (INDEX, CONGRESS, EXECUTIVE, COURTS, STATES, LOCAL, TRIBAL)
