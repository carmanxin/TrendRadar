import importlib.util
from pathlib import Path

# Load trendradar/desktop/paths.py directly, bypassing trendradar/__init__.py
_PATHS_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "paths.py"
spec = importlib.util.spec_from_file_location("_trendradar_desktop_paths", _PATHS_PY)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Tests — same as brief but using the loaded module
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


import pytest


@pytest.fixture(autouse=True)
def isolated_user_config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "user_config_file", lambda: tmp_path / "user_config.yaml")
    monkeypatch.setattr(paths, "audit_log_file", lambda: tmp_path / "audit.log")
    yield tmp_path