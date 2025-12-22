import pytest
from sqlalchemy import create_engine, text
from sqlalchemy import inspect

from app.db.migrations import run_migrations
from app.db.models import APIKey, ScanJob


@pytest.mark.unit
def test_api_key_rate_limit_column_renamed():
    column_names = set(APIKey.__table__.columns.keys())

    assert "rate_limit_per_day" in column_names
    assert "rate_limit_per_miniute" not in column_names


@pytest.mark.unit
def test_scan_job_has_api_key_column():
    column_names = set(ScanJob.__table__.columns.keys())

    assert "api_key_id" in column_names


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
