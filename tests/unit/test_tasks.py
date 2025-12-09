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


@pytest.mark.unit
def test_run_scan_fans_out_all_enabled_engines(monkeypatch):
    """Avast should appear in the fan-out when enabled in the registry."""

    engine_registry = {
        "clamav": {"runner": lambda path: {}, "timeout": 30, "weight": 0.35},
        "avast": {"runner": lambda path: {}, "timeout": 120, "weight": 0.30},
    }

    class DummySig:
        def __init__(self, name, kwargs):
            self.name = name
            self.kwargs = kwargs
            self.set_calls = []

        def set(self, **kwargs):
            self.set_calls.append(kwargs)
            return self

    class FakeResult:
        def __init__(self):
            self.id = "fake-chord-id"

    chord_calls = {}

    class FakeChord:
        def __init__(self, signatures, callback):
            chord_calls["engine_names"] = [sig.name for sig in signatures]
            chord_calls["timeouts"] = [sig.kwargs["timeout"] for sig in signatures]
            chord_calls["callback"] = callback

        def apply_async(self):
            chord_calls["applied"] = True
            return FakeResult()

    monkeypatch.setattr(tasks, "get_active_engines", lambda: engine_registry)
    monkeypatch.setattr(tasks.dispatcher, "mark_job_status", lambda job_id, status: {"id": job_id})
    monkeypatch.setattr(tasks.dispatcher, "record_dispatch_error", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks, "chord", lambda sigs, callback: FakeChord(sigs, callback))
    monkeypatch.setattr(tasks.run_engine_task, "s", lambda **kwargs: DummySig(kwargs["engine_name"], kwargs))
    monkeypatch.setattr(tasks.finalize_job, "s", lambda **kwargs: DummySig("finalize", kwargs))
    monkeypatch.setattr(tasks.handle_chord_failure, "s", lambda **kwargs: DummySig("handle", kwargs))

    result = tasks.run_scan(job_id="job-1", file_location="/tmp/file.bin")

    assert chord_calls["engine_names"] == list(engine_registry.keys())
    assert chord_calls["timeouts"] == [30, 120]
    assert chord_calls["callback"].name == "finalize"
    assert result["chord_id"] == "fake-chord-id"
