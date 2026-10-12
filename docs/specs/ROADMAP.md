# Roadmap: dataset-tool

Specs of this repo, in order. Each one goes through its own cycle: spec, plan, implementation, review. Tracking: issue [#1](https://github.com/BenchCommons/dataset-tool/issues/1).

| Order | Spec | Depends on | Delivers |
|---|---|---|---|
| 1 | [`001-input-contract`](001-input-contract/spec.md) | none | The input contract, its JSON Schemas and test vectors, and the reference `build` and `validate` commands |
| 2 | `002-release-workflow` | 001 | A reusable GitHub workflow that dataset repos call to build, validate and attach inputs to their releases |
| 3 | `003-consumer-fetch` | 001 | A `fetch` command (and/or GitHub Action) for catalog-algorithms and benchmark-tool: resolve input references, download, verify, cache, offline mode |

Adoption by each dataset is specified in that dataset's repo: [dataset-names#24](https://github.com/BenchCommons/dataset-names/issues/24), [dataset-commons#1](https://github.com/BenchCommons/dataset-commons/issues/1).
