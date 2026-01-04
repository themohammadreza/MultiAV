#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-multiav-postgres}"
DB_USER="${DB_USER:-multiav_user}"
DB_NAME="${DB_NAME:-multiav_db}"
CLEAR_MODE="${CLEAR_MODE:-verdict}"
PSQL_FLAGS=(-X -tA)

if ! docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  echo "Container $CONTAINER_NAME is not running." >&2
  exit 1
fi

has_api_key_usages="$(
  docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" "${PSQL_FLAGS[@]}" -c \
    "SELECT to_regclass('public.api_key_usages') IS NOT NULL;" | tr -d '[:space:]'
)"
has_verdict_column="$(
  docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" "${PSQL_FLAGS[@]}" -c \
    "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='api_key_usages' AND column_name='verdict');" | tr -d '[:space:]'
)"

if [[ "$CLEAR_MODE" == "all" ]] || [[ "$has_api_key_usages" != "t" ]] || [[ "$has_verdict_column" != "t" ]]; then
  docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
DELETE FROM api_key_usages;
DELETE FROM engine_results;
DELETE FROM scan_jobs;
DELETE FROM files;
SQL
  echo "Cleared api_key_usages, engine_results, scan_jobs, and files tables in $DB_NAME on $CONTAINER_NAME."
  exit 0
fi

docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
WITH target_jobs AS (
    SELECT scan_jobs.id, scan_jobs.file_id
    FROM scan_jobs
    JOIN api_key_usages ON api_key_usages.job_id = scan_jobs.id
    WHERE LOWER(api_key_usages.verdict) IN ('malicious', 'suspicious')
),
deleted_usages AS (
    DELETE FROM api_key_usages
    WHERE job_id IN (SELECT id FROM target_jobs)
    RETURNING job_id
),
deleted_results AS (
    DELETE FROM engine_results
    WHERE job_id IN (SELECT id FROM target_jobs)
    RETURNING job_id
),
deleted_jobs AS (
    DELETE FROM scan_jobs
    WHERE id IN (SELECT id FROM target_jobs)
    RETURNING file_id
),
deleted_files AS (
	DELETE FROM files
WHERE id IN (SELECT file_id FROM deleted_jobs)
  AND NOT EXISTS (
      SELECT 1
      FROM scan_jobs
      WHERE scan_jobs.file_id = files.id
  )
    RETURNING id
)
SELECT
    (SELECT COUNT(*) FROM target_jobs) AS jobs_targeted,
    (SELECT COUNT(*) FROM deleted_usages) AS api_key_usages_deleted,
    (SELECT COUNT(*) FROM deleted_results) AS engine_results_deleted,
    (SELECT COUNT(*) FROM deleted_jobs) AS scan_jobs_deleted,
    (SELECT COUNT(*) FROM deleted_files) AS files_deleted;
SQL

echo "Cleared malicious/suspicious scan data in $DB_NAME on $CONTAINER_NAME."

