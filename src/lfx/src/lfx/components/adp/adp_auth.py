"""ADPAuthComponent — produces an ADPConnection via OAuth client_credentials + mTLS."""

from __future__ import annotations

from typing import ClassVar

from lfx.components.adp._shared import DEFAULT_TOKEN_URL, ADPConnection, fetch_token, validate_adp_url
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import TextFileSecretInput
from lfx.io import MessageTextInput, Output, SecretStrInput


class ADPAuthComponent(Component):
    display_name = "ADP Auth"
    description = "Authenticate to ADP via OAuth 2.0 client_credentials over mTLS."
    icon = "Key"
    name = "ADPAuth"
    version: int = 2
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=2,
            changes=(
                "- Replaced the `cert_source` File Path / PEM toggle with "
                "**paste-or-upload** TextFileSecretInput fields for cert_pem "
                "and key_pem.\n"
                "- `cert_path` and `key_path` inputs removed.\n"
                "- client_id, client_secret, cert_pem, and key_pem are now "
                "Fernet-encrypted at rest via hidden auto-Variables (not "
                "stored plaintext in the flow JSON)."
            ),
            notes=(
                "Saved flows with cert_source='File Path' drop the cert_path "
                "and key_path values on load. Paste the certificate and key "
                "PEMs (or upload the .pem/.crt/.key files) into the new "
                "fields to restore the connection. client_id and "
                "client_secret typed inline are now silently encrypted on "
                "save; exported flow JSON will show empty values where it "
                "previously showed plaintext — re-enter credentials on import."
            ),
        ),
    ]

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
        TextFileSecretInput(
            name="cert_pem",
            display_name="Client Certificate (PEM)",
            info=(
                "Client certificate for mTLS. Paste the PEM contents or upload a "
                ".pem/.crt file. Stored Fernet-encrypted at rest."
            ),
            file_types=["pem", "crt"],
            required=True,
        ),
        TextFileSecretInput(
            name="key_pem",
            display_name="Client Key (PEM)",
            info=(
                "Client private key for mTLS. Paste the PEM contents or upload a "
                ".pem/.key file. Stored Fernet-encrypted at rest."
            ),
            file_types=["pem", "key"],
            required=True,
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
