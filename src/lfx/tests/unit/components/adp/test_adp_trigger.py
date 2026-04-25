"""Unit tests for ADPTriggerComponent."""

import json  # used by later tests

import pytest  # noqa: F401  # used by later test fixtures
from lfx.components.adp.adp_trigger import EVENT_TYPE_MAP, ADPTriggerComponent
from lfx.schema.data import Data  # used by later tests


def test_component_class_metadata():
    assert ADPTriggerComponent.name == "ADPTrigger"
    assert ADPTriggerComponent.display_name == "ADP Trigger"
    assert ADPTriggerComponent.icon  # non-empty string


def test_event_type_map_covers_all_spec_entries():
    # Exactly the six friendly names called out in the spec
    assert set(EVENT_TYPE_MAP.keys()) == {
        "New Hire",
        "Rehire",
        "Retirement",
        "Leave",
        "Hire Date Change",
        "Deceased",
    }


def test_event_type_map_values_are_non_empty_lists_of_strings():
    for friendly, adp_ids in EVENT_TYPE_MAP.items():
        assert isinstance(adp_ids, list), f"{friendly} must map to a list"
        assert adp_ids, f"{friendly} must map to at least one ADP id"
        assert all(isinstance(x, str) and x for x in adp_ids)


def test_reverse_lookup_friendly_name_for_known_adp_ids():
    from lfx.components.adp.adp_trigger import friendly_name_for_adp_id

    assert friendly_name_for_adp_id("worker.hire.eventNotify") == "New Hire"
    assert friendly_name_for_adp_id("worker.rehire.eventNotify") == "Rehire"
    assert (
        friendly_name_for_adp_id("worker.rehire.eventNotify.subscribe") == "Rehire"
    )
    assert (
        friendly_name_for_adp_id("worker.deceased.eventNotify.subscribe")
        == "Deceased"
    )


def test_reverse_lookup_returns_none_for_unknown_adp_id():
    from lfx.components.adp.adp_trigger import friendly_name_for_adp_id

    assert friendly_name_for_adp_id("worker.unknown.eventNotify") is None
    assert friendly_name_for_adp_id("") is None


def _input_by_name(component_cls, input_name: str):
    for inp in component_cls.inputs:
        if inp.name == input_name:
            return inp
    return None


def test_component_has_data_input_like_webhook():
    data_input = _input_by_name(ADPTriggerComponent, "data")
    assert data_input is not None
    # Same field_type family as WebhookComponent.data (MultilineInput -> TEXT)
    assert data_input.display_name == "Payload"
    assert data_input.advanced is True


def test_component_has_event_types_multiselect():
    et = _input_by_name(ADPTriggerComponent, "event_types")
    assert et is not None, "event_types input must be declared"
    # MultiselectInput stores list values; options must be the six friendly names
    assert set(et.options) == set(EVENT_TYPE_MAP.keys())
    assert isinstance(et.value, list)


def test_component_has_endpoint_and_api_key_display_fields():
    endpoint = _input_by_name(ADPTriggerComponent, "endpoint")
    api_key = _input_by_name(ADPTriggerComponent, "api_key")
    assert endpoint is not None
    assert api_key is not None
    assert endpoint.advanced is False
    assert api_key.advanced is False


def test_component_has_single_output_named_output_data():
    outs = ADPTriggerComponent.outputs
    assert len(outs) == 1
    assert outs[0].name == "output_data"
    assert outs[0].method == "build_data"


# --- Payload extraction ---

HIRE_PAYLOAD = {
    "events": [
        {
            "eventID": "EV-1",
            "eventNameCode": {"codeValue": "worker.hire.eventNotify"},
            "data": {
                "eventContext": {
                    "worker": {
                        "associateOID": "G3H",
                        "workerID": {"idValue": "100123"},
                        "person": {"legalName": {"formattedName": "Jane Doe"}},
                    }
                },
                "transform": {"effectiveDateTime": "2026-04-01T00:00:00Z"},
            },
        }
    ]
}


def test_extract_event_id_from_well_formed_payload():
    from lfx.components.adp.adp_trigger import _extract_event_id

    assert _extract_event_id(HIRE_PAYLOAD) == "worker.hire.eventNotify"


def test_extract_event_id_missing_returns_empty_string():
    from lfx.components.adp.adp_trigger import _extract_event_id

    assert _extract_event_id({}) == ""
    assert _extract_event_id({"events": []}) == ""
    assert _extract_event_id({"events": [{}]}) == ""
    assert _extract_event_id({"events": [{"eventNameCode": {}}]}) == ""


def test_extract_worker_returns_dict_or_empty():
    from lfx.components.adp.adp_trigger import _extract_worker

    worker = _extract_worker(HIRE_PAYLOAD)
    assert worker["associateOID"] == "G3H"
    assert worker["workerID"]["idValue"] == "100123"

    assert _extract_worker({}) == {}
    assert _extract_worker({"events": [{"data": {}}]}) == {}


def test_extract_effective_date_returns_string_or_empty():
    from lfx.components.adp.adp_trigger import _extract_effective_date

    assert _extract_effective_date(HIRE_PAYLOAD) == "2026-04-01T00:00:00Z"
    assert _extract_effective_date({}) == ""
    assert _extract_effective_date({"events": [{"data": {"transform": {}}}]}) == ""


# --- Event filtering ---


def test_event_matches_selection_by_friendly_name():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.hire.eventNotify",
        selected=["New Hire"],
    ) is True


def test_event_matches_selection_supports_multi_id_friendly_name():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.rehire.eventNotify.subscribe",
        selected=["Rehire"],
    ) is True
    assert _event_matches_selection(
        adp_event_id="worker.rehire.eventNotify",
        selected=["Rehire"],
    ) is True


def test_event_does_not_match_when_not_selected():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.deceased.eventNotify.subscribe",
        selected=["New Hire", "Rehire"],
    ) is False


def test_event_does_not_match_when_selection_empty():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    # An empty selection means nothing is accepted — "opt-in" semantics
    assert _event_matches_selection(
        adp_event_id="worker.hire.eventNotify",
        selected=[],
    ) is False


def test_event_does_not_match_for_unknown_adp_id():
    from lfx.components.adp.adp_trigger import _event_matches_selection

    assert _event_matches_selection(
        adp_event_id="worker.unknown.eventNotify",
        selected=["New Hire", "Rehire"],
    ) is False


# --- build_data happy path ---


def _make_component(data: str | None, event_types: list[str]) -> ADPTriggerComponent:
    """Instantiate the component with raw inputs mirroring runtime attributes."""
    c = ADPTriggerComponent()
    c.data = data
    c.event_types = event_types
    return c


def test_build_data_passes_through_matched_event():
    payload = HIRE_PAYLOAD
    c = _make_component(data=json.dumps(payload), event_types=["New Hire"])

    result = c.build_data()

    assert isinstance(result, Data)
    assert result.data["event_type"] == "New Hire"
    assert result.data["event_id"] == "worker.hire.eventNotify"
    assert result.data["worker"]["associateOID"] == "G3H"
    assert result.data["effective_date"] == "2026-04-01T00:00:00Z"
    assert result.data["raw_payload"] == payload


# --- build_data filtering & edge cases ---


def test_build_data_drops_unmatched_event_type():
    c = _make_component(data=json.dumps(HIRE_PAYLOAD), event_types=["Rehire"])

    result = c.build_data()

    assert isinstance(result, Data)
    assert result.data == {}
    assert "filtered out" in (c.status or "").lower()


def test_build_data_drops_when_selection_is_empty():
    c = _make_component(data=json.dumps(HIRE_PAYLOAD), event_types=[])

    result = c.build_data()

    assert result.data == {}


def test_build_data_returns_empty_on_none_data():
    c = _make_component(data=None, event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}
    assert "no payload" in (c.status or "").lower()


def test_build_data_returns_empty_on_invalid_json():
    c = _make_component(data="not-json-at-all", event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}
    assert "invalid json" in (c.status or "").lower()


def test_build_data_returns_empty_on_non_object_payload():
    c = _make_component(data=json.dumps(["array", "not", "object"]), event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}


def test_build_data_handles_payload_missing_events_array():
    # Payload is a valid object but has no `events` key — treat as "no matching event"
    c = _make_component(data=json.dumps({"foo": "bar"}), event_types=["New Hire"])

    result = c.build_data()

    assert result.data == {}


# --- Bundle smoke ---


def test_component_importable_from_adp_bundle_root():
    from lfx.components.adp import ADPTriggerComponent as FromBundle

    assert FromBundle is ADPTriggerComponent


# --- Real-world ADP payload shapes ---

REAL_ADP_HIRE_PAYLOAD = {
    "events": [
        {
            "eventID": "fa83e726-dcae-48e3-a83e-8294e4320aa1",
            "eventNameCode": {"codeValue": "worker.hire"},
            "data": {
                "output": {
                    "worker": {
                        "associateOID": "G3RTBS62BXQJQMD6",
                        "workerID": {"idValue": "BKQ8EMBCE"},
                        "person": {
                            "legalName": {
                                "formattedName": "NewHire, Test794108292 two",
                            },
                        },
                    },
                },
            },
            "serviceCategoryCode": {"codeValue": "HR"},
            "eventStatusCode": {"codeValue": "COMPLETED"},
            "effectiveDateTime": "2020-06-15T04:00:00.000+0000",
        }
    ]
}


def test_reverse_lookup_accepts_base_event_id_without_eventnotify_suffix():
    from lfx.components.adp.adp_trigger import friendly_name_for_adp_id

    assert friendly_name_for_adp_id("worker.hire") == "New Hire"
    assert friendly_name_for_adp_id("worker.deceased") == "Deceased"
    assert friendly_name_for_adp_id("worker.onLeave") == "Leave"


def test_extract_worker_finds_data_output_worker_path():
    from lfx.components.adp.adp_trigger import _extract_worker

    worker = _extract_worker(REAL_ADP_HIRE_PAYLOAD)
    assert worker["associateOID"] == "G3RTBS62BXQJQMD6"
    assert worker["workerID"]["idValue"] == "BKQ8EMBCE"


def test_extract_effective_date_finds_event_level_field():
    from lfx.components.adp.adp_trigger import _extract_effective_date

    assert (
        _extract_effective_date(REAL_ADP_HIRE_PAYLOAD)
        == "2020-06-15T04:00:00.000+0000"
    )


def test_build_data_normalizes_real_world_hire_payload():
    c = _make_component(
        data=json.dumps(REAL_ADP_HIRE_PAYLOAD),
        event_types=["New Hire", "Retirement", "Deceased"],
    )

    result = c.build_data()

    assert result.data["event_type"] == "New Hire"
    assert result.data["event_id"] == "worker.hire"
    assert result.data["worker"]["associateOID"] == "G3RTBS62BXQJQMD6"
    assert result.data["effective_date"] == "2020-06-15T04:00:00.000+0000"
    assert result.data["raw_payload"] == REAL_ADP_HIRE_PAYLOAD
