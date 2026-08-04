"""Tests for /api/reports endpoints."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_APP_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "app.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


app_mod = _load("_api_reports_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path / "uc"))
    proj = tmp_path / "proj"
    (proj / "output" / "html" / "2026-08-04").mkdir(parents=True)
    (proj / "output" / "html" / "2026-08-04" / "093000.html").write_text("<h1>x</h1>", encoding="utf-8")
    (proj / "output" / "html" / "latest").mkdir(parents=True)
    (proj / "output" / "html" / "latest" / "daily.html").write_text("<h1>y</h1>", encoding="utf-8")
    monkeypatch.chdir(proj)
    return proj


def test_list_reports(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/reports")
    assert r.status_code == 200
    data = r.json()["reports"]
    assert any(item["date"] == "2026-08-04" for item in data)


def test_latest_report(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/reports/latest?mode=daily")
    assert r.status_code == 200
    assert r.json()["path"].endswith("daily.html")


def test_latest_report_missing_returns_404(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/reports/latest?mode=current")
    assert r.status_code == 404
