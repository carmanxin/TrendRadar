"""Run-now endpoints: start/stop a TrendRadar subprocess + SSE log stream.

All cross-module references are lazy (importlib) to avoid the eager
`trendradar/__init__.py` chain (litellm). NOTE: no `from __future__
import annotations` — pydantic needs concrete list[str] at class time.
"""
import asyncio
import importlib.util
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/run", tags=["run"])

_DESKTOP = Path(__file__).resolve().parent.parent


def _load_config_store():
    spec = importlib.util.spec_from_file_location(
        "_routes_run_config_store", _DESKTOP / "config_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "_routes_run_runner", _DESKTOP / "runner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_errors():
    spec = importlib.util.spec_from_file_location(
        "_routes_run_errors", _DESKTOP / "errors.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mgr(request: Request):
    return request.app.state.desktop.run_manager


class StartPayload(BaseModel):
    command: Optional[list[str]] = None  # for tests/dev; production uses default


def _build_env_overrides() -> dict:
    ConfigStore = _load_config_store().ConfigStore
    cfg = ConfigStore().load()
    ai = cfg.get("ai", {})
    overrides = {}
    if ai.get("api_key"):
        overrides["AI_API_KEY"] = ai["api_key"]
    if ai.get("api_base"):
        overrides["AI_API_BASE"] = ai["api_base"]
    if ai.get("model"):
        overrides["AI_MODEL"] = ai["model"]
    cfg_path = Path("config") / "config.yaml"
    if cfg_path.exists():
        overrides["CONFIG_PATH"] = str(cfg_path)
    return overrides


@router.post("/start")
def start(payload: StartPayload, request: Request):
    mgr = _mgr(request)
    # Check-then-act: avoids depending on exception class identity across
    # importlib copies of errors.py. The manager's own lock guards the race;
    # a concurrent start that slips past is caught by the message check below.
    if mgr.is_running():
        raise HTTPException(status_code=409, detail="a TrendRadar run is already in progress")
    try:
        mgr.start(env_overrides=_build_env_overrides(), command=payload.command)
    except Exception as e:
        if "already in progress" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise
    return {"started": True}


@router.post("/stop")
def stop(request: Request):
    _mgr(request).stop()
    return {"stopped": True}


@router.get("/logs")
def logs(request: Request):
    mgr = _mgr(request)
    return {"logs": mgr.recent_logs()[-500:]}


@router.get("/logs/stream")
async def stream(request: Request) -> StreamingResponse:
    mgr = _mgr(request)
    queue_holder = mgr.subscribe()

    async def event_gen() -> AsyncIterator[bytes]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                # queue.Queue.get is blocking; run it off the event loop.
                line = await asyncio.to_thread(queue_holder.get, timeout=1.0)
                if line is None:  # sentinel: stream closed
                    break
                payload = line.encode("utf-8", errors="replace")
                yield b"data: " + payload + b"\n\n"
                if not mgr.is_running() and queue_holder.empty():
                    break
            yield b"event: end\ndata: {}\n\n"
        finally:
            mgr.unsubscribe(queue_holder)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
