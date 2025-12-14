# AGENTS GUIDE

Guidance for AI contributors working on MultiAV. Follow this to avoid breaking core flows.

## Project snapshot
- Multi-engine malware scanner: FastAPI API (`app/main.py`), Celery workers (`app/workers/tasks.py`), AV engines (ClamAV, YARA, Windows Defender), storage abstraction (`app/services/storage.py`), and Streamlit UI (`ui/streamlit_app.py`).
- Persistence: PostgreSQL (metadata) and Redis (Celery broker/result). Uploaded files go to S3/MinIO by default with TTL/size caps; local filesystem backend is available for single-container/dev.
- Orchestration: uploads enqueue a Celery chord (fan-out per engine, fan-in finalize). Aggregation lives in `app/services/aggregator`.
- Terminal statuses: `done`, `done_with_errors`, `error`. Anything else is non-terminal and may still be running.

## Invariants to keep
- Job IDs are UUIDs; reject/normalize invalid IDs before hitting APIs.
- One `EngineResult` per `(job_id, engine)`; updates should upsert, not duplicate.
- Job status progression: created -> `running...` -> terminal (`done` | `done_with_errors` | `error`). Terminal states should set `completed_at`.
- Engine registry is YAML-driven (`config/engines.yaml`) and may be mounted read-only; do not require code changes to toggle engines.
- Storage backend must always clean up via TTL/size caps for S3/MinIO; local backend keeps files on disk intentionally.

## Run the stack
- Preferred: `docker compose up --build` from repo root. Services: API (8000), Streamlit (8501), Postgres (55432 in compose), Redis (6380), ClamAV (3310), Windows Defender (3993), MinIO (9000/9001).
- Streamlit UI: `http://localhost:8501` after compose is up. API docs: `http://localhost:8000/docs`.
- Edit `config/engines.yaml` to enable/disable engines or change weights/timeouts; restart `app` and `worker` containers to apply.

## Local (non-docker) dev
- Python with a virtualenv; install deps: `pip install -r requirements.txt`.
- API: `uvicorn app.main:app --reload` (requires Postgres/Redis reachable per `app/core/config.py`).
- Streamlit: `streamlit run ui/streamlit_app.py` (configure via env vars or `st.secrets`: `API_BASE_URL`, `POLL_INTERVAL`, `REQUEST_TIMEOUT`, `MAX_UPLOAD_MB`, `FEATURE_HISTORY`).
- Without engine services, tests stub ClamAV; real scans need the engines running.

## Testing
- Full suite: `pytest`. Uses sqlite + in-memory Celery/Redis via `tests/conftest.py`; no external services required. Streamlit is optional but bundled in requirements.
- Faster unit-only run: `pytest -m 'not integration'`.
- Targeted: `pytest tests/test_ui_client.py`, `pytest tests/test_scan_workflow.py -m integration`, etc.
- Keep tests deterministic; prefer stubbing registry/engines via `tests.utils.configure_stub_engines` when adding behaviors.

## API surface (v1)
- `POST /api/v1/scan/` — multipart upload (`file` field); returns `{job_id, status, cached}`.
- `GET /api/v1/results/{job_id}` — aggregated verdict/severity/confidence plus per-engine `details`.
- `GET /api/v1/ui/jobs/recent` — recent jobs feed with filters.
- `GET /api/v1/ui/engines/active` — enabled engines with weights/timeouts.

## UI notes
- UI relies on `MultiAVClient` (`app/ui/client.py`) with terminal statuses set above.
- Upload tab enqueues scans and may poll non-terminal jobs; history view reads from `/ui/jobs/recent`.
- Keep session/query-param handling robust: invalid job IDs should not hammer the API; prefer fail-fast validation.

## Storage/config
- Key env vars: `STORAGE_BACKEND` (`local`|`s3`), `STORAGE_PATH`, `STORAGE_S3_ENDPOINT/REGION/BUCKET/ACCESS_KEY/SECRET_KEY`, `STORAGE_TTL_SECONDS`, `STORAGE_MAX_BYTES`.
- Engine endpoints: `CLAMAV_SOCKET`, `WINDEFENDER_HOST/PORT/TIMEOUT`.
- Database/broker: `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.

## Coding style and workflow
- Python/Streamlit code: prefer type hints, small helpers, and minimal but clear logging/errors. Preserve existing status strings and JSON shapes.
- Favor fast searches (`rg`) and targeted edits (`apply_patch`). Avoid destructive git commands.
- When adding features: update tests, keep aggregation/status logic consistent, and document new config knobs. For new engines, update registry loading and weights without breaking YAML-driven toggles.

## Common pitfalls
- Do not assume engines exist; guard for missing/disabled engines and persist errors without failing the whole job.
- Ensure Celery tasks always return and persist results even on timeouts/errors; use soft time limits with a grace window.
- Avoid storing large uploads in session by default; honor opt-in for re-upload caching in the UI.
