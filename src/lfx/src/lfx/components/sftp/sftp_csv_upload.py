"""SFTPCSVUploadComponent — serialize tabular data to CSV and upload via SFTP."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import posixpath
import time as _time
from typing import TYPE_CHECKING, Any

import asyncssh
import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema import Data, DataFrame, Message
from lfx.utils.component_utils import set_field_display

if TYPE_CHECKING:
    from lfx.schema.dotdict import dotdict


_QUOTING_MAP = {
    "Minimal": csv.QUOTE_MINIMAL,
    "All": csv.QUOTE_ALL,
    "Non-numeric": csv.QUOTE_NONNUMERIC,
    "None": csv.QUOTE_NONE,
}

_CONNECT_TIMEOUT_SECONDS = 30


def _normalize_to_dataframe(value: object) -> pd.DataFrame:
    if isinstance(value, DataFrame):
        return pd.DataFrame(value)
    if isinstance(value, Data):
        return pd.DataFrame([value.data])
    if isinstance(value, list):
        records = []
        for item in value:
            if isinstance(item, Data):
                records.append(item.data)
            elif isinstance(item, dict):
                records.append(item)
            else:
                msg = (
                    "data must be DataFrame, Data, or list of Data/dicts; "
                    f"list contained {type(item).__name__}"
                )
                raise TypeError(msg)
        return pd.DataFrame.from_records(records)
    msg = f"data must be DataFrame, Data, or list of Data/dicts; got {type(value).__name__}"
    raise TypeError(msg)


def _resolve_remote_path(
    remote_directory: str, filename: str, *, now: _time.struct_time | None = None
) -> str:
    when = now if now is not None else _time.gmtime()
    rendered = filename.replace("{timestamp}", _time.strftime("%Y%m%d_%H%M%S", when))
    rendered = rendered.replace("{date}", _time.strftime("%Y%m%d", when))
    if "/" in rendered:
        msg = "filename must not contain path separator '/'; use remote_directory"
        raise ValueError(msg)
    return posixpath.join(remote_directory, rendered)


def _render_csv_bytes(
    df: pd.DataFrame,
    *,
    delimiter: str,
    include_header: bool,
    encoding: str,
    quote_char: str,
    quoting: str,
    line_terminator: str,
    null_representation: str,
) -> bytes:
    if quoting not in _QUOTING_MAP:
        msg = f"quoting must be one of {sorted(_QUOTING_MAP)}; got {quoting!r}"
        raise ValueError(msg)
    buf = io.StringIO()
    df.to_csv(
        buf,
        index=False,
        sep=delimiter,
        header=include_header,
        quotechar=quote_char,
        quoting=_QUOTING_MAP[quoting],
        lineterminator=line_terminator,
        na_rep=null_representation,
    )
    return buf.getvalue().encode(encoding)


def _compute_sha256_fingerprint(host_key) -> str:
    raw = host_key.export_public_key("openssh")
    digest = hashlib.sha256(raw).digest()
    return base64.b64encode(digest).decode().rstrip("=")


def _verify_host_key(host_key, *, expected: str) -> None:
    normalized_expected = expected.strip()
    if normalized_expected.lower().startswith("sha256:"):
        normalized_expected = normalized_expected.split(":", 1)[1]
    actual = _compute_sha256_fingerprint(host_key)
    if actual != normalized_expected:
        msg = (
            f"host key fingerprint mismatch: expected SHA256:{normalized_expected}, "
            f"got SHA256:{actual}"
        )
        raise ValueError(msg)


def _make_known_hosts_callback(expected_fingerprint: str):
    """Return an asyncssh known_hosts callback that verifies SHA-256 fingerprint."""

    def _callback(host, addr, port):  # noqa: ARG001
        def _validate(key):
            _verify_host_key(key, expected=expected_fingerprint)
            return True

        return _validate, [], []

    return _callback


class SFTPCSVUploadComponent(Component):
    display_name = "SFTP CSV Upload"
    description = "Serialize upstream data to CSV and upload to an SFTP server."
    icon = "Upload"
    name = "SFTPCSVUpload"

    inputs = [
        # Connection
        StrInput(name="host", display_name="Host", info="SFTP server hostname.", required=True),
        IntInput(name="port", display_name="Port", value=22),
        StrInput(name="username", display_name="Username", required=True),
        DropdownInput(
            name="auth_method",
            display_name="Auth Method",
            options=["Password", "SSH Key"],
            value="Password",
            real_time_refresh=True,
        ),
        SecretStrInput(name="password", display_name="Password"),
        SecretStrInput(
            name="private_key",
            display_name="Private Key (PEM)",
            info="Paste PEM contents of the SSH private key.",
            show=False,
        ),
        SecretStrInput(
            name="private_key_passphrase",
            display_name="Private Key Passphrase",
            show=False,
        ),
        StrInput(
            name="host_key_fingerprint",
            display_name="Host Key Fingerprint (SHA-256)",
            info="Optional. Format: SHA256:<base64>. Empty = auto-accept any host key.",
            advanced=True,
        ),
        # Data
        HandleInput(
            name="data",
            display_name="Data",
            input_types=["DataFrame", "Table", "Data", "JSON"],
            required=True,
        ),
        # Destination
        StrInput(name="remote_directory", display_name="Remote Directory", required=True),
        StrInput(
            name="filename",
            display_name="Filename",
            info="Supports {timestamp} (UTC YYYYMMDD_HHMMSS) and {date} (UTC YYYYMMDD).",
            required=True,
        ),
        # CSV options
        DropdownInput(
            name="delimiter",
            display_name="Delimiter",
            options=[",", ";", "\t", "|"],
            value=",",
            advanced=True,
        ),
        BoolInput(name="include_header", display_name="Include Header", value=True, advanced=True),
        DropdownInput(
            name="encoding",
            display_name="Encoding",
            options=["utf-8", "utf-8-sig", "latin-1"],
            value="utf-8",
            advanced=True,
        ),
        StrInput(name="quote_char", display_name="Quote Char", value='"', advanced=True),
        DropdownInput(
            name="quoting",
            display_name="Quoting",
            options=["Minimal", "All", "Non-numeric", "None"],
            value="Minimal",
            advanced=True,
        ),
        DropdownInput(
            name="line_terminator",
            display_name="Line Terminator",
            options=["\n", "\r\n"],
            value="\n",
            advanced=True,
        ),
        MessageTextInput(
            name="null_representation",
            display_name="Null Representation",
            value="",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Result", name="result", method="build_upload")]

    def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict:
        if field_name == "auth_method":
            is_password = field_value == "Password"
            set_field_display(build_config, "password", value=is_password)
            set_field_display(build_config, "private_key", value=not is_password)
            set_field_display(build_config, "private_key_passphrase", value=not is_password)
        return build_config

    async def build_upload(self) -> Message:
        # --- Validate required string fields up front ---
        host = (self.host or "").strip()
        username = (self.username or "").strip()
        remote_directory = (self.remote_directory or "").strip()
        filename = (self.filename or "").strip()
        for name, value in (
            ("host", host),
            ("username", username),
            ("remote_directory", remote_directory),
            ("filename", filename),
        ):
            if not value:
                msg = f"{name} is required"
                raise ValueError(msg)

        # --- Auth dispatch ---
        auth_kwargs: dict[str, Any] = {}
        if self.auth_method == "Password":
            password = self.password or ""
            if not password:
                msg = "password is required when Auth Method is Password"
                raise ValueError(msg)
            auth_kwargs["password"] = password
        elif self.auth_method == "SSH Key":
            pem = self.private_key or ""
            if not pem:
                msg = "private_key is required when Auth Method is SSH Key"
                raise ValueError(msg)
            passphrase = self.private_key_passphrase or ""
            auth_kwargs["client_keys"] = [asyncssh.import_private_key(pem, passphrase)]
        else:
            msg = f"unknown auth_method: {self.auth_method!r}"
            raise ValueError(msg)

        # --- Host key verification ---
        fingerprint = (self.host_key_fingerprint or "").strip()
        known_hosts = _make_known_hosts_callback(fingerprint) if fingerprint else None

        # --- Data → CSV bytes ---
        df = _normalize_to_dataframe(self.data)
        csv_bytes = _render_csv_bytes(
            df,
            delimiter=self.delimiter,
            include_header=bool(self.include_header),
            encoding=self.encoding,
            quote_char=self.quote_char,
            quoting=self.quoting,
            line_terminator=self.line_terminator,
            null_representation=self.null_representation or "",
        )

        # --- Resolve destination ---
        remote_path = _resolve_remote_path(remote_directory, filename)

        # --- Upload ---
        async with asyncssh.connect(
            host,
            port=int(self.port or 22),
            username=username,
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            known_hosts=known_hosts,
            **auth_kwargs,
        ) as conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.put_data(csv_bytes, remote_path)

        rendered_filename = posixpath.basename(remote_path)
        text = (
            f"Uploaded {rendered_filename} ({len(df)} rows, {len(csv_bytes)} bytes) "
            f"to sftp://{host}:{int(self.port or 22)}{remote_path}"
        )
        return Message(text=text)
