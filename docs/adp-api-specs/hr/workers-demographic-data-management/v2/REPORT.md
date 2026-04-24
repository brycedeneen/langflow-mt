# Workers Demographic Data Management (v2)

- Domain: `hr`
- Slug: `workers-demographic-data-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-demographic-data-management/v2/workers-demographic-data-management-swagger_v2-merged.json
- Status: **ok**

## Operations (12)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.birth-name.change` | 37,735 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.birth-name.change/meta` | 68,604 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.legal-name.change` | 62,329 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.legal-name.change/meta` | 75,899 | `control` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.marital-status.change` | 57,889 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.marital-status.change/meta` | 65,048 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.military-classification.change` | 54,500 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.military-classification.change/meta` | 63,083 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.military-status.change` | 55,592 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.military-status.change/meta` | 62,545 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.preferred-name.change` | 58,695 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.preferred-name.change/meta` | 68,812 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/hr/v1/worker.birth-name.change`
- Summary: Change Birth Name
- Schema file: `events_hr.worker.birthName.change_schema_v01_00_rev003.json` (37,735 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.birth-name.change/meta`
- Summary: Change Birth Name Meta
- Schema file: `events_hr.worker.birthName.change_meta_schema_v01_00_rev003.json` (68,604 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.legal-name.change`
- Summary: Change Legal Name
- Schema file: `events_hr.worker.legalName.change_schema_v01_00_rev004.json` (62,329 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.legal-name.change/meta`
- Summary: Change Legal Name Meta
- Schema file: `events_hr.worker.legalName.change_meta_schema_v01_00_rev004.json` (75,899 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.marital-status.change`
- Summary: Change Worker Marital Status
- Schema file: `events_hr.worker.maritalStatus.change_schema_v01_00_rev004.json` (57,889 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.marital-status.change/meta`
- Summary: Change Worker Marital Status Meta
- Schema file: `events_hr.worker.maritalStatus.change_meta_schema_v01_00_rev004.json` (65,048 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.military-classification.change`
- Summary: Change Worker Military Classification
- Schema file: `events_hr.worker.militaryClassification.change_schema_v01_00_rev004.json` (54,500 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.military-classification.change/meta`
- Summary: Change Worker Military Classification Meta
- Schema file: `events_hr.worker.militaryClassification.change_meta_schema_v01_00_rev004.json` (63,083 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.military-status.change`
- Summary: Change Worker Military Status
- Schema file: `events_hr.worker.militaryStatus.change_schema_v01_00_rev004.json` (55,592 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.military-status.change/meta`
- Summary: Change Worker Military Status Meta
- Schema file: `events_hr.worker.militaryStatus.change_meta_schema_v01_00_rev004.json` (62,545 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.preferred-name.change`
- Summary: Change Preferred Name
- Schema file: `events_hr.worker.preferredName.change_schema_v01_00_rev004.json` (58,695 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.preferred-name.change/meta`
- Summary: Change Preferred Name Meta
- Schema file: `events_hr.worker.preferredName.change_meta_schema_v01_00_rev004.json` (68,812 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
