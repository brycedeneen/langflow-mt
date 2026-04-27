from typing import ClassVar

from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output


class _EnabledComponent(Component):
    error_output_enabled: ClassVar[bool] = True
    outputs = [Output(display_name="Result", name="result", method="run")]

    def run(self) -> str:
        return "ok"


class _DisabledComponent(Component):
    outputs = [Output(display_name="Result", name="result", method="run")]

    def run(self) -> str:
        return "ok"


def test_enabled_component_has_error_output():
    component = _EnabledComponent()
    output_names = {o.name for o in component.outputs}
    assert "result" in output_names
    assert "error" in output_names

    error_output = next(o for o in component.outputs if o.name == "error")
    assert error_output.display_name == "Error"
    assert error_output.types == ["ErrorPayload"]


def test_disabled_component_lacks_error_output():
    component = _DisabledComponent()
    output_names = {o.name for o in component.outputs}
    assert "error" not in output_names


def test_double_injection_is_idempotent():
    """Re-instantiating doesn't add a second 'error' output."""
    component = _EnabledComponent()
    component2 = _EnabledComponent()
    assert sum(1 for o in component.outputs if o.name == "error") == 1
    assert sum(1 for o in component2.outputs if o.name == "error") == 1


def test_enabled_component_error_in_outputs_map():
    component = _EnabledComponent()
    assert "error" in component._outputs_map
    assert component._outputs_map["error"].types == ["ErrorPayload"]
    assert component._outputs_map["error"].selected == "ErrorPayload"
