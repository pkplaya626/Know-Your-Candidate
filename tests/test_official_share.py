"""Share pages for the federal officials and judges (rule 96; TECH-09).

The President, the Vice President, the Cabinet and every federal judge open
in the officials' dialog behind "#/official/<id>", which crawlers drop: a
shared official unfurled as the home page's card. Each now has o/<id>.html,
in the dialog's words (``shareWords`` in kyc-official.js), which the render
suite compares for every official (``testOfficialSharePages``) and asks every
case of this fixture about; these check the pipeline's side.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import emit, federal_build, official_share  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
SEAT = {"court": "ak", "title": "Judge", "appointedBy": "Barack Obama"}


def judge(**kwargs):
    base = {"id": "fjc-1", "name": "Jane Doe", "status": "active", "seats": [dict(SEAT)]}
    base.update(kwargs)
    return base


def found(kind="judge", person=None, office=None, court="ak"):
    return {"kind": kind, "person": person or judge(), "office": office,
            "court": court if kind == "judge" else None}


def portrait(**kwargs):
    base = {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/J.jpg/120px-J.jpg",
            "set": [[120, "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/J.jpg/120px-J.jpg"],
                    [250, "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/J.jpg/250px-J.jpg"]],
            "by": "U.S. Senate Judiciary Committee", "licence": "Public domain",
            "source": "https://commons.wikimedia.org/wiki/File:J.jpg", "route": "item", "year": 2018}
    base.update(kwargs)
    return base


_REAL = {}


def real_build():
    """The committed caches' federal build, once: what the site's pages are
    written from, for a test that writes into a folder without them."""
    if "build" not in _REAL:
        _REAL["build"] = federal_build.build(ROOT)
    return _REAL["build"]


class TestWordsTable(unittest.TestCase):
    """Every case is in tests/fixtures/official_share_words.json, which the
    render suite asks ``KYC.official.shareWords`` about, row by row."""

    def test_the_fixture_is_this_codes(self):
        with open(official_share.WORDS_TABLE, encoding="utf-8", newline="") as handle:
            on_disk = handle.read()
        self.assertEqual(on_disk, official_share.words_table_text(),
                         'regenerate: python -c "from kyc import official_share; '
                         'official_share.write_words_table()" after making the same change in '
                         "assets/kyc-official.js")

    def test_it_holds_every_kind_and_every_service(self):
        rows = official_share.words_table()["cases"]
        self.assertEqual({row[0] for row in rows}, {"leader", "officer", "former", "judge"})
        statuses = {row[3]["status"] for row in rows}
        for words in ("Active service", "Senior status", "Retired justice, not a member of the Court",
                      "Acting", "Left office Feb. 13, 2025", "Acting service ended March 2025",
                      "Left office; the sources differ on the date"):
            self.assertIn(words, statuses)
        self.assertTrue(any(s.startswith("Senior status from Oct. 5, 2026 by the courts’ list")
                            for s in statuses))


class TestWords(unittest.TestCase):

    def test_both_sources_of_a_judges_service_are_said(self):
        # Rule 82: Judge Varlan, senior by the courts' list and active by the
        # directory - neither picked silently.
        words = official_share.share_words(found(person=judge(listedSenior={"since": "2026-10-05"})))
        self.assertEqual(words["status"], "Senior status from Oct. 5, 2026 by the courts’ list of "
                                          "vacancies; the FJC directory still lists active service")

    def test_a_judge_and_a_cabinet_officer_have_no_party(self):
        words = official_share.share_words(found(person=judge(party="Democratic")))
        self.assertEqual(words["party"], "")
        self.assertEqual(words["appointedBy"], "Barack Obama")
        self.assertEqual(words["kind"], "U.S. District Court for the District of Alaska")
        officer = official_share.share_words(found(
            "officer", {"id": "x-b", "name": "B", "title": "Secretary of State", "party": "Republican"},
            {"office": "Secretary of State", "body": "Department of State"}))
        self.assertEqual((officer["kind"], officer["office"], officer["party"]),
                         ("Department of State", "Secretary of State", ""))
        page = official_share.render_official("fjc-1", found(person=judge(party="Democratic")),
                                              "example.org")
        self.assertNotIn("Democratic", page)

    def test_a_nomination_is_in_the_future_tense(self):
        to = {"id": "ca10", "name": "U.S. Court of Appeals for the Tenth Circuit",
              "nominated": "2026-05-12", "asOf": "2026-11-01"}
        page = official_share.render_official("fjc-1", found(person=judge(nominatedTo=to)),
                                              "example.org")
        self.assertIn('<p class="share-nominated">Nominated to the Court of Appeals for the Tenth '
                      "Circuit on May 12, 2026, pending in the Senate, as the courts’ list of "
                      "announced vacancies has it.</p>", page)
        # Nothing dated by a read: the list's own as-of day is the dialog's.
        self.assertNotIn("Nov. 1, 2026", page)

    def test_the_president_with_his_party_and_term(self):
        leader = {"id": "x-a", "name": "A B", "office": "President of the United States",
                  "party": "Republican", "since": "2025-01-20", "until": "2029-01-20"}
        page = official_share.render_official("x-a", found("leader", leader), "example.org")
        self.assertIn('<meta property="og:title" content="A B (Republican)">', page)
        self.assertIn("<strong>In office since Jan. 20, 2025; term ends Jan. 20, 2029</strong>", page)


class TestPicture(unittest.TestCase):
    """Only what the dialog shows, by its route (rules 24, 42, 82, 87, 101)."""

    def test_a_judges_commons_portrait_at_its_own_size_with_its_credit(self):
        url, credit = official_share.picture(found(person=judge(portrait=portrait())))
        self.assertTrue(url.endswith("/250px-J.jpg"))
        self.assertEqual(official_share.credit_html(credit),
                         'Photo (2018): U.S. Senate Judiciary Committee, Public domain, via '
                         '<a href="https://commons.wikimedia.org/wiki/File:J.jpg" target="_blank" '
                         'rel="noopener noreferrer">Wikimedia Commons</a>')
        _url, official = official_share.picture(found(person=judge(portrait=portrait(route="official"))))
        self.assertTrue(official_share.credit_html(official).startswith(
            "Official portrait, 2018. Photo: U.S. Senate"))

    def test_no_licence_or_another_host_is_the_card(self):
        for item in (judge(portrait=portrait(licence=None, credit="Supreme Court of the United States")),
                     judge(portrait=portrait(url="https://www.supremecourt.gov/x.jpg", set=[]))):
            self.assertEqual(official_share.picture(found(person=item)), (None, None), item)
        page = official_share.render_official("fjc-1", found(person=judge()), "example.org")
        self.assertIn('<meta property="og:image" content="https://example.org/assets/social-card.png">', page)
        self.assertNotIn("share-photo-credit", page)

    def test_the_white_house_photograph_or_its_copy_on_the_sites_host(self):
        holder = {"id": "x-b", "name": "B", "title": "Secretary of State",
                  "photo": "https://www.whitehouse.gov/b.jpeg",
                  "photoSet": [["https://www.whitehouse.gov/b.jpeg?resize=453,600", 453],
                               ["https://www.whitehouse.gov/b.jpeg?resize=768,1017", 768],
                               ["https://www.whitehouse.gov/b.jpeg", 967]]}
        office = {"office": "Secretary of State", "body": "Department of State"}
        url, credit = official_share.picture(found("officer", holder, office))
        self.assertEqual((url, credit), ("https://www.whitehouse.gov/b.jpeg?resize=453,600",
                                         {"by": "The White House"}))
        copied = dict(holder, photoCopy={"src": "photos/0123456789abcdef0123.jpg?v=0123456789",
                                         "of": holder["photo"], "ofBytes": 2084362})
        url, credit = official_share.picture(found("officer", copied, office), "example.org")
        self.assertEqual(url, "https://example.org/photos/0123456789abcdef0123.jpg?v=0123456789")
        self.assertIn("; a smaller copy made by this site of <a href=\"https://www.whitehouse.gov/b.jpeg\" "
                      'target="_blank" rel="noopener noreferrer">the original file (2.1 MB)</a>',
                      official_share.credit_html(credit))
        # A copy of another address is not this photograph's.
        other = dict(holder, photoCopy={"src": "photos/x.jpg", "of": "https://www.whitehouse.gov/c.jpeg"})
        self.assertEqual(official_share.picture(found("officer", other, office), "example.org")[0],
                         "https://www.whitehouse.gov/b.jpeg?resize=453,600")


class TestPages(unittest.TestCase):

    def test_its_own_address_and_the_view_it_opens(self):
        page = official_share.render_official("fjc-1", found(), "example.org")
        self.assertIn('<link rel="canonical" href="https://example.org/o/fjc-1.html">', page)
        self.assertIn('<a id="shareView" href="../courts/ak.html#/official/fjc-1">', page)
        self.assertIn("<title>Jane Doe — Know Your Candidate</title>", page)
        self.assertNotIn("<script>", page)
        justice = found(person=judge(justice={"role": "Chief Justice"},
                                     seats=[dict(SEAT, court="scotus", title="Chief Justice")]),
                        court=None)
        self.assertIn('href="../federal/index.html#/official/fjc-1"',
                      official_share.render_official("fjc-1", justice, "example.org"))

    def test_everyone_the_dialog_answers_to_and_no_one_twice(self):
        fed, per_court, _search, _problems = real_build()
        everyone = official_share.officials(fed, per_court)
        self.assertIn(fed["president"]["id"], everyone)
        self.assertEqual(everyone[fed["president"]["id"]]["kind"], "leader")
        for office in fed["offices"]:
            if office.get("holder"):
                self.assertEqual(everyone[office["holder"]["id"]]["kind"], "officer")
        for member in fed["supremeCourt"]["members"]:
            self.assertIsNone(everyone[member["id"]]["court"])
        judges = {j["id"] for c in per_court.values() for j in c["judges"]}
        self.assertTrue(judges <= set(everyone))
        for jid, entry in everyone.items():
            if entry["court"]:
                listed = per_court[entry["court"]]["judges"] + per_court[entry["court"]].get("retired", [])
                self.assertIn(jid, {j["id"] for j in listed})
        # No official is a profile (rule 27): their own folder, their own ids.
        self.assertTrue(all(oid.startswith(("x-", "fjc-")) for oid in everyone))


class TestBuiltAndVerified(unittest.TestCase):
    """Written with the profiles' share pages, checked by verify, cleaned up
    when an official is no longer held, never rewritten unchanged, and left
    alone when the federal build cannot run."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        os.makedirs(os.path.join(root, emit.SITE_DIR))
        with open(os.path.join(root, emit.CNAME_FILE), "w", encoding="utf-8") as f:
            f.write("example.org\n")
        self.root = root
        self.site = os.path.join(root, emit.SITE_DIR)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, build=None):
        with mock.patch.object(federal_build, "build", build or (lambda root: real_build())):
            return emit.write_state_pages([], self.root, summary={"states": {}}, stamp_from=ROOT,
                                          races=[])

    def check(self, build=None):
        with mock.patch.object(federal_build, "build", build or (lambda root: real_build())):
            return emit.check_state_pages([], self.root, {"states": {}}, ROOT, [])

    def test_written_checked_cleaned_up_and_kept(self):
        fed, per_court, _s, _p = real_build()
        everyone = official_share.officials(fed, per_court)
        self.write()
        folder = os.path.join(self.site, official_share.OFFICIAL_DIR)
        self.assertEqual(len(os.listdir(folder)), len(everyone))
        with open(os.path.join(self.site, "sitemap.xml"), encoding="utf-8") as f:
            xml = f.read()
        self.assertIn(f"<loc>https://example.org/o/{fed['president']['id']}.html</loc>", xml)
        self.assertEqual([p for p in self.check() if "/o/" in p[0].replace(os.sep, "/")], [])

        # Unchanged: not rewritten.
        page = os.path.join(folder, fed["president"]["id"] + ".html")
        os.utime(page, (1_000_000_000, 1_000_000_000))
        written = self.write()
        self.assertNotIn(page, written)
        self.assertEqual(os.path.getmtime(page), 1_000_000_000)

        # A hand edit, and a page for someone no longer held.
        with open(page, "a", encoding="utf-8") as f:
            f.write("<!-- by hand -->")
        with open(os.path.join(folder, "fjc-0.html"), "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>")
        found = {os.path.basename(rel): why for rel, why in self.check()
                 if os.path.dirname(rel).endswith(os.sep + "o")}
        self.assertEqual(found, {fed["president"]["id"] + ".html": "stale", "fjc-0.html": "orphaned"})
        self.write()
        self.assertFalse(os.path.exists(os.path.join(folder, "fjc-0.html")))

        # Without the federal build, none is written and none removed.
        def broken(root):
            raise federal_build.FederalBuildError("no caches")
        self.write(broken)
        self.assertEqual(len(os.listdir(folder)), len(everyone))
        self.assertEqual([p for p in self.check(broken) if "o" + os.sep in p[0]], [])


if __name__ == "__main__":
    unittest.main()
