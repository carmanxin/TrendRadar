"""Cross-platform 'run at login' toggle."""
from __future__ import annotations

import sys
from pathlib import Path


def _linux_desktop_file(exe_path: str) -> Path:
    p = Path.home() / ".config" / "autostart"
    p.mkdir(parents=True, exist_ok=True)
    return p / "trendradar.desktop"


def _mac_plist(exe_path: str) -> Path:
    p = Path.home() / "Library" / "LaunchAgents"
    p.mkdir(parents=True, exist_ok=True)
    return p / "com.trendradar.desktop.plist"


def _windows_set(enabled: bool, exe_path: str) -> None:
    import winreg
    KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, "TrendRadar", 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(k, "TrendRadar")
            except FileNotFoundError:
                pass


def _windows_get(exe_path: str) -> bool:
    import winreg
    KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ) as k:
            value, _ = winreg.QueryValueEx(k, "TrendRadar")
            return value.strip('"') == exe_path
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool, exe_path: str) -> None:
    if sys.platform == "win32":
        _windows_set(enabled, exe_path)
    elif sys.platform == "darwin":
        f = _mac_plist(exe_path)
        if enabled:
            f.write_text(
                f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                f'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                f'<plist version="1.0"><dict><key>Label</key><string>com.trendradar.desktop</string>'
                f'<key>ProgramArguments</key><array><string>{exe_path}</string></array>'
                f'<key>RunAtLoad</key><true/></dict></plist>\n',
                encoding="utf-8",
            )
        else:
            if f.exists():
                f.unlink()
    else:
        f = _linux_desktop_file(exe_path)
        if enabled:
            f.write_text(
                "[Desktop Entry]\nType=Application\nName=TrendRadar\nExec=" + exe_path + "\nX-GNOME-Autostart-enabled=true\n",
                encoding="utf-8",
            )
        else:
            if f.exists():
                f.unlink()


def is_enabled(exe_path: str) -> bool:
    if sys.platform == "win32":
        return _windows_get(exe_path)
    if sys.platform == "darwin":
        return _mac_plist(exe_path).exists()
    return _linux_desktop_file(exe_path).exists()
