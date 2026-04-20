"""Smoke probe: docling under pandas 3.0 override.

docling declares `pandas<3.0.0` but we force `pandas>=3.0`. This probe
verifies docling's import graph and a pandas-adjacent call path work
after the override.
"""
import pytest

pytest.importorskip("docling")


@pytest.mark.smoke
def test_docling_imports_cleanly():
    import docling
    from docling.document_converter import DocumentConverter

    assert DocumentConverter is not None


@pytest.mark.smoke
def test_docling_converter_instantiates():
    """DocumentConverter touches docling-core and pandas internals at construction."""
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    # No network, no file IO — just construction + minimal method access.
    assert hasattr(converter, "convert")
