# MultiAV Contributors Guide

This document explains how MultiAV’s pieces fit together, what invariants to preserve, and how to safely extend the system.

If you only need to run the stack, start with `README.md`.

## What this project is
MultiAV is a multi-engine malware scanning service:
- Upload a file via the API (or the Next.js UI)
- Scan asynchronously across multiple engines (Celery workers)
- Persist per-engine results and a job lifecycle in the database
- Return an aggregated verdict + per-engine details

## Components and responsibilities

### API (FastAPI)
**Location:** `app/main.py`, `app/api/v1/*`

Responsibilities:
- Accept uploads (`POST /api/v1/scan/`)
- Return aggregated results (`GET /api/v1/results/{job_id}`)
- Provide UI helper endpoints (`/api/v1/ui/*`)
- Enforce API key authentication and quotas

Key files:
- `app/api/v1/scan.py`: upload, SHA-256 caching, enqueue Celery scan job
- `app/api/v1/results.py`: results lookup + summary; does not consume quota (safe for polling)
- `app/api/v1/ui.py`: lightweight UI endpoints + `/api-key` status endpoint

### Authentication (API keys)
**Location:** `app/core/auth.py`

How it works:
- Clients send `X-API-Key`.
- Keys are stored hashed (`APIKey.key_hash`).
- Keys can be bypassed in local development with `BYPASS_AUTH=true`.
- Keys expire after `API_KEY_TTL_DAYS` (default: 30) using the key’s `created_at` timestamp as the subscription start.

### Rate limiting (daily quota)
**Location:** `app/core/rate_limit.py`

How it works:
- Quotas are **per day** (`APIKey.rate_limit_per_day`).
- `POST /api/v1/scan/` consumes quota (one request = one unit).
- `GET /api/v1/results/{job_id}` is intentionally not consumed (polling is “free”).
- Redis is used for counting when available; tests use an in-memory fallback.

### Worker (Celery)
**Location:** `app/workers/*`

Responsibilities:
- Execute scan orchestration asynchronously
- Fan out to per-engine tasks and fan in to finalize

Important design goals:
- One scan job => one chord (parallel engine runs) => one final aggregation.
- Engine failures/timeouts must be recorded without killing the whole job.

### Orchestrator / Engine registry
**Location:** `app/services/orchestrator/*`, `config/engines.yaml`

Responsibilities:
- Load engine configuration from YAML (`config/engines.yaml`)
- Decide which engines are active and their timeouts/weights
- Ensure one `EngineResult` per `(job_id, engine)` (idempotent / upsert-safe writes)

Best practice:
- Do not hardcode “enabled” flags in code. Keep toggles in YAML so deployments can mount read-only config and flip engines without code changes.

### Engines
**Location:** `app/services/engines/*`

Responsibilities:
- Perform the actual scan (ClamAV, YARA, Windows Defender)
- Return normalized payloads for aggregation

Best practice:
- Treat engine output as untrusted: always normalize defensively and preserve error details.
- Enforce timeouts per engine (configured in YAML).

### Aggregator
**Location:** `app/services/aggregator/*`

Responsibilities:
- Normalize engine payloads into a common schema
- Apply weighted voting and derive `verdict`, `severity`, `confidence`
- Produce a stable summary shape for the API/UI

Best practice:
- Do not change existing status strings or response keys unless you update UI and tests in the same change.

### Storage
**Location:** `app/services/storage.py`

Responsibilities:
- Persist uploaded binaries via a pluggable backend:
  - S3/MinIO (default in compose) with TTL and size-cap cleanup
  - Local filesystem (dev-only, keeps files on disk)

Best practice:
- S3/MinIO backend must always enforce TTL and max-bucket size caps.
- Avoid loading the entire file into memory; stream whenever possible.

### Database / Models
**Location:** `app/db/models.py`, `app/db/session.py`

Core entities:
- `File`: one per unique SHA-256 upload
- `ScanJob`: one per scan request; tracks status + timestamps
- `EngineResult`: one per engine per job (`(job_id, engine)` unique)
- `APIKey`: API key metadata and quotas

Invariants to preserve:
- Job IDs are UUIDs; reject/normalize invalid IDs early (UI and API).
- Job status progression: created/running => terminal (`done` | `done_with_errors` | `error`); terminal implies `completed_at` is set.
- One `EngineResult` per `(job_id, engine)`; updates must not duplicate rows.

### UI (Next.js)
**Location:** `ui/web/*`

Responsibilities:
- Provide a usable browser UI for uploads, results, and recent jobs
- Store API key locally (browser storage) and send it as `X-API-Key`
- Poll results until terminal status, with backoff to avoid hammering the API

Best practice:
- Keep client-side polling resilient (backoff, stop on terminal, don’t show full-page loading spinners during background refresh).
- When adding/renaming API fields, update `ui/web/src/lib/api-types.ts` and the API client.

### Scripts (operator tooling)
**Location:** `scripts/*`

`scripts/manage_keys.py` supports:
- `create <name> [requests_per_day]`
- `list`
- `revoke <name|uuid>` (disable)
- `delete <name|uuid>` (hard delete)
- `set-limit <name|uuid> <requests_per_day>`
- `renew <name|uuid>` (reactivate + reset the 30-day window)

This is the intended “billing integration” point: when a user renews a subscription, your billing webhook would call the equivalent of `renew`.

## End-to-end request flow
1. User uploads a file via UI or `POST /api/v1/scan/`.
2. API authenticates (`X-API-Key`) and checks daily quota.
3. API stores the file and creates/returns a scan job.
4. Worker runs all enabled engines (in parallel) and persists results.
5. Finalizer aggregates results and sets the terminal job state.
6. UI polls `GET /api/v1/results/{job_id}` until terminal (polling doesn’t consume quota).

## Running the full stack via Docker Compose

### 1) Start services
From the repo root:
```bash
docker compose up --build
```

Ports:
- API: `http://localhost:8000` (docs at `/docs`)
- UI: `http://localhost:3000`
- MinIO: `http://localhost:9001` (console), `http://localhost:9000` (S3 endpoint)

### 2) Create an API key (required by default)
In another terminal:
```bash
docker compose exec app python scripts/manage_keys.py create dev 50
```
Copy the printed `API Key: ...`.

### 3) Use the key
- UI: open `http://localhost:3000`, click the key icon, paste the key.
- curl:
  ```bash
  curl -H "X-API-Key: <your-key>" -F "file=@/path/to/file.bin" http://localhost:8000/api/v1/scan/
  curl -H "X-API-Key: <your-key>" http://localhost:8000/api/v1/results/<job_id>
  ```

### 4) Optional: local dev bypass
For local development only, you can bypass auth:
- Set `BYPASS_AUTH: "true"` for `app` and `worker` in `docker-compose.yml`, then restart.

### 5) Resetting everything
To stop and delete volumes (wipes DB, Redis, MinIO data):
```bash
docker compose down -v
```

## Best practices when changing code
- Keep API response shapes stable; update UI + tests together when contracts change.
- Treat engines as unreliable: record timeouts/errors per engine and keep jobs progressing to a terminal status.
- Preserve DB invariants (UUID job IDs, terminal statuses, unique `(job_id, engine)`).
- Keep engine toggles and weights YAML-driven (no code edits required to enable/disable).
- Add tests for behavior changes; prefer stubbing engines in tests (see `tests/utils.py`).
- Avoid “polling costs quota” traps: results polling should remain cheap and safe.

