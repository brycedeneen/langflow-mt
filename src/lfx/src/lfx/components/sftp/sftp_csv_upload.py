"""SFTPCSVUploadComponent — serialize tabular data to CSV and upload via SFTP."""

from __future__ import annotations

import csv
import io
import posixpath
import time as _time

import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput  # noqa: F401
from lfx.schema import Data, DataFrame


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


class SFTPCSVUploadComponent(Component):
    display_name = "SFTP CSV Upload"
    description = "Serialize upstream data to CSV and upload to an SFTP server."
    icon = "Upload"
    name = "SFTPCSVUpload"

    inputs = []  # populated in Task 6
    outputs = [Output(display_name="Result", name="result", method="build_upload")]

    async def build_upload(self):  # implemented in Task 6
        raise NotImplementedError
