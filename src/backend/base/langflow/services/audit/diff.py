from __future__ import annotations

import hashlib
import json
from typing import Any

REDACTED = "<redacted>"
HASHED_VALUE = "<hashed>"
DIFF_BYTE_CAP = 64 * 1024  # 64 KB


def redact_value(_unused: Any) -> str:
    return REDACTED


def hash_value(value: Any) -> str:
    canon = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def compute_diff_hash(diff: dict[str, Any]) -> str:
    return hash_value(diff)


def truncate_diff(diff: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(diff, sort_keys=True, separators=(",", ":"), default=str)
    if len(encoded) <= DIFF_BYTE_CAP:
        return diff
    # Build a compact summary from changed keys or after-state keys.
    summary: dict[str, Any] = {}
    if "changed" in diff and isinstance(diff["changed"], dict):
        summary["changed_fields"] = sorted(diff["changed"].keys())[:32]
    elif "after" in diff and isinstance(diff["after"], dict):
        summary["after_keys"] = sorted(diff["after"].keys())[:32]
    elif "before" in diff and isinstance(diff["before"], dict):
        summary["before_keys"] = sorted(diff["before"].keys())[:32]
    return {
        "truncated": True,
        "original_bytes": len(encoded),
        "summary": summary,
    }


# ---- model-aware helpers ----

# Fields excluded from all diffs (noise / housekeeping).
_EXCLUDED_FIELDS: frozenset[str] = frozenset({"updated_at", "created_at"})

# Per-tablename redaction: field name -> "redact"
_REDACT: dict[str, frozenset[str]] = {
    "variable": frozenset({"value"}),
}

# Per-tablename hash-only fields (big JSON graphs).
_HASH_ONLY: dict[str, frozenset[str]] = {
    "flow": frozenset({"data"}),
    "template": frozenset({"data"}),
}


def _model_table_name(instance: Any) -> str:
    return getattr(instance.__class__, "__tablename__", instance.__class__.__name__.lower())


def _column_names(instance: Any) -> list[str]:
    # Instance.__dict__ keys excluding SQLAlchemy internals; fallback via __fields__ for SQLModel.
    cls = instance.__class__
    fields = getattr(cls, "model_fields", None)
    if fields:
        return list(fields.keys())
    return [k for k in vars(instance) if not k.startswith("_")]


def serialize_entity_snapshot(instance: Any) -> dict[str, Any]:
    """Serialize an entity for create/delete diffs, applying redaction + hash-only rules."""
    table = _model_table_name(instance)
    redact_fields = _REDACT.get(table, frozenset())
    hash_fields = _HASH_ONLY.get(table, frozenset())

    snapshot: dict[str, Any] = {}
    for field_name in _column_names(instance):
        if field_name in _EXCLUDED_FIELDS:
            continue
        value = getattr(instance, field_name, None)
        if field_name in redact_fields:
            snapshot[field_name] = REDACTED
        elif field_name in hash_fields and value is not None:
            snapshot[field_name] = {"marker": HASHED_VALUE, "hash": hash_value(value)}
        else:
            snapshot[field_name] = _to_jsonable(value)
    return snapshot


def build_update_diff(
    *,
    target_type: str,
    before_values: dict[str, Any],
    after_values: dict[str, Any],
) -> dict[str, Any]:
    """Build a per-field delta.

    `before_values` and `after_values` must already be flat dict snapshots
    (produced by the listener via attribute history).
    """
    redact_fields = _REDACT.get(target_type, frozenset())
    hash_fields = _HASH_ONLY.get(target_type, frozenset())
    changed: dict[str, Any] = {}

    keys = set(before_values) | set(after_values)
    for field_name in sorted(keys):
        if field_name in _EXCLUDED_FIELDS:
            continue
        b = before_values.get(field_name)
        a = after_values.get(field_name)
        if b == a:
            continue
        if field_name in redact_fields:
            changed[field_name] = {"before": REDACTED, "after": REDACTED}
        elif field_name in hash_fields:
            changed[field_name] = {
                "marker": HASHED_VALUE,
                "before_hash": hash_value(b) if b is not None else None,
                "after_hash": hash_value(a) if a is not None else None,
            }
        else:
            changed[field_name] = {"before": _to_jsonable(b), "after": _to_jsonable(a)}

    return {"changed": changed}


def _to_jsonable(value: Any) -> Any:
    """Coerce to JSON-safe primitives; UUIDs/datetimes become strings."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    return str(value)
