# Backend deps — deferred major/risky bumps (follow-up)

> Complement to the three deps commits on `platform-multi-tenant` (pillow+typer+validators, 28 patches, uvicorn + docling + 9 vendor SDK minors). Written 2026-04-24 after running `uv pip list --outdated` against a freshly patched lockfile (~220 packages still drifted, most transitive or risky).

## Known-blocked (don't retry without breaking the blocker)

| Package | Current → Latest | Blocker |
|---|---|---|
| `typer` | 0.21.2 → 0.24.2 | `docling` 2.91 still caps `typer<0.22`. Unblocks if docling relaxes. |
| `redis` | 5.3.1 → 7.4.0 | `arq==0.28.0` pins `redis<6`. Per memory: upstream-blocked. |
| `elasticsearch` + `elastic-transport` | 8.19 / 8.17 → 9.3 / 9.2 | Intentionally on ES 8 for support. Per memory. |
| `agent-lifecycle-toolkit` | 0.4.5 → 0.10.1 | User's ALTK decision — tied to WatsonX Phase 6 follow-up (see `project_remove_watsonx.md`). Transitively drags `ibm-watsonx-ai` + `langchain-ibm`. |
| `websockets` | 15.0.1 → 16.0 | Held by docling chain (tried a focused `--upgrade-package websockets` — resolver kept 15). |
| `cryptography` | 46.0.7 → 47.0.0 | Just bumped 43→46 in Phase 3b. Let it settle. |
| `starlette` | 0.52 → 1.0 | Moves in lockstep with `fastapi`. Don't force; follows the next fastapi minor. |
| `astra-assistants` | 2.2.13 → 2.5.5 | We have a `tree-sitter>=0.25` override sized for 2.2 (per `pyproject.toml` override comment). Re-test the override fits 2.5.x before bumping. |
| `elevenlabs` | 1.58.1 → 2.44.0 | Current spec is platform-pinned at 1.58.1 for `python_version == 3.12`. Re-pin story needed before major bump. |
| `pypdfium2` | 4.30 → 5.7 | Transitive via docling. Risky for PDF rendering path. |

## Isolated majors worth evaluating individually

Each deserves its own commit + spec cap + smoke pass. Rough ordering by risk, low → high:

- `authlib`-adjacent: `joserfc` (new), `python-jose` deprecation. Authlib 1.7 already landed; eyeballing JWT verification end-to-end in a follow-up run is prudent.
- `anthropic` 0.96→0.97 (already landed), `langchain-openai` 1.1→1.2, `langchain-core` 1.3.0→1.3.2 — LLM SDK patches; next LC integration sweep should fold these in.
- `groq` 0.37→1.2 (major). Affects the Groq model bundle; sanity-check `test_groq_chat_completion.py`.
- `huggingface-hub` 0.36→1.12 (major leap across many releases). Ecosystem-wide impact (`transformers`, `sentence-transformers`, `accelerate`). Tie to the `transformers 4→5` decision.
- `transformers` 4→5, `sentence-transformers`, `accelerate`, `trl` 0.29→1.2 — coordinated ML-stack bump. Whole-session's worth of work on its own; pair with `huggingface-hub` 1.x.
- `pydantic-ai` 0.4→1.86 (massive leap — may need real API migration). Skip until we're intentionally integrating pydantic-ai features.
- `cohere` 5→6, `firecrawl-py` 1→4, `e2b` 1→2, `twelvelabs` 0.4→1.2, `yfinance` 0.2→1.3, `assemblyai` 0.35→0.63, `scrapegraph-py` 1→2, `atlassian-python-api` 3.41→4.0, `clickhouse-connect` 0.7→0.15, `wrapt` 1→2, `pygls` 1→2, `semver` 2→3, `tenacity` 8→9, `semchunk` 2→4, `pybase62` 0.4→1.0, `asttokens` 2→3, `pytest` 8→9, `dill` 0.3→0.4, `invoke` 2→3, `junitparser` 4→5, `google-cloud-storage` 2.19→3.10 — each is a single vendor SDK or tooling major; batch them in pairs when you touch the relevant component next.
- `gevent` 24→26, `gymnasium` 1.2→1.3, `google-cloud-aiplatform` 1.141→1.148 — usually safe but worth their own verify step.

## Deferred tooling

- `codeflash` 0.17→0.20 — known to attach a RichHandler to root/stdout (per `project_codeflash_richhandler_stdout_leak.md`). Before bumping, confirm the patch doesn't make the CLI-runner stdout-leak worse.

## Patch drift still present (transitives held)

`botocore` 1.42.94→1.42.96, `ruamel-yaml` 0.18→0.19, `fsspec` 2026.2→2026.3, `boto3-stubs`, `idna` 3.11→3.13, `greenlet` 3.1→3.4, `grpcio` 1.78→1.80, `google-*` patches, `crosshair-tool`, `exa-py`, `dynaconf`, etc. — will land when their parents bump, or on the next broad lockfile refresh.

## When to revisit

- After the next `fastapi` or `docling` minor — re-check `typer`, `starlette`, `websockets`.
- When the ALTK decision lands — drops a whole cluster of transitive holds (`ibm-watsonx-ai`, `langchain-ibm`, related IBM SDKs).
- Before the next CalVer release — refresh `certifi`, `pytz` (just bumped), `*-stubs`, and run `uv lock --upgrade` with the blocklist above as `--no-upgrade-package` filters.
