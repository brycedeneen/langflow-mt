# Pay Distributions (v2)

- Domain: `payroll`
- Slug: `pay-distributions`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/payroll/pay-distributions/v2/pay-distributions-swagger_v2-merged.json
- Status: **ok**

## Operations (4)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/payroll/v1/worker.pay-distribution.change` | 118,907 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v1/worker.pay-distribution.change/meta` | 128,852 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/payroll/v2/workers/{aoid}/pay-distributions` | 81,585 | `requestedStartDate`, `distributionPurposeCode`, `distributionStatusCode`, `distributionInstructions`, `actions`, `attestationIndicator`, `itemID`, `workerID` *(+5)* | SPLIT — 13 top-level groups, 81,585B schema |
| GET | `/payroll/v2/workers/{aoid}/pay-distributions/{pay-distribution-id}` | 81,585 | `requestedStartDate`, `distributionPurposeCode`, `distributionStatusCode`, `distributionInstructions`, `actions`, `attestationIndicator`, `itemID`, `workerID` *(+5)* | SPLIT — 13 top-level groups, 81,585B schema |

## Per-operation detail

### POST `/events/payroll/v1/worker.pay-distribution.change`
- Summary: Change Pay Distribution
- Schema file: `events_payroll.worker.payDistribution.change_schema_v01_00_rev011.json` (118,907 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v1/worker.pay-distribution.change/meta`
- Summary: Change Pay Distribution Meta
- Schema file: `events_payroll.worker.payDistribution.change_meta_schema_v01_00_rev011.json` (128,852 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/payroll/v2/workers/{aoid}/pay-distributions`
- Summary: Pay Distributions
- Schema file: `payDistributions_schema_v02_00_rev009.json` (81,585 bytes)
- Top-level response groups (13): requestedStartDate, distributionPurposeCode, distributionStatusCode, distributionInstructions, actions, attestationIndicator, itemID, workerID, payrollFileNumber, payrollAgreementDescription, payrollRegionCode, payrollGroupCode, links
- Recommendation: **SPLIT — 13 top-level groups, 81,585B schema**

### GET `/payroll/v2/workers/{aoid}/pay-distributions/{pay-distribution-id}`
- Summary: Pay Distribution
- Schema file: `payDistributions_schema_v02_00_rev009.json` (81,585 bytes)
- Top-level response groups (13): requestedStartDate, distributionPurposeCode, distributionStatusCode, distributionInstructions, actions, attestationIndicator, itemID, workerID, payrollFileNumber, payrollAgreementDescription, payrollRegionCode, payrollGroupCode, links
- Recommendation: **SPLIT — 13 top-level groups, 81,585B schema**
