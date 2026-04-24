# Associate Memberships (v2)

- Domain: `talent`
- Slug: `associate-memberships`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/talent/associate-memberships/v2/associate-memberships-swagger_v2-merged.json
- Status: **ok**

## Operations (22)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/event-notifications/talent/v1/associate.ksaoc.membership.add` | 84,991 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/event-notifications/talent/v1/associate.ksaoc.membership.add.review` | 88,112 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/event-notifications/talent/v1/associate.ksaoc.membership.change` | 85,625 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/event-notifications/talent/v1/associate.ksaoc.membership.change.review` | 88,746 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/event-notifications/talent/v1/associate.ksaoc.membership.remove` | 82,299 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/event-notifications/talent/v1/associate.ksaoc.membership.remove.review` | 85,722 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/talent/v1/associate.ksaoc.membership.add` | 84,991 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/talent/v1/associate.ksaoc.membership.add.review` | 88,112 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.membership.add.review/meta` | 129,276 | `control` | single tool (meta discovery — rarely agent-facing) |
| GET | `/events/talent/v1/associate.ksaoc.membership.add/meta` | 110,718 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.membership.change` | 85,625 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/talent/v1/associate.ksaoc.membership.change.review` | 88,746 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.membership.change.review/meta` | 129,504 | `control` | single tool (meta discovery — rarely agent-facing) |
| GET | `/events/talent/v1/associate.ksaoc.membership.change/meta` | 110,946 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/talent/v1/associate.ksaoc.membership.remove` | 82,299 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| POST | `/events/talent/v1/associate.ksaoc.membership.remove.review` | 85,722 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/talent/v1/associate.ksaoc.membership.remove.review/meta` | 92,386 | `control` | single tool (meta discovery — rarely agent-facing) |
| GET | `/events/talent/v1/associate.ksaoc.membership.remove/meta` | 61,261 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-memberships` | 58,992 | `membershipID`, `membershipOrganization`, `typeCode`, `memberTitle`, `memberSinceDate`, `expirationDate`, `employerPaidAmount`, `issuingParty` *(+5)* | SPLIT — 13 top-level groups, 58,992B schema |
| GET | `/talent/v2/associates/{aoid}/associate-memberships/meta` | 104,460 | `queryCriteria`, `/associateMemberships`, `/associateMemberships/membershipID`, `/associateMemberships/membershipID/idValue`, `/associateMemberships/membershipID/schemeCode`, `/associateMemberships/membershipID/schemeCode/codeValue`, `/associateMemberships/membershipID/schemeCode/shortName`, `/associateMemberships/membershipID/schemeCode/longName` *(+326)* | single tool (meta discovery — rarely agent-facing) |
| GET | `/talent/v2/associates/{aoid}/associate-memberships/{membership-id}` | 58,992 | `membershipID`, `membershipOrganization`, `typeCode`, `memberTitle`, `memberSinceDate`, `expirationDate`, `employerPaidAmount`, `issuingParty` *(+5)* | SPLIT — 13 top-level groups, 58,992B schema |
| GET | `/talent/v2/associates/{aoid}/associate-memberships/{membership-id}/meta` | 104,460 | `queryCriteria`, `/associateMemberships`, `/associateMemberships/membershipID`, `/associateMemberships/membershipID/idValue`, `/associateMemberships/membershipID/schemeCode`, `/associateMemberships/membershipID/schemeCode/codeValue`, `/associateMemberships/membershipID/schemeCode/shortName`, `/associateMemberships/membershipID/schemeCode/longName` *(+326)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/event-notifications/talent/v1/associate.ksaoc.membership.add`
- Summary: Add Membership Notification
- Schema file: `events_talent.associate.ksaoc.membership.add_schema_v01_00_rev006.json` (84,991 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/event-notifications/talent/v1/associate.ksaoc.membership.add.review`
- Summary: Review Add Membership Notification
- Schema file: `events_talent.associate.ksaoc.membership.add.review_schema_v01_00_rev001.json` (88,112 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/event-notifications/talent/v1/associate.ksaoc.membership.change`
- Summary: Change Membership Notification
- Schema file: `events_talent.associate.ksaoc.membership.change_schema_v01_00_rev006.json` (85,625 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/event-notifications/talent/v1/associate.ksaoc.membership.change.review`
- Summary: Review Change Membership Notification
- Schema file: `events_talent.associate.ksaoc.membership.change.review_schema_v01_00_rev001.json` (88,746 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/event-notifications/talent/v1/associate.ksaoc.membership.remove`
- Summary: Remove Membership Notification
- Schema file: `events_talent.associate.ksaoc.membership.remove_schema_v01_00_rev006.json` (82,299 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/event-notifications/talent/v1/associate.ksaoc.membership.remove.review`
- Summary: Review Remove Membership Notification
- Schema file: `events_talent.associate.ksaoc.membership.remove.review_schema_v01_00_rev001.json` (85,722 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/talent/v1/associate.ksaoc.membership.add`
- Summary: Add Membership
- Schema file: `events_talent.associate.ksaoc.membership.add_schema_v01_00_rev006.json` (84,991 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/talent/v1/associate.ksaoc.membership.add.review`
- Summary: Review Add Membership
- Schema file: `events_talent.associate.ksaoc.membership.add.review_schema_v01_00_rev001.json` (88,112 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.membership.add.review/meta`
- Summary: Review Add Membership Meta
- Schema file: `events_talent.associate.ksaoc.membership.add.review_meta_schema_v01_00_rev001.json` (129,276 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/events/talent/v1/associate.ksaoc.membership.add/meta`
- Summary: Add Membership Meta
- Schema file: `events_talent.associate.ksaoc.membership.add_meta_schema_v01_00_rev006.json` (110,718 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.membership.change`
- Summary: Change Membership
- Schema file: `events_talent.associate.ksaoc.membership.change_schema_v01_00_rev006.json` (85,625 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/talent/v1/associate.ksaoc.membership.change.review`
- Summary: Review Change Membership
- Schema file: `events_talent.associate.ksaoc.membership.change.review_schema_v01_00_rev001.json` (88,746 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.membership.change.review/meta`
- Summary: Review Change Membership Meta
- Schema file: `events_talent.associate.ksaoc.membership.change.review_meta_schema_v01_00_rev001.json` (129,504 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/events/talent/v1/associate.ksaoc.membership.change/meta`
- Summary: Change Membership Meta
- Schema file: `events_talent.associate.ksaoc.membership.change_meta_schema_v01_00_rev006.json` (110,946 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/talent/v1/associate.ksaoc.membership.remove`
- Summary: Remove Membership
- Schema file: `events_talent.associate.ksaoc.membership.remove_schema_v01_00_rev006.json` (82,299 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### POST `/events/talent/v1/associate.ksaoc.membership.remove.review`
- Summary: Review Remove Membership
- Schema file: `events_talent.associate.ksaoc.membership.remove.review_schema_v01_00_rev001.json` (85,722 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/talent/v1/associate.ksaoc.membership.remove.review/meta`
- Summary: Review Remove Membership Meta
- Schema file: `events_talent.associate.ksaoc.membership.remove.review_meta_schema_v01_00_rev001.json` (92,386 bytes)
- Top-level response groups (1): control
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/events/talent/v1/associate.ksaoc.membership.remove/meta`
- Summary: Remove Membership Meta
- Schema file: `events_talent.associate.ksaoc.membership.remove_meta_schema_v01_00_rev006.json` (61,261 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-memberships`
- Summary: Memberships
- Schema file: `associateMemberships_schema_v02_00_rev003.json` (58,992 bytes)
- Top-level response groups (13): membershipID, membershipOrganization, typeCode, memberTitle, memberSinceDate, expirationDate, employerPaidAmount, issuingParty, comments, customFieldGroup, itemID, personOID, links
- Recommendation: **SPLIT — 13 top-level groups, 58,992B schema**

### GET `/talent/v2/associates/{aoid}/associate-memberships/meta`
- Summary: Membership Meta
- Schema file: `associateMemberships_meta_schema_v02_00_rev003.json` (104,460 bytes)
- Top-level response groups (334): queryCriteria, /associateMemberships, /associateMemberships/membershipID, /associateMemberships/membershipID/idValue, /associateMemberships/membershipID/schemeCode, /associateMemberships/membershipID/schemeCode/codeValue, /associateMemberships/membershipID/schemeCode/shortName, /associateMemberships/membershipID/schemeCode/longName, /associateMemberships/membershipOrganization, /associateMemberships/membershipOrganization/nameCode, /associateMemberships/membershipOrganization/nameCode/codeValue, /associateMemberships/membershipOrganization/nameCode/shortName, /associateMemberships/membershipOrganization/nameCode/longName, /associateMemberships/membershipOrganization/nameCode/alternateID, /associateMemberships/membershipOrganization/nameCode/alternateID/idValue, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode/codeValue, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode/shortName, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode/longName, /associateMemberships/membershipOrganization/address, /associateMemberships/membershipOrganization/address/nameCode, /associateMemberships/membershipOrganization/address/nameCode/codeValue, /associateMemberships/membershipOrganization/address/nameCode/shortName, /associateMemberships/membershipOrganization/address/nameCode/longName, /associateMemberships/membershipOrganization/address/attentionOfName, /associateMemberships/membershipOrganization/address/careOfName, /associateMemberships/membershipOrganization/address/lineOne, /associateMemberships/membershipOrganization/address/lineTwo, /associateMemberships/membershipOrganization/address/lineThree, /associateMemberships/membershipOrganization/address/cityName … (+304)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/talent/v2/associates/{aoid}/associate-memberships/{membership-id}`
- Summary: Membership Details
- Schema file: `associateMemberships_schema_v02_00_rev003.json` (58,992 bytes)
- Top-level response groups (13): membershipID, membershipOrganization, typeCode, memberTitle, memberSinceDate, expirationDate, employerPaidAmount, issuingParty, comments, customFieldGroup, itemID, personOID, links
- Recommendation: **SPLIT — 13 top-level groups, 58,992B schema**

### GET `/talent/v2/associates/{aoid}/associate-memberships/{membership-id}/meta`
- Summary: Membership Details Meta
- Schema file: `associateMemberships_meta_schema_v02_00_rev003.json` (104,460 bytes)
- Top-level response groups (334): queryCriteria, /associateMemberships, /associateMemberships/membershipID, /associateMemberships/membershipID/idValue, /associateMemberships/membershipID/schemeCode, /associateMemberships/membershipID/schemeCode/codeValue, /associateMemberships/membershipID/schemeCode/shortName, /associateMemberships/membershipID/schemeCode/longName, /associateMemberships/membershipOrganization, /associateMemberships/membershipOrganization/nameCode, /associateMemberships/membershipOrganization/nameCode/codeValue, /associateMemberships/membershipOrganization/nameCode/shortName, /associateMemberships/membershipOrganization/nameCode/longName, /associateMemberships/membershipOrganization/nameCode/alternateID, /associateMemberships/membershipOrganization/nameCode/alternateID/idValue, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode/codeValue, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode/shortName, /associateMemberships/membershipOrganization/nameCode/alternateID/schemeCode/longName, /associateMemberships/membershipOrganization/address, /associateMemberships/membershipOrganization/address/nameCode, /associateMemberships/membershipOrganization/address/nameCode/codeValue, /associateMemberships/membershipOrganization/address/nameCode/shortName, /associateMemberships/membershipOrganization/address/nameCode/longName, /associateMemberships/membershipOrganization/address/attentionOfName, /associateMemberships/membershipOrganization/address/careOfName, /associateMemberships/membershipOrganization/address/lineOne, /associateMemberships/membershipOrganization/address/lineTwo, /associateMemberships/membershipOrganization/address/lineThree, /associateMemberships/membershipOrganization/address/cityName … (+304)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
