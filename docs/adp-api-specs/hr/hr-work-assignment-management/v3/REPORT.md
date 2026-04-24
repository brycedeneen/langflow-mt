# Hr Work Assignment Management (v3)

- Domain: `hr`
- Slug: `hr-work-assignment-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/hr-work-assignment-management/v3/hr-work-assignment-management-swagger_v3-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/hr/v3/workers/{aoid}/work-assignments` | 0 | — | keep whole (mutation requires full body) |
| GET | `/hr/v3/workers/{aoid}/work-assignments/meta` | 107,270 | `queryCriteria`, `/workAssignment`, `/workAssignment/workAssignmentID`, `/workAssignment/alternateIDs`, `/workAssignment/alternateIDs/id`, `/workAssignment/alternateIDs/schemeCode`, `/workAssignment/alternateIDs/schemeCode/code`, `/workAssignment/alternateIDs/schemeCode/name` *(+327)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/hr/v3/workers/{aoid}/work-assignments`
- Summary: Create worker's work assignment
- Schema file: `confirm-message-schema_v03.json` (0 bytes)
- Top-level response groups (0): —
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/v3/workers/{aoid}/work-assignments/meta`
- Summary: Returns a meta for Work assignment, Pass method parameter to reterive appropriate response
- Schema file: `work-assignment-create-request-meta-schema_v03.json` (107,270 bytes)
- Top-level response groups (335): queryCriteria, /workAssignment, /workAssignment/workAssignmentID, /workAssignment/alternateIDs, /workAssignment/alternateIDs/id, /workAssignment/alternateIDs/schemeCode, /workAssignment/alternateIDs/schemeCode/code, /workAssignment/alternateIDs/schemeCode/name, /workAssignment/alternateIDs/schemeAgencyCode, /workAssignment/alternateIDs/schemeAgencyCode/code, /workAssignment/alternateIDs/schemeAgencyCode/name, /workAssignment/workAssignmentStatus, /workAssignment/workAssignmentStatus/statusCode, /workAssignment/workAssignmentStatus/statusCode/code, /workAssignment/workAssignmentStatus/statusCode/name, /workAssignment/workAssignmentStatus/reasonCode, /workAssignment/workAssignmentStatus/reasonCode/code, /workAssignment/workAssignmentStatus/reasonCode/name, /workAssignment/workAssignmentStatus/effectiveDateTime, /workAssignment/workAgreementRef, /workAssignment/workAgreementRef/countryCode, /workAssignment/workAgreementRef/workAgreementID, /workAssignment/workAgreementRef/legalEntityID, /workAssignment/workAgreementRef/legalEntityID/id, /workAssignment/workAgreementRef/legalEntityID/schemeCode, /workAssignment/workAgreementRef/legalEntityID/schemeCode/code, /workAssignment/workAgreementRef/legalEntityID/schemeCode/name, /workAssignment/workAgreementRef/legalEntityID/schemeAgencyCode, /workAssignment/workAgreementRef/legalEntityID/schemeAgencyCode/code, /workAssignment/workAgreementRef/legalEntityID/schemeAgencyCode/name … (+305)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
