"""CHNoteGen export.

The full color editor (157 keys across guitar / drums / sixfret / other) is
rendered in the frontend from the extracted ``notegen_data.json``. This module
takes the finished ``colors`` map and writes Clone Hero's colors INI, matching
the original section ordering.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from .config import detect_installs, documents_clone_hero, get_config
from .errors import ApiError

_SECTION_ORDER = ["sixfret", "drums", "other", "guitar"]


def _generate_ini(colors: dict) -> str:
    lines: list[str] = []
    for section in _SECTION_ORDER:
        if section not in colors:
            continue
        lines.append(f"[{section}]")
        for key, val in colors[section].items():
            lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines)


def export(body: dict) -> dict:
    colors = body.get("colors")
    if not isinstance(colors, dict) or not colors:
        raise ApiError("No colors supplied to export.", code="empty")

    name = (body.get("profileName") or "colors").strip() or "colors"
    if not name.lower().endswith(".ini"):
        name += ".ini"

    target = body.get("path")
    if target:
        path = Path(target)
        if path.is_dir():
            path = path / name
    else:
        path = documents_clone_hero() / name

    text = _generate_ini(colors)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as e:
        raise ApiError(f"Could not write color INI: {e}", code="write", status=500)

    return {"path": str(path), "sections": [s for s in _SECTION_ORDER if s in colors]}


# ---------------------------------------------------------------------------
# Profile auto-detection - scans the folders Clone Hero (and this app's own
# Export) keep colour INIs in, the same locations the original CHSuite did.
# ---------------------------------------------------------------------------

def _colors_dirs() -> list[Path]:
    """Every plausible Custom/Colors location, not just the first one that
    resolves - ``ch_default_install`` is sometimes the launcher's base folder
    (e.g. ``Clone Hero/``) rather than the actual versioned game folder
    (``Clone Hero/v1.2.3/``), so it can be a *valid* directory that still
    isn't the right one. Trying every candidate base avoids stopping early on
    a technically-real-but-wrong path."""
    dirs: list[Path] = [documents_clone_hero()]

    cfg = get_config()
    bases: list[Path] = []

    default_install = cfg.get("ch_default_install", "")
    if default_install and Path(default_install).is_dir():
        bases.append(Path(default_install))

    data_path = cfg.get("default_data_path", "")
    if data_path and Path(data_path).is_dir():
        bases.append(Path(data_path).parent)

    for inst in detect_installs({}).get("installs", []):
        p = inst.get("path", "")
        if p and Path(p).is_dir():
            bases.append(Path(p))

    seen: set[str] = set()
    for base in bases:
        key = str(base)
        if key in seen:
            continue
        seen.add(key)
        dirs.append(base / "Custom" / "Colors")
        dirs.append(base / "PlayerData" / "Custom" / "Colors")

    return dirs


def _parse_ini(path: Path) -> dict:
    parser = configparser.ConfigParser(allow_no_value=True)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return {}
    result: dict = {}
    for section in parser.sections():
        sec = {}
        for key, val in parser.items(section):
            if val and val.strip():
                sec[key.lower()] = val.strip().upper()
        if sec:
            result[section.lower()] = sec
    return result


def list_profiles(_body: dict) -> dict:
    """Auto-detect saved colour profiles, mirroring the original CHSuite's scan."""
    profiles: list[dict] = []
    seen: set[str] = set()
    for colors_dir in _colors_dirs():
        if not colors_dir.is_dir():
            continue
        for ini_path in sorted(colors_dir.glob("*.ini")):
            name = ini_path.stem
            if name in seen:
                continue
            parsed = _parse_ini(ini_path)
            if not any(section in parsed for section in _SECTION_ORDER):
                continue
            seen.add(name)
            profiles.append({"name": name, "colors": parsed})
    return {"profiles": profiles}
