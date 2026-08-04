"""Path resolution that works in both dev and PyInstaller-bundled modes."""
from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_config_dir as _platform_user_config_dir

APP_NAME = "TrendRadar"
APP_AUTHOR = "TrendRadar"


def user_config_dir() -> Path:
    p = Path(_platform_user_config_dir(APP_NAME, APP_AUTHOR, roaming=True))
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