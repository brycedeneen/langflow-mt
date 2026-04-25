"""Peer-index construction for the agent_summary prompt.

A "peer" is a non-legacy component in the same category that the LLM can
legitimately reference when writing the optional 3rd-sentence tradeoff
("Prefer over <peer> when …"). Opted-out components (assist_enabled=False)
remain peer-eligible because they still appear in the canvas picker.
Hand-authored peers cover components that are worth referencing but have
no LLM-generated row of their own (currently DataMapper).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeerEntry:
    component_name: str
    category: str
    display_name: str
    description: str


HAND_AUTHORED_PEERS: dict[str, PeerEntry] = {
    "DataMapper": PeerEntry(
        component_name="DataMapper",
        category="processing",
        display_name="Data Mapper",
        description=(
            "Hyper-precise field-to-field mapping with an explicit schema and transforms. "
            "Very low cost per run; requires technical expertise to author the mapping. "
            "Has its own dedicated configuration agent."
        ),
    ),
}


def build_peer_index(
    classes: list[tuple[type, str]],
) -> dict[str, list[PeerEntry]]:
    """Group classes by category, applying the peer-eligibility rules.

    Eligibility:
    - ``getattr(cls, "legacy", False)`` is True -> EXCLUDED.
    - All others -> INCLUDED (opted-out components stay in the index).

    Hand-authored peers (e.g., DataMapper) are merged into the matching
    category after the class scan.

    Args:
        classes: list of ``(component_class, category)`` tuples produced
            by the walker / generator pipeline.

    Returns:
        ``{category: [PeerEntry, ...]}``. Each list is sorted by
        ``component_name`` for stable prompt output.
    """
    by_category: dict[str, list[PeerEntry]] = {}
    for cls, category in classes:
        if getattr(cls, "legacy", False):
            continue
        entry = PeerEntry(
            component_name=cls.__name__,
            category=category,
            display_name=str(getattr(cls, "display_name", cls.__name__) or cls.__name__),
            description=str(getattr(cls, "description", "") or "").strip(),
        )
        by_category.setdefault(category, []).append(entry)

    for hand_entry in HAND_AUTHORED_PEERS.values():
        by_category.setdefault(hand_entry.category, []).append(hand_entry)

    for category, entries in by_category.items():
        by_category[category] = sorted(entries, key=lambda p: p.component_name)

    return by_category


def format_peers_block(peers: list[PeerEntry], *, exclude: str) -> str:
    """Render the peer list for the prompt, one line per peer, excluding self.

    Returns ``"(no peers in this category)"`` when nothing remains after
    excluding the current component.
    """
    lines = [
        f"- {p.component_name} — {p.display_name} — {p.description}"
        for p in peers
        if p.component_name != exclude
    ]
    if not lines:
        return "(no peers in this category)"
    return "\n".join(lines)
