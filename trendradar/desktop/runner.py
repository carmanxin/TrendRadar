"""Subprocess manager that streams redacted stdout via a thread-safe queue.

Runs a dedicated pump thread that reads the subprocess's stdout line by
line, redacts secrets, appends to a ring buffer, and fans out to subscriber
queues. Works whether `start()` is called from an async context (FastAPI
route) or a sync context (system tray thread). Subscribers use
`queue.Queue` (thread-safe); async consumers poll via asyncio.to_thread.

This module uses a lazy loader for `errors` to avoid the eager
`trendradar/__init__.py` chain (litellm).
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import queue
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
    """Owns at most one subprocess. Thread-safe start/wait, stream API."""

    _RING_BUFFER_SIZE = 10_000

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._subscribers: List[queue.Queue] = []
        self._logs: Deque[str] = deque(maxlen=self._RING_BUFFER_SIZE)
        self._lock = threading.Lock()
        self._pump_thread: Optional[threading.Thread] = None

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
            # Reuse live subscriber queues, but clear stale ones from previous runs.
            self._subscribers = [q for q in self._subscribers if q is not None]
            self._pump_thread = threading.Thread(target=self._pump_loop, daemon=True)
            self._pump_thread.start()

    def _pump_loop(self) -> None:
        """Read subprocess stdout line-by-line until EOF; then wait for exit."""
        assert self._proc is not None and self._proc.stdout is not None
        try:
            for raw in self._proc.stdout:
                line = raw.rstrip("\n")
                line = redact_secrets(line)
                self._logs.append(line)
                for q in list(self._subscribers):
                    try:
                        q.put_nowait(line)
                    except queue.Full:
                        pass
        finally:
            try:
                self._proc.wait()
            except Exception:
                pass
            # Notify subscribers of stream end.
            for q in list(self._subscribers):
                try:
                    q.put_nowait(None)  # sentinel: stream closed
                except queue.Full:
                    pass

    async def wait_async(self) -> int:
        return await asyncio.to_thread(self.wait)

    def wait(self) -> int:  # sync helper
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

    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=10000)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def recent_logs(self) -> List[str]:
        return list(self._logs)
