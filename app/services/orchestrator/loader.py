import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

ENV_CONFIG_PATH = "ENGINE_CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "engines.yaml"


class EngineConfigError(Exception):
    """Raised when the engine configuration file cannot be parsed."""


def _resolve_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """Prefer an explicit path, then ENV_CONFIG_PATH, then the default location."""
    if config_path:
        return Path(config_path).expanduser()

    env_path = os.getenv(ENV_CONFIG_PATH)
    if env_path:
        return Path(env_path).expanduser()

    return DEFAULT_CONFIG_PATH


def load_engine_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load the engine registry YAML into a Python dict."""
    path = _resolve_path(config_path)

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    except Exception as exc:  # noqa: BLE001 - surface parsing issues to callers
        raise EngineConfigError(f"Failed to load engine config from {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise EngineConfigError(f"Engine config root must be a mapping, got {type(payload).__name__}")

    return payload
