import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

try:
    from app.services.aggregator.normalize import normalize_engine_result
except Exception:
    from schema import normalize_engine_result  # type: ignore


ENGINE_NAME = "Windows Defender"
ENGINE_TYPE = "Antivirus"
DEFAULT_HOST = "windows-defender"
DEFAULT_PORT = 3993
DEFAULT_TIMEOUT = 120
MIN_RECOMMENDED_TIMEOUT_SECONDS = 10.0
MAX_CONNECTION_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 1.0
CONNECT_TIMEOUT_SECONDS = 5.0
WARM_UP_TIMEOUT_SECONDS = 2.0


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


def warm_up(timeout_seconds: float = WARM_UP_TIMEOUT_SECONDS) -> bool:
    """Send a lightweight request to the Windows Defender service to reduce cold-start latency."""
    url = _build_url()
    try:
        requests.get(url, timeout=timeout_seconds, allow_redirects=False)
        return True
    except requests.RequestException as exc:
        logger.warning("Windows Defender warm-up failed: %s", exc)
        return False


def _get_timeout_seconds() -> float:
    raw_timeout = os.getenv("WINDEFENDER_TIMEOUT", str(DEFAULT_TIMEOUT))
    try:
        configured_timeout = float(raw_timeout)
    except ValueError:
        logger.warning("Invalid WINDEFENDER_TIMEOUT=%s, using default %ss", raw_timeout, DEFAULT_TIMEOUT)
        configured_timeout = float(DEFAULT_TIMEOUT)

    if configured_timeout < MIN_RECOMMENDED_TIMEOUT_SECONDS:
        logger.warning(
            "Windows Defender timeout %ss is below recommended floor %ss; cold starts may timeout early",
            configured_timeout,
            MIN_RECOMMENDED_TIMEOUT_SECONDS,
        )
    return max(configured_timeout, 0.1)


def _post_scan(path: Path, url: str, timeout: float) -> Tuple[requests.Response, int, Optional[int]]:
    """POST the file to Windows Defender with retry/backoff and a total timeout budget.

    Returns (response, attempts, first_latency_ms).
    """

    start_time = time.time()
    deadline = start_time + timeout
    first_latency_ms: Optional[int] = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, MAX_CONNECTION_ATTEMPTS + 1):
        remaining = deadline - time.time()
        if remaining <= 0:
            raise requests.Timeout(f"Windows Defender request exceeded {timeout}s budget before attempt {attempt}")

        # Apply a tuple timeout so the connect phase does not consume the full budget.
        connect_timeout = min(CONNECT_TIMEOUT_SECONDS, max(remaining, 0.1))
        per_attempt_timeout: float | tuple[float, float] = (connect_timeout, remaining)

        try:
            with open(path, "rb") as f:
                response = requests.post(
                    url,
                    files={"malware": f},
                    timeout=per_attempt_timeout,
                    allow_redirects=False,
                )

            if first_latency_ms is None:
                first_latency_ms = int((time.time() - start_time) * 1000)

            return response, attempt, first_latency_ms

        except (requests.ConnectionError, requests.Timeout) as exc:  # noqa: BLE001 - retry on cold-start refusal/timeout
            last_exc = exc
            if first_latency_ms is None:
                first_latency_ms = int((time.time() - start_time) * 1000)

            if attempt < MAX_CONNECTION_ATTEMPTS:
                delay = min(RETRY_BACKOFF_SECONDS * attempt, max(deadline - time.time(), 0))
                if delay <= 0:
                    break
                logger.warning(
                    "Windows Defender connection attempt %s/%s failed (%s), retrying in %ss (remaining budget=%ss)",
                    attempt,
                    MAX_CONNECTION_ATTEMPTS,
                    exc,
                    delay,
                    round(deadline - time.time(), 2),
                )
                time.sleep(delay)
                continue

            raise

    if last_exc:
        raise last_exc

    raise RuntimeError("Windows Defender request failed without raising an exception")


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
    timeout = _get_timeout_seconds()
    attempts = 0
    first_latency_ms: Optional[int] = None

    try:
        response, attempts, first_latency_ms = _post_scan(path, url, timeout)
    except requests.RequestException as exc:  # noqa: BLE001 - network/connection errors should be reported
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Windows Defender request failed after %sms (attempts=%s): %s",
            duration_ms,
            MAX_CONNECTION_ATTEMPTS,
            exc,
        )
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
                "request_attempts": attempts or MAX_CONNECTION_ATTEMPTS,
                "first_request_latency_ms": first_latency_ms,
                "timeout_seconds": timeout,
            },
        )

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Windows Defender first-request latency %sms over %s attempt(s); total duration %sms (timeout=%ss)",
        first_latency_ms,
        attempts,
        duration_ms,
        timeout,
    )

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
                "request_attempts": attempts,
                "first_request_latency_ms": first_latency_ms,
                "timeout_seconds": timeout,
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
                "request_attempts": attempts,
                "first_request_latency_ms": first_latency_ms,
                "timeout_seconds": timeout,
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
            "first_request_latency_ms": first_latency_ms,
            "request_attempts": attempts,
            "timeout_seconds": timeout,
            "updated_at": updated_at,
            "response_status": response.status_code,
        },
        raw=payload,
    )
