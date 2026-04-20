"""Smoke tests for ChunkDoclingDocumentComponent.

The existing test file at
src/backend/tests/unit/components/docling/test_chunk_docling_document_component.py
covers only the UI-config show/hide logic. This file exercises the actual
chunking pipeline end-to-end against a tiny synthetic DoclingDocument.
"""

import pytest

pytest.importorskip("tiktoken")
pytest.importorskip("docling_core")

from docling_core.types.doc import DoclingDocument

from lfx.components.docling.chunk_docling_document import ChunkDoclingDocumentComponent
from lfx.schema import Data


def _tiny_doc() -> DoclingDocument:
    return DoclingDocument(name="smoke_doc")


class TestChunkDoclingDocumentSmoke:
    def test_hierarchical_chunker_returns_dataframe(self):
        component = ChunkDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.chunker = "HierarchicalChunker"
        # HybridChunker-only fields, set to defaults (unused for HierarchicalChunker):
        component.provider = "Hugging Face"
        component.hf_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        component.openai_model_name = "gpt-4o"
        component.max_tokens = None
        component.merge_peers = True
        component.always_emit_headings = False

        df = component.chunk_documents()

        # An empty DoclingDocument yields 0 chunks; the smoke check is that
        # the method completes and returns a DataFrame.
        assert hasattr(df, "columns")

    def test_hybrid_chunker_openai_provider_returns_dataframe(self):
        """OpenAI tokenizer path requires tiktoken but not network — good smoke coverage."""
        component = ChunkDoclingDocumentComponent()
        component.data_inputs = Data(data={"doc": _tiny_doc(), "file_path": "synthetic.md"})
        component.doc_key = "doc"
        component.chunker = "HybridChunker"
        component.provider = "OpenAI"
        component.hf_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        component.openai_model_name = "gpt-4o"
        component.max_tokens = None
        component.merge_peers = True
        component.always_emit_headings = False

        df = component.chunk_documents()

        assert hasattr(df, "columns")
