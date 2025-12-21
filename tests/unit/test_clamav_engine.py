from pathlib import Path

import pytest

from app.services.engines.clamav import engine


@pytest.mark.unit
def test_clamav_run_rejects_path_outside_allowed_roots(monkeypatch):
    called = False

    def fail_if_called(*args, **kwargs):  # noqa: ANN001 - test double
        nonlocal called
        called = True
        raise RuntimeError("connection should not be attempted")

    monkeypatch.setattr(engine, "get_connection", fail_if_called)

    unsafe_path = Path("/etc/passwd")
    result = engine.run(str(unsafe_path))

    assert result["status"] == "error"
    assert "Unsafe file path" in result["error"]
    assert called is False
