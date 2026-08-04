"""First-run wizard endpoint.

Uses an inline lazy loader for config_store to avoid the eager
`trendradar/__init__.py` chain (litellm).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/wizard", tags=["wizard"])

_DESKTOP = Path(__file__).resolve().parent.parent


def _load_config_store():
    spec = importlib.util.spec_from_file_location(
        "_routes_wizard_config_store", _DESKTOP / "config_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WizardPayload(BaseModel):
    ai_base: str = Field(min_length=1)
    ai_key: str = Field(min_length=1)
    ai_model: str = Field(min_length=1)
    timezone: str = Field(min_length=1)


@router.post("/complete")
def complete(payload: WizardPayload):
    ConfigStore = _load_config_store().ConfigStore
    store = ConfigStore()
    store.update({
        "wizard": {"completed": True},
        "ai": {
            "api_base": payload.ai_base,
            "api_key": payload.ai_key,
            "model": payload.ai_model,
        },
        "app": {"timezone": payload.timezone},
    })
    store.audit("wizard completed")
    return {"status": "READY"}
