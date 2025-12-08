#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-multiav-postgres}"
DB_USER="${DB_USER:-multiav_user}"
DB_NAME="${DB_NAME:-multiav_db}"

if ! docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  echo "Container $CONTAINER_NAME is not running." >&2
  exit 1
fi

docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
DELETE FROM engine_results;
DELETE FROM scan_jobs;
DELETE FROM files;
SQL

echo "Cleared engine_results, scan_jobs, and files tables in $DB_NAME on $CONTAINER_NAME."
