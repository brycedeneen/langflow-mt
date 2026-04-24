# Workers (v2)

- Domain: `hr`
- Slug: `workers`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/workers/v2/workers-swagger_v2-merged.json
- Status: **ok**

## Operations (8)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.photo.remove` | 54,504 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.photo.remove/meta` | 61,602 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/hr/v1/worker.photo.upload` | 55,406 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.photo.upload/meta` | 64,451 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/hr/v2/workers` | 221,686 | `associateOID`, `workerID`, `alternateIDs`, `person`, `associateProfile`, `workerDates`, `workerStatus`, `photos` *(+7)* | SPLIT — 15 top-level groups, 221,686B schema |
| GET | `/hr/v2/workers/meta` | 482,083 | `queryCriteria`, `/workers`, `/workers/associateOID`, `/workers/workerID`, `/workers/workerID/idValue`, `/workers/workerID/schemeCode`, `/workers/workerID/schemeCode/codeValue`, `/workers/workerID/schemeCode/shortName` *(+3015)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/hr/v2/workers/{aoid}` | 221,686 | `associateOID`, `workerID`, `alternateIDs`, `person`, `associateProfile`, `workerDates`, `workerStatus`, `photos` *(+7)* | SPLIT — 15 top-level groups, 221,686B schema |
| GET | `/hr/v2/workers/{aoid}/worker-images/photo` | 0 | — | single tool — payload is small |

## Per-operation detail

### POST `/events/hr/v1/worker.photo.remove`
- Summary: Remove Photo
- Schema file: `events_hr.worker.photo.remove_schema_v01_00_rev003.json` (54,504 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.photo.remove/meta`
- Summary: Remove Photo Meta
- Schema file: `events_hr.worker.photo.remove_meta_schema_v01_00_rev003.json` (61,602 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/hr/v1/worker.photo.upload`
- Summary: Upload Photo
- Schema file: `events_hr.worker.photo.upload_schema_v01_00_rev003.json` (55,406 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.photo.upload/meta`
- Summary: Upload Worker Profile Photo Meta
- Schema file: `events_hr.worker.photo.upload_meta_schema_v01_00_rev003.json` (64,451 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/hr/v2/workers`
- Summary: Workers Data Collection
- Schema file: `workers_schema_v02_00_rev021.json` (221,686 bytes)
- Top-level response groups (15): associateOID, workerID, alternateIDs, person, associateProfile, workerDates, workerStatus, photos, businessCommunication, workAssignments, organizationalRoles, workerMedia, customFieldGroup, links, _languageCode
- Recommendation: **SPLIT — 15 top-level groups, 221,686B schema**

### GET `/hr/v2/workers/meta`
- Summary: Worker Meta
- Schema file: `workers_meta_schema_v02_00_rev021.json` (482,083 bytes)
- Top-level response groups (3023): queryCriteria, /workers, /workers/associateOID, /workers/workerID, /workers/workerID/idValue, /workers/workerID/schemeCode, /workers/workerID/schemeCode/codeValue, /workers/workerID/schemeCode/shortName, /workers/workerID/schemeCode/longName, /workers/alternateIDs, /workers/alternateIDs/idValue, /workers/alternateIDs/schemeCode, /workers/alternateIDs/schemeCode/codeValue, /workers/alternateIDs/schemeCode/shortName, /workers/alternateIDs/schemeCode/longName, /workers/person, /workers/person/governmentIDs, /workers/person/governmentIDs/idValue, /workers/person/governmentIDs/nameCode, /workers/person/governmentIDs/nameCode/codeValue, /workers/person/governmentIDs/nameCode/shortName, /workers/person/governmentIDs/nameCode/longName, /workers/person/governmentIDs/countryCode, /workers/person/governmentIDs/statusCode, /workers/person/governmentIDs/statusCode/codeValue, /workers/person/governmentIDs/statusCode/shortName, /workers/person/governmentIDs/statusCode/longName, /workers/person/governmentIDs/statusCode/effectiveDate, /workers/person/governmentIDs/expirationDate, /workers/person/governmentIDs/itemID … (+2993)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/hr/v2/workers/{aoid}`
- Summary: Individual Worker Data
- Schema file: `workers_schema_v02_00_rev021.json` (221,686 bytes)
- Top-level response groups (15): associateOID, workerID, alternateIDs, person, associateProfile, workerDates, workerStatus, photos, businessCommunication, workAssignments, organizationalRoles, workerMedia, customFieldGroup, links, _languageCode
- Recommendation: **SPLIT — 15 top-level groups, 221,686B schema**

### GET `/hr/v2/workers/{aoid}/worker-images/photo`
- Summary: Worker Profile Picture
- Schema file: `—` (0 bytes)
- Top-level response groups (0): —
- Recommendation: **single tool — payload is small**
