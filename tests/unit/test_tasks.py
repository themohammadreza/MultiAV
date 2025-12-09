import pytest

from app.workers import tasks


@pytest.mark.unit
def test_run_engine_task_uses_provided_file_path(monkeypatch, tmp_path):
    """Ensure engine tasks operate on the supplied file path without relying on undefined globals."""
    provided_path = tmp_path / "sample.bin"
    provided_path.write_bytes(b"binary")

    calls = {}

    def fake_runner(path: str):
        calls["runner_path"] = path
        return {"status": "ok"}

    class FakeStorage:
        def ensure_local_copy(self, location):
            calls["storage_path"] = location
            return location, lambda: None

    monkeypatch.setattr(
        tasks, "get_active_engines", lambda: {"clamav": {"runner": fake_runner, "timeout": 5, "weight": 0.5}}
    )
    monkeypatch.setattr(tasks, "get_storage_service", lambda: FakeStorage())
    monkeypatch.setattr(tasks.dispatcher, "record_engine_result", lambda *args, **kwargs: True)
    monkeypatch.setattr(tasks.dispatcher, "record_dispatch_error", lambda *args, **kwargs: None)

    result = tasks.run_engine_task.run(
        job_id="job-123",
        file_path=str(provided_path),
        engine_name="clamav",
        timeout=5,
    )

    assert result["status"] == "success"
    assert calls["storage_path"] == str(provided_path)
    assert calls["runner_path"] == str(provided_path)
