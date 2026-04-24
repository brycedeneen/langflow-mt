# Hr Worker Profiles (v1)

- Domain: `hr`
- Slug: `hr-worker-profiles`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/hr-worker-profiles/v1/hr-worker-profiles-swagger_v1-merged.json
- Status: **ok**

## Operations (14)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations` | 47,676 | `associateOID`, `workerID`, `workAssignmentID`, `additionalRemunerations`, `_links`, `_meta`, `_confirmMessage` | keep whole (mutation requires full body) |
| GET | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations` | 47,676 | `associateOID`, `workerID`, `workAssignmentID`, `additionalRemunerations`, `_links`, `_meta`, `_confirmMessage` | SPLIT — 7 top-level groups, 47,676B schema |
| PUT | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations` | 47,676 | `associateOID`, `workerID`, `workAssignmentID`, `additionalRemunerations`, `_links`, `_meta`, `_confirmMessage` | keep whole (mutation requires full body) |
| GET | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations/meta` | 76,109 | `queryCriteria`, `/associateOID`, `/workerID`, `/workerID/id`, `/workerID/scheme`, `/workerID/scheme/code`, `/workerID/scheme/name`, `/workerID/schemeAgency` *(+72)* | single tool (meta discovery — rarely agent-facing) |
| PUT | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/base-remuneration` | 55,460 | `associateOID`, `workerID`, `workAssignmentID`, `baseRemuneration`, `payCycleCode`, `standardHours`, `wageLawCoverage`, `premiumRateFactor` *(+4)* | keep whole (mutation requires full body) |
| GET | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/base-remuneration/meta` | 79,408 | `queryCriteria`, `/associateOID`, `/workerID`, `/workerID/id`, `/workerID/scheme`, `/workerID/scheme/code`, `/workerID/scheme/name`, `/workerID/schemeAgency` *(+112)* | single tool (meta discovery — rarely agent-facing) |
| POST | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/corporate-groups` | 77,531 | `groupStatus`, `homeWorkLocation`, `homeOrganizationalUnits`, `workerGroups`, `laborUnion`, `bargainingUnit` | keep whole (mutation requires full body) |
| GET | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/corporate-groups/meta` | 113,236 | `queryCriteria`, `/corporateGroups`, `/corporateGroups/groupStatus`, `/corporateGroups/groupStatus/statusCode`, `/corporateGroups/groupStatus/statusCode/code`, `/corporateGroups/groupStatus/statusCode/name`, `/corporateGroups/groupStatus/reasonCode`, `/corporateGroups/groupStatus/reasonCode/code` *(+346)* | single tool (meta discovery — rarely agent-facing) |
| PUT | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/primary-assignment` | 33,727 | `effectiveDate`, `workAssignments`, `_links`, `_meta`, `_confirmMessage` | keep whole (mutation requires full body) |
| POST | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits` | 36,898 | `associateOID`, `workerID`, `workAssignmentID`, `reportableBenefits`, `_links`, `_meta`, `_confirmMessage` | keep whole (mutation requires full body) |
| GET | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits` | 36,898 | `associateOID`, `workerID`, `workAssignmentID`, `reportableBenefits`, `_links`, `_meta`, `_confirmMessage` | SPLIT — 7 top-level groups, 36,898B schema |
| PUT | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits` | 36,898 | `associateOID`, `workerID`, `workAssignmentID`, `reportableBenefits`, `_links`, `_meta`, `_confirmMessage` | keep whole (mutation requires full body) |
| GET | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits/meta` | 70,997 | `queryCriteria`, `/associateOID`, `/workerID`, `/workerID/id`, `/workerID/scheme`, `/workerID/scheme/code`, `/workerID/scheme/name`, `/workerID/schemeAgency` *(+30)* | single tool (meta discovery — rarely agent-facing) |
| PUT | `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/worker-dates` | 0 | — | keep whole (mutation requires full body) |

## Per-operation detail

### POST `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations`
- Summary: Create worker's additional remunerations
- Schema file: `worker-compensation-variable-schema_v01.json` (47,676 bytes)
- Top-level response groups (7): associateOID, workerID, workAssignmentID, additionalRemunerations, _links, _meta, _confirmMessage
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations`
- Summary: Read worker's additional remunerations
- Schema file: `worker-compensation-variable-schema_v01.json` (47,676 bytes)
- Top-level response groups (7): associateOID, workerID, workAssignmentID, additionalRemunerations, _links, _meta, _confirmMessage
- Recommendation: **SPLIT — 7 top-level groups, 47,676B schema**

### PUT `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations`
- Summary: Update worker's additional remunerations
- Schema file: `worker-compensation-variable-schema_v01.json` (47,676 bytes)
- Top-level response groups (7): associateOID, workerID, workAssignmentID, additionalRemunerations, _links, _meta, _confirmMessage
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/additional-remunerations/meta`
- Summary: Read additional remuneration add/update metadata
- Schema file: `worker-compensation-variable-meta-schema_v01.json` (76,109 bytes)
- Top-level response groups (80): queryCriteria, /associateOID, /workerID, /workerID/id, /workerID/scheme, /workerID/scheme/code, /workerID/scheme/name, /workerID/schemeAgency, /workAssignmentID, /additionalRemunerations, /additionalRemunerations/remunerationID, /additionalRemunerations/remunerationTypeCode, /additionalRemunerations/remunerationTypeCode/code, /additionalRemunerations/remunerationTypeCode/name, /additionalRemunerations/remunerationMinRate, /additionalRemunerations/remunerationMinRate/rate, /additionalRemunerations/remunerationMinRate/currencyCode, /additionalRemunerations/remunerationMinRate/unitCode, /additionalRemunerations/remunerationMinRate/unitCode/code, /additionalRemunerations/remunerationMinRate/unitCode/name, /additionalRemunerations/remunerationMinRate/baseUnitCode, /additionalRemunerations/remunerationMinRate/baseUnitCode/code, /additionalRemunerations/remunerationMinRate/baseUnitCode/name, /additionalRemunerations/remunerationMinRate/baseMultiplierValue, /additionalRemunerations/remunerationMaxRate, /additionalRemunerations/remunerationMaxRate/rate, /additionalRemunerations/remunerationMaxRate/currencyCode, /additionalRemunerations/remunerationMaxRate/unitCode, /additionalRemunerations/remunerationMaxRate/unitCode/code, /additionalRemunerations/remunerationMaxRate/unitCode/name … (+50)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### PUT `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/base-remuneration`
- Summary: Update base remuneration
- Schema file: `worker-compensation-regular-schema_v01.json` (55,460 bytes)
- Top-level response groups (12): associateOID, workerID, workAssignmentID, baseRemuneration, payCycleCode, standardHours, wageLawCoverage, premiumRateFactor, tippedWorkerIndicator, _links, _meta, _confirmMessage
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/base-remuneration/meta`
- Summary: Read base remuneration update metadata
- Schema file: `worker-compensation-regular-meta-schema_v01.json` (79,408 bytes)
- Top-level response groups (120): queryCriteria, /associateOID, /workerID, /workerID/id, /workerID/scheme, /workerID/scheme/code, /workerID/scheme/name, /workerID/schemeAgency, /workAssignmentID, /baseRemuneration, /baseRemuneration/recordingBasisCode, /baseRemuneration/recordingBasisCode/code, /baseRemuneration/recordingBasisCode/name, /baseRemuneration/hourlyRateAmount, /baseRemuneration/hourlyRateAmount/amount, /baseRemuneration/hourlyRateAmount/currencyCode, /baseRemuneration/dailyRateAmount, /baseRemuneration/dailyRateAmount/amount, /baseRemuneration/dailyRateAmount/currencyCode, /baseRemuneration/weeklyRateAmount, /baseRemuneration/weeklyRateAmount/amount, /baseRemuneration/weeklyRateAmount/currencyCode, /baseRemuneration/biweeklyRateAmount, /baseRemuneration/biweeklyRateAmount/amount, /baseRemuneration/biweeklyRateAmount/currencyCode, /baseRemuneration/semiMonthlyRateAmount, /baseRemuneration/semiMonthlyRateAmount/amount, /baseRemuneration/semiMonthlyRateAmount/currencyCode, /baseRemuneration/monthlyRateAmount, /baseRemuneration/monthlyRateAmount/amount … (+90)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/corporate-groups`
- Summary: Create Corporate Group
- Schema file: `corporate-groups-request-schema_v03.json` (77,531 bytes)
- Top-level response groups (6): groupStatus, homeWorkLocation, homeOrganizationalUnits, workerGroups, laborUnion, bargainingUnit
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/corporate-groups/meta`
- Summary: Read additional Corporate Groups add/update metadata
- Schema file: `corporate-groups-meta-schema_v03.json` (113,236 bytes)
- Top-level response groups (354): queryCriteria, /corporateGroups, /corporateGroups/groupStatus, /corporateGroups/groupStatus/statusCode, /corporateGroups/groupStatus/statusCode/code, /corporateGroups/groupStatus/statusCode/name, /corporateGroups/groupStatus/reasonCode, /corporateGroups/groupStatus/reasonCode/code, /corporateGroups/groupStatus/reasonCode/name, /corporateGroups/groupStatus/effectiveDateTime, /corporateGroups/homeWorkLocation, /corporateGroups/homeWorkLocation/locationID, /corporateGroups/homeWorkLocation/nameCode, /corporateGroups/homeWorkLocation/nameCode/code, /corporateGroups/homeWorkLocation/nameCode/name, /corporateGroups/homeWorkLocation/address, /corporateGroups/homeWorkLocation/address/nameCode, /corporateGroups/homeWorkLocation/address/nameCode/code, /corporateGroups/homeWorkLocation/address/nameCode/name, /corporateGroups/homeWorkLocation/address/attentionOfName, /corporateGroups/homeWorkLocation/address/careOfName, /corporateGroups/homeWorkLocation/address/scriptCode, /corporateGroups/homeWorkLocation/address/scriptCode/code, /corporateGroups/homeWorkLocation/address/scriptCode/name, /corporateGroups/homeWorkLocation/address/lineFour, /corporateGroups/homeWorkLocation/address/lineFive, /corporateGroups/homeWorkLocation/address/buildingNumber, /corporateGroups/homeWorkLocation/address/buildingNumberExtension, /corporateGroups/homeWorkLocation/address/buildingName, /corporateGroups/homeWorkLocation/address/blockName … (+324)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### PUT `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/primary-assignment`
- Summary: Update worker's primary assignment
- Schema file: `worker-primary-assignment-schema_v01.json` (33,727 bytes)
- Top-level response groups (5): effectiveDate, workAssignments, _links, _meta, _confirmMessage
- Recommendation: **keep whole (mutation requires full body)**

### POST `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits`
- Summary: Create worker's reportable benefits
- Schema file: `worker-compensation-reportable-benefits-schema_v01.json` (36,898 bytes)
- Top-level response groups (7): associateOID, workerID, workAssignmentID, reportableBenefits, _links, _meta, _confirmMessage
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits`
- Summary: Read worker's reportable benefits
- Schema file: `worker-compensation-reportable-benefits-schema_v01.json` (36,898 bytes)
- Top-level response groups (7): associateOID, workerID, workAssignmentID, reportableBenefits, _links, _meta, _confirmMessage
- Recommendation: **SPLIT — 7 top-level groups, 36,898B schema**

### PUT `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits`
- Summary: Update worker's reportable benefits
- Schema file: `worker-compensation-reportable-benefits-schema_v01.json` (36,898 bytes)
- Top-level response groups (7): associateOID, workerID, workAssignmentID, reportableBenefits, _links, _meta, _confirmMessage
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/reportable-benefits/meta`
- Summary: Read reportable benefit add/update metadata
- Schema file: `worker-compensation-reportable-benefits-meta-schema_v01.json` (70,997 bytes)
- Top-level response groups (38): queryCriteria, /associateOID, /workerID, /workerID/id, /workerID/scheme, /workerID/scheme/code, /workerID/scheme/name, /workerID/schemeAgency, /workAssignmentID, /reportableBenefits, /reportableBenefits/earningID, /reportableBenefits/earningCode, /reportableBenefits/earningCode/code, /reportableBenefits/earningCode/name, /reportableBenefits/earningAmount, /reportableBenefits/earningAmount/amount, /reportableBenefits/earningAmount/currencyCode, /reportableBenefits/itemCategoryCode, /reportableBenefits/itemCategoryCode/code, /reportableBenefits/itemCategoryCode/name, /reportableBenefits/inactiveIndicator, /reportableBenefits/effectiveDate, /_links, /_links/linkID, /_links/href, /_links/rel, /_links/canonicalUri, /_links/title, /_links/mediaType, /_links/method … (+8)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### PUT `/hr/worker-profile/v1/workers/{aoid}/work-assignments/{assignment-id}/worker-dates`
- Summary: Update worker dates
- Schema file: `confirm-message-schema_v01.json` (0 bytes)
- Top-level response groups (0): —
- Recommendation: **keep whole (mutation requires full body)**
