"""SFTPCSVUploadComponent — serialize tabular data to CSV and upload via SFTP."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput  # noqa: F401


class SFTPCSVUploadComponent(Component):
    display_name = "SFTP CSV Upload"
    description = "Serialize upstream data to CSV and upload to an SFTP server."
    icon = "Upload"
    name = "SFTPCSVUpload"

    inputs = []  # populated in Task 6
    outputs = [Output(display_name="Result", name="result", method="build_upload")]

    async def build_upload(self):  # implemented in Task 6
        raise NotImplementedError
