"""Integration test: SFTPCSVUploadComponent against an in-process asyncssh server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncssh
import pytest
from lfx.components.sftp.sftp_csv_upload import SFTPCSVUploadComponent
from lfx.schema import DataFrame


class _AcceptAllSSHServer(asyncssh.SSHServer):
    def begin_auth(self, username):  # noqa: ARG002
        return True

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username, password) -> bool:  # noqa: ARG002
        return password == "secretpw"  # noqa: S105


class _SFTPServer(asyncssh.SFTPServer):
    def __init__(self, chan):
        super().__init__(chan)


async def _start_server(tmp_path: Path):
    host_key = asyncssh.generate_private_key("ssh-rsa")
    host_key_path = tmp_path / "host_key"
    host_key_path.write_bytes(host_key.export_private_key())
    server = await asyncssh.create_server(
        _AcceptAllSSHServer,
        host="127.0.0.1",
        port=0,
        server_host_keys=[str(host_key_path)],
        sftp_factory=_SFTPServer,
    )
    port = server.sockets[0].getsockname()[1]
    return server, port


def _make_component(tmp_path: Path, port: int, **overrides):
    base = dict(
        host="127.0.0.1",
        port=port,
        username="user",
        auth_method="Password",
        password="secretpw",
        private_key="",
        private_key_passphrase="",
        host_key_fingerprint="",
        data=DataFrame([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]),
        remote_directory=str(tmp_path),
        filename="users.csv",
        delimiter=",",
        include_header=True,
        encoding="utf-8",
        quote_char='"',
        quoting="Minimal",
        line_terminator="\n",
        null_representation="",
    )
    base.update(overrides)
    return SFTPCSVUploadComponent(**base)


async def test_happy_path_uploads_csv_with_correct_bytes(tmp_path):
    server, port = await _start_server(tmp_path)
    try:
        component = _make_component(tmp_path, port)
        result = await asyncio.wait_for(component.build_upload(), timeout=30.0)
    finally:
        server.close()
        await server.wait_closed()

    written = (tmp_path / "users.csv").read_bytes()
    assert written == b"a,b\n1,x\n2,y\n"
    assert "2 rows" in result.text
    assert f"{len(written)} bytes" in result.text


async def test_bad_password_raises_permission_denied(tmp_path):
    server, port = await _start_server(tmp_path)
    try:
        component = _make_component(tmp_path, port, password="wrongpw")
        with pytest.raises(asyncssh.PermissionDenied):
            await asyncio.wait_for(component.build_upload(), timeout=30.0)
    finally:
        server.close()
        await server.wait_closed()
