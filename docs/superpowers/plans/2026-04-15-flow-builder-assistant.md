# Flow Builder Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an in-app AI co-pilot that understands Langflow components and can add/connect/configure them on the user's canvas via natural language.

**Architecture:** Backend proxy model — the LLM call runs server-side with the org's API key, streams SSE events to a dockable side panel. Read-only component catalog is exposed via MCP (reusable by external clients). Flow mutations are in-process Python functions that go through the existing flow service. Per-flow conversation persisted in DB.

**Tech Stack:** Python/FastAPI (backend), SQLModel/Alembic (DB), MCP SDK (catalog), OpenAI + Anthropic SDKs (providers), React/TypeScript/Zustand (frontend), SSE via `sse-starlette` (streaming).

**Spec:** `docs/superpowers/specs/2026-04-15-flow-builder-assistant-design.md`

---

## File Structure

### Backend (all under `src/backend/base/langflow/`)

| File | Responsibility |
|------|----------------|
| `services/assistant/__init__.py` | Package init, exports |
| `services/assistant/service.py` | `AssistantService` — orchestrates tool loop, streaming, persistence |
| `services/assistant/context_window.py` | Message packing by token budget |
| `services/assistant/providers/__init__.py` | Provider exports |
| `services/assistant/providers/base.py` | `ProviderClient` ABC + `FakeProviderClient` for tests |
| `services/assistant/providers/openai_provider.py` | OpenAI tool-calling adapter |
| `services/assistant/providers/anthropic_provider.py` | Anthropic tool-calling adapter |
| `services/assistant/tools/__init__.py` | Tool exports |
| `services/assistant/tools/catalog.py` | Read-only catalog tools (wraps `agentic/utils/component_search`) |
| `services/assistant/tools/mutation.py` | `FlowMutationTools` — add/connect/set/remove/sticky |
| `services/assistant/tools/registry.py` | Collects all tools, converts to provider-native format |
| `services/assistant/mcp_server.py` | MCP server exposing catalog tools for external clients |
| `services/database/models/assistant/__init__.py` | Model exports |
| `services/database/models/assistant/model.py` | `AssistantConversation` + `AssistantMessage` SQLModel |
| `api/v1/assistant.py` | REST + SSE endpoints |
| `alembic/versions/xxxx_add_assistant_tables.py` | Migration |

### Frontend (all under `src/frontend/src/`)

| File | Responsibility |
|------|----------------|
| `stores/assistantStore.ts` | Panel state, conversation, streaming |
| `controllers/API/queries/assistant.ts` | API client hooks (React Query + raw fetch for SSE) |
| `modals/AssistantPanel/index.tsx` | Panel shell with docking |
| `modals/AssistantPanel/components/panel-header.tsx` | Title, collapse, clear |
| `modals/AssistantPanel/components/message-list.tsx` | Scrollable message history |
| `modals/AssistantPanel/components/message.tsx` | Single message bubble |
| `modals/AssistantPanel/components/tool-call-card.tsx` | Collapsed tool invocation |
| `modals/AssistantPanel/components/composer.tsx` | Text input + send |
| `modals/AssistantPanel/components/settings-required.tsx` | Empty state |
| `modals/AssistantPanel/hooks/use-assistant-stream.ts` | SSE parser + event dispatch |
| `modals/AssistantPanel/hooks/use-assistant-conversation.ts` | Load history on mount |
| `pages/SettingsPage/pages/AssistantSettingsPage/index.tsx` | Provider/model/key config |

### Tests

| File | Responsibility |
|------|----------------|
| `src/backend/tests/unit/test_assistant_models.py` | DB model unit tests |
| `src/backend/tests/unit/test_assistant_catalog.py` | Catalog tool tests |
| `src/backend/tests/unit/test_assistant_mutation.py` | Mutation tool tests |
| `src/backend/tests/unit/test_assistant_context_window.py` | Context packing tests |
| `src/backend/tests/unit/test_assistant_service.py` | Service tool-loop tests (fake provider) |
| `src/backend/tests/integration/test_assistant_api.py` | API endpoint integration tests |

---

## Task 1: Database Models + Migration

**Files:**
- Create: `src/backend/base/langflow/services/database/models/assistant/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/assistant/model.py`
- Create: Alembic migration (auto-generated)

- [x] **Step 1: Write the failing test for model creation**

Create `src/backend/tests/unit/test_assistant_models.py`:

```python
from uuid import uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.assistant.model import (
    AssistantConversation,
    AssistantMessage,
)


@pytest.mark.asyncio
async def test_create_conversation(session: AsyncSession):
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    session.add(conv)
    await session.flush()
    await session.refresh(conv)

    assert conv.id is not None
    assert conv.flow_id == flow_id
    assert conv.org_id == org_id
    assert conv.created_at is not None
    assert conv.updated_at is not None


@pytest.mark.asyncio
async def test_create_message(session: AsyncSession):
    flow_id = uuid4()
    org_id = uuid4()
    user_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    session.add(conv)
    await session.flush()
    await session.refresh(conv)

    msg = AssistantMessage(
        conversation_id=conv.id,
        user_id=user_id,
        role="user",
        content="Add an OpenAI LLM to my flow",
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)

    assert msg.id is not None
    assert msg.conversation_id == conv.id
    assert msg.role == "user"
    assert msg.content == "Add an OpenAI LLM to my flow"
    assert msg.tool_calls is None
    assert msg.created_at is not None


@pytest.mark.asyncio
async def test_create_tool_message(session: AsyncSession):
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    session.add(conv)
    await session.flush()
    await session.refresh(conv)

    msg = AssistantMessage(
        conversation_id=conv.id,
        user_id=None,
        role="tool",
        content=None,
        tool_call_id="call_abc123",
        tool_result={"node_id": "OpenAIModel-x1y2z", "applied_patch": {"added_nodes": []}},
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)

    assert msg.role == "tool"
    assert msg.user_id is None
    assert msg.tool_call_id == "call_abc123"
    assert msg.tool_result["node_id"] == "OpenAIModel-x1y2z"


@pytest.mark.asyncio
async def test_conversation_messages_ordered(session: AsyncSession):
    conv = AssistantConversation(flow_id=uuid4(), org_id=uuid4())
    session.add(conv)
    await session.flush()
    await session.refresh(conv)

    for i in range(3):
        msg = AssistantMessage(
            conversation_id=conv.id, role="user", content=f"msg {i}"
        )
        session.add(msg)

    await session.flush()

    result = await session.exec(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conv.id)
        .order_by(AssistantMessage.created_at)
    )
    messages = result.all()
    assert len(messages) == 3
    assert [m.content for m in messages] == ["msg 0", "msg 1", "msg 2"]
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'langflow.services.database.models.assistant'`

- [x] **Step 3: Implement the models**

Create `src/backend/base/langflow/services/database/models/assistant/__init__.py`:

```python
from langflow.services.database.models.assistant.model import (
    AssistantConversation,
    AssistantMessage,
)

__all__ = ["AssistantConversation", "AssistantMessage"]
```

Create `src/backend/base/langflow/services/database/models/assistant/model.py`:

```python
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, DateTime, Field, Index, Relationship, SQLModel, Text, func


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AssistantConversation(SQLModel, table=True):
    __tablename__ = "assistant_conversation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(index=True, unique=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    created_at: datetime = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        ),
    )
    messages: list["AssistantMessage"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class AssistantMessage(SQLModel, table=True):
    __tablename__ = "assistant_message"
    __table_args__ = (
        Index("ix_assistant_message_conv_created", "conversation_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(foreign_key="assistant_conversation.id", index=True)
    user_id: UUID | None = Field(default=None)
    role: str = Field(max_length=20)
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tool_calls: dict | list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    tool_call_id: str | None = Field(default=None, max_length=255)
    tool_result: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    conversation: AssistantConversation = Relationship(back_populates="messages")
```

- [x] **Step 4: Register the model in the database models `__init__`**

Add the import to `src/backend/base/langflow/services/database/models/__init__.py` so alembic sees it. Find where other models are imported and add:

```python
from langflow.services.database.models.assistant import AssistantConversation, AssistantMessage  # noqa: F401
```

- [x] **Step 5: Generate and review alembic migration**

Run:
```bash
cd src/backend/base && python -m alembic revision --autogenerate -m "add_assistant_conversation_and_message_tables"
```

Review the generated migration file. It should create `assistant_conversation` and `assistant_message` tables with all columns and indices.

- [x] **Step 6: Run migration and tests**

Run:
```bash
cd src/backend/base && python -m alembic upgrade head
cd src/backend && python -m pytest tests/unit/test_assistant_models.py -v
```
Expected: All 4 tests PASS.

- [x] **Step 7: Commit**

```bash
git add src/backend/base/langflow/services/database/models/assistant/ \
        src/backend/base/langflow/alembic/versions/*assistant* \
        src/backend/tests/unit/test_assistant_models.py
git commit -m "feat(assistant): add conversation + message DB models and migration"
```

---

## Task 2: Catalog Tools (Read-Only Component Knowledge)

**Files:**
- Create: `src/backend/base/langflow/services/assistant/__init__.py`
- Create: `src/backend/base/langflow/services/assistant/tools/__init__.py`
- Create: `src/backend/base/langflow/services/assistant/tools/catalog.py`
- Test: `src/backend/tests/unit/test_assistant_catalog.py`

These wrap the existing `agentic/utils/component_search.py` functions into a tool-friendly interface.

- [x] **Step 1: Write the failing tests**

Create `src/backend/tests/unit/test_assistant_catalog.py`:

```python
import pytest

from langflow.services.assistant.tools.catalog import (
    list_categories,
    search_components,
    get_component_schema,
    list_compatible_outputs,
)


@pytest.mark.asyncio
async def test_list_categories():
    result = await list_categories()
    assert isinstance(result, list)
    assert len(result) > 0
    for cat in result:
        assert "name" in cat
        assert "count" in cat


@pytest.mark.asyncio
async def test_search_components_by_query():
    result = await search_components(query="openai")
    assert isinstance(result, list)
    for comp in result:
        assert "name" in comp
        assert "display_name" in comp
        assert "type" in comp
        assert "description" in comp


@pytest.mark.asyncio
async def test_search_components_by_type():
    result = await search_components(component_type="llms")
    assert isinstance(result, list)
    assert len(result) > 0
    for comp in result:
        assert comp["type"] == "llms"


@pytest.mark.asyncio
async def test_get_component_schema():
    components = await search_components(query="openai")
    if not components:
        pytest.skip("No OpenAI component found")
    name = components[0]["name"]
    schema = await get_component_schema(component_name=name)
    assert schema is not None
    assert "name" in schema
    assert "template" in schema
    assert "inputs" in schema or "template" in schema


@pytest.mark.asyncio
async def test_get_component_schema_not_found():
    result = await get_component_schema(component_name="NonExistentComponent12345")
    assert result is None


@pytest.mark.asyncio
async def test_list_compatible_outputs():
    result = await list_compatible_outputs(input_type="Message")
    assert isinstance(result, list)
    for comp in result:
        assert "name" in comp
        assert "output_types" in comp or "type" in comp
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement catalog tools**

Create `src/backend/base/langflow/services/assistant/__init__.py`:

```python
```

Create `src/backend/base/langflow/services/assistant/tools/__init__.py`:

```python
```

Create `src/backend/base/langflow/services/assistant/tools/catalog.py`:

```python
from __future__ import annotations

from typing import Any

from langflow.agentic.utils.component_search import (
    get_all_component_types,
    get_component_by_name,
    get_components_by_type,
    get_components_count,
    list_all_components,
)

SUMMARY_FIELDS = ["name", "display_name", "type", "description"]
SCHEMA_FIELDS = ["name", "display_name", "type", "description", "template", "icon", "is_input", "is_output"]


async def list_categories() -> list[dict[str, Any]]:
    """List all component categories with counts."""
    types = await get_all_component_types()
    result = []
    for t in types:
        count = await get_components_count(component_type=t)
        result.append({"name": t, "count": count})
    return result


async def search_components(
    query: str | None = None,
    component_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search components by query string and/or type. Returns summary fields."""
    return await list_all_components(
        query=query,
        component_type=component_type,
        fields=SUMMARY_FIELDS,
    )


async def get_component_schema(component_name: str) -> dict[str, Any] | None:
    """Get full schema for a component including template (inputs/outputs)."""
    return await get_component_by_name(
        component_name=component_name,
        fields=SCHEMA_FIELDS,
    )


async def list_compatible_outputs(input_type: str) -> list[dict[str, Any]]:
    """Find components that can produce a given output type."""
    all_components = await list_all_components(
        fields=["name", "display_name", "type", "description", "template"],
    )
    compatible = []
    for comp in all_components:
        template = comp.get("template", {})
        outputs = template.get("outputs", []) if isinstance(template, dict) else []
        output_types = set()
        if isinstance(outputs, list):
            for out in outputs:
                if isinstance(out, dict):
                    for ot in out.get("types", []):
                        output_types.add(ot)
        if input_type in output_types:
            compatible.append({
                "name": comp["name"],
                "display_name": comp.get("display_name", comp["name"]),
                "type": comp["type"],
                "description": comp.get("description", ""),
                "output_types": sorted(output_types),
            })
    return compatible
```

- [x] **Step 4: Run tests**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_catalog.py -v`
Expected: All tests PASS (or some skip if no OpenAI component is registered in the test environment).

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/assistant/ \
        src/backend/tests/unit/test_assistant_catalog.py
git commit -m "feat(assistant): add catalog tools wrapping component search"
```

---

## Task 3: MCP Server for Catalog Tools

**Files:**
- Create: `src/backend/base/langflow/services/assistant/mcp_server.py`

This exposes the catalog tools as an MCP server, reusable by Claude Desktop/Cursor/external clients.

- [x] **Step 1: Implement the MCP server**

Create `src/backend/base/langflow/services/assistant/mcp_server.py`:

```python
from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server import Server

from langflow.services.assistant.tools.catalog import (
    get_component_schema,
    list_categories,
    list_compatible_outputs,
    search_components,
)

server = Server("langflow-components-catalog")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_categories",
            description="List all Langflow component categories with counts. Use this first to understand what kinds of components are available.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="search_components",
            description="Search for Langflow components by name/description or filter by category type. Returns name, display_name, type, and description for each match.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term to match against name, display_name, description"},
                    "component_type": {"type": "string", "description": "Filter by category (e.g. 'llms', 'vectorstores', 'embeddings')"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_component_schema",
            description="Get the full schema for a specific component, including its template with all inputs/outputs and their types. Use after search_components to drill into a specific component.",
            inputSchema={
                "type": "object",
                "properties": {
                    "component_name": {"type": "string", "description": "Exact component name from search results"},
                },
                "required": ["component_name"],
            },
        ),
        types.Tool(
            name="list_compatible_outputs",
            description="Find all components whose outputs include a given type. Useful for figuring out what can connect to a given input.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_type": {"type": "string", "description": "The input type to match (e.g. 'Message', 'Document', 'Embeddings')"},
                },
                "required": ["input_type"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    arguments = arguments or {}

    if name == "list_categories":
        result = await list_categories()
    elif name == "search_components":
        result = await search_components(
            query=arguments.get("query"),
            component_type=arguments.get("component_type"),
        )
    elif name == "get_component_schema":
        result = await get_component_schema(
            component_name=arguments["component_name"],
        )
    elif name == "list_compatible_outputs":
        result = await list_compatible_outputs(
            input_type=arguments["input_type"],
        )
    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    return [types.TextContent(type="text", text=json.dumps(result, default=str))]
```

- [x] **Step 2: Register the MCP server in the API router**

Add an SSE transport endpoint for the catalog MCP server. Create or extend `src/backend/base/langflow/api/v1/assistant.py` (we'll add REST endpoints in a later task):

```python
from fastapi import APIRouter, Request, Response
from mcp.server.sse import SseServerTransport
from starlette.responses import StreamingResponse

from langflow.services.assistant.mcp_server import server as catalog_mcp_server

router = APIRouter(prefix="/assistant", tags=["Assistant"])

catalog_sse = SseServerTransport("/api/v1/assistant/catalog-mcp/messages/")


@router.get("/catalog-mcp/sse")
async def catalog_mcp_sse(request: Request) -> StreamingResponse:
    async with catalog_sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await catalog_mcp_server.run(
            streams[0], streams[1], catalog_mcp_server.create_initialization_options()
        )


@router.post("/catalog-mcp/messages/")
async def catalog_mcp_messages(request: Request) -> Response:
    await catalog_sse.handle_post_message(request.scope, request.receive, request._send)
    return Response(status_code=202)
```

- [x] **Step 3: Wire the router into the app**

Find where other routers are included (likely `src/backend/base/langflow/api/v1/__init__.py` or the app factory) and add:

```python
from langflow.api.v1.assistant import router as assistant_router
# ... in the router inclusion list:
app.include_router(assistant_router)
```

- [x] **Step 4: Manual smoke test**

Start the dev server and test with an MCP client or curl:
```bash
curl -N http://localhost:7860/api/v1/assistant/catalog-mcp/sse
```
Should see the SSE connection open and wait.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/assistant/mcp_server.py \
        src/backend/base/langflow/api/v1/assistant.py
git commit -m "feat(assistant): expose component catalog as MCP server"
```

---

## Task 4: Flow Mutation Tools

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/mutation.py`
- Test: `src/backend/tests/unit/test_assistant_mutation.py`

These are in-process Python functions that modify a flow's `data` (nodes/edges JSON). They do NOT directly write to DB — they mutate a dict and return patches. The caller (`AssistantService`) persists.

- [x] **Step 1: Write the failing tests**

Create `src/backend/tests/unit/test_assistant_mutation.py`:

```python
import copy

import pytest

from langflow.services.assistant.tools.mutation import FlowMutationTools

EMPTY_FLOW_DATA = {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}

FLOW_WITH_PROMPT = {
    "nodes": [
        {
            "id": "Prompt-abc12",
            "type": "genericNode",
            "position": {"x": 100, "y": 200},
            "data": {
                "type": "Prompt",
                "id": "Prompt-abc12",
                "node": {
                    "template": {
                        "template": {"type": "str", "value": "Hello {name}"},
                    },
                    "outputs": [{"types": ["Message"], "name": "output"}],
                },
                "output_types": ["Message"],
            },
        }
    ],
    "edges": [],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


def make_tools(flow_data: dict) -> FlowMutationTools:
    return FlowMutationTools(flow_data=copy.deepcopy(flow_data))


class TestAddComponent:
    def test_add_component_auto_position(self):
        tools = make_tools(EMPTY_FLOW_DATA)
        result = tools.add_component(component_type="OpenAIModel", position="auto")
        assert "node_id" in result
        assert result["node_id"].startswith("OpenAIModel-")
        patch = result["applied_patch"]
        assert len(patch["added_nodes"]) == 1
        node = patch["added_nodes"][0]
        assert node["data"]["type"] == "OpenAIModel"
        assert "position" in node

    def test_add_component_explicit_position(self):
        tools = make_tools(EMPTY_FLOW_DATA)
        result = tools.add_component(
            component_type="OpenAIModel",
            position={"x": 300, "y": 400},
        )
        node = result["applied_patch"]["added_nodes"][0]
        assert node["position"] == {"x": 300, "y": 400}

    def test_add_component_with_initial_fields(self):
        tools = make_tools(EMPTY_FLOW_DATA)
        result = tools.add_component(
            component_type="OpenAIModel",
            position="auto",
            initial_fields={"model_name": "gpt-4o"},
        )
        node = result["applied_patch"]["added_nodes"][0]
        template = node["data"]["node"]["template"]
        assert template.get("model_name", {}).get("value") == "gpt-4o"

    def test_add_component_updates_flow_data(self):
        tools = make_tools(EMPTY_FLOW_DATA)
        tools.add_component(component_type="OpenAIModel", position="auto")
        assert len(tools.flow_data["nodes"]) == 1


class TestConnectEdge:
    def test_connect_edge(self):
        tools = make_tools(FLOW_WITH_PROMPT)
        add_result = tools.add_component(component_type="OpenAIModel", position="auto")
        target_id = add_result["node_id"]

        result = tools.connect_edge(
            source_node_id="Prompt-abc12",
            source_output="output",
            target_node_id=target_id,
            target_input="input",
        )
        assert "edge_id" in result
        patch = result["applied_patch"]
        assert len(patch["added_edges"]) == 1
        edge = patch["added_edges"][0]
        assert edge["source"] == "Prompt-abc12"
        assert edge["target"] == target_id

    def test_connect_edge_missing_node(self):
        tools = make_tools(FLOW_WITH_PROMPT)
        with pytest.raises(ValueError, match="not found"):
            tools.connect_edge(
                source_node_id="NonExistent-xyz",
                source_output="output",
                target_node_id="Prompt-abc12",
                target_input="input",
            )


class TestSetFieldValue:
    def test_set_field_value(self):
        tools = make_tools(FLOW_WITH_PROMPT)
        result = tools.set_field_value(
            node_id="Prompt-abc12",
            field_name="template",
            value="Goodbye {name}",
        )
        assert result["updated_node_id"] == "Prompt-abc12"
        node = tools.flow_data["nodes"][0]
        assert node["data"]["node"]["template"]["template"]["value"] == "Goodbye {name}"

    def test_set_field_value_missing_node(self):
        tools = make_tools(FLOW_WITH_PROMPT)
        with pytest.raises(ValueError, match="not found"):
            tools.set_field_value(node_id="nope", field_name="x", value="y")


class TestRemoveComponent:
    def test_remove_component(self):
        tools = make_tools(FLOW_WITH_PROMPT)
        result = tools.remove_component(node_id="Prompt-abc12")
        assert result["removed_node_id"] == "Prompt-abc12"
        assert len(tools.flow_data["nodes"]) == 0

    def test_remove_component_removes_connected_edges(self):
        tools = make_tools(FLOW_WITH_PROMPT)
        add_result = tools.add_component(component_type="OpenAIModel", position="auto")
        tools.connect_edge(
            source_node_id="Prompt-abc12",
            source_output="output",
            target_node_id=add_result["node_id"],
            target_input="input",
        )
        assert len(tools.flow_data["edges"]) == 1
        tools.remove_component(node_id="Prompt-abc12")
        assert len(tools.flow_data["edges"]) == 0


class TestAddStickyNote:
    def test_add_sticky_note(self):
        tools = make_tools(EMPTY_FLOW_DATA)
        result = tools.add_sticky_note(
            content="TODO: Set your API key",
            position={"x": 50, "y": 50},
        )
        assert "node_id" in result
        node = result["applied_patch"]["added_nodes"][0]
        assert node["type"] == "noteNode"
        assert "TODO: Set your API key" in str(node["data"])
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_mutation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement mutation tools**

Create `src/backend/base/langflow/services/assistant/tools/mutation.py`:

```python
from __future__ import annotations

from typing import Any
from uuid import uuid4


def _short_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:5]}"


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    for n in nodes:
        if n["id"] == node_id:
            return n
    return None


def _auto_position(nodes: list[dict]) -> dict[str, int]:
    if not nodes:
        return {"x": 100, "y": 200}
    max_x = max(n.get("position", {}).get("x", 0) for n in nodes)
    avg_y = sum(n.get("position", {}).get("y", 0) for n in nodes) // max(len(nodes), 1)
    return {"x": max_x + 300, "y": avg_y}


class FlowMutationTools:
    def __init__(self, flow_data: dict):
        self.flow_data = flow_data
        if "nodes" not in self.flow_data:
            self.flow_data["nodes"] = []
        if "edges" not in self.flow_data:
            self.flow_data["edges"] = []

    def add_component(
        self,
        component_type: str,
        position: dict[str, int] | str = "auto",
        initial_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        node_id = _short_id(component_type)
        if position == "auto":
            position = _auto_position(self.flow_data["nodes"])

        template = {}
        if initial_fields:
            for k, v in initial_fields.items():
                template[k] = {"type": "str", "value": v}

        node = {
            "id": node_id,
            "type": "genericNode",
            "position": position,
            "data": {
                "type": component_type,
                "id": node_id,
                "node": {
                    "template": template,
                    "outputs": [],
                },
                "output_types": [],
            },
        }

        self.flow_data["nodes"].append(node)
        return {
            "node_id": node_id,
            "applied_patch": {"added_nodes": [node], "added_edges": [], "updated_nodes": [], "removed_ids": []},
        }

    def connect_edge(
        self,
        source_node_id: str,
        source_output: str,
        target_node_id: str,
        target_input: str,
    ) -> dict[str, Any]:
        source_node = _find_node(self.flow_data["nodes"], source_node_id)
        if source_node is None:
            raise ValueError(f"Source node '{source_node_id}' not found in flow")
        target_node = _find_node(self.flow_data["nodes"], target_node_id)
        if target_node is None:
            raise ValueError(f"Target node '{target_node_id}' not found in flow")

        edge_id = f"reactflow__edge-{source_node_id}{source_output}-{target_node_id}{target_input}"
        edge = {
            "id": edge_id,
            "source": source_node_id,
            "target": target_node_id,
            "sourceHandle": {
                "dataType": source_node["data"]["type"],
                "id": source_node_id,
                "name": source_output,
                "output_types": source_node["data"].get("output_types", []),
            },
            "targetHandle": {
                "fieldName": target_input,
                "id": target_node_id,
                "type": target_node["data"]["type"],
            },
            "data": {
                "sourceHandle": {
                    "dataType": source_node["data"]["type"],
                    "id": source_node_id,
                    "name": source_output,
                    "output_types": source_node["data"].get("output_types", []),
                },
                "targetHandle": {
                    "fieldName": target_input,
                    "id": target_node_id,
                    "type": target_node["data"]["type"],
                },
            },
        }

        self.flow_data["edges"].append(edge)
        return {
            "edge_id": edge_id,
            "applied_patch": {"added_nodes": [], "added_edges": [edge], "updated_nodes": [], "removed_ids": []},
        }

    def set_field_value(
        self, node_id: str, field_name: str, value: Any
    ) -> dict[str, Any]:
        node = _find_node(self.flow_data["nodes"], node_id)
        if node is None:
            raise ValueError(f"Node '{node_id}' not found in flow")

        template = node["data"]["node"].setdefault("template", {})
        if field_name in template and isinstance(template[field_name], dict):
            template[field_name]["value"] = value
        else:
            template[field_name] = {"type": "str", "value": value}

        return {
            "updated_node_id": node_id,
            "applied_patch": {"added_nodes": [], "added_edges": [], "updated_nodes": [node], "removed_ids": []},
        }

    def remove_component(self, node_id: str) -> dict[str, Any]:
        node = _find_node(self.flow_data["nodes"], node_id)
        if node is None:
            raise ValueError(f"Node '{node_id}' not found in flow")

        self.flow_data["nodes"] = [n for n in self.flow_data["nodes"] if n["id"] != node_id]

        removed_edges = [e for e in self.flow_data["edges"] if e["source"] == node_id or e["target"] == node_id]
        removed_edge_ids = [e["id"] for e in removed_edges]
        self.flow_data["edges"] = [e for e in self.flow_data["edges"] if e["id"] not in removed_edge_ids]

        return {
            "removed_node_id": node_id,
            "applied_patch": {
                "added_nodes": [],
                "added_edges": [],
                "updated_nodes": [],
                "removed_ids": [node_id] + removed_edge_ids,
            },
        }

    def add_sticky_note(
        self,
        content: str,
        position: dict[str, int] | str = "auto",
    ) -> dict[str, Any]:
        node_id = _short_id("note")
        if position == "auto":
            position = _auto_position(self.flow_data["nodes"])
            position["x"] -= 200
            position["y"] -= 150

        node = {
            "id": node_id,
            "type": "noteNode",
            "position": position,
            "width": 300,
            "height": 200,
            "data": {
                "type": "note",
                "id": node_id,
                "node": {
                    "description": content,
                    "template": {},
                },
            },
        }

        self.flow_data["nodes"].append(node)
        return {
            "node_id": node_id,
            "applied_patch": {"added_nodes": [node], "added_edges": [], "updated_nodes": [], "removed_ids": []},
        }
```

- [x] **Step 4: Run tests**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_mutation.py -v`
Expected: All tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/assistant/tools/mutation.py \
        src/backend/tests/unit/test_assistant_mutation.py
git commit -m "feat(assistant): add flow mutation tools (add/connect/set/remove/sticky)"
```

---

## Task 5: Tool Registry

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/registry.py`

Collects all tools (catalog + mutation) and converts to provider-native tool definitions.

- [x] **Step 1: Implement the tool registry**

Create `src/backend/base/langflow/services/assistant/tools/registry.py`:

```python
from __future__ import annotations

from typing import Any

CATALOG_TOOLS = [
    {
        "name": "list_categories",
        "description": "List all Langflow component categories with counts. Call this first to understand what kinds of components are available.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_components",
        "description": "Search for Langflow components by name/description or filter by category. Returns name, display_name, type, description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "component_type": {"type": "string", "description": "Category filter (e.g. 'llms', 'vectorstores')"},
            },
            "required": [],
        },
    },
    {
        "name": "get_component_schema",
        "description": "Get the full schema for a specific component including all inputs/outputs and types.",
        "parameters": {
            "type": "object",
            "properties": {
                "component_name": {"type": "string", "description": "Exact component name"},
            },
            "required": ["component_name"],
        },
    },
    {
        "name": "list_compatible_outputs",
        "description": "Find components whose outputs include a given type. Useful for figuring out what can connect to a given input.",
        "parameters": {
            "type": "object",
            "properties": {
                "input_type": {"type": "string", "description": "The input type (e.g. 'Message', 'Document')"},
            },
            "required": ["input_type"],
        },
    },
]

MUTATION_TOOLS = [
    {
        "name": "add_component",
        "description": "Add a new component node to the flow canvas. Use get_component_schema first to find the exact component_type name.",
        "parameters": {
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "Component type name (e.g. 'OpenAIModel')"},
                "position": {
                    "description": "'auto' to auto-position, or {x, y} coordinates",
                    "oneOf": [
                        {"type": "string", "enum": ["auto"]},
                        {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
                    ],
                },
                "initial_fields": {
                    "type": "object",
                    "description": "Field values to pre-populate (field_name → value)",
                    "additionalProperties": True,
                },
            },
            "required": ["component_type"],
        },
    },
    {
        "name": "connect_edge",
        "description": "Connect an output of one node to an input of another node.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_node_id": {"type": "string"},
                "source_output": {"type": "string", "description": "Output name on the source node"},
                "target_node_id": {"type": "string"},
                "target_input": {"type": "string", "description": "Input field name on the target node"},
            },
            "required": ["source_node_id", "source_output", "target_node_id", "target_input"],
        },
    },
    {
        "name": "set_field_value",
        "description": "Set a field value on an existing node in the flow.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "field_name": {"type": "string"},
                "value": {"description": "The value to set"},
            },
            "required": ["node_id", "field_name", "value"],
        },
    },
    {
        "name": "remove_component",
        "description": "Remove a node and all its connected edges from the flow.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "add_sticky_note",
        "description": "Add a sticky note to the flow canvas.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Note text (supports markdown)"},
                "position": {
                    "description": "'auto' or {x, y}",
                    "oneOf": [
                        {"type": "string", "enum": ["auto"]},
                        {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
                    ],
                },
            },
            "required": ["content"],
        },
    },
]

ALL_TOOLS = CATALOG_TOOLS + MUTATION_TOOLS


def get_tools_for_openai() -> list[dict[str, Any]]:
    """Return tools in OpenAI function-calling format."""
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in ALL_TOOLS
    ]


def get_tools_for_anthropic() -> list[dict[str, Any]]:
    """Return tools in Anthropic tool_use format."""
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in ALL_TOOLS
    ]


def is_catalog_tool(name: str) -> bool:
    return any(t["name"] == name for t in CATALOG_TOOLS)


def is_mutation_tool(name: str) -> bool:
    return any(t["name"] == name for t in MUTATION_TOOLS)
```

- [x] **Step 2: Commit**

```bash
git add src/backend/base/langflow/services/assistant/tools/registry.py
git commit -m "feat(assistant): add tool registry with provider-native format conversion"
```

---

## Task 6: Provider Base + Fake Provider

**Files:**
- Create: `src/backend/base/langflow/services/assistant/providers/__init__.py`
- Create: `src/backend/base/langflow/services/assistant/providers/base.py`

- [x] **Step 1: Define the provider interface and fake**

Create `src/backend/base/langflow/services/assistant/providers/__init__.py`:

```python
from langflow.services.assistant.providers.base import FakeProviderClient, ProviderClient

__all__ = ["FakeProviderClient", "ProviderClient"]
```

Create `src/backend/base/langflow/services/assistant/providers/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class StreamEvent:
    """A single event from the provider stream."""
    type: str  # "token", "tool_call", "tool_result_request", "message_complete", "error"
    text: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class ToolResult:
    tool_call_id: str
    content: str


class ProviderClient(ABC):
    @abstractmethod
    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        """Stream a single LLM turn. Yields StreamEvents. Stops at message end or tool_calls."""
        ...

    @abstractmethod
    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        """Continue after tool execution. Adds tool results to messages and streams next turn."""
        ...


@dataclass
class ScriptedTurn:
    """A scripted sequence of events the fake provider should emit."""
    events: list[StreamEvent] = field(default_factory=list)


class FakeProviderClient(ProviderClient):
    """Test double that replays scripted turns."""

    def __init__(self, turns: list[ScriptedTurn]):
        self._turns = list(turns)
        self._turn_index = 0

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        if self._turn_index >= len(self._turns):
            yield StreamEvent(type="error", error_message="No more scripted turns")
            return
        turn = self._turns[self._turn_index]
        self._turn_index += 1
        for event in turn.events:
            yield event

    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        if self._turn_index >= len(self._turns):
            yield StreamEvent(type="error", error_message="No more scripted turns")
            return
        turn = self._turns[self._turn_index]
        self._turn_index += 1
        for event in turn.events:
            yield event
```

- [x] **Step 2: Commit**

```bash
git add src/backend/base/langflow/services/assistant/providers/
git commit -m "feat(assistant): add provider ABC and fake provider for tests"
```

---

## Task 7: Context Window Packing

**Files:**
- Create: `src/backend/base/langflow/services/assistant/context_window.py`
- Test: `src/backend/tests/unit/test_assistant_context_window.py`

- [x] **Step 1: Write the failing tests**

Create `src/backend/tests/unit/test_assistant_context_window.py`:

```python
import pytest

from langflow.services.assistant.context_window import pack_messages


def _msg(role: str, content: str, tool_call_id: str | None = None, tool_calls: list | None = None) -> dict:
    m = {"role": role, "content": content}
    if tool_call_id:
        m["tool_call_id"] = tool_call_id
    if tool_calls:
        m["tool_calls"] = tool_calls
    return m


class TestPackMessages:
    def test_all_fit(self):
        messages = [_msg("user", "hi"), _msg("assistant", "hello")]
        result = pack_messages(messages, budget_tokens=1000, tokens_per_char=0.25)
        assert len(result) == 2

    def test_oldest_dropped_first(self):
        messages = [
            _msg("user", "a" * 400),
            _msg("assistant", "b" * 400),
            _msg("user", "c" * 100),
            _msg("assistant", "d" * 100),
        ]
        result = pack_messages(messages, budget_tokens=200, tokens_per_char=0.25)
        assert result[-1]["content"] == "d" * 100
        assert len(result) < 4

    def test_never_breaks_tool_call_pair(self):
        messages = [
            _msg("user", "old message " * 50),
            _msg("assistant", None, tool_calls=[{"id": "call_1", "function": {"name": "search"}}]),
            _msg("tool", "result data", tool_call_id="call_1"),
            _msg("assistant", "based on the result..."),
            _msg("user", "thanks"),
            _msg("assistant", "you're welcome"),
        ]
        result = pack_messages(messages, budget_tokens=200, tokens_per_char=0.25)
        roles = [m["role"] for m in result]
        if "tool" in roles:
            tool_idx = roles.index("tool")
            assert tool_idx > 0
            assert result[tool_idx - 1].get("tool_calls") is not None

    def test_empty_messages(self):
        assert pack_messages([], budget_tokens=1000, tokens_per_char=0.25) == []

    def test_single_message_too_large_still_included(self):
        messages = [_msg("user", "x" * 10000)]
        result = pack_messages(messages, budget_tokens=10, tokens_per_char=0.25)
        assert len(result) == 1
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_context_window.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement context window packing**

Create `src/backend/base/langflow/services/assistant/context_window.py`:

```python
from __future__ import annotations

from typing import Any


def _estimate_tokens(message: dict[str, Any], tokens_per_char: float) -> int:
    content = message.get("content") or ""
    tool_calls = message.get("tool_calls")
    tool_result = message.get("tool_result")
    text_len = len(str(content))
    if tool_calls:
        text_len += len(str(tool_calls))
    if tool_result:
        text_len += len(str(tool_result))
    return max(1, int(text_len * tokens_per_char))


def pack_messages(
    messages: list[dict[str, Any]],
    budget_tokens: int,
    tokens_per_char: float = 0.25,
) -> list[dict[str, Any]]:
    """Pack messages newest-first into a token budget.

    Never breaks tool-call/result pairs: if the oldest included message is
    role=tool, walks back to include the assistant message that triggered it.
    """
    if not messages:
        return []

    used = 0
    selected_indices: list[int] = []

    for i in range(len(messages) - 1, -1, -1):
        cost = _estimate_tokens(messages[i], tokens_per_char)
        if used + cost > budget_tokens and selected_indices:
            break
        used += cost
        selected_indices.append(i)

    selected_indices.reverse()

    if selected_indices:
        first_idx = selected_indices[0]
        msg = messages[first_idx]
        if msg.get("role") == "tool" and first_idx > 0:
            prev = messages[first_idx - 1]
            if prev.get("tool_calls"):
                selected_indices.insert(0, first_idx - 1)

    return [messages[i] for i in selected_indices]
```

- [x] **Step 4: Run tests**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_context_window.py -v`
Expected: All tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/assistant/context_window.py \
        src/backend/tests/unit/test_assistant_context_window.py
git commit -m "feat(assistant): add context window packing with tool-pair safety"
```

---

## Task 8: AssistantService

**Files:**
- Create: `src/backend/base/langflow/services/assistant/service.py`
- Test: `src/backend/tests/unit/test_assistant_service.py`

The core orchestrator: builds context, runs the tool loop, streams events, persists messages.

- [x] **Step 1: Write the failing tests**

Create `src/backend/tests/unit/test_assistant_service.py`:

```python
import json
from uuid import uuid4

import pytest

from langflow.services.assistant.providers.base import (
    FakeProviderClient,
    ScriptedTurn,
    StreamEvent,
)
from langflow.services.assistant.service import AssistantService

EMPTY_FLOW_DATA = {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


def _make_service(turns: list[ScriptedTurn], flow_data: dict | None = None) -> AssistantService:
    provider = FakeProviderClient(turns=turns)
    return AssistantService(
        provider_client=provider,
        flow_data=flow_data or EMPTY_FLOW_DATA.copy(),
        flow_id=uuid4(),
        org_id=uuid4(),
        user_id=uuid4(),
        model_name="fake-model",
    )


@pytest.mark.asyncio
async def test_simple_text_response():
    turns = [
        ScriptedTurn(events=[
            StreamEvent(type="token", text="Hello"),
            StreamEvent(type="token", text=" world"),
            StreamEvent(type="message_complete"),
        ])
    ]
    svc = _make_service(turns)
    events = []
    async for event in svc.send_message("Hi"):
        events.append(event)

    types = [e["type"] for e in events]
    assert "token" in types
    assert "message_complete" in types
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "Hello world"


@pytest.mark.asyncio
async def test_tool_call_and_response():
    turns = [
        ScriptedTurn(events=[
            StreamEvent(
                type="tool_call",
                tool_call_id="call_1",
                tool_name="list_categories",
                tool_args={},
            ),
        ]),
        ScriptedTurn(events=[
            StreamEvent(type="token", text="There are several categories."),
            StreamEvent(type="message_complete"),
        ]),
    ]
    svc = _make_service(turns)
    events = []
    async for event in svc.send_message("What components do you have?"):
        events.append(event)

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "message_complete" in types


@pytest.mark.asyncio
async def test_mutation_tool_emits_flow_patch():
    turns = [
        ScriptedTurn(events=[
            StreamEvent(
                type="tool_call",
                tool_call_id="call_1",
                tool_name="add_component",
                tool_args={"component_type": "OpenAIModel", "position": "auto"},
            ),
        ]),
        ScriptedTurn(events=[
            StreamEvent(type="token", text="Done!"),
            StreamEvent(type="message_complete"),
        ]),
    ]
    svc = _make_service(turns)
    events = []
    async for event in svc.send_message("Add an OpenAI LLM"):
        events.append(event)

    types = [e["type"] for e in events]
    assert "flow_patch" in types
    patch_event = next(e for e in events if e["type"] == "flow_patch")
    assert len(patch_event["patch"]["added_nodes"]) == 1


@pytest.mark.asyncio
async def test_error_in_provider():
    turns = [
        ScriptedTurn(events=[
            StreamEvent(type="error", error_message="Rate limit exceeded"),
        ])
    ]
    svc = _make_service(turns)
    events = []
    async for event in svc.send_message("Hi"):
        events.append(event)

    types = [e["type"] for e in events]
    assert "error" in types
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement AssistantService**

Create `src/backend/base/langflow/services/assistant/service.py`:

```python
from __future__ import annotations

import json
from typing import Any, AsyncIterator
from uuid import UUID

from langflow.services.assistant.context_window import pack_messages
from langflow.services.assistant.providers.base import ProviderClient, StreamEvent, ToolResult
from langflow.services.assistant.tools.catalog import (
    get_component_schema,
    list_categories,
    list_compatible_outputs,
    search_components,
)
from langflow.services.assistant.tools.mutation import FlowMutationTools
from langflow.services.assistant.tools.registry import (
    is_catalog_tool,
    is_mutation_tool,
)

SYSTEM_PROMPT_TEMPLATE = """You are Langflow Assistant, an AI co-pilot that helps users build and modify integration flows.

You have access to tools that let you:
- Search and discover Langflow components (LLMs, vector stores, loaders, agents, etc.)
- Add components to the user's flow canvas
- Connect components together by wiring edges
- Set field values on components
- Remove components
- Add sticky notes

Current flow state:
{canvas_summary}

When adding components:
1. First search for the right component using search_components or list_categories
2. Get its full schema with get_component_schema to understand inputs/outputs
3. Add it with add_component
4. Connect it with connect_edge
5. Pre-fill fields with set_field_value where you know good defaults

Always explain what you're doing and why."""

MODEL_CONTEXT_WINDOWS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-opus-4-20250514": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
}

DEFAULT_CONTEXT_WINDOW = 128_000
RESERVED_TOKENS = 16_000
MAX_OUTPUT_TOKENS = 4_096


def _build_canvas_summary(flow_data: dict) -> str:
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])
    if not nodes:
        return "The canvas is empty."
    summary_nodes = []
    for n in nodes:
        node_type = n.get("data", {}).get("type", "unknown")
        node_id = n.get("id", "?")
        summary_nodes.append(f"- {node_id} ({node_type})")
    summary_edges = []
    for e in edges:
        summary_edges.append(f"- {e.get('source', '?')} → {e.get('target', '?')}")
    parts = [f"Nodes ({len(nodes)}):", *summary_nodes]
    if edges:
        parts.extend([f"Edges ({len(edges)}):", *summary_edges])
    return "\n".join(parts)


class AssistantService:
    def __init__(
        self,
        provider_client: ProviderClient,
        flow_data: dict,
        flow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        model_name: str,
    ):
        self.provider = provider_client
        self.flow_data = flow_data
        self.mutation_tools = FlowMutationTools(flow_data)
        self.flow_id = flow_id
        self.org_id = org_id
        self.user_id = user_id
        self.model_name = model_name
        self._conversation_messages: list[dict[str, Any]] = []

    def set_conversation_history(self, messages: list[dict[str, Any]]) -> None:
        self._conversation_messages = list(messages)

    async def send_message(self, user_content: str) -> AsyncIterator[dict[str, Any]]:
        self._conversation_messages.append({"role": "user", "content": user_content})

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            canvas_summary=_build_canvas_summary(self.flow_data)
        )

        context_budget = MODEL_CONTEXT_WINDOWS.get(self.model_name, DEFAULT_CONTEXT_WINDOW) - RESERVED_TOKENS - MAX_OUTPUT_TOKENS
        windowed = pack_messages(self._conversation_messages, budget_tokens=context_budget)

        tools = self._get_tools()
        accumulated_text = ""

        max_tool_rounds = 10
        for _ in range(max_tool_rounds):
            pending_tool_calls: list[dict] = []

            async for event in self.provider.stream_with_tools(windowed, system_prompt, tools):
                if event.type == "token":
                    accumulated_text += event.text or ""
                    yield {"type": "token", "text": event.text}
                elif event.type == "tool_call":
                    pending_tool_calls.append({
                        "id": event.tool_call_id,
                        "name": event.tool_name,
                        "args": event.tool_args or {},
                    })
                    yield {"type": "tool_call", "id": event.tool_call_id, "name": event.tool_name, "args": event.tool_args}
                elif event.type == "message_complete":
                    if accumulated_text:
                        self._conversation_messages.append({"role": "assistant", "content": accumulated_text})
                    yield {"type": "message_complete", "message_id": None}
                    return
                elif event.type == "error":
                    yield {"type": "error", "message": event.error_message}
                    return

            if not pending_tool_calls:
                yield {"type": "message_complete", "message_id": None}
                return

            if accumulated_text:
                self._conversation_messages.append({"role": "assistant", "content": accumulated_text, "tool_calls": pending_tool_calls})
            else:
                self._conversation_messages.append({"role": "assistant", "content": None, "tool_calls": pending_tool_calls})
            accumulated_text = ""

            tool_results: list[ToolResult] = []
            for tc in pending_tool_calls:
                result = await self._execute_tool(tc["name"], tc["args"])
                tool_results.append(ToolResult(tool_call_id=tc["id"], content=json.dumps(result, default=str)))
                self._conversation_messages.append({"role": "tool", "content": json.dumps(result, default=str), "tool_call_id": tc["id"]})
                yield {"type": "tool_result", "id": tc["id"], "result": result}

                if is_mutation_tool(tc["name"]) and "applied_patch" in result:
                    yield {"type": "flow_patch", "patch": result["applied_patch"]}

            windowed = pack_messages(self._conversation_messages, budget_tokens=context_budget)

        yield {"type": "error", "message": "Too many tool rounds"}

    async def _execute_tool(self, name: str, args: dict) -> dict[str, Any]:
        try:
            if name == "list_categories":
                return {"categories": await list_categories()}
            elif name == "search_components":
                return {"components": await search_components(**args)}
            elif name == "get_component_schema":
                result = await get_component_schema(**args)
                return {"schema": result} if result else {"error": f"Component '{args.get('component_name')}' not found"}
            elif name == "list_compatible_outputs":
                return {"components": await list_compatible_outputs(**args)}
            elif name == "add_component":
                return self.mutation_tools.add_component(**args)
            elif name == "connect_edge":
                return self.mutation_tools.connect_edge(**args)
            elif name == "set_field_value":
                return self.mutation_tools.set_field_value(**args)
            elif name == "remove_component":
                return self.mutation_tools.remove_component(**args)
            elif name == "add_sticky_note":
                return self.mutation_tools.add_sticky_note(**args)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"error": str(e)}

    def _get_tools(self) -> list[dict[str, Any]]:
        from langflow.services.assistant.tools.registry import get_tools_for_openai
        return get_tools_for_openai()
```

- [x] **Step 4: Run tests**

Run: `cd src/backend && python -m pytest tests/unit/test_assistant_service.py -v`
Expected: All 4 tests PASS.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/assistant/service.py \
        src/backend/tests/unit/test_assistant_service.py
git commit -m "feat(assistant): add AssistantService with tool-calling loop"
```

---

## Task 9: OpenAI Provider Adapter

**Files:**
- Create: `src/backend/base/langflow/services/assistant/providers/openai_provider.py`

- [x] **Step 1: Implement OpenAI provider**

Create `src/backend/base/langflow/services/assistant/providers/openai_provider.py`:

```python
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langflow.services.assistant.providers.base import ProviderClient, StreamEvent, ToolResult


class OpenAIProviderClient(ProviderClient):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            api_msg: dict[str, Any] = {"role": m["role"], "content": m.get("content") or ""}
            if m.get("tool_calls"):
                api_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                    for tc in m["tool_calls"]
                ]
                api_msg["content"] = api_msg["content"] or None
            if m.get("tool_call_id"):
                api_msg["tool_call_id"] = m["tool_call_id"]
            api_messages.append(api_msg)

        stream = await client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=tools if tools else None,
            stream=True,
        )

        tool_calls_buffer: dict[int, dict] = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                yield StreamEvent(type="token", text=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_buffer[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_buffer[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tc_delta.function.arguments

            finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
            if finish_reason == "tool_calls":
                for tc in tool_calls_buffer.values():
                    try:
                        args = json.loads(tc["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamEvent(
                        type="tool_call",
                        tool_call_id=tc["id"],
                        tool_name=tc["name"],
                        tool_args=args,
                    )
                return
            elif finish_reason == "stop":
                yield StreamEvent(type="message_complete")
                return

    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        async for event in self.stream_with_tools(messages, system_prompt, tools):
            yield event
```

- [x] **Step 2: Commit**

```bash
git add src/backend/base/langflow/services/assistant/providers/openai_provider.py
git commit -m "feat(assistant): add OpenAI provider adapter"
```

---

## Task 10: Anthropic Provider Adapter

**Files:**
- Create: `src/backend/base/langflow/services/assistant/providers/anthropic_provider.py`

- [x] **Step 1: Implement Anthropic provider**

Create `src/backend/base/langflow/services/assistant/providers/anthropic_provider.py`:

```python
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langflow.services.assistant.providers.base import ProviderClient, StreamEvent, ToolResult
from langflow.services.assistant.tools.registry import get_tools_for_anthropic


class AnthropicProviderClient(ProviderClient):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        client = self._get_client()

        api_messages = []
        for m in messages:
            if m["role"] == "tool":
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m.get("content", ""),
                    }],
                })
            elif m["role"] == "assistant" and m.get("tool_calls"):
                content_blocks: list[dict] = []
                if m.get("content"):
                    content_blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["args"],
                    })
                api_messages.append({"role": "assistant", "content": content_blocks})
            else:
                api_messages.append({"role": m["role"], "content": m.get("content") or ""})

        anthropic_tools = get_tools_for_anthropic()

        async with client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=api_messages,
            tools=anthropic_tools if anthropic_tools else [],
        ) as stream:
            current_tool_id = None
            current_tool_name = None
            current_tool_json = ""

            async for event in stream:
                if event.type == "content_block_start":
                    if hasattr(event.content_block, "type"):
                        if event.content_block.type == "tool_use":
                            current_tool_id = event.content_block.id
                            current_tool_name = event.content_block.name
                            current_tool_json = ""
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield StreamEvent(type="token", text=event.delta.text)
                    elif hasattr(event.delta, "partial_json"):
                        current_tool_json += event.delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool_id:
                        try:
                            args = json.loads(current_tool_json) if current_tool_json else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamEvent(
                            type="tool_call",
                            tool_call_id=current_tool_id,
                            tool_name=current_tool_name,
                            tool_args=args,
                        )
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_json = ""
                elif event.type == "message_stop":
                    stop_reason = getattr(stream, "current_message_snapshot", None)
                    if stop_reason and getattr(stop_reason, "stop_reason", None) == "tool_use":
                        return
                    yield StreamEvent(type="message_complete")
                    return

    async def stream_with_tool_results(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> AsyncIterator[StreamEvent]:
        async for event in self.stream_with_tools(messages, system_prompt, tools):
            yield event
```

- [x] **Step 2: Update providers `__init__.py`**

Edit `src/backend/base/langflow/services/assistant/providers/__init__.py`:

```python
from langflow.services.assistant.providers.anthropic_provider import AnthropicProviderClient
from langflow.services.assistant.providers.base import FakeProviderClient, ProviderClient
from langflow.services.assistant.providers.openai_provider import OpenAIProviderClient

__all__ = ["AnthropicProviderClient", "FakeProviderClient", "OpenAIProviderClient", "ProviderClient"]
```

- [x] **Step 3: Commit**

```bash
git add src/backend/base/langflow/services/assistant/providers/
git commit -m "feat(assistant): add Anthropic provider adapter"
```

---

## Task 11: API Endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/assistant.py`
- Test: `src/backend/tests/integration/test_assistant_api.py`

- [x] **Step 1: Write the failing tests**

Create `src/backend/tests/integration/test_assistant_api.py`:

```python
from uuid import uuid4

import pytest
from httpx import AsyncClient

from langflow.services.database.models.assistant.model import AssistantConversation, AssistantMessage


@pytest.mark.asyncio
async def test_get_conversation_empty(client: AsyncClient, logged_in_headers: dict, flow):
    response = await client.get(
        f"/api/v1/assistant/flows/{flow.id}/conversation",
        headers=logged_in_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
    assert data["settings_configured"] is False


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient, logged_in_headers: dict, flow, session):
    conv = AssistantConversation(flow_id=flow.id, org_id=flow.organization_id)
    session.add(conv)
    await session.flush()
    msg = AssistantMessage(conversation_id=conv.id, role="user", content="test")
    session.add(msg)
    await session.commit()

    response = await client.delete(
        f"/api/v1/assistant/flows/{flow.id}/conversation",
        headers=logged_in_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_settings_empty(client: AsyncClient, logged_in_headers: dict):
    response = await client.get(
        "/api/v1/assistant/settings",
        headers=logged_in_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_key"] is False


@pytest.mark.asyncio
async def test_put_settings(client: AsyncClient, logged_in_headers: dict):
    response = await client.put(
        "/api/v1/assistant/settings",
        headers=logged_in_headers,
        json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-test123"},
    )
    assert response.status_code == 200

    response = await client.get("/api/v1/assistant/settings", headers=logged_in_headers)
    data = response.json()
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o"
    assert data["has_key"] is True
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/backend && python -m pytest tests/integration/test_assistant_api.py -v`
Expected: FAIL

- [x] **Step 3: Implement API endpoints**

Rewrite `src/backend/base/langflow/api/v1/assistant.py` with the full endpoints:

```python
from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sse_starlette.sse import EventSourceResponse
from starlette.responses import StreamingResponse

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.assistant.providers.anthropic_provider import AnthropicProviderClient
from langflow.services.assistant.providers.openai_provider import OpenAIProviderClient
from langflow.services.assistant.service import AssistantService
from langflow.services.database.models.assistant.model import (
    AssistantConversation,
    AssistantMessage,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope

router = APIRouter(prefix="/assistant", tags=["Assistant"])


ASSISTANT_VAR_PREFIX = "assistant."


class SendMessageRequest(BaseModel):
    content: str


class SettingsRequest(BaseModel):
    provider: str
    model: str
    api_key: str | None = None


async def _get_org_id(current_user: CurrentActiveUser) -> UUID:
    """Get the user's current org id."""
    if hasattr(current_user, "organization_id") and current_user.organization_id:
        return current_user.organization_id
    raise HTTPException(status_code=400, detail="No organization context")


async def _verify_flow_access(session: AsyncSession, flow_id: UUID, org_id: UUID) -> Flow:
    result = await session.exec(
        select(Flow).where(Flow.id == flow_id, Flow.organization_id == org_id)
    )
    flow = result.first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


async def _get_settings(session: AsyncSession, org_id: UUID) -> dict[str, str | None]:
    result = await session.exec(
        select(Variable).where(
            Variable.organization_id == org_id,
            Variable.name.startswith(ASSISTANT_VAR_PREFIX),
        )
    )
    variables = result.all()
    settings: dict[str, str | None] = {"provider": None, "model": None, "api_key": None}
    for v in variables:
        key = v.name.replace(ASSISTANT_VAR_PREFIX, "")
        if key in settings:
            settings[key] = v.value
    return settings


@router.get("/flows/{flow_id}/conversation")
async def get_conversation(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    org_id = await _get_org_id(current_user)
    await _verify_flow_access(session, flow_id, org_id)

    result = await session.exec(
        select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    )
    conv = result.first()

    settings = await _get_settings(session, org_id)
    settings_configured = bool(settings.get("api_key") and settings.get("provider"))

    if not conv:
        return {"conversation_id": None, "messages": [], "settings_configured": settings_configured}

    result = await session.exec(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conv.id)
        .order_by(AssistantMessage.created_at)
    )
    messages = result.all()

    return {
        "conversation_id": str(conv.id),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_call_id": m.tool_call_id,
                "tool_result": m.tool_result,
                "user_id": str(m.user_id) if m.user_id else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "settings_configured": settings_configured,
    }


@router.post("/flows/{flow_id}/messages")
async def send_message(
    flow_id: UUID,
    body: SendMessageRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    org_id = await _get_org_id(current_user)
    flow = await _verify_flow_access(session, flow_id, org_id)
    settings = await _get_settings(session, org_id)

    if not settings.get("api_key") or not settings.get("provider"):
        raise HTTPException(status_code=400, detail="Assistant not configured. Set provider and API key in settings.")

    provider = settings["provider"]
    model = settings["model"] or ("gpt-4o" if provider == "openai" else "claude-sonnet-4-20250514")
    api_key = settings["api_key"]

    if provider == "openai":
        provider_client = OpenAIProviderClient(api_key=api_key, model=model)
    elif provider == "anthropic":
        provider_client = AnthropicProviderClient(api_key=api_key, model=model)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    result = await session.exec(
        select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    )
    conv = result.first()
    if not conv:
        conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
        session.add(conv)
        await session.flush()
        await session.refresh(conv)

    msg_result = await session.exec(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conv.id)
        .order_by(AssistantMessage.created_at)
    )
    history = msg_result.all()
    history_dicts = [
        {"role": m.role, "content": m.content, "tool_calls": m.tool_calls, "tool_call_id": m.tool_call_id}
        for m in history
    ]

    flow_data = flow.data or {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}

    svc = AssistantService(
        provider_client=provider_client,
        flow_data=flow_data,
        flow_id=flow_id,
        org_id=org_id,
        user_id=current_user.id,
        model_name=model,
    )
    svc.set_conversation_history(history_dicts)

    conversation_id = conv.id

    async def event_generator():
        user_msg = AssistantMessage(
            conversation_id=conversation_id,
            user_id=current_user.id,
            role="user",
            content=body.content,
        )
        async with session_scope() as persist_session:
            persist_session.add(user_msg)
            await persist_session.commit()

        accumulated_text = ""
        accumulated_tool_calls = []

        async for event in svc.send_message(body.content):
            yield {"event": event["type"], "data": json.dumps(event)}

            if event["type"] == "token":
                accumulated_text += event.get("text", "")
            elif event["type"] == "tool_call":
                accumulated_tool_calls.append({"id": event["id"], "name": event["name"], "args": event.get("args", {})})
            elif event["type"] == "tool_result":
                async with session_scope() as persist_session:
                    tool_msg = AssistantMessage(
                        conversation_id=conversation_id,
                        role="tool",
                        tool_call_id=event["id"],
                        tool_result=event.get("result"),
                        content=json.dumps(event.get("result", {})),
                    )
                    persist_session.add(tool_msg)
                    await persist_session.commit()
            elif event["type"] == "flow_patch":
                async with session_scope() as persist_session:
                    flow_to_update = (await persist_session.exec(select(Flow).where(Flow.id == flow_id))).first()
                    if flow_to_update:
                        flow_to_update.data = svc.flow_data
                        persist_session.add(flow_to_update)
                        await persist_session.commit()
            elif event["type"] == "message_complete":
                if accumulated_text or accumulated_tool_calls:
                    async with session_scope() as persist_session:
                        assistant_msg = AssistantMessage(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=accumulated_text or None,
                            tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                        )
                        persist_session.add(assistant_msg)
                        await persist_session.commit()

    return EventSourceResponse(event_generator())


@router.delete("/flows/{flow_id}/conversation")
async def delete_conversation(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    org_id = await _get_org_id(current_user)
    await _verify_flow_access(session, flow_id, org_id)

    result = await session.exec(
        select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    )
    conv = result.first()
    if conv:
        await session.delete(conv)
        await session.commit()

    return {"status": "ok"}


@router.get("/settings")
async def get_settings(
    session: DbSession,
    current_user: CurrentActiveUser,
):
    org_id = await _get_org_id(current_user)
    settings = await _get_settings(session, org_id)
    return {
        "provider": settings.get("provider"),
        "model": settings.get("model"),
        "has_key": bool(settings.get("api_key")),
    }


@router.put("/settings")
async def put_settings(
    body: SettingsRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    org_id = await _get_org_id(current_user)

    for key, value in [("provider", body.provider), ("model", body.model), ("api_key", body.api_key)]:
        if value is None:
            continue
        var_name = f"{ASSISTANT_VAR_PREFIX}{key}"
        result = await session.exec(
            select(Variable).where(
                Variable.organization_id == org_id,
                Variable.name == var_name,
            )
        )
        existing = result.first()
        if existing:
            existing.value = value
            session.add(existing)
        else:
            new_var = Variable(
                name=var_name,
                value=value,
                type="assistant",
                user_id=current_user.id,
                organization_id=org_id,
            )
            session.add(new_var)

    await session.commit()
    return {"status": "ok"}
```

- [x] **Step 4: Run tests**

Run: `cd src/backend && python -m pytest tests/integration/test_assistant_api.py -v`
Expected: Tests PASS (adjust fixtures as needed for the test environment).

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/assistant.py \
        src/backend/tests/integration/test_assistant_api.py
git commit -m "feat(assistant): add REST + SSE API endpoints"
```

---

## Task 12: Frontend — Assistant Store + API Client

**Files:**
- Create: `src/frontend/src/stores/assistantStore.ts`
- Create: `src/frontend/src/controllers/API/queries/assistant.ts`

- [x] **Step 1: Create the Zustand store**

Create `src/frontend/src/stores/assistantStore.ts`:

```typescript
import { create } from "zustand";

export type AssistantMessageType = {
  id?: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: Array<{ id: string; name: string; args: Record<string, any> }>;
  tool_call_id?: string;
  tool_result?: Record<string, any>;
  user_id?: string | null;
  created_at?: string;
};

export type FlowPatch = {
  added_nodes: any[];
  added_edges: any[];
  updated_nodes: any[];
  removed_ids: string[];
};

type AssistantStoreState = {
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
  togglePanel: () => void;

  messages: AssistantMessageType[];
  setMessages: (messages: AssistantMessageType[]) => void;
  addMessage: (message: AssistantMessageType) => void;
  appendToLastAssistant: (text: string) => void;
  clearMessages: () => void;

  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;

  settingsConfigured: boolean;
  setSettingsConfigured: (configured: boolean) => void;

  conversationId: string | null;
  setConversationId: (id: string | null) => void;

  pendingPatches: FlowPatch[];
  addPendingPatch: (patch: FlowPatch) => void;
  clearPendingPatches: () => void;
};

const useAssistantStore = create<AssistantStoreState>((set, get) => ({
  panelOpen: false,
  setPanelOpen: (open) => set({ panelOpen: open }),
  togglePanel: () => set({ panelOpen: !get().panelOpen }),

  messages: [],
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set({ messages: [...get().messages, message] }),
  appendToLastAssistant: (text) => {
    const msgs = [...get().messages];
    const last = msgs[msgs.length - 1];
    if (last && last.role === "assistant") {
      last.content = (last.content || "") + text;
      set({ messages: msgs });
    }
  },
  clearMessages: () => set({ messages: [], conversationId: null }),

  isStreaming: false,
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  settingsConfigured: false,
  setSettingsConfigured: (configured) => set({ settingsConfigured: configured }),

  conversationId: null,
  setConversationId: (id) => set({ conversationId: id }),

  pendingPatches: [],
  addPendingPatch: (patch) =>
    set({ pendingPatches: [...get().pendingPatches, patch] }),
  clearPendingPatches: () => set({ pendingPatches: [] }),
}));

export default useAssistantStore;
```

- [x] **Step 2: Create the API client**

Create `src/frontend/src/controllers/API/queries/assistant.ts`:

```typescript
import { api } from "../api";

const BASE = "/api/v1/assistant";

export async function getConversation(flowId: string) {
  const res = await api.get(`${BASE}/flows/${flowId}/conversation`);
  return res.data;
}

export async function deleteConversation(flowId: string) {
  const res = await api.delete(`${BASE}/flows/${flowId}/conversation`);
  return res.data;
}

export async function getAssistantSettings() {
  const res = await api.get(`${BASE}/settings`);
  return res.data;
}

export async function putAssistantSettings(body: {
  provider: string;
  model: string;
  api_key?: string;
}) {
  const res = await api.put(`${BASE}/settings`, body);
  return res.data;
}

export function createMessageSSEUrl(flowId: string): string {
  return `${BASE}/flows/${flowId}/messages`;
}
```

- [x] **Step 3: Commit**

```bash
git add src/frontend/src/stores/assistantStore.ts \
        src/frontend/src/controllers/API/queries/assistant.ts
git commit -m "feat(assistant): add frontend store and API client"
```

---

## Task 13: Frontend — SSE Stream Hook

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-stream.ts`

- [x] **Step 1: Implement the SSE hook**

Create `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-stream.ts`:

```typescript
import { useCallback } from "react";
import useAssistantStore from "@/stores/assistantStore";
import { createMessageSSEUrl } from "@/controllers/API/queries/assistant";
import useFlowStore from "@/stores/flowStore";

export function useAssistantStream(flowId: string) {
  const addMessage = useAssistantStore((s) => s.addMessage);
  const appendToLastAssistant = useAssistantStore((s) => s.appendToLastAssistant);
  const setIsStreaming = useAssistantStore((s) => s.setIsStreaming);
  const addPendingPatch = useAssistantStore((s) => s.addPendingPatch);

  const sendMessage = useCallback(
    async (content: string) => {
      addMessage({ role: "user", content });
      addMessage({ role: "assistant", content: "" });
      setIsStreaming(true);

      try {
        const url = createMessageSSEUrl(flowId);
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
          credentials: "include",
        });

        if (!response.ok) {
          const error = await response.text();
          appendToLastAssistant(`Error: ${error}`);
          setIsStreaming(false);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          setIsStreaming(false);
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const jsonStr = line.slice(6);
              try {
                const event = JSON.parse(jsonStr);
                handleEvent(event);
              } catch {
                // skip malformed
              }
            }
          }
        }
      } catch (err: any) {
        appendToLastAssistant(`\n\nConnection error: ${err.message}`);
      } finally {
        setIsStreaming(false);
      }
    },
    [flowId],
  );

  function handleEvent(event: any) {
    switch (event.type) {
      case "token":
        appendToLastAssistant(event.text || "");
        break;
      case "tool_call":
        addMessage({
          role: "tool",
          content: `Calling ${event.name}...`,
          tool_call_id: event.id,
        });
        break;
      case "tool_result":
        // Update the tool message with result
        break;
      case "flow_patch":
        if (event.patch) {
          addPendingPatch(event.patch);
          applyFlowPatch(event.patch);
        }
        break;
      case "error":
        appendToLastAssistant(`\n\nError: ${event.message}`);
        break;
      case "message_complete":
        break;
    }
  }

  return { sendMessage };
}

function applyFlowPatch(patch: any) {
  const { setNodes, setEdges, nodes, edges } = useFlowStore.getState();

  if (patch.removed_ids?.length) {
    const removedSet = new Set(patch.removed_ids);
    setNodes((prev) => prev.filter((n) => !removedSet.has(n.id)));
    setEdges((prev) => prev.filter((e) => !removedSet.has(e.id)));
  }

  if (patch.added_nodes?.length) {
    setNodes((prev) => [...prev, ...patch.added_nodes]);
  }

  if (patch.added_edges?.length) {
    setEdges((prev) => [...prev, ...patch.added_edges]);
  }

  if (patch.updated_nodes?.length) {
    const updateMap = new Map(patch.updated_nodes.map((n: any) => [n.id, n]));
    setNodes((prev) =>
      prev.map((n) => (updateMap.has(n.id) ? { ...n, ...updateMap.get(n.id) } : n)),
    );
  }

  // Auto-fit view after changes
  setTimeout(() => {
    const { reactFlowInstance } = useFlowStore.getState();
    reactFlowInstance?.fitView({ duration: 300 });
  }, 100);
}
```

- [x] **Step 2: Commit**

```bash
git add src/frontend/src/modals/AssistantPanel/hooks/use-assistant-stream.ts
git commit -m "feat(assistant): add SSE stream hook with flow patch application"
```

---

## Task 14: Frontend — Conversation History Hook

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-conversation.ts`

- [x] **Step 1: Implement the conversation hook**

Create `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-conversation.ts`:

```typescript
import { useEffect } from "react";
import useAssistantStore from "@/stores/assistantStore";
import { getConversation } from "@/controllers/API/queries/assistant";

export function useAssistantConversation(flowId: string) {
  const setMessages = useAssistantStore((s) => s.setMessages);
  const setConversationId = useAssistantStore((s) => s.setConversationId);
  const setSettingsConfigured = useAssistantStore((s) => s.setSettingsConfigured);

  useEffect(() => {
    if (!flowId) return;

    let cancelled = false;

    async function load() {
      try {
        const data = await getConversation(flowId);
        if (cancelled) return;

        setConversationId(data.conversation_id);
        setSettingsConfigured(data.settings_configured);
        setMessages(
          data.messages.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            tool_calls: m.tool_calls,
            tool_call_id: m.tool_call_id,
            tool_result: m.tool_result,
            user_id: m.user_id,
            created_at: m.created_at,
          })),
        );
      } catch (err) {
        console.error("Failed to load assistant conversation", err);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [flowId]);
}
```

- [x] **Step 2: Commit**

```bash
git add src/frontend/src/modals/AssistantPanel/hooks/use-assistant-conversation.ts
git commit -m "feat(assistant): add conversation history loader hook"
```

---

## Task 15: Frontend — Panel Components

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/components/composer.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/components/message.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/components/tool-call-card.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/components/message-list.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/components/panel-header.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/components/settings-required.tsx`

- [x] **Step 1: Create composer**

Create `src/frontend/src/modals/AssistantPanel/components/composer.tsx`:

```tsx
import { useRef, useState } from "react";
import useAssistantStore from "@/stores/assistantStore";

type Props = {
  onSend: (content: string) => void;
};

export default function Composer({ onSend }: Props) {
  const [text, setText] = useState("");
  const isStreaming = useAssistantStore((s) => s.isStreaming);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setText("");
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="flex items-end gap-2 border-t p-3">
      <textarea
        ref={inputRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask the assistant..."
        className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        rows={1}
        disabled={isStreaming}
      />
      <button
        onClick={handleSubmit}
        disabled={!text.trim() || isStreaming}
        className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {isStreaming ? "..." : "Send"}
      </button>
    </div>
  );
}
```

- [x] **Step 2: Create message component**

Create `src/frontend/src/modals/AssistantPanel/components/message.tsx`:

```tsx
import type { AssistantMessageType } from "@/stores/assistantStore";
import ToolCallCard from "./tool-call-card";

type Props = {
  message: AssistantMessageType;
};

export default function Message({ message }: Props) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  if (isTool) {
    return <ToolCallCard message={message} />;
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content || ""}</div>
      </div>
    </div>
  );
}
```

- [x] **Step 3: Create tool-call-card**

Create `src/frontend/src/modals/AssistantPanel/components/tool-call-card.tsx`:

```tsx
import { useState } from "react";
import type { AssistantMessageType } from "@/stores/assistantStore";

type Props = {
  message: AssistantMessageType;
};

export default function ToolCallCard({ message }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mx-3 mb-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 rounded border bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
      >
        <span className="font-mono">{expanded ? "▼" : "▶"}</span>
        <span>{message.content}</span>
      </button>
      {expanded && message.tool_result && (
        <pre className="mt-1 max-h-40 overflow-auto rounded border bg-background p-2 text-xs">
          {JSON.stringify(message.tool_result, null, 2)}
        </pre>
      )}
    </div>
  );
}
```

- [x] **Step 4: Create message-list**

Create `src/frontend/src/modals/AssistantPanel/components/message-list.tsx`:

```tsx
import { useEffect, useRef } from "react";
import useAssistantStore from "@/stores/assistantStore";
import Message from "./message";

export default function MessageList() {
  const messages = useAssistantStore((s) => s.messages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-4 text-center text-sm text-muted-foreground">
        Ask me to add components, connect them, or modify your flow.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-3">
      {messages.map((msg, i) => (
        <Message key={msg.id || `msg-${i}`} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [x] **Step 5: Create panel-header**

Create `src/frontend/src/modals/AssistantPanel/components/panel-header.tsx`:

```tsx
import useAssistantStore from "@/stores/assistantStore";

type Props = {
  flowId: string;
  onClear: () => void;
};

export default function PanelHeader({ flowId, onClear }: Props) {
  const setPanelOpen = useAssistantStore((s) => s.setPanelOpen);

  return (
    <div className="flex items-center justify-between border-b px-4 py-3">
      <h3 className="text-sm font-semibold">Flow Assistant</h3>
      <div className="flex items-center gap-2">
        <button
          onClick={() => {
            if (confirm("Clear conversation history?")) {
              onClear();
            }
          }}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Clear conversation"
        >
          🗑
        </button>
        <button
          onClick={() => setPanelOpen(false)}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Close panel"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
```

- [x] **Step 6: Create settings-required**

Create `src/frontend/src/modals/AssistantPanel/components/settings-required.tsx`:

```tsx
import { useNavigate } from "react-router-dom";

export default function SettingsRequired() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="text-3xl">⚙️</div>
      <h3 className="text-sm font-semibold">Assistant Not Configured</h3>
      <p className="text-xs text-muted-foreground">
        An org admin needs to configure the AI provider and API key before the
        assistant can be used.
      </p>
      <button
        onClick={() => navigate("/settings/assistant")}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Configure Assistant
      </button>
    </div>
  );
}
```

- [x] **Step 7: Commit**

```bash
git add src/frontend/src/modals/AssistantPanel/components/
git commit -m "feat(assistant): add panel UI components (composer, messages, header)"
```

---

## Task 16: Frontend — Panel Shell + Editor Integration

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/index.tsx`
- Modify: The flow editor layout to add the panel and toggle button

- [x] **Step 1: Create panel shell**

Create `src/frontend/src/modals/AssistantPanel/index.tsx`:

```tsx
import useAssistantStore from "@/stores/assistantStore";
import { useAssistantConversation } from "./hooks/use-assistant-conversation";
import { useAssistantStream } from "./hooks/use-assistant-stream";
import Composer from "./components/composer";
import MessageList from "./components/message-list";
import PanelHeader from "./components/panel-header";
import SettingsRequired from "./components/settings-required";
import { deleteConversation } from "@/controllers/API/queries/assistant";

type Props = {
  flowId: string;
};

export default function AssistantPanel({ flowId }: Props) {
  const panelOpen = useAssistantStore((s) => s.panelOpen);
  const settingsConfigured = useAssistantStore((s) => s.settingsConfigured);
  const clearMessages = useAssistantStore((s) => s.clearMessages);

  useAssistantConversation(flowId);
  const { sendMessage } = useAssistantStream(flowId);

  if (!panelOpen) return null;

  async function handleClear() {
    await deleteConversation(flowId);
    clearMessages();
  }

  return (
    <div className="flex h-full w-[400px] min-w-[300px] flex-col border-l bg-background">
      <PanelHeader flowId={flowId} onClear={handleClear} />
      {settingsConfigured ? (
        <>
          <MessageList />
          <Composer onSend={sendMessage} />
        </>
      ) : (
        <SettingsRequired />
      )}
    </div>
  );
}
```

- [x] **Step 2: Add toggle button and panel to the flow editor**

Find the flow editor layout component (likely in `src/frontend/src/pages/FlowPage/` or similar). Add:

1. An import for `AssistantPanel` and `useAssistantStore`
2. A toggle button in the toolbar
3. The panel as a sibling of the canvas, rendering conditionally

The toggle button:
```tsx
import useAssistantStore from "@/stores/assistantStore";

// In the toolbar:
const togglePanel = useAssistantStore((s) => s.togglePanel);

<button
  onClick={togglePanel}
  className="rounded p-2 hover:bg-muted"
  title="Toggle Flow Assistant"
>
  <ForwardedIconComponent name="Bot" className="h-5 w-5" />
</button>
```

The panel in the layout:
```tsx
import AssistantPanel from "@/modals/AssistantPanel";

// In the editor layout, wrapping the canvas:
<div className="flex h-full">
  <div className="flex-1">
    {/* existing canvas */}
  </div>
  <AssistantPanel flowId={currentFlowId} />
</div>
```

(Exact file paths and insertion points depend on current layout structure — the implementer should find the flow editor's root layout component and add the panel as a flex sibling.)

- [x] **Step 3: Commit**

```bash
git add src/frontend/src/modals/AssistantPanel/index.tsx
# plus whatever editor layout files were modified
git commit -m "feat(assistant): add dockable panel to flow editor"
```

---

## Task 17: Frontend — Assistant Settings Page

**Files:**
- Create: `src/frontend/src/pages/SettingsPage/pages/AssistantSettingsPage/index.tsx`
- Modify: `src/frontend/src/pages/SettingsPage/index.tsx` (add sidebar entry)
- Modify: Routes file to add the route

- [x] **Step 1: Create the settings page**

Create `src/frontend/src/pages/SettingsPage/pages/AssistantSettingsPage/index.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  getAssistantSettings,
  putAssistantSettings,
} from "@/controllers/API/queries/assistant";

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
];

const MODELS: Record<string, Array<{ value: string; label: string }>> = {
  openai: [
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  ],
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
    { value: "claude-opus-4-20250514", label: "Claude Opus 4" },
  ],
};

export default function AssistantSettingsPage() {
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    async function load() {
      const data = await getAssistantSettings();
      setProvider(data.provider || "");
      setModel(data.model || "");
      setHasKey(data.has_key);
      setLoaded(true);
    }
    load();
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await putAssistantSettings({
        provider,
        model,
        ...(apiKey ? { api_key: apiKey } : {}),
      });
      setHasKey(true);
      setApiKey("");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return <div className="p-6">Loading...</div>;

  const modelOptions = MODELS[provider] || [];

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="text-lg font-semibold">Flow Assistant Settings</h2>
        <p className="text-sm text-muted-foreground">
          Configure the AI provider for the flow builder assistant. These
          settings apply to everyone in your organization.
        </p>
      </div>

      <div className="flex max-w-md flex-col gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Provider</label>
          <select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value);
              setModel(MODELS[e.target.value]?.[0]?.value || "");
            }}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">Select provider</option>
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">Model</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            disabled={!provider}
          >
            <option value="">Select model</option>
            {modelOptions.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={hasKey ? "••••••• (key saved)" : "Enter API key"}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          />
          {hasKey && !apiKey && (
            <p className="mt-1 text-xs text-muted-foreground">
              Key is saved. Enter a new value to update it.
            </p>
          )}
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !provider || !model}
          className="w-fit rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}
```

- [x] **Step 2: Add sidebar entry to SettingsPage**

In `src/frontend/src/pages/SettingsPage/index.tsx`, add to the `sidebarNavItems` array:

```typescript
{
  title: "Flow Assistant",
  href: "/settings/assistant",
  icon: <ForwardedIconComponent name="Bot" />,
},
```

- [x] **Step 3: Add route**

Find the routes configuration (likely `src/frontend/src/routes.tsx` or similar) and add:

```typescript
{
  path: "assistant",
  element: <AssistantSettingsPage />,
}
```

as a child of the settings route, importing `AssistantSettingsPage` from `@/pages/SettingsPage/pages/AssistantSettingsPage`.

- [x] **Step 4: Commit**

```bash
git add src/frontend/src/pages/SettingsPage/pages/AssistantSettingsPage/ \
        src/frontend/src/pages/SettingsPage/index.tsx \
        src/frontend/src/routes.tsx
git commit -m "feat(assistant): add Assistant Settings page with provider/model/key config"
```

---

## Task 18: Frontend — Stale History Banner

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/index.tsx`

- [x] **Step 1: Add polling and banner**

Add to `AssistantPanel/index.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";

// Inside AssistantPanel component:
const [stale, setStale] = useState(false);
const lastSeenRef = useRef<string | null>(null);

useEffect(() => {
  if (!panelOpen || !flowId) return;

  const msgs = useAssistantStore.getState().messages;
  if (msgs.length > 0) {
    lastSeenRef.current = msgs[msgs.length - 1].id || null;
  }

  const interval = setInterval(async () => {
    try {
      const data = await getConversation(flowId);
      const remoteMessages = data.messages || [];
      if (remoteMessages.length > 0) {
        const lastRemoteId = remoteMessages[remoteMessages.length - 1].id;
        if (lastSeenRef.current && lastRemoteId !== lastSeenRef.current) {
          setStale(true);
        }
      }
    } catch {
      // ignore polling errors
    }
  }, 30_000);

  return () => clearInterval(interval);
}, [panelOpen, flowId]);

function handleRefresh() {
  setStale(false);
  // Re-trigger conversation load
  const load = async () => {
    const data = await getConversation(flowId);
    useAssistantStore.getState().setMessages(data.messages);
    lastSeenRef.current = data.messages[data.messages.length - 1]?.id || null;
  };
  load();
}

// In the JSX, above MessageList:
{stale && (
  <div className="flex items-center justify-between bg-amber-100 px-4 py-2 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
    <span>New messages from a teammate</span>
    <button onClick={handleRefresh} className="font-medium underline">
      Refresh
    </button>
  </div>
)}
```

- [x] **Step 2: Commit**

```bash
git add src/frontend/src/modals/AssistantPanel/index.tsx
git commit -m "feat(assistant): add stale-history polling banner"
```

---

## Task 19: End-to-End Test

**Files:**
- Create: `src/frontend/tests/e2e/assistant.spec.ts`

- [x] **Step 1: Write the golden-path e2e test**

Create `src/frontend/tests/e2e/assistant.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Flow Builder Assistant", () => {
  test("opens panel and shows empty state when no settings configured", async ({
    page,
  }) => {
    // Navigate to a flow page (adjust URL to match your test fixture)
    await page.goto("/flow/test-flow-id");

    // Find and click the assistant toggle button
    const toggleBtn = page.locator('button[title="Toggle Flow Assistant"]');
    await toggleBtn.click();

    // Panel should open
    const panel = page.locator("text=Flow Assistant");
    await expect(panel).toBeVisible();

    // Should show settings-required state
    await expect(
      page.locator("text=Assistant Not Configured"),
    ).toBeVisible();
  });

  test("settings page allows configuration", async ({ page }) => {
    await page.goto("/settings/assistant");

    // Select provider
    const providerSelect = page.locator("select").first();
    await providerSelect.selectOption("openai");

    // Select model
    const modelSelect = page.locator("select").nth(1);
    await modelSelect.selectOption("gpt-4o");

    // Enter API key
    const keyInput = page.locator('input[type="password"]');
    await keyInput.fill("sk-test-key-12345");

    // Save
    const saveBtn = page.locator("text=Save");
    await saveBtn.click();

    // Verify saved state
    await expect(page.locator("text=key saved")).toBeVisible();
  });
});
```

- [x] **Step 2: Run e2e tests**

Run: `cd src/frontend && npx playwright test tests/e2e/assistant.spec.ts`
Expected: Tests pass against a running dev server (may need test fixtures/mocks adjusted).

- [x] **Step 3: Commit**

```bash
git add src/frontend/tests/e2e/assistant.spec.ts
git commit -m "test(assistant): add e2e tests for panel and settings page"
```

---

## Summary

| Task | Component | Description |
|------|-----------|-------------|
| 1 | DB | `AssistantConversation` + `AssistantMessage` models + migration |
| 2 | Backend | Catalog tools wrapping component search |
| 3 | Backend | MCP server exposing catalog tools |
| 4 | Backend | Flow mutation tools (add/connect/set/remove/sticky) |
| 5 | Backend | Tool registry with provider-native format conversion |
| 6 | Backend | Provider ABC + FakeProviderClient for tests |
| 7 | Backend | Context window packing |
| 8 | Backend | AssistantService orchestrator |
| 9 | Backend | OpenAI provider adapter |
| 10 | Backend | Anthropic provider adapter |
| 11 | Backend | REST + SSE API endpoints |
| 12 | Frontend | Zustand store + API client |
| 13 | Frontend | SSE stream hook + flow patch application |
| 14 | Frontend | Conversation history loader hook |
| 15 | Frontend | Panel UI components |
| 16 | Frontend | Panel shell + editor integration |
| 17 | Frontend | Assistant Settings page |
| 18 | Frontend | Stale-history polling banner |
| 19 | E2E | Playwright tests |
