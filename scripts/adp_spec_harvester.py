"""Harvest ADP WFN API swagger + response schemas and emit a tool-split report.

Usage:
    uv run python scripts/adp_spec_harvester.py

Downloads every tile listed in `TILES` from api-library-marketplace.adp.com,
resolves the external JSON-schema $refs referenced by each operation's
application/json response, and writes:

    docs/adp-api-specs/<domain>/<tile>/v<N>/swagger.json
    docs/adp-api-specs/<domain>/<tile>/v<N>/schemas/<...>.json
    docs/adp-api-specs/<domain>/<tile>/v<N>/REPORT.md
    docs/adp-api-specs/README.md     (master index + split recommendations)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import httpx

BASE = "https://api-library-marketplace.adp.com/hcm-offrg-wfn"
REPO = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO / "docs" / "adp-api-specs"

# (domain, tile_slug, version)
TILES: list[tuple[str, str, str]] = [
    # HR
    ("hr", "workers", "v2"),
    ("hr", "workers-compensation-management", "v2"),
    ("hr", "workers-personal-communication-management", "v2"),
    ("hr", "workers-work-deployment-management", "v2"),
    ("hr", "workers-identification-management", "v2"),
    ("hr", "workers-work-assignment-management", "v2"),
    ("hr", "workers-demographic-data-management", "v2"),
    ("hr", "workers-biological-data-management", "v2"),
    ("hr", "workers-business-communication-management", "v2"),
    ("hr", "workers-lifecycle-management", "v2"),
    ("hr", "worker-leaves", "v2"),
    ("hr", "hr-worker-profiles", "v1"),
    ("hr", "hr-work-assignment-management", "v3"),
    ("hr", "worker-associate-profiles", "v2"),
    ("hr", "corporate-directory", "v1"),
    # HCM
    ("hcm", "applicant-onboarding", "v2"),
    ("hcm", "wfn-codelists", "v3"),  # 403 gated — logged and skipped
    # Payroll
    ("payroll", "worker-payroll-instructions", "v1"),
    ("payroll", "pay-data-input", "v1"),
    ("payroll", "us-tax-profiles", "v1"),
    ("payroll", "us-tax-profiles", "v2"),
    ("payroll", "deduction-configurations", "v3"),
    ("payroll", "pay-distributions", "v2"),
    ("payroll", "pay-statements", "v1"),
    ("payroll", "pay-statements", "v2"),  # 403 gated
    # Time
    ("time", "time-cards", "v2"),
    ("time", "team-time-cards", "v2"),
    ("time", "work-schedules", "v1"),
    ("time", "work-schedule-entry-uploads", "v2"),
    ("time", "data-collection-entries", "v1"),
    ("time", "time-off-balances", "v3"),
    ("time", "time-off-requests", "v2"),
    ("time", "time-off-requests", "v3"),
    # Talent
    ("talent", "associate-languages", "v2"),
    ("talent", "associate-competencies", "v2"),
    ("talent", "associate-certifications", "v2"),
    ("talent", "associate-educational-degrees", "v2"),
    ("talent", "associate-memberships", "v2"),
    ("talent", "associate-licenses", "v2"),
    ("talent", "associate-recognitions", "v2"),
    # Benefits
    ("benefits", "beneficiaries", "v1"),
    ("benefits", "dependents", "v1"),
    ("benefits", "external-plans", "v1"),
    ("benefits", "spending-account-plans", "v1"),
    ("benefits", "spending-account-enrollments", "v1"),
    # Staffing
    ("staffing", "job-requisitions", "v1"),
    ("staffing", "job-applications", "v2"),
    ("staffing", "job-applicants", "v2"),
]

SPLIT_HINT_THRESHOLD_BYTES = 20_000  # schemas bigger than this → recommend splitting
SPLIT_HINT_TOP_LEVEL_PROPS = 6        # or more top-level property groups → split


@dataclass
class Operation:
    method: str
    path: str
    summary: str
    schema_ref: str | None
    schema_bytes: int = 0
    top_level_props: list[str] = field(default_factory=list)

    @property
    def is_meta_endpoint(self) -> bool:
        return self.path.endswith("/meta")

    @property
    def split_recommendation(self) -> str:
        if self.is_meta_endpoint:
            return "single tool (meta discovery — rarely agent-facing)"
        if self.method != "GET":
            return "keep whole (mutation requires full body)"
        if self.schema_bytes >= SPLIT_HINT_THRESHOLD_BYTES and len(self.top_level_props) >= SPLIT_HINT_TOP_LEVEL_PROPS:
            return f"SPLIT — {len(self.top_level_props)} top-level groups, {self.schema_bytes:,}B schema"
        if self.schema_bytes >= SPLIT_HINT_THRESHOLD_BYTES:
            return f"split-maybe — {self.schema_bytes:,}B schema"
        return "single tool — payload is small"


@dataclass
class TileResult:
    domain: str
    name: str
    version: str
    status: str  # "ok" | f"error:{code}"
    operations: list[Operation] = field(default_factory=list)
    error: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.domain}/{self.name}/{self.version}"

    @property
    def display(self) -> str:
        return self.name.replace("-", " ").title()


def swagger_url(domain: str, tile: str, version: str) -> str:
    return f"{BASE}/{domain}/{tile}/{version}/{tile}-swagger_{version}-merged.json"


def tile_dir(domain: str, tile: str, version: str) -> Path:
    return OUT_ROOT / domain / tile / version


ADP_WRAPPER_KEYS = {"meta", "confirmMessage"}


def top_level_properties(schema: dict) -> list[str]:
    """Return the meaningful top-level property groups for split planning.

    ADP responses follow a standard wrapper: `{<entity>: [...], meta: {...},
    confirmMessage: {...}}`. We want the fields of `<entity>` — those are the
    split candidates (person, workAssignments, …), not the wrapper keys.
    """
    props = schema.get("properties") or {}
    # Single-key wrapper
    if len(props) == 1:
        only = next(iter(props.values()))
        if only.get("type") == "array" and only.get("items", {}).get("properties"):
            return list(only["items"]["properties"].keys())
        if only.get("properties"):
            return list(only["properties"].keys())
    # Standard ADP wrapper: pick non-meta key as the entity
    entity_keys = [k for k in props if k not in ADP_WRAPPER_KEYS]
    if len(entity_keys) == 1:
        entity = props[entity_keys[0]]
        if entity.get("type") == "array" and entity.get("items", {}).get("properties"):
            return list(entity["items"]["properties"].keys())
        if entity.get("properties"):
            return list(entity["properties"].keys())
    return list(props.keys())


def harvest_tile(client: httpx.Client, domain: str, tile: str, version: str) -> TileResult:
    result = TileResult(domain=domain, name=tile, version=version, status="ok")
    url = swagger_url(domain, tile, version)
    try:
        resp = client.get(url, timeout=30.0)
    except httpx.RequestError as e:
        result.status = "error:network"
        result.error = str(e)
        return result

    if resp.status_code != 200:
        result.status = f"error:{resp.status_code}"
        return result

    out_dir = tile_dir(domain, tile, version)
    out_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir = out_dir / "schemas"
    schemas_dir.mkdir(exist_ok=True)

    swagger = resp.json()
    (out_dir / "swagger.json").write_text(json.dumps(swagger, indent=2))

    for path, path_item in sorted(swagger.get("paths", {}).items()):
        for method, op in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            summary = op.get("summary", "").strip()
            # Look at first 2xx response
            responses = op.get("responses", {})
            success = responses.get("200") or responses.get("201") or next(iter(responses.values()), {})
            content = success.get("content", {}).get("application/json", {})
            schema = content.get("schema", {})
            ref = schema.get("$ref")

            schema_bytes = 0
            top_props: list[str] = []
            if ref and ref.startswith("./"):
                schema_url = urljoin(url, ref)
                schema_name = Path(ref).name
                dest = schemas_dir / schema_name
                if not dest.exists():
                    sresp = client.get(schema_url, timeout=30.0)
                    if sresp.status_code == 200:
                        dest.write_bytes(sresp.content)
                if dest.exists():
                    try:
                        schema_doc = json.loads(dest.read_text())
                        schema_bytes = dest.stat().st_size
                        top_props = top_level_properties(schema_doc)
                    except json.JSONDecodeError:
                        pass

            result.operations.append(Operation(
                method=method.upper(),
                path=path,
                summary=summary,
                schema_ref=ref,
                schema_bytes=schema_bytes,
                top_level_props=top_props,
            ))
    return result


def render_tile_report(result: TileResult) -> str:
    lines = [
        f"# {result.display} ({result.version})",
        "",
        f"- Domain: `{result.domain}`",
        f"- Slug: `{result.name}`",
        f"- Swagger: {swagger_url(result.domain, result.name, result.version)}",
        f"- Status: **{result.status}**",
        "",
    ]
    if result.status != "ok":
        if result.status == "error:403":
            lines += ["> **Gated** — auth cookie required to fetch this spec.", ""]
        return "\n".join(lines)

    lines += [f"## Operations ({len(result.operations)})", ""]
    lines += ["| Method | Path | Schema (B) | Top-level groups | Split recommendation |"]
    lines += ["|---|---|---|---|---|"]
    for op in result.operations:
        groups = ", ".join(f"`{p}`" for p in op.top_level_props[:8])
        if len(op.top_level_props) > 8:
            groups += f" *(+{len(op.top_level_props)-8})*"
        lines += [f"| {op.method} | `{op.path}` | {op.schema_bytes:,} | {groups or '—'} | {op.split_recommendation} |"]
    lines += ["", "## Per-operation detail", ""]
    for op in result.operations:
        shown = op.top_level_props[:30]
        more = len(op.top_level_props) - len(shown)
        shown_str = ", ".join(shown) + (f" … (+{more})" if more > 0 else "")
        lines += [
            f"### {op.method} `{op.path}`",
            f"- Summary: {op.summary or '—'}",
            f"- Schema file: `{Path(op.schema_ref).name if op.schema_ref else '—'}` ({op.schema_bytes:,} bytes)",
            f"- Top-level response groups ({len(op.top_level_props)}): {shown_str or '—'}",
            f"- Recommendation: **{op.split_recommendation}**",
            "",
        ]
    return "\n".join(lines)


def render_master_index(results: list[TileResult]) -> str:
    ok = [r for r in results if r.status == "ok"]
    errs = [r for r in results if r.status != "ok"]
    lines = [
        "# ADP Workforce Now API specs — harvester output",
        "",
        f"- Tiles attempted: **{len(results)}**",
        f"- Tiles harvested: **{len(ok)}**",
        f"- Tiles gated / errored: **{len(errs)}**",
        "",
        "Re-run: `uv run python scripts/adp_spec_harvester.py`",
        "",
        "## Per-tile summary",
        "",
        "| Domain | Tile | Version | Operations | Largest response (B) | Total report |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(ok, key=lambda x: (x.domain, x.name, x.version)):
        largest = max((op.schema_bytes for op in r.operations), default=0)
        link = f"[report]({r.domain}/{r.name}/{r.version}/REPORT.md)"
        lines.append(f"| {r.domain} | {r.name} | {r.version} | {len(r.operations)} | {largest:,} | {link} |")
    if errs:
        lines += ["", "## Gated / errored", "", "| Tile | Status |", "|---|---|"]
        for r in errs:
            lines.append(f"| `{r.slug}` | {r.status} |")
    lines += ["", "## Split heuristic", ""]
    lines += [
        f"- GET with schema ≥ {SPLIT_HINT_THRESHOLD_BYTES:,}B **and** ≥ {SPLIT_HINT_TOP_LEVEL_PROPS} top-level groups → SPLIT into multiple extractor tools (Workers-pattern).",
        f"- GET with schema ≥ {SPLIT_HINT_THRESHOLD_BYTES:,}B only → split-maybe, review manually.",
        "- Any POST / PUT / PATCH / DELETE → keep as a single tool (mutations need the full request body).",
        "- Other GETs → single tool, payload is small enough to return verbatim.",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results: list[TileResult] = []
    with httpx.Client() as client:
        for i, (domain, tile, version) in enumerate(TILES, 1):
            print(f"[{i}/{len(TILES)}] {domain}/{tile}/{version} ...", end=" ", flush=True)
            r = harvest_tile(client, domain, tile, version)
            results.append(r)
            print(r.status if r.status != "ok" else f"ok ({len(r.operations)} ops)")
            if r.status == "ok":
                (tile_dir(domain, tile, version) / "REPORT.md").write_text(render_tile_report(r))
    (OUT_ROOT / "README.md").write_text(render_master_index(results))
    print(f"\nWrote {OUT_ROOT}/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
