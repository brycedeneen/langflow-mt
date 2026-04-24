# ADP Workforce Now API specs — harvester output

- Tiles attempted: **1**
- Tiles harvested: **1**
- Tiles gated / errored: **0**

Re-run: `uv run python scripts/adp_spec_harvester.py`

## Per-tile summary

| Domain | Tile | Version | Operations | Largest response (B) | Total report |
|---|---|---|---|---|---|
| staffing | job-applicants | v2 | 4 | 97,691 | [report](staffing/job-applicants/v2/REPORT.md) |

## Split heuristic

- GET with schema ≥ 20,000B **and** ≥ 6 top-level groups → SPLIT into multiple extractor tools (Workers-pattern).
- GET with schema ≥ 20,000B only → split-maybe, review manually.
- Any POST / PUT / PATCH / DELETE → keep as a single tool (mutations need the full request body).
- Other GETs → single tool, payload is small enough to return verbatim.