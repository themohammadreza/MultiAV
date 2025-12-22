import time

import pytest
import requests

from app.services.engines.windows_defender import engine as win_engine
from tests.utils import (
    configure_stub_engines,
    execute_scan,
    load_engine_results,
    stage_file_and_job,
    wait_for_job_status,
)


@pytest.mark.integration
def test_windows_defender_cold_start_persists_results(monkeypatch, celery_worker_instance):
    attempts: dict[str, int | float] = {"count": 0}
    monkeypatch.setenv("WINDEFENDER_TIMEOUT", "5")  # Ensure low budgets are respected
    monkeypatch.setattr(win_engine, "RETRY_BACKOFF_SECONDS", 0.01)
    monkeypatch.setattr(win_engine, "MAX_CONNECTION_ATTEMPTS", 2)

    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {"windows-defender": {"infected": False, "engine": "1.0", "result": "clean"}}

    def fake_post(url, files, timeout, allow_redirects=True):  # noqa: ARG001
        attempts["count"] += 1
        attempts["url"] = url
        attempts["timeout"] = timeout
        if attempts["count"] == 1:
            time.sleep(0.02)
            raise requests.ConnectionError("connection refused")
        return FakeResponse()

    monkeypatch.setattr(win_engine.requests, "post", fake_post)

    configure_stub_engines(
        monkeypatch,
        {"windows_defender": {"runner": win_engine.run, "timeout": 5, "weight": 0.5}},
    )

    job, path = stage_file_and_job(b"windows defender cold start")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    assert job.status == "done"

    results = load_engine_results(job.id)
    assert len(results) == 1
    assert results[0].status == "success"
    details = results[0].result.get("details", {})
    assert details.get("request_attempts") == 2
    assert details.get("first_request_latency_ms") is not None
    assert details.get("timeout_seconds") == 5.0
