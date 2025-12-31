#!/usr/bin/env bash
# Source this file: `source ./env.local.sh`
# Optional helper for local (non-Docker) development; not used by Docker Compose.

export DATABASE_URL="postgresql://multiav_user:multiav_password@localhost:55432/multiav_db"
export REDIS_URL="redis://localhost:6380/0"
export CLAMAV_HOST="localhost"
export CLAMAV_PORT="3310"
export CELERY_BROKER_URL="$REDIS_URL"
export CELERY_RESULT_BACKEND="$REDIS_URL"
export STORAGE_BACKEND="local"
export STORAGE_PATH="storage/files"
# Object storage (used when STORAGE_BACKEND=s3)
export STORAGE_S3_ENDPOINT="http://localhost:9000"
export STORAGE_S3_BUCKET="multiav"
export STORAGE_S3_REGION="us-east-1"
export STORAGE_S3_ACCESS_KEY="minio_username"
export STORAGE_S3_SECRET_KEY="minio_password"
export STORAGE_S3_USE_SSL="false"

echo "Environment variables set for MultiAV (targets services exposed on localhost)."
