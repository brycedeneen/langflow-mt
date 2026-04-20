"""Smoke tests for DoclingRemoteComponent — mocked Docling Serve HTTP."""

import base64
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.base.data import BaseFileComponent
from lfx.components.docling.docling_remote import DoclingRemoteComponent
from lfx.schema import Data


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestDoclingRemoteSmoke:
    def test_process_files_converts_file_via_mocked_http(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = DoclingRemoteComponent()
        component.api_url = "http://docling-serve.example:5001"
        component.max_concurrency = 1
        component.max_poll_timeout = 60.0
        component.api_headers = None
        component.docling_serve_opts = None

        doc_payload = DoclingDocument(name="smoke_doc").model_dump(mode="json")

        fake_client = MagicMock()
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = False
        fake_client.post.return_value = _FakeResponse(200, {"task_id": "t1", "task_status": "pending"})
        fake_client.get.side_effect = [
            _FakeResponse(200, {"task_id": "t1", "task_status": "success"}),
            _FakeResponse(200, {"document": {"json_content": doc_payload}}),
        ]

        # Real BaseFile signature: BaseFile(data, path, *, delete_after_processing=False)
        seed_data = Data(data={"file_path": str(pdf_path)})
        file_list = [BaseFileComponent.BaseFile(data=seed_data, path=pdf_path)]

        with patch("lfx.components.docling.docling_remote.httpx.Client", return_value=fake_client), \
             patch("lfx.components.docling.docling_remote.time.sleep"):
            result = component.process_files(file_list)

        assert len(result) == 1
        posted_payload = fake_client.post.call_args.kwargs["json"]
        assert posted_payload["sources"][0]["filename"] == "smoke.pdf"
        assert base64.b64decode(posted_payload["sources"][0]["base64_string"]) == b"%PDF-1.4\n%mocked\n"

    def test_process_files_returns_none_when_json_content_missing(self, tmp_path):
        pdf_path = tmp_path / "smoke.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%mocked\n")

        component = DoclingRemoteComponent()
        component.api_url = "http://docling-serve.example:5001"
        component.max_concurrency = 1
        component.max_poll_timeout = 60.0
        component.api_headers = None
        component.docling_serve_opts = None

        fake_client = MagicMock()
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = False
        fake_client.post.return_value = _FakeResponse(200, {"task_id": "t1", "task_status": "pending"})
        fake_client.get.side_effect = [
            _FakeResponse(200, {"task_id": "t1", "task_status": "success"}),
            _FakeResponse(200, {"document": {"json_content": None}}),
        ]

        seed_data = Data(data={"file_path": str(pdf_path)})
        file_list = [BaseFileComponent.BaseFile(data=seed_data, path=pdf_path)]

        with patch("lfx.components.docling.docling_remote.httpx.Client", return_value=fake_client), \
             patch("lfx.components.docling.docling_remote.time.sleep"):
            result = component.process_files(file_list)

        assert len(result) == 1
        assert result[0].data == []
