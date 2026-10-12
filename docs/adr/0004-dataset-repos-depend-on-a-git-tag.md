# 0004. Dataset repos depend on tools-dataset through a uv git source pinned to a tag

## Status

Accepted (2026-10-12). Spec [004](../specs/004-source-toolkit/spec.md).

## Context

`dataset-names` and later `dataset-*` repos must import the source toolkit. Their builds have to be reproducible: the same commit of a dataset repo must always run the same toolkit code. The options are:

| Option | Reproducible | Cost |
|---|---|---|
| Git dependency pinned to a tag, resolved by `uv` and locked to the commit in `uv.lock` | Yes (`uv.lock` records the commit SHA) | None beyond tagging releases |
| Wheel published to PyPI | Yes, by version | A PyPI project, trusted publishing, name ownership, a release job; nothing else in the org needs PyPI today |
| Wheel attached to GitHub Releases, installed by URL | Yes | A build job and a URL per version in every consumer |
| Git submodule or vendored copy | Yes | Copies drift, which is what spec 004 removes |
| Git dependency on a branch | No | A push to the branch changes every consumer |

## Decision

- tools-dataset releases are git tags `vX.Y.Z` (SemVer) on `main`, created by the maintainer after the release's pull request merges. Tags are never moved or deleted.
- A dataset repo declares the dependency by version and pins its source to the tag with `uv`:

  ```toml
  [project]
  dependencies = ["benchcommons-tools-dataset==0.1.0"]

  [tool.uv.sources]
  benchcommons-tools-dataset = { git = "https://github.com/BenchCommons/tools-dataset", tag = "v0.1.0" }
  ```

  and commits the resulting `uv.lock`. Upgrading is a change of both lines in one pull request.
- The package version in `pyproject.toml` equals the tag without the `v`. CI checks that a fresh project installs the package from this repo's git URL.
- No PyPI publication for now. Publishing a wheel later does not change the import or distribution name (ADR 0003), so consumers would only drop the `[tool.uv.sources]` entry.

## Consequences

- Consumers need network access to GitHub when they resolve or sync without a cache, as they already do for PyPI.
- A tag must exist before a consumer can adopt a version; the pull request that changes the package ends with a tagging step for the maintainer.
- `pip` users can install the same ref with `pip install "benchcommons-tools-dataset @ git+https://github.com/BenchCommons/tools-dataset@v0.1.0"`.
- A tag that points at a broken commit cannot be fixed in place; the fix is a new patch tag.
