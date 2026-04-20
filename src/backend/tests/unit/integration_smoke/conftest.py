"""Integration smoke probes for pandas-3 dep overrides.

These probes verify that transitive deps whose pandas<3 caps we override
in pyproject.toml actually work at runtime on pandas 3.0+. Each probe
exercises the dep's pandas surface without network or auth.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "smoke: pandas-3 dep override smoke probes (collected by default).",
    )
