"""DataMapperComponent — deterministic record-level field mapping.

Phase 1a surface: mapping configured via raw JSON in `mapping_config`.
Phase 1b replaces that with a custom UI input (`MappingInput`).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, ClassVar
from uuid import UUID

from pydantic import ValidationError

from lfx.components.processing._data_mapper import MapperConfig, package_output, run
from lfx.custom import Component
from lfx.custom.custom_component.changelog import ChangelogEntry
from lfx.io import DropdownInput, HandleInput, MappingInput, Output
from lfx.schema import Data, DataFrame, Message
from lfx.schema.data import JSON
from lfx.services.deps import get_variable_service, session_scope

logger = logging.getLogger(__name__)


def _resolve_mapping_config(raw: Any) -> MapperConfig:
    """Parse + validate the JSON blob from the mapping_config field."""
    if raw is None or raw == "":
        msg = "mapping_config is empty"
        raise ValueError(msg)
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        msg = f"mapping_config is not valid JSON: {e}"
        raise ValueError(msg) from e
    try:
        return MapperConfig.model_validate(parsed)
    except ValidationError as e:
        msg = f"mapping_config failed validation: {e}"
        raise ValueError(msg) from e


def _normalize_inputs_for_run(raw: Any, n_expected: int) -> list[Any]:
    """Normalize the `inputs` handle value to a positional list of length n_expected.

    Langflow's `HandleInput(is_list=True)` yields a list of upstream values. When only
    one upstream is connected, the value may arrive as a single object.
    """
    if raw is None:
        return [None] * n_expected
    if isinstance(raw, list):
        return list(raw) + [None] * max(0, n_expected - len(raw))
    return [raw] + [None] * (n_expected - 1)


def _unwrap_langflow_type(v: Any) -> Any:
    """Convert Data/DataFrame/Message/JSON back to plain dict or list[dict]."""
    if v is None:
        return None
    if isinstance(v, Data):
        return v.data
    if isinstance(v, JSON):
        return v.data
    if isinstance(v, DataFrame):
        return v.to_dict(orient="records") if hasattr(v, "to_dict") else list(v)
    if isinstance(v, Message):
        try:
            return json.loads(v.text)
        except (json.JSONDecodeError, TypeError):
            return {"text": v.text}
    return v


def _collect_referenced_variable_names(cfg: MapperConfig) -> list[str]:
    """Walk the mapping config and collect every `variable` transform's target name."""
    names: list[str] = []
    for m in cfg.mappings:
        if m.transform == "variable":
            n = m.config.get("variable")
            if isinstance(n, str) and n:
                names.append(n)
    return names


class DataMapperComponent(Component):
    display_name = "Data Mapper"
    description = (
        "Left-join 1..N upstream inputs on declared keys, apply per-destination-field "
        "transforms (direct / template / expression / static / variable / array), "
        "and emit Data / DataFrame / Message / JSON."
    )
    documentation: str = "https://docs.langflow.org/data-mapper"
    icon = "shuffle"
    name = "DataMapper"

    version: int = 2
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(version=1, changes="Initial release."),
        ChangelogEntry(
            version=2,
            changes="Config surface upgraded from raw JSON editor to visual modal.",
            notes="No action needed; existing saved configurations continue to parse.",
        ),
    ]

    inputs = [
        HandleInput(
            name="inputs",
            display_name="Inputs",
            input_types=["Message", "Data", "JSON", "DataFrame"],
            info="Upstream inputs to map from. Positional order must match mapping_config.inputs.",
            is_list=True,
            required=True,
        ),
        MappingInput(
            name="mapping_config",
            display_name="Mapping Config",
            info=(
                "Visual mapping editor. Describes inputs, join keys, destination schema, "
                "and per-field transforms."
            ),
            required=True,
        ),
        DropdownInput(
            name="output_type",
            display_name="Output Type",
            options=["Auto", "Data", "DataFrame", "Message", "JSON"],
            info="Auto: DataFrame when driver is a list, Data when a single record.",
            real_time_refresh=True,
            value="Auto",
        ),
    ]

    outputs = [
        Output(display_name="Data Output", name="data_output", method="build_data", types=["Data"]),
        Output(
            display_name="DataFrame Output",
            name="dataframe_output",
            method="build_dataframe",
            types=["DataFrame"],
        ),
        Output(
            display_name="Message Output",
            name="message_output",
            method="build_message",
            types=["Message"],
        ),
        Output(display_name="JSON Output", name="json_output", method="build_json", types=["JSON"]),
    ]

    async def _collect_variable_values(self, cfg: MapperConfig) -> dict[str, Any]:
        """Pre-resolve all referenced variables (env first, then VariableService).

        Done upfront so the sync engine can consume a plain dict. Unknown names
        are simply absent from the dict; the engine maps that to `_MISSING`.
        """
        names = _collect_referenced_variable_names(cfg)
        if not names:
            return {}

        resolved: dict[str, Any] = {}
        remaining: list[str] = []
        for name in names:
            env_value = os.environ.get(name)
            if env_value is not None:
                resolved[name] = env_value
            else:
                remaining.append(name)

        if not remaining:
            return resolved

        user_id = getattr(self, "_user_id", None)
        if user_id is None:
            # No user context — DB-backed variables are unreachable.
            return resolved

        variable_service = get_variable_service()
        if variable_service is None:
            return resolved

        try:
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        except (ValueError, TypeError):
            logger.warning("DataMapper: could not coerce user_id=%r to UUID", user_id)
            return resolved

        async with session_scope() as session:
            for name in remaining:
                try:
                    value = await variable_service.get_variable(
                        user_id=user_uuid,
                        name=name,
                        field="",
                        session=session,
                    )
                except ValueError:
                    continue  # unknown / null → leave out so engine yields _MISSING
                except Exception:  # noqa: BLE001
                    logger.exception("DataMapper: variable lookup failed for %r", name)
                    continue
                if value is not None:
                    resolved[name] = value
        return resolved

    async def _run_engine(self) -> tuple[list[dict[str, Any]], bool]:
        cfg = _resolve_mapping_config(self.mapping_config)
        raw_inputs = _normalize_inputs_for_run(self.inputs, len(cfg.inputs))
        unwrapped = [_unwrap_langflow_type(v) for v in raw_inputs]
        resolved_vars = await self._collect_variable_values(cfg)
        rows = run(
            cfg,
            inputs=unwrapped,
            variable_resolver=resolved_vars.get,
        )
        driver_was_list = isinstance(unwrapped[cfg.driver_index], list)
        return rows, driver_was_list

    async def build_data(self) -> Data:
        rows, driver_was_list = await self._run_engine()
        selected = "Data" if self.output_type == "Auto" else self.output_type
        result = package_output(rows, output_type=selected, driver_was_list=driver_was_list)
        self.status = result
        return result  # type: ignore[return-value]

    async def build_dataframe(self) -> DataFrame:
        rows, driver_was_list = await self._run_engine()
        selected = "DataFrame" if self.output_type == "Auto" else self.output_type
        result = package_output(rows, output_type=selected, driver_was_list=driver_was_list)
        self.status = result
        return result  # type: ignore[return-value]

    async def build_message(self) -> Message:
        rows, driver_was_list = await self._run_engine()
        result = package_output(rows, output_type="Message", driver_was_list=driver_was_list)
        self.status = result
        return result  # type: ignore[return-value]

    async def build_json(self) -> JSON:
        rows, driver_was_list = await self._run_engine()
        result = package_output(rows, output_type="JSON", driver_was_list=driver_was_list)
        self.status = result
        return result  # type: ignore[return-value]

    _OUTPUT_SPEC: ClassVar[dict[str, dict[str, Any]]] = {
        "Data": {
            "display_name": "Data Output",
            "name": "data_output",
            "method": "build_data",
            "types": ["Data"],
        },
        "DataFrame": {
            "display_name": "DataFrame Output",
            "name": "dataframe_output",
            "method": "build_dataframe",
            "types": ["DataFrame"],
        },
        "Message": {
            "display_name": "Message Output",
            "name": "message_output",
            "method": "build_message",
            "types": ["Message"],
        },
        "JSON": {
            "display_name": "JSON Output",
            "name": "json_output",
            "method": "build_json",
            "types": ["JSON"],
        },
    }

    def update_outputs(
        self,
        frontend_node: dict[str, Any],
        field_name: str,
        field_value: Any,
    ) -> dict[str, Any]:
        if field_name != "output_type":
            return frontend_node

        frontend_node["outputs"] = []
        if field_value == "Auto":
            for spec in self._OUTPUT_SPEC.values():
                frontend_node["outputs"].append(Output(**spec).to_dict())
        elif field_value in self._OUTPUT_SPEC:
            frontend_node["outputs"].append(
                Output(**self._OUTPUT_SPEC[field_value]).to_dict()
            )
        return frontend_node

    async def update_frontend_node(
        self,
        new_frontend_node: dict[str, Any],
        current_frontend_node: dict[str, Any],
    ) -> dict[str, Any]:
        await super().update_frontend_node(new_frontend_node, current_frontend_node)
        output_type = (
            new_frontend_node.get("template", {}).get("output_type", {}).get("value", "Auto")
        )
        self.update_outputs(new_frontend_node, "output_type", output_type)
        return new_frontend_node
