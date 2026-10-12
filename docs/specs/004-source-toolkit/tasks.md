# 004. The source toolkit: tasks

Spec: [`spec.md`](spec.md). Plan: [`plan.md`](plan.md). Each task is one commit with its tests passing (test first). Port commits name their origin: `ported from BenchCommons/dataset-names@e7e8405 <path>`.

- [ ] **T1. Spec and ADRs.** `spec.md`, ADRs 0003 to 0006, roadmap row. Done when committed.
- [ ] **T2. Package skeleton and CI.** `pyproject.toml` (plan section 1), `.python-version`, `uv.lock`, `LICENSE`, `src/datasettool/__init__.py`, `src/datasettool/sources/__init__.py`, `tests/conftest.py` with the local HTTP server, the `tests` and `install-from-git` CI jobs, `AGENTS.md` and `README.md` with stack and commands. Tests: `__version__` equals the distribution version; `pyproject.toml` pins `xlrd==2.0.2` and `pyyaml==6.0.3`. This also delivers spec 001's T2 skeleton.
- [ ] **T3. Adapter base.** `datasettool.sources.adapters` (plan 2.1). Tests: the adapter rows of the port map, plus `optional` callables.
- [ ] **T4. Download cache.** `datasettool.sources.cache` (plan 2.2). Tests: the 22 ported cache tests, plus `DEFAULT_USER_AGENT` and the dataset-names header through `make_user_agent`.
- [ ] **T5. Spreadsheet reader.** `datasettool.sources.spreadsheet` (plan 2.3) and `tests/fixtures/spreadsheets/types.xls`. Tests: the ported spreadsheet tests.
- [ ] **T6. Source registry.** `datasettool.sources.registry` (plan 2.4) and `tests/names_registry.py`. Tests: every test of dataset-names' `test_sources.py` and `test_sources_extensoes.py` through the names schema, plus schema rules (no licence list, redefined generic field, generic `Source` with `extra`, custom factory).
- [ ] **T7. File helpers.** `datasettool.files` (plan 2.5). Tests: the ported row-count vectors, `describe_files` with quoted multi-line CSV, an excluded manifest, an unknown suffix and a custom counter.
- [ ] **T8. Acceptance.** Run the suite; install from the pushed branch by git URL in an empty `uv` project and import every module; tick the tasks; open the pull request (closes #4).
- [ ] **T9. Release tag (maintainer, after merge).** Tag `v0.1.0` on the merge commit and run the check of plan section 5. Then issue #5 can start.
