from __future__ import annotations

import hashlib
import json

from langflow.services.audit.diff import (
    DIFF_BYTE_CAP,
    HASHED_VALUE,
    REDACTED,
    compute_diff_hash,
    hash_value,
    redact_value,
    truncate_diff,
)


def test_redact_value_replaces_strings_wholesale():
    assert redact_value("supersecret") == REDACTED
    assert redact_value(None) == REDACTED


def test_hash_value_is_deterministic_sha256():
    a = {"nodes": [{"id": "x", "data": {"foo": "bar"}}]}
    h1 = hash_value(a)
    h2 = hash_value({"nodes": [{"id": "x", "data": {"foo": "bar"}}]})
    h3 = hash_value({"nodes": [{"id": "y"}]})
    assert h1 == h2
    assert h1 != h3
    # Canonical JSON → sha256 hex
    canon = json.dumps(a, sort_keys=True, separators=(",", ":"))
    assert h1 == hashlib.sha256(canon.encode("utf-8")).hexdigest()


def test_truncate_diff_leaves_small_diffs_untouched():
    diff = {"changed": {"name": {"before": "a", "after": "b"}}}
    assert truncate_diff(diff) == diff


def test_truncate_diff_marks_oversized_payloads():
    big = {"changed": {"name": {"before": "x" * DIFF_BYTE_CAP, "after": "y"}}}
    out = truncate_diff(big)
    assert out["truncated"] is True
    assert out["original_bytes"] >= DIFF_BYTE_CAP
    assert "summary" in out


def test_compute_diff_hash_canonicalizes():
    d1 = {"b": 1, "a": 2}
    d2 = {"a": 2, "b": 1}
    assert compute_diff_hash(d1) == compute_diff_hash(d2)


def test_hashed_value_marker_is_stable():
    assert HASHED_VALUE == "<hashed>"


from uuid import uuid4

from langflow.services.audit.diff import (
    serialize_entity_snapshot,
    build_update_diff,
)


class _FakeVariable:
    __tablename__ = "variable"

    def __init__(self):
        self.id = uuid4()
        self.name = "OPENAI_API_KEY"
        self.value = "secret-ciphertext"
        self.type = "generic"


class _FakeFlow:
    __tablename__ = "flow"

    def __init__(self):
        self.id = uuid4()
        self.name = "my flow"
        self.description = "hello"
        self.data = {"nodes": [{"id": "a"}], "edges": []}
        self.user_id = uuid4()


def test_serialize_variable_redacts_value():
    v = _FakeVariable()
    snap = serialize_entity_snapshot(v)
    assert snap["value"] == REDACTED
    assert snap["name"] == v.name


def test_serialize_flow_hashes_data():
    f = _FakeFlow()
    snap = serialize_entity_snapshot(f)
    assert snap["data"] == {"hash": hash_value(f.data), "marker": HASHED_VALUE}
    assert snap["name"] == f.name


def test_build_update_diff_emits_per_field_delta():
    diff = build_update_diff(
        target_type="flow",
        before_values={"name": "old", "description": "a"},
        after_values={"name": "new", "description": "a", "data": {"nodes": []}},
    )
    assert "changed" in diff
    # Unchanged description omitted; changed name present; data collapses to hash delta.
    assert diff["changed"]["name"] == {"before": "old", "after": "new"}
    assert "description" not in diff["changed"]
    # data: introduced (before None) → after hashed
    d = diff["changed"]["data"]
    assert d["marker"] == HASHED_VALUE
    assert d["after_hash"] == hash_value({"nodes": []})
