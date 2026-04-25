"""Tests for autosecret marker / Vault path helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from langflow.services.variable.auto_secrets import (
    LEGACY_AUTOSECRET_PREFIX,
    NEW_AUTOSECRET_PREFIX as AUTOSECRET_PREFIX,
    autosecret_marker,
    autosecret_vault_path,
    parse_autosecret_marker,
)


FLOW_ID = UUID("4312a8ac-22db-4d86-805e-86d19451c489")
ORG_ID = UUID("11111111-2222-3333-4444-555555555555")


def test_prefixes_are_distinct():
    assert AUTOSECRET_PREFIX == "__autosecret|"
    assert LEGACY_AUTOSECRET_PREFIX == "__autosecret_"
    assert AUTOSECRET_PREFIX != LEGACY_AUTOSECRET_PREFIX


def test_autosecret_marker_format():
    marker = autosecret_marker(FLOW_ID, "ADPAuth-fMRCo", "client_secret")
    assert marker == f"__autosecret|{FLOW_ID}|ADPAuth-fMRCo|client_secret"
    assert marker.startswith(AUTOSECRET_PREFIX)


def test_autosecret_vault_path_format():
    path = autosecret_vault_path(ORG_ID, FLOW_ID, "ADPAuth-fMRCo", "cert_pem")
    assert path == f"{ORG_ID}/flows/{FLOW_ID}/autosecrets/ADPAuth-fMRCo/cert_pem"


def test_parse_round_trip():
    marker = autosecret_marker(FLOW_ID, "ADPAuth-fMRCo", "client_secret")
    flow_id, node_id, field_name = parse_autosecret_marker(marker)
    assert flow_id == FLOW_ID
    assert node_id == "ADPAuth-fMRCo"
    assert field_name == "client_secret"


def test_parse_handles_underscores_in_node_id_and_field_name():
    marker = autosecret_marker(FLOW_ID, "Some_Node-1", "client_secret")
    flow_id, node_id, field_name = parse_autosecret_marker(marker)
    assert node_id == "Some_Node-1"
    assert field_name == "client_secret"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-an-autosecret",
        "__autosecret_old-style",
        "__autosecret|too|few",
        f"__autosecret|{FLOW_ID}|node",
        f"__autosecret|not-a-uuid|node|field",
    ],
)
def test_parse_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_autosecret_marker(bad)
