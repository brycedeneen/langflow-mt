"""Smoke tests for DoclingInlineComponent — mocked docling_worker to avoid 15+ min model loads."""

from unittest.mock import patch

import pytest

pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.base.data import BaseFileComponent
from lfx.components.docling.docling_inline import DoclingInlineComponent
from lfx.schema import Data


def _make_component() -> DoclingInlineComponent:
    component = DoclingInlineComponent()
    component.pipeline = "standard"
    component.ocr_engine = "None"
    component.do_picture_classification = False
    component.pic_desc_llm = None
    component.pic_desc_prompt = "unused"
    return component


def _make_file(pdf_path):
    seed = Data(data={"file_path": str(pdf_path)})
    return BaseFileComponent.BaseFile(data=seed, path=pdf_path)


class TestDoclingInlineSmoke:
    def test_process_files_rollup_maps_worker_results(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = _make_component()
        file_list = [_make_file(pdf_path)]

        synthetic = DoclingDocument(name="smoke_doc")

        def fake_worker(*, queue, file_paths, **kwargs):  # noqa: ARG001
            queue.put(
                [
                    {
                        "document": synthetic,
                        "file_path": str(pdf_path),
                        "status": "SUCCESS",
                    }
                ]
            )

        with patch("lfx.components.docling.docling_inline.docling_worker", side_effect=fake_worker):
            result = component.process_files(file_list)

        assert len(result) == 1

    def test_process_files_raises_on_dependency_error(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = _make_component()
        file_list = [_make_file(pdf_path)]

        def fake_worker(*, queue, **kwargs):  # noqa: ARG001
            queue.put(
                {
                    "error": "tesserocr is not correctly installed. pip install tesserocr",
                    "error_type": "dependency_error",
                    "dependency_name": "tesserocr",
                }
            )

        with patch("lfx.components.docling.docling_inline.docling_worker", side_effect=fake_worker):
            with pytest.raises(ImportError, match="tesserocr"):
                component.process_files(file_list)

    def test_process_files_empty_list_skips_worker(self):
        component = _make_component()

        with patch("lfx.components.docling.docling_inline.docling_worker") as worker:
            result = component.process_files([])

        assert result == []
        worker.assert_not_called()
