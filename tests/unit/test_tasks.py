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


@pytest.mark.unit
def test_run_engine_task_with_avast_runner(monkeypatch, tmp_path):
    """Exercise the Avast runner inside the engine task orchestration."""

    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"content")

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):  # noqa: D401 - test helper
            return self._payload

        @property
        def text(self):  # pragma: no cover - unused in happy path
            return str(self._payload)

    payload = {"avast": {"infected": False, "result": None, "version": "10.0"}}

    from app.services.engines.avast import engine as avast_engine

    monkeypatch.setattr(avast_engine.requests, "post", lambda url, files, timeout: FakeResponse(payload))

    recorded = {}

    def record_engine_result(job_id, engine_name, status, payload):  # noqa: ANN001
        recorded.update({
            "job_id": job_id,
            "engine": engine_name,
            "status": status,
            "payload": payload,
        })
        return True

    monkeypatch.setattr(tasks.dispatcher, "record_engine_result", record_engine_result)
    monkeypatch.setattr(tasks.dispatcher, "record_dispatch_error", lambda *args, **kwargs: None)

    class FakeStorage:
        def ensure_local_copy(self, location):  # noqa: ANN001 - signature mirrors real storage
            return location, lambda: None

    monkeypatch.setattr(tasks, "get_storage_service", lambda: FakeStorage())
    monkeypatch.setattr(
        tasks,
        "get_active_engines",
        lambda: {"avast": {"runner": avast_engine.run, "timeout": 15, "weight": 0.3}},
    )

    result = tasks.run_engine_task.run(
        job_id="job-avast",
        file_path=str(sample),
        engine_name="avast",
        timeout=15,
    )

    assert result == {"job_id": "job-avast", "engine": "avast", "status": "success"}
    assert recorded["status"] == "success"
    assert recorded["payload"]["verdict"] == "clean"
    assert recorded["payload"]["severity"] == "informational"
    assert recorded["payload"]["confidence"] == 0.0
