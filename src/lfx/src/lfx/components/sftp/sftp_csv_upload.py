"""SFTPCSVUploadComponent — serialize tabular data to CSV and upload via SFTP."""

from __future__ import annotations

import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput  # noqa: F401
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


class SFTPCSVUploadComponent(Component):
    display_name = "SFTP CSV Upload"
    description = "Serialize upstream data to CSV and upload to an SFTP server."
    icon = "Upload"
    name = "SFTPCSVUpload"

    inputs = []  # populated in Task 6
    outputs = [Output(display_name="Result", name="result", method="build_upload")]

    async def build_upload(self):  # implemented in Task 6
        raise NotImplementedError
