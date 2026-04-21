# Langflow Frontend

Vite + React 18 + TypeScript SPA. Styled with Tailwind v4 (CSS-first config — no `tailwind.config.mjs`; `index.css` owns the theme). Uses TanStack Query v5, Zustand v5, React Flow (`@xyflow/react`), and Radix primitives.

## Running in dev

From the repo root:
```shell
make frontend
```

That runs `npm install` once, then `npm start` — Vite on `http://localhost:3000`, HMR enabled. The `%` placeholder target in `Makefile.frontend` swallows positional args, so extra make args won't pollute the vite flags.

If you want the raw script:
```shell
cd src/frontend
npm install
npm start
```

### Dependencies

- Node.js **>=20.19** (enforced in `package.json`)
- npm 10+
- A running backend at `BACKEND_URL` (default `http://localhost:7860`)

### Environment variables

Vite reads from `.env` files in `src/frontend/`. Only one var actually matters for dev:

| Var | Required | Default | Description |
|---|---|---|---|
| `BACKEND_URL` | Yes | `http://localhost:7860` | Langflow API the frontend calls and proxies WebSockets to |

All other runtime config is served by the backend at `/api/v1/config` and read by the app — there is no separate frontend `.env` file to maintain.

## Building for production

```shell
# From repo root — builds the SPA AND copies it into the backend package
make build_frontend
```

Outputs:
- `src/frontend/build/` — raw static bundle
- `src/backend/base/langflow/frontend/` — same bundle, copied so the backend serves it from the same container

Serving the bundle requires no Node process; the backend's FastAPI app mounts `LANGFLOW_FRONTEND_PATH` (defaulting to the copy above) as static files.

### Building a standalone frontend image

If you want the frontend in its own container (as `deploy/docker-compose.yml` does):

```shell
make docker_build_frontend
```

Uses `docker/frontend/build_and_push_frontend.Dockerfile`. The resulting image is an `nginx:alpine` serving the Vite build and proxying `/api` to `BACKEND_URL`.

## Testing

| Command | What it runs |
|---|---|
| `make test_frontend` | Jest unit tests (this project uses **Jest**, not Vitest) |
| `make test_frontend_watch` | Jest in watch mode |
| `make test_frontend_coverage` | Jest with coverage |
| `make tests_frontend` | Playwright E2E — requires a running backend |
| `make tests_frontend UI=true` | Playwright with UI |

React Query v5 quirk: use `isPending` (not `isLoading`) in assertions; `isLoading` is v4 terminology.

## Formatting and linting

```shell
make format_frontend           # biome format --write
make format_frontend_check     # biome check (read-only)
```

Biome is the only formatter/linter — no ESLint, no Prettier.

## Storybook

```shell
make storybook            # http://localhost:6006
make storybook_network    # accessible on 0.0.0.0:6006
make storybook_build      # static export to storybook-static/
```

## Dependency on the backend

The frontend expects the backend API surface (v1 + v2). Run the backend and a worker (if you're exercising webhook/schedule flows) as described in the root [README](../../README.md#running-locally).
