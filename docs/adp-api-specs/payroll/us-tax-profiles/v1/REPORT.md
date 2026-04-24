# Us Tax Profiles (v1)

- Domain: `payroll`
- Slug: `us-tax-profiles`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/payroll/us-tax-profiles/v1/us-tax-profiles-swagger_v1-merged.json
- Status: **ok**

## Operations (11)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/payroll/v1/us-tax-profile.federal-income-tax-instruction.change` | 88,711 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v1/us-tax-profile.federal-income-tax-instruction.change/meta` | 56,722 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.add` | 69,401 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.add/meta` | 51,021 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.change` | 69,739 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.change/meta` | 51,701 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.remove` | 62,881 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.remove/meta` | 31,028 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/payroll/v1/workers/{aoid}/us-tax-profiles` | 64,338 | `payrollRegionCode`, `payrollGroupCode`, `payrollFileNumber`, `itemID`, `usFederalTaxInstruction`, `usStateTaxInstructions`, `usLocalTaxInstructions`, `links` | SPLIT — 8 top-level groups, 64,338B schema |
| GET | `/payroll/v1/workers/{aoid}/us-tax-profiles/{us-tax-profile-id}/local` | 39,072 | `payrollRegionCode`, `payrollGroupCode`, `payrollFileNumber`, `usLocalTaxInstructions`, `links` | split-maybe — 39,072B schema |
| GET | `/payroll/v1/workers/{aoid}/us-tax-profiles/{us-tax-profile-id}/state` | 46,022 | `payrollRegionCode`, `payrollGroupCode`, `payrollFileNumber`, `usStateTaxInstructions`, `links` | split-maybe — 46,022B schema |

## Per-operation detail

### POST `/events/payroll/v1/us-tax-profile.federal-income-tax-instruction.change`
- Summary: US Federal Tax Profile - Change Federal Income Tax Instruction
- Schema file: `events_payroll.worker.usTaxProfile.federalIncomeTaxInstruction.change_schema_v01_00_rev002.json` (88,711 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v1/us-tax-profile.federal-income-tax-instruction.change/meta`
- Summary: US Federal Tax Profile - Change Federal Income Tax Instruction Meta
- Schema file: `events_payroll.worker.usTaxProfile.federalIncomeTaxInstruction.change_meta_schema_v01_00_rev002.json` (56,722 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.add`
- Summary: US Local Tax Profile - Add Local Income Tax Instruction
- Schema file: `events_payroll.worker.usTaxProfile.localIncomeTaxInstruction.add_schema_v01_00_rev001.json` (69,401 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.add/meta`
- Summary: US Local Tax Profile - Add Local Income Tax Instruction Meta
- Schema file: `events_payroll.worker.usTaxProfile.localIncomeTaxInstruction.add_meta_schema_v01_00_rev001.json` (51,021 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.change`
- Summary: US Local Tax Profile - Change Local Income Tax Instruction
- Schema file: `events_payroll.worker.usTaxProfile.localIncomeTaxInstruction.change_schema_v01_00_rev001.json` (69,739 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.change/meta`
- Summary: US Local Tax Profile - Change Local Income Tax Instruction Meta
- Schema file: `events_payroll.worker.usTaxProfile.localIncomeTaxInstruction.change_meta_schema_v01_00_rev001.json` (51,701 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.remove`
- Summary: US Local Tax Profile - Remove Local Income Tax Instruction
- Schema file: `events_payroll.worker.usTaxProfile.localIncomeTaxInstruction.remove_schema_v01_00_rev001.json` (62,881 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v1/us-tax-profile.local-income-tax-instruction.remove/meta`
- Summary: US Local Tax Profile - Remove Local Income Tax Instruction Meta
- Schema file: `events_payroll.worker.usTaxProfile.localIncomeTaxInstruction.remove_meta_schema_v01_00_rev001.json` (31,028 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/payroll/v1/workers/{aoid}/us-tax-profiles`
- Summary: US Tax Profiles
- Schema file: `usTaxProfiles_schema_v01_00_rev006.json` (64,338 bytes)
- Top-level response groups (8): payrollRegionCode, payrollGroupCode, payrollFileNumber, itemID, usFederalTaxInstruction, usStateTaxInstructions, usLocalTaxInstructions, links
- Recommendation: **SPLIT — 8 top-level groups, 64,338B schema**

### GET `/payroll/v1/workers/{aoid}/us-tax-profiles/{us-tax-profile-id}/local`
- Summary: US Local Tax Profile Details
- Schema file: `usLocalTaxProfile_schema_v01_00_rev006.json` (39,072 bytes)
- Top-level response groups (5): payrollRegionCode, payrollGroupCode, payrollFileNumber, usLocalTaxInstructions, links
- Recommendation: **split-maybe — 39,072B schema**

### GET `/payroll/v1/workers/{aoid}/us-tax-profiles/{us-tax-profile-id}/state`
- Summary: US State Tax Profile Details
- Schema file: `usStateTaxProfile_schema_v01_00_rev006.json` (46,022 bytes)
- Top-level response groups (5): payrollRegionCode, payrollGroupCode, payrollFileNumber, usStateTaxInstructions, links
- Recommendation: **split-maybe — 46,022B schema**
