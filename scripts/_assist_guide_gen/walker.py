"""Walk component roots, yielding candidate files for guide generation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

EXCLUDED_DIRECTORY_NAMES: frozenset[str] = frozenset({"deactivated", "__pycache__"})


@dataclass(frozen=True)
class FileCandidate:
    path: Path          # absolute path to the .py file
    category: str       # top-level directory under the component root


def iter_candidate_files(root: Path) -> Iterator[FileCandidate]:
    """Yield every `.py` file under `root` eligible for guide generation.

    Excludes:
    - files whose name starts with `_` (internal/mixins) — including `__init__.py`
    - any file inside a directory whose name is in ``EXCLUDED_DIRECTORY_NAMES``
    """
    if not root.is_dir():
        return

    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.parts):
            continue
        rel = path.relative_to(root)
        if not rel.parts:
            continue
        yield FileCandidate(path=path, category=rel.parts[0])


def iter_all(roots: Iterable[Path]) -> Iterator[FileCandidate]:
    for root in roots:
        yield from iter_candidate_files(root)
