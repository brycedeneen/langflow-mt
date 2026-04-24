# Team Time Cards (v2)

- Domain: `time`
- Slug: `team-time-cards`
- Swagger: https://api-library-marketplace.adp.com/hcm-offrg-wfn/time/team-time-cards/v2/team-time-cards-swagger_v2-merged.json
- Status: **ok**

## Operations (1)

| Method | Path | Schema (B) | Top-level groups | Split recommendation |
|---|---|---|---|---|
| GET | `/time/v2/workers/{aoid}/team-time-cards` | 114,152 | `associateOID`, `workerID`, `personLegalName`, `timeCards` | split-maybe — 114,152B schema |

## Per-operation detail

### GET `/time/v2/workers/{aoid}/team-time-cards`
- Summary: Team Time Cards
- Schema file: `teamTimeCards_schema_v02_00_rev009.json` (114,152 bytes)
- Top-level response groups (4): associateOID, workerID, personLegalName, timeCards
- Recommendation: **split-maybe — 114,152B schema**
