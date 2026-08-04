"""Tests for /api/keywords and /api/interests endpoints."""
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


app_mod = _load("_api_keywords_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path / "uc"))
    proj = tmp_path / "proj"
    (proj / "config").mkdir(parents=True)
    (proj / "config" / "frequency_words.txt").write_text(
        "组A\n关键词1\n关键词2\n", encoding="utf-8"
    )
    (proj / "config" / "ai_interests.txt").write_text("兴趣A", encoding="utf-8")
    monkeypatch.chdir(proj)
    return proj


def test_get_keywords_returns_content(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/keywords")
    assert r.status_code == 200
    assert r.json()["content"].startswith("组A")


def test_put_keywords_writes_file(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.put("/api/keywords", json={"content": "组X\nfoo bar"})
    assert r.status_code == 200
    on_disk = (isolated_env / "config" / "frequency_words.txt").read_text(encoding="utf-8")
    assert on_disk == "组X\nfoo bar"


def test_get_interests_returns_content(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/interests")
    assert r.status_code == 200
    assert "兴趣A" in r.json()["content"]


def test_put_interests_writes_file(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.put("/api/interests", json={"content": "兴趣B\n优先级 1"})
    assert r.status_code == 200
    on_disk = (isolated_env / "config" / "ai_interests.txt").read_text(encoding="utf-8")
    assert on_disk == "兴趣B\n优先级 1"
