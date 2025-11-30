def normalize_engine_result(
    engine: str,
    detected: bool,
    signature: str = None,
    malware_family: str = None,
    category: str = None,
    severity: str = None,
    confidence: float = None,
    details: dict = None,
):
    return {
        "engine": engine,
        "detected": detected,
        "signature": signature,
        "malware_family": malware_family,
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "details": details or {}
    }
