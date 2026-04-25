from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lfx.graph.vertex.base import Vertex
from lfx.schema.properties import Usage


def _make_vertex_stub(*, model_name: str | None, usage: Usage | None) -> Vertex:
    """Construct just enough of a Vertex to invoke finalize_build."""
    stub = Vertex.__new__(Vertex)
    stub.is_output = False
    stub.custom_component = SimpleNamespace(_token_usage=usage, _model_name=model_name)
    stub.id = "vertex-1"
    stub.display_name = "Test"
    stub.outputs_logs = {}
    stub.logs = {}
    stub.artifacts_raw = {}
    stub.artifacts = {}
    stub.get_built_result = lambda: {}
    stub.set_artifacts = lambda: None
    stub.extract_messages_from_artifacts = lambda *_a, **_kw: []
    stub.set_result = MagicMock()
    return stub


def test_finalize_build_stamps_model_name_and_cost_when_pricing_known():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name="my-model", usage=usage)

    pricing = MagicMock()
    pricing.compute_cost_micros.return_value = 123_456

    settings = SimpleNamespace(cost_tracking_enabled=True)

    with (
        patch("lfx.graph.vertex.base._get_pricing_service", return_value=pricing),
        patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)),
    ):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_called_once_with("my-model", input_tokens=1000, output_tokens=500)
    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name == "my-model"
    assert result_data.token_usage.cost_micros == 123_456


def test_finalize_build_skips_cost_when_tracking_disabled():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name="my-model", usage=usage)

    pricing = MagicMock()
    settings = SimpleNamespace(cost_tracking_enabled=False)

    with (
        patch("lfx.graph.vertex.base._get_pricing_service", return_value=pricing),
        patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)),
    ):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_not_called()
    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name == "my-model"
    assert result_data.token_usage.cost_micros is None


def test_finalize_build_skips_cost_when_model_name_missing():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name=None, usage=usage)

    pricing = MagicMock()
    settings = SimpleNamespace(cost_tracking_enabled=True)

    with (
        patch("lfx.graph.vertex.base._get_pricing_service", return_value=pricing),
        patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)),
    ):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_not_called()
    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name is None
    assert result_data.token_usage.cost_micros is None


def test_finalize_build_handles_unpriced_model():
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    vertex = _make_vertex_stub(model_name="unpriced-model", usage=usage)

    pricing = MagicMock()
    pricing.compute_cost_micros.return_value = None

    settings = SimpleNamespace(cost_tracking_enabled=True)

    with (
        patch("lfx.graph.vertex.base._get_pricing_service", return_value=pricing),
        patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)),
    ):
        vertex.finalize_build()

    result_data = vertex.set_result.call_args.args[0]
    assert result_data.token_usage.model_name == "unpriced-model"
    assert result_data.token_usage.cost_micros is None


def test_finalize_build_resolves_model_name_from_list_of_dicts():
    """Regression: the agent's self.model is a list-of-dicts; finalize_build
    must receive a string model id (not a list) to look up pricing.

    The contract enforced by extract_model_name() is that by the time
    finalize_build runs, ``_model_name`` has already been resolved to a clean
    string. This test documents that contract end-to-end.
    """
    usage = Usage(input_tokens=1000, output_tokens=500, total_tokens=1500)
    # Simulate a stamp that already extracted the name (matches the new helper):
    vertex = _make_vertex_stub(model_name="claude-haiku-4-5-20251001", usage=usage)

    pricing = MagicMock()
    pricing.compute_cost_micros.return_value = 50_000

    settings = SimpleNamespace(cost_tracking_enabled=True)

    with (
        patch("lfx.graph.vertex.base._get_pricing_service", return_value=pricing),
        patch("lfx.graph.vertex.base.get_settings_service", return_value=SimpleNamespace(settings=settings)),
    ):
        vertex.finalize_build()

    pricing.compute_cost_micros.assert_called_once_with(
        "claude-haiku-4-5-20251001", input_tokens=1000, output_tokens=500
    )
