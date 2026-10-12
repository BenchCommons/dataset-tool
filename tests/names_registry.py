"""dataset-names' registry rules expressed with the public registry API (spec 004, acceptance criterion 3).

Mirrors BenchCommons/dataset-names@e7e8405 src/namescommons/sources.py. The only difference is the
country check: dataset-names uses pycountry, this test schema uses a fixed set of codes.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from datasettool.sources.registry import ATTRIBUTION_ONLY_LICENSES, Field, RegistrySchema

COUNTRIES = frozenset({"BR", "CA", "ES", "FR", "IE", "NO", "NZ", "PT", "US"})
COUNT_TYPES = ("births", "population", "attested")


@dataclass(frozen=True)
class NamesSource:
    id: str
    name: str
    url: str
    license: str
    attribution: str
    country: str | None
    count_type: str
    primary: bool
    suppression: int | None
    retrieved: date
    uniform_case: bool = False
    adapter: bool = True


def _country(value):
    if isinstance(value, bool):
        return f"country read as boolean {value}; quote the code, e.g. \"NO\""
    if value is not None and not (isinstance(value, str) and value in COUNTRIES):
        return f"country '{value}' is not ISO 3166-1 alpha-2"
    return None


def _count_type(value):
    return None if value in COUNT_TYPES else f"count_type '{value}' is invalid"


def _primary(value):
    return None if isinstance(value, bool) else "'primary' must be true or false"


def _suppression(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        return "'suppression' must be a positive integer or empty"
    return None


def _uniform_case(value):
    return None if isinstance(value, bool) else "'uniform_case' must be true or false"


def one_primary(sources: Mapping[str, NamesSource]) -> list[str]:
    """Exactly one primary per (country, count_type) with counts; attested is not checked."""
    groups: dict[tuple, list[NamesSource]] = {}
    for s in sources.values():
        if s.count_type == "attested":
            continue
        groups.setdefault((s.country, s.count_type), []).append(s)
    errors = []
    for (country, kind), group in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        if len(group) > 1 and sum(s.primary is True for s in group) != 1:
            errors.append(f"{country}/{kind}: sources {sorted(s.id for s in group)}; exactly one must have primary: true")
    return errors


SCHEMA = RegistrySchema(
    accepted_licenses=ATTRIBUTION_ONLY_LICENSES | {"statcan-open-licence"},
    license_policy="ADR 0001",
    fields=(
        Field("country", _country),
        Field("count_type", _count_type),
        Field("primary", _primary),
        Field("suppression", _suppression),
        Field("uniform_case", _uniform_case, required=False, default=False),
    ),
    checks=(one_primary,),
    factory=lambda entry: NamesSource(**entry),
)
