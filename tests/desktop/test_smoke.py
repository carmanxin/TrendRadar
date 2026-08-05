"""Smoke check: start the desktop server and hit the status endpoint.

Gated behind TRENDRADAR_SMOKE=1 because it needs the full trendradar
package (litellm) installed. Runs in CI after `pip install -e .`.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(0.1)
    return False


@pytest.mark.skipif(
    os.environ.get("TRENDRADAR_SMOKE") != "1",
    reason="set TRENDRADAR_SMOKE=1 to run",
)
def test_smoke_starts_and_responds(tmp_path):
    env = os.environ.copy()
    env["TRENDRADAR_DESKTOP_NO_TRAY"] = "1"
    env["PYTHONPATH"] = str(Path.cwd()) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "trendradar.desktop"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=str(tmp_path),
    )
    try:
        assert _wait_for_port("127.0.0.1", 8765, timeout=20), "server didn't bind 8765"
        with urllib.request.urlopen("http://127.0.0.1:8765/api/system/status", timeout=5) as r:
            data = json.loads(r.read())
        assert data["status"] in ("NEED_WIZARD", "READY")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
