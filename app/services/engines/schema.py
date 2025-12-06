from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

SEVERITY_LEVELS = ["informational", "low", "medium", "high", "critical"]
SEVERITY_SCORES = {
    "informational": 0.1,
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}
ENGINE_STATUSES = ["ok", "error"]
VERDICTS = ["clean", "malicious", "suspicious", "error", "unknown"]


class EngineResultModel(BaseModel):
    engine: str
    engine_version: Optional[str] = None
    engine_type: Optional[str] = None
    status: str = Field(default="ok")
    detected: bool
    verdict: str
    severity: str
    severity_score: float
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    signature: Optional[str] = None
    malware_family: Optional[str] = None
    category: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    details: Dict[str, Any] = Field(default_factory=dict)
    raw: Optional[Any] = None
    error: Optional[str] = None

    class Config:
        extra = "allow"


def _normalize_severity(severity: Optional[str]) -> str:
    if not severity:
        return "informational"
    sev = severity.lower()
    return sev if sev in SEVERITY_LEVELS else "informational"


def _clamp_confidence(confidence: Optional[float]) -> float:
    if confidence is None:
        return 0.0
    try:
        return max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        return 0.0


def normalize_engine_result(
    engine: str,
    detected: bool,
    signature: Optional[str] = None,
    malware_family: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    confidence: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
    *,
    engine_version: Optional[str] = None,
    engine_type: Optional[str] = None,
    status: Optional[str] = None,
    verdict: Optional[str] = None,
    duration_ms: Optional[int] = None,
    raw: Optional[Any] = None,
    error: Optional[str] = None,
):
    normalized_severity = _normalize_severity(severity)
    severity_score = SEVERITY_SCORES[normalized_severity]

    normalized_status = (status or "ok").lower()
    if error:
        normalized_status = "error"
    if normalized_status not in ENGINE_STATUSES:
        normalized_status = "error" if error else "ok"

    normalized_confidence = _clamp_confidence(confidence)

    if normalized_status == "error":
        normalized_verdict = "error"
    else:
        inferred_verdict = "malicious" if detected else "clean"
        normalized_verdict = (verdict or inferred_verdict).lower()
        if normalized_verdict not in VERDICTS:
            normalized_verdict = inferred_verdict

    payload = EngineResultModel(
        engine=engine,
        engine_version=engine_version,
        engine_type=engine_type,
        status=normalized_status,
        detected=detected,
        verdict=normalized_verdict,
        severity=normalized_severity,
        severity_score=severity_score,
        confidence=normalized_confidence,
        signature=signature,
        malware_family=malware_family,
        category=category,
        duration_ms=duration_ms,
        details=details or {},
        raw=raw,
        error=error,
    )
    try:
        return payload.model_dump()
    except AttributeError:
        return payload.dict()
