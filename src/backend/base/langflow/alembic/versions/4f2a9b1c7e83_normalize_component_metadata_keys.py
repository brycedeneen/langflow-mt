"""normalize component_metadata.component_name to canonical registry keys

Resolves any rows keyed by Python class name (e.g. ``ADPAPIRequestComponent``)
or display name (e.g. ``ADP API Request``) to the canonical live-registry key
(e.g. ``ADPAPIRequest``). Rows that do not resolve to any live component are
deleted (truly stale — the component has been removed or consolidated).

When both the alias-keyed row and a row already keyed by the canonical name
exist, the admin-curated row (``updated_by IS NOT NULL``) wins; if both or
neither are admin-curated, the row already at the canonical key wins.

Revision ID: 4f2a9b1c7e83
Revises: d6b4990402d7
Create Date: 2026-04-26
"""
from __future__ import annotations

import json
import logging
import pathlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers
revision: str = "4f2a9b1c7e83"
down_revision: str | Sequence[str] | None = "d6b4990402d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _component_index_path() -> pathlib.Path:
    """Locate the bundled component_index.json shipped with lfx."""
    try:
        import lfx  # noqa: PLC0415
    except ImportError:
        return pathlib.Path()
    return pathlib.Path(lfx.__file__).resolve().parent / "_assets" / "component_index.json"


def _load_alias_map() -> dict[str, str]:
    """Build {alias: canonical_registry_key} from the bundled component index.

    Aliases include the registry key itself, the display name, and the Python
    class name extracted from each entry's ``metadata.module`` dotted path.
    """
    index_path = _component_index_path()
    aliases: dict[str, str] = {}
    if not index_path.is_file():
        logger.warning("component_index.json not found at %s; skipping normalisation.", index_path)
        return aliases
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        logger.warning("Could not load component_index.json: %s", err)
        return aliases

    entries = index.get("entries") or []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 2:
            continue
        _comp_type, components = entry
        if not isinstance(components, dict):
            continue
        for registry_key, component_data in components.items():
            if not isinstance(registry_key, str) or not isinstance(component_data, dict):
                continue
            aliases[registry_key] = registry_key
            display_name = component_data.get("display_name")
            if isinstance(display_name, str) and display_name:
                aliases.setdefault(display_name, registry_key)
            module_path = (component_data.get("metadata") or {}).get("module")
            if isinstance(module_path, str) and module_path:
                class_name = module_path.rsplit(".", 1)[-1]
                if class_name:
                    aliases.setdefault(class_name, registry_key)
    return aliases


def upgrade() -> None:
    conn = op.get_bind()
    aliases = _load_alias_map()

    rows = conn.execute(
        sa.text("SELECT id, component_name, updated_by FROM component_metadata")
    ).all()

    # Group by what each row should canonically be keyed as. Drop unresolved.
    by_canonical: dict[str, list[dict]] = {}
    unresolved_ids: list = []
    for row in rows:
        canonical = aliases.get(row.component_name)
        if canonical is None:
            unresolved_ids.append(row.id)
            continue
        by_canonical.setdefault(canonical, []).append(
            {
                "id": row.id,
                "component_name": row.component_name,
                "updated_by": row.updated_by,
                "is_canonical": row.component_name == canonical,
            }
        )

    # Delete truly stale rows (no matching live component).
    for row_id in unresolved_ids:
        conn.execute(
            sa.text("DELETE FROM component_metadata WHERE id = :id"),
            {"id": row_id},
        )
    if unresolved_ids:
        logger.info("Deleted %d truly-stale component_metadata rows.", len(unresolved_ids))

    # Resolve duplicates per canonical key, then rename the survivor when needed.
    renamed = 0
    deduped = 0
    for canonical, group in by_canonical.items():
        if len(group) == 1:
            row = group[0]
            if not row["is_canonical"]:
                conn.execute(
                    sa.text(
                        "UPDATE component_metadata SET component_name = :new "
                        "WHERE id = :id"
                    ),
                    {"new": canonical, "id": row["id"]},
                )
                renamed += 1
            continue

        # Multiple rows resolved to the same canonical key. Pick a survivor:
        # 1) admin-curated (updated_by IS NOT NULL) beats non-curated;
        # 2) among ties, the row already at the canonical key wins;
        # 3) among further ties, sort by id for determinism.
        survivor = sorted(
            group,
            key=lambda r: (
                0 if r["updated_by"] is not None else 1,
                0 if r["is_canonical"] else 1,
                str(r["id"]),
            ),
        )[0]

        loser_ids = [r["id"] for r in group if r["id"] != survivor["id"]]
        for lid in loser_ids:
            conn.execute(
                sa.text("DELETE FROM component_metadata WHERE id = :id"),
                {"id": lid},
            )
            deduped += 1

        if not survivor["is_canonical"]:
            conn.execute(
                sa.text(
                    "UPDATE component_metadata SET component_name = :new "
                    "WHERE id = :id"
                ),
                {"new": canonical, "id": survivor["id"]},
            )
            renamed += 1

    if renamed or deduped:
        logger.info(
            "Normalised component_metadata: renamed %d, deduplicated %d.",
            renamed,
            deduped,
        )


def downgrade() -> None:
    # No-op: original alias-keyed rows are not recoverable. The next seed cycle
    # will repopulate canonical-keyed rows from the YAML bundles.
    pass
