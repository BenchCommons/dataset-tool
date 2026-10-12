# 001. The input contract

Issue: [#1](https://github.com/BenchCommons/tools-dataset/issues/1). Org contract index: [.product CONTRACTS.md](https://github.com/BenchCommons/.product/blob/main/CONTRACTS.md), row "Benchmark inputs". Roadmap: [`../ROADMAP.md`](../ROADMAP.md).

## Why

BenchCommons measures the same algorithm in many languages (`catalog-algorithms`). A comparison is only fair if every implementation reads byte-identical input, and if anyone can rebuild that input later and get the same bytes. Today each `dataset-*` repo publishes data in its own shape: `dataset-names` releases `given_names.csv`, `family_names.csv`, `by_country/<CC>.csv` and Parquet files with a `manifest.json`, which is right for a dataset but not for a benchmark that needs "100,000 names, one per line, in a fixed order".

This spec defines, once, the **input contract**: what a benchmark input is, how it is derived from a dataset release, how it is identified, encoded, checksummed, versioned, licensed and validated, and how a consumer declares and fetches it. `dataset-tool` owns the contract. `dataset-names` and `dataset-commons` produce inputs that follow it; `catalog-algorithms` and `benchmark-tool` consume them. Those repos reference this spec and never redefine it.

## Terms

- **Dataset release**: an immutable, versioned release of a `dataset-*` repo (for `dataset-names`, CalVer `YYYY.MM[.N]` with its own `manifest.json`).
- **Input**: a named, benchmark-ready view of a dataset release: one population of records, one record schema, one sampling method and one seed. Example: `names/given-names`.
- **Population**: the full, deduplicated set of records an input is drawn from.
- **Sample**: the input at one named size (for example `100k`). Each sample is one file.
- **Input manifest**: the JSON file that describes one input in one release (R2).
- **Input reference**: what a consumer writes to pin one sample.

## Requirements

### R1. Input identity

- **R1.1** An input id is `<dataset>/<name>`, where `<dataset>` is the repo name without the `dataset-` prefix and `<name>` matches `^[a-z0-9]+(-[a-z0-9]+)*$`. Example: `names/given-names`, `commons/english-words`.
- **R1.2** An input is defined by its dataset repo in a definition file (`inputs.yaml`, schema in the plan). The definition names the source artifact of the dataset release, the field(s) projected into records, the record format, the sampling method, the seed and the list of sizes.
- **R1.3** Inputs are never derived from material without a declared license. In `dataset-names` this excludes everything under `legacy/`.

### R2. Input manifest

Every input in a release has an input manifest, published as `<dataset>-<name>.input.json` (for example `names-given-names.input.json`), with at least:

| Field | Rule |
|---|---|
| `contract_version` | SemVer of this contract (starts at `1.0.0`). |
| `id` | Input id (R1.1). |
| `version` | The dataset release version the input is published in (R6). |
| `title`, `description` | Human-readable text, English. |
| `license` | SPDX license expression for the data, for example `CC-BY-4.0`. Licenses without an SPDX id use `LicenseRef-<name>`. |
| `attribution` | List of `{source, text, license}` copied from the dataset's source registry (for `dataset-names`, `sources.yaml`), one per upstream source that contributes records. `text` is the exact notice the upstream license requires, untranslated. |
| `notices` | Extra license conditions that must travel with the data (for example the Statistics Canada conditions notice), verbatim. May be empty. |
| `upstream` | `{repo, release, artifact, sha256}`: the dataset release artifact the population was built from. |
| `record` | Record schema: `format` (`lines` or `csv`), and `fields` as a list of `{name, type, description}`. `lines` has exactly one field. Types: `string`, `integer`, `decimal`. |
| `population` | `{records, sha256}`: size of the population and SHA-256 of its canonical serialization (R4.4). |
| `sampling` | `{method, seed}` (R3). |
| `samples` | Map from size name to `{records, bytes, sha256, file}` (R4, R5). |
| `scripts` | Map from ISO 15924 code to record count, computed over the population, so consumers know which writing systems appear. |

### R3. Deterministic samples by size

- **R3.1** Size names match `^[1-9][0-9]*(k|m)?$` and mean exact record counts in decimal SI: `1k` = 1,000, `100k` = 100,000, `1m` = 1,000,000. The default ladder is `1k`, `10k`, `100k`, `1m`; an input lists the sizes it publishes.
- **R3.2** The seed is a non-empty ASCII string fixed in the input definition. It is recorded in the manifest. Changing it changes the input and requires a new release.
- **R3.3** Sampling is language-independent: it uses only SHA-256 and integer arithmetic, never a language's random number generator, so any implementation can reproduce it from the manifest alone. The exact algorithms are in the plan.
- **R3.4** Two methods exist in contract 1.x:
  - `hash-order` (without replacement, the default): each population record gets a score from SHA-256 of the seed and the record; the sample of size *n* is the *n* records with the lowest scores, in ascending score order. Sizes larger than the population are invalid.
  - `hash-index` (with replacement): record *i* of the sample is the population record at an index computed from SHA-256 of the seed and *i*. Used when duplicates are wanted (deduplication, hashing with collisions). Any size is valid.
- **R3.5** Samples of the same input are nested: the sample of size *n* is the first *n* records of every larger sample. This holds for both methods.
- **R3.6** The record order in the file is the sampling order. It is not sorted, so sorting benchmarks start from a shuffled input.

### R4. File format and encoding

- **R4.1** Encoding is UTF-8 without BOM. Every text value is in Unicode NFC. Records keep their original script (Latin, Cyrillic, Han, Arabic and others); there is no transliteration unless the input definition projects an ASCII field (for example `dataset-names`' `ascii` column) into a separate input.
- **R4.2** Line terminator is LF (`\n`). There is no CR anywhere. The file ends with exactly one LF after the last record. Empty files are invalid.
- **R4.3** Two formats:
  - `lines` (`.txt`): one record per line, no header. A record is a non-empty string without LF, CR, NUL or other C0/C1 control characters, without leading or trailing whitespace.
  - `csv` (`.csv`): RFC 4180 with LF terminators, a header row with the field names from the manifest, comma separator. Values follow the same character rules as `lines` records, except that they may be empty. A value is quoted with `"` only when it contains a comma or a quote, and inner quotes are doubled. Integers are base-10 without separators or leading zeros; decimals use `.` and no exponent.
- **R4.4** The canonical serialization of the population is the population records in ascending order of their UTF-8 bytes, in the input's format. It is used only for `population.sha256`, so a rebuild can prove it started from the same population.
- **R4.5** Sample files are named `<dataset>-<name>-<size>.<ext>`, for example `names-given-names-100k.txt`. Files are published uncompressed.

### R5. Checksums

- **R5.1** Every published input file (each sample, each input manifest, the license and attribution files) has a SHA-256 checksum, lowercase hex.
- **R5.2** Sample checksums are recorded in the input manifest. The release also carries a `SHA256SUMS` file in the format of GNU `sha256sum` covering every asset, including each input manifest, so `sha256sum -c` works without any BenchCommons tool.
- **R5.3** A consumer pins the checksum of the sample file it reads. A mismatch is a hard failure; there is no fallback.

### R6. Versioned releases

- **R6.1** Inputs are published as assets of the dataset repo's GitHub Release, next to the dataset's own artifacts. The input version is that release's tag (for `dataset-names`, `YYYY.MM[.N]`).
- **R6.2** Releases are immutable. Any change in the bytes of any published input file, including a new seed, new sizes, or new upstream data, requires a new release tag. Retagging or replacing assets is forbidden.
- **R6.3** `contract_version` follows SemVer: removing or renaming a manifest field, changing a format rule or a sampling algorithm is a major bump; adding an optional field is a minor bump.
- **R6.4** Consumers pin an input by repo, release tag, input id, size and SHA-256 together. None of these alone is a valid pin.

### R7. Declaring and fetching an input

- **R7.1** An **input reference** is the object:

  ```json
  {"input": "names/given-names", "repo": "BenchCommons/dataset-names", "release": "2026.10", "size": "100k", "sha256": "<64 hex>"}
  ```

  This spec owns the shape of the reference. Where a catalog stores it (per-algorithm or per-implementation metadata) is decided by the catalog contract in [benchmark-tool#29](https://github.com/BenchCommons/benchmark-tool/issues/29), which references this object.
- **R7.2** The download URL is derived, never stored: `https://github.com/<repo>/releases/download/<release>/<file>`, with `<file>` from R4.5.
- **R7.3** Fetching means: download, compute SHA-256, compare with the pinned value, and only then expose the file to the benchmark. Fetched files are cached by checksum, so a cached file is reused only if its checksum matches. An offline run uses only the cache and fails if the file is missing.
- **R7.4** Fetching needs no BenchCommons tool: `curl` and `sha256sum` are enough. A fetch command in `dataset-tool` is a convenience (see the roadmap), not a requirement of the contract.
- **R7.5** How the measured program receives the file (path argument, stdin) belongs to the catalog contract. This contract only guarantees the bytes.

### R8. Validation

`dataset-tool validate` (name proposed in the plan) checks a release directory and rejects it, with a message naming the file and rule, when any of these fail:

- **V1** Each input manifest is valid against the manifest JSON Schema and `contract_version` is supported.
- **V2** Every sample file exists, and its byte size, record count and SHA-256 match the manifest.
- **V3** Encoding: valid UTF-8, no BOM, NFC, LF only, single trailing LF, no forbidden characters (R4.1 to R4.3).
- **V4** Format: `lines` records are non-empty and trimmed; `csv` has the exact header and the declared field count on every row, and values parse as their declared types.
- **V5** Determinism: rebuilding every sample from the upstream artifact, the definition, the method and the seed yields byte-identical files.
- **V6** Nesting (R3.5) holds between all sizes.
- **V7** `hash-order` sizes do not exceed `population.records`; `hash-order` samples contain no duplicate record.
- **V8** `upstream.sha256` matches the dataset release artifact, and that artifact's checksum matches the dataset's own manifest.
- **V9** Licensing: `license` is a valid SPDX expression (or `LicenseRef-`), `attribution` is non-empty and every source that contributes records has an entry, and the release carries the license and attribution files (R9).
- **V10** `SHA256SUMS` covers every asset and every line verifies.

### R9. Data licensing

- **R9.1** An input keeps the license of the dataset release it derives from. `dataset-tool` never relicenses data. For `dataset-names`, the data is CC BY 4.0 (`DATA_LICENSE`), while its code is Apache-2.0; the input's `license` is the data license, never the code license.
- **R9.2** Upstream attributions and notices travel with every input: in the input manifest, and in an attribution file and the data license file published in the same release. For `dataset-names`, this includes the Statistics Canada notice and its conditions notice, verbatim, as required by that repo's ADR 0004.
- **R9.3** A dataset whose registry contains a ShareAlike, NonCommercial or undeclared license for a contributing source cannot publish inputs until its own license decision allows it. The data license policy across datasets is the subject of [.product ADR 0003](https://github.com/BenchCommons/.product/blob/main/docs/adr/0003-default-branch-and-licenses.md); this contract only requires that the license is declared and preserved.
- **R9.4** Inputs carry no personal data beyond what the upstream release already publishes, and sampling never joins datasets.

## Acceptance criteria

1. The manifest JSON Schema and the input reference JSON Schema exist in this repo, and a fixture manifest for `names/given-names` validates against them.
2. Published test vectors (a small population, a seed, and the expected order and checksums for both methods) are reproduced exactly by the reference implementation; the vectors are documented well enough that a second implementation in another language can check itself against them.
3. Running the build twice on the same upstream artifact, on Linux and macOS, produces byte-identical samples and manifests.
4. The validator rejects, each with a specific message: a BOM, a CRLF, a missing trailing LF, a non-NFC record, a record with a control character, a wrong header, a size larger than the population under `hash-order`, a broken nesting, a checksum mismatch, a missing attribution, and an invalid SPDX expression.
5. A fixture built from a small subset of `dataset-names`' `given_names.csv` covering Latin, Cyrillic and Han names, and a name with a space, produces a `names/given-names` input whose `scripts` map and checksums match hand-checked values.
6. Following R7 with only `curl` and `sha256sum` fetches and verifies a sample from a GitHub Release, and a tampered file is rejected.
7. `CONTRACTS.md` in `.product` links to this spec for the "Benchmark inputs" row.

## Out of scope

- The list of datasets and inputs: `dataset-names` ([dataset-names#24](https://github.com/BenchCommons/dataset-names/issues/24)) and `dataset-commons` ([dataset-commons#1](https://github.com/BenchCommons/dataset-commons/issues/1)) define their own inputs in their own specs.
- The release pipeline that publishes inputs from the dataset repos, and the consumer fetch command (see [`../ROADMAP.md`](../ROADMAP.md)).
- Expected outputs, correctness checks and string collation used by algorithms (catalog-algorithms spec 010 and 012).
- Where catalogs store input references and how programs receive the file (catalog contract, benchmark-tool#29).
- Weighted sampling (by name frequency), binary formats (Parquet, Arrow) and compressed transport.
- Hosting outside GitHub Releases (mirrors, CDN).
