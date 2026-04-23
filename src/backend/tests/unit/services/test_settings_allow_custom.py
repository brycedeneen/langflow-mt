"""Regression: LANGFLOW_ALLOW_CUSTOM_COMPONENTS must default to False and parse env-var truthy values."""

from __future__ import annotations

import pytest

from langflow.services.settings.base import Settings


def test_allow_custom_components_defaults_to_false(monkeypatch):
    monkeypatch.delenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", raising=False)
    assert Settings().allow_custom_components is False


@pytest.mark.parametrize("truthy", ["true", "True", "1", "TRUE"])
def test_allow_custom_components_parses_truthy(monkeypatch, truthy):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", truthy)
    assert Settings().allow_custom_components is True


@pytest.mark.parametrize("falsy", ["false", "0", "False", "FALSE"])
def test_allow_custom_components_parses_falsy(monkeypatch, falsy):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", falsy)
    assert Settings().allow_custom_components is False
