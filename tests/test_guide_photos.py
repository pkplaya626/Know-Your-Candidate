"""The election offices' own guides' photographs, hosted here unmodified
(kyc/guide_photos.py; the owner's decision of 2026-10-25).

Washington's voters' guide serves each photograph only base64 inside its
JSON, Alaska's pamphlet only inside each candidate's statement PDF. A
photograph is joined to a person only where the guide's own page names them
beside it, for that office, in words of their filing, profile or list - any
order, never a surname alone, a short form only by an evidenced entry - and
only where the name fits one person; the bytes are hosted unmodified, listed
in rule 101's manifest, and checked there both ways."""

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import guide_photos, pdfread, photocopies, statewide_photos  # noqa: E402


def jpeg(width=300, height=400, components=3, adobe=None, pad=2000, seed=b""):
    """A JPEG's markers (no picture): enough for its size and components."""
    out = b"\xff\xd8"
    if adobe is not None:
        body = b"Adobe" + b"\x00\x64" + b"\x00\x00" + b"\x00\x00" + bytes([adobe])
        out += b"\xff\xee" + (len(body) + 2).to_bytes(2, "big") + body
    sof = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + bytes([components])
    for i in range(components):
        sof += bytes([i + 1, 0x11, 0])
    out += b"\xff\xc0" + (len(sof) + 2).to_bytes(2, "big") + sof
    out += b"\xff\xda\x00\x02" + (hashlib.sha256(seed).digest() * (pad // 32 + 1))[:pad]
    return out + b"\xff\xd9"


def pdf(lines, images=(), form=False, encrypt=False, catalog_extra=""):
    """A one-page PDF whose page shows *lines* (top down) and draws each of
    *images* (``(jpeg bytes, colour space)``), optionally through a form."""
    objects = {}
    content = "BT /F1 12 Tf 50 700 Td " + " ".join(
        f"({line}) Tj 0 -14 Td" for line in lines) + " ET\n"
    xobjects = {}
    n = 10
    for i, (data, space) in enumerate(images):
        objects[n] = (f"<< /Type /XObject /Subtype /Image /Width 300 /Height 400 "
                      f"/ColorSpace /{space} /BitsPerComponent 8 /Filter /DCTDecode "
                      f"/Length {len(data)} >>").encode(), data
        xobjects[f"Im{i}"] = n
        n += 1
    draws = "".join(f"q 100 0 0 120 {40 + 150 * i} 400 cm /Im{i} Do Q\n"
                    for i in range(len(images)))
    names = " ".join(f"/{k} {v} 0 R" for k, v in xobjects.items())
    if form:
        inner = draws.encode()
        objects[n] = (f"<< /Type /XObject /Subtype /Form /BBox [0 0 600 800] "
                      f"/Resources << /XObject << {names} >> >> /Length {len(inner)} >>").encode(), inner
        names = f"/Fm0 {n} 0 R"
        draws = "q /Fm0 Do Q\n"
    body = (content + draws).encode()
    objects[3] = (f"<< /Length {len(body)} >>").encode(), body
    objects[2] = (f"<< /Type /Page /Parent 1 0 R /MediaBox [0 0 504 720] /Contents 3 0 R "
                  f"/Resources << /Font << /F1 4 0 R >> /XObject << {names} >> >> >>").encode(), None
    objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", None
    objects[1] = b"<< /Type /Pages /Kids [2 0 R] /Count 1 >>", None
    objects[5] = (f"<< /Type /Catalog /Pages 1 0 R {catalog_extra}>>").encode(), None
    out = b"%PDF-1.4\n"
    for num in sorted(objects):
        head, stream = objects[num]
        out += f"{num} 0 obj\n".encode() + head
        if stream is not None:
            out += b"\nstream\n" + stream + b"\nendstream"
        out += b"\nendobj\n"
    out += b"trailer\n<< /Root 5 0 R" + (b" /Encrypt 6 0 R" if encrypt else b"") + b" >>\n%%EOF\n"
    return out


def profile(pid, name, filed=None, district=4, state="WA", photos=None, chamber="House (Candidate)"):
    return {"id": pid, "name": name, "filedName": filed, "state": state, "chamber": chamber,
            "districtNum": district, "isCandidate": True, "raceStatus": "nominee",
            "photos": photos or ["placeholder"]}


def wa_index(races):
    return json.dumps({"Categories": [{"CategoryCode": "FED", "Races": [
        {"RaceID": rid, "Name": "U.S. Representative", "Jurisdiction": f"Congressional District {d}",
         "Candidates": [{"BallotID": b, "BallotName": n, "PartyName": p} for b, n, p in people]}
        for rid, d, people in races]}]}).encode()


def wa_record(race, entries):
    return json.dumps([{"statement": {"RaceID": race, "BallotID": b, "BallotName": n,
                                      "PartyName": p,
                                      "Photo": base64.b64encode(data).decode() if data else None}}
                       for b, n, p, data in entries]).encode()


class Getter:
    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def __call__(self, url, limit=None):
        self.asked.append(url)
        if url not in self.pages:
            raise guide_photos.GuidePhotoError(f"could not read {url}: HTTP 503")
        return self.pages[url]


class TestNames(unittest.TestCase):
    def test_any_order_and_the_lists_own_forms(self):
        w = guide_photos.name_words
        self.assertEqual(w("Sullivan, Daniel J. Jr."), w("Daniel J. Sullivan Jr."))
        self.assertEqual(w("Sullivan, Daniel J. Jr."), ("daniel", "j", "sullivan"))
        self.assertEqual(w("SULLIVAN, DANIEL J", filed=True), ("daniel", "j", "sullivan"))
        self.assertEqual(w("Kreiss-Tomkins, Jonathan S. “JKT”"),
                         w("Jonathan S. Kreiss-Tomkins “JKT”"))
        self.assertEqual(w("KAHL, BARBARA J DR DVM", filed=True), ("barbara", "j", "kahl"))

    def test_an_initial_tells_two_sullivans_apart(self):
        w = guide_photos.name_words
        self.assertNotEqual(w("Sullivan, Dan S."), w("Daniel J. Sullivan Jr."))
        self.assertNotEqual(w("Sullivan, Dan S."), w("Dan Sullivan"))


class TestJoin(unittest.TestCase):
    def join(self, names, people, forms=None):
        entries = [{"name": n} for n in names]
        with mock.patch("kyc.overrides.GUIDE_NAME_FORMS", forms or {}, create=True):
            return guide_photos.join("WA", entries, people, guide_photos.profile_key_of,
                                     guide_photos.person_words)

    def test_the_guides_name_joins_the_one_person_it_names(self):
        people = [profile("A", "John Duresky", "DURESKY, JOHN"),
                  profile("B", "Amanda McKinney", "MCKINNEY, AMANDA")]
        joined, problems = self.join(["Amanda McKinney", "John Duresky"], people)
        self.assertEqual(joined, {0: "person:B", 1: "person:A"})
        self.assertEqual(problems, [])

    def test_the_filings_words_in_any_order(self):
        people = [profile("A", "Doug Basler", "BASLER, DOUGLAS MICHAEL")]
        self.assertEqual(self.join(["Douglas Michael Basler"], people)[0], {0: "person:A"})

    def test_never_a_surname_alone_nor_a_short_form_without_evidence(self):
        people = [profile("A", "Teresa Fox", "FOX, TERESA")]
        self.assertEqual(self.join(["Fox"], people)[0], {})
        self.assertEqual(self.join(["Terri Fox"], people)[0], {})
        self.assertEqual(self.join(["Edwin H. Feller"],
                                   [profile("F", "Edwin Harold Feller",
                                            "FELLER, EDWIN HAROLD")])[0], {})
        # An evidenced entry names the person it stands for.
        forms = {("WA", "Terri Fox"): ("person:A", "her campaign's site, read 2026-10-25")}
        self.assertEqual(self.join(["Terri Fox"], people, forms)[0], {0: "person:A"})

    def test_a_namesake_is_refused(self):
        people = [profile("A", "John Smith", "SMITH, JOHN"),
                  profile("B", "John Smith", "SMITH, JOHN")]
        joined, problems = self.join(["John Smith"], people)
        self.assertEqual(joined, {})
        self.assertTrue(any("fits 2 people" in p for p in problems), problems)

    def test_two_of_the_guides_names_for_one_person_are_refused(self):
        people = [profile("A", "John Smith", "SMITH, JOHN")]
        joined, problems = self.join(["John Smith", "Smith, John"], people)
        self.assertEqual(joined, {})
        self.assertTrue(problems)


AK_PAGE = """
<h4><a id="sen"></a>UNITED STATES SENATOR</h4>
<table><tbody>
<tr><td><a id="Sullivan%2C+Dan+S."></a><strong>Sullivan, Dan S.</strong><br><small>(Registered Republican)</small></td>
<td>x</td><td>x</td><td><ul><li><strong>Candidate Statement</strong>
<br><a class="l" href="https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DAN%20S_US%20Sen.pdf">s</a></li></ul></td></tr>
<tr><td><a id="Sullivan%2C+Daniel+J.+Jr."></a><strong>Sullivan, Daniel J. Jr.</strong><br><small>(Registered Republican)</small></td>
<td>x</td><td>x</td><td><ul><li><strong>Candidate Statement</strong>
<br><a class="l" href="https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DANIEL%20J.%20JR%20_US%20Sen.pdf">s</a></li></ul></td></tr>
</tbody></table>
<h4><a id="gov"></a>GOVERNOR / LIEUTENANT GOVERNOR</h4>
<table><tbody>
<tr><td><strong>Taylor, Treg/ English, Candi</strong><br><small>(Registered Republican)</small></td>
<td>x</td><td>x</td><td><ul><li><strong>Governor Statement</strong>
<br><a class="l" href="https://elections.alaska.gov/doc/oep/2026/TAYLOR.pdf">s</a></li>
<li><strong>Running Mate Statement</strong><br><a class="l" href="https://elections.alaska.gov/doc/oep/2026/ENGLISH.pdf">s</a></li></ul></td></tr>
</tbody></table>
<h4>UNITED STATES REPRESENTATIVE</h4>
<table><tbody>
<tr><td><strong>Hill, Bill</strong></td><td>x</td><td>x</td><td><ul><li><strong>Candidate Statement</strong>
<br><a class="l" href="https://elections.alaska.gov/doc/oep/2026/HILL.pdf">s</a></li></ul></td></tr>
</tbody></table>
<h4>SENATE DISTRICT A</h4>
"""


class TestAlaska(unittest.TestCase):
    def setUp(self):
        self.member = profile("S001198", "Dan Sullivan", "SULLIVAN, DAN", state="AK",
                              chamber="Senate (Candidate)", district=None,
                              photos=["https://clerk.example/s.jpg"])
        self.jr = profile("FEC_S6AK00326", "Daniel J. Sullivan Jr.", "SULLIVAN, DANIEL J",
                          state="AK", chamber="Senate (Candidate)", district=None)

    def statement(self, office, name, images=None, space="DeviceGray"):
        if images is None:
            images = [(jpeg(components=1, seed=name.encode()), space)]
        return pdf([office, f"{name}, Registered Republican", "STATEMENT:"], images)

    def pages(self, **more):
        out = {guide_photos.AK_LIST: AK_PAGE.encode(),
               "https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DAN%20S_US%20Sen.pdf":
                   self.statement("United States Senator", "Dan S. Sullivan"),
               "https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DANIEL%20J.%20JR%20_US%20Sen.pdf":
                   self.statement("United States Senator", "Daniel J. Sullivan Jr."),
               "https://elections.alaska.gov/doc/oep/2026/TAYLOR.pdf":
                   self.statement("Governor", "Treg Taylor"),
               "https://elections.alaska.gov/doc/oep/2026/ENGLISH.pdf":
                   self.statement("Lieutenant Governor", "Candi English"),
               "https://elections.alaska.gov/doc/oep/2026/HILL.pdf":
                   pdf(["United States Representative", "Bill Hill, Nonpartisan"],
                       [(jpeg(components=4, adobe=2), "DeviceCMYK")])}
        out.update(more)
        return out

    def test_the_list_pairs_each_statement_with_its_name(self):
        rows = guide_photos.ak_rows(AK_PAGE)
        self.assertEqual([r["names"] for r in rows],
                         [["Sullivan, Dan S."], ["Sullivan, Daniel J. Jr."],
                          ["Taylor, Treg", "English, Candi"], ["Hill, Bill"]])
        self.assertEqual(sorted(rows[2]["statements"]), [0, 1])

    def test_the_sullivans_are_joined_only_on_the_initial_and_the_suffix(self):
        getter = Getter(self.pages())
        photos, problems, _ = guide_photos.read_alaska(
            {"S-AK-2026": [self.member, self.jr]}, getter=getter)
        self.assertEqual(sorted(photos), ["person:FEC_S6AK00326"])
        rec = photos["person:FEC_S6AK00326"]
        self.assertIn("SULLIVAN,%20DANIEL%20J.%20JR", rec["page"])
        self.assertIn("'Daniel J. Sullivan Jr., Registered Republican'", rec["evidence"])
        self.assertIn("Sullivan%2C+Daniel+J.+Jr.", rec["list"])
        # Never the incumbent's statement for him: "Dan S." is not "Dan".
        self.assertNotIn("person:S001198", photos)
        self.assertNotIn("https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DAN%20S_US%20Sen.pdf",
                         getter.asked)

    def test_the_statement_must_name_them_under_the_office(self):
        wrong = self.statement("United States Senator", "Dan S. Sullivan")
        getter = Getter(self.pages(**{
            "https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DANIEL%20J.%20JR%20_US%20Sen.pdf": wrong}))
        photos, problems, _ = guide_photos.read_alaska({"S-AK-2026": [self.jr]}, getter=getter)
        self.assertEqual(photos, {})
        self.assertTrue(any("names 'Dan S. Sullivan'" in p for p in problems), problems)

    def test_a_cmyk_photograph_is_refused(self):
        hill = profile("H", "Bill Hill", "HILL, BILL", state="AK", district=0)
        photos, problems, _ = guide_photos.read_alaska({"H-AK-00-2026": [hill]},
                                                       getter=Getter(self.pages()))
        self.assertEqual(photos, {})
        self.assertTrue(any("CMYK" in p for p in problems), problems)
        self.assertIn("inverted", guide_photos.drawable(jpeg(components=4, adobe=2)))
        self.assertTrue(guide_photos.drawable(jpeg(components=1), "DeviceCMYK"))
        self.assertTrue(guide_photos.drawable(jpeg(components=3), "ICCBased"))
        self.assertEqual(guide_photos.drawable(jpeg(components=1), "DeviceGray"), "")

    def test_a_pdf_with_two_photographs_or_none_gives_none(self):
        two = pdf(["Governor", "Treg Taylor, Registered Republican"],
                  [(jpeg(components=1, seed=b"a"), "DeviceGray"),
                   (jpeg(components=1, seed=b"b"), "DeviceGray")])
        raw, _space, _words, why = guide_photos.ak_statement(two, "governor", "Taylor, Treg")
        self.assertIsNone(raw)
        self.assertIn("2 images", why)
        none = pdf(["Governor", "Treg Taylor, Registered Republican"], [])
        self.assertIn("0 images", guide_photos.ak_statement(none, "governor", "Taylor, Treg")[3])
        # Through a form, the one image it draws is the one photograph.
        one = pdf(["Governor", "Treg Taylor, Registered Republican"],
                  [(jpeg(components=1), "DeviceGray")], form=True)
        raw, space, words, why = guide_photos.ak_statement(one, "governor", "Taylor, Treg")
        self.assertEqual((raw, space, why), (jpeg(components=1), "DeviceGray", ""))

    def test_the_tickets_statements_go_to_governor_and_running_mate(self):
        wanted = {"AK|governor": [{"key": "candidate:AK:governor:Treg Taylor",
                                   "name": "Taylor, Treg"}],
                  "AK|lt": [{"key": "candidate:AK:lt:Candi English", "name": "English, Candi"}]}
        photos, problems, _ = guide_photos.read_alaska(wanted, getter=Getter(self.pages()))
        self.assertEqual(sorted(photos), ["candidate:AK:governor:Treg Taylor",
                                          "candidate:AK:lt:Candi English"])
        self.assertTrue(photos["candidate:AK:lt:Candi English"]["page"].endswith("ENGLISH.pdf"))

    def test_an_unreadable_list_concludes_nothing(self):
        photos, problems, unread = guide_photos.read_alaska({"S-AK-2026": [self.jr]},
                                                            getter=Getter({}))
        self.assertEqual(photos, {})
        self.assertEqual(unread, {"S-AK-2026"})


class TestPdfRead(unittest.TestCase):
    def test_what_a_page_draws_not_what_the_file_holds(self):
        # The catalog's own words name "/Image" (the research reader counted
        # them across objects); only the Do of the page's one image counts.
        data = pdf(["Governor", "Treg Taylor, Registered Republican"],
                   [(jpeg(components=1), "DeviceGray")], catalog_extra="/Note (/Image /Image) ")
        doc = pdfread.Document(data)
        read = pdfread.read_page(doc, doc.pages()[0])
        self.assertEqual(len(read["images"]), 1)
        self.assertEqual(read["images"][0]["box"], (40.0, 400.0, 140.0, 520.0))
        self.assertEqual(pdfread.page_text(read).split("\n")[:2],
                         ["Governor", "Treg Taylor, Registered Republican"])

    def test_runs_that_abut_are_one_word_and_runs_apart_are_two(self):
        # Alaska's statements set "Registered Demo" and "crat" as two runs
        # (Kreiss-Tomkins's); the cache quoted "Registered Demo crat".
        runs = [(50, "Registered Demo"), (50 + 15 * 5, "crat"), (200, "Next"),
                (200 + 4 * 5 + 1, "word")]
        body = "".join(f"BT /F1 10 Tf 1 0 0 1 {x} 700 Tm ({t}) Tj ET\n" for x, t in runs)
        body += "BT /F2 10 Tf 1 0 0 1 50 650 Tm (Plain) Tj ET\nBT /F2 10 Tf 1 0 0 1 75 650 Tm (font) Tj ET\n"
        widths = " ".join(["500"] * 95)
        objects = {
            1: b"<< /Type /Pages /Kids [2 0 R] /Count 1 >>",
            2: b"<< /Type /Page /Parent 1 0 R /MediaBox [0 0 504 720] /Contents 3 0 R "
               b"/Resources << /Font << /F1 4 0 R /F2 6 0 R >> >> >>",
            4: f"<< /Type /Font /Subtype /TrueType /BaseFont /Arial /FirstChar 32 "
               f"/LastChar 126 /Widths [{widths}] >>".encode(),
            5: b"<< /Type /Catalog /Pages 1 0 R >>",
            6: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
        out = b"%PDF-1.4\n"
        for num in sorted(objects):
            out += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"
        stream = body.encode()
        out += b"3 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + \
            b"\nendstream\nendobj\ntrailer\n<< /Root 5 0 R >>\n%%EOF\n"
        doc = pdfread.Document(out)
        read = pdfread.read_page(doc, doc.pages()[0])
        self.assertEqual(read["ends"][:2], [125.0, 145.0])
        # "Next" ends at 220 and "word" starts at 221: a tenth of the type
        # apart, one word; a font with no widths keeps its runs apart.
        self.assertEqual(pdfread.page_text(read).split("\n"),
                         ["Registered Democrat Nextword", "Plain font"])

    def test_an_encrypted_file_is_not_read(self):
        with self.assertRaises(pdfread.PDFError):
            pdfread.Document(pdf(["Governor"], [], encrypt=True))
        _raw, _s, _w, why = guide_photos.ak_statement(pdf(["Governor"], [], encrypt=True),
                                                      "governor", "Taylor, Treg")
        self.assertIn("encrypted", why)

    def test_objects_in_an_object_stream(self):
        import zlib
        pages = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >> "
        header = b"1 0 2 " + str(len(pages)).encode() + b" "
        inner = header + pages + b"<< /Type /Catalog /Pages 1 0 R >>"
        first = len(header)
        packed = zlib.compress(inner)
        data = (b"%PDF-1.5\n9 0 obj\n<< /Type /ObjStm /N 2 /First " + str(first).encode()
                + b" /Filter /FlateDecode /Length " + str(len(packed)).encode() + b" >>\nstream\n"
                + packed + b"\nendstream\nendobj\n3 0 obj\n<< /Type /Page /Contents 4 0 R >>\n"
                b"endobj\n4 0 obj\n<< /Length 30 >>\nstream\nBT 1 0 0 1 9 9 Tm (Hi) Tj ET   \n"
                b"endstream\nendobj\n%%EOF")
        doc = pdfread.Document(data)
        self.assertEqual(doc.catalog().get("Type"), "Catalog")
        pages = doc.pages()
        self.assertEqual(len(pages), 1)
        self.assertEqual(pdfread.read_page(doc, pages[0])["text"], [(9.0, 9.0, "Hi", 1.0)])


class Root(unittest.TestCase):
    """A scratch site with a manifest and photos/."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="kyc-guide-")
        os.makedirs(os.path.join(self.root, photocopies.PHOTOS_DIR))
        os.makedirs(os.path.join(self.root, "candidate_profiles_site", "data"), exist_ok=True)
        photocopies.save({"originals": {}, "hosted": {}}, self.root)
        self.addCleanup(shutil.rmtree, self.root, True)

    def wa_pages(self, photos):
        """The guide for WA-4 and WA-6, with *photos* ``{ballot: bytes}``."""
        index = wa_index([("186950", 4, [("1601894", "Amanda McKinney", "(Prefers Republican Party)"),
                                         ("1601895", "John Duresky", "(Prefers Democratic Party)")]),
                          ("186952", 6, [("1601899", "Teresa Fox", "(Prefers Republican Party)")])])
        return {
            guide_photos.WA_INDEX: index,
            guide_photos.WA_RECORD.format(race="186950"): wa_record("186950", [
                ("1601894", "Amanda McKinney", "(Prefers Republican Party)", photos.get("1601894")),
                ("1601895", "John Duresky", "(Prefers Democratic Party)", photos.get("1601895"))]),
            guide_photos.WA_RECORD.format(race="186952"): wa_record("186952", [
                ("1601899", "Teresa Fox", "(Prefers Republican Party)", photos.get("1601899"))]),
        }

    def people(self):
        return [profile("FEC_H6WA04190", "John Duresky", "DURESKY, JOHN"),
                profile("FEC_H6WA04216", "Amanda McKinney", "MCKINNEY, AMANDA",
                        photos=["https://amanda.example/a.jpg"]),
                profile("FEC_H6WA06286", "Teresa Fox", "FOX, TERESA", district=6)]

    def fetch(self, pages, people=None):
        return guide_photos.fetch(self.root, profiles=people or self.people(), stategov={},
                                  getter=Getter(pages), log=lambda *a: None)


class TestWashington(Root):
    def test_the_guides_statement_joins_and_the_bytes_are_hosted_unmodified(self):
        duresky = jpeg(seed=b"duresky", pad=5000)
        cache, problems = self.fetch(self.wa_pages({"1601895": duresky, "1601894": jpeg(seed=b"m")}))
        # McKinney has a photograph by another route: the guide's is not taken.
        self.assertEqual(sorted(cache["photos"]), ["person:FEC_H6WA04190"])
        rec = cache["photos"]["person:FEC_H6WA04190"]
        name = hashlib.sha256(duresky).hexdigest()[:20] + ".jpg"
        self.assertEqual(rec["photo"], "photos/" + name)
        self.assertEqual(rec["page"], "https://voter.votewa.gov/genericvoterguide.aspx?e=899&c=99"
                                      "#/candidates/186950/1601895")
        self.assertEqual(rec["from"], guide_photos.WA_RECORD.format(race="186950"))
        self.assertIn("'John Duresky' (Prefers Democratic Party), U.S. Representative, "
                      "Congressional District 4", rec["evidence"])
        self.assertEqual(rec["by"], "from the Washington Secretary of State's voters' guide")
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, name), "rb") as handle:
            self.assertEqual(handle.read(), duresky)
        entry = photocopies.load(self.root)["hosted"][name]
        self.assertEqual(entry["method"], "unmodified")
        self.assertEqual((entry["sha256"], entry["bytes"], entry["width"], entry["height"]),
                         (hashlib.sha256(duresky).hexdigest(), len(duresky), 300, 400))
        self.assertEqual(entry["for"], ["person:FEC_H6WA04190"])
        self.assertEqual(entry["page"], rec["page"])
        self.assertEqual(entry["from"], rec["from"])
        self.assertTrue(entry["read"])
        self.assertEqual(guide_photos.problems(cache, photocopies.load(self.root)), [])
        self.assertEqual([p for p in photocopies.problems(photocopies.load(self.root), self.root)
                          if p[0] == "error"], [])

    def test_a_landscape_frame_and_a_refused_page_give_none(self):
        wide = jpeg(width=900, height=400, seed=b"wide")
        cache, problems = self.fetch(self.wa_pages({"1601895": wide}))
        self.assertEqual(cache["photos"], {})
        self.assertTrue(any("head-and-shoulders" in p for p in problems), problems)
        page = "https://voter.votewa.gov/genericvoterguide.aspx?e=899&c=99#/candidates/186950/1601895"
        with mock.patch.dict("kyc.overrides.NOT_A_PORTRAIT",
                             {page: ("2026-10-25", "a group photograph")}):
            cache, problems = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
        self.assertEqual(cache["photos"], {})

    def test_a_refusal_is_recorded_and_outlives_a_read_that_concludes_nothing(self):
        """What a person refused of a guide is recorded for validate's
        staleness check, by race; a guide that cannot be read keeps it
        (rule 8), and a read that reaches the race lets it go."""
        from kyc.photos import refused_urls
        page = "https://voter.votewa.gov/genericvoterguide.aspx?e=899&c=99#/candidates/186950/1601895"
        table = {page: ("2026-10-25", "a group photograph")}
        with mock.patch.dict("kyc.overrides.NOT_A_PORTRAIT", table):
            cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
            self.assertEqual(refused_urls(cache.get("notPortraits")), {page})
            guide_photos.save_cache(cache, self.root)
            again, _ = self.fetch({})
            self.assertEqual(refused_urls(again.get("notPortraits")), {page})
            guide_photos.save_cache(again, self.root)
        whole, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
        self.assertNotIn("notPortraits", whole)

    def test_a_statement_for_another_race_is_refused(self):
        pages = self.wa_pages({"1601895": jpeg(seed=b"d")})
        pages[guide_photos.WA_RECORD.format(race="186950")] = wa_record("186952", [
            ("1601895", "John Duresky", "(Prefers Democratic Party)", jpeg(seed=b"d"))])
        cache, problems = self.fetch(pages)
        self.assertEqual(cache["photos"], {})

    def test_a_guide_that_cannot_be_read_keeps_its_photographs(self):
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d"), "1601899": jpeg(seed=b"f")}))
        guide_photos.save_cache(cache, self.root)
        again, problems = self.fetch({})
        self.assertEqual(sorted(again["photos"]), sorted(cache["photos"]))
        self.assertTrue(any("kept" in p for p in problems))
        for rec in again["photos"].values():
            self.assertTrue(os.path.exists(os.path.join(self.root, "candidate_profiles_site",
                                                        rec["photo"])))

    def test_one_who_gains_another_photograph_loses_the_hosted_file(self):
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
        guide_photos.save_cache(cache, self.root)
        name = cache["photos"]["person:FEC_H6WA04190"]["photo"]
        people = self.people()
        people[0]["photos"] = ["https://duresky.example/d.jpg"]
        again, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}), people)
        self.assertEqual(again["photos"], {})
        self.assertEqual(photocopies.load(self.root)["hosted"], {})
        self.assertFalse(os.path.exists(os.path.join(self.root, "candidate_profiles_site", name)))


class TestTheManifest(Root):
    """The hosted files are checked both ways: every file under photos/ is
    listed, every listed file is on disk and is the bytes and pixels the
    manifest gives, how it was taken and for whom."""

    def host(self, data=None, **changes):
        data = data or jpeg(seed=b"x")
        sha = hashlib.sha256(data).hexdigest()
        name = sha[:20] + ".jpg"
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, name), "wb") as handle:
            handle.write(data)
        entry = {"method": "unmodified", "page": "https://voter.votewa.gov/g#/candidates/1/2",
                 "from": "https://voter.votewa.gov/elections/candidate.ashx?e=899&r=1",
                 "sha256": sha, "bytes": len(data), "width": 300, "height": 400,
                 "type": "image/jpeg", "read": "2026-10-25", "for": ["person:A"],
                 "by": "Washington Secretary of State, voters' guide"}
        entry.update(changes)
        manifest = photocopies.load(self.root)
        manifest["hosted"][name] = entry
        photocopies.save(manifest, self.root)
        return name

    def codes(self, shown=None):
        return sorted({c for level, c, _m in photocopies.problems(
            photocopies.load(self.root), self.root, shown) if level == "error"})

    def test_a_sound_entry_passes(self):
        self.host()
        self.assertEqual(self.codes(), [])

    def test_a_file_not_listed_fails(self):
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, "0" * 20 + ".jpg"), "wb") as h:
            h.write(jpeg())
        self.assertEqual(self.codes(), ["photo-copy-unlisted"])

    def test_a_listed_file_that_is_missing_or_not_itself_fails(self):
        name = self.host()
        os.remove(os.path.join(self.root, photocopies.PHOTOS_DIR, name))
        self.assertEqual(self.codes(), ["photo-hosted-missing"])
        name = self.host(jpeg(seed=b"y"), bytes=99)
        self.assertIn("photo-hosted-bytes", self.codes())
        name = self.host(jpeg(seed=b"z"), width=301)
        self.assertIn("photo-hosted-shape", self.codes())
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, name), "ab") as handle:
            handle.write(b"tampered")
        self.assertIn("photo-hosted-hash", self.codes())

    def test_it_says_how_it_was_taken_from_where_and_for_whom(self):
        self.host(method="resized")
        self.assertEqual(self.codes(), ["photo-hosted-method"])
        self.setUp()
        self.host(page="", **{"for": []})
        self.assertEqual(self.codes(), ["photo-hosted-unrecorded"])

    def test_it_is_shown_only_for_whom_it_was_hosted_and_credited(self):
        name = self.host()
        shown = photocopies.Shown()
        shown.add("photos/" + name, "person", "person:A", {}, True)
        self.assertEqual(self.codes(shown), [])
        shown.add("photos/" + name, "person", "person:B", {}, True)
        self.assertEqual(self.codes(shown), ["photo-hosted-not-theirs"])
        shown = photocopies.Shown()
        shown.add("photos/" + name, "person", "person:A", {}, False)
        self.assertEqual(self.codes(shown), ["photo-hosted-uncredited"])
        shown = photocopies.Shown()
        shown.add("photos/" + "f" * 20 + ".jpg", "person", "person:A", {}, True)
        self.assertEqual(self.codes(shown), ["photo-hosted-unlisted"])

    def test_a_heavy_one_is_shown_as_a_copy_made_of_the_very_file(self):
        heavy = jpeg(width=2254, height=2705, seed=b"heavy", pad=400_000)
        name = self.host(heavy, width=2254, height=2705)
        shown = photocopies.Shown()
        shown.add("photos/" + name, "person", "person:A", {}, True)
        made = []

        def maker(jobs, root, deadline=None):
            results = {}
            for job in jobs:
                made.append(job)
                with open(job["in"], "rb") as handle:
                    self.assertEqual(handle.read(), heavy)
                out = b"\xff\xd8\xff\xe0" + hashlib.sha256(job["in"].encode()).digest() * 50
                with open(job["out"], "wb") as handle:
                    handle.write(out)
                results[job["id"]] = {"ok": True, "width": 540, "height": 648,
                                      "srcWidth": 2254, "srcHeight": 2705}
            return {"chrome": "HeadlessChrome/156.0", "quality": photocopies.QUALITY,
                    "results": results}

        report = photocopies.copy_hosted(self.root, shown, maker=maker, log=lambda *a: None)
        self.assertEqual(report["copied"], 1)
        copy = photocopies.load(self.root)["hosted"][name]["copy"]
        self.assertEqual(copy["for"], ["person:A"])
        record = {"photos": ["photos/" + name], "photoCredit": {"by": "x"}}
        self.assertTrue(photocopies.attach(record, "photos/" + name, photocopies.load(self.root),
                                           "person", key="person:A"))
        self.assertEqual(record["photoCopy"]["of"], "photos/" + name)
        self.assertEqual(record["photoCopy"]["ofBytes"], len(heavy))
        self.assertFalse(photocopies.attach({}, "photos/" + name, photocopies.load(self.root),
                                            "person", key="person:B"))
        # Never made again while the file is the same.
        photocopies.copy_hosted(self.root, shown, maker=maker, log=lambda *a: None)
        self.assertEqual(len(made), 1)


class TestThePage(Root):
    def test_shown_only_where_no_other_route_gives_one_and_while_the_name_holds(self):
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
        guide_photos.save_cache(cache, self.root)
        manifest = photocopies.load(self.root)
        people = self.people()
        people[0]["photos"] = ["placeholder"]
        self.assertEqual(guide_photos.apply_people(people, cache, manifest), 1)
        rec = cache["photos"]["person:FEC_H6WA04190"]
        self.assertEqual(people[0]["photos"][0], rec["photo"])
        self.assertEqual(people[0]["photoSource"], guide_photos.ROUTE)
        self.assertEqual(people[0]["photoCredit"], {"by": rec["by"], "page": rec["page"]})
        # Someone else under the same id, or another photograph first: none.
        other = profile("FEC_H6WA04190", "Jon Doresky", "DORESKY, JON")
        self.assertEqual(guide_photos.apply_people([other], cache, manifest), 0)
        pictured = profile("FEC_H6WA04190", "John Duresky", photos=["https://x.example/a.jpg"])
        self.assertEqual(guide_photos.apply_people([pictured], cache, manifest), 0)
        moved = profile("FEC_H6WA04190", "John Duresky", district=5)
        self.assertEqual(guide_photos.apply_people([moved], cache, manifest), 0)
        # A person's list withdraws it, whenever it was read.
        with mock.patch.dict("kyc.overrides.NOT_A_PORTRAIT",
                             {rec["page"]: ("2026-10-25", "not a likeness")}):
            fresh = [profile("FEC_H6WA04190", "John Duresky", "DURESKY, JOHN")]
            self.assertEqual(guide_photos.apply_people(fresh, cache, manifest), 0)
        # The manifest must hold the file for them.
        manifest["hosted"][rec["photo"][7:]]["for"] = ["person:B"]
        fresh = [profile("FEC_H6WA04190", "John Duresky", "DURESKY, JOHN")]
        self.assertEqual(guide_photos.apply_people(fresh, cache, manifest), 0)

    def test_a_statewide_candidate_no_other_route_pictures(self):
        data = jpeg(components=1, seed=b"t")
        name = hashlib.sha256(data).hexdigest()[:20] + ".jpg"
        key = "candidate:AK:governor:Treg Taylor"
        rec = {"state": "AK", "race": "", "office": "governor", "name": "Taylor, Treg",
               "page": "https://elections.alaska.gov/doc/oep/2026/TAYLOR.pdf",
               "from": "https://elections.alaska.gov/doc/oep/2026/TAYLOR.pdf",
               "evidence": "the statement's heading reads 'Governor' and 'Treg Taylor, ...'",
               "read": "2026-10-25", "photo": "photos/" + name,
               "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "width": 300,
               "height": 400, "type": "image/jpeg", "for": key,
               "by": "Alaska Division of Elections, Official Election Pamphlet"}
        guides = {"photos": {key: rec}}
        manifest = {"hosted": {name: {"sha256": rec["sha256"], "for": [key]}}}
        rows = [{"name": "Treg Taylor", "party": "Registered Republican"},
                {"name": "Dave Bronson", "party": "Registered Republican"}]
        listed = {"candidates": [{"name": "Taylor, Treg"}, {"name": "Bronson, Dave"}]}
        statewide_photos.attach("AK", "governor", rows, listed, {}, None, {"photos": {}},
                                guides, manifest)
        self.assertEqual(rows[0]["photo"], "photos/" + name)
        self.assertEqual(rows[0]["photoCredit"]["by"],
                         "from the Alaska Division of Elections' Official Election Pamphlet")
        self.assertNotIn("photo", rows[1])
        # The list no longer prints that name for the office: not shown.
        rows = [{"name": "Treg Taylor Jr."}]
        statewide_photos.attach("AK", "governor", rows, {"candidates": [{"name": "Taylor, Treg Jr."}]},
                                {}, None, {"photos": {}}, guides, manifest)
        self.assertNotIn("photo", rows[0])


JPX = os.path.join(os.path.dirname(__file__), "fixtures", "jpx_dropbox_mask.jp2")


def oregon_book(columns, colour="DeviceGray"):
    """A pamphlet page: each column ``(x, office, name lines, party)`` with a
    JPEG 2000 photograph at its head, the name in 20pt type beside it, the
    party in 10pt and the occupation in 8pt, as the State Voters' Pamphlet
    sets them."""
    with open(JPX, "rb") as handle:
        jpx_bytes = handle.read()
    objects, draws, names = {}, "", []
    n = 10
    for i, (x, office, lines, party) in enumerate(columns):
        objects[n] = (f"<< /Type /XObject /Subtype /Image /Width 456 /Height 460 "
                      f"/ColorSpace /{colour} /BitsPerComponent 8 /Filter /JPXDecode "
                      f"/Length {len(jpx_bytes)} >>").encode(), jpx_bytes
        names.append(f"/Im{i} {n} 0 R")
        draws += f"q 108 0 0 126 {x} 581.2 cm /Im{i} Do Q\n"
        draws += f"BT /F1 10 Tf 1 0 0 1 {x} 716.8 Tm ({office}) Tj ET\n"
        y = 693.4
        for line in lines:
            draws += f"BT /F1 20 Tf 1 0 0 1 {x + 118} {y} Tm ({line} ) Tj ET\n"
            y -= 20
        draws += f"BT /F1 10 Tf 1 0 0 1 {x + 118} 657.8 Tm ({party}) Tj ET\n"
        draws += f"BT /F1 8 Tf 1 0 0 1 {x + 118} 632.2 Tm (Occupation:) Tj ET\n"
        n += 1
    body = draws.encode()
    objects[3] = (f"<< /Length {len(body)} >>").encode(), body
    objects[2] = (f"<< /Type /Page /Parent 1 0 R /MediaBox [0 0 540 774] /Contents 3 0 R "
                  f"/Resources << /Font << /F1 4 0 R >> /XObject << {' '.join(names)} >> >> >>"
                  ).encode(), None
    objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", None
    objects[1] = b"<< /Type /Pages /Kids [2 0 R] /Count 1 >>", None
    objects[5] = b"<< /Type /Catalog /Pages 1 0 R >>", None
    out = b"%PDF-1.6\n"
    for num in sorted(objects):
        head, stream = objects[num]
        out += f"{num} 0 obj\n".encode() + head
        if stream is not None:
            out += b"\nstream\n" + stream + b"\nendstream"
        out += b"\nendobj\n"
    return out + b"trailer\n<< /Root 5 0 R >>\n%%EOF\n"


OR_INDEX_PAGE = (
    '<ul><li><a href="/elections/Voters-Pamphlet/Documents/VP_G26-Book12_web.pdf">Washington</a>'
    '<a href="/elections/Voters-Pamphlet/Documents/VP_G26-Book9_web.pdf">Polk</a>'
    '<a href="/elections/Voters-Pamphlet/Documents/VP_G26-Book12_web.pdf">Columbia</a>'
    '<a href="/elections/other.pdf">a form</a></ul>').encode()
BOOK12 = "https://sos.oregon.gov/elections/Voters-Pamphlet/Documents/VP_G26-Book12_web.pdf"
BOOK9 = "https://sos.oregon.gov/elections/Voters-Pamphlet/Documents/VP_G26-Book9_web.pdf"


class TestOregon(Root):
    def kahl(self):
        return profile("FEC_H6OR01308", "Barbara J Kahl", "KAHL, BARBARA J DR DVM", state="OR",
                       district=1)

    def pages(self, book=None):
        return {guide_photos.OR_INDEX: OR_INDEX_PAGE,
                BOOK12: book or oregon_book([
                    (22.5, "US Representative, 1st District", ["Barbara J", "Kahl"], "Republican"),
                    (274.7, "US Representative, 1st District", ["Suzanne", "Bonamici"],
                     "Democrat")])}

    def test_the_books_in_the_pamphlets_order_each_once(self):
        books = guide_photos.or_books(OR_INDEX_PAGE.decode())
        self.assertEqual(books, [(BOOK12, ["Washington", "Columbia"]), (BOOK9, ["Polk"])])

    def test_the_name_beside_the_photograph_under_the_office(self):
        doc = pdfread.Document(self.pages()[BOOK12])
        columns = guide_photos.or_columns(doc)
        self.assertEqual([(c["office"], c["name"], c["party"]) for c in columns],
                         [("US Representative, 1st District", "Barbara J Kahl", "Republican"),
                          ("US Representative, 1st District", "Suzanne Bonamici", "Democrat")])
        self.assertEqual(guide_photos.or_target(columns[0]["office"]), "H-OR-01-2026")
        self.assertEqual(guide_photos.or_target("Governor"), "OR|governor")

    def test_a_photograph_decoded_losslessly_and_hosted_as_a_png(self):
        from kyc import jpx
        getter = Getter(self.pages())
        photos, problems, unread = guide_photos.read_oregon({"H-OR-01-2026": [self.kahl()]},
                                                            getter=getter)
        rec = photos["person:FEC_H6OR01308"]
        self.assertEqual(rec["method"], "decoded")
        with open(JPX, "rb") as handle:
            source = handle.read()
        self.assertEqual(rec["sourceSha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(rec["type"], "image/png")
        self.assertTrue(rec["photo"].endswith(".png"))
        self.assertEqual(jpx.png_pixels(rec["_data"]), jpx.decode(source))
        self.assertEqual(rec["page"], BOOK12 + "#page=1")
        self.assertIn("heads a column 'US Representative, 1st District' and prints "
                      "'Barbara J Kahl', 'Republican'", rec["evidence"])
        self.assertIn("Washington, Columbia", rec["evidence"])
        # The other books are not read once every race wanted is found.
        self.assertNotIn(BOOK9, getter.asked)

    def test_the_manifest_lists_a_decoded_file_with_its_source(self):
        people = [self.kahl()]
        cache, problems = guide_photos.fetch(self.root, profiles=people, stategov={},
                                             getter=Getter(self.pages()), log=lambda *a: None)
        rec = cache["photos"]["person:FEC_H6OR01308"]
        entry = photocopies.load(self.root)["hosted"][rec["photo"][len("photos/"):]]
        self.assertEqual((entry["method"], entry["sourceSha256"], entry["decoder"]),
                         ("decoded", rec["sourceSha256"], guide_photos.DECODER))
        codes = [c for level, c, _m in photocopies.problems(photocopies.load(self.root), self.root)
                 if level == "error"]
        self.assertEqual(codes, [])
        manifest = photocopies.load(self.root)
        del manifest["hosted"][rec["photo"][len("photos/"):]]["sourceSha256"]
        photocopies.save(manifest, self.root)
        codes = [c for level, c, _m in photocopies.problems(photocopies.load(self.root), self.root)
                 if level == "error"]
        self.assertEqual(codes, ["photo-hosted-unrecorded"])

    def test_a_short_form_needs_its_evidenced_entry(self):
        russ = profile("FEC_H2OR01240", "David Russ", "RUSS, DAVID HONORABLE",
                       state="OR", district=6)
        pages = lambda given: {guide_photos.OR_INDEX: OR_INDEX_PAGE, BOOK12: oregon_book(  # noqa: E731
            [(274.7, "US Representative, 6th District", [given, "Russ"], "Republican")])}
        # "Honorable" is an honorific, not a name: the pamphlet's "David
        # Russ" is the filing's words, and joins without an entry.
        with mock.patch("kyc.overrides.GUIDE_NAME_FORMS", {}):
            photos, problems, _ = guide_photos.read_oregon({"H-OR-06-2026": [russ]},
                                                           getter=Getter(pages("David")))
        self.assertEqual(sorted(photos), ["person:FEC_H2OR01240"])
        # A short form the filing does not write needs its evidenced entry.
        with mock.patch("kyc.overrides.GUIDE_NAME_FORMS", {}):
            photos, problems, _ = guide_photos.read_oregon({"H-OR-06-2026": [russ]},
                                                           getter=Getter(pages("Dave")))
        self.assertEqual(photos, {})
        self.assertTrue(any("'Dave Russ' shares a surname" in p for p in problems), problems)
        forms = {("OR", "Dave Russ"): ("person:FEC_H2OR01240", "a test's evidence")}
        with mock.patch("kyc.overrides.GUIDE_NAME_FORMS", forms):
            photos, problems, _ = guide_photos.read_oregon({"H-OR-06-2026": [russ]},
                                                           getter=Getter(pages("Dave")))
        self.assertEqual(sorted(photos), ["person:FEC_H2OR01240"])

    def test_a_colour_or_unreadable_image_gives_none(self):
        book = oregon_book([(22.5, "US Representative, 1st District", ["Barbara J", "Kahl"],
                             "Republican")], colour="DeviceRGB")
        photos, problems, _ = guide_photos.read_oregon({"H-OR-01-2026": [self.kahl()]},
                                                       getter=Getter(self.pages(book)))
        self.assertEqual(photos, {})
        self.assertTrue(any("not grey" in p for p in problems), problems)

    def test_two_images_beside_one_name_give_none(self):
        book = oregon_book([(22.5, "US Representative, 1st District", ["Barbara J", "Kahl"],
                             "Republican"),
                            (40.5, "US Representative, 1st District", ["Barbara J", "Kahl"],
                             "Republican")])
        doc = pdfread.Document(book)
        self.assertEqual(guide_photos.or_columns(doc), [])

    def test_an_unreadable_pamphlet_concludes_nothing(self):
        photos, problems, unread = guide_photos.read_oregon({"H-OR-01-2026": [self.kahl()]},
                                                            getter=Getter({}))
        self.assertEqual((photos, unread), ({}, {"H-OR-01-2026"}))


class TestTheRefreshOrder(Root):
    """The refresh runs ``guidephotos``, then ``photocopies``, then the
    build. On 2026-10-26 the runner's zlib wrote Oregon's decoded PNGs in
    other bytes than the zlib-ng that made the committed files, so each was
    hosted under a new name and the old let go; ``photocopies`` then read
    the last build's people files, found four nominees "showing" files the
    manifest no longer listed (photo-hosted-unlisted), and failed."""

    KEY = "person:FEC_H6OR01308"
    kahl = TestOregon.kahl
    pages = TestOregon.pages

    def fetch_or(self, people):
        cache, problems = guide_photos.fetch(self.root, profiles=people, stategov={},
                                             getter=Getter(self.pages()), log=lambda *a: None)
        guide_photos.save_cache(cache, self.root)
        return cache, problems

    def build(self):
        """The people as a build shows them, written where the build writes
        them (``photocopies.read_people`` reads them back)."""
        from kyc import emit
        people = [self.kahl()]
        guide_photos.apply_people(people, guide_photos.load_cache(self.root),
                                  photocopies.load(self.root))
        directory = os.path.join(self.root, emit.PEOPLE_DIR)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "OR.js"), "w", encoding="utf-8", newline="") as handle:
            handle.write("window.kycPeopleFile = " + json.dumps({"people": people}) + ";\n")
        return people

    def other_zlib(self):
        """A zlib whose compressed bytes differ for the same pixels."""
        import zlib
        real = zlib.compress
        return mock.patch.object(zlib, "compress", lambda data, level=-1: real(data, 1))

    def test_another_zlibs_bytes_are_another_file_only_where_the_pixels_differ(self):
        from kyc import jpx
        self.fetch_or([self.kahl()])
        people = self.build()
        hosted = people[0]["photos"][0]
        self.assertTrue(hosted.startswith("photos/"))
        with self.other_zlib():
            fresh = guide_photos.read_oregon({"H-OR-01-2026": [self.kahl()]},
                                             getter=Getter(self.pages()))[0][self.KEY]
            self.assertNotEqual(fresh["photo"], hosted)  # the test's premise
            cache, problems = self.fetch_or(photocopies.read_people(self.root))
        self.assertEqual(cache["photos"][self.KEY]["photo"], hosted)
        self.assertFalse([p for p in problems if "photograph changed" in p], problems)
        name = hosted[len("photos/"):]
        self.assertEqual(photocopies.load(self.root)["hosted"][name]["for"], [self.KEY])
        with open(os.path.join(self.root, photocopies.PHOTOS_DIR, name), "rb") as handle:
            self.assertEqual(jpx.png_pixels(handle.read()), jpx.png_pixels(fresh["_data"]))
        self.assertEqual(os.listdir(os.path.join(self.root, photocopies.PHOTOS_DIR)), [name])

    def test_copies_after_the_guides_see_what_the_next_build_shows(self):
        self.fetch_or([self.kahl()])
        old = self.build()[0]["photos"][0]
        # The guide's photograph is another file now (a new photograph, or
        # bytes no earlier file holds): the old one is let go at once.
        with self.other_zlib(), mock.patch.object(guide_photos, "same_decode", return_value=None):
            cache, _ = self.fetch_or(photocopies.read_people(self.root))
        new = cache["photos"][self.KEY]["photo"]
        self.assertNotEqual(new, old)
        self.assertNotIn(old[len("photos/"):], photocopies.load(self.root)["hosted"])
        # photocopies reads the last build's people files, which still show
        # the old file, and judges them as the next build will show them.
        with mock.patch("kyc.legislature.build", return_value={}), \
                mock.patch("kyc.federal_build.build", return_value=({}, [])), \
                mock.patch("kyc.stategov.build", return_value=({}, [])):
            shown = photocopies.gather(self.root)
        self.assertEqual(sorted(shown.hosted), [new])
        self.assertEqual(sorted(shown.hosted[new]["records"]), [self.KEY])
        issues = photocopies.problems(photocopies.load(self.root), self.root, shown)
        self.assertEqual([i for i in issues if i[0] == "error"], [])
        self.assertFalse([i for i in issues if i[1] == "photo-hosted-orphan"], issues)
        # And the people file as the build will write it shows the new file,
        # credited, the way gather took it.
        self.assertEqual(self.build()[0]["photos"][0], new)

    def test_one_the_guide_no_longer_pictures_is_shown_none(self):
        self.fetch_or([self.kahl()])
        self.build()
        guide_photos.save_cache({"photos": {}}, self.root)
        people = photocopies.read_people(self.root)
        self.assertEqual(guide_photos.reapply_people(people, guide_photos.load_cache(self.root),
                                                     photocopies.load(self.root)), 0)
        self.assertEqual(people[0]["photos"], ["placeholder"])
        self.assertEqual(people[0]["photo_url"], "placeholder")
        for field in ("photoSource", "photoCredit", "photoCopy"):
            self.assertNotIn(field, people[0])


class TestTheCommittedCache(unittest.TestCase):
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def test_every_record_is_sound_and_its_file_hosted_for_them(self):
        cache = guide_photos.load_cache(self.ROOT)
        manifest = photocopies.load(self.ROOT)
        self.assertEqual(guide_photos.problems(cache, manifest), [])
        for key, rec in (cache.get("photos") or {}).items():
            entry = manifest["hosted"][rec["photo"][len("photos/"):]]
            self.assertIn(key, entry["for"])
            self.assertTrue(rec["page"].startswith(("https://voter.votewa.gov/",
                                                    "https://elections.alaska.gov/",
                                                    "https://sos.oregon.gov/")), key)

    def test_every_decoded_photograph_names_its_source_and_every_other_is_unmodified(self):
        cache = guide_photos.load_cache(self.ROOT)
        manifest = photocopies.load(self.ROOT)
        for key, rec in (cache.get("photos") or {}).items():
            entry = manifest["hosted"][rec["photo"][len("photos/"):]]
            if rec["state"] == "OR":
                self.assertEqual(entry["method"], "decoded", key)
                self.assertEqual(entry["sourceSha256"], rec["sourceSha256"], key)
                self.assertTrue(rec["page"].startswith(
                    "https://sos.oregon.gov/elections/Voters-Pamphlet/Documents/"), key)
            else:
                self.assertEqual(entry["method"], "unmodified", key)


    def test_a_pamphlet_photograph_hosted_is_the_decode_of_its_codestream(self):
        """One photograph's own codestream (David Russ's, Book 14 page 36,
        tests/fixtures/jpx_or_pamphlet_russ.jp2) decodes to exactly the
        pixels of the PNG hosted for him: what the hash in the manifest says
        is checked here, offline, not only once against PDFium."""
        from kyc import jpx
        with open(RUSS_JPX, "rb") as handle:
            source = handle.read()
        cache = guide_photos.load_cache(self.ROOT)
        rec = cache["photos"]["person:FEC_H2OR01240"]
        self.assertEqual(rec["sourceSha256"], hashlib.sha256(source).hexdigest())
        entry = photocopies.load(self.ROOT)["hosted"][rec["photo"][len("photos/"):]]
        self.assertEqual(entry["sourceSha256"], rec["sourceSha256"])
        with open(os.path.join(self.ROOT, "candidate_profiles_site", rec["photo"]), "rb") as handle:
            hosted = handle.read()
        self.assertEqual(hashlib.sha256(hosted).hexdigest(), rec["sha256"])
        self.assertEqual(jpx.png_pixels(hosted), jpx.decode(source))


RUSS_JPX = os.path.join(os.path.dirname(__file__), "fixtures", "jpx_or_pamphlet_russ.jp2")


class TestAGuideOfAnotherShape(Root):
    """A guide that answers but whose page has changed its layout concludes
    nothing (rules 8 and 36): the last photographs are kept, and their files
    stay, rather than thirteen people going back to the silhouette (the
    review of PR #138)."""

    def kept(self, pages):
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d"),
                                             "1601899": jpeg(seed=b"f")}))
        guide_photos.save_cache(cache, self.root)
        self.assertEqual(len(cache["photos"]), 2)
        again, problems = self.fetch(pages)
        self.assertEqual(sorted(again["photos"]), sorted(cache["photos"]))
        self.assertTrue(any("kept" in p for p in problems), problems)
        for rec in again["photos"].values():
            self.assertTrue(os.path.exists(os.path.join(self.root, "candidate_profiles_site",
                                                        rec["photo"])))
        self.assertEqual(sorted(photocopies.load(self.root)["hosted"]),
                         sorted(r["photo"][len("photos/"):] for r in cache["photos"].values()))
        return problems

    def test_washingtons_index_with_no_races(self):
        pages = self.wa_pages({})
        pages[guide_photos.WA_INDEX] = json.dumps({"Categories": []}).encode()
        problems = self.kept(pages)
        self.assertTrue(any("index has no race for H-WA-04-2026" in p for p in problems), problems)

    def test_washingtons_index_with_no_names(self):
        pages = self.wa_pages({})
        pages[guide_photos.WA_INDEX] = wa_index([("186950", 4, [("1601895", None, "")]),
                                                 ("186952", 6, [])])
        self.kept(pages)

    def test_washingtons_statements_with_no_photograph_field(self):
        pages = self.wa_pages({})
        for race, people in (("186950", [("1601894", "Amanda McKinney"),
                                         ("1601895", "John Duresky")]),
                             ("186952", [("1601899", "Teresa Fox")])):
            pages[guide_photos.WA_RECORD.format(race=race)] = json.dumps(
                [{"statement": {"RaceID": race, "BallotID": b, "BallotName": n,
                                "Image": "x"}} for b, n in people]).encode()
        self.kept(pages)

    def test_washingtons_empty_answer(self):
        pages = self.wa_pages({})
        for race in ("186950", "186952"):
            pages[guide_photos.WA_RECORD.format(race=race)] = b"[]"
        self.kept(pages)

    def test_a_guide_that_prints_no_photograph_for_them_is_a_conclusion(self):
        # The fields are there and Duresky's is empty: the guide no longer
        # prints one, and the hosted file goes (not rule 8's case).
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
        guide_photos.save_cache(cache, self.root)
        again, problems = self.fetch(self.wa_pages({}))
        self.assertEqual(again["photos"], {})
        self.assertTrue(any("prints no photograph for John Duresky" in p for p in problems))


class TestAlaskasListOfAnotherShape(unittest.TestCase):
    def setUp(self):
        self.alaska = TestAlaska()
        self.alaska.setUp()

    def read(self, page=None, **more):
        pages = self.alaska.pages(**more)
        if page is not None:
            pages[guide_photos.AK_LIST] = page.encode()
        wanted = {"S-AK-2026": [self.alaska.jr],
                  "AK|governor": [{"key": "candidate:AK:governor:Treg Taylor",
                                   "name": "Taylor, Treg"}]}
        return guide_photos.read_alaska(wanted, getter=Getter(pages))

    def test_a_list_whose_sections_are_not_found_concludes_nothing(self):
        page = AK_PAGE.replace("<h4>", "<h3>").replace("</h4>", "</h3>")
        photos, problems, unread = self.read(page)
        self.assertEqual(photos, {})
        self.assertEqual(unread, {"S-AK-2026", "AK|governor"})
        self.assertTrue(any("has no row for the office" in p for p in problems), problems)

    def test_a_list_that_links_no_statement_concludes_nothing(self):
        page = AK_PAGE.replace("Candidate Statement", "Candidate Letter") \
            .replace("Governor Statement", "Governor Letter")
        photos, problems, unread = self.read(page)
        self.assertEqual(photos, {})
        self.assertEqual(unread, {"S-AK-2026", "AK|governor"})
        self.assertTrue(any("links no statement" in p for p in problems), problems)

    def test_a_statement_this_reader_cannot_parse_concludes_nothing(self):
        photos, problems, unread = self.read(**{
            "https://elections.alaska.gov/doc/oep/2026/SULLIVAN,%20DANIEL%20J.%20JR%20_US%20Sen.pdf":
                b"%PDF-1.7\nnot a document"})
        self.assertNotIn("person:FEC_S6AK00326", photos)
        self.assertIn("person:FEC_S6AK00326", unread)
        self.assertIn("candidate:AK:governor:Treg Taylor", photos)

    def test_the_list_as_it_is_concludes(self):
        photos, _problems, unread = self.read()
        self.assertEqual(unread, set())
        self.assertEqual(sorted(photos), ["candidate:AK:governor:Treg Taylor",
                                          "person:FEC_S6AK00326"])


class TestARefusalNamesOnePhotograph(Root):
    """A person's NOT_A_PORTRAIT or PORTRAIT_LICENCE_DOUBTS entry is keyed on
    an address that names one candidate: never Washington's candidate.ashx
    (the whole race), an Oregon page (two columns) or its book (a county's
    every candidate)."""

    def test_oregon_on_the_hosted_file_alone(self):
        kahl = TestOregon.kahl(self)
        cache, _ = guide_photos.fetch(self.root, profiles=[kahl], stategov={},
                                      getter=Getter(TestOregon.pages(self)), log=lambda *a: None)
        key = "person:FEC_H6OR01308"
        rec = cache["photos"][key]
        manifest = photocopies.load(self.root)
        words = guide_photos.person_words(kahl)
        self.assertEqual(guide_photos.own_addresses("OR", rec["page"], rec["photo"]),
                         (rec["photo"],))
        self.assertIsNotNone(guide_photos.shown_record(cache, key, words, manifest=manifest))
        for shared in (rec["page"], rec["from"]):
            with mock.patch.dict("kyc.overrides.NOT_A_PORTRAIT",
                                 {shared: ("2026-10-25", "the other column's photograph")}):
                self.assertIsNotNone(
                    guide_photos.shown_record(cache, key, words, manifest=manifest), shared)
        with mock.patch.dict("kyc.overrides.NOT_A_PORTRAIT",
                             {rec["photo"]: ("2026-10-25", "not a likeness")}):
            self.assertIsNone(guide_photos.shown_record(cache, key, words, manifest=manifest))

    def test_washington_on_the_candidates_page_or_the_file_never_the_race(self):
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d"),
                                             "1601899": jpeg(seed=b"f")}))
        manifest = photocopies.load(self.root)
        key = "person:FEC_H6WA04190"
        rec = cache["photos"][key]
        words = guide_photos.person_words(self.people()[0])
        with mock.patch.dict("kyc.overrides.NOT_A_PORTRAIT",
                             {rec["from"]: ("2026-10-25", "the opponent's photograph")}):
            self.assertIsNotNone(guide_photos.shown_record(cache, key, words, manifest=manifest))
            fresh, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
            self.assertIn(key, fresh["photos"])
        with mock.patch.dict("kyc.overrides.PORTRAIT_LICENCE_DOUBTS",
                             {rec["photo"]: ("2026-10-25", "a studio's credit")}):
            self.assertIsNone(guide_photos.shown_record(cache, key, words, manifest=manifest))


class TestTheCredit(unittest.TestCase):
    def test_it_says_where_the_photograph_was_found_and_a_decoded_one_says_so(self):
        wa = {"state": "WA", "by": "Washington Secretary of State, voters' guide",
              "page": "https://voter.votewa.gov/g#/candidates/1/2", "method": "unmodified"}
        self.assertEqual(guide_photos.credit(wa), {
            "by": "from the Washington Secretary of State's voters' guide", "page": wa["page"]})
        ak = {"state": "AK", "by": "x", "page": "https://elections.alaska.gov/doc/oep/2026/A.pdf"}
        self.assertEqual(guide_photos.credit(ak)["by"],
                         "from the Alaska Division of Elections' Official Election Pamphlet")
        self.assertNotIn("converted", guide_photos.credit(ak))
        oregon = {"state": "OR", "by": "x", "method": "decoded",
                  "page": "https://sos.oregon.gov/elections/Voters-Pamphlet/Documents/B.pdf#page=3"}
        self.assertEqual(guide_photos.credit(oregon)["converted"],
                         "converted by this site to PNG from the pamphlet's JPEG 2000 image, "
                         "pixel for pixel")

    def test_the_committed_records_credit_the_guide_in_its_words(self):
        cache = guide_photos.load_cache(TestTheCommittedCache.ROOT)
        manifest = photocopies.load(TestTheCommittedCache.ROOT)
        for key, rec in cache["photos"].items():
            self.assertEqual(rec["by"], guide_photos.GUIDES[rec["state"]]["credit"], key)
            entry = manifest["hosted"][rec["photo"][len("photos/"):]]
            self.assertEqual(entry["by"], rec["by"], key)
            self.assertEqual("converted" in guide_photos.credit(rec),
                             entry["method"] == "decoded", key)


class TestTheBuildsCheck(Root):
    """validate's check of a profile shown with a guide's photograph reads
    the cache and manifest the build read, from the build's root, once."""

    def test_a_profile_shown_with_no_record_fails(self):
        from kyc import validate
        cache, _ = self.fetch(self.wa_pages({"1601895": jpeg(seed=b"d")}))
        manifest = photocopies.load(self.root)
        people = self.people()
        self.assertEqual(guide_photos.apply_people(people, cache, manifest), 1)
        shown = [p for p in people if p.get("photoSource") == guide_photos.ROUTE]
        self.assertEqual(validate.check_photo_evidence(shown, {}, {}, cache, manifest), [])
        # No cache given (or read from another folder): no record of it.
        issues = validate.check_photo_evidence(shown, {}, {}, None, manifest)
        self.assertEqual([i.code for i in issues], ["photo-unevidenced"])
        self.assertIn("no record of the guide's photograph", str(issues[0].detail or issues[0]))
        # A record of another file than the one shown.
        other = dict(shown[0], photos=["photos/ffffffffffffffffffff.jpg"])
        self.assertEqual([i.code for i in validate.check_photo_evidence(
            [other], {}, {}, cache, manifest)], ["photo-unevidenced"])
        # The manifest does not hold the file for them.
        self.assertEqual([i.code for i in validate.check_photo_evidence(
            shown, {}, {}, cache, {"hosted": {}})], ["photo-unevidenced"])


if __name__ == "__main__":
    unittest.main()
