"""Read/update project YAML config (config/config.yaml).

Uses inline lazy loaders to avoid the eager trendradar/__init__.py chain.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/config", tags=["config"])

_DESKTOP = Path(__file__).resolve().parent.parent
_PROJECT_CONFIG_PATH = Path("config") / "config.yaml"


def _load_config_store():
    spec = importlib.util.spec_from_file_location(
        "_routes_config_config_store", _DESKTOP / "config_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_mask_config():
    spec = importlib.util.spec_from_file_location(
        "_routes_config_runner", _DESKTOP / "runner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.mask_config


def _load_project_yaml() -> Dict[str, Any]:
    if not _PROJECT_CONFIG_PATH.exists():
        return {}
    with _PROJECT_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_project_yaml(data: Dict[str, Any]) -> None:
    _PROJECT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _PROJECT_CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _merged() -> Dict[str, Any]:
    ConfigStore = _load_config_store().ConfigStore
    user = ConfigStore().load()
    project = _load_project_yaml()
    return {**project, **user}


@router.get("")
def get_config():
    mask_config = _load_mask_config()
    return mask_config(_merged())


@router.put("/section/{name}")
def update_section(name: str, payload: Dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    ConfigStore = _load_config_store().ConfigStore
    project = _load_project_yaml()
    project[name] = payload
    _save_project_yaml(project)
    ConfigStore().audit(f"updated config section: {name}")
    mask_config = _load_mask_config()
    return mask_config(_merged())
