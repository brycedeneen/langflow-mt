# Time Off Balances (v3)

- Domain: `time`
- Slug: `time-off-balances`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/time-off-balances/v3/time-off-balances-swagger_v3-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/time/v3/time-off-balances.modify` | 64,022 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/time/v3/time-off-balances.modify/meta` | 63,745 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/time/v3/time-off-balances.modify`
- Summary: Modify Time Off Balances
- Schema file: `events_time.timeOffBalances.modify_schema_v03_00_rev001.json` (64,022 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/time/v3/time-off-balances.modify/meta`
- Summary: Modify Time Off Balances Meta
- Schema file: `events_time.timeOffBalances.modify_meta_schema_v03_00_rev001.json` (63,745 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
