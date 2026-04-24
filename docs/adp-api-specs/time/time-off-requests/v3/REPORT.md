# Time Off Requests (v3)

- Domain: `time`
- Slug: `time-off-requests`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/time-off-requests/v3/time-off-requests-swagger_v3-merged.json
- Status: **ok**

## Operations (3)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/time/v3/workers/{aoid}/team-time-off-request-summaries` | 36,099 | `requestorName`, `associateOID`, `workerID`, `workAssignmentID`, `workAssignmentTitle`, `positionID`, `positionTitle`, `requestStatusTotals` *(+1)* | SPLIT — 9 top-level groups, 36,099B schema |
| GET | `/time/v3/workers/{aoid}/time-off-request-summaries` | 36,099 | `requestorName`, `associateOID`, `workerID`, `workAssignmentID`, `workAssignmentTitle`, `positionID`, `positionTitle`, `requestStatusTotals` *(+1)* | SPLIT — 9 top-level groups, 36,099B schema |
| GET | `/time/v3/workers/{aoid}/time-off-request-summaries/meta` | 65,014 | `queryCriteria`, `/timeOffRequestSummaries`, `/timeOffRequestSummaries/requestorName`, `/timeOffRequestSummaries/requestorName/givenName`, `/timeOffRequestSummaries/requestorName/middleName`, `/timeOffRequestSummaries/requestorName/familyName1`, `/timeOffRequestSummaries/requestorName/familyName2`, `/timeOffRequestSummaries/requestorName/formattedName` *(+44)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### GET `/time/v3/workers/{aoid}/team-time-off-request-summaries`
- Summary: Team Time Off Request Summaries
- Schema file: `timeOffRequestSummaries_schema_v03_00_rev001.json` (36,099 bytes)
- Top-level response groups (9): requestorName, associateOID, workerID, workAssignmentID, workAssignmentTitle, positionID, positionTitle, requestStatusTotals, links
- Recommendation: **SPLIT — 9 top-level groups, 36,099B schema**

### GET `/time/v3/workers/{aoid}/time-off-request-summaries`
- Summary: Worker Time Off Request Summaries
- Schema file: `timeOffRequestSummaries_schema_v03_00_rev001.json` (36,099 bytes)
- Top-level response groups (9): requestorName, associateOID, workerID, workAssignmentID, workAssignmentTitle, positionID, positionTitle, requestStatusTotals, links
- Recommendation: **SPLIT — 9 top-level groups, 36,099B schema**

### GET `/time/v3/workers/{aoid}/time-off-request-summaries/meta`
- Summary: Worker Time Off Request Summary Meta
- Schema file: `timeOffRequestSummaries_meta_schema_v03_00_rev001.json` (65,014 bytes)
- Top-level response groups (52): queryCriteria, /timeOffRequestSummaries, /timeOffRequestSummaries/requestorName, /timeOffRequestSummaries/requestorName/givenName, /timeOffRequestSummaries/requestorName/middleName, /timeOffRequestSummaries/requestorName/familyName1, /timeOffRequestSummaries/requestorName/familyName2, /timeOffRequestSummaries/requestorName/formattedName, /timeOffRequestSummaries/associateOID, /timeOffRequestSummaries/workerID, /timeOffRequestSummaries/workerID/idValue, /timeOffRequestSummaries/workerID/schemeCode, /timeOffRequestSummaries/workerID/schemeCode/codeValue, /timeOffRequestSummaries/workerID/schemeCode/shortName, /timeOffRequestSummaries/workerID/schemeCode/longName, /timeOffRequestSummaries/workAssignmentID, /timeOffRequestSummaries/workAssignmentTitle, /timeOffRequestSummaries/positionID, /timeOffRequestSummaries/positionTitle, /timeOffRequestSummaries/requestStatusTotals, /timeOffRequestSummaries/requestStatusTotals/requestStatusCode, /timeOffRequestSummaries/requestStatusTotals/requestStatusCode/codeValue, /timeOffRequestSummaries/requestStatusTotals/requestStatusCode/shortName, /timeOffRequestSummaries/requestStatusTotals/requestStatusCode/longName, /timeOffRequestSummaries/requestStatusTotals/requestStatusCode/effectiveDate, /timeOffRequestSummaries/requestStatusTotals/totalRequestQuantity, /timeOffRequestSummaries/requestStatusTotals/totalQuantity, /timeOffRequestSummaries/requestStatusTotals/totalQuantity/quantityValue, /timeOffRequestSummaries/requestStatusTotals/totalQuantity/unitTimeCode, /timeOffRequestSummaries/requestStatusTotals/totalQuantity/unitTimeCode/codeValue … (+22)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
