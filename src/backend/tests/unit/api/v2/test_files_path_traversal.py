"""Regression: v2 file upload must sanitize filenames and contain paths.

Covers CVE-2026-33309 (GHSA-g2j9-7rj2-gm6c). Tests both layers:
- API sanitization (`../` stripped / rejected at file boundary)
- Storage layer containment (resolved path stays inside flow_id folder)
"""

from __future__ import annotations

import io

import pytest

from langflow.services.deps import get_settings_service


async def test_v2_upload_rejects_path_traversal_filename(client, logged_in_headers):
    """A multipart upload with a `../../` filename must be rejected before
    it lands on disk."""
    traversal_name = "../../evil.txt"
    files = {"file": (traversal_name, io.BytesIO(b"attacker"), "text/plain")}
    resp = await client.post("api/v2/files", headers=logged_in_headers, files=files)
    # Accept any 4xx — schema rejection (422) or explicit 400 both prove the
    # sanitization fired. 2xx would be the vulnerability.
    assert 400 <= resp.status_code < 500, resp.text
    # Make absolutely sure the file did not land on disk escaping the user's
    # storage dir.
    settings = get_settings_service().settings
    from pathlib import Path as P

    escape_target = P(settings.config_dir).resolve().parent / "evil.txt"
    assert not escape_target.exists(), (
        f"path traversal landed at {escape_target}"
    )


@pytest.mark.asyncio
async def test_local_storage_containment(tmp_path):
    """The LocalStorageService must refuse to write outside `data_dir/flow_id/`."""
    from langflow.services.storage.local import LocalStorageService

    svc = LocalStorageService.__new__(LocalStorageService)
    svc.data_dir = tmp_path
    # Bypass StorageService.__init__ — we need neither session nor settings.

    with pytest.raises((ValueError, OSError)):
        await svc.save_file(flow_id="victim", file_name="../../escapee.txt", data=b"payload")

    # Confirm the file did NOT land outside tmp_path.
    assert not (tmp_path.parent / "escapee.txt").exists()
