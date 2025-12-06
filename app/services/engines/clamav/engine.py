import clamd
import os
import time
import sys
import re

# Prefer TCP host:port when set (for container-to-container connections), otherwise fallback to local socket.
DEFAULT_SOCKET = os.getenv("CLAMAV_SOCKET", "/var/run/clamav/clamd.ctl")
DEFAULT_HOST = os.getenv("CLAMAV_HOST")
DEFAULT_PORT = int(os.getenv("CLAMAV_PORT", "3310"))

cd = None
DEFAULT_ENGINE_NAME = "ClamAV"
DEFAULT_ENGINE_TYPE = "Antivirus"
DEFAULT_VERSION = "1.4.3"

try:
    from app.services.engines.schema import normalize_engine_result
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


def get_connection(max_retries: int = 5, delay_seconds: int = 2):
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
                print(f"[ClamAV] Connection attempt {attempt + 1} failed, retrying...", file=sys.stderr)
                time.sleep(delay_seconds)
            else:
                raise RuntimeError(f"Failed to connect to clamd after {max_retries} attempts: {exc}") from exc

    raise RuntimeError(f"Failed to connect to clamd: {last_exc}")

def parse_signature(signature: str):
    """
    Split signature by common separators to derive family and category.
    Examples:
      - "Eicar-Signature" -> ("Eicar", "Signature")
      - "Win.Trojan.Zusy" -> ("Win", "Trojan")
      - "Pdf.Dropper.Agent-7145616-0" -> ("Pdf", "Dropper")
    """
    if not signature:
        return None, None

    parts = [p for p in re.split(r"[-.]", signature) if p]
    family = parts[0] if parts else None
    category = parts[1] if len(parts) > 1 else None
    return family, category


def _parse_response(response, start_time: float):
    scan_time_ms = int((time.time() - start_time) * 1000)
    status, signature = response.get('stream', (None, None))

    if status == "FOUND":
        malware_family, category = parse_signature(signature)
        return normalize_engine_result(
            engine=DEFAULT_ENGINE_NAME,
            engine_type=DEFAULT_ENGINE_TYPE,
            engine_version=DEFAULT_VERSION,
            status="ok",
            detected=True,
            signature=signature,
            malware_family=malware_family,
            category=category,
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
    FILE_PATH = os.path.abspath(file_path)

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

    except clamd.ConnectionError as e:
        # Attempt one reconnect in case the daemon restarted between scans
        try:
            client = get_connection()
            with open(FILE_PATH, 'rb') as f:
                response = client.instream(f)
            return _parse_response(response, start_time)
        except Exception as reconnection_exc:  # noqa: BLE001
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
                error=f"Connection error: {str(e)}; reconnection attempt failed: {reconnection_exc}",
                details={
                    "version": DEFAULT_VERSION,
                    "scan_time_ms": int((time.time() - start_time) * 1000),
                },
            )

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
