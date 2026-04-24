# Associate Certifications (v2)

- Domain: `talent`
- Slug: `associate-certifications`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-certifications/v2/associate-certifications-swagger_v2-merged.json
- Status: **ok**

## Operations (9)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/talent/v1/associate.ksaoc.certification.add` | 84,423 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.certification.add/meta` | 99,545 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.certification.change` | 85,236 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.certification.change/meta` | 99,778 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.certification.remove` | 80,971 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.certification.remove/meta` | 61,192 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-certifications` | 58,262 | `certificationID`, `certificationNameCode`, `certificationDescription`, `categoryCode`, `statusCode`, `issuingParty`, `firstIssueDate`, `lastIssueDate` *(+8)* | SPLIT — 16 top-level groups, 58,262B schema |
| GET | `/talent/v2/associates/{aoid}/associate-certifications/meta` | 94,647 | `queryCriteria`, `/associateCertifications`, `/associateCertifications/certificationID`, `/associateCertifications/certificationID/idValue`, `/associateCertifications/certificationID/schemeCode`, `/associateCertifications/certificationID/schemeCode/codeValue`, `/associateCertifications/certificationID/schemeCode/shortName`, `/associateCertifications/certificationID/schemeCode/longName` *(+255)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-certifications/{certification-id}` | 58,262 | `certificationID`, `certificationNameCode`, `certificationDescription`, `categoryCode`, `statusCode`, `issuingParty`, `firstIssueDate`, `lastIssueDate` *(+8)* | SPLIT — 16 top-level groups, 58,262B schema |

## Per-operation detail

### POST `/events/talent/v1/associate.ksaoc.certification.add`
- Summary: Add Certification
- Schema file: `events_talent.associate.ksaoc.certification.add_schema_v01_00_rev006.json` (84,423 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.certification.add/meta`
- Summary: Add Certification Meta
- Schema file: `events_talent.associate.ksaoc.certification.add_meta_schema_v01_00_rev006.json` (99,545 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.certification.change`
- Summary: Change Certification
- Schema file: `events_talent.associate.ksaoc.certification.change_schema_v01_00_rev006.json` (85,236 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.certification.change/meta`
- Summary: Change Certification Meta
- Schema file: `events_talent.associate.ksaoc.certification.change_meta_schema_v01_00_rev006.json` (99,778 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.certification.remove`
- Summary: Remove Certification
- Schema file: `events_talent.associate.ksaoc.certification.remove_schema_v01_00_rev006.json` (80,971 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.certification.remove/meta`
- Summary: Remove Certification Meta
- Schema file: `events_talent.associate.ksaoc.certification.remove_meta_schema_v01_00_rev006.json` (61,192 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-certifications`
- Summary: Certifications
- Schema file: `associateCertifications_schema_v02_00_rev003.json` (58,262 bytes)
- Top-level response groups (16): certificationID, certificationNameCode, certificationDescription, categoryCode, statusCode, issuingParty, firstIssueDate, lastIssueDate, expirationDate, employerPaidAmount, comments, renewalComments, customFieldGroup, itemID, associateOID, links
- Recommendation: **SPLIT — 16 top-level groups, 58,262B schema**

### GET `/talent/v2/associates/{aoid}/associate-certifications/meta`
- Summary: Certification Meta
- Schema file: `associateCertifications_meta_schema_v02_00_rev003.json` (94,647 bytes)
- Top-level response groups (263): queryCriteria, /associateCertifications, /associateCertifications/certificationID, /associateCertifications/certificationID/idValue, /associateCertifications/certificationID/schemeCode, /associateCertifications/certificationID/schemeCode/codeValue, /associateCertifications/certificationID/schemeCode/shortName, /associateCertifications/certificationID/schemeCode/longName, /associateCertifications/certificationNameCode, /associateCertifications/certificationNameCode/codeValue, /associateCertifications/certificationNameCode/shortName, /associateCertifications/certificationNameCode/longName, /associateCertifications/certificationDescription, /associateCertifications/categoryCode, /associateCertifications/categoryCode/codeValue, /associateCertifications/categoryCode/shortName, /associateCertifications/categoryCode/longName, /associateCertifications/statusCode, /associateCertifications/statusCode/codeValue, /associateCertifications/statusCode/shortName, /associateCertifications/statusCode/longName, /associateCertifications/statusCode/effectiveDate, /associateCertifications/issuingParty, /associateCertifications/issuingParty/nameCode, /associateCertifications/issuingParty/nameCode/codeValue, /associateCertifications/issuingParty/nameCode/shortName, /associateCertifications/issuingParty/nameCode/longName, /associateCertifications/issuingParty/nameCode/alternateID, /associateCertifications/issuingParty/nameCode/alternateID/idValue, /associateCertifications/issuingParty/nameCode/alternateID/schemeCode … (+233)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-certifications/{certification-id}`
- Summary: Certification Details
- Schema file: `associateCertifications_schema_v02_00_rev003.json` (58,262 bytes)
- Top-level response groups (16): certificationID, certificationNameCode, certificationDescription, categoryCode, statusCode, issuingParty, firstIssueDate, lastIssueDate, expirationDate, employerPaidAmount, comments, renewalComments, customFieldGroup, itemID, associateOID, links
- Recommendation: **SPLIT — 16 top-level groups, 58,262B schema**
