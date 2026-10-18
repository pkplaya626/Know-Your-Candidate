"""Tests for Know Your Government, the guide (kyc/government.py), and the
site's navigation around it (kyc/pages.py).

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


class TestNavigation(unittest.TestCase):
    """The sidebar, by level of government: one table (pages.nav_groups)."""

    def test_every_entry_leads_to_a_page(self):
        generated = {"legislature/index.html", "counties/index.html"}
        for _heading, entries in pages.nav_groups():
            for key, path, _icon, _label in entries:
                page = path.split("#")[0]
                self.assertTrue(os.path.isfile(os.path.join(SITE, *page.split("/"))) or page in generated,
                                (key, path))

    def test_the_hand_maintained_pages_carry_it(self):
        for page, ok, note in emit.check_nav(ROOT):
            self.assertTrue(ok, (page, note))

    def test_the_hubs_sections_are_the_guides_to_name(self):
        # The guide may link a section the hub's script draws; the two lists
        # are one (kyc/government.py SITE_ANCHORS, assets/kyc-federal.js).
        with open(os.path.join(SITE, "assets", "kyc-federal.js"), encoding="utf-8") as handle:
            script = handle.read()
        # The hub's sections and the changes section it always draws, read
        # from the script, never added by hand.
        hub = script[script.index("function renderHub"):script.index("el(\"federalBody\").innerHTML = html")]
        changes = script[script.index("function changesSection"):script.index("function renderHub")]
        drawn = set(re.findall(r'section\("([a-z-]+)"', hub + changes))
        self.assertEqual(set(government.SITE_ANCHORS["federal/index.html"]), drawn)
        for target, _words in re.findall(r'\["([a-z]+\.html#[a-z-]+)", "([^"]+)"\]', script):
            slug, anchor = target[:-len(".html") - len(target.split("#")[1]) - 1], target.split("#")[1]
            self.assertIn(anchor, government._section_ids(slug), target)

    def test_a_section_the_hub_does_not_draw_is_refused(self):
        with self.assertRaises(ValueError):
            government.href("site:federal/index.html#nowhere", "executive")
        # A route the page's script reads is not a section.
        self.assertEqual(government.href("site:index.html#/?role=member", "congress")[0],
                         "../index.html#/?role=member")

    def test_none_is_not_zero(self):
        html = pages.render_counties_index("", {"year": "2022", "states": {
            "CT": {"county": None, "municipal": 30, "township": 149, "school": 17,
                   "special": 336, "total": 532}}})
        row = re.search(r"Connecticut</a></th>(.*?)</tr>", html).group(1)
        self.assertIn('<td class="faint" title="No county governments.">none<sup>', row)
        self.assertNotIn("<td>0</td>", row)
        # And says why, in a note under the table the cell links to.
        self.assertIn('href="#county-note-ct"', row)
        self.assertIn('id="county-note-ct"', html)
        self.assertIn("abolished them in 1960", html)
        # A count of school districts is of independent ones (the guide's words).
        self.assertIn("<th scope=\"col\">Independent school districts</th>", html)
        self.assertNotIn(">School districts<", html)


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
            written = emit.write_state_pages(people, tmp, summary={"states": {}}, stamp_from=ROOT)
            guide = sorted(os.path.basename(w) for w in written
                           if os.path.normpath(emit.GOVERNMENT_DIR) in os.path.normpath(w))
            self.assertEqual(guide, sorted(f"{s}.html" for s in government.slugs()))
            self.assertEqual(emit.check_state_pages(people, tmp, summary={"states": {}}, stamp_from=ROOT), [])
            with open(os.path.join(tmp, emit.GOVERNMENT_DIR, "index.html"), "a",
                      encoding="utf-8") as f:
                f.write("<!-- edited by hand -->")
            stale = emit.check_state_pages(people, tmp, summary={"states": {}}, stamp_from=ROOT)
            self.assertEqual([os.path.basename(rel) for rel, _ in stale], ["index.html"])

    def test_the_committed_guide_pages_are_wired(self):
        results = {p: (ok, note) for p, ok, note in emit.check_pages(ROOT)}
        guide = [p for p in results if p.startswith("government/")]
        self.assertEqual(len(guide), len(government.slugs()))
        for page in guide:
            self.assertEqual(results[page], (True, "ok"), page)


class TestDatedText(unittest.TestCase):
    """Static prose about a dated event reads as still to come long after it
    (rule 48). From each revisit date a page lists, validate warns until the
    page is checked again and its "reviewed" moved past the date."""

    def test_nothing_is_due_while_the_dates_are_ahead(self):
        self.assertEqual(government.revisits("2026-10-16"), [])

    def test_a_passed_date_is_due_until_the_page_is_checked_again(self):
        from kyc import validate

        due = government.revisits("2026-11-04")
        self.assertEqual([(slug, day) for slug, day, _what in due],
                         [("states", "2026-11-04"), ("elections", "2026-11-04")])
        self.assertEqual([i.code for i in validate.check_guide("2027-02-01")], ["guide-revisit"])
        # Three on the elections page, two on the states page (its 2026
        # ballot map, and Arizona's first lieutenant governor).
        self.assertEqual(len(validate.check_guide("2027-02-01")[0].detail), 5)
        self.assertEqual(validate.check_guide("2026-10-16"), [])


class TestNoCongressIsTyped(unittest.TestCase):
    """Which Congress sits is the data's word (rule 68): the guide's
    "the members of the 119th Congress" would have gone on saying so after
    January 3. A citation of a dated source (the Census's 119th Congress
    boundary files) is the one place a number belongs."""

    PATTERN = re.compile(r"[^.<>]*\b\d+(?:st|nd|rd|th) Congress[^.<>]*")

    def found(self, text):
        return [m.group(0).strip() for m in self.PATTERN.finditer(text)
                if "artographic" not in m.group(0)]

    def test_no_page_names_the_sitting_congress_by_number(self):
        typed = []
        for folder, _, files in os.walk(SITE):
            for name in files:
                if name.endswith(".html"):
                    with open(os.path.join(folder, name), encoding="utf-8") as handle:
                        typed += [f"{name}: {t}" for t in self.found(handle.read())]
        for module in ("government_text.py", "pages.py"):
            with open(os.path.join(ROOT, "kyc", module), encoding="utf-8") as handle:
                typed += [f"{module}: {t}" for t in self.found(handle.read())]
        self.assertEqual(typed, [])


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
                    # A URL from the root (the 404 page's) is the site's.
                    base = SITE if target.startswith("/") else folder
                    if target and not os.path.exists(
                            os.path.join(base, *target.lstrip("/").split("/"))):
                        missing.append(f"{os.path.relpath(path, SITE)} -> {ref}")
        self.assertEqual(missing, [])

    def test_a_district_page_reaches_the_states_index(self):
        html = pages.render_district_page("CA", "example.org")
        self.assertIn('href="../states/index.html"', html)
        # "index.html" from a district page is the district maps' own
        # directory now, which exists and is linked under its name; it once
        # pointed at a page that did not.
        self.assertIn(f'href="index.html"><svg class="icon" aria-hidden="true"><use href="#i-map"/></svg> '
                      f'{pages.DISTRICTS_INDEX_NAME}</a>', html)
        self.assertTrue(os.path.exists(os.path.join(SITE, "districts", "index.html")))


def _text_of(slug):
    """A guide page's words, as a reader sees them: the tags stripped."""
    html = government.render(slug, "example.org")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


class TestOneNamePerPage(unittest.TestCase):
    """The navigation said "How the federal courts work" over a page titled
    "The federal courts", "Elections" over "How elections work", and
    "Overview" over "How American government is organized" (rule 75)."""

    LINK = re.compile(r'<a\b[^>]*href="(?:\.\./)*government/([a-z]+)\.html"[^>]*>(.*?)</a>', re.S)

    def test_title_heading_navigation_and_pager_use_the_one_name(self):
        for slug in government.slugs():
            html = government.render(slug, "example.org")
            name = government.name(slug)
            self.assertIn(f"<title>{name} — Know Your Candidate</title>", html.replace("&#x27;", "'"))
            self.assertRegex(html, r"<h1[^>]*>" + re.escape(name) + "</h1>")
            for other in government.slugs():
                entry = re.search(r'<a class="nav-link nav-sub" href="' + other +
                                  r'\.html"[^>]*>([^<]*)</a>', html)
                self.assertEqual(entry.group(1), government.name(other), (slug, other))
            for link in re.findall(r'class="guide-pager-link[^"]*"[^>]*href="([a-z]+)\.html">'
                                   r"<span>[A-Za-z]+</span> ([^<]*)</a>", html):
                self.assertEqual(link[1], government.name(link[0]), slug)

    def test_every_link_to_a_whole_guide_page_says_its_name(self):
        # Every generated page and every module that writes a link to one.
        wrong = []
        texts = []
        for folder, _, files in os.walk(SITE):
            for name in files:
                if name.endswith((".html", ".js")) and "data" not in folder:
                    with open(os.path.join(folder, name), encoding="utf-8") as handle:
                        texts.append((name, handle.read()))
        for name, text in texts:
            for slug, inner in self.LINK.findall(text):
                words = re.sub(r"<[^>]+>", "", inner).strip()
                if words in ("Know Your Government",) and slug == "index":
                    continue
                if words != government.name(slug):
                    wrong.append(f"{name}: {slug} '{words}'")
        # The state page's link is drawn by its script from the name the
        # generated page carries (pages._state_main), never a typed one.
        with open(os.path.join(SITE, "assets", "kyc-state.js"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertNotIn(government.name("states"), script)
        page = pages.render_state("TX", "example.org")
        self.assertIn(f'data-guide-name="{government.name("states")}"', page)
        self.assertEqual(sorted(set(wrong)), [])

    def test_the_index_is_named_as_the_sites_navigation_names_it(self):
        self.assertEqual(government.name("index"), "Know Your Government")
        self.assertIn(("guide", "government/index.html", "scroll", "Know Your Government"),
                      [entry for _h, entries in pages.nav_groups() for entry in entries])


class TestMapPagesText(unittest.TestCase):
    """On the courts, states, local and tribal pages every section was a
    closed <details> whose title was bare <summary> text: no heading for a
    screen reader to list, and a map with five closed rows to land on."""

    def test_each_section_title_is_a_heading_and_the_first_is_open(self):
        for slug in ("courts", "states", "local", "tribal"):
            html = government.render(slug, "example.org")
            sections = re.findall(r'<details class="guide-more-section" id="[^"]+"( open)?>\s*'
                                  r"<summary>(.*?)</summary>", html, re.S)
            self.assertTrue(sections, slug)
            self.assertEqual(sections[0][0], " open", slug)
            self.assertTrue(all(not s[0] for s in sections[1:]), slug)
            self.assertTrue(all(re.fullmatch(r'<h3 class="guide-more-heading">[^<]+</h3>', s[1])
                                for s in sections), slug)
            # A subheading inside a section ranks below the section's title.
            folded = html[html.index('class="guide-more"'):]
            self.assertNotIn('<h3 class="guide-subheading"', folded, slug)


class TestCorrections(unittest.TestCase):
    """The audit of 2026-10-17's corrections to the guide's text."""

    def test_the_lieutenant_governor_count_is_the_maps(self):
        from kyc import government_maps

        text = _text_of("states")
        count = len(government_maps.SENATE_PRESIDES["ltgov"])
        self.assertIn(f"In {count} states the lieutenant governor is the president of the senate",
                      text)
        self.assertNotIn("about 26", text)
        self.assertNotIn("{{", text)
        presides = next(m for m in government_maps.modes()["states"] if m["id"] == "presides")
        self.assertIn(f"In {count} states", presides["about"])

    def test_an_unknown_figure_is_refused(self):
        with self.assertRaises(ValueError):
            government.inline("In {{no-such-count}} states", "states")

    def test_the_overview_lists_every_part_of_the_site(self):
        html = government.render("index", "example.org")
        for page in ("index.html", "map.html", "federal/index.html", "states/index.html",
                     "legislature/index.html", "counties/index.html"):
            self.assertIn(f'href="../{page}"', html, page)
        self.assertNotIn("follows one part of all this", html)

    def test_tribal_jurisdiction_names_mcgirt_and_castro_huerta(self):
        text = _text_of("tribal")
        for words in ("Oklahoma v. Castro-Huerta", "McGirt v. Oklahoma", "18 U.S.C. 1151",
                      "18 U.S.C. 1152", "Indian country is a term federal law defines"):
            self.assertIn(words, text)
        # The one-year limit is the 1986 amendment's, not the 1968 Act's.
        self.assertIn("six months and a $500 fine", text)
        self.assertIn("since a 1986 amendment one year and a $5,000 fine", text)

    def test_maine_ranks_its_congressional_primaries(self):
        text = _text_of("elections")
        self.assertNotIn("state-level primaries", text)
        self.assertIn("its primaries for Congress, governor and the legislature", text)
        # Not "all its primaries": county offices' primaries are not ranked
        # (21-A M.R.S. 723-A names the offices).
        self.assertNotIn("all its primaries", text)

    def test_portland_is_said_once(self):
        text = _text_of("local")
        self.assertNotIn("still using it", text)
        self.assertIn("the largest city to keep it", text)

    def test_legal_terms_are_defined_where_first_used(self):
        self.assertIn("petty offenses (the least serious federal crimes", _text_of("courts"))
        self.assertIn("tax deficiency, more tax than", _text_of("courts"))
        congress = _text_of("congress")
        self.assertIn("germane: on the subject of the bill", congress)
        self.assertIn("any one senator can block by objecting", congress)
        self.assertIn("one that would stand on state law alone", _text_of("index"))


class TestNewSections(unittest.TestCase):
    """What the audit found the guide never explained."""

    def test_the_sections_exist_and_cite_sources(self):
        wanted = {"congress": ("lawmaking", "districts", "reaching"),
                  "executive": ("taking-part",), "states": ("taking-part",),
                  "local": ("taking-part",),
                  "elections": ("before", "funding", "running", "after")}
        for slug, ids in wanted.items():
            page = next(p for p in PAGES if p["slug"] == slug)
            have = {s["id"]: s for s in page["sections"]}
            for sid in ids:
                self.assertIn(sid, have, f"{slug}#{sid}")
                self.assertTrue(have[sid]["sources"], f"{slug}#{sid}")

    def test_the_bill_flow_is_page_text(self):
        html = government.render("congress", "example.org")
        flow = html[html.index('<figure class="guide-flow">'):]
        flow = flow[:flow.index("</figure>")]
        self.assertNotIn("<svg", flow)
        for step in ("Committee", "On the Senate floor", "three-fifths", "pocket", "Override"):
            self.assertIn(step, flow)
        # One chamber's floor, then the other chamber: never the House floor
        # and the Senate floor as two steps followed by "the other chamber",
        # which reads as a third passage.
        titles = re.findall(r'<li class="guide-flow-step"><strong>(.*?)</strong>', flow)
        self.assertNotIn("On the House floor", titles)
        self.assertEqual(titles.index("The other chamber"),
                         titles.index("On the floor of its chamber") + 1)

    def test_every_redrawn_state_is_listed_from_the_table(self):
        from kyc import districts

        html = government.render("congress", "example.org")
        listed = re.findall(r'<ul class="guide-list guide-redrawn">(.*?)</ul>', html, re.S)[0]
        self.assertEqual(sorted(re.findall(r'href="\.\./districts/([a-z]{2})\.html"', listed)),
                         sorted(c.lower() for c in districts.REDRAWN))

    def test_the_timeline_keys_its_steps_to_the_sites_statuses(self):
        html = government.render("elections", "example.org")
        statuses = set(re.findall(r'class="badge guide-status" data-status="([a-z]+)"', html))
        self.assertEqual(statuses, {"nominee", "awaiting", "elected", "defeated", "runoff"})
        days = re.findall(r'<li data-date="(\d{4}-\d{2}-\d{2})">', html)
        self.assertEqual(days, sorted(days))
        self.assertEqual(days[-1], "2027-01-03")

    def test_a_timeline_out_of_order_is_refused(self):
        spec = {"items": [("2026-12-01", "Dec 1", "b", "b", []),
                          ("2026-11-03", "Nov 3", "a", "a", [])]}
        with self.assertRaises(ValueError):
            government._timeline(spec, "elections", "")

    def test_the_voting_link_and_jump_list_open_a_states_voting_section(self):
        html = government.render("elections", "example.org")
        self.assertIn('href="../states/index.html" data-voting-link>', html)
        self.assertIn('data-jump-to="states/{code}.html#voting"', html)
        self.assertIn("data-voting-picker", html)

    def test_the_contribution_limit_and_threshold_are_the_statutes(self):
        text = _text_of("elections")
        self.assertIn("more than $5,000 (52 U.S.C. 30101(2))", text)
        self.assertIn("up to $3,500 per election", text)


if __name__ == "__main__":
    unittest.main()
