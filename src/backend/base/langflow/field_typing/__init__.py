from typing import Any

# NOTE: AgentExecutor, Chain, BaseChatMemory, BaseMemory are intentionally NOT
# imported at module scope — they are deferred in lfx.field_typing.constants to
# avoid pulling ~3s of langchain_classic into pytest collection time.
# All symbols are accessible via the __getattr__ lazy path below.

from lfx.field_typing.constants import (
    BaseChatMessageHistory,
    BaseChatModel,
    BaseDocumentCompressor,
    BaseLanguageModel,
    BaseLLM,
    BaseLLMOutputParser,
    BaseLoader,
    BaseOutputParser,
    BasePromptTemplate,
    BaseRetriever,
    BaseTool,
    Callable,
    ChatPromptTemplate,
    Code,
    Document,
    Embeddings,
    LanguageModel,
    Memory,
    NestedDict,
    Object,
    OutputParser,
    PromptTemplate,
    Retriever,
    TextSplitter,
    Tool,
    ToolEnabledLanguageModel,
    VectorStore,
    VectorStoreRetriever,
)
from lfx.field_typing.constants import (
    CUSTOM_COMPONENT_SUPPORTED_TYPES,
    DEFAULT_IMPORT_STRING,
    LANGCHAIN_BASE_TYPES,
)
from lfx.field_typing.range_spec import RangeSpec

# Import lfx schema types
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

# Import Message from langflow.schema for backward compatibility
from langflow.schema.message import Message

# Add Message and DataFrame to CUSTOM_COMPONENT_SUPPORTED_TYPES
CUSTOM_COMPONENT_SUPPORTED_TYPES = {
    **CUSTOM_COMPONENT_SUPPORTED_TYPES,
    "Message": Message,
    "DataFrame": DataFrame,
}


# Heavy langchain_classic symbols — resolved lazily on first attribute access.
_LAZY_LANGCHAIN_CLASSIC = frozenset({"AgentExecutor", "Chain", "BaseChatMemory", "BaseMemory"})


def _import_input_class():
    from lfx.template.field.base import Input

    return Input


def _import_output_class():
    from lfx.template.field.base import Output

    return Output


def __getattr__(name: str) -> Any:
    if name == "Input":
        return _import_input_class()
    if name == "Output":
        return _import_output_class()
    if name == "RangeSpec":
        return RangeSpec
    if name in _LAZY_LANGCHAIN_CLASSIC:
        # Use the _LazyTypeDict resolver — triggers the deferred import.
        return LANGCHAIN_BASE_TYPES[name]
    # The other names should work as if they were imported from constants
    from lfx.field_typing import constants

    return getattr(constants, name)


__all__ = [
    "AgentExecutor",
    "BaseChatMemory",
    "BaseChatModel",
    "BaseDocumentCompressor",
    "BaseLLM",
    "BaseLLMOutputParser",
    "BaseLanguageModel",
    "BaseLoader",
    "BaseMemory",
    "BaseOutputParser",
    "BasePromptTemplate",
    "BaseRetriever",
    "BaseTool",
    # Additional types
    "Callable",
    "Chain",
    "ChatPromptTemplate",
    "Code",
    "Data",
    "DataFrame",
    "Document",
    "Embeddings",
    "LanguageModel",
    "Memory",
    "Message",
    "NestedDict",
    "Object",
    "OutputParser",
    "PromptTemplate",
    "Retriever",
    "Text",
    "TextSplitter",
    "Tool",
    "ToolEnabledLanguageModel",
    "VectorStore",
    "VectorStoreRetriever",
    "CUSTOM_COMPONENT_SUPPORTED_TYPES",
    "DEFAULT_IMPORT_STRING",
    "LANGCHAIN_BASE_TYPES",
]
