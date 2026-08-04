"""Tests for trendradar.desktop.runner.

This test file uses `importlib.util.spec_from_file_location` to load
`runner.py` directly, bypassing the eager `trendradar/__init__.py` chain
(which imports litellm and is unavailable in the minimal test env).
Same pattern as test_paths.py and test_config_store.py.
"""
import importlib.util
from pathlib import Path

# Load dependencies the same way.
_PATHS_PY = (
    Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "paths.py"
)
_paths_spec = importlib.util.spec_from_file_location(
    "_trendradar_desktop_paths_runner_test", _PATHS_PY
)
paths = importlib.util.module_from_spec(_paths_spec)
_paths_spec.loader.exec_module(paths)

_ERRORS_PY = (
    Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "errors.py"
)
_errors_spec = importlib.util.spec_from_file_location(
    "_trendradar_desktop_errors_runner_test", _ERRORS_PY
)
errors = importlib.util.module_from_spec(_errors_spec)
_errors_spec.loader.exec_module(errors)
RunAlreadyActiveError = errors.RunAlreadyActiveError

_RUNNER_PY = (
    Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "runner.py"
)
_runner_spec = importlib.util.spec_from_file_location(
    "_trendradar_desktop_runner_test", _RUNNER_PY
)
runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(runner)
redact_secrets = runner.redact_secrets
RunManager = runner.RunManager


import sys
import time

import pytest


@pytest.fixture(autouse=True)
def share_errors_module(monkeypatch):
    """Make `runner._load_errors()` return OUR errors module so `pytest.raises`
    in the test sees the same exception class that RunManager raises.
    Without this, the two importlib copies of errors.py produce distinct
    RunAlreadyActiveError classes and isinstance checks fail.
    """
    monkeypatch.setattr(runner, "_load_errors", lambda: errors)


def test_redact_secrets_replaces_api_key():
    s = "Starting with AI_API_KEY=sk-abcdef12345 and openai_key=sk-xyz"
    out = redact_secrets(s)
    assert "sk-abcdef12345" not in out
    assert "sk-xyz" not in out
    assert out.count("***") == 2


def test_redact_secrets_replaces_token_and_password():
    s = "TOKEN=gho_abc PASSWORD=secret123"
    out = redact_secrets(s)
    assert "gho_abc" not in out
    assert "secret123" not in out


def test_redact_secrets_keeps_non_secret_lines_intact():
    s = "[INFO] fetched 10 headlines from zhihu"
    assert redact_secrets(s) == s


@pytest.mark.asyncio
async def test_run_manager_runs_simple_command_and_streams_redacted_output():
    mgr = RunManager()
    cmd = [sys.executable, "-c", "print('TOKEN=shouldhide'); print('hello')"]
    mgr.start(env_overrides={"PYTHONIOENCODING": "utf-8"}, command=cmd)
    code = await mgr.wait_async()
    assert code == 0
    lines = mgr.recent_logs()
    assert any("hello" in line for line in lines)
    assert all("shouldhide" not in line for line in lines)


@pytest.mark.asyncio
async def test_run_manager_rejects_concurrent_start():
    mgr = RunManager()
    cmd = [sys.executable, "-c", "import time; time.sleep(0.5)"]
    mgr.start(env_overrides={}, command=cmd)
    with pytest.raises(RunAlreadyActiveError):
        mgr.start(env_overrides={}, command=cmd)
    await mgr.wait_async()


def test_run_manager_is_running_reflects_state():
    mgr = RunManager()
    cmd = [sys.executable, "-c", "import time; time.sleep(0.3)"]
    assert mgr.is_running() is False
    mgr.start(env_overrides={}, command=cmd)
    assert mgr.is_running() is True
    while mgr.is_running():
        time.sleep(0.05)
    assert mgr.is_running() is False
