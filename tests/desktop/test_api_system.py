"""Tests for /api/system/* endpoints.

Uses importlib to bypass trendradar/__init__.py's litellm chain. Patches
`routes_system._load_paths`/`_load_config_store` so that the status endpoint
sees a fresh tmp_path-backed user config (no real %APPDATA% writes).
"""
import importlib.util
from pathlib import Path

# Load helpers via importlib (same pattern as other desktop tests)
_PATHS_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "paths.py"
_CS_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "config_store.py"
_APP_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "app.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


paths = _load("_api_system_paths_test", _PATHS_PY)
cs_mod = _load("_api_system_cs_test", _CS_PY)
ConfigStore = cs_mod.ConfigStore
app_mod = _load("_api_system_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp


import pytest

from fastapi.testclient import TestClient

# Load routes_system so we can patch its loaders
_ROUTES_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "api" / "routes_system.py"
routes_system = _load("_api_system_routes_test", _ROUTES_PY)


def _make_client():
    return TestClient(DesktopApp(port=18765).make_test_app())


@pytest.fixture(autouse=True)
def isolate_paths(monkeypatch, tmp_path):
    """Point every desktop paths consumer (via env override) at a temp dir.

    All modules (paths, config_store, routes_system, server) load paths.py
    independently; the TRENDRADAR_USER_CONFIG_DIR env override in paths.py
    makes every fresh copy resolve to the same tmp_path. No module-level
    monkeypatching needed.
    """
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path))
    yield tmp_path


def test_status_needs_wizard_when_no_user_config(isolate_paths):
    client = _make_client()
    r = client.get("/api/system/status")
    assert r.status_code == 200
    assert r.json()["status"] == "NEED_WIZARD"


def test_status_ready_after_wizard_completed(isolate_paths):
    ConfigStore(isolate_paths / "user_config.yaml").update({"wizard": {"completed": True}})
    client = _make_client()
    r = client.get("/api/system/status")
    assert r.json()["status"] == "READY"


def test_info_returns_os_and_version(isolate_paths):
    client = _make_client()
    r = client.get("/api/system/info")
    assert r.status_code == 200
    data = r.json()
    assert "os" in data
    assert "version" in data
    assert "user_config_dir" in data


def test_index_returns_html(isolate_paths):
    client = _make_client()
    r = client.get("/")
    assert r.status_code == 200
    assert b"TrendRadar" in r.content


def test_favicon_returns_204(isolate_paths):
    client = _make_client()
    r = client.get("/favicon.ico")
    assert r.status_code == 204


def test_static_assets_serves_css(isolate_paths):
    client = _make_client()
    r = client.get("/static/assets/styles.css")
    assert r.status_code == 200
    assert b"body" in r.content
