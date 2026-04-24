# Time Cards (v2)

- Domain: `time`
- Slug: `time-cards`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/time-cards/v2/time-cards-swagger_v2-merged.json
- Status: **ok**

## Operations (1)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/time/v2/time-entries.modify` | 111,874 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |

## Per-operation detail

### POST `/events/time/v2/time-entries.modify`
- Summary: Modify Time Entries
- Schema file: `events_time.timeEntries.modify_schema_v02_00_rev004.json` (111,874 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**
