"""Subprocess manager that streams redacted stdout via an asyncio queue.

This module uses a lazy loader for `errors` to avoid the eager
`trendradar/__init__.py` import chain (which pulls in litellm and other
heavy deps). In production, when litellm is installed and the package
is on sys.path normally, the import `from trendradar.desktop import errors`
would also work — but the lazy form keeps the module usable in minimal
test environments and matches the pattern used in test_paths.py and
test_config_store.py.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import signal
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional

_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|openai[_-]?key|access[_-]?key|secret[_-]?key|token|password)[=:]\s*\S+"
)


def _load_errors():
    """Lazily import sibling `errors.py` without triggering trendradar/__init__.py.

    Mirrors the importlib trick used in tests/desktop/* and in config_store.py
    so that `runner` can be imported in environments where the full
    `trendradar` package (and its litellm dependency) is unavailable.
    """
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "_trendradar_desktop_errors_for_runner", here / "errors.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load errors module from {here / 'errors.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def redact_secrets(text: str) -> str:
    return _SECRET_PATTERN.sub(r"\1=***", text)


_SECRET_KEY_PATHS = (
    "ai.api_key",
    "notification.channels.feishu.webhook_url",
    "notification.channels.dingtalk.webhook_url",
    "notification.channels.wework.webhook_url",
    "notification.channels.telegram.bot_token",
    "notification.channels.email.password",
    "notification.channels.ntfy.token",
    "notification.channels.bark.url",
    "notification.channels.slack.webhook_url",
    "notification.channels.generic_webhook.webhook_url",
)


def mask_config(cfg: dict) -> dict:
    """Deep-copy cfg, masking values at known secret paths.

    Returns a copy; does NOT mutate the input. Each masked value becomes
    `sk-abc****yz` style (first 6 + '****' + last 2 chars) when longer than
    10 chars, else a bare `****`.
    """
    import copy

    out = copy.deepcopy(cfg)
    for dotted in _SECRET_KEY_PATHS:
        parts = dotted.split(".")
        cur = out
        for p in parts[:-1]:
            if not isinstance(cur, dict) or p not in cur:
                cur = None
                break
            cur = cur[p]
        if isinstance(cur, dict) and parts[-1] in cur and isinstance(cur[parts[-1]], str):
            v = cur[parts[-1]]
            cur[parts[-1]] = (v[:6] + "****" + v[-2:]) if len(v) > 10 else "****"
    return out


class RunManager:
    """Owns at most one subprocess. Thread-safe start/wait, async stream API."""

    _RING_BUFFER_SIZE = 10_000

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._subscribers: List[asyncio.Queue[str]] = []
        self._logs: Deque[str] = deque(maxlen=self._RING_BUFFER_SIZE)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self._pump_task: Optional[asyncio.Task] = None

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def start(self, env_overrides: Dict[str, str], command: Optional[List[str]] = None) -> None:
        with self._lock:
            errors = _load_errors()
            if self._proc is not None and self._proc.poll() is None:
                raise errors.RunAlreadyActiveError("a TrendRadar run is already in progress")
            cmd = command if command is not None else [sys.executable, "-m", "trendradar"]
            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env.update({k: str(v) for k, v in env_overrides.items()})
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=os.getcwd(),
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._logs.clear()
            self._subscribers.clear()
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None
            if self._loop is not None:
                self._pump_task = self._loop.create_task(self._pump_logs())

    async def _pump_logs(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, self._proc.stdout.readline)
            if not line:
                break
            line = line.rstrip("\n")
            line = redact_secrets(line)
            self._logs.append(line)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(line)
                except asyncio.QueueFull:
                    pass
        await loop.run_in_executor(None, self._proc.wait)

    async def wait_async(self) -> int:
        if self._loop is None:
            raise RuntimeError("start() must be called from within an asyncio loop")
        if self._pump_task is not None:
            await self._pump_task
        with self._lock:
            return self._proc.returncode if self._proc else -1

    def wait(self) -> int:  # sync helper for tests
        if self._proc is None:
            return -1
        return self._proc.wait()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                return
            try:
                if os.name == "nt":
                    self._proc.terminate()
                else:
                    self._proc.send_signal(signal.SIGTERM)
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=10000)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def recent_logs(self) -> List[str]:
        return list(self._logs)


    async def _pump_logs(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, self._proc.stdout.readline)
            if not line:
                break
            line = line.rstrip("\n")
            line = redact_secrets(line)
            self._logs.append(line)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(line)
                except asyncio.QueueFull:
                    pass
        await loop.run_in_executor(None, self._proc.wait)

    async def wait_async(self) -> int:
        if self._loop is None:
            raise RuntimeError("start() must be called from within an asyncio loop")
        if self._pump_task is not None:
            await self._pump_task
        with self._lock:
            return self._proc.returncode if self._proc else -1

    def wait(self) -> int:  # sync helper for tests
        if self._proc is None:
            return -1
        return self._proc.wait()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                return
            try:
                if os.name == "nt":
                    self._proc.terminate()
                else:
                    self._proc.send_signal(signal.SIGTERM)
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=10000)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def recent_logs(self) -> List[str]:
        return list(self._logs)
