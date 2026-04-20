"""Guard test: CoW opt-in must be active across the lfx unit suite."""
import pandas as pd


def test_copy_on_write_is_enabled():
    assert pd.options.mode.copy_on_write is True
