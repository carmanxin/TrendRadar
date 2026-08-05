"""Read/write the per-user user_config.yaml in the OS user config dir.

This module uses a *lazy* loader for `paths` to avoid the eager
`trendradar/__init__.py` import chain (which pulls in litellm and other
heavy deps). In production, when `litellm` is installed and the package
is on `sys.path` normally, the import `from trendradar.desktop import paths`
would also work — but the lazy form keeps the module usable in minimal
test environments and matches the pattern used in `test_paths.py`.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def _load_paths():
    """Lazily import sibling `paths.py` without triggering trendradar/__init__.py.

    This mirrors the importlib trick used in tests/desktop/test_paths.py
    so that `config_store` can be imported in environments where the full
    `trendradar` package (and its litellm dependency) is unavailable.
    """
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "_trendradar_desktop_paths_for_config_store", here / "paths.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load paths module from {here / 'paths.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class ConfigStore:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        audit_log: Optional[Path] = None,
    ):
        paths_mod = _load_paths()
        self.config_path = (
            Path(config_path) if config_path else paths_mod.user_config_file()
        )
        self.audit_log = (
            Path(audit_log) if audit_log else paths_mod.audit_log_file()
        )

    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with self.config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}

    def save(self, data: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp in same dir, then replace.
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.config_path.name + ".",
            dir=str(self.config_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            os.replace(tmp_name, self.config_path)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def update(self, merge: Dict[str, Any]) -> Dict[str, Any]:
        new_data = _deep_merge(self.load(), merge)
        self.save(new_data)
        return new_data

    def set_secret(self, key_path: str, value: Any) -> Dict[str, Any]:
        parts = key_path.split(".")
        overlay: Dict[str, Any] = {}
        cursor = overlay
        for p in parts[:-1]:
            cursor[p] = {}
            cursor = cursor[p]
        cursor[parts[-1]] = value
        result = self.update(overlay)
        self.audit(f"set {key_path}")
        return result

    def audit(self, message: str) -> None:
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        line = f"{ts} {message}\n"
        with self.audit_log.open("a", encoding="utf-8") as f:
            f.write(line)
