"""Path resolution that works in both dev and PyInstaller-bundled modes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_config_dir as _platform_user_config_dir

APP_NAME = "TrendRadar"
APP_AUTHOR = "TrendRadar"

# Env override for the user config dir. Set by tests and available in
# production for portable installs. All desktop modules resolve through
# paths.py, so overriding here affects every consumer consistently.
_ENV_USER_CONFIG_DIR = "TRENDRADAR_USER_CONFIG_DIR"


def _user_config_dir() -> Path:
    override = os.environ.get(_ENV_USER_CONFIG_DIR, "")
    if override:
        return Path(override)
    return Path(_platform_user_config_dir(APP_NAME, APP_AUTHOR, roaming=True))


def user_config_dir() -> Path:
    p = _user_config_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_config_file() -> Path:
    return user_config_dir() / "user_config.yaml"


def audit_log_file() -> Path:
    return user_config_dir() / "audit.log"


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def webui_dir() -> Path:
    """Resolve the webui static directory. Works both dev and bundled."""
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    candidate = base / "webui"
    if not candidate.exists():
        raise FileNotFoundError(f"WebUI directory not found at {candidate}")
    return candidate