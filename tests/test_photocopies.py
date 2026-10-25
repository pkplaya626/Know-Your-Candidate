"""Smaller copies of heavy portraits, made here (rule 101; the owner's
decision of 2026-10-25): the Oklahoma Senate's 9-12.5 MB portraits for a
56x70 box, the White House's up to 3.5 MB. A copy is only ever of an address
a record already shows, is that photograph smaller, keeps its original's
credit, and is never remade while the original is unchanged."""

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import judge_links, photocopies, portraits, share  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
HEAVY = "https://oksenate.gov/sites/default/files/Bergstrom.jpg"
LIGHT = "https://akleg.gov/images/legislators/ALR.jpg"
WIKI = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Someone.jpg"


def css():
    with open(os.path.join(ROOT, "candidate_profiles_site", "assets", "kyc.css"),
              encoding="utf-8") as handle:
        return handle.read()


def block(text, selector):
    """The declarations of the first rule for *selector*."""
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert match, selector
    return match.group(1)


def px(decls, prop):
    return int(re.search(r"(?m)^\s*" + prop + r":\s*(\d+)px", decls).group(1))


class FakeNet:
    """An original per address, and what each read answers."""

    def __init__(self):
        self.files = {}
        self.answers = {}
        self.reads = []
        self.fetches = []

    def jpeg(self, url, size, width=3000, height=4000, etag='"a"'):
        body = bytes([0xFF, 0xD8, 0xFF]) + hashlib.sha256(url.encode() + str(size).encode()).digest()
        body = (body * (size // len(body) + 1))[:size]
        self.files[url] = (body, width, height, etag)

    def prober(self, url, entry=None, headers=None):
        self.reads.append(url)
        if url in self.answers:
            return dict(self.answers[url])
        body, width, height, etag = self.files[url]
        if entry and entry.get("etag") == etag:
            return {"status": "unchanged"}
        whole = len(body) <= photocopies.HEAD_BYTES
        return {"status": "ok", "bytes": len(body), "width": width, "height": height,
                "etag": etag, "lastModified": "", "type": "image/jpeg",
                "data": body if whole else None}

    def fetcher(self, url, headers=None):
        self.fetches.append(url)
        return self.files[url][0]


class FakeChrome:
    def __init__(self):
        self.calls = 0
        self.deadlines = []

    def __call__(self, jobs, root, deadline=None):
        self.calls += 1
        self.deadlines.append(deadline)
        results = {}
        for job in jobs:
            with open(job["in"], "rb") as handle:
                data = handle.read()
            out = b"\xff\xd8\xff\xe0" + hashlib.sha256(data).digest() * 100
            with open(job["out"], "wb") as handle:
                handle.write(out)
            # The original's 3:4, covering the box (no copy is cropped).
            results[job["id"]] = {"ok": True, "width": job["box"][0],
                                  "height": round(job["box"][0] * 4 / 3),
                                  "srcWidth": 3000, "srcHeight": 4000, "bytes": len(out)}
        return {"chrome": "HeadlessChrome/156.0", "quality": photocopies.QUALITY,
                "results": results}


def shown(*pairs):
    s = photocopies.Shown()
    for url, kind in pairs:
        s.add(url, kind, f"{kind}:{url[-12:]}")
    return s


class TestBoxes(unittest.TestCase):
    """A copy covers three times the largest box a page draws its kind in,
    read back from the stylesheet: a box that grows must grow the copies."""

    def test_the_boxes_are_the_stylesheets(self):
        text = css()
        for kind, selector in (("legislator", ".leg-photo"), ("federal", ".modal-portrait img"),
                               ("governor", ".gov-portrait"), ("officer", ".gov-officer-photo")):
            decls = block(text, selector)
            self.assertEqual(photocopies.BOXES[kind], (px(decls, "width"), px(decls, "height")),
                             selector)
        fed = block(text, ".fed-photo")
        self.assertLessEqual(px(fed, "width"), photocopies.BOXES["federal"][0])
        self.assertLessEqual(px(fed, "height"), photocopies.BOXES["federal"][1])
        widest = re.search(r"\.senate-holder \.card-grid \{ grid-template-columns: "
                           r"minmax\(\d+px, (\d+)px\)", text)
        self.assertEqual(photocopies.BOXES["person"][0], int(widest.group(1)))
        self.assertEqual(photocopies.box_for(["legislator"]), [168, 210])
        self.assertEqual(photocopies.box_for(["legislator", "federal"]), [348, 435])


class TestRun(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "candidate_profiles_site", "data"))
        self.net = FakeNet()
        self.chrome = FakeChrome()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_once(self, s, **kw):
        return photocopies.run(self.root, shown=s, maker=self.chrome, prober=self.net.prober,
                               fetcher=self.net.fetcher, log=lambda *_: None, force=True,
                               workers=2, **kw)

    def cache(self):
        return photocopies.load(self.root)

    def photos(self):
        directory = os.path.join(self.root, photocopies.PHOTOS_DIR)
        return sorted(os.listdir(directory)) if os.path.isdir(directory) else []

    def test_a_heavy_original_is_copied_and_a_light_one_is_not(self):
        self.net.jpeg(HEAVY, 9_000_000)
        self.net.jpeg(LIGHT, 150_000, 450, 600)
        report = self.run_once(shown((HEAVY, "legislator"), (LIGHT, "legislator")))
        self.assertEqual((report["copied"], report["heavy"]), (1, 1))
        entry = self.cache()["originals"][HEAVY]
        copy = entry["copy"]
        self.assertEqual(entry["sha256"], hashlib.sha256(self.net.files[HEAVY][0]).hexdigest())
        self.assertEqual(copy["box"], [168, 210])
        self.assertEqual(self.photos(), [copy["file"]])
        self.assertTrue(copy["file"].startswith(copy["sha256"][:20]))
        self.assertEqual(copy["chrome"], "HeadlessChrome/156.0")
        self.assertNotIn("copy", self.cache()["originals"][LIGHT])
        self.assertEqual(self.cache()["originals"][LIGHT]["bytes"], 150_000)
        self.assertEqual(photocopies.problems(self.cache(), self.root), [])

    def test_an_unchanged_original_is_never_copied_again(self):
        self.net.jpeg(HEAVY, 9_000_000)
        s = shown((HEAVY, "legislator"))
        self.run_once(s)
        first = self.cache()["originals"][HEAVY]["copy"]
        report = self.run_once(s)
        self.assertEqual(report["unchanged"], 1)
        self.assertEqual(self.chrome.calls, 1)
        self.assertEqual(self.cache()["originals"][HEAVY]["copy"], first)
        # A server that ignores the conditional read, same file: read again,
        # same hash, kept - Chrome is not asked (rule 18).
        self.net.files[HEAVY] = self.net.files[HEAVY][:3] + ('"b"',)
        report = self.run_once(s)
        self.assertEqual((report["kept"], self.chrome.calls), (1, 1))
        self.assertEqual(self.cache()["originals"][HEAVY]["copy"], first)

    def test_a_changed_original_is_copied_again_and_the_old_copy_goes(self):
        self.net.jpeg(HEAVY, 9_000_000)
        s = shown((HEAVY, "legislator"))
        self.run_once(s)
        old = self.cache()["originals"][HEAVY]["copy"]["file"]
        self.net.jpeg(HEAVY, 8_000_000, etag='"new"')
        self.run_once(s)
        new = self.cache()["originals"][HEAVY]["copy"]["file"]
        self.assertNotEqual(old, new)
        self.assertEqual(self.photos(), [new])

    def test_a_changed_original_whose_copy_fails_shows_no_old_copy(self):
        self.net.jpeg(HEAVY, 9_000_000)
        s = shown((HEAVY, "legislator"))
        self.run_once(s)
        self.net.jpeg(HEAVY, 8_000_000, etag='"new"')

        def broken(jobs, root, deadline=None):
            raise photocopies.PhotoCopyError("no Chrome")
        photocopies.run(self.root, shown=s, maker=broken, prober=self.net.prober,
                        fetcher=self.net.fetcher, log=lambda *_: None, force=True)
        self.assertIsNone(photocopies.current(self.cache(), HEAVY))
        self.assertEqual(self.photos(), [])

    def test_a_changed_original_that_cannot_be_downloaded_loses_its_copy(self):
        # A seat-keyed file (rule 100) whose size changed may be a
        # successor's photograph: a download that then fails must not leave
        # the predecessor's copy shown until the next run.
        self.net.jpeg(HEAVY, 9_000_000)
        s = shown((HEAVY, "legislator"))
        self.run_once(s)
        self.net.jpeg(HEAVY, 8_000_000, etag='"new"')

        def refused(url, headers=None):
            raise OSError("connection reset")
        report = photocopies.run(self.root, shown=s, maker=self.chrome, prober=self.net.prober,
                                 fetcher=refused, log=lambda *_: None, force=True)
        self.assertIsNone(photocopies.current(self.cache(), HEAVY))
        self.assertEqual((report["removed"], report["errors"]), (1, 1))
        self.assertEqual(self.photos(), [])
        # Read again whole the next day, it is copied anew.
        self.run_once(s)
        self.assertIsNotNone(photocopies.current(self.cache(), HEAVY))

    def test_moving_validators_on_the_same_file_keep_the_copy(self):
        # The same bytes under a new ETag (a server whose machines disagree):
        # the copy is withdrawn while it is read, and given back on the hash.
        self.net.jpeg(HEAVY, 9_000_000)
        s = shown((HEAVY, "legislator"))
        self.run_once(s)
        first = self.cache()["originals"][HEAVY]["copy"]
        self.net.files[HEAVY] = self.net.files[HEAVY][:3] + ('"other-node"',)
        report = self.run_once(s)
        self.assertEqual((report["kept"], report["removed"], self.chrome.calls), (1, 0, 1))
        self.assertEqual(self.cache()["originals"][HEAVY]["copy"], first)

    def test_gone_twice_takes_the_copy_away_and_a_failure_concludes_nothing(self):
        self.net.jpeg(HEAVY, 9_000_000)
        s = shown((HEAVY, "legislator"))
        self.run_once(s)
        self.net.answers[HEAVY] = {"status": "error", "why": "HTTP 503", "code": 503}
        self.run_once(s)
        self.assertIsNotNone(photocopies.current(self.cache(), HEAVY))
        self.net.answers[HEAVY] = {"status": "gone", "code": 404}
        self.run_once(s)
        self.assertIsNotNone(photocopies.current(self.cache(), HEAVY), "once is not gone")
        self.run_once(s)
        self.assertIsNone(photocopies.current(self.cache(), HEAVY))
        self.assertEqual(self.photos(), [])

    def test_a_copy_no_record_shows_is_removed(self):
        self.net.jpeg(HEAVY, 9_000_000)
        self.run_once(shown((HEAVY, "legislator")))
        report = self.run_once(photocopies.Shown())
        self.assertEqual(report["orphans"], 1)
        self.assertEqual((self.cache()["originals"], self.photos()), ({}, []))

    def test_a_batch_is_oldest_first_and_keeps_what_it_did_not_reach(self):
        for i in range(3):
            self.net.jpeg(f"https://a{i}.example.gov/p.jpg", 9_000_000)
        s = shown(*[(f"https://a{i}.example.gov/p.jpg", "legislator") for i in range(3)])
        report = photocopies.run(self.root, shown=s, maker=self.chrome, prober=self.net.prober,
                                 fetcher=self.net.fetcher, log=lambda *_: None, limit=2)
        self.assertEqual((report["weighed"], report["skipped"]), (2, 1))
        originals = self.cache()["originals"]
        self.assertEqual(len(originals), 3, "the one not reached is kept, unread")
        self.assertEqual(sorted(u for u, e in originals.items() if not e.get("read")),
                         ["https://a2.example.gov/p.jpg"])
        self.net.reads.clear()
        photocopies.run(self.root, shown=s, maker=self.chrome, prober=self.net.prober,
                        fetcher=self.net.fetcher, log=lambda *_: None, limit=1, force=True)
        self.assertEqual(self.net.reads, ["https://a2.example.gov/p.jpg"], "never read comes first")

    def test_a_successor_on_the_same_address_is_read_again_before_it_is_shown_the_copy(self):
        # A seat's file passes from A to B. The copy made for A is not B's
        # until the file is read again whole, at once whatever its age, and
        # is the very file it was made of (the PR #137 review's blocker).
        self.net.jpeg(HEAVY, 9_000_000)
        a = photocopies.Shown()
        a.add(HEAVY, "legislator", "legislator:CT:A")
        photocopies.run(self.root, shown=a, maker=self.chrome, prober=self.net.prober,
                        fetcher=self.net.fetcher, log=lambda *_: None)
        copy = self.cache()["originals"][HEAVY]["copy"]
        self.assertEqual(copy["for"], ["legislator:CT:A"])
        self.assertIsNone(photocopies.current(self.cache(), HEAVY, "legislator", "legislator:CT:B"))
        b = photocopies.Shown()
        b.add(HEAVY, "legislator", "legislator:CT:B")
        # Not forced, read today: due all the same.
        self.assertEqual(photocopies._order(b, self.cache()), [HEAVY])
        self.assertEqual(photocopies._order(a, self.cache()), [])
        self.net.reads.clear()
        self.net.fetches.clear()
        report = photocopies.run(self.root, shown=b, maker=self.chrome, prober=self.net.prober,
                                 fetcher=self.net.fetcher, log=lambda *_: None)
        self.assertEqual((self.net.reads, self.net.fetches), ([HEAVY], [HEAVY]),
                         "read whole, not on its validators")
        self.assertEqual((report["kept"], self.chrome.calls), (1, 1))
        self.assertEqual(self.cache()["originals"][HEAVY]["copy"]["for"], ["legislator:CT:B"])
        self.assertIsNotNone(photocopies.current(self.cache(), HEAVY, "legislator", "legislator:CT:B"))
        # Had the file changed, B gets a new copy of the new file, and the
        # old one is gone.
        c = photocopies.Shown()
        c.add(HEAVY, "legislator", "legislator:CT:C")
        old = self.cache()["originals"][HEAVY]["copy"]["file"]
        self.net.files[HEAVY] = (self.net.files[HEAVY][0][:-1] + b"\x01",) + self.net.files[HEAVY][1:]
        photocopies.run(self.root, shown=c, maker=self.chrome, prober=self.net.prober,
                        fetcher=self.net.fetcher, log=lambda *_: None)
        copy = self.cache()["originals"][HEAVY]["copy"]
        self.assertNotEqual(copy["file"], old)
        self.assertEqual((copy["for"], self.photos()), (["legislator:CT:C"], [copy["file"]]))

    def test_the_weighing_is_kept_before_chrome_and_chrome_gets_the_budget(self):
        self.net.jpeg(HEAVY, 9_000_000)
        seen = {}

        def maker(jobs, root, deadline=None):
            seen["deadline"] = deadline
            seen["saved"] = photocopies.load(root)["originals"].get(HEAVY, {}).get("sha256")
            raise subprocess.TimeoutExpired("node", 1)
        photocopies.run(self.root, shown=shown((HEAVY, "legislator")), maker=maker,
                        prober=self.net.prober, fetcher=self.net.fetcher, log=lambda *_: None,
                        max_minutes=30)
        self.assertEqual(seen["saved"], hashlib.sha256(self.net.files[HEAVY][0]).hexdigest())
        self.assertGreater(seen["deadline"], time.time() * 1000 + 25 * 60 * 1000)
        self.assertIsNone(photocopies.current(self.cache(), HEAVY))

    def test_a_copy_made_for_a_smaller_box_is_made_again(self):
        self.net.jpeg(HEAVY, 9_000_000)
        self.run_once(shown((HEAVY, "legislator")))
        self.assertIsNone(photocopies.current(self.cache(), HEAVY, "person"))
        self.run_once(shown((HEAVY, "legislator"), (HEAVY, "person")))
        self.assertEqual(self.cache()["originals"][HEAVY]["copy"]["box"], [540, 675])
        self.assertIsNotNone(photocopies.current(self.cache(), HEAVY, "person"))


class TestProblems(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, photocopies.PHOTOS_DIR))
        data = b"\xff\xd8\xff\xe0copy"
        self.sha = hashlib.sha256(data).hexdigest()
        self.name = self.sha[:20] + ".jpg"
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, self.name), "wb") as handle:
            handle.write(data)
        self.cache = {"originals": {HEAVY: {
            "bytes": 9_000_000, "width": 3000, "height": 4000, "sha256": "ab" * 32,
            "read": "2026-10-25", "kinds": ["legislator"],
            "copy": {"file": self.name, "sha256": self.sha, "bytes": len(data), "width": 168,
                     "height": 224, "box": [168, 210], "chrome": "HeadlessChrome/156",
                     "quality": 0.86, "made": "2026-10-25", "from": [3000, 4000],
                     "for": ["legislator:OK:1", "person:1"]}}}}

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def codes(self, shown=None):
        return sorted({code for _, code, _ in photocopies.problems(self.cache, self.root, shown)})

    def test_a_sound_copy_passes(self):
        self.assertEqual(self.codes(), [])

    def test_every_file_is_listed_and_every_listed_file_is_itself(self):
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, "0" * 20 + ".jpg"), "wb") as h:
            h.write(b"x")
        self.assertEqual(self.codes(), ["photo-copy-unlisted"])
        os.remove(os.path.join(self.root, photocopies.PHOTOS_DIR, "0" * 20 + ".jpg"))
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, self.name), "ab") as h:
            h.write(b"tampered")
        self.assertIn("photo-copy-hash", self.codes())
        os.remove(os.path.join(self.root, photocopies.PHOTOS_DIR, self.name))
        self.assertIn("photo-copy-missing", self.codes())

    def test_a_copy_larger_than_its_box_or_of_a_light_file_fails(self):
        self.cache["originals"][HEAVY]["copy"].update(width=400, height=500)
        self.assertIn("photo-copy-oversize", self.codes())
        self.cache["originals"][HEAVY]["copy"].update(width=168, height=224)
        self.cache["originals"][HEAVY].update(bytes=120_000, width=400, height=500)
        self.assertIn("photo-copy-unneeded", self.codes())

    def test_never_a_copy_of_a_wikimedia_file(self):
        self.cache["originals"][WIKI] = self.cache["originals"].pop(HEAVY)
        self.assertIn("photo-copy-wikimedia", self.codes())
        s = photocopies.Shown()
        s.add(WIKI, "person", "person:x", {"photoCopy": {"src": "photos/x.jpg", "of": WIKI}})
        self.assertNotIn(WIKI, s.urls, "Wikimedia serves its own sizes (rule 42)")
        self.assertEqual([c for _, c, _ in s.issues], ["photo-copy-wikimedia"])

    def test_a_copy_is_shown_only_for_its_own_original_and_credited(self):
        s = photocopies.Shown()
        s.add(LIGHT, "legislator", "legislator:AK:1", {"photoCopy": {"src": "photos/a.jpg",
                                                                    "of": HEAVY}})
        s.add(HEAVY, "officer", "officer:AK:ag", {"photoCopy": {"src": "photos/a.jpg",
                                                               "of": HEAVY}}, credited=False)
        self.assertEqual(sorted(c for _, c, _ in s.issues),
                         ["photo-copy-misplaced", "photo-copy-uncredited"])

    def test_a_record_shows_exactly_the_manifests_copy(self):
        good = photocopies.src(self.cache["originals"][HEAVY]["copy"])
        s = photocopies.Shown()
        s.add(HEAVY, "legislator", "legislator:OK:1", {"photoCopy": {"src": good, "of": HEAVY}})
        self.assertNotIn("photo-copy-stale", self.codes(s))
        # A copy the manifest no longer holds, or one made for a smaller box
        # than the record is drawn in, is never shown.
        s = photocopies.Shown()
        s.add(HEAVY, "legislator", "legislator:OK:1",
              {"photoCopy": {"src": "photos/0000.jpg?v=0", "of": HEAVY}})
        self.assertIn("photo-copy-stale", self.codes(s))
        s = photocopies.Shown()
        s.add(HEAVY, "person", "person:1", {"photoCopy": {"src": good, "of": HEAVY}})
        self.assertIn("photo-copy-stale", self.codes(s))
        # Nor one made for another record on the same address.
        s = photocopies.Shown()
        s.add(HEAVY, "legislator", "legislator:OK:2", {"photoCopy": {"src": good, "of": HEAVY}})
        self.assertIn("photo-copy-stale", self.codes(s))

    def test_a_copy_records_whom_it_was_made_for_and_keeps_its_shape(self):
        self.cache["originals"][HEAVY]["copy"].pop("for")
        self.assertIn("photo-copy-unrecorded", self.codes())
        self.cache["originals"][HEAVY]["copy"]["for"] = ["legislator:OK:1"]
        # Cropped: no longer the original's shape.
        self.cache["originals"][HEAVY]["copy"]["from"] = [3000, 3000]
        self.assertIn("photo-copy-shape", self.codes())
        self.cache["originals"][HEAVY]["copy"]["from"] = [3000, 4000]
        self.assertEqual(self.codes(), [])
        # The file's own pixels are the manifest's.
        data = png(168, 230)
        sha = hashlib.sha256(data).hexdigest()
        os.remove(os.path.join(self.root, photocopies.PHOTOS_DIR, self.name))
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, sha[:20] + ".jpg"), "wb") as h:
            h.write(data)
        self.cache["originals"][HEAVY]["copy"].update(file=sha[:20] + ".jpg", sha256=sha,
                                                      bytes=len(data))
        self.assertEqual(self.codes(), ["photo-copy-shape"])

    def test_what_is_left_is_counted_by_kind(self):
        s = shown((HEAVY, "legislator"), (LIGHT, "officer"))
        self.cache["originals"][HEAVY].pop("copy")
        os.remove(os.path.join(self.root, photocopies.PHOTOS_DIR, self.name))
        found = {code: message for _, code, message in photocopies.problems(self.cache, self.root, s)}
        self.assertIn("legislator 1", found["photo-copies-missing"])
        self.assertIn("officer 1", found["photo-copies-unweighed"])


class TestAttach(unittest.TestCase):
    cache = {"originals": {HEAVY: {"bytes": 9_000_000, "copy": {
        "file": "abc.jpg", "sha256": "0123456789abcdef", "box": [168, 210],
        "for": ["legislator:OK:ocd-person/1", "legislator::ocd-person/1"]}}}}

    def test_the_copy_is_named_stamped_and_tied_to_its_original(self):
        member = {"id": "ocd-person/1", "image": HEAVY,
                  "imageCredit": {"by": "Oklahoma Legislature", "page": "https://oksenate.gov/x"}}
        self.assertTrue(photocopies.attach(member, HEAVY, self.cache, "legislator"))
        self.assertEqual(member["photoCopy"], {"src": "photos/abc.jpg?v=0123456789", "of": HEAVY,
                                               "ofBytes": 9_000_000})
        self.assertEqual(member["image"], HEAVY, "the record keeps its original")
        self.assertFalse(photocopies.attach(member, LIGHT, self.cache, "legislator"))
        self.assertNotIn("photoCopy", member)
        self.assertFalse(photocopies.attach({}, HEAVY, self.cache, "federal"),
                         "a copy made for a 56x70 card is not sharp in a 116px dialog")

    def test_a_copy_is_only_ever_shown_for_the_record_it_was_made_for(self):
        # A seat-keyed address (rule 100) passes to a successor: the copy
        # made while it showed the predecessor is never shown for them, and
        # the card draws the original, as before the copies (PR #137 review).
        payload = {"chambers": {"upper": {"members": {"1": [{"id": "ocd-person/1", "image": HEAVY},
                                                            {"id": "ocd-person/2", "image": HEAVY}]}}}}
        self.assertEqual(photocopies.apply_legislature(payload, self.cache, "OK"), 1)
        first, second = payload["chambers"]["upper"]["members"]["1"]
        self.assertIn("photoCopy", first)
        self.assertNotIn("photoCopy", second)
        # A governor or an officer is keyed by name, never by seat.
        self.assertEqual(photocopies.key_of("officer", {"name": "Cori Mills"}, "AK", "ag"),
                         "officer:AK:ag:Cori Mills")
        self.assertEqual(photocopies.key_of("governor", {"name": "Mike Dunleavy"}, "AK"),
                         "governor:AK:Mike Dunleavy")

    def test_a_copy_is_of_the_file_the_records_own_source_weighed(self):
        # The legislature's own photograph (rule 100) is copied only where
        # this cache read the file legphotos weighed: the same length, the
        # same day of Last-Modified.
        cache = {"originals": {HEAVY: dict(self.cache["originals"][HEAVY],
                                           lastModified="Thu, 06 Mar 2025 10:00:00 GMT")}}
        member = {"id": "ocd-person/1", "image": HEAVY}
        photos = {"people": {"ocd-person/1": {"image": HEAVY, "bytes": 9_000_000,
                                              "lastModified": "2025-03-06"}}}
        payload = {"members": [member]}
        self.assertEqual(photocopies.apply_legislature(payload, cache, "OK", photos), 1)
        for change in ({"bytes": 8_000_000}, {"lastModified": "2026-01-10"}):
            photos["people"]["ocd-person/1"].update(change)
            self.assertEqual(photocopies.apply_legislature(payload, cache, "OK", photos), 0, change)
            self.assertNotIn("photoCopy", member)
            photos = {"people": {"ocd-person/1": {"image": HEAVY, "bytes": 9_000_000,
                                                  "lastModified": "2025-03-06"}}}
        # "Over the cap" is not a length legphotos read.
        photos["people"]["ocd-person/1"]["bytes"] = 300_001
        self.assertEqual(photocopies.expected("OK", member, photos), {"lastModified": "2025-03-06"})
        # Another file than the card shows says nothing about this one.
        photos["people"]["ocd-person/1"]["image"] = LIGHT
        self.assertIsNone(photocopies.expected("OK", member, photos))

    def test_a_legislators_portrait_is_copied_only_from_a_governments_host(self):
        # Open States also lists news sites' and campaigns' photographs:
        # those stay drawn from their own host (PR #137 review; rule 101).
        news = "https://www.chicagotribune.com/wp-content/uploads/2026/07/x.jpg"
        for url, ok in ((HEAVY, True), ("https://www2.housedems.ct.gov/p.jpg", True),
                        ("http://www.legislature.state.al.us/aliswww/p.jpg", True),
                        (news, False), ("https://images.squarespace-cdn.com/p.jpg", False),
                        ("https://senatedems.com/p.jpg", False), (WIKI, False)):
            self.assertEqual(photocopies.may_copy(url, "legislator", "OK"), ok, url)
        self.assertTrue(photocopies.may_copy("https://bobsmithforcongress.com/p.jpg", "person"))
        cache = {"originals": {news: dict(self.cache["originals"][HEAVY])}}
        member = {"id": "ocd-person/1", "image": news}
        self.assertFalse(photocopies.attach(member, news, cache, "legislator", code="IL"))
        s = photocopies.Shown()
        s.add(news, "legislator", "legislator:IL:1", {"photoCopy": {"src": "photos/a.jpg", "of": news}},
              code="IL")
        self.assertNotIn(news, s.urls)
        self.assertEqual(s.linked, {news: {"legislator"}})
        self.assertEqual([c for _, c, _ in s.issues], ["photo-copy-host"])

    def test_a_profile_without_a_credit_gets_no_copy(self):
        cache = {"originals": {HEAVY: dict(self.cache["originals"][HEAVY],
                                           copy=dict(self.cache["originals"][HEAVY]["copy"],
                                                     box=[540, 675], **{"for": ["person:a", "person:b"]}))}}
        people = [{"id": "a", "photos": [HEAVY], "photoCredit": {"by": "x.com"}},
                  {"id": "b", "photos": [HEAVY]}]
        self.assertEqual(photocopies.apply_people(people, cache), 1)
        self.assertIn("photoCopy", people[0])
        self.assertNotIn("photoCopy", people[1])

    def test_a_shared_profile_unfurls_with_the_copy_on_the_sites_host(self):
        person = {"photo_url": HEAVY, "photoSource": "campaign-site",
                  "photoCredit": {"by": "x.com"},
                  "photoCopy": {"src": "photos/abc.jpg?v=0123456789", "of": HEAVY}}
        self.assertEqual(share.og_photo(person, "candidates.example.org"),
                         "https://candidates.example.org/photos/abc.jpg?v=0123456789")
        self.assertEqual(share.og_photo(dict(person, photoCopy=None), "candidates.example.org"),
                         HEAVY)


class TestJusticesYears(unittest.TestCase):
    """Five of the nine justices' Commons portraits are older than the
    Court's current ones: the credit says the year Commons dates each to,
    and only that."""

    def test_a_year_is_one_the_page_gives(self):
        self.assertEqual(portraits.year_of("2005"), 2005)
        self.assertEqual(portraits.year_of("21 August 2009, per metadata"), 2009)
        self.assertEqual(portraits.year_of("2017-05-25 11:50:06"), 2017)
        self.assertIsNone(portraits.year_of("between 2005 and 2006"))
        self.assertIsNone(portraits.year_of("circa the 1990s"))
        self.assertIsNone(portraits.year_of(None))
        info = {"extmetadata": {"DateTimeOriginal": {"value": "2007-09-24"},
                                "LicenseShortName": {"value": "Public domain"}}}
        self.assertEqual(portraits.credit_of(info)["year"], 2007)
        self.assertIn("DateTimeOriginal", portraits._CREDIT_FIELDS)

    def test_only_an_official_portrait_carries_it_and_none_is_guessed(self):
        self.assertEqual(judge_links.dated({"year": 2005}), {"year": 2005})
        self.assertEqual(judge_links.dated({"year": None}), {"yearUnstated": True})
        self.assertIn("year", judge_links.PAGE_KEYS)
        cache = judge_links.load_cache(ROOT)
        official = [e["portrait"] for e in cache["judges"].values()
                    if (e.get("portrait") or {}).get("route") == "official"]
        self.assertEqual(len(official), 9)
        self.assertTrue(all("year" in p or p.get("yearUnstated") for p in official))
        self.assertFalse(any("year" in e.get("portrait", {}) for e in cache["judges"].values()
                             if (e.get("portrait") or {}).get("route") != "official"))

    def test_a_portrait_read_before_the_year_was_is_read_again(self):
        cache = {"judges": {"1": {"portrait": {
            "credit": "Wikimedia Commons", "route": "official", "licence": "Public domain",
            "creditForm": portraits.CREDIT_FORM, "by": "Steve Petteway",
            "url": "https://upload.wikimedia.org/wikipedia/commons/4/43/Official_roberts_CJ.jpg"}}}}

        def info_of(urls):
            return {u: {"width": 2000, "height": 2500, "descriptionurl": "d", "extmetadata": {
                "Artist": {"value": "Steve Petteway"}, "LicenseShortName": {"value": "Public domain"},
                "DateTimeOriginal": {"value": "2005"}}} for u in urls}
        self.assertEqual(judge_links.credit_portraits(cache, info_of, log=None), (1, 0))
        self.assertEqual(cache["judges"]["1"]["portrait"]["year"], 2005)
        self.assertEqual(judge_links.credit_portraits(cache, info_of, log=None), (0, 0))


def png(width, height):
    """A grey PNG with a transparent band, for the maker."""
    rows = b"".join(b"\x00" + bytes([128, 128, 128, 0 if y < height // 4 else 255]) * width
                    for y in range(height))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class TestChrome(unittest.TestCase):
    """The maker itself, in a real headless Chrome where one is installed."""

    def test_a_copy_just_covers_its_box_and_is_a_jpeg(self):
        if not shutil.which("node"):
            self.skipTest("no node")
        tmp = tempfile.mkdtemp()
        try:
            source = os.path.join(tmp, "in.png")
            with open(source, "wb") as handle:
                handle.write(png(1500, 2000))
            jobs = [{"id": "a", "in": source, "out": os.path.join(tmp, "a.jpg"), "box": [168, 210]},
                    {"id": "b", "in": source, "out": os.path.join(tmp, "b.jpg"), "box": [3000, 4000]}]
            try:
                made = photocopies.make_copies(jobs, ROOT)
            except photocopies.PhotoCopyError as exc:
                self.skipTest(f"no Chrome here: {exc}")
            a, b = made["results"]["a"], made["results"]["b"]
            self.assertTrue(a["ok"], a)
            self.assertEqual((a["width"], a["height"]), (168, 224))
            self.assertEqual((a["srcWidth"], a["srcHeight"]), (1500, 2000))
            self.assertEqual((b["width"], b["height"]), (1500, 2000), "never scaled up")
            with open(jobs[0]["out"], "rb") as handle:
                data = handle.read()
            self.assertEqual(data[:3], b"\xff\xd8\xff")
            self.assertEqual(portraits.image_size(data), (168, 224))
            self.assertTrue(made["chrome"])
            # Past its deadline the maker starts nothing, and says so.
            late = photocopies.make_copies(jobs[:1], ROOT, deadline=int(time.time() * 1000) - 1)
            self.assertEqual((late["results"]["a"]["ok"], late["results"]["a"]["error"]),
                             (False, "out of time"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCommitted(unittest.TestCase):
    def test_the_committed_copies_are_sound(self):
        cache = photocopies.load(ROOT)
        errors = [p for p in photocopies.problems(cache, ROOT) if p[0] == "error"]
        self.assertEqual(errors, [])
        for url in cache["originals"]:
            self.assertFalse(photocopies.is_wikimedia(url), url)
        for url, entry in cache["originals"].items():
            if entry.get("copy"):
                self.assertTrue(entry["copy"].get("for"), url)

    def test_the_validate_only_build_checks_the_records_too(self):
        # `build --check` ran only the manifest's file checks; the records'
        # (stale, misplaced, uncredited, the counts) ran only in a writing
        # build and in verify (the reviewers of PR #137).
        import inspect
        from kyc import cli
        source = inspect.getsource(cli._build)
        check_return = source.index('print("\\n[check] validation only, nothing written.")')
        gathered = source.index("photocopies.gather(args.root, people=profiles)")
        self.assertLess(gathered, check_return)


if __name__ == "__main__":
    unittest.main()
