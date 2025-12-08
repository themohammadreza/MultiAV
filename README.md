MultiAV is a FastAPI + Celery powered multi-engine malware scanning service. It ingests files over HTTP, runs them through multiple AV/static-analysis engines, normalizes the outputs, and returns a single aggregated verdict with per-engine details.

## Final goal
- Ship a production-ready, horizontally scalable multi-engine scanner with pluggable engines, weighted aggregation, and simple ops (one-command docker-compose for local, K8s-ready later).
- Let operators toggle engines and tune weights from config without code edits.
- Provide clear APIs for uploading files, polling results, and wiring into other security workflows.

## Architecture at a glance
- **API (FastAPI, `app/main.py`)**: exposes `/api/v1/scan/` to upload and `/api/v1/results/{job_id}` to retrieve aggregated verdicts.
- **Worker (Celery, `app/workers/tasks.py`)**: orchestrates a Celery chord per scan: fan-out one task per enabled engines, then a fan-in callback to finalize the job.
- **Orchestrator (`app/services/orchestrator/dispatcher.py`)**: loads enabled engines from `config/engines.yaml`, records per-engine results (one row per engine per job), updates job status, and returns aggregated summaries.
- **Engines (`app/services/engines/*`)**:
  - ClamAV daemon (TCP or UNIX socket)
  - YARA rules compiled from `rules/yara`
  - Windows Defender via `malice/windows-defender`
- **Aggregation (`app/services/aggregator/*`)**: normalizes engine payloads, applies weights, derives verdict/severity/confidence, and infers families/categories.
- **Persistence**: PostgreSQL for metadata (files, jobs, engine results), Redis for Celery broker/result backend, filesystem storage at `storage/files/<sha256>/original` for uploaded binaries.
- **Container topology (`docker-compose.yml`)**: app API, worker, Postgres, Redis, ClamAV, and Windows Defender wired together with healthchecks and mounted config/storage.

## Project layout (opinionated guide)
- `app/main.py` — FastAPI app factory and router wiring; creates DB schema on startup for local/dev.
- `app/api/v1/scan.py` — upload endpoint; hashes file, caches by SHA-256, enqueues Celery job.
- `app/api/v1/results.py` — fetch results by job UUID; returns aggregated summary + per-engine details.
- `app/services/orchestrator/dispatcher.py` — runs enabled engines in parallel via Celery chord, records success/error, updates job status.
- `app/services/orchestrator/registry.py` — loads `config/engines.yaml`, applies defaults, and produces the active engine registry with weights/timeouts.
- `app/services/aggregator/` — normalize engine outputs, vote on verdicts, calculate severity/confidence, and infer malware families.
- `app/services/engines/clamav|windows_defender|yara/` — individual engine runners and (for ClamAV) Dockerfile.
- `app/services/storage.py` — saves uploads to `storage/files`, keyed by SHA-256 for cache hits.
- `app/core/config.py` — environment-driven settings (DB/Redis/engine hosts, storage path).
- `app/db/models.py` & `app/db/session.py` — SQLAlchemy models and session/engine factory.
- `config/engines.yaml` — enable/disable engines and tune weights/timeouts.
- `docker-compose.yml` — local stack definition; mounts `./storage` and `./config` into app/worker.
- `Dockerfile` — app image builder used by API and worker services.
- `technical-docs.md` — deeper, lower-level technical notes.
- `tests/` — starting point for automated coverage (extend here as you add features).
- `setup-docker-mirror.sh` — optional helper to point Docker at an alternate registry mirror (uses sudo).

## Contributors: run it locally
### Prerequisites
- Docker and Docker Compose
- ~8 GB free disk for images (ClamAV DB + Windows Defender image are chunky)
- Ports free: 8000 (API), 3310 (ClamAV), 3993 (Windows Defender), 55432 (Postgres), 6380 (Redis)

### Quick start
1. From the repo root, build and launch everything:
   ```bash
   docker compose up --build
   ```
   This starts Postgres, Redis, ClamAV, Windows Defender, the FastAPI app, and the Celery worker.
2. Upload a file:
   ```bash
   curl -F "file=@/path/to/sample.bin" http://localhost:8000/api/v1/scan/
   ```
   Note the returned `job_id`.
3. Poll results:
   ```bash
   curl http://localhost:8000/api/v1/results/<job_id>
   ```
   Or open `http://localhost:8000/docs` for Swagger UI.

### Engine switches and tuning
- Edit `config/engines.yaml` to toggle engines or adjust weights/timeouts:
  ```yaml
  engines:
    clamav:
      enabled: true
      weight: 0.26
      timeout: 30
  ```
- Restart the app/worker containers to pick up changes:
  ```bash
  docker compose restart app worker
  ```
- **There is no need to touch the codebase to disable or reweight an engine—flip the YAML and restart.**

### Parallel scanning behavior
- Each scan spawns a Celery chord: one task per enabled engines in parallel, followed by a finalize task that aggregates results and sets the job status.
- Per-engine timeouts are enforced from `config/engines.yaml`; timeouts/errors are recorded per engine without blocking others. Mixed success/error becomes `done_with_errors`; all errors become `error`.
- Engine results are unique per `(job_id, engine)`; new deployments get this constraint automatically. Existing DB volumes created before this change need a one-time SQL:  
  `ALTER TABLE engine_results ADD CONSTRAINT uq_engine_results_job_engine UNIQUE (job_id, engine);`

## API surface (v1)
- `POST /api/v1/scan/` — multipart upload (`file` field). Returns `{job_id, status, cached, scanned_at?}`.
- `GET /api/v1/results/{job_id}` — aggregated verdict, severity/confidence, families/categories, and `details` keyed by engine.

## Roadmap / still to build
- Engine prioritization / smart scheduling policies.
- Pluggable object storage (e.g., MinIO/S3) instead of local `storage/files`.
- Production-grade health monitoring, metrics, and structured logging across services.
- Hardened retries/backoff per engine and clearer error surfacing.
- CI/CD with automated tests, linting, and sample corpus regression runs.
- Optional auth/rate limiting on the API and per-tenant quotas.
