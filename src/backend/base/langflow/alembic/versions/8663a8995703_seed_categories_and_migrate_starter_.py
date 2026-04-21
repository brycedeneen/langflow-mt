"""seed categories and migrate starter templates

Revision ID: 8663a8995703
Revises: 7c8e4f1a2d9b
Create Date: 2026-04-21
"""
from __future__ import annotations

import json
import pathlib
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8663a8995703"
down_revision: str | None = "7c8e4f1a2d9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIXTURE_DIR = pathlib.Path(__file__).parent / "category_rework_fixtures"

_CATEGORY_SEEDS: list[dict[str, str]] = [
    {"name": "Agents",             "icon": "bot",             "color": "rose"},
    {"name": "Assistants",         "icon": "users-round",     "color": "slate"},
    {"name": "Classification",     "icon": "tag",             "color": "amber"},
    {"name": "Coding",             "icon": "code",            "color": "violet"},
    {"name": "Content Generation", "icon": "book-open",       "color": "emerald"},
    {"name": "Prompting",          "icon": "message-square",  "color": "fuchsia"},
    {"name": "Q&A",                "icon": "help-circle",     "color": "sky"},
    {"name": "RAG",                "icon": "database",        "color": "indigo"},
    {"name": "Web Scraping",       "icon": "globe",           "color": "teal"},
    {"name": "ADP",                "icon": "briefcase",       "color": "orange"},
    {"name": "SFTP",               "icon": "upload-cloud",    "color": "cyan"},
]

# Tag strings found in starter JSON → category name (or None to skip).
_TAG_TO_CATEGORY: dict[str, str | None] = {
    "assistants": "Assistants",
    "classification": "Classification",
    "coding": "Coding",
    "content-generation": "Content Generation",
    "q-a": "Q&A",
    "chatbots": "Prompting",
    "rag": "RAG",
    "agents": "Agents",
    "agent": "Agents",          # alias
    "web-scraping": "Web Scraping",
    "adp": "ADP",
    "sftp": "SFTP",
    "openai": None,             # vendor — skip
    "astradb": None,            # vendor — skip
    "hybrid": None,             # modifier — skip
}


def _seed_categories(conn, now):
    name_to_id: dict[str, uuid.UUID] = {}
    for seed in _CATEGORY_SEEDS:
        existing = conn.execute(
            sa.text("SELECT id FROM category WHERE LOWER(name) = LOWER(:name)"),
            {"name": seed["name"]},
        ).first()
        if existing:
            name_to_id[seed["name"]] = existing[0]
            continue
        new_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO category (id, name, icon, color, created_at, updated_at) "
                "VALUES (:id, :n, :i, :c, :ts, :ts)"
            ),
            {"id": str(new_id), "n": seed["name"], "i": seed["icon"], "c": seed["color"], "ts": now},
        )
        name_to_id[seed["name"]] = new_id
    return name_to_id


def _import_starters(conn, now, name_to_id):
    for json_path in sorted(FIXTURE_DIR.glob("*.json")):
        if json_path.name.endswith(".metadata.json"):
            continue
        data = json.loads(json_path.read_text())
        name = data["name"]

        # Idempotence
        existing = conn.execute(
            sa.text(
                "SELECT id FROM template "
                "WHERE LOWER(name) = LOWER(:name) AND scope = 'platform' AND org_id IS NULL"
            ),
            {"name": name},
        ).first()
        if existing:
            continue

        tid = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO template "
                "(id, name, description, icon, gradient, scope, org_id, nodes, edges, "
                "created_by, updated_by, created_at, updated_at) "
                "VALUES (:id, :n, :d, :icon, :g, 'platform', NULL, :nodes, :edges, "
                "NULL, NULL, :ts, :ts)"
            ),
            {
                "id": str(tid),
                "n": name,
                "d": data.get("description"),
                "icon": data.get("icon") or "bot",
                "g": data.get("gradient") or "1",
                "nodes": json.dumps(data.get("data", {}).get("nodes", [])),
                "edges": json.dumps(data.get("data", {}).get("edges", [])),
                "ts": now,
            },
        )
        # Resolve tags → category names, deduplicating aliases (e.g. "agent" + "agents" → "Agents" once).
        resolved_cats: set[str] = set()
        for tag in data.get("tags", []):
            if tag not in _TAG_TO_CATEGORY:
                raise RuntimeError(
                    f"Starter JSON {json_path.name} uses unknown tag {tag!r}; "
                    f"add it to _TAG_TO_CATEGORY in this revision."
                )
            cat_name = _TAG_TO_CATEGORY[tag]
            if cat_name is None:
                continue
            resolved_cats.add(cat_name)
        for cat_name in resolved_cats:
            conn.execute(
                sa.text(
                    "INSERT INTO template_category (template_id, category_id) VALUES (:t, :c)"
                ),
                {"t": str(tid), "c": str(name_to_id[cat_name])},
            )


def _delete_shadow_starter_rows(conn):
    """Delete old starter Flow rows and their containing folder."""
    conn.execute(
        sa.text(
            "DELETE FROM flow WHERE folder_id IN "
            "(SELECT id FROM folder WHERE name = :n)"
        ),
        {"n": "Starter Projects"},  # match STARTER_FOLDER_NAME exactly
    )
    conn.execute(
        sa.text("DELETE FROM folder WHERE name = :n"),
        {"n": "Starter Projects"},
    )


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    name_to_id = _seed_categories(conn, now)
    _import_starters(conn, now, name_to_id)
    _delete_shadow_starter_rows(conn)


def downgrade() -> None:
    conn = op.get_bind()
    # Delete in reverse order to respect FK constraints.
    # Delete template_category rows for templates that match the seeded set,
    # then those templates, then the seeded categories.
    fixture_names = [
        json.loads(p.read_text())["name"]
        for p in sorted(FIXTURE_DIR.glob("*.json"))
        if not p.name.endswith(".metadata.json")
    ]
    for name in fixture_names:
        conn.execute(
            sa.text(
                "DELETE FROM template_category WHERE template_id IN "
                "(SELECT id FROM template WHERE LOWER(name) = LOWER(:name) "
                "AND scope = 'platform' AND org_id IS NULL)"
            ),
            {"name": name},
        )
        conn.execute(
            sa.text(
                "DELETE FROM template WHERE LOWER(name) = LOWER(:name) "
                "AND scope = 'platform' AND org_id IS NULL"
            ),
            {"name": name},
        )

    for seed in _CATEGORY_SEEDS:
        conn.execute(
            sa.text("DELETE FROM category WHERE LOWER(name) = LOWER(:name)"),
            {"name": seed["name"]},
        )
