# 0003. Python package name: `benchcommons-dataset-tool`, imported as `datasettool`

## Status

Accepted (2026-10-12). Spec [004](../specs/004-source-toolkit/spec.md).

## Context

Spec 004 makes this repo an installable Python package, first for the source toolkit and later for the reference builder and validator of spec 001. Spec 001's plan already places the code in `src/datasettool/` and names the command `dataset-tool`. The package needs a distribution name (what `uv` and `pip` install) and an import name (what code imports).

`dataset-tool` alone is generic enough that an unrelated project on PyPI may hold it, and a git dependency still declares a distribution name that must not collide with anything a dataset repo also installs. Import names cannot contain `-`.

## Decision

- Distribution name: **`benchcommons-dataset-tool`**. The org prefix avoids collisions and makes the origin visible in a lock file.
- Import package: **`datasettool`**, as in spec 001's plan, so the two specs share one package.
- Layout: the source toolkit lives in the subpackage `datasettool.sources` (`cache`, `spreadsheet`, `adapters`, `registry`); helpers shared with spec 001 (checksums, row counts) live at the top level (`datasettool.files`). Spec 001 adds its own modules next to them.
- The command name `dataset-tool` stays reserved for spec 001's CLI.

## Consequences

- Dataset repos write `benchcommons-dataset-tool` in their dependencies and `from datasettool.sources import cache` in code.
- The distribution and import names differ, which is common in Python but must be documented in `AGENTS.md` and `README.md`.
- Renaming later breaks every dataset repo's imports and lock file, so the names are fixed from `v0.1.0`.
