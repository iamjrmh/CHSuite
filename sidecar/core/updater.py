"""CHSuite self-update check + install.

Same GitHub repo and release feed the original Tkinter CHSuite used - this
rebuild is published to the same repo. Mirrors how userdeck's Configurator
handles updates: download the installer to a temp dir, spawn it detached
(visible, not silent, so the user sees and drives the actual install), then
let the frontend close the app so the installer can replace the running
files. Runs as a background job (like every other download in this sidecar)
so the frontend can show real progress instead of an indeterminate spinner.
"""

from __future__ import annotations

import copy
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from . import config
from .errors import ApiError, MissingDependency

_GITHUB_REPO = "iamjrmh/CHSuite"
_API_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
_RELEASES_URL = f"https://github.com/{_GITHUB_REPO}/releases"

_install_jobs: dict[str, dict] = {}
_install_lock = threading.Lock()


def _requests():
    try:
        import requests  # noqa: PLC0415
        return requests
    except ImportError as e:
        raise MissingDependency("requests", "checking for updates") from e


def _parse_version(v: str) -> tuple[int, ...]:
    v = (v or "").strip().lstrip("vV")
    parts = []
    for chunk in v.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _pick_installer_asset(assets: list[dict]) -> dict | None:
    # Prefer the NSIS .exe (matches userdeck's preference) - simpler
    # double-click flow than the MSI for a self-update prompt.
    exe = next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None)
    if exe:
        return exe
    return next((a for a in assets if a.get("name", "").lower().endswith(".msi")), None)


def check(_body: dict | None = None) -> dict:
    requests = _requests()
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
    assets = [
        {"name": a.get("name", ""), "url": a.get("browser_download_url", ""), "size": a.get("size", 0)}
        for a in data.get("assets", [])
    ]
    installer = _pick_installer_asset(assets)
    return {
        "current": config.APP_VERSION,
        "latest": latest_tag.lstrip("vV"),
        "updateAvailable": _is_newer(latest_tag, config.APP_VERSION),
        "url": data.get("html_url") or _RELEASES_URL,
        "publishedAt": data.get("published_at", ""),
        "notes": data.get("body", ""),
        "installerUrl": installer["url"] if installer else "",
        "installerName": installer["name"] if installer else "",
    }


def _launch_installer(path: Path) -> None:
    if config.IS_WINDOWS:
        detached_process = 0x00000008
        create_new_process_group = 0x00000200
        subprocess.Popen(
            [str(path)],
            creationflags=detached_process | create_new_process_group,
            close_fds=True,
        )
    else:
        subprocess.Popen([str(path)], close_fds=True, start_new_session=True)


def start_install_update(body: dict) -> dict:
    url = body.get("url") or ""
    name = body.get("name") or ""
    if not url or not name:
        raise ApiError("Missing installer info.", code="empty")

    requests = _requests()
    dest = Path(tempfile.gettempdir()) / name

    job_id = uuid.uuid4().hex
    with _install_lock:
        _install_jobs[job_id] = {
            "status": "running", "downloaded": 0, "total": 0, "message": "Starting download…",
        }

    def run() -> None:
        try:
            downloaded = 0
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0)
                with _install_lock:
                    _install_jobs[job_id]["total"] = total
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        mb = downloaded / 1_048_576
                        msg = f"Downloading… {mb:.1f} / {total / 1_048_576:.1f} MB" if total else f"Downloading… {mb:.1f} MB"
                        with _install_lock:
                            _install_jobs[job_id]["downloaded"] = downloaded
                            _install_jobs[job_id]["message"] = msg

            with _install_lock:
                _install_jobs[job_id]["message"] = "Launching installer…"

            _launch_installer(dest)

            with _install_lock:
                _install_jobs[job_id] = {
                    "status": "done", "downloaded": downloaded, "total": downloaded,
                    "message": "Installer launched.", "path": str(dest),
                }
        except Exception as e:  # noqa: BLE001
            with _install_lock:
                _install_jobs[job_id] = {"status": "error", "error": str(e)}

    threading.Thread(target=run, daemon=True).start()
    return {"jobId": job_id}


def install_update_status(body: dict) -> dict:
    job_id = body.get("jobId", "")
    with _install_lock:
        job = _install_jobs.get(job_id)
        if job is None:
            raise ApiError("Unknown update-install job.", code="not_found", status=404)
        return copy.deepcopy(job)
