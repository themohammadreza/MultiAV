from typing import Dict, List, Tuple

from app.services.aggregator.confidence import weight_for_engine, weighted_confidence
from app.services.aggregator.family_detection import detect_families
from app.services.aggregator.normalize import SEVERITY_SCORES
from app.services.aggregator.voting import weighted_verdict


def _closest_severity_label(score: float) -> str:
    return min(SEVERITY_SCORES.items(), key=lambda item: abs(item[1] - score))[0]


def _aggregate_severity(results: List[Dict]) -> Tuple[str, float]:
    weighted_score = 0.0
    total_weight = 0.0

    for result in results:
        if (result.get("status") or "").lower() != "ok":
            continue
        weight = weight_for_engine(result.get("engine", ""))
        total_weight += weight
        weighted_score += float(result.get("severity_score") or 0.0) * weight

    if total_weight <= 0:
        baseline = SEVERITY_SCORES["informational"]
        return "informational", baseline

    avg_score = weighted_score / total_weight
    return _closest_severity_label(avg_score), avg_score


def _serialize_engine_result(record) -> Dict:
    payload = record.result or {}
    # Ensure essential fields are present
    payload.setdefault("engine", record.engine)
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

    verdict = weighted_verdict(results)
    severity_label, severity_score = _aggregate_severity(results)
    confidence = weighted_confidence(results, verdict)
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
