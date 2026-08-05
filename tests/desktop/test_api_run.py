"""Tests for /api/run/* endpoints."""
import importlib.util
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_APP_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "app.py"
_RUNNER_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "runner.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


app_mod = _load("_api_run_app_test", _APP_PY)
DesktopApp = app_mod.DesktopApp
runner_mod = _load("_api_run_runner_test", _RUNNER_PY)
RunManager = runner_mod.RunManager


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDRADAR_USER_CONFIG_DIR", str(tmp_path / "uc"))
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)
    return tmp_path


def test_run_start_returns_started(isolated_env):
    app_inst = DesktopApp(port=18765)
    client = TestClient(app_inst.make_test_app())
    # Inject an isolated RunManager for deterministic behavior.
    test_mgr = RunManager()
    app_inst.run_manager = test_mgr

    r = client.post("/api/run/start", json={
        "command": [sys.executable, "-c", "print('TOKEN=shouldhide'); print('hello')"]
    })
    assert r.status_code == 200
    assert r.json()["started"] is True
    while test_mgr.is_running():
        time.sleep(0.05)
    logs = client.get("/api/run/logs").json()["logs"]
    assert any("hello" in line for line in logs)
    assert all("shouldhide" not in line for line in logs)


def test_run_start_twice_returns_409(isolated_env):
    app_inst = DesktopApp(port=18765)
    client = TestClient(app_inst.make_test_app())
    r1 = client.post("/api/run/start", json={
        "command": [sys.executable, "-c", "import time; time.sleep(0.5)"]
    })
    assert r1.status_code == 200
    r2 = client.post("/api/run/start", json={"command": [sys.executable, "-c", "print(1)"]})
    assert r2.status_code == 409
    while app_inst.run_manager.is_running():
        time.sleep(0.05)
    app_inst.run_manager.stop()


def test_run_stop_returns_stopped(isolated_env):
    app_inst = DesktopApp(port=18765)
    client = TestClient(app_inst.make_test_app())
    test_mgr = RunManager()
    app_inst.run_manager = test_mgr
    r = client.post("/api/run/stop")
    assert r.status_code == 200
    assert r.json()["stopped"] is True


def test_logs_stream_emits_end_event(isolated_env):
    """SSE stream must emit `event: end` after the subprocess exits."""
    app_inst = DesktopApp(port=18765)
    client = TestClient(app_inst.make_test_app())
    test_mgr = RunManager()
    app_inst.run_manager = test_mgr

    # Start a short run, then open the SSE stream.
    r = client.post("/api/run/start", json={
        "command": [sys.executable, "-c", "import time; time.sleep(0.2); print('done')"]
    })
    assert r.status_code == 200

    with client.stream("GET", "/api/run/logs/stream") as resp:
        assert resp.status_code == 200
        chunks = []
        for line in resp.iter_lines():
            if line:
                chunks.append(line)
            if "event: end" in "\n".join(chunks):
                break
    body = "\n".join(chunks)
    assert "done" in body
    assert "event: end" in body


def test_logs_stream_handles_no_run(isolated_env):
    """Opening the stream with no run in progress should terminate (not hang)."""
    app_inst = DesktopApp(port=18765)
    client = TestClient(app_inst.make_test_app())
    test_mgr = RunManager()
    app_inst.run_manager = test_mgr

    with client.stream("GET", "/api/run/logs/stream") as resp:
        assert resp.status_code == 200
        chunks = []
        for line in resp.iter_lines():
            if line:
                chunks.append(line)
            if "event: end" in "\n".join(chunks):
                break
    assert "event: end" in "\n".join(chunks)
