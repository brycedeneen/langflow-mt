from __future__ import annotations
import json
from typing import Any
from uuid import UUID

from langflow.services.storage.service import StorageService


class PayloadOffloader:
    def __init__(self, storage: StorageService, *, inline_max_bytes: int):
        self.storage = storage
        self.inline_max_bytes = inline_max_bytes

    async def store(self, run_id: UUID, kind: str, payload: Any) -> tuple[Any | None, str | None]:
        data = json.dumps(payload).encode("utf-8")
        if len(data) <= self.inline_max_bytes:
            return payload, None
        file_name = f"{kind}.json"
        await self.storage.save_file(flow_id=str(run_id), file_name=file_name, data=data)
        ref = self.storage.build_full_path(str(run_id), file_name)
        return None, ref

    async def load(self, ref: str) -> Any:
        flow_id, file_name = self.storage.parse_file_path(ref)
        data = await self.storage.get_file(flow_id=flow_id, file_name=file_name)
        return json.loads(data.decode("utf-8"))
