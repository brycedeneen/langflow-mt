"""Tests for peer-index construction."""
from __future__ import annotations

from scripts._agent_metadata_gen.peers import (
    HAND_AUTHORED_PEERS,
    PeerEntry,
    build_peer_index,
    format_peers_block,
)


def _comp(
    name: str,
    *,
    category: str,
    display_name: str = "",
    description: str = "",
    legacy: bool = False,
    assist_enabled: bool = True,
):
    cls = type(name, (), {})
    cls.display_name = display_name or name
    cls.description = description
    cls.legacy = legacy
    cls.assist_enabled = assist_enabled
    cls.__category__ = category  # test helper; build_peer_index actually consumes (cls, category) tuples
    return cls


def test_index_groups_by_category_and_excludes_legacy():
    classes = [
        (_comp("Alpha", category="x", description="desc-a"), "x"),
        (_comp("Beta", category="x", description="desc-b", legacy=True), "x"),
        (_comp("Gamma", category="y", description="desc-g"), "y"),
    ]
    idx = build_peer_index(classes)
    assert sorted(p.component_name for p in idx["x"]) == ["Alpha"]
    assert sorted(p.component_name for p in idx["y"]) == ["Gamma"]


def test_index_includes_opted_out_components():
    """Opted-out components still appear in the canvas picker, so they remain peer-eligible."""
    classes = [
        (_comp("OptedOut", category="z", description="desc-o", assist_enabled=False), "z"),
        (_comp("Visible", category="z", description="desc-v"), "z"),
    ]
    idx = build_peer_index(classes)
    assert sorted(p.component_name for p in idx["z"]) == ["OptedOut", "Visible"]


def test_index_merges_hand_authored_peers():
    """Hand-authored peers are merged into the matching category."""
    classes = [
        (_comp("StructuredOutput", category="processing", description="natural-language extraction"), "processing"),
    ]
    idx = build_peer_index(classes)
    names = sorted(p.component_name for p in idx["processing"])
    assert "DataMapper" in names  # comes from HAND_AUTHORED_PEERS
    assert "StructuredOutput" in names


def test_format_peers_block_excludes_self_and_renders_one_line_each():
    peers = [
        PeerEntry(component_name="A", category="x", display_name="A Comp", description="does a"),
        PeerEntry(component_name="B", category="x", display_name="B Comp", description="does b"),
        PeerEntry(component_name="Self", category="x", display_name="Self", description="ignored"),
    ]
    block = format_peers_block(peers, exclude="Self")
    lines = [line for line in block.splitlines() if line.strip()]
    assert lines == [
        "- A — A Comp — does a",
        "- B — B Comp — does b",
    ]


def test_format_peers_block_returns_placeholder_when_empty():
    assert format_peers_block([], exclude="X") == "(no peers in this category)"


def test_format_peers_block_marks_canonical_peers():
    """`is_canonical=True` peers render with a `(canonical alternative)` marker so the
    prompt rule can bias the LLM toward picking them for the tradeoff sentence."""
    peers = [
        PeerEntry(component_name="Plain", category="x", display_name="Plain", description="ordinary"),
        PeerEntry(
            component_name="DataMapper",
            category="x",
            display_name="Data Mapper",
            description="hand-flagged",
            is_canonical=True,
        ),
    ]
    block = format_peers_block(peers, exclude="X")
    assert "- Plain — Plain — ordinary" in block
    assert "- DataMapper (canonical alternative) — Data Mapper — hand-flagged" in block


def test_hand_authored_data_mapper_entry_present():
    """The DataMapper hand-authored entry is the canonical example."""
    assert "DataMapper" in HAND_AUTHORED_PEERS
    entry = HAND_AUTHORED_PEERS["DataMapper"]
    assert entry.category == "processing"
    assert "low cost" in entry.description.lower() or "precise" in entry.description.lower()


def test_hand_authored_peer_appears_in_extra_categories():
    """Hand-authored peers with `extra_categories` show up in those categories' peer lists.

    DataMapper (home category=processing) declares extra_categories=("llm_operations",)
    so that StructuredOutput (in llm_operations) sees it as a peer for the canonical
    "Prefer over Data Mapper when ..." tradeoff sentence.
    """
    classes = [
        (_comp("StructuredOutputComponent", category="llm_operations", description="LLM-driven extraction"), "llm_operations"),
    ]
    idx = build_peer_index(classes)
    names_in_llm_ops = sorted(p.component_name for p in idx["llm_operations"])
    assert "DataMapper" in names_in_llm_ops
    assert "StructuredOutputComponent" in names_in_llm_ops


def test_hand_authored_peer_still_appears_in_home_category():
    """Adding extra_categories must not remove the peer from its primary category."""
    classes = [
        (_comp("OtherProcessing", category="processing", description="some processing"), "processing"),
    ]
    idx = build_peer_index(classes)
    names_in_processing = sorted(p.component_name for p in idx["processing"])
    assert "DataMapper" in names_in_processing
    assert "OtherProcessing" in names_in_processing
