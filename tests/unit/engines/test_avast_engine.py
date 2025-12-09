import requests
import pytest

from app.services.engines.avast import engine


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=None):
        self.payload = payload
        self.status_code = status_code
        self._text = text if text is not None else str(payload)

    def json(self):
        return self.payload

    @property
    def text(self):  # pragma: no cover - simple passthrough
        return self._text


@pytest.mark.unit
def test_avast_run_reports_infected_sample(monkeypatch, tmp_path):
    sample = tmp_path / "malware.bin"
    sample.write_bytes(b"malware")

    payload = {
        "avast": {
            "infected": True,
            "result": "EICAR-Test",
            "engine": "23.4.1",
            "updated": "2024-02-02",
        }
    }

    monkeypatch.setattr(requests, "post", lambda url, files, timeout: _FakeResponse(payload))

    result = engine.run(str(sample))

    assert result["status"] == "ok"
    assert result["detected"] is True
    assert result["verdict"] == "malicious"
    assert result["severity"] == "high"
    assert result["confidence"] == 1.0
    assert result["signature"] == "EICAR-Test"
    assert result["engine_version"] == "23.4.1"
    assert result["raw"] == payload


@pytest.mark.unit
def test_avast_run_reports_clean_sample(monkeypatch, tmp_path):
    sample = tmp_path / "clean.bin"
    sample.write_bytes(b"clean")

    payload = {"avast": {"infected": False, "result": None, "version": "2024.02"}}

    monkeypatch.setattr(requests, "post", lambda url, files, timeout: _FakeResponse(payload))

    result = engine.run(str(sample))

    assert result["status"] == "ok"
    assert result["detected"] is False
    assert result["verdict"] == "clean"
    assert result["severity"] == "informational"
    assert result["confidence"] == 0.0
    assert result["signature"] is None
    assert result["engine_version"] == "2024.02"


@pytest.mark.unit
def test_avast_run_surfaces_request_errors(monkeypatch, tmp_path):
    sample = tmp_path / "error.bin"
    sample.write_bytes(b"error")

    def raise_error(*args, **kwargs):  # noqa: ANN001
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "post", raise_error)

    result = engine.run(str(sample))

    assert result["status"] == "error"
    assert result["verdict"] == "error"
    assert result["severity"] == "informational"
    assert result["confidence"] == 0.0
    assert "Request error" in result["error"]
