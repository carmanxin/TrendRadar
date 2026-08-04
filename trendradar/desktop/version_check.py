"""Best-effort GitHub latest release check. Network failures are silent."""
from __future__ import annotations

from typing import Optional

import requests


def fetch_latest(repo: str = "sansan0/TrendRadar", proxy_url: Optional[str] = None) -> Optional[str]:
    try:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            proxies=proxies, timeout=5,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code == 200:
            return r.json().get("tag_name")
    except Exception:
        return None
    return None
