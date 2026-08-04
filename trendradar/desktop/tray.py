"""System tray icon and menu.

Uses lazy importlib loaders for autostart to avoid the eager
`trendradar/__init__.py` chain (litellm).
"""
from __future__ import annotations

import importlib.util
import logging
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from trendradar.desktop.app import DesktopApp

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent


def _load_autostart():
    spec = importlib.util.spec_from_file_location(
        "_tray_autostart", _HERE / "autostart.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((8, 8, 56, 56), fill=(10, 170, 120, 255))
    d.text((20, 22), "TR", fill="white")
    return img


class Tray:
    def __init__(self, desktop: "DesktopApp"):
        self.desktop = desktop
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._autostart_enabled = False

    def _toggle_autostart(self, icon: pystray.Icon, item: pystray.MenuItem):
        import sys
        exe = sys.executable
        self._autostart_enabled = not self._autostart_enabled
        autostart = _load_autostart()
        autostart.set_enabled(self._autostart_enabled, exe)

    def _run_now(self, icon: pystray.Icon, item: pystray.MenuItem):
        mgr = self.desktop.run_manager
        if mgr.is_running():
            log.info("tray: run already in progress, ignoring")
            return
        # Env overrides come from user_config via the /api/run path; here we
        # start with empty overrides so the subprocess inherits the desktop env.
        mgr.start(env_overrides={})

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem("打开 WebUI", lambda i, it: webbrowser.open(f"http://{self.desktop.host}:{self.desktop.port}")),
            pystray.MenuItem("立即运行", self._run_now),
            pystray.MenuItem(
                "开机自启",
                self._toggle_autostart,
                checked=lambda item: self._autostart_enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda i, it: self.desktop.stop()),
        )

    def start(self) -> None:
        self._icon = pystray.Icon("TrendRadar", _make_icon_image(), "TrendRadar", self._build_menu())
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
