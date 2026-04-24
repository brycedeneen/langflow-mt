# Job Applicants (v2)

- Domain: `staffing`
- Slug: `job-applicants`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/staffing/job-applicants/v2/job-applicants-swagger_v2-merged.json
- Status: **ok**

## Operations (4)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/staffing/v1/job-applicant.external-assessment.status.change` | 96,591 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/staffing/v1/job-applicant.external-screening.initiate` | 96,961 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/staffing/v1/job-applicant.external-screening.packages.modify` | 56,041 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/staffing/v1/job-applicant.external-screening.status.change` | 97,691 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |

## Per-operation detail

### POST `/events/staffing/v1/job-applicant.external-assessment.status.change`
- Summary: Update Applicant's External Agency Assessment Status
- Schema file: `events_staffing.jobApplicant.externalAssessment.status.change_schema_v01_00_rev001.json` (96,591 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/staffing/v1/job-applicant.external-screening.initiate`
- Summary: Intiate Applicant's External Agency Screening
- Schema file: `events_staffing.jobApplicant.externalScreening.initiate_schema_v01_00_rev001.json` (96,961 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/staffing/v1/job-applicant.external-screening.packages.modify`
- Summary: Intiate Applicant's External Agency Screening
- Schema file: `events_staffing.jobApplicant.externalScreening.packages.modify_schema_v01_00_rev001.json` (56,041 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/staffing/v1/job-applicant.external-screening.status.change`
- Summary: Update Applicant's External Agency Screening Status
- Schema file: `events_staffing.jobApplicant.externalScreening.status.change_schema_v01_00_rev001.json` (97,691 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**
