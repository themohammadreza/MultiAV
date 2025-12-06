import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

try:
    from app.services.aggregator.normalize import normalize_engine_result
except Exception:
    from schema import normalize_engine_result  # type: ignore


ENGINE_NAME = "Windows Defender"
ENGINE_TYPE = "Antivirus"
DEFAULT_HOST = "windows-defender"
DEFAULT_PORT = 3993
DEFAULT_TIMEOUT = 120


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


def _extract_result_block(payload: Any) -> Optional[Dict[str, Any]]:
    """
    Handle the various shapes returned by malice/windows-defender:
    - {"windows-defender": {...}}
    - {"windows_defender": {...}}
    - {"infected": true, "result": "...", ...}
    """
    if not isinstance(payload, dict):
        return None

    for key in ("windows-defender", "windows_defender"):
        block = payload.get(key)
        if isinstance(block, dict):
            return block

    # Fall back to a single-value dict or any nested dict with expected fields
    if len(payload) == 1:
        only_value = next(iter(payload.values()))
        if isinstance(only_value, dict):
            return only_value

    for value in payload.values():
        if isinstance(value, dict) and ("infected" in value or "result" in value):
            return value

    return None


def _build_url() -> str:
    host = os.getenv("WINDEFENDER_HOST", DEFAULT_HOST)
    port = int(os.getenv("WINDEFENDER_PORT", str(DEFAULT_PORT)))
    return f"http://{host}:{port}/scan"


def run(file_path: str):
    """
    Scan a file using the malice/windows-defender web service.
    """
    start_time = time.time()
    path = Path(file_path)
    if not path.is_file():
        return normalize_engine_result(
            engine=ENGINE_NAME,
            engine_type=ENGINE_TYPE,
            engine_version=None,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=0,
            error=f"File not found: {path}",
            details={"scan_time_ms": 0},
        )

    url = _build_url()
    timeout = float(os.getenv("WINDEFENDER_TIMEOUT", str(DEFAULT_TIMEOUT)))

    try:
        with open(path, "rb") as f:
            response = requests.post(url, files={"malware": f}, timeout=timeout)
    except requests.RequestException as exc:  # noqa: BLE001 - network/connection errors should be reported
        duration_ms = int((time.time() - start_time) * 1000)
        return normalize_engine_result(
            engine=ENGINE_NAME,
            engine_type=ENGINE_TYPE,
            engine_version=None,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=duration_ms,
            error=f"Request error: {exc}",
            details={
                "scan_time_ms": duration_ms,
                "url": url,
            },
        )

    duration_ms = int((time.time() - start_time) * 1000)

    if response.status_code != 200:
        return normalize_engine_result(
            engine=ENGINE_NAME,
            engine_type=ENGINE_TYPE,
            engine_version=None,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=duration_ms,
            error=f"Unexpected status code: {response.status_code}",
            details={
                "scan_time_ms": duration_ms,
                "url": url,
                "response_text": response.text,
            },
        )

    try:
        payload: Dict[str, Any] = response.json()
    except Exception as exc:  # noqa: BLE001 - report malformed payloads
        return normalize_engine_result(
            engine=ENGINE_NAME,
            engine_type=ENGINE_TYPE,
            engine_version=None,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=duration_ms,
            error=f"Failed to parse JSON response: {exc}",
            details={
                "scan_time_ms": duration_ms,
                "url": url,
                "response_text": response.text,
            },
        )

    result_block = _extract_result_block(payload)

    infected = _as_bool(result_block.get("infected")) if isinstance(result_block, dict) else False
    signature = result_block.get("result") if isinstance(result_block, dict) else None
    engine_version = str(result_block.get("engine")) if isinstance(result_block, dict) and result_block.get("engine") else None
    updated_at = result_block.get("updated") if isinstance(result_block, dict) else None

    severity = "high" if infected else "informational"
    confidence = 1.0 if infected else 0.0

    return normalize_engine_result(
        engine=ENGINE_NAME,
        engine_type=ENGINE_TYPE,
        engine_version=engine_version,
        status="ok",
        detected=infected,
        signature=signature,
        severity=severity,
        confidence=confidence,
        duration_ms=duration_ms,
        details={
            "scan_time_ms": duration_ms,
            "updated_at": updated_at,
            "response_status": response.status_code,
        },
        raw=payload,
    )
