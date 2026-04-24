# Applicant Onboarding (v2)

- Domain: `hcm`
- Slug: `applicant-onboarding`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/hcm/applicant-onboarding/v2/applicant-onboarding-swagger_v2-merged.json
- Status: **ok**

## Operations (2)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/hcm/v2/applicant.onboard` | 25,215 | `alternateIDs`, `_confirmMessage`, `_meta` | keep whole (mutation requires full body) |
| GET | `/hcm/v2/applicant.onboard/meta` | 670,405 | `queryCriteria`, `/applicantOnboarding`, `/applicantOnboarding/onboardingID`, `/applicantOnboarding/onboardingTemplateCode`, `/applicantOnboarding/onboardingTemplateCode/code`, `/applicantOnboarding/onboardingTemplateCode/name`, `/applicantOnboarding/countryCode`, `/applicantOnboarding/onboardingExperienceCode` *(+3738)* | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/hcm/v2/applicant.onboard`
- Summary: Initiate New Applicant Onboarding
- Schema file: `applicant-onboarding-response-schema_v02.json` (25,215 bytes)
- Top-level response groups (3): alternateIDs, _confirmMessage, _meta
- Recommendation: **keep whole (mutation requires full body)**

### GET `/hcm/v2/applicant.onboard/meta`
- Summary: Initiate New Applicant Onboarding Metadata
- Schema file: `applicant-onboarding-meta-schema_v02.json` (670,405 bytes)
- Top-level response groups (3746): queryCriteria, /applicantOnboarding, /applicantOnboarding/onboardingID, /applicantOnboarding/onboardingTemplateCode, /applicantOnboarding/onboardingTemplateCode/code, /applicantOnboarding/onboardingTemplateCode/name, /applicantOnboarding/countryCode, /applicantOnboarding/onboardingExperienceCode, /applicantOnboarding/onboardingExperienceCode/code, /applicantOnboarding/onboardingExperienceCode/name, /applicantOnboarding/onboardingChecklists, /applicantOnboarding/onboardingChecklists/checklistCode, /applicantOnboarding/onboardingChecklists/checklistCode/code, /applicantOnboarding/onboardingChecklists/checklistCode/name, /applicantOnboarding/onboardingChecklists/accessGroup, /applicantOnboarding/onboardingChecklists/accessGroup/groupCode, /applicantOnboarding/onboardingChecklists/accessGroup/groupCode/code, /applicantOnboarding/onboardingChecklists/accessGroup/groupCode/name, /applicantOnboarding/onboardingChecklists/accessGroup/groupMember, /applicantOnboarding/onboardingChecklists/accessGroup/groupMember/associateOID, /applicantOnboarding/onboardingChecklists/accessGroup/groupMember/formattedName, /applicantOnboarding/onboardingChecklists/accessGroup/anyMemberIndicator, /applicantOnboarding/employmentEligibilityOptionCode, /applicantOnboarding/employmentEligibilityOptionCode/code, /applicantOnboarding/employmentEligibilityOptionCode/name, /applicantOnboarding/preHireIndicator, /applicantOnboarding/onboardingStatus, /applicantOnboarding/onboardingStatus/statusCode, /applicantOnboarding/onboardingStatus/statusCode/code, /applicantOnboarding/onboardingStatus/statusCode/name … (+3716)
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
