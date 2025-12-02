import yara
import os
import time
from pathlib import Path
import re

from app.services.engines.schema import normalize_engine_result

# yara.py -> engines -> services -> app -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RULES_DIR = PROJECT_ROOT / "rules" / "yara"

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


def parse_signature(signature: str):
    """
    Split signature/rule names by common separators to infer family/category.
    Examples:
      - "invalid_trailer_structure" -> ("invalid", "trailer")
      - "Pdf.Dropper.Agent-7145616-0" -> ("Pdf", "Dropper")
    """
    if not signature:
        return None, None

    parts = [p for p in re.split(r"[-._]", signature) if p]
    family = parts[0] if parts else None
    category = parts[1] if len(parts) > 1 else None
    return family, category

def run(file_path: str):
    start = time.time()

    if not rules:
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

    all_matches = []
    for rule_set in rules:
        try:
            all_matches.extend(rule_set.match(filepath=file_path))
        except Exception as e:
            all_matches.append({"error": str(e)})

    # Filter out placeholder dict errors from match objects
    matches = [m for m in all_matches if not isinstance(m, dict)]

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

    if not malware_family or not category:
        inferred_family, inferred_category = parse_signature(signature or "")
        malware_family = malware_family or inferred_family
        category = category or inferred_category

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
