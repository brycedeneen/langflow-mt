# Workers Personal Communication Management (v2)

- Domain: `hr`
- Slug: `workers-personal-communication-management`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers-personal-communication-management/v2/workers-personal-communication-management-swagger_v2-merged.json
- Status: **ok**

## Operations (22)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.legal-address.add` | 60,817 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.legal-address.change` | 60,818 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.legal-address.remove` | 60,310 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-address.add` | 72,569 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-address.change` | 73,271 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-address.remove` | 64,888 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.email.add` | 56,280 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.email.change` | 57,372 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.email.remove` | 55,535 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.fax.add` | 60,923 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.fax.change` | 62,009 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.fax.remove` | 58,031 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.landline.add` | 60,948 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.landline.change` | 62,049 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.landline.remove` | 58,066 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.mobile.add` | 60,952 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.mobile.change` | 62,033 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.mobile.remove` | 58,052 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.pager.add` | 60,947 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.pager.change` | 62,025 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/hr/v1/worker.personal-communication.pager.remove` | 58,045 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.personal-communication.pager.remove/meta` | 57,059 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/hr/v1/worker.legal-address.add`
- Summary: Add Worker Legal Address
- Schema file: `events_hr.worker.legalAddress.add_schema_v01_00_rev003.json` (60,817 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.legal-address.change`
- Summary: Change Worker Legal Address
- Schema file: `events_hr.worker.legalAddress.change_schema_v01_00_rev004.json` (60,818 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.legal-address.remove`
- Summary: Remove Worker Legal Address
- Schema file: `events_hr.worker.legalAddress.remove_schema_v01_00_rev001.json` (60,310 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-address.add`
- Summary: Add Worker Personal Address
- Schema file: `events_hr.worker.personalAddress.add_schema_v01_00_rev004.json` (72,569 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-address.change`
- Summary: Change Worker Personal Address
- Schema file: `events_hr.worker.personalAddress.change_schema_v01_00_rev005.json` (73,271 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-address.remove`
- Summary: Remove Worker Personal Address
- Schema file: `events_hr.worker.personalAddress.remove_schema_v01_00_rev004.json` (64,888 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.email.add`
- Summary: Add Worker Personal Email
- Schema file: `events_hr.worker.personalCommunication.email.add_schema_v01_00_rev004.json` (56,280 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.email.change`
- Summary: Change Worker Personal Email
- Schema file: `events_hr.worker.personalCommunication.email.change_schema_v01_00_rev004.json` (57,372 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.email.remove`
- Summary: Remove Worker Personal Email
- Schema file: `events_hr.worker.personalCommunication.email.remove_schema_v01_00_rev004.json` (55,535 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.fax.add`
- Summary: Add Worker Personal Fax
- Schema file: `events_hr.worker.personalCommunication.fax.add_schema_v01_00_rev004.json` (60,923 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.fax.change`
- Summary: Change Worker Personal Fax
- Schema file: `events_hr.worker.personalCommunication.fax.change_schema_v01_00_rev004.json` (62,009 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.fax.remove`
- Summary: Remove Worker Personal Fax
- Schema file: `events_hr.worker.personalCommunication.fax.remove_schema_v01_00_rev004.json` (58,031 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.landline.add`
- Summary: Add Worker Personal Landline
- Schema file: `events_hr.worker.personalCommunication.landline.add_schema_v01_00_rev004.json` (60,948 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.landline.change`
- Summary: Change Worker Personal Landline
- Schema file: `events_hr.worker.personalCommunication.landline.change_schema_v01_00_rev004.json` (62,049 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.landline.remove`
- Summary: Remove Worker Personal Landline
- Schema file: `events_hr.worker.personalCommunication.landline.remove_schema_v01_00_rev004.json` (58,066 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.mobile.add`
- Summary: Add Worker Personal Mobile
- Schema file: `events_hr.worker.personalCommunication.mobile.add_schema_v01_00_rev004.json` (60,952 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.mobile.change`
- Summary: Change Worker Personal Mobile
- Schema file: `events_hr.worker.personalCommunication.mobile.change_schema_v01_00_rev004.json` (62,033 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.mobile.remove`
- Summary: Remove Worker Personal Mobile
- Schema file: `events_hr.worker.personalCommunication.mobile.remove_schema_v01_00_rev004.json` (58,052 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.pager.add`
- Summary: Add Worker Personal Pager
- Schema file: `events_hr.worker.personalCommunication.pager.add_schema_v01_00_rev004.json` (60,947 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.pager.change`
- Summary: Change Worker Personal Pager
- Schema file: `events_hr.worker.personalCommunication.pager.change_schema_v01_00_rev004.json` (62,025 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/hr/v1/worker.personal-communication.pager.remove`
- Summary: Remove Worker Personal Pager
- Schema file: `events_hr.worker.personalCommunication.pager.remove_schema_v01_00_rev004.json` (58,045 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.personal-communication.pager.remove/meta`
- Summary: Remove Worker Personal Pager Meta
- Schema file: `events_hr.worker.personalCommunication.pager.remove_meta_schema_v01_00_rev004.json` (57,059 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
