import re
from collections import Counter
from typing import Dict, List, Optional, Tuple


def _tokenize(signature: str) -> List[str]:
    return [part for part in re.split(r"[:/._-]", signature) if part]


def extract_family_category(signature: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Derive family and category hints from a signature string."""
    if not signature:
        return None, None

    parts = _tokenize(signature)
    family = parts[0] if parts else None
    category = parts[1] if len(parts) > 1 else None
    return family, category


def detect_families(results: List[Dict]) -> Dict[str, object]:
    """Aggregate family/category signals across engine signatures."""
    family_counter: Counter = Counter()
    category_counter: Counter = Counter()
    signatures = []

    for result in results:
        signature = result.get("signature")
        if not signature:
            continue

        signatures.append({"engine": result.get("engine"), "signature": signature})

        family, category = extract_family_category(signature)
        if family:
            family_counter[family] += 1
        if category:
            category_counter[category] += 1

    primary_family = family_counter.most_common(1)[0][0] if family_counter else None

    return {
        "primary_family": primary_family,
        "families": sorted(family_counter.keys()),
        "categories": sorted(category_counter.keys()),
        "signatures": signatures,
    }

