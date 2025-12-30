import logging
import time
from pathlib import Path

import yara

from app.services.aggregator.normalize import (
    SEVERITY_LEVELS,
    normalize_engine_result,
)

# yara.py -> engines -> services -> app -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RULES_DIR = PROJECT_ROOT / "rules" / "yara"
ENGINE_NAME = "YARA"
ENGINE_TYPE = "Pattern Matcher"
ENGINE_VERSION = getattr(yara, "__version__", None)
logger = logging.getLogger(__name__)

def load_rules():
    if not RULES_DIR.is_dir():
        print(f"YARA rules directory not found: {RULES_DIR}")
        return None

    index = RULES_DIR / "index.yar"
    if index.exists():
        try:
            print(f"Loading YARA index: {index}")
            return [yara.compile(filepath=str(index))]
        except yara.Error as e:
            print(f"YARA compile error (index): {e}")

    compiled_sets = []
    failed_files = []

    rule_paths = list(RULES_DIR.rglob("*.yar")) + list(RULES_DIR.rglob("*.yara"))
    if not rule_paths:
        print(f"No .yar/.yara files found in: {RULES_DIR}")
        return None

    for path in sorted(rule_paths):
        try:
            compiled_sets.append(yara.compile(filepath=str(path)))
        except yara.Error as e:
            failed_files.append((path, str(e)))

    if failed_files:
        print(f"Skipped {len(failed_files)} YARA files due to errors:")
        for p, err in failed_files[:10]:
            print(f"  - {p}: {err}")
        if len(failed_files) > 10:
            print(f"  ... and {len(failed_files) - 10} more")

    if not compiled_sets:
        print("All YARA files failed to compile; no rules loaded.")
        return None

    print(f"Loaded {len(compiled_sets)} YARA rule sets (from {len(rule_paths)} files)")
    return compiled_sets

rules = load_rules()


def warm_up() -> bool:
    """Ensure YARA rules are loaded to reduce first-scan latency."""
    global rules
    if rules:
        return True

    try:
        rules = load_rules()
        return rules is not None
    except Exception as exc:  # noqa: BLE001 - warm-up should never crash startup
        logger.warning("YARA warm-up failed: %s", exc)
        return False


def run(file_path: str):
    start = time.time()

    if not rules:
        duration_ms = int((time.time() - start) * 1000)
        return normalize_engine_result(
            engine=ENGINE_NAME,
            engine_type=ENGINE_TYPE,
            engine_version=ENGINE_VERSION,
            status="error",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=duration_ms,
            error="No YARA rules loaded",
            details={"scan_time_ms": duration_ms},
        )

    matches = []
    errors = []
    for rule_set in rules:
        try:
            matches.extend(rule_set.match(filepath=file_path))
        except Exception as e:
            errors.append(str(e))

    detected = bool(matches)
    duration_ms = int((time.time() - start) * 1000)

    if not detected:
        return normalize_engine_result(
            engine=ENGINE_NAME,
            engine_type=ENGINE_TYPE,
            engine_version=ENGINE_VERSION,
            status="ok",
            detected=False,
            signature=None,
            malware_family=None,
            category=None,
            severity="informational",
            confidence=0.0,
            duration_ms=duration_ms,
            details={
                "match_count": 0,
                "matches": [],
                "scan_time_ms": duration_ms,
                "errors": errors,
            },
            raw={"errors": errors} if errors else None,
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

    meta_severity = (meta.get("severity") if isinstance(meta, dict) else None) or "high"
    severity = meta_severity.lower() if isinstance(meta_severity, str) else "high"
    if severity not in SEVERITY_LEVELS:
        severity = "high"

    meta_confidence = meta.get("confidence") if isinstance(meta, dict) else None
    confidence = None
    if isinstance(meta_confidence, (int, float)):
        confidence = meta_confidence
    elif isinstance(meta_confidence, str):
        try:
            confidence = float(meta_confidence)
        except ValueError:
            confidence = None
    confidence = 1.0 if confidence is None else confidence

    return normalize_engine_result(
        engine=ENGINE_NAME,
        engine_type=ENGINE_TYPE,
        engine_version=ENGINE_VERSION,
        status="ok",
        detected=True,
        signature=signature,
        severity=severity,
        confidence=confidence,
        duration_ms=duration_ms,
        details={
            "match_count": len(match_list),
            "matches": match_list,
            "scan_time_ms": duration_ms,
            "errors": errors,
        },
        raw={"matches": match_list, "errors": errors} if errors else {"matches": match_list},
    )
