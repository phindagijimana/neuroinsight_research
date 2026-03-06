"""
Platform credential persistence for auto-reconnect.

Stores per-platform credentials in the data directory so API workers can
re-establish platform sessions on demand.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = ".platform_config.json"


def _config_path() -> Path:
    data_dir = os.getenv("DATA_DIR", "./data")
    return Path(data_dir) / _CONFIG_FILENAME


def _load_all() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning("Could not read platform config from %s: %s", path, e)
        return {}


def _save_all(config: dict) -> None:
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2))
        if os.name == "posix":
            os.chmod(path, 0o600)
    except Exception as e:
        logger.warning("Could not write platform config to %s: %s", path, e)


def save_platform_config(platform: str, credentials: dict) -> None:
    config = _load_all()
    config[platform] = credentials
    _save_all(config)


def load_platform_config(platform: str) -> Optional[dict]:
    config = _load_all()
    creds = config.get(platform)
    return creds if isinstance(creds, dict) else None


def clear_platform_config(platform: str) -> None:
    config = _load_all()
    if platform in config:
        config.pop(platform, None)
        _save_all(config)
