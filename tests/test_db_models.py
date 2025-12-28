import pytest
from sqlalchemy import create_engine, text
from sqlalchemy import inspect

from app.db.migrations import run_migrations

from app.db.models import APIKey, AdminUser, ApiKeyAuditLog, ApiKeyUsage, File, ScanJob


@pytest.mark.unit
def test_api_key_rate_limit_column_renamed():
    column_names = set(APIKey.__table__.columns.keys())

    assert "rate_limit_per_day" in column_names
    assert "rate_limit_per_miniute" not in column_names
    assert "revoked_at" in column_names
    assert "last_used_at" in column_names


@pytest.mark.unit
def test_scan_job_has_api_key_column():
    column_names = set(ScanJob.__table__.columns.keys())

    assert "api_key_id" in column_names


@pytest.mark.unit
def test_api_key_usage_columns():
    column_names = set(ApiKeyUsage.__table__.columns.keys())

    assert "api_key_id" in column_names
    assert "job_id" in column_names
    assert "created_at" in column_names
    assert "status" in column_names
    assert "verdict" in column_names

@pytest.mark.unit
def test_file_has_filename_column():
    column_names = set(File.__table__.columns.keys())

    assert "filename" in column_names


@pytest.mark.unit
def test_admin_user_columns():
    column_names = set(AdminUser.__table__.columns.keys())

    assert "username" in column_names
    assert "password_hash" in column_names
    assert "is_superadmin" in column_names
    assert "created_at" in column_names
    assert "updated_at" in column_names
    assert "last_login_at" in column_names


@pytest.mark.unit
def test_api_key_audit_log_columns():
    column_names = set(ApiKeyAuditLog.__table__.columns.keys())

    assert "api_key_id" in column_names
    assert "action" in column_names
    assert "performed_by_admin_id" in column_names
    assert "performed_by_username" in column_names
    assert "created_at" in column_names
    assert "metadata" in column_names


@pytest.mark.unit
def test_run_migrations_adds_api_key_id_column():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE scan_jobs ("
                "id TEXT PRIMARY KEY, "
                "file_id TEXT, "
                "status TEXT, "
                "created_at TIMESTAMP, "
                "completed_at TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE TABLE api_keys (id TEXT PRIMARY KEY)"))

    run_migrations(engine)

    inspector = inspect(engine)
    column_names = {col["name"] for col in inspector.get_columns("scan_jobs")}
    assert "api_key_id" in column_names


@pytest.mark.unit
def test_run_migrations_adds_filename_column():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE scan_jobs ("
                "id TEXT PRIMARY KEY, "
                "file_id TEXT, "
                "status TEXT, "
                "created_at TIMESTAMP, "
                "completed_at TIMESTAMP"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE files ("
                "id TEXT PRIMARY KEY, "
                "sha256 TEXT, "
                "path TEXT, "
                "uploaded_at TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE TABLE api_keys (id TEXT PRIMARY KEY)"))

    run_migrations(engine)

    inspector = inspect(engine)
    column_names = {col["name"] for col in inspector.get_columns("files")}
    assert "filename" in column_names


@pytest.mark.unit
def test_run_migrations_adds_api_key_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE api_keys (id TEXT PRIMARY KEY, name TEXT, key_hash TEXT)"))

    run_migrations(engine)

    inspector = inspect(engine)
    column_names = {col["name"] for col in inspector.get_columns("api_keys")}
    assert "revoked_at" in column_names
    assert "last_used_at" in column_names


@pytest.mark.unit
def test_run_migrations_creates_api_key_usages_table():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE scan_jobs ("
                "id TEXT PRIMARY KEY, "
                "file_id TEXT, "
                "status TEXT, "
                "created_at TIMESTAMP, "
                "completed_at TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE TABLE api_keys (id TEXT PRIMARY KEY, name TEXT, key_hash TEXT)"))

    run_migrations(engine)

    inspector = inspect(engine)
    assert "api_key_usages" in inspector.get_table_names()


@pytest.mark.unit
def test_run_migrations_creates_admin_users_table():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE scan_jobs (id TEXT PRIMARY KEY)"))

    run_migrations(engine)

    inspector = inspect(engine)
    assert "admin_users" in inspector.get_table_names()


@pytest.mark.unit
def test_run_migrations_creates_api_key_audit_logs_table():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE api_keys (id TEXT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE admin_users (id TEXT PRIMARY KEY)"))

    run_migrations(engine)

    inspector = inspect(engine)
    assert "api_key_audit_logs" in inspector.get_table_names()
