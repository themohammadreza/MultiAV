# MultiAV Technical Documentation

## Overview
MultiAV is a FastAPI-based multi-engine malware scanning service. It exposes REST endpoints for uploading files and retrieving scan results, orchestrates asynchronous scanning jobs via Celery, and aggregates normalized findings from ClamAV, Windows Defender, and YARA engines. Persistent state is stored in PostgreSQL, while Redis backs Celery queues. File contents are stored in S3/MinIO by default with TTL/size-cap cleanup, with a local filesystem backend available for single-container development.

## System architecture
- **API service** (`app/main.py`): FastAPI application that wires the v1 scan and results routers and initializes the database schema on startup.
- **Worker** (`app/workers/tasks.py`): Celery worker that orchestrates a chord per scan (fan-out engine tasks, fan-in finalizer). Runs with a thread pool (`--pool=threads`, concurrency 4, prefetch 1) to better handle IO-bound engines.
- **Orchestrator** (`app/services/orchestrator/dispatcher.py`): Loads enabled engines from the registry, records one `EngineResult` per engine per job (upsert-safe), and finalizes job status/verdict.
- **Aggregator** (`app/services/aggregator/*`): Normalizes engine payloads, performs weighted voting/confidence, preserves first-seen category ordering, and summarizes the final verdict exposed by the results API.
- **Persistence**:
  - PostgreSQL for relational data (files, scan jobs, engine results) configured in `docker-compose.yml`.
  - Object storage (S3/MinIO by default via compose) for uploaded binaries with TTL and bucket-size cleanup; optional local storage fallback at `storage/files/<sha256>/original` for single-container dev.
- **Message broker**: Redis for Celery broker and result backend (configured via environment variables and compose file).
- **Engines**: ClamAV (`app/services/engines/clamav`), Windows Defender (`app/services/engines/windows_defender` via the malice microservice), and YARA (`app/services/engines/yara`) provide detection coverage; results are normalized through the shared helper (`app/services/aggregator/normalize.py`).

## Data model
The SQLAlchemy models in `app/db/models.py` define three core tables:
- **File**: stores the SHA-256 hash, filesystem path, and upload timestamp.
- **ScanJob**: links to a file, tracks lifecycle status (`pending...`, `running...`, `done`, `done_with_errors`, `error`), creation, and completion times.
- **EngineResult**: one per engine execution, capturing engine name, status, normalized result payload, and scan timestamp. A DB unique constraint (`uq_engine_results_job_engine`) enforces one row per `(job_id, engine)` to keep fan-out writes consistent.

## Request flow
1. **Upload** (`POST /api/v1/scan/` in `app/api/v1/scan.py`):
   - Reads the upload, computes SHA-256, and persists the file under its hash. If the hash already exists, the latest job status is returned from cache.
   - For new files, creates `File` and `ScanJob` rows, then enqueues `run_scan(job_id, path)` via Celery.
2. **Worker orchestration** (`run_scan` in `app/workers/tasks.py`):
   - Marks the job `running...`.
   - Builds a chord: one `run_engine_task` per enabled engine (parallel fan-out with per-engine time limits) plus a `finalize_job` callback (fan-in).
   - Schedules the chord; errors in scheduling or chord execution are recorded as orchestrator errors without leaving jobs stuck.
3. **Engine tasks** (`run_engine_task`):
   - Resolve the engine runner from the registry; if disabled/missing, record an error result and return.
   - Execute the engine with a Celery soft time limit; on success/error/timeout, upsert a single `EngineResult` row for `(job_id, engine)` with status and payload.
   - Small in-task retry protects persistence; failures to persist are recorded as orchestrator errors.
4. **Finalizer** (`finalize_job`):
   - Loads all results for the job, sets job status: `done` when all succeeded, `done_with_errors` when mixed, `error` when all failed/none.
   - Stamps `completed_at` and returns the aggregated summary (verdict, confidence, severity, families, per-engine `details`).
5. **Result retrieval** (`GET /api/v1/results/{job_id}`): returns the summary; 404 is raised for unknown job IDs.

## Storage lifecycle and retention
- The S3/MinIO backend uses `STORAGE_TTL_SECONDS` (default 180s) to delete aged objects and `STORAGE_MAX_BYTES` (default 5 MiB) to cap total bucket size.
- Cleanup runs immediately after uploads and through a background timer so TTL enforcement continues even when no new files arrive.
- When the size cap is exceeded, oldest objects are trimmed first after TTL deletions are applied.
- The local filesystem backend keeps files for repeatable scans and relies on manual cleanup.

## Engine behaviors
### ClamAV
- Connects via TCP (`CLAMAV_HOST`/`CLAMAV_PORT`) or UNIX socket (`CLAMAV_SOCKET`) with retry logic.
- Attaches scan duration and engine version metadata, and gracefully reports connection errors.
- Default timeout: 60s (tunable in `config/engines.yaml`).

### YARA
- Loads compiled rules from `rules/yara`. Prefers `index.yar` if present; otherwise compiles all `.yar`/`.yara` files, logging any compile failures.
- Rule set is curated to keep startup clean: invalid ELF rules referencing `is__elf` (Mirai Okiru/Satori, Rebirth Vulcan, TinyShell, Torte, Mandibule) and the missing `MALW_Mirai.yar` include were removed after repeated load warnings. If logs show “Skipped N YARA files due to errors”, fix or delete those rules before shipping.
- Matches produce rule, tags, and meta fields; returns normalized detections with match details and scan time. Family/category inference is handled centrally by the aggregator, which now preserves first-seen category ordering to align with signature lists.
- Default timeout: 300s to allow large rule sets to compile and scans to finish.

### Windows Defender (malice/windows-defender)
- Runs the upstream `malice/windows-defender` image in `web` mode (port 3993) and POSTs files to `/scan` with form field `malware`.
- Normalizes the plugin JSON (`infected`, `result`, `engine`, `updated`) into the shared schema; infected results are treated as high severity with full confidence.
- Configurable via `WINDEFENDER_HOST`, `WINDEFENDER_PORT`, and `WINDEFENDER_TIMEOUT` (defaults: `windows-defender`, `3993`, `300s`).
- Docker Hub status checked 2024-10-16: repository is marked `active` (not deprecated); last published update was 2022-09-25.

## Configuration
Default settings live in `app/core/config.py` and are overridden via environment variables. `docker-compose.yml` wires the defaults for local development (PostgreSQL, Redis, ClamAV, API, and worker containers) and points the app/worker at MinIO for object storage.

Key storage settings:
- `STORAGE_BACKEND` (`local` or `s3`) and `STORAGE_PATH` (local path).
- `STORAGE_TTL_SECONDS` and `STORAGE_MAX_BYTES` govern retention/size cleanup for the S3/MinIO backend.

### Engine registry (YAML-driven)
- Edit `config/engines.yaml` to enable/disable engines and adjust weights/timeouts without changing code.
- The `app` and `worker` containers mount `./config` read-only and also bake this file into the image; override the path with `ENGINE_CONFIG_PATH` if you want a different location.

## Running locally
1. Install Docker and Docker Compose.
2. From the repository root, run `docker compose up --build` to start PostgreSQL, Redis, ClamAV, Windows Defender (port 3993), the API server (port 8000), and the Celery worker. Updates to `config/engines.yaml` are picked up on container restart (no code rebuild required).
3. Submit files to `POST http://localhost:8000/api/v1/scan/` and poll `GET http://localhost:8000/api/v1/results/{job_id}` for statuses and results.

You can also open `http://localhost:8000/docs` and use the FastAPI Swagger UI to upload files through the interactive form, receive the returned UUIDs, and fetch results without crafting manual requests.

## Frontend notes
- Next.js UI (`ui/web`, port 3000) uses Mantine + TanStack Query. Uploads surface a live results panel beneath the form and stop polling once a terminal status is reached to avoid noisy refreshes. Signatures render flattened (no `[object Object]`).

## Docker mirror for sanctioned regions
Run `./setup-docker-mirror.sh` to rewrite `/etc/docker/daemon.json` (uses `sudo`) so Docker pulls via `https://registry.docker.ir` as both an insecure registry and registry mirror. The script restarts Docker automatically to apply the change. This helps work around Docker Hub sanctions/blocks.
