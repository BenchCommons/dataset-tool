# 0007. The source toolkit lives in tools-dataset, not in tools-commons

## Status

Accepted (2026-10-12). Spec [004](../specs/004-source-toolkit/spec.md).

## Context

The owner decided (2026-10-12) that the generic source code of `dataset-names` (download cache, spreadsheet reader, adapter base, source registry, file helpers) moves to a shared package. [.product ADR 0005](https://github.com/BenchCommons/.product/blob/main/docs/adr/0005-tools-prefix.md) then renamed this repo to `tools-dataset` and created `tools-commons` for the shared libraries of the tools (`tools-benchmark`, `tools-dataset`). Its scope issue, [tools-commons#1](https://github.com/BenchCommons/tools-commons/issues/1), lists "retry wrappers for flaky downloads" among the candidates, which overlaps with the cache.

## Decision

- The source toolkit lives in `tools-dataset` (package `benchcommons-tools-dataset`, [ADR 0003](0003-python-package-name.md)). Its consumers are the `dataset-*` repos, inside the dataset domain this repo owns, and spec 001 builds on the same package.
- A piece that another tool also needs (for example the retrying download for `tools-benchmark`) moves to `tools-commons` through a spec there; this package then depends on `tools-commons` instead of keeping its own copy.

## Consequences

- Dataset repos depend on one package for both the source toolkit and, later, the input contract tooling.
- If `tools-commons` takes the download code, `datasettool.sources.cache` becomes a thin layer over it, and its public API stays the same for dataset repos.
