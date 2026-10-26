"""The JPEG 2000 decoder Oregon's pamphlet needs (kyc/jpx.py): standard
library only, lossless, and refusing what it does not read.

The fixture is an image from the State Voters' Pamphlet itself (a drop box's
mask, VP_G26-Book12 object 149: 456x460, four tiles, the pamphlet's coding).
Its pixels, as this decoder gives them, were compared on 2026-10-25 with
what Chrome's own PDF renderer (PDFium, which decodes with OpenJPEG) draws
of it at one pixel to one pixel: every one of 209,760 the same. So were the
five candidates' photographs the site shows."""

import hashlib
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import jpx  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "jpx_dropbox_mask.jp2")
PIXELS = "2ce8eb2f66158e79c6de62efdd5f3599dfc5c46214f8ee53bf1d5afdb3297450"


def fixture():
    with open(FIXTURE, "rb") as handle:
        return handle.read()


def segment(cs, marker):
    """``(start of its body, length)`` of the first *marker* segment."""
    pos = 2
    while True:
        m, length = struct.unpack(">HH", cs[pos:pos + 4])
        if m == marker:
            return pos + 4, length - 2
        pos += 2 + length


class TestTheFixture(unittest.TestCase):
    def test_it_decodes_to_the_pixels_pdfium_draws(self):
        width, height, rows = jpx.decode(fixture())
        self.assertEqual((width, height), (456, 460))
        self.assertEqual(hashlib.sha256(b"".join(rows)).hexdigest(), PIXELS)
        # A mask: black about the shape, white inside it.
        self.assertEqual((rows[0][0], rows[459][455], rows[230][228]), (0, 0, 255))

    def test_the_png_holds_those_very_pixels(self):
        width, height, rows = jpx.decode(fixture())
        again = jpx.png_pixels(jpx.png(width, height, rows))
        self.assertEqual(again, (width, height, rows))


class TestRefusals(unittest.TestCase):
    """Anything outside the profile is refused, never guessed."""

    def changed(self, marker, offset, value):
        data = bytearray(fixture())
        cs_at = data.index(b"\xff\x4f\xff\x51")
        body, _ = segment(bytes(data[cs_at:]), marker)
        data[cs_at + body + offset] = value
        return bytes(data)

    def test_the_irreversible_wavelet(self):
        with self.assertRaisesRegex(jpx.JPXError, "5/3"):
            jpx.decode(self.changed(0xFF52, 9, 0))

    def test_a_code_block_mode(self):
        with self.assertRaisesRegex(jpx.JPXError, "code-block style"):
            jpx.decode(self.changed(0xFF52, 8, 1))

    def test_precincts(self):
        with self.assertRaisesRegex(jpx.JPXError, "precincts"):
            jpx.decode(self.changed(0xFF52, 0, 1))

    def test_quantization(self):
        with self.assertRaisesRegex(jpx.JPXError, "quantization"):
            jpx.decode(self.changed(0xFF5C, 0, 0x42))

    def test_a_tile_whose_packets_do_not_use_its_bytes(self):
        data = bytearray(fixture())
        last = data.rindex(b"\xff\x90\x00\x0a")
        psot = struct.unpack(">I", data[last + 6:last + 10])[0]
        # One byte more in the last tile-part than its packets use.
        data[last + 6:last + 10] = struct.pack(">I", psot + 1)
        data[last + psot:last + psot] = b"\x00"
        with self.assertRaises(jpx.JPXError):
            jpx.decode(bytes(data))

    def test_not_a_jpeg_2000(self):
        with self.assertRaises(jpx.JPXError):
            jpx.decode(b"\xff\xd8\xff\xe0 a JPEG")


class TestTheWavelet(unittest.TestCase):
    def test_the_synthesis_undoes_the_analysis_at_every_parity(self):
        rng = random.Random(20261025)
        for n in range(1, 40):
            for i0 in range(4):
                x = [rng.randint(-512, 512) for _ in range(n)]
                self.assertEqual(jpx.synthesis_1d(jpx.analysis_1d(x, i0), i0), x, (n, i0))


class MQEncoder:
    """T.800 C.2's MQ encoder, written from the standard apart from the
    decoder, so a round trip tests the decoder against it."""

    def __init__(self, contexts):
        self.cx = [list(c) for c in contexts]
        self.a, self.c, self.ct = 0x8000, 0, 12
        self.out = bytearray()
        self.b = None

    def _byteout(self):
        if self.b is None:          # BP before the start: the first byte
            self.b = (self.c >> 19) & 0xFF
            self.c &= 0x7FFFF
            self.ct = 8
            return
        if self.b == 0xFF:
            self.out.append(self.b)
            self.b = (self.c >> 20) & 0xFF
            self.c &= 0xFFFFF
            self.ct = 7
        elif self.c < 0x8000000:
            self.out.append(self.b)
            self.b = (self.c >> 19) & 0xFF
            self.c &= 0x7FFFF
            self.ct = 8
        else:
            self.b += 1
            if self.b == 0xFF:
                self.c &= 0x7FFFFFF
                self.out.append(self.b)
                self.b = (self.c >> 20) & 0xFF
                self.c &= 0xFFFFF
                self.ct = 7
            else:
                self.out.append(self.b)
                self.b = (self.c >> 19) & 0xFF
                self.c &= 0x7FFFF
                self.ct = 8

    def _renorm(self):
        while True:
            self.a = (self.a << 1) & 0xFFFF
            self.c <<= 1
            self.ct -= 1
            if self.ct == 0:
                self._byteout()
            if self.a & 0x8000:
                break

    def encode(self, n, d):
        cx = self.cx[n]
        qe, nmps, nlps, switch = jpx._QE[cx[0]]
        if d == cx[1]:
            self.a -= qe
            if not self.a & 0x8000:
                if self.a < qe:
                    self.a = qe
                else:
                    self.c += qe
                cx[0] = nmps
                self._renorm()
            else:
                self.c += qe
        else:
            self.a -= qe
            if self.a < qe:
                self.c += qe
            else:
                self.a = qe
            if switch:
                cx[1] = 1 - cx[1]
            cx[0] = nlps
            self._renorm()

    def flush(self):
        # SETBITS, then two byte-outs.
        temp = self.c + self.a
        self.c |= 0xFFFF
        if self.c >= temp:
            self.c -= 0x8000
        self.c <<= self.ct
        self._byteout()
        self.c <<= self.ct
        self._byteout()
        if self.b is not None and self.b != 0xFF:
            self.out.append(self.b)
        return bytes(self.out)


class TestTheArithmeticDecoder(unittest.TestCase):
    def test_a_round_trip_through_the_standards_encoder(self):
        rng = random.Random(7)
        for trial in range(20):
            symbols = []
            for _ in range(2000):
                n = rng.randrange(19)
                # Skewed, as the coder's real input is.
                d = 1 if rng.random() < (0.9 if n % 2 else 0.2) else 0
                symbols.append((n, d))
            enc = MQEncoder(jpx._INITIAL)
            for n, d in symbols:
                enc.encode(n, d)
            data = enc.flush()
            dec = jpx.MQDecoder(data, jpx._INITIAL)
            self.assertEqual([dec.decode(n) for n, _d in symbols], [d for _n, d in symbols],
                             trial)


if __name__ == "__main__":
    unittest.main()
