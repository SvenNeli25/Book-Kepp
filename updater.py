from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from app_version import GITHUB_REPO, __version__


_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _parse_version(v: str) -> Optional[tuple[int, int, int]]:
    m = _TAG_RE.match((v or "").strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _cmp(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a > b) - (a < b)


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    latest_tag: str
    release_url: str
    installer_url: Optional[str]


def fetch_latest_release(timeout_s: float = 4.0) -> Optional[dict]:
    """
    Returns the GitHub API JSON object for the latest release, or None if unreachable.
    """
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return None

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            # GitHub blocks requests without a UA sometimes.
            "User-Agent": "Book-Keep-Updater",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def get_update_info(timeout_s: float = 4.0) -> Optional[UpdateInfo]:
    data = fetch_latest_release(timeout_s=timeout_s)
    if not data:
        return None

    latest_tag = (data.get("tag_name") or "").strip()
    latest_v = _parse_version(latest_tag)
    current_v = _parse_version(__version__)
    if not latest_v or not current_v:
        return None

    if _cmp(latest_v, current_v) <= 0:
        return None

    html_url = (data.get("html_url") or "").strip() or f"https://github.com/{GITHUB_REPO}/releases/latest"

    installer_url = None
    assets = data.get("assets") or []
    for a in assets:
        name = (a.get("name") or "").lower()
        url = (a.get("browser_download_url") or "").strip()
        if not url:
            continue
        if name.endswith(".exe") or name.endswith(".msi"):
            installer_url = url
            break

    return UpdateInfo(
        current_version=__version__,
        latest_version=".".join(str(x) for x in latest_v),
        latest_tag=latest_tag,
        release_url=html_url,
        installer_url=installer_url,
    )

