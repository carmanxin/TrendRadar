# TrendRadar Desktop — Architecture & Dev Notes

This document is the developer-facing companion to the design spec at `docs/superpowers/specs/2026-08-04-trendradar-desktop-design.md`.

## Layout
- All desktop code lives under `trendradar/desktop/`. It must NOT import or modify anything outside `trendradar/desktop/` + `trendradar/__init__.py`.
- The bundled executable is produced by `packaging/build.py` using the PyInstaller spec at `packaging/trendradar.spec`.
- The CI build is at `.github/workflows/build-desktop.yml` (Windows / macOS / Linux matrix).

## Running in dev
```bash
pip install -e .
TRENDRADAR_DESKTOP_NO_TRAY=1 python -m trendradar.desktop
```
Then open <http://127.0.0.1:8765>.

> Note: dev mode requires the full core dependencies (especially `litellm`) because
> `trendradar/__init__.py` imports `AppContext` eagerly. The bundled executable
> always includes them, so this only affects `python -m` development runs.

## Running the bundled app
1. Run `python packaging/build.py`.
2. Distribute `dist/TrendRadar/` (or zip it).
3. Double-click `TrendRadar.exe` (or the equivalent on the target OS).

## Configuration storage
- User secrets (API keys): `%APPDATA%/TrendRadar/user_config.yaml` (Windows) / `~/Library/Application Support/TrendRadar/` (macOS) / `~/.config/TrendRadar/` (Linux).
- Override for tests & portable installs: set `TRENDRADAR_USER_CONFIG_DIR` env var.
- Audit log: `audit.log` in the same directory.
- Project YAML (`config/config.yaml`, `config/frequency_words.txt`, `config/ai_interests.txt`) lives next to the executable and is edited by the WebUI.

## Secret masking
- `trendradar.desktop.runner.redact_secrets` rewrites any `api_key=…`, `token=…`, `password=…` substring to `***` before logs reach the SSE stream or UI.
- `trendradar.desktop.runner.mask_config` masks known secret paths in the config dict returned to the WebUI (first 6 + `****` + last 2 chars).

## The lazy-importlib pattern (IMPORTANT)
Because `trendradar/__init__.py` eagerly imports `AppContext` (which pulls in `litellm`),
desktop modules must NOT use `from trendradar.desktop.X import Y` at module top level —
that triggers the parent package init. Every cross-module reference inside
`trendradar/desktop/` uses `importlib.util.spec_from_file_location` at call time
(lazy loader functions named `_load_*`). Test files use the same trick.
This keeps desktop modules importable in minimal test environments where litellm
is not installed, and is invisible to the PyInstaller bundle (which includes litellm).

## API endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/system/status` | `NEED_WIZARD` / `READY` + port + version |
| GET | `/api/system/info` | OS, user config dir, audit log, version |
| GET/PUT | `/api/system/autostart` | read / set run-at-login |
| GET | `/api/system/version-check` | GitHub latest release vs current |
| POST | `/api/wizard/complete` | first-run wizard: AI base/key/model/timezone |
| GET/PUT | `/api/config`, `/api/config/section/{name}` | read (masked) / update project config |
| GET/PUT | `/api/keywords` | read / write `config/frequency_words.txt` |
| GET/PUT | `/api/interests` | read / write `config/ai_interests.txt` |
| GET/PUT | `/api/sources/platforms`, `/api/sources/rss` | enable/disable sources |
| POST | `/api/run/start`, `/api/run/stop` | start/stop the TrendRadar subprocess |
| GET | `/api/run/logs` | last 500 redacted log lines |
| GET | `/api/run/logs/stream` | SSE stream of redacted logs |
| GET | `/api/reports`, `/api/reports/latest?mode=` | list / latest HTML reports |

## Testing
```bash
pip install pytest pytest-asyncio
pytest tests/desktop -v
```
The smoke test (`tests/desktop/test_smoke.py`) only runs when `TRENDRADAR_SMOKE=1` is set
(used by CI after `pip install -e .`).

## Building release artifacts
GitHub Actions workflow at `.github/workflows/build-desktop.yml` produces platform
artifacts on every push that touches the desktop code, or via `workflow_dispatch`.
