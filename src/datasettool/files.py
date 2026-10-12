"""File checksums and row counts for release manifests (spec 004, R6).

The manifest layout, release version format and output schema belong to each dataset.

Ported from BenchCommons/dataset-names@e7e8405 src/namescommons/manifest.py (generic part).
"""

import csv
import hashlib
from collections.abc import Callable, Collection, Mapping
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    """Lowercase hex SHA-256 of a file, read in 1 MiB blocks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def count_csv_records(path: str | Path) -> int:
    """CSV records, read with a CSV reader: no header, no blank lines; a quoted multi-line value is one record."""
    with open(path, encoding="utf-8", newline="") as fh:
        records = sum(1 for row in csv.reader(fh) if row)
        return max(records - 1, 0)


DEFAULT_COUNTERS: Mapping[str, Callable[[Path], int]] = {".csv": count_csv_records}


def describe_files(
    root: str | Path,
    exclude: Collection[str] = ("manifest.json",),
    counters: Mapping[str, Callable[[Path], int]] = DEFAULT_COUNTERS,
) -> dict[str, dict]:
    """{POSIX relative path: {"sha256", "rows"}} of every file under root, sorted.

    Rows are counted by the counter registered for the file's suffix; a file without one is a
    ValueError, never a guessed count. Files whose name is in `exclude` are left out.
    """
    root = Path(root)
    files = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in exclude:
            continue
        relative = p.relative_to(root).as_posix()
        counter = counters.get(p.suffix)
        if counter is None:
            raise ValueError(f"{relative}: no row counter for {p.suffix!r}; register one in counters")
        files[relative] = {"sha256": sha256_file(p), "rows": counter(p)}
    return files
