import clamd
import os

from app.core.config import settings
# connection to clamd
cd = clamd.ClamdUnixSocket(path=settings.CLAMAV_SOCKET)

def run(file_path: str):
    FILE_PATH = os.path.abspath(file_path)

    try:
        with open(FILE_PATH, 'rb') as f:
            response = cd.instream(f)
        # Example Response: {'/path/to/file': ('FOUND', 'Win.Trojan.Test')}
    except Exception as e:
        return {
            "file_path": FILE_PATH,
            "engine": "ClamAV",
            "malicious": None,
            "signature": None,
            "details": {"error": str(e)}
        }

    status, signature = response['stream']

    if status == "FOUND":
        return {
            "file_path": FILE_PATH ,
            "engine": "ClamAV",
            "malicious": True,
            "signature": signature,
            "confidence": 1.0,
            "details": response,
        }

    
    return {
        "file_path": FILE_PATH ,
        "engine": "ClamAV",
        "malicious": False,
        "signature": None,
        "confidence": 0.0,
        "details": response,
        }
