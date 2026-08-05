"""One-shot PyInstaller build."""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main() -> int:
    if not (ROOT / "config" / "config.yaml").exists():
        print("ERROR: run from a checkout that has config/config.yaml", file=sys.stderr)
        return 1
    spec = HERE / "trendradar.spec"
    cmd = ["pyinstaller", "--noconfirm", "--clean", str(spec)]
    print("Running:", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(HERE))
    if rc != 0:
        return rc
    out = ROOT / "dist" / "TrendRadar"
    if not out.exists():
        print("ERROR: dist/TrendRadar not produced", file=sys.stderr)
        return 1
    # Copy config templates next to the executable so first launch can read them.
    config_dst = out / "config"
    if config_dst.exists():
        shutil.rmtree(config_dst)
    shutil.copytree(ROOT / "config", config_dst)
    print(f"Build OK. Output: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
