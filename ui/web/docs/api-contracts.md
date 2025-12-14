# API Contracts

## POST /api/v1/scan/
- **Request**: multipart/form-data with `file` (binary) and `cached` (boolean string).
- **Response** (`ScanResponse`):
  - `job_id` (UUID)
  - `status`: `pending | running | done | done_with_errors | error`
  - `cached`: boolean
  - `submitted_at`: ISO timestamp

## GET /api/v1/results/{job_id}
- **Response** (`ResultSummary`):
  - `job_id`, `cached`, `submitted_at`, optional `completed_at`
  - `status`: `pending | running | done | done_with_errors | error`
  - `verdict`: `clean | malicious | suspicious | unknown`
  - `engines`: array of `{ engine, status, signature?, version?, updated_at?, message? }`
  - `details`: object containing vendor-specific information

## GET /ui/jobs/recent
- **Response** (`RecentJobsResponse`): `{ jobs: RecentJob[] }` where `RecentJob` has
  `job_id`, `filename`, `size`, `submitted_at`, optional `verdict`, `cached`, `status`.

## GET /ui/engines/active
- **Response** (`ActiveEnginesResponse`): `{ engines: EngineStatus[] }` where `EngineStatus` has
  `name`, optional `version`, optional `updated_at`, and `status` of `active | inactive | degraded`.

These shapes are mirrored in `src/lib/api-types.ts` and consumed by `src/lib/api-client.ts`, enabling typed data access
throughout the UI.
