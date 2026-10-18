"""Tests for each state's highest court (kyc/courts.py): the roster read from
the court's own page by its recipe, the names as a reader should see them,
and the court as the page shows it.

A court's members come only from the court. A page that draws itself with
JavaScript, or answers a browser and not a plain request, is read in a
headless Chrome; a roster published as a PDF is read from the file's text;
a site that refuses every automated reader is read by hand and says so; and
a page nobody can read lists the court without members, and says why.
"""

import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import courts, stategov  # noqa: E402
from kyc.government_maps import HIGH_COURTS, STATES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestNames(unittest.TestCase):

    def test_titles_seats_and_honorifics_are_not_names(self):
        cases = {
            "Chief Justice Karen R. Baker, Position 1": "Karen R. Baker",
            "Associate Justice Cody Hiland, Position 3": "Cody Hiland",
            "Justice Mark S. Massa (107)": "Mark S. Massa",
            "Hon. Andrew M. Mead ": "Andrew M. Mead",
            "The Honorable Wesley G. Russell Jr.": "Wesley G. Russell Jr.",
            "Gary L. Lumpkin – Presiding Judge": "Gary L. Lumpkin",
            "P. Scott Neville, Jr., Chief Justice": "P. Scott Neville, Jr.",
            "Vice Chief Justice John R. Lopez IV": "John R. Lopez IV",
            "Honorable Matthew Fader, Chief Justice": "Matthew Fader",
            "Debra  Todd": "Debra Todd",
        }
        for raw, shown in cases.items():
            self.assertEqual(courts.clean_name(raw), shown, raw)

    def test_a_name_printed_last_first_is_turned_round(self):
        self.assertEqual(courts.clean_name("Rabner, Stuart"), "Stuart Rabner")
        self.assertEqual(courts.clean_name("William H. Bright, Jr."), "William H. Bright, Jr.")

    def test_capitals_read_as_the_person_writes_them(self):
        self.assertEqual(courts.clean_name("NELS S.D. PETERSON"), "Nels S.D. Peterson")
        self.assertEqual(courts.clean_name("CARLA WONG MCMILLIAN"), "Carla Wong McMillian")
        self.assertEqual(courts.clean_name("SHAWN ELLEN LAGRUA"), "Shawn Ellen LaGrua")
        # Nearly all capitals is capitals: Washington's page writes "McCLOUD".
        self.assertEqual(courts.clean_name("JUSTICE SHERYL GORDON McCLOUD"), "Sheryl Gordon McCloud")


class TestChief(unittest.TestCase):

    def test_only_the_chief_is_chief(self):
        import re
        for title in ("Chief Justice", "Chief Judge", "Presiding Judge", "CHIEF JUSTICE"):
            self.assertTrue(re.search(courts.CHIEF, title, re.I), title)
        # Arizona's Vice Chief Justice, Utah's and Washington's Associate Chief
        # Justice, Kentucky's Deputy Chief Justice, Oklahoma's Vice Presiding
        # Judge, Mississippi's Presiding Justices.
        for title in ("Vice Chief Justice", "Associate Chief Justice", "ASSOCIATE CHIEF JUSTICE",
                      "Deputy Chief Justice", "Vice Presiding Judge", "Presiding Justice"):
            self.assertFalse(re.search(courts.CHIEF, title, re.I), title)

    def test_an_associate_chief_split_across_a_line_is_not_the_chief(self):
        # Utah's page names an Associate Chief Justice and no chief; a line
        # break or a non-breaking space inside the title must not make her one.
        recipe = {"url": "x", "item": r"<h3>(?P<title>[^<]*(?:<br>[^<]*)?)</h3>\s*<p>(?P<name>[^<]+)</p>"}
        for title in ("Associate<br>\n   Chief Justice", "Associate&nbsp;Chief Justice",
                      "Associate\u00a0Chief Justice"):
            page = f"<h3>{title}</h3><p>Jill M. Pohlman</p>"
            self.assertEqual(courts.extract(page, recipe), [("Jill M. Pohlman", False)], title)


class TestRecipes(unittest.TestCase):

    def test_a_recipe_reads_its_slice_and_skips_comments(self):
        page = ("<h2>Alaska Supreme Court Justices</h2><table>"
                "<tr><td class='x'><a href='a.pdf'>Susan M. Carney</a><br>Chief Justice</td></tr>"
                "<tr><td class='x'>Aimee A. Oravec <!-- <a href='b.pdf'>Aimee Oravec</a> --></td></tr>"
                "</table><table><tr><td>Court of Appeals Judge</td></tr></table>")
        got = courts.extract(page, courts.COURTS["AK"])
        self.assertEqual(got, [("Susan M. Carney", True), ("Aimee A. Oravec", False)])

    def test_a_json_recipe(self):
        page = ('{"value": [{"FullName": "<div>Meagan A Flynn</div>", "Job_x0020_Title": '
                '"Supreme Court Chief Justice"}, {"FullName": "<div>Stephen K Bushong</div>", '
                '"Job_x0020_Title": "Supreme Court Justice"}]}')
        got = courts.extract(page, courts.COURTS["OR"])
        self.assertEqual(got, [("Meagan A. Flynn", True), ("Stephen K. Bushong", False)])

    def test_a_vacant_seat_card_is_not_a_person(self):
        page = ('<a href="/about-court/justices-court/chief-justice-patricia-guerrero">Chief Justice '
                'Patricia Guerrero</a><div class="usa-card__brow-color"><div>Kelli M. Evans</div></div>'
                '<div class="usa-card__brow-color"><div>Vacant Seat</div></div>')
        got = courts.extract(page, courts.COURTS["CA"])
        self.assertEqual([n for n, _ in got], ["Patricia Guerrero", "Kelli M. Evans"])

    def test_a_court_that_reads_fewer_members_than_last_time_is_reported(self):
        before = {"OK": {"listed": 9, "members": ["Dustin P. Rowe", "Travis Jett"]},
                  "TX": {"listed": 9, "members": []}}
        after = {"OK": {"listed": 8, "members": ["Dustin P. Rowe"]},
                 "TX": {"listed": 9, "members": []}}
        problems = courts.shrunk(before, after)
        self.assertEqual(len(problems), 1)
        self.assertIn("OK: 8 members read, 9 last time", problems[0])
        self.assertIn("Travis Jett", problems[0])

    def test_a_page_that_does_not_fit_its_court_is_refused(self):
        saved = courts._get_bytes
        try:
            courts._get_bytes = lambda url, headers=None, timeout=60: (
                b"<h2><a>Chief Justice A B</a></h2><h2><a>Chief Justice C D</a></h2>")
            recipe = {"url": "https://example.gov/", "item": r"<h2><a>(?P<name>[^<]+)</a></h2>"}
            with self.assertRaisesRegex(courts.CourtsError, "more than one chief"):
                courts.read_court("XX", recipe, 7)
            with self.assertRaisesRegex(courts.CourtsError, "seats|more"):
                courts.read_court("XX", recipe, 1)          # more names than seats
            courts._get_bytes = lambda url, headers=None, timeout=60: b"<p>nothing</p>"
            with self.assertRaisesRegex(courts.CourtsError, "no members"):
                courts.read_court("XX", recipe, 7)
        finally:
            courts._get_bytes = saved

    def test_every_recipe_names_a_page_and_a_way_to_read_it(self):
        for code, recipe in courts.COURTS.items():
            self.assertTrue(recipe["url"].startswith("https://"), code)
            self.assertTrue(recipe.get("item") or recipe.get("items"), code)
            self.assertNotIn(code, courts.UNREADABLE, code)


def _pdf(*streams):
    """A PDF with these content streams, each Flate-compressed as a word
    processor writes them, and a binary "font" stream that holds "BT"."""
    out = [b"%PDF-1.6\n"]
    font = bytes(range(128, 256)) * 8 + b" BT " + bytes(range(128, 256)) * 8
    for n, body in enumerate(streams + (font,), 1):
        packed = zlib.compress(body)
        out.append(b"%d 0 obj\n<</Length %d/Filter/FlateDecode>>stream\n" % (n, len(packed)) +
                   packed + b"\nendstream\nendobj\n")
    return b"".join(out)


RI_PAGE = (b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (Revised June 5, 2026)Tj ET\n"
           b"BT 72 700 Td [(Supreme Court - 1 Chief Justice, 4 Justices)]TJ\n"
           b"0 -1.1 Td [(Chief Justice P)-55.3 (aul A. Suttell)]TJ\n"
           b"0 -1.1 Td [(Justice Maureen)-55.6 ( Keou)]TJ 13.5 0 Td (gh)Tj\n"
           b"T* [(Justice Sarah)-55.6 ( Taft)]TJ 11.6 0 Td (-)Tj [(Cart)-55.3 (er)]TJ\n"
           b"T* (Justice \\(Vacant\\))Tj\n"
           b"T* (Superior Court - 1 Presiding Justice)Tj\n"
           b"T* (Associate Justice Robert D. Krause)Tj ET\n")


class TestPdf(unittest.TestCase):
    """Rhode Island publishes its roster only as a PDF; its text is read
    from the file with the standard library."""

    def test_lines_are_read_as_drawn(self):
        lines = courts.pdf_lines(_pdf(RI_PAGE))
        self.assertEqual(lines[:2], ["Revised June 5, 2026", "Supreme Court - 1 Chief Justice, 4 Justices"])
        # A kerning gap inside a TJ array is not a space; a run continued
        # along the line is the same word ("Keou" + "gh"), not two.
        self.assertIn("Chief Justice Paul A. Suttell", lines)
        self.assertIn("Justice Maureen Keough", lines)
        self.assertIn("Justice Sarah Taft-Carter", lines)
        self.assertIn("Justice (Vacant)", lines)
        # A binary stream that happens to hold "BT" is not text.
        self.assertTrue(all(ch.isprintable() for line in lines for ch in line), lines)

    def test_a_wide_gap_in_a_tj_array_is_a_space(self):
        lines = courts.pdf_lines(_pdf(b"BT [(Justice)-300 (Erin Lynch Prata)]TJ ET"))
        self.assertEqual(lines, ["Justice Erin Lynch Prata"])

    def _read(self, data):
        saved = courts._get_bytes
        courts._get_bytes = lambda url, headers=None, timeout=60: data
        try:
            return courts.read_court("RI", courts.COURTS["RI"], 5)
        finally:
            courts._get_bytes = saved

    def test_rhode_islands_recipe_reads_its_court_and_the_files_date(self):
        got = self._read(_pdf(RI_PAGE))
        # The Supreme Court's block only (Krause sits on the Superior
        # Court), and "(Vacant)" is the court saying a seat is empty.
        self.assertEqual(got["members"], ["Paul A. Suttell", "Maureen Keough", "Sarah Taft-Carter"])
        self.assertEqual(got["chief"], "Paul A. Suttell")
        self.assertEqual((got["listed"], got["seats"]), (3, 5))
        self.assertEqual(got["revised"], "2026-06-05")

    def test_a_rejection_page_is_not_the_roster(self):
        # Rule 52: a server's "Request Rejected" with status 200 is not a file.
        with self.assertRaisesRegex(courts.CourtsError, "did not answer with a PDF"):
            self._read(b"<html><body>Request Rejected</body></html>")

    def test_a_roster_that_no_longer_says_when_it_was_revised_is_refused(self):
        with self.assertRaisesRegex(courts.CourtsError, "revised"):
            self._read(_pdf(RI_PAGE.replace(b"Revised June 5, 2026", b"Judicial Roster")))


class TestBrowser(unittest.TestCase):
    """The courts whose page a headless Chrome must draw."""

    LA = ('<div><p>Hon. John L. Weimer, Chief Justice</p></div><table><tbody>'
          '<tr><td><p><a href="/Biography?p=John_L._Weimer" title="Justice John L. Weimer"><strong>'
          'John L. Weimer</strong></a></p></td><td><p>Chief Justice</p></td></tr>'
          '<tr><td><p><a style="font-weight: bold;" href="/Biography?p=William_H_Burris">William H. '
          'Burris</a></p></td><td><p>Associate Justice<br></p></td></tr>'
          '<tr><td><p><a href="/Biography?p=Cade_R._Cole"><span style="font-weight: bold;">Cade R. '
          'Cole</span></a></p></td><td><p>Associate Justice&nbsp;</p></td></tr>'
          '<tr><td><p><a href="/Biography?p=Jefferson_Hughes"><strong>Jefferson Hughes</strong></a>'
          '</p></td><td><p style="margin-top: 0px;">Associate Justice</p></td></tr></tbody></table>')

    def test_louisianas_table_reads_every_row_however_it_is_marked_up(self):
        # On 2026-10-18 the first recipe read five of seven: a bold <span>
        # and a styled title cell each lost a justice.
        got = courts.extract(self.LA, courts.COURTS["LA"])
        self.assertEqual(got, [("John L. Weimer", True), ("William H. Burris", False),
                               ("Cade R. Cole", False), ("Jefferson Hughes", False)])

    def test_tennessees_cards_are_read_wherever_they_link_and_nothing_after(self):
        card = ('<div class="card-footer"><a href="{}" class="card-link ">\n'
                '          {}        </a></div>')
        page = ('<img alt="(Left to Right) Justice Tarwater, Justice Kirby, Chief Justice Bivins">'
                '<h2><div class="field">Supreme Court Justices</div></h2>' +
                card.format("/courts/supreme-court/judges/jeff-bivins", "Chief Justice Jeffrey S. Bivins") +
                card.format("https://www.tncourts.gov/courts/court-criminal-appeals/judges/kyle-hixson",
                            "Justice Kyle Hixson") +
                '<h2><div class="field">About</div></h2>' +
                card.format("/courts/court-appeals/judges/x", "Justice Someone Else"))
        got = courts.extract(page, courts.COURTS["TN"])
        self.assertEqual(got, [("Jeffrey S. Bivins", True), ("Kyle Hixson", False)])

    def test_a_browser_court_with_no_drawn_page_is_not_read(self):
        with self.assertRaisesRegex(courts.CourtsError, "browser did not read"):
            courts.read_court("CT", courts.COURTS["CT"], 7, None)

    def test_with_no_reader_nothing_is_read_and_the_run_says_why(self):
        # Rule 8: no Node, no Chrome or a reader that fails reads nothing,
        # and each court keeps its last good read (kyc/cli.py).
        empty = tempfile.mkdtemp()
        try:
            found, problems = courts.read_with_browser({"CT": courts.COURTS["CT"]["url"]}, root=empty,
                                                       out_dir=os.path.join(empty, "out"))
        finally:
            shutil.rmtree(empty, ignore_errors=True)
        self.assertEqual(found, {})
        self.assertEqual(len(problems), 1)
        self.assertIn("keep their last read", problems[0])

    def test_fetch_reports_each_browser_court_it_could_not_read(self):
        saved = courts.read_with_browser
        courts.read_with_browser = lambda pages, root=".", out_dir=None: (
            {}, ["the browser reader did not run (no Chrome); CT keep their last read"])
        try:
            found, problems = courts.fetch(["CT"], pause=0)
        finally:
            courts.read_with_browser = saved
        self.assertEqual(found, {})
        self.assertTrue(any("did not run" in p for p in problems), problems)
        self.assertTrue(any(p.startswith("CT: the browser did not read") for p in problems), problems)

    @unittest.skipUnless(shutil.which("node"), "needs Node")
    def test_a_page_the_browser_was_refused_is_not_read(self):
        # A bot wall's 403 is drawn like any page; the manifest's status
        # keeps it out, so a challenge page is never a roster.
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, "tools"))
            with open(os.path.join(root, courts.BROWSER_TOOL), "w", encoding="utf-8") as handle:
                handle.write(
                    "import fs from 'node:fs';\n"
                    "const dir = process.argv[3];\n"
                    "fs.mkdirSync(dir, { recursive: true });\n"
                    "fs.writeFileSync(dir + '/CT.html', '<li><a href=\"x\">Justice A B</a>');\n"
                    "fs.writeFileSync(dir + '/MA.html', 'Just a moment...');\n"
                    "fs.writeFileSync(dir + '/manifest.json', JSON.stringify({pages: {"
                    "CT: {status: 200}, MA: {status: 403, title: 'Just a moment...'}}}));\n")
            found, problems = courts.read_with_browser(
                {"CT": "https://a.example/", "MA": "https://b.example/"}, root=root,
                out_dir=os.path.join(root, "out"))
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(sorted(found), ["CT"])
        self.assertEqual(len(problems), 1)
        self.assertIn("MA: the browser read 403", problems[0])


class TestCurated(unittest.TestCase):
    """Four courts' sites refuse every automated reader; their rosters were
    read by hand from the court's own page (overrides.COURT_ROSTERS)."""

    def test_the_committed_rosters_fit_their_courts(self):
        for code, roster in courts.curated().items():
            day = datetime.date.fromisoformat(roster["read"])
            self.assertEqual(courts.curated_problems(today=day), [], code)
            # The evidence quotes every name the roster lists.
            for name in roster["members"]:
                self.assertIn(name.split()[-1], roster["evidence"], (code, name))

    def test_a_hand_read_roster_is_checked_like_a_read_one(self):
        from kyc import overrides
        saved = dict(overrides.COURT_ROSTERS)
        try:
            overrides.COURT_ROSTERS.clear()
            overrides.COURT_ROSTERS.update({
                "NH": ("https://www.courts.nh.gov/x", "2026-10-18", tuple("ABCDEF"), "", "quoted"),
                "NV": ("https://nvcourts.gov/x", "2026-10-18", ("A B", "C D"), "E F", "quoted"),
                "MA": ("https://www.mass.gov/x", "2026-10-18", ("A B",), "", "quoted"),
                "NY": ("https://www.nycourts.gov/x", "2026-10-18", ("A B",), "", "")})
            problems = courts.curated_problems(today=datetime.date(2026, 10, 18))
        finally:
            overrides.COURT_ROSTERS.clear()
            overrides.COURT_ROSTERS.update(saved)
        text = "\n".join(problems)
        self.assertIn("NH: the curated roster lists 6 for 5 seats", text)
        self.assertIn("NV: the curated chief E F is not among its members", text)
        self.assertIn("MA: a curated roster for a court the pipeline reads", text)
        self.assertIn("NY: a curated roster needs the court's page and what it says", text)

    def test_a_hand_read_roster_says_when_it_is_old(self):
        roster = courts.curated()["NY"]
        day = datetime.date.fromisoformat(roster["read"])
        late = day + datetime.timedelta(days=courts.STALE_DAYS + 1)
        self.assertEqual(courts.curated_problems(today=day + datetime.timedelta(days=courts.STALE_DAYS)), [])
        self.assertTrue(any(p.startswith("NY: the court's roster was read by hand")
                            for p in courts.curated_problems(today=late)))

    def test_the_page_says_a_roster_was_read_by_hand_and_when(self):
        court = courts.for_state("NY", {"courts": {}})["court"]
        roster = courts.curated()["NY"]
        self.assertEqual(court["members"], list(roster["members"]))
        self.assertEqual(court["chief"], roster["chief"])
        self.assertEqual(court["readOn"], roster["read"])
        self.assertEqual(court["word"], "judges")
        self.assertNotIn("unreadable", court)

    def test_a_court_that_names_no_chief_has_none(self):
        # New Hampshire's page names a Senior Associate Justice, who is not
        # the chief (rule 57).
        court = courts.for_state("NH", {"courts": {}})["court"]
        self.assertEqual(court["chief"], "")
        self.assertLess(len(court["members"]), court["seats"])


class TestStale(unittest.TestCase):

    def test_a_read_kept_too_long_is_reported(self):
        cache = {"fetched": "2026-10-18T00:00:00+00:00", "courts": {
            "CT": {"read": "2026-08-01"}, "MA": {"read": "2026-10-10"}, "TX": {}}}
        problems = courts.stale(cache, today=datetime.date(2026, 10, 18))
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("CT: the court's roster was last read 78 days ago"))
        # A read from before reads carried their day is as old as the cache.
        late = courts.stale(cache, today=datetime.date(2026, 12, 31))
        self.assertTrue(any(p.startswith("TX:") for p in late), late)

    def test_a_read_says_when_it_was_read(self):
        saved = courts._get_bytes
        courts._get_bytes = lambda url, headers=None, timeout=60: b"<h2><a>Chief Justice A B</a></h2>"
        try:
            got = courts.read_court("XX", {"url": "https://example.gov/",
                                           "item": r"<h2><a>(?P<name>[^<]+)</a></h2>"}, 7)
        finally:
            courts._get_bytes = saved
        self.assertEqual(got["read"], datetime.date.today().isoformat())


class TestForState(unittest.TestCase):

    def test_an_unreadable_court_says_why_and_has_no_members(self):
        court = courts.for_state("AL", {"courts": {}})["court"]
        self.assertIn("reset", court["unreadable"])
        self.assertNotIn("members", court)
        self.assertEqual(court["seats"], HIGH_COURTS["AL"][1])

    def test_texas_and_oklahoma_have_two_highest_courts(self):
        cache = {"courts": {
            "TX": {"members": ["A B"], "chief": "A B", "listed": 1, "seats": 9, "url": "u"},
            "TX-CCA": {"members": ["C D"], "chief": "C D", "listed": 1, "seats": 9, "url": "v"}}}
        out = courts.for_state("TX", cache)
        self.assertEqual(out["criminalCourt"]["name"], "Court of Criminal Appeals")
        self.assertEqual(out["criminalCourt"]["word"], "judges")
        self.assertEqual(out["court"]["word"], "justices")


class TestCommitted(unittest.TestCase):

    def test_every_state_has_its_court_read_or_says_why_not(self):
        cache = courts.load_cache(ROOT)
        curated = courts.curated()
        for code in STATES:
            self.assertEqual(sum((code in cache["courts"], code in curated, code in courts.UNREADABLE)), 1,
                             code)
        # STATEGOV-12: ten courts showed no one on 2026-10-17. Only a court
        # nobody can read - not by a script, a browser or by hand - is left.
        self.assertEqual(sorted(courts.UNREADABLE), ["AL"])

    def test_a_court_a_browser_reads_has_a_read_in_the_cache(self):
        cache = courts.load_cache(ROOT)
        for code, recipe in courts.COURTS.items():
            if recipe.get("browser") or recipe.get("format") == "pdf":
                self.assertIn(code, cache["courts"], code)
        self.assertTrue(cache["courts"]["RI"].get("revised"))

    def test_every_roster_fits_its_court(self):
        for code, court in courts.load_cache(ROOT)["courts"].items():
            self.assertLessEqual(court["listed"], court["seats"], code)
            self.assertEqual(court["listed"], len(court["members"]), code)
            self.assertTrue(not court["chief"] or court["chief"] in court["members"], code)

    def test_the_page_gets_each_states_court(self):
        payload, _ = stategov.build(ROOT)
        for code in STATES:
            court = payload["states"][code]["court"]
            self.assertTrue(court.get("members") or court.get("unreadable"), code)


if __name__ == "__main__":
    unittest.main()
