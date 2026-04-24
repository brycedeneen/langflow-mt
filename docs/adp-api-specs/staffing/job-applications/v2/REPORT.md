# Job Applications (v2)

- Domain: `staffing`
- Slug: `job-applications`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/staffing/job-applications/v2/job-applications-swagger_v2-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/staffing/v2/job-applications` | 252,130 | `applicationSubmittedDateTime`, `applicantReferralIndicator`, `applicantReferredBy`, `referralSourceCode`, `sourceCategoryCode`, `staffingVendorCode`, `requestedPayRate`, `attachments` *(+18)* | SPLIT — 26 top-level groups, 252,130B schema |
| GET | `/staffing/v2/job-applications/{job-application-id}` | 252,130 | `applicationSubmittedDateTime`, `applicantReferralIndicator`, `applicantReferredBy`, `referralSourceCode`, `sourceCategoryCode`, `staffingVendorCode`, `requestedPayRate`, `attachments` *(+18)* | SPLIT — 26 top-level groups, 252,130B schema |

## Per-operation detail

### GET `/staffing/v2/job-applications`
- Summary: Job Applications
- Schema file: `jobApplications_schema_v02_00_rev010.json` (252,130 bytes)
- Top-level response groups (26): applicationSubmittedDateTime, applicantReferralIndicator, applicantReferredBy, referralSourceCode, sourceCategoryCode, staffingVendorCode, requestedPayRate, attachments, itemID, _languageCode, jobRequisitionReference, jobOfferReference, applicationStatusCode, applicationSource, vendorCode, applicant, externalBackgroundScreening, externalAssessment, externalInterview, appliedLocations, attestations, questionnaire, comments, applicationContentLinks, actions, links
- Recommendation: **SPLIT — 26 top-level groups, 252,130B schema**

### GET `/staffing/v2/job-applications/{job-application-id}`
- Summary: Job Application
- Schema file: `jobApplications_schema_v02_00_rev010.json` (252,130 bytes)
- Top-level response groups (26): applicationSubmittedDateTime, applicantReferralIndicator, applicantReferredBy, referralSourceCode, sourceCategoryCode, staffingVendorCode, requestedPayRate, attachments, itemID, _languageCode, jobRequisitionReference, jobOfferReference, applicationStatusCode, applicationSource, vendorCode, applicant, externalBackgroundScreening, externalAssessment, externalInterview, appliedLocations, attestations, questionnaire, comments, applicationContentLinks, actions, links
- Recommendation: **SPLIT — 26 top-level groups, 252,130B schema**
