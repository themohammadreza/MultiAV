import clamd
import os

from app.core.config import settings
from app.services.engines.schema import normalize_engine_result

# connection to clamd
cd = clamd.ClamdUnixSocket(path=settings.CLAMAV_SOCKET)

def run(file_path: str):
    FILE_PATH = os.path.abspath(file_path)

    try:
        with open(FILE_PATH, 'rb') as f:
            response = cd.instream(f)
        # Example Response: {'stream': ('FOUND', 'Win.Trojan.Test')}
    except Exception as e:
        return normalize_engine_result(
            engine="clamav",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="error",
            confidence=0.0,
            details={"error": str(e)}
        )

    status, signature = response['stream']

    if status == "FOUND":
        malware_family = None # will calculated after by signature check!
        category = None
        
        if signature: # extract category and malware family from signature
            parts = signature.split('.')
            if len(parts) > 1:
                category = parts[0]  # e.g., "Win", "Linux", "Android"
                malware_family = parts[1] if len(parts) > 1 else None  # e.g., "Trojan"
            else:
                malware_family = signature.split('-')[0]  # e.g., "Eicar" from "Eicar-Signature"
        
        return normalize_engine_result(
            engine="clamav",
            detected=True,
            signature=signature,
            malware_family=malware_family,
            category=category,
            severity="high",
            confidence=1.0,
            details=response
        )

    return normalize_engine_result(
        engine="clamav",
        detected=False,
        signature=None,
        malware_family=None,
        category=None,
        severity="low",
        confidence=0.0,
        details=response
    )