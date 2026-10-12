"""Spec 004, R1: package metadata and pinned runtime dependencies."""

import tomllib
from importlib.metadata import version
from pathlib import Path

import datasettool

PYPROJECT = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8"))


def test_version_comes_from_the_distribution():
    assert datasettool.__version__ == version("benchcommons-dataset-tool") == PYPROJECT["project"]["version"]


def test_runtime_dependencies_are_pinned():
    # ADR 0005: exactly these two, pinned; xlrd pin carried over from dataset-names ADR 0005.
    assert sorted(PYPROJECT["project"]["dependencies"]) == ["pyyaml==6.0.3", "xlrd==2.0.2"]
