"""A small PDF reader, standard library only: objects, pages, the text a
page shows with where it stands, and the images it draws (rules 24, 91).

The election offices that print a candidate's photograph beside their name
serve some guides only as PDFs: Alaska's Official Election Pamphlet has one
statement per candidate, Oregon's State Voters' Pamphlet one book per
county (kyc/guide_photos.py). A guide's photograph is taken only where the
page draws it beside the words naming the person, so this reads what a page
*draws* - each ``Do`` of an image, through any form it sits in, with the
place the page's matrices put it - never what a file merely holds: the
first research reader counted ``/Image`` across the whole file with a
pattern that ran from one object into the next, and counted the document's
catalog as a second image.

What it does not read it refuses (``PDFError``), never guesses: an
encrypted file (none of the guides is; a file that becomes one is reported
unread, rule 8), a filter it does not know, an object it cannot find.
"""

import re
import zlib


class PDFError(ValueError):
    """The file cannot be read as far as the caller needs."""


class Name(str):
    """A PDF name (``/Type``), without its slash."""


class Op(str):
    """A content stream's operator (``Tj``, ``Do``)."""


class Ref(tuple):
    """An indirect reference, ``(number, generation)``."""

    def __new__(cls, num, gen=0):
        return super().__new__(cls, (num, gen))


class Stream:
    def __init__(self, info, raw):
        self.info = info
        self.raw = raw


_WS = b" \t\r\n\f\x00"
_DELIM = b"()<>[]{}/%"
_NUMBER = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)")
_OBJ = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b")
_ENCRYPT = re.compile(rb"/Encrypt\s*(?:\d+\s+\d+\s+R|<<)")
_ESCAPES = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b",
            ord("f"): b"\f", ord("("): b"(", ord(")"): b")", ord("\\"): b"\\"}


def _skip(data, pos):
    n = len(data)
    while pos < n:
        c = data[pos]
        if c in _WS:
            pos += 1
        elif c == 0x25:                                   # % comment
            while pos < n and data[pos] not in b"\r\n":
                pos += 1
        else:
            break
    return pos


def _literal(data, pos):
    """A ``( ... )`` string from just after its opening parenthesis."""
    out = bytearray()
    depth = 1
    n = len(data)
    while pos < n:
        c = data[pos]
        if c == 0x5C:                                     # backslash
            pos += 1
            if pos >= n:
                break
            e = data[pos]
            if e in _ESCAPES:
                out += _ESCAPES[e]
                pos += 1
            elif 0x30 <= e <= 0x37:
                digits = data[pos:pos + 3]
                m = re.match(rb"[0-7]{1,3}", digits)
                out.append(int(m.group(0), 8) & 0xFF)
                pos += len(m.group(0))
            elif e in b"\r\n":                            # a line continued
                pos += 2 if data[pos:pos + 2] == b"\r\n" else 1
            else:
                out.append(e)
                pos += 1
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return bytes(out), pos + 1
        out.append(c)
        pos += 1
    raise PDFError("a string that never closes")


def parse(data, pos=0, ops=False):
    """``(value, next position)`` of the object at *pos*. With *ops*, a bare
    keyword is an operator (``Op``) rather than an error."""
    pos = _skip(data, pos)
    if pos >= len(data):
        raise PDFError("the file ends inside an object")
    c = data[pos:pos + 1]
    if c == b"/":
        end = pos + 1
        while end < len(data) and data[end] not in _WS and data[end] not in _DELIM:
            end += 1
        raw = data[pos + 1:end]
        name = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw)
        return Name(name.decode("latin-1")), end
    if c == b"<" and data[pos + 1:pos + 2] == b"<":
        out = {}
        pos += 2
        while True:
            pos = _skip(data, pos)
            if data[pos:pos + 2] == b">>":
                return out, pos + 2
            key, pos = parse(data, pos)
            if not isinstance(key, Name):
                raise PDFError("a dictionary key that is not a name")
            value, pos = parse(data, pos)
            out[str(key)] = value
    if c == b"<":
        end = data.find(b">", pos)
        if end < 0:
            raise PDFError("a hex string that never closes")
        digits = re.sub(rb"[^0-9A-Fa-f]", b"", data[pos + 1:end])
        if len(digits) % 2:
            digits += b"0"
        return bytes.fromhex(digits.decode("ascii")), end + 1
    if c == b"(":
        return _literal(data, pos + 1)
    if c == b"[":
        out = []
        pos += 1
        while True:
            pos = _skip(data, pos)
            if data[pos:pos + 1] == b"]":
                return out, pos + 1
            value, pos = parse(data, pos, ops)
            out.append(value)
    m = _NUMBER.match(data, pos)
    if m:
        text = m.group(0)
        end = m.end()
        if b"." not in text:
            # "12 0 R": a reference.
            ref = re.match(rb"\s+(\d+)\s+R(?![A-Za-z])", data[end:end + 24])
            if ref and not text.startswith((b"+", b"-")):
                return Ref(int(text), int(ref.group(1))), end + ref.end()
            return int(text), end
        return float(text), end
    end = pos
    while end < len(data) and data[end] not in _WS and data[end] not in _DELIM:
        end += 1
    word = data[pos:end]
    if word == b"true":
        return True, end
    if word == b"false":
        return False, end
    if word == b"null":
        return None, end
    if ops and word:
        return Op(word.decode("latin-1")), end
    if ops and data[pos:pos + 1] in (b"{", b"}"):
        return Op(data[pos:pos + 1].decode()), pos + 1
    raise PDFError(f"cannot read the object at byte {pos}: {data[pos:pos + 20]!r}")


# ------------------------------------------------------------------ filters

def _png_predicted(data, columns, colors=1, bpc=8):
    """Undo PNG predictors (``/Predictor`` 10-15) row by row."""
    bpp = max(1, colors * bpc // 8)
    stride = (columns * colors * bpc + 7) // 8
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    while pos < len(data):
        kind = data[pos]
        row = bytearray(data[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(len(row)):
            left = row[i - bpp] if i >= bpp else 0
            up = prev[i]
            if kind == 1:
                row[i] = (row[i] + left) & 0xFF
            elif kind == 2:
                row[i] = (row[i] + up) & 0xFF
            elif kind == 3:
                row[i] = (row[i] + ((left + up) >> 1)) & 0xFF
            elif kind == 4:
                ul = prev[i - bpp] if i >= bpp else 0
                p = left + up - ul
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - ul)
                pred = left if pa <= pb and pa <= pc else (up if pb <= pc else ul)
                row[i] = (row[i] + pred) & 0xFF
            elif kind != 0:
                raise PDFError(f"PNG predictor {kind}")
        out += row
        prev = row
    return bytes(out)


def _ascii85(data):
    data = re.sub(rb"\s", b"", data)
    if data.endswith(b"~>"):
        data = data[:-2]
    out = bytearray()
    group = []
    for c in data:
        if c == ord("z") and not group:
            out += b"\0\0\0\0"
            continue
        group.append(c - 33)
        if len(group) == 5:
            value = 0
            for g in group:
                value = value * 85 + g
            out += value.to_bytes(4, "big")
            group = []
    if group:
        n = len(group)
        group += [84] * (5 - n)
        value = 0
        for g in group:
            value = value * 85 + g
        out += value.to_bytes(4, "big")[:n - 1]
    return bytes(out)


# Image filters are left to the caller: the bytes of a JPEG (DCTDecode) or a
# JPEG 2000 codestream (JPXDecode) are the image itself.
IMAGE_FILTERS = ("DCTDecode", "JPXDecode", "CCITTFaxDecode", "JBIG2Decode")


def decode(stream, stop_at_image=True):
    """The stream's bytes with its filters undone, up to an image filter
    when *stop_at_image* (returned with the image filter's name); ``(bytes,
    image filter or None)``."""
    filters = stream.info.get("Filter")
    params = stream.info.get("DecodeParms")
    filters = [] if filters is None else (filters if isinstance(filters, list) else [filters])
    params = params if isinstance(params, list) else [params] * max(1, len(filters))
    data = stream.raw
    for i, name in enumerate(filters):
        name = str(name)
        parm = params[i] if i < len(params) and isinstance(params[i], dict) else {}
        if name in ("FlateDecode", "Fl"):
            try:
                data = zlib.decompress(data)
            except zlib.error:
                data = zlib.decompressobj().decompress(data)
            if (parm.get("Predictor") or 1) >= 10:
                data = _png_predicted(data, parm.get("Columns") or 1, parm.get("Colors") or 1,
                                      parm.get("BitsPerComponent") or 8)
            elif (parm.get("Predictor") or 1) == 2:
                raise PDFError("TIFF predictor")
        elif name in ("ASCIIHexDecode", "AHx"):
            digits = re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0])
            data = bytes.fromhex((digits + b"0" * (len(digits) % 2)).decode())
        elif name in ("ASCII85Decode", "A85"):
            data = _ascii85(data)
        elif name in IMAGE_FILTERS and stop_at_image:
            if i != len(filters) - 1:
                raise PDFError(f"{name} is not the last filter")
            return data, name
        else:
            raise PDFError(f"a filter this reader does not know: {name}")
    return data, None


# ----------------------------------------------------------------- the file

class Document:
    """A PDF's objects, read where they stand in the file (the cross-reference
    table is not needed for that) and from its object streams."""

    def __init__(self, data):
        if not data.startswith(b"%PDF-"):
            raise PDFError("not a PDF")
        if _ENCRYPT.search(data):
            raise PDFError("the file is encrypted")
        self.data = data
        self._at = {}
        for m in _OBJ.finditer(data):
            # The last definition stands (an incremental update adds one).
            self._at[int(m.group(1))] = m.end()
        self._cache = {}
        self._in_streams = None

    def _top(self, num):
        pos = self._at[num]
        value, pos = parse(self.data, pos)
        pos = _skip(self.data, pos)
        if isinstance(value, dict) and self.data.startswith(b"stream", pos):
            pos += len(b"stream")
            if self.data[pos:pos + 2] == b"\r\n":
                pos += 2
            elif self.data[pos:pos + 1] in (b"\n", b"\r"):
                pos += 1
            length = self.resolve(value.get("Length"))
            if not isinstance(length, int) or length < 0:
                raise PDFError(f"object {num}: a stream with no length")
            raw = self.data[pos:pos + length]
            after = _skip(self.data, pos + length)
            if not self.data.startswith(b"endstream", after):
                raise PDFError(f"object {num}: the stream is not {length} bytes long")
            return Stream(value, raw)
        return value

    def _object_streams(self):
        if self._in_streams is None:
            self._in_streams = {}
            for num in list(self._at):
                try:
                    value = self._top(num)
                except PDFError:
                    continue
                if isinstance(value, Stream) and value.info.get("Type") == "ObjStm":
                    data, _ = decode(value, stop_at_image=False)
                    first = value.info.get("First") or 0
                    header = data[:first].split()
                    for i in range(0, len(header) - 1, 2):
                        inner, offset = int(header[i]), int(header[i + 1])
                        if inner not in self._at:
                            self._in_streams[inner] = (data, first + offset)
        return self._in_streams

    def get(self, num):
        if num in self._cache:
            return self._cache[num]
        if num in self._at:
            value = self._top(num)
        else:
            found = self._object_streams().get(num)
            if not found:
                raise PDFError(f"object {num} is not in the file")
            value, _ = parse(found[0], found[1])
        self._cache[num] = value
        return value

    def resolve(self, value):
        seen = 0
        while isinstance(value, Ref):
            value = self.get(value[0])
            seen += 1
            if seen > 32:
                raise PDFError("a reference that leads to itself")
        return value

    def catalog(self):
        for num in sorted(self._at):
            try:
                value = self.get(num)
            except PDFError:
                continue
            info = value.info if isinstance(value, Stream) else value
            if isinstance(info, dict) and info.get("Type") == "Catalog":
                return info
        for num in sorted(self._object_streams()):
            value = self.get(num)
            if isinstance(value, dict) and value.get("Type") == "Catalog":
                return value
        raise PDFError("no document catalog")

    def pages(self):
        """Each page's dictionary, in order, with inherited resources."""
        out = []

        def walk(node, inherited, depth=0):
            node = self.resolve(node)
            if depth > 32 or not isinstance(node, dict):
                raise PDFError("a page tree this reader cannot follow")
            inherited = dict(inherited)
            for key in ("Resources", "MediaBox"):
                if key in node:
                    inherited[key] = node[key]
            if node.get("Type") == "Pages" or "Kids" in node:
                for kid in self.resolve(node.get("Kids")) or []:
                    walk(kid, inherited, depth + 1)
            else:
                page = dict(inherited)
                page.update(node)
                out.append(page)

        walk(self.catalog().get("Pages"), {})
        return out


# ------------------------------------------------------------------- a page

def _mul(a, b):
    """The product of two PDF matrices ``[a b c d e f]``: *a* then *b*."""
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


_IDENTITY = [1, 0, 0, 1, 0, 0]


def _cmap(data):
    """A ToUnicode CMap: ``({code bytes: text}, code lengths)``."""
    table = {}
    lengths = set()
    for block in re.findall(rb"begincodespacerange(.*?)endcodespacerange", data, re.S):
        for lo in re.findall(rb"<([0-9A-Fa-f]+)>\s*<[0-9A-Fa-f]+>", block):
            lengths.add(len(lo) // 2)

    def text(hexes):
        raw = bytes.fromhex(hexes.decode())
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            table[bytes.fromhex(src.decode())] = text(dst)
            lengths.add(len(src) // 2)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, rest in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", block):
            a, b = int(lo, 16), int(hi, 16)
            width = len(lo) // 2
            lengths.add(width)
            if b - a > 65535:
                continue
            if rest.startswith(b"["):
                targets = re.findall(rb"<([0-9A-Fa-f]*)>", rest)
                for i, dst in enumerate(targets[:b - a + 1]):
                    table[(a + i).to_bytes(width, "big")] = text(dst)
            else:
                base = bytes.fromhex(rest[1:-1].decode())
                for i in range(b - a + 1):
                    last = int.from_bytes(base[-2:], "big") + i if len(base) >= 2 else i
                    dst = base[:-2] + (last & 0xFFFF).to_bytes(2, "big") if len(base) >= 2 \
                        else bytes([(base[0] if base else 0) + i])
                    try:
                        table[(a + i).to_bytes(width, "big")] = dst.decode("utf-16-be")
                    except UnicodeDecodeError:
                        pass
    return table, sorted(lengths or {1}, reverse=True)


class _Font:
    def __init__(self, doc, info):
        info = doc.resolve(info) or {}
        self.two_byte = info.get("Subtype") == "Type0"
        self.table, self.lengths = {}, [2 if self.two_byte else 1]
        unicode = doc.resolve(info.get("ToUnicode"))
        if isinstance(unicode, Stream):
            data, _ = decode(unicode, stop_at_image=False)
            self.table, self.lengths = _cmap(data)

    def text(self, raw):
        if not self.table:
            # A simple font without a map: its codes are WinAnsi's; a
            # two-byte font without one cannot be read, and says nothing.
            return "" if self.two_byte else raw.decode("cp1252", errors="replace")
        out = []
        pos = 0
        while pos < len(raw):
            for n in self.lengths:
                code = raw[pos:pos + n]
                if code in self.table:
                    out.append(self.table[code])
                    pos += n
                    break
            else:
                pos += self.lengths[-1]
        return "".join(out)


def read_page(doc, page, depth=0):
    """``{"text": [(x, y, text, size)], "images": [{"ref", "info", "box"}]}``:
    every piece of text the page shows, at the point its text matrix puts it
    in page space and at the height its font is drawn, and every image it
    draws (``Do``), with the box - ``(x0, y0,
    x1, y1)`` in page space - the current matrix puts it in. Forms are read
    through, to a depth of eight."""
    out = {"text": [], "images": []}
    contents = doc.resolve(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [contents]
    data = b"\n".join(decode(doc.resolve(p), stop_at_image=False)[0]
                      for p in parts if isinstance(doc.resolve(p), Stream))
    _run(doc, data, doc.resolve(page.get("Resources")) or {}, list(_IDENTITY), out, 0)
    return out


def _run(doc, data, resources, ctm, out, depth):
    if depth > 8:
        raise PDFError("forms nested too deep")
    fonts = {}
    xobjects = doc.resolve(resources.get("XObject")) or {}
    font_table = doc.resolve(resources.get("Font")) or {}
    stack = []
    tm = list(_IDENTITY)
    tlm = list(_IDENTITY)
    leading = 0
    font = None
    size = 1
    operands = []
    pos = 0
    n = len(data)
    while True:
        pos = _skip(data, pos)
        if pos >= n:
            break
        value, pos = parse(data, pos, ops=True)
        if not isinstance(value, Op):
            operands.append(value)
            continue
        op = str(value)
        args, operands = operands, []
        if op == "BI":
            # An inline image: skipped to its end (``EI``).
            end = re.compile(rb"\sEI(?=[\s]|$)").search(data, pos)
            pos = end.end() if end else n
            continue
        if op == "q":
            stack.append(list(ctm))
        elif op == "Q":
            ctm = stack.pop() if stack else ctm
        elif op == "cm" and len(args) == 6:
            ctm = _mul([float(a) for a in args], ctm)
        elif op == "BT":
            tm, tlm = list(_IDENTITY), list(_IDENTITY)
        elif op == "Tf" and len(args) == 2:
            name = str(args[0])
            if name not in fonts:
                fonts[name] = _Font(doc, font_table.get(name))
            font, size = fonts[name], args[1]
        elif op == "TL" and args:
            leading = args[0]
        elif op in ("Td", "TD") and len(args) == 2:
            if op == "TD":
                leading = -args[1]
            tlm = _mul([1, 0, 0, 1, args[0], args[1]], tlm)
            tm = list(tlm)
        elif op == "Tm" and len(args) == 6:
            tlm = [float(a) for a in args]
            tm = list(tlm)
        elif op == "T*":
            tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
            tm = list(tlm)
        elif op in ("Tj", "'", '"', "TJ"):
            if op in ("'", '"'):
                tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
                tm = list(tlm)
            shown = args[-1] if args else b""
            pieces = shown if isinstance(shown, list) else [shown]
            text = "".join(font.text(p) if font else p.decode("cp1252", "replace")
                           for p in pieces if isinstance(p, bytes))
            if op == "TJ":
                # A wide gap in a TJ array is a space between words.
                text = ""
                for p in pieces:
                    if isinstance(p, bytes):
                        text += font.text(p) if font else p.decode("cp1252", "replace")
                    elif isinstance(p, (int, float)) and p < -200:
                        text += " "
            at = _mul(tm, ctm)
            if text.strip():
                drawn = abs(float(size)) * (abs(at[3]) or abs(at[2]) or 1)
                out["text"].append((round(at[4], 1), round(at[5], 1), text, round(drawn, 1)))
        elif op == "Do" and args:
            target_ref = xobjects.get(str(args[0]))
            target = doc.resolve(target_ref)
            if not isinstance(target, Stream):
                continue
            kind = target.info.get("Subtype")
            if kind == "Image":
                xs = [ctm[4], ctm[4] + ctm[0], ctm[4] + ctm[2], ctm[4] + ctm[0] + ctm[2]]
                ys = [ctm[5], ctm[5] + ctm[1], ctm[5] + ctm[3], ctm[5] + ctm[1] + ctm[3]]
                out["images"].append({"ref": target_ref if isinstance(target_ref, Ref) else None,
                                      "name": str(args[0]), "stream": target,
                                      "box": (round(min(xs), 1), round(min(ys), 1),
                                              round(max(xs), 1), round(max(ys), 1))})
            elif kind == "Form":
                inner, _ = decode(target, stop_at_image=False)
                matrix = target.info.get("Matrix") or _IDENTITY
                inner_res = doc.resolve(target.info.get("Resources")) or resources
                _run(doc, inner, inner_res, _mul([float(m) for m in matrix], ctm), out,
                     depth + 1)
    return out


def page_text(read):
    """The words of a page read by :func:`read_page`, top to bottom and left
    to right, one line per baseline: what a person reading it sees."""
    lines = {}
    for x, y, text, _size in read["text"]:
        lines.setdefault(round(y), []).append((x, text))
    out = []
    for y in sorted(lines, reverse=True):
        out.append(" ".join(t.strip() for _x, t in sorted(lines[y])))
    return "\n".join(line for line in out if line.strip())
