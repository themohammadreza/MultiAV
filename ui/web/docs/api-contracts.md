# API Contracts

## POST /api/v1/scan/
- **Request**: multipart/form-data with `file` (binary).
- **Response** (`ScanResponse`):
  - `job_id` (UUID)
  - `status`: `pending... | queued | running... | done | done_with_errors | error`
  - `cached`: boolean
  - optional `scanned_at` (ISO timestamp when served from cache)

## GET /api/v1/results/{job_id}
- **Response** (`ResultSummary`):
  - `job_id`, `status`, `verdict`, `confidence`, `severity`, `severity_score`, `engine_count`
  - `started_at`, optional `completed_at`
  - `families`, `primary_family`, `categories`, `signatures`
  - `details`: object keyed by engine name with vendor-specific fields (e.g., `status`, `signature`, `message`, `detected`, `scanned_at`)

## GET /api/v1/ui/jobs/recent
- **Response** (`RecentJobsResponse`): `{ items: RecentJobItem[], count }` where each `RecentJobItem` has
  `job_id`, `status`, optional `verdict`, optional `severity`, optional `sha256`, `started_at`, optional `completed_at`.

## GET /api/v1/ui/engines/active
- **Response** (`ActiveEnginesResponse`): `{ engines: { engine, timeout?, weight? }[] }`.

These shapes are mirrored in `src/lib/api-types.ts` and consumed by `src/lib/api-client.ts`, enabling typed data access
throughout the UI.
