import pytest
from unittest.mock import Mock
from uuid import uuid4

from langflow.services.runs.payload import PayloadOffloader
from langflow.services.storage.local import LocalStorageService


@pytest.fixture
async def storage_service(tmp_path):
    settings_service = Mock()
    settings_service.settings.config_dir = str(tmp_path)
    svc = LocalStorageService(Mock(), settings_service)
    yield svc
    await svc.teardown()


@pytest.mark.asyncio
async def test_small_payload_inlines(storage_service):
    off = PayloadOffloader(storage_service, inline_max_bytes=1024)
    run_id = uuid4()
    inline, ref = await off.store(run_id, "inputs", {"a": 1})
    assert inline == {"a": 1}
    assert ref is None


@pytest.mark.asyncio
async def test_large_payload_offloads(storage_service):
    off = PayloadOffloader(storage_service, inline_max_bytes=10)
    run_id = uuid4()
    big = {"a": "x" * 1000}
    inline, ref = await off.store(run_id, "result", big)
    assert inline is None
    assert ref is not None
    loaded = await off.load(ref)
    assert loaded == big
