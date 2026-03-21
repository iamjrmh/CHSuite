"""
CHSuite  by JURMR  v2.0
=======================
All-in-one Clone Hero utility suite.

  • CHMenuChanger  — swap in-game menu backgrounds via UnityPy
  • CHNameGen      — gradient / per-letter Clone Hero name tags
  • CHNoteGen      — note/color profile editor with live highway preview
  • CHCleaner      — parse badsongs.txt and delete ERROR folders
  • CHPatcher      — patch the launcher so it stops resetting game files

Dependencies (CHMenuChanger tab only):
    pip install Pillow UnityPy

Python 3.9+
"""

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
import datetime
from pathlib import Path

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
)

FT  = ("Segoe UI", 10)
FTB = ("Segoe UI", 10, "bold")
FTS = ("Segoe UI", 8)
FTH = ("Segoe UI", 13, "bold")
FTT = ("Segoe UI", 20, "bold")
FTM = ("Consolas", 9)
FT_LABEL = ("Segoe UI", 9)

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
             font=("Segoe UI", 11), bg=C["bg"], fg=C["text"], pady=20).pack()
    tk.Label(_pr, text="Running pip, please wait…",
             font=("Consolas", 9), bg=C["bg"], fg=C["text_dim"]).pack()
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
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

CONFIG_FILE   = _app_dir() / "chsuite_config.json"
PROFILES_FILE = _app_dir() / "ch_bg_profiles.json"
SCAN_LOG_FILE = _app_dir() / "ch_bg_scan.log"

# ── CH Launcher registry path ─────────────────────────────────────────────────
_INSTALLS_FILE = (
    Path(os.environ.get("APPDATA", "")) /
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
    "bgchanger":   "CHMenuChanger",
    "namegen":     "CHNameGen",
    "notegen":     "CHNoteGen",
    "cleaner":     "CHCleaner",
    "patcher":     "CHPatcher",
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

class RoundedButton(tk.Canvas):
    """Canvas-based rounded button with hover and disabled states."""
    def __init__(self, parent, text, command, bg_color, hover_color,
                 height=42, radius=10, text_font=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.command     = command
        self.bg_color    = bg_color
        self.hover_color = hover_color
        self.text        = text
        self.enabled     = True
        self.radius      = radius
        self.text_font   = text_font or ("Segoe UI", 10, "bold")
        self.config(bg=C["bg"], height=height, cursor="hand2")
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Configure>", lambda e: self.draw())
        self.draw()

    def draw(self, hover=False):
        self.delete("all")
        color = self.hover_color if (hover and self.enabled) else self.bg_color
        if not self.enabled:
            color = "#1e2030"
        w = self.winfo_width() if self.winfo_width() > 1 else 200
        h = self.winfo_height() if self.winfo_height() > 1 else 42
        self._rounded_rect(4, 4, w - 4, h - 4, self.radius, fill=color, outline="")
        fg = C["text_dim"] if not self.enabled else C["text"]
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
        self.config(cursor="hand2" if enabled else "arrow")
        self.draw()


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
                     font=("Segoe UI", 10, "bold"),
                     fg=C["warn"], bg=C["card"],
                     justify="left").pack(anchor="w", pady=(0, 6))

        tk.Label(inner, text=self._text,
                 font=("Segoe UI", 9),
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


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION 1 — BG CHANGER (CHMenuChanger)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_PROFILE_NAME = "Default (Original)"
DEFAULT_DATA = str(Path.home() / "Documents" / "Clone Hero" / "Clone Hero_Data")

def _get_default_data():
    """Return the best known data path: saved config value, or the hardcoded fallback."""
    cfg = _load_json(CONFIG_FILE, {})
    return cfg.get("default_data_path", DEFAULT_DATA)

BACKGROUNDS = [
    "Black", "Spray", "Pastel Burst", "Groovy", "Grains",
    "Blue Rays", "Alien", "Autumn", "Light", "Dark",
    "Classic", "Surfer", "SurferAlt", "Rainbow", "Animated",
    "Logo_Transparent",
]
EXACT_ASSET_FILE = {"Logo_Transparent": "globalgamemanagers.assets"}

def required_size(name):
    return (2030, 1328) if name == "Logo_Transparent" else (1920, 1080)

def exact_match_required(name):
    return name == "Logo_Transparent"

def _norm(s):
    return re.sub(r"[\s_\-]", "", s).lower()


class AssetManager:
    BACKUP_DIR_NAME = "_CH_BG_Backups"

    def __init__(self, data_dir):
        self.data_dir = str(data_dir)
        self._data    = {}
        self._env_map = {}
        self._envs    = {}
        self._dirty   = set()
        try:
            with open(SCAN_LOG_FILE, "w", encoding="utf-8") as _lf:
                _lf.write("CHSuite scan log -- {}\ndata_dir: {}\n\n".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data_dir))
        except Exception:
            pass
        self._scan()

    def _scan(self):
        data_dir = Path(self.data_dir)
        candidates = []
        for f in data_dir.iterdir():
            if not f.is_file():
                continue
            lo = f.name.lower()
            if f.suffix.lower() == ".assets":
                candidates.append(f)
            elif lo == "globalgamemanagers":
                candidates.append(f)

        def sort_key(p):
            n = p.name.lower()
            if n == "sharedassets1.assets":       return 0
            if n == "globalgamemanagers.assets":  return 1
            if n == "globalgamemanagers":         return 2
            if "sharedassets" in n:               return 3
            if "resources" in n:                  return 4
            return 5
        candidates.sort(key=sort_key)
        for fpath in candidates:
            self._load_file(fpath)

    def _load_file(self, fpath):
        key = str(fpath)
        if key in self._envs:
            return
        try:
            env = UnityPy.load(key)
            self._envs[key] = env
            count = 0
            for obj in env.objects:
                if obj.type.name == "Texture2D":
                    try:
                        d = obj.read()
                        n = getattr(d, "m_Name", None) or getattr(d, "name", None)
                        if n and n not in self._data:
                            self._data[n]    = d
                            self._env_map[n] = (env, key)
                            count += 1
                    except Exception as ex:
                        _log(f"[_load_file] read error in {Path(fpath).name}: {ex}")
            if count:
                _log(f"[scan] {Path(fpath).name} -> {count} texture(s)")
        except Exception as e:
            _log(f"[scan] skipped {Path(fpath).name}: {e}")

    def texture_names(self):
        return list(self._data.keys())

    def source_file(self, asset_name):
        entry = self._env_map.get(asset_name)
        return entry[1] if entry else None

    def find_for_bg(self, bg):
        required_file = EXACT_ASSET_FILE.get(bg)
        if required_file:
            req_lo = required_file.lower()
            for name, (env, fpath) in self._env_map.items():
                if Path(fpath).name.lower() != req_lo:
                    continue
                if _norm(name) == _norm(bg) or _norm(bg) in _norm(name):
                    return name
            return None
        nb    = _norm(bg)
        names = list(self._data.keys())
        for n in names:
            if _norm(n) == nb: return n
        for n in names:
            if nb in _norm(n): return n
        for n in names:
            nn = _norm(n)
            if len(nn) >= 3 and nn in nb: return n
        return None

    def export_image(self, asset_name):
        d = self._data.get(asset_name)
        if d is None:
            return None, f"Asset '{asset_name}' not in cache"
        errors = []
        try:
            img = d.image
            if img is not None:
                return img.convert("RGBA"), None
            errors.append("Approach 1 (.image): returned None")
        except Exception as e:
            errors.append(f"Approach 1 (.image): {e}")
        try:
            import texture2ddecoder as _t2d
            from UnityPy.enums import TextureFormat as TF
            fmt = d.m_TextureFormat; w = d.m_Width; h = d.m_Height
            data = bytes(d.image_data) if d.image_data else b""
            if not data:
                sd = getattr(d, "m_StreamData", None)
                if sd is not None:
                    res_path = getattr(sd, "path", None)
                    offset   = getattr(sd, "offset", 0)
                    size     = getattr(sd, "size",   0)
                    if res_path and size > 0:
                        entry     = self._env_map.get(asset_name)
                        asset_dir = str(Path(entry[1]).parent) if entry else self.data_dir
                        clean_path = res_path.split("/")[-1] if "/" in res_path else res_path
                        full_res   = os.path.join(asset_dir, clean_path)
                        if os.path.isfile(full_res):
                            with open(full_res, "rb") as rf:
                                rf.seek(offset); data = rf.read(size)
            if data:
                _BC = {
                    TF.DXT1:  (_t2d.decode_bc1, "BGRA"), TF.DXT1Crunched: (_t2d.decode_bc1, "BGRA"),
                    TF.DXT5:  (_t2d.decode_bc3, "BGRA"), TF.DXT5Crunched: (_t2d.decode_bc3, "BGRA"),
                    TF.BC7:   (_t2d.decode_bc7, "BGRA"), TF.BC6H: (_t2d.decode_bc6, "BGRA"),
                    TF.ETC_RGB4:  (_t2d.decode_etc1,   "BGRA"),
                    TF.ETC2_RGB:  (_t2d.decode_etc2,   "BGRA"),
                    TF.ETC2_RGBA8:(_t2d.decode_etc2a8, "BGRA"),
                }
                _RAW = {
                    TF.RGBA32: ("RGBA","raw","RGBA"), TF.RGB24: ("RGBA","raw","RGB"),
                    TF.BGRA32: ("RGBA","raw","BGRA"), TF.ARGB32:("RGBA","raw","ARGB"),
                }
                if fmt in _BC:
                    fn, mode = _BC[fmt]
                    img = Image.frombytes("RGBA",(w,h), fn(data,w,h),"raw",mode)
                    return img.transpose(Image.FLIP_TOP_BOTTOM), None
                elif fmt in _RAW:
                    out_mode, dec, raw_mode = _RAW[fmt]
                    img = Image.frombytes(out_mode,(w,h),data,dec,raw_mode)
                    return img.convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM), None
        except Exception as e:
            errors.append(f"Approach 2: {e}")
        return None, " | ".join(errors)

    def import_image(self, asset_name, pil):
        d = self._data.get(asset_name)
        if d is None:
            return False
        rgba = pil.convert("RGBA")
        try:
            if hasattr(d, "set_image"):
                d.set_image(rgba); d.save()
                self._dirty.add(asset_name)
                return True
        except Exception as e:
            _log(f"[WRITE FAIL] set_image '{asset_name}': {e}")
        try:
            d.image = rgba; d.save()
            self._dirty.add(asset_name)
            return True
        except Exception as e:
            _log(f"[WRITE FAIL] image= setter '{asset_name}': {e}")
            return False

    def backup_dir(self):
        return os.path.join(self.data_dir, self.BACKUP_DIR_NAME)

    def needs_backup(self):
        bd = self.backup_dir()
        return [fp for fp in self._envs
                if not os.path.isfile(os.path.join(bd, Path(fp).name))]

    def has_full_backup(self):
        return len(self.needs_backup()) == 0

    def create_backups(self):
        bd = self.backup_dir()
        os.makedirs(bd, exist_ok=True)
        created, errors = [], []
        for fpath in self.needs_backup():
            dest = os.path.join(bd, Path(fpath).name)
            try:
                shutil.copy2(fpath, dest)
                created.append(dest)
            except Exception as e:
                errors.append(f"{Path(fpath).name}: {e}")
        return created, errors

    def save_modified(self):
        dirty_files = {}
        for name in self._dirty:
            entry = self._env_map.get(name)
            if entry:
                env, fpath = entry
                dirty_files[fpath] = env
        if not dirty_files:
            return [], ["No textures were imported - nothing to save."]
        saved, errors = [], []
        for fpath, env in dirty_files.items():
            fname = Path(fpath).name
            try:
                data = env.file.save()
                with open(fpath, "wb") as f:
                    f.write(data)
                saved.append(fpath)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        if saved:
            self._reload_saved(saved)
        return saved, errors

    def _reload_saved(self, saved_paths):
        for fpath in saved_paths:
            try:
                env = UnityPy.load(fpath)
                self._envs[fpath] = env
                for obj in env.objects:
                    if obj.type.name == "Texture2D":
                        try:
                            d = obj.read()
                            n = getattr(d, "m_Name", None) or getattr(d, "name", None)
                            if n and n in self._data:
                                self._data[n] = d
                                self._env_map[n] = (env, fpath)
                        except Exception:
                            pass
            except Exception as e:
                print("[reload]", Path(fpath).name, e)
        self._dirty.clear()


def _blank_profile(name):
    return {"name": name, "data_path": _get_default_data(), "replacements": {}}

def _load_profiles():
    d = _load_json(PROFILES_FILE, {})
    return d if isinstance(d, dict) else {}

def _save_profiles(p):
    _save_json(PROFILES_FILE, p)


class SetupDialog:
    """
    First-launch dialog.  Asks the user to locate their Clone Hero install
    folder, then derives the _Data path automatically and saves it to config.

    After the dialog closes, call .result to get the chosen data path (str),
    or None if the user skipped.
    """

    def __init__(self, root: tk.Tk):
        self.result = None   # Clone Hero_Data path

        self.win = tk.Toplevel(root)
        self.win.title("Welcome to CHSuite")
        self.win.configure(bg=C["bg"])
        self.win.resizable(False, False)
        self.win.grab_set()
        # Closing the window == skipping setup
        self.win.protocol("WM_DELETE_WINDOW", self._skip)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=C["panel"]); hdr.pack(fill="x")
        hi  = tk.Frame(hdr, bg=C["panel"], padx=28, pady=18); hi.pack(fill="x")
        tk.Label(hi, text="CHSuite", font=("Segoe UI", 22, "bold"),
                 bg=C["panel"], fg=C["text"]).pack(side="left")
        tk.Label(hi, text="  by JURMR", font=("Segoe UI", 13),
                 bg=C["panel"], fg=C["accent"]).pack(side="left", pady=(8, 0))

        # Patch status badge – top-right, updated after Confirm
        self._patch_badge = tk.Label(
            hi, text="", font=("Segoe UI", 9, "bold"),
            bg=C["panel"], fg=C["text_dim"], padx=10, pady=4)
        self._patch_badge.pack(side="right", padx=(0, 4))
        self._update_patch_badge(None)

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self.win, bg=C["bg"], padx=28, pady=22)
        body.pack(fill="both")

        tk.Label(body,
                 text="Select your Clone Hero installation folder to get started.",
                 font=("Segoe UI", 11), fg=C["text"], bg=C["bg"],
                 justify="left").pack(anchor="w", pady=(0, 18))

        # Path picker card
        pick_card = tk.Frame(body, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=18, pady=16)
        pick_card.pack(fill="x", pady=(0, 10))

        tk.Label(pick_card, text="CLONE HERO INSTALL FOLDER",
                 font=("Segoe UI", 8, "bold"), fg=C["text_dim"],
                 bg=C["card"]).pack(anchor="w", pady=(0, 8))

        row = tk.Frame(pick_card, bg=C["card"]); row.pack(fill="x")
        self._path_var = tk.StringVar()
        self._path_entry = ttk.Entry(row, textvariable=self._path_var,
                                     font=FTM, style="DE.TEntry")
        self._path_entry.pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse…", command=self._browse,
                  bg=C["accent_dim"], fg=C["text"], relief="flat",
                  font=FT, padx=10, pady=4, cursor="hand2").pack(side="left", padx=(8, 0))

        # Derived path preview
        self._derived_lbl = tk.Label(pick_card, text="",
                                      font=FTM, fg=C["text_dim"],
                                      bg=C["card"], anchor="w")
        self._derived_lbl.pack(fill="x", pady=(10, 0))
        self._path_var.trace_add("write", self._on_path_change)

        # Try to pre-fill with the default Documents location if it exists
        default = str(Path.home() / "Documents" / "Clone Hero")
        if os.path.isdir(default):
            self._path_var.set(default)

        # Info blurb
        info_card = tk.Frame(body, bg=C["card2"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=18, pady=14)
        info_card.pack(fill="x", pady=(4, 0))
        tk.Label(info_card,
                 text="This is the folder that contains \"Clone Hero.exe\".\n"
                      "CHSuite will look for game assets inside the \"Clone Hero_Data\"\n"
                      "subfolder found within it.",
                 font=FT, fg=C["text_mid"], bg=C["card2"],
                 justify="left").pack(anchor="w")

        # ── Footer ────────────────────────────────────────────────────────────
        foot = tk.Frame(self.win, bg=C["panel"], padx=24, pady=14)
        foot.pack(fill="x")
        tk.Label(foot, text="Made by JURMR", font=FTS,
                 bg=C["panel"], fg=C["text_dim"]).pack(side="left")
        tk.Button(foot, text="Skip",
                  command=self._skip,
                  bg=C["border"], fg=C["text_dim"], relief="flat",
                  font=FT, padx=14, pady=6, cursor="hand2").pack(side="right", padx=(8, 0))
        self._confirm_btn = tk.Button(foot, text="Confirm  →",
                                       command=self._confirm,
                                       bg=C["accent"], fg="white", relief="flat",
                                       font=FTB, padx=18, pady=6, cursor="hand2")
        self._confirm_btn.pack(side="right")

        # Centre on root
        self.win.update_idletasks()
        rw = root.winfo_width()  or 900
        rh = root.winfo_height() or 700
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        dw = self.win.winfo_reqwidth()
        dh = self.win.winfo_reqheight()
        self.win.geometry(f"+{rx+(rw-dw)//2}+{ry+(rh-dh)//2}")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _browse(self):
        p = filedialog.askdirectory(
            title="Select your Clone Hero install folder",
            initialdir=self._path_var.get() or str(Path.home()))
        if p:
            self._path_var.set(p)

    def _on_path_change(self, *_):
        p = self._path_var.get().strip()
        data_path = os.path.join(p, "Clone Hero_Data") if p else ""
        if p and os.path.isdir(data_path):
            self._derived_lbl.config(
                text=f"  Data folder found:  {data_path}",
                fg=C["success"])
            self._confirm_btn.config(state="normal", bg=C["accent"])
        elif p:
            self._derived_lbl.config(
                text=f"  Derived path:  {data_path}  (not found yet)",
                fg=C["warn"])
            self._confirm_btn.config(state="normal", bg=C["accent"])
        else:
            self._derived_lbl.config(text="", fg=C["text_dim"])

    def _confirm(self):
        p = self._path_var.get().strip()
        if not p:
            messagebox.showerror("No folder selected",
                                 "Please choose your Clone Hero install folder.",
                                 parent=self.win)
            return
        data_path = os.path.join(p, "Clone Hero_Data")
        if not os.path.isdir(data_path):
            if not messagebox.askyesno(
                    "Folder not found",
                    f"\"Clone Hero_Data\" was not found inside:\n{p}\n\n"
                    "This might not be the right folder.  Continue anyway?",
                    parent=self.win):
                return

        # Kill the launcher if running, then patch after it exits
        if _launcher_is_running():
            if _kill_launcher():
                _log("[launcher-patch] Launcher force-closed before patching")
                self.win.after(600, lambda: self._do_patch(p, data_path))
                return
            else:
                _log("[launcher-patch] Launcher detected but could not be killed")

        self._do_patch(p, data_path)

    def _do_patch(self, p: str, data_path: str):
        """Run patch, show badge, auto-close."""
        self.result = data_path
        msg     = _silent_patch_as_manual(p)
        success = msg.startswith("Launcher patch applied")
        _log("[launcher-patch] " + msg)
        self._update_patch_badge(success)
        self.win.after(900, self.win.destroy)

    def _update_patch_badge(self, success):
        """None = not yet attempted, True = patched, False = failed."""
        if success is None:
            self._patch_badge.config(text="◦  Not Patched", fg=C["text_dim"])
        elif success:
            self._patch_badge.config(text="✓  Patched",     fg=C["success"])
        else:
            self._patch_badge.config(text="✗  Not Patched", fg=C["error"])

    def _skip(self):
        self.result = None
        self.win.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION 2 — NAME GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

__namegen_version__ = "1.1.1"
GITHUB_REPO_OWNER   = "iamjrmh"
GITHUB_REPO_NAME    = "CloneHeroColorGen"
GITHUB_RELEASE_API  = (
    f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
)
UPDATE_ZIP_FILENAME = "CloneHeroColorGen.zip"


def _ng_hex_to_rgb_f(hex_color: str) -> tuple:
    """Pure-Python hex → (r, g, b) in 0.0–1.0 range (for gradient interpolation)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def _ng_rgb_f_to_hex(rgb: tuple) -> str:
    """Pure-Python (r, g, b) 0.0–1.0 → '#RRGGBB' string."""
    return "#{:02X}{:02X}{:02X}".format(
        min(255, max(0, int(round(rgb[0] * 255)))),
        min(255, max(0, int(round(rgb[1] * 255)))),
        min(255, max(0, int(round(rgb[2] * 255))))
    )

def _interpolate_colors(hex_colors: list, steps: int) -> list:
    rgb_colors = [_ng_hex_to_rgb_f(c) for c in hex_colors if c]
    if len(rgb_colors) < 2:
        raise ValueError("At least a start and end color are required.")
    segments = len(rgb_colors) - 1
    steps_per_seg = steps // segments
    extra = steps % segments
    result = []
    for i in range(segments):
        start = rgb_colors[i]; end = rgb_colors[i + 1]
        cur = steps_per_seg + (1 if i < extra else 0)
        for j in range(cur):
            t = j / max(cur - 1, 1)
            r = start[0] + (end[0] - start[0]) * t
            g = start[1] + (end[1] - start[1]) * t
            b = start[2] + (end[2] - start[2]) * t
            result.append(_ng_rgb_f_to_hex((r, g, b)))
    return result[:steps]

def _generate_gradient_name(name, colors, bold=False, italic=False,
                             underline=False, strike=False,
                             size=None, spacing=None):
    gradient = _interpolate_colors(colors, len(name))
    segments = [f"<color={c}>{ch}</color>" for c, ch in zip(gradient, name)]
    styled = "".join(segments)
    if bold:      styled = f"<b>{styled}</b>"
    if italic:    styled = f"<i>{styled}</i>"
    if underline: styled = f"<u>{styled}</u>"
    if strike:    styled = f"<s>{styled}</s>"
    if size:      styled = f"<size={size}>{styled}</size>"
    if spacing:   styled = f"<cspace={spacing}>{styled}</cspace>"
    return styled, gradient

def _generate_individual_name(letters_data, global_size=None, global_spacing=None):
    segments = []; colors = []
    for ld in letters_data:
        char = ld["char"]; color = ld["color"]
        if not color.startswith("#"): color = "#" + color
        sc = f"<color={color}>{char}</color>"
        if ld["bold"]:      sc = f"<b>{sc}</b>"
        if ld["italic"]:    sc = f"<i>{sc}</i>"
        if ld["underline"]: sc = f"<u>{sc}</u>"
        if ld["strike"]:    sc = f"<s>{sc}</s>"
        segments.append(sc); colors.append(color)
    result = "".join(segments)
    if global_size:    result = f"<size={global_size}>{result}</size>"
    if global_spacing: result = f"<cspace={global_spacing}>{result}</cspace>"
    return result, colors




# ──────────────────────────────────────────────────────────────────────────────
#  SECTION 3 — NOTEGEN  (ported from CHNoteGen by JURMR)
# ──────────────────────────────────────────────────────────────────────────────

# Storage paths for NoteGen (alongside the exe / script)
_NG_PROFILES_FILE = _app_dir() / "ch_notegen_profiles.json"
_NG_CONFIG_FILE   = _app_dir() / "ch_notegen_config.json"
_NG_DEFAULT_INI   = _app_dir() / "DefaultColors.ini"
_NG_IMAGES_DIR    = _app_dir() / "Images"
_NG_DEFAULT_PROFILE_NAME = "Default (Read-Only)"

_NOTE_FILE_MAP = [
    ("green",  "note_green",  "Green.png"),
    ("red",    "note_red",    "Red.png"),
    ("yellow", "note_yellow", "Yellow.png"),
    ("blue",   "note_blue",   "Blue.png"),
    ("orange", "note_orange", "Orange.png"),
]
_TEMPLATE_NAMES = ["grayscale metallic.png", "MonoNote.png", "monenote.png"]
_SECTION_ORDER  = ["sixfret", "drums", "other", "guitar"]

# ── Default colours ───────────────────────────────────────────────────────────

_NG_DEFAULT_COLORS: dict = {
    "guitar": {
        "striker_base_orange":"#FFFFFF","striker_base_blue":"#FFFFFF",
        "striker_base_yellow":"#FFFFFF","striker_base_red":"#FFFFFF",
        "striker_base_green":"#FFFFFF",
        "striker_head_light_open":"#FFCE86","striker_head_light_orange":"#FFB300",
        "striker_head_light_blue":"#0089FF","striker_head_light_yellow":"#FFFF00",
        "striker_head_light_red":"#FF0000","striker_head_light_green":"#00FF00",
        "striker_head_cover_orange":"#FFB300","striker_head_cover_blue":"#0089FF",
        "striker_head_cover_yellow":"#FFFF00","striker_head_cover_red":"#FF0000",
        "striker_head_cover_green":"#00FF00",
        "striker_cover_orange":"#FFB300","striker_cover_blue":"#0089FF",
        "striker_cover_yellow":"#FFFF00","striker_cover_red":"#FF0000",
        "striker_cover_green":"#00FF00",
        "sustain_sp_active":"#00FFFF","sustain_sp_phrase_active":"#00FFFF",
        "sustain_sp_phrase":"#00FFFF","sustain_open":"#DB33F9",
        "sustain_orange":"#FFD23B","sustain_blue":"#00C5FF",
        "sustain_yellow":"#FFFF00","sustain_red":"#FF0000","sustain_green":"#00FF00",
        "note_anim_sp_active":"#51FFFF","note_anim_sp_phrase_active":"#FFFFFF",
        "note_anim_sp_phrase":"#51FFFF","note_anim_open":"#FFFFFF",
        "note_anim_orange":"#FFBE28","note_anim_blue":"#77D1FF",
        "note_anim_yellow":"#FFFF57","note_anim_red":"#FF8B8B","note_anim_green":"#00FF00",
        "note_sp_active":"#00FFFF","note_sp_phrase_active":"#00FFFF",
        "note_sp_phrase":"#00FFFF","note_open":"#BA00FF",
        "note_orange":"#FFB300","note_blue":"#0089FF",
        "note_yellow":"#FFFF00","note_red":"#FF0000","note_green":"#00FF00",
    },
    "drums": {
        "drums_striker_base_green":"#FFFFFF","drums_striker_base_blue":"#FFFFFF",
        "drums_striker_base_yellow":"#FFFFFF","drums_striker_base_red":"#FFFFFF",
        "drums_striker_head_light_kick":"#FFCE86","drums_striker_head_light_green":"#00FF00",
        "drums_striker_head_light_blue":"#0089FF","drums_striker_head_light_yellow":"#FFFF00",
        "drums_striker_head_light_red":"#FF0000",
        "drums_striker_head_cover_green":"#00FF00","drums_striker_head_cover_blue":"#0089FF",
        "drums_striker_head_cover_yellow":"#FFFF00","drums_striker_head_cover_red":"#FF0000",
        "drums_striker_cover_green":"#00FF00","drums_striker_cover_blue":"#0089FF",
        "drums_striker_cover_yellow":"#FFFF00","drums_striker_cover_red":"#FF0000",
        "note_anim_kick_sp_active":"#00FFFF","note_overlay_kick_sp_phrase":"#00D7D7",
        "note_anim_kick_sp_phrase_active":"#FFFFFF","note_anim_kick_sp_phrase":"#FFFF00",
        "note_kick_sp_active":"#009178","note_kick_sp_phrase_active":"#FFFFFF",
        "note_kick_sp_phrase":"#FF4600","note_anim_kick":"#FFFF00","note_kick":"#FF4600",
        "cym_anim_sp_active":"#7CFFD6","cym_anim_sp_phrase_active":"#FFFFFF",
        "cym_anim_sp_phrase":"#7CFFD6","cym_anim_blue":"#609EFF","cym_anim_yellow":"#FFEF5B",
        "cym_anim_red":"#FF8B8B","cym_anim_green":"#A5FF7B",
        "cym_sp_active":"#7CFFD6","cym_sp_phrase_active":"#7CFFD6","cym_sp_phrase":"#7CFFD6",
        "cym_blue":"#1D63FF","cym_yellow":"#FFE531","cym_red":"#FF4663","cym_green":"#0CFF0C",
        "tom_anim_sp_active":"#51FFFF","tom_anim_sp_phrase_active":"#FFFFFF",
        "tom_anim_sp_phrase":"#51FFFF","tom_anim_blue":"#2685FF","tom_anim_yellow":"#FFFF26",
        "tom_anim_red":"#FF2F2F","tom_anim_green":"#19FF19",
        "tom_sp_active":"#00FFFF","tom_sp_phrase_active":"#00FFFF","tom_sp_phrase":"#00FFFF",
        "tom_blue":"#0089FF","tom_yellow":"#FFFF00","tom_red":"#FF0000","tom_green":"#00FF00",
    },
    "sixfret": {
        "sf_note_hopo":"#00FFFF",
        "sf_striker_base_white_right":"#FFFFFF","sf_striker_base_white_mid":"#FFFFFF",
        "sf_striker_base_white_left":"#FFFFFF","sf_striker_base_black_right":"#3F3F3F",
        "sf_striker_base_black_mid":"#3F3F3F","sf_striker_base_black_left":"#3F3F3F",
        "sf_sustain_sp_active":"#00FFFF","sf_sustain_sp_phrase_active":"#00FFFF",
        "sf_sustain_sp_phrase":"#00FFFF","sf_sustain_open":"#FFFFFF",
        "sf_sustain_right":"#FFFFFF","sf_sustain_mid":"#FFFFFF","sf_sustain_left":"#FFFFFF",
        "sf_note_tap_open":"#BA00FF","sf_note_tap_white_right":"#BA00FF",
        "sf_note_tap_white_mid":"#BA00FF","sf_note_tap_white_left":"#BA00FF",
        "sf_note_tap_black_right":"#BA00FF","sf_note_tap_black_mid":"#BA00FF",
        "sf_note_tap_black_left":"#BA00FF",
        "sf_note_sp_active":"#00FFFF","sf_note_sp_phrase_active":"#00FFFF",
        "sf_note_sp_phrase":"#00FFFF","sf_note_open":"#FFFFFF",
        "sf_note_white_right":"#FFFFFF","sf_note_white_mid":"#FFFFFF","sf_note_white_left":"#FFFFFF",
        "sf_note_black_right":"#3F3F3F","sf_note_black_mid":"#3F3F3F","sf_note_black_left":"#3F3F3F",
    },
    "other": {
        "combo_sp_active_glow":"#FFFFFF","combo_four_glow":"#E8B1FF",
        "combo_three_glow":"#F0FFF0","combo_two_glow":"#FFFF00",
        "combo_sp_active":"#00CCCC","combo_four":"#874E9E","combo_three":"#00FF00",
        "combo_two":"#D55800","combo_one":"#FFDD00",
        "striker_hold_spark_sp_active":"#FF1200","striker_hold_spark":"#FF1200",
        "striker_hit_particles_sp_active":"#00FFFF","striker_hit_particles":"#FF5000",
        "striker_hit_flame_sp_active":"#00FFFF","striker_hit_flame":"#FFB76D",
        "striker_hit_flame_kick":"#FFB300","striker_hit_flame_open":"#BA00FF",
        "sp_bar_arrow":"#7FFFFF","sp_bar_elec":"#B2B2B2","sp_bar_color":"#004848",
        "sp_act_animation":"#00C1E5","sp_act_flash":"#0029BF",
        "general_sp_active":"#FFFFFF","general_sp":"#00FFFF",
    },
}

_NG_FRIENDLY: dict = {
    "note_green":"Note · Green","note_red":"Note · Red","note_yellow":"Note · Yellow",
    "note_blue":"Note · Blue","note_orange":"Note · Orange","note_open":"Note · Open",
    "note_sp_active":"Note · SP Active","note_sp_phrase":"Note · SP Phrase",
    "note_sp_phrase_active":"Note · SP Phrase Active",
    "note_anim_green":"Note Anim · Green","note_anim_red":"Note Anim · Red",
    "note_anim_yellow":"Note Anim · Yellow","note_anim_blue":"Note Anim · Blue",
    "note_anim_orange":"Note Anim · Orange","note_anim_open":"Note Anim · Open",
    "note_anim_sp_active":"Note Anim · SP Active","note_anim_sp_phrase":"Note Anim · SP Phrase",
    "note_anim_sp_phrase_active":"Note Anim · SP Phrase Active",
    "sustain_green":"Sustain · Green","sustain_red":"Sustain · Red",
    "sustain_yellow":"Sustain · Yellow","sustain_blue":"Sustain · Blue",
    "sustain_orange":"Sustain · Orange","sustain_open":"Sustain · Open",
    "sustain_sp_active":"Sustain · SP Active","sustain_sp_phrase":"Sustain · SP Phrase",
    "sustain_sp_phrase_active":"Sustain · SP Phrase Active",
    "striker_base_green":"Strikeline Base · Green","striker_base_red":"Strikeline Base · Red",
    "striker_base_yellow":"Strikeline Base · Yellow","striker_base_blue":"Strikeline Base · Blue",
    "striker_base_orange":"Strikeline Base · Orange",
    "striker_head_light_green":"Strikeline Head Light · Green",
    "striker_head_light_red":"Strikeline Head Light · Red",
    "striker_head_light_yellow":"Strikeline Head Light · Yellow",
    "striker_head_light_blue":"Strikeline Head Light · Blue",
    "striker_head_light_orange":"Strikeline Head Light · Orange",
    "striker_head_light_open":"Strikeline Head Light · Open",
    "striker_head_cover_green":"Strikeline Head Cover · Green",
    "striker_head_cover_red":"Strikeline Head Cover · Red",
    "striker_head_cover_yellow":"Strikeline Head Cover · Yellow",
    "striker_head_cover_blue":"Strikeline Head Cover · Blue",
    "striker_head_cover_orange":"Strikeline Head Cover · Orange",
    "striker_cover_green":"Strikeline Cover · Green","striker_cover_red":"Strikeline Cover · Red",
    "striker_cover_yellow":"Strikeline Cover · Yellow","striker_cover_blue":"Strikeline Cover · Blue",
    "striker_cover_orange":"Strikeline Cover · Orange",
    "note_kick":"Kick Note","note_anim_kick":"Kick Note Anim",
    "note_kick_sp_active":"Kick · SP Active","note_kick_sp_phrase":"Kick · SP Phrase",
    "note_kick_sp_phrase_active":"Kick · SP Phrase Active",
    "note_anim_kick_sp_active":"Kick Anim · SP Active","note_anim_kick_sp_phrase":"Kick Anim · SP Phrase",
    "note_anim_kick_sp_phrase_active":"Kick Anim · SP Phrase Active",
    "note_overlay_kick_sp_phrase":"Kick Overlay · SP Phrase",
    "cym_green":"Cymbal · Green","cym_red":"Cymbal · Red","cym_yellow":"Cymbal · Yellow","cym_blue":"Cymbal · Blue",
    "cym_anim_green":"Cymbal Anim · Green","cym_anim_red":"Cymbal Anim · Red",
    "cym_anim_yellow":"Cymbal Anim · Yellow","cym_anim_blue":"Cymbal Anim · Blue",
    "cym_sp_active":"Cymbal · SP Active","cym_sp_phrase":"Cymbal · SP Phrase","cym_sp_phrase_active":"Cymbal · SP Phrase Active",
    "cym_anim_sp_active":"Cymbal Anim · SP Active","cym_anim_sp_phrase":"Cymbal Anim · SP Phrase",
    "cym_anim_sp_phrase_active":"Cymbal Anim · SP Phrase Active",
    "tom_green":"Tom · Green","tom_red":"Tom · Red","tom_yellow":"Tom · Yellow","tom_blue":"Tom · Blue",
    "tom_anim_green":"Tom Anim · Green","tom_anim_red":"Tom Anim · Red",
    "tom_anim_yellow":"Tom Anim · Yellow","tom_anim_blue":"Tom Anim · Blue",
    "tom_sp_active":"Tom · SP Active","tom_sp_phrase":"Tom · SP Phrase","tom_sp_phrase_active":"Tom · SP Phrase Active",
    "tom_anim_sp_active":"Tom Anim · SP Active","tom_anim_sp_phrase":"Tom Anim · SP Phrase",
    "tom_anim_sp_phrase_active":"Tom Anim · SP Phrase Active",
    "drums_striker_base_green":"Drum Strikeline Base · Green","drums_striker_base_red":"Drum Strikeline Base · Red",
    "drums_striker_base_yellow":"Drum Strikeline Base · Yellow","drums_striker_base_blue":"Drum Strikeline Base · Blue",
    "drums_striker_head_light_kick":"Drum Strikeline Head Light · Kick",
    "drums_striker_head_light_green":"Drum Strikeline Head Light · Green",
    "drums_striker_head_light_red":"Drum Strikeline Head Light · Red",
    "drums_striker_head_light_yellow":"Drum Strikeline Head Light · Yellow",
    "drums_striker_head_light_blue":"Drum Strikeline Head Light · Blue",
    "drums_striker_head_cover_green":"Drum Strikeline Head Cover · Green",
    "drums_striker_head_cover_red":"Drum Strikeline Head Cover · Red",
    "drums_striker_head_cover_yellow":"Drum Strikeline Head Cover · Yellow",
    "drums_striker_head_cover_blue":"Drum Strikeline Head Cover · Blue",
    "drums_striker_cover_green":"Drum Strikeline Cover · Green",
    "drums_striker_cover_red":"Drum Strikeline Cover · Red",
    "drums_striker_cover_yellow":"Drum Strikeline Cover · Yellow",
    "drums_striker_cover_blue":"Drum Strikeline Cover · Blue",
    "sf_note_hopo":"Six-Fret Note · HOPO","sf_note_open":"Six-Fret Note · Open",
    "sf_note_white_left":"Six-Fret Note · White Left","sf_note_white_mid":"Six-Fret Note · White Mid",
    "sf_note_white_right":"Six-Fret Note · White Right","sf_note_black_left":"Six-Fret Note · Black Left",
    "sf_note_black_mid":"Six-Fret Note · Black Mid","sf_note_black_right":"Six-Fret Note · Black Right",
    "sf_note_sp_active":"Six-Fret Note · SP Active","sf_note_sp_phrase":"Six-Fret Note · SP Phrase",
    "sf_note_sp_phrase_active":"Six-Fret Note · SP Phrase Active",
    "sf_note_tap_open":"Six-Fret Tap · Open","sf_note_tap_white_left":"Six-Fret Tap · White Left",
    "sf_note_tap_white_mid":"Six-Fret Tap · White Mid","sf_note_tap_white_right":"Six-Fret Tap · White Right",
    "sf_note_tap_black_left":"Six-Fret Tap · Black Left","sf_note_tap_black_mid":"Six-Fret Tap · Black Mid",
    "sf_note_tap_black_right":"Six-Fret Tap · Black Right",
    "sf_sustain_open":"Six-Fret Sustain · Open","sf_sustain_left":"Six-Fret Sustain · Left",
    "sf_sustain_mid":"Six-Fret Sustain · Mid","sf_sustain_right":"Six-Fret Sustain · Right",
    "sf_sustain_sp_active":"Six-Fret Sustain · SP Active","sf_sustain_sp_phrase":"Six-Fret Sustain · SP Phrase",
    "sf_sustain_sp_phrase_active":"Six-Fret Sustain · SP Phrase Active",
    "sf_striker_base_white_left":"Six-Fret Strikeline Base · White Left",
    "sf_striker_base_white_mid":"Six-Fret Strikeline Base · White Mid",
    "sf_striker_base_white_right":"Six-Fret Strikeline Base · White Right",
    "sf_striker_base_black_left":"Six-Fret Strikeline Base · Black Left",
    "sf_striker_base_black_mid":"Six-Fret Strikeline Base · Black Mid",
    "sf_striker_base_black_right":"Six-Fret Strikeline Base · Black Right",
    "combo_one":"Multiplier · x1","combo_two":"Multiplier · x2","combo_three":"Multiplier · x3",
    "combo_four":"Multiplier · x4","combo_sp_active":"Multiplier · SP Active",
    "combo_two_glow":"Multiplier Glow · x2","combo_three_glow":"Multiplier Glow · x3",
    "combo_four_glow":"Multiplier Glow · x4","combo_sp_active_glow":"Multiplier Glow · SP Active",
    "striker_hit_flame":"Hit Flame","striker_hit_flame_sp_active":"Hit Flame · SP Active",
    "striker_hit_flame_kick":"Hit Flame · Kick","striker_hit_flame_open":"Hit Flame · Open",
    "striker_hit_particles":"Hit Particles","striker_hit_particles_sp_active":"Hit Particles · SP Active",
    "striker_hold_spark":"Hold Spark","striker_hold_spark_sp_active":"Hold Spark · SP Active",
    "sp_bar_color":"SP Bar · Color","sp_bar_arrow":"SP Bar · Arrow","sp_bar_elec":"SP Bar · Electric",
    "sp_act_animation":"SP Activation · Animation","sp_act_flash":"SP Activation · Flash",
    "general_sp":"General SP Color","general_sp_active":"General SP Active Color",
}

_NG_GROUPS: dict = {
    "guitar": [
        ("Notes", ["note_green","note_red","note_yellow","note_blue","note_orange","note_open",
                   "note_sp_phrase","note_sp_active","note_sp_phrase_active"]),
        ("Note Animations", ["note_anim_green","note_anim_red","note_anim_yellow","note_anim_blue",
                             "note_anim_orange","note_anim_open",
                             "note_anim_sp_phrase","note_anim_sp_active","note_anim_sp_phrase_active"]),
        ("Sustains", ["sustain_green","sustain_red","sustain_yellow","sustain_blue",
                      "sustain_orange","sustain_open",
                      "sustain_sp_phrase","sustain_sp_active","sustain_sp_phrase_active"]),
        ("Strikeline Head Light", ["striker_head_light_green","striker_head_light_red",
                                   "striker_head_light_yellow","striker_head_light_blue",
                                   "striker_head_light_orange","striker_head_light_open"]),
        ("Strikeline Head Cover", ["striker_head_cover_green","striker_head_cover_red",
                                   "striker_head_cover_yellow","striker_head_cover_blue",
                                   "striker_head_cover_orange"]),
        ("Strikeline Cover", ["striker_cover_green","striker_cover_red","striker_cover_yellow",
                              "striker_cover_blue","striker_cover_orange"]),
    ],
}

_NG_GUITAR_LANES = ["green","red","yellow","blue","orange"]
_NG_DRUM_LANES   = ["red","yellow","blue","green"]
_NG_SF_LANES     = [("black","left"),("white","left"),("black","mid"),
                    ("white","mid"),("black","right"),("white","right")]


def _ng_friendly(key: str) -> str:
    return _NG_FRIENDLY.get(key, key.replace("_"," ").title())

def _ng_valid_hex(s: str) -> bool:
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', s.strip()))

def _ng_hex_to_rgb(h: str):
    """int-based hex→(r,g,b) for NoteGen colorization."""
    h = h.lstrip("#")
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

def _ng_rgb_to_hex(r:int, g:int, b:int) -> str:
    return "#{:02X}{:02X}{:02X}".format(max(0,min(255,r)),max(0,min(255,g)),max(0,min(255,b)))

def _ng_darken(h:str, f:float=0.4) -> str:
    r,g,b = _ng_hex_to_rgb(h); return _ng_rgb_to_hex(int(r*f),int(g*f),int(b*f))

def _ng_lighten(h:str, f:float=1.6) -> str:
    r,g,b = _ng_hex_to_rgb(h); return _ng_rgb_to_hex(int(r*f),int(g*f),int(b*f))

def _ng_lerp_hex(a:str, b:str, t:float) -> str:
    ar,ag,ab_ = _ng_hex_to_rgb(a); br,bg_,bb = _ng_hex_to_rgb(b)
    return _ng_rgb_to_hex(int(ar+(br-ar)*t),int(ag+(bg_-ag)*t),int(ab_+(bb-ab_)*t))

def _ng_alpha_blend(h:str, bg:str, alpha:float) -> str:
    r1,g1,b1 = _ng_hex_to_rgb(h); r2,g2,b2 = _ng_hex_to_rgb(bg)
    return _ng_rgb_to_hex(int(r1*alpha+r2*(1-alpha)),int(g1*alpha+g2*(1-alpha)),int(b1*alpha+b2*(1-alpha)))

def _ng_load_profiles() -> dict:
    try:
        if _NG_PROFILES_FILE.is_file():
            return json.loads(_NG_PROFILES_FILE.read_text(encoding="utf-8"))
    except Exception: pass
    return {}

def _ng_save_profiles(profiles: dict):
    try: _NG_PROFILES_FILE.write_text(json.dumps(profiles,indent=2),encoding="utf-8")
    except Exception as e: print(f"[ng_save_profiles] {e}")

def _ng_fresh_colors() -> dict:
    return copy.deepcopy(_NG_DEFAULT_COLORS)

def _ng_parse_ini(path:str) -> dict:
    cfg = configparser.ConfigParser(allow_no_value=True); cfg.optionxform = str
    cfg.read(path, encoding="utf-8"); result = {}
    for section in cfg.sections():
        result[section.lower()] = {}
        for key, val in cfg.items(section):
            if val and val.strip():
                result[section.lower()][key.lower()] = val.strip().upper()
    return result

def _ng_generate_ini(colors:dict) -> str:
    lines = []
    for section in _SECTION_ORDER:
        if section not in colors: continue
        lines.append(f"[{section}]")
        for key, val in colors[section].items(): lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines)

def _ng_find_template():
    for name in _TEMPLATE_NAMES:
        p = _NG_IMAGES_DIR / name
        if p.is_file(): return p
        p2 = _app_dir() / name
        if p2.is_file(): return p2
    return None

def _ng_find_mask():
    for d in (_NG_IMAGES_DIR, _app_dir()):
        p = d / "mask.png"
        if p.is_file(): return p
    return None

def _ng_rgb_to_hsl(r,g,b):
    r,g,b = r/255.,g/255.,b/255.; cmax,cmin=max(r,g,b),min(r,g,b); delta=cmax-cmin
    l=(cmax+cmin)/2.; s=0. if delta==0 else delta/(1-abs(2*l-1))
    if delta==0: h=0.
    elif cmax==r: h=60.*(((g-b)/delta)%6)
    elif cmax==g: h=60.*(((b-r)/delta)+2)
    else: h=60.*(((r-g)/delta)+4)
    return h,s,l

def _ng_hsl_to_rgb(h,s,l):
    c=(1-abs(2*l-1))*s; x=c*(1-abs((h/60)%2-1)); m=l-c/2
    if h<60:   r1,g1,b1=c,x,0.
    elif h<120:r1,g1,b1=x,c,0.
    elif h<180:r1,g1,b1=0.,c,x
    elif h<240:r1,g1,b1=0.,x,c
    elif h<300:r1,g1,b1=x,0.,c
    else:      r1,g1,b1=c,0.,x
    return int((r1+m)*255),int((g1+m)*255),int((b1+m)*255)

def _ng_colorize_pil(img, hex_color:str):
    try:
        import numpy as np
        _NP = True
    except ImportError:
        _NP = False
    rgba = img.convert("RGBA")
    if not _NP:
        hue,sat,_ = _ng_rgb_to_hsl(*_ng_hex_to_rgb(hex_color))
        r_lut,g_lut,b_lut=[],[],[]
        for L in range(256):
            if L<=40: w=0.
            elif L<=85: w=(L-40)/45.
            elif L<=210: w=1.
            elif L<=240: w=1.-(L-210)/30.
            else: w=0.
            w=w*w*(3-2*w)
            rc,gc,bc=_ng_hsl_to_rgb(hue,sat,L/255.)
            r_lut.append(max(0,min(255,int(L*(1-w)+rc*w))))
            g_lut.append(max(0,min(255,int(L*(1-w)+gc*w))))
            b_lut.append(max(0,min(255,int(L*(1-w)+bc*w))))
        r_ch,g_ch,b_ch,a_ch=rgba.split(); gray=r_ch
        from PIL import Image as _PI
        return _PI.merge("RGBA",(gray.point(r_lut),gray.point(g_lut),gray.point(b_lut),a_ch))
    import numpy as np
    arr=np.array(rgba,dtype=np.float32); H,W=arr.shape[:2]
    R,G,B,A=arr[:,:,0],arr[:,:,1],arr[:,:,2],arr[:,:,3]
    lum=0.299*R+0.587*G+0.114*B
    mask_path=_ng_find_mask()
    if mask_path:
        from PIL import Image as _PI
        mi=_PI.open(str(mask_path)).convert("L").resize((W,H),_PI.LANCZOS)
        weight=np.array(mi,dtype=np.float32)/255.*(A/255.)
    else:
        weight=A/255.
    tr,tg,tb=_ng_hex_to_rgb(hex_color)
    scale=lum/128.
    r_col=np.clip(scale*tr,0.,255.); g_col=np.clip(scale*tg,0.,255.); b_col=np.clip(scale*tb,0.,255.)
    orig=arr[:,:,:3]
    r_o=np.clip(orig[:,:,0]*(1.-weight)+r_col*weight,0,255).astype(np.uint8)
    g_o=np.clip(orig[:,:,1]*(1.-weight)+g_col*weight,0,255).astype(np.uint8)
    b_o=np.clip(orig[:,:,2]*(1.-weight)+b_col*weight,0,255).astype(np.uint8)
    a_o=arr[:,:,3].astype(np.uint8)
    from PIL import Image as _PI
    return _PI.fromarray(np.stack([r_o,g_o,b_o,a_o],axis=2),"RGBA")

def _ng_generate_note_images(guitar_colors:dict):
    if not _PIL_OK: return [],["Pillow is not installed."]
    tpl=_ng_find_template()
    if tpl is None: return [],[f"Template not found. Place one of {_TEMPLATE_NAMES} in {_NG_IMAGES_DIR}"]
    try:
        from PIL import Image as _PI
        base=_PI.open(str(tpl))
    except Exception as e: return [],[f"Could not open template: {e}"]
    _NG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    saved,errors=[],[]
    for lane,ini_key,filename in _NOTE_FILE_MAP:
        hex_color=guitar_colors.get(ini_key,"#FFFFFF")
        try:
            colored=_ng_colorize_pil(base,hex_color)
            out=_NG_IMAGES_DIR/filename; colored.save(str(out)); saved.append(filename)
        except Exception as e: errors.append(f"{filename}: {e}")
    return saved,errors


# ── NoteGen custom HSV colour picker ─────────────────────────────────────────

class _ColorPickerDialog(tk.Toplevel):
    """Full HSV square + hue bar colour picker — replaces tkinter's colorchooser."""
    _SQ = 220
    _HH = 20

    def __init__(self, parent, initial_hex:str, title:str="Pick Color"):
        super().__init__(parent)
        self.title(title); self.resizable(False,False)
        self.configure(bg=C["bg"]); self.transient(parent); self.grab_set()
        self.result = None
        try: ri,gi,bi = _ng_hex_to_rgb(initial_hex)
        except Exception: ri,gi,bi = 255,255,255
        h,s,v = colorsys.rgb_to_hsv(ri/255,gi/255,bi/255)
        self._h,self._s,self._v = h,s,v
        self._orig = _ng_rgb_to_hex(ri,gi,bi).upper()
        self._r=tk.IntVar(value=ri); self._g=tk.IntVar(value=gi); self._b=tk.IntVar(value=bi)
        self._hex_var=tk.StringVar(value=self._orig)
        self._busy=False; self._sq_cur_ids=[]; self._hue_cur_ids=[]
        self._sq_photo=None
        self._build_ui(); self._render_sq(); self._render_hue()
        self._refresh_cursors(); self._update_preview()
        self.update_idletasks()
        pw,ph=parent.winfo_width(),parent.winfo_height()
        px,py=parent.winfo_rootx(),parent.winfo_rooty()
        ww,wh=self.winfo_reqwidth(),self.winfo_reqheight()
        self.geometry(f"+{px+(pw-ww)//2}+{py+(ph-wh)//2}")
        self.wait_window()

    def _build_ui(self):
        SQ=self._SQ
        outer=tk.Frame(self,bg=C["bg"],padx=18,pady=16); outer.pack()
        left=tk.Frame(outer,bg=C["bg"]); left.pack(side="left",padx=(0,20))
        sq_wrap=tk.Frame(left,bg="#252845",padx=1,pady=1); sq_wrap.pack()
        self._sq_cv=tk.Canvas(sq_wrap,width=SQ,height=SQ,highlightthickness=0,cursor="crosshair")
        self._sq_cv.pack()
        self._sq_cv.bind("<Button-1>",self._sq_drag)
        self._sq_cv.bind("<B1-Motion>",self._sq_drag)
        tk.Frame(left,bg=C["border"],height=1).pack(fill="x",pady=(10,0))
        hue_wrap=tk.Frame(left,bg="#252845",padx=1,pady=1); hue_wrap.pack(pady=(8,0))
        self._hue_cv=tk.Canvas(hue_wrap,width=SQ,height=self._HH,highlightthickness=0,cursor="sb_h_double_arrow")
        self._hue_cv.pack()
        self._hue_cv.bind("<Button-1>",self._hue_drag)
        self._hue_cv.bind("<B1-Motion>",self._hue_drag)
        right=tk.Frame(outer,bg=C["bg"]); right.pack(side="left",fill="both")
        pv=tk.Frame(right,bg=C["bg"]); pv.pack(fill="x",pady=(0,14))
        tk.Label(pv,text="BEFORE",bg=C["bg"],fg=C["text_dim"],font=("Segoe UI",7,"bold")).pack(side="left")
        self._sw_old=tk.Frame(pv,bg=self._orig,width=54,height=36); self._sw_old.pack(side="left",padx=(5,2)); self._sw_old.pack_propagate(False)
        self._sw_new=tk.Frame(pv,bg=self._orig,width=54,height=36); self._sw_new.pack(side="left",padx=(2,5)); self._sw_new.pack_propagate(False)
        tk.Label(pv,text="AFTER",bg=C["bg"],fg=C["text_dim"],font=("Segoe UI",7,"bold")).pack(side="left")
        for label,var,trough in [("R",self._r,"#5c1212"),("G",self._g,"#124a22"),("B",self._b,"#12265c")]:
            row=tk.Frame(right,bg=C["bg"]); row.pack(fill="x",pady=3)
            tk.Label(row,text=label,bg=C["bg"],fg=C["text"],font=FTB,width=2).pack(side="left")
            tk.Scale(row,variable=var,from_=0,to=255,orient="horizontal",length=200,showvalue=True,
                     bg=C["bg"],fg=C["text_mid"],troughcolor=trough,highlightthickness=0,bd=0,
                     sliderrelief="flat",font=("Segoe UI",8),command=lambda _v: self._on_rgb()).pack(side="left",padx=(4,0))
        tk.Frame(right,bg=C["border"],height=1).pack(fill="x",pady=(10,8))
        hx=tk.Frame(right,bg=C["bg"]); hx.pack(fill="x",pady=(0,4))
        tk.Label(hx,text="HEX",bg=C["bg"],fg=C["text_dim"],font=("Segoe UI",7,"bold")).pack(side="left",padx=(0,8))
        self._hex_entry=tk.Entry(hx,textvariable=self._hex_var,font=("Consolas",10),width=9,
                                  bg="#0a0c16",fg=C["accent"],insertbackground=C["accent"],
                                  relief="flat",bd=0,highlightthickness=1,
                                  highlightbackground=C["border"],highlightcolor=C["accent"])
        self._hex_entry.pack(side="left",ipady=4,padx=4)
        self._hex_entry.bind("<Return>",self._on_hex); self._hex_entry.bind("<FocusOut>",self._on_hex)
        hsv_row=tk.Frame(right,bg=C["bg"]); hsv_row.pack(fill="x",pady=(8,0))
        self._lh=tk.Label(hsv_row,text="H: 0°",bg=C["bg"],fg=C["text_dim"],font=FTS)
        self._ls=tk.Label(hsv_row,text="S: 0%",bg=C["bg"],fg=C["text_dim"],font=FTS)
        self._lv=tk.Label(hsv_row,text="V: 100%",bg=C["bg"],fg=C["text_dim"],font=FTS)
        for lbl in (self._lh,self._ls,self._lv): lbl.pack(side="left",padx=(0,10))
        btn_row=tk.Frame(right,bg=C["bg"]); btn_row.pack(fill="x",pady=(18,0))
        tk.Button(btn_row,text="Cancel",font=FT,bg=C["card2"],fg=C["text_mid"],
                  activebackground=C["border2"] if "border2" in C else C["border"],
                  activeforeground=C["text"],relief="flat",bd=0,padx=12,pady=7,cursor="hand2",
                  command=self.destroy).pack(side="right",padx=(4,0))
        tk.Button(btn_row,text="✓  Apply",font=FTB,bg=C["accent"],fg="#fff",
                  activebackground=C["accent_dim"],activeforeground="#fff",
                  relief="flat",bd=0,padx=16,pady=7,cursor="hand2",
                  command=self._ok).pack(side="right")

    def _render_sq(self):
        SQ=self._SQ
        try:
            import numpy as np
            from PIL import Image as _PI
            from PIL import ImageTk as _ITk
            xs=np.linspace(0,1,SQ); ys=np.linspace(1,0,SQ)
            S,V=np.meshgrid(xs,ys); h=self._h
            hi=np.floor(h*6).astype(int)%6; f=h*6-np.floor(h*6)
            p=V*(1-S); q=V*(1-f*S); t_=V*(1-(1-f)*S)
            cR=np.select([hi==0,hi==1,hi==2,hi==3,hi==4],[V,q,p,p,t_],V)
            cG=np.select([hi==0,hi==1,hi==2,hi==3,hi==4],[t_,V,V,q,p],p)
            cB=np.select([hi==0,hi==1,hi==2,hi==3,hi==4],[p,p,t_,V,V],q)
            rgb=(np.stack([cR,cG,cB],axis=2)*255).astype(np.uint8)
            photo=_ITk.PhotoImage(_PI.fromarray(rgb,"RGB"))
        except Exception:
            photo=tk.PhotoImage(width=SQ,height=SQ)
            rows=[]
            for y in range(SQ):
                v=1.-y/max(SQ-1,1)
                cols=[_ng_rgb_to_hex(*[int(c*255) for c in colorsys.hsv_to_rgb(self._h,x/max(SQ-1,1),v)]) for x in range(SQ)]
                rows.append("{"+' '.join(cols)+"}")
            photo.put(' '.join(rows))
        self._sq_photo=photo
        self._sq_cv.delete("all")
        self._sq_cv.create_image(0,0,anchor="nw",image=photo)

    def _render_hue(self):
        SQ=self._SQ; HH=self._HH
        try:
            import numpy as np
            from PIL import Image as _PI
            from PIL import ImageTk as _ITk
            xs=np.linspace(0,1,SQ)
            r,g,b=np.vectorize(lambda h: colorsys.hsv_to_rgb(h,1,1))(xs)
            row=(np.stack([r,g,b],axis=1)*255).astype(np.uint8)
            arr=np.tile(row[np.newaxis,:,:],(HH,1,1))
            photo=_ITk.PhotoImage(_PI.fromarray(arr,"RGB"))
        except Exception:
            photo=tk.PhotoImage(width=SQ,height=HH)
            rows=[]
            for _ in range(HH):
                cols=[_ng_rgb_to_hex(*[int(c*255) for c in colorsys.hsv_to_rgb(x/max(SQ-1,1),1,1)]) for x in range(SQ)]
                rows.append("{"+' '.join(cols)+"}")
            photo.put(' '.join(rows))
        self._hue_photo=photo
        self._hue_cv.delete("all")
        self._hue_cv.create_image(0,0,anchor="nw",image=photo)

    def _refresh_cursors(self):
        for iid in self._sq_cur_ids: self._sq_cv.delete(iid)
        for iid in self._hue_cur_ids: self._hue_cv.delete(iid)
        self._sq_cur_ids=[]; self._hue_cur_ids=[]
        SQ=self._SQ; cx=int(self._s*(SQ-1)); cy=int((1.-self._v)*(SQ-1)); cr=8
        self._sq_cur_ids=[self._sq_cv.create_oval(cx-cr,cy-cr,cx+cr,cy+cr,outline="#ffffff",width=2),
                          self._sq_cv.create_oval(cx-cr+2,cy-cr+2,cx+cr-2,cy+cr-2,outline="#000000",width=1)]
        hx=int(self._h*(SQ-1))
        self._hue_cur_ids=[self._hue_cv.create_line(hx,0,hx,self._HH,fill="#ffffff",width=2),
                           self._hue_cv.create_line(hx,0,hx,self._HH,fill="#000000",width=1,dash=(3,3))]

    def _update_preview(self):
        hx=_ng_rgb_to_hex(self._r.get(),self._g.get(),self._b.get())
        self._sw_new.config(bg=hx); self._hex_var.set(hx.upper())
        self._lh.config(text=f"H: {int(self._h*360)}°")
        self._ls.config(text=f"S: {int(self._s*100)}%")
        self._lv.config(text=f"V: {int(self._v*100)}%")

    def _sq_drag(self,ev):
        SQ=self._SQ; self._s=max(0.,min(1.,ev.x/(SQ-1))); self._v=max(0.,min(1.,1.-ev.y/(SQ-1)))
        self._sq_cv.delete("all"); self._sq_cv.create_image(0,0,anchor="nw",image=self._sq_photo)
        cx=int(self._s*(SQ-1)); cy=int((1.-self._v)*(SQ-1)); cr=8
        self._sq_cv.create_oval(cx-cr,cy-cr,cx+cr,cy+cr,outline="#ffffff",width=2)
        self._sq_cv.create_oval(cx-cr+2,cy-cr+2,cx+cr-2,cy+cr-2,outline="#000000",width=1)
        r,g,b=colorsys.hsv_to_rgb(self._h,self._s,self._v)
        self._busy=True; self._r.set(int(r*255+.5)); self._g.set(int(g*255+.5)); self._b.set(int(b*255+.5))
        self._busy=False; self._update_preview()

    def _hue_drag(self,ev):
        self._h=max(0.,min(1.,ev.x/(self._SQ-1)))
        self._render_sq(); self._refresh_cursors()
        r,g,b=colorsys.hsv_to_rgb(self._h,self._s,self._v)
        self._busy=True; self._r.set(int(r*255+.5)); self._g.set(int(g*255+.5)); self._b.set(int(b*255+.5))
        self._busy=False; self._update_preview()

    def _on_rgb(self):
        if self._busy: return
        self._busy=True
        self._h,self._s,self._v=colorsys.rgb_to_hsv(self._r.get()/255,self._g.get()/255,self._b.get()/255)
        self._render_sq(); self._render_hue(); self._refresh_cursors(); self._update_preview()
        self._busy=False

    def _on_hex(self,_=None):
        val=self._hex_var.get().strip().lstrip("#")
        if len(val)==6:
            try: ri,gi,bi=int(val[0:2],16),int(val[2:4],16),int(val[4:6],16)
            except ValueError: return
            if self._busy: return
            self._busy=True; self._r.set(ri); self._g.set(gi); self._b.set(bi)
            self._h,self._s,self._v=colorsys.rgb_to_hsv(ri/255,gi/255,bi/255)
            self._render_sq(); self._render_hue(); self._refresh_cursors(); self._update_preview()
            self._busy=False

    def _ok(self):
        self.result=_ng_rgb_to_hex(self._r.get(),self._g.get(),self._b.get()).upper()
        self.destroy()


# ── NoteGen scrollable frame ──────────────────────────────────────────────────

class _NgScrollFrame(tk.Frame):
    def __init__(self,parent,bg="",**kw):
        bg=bg or C["card"]
        super().__init__(parent,bg=bg,**kw)
        self._cv=tk.Canvas(self,bg=bg,highlightthickness=0,bd=0)
        self._vsb=ttk.Scrollbar(self,orient="vertical",command=self._cv.yview)
        self._cv.configure(yscrollcommand=self._vsb.set)
        self._vsb.pack(side="right",fill="y"); self._cv.pack(side="left",fill="both",expand=True)
        self.inner=tk.Frame(self._cv,bg=bg)
        self._win=self._cv.create_window((0,0),window=self.inner,anchor="nw")
        self.inner.bind("<Configure>",self._on_inner)
        self._cv.bind("<Configure>",self._on_canvas)
        self._cv.bind("<Enter>",lambda _: self._cv.bind_all("<MouseWheel>",self._scroll))
        self._cv.bind("<Leave>",lambda _: self._cv.unbind_all("<MouseWheel>"))

    def _on_inner(self,_=None): self._cv.configure(scrollregion=self._cv.bbox("all"))
    def _on_canvas(self,ev): self._cv.itemconfig(self._win,width=ev.width)
    def _scroll(self,ev): self._cv.yview_scroll(int(-1*(ev.delta/120)),"units")
    def scroll_top(self): self._cv.yview_moveto(0)


# ── NoteGen collapsible group header ─────────────────────────────────────────

class _NgGroupHeader(tk.Frame):
    _BG="#080a16"; _HOV="#0e1024"
    def __init__(self,parent,text,count=0,**kw):
        super().__init__(parent,bg=self._BG,cursor="hand2",**kw)
        self._expanded=True; self._children=None
        row=tk.Frame(self,bg=self._BG); row.pack(fill="x")
        tk.Frame(row,bg=C["accent"],width=3).pack(side="left",fill="y")
        self._chev=tk.Label(row,text="▾",bg=self._BG,fg=C["accent"],font=("Segoe UI",10))
        self._chev.pack(side="left",padx=(8,4))
        self._title=tk.Label(row,text=text,font=("Segoe UI",8,"bold"),bg=self._BG,fg=C["accent"],pady=8,anchor="w")
        self._title.pack(side="left",fill="x",expand=True)
        if count:
            badge=tk.Frame(row,bg=C["accent_dim"]); badge.pack(side="right",padx=(0,10))
            tk.Label(badge,text=f" {count} ",font=("Segoe UI",7,"bold"),bg=C["accent_dim"],fg=C["accent"]).pack(padx=2,pady=2)
        tk.Frame(self,bg="#141830",height=1).pack(fill="x")
        for w in (self,row,self._chev,self._title):
            w.bind("<Enter>",self._h_on); w.bind("<Leave>",self._h_off); w.bind("<Button-1>",self._toggle)

    def _h_on(self,_=None):
        for w in (self,self._chev,self._title):
            try: w.config(bg=self._HOV)
            except: pass
    def _h_off(self,_=None):
        for w in (self,self._chev,self._title):
            try: w.config(bg=self._BG)
            except: pass
    def _toggle(self,_=None):
        self._expanded=not self._expanded; self._chev.config(text="▾" if self._expanded else "▸")
        if self._children:
            (self._children.pack if self._expanded else self._children.pack_forget)(fill="x") if self._expanded else self._children.pack_forget()
    def attach(self,frame): self._children=frame


# ── NoteGen colour row ────────────────────────────────────────────────────────

class _NgColorRow(tk.Frame):
    _IDLE_ODD="#0c0e1d"; _IDLE_EVEN="#090b17"; _HOV="#161930"; _ACT="#1e2145"; _STEPS=8

    def __init__(self,parent,section,key,notegen_page,row_idx):
        idle=self._IDLE_ODD if row_idx%2 else self._IDLE_EVEN
        super().__init__(parent,bg=idle,cursor="hand2")
        self._section=section; self._key=key; self._page=notegen_page
        self._idle=idle; self._muted=False; self._anim_id=None; self._t=0.; self._going=0
        tk.Frame(self,bg="#0f1228",height=1).pack(side="bottom",fill="x")
        self._sw=tk.Canvas(self,width=50,height=28,highlightthickness=0,bg="#000",cursor="hand2")
        self._sw.pack(side="left",padx=(12,10),pady=6)
        self._lbl=tk.Label(self,text=_ng_friendly(key),bg=idle,fg=C["text_mid"],font=FTS,anchor="w")
        self._lbl.pack(side="left",fill="x",expand=True,padx=(0,6))
        pill=tk.Frame(self,bg="#0a0d1e",highlightthickness=1,highlightbackground="#222545")
        pill.pack(side="right",padx=(0,12),pady=6)
        self._var=tk.StringVar(value="#000000")
        self._entry=tk.Entry(pill,textvariable=self._var,font=("Consolas",9),width=8,
                             bg="#0a0d1e",fg="#8a7fff",insertbackground=C["accent"],
                             relief="flat",bd=4,highlightthickness=0,cursor="hand2",
                             state="readonly",readonlybackground="#0a0d1e")
        self._entry.pack()
        self._entry.bind("<FocusIn>",lambda e: pill.config(highlightbackground=C["accent"]))
        self._entry.bind("<FocusOut>",lambda e: pill.config(highlightbackground="#222545"))
        self._entry.bind("<Button-1>",self._copy_hex)
        self._pill=pill
        self._pick_btn=tk.Button(self,text="Pick Color",font=("Segoe UI",8),bg="#1a1d36",fg=C["text_mid"],
                                  relief="flat",activebackground=C["accent"],activeforeground="#fff",
                                  cursor="hand2",bd=0,padx=8,pady=3,command=self._open_picker)
        self._pick_btn.pack(side="right",padx=(0,4))
        self._pick_btn.bind("<Enter>",lambda e: self._pick_btn.config(bg=C["accent"],fg="#fff"))
        self._pick_btn.bind("<Leave>",lambda e: self._pick_btn.config(bg="#1a1d36",fg=C["text_mid"]))
        self._copied_lbl=tk.Label(self,text="Copied!",font=("Segoe UI",8,"bold"),bg=self._idle,fg=C["success"],padx=4)
        for w in (self,self._lbl,self._sw):
            w.bind("<Enter>",self._h_in); w.bind("<Leave>",self._h_out); w.bind("<Button-1>",self._click)
        self._var.trace_add("write",self._on_write)

    def _draw_sw(self,col):
        self._sw.delete("all"); self._sw.create_rectangle(0,0,50,28,fill=col,outline="")
        try: self._sw.create_rectangle(3,2,28,7,fill=_ng_lighten(col,1.8),outline="")
        except: pass
        self._sw.create_rectangle(0,0,49,27,outline=_ng_darken(col,0.5),fill="")

    def _animate(self):
        self._t=max(0.,min(1.,self._t+self._going/self._STEPS)); t=self._t*self._t*(3-2*self._t)
        bg=_ng_lerp_hex(self._idle,self._HOV,t); fg=_ng_lerp_hex(C["text_mid"],C["text"],t)
        self.config(bg=bg); self._lbl.config(bg=bg,fg=fg)
        if 0.<self._t<1.: self._anim_id=self.after(16,self._animate)
        else: self._anim_id=None

    def _h_in(self,_=None):
        self._going=+1
        if not self._anim_id: self._animate()
    def _h_out(self,_=None):
        self._going=-1
        if not self._anim_id: self._animate()
    def _click(self,_=None):
        self.config(bg=self._ACT); self._lbl.config(bg=self._ACT)
        self.after(80,self._h_in); self._open_picker()

    def _copy_hex(self,e=None):
        col=self.get_color()
        try: self.clipboard_clear(); self.clipboard_append(col)
        except: pass
        self._pill.config(highlightbackground=C["success"])
        self._copied_lbl.config(bg=self.cget("bg"))
        self._copied_lbl.pack(side="right",before=self._pill)
        def _hide():
            self._copied_lbl.pack_forget(); self._pill.config(highlightbackground="#222545")
        if hasattr(self,"_copy_after_id"):
            try: self.after_cancel(self._copy_after_id)
            except: pass
        self._copy_after_id=self.after(900,_hide)
        return "break"

    def set_color(self,hex_str:str):
        self._muted=True; self._var.set(hex_str.upper())
        if _ng_valid_hex(hex_str): self._draw_sw(hex_str)
        self._muted=False

    def get_color(self): return self._var.get().strip().upper()

    def set_readonly(self,readonly):
        self._entry.config(state="disabled" if readonly else "readonly",
                           fg=C["text_dim"] if readonly else "#8a7fff",
                           readonlybackground="#0a0d1e",disabledbackground="#0a0d1e",
                           disabledforeground=C["text_dim"])
        self._pick_btn.config(state="disabled" if readonly else "normal",
                              bg=C["border"] if readonly else "#1a1d36",
                              fg=C["text_dim"] if readonly else C["text_mid"])
        cur="" if readonly else "hand2"
        for w in (self,self._lbl,self._sw):
            w.config(cursor=cur)
            if readonly: w.unbind("<Enter>"); w.unbind("<Leave>"); w.unbind("<Button-1>")
            else:
                w.bind("<Enter>",self._h_in); w.bind("<Leave>",self._h_out)
                w.bind("<Button-1>",self._click)

    def _on_write(self,*_):
        if self._muted: return
        val=self._var.get().strip()
        if not val.startswith("#"): val="#"+val
        if _ng_valid_hex(val):
            self._draw_sw(val); self._page.on_color_changed(self._section,self._key,val.upper())

    def _open_picker(self,*_):
        cur=self.get_color()
        if not _ng_valid_hex(cur): cur="#FFFFFF"
        dlg=_ColorPickerDialog(self.winfo_toplevel(),cur,title=_ng_friendly(self._key))
        if dlg.result:
            self.set_color(dlg.result); self._page.on_color_changed(self._section,self._key,dlg.result)


# ── NoteGen section editor ────────────────────────────────────────────────────

class _NgSectionEditor(tk.Frame):
    def __init__(self,parent,section,notegen_page,**kw):
        super().__init__(parent,bg="#07090e",**kw)
        self._rows: dict = {}
        self._sf=_NgScrollFrame(self,bg="#07090e"); self._sf.pack(fill="both",expand=True)
        groups=_NG_GROUPS.get(section,[])
        if not groups: groups=[("All",list(_NG_DEFAULT_COLORS.get(section,{}).keys()))]
        row_idx=0
        for group_name,keys in groups:
            valid=[k for k in keys if k in _NG_DEFAULT_COLORS.get(section,{})]
            if not valid: continue
            hdr=_NgGroupHeader(self._sf.inner,group_name,count=len(valid)); hdr.pack(fill="x")
            cf=tk.Frame(self._sf.inner,bg="#07090e"); cf.pack(fill="x"); hdr.attach(cf)
            for key in valid:
                row=_NgColorRow(cf,section,key,notegen_page,row_idx)
                row.pack(fill="x"); self._rows[key]=row; row_idx+=1

    def push(self,color_dict):
        for key,row in self._rows.items(): row.set_color(color_dict.get(key,"#FFFFFF"))
        self._sf.scroll_top()

    def set_readonly(self,readonly):
        for row in self._rows.values(): row.set_readonly(readonly)


# ── NoteGen highway preview ───────────────────────────────────────────────────

class _NgHighwayPreview(tk.Frame):
    """
    Live guitar highway preview — 1:1 port of CHNoteGen's _HighwayPreview.
    Notes at the bottom, sustains running full-height to the top edge,
    SP stripe across the very top.
    """
    def __init__(self, parent, notegen_page, **kw):
        super().__init__(parent, bg=C["panel"], **kw)
        self._page = notegen_page
        self._photo_cache: dict = {}
        self._cv = tk.Canvas(self, bg="#07090e", highlightthickness=1,
                             highlightbackground=C["border"])
        self._cv.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._cv.bind("<Configure>", lambda _: self.refresh())

    # ── public ─────────────────────────────────────────────────────────────────
    def refresh(self):
        self._cv.delete("all")
        w, h = self._cv.winfo_width(), self._cv.winfo_height()
        if w < 20 or h < 20:
            return
        self._draw_guitar(w, h)

    def clear_photo_cache(self, hex_color=None):
        if hex_color is None:
            self._photo_cache.clear()
        else:
            for k in [k for k in self._photo_cache if k[0] == hex_color]:
                del self._photo_cache[k]

    # ── note image loader ───────────────────────────────────────────────────────
    def _get_note_photo(self, hex_color: str, pixel_size: int):
        if not _PIL_OK:
            return None
        key = (hex_color.upper(), pixel_size)
        if key in self._photo_cache:
            return self._photo_cache[key]
        tpl = _ng_find_template()
        if tpl is None:
            return None
        try:
            from PIL import Image as _PI, ImageTk as _ITk
            base    = _PI.open(str(tpl))
            colored = _ng_colorize_pil(base, hex_color)
            colored = colored.resize((pixel_size, pixel_size), _PI.LANCZOS)
            photo   = _ITk.PhotoImage(colored)
            self._photo_cache[key] = photo
            return photo
        except Exception:
            return None

    # ── dome note shape (1:1 from CHNoteGen) ───────────────────────────────────
    def _draw_dome_note(self, cv, cx: int, cy: int, col: str, nr: int):
        sh = int(nr * 0.22)
        cv.create_oval(cx - nr, cy + sh, cx + nr, cy + sh + int(nr * 0.42),
                       fill="#000000", outline="")
        sk_h = int(nr * 0.30); sk_y = cy + int(nr * 0.20)
        cv.create_oval(cx - nr, sk_y - sk_h, cx + nr, sk_y + sk_h,
                       fill=_ng_darken(col, 0.50), outline="")
        dw = int(nr * 0.82); dh = int(nr * 0.72)
        cv.create_oval(cx - dw, cy - dh, cx + dw, cy + int(nr * 0.26),
                       fill=col, outline="")
        cv.create_oval(cx - dw, cy + int(nr * 0.10), cx + dw, cy + int(nr * 0.36),
                       fill=_ng_darken(col, 0.72), outline="")
        hl_w = int(nr * 0.44); hl_h = int(nr * 0.26)
        hl_x = cx - int(nr * 0.14); hl_y = cy - int(nr * 0.42)
        cv.create_oval(hl_x - hl_w, hl_y - hl_h, hl_x + hl_w, hl_y + hl_h,
                       fill=_ng_lighten(col, 1.85), outline="")
        gr = max(3, int(nr * 0.20)); gy = cy - int(nr * 0.10)
        cv.create_oval(cx - gr, gy - gr, cx + gr, gy + gr, fill="#FFFFFF", outline="")

    # ── lane backgrounds with beat lines (1:1 from CHNoteGen) ──────────────────
    def _draw_lanes(self, cv, w: int, h: int, n: int, lane_tints: list):
        lw = w / n
        for i in range(n):
            x1, x2 = int(i * lw), int((i + 1) * lw)
            bg = _ng_alpha_blend(lane_tints[i], "#07090e", 0.10)
            cv.create_rectangle(x1, 0, x2, h, fill=bg, outline="")
            if i > 0:
                cv.create_line(x1, 0, x1, h, fill=C["border"], width=1)
        for frac in [0.25, 0.42, 0.58, 0.74]:
            y = int(h * frac)
            cv.create_line(0, y, w, y, fill=C["border"], width=1, dash=(2, 12))

    # ── sustain bar with rounded caps (1:1 from CHNoteGen) ─────────────────────
    def _draw_sustain(self, cv, cx: int, top: int, bottom: int,
                      col: str, sw: int):
        cv.create_rectangle(cx - sw, top + sw, cx + sw, bottom - sw,
                            fill=col, outline="")
        cv.create_oval(cx - sw, top,            cx + sw, top    + sw * 2, fill=col, outline="")
        cv.create_oval(cx - sw, bottom - sw * 2, cx + sw, bottom,         fill=col, outline="")

    # ── guitar highway (1:1 from CHNoteGen) ────────────────────────────────────
    def _draw_guitar(self, w: int, h: int):
        cv  = self._cv
        gc  = self._page._ng_active_colors().get("guitar", {})
        n   = len(_NG_GUITAR_LANES)
        lw  = w / n

        nr      = max(18, int(lw * 0.40))
        note_y  = h - nr - 14
        sw      = max(4, int(lw * 0.10))
        sus_top = -sw          # bleed above canvas so sustains reach the very top
        sus_bot = note_y

        self._draw_lanes(cv, w, h, n,
                         [gc.get(f"note_{l}", "#333") for l in _NG_GUITAR_LANES])

        # Sustains drawn before notes so notes sit on top
        for i, lane in enumerate(_NG_GUITAR_LANES):
            cx  = int(i * lw + lw / 2)
            col = gc.get(f"sustain_{lane}", "#888")
            self._draw_sustain(cv, cx, sus_top, sus_bot, col, sw)

        # SP stripe across the top (drawn over sustains as visual cutoff)
        cv.create_rectangle(0, 0, w, 4,
                            fill=gc.get("note_sp_active", "#00FFFF"), outline="")

        # Notes
        img_size = nr * 2
        for i, lane in enumerate(_NG_GUITAR_LANES):
            cx    = int(i * lw + lw / 2)
            col   = gc.get(f"note_{lane}", "#888")
            photo = self._get_note_photo(col, img_size)
            if photo is not None:
                cv.create_image(cx, note_y, image=photo, anchor="center")
            else:
                self._draw_dome_note(cv, cx, note_y, col, nr)

        cv.create_text(w // 2, h - 5, text="Guitar Highway",
                       font=("Segoe UI", 8), fill=C["text_dim"])


# ──────────────────────────────────────────────────────────────────────────────
#  SECTION 4 — BAD SONGS CLEANER
# ──────────────────────────────────────────────────────────────────────────────

def _deep_clean_path(path_str: str) -> str:
    match = re.search(r'\((([a-zA-Z]:\\.*?))\)', path_str)
    if match:
        path_str = match.group(1)
    if "e}" in path_str:
        path_str = path_str.split("e}")[0]
    return path_str.strip().rstrip("]")

def _parse_bad_songs(badsongs_path: str) -> list:
    if not badsongs_path or not os.path.exists(badsongs_path):
        return []
    bad_folders = set()
    in_error = False
    with open(badsongs_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("ERROR:"):
                in_error = True; continue
            if line.startswith("Warning:"):
                in_error = False; continue
            if in_error and ":\\" in line:
                bad_folders.add(_deep_clean_path(line))
    return list(bad_folders)


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION
# ──────────────────────────────────────────────────────────────────────────────

class CHSuite(tk.Tk):
    # ── init ──────────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.title("CHSuite  by JURMR")
        self.configure(bg=C["bg"])
        self.minsize(1200, 780)
        self.geometry("1350x860")

        # Set window icon from JURMRWEED.png if present
        try:
            _icon_path = _app_dir() / "JURMRWEED.png"
            if _icon_path.is_file() and _PIL_OK:
                _icon_img = ImageTk.PhotoImage(Image.open(str(_icon_path)))
                self.iconphoto(True, _icon_img)
                self._icon_img = _icon_img  # keep reference so GC doesn't destroy it
        except Exception:
            pass

        self._cfg      = _load_json(CONFIG_FILE, {})
        self._profiles = _load_profiles()

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

        # ── Discord Rich Presence ─────────────────────────────────────────────
        _client_id = self._cfg.get("discord_client_id", DISCORD_CLIENT_ID_DEFAULT)
        self._drpc  = _DiscordRPC(_client_id)
        self._update_discord_rpc()
        self._update_discord_dot()

    # ── styles ────────────────────────────────────────────────────────────────
    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=C["panel"], fieldbackground=C["panel"],
                    foreground=C["text"], bordercolor=C["border"],
                    rowheight=32, font=FT)
        s.map("Treeview",
              background=[("selected", C["selected"])],
              foreground=[("selected", C["text"])])
        s.configure("Treeview.Heading",
                    background=C["border"], foreground=C["text_mid"], font=FTS)
        s.configure("DE.TEntry",
                    fieldbackground=C["card2"], foreground=C["text"],
                    insertcolor=C["text"], bordercolor=C["border"])
        s.configure("Vertical.TScrollbar",
                    background=C["border"], troughcolor=C["panel"],
                    arrowcolor=C["text_dim"])
        s.configure("TCombobox",
                    fieldbackground=C["card2"], background=C["card2"],
                    foreground=C["text"], selectbackground=C["selected"],
                    selectforeground=C["text"])
        s.map("TCombobox",
              fieldbackground=[("readonly", C["card2"])],
              foreground=[("readonly", C["text"])])

    # ── top-level layout ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Title bar
        titlebar = tk.Frame(self, bg=C["panel"])
        titlebar.pack(fill="x")
        inner_tb = tk.Frame(titlebar, bg=C["panel"], padx=20, pady=12)
        inner_tb.pack(fill="x")
        tk.Label(inner_tb, text="⬡", font=("Segoe UI", 24),
                 bg=C["panel"], fg=C["accent"]).pack(side="left", padx=(0, 10))
        tk.Label(inner_tb, text="CHSuite",
                 font=FTT, bg=C["panel"], fg=C["text"]).pack(side="left")
        tk.Label(inner_tb, text="  by JURMR  v2.0",
                 font=("Segoe UI", 13), bg=C["panel"], fg=C["accent"]).pack(side="left", pady=(6,0))

        # Discord status dot
        self._discord_dot = tk.Label(inner_tb, text="⬤  Discord",
                                      font=("Segoe UI", 9), bg=C["panel"],
                                      fg=C["text_dim"], cursor="hand2", padx=12)
        self._discord_dot.pack(side="right")
        self._discord_dot.bind("<Button-1>", lambda e: self._discord_setup_prompt())

        # Launch Clone Hero button — always visible in titlebar
        self._launch_btn = tk.Button(
            inner_tb, text="▶  Launch Clone Hero",
            command=self._launch_clone_hero,
            bg=C["success"], fg="#000000",
            activebackground="#1aaa50", activeforeground="#000000",
            relief="flat", font=("Segoe UI", 9, "bold"),
            padx=14, pady=5, cursor="hand2")
        self._launch_btn.pack(side="right", padx=(0, 8))

        # Body: left nav + content pane
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # Left navigation sidebar
        self._nav = tk.Frame(body, bg=C["sidebar"], width=200)
        self._nav.pack(side="left", fill="y")
        self._nav.pack_propagate(False)

        # Content area
        self._content = tk.Frame(body, bg=C["bg"])
        self._content.pack(side="left", fill="both", expand=True)

        self._pages = {}
        self._nav_btns = {}
        self._current_page = None

        self._build_nav()
        self._build_page_bgchanger()
        self._build_page_namegen()
        self._build_page_notegen()
        self._build_page_cleaner()
        self._build_page_patcher()
        self._build_page_gamemanager()

        self._show_page("bgchanger")

    # ── navigation sidebar ────────────────────────────────────────────────────
    def _build_nav(self):
        tk.Frame(self._nav, bg=C["sidebar"], height=20).pack()

        logo_frame = tk.Frame(self._nav, bg=C["sidebar"])
        logo_frame.pack(fill="x", padx=16, pady=(0, 20))
        tk.Label(logo_frame, text="TOOLS", font=("Segoe UI", 7, "bold"),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(anchor="w")
        _sep(logo_frame, bg=C["border"]).pack(fill="x", pady=(6, 0))

        # Each nav item: (page_id, icon_char, label_text)
        # Icons are drawn in a fixed-width Label so text always starts at
        # the same x position regardless of glyph width.
        nav_items = [
            ("bgchanger",    "◈", "CHMenuChanger"),
            ("namegen",      "✦", "CHNameGen"),
            ("notegen",      "♪", "CHNoteGen"),
            ("cleaner",      "⊘", "CHCleaner"),
            ("patcher",      "⚙", "CHPatcher"),
            ("gamemanager",  "▦", "CHManager"),
        ]
        for page_id, icon, label in nav_items:
            # Outer frame acts as the clickable "button"
            btn_frame = tk.Frame(self._nav, bg=C["sidebar"], cursor="hand2")
            btn_frame.pack(fill="x")

            icon_lbl = tk.Label(btn_frame,
                                text=icon,
                                font=("Segoe UI", 11),
                                width=2,          # fixed char-width → always same offset
                                anchor="center",
                                bg=C["sidebar"], fg=C["text_dim"])
            icon_lbl.pack(side="left", padx=(14, 0), pady=10)

            text_lbl = tk.Label(btn_frame,
                                text=label,
                                font=("Segoe UI", 10),
                                anchor="w",
                                bg=C["sidebar"], fg=C["text_mid"])
            text_lbl.pack(side="left", padx=(6, 14), pady=10, fill="x", expand=True)

            # Bind click + hover to every part of the row
            cmd = lambda p=page_id: self._show_page(p)
            for w in (btn_frame, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda e, c=cmd: c())
                w.bind("<Enter>",
                       lambda e, f=btn_frame, il=icon_lbl, tl=text_lbl:
                           self._nav_hover(f, il, tl, True))
                w.bind("<Leave>",
                       lambda e, f=btn_frame, il=icon_lbl, tl=text_lbl:
                           self._nav_hover(f, il, tl, False))

            # Store references so _show_page can update active state
            self._nav_btns[page_id] = (btn_frame, icon_lbl, text_lbl)

        # Version at bottom
        tk.Frame(self._nav, bg=C["sidebar"]).pack(fill="y", expand=True)
        tk.Label(self._nav, text="CHSuite v2.0", font=("Segoe UI", 8),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(pady=(0, 12))

    def _nav_hover(self, frame, icon_lbl, text_lbl, entering: bool):
        """Lighten the row on hover, but only if it isn't the active page."""
        # Check if this row is the active one
        for pid, refs in self._nav_btns.items():
            if refs[0] is frame and pid == self._current_page:
                return   # active row — don't override its style
        bg = C["nav_hover"] if entering else C["sidebar"]
        fg_icon = C["text"] if entering else C["text_dim"]
        fg_text = C["text"] if entering else C["text_mid"]
        frame.config(bg=bg)
        icon_lbl.config(bg=bg, fg=fg_icon)
        text_lbl.config(bg=bg, fg=fg_text)

    def _show_page(self, page_id):
        for pg in self._pages.values():
            pg.pack_forget()
        if page_id in self._pages:
            self._pages[page_id].pack(fill="both", expand=True)
            self._current_page = page_id
        for pid, (frame, icon_lbl, text_lbl) in self._nav_btns.items():
            if pid == page_id:
                frame.config(bg=C["nav_active"])
                icon_lbl.config(bg=C["nav_active"], fg="white",
                                font=("Segoe UI", 11, "bold"))
                text_lbl.config(bg=C["nav_active"], fg="white",
                                font=("Segoe UI", 10, "bold"))
            else:
                frame.config(bg=C["sidebar"])
                icon_lbl.config(bg=C["sidebar"], fg=C["text_dim"],
                                font=("Segoe UI", 11))
                text_lbl.config(bg=C["sidebar"], fg=C["text_mid"],
                                font=("Segoe UI", 10))
        # Update Discord activity whenever the active tab changes
        if hasattr(self, "_drpc"):
            self._update_discord_rpc()

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 1 — BG CHANGER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_bgchanger(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["bgchanger"] = page

        # ── Profile bar ───────────────────────────────────────────────────────
        prof_bar = tk.Frame(page, bg=C["card2"],
                            highlightbackground=C["border"], highlightthickness=1)
        prof_bar.pack(fill="x")
        pi = tk.Frame(prof_bar, bg=C["card2"], padx=14, pady=7); pi.pack(fill="x")
        tk.Label(pi, text="PROFILE:", font=FTB,
                 bg=C["card2"], fg=C["text_mid"]).pack(side="left")
        self._prof_var = tk.StringVar()
        self._prof_cb  = ttk.Combobox(pi, textvariable=self._prof_var,
                                       width=30, font=FT, state="readonly")
        self._prof_cb.pack(side="left", padx=8)
        self._prof_cb.bind("<<ComboboxSelected>>", self._on_profile_combo)

        def pbtn(label, cmd, bg=C["border"]):
            return tk.Button(pi, text=label, command=cmd,
                             bg=bg, fg=C["text"], relief="flat",
                             font=FT, padx=9, pady=3, cursor="hand2")
        pbtn("+ New",     self._profile_new).pack(side="left", padx=2)
        self._btn_rename = pbtn("Rename",    self._profile_rename)
        self._btn_rename.pack(side="left", padx=2)
        pbtn("Duplicate", self._profile_duplicate).pack(side="left", padx=2)
        self._btn_delete = pbtn("Delete",    self._profile_delete, "#3d1a1a")
        self._btn_delete.pack(side="left", padx=2)
        self._lock_lbl = tk.Label(pi, text="", font=FTS, bg=C["card2"], fg=C["warn"])
        self._lock_lbl.pack(side="left", padx=(10, 0))

        # Reminder to set default install in the launcher (right-aligned so it never gets clipped)
        tk.Label(pi,
                 text="ℹ  If backgrounds aren't saving, open the Launcher → Settings and set this install as your default.",
                 font=("Segoe UI", 8), bg=C["card2"], fg=C["text_dim"]).pack(side="right", padx=(14, 0))
        self._refresh_profile_combo()

        # ── Data folder bar ───────────────────────────────────────────────────
        ggm_bar = tk.Frame(page, bg=C["card"],
                           highlightbackground=C["border"], highlightthickness=1)
        ggm_bar.pack(fill="x")
        gi = tk.Frame(ggm_bar, bg=C["card"], padx=14, pady=9); gi.pack(fill="x")
        tk.Label(gi, text="Clone Hero_Data folder:", font=FTB,
                 bg=C["card"], fg=C["text_mid"]).pack(side="left")
        self._data_v = tk.StringVar(value=_get_default_data())
        ttk.Entry(gi, textvariable=self._data_v,
                  width=56, font=FTM, style="DE.TEntry").pack(side="left", padx=8)
        tk.Button(gi, text="Browse…", command=self._browse_data,
                  bg=C["accent_dim"], fg=C["text"], relief="flat",
                  font=FT, padx=10, pady=3, cursor="hand2").pack(side="left", padx=2)
        tk.Button(gi, text="Load & Scan", command=self._load_ggm,
                  bg=C["accent"], fg="white", relief="flat",
                  font=FTB, padx=14, pady=3, cursor="hand2").pack(side="left", padx=2)
        self._backup_lbl = tk.Label(gi, text="", font=FTS, bg=C["card"], fg=C["text_dim"])
        self._backup_lbl.pack(side="right", padx=(0, 4))
        tk.Button(gi, text="Restore Backups", command=self._act_restore_backups,
                  bg=C["border"], fg=C["text_dim"], relief="flat",
                  font=FTS, padx=8, pady=2, cursor="hand2").pack(side="right", padx=4)

        # ── Main area ─────────────────────────────────────────────────────────
        main = tk.Frame(page, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=10, pady=8)

        # BG tree sidebar
        side = tk.Frame(main, bg=C["panel"], width=218)
        side.pack(side="left", fill="y", padx=(0, 8)); side.pack_propagate(False)
        tk.Label(side, text="BACKGROUNDS", font=("Segoe UI", 8, "bold"),
                 bg=C["panel"], fg=C["accent"], pady=7).pack(fill="x", padx=12)
        lf  = tk.Frame(side, bg=C["panel"]); lf.pack(fill="both", expand=True, padx=6, pady=(0,6))
        vsb = ttk.Scrollbar(lf, orient="vertical")
        self._tree = ttk.Treeview(lf, selectmode="browse", show="tree",
                                   yscrollcommand=vsb.set, height=22)
        self._tree.column("#0", width=195)
        vsb.config(command=self._tree.yview)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tiid = {}
        for bg in BACKGROUNDS:
            iid = self._tree.insert("", "end", text=f"  {bg}")
            self._tiid[iid] = bg
        self._tree.selection_set(list(self._tiid.keys())[0])

        # Preview + controls
        right = tk.Frame(main, bg=C["bg"]); right.pack(side="left", fill="both", expand=True)
        prow  = tk.Frame(right, bg=C["bg"]); prow.pack(fill="both", expand=True)
        self._orig_card = self._make_bg_card(prow, "CURRENT  (in-game)", C["text_dim"])
        self._orig_card.pack(side="left", fill="both", expand=True, padx=(0,5))
        self._new_card  = self._make_bg_card(prow, "REPLACEMENT  (new)",  C["accent2"])
        self._new_card.pack(side="left", fill="both", expand=True, padx=(5,0))

        ctrl = tk.Frame(right, bg=C["panel"], padx=14, pady=9)
        ctrl.pack(fill="x", pady=(8, 0))
        self._sel_lbl = tk.Label(ctrl, text="Selected: -",
                                  font=FTH, bg=C["panel"], fg=C["text"])
        self._sel_lbl.pack(side="left")
        self._req_lbl = tk.Label(ctrl, text="", font=FTS, bg=C["panel"], fg=C["text_dim"])
        self._req_lbl.pack(side="left", padx=(10, 0))
        br = tk.Frame(ctrl, bg=C["panel"]); br.pack(side="right")
        def cbtn(t, cmd, bg=C["border"], fg=C["text"], bold=False):
            return tk.Button(br, text=t, command=cmd, bg=bg, fg=fg,
                             relief="flat", font=(FTB if bold else FT),
                             padx=11, pady=5, cursor="hand2")
        cbtn("▶ Export Original",    self._act_export_orig).pack(side="left", padx=3)
        cbtn("📂 Choose Replacement", self._act_choose_replacement, C["accent_dim"]).pack(side="left", padx=3)
        cbtn("✖ Clear",               self._act_clear_replacement).pack(side="left", padx=3)
        self._apply_btn = cbtn("✔  Apply & Save", self._act_apply_all, C["accent2"], "white", True)
        self._apply_btn.pack(side="left", padx=3)

        # Status bar
        sbar = tk.Frame(page, bg=C["panel"], pady=5)
        sbar.pack(fill="x", side="bottom")
        tk.Label(sbar, textvariable=self._status_v, font=FTM,
                 bg=C["panel"], fg=C["text_mid"], padx=14).pack(side="left")

    def _make_bg_card(self, parent, label, label_fg):
        card = tk.Frame(parent, bg=C["card"],
                        highlightbackground=C["border"], highlightthickness=1)
        tk.Label(card, text=label, font=("Segoe UI", 9, "bold"),
                 bg=C["card"], fg=label_fg, pady=5).pack(fill="x", padx=10)
        cv = tk.Canvas(card, bg=C["bg"], bd=0, highlightthickness=0, height=295)
        cv.pack(fill="both", expand=True, padx=6, pady=(0, 3))
        info = tk.Label(card, text="", font=FTS, bg=C["card"], fg=C["text_dim"])
        info.pack(pady=(0, 5))
        card._cv        = cv
        card._info      = info
        card._ph_text   = ""   # track current placeholder text so resize can redraw it
        cv.bind("<Configure>", lambda e, c=cv, k=card: self._on_bg_resize(c, k))
        # Don't draw placeholder at construction time — canvas has no real size yet.
        # It will be drawn correctly on the first <Configure> event once laid out.
        return card

    # ── BG profile management ─────────────────────────────────────────────────
    def _load_initial_profile(self):
        if DEFAULT_PROFILE_NAME not in self._profiles:
            self._profiles[DEFAULT_PROFILE_NAME] = _blank_profile(DEFAULT_PROFILE_NAME)
        self._profiles[DEFAULT_PROFILE_NAME]["locked"] = True
        self._profiles[DEFAULT_PROFILE_NAME]["replacements"] = {}
        _save_profiles(self._profiles)
        last = self._cfg.get("last_profile", "")
        if last and last in self._profiles:
            self._switch_profile(last)
        elif self._profiles:
            self._switch_profile(next(iter(self._profiles)))

        # Show setup dialog on first launch to capture the CH install directory
        if not self._cfg.get("setup_done", False):
            dlg = SetupDialog(self)
            self.wait_window(dlg.win)
            if dlg.result:
                self._data_v.set(dlg.result)
                if not self._is_default_profile():
                    self._active_prof["data_path"] = dlg.result
                    _save_profiles(self._profiles)
                self._cfg["default_data_path"] = dlg.result
            self._cfg["setup_done"] = True
            _save_json(CONFIG_FILE, self._cfg)

    def _refresh_profile_combo(self):
        names = sorted(self._profiles.keys(),
                       key=lambda n: (0 if n == DEFAULT_PROFILE_NAME else 1, n))
        self._prof_cb["values"] = names
        if self._active_name in names:
            self._prof_var.set(self._active_name)
        elif names:
            self._prof_var.set(names[0])

    def _on_profile_combo(self, _=None):
        n = self._prof_var.get()
        if n and n != self._active_name:
            self._switch_profile(n)

    def _switch_profile(self, name):
        if name not in self._profiles: return
        self._active_name = name
        self._active_prof = self._profiles[name]
        self._prof_var.set(name)
        self._cfg["last_profile"] = name
        _save_json(CONFIG_FILE, self._cfg)
        self._data_v.set(self._active_prof.get("data_path", DEFAULT_DATA))
        self._am = None
        self._asset_cache.clear(); self._orig_pil.clear()
        self._new_pil.clear(); self._orig_tk.clear(); self._new_tk.clear()
        self._bg_refresh_tree()
        self._status(f"Profile: {name}")
        if hasattr(self, "_backup_lbl"):
            self._backup_lbl.config(text="", fg=C["text_dim"])
        if hasattr(self, "_btn_rename"):
            locked = self._is_default_profile(name)
            s = "disabled" if locked else "normal"
            fg = C["text_dim"] if locked else C["text"]
            self._btn_rename.config(state=s, fg=fg)
            self._btn_delete.config(state=s, fg=fg)
            self._lock_lbl.config(
                text="🔒  Read-only" if locked else "")
        self._bg_refresh_panels()

    def _is_default_profile(self, name=None):
        n = name if name is not None else self._active_name
        return n == DEFAULT_PROFILE_NAME or self._profiles.get(n, {}).get("locked", False)

    def _profile_new(self):
        name = simpledialog.askstring("New Profile", "Profile name:", parent=self)
        if not name or not name.strip(): return
        name = name.strip()
        if name == DEFAULT_PROFILE_NAME:
            messagebox.showwarning("Reserved", "That name is reserved."); return
        if name in self._profiles:
            messagebox.showwarning("Exists", f"Profile '{name}' already exists."); return
        self._profiles[name] = _blank_profile(name)
        _save_profiles(self._profiles)
        self._refresh_profile_combo(); self._switch_profile(name)

    def _profile_rename(self):
        old = self._active_name
        if not old or self._is_default_profile(old):
            messagebox.showwarning("Locked", "Cannot rename the Default profile."); return
        name = simpledialog.askstring("Rename", f"Rename '{old}' to:",
                                       initialvalue=old, parent=self)
        if not name or not name.strip() or name.strip() == old: return
        name = name.strip()
        if name in self._profiles:
            messagebox.showwarning("Exists", f"Profile '{name}' already exists."); return
        self._profiles[name] = self._profiles.pop(old)
        self._profiles[name]["name"] = name
        _save_profiles(self._profiles); self._active_name = name
        self._cfg["last_profile"] = name; _save_json(CONFIG_FILE, self._cfg)
        self._refresh_profile_combo()

    def _profile_duplicate(self):
        src = self._active_name
        if not src: return
        default_name = "My Theme" if self._is_default_profile(src) else src + " Copy"
        name = simpledialog.askstring("Duplicate", f"Name for copy of '{src}':",
                                       initialvalue=default_name, parent=self)
        if not name or not name.strip(): return
        name = name.strip()
        if name in self._profiles:
            messagebox.showwarning("Exists", f"Profile '{name}' already exists."); return
        self._profiles[name] = copy.deepcopy(self._profiles[src])
        self._profiles[name]["name"] = name
        self._profiles[name].pop("locked", None)
        _save_profiles(self._profiles); self._refresh_profile_combo()
        self._switch_profile(name)

    def _profile_delete(self):
        name = self._active_name
        if not name or self._is_default_profile(name):
            messagebox.showwarning("Locked", "Cannot delete the Default profile."); return
        non_default = [n for n in self._profiles if not self._is_default_profile(n)]
        if len(non_default) <= 1:
            messagebox.showwarning("Cannot delete",
                                   "You must keep at least one profile besides Default."); return
        if not messagebox.askyesno("Delete Profile", f"Delete '{name}'? This cannot be undone."):
            return
        del self._profiles[name]; _save_profiles(self._profiles)
        self._refresh_profile_combo(); self._switch_profile(next(iter(self._profiles)))

    # ── BG loading ────────────────────────────────────────────────────────────
    def _browse_data(self):
        p = filedialog.askdirectory(title="Select Clone Hero_Data folder",
                                    initialdir=str(Path.home()/"Documents"/"Clone Hero"))
        if p: self._data_v.set(p)

    def _load_ggm(self):
        if not _PIL_OK or not _UNITYPY_OK:
            messagebox.showerror("Missing dependencies",
                "Pillow and UnityPy are required for the BG Changer.\n\n"
                "Restart CHSuite to be prompted to install them."); return
        path = self._data_v.get().strip()
        if not os.path.isdir(path):
            messagebox.showerror("Not found",
                "Folder not found:\n" + path +
                "\n\nPlease select your Clone Hero_Data folder."); return
        if not self._is_default_profile():
            self._active_prof["data_path"] = path
            _save_profiles(self._profiles)
        self._status("Scanning " + path + " ...")
        self.update_idletasks()

        def worker():
            try:
                am = AssetManager(path)
                needs = am.needs_backup()
                if needs:
                    created, bk_errors = am.create_backups()
                    if bk_errors:
                        self.after(0, lambda: messagebox.showwarning(
                            "Backup warning",
                            "Some files could not be backed up:\n\n" +
                            "\n".join(bk_errors)))
                self.after(0, lambda: self._on_ggm_ready(am))
            except Exception as ex:
                msg = str(ex)
                self.after(0, lambda: (
                    self._status("Load error: " + msg),
                    messagebox.showerror("Load Error",
                        "Could not scan folder:\n\n" + msg +
                        "\n\nMake sure you selected the Clone Hero_Data folder.")))
        threading.Thread(target=worker, daemon=True).start()

    def _on_ggm_ready(self, am):
        self._am = am; self._asset_cache.clear()
        self._orig_pil.clear(); self._orig_tk.clear()
        all_names = am.texture_names()
        for bg in BACKGROUNDS:
            self._asset_cache[bg] = am.find_for_bg(bg)
        found = sum(1 for v in self._asset_cache.values() if v is not None)
        backed_up = am.has_full_backup()
        self._update_backup_indicator(backed_up, am)
        bk_note = "  ✓ Backups ready." if backed_up else "  ⚠ Creating backups…"
        self._status("Scanned {} — {} textures, {}/{} backgrounds matched.{}".format(
            Path(am.data_dir).name, len(all_names), found, len(BACKGROUNDS), bk_note))
        self._bg_refresh_tree(); self._bg_refresh_panels()

    def _update_backup_indicator(self, backed_up, am=None):
        if backed_up:
            bd_name = am.BACKUP_DIR_NAME if am else "_CH_BG_Backups"
            self._backup_lbl.config(text="✓ Backups in " + bd_name, fg=C["success"])
        else:
            self._backup_lbl.config(text="⚠ No backups yet", fg=C["warn"])

    def _act_restore_backups(self):
        if self._am is None:
            messagebox.showwarning("No folder", "Load a Clone Hero_Data folder first."); return
        bd = self._am.backup_dir()
        if not os.path.isdir(bd):
            messagebox.showinfo("No backups", "No backup folder found at:\n" + bd); return
        backup_files = [f for f in Path(bd).iterdir() if f.is_file()]
        if not backup_files:
            messagebox.showinfo("No backups", "Backup folder is empty."); return
        names = "\n".join("  " + f.name for f in backup_files)
        if not messagebox.askyesno("Restore backups",
                "Overwrite current files with originals from backup?\n\n" + names + "\n\nProceed?"):
            return
        errors = []; restored = []
        for bk in backup_files:
            dest = Path(self._am.data_dir) / bk.name
            try:
                shutil.copy2(str(bk), str(dest)); restored.append(bk.name)
            except Exception as e:
                errors.append(f"{bk.name}: {e}")
        if errors:
            messagebox.showerror("Restore errors", "\n".join(errors))
        else:
            self._status(f"Restored {len(restored)} file(s) from backup.")
            messagebox.showinfo("Restored",
                f"Restored {len(restored)} file(s).\n\nReload the folder to continue editing.")
            self._orig_pil.clear(); self._orig_tk.clear()
            self._am = None; self._asset_cache.clear()
            if hasattr(self, "_backup_lbl"):
                self._backup_lbl.config(text="", fg=C["text_dim"])
            self._load_ggm()

    # ── BG tree / panels ──────────────────────────────────────────────────────
    def _bg_refresh_tree(self):
        reps = self._active_prof.get("replacements", {})
        for iid, bg in self._tiid.items():
            has_rep = bool(reps.get(bg) and os.path.isfile(reps[bg]))
            matched  = self._asset_cache.get(bg) is not None
            icon = ("✎ " if (has_rep and matched)
                    else "⚠ " if (has_rep and not matched)
                    else "  ")
            self._tree.item(iid, text=f"{icon}{bg}")

    def _selected_bg(self):
        sel = self._tree.selection()
        if sel: return self._tiid.get(sel[0], BACKGROUNDS[0])
        return BACKGROUNDS[0]

    def _on_tree_select(self, _=None):
        bg = self._selected_bg()
        w, h   = required_size(bg)
        exact  = exact_match_required(bg)
        self._sel_lbl.config(text=f"Selected: {bg}")
        self._req_lbl.config(text=f"{'Exact' if exact else 'Min'}: {w}×{h}")
        self._bg_refresh_panels()
        # Update Discord activity to reflect the selected background
        if hasattr(self, "_drpc"):
            self._update_discord_rpc()

    def _bg_refresh_panels(self):
        bg = self._selected_bg()
        if bg in self._orig_pil:
            self._orig_card._ph_text = ""
            self._bg_put_image(self._orig_card, self._orig_pil[bg], "orig", bg)
        elif self._am is not None:
            an = self._asset_cache.get(bg)
            if an:
                self._bg_placeholder(self._orig_card._cv, "Loading\u2026")
                self._orig_card._info.config(text="")
                am = self._am
                def _load(am=am, bg=bg, an=an):
                    img, err = am.export_image(an)
                    self.after(0, lambda: self._on_orig_ready(bg, an, img, err))
                threading.Thread(target=_load, daemon=True).start()
            else:
                self._bg_placeholder(self._orig_card._cv,
                                     f"No Texture2D matched for '{bg}'")
                self._orig_card._info.config(text="")
        else:
            self._bg_placeholder(self._orig_card._cv,
                                  "Select and scan a Clone Hero_Data folder first.")
            self._orig_card._info.config(text="")

        reps     = self._active_prof.get("replacements", {})
        rep_path = reps.get(bg, "")
        if bg in self._new_pil:
            self._new_card._ph_text = ""
            self._bg_put_image(self._new_card, self._new_pil[bg], "new", bg)
        elif rep_path and os.path.isfile(rep_path):
            try:
                img = Image.open(rep_path).convert("RGBA")
                self._new_pil[bg] = img
                self._new_card._ph_text = ""
                self._bg_put_image(self._new_card, img, "new", bg)
                w, h = img.size
                self._new_card._info.config(text=f"{w}\u00d7{h}  |  {Path(rep_path).name}",
                                            fg=C["success"])
            except Exception:
                self._bg_placeholder(self._new_card._cv, "Could not load replacement image")
                self._new_card._info.config(text="")
        else:
            self._bg_placeholder(self._new_card._cv, "No replacement selected")
            self._new_card._info.config(text="")

    def _on_orig_ready(self, bg, asset_name, img, err=None):
        if img:
            self._orig_pil[bg] = img
            if self._selected_bg() == bg:
                self._bg_put_image(self._orig_card, img, "orig", bg)
                w, h = img.size
                self._orig_card._info.config(text=f"{w}×{h}  |  {asset_name}",
                                             fg=C["text_mid"])
        else:
            if self._selected_bg() == bg:
                short_err = (err or "unknown error")[:300]
                self._bg_placeholder(self._orig_card._cv,
                                     f"Could not decode '{asset_name}'\n{short_err}")
                self._orig_card._info.config(text="Decode failed", fg=C["error"])

    def _bg_put_image(self, card, pil, key, bg):
        cv = card._cv; cv.update_idletasks()
        cw = cv.winfo_width() or 520; ch = cv.winfo_height() or 295
        ph = pil.copy(); ph.thumbnail((cw-10, ch-10), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(ph)
        cv.delete("all")
        cv.create_rectangle(0, 0, cw, ch, fill=C["bg"], outline="")
        cv.create_image(cw//2, ch//2, image=tk_img, anchor="center")
        (self._orig_tk if key == "orig" else self._new_tk)[bg] = tk_img

    def _on_bg_resize(self, cv, card):
        bg = self._selected_bg()
        if card is self._orig_card and bg in self._orig_pil:
            self._bg_put_image(self._orig_card, self._orig_pil[bg], "orig", bg)
        elif card is self._new_card and bg in self._new_pil:
            self._bg_put_image(self._new_card, self._new_pil[bg], "new", bg)
        else:
            # Redraw placeholder at the new correct canvas size
            ph = getattr(card, "_ph_text", "")
            if ph:
                self._bg_placeholder(cv, ph)
            else:
                # First-time draw — pull the right message from current state
                self._bg_refresh_panels()

    def _bg_placeholder(self, cv: tk.Canvas, text: str):
        cv.update_idletasks()
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 20: w = 520
        if h < 20: h = 295
        cv.delete("all")
        cv.create_rectangle(1, 1, w-1, h-1, outline=C["border"], fill=C["bg"])
        cv.create_text(w//2, h//2, text=text, fill=C["text_dim"], font=FT, width=w-40)
        # Find the card that owns this canvas and remember the text for resize redraws
        for card in (self._orig_card, self._new_card):
            if hasattr(card, "_cv") and card._cv is cv:
                card._ph_text = text
                break

    # ── BG action buttons ─────────────────────────────────────────────────────
    def _act_export_orig(self):
        if self._am is None:
            messagebox.showwarning("No folder", "Select and scan a Clone Hero_Data folder first.")
            return
        bg = self._selected_bg(); an = self._asset_cache.get(bg)
        if not an:
            messagebox.showwarning("Not found", f"No texture matched for '{bg}'."); return
        out = filedialog.asksaveasfilename(
            title=f"Export '{bg}' as PNG", defaultextension=".png",
            initialfile=f"{bg.replace(' ','_')}_original.png",
            filetypes=[("PNG", "*.png")])
        if not out: return
        img = self._orig_pil.get(bg)
        if img is None: img, err = self._am.export_image(an)
        else: err = None
        if img:
            img.save(out); self._status(f"Exported: {out}")
            messagebox.showinfo("Exported", f"Saved to:\n{out}")
        else:
            messagebox.showerror("Export failed",
                "Could not decode texture.\n\n" + (err or "unknown error"))

    def _act_choose_replacement(self):
        if self._is_default_profile():
            if messagebox.askyesno("Create a profile first",
                    "The Default profile is read-only.\nCreate a new profile to set replacements?"):
                self._profile_new(); return
            return
        bg   = self._selected_bg()
        path = filedialog.askopenfilename(
            title=f"Choose replacement for '{bg}'",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tga"), ("All", "*")])
        if not path: return
        try: img = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Image error", f"Cannot open:\n{e}"); return
        iw, ih = img.size; rw, rh = required_size(bg)
        if exact_match_required(bg):
            if iw != rw or ih != rh:
                messagebox.showerror("Wrong size",
                    f"'{bg}' requires exactly {rw}×{rh} px.\nYour image is {iw}×{ih}."); return
        else:
            if iw < rw or ih < rh:
                messagebox.showerror("Too small",
                    f"'{bg}' needs at least {rw}×{rh} px.\nYour image is only {iw}×{ih}."); return
        reps = self._active_prof.setdefault("replacements", {})
        reps[bg] = path; _save_profiles(self._profiles)
        self._new_pil[bg] = img; self._new_tk.pop(bg, None)
        self._bg_put_image(self._new_card, img, "new", bg)
        self._new_card._info.config(text=f"{iw}×{ih}  ✓  |  {Path(path).name}", fg=C["success"])
        self._bg_refresh_tree(); self._status(f"Replacement set for '{bg}'.")

    def _act_clear_replacement(self):
        if self._is_default_profile(): return
        bg = self._selected_bg()
        self._active_prof.get("replacements", {}).pop(bg, None)
        _save_profiles(self._profiles)
        self._new_pil.pop(bg, None); self._new_tk.pop(bg, None)
        self._bg_placeholder(self._new_card._cv, "No replacement selected")
        self._new_card._info.config(text="")
        self._bg_refresh_tree(); self._status(f"Cleared replacement for '{bg}'.")

    def _act_apply_all(self):
        if self._am is None:
            messagebox.showwarning("No folder", "Select and scan a Clone Hero_Data folder first.")
            return
        if self._is_default_profile():
            if messagebox.askyesno("Create a profile first",
                    "You are on the read-only Default profile.\nCreate a new profile now?"):
                self._profile_new(); return
            return
        reps = self._active_prof.get("replacements", {})
        if not reps:
            messagebox.showwarning("Nothing to apply", "Set at least one replacement image first.")
            return
        if not self._am.has_full_backup():
            messagebox.showerror("No backup",
                "Backups have not been created yet.\nReload the folder to trigger backup creation.")
            return
        summary = []; skipped = []
        for bg, img_path in reps.items():
            an = self._asset_cache.get(bg)
            src_file = self._am.source_file(an) if an else None
            if an and os.path.isfile(img_path):
                label = Path(src_file).name if src_file else "?"
                summary.append(f"  {bg}  ->  {Path(img_path).name}  ({label})")
            else:
                reason = "texture not found" if not an else "image file missing"
                skipped.append(f"  {bg}  ({reason})")
        if not summary:
            messagebox.showwarning("Nothing applicable",
                "None of the replacements can be applied.\n\n" + "\n".join(skipped)); return
        msg = "\n".join(summary)
        if skipped: msg += "\n\nSkipped:\n" + "\n".join(skipped)
        if not messagebox.askyesno("Apply & Save in-place",
                "Apply these replacements directly to Clone Hero_Data:\n\n" +
                msg + "\n\nOriginals are backed up in _CH_BG_Backups.\nProceed?"):
            return
        self._status("Applying…"); self.update_idletasks()
        self._apply_btn.config(state="disabled")

        def worker():
            errors = []; applied = 0
            for bg, img_path in reps.items():
                an = self._asset_cache.get(bg)
                if not an: errors.append(f"'{bg}': no matching texture found"); continue
                if not os.path.isfile(img_path): errors.append(f"'{bg}': image missing"); continue
                try:
                    pil = Image.open(img_path).convert("RGBA")
                    ok  = self._am.import_image(an, pil)
                    if ok: applied += 1
                    else: errors.append(f"'{bg}': import_image returned False")
                except Exception as ex:
                    errors.append(f"'{bg}': {ex}")
            if applied == 0:
                def fail():
                    self._apply_btn.config(state="normal")
                    self._status("Apply failed.")
                    messagebox.showerror("Apply failed",
                        "No textures could be written.\n\nErrors:\n" + "\n".join(errors))
                self.after(0, fail); return
            saved, save_errors = self._am.save_modified()
            errors.extend(save_errors)
            def done():
                self._apply_btn.config(state="normal")
                if saved:
                    file_list = "\n".join("  " + Path(p).name for p in saved)
                    extra = ("\n\nWarnings:\n" + "\n".join(errors)) if errors else ""
                    self._status(f"{applied} texture(s) applied in-place.")
                    messagebox.showinfo("Done!",
                        f"Applied {applied} texture(s).\n\nModified:\n{file_list}\n\n"
                        f"Restart Clone Hero to see the changes.{extra}")
                    self._orig_pil.clear(); self._orig_tk.clear()
                else:
                    self._status("Save FAILED.")
                    messagebox.showerror("Save failed",
                        "Textures were patched but could not be saved.\n\n" + "\n".join(errors))
            self.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def _status(self, msg):
        self._status_v.set(msg); self.update_idletasks()

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 2 — NAME GENERATOR
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_namegen(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["namegen"] = page

        # Inner layout: left sub-nav + right content
        left_nav = tk.Frame(page, bg=C["sidebar"], width=170)
        left_nav.pack(side="left", fill="y"); left_nav.pack_propagate(False)
        right_area = tk.Frame(page, bg=C["bg"])
        right_area.pack(side="left", fill="both", expand=True)

        # Sub-pages
        self._ng_pages = {}
        self._ng_nav_btns = {}
        self._ng_current  = None

        # Sub-nav header
        tk.Frame(left_nav, bg=C["sidebar"], height=20).pack()
        tk.Label(left_nav, text="MODE", font=("Segoe UI", 7, "bold"),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(anchor="w", padx=16)
        _sep(left_nav, bg=C["border"]).pack(fill="x", padx=16, pady=(4, 0))

        ng_items = [
            ("gradient",   "◈", "Gradient"),
            ("individual", "✦", "Per-Letter"),
        ]
        for pid, icon, label in ng_items:
            btn_frame = tk.Frame(left_nav, bg=C["sidebar"], cursor="hand2")
            btn_frame.pack(fill="x")
            icon_lbl = tk.Label(btn_frame, text=icon, font=("Segoe UI", 11),
                                width=2, anchor="center",
                                bg=C["sidebar"], fg=C["text_dim"])
            icon_lbl.pack(side="left", padx=(14, 0), pady=10)
            text_lbl = tk.Label(btn_frame, text=label, font=("Segoe UI", 10),
                                anchor="w", bg=C["sidebar"], fg=C["text_mid"])
            text_lbl.pack(side="left", padx=(6, 14), pady=10, fill="x", expand=True)
            cmd = lambda p=pid: self._ng_show(p)
            for w in (btn_frame, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda e, c=cmd: c())
                w.bind("<Enter>",
                       lambda e, f=btn_frame, il=icon_lbl, tl=text_lbl:
                           self._ng_hover(f, il, tl, True))
                w.bind("<Leave>",
                       lambda e, f=btn_frame, il=icon_lbl, tl=text_lbl:
                           self._ng_hover(f, il, tl, False))
            self._ng_nav_btns[pid] = (btn_frame, icon_lbl, text_lbl)

        # Build sub-pages
        self._build_ng_gradient(right_area)
        self._build_ng_individual(right_area)
        self._ng_show("gradient")

    def _ng_hover(self, frame, icon_lbl, text_lbl, entering: bool):
        for pid, refs in self._ng_nav_btns.items():
            if refs[0] is frame and pid == self._ng_current:
                return
        bg = C["nav_hover"] if entering else C["sidebar"]
        frame.config(bg=bg)
        icon_lbl.config(bg=bg, fg=C["text"] if entering else C["text_dim"])
        text_lbl.config(bg=bg, fg=C["text"] if entering else C["text_mid"])

    def _ng_show(self, pid):
        for pg in self._ng_pages.values(): pg.pack_forget()
        if pid in self._ng_pages:
            self._ng_pages[pid].pack(fill="both", expand=True)
            self._ng_current = pid
        for p, (frame, icon_lbl, text_lbl) in self._ng_nav_btns.items():
            if p == pid:
                frame.config(bg=C["accent"])
                icon_lbl.config(bg=C["accent"], fg="white", font=("Segoe UI", 11, "bold"))
                text_lbl.config(bg=C["accent"], fg="white", font=("Segoe UI", 10, "bold"))
            else:
                frame.config(bg=C["sidebar"])
                icon_lbl.config(bg=C["sidebar"], fg=C["text_dim"], font=("Segoe UI", 11))
                text_lbl.config(bg=C["sidebar"], fg=C["text_mid"], font=("Segoe UI", 10))

    def _ng_section(self, parent, title):
        """A labelled section card."""
        wrap = tk.Frame(parent, bg=C["bg"]); wrap.pack(fill="x", pady=(0, 12))
        tk.Label(wrap, text=title, font=("Segoe UI", 8, "bold"),
                 fg=C["accent"], bg=C["bg"]).pack(anchor="w", padx=2, pady=(0, 4))
        card = tk.Frame(wrap, bg=C["card"],
                        highlightbackground=C["border"], highlightthickness=1,
                        padx=14, pady=12)
        card.pack(fill="x")
        return card

    def _ng_labeled_entry(self, parent, label, var, with_picker=False, label_width=22):
        row = tk.Frame(parent, bg=C["card"]); row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=label_width, anchor="w", font=FT_LABEL,
                 fg=C["text_mid"], bg=C["card"]).pack(side="left")
        e = ttk.Entry(row, textvariable=var, style="DE.TEntry"); e.pack(side="left", fill="x", expand=True, padx=4)
        if with_picker:
            tk.Button(row, text="Pick", command=lambda v=var: self._pick_color(v),
                      bg=C["border"], fg=C["text"], relief="flat",
                      font=FTS, padx=8, pady=2, cursor="hand2").pack(side="left", padx=2)
        return e

    def _pick_color(self, var):
        """Open CHNoteGen's custom HSV picker; update var with the chosen hex."""
        current = var.get().strip()
        if not current.startswith("#") or len(current) != 7:
            current = "#FFFFFF"
        dlg = _ColorPickerDialog(self, current, title="Pick Color")
        if dlg.result:
            var.set(dlg.result)

    # ── Scroll-wheel helper ───────────────────────────────────────────────────
    @staticmethod
    def _bind_mousewheel_to_canvas(canvas: tk.Canvas):
        """Enable scroll-wheel scrolling on a Canvas.

        Uses bind_all so the wheel works even when the pointer is over a child
        widget (Entry, Label, Frame…) inside the canvas.  Binding is activated
        on <Enter> and released on <Leave> so it never hijacks the wheel from
        other scrollable areas.
        """
        def _scroll(event):
            # Windows / macOS: event.delta is ±120 (or multiples).
            # Linux: Button-4 = scroll up, Button-5 = scroll down.
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_enter(_event):
            canvas.bind_all("<MouseWheel>", _scroll)   # Windows / macOS
            canvas.bind_all("<Button-4>",   _scroll)   # Linux scroll up
            canvas.bind_all("<Button-5>",   _scroll)   # Linux scroll down

        def _on_leave(_event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

    # ── Gradient sub-page ─────────────────────────────────────────────────────
    def _build_ng_gradient(self, parent):
        page = tk.Frame(parent, bg=C["bg"]); self._ng_pages["gradient"] = page
        canvas = tk.Canvas(page, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 4), pady=12)
        vsb.pack(side="right", fill="y", pady=12)
        frame = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            canvas.itemconfig(win_id, width=canvas.winfo_width())))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        self._bind_mousewheel_to_canvas(canvas)

        tk.Label(frame, text="CHNameGen — Gradient",
                 font=("Segoe UI", 16, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w", pady=(0,16))

        self._grad_start_var  = tk.StringVar(value="#8044AB")
        self._grad_c2_var     = tk.StringVar()
        self._grad_c3_var     = tk.StringVar()
        self._grad_c4_var     = tk.StringVar()
        self._grad_end_var    = tk.StringVar(value="#F2AAF6")
        self._grad_bold_var   = tk.BooleanVar()
        self._grad_italic_var = tk.BooleanVar()
        self._grad_ul_var     = tk.BooleanVar()
        self._grad_str_var    = tk.BooleanVar()
        self._grad_size_var   = tk.StringVar()
        self._grad_space_var  = tk.StringVar()

        # Name input
        name_card = self._ng_section(frame, "NAME")
        self._grad_name_entry = ttk.Entry(name_card, style="DE.TEntry", font=("Segoe UI", 11))
        self._grad_name_entry.pack(fill="x")

        # Colors
        col_card = self._ng_section(frame, "GRADIENT COLORS")
        self._ng_labeled_entry(col_card, "Start Color",       self._grad_start_var, with_picker=True)
        self._ng_labeled_entry(col_card, "Color 2 (optional)", self._grad_c2_var,   with_picker=True)
        self._ng_labeled_entry(col_card, "Color 3 (optional)", self._grad_c3_var,   with_picker=True)
        self._ng_labeled_entry(col_card, "Color 4 (optional)", self._grad_c4_var,   with_picker=True)
        self._ng_labeled_entry(col_card, "End Color",          self._grad_end_var,  with_picker=True)

        # Style
        sty_card = self._ng_section(frame, "STYLE")
        sty_row  = tk.Frame(sty_card, bg=C["card"]); sty_row.pack(fill="x", pady=(0,8))
        for text, var in [("Bold", self._grad_bold_var), ("Italic", self._grad_italic_var),
                          ("Underline", self._grad_ul_var), ("Strike", self._grad_str_var)]:
            tk.Checkbutton(sty_row, text=text, variable=var,
                           bg=C["card"], fg=C["text"], selectcolor=C["bg"],
                           activebackground=C["card"], font=FT, relief="flat").pack(side="left", padx=8)
        self._ng_labeled_entry(sty_card, "Font Size (optional)",    self._grad_size_var)
        self._ng_labeled_entry(sty_card, "Spacing (optional)",      self._grad_space_var)

        # Buttons
        btn_row = tk.Frame(frame, bg=C["bg"]); btn_row.pack(fill="x", pady=12)
        RoundedButton(btn_row, "Generate", self._on_grad_generate,
                      C["accent"], C["accent_dim"], height=40).pack(side="left", padx=(0,8), fill="x", expand=True)
        RoundedButton(btn_row, "Export to profiles.ini", self._on_grad_export,
                      C["border"], C["hover"], height=40).pack(side="left", fill="x", expand=True)

        # Output
        out_card = self._ng_section(frame, "OUTPUT")
        self._grad_output = tk.Text(out_card, height=3, state=tk.DISABLED,
                                    wrap="word", relief="flat",
                                    bg=C["card2"], fg=C["text"], font=FTM,
                                    insertbackground=C["text"])
        self._grad_output.pack(fill="x", pady=(0,8))
        copy_btn = tk.Button(out_card, text="Copy to Clipboard",
                             command=lambda: self._copy_text(self._grad_output),
                             bg=C["border"], fg=C["text"], relief="flat",
                             font=FTS, padx=10, pady=3, cursor="hand2")
        copy_btn.pack(anchor="e")

        prev_card = self._ng_section(frame, "PREVIEW")
        self._grad_preview = tk.Text(prev_card, height=4, state=tk.DISABLED,
                                     wrap="word", relief="flat",
                                     bg=C["bg"], fg=C["text"], font=("Segoe UI", 16))
        self._grad_preview.pack(fill="both", expand=True)

    def _on_grad_generate(self):
        name = self._grad_name_entry.get()
        if not name:
            messagebox.showerror("Input Error", "Please enter a name."); return
        colors_raw = [self._grad_start_var.get(), self._grad_c2_var.get(),
                      self._grad_c3_var.get(), self._grad_c4_var.get(),
                      self._grad_end_var.get()]
        colors = []
        for c in colors_raw:
            c = c.strip()
            if not c: continue
            if not c.startswith("#"): c = "#" + c
            colors.append(c)
        if len(colors) < 2:
            messagebox.showerror("Input Error", "Please provide at least a start and end color.")
            return
        try:
            size_val    = int(self._grad_size_var.get()) if self._grad_size_var.get() else None
            spacing_val = int(self._grad_space_var.get()) if self._grad_space_var.get() else None
            result, gradient = _generate_gradient_name(
                name, colors,
                bold=self._grad_bold_var.get(), italic=self._grad_italic_var.get(),
                underline=self._grad_ul_var.get(), strike=self._grad_str_var.get(),
                size=size_val, spacing=spacing_val)
            self._grad_output.config(state=tk.NORMAL)
            self._grad_output.delete("1.0", tk.END)
            self._grad_output.insert(tk.END, result)
            self._grad_output.config(state=tk.DISABLED)
            self._grad_preview.config(state=tk.NORMAL)
            self._grad_preview.delete("1.0", tk.END)
            base_fs = min(max((size_val // 2), 10), 24) if size_val else 16
            font_styles = []
            if self._grad_bold_var.get():   font_styles.append("bold")
            if self._grad_italic_var.get(): font_styles.append("italic")
            if self._grad_ul_var.get():     font_styles.append("underline")
            if self._grad_str_var.get():    font_styles.append("overstrike")
            font_tuple = ("Segoe UI", base_fs, " ".join(font_styles) if font_styles else "normal")
            self._grad_preview.configure(font=font_tuple)
            for i, (ch, color) in enumerate(zip(name, gradient)):
                tag = f"gc_{i}"
                self._grad_preview.insert(tk.END, ch, tag)
                self._grad_preview.tag_config(tag, foreground=color)
            self._grad_preview.config(state=tk.DISABLED)
        except ValueError as ve:
            messagebox.showerror("Input Error", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {e}")

    def _on_grad_export(self):
        output = self._grad_output.get("1.0", tk.END).strip()
        if not output:
            messagebox.showerror("Error", "Generate a name first."); return
        self._export_to_profiles_ini(output)

    # ── Individual sub-page ───────────────────────────────────────────────────
    def _build_ng_individual(self, parent):
        page = tk.Frame(parent, bg=C["bg"]); self._ng_pages["individual"] = page
        canvas = tk.Canvas(page, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 4), pady=12)
        vsb.pack(side="right", fill="y", pady=12)
        frame = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            canvas.itemconfig(win_id, width=canvas.winfo_width())))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        self._indiv_canvas = canvas
        self._bind_mousewheel_to_canvas(canvas)

        tk.Label(frame, text="CHNameGen — Per-Letter",
                 font=("Segoe UI", 16, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w", pady=(0,16))

        self._indiv_size_var  = tk.StringVar()
        self._indiv_space_var = tk.StringVar()

        # Name entry
        name_card = self._ng_section(frame, "NAME")
        name_row = tk.Frame(name_card, bg=C["card"]); name_row.pack(fill="x")
        self._indiv_name_entry = ttk.Entry(name_row, style="DE.TEntry", font=("Segoe UI", 11))
        self._indiv_name_entry.pack(side="left", fill="x", expand=True)
        tk.Button(name_row, text="Update Letters", command=self._update_individual_letters,
                  bg=C["accent"], fg="white", relief="flat",
                  font=FTB, padx=10, pady=4, cursor="hand2").pack(side="right", padx=(8, 0))

        # Letter controls container
        lc_card = self._ng_section(frame, "LETTER CONTROLS")
        self._indiv_letter_frame = tk.Frame(lc_card, bg=C["card"])
        self._indiv_letter_frame.pack(fill="x")

        # Global options
        glob_card = self._ng_section(frame, "GLOBAL OPTIONS")
        self._ng_labeled_entry(glob_card, "Font Size (optional)",  self._indiv_size_var)
        self._ng_labeled_entry(glob_card, "Spacing (optional)",    self._indiv_space_var)

        # Buttons
        btn_row = tk.Frame(frame, bg=C["bg"]); btn_row.pack(fill="x", pady=12)
        RoundedButton(btn_row, "Generate", self._on_indiv_generate,
                      C["accent"], C["accent_dim"], height=40).pack(side="left", padx=(0,8), fill="x", expand=True)
        RoundedButton(btn_row, "Export to profiles.ini", self._on_indiv_export,
                      C["border"], C["hover"], height=40).pack(side="left", fill="x", expand=True)

        # Output
        out_card = self._ng_section(frame, "OUTPUT")
        self._indiv_output = tk.Text(out_card, height=3, state=tk.DISABLED,
                                     wrap="word", relief="flat",
                                     bg=C["card2"], fg=C["text"], font=FTM)
        self._indiv_output.pack(fill="x", pady=(0,8))
        tk.Button(out_card, text="Copy to Clipboard",
                  command=lambda: self._copy_text(self._indiv_output),
                  bg=C["border"], fg=C["text"], relief="flat",
                  font=FTS, padx=10, pady=3, cursor="hand2").pack(anchor="e")

        prev_card = self._ng_section(frame, "PREVIEW")
        self._indiv_preview = tk.Text(prev_card, height=3, state=tk.DISABLED,
                                      wrap="word", relief="flat",
                                      bg=C["bg"], fg=C["text"], font=("Segoe UI", 16))
        self._indiv_preview.pack(fill="x")

    def _update_individual_letters(self):
        name = self._indiv_name_entry.get()
        for w in self._indiv_letter_frame.winfo_children():
            w.destroy()
        self._letter_frames.clear(); self._letter_controls.clear()
        if not name: return
        for i, char in enumerate(name):
            row = tk.Frame(self._indiv_letter_frame, bg=C["card"])
            row.pack(fill="x", pady=2)
            self._letter_frames.append(row)
            tk.Label(row, text=f"'{char}'", width=4, anchor="center",
                     font=("Consolas", 11, "bold"), fg=C["accent2"], bg=C["card"]).pack(side="left", padx=4)
            color_var = tk.StringVar(value="#FFFFFF")
            color_swatch = tk.Label(row, bg="#FFFFFF", width=2)
            color_swatch.pack(side="left", padx=2)
            e = ttk.Entry(row, textvariable=color_var, width=9, style="DE.TEntry")
            e.pack(side="left", padx=2)
            def _update_swatch(sv=color_var, sw=color_swatch):
                try: sw.config(bg=sv.get())
                except Exception: pass
            color_var.trace_add("write", lambda *_, sv=color_var, sw=color_swatch: _update_swatch(sv, sw))
            tk.Button(row, text="Pick",
                      command=lambda cv=color_var: self._pick_color(cv),
                      bg=C["border"], fg=C["text"], relief="flat",
                      font=FTS, padx=6, pady=1, cursor="hand2").pack(side="left", padx=2)
            bold_var = tk.BooleanVar(); italic_var = tk.BooleanVar()
            ul_var   = tk.BooleanVar(); str_var    = tk.BooleanVar()
            for txt, var in [("B", bold_var),("I", italic_var),("U", ul_var),("S", str_var)]:
                tk.Checkbutton(row, text=txt, variable=var, width=2,
                               bg=C["card"], fg=C["text"], selectcolor=C["bg"],
                               activebackground=C["card"],
                               font=("Segoe UI", 9, "bold"), relief="flat").pack(side="left", padx=2)
            self._letter_controls.append({
                "char": char, "color_var": color_var,
                "bold_var": bold_var, "italic_var": italic_var,
                "underline_var": ul_var, "strike_var": str_var
            })

    def _on_indiv_generate(self):
        if not self._letter_controls:
            messagebox.showerror("Error", "Enter a name and click 'Update Letters' first."); return
        try:
            size_val    = int(self._indiv_size_var.get()) if self._indiv_size_var.get() else None
            spacing_val = int(self._indiv_space_var.get()) if self._indiv_space_var.get() else None
            letters_data = [{"char": c["char"], "color": c["color_var"].get(),
                              "bold": c["bold_var"].get(), "italic": c["italic_var"].get(),
                              "underline": c["underline_var"].get(), "strike": c["strike_var"].get()}
                            for c in self._letter_controls]
            result, colors = _generate_individual_name(letters_data, size_val, spacing_val)
            self._indiv_output.config(state=tk.NORMAL)
            self._indiv_output.delete("1.0", tk.END)
            self._indiv_output.insert(tk.END, result)
            self._indiv_output.config(state=tk.DISABLED)
            self._indiv_preview.config(state=tk.NORMAL)
            self._indiv_preview.delete("1.0", tk.END)
            base_fs = min(max((size_val // 2), 10), 24) if size_val else 16
            for i, (ctrl, color) in enumerate(zip(self._letter_controls, colors)):
                tag = f"ic_{i}"
                font_styles = []
                if ctrl["bold_var"].get():      font_styles.append("bold")
                if ctrl["italic_var"].get():    font_styles.append("italic")
                if ctrl["underline_var"].get(): font_styles.append("underline")
                if ctrl["strike_var"].get():    font_styles.append("overstrike")
                self._indiv_preview.insert(tk.END, ctrl["char"], tag)
                self._indiv_preview.tag_config(tag, foreground=color,
                    font=("Segoe UI", base_fs, " ".join(font_styles) if font_styles else "normal"))
            self._indiv_preview.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {e}")

    def _on_indiv_export(self):
        output = self._indiv_output.get("1.0", tk.END).strip()
        if not output:
            messagebox.showerror("Error", "Generate a name first."); return
        self._export_to_profiles_ini(output)

    # ── Shared name gen helpers ───────────────────────────────────────────────
    def _copy_text(self, text_widget):
        text = text_widget.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear(); self.clipboard_append(text)
            messagebox.showinfo("Copied", "Output copied to clipboard!")

    def _export_to_profiles_ini(self, name_tagged: str):
        folder = filedialog.askdirectory(title="Choose folder to save profiles.ini")
        if not folder: return
        filepath = os.path.join(folder, "profiles.ini")
        config = configparser.ConfigParser()
        if os.path.exists(filepath): config.read(filepath)
        profile_num = 1
        while f"profile{profile_num}" in config: profile_num += 1
        section = f"profile{profile_num}"
        config[section] = {
            "controller_type":"0","lefty_flip":"0","gamepad_mode":"0","is_bot":"0",
            "show_displayname":"0","drum_dynamics_hidden":"0","square_tom_notes":"0",
            "alt_taps":"0","show_accuracy_display":"0","player_name":name_tagged,
            "note_speed":"7","tilt_activation":"1","highway_length":"100",
            "highway_name":"default","color_profile_name":"DefaultColors",
            "midi_device_id":"-1","dynamics_threshold":"100"}
        try:
            with open(filepath, "w", encoding="utf-8") as f: config.write(f)
            messagebox.showinfo("Exported",
                f"Saved profile to:\n{filepath}\nunder section [{section}]")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save profiles.ini: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 3 — NOTEGEN (CHNoteGen)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_notegen(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["notegen"] = page

        BG_TITLE = "#06080c"
        BG_PROF  = "#0a0c16"

        # ── Title bar ─────────────────────────────────────────────────────────
        title = tk.Frame(page, bg=BG_TITLE); title.pack(fill="x")
        tk.Frame(title, bg=C["accent"], height=2).pack(fill="x", side="bottom")
        left_t = tk.Frame(title, bg=BG_TITLE); left_t.pack(side="left", padx=18, pady=11)
        tk.Label(left_t, text="CH", font=("Segoe UI",18,"bold"),
                 bg=BG_TITLE, fg=C["accent"]).pack(side="left")
        tk.Label(left_t, text="NoteGen", font=("Segoe UI",18,"bold"),
                 bg=BG_TITLE, fg=C["text"]).pack(side="left")
        tk.Label(left_t, text="  Guitar Color Editor",
                 font=("Segoe UI",9), bg=BG_TITLE, fg=C["text_dim"]).pack(side="left", pady=(5,0))
        tk.Label(title, text="Ctrl+S  Export",
                 font=("Segoe UI",8), bg=BG_TITLE, fg=C["text_dim"]).pack(side="right", padx=18)

        # ── Profile bar ───────────────────────────────────────────────────────
        pbar = tk.Frame(page, bg=BG_PROF); pbar.pack(fill="x")
        tk.Frame(pbar, bg="#181c38", height=1).pack(fill="x", side="bottom")
        pi = tk.Frame(pbar, bg=BG_PROF); pi.pack(fill="x", padx=14, pady=8)

        pw = tk.Frame(pi, bg=BG_PROF); pw.pack(side="left")
        tk.Label(pw, text="PROFILE", font=("Segoe UI",7,"bold"),
                 bg=BG_PROF, fg=C["text_dim"]).pack(anchor="w")
        self._ng_prof_var = tk.StringVar()
        self._ng_prof_cb  = ttk.Combobox(pw, textvariable=self._ng_prof_var,
                                          state="readonly", width=22, font=FT)
        self._ng_prof_cb.pack()
        self._ng_prof_cb.bind("<<ComboboxSelected>>", self._ng_on_prof_selected)

        tk.Frame(pi, bg="#181c38", width=1, height=28).pack(side="left", padx=12)

        def _pb(text, cmd, style="ghost"):
            styles = {"ghost":("#11142a",C["text_mid"],"#1b1f40",C["text"]),
                      "accent":(C["accent"],"#fff",C["accent_dim"],"#fff"),
                      "danger":("#1a0808","#d45555","#2c0f0f","#ff8080")}
            bg,fg,hbg,hfg = styles[style]
            b = tk.Button(pi, text=text, font=("Segoe UI",8), bg=bg, fg=fg,
                          relief="flat", activebackground=hbg, activeforeground=hfg,
                          cursor="hand2", command=cmd, bd=0, padx=10, pady=5)
            b.pack(side="left", padx=2)
            b.bind("<Enter>", lambda _: b.config(bg=hbg, fg=hfg))
            b.bind("<Leave>", lambda _: b.config(bg=bg,  fg=fg))
            return b

        _pb("+ New",        self._ng_prof_new)
        _pb("⎘ Duplicate",  self._ng_prof_duplicate)
        self._ng_rename_btn = _pb("✎ Rename", self._ng_prof_rename)
        self._ng_delete_btn = _pb("✕ Delete", self._ng_prof_delete, "danger")
        tk.Frame(pi, bg="#181c38", width=1, height=28).pack(side="left", padx=12)
        _pb("↑ Import .ini", self._ng_import_ini)
        _pb("↓ Export .ini", self._ng_export_ini, "accent")

        self._ng_status_var = tk.StringVar(value="")
        self._ng_status_lbl = tk.Label(pi, textvariable=self._ng_status_var,
                                        font=("Segoe UI",8), bg=BG_PROF, fg=C["text_dim"])
        self._ng_status_lbl.pack(side="right", padx=6)

        # ── Read-only banner ──────────────────────────────────────────────────
        self._ng_ro_bar = tk.Frame(page, bg="#0e0828"); ro_i = tk.Frame(self._ng_ro_bar, bg="#0e0828")
        ro_i.pack(fill="x", padx=14, pady=6)
        tk.Label(ro_i, text="🔒  Read-only profile", font=("Segoe UI",8,"bold"),
                 bg="#0e0828", fg=C["accent"]).pack(side="left")
        tk.Label(ro_i, text=" — duplicate or create a new profile to edit colours.",
                 font=("Segoe UI",8), bg="#0e0828", fg="#6b4faa").pack(side="left")
        tk.Button(ro_i, text="⎘ Duplicate now", font=("Segoe UI",8), bg=C["accent"], fg="#fff",
                  relief="flat", activebackground=C["accent_dim"], activeforeground="#fff",
                  cursor="hand2", command=self._ng_prof_duplicate, bd=0, padx=8, pady=3
                  ).pack(side="right")

        # ── Main body: paned (editor left, preview right) ─────────────────────
        body = tk.PanedWindow(page, orient="horizontal",
                              bg="#0d1020", sashwidth=4, sashrelief="flat", handlesize=0)
        body.pack(fill="both", expand=True)
        left  = tk.Frame(body, bg="#07090e")
        right = tk.Frame(body, bg=C["panel"])
        body.add(left,  minsize=380, width=640, stretch="always")
        body.add(right, minsize=300, width=480, stretch="always")

        # ── Editor (Guitar + Effects tabs) ────────────────────────────────────
        TABS = [("🎸  Guitar","guitar"), ("✨  Effects","other")]
        self._ng_tab_lbls = {}; self._ng_active_tab = "guitar"
        BG = "#07090e"
        tab_bar = tk.Frame(left, bg=BG); tab_bar.pack(fill="x", side="top")
        self._ng_ind_cv = tk.Canvas(tab_bar, height=2, bg=BG, highlightthickness=0)
        self._ng_ind_cv.pack(fill="x", side="bottom")
        self._ng_ind_rect = self._ng_ind_cv.create_rectangle(0,0,0,2,fill=C["accent"],outline="")
        self._ng_ind_x0 = self._ng_ind_x1 = 0.
        self._ng_ind_tx0= self._ng_ind_tx1= 0.
        self._ng_ind_aid= None
        tab_row = tk.Frame(tab_bar, bg=BG); tab_row.pack(fill="x")
        self._ng_tab_bounds = {}
        content = tk.Frame(left, bg=BG); content.pack(fill="both", expand=True)

        def _ng_switch(section):
            self._ng_active_tab = section
            for s,lbl in self._ng_tab_lbls.items():
                lbl.config(fg=C["text"] if s==section else C["text_dim"],
                           font=("Segoe UI",9,"bold") if s==section else ("Segoe UI",9))
            if section in self._ng_tab_bounds:
                x0,x1=self._ng_tab_bounds[section]; self._ng_slide_to(x0,x1)
            for s,ed in self._ng_editors.items(): ed.pack_forget()
            self._ng_editors[section].pack(fill="both", expand=True, in_=content)

        for tab_label, section in TABS:
            lbl = tk.Label(tab_row, text=tab_label, font=("Segoe UI",9), bg=BG,
                           fg=C["text_dim"], padx=18, pady=12, cursor="hand2")
            lbl.pack(side="left"); self._ng_tab_lbls[section] = lbl
            def _bind(l,s):
                l.bind("<Enter>", lambda e,_s=s: l.config(fg=C["text_mid"]) if self._ng_active_tab!=_s else None)
                l.bind("<Leave>", lambda e,_s=s: l.config(fg=C["text_dim"]) if self._ng_active_tab!=_s else None)
                l.bind("<Button-1>", lambda e,sec=s: _ng_switch(sec))
            _bind(lbl, section)
        tk.Frame(tab_bar, bg="#151830", height=1).pack(fill="x", side="bottom")

        def _init_bounds(_=None):
            tab_row.update_idletasks()
            for s,lbl in self._ng_tab_lbls.items():
                x0=lbl.winfo_x(); x1=x0+lbl.winfo_width(); self._ng_tab_bounds[s]=(x0,x1)
            x0,x1=self._ng_tab_bounds.get("guitar",(0,120))
            self._ng_ind_x0=self._ng_ind_x1=x0; self._ng_ind_tx0=self._ng_ind_tx1=x1
            self._ng_ind_cv.coords(self._ng_ind_rect,x0,0,x1,2)
        tab_row.bind("<Configure>", _init_bounds)

        for _, section in TABS:
            ed = _NgSectionEditor(content, section, self)
            self._ng_editors[section] = ed
        _ng_switch("guitar")
        self._ng_tab_lbls["guitar"].config(fg=C["text"], font=("Segoe UI",9,"bold"))

        # ── Preview ───────────────────────────────────────────────────────────
        hdr_r = tk.Frame(right, bg=C["panel"]); hdr_r.pack(fill="x", padx=8, pady=(8,2))
        tk.Label(hdr_r, text="LIVE PREVIEW", font=FTB,
                 bg=C["panel"], fg=C["accent2"]).pack(side="left")
        self._ng_preview = _NgHighwayPreview(right, self)
        self._ng_preview.pack(fill="both", expand=True)

        # ── Init profiles ─────────────────────────────────────────────────────
        page.bind("<Control-s>", lambda _: self._ng_export_ini())
        self._ng_refresh_profile_list()
        self._ng_select_profile(_NG_DEFAULT_PROFILE_NAME)

    # ── NoteGen tab slider ────────────────────────────────────────────────────
    def _ng_slide_to(self, tx0, tx1):
        self._ng_ind_tx0=tx0; self._ng_ind_tx1=tx1
        if self._ng_ind_aid: self.after_cancel(self._ng_ind_aid); self._ng_ind_aid=None
        self._ng_do_slide()

    def _ng_do_slide(self):
        sp=0.20
        self._ng_ind_x0 += (self._ng_ind_tx0-self._ng_ind_x0)*sp
        self._ng_ind_x1 += (self._ng_ind_tx1-self._ng_ind_x1)*sp
        self._ng_ind_cv.coords(self._ng_ind_rect,self._ng_ind_x0,0,self._ng_ind_x1,2)
        if abs(self._ng_ind_tx0-self._ng_ind_x0)>0.5 or abs(self._ng_ind_tx1-self._ng_ind_x1)>0.5:
            self._ng_ind_aid=self.after(13,self._ng_do_slide)
        else:
            self._ng_ind_x0,self._ng_ind_x1=self._ng_ind_tx0,self._ng_ind_tx1
            self._ng_ind_cv.coords(self._ng_ind_rect,self._ng_ind_x0,0,self._ng_ind_x1,2)
            self._ng_ind_aid=None

    # ── NoteGen helpers called by child widgets ───────────────────────────────
    def _ng_active_colors(self) -> dict:
        return self._ng_active_colors_data

    def on_color_changed(self, section:str, key:str, hex_val:str):
        """Called by _NgColorRow when a colour is picked — mirrors CHNoteGen's App method."""
        if self._ng_active_name == _NG_DEFAULT_PROFILE_NAME: return
        if not _ng_valid_hex(hex_val): return
        old_val = self._ng_active_colors_data.get(section,{}).get(key,"")
        self._ng_active_colors_data.setdefault(section,{})[key] = hex_val.upper()
        self._ng_profiles[self._ng_active_name] = copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles)
        if section=="guitar" and key.startswith("note_") and old_val:
            self._ng_preview.clear_photo_cache(old_val.upper())
        self._ng_preview.refresh()

    # ── NoteGen profile management ────────────────────────────────────────────
    def _ng_is_default(self): return self._ng_active_name == _NG_DEFAULT_PROFILE_NAME

    def _ng_refresh_profile_list(self):
        names=[_NG_DEFAULT_PROFILE_NAME]+sorted(self._ng_profiles.keys())
        self._ng_prof_cb["values"]=names
        if self._ng_prof_var.get() not in names: self._ng_prof_var.set(_NG_DEFAULT_PROFILE_NAME)

    def _ng_select_profile(self, name:str):
        self._ng_active_name=name; self._ng_prof_var.set(name)
        if name==_NG_DEFAULT_PROFILE_NAME:
            self._ng_active_colors_data=_ng_fresh_colors()
        else:
            saved=self._ng_profiles.get(name,{}); colors=_ng_fresh_colors()
            for section in colors:
                if section in saved: colors[section].update(saved[section])
            self._ng_active_colors_data=colors
        is_ro=self._ng_is_default()
        if is_ro: self._ng_ro_bar.pack(fill="x")
        else: self._ng_ro_bar.pack_forget()
        self._ng_rename_btn.config(state="normal" if not is_ro else "disabled",
                                    fg="#fff" if not is_ro else C["text_dim"])
        self._ng_delete_btn.config(state="normal" if not is_ro else "disabled",
                                    fg="#fff" if not is_ro else C["text_dim"])
        for section,ed in self._ng_editors.items():
            ed.push(self._ng_active_colors_data.get(section,{}))
            ed.set_readonly(is_ro)
        self.after(80, self._ng_preview.refresh)
        self._ng_status(f"Profile: {name}")

    def _ng_on_prof_selected(self,_=None): self._ng_select_profile(self._ng_prof_var.get())

    def _ng_prof_new(self):
        name=simpledialog.askstring("New Profile","Profile name:",parent=self)
        if not name: return
        name=name.strip()
        if name==_NG_DEFAULT_PROFILE_NAME:
            messagebox.showwarning("Reserved","That name is reserved.",parent=self); return
        if name in self._ng_profiles:
            messagebox.showwarning("Exists",f"'{name}' already exists.",parent=self); return
        self._ng_profiles[name]=copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(name); self._ng_status(f"Created '{name}'.")

    def _ng_prof_duplicate(self):
        name=simpledialog.askstring("Duplicate Profile",
                                     f"New name (duplicating '{self._ng_active_name}'):",parent=self)
        if not name: return
        name=name.strip()
        if not name or name==_NG_DEFAULT_PROFILE_NAME: return
        if name in self._ng_profiles:
            messagebox.showwarning("Exists",f"'{name}' already exists.",parent=self); return
        self._ng_profiles[name]=copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(name); self._ng_status(f"Duplicated as '{name}'.")

    def _ng_prof_rename(self):
        if self._ng_is_default(): return
        new=simpledialog.askstring("Rename Profile",f"Rename '{self._ng_active_name}' to:",parent=self)
        if not new: return
        new=new.strip()
        if not new or new==_NG_DEFAULT_PROFILE_NAME: return
        if new in self._ng_profiles:
            messagebox.showwarning("Exists",f"'{new}' already exists.",parent=self); return
        old=self._ng_active_name; self._ng_profiles[new]=self._ng_profiles.pop(old)
        _ng_save_profiles(self._ng_profiles); self._ng_active_name=new
        self._ng_refresh_profile_list(); self._ng_prof_var.set(new)
        self._ng_status(f"Renamed to '{new}'.")

    def _ng_prof_delete(self):
        if self._ng_is_default(): return
        if not messagebox.askyesno("Delete Profile",f"Delete '{self._ng_active_name}'?",parent=self): return
        self._ng_profiles.pop(self._ng_active_name,None)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(_NG_DEFAULT_PROFILE_NAME)

    def _ng_import_ini(self):
        path=filedialog.askopenfilename(title="Import Colors .ini",
                                        filetypes=[("INI files","*.ini"),("All files","*.*")],parent=self)
        if not path: return
        parsed=_ng_parse_ini(path)
        if not any(parsed.get(s) for s in _NG_DEFAULT_COLORS):
            messagebox.showerror("Parse Error","No recognisable colour sections found.",parent=self); return
        name=simpledialog.askstring("Import .ini",f"Importing '{Path(path).name}'\n\nSave as profile name:",parent=self)
        if name is None: return
        name=name.strip()
        if not name:
            if self._ng_is_default():
                messagebox.showwarning("Read-Only","Cannot overwrite the Default profile.",parent=self); return
            target=self._ng_active_name
        else:
            target=name
        colors=_ng_fresh_colors()
        for section in colors:
            if section in parsed: colors[section].update(parsed[section])
        self._ng_profiles[target]=copy.deepcopy(colors)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(target); self._ng_status(f"Imported '{Path(path).name}' → '{target}'.")

    def _ng_export_ini(self,_=None):
        ini_str=_ng_generate_ini(self._ng_active_colors_data)
        default_file=("DefaultColors.ini" if self._ng_is_default()
                      else self._ng_active_name.replace(" ","_")+".ini")
        path=filedialog.asksaveasfilename(title="Export Colors .ini",defaultextension=".ini",
                                          filetypes=[("INI files","*.ini"),("All files","*.*")],
                                          initialfile=default_file,parent=self)
        if not path: return
        try:
            Path(path).write_text(ini_str,encoding="utf-8")
            self._ng_status(f"Exported → '{Path(path).name}'.")
            messagebox.showinfo("Exported",
                f"Profile exported to:\n{path}\n\nCopy to your Clone Hero  Custom/Colors  folder.",parent=self)
        except Exception as e: messagebox.showerror("Export Error",str(e),parent=self)

    def _ng_status(self, msg:str):
        self._ng_status_var.set(msg)
        self._ng_status_lbl.config(fg=C["accent"])
        self.after(2000, lambda: self._ng_status_lbl.config(fg=C["text_dim"])
                   if hasattr(self,"_ng_status_lbl") else None)

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 4 — BAD SONGS CLEANER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_cleaner(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["cleaner"] = page
        inner = tk.Frame(page, bg=C["bg"], padx=24, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="CHCleaner",
                 font=("Segoe UI", 18, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner, text="Load your badsongs.txt, review ERROR folders, and delete them.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 16))

        # File picker card
        file_card = tk.Frame(inner, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=16, pady=14)
        file_card.pack(fill="x", pady=(0, 14))
        tk.Label(file_card, text="SELECTED FILE", font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w")
        self._cl_file_lbl = tk.Label(file_card, text="No file selected",
                                     fg=C["text_dim"], bg=C["card"], font=FT_LABEL,
                                     wraplength=800, justify="left", anchor="w")
        self._cl_file_lbl.pack(fill="x", pady=(4, 10))
        RoundedButton(file_card, "📂  Select badsongs.txt", self._cl_select_file,
                      C["accent"], C["accent_dim"], height=42).pack(fill="x")

        # Song list card
        list_card = tk.Frame(inner, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1)
        list_card.pack(fill="both", expand=True, pady=(0, 14))
        list_hdr = tk.Frame(list_card, bg=C["card"], padx=14, pady=10)
        list_hdr.pack(fill="x")
        tk.Label(list_hdr, text="Songs to Delete", font=FTB,
                 fg=C["text"], bg=C["card"]).pack(side="left")
        self._cl_count_lbl = tk.Label(list_hdr, text="0 selected",
                                      font=FT, fg=C["text_mid"], bg=C["card"])
        self._cl_count_lbl.pack(side="right")
        btn_grp = tk.Frame(list_hdr, bg=C["card"]); btn_grp.pack(side="right", padx=(0, 16))
        for txt, cmd in [("Select All", self._cl_select_all), ("Select None", self._cl_select_none)]:
            tk.Button(btn_grp, text=txt, command=cmd, bg=C["border"], fg=C["text"],
                      relief="flat", padx=10, pady=4, font=FT_LABEL, cursor="hand2").pack(side="left", padx=2)

        _sep(list_card, bg=C["border"]).pack(fill="x")

        list_inner = tk.Frame(list_card, bg=C["card"])
        list_inner.pack(fill="both", expand=True, padx=12, pady=8)
        vsb = ttk.Scrollbar(list_inner, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._cl_canvas = tk.Canvas(list_inner, bg=C["card"], highlightthickness=0,
                                     yscrollcommand=vsb.set)
        self._cl_canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._cl_canvas.yview)
        self._cl_inner = tk.Frame(self._cl_canvas, bg=C["card"])
        self._cl_canvas.create_window((0, 0), window=self._cl_inner, anchor="nw")
        self._cl_inner.bind("<Configure>", lambda e: self._cl_canvas.configure(
            scrollregion=self._cl_canvas.bbox("all")))

        # Delete button
        self._cl_del_btn = RoundedButton(inner, "🗑  Delete Selected Songs",
                                          self._cl_delete, C["error"], "#dc2626", height=46)
        self._cl_del_btn.pack(fill="x", pady=(0, 8))
        self._cl_del_btn.set_state(False)

        # Status
        stat_card = tk.Frame(inner, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=14, pady=10)
        stat_card.pack(fill="x")
        tk.Label(stat_card, text="STATUS", font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w")
        self._cl_status_lbl = tk.Label(stat_card, text="Ready to clean bad songs.",
                                        fg=C["success"], bg=C["card"], font=FT,
                                        wraplength=900, justify="left", anchor="w")
        self._cl_status_lbl.pack(anchor="w", pady=(4, 0), fill="x")

    def _cl_select_file(self):
        fp = filedialog.askopenfilename(title="Select badsongs.txt",
                                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if fp:
            self._badsongs_path = fp
            self._cl_file_lbl.config(text=f"✓  {fp}", fg=C["text"])
            self._cl_load_songs()

    def _cl_load_songs(self):
        for w in self._cl_inner.winfo_children(): w.destroy()
        self._song_vars.clear()
        self._cl_status_lbl.config(text="Parsing file…", fg=C["warn"])
        self.update()
        self._bad_paths = _parse_bad_songs(self._badsongs_path)
        if not self._bad_paths:
            messagebox.showinfo("Info", "No ERROR folders found in the file.")
            self._cl_status_lbl.config(text="No folders to delete.", fg=C["success"])
            self._cl_del_btn.set_state(False)
            self._cl_count_lbl.config(text="0 selected")
            return
        for path in self._bad_paths:
            var = tk.BooleanVar(value=True)
            self._song_vars[path] = var
            row = tk.Frame(self._cl_inner, bg=C["card"]); row.pack(fill="x", pady=1)
            tk.Checkbutton(row, text=path, variable=var, command=self._cl_update_count,
                           bg=C["card"], fg=C["text"], selectcolor=C["bg"],
                           activebackground=C["card"], activeforeground=C["text"],
                           font=("Consolas", 9), anchor="w", relief="flat").pack(fill="x", padx=4)
        self._cl_update_count()
        self._cl_del_btn.set_state(True)
        self._cl_status_lbl.config(text=f"Loaded {len(self._bad_paths)} ERROR folder(s).", fg=C["success"])

    def _cl_select_all(self):
        for v in self._song_vars.values(): v.set(True)
        self._cl_update_count()

    def _cl_select_none(self):
        for v in self._song_vars.values(): v.set(False)
        self._cl_update_count()

    def _cl_update_count(self):
        n = sum(1 for v in self._song_vars.values() if v.get())
        self._cl_count_lbl.config(text=f"{n} selected")

    def _cl_delete(self):
        if not self._badsongs_path:
            messagebox.showerror("Error", "Select a badsongs.txt file first."); return
        selected = [p for p, v in self._song_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("Info", "No songs selected for deletion."); return
        if not messagebox.askyesno("Confirm Deletion",
                f"Delete {len(selected)} selected songs?\n\nThis action cannot be undone."):
            self._cl_status_lbl.config(text="Deletion cancelled.", fg=C["warn"]); return
        deleted = 0; failed = 0
        self._log_entries = [f"--- Deletion started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---"]
        for raw_path in selected:
            try:
                p = Path(raw_path)
                target = p if p.is_dir() else p.parent
                if target.exists() and target.is_dir():
                    shutil.rmtree(target); deleted += 1
                    self._log_entries.append(f"✓ Deleted: {target}")
                else:
                    self._log_entries.append(f"⚠ Not found: {raw_path}"); failed += 1
            except Exception as e:
                failed += 1; self._log_entries.append(f"✗ Failed: {raw_path}\n  {e}")
        self._cl_auto_save_log()
        messagebox.showinfo("Done",
            f"Deleted: {deleted}  |  Failed: {failed}\n\nLog saved to Documents/Clone Hero/deletedsongs.log")
        self._cl_status_lbl.config(
            text=f"Completed: {deleted} deleted, {failed} failed. Log saved.",
            fg=C["success"])
        self._cl_load_songs()

    def _cl_auto_save_log(self):
        try:
            log_dir = Path.home() / "Documents" / "Clone Hero"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "deletedsongs.log", "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(self._log_entries) + "\n" + "=" * 60 + "\n\n")
        except Exception as e:
            messagebox.showerror("Log Error", f"Could not save log: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 4 — LAUNCHER PATCHER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_patcher(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["patcher"] = page
        inner = tk.Frame(page, bg=C["bg"], padx=24, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="CHPatcher",
                 font=("Segoe UI", 18, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner,
                 text="Mark installs as Manual so the launcher stops overwriting your game files.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 18))

        # ── Status card ───────────────────────────────────────────────────────
        stat_card = _card(inner, padx=18, pady=14)
        stat_card.pack(fill="x", pady=(0, 14))
        tk.Label(stat_card, text="LAUNCHER STATUS", font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w", pady=(0, 8))
        self._pt_status_lbl = tk.Label(
            stat_card, text="", font=("Segoe UI", 11, "bold"),
            fg=C["text_dim"], bg=C["card"])
        self._pt_status_lbl.pack(anchor="w")
        self._pt_status_sub = tk.Label(
            stat_card, text="", font=FT, fg=C["text_dim"], bg=C["card"],
            wraplength=700, justify="left")
        self._pt_status_sub.pack(anchor="w", pady=(4, 0))

        tk.Button(stat_card, text="↺  Refresh", command=self._pt_refresh,
                  bg=C["border"], fg=C["text"], relief="flat",
                  font=FT_LABEL, padx=10, pady=3, cursor="hand2").pack(anchor="e", pady=(10, 0))

        # ── Installs list ─────────────────────────────────────────────────────
        list_card = _card(inner, padx=0, pady=0)
        list_card.pack(fill="both", expand=True, pady=(0, 14))
        lh = tk.Frame(list_card, bg=C["card"], padx=16, pady=10); lh.pack(fill="x")
        tk.Label(lh, text="INSTALLS IN game_installs.json",
                 font=("Segoe UI", 8, "bold"), fg=C["text_dim"], bg=C["card"]).pack(side="left")
        _sep(list_card, bg=C["border"]).pack(fill="x")

        scroll_wrap = tk.Frame(list_card, bg=C["card"])
        scroll_wrap.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(scroll_wrap, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._pt_canvas = tk.Canvas(scroll_wrap, bg=C["card"],
                                    highlightthickness=0, yscrollcommand=vsb.set)
        self._pt_canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._pt_canvas.yview)
        self._pt_inner = tk.Frame(self._pt_canvas, bg=C["card"])
        self._pt_canvas.create_window((0, 0), window=self._pt_inner, anchor="nw")
        self._pt_inner.bind("<Configure>", lambda e: self._pt_canvas.configure(
            scrollregion=self._pt_canvas.bbox("all")))

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=C["bg"]); btn_row.pack(fill="x", pady=(0, 4))
        self._pt_patch_btn = RoundedButton(
            btn_row, "⚙  Patch Selected as Manual",
            self._pt_patch_selected, C["accent"], C["accent_dim"], height=46)
        self._pt_patch_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._pt_unpatch_btn = RoundedButton(
            btn_row, "↩  Unpatch Selected (Restore Launcher)",
            self._pt_unpatch_selected, C["border"], C["hover"], height=46)
        self._pt_unpatch_btn.pack(side="left", fill="x", expand=True)

        btn_row2 = tk.Frame(inner, bg=C["bg"]); btn_row2.pack(fill="x", pady=(0, 8))
        self._pt_remove_btn = RoundedButton(
            btn_row2, "✕  Remove Selected Entry from JSON",
            self._pt_remove_selected, "#3d1a1a", "#5a2020", height=38)
        self._pt_remove_btn.pack(fill="x")

        # Warning note
        warn_card = tk.Frame(inner, bg="#2a1f0a",
                             highlightbackground=C["warn"], highlightthickness=1,
                             padx=14, pady=10)
        warn_card.pack(fill="x")
        tk.Label(warn_card,
                 text="⚠  Close the Clone Hero Launcher before patching. "
                      "CHSuite will attempt to close it automatically if detected.",
                 font=FT_LABEL, fg=C["warn"], bg="#2a1f0a",
                 wraplength=760, justify="left").pack(anchor="w")

        # ── Store selection vars ───────────────────────────────────────────────
        self._pt_vars = {}          # directoryPath → BooleanVar
        self._pt_refresh()

    def _pt_refresh(self):
        """Reload installs from game_installs.json and rebuild the list."""
        for w in self._pt_inner.winfo_children():
            w.destroy()
        self._pt_vars.clear()

        if not _INSTALLS_FILE.is_file():
            self._pt_status_lbl.config(
                text="✗  game_installs.json not found",
                fg=C["error"])
            self._pt_status_sub.config(
                text=f"Expected at: {_INSTALLS_FILE}\n"
                     "The Clone Hero Launcher may not be installed.",
                fg=C["text_dim"])
            return

        installs = _read_installs()
        if not installs:
            self._pt_status_lbl.config(
                text="◦  No installs found", fg=C["text_dim"])
            self._pt_status_sub.config(text="", fg=C["text_dim"])
            return

        # Count how many are already manual
        manual_count = sum(1 for i in installs if i.get("isFromLauncher") is False)
        total = len(installs)
        if manual_count == total:
            status_text = f"✓  All {total} install(s) patched as Manual"
            status_fg   = C["success"]
        elif manual_count == 0:
            status_text = f"✗  {total} install(s) — none patched"
            status_fg   = C["error"]
        else:
            status_text = f"◑  {manual_count}/{total} install(s) patched"
            status_fg   = C["warn"]
        self._pt_status_lbl.config(text=status_text, fg=status_fg)
        self._pt_status_sub.config(
            text=f"File: {_INSTALLS_FILE}", fg=C["text_dim"])

        # Populate list
        for inst in installs:
            path     = inst.get("directoryPath", "?")
            ver      = inst.get("version") or "—"
            is_man   = inst.get("isFromLauncher") is False
            disabled = inst.get("disabled", False)

            row = tk.Frame(self._pt_inner, bg=C["card"], pady=0)
            row.pack(fill="x")
            _sep(row, bg=C["border"]).pack(fill="x")

            inner_row = tk.Frame(row, bg=C["card"], padx=14, pady=10)
            inner_row.pack(fill="x")

            # ── Custom toggle indicator ───────────────────────────────────────
            # tk.Checkbutton's dark-theme indicator is invisible on Windows.
            # Use a small colored Canvas square instead — bulletproof on all
            # Windows/tkinter versions.
            var = tk.BooleanVar(self, value=True)
            self._pt_vars[path] = var

            IND_SIZE = 20
            # highlightthickness=0 and bd=0 remove the system focus box entirely.
            # We draw our own border as part of the canvas content so it's
            # always pixel-perfect and never shows OS-themed artifacts.
            ind_cv = tk.Canvas(inner_row, width=IND_SIZE, height=IND_SIZE,
                               bg=C["card"], highlightthickness=0, bd=0,
                               cursor="hand2")
            ind_cv.pack(side="left", padx=(0, 10))

            def _draw_ind(cv=ind_cv, v=var):
                cv.delete("all")
                if v.get():
                    # Filled accent rounded square
                    r = 4
                    cv.create_polygon(
                        r, 0,  IND_SIZE-r, 0,
                        IND_SIZE, r,  IND_SIZE, IND_SIZE-r,
                        IND_SIZE-r, IND_SIZE,  r, IND_SIZE,
                        0, IND_SIZE-r,  0, r,
                        fill=C["accent"], outline="", smooth=True)
                    # Checkmark: short leg then long diagonal
                    cv.create_line(
                        4, IND_SIZE//2 + 1,
                        IND_SIZE//2 - 1, IND_SIZE - 4,
                        IND_SIZE - 3, 4,
                        fill="white", width=2,
                        joinstyle="round", capstyle="round")
                else:
                    # Empty rounded square with subtle border
                    r = 4
                    cv.create_polygon(
                        r, 0,  IND_SIZE-r, 0,
                        IND_SIZE, r,  IND_SIZE, IND_SIZE-r,
                        IND_SIZE-r, IND_SIZE,  r, IND_SIZE,
                        0, IND_SIZE-r,  0, r,
                        fill=C["card"], outline=C["border2"], smooth=True)

            _draw_ind()

            def _toggle(event=None, v=var, draw=_draw_ind):
                v.set(not v.get())
                draw()
                self._pt_update_count()

            ind_cv.bind("<Button-1>", _toggle)

            # Info
            info = tk.Frame(inner_row, bg=C["card"]); info.pack(side="left", fill="x", expand=True)
            name_color = C["text_dim"] if disabled else C["text"]
            tk.Label(info, text=os.path.basename(path),
                     font=FTB, fg=name_color, bg=C["card"]).pack(anchor="w")
            tk.Label(info, text=path,
                     font=FTM, fg=C["text_dim"], bg=C["card"]).pack(anchor="w")

            tag_row = tk.Frame(info, bg=C["card"]); tag_row.pack(anchor="w", pady=(2, 0))
            tk.Label(tag_row, text=f"v{ver}", font=FTM,
                     fg=C["text_dim"], bg=C["card"]).pack(side="left", padx=(0, 8))
            if disabled:
                tk.Label(tag_row, text="disabled", font=FTM,
                         fg=C["error"], bg="#3a1f1f", padx=4).pack(side="left", padx=(0, 6))

            # Patch badge
            if is_man:
                badge_text, badge_fg, badge_bg = "✓ Manual", C["success"], "#0d2e1a"
            else:
                badge_text, badge_fg, badge_bg = "⚙ Launcher", C["warn"], "#2a1f0a"
            badge_lbl = tk.Label(inner_row, text=badge_text, font=("Segoe UI", 9, "bold"),
                                 fg=badge_fg, bg=badge_bg, padx=8, pady=3)
            badge_lbl.pack(side="right")

            # Bind click on every part of the row so it's easy to select
            for widget in (inner_row, info, tag_row, badge_lbl):
                widget.bind("<Button-1>", _toggle)
                widget.config(cursor="hand2")
            for child in info.winfo_children() + tag_row.winfo_children():
                try:
                    child.bind("<Button-1>", _toggle)
                    child.config(cursor="hand2")
                except Exception:
                    pass

    def _pt_update_count(self):
        """Update any count label — currently a no-op placeholder for future use."""
        pass

    def _pt_patch_selected(self):
        """Patch all checked installs as Manual."""
        selected = [p for p, v in self._pt_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Tick at least one install to patch.", parent=self)
            return
        if _launcher_is_running():
            if _kill_launcher():
                _log("[patcher] Launcher force-closed")
                self.after(600, lambda: self._pt_do_patch(selected))
                return
            else:
                _log("[patcher] Launcher detected but could not be killed")
        self._pt_do_patch(selected)

    def _pt_do_patch(self, paths: list):
        results = []
        for p in paths:
            msg = _silent_patch_as_manual(p)
            results.append(f"{'✓' if msg.startswith('Launcher patch') else '✗'}  {os.path.basename(p)}: {msg}")
            _log("[patcher] " + msg)
        messagebox.showinfo("Patch complete",
                            "\n".join(results) +
                            "\n\nOpen the Launcher and set the install as default.", parent=self)
        self._pt_refresh()

    def _pt_unpatch_selected(self):
        """Unpatch all checked installs back to Launcher-managed."""
        selected = [p for p, v in self._pt_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Tick at least one install to unpatch.", parent=self)
            return
        if _launcher_is_running():
            if _kill_launcher():
                _log("[patcher] Launcher force-closed for unpatch")
                self.after(600, lambda: self._pt_do_unpatch(selected))
                return
            else:
                _log("[patcher] Launcher detected but could not be killed")
        self._pt_do_unpatch(selected)

    def _pt_do_unpatch(self, paths: list):
        results = []
        for p in paths:
            msg = _unpatch_as_launcher(p)
            results.append(f"{'✓' if msg.startswith('Unpatch applied') else '✗'}  {os.path.basename(p)}: {msg}")
            _log("[patcher] " + msg)
        messagebox.showinfo("Unpatch complete", "\n".join(results), parent=self)
        self._pt_refresh()

    def _pt_remove_selected(self):
        """Remove selected entries entirely from game_installs.json."""
        selected = [p for p, v in self._pt_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Tick at least one install to remove.", parent=self)
            return
        names = "\n".join(f"  • {os.path.basename(p)}" for p in selected)
        if not messagebox.askyesno(
                "Remove entries",
                f"Remove {len(selected)} entry/entries from game_installs.json?\n\n"
                f"{names}\n\n"
                "This only removes them from the launcher's registry — "
                "it does NOT delete any files on disk.",
                parent=self):
            return
        if not _INSTALLS_FILE.is_file():
            messagebox.showerror("Error", "game_installs.json not found.", parent=self)
            return
        try:
            shutil.copy2(str(_INSTALLS_FILE), str(_INSTALLS_FILE) + ".bak")
            data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
            before = len(data.get("installs", []))
            norm = {os.path.normcase(os.path.normpath(p)) for p in selected}
            data["installs"] = [
                inst for inst in data.get("installs", [])
                if os.path.normcase(os.path.normpath(
                    inst.get("directoryPath", ""))) not in norm
            ]
            removed = before - len(data["installs"])
            _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            _log(f"[patcher] Removed {removed} entry/entries from game_installs.json")
            messagebox.showinfo(
                "Removed",
                f"Removed {removed} entry/entries.\n\n"
                "A backup was saved as game_installs.json.bak",
                parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove entries:\n{e}", parent=self)
            _log(f"[patcher] Remove failed: {e}")
        self._pt_refresh()

    # ── Discord Rich Presence ─────────────────────────────────────────────────
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
        win = tk.Toplevel(self)
        win.title("Discord Rich Presence")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        inner = tk.Frame(win, bg=C["bg"], padx=28, pady=24)
        inner.pack(fill="both")

        tk.Label(inner, text="Discord Rich Presence", font=("Segoe UI", 14, "bold"),
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

        close_btn = tk.Button(foot, text="Close", command=win.destroy,
                              bg=C["border"], fg=C["text_dim"], relief="flat",
                              font=FT, padx=12, pady=5, cursor="hand2")
        close_btn.pack(side="right")

        reconnect_btn = tk.Button(foot, text="Reconnect",
                                  bg=C["accent"], fg="white", relief="flat",
                                  font=FTB, padx=14, pady=5, cursor="hand2")
        reconnect_btn.pack(side="right", padx=(0, 6))

        def _reconnect():
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

        reconnect_btn.config(command=_reconnect)

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
            if page == "bgchanger":
                profile = getattr(self, "_active_name", "") or ""
                bg      = self._selected_bg()
                details = f"Profile: {profile}  ·  {bg}" if profile else f"Editing: {bg}"
                self._drpc.update(tool, details)
            elif page == "notegen":
                profile = getattr(self, "_ng_active_name", "") or ""
                details = f"Profile: {profile}" if profile else ""
                self._drpc.update(tool, details)
            else:
                self._drpc.update(tool)
            self._drpc_last_update = time.monotonic()

        self._drpc_pending = self.after(600, _do_update)

    # ── Launch Clone Hero ─────────────────────────────────────────────────────
    def _launch_clone_hero(self):
        """Launch from the default install (titlebar button)."""
        default_dir = self._cfg.get("ch_default_install", "") or self._cfg.get("ch_install_dir", "")

        # Fall back to first registered install if nothing saved
        if not default_dir or not os.path.isdir(default_dir):
            installs = _read_installs()
            if installs:
                default_dir = installs[0].get("directoryPath", "")

        exe = self._find_ch_exe(default_dir) if default_dir else None

        if not exe:
            answer = messagebox.askyesno(
                "Clone Hero not found",
                "CHSuite doesn't know which Clone Hero to launch.\n\n"
                "Go to the CHManager tab to set a default install,\n"
                "or browse to Clone Hero.exe now?",
                parent=self)
            if not answer:
                return
            exe = filedialog.askopenfilename(
                title="Select Clone Hero.exe",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
                initialdir=default_dir or str(Path.home()))
            if not exe:
                return
            found_dir = str(Path(exe).parent)
            self._cfg["ch_default_install"] = found_dir
            self._cfg["ch_install_dir"]     = found_dir
            _save_json(CONFIG_FILE, self._cfg)

        self._do_launch_exe(exe)

    @staticmethod
    def _find_ch_exe(directory: str):
        """Return path to Clone Hero.exe in directory, or None."""
        if not directory or not os.path.isdir(directory):
            return None
        for candidate in ("Clone Hero.exe", "clonehero.exe", "CloneHero.exe"):
            p = Path(directory) / candidate
            if p.is_file():
                return str(p)
        for p in Path(directory).glob("*.exe"):
            if "clone" in p.stem.lower() and "hero" in p.stem.lower():
                return str(p)
        return None

    def _do_launch_exe(self, exe_path: str):
        """
        Launch Clone Hero, minimize CHSuite to the taskbar while it runs,
        and restore automatically when Clone Hero exits.
        """
        try:
            proc = subprocess.Popen([exe_path], cwd=str(Path(exe_path).parent))
        except Exception as e:
            messagebox.showerror("Launch failed",
                                 f"Could not launch Clone Hero:\n{e}", parent=self)
            return

        self._status(f"Launched: {Path(exe_path).name}")

        # Minimize to taskbar
        self.iconify()

        def _watch():
            proc.wait()          # blocks until CH exits
            self.after(0, self._restore_from_taskbar)

        threading.Thread(target=_watch, daemon=True).start()

    def _restore_from_taskbar(self):
        """Bring CHSuite back to the foreground after Clone Hero closes."""
        self.deiconify()
        self.lift()
        self.focus_force()
        self._status("Clone Hero closed — welcome back!")

    def _gm_set_default_install(self, path: str):
        """Save path as the default Clone Hero install and refresh the list."""
        self._cfg["ch_default_install"] = path
        self._cfg["ch_install_dir"]     = path
        _save_json(CONFIG_FILE, self._cfg)
        self._gm_refresh_installs()
        self._gm_status(f"Default set: {os.path.basename(path)}")

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 6 — GAME MANAGER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_gamemanager(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["gamemanager"] = page

        inner = tk.Frame(page, bg=C["bg"], padx=24, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="CHManager",
                 font=("Segoe UI", 18, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner,
                 text="Manage Clone Hero installations, download new versions, and patch installs.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 16))

        # ── Split: left = installs, right = download ──────────────────────────
        split = tk.Frame(inner, bg=C["bg"])
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # ── LEFT: Local Installs ──────────────────────────────────────────────
        left_card = tk.Frame(split, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        lh = tk.Frame(left_card, bg=C["card"], padx=14, pady=10); lh.pack(fill="x")
        tk.Label(lh, text="LOCAL INSTALLS", font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(side="left")
        tk.Button(lh, text="↺ Refresh", command=self._gm_refresh_installs,
                  bg=C["border"], fg=C["text"], relief="flat",
                  font=FTS, padx=8, pady=2, cursor="hand2").pack(side="right")
        _sep(left_card, bg=C["border"]).pack(fill="x")

        inst_scroll = tk.Frame(left_card, bg=C["card"])
        inst_scroll.pack(fill="both", expand=True)
        vsb_inst = ttk.Scrollbar(inst_scroll, orient="vertical")
        vsb_inst.pack(side="right", fill="y")
        self._gm_inst_canvas = tk.Canvas(inst_scroll, bg=C["card"],
                                          highlightthickness=0,
                                          yscrollcommand=vsb_inst.set)
        self._gm_inst_canvas.pack(side="left", fill="both", expand=True)
        vsb_inst.config(command=self._gm_inst_canvas.yview)
        self._gm_inst_inner = tk.Frame(self._gm_inst_canvas, bg=C["card"])
        _inst_win = self._gm_inst_canvas.create_window((0, 0), window=self._gm_inst_inner, anchor="nw")
        def _inst_configure(e):
            bbox = self._gm_inst_canvas.bbox("all")
            if bbox:
                cw = self._gm_inst_canvas.winfo_height()
                h  = max(bbox[3], cw)
                self._gm_inst_canvas.configure(scrollregion=(0, 0, bbox[2], h))
        self._gm_inst_inner.bind("<Configure>", _inst_configure)
        self._gm_inst_canvas.bind("<Configure>", lambda e: self._gm_inst_canvas.itemconfig(
            _inst_win, width=e.width))
        def _inst_wheel(event):
            self._gm_inst_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._inst_wheel = _inst_wheel
        self._gm_inst_canvas.bind("<MouseWheel>", _inst_wheel)
        self._gm_inst_inner.bind("<MouseWheel>", _inst_wheel)

        # Add install buttons
        add_row = tk.Frame(left_card, bg=C["card"], padx=12, pady=8); add_row.pack(fill="x")
        tk.Button(add_row, text="+ Add Existing Install",
                  command=self._gm_add_install,
                  bg=C["accent_dim"], fg=C["text"], relief="flat",
                  font=FT, padx=10, pady=4, cursor="hand2").pack(side="left")

        # ── RIGHT: Download ───────────────────────────────────────────────────
        right_col = tk.Frame(split, bg=C["bg"])
        right_col.grid(row=0, column=1, sticky="nsew")

        dl_card = tk.Frame(right_col, bg=C["card"],
                           highlightbackground=C["border"], highlightthickness=1)
        dl_card.pack(fill="both", expand=True)

        dh = tk.Frame(dl_card, bg=C["card"], padx=14, pady=10); dh.pack(fill="x")
        tk.Label(dh, text="DOWNLOAD", font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(side="left")
        tk.Button(dh, text="↺ Check", command=self._gm_check_releases,
                  bg=C["border"], fg=C["text"], relief="flat",
                  font=FTS, padx=8, pady=2, cursor="hand2").pack(side="right")
        _sep(dl_card, bg=C["border"]).pack(fill="x")

        dl_inner = tk.Frame(dl_card, bg=C["card"], padx=14, pady=12)
        dl_inner.pack(fill="both", expand=True)

        self._gm_release_lbl = tk.Label(
            dl_inner,
            text="Click  ↺ Check  to load releases from GitHub.",
            font=FT, fg=C["text_dim"], bg=C["card"], justify="left")
        self._gm_release_lbl.pack(anchor="w", pady=(0, 8))

        # ── Tabbed download panel (Release / PTB) ─────────────────────────────
        _nb_style = ttk.Style()
        _nb_style.configure("DL.TNotebook",        background=C["card"], borderwidth=0)
        _nb_style.configure("DL.TNotebook.Tab",    background=C["border"], foreground=C["text_dim"],
                            padding=[10, 4], font=("Segoe UI", 9, "bold"))
        _nb_style.map("DL.TNotebook.Tab",
                      background=[("selected", C["accent_dim"])],
                      foreground=[("selected", C["text"])])

        dl_nb = ttk.Notebook(dl_inner, style="DL.TNotebook")
        dl_nb.pack(fill="both", expand=True, pady=(0, 6))

        tab_rel = tk.Frame(dl_nb, bg=C["card"])
        tab_ptb = tk.Frame(dl_nb, bg=C["card"])
        dl_nb.add(tab_rel, text="  Release  ")
        dl_nb.add(tab_ptb, text="  PTB  ")

        def _make_scrollable_tab(parent):
            vsb = ttk.Scrollbar(parent, orient="vertical")
            vsb.pack(side="right", fill="y")
            cv = tk.Canvas(parent, bg=C["card"], highlightthickness=0,
                           yscrollcommand=vsb.set)
            cv.pack(side="left", fill="both", expand=True)
            vsb.config(command=cv.yview)
            inner_f = tk.Frame(cv, bg=C["card"])
            cv.create_window((0, 0), window=inner_f, anchor="nw")
            inner_f.bind("<Configure>", lambda e: cv.configure(
                scrollregion=cv.bbox("all")))
            def _on_wheel(event, _cv=cv):
                _cv.yview_scroll(int(-1 * (event.delta / 120)), "units")
            cv.bind("<MouseWheel>", _on_wheel)
            inner_f.bind("<MouseWheel>", _on_wheel)
            return inner_f

        self._gm_rel_frame = _make_scrollable_tab(tab_rel)
        self._gm_ptb_frame = _make_scrollable_tab(tab_ptb)

        # Progress bar (hidden until download starts)
        self._gm_progress_var = tk.DoubleVar(value=0)
        self._gm_progress = ttk.Progressbar(
            dl_inner, variable=self._gm_progress_var,
            maximum=100, length=260)
        self._gm_progress_lbl = tk.Label(dl_inner, text="", font=FTM,
                                          fg=C["text_dim"], bg=C["card"])

        # Status line
        self._gm_status_lbl = tk.Label(dl_inner, text="", font=FTM,
                                        fg=C["text_dim"], bg=C["card"], anchor="w")
        self._gm_status_lbl.pack(fill="x", pady=(4, 0))

        # Internal state
        self._gm_releases = []      # list of release dicts from GitHub API
        self._gm_dl_thread = None

        self._gm_refresh_installs()

    # ── Game Manager helpers ──────────────────────────────────────────────────

    def _gm_refresh_installs(self):
        """Rebuild the local installs list from game_installs.json."""
        for w in self._gm_inst_inner.winfo_children():
            w.destroy()
        self._gm_inst_canvas.yview_moveto(0)

        installs = _read_installs()
        if not installs:
            tk.Label(self._gm_inst_inner,
                     text="No installs found in game_installs.json.\n"
                          "Run the Clone Hero Launcher at least once,\n"
                          "or add an install manually below.",
                     font=FT, fg=C["text_dim"], bg=C["card"],
                     justify="left").pack(padx=14, pady=14, anchor="w")
            return

        default_dir = os.path.normcase(os.path.normpath(
            self._cfg.get("ch_default_install", "") or
            self._cfg.get("ch_install_dir", "")))

        # Auto-remove entries whose exe is missing
        valid_installs = []
        removed_any = False
        for inst in installs:
            p = inst.get("directoryPath", "")
            if p and not (Path(p) / "Clone Hero.exe").is_file():
                # Remove from game_installs.json silently
                try:
                    data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
                    norm = os.path.normcase(os.path.normpath(p))
                    data["installs"] = [
                        i for i in data.get("installs", [])
                        if os.path.normcase(os.path.normpath(
                            i.get("directoryPath", ""))) != norm
                    ]
                    _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    removed_any = True
                    _log(f"[gm] Auto-removed missing install: {p}")
                except Exception as e:
                    _log(f"[gm] Could not remove missing entry: {e}")
            else:
                valid_installs.append(inst)
        installs = valid_installs

        if not installs:
            tk.Label(self._gm_inst_inner,
                     text="No installs found in game_installs.json.\n"
                          "Run the Clone Hero Launcher at least once,\n"
                          "or add an install manually below.",
                     font=FT, fg=C["text_dim"], bg=C["card"],
                     justify="left").pack(padx=14, pady=14, anchor="w")
            return

        for inst in installs:
            path     = inst.get("directoryPath", "?")
            ver      = inst.get("version") or "?"
            is_man   = inst.get("isFromLauncher") is False
            disabled = inst.get("disabled", False)
            exe_path = Path(path) / "Clone Hero.exe"
            exe_ok   = exe_path.is_file()
            is_def   = os.path.normcase(os.path.normpath(path)) == default_dir

            row_bg = C["card2"] if is_def else C["card"]

            row = tk.Frame(self._gm_inst_inner, bg=row_bg)
            row.pack(fill="x")
            _sep(row, bg=C["accent"] if is_def else C["border"]).pack(fill="x")
            ri = tk.Frame(row, bg=row_bg, padx=14, pady=10)
            ri.pack(fill="x")
            # Propagate mousewheel from row widgets
            for _w in (row, ri):
                _w.bind("<MouseWheel>", self._inst_wheel)

            # Left info
            info = tk.Frame(ri, bg=row_bg); info.pack(side="left", fill="x", expand=True)
            name_fg = C["text_dim"] if disabled else C["text"]
            name_row = tk.Frame(info, bg=row_bg); name_row.pack(anchor="w")

            # Default star badge
            if is_def:
                tk.Label(name_row, text="★", font=("Segoe UI", 12),
                         fg=C["warn"], bg=row_bg).pack(side="left", padx=(0, 5))
            tk.Label(name_row, text=os.path.basename(path), font=FTB,
                     fg=name_fg, bg=row_bg).pack(side="left")

            tk.Label(info, text=path, font=FTM, fg=C["text_dim"],
                     bg=row_bg).pack(anchor="w")

            tag_r = tk.Frame(info, bg=row_bg); tag_r.pack(anchor="w", pady=(2, 0))
            tk.Label(tag_r, text=f"v{ver}", font=FTS, fg=C["text_dim"],
                     bg=row_bg).pack(side="left", padx=(0, 8))
            if is_man:
                tk.Label(tag_r, text="Manual", font=FTS, fg=C["success"],
                         bg="#0d2e1a", padx=4).pack(side="left", padx=(0, 4))
            else:
                tk.Label(tag_r, text="Launcher", font=FTS, fg=C["warn"],
                         bg="#2a1f0a", padx=4).pack(side="left", padx=(0, 4))
            if is_def:
                tk.Label(tag_r, text="default", font=FTS, fg=C["warn"],
                         bg="#2a1200", padx=4).pack(side="left", padx=(0, 4))
            if disabled:
                tk.Label(tag_r, text="disabled", font=FTS, fg=C["error"],
                         bg="#3a1f1f", padx=4).pack(side="left")

            # Right: buttons
            # ── Buttons: 2-column grid, uniform width ────────────────────────
            btn_col = tk.Frame(ri, bg=row_bg)
            btn_col.pack(side="right", padx=(8, 0))

            # Shared kwargs for all small buttons
            _bs = dict(relief="flat", font=FTS, cursor="hand2", width=10, pady=2)

            # Row 0: Set as Default (spans both cols, only if not default)
            if not is_def:
                tk.Button(btn_col, text="★ Default",
                          command=lambda p=path: self._gm_set_default_install(p),
                          bg="#2a1f0a", fg=C["warn"], **_bs
                          ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3))

            # Row 1: Launch | Open folder
            if exe_ok:
                launch_bg = C["success"] if is_def else C["border"]
                launch_fg = "#000" if is_def else C["text"]
                tk.Button(btn_col, text="▶ Launch",
                          command=lambda p=str(exe_path): self._do_launch_exe(p),
                          bg=launch_bg, fg=launch_fg,
                          relief="flat", font=("Segoe UI", 9, "bold"),
                          cursor="hand2", width=10, pady=3
                          ).grid(row=1, column=0, sticky="ew", padx=(0, 3))
            else:
                tk.Label(btn_col, text="missing", font=FTS,
                         fg=C["error"], bg=row_bg, width=10
                         ).grid(row=1, column=0, padx=(0, 3))
            tk.Button(btn_col, text="📂 Folder",
                      command=lambda p=path: self._gm_open_folder(p),
                      bg=C["border"], fg=C["text"], **_bs
                      ).grid(row=1, column=1, sticky="ew")

            # Row 2: Patch | Unpatch
            tk.Button(btn_col, text="⚙ Patch",
                      command=lambda p=path: self._gm_patch_install(p),
                      bg="#1a2a1a", fg=C["success"], **_bs
                      ).grid(row=2, column=0, sticky="ew", padx=(0, 3), pady=(3, 0))
            tk.Button(btn_col, text="↺ Unpatch",
                      command=lambda p=path: self._gm_unpatch_install(p),
                      bg="#2a1f0a", fg=C["warn"], **_bs
                      ).grid(row=2, column=1, sticky="ew", pady=(3, 0))

            # Row 3: Delete (spans both cols)
            tk.Button(btn_col, text="🗑 Delete",
                      command=lambda p=path: self._gm_delete_install(p),
                      bg="#3a1f1f", fg=C["error"], **_bs
                      ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(3, 0))

    def _gm_launch_exe(self, exe_path: str):
        """Kept for compatibility — delegates to shared _do_launch_exe."""
        self._do_launch_exe(exe_path)

    def _gm_open_folder(self, path: str):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _gm_patch_install(self, path: str):
        """Patch a single install (mark as Manual so the launcher won't overwrite files)."""
        if _launcher_is_running():
            if _kill_launcher():
                _log("[gm] Launcher force-closed before patch")
                self.after(600, lambda: self._gm_patch_install(path))
                return
        msg = _silent_patch_as_manual(path)
        ok  = msg.startswith("Launcher patch")
        messagebox.showinfo("Patch complete" if ok else "Patch failed",
                            f"{'✓' if ok else '✗'}  {os.path.basename(path)}\n\n{msg}",
                            parent=self)
        if ok:
            self._gm_status(f"Patched: {os.path.basename(path)}")
        self._gm_refresh_installs()

    def _gm_unpatch_install(self, path: str):
        """Unpatch a single install (restore Launcher-managed mode)."""
        if _launcher_is_running():
            if _kill_launcher():
                _log("[gm] Launcher force-closed before unpatch")
                self.after(600, lambda: self._gm_unpatch_install(path))
                return
        msg = _unpatch_as_launcher(path)
        ok  = msg.startswith("Unpatch applied")
        messagebox.showinfo("Unpatch complete" if ok else "Unpatch failed",
                            f"{'✓' if ok else '✗'}  {os.path.basename(path)}\n\n{msg}",
                            parent=self)
        if ok:
            self._gm_status(f"Unpatched: {os.path.basename(path)}")
        self._gm_refresh_installs()

    def _gm_delete_install(self, path: str):
        """Delete the install folder and remove its entry from game_installs.json."""
        if not messagebox.askyesno(
                "Delete install",
                f"This will permanently delete:\n\n{path}\n\n"
                "and all its contents. This cannot be undone.\n\nContinue?",
                icon="warning", parent=self):
            return
        # Remove folder
        try:
            shutil.rmtree(path, ignore_errors=False)
        except Exception as e:
            messagebox.showerror("Delete failed",
                                 f"Could not delete folder:\n{e}", parent=self)
            return
        # Remove from game_installs.json
        if _INSTALLS_FILE.is_file():
            try:
                data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
                norm = os.path.normcase(os.path.normpath(path))
                data["installs"] = [
                    i for i in data.get("installs", [])
                    if os.path.normcase(os.path.normpath(
                        i.get("directoryPath", ""))) != norm
                ]
                _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                _log(f"[gm] Could not update game_installs.json after delete: {e}")
        # If deleted install was the default, clear it
        for key in ("ch_default_install", "ch_install_dir"):
            if os.path.normcase(os.path.normpath(
                    self._cfg.get(key, ""))) == os.path.normcase(
                    os.path.normpath(path)):
                self._cfg.pop(key, None)
        _save_json(CONFIG_FILE, self._cfg)
        self._gm_status(f"Deleted: {os.path.basename(path)}")
        self._gm_refresh_installs()

    def _gm_add_install(self):
        """Browse to a Clone Hero install folder and register it in game_installs.json."""
        folder = filedialog.askdirectory(
            title="Select Clone Hero install folder",
            initialdir=str(Path.home()))
        if not folder:
            return

        exe = Path(folder) / "Clone Hero.exe"
        if not exe.is_file():
            if not messagebox.askyesno(
                    "Exe not found",
                    f"Clone Hero.exe was not found in:\n{folder}\n\n"
                    "Add it anyway?", parent=self):
                return

        if not _INSTALLS_FILE.is_file():
            messagebox.showerror(
                "Launcher not found",
                "game_installs.json doesn't exist yet.\n"
                "Run the Clone Hero Launcher at least once first.", parent=self)
            return

        try:
            shutil.copy2(str(_INSTALLS_FILE), str(_INSTALLS_FILE) + ".bak")
            data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
            existing = [os.path.normcase(os.path.normpath(i.get("directoryPath", "")))
                        for i in data.get("installs", [])]
            norm = os.path.normcase(os.path.normpath(folder))
            if norm in existing:
                messagebox.showinfo("Already registered",
                                    "That folder is already in game_installs.json.", parent=self)
                return
            data.setdefault("installs", []).append({
                "directoryPath": folder,
                "isFromLauncher": False,
                "version": None,
                "manifestVersion": None,
                "manifestDate": None,
                "releaseChannel": "stable",
                "disabled": False,
            })
            _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self._gm_status(f"Added: {os.path.basename(folder)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not update game_installs.json:\n{e}", parent=self)
        self._gm_refresh_installs()

    def _gm_check_releases(self):
        """Fetch the latest Clone Hero releases from the GitHub API in a thread."""
        if not _REQUESTS_OK:
            messagebox.showerror("Missing dependency",
                                 "The 'requests' library is required to check for releases.",
                                 parent=self)
            return
        self._gm_release_lbl.config(text="Checking GitHub…", fg=C["text_mid"])
        for frame in (self._gm_rel_frame, self._gm_ptb_frame):
            for w in frame.winfo_children():
                w.destroy()

        def _worker():
            try:
                url = "https://api.github.com/repos/clonehero-game/releases/releases?per_page=50"
                resp = requests.get(url, timeout=15,
                                    headers={"Accept": "application/vnd.github+json"})
                resp.raise_for_status()
                releases = resp.json()
                self._gm_releases = releases
                self.after(0, self._gm_populate_releases)
            except Exception as e:
                self.after(0, lambda: self._gm_release_lbl.config(
                    text=f"Could not fetch releases:\n{e}", fg=C["error"]))

        threading.Thread(target=_worker, daemon=True).start()

    def _gm_populate_releases(self):
        """Populate the Release and PTB download tabs with fetched release data."""
        for frame in (self._gm_rel_frame, self._gm_ptb_frame):
            for w in frame.winfo_children():
                w.destroy()

        if not self._gm_releases:
            self._gm_release_lbl.config(text="No releases found.", fg=C["text_dim"])
            return

        # Split by release type
        full_rels = [r for r in self._gm_releases if not r.get("prerelease", False)]
        ptb_rels  = [r for r in self._gm_releases if r.get("prerelease", False)]

        # Sort newest → oldest by version number extracted from tag_name,
        # falling back to published_at date as a tiebreaker.
        def _ver_key(r):
            tag = r.get("tag_name", "") or r.get("name", "") or ""
            # Extract all numeric parts from the tag, e.g. "v0.9.3-PTB1" → (0, 9, 3, 1)
            parts = tuple(int(x) for x in re.findall(r"\d+", tag))
            date  = r.get("published_at") or r.get("created_at") or ""
            return (parts, date)

        full_rels.sort(key=_ver_key, reverse=True)
        ptb_rels.sort(key=_ver_key,  reverse=True)

        # Detect host architecture
        _machine = platform.machine().lower()
        _is_64   = _machine in ("amd64", "x86_64") or (
            _machine == "x86" and platform.architecture()[0] == "64bit")

        arch_str = "x64" if _is_64 else "x32"
        self._gm_release_lbl.config(
            text=f"Found {len(full_rels)} release(s)  ·  {len(ptb_rels)} PTB  ·  showing {arch_str}",
            fg=C["text"])

        def _win_asset(release):
            """Return the Windows asset matching the host architecture."""
            WIN_EXTS = (".exe", ".7z", ".zip")
            arch_tag   = "64" if _is_64 else "32"
            anti_tag   = "32" if _is_64 else "64"
            candidates = []
            fallback   = []
            for a in release.get("assets", []):
                n = a["name"].lower()
                if not any(n.endswith(ext) for ext in WIN_EXTS):
                    continue
                if not ("win" in n or "windows" in n):
                    continue
                if anti_tag in n:
                    continue          # wrong bitness — skip entirely
                if arch_tag in n:
                    candidates.append(a)
                else:
                    fallback.append(a)   # win asset with no explicit bitness tag
            pool = candidates if candidates else fallback
            # Prefer .exe → .7z → .zip
            def _ext_rank(a):
                n = a["name"].lower()
                for i, ext in enumerate(WIN_EXTS):
                    if n.endswith(ext):
                        return i
                return 99
            pool.sort(key=_ext_rank)
            return pool[0] if pool else None

        def _populate_frame(frame, releases):
            if not releases:
                tk.Label(frame, text="No releases found.", font=FT,
                         fg=C["text_dim"], bg=C["card"]).pack(padx=8, pady=8, anchor="w")
                return

            # Grab the canvas ancestor so we can re-bind wheel on new widgets
            cv = frame.master

            def _on_wheel(event, _cv=cv):
                _cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

            for rel in releases:
                asset = _win_asset(rel)
                if not asset:
                    continue
                rtag    = rel.get("tag_name", "?")
                rname   = rel.get("name", rtag)
                pub     = rel.get("published_at", "")[:10]
                size_mb = asset.get("size", 0) / 1_048_576

                row = tk.Frame(frame, bg=C["card"])
                row.pack(fill="x", pady=(0, 6), padx=4)
                for w in (row,):
                    w.bind("<MouseWheel>", _on_wheel)

                lbl_name = tk.Label(row, text=rname, font=FTB, fg=C["text"], bg=C["card"])
                lbl_name.pack(anchor="w")
                lbl_name.bind("<MouseWheel>", _on_wheel)

                lbl_info = tk.Label(row,
                    text=f"{pub}  ·  {size_mb:.1f} MB  ·  {asset['name']}",
                    font=FTS, fg=C["text_dim"], bg=C["card"])
                lbl_info.pack(anchor="w")
                lbl_info.bind("<MouseWheel>", _on_wheel)

                tk.Button(row, text="⬇ Download & Install",
                          command=lambda a=asset, r=rtag: self._gm_start_download(a, r),
                          bg=C["accent"], fg="white", relief="flat",
                          font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                          cursor="hand2").pack(anchor="w", pady=(4, 0))

        _populate_frame(self._gm_rel_frame, full_rels)
        _populate_frame(self._gm_ptb_frame, ptb_rels)

    def _gm_start_download(self, asset: dict, tag: str):
        """Download a release zip and extract it to the chosen destination."""
        if not _REQUESTS_OK:
            return

        # Ask the user where to install
        initial = self._cfg.get("ch_install_dir", str(Path.home() / "Documents" / "Clone Hero"))
        dest_base = filedialog.askdirectory(
            title=f"Choose install folder for Clone Hero {tag}",
            initialdir=initial,
            parent=self)
        if not dest_base:
            return  # user cancelled

        dest_dir = Path(dest_base)
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create folder:\n{e}", parent=self)
            return

        url      = asset["browser_download_url"]
        filename = asset["name"]
        zip_path = dest_dir / filename
        total    = asset.get("size", 0)

        # Show progress bar
        self._gm_progress_var.set(0)
        self._gm_progress.pack(anchor="w", pady=(8, 2))
        self._gm_progress_lbl.config(text="Starting download…")
        self._gm_progress_lbl.pack(anchor="w")
        self.update_idletasks()

        # Disable buttons during download
        for frame in (self._gm_rel_frame, self._gm_ptb_frame):
            for w in frame.winfo_children():
                for child in w.winfo_children():
                    try: child.config(state="disabled")
                    except Exception: pass

        def _worker():
            try:
                _log(f"[gm] Downloading {filename} from {url}")
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    downloaded = 0
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = downloaded / total * 100
                                self.after(0, lambda p=pct: (
                                    self._gm_progress_var.set(p),
                                    self._gm_progress_lbl.config(
                                        text=f"Downloading…  {downloaded/1_048_576:.1f} / "
                                             f"{total/1_048_576:.1f} MB")))

                self.after(0, lambda: self._gm_progress_lbl.config(text="Extracting…"))
                fname_lower = filename.lower()
                if fname_lower.endswith(".exe"):
                    _log(f"[gm] Running Inno Setup silent install: {zip_path}")
                    self.after(0, lambda: self._gm_progress_lbl.config(
                        text="Running installer… (this may take a moment)"))

                    # Watcher thread: auto-click Yes on any popup during install
                    # (e.g. the Portable Mode confirmation dialog).
                    _stop_watcher = threading.Event()
                    def _dialog_watcher(stop_evt=_stop_watcher, _proc=None):
                        if sys.platform != "win32":
                            return
                        import ctypes, ctypes.wintypes
                        user32    = ctypes.windll.user32
                        kernel32  = ctypes.windll.kernel32
                        BM_CLICK  = 0x00F5
                        GW_CHILD  = 5
                        GW_HWNDNEXT = 2
                        SMTO_ABORTIFHUNG = 0x0002

                        def _get_text(hwnd):
                            buf = ctypes.create_unicode_buffer(256)
                            user32.GetWindowTextW(hwnd, buf, 256)
                            return buf.value

                        def _get_class(hwnd):
                            buf = ctypes.create_unicode_buffer(256)
                            user32.GetClassNameW(hwnd, buf, 256)
                            return buf.value

                        def _find_yes_in(parent):
                            child = user32.GetWindow(parent, GW_CHILD)
                            while child:
                                cls = _get_class(child)
                                txt = _get_text(child).replace("&","").strip().lower()
                                if cls == "Button" and txt == "yes":
                                    return child
                                child = user32.GetWindow(child, GW_HWNDNEXT)
                            return None

                        EnumWindowsProc = ctypes.WINFUNCTYPE(
                            ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

                        clicked = set()
                        while not stop_evt.is_set():
                            wins = []
                            def _cb(hwnd, _, _lst=wins):
                                _lst.append(hwnd)
                                return True
                            user32.EnumWindows(EnumWindowsProc(_cb), 0)

                            for hwnd in wins:
                                if hwnd in clicked:
                                    continue
                                # Only act on dialog-class windows
                                if _get_class(hwnd) != "#32770":
                                    continue
                                # Try control ID 6 (IDYES from MB_YESNO MessageBox)
                                yes_btn = user32.GetDlgItem(hwnd, 6)
                                # Also try scanning children for a "Yes" Button
                                if not yes_btn:
                                    yes_btn = _find_yes_in(hwnd)
                                if yes_btn:
                                    _log("[gm] Auto-clicking Yes on installer dialog")
                                    clicked.add(hwnd)
                                    user32.SetForegroundWindow(hwnd)
                                    # Use PostMessage so the button processes the click
                                    user32.PostMessageW(yes_btn, BM_CLICK, 0, 0)
                            stop_evt.wait(0.1)

                    watcher = threading.Thread(target=_dialog_watcher, daemon=True)
                    watcher.start()
                    try:
                        result = subprocess.run(
                            [str(zip_path), "/VERYSILENT", "/CURRENTUSER",
                             "/TYPE=portable", f"/DIR={dest_dir}"],
                            timeout=300)
                    finally:
                        _stop_watcher.set()
                    zip_path.unlink(missing_ok=True)
                    if result.returncode != 0:
                        raise RuntimeError(
                            f"Installer exited with code {result.returncode}.")
                elif fname_lower.endswith(".7z"):
                    _log(f"[gm] Extracting .7z {zip_path} → {dest_dir}")
                    # Try py7zr first, fall back to system 7z/7za
                    try:
                        import py7zr
                        with py7zr.SevenZipFile(zip_path, mode="r") as z:
                            z.extractall(path=dest_dir)
                    except ImportError:
                        # Try system 7z binary
                        found_7z = None
                        for cmd in ("7z", "7za", r"C:\Program Files\7-Zip\7z.exe"):
                            try:
                                subprocess.run([cmd, "i"], capture_output=True, timeout=5)
                                found_7z = cmd
                                break
                            except Exception:
                                pass
                        if found_7z:
                            subprocess.run(
                                [found_7z, "x", str(zip_path), f"-o{dest_dir}", "-y"],
                                check=True)
                        else:
                            raise RuntimeError(
                                "Cannot extract .7z: install py7zr (pip install py7zr) "
                                "or 7-Zip.")
                    zip_path.unlink(missing_ok=True)
                else:
                    _log(f"[gm] Extracting .zip {zip_path} → {dest_dir}")
                    import zipfile
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(dest_dir)
                    zip_path.unlink(missing_ok=True)

                # Register in game_installs.json if launcher JSON exists
                self.after(0, lambda: self._gm_post_install(str(dest_dir), tag))

            except Exception as e:
                _log(f"[gm] Download failed: {e}")
                self.after(0, lambda err=str(e): (
                    self._gm_progress.pack_forget(),
                    self._gm_progress_lbl.pack_forget(),
                    messagebox.showerror("Download failed", err, parent=self),
                    self._gm_refresh_installs()))

        threading.Thread(target=_worker, daemon=True).start()

    def _gm_post_install(self, install_dir: str, tag: str):
        """After a successful download+extract, register and patch the new install."""
        self._gm_progress.pack_forget()
        self._gm_progress_lbl.pack_forget()

        # Look for the actual game folder inside dest (zip may have a subfolder)
        actual = install_dir
        for item in Path(install_dir).iterdir():
            if item.is_dir() and (item / "Clone Hero.exe").is_file():
                actual = str(item)
                break

        # Register in game_installs.json as Manual
        if _INSTALLS_FILE.is_file():
            try:
                shutil.copy2(str(_INSTALLS_FILE), str(_INSTALLS_FILE) + ".bak")
                data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
                existing = {os.path.normcase(os.path.normpath(i.get("directoryPath", "")))
                            for i in data.get("installs", [])}
                if os.path.normcase(os.path.normpath(actual)) not in existing:
                    data.setdefault("installs", []).append({
                        "directoryPath": actual,
                        "isFromLauncher": False,
                        "version": tag.lstrip("v"),
                        "manifestVersion": None,
                        "manifestDate": None,
                        "releaseChannel": "stable",
                        "disabled": False,
                    })
                    _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    _log(f"[gm] Registered {actual} in game_installs.json")
            except Exception as e:
                _log(f"[gm] Could not register install: {e}")

        # Save as default install dir
        self._cfg["ch_install_dir"] = actual
        _save_json(CONFIG_FILE, self._cfg)

        self._gm_status(f"Installed {tag} → {actual}")
        messagebox.showinfo(
            "Installation complete",
            f"Clone Hero {tag} installed to:\n{actual}\n\n"
            "It has been added to your installs list.",
            parent=self)
        self._gm_refresh_installs()

    def _gm_status(self, msg: str):
        if hasattr(self, "_gm_status_lbl"):
            self._gm_status_lbl.config(text=msg, fg=C["accent"])
            self.after(4000, lambda: self._gm_status_lbl.config(
                text="", fg=C["text_dim"]) if hasattr(self, "_gm_status_lbl") else None)

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
    if not getattr(sys, "frozen", False) and sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
    CHSuite().mainloop()


if __name__ == "__main__":
    main()
