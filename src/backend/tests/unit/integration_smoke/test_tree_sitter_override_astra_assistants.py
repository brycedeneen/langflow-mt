"""Smoke probe: astra-assistants under tree-sitter 0.25 override.

astra-assistants 2.5.5 declares `tree-sitter<0.24.0` but we force
`tree-sitter>=0.25,<0.27` to satisfy docling-core 2.74[chunking].
Astra-assistants uses the modern Language()/Parser() API that is
compatible across both 0.23 and 0.25, so the override should be a
resolver lie with no runtime impact. This probe verifies that claim.
"""
import pytest

pytest.importorskip("astra_assistants")
pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_python")


@pytest.mark.smoke
def test_tree_sitter_modern_api_works_under_override():
    """astra-assistants uses Language(tspython.language()) + Parser(lang) — both valid in 0.25."""
    import importlib.metadata
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    # tree-sitter 0.25+ guarantee (tree_sitter module has no __version__ attr; use metadata)
    ts_version = importlib.metadata.version("tree-sitter")
    assert ts_version.startswith(("0.25", "0.26")), f"Unexpected tree-sitter version: {ts_version}"

    ts_language = Language(tspython.language())
    parser = Parser(ts_language)
    tree = parser.parse(b"x = 1\n")
    assert tree.root_node.type == "module"


@pytest.mark.smoke
def test_astra_assistants_structured_code_tools_import():
    """The two astra files that use tree-sitter directly must import cleanly."""
    from astra_assistants.tools.structured_code import indent as _indent  # noqa: F401
    from astra_assistants.tools.structured_code import util as _util  # noqa: F401
