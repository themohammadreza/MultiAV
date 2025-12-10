import pytest

from app.services.aggregator import family_detection, voting


@pytest.mark.unit
def test_weighted_verdict_handles_errors_and_majority():
    results = [
        {"engine": "a", "status": "ok", "verdict": "malicious", "engine_key": "a"},
        {"engine": "b", "status": "error", "verdict": "clean", "engine_key": "b"},
        {"engine": "c", "status": "ok", "verdict": "clean", "engine_key": "c"},
    ]
    weights = {"a": 2.0, "b": 1.0, "c": 0.5}

    verdict = voting.weighted_verdict(results, engine_weights=weights)

    assert verdict == "malicious"  # malicious outweighs clean even with errors present


@pytest.mark.unit
def test_weighted_verdict_returns_error_when_no_valid_votes():
    results = [
        {"engine": "a", "status": "error"},
        {"engine": "b", "status": "timeout"},
    ]

    verdict = voting.weighted_verdict(results, engine_weights=None)

    assert verdict == "error"


@pytest.mark.unit
def test_detect_families_extracts_primary_and_categories():
    results = [
        {"engine": "a", "signature": "trojan.fake:generic"},
        {"engine": "b", "signature": "trojan.fake.variant"},
        {"engine": "c", "signature": "worm.sample"},
    ]

    families = family_detection.detect_families(results)

    assert families["primary_family"] == "trojan"
    assert "trojan" in families["families"]
    assert "fake" in families["categories"]
    assert len(families["signatures"]) == 3


@pytest.mark.unit
def test_detect_families_preserves_category_order():
    results = [
        {"engine": "engine-a", "signature": "malware.email.phishing"},
        {"engine": "engine-b", "signature": "trojan.loader.variant"},
        {"engine": "engine-c", "signature": "worm.autorun.sample"},
    ]

    families = family_detection.detect_families(results)

    assert families["categories"] == ["email", "loader", "autorun"]
