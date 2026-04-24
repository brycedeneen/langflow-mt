# Dependents (v1)

- Domain: `benefits`
- Slug: `dependents`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/benefits/dependents/v1/dependents-swagger_v1-merged.json
- Status: **ok**

## Operations (1)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/benefits/v1/associates/{aoid}/dependents` | 102,052 | `associateOID`, `relationshipTypeCode`, `classificationCode`, `person`, `benefitEligibilityPeriod`, `legalSeparationDate`, `itemID`, `evidenceDueDate` *(+4)* | SPLIT — 12 top-level groups, 102,052B schema |

## Per-operation detail

### GET `/benefits/v1/associates/{aoid}/dependents`
- Summary: Collection of Dependents
- Schema file: `dependents_schema_v01_00_rev006.json` (102,052 bytes)
- Top-level response groups (12): associateOID, relationshipTypeCode, classificationCode, person, benefitEligibilityPeriod, legalSeparationDate, itemID, evidenceDueDate, evidenceAdministrativeEndDate, submittalEndDate, customFieldGroup, links
- Recommendation: **SPLIT — 12 top-level groups, 102,052B schema**
