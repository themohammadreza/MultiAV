from unittest.mock import Mock, patch

import pytest

from app.workers import tasks


def _call_task(task, *args, **kwargs):
    # Celery replaces functions with Task objects; use .run when present for unit execution
    func = getattr(task, "run", task)
    return func(*args, **kwargs)


@pytest.mark.unit
@patch("app.workers.tasks.get_active_engines")
@patch("app.workers.tasks.dispatcher.record_dispatch_error")
@patch("app.workers.tasks.dispatcher.mark_job_status")
def test_run_scan_handles_missing_job(mock_mark, mock_record_error, mock_engines):
    mock_mark.return_value = None  # Job not found

    result = _call_task(tasks.run_scan, "fake-job-id", "/tmp/file")

    assert result["status"] == "error"
    assert "not found" in result["error"].lower()
    mock_record_error.assert_called_once()


@pytest.mark.unit
@patch("app.workers.tasks.dispatcher.record_engine_result", return_value=True)
@patch("app.workers.tasks.get_active_engines", return_value={})
def test_run_engine_task_handles_disabled_engine(mock_engines, mock_record):
    result = _call_task(
        tasks.run_engine_task,
        job_id="job-123",
        file_path="/tmp/test",
        engine_name="nonexistent-engine",
        timeout=30,
    )

    assert result["status"] == "error"
    assert "not configured" in result["error"].lower()
    mock_record.assert_called_once()


@pytest.mark.unit
@patch("app.workers.tasks.get_active_engines")
@patch("app.workers.tasks.dispatcher.mark_job_status")
@patch("app.workers.tasks.dispatcher.record_dispatch_error")
def test_run_scan_handles_no_engines_configured(mock_record_error, mock_mark, mock_engines):
    """When no engines are enabled, job should fail gracefully"""
    mock_job = Mock(id="job-123", status="pending")
    mock_mark.return_value = mock_job
    mock_engines.return_value = {}

    result = _call_task(tasks.run_scan, "job-123", "/tmp/file")

    assert result["status"] == "error"
    assert "no_engines" in result["error"] or "no engines" in result["error"].lower()
    mock_record_error.assert_called_once()


@pytest.mark.unit
@patch("app.workers.tasks.dispatcher.record_engine_result", return_value=True)
@patch("app.workers.tasks.get_active_engines")
@patch("app.workers.tasks.get_storage_service")
def test_run_engine_task_handles_timeout(mock_storage, mock_engines, mock_record):
    """SoftTimeLimitExceeded should be caught and recorded"""
    from celery.exceptions import SoftTimeLimitExceeded

    def timeout_runner(path):
        raise SoftTimeLimitExceeded()

    mock_engines.return_value = {
        "slow": {"runner": timeout_runner, "timeout": 5, "weight": 1.0}
    }

    mock_storage_instance = Mock()
    mock_storage_instance.ensure_local_copy.return_value = ("/tmp/test", lambda: None)
    mock_storage.return_value = mock_storage_instance

    result = _call_task(
        tasks.run_engine_task,
        job_id="job-123",
        file_path="/tmp/test",
        engine_name="slow",
        timeout=5,
    )

    assert result["status"] == "timeout"
    assert "time limit" in mock_record.call_args[0][3]["error"].lower()
