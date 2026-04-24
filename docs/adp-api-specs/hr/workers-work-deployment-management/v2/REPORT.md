# Workers Work Deployment Management (v2)

- Domain: `hr`
- Slug: `workers-work-deployment-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-work-deployment-management/v2/workers-work-deployment-management-swagger_v2-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.work-assignment.standard-hours.change` | 34,810 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.work-assignment.worker-type.change` | 54,566 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |

## Per-operation detail

### POST `/events/hr/v1/worker.work-assignment.standard-hours.change`
- Summary: Change Standard Hours
- Schema file: `events_hr.worker.workAssignment.standardHours.change_schema_v01_00_rev003.json` (34,810 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.work-assignment.worker-type.change`
- Summary: Change Worker Type
- Schema file: `events_hr.worker.workAssignment.workerType.change_schema_v01_00_rev001.json` (54,566 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**
