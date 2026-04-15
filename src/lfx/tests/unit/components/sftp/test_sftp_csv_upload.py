def test_component_imports_and_registers():
    from lfx.components.sftp import SFTPCSVUploadComponent

    assert SFTPCSVUploadComponent.display_name == "SFTP CSV Upload"
    assert SFTPCSVUploadComponent.name == "SFTPCSVUpload"


import pandas as pd
import pytest
from lfx.schema import Data, DataFrame
from lfx.components.sftp.sftp_csv_upload import _normalize_to_dataframe


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


import time
from lfx.components.sftp.sftp_csv_upload import _resolve_remote_path

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


from lfx.components.sftp.sftp_csv_upload import _render_csv_bytes

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
