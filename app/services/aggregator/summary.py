from typing import Dict, List, Tuple

from app.services.aggregator.confidence import weight_for_engine, weighted_confidence
from app.services.aggregator.family_detection import detect_families
from app.services.aggregator.normalize import SEVERITY_SCORES
from app.services.aggregator.voting import weighted_verdict
from app.services.orchestrator.registry import get_active_engines, get_engine_weights


def _closest_severity_label(score: float) -> str:
    return min(SEVERITY_SCORES.items(), key=lambda item: abs(item[1] - score))[0]


def _aggregate_severity(results: List[Dict], engine_weights: Dict[str, float]) -> Tuple[str, float]:
    weighted_score = 0.0
    total_weight = 0.0

    for result in results:
        if (result.get("status") or "").lower() != "ok":
            continue
        engine_name = result.get("engine_key") or result.get("engine", "")
        weight = weight_for_engine(engine_name, engine_weights)
        total_weight += weight
        weighted_score += float(result.get("severity_score") or 0.0) * weight

    if total_weight <= 0:
        baseline = SEVERITY_SCORES["informational"]
        return "informational", baseline

    avg_score = weighted_score / total_weight
    return _closest_severity_label(avg_score), avg_score


def _serialize_engine_result(record) -> Dict:
    payload = record.result or {}
    engine_key = record.engine or payload.get("engine")
    # Ensure essential fields are present
    if engine_key:
        payload["engine_key"] = engine_key
    payload.setdefault("engine", engine_key)
    payload.setdefault("status", "ok" if record.status == "success" else "error")
    payload.setdefault("detected", False)
    payload.setdefault("confidence", 0.0)
    return payload


def summarize_job(job, engine_results) -> Dict[str, object]:
    """Produce a single aggregated view for a ScanJob."""
    results = [_serialize_engine_result(r) for r in engine_results]

    if not results:
        return {
            "job_id": str(job.id),
            "status": job.status,
            "verdict": "pending",
            "confidence": 0.0,
            "severity": "informational",
            "severity_score": SEVERITY_SCORES["informational"],
            "engine_count": 0,
            "started_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "families": [],
            "primary_family": None,
            "categories": [],
            "signatures": [],
            "details": {},
        }

    engine_registry = get_active_engines()
    engine_weights = get_engine_weights(engine_registry)

    verdict = weighted_verdict(results, engine_weights)
    severity_label, severity_score = _aggregate_severity(results, engine_weights)
    confidence = weighted_confidence(results, verdict, engine_weights)
    families = detect_families(results)

    details = {result.get("engine", f"engine-{idx}"): result for idx, result in enumerate(results)}

    aggregated = {
        "job_id": str(job.id),
        "status": job.status,
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "severity": severity_label,
        "severity_score": round(severity_score, 3),
        "engine_count": len(results),
        "started_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "families": families.get("families"),
        "primary_family": families.get("primary_family"),
        "categories": families.get("categories"),
        "signatures": families.get("signatures"),
        "details": details,
    }

    return aggregated
