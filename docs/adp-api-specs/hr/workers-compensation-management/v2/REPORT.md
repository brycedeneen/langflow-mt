# Workers Compensation Management (v2)

- Domain: `hr`
- Slug: `workers-compensation-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-compensation-management/v2/workers-compensation-management-swagger_v2-merged.json
- Status: **ok**

## Operations (8)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.work-assignment.additional-remuneration.add` | 45,292 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.work-assignment.additional-remuneration.add/meta` | 70,784 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.work-assignment.additional-remuneration.change` | 46,116 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.work-assignment.additional-remuneration.change/meta` | 71,065 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.work-assignment.additional-remuneration.remove` | 41,442 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.work-assignment.additional-remuneration.remove/meta` | 62,107 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.work-assignment.base-remuneration.change` | 87,430 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.work-assignment.base-remuneration.change/meta` | 101,569 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/hr/v1/worker.work-assignment.additional-remuneration.add`
- Summary: Add Additional Remuneration
- Schema file: `events_hr.worker.workAssignment.additionalRemuneration.add_schema_v01_00_rev004.json` (45,292 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.work-assignment.additional-remuneration.add/meta`
- Summary: Add Additional Remuneration Meta
- Schema file: `events_hr.worker.workAssignment.additionalRemuneration.add_meta_schema_v01_00_rev004.json` (70,784 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.work-assignment.additional-remuneration.change`
- Summary: Change Additional Remuneration
- Schema file: `events_hr.worker.workAssignment.additionalRemuneration.change_schema_v01_00_rev004.json` (46,116 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.work-assignment.additional-remuneration.change/meta`
- Summary: Change Additional Remuneration Meta
- Schema file: `events_hr.worker.workAssignment.additionalRemuneration.change_meta_schema_v01_00_rev004.json` (71,065 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.work-assignment.additional-remuneration.remove`
- Summary: Remove Additional Remuneration
- Schema file: `events_hr.worker.workAssignment.additionalRemuneration.remove_schema_v01_00_rev004.json` (41,442 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.work-assignment.additional-remuneration.remove/meta`
- Summary: Remove Additional Remuneration Meta
- Schema file: `events_hr.worker.workAssignment.additionalRemuneration.remove_meta_schema_v01_00_rev004.json` (62,107 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.work-assignment.base-remuneration.change`
- Summary: Change Base Remuneration
- Schema file: `events_hr.worker.workAssignment.baseRemuneration.change_schema_v01_00_rev008.json` (87,430 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.work-assignment.base-remuneration.change/meta`
- Summary: Change Base Remuneration Meta
- Schema file: `events_hr.worker.workAssignment.baseRemuneration.change_meta_schema_v01_00_rev008.json` (101,569 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
