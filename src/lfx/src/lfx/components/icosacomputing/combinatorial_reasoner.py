from typing import ClassVar

import requests
from requests.auth import HTTPBasicAuth

from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, SecretStrInput, StrInput
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


class CombinatorialReasonerComponent(Component):
    display_name = "Combinatorial Reasoner"
    description = (
        "WARNING: This component forwards your OpenAI API key to Icosa Computing's servers "
        "(cr-api.icosacomputing.com). Your key is used by Icosa to call OpenAI on your behalf. "
        "Only use this component if you trust Icosa with your OpenAI credentials. "
        "Uses Combinatorial Optimization to construct an optimal prompt with embedded reasons. "
        "Sign up here:\nhttps://forms.gle/oWNv2NKjBNaqqvCx6"
    )
    icon = "Icosa"
    name = "Combinatorial Reasoner"
    legacy: ClassVar[bool] = True

    inputs = [
        MessageTextInput(name="prompt", display_name="Prompt", required=True),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info=(
                "WARNING: This key is sent to Icosa Computing's servers (cr-api.icosacomputing.com), "
                "which then call OpenAI on your behalf. Only provide a key you are willing to share with Icosa."
            ),
            advanced=False,
            value="OPENAI_API_KEY",
            required=True,
        ),
        StrInput(
            name="username",
            display_name="Username",
            info="Username to authenticate access to Icosa CR API",
            advanced=False,
            required=True,
        ),
        SecretStrInput(
            name="password",
            display_name="Combinatorial Reasoner Password",
            info="Password to authenticate access to Icosa CR API.",
            advanced=False,
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=OPENAI_CHAT_MODEL_NAMES,
            value=OPENAI_CHAT_MODEL_NAMES[0],
        ),
    ]

    outputs = [
        Output(
            display_name="Optimized Prompt",
            name="optimized_prompt",
            method="build_prompt",
        ),
        Output(display_name="Selected Reasons", name="reasons", method="build_reasons"),
    ]

    def build_prompt(self) -> Message:
        params = {
            "prompt": self.prompt,
            "apiKey": self.openai_api_key,
            "model": self.model_name,
        }

        creds = HTTPBasicAuth(self.username, password=self.password)
        response = requests.post(
            "https://cr-api.icosacomputing.com/cr/langflow",
            json=params,
            auth=creds,
            timeout=100,
        )
        response.raise_for_status()

        prompt = response.json()["prompt"]

        self.reasons = response.json()["finalReasons"]
        return prompt

    def build_reasons(self) -> Data:
        # list of selected reasons
        final_reasons = [reason[0] for reason in self.reasons]
        return Data(value=final_reasons)
