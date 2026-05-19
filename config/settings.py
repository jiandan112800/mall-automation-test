from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"


def _deep_get(data: dict[str, Any], key_path: str, default: Any = None) -> Any:
    current: Any = data
    for key in key_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def load_settings() -> dict[str, Any]:
    """
    Load settings from config/config.yaml.
    Supports selecting environment by TEST_ENV (default: dev).
    """
    config_path = CONFIG_DIR / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    env_name = os.getenv("TEST_ENV", "dev")

    # New structure: environments.dev / environments.test ...
    if isinstance(raw.get("environments"), dict):
        env_config = _deep_get(raw, f"environments.{env_name}", {})
        common_config = raw.get("common", {})
        if not isinstance(common_config, dict):
            common_config = {}
        if not isinstance(env_config, dict):
            env_config = {}
        merged = {**common_config, **env_config}
        return merged

    # Backward compatible: flat yaml
    if isinstance(raw, dict):
        return raw
    return {}
