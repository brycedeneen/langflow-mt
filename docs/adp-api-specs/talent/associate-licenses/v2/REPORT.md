# Associate Licenses (v2)

- Domain: `talent`
- Slug: `associate-licenses`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-licenses/v2/associate-licenses-swagger_v2-merged.json
- Status: **ok**

## Operations (10)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/talent/v1/associate.ksaoc.license.add` | 93,651 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.license.add/meta` | 141,529 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.license.change` | 94,319 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.license.change/meta` | 141,750 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.license.remove` | 86,371 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.license.remove/meta` | 61,156 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-licenses` | 61,060 | `licenseID`, `licenseNameCode`, `licenseDescription`, `categoryCode`, `statusCode`, `issuingParty`, `firstIssueDate`, `lastIssueDate` *(+10)* | SPLIT — 18 top-level groups, 61,060B schema |
| GET | `/talent/v2/associates/{aoid}/associate-licenses/meta` | 129,477 | `queryCriteria`, `/associateLicenses`, `/associateLicenses/licenseID`, `/associateLicenses/licenseID/idValue`, `/associateLicenses/licenseID/schemeCode`, `/associateLicenses/licenseID/schemeCode/codeValue`, `/associateLicenses/licenseID/schemeCode/shortName`, `/associateLicenses/licenseID/schemeCode/longName` *(+507)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-licenses/{license-id}` | 61,060 | `licenseID`, `licenseNameCode`, `licenseDescription`, `categoryCode`, `statusCode`, `issuingParty`, `firstIssueDate`, `lastIssueDate` *(+10)* | SPLIT — 18 top-level groups, 61,060B schema |
| GET | `/talent/v2/associates/{aoid}/associate-licenses/{license-id}/meta` | 129,477 | `queryCriteria`, `/associateLicenses`, `/associateLicenses/licenseID`, `/associateLicenses/licenseID/idValue`, `/associateLicenses/licenseID/schemeCode`, `/associateLicenses/licenseID/schemeCode/codeValue`, `/associateLicenses/licenseID/schemeCode/shortName`, `/associateLicenses/licenseID/schemeCode/longName` *(+507)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/talent/v1/associate.ksaoc.license.add`
- Summary: Add License
- Schema file: `events_talent.associate.ksaoc.license.add_schema_v01_00_rev008.json` (93,651 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.license.add/meta`
- Summary: Add License Meta
- Schema file: `events_talent.associate.ksaoc.license.add_meta_schema_v01_00_rev008.json` (141,529 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.license.change`
- Summary: Change License
- Schema file: `events_talent.associate.ksaoc.license.change_schema_v01_00_rev008.json` (94,319 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.license.change/meta`
- Summary: Change License Meta
- Schema file: `events_talent.associate.ksaoc.license.change_meta_schema_v01_00_rev008.json` (141,750 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.license.remove`
- Summary: Remove License
- Schema file: `events_talent.associate.ksaoc.license.remove_schema_v01_00_rev008.json` (86,371 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.license.remove/meta`
- Summary: Remove License Meta
- Schema file: `events_talent.associate.ksaoc.license.remove_meta_schema_v01_00_rev008.json` (61,156 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-licenses`
- Summary: Licenses
- Schema file: `associateLicenses_schema_v02_00_rev004.json` (61,060 bytes)
- Top-level response groups (18): licenseID, licenseNameCode, licenseDescription, categoryCode, statusCode, issuingParty, firstIssueDate, lastIssueDate, expirationDate, endorsements, restrictions, employerPaidAmount, comments, renewalComments, violations, customFieldGroup, itemID, links
- Recommendation: **SPLIT — 18 top-level groups, 61,060B schema**

### GET `/talent/v2/associates/{aoid}/associate-licenses/meta`
- Summary: License Meta
- Schema file: `associateLicenses_meta_schema_v02_00_rev004.json` (129,477 bytes)
- Top-level response groups (515): queryCriteria, /associateLicenses, /associateLicenses/licenseID, /associateLicenses/licenseID/idValue, /associateLicenses/licenseID/schemeCode, /associateLicenses/licenseID/schemeCode/codeValue, /associateLicenses/licenseID/schemeCode/shortName, /associateLicenses/licenseID/schemeCode/longName, /associateLicenses/licenseNameCode, /associateLicenses/licenseNameCode/codeValue, /associateLicenses/licenseNameCode/shortName, /associateLicenses/licenseNameCode/longName, /associateLicenses/licenseDescription, /associateLicenses/categoryCode, /associateLicenses/categoryCode/codeValue, /associateLicenses/categoryCode/shortName, /associateLicenses/categoryCode/longName, /associateLicenses/statusCode, /associateLicenses/statusCode/codeValue, /associateLicenses/statusCode/shortName, /associateLicenses/statusCode/longName, /associateLicenses/statusCode/effectiveDate, /associateLicenses/issuingParty, /associateLicenses/issuingParty/nameCode, /associateLicenses/issuingParty/nameCode/codeValue, /associateLicenses/issuingParty/nameCode/shortName, /associateLicenses/issuingParty/nameCode/longName, /associateLicenses/issuingParty/nameCode/alternateID, /associateLicenses/issuingParty/nameCode/alternateID/idValue, /associateLicenses/issuingParty/nameCode/alternateID/schemeCode … (+485)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-licenses/{license-id}`
- Summary: License Details
- Schema file: `associateLicenses_schema_v02_00_rev004.json` (61,060 bytes)
- Top-level response groups (18): licenseID, licenseNameCode, licenseDescription, categoryCode, statusCode, issuingParty, firstIssueDate, lastIssueDate, expirationDate, endorsements, restrictions, employerPaidAmount, comments, renewalComments, violations, customFieldGroup, itemID, links
- Recommendation: **SPLIT — 18 top-level groups, 61,060B schema**

### GET `/talent/v2/associates/{aoid}/associate-licenses/{license-id}/meta`
- Summary: License Details Meta
- Schema file: `associateLicenses_meta_schema_v02_00_rev004.json` (129,477 bytes)
- Top-level response groups (515): queryCriteria, /associateLicenses, /associateLicenses/licenseID, /associateLicenses/licenseID/idValue, /associateLicenses/licenseID/schemeCode, /associateLicenses/licenseID/schemeCode/codeValue, /associateLicenses/licenseID/schemeCode/shortName, /associateLicenses/licenseID/schemeCode/longName, /associateLicenses/licenseNameCode, /associateLicenses/licenseNameCode/codeValue, /associateLicenses/licenseNameCode/shortName, /associateLicenses/licenseNameCode/longName, /associateLicenses/licenseDescription, /associateLicenses/categoryCode, /associateLicenses/categoryCode/codeValue, /associateLicenses/categoryCode/shortName, /associateLicenses/categoryCode/longName, /associateLicenses/statusCode, /associateLicenses/statusCode/codeValue, /associateLicenses/statusCode/shortName, /associateLicenses/statusCode/longName, /associateLicenses/statusCode/effectiveDate, /associateLicenses/issuingParty, /associateLicenses/issuingParty/nameCode, /associateLicenses/issuingParty/nameCode/codeValue, /associateLicenses/issuingParty/nameCode/shortName, /associateLicenses/issuingParty/nameCode/longName, /associateLicenses/issuingParty/nameCode/alternateID, /associateLicenses/issuingParty/nameCode/alternateID/idValue, /associateLicenses/issuingParty/nameCode/alternateID/schemeCode … (+485)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
