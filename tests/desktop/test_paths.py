import importlib.util
from pathlib import Path

# Load trendradar/desktop/paths.py directly, bypassing trendradar/__init__.py
_PATHS_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "paths.py"
spec = importlib.util.spec_from_file_location("_trendradar_desktop_paths", _PATHS_PY)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)


def test_user_config_dir_returns_path():
    result = paths.user_config_dir()
    assert isinstance(result, Path)
    assert result.exists()
    assert result.is_dir()


def test_user_config_file_inside_user_config_dir():
    base = paths.user_config_dir()
    target = paths.user_config_file()
    assert target.parent == base
    assert target.name == "user_config.yaml"


def test_audit_log_inside_user_config_dir():
    base = paths.user_config_dir()
    target = paths.audit_log_file()
    assert target.parent == base
    assert target.name == "audit.log"


def test_is_frozen_returns_bool():
    assert isinstance(paths.is_frozen(), bool)


def test_webui_dir_is_callable():
    # webui/ may not exist yet at Task 1 — it's created in Task 4.
    # This test just verifies the function exists and is callable.
    # A stronger test that asserts directory presence lives in Task 4.
    assert callable(paths.webui_dir)


def test_module_constants_are_set():
    assert paths.APP_NAME == "TrendRadar"
    assert paths.APP_AUTHOR == "TrendRadar"


def test_webui_dir_frozen_mode_resolves_meipass(tmp_path, monkeypatch):
    """Frozen mode must resolve webui from sys._MEIPASS root, matching the
    PyInstaller spec's datas destination ('../trendradar/desktop/webui', 'webui')."""
    # Simulate the PyInstaller bundle layout: _MEIPASS/webui/index.html
    (tmp_path / "webui" / "index.html").parent.mkdir(parents=True)
    (tmp_path / "webui" / "index.html").write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    # _MEIPASS is normally only present inside a frozen bundle; inject it onto
    # the real sys module and restore after the test.
    import sys as _real_sys
    _real_sys._MEIPASS = str(tmp_path)  # type: ignore[attr-defined]
    try:
        result = paths.webui_dir()
        assert result == tmp_path / "webui"
        assert (result / "index.html").exists()
    finally:
        del _real_sys._MEIPASS  # type: ignore[attr-defined]


def test_webui_dir_frozen_mode_missing_raises(tmp_path, monkeypatch):
    """If the bundle lacks webui/ (spec misconfigured), webui_dir() must raise."""
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    import sys as _real_sys
    _real_sys._MEIPASS = str(tmp_path)  # type: ignore[attr-defined]
    try:
        try:
            paths.webui_dir()
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass
    finally:
        del _real_sys._MEIPASS  # type: ignore[attr-defined]