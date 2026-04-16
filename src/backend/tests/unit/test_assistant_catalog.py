"""Tests for the assistant catalog tools.

These tools wrap ``langflow.agentic.utils.component_search`` into a
higher-level interface used by the AssistantService / MCP layer.

The tests use mocked component data so they run without a full Langflow
settings service or component registry.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from langflow.services.assistant.tools.catalog import (
    SCHEMA_FIELDS,
    SUMMARY_FIELDS,
    get_component_schema,
    list_categories,
    list_compatible_outputs,
    search_components,
)

# ---------------------------------------------------------------------------
# Fixtures — fake component data
# ---------------------------------------------------------------------------

FAKE_TYPES_DICT: dict[str, dict] = {
    "llms": {
        "OpenAIModel": {
            "display_name": "OpenAI",
            "description": "OpenAI LLM wrapper",
            "template": {"model_name": {}},
            "icon": "OpenAI",
            "is_input": False,
            "is_output": False,
            "output_types": ["Message"],
            "outputs": [{"name": "text_output", "types": ["Message"]}],
        },
        "AnthropicModel": {
            "display_name": "Anthropic",
            "description": "Anthropic Claude model",
            "template": {"model_name": {}},
            "icon": "Anthropic",
            "is_input": False,
            "is_output": False,
            "output_types": ["Message"],
            "outputs": [{"name": "text_output", "types": ["Message"]}],
        },
    },
    "embeddings": {
        "OpenAIEmbeddings": {
            "display_name": "OpenAI Embeddings",
            "description": "OpenAI embedding model",
            "template": {"model": {}},
            "icon": "OpenAI",
            "is_input": False,
            "is_output": False,
            "output_types": ["Embeddings"],
            "outputs": [{"name": "embeddings", "types": ["Embeddings"]}],
        },
    },
    "tools": {
        "SearchAPI": {
            "display_name": "Search API",
            "description": "Web search tool",
            "template": {"api_key": {}},
            "icon": "Search",
            "is_input": False,
            "is_output": False,
            "output_types": ["Data"],
            "outputs": [{"name": "results", "types": ["Data"]}],
        },
    },
}


@pytest.fixture(autouse=True)
def _mock_component_cache():
    """Patch the low-level cache loader to return our fake data."""
    with patch(
        "langflow.agentic.utils.component_search.get_and_cache_all_types_dict",
        new_callable=AsyncMock,
        return_value=FAKE_TYPES_DICT,
    ):
        yield


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_categories_returns_all():
    categories = await list_categories()
    names = {c["name"] for c in categories}
    assert names == {"llms", "embeddings", "tools"}


@pytest.mark.anyio
async def test_list_categories_has_name_and_count():
    categories = await list_categories()
    for cat in categories:
        assert "name" in cat
        assert "count" in cat
        assert isinstance(cat["count"], int)
        assert cat["count"] > 0


@pytest.mark.anyio
async def test_list_categories_counts_correct():
    categories = await list_categories()
    by_name = {c["name"]: c["count"] for c in categories}
    assert by_name["llms"] == 2
    assert by_name["embeddings"] == 1
    assert by_name["tools"] == 1


# ---------------------------------------------------------------------------
# search_components
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_components_all():
    results = await search_components()
    assert len(results) == 4  # 2 llms + 1 embedding + 1 tool


@pytest.mark.anyio
async def test_search_components_has_summary_fields():
    results = await search_components()
    for r in results:
        for field in SUMMARY_FIELDS:
            assert field in r, f"Missing field {field}"


@pytest.mark.anyio
async def test_search_components_by_query():
    results = await search_components(query="openai")
    names = {r["name"] for r in results}
    assert "OpenAIModel" in names
    assert "OpenAIEmbeddings" in names
    # Anthropic and SearchAPI should not match
    assert "AnthropicModel" not in names
    assert "SearchAPI" not in names


@pytest.mark.anyio
async def test_search_components_by_type():
    results = await search_components(component_type="llms")
    assert len(results) == 2
    assert all(r["type"] == "llms" for r in results)


@pytest.mark.anyio
async def test_search_components_by_query_and_type():
    results = await search_components(query="openai", component_type="llms")
    assert len(results) == 1
    assert results[0]["name"] == "OpenAIModel"


# ---------------------------------------------------------------------------
# get_component_schema
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_component_schema_known():
    schema = await get_component_schema("OpenAIModel")
    assert schema is not None
    assert schema["name"] == "OpenAIModel"
    assert schema["type"] == "llms"
    # Should contain schema-level fields
    for field in SCHEMA_FIELDS:
        if field in ("name", "type"):
            continue
        assert field in schema, f"Missing schema field {field}"


@pytest.mark.anyio
async def test_get_component_schema_unknown():
    schema = await get_component_schema("NonExistentComponent")
    assert schema is None


# ---------------------------------------------------------------------------
# list_compatible_outputs
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_compatible_outputs_message():
    matches = await list_compatible_outputs("Message")
    names = {m["name"] for m in matches}
    assert "OpenAIModel" in names
    assert "AnthropicModel" in names
    # Embeddings and tools output different types
    assert "OpenAIEmbeddings" not in names
    assert "SearchAPI" not in names


@pytest.mark.anyio
async def test_list_compatible_outputs_embeddings():
    matches = await list_compatible_outputs("Embeddings")
    names = {m["name"] for m in matches}
    assert "OpenAIEmbeddings" in names
    assert len(names) == 1


@pytest.mark.anyio
async def test_list_compatible_outputs_no_match():
    matches = await list_compatible_outputs("UnknownType")
    assert matches == []


@pytest.mark.anyio
async def test_list_compatible_outputs_result_shape():
    matches = await list_compatible_outputs("Message")
    expected_keys = {"name", "display_name", "type", "description", "output_types"}
    for m in matches:
        assert set(m.keys()) == expected_keys


@pytest.mark.anyio
async def test_list_compatible_outputs_case_insensitive():
    matches = await list_compatible_outputs("message")
    names = {m["name"] for m in matches}
    assert "OpenAIModel" in names
