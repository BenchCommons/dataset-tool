# 001. The input contract: plan

Spec: [`spec.md`](spec.md). Tasks: [`tasks.md`](tasks.md).

This plan says how the contract is expressed (schemas, algorithms, file layout) and proposes the reference implementation. The language and tooling are a proposal for review; the contract itself (spec R1 to R9) does not depend on them.

## 1. Where things live

| Artifact | Owner | Location |
|---|---|---|
| Contract text, JSON Schemas, test vectors | dataset-tool | this repo: `docs/specs/001-input-contract/`, `schema/`, `vectors/` |
| Reference builder and validator | dataset-tool | this repo: `src/datasettool/` |
| Input definitions (`inputs.yaml`) | each dataset repo | repo root, next to `sources.yaml` in `dataset-names` |
| Published inputs | each dataset repo | assets of that repo's GitHub Release |
| Input references (pins) | each consumer | location set by the catalog contract (benchmark-tool#29) |

## 2. Input definition: `inputs.yaml` (in the dataset repo)

```yaml
contract: 1                      # major version of this contract
inputs:
  - name: given-names
    title: Given names
    description: Distinct given names from all countries, in their published script.
    upstream:
      artifact: given_names.csv  # file of the same dataset release
    filter: {}                   # optional equality filters on upstream columns, e.g. {script: Latn}
    record:
      format: lines
      fields:
        - {name: name, type: string, from: name, description: Display form of the name (NFC)}
    sampling: {method: hash-order, seed: "benchcommons:names/given-names:1"}
    sizes: [1k, 10k, 100k]
  - name: given-names-dup
    title: Given names with repetitions
    upstream: {artifact: given_names.csv}
    record:
      format: lines
      fields: [{name: name, type: string, from: name}]
    sampling: {method: hash-index, seed: "benchcommons:names/given-names-dup:1"}
    sizes: [1k, 100k, 1m]
```

The example uses real columns of `dataset-names` (`given_names.csv`: `name`, `name_key`, `ascii`, `script`, …; spec 001 of that repo). The actual list of inputs and sizes belongs to dataset-names#24; `1m` without replacement is likely larger than the number of distinct given names, which is why the example puts `1m` under `hash-index`.

Rules: `from` names an upstream column; a `csv` input may project several columns; `filter` keeps only rows whose columns equal the given values. The definition is validated by `schema/inputs-definition.schema.json`.

## 3. Building the population

1. Verify the upstream artifact against the dataset release's own `manifest.json` (dataset-names already writes `files.<path>.sha256` there) and record `upstream`.
2. Read the upstream artifact as UTF-8 CSV, apply `filter`, project the fields.
3. Check each value against spec R4.1 to R4.3. The build **fails** on an invalid value (non-NFC, control character, surrounding whitespace); it never normalizes or drops silently. Fixing data is the dataset's job.
4. Serialize each record to its canonical bytes: for `lines` the value; for `csv` the row as written by R4.3. In both cases without the trailing LF.
5. Deduplicate by canonical bytes. Sort ascending by bytes. This is the population; its serialization (records joined by LF, final LF, plus the header for `csv`) gives `population.sha256`.
6. Compute `scripts` (ISO 15924 per record, by the predominant script of its letters; `Zyyy` when no letter), using the same rule as `dataset-names` R1 so the numbers agree. For `csv` inputs, over the first string field.

## 4. Sampling algorithms (normative detail of spec R3)

Notation: `S` = seed as ASCII bytes; `||` = concatenation; `H` = SHA-256; `r` = canonical record bytes; scores are compared as 32-byte unsigned big-endian integers (plain byte-wise comparison).

**`hash-order`** (without replacement)

```
score(r) = H(S || 0x00 || r)
sample(n) = the n records with the smallest score, ascending; ties by r ascending
```

Ties need equal digests of different records, so in practice they never happen, but the rule keeps the algorithm total. Because the order is fixed for the whole population, `sample(n)` is a prefix of `sample(m)` for `n < m` (spec R3.5). Cost: one hash per record and a sort, fine for millions of records.

**`hash-index`** (with replacement)

```
N = population size, population in canonical order (section 3, step 5)
for i in 0 .. n-1:
    d = H(S || 0x00 || ascii_decimal(i))       # "0", "1", ... no leading zeros
    x = first 8 bytes of d as unsigned big-endian 64-bit integer
    record_i = population[x mod N]
```

The modulo bias is below N / 2^64 and does not affect reproducibility. Record `i` depends only on `i`, so samples are nested.

Both algorithms only need SHA-256, byte comparison and 64-bit unsigned arithmetic, available in every language the catalogs use. The `0x00` separator prevents ambiguity between seed and record because neither may contain NUL.

## 5. Release layout

Example for a `dataset-names` release `2026.10` (dataset artifacts first, unchanged):

```
manifest.json                       dataset's own manifest (dataset-names spec 001, R5)
given_names.csv, family_names.csv, by_country/…, *.parquet
names-given-names.input.json        input manifest (spec R2)
names-given-names-1k.txt
names-given-names-10k.txt
names-given-names-100k.txt
names-given-names-dup.input.json
names-given-names-dup-1k.txt  …
DATA_LICENSE                        data license text (CC BY 4.0 for dataset-names)
ATTRIBUTION.txt                     one block per upstream source: name, license, required text; then notices
SHA256SUMS                          `sha256sum` format, every asset
```

`DATA_LICENSE` and `ATTRIBUTION.txt` are generated from the dataset repo (its `DATA_LICENSE` and `sources.yaml`), so they cannot drift from the source registry.

## 6. Licensing mapping

- `license` is the dataset's data license as SPDX: `dataset-names` → `CC-BY-4.0`.
- `attribution` is built from the source registry entries whose `source_id` contributes at least one population record. For `dataset-names` this needs the `sources` column of `given_names.csv` / `family_names.csv`. Upstream license ids are mapped to SPDX where one exists (`CC-BY-4.0`, `etalab-2.0`) and to `LicenseRef-` otherwise (`public-domain` → `LicenseRef-Public-Domain`, `statcan-open-licence` → `LicenseRef-StatCan-Open-Licence`). The mapping table lives in this repo and the build fails on an unknown id.
- `notices` carries text the upstream terms require beyond attribution. For `dataset-names` that is the Statistics Canada conditions notice already in its README (ADR 0004 of that repo).
- `legacy/` of `dataset-names` is never an upstream (its content has no license grant and includes non-commercial IMDb data).
- The license of this repo's code is pending the org decision in .product ADR 0003; it does not affect the data.

## 7. Schemas

- `schema/inputs-definition.schema.json`: `inputs.yaml` (section 2).
- `schema/input-manifest.schema.json`: spec R2, with `contract_version` pattern, size name pattern, 64-hex checksums, `record.format` enum and the `lines`-has-one-field rule.
- `schema/input-reference.schema.json`: spec R7.1. benchmark-tool#29 references this file by URL at a tag of this repo.

All three use JSON Schema 2020-12, so consumers in any language can validate without this tool.

## 8. Test vectors

`vectors/` holds language-neutral cases: a population file (with Latin, Cyrillic, Han and Arabic records, one with a space and one with an apostrophe), a seed, and for each method the expected sample files and their SHA-256 for a few sizes, plus the expected scores of the first records. A second implementation proves conformance by reproducing them. Changing a vector is a major contract change (spec R6.3).

## 9. Reference implementation (proposal)

- **Language and tooling:** Python 3.12, `uv`, `pytest`, packaged with `hatchling`, the same stack as `dataset-names`, so dataset maintainers need nothing new. Only the standard library is needed for hashing, Unicode normalization and CSV; dependencies: `pyyaml`, `jsonschema`, `license-expression` (SPDX parsing).
- **CLI** `dataset-tool` (names are proposals):
  - `dataset-tool build --dataset <repo dir> --release-dir <dir with the dataset release> --out <dir>`: reads `inputs.yaml`, writes samples, manifests, license files and `SHA256SUMS`.
  - `dataset-tool validate <dir>`: rules V1 to V10; V5 rebuilds from the upstream artifact in the same directory.
  - `dataset-tool vectors --check`: runs the implementation against `vectors/`.
- **Layout:** `src/datasettool/{definition,population,sampling,formats,manifest,licensing,validate,cli}.py`, `tests/`, `schema/`, `vectors/`.
- **Use from dataset repos:** pinned by tag, for example `uvx --from git+https://github.com/BenchCommons/tools-dataset@vX.Y.Z dataset-tool build …`, where `vX.Y.Z` is the first tag that ships this CLI (`v0.1.0` is the source toolkit of spec 004 and has no CLI). A reusable release workflow comes in spec 002.
- **Tests never use the network**, as in `dataset-names`.

## 10. Decisions

| # | Decision | Alternatives rejected | Reason |
|---|---|---|---|
| D1 | Inputs are assets of the dataset repo's release; input version = release tag | Releases in dataset-tool; a separate `inputs` repo | Data, license and attribution stay with the repo that owns them; one tag pins both dataset and inputs. |
| D2 | Hash-based sampling (SHA-256 of seed and record or index) | A seeded PRNG (Mersenne Twister, PCG) | Any language reproduces it with only SHA-256; no PRNG to reimplement bit-exactly. |
| D3 | Samples are nested prefixes | Independent samples per size | Results across sizes compare the same records; smaller samples are cheap checks of larger ones. |
| D4 | Text formats only (`lines`, `csv`), uncompressed | Parquet, gzip | Every language in the catalogs can read them without libraries; sizes up to `1m` are a few tens of MB. |
| D5 | Build fails on invalid data instead of cleaning it | Normalize or drop silently | Silent fixes would make the input differ from the dataset without trace. |
| D6 | `SHA256SUMS` in GNU format in addition to manifests | Manifests only | Verification with stock tools (spec R7.4). |
| D7 | Python reference implementation | Rust (like perfratio), Go | Same stack as dataset-names; consumers do not need the tool to fetch. |

D1 and D2 are cross-repo and long-lived, so they are also recorded as ADRs in `docs/adr/` (tasks T1).

## 11. Risks

- **dataset-names has no published release yet.** The fixture in acceptance criterion 5 is built from a hand-made subset of `given_names.csv` with the real header until the first release exists.
- **Python CSV quoting vs R4.3.** The writer is configured explicitly (minimal quoting, LF) and tested against vectors, not trusted by default.
- **Population size unknown for `1m`.** Validation V7 catches a too-large `hash-order` size at build time; the dataset spec picks sizes.
