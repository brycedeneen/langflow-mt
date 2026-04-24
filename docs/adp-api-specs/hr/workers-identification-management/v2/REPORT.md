# Workers Identification Management (v2)

- Domain: `hr`
- Slug: `workers-identification-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-identification-management/v2/workers-identification-management-swagger_v2-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.government-id.add` | 57,423 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.government-id.change` | 59,368 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |

## Per-operation detail

### POST `/events/hr/v1/worker.government-id.add`
- Summary: Add Worker Government ID
- Schema file: `events_hr.worker.governmentID.add_schema_v01_00_rev003.json` (57,423 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.government-id.change`
- Summary: Change Worker Government ID
- Schema file: `events_hr.worker.governmentID.change_schema_v01_00_rev003.json` (59,368 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**
