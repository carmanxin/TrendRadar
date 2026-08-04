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

    # Load routes_wizard via importlib (same reason).
    wizard_spec = importlib.util.spec_from_file_location(
        "_server_routes_wizard",
        Path(__file__).resolve().parent / "api" / "routes_wizard.py",
    )
    wizard_mod = importlib.util.module_from_spec(wizard_spec)
    wizard_spec.loader.exec_module(wizard_mod)
    app.include_router(wizard_mod.router)

    # Load routes_config via importlib (same reason).
    config_spec = importlib.util.spec_from_file_location(
        "_server_routes_config",
        Path(__file__).resolve().parent / "api" / "routes_config.py",
    )
    config_mod = importlib.util.module_from_spec(config_spec)
    config_spec.loader.exec_module(config_mod)
    app.include_router(config_mod.router)

    # Load routes_keywords / routes_interests via importlib.
    for fname, modname in (("routes_keywords", "keywords"), ("routes_interests", "interests")):
        spec = importlib.util.spec_from_file_location(
            f"_server_{modname}",
            Path(__file__).resolve().parent / "api" / f"{fname}.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        app.include_router(mod.router)

    # Load routes_sources via importlib.
    sources_spec = importlib.util.spec_from_file_location(
        "_server_routes_sources",
        Path(__file__).resolve().parent / "api" / "routes_sources.py",
    )
    sources_mod = importlib.util.module_from_spec(sources_spec)
    sources_spec.loader.exec_module(sources_mod)
    app.include_router(sources_mod.router)

    # Load routes_run via importlib.
    run_spec = importlib.util.spec_from_file_location(
        "_server_routes_run",
        Path(__file__).resolve().parent / "api" / "routes_run.py",
    )
    run_mod = importlib.util.module_from_spec(run_spec)
    run_spec.loader.exec_module(run_mod)
    app.include_router(run_mod.router)

    # Load routes_reports via importlib.
    reports_spec = importlib.util.spec_from_file_location(
        "_server_routes_reports",
        Path(__file__).resolve().parent / "api" / "routes_reports.py",
    )
    reports_mod = importlib.util.module_from_spec(reports_spec)
    reports_spec.loader.exec_module(reports_mod)
    app.include_router(reports_mod.router)

    app.mount("/static/assets", StaticFiles(directory=webui / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(webui / "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return Response(status_code=204)

    return app
