import pytest
from celery.exceptions import SoftTimeLimitExceeded

from tests.utils import (
    configure_stub_engines,
    execute_scan,
    load_engine_results,
    stage_file_and_job,
    wait_for_job_status,
)


@pytest.mark.integration
def test_engine_timeout_does_not_block_completion(monkeypatch, celery_worker_instance):
    def slow_runner(path: str):  # noqa: ARG001
        raise SoftTimeLimitExceeded()

    def fast_runner(path: str):  # noqa: ARG001
        return {"engine": "fast", "status": "ok", "detected": True, "verdict": "malicious"}

    configure_stub_engines(
        monkeypatch,
        {
            "slow": {"runner": slow_runner, "timeout": 1, "weight": 0.5},
            "fast": {"runner": fast_runner, "timeout": 5, "weight": 0.5},
        },
    )

    job, path = stage_file_and_job(b"timeout test")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id, timeout=15)
    assert job.status == "done_with_errors"

    statuses = {result.engine: result.status for result in load_engine_results(job.id)}
    assert statuses["slow"] == "timeout"
    assert statuses["fast"] == "success"
