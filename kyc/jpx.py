"""A JPEG 2000 decoder for the one kind of image Oregon's State Voters'
Pamphlet holds, standard library only (kyc/guide_photos.py).

Oregon prints each candidate's photograph in its county pamphlets as a JPEG
2000 codestream inside the PDF (``JPXDecode``), which no browser draws. Every
one read on 2026-10-25 was coded the same way, by Adobe's PDF library: one
grey component of 8 bits, 256-pixel tiles, five levels of the reversible
5/3 wavelet with no quantization, 32x32 code-blocks in the default mode, one
precinct per resolution. That coding is lossless: decoded whole, it gives
back the very pixels that were coded, which this module writes as a PNG
(zlib) - nothing scaled, filtered or retouched.

Anything outside that - the irreversible 9/7 wavelet, quantization, colour,
a code-block mode, precincts, regions of interest, progression changes,
packed headers, a layer left out - is refused (``JPXError``), never guessed:
an image this site cannot decode faithfully is not shown. Each tile's
packets must use up its data exactly, and each code-block's passes its
bytes, or the image is refused.

The algorithms are ITU-T T.800 (ISO/IEC 15444-1): Annex B (structure),
Annex C (the MQ arithmetic decoder), Annex D (coefficient bit modelling),
Annex F (the 5/3 reversible synthesis), and the reconstruction convention of
the reference decoder (OpenJPEG), which decodes with one fractional bit.
"""

import struct
import zlib


class JPXError(ValueError):
    """The codestream is not one this decoder reads faithfully."""


# ------------------------------------------------------------------ boxes

def codestream(data):
    """The contiguous codestream of a JP2 file, or *data* itself when it is a
    bare codestream."""
    if data[:4] == b"\xff\x4f\xff\x51":
        return data
    if data[4:8] != b"jP  ":
        raise JPXError("neither a JP2 file nor a JPEG 2000 codestream")
    pos = 0
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        head = 8
        if length == 1:
            length = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            head = 16
        elif length == 0:
            length = len(data) - pos
        if length < head:
            raise JPXError("a box shorter than its header")
        if kind == b"jp2c":
            return data[pos + head:pos + length]
        pos += length
    raise JPXError("no codestream box")


# ------------------------------------------------------------------ the MQ decoder

# Table C.2: Qe, the next index on an MPS, on an LPS, and whether an LPS
# switches the sense of the MPS.
_QE = (
    (0x5601, 1, 1, 1), (0x3401, 2, 6, 0), (0x1801, 3, 9, 0), (0x0AC1, 4, 12, 0),
    (0x0521, 5, 29, 0), (0x0221, 38, 33, 0), (0x5601, 7, 6, 1), (0x5401, 8, 14, 0),
    (0x4801, 9, 14, 0), (0x3801, 10, 14, 0), (0x3001, 11, 17, 0), (0x2401, 12, 18, 0),
    (0x1C01, 13, 20, 0), (0x1601, 29, 21, 0), (0x5601, 15, 14, 1), (0x5401, 16, 14, 0),
    (0x5101, 17, 15, 0), (0x4801, 18, 16, 0), (0x3801, 19, 17, 0), (0x3401, 20, 18, 0),
    (0x3001, 21, 19, 0), (0x2801, 22, 19, 0), (0x2401, 23, 20, 0), (0x2201, 24, 21, 0),
    (0x1C01, 25, 22, 0), (0x1801, 26, 23, 0), (0x1601, 27, 24, 0), (0x1401, 28, 25, 0),
    (0x1201, 29, 26, 0), (0x1101, 30, 27, 0), (0x0AC1, 31, 28, 0), (0x09C1, 32, 29, 0),
    (0x08A1, 33, 30, 0), (0x0521, 34, 31, 0), (0x0441, 35, 32, 0), (0x02A1, 36, 33, 0),
    (0x0221, 37, 34, 0), (0x0141, 38, 35, 0), (0x0111, 39, 36, 0), (0x0085, 40, 37, 0),
    (0x0049, 41, 38, 0), (0x0025, 42, 39, 0), (0x0015, 43, 40, 0), (0x0009, 44, 41, 0),
    (0x0005, 45, 42, 0), (0x0001, 45, 43, 0), (0x5601, 46, 46, 0),
)


class MQDecoder:
    """The MQ arithmetic decoder of Annex C, over one code-block's bytes
    (followed, as the standard has it, by 0xFF bytes)."""

    def __init__(self, data, contexts):
        self.data = bytes(data) + b"\xff\xff"
        self.end = len(data)
        self.bp = 0
        # Each context: [index, mps].
        self.cx = [list(c) for c in contexts]
        self.c = (self.data[0] << 16)
        self._bytein()
        self.c = (self.c << 7) & 0xFFFFFFFF
        self.ct -= 7
        self.a = 0x8000

    def _bytein(self):
        data, bp = self.data, self.bp
        if data[bp] == 0xFF:
            if data[bp + 1] > 0x8F:
                self.c += 0xFF00
                self.ct = 8
            else:
                self.bp = bp + 1
                self.c += data[bp + 1] << 9
                self.ct = 7
        else:
            self.bp = bp + 1
            self.c += data[bp + 1] << 8
            self.ct = 8
        self.c &= 0xFFFFFFFF

    def _renorm(self):
        while True:
            if self.ct == 0:
                self._bytein()
            self.a = (self.a << 1) & 0xFFFF
            self.c = (self.c << 1) & 0xFFFFFFFF
            self.ct -= 1
            if self.a & 0x8000:
                break

    def decode(self, n):
        cx = self.cx[n]
        qe, nmps, nlps, switch = _QE[cx[0]]
        self.a -= qe
        if (self.c >> 16) < qe:
            # The LPS sub-interval (C.3.2, LPS_EXCHANGE).
            if self.a < qe:
                self.a = qe
                d = cx[1]
                cx[0] = nmps
            else:
                self.a = qe
                d = 1 - cx[1]
                if switch:
                    cx[1] = 1 - cx[1]
                cx[0] = nlps
            self._renorm()
            return d
        self.c = (self.c - (qe << 16)) & 0xFFFFFFFF
        if self.a & 0x8000:
            return cx[1]
        # MPS_EXCHANGE.
        if self.a < qe:
            d = 1 - cx[1]
            if switch:
                cx[1] = 1 - cx[1]
            cx[0] = nlps
        else:
            d = cx[1]
            cx[0] = nmps
        self._renorm()
        return d


# ------------------------------------------------------------------ coefficient bit modelling

UNIFORM, RUN = 18, 17
_INITIAL = [(0, 0)] * 19
_INITIAL[0] = (4, 0)
_INITIAL[RUN] = (3, 0)
_INITIAL[UNIFORM] = (46, 0)


def _zc_table(kind):
    """Table D.1: the zero coding context for each (h, v, d) count of
    significant neighbours, by subband: "LL"/"LH", "HL" or "HH"."""
    out = {}
    for h in range(3):
        for v in range(3):
            for d in range(5):
                if kind == "HH":
                    hv = h + v
                    if d >= 3:
                        c = 8
                    elif d == 2:
                        c = 7 if hv >= 1 else 6
                    elif d == 1:
                        c = 5 if hv >= 2 else 4 if hv == 1 else 3
                    else:
                        c = 2 if hv >= 2 else 1 if hv == 1 else 0
                else:
                    a, b = (h, v) if kind != "HL" else (v, h)
                    if a == 2:
                        c = 8
                    elif a == 1:
                        c = 7 if b >= 1 else 6 if d >= 1 else 5
                    else:
                        c = 4 if b == 2 else 3 if b == 1 else 2 if d >= 2 else 1 if d == 1 else 0
                out[(h, v, d)] = c
    return out


_ZC = {kind: _zc_table(kind) for kind in ("LL", "HL", "HH")}
# Table D.3: (context, xor bit) by the horizontal and vertical contributions.
_SC = {(1, 1): (13, 0), (1, 0): (12, 0), (1, -1): (11, 0),
       (0, 1): (10, 0), (0, 0): (9, 0), (0, -1): (10, 1),
       (-1, 1): (11, 1), (-1, 0): (12, 1), (-1, -1): (13, 1)}


def decode_block(data, width, height, bitplanes, passes, kind):
    """A code-block's coefficients, ``[row][col]`` integers, from its bytes:
    *bitplanes* magnitude bit-planes (the band's less the block's zero
    bit-planes), *passes* coding passes (cleanup first), in the default
    mode. Reconstructed as the reference decoder does, with one fractional
    bit: exact when every pass is decoded."""
    if passes <= 0 or bitplanes <= 0:
        return [[0] * width for _ in range(height)]
    if passes > 3 * bitplanes - 2:
        raise JPXError("a code-block with more passes than bit-planes")
    zc = _ZC["LL" if kind in ("LL", "LH") else kind]
    mq = MQDecoder(data, _INITIAL)
    w2 = width + 2
    size = w2 * (height + 2)
    sig = [0] * size          # 1 where significant
    neg = [0] * size          # 1 where negative
    seen = [0] * size         # visited in this bit-plane's significance pass
    refined = [0] * size      # refined at least once
    mag = [0] * size          # twice the magnitude, as the reference decoder keeps it
    pad = [False] * size      # outside the block: never significant
    for y in range(height + 2):
        for x in range(w2):
            if x == 0 or y == 0 or x == w2 - 1 or y == height + 1:
                pad[y * w2 + x] = True

    def counts(i):
        h = sig[i - 1] + sig[i + 1]
        v = sig[i - w2] + sig[i + w2]
        d = sig[i - w2 - 1] + sig[i - w2 + 1] + sig[i + w2 - 1] + sig[i + w2 + 1]
        return h, v, d

    def contribution(a, b):
        out = 0
        for j in (a, b):
            if sig[j]:
                out += -1 if neg[j] else 1
        return 1 if out > 0 else -1 if out < 0 else 0

    def sign_of(i):
        ctx, xor = _SC[(contribution(i - 1, i + 1), contribution(i - w2, i + w2))]
        return mq.decode(ctx) ^ xor

    def significant(i, p):
        neg[i] = sign_of(i)
        sig[i] = 1
        mag[i] = 3 << p

    order = []
    for top in range(0, height, 4):
        rows = min(4, height - top)
        for x in range(width):
            order.append((top, rows, x))

    def cleanup(p):
        for top, rows, x in order:
            start = (top + 1) * w2 + x + 1
            y = 0
            if rows == 4:
                column = [start + k * w2 for k in range(4)]
                if all(not sig[i] and not seen[i] and counts(i) == (0, 0, 0) for i in column):
                    if not mq.decode(RUN):
                        continue
                    y = (mq.decode(UNIFORM) << 1) | mq.decode(UNIFORM)
                    significant(column[y], p)
                    y += 1
            while y < rows:
                i = start + y * w2
                if not sig[i] and not seen[i]:
                    if mq.decode(zc[counts(i)]):
                        significant(i, p)
                y += 1
        for i in range(size):
            seen[i] = 0

    def significance(p):
        for top, rows, x in order:
            start = (top + 1) * w2 + x + 1
            for y in range(rows):
                i = start + y * w2
                if sig[i]:
                    continue
                c = counts(i)
                if c == (0, 0, 0):
                    continue
                seen[i] = 1
                if mq.decode(zc[c]):
                    significant(i, p)

    def refinement(p):
        for top, rows, x in order:
            start = (top + 1) * w2 + x + 1
            for y in range(rows):
                i = start + y * w2
                if not sig[i] or seen[i]:
                    continue
                if refined[i]:
                    ctx = 16
                else:
                    ctx = 15 if counts(i) != (0, 0, 0) else 14
                    refined[i] = 1
                mag[i] += (1 << p) if mq.decode(ctx) else -(1 << p)

    p = bitplanes - 1
    done = 0
    cleanup(p)
    done += 1
    while done < passes:
        p -= 1
        significance(p)
        done += 1
        if done >= passes:
            break
        refinement(p)
        done += 1
        if done >= passes:
            break
        cleanup(p)
        done += 1
    if mq.bp > mq.end + 2:
        raise JPXError("a code-block read past its bytes")
    out = []
    for y in range(height):
        row = []
        base = (y + 1) * w2 + 1
        for x in range(width):
            i = base + x
            value = mag[i] >> 1
            row.append(-value if neg[i] else value)
        out.append(row)
    return out


# ------------------------------------------------------------------ packets

class _Bits:
    """The packet header's bit reader, with the bit stuffing of B.10.1."""

    def __init__(self, data, pos):
        self.data = data
        self.pos = pos
        self.buf = 0
        self.ct = 0

    def bit(self):
        if self.ct == 0:
            self.buf = (self.buf << 8) & 0xFFFF
            self.ct = 7 if self.buf == 0xFF00 else 8
            if self.pos >= len(self.data):
                raise JPXError("a packet header runs past its tile")
            self.buf |= self.data[self.pos]
            self.pos += 1
        self.ct -= 1
        return (self.buf >> self.ct) & 1

    def bits(self, n):
        out = 0
        for _ in range(n):
            out = (out << 1) | self.bit()
        return out

    def align(self):
        if (self.buf & 0xFF) == 0xFF:
            self.buf = (self.buf << 8) & 0xFFFF
            self.ct = 8
            self.pos += 1
        self.ct = 0
        return self.pos


class _TagTree:
    def __init__(self, width, height):
        self.levels = []
        w, h = width, height
        while True:
            self.levels.append((w, h, [1 << 30] * (w * h), [0] * (w * h)))
            if w == 1 and h == 1:
                break
            w, h = (w + 1) // 2, (h + 1) // 2

    def decode(self, bits, x, y, threshold):
        path = []
        for w, h, value, low in self.levels:
            path.append((value, low, y * w + x))
            x, y = x // 2, y // 2
        floor = 0
        for value, low, i in reversed(path):
            if floor > low[i]:
                low[i] = floor
            else:
                floor = low[i]
            while floor < threshold and floor < value[i]:
                if bits.bit():
                    value[i] = floor
                else:
                    floor += 1
            low[i] = floor
        leaf_value, _low, leaf = path[0]
        return leaf_value[leaf] < threshold

    def value(self, x, y):
        w = self.levels[0][0]
        return self.levels[0][2][y * w + x]


def _passes(bits):
    if not bits.bit():
        return 1
    if not bits.bit():
        return 2
    n = bits.bits(2)
    if n != 3:
        return 3 + n
    n = bits.bits(5)
    if n != 31:
        return 6 + n
    return 37 + bits.bits(7)


def _ceil_div(a, b):
    return -(-a // b)


class _Block:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.included = False
        self.bitplanes = 0
        self.lblock = 3
        self.passes = 0
        self.data = bytearray()


class _Band:
    def __init__(self, kind, x0, y0, x1, y1, xcb, ycb, magnitude_bits):
        self.kind = kind
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.bits = magnitude_bits
        self.blocks = []
        self.cols = self.rows = 0
        if x1 > x0 and y1 > y0:
            bx0, by0 = x0 >> xcb, y0 >> ycb
            bx1, by1 = _ceil_div(x1, 1 << xcb), _ceil_div(y1, 1 << ycb)
            self.cols, self.rows = bx1 - bx0, by1 - by0
            for by in range(by0, by1):
                for bx in range(bx0, bx1):
                    self.blocks.append(_Block(max(x0, bx << xcb), max(y0, by << ycb),
                                              min(x1, (bx + 1) << xcb), min(y1, (by + 1) << ycb)))
            self.inclusion = _TagTree(self.cols, self.rows)
            self.zero = _TagTree(self.cols, self.rows)


# ------------------------------------------------------------------ the 5/3 synthesis

def _pse(i, i0, i1):
    if i1 - i0 == 1:
        return i0
    period = 2 * (i1 - i0 - 1)
    k = (i - i0) % period
    return i0 + min(k, period - k)


def synthesis_1d(y, i0):
    """F.3.8.1's reversible 5/3 1D_SR over samples *y* standing for
    coordinates ``i0 .. i0 + len(y) - 1`` (even coordinates low-pass)."""
    i1 = i0 + len(y)
    if len(y) == 1:
        return [int(y[0] / 2)] if i0 % 2 else list(y)

    def Y(i):
        return y[_pse(i, i0, i1) - i0]

    x = {}
    for n in range(i0 // 2, i1 // 2 + 1):
        x[2 * n] = Y(2 * n) - ((Y(2 * n - 1) + Y(2 * n + 1) + 2) >> 2)
    for n in range(i0 // 2, i1 // 2):
        x[2 * n + 1] = Y(2 * n + 1) + ((x[2 * n] + x[2 * n + 2]) >> 1)
    return [x[i] for i in range(i0, i1)]


def analysis_1d(x, i0):
    """The forward 5/3 (F.4.8.1), the inverse of :func:`synthesis_1d`: for
    the tests' round trip."""
    i1 = i0 + len(x)
    if len(x) == 1:
        return [x[0] * 2] if i0 % 2 else list(x)

    def X(i):
        return x[_pse(i, i0, i1) - i0]

    def odd(i):
        return X(i) - ((X(i - 1) + X(i + 1)) >> 1)

    return [odd(i) if i % 2 else X(i) + ((odd(i - 1) + odd(i + 1) + 2) >> 2)
            for i in range(i0, i1)]


def _synthesis_2d(ll, bands, x0, y0, x1, y1):
    """One level: interleave LL, HL, LH and HH (F.3.3) over the resolution
    region ``[x0, x1) x [y0, y1)``, then each row (HOR_SR), then each column
    (VER_SR)."""
    width, height = x1 - x0, y1 - y0
    out = [[0] * width for _ in range(height)]
    for kind, (data, bx0, by0) in (("LL", ll), ("HL", bands["HL"]), ("LH", bands["LH"]),
                                   ("HH", bands["HH"])):
        ox = 1 if kind in ("HL", "HH") else 0
        oy = 1 if kind in ("LH", "HH") else 0
        for j, row in enumerate(data):
            v = 2 * (by0 + j) + oy - y0
            if not 0 <= v < height:
                raise JPXError("a subband outside its resolution")
            target = out[v]
            for i, value in enumerate(row):
                u = 2 * (bx0 + i) + ox - x0
                if not 0 <= u < width:
                    raise JPXError("a subband outside its resolution")
                target[u] = value
    if width:
        out = [synthesis_1d(row, x0) for row in out]
    if height:
        columns = [synthesis_1d([out[r][c] for r in range(height)], y0) for c in range(width)]
        out = [[columns[c][r] for c in range(width)] for r in range(height)]
    return out


# ------------------------------------------------------------------ the codestream

def _u16(data, pos):
    return struct.unpack(">H", data[pos:pos + 2])[0]


def decode(data):
    """``(width, height, rows)``: the grey image a JPEG 2000 file or
    codestream holds, each row ``bytes`` of 8-bit samples; ``JPXError`` for
    anything outside the profile this module reads faithfully."""
    cs = codestream(data)
    if _u16(cs, 0) != 0xFF4F:
        raise JPXError("no start of codestream")
    pos = 2
    siz = cod = qcd = None
    while True:
        if pos + 4 > len(cs):
            raise JPXError("the main header never ends")
        marker = _u16(cs, pos)
        if marker == 0xFF90:
            break
        length = _u16(cs, pos + 2)
        seg = cs[pos + 4:pos + 2 + length]
        if marker == 0xFF51:
            siz = seg
        elif marker == 0xFF52:
            cod = seg
        elif marker == 0xFF5C:
            qcd = seg
        elif marker in (0xFF55, 0xFF57, 0xFF63, 0xFF64):
            pass                          # TLM, PLM, CRG, COM: nothing to decode
        else:
            raise JPXError(f"marker {marker:04X} in the main header (not read)")
        pos += 2 + length
    if not (siz and cod and qcd):
        raise JPXError("a main header without SIZ, COD and QCD")
    (_rsiz, xsiz, ysiz, xo, yo, xt, yt, xto, yto, comps) = struct.unpack(">HIIIIIIIIH", siz[:36])
    if comps != 1:
        raise JPXError(f"{comps} components: only a grey image is read")
    ssiz, xr, yr = siz[36], siz[37], siz[38]
    if ssiz != 7 or xr != 1 or yr != 1:
        raise JPXError("not 8 unsigned bits at full resolution")
    scod, order, layers, mct, levels, xcb, ycb, style, transform = struct.unpack(">BBHBBBBBB", cod[:10])
    if scod & 1 or len(cod) > 10:
        raise JPXError("precincts given: not read")
    if mct or transform != 1:
        raise JPXError("not the reversible 5/3 wavelet")
    if style:
        raise JPXError(f"code-block style {style}: not read")
    if order > 4:
        raise JPXError("an unknown progression order")
    xcb, ycb = xcb + 2, ycb + 2
    sop, eph = bool(scod & 2), bool(scod & 4)
    guard, qstyle = qcd[0] >> 5, qcd[0] & 0x1F
    if qstyle != 0 or len(qcd) != 1 + 3 * levels + 1:
        raise JPXError("quantization: not the reversible profile")
    exponents = [b >> 3 for b in qcd[1:]]
    width, height = xsiz - xo, ysiz - yo
    if width <= 0 or height <= 0 or xt <= 0 or yt <= 0:
        raise JPXError("an empty image")
    tiles_x, tiles_y = _ceil_div(xsiz - xto, xt), _ceil_div(ysiz - yto, yt)
    # Every tile's data, its tile-parts joined in order.
    parts = {}
    while pos + 2 <= len(cs):
        marker = _u16(cs, pos)
        if marker == 0xFFD9:
            break
        if marker != 0xFF90:
            raise JPXError(f"marker {marker:04X} where a tile-part should start")
        _lsot, tile, psot, tpsot, _tnsot = struct.unpack(">HHIBB", cs[pos + 2:pos + 12])
        end = pos + psot if psot else len(cs) - 2
        p = pos + 12
        while True:
            m = _u16(cs, p)
            if m == 0xFF93:
                p += 2
                break
            if m in (0xFF58, 0xFF64):      # PLT, COM
                p += 2 + _u16(cs, p + 2)
                continue
            raise JPXError(f"marker {m:04X} in a tile-part header (not read)")
        if tile >= tiles_x * tiles_y or tpsot != len(parts.get(tile, [])):
            raise JPXError("tile-parts out of order")
        parts.setdefault(tile, []).append(cs[p:end])
        pos = end
    if len(parts) != tiles_x * tiles_y:
        raise JPXError(f"{len(parts)} of {tiles_x * tiles_y} tiles")
    image = [bytearray(width) for _ in range(height)]
    for tile in range(tiles_x * tiles_y):
        p, q = tile % tiles_x, tile // tiles_x
        tx0, ty0 = max(xto + p * xt, xo), max(yto + q * yt, yo)
        tx1, ty1 = min(xto + (p + 1) * xt, xsiz), min(yto + (q + 1) * yt, ysiz)
        samples = _tile(b"".join(parts[tile]), tx0, ty0, tx1, ty1, levels, layers, order,
                        xcb, ycb, guard, exponents, sop, eph)
        for j, row in enumerate(samples):
            line = image[ty0 - yo + j]
            for i, value in enumerate(row):
                value += 128
                line[tx0 - xo + i] = 0 if value < 0 else 255 if value > 255 else value
    return width, height, [bytes(row) for row in image]


def _tile(data, tx0, ty0, tx1, ty1, levels, layers, order, xcb, ycb, guard, exponents,
          sop, eph):
    resolutions = []
    for r in range(levels + 1):
        n = levels - r
        rx0, ry0 = _ceil_div(tx0, 1 << n), _ceil_div(ty0, 1 << n)
        rx1, ry1 = _ceil_div(tx1, 1 << n), _ceil_div(ty1, 1 << n)
        if rx1 > rx0 and ry1 > ry0 and (rx0 >> 15 != (rx1 - 1) >> 15
                                        or ry0 >> 15 != (ry1 - 1) >> 15):
            raise JPXError("more than one precinct in a resolution")
        bands = []
        kinds = ("LL",) if r == 0 else ("HL", "LH", "HH")
        nb = levels if r == 0 else levels - r + 1
        for k, kind in enumerate(kinds):
            ox = 1 if kind in ("HL", "HH") else 0
            oy = 1 if kind in ("LH", "HH") else 0
            half = (1 << (nb - 1)) if nb else 0
            bx0 = _ceil_div(tx0 - half * ox, 1 << nb)
            by0 = _ceil_div(ty0 - half * oy, 1 << nb)
            bx1 = _ceil_div(tx1 - half * ox, 1 << nb)
            by1 = _ceil_div(ty1 - half * oy, 1 << nb)
            index = 0 if r == 0 else 3 * (r - 1) + 1 + k
            bands.append(_Band(kind, bx0, by0, bx1, by1, xcb, ycb,
                               guard + exponents[index] - 1))
        resolutions.append(((rx0, ry0, rx1, ry1), bands))
    # One component, one precinct per resolution: the progression orders
    # differ only in whether layers or resolutions come first.
    if order == 0:
        sequence = [(layer, r) for layer in range(layers) for r in range(levels + 1)]
    else:
        sequence = [(layer, r) for r in range(levels + 1) for layer in range(layers)]
    pos = 0
    for layer, r in sequence:
        (rx0, ry0, rx1, ry1), bands = resolutions[r]
        if rx1 <= rx0 or ry1 <= ry0:
            continue
        if sop:
            if data[pos:pos + 2] != b"\xff\x91":
                raise JPXError("a packet without its SOP marker")
            pos += 6
        bits = _Bits(data, pos)
        pending = []
        if bits.bit():
            for band in bands:
                for index, block in enumerate(band.blocks):
                    bx, by = index % band.cols, index // band.cols
                    if not block.included:
                        here = band.inclusion.decode(bits, bx, by, layer + 1)
                    else:
                        here = bits.bit()
                    if not here:
                        continue
                    if not block.included:
                        zero = 0
                        while not band.zero.decode(bits, bx, by, zero + 1):
                            zero += 1
                        block.bitplanes = band.bits - band.zero.value(bx, by)
                        block.included = True
                    new = _passes(bits)
                    while bits.bit():
                        block.lblock += 1
                    length = bits.bits(block.lblock + new.bit_length() - 1)
                    pending.append((block, new, length))
        pos = bits.align()
        if eph:
            if data[pos:pos + 2] != b"\xff\x92":
                raise JPXError("a packet header without its EPH marker")
            pos += 2
        for block, new, length in pending:
            if pos + length > len(data):
                raise JPXError("a packet's body runs past its tile")
            block.data += data[pos:pos + length]
            block.passes += new
            pos += length
    if pos != len(data):
        raise JPXError(f"a tile's packets use {pos} of its {len(data)} bytes")
    # Tier 1, then the synthesis from the lowest resolution up.
    decoded = []
    for (_region, bands) in resolutions:
        level = {}
        for band in bands:
            rows = [[0] * (band.x1 - band.x0) for _ in range(band.y1 - band.y0)]
            for block in band.blocks:
                if not block.included:
                    continue
                values = decode_block(block.data, block.x1 - block.x0, block.y1 - block.y0,
                                      block.bitplanes, block.passes, band.kind)
                for j, row in enumerate(values):
                    rows[block.y0 - band.y0 + j][block.x0 - band.x0:block.x1 - band.x0] = row
            level[band.kind] = (rows, band.x0, band.y0)
        decoded.append(level)
    current = decoded[0]["LL"][0]
    for r in range(1, levels + 1):
        (rx0, ry0, rx1, ry1), _bands = resolutions[r]
        (px0, py0, _px1, _py1), _ = resolutions[r - 1]
        current = _synthesis_2d((current, px0, py0), decoded[r], rx0, ry0, rx1, ry1)
    return current


# ------------------------------------------------------------------ PNG

def png(width, height, rows):
    """A grey 8-bit PNG of *rows*: the decoded pixels, unchanged."""
    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def png_pixels(data):
    """``(width, height, rows)`` of a grey 8-bit PNG this module wrote (no
    filter): what the tests compare."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise JPXError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    pos, idat = 8, b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        if kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    rows = [raw[i * (width + 1) + 1:(i + 1) * (width + 1)] for i in range(height)]
    return width, height, rows
