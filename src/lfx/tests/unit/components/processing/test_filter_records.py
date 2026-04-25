from lfx.components.processing.filter_records import FilterRecordsComponent


def test_component_metadata():
    assert FilterRecordsComponent.display_name == "Filter Records"
    assert FilterRecordsComponent.name == "FilterRecords"
    assert FilterRecordsComponent.icon == "filter"
    assert FilterRecordsComponent.version == 1
    assert len(FilterRecordsComponent.changelog) == 1
    assert FilterRecordsComponent.changelog[0].version == 1


def test_component_declares_expected_inputs():
    input_names = [i.name for i in FilterRecordsComponent.inputs]
    assert input_names == ["records", "conditions", "combinator", "mode"]


def test_component_declares_two_outputs():
    output_names = [o.name for o in FilterRecordsComponent.outputs]
    assert output_names == ["matched", "unmatched"]


def test_component_keywords_include_filter():
    assert "filter" in FilterRecordsComponent.metadata["keywords"]
