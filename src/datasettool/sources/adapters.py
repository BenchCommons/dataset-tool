"""Adapter base (spec 004, R4).

An adapter is the module <package>.<source_id with - replaced by _> of a dataset repo. It exposes
SOURCE_ID (the registry id), RESOURCES (a non-empty list of Resource) and parse(files), which reads
the downloaded files without network and yields records of the dataset's own record type.
The toolkit defines no record type: dataset-names, for example, yields RawRecord and RawLink.

Ported from BenchCommons/dataset-names@e7e8405 src/namescommons/adapters/__init__.py (generic part).
"""

import importlib
import importlib.util
import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit


class AdapterError(Exception):
    """Adapter absent, broken or outside the contract of R4."""


class FormatError(ValueError):
    """A source file is not in the format the adapter expects."""


@dataclass(frozen=True)
class Resource:
    url: str
    filename: str


def module_name(source_id: str) -> str:
    return source_id.replace("-", "_")


def is_http_url(url: object) -> bool:
    """http or https URL with a host, without whitespace or control characters; never raises."""
    if not isinstance(url, str) or any(c.isspace() or not c.isprintable() for c in url):
        return False
    try:
        parts = urlsplit(url)
        return parts.scheme.lower() in ("http", "https") and bool(parts.netloc)
    except ValueError:
        return False


def is_safe_filename(name: object) -> bool:
    """A plain file name that cannot escape the cache directory or collide with cache bookkeeping."""
    return (
        isinstance(name, str) and name.isprintable() and name not in ("", ".", "..") and not name.startswith(".")
        and "/" not in name and "\\" not in name
        and not name.endswith((".meta.json", ".part"))
    )


def check_adapter(mod: object, source_id: str, optional: Iterable[str] = ()) -> None:
    """Raise AdapterError if the module breaks the contract of R4.

    `optional` names extra functions the dataset's own protocol allows; each is checked only when present.
    """
    for attribute in ("SOURCE_ID", "RESOURCES", "parse"):
        if not hasattr(mod, attribute):
            raise AdapterError(f"adapter '{source_id}' has no {attribute}")
    if mod.SOURCE_ID != source_id:
        raise AdapterError(f"SOURCE_ID '{mod.SOURCE_ID}' differs from the id '{source_id}' in the registry")
    resources = mod.RESOURCES
    if not isinstance(resources, (list, tuple)) or not resources or not all(
        isinstance(r, Resource) for r in resources
    ):
        raise AdapterError(f"'{source_id}': RESOURCES must be a non-empty list of Resource")
    seen: set[str] = set()
    for r in resources:
        if not is_http_url(r.url):
            raise AdapterError(f"'{source_id}': url {r.url!r} must use http or https")
        if not is_safe_filename(r.filename):
            raise AdapterError(f"'{source_id}': filename {r.filename!r} is invalid")
        if r.filename in seen:
            raise AdapterError(f"'{source_id}': filename {r.filename!r} is repeated")
        seen.add(r.filename)
    if not callable(mod.parse):
        raise AdapterError(f"'{source_id}': parse must be a function")
    for name in optional:
        if hasattr(mod, name) and not callable(getattr(mod, name)):
            raise AdapterError(f"'{source_id}': {name} must be a function")


def _expected_path(package: str, module: str) -> str:
    try:
        spec = importlib.util.find_spec(package)
    except ImportError:
        spec = None
    if spec is None or not spec.submodule_search_locations:
        return f"package {package!r} not found"
    return str(Path(list(spec.submodule_search_locations)[0]) / f"{module}.py")


def load_adapter(source_id: str, package: str, optional: Iterable[str] = ()) -> ModuleType:
    """Import and check the adapter of `source_id` from `package`.

    A module that does not exist is reported as absent, with the expected path; a module that exists
    but fails to import (even because it imports something missing) is reported as broken.
    """
    name = f"{package}.{module_name(source_id)}"
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name is not None and (name == e.name or name.startswith(e.name + ".")):
            expected = _expected_path(package, module_name(source_id))
            raise AdapterError(f"adapter {name} absent (expected at {expected})") from e
        raise AdapterError(f"adapter {name} broken: {type(e).__name__}: {e}") from e
    except Exception as e:
        raise AdapterError(f"adapter {name} broken: {type(e).__name__}: {e}") from e
    check_adapter(mod, source_id, optional)
    return mod


class SourceFiles(dict):
    """Downloaded files of a source (key = filename); a key outside RESOURCES raises AdapterError."""

    def __missing__(self, key):
        raise AdapterError(f"parse asked for file {key!r}, outside RESOURCES; available: {sorted(self)}")


_INTEGER = re.compile(r"[0-9]+")


def parse_count(value: str, missing: Collection[str] = (), field: str = "count") -> int | None:
    """Published integer (a count or a year); a marker from `missing` (suppressed or absent value) becomes None.

    Any other text raises FormatError, so a new marker of the source never passes silently.
    """
    text = value.strip()
    if text in missing:
        return None
    if _INTEGER.fullmatch(text):
        return int(text)
    raise FormatError(f"{field} {value!r} is neither an integer nor a known marker {sorted(missing)}")


def parse_code(value: str, mapping: Mapping[str, str], field: str) -> str:
    """Translate a source code (for example sex '1' and '2') through the mapping; an unknown code is FormatError."""
    try:
        return mapping[value.strip()]
    except KeyError:
        raise FormatError(f"{field} {value!r} unknown; expected one of {sorted(mapping)}") from None
