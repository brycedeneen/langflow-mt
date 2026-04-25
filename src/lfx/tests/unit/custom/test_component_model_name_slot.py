from __future__ import annotations

from lfx.custom.custom_component.component import Component


def test_fresh_component_has_model_name_slot_defaulted_to_none():
    component = Component()
    assert hasattr(component, "_model_name")
    assert component._model_name is None
