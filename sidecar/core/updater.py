"""CHSuite self-update check.

Same GitHub repo and release feed the original Tkinter CHSuite used - this
rebuild is published to the same repo. Unlike the original, this only
reports whether a newer release exists; it doesn't download/replace itself,
since installs here go through the NSIS installer instead of a self-patching
exe.
"""

from __future__ import annotations

from . import config
from .errors import ApiError, MissingDependency

_GITHUB_REPO = "iamjrmh/CHSuite"
_API_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
_RELEASES_URL = f"https://github.com/{_GITHUB_REPO}/releases"


def _parse_version(v: str) -> tuple[int, ...]:
    v = (v or "").strip().lstrip("vV")
    parts = []
    for chunk in v.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def check(_body: dict | None = None) -> dict:
    try:
        import requests  # noqa: PLC0415
    except ImportError as e:
        raise MissingDependency("requests", "checking for updates") from e

    try:
        resp = requests.get(
            _API_URL, timeout=15,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"CHSuite-UpdateChecker/{config.APP_VERSION}",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        raise ApiError(f"Could not reach GitHub: {e}", code="github", status=502)

    latest_tag = data.get("tag_name", "") or data.get("name", "")
    return {
        "current": config.APP_VERSION,
        "latest": latest_tag.lstrip("vV"),
        "updateAvailable": _is_newer(latest_tag, config.APP_VERSION),
        "url": data.get("html_url") or _RELEASES_URL,
        "publishedAt": data.get("published_at", ""),
        "notes": data.get("body", ""),
    }
