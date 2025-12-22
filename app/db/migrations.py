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
