import pytest

from app.services.engines.windows_defender import engine


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"windows-defender": {"infected": True}}, {"infected": True}),
        ({"windows_defender": {"result": "abc"}}, {"result": "abc"}),
        ({"nested": {"infected": False, "result": "ok"}}, {"infected": False, "result": "ok"}),
        ({"only": {"other": "data"}}, {"other": "data"}),
    ],
)
def test_extract_result_block_handles_various_shapes(payload, expected):
    assert engine._extract_result_block(payload) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [(True, True), ("YES", True), ("0", False), (0, False), ("no", False)],
)
def test_as_bool_coercion(value, expected):
    assert engine._as_bool(value) is expected


@pytest.mark.unit
def test_run_handles_missing_file(tmp_path):
    missing = tmp_path / "missing.bin"

    result = engine.run(str(missing))

    assert result["status"] == "error"
    assert "File not found" in result.get("error", "")

@pytest.mark.unit
def test_run_returns_error_on_connection_retry(monkeypatch, tmp_path):
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"payload")

    def fake_post_scan(path, url, timeout):  # noqa: ARG001
        raise engine.ConnectionRetry(engine.ENGINE_NAME, "service unavailable", attempts=1)

    monkeypatch.setattr(engine, "_post_scan", fake_post_scan)
    monkeypatch.setattr(engine, "_build_url", lambda: "http://windows-defender:3993/scan")
    monkeypatch.setattr(engine, "_get_timeout_seconds", lambda: 1.0)

    result = engine.run(str(sample))

    assert result["status"] == "error"
    assert "service unavailable" in result.get("error", "")
    assert result["details"]["request_attempts"] == 1