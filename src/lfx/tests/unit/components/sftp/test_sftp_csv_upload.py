import base64
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from lfx.components.sftp.sftp_csv_upload import (
    SFTPCSVUploadComponent,
    _compute_sha256_fingerprint,
    _normalize_to_dataframe,
    _render_csv_bytes,
    _resolve_remote_path,
    _verify_host_key,
)
from lfx.schema import Data, DataFrame


def test_component_imports_and_registers():
    from lfx.components.sftp import SFTPCSVUploadComponent

    assert SFTPCSVUploadComponent.display_name == "SFTP CSV Upload"
    assert SFTPCSVUploadComponent.name == "SFTPCSVUpload"


def test_normalize_dataframe_passthrough():
    df = DataFrame([{"a": 1, "b": 2}])
    out = _normalize_to_dataframe(df)
    assert isinstance(out, pd.DataFrame)
    assert out.to_dict("records") == [{"a": 1, "b": 2}]


def test_normalize_single_data_wraps_to_one_row():
    out = _normalize_to_dataframe(Data(data={"a": 1, "b": 2}))
    assert out.to_dict("records") == [{"a": 1, "b": 2}]


def test_normalize_list_of_data():
    items = [Data(data={"a": 1}), Data(data={"a": 2})]
    out = _normalize_to_dataframe(items)
    assert out.to_dict("records") == [{"a": 1}, {"a": 2}]


def test_normalize_list_of_dicts():
    out = _normalize_to_dataframe([{"a": 1}, {"a": 2}])
    assert out.to_dict("records") == [{"a": 1}, {"a": 2}]


def test_normalize_unsupported_type_raises():
    with pytest.raises(TypeError, match="data must be"):
        _normalize_to_dataframe(42)


FROZEN = time.struct_time((2026, 4, 15, 14, 30, 22, 0, 0, 0))


def test_resolve_path_literal_filename():
    assert _resolve_remote_path("/exports", "users.csv", now=FROZEN) == "/exports/users.csv"


def test_resolve_path_substitutes_timestamp():
    assert _resolve_remote_path("/exports", "users_{timestamp}.csv", now=FROZEN) == "/exports/users_20260415_143022.csv"


def test_resolve_path_substitutes_date():
    assert _resolve_remote_path("/exports", "users_{date}.csv", now=FROZEN) == "/exports/users_20260415.csv"


def test_resolve_path_rejects_slash_in_filename():
    with pytest.raises(ValueError, match="path separator"):
        _resolve_remote_path("/exports", "sub/users.csv", now=FROZEN)


def test_resolve_path_rejects_slash_after_substitution():
    with pytest.raises(ValueError, match="path separator"):
        _resolve_remote_path("/exports", "{date}/users.csv", now=FROZEN)


def test_resolve_path_uses_gmtime_when_now_omitted():
    out = _resolve_remote_path("/exports", "users_{date}.csv")
    assert out.startswith("/exports/users_") and out.endswith(".csv")


DEFAULTS = {
    "delimiter": ",",
    "include_header": True,
    "encoding": "utf-8",
    "quote_char": '"',
    "quoting": "Minimal",
    "line_terminator": "\n",
    "null_representation": "",
}


def _render(df, **overrides):
    return _render_csv_bytes(df, **{**DEFAULTS, **overrides})


def test_csv_default_round_trip():
    df = pd.DataFrame([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
    assert _render(df) == b"a,b\n1,x\n2,y\n"


def test_csv_no_header():
    df = pd.DataFrame([{"a": 1, "b": "x"}])
    assert _render(df, include_header=False) == b"1,x\n"


@pytest.mark.parametrize("delim,sep_byte", [(",", b","), (";", b";"), ("\t", b"\t"), ("|", b"|")])
def test_csv_delimiters(delim, sep_byte):
    df = pd.DataFrame([{"a": 1, "b": 2}])
    out = _render(df, delimiter=delim)
    assert b"a" + sep_byte + b"b" in out


def test_csv_crlf_line_terminator():
    df = pd.DataFrame([{"a": 1}])
    out = _render(df, line_terminator="\r\n")
    assert out == b"a\r\n1\r\n"


def test_csv_utf8_sig_bom():
    df = pd.DataFrame([{"a": 1}])
    out = _render(df, encoding="utf-8-sig")
    assert out.startswith(b"\xef\xbb\xbf")


def test_csv_latin1_encoding():
    df = pd.DataFrame([{"a": "café"}])
    out = _render(df, encoding="latin-1")
    assert "café".encode("latin-1") in out


def test_csv_null_representation():
    df = pd.DataFrame([{"a": 1, "b": None}])
    out = _render(df, null_representation="NULL")
    assert b"NULL" in out


def test_csv_quoting_all_quotes_everything():
    df = pd.DataFrame([{"a": 1, "b": "x"}])
    out = _render(df, quoting="All")
    assert out == b'"a","b"\n"1","x"\n'


def test_csv_quoting_none():
    df = pd.DataFrame([{"a": "x"}])
    out = _render(df, quoting="None", quote_char='"')
    assert out == b"a\nx\n"


def test_csv_custom_quote_char():
    df = pd.DataFrame([{"a": "has,comma"}])
    out = _render(df, quote_char="'")
    assert b"'has,comma'" in out


class _FakeHostKey:
    def __init__(self, raw: bytes):
        self._raw = raw

    def export_public_key(self, fmt: str) -> bytes:  # noqa: ARG002
        return self._raw


def _expected_fp(raw: bytes) -> str:
    return base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")


def test_compute_fingerprint_matches_known_value():
    raw = b"ssh-rsa AAAAB3..."
    fp = _compute_sha256_fingerprint(_FakeHostKey(raw))
    assert fp == _expected_fp(raw)


def test_verify_host_key_accepts_match_with_prefix():
    raw = b"ssh-rsa AAAAB3..."
    _verify_host_key(_FakeHostKey(raw), expected=f"SHA256:{_expected_fp(raw)}")


def test_verify_host_key_accepts_match_without_prefix():
    raw = b"ssh-rsa AAAAB3..."
    _verify_host_key(_FakeHostKey(raw), expected=_expected_fp(raw))


def test_verify_host_key_is_case_insensitive_on_prefix():
    raw = b"ssh-rsa AAAAB3..."
    _verify_host_key(_FakeHostKey(raw), expected=f"sha256:{_expected_fp(raw)}")


def test_verify_host_key_raises_on_mismatch():
    raw = b"ssh-rsa AAAAB3..."
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        _verify_host_key(_FakeHostKey(raw), expected="SHA256:wrongfingerprintxxxxxxxxxxxxxxxxxxxxxxxxxxx")


VALID_PASSWORD_KWARGS = dict(
    host="sftp.example.com",
    port=22,
    username="user",
    auth_method="Password",
    password="pw",
    private_key="",
    private_key_passphrase="",
    host_key_fingerprint="",
    data=DataFrame([{"a": 1}]),
    remote_directory="/exports",
    filename="users.csv",
    delimiter=",",
    include_header=True,
    encoding="utf-8",
    quote_char='"',
    quoting="Minimal",
    line_terminator="\n",
    null_representation="",
)


def _make_connect_mock():
    """Return (connect_patch, sftp_put_mock)."""
    sftp = MagicMock()
    sftp.put_data = AsyncMock()
    sftp_cm = MagicMock()
    sftp_cm.__aenter__ = AsyncMock(return_value=sftp)
    sftp_cm.__aexit__ = AsyncMock(return_value=None)
    conn = MagicMock()
    conn.start_sftp_client = MagicMock(return_value=sftp_cm)
    conn_cm = MagicMock()
    conn_cm.__aenter__ = AsyncMock(return_value=conn)
    conn_cm.__aexit__ = AsyncMock(return_value=None)
    connect_mock = MagicMock(return_value=conn_cm)
    return connect_mock, sftp.put_data


async def test_build_upload_password_auth_calls_connect_with_password():
    component = SFTPCSVUploadComponent(**VALID_PASSWORD_KWARGS)
    connect_mock, put_mock = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        result = await component.build_upload()

    kwargs = connect_mock.call_args.kwargs
    assert kwargs["password"] == "pw"
    assert "client_keys" not in kwargs
    put_mock.assert_awaited_once()
    args, _ = put_mock.call_args
    assert args[0] == b"a\n1\n"
    assert args[1] == "/exports/users.csv"
    assert "Uploaded users.csv" in result.text
    assert "1 rows" in result.text


async def test_build_upload_ssh_key_auth_passes_client_keys():
    kwargs = {**VALID_PASSWORD_KWARGS, "auth_method": "SSH Key", "password": "", "private_key": "PEMDATA"}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock), patch(
        "lfx.components.sftp.sftp_csv_upload.asyncssh.import_private_key", return_value="KEYOBJ"
    ) as import_mock:
        await component.build_upload()
    import_mock.assert_called_once_with("PEMDATA", "")
    assert connect_mock.call_args.kwargs["client_keys"] == ["KEYOBJ"]
    assert "password" not in connect_mock.call_args.kwargs


@pytest.mark.parametrize(
    "field,blank_value,match",
    [
        ("host", "", "host"),
        ("username", "", "username"),
        ("remote_directory", "", "remote_directory"),
        ("filename", "", "filename"),
    ],
)
async def test_build_upload_missing_required_field_raises_before_connect(field, blank_value, match):
    kwargs = {**VALID_PASSWORD_KWARGS, field: blank_value}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        with pytest.raises(ValueError, match=match):
            await component.build_upload()
    connect_mock.assert_not_called()


async def test_build_upload_password_mode_missing_password_raises():
    kwargs = {**VALID_PASSWORD_KWARGS, "password": ""}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        with pytest.raises(ValueError, match="password"):
            await component.build_upload()
    connect_mock.assert_not_called()


async def test_build_upload_ssh_key_mode_missing_private_key_raises():
    kwargs = {**VALID_PASSWORD_KWARGS, "auth_method": "SSH Key", "password": "", "private_key": ""}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        with pytest.raises(ValueError, match="private_key"):
            await component.build_upload()
    connect_mock.assert_not_called()


async def test_build_upload_no_fingerprint_passes_known_hosts_none():
    component = SFTPCSVUploadComponent(**VALID_PASSWORD_KWARGS)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        await component.build_upload()
    assert connect_mock.call_args.kwargs["known_hosts"] is None


async def test_build_upload_with_fingerprint_passes_callable_known_hosts():
    kwargs = {**VALID_PASSWORD_KWARGS, "host_key_fingerprint": "SHA256:abc123"}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        await component.build_upload()
    known_hosts = connect_mock.call_args.kwargs["known_hosts"]
    assert callable(known_hosts)


def test_update_build_config_toggles_password_fields():
    from lfx.schema.dotdict import dotdict

    component = SFTPCSVUploadComponent(**VALID_PASSWORD_KWARGS)
    config = dotdict(
        {
            "password": dotdict({"show": False}),
            "private_key": dotdict({"show": True}),
            "private_key_passphrase": dotdict({"show": True}),
        }
    )
    out = component.update_build_config(config, field_value="Password", field_name="auth_method")
    assert out["password"]["show"] is True
    assert out["private_key"]["show"] is False
    assert out["private_key_passphrase"]["show"] is False


async def test_build_upload_port_zero_raises():
    kwargs = {**VALID_PASSWORD_KWARGS, "port": 0}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        with pytest.raises(ValueError, match="port"):
            await component.build_upload()
    connect_mock.assert_not_called()


async def test_build_upload_port_too_large_raises():
    kwargs = {**VALID_PASSWORD_KWARGS, "port": 70000}
    component = SFTPCSVUploadComponent(**kwargs)
    connect_mock, _ = _make_connect_mock()
    with patch("lfx.components.sftp.sftp_csv_upload.asyncssh.connect", connect_mock):
        with pytest.raises(ValueError, match="port"):
            await component.build_upload()
    connect_mock.assert_not_called()


def test_update_build_config_toggles_ssh_key_fields():
    from lfx.schema.dotdict import dotdict

    component = SFTPCSVUploadComponent(**VALID_PASSWORD_KWARGS)
    config = dotdict(
        {
            "password": dotdict({"show": True}),
            "private_key": dotdict({"show": False}),
            "private_key_passphrase": dotdict({"show": False}),
        }
    )
    out = component.update_build_config(config, field_value="SSH Key", field_name="auth_method")
    assert out["password"]["show"] is False
    assert out["private_key"]["show"] is True
    assert out["private_key_passphrase"]["show"] is True
