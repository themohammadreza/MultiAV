from typing import Dict, List, Optional

from app.services.aggregator.confidence import weight_for_engine


def weighted_verdict(
    results: List[Dict],
    engine_weights: Optional[Dict[str, float]] = None,
) -> str:
    """Compute a verdict via weighted voting across engines."""
    votes = {"malicious": 0.0, "clean": 0.0, "suspicious": 0.0}
    error_weight = 0.0

    for result in results:
        engine_name = result.get("engine_key") or result.get("engine", "")
        weight = weight_for_engine(engine_name, engine_weights)
        status = (result.get("status") or "").lower()
        if status != "ok":
            error_weight += weight
            continue

        verdict = (result.get("verdict") or "").lower()
        if not verdict:
            verdict = "malicious" if result.get("detected") else "clean"

        if verdict == "malicious":
            votes["malicious"] += weight
        elif verdict == "suspicious":
            votes["suspicious"] += weight
        elif verdict == "clean":
            votes["clean"] += weight
        else:
            votes["suspicious"] += weight * 0.5

    total_votes = sum(votes.values())
    if total_votes == 0:
        return "error" if error_weight else "unknown"

    malicious_ratio = votes["malicious"] / total_votes
    clean_ratio = votes["clean"] / total_votes
    suspicious_ratio = votes["suspicious"] / total_votes

    if malicious_ratio >= 0.5:
        return "malicious"
    if clean_ratio >= 0.6 and malicious_ratio < 0.3:
        return "clean"
    if suspicious_ratio >= 0.3 or (malicious_ratio >= 0.35 and clean_ratio >= 0.35):
        return "suspicious"

    return "malicious" if votes["malicious"] >= votes["clean"] else "clean"
