# Time Off Requests (v2)

- Domain: `time`
- Slug: `time-off-requests`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/time-off-requests/v2/time-off-requests-swagger_v2-merged.json
- Status: **ok**

## Operations (5)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/time/v2/workers/{aoid}/time-off-details/time-off-balances` | 156,418 | `paidTimeOffConfiguration`, `paidTimeOffBalances`, `paidTimeOffRequests` | split-maybe — 156,418B schema |
| GET | `/time/v2/workers/{aoid}/time-off-details/time-off-configurations` | 156,418 | `paidTimeOffConfiguration`, `paidTimeOffBalances`, `paidTimeOffRequests` | split-maybe — 156,418B schema |
| GET | `/time/v2/workers/{aoid}/time-off-details/time-off-requests` | 156,418 | `paidTimeOffConfiguration`, `paidTimeOffBalances`, `paidTimeOffRequests` | split-maybe — 156,418B schema |
| POST | `/time/v2/workers/{aoid}/time-off-requests` | 151,786 | `positionRef`, `requestID`, `requestUri`, `entryDateTime`, `approvalDueDate`, `requestStatus`, `requestorComment`, `comments` *(+4)* | keep whole (mutation requires full body) |
| PUT | `/time/v2/workers/{aoid}/time-off-requests/{request-id}` | 151,786 | `positionRef`, `requestID`, `requestUri`, `entryDateTime`, `approvalDueDate`, `requestStatus`, `requestorComment`, `comments` *(+4)* | keep whole (mutation requires full body) |

## Per-operation detail

### GET `/time/v2/workers/{aoid}/time-off-details/time-off-balances`
- Summary: Paid Time Off - Balances
- Schema file: `paidTimeOffDetails_v02_00_rev012_schema.json` (156,418 bytes)
- Top-level response groups (3): paidTimeOffConfiguration, paidTimeOffBalances, paidTimeOffRequests
- Recommendation: **split-maybe — 156,418B schema**

### GET `/time/v2/workers/{aoid}/time-off-details/time-off-configurations`
- Summary: Paid Time Off - Configurations
- Schema file: `paidTimeOffDetails_v02_00_rev012_schema.json` (156,418 bytes)
- Top-level response groups (3): paidTimeOffConfiguration, paidTimeOffBalances, paidTimeOffRequests
- Recommendation: **split-maybe — 156,418B schema**

### GET `/time/v2/workers/{aoid}/time-off-details/time-off-requests`
- Summary: Paid Time Off - Requests
- Schema file: `paidTimeOffDetails_v02_00_rev012_schema.json` (156,418 bytes)
- Top-level response groups (3): paidTimeOffConfiguration, paidTimeOffBalances, paidTimeOffRequests
- Recommendation: **split-maybe — 156,418B schema**

### POST `/time/v2/workers/{aoid}/time-off-requests`
- Summary: Paid Time Off Request - Create
- Schema file: `paidTimeOffRequestResponse_v02_00_rev008_schema.json` (151,786 bytes)
- Top-level response groups (12): positionRef, requestID, requestUri, entryDateTime, approvalDueDate, requestStatus, requestorComment, comments, totalQuantity, totalTime, meta, paidTimeOffEntries
- Recommendation: **keep whole (mutation requires full body)**

### PUT `/time/v2/workers/{aoid}/time-off-requests/{request-id}`
- Summary: Paid Time Off Request - Details
- Schema file: `paidTimeOffRequestResponse_v02_00_rev008_schema.json` (151,786 bytes)
- Top-level response groups (12): positionRef, requestID, requestUri, entryDateTime, approvalDueDate, requestStatus, requestorComment, comments, totalQuantity, totalTime, meta, paidTimeOffEntries
- Recommendation: **keep whole (mutation requires full body)**
