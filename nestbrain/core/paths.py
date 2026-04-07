from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Nestbrain"


def is_frozen_app() -> bool:
    """Return True when running from a bundled executable."""
    return bool(getattr(sys, "frozen", False))


def get_resource_root(default_root: str | Path | None = None) -> Path:
    """Resolve read-only bundled resources root for source and frozen modes."""
    if is_frozen_app():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent

    if default_root is not None:
        return Path(default_root).resolve()

    return Path(__file__).resolve().parents[1]


def get_distribution_root() -> Path:
    """Resolve the repo root in source mode or bundle root in frozen mode."""
    if is_frozen_app():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def get_user_data_dir(app_name: str = APP_NAME) -> Path:
    """Resolve writable per-user application data directory."""
    if os.name == "nt":
        base = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME") or (Path.home() / ".config"))

    target = base / app_name
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_logs_dir(app_name: str = APP_NAME) -> Path:
    path = get_user_data_dir(app_name) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_runs_dir(app_name: str = APP_NAME) -> Path:
    path = get_user_data_dir(app_name) / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path(app_name: str = APP_NAME) -> Path:
    return get_user_data_dir(app_name) / "config.json"


def get_registry_path(app_name: str = APP_NAME) -> Path:
    return get_user_data_dir(app_name) / "pipeline-registry.json"


def get_default_vault_root(app_name: str = APP_NAME) -> Path:
    """Resolve the canonical default vault root used on first launch."""
    return get_user_data_dir(app_name) / "My Brain"
