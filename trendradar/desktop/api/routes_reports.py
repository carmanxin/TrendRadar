"""List historical HTML reports.

Self-contained: no imports from the trendradar package, so no lazy-loader
needed.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/reports", tags=["reports"])

_HTML_ROOT = Path("output") / "html"


def _scan_dates():
    if not _HTML_ROOT.exists():
        return []
    return sorted(p.name for p in _HTML_ROOT.iterdir() if p.is_dir() and p.name != "latest")


@router.get("")
def list_reports():
    reports = []
    for date in reversed(_scan_dates()):
        day_dir = _HTML_ROOT / date
        htmls = sorted(day_dir.glob("*.html"))
        reports.append({
            "date": date,
            "files": [str(p.relative_to(_HTML_ROOT)) for p in htmls][-10:],
        })
    return {"reports": reports}


@router.get("/latest")
def latest_report(mode: str = "daily"):
    latest = _HTML_ROOT / "latest" / f"{mode}.html"
    if not latest.exists():
        raise HTTPException(status_code=404, detail=f"no latest report for mode={mode}")
    return {"path": str(latest)}
