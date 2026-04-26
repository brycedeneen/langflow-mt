-- One-shot cleanup for duplicate user Variables in `variable`.
--
-- Why this exists: the `variable` table has no UNIQUE constraint on
-- (user_id, organization_id, name), so each call to
-- create_secret_variable inserts a fresh row. The Assist tool
-- previously called create_secret_variable for ADP creds (and other
-- secret fields), so a single user accumulated many same-name rows
-- across rebuilds.
--
-- What this does: for every (user_id, organization_id, name) group
-- with >1 row, keep the most-recently-touched row and delete the
-- rest. "Most recent" = COALESCE(updated_at, created_at) DESC, with
-- id DESC as a deterministic tiebreaker.
--
-- Usage:
--   docker exec -i postgresdb psql -U postgres -d langflow \
--     -f - < scripts/cleanup_duplicate_variables.sql
--
-- Idempotent: running it on a clean table is a no-op.

BEGIN;

-- Preview what's about to be deleted (safe to keep — it's just a SELECT).
WITH ranked AS (
    SELECT
        id,
        name,
        user_id,
        organization_id,
        created_at,
        updated_at,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, organization_id, name
            ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
        ) AS rn
    FROM variable
)
SELECT
    id,
    name,
    user_id,
    organization_id,
    COALESCE(updated_at, created_at) AS last_touched,
    rn AS rank_in_group
FROM ranked
WHERE rn > 1
ORDER BY name, last_touched DESC;

-- Delete every row except the rank-1 row in each group.
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, organization_id, name
            ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
        ) AS rn
    FROM variable
)
DELETE FROM variable
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Verify: no group should have >1 row after cleanup.
SELECT
    name,
    user_id,
    organization_id,
    COUNT(*) AS remaining
FROM variable
GROUP BY name, user_id, organization_id
HAVING COUNT(*) > 1;

COMMIT;
