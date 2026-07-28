# casas-infra-platform-demo

A **product repo** with **no terraform / infra rights**. It owns two things per service:

1. **The tenant contract** — `tenants/<service>/dev/<service>-dev.json` (what the service needs: Cloud Run, and optionally Cloud SQL, Redis, GCS, Vertex). This is *just JSON*.
2. **The app** — `services/<service>/` (source + Dockerfile) + its image build.

Everything else — modules, foundation, the shared environment, and **the `terragrunt apply`
itself** — lives in the control plane (`Liberty-Global-Tech/casas-infra-platform`), which holds
the *only* terraform identity.

## Services

| Service | Language | Tenant contract | CI workflow |
|---|---|---|---|
| `demo` | Python (FastAPI) | `tenants/demo/dev/demo-dev.json` | `demo-build.yml` |
| `smoke-go` | Go 1.23 | `tenants/smoke-go/dev/smoke-go-dev.json` | `smoke-go-build.yml` |
| `smoke-java` | Java 17 (Maven) | `tenants/smoke-java/dev/smoke-java-dev.json` | `smoke-java-build.yml` |
| `smoke-python` | Python 3.13 (FastAPI) | `tenants/smoke-python/dev/smoke-python-dev.json` | `smoke-python-build.yml` |

The three `smoke-*` services are calculator libraries (add / subtract / multiply) wrapped as
lightweight HTTP services. They serve as factory pipeline smoke tests — each exercises the
Spec → Plan → Build cycle for a different language on this repo's CI/CD infrastructure.

## How a change ships (no cloud creds here)

```
edit tenants/<service>/dev/<service>-dev.json  ─PR→ merge
        │
        └─ dispatch.yml WIF-auths (narrow image-CI SA), reads a GitHub token from Secret
           Manager (keyless — no stored secret), and fires repository_dispatch ─▶
              control plane checks this contract out READ-ONLY and runs terragrunt apply
              with its deployer SA. This repo never holds a terraform identity.
```

## The one cloud right this repo has (narrow)

`*-build.yml` workflows build/push the container and deploy it to Cloud Run using a **narrow
image-CI identity** (`GCP_IMAGE_CI_SA` — Artifact Registry writer + Cloud Run developer only).
They **cannot** provision or change infrastructure.

Tests run inside the Docker build for every service:
- **Go** — `go test ./...` in the builder stage (CGO disabled)
- **Java** — `mvn package` runs Surefire in the builder stage
- **Python** — multi-stage build: `pytest` in the `test` stage gates the runtime image

## Layout

```
.
├── tenants/
│   ├── demo/dev/demo-dev.json                # Cloud Run + SQL + Redis + GCS + Vertex
│   ├── smoke-go/dev/smoke-go-dev.json        # Cloud Run only
│   ├── smoke-java/dev/smoke-java-dev.json    # Cloud Run only
│   └── smoke-python/dev/smoke-python-dev.json
├── services/
│   ├── demo/                                 # FastAPI demo (original)
│   ├── go/                                   # Go calculator + HTTP server
│   ├── java/                                 # Java calculator + HTTP server (JDK HttpServer)
│   └── python/                               # Python calculator + FastAPI wrapper
└── .github/workflows/
    ├── demo-build.yml                        # build/push/deploy demo image
    ├── smoke-go-build.yml                    # build/push/deploy smoke-go image
    ├── smoke-java-build.yml                  # build/push/deploy smoke-java image
    ├── smoke-python-build.yml                # build/push/deploy smoke-python image
    └── dispatch.yml                          # notify the control plane on contract change
```

## Adding a new service

1. Add `services/<name>/` with a `Dockerfile` exposing port 8080 (dynamic via `PORT` env var).
2. Add `tenants/<name>/dev/<name>-dev.json` declaring the Cloud Run config (and any backends needed).
3. Copy one of the existing `*-build.yml` workflows, update `REPO`, `IMAGE`, and `SERVICE`, and set `paths: ["services/<name>/**"]`.
4. Open a PR — `dispatch.yml` notifies the control plane to plan the new tenant contract.

## Status check on PRs

The control plane posts a `platform/tenant-plan` commit status on PRs touching `tenants/**`
(pending while it runs, then pass/fail with the plan+policy result). It's advisory only unless
this repo's branch protection requires it — add that as a required status check on `main` if you
want PRs blocked until the platform's plan/policy gate passes.

## Repo variables / secrets

- `vars.GCP_WIF_PROVIDER`, `vars.GCP_IMAGE_CI_SA` — the narrow image-CI identity, used by all
  `*-build.yml` workflows and by `dispatch.yml` to WIF-auth into Secret Manager
  (`orchestrator-github-token-dev`). Both are provisioned into this repo's `dev` GitHub
  Environment by the platform's foundation — nothing to set here.
- **No GitHub Actions secrets in this repo** — the dispatch token lives only in Secret Manager.
