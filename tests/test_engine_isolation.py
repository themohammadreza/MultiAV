import pytest

from tests.utils import (
    configure_stub_engines,
    execute_scan,
    load_engine_results,
    stage_file_and_job,
    wait_for_job_status,
)
from app.services.aggregator.normalize import normalize_engine_result


@pytest.mark.integration
def test_engine_failure_does_not_block_others(monkeypatch, celery_worker_instance):
    def failing_runner(path: str):  # noqa: ARG001
        raise RuntimeError("engine boom")

    def ok_runner(path: str):
        return {"engine": "ok", "status": "ok", "detected": True, "verdict": "malicious"}

    configure_stub_engines(
        monkeypatch,
        {
            "bad-engine": {"runner": failing_runner, "timeout": 5, "weight": 0.5},
            "good-engine": {"runner": ok_runner, "timeout": 5, "weight": 0.5},
        },
    )

    job, path = stage_file_and_job(b"isolation content")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    assert job.status == "done_with_errors"

    statuses = {result.engine: result.status for result in load_engine_results(job.id)}

    assert statuses == {"bad-engine": "error", "good-engine": "success"}


@pytest.mark.integration
def test_engine_error_payload_marks_done_with_errors(monkeypatch, celery_worker_instance):
    def error_payload_runner(path: str):  # noqa: ARG001
        return normalize_engine_result(
            engine="clamav",
            status="error",
            detected=False,
            verdict="error",
            severity="informational",
            confidence=0.0,
            error="clamav unavailable",
        )

    def ok_runner(path: str):  # noqa: ARG001
        return normalize_engine_result(
            engine="yara",
            status="ok",
            detected=False,
            verdict="clean",
            severity="informational",
            confidence=0.0,
        )

    configure_stub_engines(
        monkeypatch,
        {
            "clamav": {"runner": error_payload_runner, "timeout": 5, "weight": 0.5},
            "yara": {"runner": ok_runner, "timeout": 5, "weight": 0.5},
        },
    )

    job, path = stage_file_and_job(b"payload error")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    assert job.status == "done_with_errors"

    statuses = {result.engine: result.status for result in load_engine_results(job.id)}

    assert statuses == {"clamav": "error", "yara": "success"}


@pytest.mark.integration
def test_all_engines_fail_sets_error_status(monkeypatch, celery_worker_instance):
    def failing_runner(path: str):  # noqa: ARG001
        raise RuntimeError("engine boom")

    configure_stub_engines(
        monkeypatch,
        {"broken": {"runner": failing_runner, "timeout": 5, "weight": 1.0}},
    )

    job, path = stage_file_and_job(b"all fail")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    assert job.status == "error"
