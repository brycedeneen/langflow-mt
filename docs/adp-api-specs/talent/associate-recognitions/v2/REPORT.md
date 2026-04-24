# Associate Recognitions (v2)

- Domain: `talent`
- Slug: `associate-recognitions`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-recognitions/v2/associate-recognitions-swagger_v2-merged.json
- Status: **ok**

## Operations (8)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/talent/v1/associate.ksaoc.recognition.add` | 82,556 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.recognition.add/meta` | 97,774 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.recognition.change` | 83,095 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.recognition.change/meta` | 98,009 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.recognition.remove` | 79,574 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.recognition.remove/meta` | 61,277 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-recognitions` | 56,647 | `nameCode`, `typeCode`, `issuingParty`, `issueDate`, `customFieldGroup`, `itemID`, `personOID`, `links` | SPLIT — 8 top-level groups, 56,647B schema |
| GET | `/talent/v2/associates/{aoid}/associate-recognitions/meta` | 92,915 | `queryCriteria`, `/associateRecognitions`, `/associateRecognitions/nameCode`, `/associateRecognitions/nameCode/codeValue`, `/associateRecognitions/nameCode/shortName`, `/associateRecognitions/nameCode/longName`, `/associateRecognitions/nameCode/alternateID`, `/associateRecognitions/nameCode/alternateID/idValue` *(+245)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/talent/v1/associate.ksaoc.recognition.add`
- Summary: Add Recognition
- Schema file: `events_talent.associate.ksaoc.recognition.add_schema_v01_00_rev006.json` (82,556 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.recognition.add/meta`
- Summary: Add Recognition Meta
- Schema file: `events_talent.associate.ksaoc.recognition.add_meta_schema_v01_00_rev006.json` (97,774 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.recognition.change`
- Summary: Change Recognition
- Schema file: `events_talent.associate.ksaoc.recognition.change_schema_v01_00_rev006.json` (83,095 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.recognition.change/meta`
- Summary: Change Recognition Meta
- Schema file: `events_talent.associate.ksaoc.recognition.change_meta_schema_v01_00_rev006.json` (98,009 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.recognition.remove`
- Summary: Remove Recognition
- Schema file: `events_talent.associate.ksaoc.recognition.remove_schema_v01_00_rev007.json` (79,574 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.recognition.remove/meta`
- Summary: Remove Recognition Meta
- Schema file: `events_talent.associate.ksaoc.recognition.remove_meta_schema_v01_00_rev007.json` (61,277 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-recognitions`
- Summary: Recognitions
- Schema file: `associateRecognitions_schema_v02_00_rev003.json` (56,647 bytes)
- Top-level response groups (8): nameCode, typeCode, issuingParty, issueDate, customFieldGroup, itemID, personOID, links
- Recommendation: **SPLIT — 8 top-level groups, 56,647B schema**

### GET `/talent/v2/associates/{aoid}/associate-recognitions/meta`
- Summary: Recognition Meta
- Schema file: `associateRecognitions_meta_schema_v02_00_rev003.json` (92,915 bytes)
- Top-level response groups (253): queryCriteria, /associateRecognitions, /associateRecognitions/nameCode, /associateRecognitions/nameCode/codeValue, /associateRecognitions/nameCode/shortName, /associateRecognitions/nameCode/longName, /associateRecognitions/nameCode/alternateID, /associateRecognitions/nameCode/alternateID/idValue, /associateRecognitions/nameCode/alternateID/schemeCode, /associateRecognitions/nameCode/alternateID/schemeCode/codeValue, /associateRecognitions/nameCode/alternateID/schemeCode/shortName, /associateRecognitions/nameCode/alternateID/schemeCode/longName, /associateRecognitions/typeCode, /associateRecognitions/typeCode/codeValue, /associateRecognitions/typeCode/shortName, /associateRecognitions/typeCode/longName, /associateRecognitions/typeCode/alternateID, /associateRecognitions/typeCode/alternateID/idValue, /associateRecognitions/typeCode/alternateID/schemeCode, /associateRecognitions/typeCode/alternateID/schemeCode/codeValue, /associateRecognitions/typeCode/alternateID/schemeCode/shortName, /associateRecognitions/typeCode/alternateID/schemeCode/longName, /associateRecognitions/issuingParty, /associateRecognitions/issuingParty/nameCode, /associateRecognitions/issuingParty/nameCode/codeValue, /associateRecognitions/issuingParty/nameCode/shortName, /associateRecognitions/issuingParty/nameCode/longName, /associateRecognitions/issuingParty/nameCode/alternateID, /associateRecognitions/issuingParty/nameCode/alternateID/idValue, /associateRecognitions/issuingParty/nameCode/alternateID/schemeCode … (+223)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
