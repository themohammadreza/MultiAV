MultiAV is a FastAPI + Celery powered multi-engine malware scanning service. It ingests files over HTTP, runs them through multiple AV/static-analysis engines, normalizes the outputs, and returns a single aggregated verdict with per-engine details.

For deeper architecture + contribution guidance, see `CONTRIBUTERS_GUIDE.md`.

## Final goal
- Ship a production-ready, horizontally scalable multi-engine scanner with pluggable engines, weighted aggregation, and simple ops (one-command docker-compose for local, K8s-ready later).
- Let operators toggle engines and tune weights from config without code edits.
- Provide clear APIs for uploading files, polling results, and wiring into other security workflows.

## Architecture at a glance
- **API (FastAPI, `app/main.py`)**: exposes `/api/v1/scan/` to upload and `/api/v1/results/{job_id}/` to retrieve aggregated verdicts, plus UI helpers like `/api/v1/ui/api-key/` and `/api/v1/health/`.
- **Worker (Celery, `app/workers/tasks.py`)**: orchestrates a Celery chord per scan: fan-out one task per enabled engines, then a fan-in callback to finalize the job.
- **Orchestrator (`app/services/orchestrator/dispatcher.py`)**: loads enabled engines from `config/engines.yaml`, records per-engine results (one row per engine per job), updates job status, and returns aggregated summaries.
- **Engines (`app/services/engines/*`)**:
  - ClamAV daemon (TCP or UNIX socket)
  - YARA rules compiled from the curated set in `rules/yara` (startup logs list any skipped rule files that need pruning/fixes)
  - Windows Defender via `malice/windows-defender`
- **Aggregation (`app/services/aggregator/*`)**: normalizes engine payloads, applies weights, derives verdict/severity/confidence, and infers families/categories.
- **Persistence**: PostgreSQL for metadata (files, jobs, engine results), Redis for Celery broker/result backend, and pluggable storage backends. Use S3/MinIO object storage for uploaded binaries with TTL/size-cap cleanup (default via `docker-compose`), or fallback to local filesystem in single-container dev setups.
- **Auth & quotas**: `X-API-Key` auth with optional `BYPASS_AUTH=true` for local development; daily quotas and 30-day key expiry.
- **Workers**: Celery runs with a thread pool (`--pool=threads`, concurrency 4, prefetch 1) to better handle the IO-bound AV engines without process churn.
- **Container topology (`docker-compose.yml`)**: app API, worker, Postgres, Redis, ClamAV, Windows Defender, and MinIO wired together with healthchecks. Config is still mounted read-only; file-sharing volumes are no longer required between API/worker.

## Project layout
- `app/main.py` — FastAPI app factory and router wiring; creates DB schema and applies lightweight migrations on startup for local/dev.
- `app/api/v1/scan.py` — upload endpoint; hashes file, caches by SHA-256, enqueues Celery job.
- `app/api/v1/results.py` — fetch results by job UUID; returns aggregated summary + per-engine details.
- `app/services/orchestrator/dispatcher.py` — runs enabled engines in parallel via Celery chord, records success/error, updates job status.
- `app/services/orchestrator/registry.py` — loads `config/engines.yaml`, applies defaults, and produces the active engine registry with weights/timeouts.
- `app/services/aggregator/` — normalize engine outputs, vote on verdicts, calculate severity/confidence, and infer malware families.
- `app/services/engines/clamav|windows_defender|yara/` — individual engine runners and (for ClamAV) Dockerfile.
- `app/services/storage.py` — pluggable storage backend (S3/MinIO or local) that streams uploads and provides per-task temp copies.
- `app/core/config.py` — environment-driven settings (DB/Redis/engine hosts, storage backend/object store config).
- `app/db/models.py` & `app/db/session.py` — SQLAlchemy models and session/engine factory.
- `app/db/migrations.py` — lightweight, idempotent schema updates (e.g., backfilling `api_key_id`, filenames) for deployments without Alembic.
- `config/engines.yaml` — enable/disable engines and tune weights/timeouts.
- `docker-compose.yml` — local stack definition; includes MinIO for object storage and mounts `./config` into app/worker.
- `Dockerfile` — app image builder used by API and worker services.
- `CONTRIBUTERS_GUIDE.md` — how the pieces fit together, invariants, and best practices for changes.
- `tests/` — starting point for automated coverage (extend here as you add features).
- `setup-docker-mirror.sh` — optional helper to point Docker at an alternate registry mirror (uses sudo).
- `ui/admin` — Next.js admin UI for managing admin users and API keys.

## Contributors: run it locally
### Prerequisites
- Docker and Docker Compose
- ~8 GB free disk for images (ClamAV DB + Windows Defender image are chunky)
- Ports free: 3000 (UI), 3001 (Admin UI), 8000 (API), 3310 (ClamAV), 3993 (Windows Defender), 9000/9001 (MinIO), 55432 (Postgres), 6380 (Redis)

### Quick start
1. From the repo root, build and launch everything:
   ```bash
   docker compose up --build
   ```
   This starts Postgres, Redis, ClamAV, Windows Defender, the FastAPI app, and the Celery worker.
2. Create an API key (required by default):
   ```bash
   docker compose exec app python scripts/manage_keys.py create dev 50
   ```
   Copy the printed `API Key: ...` value.
3. Use the key:
   - UI: open `http://localhost:3000`, click the key icon, paste the key.
   - curl:
     ```bash
     curl -H "X-API-Key: <your-key>" -F "file=@/path/to/sample.bin" http://localhost:8000/api/v1/scan/
     curl -H "X-API-Key: <your-key>" http://localhost:8000/api/v1/results/<job_id>/
     ```
   Or open `http://localhost:8000/docs` for Swagger UI.
4. Frontend: Next.js UI runs at `http://localhost:3000` with inline results and polling that stops at terminal status.

### Auth & quotas
- Required headers: `X-API-Key` for `POST /api/v1/scan/` and `GET /api/v1/results/{job_id}/`.
- Daily quota: `rate_limit_per_day` controls how many **new** scans a key can start per day; cached scans and results polling do not consume quota.
- Cache scope: SHA-256 cache hits are scoped to the requesting API key (or anonymous if auth is bypassed) to avoid cross-tenant sharing.
- Expiry: keys expire after `API_KEY_TTL_DAYS` (default 30). Renew with:
  ```bash
  docker compose exec app python scripts/manage_keys.py renew <name|uuid>
  ```
- Local dev bypass: set `BYPASS_AUTH=true` for `app` and `worker` in `docker-compose.yml` (do not use in production).

### Admin access
- On startup, a default superadmin is seeded **only if no admin users exist**.
- Supply `ADMIN_DEFAULT_USERNAME` and `ADMIN_DEFAULT_PASSWORD` for first-time setup. Startup fails with a clear error if either is missing.
- In Docker, set them for the `app` (and optionally `worker`) service via a `.env` file or `docker-compose.yml` overrides:
  ```bash
  ADMIN_DEFAULT_USERNAME=your-admin
  ADMIN_DEFAULT_PASSWORD=your-strong-password
  ```
- Rotate the superadmin password by logging into the admin UI and updating the account via the **Admin Users** page (superadmins only). For automation, call `PATCH /api/v1/admin/users/{user_id}/` with a new `password`.
- Admin UI runs at `http://localhost:3001` when `admin-frontend` is enabled in `docker-compose.yml`.

**Conda users**: export a minimal environment spec from installed packages with:
```bash
conda env export --from-history > environment.yml
```

### Engine switches and tuning
- Edit `config/engines.yaml` to toggle engines or adjust weights/timeouts:
  ```yaml
  engines:
    clamav:
      enabled: true
      weight: 0.35
      timeout: 60
    yara:
      enabled: true
      weight: 0.30
      timeout: 300
    windows-defender:
      enabled: true
      weight: 0.35
      timeout: 300
  ```
- Restart the app/worker containers to pick up changes:
  ```bash
  docker compose restart app worker
  ```
- **There is no need to touch the codebase to disable or reweight an engine—flip the YAML and restart.**
- If YARA logs “Skipped N YARA files due to errors”, remove or fix those rule files before running in production to keep compilation clean.
- Default timeouts are generous (ClamAV 60s, YARA 300s, Windows Defender 300s) to let heavier scans finish; tune down if you need stricter SLAs.

### Storage retention (MinIO/S3)
- `STORAGE_TTL_SECONDS` controls how long objects stay in the bucket (default 180s for dev/test).
- `STORAGE_MAX_BYTES` caps total bucket size (default 5 MiB); oldest objects are trimmed first when the cap is exceeded.
- Cleanup runs after uploads and via a background timer so TTL enforcement still happens during idle periods.
- Applies to the S3/MinIO backend; the local backend keeps files on disk for repeatable scans and relies on manual cleanup.

### Parallel scanning behavior
- Each scan spawns a Celery chord: one task per enabled engines in parallel, followed by a finalize task that aggregates results and sets the job status.
- Per-engine timeouts are enforced from `config/engines.yaml`; timeouts/errors are recorded per engine without blocking others. Mixed success/error becomes `done_with_errors`; all errors become `error`.
- Engine results are unique per `(job_id, engine)`; new deployments get this constraint automatically. Existing DB volumes created before this change need a one-time SQL:  
  `ALTER TABLE engine_results ADD CONSTRAINT uq_engine_results_job_engine UNIQUE (job_id, engine);`
- Workers run with `--prefetch-multiplier=1` to avoid one engine hogging the pool and to keep long-running scans more fairly scheduled.

## API surface (v1)
- `POST /api/v1/scan/` — multipart upload (`file` field). Returns `{job_id, status, cached, scanned_at?}`.
- `GET /api/v1/results/{job_id}/` — aggregated verdict, severity/confidence, families/categories, `filename`, and `details` keyed by engine.
- `GET /api/v1/ui/jobs/recent/` — lightweight feed of recent jobs with status/verdict/severity, filename, and SHA256.
- `GET /api/v1/ui/engines/active/` — enumerates enabled engines with configured timeouts and weights.
- `GET /api/v1/ui/api-key/` — returns API key name, quota usage, and expiry metadata.
- `GET /api/v1/health/` — readiness probe used by the UI during startup; includes per-dependency checks and errors.

## Frontends
- **Next.js UI** (recommended): `ui/web` served on port 3000 via compose. Inline results render under the upload form; polling stops automatically when a job hits a terminal status. The results page uses the same summary layout and a download JSON action.
  - Env: `NEXT_PUBLIC_API_BASE_URL` (defaults to `/` with compose proxy), `API_PROXY_TARGET` for reverse proxy, `NEXT_PUBLIC_UPLOAD_SIZE_LIMIT_MB` (or legacy `NEXT_PUBLIC_UPLOAD_LIMIT_MB`), plus `NEXT_PUBLIC_POLL_INTERVAL_MS`/`NEXT_PUBLIC_POLL_TIMEOUT_MS` for status polling.
  - The UI waits for `/api/v1/health/` before showing routes and surfaces API key quota/expiry info from `/api/v1/ui/api-key/`.
  - Local dev: `npm run dev` inside `ui/web`; compose already injects proxy vars.
- **Admin UI**: `ui/admin` served on port 3001 via compose. Provides login, admin user management (activation/superadmin), and API key management using the `/api/v1/admin/*` endpoints.

## Roadmap / still to build
- Engine prioritization / smart scheduling policies.
- Storage observability (metrics around TTL deletions, bucket usage) and tunable retention by environment.
- Production-grade health monitoring, metrics, and structured logging across services.
- Hardened retries/backoff per engine and clearer error surfacing.
- CI/CD with automated tests, linting, and sample corpus regression runs.
- Billing/subscriptions integration and an operator/admin key management surface.
