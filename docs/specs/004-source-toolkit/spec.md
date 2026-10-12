# 004. The source toolkit

Issue: [#4](https://github.com/BenchCommons/dataset-tool/issues/4). Roadmap: [`../ROADMAP.md`](../ROADMAP.md). Adoption by dataset-names: [#5](https://github.com/BenchCommons/dataset-tool/issues/5).

## Why

Every `dataset-*` repo does the same three things before it can build anything: it downloads upstream files politely and reproducibly, it reads the formats institutes publish (CSV, XLS, XLSX), and it keeps a registry of its sources with their licences and attributions. `dataset-names` already does all three, with tests hardened over several reviews (its specs 002, 003, 003b and 003e, ADRs 0001 and 0005). `dataset-commons` and later datasets would otherwise copy that code and let the copies drift.

Owner decision (2026-10-12): the generic parts move to `dataset-tool` as an installable Python package, the **source toolkit**; the names-specific parts (record types, output schema, the names manifest, the names licence list) stay in `dataset-names`. This spec defines the toolkit's behaviour and how dataset repos depend on it. `dataset-tool` owns this contract; dataset repos link to it and never redefine it.

## Terms

- **Source**: one upstream publisher's dataset, registered once in the dataset repo's registry file (for `dataset-names`, `sources.yaml`).
- **Resource**: one file of a source, given by URL and local file name.
- **Adapter**: the dataset repo's module that lists a source's resources and parses the downloaded files into the dataset's own record type.
- **Registry schema**: the generic registry fields plus the fields, licence list and cross-entry checks a dataset adds.

## Requirements

### R1. Package

- **R1.1** The toolkit is the Python distribution `benchcommons-dataset-tool`, import package `datasettool`, in this repo ([ADR 0003](../../adr/0003-python-package-name.md)). It needs Python 3.12 or later, is built with `hatchling` and developed with `uv` and `pytest`.
- **R1.2** The toolkit modules are `datasettool.sources.cache` (R2), `datasettool.sources.spreadsheet` (R3), `datasettool.sources.adapters` (R4), `datasettool.sources.registry` (R5) and `datasettool.files` (R6).
- **R1.3** Versions follow SemVer and are released as git tags `vX.Y.Z` of this repo. The first release of this spec is `v0.1.0`. While the major version is 0, a minor bump may break the API; dataset repos pin an exact tag.
- **R1.4** Dataset repos depend on the package through a `uv` git source pinned to a tag ([ADR 0004](../../adr/0004-dataset-repos-depend-on-a-git-tag.md)). The package is not published to PyPI.
- **R1.5** Runtime dependencies are `pyyaml` and `xlrd`, both pinned to an exact version ([ADR 0005](../../adr/0005-source-toolkit-runtime-dependencies.md)). Any other runtime dependency needs a new ADR.
- **R1.6** User-facing messages and identifiers are in English. Each ported behaviour keeps its meaning and its test vectors (R7).

### R2. Download cache

Ported from `dataset-names` spec 002 R4, spec 003 R4 (403 hint) and spec 003e R4.1.

- **R2.1** A resource is cached at `<cache>/<source_id>/<filename>`, with `<filename>.meta.json` next to it holding `url`, `downloaded_at` (ISO 8601 with time zone, seconds), `sha256` and `size`.
- **R2.2** Without refresh, a file present in the cache is returned without any request. With refresh, it is downloaded again. With offline, no request is made and a missing file is a `FetchError` naming the path. Offline and refresh together are a `ValueError`.
- **R2.3** Every request sends a `User-Agent`. The default identifies `dataset-tool`, its version and this repo's URL; a dataset passes its own (name, version and repo URL) so upstream operators know who is downloading.
- **R2.4** A download has a timeout and up to three attempts by default, waiting 2 s, then 4 s (doubling). A 4xx response is final and is not retried, except 408 and 429. The number of attempts, the first wait and the sleep function are parameters; fewer than one attempt is a `ValueError`.
- **R2.5** A partial download never enters the cache: bytes go to `<filename>.part` and are renamed only when complete. A `Content-Length` that is malformed or differs from the bytes received is a `FetchError`. The old `.meta.json` is removed before the new file is renamed into place, so a failure in between leaves a file without metadata, never metadata describing another file. A failed refresh keeps the previous version.
- **R2.6** A `Content-Type` of `text/html` for a resource whose file name does not end in `.html` or `.htm` is a `BlockedError` (a subclass of `FetchError`): nothing is cached, there is no retry, and the message names the URL and the exact cache path where to save a file downloaded with a browser, then rerun offline.
- **R2.7** After the last failed attempt, the `FetchError` names the URL, the number of attempts and the last cause. For a 403, the message adds the same manual-download hint as R2.6; other errors do not carry it.

### R3. Spreadsheet reader

Ported from `dataset-names` spec 003b R1 and ADR 0005, unchanged in behaviour.

- **R3.1** `sheet_names(path)` lists sheets in file order. `rows(path, sheet)` yields `(Excel row number, values by column)` for each non-empty row; column A is index 0. A missing sheet is a `FormatError` naming the sheet and listing the sheets.
- **R3.2** The format is detected from the first bytes, not the extension: `PK\x03\x04` is XLSX, the OLE2 signature is XLS. Anything else, including an HTML error page saved under a spreadsheet name, is a `FormatError`.
- **R3.3** Both formats return the same value types: `str`, `int` (integral numbers), `float`, `bool`, `None` for empty cells. Trailing `None` values are cut and empty rows skipped. Formula errors, the XLSX date type `d` and unknown cell types are `FormatError` naming the sheet and cell.
- **R3.4** XLSX is read in a stream with the standard library. Rejected with `FormatError`: a DTD (`<!DOCTYPE` or `<!ENTITY`) before the root element of any XML member, checked in the first 64 KiB, and a prologue larger than that; a member missing from the ZIP; a member that inflates to more than 1 GiB, or to more than 1 MiB at a ratio above 100:1; a malformed cell reference or one beyond column `XFD`; a non-numeric row number; a shared-string index that is not an integer or is out of range. Memory stays flat over the whole sheet.
- **R3.5** XLS is read with `xlrd` pinned to `2.0.2`; a file `xlrd` cannot open is a `FormatError` carrying the original message.
- **R3.6** `cell_count(value, missing=(), field="count")` turns a cell into a non-negative count or `None` for a declared marker, by the rules of R4.4; an empty cell is accepted only when `""` is a marker.

### R4. Adapter base

Ported from the generic part of `dataset-names` `src/namescommons/adapters/__init__.py` (its spec 002 R1 and spec 003 R2.2 and R2.6).

- **R4.1** An adapter is the module `<package>.<source_id with - replaced by _>`, where the dataset chooses `<package>`. It exposes `SOURCE_ID` (equal to the registry id), `RESOURCES` (a non-empty list of `Resource(url, filename)`) and `parse(files)`, which reads the downloaded files without network and yields records of the **dataset's own record type**. The toolkit defines no record type.
- **R4.2** `check_adapter(module, source_id, optional=())` rejects with `AdapterError`: a missing `SOURCE_ID`, `RESOURCES` or `parse`; a `SOURCE_ID` different from the registry id; `RESOURCES` that is empty or not made of `Resource`; a URL that is not `http` or `https` with a host, or that contains whitespace or control characters; a file name that is empty, `.` or `..`, starts with a dot, contains `/`, `\` or a non-printable character, or ends in `.meta.json` or `.part`; a repeated file name; a `parse` that is not callable; and any name in `optional` that the module defines but is not callable (for `dataset-names`, `links`).
- **R4.3** `load_adapter(source_id, package, optional=())` imports and checks the adapter. A module that does not exist is reported as **absent**, with the path where it was expected; a module that exists but fails to import, including when it imports something missing, is reported as **broken**, with the exception type and message. A package that does not exist is reported by name.
- **R4.4** `parse_count(value, missing=(), field="count")` accepts a non-negative decimal integer (surrounding whitespace allowed) or a declared marker (returns `None`); anything else is a `FormatError` naming the field, the value and the markers, so a new suppression marker never becomes zero. `parse_code(value, mapping, field)` maps a source code through an explicit mapping; an unknown code is a `FormatError` listing the expected codes.
- **R4.5** `SourceFiles` is the mapping passed to `parse`; asking it for a file outside `RESOURCES` is an `AdapterError` listing the available files.

### R5. Source registry and licence policy

Ported from the generic part of `dataset-names` `src/namescommons/sources.py` (its spec 001 R2, spec 002 R2 and R3, spec 003 R2.7).

- **R5.1** The registry is a YAML file whose root is a mapping with a `sources` list. An unreadable file, invalid YAML, a root that is not a mapping and a `sources` that is not a list are each a `RegistryError` naming the file. An empty or missing list is an empty registry.
- **R5.2** Generic required fields of every entry: `id`, `name`, `url`, `license`, `attribution`, `retrieved`. Generic optional field: `adapter` (boolean, default `true`; `false` registers a source used only by hand).
- **R5.3** Generic rules: `id`, `name`, `url` and `attribution` are non-empty strings; `id` matches `[a-z0-9]+(-[a-z0-9]+)*`; `url` is `http` or `https` with a host (the R4.2 rule); `license` is a string in the dataset's accepted list; `retrieved` is a date without time; ids are unique; fields outside the schema are rejected.
- **R5.4** A dataset extends the schema with its own fields (each required or optional with a default, each with its own check), its accepted licence list, a text naming the policy that decides that list (shown in the licence error, for example "ADR 0001"), cross-entry checks over the parsed sources, and a factory that builds its own source type. `dataset-names` uses this for `country`, `count_type`, `primary`, `suppression`, `uniform_case` and its one-primary rule.
- **R5.5** The accepted licence list belongs to each dataset, because it depends on that dataset's data licence ([ADR 0006](../../adr/0006-accepted-licences-per-dataset.md); org policy in [.product ADR 0003](https://github.com/BenchCommons/.product/blob/main/docs/adr/0003-default-branch-and-licenses.md)). There is no implicit default: a schema without a list is an error. The toolkit exports `ATTRIBUTION_ONLY_LICENSES`, the licences that ask for no more than attribution (`public-domain`, `CC0-1.0`, `CC-BY-3.0`, `CC-BY-4.0`, `ODC-By-1.0`, `OGL-UK-3.0`, `etalab-2.0`), as a starting point a dataset copies or extends by its own ADR.
- **R5.6** All problems of a registry are collected and reported together in one `RegistryError`, each prefixed with the entry id (or `#<index>` when the id is unusable).

### R6. File helpers

Ported from the generic part of `dataset-names` `src/namescommons/manifest.py` (its spec 001 R5 and spec 002 R9).

- **R6.1** `sha256_file(path)` returns the lowercase hex SHA-256 of a file, read in blocks.
- **R6.2** `count_csv_records(path)` counts CSV records with a CSV reader, not physical lines: the header and blank lines are not counted, and a quoted value spanning lines is one record.
- **R6.3** `describe_files(root, exclude=…, counters=…)` maps each file under `root` (POSIX relative path, sorted) to `{sha256, rows}`, counting rows with the counter registered for the file's suffix (`.csv` by default); a file with no counter is a `ValueError` naming it, never a guessed count.
- **R6.4** The dataset's manifest layout, release version format and output schema are not part of the toolkit.

### R7. Faithful port

- **R7.1** Each test of `dataset-names` that exercises a ported behaviour is ported with its inputs and expected values unchanged (test vectors), at `dataset-names@e7e8405`. Only the language of messages and identifiers changes. Tests that depend on names-specific code (record types, the names pipeline, the INE adapter samples) stay in `dataset-names`.
- **R7.2** Each commit that ports a module names its origin, for example `ported from BenchCommons/dataset-names@e7e8405 src/namescommons/cache.py`. Both repos' code is Apache-2.0, and this repo carries the Apache-2.0 `LICENSE`.
- **R7.3** Tests never use the network: downloads are tested against an HTTP server on `127.0.0.1` started by the tests.

### R8. CI

The CI workflow keeps the org docs job and adds a Python job that runs `uv sync --locked` and `uv run pytest -q`, and a job that installs the package into a fresh project from this repo by git URL at the commit under test and imports every module.

## Acceptance criteria

1. Every test listed in the plan's port map passes in this repo with the same test vectors as in `dataset-names@e7e8405`.
2. `uv run pytest -q` passes locally and in CI, with no network access other than `127.0.0.1`.
3. A registry schema built only from the public API, with the fields and rules of `dataset-names` (`country`, `count_type`, `primary`, `suppression`, `uniform_case`, one primary per country and count type), passes the ported `dataset-names` registry tests.
4. In a fresh `uv` project, the package installs from a git URL of this repo pinned to a ref, and every module imports. The CI job proves it at the commit under test; after merge, the same command at tag `v0.1.0` proves it for the release.
5. The CI workflow runs the docs job and the Python jobs, and all pass on the pull request of this spec.
6. Issue [#5](https://github.com/BenchCommons/dataset-tool/issues/5) tracks the adoption by `dataset-names`.

## Out of scope

- Any change in `dataset-names` (issue #5; its own spec goes in that repo).
- A command-line interface. Dataset repos keep their CLIs and pass the offline and refresh flags through.
- The input contract and its build and validate commands (spec 001), the release workflow (002) and consumer fetch (003).
- Publishing to PyPI, Parquet row counting (a dataset registers its own counter), and the names record types, output schema and manifest.
