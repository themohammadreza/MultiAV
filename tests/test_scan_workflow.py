import pytest

from tests.utils import (
    configure_stub_engines,
    execute_scan,
    load_engine_results,
    stage_file_and_job,
    summarize_job,
    wait_for_job_status,
)


@pytest.mark.integration
def test_scan_workflow(monkeypatch, celery_worker_instance):
    def ok_runner(path: str):
        return {
            "engine": "ok-engine",
            "status": "ok",
            "detected": False,
            "verdict": "clean",
            "severity_score": 0.1,
        }

    configure_stub_engines(
        monkeypatch,
        {"ok-engine": {"runner": ok_runner, "timeout": 5, "weight": 0.5}},
    )

    job, path = stage_file_and_job(b"workflow content")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    assert job.status == "done"

    results = load_engine_results(job.id)
    assert len(results) == 1
    assert results[0].status == "success"

    summary = summarize_job(job.id)
    assert summary["status"] == "done"
    assert summary["engine_count"] == 1
    assert summary["verdict"] in {"clean", "unknown"}
