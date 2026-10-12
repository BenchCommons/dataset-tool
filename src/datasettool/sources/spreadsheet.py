"""XLS and XLSX reader for source adapters (spec 004, R3; ADR 0005).

The format is detected from the first bytes. XLSX is streamed with the standard library;
XLS is read with xlrd. Both return values of the same types: str, int, float, bool or None.

Ported from BenchCommons/dataset-names@e7e8405 src/namescommons/spreadsheet.py.
"""

import io
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

import xlrd

from datasettool.sources.adapters import FormatError, parse_count

_ZIP = b"PK\x03\x04"
_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_DOC = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_REL_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_ROW, _C, _V, _IS, _T, _R, _SI, _SHEET, _SHEET_DATA = (
    _MAIN + n for n in ("row", "c", "v", "is", "t", "r", "si", "sheet", "sheetData")
)
_REF = re.compile(r"([A-Z]{1,3})([0-9]+)")
_MAX_COLUMNS = 16384  # XFD, Excel's last column
# Guard against disproportionate ZIPs: a member above 1 GiB, or above 1 MiB with a ratio above 100:1.
_MAX_MEMBER = 1 << 30
_MAX_RATIO = 100
_MIN_BYTES_RATIO = 1 << 20
_INTEGER = re.compile(r"-?[0-9]+")
# Defence in depth (ADR 0005): an XML member with a DTD is refused before it reaches the parser.
_MAX_PROLOGUE = 1 << 16
_SPACE = re.compile(r"[\s﻿]*")


def _format(path: Path) -> str:
    with open(path, "rb") as fh:
        start = fh.read(8)
    if start.startswith(_ZIP):
        return "xlsx"
    if start == _OLE2:
        return "xls"
    raise FormatError(f"{path.name}: not an XLS or XLSX spreadsheet (starts with {start!r})")


def sheet_names(path: str | Path) -> list[str]:
    """Sheets in file order."""
    path = Path(path)
    if _format(path) == "xls":
        return _xls_sheet_names(path)
    with _open_zip(path) as z:
        return [name for name, _ in _xlsx_sheets(z, path)]


def rows(path: str | Path, sheet: str) -> Iterator[tuple[int, list]]:
    """(Excel row number, values by column) of each non-empty row of the sheet."""
    path = Path(path)
    if _format(path) == "xls":
        yield from _xls_rows(path, sheet)
    else:
        yield from _xlsx_rows(path, sheet)


def cell_count(value: object, missing: Iterable[str] = (), field: str = "count") -> int | None:
    """Count in a cell (R3.6). A marker from `missing` becomes None; anything else is FormatError."""
    markers = set(missing)
    if value is None:
        if "" in markers:
            return None
        raise FormatError(f"{field} empty; expected an integer or a known marker {sorted(markers)}")
    if isinstance(value, bool):
        raise FormatError(f"{field} {value!r} is not a number")
    if isinstance(value, float):
        if not value.is_integer():
            raise FormatError(f"{field} {value!r} is not an integer")
        value = int(value)
    if isinstance(value, int):
        if value < 0:
            raise FormatError(f"{field} {value!r} is negative")
        return value
    if isinstance(value, str):
        return parse_count(value, markers, field)
    raise FormatError(f"{field} {value!r} has unexpected type {type(value).__name__}")


def _drop_trailing_none(values: list) -> list:
    while values and values[-1] is None:
        values.pop()
    return values


# XLSX ---------------------------------------------------------------------------------------------

def _open_zip(path: Path) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise FormatError(f"{path.name}: corrupt XLSX: {e}") from None
    if "xl/workbook.xml" not in z.namelist():
        z.close()
        raise FormatError(f"{path.name}: ZIP without xl/workbook.xml; not an XLSX")
    return z


def _member(z: zipfile.ZipFile, name: str, path: Path):
    """Open a ZIP member after checking its declared uncompressed size."""
    try:
        info = z.getinfo(name)
    except KeyError:
        raise FormatError(f"{path.name}: member {name} missing from the ZIP") from None
    size, compressed = info.file_size, max(info.compress_size, 1)
    if size > _MAX_MEMBER:
        raise FormatError(f"{path.name}: member {name} inflates to {size} bytes, above the limit of {_MAX_MEMBER}")
    if size > _MIN_BYTES_RATIO and size / compressed > _MAX_RATIO:
        raise FormatError(f"{path.name}: member {name} inflates to {size} bytes, "
                          f"compression ratio {size // compressed}:1 above {_MAX_RATIO}:1")
    return _NoDtd(z.open(info), name, path)


class _NoDtd(io.RawIOBase):
    """Stream of an XML member that refuses a DTD in the prologue, then passes the bytes to the parser.

    It reads at most 64 KiB, up to the first element tag, and hands that prefix to the parser before
    the rest of the stream; streaming of large sheets is unchanged.
    """

    def __init__(self, fh, name: str, path: Path):
        super().__init__()
        self._fh = fh
        prefix = b""
        while True:
            part = fh.read(4096)
            prefix += part
            decision = _prologue(prefix)
            if decision == "dtd":
                fh.close()
                raise FormatError(f"{path.name}: member {name} has a DTD (DOCTYPE or ENTITY); refused")
            if decision == "root" or not part:
                break
            if len(prefix) >= _MAX_PROLOGUE:
                fh.close()
                raise FormatError(f"{path.name}: member {name} has a prologue above {_MAX_PROLOGUE} bytes without a root element")
        self._prefix = memoryview(prefix)

    def readable(self) -> bool:
        return True

    def readinto(self, buf) -> int:
        if self._prefix:
            n = min(len(buf), len(self._prefix))
            buf[:n] = self._prefix[:n]
            self._prefix = self._prefix[n:]
            return n
        return self._fh.readinto(buf)

    def close(self) -> None:
        self._fh.close()
        super().close()


def _prologue(data: bytes) -> str:
    """'dtd' if DOCTYPE/ENTITY comes before the root element, 'root' if the root has started, else 'more'."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = data.decode("utf-16", errors="replace")
    elif b"\x00" in data[:4]:
        text = data.decode("utf-16-le" if data[1:2] == b"\x00" else "utf-16-be", errors="replace")
    else:
        # UTF-8 (optional BOM). UTF-32 and EBCDIC are not inspected and fail in expat.
        text = data.removeprefix(b"\xef\xbb\xbf").decode("utf-8", errors="replace")
    i = 0
    while True:
        i = _SPACE.match(text, i).end()
        if i >= len(text):
            return "more"
        if text.startswith("<?", i):
            end, skip = text.find("?>", i), 2
        elif text.startswith("<!--", i):
            end, skip = text.find("-->", i), 3
        elif text[i:i + 9].upper() == "<!DOCTYPE" or text[i:i + 8].upper() == "<!ENTITY":
            return "dtd"
        elif len(text) - i < 9 and any(mark.startswith(text[i:].upper()) for mark in ("<!DOCTYPE", "<!ENTITY", "<!--")):
            return "more"  # prefix too short to decide
        else:
            return "root"  # root element (or garbage, which the parser describes)
        if end < 0:
            return "more"
        i = end + skip


def _xlsx_sheets(z: zipfile.ZipFile, path: Path) -> list[tuple[str, str]]:
    """(name, ZIP member) of each sheet, in the order of xl/workbook.xml."""
    try:
        with _member(z, "xl/workbook.xml", path) as fh:
            book = ET.parse(fh).getroot()
        with _member(z, "xl/_rels/workbook.xml.rels", path) as fh:
            rels = ET.parse(fh).getroot()
    except ET.ParseError as e:
        raise FormatError(f"{path.name}: unreadable XLSX workbook: {e}") from None
    targets = {r.get("Id"): r.get("Target", "") for r in rels.iter(_REL_PKG + "Relationship")}
    sheets = []
    for sheet in book.iter(_SHEET):
        target = targets.get(sheet.get(_REL_DOC + "id"))
        if target is None:
            raise FormatError(f"{path.name}: sheet {sheet.get('name')!r} has no relationship in workbook.xml.rels")
        member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        sheets.append((sheet.get("name"), member))
    return sheets


def _text(element: ET.Element) -> str:
    """Text of <si> or <is>: direct <t> and those of <r> runs; the phonetic reading <rPh> is left out."""
    parts = []
    for child in element:
        if child.tag == _T:
            parts.append(child.text or "")
        elif child.tag == _R:
            parts.extend(t.text or "" for t in child.iter(_T))
    return "".join(parts)


def _shared_strings(z: zipfile.ZipFile, path: Path) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    strings = []
    with _member(z, "xl/sharedStrings.xml", path) as fh:
        try:
            for _, el in ET.iterparse(fh):
                if el.tag == _SI:
                    strings.append(_text(el))
                    el.clear()
        except ET.ParseError as e:
            raise FormatError(f"{path.name}: unreadable sharedStrings.xml: {e}") from None
    return strings


def _column(ref: str, where: str) -> int:
    """Column index (A = 0) of a reference such as 'C7'."""
    m = _REF.fullmatch(ref)
    if not m:
        raise FormatError(f"{where}: invalid cell reference {ref!r}")
    n = 0
    for letter in m.group(1):
        n = n * 26 + ord(letter) - ord("A") + 1
    if n > _MAX_COLUMNS:
        raise FormatError(f"{where}, cell {ref}: column beyond XFD")
    return n - 1


def _number(text: str, where: str) -> int | float:
    text = text.strip()
    if _INTEGER.fullmatch(text):
        return int(text)
    try:
        value = float(text)
    except ValueError:
        raise FormatError(f"{where}: invalid number {text!r}") from None
    return int(value) if value.is_integer() else value


def _value(c: ET.Element, strings: list[str], where: str):
    kind = c.get("t", "n")
    v = c.find(_V)
    if kind == "inlineStr":
        block = c.find(_IS)
        return None if block is None else _text(block)
    if v is None or v.text is None:
        return "" if kind == "str" and v is not None else None
    if kind == "s":
        try:
            index = int(v.text)
        except ValueError:
            raise FormatError(f"{where}: shared string index {v.text!r} is not an integer") from None
        if not 0 <= index < len(strings):
            raise FormatError(f"{where}: shared string {index} outside the table of {len(strings)}")
        return strings[index]
    if kind == "str":
        return v.text
    if kind == "n":
        return _number(v.text, where)
    if kind == "b":
        return v.text.strip() == "1"
    if kind == "e":
        raise FormatError(f"{where}: formula error {v.text!r}")
    raise FormatError(f"{where}: unknown type {kind!r}")


def _xlsx_rows(path: Path, sheet: str) -> Iterator[tuple[int, list]]:
    with _open_zip(path) as z:
        sheets = _xlsx_sheets(z, path)
        member = dict(sheets).get(sheet)
        if member is None:
            raise FormatError(f"{path.name}: sheet {sheet!r} does not exist; sheets: {[n for n, _ in sheets]}")
        strings = _shared_strings(z, path)
        prefix = f"{path.name}, sheet {sheet!r}"
        if member not in z.namelist():
            raise FormatError(f"{path.name}: sheet {sheet!r} points to {member}, missing from the ZIP")
        with _member(z, member, path) as fh:
            number, parent = 0, None
            try:
                for event, el in ET.iterparse(fh, events=("start", "end")):
                    if event == "start":
                        if el.tag == _SHEET_DATA:
                            parent = el
                        continue
                    if el.tag != _ROW:
                        continue
                    r = el.get("r")
                    if r is None:
                        number += 1
                    elif r.isdigit():
                        number = int(r)
                    else:
                        raise FormatError(f"{prefix}: invalid row {r!r}")
                    values: list = []
                    for c in el.iter(_C):
                        ref = c.get("r")
                        position = len(values) if ref is None else _column(ref, prefix)
                        values.extend([None] * (position - len(values) + 1))
                        values[position] = _value(c, strings, f"{prefix}, cell {ref or position}")
                    # Remove the row just read from the tree: memory stays flat over the whole sheet.
                    el.clear()
                    if parent is not None:
                        parent.remove(el)
                    if _drop_trailing_none(values):
                        yield number, values
            except ET.ParseError as e:
                raise FormatError(f"{prefix}: unreadable XML: {e}") from None


# XLS ----------------------------------------------------------------------------------------------

def _xls_open(path: Path):
    try:
        return xlrd.open_workbook(path, on_demand=True)
    except Exception as e:  # xlrd raises XLRDError, CompDocError, AssertionError and others
        raise FormatError(f"{path.name}: unreadable XLS: {type(e).__name__}: {e}") from None


def _xls_sheet_names(path: Path) -> list[str]:
    book = _xls_open(path)
    try:
        return book.sheet_names()
    finally:
        book.release_resources()


def _xls_value(cell, where: str):
    kind = cell.ctype
    if kind in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if kind == xlrd.XL_CELL_TEXT:
        return cell.value
    if kind in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_DATE):
        value = float(cell.value)
        return int(value) if value.is_integer() else value
    if kind == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if kind == xlrd.XL_CELL_ERROR:
        text = xlrd.error_text_from_code.get(cell.value, f"code {cell.value}")
        raise FormatError(f"{where}: formula error {text!r}")
    raise FormatError(f"{where}: unknown cell type {kind}")


def _xls_rows(path: Path, sheet: str) -> Iterator[tuple[int, list]]:
    book = _xls_open(path)
    try:
        if sheet not in book.sheet_names():
            raise FormatError(f"{path.name}: sheet {sheet!r} does not exist; sheets: {book.sheet_names()}")
        try:
            ws = book.sheet_by_name(sheet)
        except Exception as e:
            raise FormatError(f"{path.name}, sheet {sheet!r}: unreadable XLS: {type(e).__name__}: {e}") from None
        prefix = f"{path.name}, sheet {sheet!r}"
        for i in range(ws.nrows):
            values = [
                _xls_value(cell, f"{prefix}, cell {xlrd.cellname(i, j)}")
                for j, cell in enumerate(ws.row(i))
            ]
            if _drop_trailing_none(values):
                yield i + 1, values
    finally:
        book.release_resources()
