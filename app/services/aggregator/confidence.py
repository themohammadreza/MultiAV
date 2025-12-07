from typing import Dict, List, Optional

from app.services.orchestrator.registry import DEFAULT_ENGINE_WEIGHT

DEFAULT_WEIGHT = DEFAULT_ENGINE_WEIGHT


def weight_for_engine(engine: str, engine_weights: Optional[Dict[str, float]] = None) -> float:
    """Return the trust weight for an engine name (case-insensitive)."""
    key = (engine or "").lower()
    try:
        weight = float((engine_weights or {}).get(key, DEFAULT_WEIGHT))
        return DEFAULT_WEIGHT if weight <= 0 else weight
    except (TypeError, ValueError):
        return DEFAULT_WEIGHT


def weighted_confidence(
    results: List[Dict],
    final_verdict: str,
    engine_weights: Optional[Dict[str, float]] = None,
) -> float:
    """Aggregate confidence using engine trust weights and verdict alignment."""
    total_weight = 0.0
    confidence_weighted = 0.0
    support_weight = 0.0
    error_weight = 0.0

    for result in results:
        engine_name = result.get("engine_key") or result.get("engine", "")
        weight = weight_for_engine(engine_name, engine_weights)
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
