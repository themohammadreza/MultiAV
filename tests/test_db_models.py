import pytest

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
