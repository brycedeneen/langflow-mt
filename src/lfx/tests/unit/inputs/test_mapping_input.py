import pytest

from lfx.inputs import inputs as inputs_module
from lfx.inputs.input_mixin import FieldTypes


def test_field_types_has_mapping_entry():
    assert FieldTypes.MAPPING.value == "mapping"


def test_mapping_input_class_exists_and_has_correct_field_type():
    cls = inputs_module.MappingInput
    instance = cls(name="mapping_config", display_name="Mapping Config")
    assert instance.field_type == FieldTypes.MAPPING


def test_mapping_input_is_reexported_from_lfx_io():
    from lfx.io import MappingInput as ReexportedMappingInput
    assert ReexportedMappingInput is inputs_module.MappingInput
