"""Source registry and licence policy (spec 004, R5; ADR 0006).

A registry is a YAML file with a `sources` list. Every entry has the generic fields; each dataset
extends the schema with its own fields, its accepted licences, cross-entry checks and a factory
that builds its own source type.

Ported from BenchCommons/dataset-names@e7e8405 src/namescommons/sources.py (generic part).
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Generic, TypeVar

import yaml

from datasettool.sources.adapters import ID_PATTERN, is_http_url

# Licences that ask for no more than attribution, compatible with a CC BY 4.0 dataset (ADR 0006).
# A starting set: each dataset declares its own list and extends it by its own ADR.
ATTRIBUTION_ONLY_LICENSES = frozenset({
    "public-domain", "CC0-1.0", "CC-BY-3.0", "CC-BY-4.0", "ODC-By-1.0", "OGL-UK-3.0", "etalab-2.0",
})

REQUIRED = ("id", "name", "url", "license", "attribution", "retrieved")
OPTIONAL = {"adapter": True}
GENERIC = REQUIRED + tuple(OPTIONAL)


class RegistryError(ValueError):
    """Invalid registry. The message lists every problem found, one per line."""


@dataclass(frozen=True)
class Field:
    """A dataset field: `check` returns an error text or None; optional fields take `default` when absent."""

    name: str
    check: Callable[[Any], str | None] | None = None
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class Source:
    """Source built by the default factory; dataset fields are in `extra`, read-only.

    Hashable: `extra` (a MappingProxyType, which is unhashable) takes part in equality but not in the hash.
    """

    id: str
    name: str
    url: str
    license: str
    attribution: str
    retrieved: date
    adapter: bool = True
    extra: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}), hash=False)

    @classmethod
    def from_entry(cls, entry: dict[str, Any]) -> "Source":
        extra = {k: v for k, v in entry.items() if k not in GENERIC}
        return cls(**{k: entry[k] for k in GENERIC}, extra=MappingProxyType(extra))


S = TypeVar("S")


@dataclass(frozen=True)
class RegistrySchema(Generic[S]):
    accepted_licenses: frozenset[str]
    license_policy: str  # names the decision behind the list, e.g. "ADR 0001"
    fields: tuple[Field, ...] = ()
    checks: tuple[Callable[[Mapping[str, S]], Iterable[str]], ...] = ()
    factory: Callable[[dict[str, Any]], S] = Source.from_entry

    def __post_init__(self):
        # A str is iterable: as a licence list it would turn the check into a substring test.
        for name in ("accepted_licenses", "fields", "checks"):
            if isinstance(getattr(self, name), (str, bytes)):
                raise TypeError(f"{name} must be a collection, not a string")
        object.__setattr__(self, "accepted_licenses", frozenset(self.accepted_licenses))
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "checks", tuple(self.checks))
        for f in self.fields:
            if not isinstance(f, Field):
                raise TypeError(f"fields must contain Field, got {f!r}")
        for c in self.checks:
            if not callable(c):
                raise TypeError(f"checks must contain callables, got {c!r}")
        if not self.accepted_licenses:
            raise ValueError("a registry schema needs a non-empty accepted_licenses list (ADR 0006)")
        seen: set[str] = set()
        for f in self.fields:
            if f.name in GENERIC:
                raise ValueError(f"dataset field '{f.name}' redefines a generic field")
            if f.name in seen:
                raise ValueError(f"dataset field '{f.name}' declared twice")
            seen.add(f.name)


def load_registry(path: Path, schema: RegistrySchema[S]) -> dict[str, S]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise RegistryError(f"cannot read {path}: {e}") from e
    except yaml.YAMLError as e:
        raise RegistryError(f"{path}: invalid YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RegistryError(f"{path}: the root must be a mapping with the key 'sources'")
    entries = data.get("sources", [])
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise RegistryError(f"{path}: 'sources' must be a list")
    return parse_registry(entries, schema)


def _entry_errors(e: dict, label: str, schema: RegistrySchema) -> list[str]:
    errors: list[str] = []
    required = list(REQUIRED) + [f.name for f in schema.fields if f.required]
    missing = [name for name in required if name not in e]
    if missing:
        return [f"{label}: missing fields {missing}"]
    known = set(GENERIC) | {f.name for f in schema.fields}
    unknown = sorted(set(e) - known, key=str)
    if unknown:
        errors.append(f"{label}: unknown fields {unknown}")
    for name in ("id", "name", "url", "attribution"):
        if not isinstance(e[name], str) or not e[name].strip():
            errors.append(f"{label}: '{name}' empty")
    if isinstance(e["id"], str) and e["id"].strip() and not ID_PATTERN.fullmatch(e["id"]):
        errors.append(f"{label}: 'id' has an invalid format (use [a-z0-9]+(-[a-z0-9]+)*)")
    if isinstance(e["url"], str) and e["url"].strip() and not is_http_url(e["url"]):
        errors.append(f"{label}: 'url' must use the http or https scheme")
    if not isinstance(e["license"], str) or e["license"] not in schema.accepted_licenses:
        errors.append(f"{label}: license '{e['license']}' is not accepted ({schema.license_policy})")
    if not isinstance(e["retrieved"], date) or isinstance(e["retrieved"], datetime):
        errors.append(f"{label}: 'retrieved' must be a YYYY-MM-DD date, without time")
    for name in OPTIONAL:
        if name in e and not isinstance(e[name], bool):
            errors.append(f"{label}: '{name}' must be true or false")
    for f in schema.fields:
        if f.check is not None and f.name in e:
            problem = f.check(e[f.name])
            if problem:
                errors.append(f"{label}: {problem}")
    return errors


def parse_registry(entries: list, schema: RegistrySchema[S]) -> dict[str, S]:
    """Validate every entry and build the sources; all problems are raised together in one RegistryError."""
    errors: list[str] = []
    sources: dict[str, S] = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            errors.append(f"#{i}: entry must be a mapping")
            continue
        label = str(e.get("id") or f"#{i}")
        problems = _entry_errors(e, label, schema)
        if problems:
            errors.extend(problems)
            continue
        if e["id"] in sources:
            errors.append(f"{label}: duplicate id")
            continue
        values = {name: e[name] for name in REQUIRED}
        values.update({name: e.get(name, default) for name, default in OPTIONAL.items()})
        values.update({f.name: e.get(f.name, f.default) for f in schema.fields})
        sources[e["id"]] = schema.factory(values)
    for check in schema.checks:
        errors.extend(check(sources))
    if errors:
        raise RegistryError("\n".join(errors))
    return sources
