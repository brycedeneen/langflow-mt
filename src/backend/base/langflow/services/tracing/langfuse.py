from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain_core.callbacks import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


class LangFuseTracer(BaseTracer):
    flow_id: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict = OrderedDict()  # spans that are not ended

        config = self._get_config()
        self._ready: bool = self.setup_langfuse(config) if config else False

    @property
    def ready(self):
        return self._ready

    def setup_langfuse(self, config) -> bool:
        try:
            from langfuse import Langfuse

            self._client = Langfuse(**config)
            # langfuse v3+ replaces the v2 `client.client.health.health()` probe
            # with a high-level auth_check() returning bool.
            try:
                if not self._client.auth_check():
                    logger.debug("Langfuse auth_check failed")
                    return False
            except Exception as e:  # noqa: BLE001
                logger.debug(f"can not connect to Langfuse: {e}")
                return False

            # langfuse v3+ removed client.trace(); a root span implicitly creates
            # the enclosing trace. Trace-level attributes (user_id, session_id)
            # are attached via span.update_trace() on the root.
            self._root_span = self._client.start_span(name=self.flow_id)
            try:
                self._root_span.update_trace(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    metadata={"langflow_trace_id": str(self.trace_id)},
                )
            except Exception as e:  # noqa: BLE001 — tolerate minor-version API shape drift
                logger.debug(f"Langfuse update_trace failed: {e}")
            # Back-compat alias so the rest of the class reads naturally.
            self.trace = self._root_span

        except ImportError:
            logger.exception("Could not import langfuse. Please install it with `pip install langfuse`.")
            return False

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up Langfuse tracer: {e}")
            return False

        return True

    @override
    def add_trace(
        self,
        trace_id: str,  # actualy component id
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        start_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        metadata_: dict = {"from_langflow_component": True, "component_id": trace_id}
        metadata_ |= {"trace_type": trace_type} if trace_type else {}
        metadata_ |= metadata or {}

        name = trace_name.removesuffix(f" ({trace_id})")

        # langfuse v3+ uses start_span on the parent (trace = root span here).
        # start_time is set automatically; we no longer pass it explicitly.
        # Concurrent component builds still flatten to the root; nested parent
        # tracking is left as-is (see commented block in the v2 code for the
        # deferred alternative).
        serialized = serialize({"input": inputs, "metadata": metadata_})
        span = self.trace.start_span(
            name=name,
            input=serialized.get("input"),
            metadata=serialized.get("metadata"),
        )
        _ = start_time  # preserved for future use; langfuse v3 sets automatically

        self.spans[trace_id] = span

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        end_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        span = self.spans.pop(trace_id, None)
        if span:
            output: dict = {}
            output |= outputs or {}
            output |= {"error": str(error)} if error else {}
            output |= {"logs": list(logs)} if logs else {}
            serialized = serialize({"output": output})
            span.update(output=serialized.get("output"))
            # v3+: explicitly end the span. end_time is set by .end() automatically.
            span.end()
            _ = end_time  # v3 sets end_time on .end() — kept for symmetry

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._ready:
            return
        serialized = serialize({"input": inputs, "output": outputs, "metadata": metadata})
        self.trace.update(
            input=serialized.get("input"),
            output=serialized.get("output"),
            metadata=serialized.get("metadata"),
        )
        # v3+: root span must be explicitly ended to flush the trace.
        self.trace.end()

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        if not self._ready:
            return None

        # langfuse v3+ moved the langchain callback to langfuse.langchain and
        # it picks up the current span from OpenTelemetry context automatically.
        try:
            from langfuse.langchain import CallbackHandler
        except ImportError:  # v2 fallback retained for graceful degradation
            stateful_client = self.spans[next(reversed(self.spans))] if len(self.spans) > 0 else self.trace
            return stateful_client.get_langchain_handler()
        return CallbackHandler()

    @staticmethod
    def _get_config() -> dict:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", None)
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", None)
        host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
        if secret_key and public_key and host:
            return {"secret_key": secret_key, "public_key": public_key, "host": host}
        return {}
