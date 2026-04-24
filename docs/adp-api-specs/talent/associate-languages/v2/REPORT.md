# Associate Languages (v2)

- Domain: `talent`
- Slug: `associate-languages`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-languages/v2/associate-languages-swagger_v2-merged.json
- Status: **ok**

## Operations (10)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/talent/v1/associate.ksaoc.language.add` | 78,846 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.language.add/meta` | 83,816 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.language.change` | 79,322 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.language.change/meta` | 84,039 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.language.remove` | 74,490 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.language.remove/meta` | 56,329 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-languages` | 50,851 | `languageCode`, `nativeLanguageIndicator`, `acquisitionDate`, `lastUsedDate`, `experienceDuration`, `hasCompetencyIndicator`, `selfAssessedProficiencyScore`, `competencyDimensions` *(+4)* | SPLIT — 12 top-level groups, 50,851B schema |
| GET | `/talent/v2/associates/{aoid}/associate-languages/meta` | 59,982 | `queryCriteria`, `/associateLanguages`, `/associateLanguages/languageCode`, `/associateLanguages/languageCode/codeValue`, `/associateLanguages/languageCode/shortName`, `/associateLanguages/languageCode/longName`, `/associateLanguages/languageCode/alternateID`, `/associateLanguages/languageCode/alternateID/idValue` *(+42)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-languages/{language-id}` | 50,851 | `languageCode`, `nativeLanguageIndicator`, `acquisitionDate`, `lastUsedDate`, `experienceDuration`, `hasCompetencyIndicator`, `selfAssessedProficiencyScore`, `competencyDimensions` *(+4)* | SPLIT — 12 top-level groups, 50,851B schema |
| GET | `/talent/v2/associates/{aoid}/associate-languages/{language-id}/meta` | 59,982 | `queryCriteria`, `/associateLanguages`, `/associateLanguages/languageCode`, `/associateLanguages/languageCode/codeValue`, `/associateLanguages/languageCode/shortName`, `/associateLanguages/languageCode/longName`, `/associateLanguages/languageCode/alternateID`, `/associateLanguages/languageCode/alternateID/idValue` *(+42)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/talent/v1/associate.ksaoc.language.add`
- Summary: Add Language
- Schema file: `events_talent.associate.ksaoc.language.add_schema_v01_00_rev006.json` (78,846 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.language.add/meta`
- Summary: Add Language Meta
- Schema file: `events_talent.associate.ksaoc.language.add_meta_schema_v01_00_rev006.json` (83,816 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.language.change`
- Summary: Change Language
- Schema file: `events_talent.associate.ksaoc.language.change_schema_v01_00_rev006.json` (79,322 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.language.change/meta`
- Summary: Change Language Meta
- Schema file: `events_talent.associate.ksaoc.language.change_meta_schema_v01_00_rev006.json` (84,039 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.language.remove`
- Summary: Remove Language
- Schema file: `events_talent.associate.ksaoc.language.remove_schema_v01_00_rev006.json` (74,490 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.language.remove/meta`
- Summary: Remove Language Meta
- Schema file: `events_talent.associate.ksaoc.language.remove_meta_schema_v01_00_rev006.json` (56,329 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-languages`
- Summary: Languages
- Schema file: `associateLanguages_schema_v02_00_rev003.json` (50,851 bytes)
- Top-level response groups (12): languageCode, nativeLanguageIndicator, acquisitionDate, lastUsedDate, experienceDuration, hasCompetencyIndicator, selfAssessedProficiencyScore, competencyDimensions, customFieldGroup, itemID, personOID, links
- Recommendation: **SPLIT — 12 top-level groups, 50,851B schema**

### GET `/talent/v2/associates/{aoid}/associate-languages/meta`
- Summary: Language Meta
- Schema file: `associateLanguages_meta_schema_v02_00_rev003.json` (59,982 bytes)
- Top-level response groups (50): queryCriteria, /associateLanguages, /associateLanguages/languageCode, /associateLanguages/languageCode/codeValue, /associateLanguages/languageCode/shortName, /associateLanguages/languageCode/longName, /associateLanguages/languageCode/alternateID, /associateLanguages/languageCode/alternateID/idValue, /associateLanguages/nativeLanguageIndicator, /associateLanguages/acquisitionDate, /associateLanguages/lastUsedDate, /associateLanguages/experienceDuration, /associateLanguages/hasCompetencyIndicator, /associateLanguages/selfAssessedProficiencyScore, /associateLanguages/selfAssessedProficiencyScore/scoreCode, /associateLanguages/competencyDimensions, /associateLanguages/competencyDimensions/itemID, /associateLanguages/competencyDimensions/dimensionNameCode, /associateLanguages/competencyDimensions/dimensionNameCode/codeValue, /associateLanguages/competencyDimensions/dimensionNameCode/shortName, /associateLanguages/competencyDimensions/dimensionNameCode/longName, /associateLanguages/competencyDimensions/hasDimensionIndicator, /associateLanguages/competencyDimensions/selfAssessedProficiencyScore, /associateLanguages/competencyDimensions/selfAssessedProficiencyScore/scoreCode, /associateLanguages/customFieldGroup, /associateLanguages/customFieldGroup/amountFields, /associateLanguages/customFieldGroup/codeFields, /associateLanguages/customFieldGroup/multiCodeFields, /associateLanguages/customFieldGroup/dateFields, /associateLanguages/customFieldGroup/dateTimeFields … (+20)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-languages/{language-id}`
- Summary: Language Details
- Schema file: `associateLanguages_schema_v02_00_rev003.json` (50,851 bytes)
- Top-level response groups (12): languageCode, nativeLanguageIndicator, acquisitionDate, lastUsedDate, experienceDuration, hasCompetencyIndicator, selfAssessedProficiencyScore, competencyDimensions, customFieldGroup, itemID, personOID, links
- Recommendation: **SPLIT — 12 top-level groups, 50,851B schema**

### GET `/talent/v2/associates/{aoid}/associate-languages/{language-id}/meta`
- Summary: Language Details Meta
- Schema file: `associateLanguages_meta_schema_v02_00_rev003.json` (59,982 bytes)
- Top-level response groups (50): queryCriteria, /associateLanguages, /associateLanguages/languageCode, /associateLanguages/languageCode/codeValue, /associateLanguages/languageCode/shortName, /associateLanguages/languageCode/longName, /associateLanguages/languageCode/alternateID, /associateLanguages/languageCode/alternateID/idValue, /associateLanguages/nativeLanguageIndicator, /associateLanguages/acquisitionDate, /associateLanguages/lastUsedDate, /associateLanguages/experienceDuration, /associateLanguages/hasCompetencyIndicator, /associateLanguages/selfAssessedProficiencyScore, /associateLanguages/selfAssessedProficiencyScore/scoreCode, /associateLanguages/competencyDimensions, /associateLanguages/competencyDimensions/itemID, /associateLanguages/competencyDimensions/dimensionNameCode, /associateLanguages/competencyDimensions/dimensionNameCode/codeValue, /associateLanguages/competencyDimensions/dimensionNameCode/shortName, /associateLanguages/competencyDimensions/dimensionNameCode/longName, /associateLanguages/competencyDimensions/hasDimensionIndicator, /associateLanguages/competencyDimensions/selfAssessedProficiencyScore, /associateLanguages/competencyDimensions/selfAssessedProficiencyScore/scoreCode, /associateLanguages/customFieldGroup, /associateLanguages/customFieldGroup/amountFields, /associateLanguages/customFieldGroup/codeFields, /associateLanguages/customFieldGroup/multiCodeFields, /associateLanguages/customFieldGroup/dateFields, /associateLanguages/customFieldGroup/dateTimeFields … (+20)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
