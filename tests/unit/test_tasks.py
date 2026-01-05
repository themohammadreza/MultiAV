import pytest

from app.services.engines.exceptions import ConnectionRetry
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


@pytest.mark.unit
def test_run_scan_prefers_local_file_path_when_available(monkeypatch, tmp_path):
    local_path = tmp_path / "sample.bin"
    local_path.write_bytes(b"content")

    class DummySig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def set(self, **kwargs):
            self.kwargs.update(kwargs)
            return self

    engine_calls: list[DummySig] = []

    def fake_run_engine_task_s(**kwargs):
        sig = DummySig(**kwargs)
        engine_calls.append(sig)
        return sig

    def fake_finalize_job_s(**kwargs):
        return DummySig(**kwargs)

    def fake_handle_failure_s(**kwargs):
        return DummySig(**kwargs)

    class FakeChord:
        def __init__(self, engine_tasks, callback):
            self.engine_tasks = engine_tasks
            self.callback = callback

        def apply_async(self):
            return type("Result", (), {"id": "chord-123"})

    monkeypatch.setattr(tasks, "chord", lambda engine_tasks, callback: FakeChord(engine_tasks, callback))
    monkeypatch.setattr(tasks.run_engine_task, "s", fake_run_engine_task_s)
    monkeypatch.setattr(tasks.finalize_job, "s", fake_finalize_job_s)
    monkeypatch.setattr(tasks.handle_chord_failure, "s", fake_handle_failure_s)
    monkeypatch.setattr(
        tasks, "get_active_engines", lambda: {"yara": {"runner": lambda path: {}, "timeout": 10, "weight": 0.5}}
    )
    monkeypatch.setattr(tasks.dispatcher, "mark_job_status", lambda job_id, status, completed=False: object())
    monkeypatch.setattr(tasks.dispatcher, "record_dispatch_error", lambda *args, **kwargs: None)

    result = tasks.run_scan("job-1", "remote-key", file_path=str(local_path))

    assert engine_calls
    assert engine_calls[0].kwargs["file_path"] == str(local_path)
    assert result == {"job_id": "job-1", "chord_id": "chord-123"}


@pytest.mark.unit
def test_run_engine_task_records_connection_retry(monkeypatch, tmp_path):
    provided_path = tmp_path / "sample.bin"
    provided_path.write_bytes(b"binary")

    calls: dict[str, object] = {"status": None, "payload": None}

    def fake_runner(path: str):
        raise ConnectionRetry("ClamAV", "connection refused", attempts=1)

    class FakeStorage:
        def ensure_local_copy(self, location):
            return location, lambda: None

    def fake_record_engine_result(job_id, engine_name, status, payload):  # noqa: ARG001
        calls["status"] = status
        calls["payload"] = payload
        return True

    monkeypatch.setattr(
        tasks, "get_active_engines", lambda: {"clamav": {"runner": fake_runner, "timeout": 5, "weight": 0.5}}
    )
    monkeypatch.setattr(tasks, "get_storage_service", lambda: FakeStorage())
    monkeypatch.setattr(tasks.dispatcher, "record_engine_result", fake_record_engine_result)
    monkeypatch.setattr(tasks.dispatcher, "record_dispatch_error", lambda *args, **kwargs: None)

    result = tasks.run_engine_task.run(
        job_id="job-123",
        file_path=str(provided_path),
        engine_name="clamav",
        timeout=5,
    )

    assert result["status"] == "error"
    assert calls["status"] == "error"
    assert calls["payload"]["connection_retry"] is True