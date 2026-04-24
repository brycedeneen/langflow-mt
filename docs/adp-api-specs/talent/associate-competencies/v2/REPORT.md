# Associate Competencies (v2)

- Domain: `talent`
- Slug: `associate-competencies`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-competencies/v2/associate-competencies-swagger_v2-merged.json
- Status: **ok**

## Operations (9)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/talent/v1/associate.ksaoc.competency.add` | 76,754 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.competency.add/meta` | 84,494 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.competency.change` | 77,193 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.competency.change/meta` | 84,721 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.competency.remove` | 71,782 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.competency.remove/meta` | 56,335 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-competencies` | 49,517 | `competencyNameCode`, `competencyDescription`, `categoryCode`, `acquisitionDate`, `lastUsedDate`, `lastUsedYear`, `experienceDuration`, `hasCompetencyIndicator` *(+9)* | SPLIT — 17 top-level groups, 49,517B schema |
| GET | `/talent/v2/associates/{aoid}/associate-competencies/meta` | 103,953 | `queryCriteria`, `/associateCompetencies`, `/associateCompetencies/competencyNameCode`, `/associateCompetencies/competencyNameCode/codeValue`, `/associateCompetencies/competencyNameCode/shortName`, `/associateCompetencies/competencyNameCode/longName`, `/associateCompetencies/competencyDescription`, `/associateCompetencies/categoryCode` *(+174)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-competencies/{competency-id}` | 49,517 | `competencyNameCode`, `competencyDescription`, `categoryCode`, `acquisitionDate`, `lastUsedDate`, `lastUsedYear`, `experienceDuration`, `hasCompetencyIndicator` *(+9)* | SPLIT — 17 top-level groups, 49,517B schema |

## Per-operation detail

### POST `/events/talent/v1/associate.ksaoc.competency.add`
- Summary: Add Competency
- Schema file: `events_talent.associate.ksaoc.competency.add_schema_v01_00_rev007.json` (76,754 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.competency.add/meta`
- Summary: Add Competency Meta
- Schema file: `events_talent.associate.ksaoc.competency.add_meta_schema_v01_00_rev007.json` (84,494 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.competency.change`
- Summary: Change Compentency
- Schema file: `events_talent.associate.ksaoc.competency.change_schema_v01_00_rev007.json` (77,193 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.competency.change/meta`
- Summary: Change Compentency Meta
- Schema file: `events_talent.associate.ksaoc.competency.change_meta_schema_v01_00_rev007.json` (84,721 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.competency.remove`
- Summary: Remove Competency
- Schema file: `events_talent.associate.ksaoc.competency.remove_schema_v01_00_rev007.json` (71,782 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.competency.remove/meta`
- Summary: Remove Competency Meta
- Schema file: `events_talent.associate.ksaoc.competency.remove_meta_schema_v01_00_rev007.json` (56,335 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-competencies`
- Summary: Competencies
- Schema file: `associateCompetencies_schema_v02_00_rev004.json` (49,517 bytes)
- Top-level response groups (17): competencyNameCode, competencyDescription, categoryCode, acquisitionDate, lastUsedDate, lastUsedYear, experienceDuration, hasCompetencyIndicator, testRequiredIndicator, certificationRequiredIndicator, autoCalculateExperienceIndicator, comments, selfAssessedProficiencyScore, competencyDimensions, customFieldGroup, itemID, links
- Recommendation: **SPLIT — 17 top-level groups, 49,517B schema**

### GET `/talent/v2/associates/{aoid}/associate-competencies/meta`
- Summary: Competency Meta
- Schema file: `associateCompetencies_meta_schema_v02_00_rev004.json` (103,953 bytes)
- Top-level response groups (182): queryCriteria, /associateCompetencies, /associateCompetencies/competencyNameCode, /associateCompetencies/competencyNameCode/codeValue, /associateCompetencies/competencyNameCode/shortName, /associateCompetencies/competencyNameCode/longName, /associateCompetencies/competencyDescription, /associateCompetencies/categoryCode, /associateCompetencies/categoryCode/codeValue, /associateCompetencies/categoryCode/shortName, /associateCompetencies/categoryCode/longName, /associateCompetencies/acquisitionDate, /associateCompetencies/lastUsedDate, /associateCompetencies/lastUsedYear, /associateCompetencies/experienceDuration, /associateCompetencies/hasCompetencyIndicator, /associateCompetencies/testRequiredIndicator, /associateCompetencies/certificationRequiredIndicator, /associateCompetencies/autoCalculateExperienceIndicator, /associateCompetencies/comments, /associateCompetencies/selfAssessedProficiencyScore, /associateCompetencies/selfAssessedProficiencyScore/unitCode, /associateCompetencies/selfAssessedProficiencyScore/unitCode/codeValue, /associateCompetencies/selfAssessedProficiencyScore/unitCode/shortName, /associateCompetencies/selfAssessedProficiencyScore/unitCode/longName, /associateCompetencies/selfAssessedProficiencyScore/scoreValue, /associateCompetencies/selfAssessedProficiencyScore/scoreCode, /associateCompetencies/selfAssessedProficiencyScore/scoreCode/codeValue, /associateCompetencies/selfAssessedProficiencyScore/scoreCode/shortName, /associateCompetencies/selfAssessedProficiencyScore/scoreCode/longName … (+152)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-competencies/{competency-id}`
- Summary: Competency Details
- Schema file: `associateCompetencies_schema_v02_00_rev004.json` (49,517 bytes)
- Top-level response groups (17): competencyNameCode, competencyDescription, categoryCode, acquisitionDate, lastUsedDate, lastUsedYear, experienceDuration, hasCompetencyIndicator, testRequiredIndicator, certificationRequiredIndicator, autoCalculateExperienceIndicator, comments, selfAssessedProficiencyScore, competencyDimensions, customFieldGroup, itemID, links
- Recommendation: **SPLIT — 17 top-level groups, 49,517B schema**
