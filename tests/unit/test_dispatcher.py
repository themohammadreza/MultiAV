import sys
import types
import uuid

import pytest

from app.services.orchestrator import dispatcher


@pytest.mark.unit
def test_run_all_engines_rejects_invalid_uuid(monkeypatch, tmp_path):
    calls = {"delay_called": False}

    def fake_delay(job_id, file_path):  # noqa: ANN001 - test double
        calls["delay_called"] = (job_id, file_path)
        return "queued"

    fake_tasks = types.SimpleNamespace(run_scan=types.SimpleNamespace(delay=fake_delay))
    monkeypatch.setitem(sys.modules, "app.workers.tasks", fake_tasks)

    result = dispatcher.run_all_engines("not-a-uuid", str(tmp_path / "file.bin"))

    assert result is None
    assert calls["delay_called"] is False


@pytest.mark.unit
def test_run_all_engines_enqueues_when_uuid_is_valid(monkeypatch, tmp_path):
    captured = {}

    def fake_delay(job_id, file_path):  # noqa: ANN001 - test double
        captured["args"] = (job_id, file_path)
        return "queued"

    fake_tasks = types.SimpleNamespace(run_scan=types.SimpleNamespace(delay=fake_delay))
    monkeypatch.setitem(sys.modules, "app.workers.tasks", fake_tasks)

    job_id = uuid.uuid4()
    file_path = tmp_path / "file.bin"

    result = dispatcher.run_all_engines(str(job_id), str(file_path))

    assert result == "queued"
    assert captured["args"] == (str(job_id), str(file_path))
