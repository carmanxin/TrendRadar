"""Tests for /api/sources/{platforms,rss} endpoints."""
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


app_mod = _load("_api_sources_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path / "uc"))
    proj = tmp_path / "proj"
    (proj / "config").mkdir(parents=True)
    (proj / "config" / "config.yaml").write_text(
        "platforms:\n  enabled: true\n  sources:\n    - id: zhihu\n      name: 知乎\n    - id: weibo\n      name: 微博\n"
        "rss:\n  enabled: true\n  feeds:\n    - id: hacker-news\n      name: Hacker News\n      url: https://x\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(proj)
    return proj


def test_get_platforms(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/sources/platforms")
    assert r.status_code == 200
    items = r.json()
    assert {p["id"] for p in items} == {"zhihu", "weibo"}


def test_put_platforms_disables_one(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.put("/api/sources/platforms", json={"enabled_ids": ["zhihu"]})
    assert r.status_code == 200
    items = {p["id"]: p.get("enabled", True) for p in r.json()}
    assert items["zhihu"] is True
    assert items["weibo"] is False


def test_get_rss(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.get("/api/sources/rss")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "hacker-news"


def test_put_rss_disables_one(isolated_env):
    client = TestClient(DesktopApp(port=18765).make_test_app())
    r = client.put("/api/sources/rss", json={"enabled_ids": []})
    assert r.status_code == 200
    items = {f["id"]: f.get("enabled", True) for f in r.json()}
    assert items["hacker-news"] is False
