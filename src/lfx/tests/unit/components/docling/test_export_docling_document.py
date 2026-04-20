"""Smoke tests for ExportDoclingDocumentComponent."""

import pytest

pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.components.docling.export_docling_document import ExportDoclingDocumentComponent
from lfx.schema import Data


def _tiny_doc() -> DoclingDocument:
    return DoclingDocument(name="smoke_doc")


class TestExportDoclingDocumentSmoke:
    @pytest.mark.parametrize("export_format", ["Markdown", "HTML", "Plaintext", "DocTags"])
    def test_export_each_format_returns_data_object(self, export_format):
        component = ExportDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.export_format = export_format
        component.image_mode = "placeholder"
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""

        results = component.export_document()

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], Data)
        # Empty DoclingDocument renders an empty string in some formats (Plaintext especially);
        # the smoke assertion is that `.text` is a `str` and the call did not raise.
        assert isinstance(results[0].text, str)

    def test_export_dataframe_wraps_export_document(self):
        component = ExportDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.export_format = "Markdown"
        component.image_mode = "placeholder"
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""

        df = component.as_dataframe()

        assert len(df) == 1
