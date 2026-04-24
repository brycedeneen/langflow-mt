# ADP Workforce Now API specs — harvester output

- Tiles attempted: **43**
- Tiles harvested: **38**
- Tiles gated / errored: **5**

Re-run: `uv run python scripts/adp_spec_harvester.py`

## Per-tile summary

| Domain | Tile | Version | Operations | Largest response (B) | Total report |
|---|---|---|---|---|---|
| benefits | beneficiaries | v1 | 1 | 119,841 | [report](benefits/beneficiaries/v1/REPORT.md) |
| benefits | external-plans | v1 | 2 | 0 | [report](benefits/external-plans/v1/REPORT.md) |
| hcm | applicant-onboarding | v2 | 2 | 670,405 | [report](hcm/applicant-onboarding/v2/REPORT.md) |
| hr | corporate-directory | v1 | 1 | 0 | [report](hr/corporate-directory/v1/REPORT.md) |
| hr | hr-work-assignment-management | v3 | 2 | 107,270 | [report](hr/hr-work-assignment-management/v3/REPORT.md) |
| hr | hr-worker-profiles | v1 | 14 | 113,236 | [report](hr/hr-worker-profiles/v1/REPORT.md) |
| hr | worker-associate-profiles | v2 | 2 | 56,862 | [report](hr/worker-associate-profiles/v2/REPORT.md) |
| hr | worker-leaves | v2 | 9 | 79,820 | [report](hr/worker-leaves/v2/REPORT.md) |
| hr | workers | v2 | 8 | 482,083 | [report](hr/workers/v2/REPORT.md) |
| hr | workers-biological-data-management | v2 | 5 | 59,682 | [report](hr/workers-biological-data-management/v2/REPORT.md) |
| hr | workers-compensation-management | v2 | 8 | 101,569 | [report](hr/workers-compensation-management/v2/REPORT.md) |
| hr | workers-demographic-data-management | v2 | 12 | 75,899 | [report](hr/workers-demographic-data-management/v2/REPORT.md) |
| hr | workers-identification-management | v2 | 2 | 59,368 | [report](hr/workers-identification-management/v2/REPORT.md) |
| hr | workers-lifecycle-management | v2 | 2 | 511,282 | [report](hr/workers-lifecycle-management/v2/REPORT.md) |
| hr | workers-personal-communication-management | v2 | 22 | 73,271 | [report](hr/workers-personal-communication-management/v2/REPORT.md) |
| hr | workers-work-assignment-management | v2 | 7 | 280,994 | [report](hr/workers-work-assignment-management/v2/REPORT.md) |
| hr | workers-work-deployment-management | v2 | 2 | 54,566 | [report](hr/workers-work-deployment-management/v2/REPORT.md) |
| payroll | pay-data-input | v1 | 2 | 201,459 | [report](payroll/pay-data-input/v1/REPORT.md) |
| payroll | pay-distributions | v2 | 4 | 128,852 | [report](payroll/pay-distributions/v2/REPORT.md) |
| payroll | pay-statements | v1 | 3 | 82,858 | [report](payroll/pay-statements/v1/REPORT.md) |
| payroll | us-tax-profiles | v1 | 11 | 88,711 | [report](payroll/us-tax-profiles/v1/REPORT.md) |
| payroll | us-tax-profiles | v2 | 4 | 85,542 | [report](payroll/us-tax-profiles/v2/REPORT.md) |
| payroll | worker-payroll-instructions | v1 | 8 | 131,833 | [report](payroll/worker-payroll-instructions/v1/REPORT.md) |
| staffing | job-applications | v2 | 2 | 252,130 | [report](staffing/job-applications/v2/REPORT.md) |
| staffing | job-requisitions | v1 | 2 | 131,145 | [report](staffing/job-requisitions/v1/REPORT.md) |
| talent | associate-certifications | v2 | 9 | 99,778 | [report](talent/associate-certifications/v2/REPORT.md) |
| talent | associate-competencies | v2 | 9 | 103,953 | [report](talent/associate-competencies/v2/REPORT.md) |
| talent | associate-educational-degrees | v2 | 9 | 142,340 | [report](talent/associate-educational-degrees/v2/REPORT.md) |
| talent | associate-languages | v2 | 10 | 84,039 | [report](talent/associate-languages/v2/REPORT.md) |
| talent | associate-licenses | v2 | 10 | 141,750 | [report](talent/associate-licenses/v2/REPORT.md) |
| talent | associate-memberships | v2 | 22 | 129,504 | [report](talent/associate-memberships/v2/REPORT.md) |
| time | data-collection-entries | v1 | 2 | 120,207 | [report](time/data-collection-entries/v1/REPORT.md) |
| time | team-time-cards | v2 | 1 | 114,152 | [report](time/team-time-cards/v2/REPORT.md) |
| time | time-cards | v2 | 1 | 111,874 | [report](time/time-cards/v2/REPORT.md) |
| time | time-off-balances | v3 | 2 | 64,022 | [report](time/time-off-balances/v3/REPORT.md) |
| time | time-off-requests | v2 | 5 | 156,418 | [report](time/time-off-requests/v2/REPORT.md) |
| time | time-off-requests | v3 | 3 | 65,014 | [report](time/time-off-requests/v3/REPORT.md) |
| time | work-schedules | v1 | 19 | 94,976 | [report](time/work-schedules/v1/REPORT.md) |

## Gated / errored

| Tile | Status |
|---|---|
| `hcm/wfn-codelists/v3` | error:403 |
| `payroll/pay-statements/v2` | error:403 |
| `time/work-schedule-entry-uploads/v2` | error:403 |
| `benefits/spending-account-plans/v1` | error:403 |
| `benefits/spending-account-enrollments/v1` | error:403 |

## Split heuristic

- GET with schema ≥ 20,000B **and** ≥ 6 top-level groups → SPLIT into multiple extractor tools (Workers-pattern).
- GET with schema ≥ 20,000B only → split-maybe, review manually.
- Any POST / PUT / PATCH / DELETE → keep as a single tool (mutations need the full request body).
- Other GETs → single tool, payload is small enough to return verbatim.