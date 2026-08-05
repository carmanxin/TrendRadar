"""TrendRadar Desktop - PyInstaller-bundled GUI wrapper."""

__all__ = ["DesktopApp"]


def __getattr__(name: str):  # lazy import to avoid loading GUI deps at CLI
    if name == "DesktopApp":
        from trendradar.desktop.app import DesktopApp
        return DesktopApp
    raise AttributeError(f"module 'trendradar.desktop' has no attribute {name!r}")