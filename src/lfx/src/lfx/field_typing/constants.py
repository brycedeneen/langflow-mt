"""Constants for field typing used throughout lfx package."""

import importlib.util
from collections.abc import Callable
from typing import TYPE_CHECKING, Text, TypeAlias, TypeVar

if TYPE_CHECKING:
    # Heavy: each transitively pulls ~1-3s of langchain_classic. Kept behind
    # TYPE_CHECKING so importing lfx.field_typing.constants doesn't force the
    # full langchain_classic import graph at pytest collection time.
    from langchain_classic.agents.agent import AgentExecutor
    from langchain_classic.base_memory import BaseMemory
    from langchain_classic.chains.base import Chain
    from langchain_classic.memory.chat_memory import BaseChatMemory

# Lighter langchain_core / text_splitters imports — keep eager. ImportError
# stubs preserved for environments where langchain isn't installed.
try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.document_loaders import BaseLoader
    from langchain_core.documents import Document
    from langchain_core.documents.compressor import BaseDocumentCompressor
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseLanguageModel, BaseLLM
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
    from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.tools import BaseTool, Tool
    from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
    from langchain_text_splitters import TextSplitter
except ImportError:
    # Stub types for environments without langchain installed.
    class BaseChatMessageHistory:
        pass

    class BaseLoader:
        pass

    class Document:
        pass

    class BaseDocumentCompressor:
        pass

    class Embeddings:
        pass

    class BaseLanguageModel:
        pass

    class BaseLLM:
        pass

    class BaseChatModel:
        pass

    class BaseLLMOutputParser:
        pass

    class BaseOutputParser:
        pass

    class BasePromptTemplate:
        pass

    class ChatPromptTemplate:
        pass

    class PromptTemplate:
        pass

    class BaseRetriever:
        pass

    class BaseTool:
        pass

    class Tool:
        pass

    class VectorStore:
        pass

    class VectorStoreRetriever:
        pass

    class TextSplitter:
        pass


# NOTE: AgentExecutor / Chain / BaseChatMemory / BaseMemory are only used as
# string keys in LANGCHAIN_BASE_TYPES and as TYPE_CHECKING annotations.
# If you add a new RUNTIME use (isinstance, constructor, etc.), do a local
# import inside the function body, NOT at module scope.


# Import lfx schema types (avoid circular deps)
from lfx.schema.data import JSON, Data
from lfx.schema.dataframe import DataFrame, Table

# Type aliases
NestedDict: TypeAlias = dict[str, str | dict]
LanguageModel = TypeVar("LanguageModel", BaseLanguageModel, BaseLLM, BaseChatModel)
ToolEnabledLanguageModel = TypeVar("ToolEnabledLanguageModel", BaseLanguageModel, BaseLLM, BaseChatModel)
Memory = TypeVar("Memory", bound=BaseChatMessageHistory)

Retriever = TypeVar(
    "Retriever",
    BaseRetriever,
    VectorStoreRetriever,
)
OutputParser = TypeVar(
    "OutputParser",
    BaseOutputParser,
    BaseLLMOutputParser,
)


class Object:
    """Generic object type for custom components."""


class Code:
    """Code type for custom components."""


def _resolve_langchain_classic_type(name: str) -> type:
    """Lazy resolver for heavy langchain_classic types.

    Called only when the actual class object is needed (e.g. isinstance checks
    or value access on LANGCHAIN_BASE_TYPES). Importing on first call avoids
    pulling ~3s of langchain_classic into the module-import graph at collection
    time.
    """
    if name == "AgentExecutor":
        from langchain_classic.agents.agent import AgentExecutor as _T
    elif name == "Chain":
        from langchain_classic.chains.base import Chain as _T
    elif name == "BaseChatMemory":
        from langchain_classic.memory.chat_memory import BaseChatMemory as _T
    elif name == "BaseMemory":
        from langchain_classic.base_memory import BaseMemory as _T
    else:
        msg = f"Unknown lazy langchain_classic type: {name!r}"
        raise KeyError(msg)
    return _T  # type: ignore[return-value]


class _LazyTypeDict(dict):
    """dict subclass that defers resolution of heavy langchain_classic types.

    Keys are resolved at construction time (cheap — just strings).
    Values for the four heavy symbols are resolved lazily on first __getitem__
    or iteration over values/items.  The .keys() fast-path (the only production
    call site) never triggers the imports.

    NOTE: __iter__ intentionally does NOT resolve lazy entries so that we can
    copy raw sentinel values between two _LazyTypeDict instances without
    triggering the heavy imports. Use .values() or .items() when you need the
    real classes.
    """

    # Sentinels stored as a frozenset so they are excluded from normal dict ops.
    _LAZY_KEYS: frozenset[str] = frozenset({"AgentExecutor", "Chain", "BaseChatMemory", "BaseMemory"})

    def __getitem__(self, key: str) -> type:
        value = dict.__getitem__(self, key)
        if value is None and key in self._LAZY_KEYS:
            resolved = _resolve_langchain_classic_type(key)
            dict.__setitem__(self, key, resolved)
            return resolved
        return value  # type: ignore[return-value]

    def values(self):
        self._resolve_all()
        return dict.values(self)

    def items(self):
        self._resolve_all()
        return dict.items(self)

    def _resolve_all(self) -> None:
        for key in self._LAZY_KEYS:
            if dict.__getitem__(self, key) is None:
                dict.__setitem__(self, key, _resolve_langchain_classic_type(key))


# Langchain base types mapping — four heavy langchain_classic entries are stored
# as None and resolved lazily on first value access.
LANGCHAIN_BASE_TYPES: _LazyTypeDict = _LazyTypeDict(
    {
        "Chain": None,  # lazy: langchain_classic.chains.base.Chain
        "AgentExecutor": None,  # lazy: langchain_classic.agents.agent.AgentExecutor
        "BaseTool": BaseTool,
        "Tool": Tool,
        "BaseLLM": BaseLLM,
        "BaseLanguageModel": BaseLanguageModel,
        "PromptTemplate": PromptTemplate,
        "ChatPromptTemplate": ChatPromptTemplate,
        "BasePromptTemplate": BasePromptTemplate,
        "BaseLoader": BaseLoader,
        "Document": Document,
        "TextSplitter": TextSplitter,
        "VectorStore": VectorStore,
        "Embeddings": Embeddings,
        "BaseRetriever": BaseRetriever,
        "BaseOutputParser": BaseOutputParser,
        "BaseMemory": None,  # lazy: langchain_classic.base_memory.BaseMemory
        "BaseChatMemory": None,  # lazy: langchain_classic.memory.chat_memory.BaseChatMemory
        "BaseChatModel": BaseChatModel,
        "Memory": Memory,
        "BaseDocumentCompressor": BaseDocumentCompressor,
    }
)

# Langchain base types plus Python base types.
# Build by reading raw dict entries (bypassing lazy resolution) with dict.items().
# Since __iter__ doesn't resolve lazy entries, iterating over LANGCHAIN_BASE_TYPES
# here is safe — the None sentinels pass through unchanged.
CUSTOM_COMPONENT_SUPPORTED_TYPES: _LazyTypeDict = _LazyTypeDict(
    {
        # Iterate raw keys/values without triggering lazy resolution.
        **{k: dict.__getitem__(LANGCHAIN_BASE_TYPES, k) for k in LANGCHAIN_BASE_TYPES},
        # Non-langchain-classic extras.
        "NestedDict": NestedDict,
        "Data": Data,
        "JSON": JSON,
        "DataFrame": DataFrame,
        "Table": Table,
        "Text": Text,  # noqa: UP019
        "Object": Object,
        "Callable": Callable,
        "LanguageModel": LanguageModel,
        "Retriever": Retriever,
    }
)

# Default import string for component code generation
LANGCHAIN_IMPORT_STRING = """from langchain_classic.agents.agent import AgentExecutor
from langchain_classic.chains.base import Chain
from langchain_classic.memory.chat_memory import BaseChatMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_classic.base_memory import BaseMemory
from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.tools import BaseTool, Tool
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
from langchain_text_splitters import TextSplitter
"""


DEFAULT_IMPORT_STRING = """

from lfx.io import (
    BoolInput,
    CodeInput,
    DataInput,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    JSONInput,
    LinkInput,
    MessageInput,
    MessageTextInput,
    MultilineInput,
    MultilineSecretInput,
    MultiselectInput,
    NestedDictInput,
    Output,
    PromptInput,
    SecretStrInput,
    SliderInput,
    StrInput,
    TableInput,
)
from lfx.schema.data import JSON, Data
from lfx.schema.dataframe import DataFrame, Table
"""

if importlib.util.find_spec("langchain") is not None:
    DEFAULT_IMPORT_STRING = LANGCHAIN_IMPORT_STRING + DEFAULT_IMPORT_STRING
