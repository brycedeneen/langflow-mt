# Non-LC dep follow-ups — status snapshot

**Date:** 2026-04-22 (re-verified 2026-04-24)
**Status:** Informational — no action required today
**Goal:** Track the three dep-audit items that were deferred on 2026-04-22 because they were either upstream-blocked or already landed at an intermediate cut. None are blockers; they are "when upstream moves, we move" follow-ups.

**Re-verification on 2026-04-24 (from `uv.lock`):**
- `arq==0.28.0` — unchanged, still pins `redis<6`. Item A remains upstream-blocked.
- `redis==5.3.1` — unchanged.
- `chromadb==1.5.8` — unchanged, still on latest. Item B remains resolved — no action.
- `elasticsearch==8.19.3` — unchanged, still within ES 8 support window.
- None of items A / B / C changed since 2026-04-22; this file stays as a memory anchor rather than an active plan.

## Item A — `redis 5.x → 7.x`

- **Current:** `redis==5.3.1` (langflow-base extra pin `redis>=5.2.1,<6.0.0`).
- **Latest:** `redis==7.4.0`.
- **Blocker:** `arq==0.28.0` (transitive job-queue dep) pins `redis<6`. `arq` is the only consumer of redis in the default install tree.
- **Upstream state:** arq 0.28.0 was the current release as of 2026-04-22 — latest on PyPI. No pre-release has lifted the redis cap.
- **Action:** Watch `arq`'s GitHub releases. When arq lifts its `redis<6` pin, lift langflow-base's `redis<6.0.0` cap in the same PR. No refactor needed in our code — `redis-py 6/7` APIs we use (set/get/expire/pubsub) are stable across the major bumps.
- **Risk if never fixed:** None today. redis 5 is LTS-style; upgrading is a nice-to-have.

## Item B — `chromadb 1.x → 3.x`

- **Current:** `chromadb==1.5.8` (langflow-base `chroma` extra pins `chromadb>=1.3.5,<2.0.0`).
- **Latest:** `chromadb==1.5.8` — **we are on latest**.
- **Resolution:** On 2026-04-22 the initial audit said "chromadb 1→3" but PyPI's `chromadb` package went from 1.x to **1.5.x** (not 3.x). The confusion was with an internal version tag; the actual upstream release line is `chromadb 1.x`, currently `1.5.8`. We are current.
- **`langchain-chroma` gate:** our cap is `langchain-chroma<2.0.0`; latest is `1.1.0` (installed). Sync.
- **Action:** None. Close this follow-up.

## Item C — `elasticsearch 8.x → 9.x`

- **Current:** `elasticsearch==8.19.3` (langflow-base `elasticsearch` extra pins `elasticsearch>=8.19.0,<9.0.0`).
- **Latest:** `elasticsearch==9.3.0`.
- **Intermediate gate:** LC 1.x Phase 1 landed `langchain-elasticsearch==1.0.0`. That package's `elasticsearch` support window does extend into 9.x on some code paths but its tested surface stays on 8.x.
- **Blocker:** Lifting our `elasticsearch<9.0.0` cap requires:
  1. Verifying `langchain-elasticsearch` 1.x works with `elasticsearch 9.x` at runtime (not just at install).
  2. Re-running the `langchain-elasticsearch` component smoke tests against a 9.x cluster.
- **Action:** Deferred. No urgency — 8.19 is supported upstream through 2027. When someone bumps, own both the extra pin lift and the smoke verification in one PR.
- **Risk if never fixed:** None short-term; ES 8 is supported. Long-term, we'll want the upgrade before Elastic's 8.x EOL.

## Summary

| Item | State | Next action | Owner |
|---|---|---|---|
| A — redis 5 → 7 | Upstream-blocked by `arq` | Watch arq releases; bump both together | — |
| B — chromadb 1 → 3 | **Resolved** (audit miscount; we are on latest 1.5.8) | Close the follow-up | — |
| C — elasticsearch 8 → 9 | Deferred; ES 8 supported to 2027 | Verify `langchain-elasticsearch 1.x` on ES 9 when ready | — |

None of these blocks Phase 3 (composio + openinference tooling) or Phase 4 (watsonx removal). Keep this doc updated as a project-memory anchor rather than a live plan.

---

## Deferred dep bumps that surfaced as Phase 1 startup-log noise

Four upstream packages emit `PydanticDeprecatedSince20` / `LangGraphDeprecatedSinceV10` warnings on first import. On 2026-04-22 we added filter-warnings in `src/backend/base/langflow/__init__.py` to silence them (the warnings are future-failures, not current bugs). The underlying pattern fixes will need the bumps below when upstream is ready:

| Package | Installed | Latest | Pin | Notes |
|---|---|---|---|---|
| `trustcall` | `0.0.39` | `0.0.39` | `>=0.0.38,<1.0.0` (backend/base) | Already on latest; warning is `from langgraph.constants import Send`. No bump available — upstream PR to migrate to `langgraph.types.Send` needed. |
| `twelvelabs` | `0.4.11` | `1.2.3` (2026-04-20) | `>=0.4.7,<1.0.0` (backend/base `twelvelabs` extra) | Major bump; likely breaking. Our imports are limited to `from twelvelabs import TwelveLabs` in five `components/twelvelabs/*.py` files — the client-class surface is probably stable. Lift the `<1.0.0` cap, sync, run the twelvelabs component tests, fix any API drift. |
| `storage3` | `2.25.1` | `2.28.3` | Transitive via `supabase>=2.6.0,<3.0.0` | No direct pin; upgrade comes "for free" by refreshing supabase's resolution window with `uv lock --upgrade-package storage3`. Verify the supabase extra still imports cleanly. |
| `agent-lifecycle-toolkit` (installs as `altk`) | `0.4.5` | `0.10.1` | `~=0.4.4` (backend/base `altk` extra) | `~=` blocks 0.5+. Check `src/lfx/src/lfx/base/agents/altk_base_agent.py` + `altk_tool_wrappers.py` for API churn before lifting; IBM's altk 0.5–0.10 has gone through tool-wrapper refactors. Likely needs matching code changes. |

**Priority for these bumps:** low. Warnings are silenced; nothing is broken. Revisit when one of the breakage horizons closes (Pydantic 3.0 release, LangGraph 2.0 release, or a real bug in the pinned version surfaces).
