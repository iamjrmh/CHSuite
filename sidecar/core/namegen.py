"""CHNameGen export.

The colored-name *markup* (TextMesh Pro ``<color>`` tags, gradient / per-letter)
is generated client-side in the frontend - it is pure, instant, and needs no
filesystem access. This module only handles persisting a finished markup string
into Clone Hero's ``profiles.ini``, preserving every other line untouched.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import documents_clone_hero
from .errors import ApiError

_COLOR_TAGS = re.compile(r"<color=[^>]*>|</color>|<b>|</b>|<i>|</i>|<u>|</u>|<s>|</s>")


def _resolve_path(body: dict) -> Path:
    path = body.get("path")
    if path:
        return Path(path)
    auto = documents_clone_hero() / "profiles.ini"
    return auto


def _parse_sections(path: Path):
    """Return list of (section_name, [raw_lines]) for [profileN] blocks."""
    sections = []
    current = None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return sections
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            inner = stripped[1:-1]
            if inner.startswith("profile") and inner[7:].isdigit():
                current = [line]
                sections.append((inner, current))
                continue
            current = None
        if current is not None:
            current.append(line)
    return sections


def _player_name(raw_lines) -> str:
    for line in raw_lines:
        s = line.strip()
        if s.startswith("player_name"):
            idx = s.find("=")
            if idx != -1:
                return s[idx + 1:].strip().strip('"')
    return ""


def _plain(name: str) -> str:
    return _COLOR_TAGS.sub("", name)


def list_profiles(body: dict) -> dict:
    path = _resolve_path(body)
    if not path.is_file():
        return {"path": str(path), "exists": False, "profiles": []}
    sections = _parse_sections(path)
    profiles = []
    for sec, raw in sections:
        pname = _player_name(raw)
        profiles.append({"section": sec, "name": _plain(pname) or sec, "raw": pname})
    return {"path": str(path), "exists": True, "profiles": profiles}


def export_profile_name(body: dict) -> dict:
    markup = body.get("markup") or ""
    if not markup:
        raise ApiError("No generated name to export.", code="empty")
    path = _resolve_path(body)
    index = body.get("profileIndex")

    sections = _parse_sections(path) if path.is_file() else []

    # Create a fresh file if there is nothing to merge into.
    if not sections:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"[profile0]\nplayer_name = {markup}\n", encoding="utf-8")
        except OSError as e:
            raise ApiError(f"Could not create profiles.ini: {e}", code="write", status=500)
        return {"path": str(path), "created": True, "profile": "profile0"}

    # Append a new profile slot when the caller asks for one (or out of range).
    if index is None or index < 0 or index >= len(sections):
        new_key = f"profile{len(sections)}"
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n[{new_key}]\nplayer_name = {markup}\n")
        except OSError as e:
            raise ApiError(f"Could not write profiles.ini: {e}", code="write", status=500)
        return {"path": str(path), "created": True, "profile": new_key}

    # Replace player_name in the chosen existing profile, minimal diff.
    sec_name, raw_lines = sections[index]
    replaced = False
    for i, line in enumerate(raw_lines):
        if line.strip().startswith("player_name"):
            indent = line[: len(line) - len(line.lstrip())]
            eol = "\n" if line.endswith("\n") else ""
            raw_lines[i] = f"{indent}player_name = {markup}{eol}"
            replaced = True
            break
    if not replaced:
        insert_at = 1 if len(raw_lines) > 1 else len(raw_lines)
        raw_lines.insert(insert_at, f"player_name = {markup}\n")

    # Reassemble: walk the original file, swapping only this section's block.
    try:
        original = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError as e:
        raise ApiError(f"Could not read profiles.ini: {e}", code="read", status=500)

    rebuilt, idx, in_target = [], 0, False
    target_header = f"[{sec_name}]"
    for line in original:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_target = stripped == target_header
            if in_target:
                rebuilt.extend(raw_lines)
                continue
        if not in_target:
            rebuilt.append(line)
    try:
        path.write_text("".join(rebuilt), encoding="utf-8")
    except OSError as e:
        raise ApiError(f"Could not save profiles.ini: {e}", code="write", status=500)
    return {"path": str(path), "created": False, "profile": sec_name}
