"""Configuration + Clone Hero path discovery.

The rebuilt app stores its own settings under a stable per-user directory so it
never depends on where the executable lives. Clone Hero's own files (the
launcher install registry, the Documents song folder) are discovered using the
same conventions the original CHSuite used.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from .errors import ApiError

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

# Single source of truth for the running app's version. build.bat's version
# bump step rewrites this line (and the matching fields in package.json /
# tauri.conf.json / the frontend) together, so keep the "X.Y.Z" format exact.
APP_VERSION = "8.0.0"


def app_config_dir() -> Path:
    """Per-user directory holding CHSuite's own settings."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "CHSuite"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_FILE = app_config_dir() / "chsuite_config.json"


def installs_file() -> Path:
    """Clone Hero Launcher's install registry (game_installs.json)."""
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", "")) / "net.clonehero" / "ch_launcher" / "game_installs.json"
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / "net.clonehero" / "ch_launcher" / "game_installs.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "net.clonehero" / "ch_launcher" / "game_installs.json"


def documents_clone_hero() -> Path:
    """The user-data Clone Hero folder (songs, badsongs.txt, profiles.ini)."""
    return Path.home() / "Documents" / "Clone Hero"


# ---------------------------------------------------------------------------
# Config read / write
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "theme": "Default",
    "default_data_path": "",
    "ch_default_install": "",
    "sm_songs_dir": "",
    "discord_rpc": False,
    "install_names": {},
    "default_install_dir": "",
}


def get_config() -> dict:
    cfg = dict(_DEFAULTS)
    if CONFIG_FILE.is_file():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError as e:
        raise ApiError(f"Could not save config: {e}", code="config_write", status=500)


def update_config(patch: dict) -> dict:
    cfg = get_config()
    cfg.update({k: v for k, v in patch.items() if not k.startswith("_")})
    save_config(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def detect_installs(_body: dict) -> dict:
    """Best-effort discovery of Clone Hero locations on this machine."""
    result = {
        "documents": str(documents_clone_hero()) if documents_clone_hero().is_dir() else "",
        "badsongs": "",
        "profiles_ini": "",
        "installs_registry": "",
        "installs": [],
    }

    docs = documents_clone_hero()
    if (docs / "badsongs.txt").is_file():
        result["badsongs"] = str(docs / "badsongs.txt")
    if (docs / "profiles.ini").is_file():
        result["profiles_ini"] = str(docs / "profiles.ini")

    reg = installs_file()
    if reg.is_file():
        result["installs_registry"] = str(reg)
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
            for inst in data.get("installs", []):
                p = inst.get("directoryPath") or inst.get("path") or ""
                result["installs"].append({
                    "path": p,
                    "version": inst.get("version") or inst.get("buildVersion") or "?",
                    "fromLauncher": bool(inst.get("isFromLauncher", True)),
                })
        except (json.JSONDecodeError, OSError):
            pass

    return result
