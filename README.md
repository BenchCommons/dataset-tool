# dataset-tool

Builds, validates and exports BenchCommons datasets and delivers pinned inputs to the catalogs and benchmark-tool.

This repo owns the **input contract** for every `dataset-*` repo (see [CONTRACTS.md](https://github.com/BenchCommons/.product/blob/main/CONTRACTS.md), spec [001](docs/specs/001-input-contract/spec.md)) and the **source toolkit** they share (spec [004](docs/specs/004-source-toolkit/spec.md)): a download cache, a spreadsheet reader, the adapter base and the source registry.

## Use from a dataset repo

```toml
[project]
dependencies = ["benchcommons-dataset-tool==0.1.0"]

[tool.uv.sources]
benchcommons-dataset-tool = { git = "https://github.com/BenchCommons/dataset-tool", tag = "v0.1.0" }
```

```python
from datasettool.sources.cache import fetch_resource
from datasettool.sources.spreadsheet import rows
```

See [ADR 0004](docs/adr/0004-dataset-repos-depend-on-a-git-tag.md). Specs live in `docs/specs/<NNN>-<feature>/`.

## License

Code: Apache-2.0 ([`LICENSE`](LICENSE)).
