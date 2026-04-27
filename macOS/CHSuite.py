"""
CHSuite  by JURMR  v7.1
=======================
All-in-one Clone Hero utility suite.  (Split entry point.)

This is the SPLIT version of CHSuite.py.  Sibling modules
(CHMenuChanger, CHNameGen, CHNoteGen, CHCleaner, CHPatcher,
CHSongManager, CHManager) each provide one mixin class that is
composed into the final ``CHSuite`` class at the bottom of this file.
"""

"""
CHSuite  by JURMR  v7.1
=======================
All-in-one Clone Hero utility suite.

  • CHMenuChanger  — swap in-game menu backgrounds via UnityPy
  • CHNameGen      — gradient / per-letter Clone Hero name tags
  • CHNoteGen      — note/color profile editor with live highway preview
  • CHCleaner      — parse badsongs.txt and delete ERROR folders
  • CHSongManager  — download any song from chorus encore directly from CHSuite
  • CHPatcher      — patch the launcher so it stops resetting game files

Dependencies (CHMenuChanger tab only):
    pip install Pillow UnityPy

Python 3.9+
"""

import os as _os

def load_base64(key, _b64_file=None):
    """Return the base64 string stored under *key* in base64.txt.

    Path resolution (evaluated lazily so frozen builds work correctly):
      • Running from source  → base64.txt sits next to CHSuite.py.
      • Frozen by PyInstaller (onedir) → base64.txt is bundled inside
        _internal/ which PyInstaller exposes as sys._MEIPASS at runtime.
    The old approach of using _os.path.dirname(__file__) as a default
    argument fails when frozen because __file__ is evaluated at import time
    inside the PYZ archive and may not resolve to the expected directory.
    """
    if _b64_file is None:
        import sys as _sys
        if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
            # Frozen: base64.txt was bundled into _internal/ (destination ".")
            _b64_file = _os.path.join(_sys._MEIPASS, "base64.txt")
        else:
            # Source: base64.txt lives next to CHSuite.py
            _b64_file = _os.path.join(
                _os.path.dirname(_os.path.abspath(__file__)), "base64.txt"
            )
    with open(_b64_file, "r", encoding="utf-8") as _fh:
        for _line in _fh:
            _line = _line.strip()
            if _line.startswith(key + " = "):
                return _line[len(key) + 3:]
    raise KeyError(f"base64 key {key!r} not found in {_b64_file!r}")

# ── stdlib ─────────────────────────────────────────────────────────────────────
import os
import sys
import re
import json
import copy
import math
import colorsys
import shutil
import threading
import subprocess
import tempfile
import platform
import configparser

# ── OS detection (set once, used everywhere) ──────────────────────────────────
_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX   = sys.platform.startswith("linux")
_IS_MAC     = sys.platform == "darwin"

# Clone Hero's data folder is named differently per platform:
#   Windows → "Clone Hero_Data",  Linux → "clonehero_Data",  macOS → "Data"
_CH_DATA_DIR = ("clonehero_Data" if _IS_LINUX
                else ("Data"           if _IS_MAC
                else  "Clone Hero_Data"))

# Executable candidates (in priority order)
_CH_EXE_CANDIDATES_WIN = ("Clone Hero.exe", "clonehero.exe", "CloneHero.exe")
_CH_EXE_CANDIDATES_LIN = ("clonehero", "Clone Hero", "clonehero.x86_64")
_CH_EXE_CANDIDATES_MAC = ("Clone Hero",)          # executable inside Contents/MacOS/
import datetime
import urllib.request
from pathlib import Path

# ── macOS: Clone Hero ships as an app bundle at this well-known location.
# The game data folder lives at Contents/Resources/Data inside that bundle.
_MAC_CH_APP       = Path("/Applications/Clone Hero.app")
_MAC_CH_DATA_PATH = _MAC_CH_APP / "Contents" / "Resources" / "Data"

# ── tkinter ────────────────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

# ──────────────────────────────────────────────────────────────────────────────
#  GLOBAL COLOUR / FONT CONSTANTS  (defined early — used by the dep bootstrap)
# ──────────────────────────────────────────────────────────────────────────────

C = dict(
    bg="#0c0e13",
    panel="#13161f",
    card="#181c28",
    card2="#1c2030",
    sidebar="#0f111a",
    border="#252b3d",
    border2="#2e3650",
    accent="#6c3bff",
    accent_dim="#3d2299",
    accent2="#ff3b8a",
    accent3="#00d4aa",
    text="#e9ecf8",
    text_dim="#636b82",
    text_mid="#9aa3bf",
    success="#22c55e",
    warn="#f59e0b",
    error="#ef4444",
    selected="#341a7a",
    hover="#1e2235",
    nav_active="#6c3bff",
    nav_hover="#1e2235",
    nav_btn="#09010f",
)

FT  = ("Lato", 10)
FTB = ("Lato", 10, "bold")
FTS = ("Lato", 8)
FTH = ("Lato", 13, "bold")
FTT = ("Lato", 20, "bold")
FTM = ("Lato", 9)
FT_LABEL = ("Lato", 9)

# ── Embedded window icon (JURMRWEED.png, base64) ─────────────────────────────
_ICON_B64 = load_base64("KEY_0")

# ── Embedded Lato font (lato.ttf, base64) ────────────────────────────────────
# Run embed_font.py once to populate this value before building the .exe.
_LATO_B64 = load_base64("KEY_1")
_LATO_BOLD_B64 = load_base64("KEY_2")


def _register_ttf(b64_payload: str, prefix: str) -> bool:
    """Decode a base64 TTF, write to a temp file, and register with the OS.
    Returns True on success, False on any failure (always silent)."""
    import base64 as _b64
    if not b64_payload:
        return False
    try:
        data = _b64.b64decode(b64_payload)
        import tempfile as _tf
        fd, path = _tf.mkstemp(suffix=".ttf", prefix=prefix)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            if sys.platform == "win32":
                import ctypes as _ct
                # FR_PRIVATE (0x10) keeps the font scoped to this process
                return _ct.windll.gdi32.AddFontResourceExW(path, 0x10, None) > 0
            # macOS / Linux: font is in the temp file; tkinter may pick it up
            # once the font cache is aware of the temp dir.
            return True
        except Exception:
            try:
                os.unlink(path)
            except Exception:
                pass
            return False
    except Exception:
        return False


_LATO_LOADED      = _register_ttf(_LATO_B64,      "chsuite_lato_")
_LATO_BOLD_LOADED = _register_ttf(_LATO_BOLD_B64, "chsuite_latobold_")

# ──────────────────────────────────────────────────────────────────────────────
#  DEPENDENCY BOOTSTRAP  (Pillow + UnityPy + pypresence)
# ──────────────────────────────────────────────────────────────────────────────

def _check_deps():
    if getattr(sys, "frozen", False):
        return
    missing = []
    try:
        from PIL import Image  # noqa
    except ImportError:
        missing.append("Pillow")
    try:
        import UnityPy  # noqa
    except ImportError:
        missing.append("UnityPy")
    try:
        import pypresence  # noqa
    except ImportError:
        missing.append("pypresence")
    if not missing:
        return

    exe     = sys.executable
    pkgs    = missing[:]
    pip_cmd = [exe, "-m", "pip", "install"] + pkgs

    _root = tk.Tk(); _root.withdraw()
    answer = messagebox.askyesno(
        "Install required packages",
        "The following package(s) are missing:\n\n"
        + "\n".join("  - " + m for m in missing)
        + "\n\nPython: " + exe
        + "\n\nClick YES to install now. Click NO to continue without them\n"
          "(CHMenuChanger will be unavailable without Pillow/UnityPy;\n"
          " Discord Rich Presence will be unavailable without pypresence).",
        icon="warning")
    _root.destroy()
    if not answer:
        return

    _pr = tk.Tk(); _pr.title("Installing…")
    _pr.configure(bg=C["bg"]); _pr.resizable(False, False); _pr.geometry("500x120")
    tk.Label(_pr, text="Installing: " + " ".join(pkgs),
             font=("Lato", 11), bg=C["bg"], fg=C["text"], pady=20).pack()
    tk.Label(_pr, text="Running pip, please wait…",
             font=("Lato", 9), bg=C["bg"], fg=C["text_dim"]).pack()
    _pr.update()
    try:
        cflags = 0x08000000 if sys.platform == "win32" else 0
        result = subprocess.run(pip_cmd, capture_output=True,
                                text=True, timeout=180, creationflags=cflags)
    except Exception as ex:
        _pr.destroy()
        messagebox.showerror("Install error", str(ex))
        return
    _pr.destroy()
    if result.returncode != 0:
        messagebox.showerror("pip failed",
                             "pip exited with code {}:\n\n{}".format(
                                 result.returncode,
                                 (result.stderr or result.stdout)[:600]))

_check_deps()

# ── optional imports (graceful fallback) ───────────────────────────────────────
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import UnityPy
    _UNITYPY_OK = True
except ImportError:
    _UNITYPY_OK = False

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    from pypresence import Presence as _DiscordPresence
    _PYPRESENCE_OK = True
except ImportError:
    _PYPRESENCE_OK = False


# ──────────────────────────────────────────────────────────────────────────────
#  PERSISTENT STORAGE PATHS
# ──────────────────────────────────────────────────────────────────────────────

def _app_dir():
    """
    Mutable data directory (config, logs, profiles, generated files).
    On macOS .app bundles the bundle Contents/MacOS is read-only after signing,
    so we redirect to ~/Library/Application Support/CHSuite instead.
    """
    if getattr(sys, "frozen", False) and _IS_MAC:
        d = Path.home() / "Library" / "Application Support" / "CHSuite"
        d.mkdir(parents=True, exist_ok=True)
        return d
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _resources_dir():
    """
    Read-only bundled assets directory (Images, themes).

    macOS .app  → Contents/Resources/  (PyInstaller BUNDLE layout)
    Win/Linux frozen → sys._MEIPASS  (PyInstaller 6+ places all bundled
                        datas inside _internal/ next to the exe, accessible
                        via sys._MEIPASS in both onedir and onefile modes)
    Dev (unfrozen)   → same directory as the script
    """
    if getattr(sys, "frozen", False) and _IS_MAC:
        # sys.executable → .../CHSuite.app/Contents/MacOS/CHSuite
        return Path(sys.executable).parent.parent / "Resources"
    if getattr(sys, "frozen", False):
        # PyInstaller 6+ onedir: all datas live in _internal/ (sys._MEIPASS),
        # NOT in the same folder as the .exe itself.
        _meipass = getattr(sys, "_MEIPASS", None)
        if _meipass:
            return Path(_meipass)
        # Fallback for older PyInstaller (<6): _internal/ if present, else exe dir
        _internal = Path(sys.executable).parent / "_internal"
        if _internal.is_dir():
            return _internal
    return _app_dir()

CONFIG_FILE   = _app_dir() / "chsuite_config.json"
PROFILES_FILE = _app_dir() / "ch_bg_profiles.json"
SCAN_LOG_FILE = _app_dir() / "ch_bg_scan.log"
THEMES_DIR    = _resources_dir() / "themes"
IPC_PORT      = 59832   # ThemeGen live-preview socket

# ──────────────────────────────────────────────────────────────────────────────
#  THEME SYSTEM
# ──────────────────────────────────────────────────────────────────────────────

_THEME_KEYS = (
    "bg", "panel", "card", "card2", "sidebar",
    "border", "border2",
    "accent", "accent_dim", "accent2", "accent3",
    "text", "text_dim", "text_mid",
    "success", "warn", "error",
    "selected", "hover", "nav_active", "nav_hover",
)

def _list_themes() -> list[str]:
    """Return sorted theme names (stems of .json files) found in the themes dir."""
    if not THEMES_DIR.is_dir():
        return ["Default"]
    names = []
    for p in sorted(THEMES_DIR.glob("*.json")):
        if p.stem != "Template":
            names.append(p.stem)
    return names if names else ["Default"]

def _load_theme(name: str) -> bool:
    """
    Load a theme JSON from themes/<name>.json and update the global C dict.
    Returns True on success, False on any error (C is left unchanged on error).
    Falls back to built-in defaults if the file is missing.
    """
    path = THEMES_DIR / f"{name}.json"
    if not path.is_file():
        # Silently keep the current theme if file not found
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    # Validate: every required key must map to a non-empty string
    for k in _THEME_KEYS:
        v = raw.get(k, "")
        if not isinstance(v, str) or not v.startswith("#"):
            return False
    # All good — update the live C dict in-place so all existing references
    # (strings captured in lambdas) still point to the same dict object.
    for k in _THEME_KEYS:
        C[k] = raw[k]
    return True

# ── CH Launcher registry path (platform-aware) ───────────────────────────────
if _IS_WINDOWS:
    _INSTALLS_FILE = (
        Path(os.environ.get("APPDATA", "")) /
        "net.clonehero" / "ch_launcher" / "game_installs.json"
    )
elif _IS_MAC:
    _INSTALLS_FILE = (
        Path.home() / "Library" / "Application Support" /
        "net.clonehero" / "ch_launcher" / "game_installs.json"
    )
else:  # Linux — XDG config dir, falls back to ~/.config
    _INSTALLS_FILE = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) /
        "net.clonehero" / "ch_launcher" / "game_installs.json"
    )
_LAUNCHER_PROCS = ("CloneHeroLauncher.exe", "ch_launcher.exe", "clone-hero-launcher.exe")


def _launcher_is_running() -> bool:
    """Return True if any known launcher process is currently running."""
    if sys.platform == "win32":
        try:
            flags = 0x08000000
            for proc in ("CloneHeroLauncher.exe", "ch_launcher.exe"):
                out = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc}", "/NH", "/FO", "CSV"],
                    capture_output=True, text=True, creationflags=flags).stdout
                if proc.lower() in out.lower():
                    return True
        except Exception:
            pass
        return False
    else:
        for proc in _LAUNCHER_PROCS:
            try:
                if subprocess.run(["pgrep", "-f", proc],
                                  capture_output=True).returncode == 0:
                    return True
            except Exception:
                pass
        return False


def _kill_launcher() -> bool:
    """Force-kill the CH Launcher. Returns True if something was killed."""
    killed = False
    if sys.platform == "win32":
        for proc in _LAUNCHER_PROCS:
            try:
                r = subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    capture_output=True, creationflags=0x08000000)
                if r.returncode == 0:
                    killed = True
            except Exception:
                pass
    else:
        for proc in _LAUNCHER_PROCS:
            try:
                if subprocess.run(["pkill", "-9", "-f", proc],
                                  capture_output=True).returncode == 0:
                    killed = True
            except Exception:
                pass
    return killed


def _norm_path(p) -> str:
    return str(p).replace("\\", "/").rstrip("/").lower()


def _silent_patch_as_manual(install_folder: str) -> str:
    """Patch game_installs.json – mark install as isFromLauncher=false. Never raises."""
    if not _INSTALLS_FILE.is_file():
        return "game_installs.json not found – launcher may not be installed"
    try:
        shutil.copy2(str(_INSTALLS_FILE), str(_INSTALLS_FILE) + ".bak")
    except Exception as e:
        return f"Could not back up game_installs.json: {e}"
    try:
        data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Could not read game_installs.json: {e}"
    target  = _norm_path(install_folder)
    patched = 0
    for inst in data.get("installs", []):
        if _norm_path(inst.get("directoryPath", "")) == target:
            inst["isFromLauncher"]  = False
            inst["manifestVersion"] = None
            inst["manifestDate"]    = None
            patched += 1
    if patched == 0:
        return f"No matching install in game_installs.json for: {install_folder}"
    try:
        _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        return f"Could not save game_installs.json: {e}"
    return f"Launcher patch applied ({patched} install(s) set to Manual)"


def _unpatch_as_launcher(install_folder: str) -> str:
    """Reverse the patch – set isFromLauncher=true and restore manifestVersion. Never raises."""
    if not _INSTALLS_FILE.is_file():
        return "game_installs.json not found"
    try:
        shutil.copy2(str(_INSTALLS_FILE), str(_INSTALLS_FILE) + ".bak")
    except Exception as e:
        return f"Could not back up game_installs.json: {e}"
    try:
        data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Could not read game_installs.json: {e}"
    target  = _norm_path(install_folder)
    patched = 0
    for inst in data.get("installs", []):
        if _norm_path(inst.get("directoryPath", "")) == target:
            inst["isFromLauncher"] = True
            ver = inst.get("version")
            if ver and not inst.get("manifestVersion"):
                channel = inst.get("releaseChannel", "stable")
                suffix  = f"-{channel}" if channel != "stable" else ""
                inst["manifestVersion"] = f"{ver}{suffix}-win64.json"
            patched += 1
    if patched == 0:
        return f"No matching install in game_installs.json for: {install_folder}"
    try:
        _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        return f"Could not save game_installs.json: {e}"
    return f"Unpatch applied ({patched} install(s) set back to Launcher)"


def _read_installs() -> list:
    """Return the list of installs from game_installs.json, or []."""
    try:
        if _INSTALLS_FILE.is_file():
            return json.loads(_INSTALLS_FILE.read_text(encoding="utf-8")).get("installs", [])
    except Exception:
        pass
    return []

# ──────────────────────────────────────────────────────────────────────────────
#  DISCORD RICH PRESENCE
# ──────────────────────────────────────────────────────────────────────────────

# Discord Client ID — baked in as the default.  Users can override via the
# ⬤ Discord dot in the titlebar; their value is saved to chsuite_config.json.
DISCORD_CLIENT_ID_DEFAULT = "1484437105164943421"

# Map internal page IDs → display names shown in Discord
_PAGE_DISPLAY_NAMES = {
    "about":       "About This Tool",
    "bgchanger":   "CHMenuChanger",
    "namegen":     "CHNameGen",
    "notegen":     "CHNoteGen",
    "cleaner":     "CHCleaner",
    "patcher":     "CHPatcher",
    "songmanager": "CHSongManager",
    "gamemanager": "CHManager",
}

# The large_image key must match an Art Asset uploaded in the Discord
# Developer Portal (Rich Presence → Art Assets).
# This is detected automatically at runtime from any .ico file sitting
# next to the exe / script — so just name your art asset the same as
# your icon file (lowercase, no extension).  Falls back to "jurmrweed".
def _detect_discord_icon_key() -> str:
    """
    Look for a .ico file in the same directory as the exe / script and
    return its stem lowercased as the Discord art-asset key.
    e.g.  JURMRWEED.ico  →  "jurmrweed"
    Falls back to "jurmrweed" if nothing is found.
    """
    try:
        ico_files = list(_app_dir().glob("*.ico"))
        if ico_files:
            return ico_files[0].stem.lower()
    except Exception:
        pass
    return "jurmrweed"

_DISCORD_LARGE_IMAGE = _detect_discord_icon_key()
_DISCORD_LARGE_TEXT  = "CHSuite by JURMR"

# Platform display in Discord Rich Presence
_PLATFORM_STR        = "macOS" if _IS_MAC else ("Linux" if _IS_LINUX else "Windows")
_DISCORD_SMALL_IMAGE = "apple512x512" if _IS_MAC else ("linux512x512" if _IS_LINUX else "windows512x512")
_DISCORD_SMALL_TEXT  = f"Running on {_PLATFORM_STR}"


class _DiscordRPC:
    """
    Thin wrapper around pypresence.Presence.
    Silently does nothing if pypresence is not installed or Discord is closed.
    """

    def __init__(self, client_id: str):
        self._rpc     = None
        self._running = False
        if not _PYPRESENCE_OK:
            return
        if not client_id:
            return
        # ── Connect ───────────────────────────────────────────────────────────
        try:
            self._rpc = _DiscordPresence(client_id)
            self._rpc.connect()
            self._running = True
            _log("[Discord RPC] Connected")
        except Exception as e:
            _log(f"[Discord RPC] Could not connect: {e}")

    def update(self, state: str, details: str = ""):
        """Update the Discord activity.  details = tool name (top), state = context (bottom)."""
        if not self._running:
            return
        try:
            kwargs = dict(
                details=state,          # top line  — tool name e.g. "CHMenuChanger"
                large_image=_DISCORD_LARGE_IMAGE,
                large_text=_DISCORD_LARGE_TEXT,
                small_image=_DISCORD_SMALL_IMAGE,
                small_text=_DISCORD_SMALL_TEXT,
                buttons=[
                    {"label": "Download",          "url": "https://github.com/iamjrmh/CHSuite"},
                    {"label": "Murrin' it Central", "url": "https://discord.gg/KJYPjnzd7C"},
                ],
            )
            if details:
                kwargs["state"] = details   # bottom line — e.g. "Editing: Black"
            self._rpc.update(**kwargs)
        except Exception as e:
            _log(f"[Discord RPC] update failed: {e}")

    def close(self):
        if not (self._rpc and self._running):
            return
        self._running = False
        rpc = self._rpc
        self._rpc = None

        def _do_close():
            try:
                rpc.clear()
                rpc.close()
                _log("[Discord RPC] Disconnected")
            except Exception as e:
                _log(f"[Discord RPC] Close error: {e}")

        t = threading.Thread(target=_do_close, daemon=True)
        t.start()
        t.join(timeout=3)   # wait up to 3 s — never block the UI forever


def _log(msg: str):
    line = "[{}] {}".format(datetime.datetime.now().strftime("%H:%M:%S"), msg)
    print(line)
    try:
        with open(SCAN_LOG_FILE, "a", encoding="utf-8") as _lf:
            _lf.write(line + "\n")
    except Exception:
        pass

_CRASH_LOG_DIR = _app_dir() / "Logs"

def _write_crash_log(exc_info=None, simulated=False):
    """Write a crash report including system specs to Logs/[Date].log."""
    try:
        _CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
        fname = datetime.datetime.now().strftime("%Y-%m-%d") + ".log"
        fpath = _CRASH_LOG_DIR / fname
        with open(fpath, "a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(f"CHSuite Crash Report\n")
            f.write(f"Timestamp : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if simulated:
                f.write(f"Type      : SIMULATED (F12)\n")
            else:
                f.write(f"Type      : UNHANDLED EXCEPTION\n")
            f.write(f"\n--- System Info ---\n")
            f.write(f"OS        : {platform.platform()}\n")
            f.write(f"OS Name   : {platform.system()} {platform.release()}\n")
            f.write(f"Machine   : {platform.machine()}\n")
            f.write(f"Processor : {platform.processor()}\n")
            f.write(f"Python    : {sys.version}\n")
            try:
                import psutil
                mem = psutil.virtual_memory()
                f.write(f"RAM Total : {mem.total // (1024**2)} MB\n")
                f.write(f"RAM Avail : {mem.available // (1024**2)} MB\n")
                f.write(f"CPU Count : {psutil.cpu_count(logical=True)}\n")
            except Exception:
                f.write(f"CPU Count : {os.cpu_count()}\n")
            f.write(f"\n--- CHSuite ---\n")
            f.write(f"Frozen    : {getattr(sys, 'frozen', False)}\n")
            f.write(f"App Dir   : {_app_dir()}\n")
            if exc_info and exc_info[0] is not None:
                import traceback
                f.write(f"\n--- Traceback ---\n")
                traceback.print_exception(*exc_info, file=f)
            f.write("=" * 60 + "\n\n")
        return fpath
    except Exception as _ce:
        print(f"[crash log] Could not write crash log: {_ce}")
        return None


def _load_json(path: Path, default):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[save_json] {path}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
#  REUSABLE WIDGET HELPERS
# ──────────────────────────────────────────────────────────────────────────────

class StyledDropdown(tk.Canvas):
    """
    Canvas-based dropdown that matches the CHSuite rounded dark aesthetic.
    Drop-in replacement for ttk.Combobox — supports:
      • textvariable / get() / set()
      • widget["values"] = [...]
      • bind("<<ComboboxSelected>>", handler)
      • state="readonly" / config(state=...)
      • width= (in characters, like Combobox)
    """

    _POPUP_REF: "StyledDropdown | None" = None   # currently-open popup owner

    def __init__(self, parent, textvariable=None, values=None,
                 state="readonly", width=20, font=None,
                 canvas_bg=None, height=34, radius=10, **kw):
        self._font      = font or ("Lato", 9)
        self._char_w    = 8          # approximate px per char for sizing
        self._radius    = radius
        self._height    = height
        self._canvas_bg = canvas_bg or C["bg"]
        self._enabled   = (state != "disabled")
        self._hovered   = False
        self._values    = list(values or [])
        self._var       = textvariable if textvariable is not None else tk.StringVar()
        self._popup_win = None
        self._closing   = False   # debounce flag: True briefly after popup closes

        # Calculate pixel width from char width if not given as pixels
        px_width = max(width * self._char_w + 36, 80)

        super().__init__(parent, highlightthickness=0,
                         bg=self._canvas_bg,
                         width=px_width, height=height,
                         cursor="hand2", **kw)

        self.bind("<Button-1>",  self._on_click)
        self.bind("<Enter>",     self._on_enter)
        self.bind("<Leave>",     self._on_leave)
        self.bind("<Configure>", lambda e: self._draw())
        # Close popup when window loses focus
        self.winfo_toplevel().bind("<FocusOut>", self._on_root_focus_out, "+")
        self._draw()

    # ── drawing ───────────────────────────────────────────────────────────────
    def _draw(self, hover=False):
        self.delete("all")
        w = max(self.winfo_width(),  1)
        h = max(self.winfo_height(), 1)
        r = self._radius

        if not self._enabled:
            bg_fill  = C["panel"]
            fg_col   = C["text_dim"]
            border   = C["border"]
        elif hover or self._hovered:
            bg_fill  = C["hover"]
            fg_col   = C["text"]
            border   = C["accent"]
        else:
            bg_fill  = C["card2"]
            fg_col   = C["text"]
            border   = C["border"]

        # Rounded rect — draw border layer first, then fill on top (no outline on
        # either polygon; smooth=True + outline causes white artefacts on Windows)
        b = 1  # border thickness in px
        bpts = [r,0, w-r,0, w,0, w,r, w,h-r, w,h, w-r,h, r,h, 0,h, 0,h-r, 0,r, 0,0]
        self.create_polygon(bpts, smooth=True, fill=border, outline="")
        ipts = [r+b,b, w-r-b,b, w-b,b, w-b,r+b, w-b,h-r-b, w-b,h-b,
                w-r-b,h-b, r+b,h-b, b,h-b, b,h-r-b, b,r+b, b,b]
        self.create_polygon(ipts, smooth=True, fill=bg_fill, outline="")

        # Current value text — truncate if too wide
        val  = self._var.get()
        max_chars = max(int((w - 36) / self._char_w), 4)
        disp = val if len(val) <= max_chars else val[:max_chars - 1] + "…"
        self.create_text(10, h // 2, text=disp, anchor="w",
                         fill=fg_col, font=self._font)

        # Chevron ▾
        cx = w - 14
        cy = h // 2
        self.create_polygon(
            [cx - 5, cy - 3, cx + 5, cy - 3, cx, cy + 3],
            fill=C["text_dim"] if self._enabled else C["border"],
            outline="")

    # ── events ────────────────────────────────────────────────────────────────
    def _on_enter(self, _):
        self._hovered = True
        self._draw(hover=True)

    def _on_leave(self, _):
        self._hovered = False
        self._draw(hover=False)

    def _on_click(self, _):
        if not self._enabled:
            return
        # Debounce: if popup just closed (via FocusOut), don't immediately reopen
        if self._closing:
            return
        # If another dropdown is open, close it first
        if StyledDropdown._POPUP_REF and StyledDropdown._POPUP_REF is not self:
            StyledDropdown._POPUP_REF._close_popup()
        if self._popup_win and self._popup_win.winfo_exists():
            self._close_popup()
            return
        self._open_popup()

    def _on_root_focus_out(self, event):
        # Close if focus moved completely outside the app
        try:
            focused = self.focus_get()
        except Exception:
            focused = None
        if focused is None:
            self._close_popup()

    # ── popup ─────────────────────────────────────────────────────────────────
    def _open_popup(self):
        if not self._values:
            return

        self.update_idletasks()
        root_x = self.winfo_rootx()
        root_y = self.winfo_rooty() + self.winfo_height() + 2
        w      = max(self.winfo_width(), 120)

        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.configure(bg=C["border"])
        win.attributes("-topmost", True)

        # Outer frame — acts as border
        outer = tk.Frame(win, bg=C["border"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        # Measure actual row height from font metrics to avoid OS padding issues
        import tkinter.font as tkfont
        try:
            fnt  = tkfont.Font(family=self._font[0], size=self._font[1])
            row_h = fnt.metrics("linespace") + 2
        except Exception:
            row_h = 22
        max_rows  = 10
        n_rows    = min(len(self._values), max_rows)
        lb_height = n_rows * row_h

        lb = tk.Listbox(
            outer,
            font=self._font,
            bg=C["card2"],
            fg=C["text"],
            selectbackground=C["accent"],
            selectforeground="white",
            activestyle="none",
            relief="flat",
            bd=0,
            highlightthickness=0,
            height=n_rows,
        )

        # Scrollbar only when needed
        if len(self._values) > max_rows:
            sb = tk.Scrollbar(outer, orient="vertical", command=lb.yview,
                              bg=C["border"], troughcolor=C["panel"],
                              width=10, relief="flat", bd=0)
            lb.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")

        lb.pack(fill="both", expand=True)

        for v in self._values:
            lb.insert(tk.END, "  " + v)

        # Highlight current selection
        cur = self._var.get()
        if cur in self._values:
            idx = self._values.index(cur)
            lb.selection_set(idx)
            lb.see(idx)

        # Hover highlight (row bg, not selection)
        def _on_motion(e):
            lb.selection_clear(0, tk.END)
            idx = lb.nearest(e.y)
            lb.selection_set(idx)

        lb.bind("<Motion>",   _on_motion)
        lb.bind("<Button-1>", lambda e: self.after(10, lambda: self._pick(lb)))
        lb.bind("<Return>",   lambda e: self._pick(lb))
        lb.bind("<Escape>",   lambda e: self._close_popup())
        win.bind("<Escape>",  lambda e: self._close_popup())

        # Close when clicking anywhere outside the popup
        def _on_root_click(e):
            try:
                wx, wy = win.winfo_rootx(), win.winfo_rooty()
                ww, wh = win.winfo_width(), win.winfo_height()
                if not (wx <= e.x_root <= wx + ww and wy <= e.y_root <= wy + wh):
                    self._close_popup()
            except Exception:
                self._close_popup()
        _root_click_id = self.winfo_toplevel().bind("<Button-1>", _on_root_click, "+")
        self._root_click_id = _root_click_id

        # Position: try below, flip above if off-screen
        sh = self.winfo_screenheight()
        popup_h = lb_height + 2   # +border
        if root_y + popup_h > sh - 10:
            root_y = self.winfo_rooty() - popup_h - 2

        win.geometry(f"{w}x{popup_h}+{root_x}+{root_y}")
        win.lift()
        lb.focus_set()

        self._popup_win = win
        self._popup_lb  = lb
        StyledDropdown._POPUP_REF = self

    def _pick(self, lb):
        sel = lb.curselection()
        if not sel:
            return
        val = self._values[sel[0]]
        self._var.set(val)
        self._draw()
        self._close_popup()
        # Fire virtual event so existing <<ComboboxSelected>> bindings work
        self.event_generate("<<ComboboxSelected>>")

    def _close_popup(self):
        if self._popup_win:
            try:
                self._popup_win.destroy()
            except Exception:
                pass
            self._popup_win = None
            self._popup_lb  = None
        # Unbind root click handler
        if hasattr(self, "_root_click_id") and self._root_click_id:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._root_click_id)
            except Exception:
                pass
            self._root_click_id = None
        if StyledDropdown._POPUP_REF is self:
            StyledDropdown._POPUP_REF = None
        # Debounce: prevent immediately reopening when same click closes us
        self._closing = True
        self.after(200, self._reset_closing)
        self._draw()

    def _reset_closing(self):
        self._closing = False

    # ── public API (Combobox-compatible) ──────────────────────────────────────
    def get(self):
        return self._var.get()

    def set(self, value):
        self._var.set(value)
        self._draw()

    def __getitem__(self, key):
        if key == "values":
            return self._values
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "values":
            self._values = list(value)
            self._draw()
        else:
            raise KeyError(key)

    def config(self, **kw):
        state = kw.pop("state", None)
        if state is not None:
            self._enabled = (state not in ("disabled", tk.DISABLED))
            tk.Canvas.config(self, cursor="hand2" if self._enabled else "arrow")
            self._draw()
        if kw:
            tk.Canvas.config(self, **kw)

    configure = config


class RoundedButton(tk.Canvas):
    """Canvas-based rounded button with hover and disabled states."""
    def __init__(self, parent, text, command, bg_color, hover_color,
                 height=42, radius=18, text_font=None,
                 text_color=None, canvas_bg=None, **kwargs):
        # Pass height directly into Canvas.__init__ so the geometry manager
        # honours it from creation on all platforms (including macOS, where
        # setting height via .config() *after* packing can be ignored).
        super().__init__(parent, highlightthickness=0, height=height, **kwargs)
        self.command     = command
        self.bg_color    = bg_color
        self.hover_color = hover_color
        self.text        = text
        self.enabled     = True
        self.radius      = radius
        self.text_color  = text_color or C["text"]
        self.text_font   = text_font or ("Lato", 10, "bold")
        # canvas_bg should match the parent frame background so rounded
        # corners look seamless instead of leaving a rectangular artifact.
        tk.Canvas.config(self, bg=canvas_bg or C["bg"], cursor="hand2")
        self.bind("<Button-1>",  self._on_click)
        self.bind("<Enter>",     self._on_enter)
        self.bind("<Leave>",     self._on_leave)
        self.bind("<Configure>", lambda e: self.draw())
        self.draw()

    def draw(self, hover=False):
        self.delete("all")
        color = self.hover_color if (hover and self.enabled) else self.bg_color
        if not self.enabled:
            color = "#1e2030"
        w = self.winfo_width()  if self.winfo_width()  > 1 else 200
        h = self.winfo_height() if self.winfo_height() > 1 else 38
        self._rounded_rect(4, 4, w - 4, h - 4, self.radius, fill=color, outline="")
        fg = C["text_dim"] if not self.enabled else self.text_color
        self.create_text(w // 2, h // 2, text=self.text, fill=fg, font=self.text_font)

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
               x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _on_enter(self, _): self.draw(hover=True)
    def _on_leave(self, _): self.draw(hover=False)
    def _on_click(self, _):
        if self.enabled and self.command:
            self.command()

    def set_state(self, enabled):
        self.enabled = enabled
        tk.Canvas.config(self, cursor="hand2" if enabled else "arrow")
        self.draw()

    def config(self, **kw):
        """Compatibility shim so existing .config() calls keep working."""
        state = kw.pop("state", None)
        if state is not None:
            self.set_state(state not in ("disabled", tk.DISABLED))
        new_cmd = kw.pop("command", None)
        if new_cmd is not None:
            self.command = new_cmd
        new_text = kw.pop("text", None)
        if new_text is not None:
            self.text = new_text
        new_bg = kw.pop("bg", kw.pop("background", None))
        if new_bg is not None:
            self.bg_color = new_bg
        new_fg = kw.pop("fg", kw.pop("foreground", None))
        if new_fg is not None:
            self.text_color = new_fg
        cursor = kw.pop("cursor", None)
        if cursor is not None:
            tk.Canvas.config(self, cursor=cursor)
        if new_text is not None or new_bg is not None or new_fg is not None:
            self.draw()
        if kw:
            tk.Canvas.config(self, **kw)

    configure = config


class _RoundedNavBtn(tk.Canvas):
    """Canvas-based rounded navigation button with icon + label text.
    Fully manages its own hover and active visual state internally."""
    _H = 46
    _R = 12

    def __init__(self, parent, icon, label, command, canvas_bg, **kw):
        super().__init__(parent, highlightthickness=0, bg=canvas_bg,
                         height=self._H, cursor="hand2", **kw)
        self._icon    = icon
        self._label   = label
        self._command = command
        self._cbg     = canvas_bg
        self._active  = False
        self._hovered = False
        self.bind("<Button-1>",  self._click)
        self.bind("<Enter>",     self._enter)
        self.bind("<Leave>",     self._leave)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = self._H
        r = self._R

        if self._active:
            fill  = C["nav_active"]
            icol  = "white"
            tcol  = "white"
            bold  = True
        elif self._hovered:
            fill  = C["nav_hover"]
            icol  = C["text"]
            tcol  = C["text"]
            bold  = False
        else:
            fill  = C["nav_btn"]
            icol  = C["text_dim"]
            tcol  = C["text_mid"]
            bold  = False

        pts = [r,0, w-r,0, w,0, w,r, w,h-r, w,h,
               w-r,h, r,h, 0,h, 0,h-r, 0,r, 0,0]
        self.create_polygon(pts, smooth=True, fill=fill, outline="")

        wt = "bold" if bold else "normal"
        self.create_text(30, h // 2, text=self._icon,
                         fill=icol, font=("Lato", 12, wt), anchor="center")
        self.create_text(50, h // 2, text=self._label,
                         fill=tcol, font=("Lato", 10, wt), anchor="w")

    def _click(self, _):
        if self._command:
            self._command()

    def _enter(self, _):
        if not self._active:
            self._hovered = True
            self._draw()

    def _leave(self, _):
        self._hovered = False
        if not self._active:
            self._draw()

    def set_active(self, active: bool):
        self._active  = active
        self._hovered = False
        self._draw()


class _RoundedAboutCard(tk.Frame):
    """A variable-height card with smooth rounded corners, used on the About page."""
    _R = 16

    def __init__(self, parent, padx=20, pady=16, **kw):
        outer_bg = kw.pop("outer_bg", C["bg"])
        bg       = kw.pop("bg", C["card"])
        super().__init__(parent, bg=outer_bg, **kw)

        self._bg = bg
        r = self._R

        self._cv = tk.Canvas(self, bg=outer_bg, highlightthickness=0, height=60)
        self._cv.pack(fill="x")

        # inner frame holds actual content — pack children into self.inner
        self.inner = tk.Frame(self._cv, bg=bg, padx=padx, pady=pady)
        self._win  = self._cv.create_window(r, r, anchor="nw", window=self.inner)

        self.inner.bind("<Configure>", self._sync)
        self._cv.bind("<Configure>",   self._sync)

    def _sync(self, e=None):
        self.update_idletasks()
        cv_w = self._cv.winfo_width()
        in_h = self.inner.winfo_reqheight()
        if cv_w < 2:
            return
        r = self._R
        h = in_h + 2 * r
        self._cv.configure(height=h)
        self._cv.delete("_bg")
        pts = [r,0, cv_w-r,0, cv_w,0, cv_w,r, cv_w,h-r, cv_w,h,
               cv_w-r,h, r,h, 0,h, 0,h-r, 0,r, 0,0]
        self._cv.create_polygon(pts, smooth=True, fill=self._bg,
                                outline="", tags="_bg")
        self._cv.tag_lower("_bg")
        self._cv.itemconfig(self._win, width=max(1, cv_w - 2 * r))


def _card(parent, padx=14, pady=10, **kw):
    """A dark card frame with a border outline."""
    return tk.Frame(parent, bg=C["card"],
                    highlightbackground=C["border"], highlightthickness=1,
                    padx=padx, pady=pady, **kw)

def _label(parent, text, font=None, fg=None, **kw):
    return tk.Label(parent, text=text, font=font or FT,
                    fg=fg or C["text"], bg=kw.pop("bg", C["card"]), **kw)

def _sep(parent, bg=None):
    return tk.Frame(parent, bg=bg or C["border"], height=1)


class HoverTooltip:
    """
    Attach a rich tooltip popup to any widget.
    The popup appears after a short delay when the mouse enters the widget
    and disappears when it leaves.

    Usage:
        HoverTooltip(widget, "Some message text")
    """
    _PAD   = 14
    _DELAY = 400   # ms before showing

    def __init__(self, widget: tk.Widget, text: str,
                 title: str = "", width: int = 400):
        self._widget = widget
        self._text   = text
        self._title  = title
        self._width  = width
        self._win    = None
        self._job    = None
        widget.bind("<Enter>",    self._on_enter,  add="+")
        widget.bind("<Leave>",    self._on_leave,  add="+")
        widget.bind("<Button-1>", self._on_leave,  add="+")
        widget.bind("<Destroy>",  self._on_destroy, add="+")

    def _on_enter(self, _=None):
        self._cancel()
        self._job = self._widget.after(self._PAD * 0 + self._DELAY, self._show)

    def _on_leave(self, _=None):
        self._cancel()
        self._hide()

    def _on_destroy(self, _=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._job:
            try: self._widget.after_cancel(self._job)
            except Exception: pass
            self._job = None

    def _show(self):
        if self._win:
            return
        # Position: just below-right of the widget
        try:
            x = self._widget.winfo_rootx() + 24
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        except Exception:
            return

        self._win = tk.Toplevel(self._widget)
        self._win.wm_overrideredirect(True)
        self._win.configure(bg=C["border"])
        self._win.attributes("-topmost", True)

        inner = tk.Frame(self._win, bg=C["card"],
                         padx=self._PAD, pady=self._PAD)
        inner.pack(padx=1, pady=1)          # 1 px border from bg=C["border"]

        if self._title:
            tk.Label(inner, text=self._title,
                     font=("Lato", 10, "bold"),
                     fg=C["warn"], bg=C["card"],
                     justify="left").pack(anchor="w", pady=(0, 6))

        tk.Label(inner, text=self._text,
                 font=("Lato", 9),
                 fg=C["text_mid"], bg=C["card"],
                 justify="left", wraplength=self._width).pack(anchor="w")

        self._win.update_idletasks()
        # Clamp to screen right edge
        sw = self._win.winfo_screenwidth()
        tw = self._win.winfo_reqwidth()
        if x + tw > sw - 10:
            x = sw - tw - 10
        self._win.geometry(f"+{x}+{y}")
        # Close if mouse wanders back into the popup itself
        self._win.bind("<Leave>", self._on_leave)

    def _hide(self):
        if self._win:
            try: self._win.destroy()
            except Exception: pass
            self._win = None






# ── ThemeGen IPC helpers ───────────────────────────────────────────────────────
def _ipc_pack(data: dict) -> bytes:
    import struct
    payload = json.dumps(data).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload

def _ipc_recv_msg(conn, timeout: float = 5.0) -> dict | None:
    import struct
    conn.settimeout(timeout)
    try:
        raw = b""
        while len(raw) < 4:
            chunk = conn.recv(4 - len(raw))
            if not chunk:
                return None
            raw += chunk
        length = struct.unpack(">I", raw)[0]
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def _flatten_single_subdir(dest_dir: "Path"):
    """If dest_dir contains exactly one subfolder (any name), move its contents
    up into dest_dir and remove the now-empty subfolder.  Used as a second pass
    after _flatten_platform_subdir to handle archives like:
      dest/{tag}/Windows/CloneHero-Win-x64/<files>
    which need two levels of flattening on Windows.
    """
    try:
        subdirs = [p for p in dest_dir.iterdir() if p.is_dir()]
        if len(subdirs) == 1:
            sub = subdirs[0]
            _log(f"[gm] Flattening inner subfolder '{sub.name}' into {dest_dir}")
            for item in list(sub.iterdir()):
                shutil.move(str(item), str(dest_dir / item.name))
            try:
                sub.rmdir()
            except Exception:
                shutil.rmtree(str(sub), ignore_errors=True)
            _log(f"[gm] Removed inner subfolder '{sub.name}'")
    except Exception as e:
        _log(f"[gm] _flatten_single_subdir error: {e}")


def _flatten_platform_subdir(dest_dir: "Path", platform_name: str):
    """After extraction, if dest_dir contains exactly one subfolder whose name
    matches platform_name (case-insensitive), move its contents up to dest_dir
    and remove the now-empty subfolder.  This flattens archives like:
      dest/{tag}/Linux/clonehero  →  dest/{tag}/clonehero   (Linux)
      dest/{tag}/Windows/CloneHero-Win-x64/<files>  →  dest/{tag}/<files>  (Windows)
    On Windows the zip nests two levels deep (Windows/CloneHero-Win-x64/), so a
    second pass via _flatten_single_subdir is performed automatically.
    """
    try:
        subdirs = [p for p in dest_dir.iterdir() if p.is_dir()]
        if len(subdirs) == 1 and subdirs[0].name.lower() == platform_name:
            sub = subdirs[0]
            _log(f"[gm] Flattening subfolder '{sub.name}' into {dest_dir}")
            for item in list(sub.iterdir()):
                shutil.move(str(item), str(dest_dir / item.name))
            try:
                sub.rmdir()
            except Exception:
                shutil.rmtree(str(sub), ignore_errors=True)
            _log(f"[gm] Removed subfolder '{sub.name}'")
            # Second pass: flatten the inner subfolder (e.g. CloneHero-Win-x64)
            # that Windows zips place inside the platform folder.
            if platform_name == "windows":
                _flatten_single_subdir(dest_dir)
    except Exception as e:
        _log(f"[gm] _flatten_platform_subdir error: {e}")



# ─────────────────────────────────────────────────────────────────────────────
#  Import per-tool mixins
# ─────────────────────────────────────────────────────────────────────────────
# The shared module-level names above (C, FT, _log, helpers, widget classes,
# etc.) are intentionally defined BEFORE these imports.  Each split file does
# `from CHSuite import …` at module load time — those imports succeed because
# CHSuite is partially loaded with all the names they need already in place.

from CHMenuChanger import (
    CHMenuChangerMixin,
    AssetManager, SetupDialog,
    DEFAULT_PROFILE_NAME, DEFAULT_DATA, BACKGROUNDS, EXACT_ASSET_FILE,
    _get_default_data, required_size, exact_match_required, _norm,
    _scroll_units,
    _blank_profile, _load_profiles, _save_profiles,
)
from CHNameGen import (
    CHNameGenMixin,
    __namegen_version__, GITHUB_REPO_OWNER, GITHUB_REPO_NAME,
    GITHUB_RELEASE_API, UPDATE_ZIP_FILENAME,
    _ng_hex_to_rgb_f, _ng_rgb_f_to_hex, _interpolate_colors,
    _generate_gradient_name, _generate_individual_name,
)
from CHNoteGen import (
    CHNoteGenMixin,
    _NG_PROFILES_FILE, _NG_CONFIG_FILE, _NG_DEFAULT_INI, _NG_IMAGES_DIR,
    _NG_DEFAULT_PROFILE_NAME, _NOTE_FILE_MAP, _TEMPLATE_NAMES, _SECTION_ORDER,
    _NG_DEFAULT_COLORS, _NG_FRIENDLY, _NG_GROUPS,
    _NG_GUITAR_LANES, _NG_DRUM_LANES, _NG_SF_LANES,
    _ng_friendly, _ng_valid_hex, _ng_hex_to_rgb, _ng_rgb_to_hex,
    _ng_darken, _ng_lighten, _ng_lerp_hex, _ng_alpha_blend,
    _ng_load_profiles, _ng_save_profiles, _ng_fresh_colors,
    _ng_parse_ini, _ng_generate_ini,
    _ng_find_template, _ng_find_mask,
    _ng_rgb_to_hsl, _ng_hsl_to_rgb,
    _ng_composite_note_pil, _ng_colorize_pil, _ng_generate_note_images,
    _ColorPickerDialog, _NgAutoGradientDialog,
    _NgNoteCard, _NgScrollFrame, _NgGroupHeader, _NgColorRow,
    _NgSectionEditor, _NgHighwayPreview,
)
from CHCleaner import (
    CHCleanerMixin,
    _deep_clean_path, _parse_bad_songs,
)
from CHPatcher import CHPatcherMixin
from CHSongManager import (
    CHSongManagerMixin,
    CHSongManagerTab,
    _ps_now_filetime, _ps_make_record_hash, _ps_lp_str, _ps_parse_ini,
    _ps_build_difficulty_block, _ps_find_chart, _ps_scan_songs, _ps_build_cache,
)
from CHManager import CHManagerMixin


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION CLASS
# ─────────────────────────────────────────────────────────────────────────────

class CHSuite(
    CHMenuChangerMixin,
    CHNameGenMixin,
    CHNoteGenMixin,
    CHCleanerMixin,
    CHPatcherMixin,
    CHSongManagerMixin,
    CHManagerMixin,
    tk.Tk,
):
    def __init__(self):
        super().__init__()
        self.title("CHSuite  by JURMR")
        self.configure(bg=C["bg"])
        self.minsize(1200, 780)
        self.geometry("1350x860")

        # ── Windows 10 drag-performance tweaks ────────────────────────────────
        if _IS_WINDOWS:
            try:
                import ctypes
                # Full opacity — any alpha value < 1 forces DWM to composite
                # every frame through a separate layered-window pass.
                self.attributes("-alpha", 1.0)
                # Tell Tk to flush GDI commands immediately rather than batching;
                # reduces the visual lag between pointer movement and window redraw.
                self.tk.call("tk", "useinputmethods", "0")
            except Exception:
                pass

        # Set embedded window icon
        try:
            import base64 as _b64, io as _io
            _raw = _b64.b64decode(_ICON_B64)
            _icon_img = ImageTk.PhotoImage(Image.open(_io.BytesIO(_raw)))
            self.iconphoto(True, _icon_img)
            self._icon_img = _icon_img
        except Exception:
            pass

        self._cfg      = _load_json(CONFIG_FILE, {})
        self._profiles = _load_profiles()

        # ── Apply saved theme before any widgets are created ──────────────────
        _saved_theme = self._cfg.get("theme", "Default")
        _load_theme(_saved_theme)   # silently falls back to built-in C if missing

        # ── BG changer state ──────────────────────────────────────────────────
        self._am          = None
        self._asset_cache = {}
        self._orig_pil    = {}
        self._new_pil     = {}
        self._orig_tk     = {}
        self._new_tk      = {}
        self._active_name = ""
        self._active_prof = {}
        self._status_v    = tk.StringVar(value="Ready.")

        # ── Name gen state ────────────────────────────────────────────────────
        self._letter_frames   = []
        self._letter_controls = []

        # ── Bad songs state ───────────────────────────────────────────────────
        self._badsongs_path = None
        self._bad_paths     = []
        self._song_vars     = {}
        self._log_entries   = []

        # ── NoteGen state ─────────────────────────────────────────────────────
        self._ng_profiles: dict = _ng_load_profiles()
        self._ng_active_name: str = _NG_DEFAULT_PROFILE_NAME
        self._ng_active_colors_data: dict = _ng_fresh_colors()
        self._ng_editors: dict = {}

        self.withdraw()
        self.update_idletasks()
        self._apply_styles()
        self._build_ui()
        self._load_initial_profile()
        self.deiconify()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<F12>", lambda e: self._simulate_crash())

        # ── ThemeGen IPC server ───────────────────────────────────────────
        self._start_themegen_ipc()

        # ── Discord Rich Presence ─────────────────────────────────────────────
        _client_id = self._cfg.get("discord_client_id", DISCORD_CLIENT_ID_DEFAULT)
        self._drpc  = _DiscordRPC(_client_id)
        self._update_discord_rpc()
        self._update_discord_dot()

        # ── What's New — show once per version ───────────────────────────────
        if self._cfg.get("last_seen_version") != "7.1":
            self._cfg["last_seen_version"] = "7.1"
            _save_json(CONFIG_FILE, self._cfg)
            self.after(300, self._show_whats_new)

    # ── ThemeGen live-preview IPC ─────────────────────────────────────────────
    def _start_themegen_ipc(self):
        """Start a background socket server for ThemeGen live-preview on IPC_PORT."""
        def _handle(conn):
            try:
                # Greet ThemeGen with current colours + themes directory
                hello = {
                    "type": "hello",
                    "colors": {k: C[k] for k in _THEME_KEYS},
                    "themes_dir": str(THEMES_DIR),
                }
                conn.sendall(_ipc_pack(hello))
                # Wait for apply messages
                while True:
                    msg = _ipc_recv_msg(conn, timeout=None)
                    if msg is None:
                        break
                    if msg.get("type") == "apply" and "colors" in msg:
                        self.after(0, lambda d=msg["colors"]: self._apply_live_theme(d))
            except Exception:
                pass

        def _serve():
            import socket as _sock
            with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as srv:
                srv.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                try:
                    srv.bind(("127.0.0.1", IPC_PORT))
                    srv.listen(4)
                    while True:
                        try:
                            conn, _ = srv.accept()
                            threading.Thread(target=_handle, args=(conn,),
                                             daemon=True).start()
                        except Exception:
                            break
                except Exception:
                    pass

        threading.Thread(target=_serve, daemon=True).start()

    def _apply_live_theme(self, incoming: dict):
        """Receive a colour dict from ThemeGen and repaint all live widgets."""
        # Snapshot old colours before we change anything
        old_c = {k: C[k] for k in _THEME_KEYS}

        # Apply only valid hex values
        for k in _THEME_KEYS:
            v = incoming.get(k, "")
            if isinstance(v, str) and v.startswith("#"):
                C[k] = v

        # Build a hex-remap table:  old_value.lower() -> new_value
        remap = {}
        for k in _THEME_KEYS:
            old = self._norm_color(old_c[k])
            new = C[k]
            if old != new.lower():
                remap[old] = new

        if remap:
            self._recolor_walk(self, remap)
            self.update_idletasks()

    @staticmethod
    def _norm_color(raw: str) -> str:
        """Normalize a color string returned by widget.cget() to 6-digit lowercase hex.

        On Linux/X11, tkinter expands stored colors to 12-digit form:
          #0c0e13  →  #0c0c0e0e1313
        Taking the first two hex digits of each 4-digit channel group recovers
        the original 6-digit value so remap lookups work on all platforms.
        """
        s = raw.lower()
        if len(s) == 13 and s.startswith("#"):
            # #rrrrggggbbbb  →  #rrggbb
            s = "#" + s[1:3] + s[5:7] + s[9:11]
        return s

    def _recolor_walk(self, widget, remap: dict):
        """Recursively remap every colour attribute on every widget."""
        ATTRS = (
            "bg", "fg", "background", "foreground",
            "activebackground", "activeforeground",
            "selectbackground", "highlightbackground", "highlightcolor",
        )
        try:
            info = widget.configure()
            for attr in ATTRS:
                if attr in info:
                    try:
                        cur = self._norm_color(widget.cget(attr))
                        if cur in remap:
                            widget.configure(**{attr: remap[cur]})
                    except Exception:
                        pass
        except Exception:
            pass
        for child in widget.winfo_children():
            self._recolor_walk(child, remap)

    # ── styles ────────────────────────────────────────────────────────────────
    def _apply_styles(self):
        # Global tk.Button defaults — gives every plain tk.Button a flat,
        # cursor-aware look even if the call site doesn't set these explicitly.
        self.option_add("*Button.relief",             "flat")
        self.option_add("*Button.cursor",             "hand2")
        self.option_add("*Button.borderWidth",        0)
        self.option_add("*Button.highlightThickness", 0)
        self.option_add("*Button.activeBackground",   C["hover"])
        self.option_add("*Button.activeForeground",   C["text"])

        # Global tk.Entry defaults — highlightthickness draws a clean rectangle
        # with no corner clipping artifacts unlike ttk.Entry's field element.
        self.option_add("*Entry.relief",              "flat")
        self.option_add("*Entry.bd",                  "0")
        self.option_add("*Entry.highlightThickness",  "1")
        self.option_add("*Entry.highlightBackground", C["border"])
        self.option_add("*Entry.highlightColor",      C["accent"])
        self.option_add("*Entry.background",          C["card2"])
        self.option_add("*Entry.foreground",          C["text"])
        self.option_add("*Entry.insertBackground",    C["text"])
        self.option_add("*Entry.selectBackground",    C["selected"])
        self.option_add("*Entry.selectForeground",    C["text"])

        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=C["panel"], fieldbackground=C["panel"],
                    foreground=C["text"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"],
                    relief="flat", borderwidth=1,
                    rowheight=32, font=FT)
        s.map("Treeview",
              background=[("selected", C["selected"])],
              foreground=[("selected", C["text"])],
              lightcolor=[("focus", C["border"]), ("!focus", C["border"])],
              darkcolor=[("focus", C["border"]), ("!focus", C["border"])])
        s.configure("Treeview.Heading",
                    background=C["border"], foreground=C["text_mid"], font=FTS,
                    lightcolor=C["border"], darkcolor=C["border"])
        s.configure("DE.TEntry",
                    fieldbackground=C["card2"], foreground=C["text"],
                    insertcolor=C["text"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"],
                    relief="flat", borderwidth=1)
        s.map("DE.TEntry",
              lightcolor=[("focus", C["accent"]), ("!focus", C["border"])],
              darkcolor=[("focus", C["accent"]), ("!focus", C["border"])],
              bordercolor=[("focus", C["accent"]), ("!focus", C["border"])])
        s.configure("Vertical.TScrollbar",
                    background=C["border"], troughcolor=C["panel"],
                    arrowcolor=C["text_dim"])
        # TCombobox styling removed — all dropdowns use StyledDropdown

    # ── top-level layout ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Title bar
        titlebar = tk.Frame(self, bg=C["panel"])
        titlebar.pack(fill="x")
        inner_tb = tk.Frame(titlebar, bg=C["panel"], padx=20, pady=12)
        inner_tb.pack(fill="x")
        tk.Label(inner_tb, text="⬡", font=("Lato", 24),
                 bg=C["panel"], fg=C["accent"]).pack(side="left", padx=(0, 10))
        tk.Label(inner_tb, text="CHSuite",
                 font=FTT, bg=C["panel"], fg=C["text"]).pack(side="left")
        tk.Label(inner_tb, text="  by JURMR  v7.1",
                 font=("Lato", 13), bg=C["panel"], fg=C["accent"]).pack(side="left", pady=(6,0))

        # Discord status dot
        self._discord_dot = tk.Label(inner_tb, text="⬤  Discord",
                                      font=("Lato", 9), bg=C["panel"],
                                      fg=C["text_dim"], cursor="hand2", padx=12)
        self._discord_dot.pack(side="right")
        self._discord_dot.bind("<Button-1>", lambda e: self._discord_setup_prompt())

        # Social icon buttons (Discord + GitHub) — right of Discord dot
        _TB_GITHUB_URL  = "https://github.com/iamjrmh/CHSuite"
        _TB_DISCORD_URL = "https://discord.gg/PtVqaCWFHa"

        def _tb_load_png(filename, size=18):
            try:
                from PIL import Image, ImageTk
                img = Image.open(_resources_dir() / "Images" / filename).resize(
                    (size, size), Image.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                return None

        _tb_discord_img = _tb_load_png("Discord256x256.png")
        _tb_github_img  = _tb_load_png("GitHub256x256.png")

        def _tb_make_icon(img, url, fallback_text):
            if img:
                lbl = tk.Label(inner_tb, image=img, bg=C["panel"],
                               cursor="hand2", padx=4)
                lbl.image = img
            else:
                lbl = tk.Label(inner_tb, text=fallback_text,
                               font=("Lato", 8), bg=C["panel"],
                               fg=C["accent"], cursor="hand2", padx=4)
            lbl.pack(side="right", padx=(0, 2))
            lbl.bind("<Button-1>", lambda e, u=url: __import__("webbrowser").open(u))
            lbl.bind("<Enter>", lambda e, w=lbl: w.config(bg=C["hover"]))
            lbl.bind("<Leave>", lambda e, w=lbl: w.config(bg=C["panel"]))
            return lbl

        _tb_make_icon(_tb_discord_img, _TB_DISCORD_URL, "Discord")
        _tb_make_icon(_tb_github_img,  _TB_GITHUB_URL,  "GitHub")

        # Launch Clone Hero button — always visible in titlebar
        self._launch_btn = RoundedButton(
            inner_tb, "▶  Launch Clone Hero", self._launch_clone_hero,
            bg_color=C["success"], hover_color="#1aaa50",
            text_color="#000000", height=44, radius=18,
            text_font=("Lato", 9, "bold"), canvas_bg=C["panel"], width=215)
        self._launch_btn.pack(side="right", padx=(0, 8))

        # Body: left nav + content pane
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # Left navigation sidebar — Canvas gives us rounded corners
        _NAV_R = 14
        _nav_margin = tk.Frame(body, bg=C["bg"])
        _nav_margin.pack(side="left", fill="y")

        self._nav_cv = tk.Canvas(_nav_margin, bg=C["bg"], highlightthickness=0, width=216)
        self._nav_cv.pack(fill="both", expand=True, padx=(8, 0), pady=8)

        self._nav = tk.Frame(self._nav_cv, bg=C["sidebar"])
        self._nav.pack_propagate(False)
        _nw_id = [self._nav_cv.create_window(_NAV_R, _NAV_R, anchor="nw", window=self._nav)]

        def _resize_nav(e):
            w, h = e.width, e.height
            if w < 4 or h < 4:
                return
            self._nav_cv.delete("_navbg")
            r = _NAV_R
            pts = [r,0, w-r,0, w,0, w,r, w,h-r, w,h,
                   w-r,h, r,h, 0,h, 0,h-r, 0,r, 0,0]
            self._nav_cv.create_polygon(pts, smooth=True, fill=C["sidebar"],
                                        outline="", tags="_navbg")
            self._nav_cv.tag_lower("_navbg")
            fw = max(1, w - 2*r)
            fh = max(1, h - 2*r)
            self._nav_cv.itemconfig(_nw_id[0], width=fw, height=fh)

        self._nav_cv.bind("<Configure>", _resize_nav)

        # Content area
        self._content = tk.Frame(body, bg=C["bg"])
        self._content.pack(side="left", fill="both", expand=True)

        self._pages = {}
        self._nav_btns = {}
        self._current_page = None

        self._build_nav()
        # Build the landing page and BGChanger eagerly (BGChanger auto-scans on start).
        # All other pages are built lazily on first visit to keep startup fast.
        self._build_page_about()
        self._build_page_bgchanger()

        self._show_page("about")

    # ── navigation sidebar ────────────────────────────────────────────────────
    def _build_nav(self):
        tk.Frame(self._nav, bg=C["sidebar"], height=20).pack()

        logo_frame = tk.Frame(self._nav, bg=C["sidebar"])
        logo_frame.pack(fill="x", padx=16, pady=(0, 20))
        tk.Label(logo_frame, text="TOOLS", font=("Lato", 7, "bold"),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(anchor="w")
        _sep(logo_frame, bg=C["border"]).pack(fill="x", pady=(6, 0))

        # Each nav item: (page_id, icon_char, label_text)
        # Icons are drawn in a fixed-width Label so text always starts at
        # the same x position regardless of glyph width.
        nav_items = [
            ("about",        "ⓘ", "About This Tool"),
            ("bgchanger",    "◈", "CHMenuChanger"),
            ("namegen",      "✦", "CHNameGen"),
            ("notegen",      "♪", "CHNoteGen"),
            ("cleaner",      "⊘", "CHCleaner"),
            ("patcher",      "⚙", "CHPatcher"),
            ("songmanager",  "♫", "CHSongManager"),
            ("gamemanager",  "▦", "CHManager"),
        ]
        for page_id, icon, label in nav_items:
            btn = _RoundedNavBtn(
                self._nav, icon, label,
                command=lambda p=page_id: self._show_page(p),
                canvas_bg=C["sidebar"],
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[page_id] = btn

        # ── Theme picker at the bottom of the sidebar ─────────────────────────
        theme_sep = tk.Frame(self._nav, bg=C["border"], height=1)
        theme_sep.pack(fill="x", padx=12, pady=(0, 8))

        theme_frame = tk.Frame(self._nav, bg=C["sidebar"], padx=12)
        theme_frame.pack(fill="x", pady=(0, 6))

        tk.Label(theme_frame, text="THEME", font=("Lato", 7, "bold"),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(anchor="w", pady=(0, 4))

        self._theme_var = tk.StringVar(value=self._cfg.get("theme", "Default"))
        self._theme_cb  = StyledDropdown(
            theme_frame,
            textvariable=self._theme_var,
            values=_list_themes(),
            state="readonly",
            font=("Lato", 8),
            width=18,
            canvas_bg=C["sidebar"],
            height=32,
        )
        self._theme_cb.pack(fill="x")
        self._theme_cb.bind("<<ComboboxSelected>>", self._on_theme_change)

        # Theme Lab launcher button
        RoundedButton(
            theme_frame, "🎨  Theme Lab", self._open_theme_lab,
            bg_color=C["accent_dim"], hover_color=C["accent"],
            text_color=C["text"], height=34, radius=12,
            text_font=("Lato", 8, "bold"), canvas_bg=C["sidebar"],
        ).pack(fill="x", pady=(8, 0))

        # Check for Updates button
        upd_sep = tk.Frame(self._nav, bg=C["border"], height=1)
        upd_sep.pack(fill="x", padx=12, pady=(8, 6))

        upd_frame = tk.Frame(self._nav, bg=C["sidebar"], padx=12)
        upd_frame.pack(fill="x", pady=(0, 4))

        RoundedButton(
            upd_frame, "↑  Check for Updates", self._check_for_updates,
            bg_color=C["accent_dim"], hover_color=C["accent"],
            text_color=C["text"], height=34, radius=12,
            text_font=("Lato", 8, "bold"), canvas_bg=C["sidebar"],
        ).pack(fill="x")

        # Reset to Default button
        reset_sep = tk.Frame(self._nav, bg=C["border"], height=1)
        reset_sep.pack(fill="x", padx=12, pady=(6, 6))

        reset_frame = tk.Frame(self._nav, bg=C["sidebar"], padx=12)
        reset_frame.pack(fill="x", pady=(0, 4))

        reset_btn = RoundedButton(
            reset_frame, "⟳  Reset to Default", self._reset_to_default,
            bg_color="#3d1a1a", hover_color=C["error"],
            text_color=C["error"], height=34, radius=12,
            text_font=("Lato", 8, "bold"), canvas_bg=C["sidebar"],
        )
        reset_btn.pack(fill="x")

        # Flexible spacer — pushes version label to the bottom
        tk.Frame(self._nav, bg=C["sidebar"]).pack(fill="y", expand=True)

        ver_row = tk.Frame(self._nav, bg=C["sidebar"])
        ver_row.pack(pady=(0, 12), padx=12, fill="x")

        tk.Label(ver_row, text="CHSuite v7.1", font=("Lato", 8),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(side="left")

        info_lbl = tk.Label(ver_row, text=" ⓘ", font=("Lato", 9),
                            fg=C["accent_dim"], bg=C["sidebar"], cursor="hand2")
        info_lbl.pack(side="left")

        self._wn_tooltip = None

        def _show_wn_tip(e):
            if self._wn_tooltip:
                return
            tip = tk.Toplevel(self)
            tip.overrideredirect(True)
            tip.configure(bg=C["border"])
            self._wn_tooltip = tip

            f = tk.Frame(tip, bg=C["card"], padx=14, pady=12)
            f.pack(padx=1, pady=1)

            tk.Label(f, text="What's New in v7.1", font=("Lato", 9, "bold"),
                     fg=C["text"], bg=C["card"]).pack(anchor="w")

            items = [
                (C["success"],  "CHPreScan Added to the CHSuite"),
            ]
            for clr, txt in items:
                row = tk.Frame(f, bg=C["card"])
                row.pack(anchor="w", pady=(4, 0))
                tk.Label(row, text="•", font=FTS, fg=clr,
                         bg=C["card"]).pack(side="left", padx=(0, 5))
                tk.Label(row, text=txt, font=FTS, fg=C["text_mid"],
                         bg=C["card"]).pack(side="left")

            sep = tk.Frame(f, bg=C["border"], height=1)
            sep.pack(fill="x", pady=(10, 6))
            see_lbl = tk.Label(f, text="Click ⓘ to open the full What's New",
                               font=("Lato", 7), fg=C["text_dim"], bg=C["card"],
                               cursor="hand2")
            see_lbl.pack(anchor="w")
            see_lbl.bind("<Button-1>", lambda _: (tip.destroy(), self._show_whats_new()))

            # Position: to the right of the sidebar
            tip.update_idletasks()
            tip_w = tip.winfo_reqwidth()
            tip_h = tip.winfo_reqheight()
            sx = self.winfo_rootx() + 204
            sy = self.winfo_rooty() + self.winfo_height() - tip_h - 20
            tip.geometry(f"+{sx}+{sy}")

        def _hide_wn_tip(e):
            if self._wn_tooltip:
                try:
                    self._wn_tooltip.destroy()
                except Exception:
                    pass
                self._wn_tooltip = None

        info_lbl.bind("<Enter>", _show_wn_tip)
        info_lbl.bind("<Leave>", _hide_wn_tip)
        info_lbl.bind("<Button-1>", lambda e: self._show_whats_new())

    def _make_toplevel(self, title: str = "") -> tk.Toplevel:
        """Create a Toplevel that inherits the app icon."""
        win = tk.Toplevel(self)
        if title:
            win.title(title)
        try:
            if hasattr(self, "_icon_img"):
                win.iconphoto(False, self._icon_img)
        except Exception:
            pass
        return win

    def _nav_hover(self, *_):
        """No-op: hover is handled internally by _RoundedNavBtn."""
        pass

    def _show_page(self, page_id):
        # Build the page on first visit (lazy construction keeps startup fast)
        if page_id not in self._pages:
            builder = getattr(self, f"_build_page_{page_id}", None)
            if builder:
                builder()
        for pg in self._pages.values():
            pg.pack_forget()
        if page_id in self._pages:
            self._pages[page_id].pack(fill="both", expand=True)
            self._current_page = page_id
        for pid, btn in self._nav_btns.items():
            btn.set_active(pid == page_id)
        # Route Ctrl+S at the window level so it fires regardless of which
        # child widget currently holds keyboard focus.
        if page_id == "bgchanger":
            self.bind("<Control-s>", lambda e: self._act_apply_all())
        elif page_id == "notegen":
            self.bind("<Control-s>", lambda e: self._ng_export_ini())
        else:
            self.unbind("<Control-s>")
        # Update Discord activity whenever the active tab changes
        if hasattr(self, "_drpc"):
            self._update_discord_rpc()

    # ── Theme Lab launcher ────────────────────────────────────────────────────
    def _open_theme_lab(self):
        """Launch ThemeGen from the same folder as CHSuite (hidden file)."""
        _tg_name = "ThemeGen.exe" if _IS_WINDOWS else "ThemeGen"
        exe = _app_dir() / _tg_name
        if not exe.is_file():
            messagebox.showerror(
                "Theme Lab",
                f"{_tg_name} not found in:\n{_app_dir()}\n\n"
                f"Make sure {_tg_name} is in the same folder as CHSuite.",
                parent=self,
            )
            return
        try:
            if _IS_WINDOWS:
                subprocess.Popen(
                    [str(exe)],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # Ensure the binary is executable before launching (build.sh
                # intentionally strips +x from ThemeGen so users can't run it
                # directly, but CHSuite needs to be able to launch it).
                import stat as _stat
                _mode = exe.stat().st_mode
                if not (_mode & _stat.S_IXUSR):
                    exe.chmod(_mode | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)
                # DETACHED_PROCESS is Windows-only; start_new_session is the POSIX equivalent
                subprocess.Popen(
                    [str(exe)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as exc:
            messagebox.showerror("Theme Lab", f"Failed to launch {_tg_name}:\n{exc}", parent=self)

    # ── theme change ──────────────────────────────────────────────────────────
    def _on_theme_change(self, event=None):
        """Apply the chosen theme and restart the window so all colors refresh."""
        name = self._theme_var.get()
        if not _load_theme(name):
            messagebox.showwarning(
                "Theme Error",
                f"Could not load theme '{name}'.\n"
                "Make sure themes/{name}.json exists and is valid.",
                parent=self)
            # Revert picker to the currently saved theme
            self._theme_var.set(self._cfg.get("theme", "Default"))
            return

        # Save choice to config
        self._cfg["theme"] = name
        _save_json(CONFIG_FILE, self._cfg)

        # Notify user that a restart is needed for a full repaint
        resp = messagebox.askokcancel(
            "Theme Applied",
            f"Theme '{name}' will be fully applied the next time CHSuite starts.\n\n"
            "Restart now?",
            parent=self)
        if resp:
            self._on_close()
            python = sys.executable
            os.execv(python, [python] + sys.argv)

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 0 — ABOUT THIS TOOL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_about(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["about"] = page

        # Scrollable canvas setup
        canvas = tk.Canvas(page, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        inner = tk.Frame(canvas, bg=C["bg"], padx=32, pady=14)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            canvas.itemconfig(win_id, width=canvas.winfo_width())))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        self._bind_mousewheel_to_canvas(canvas)

        # Header
        tk.Label(inner, text="About CHSuite",
                 font=("Lato", 22, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner,
                 text="A comprehensive utility suite for Clone Hero — built to give you full control over every aspect of the game.",
                 font=FT, fg=C["text_dim"], bg=C["bg"], wraplength=820, justify="left",
                 ).pack(anchor="w", pady=(2, 6))

        _sep(inner, bg=C["border"]).pack(fill="x", pady=(0, 8))

        # Tool entries: (icon, page_id, name, accent_color, description)
        tools = [
            ("◈", "bgchanger", "CHMenuChanger", C["accent"],
             "Replace in-game menu backgrounds with any image by patching asset bundles directly via UnityPy."),
            ("✦", "namegen", "CHNameGen", C["accent2"],
             "Design player name tags with full gradient and per-letter colour control, then copy them straight into Clone Hero."),
            ("♪", "notegen", "CHNoteGen", C["accent3"],
             "Craft custom note and highway colour profiles with a live preview, then export them ready for use in-game."),
            ("⊘", "cleaner", "CHCleaner", C["warn"],
             "Parse badsongs.txt and delete every failed-to-load folder in one click, keeping your library clean and fast."),
            ("⚙", "patcher", "CHPatcher", C["success"],
             "Stop the Clone Hero Launcher from overwriting your customised files by marking installs as manually managed."),
            ("♫", "songmanager", "CHSongManager", C["accent2"],
             "Search Chorus Encore (enchor.us), download, auto-extract, and install charts directly into your Clone Hero songs folder."),
            ("▦", "gamemanager", "CHManager", C["accent"],
             "Browse, download, and manage every Clone Hero installation from one unified interface — no external launcher needed."),
        ]

        for icon, page_id, name, accent, desc in tools:
            card = _RoundedAboutCard(inner, padx=20, pady=8,
                                     bg=C["card"], outer_bg=C["bg"])
            card.pack(fill="x", pady=(0, 4))
            cf = card.inner  # pack content into this frame

            # Icon + name row
            hdr = tk.Frame(cf, bg=C["card"])
            hdr.pack(anchor="w", fill="x")
            icon_lbl = tk.Label(hdr, text=icon, font=("Lato", 14),
                                fg=accent, bg=C["card"])
            icon_lbl.pack(side="left", padx=(0, 8))

            name_lbl = tk.Label(hdr, text=name, font=("Lato", 12, "bold"),
                                fg=accent, bg=C["card"])
            name_lbl.pack(side="left")

            desc_lbl = tk.Label(cf, text=desc,
                                font=FT, fg=C["text_mid"], bg=C["card"],
                                wraplength=820, justify="left")
            desc_lbl.pack(anchor="w", pady=(3, 0))

            # Make the entire card clickable with hover highlight.
            # Debounce Leave so crossing between child widgets doesn't flash.
            def _bind_card(cv, inf, h, il, nl, dl, pid=page_id, acc=accent):
                _leave_job = [None]
                def _navigate(e=None):
                    self._show_page(pid)
                def _on_enter(e=None):
                    if _leave_job[0] is not None:
                        self.after_cancel(_leave_job[0])
                        _leave_job[0] = None
                    nl.config(fg=C["text"])
                def _on_leave(e=None):
                    if _leave_job[0] is not None:
                        self.after_cancel(_leave_job[0])
                    _leave_job[0] = self.after(80, lambda: nl.config(fg=acc))
                for w in (cv, inf, h, il, nl, dl):
                    w.config(cursor="hand2")
                    w.bind("<Button-1>", lambda e, fn=_navigate: fn())
                    w.bind("<Enter>",    lambda e, fn=_on_enter: fn())
                    w.bind("<Leave>",    lambda e, fn=_on_leave: fn())
            _bind_card(card._cv, cf, hdr, icon_lbl, name_lbl, desc_lbl)

        # Footer
        _sep(inner, bg=C["border"]).pack(fill="x", pady=(8, 6))
        tk.Label(inner, text="CHSuite v7.1  ·  by JURMR",
                 font=("Lato", 8), fg=C["text_dim"], bg=C["bg"]).pack(anchor="w")

    # ── What's New popup ──────────────────────────────────────────────────────
    def _show_whats_new(self):
        """Show a one-time What's New dialog for v7.1"""
        win = self._make_toplevel("What's New in CHSuite v7.1")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        # Centre over main window
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  // 2 - 275
        y = self.winfo_y() + self.winfo_height() // 2 - 250
        win.geometry(f"550x500+{x}+{y}")

        # ── Fixed header ──────────────────────────────────────────────────────
        header = tk.Frame(win, bg=C["bg"], padx=28, pady=20)
        header.pack(fill="x", side="top")

        title_row = tk.Frame(header, bg=C["bg"])
        title_row.pack(anchor="center")
        tk.Label(title_row, text="🎉", font=("Lato", 18),
                 fg=C["text"], bg=C["bg"]).pack(side="left", padx=(0, 10))
        tk.Label(title_row, text="What's New in v7.1",
                 font=("Lato", 16, "bold"), fg=C["text"], bg=C["bg"]).pack(side="left")
        tk.Label(header, text="Here's everything that changed in this release:",
                 font=FT, fg=C["text_dim"], bg=C["bg"], justify="center").pack(anchor="center", pady=(6, 0))
        _sep(header, bg=C["border"]).pack(fill="x", pady=(12, 0))

        # ── Fixed footer (packed before content so it stays anchored) ─────────
        footer = tk.Frame(win, bg=C["bg"], padx=28, pady=14)
        footer.pack(fill="x", side="bottom")
        _sep(footer, bg=C["border"]).pack(fill="x", pady=(0, 12))
        RoundedButton(footer, "Got it  ✓", win.destroy,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="white", height=44, radius=18,
                      text_font=("Lato", 10, "bold"),
                      canvas_bg=C["bg"], width=140).pack(anchor="e")

        # ── Scrollable content area ───────────────────────────────────────────
        scroll_frame = tk.Frame(win, bg=C["bg"])
        scroll_frame.pack(fill="both", expand=True, padx=28)

        canvas = tk.Canvas(scroll_frame, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        inner = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            canvas.itemconfig(win_id, width=canvas.winfo_width())))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        self._bind_mousewheel_to_canvas(canvas)

        changes = [
            (C["success"],  "CHPreScan Added to the CHSuite",
             "ever got stuck on clone hero waiting for your songs to scan? its because their "
             "scanning sucks sometimes. mine never sucks. infact, its so good, im surprised it even works"),
        ]

        for accent, heading, body in changes:
            row = _card(inner, padx=14, pady=10)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=heading, font=("Lato", 10, "bold"),
                     fg=accent, bg=C["card"]).pack(anchor="w")
            tk.Label(row, text=body, font=FT, fg=C["text_mid"], bg=C["card"],
                     wraplength=460, justify="left").pack(anchor="w", pady=(3, 0))



    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 1 — BG CHANGER
    # ══════════════════════════════════════════════════════════════════════════
    def _update_discord_dot(self):
        """Update the titlebar dot colour: green = connected, grey = off."""
        if not hasattr(self, "_discord_dot"):
            return
        if self._drpc._running:
            self._discord_dot.config(fg=C["success"], text="⬤  Discord")
        elif self._cfg.get("discord_client_id", ""):
            # ID is set but connection failed (Discord closed, bad ID, etc.)
            self._discord_dot.config(fg=C["error"], text="⬤  Discord")
        else:
            # No ID configured yet — prompt the user
            self._discord_dot.config(fg=C["text_dim"], text="⬤  Discord")

    def _discord_setup_prompt(self):
        """Show Discord Rich Presence connection status (read-only)."""
        win = self._make_toplevel("Discord Rich Presence")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        inner = tk.Frame(win, bg=C["bg"], padx=28, pady=24)
        inner.pack(fill="both")

        tk.Label(inner, text="Discord Rich Presence", font=("Lato", 14, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner, text="CHSuite activity is shown on your Discord profile.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 16))

        # Status card
        card = tk.Frame(inner, bg=C["card"],
                        highlightbackground=C["border"], highlightthickness=1,
                        padx=16, pady=14)
        card.pack(fill="x")

        status_text = "✓  Connected" if self._drpc._running else "✗  Not connected — make sure Discord is open."
        status_fg   = C["success"] if self._drpc._running else C["error"]
        status_lbl  = tk.Label(card, text=status_text, font=(FT[0], FT[1], "bold"),
                               fg=status_fg, bg=C["card"])
        status_lbl.pack(anchor="w")

        # Progress bar — hidden until reconnect starts
        bar = ttk.Progressbar(card, mode="indeterminate", length=260)

        foot = tk.Frame(win, bg=C["panel"], padx=20, pady=12)
        foot.pack(fill="x")

        close_btn = RoundedButton(foot, "Close", win.destroy,
                                  bg_color=C["border"], hover_color=C["hover"],
                                  text_color=C["text_dim"], height=42, radius=16,
                                  text_font=FT, canvas_bg=C["panel"],
                                  width=108)
        close_btn.pack(side="right")

        reconnect_btn = RoundedButton(foot, "Reconnect", None,
                                      bg_color=C["accent"], hover_color=C["accent_dim"],
                                      text_color="white", height=42, radius=16,
                                      text_font=FTB, canvas_bg=C["panel"],
                                      width=130)
        reconnect_btn.pack(side="right", padx=(0, 6))

        def _reconnect():
            reconnect_btn.command = None   # prevent double-click during run
            reconnect_btn.config(state="disabled", cursor="arrow")
            close_btn.config(state="disabled", cursor="arrow")
            status_lbl.config(text="Reconnecting…", fg=C["text_dim"])
            bar.pack(anchor="w", pady=(10, 0))
            bar.start(12)
            win.update_idletasks()

            def _worker():
                self._drpc.close()
                _client_id = self._cfg.get("discord_client_id", DISCORD_CLIENT_ID_DEFAULT)
                self._drpc = _DiscordRPC(_client_id)

            def _done():
                bar.stop()
                bar.pack_forget()
                self._update_discord_rpc()
                self._update_discord_dot()
                win.destroy()
                self._status("Discord Rich Presence reconnected." if self._drpc._running
                             else "Discord RPC: could not connect — is Discord open?")

            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            def _poll():
                if t.is_alive():
                    win.after(100, _poll)
                else:
                    _done()
            win.after(100, _poll)

        reconnect_btn.command = _reconnect

        # Centre on main window
        win.update_idletasks()
        rw = self.winfo_width();  rh = self.winfo_height()
        rx = self.winfo_rootx();  ry = self.winfo_rooty()
        dw = win.winfo_reqwidth(); dh = win.winfo_reqheight()
        win.geometry(f"+{rx+(rw-dw)//2}+{ry+(rh-dh)//2}")

    def _update_discord_rpc(self):
        """Schedule a Discord presence update, debounced by 600 ms.

        Discord enforces a 15-second rate limit between updates.  Calling
        update() too soon raises an exception that pypresence swallows
        silently, which is why CHCleaner / CHPatcher never appeared —
        the user switched tabs within the rate-limit window.

        We cancel any pending scheduled call and re-schedule 600 ms out,
        so only the *last* tab switch in a burst actually fires.  After the
        first update on launch we also enforce a 15-second cooldown.
        """
        # Cancel any already-pending debounce job
        job = getattr(self, "_drpc_pending", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass

        def _do_update():
            self._drpc_pending = None
            import time
            now = time.monotonic()
            last = getattr(self, "_drpc_last_update", 0)
            # If we're still inside the 15 s window, reschedule for when it ends
            gap = now - last
            if gap < 15 and last != 0:
                wait_ms = int((15 - gap) * 1000) + 100
                self._drpc_pending = self.after(wait_ms, _do_update)
                return
            page = getattr(self, "_current_page", "bgchanger") or "bgchanger"
            tool = _PAGE_DISPLAY_NAMES.get(page, "CHSuite")
            platform_suffix = f" · {_PLATFORM_STR}"
            if page == "bgchanger":
                profile = getattr(self, "_active_name", "") or ""
                bg      = self._selected_bg()
                details = f"Profile: {profile}  ·  {bg}" if profile else f"Editing: {bg}"
                self._drpc.update(tool + platform_suffix, details)
            elif page == "notegen":
                profile = getattr(self, "_ng_active_name", "") or ""
                details = f"Profile: {profile}" if profile else ""
                self._drpc.update(tool + platform_suffix, details)
            elif page == "songmanager":
                sdir = getattr(self, "_dir_var", None)
                details = f"Library: {Path(sdir.get()).name}" if sdir and sdir.get() else ""
                self._drpc.update(tool + platform_suffix, details)
            else:
                self._drpc.update(tool + platform_suffix)
            self._drpc_last_update = time.monotonic()

        self._drpc_pending = self.after(600, _do_update)

    # ── Check for Updates ─────────────────────────────────────────────────────
    def _check_for_updates(self):
        """Fetch the latest GitHub release, compare versions, and auto-install."""
        CURRENT = "7.1"
        API_URL  = "https://api.github.com/repos/iamjrmh/CHSuite/releases/latest"
        INSTALL_DIR = Path("C:/CHSuite")  # Windows full-install path

        if getattr(sys, "frozen", False):
            _run_dir = Path(sys.executable).parent.resolve()
        else:
            _run_dir = Path(__file__).parent.resolve()

        if _IS_LINUX:
            # On Linux: running inside an AppImage = full install; anything else = portable
            is_portable = not bool(os.environ.get("APPIMAGE"))
            # The "install location" for a Linux AppImage is where the AppImage lives
            _linux_appimage = os.environ.get("APPIMAGE", "")
            _linux_install_dir = Path(_linux_appimage).parent if _linux_appimage else _run_dir
        elif _IS_MAC:
            # On macOS: "portable" = not running from /Applications
            is_portable = not str(_run_dir).lower().startswith("/applications")
        else:
            # Windows: portable = not running from C:\CHSuite
            is_portable = not str(_run_dir).lower().startswith(
                str(INSTALL_DIR.resolve()).lower())

        win = self._make_toplevel("Check for Updates")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  // 2 - 195
        y = self.winfo_y() + self.winfo_height() // 2 - 130
        win.geometry(f"390x262+{x}+{y}")

        outer = tk.Frame(win, bg=C["bg"], padx=24, pady=20)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Check for Updates", font=("Lato", 13, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(anchor="w")
        _sep(outer, bg=C["border"]).pack(fill="x", pady=(10, 12))

        status_var = tk.StringVar(value="Checking GitHub…")
        status_lbl = tk.Label(outer, textvariable=status_var,
                              font=FT, fg=C["text_dim"], bg=C["bg"],
                              wraplength=340, justify="left")
        status_lbl.pack(anchor="w")

        ver_frame = tk.Frame(outer, bg=C["bg"])
        ver_frame.pack(anchor="w", pady=(8, 0))
        cur_lbl = tk.Label(ver_frame, text=f"Installed:  v{CURRENT}",
                           font=("Lato", 9), fg=C["text_mid"], bg=C["bg"])
        cur_lbl.pack(anchor="w")
        lat_lbl = tk.Label(ver_frame, text="Latest:      checking…",
                           font=("Lato", 9), fg=C["text_dim"], bg=C["bg"])
        lat_lbl.pack(anchor="w")

        # ── Enable CHSuite Beta toggle ─────────────────────────────────────────
        _beta_initial = bool(self._cfg.get("beta_updates_enabled", False))
        beta_var = tk.BooleanVar(value=_beta_initial)
        beta_frame = tk.Frame(outer, bg=C["bg"])
        beta_frame.pack(anchor="w", pady=(10, 0))

        def _on_beta_toggle():
            if beta_var.get():
                # User is trying to ENABLE beta — show I CONFIRM prompt
                dlg = self._make_toplevel("Enable Beta Builds")
                dlg.configure(bg=C["bg"])
                dlg.resizable(False, False)
                dlg.grab_set()
                dlg.update_idletasks()
                dx = win.winfo_x() + win.winfo_width()  // 2 - 185
                dy = win.winfo_y() + win.winfo_height() // 2 - 120
                dlg.geometry(f"370x242+{dx}+{dy}")

                di = tk.Frame(dlg, bg=C["bg"], padx=20, pady=16)
                di.pack(fill="both", expand=True)

                tk.Label(di, text="⚠  Enable Beta Builds",
                         font=("Lato", 12, "bold"),
                         fg=C.get("warn", "#f59e0b"), bg=C["bg"]).pack(anchor="w")
                _sep(di, bg=C["border"]).pack(fill="x", pady=(8, 10))
                tk.Label(di, wraplength=326, justify="left", bg=C["bg"],
                         fg=C["text_mid"], font=("Lato", 9),
                         text=(
                             "Beta (pre-release) builds may be unstable, contain bugs, "
                             "or break existing functionality.  They are NOT recommended "
                             "unless you have a specific reason or are testing a known issue."
                             "\n\nType  I CONFIRM  below to proceed."
                         )).pack(anchor="w")

                confirm_var = tk.StringVar()
                conf_entry = tk.Entry(di, textvariable=confirm_var,
                                      font=("Lato", 10), bg=C["card"],
                                      fg=C["text"], insertbackground=C["text"],
                                      relief="flat", bd=0, highlightthickness=1,
                                      highlightbackground=C["border"],
                                      highlightcolor=C["accent"])
                conf_entry.pack(fill="x", pady=(10, 0), ipady=6)
                conf_entry.focus_set()

                err_lbl = tk.Label(di, text="", font=("Lato", 8),
                                   fg=C.get("error", "#ef4444"), bg=C["bg"])
                err_lbl.pack(anchor="w", pady=(3, 0))

                def _submit(_event=None):
                    if confirm_var.get().strip() == "I CONFIRM":
                        self._cfg["beta_updates_enabled"] = True
                        _save_json(CONFIG_FILE, self._cfg)
                        dlg.destroy()
                        # Re-run the fetch now that beta is enabled
                        status_var.set("Checking GitHub…")
                        lat_lbl.config(text="Latest:      checking…",
                                       fg=C["text_dim"])
                        threading.Thread(target=_fetch, daemon=True).start()
                    else:
                        err_lbl.config(
                            text="You must type exactly:  I CONFIRM")
                        conf_entry.delete(0, "end")

                def _cancel_beta():
                    beta_var.set(False)   # revert the checkbox
                    dlg.destroy()

                conf_entry.bind("<Return>", _submit)
                dlg.protocol("WM_DELETE_WINDOW", _cancel_beta)

                df = tk.Frame(di, bg=C["bg"]); df.pack(anchor="e", pady=(8, 0))
                RoundedButton(df, "Cancel", _cancel_beta,
                              bg_color=C["card"], hover_color=C["hover"],
                              text_color=C["text_mid"], height=36, radius=14,
                              text_font=("Lato", 9, "bold"),
                              canvas_bg=C["bg"], width=90).pack(side="left")
                RoundedButton(df, "Enable", _submit,
                              bg_color=C.get("warn", "#f59e0b"),
                              hover_color="#d97706",
                              text_color="white", height=36, radius=14,
                              text_font=("Lato", 9, "bold"),
                              canvas_bg=C["bg"], width=90).pack(
                                  side="left", padx=(8, 0))
            else:
                # User is DISABLING beta — no confirmation needed
                self._cfg["beta_updates_enabled"] = False
                _save_json(CONFIG_FILE, self._cfg)
                status_var.set("Checking GitHub…")
                lat_lbl.config(text="Latest:      checking…", fg=C["text_dim"])
                threading.Thread(target=_fetch, daemon=True).start()

        beta_chk = tk.Checkbutton(
            beta_frame, text="Enable CHSuite Beta  (pre-release builds)",
            variable=beta_var, command=_on_beta_toggle,
            font=("Lato", 9), fg=C["text_mid"], bg=C["bg"],
            activeforeground=C["text"], activebackground=C["bg"],
            selectcolor=C["card"], relief="flat", bd=0,
            highlightthickness=0)
        beta_chk.pack(side="left")
        if _beta_initial:
            tk.Label(beta_frame, text="  ⚠ beta",
                     font=("Lato", 8), fg=C.get("warn", "#f59e0b"),
                     bg=C["bg"]).pack(side="left")

        # Progress bar — hidden until a download starts
        prog_frame = tk.Frame(outer, bg=C["bg"])
        prog_bar   = ttk.Progressbar(prog_frame, length=342, mode="determinate")
        prog_bar.pack(fill="x")
        prog_lbl = tk.Label(prog_frame, text="", font=FTS,
                            fg=C["text_dim"], bg=C["bg"])
        prog_lbl.pack(anchor="w", pady=(2, 0))

        _sep(outer, bg=C["border"]).pack(fill="x", pady=(14, 10))

        btn_frame = tk.Frame(outer, bg=C["bg"])
        btn_frame.pack(anchor="e")

        close_btn = RoundedButton(
            btn_frame, "Close", win.destroy,
            bg_color=C["accent"], hover_color=C["accent_dim"],
            text_color="white", height=44, radius=18,
            text_font=("Lato", 10, "bold"), canvas_bg=C["bg"],
            width=128)
        close_btn.pack(side="right")

        install_btn = RoundedButton(
            btn_frame, "Install Update", None,
            bg_color=C["success"], hover_color="#16a34a",
            text_color="white", height=44, radius=18,
            text_font=("Lato", 10, "bold"), canvas_bg=C["bg"],
            width=160)
        # packed only when an update is found

        _cancel = threading.Event()

        def _restart():
            status_var.set("Restarting CHSuite…")
            status_lbl.config(fg=C["success"])
            close_btn.config(state="disabled")
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable])
            else:
                subprocess.Popen([sys.executable] + sys.argv)
            self.after(1500, self.destroy)

        def _apply(tmp_file, tmp_dir):
            # ── Linux branch (shell-script updater, no cmd.exe) ───────────────
            if _IS_LINUX:
                import zipfile, stat as _stat

                def _linux_apply():
                    try:
                        if is_portable:
                            # Portable (zip): extract over current dir then relaunch
                            def _start_prog():
                                prog_bar.config(mode="indeterminate")
                                prog_bar.start(15)
                                prog_lbl.config(text="Extracting…")
                                prog_frame.pack(anchor="w", fill="x", pady=(8, 0))
                                win.geometry(f"390x290+{x}+{y}")
                                status_var.set("Extracting archive…")
                                status_lbl.config(fg=C["text_mid"])
                                close_btn.config(state="disabled")
                            self.after(0, _start_prog)

                            with zipfile.ZipFile(str(tmp_file), "r") as zf:
                                names = zf.namelist()
                            total = max(len(names), 1)

                            staging_dir = Path(tmp_dir) / "staging"
                            staging_dir.mkdir(parents=True, exist_ok=True)
                            with zipfile.ZipFile(str(tmp_file), "r") as zf:
                                for i, name in enumerate(names, 1):
                                    zf.extract(name, staging_dir)
                                    if i % 4 == 0 or i == total:
                                        pct = int(i * 100 / total)
                                        def _upd(n=i, t=total, p=pct):
                                            prog_bar.stop()
                                            prog_bar.config(mode="determinate",
                                                            maximum=t, value=n)
                                            prog_lbl.config(
                                                text=f"{n} / {t} files  ({p}%)")
                                        self.after(0, _upd)

                            contents = list(staging_dir.iterdir())
                            source_dir = (contents[0]
                                          if len(contents) == 1 and contents[0].is_dir()
                                          else staging_dir)

                            if getattr(sys, "frozen", False):
                                exe_target = str(_run_dir / Path(sys.executable).name)
                            else:
                                exe_target = sys.executable

                            sh_path = Path(tmp_dir) / "ch_updater.sh"
                            sh_content  = "#!/bin/bash\n"
                            sh_content += "sleep 2\n"
                            sh_content += f'cp -a "{source_dir}/"* "{str(_run_dir)}/"\n'
                            sh_content += f'chmod +x "{exe_target}" 2>/dev/null || true\n'
                            sh_content += f'"{exe_target}" &\n'
                            sh_content += f'rm -rf "{str(tmp_dir)}"\n'
                            sh_content += 'rm -- "$0"\n'
                            sh_path.write_text(sh_content, encoding="utf-8")
                            sh_path.chmod(sh_path.stat().st_mode | 0o111)
                            subprocess.Popen(["bash", str(sh_path)])

                        else:
                            # Full install (AppImage): replace current AppImage
                            appimage_src = str(tmp_file)
                            if _linux_appimage:
                                appimage_dest = _linux_appimage
                            else:
                                appimage_dest = str(_linux_install_dir / "CHSuiteLinux.AppImage")

                            sh_path = Path(tmp_dir) / "ch_updater.sh"
                            sh_content  = "#!/bin/bash\n"
                            sh_content += "sleep 2\n"
                            sh_content += f'cp "{appimage_src}" "{appimage_dest}"\n'
                            sh_content += f'chmod +x "{appimage_dest}"\n'
                            sh_content += f'"{appimage_dest}" &\n'
                            sh_content += f'rm -rf "{str(tmp_dir)}"\n'
                            sh_content += 'rm -- "$0"\n'
                            sh_path.write_text(sh_content, encoding="utf-8")
                            sh_path.chmod(sh_path.stat().st_mode | 0o111)
                            subprocess.Popen(["bash", str(sh_path)])

                        def _quit_linux():
                            status_var.set("Update ready — restarting…")
                            status_lbl.config(fg=C["success"])
                            prog_lbl.config(text="")
                            self.after(1200, lambda: (self.destroy(), os._exit(0)))
                        self.after(0, _quit_linux)

                    except Exception as exc:
                        self.after(0, lambda e=exc: (
                            prog_bar.stop(),
                            prog_frame.pack_forget(),
                            win.geometry(f"390x230+{x}+{y}"),
                            status_var.set(f"Update failed: {e}"),
                            status_lbl.config(fg=C["error"]),
                            close_btn.config(state="normal", text="Close",
                                             command=win.destroy)))

                threading.Thread(target=_linux_apply, daemon=True).start()
                return  # skip macOS / Windows paths below

            # ── macOS branch ──────────────────────────────────────────────────
            if _IS_MAC:
                def _mac_apply():
                    try:
                        fname_lower = str(tmp_file).lower()
                        if fname_lower.endswith(".pkg"):
                            def _start_pkg():
                                prog_bar.config(mode="indeterminate")
                                prog_bar.start(15)
                                prog_lbl.config(text="Running installer…")
                                prog_frame.pack(anchor="w", fill="x", pady=(8, 0))
                                win.geometry(f"390x290+{x}+{y}")
                                status_var.set("Running .pkg installer…")
                                status_lbl.config(fg=C["text_mid"])
                                close_btn.config(state="disabled")
                            self.after(0, _start_pkg)
                            result = subprocess.run(
                                ["sudo", "installer", "-pkg", str(tmp_file),
                                 "-target", "/"],
                                timeout=300)
                            if result.returncode != 0:
                                raise RuntimeError(
                                    f"pkg installer exited with code "
                                    f"{result.returncode}.")

                        elif fname_lower.endswith(".dmg"):
                            def _start_dmg():
                                prog_bar.config(mode="indeterminate")
                                prog_bar.start(15)
                                prog_lbl.config(text="Mounting disk image…")
                                prog_frame.pack(anchor="w", fill="x", pady=(8, 0))
                                win.geometry(f"390x290+{x}+{y}")
                                status_var.set("Mounting disk image…")
                                status_lbl.config(fg=C["text_mid"])
                                close_btn.config(state="disabled")
                            self.after(0, _start_dmg)
                            import plistlib
                            mount_result = subprocess.run(
                                ["hdiutil", "attach", str(tmp_file),
                                 "-nobrowse", "-readonly", "-plist"],
                                capture_output=True, text=True, timeout=60)
                            if mount_result.returncode != 0:
                                raise RuntimeError(
                                    f"hdiutil attach failed:\n"
                                    f"{mount_result.stderr}")
                            plist_data = plistlib.loads(
                                mount_result.stdout.encode())
                            mount_point = None
                            for entity in plist_data.get("system-entities", []):
                                if "mount-point" in entity:
                                    mount_point = entity["mount-point"]
                                    break
                            if not mount_point:
                                raise RuntimeError(
                                    "Could not determine DMG mount point.")
                            try:
                                self.after(0, lambda: prog_lbl.config(
                                    text="Copying app bundle…"))
                                apps = list(Path(mount_point).glob("*.app"))
                                if not apps:
                                    raise RuntimeError(
                                        "No .app bundle found inside the DMG.")
                                src_app = apps[0]
                                dst_app = Path("/Applications") / src_app.name
                                if dst_app.exists():
                                    shutil.rmtree(str(dst_app))
                                shutil.copytree(str(src_app), str(dst_app))
                            finally:
                                subprocess.run(
                                    ["hdiutil", "detach", mount_point,
                                     "-quiet"],
                                    capture_output=True, timeout=30)
                        else:
                            raise RuntimeError(
                                f"Unsupported update format: "
                                f"{Path(str(tmp_file)).suffix}")

                        def _quit_mac():
                            status_var.set("Update ready — restarting…")
                            status_lbl.config(fg=C["success"])
                            prog_lbl.config(text="")
                            self.after(1200, lambda: (self.destroy(),
                                                      os._exit(0)))
                        self.after(0, _quit_mac)

                    except Exception as exc:
                        self.after(0, lambda e=exc: (
                            prog_bar.stop(),
                            prog_frame.pack_forget(),
                            win.geometry(f"390x230+{x}+{y}"),
                            status_var.set(f"Update failed: {e}"),
                            status_lbl.config(fg=C["error"]),
                            close_btn.config(state="normal", text="Close",
                                             command=win.destroy)))

                threading.Thread(target=_mac_apply, daemon=True).start()
                return  # skip Windows path below

            # ── Windows branch ────────────────────────────────────────────────
            if is_portable:
                # ── Portable: show extraction progress, then hand off to batch ──
                import zipfile
                status_var.set("Extracting…")
                status_lbl.config(fg=C["text_mid"])
                # Keep prog_frame visible and switch to indeterminate while we
                # count the entries, then back to determinate during extraction.
                prog_bar.config(mode="indeterminate")
                prog_bar.start(15)
                prog_lbl.config(text="Reading archive…")
                close_btn.config(state="disabled")

                def _extract():
                    try:
                        # ── 1. Count entries for progress ─────────────────────
                        with zipfile.ZipFile(tmp_file, "r") as zf:
                            names = zf.namelist()
                        total = max(len(names), 1)

                        def _start_det():
                            prog_bar.stop()
                            prog_bar.config(mode="determinate", value=0,
                                            maximum=total)
                            prog_lbl.config(text=f"0 / {total} files")
                        self.after(0, _start_det)

                        # ── 2. Extract file-by-file with UI progress ──────────
                        staging_dir = Path(tmp_dir) / "staging"
                        staging_dir.mkdir(parents=True, exist_ok=True)
                        with zipfile.ZipFile(tmp_file, "r") as zf:
                            for i, name in enumerate(names, 1):
                                zf.extract(name, staging_dir)
                                if i % 4 == 0 or i == total:
                                    pct = int(i * 100 / total)
                                    def _upd(n=i, t=total, p=pct):
                                        prog_bar.config(value=n)
                                        prog_lbl.config(
                                            text=f"{n} / {t} files  ({p}%)")
                                    self.after(0, _upd)

                        # Unwrap a single top-level folder if the zip packed
                        # everything inside one (e.g. CHSuite-3.2/)
                        contents = list(staging_dir.iterdir())
                        source_dir = (contents[0]
                                      if len(contents) == 1 and contents[0].is_dir()
                                      else staging_dir)

                        # ── 3. Resolve the running exe name for the wait loop ──
                        if getattr(sys, "frozen", False):
                            exe_name   = Path(sys.executable).name
                            exe_target = str(_run_dir / exe_name)
                        else:
                            exe_name   = None
                            exe_target = sys.executable

                        # ── 4. Write a tiny batch updater ─────────────────────
                        bat_path    = Path(tmp_dir) / "ch_updater.bat"
                        source_str  = str(source_dir)
                        run_dir_str = str(_run_dir)

                        # Fixed wait: simple timeout is more reliable than
                        # a tasklist loop racing against os._exit()
                        wait_secs = 5 if exe_name else 3

                        exe_stem = Path(exe_target).stem
                        bat_content = (
                            "@echo off\r\n"
                            "title CHSuite Updater\r\n"
                            "cls\r\n"
                            "echo ============================================\r\n"
                            "echo  CHSuite Portable Updater\r\n"
                            "echo ============================================\r\n"
                            "echo.\r\n"
                            "timeout /t 2 /nobreak >NUL 2>&1\r\n"
                            + f"xcopy /E /Y /I /Q \"{source_str}\\*\""
                              f" \"{run_dir_str}\\\" >NUL 2>&1\r\n"
                            + f"start \"\" \"{exe_target}\"\r\n"
                            + f"rd /S /Q \"{str(tmp_dir)}\" 2>NUL\r\n"
                            + "powershell -NoProfile -Command \""
                            f"$n='{exe_stem}';"
                            "$w=40;$p=0;"
                            "while($p-lt 95){"
                            "$f='#'*[int]($p*$w/100);"
                            "$e='-'*($w-$f.Length);"
                            "[Console]::Write([char]13+'  ['+$f+$e+'] '+[string]$p+'%%  ');"
                            "Start-Sleep -Milliseconds 80;"
                            "$p=[Math]::Min($p+(Get-Random -Minimum 1 -Maximum 3),95);"
                            "if(Get-Process $n -ErrorAction SilentlyContinue){$p=95}"
                            "};"
                            "while(!(Get-Process $n -ErrorAction SilentlyContinue)){Start-Sleep -Milliseconds 300};"
                            "[Console]::Write([char]13+'  ['+'#'*$w+'] 100%%  '+[char]10);"
                            "Start-Sleep -Milliseconds 500"
                            "\"\r\n"
                            + "del \"%~f0\"\r\n"
                        )
                        bat_path.write_text(bat_content, encoding="utf-8")

                        # ── 5. Launch batch in a new visible console ─────────────
                        subprocess.Popen(
                            ["cmd.exe", "/C", str(bat_path)],
                            creationflags=(
                                subprocess.CREATE_NEW_CONSOLE
                                | subprocess.CREATE_NEW_PROCESS_GROUP),
                        )

                        # ── 6. Quit CHSuite — the batch handles the restart ───
                        def _quit_for_update():
                            status_var.set("Update ready — restarting…")
                            status_lbl.config(fg=C["success"])
                            prog_lbl.config(text="")
                            # Hard-exit after a brief pause so the exe is
                            # fully unlocked before the batch runs xcopy
                            self.after(1200, lambda: (
                                self.destroy(),
                                os._exit(0)))
                        self.after(0, _quit_for_update)

                    except Exception as exc:
                        self.after(0, lambda e=exc: (
                            prog_bar.stop(),
                            prog_frame.pack_forget(),
                            win.geometry(f"390x230+{x}+{y}"),
                            status_var.set(f"Extract failed: {e}"),
                            status_lbl.config(fg=C["error"]),
                            close_btn.config(state="normal", text="Close",
                                             command=win.destroy)))
                threading.Thread(target=_extract, daemon=True).start()
            else:
                # ── Full installer: close CHSuite first, run installer via batch ──
                # The running .exe cannot be overwritten while it is alive.
                # Strategy: write a detached batch that (1) waits for this
                # process to exit, (2) runs the installer silently, then
                # (3) relaunches CHSuite from the install directory.
                status_var.set("Preparing installer…")
                status_lbl.config(fg=C["text_mid"])
                prog_frame.pack_forget()
                close_btn.config(state="disabled")

                def _launch_installer_batch():
                    try:
                        if getattr(sys, "frozen", False):
                            exe_name   = Path(sys.executable).name
                        else:
                            exe_name   = None

                        # After install, CHSuite.exe lives here:
                        relaunch_target = str(INSTALL_DIR / (exe_name or "CHSuite.exe"))
                        tmp_dir_str     = str(tmp_dir)
                        installer_path  = str(tmp_file)

                        wait_secs = 5 if exe_name else 3

                        bat_path = Path(tmp_dir) / "ch_install.bat"
                        bat_content = (
                            "@echo off\r\n"
                            "title CHSuite Updater\r\n"
                            "cls\r\n"
                            "echo ============================================\r\n"
                            "echo  CHSuite Full Install Updater\r\n"
                            "echo ============================================\r\n"
                            "echo.\r\n"
                            "timeout /t 2 /nobreak >NUL 2>&1\r\n"
                            + f"\"{installer_path}\" /S\r\n"
                            + "powershell -NoProfile -Command \""
                            f"$t='{relaunch_target}';"
                            "$w=40;$p=0;"
                            "while($p-lt 95){"
                            "$f='#'*[int]($p*$w/100);"
                            "$e='-'*($w-$f.Length);"
                            "[Console]::Write([char]13+'  ['+$f+$e+'] '+[string]$p+'%%  ');"
                            "Start-Sleep -Milliseconds 80;"
                            "$p=[Math]::Min($p+(Get-Random -Minimum 1 -Maximum 3),95);"
                            "if(Test-Path $t){$p=100}"
                            "};"
                            "while(!(Test-Path $t)){"
                            "$f='#'*[int](95*$w/100);"
                            "$e='-'*($w-$f.Length);"
                            "[Console]::Write([char]13+'  ['+$f+$e+'] 95%%  ');"
                            "Start-Sleep -Milliseconds 300"
                            "};"
                            "[Console]::Write([char]13+'  ['+'#'*$w+'] 100%%  '+[char]10);"
                            "Start-Sleep -Milliseconds 500"
                            "\"\r\n"
                            + f"if exist \"{relaunch_target}\" (\r\n"
                            + f"    start \"\" \"{relaunch_target}\"\r\n"
                            ") else (\r\n"
                            "    echo WARNING: Could not find CHSuite.exe after install.\r\n"
                            "    pause\r\n"
                            ")\r\n"
                            + f"rd /S /Q \"{tmp_dir_str}\" 2>NUL\r\n"
                            + "del \"%~f0\"\r\n"
                        )
                        bat_path.write_text(bat_content, encoding="utf-8")

                        subprocess.Popen(
                            ["cmd.exe", "/C", str(bat_path)],
                            creationflags=(
                                subprocess.CREATE_NEW_CONSOLE
                                | subprocess.CREATE_NEW_PROCESS_GROUP),
                        )

                        def _quit_for_installer():
                            status_var.set(
                                "Installer running — will relaunch when done…")
                            status_lbl.config(fg=C["success"])
                            # Hard-exit immediately so the installer can
                            # overwrite CHSuite.exe without a sharing violation
                            self.after(1000, lambda: (
                                self.destroy(),
                                os._exit(0)))
                        self.after(0, _quit_for_installer)

                    except Exception as exc:
                        self.after(0, lambda e=exc: (
                            status_var.set(f"Installer failed: {e}"),
                            status_lbl.config(fg=C["error"]),
                            close_btn.config(state="normal", text="Close",
                                             command=win.destroy)))
                threading.Thread(target=_launch_installer_batch, daemon=True).start()

        def _do_install(asset_url, asset_name):
            install_btn.pack_forget()
            close_btn.config(text="Cancel", command=lambda: _cancel.set())
            prog_frame.pack(anchor="w", fill="x", pady=(8, 0))
            win.geometry(f"390x290+{x}+{y}")
            status_var.set("Downloading update…")
            status_lbl.config(fg=C["text_mid"])

            tmp_dir  = Path(tempfile.mkdtemp())
            tmp_file = tmp_dir / asset_name

            def _download():
                try:
                    req = urllib.request.Request(
                        asset_url,
                        headers={"User-Agent": "CHSuite-Updater/7.1"})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        total      = int(resp.headers.get("Content-Length", 0))
                        downloaded = 0
                        with open(tmp_file, "wb") as fh:
                            while True:
                                if _cancel.is_set():
                                    self.after(0, lambda: (
                                        status_var.set("Update cancelled."),
                                        status_lbl.config(fg=C["text_dim"]),
                                        prog_frame.pack_forget(),
                                        win.geometry(f"390x230+{x}+{y}"),
                                        close_btn.config(text="Close",
                                                         command=win.destroy)))
                                    return
                                buf = resp.read(65536)
                                if not buf:
                                    break
                                fh.write(buf)
                                downloaded += len(buf)
                                if total:
                                    pct = int(downloaded * 100 / total)
                                    mb  = downloaded / 1_048_576
                                    self.after(0, lambda p=pct, m=mb: (
                                        prog_bar.config(value=p),
                                        prog_lbl.config(
                                            text=f"{m:.1f} MB  ({p}%)")))
                except Exception as exc:
                    self.after(0, lambda: (
                        status_var.set(f"Download failed: {exc}"),
                        status_lbl.config(fg=C["error"]),
                        prog_frame.pack_forget(),
                        win.geometry(f"390x230+{x}+{y}"),
                        close_btn.config(text="Close", command=win.destroy)))
                    return
                self.after(0, lambda: _apply(tmp_file, tmp_dir))

            threading.Thread(target=_download, daemon=True).start()

        def _fetch():
            _beta_on = bool(self._cfg.get("beta_updates_enabled", False))
            # When beta is enabled, fetch all releases and pick the newest
            # pre-release.  Otherwise use the /releases/latest shortcut.
            _fetch_url = (
                "https://api.github.com/repos/iamjrmh/CHSuite/releases"
                if _beta_on else API_URL)
            try:
                import ssl as _ssl, socket as _socket
                req = urllib.request.Request(
                    _fetch_url,
                    headers={"User-Agent": "CHSuite-UpdateChecker/7.1",
                             "Accept": "application/vnd.github+json"})
                # macOS: the SSL handshake can hang indefinitely if the system
                # cert store isn't set up (e.g. PyInstaller bundle without
                # certifi).  Set a hard socket deadline first, then try a
                # verified context and fall back to unverified on cert errors.
                _old_timeout = _socket.getdefaulttimeout()
                _socket.setdefaulttimeout(10)
                try:
                    _ctx = _ssl.create_default_context()
                    with urllib.request.urlopen(req, timeout=10,
                                                context=_ctx) as resp:
                        raw = json.loads(resp.read().decode("utf-8"))
                except _ssl.SSLCertVerificationError:
                    # Cert bundle not available (common in frozen macOS builds).
                    # Retry without certificate verification.
                    _ctx_noverify = _ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=10,
                                                context=_ctx_noverify) as resp:
                        raw = json.loads(resp.read().decode("utf-8"))
                finally:
                    _socket.setdefaulttimeout(_old_timeout)
            except Exception as exc:
                self.after(0, lambda: (
                    status_var.set(f"Could not reach GitHub: {exc}"),
                    status_lbl.config(fg=C["error"]),
                    lat_lbl.config(text="Latest:      —")))
                return

            # When beta mode is active, raw is a list; pick the newest pre-release.
            # Fall back to the newest release of any kind if no pre-release exists.
            if _beta_on and isinstance(raw, list):
                pre_releases = [r for r in raw if r.get("prerelease", False)]
                data = (pre_releases[0] if pre_releases
                        else (raw[0] if raw else {}))
            else:
                data = raw

            tag    = data.get("tag_name", "").lstrip("vV")
            assets = data.get("assets", [])
            _is_prerelease = data.get("prerelease", False)

            # Pick the right asset for this install type
            if _IS_LINUX:
                # Linux: use fixed direct-download URLs — ignore the assets list.
                # In beta mode, point at the specific tag rather than /latest.
                if _beta_on and tag:
                    _base = f"https://github.com/iamjrmh/CHSuite/releases/download/v{tag}"
                else:
                    _base = "https://github.com/iamjrmh/CHSuite/releases/latest/download"
                if is_portable:
                    _linux_url  = f"{_base}/CHSuiteLinux.zip"
                    _linux_name = "CHSuiteLinux.zip"
                else:
                    _linux_url  = f"{_base}/CHSuiteLinux.AppImage"
                    _linux_name = "CHSuiteLinux.AppImage"
                asset = {"browser_download_url": _linux_url, "name": _linux_name}
            elif _IS_MAC:
                # macOS: prefer .dmg (auto-mounts via hdiutil and copies the
                # .app bundle — no sudo needed).  Fall back to .pkg if no
                # .dmg is present (pkg install requires sudo installer).
                asset = (next((a for a in assets
                               if a["name"].lower().endswith(".dmg")), None) or
                         next((a for a in assets
                               if a["name"].lower().endswith(".pkg")), None))
            elif is_portable:
                asset = next(
                    (a for a in assets
                     if "portable" in a["name"].lower()
                     or a["name"].lower().endswith(".zip")), None)
            else:
                asset = next(
                    (a for a in assets
                     if "setup"     in a["name"].lower()
                     or "installer" in a["name"].lower()
                     or a["name"].lower().endswith(".exe")), None)

            def _ver_tuple(v: str):
                """Convert a version string like '3.1.2' into a comparable tuple."""
                try:
                    # Strip any non-numeric suffix (e.g. "-PTB1") for comparison
                    import re as _re
                    clean = _re.split(r"[^0-9.]", v.strip())[0]
                    return tuple(int(x) for x in clean.split(".") if x)
                except ValueError:
                    return (0,)

            def _show():
                _tag_display = f"v{tag}" + ("  [Beta]" if _is_prerelease else "")
                lat_lbl.config(text=f"Latest:       {_tag_display}",
                               fg=C["text_mid"])
                remote = _ver_tuple(tag)
                local  = _ver_tuple(CURRENT)
                if remote <= local:
                    _msg = ("✓  You're up to date!"
                            if not _is_prerelease else
                            "✓  You're already on the latest beta!")
                    status_var.set(_msg)
                    status_lbl.config(fg=C["success"])
                elif asset:
                    mode = "portable" if is_portable else "full install"
                    _channel = "beta " if _is_prerelease else ""
                    status_var.set(
                        f"{_channel}v{tag} is available  ·  {mode}")
                    status_lbl.config(fg=C["warn"])
                    install_btn.command = lambda: _do_install(
                            asset["browser_download_url"], asset["name"])
                    install_btn.pack(side="right", padx=(8, 0))
                else:
                    status_var.set(
                        f"v{tag} is available — no matching asset found on GitHub.")
                    status_lbl.config(fg=C["warn"])
            self.after(0, _show)

        threading.Thread(target=_fetch, daemon=True).start()

    # ── Launch Clone Hero ─────────────────────────────────────────────────────
    def _reset_to_default(self):
        """Delete all CHSuite-created JSON files, restoring a fresh-install state."""
        json_files = [
            CONFIG_FILE,        # chsuite_config.json
            PROFILES_FILE,      # ch_bg_profiles.json
            _NG_PROFILES_FILE,  # ch_notegen_profiles.json
            _NG_CONFIG_FILE,    # ch_notegen_config.json
        ]

        # Only list files that actually exist
        existing = [f for f in json_files if f.is_file()]
        if not existing:
            messagebox.showinfo(
                "Reset to Default",
                "No CHSuite data files found — already at factory defaults.",
                parent=self,
            )
            return

        file_list = "\n".join(f"  • {f.name}" for f in existing)
        confirmed = messagebox.askyesno(
            "Reset to Default",
            f"This will permanently delete the following CHSuite data files "
            f"and restore factory defaults:\n\n{file_list}\n\n"
            f"The application will close and must be restarted.\n\n"
            f"Are you sure?",
            icon="warning",
            parent=self,
        )
        if not confirmed:
            return

        errors = []
        for f in existing:
            try:
                f.unlink()
            except Exception as exc:
                errors.append(f"{f.name}: {exc}")

        if errors:
            messagebox.showerror(
                "Reset to Default",
                "Some files could not be deleted:\n\n" + "\n".join(errors),
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Reset to Default",
                "All CHSuite data files have been deleted.\n"
                "Please restart the application.",
                parent=self,
            )

        # Close without saving (avoids re-writing the deleted files)
        if hasattr(self, "_drpc"):
            self._drpc.close()
        self.destroy()

    # ── Simulate crash (F12 — developer only) ────────────────────────────────
    def _simulate_crash(self):
        try:
            raise RuntimeError("Simulated crash triggered by developer (F12)")
        except Exception:
            fpath = _write_crash_log(sys.exc_info(), simulated=True)
            if fpath:
                messagebox.showinfo(
                    "Crash Simulated",
                    f"Crash log written to:\n{fpath}",
                    parent=self)
            else:
                messagebox.showerror(
                    "Crash Simulated",
                    "Could not write crash log — check console output.",
                    parent=self)

    # ── Close ─────────────────────────────────────────────────────────────────
    def _on_close(self):
        if hasattr(self, "_drpc"):
            self._drpc.close()
        _save_json(CONFIG_FILE, self._cfg)
        _save_profiles(self._profiles)
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def main():
    try:
        _run_main()
    except Exception:
        fpath = _write_crash_log(sys.exc_info(), simulated=False)
        msg = f"CHSuite encountered an unhandled error and must close."
        if fpath:
            msg += f"\n\nCrash log saved to:\n{fpath}"
        try:
            import tkinter as _tk
            _r = _tk.Tk(); _r.withdraw()
            from tkinter import messagebox as _mb
            _mb.showerror("CHSuite Crashed", msg)
            _r.destroy()
        except Exception:
            print(msg)
        sys.exit(1)


def _run_main():
    if sys.platform == "win32":
        import ctypes, ctypes.wintypes
        try:
            # ── Hide console window when running from source ──────────────────
            if not getattr(sys, "frozen", False):
                ctypes.windll.user32.ShowWindow(
                    ctypes.windll.kernel32.GetConsoleWindow(), 0)

            kernel32 = ctypes.windll.kernel32

            # ── HIGH_PRIORITY_CLASS: more CPU time for the UI thread ──────────
            # 0x00000080 = HIGH_PRIORITY_CLASS
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00000080)

            # ── 1 ms system timer resolution ──────────────────────────────────
            # Windows 10 defaults to 15.6 ms, meaning the tkinter event loop
            # can only fire ~64×/sec — exactly why dragging feels sluggish.
            # Windows 11 already defaults to ~0.5 ms; this call is a no-op there.
            ctypes.WinDLL("winmm").timeBeginPeriod(1)

            # ── Per-Monitor v2 DPI awareness ──────────────────────────────────
            # Without this, DWM scales the window bitmap on Win10 HiDPI screens,
            # adding a compositing pass on every frame during a drag.
            try:
                # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (-4), Win10 1703+
                ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
            except Exception:
                try:
                    # PROCESS_PER_MONITOR_DPI_AWARE (2), Win8.1+
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)
                except Exception:
                    ctypes.windll.user32.SetProcessDPIAware()

            # ── Disable window ghosting ───────────────────────────────────────
            # Stops Windows from drawing the "Not Responding" translucent
            # overlay, which triggers an extra DWM compositing pass mid-drag.
            ctypes.windll.user32.DisableProcessWindowsGhosting()

        except Exception:
            pass

    CHSuite().mainloop()


if __name__ == "__main__":
    main()