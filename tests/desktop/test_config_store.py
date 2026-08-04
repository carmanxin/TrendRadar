"""Tests for trendradar.desktop.config_store.ConfigStore.

Note: this test file loads both `paths` and `config_store` via
`importlib.util.spec_from_file_location` to bypass `trendradar/__init__.py`,
which imports litellm and is not available in the minimal test environment.
This mirrors the pattern in `test_paths.py`.
"""
import importlib.util
from pathlib import Path

# --- Load trendradar/desktop/paths.py (same trick as test_paths.py) ---------
_PATHS_PY = (
    Path(__file__).resolve().parents[2]
    / "trendradar"
    / "desktop"
    / "paths.py"
)
_paths_spec = importlib.util.spec_from_file_location(
    "_trendradar_desktop_paths", _PATHS_PY
)
paths = importlib.util.module_from_spec(_paths_spec)
_paths_spec.loader.exec_module(paths)

# --- Load trendradar/desktop/config_store.py the same way --------------------
_CS_PY = (
    Path(__file__).resolve().parents[2]
    / "trendradar"
    / "desktop"
    / "config_store.py"
)
_cs_spec = importlib.util.spec_from_file_location(
    "_trendradar_desktop_config_store", _CS_PY
)
cs_mod = importlib.util.module_from_spec(_cs_spec)
_cs_spec.loader.exec_module(cs_mod)
ConfigStore = cs_mod.ConfigStore


import pytest


@pytest.fixture(autouse=True)
def isolated_user_config_dir(tmp_path, monkeypatch):
    """Point paths.user_config_dir/file/audit_log at a temp dir for every test.

    This mirrors the autouse fixture in `test_paths.py`. Both files load
    `paths` via importlib, so this monkeypatch on the shared `paths` module
    also affects ConfigStore's lazy lookup.
    """
    monkeypatch.setattr(paths, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(
        paths, "user_config_file", lambda: tmp_path / "user_config.yaml"
    )
    monkeypatch.setattr(
        paths, "audit_log_file", lambda: tmp_path / "audit.log"
    )
    yield tmp_path


def test_load_returns_empty_dict_when_missing(tmp_path: Path):
    store = ConfigStore(tmp_path / "user_config.yaml")
    assert store.load() == {}


def test_save_then_load_roundtrip(tmp_path: Path):
    p = tmp_path / "user_config.yaml"
    store = ConfigStore(p)
    store.save({"ai": {"api_key": "sk-test", "model": "gpt-4o"}})
    assert store.load() == {"ai": {"api_key": "sk-test", "model": "gpt-4o"}}


def test_update_deep_merges(tmp_path: Path):
    p = tmp_path / "user_config.yaml"
    store = ConfigStore(p)
    store.save(
        {"ai": {"api_key": "sk-a", "model": "gpt-4o"}, "ui": {"theme": "dark"}}
    )
    store.update({"ai": {"api_key": "sk-b", "temperature": 0.7}})
    assert store.load() == {
        "ai": {"api_key": "sk-b", "model": "gpt-4o", "temperature": 0.7},
        "ui": {"theme": "dark"},
    }


def test_set_secret_uses_dot_path(tmp_path: Path):
    p = tmp_path / "user_config.yaml"
    store = ConfigStore(p)
    store.set_secret("ai.api_key", "sk-new")
    assert store.load()["ai"]["api_key"] == "sk-new"


def test_audit_appends_line(tmp_path: Path):
    p = tmp_path / "user_config.yaml"
    audit = tmp_path / "audit.log"
    store = ConfigStore(p, audit_log=audit)
    store.audit("wizard completed")
    store.audit("api key changed")
    content = audit.read_text(encoding="utf-8")
    assert content.count("\n") == 2
    assert "wizard completed" in content
    assert "api key changed" in content


def test_save_is_atomic(tmp_path: Path):
    p = tmp_path / "user_config.yaml"
    store = ConfigStore(p)
    store.save({"k": 1})
    # No leftover temp file in dir
    leftovers = [f for f in tmp_path.iterdir() if f.name.startswith("user_config.yaml.")]
    assert leftovers == []
