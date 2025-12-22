from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.aggregator import summary


class DummyResult(SimpleNamespace):
    pass


@pytest.mark.unit
def test_aggregate_severity_uses_weights_and_skips_errors():
    results = [
        {"engine": "a", "status": "ok", "severity_score": 1.0},
        {"engine": "b", "status": "error", "severity_score": 0.5},
        {"engine": "c", "status": "ok", "severity_score": 0.25},
    ]
    weights = {"a": 2.0, "c": 1.0, "missing": 5.0}

    label, score = summary._aggregate_severity(results, weights)

    assert label == "high"
    assert score == pytest.approx((1.0 * 2.0 + 0.25 * 1.0) / 3.0)


@pytest.mark.unit
def test_aggregate_severity_handles_all_errors():
    """All engines errored → should return safe default"""
    results = [
        {"engine": "a", "status": "error", "severity_score": 1.0},
        {"engine": "b", "status": "timeout", "severity_score": 0.5},
    ]
    weights = {"a": 1.0, "b": 1.0}

    label, score = summary._aggregate_severity(results, weights)

    assert label == "informational"  # Safe default when no valid data
    assert score == pytest.approx(0.1)  # SEVERITY_SCORES["informational"]


@pytest.mark.unit
def test_summarize_job_without_results_returns_pending():
    job = SimpleNamespace(
        id="123",
        status="queued",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        completed_at=None,
        file=SimpleNamespace(filename="empty.bin"),
    )

    summary_data = summary.summarize_job(job, [])

    assert summary_data["verdict"] == "pending"
    assert summary_data["engine_count"] == 0
    assert summary_data["severity"] == "informational"
    assert summary_data["filename"] == "empty.bin"


@pytest.mark.unit
def test_weighted_confidence_penalizes_errors():
    """High error rate should reduce confidence"""
    from app.services.aggregator.confidence import weighted_confidence

    results = [
        {"engine": "a", "status": "ok", "detected": True, "confidence": 1.0, "verdict": "malicious"},
        {"engine": "b", "status": "error", "detected": False, "confidence": 0.0, "verdict": "clean"},
        {"engine": "c", "status": "error", "detected": False, "confidence": 0.0, "verdict": "clean"},
    ]
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}

    conf = weighted_confidence(results, "malicious", weights)

    assert conf < 0.5  # Should be penalized despite 1 detection


@pytest.mark.unit
def test_summarize_job_aggregates_details(monkeypatch):
    job = SimpleNamespace(
        id="123",
        status="processing",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )

    engine_results = [
        DummyResult(
            engine="engine-a",
            status="success",
            scanned_at=datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc),
            result={
                "engine": "engine-a",
                "status": "ok",
                "detected": True,
                "verdict": "malicious",
                "confidence": 0.8,
                "severity_score": 1.0,
                "signature": "trojan/family",
            },
        ),
        DummyResult(
            engine="engine-b",
            status="success",
            scanned_at=datetime(2024, 1, 1, 0, 40, tzinfo=timezone.utc),
            result={
                "engine": "engine-b",
                "status": "ok",
                "detected": False,
                "verdict": "clean",
                "confidence": 0.4,
                "severity_score": 0.25,
            },
        ),
    ]

    monkeypatch.setattr(summary, "get_active_engines", lambda: {"engine-a": {"weight": 2}, "engine-b": {"weight": 0.5}})
    monkeypatch.setattr(summary, "get_engine_weights", lambda registry: {"engine-a": 2.0, "engine-b": 0.5})

    payload = summary.summarize_job(job, engine_results)

    assert payload["verdict"] == "malicious"
    assert payload["confidence"] > 0
    assert payload["families"] == ["trojan"]
    assert payload["primary_family"] == "trojan"
    assert payload["signatures"]
    assert set(payload["details"].keys()) == {"engine-a", "engine-b"}


@pytest.mark.unit
def test_summarize_job_handles_mixed_timezones(monkeypatch):
    job = SimpleNamespace(
        id="321",
        status="done",
        created_at=datetime(2024, 1, 1, 12, 0, 0),  # naive
        completed_at=datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
    )

    engine_results = [
        DummyResult(
            engine="engine-a",
            status="success",
            scanned_at=datetime(2024, 1, 1, 12, 5, 0),  # naive
            result={
                "engine": "engine-a",
                "status": "ok",
                "detected": False,
                "verdict": "clean",
                "confidence": 0.5,
                "severity_score": 0.1,
            },
        )
    ]

    monkeypatch.setattr(summary, "get_active_engines", lambda: {"engine-a": {"weight": 1.0}})
    monkeypatch.setattr(summary, "get_engine_weights", lambda registry: {"engine-a": 1.0})

    payload = summary.summarize_job(job, engine_results)

    assert payload["started_at"]
    assert payload["completed_at"]
    assert payload["details"]["engine-a"]["scanned_at"]

    parsed_start = datetime.fromisoformat(payload["started_at"])
    parsed_completed = datetime.fromisoformat(payload["completed_at"])
    parsed_scan = datetime.fromisoformat(payload["details"]["engine-a"]["scanned_at"])

    assert parsed_start.tzinfo is not None
    assert parsed_completed.tzinfo is not None
    assert parsed_scan.tzinfo is not None

    valid_offsets = {"+03:30", "+04:30"}
    assert any(payload["started_at"].endswith(offset) for offset in valid_offsets)
    assert any(payload["completed_at"].endswith(offset) for offset in valid_offsets)
    assert any(payload["details"]["engine-a"]["scanned_at"].endswith(offset) for offset in valid_offsets)


@pytest.mark.unit
def test_aggregate_severity_confidence_bounds():
    """Confidence should stay within [0.0, 1.0] bounds"""
    from app.services.aggregator.confidence import weighted_confidence

    results = [
        {"engine": "a", "status": "ok", "detected": True, "confidence": 2.0, "verdict": "malicious"},
        {"engine": "b", "status": "ok", "detected": True, "confidence": -0.5, "verdict": "malicious"},
    ]
    weights = {"a": 1.0, "b": 1.0}

    conf = weighted_confidence(results, "malicious", weights)

    assert 0.0 <= conf <= 1.0
