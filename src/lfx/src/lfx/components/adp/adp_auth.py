"""ADPAuthComponent — produces an ADPConnection via OAuth client_credentials + mTLS."""

from __future__ import annotations

from typing import Any

from lfx.components.adp._shared import DEFAULT_TOKEN_URL, ADPConnection, fetch_token, validate_adp_url
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import TabInput
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.schema.dotdict import dotdict
from lfx.utils.component_utils import set_field_display


class ADPAuthComponent(Component):
    display_name = "ADP Auth"
    description = "Authenticate to ADP via OAuth 2.0 client_credentials over mTLS."
    icon = "Key"
    name = "ADPAuth"

    inputs = [
        SecretStrInput(
            name="client_id",
            display_name="Client ID",
            info="ADP developer client ID.",
            required=True,
        ),
        SecretStrInput(
            name="client_secret",
            display_name="Client Secret",
            info="ADP developer client secret.",
            required=True,
        ),
        TabInput(
            name="cert_source",
            display_name="Cert Source",
            options=["File Path", "PEM"],
            value="File Path",
            info="How to supply the mTLS client certificate and key.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="cert_path",
            display_name="Client Certificate Path",
            info="Absolute path to the client certificate (PEM).",
        ),
        MessageTextInput(
            name="key_path",
            display_name="Client Key Path",
            info="Absolute path to the client private key (PEM).",
        ),
        SecretStrInput(
            name="cert_pem",
            display_name="Client Certificate (PEM)",
            info="Paste the client certificate contents.",
            show=False,
        ),
        SecretStrInput(
            name="key_pem",
            display_name="Client Key (PEM)",
            info="Paste the client private key contents.",
            show=False,
        ),
        MessageTextInput(
            name="token_url",
            display_name="Token URL",
            info="OAuth token endpoint. Override only for staging/testing.",
            value=DEFAULT_TOKEN_URL,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Connection", name="connection", method="build_connection"),
    ]

    async def build_connection(self) -> ADPConnection:
        client_id = (self.client_id or "").strip()
        client_secret = (self.client_secret or "").strip()
        if not client_id:
            msg = "client_id is required"
            raise ValueError(msg)
        if not client_secret:
            msg = "client_secret is required"
            raise ValueError(msg)

        cert_pem = (self.cert_pem or "").strip()
        key_pem = (self.key_pem or "").strip()
        if not cert_pem:
            msg = "cert_pem is required"
            raise ValueError(msg)
        if not key_pem:
            msg = "key_pem is required"
            raise ValueError(msg)

        token_url = (self.token_url or DEFAULT_TOKEN_URL).strip()
        validate_adp_url(token_url, field_name="token_url")

        conn = ADPConnection(
            client_id=client_id,
            client_secret=client_secret,
            cert_pem=cert_pem,
            key_pem=key_pem,
            token_url=token_url,
        )
        await fetch_token(conn)
        return conn

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "cert_source":
            is_path = field_value == "File Path"
            set_field_display(build_config, "cert_path", value=is_path)
            set_field_display(build_config, "key_path", value=is_path)
            set_field_display(build_config, "cert_pem", value=not is_path)
            set_field_display(build_config, "key_pem", value=not is_path)
        return build_config
