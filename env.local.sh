#!/usr/bin/env bash
# Source this file: `source ./env.local.sh`

export DATABASE_URL="postgresql://multiav_user:mohammad@localhost:55432/multiav_db"
export REDIS_URL="redis://localhost:6380/0"
export CLAMAV_HOST="localhost"
export CLAMAV_PORT="3310"
export CELERY_BROKER_URL="$REDIS_URL"
export CELERY_RESULT_BACKEND="$REDIS_URL"
export STORAGE_PATH="storage/files"

echo "Environment variables set for MultiAV (targets services exposed on localhost)."
