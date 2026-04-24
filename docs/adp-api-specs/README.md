# ADP Workforce Now API specs — harvester output

- Tiles attempted: **4**
- Tiles harvested: **4**
- Tiles gated / errored: **0**

Re-run: `uv run python scripts/adp_spec_harvester.py`

## Per-tile summary

| Domain | Tile | Version | Operations | Largest response (B) | Total report |
|---|---|---|---|---|---|
| benefits | dependents | v1 | 1 | 102,052 | [report](benefits/dependents/v1/REPORT.md) |
| hr | workers-business-communication-management | v2 | 15 | 60,672 | [report](hr/workers-business-communication-management/v2/REPORT.md) |
| payroll | deduction-configurations | v3 | 1 | 80,043 | [report](payroll/deduction-configurations/v3/REPORT.md) |
| talent | associate-recognitions | v2 | 8 | 98,009 | [report](talent/associate-recognitions/v2/REPORT.md) |

## Split heuristic

- GET with schema ≥ 20,000B **and** ≥ 6 top-level groups → SPLIT into multiple extractor tools (Workers-pattern).
- GET with schema ≥ 20,000B only → split-maybe, review manually.
- Any POST / PUT / PATCH / DELETE → keep as a single tool (mutations need the full request body).
- Other GETs → single tool, payload is small enough to return verbatim.