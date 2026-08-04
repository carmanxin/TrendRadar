"""Tests for /api/wizard/complete.

Uses TRENDRADAR_USER_CONFIG_DIR env override so every paths consumer
resolves to tmp_path.
"""
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


app_mod = _load("_api_wizard_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp


@pytest.fixture(autouse=True)
def isolate_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path))
    yield tmp_path


def test_wizard_complete_writes_user_config_and_marks_done(isolate_paths):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.post("/api/wizard/complete", json={
        "ai_base": "https://api.deepseek.com/v1",
        "ai_key": "sk-test-123",
        "ai_model": "deepseek/deepseek-reasoner",
        "timezone": "Asia/Shanghai",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "READY"

    import yaml
    saved = yaml.safe_load((isolate_paths / "user_config.yaml").read_text(encoding="utf-8"))
    assert saved["wizard"]["completed"] is True
    assert saved["ai"]["api_key"] == "sk-test-123"
    assert saved["ai"]["api_base"] == "https://api.deepseek.com/v1"
    assert saved["ai"]["model"] == "deepseek/deepseek-reasoner"
    assert saved["app"]["timezone"] == "Asia/Shanghai"

    audit = (isolate_paths / "audit.log").read_text(encoding="utf-8")
    assert "wizard completed" in audit


def test_wizard_rejects_missing_required_field(isolate_paths):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.post("/api/wizard/complete", json={"ai_base": "x"})
    assert r.status_code == 422
