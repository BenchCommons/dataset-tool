# 0003. Python package name: `benchcommons-tools-dataset`, imported as `datasettool`

## Status

Accepted (2026-10-12). Spec [004](../specs/004-source-toolkit/spec.md).

## Context

Spec 004 makes this repo an installable Python package, first for the source toolkit and later for the reference builder and validator of spec 001. Spec 001's plan already places the code in `src/datasettool/`. The package needs a distribution name (what `uv` and `pip` install) and an import name (what code imports).

This repo was renamed from `dataset-tool` to `tools-dataset` by [.product ADR 0005](https://github.com/BenchCommons/.product/blob/main/docs/adr/0005-tools-prefix.md). A bare `tools-dataset` is generic enough that an unrelated project on PyPI may hold it, and a git dependency still declares a distribution name that must not collide with anything a dataset repo also installs. Import names cannot contain `-`.

The same ADR creates `tools-commons` for code shared by several tools (`tools-benchmark`, `tools-dataset`). The source toolkit is shared by the `dataset-*` repos, inside the dataset domain this repo owns, so it belongs here; a piece that `tools-benchmark` also needs (for example a generic retrying download) would move to `tools-commons` by its own spec.

## Decision

- Distribution name: **`benchcommons-tools-dataset`**: the org prefix plus the repo name, so a lock file shows where the code comes from.
- Import package: **`datasettool`**, as in spec 001's plan, so the two specs share one package and no import changes with the repo rename.
- Layout: the source toolkit lives in the subpackage `datasettool.sources` (`cache`, `spreadsheet`, `adapters`, `registry`); helpers shared with spec 001 (checksums, row counts) live at the top level (`datasettool.files`). Spec 001 adds its own modules next to them.
- The command name of spec 001's CLI is decided by spec 001.

## Consequences

- Dataset repos write `benchcommons-tools-dataset` in their dependencies and `from datasettool.sources import cache` in code.
- The distribution and import names differ, which is common in Python but must be documented in `AGENTS.md` and `README.md`.
- Renaming later breaks every dataset repo's imports and lock file, so the names are fixed from `v0.1.0`.
