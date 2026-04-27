def test_error_handler_declares_expected_inputs():
    from lfx.components.reliability.error_handler import ErrorHandler

    component = ErrorHandler()
    input_names = {i.name for i in component.inputs}
    expected = {
        "error_input",
        "max_attempts",
        "alert_mode",
        "bell_audience",
        "bell_specific_user_id",
        "alert_title_template",
        "backoff_strategy",
        "base_delay_seconds",
        "max_delay_seconds",
        "alert_body_template",
    }
    assert input_names == expected


def test_error_handler_has_gave_up_output():
    from lfx.components.reliability.error_handler import ErrorHandler

    component = ErrorHandler()
    output_names = {o.name for o in component.outputs}
    assert "gave_up" in output_names
    gave_up = next(o for o in component.outputs if o.name == "gave_up")
    assert gave_up.types == ["ErrorPayload"]


def test_error_handler_does_not_inject_error_output():
    """ErrorHandler must NOT have an error output (no nested error recovery)."""
    from lfx.components.reliability.error_handler import ErrorHandler

    component = ErrorHandler()
    output_names = {o.name for o in component.outputs}
    assert "error" not in output_names
