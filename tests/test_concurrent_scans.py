import pytest

from tests.utils import configure_stub_engines, load_engine_results, stage_file_and_job


@pytest.mark.integration
def test_concurrent_results_upsert(monkeypatch, celery_worker_instance):
    def ok_runner(path: str):  # noqa: ARG001
        return {"engine": "racer", "status": "ok", "detected": False, "verdict": "clean"}

    configure_stub_engines(
        monkeypatch,
        {"racer": {"runner": ok_runner, "timeout": 5, "weight": 1.0}},
    )

    job, path = stage_file_and_job(b"concurrent")

    from app.workers.tasks import run_engine_task

    run_engine_task.run(job_id=job.id, file_path=path, engine_name="racer", timeout=5)
    run_engine_task.run(job_id=job.id, file_path=path, engine_name="racer", timeout=5)

    results = load_engine_results(job.id)

    assert len(results) == 1
    assert results[0].engine == "racer"
