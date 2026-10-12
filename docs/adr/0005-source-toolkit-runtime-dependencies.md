# 0005. Runtime dependencies of the source toolkit: `pyyaml` and `xlrd`, pinned

## Status

Accepted (2026-10-12). Spec [004](../specs/004-source-toolkit/spec.md).

## Context

The source toolkit is ported from `dataset-names`, which uses `pyyaml` to read `sources.yaml` and `xlrd` 2.0.2 to read XLS. Its [ADR 0005](https://github.com/BenchCommons/dataset-names/blob/master/docs/adr/0005-leitor-de-planilhas.md) compared spreadsheet readers (`openpyxl`, `pandas`, `python-calamine`, `xlrd`, an own XLSX reader) and chose: XLSX through the standard library (`zipfile` and `iterparse`, streamed, with DTD and ZIP-bomb guards), XLS through `xlrd`, the only pure-Python reader of BIFF8 with no further dependencies (BSD licence). Everything else (HTTP, hashing, CSV, XML) uses the standard library.

`dataset-names` also depends on `pycountry` and `pyarrow`, but only for names-specific code (country codes and Parquet output); they are not needed by the generic toolkit.

## Decision

- Runtime dependencies: `pyyaml==6.0.3` (registry files) and `xlrd==2.0.2` (XLS). Both are pinned exactly in `pyproject.toml`, and `uv.lock` is committed.
- The reasoning of dataset-names ADR 0005 is carried over, including its amendment in dataset-names PR #39: XLSX stays on the standard library, without `defusedxml`. expat in Python 3.12 does not fetch external entities and limits expansion, and the reader refuses DTDs in two independent layers: (1) a pre-scan of the first 64 KiB, which must be valid UTF-8 or UTF-16 with an XML declaration naming no other encoding, so no encoding expat accepts can hide a `<!DOCTYPE` from the scan; (2) expat used directly with `ElementTree.TreeBuilder` (the C `ET.XMLParser` does not expose expat), with `StartDoctypeDeclHandler` and `EntityDeclHandler` raising `FormatError`, which holds even if the pre-scan fails and keeps streaming.
- `pycountry`, `pyarrow` and any other library used by one dataset only stay in that dataset. A dataset passes its own field checks and row counters to the toolkit (spec 004, R5.4 and R6.3).
- Adding a runtime dependency needs a new ADR.

## Consequences

- Installing the toolkit pulls two small pure-Python packages.
- Exact pins mean upgrades are deliberate: a new version of either library is a toolkit release with its own tag.
- `xlrd` is in minimal maintenance; XLS is a frozen format, and replacing the reader would be confined to `datasettool.sources.spreadsheet`.
