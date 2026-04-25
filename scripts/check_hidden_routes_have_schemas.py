#!/usr/bin/env python3
"""Fail CI if a backend router adds an `include_in_schema=False` route or
router-level prefix without a corresponding hand-written schema in
`src/frontend/src/schemas/app/internal/`.

This catches schema drift at PR time — we can't catch *response-shape* drift
on already-represented routes (that's left to ValidationError telemetry during
the permissive bake), but we can ensure every hidden route has a schema id
registered by name.

Usage: python3 scripts/check_hidden_routes_have_schemas.py
Exit codes: 0 = OK, 1 = missing schemas, 2 = bad arguments
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "src" / "backend" / "base" / "langflow" / "api"
INTERNAL_DIR = REPO / "src" / "frontend" / "src" / "schemas" / "app" / "internal"

# Match @router.<method>("/path", ..., include_in_schema=False, ...) — multi-line ok.
ROUTE_RE = re.compile(
    r"@router\.(?P<method>get|post|patch|put|delete)\([^)]*?include_in_schema\s*=\s*False",
    re.DOTALL,
)
# Match router-level prefix: APIRouter(prefix="/foo", ..., include_in_schema=False, ...)
ROUTER_PREFIX_RE = re.compile(
    r'APIRouter\([^)]*?prefix\s*=\s*"(?P<prefix>[^"]+)"[^)]*?include_in_schema\s*=\s*False',
    re.DOTALL,
)
# Also match the reverse arg order: include_in_schema=False, ..., prefix="..."
ROUTER_PREFIX_RE_REV = re.compile(
    r'APIRouter\([^)]*?include_in_schema\s*=\s*False[^)]*?prefix\s*=\s*"(?P<prefix>[^"]+)"',
    re.DOTALL,
)
# Routes with an explicit deprecated=True aren't required to have schemas
# (the migration policy in the plan exempts deprecated paths).
DEPRECATED_RE = re.compile(r"deprecated\s*=\s*True")

# Schema ids look like `registerSchema("api.<router>.<op>", ...)` — we need the <router>.
ID_RE = re.compile(r'registerSchema\(\s*"api\.(?P<router>[A-Za-z0-9_]+)\.[^"]+"')


def main() -> int:
    if not INTERNAL_DIR.exists():
        print(f"::error::Missing {INTERNAL_DIR}", file=sys.stderr)
        return 1

    # Gather hidden-router names (the prefix's first segment, lowercased) from backend.
    hidden_routers: dict[str, list[Path]] = {}  # router-name -> list of files
    for py in BACKEND.rglob("*.py"):
        text = py.read_text()
        # Whole-router-hidden:
        for m in ROUTER_PREFIX_RE.finditer(text):
            router = router_name_from_prefix(m.group("prefix"))
            hidden_routers.setdefault(router, []).append(py)
        for m in ROUTER_PREFIX_RE_REV.finditer(text):
            router = router_name_from_prefix(m.group("prefix"))
            hidden_routers.setdefault(router, []).append(py)
        # Route-level hidden:
        for m in ROUTE_RE.finditer(text):
            # Skip deprecated routes — same matched block.
            if DEPRECATED_RE.search(m.group(0)):
                continue
            router = py.stem  # e.g. "api_key" for api_key.py
            hidden_routers.setdefault(router, []).append(py)

    # Gather registered router prefixes from the schemas/app/internal/*.ts files.
    registered: set[str] = set()
    for f in INTERNAL_DIR.glob("*.ts"):
        for m in ID_RE.finditer(f.read_text()):
            registered.add(m.group("router"))

    # Aliases between backend router names and schema id prefixes. Add new entries
    # here when a hand-written schema deliberately uses a friendlier name than the
    # backend file/prefix it covers.
    ALIASES = {
        "variable": "variables",   # variable.py exposes /variables/*
        "login": "auth",            # login.py exposes /auth/{login,refresh,session,logout}
        "voice_mode": "voice",      # already canonicalized by router_name_from_prefix
    }

    missing: list[str] = []
    for r in sorted(hidden_routers):
        if r in registered:
            continue
        if ALIASES.get(r) in registered:
            continue
        missing.append(r)

    if missing:
        print("::error::Hidden router prefixes without matching schemas in schemas/app/internal/:", file=sys.stderr)
        for r in missing:
            files = sorted(set(p.relative_to(REPO) for p in hidden_routers[r]))
            print(f"  api.{r}.*  (from {', '.join(map(str, files))})", file=sys.stderr)
        print(
            f"\nFix: add a `registerSchema(\"api.{missing[0]}.<op>\", ...)` line "
            f"to a new or existing file under {INTERNAL_DIR.relative_to(REPO)}/.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(hidden_routers)} hidden router(s) all have matching schemas.")
    print(f"  Registered prefixes: {sorted(registered)}")
    print(f"  Backend hidden routers: {sorted(hidden_routers)}")
    return 0


def router_name_from_prefix(prefix: str) -> str:
    """Convert a router prefix (`/api_key`, `/voice`, `/api/v2/registration`) to the
    canonical schema-id router name used in `registerSchema("api.<router>.<op>", ...)`.
    """
    # Strip leading /api[/vN]/ if present, take the first remaining segment.
    parts = [p for p in prefix.strip("/").split("/") if p and p not in {"api", "v1", "v2"}]
    return parts[0].lower() if parts else "untagged"


if __name__ == "__main__":
    raise SystemExit(main())
