"""Tests for the autostart module (platform backends mocked for determinism)."""
import importlib.util
from pathlib import Path

_AUTOSTART_PY = Path(__file__).resolve().parents[2] / "trendradar" / "desktop" / "autostart.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


autostart = _load("_autostart_test", _AUTOSTART_PY)


def test_set_and_get_autostart_roundtrip(tmp_path, monkeypatch):
    fake_exe = tmp_path / "fake.exe"
    fake_exe.write_text("")
    reg_file = tmp_path / "regstate.json"

    def fake_set(enabled, exe_path):
        import json
        reg_file.write_text(json.dumps({"enabled": enabled, "exe": exe_path}), encoding="utf-8")

    def fake_get(exe_path):
        import json
        if not reg_file.exists():
            return False
        data = json.loads(reg_file.read_text(encoding="utf-8"))
        return bool(data.get("enabled")) and data.get("exe") == exe_path

    # Stub the platform-specific helpers so the roundtrip is deterministic
    # and does NOT touch the real registry / LaunchAgents / autostart dirs.
    monkeypatch.setattr(autostart, "_windows_set", fake_set)
    monkeypatch.setattr(autostart, "_windows_get", fake_get)

    autostart.set_enabled(True, str(fake_exe))
    assert autostart.is_enabled(str(fake_exe)) is True
    autostart.set_enabled(False, str(fake_exe))
    assert autostart.is_enabled(str(fake_exe)) is False
