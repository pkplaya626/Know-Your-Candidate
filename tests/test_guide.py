"""Tests for the guide to how government works (kyc/government.py).

The guide is static text about institutions, generated into pages like the
state pages. What can go wrong with it is what goes wrong with any page here:
a link that leads nowhere, a page that loads its module before its data, a
claim with no source behind it. Each is checked the way the build checks the
rest of the site.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, government, pages  # noqa: E402
from kyc.government_text import PAGES, SOURCES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = os.path.join(ROOT, emit.SITE_DIR)


class TestGuideText(unittest.TestCase):

    def test_the_guide_is_sound(self):
        # Every link resolves, every section cites a listed source, and every
        # listed source is cited somewhere.
        self.assertEqual(government.check(), [])

    def test_every_section_cites_a_source(self):
        for page in PAGES:
            for section in page["sections"]:
                self.assertTrue(section.get("sources"), f"{page['slug']}#{section['id']}")

    def test_sources_are_primary_or_named(self):
        # Wikipedia may point to a source; it is never itself the source here.
        for key, (title, url) in SOURCES.items():
            self.assertTrue(url.startswith("https://"), key)
            self.assertNotIn("wikipedia.org", url, key)
            self.assertTrue(title.strip(), key)

    def test_the_index_comes_first_and_every_page_is_reachable(self):
        self.assertEqual(government.slugs()[0], "index")
        index = government.render("index", "example.org")
        for slug in government.slugs()[1:]:
            self.assertIn(f'href="{slug}.html"', index)

    def test_no_people_are_typed_into_the_guide(self):
        # Who holds an office comes from the data (kyc-guide.js), never the
        # text: rule 17, and "headline figures come from kycBuildMeta".
        text = " ".join(
            str(block) for page in PAGES for section in page["sections"]
            for block in section["blocks"])
        # Full names: the text rightly cites Johnson v. M'Intosh.
        for name in ("Mike Johnson", "John Thune", "Chuck Schumer", "Hakeem Jeffries",
                     "Steve Scalise", "Chuck Grassley", "John Roberts", "Donald Trump",
                     "Vance"):
            self.assertNotIn(name, text)


class TestGuideLinks(unittest.TestCase):

    def test_links_resolve_or_are_refused(self):
        self.assertEqual(government.href("guide:congress#senate", "index"),
                         ("congress.html#senate", False))
        self.assertEqual(government.href("site:map.html", "index"), ("../map.html", False))
        self.assertEqual(government.href("state:TX", "index"), ("../states/tx.html", False))
        self.assertEqual(government.href("https://example.org/a", "index"),
                         ("https://example.org/a", True))
        for bad in ("guide:nowhere", "guide:congress#nowhere", "#nowhere", "state:XX",
                    "site:/map.html", "site:../map.html", "site:mpa.html",
                    "http://example.org", "ftp:x"):
            with self.assertRaises(ValueError, msg=bad):
                government.href(bad, "index")

    def test_text_and_labels_are_escaped(self):
        html = government.inline("a <b> & [x <y>](https://e.org/?a=1&b=2) z", "index")
        self.assertEqual(
            html,
            'a &lt;b&gt; &amp; <a href="https://e.org/?a=1&amp;b=2" target="_blank" '
            'rel="noopener noreferrer">x &lt;y&gt;</a> z')

    def test_a_link_the_build_cannot_read_is_refused(self):
        # A parenthesis in the target defeats the pattern; the text must not
        # reach the page as raw "[label](url)".
        with self.assertRaises(ValueError):
            government.inline("See [the Lumbee](https://e.org/wiki/Lumbee_(tribe)).", "index")
        with self.assertRaises(ValueError):
            government.inline("A [broken] (guide:congress) link", "index")
        self.assertEqual(government.inline("Brackets [like these] are text.", "index"),
                         "Brackets [like these] are text.")

    def test_an_unknown_source_or_block_is_refused(self):
        with self.assertRaises(ValueError):
            government._sources(["no-such-source"], "index")
        with self.assertRaises(ValueError):
            government._block(("marquee", "x"), "index", "")

    def test_a_table_row_must_fill_its_columns(self):
        with self.assertRaises(ValueError):
            government._table({"head": ["A", "B"], "rows": [["only one"]]}, "index", "")


class TestGuidePages(unittest.TestCase):

    def test_every_page_renders_with_its_scripts_in_order(self):
        for slug in government.slugs():
            html = government.render(slug, "example.org", ["TX", "AK"])
            self.assertIn(f'rel="canonical" href="https://example.org/government/{slug}.html"',
                          html)
            # A map page also says which guide page it is (kyc-guide.js reads it).
            self.assertRegex(html, r'data-page="guide(-[a-z]+)?"')
            self.assertIn('data-root="../"', html)
            self.assertIsNone(re.search(r"\$[a-z_]+", html.replace("$5,000", "")), slug)
            self.assertEqual(emit.script_sources(html),
                             ["../assets/kyc.js"] + list(government.scripts(slug)))

    def test_only_a_page_with_people_loads_the_profiles(self):
        for page in PAGES:
            html = government.render(page["slug"], "example.org", ["TX"])
            loads = "../data/profiles.js" in emit.script_sources(html)
            self.assertEqual(loads, bool(page.get("people")), page["slug"])
            # Such a page shows the chambers' balance, as a state page does;
            # the others have no build metadata to fill it from.
            self.assertEqual('id="senateBalance"' in html, loads, page["slug"])

    def test_a_page_without_people_carries_its_own_jump_list(self):
        html = government.render("index", "example.org", ["TX", "AK", "DC"])
        options = re.findall(r'<option value="([A-Z]{2})">([^<]+)</option>', html)
        self.assertEqual(options, [("AK", "Alaska (AK)"), ("DC", "District of Columbia (DC)"),
                                   ("TX", "Texas (TX)")])

    def test_the_guide_marks_where_the_reader_is(self):
        html = government.render("congress", "example.org")
        self.assertIn('class="nav-link nav-sub" href="congress.html" aria-current="page"', html)
        self.assertIn('href="../government/index.html"', html)
        self.assertIn('rel="prev" href="index.html"', html)

    def test_the_sitemap_lists_the_guide_in_reading_order_last(self):
        xml = pages.sitemap("example.org", ["TX"], district_maps=["TX"],
                            guide=government.slugs())
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        self.assertEqual(locs[-len(government.slugs()):],
                         [f"https://example.org/government/{s}.html" for s in government.slugs()])

    def test_pages_are_written_and_checked_with_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.SITE_DIR))
            with open(os.path.join(tmp, emit.CNAME_FILE), "w", encoding="utf-8") as f:
                f.write("example.org\n")
            people = [{"id": "X1", "state": "TX", "isCandidate": False}]
            written = emit.write_state_pages(people, tmp, summary={"states": {}})
            guide = sorted(os.path.basename(w) for w in written
                           if os.path.normpath(emit.GOVERNMENT_DIR) in os.path.normpath(w))
            self.assertEqual(guide, sorted(f"{s}.html" for s in government.slugs()))
            self.assertEqual(emit.check_state_pages(people, tmp, summary={"states": {}}), [])
            with open(os.path.join(tmp, emit.GOVERNMENT_DIR, "index.html"), "a",
                      encoding="utf-8") as f:
                f.write("<!-- edited by hand -->")
            stale = emit.check_state_pages(people, tmp, summary={"states": {}})
            self.assertEqual([os.path.basename(rel) for rel, _ in stale], ["index.html"])

    def test_the_committed_guide_pages_are_wired(self):
        results = {p: (ok, note) for p, ok, note in emit.check_pages(ROOT)}
        guide = [p for p in results if p.startswith("government/")]
        self.assertEqual(len(guide), len(government.slugs()))
        for page in guide:
            self.assertEqual(results[page], (True, "ok"), page)


class TestEveryLocalLinkResolves(unittest.TestCase):
    """CI checked only the pages at the site's root, so every district page's
    "States & territories" link pointed at districts/index.html - a page that
    has never existed - and nothing failed. Every page, every folder."""

    def test_every_href_and_src_on_every_page_exists(self):
        missing = []
        for folder, _, files in os.walk(SITE):
            for name in files:
                if not name.endswith(".html"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                for ref in re.findall(r'(?:src|href)="([^"#?][^"]*)"', text):
                    if ref.startswith(("http:", "https:", "data:", "mailto:")):
                        continue
                    target = ref.split("#")[0].split("?")[0]
                    if target and not os.path.exists(os.path.join(folder, *target.split("/"))):
                        missing.append(f"{os.path.relpath(path, SITE)} -> {ref}")
        self.assertEqual(missing, [])

    def test_a_district_page_reaches_the_states_index(self):
        html = pages.render_district_page("CA", "example.org")
        self.assertIn('href="../states/index.html"', html)
        self.assertNotIn('href="index.html"', html)


if __name__ == "__main__":
    unittest.main()
