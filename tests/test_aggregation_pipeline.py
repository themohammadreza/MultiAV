import pytest

from app.services.aggregator.normalize import normalize_engine_result
from tests.utils import configure_stub_engines, execute_scan, stage_file_and_job, summarize_job, wait_for_job_status


@pytest.mark.integration
def test_aggregation_pipeline_outputs(monkeypatch, celery_worker_instance):
    def malicious_runner(path: str):
        return normalize_engine_result(
            engine="alpha",
            detected=True,
            severity="high",
            confidence=0.9,
            verdict="malicious",
            signature="EICAR",
            malware_family="TestFamily",
            category="test",
        )

    def clean_runner(path: str):
        return normalize_engine_result(
            engine="beta",
            detected=False,
            severity="low",
            confidence=0.2,
            verdict="clean",
        )

    configure_stub_engines(
        monkeypatch,
        {
            "alpha": {"runner": malicious_runner, "timeout": 5, "weight": 0.7},
            "beta": {"runner": clean_runner, "timeout": 5, "weight": 0.3},
        },
    )

    job, path = stage_file_and_job(b"aggregate")
    execute_scan(job.id, path)

    job = wait_for_job_status(job.id)

    summary = summarize_job(job.id)

    assert summary["status"] == "done"
    assert summary["engine_count"] == 2
    assert summary["verdict"] == "malicious"
    assert 0.45 <= summary["confidence"] <= 1.0
    assert summary["severity"] in {"medium", "high"}
    assert "alpha" in summary["details"]
    assert summary["details"]["alpha"]["detected"] is True
    assert summary["details"]["beta"]["detected"] is False
