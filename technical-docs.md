# MultiAV Technical Documentation

## Overview
MultiAV is a FastAPI-based multi-engine malware scanning service. It exposes REST endpoints for uploading files and retrieving scan results, orchestrates asynchronous scanning jobs via Celery, and aggregates normalized findings from ClamAV, Windows Defender, and YARA engines. Persistent state is stored in PostgreSQL, while Redis backs Celery queues. File contents are stored on the local filesystem for repeatable scans.

## System architecture
- **API service** (`app/main.py`): FastAPI application that wires the v1 scan and results routers and initializes the database schema on startup.
- **Worker** (`app/workers/tasks.py`): Celery worker that executes scan jobs by invoking the orchestrator dispatcher.
- **Orchestrator** (`app/services/orchestrator/dispatcher.py`): Runs all engines from the dynamic registry and records per-engine results.
- **Aggregator** (`app/services/aggregator/*`): Normalizes engine payloads, performs weighted voting/confidence, and summarizes the final verdict exposed by the results API.
- **Persistence**:
  - PostgreSQL for relational data (files, scan jobs, engine results) configured in `docker-compose.yml`.
  - Local storage for uploaded binaries at `storage/files/<sha256>/original` (`app/services/storage.py`).
- **Message broker**: Redis for Celery broker and result backend (configured via environment variables and compose file).
- **Engines**: ClamAV (`app/services/engines/clamav`), Windows Defender (`app/services/engines/windows_defender` via the malice microservice), and YARA (`app/services/engines/yara`) provide detection coverage; results are normalized through the shared helper (`app/services/aggregator/normalize.py`).

## Data model
The SQLAlchemy models in `app/db/models.py` define three core tables:
- **File**: stores the SHA-256 hash, filesystem path, and upload timestamp.
- **ScanJob**: links to a file, tracks lifecycle status (`pending...`, `running...`, `done`), creation, and completion times.
- **EngineResult**: one per engine execution, capturing engine name, status, normalized result payload, and scan timestamp.

## Request flow
1. **Upload** (`POST /api/v1/scan/` in `app/api/v1/scan.py`):
   - Reads the upload, computes SHA-256, and persists the file under its hash. If the hash already exists, the latest job status is returned from cache.
   - For new files, creates `File` and `ScanJob` rows, then enqueues `run_scan(job_id, path)` via Celery.
2. **Worker execution** (`run_scan` in `app/workers/tasks.py`): calls the dispatcher with the job ID and file path.
3. **Engine dispatcher** (`app/services/orchestrator/dispatcher.py`):
   - Marks the job as `running...`.
   - Executes each engine (ClamAV, Windows Defender, YARA) sequentially, persisting an `EngineResult` with `success` or `error` status and normalized payload.
   - Marks the job `done` and records completion time.
4. **Result retrieval** (`GET /api/v1/results/{job_id}`): returns an aggregated verdict with weighted confidence/severity plus a `details` map of each engine result; 404 is raised for unknown jobs.

## Engine behaviors
### ClamAV
- Connects via TCP (`CLAMAV_HOST`/`CLAMAV_PORT`) or UNIX socket (`CLAMAV_SOCKET`) with retry logic.
- Attaches scan duration and engine version metadata, and gracefully reports connection errors.

### YARA
- Loads compiled rules from `rules/yara`. Prefers `index.yar` if present; otherwise compiles all `.yar`/`.yara` files, logging any compile failures.
- Matches produce rule, tags, and meta fields; returns normalized detections with match details and scan time. Family/category inference is handled centrally by the aggregator.

### Windows Defender (malice/windows-defender)
- Runs the upstream `malice/windows-defender` image in `web` mode (port 3993) and POSTs files to `/scan` with form field `malware`.
- Normalizes the plugin JSON (`infected`, `result`, `engine`, `updated`) into the shared schema; infected results are treated as high severity with full confidence.
- Configurable via `WINDEFENDER_HOST`, `WINDEFENDER_PORT`, and `WINDEFENDER_TIMEOUT` (defaults: `windows-defender`, `3993`, `120s`).
- Docker Hub status checked 2024-10-16: repository is marked `active` (not deprecated); last published update was 2022-09-25.

## Configuration
Default settings live in `app/core/config.py` and are overridden via environment variables. `docker-compose.yml` wires the defaults for local development (PostgreSQL, Redis, ClamAV, API, and worker containers) and mounts `./storage` into the app for persisted uploads.

### Engine registry (YAML-driven)
- Edit `config/engines.yaml` to enable/disable engines and adjust weights/timeouts without changing code.
- The `app` and `worker` containers mount `./config` read-only and also bake this file into the image; override the path with `ENGINE_CONFIG_PATH` if you want a different location.

## Running locally
1. Install Docker and Docker Compose.
2. From the repository root, run `docker compose up --build` to start PostgreSQL, Redis, ClamAV, Windows Defender (port 3993), the API server (port 8000), and the Celery worker. Updates to `config/engines.yaml` are picked up on container restart (no code rebuild required).
3. Submit files to `POST http://localhost:8000/api/v1/scan/` and poll `GET http://localhost:8000/api/v1/results/{job_id}` for statuses and results.

You can also open `http://localhost:8000/docs` and use the FastAPI Swagger UI to upload files through the interactive form, receive the returned UUIDs, and fetch results without crafting manual requests.

## Docker mirror for sanctioned regions
Run `./setup-docker-mirror.sh` to rewrite `/etc/docker/daemon.json` (uses `sudo`) so Docker pulls via `https://registry.docker.ir` as both an insecure registry and registry mirror. The script restarts Docker automatically to apply the change. This helps work around Docker Hub sanctions/blocks.
