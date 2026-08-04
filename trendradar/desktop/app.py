"""Desktop application orchestrator: server + lifecycle.

Uses lazy loaders for paths/errors/server to avoid the eager
`trendradar/__init__.py` chain (litellm).
"""
from __future__ import annotations

import importlib.util
import logging
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn

log = logging.getLogger(__name__)


_PATHS_PY = Path(__file__).resolve().parent / "paths.py"
_ERRORS_PY = Path(__file__).resolve().parent / "errors.py"


def _load_paths():
    spec = importlib.util.spec_from_file_location("_app_paths", _PATHS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_errors():
    spec = importlib.util.spec_from_file_location("_app_errors", _ERRORS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_version() -> str:
    try:
        from trendradar import __version__ as v
        return v
    except Exception:
        version_file = Path(__file__).resolve().parents[2] / "version"
        if version_file.exists():
            try:
                return version_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return "unknown"


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect((host, port))
        except OSError:
            return True
        return False


def _find_free_port(host: str, start: int, attempts: int = 10) -> int:
    errors = _load_errors()
    for offset in range(attempts):
        candidate = start + offset
        if _is_port_free(host, candidate):
            return candidate
    raise errors.PortInUseError(f"no free port in range {start}..{start + attempts - 1}")


class DesktopApp:
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8765

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.version = _get_version()
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self.host = self.DEFAULT_HOST
        self._tray = None
        self._run_manager = None

    @property
    def run_manager(self):
        if self._run_manager is None:
            # Lazy instantiate so importing app.py doesn't pull in runner.
            runner_spec = importlib.util.spec_from_file_location(
                "_app_runner", Path(__file__).resolve().parent / "runner.py"
            )
            runner_mod = importlib.util.module_from_spec(runner_spec)
            runner_spec.loader.exec_module(runner_mod)
            self._run_manager = runner_mod.RunManager()
        return self._run_manager

    @run_manager.setter
    def run_manager(self, value):
        self._run_manager = value

    def start(self, open_browser: bool = True) -> None:
        if not _is_port_free(self.host, self.port):
            self.port = _find_free_port(self.host, self.port + 1)

        from trendradar.desktop.server import create_app
        app = create_app(self)
        config = uvicorn.Config(
            app, host=self.host, port=self.port, log_level="warning", lifespan="on"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        for _ in range(50):
            if self._server.started:
                break
            time.sleep(0.1)
        if open_browser:
            try:
                webbrowser.open(f"http://{self.host}:{self.port}")
            except Exception:
                log.warning("could not open browser", exc_info=True)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=3.0)

    def make_test_app(self):
        """Create a FastAPI app instance bound to this DesktopApp, without starting uvicorn.

        Uses lazy importlib loading of server.py to avoid triggering the eager
        `trendradar/__init__.py` chain (which imports litellm).
        """
        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location("_app_server_for_test_app", here / "server.py")
        server_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_mod)
        return server_mod.create_app(self)
