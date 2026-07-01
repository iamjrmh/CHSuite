"""CHCleaner - parse badsongs.txt and bulk-delete ERROR song folders.

Ported faithfully from the original CHCleaner logic: only folders listed under
``ERROR:`` sections are eligible; ``Warning:`` sections are ignored.
"""

from __future__ import annotations

import datetime
import re
import shutil
from pathlib import Path

from .config import documents_clone_hero
from .errors import ApiError


def _deep_clean_path(path_str: str) -> str:
    match = re.search(r"\((([a-zA-Z]:\\.*?))\)", path_str)
    if match:
        path_str = match.group(1)
    if "e}" in path_str:
        path_str = path_str.split("e}")[0]
    return path_str.strip().rstrip("]")


def _parse(badsongs_path: str) -> list[str]:
    p = Path(badsongs_path)
    if not badsongs_path or not p.is_file():
        return []
    bad: set[str] = set()
    in_error = False
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("ERROR:"):
                in_error = True
                continue
            if line.startswith("Warning:"):
                in_error = False
                continue
            if in_error and (":\\" in line or ":/" in line):
                bad.add(_deep_clean_path(line))
    return sorted(bad)


def parse_bad_songs(body: dict) -> dict:
    path = body.get("path") or ""
    folders = _parse(path)
    items = []
    for fp in folders:
        items.append({
            "path": fp,
            "name": Path(fp).name or fp,
            "exists": Path(fp).is_dir(),
        })
    return {"path": path, "count": len(items), "songs": items}


def delete_songs(body: dict) -> dict:
    paths = body.get("paths") or []
    if not isinstance(paths, list) or not paths:
        raise ApiError("No song folders supplied for deletion.", code="empty")

    log_dir = documents_clone_hero()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "deletedsongs.log"

    deleted, missing, failed = [], [], []
    lines = [f"-- Deletion started at {datetime.datetime.now():%Y-%m-%d %H:%M:%S} --"]

    for raw in paths:
        p = Path(raw)
        if not p.exists():
            missing.append(raw)
            lines.append(f"⚠ Not found: {raw}")
            continue
        try:
            shutil.rmtree(p)
            deleted.append(raw)
            lines.append(f"✓ Deleted Folder: {raw}")
        except Exception as e:  # noqa: BLE001
            failed.append({"path": raw, "error": str(e)})
            lines.append(f"✗ Failed: {raw}\n  Error: {e}")

    lines.append("=" * 60)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass

    return {
        "deleted": deleted,
        "missing": missing,
        "failed": failed,
        "log": str(log_path),
    }
