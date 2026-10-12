"""Spec 004, R6: file checksums and row counts.

Ported from BenchCommons/dataset-names@e7e8405 tests/test_manifest.py and
tests/test_robustez.py (test_manifesto_conta_registros_csv_e_nao_linhas_fisicas). Test vectors unchanged.
"""

import hashlib

import pytest

from datasettool.files import count_csv_records, describe_files, sha256_file


@pytest.mark.parametrize("content, expected", [
    ("", 0),
    ("a,b\n", 0),
    ("a,b\n1,2\n", 1),
    ("a,b\n1,2\n\n", 1),
    ("a,b\n1,2\n\n\n3,4\n", 2),
    ('a,b\n"x\ny",2\n', 1),
])
def test_csv_rows_exclude_header_and_blank_lines(tmp_path, content, expected):
    path = tmp_path / "t.csv"
    path.write_text(content, encoding="utf-8")
    assert count_csv_records(path) == expected


def test_describe_files_counts_csv_records_not_physical_lines(tmp_path):
    (tmp_path / "x.csv").write_text('name,nota\n"Ana","linha 1\nlinha 2"\nBia,ok\n', encoding="utf-8")
    assert describe_files(tmp_path)["x.csv"]["rows"] == 2


def test_sha256_file_reads_in_blocks(tmp_path):
    data = b"x" * (3 * (1 << 20) + 7)
    (tmp_path / "big.bin").write_bytes(data)
    assert sha256_file(tmp_path / "big.bin") == hashlib.sha256(data).hexdigest()


def test_describe_files_maps_posix_paths_sorted_and_excludes_the_manifest(tmp_path):
    (tmp_path / "by_country").mkdir()
    (tmp_path / "by_country" / "PT.csv").write_text("name\nMaria\n", encoding="utf-8")
    (tmp_path / "a.csv").write_text("name\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    files = describe_files(tmp_path)
    assert list(files) == ["a.csv", "by_country/PT.csv"]
    assert files["by_country/PT.csv"] == {"sha256": hashlib.sha256(b"name\nMaria\n").hexdigest(), "rows": 1}
    assert files["a.csv"]["rows"] == 0


def test_file_without_a_counter_is_refused(tmp_path):
    (tmp_path / "observations.parquet").write_bytes(b"PAR1")
    with pytest.raises(ValueError, match="observations.parquet: no row counter for '.parquet'"):
        describe_files(tmp_path)


def test_dataset_registers_its_own_counter(tmp_path):
    (tmp_path / "observations.parquet").write_bytes(b"PAR1")
    (tmp_path / "x.csv").write_text("a\n1\n", encoding="utf-8")
    files = describe_files(tmp_path, counters={".csv": count_csv_records, ".parquet": lambda p: 42})
    assert files["observations.parquet"]["rows"] == 42 and files["x.csv"]["rows"] == 1


def test_custom_exclusions(tmp_path):
    (tmp_path / "SHA256SUMS").write_text("", encoding="utf-8")
    (tmp_path / "x.csv").write_text("a\n", encoding="utf-8")
    assert list(describe_files(tmp_path, exclude=("SHA256SUMS",))) == ["x.csv"]
