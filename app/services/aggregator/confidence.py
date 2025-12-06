from typing import Dict, List

ENGINE_WEIGHTS: Dict[str, float] = {
    # Heavier weights for engines with broad community trust
    "windows-defender": 0.34,
    "clamav": 0.26,
    "yara": 0.18,
}

DEFAULT_WEIGHT = 0.15


def weight_for_engine(engine: str) -> float:
    """Return the trust weight for an engine name (case-insensitive)."""
    key = (engine or "").lower()
    return ENGINE_WEIGHTS.get(key, DEFAULT_WEIGHT)


def weighted_confidence(results: List[Dict], final_verdict: str) -> float:
    """Aggregate confidence using engine trust weights and verdict alignment."""
    total_weight = 0.0
    confidence_weighted = 0.0
    support_weight = 0.0
    error_weight = 0.0

    for result in results:
        engine_name = result.get("engine", "")
        weight = weight_for_engine(engine_name)
        total_weight += weight

        status = (result.get("status") or "").lower()
        if status != "ok":
            error_weight += weight
            continue

        base_conf = float(result.get("confidence") or 0.0)
        confidence_weighted += base_conf * weight

        verdict = (result.get("verdict") or "").lower()
        if not verdict:
            verdict = "malicious" if result.get("detected") else "clean"

        if verdict == final_verdict:
            support_weight += weight
        elif final_verdict == "suspicious" and verdict == "malicious":
            support_weight += weight * 0.6
        elif final_verdict == "suspicious" and verdict == "clean":
            support_weight += weight * 0.4

    if total_weight <= 0:
        return 0.0

    avg_confidence = confidence_weighted / total_weight

    alignment_denominator = max(total_weight - error_weight, 1e-9)
    alignment = support_weight / alignment_denominator if alignment_denominator else 0.0

    # Penalize heavy error presence but never below a floor
    penalty = max(0.25, 1 - (error_weight / max(total_weight, 1e-9)) * 0.5)

    final = avg_confidence * alignment * penalty
    return max(0.0, min(1.0, final))
