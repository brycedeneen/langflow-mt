"""Guard test: CoW opt-in must be active across the backend unit suite."""
import pandas as pd


def test_copy_on_write_is_enabled():
    """During the pandas 2.3 -> 3.0 migration we require CoW active via conftest.

    Remove this test (and the conftest opt-in it guards) only after pandas
    bump is live and CoW is the default — at that point the opt-in is a no-op
    but kept for intent.
    """
    assert pd.options.mode.copy_on_write is True
