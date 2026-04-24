# Work Schedules (v1)

- Domain: `time`
- Slug: `work-schedules`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/work-schedules/v1/work-schedules-swagger_v1-merged.json
- Status: **ok**

## Operations (19)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/time/v1/work-schedule-day.add` | 74,831 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule-day.add/meta` | 88,212 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule-day.change` | 75,115 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule-day.change/meta` | 88,332 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule-day.copy` | 76,432 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule-day.copy/meta` | 90,877 | `control` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule-day.remove` | 72,785 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule-day.remove/meta` | 61,607 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule-entry.change` | 71,813 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/time/v1/work-schedule.add` | 75,414 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule.add/meta` | 90,893 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule.change` | 75,539 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule.change/meta` | 91,035 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule.copy` | 78,926 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule.copy/meta` | 94,976 | `control` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/time/v1/work-schedule.remove` | 72,399 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/work-schedule.remove/meta` | 61,195 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/time/v1/work-schedules` | 94,162 | `workSchedules`, `workScheduleTotals`, `meta`, `confirmMessage` | split-maybe — 94,162B schema |
| GET | `/time/v1/workers/{aoid}/work-schedules` | 94,162 | `workSchedules`, `workScheduleTotals`, `meta`, `confirmMessage` | split-maybe — 94,162B schema |

## Per-operation detail

### POST `/events/time/v1/work-schedule-day.add`
- Summary: Add Schedule Day
- Schema file: `events_time.workScheduleDay.add_schema_v01_00_rev002.json` (74,831 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule-day.add/meta`
- Summary: Add Schedule Day Meta
- Schema file: `events_time.workScheduleDay.add_meta_schema_v01_00_rev002.json` (88,212 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule-day.change`
- Summary: Change Schedule Day
- Schema file: `events_time.workScheduleDay.change_schema_v01_00_rev002.json` (75,115 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule-day.change/meta`
- Summary: Change Schedule Day Meta
- Schema file: `events_time.workScheduleDay.change_meta_schema_v01_00_rev002.json` (88,332 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule-day.copy`
- Summary: Copy Schedule Day
- Schema file: `events_time.workScheduleDay.copy_schema_v01_00_rev002.json` (76,432 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule-day.copy/meta`
- Summary: Copy Schedule Day Meta
- Schema file: `events_time.workScheduleDay.copy_meta_schema_v01_00_rev002.json` (90,877 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule-day.remove`
- Summary: Remove Schedule Day
- Schema file: `events_time.workScheduleDay.remove_schema_v01_00_rev002.json` (72,785 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule-day.remove/meta`
- Summary: Remove Schedule Day Meta
- Schema file: `events_time.workScheduleDay.remove_meta_schema_v01_00_rev002.json` (61,607 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule-entry.change`
- Summary: Change Schedule Entry
- Schema file: `events_time.workScheduleEntry.change_schema_v01_00_rev002.json` (71,813 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/time/v1/work-schedule.add`
- Summary: Add Employee Work Schedule
- Schema file: `events_time.workSchedule.add_schema_v01_00_rev002.json` (75,414 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule.add/meta`
- Summary: Add Employee Work Schedule Meta
- Schema file: `events_time.workSchedule.add_meta_schema_v01_00_rev002.json` (90,893 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule.change`
- Summary: Change Employee Work Schedule
- Schema file: `events_time.workSchedule.change_schema_v01_00_rev002.json` (75,539 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule.change/meta`
- Summary: Change Employee Work Schedule Meta
- Schema file: `events_time.workSchedule.change_meta_schema_v01_00_rev002.json` (91,035 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule.copy`
- Summary: Copy Employee Work Schedule
- Schema file: `events_time.workSchedule.copy_schema_v01_00_rev002.json` (78,926 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule.copy/meta`
- Summary: Copy Employee Work Schedule Meta
- Schema file: `events_time.workSchedule.copy_meta_schema_v01_00_rev002.json` (94,976 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/time/v1/work-schedule.remove`
- Summary: Remove Employee Work Schedule
- Schema file: `events_time.workSchedule.remove_schema_v01_00_rev002.json` (72,399 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/work-schedule.remove/meta`
- Summary: Remove Employee Work Schedule Meta
- Schema file: `events_time.workSchedule.remove_meta_schema_v01_00_rev002.json` (61,195 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/time/v1/work-schedules`
- Summary: Team Work Schedules [DEPRECATED]
- Schema file: `workSchedules_schema_v01_00_rev005.json` (94,162 bytes)
- Top-level response groups (4): workSchedules, workScheduleTotals, meta, confirmMessage
- Recommendation: **split-maybe — 94,162B schema**

### GET `/time/v1/workers/{aoid}/work-schedules`
- Summary: Work Schedules
- Schema file: `workSchedules_schema_v01_00_rev005.json` (94,162 bytes)
- Top-level response groups (4): workSchedules, workScheduleTotals, meta, confirmMessage
- Recommendation: **split-maybe — 94,162B schema**
