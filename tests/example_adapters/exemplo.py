"""Test-only adapter, ported from BenchCommons/dataset-names@e7e8405 tests/adaptadores/exemplo.py.

It yields its own record type, as every dataset does (spec 004, R4.1).
"""

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from datasettool.sources.adapters import Resource

SOURCE_ID = "exemplo"
RESOURCES = [
    Resource("https://example.org/exemplo/primeiros.csv", "primeiros.csv"),
    Resource("https://example.org/exemplo/sobrenomes.csv", "sobrenomes.csv"),
]


@dataclass(frozen=True)
class Row:
    name: str
    kind: str


def parse(files: dict[str, Path]) -> Iterator[Row]:
    for filename, kind in (("primeiros.csv", "given"), ("sobrenomes.csv", "family")):
        with open(files[filename], encoding="utf-8", newline="") as fh:
            for line in csv.DictReader(fh):
                yield Row(line["nome"], kind)
