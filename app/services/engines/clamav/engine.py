import clamd
import logging
import os
import socket
import tempfile
import time
from pathlib import Path

from app.services.engines.exceptions import ConnectionRetry

# Prefer TCP host:port when set (for container-to-container connections), otherwise fallback to local socket.
DEFAULT_SOCKET = os.getenv("CLAMAV_SOCKET", "/var/run/clamav/clamd.ctl")
DEFAULT_HOST = os.getenv("CLAMAV_HOST")
DEFAULT_PORT = int(os.getenv("CLAMAV_PORT", "3310"))

cd = None
DEFAULT_ENGINE_NAME = "ClamAV"
DEFAULT_ENGINE_TYPE = "Antivirus"
DEFAULT_VERSION = "1.4.3"
WARM_UP_TIMEOUT_SECONDS = 2.0

logger = logging.getLogger(__name__)

try:
    from app.services.aggregator.normalize import normalize_engine_result
except Exception:
    # Fallback for execution in container path layout
    from schema import normalize_engine_result  # type: ignore


def _build_client():
    """
    Create a ClamAV client targeting either TCP or a UNIX socket.
    Using TCP by default makes it easy to connect to the dedicated ClamAV container.
    """
    host = os.getenv("CLAMAV_HOST", DEFAULT_HOST)
    socket_path = os.getenv("CLAMAV_SOCKET", DEFAULT_SOCKET)
    port = int(os.getenv("CLAMAV_PORT", str(DEFAULT_PORT)))

    if host:
        return clamd.ClamdNetworkSocket(host=host, port=port)

    return clamd.ClamdUnixSocket(path=socket_path)


def warm_up(timeout_seconds: float = WARM_UP_TIMEOUT_SECONDS) -> bool:
    """Warm up the ClamAV client by pinging the daemon with a short timeout."""
    host = os.getenv("CLAMAV_HOST", DEFAULT_HOST)
    socket_path = os.getenv("CLAMAV_SOCKET", DEFAULT_SOCKET)
    port = int(os.getenv("CLAMAV_PORT", str(DEFAULT_PORT)))

    try:
        if host:
            with socket.create_connection((host, port), timeout=timeout_seconds):
                pass
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout_seconds)
            try:
                sock.connect(socket_path)
            finally:
                sock.close()

        client = _build_client()
        client.ping()
        global cd
        cd = client
        return True
    except Exception as exc:  # noqa: BLE001 - warm-up should never crash startup
        logger.warning("ClamAV warm-up failed: %s", exc)
        return False


def get_connection(max_retries: int = 5):
    """Get clamd connection with retry logic."""
    global cd
    last_exc = None

    for attempt in range(max_retries):
        try:
            if cd is None:
                cd = _build_client()

            cd.ping()
            return cd
        except Exception as exc:  # noqa: BLE001 - we want to retry on anything connection-related
            last_exc = exc
            cd = None
            if attempt < max_retries - 1:
                logger.warning(
                    "ClamAV connection attempt %s/%s failed: %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                continue
            raise ConnectionRetry(
                DEFAULT_ENGINE_NAME,
                f"Failed to connect to clamd after {max_retries} attempts: {exc}",
                attempts=max_retries,
                last_exc=exc,
            ) from exc

    raise ConnectionRetry(
        DEFAULT_ENGINE_NAME,
        f"Failed to connect to clamd: {last_exc}",
        attempts=max_retries,
        last_exc=last_exc,
    )


def _is_safe_path(file_path: Path) -> bool:
    """Ensure the target file is within an expected directory to avoid traversal."""
    try:
        resolved = file_path.resolve()
    except Exception:
        return False

    allowed_roots = {Path(tempfile.gettempdir()).resolve()}
    storage_root = os.getenv("STORAGE_PATH", "storage/files")
    try:
        allowed_roots.add(Path(storage_root).resolve())
    except Exception:
        # If the storage path is invalid, fall back to temp-only allowlist
        pass

    return any(resolved == root or root in resolved.parents for root in allowed_roots)

def _parse_response(response, start_time: float):
    scan_time_ms = int((time.time() - start_time) * 1000)
    status, signature = response.get('stream', (None, None))

    if status == "FOUND":
        return normalize_engine_result(
            engine=DEFAULT_ENGINE_NAME,
            engine_type=DEFAULT_ENGINE_TYPE,
            engine_version=DEFAULT_VERSION,
            status="ok",
            detected=True,
            signature=signature,
            severity="high",
            confidence=1.0,
            duration_ms=scan_time_ms,
            details={
                "version": DEFAULT_VERSION,
                "scan_time_ms": scan_time_ms,
            },
            raw=response,
        )

    return normalize_engine_result(
        engine=DEFAULT_ENGINE_NAME,
        engine_type=DEFAULT_ENGINE_TYPE,
        engine_version=DEFAULT_VERSION,
        status="ok",
        detected=False,
        signature=None,
        malware_family=None,
        category=None,
        severity="informational",
        confidence=0.0,
        duration_ms=scan_time_ms,
        details={
            "version": DEFAULT_VERSION,
            "scan_time_ms": scan_time_ms,
        },
        raw=response,
    )


def run(file_path: str):
    """
    Scan a file using ClamAV daemon

    Returns normalized result dict per schema.py format
    """
    start_time = time.time()
    path_obj = Path(file_path)
    if not _is_safe_path(path_obj):
        return normalize_engine_result(
            engine=DEFAULT_ENGINE_NAME,
            engine_type=DEFAULT_ENGINE_TYPE,
            engine_version=DEFAULT_VERSION,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=0,
            error=f"Unsafe file path provided: {path_obj}",
            details={
                "version": DEFAULT_VERSION,
                "scan_time_ms": 0,
            },
        )

    FILE_PATH = str(path_obj.resolve())

    if not os.path.exists(FILE_PATH):
        return normalize_engine_result(
            engine=DEFAULT_ENGINE_NAME,
            engine_type=DEFAULT_ENGINE_TYPE,
            engine_version=DEFAULT_VERSION,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=0,
            error=f"File not found: {FILE_PATH}",
            details={
                "version": DEFAULT_VERSION,
                "scan_time_ms": 0,
            },
        )

    try:
        client = get_connection()
        with open(FILE_PATH, 'rb') as f:
            response = client.instream(f)
        return _parse_response(response, start_time)
    except ConnectionRetry:
        raise
    except clamd.ConnectionError as exc:
        raise ConnectionRetry(
            DEFAULT_ENGINE_NAME,
            f"ClamAV connection error: {exc}",
            attempts=1,
            last_exc=exc,
        ) from exc
    except Exception as e:
        return normalize_engine_result(
            engine=DEFAULT_ENGINE_NAME,
            engine_type=DEFAULT_ENGINE_TYPE,
            engine_version=DEFAULT_VERSION,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=int((time.time() - start_time) * 1000),
            error=str(e),
            details={
                "version": DEFAULT_VERSION,
                "scan_time_ms": int((time.time() - start_time) * 1000),
            },
        )

# Test function for standalone execution
if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        print(f"Testing ClamAV scan on: {test_file}")
        result = run(test_file)
        print(result)
    else:
        print("Usage: python engine.py <file_path>")
