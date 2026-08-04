"""System-level endpoints: status, info, version.

Uses inline lazy loaders for paths/config_store to avoid the eager
`trendradar/__init__.py` chain (which imports litellm). Every cross-module
reference is resolved via importlib so that this module is importable in
minimal test environments.
"""
from __future__ import annotations

import importlib.util
import platform
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/system", tags=["system"])

_HERE = Path(__file__).resolve().parent  # .../trendradar/desktop/api
_DESKTOP = _HERE.parent


def _load_paths():
    spec = importlib.util.spec_from_file_location(
        "_routes_system_paths", _DESKTOP / "paths.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_config_store():
    spec = importlib.util.spec_from_file_location(
        "_routes_system_config_store", _DESKTOP / "config_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _status_payload(desktop) -> dict:
    ConfigStore = _load_config_store().ConfigStore
    user_cfg = ConfigStore().load()
    status = "READY" if user_cfg.get("wizard", {}).get("completed") else "NEED_WIZARD"
    return {"status": status, "port": desktop.port, "version": desktop.version}


@router.get("/status")
def status(request: Request):
    return _status_payload(request.app.state.desktop)


@router.get("/info")
def info():
    paths = _load_paths()
    return {
        "os": platform.platform(),
        "user_config_dir": str(paths.user_config_dir()),
        "audit_log": str(paths.audit_log_file()),
        "version": _get_trendradar_version(),
        "frozen": paths.is_frozen(),
    }


def _get_trendradar_version() -> str:
    """Read version without triggering the eager trendradar/__init__.py chain.

    Tries trendradar.__version__, then the `version` file at repo root.
    """
    try:
        from trendradar import __version__ as v
        return v
    except Exception:
        pass
    version_file = Path(__file__).resolve().parents[3] / "version"
    if version_file.exists():
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "unknown"


def _load_autostart():
    spec = importlib.util.spec_from_file_location(
        "_routes_system_autostart", _DESKTOP / "autostart.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_version_check():
    spec = importlib.util.spec_from_file_location(
        "_routes_system_version_check", _DESKTOP / "version_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@router.get("/autostart")
def get_autostart():
    import sys
    autostart = _load_autostart()
    return {"enabled": autostart.is_enabled(sys.executable)}


@router.put("/autostart")
def put_autostart(payload: dict):
    import sys
    autostart = _load_autostart()
    enabled = bool(payload.get("enabled"))
    autostart.set_enabled(enabled, sys.executable)
    return {"enabled": enabled}


@router.get("/version-check")
def version_check_endpoint():
    version_check = _load_version_check()
    latest = version_check.fetch_latest()
    current = _get_trendradar_version()
    return {
        "current": current,
        "latest": latest,
        "update_available": latest is not None and latest.lstrip("v") != current,
    }
