# Data Collection Entries (v1)

- Domain: `time`
- Slug: `data-collection-entries`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/data-collection-entries/v1/data-collection-entries-swagger_v1-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/time/v1/data-collection-entries.process` | 120,207 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v1/data-collection-entries.process/{event-id}` | 120,207 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | SPLIT — 21 top-level groups, 120,207B schema |

## Per-operation detail

### POST `/events/time/v1/data-collection-entries.process`
- Summary: Process Data Collection Entries
- Schema file: `events_time.dataCollectionEntries.process_schema_v01_00_rev002.json` (120,207 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v1/data-collection-entries.process/{event-id}`
- Summary: Process Data Collection Entries  Event Instance (by Event Manager)
- Schema file: `events_time.dataCollectionEntries.process_schema_v01_00_rev002.json` (120,207 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **SPLIT — 21 top-level groups, 120,207B schema**
