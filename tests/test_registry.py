"""Spec 004, R5: source registry and licence policy.

Ported from BenchCommons/dataset-names@e7e8405 tests/test_sources.py and tests/test_sources_extensoes.py,
run through tests/names_registry.py, a registry schema built only from the public API
(acceptance criterion 3). Test vectors unchanged; messages in English.
"""

from datetime import date, datetime

import pytest

from datasettool.sources.registry import (
    ATTRIBUTION_ONLY_LICENSES, Field, RegistryError, RegistrySchema, Source, load_registry, parse_registry,
)
from names_registry import SCHEMA


def parse_sources(entries):
    return parse_registry(entries, SCHEMA)


def load_sources(path):
    return load_registry(path, SCHEMA)


def source(**fields):
    base = {
        "id": "us-ssa-births", "name": "SSA Baby Names", "url": "https://www.ssa.gov/oact/babynames/",
        "license": "public-domain", "attribution": "U.S. Social Security Administration",
        "country": "US", "count_type": "births", "primary": True, "suppression": 5,
        "retrieved": date(2026, 10, 1),
    }
    return {**base, **fields}


def test_valid_source():
    sources = parse_sources([source()])
    assert sources["us-ssa-births"].suppression == 5


def test_loads_yaml(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(
        "sources:\n"
        "  - id: wikidata\n"
        "    name: Wikidata\n"
        "    url: https://www.wikidata.org/\n"
        "    license: CC0-1.0\n"
        "    attribution: Wikidata\n"
        "    country: null\n"
        "    count_type: attested\n"
        "    primary: false\n"
        "    suppression: null\n"
        "    retrieved: 2026-10-01\n",
        encoding="utf-8",
    )
    assert load_sources(p)["wikidata"].retrieved == date(2026, 10, 1)


def test_file_without_sources(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("sources: []\n", encoding="utf-8")
    assert load_sources(p) == {}


@pytest.mark.parametrize("license", ["CC-BY-SA-4.0", "ODbL-1.0", "CC-BY-NC-4.0", "desconhecida"])
def test_incompatible_license_is_refused(license):
    with pytest.raises(RegistryError, match="ADR 0001"):
        parse_sources([source(license=license)])


def test_statcan_open_licence_is_accepted_by_the_dataset_extension():
    # dataset-names ADR 0004 extends its ADR 0001 list; the dataset adds it to the shared starting set.
    sources = parse_sources([source(license="statcan-open-licence")])
    assert sources["us-ssa-births"].license == "statcan-open-licence"


@pytest.mark.parametrize("fields, fragment", [
    ({"country": "XX"}, "ISO 3166-1"),
    ({"country": "br"}, "ISO 3166-1"),
    ({"count_type": "deaths"}, "count_type"),
    ({"primary": "sim"}, "primary"),
    ({"suppression": 0}, "suppression"),
    ({"retrieved": "ontem"}, "retrieved"),
    ({"url": ""}, "'url' empty"),
    ({"extra": 1}, "unknown"),
])
def test_invalid_field(fields, fragment):
    with pytest.raises(RegistryError, match=fragment):
        parse_sources([source(**fields)])


@pytest.mark.parametrize("ident", ["../../etc", "Us-Ssa", "us_ssa", "-us", "us-", "us--ssa", "us ssa", "a/b"])
def test_id_with_invalid_format(ident):
    with pytest.raises(RegistryError, match="invalid format") as e:
        parse_sources([source(id=ident)])
    assert ident in str(e.value)


def test_missing_field():
    entry = source()
    del entry["license"]
    with pytest.raises(RegistryError, match="missing"):
        parse_sources([entry])


def test_duplicate_id():
    with pytest.raises(RegistryError, match="duplicate"):
        parse_sources([source(), source()])


def test_two_sources_for_the_same_pair_need_one_primary():
    with pytest.raises(RegistryError, match="exactly one"):
        parse_sources([source(id="a"), source(id="b")])
    with pytest.raises(RegistryError, match="exactly one"):
        parse_sources([source(id="a", primary=False), source(id="b", primary=False)])
    assert set(parse_sources([source(id="a"), source(id="b", primary=False)])) == {"a", "b"}


def test_all_errors_are_listed():
    with pytest.raises(RegistryError) as e:
        parse_sources([source(license="ODbL-1.0", country="XX")])
    assert "ADR 0001" in str(e.value) and "ISO 3166-1" in str(e.value)


def test_non_text_license_is_a_registry_error():
    with pytest.raises(RegistryError, match="ADR 0001"):
        parse_sources([source(license=["CC0-1.0"])])


def test_non_text_id_is_a_registry_error():
    with pytest.raises(RegistryError, match="'id' empty"):
        parse_sources([source(id=["us-ssa-births"])])


@pytest.mark.parametrize("fields, fragment", [
    ({"country": ["US"]}, "ISO 3166-1"),
    ({"count_type": ["births"]}, "count_type"),
])
def test_non_text_field_is_a_registry_error(fields, fragment):
    with pytest.raises(RegistryError, match=fragment):
        parse_sources([source(**fields)])


def test_entry_that_is_not_a_mapping():
    with pytest.raises(RegistryError, match="#0: entry must be a mapping") as e:
        parse_sources(["foo", None])
    assert "#1: entry must be a mapping" in str(e.value)


def test_missing_file(tmp_path):
    with pytest.raises(RegistryError, match="cannot read"):
        load_sources(tmp_path / "nao-existe.yaml")


def test_malformed_yaml(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("sources: [\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="invalid YAML"):
        load_sources(p)


def test_root_that_is_not_a_mapping(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("- foo\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="the root must be a mapping"):
        load_sources(p)


@pytest.mark.parametrize("content", ["sources: 5\n", "sources: texto\n"])
def test_sources_that_is_not_a_list(tmp_path, content):
    p = tmp_path / "sources.yaml"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(RegistryError, match="'sources' must be a list"):
        load_sources(p)


def test_attested_does_not_need_primary():
    """dataset-names spec 004, R5 (its issue #3): primary has no effect for attested and is not checked."""
    no_country = [source(id=i, country=None, count_type="attested", primary=False) for i in ("a", "b")]
    assert set(parse_sources(no_country)) == {"a", "b"}
    same_country = [source(id=i, count_type="attested", primary=True) for i in ("a", "b")]
    assert set(parse_sources(same_country)) == {"a", "b"}


@pytest.mark.parametrize("kind", ["births", "population"])
def test_counts_still_need_one_primary(kind):
    with pytest.raises(RegistryError, match=f"US/{kind}: sources \\['a', 'b'\\]; exactly one"):
        parse_sources([source(id=i, count_type=kind, primary=False) for i in ("a", "b")])


def test_boolean_country_asks_for_quotes():
    with pytest.raises(RegistryError, match='country read as boolean False; quote the code, e.g. "NO"'):
        parse_sources([source(country=False)])


# Optional fields and the last refusals of dataset-names spec 002 R3 (test_sources_extensoes.py) ----

def ext_source(**fields):
    base = {
        "id": "pt-exemplo", "name": "Exemplo", "url": "https://example.org/nomes",
        "license": "CC-BY-4.0", "attribution": "Exemplo", "country": "PT",
        "count_type": "births", "primary": True, "suppression": None,
        "retrieved": date(2026, 10, 1),
    }
    return {**base, **fields}


def test_optional_fields_have_defaults():
    s = parse_sources([ext_source()])["pt-exemplo"]
    assert (s.uniform_case, s.adapter) == (False, True)


def test_optional_fields_declared():
    s = parse_sources([ext_source(uniform_case=True, adapter=False)])["pt-exemplo"]
    assert (s.uniform_case, s.adapter) == (True, False)


@pytest.mark.parametrize("field", ["uniform_case", "adapter"])
@pytest.mark.parametrize("value", ["sim", 1, None])
def test_optional_field_not_boolean(field, value):
    with pytest.raises(RegistryError, match=f"'{field}' must be true or false"):
        parse_sources([ext_source(**{field: value})])


def test_retrieved_with_time_is_refused():
    with pytest.raises(RegistryError, match="'retrieved' must be a YYYY-MM-DD date"):
        parse_sources([ext_source(retrieved=datetime(2026, 10, 1, 12, 30))])


def test_retrieved_with_time_in_yaml_is_refused(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(
        "sources:\n"
        "  - id: pt-exemplo\n"
        "    name: Exemplo\n"
        "    url: https://example.org/nomes\n"
        "    license: CC-BY-4.0\n"
        "    attribution: Exemplo\n"
        "    country: PT\n"
        "    count_type: births\n"
        "    primary: true\n"
        "    suppression: null\n"
        "    retrieved: 2026-10-01T10:00:00\n",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="retrieved"):
        load_sources(p)


@pytest.mark.parametrize("url", [
    "ftp://example.org/nomes", "example.org/nomes", "file:///tmp/nomes.csv", "https://", "mailto:a@b.c",
    "http://[::1", " https://example.org/nomes", "https://example.org/nomes\n", "https://exam ple.org/",
])
def test_url_without_http_scheme_is_refused(url):
    with pytest.raises(RegistryError, match="http or https"):
        parse_sources([ext_source(url=url)])


@pytest.mark.parametrize("url", ["http://example.org/a.csv", "HTTPS://example.org/"])
def test_http_and_https_urls_are_accepted(url):
    assert parse_sources([ext_source(url=url)])["pt-exemplo"].url == url


def test_malformed_url_names_the_source_instead_of_raising_value_error():
    with pytest.raises(RegistryError, match="pt-exemplo: 'url' must use the http or https scheme"):
        parse_sources([ext_source(url="http://[::1")])


# Generic schema (spec 004, R5.2 to R5.5) ------------------------------------------------------------

def generic(**fields):
    base = {"id": "wordnet", "name": "WordNet", "url": "https://wordnet.princeton.edu/",
            "license": "CC-BY-4.0", "attribution": "Princeton University", "retrieved": date(2026, 10, 1)}
    return {**base, **fields}


GENERIC = RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="ADR 0001 of dataset-commons")


def test_generic_schema_builds_the_default_source():
    s = parse_registry([generic()], GENERIC)["wordnet"]
    assert s == Source("wordnet", "WordNet", "https://wordnet.princeton.edu/", "CC-BY-4.0",
                       "Princeton University", date(2026, 10, 1))
    assert s.adapter is True and dict(s.extra) == {}


def test_generic_schema_refuses_dataset_fields():
    with pytest.raises(RegistryError, match=r"wordnet: unknown fields \['country'\]"):
        parse_registry([generic(country="US")], GENERIC)


def test_dataset_fields_go_to_extra_in_the_default_source():
    schema = RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x",
                            fields=(Field("language"), Field("words", required=False, default=0)))
    s = parse_registry([generic(language="en")], schema)["wordnet"]
    assert dict(s.extra) == {"language": "en", "words": 0}
    with pytest.raises(TypeError):
        s.extra["language"] = "pt"


def test_licence_error_names_the_dataset_policy():
    with pytest.raises(RegistryError, match=r"wordnet: license 'ODbL-1.0' is not accepted \(ADR 0001 of dataset-commons\)"):
        parse_registry([generic(license="ODbL-1.0")], GENERIC)


def test_attribution_only_licenses():
    assert ATTRIBUTION_ONLY_LICENSES == {
        "public-domain", "CC0-1.0", "CC-BY-3.0", "CC-BY-4.0", "ODC-By-1.0", "OGL-UK-3.0", "etalab-2.0",
    }
    assert "statcan-open-licence" not in ATTRIBUTION_ONLY_LICENSES


def test_schema_without_accepted_licenses_is_an_error():
    with pytest.raises(ValueError, match="accepted_licenses"):
        RegistrySchema(accepted_licenses=frozenset(), license_policy="x")


@pytest.mark.parametrize("name", ["id", "license", "retrieved", "adapter"])
def test_dataset_field_cannot_redefine_a_generic_field(name):
    with pytest.raises(ValueError, match=f"'{name}'"):
        RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x", fields=(Field(name),))


def test_dataset_field_declared_twice_is_an_error():
    with pytest.raises(ValueError, match="'language'"):
        RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x",
                       fields=(Field("language"), Field("language")))


def test_cross_checks_see_only_valid_entries_and_all_errors_are_reported():
    seen = []

    def check(sources):
        seen.append(sorted(sources))
        return ["cross-entry problem"]

    schema = RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x", checks=(check,))
    with pytest.raises(RegistryError) as e:
        parse_registry([generic(), generic(id="bad", license="ODbL-1.0")], schema)
    assert seen == [["wordnet"]]
    assert str(e.value).splitlines() == ["bad: license 'ODbL-1.0' is not accepted (x)", "cross-entry problem"]


# Collections passed as a single string (review of PR #7) -------------------------------------------

def test_license_list_given_as_a_string_is_refused():
    # A str would make the licence check a substring test: "BY" in "CC-BY-4.0".
    with pytest.raises(TypeError, match="accepted_licenses"):
        RegistrySchema(accepted_licenses="CC-BY-4.0", license_policy="x")


@pytest.mark.parametrize("name, value", [("fields", "country"), ("checks", "one_primary")])
def test_fields_and_checks_given_as_a_string_are_refused(name, value):
    with pytest.raises(TypeError, match=name):
        RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x", **{name: value})


def test_schema_collections_are_coerced():
    schema = RegistrySchema(accepted_licenses=["CC-BY-4.0"], license_policy="x", fields=[Field("language")],
                            checks=[lambda sources: []])
    assert schema.accepted_licenses == frozenset({"CC-BY-4.0"})
    assert isinstance(schema.fields, tuple) and isinstance(schema.checks, tuple)
    with pytest.raises(RegistryError, match="license 'BY' is not accepted"):
        parse_registry([generic(license="BY", language="en")], schema)


def test_field_and_check_types_are_checked():
    with pytest.raises(TypeError, match="Field"):
        RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x", fields=("country",))
    with pytest.raises(TypeError, match="callable"):
        RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x", checks=(3,))


def test_default_source_is_hashable():
    # extra is a read-only MappingProxyType (unhashable); it is left out of the hash, not of equality.
    schema = RegistrySchema(accepted_licenses=ATTRIBUTION_ONLY_LICENSES, license_policy="x", fields=(Field("language"),))
    a = parse_registry([generic(language="en")], schema)["wordnet"]
    b = parse_registry([generic(language="pt")], schema)["wordnet"]
    assert len({a, a}) == 1
    assert a != b and len({a, b}) == 2
