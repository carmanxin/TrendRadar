"""Read/write config/ai_interests.txt.

Self-contained lazy loaders (no cross-route import) to avoid triggering
the trendradar/__init__.py chain.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/interests", tags=["interests"])

_DESKTOP = Path(__file__).resolve().parent.parent
_FILE = Path("config") / "ai_interests.txt"


def _load_config_store():
    spec = importlib.util.spec_from_file_location(
        "_routes_interests_config_store", _DESKTOP / "config_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class ContentPayload(BaseModel):
    content: str


@router.get("")
def get_interests():
    if not _FILE.exists():
        return {"content": "", "path": str(_FILE)}
    return {"content": _FILE.read_text(encoding="utf-8"), "path": str(_FILE)}


@router.put("")
def put_interests(payload: ContentPayload):
    _atomic_write(_FILE, payload.content)
    ConfigStore = _load_config_store().ConfigStore
    ConfigStore().audit("updated ai_interests.txt")
    return {"ok": True}
