"""Regression tests for Graph snapshot independence.

These pin the contract that ``get_snapshot()`` and ``_snapshot()`` return dicts
whose container values are NOT shared with the live graph state. Mutating the
graph after capturing a snapshot must not change the captured snapshot, and
mutating the snapshot must not change the graph.

If a rewrite of the snapshot path replaces ``copy.deepcopy`` with a structural
shallow copy (the perf/graph-deepcopy plan), these tests catch any over-sharing.
The terminal values inside snapshots are vertex-id strings (immutable), so
sharing those across snapshot/graph is fine; container identity must not be
shared.
"""

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph


def _build_graph() -> Graph:
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(_id="chat_output").set(input_value=chat_input.message_response)
    g = Graph(chat_input, chat_output)
    g.prepare()
    return g


def test_get_snapshot_vertices_layers_is_independent():
    g = _build_graph()
    snap = g.get_snapshot()
    # Mutate graph state after the snapshot.
    g.vertices_layers.append(["new_vertex"])
    if g.vertices_layers and g.vertices_layers[0]:
        g.vertices_layers[0].append("injected")
    # Snapshot must be unchanged.
    for layer_in_snap in snap["vertices_layers"]:
        assert "injected" not in layer_in_snap
    assert ["new_vertex"] not in snap["vertices_layers"]


def test_get_snapshot_run_manager_is_independent():
    g = _build_graph()
    snap = g.get_snapshot()
    # Mutate run_manager state.
    g.run_manager.vertices_to_run.add("synthetic_vertex")
    g.run_manager.run_predecessors["x"] = ["y"]
    # Snapshot must be unchanged.
    rm_snap = snap["run_manager"]
    assert "synthetic_vertex" not in rm_snap["vertices_to_run"]
    assert "x" not in rm_snap["run_predecessors"] or rm_snap["run_predecessors"].get("x") != ["y"]


def test_get_snapshot_run_queue_is_independent():
    g = _build_graph()
    snap = g.get_snapshot()
    g._run_queue.append("synthetic_vertex")
    assert "synthetic_vertex" not in list(snap["run_queue"])


def test_snapshot_mutation_does_not_affect_graph():
    g = _build_graph()
    snap = g.get_snapshot()
    # Mutate the snapshot.
    snap["vertices_layers"].append(["snap_only_layer"])
    if isinstance(snap["run_manager"]["vertices_to_run"], set):
        snap["run_manager"]["vertices_to_run"].add("snap_only_vertex")
    # Live graph must be unchanged.
    assert ["snap_only_layer"] not in g.vertices_layers
    assert "snap_only_vertex" not in g.run_manager.vertices_to_run


def test_private_snapshot_independence():
    """Even though ``_snapshot`` is currently dead on the execution path, the
    rewrite must preserve the same independence contract."""
    g = _build_graph()
    snap = g._snapshot()
    g.vertices_layers.append(["new_layer"])
    g.vertices_to_run.add("synthetic")
    if g.vertices_layers and g.vertices_layers[0]:
        g.vertices_layers[0].append("injected")
    g.run_manager.vertices_to_run.add("rm_synthetic")
    for layer_in_snap in snap["vertices_layers"]:
        assert "injected" not in layer_in_snap
    assert ["new_layer"] not in snap["vertices_layers"]
    assert "synthetic" not in snap["vertices_to_run"]
    assert "rm_synthetic" not in snap["run_manager"]["vertices_to_run"]
