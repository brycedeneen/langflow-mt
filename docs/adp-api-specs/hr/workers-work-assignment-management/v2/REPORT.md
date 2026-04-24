# Workers Work Assignment Management (v2)

- Domain: `hr`
- Slug: `workers-work-assignment-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-work-assignment-management/v2/workers-work-assignment-management-swagger_v2-merged.json
- Status: **ok**

## Operations (7)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.reports-to.modify` | 60,880 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.reports-to.modify/meta` | 65,578 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.work-assignment.assigned-organizational-units.modify` | 57,202 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.work-assignment.assigned-organizational-units.modify/meta` | 280,994 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.work-assignment.modify` | 238,541 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.work-assignment.modify/meta` | 280,994 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.work-assignment.terminate` | 93,896 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |

## Per-operation detail

### POST `/events/hr/v1/worker.reports-to.modify`
- Summary: Modify Worker Reports To
- Schema file: `events_hr.worker.reportsTo.modify_schema_v01_00_rev001.json` (60,880 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.reports-to.modify/meta`
- Summary: Modify Worker Reports To Meta
- Schema file: `events_hr.worker.reportsTo.modify_meta_schema_v01_00_rev001.json` (65,578 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.work-assignment.assigned-organizational-units.modify`
- Summary: Modify Worker's Assigned Organizational Units
- Schema file: `events_hr.worker.workAssignment.assignedOrganizationalUnits.modify_schema_v01_00_rev001.json` (57,202 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.work-assignment.assigned-organizational-units.modify/meta`
- Summary: Modify Worker's Assigned Organizational Units Metadata
- Schema file: `events_hr.worker.workAssignment.modify_meta_schema_v01_00_rev007.json` (280,994 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.work-assignment.modify`
- Summary: Modify Work Assignment
- Schema file: `events_hr.worker.workAssignment.modify_schema_v01_00_rev007.json` (238,541 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.work-assignment.modify/meta`
- Summary: Modify Work Assignment Meta
- Schema file: `events_hr.worker.workAssignment.modify_meta_schema_v01_00_rev007.json` (280,994 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.work-assignment.terminate`
- Summary: Terminate Work Assignment
- Schema file: `events_hr.worker.workAssignment.terminate_schema_v01_00_rev005.json` (93,896 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**
