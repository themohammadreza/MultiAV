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

    if "admin_users" not in table_names:
        _create_admin_users_table(engine)
    else:
        admin_user_columns = {col["name"] for col in inspector.get_columns("admin_users")}
        if "is_active" not in admin_user_columns:
            _add_admin_users_is_active(engine)

    if "api_key_audit_logs" not in table_names:
        _create_api_key_audit_logs_table(engine)


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


def _create_admin_users_table(engine: Engine) -> None:
    """Create the admin_users table if missing."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS admin_users ("
                    "id UUID PRIMARY KEY, "
                    "username TEXT NOT NULL UNIQUE, "
                    "password_hash TEXT NOT NULL, "
                    "is_superadmin BOOLEAN NOT NULL DEFAULT FALSE, "
                    "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
                    "created_at TIMESTAMP, "
                    "updated_at TIMESTAMP, "
                    "last_login_at TIMESTAMP"
                    ")"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_users_username ON admin_users (username)"))
            return

        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS admin_users ("
                "id TEXT PRIMARY KEY, "
                "username TEXT NOT NULL UNIQUE, "
                "password_hash TEXT NOT NULL, "
                "is_superadmin BOOLEAN NOT NULL DEFAULT 0, "
                "is_active BOOLEAN NOT NULL DEFAULT 1, "
                "created_at TIMESTAMP, "
                "updated_at TIMESTAMP, "
                "last_login_at TIMESTAMP"
                ")"
            )
        )


def _add_admin_users_is_active(engine: Engine) -> None:
    """Add is_active column to admin_users and backfill."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(
                text("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
            )
            conn.execute(text("UPDATE admin_users SET is_active = TRUE WHERE is_active IS NULL"))
            return

        conn.execute(text("ALTER TABLE admin_users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        conn.execute(text("UPDATE admin_users SET is_active = 1 WHERE is_active IS NULL"))


def _create_api_key_audit_logs_table(engine: Engine) -> None:
    """Create the api_key_audit_logs table if missing."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS api_key_audit_logs ("
                    "id UUID PRIMARY KEY, "
                    "api_key_id UUID NOT NULL, "
                    "action TEXT NOT NULL, "
                    "performed_by_admin_id UUID NOT NULL, "
                    "performed_by_username TEXT NOT NULL, "
                    "created_at TIMESTAMP, "
                    "metadata JSON, "
                    "CONSTRAINT fk_api_key_audit_logs_api_key FOREIGN KEY(api_key_id) REFERENCES api_keys (id), "
                    "CONSTRAINT fk_api_key_audit_logs_admin_user FOREIGN KEY(performed_by_admin_id) REFERENCES admin_users (id)"
                    ")"
                )
            )
            return

        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS api_key_audit_logs ("
                "id TEXT PRIMARY KEY, "
                "api_key_id TEXT NOT NULL, "
                "action TEXT NOT NULL, "
                "performed_by_admin_id TEXT NOT NULL, "
                "performed_by_username TEXT NOT NULL, "
                "created_at TIMESTAMP, "
                "metadata TEXT"
                ")"
            )
        )
