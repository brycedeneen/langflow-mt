"""Discovery + exclusion rule tests."""
from __future__ import annotations

from pathlib import Path

from scripts._assist_guide_gen.walker import (
    EXCLUDED_DIRECTORY_NAMES,
    FileCandidate,
    iter_candidate_files,
)


def _write(root: Path, rel: str, body: str = "class Foo: ...") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_excludes_files_starting_with_underscore(tmp_path: Path):
    _write(tmp_path, "processing/foo.py")
    _write(tmp_path, "processing/_private.py")
    files = list(iter_candidate_files(tmp_path))
    names = {f.path.name for f in files}
    assert "foo.py" in names
    assert "_private.py" not in names


def test_excludes_deactivated_directory(tmp_path: Path):
    _write(tmp_path, "deactivated/old.py")
    _write(tmp_path, "processing/keep.py")
    files = list(iter_candidate_files(tmp_path))
    paths = {str(f.path.relative_to(tmp_path)) for f in files}
    assert "processing/keep.py" in paths
    assert all("deactivated/" not in p for p in paths)


def test_excludes_dunder_init(tmp_path: Path):
    _write(tmp_path, "processing/__init__.py")
    _write(tmp_path, "processing/thing.py")
    names = {f.path.name for f in iter_candidate_files(tmp_path)}
    assert "__init__.py" not in names
    assert "thing.py" in names


def test_category_inferred_from_top_level_directory(tmp_path: Path):
    _write(tmp_path, "processing/text_ops.py")
    _write(tmp_path, "vectorstores/chroma/local.py")
    files = {str(f.path.relative_to(tmp_path)): f.category for f in iter_candidate_files(tmp_path)}
    assert files["processing/text_ops.py"] == "processing"
    assert files["vectorstores/chroma/local.py"] == "vectorstores"


def test_excluded_directory_names_covers_known_skips():
    assert "deactivated" in EXCLUDED_DIRECTORY_NAMES
