"""The site's frame (the 2026-10-17 audit): who runs it and where its data
comes from (about.html), the way to report an error, the page GitHub serves
for a missing address, the tag naming each page's section, and each page's
own sources with the date they were read."""

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, pages, results  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATES = {"openstates": "2026-10-15", "ncsl": "2026-10-16", "census": "2026-10-05",
         "executive": "2026-10-16", "judiciary": "2026-10-16", "vacancies": "2026-10-17"}


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def footer(html):
    return re.sub(r"\s+", " ", html[html.index('<footer class="site-footer">'):])


class TestDatesInWords(unittest.TestCase):
    def test_a_day_reads_as_the_pages_write_it(self):
        self.assertEqual(pages.date_words("2026-10-15T13:14:00+00:00"), "Oct. 15, 2026")
        self.assertEqual(pages.date_words("2027-01-03"), "Jan. 3, 2027")
        self.assertEqual(pages.date_words("2026-09-01"), "Sept. 1, 2026")
        self.assertEqual(pages.date_words("2026-05-08"), "May 8, 2026")

    def test_anything_else_is_no_date_rather_than_a_wrong_one(self):
        for value in (None, "", "nan", "October 06, 2026", "2026-13-01", "2026"):
            self.assertEqual(pages.date_words(value), "", value)
        self.assertEqual(pages.time_html(None), "")

    def test_the_page_script_words_a_date_the_same_way(self):
        # kyc.js dateWords and pages.date_words: one spelling of each month.
        js = read("candidate_profiles_site", "assets", "kyc.js")
        months = re.search(r"var MONTH_WORDS = \[([^\]]+)\]", js).group(1)
        self.assertEqual(re.findall(r'"([^"]+)"', months), list(pages._MONTHS))

    def test_a_span_of_reads_never_claims_the_latest_for_all(self):
        self.assertEqual(pages._read_span(DATES, "openstates", "ncsl"), ("2026-10-15", "2026-10-16"))
        self.assertIn("between", pages.read_words(("2026-10-15", "2026-10-16")))
        self.assertIn("Sources read on", pages.read_words(("2026-10-15", "2026-10-15")))
        self.assertIsNone(pages._read_span({}, "openstates"))


class TestReportAProblem(unittest.TestCase):
    """TRUST-03: every page and dialog reports through one issue form."""

    def test_the_form_is_filled_from_the_ids_the_links_name(self):
        form = read(".github", "ISSUE_TEMPLATE", "correction.yml")
        ids = re.findall(r"^\s+id: (\S+)", form, re.M)
        for param in ("page", "profile"):
            self.assertIn(param, ids)
        url = pages.report_url("https://example.org/states/tx.html", "A000001")
        self.assertTrue(url.startswith(pages.REPO + "/issues/new?template=correction.yml&"))
        self.assertIn("&page=https%3A%2F%2Fexample.org%2Fstates%2Ftx.html", url)
        self.assertIn("&profile=A000001", url)

    def test_the_page_script_names_the_same_repository(self):
        js = read("candidate_profiles_site", "assets", "kyc.js")
        self.assertIn(f'var REPO_URL = "{pages.REPO}";', js)
        self.assertIn('"/issues/new?template=correction.yml"', js)

    def test_the_form_names_no_hostname(self):
        # Rule 21: a new file naming the host must be checked against CNAME.
        host = emit.canonical_host(ROOT)
        if host:
            self.assertNotIn(host, read(".github", "ISSUE_TEMPLATE", "correction.yml"))

    def test_every_generated_footer_links_about_and_the_form(self):
        for html in (pages.render_state("TX", "example.org"),
                     pages.render_legislature_page("NC", "example.org", dates=DATES),
                     pages.render_counties_page("NC", "example.org", "2026-10-06"),
                     pages.render_court_page("ca9", "example.org", dates=DATES),
                     pages.render_about("example.org", DATES),
                     pages.render_404("example.org")):
            text = footer(html)
            self.assertIn("About &amp; sources</a>", text)
            self.assertIn(pages.ISSUE_FORM, text)
            self.assertEqual(text.count("Non-partisan and independent."), 1)


class TestSectionTags(unittest.TestCase):
    """VISUALS-01: "U.S. Congress" was the tag over a county's governments."""

    def tag(self, html):
        return re.search(r'<span class="brand-sub"( data-congress)?>([^<]*)</span>', html).groups()

    def test_each_page_names_its_section(self):
        from kyc import government
        cases = {
            "State legislatures": pages.render_legislature_page("NC", "example.org"),
            "Counties &amp; local governments": pages.render_counties_page("NC", "example.org"),
            "Federal government": pages.render_federal_page("example.org"),
            "Federal courts": pages.render_court_page("ca9", "example.org"),
            "Know Your Government": government.render("congress", "example.org"),
            "About &amp; sources": pages.render_about("example.org", {}),
        }
        for want, html in cases.items():
            self.assertEqual(self.tag(html), (None, want), want)

    def test_the_congress_tag_only_where_profiles_load(self):
        html = pages.render_state("TX", "example.org")
        self.assertIn("data/people/meta.js", html)
        self.assertEqual(self.tag(html)[0], " data-congress")

    def test_the_section_names_are_the_navigations(self):
        labels = {key: label for _h, entries in pages.nav_groups() for key, _p, _i, label in entries}
        for key in ("legislatures", "local", "courts", "guide", "about"):
            self.assertEqual(pages.brand_sub(key), f'<span class="brand-sub">'
                             f'{labels[key].replace("&", "&amp;")}</span>')


class TestOwnSources(unittest.TestCase):
    """TECH-12, FEDERAL-14: each page cites what it shows, dated."""

    def test_a_legislature_page_dates_open_states_and_does_not_call_portraits_public_domain(self):
        text = footer(pages.render_legislature_page("NC", "example.org", dates=DATES))
        self.assertIn('as each legislature publishes them, as read on <time datetime="2026-10-15">'
                      "Oct. 15, 2026</time>", text)
        self.assertNotIn("public domain", text)
        self.assertIn("portraits as each legislature publishes them", text)

    def test_a_county_page_dates_its_listing(self):
        text = footer(pages.render_counties_page("NC", "example.org", "2026-10-06"))
        self.assertIn('Government Units listing, read on <time datetime="2026-10-06">Oct. 6, 2026', text)
        self.assertIn(pages.listing_date("NC", ROOT) or "", read("local_governments", "nc.json"))

    def test_a_court_page_cites_the_judges_sources_not_the_cabinets(self):
        for cid in ("ca9", "gu", "scotus"):
            text = footer(pages.render_court_page(cid, "example.org", dates=DATES))
            self.assertNotIn("Cabinet", text, cid)
            self.assertNotIn("Vice President", text, cid)
            self.assertIn("uscourts.gov, as read on", text, cid)
        self.assertIn("lists Article III judges only",
                      footer(pages.render_court_page("gu", "example.org", dates=DATES)))

    def test_the_federal_hub_dates_each_source(self):
        text = footer(pages.render_federal_page("example.org", dates=DATES))
        self.assertEqual(text.count("as read on"), 3)

    def test_no_page_date_comes_from_the_odds_cache(self):
        # Rule 41: the odds job may change no page.
        self.assertFalse([c for c in pages.DATED_CACHES if "odds" in c[1]])
        self.assertNotIn("odds", pages.data_dates(ROOT))

    def test_a_cache_with_no_date_names_its_source_without_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.DATA_DIR))
            with open(os.path.join(tmp, emit.DATA_DIR, "state_legislators.json"), "w") as handle:
                json.dump({"states": {}}, handle)
            self.assertEqual(pages.data_dates(tmp), {})
        text = footer(pages.render_legislature_page("NC", "example.org", dates={}))
        self.assertNotIn("as read on", text)


class TestTheAboutPage(unittest.TestCase):
    """TRUST-02, -09, -10, -11, -23."""

    @classmethod
    def setUpClass(cls):
        cls.html = pages.render_about("example.org", pages.data_dates(ROOT))

    def test_it_states_independence_and_what_the_site_is_not(self):
        text = re.sub(r"\s+", " ", self.html)
        for words in ("independent, non-partisan project",
                      "not affiliated with any campaign, party, candidate or government office",
                      "takes no money from any of them", "carries no advertising",
                      "not an official election source", "legal advice"):
            self.assertIn(words, text)

    def test_it_links_the_repository_and_both_licences(self):
        self.assertIn(f'href="{pages.REPO}"', self.html)
        self.assertIn(f'href="{pages.REPO}/blob/main/LICENSE"', self.html)
        self.assertIn(f'href="{pages.REPO}/blob/main/LICENSE-DATA.md"', self.html)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "LICENSE")))
        self.assertTrue(os.path.exists(os.path.join(ROOT, "LICENSE-DATA.md")))

    def test_the_privacy_statement_matches_what_the_code_stores(self):
        # Two keys, both named in the statement; no cookie anywhere.
        keys = set()
        for name in os.listdir(os.path.join(ROOT, "candidate_profiles_site", "assets")):
            if name.endswith(".js"):
                js = read("candidate_profiles_site", "assets", name)
                self.assertNotIn("document.cookie", js, name)
                keys |= set(re.findall(r'var (?:THEME|STATE)_KEY = "([^"]+)"', js))
                self.assertNotIn("sessionStorage", js, name)
                self.assertNotIn("indexedDB", js, name)
                # Every use of the store names one of the two keys: a third
                # (localStorage.setItem("kycSort", ...)) would make the
                # About page's "two settings" false and pass the line above.
                for use in re.finditer(r"localStorage\b(.{0,40})", js):
                    self.assertRegex(use.group(1), r"^\.(?:get|set|remove)Item\((?:THEME|STATE)_KEY\b",
                                     f"{name}: localStorage{use.group(1)}")
        self.assertEqual(keys, {"kycTheme", "kycState"})
        self.assertIn("the theme you picked and the last state you looked at", self.html)

    def test_the_schedule_is_the_workflows(self):
        gate = read(".github", "workflows", "refresh.yml")
        windows = []
        for after, until in re.findall(
                r'\[ "\$today" \\> "(\d{4}-\d{2}-\d{2})" \] && \[ (?:! "\$today" \\> |"\$today" \\< )'
                r'"(\d{4}-\d{2}-\d{2})" \]', gate):
            windows.append((after, until))
        self.assertEqual(len(windows), 3, windows)
        import datetime
        day = datetime.timedelta(days=1)
        parsed = []
        for after, until in windows:
            first = datetime.date.fromisoformat(after) + day
            line = next(line for line in gate.splitlines() if f'"{after}"' in line)
            last = datetime.date.fromisoformat(until) - (day if '\\<' in line else datetime.timedelta())
            parsed.append((first.isoformat(), last.isoformat()))
        self.assertEqual(sorted(parsed), sorted(pages.REFRESH_DAILY))
        cron = re.search(r'cron: "(\d+) ([\d,]+) \* \* \*"', read(".github", "workflows", "odds.yml"))
        minute, hours = cron.groups()
        self.assertEqual(pages.ODDS_TIMES, tuple(f"{int(h):02d}:{int(minute):02d}"
                                                 for h in hours.split(",")))

    def test_every_dataset_has_a_schedule_and_a_dated_cache_it_names_exists(self):
        keys = {key for key, _f, _fields in pages.DATED_CACHES}
        for what, _source, _covers, when, key in pages.DATASETS:
            self.assertIn(when, pages._WHEN_READ, what)
            self.assertTrue(key is None or key in keys, what)

    def test_it_names_no_person_or_address(self):
        self.assertNotIn("mailto:", self.html)
        self.assertNotIn("pkherbert", self.html)


class TestNotFoundAndFolders(unittest.TestCase):
    """TECH-06: a mistyped address showed GitHub's page, with no way back."""

    def test_the_404_page_addresses_everything_from_the_root(self):
        html = pages.render_404("example.org", ("TX",))
        local = [u for u in re.findall(r'(?:href|src|action)="([^"]+)"', html)
                 if not re.match(r"(https?:|#)", u)]
        self.assertTrue(local)
        self.assertEqual([u for u in local if not u.startswith("/")], [])
        self.assertIn('data-root="/"', html)
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertNotIn("404.html", pages.sitemap("example.org", ["TX"]))

    def test_its_assets_are_stamped_like_any_page(self):
        from kyc import assets
        stamped = assets.stamp(pages.render_404("example.org"), ROOT)
        self.assertRegex(stamped, r'src="/assets/kyc\.js\?v=[0-9a-f]{10}"')
        self.assertRegex(stamped, r'href="/assets/kyc\.css\?v=[0-9a-f]{10}"')

    def test_the_folders_answer_and_are_in_the_sitemap(self):
        from kyc import federal_courts
        districts = pages.render_districts_index("example.org")
        self.assertIn('href="ca.html"', districts)
        courts = pages.render_courts_index("example.org")
        for cid in federal_courts.COURTS:
            self.assertIn(f'href="{cid}.html"', courts)
        xml = pages.sitemap("example.org", ["TX"], district_maps=("TX",), courts=("ca9",))
        for path in ("about.html", "districts/index.html", "courts/index.html"):
            self.assertIn(f"https://example.org/{path}", xml)

    def test_the_manifest_names_no_host_and_its_icons_exist(self):
        manifest = json.loads(pages.webmanifest())
        self.assertNotIn("://", json.dumps(manifest))
        for icon in manifest["icons"]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "candidate_profiles_site",
                                                        *icon["src"].split("/"))), icon["src"])


class TestReviewOfTheFrame(unittest.TestCase):
    """What the two reviews of the frame (PR #95) found."""

    def test_each_kind_of_court_is_headed_in_its_own_plural(self):
        html = pages.render_courts_index("example.org")
        headings = re.findall(r'<h2 class="state-heading">([^<]+)</h2>', html)
        self.assertIn("Courts of appeals", headings)
        self.assertIn("District courts", headings)
        self.assertFalse([h for h in headings if h.endswith("ss")], headings)
        self.assertIn('<h1 class="state-title">Federal courts</h1>', html)
        self.assertIn("<title>Federal courts — Know Your Candidate</title>", html)

    def test_the_navigation_leads_to_the_courts_index(self):
        self.assertIn('href="../courts/index.html" data-nav="courts"', pages.nav_html("../"))

    def test_a_district_directory_row_does_not_repeat_the_states_name(self):
        html = pages.render_districts_index("example.org", {"states": {"TX": {"house": 38}}})
        for name, facts in re.findall(r'>([^<]+)</a><div class="directory-facts">([^<]+)</div>', html):
            self.assertNotIn(name, facts)
        self.assertIn("<h1 class=\"state-title\">District maps</h1>", html)

    def test_a_territorial_courts_footer_dates_the_directory_not_the_absence(self):
        text = footer(pages.render_court_page("vi", "example.org", dates=DATES))
        self.assertIn("Biographical Directory, as read on", text)
        self.assertNotIn("not listed, as read on", text)
        self.assertNotIn("president who appointed", text)
        # Each source carries its date; the last line does not repeat them.
        self.assertEqual(text.count("read on"), 2, text)
        self.assertNotIn("Sources read", text)

    def test_the_about_page_names_the_hand_kept_rosters_and_overclaims_nothing(self):
        text = re.sub(r"\s+", " ", pages.render_about("example.org", DATES))
        self.assertNotIn("Every fact is read from a source by a script", text)
        self.assertIn("Most facts are read from a named source by a script", text)
        self.assertIn("kept by hand", text)
        self.assertIn("needs a free GitHub account", text)
        self.assertNotIn("eve of the election", text)
        self.assertNotIn("list beside or below", text)
        self.assertIn("Each profile gives the date its figures run through", text)

    def test_an_inline_script_is_structured_data_or_nothing(self):
        self.assertEqual(emit.inline_script_problems(pages.jsonld({"a": 1})), [])
        self.assertTrue(emit.inline_script_problems("<script>alert(1)</script>"))
        self.assertTrue(emit.inline_script_problems('<script type="module">x()</script>'))
        self.assertTrue(emit.inline_script_problems('<script type="application/ld+json">{x</script>'))
        self.assertEqual(emit.inline_script_problems('<script src="a.js"></script>'), [])


class TestStructuredData(unittest.TestCase):
    """TECH-17: a WebSite with its search, and a breadcrumb trail on each
    generated page, named as the navigation names each section (rule 75)."""

    def blocks(self, html):
        return [json.loads(b) for b in
                re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]

    def test_a_court_page_sits_under_federal_courts(self):
        (crumbs,) = self.blocks(pages.render_court_page("ca9", "example.org"))
        names = [i["name"] for i in crumbs["itemListElement"]]
        self.assertEqual(names, ["Know Your Candidate", "Federal courts",
                                 "U.S. Court of Appeals for the Ninth Circuit"])
        self.assertEqual(crumbs["itemListElement"][-1]["item"], "https://example.org/courts/ca9.html")

    def test_a_name_cannot_close_the_block_early(self):
        block = pages.jsonld({"name": "</script><script>alert(1)"})
        self.assertEqual(block.count("</script>"), 1)

    def test_the_home_page_carries_the_sites_block(self):
        host = emit.canonical_host(ROOT)
        if not host:
            self.skipTest("no custom domain")
        self.assertIn(pages.website_jsonld(host).strip(), read("candidate_profiles_site", "index.html"))

    def test_a_template_without_the_frame_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = os.path.join(tmp, emit.SITE_DIR)
            os.makedirs(site)
            for page in ("index.html", "map.html"):
                with open(os.path.join(site, page), "w", encoding="utf-8") as handle:
                    handle.write(pages.nav_html("", emit.NAV_PAGES[page]))
            bad = [p for p, ok, _note in emit.check_nav(tmp) if not ok]
            self.assertIn("index.html (footer)", bad)
            self.assertIn("map.html (sidebar's freshness line)", bad)


class TestResultsSource(unittest.TestCase):
    """TRUST-06: a race links the page its statuses were read from."""

    def test_a_wikipedia_title_becomes_its_address(self):
        race = {"page": "2026 United States House of Representatives election in Alaska",
                "status": {}}
        self.assertEqual(results.results_source_url(race),
                         "https://en.wikipedia.org/wiki/2026_United_States_House_of_"
                         "Representatives_election_in_Alaska")
        summary = results.race_summary({"races": {"H-AK-00-2026": race}}, "H-AK-00-2026")
        self.assertEqual(summary["sourceUrl"], results.results_source_url(race))

    def test_a_qualified_list_credits_the_secretary_of_state(self):
        from kyc import qualified
        self.assertEqual(results.results_source_url({"source": "qualified", "page": "X"}),
                         qualified.PORTAL)

    def test_no_page_no_link(self):
        self.assertIsNone(results.results_source_url({"status": {}}))


if __name__ == "__main__":
    unittest.main()
