# Us Tax Profiles (v2)

- Domain: `payroll`
- Slug: `us-tax-profiles`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/payroll/us-tax-profiles/v2/us-tax-profiles-swagger_v2-merged.json
- Status: **ok**

## Operations (4)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.add` | 85,542 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.add/meta` | 78,215 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.change` | 82,635 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.change/meta` | 78,686 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |

## Per-operation detail

### POST `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.add`
- Summary: US State Tax Profile - Add State Income Tax Instruction
- Schema file: `events_payroll.worker.usTaxProfile.stateIncomeTaxInstruction.add_schema_v02_00_rev001.json` (85,542 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.add/meta`
- Summary: US State Tax Profile - Add State Income Tax Instruction Meta
- Schema file: `events_payroll.worker.usTaxProfile.stateIncomeTaxInstruction.add_meta_schema_v02_00_rev001.json` (78,215 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.change`
- Summary: US State Tax Profile - Change State Income Tax Instruction
- Schema file: `events_payroll.worker.usTaxProfile.stateIncomeTaxInstruction.change_schema_v02_00_rev001.json` (82,635 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v2/us-tax-profile.state-income-tax-instruction.change/meta`
- Summary: US State Tax Profile - Change State Income Tax Instruction Meta
- Schema file: `events_payroll.worker.usTaxProfile.stateIncomeTaxInstruction.change_meta_schema_v02_00_rev001.json` (78,686 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**
