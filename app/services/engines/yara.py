import yara
import os
import time
from pathlib import Path

from app.services.engines.schema import normalize_engine_result

# yara.py -> engines -> services -> app -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RULES_DIR = PROJECT_ROOT / "rules" / "yara"

def load_rules():
    rule_files = {}

    if not RULES_DIR.is_dir():
        print(f"YARA rules directory not found: {RULES_DIR}")  # Debug
        return None

    for fname in os.listdir(RULES_DIR):
        if fname.endswith(".yar") or fname.endswith(".yara"):
            key = fname
            path = RULES_DIR / fname
            rule_files[key] = str(path)

    if not rule_files:
        print(f"No .yar/.yara files found in: {RULES_DIR}")  # Debug
        return None

    try:
        print(f"Loading YARA rules: {list(rule_files.keys())}")  # Debug
        return yara.compile(filepaths=rule_files)
    except yara.Error as e:
        print(f"YARA compile error: {e}")  # Debug
        return None

rules = load_rules()

def run(file_path: str):
    start = time.time()

    if rules is None:
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
        matches = rules.match(filepath=file_path)
    except Exception as e:
        return normalize_engine_result(
            engine="yara",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="error",
            confidence=0.0,
            details={"error": str(e)}
        )

    detected = bool(matches)

    if not detected:
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

    match_list = []
    for m in matches:
        match_list.append({
            "rule": getattr(m, "rule", None),
            "tags": getattr(m, "tags", []),
            "meta": getattr(m, "meta", {}),
        })

    primary = match_list[0] if match_list else {}
    signature = primary.get("rule") if isinstance(primary, dict) else None
    meta = primary.get("meta") if isinstance(primary, dict) else {}
    malware_family = meta.get("family") if isinstance(meta, dict) else None
    category = meta.get("category") if isinstance(meta, dict) else None

    return normalize_engine_result(
        engine="yara",
        detected=True,
        signature=signature,
        malware_family=malware_family,
        category=category,
        severity="high",
        confidence=1.0,
        details={
            "scan_time_ms": int((time.time() - start) * 1000),
            "matches": match_list
        }
    )

