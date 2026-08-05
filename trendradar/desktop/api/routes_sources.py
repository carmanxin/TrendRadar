"""Enable/disable platforms and RSS feeds in config/config.yaml.

Uses an inline lazy loader for config_store to avoid the eager
trendradar/__init__.py chain. NOTE: no `from __future__ import annotations`
here — pydantic needs concrete list[str] at class-definition time.
"""
import importlib.util
from pathlib import Path

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/sources", tags=["sources"])

_DESKTOP = Path(__file__).resolve().parent.parent
_CONFIG = Path("config") / "config.yaml"


def _load_config_store():
    spec = importlib.util.spec_from_file_location(
        "_routes_sources_config_store", _DESKTOP / "config_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load() -> dict:
    if not _CONFIG.exists():
        return {}
    with _CONFIG.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save(data: dict) -> None:
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _list(section: str) -> list[dict]:
    data = _load()
    return data.get(section, {}).get("sources" if section == "platforms" else "feeds", []) or []


def _apply_enabled(section: str, key: str, enabled_ids: list[str]) -> list[dict]:
    data = _load()
    sub = data.setdefault(section, {})
    list_key = "sources" if section == "platforms" else "feeds"
    items = sub.get(list_key, []) or []
    for item in items:
        item["enabled"] = item.get("id") in enabled_ids
    sub[list_key] = items
    _save(data)
    ConfigStore = _load_config_store().ConfigStore
    ConfigStore().audit(f"updated {section} enabled set: {sorted(enabled_ids)}")
    return items


class EnabledPayload(BaseModel):
    enabled_ids: list[str]


@router.get("/platforms")
def get_platforms():
    return _list("platforms")


@router.put("/platforms")
def put_platforms(payload: EnabledPayload):
    return _apply_enabled("platforms", "id", payload.enabled_ids)


@router.get("/rss")
def get_rss():
    return _list("rss")


@router.put("/rss")
def put_rss(payload: EnabledPayload):
    return _apply_enabled("rss", "id", payload.enabled_ids)
