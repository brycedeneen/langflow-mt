# Worker Payroll Instructions (v1)

- Domain: `payroll`
- Slug: `worker-payroll-instructions`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/payroll/worker-payroll-instructions/v1/worker-payroll-instructions-swagger_v1-merged.json
- Status: **ok**

## Operations (8)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| POST | `/events/payroll/v2/worker-general-deduction-instruction.change` | 72,772 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v2/worker-general-deduction-instruction.change/meta` | 83,182 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/payroll/v2/worker-general-deduction-instruction.start` | 70,853 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v2/worker-general-deduction-instruction.start/meta` | 82,279 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| POST | `/events/payroll/v2/worker-general-deduction-instruction.stop` | 67,810 | `eventID`, `serviceCategoryCode`, `eventNameCode`, `eventTitle`, `eventSubTitle`, `eventReasonCode`, `eventStatusCode`, `priorityCode` *(+13)* | keep whole (mutation requires full body) |
| GET | `/events/payroll/v2/worker-general-deduction-instruction.stop/meta` | 63,542 | `/serviceCategoryCode/codeValue`, `/eventNameCode/codeValue`, `queryCriteria`, `/data/eventContext`, `/data/transforms` | single tool (meta discovery — rarely agent-facing) |
| GET | `/payroll/v1/workers/{aoid}/payroll-instructions` | 131,833 | `payrollRegionCode`, `payrollGroupCode`, `payrollFileNumber`, `payrollProfileID`, `itemID`, `workAssignmentStatus`, `generalDeductionInstructions`, `garnishmentInstructions` *(+5)* | SPLIT — 13 top-level groups, 131,833B schema |
| GET | `/payroll/v1/workers/{aoid}/payroll-instructions/{payroll-instruction-id}` | 131,833 | `payrollRegionCode`, `payrollGroupCode`, `payrollFileNumber`, `payrollProfileID`, `itemID`, `workAssignmentStatus`, `generalDeductionInstructions`, `garnishmentInstructions` *(+5)* | SPLIT — 13 top-level groups, 131,833B schema |

## Per-operation detail

### POST `/events/payroll/v2/worker-general-deduction-instruction.change`
- Summary: Change Worker General Deduction Instruction
- Schema file: `events_payroll.worker.generalDeductionInstruction.change_schema_v02_00_rev001.json` (72,772 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v2/worker-general-deduction-instruction.change/meta`
- Summary: Change Worker General Deduction Instruction Meta
- Schema file: `events_payroll.worker.generalDeductionInstruction.change_meta_schema_v02_00_rev001.json` (83,182 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/payroll/v2/worker-general-deduction-instruction.start`
- Summary: Start Worker General Deduction Instruction
- Schema file: `events_payroll.worker.generalDeductionInstruction.start_schema_v02_00_rev001.json` (70,853 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v2/worker-general-deduction-instruction.start/meta`
- Summary: Start Worker General Deduction Instruction Meta
- Schema file: `events_payroll.worker.generalDeductionInstruction.start_meta_schema_v02_00_rev001.json` (82,279 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### POST `/events/payroll/v2/worker-general-deduction-instruction.stop`
- Summary: Stop Worker General Deduction Instruction
- Schema file: `events_payroll.worker.generalDeductionInstruction.stop_schema_v02_00_rev001.json` (67,810 bytes)
- Top-level response groups (21): eventID, serviceCategoryCode, eventNameCode, eventTitle, eventSubTitle, eventReasonCode, eventStatusCode, priorityCode, recordDateTime, creationDateTime, effectiveDateTime, expirationDateTime, dueDateTime, notificationIndicator, originator, actor, actAsParty, onBehalfOfParty, eTag, links, data
- Recommendation: **keep whole (mutation requires full body)**

### GET `/events/payroll/v2/worker-general-deduction-instruction.stop/meta`
- Summary: Stop Worker General Deduction Instruction Meta
- Schema file: `events_payroll.worker.generalDeductionInstruction.stop_meta_schema_v02_00_rev001.json` (63,542 bytes)
- Top-level response groups (5): /serviceCategoryCode/codeValue, /eventNameCode/codeValue, queryCriteria, /data/eventContext, /data/transforms
- Recommendation: **single tool (meta discovery — rarely agent-facing)**

### GET `/payroll/v1/workers/{aoid}/payroll-instructions`
- Summary: Worker Payroll Instructions
- Schema file: `payrollInstructions_schema_v01_00_rev006.json` (131,833 bytes)
- Top-level response groups (13): payrollRegionCode, payrollGroupCode, payrollFileNumber, payrollProfileID, itemID, workAssignmentStatus, generalDeductionInstructions, garnishmentInstructions, memoInstructions, earningInstructions, benefitInstructions, retirementPlanInstructions, links
- Recommendation: **SPLIT — 13 top-level groups, 131,833B schema**

### GET `/payroll/v1/workers/{aoid}/payroll-instructions/{payroll-instruction-id}`
- Summary: Worker Payroll Instruction Instance
- Schema file: `payrollInstructions_schema_v01_00_rev006.json` (131,833 bytes)
- Top-level response groups (13): payrollRegionCode, payrollGroupCode, payrollFileNumber, payrollProfileID, itemID, workAssignmentStatus, generalDeductionInstructions, garnishmentInstructions, memoInstructions, earningInstructions, benefitInstructions, retirementPlanInstructions, links
- Recommendation: **SPLIT — 13 top-level groups, 131,833B schema**
