from langchain_classic.agents import create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.inputs.inputs import (
    DataInput,
    ModelInput,
    MultilineInput,
    SecretStrInput,
)
from lfx.schema.data import Data


class OpenAIToolsAgentComponent(LCToolsAgentComponent):
    display_name: str = "OpenAI Tools Agent"
    description: str = "Agent that uses tools via openai-tools."
    icon = "LangChain"
    name = "OpenAIToolsAgent"

    inputs = [
        *LCToolsAgentComponent.get_base_inputs(),
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider or connect a Language Model component.",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt for the agent.",
            value="You are a helpful assistant",
        ),
        MultilineInput(
            name="user_prompt", display_name="Prompt", info="This prompt must contain 'input' key.", value="{input}"
        ),
        DataInput(name="chat_history", display_name="Chat History", is_list=True, advanced=True),
    ]

    def _get_llm(self):
        """Resolve the language model from dropdown selection or connected component."""
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=getattr(self, "api_key", None),
        )

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Dynamically update build config with user-filtered model options (tool-calling capable models)."""

        def get_tool_calling_model_options(user_id=None):
            return get_language_model_options(user_id=user_id, tool_calling=True)

        return update_model_options_in_build_config(
            component=self,
            build_config=dict(build_config),
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=get_tool_calling_model_options,
            field_name=field_name,
            field_value=field_value,
        )

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        if "input" not in self.user_prompt:
            msg = "Prompt must contain 'input' key."
            raise ValueError(msg)
        llm = self._get_llm()
        messages = [
            ("system", self.system_prompt),
            ("placeholder", "{chat_history}"),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=["input"], template=self.user_prompt)),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        return create_openai_tools_agent(llm, self.tools, prompt)
