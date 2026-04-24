# Langflow Distributed-Worker Helm starter

Distributed-task-runners plan (`docs/superpowers/plans/2026-04-15-distributed-task-runners.md`)
Task 30 lives in a separate Helm repo, not this one. This directory holds the
concrete templates the plan spec'd out so the Helm-repo owner can lift them
into the real chart.

## What's here

- `values.example.yaml` — the `worker:` block to merge into the main chart's
  `values.yaml`. Defaults mirror the plan spec.
- `templates/worker-deployment.yaml` — Arq-based worker Deployment, branched
  from the plan's step 2. Reuses the main Langflow image + envFrom and
  overrides `command` + a couple of env vars.
- `templates/worker-scaledobject.yaml` — KEDA `ScaledObject` that scales the
  worker Deployment by Redis queue length.

## Not included here

- `Chart.yaml`, `_helpers.tpl`, `values.schema.json`, the API Deployment that
  these templates reference as a sibling — all of those belong in the main
  chart repo.
- `helm lint` / `helm template` verification — this starter isn't a complete
  chart on its own; it only becomes valid once merged with the main chart's
  skeleton.

## How to use this in the Helm repo

1. Copy `templates/worker-deployment.yaml` and
   `templates/worker-scaledobject.yaml` into the main chart's `templates/`.
2. Merge `values.example.yaml` into the chart's `values.yaml` — preserve any
   organization-specific defaults.
3. `helm lint <chart>` should pass.
4. If you run multiple queues (`runs:default`, `runs:high`, `webhooks`),
   duplicate the Deployment with each `--queue` arg — Arq workers poll a
   single queue per process.
5. KEDA must be installed in the target cluster for the ScaledObject to take
   effect. Without KEDA, the Deployment still runs at `replicas` from
   `values.yaml`.
