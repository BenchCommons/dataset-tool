"""Spec 004, R3: XLS and XLSX spreadsheet reader.

Ported from BenchCommons/dataset-names@e7e8405 tests/test_spreadsheet.py (spec 003b R1 and ADR 0005
of dataset-names). Test vectors unchanged; messages in English. The test on the INE adapter samples
stays in dataset-names.
"""

import zipfile
from pathlib import Path

import pytest

from datasettool.sources.adapters import FormatError
from datasettool.sources.spreadsheet import cell_count, rows, sheet_names

FIXTURES = Path(__file__).parent / "fixtures"
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
NS_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xlsx(path: Path, sheets: list[tuple[str, str]], strings: list[str] = (), target="worksheets/sheet{n}.xml",
          order=None) -> Path:
    """Write a minimal XLSX. sheets: (name, sheetData XML); strings: XML of each <si>."""
    order = order or list(range(1, len(sheets) + 1))
    entries = "".join(f'<sheet name="{name}" sheetId="{n}" r:id="rId{n}"/>'
                      for n, (name, _) in zip(order, sheets))
    rels = "".join(f'<Relationship Id="rId{n}" Type="{REL}/worksheet" Target="{target.format(n=n)}"/>'
                   for n in order)
    rels += f'<Relationship Id="rId99" Type="{REL}/sharedStrings" Target="sharedStrings.xml"/>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", f'<?xml version="1.0"?><workbook {NS} {NS_R}><sheets>{entries}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   f'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        z.writestr("xl/sharedStrings.xml",
                   f'<?xml version="1.0"?><sst {NS}>' + "".join(f"<si>{t}</si>" for t in strings) + "</sst>")
        for n, (_, data) in zip(order, sheets):
            z.writestr(f"xl/worksheets/sheet{n}.xml", f'<?xml version="1.0"?><worksheet {NS}><sheetData>{data}</sheetData></worksheet>')
    return path


TYPES_XML = (
    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'
    '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2"><v>590938</v></c><c r="C2" s="5"><v>58.7</v></c></row>'
    '<row r="3"><c r="A3" t="inlineStr"><is><t>IÑIGO</t></is></c><c r="B3" t="n"><v>1E3</v></c></row>'
    '<row r="4"/>'
    '<row r="5"><c r="A5" t="str"><v>JOANA D\'ARC</v></c><c r="B5" t="b"><v>1</v></c>'
    '<c r="C5" s="3"/><c r="D5" t="b"><v>0</v></c><c r="E5" s="2"/></row>'
    '<row r="7"><c r="C7" t="s"><v>4</v></c></row>'
)
TYPES_STRINGS = ["<t>Orden</t>", "<t>Nombre</t>", "<t>Frecuencia</t>", "<t>ANTONIO</t>", "<t>..</t>"]
TYPES_EXPECTED = [
    (1, ["Orden", "Nombre", "Frecuencia"]),
    (2, ["ANTONIO", 590938, 58.7]),
    (3, ["IÑIGO", 1000]),
    (5, ["JOANA D'ARC", True, None, False]),
    (7, [None, None, ".."]),
]


# R3.1 --------------------------------------------------------------------------------------------

def test_sheet_names_in_file_order(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("Hombres", ""), ("Mujeres", ""), ("Notas", "")])
    assert sheet_names(f) == ["Hombres", "Mujeres", "Notas"]


def test_missing_sheet_lists_the_sheets(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("Hombres", ""), ("Mujeres", "")])
    with pytest.raises(FormatError, match=r"a.xlsx: sheet 'Varones' does not exist; sheets: \['Hombres', 'Mujeres'\]"):
        list(rows(f, "Varones"))


def test_excel_row_number_and_column_from_the_reference(tmp_path):
    data = ('<row r="1"><c r="A1"><v>1</v></c></row>'
            '<row r="3"><c r="C3"><v>3</v></c></row>'
            '<row r="10"><c r="AA10"><v>27</v></c></row>')
    f = _xlsx(tmp_path / "a.xlsx", [("X", data)])
    assert list(rows(f, "X")) == [(1, [1]), (3, [None, None, 3]), (10, [None] * 26 + [27])]


# R3.2 --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("content", [
    b"<!DOCTYPE html><html><body>Error 500</body></html>",
    b"",
    b"Orden;Nombre;Frecuencia\n1;ANTONIO;590938\n",
])
def test_content_that_is_not_a_spreadsheet(tmp_path, content):
    f = tmp_path / "nombres.xlsx"
    f.write_bytes(content)
    with pytest.raises(FormatError, match="nombres.xlsx: not an XLS or XLSX spreadsheet"):
        sheet_names(f)
    with pytest.raises(FormatError, match="not an XLS or XLSX spreadsheet"):
        list(rows(f, "Hombres"))


def test_zip_that_is_not_xlsx(tmp_path):
    f = tmp_path / "a.xlsx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("nomes.csv", "a,b\n")
    with pytest.raises(FormatError, match="a.xlsx: ZIP without xl/workbook.xml; not an XLSX"):
        sheet_names(f)


def test_format_from_content_not_extension(tmp_path):
    f = _xlsx(tmp_path / "planilha.xls", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    assert list(rows(f, "X")) == [(1, [1])]


# R3.3 --------------------------------------------------------------------------------------------

def test_xlsx_cell_types(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("Dados", TYPES_XML)], TYPES_STRINGS)
    got = list(rows(f, "Dados"))
    assert got == TYPES_EXPECTED
    assert [type(v) for v in got[1][1]] == [str, int, float]
    assert type(got[2][1][1]) is int


def test_empty_rows_skipped_and_trailing_none_cut(tmp_path):
    data = ('<row r="1"><c r="A1" s="1"/><c r="B1" s="1"/></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t></t></is></c><c r="B2"><v>2</v></c><c r="C2" s="1"/></row>'
            '<row r="3"><c r="A3"><v>3</v></c><c r="B3" t="s"/></row>')
    f = _xlsx(tmp_path / "a.xlsx", [("X", data)])
    assert list(rows(f, "X")) == [(2, ["", 2]), (3, [3])]


def test_formula_error_names_sheet_and_cell(tmp_path):
    data = '<row r="1"><c r="A1"><v>1</v></c></row><row r="2"><c r="B2" t="e"><v>#N/A</v></c></row>'
    f = _xlsx(tmp_path / "a.xlsx", [("Hombres", data)])
    with pytest.raises(FormatError, match=r"a.xlsx, sheet 'Hombres', cell B2: formula error '#N/A'"):
        list(rows(f, "Hombres"))


def test_unknown_cell_type(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="1"><c r="A1" t="d"><v>2025-01-01</v></c></row>')])
    with pytest.raises(FormatError, match="cell A1: unknown type 'd'"):
        list(rows(f, "X"))


def test_invalid_number(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="1"><c r="A1"><v>doze</v></c></row>')])
    with pytest.raises(FormatError, match="cell A1: invalid number 'doze'"):
        list(rows(f, "X"))


# R3.4 --------------------------------------------------------------------------------------------

def test_shared_string_with_formatting_and_rph(tmp_path):
    strings = [
        "<r><rPr><b/></rPr><t>MARIA </t></r><r><t xml:space=\"preserve\">BEGOÑA</t></r>",
        "<t>東京</t><rPh sb=\"0\" eb=\"2\"><t>トウキョウ</t></rPh>",
    ]
    data = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
    f = _xlsx(tmp_path / "a.xlsx", [("X", data)], strings)
    assert list(rows(f, "X")) == [(1, ["MARIA BEGOÑA", "東京"])]


def test_shared_string_index_outside_the_table(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="1"><c r="A1" t="s"><v>7</v></c></row>')], ["<t>a</t>"])
    with pytest.raises(FormatError, match="cell A1: shared string 7 outside the table of 1"):
        list(rows(f, "X"))


@pytest.mark.parametrize("target", ["worksheets/sheet{n}.xml", "/xl/worksheets/sheet{n}.xml"])
def test_sheet_found_through_the_relationship_target(tmp_path, target):
    sheets = [("Primeira", '<row r="1"><c r="A1"><v>2</v></c></row>'),
              ("Segunda", '<row r="1"><c r="A1"><v>1</v></c></row>')]
    f = _xlsx(tmp_path / "a.xlsx", sheets, target=target, order=[2, 1])
    assert sheet_names(f) == ["Primeira", "Segunda"]
    assert list(rows(f, "Primeira")) == [(1, [2])]
    assert list(rows(f, "Segunda")) == [(1, [1])]


# R3.6 --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    (590938, 590938), (0, 0), (" 20 ", 20), ("..", None), (None, None),
])
def test_cell_count(value, expected):
    assert cell_count(value, {"..", ""}) == expected


@pytest.mark.parametrize("value, fragment", [
    (20.5, "count 20.5 is not an integer"),
    (-1, "count -1 is negative"),
    (True, "count True is not a number"),
    ("<20", r"count '<20' is neither an integer nor a known marker \['..'\]"),
    (None, "count empty"),
])
def test_cell_count_refuses(value, fragment):
    with pytest.raises(FormatError, match=fragment):
        cell_count(value, {".."})


def test_cell_count_names_the_field():
    with pytest.raises(FormatError, match="Frecuencia 1.5 is not an integer"):
        cell_count(1.5, field="Frecuencia")


# R3.3 and R3.5: XLS through xlrd -----------------------------------------------------------------

TYPES_XLS = FIXTURES / "spreadsheets" / "types.xls"


def test_xls_cell_types():
    assert sheet_names(TYPES_XLS) == ["Dados", "Erros"]
    got = list(rows(TYPES_XLS, "Dados"))
    assert got == TYPES_EXPECTED
    assert [type(v) for v in got[1][1]] == [str, int, float]
    assert [type(v) for v in got[3][1]] == [str, bool, type(None), bool]


def test_xls_formula_error():
    with pytest.raises(FormatError, match=r"types.xls, sheet 'Erros', cell B2: formula error '#N/A'"):
        list(rows(TYPES_XLS, "Erros"))


def test_same_values_in_both_formats(tmp_path):
    xlsx = _xlsx(tmp_path / "types.xlsx", [("Dados", TYPES_XML)], TYPES_STRINGS)
    assert list(rows(xlsx, "Dados")) == list(rows(TYPES_XLS, "Dados"))


def test_missing_sheet_xls():
    with pytest.raises(FormatError, match=r"types.xls: sheet 'Notas' does not exist; sheets: \['Dados', 'Erros'\]"):
        list(rows(TYPES_XLS, "Notas"))


def test_corrupt_xls(tmp_path):
    f = tmp_path / "quebrado.xls"
    f.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
    with pytest.raises(FormatError, match="quebrado.xls: unreadable XLS"):
        sheet_names(f)


def test_xlrd_pinned():
    import tomllib
    project = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    assert "xlrd==2.0.2" in project["project"]["dependencies"]


# Malformed inputs and disproportionate ZIPs become FormatError (dataset-names PR #27 review) ------

def test_sheet_member_missing_from_the_zip(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", "")], target="worksheets/nao_existe{n}.xml")
    with pytest.raises(FormatError, match=r"a.xlsx: sheet 'X' points to xl/worksheets/nao_existe1.xml, missing from the ZIP"):
        list(rows(f, "X"))


def test_shared_string_index_not_an_integer(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="1"><c r="A1" t="s"><v>abc</v></c></row>')], ["<t>a</t>"])
    with pytest.raises(FormatError, match="cell A1: shared string index 'abc' is not an integer"):
        list(rows(f, "X"))


@pytest.mark.parametrize("ref, fragment", [
    ("XFE1", "cell XFE1: column beyond XFD"),
    ("1A", "invalid cell reference '1A'"),
    ("a1", "invalid cell reference 'a1'"),
])
def test_invalid_cell_reference(tmp_path, ref, fragment):
    f = _xlsx(tmp_path / "a.xlsx", [("X", f'<row r="1"><c r="{ref}"><v>1</v></c></row>')])
    with pytest.raises(FormatError, match=fragment):
        list(rows(f, "X"))


def test_invalid_row_number(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="x"><c r="A1"><v>1</v></c></row>')])
    with pytest.raises(FormatError, match="invalid row 'x'"):
        list(rows(f, "X"))


def test_zip_with_disproportionate_compression_ratio(tmp_path):
    padding = " " * 3_000_000
    f = _xlsx(tmp_path / "a.xlsx", [("X", f'<row r="1"><c r="A1"><v>1</v></c></row>{padding}')])
    with pytest.raises(FormatError, match=r"a.xlsx: member xl/worksheets/sheet1.xml inflates to 3\d{6} bytes, .*ratio"):
        list(rows(f, "X"))


def test_zip_with_member_too_large(tmp_path, monkeypatch):
    import datasettool.sources.spreadsheet as spreadsheet
    monkeypatch.setattr(spreadsheet, "_MAX_MEMBER", 100)
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    with pytest.raises(FormatError, match=r"a.xlsx: member xl/workbook.xml inflates to \d+ bytes, above the limit of 100"):
        sheet_names(f)


def test_rows_read_leave_the_tree(tmp_path):
    """Flat memory: a sheet with many rows does not accumulate <row> elements already read."""
    import datasettool.sources.spreadsheet as spreadsheet
    data = "".join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, 2001))
    f = _xlsx(tmp_path / "a.xlsx", [("X", data)])
    seen = []
    original = spreadsheet._events

    def spy(*args, **kwargs):
        for event, el in original(*args, **kwargs):
            yield event, el
            if event == "end" and el.tag.endswith("sheetData"):
                seen.append(len(el))

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(spreadsheet, "_events", spy)
    try:
        assert sum(1 for _ in rows(f, "X")) == 2000
    finally:
        monkeypatch.undo()
    assert seen == [0]


# Defence in depth against DTDs (dataset-names ADR 0005) ------------------------------------------

def _rewrite(src: Path, dest: Path, member: str, content: str) -> Path:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info.filename, content if info.filename == member else zin.read(info.filename))
    return dest


BILLION_LAUGHS = (
    '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
    '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
    '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
    f'<worksheet {NS}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>&lol3;</t></is></c></row></sheetData></worksheet>'
)
ROOTS = {"xl/workbook.xml": f"<workbook {NS} {NS_R}/>", "xl/_rels/workbook.xml.rels": "<Relationships/>",
         "xl/sharedStrings.xml": f"<sst {NS}/>", "xl/worksheets/sheet1.xml": f"<worksheet {NS}/>"}
OPERATIONS = [
    ("xl/workbook.xml", lambda a: sheet_names(a)),
    ("xl/_rels/workbook.xml.rels", lambda a: sheet_names(a)),
    ("xl/sharedStrings.xml", lambda a: list(rows(a, "X"))),
    ("xl/worksheets/sheet1.xml", lambda a: list(rows(a, "X"))),
]


@pytest.mark.parametrize("member, operation", OPERATIONS)
@pytest.mark.parametrize("prolog", [
    '<!DOCTYPE x [<!ENTITY a "b">]>',
    '<!doctype x>',
    '<!-- c --><!ENTITY a "b">',
])
def test_dtd_in_the_prologue_is_refused(tmp_path, member, operation, prolog):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    f = _rewrite(base, tmp_path / "a.xlsx", member, f'<?xml version="1.0"?>{prolog}{ROOTS[member]}')
    with pytest.raises(FormatError, match=rf"a\.xlsx: member {member} has a DTD"):
        operation(f)


def test_billion_laughs_fails_on_the_dtd_check(tmp_path):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    f = _rewrite(base, tmp_path / "a.xlsx", "xl/worksheets/sheet1.xml", BILLION_LAUGHS)
    with pytest.raises(FormatError, match=r"a\.xlsx: member xl/worksheets/sheet1\.xml has a DTD"):
        list(rows(f, "X"))


def test_doctype_inside_a_comment_is_not_a_dtd(tmp_path):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    content = f'<?xml version="1.0"?><!-- <!DOCTYPE x> --><worksheet {NS}><sheetData><row r="1"><c r="A1"><v>7</v></c></row></sheetData></worksheet>'
    f = _rewrite(base, tmp_path / "a.xlsx", "xl/worksheets/sheet1.xml", content)
    assert list(rows(f, "X")) == [(1, [7])]


def test_doctype_text_after_the_root_is_not_a_dtd(tmp_path):
    f = _xlsx(tmp_path / "a.xlsx", [("X", '<row r="1"><c r="A1" t="inlineStr"><is><t>&lt;!DOCTYPE</t></is></c></row>')])
    assert list(rows(f, "X")) == [(1, ["<!DOCTYPE"])]


def test_huge_prologue_is_refused(tmp_path):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    content = '<?xml version="1.0"?><!--' + "x" * 70_000 + f'--><worksheet {NS}/>'
    f = _rewrite(base, tmp_path / "a.xlsx", "xl/worksheets/sheet1.xml", content)
    with pytest.raises(FormatError, match=r"a\.xlsx: member xl/worksheets/sheet1\.xml has a prologue above 65536 bytes"):
        list(rows(f, "X"))


def test_normal_xlsx_with_bom_is_still_read(tmp_path):
    base = _xlsx(tmp_path / "base.xlsx", [("X", "")])
    content = '﻿<?xml version="1.0" encoding="UTF-8"?>\n' + f'<worksheet {NS}><sheetData><row r="1"><c r="A1"><v>3</v></c></row></sheetData></worksheet>'
    f = _rewrite(base, tmp_path / "a.xlsx", "xl/worksheets/sheet1.xml", content)
    assert list(rows(f, "X")) == [(1, [3])]


def test_300_thousand_rows_streamed_with_flat_memory(tmp_path):
    import tracemalloc
    n = 300_000
    data = "".join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c><c r="B{i}" t="inlineStr"><is><t>NOME{i}</t></is></c></row>'
                   for i in range(1, n + 1))
    f = _xlsx(tmp_path / "a.xlsx", [("X", data)])
    del data
    tracemalloc.start()
    try:
        total = last = 0
        for number, values in rows(f, "X"):
            total += 1
            last = values[0]
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (total, last) == (n, n)
    assert peak < 5 * 1024 * 1024, f"peak of {peak} bytes: the sheet is not being streamed"


@pytest.mark.parametrize("member, operation", OPERATIONS)
@pytest.mark.parametrize("prolog", [
    '<!DOCTYPE l [<!ENTITY a "AAAA"><!ENTITY b "&a;&a;">]>',
    '<!-- c --><!DOCTYPE l [<!ENTITY a "AAAA">]>',
])
def test_dtd_after_utf8_bom_is_refused(tmp_path, member, operation, prolog):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    f = _rewrite(base, tmp_path / "a.xlsx", member, f'﻿<?xml version="1.0"?>{prolog}{ROOTS[member]}')
    with pytest.raises(FormatError, match=rf"a\.xlsx: member {member} has a DTD"):
        operation(f)


# DTD in encodings that escape a UTF-8 pre-scan (parser differential) --------------------------------
# Ported from BenchCommons/dataset-names@eaaa4d1 (PR #39) tests/test_spreadsheet.py.

_DTD = '<!DOCTYPE x [<!ENTITY a "b">]>'


def _rewrite_bytes(src: Path, dest: Path, member: str, data: bytes) -> Path:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info.filename, data if info.filename == member else zin.read(info.filename))
    return dest


@pytest.mark.parametrize("member, operation", OPERATIONS)
@pytest.mark.parametrize("declared, codec", [
    ("cp037", "cp037"),
    ("utf-32", "utf-32"),
    ("UTF-32LE", "utf-32-le"),
    ("UTF-32BE", "utf-32-be"),
    ("latin-1", "latin-1"),
    ("iso-8859-1", "ascii"),
    ("windows-1252", "cp1252"),
    ("us-ascii", "ascii"),
])
def test_dtd_in_a_non_utf_encoding_is_refused(tmp_path, member, operation, declared, codec):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    text = f'<?xml version="1.0" encoding="{declared}"?>{_DTD}{ROOTS[member]}'
    f = _rewrite_bytes(base, tmp_path / "a.xlsx", member, text.encode(codec))
    with pytest.raises(FormatError, match=rf"a\.xlsx: member {member} "):
        operation(f)


@pytest.mark.parametrize("member, operation", OPERATIONS)
@pytest.mark.parametrize("data", [
    '<?xml version="1.0"?>{dtd}{raiz}'.encode("cp037"),  # no declaration: EBCDIC is not UTF-8
    '<?xml version="1.0"?>{dtd}{raiz}'.encode("utf-32-le"),
    '<?xml version="1.0"?>{dtd}{raiz}'.encode("utf-32-be"),
    b"\xff\xfe\x00\x00<\x00\x00\x00",
    b"\x00\x00\xfe\xff\x00\x00\x00<",
    b'<?xml version="1.0"?>\xe9{dtd}{raiz}',  # invalid UTF-8
], ids=["ebcdic", "utf32le", "utf32be", "bom-utf32le", "bom-utf32be", "invalid-utf8"])
def test_prefix_that_is_neither_utf8_nor_utf16_is_refused(tmp_path, member, operation, data):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    f = _rewrite_bytes(base, tmp_path / "a.xlsx", member, data)
    with pytest.raises(FormatError, match=rf"a\.xlsx: member {member} "):
        operation(f)


@pytest.mark.parametrize("member, operation", OPERATIONS)
@pytest.mark.parametrize("codec, declared", [
    ("utf-8", "UTF-8"), ("utf-8", "utf8"), ("utf-8", None), ("utf-16", "UTF-16"), ("utf-16", "utf16"),
])
def test_dtd_in_utf8_and_utf16_with_a_valid_declaration_is_still_refused(tmp_path, member, operation, codec, declared):
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    enc = f' encoding="{declared}"' if declared else ""
    text = f'<?xml version="1.0"{enc}?>{_DTD}{ROOTS[member]}'
    f = _rewrite_bytes(base, tmp_path / "a.xlsx", member, text.encode(codec))
    with pytest.raises(FormatError, match=rf"a\.xlsx: member {member} has a DTD"):
        operation(f)


@pytest.mark.parametrize("codec, declared", [
    ("utf-8", "UTF-8"), ("utf-8", "utf-8"), ("utf-16", "UTF-16"), ("utf-16-le", None)])
def test_normal_xlsx_in_utf8_or_utf16_is_read(tmp_path, codec, declared):
    base = _xlsx(tmp_path / "base.xlsx", [("X", "")])
    enc = f' encoding="{declared}"' if declared else ""
    text = (f'<?xml version="1.0"{enc}?><worksheet {NS}><sheetData><row r="1"><c r="A1" t="inlineStr">'
            '<is><t>IÑIGO</t></is></c></row></sheetData></worksheet>')
    f = _rewrite_bytes(base, tmp_path / "a.xlsx", "xl/worksheets/sheet1.xml", text.encode(codec))
    assert list(rows(f, "X")) == [(1, ["IÑIGO"])]


@pytest.mark.parametrize("member, operation", OPERATIONS)
def test_the_parser_refuses_a_dtd_even_without_the_prescan(tmp_path, monkeypatch, member, operation):
    """Defence in depth: with the pre-scan switched off, the expat handlers still refuse DTDs."""
    import datasettool.sources.spreadsheet as spreadsheet
    monkeypatch.setattr(spreadsheet, "_prologue", lambda data, where="": "root")
    base = _xlsx(tmp_path / "base.xlsx", [("X", '<row r="1"><c r="A1"><v>1</v></c></row>')])
    for dtd in (_DTD, BILLION_LAUGHS.split("<worksheet")[0].removeprefix('<?xml version="1.0"?>')):
        f = _rewrite(base, tmp_path / "a.xlsx", member, f'<?xml version="1.0"?>{dtd}{ROOTS[member]}')
        with pytest.raises(FormatError, match=rf"a\.xlsx: member {member} has a DTD"):
            operation(f)


# Corrupt ZIP members become FormatError (review of PR #7) ------------------------------------------

def _corrupt(path: Path, old: bytes, new: bytes) -> Path:
    data = path.read_bytes()
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, new))
    return path


def _stored_xlsx(path: Path) -> Path:
    src = _xlsx(path.with_name("deflated.xlsx"), [("X", '<row r="1"><c r="A1"><v>12345</v></c></row>')])
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            zout.writestr(info.filename, zin.read(info.filename))
    return path


def test_bad_crc_in_a_sheet_is_a_format_error(tmp_path):
    f = _corrupt(_stored_xlsx(tmp_path / "a.xlsx"), b"<v>12345</v>", b"<v>54321</v>")
    with pytest.raises(FormatError, match=r"a\.xlsx: member xl/worksheets/sheet1\.xml is corrupt: .*CRC"):
        list(rows(f, "X"))


def test_bad_crc_in_the_workbook_is_a_format_error(tmp_path):
    f = _corrupt(_stored_xlsx(tmp_path / "a.xlsx"), b'sheetId="1"', b'sheetId="2"')
    with pytest.raises(FormatError, match=r"a\.xlsx: member xl/workbook\.xml is corrupt"):
        sheet_names(f)


def test_corrupt_deflate_stream_is_a_format_error(tmp_path):
    padding = "".join(f'<row r="{i}"><c r="A{i}"><v>{i * 7919 % 100003}</v></c></row>' for i in range(1, 3000))
    f = _xlsx(tmp_path / "a.xlsx", [("X", padding)])
    with zipfile.ZipFile(f) as z:
        info = z.getinfo("xl/worksheets/sheet1.xml")
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    data = bytearray(f.read_bytes())
    for k in range(start + 50, start + 250):
        data[k] ^= 0xFF
    f.write_bytes(bytes(data))
    with pytest.raises(FormatError, match=r"a\.xlsx: member xl/worksheets/sheet1\.xml is corrupt"):
        list(rows(f, "X"))
