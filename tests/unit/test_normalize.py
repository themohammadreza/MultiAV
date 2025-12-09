import pytest

from app.services.aggregator import normalize


@pytest.mark.unit
@pytest.mark.parametrize(
    "detected,severity,status,confidence,verdict,expected",
    [
        (True, "UNKNOWN", "WEIRD", "abc", "strange", ("informational", "ok", 0.0, "malicious")),
        (False, None, None, None, None, ("informational", "ok", 0.0, "clean")),
    ],
)
def test_normalize_engine_result_defaults_and_clamps(
    detected, severity, status, confidence, verdict, expected
):
    normalized = normalize.normalize_engine_result(
        engine="test",
        detected=detected,
        severity=severity,
        status=status,
        confidence=confidence,
        verdict=verdict,
    )

    assert normalized["severity"] == expected[0]
    assert normalized["status"] == expected[1]
    assert normalized["confidence"] == expected[2]
    assert normalized["verdict"] == expected[3]


@pytest.mark.unit
def test_normalize_engine_result_forces_error_verdict_when_error_present():
    normalized = normalize.normalize_engine_result(
        engine="test",
        detected=False,
        status="ok",
        verdict="clean",
        severity="low",
        error="boom",
        confidence=2,
    )

    assert normalized["status"] == "error"
    assert normalized["verdict"] == "error"
    assert normalized["confidence"] == 1.0  # clamped


@pytest.mark.unit
def test_normalize_returns_all_required_fields():
    """Ensures schema contract isn't broken"""
    result = normalize.normalize_engine_result(
        engine="test",
        detected=True,
    )

    required = {
        "engine",
        "status",
        "detected",
        "verdict",
        "severity",
        "severity_score",
        "confidence",
        "details",
    }
    assert required.issubset(result.keys())

    # Validate types
    assert isinstance(result["detected"], bool)
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["status"] in ["ok", "error"]


@pytest.mark.unit
def test_normalize_handles_none_values_gracefully():
    result = normalize.normalize_engine_result(
        engine="test",
        detected=None,  # Invalid type
        confidence=None,
        severity=None,
    )

    assert result["detected"] in [True, False]
    assert 0.0 <= result["confidence"] <= 1.0
