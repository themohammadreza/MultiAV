import pytest

from tests.utils import configure_stub_engines, execute_scan, stage_file_and_job, summarize_job, wait_for_job_status


@pytest.mark.integration
def test_verdict_boundary_conditions(monkeypatch, celery_worker_instance):
    configure_stub_engines(
        monkeypatch,
        {
            "mal": {
                "runner": lambda p: {
                    "engine": "mal",
                    "status": "ok",
                    "detected": True,
                    "verdict": "malicious",
                },
                "timeout": 5,
                "weight": 0.5,
            },
            "clean": {
                "runner": lambda p: {
                    "engine": "clean",
                    "status": "ok",
                    "detected": False,
                    "verdict": "clean",
                },
                "timeout": 5,
                "weight": 0.5,
            },
        },
    )

    job, path = stage_file_and_job(b"tie breaker")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)
    summary = summarize_job(job.id)

    assert job.status == "done"
    assert summary["verdict"] in {"malicious", "suspicious"}
