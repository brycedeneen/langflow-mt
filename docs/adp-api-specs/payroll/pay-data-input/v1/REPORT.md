# Pay Data Input (v1)

- Domain: `payroll`
- Slug: `pay-data-input`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/payroll/pay-data-input/v1/pay-data-input-swagger_v1-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/payroll/v1/pay-data-input.modify` | 201,459 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v1/pay-data-input.modify/meta` | 163,417 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/payroll/v1/pay-data-input.modify`
- Summary: Modify Pay Data Input
- Schema file: `events_payroll.payDataInput.modify_schema_v01_00_rev005.json` (201,459 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v1/pay-data-input.modify/meta`
- Summary: Modify Pay Data Input Meta
- Schema file: `events_payroll.payDataInput.modify_meta_schema_v01_00_rev005.json` (163,417 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
