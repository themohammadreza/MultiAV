import pytest

from app.db.models import APIKey


@pytest.mark.unit
def test_api_key_rate_limit_column_renamed():
    column_names = set(APIKey.__table__.columns.keys())

    assert "rate_limit_per_day" in column_names
    assert "rate_limit_per_miniute" not in column_names
