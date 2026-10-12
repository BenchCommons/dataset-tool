"""Spec 004, R4: adapter base.

Ported from BenchCommons/dataset-names@e7e8405 tests/test_adapters.py and
tests/test_contrato_adaptador.py (spec 002 R1, spec 003 R2.2 and R2.6 of dataset-names).
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from datasettool.sources.adapters import (
    AdapterError, FormatError, Resource, SourceFiles, check_adapter, is_http_url, load_adapter,
    module_name, parse_code, parse_count,
)


def _parse(files):
    return iter(())


def _adapter(**fields):
    base = dict(SOURCE_ID="x", RESOURCES=[Resource("https://example.org/a.csv", "a.csv")], parse=_parse)
    return SimpleNamespace(**{**base, **fields})


def test_module_name():
    assert module_name("us-ssa-births") == "us_ssa_births"


def test_loads_the_example_adapter():
    mod = load_adapter("example", "example_adapters")
    assert mod.SOURCE_ID == "example"
    assert [r.filename for r in mod.RESOURCES] == ["given.csv", "family.csv"]


def test_dataset_defines_its_own_record_type(tmp_path):
    mod = load_adapter("example", "example_adapters")
    (tmp_path / "given.csv").write_text("name\nMARIA\n", encoding="utf-8")
    (tmp_path / "family.csv").write_text("name\nSILVA\n", encoding="utf-8")
    files = SourceFiles({r.filename: tmp_path / r.filename for r in mod.RESOURCES})
    assert list(mod.parse(files)) == [mod.Row("MARIA", "given"), mod.Row("SILVA", "family")]


def test_missing_adapter():
    with pytest.raises(AdapterError, match="example_adapters.missing_adapter"):
        load_adapter("missing-adapter", "example_adapters")


def test_valid_adapter():
    check_adapter(_adapter(), "x")


@pytest.mark.parametrize("fields, fragment", [
    ({"SOURCE_ID": "y"}, "SOURCE_ID 'y' differs"),
    ({"RESOURCES": []}, "RESOURCES"),
    ({"RESOURCES": [("https://example.org/a.csv", "a.csv")]}, "RESOURCES"),
    ({"RESOURCES": [Resource("ftp://example.org/a.csv", "a.csv")]}, "http or https"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "../a.csv")]}, "filename"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "a.csv.meta.json")]}, "filename"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "a.csv"),
                    Resource("https://example.org/b.csv", "a.csv")]}, "repeated"),
    ({"parse": None}, "parse"),
    ({"RESOURCES": [Resource("http://[::1/a.csv", "a.csv")]}, "'x': url 'http://\\[::1/a.csv' must use http or https"),
    ({"RESOURCES": [Resource(" https://example.org/a.csv", "a.csv")]}, "http or https"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "")]}, "filename"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "a.csv.part")]}, "filename"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "a\x00.csv")]}, "filename"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "a\n.csv")]}, "filename"),
    ({"RESOURCES": [Resource("https://example.org/a.csv", "a\x7f.csv")]}, "filename"),
])
def test_invalid_adapter(fields, fragment):
    with pytest.raises(AdapterError, match=fragment):
        check_adapter(_adapter(**fields), "x")


def test_adapter_without_attribute():
    with pytest.raises(AdapterError, match="SOURCE_ID"):
        check_adapter(SimpleNamespace(RESOURCES=[], parse=_parse), "x")


# Optional functions of a dataset's own protocol (dataset-names: links) ------------------------------

def test_optional_function_absent_is_fine():
    check_adapter(_adapter(), "x", optional=("links",))


def test_optional_function_present_must_be_callable():
    check_adapter(_adapter(links=_parse), "x", optional=("links",))
    with pytest.raises(AdapterError, match="'x': links must be a function"):
        check_adapter(_adapter(links=None), "x", optional=("links",))


def test_names_not_declared_optional_are_not_checked():
    check_adapter(_adapter(links=None), "x")


# URL rule shared with the registry ----------------------------------------------------------------

@pytest.mark.parametrize("url, expected", [
    ("https://example.org/a", True), ("HTTP://example.org/", True), ("ftp://example.org/a", False),
    ("example.org/a", False), ("https://", False), ("http://[::1", False), (None, False), ("https://a b/", False),
])
def test_is_http_url(url, expected):
    assert is_http_url(url) is expected


# parse_count and parse_code (dataset-names spec 003, R2.2) -----------------------------------------

@pytest.mark.parametrize("text, expected", [("5", 5), (" 1532 ", 1532), ("0", 0), ("<5", None), ("..", None)])
def test_parse_count(text, expected):
    assert parse_count(text, {"<5", ".."}) == expected


@pytest.mark.parametrize("text", ["", "1.5", "-3", "x", "<3", "١٢"])
def test_parse_count_refuses_what_it_does_not_know(text):
    with pytest.raises(FormatError, match="count"):
        parse_count(text, {"<5"})


def test_parse_count_names_the_field_and_markers():
    with pytest.raises(FormatError, match=r"year 'x' is neither an integer nor a known marker \['<5'\]"):
        parse_count("x", {"<5"}, field="year")


def test_parse_code_maps_and_refuses_unknown_code():
    sex = {"1": "M", "2": "F"}
    assert parse_code(" 2 ", sex, "sex") == "F"
    with pytest.raises(FormatError, match=r"sex 'M' unknown; expected one of \['1', '2'\]"):
        parse_code("M", sex, "sex")


# Error messages (dataset-names spec 003, R2.6) ------------------------------------------------------

def test_file_outside_resources_lists_the_available_ones():
    files = SourceFiles({"a.csv": Path("a.csv")})
    with pytest.raises(AdapterError, match=r"parse asked for file 'b.csv', outside RESOURCES; available: \['a.csv'\]"):
        files["b.csv"]


def test_missing_adapter_shows_the_expected_path():
    with pytest.raises(AdapterError) as e:
        load_adapter("missing-adapter", "example_adapters")
    message = str(e.value)
    assert "adapter example_adapters.missing_adapter absent" in message
    assert str(Path(__file__).parent / "example_adapters" / "missing_adapter.py") in message


def test_broken_adapter_is_not_reported_as_absent(tmp_path, monkeypatch):
    package = tmp_path / "quebrados"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "fonte_x.py").write_text("import modulo_que_nao_existe\n", encoding="utf-8")
    (package / "fonte_y.py").write_text("1/0\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        with pytest.raises(AdapterError, match="adapter quebrados.fonte_x broken: ModuleNotFoundError: .*modulo_que_nao_existe"):
            load_adapter("fonte-x", "quebrados")
        with pytest.raises(AdapterError, match="adapter quebrados.fonte_y broken: ZeroDivisionError"):
            load_adapter("fonte-y", "quebrados")
    finally:
        for name in ("quebrados", "quebrados.fonte_x", "quebrados.fonte_y"):
            sys.modules.pop(name, None)


def test_missing_adapter_package():
    with pytest.raises(AdapterError, match="package 'nao_ha_pacote' not found"):
        load_adapter("x", "nao_ha_pacote")


def test_load_adapter_applies_optional_checks(tmp_path, monkeypatch):
    package = tmp_path / "com_links"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "fonte.py").write_text(
        "from datasettool.sources.adapters import Resource\n"
        "SOURCE_ID = 'fonte'\nRESOURCES = [Resource('https://example.org/a.csv', 'a.csv')]\n"
        "def parse(files):\n    return iter(())\nlinks = 3\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        assert load_adapter("fonte", "com_links").SOURCE_ID == "fonte"
        with pytest.raises(AdapterError, match="links must be a function"):
            load_adapter("fonte", "com_links", optional=("links",))
    finally:
        for name in ("com_links", "com_links.fonte"):
            sys.modules.pop(name, None)


def test_optional_given_as_a_string_is_refused():
    # A str would be iterated character by character: "links" -> "l", "i", ...
    with pytest.raises(TypeError, match="optional"):
        check_adapter(_adapter(links=None), "x", optional="links")
    with pytest.raises(TypeError, match="optional"):
        load_adapter("example", "example_adapters", optional="links")
