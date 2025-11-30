import yara
import os
import time

from app.services.engines.schema import normalize_engine_result

RULES_DIR = "rules/yara"

def load_rules():
    rule_files = {}

    for file_name in os.listdir(RULES_DIR):
        if file_name.endswith(".yar") or file_name.endswith(".yara"):
            key = file_name
            path = os.path.join(RULES_DIR, file_name)

            rule_files[key] = path

    if not rule_files:
        return None

    
    return yara.compile(filepaths=rule_files)

rules = load_rules()

def run(file_path: str):
    start = time.time()

    if rules is none:
        return normalize_engine_result(
            engine="yara",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            details={"error": "No YARA rules loaded"}
        )

    try:
        matches = rules.match(file_path)

        detected = len(matches) > 0

        if not detected: # no matches
             return normalize_engine_result(
                engine="yara",
                detected=False,
                signature=None,
                malware_family=None,
                category=None,
                severity="low",
                confidence=0.0,
                details={
                    "scan_time_ms": int((time.time() - start) * 1000),
                    "matches": []
                }
            )



