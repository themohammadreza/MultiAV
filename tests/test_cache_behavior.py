import pytest

from tests.utils import cache_lookup, configure_stub_engines, execute_scan, stage_file_and_job, wait_for_job_status


@pytest.mark.integration
def test_sha256_deduplication(monkeypatch, celery_worker_instance):
    def ok_runner(path: str):
        return {"engine": "cache-engine", "status": "ok", "detected": False, "verdict": "clean"}

    configure_stub_engines(
        monkeypatch,
        {"cache-engine": {"runner": ok_runner, "timeout": 5, "weight": 0.5}},
    )

    content = b"cached payload"

    job, path = stage_file_and_job(content)
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    assert job.status in {"done", "done_with_errors"}

    cached_job = cache_lookup(content)
    assert cached_job is not None
    assert str(cached_job.id) == str(job.id)
    assert cached_job.status == job.status
