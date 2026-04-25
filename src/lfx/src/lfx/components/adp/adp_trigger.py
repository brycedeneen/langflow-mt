"""ADP Trigger component: inbound webhook trigger with ADP event filtering."""

from __future__ import annotations

import json
from typing import ClassVar

from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, MultiselectInput, Output
from lfx.schema.data import Data

EVENT_TYPE_MAP: dict[str, list[str]] = {
    "New Hire": [
        "worker.hire",
        "worker.hire.eventNotify",
        "worker.hire.eventNotify.subscribe",
    ],
    "Rehire": [
        "worker.rehire",
        "worker.rehire.eventNotify",
        "worker.rehire.eventNotify.subscribe",
    ],
    "Retirement": [
        "worker.workAssignment.retire",
        "worker.workAssignment.retire.eventNotify",
        "worker.workAssignment.retire.eventNotify.subscribe",
    ],
    "Leave": [
        "worker.onLeave",
        "worker.onLeave.eventNotify",
        "worker.onLeave.eventNotify.subscribe",
    ],
    "Hire Date Change": [
        "worker.workerOriginalHireDate.change",
        "worker.workerOriginalHireDate.change.eventNotify",
        "worker.workerOriginalHireDate.change.eventNotify.subscribe",
    ],
    "Deceased": [
        "worker.deceased",
        "worker.deceased.eventNotify",
        "worker.deceased.eventNotify.subscribe",
    ],
}


def friendly_name_for_adp_id(adp_event_id: str) -> str | None:
    """Return the friendly event name for an ADP event identifier, or None."""
    if not adp_event_id:
        return None
    for friendly, adp_ids in EVENT_TYPE_MAP.items():
        if adp_event_id in adp_ids:
            return friendly
    return None


def _first_event(payload: dict) -> dict:
    events = payload.get("events") if isinstance(payload, dict) else None
    if not events or not isinstance(events, list):
        return {}
    first = events[0]
    return first if isinstance(first, dict) else {}


def _extract_event_id(payload: dict) -> str:
    event = _first_event(payload)
    code = event.get("eventNameCode") or {}
    value = code.get("codeValue") if isinstance(code, dict) else None
    return value if isinstance(value, str) else ""


def _extract_worker(payload: dict) -> dict:
    """Find the worker dict across known ADP event envelope shapes.

    Real ADP event notifications place the worker under ``data.output.worker``.
    Older/alternate samples used ``data.eventContext.worker``. We try both.
    """
    event = _first_event(payload)
    data = event.get("data") or {}
    if not isinstance(data, dict):
        return {}
    for container_key in ("output", "eventContext"):
        container = data.get(container_key)
        if isinstance(container, dict):
            worker = container.get("worker")
            if isinstance(worker, dict):
                return worker
    return {}


def _extract_effective_date(payload: dict) -> str:
    """Return the event's effective date across known ADP envelope shapes.

    Real events carry ``effectiveDateTime`` at the event level. Some variants
    nest it under ``data.transform.effectiveDateTime``. We try the event-level
    field first, then fall back.
    """
    event = _first_event(payload)
    top_level = event.get("effectiveDateTime")
    if isinstance(top_level, str):
        return top_level
    data = event.get("data") or {}
    if isinstance(data, dict):
        transform = data.get("transform") or {}
        if isinstance(transform, dict):
            value = transform.get("effectiveDateTime")
            if isinstance(value, str):
                return value
    return ""


def _event_matches_selection(adp_event_id: str, selected: list[str]) -> bool:
    """Return True if the incoming ADP event id is in the user's selected set."""
    if not selected:
        return False
    friendly = friendly_name_for_adp_id(adp_event_id)
    if friendly is None:
        return False
    return friendly in selected


class ADPTriggerComponent(Component):
    display_name = "ADP Trigger"
    name = "ADPTrigger"
    icon = "webhook"
    documentation: str = "https://docs.langflow.org/component-adp-trigger"
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "Initial release. Inbound webhook trigger that accepts ADP event "
                "notifications and gates them by event type:\n"
                "- Friendly Event Types multiselect (New Hire, Rehire, Retirement, "
                "Leave, Hire Date Change, Deceased) mapped to all known ADP event "
                "identifier variants.\n"
                "- Tolerates real ADP envelope shapes (`data.output.worker`) and "
                "older sample shapes (`data.eventContext.worker`).\n"
                "- Extracts `effectiveDateTime` from event-level or "
                "`data.transform.effectiveDateTime` fallbacks.\n"
                "- Emits a normalized `{event_type, event_id, worker, "
                "effective_date, raw_payload}` Data object; non-matching events "
                "return an empty payload."
            ),
        ),
    ]

    inputs = [
        MultilineInput(
            name="data",
            display_name="Payload",
            info="Receives an ADP event payload via HTTP POST.",
            advanced=True,
        ),
        MultiselectInput(
            name="event_types",
            display_name="Event Types",
            info=(
                "Select which ADP event types this trigger should accept. "
                "Incoming events that do not match any selected type are ignored."
            ),
            options=list(EVENT_TYPE_MAP.keys()),
            value=[],
            advanced=False,
        ),
        MultilineInput(
            name="endpoint",
            display_name="Endpoint",
            value="BACKEND_URL",
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
        MultilineInput(
            name="api_key",
            display_name="API Key",
            info=(
                "Auto-generated API key required for ADP event delivery. "
                "Include as x-api-key header."
            ),
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
    ]
    outputs = [
        Output(display_name="JSON", name="output_data", method="build_data"),
    ]

    def build_data(self) -> Data:
        raw = getattr(self, "data", None)
        if not raw:
            self.status = "No payload received."
            return Data(data={})

        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            self.status = "Invalid JSON payload."
            return Data(data={})

        if not isinstance(payload, dict):
            self.status = "Payload must be a JSON object."
            return Data(data={})

        adp_event_id = _extract_event_id(payload)
        selected = list(getattr(self, "event_types", []) or [])

        if not _event_matches_selection(adp_event_id, selected):
            self.status = f"Event '{adp_event_id}' filtered out (not in selection)."
            return Data(data={})

        friendly = friendly_name_for_adp_id(adp_event_id) or ""
        normalized = {
            "event_type": friendly,
            "event_id": adp_event_id,
            "worker": _extract_worker(payload),
            "effective_date": _extract_effective_date(payload),
            "raw_payload": payload,
        }
        self.status = f"Accepted {friendly} event."
        return Data(data=normalized)
