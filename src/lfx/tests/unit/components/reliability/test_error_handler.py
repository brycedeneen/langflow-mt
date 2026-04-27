def test_error_handler_imports_clean():
    from lfx.components.reliability.error_handler import ErrorHandler
    assert ErrorHandler.display_name == "Error Handler"
