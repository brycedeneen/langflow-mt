# Worker Leaves (v2)

- Domain: `hr`
- Slug: `worker-leaves`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/worker-leaves/v2/worker-leaves-swagger_v2-merged.json
- Status: **ok**

## Operations (9)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.leave.absence.request` | 61,098 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.leave.absence.request/meta` | 73,137 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.leave.cancel` | 64,494 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.leave.cancel/meta` | 58,399 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.leave.change` | 65,438 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.leave.change/meta` | 79,820 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.leave.return.request` | 65,593 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.leave.return.request/meta` | 75,635 | `control` | single tool (meta discovery — rarely agent-facing) |
| GET | `/hr/v2/workers/{aoid}/leaves` | 42,149 | `associateOID`, `workerID`, `workAssignmentID`, `leaves` | split-maybe — 42,149B schema |

## Per-operation detail

### POST `/events/hr/v1/worker.leave.absence.request`
- Summary: Request Leave Of Absence
- Schema file: `events_hr.worker.leave.absence.request_schema_v01_00_rev002.json` (61,098 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.leave.absence.request/meta`
- Summary: Request Leave Of Absence Meta
- Schema file: `events_hr.worker.leave.absence.request_meta_schema_v01_00_rev002.json` (73,137 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.leave.cancel`
- Summary: Cancel Worker Leave
- Schema file: `events_hr.worker.leave.cancel_schema_v01_00_rev002.json` (64,494 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.leave.cancel/meta`
- Summary: Cancel Worker Leave Meta
- Schema file: `events_hr.worker.leave.cancel_meta_schema_v01_00_rev002.json` (58,399 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.leave.change`
- Summary: Change Worker Leave
- Schema file: `events_hr.worker.leave.change_schema_v01_00_rev002.json` (65,438 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.leave.change/meta`
- Summary: Change Worker Leave Meta
- Schema file: `events_hr.worker.leave.change_meta_schema_v01_00_rev002.json` (79,820 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.leave.return.request`
- Summary: Request Return From Leave Of Absence
- Schema file: `events_hr.worker.leave.return.request_schema_v01_00_rev003.json` (65,593 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.leave.return.request/meta`
- Summary: Request Return From Leave Of Absence Meta
- Schema file: `events_hr.worker.leave.return.request_meta_schema_v01_00_rev003.json` (75,635 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/hr/v2/workers/{aoid}/leaves`
- Summary: Worker Leaves
- Schema file: `workerLeaves_schema_v02_00_rev001.json` (42,149 bytes)
- Top-level response groups (4): associateOID, workerID, workAssignmentID, leaves
- Recommendation: **split-maybe — 42,149B schema**
