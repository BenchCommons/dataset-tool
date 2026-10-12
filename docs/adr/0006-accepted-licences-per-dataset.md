# 0006. The list of accepted source licences belongs to each dataset

## Status

Accepted (2026-10-12). Spec [004](../specs/004-source-toolkit/spec.md). Org licence policy: [.product ADR 0003](https://github.com/BenchCommons/.product/blob/main/docs/adr/0003-default-branch-and-licenses.md) (proposed).

## Context

`dataset-names` accepts a source only if its licence allows redistribution under the dataset's data licence, CC BY 4.0 ([its ADR 0001](https://github.com/BenchCommons/dataset-names/blob/master/docs/adr/0001-licenca-dos-dados.md), extended by [ADR 0004](https://github.com/BenchCommons/dataset-names/blob/master/docs/adr/0004-licenca-statistics-canada.md) for the Statistics Canada Open Licence). The source registry moves to the shared toolkit (spec 004), so the toolkit must decide where the accepted list lives.

Which source licences are acceptable depends on the dataset's own data licence: a CC BY 4.0 dataset must refuse ODbL and ShareAlike sources, while a dataset released under ODbL could accept ODbL sources. .product ADR 0003 (still proposed) says datasets use a data licence compatible with their sources, checked per source. A single org-wide list would be wrong for at least one of these cases, and silently accepting a licence is worse than failing.

## Decision

- Each dataset declares its accepted licences in its registry schema, together with a text naming the decision that justifies the list (for `dataset-names`, "ADR 0001"). The toolkit has no implicit default: a schema without a list is an error.
- The toolkit exports `ATTRIBUTION_ONLY_LICENSES` (`public-domain`, `CC0-1.0`, `CC-BY-3.0`, `CC-BY-4.0`, `ODC-By-1.0`, `OGL-UK-3.0`, `etalab-2.0`): licences that require at most attribution and are therefore compatible with a CC BY 4.0 dataset. A dataset copies it or extends it by its own ADR, as `dataset-names` does with `statcan-open-licence`.
- Licence ids in registries are the dataset's ids, SPDX where one exists. Mapping them to SPDX for published inputs is spec 001's licensing step.

## Consequences

- Adding a licence for one dataset never widens another dataset's list.
- If .product ADR 0003 is accepted with an org-wide list, that list can become a named constant here, and datasets keep choosing it explicitly.
- The licence error message names the dataset's own decision, so a contributor knows which ADR to read.
