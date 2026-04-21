"""Smoke tests ensuring the _data_mapper package is importable."""

def test_package_imports():
    from lfx.components.processing import _data_mapper  # noqa: F401

def test_submodules_import():
    from lfx.components.processing._data_mapper import (
        config_schema,
        engine,
        join,
        transforms,
    )
    assert all([config_schema, engine, join, transforms])
