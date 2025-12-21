import importlib
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypedDict, Union

from app.services.orchestrator.loader import EngineConfigError, load_engine_config

EngineRunner = Callable[[str], dict]
logger = logging.getLogger(__name__)


class _LazyEngineRunner:
    """Delay importing engine modules until the runner is invoked."""

    def __init__(self, module_path: str, attr: str = "run") -> None:
        self.module_path = module_path
        self.attr = attr
        self._runner: Optional[EngineRunner] = None

    def _load(self) -> Optional[EngineRunner]:
        if self._runner:
            return self._runner

        try:
            module = importlib.import_module(self.module_path)
        except ImportError:
            logger.warning("Engine module %s could not be imported", self.module_path)
            return None

        self._runner = getattr(module, self.attr, None)
        if not self._runner:
            logger.warning("Engine module %s missing %s callable", self.module_path, self.attr)
        return self._runner

    def warm_up(self) -> bool:
        """Eagerly import the engine module so expensive setup (e.g. YARA compile) happens at startup."""
        try:
            return self._load() is not None
        except Exception:  # noqa: BLE001 - warm-up should never crash startup
            logger.exception("Failed to warm up engine module %s", self.module_path)
            return False

    def __call__(self, file_path: str) -> dict:
        runner = self._load()
        if not runner:
            raise RuntimeError(f"Engine runner unavailable for {self.module_path}")
        return runner(file_path)


class EngineDefinition(TypedDict):
    runner: EngineRunner
    timeout: int
    weight: float


AVAILABLE_ENGINES: Dict[str, EngineRunner] = {
    "clamav": _LazyEngineRunner("app.services.engines.clamav.engine"),
    "yara": _LazyEngineRunner("app.services.engines.yara.yara"),
    "windows-defender": _LazyEngineRunner("app.services.engines.windows_defender.engine"),
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
    registry: Dict[str, EngineDefinition] = {}

    for name in AVAILABLE_ENGINES:
        parsed = _parse_engine(name, {})
        if parsed:
            registry[name] = parsed

    return registry


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


def warm_up_active_engines(config_path: Optional[Union[str, Path]] = None) -> Dict[str, bool]:
    """Eagerly import active engines so expensive module-level work is done during startup."""
    warmed: Dict[str, bool] = {}
    registry = get_active_engines(config_path)
    for name, meta in registry.items():
        runner = meta.get("runner")
        if isinstance(runner, _LazyEngineRunner):
            warmed[name] = runner.warm_up()
        else:
            warmed[name] = True
    return warmed


def get_engine_weights(
    engine_registry: Optional[Dict[str, EngineDefinition]] = None,
    *,
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, float]:
    """Extract a simple name → weight mapping."""
    registry = engine_registry or get_active_engines(config_path)
    return {name: meta["weight"] for name, meta in registry.items()}
