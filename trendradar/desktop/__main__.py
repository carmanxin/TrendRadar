"""Entry point for both `python -m trendradar.desktop` and PyInstaller bundle.

Uses `from trendradar.desktop import DesktopApp` which is a lazy attribute
(lazy `__getattr__` in the package `__init__`), so importing this module
does NOT trigger the eager `trendradar/__init__.py` chain in dev mode.
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _banner() -> str:
    try:
        from trendradar import __version__ as v
        return f"TrendRadar Desktop v{v}"
    except Exception:
        return "TrendRadar Desktop"


def main() -> int:
    print(_banner())
    try:
        from trendradar.desktop import DesktopApp
    except ModuleNotFoundError as e:
        if "litellm" in str(e):
            print(
                "Cannot start: the TrendRadar core requires `litellm`. In dev, run "
                "`pip install -e .` (or the bundled executable from the CI build).",
                file=sys.stderr,
            )
            return 2
        raise
    app = DesktopApp()
    try:
        app.start(open_browser=True)
    except KeyboardInterrupt:
        app.stop()
        return 0
    try:
        if app._thread is not None:
            app._thread.join()
    except KeyboardInterrupt:
        app.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
