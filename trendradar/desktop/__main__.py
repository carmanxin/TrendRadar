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


def _run_core_cli(argv: list[str]) -> int:
    """Invoke the core TrendRadar CLI in-process.

    Used by the frozen bundle (PyInstaller): inside a one-dir build there is
    no `python.exe` and no on-disk `trendradar/` package to spawn via
    `-m trendradar`, so the RunManager spawns *this* executable with
    `--run-core` instead, which then runs the core logic directly.
    """
    import runpy

    main_py = Path(__file__).resolve().parent.parent / "__main__.py"
    # In the bundle, __file__ points at the extracted package; in dev it's the
    # checkout. Fall back to `trendradar.__main__` if the file path is missing.
    if not main_py.exists():
        from trendradar import __main__ as core_main
        core_main.main()
        return 0
    sys.argv = [str(main_py), *argv]
    runpy.run_path(str(main_py), run_name="__main__")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--run-core" in args:
        core_args = [a for a in args if a != "--run-core"]
        return _run_core_cli(core_args)
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
