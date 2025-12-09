import pytest

from tests.utils import (
    configure_stub_engines,
    execute_scan,
    load_engine_results,
    stage_file_and_job,
    wait_for_job_status,
)


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
