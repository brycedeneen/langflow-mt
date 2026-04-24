# Job Requisitions (v1)

- Domain: `staffing`
- Slug: `job-requisitions`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/staffing/job-requisitions/v1/job-requisitions-swagger_v1-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/staffing/v1/job-requisitions` | 131,145 | `clientRequisitionID`, `requisitionStatusCode`, `requisitionDescription`, `job`, `position`, `careerLevelCode`, `requisitionLocations`, `locationIndependentIndicator` *(+57)* | SPLIT — 65 top-level groups, 131,145B schema |
| GET | `/staffing/v1/job-requisitions/{job-requisition-id}` | 131,145 | `clientRequisitionID`, `requisitionStatusCode`, `requisitionDescription`, `job`, `position`, `careerLevelCode`, `requisitionLocations`, `locationIndependentIndicator` *(+57)* | SPLIT — 65 top-level groups, 131,145B schema |

## Per-operation detail

### GET `/staffing/v1/job-requisitions`
- Summary: Job Requisitions
- Schema file: `jobRequisitions_schema_v01_00_rev013.json` (131,145 bytes)
- Top-level response groups (65): clientRequisitionID, requisitionStatusCode, requisitionDescription, job, position, careerLevelCode, requisitionLocations, locationIndependentIndicator, hiringManager, recruiter, requisitionTitle, requisitionReasonCode, requisitionPurposeCode, internalIndicator, externalIndicator, evergreenIndicator, priorityIndicator, salaryVisibleIndicator, locationVisibleIndicator, supportedLocaleCodes, postDate, positionQualifications, positionTravelRequirement, screeningRequirements, organizationalUnits, standardHours, payScaleCode, payGradeCode, payGradeStepCode, payGradeRange … (+35)
- Recommendation: **SPLIT — 65 top-level groups, 131,145B schema**

### GET `/staffing/v1/job-requisitions/{job-requisition-id}`
- Summary: Job Requisition
- Schema file: `jobRequisitions_schema_v01_00_rev013.json` (131,145 bytes)
- Top-level response groups (65): clientRequisitionID, requisitionStatusCode, requisitionDescription, job, position, careerLevelCode, requisitionLocations, locationIndependentIndicator, hiringManager, recruiter, requisitionTitle, requisitionReasonCode, requisitionPurposeCode, internalIndicator, externalIndicator, evergreenIndicator, priorityIndicator, salaryVisibleIndicator, locationVisibleIndicator, supportedLocaleCodes, postDate, positionQualifications, positionTravelRequirement, screeningRequirements, organizationalUnits, standardHours, payScaleCode, payGradeCode, payGradeStepCode, payGradeRange … (+35)
- Recommendation: **SPLIT — 65 top-level groups, 131,145B schema**
