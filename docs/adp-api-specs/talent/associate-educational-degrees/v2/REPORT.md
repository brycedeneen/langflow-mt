# Associate Educational Degrees (v2)

- Domain: `talent`
- Slug: `associate-educational-degrees`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-educational-degrees/v2/associate-educational-degrees-swagger_v2-merged.json
- Status: **ok**

## Operations (9)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/talent/v1/associate.ksaoc.educational-degree.add` | 133,892 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.educational-degree.add/meta` | 142,100 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.educational-degree.change` | 134,387 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.educational-degree.change/meta` | 142,340 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.educational-degree.remove` | 113,251 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.educational-degree.remove/meta` | 61,309 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-educational-degrees` | 90,839 | `nameCode`, `typeCode`, `statusCode`, `startDate`, `expectedCompletionDate`, `actualCompletionDate`, `completionDuration`, `issueDate` *(+17)* | SPLIT — 25 top-level groups, 90,839B schema |
| GET | `/talent/v2/associates/{aoid}/associate-educational-degrees/meta` | 68,294 | `queryCriteria`, `/associateEducationalDegrees`, `/associateEducationalDegrees/nameCode`, `/associateEducationalDegrees/nameCode/codeValue`, `/associateEducationalDegrees/nameCode/shortName`, `/associateEducationalDegrees/nameCode/longName`, `/associateEducationalDegrees/nameCode/alternateID`, `/associateEducationalDegrees/nameCode/alternateID/idValue` *(+102)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-educational-degrees/{educational-degree-id}` | 90,839 | `nameCode`, `typeCode`, `statusCode`, `startDate`, `expectedCompletionDate`, `actualCompletionDate`, `completionDuration`, `issueDate` *(+17)* | SPLIT — 25 top-level groups, 90,839B schema |

## Per-operation detail

### POST `/events/talent/v1/associate.ksaoc.educational-degree.add`
- Summary: Add Educational Degree
- Schema file: `events_talent.associate.ksaoc.educationalDegree.add_schema_v01_00_rev008.json` (133,892 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.educational-degree.add/meta`
- Summary: Add Educational Degree Meta
- Schema file: `events_talent.associate.ksaoc.educationalDegree.add_meta_schema_v01_00_rev008.json` (142,100 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.educational-degree.change`
- Summary: Change Educational Degree
- Schema file: `events_talent.associate.ksaoc.educationalDegree.change_schema_v01_00_rev008.json` (134,387 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.educational-degree.change/meta`
- Summary: Change Educational Degree Meta
- Schema file: `events_talent.associate.ksaoc.educationalDegree.change_meta_schema_v01_00_rev008.json` (142,340 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.educational-degree.remove`
- Summary: Remove Educational Degree
- Schema file: `events_talent.associate.ksaoc.educationalDegree.remove_schema_v01_00_rev008.json` (113,251 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.educational-degree.remove/meta`
- Summary: Remove Educational Degree Meta
- Schema file: `events_talent.associate.ksaoc.educationalDegree.remove_meta_schema_v01_00_rev008.json` (61,309 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-educational-degrees`
- Summary: Educational Degrees
- Schema file: `associateEducationalDegrees_schema_v02_00_rev004.json` (90,839 bytes)
- Top-level response groups (25): nameCode, typeCode, statusCode, startDate, expectedCompletionDate, actualCompletionDate, completionDuration, issueDate, majorProgramNameCodes, secondaryMajorProgramNameCodes, minorProgramNameCodes, honorsProgramNameCodes, educationalInstitutionAttendances, academicCreditTypeCode, academicCreditsCompleted, academicScore, verificationDate, employerPaidAmount, comments, customFieldGroup, issuedDegreeIdentifier, itemID, personOID, attachments, links
- Recommendation: **SPLIT — 25 top-level groups, 90,839B schema**

### GET `/talent/v2/associates/{aoid}/associate-educational-degrees/meta`
- Summary: Educational Degree Meta
- Schema file: `associateEducationalDegrees_meta_schema_v02_00_rev004.json` (68,294 bytes)
- Top-level response groups (110): queryCriteria, /associateEducationalDegrees, /associateEducationalDegrees/nameCode, /associateEducationalDegrees/nameCode/codeValue, /associateEducationalDegrees/nameCode/shortName, /associateEducationalDegrees/nameCode/longName, /associateEducationalDegrees/nameCode/alternateID, /associateEducationalDegrees/nameCode/alternateID/idValue, /associateEducationalDegrees/typeCode, /associateEducationalDegrees/typeCode/codeValue, /associateEducationalDegrees/typeCode/shortName, /associateEducationalDegrees/typeCode/longName, /associateEducationalDegrees/typeCode/alternateID, /associateEducationalDegrees/typeCode/alternateID/idValue, /associateEducationalDegrees/statusCode, /associateEducationalDegrees/startDate, /associateEducationalDegrees/expectedCompletionDate, /associateEducationalDegrees/actualCompletionDate, /associateEducationalDegrees/completionDuration, /associateEducationalDegrees/issueDate, /associateEducationalDegrees/majorProgramNameCodes, /associateEducationalDegrees/majorProgramNameCodes/codeValue, /associateEducationalDegrees/majorProgramNameCodes/shortName, /associateEducationalDegrees/majorProgramNameCodes/longName, /associateEducationalDegrees/majorProgramNameCodes/alternateID, /associateEducationalDegrees/majorProgramNameCodes/alternateID/idValue, /associateEducationalDegrees/secondaryMajorProgramNameCodes, /associateEducationalDegrees/secondaryMajorProgramNameCodes/codeValue, /associateEducationalDegrees/secondaryMajorProgramNameCodes/shortName, /associateEducationalDegrees/secondaryMajorProgramNameCodes/longName … (+80)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-educational-degrees/{educational-degree-id}`
- Summary: Educational Degree Details
- Schema file: `associateEducationalDegrees_schema_v02_00_rev004.json` (90,839 bytes)
- Top-level response groups (25): nameCode, typeCode, statusCode, startDate, expectedCompletionDate, actualCompletionDate, completionDuration, issueDate, majorProgramNameCodes, secondaryMajorProgramNameCodes, minorProgramNameCodes, honorsProgramNameCodes, educationalInstitutionAttendances, academicCreditTypeCode, academicCreditsCompleted, academicScore, verificationDate, employerPaidAmount, comments, customFieldGroup, issuedDegreeIdentifier, itemID, personOID, attachments, links
- Recommendation: **SPLIT — 25 top-level groups, 90,839B schema**
