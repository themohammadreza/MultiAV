import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypedDict, Union

from app.services.engines.clamav.engine import run as clamav_run
from app.services.engines.windows_defender.engine import run as windows_defender_run
from app.services.engines.yara.yara import run as yara_run
from app.services.orchestrator.loader import EngineConfigError, load_engine_config

EngineRunner = Callable[[str], dict]

logger = logging.getLogger(__name__)


class EngineDefinition(TypedDict):
    runner: EngineRunner
    timeout: int
    weight: float


AVAILABLE_ENGINES: Dict[str, EngineRunner] = {
    "clamav": clamav_run,
    "yara": yara_run,
    "windows-defender": windows_defender_run,
}

DEFAULT_ENGINE_TIMEOUT = 120
DEFAULT_ENGINE_WEIGHT = 0.15


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return False


def _coerce_timeout(value: Any) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else DEFAULT_ENGINE_TIMEOUT
    except (TypeError, ValueError):
        return DEFAULT_ENGINE_TIMEOUT


def _coerce_weight(value: Any) -> float:
    try:
        parsed = float(value)
        return parsed if parsed > 0 else DEFAULT_ENGINE_WEIGHT
    except (TypeError, ValueError):
        return DEFAULT_ENGINE_WEIGHT


def _parse_engine(name: str, raw_config: Any) -> Optional[EngineDefinition]:
    runner = AVAILABLE_ENGINES.get(name)
    if not runner:
        return None

    config_block = raw_config if isinstance(raw_config, dict) else {}
    if not _as_bool(config_block.get("enabled", True)):
        return None

    timeout = _coerce_timeout(config_block.get("timeout", DEFAULT_ENGINE_TIMEOUT))
    weight = _coerce_weight(config_block.get("weight", DEFAULT_ENGINE_WEIGHT))

    return {
        "runner": runner,
        "timeout": timeout,
        "weight": weight,
    }


def _default_registry() -> Dict[str, EngineDefinition]:
    return {
        name: {
            "runner": runner,
            "timeout": DEFAULT_ENGINE_TIMEOUT,
            "weight": DEFAULT_ENGINE_WEIGHT,
        }
        for name, runner in AVAILABLE_ENGINES.items()
    }


def get_active_engines(config_path: Optional[Union[str, Path]] = None) -> Dict[str, EngineDefinition]:
    """Return a mapping of enabled engine names to their runner + metadata."""
    try:
        config = load_engine_config(config_path)
    except EngineConfigError as exc:
        logger.warning("Failed to load engine config, using defaults: %s", exc)
        return _default_registry()
    except Exception as exc:  # fallback to defaults on unexpected issues
        logger.exception("Unexpected error loading engine config; using defaults")
        return _default_registry()
    engines_config = config.get("engines") if isinstance(config, dict) else {}
    if not isinstance(engines_config, dict):
        engines_config = {}

    registry: Dict[str, EngineDefinition] = {}
    for name, raw_config in engines_config.items():
        normalized_name = str(name).lower()
        parsed = _parse_engine(normalized_name, raw_config)
        if parsed:
            registry[normalized_name] = parsed

    if not registry:
        return _default_registry()

    return registry


def get_engine_weights(
    engine_registry: Optional[Dict[str, EngineDefinition]] = None,
    *,
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, float]:
    """Extract a simple name → weight mapping."""
    registry = engine_registry or get_active_engines(config_path)
    return {name: meta["weight"] for name, meta in registry.items()}
