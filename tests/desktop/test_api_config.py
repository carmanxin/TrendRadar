"""Tests for /api/config/* endpoints.

Uses TRENDRADAR_USER_CONFIG_DIR env override so every paths consumer
resolves to tmp_path. The project config file (config/config.yaml) is
resolved relative to cwd, so tests chdir to a temp project dir.
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


app_mod = _load("_api_config_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path))
    # Fake project root so routes_config reads/writes config/config.yaml here.
    proj = tmp_path / "proj"
    (proj / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(proj)
    yield tmp_path


def test_get_config_masks_secrets(isolated_env, tmp_path):
    user_cfg = tmp_path / "user_config.yaml"
    user_cfg.write_text(
        "ai:\n  api_key: sk-abcdef12345\n  model: deepseek/deepseek-reasoner\n",
        encoding="utf-8",
    )
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert "sk-abcdef12345" not in str(data)
    assert data["ai"]["api_key"].startswith("sk-abc")


def test_put_config_section_writes_project_yaml(isolated_env, tmp_path):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.put("/api/config/section/ai", json={"model": "deepseek/deepseek-chat"})
    assert r.status_code == 200
    data = r.json()
    assert data["ai"]["model"] == "deepseek/deepseek-chat"
    # Verify it hit the on-disk config/config.yaml
    import yaml
    on_disk = yaml.safe_load((tmp_path / "proj" / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert on_disk["ai"]["model"] == "deepseek/deepseek-chat"


def test_put_config_rejects_non_object_payload(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.put("/api/config/section/ai", json=[1, 2, 3])
    # FastAPI/pydantic rejects a non-object body with 422 before our handler runs.
    assert r.status_code == 422
