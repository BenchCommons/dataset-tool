# AGENTS.md — dataset-tool

Follow the org-wide rules in [BenchCommons/.github AGENTS.md](https://github.com/BenchCommons/.github/blob/main/AGENTS.md) and the decisions in [.product](https://github.com/BenchCommons/.product).

## What this repo is

The shared tooling of the `dataset-*` repos: the source toolkit (spec 004) and, next, the input contract with its reference builder and validator (spec 001). Specs: [`docs/specs/ROADMAP.md`](docs/specs/ROADMAP.md). Decisions: [`docs/adr/`](docs/adr/).

## Stack

Python 3.12, `uv`, `pytest`, built with `hatchling`. Distribution `benchcommons-dataset-tool`, import package `datasettool` ([ADR 0003](docs/adr/0003-python-package-name.md)). Runtime dependencies pinned: `pyyaml==6.0.3`, `xlrd==2.0.2` ([ADR 0005](docs/adr/0005-source-toolkit-runtime-dependencies.md)); a new one needs an ADR.

## Commands

```sh
uv sync --locked      # install
uv run pytest -q      # tests (never use the network; downloads go to a server on 127.0.0.1)
```

## Releases

SemVer tags `vX.Y.Z` on `main`, created by the maintainer after merge, never moved. `version` in `pyproject.toml` equals the tag without `v`. Dataset repos pin a tag through `[tool.uv.sources]` ([ADR 0004](docs/adr/0004-dataset-repos-depend-on-a-git-tag.md)).

## Conventions

- Docs, specs, ADRs, code, comments and messages in English.
- Conventional Commits; signed commits; AI co-authorship only as a `Co-Authored-By:` trailer.
- Code ported from another repo names its origin (`ported from BenchCommons/<repo>@<sha> <path>`) in the commit message.
- Open items go in issues, never in docs or code.
