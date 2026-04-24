from pathlib import Path

import yaml
from langchain_classic.agents import AgentExecutor
from langchain_community.agent_toolkits import create_openapi_agent
from langchain_community.agent_toolkits.openapi.toolkit import OpenAPIToolkit
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.utilities.requests import TextRequestsWrapper

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.inputs.inputs import BoolInput, FileInput, ModelInput, SecretStrInput


class OpenAPIAgentComponent(LCAgentComponent):
    display_name = "OpenAPI Agent"
    description = "Agent to interact with OpenAPI API."
    name = "OpenAPIAgent"
    icon = "LangChain"
    inputs = [
        *LCAgentComponent.get_base_inputs(),
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
        FileInput(name="path", display_name="File Path", file_types=["json", "yaml", "yml"], required=True),
        BoolInput(name="allow_dangerous_requests", display_name="Allow Dangerous Requests", value=False, required=True),
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

    def build_agent(self) -> AgentExecutor:
        llm = self._get_llm()
        path = Path(self.path)
        if path.suffix in {"yaml", "yml"}:
            with path.open(encoding="utf-8") as file:
                yaml_dict = yaml.safe_load(file)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(path)
        requests_wrapper = TextRequestsWrapper()
        toolkit = OpenAPIToolkit.from_llm(
            llm=llm,
            json_spec=spec,
            requests_wrapper=requests_wrapper,
            allow_dangerous_requests=self.allow_dangerous_requests,
        )

        agent_args = self.get_agent_kwargs()

        # This is bit weird - generally other create_*_agent functions have max_iterations in the
        # `agent_executor_kwargs`, but openai has this parameter passed directly.
        agent_args["max_iterations"] = agent_args["agent_executor_kwargs"]["max_iterations"]
        del agent_args["agent_executor_kwargs"]["max_iterations"]
        return create_openapi_agent(llm=llm, toolkit=toolkit, **agent_args)
