# SFTP CSV Upload Component Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single Langflow component, `SFTP CSV Upload`, that serializes upstream tabular data to CSV and uploads it via SFTP.

**Architecture:** One component file under `src/lfx/src/lfx/components/sftp/`, modeled on the ADP bundle but collapsed to a single component (no shared connection state). Uses `asyncssh` for async SFTP. CSV is generated in memory via pandas, then uploaded with `sftp.put_data()`. Auth supports password or SSH key via a dropdown that toggles dynamic fields. Optional SHA-256 host-key fingerprint verification.

**Tech Stack:** Python 3.11+, `asyncssh`, `pandas`, `pytest` / `pytest-asyncio`. Component framework from `lfx.custom.custom_component.component`.

**Spec:** `docs/superpowers/specs/2026-04-15-sftp-csv-connector-design.md`

---

## File Structure

**Create:**
- `src/lfx/src/lfx/components/sftp/__init__.py` — re-exports `SFTPCSVUploadComponent`.
- `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py` — the component class plus pure-function helpers.
- `src/lfx/tests/unit/components/sftp/__init__.py` — empty test package marker.
- `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py` — unit tests (no network).
- `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload_integration.py` — integration test against in-process asyncssh server.

**Modify:**
- `src/lfx/pyproject.toml` — add `asyncssh` to `[project].dependencies`.

The component file holds both the class and the small pure helpers (`_normalize_to_dataframe`, `_resolve_remote_path`, `_render_csv_bytes`, `_make_host_key_callback`). They are module-level so unit tests can call them directly without instantiating the component.

---

## Task 1: Scaffold package, register dependency, smoke-import test

**Files:**
- Create: `src/lfx/src/lfx/components/sftp/__init__.py`
- Create: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`
- Modify: `src/lfx/pyproject.toml`
- Create: `src/lfx/tests/unit/components/sftp/__init__.py`
- Test: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`

- [ ] **Step 1: Add `asyncssh` to `src/lfx/pyproject.toml`**

Find the `[project]` `dependencies = [` list (around line 10). Add `"asyncssh>=2.14.0"` in alphabetical position. Example diff:

```toml
dependencies = [
    "anyio>=4.0",
    "asyncssh>=2.14.0",
    "pandas>=2.0.0,<3.0.0",
    ...
]
```

- [ ] **Step 2: Install the new dep**

Run from the repo root:

```bash
uv sync --package lfx
```

Expected: completes without error and reports asyncssh installed.

- [ ] **Step 3: Create empty test package marker**

```python
# src/lfx/tests/unit/components/sftp/__init__.py
```

(Empty file — just makes the directory a package.)

- [ ] **Step 4: Write the failing smoke test**

Create `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`:

```python
def test_component_imports_and_registers():
    from lfx.components.sftp import SFTPCSVUploadComponent

    assert SFTPCSVUploadComponent.display_name == "SFTP CSV Upload"
    assert SFTPCSVUploadComponent.name == "SFTPCSVUpload"
```

- [ ] **Step 5: Run the test to verify it fails**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'lfx.components.sftp'`.

- [ ] **Step 6: Create the component skeleton**

`src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`:

```python
"""SFTPCSVUploadComponent — serialize tabular data to CSV and upload via SFTP."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput


class SFTPCSVUploadComponent(Component):
    display_name = "SFTP CSV Upload"
    description = "Serialize upstream data to CSV and upload to an SFTP server."
    icon = "Upload"
    name = "SFTPCSVUpload"

    inputs = []  # populated in Task 6
    outputs = [Output(display_name="Result", name="result", method="build_upload")]

    async def build_upload(self):  # implemented in Task 6
        raise NotImplementedError
```

- [ ] **Step 7: Create the package `__init__.py`**

`src/lfx/src/lfx/components/sftp/__init__.py`:

```python
"""SFTP connector bundle: CSV Upload."""

from .sftp_csv_upload import SFTPCSVUploadComponent

__all__ = ["SFTPCSVUploadComponent"]
```

- [ ] **Step 8: Run the smoke test to verify it passes**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: 1 passed.

- [ ] **Step 9: Commit**

```bash
git add src/lfx/pyproject.toml src/lfx/src/lfx/components/sftp/ src/lfx/tests/unit/components/sftp/
git commit -m "feat(sftp): scaffold SFTP CSV Upload component"
```

---

## Task 2: Input normalization helper

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`
- Test: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`

Goal: a pure function `_normalize_to_dataframe(value) -> pandas.DataFrame` that accepts a `DataFrame`, a single `Data` (dict-like with `.data` attribute), a list of `Data` / list of dicts. Anything else raises `TypeError`.

- [ ] **Step 1: Write the failing tests**

Append to `test_sftp_csv_upload.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py::test_normalize_dataframe_passthrough -v
```

Expected: FAIL with `ImportError: cannot import name '_normalize_to_dataframe'`.

- [ ] **Step 3: Implement the helper**

In `sftp_csv_upload.py`, add at module scope above the class:

```python
import pandas as pd
from lfx.schema import Data, DataFrame


def _normalize_to_dataframe(value: object) -> pd.DataFrame:
    """Coerce DataFrame / Data / list-of-Data / list-of-dicts to a pandas DataFrame."""
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
                msg = f"data must be DataFrame, Data, or list of Data/dicts; list contained {type(item).__name__}"
                raise TypeError(msg)
        return pd.DataFrame.from_records(records)
    msg = f"data must be DataFrame, Data, or list of Data/dicts; got {type(value).__name__}"
    raise TypeError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py
git commit -m "feat(sftp): add input normalization helper"
```

---

## Task 3: Filename templating helper

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`
- Test: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`

Goal: `_resolve_remote_path(remote_directory, filename, *, now=None) -> str`. Substitutes `{timestamp}` → `YYYYMMDD_HHMMSS` UTC and `{date}` → `YYYYMMDD` UTC. Joins with `posixpath.join`. Rejects resolved filename containing `/`. The `now` parameter is a `time.struct_time` for testability; defaults to `time.gmtime()`.

- [ ] **Step 1: Write the failing tests**

Append to `test_sftp_csv_upload.py`:

```python
import time
from lfx.components.sftp.sftp_csv_upload import _resolve_remote_path

FROZEN = time.struct_time((2026, 4, 15, 14, 30, 22, 0, 0, 0))


def test_resolve_path_literal_filename():
    assert _resolve_remote_path("/exports", "users.csv", now=FROZEN) == "/exports/users.csv"


def test_resolve_path_substitutes_timestamp():
    assert _resolve_remote_path("/exports", "users_{timestamp}.csv", now=FROZEN) == "/exports/users_20260415_143022.csv"


def test_resolve_path_substitutes_date():
    assert _resolve_remote_path("/exports", "users_{date}.csv", now=FROZEN) == "/exports/users_20260415.csv"


def test_resolve_path_substitutes_both_tokens():
    assert _resolve_remote_path("/exports", "{date}/users_{timestamp}.csv", now=FROZEN) is not None  # placeholder, real assert below
```

Replace that last test with the actual one (one assertion only):

```python
def test_resolve_path_rejects_slash_in_filename():
    with pytest.raises(ValueError, match="path separator"):
        _resolve_remote_path("/exports", "sub/users.csv", now=FROZEN)


def test_resolve_path_rejects_slash_after_substitution():
    with pytest.raises(ValueError, match="path separator"):
        _resolve_remote_path("/exports", "{date}/users.csv", now=FROZEN)


def test_resolve_path_uses_gmtime_when_now_omitted():
    out = _resolve_remote_path("/exports", "users_{date}.csv")
    assert out.startswith("/exports/users_") and out.endswith(".csv")
```

(Remove the `test_resolve_path_substitutes_both_tokens` placeholder.)

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: import error on `_resolve_remote_path`.

- [ ] **Step 3: Implement the helper**

Add to `sftp_csv_upload.py`:

```python
import posixpath
import time as _time


def _resolve_remote_path(
    remote_directory: str, filename: str, *, now: _time.struct_time | None = None
) -> str:
    """Substitute time tokens in filename and join with remote_directory.

    Tokens (UTC): {timestamp} -> YYYYMMDD_HHMMSS, {date} -> YYYYMMDD.
    Filenames may not contain '/' after substitution.
    """
    when = now if now is not None else _time.gmtime()
    rendered = filename.replace("{timestamp}", _time.strftime("%Y%m%d_%H%M%S", when))
    rendered = rendered.replace("{date}", _time.strftime("%Y%m%d", when))
    if "/" in rendered:
        msg = "filename must not contain path separator '/'; use remote_directory"
        raise ValueError(msg)
    return posixpath.join(remote_directory, rendered)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py
git commit -m "feat(sftp): add filename templating helper"
```

---

## Task 4: CSV bytes generation helper

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`
- Test: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`

Goal: `_render_csv_bytes(df, *, delimiter, include_header, encoding, quote_char, quoting, line_terminator, null_representation) -> bytes`. Maps the `quoting` dropdown (`Minimal`/`All`/`Non-numeric`/`None`) to `csv.QUOTE_*` constants and writes via `df.to_csv()`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: import error on `_render_csv_bytes`.

- [ ] **Step 3: Implement the helper**

Add to `sftp_csv_upload.py`:

```python
import csv
import io

_QUOTING_MAP = {
    "Minimal": csv.QUOTE_MINIMAL,
    "All": csv.QUOTE_ALL,
    "Non-numeric": csv.QUOTE_NONNUMERIC,
    "None": csv.QUOTE_NONE,
}


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
    """Serialize a DataFrame to CSV bytes with the given options."""
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
```

Note: encoding is applied at the byte stage rather than via pandas' `encoding=` argument so `utf-8-sig` produces a single leading BOM (pandas would otherwise emit one BOM per call to `to_csv` only when writing to a path).

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py
git commit -m "feat(sftp): add CSV bytes renderer"
```

---

## Task 5: Host-key fingerprint callback

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`
- Test: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`

Goal: `_compute_sha256_fingerprint(host_key) -> str` and `_verify_host_key(host_key, expected_fingerprint) -> None`. Fingerprint format is the standard `SHA256:<base64>` form that asyncssh and openssh use, compared case-insensitively after stripping any `SHA256:` prefix.

- [ ] **Step 1: Write the failing tests**

Append:

```python
import base64
import hashlib
from lfx.components.sftp.sftp_csv_upload import _compute_sha256_fingerprint, _verify_host_key


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the helpers**

Add to `sftp_csv_upload.py`:

```python
import base64
import hashlib


def _compute_sha256_fingerprint(host_key) -> str:  # asyncssh.SSHKey
    """Return the openssh-style SHA256 fingerprint (base64, no padding, no prefix)."""
    raw = host_key.export_public_key("openssh")
    digest = hashlib.sha256(raw).digest()
    return base64.b64encode(digest).decode().rstrip("=")


def _verify_host_key(host_key, *, expected: str) -> None:
    """Raise ValueError if the host key's SHA-256 fingerprint does not match expected.

    Accepts both ``SHA256:<base64>`` and bare ``<base64>`` forms (case-insensitive prefix).
    """
    normalized_expected = expected.strip()
    if normalized_expected.lower().startswith("sha256:"):
        normalized_expected = normalized_expected.split(":", 1)[1]
    actual = _compute_sha256_fingerprint(host_key)
    if actual != normalized_expected:
        msg = f"host key fingerprint mismatch: expected SHA256:{normalized_expected}, got SHA256:{actual}"
        raise ValueError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py
git commit -m "feat(sftp): add host-key fingerprint verification"
```

---

## Task 6: Component inputs, dynamic auth toggle, and `build_upload` orchestration

**Files:**
- Modify: `src/lfx/src/lfx/components/sftp/sftp_csv_upload.py`
- Test: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py`

Goal: wire up the full input list with dynamic password vs SSH-key fields, implement `build_upload()`, and add `update_build_config` to toggle field visibility on `auth_method` change. Mock `asyncssh.connect` in tests — this task is purely about orchestration.

- [ ] **Step 1: Write the failing tests**

Append:

```python
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from lfx.components.sftp.sftp_csv_upload import SFTPCSVUploadComponent

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
    """Return (connect_patch, sftp_put_mock) — patch asyncssh.connect to a no-op context."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: many failures — `inputs = []` so component construction will reject the kwargs, and `build_upload` raises `NotImplementedError`.

- [ ] **Step 3: Implement the full component**

Replace the contents of `sftp_csv_upload.py` so it now reads end-to-end as below. Keep all helpers from prior tasks (shown again here for completeness — do not duplicate; this is the final file):

```python
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
        # asyncssh calls this to obtain (trusted_host_keys, trusted_ca_keys, revoked_keys).
        # Returning a callable for trusted_host_keys lets us validate the offered key.
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
        # --- Validate required string fields up front (before any network I/O) ---
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
```

- [ ] **Step 4: Run all unit tests to verify they pass**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/sftp/sftp_csv_upload.py src/lfx/tests/unit/components/sftp/test_sftp_csv_upload.py
git commit -m "feat(sftp): implement SFTP CSV Upload component end-to-end"
```

---

## Task 7: Integration test against in-process asyncssh server

**Files:**
- Create: `src/lfx/tests/unit/components/sftp/test_sftp_csv_upload_integration.py`

Goal: stand up an in-process SFTP server using asyncssh's server APIs on `127.0.0.1:0`, run the component against it, and assert the file landed correctly. Marked `@pytest.mark.integration` so default test runs skip it.

- [ ] **Step 1: Write the failing integration test**

```python
"""Integration test: SFTPCSVUploadComponent against an in-process asyncssh server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncssh
import pytest
from lfx.components.sftp.sftp_csv_upload import SFTPCSVUploadComponent
from lfx.schema import DataFrame

pytestmark = pytest.mark.integration


class _AcceptAllSSHServer(asyncssh.SSHServer):
    def begin_auth(self, username):  # noqa: ARG002
        return True

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username, password) -> bool:  # noqa: ARG002
        return password == "secretpw"  # noqa: S105


async def _start_server(tmp_path: Path):
    host_key = asyncssh.generate_private_key("ssh-rsa")
    host_key_path = tmp_path / "host_key"
    host_key_path.write_bytes(host_key.export_private_key())
    server = await asyncssh.create_server(
        _AcceptAllSSHServer,
        host="127.0.0.1",
        port=0,
        server_host_keys=[str(host_key_path)],
        sftp_factory=True,
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
        result = await component.build_upload()
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
            await component.build_upload()
    finally:
        server.close()
        await server.wait_closed()
```

- [ ] **Step 2: Run the integration test**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/test_sftp_csv_upload_integration.py -v -m integration
```

Expected: both tests pass. (If asyncssh's `sftp_factory=True` requires an explicit `SFTPServer` subclass on this version, the agent should add a no-op `class _SFTPServer(asyncssh.SFTPServer): pass` and pass `sftp_factory=_SFTPServer`. Default file-system rooting is fine for this test.)

- [ ] **Step 3: Run the full unit test suite once more to confirm no regressions**

```bash
uv run --package lfx pytest src/lfx/tests/unit/components/sftp/ -v
```

Expected: all unit + integration tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/lfx/tests/unit/components/sftp/test_sftp_csv_upload_integration.py
git commit -m "test(sftp): add integration test against in-process asyncssh server"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Single component, file layout, `asyncssh` dep — Task 1.
  - Input normalization (DataFrame / Data / list-of-dicts / unsupported type) — Task 2.
  - Filename templating (`{timestamp}`, `{date}`, slash rejection, UTC) — Task 3.
  - All 7 CSV options — Task 4.
  - Optional fingerprint with auto-accept fallback — Task 5 + Task 6 wiring.
  - Auth dispatch (password / SSH key), required-field validation pre-network, dynamic field toggle, asyncssh.connect orchestration, Message output — Task 6.
  - Integration test (happy path + auth failure) — Task 7.
  - 30s connect timeout — set in Task 6 component code.
  - No retries, no auto-mkdir — explicitly absent (no task adds them).
- **Placeholder scan:** none. All steps include exact code, paths, commands, and expected output.
- **Type/name consistency:** `_normalize_to_dataframe`, `_resolve_remote_path`, `_render_csv_bytes`, `_compute_sha256_fingerprint`, `_verify_host_key`, `_make_known_hosts_callback`, `SFTPCSVUploadComponent.build_upload`, `update_build_config` — names are stable across all tasks.
- **Known minor risk:** asyncssh's `known_hosts` callback signature shape varies slightly between releases. The implementation in Task 6 uses the documented `(trusted_host_keys, trusted_ca_keys, revoked_keys)` tuple form with a callable for `trusted_host_keys`. If integration testing reveals signature drift, the implementing agent should consult the installed asyncssh version's docs and adjust `_make_known_hosts_callback` accordingly without changing its public contract.
