"""
HPC Configuration Persistence

Saves and restores the last-used HPC/SSH connection parameters so the app
can auto-reconnect on restart without requiring the user to re-enter
credentials through the UI.

Config is stored as a simple JSON file in the data directory.
No secrets are stored -- SSH authentication uses the agent or key files.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = ".hpc_config.json"


def _config_path() -> Path:
    data_dir = os.getenv("DATA_DIR", "./data")
    return Path(data_dir) / _CONFIG_FILENAME


def save_hpc_config(
    backend_type: str,
    ssh_host: str,
    ssh_user: str,
    ssh_port: int = 22,
    work_dir: str = "~",
    partition: str = "general",
    account: Optional[str] = None,
    qos: Optional[str] = None,
    modules: Optional[str] = None,
) -> None:
    """Persist the current HPC connection config to disk."""
    cfg = {
        "backend_type": backend_type,
        "ssh_host": ssh_host,
        "ssh_user": ssh_user,
        "ssh_port": ssh_port,
        "work_dir": work_dir,
        "partition": partition,
        "account": account,
        "qos": qos,
        "modules": modules,
    }
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2))
        logger.info("HPC config saved to %s", path)
    except Exception as e:
        logger.warning("Could not save HPC config: %s", e)


def load_hpc_config() -> Optional[dict]:
    """Load persisted HPC config. Returns None if no config exists."""
    path = _config_path()
    if not path.exists():
        return None
    try:
        cfg = json.loads(path.read_text())
        if cfg.get("ssh_host") and cfg.get("ssh_user"):
            return cfg
    except Exception as e:
        logger.warning("Could not load HPC config from %s: %s", path, e)
    return None


def clear_hpc_config() -> None:
    """Remove persisted HPC config (e.g. on explicit disconnect)."""
    path = _config_path()
    try:
        if path.exists():
            path.unlink()
            logger.info("HPC config cleared")
    except Exception as e:
        logger.warning("Could not clear HPC config: %s", e)
