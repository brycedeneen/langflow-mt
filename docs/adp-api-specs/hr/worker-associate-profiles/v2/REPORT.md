# Worker Associate Profiles (v2)

- Domain: `hr`
- Slug: `worker-associate-profiles`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hr/worker-associate-profiles/v2/worker-associate-profiles-swagger_v2-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/hr/v1/worker.associate-profile.preferred-gender-pronoun.change` | 52,581 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/hr/v1/worker.associate-profile.preferred-gender-pronoun.change/meta` | 56,862 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/hr/v1/worker.associate-profile.preferred-gender-pronoun.change`
- Summary: Update Worker's Associate Preferred Gender Pronoun
- Schema file: `events_hr.worker.associateProfile.preferredGenderPronoun.change_schema_v01_00_rev001.json` (52,581 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/hr/v1/worker.associate-profile.preferred-gender-pronoun.change/meta`
- Summary: Update Worker's Associate Preferred Gender Pronoun API Metadata
- Schema file: `events_hr.worker.associateProfile.preferredGenderPronoun.change_meta_schema_v01_00_rev001.json` (56,862 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
