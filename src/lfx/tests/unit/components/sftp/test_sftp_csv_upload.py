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
