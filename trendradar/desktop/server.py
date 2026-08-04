"""FastAPI application factory used by DesktopApp."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import importlib.util

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from trendradar.desktop.app import DesktopApp

log = logging.getLogger(__name__)


_PATHS_PY = Path(__file__).resolve().parent / "paths.py"


def _load_paths():
    spec = importlib.util.spec_from_file_location("_server_paths", _PATHS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def create_app(desktop: "DesktopApp") -> FastAPI:
    paths = _load_paths()
    webui = paths.webui_dir()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("desktop server starting on port %s", desktop.port)
        yield
        log.info("desktop server shutting down")

    app = FastAPI(title="TrendRadar Desktop", lifespan=lifespan)
    app.state.desktop = desktop

    # Load routes_system via importlib (it imports config_store which uses lazy paths).
    routes_spec = importlib.util.spec_from_file_location(
        "_server_routes_system",
        Path(__file__).resolve().parent / "api" / "routes_system.py",
    )
    routes_mod = importlib.util.module_from_spec(routes_spec)
    routes_spec.loader.exec_module(routes_mod)
    app.include_router(routes_mod.router)

    app.mount("/static/assets", StaticFiles(directory=webui / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(webui / "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return Response(status_code=204)

    return app
