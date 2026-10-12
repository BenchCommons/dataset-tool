# 004. The source toolkit: plan

Spec: [`spec.md`](spec.md). Tasks: [`tasks.md`](tasks.md). Origin of the ported code: `BenchCommons/dataset-names@e7e8405` (`master`, 2026-10-12).

## 1. Layout

```
pyproject.toml                    benchcommons-tools-dataset 0.1.0, hatchling, pins (ADR 0003, 0005)
uv.lock, .python-version (3.12)
LICENSE                           Apache-2.0, the same text as dataset-names
src/datasettool/__init__.py       __version__ from the installed distribution
src/datasettool/files.py          sha256_file, count_csv_records, describe_files (spec R6)
src/datasettool/sources/__init__.py
src/datasettool/sources/adapters.py     Resource, SourceFiles, errors, checks, parse_count/parse_code (R4)
src/datasettool/sources/cache.py        fetch_resource and friends (R2)
src/datasettool/sources/spreadsheet.py  sheet_names, rows, cell_count (R3)
src/datasettool/sources/registry.py     Field, RegistrySchema, Source, load_registry (R5)
tests/conftest.py                 LocalServer on 127.0.0.1 (ported from dataset-names tests/conftest.py)
tests/example_adapters/           test-only adapter package (load_adapter tests)
tests/names_registry.py           test-only registry schema with dataset-names' fields (acceptance criterion 3)
tests/fixtures/spreadsheets/types.xls   synthetic XLS, byte-identical copy of dataset-names tests/fixtures/planilhas/tipos.xls
tests/test_*.py
```

Dependency direction inside the package: `cache`, `registry` and `spreadsheet` import `adapters` (for `Resource`, `FormatError`, `is_http_url`, `parse_count`); `adapters` imports nothing from the package. `files` is independent.

## 2. Module contracts

Signatures are the public API of `v0.1.0`. Messages are English translations of the dataset-names messages; the tests match on them.

### 2.1 `datasettool.sources.adapters`

```python
class AdapterError(Exception)
class FormatError(ValueError)
@dataclass(frozen=True) class Resource: url: str; filename: str
class SourceFiles(dict)                      # __missing__ -> AdapterError listing available files
def module_name(source_id: str) -> str       # "us-ssa-births" -> "us_ssa_births"
def is_http_url(url: object) -> bool         # never raises
def is_safe_filename(name: object) -> bool
def check_adapter(mod: object, source_id: str, optional: Iterable[str] = ()) -> None
def load_adapter(source_id: str, package: str, optional: Iterable[str] = ()) -> ModuleType
def parse_count(value: str, missing: Collection[str] = (), field: str = "count") -> int | None
def parse_code(value: str, mapping: Mapping[str, str], field: str) -> str
```

Generic records: the module docstring states the adapter protocol (`SOURCE_ID`, `RESOURCES`, `parse(files) -> Iterator[R]`) and that `R` is the dataset's own type (`RawRecord` and `RawLink` in dataset-names). `package` has no default: the toolkit does not know where a dataset keeps its adapters. `optional` lists extra functions a dataset's protocol allows (dataset-names: `("links",)`); each is checked only for callability when present. The absent/broken distinction is kept exactly: `ModuleNotFoundError` whose `name` is the adapter module or one of its parents means absent; any other exception, including a `ModuleNotFoundError` for a different module, means broken.

### 2.2 `datasettool.sources.cache`

```python
class FetchError(Exception)
class BlockedError(FetchError)
DEFAULT_USER_AGENT: str                       # "tools-dataset/<version> (+https://github.com/BenchCommons/tools-dataset)"
def make_user_agent(name: str, version: str, url: str) -> str   # "<name>/<version> (+<url>)"
def cached_path(cache_dir: Path, source_id: str, filename: str) -> Path
def fetch_resource(cache_dir, source_id, resource, *, refresh=False, offline=False, timeout=60.0,
                   attempts=3, backoff=None, sleep=time.sleep, user_agent=None) -> Path
```

`attempts`, `backoff` and `sleep` are the dataset-names parameters `tentativas`, `espera` and `dormir`; `backoff=None` means 2.0 s. `user_agent=None` means `DEFAULT_USER_AGENT`; dataset-names passes `make_user_agent("namescommons", <its version>, "https://github.com/BenchCommons/dataset-names")`, which reproduces its current header byte for byte. The manual-download hints say "rerun with --offline": dataset CLIs keep the `--offline` and `--refresh` flag names.

### 2.3 `datasettool.sources.spreadsheet`

```python
def sheet_names(path) -> list[str]
def rows(path, sheet) -> Iterator[tuple[int, list]]
def cell_count(value, missing: Iterable[str] = (), field: str = "count") -> int | None
```

A straight port of `namescommons.spreadsheet` at `dataset-names@eaaa4d1` (PR #39, which adds the UTF-8/UTF-16 encoding guard and the expat-level DTD refusal through `xml.parsers.expat` and `ElementTree.TreeBuilder`), limits unchanged (`_MAX_MEMBER` 1 GiB, ratio 100:1 above 1 MiB, prologue 64 KiB, 16,384 columns). Private names are translated; the tests that monkeypatch `_MAX_MEMBER`, `_events` and `_prologue` follow the new names.

### 2.4 `datasettool.sources.registry`

```python
ID_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
ATTRIBUTION_ONLY_LICENSES: frozenset[str]     # ADR 0006
class RegistryError(ValueError)

@dataclass(frozen=True)
class Field:
    name: str
    check: Callable[[object], str | None] | None = None   # returns an error text or None
    required: bool = True
    default: object = None                                 # used when optional and absent

@dataclass(frozen=True)
class Source:                                 # the default factory's result
    id: str; name: str; url: str; license: str; attribution: str; retrieved: date
    adapter: bool = True
    extra: Mapping[str, object] = {}          # dataset fields, read-only

@dataclass(frozen=True)
class RegistrySchema(Generic[S]):
    accepted_licenses: frozenset[str]
    license_policy: str                       # e.g. "ADR 0001", shown in the licence error
    fields: tuple[Field, ...] = ()
    checks: tuple[Callable[[Mapping[str, S]], Iterable[str]], ...] = ()
    factory: Callable[[dict], S] = Source.from_entry

def parse_registry(entries: list, schema: RegistrySchema[S]) -> dict[str, S]
def load_registry(path: Path, schema: RegistrySchema[S]) -> dict[str, S]
```

Validation order per entry: not a mapping; missing required fields (generic, then dataset fields; stop this entry); unknown fields; empty strings; `id` format; `url`; licence; `retrieved`; `adapter`; then each dataset field's `check` in declaration order. This differs from dataset-names, which checks its own fields (`country`, `count_type`, `primary`, `suppression`) between the licence and `retrieved`, and `uniform_case` before `adapter`: the set of messages is the same, only their order inside a multi-error `RegistryError` changes. The adoption ([#5](https://github.com/BenchCommons/tools-dataset/issues/5)) must not assert on that order. An entry with any error is not built. Duplicate ids are reported. Then each cross-entry check runs over the entries that were built, and every message is collected into one `RegistryError`. A schema whose `accepted_licenses` is empty, or a dataset field that redefines a generic field or is declared twice, raises `ValueError` when the schema is created; a `str` given for `accepted_licenses`, `fields` or `checks` (or for `optional` in `check_adapter`) raises `TypeError`, and the collections are coerced to `frozenset` and tuples. The default `Source` is hashable; `extra` is left out of the hash.

How dataset-names maps onto it (the test-only `tests/names_registry.py` is exactly this, with a fixed set of country codes instead of `pycountry`):

| dataset-names field | Toolkit |
|---|---|
| `id`, `name`, `url`, `license`, `attribution`, `retrieved`, `adapter` | generic |
| `country`, `count_type`, `primary`, `suppression` | `Field(..., required=True)` with dataset checks |
| `uniform_case` | `Field("uniform_case", check=boolean, required=False, default=False)` |
| one primary per (country, count type), except `attested` | `checks` |
| `LICENCAS_COMPATIVEIS` | `ATTRIBUTION_ONLY_LICENSES \| {"statcan-open-licence"}`, policy "ADR 0001" |
| `Source` dataclass | `factory` building dataset-names' own `Source` |

### 2.5 `datasettool.files`

```python
def sha256_file(path) -> str
def count_csv_records(path) -> int
def describe_files(root, exclude: Collection[str] = ("manifest.json",),
                   counters: Mapping[str, Callable[[Path], int]] = {".csv": count_csv_records}) -> dict[str, dict]
```

`describe_files` is the file loop of dataset-names' `build_manifest`; dataset-names registers `{".parquet": <pyarrow counter>}` itself. The release format, `schema_version` and the `sources` list of the names manifest stay in dataset-names.

## 3. Port map

Tests are ported with their inputs and expected values unchanged (spec R7.1). Names in parentheses are the dataset-names tests.

| dataset-names test file | Ported to | Not ported (stays in dataset-names) |
|---|---|---|
| `tests/test_cache.py` (all 22 tests) | `tests/test_cache.py`; the User-Agent test checks the default and the explicit dataset-names header | none |
| `tests/test_spreadsheet.py` (at `eaaa4d1`, PR #39) | `tests/test_spreadsheet.py`, all tests | `test_r1_3_amostras_do_ine` (INE adapter samples, CC BY 4.0 data of dataset-names) |
| `tests/test_adapters.py` | `tests/test_adapters.py`: module name, valid adapter, the 15 invalid-adapter cases, missing attribute, loading a test adapter (renamed to `example` with English file names), absent adapter | `test_parse_da_fixture_sem_rede` (uses `RawRecord`), `test_pacote_padrao_ainda_nao_tem_adaptadores` (names default package) |
| `tests/test_contrato_adaptador.py` | `parse_count`, `parse_code`, `SourceFiles`, absent adapter path, broken adapter, missing package | R2.1, R2.3, R2.5 and the ingest test (names pipeline) |
| `tests/test_sources.py`, `tests/test_sources_extensoes.py` (all) | `tests/test_registry.py` through `tests/names_registry.py` | none |
| `tests/test_manifest.py` | `tests/test_files.py` (`count_csv_records`) | none |
| `tests/test_robustez.py` | `test_manifesto_conta_registros_csv_e_nao_linhas_fisicas` → `tests/test_files.py` (`describe_files`) | the other tests (aggregation, Parquet, names manifest) |
| `tests/conftest.py` | `LocalServer` and the `server` fixture | names observations fixtures, `servir_fixtures` |

New tests cover what is new in the toolkit: `optional` callables, the schema rules of R5.4 and R5.5 (no licence list, redefined generic field, custom factory), `describe_files` with an unknown suffix and a custom counter, `DEFAULT_USER_AGENT`, and that `pyproject.toml` pins `xlrd==2.0.2` and `pyyaml==6.0.3`.

## 4. CI

`.github/workflows/ci.yml` keeps the `docs` job and adds:

- `tests`: `actions/checkout@v4`, `astral-sh/setup-uv@v6`, `uv sync --locked`, `uv run pytest -q`.
- `install-from-git`: in an empty directory, `uv init --bare --python 3.12`, `uv add "benchcommons-tools-dataset @ git+https://github.com/<repo>@<head sha>"`, then `uv run python -c "import datasettool.files, datasettool.sources.adapters, …"`. On a pull request the head SHA is `github.event.pull_request.head.sha`; on a push, `github.sha`.

## 5. Release

After the pull request merges, the maintainer tags the merge commit on `main`:

```sh
git tag -s v0.1.0 <merge sha> -m "benchcommons-tools-dataset 0.1.0 (spec 004)"
git push origin v0.1.0
```

and checks acceptance criterion 4 at the tag in an empty directory:

```sh
uv init --bare --python 3.12 && uv add "benchcommons-tools-dataset @ git+https://github.com/BenchCommons/tools-dataset@v0.1.0"
uv run python -c "import datasettool.sources.cache, datasettool.sources.spreadsheet, datasettool.sources.adapters, datasettool.sources.registry, datasettool.files"
```

Issue #5 (dataset-names adoption) starts only after the tag exists.

## 6. Decisions

| # | Decision | Alternatives rejected | Reason |
|---|---|---|---|
| D1 | Distribution `benchcommons-tools-dataset`, import `datasettool` (ADR 0003) | `benchcommons-dataset-tool` (the pre-rename repo name), `dataset_tool` | Matches the repo name (.product ADR 0005) and spec 001's `src/datasettool/`; org prefix avoids collisions. |
| D2 | uv git source pinned to a tag (ADR 0004) | PyPI, release wheels, vendoring | Reproducible through `uv.lock` with no publishing infrastructure. |
| D3 | Accepted licences are per dataset, with a shared `ATTRIBUTION_ONLY_LICENSES` starting set (ADR 0006) | One org-wide list | Compatibility depends on each dataset's data licence; .product ADR 0003 is still proposed. |
| D4 | Registry extension by `Field` list, cross-entry checks and a factory | Subclassing a base `Source`; JSON Schema | Keeps dataset-names' typed `Source` and its exact messages; no new dependency. |
| D5 | Messages and identifiers translated to English | Keep Portuguese | This repo's language convention; vectors (inputs and expected values) stay identical. |
| D6 | INE spreadsheet samples stay in dataset-names; the synthetic `tipos.xls` moves (as `types.xls`) | Copy the INE samples | They are adapter fixtures carrying CC BY 4.0 data with attribution; the reader is fully covered by synthetic files. |
| D7 | `describe_files` refuses files without a registered counter | Count unknown files as CSV (dataset-names' fallback) | A generic tool cannot guess; a wrong row count would go unnoticed. |
| D8 | No CLI in this spec | Port `fetch` | The CLIs differ per dataset; spec 001 owns the CLI. |

## 7. Risks

- **Translated messages break consumers that match text.** dataset-names tests match Portuguese messages; its adoption (issue #5) updates those assertions or keeps its own wrappers. The adoption spec in dataset-names decides.
- **Spec 001 builds on the same package.** Its task T2 (project skeleton) is delivered here; 001 adds its dependencies through its own ADR when it starts.
- **Overlap with `tools-commons`.** [.product ADR 0005](https://github.com/BenchCommons/.product/blob/main/docs/adr/0005-tools-prefix.md) creates `tools-commons` for code shared by several tools, and its scope issue ([tools-commons#1](https://github.com/BenchCommons/tools-commons/issues/1)) lists retry wrappers for flaky downloads. The toolkit stays here because its consumers are the `dataset-*` repos ([ADR 0007](../../adr/0007-source-toolkit-lives-in-tools-dataset.md)); if `tools-benchmark` needs the download cache, moving it is a `tools-commons` spec, and this package then depends on it.
- **GitHub fetch by SHA in CI.** The install job fetches the PR head commit by SHA from GitHub; if that ever fails, the fallback is a `git+file://` URL to the checkout, which still proves installability from git.
