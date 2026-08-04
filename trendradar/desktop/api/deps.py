"""FastAPI dependencies shared by route modules.

Uses lazy paths/config_store loaders to avoid the eager
`trendradar/__init__.py` chain (which imports litellm). Same pattern
as config_store.py and runner.py.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from trendradar.desktop.app import DesktopApp


_PATHS_PY = Path(__file__).resolve().parent.parent / "paths.py"
_CS_PY = Path(__file__).resolve().parent.parent / "config_store.py"


def _load_paths():
    spec = importlib.util.spec_from_file_location("_deps_paths", _PATHS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_config_store():
    spec = importlib.util.spec_from_file_location("_deps_config_store", _CS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_desktop(request: "Request") -> "DesktopApp":
    return request.app.state.desktop


def get_paths():
    return _load_paths()


def get_config_store():
    return _load_config_store().ConfigStore
