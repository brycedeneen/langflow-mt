# Pay Statements (v1)

- Domain: `payroll`
- Slug: `pay-statements`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/payroll/pay-statements/v1/pay-statements-swagger_v1-merged.json
- Status: **ok**

## Operations (3)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/payroll/v1/workers/{aoid}/organizational-pay-statements` | 33,370 | `retirementPlanIndicator`, `meta`, `payStatements`, `confirmMessage` | split-maybe — 33,370B schema |
| GET | `/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay-statement-id}` | 82,858 | `meta`, `id`, `itemID`, `positionRef`, `payDate`, `alternateIDs`, `payPeriod`, `netPayAmount` *(+17)* | SPLIT — 25 top-level groups, 82,858B schema |
| GET | `/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay-statement-id}/images/{image-id}.{image-extension}` | 0 | — | single tool — payload is small |

## Per-operation detail

### GET `/payroll/v1/workers/{aoid}/organizational-pay-statements`
- Summary: Client Specific Pay Statements
- Schema file: `payStatements_schema_v01_00_rev012.json` (33,370 bytes)
- Top-level response groups (4): retirementPlanIndicator, meta, payStatements, confirmMessage
- Recommendation: **split-maybe — 33,370B schema**

### GET `/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay-statement-id}`
- Summary: Client Specific Pay Statement
- Schema file: `payStatement_schema_v01_00_rev021.json` (82,858 bytes)
- Top-level response groups (25): meta, id, itemID, positionRef, payDate, alternateIDs, payPeriod, netPayAmount, netPayYTDAmount, grossPayAmount, grossPayYTDAmount, totalHours, earningCategoryDetails, earnings, deductionCategoryDetails, deductions, memoCategoryDetails, memos, directDeposits, payDistributions, otherPay, employer, worker, emailPayStatementsURI, statementComments
- Recommendation: **SPLIT — 25 top-level groups, 82,858B schema**

### GET `/payroll/v1/workers/{aoid}/organizational-pay-statements/{pay-statement-id}/images/{image-id}.{image-extension}`
- Summary: Client Specific Pay Statement Image
- Schema file: `—` (0 bytes)
- Top-level response groups (0): —
- Recommendation: **single tool — payload is small**
