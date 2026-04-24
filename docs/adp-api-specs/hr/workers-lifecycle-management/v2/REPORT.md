# Workers Lifecycle Management (v2)

- Domain: `hr`
- Slug: `workers-lifecycle-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-lifecycle-management/v2/workers-lifecycle-management-swagger_v2-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.rehire` | 308,259 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.rehire/meta` | 511,282 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/hr/v1/worker.rehire`
- Summary: Rehire Worker
- Schema file: `events_hr.worker.rehire_schema_v01_00_rev018.json` (308,259 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.rehire/meta`
- Summary: Rehire Worker Meta
- Schema file: `events_hr.worker.rehire_meta_schema_v01_00_rev018.json` (511,282 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
