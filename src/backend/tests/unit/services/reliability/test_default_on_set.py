"""I/O component base classes default to error_output_enabled=True; trivial
components stay False."""
import pytest


def test_lc_tool_components_have_error_output():
    from lfx.base.langchain_utilities.model import LCToolComponent

    assert getattr(LCToolComponent, "error_output_enabled", False) is True


def test_lc_model_components_have_error_output():
    from lfx.base.models.model import LCModelComponent

    assert getattr(LCModelComponent, "error_output_enabled", False) is True


def test_lc_agent_component_has_error_output():
    from lfx.base.agents.agent import LCAgentComponent

    assert getattr(LCAgentComponent, "error_output_enabled", False) is True


def test_lc_vector_store_component_has_error_output():
    from lfx.base.vectorstores.model import LCVectorStoreComponent

    assert getattr(LCVectorStoreComponent, "error_output_enabled", False) is True


def test_lc_embeddings_model_has_error_output():
    from lfx.base.embeddings.model import LCEmbeddingsModel

    assert getattr(LCEmbeddingsModel, "error_output_enabled", False) is True


def test_base_file_component_has_error_output():
    from lfx.base.data.base_file import BaseFileComponent

    assert getattr(BaseFileComponent, "error_output_enabled", False) is True


def test_chatinput_does_not_have_error_output():
    """Trivial components should NOT have the error port by default."""
    from lfx.components.input_output.chat import ChatInput

    component = ChatInput()
    assert not any(o.name == "error" for o in component.outputs)


def test_text_input_does_not_have_error_output():
    """Text input is trivial — should NOT get error port."""
    from lfx.components.input_output.text import TextInputComponent

    component = TextInputComponent()
    assert not any(o.name == "error" for o in component.outputs)
