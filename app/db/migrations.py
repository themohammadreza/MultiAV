from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_migrations(engine: Engine) -> None:
    """Apply lightweight, idempotent migrations for environments without Alembic."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "scan_jobs" in table_names:
        columns = {col["name"] for col in inspector.get_columns("scan_jobs")}
        if "api_key_id" not in columns:
            _add_scan_jobs_api_key_id(engine, inspector)

    if "files" in table_names:
        file_columns = {col["name"] for col in inspector.get_columns("files")}
        if "filename" not in file_columns:
            _add_files_filename(engine)

    if "api_keys" in table_names:
        api_key_columns = {col["name"] for col in inspector.get_columns("api_keys")}
        if "revoked_at" not in api_key_columns:
            _add_api_keys_column(engine, "revoked_at", "TIMESTAMP")
        if "last_used_at" not in api_key_columns:
            _add_api_keys_column(engine, "last_used_at", "TIMESTAMP")

    if "api_key_usages" not in table_names:
        _create_api_key_usages_table(engine)


def _add_scan_jobs_api_key_id(engine: Engine, inspector) -> None:
    """Backfill the api_key_id column on scan_jobs if missing."""
    dialect = engine.dialect.name

    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(text('ALTER TABLE scan_jobs ADD COLUMN IF NOT EXISTS api_key_id UUID'))
            fks = inspector.get_foreign_keys("scan_jobs")
            has_fk = any(fk.get("referred_table") == "api_keys" and "api_key_id" in fk.get("constrained_columns", []) for fk in fks)
            if not has_fk:
                conn.execute(
                    text(
                        "ALTER TABLE scan_jobs "
                        "ADD CONSTRAINT fk_scan_jobs_api_key "
                        "FOREIGN KEY (api_key_id) REFERENCES api_keys (id)"
                    )
                )
            return

        # Fallback for SQLite and other dialects: add nullable column without FK to avoid dialect limitations.
        conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN api_key_id"))


def _add_files_filename(engine: Engine) -> None:
    """Add filename column to files to persist original upload name."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(text("ALTER TABLE files ADD COLUMN IF NOT EXISTS filename TEXT"))
            return

        conn.execute(text("ALTER TABLE files ADD COLUMN filename"))


def _add_api_keys_column(engine: Engine, column: str, column_type: str) -> None:
    """Add missing column to api_keys."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(text(f"ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS {column} {column_type}"))
            return

        conn.execute(text(f"ALTER TABLE api_keys ADD COLUMN {column}"))


def _create_api_key_usages_table(engine: Engine) -> None:
    """Create the api_key_usages table if missing."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS api_key_usages ("
                    "id UUID PRIMARY KEY, "
                    "api_key_id UUID NOT NULL, "
                    "job_id UUID NOT NULL, "
                    "created_at TIMESTAMP, "
                    "status TEXT NOT NULL, "
                    "verdict TEXT, "
                    "CONSTRAINT uq_api_key_usages_key_job UNIQUE (api_key_id, job_id), "
                    "CONSTRAINT fk_api_key_usages_api_key FOREIGN KEY(api_key_id) REFERENCES api_keys (id), "
                    "CONSTRAINT fk_api_key_usages_job FOREIGN KEY(job_id) REFERENCES scan_jobs (id)"
                    ")"
                )
            )
            return

        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS api_key_usages ("
                "id TEXT PRIMARY KEY, "
                "api_key_id TEXT NOT NULL, "
                "job_id TEXT NOT NULL, "
                "created_at TIMESTAMP, "
                "status TEXT NOT NULL, "
                "verdict TEXT, "
                "UNIQUE (api_key_id, job_id)"
                ")"
            )
        )
