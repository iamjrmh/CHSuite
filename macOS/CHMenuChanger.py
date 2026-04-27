"""
CHMenuChanger.py — Clone Hero menu background changer (CHMenuChanger)
=====================================================================
Split out of CHSuite.py.  Imports shared names from the main CHSuite module.
"""

# All shared module-level names live in CHSuite.py.  Wildcard import keeps
# every reference in the moved code resolving exactly the same way it did
# when the file was monolithic.  The import succeeds because CHSuite.py
# defines every shared name BEFORE importing this file (mixins are imported
# at the bottom of CHSuite.py just before the class definition).
import sys as _sys
if "CHSuite" not in _sys.modules:
    _sys.modules["CHSuite"] = _sys.modules.get("__main__")

from CHSuite import *               # noqa: F401, F403
from CHSuite import (               # explicit re-imports for the names this
    C, FT, FTB, FTS, FTH, FTT, FTM, FT_LABEL,
    _IS_WINDOWS, _IS_LINUX, _IS_MAC, _CH_DATA_DIR,
    _CH_EXE_CANDIDATES_WIN, _CH_EXE_CANDIDATES_LIN, _CH_EXE_CANDIDATES_MAC,
    _MAC_CH_APP, _MAC_CH_DATA_PATH,
    _PIL_OK, _UNITYPY_OK, _REQUESTS_OK, _PYPRESENCE_OK,
    _app_dir, _resources_dir, _log,
    _load_json, _save_json,
    CONFIG_FILE, PROFILES_FILE, SCAN_LOG_FILE, THEMES_DIR, IPC_PORT,
    _silent_patch_as_manual, _unpatch_as_launcher,
    _read_installs, _INSTALLS_FILE,
    _launcher_is_running, _kill_launcher, _norm_path,
    StyledDropdown, RoundedButton, _RoundedNavBtn, _RoundedAboutCard,
    HoverTooltip, _card, _label, _sep,
)                                   # static-analysers happier
import os, sys, re, json, copy, math, colorsys, shutil, threading
import subprocess, tempfile, platform, configparser, datetime
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

try:
    import UnityPy
except ImportError:
    UnityPy = None

try:
    import requests
except ImportError:
    requests = None

# ── Module-level helpers/classes ─────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
#  SECTION 1 — BG CHANGER (CHMenuChanger)
# ──────────────────────────────────────────────────────────────────────────────

def _scroll_units(event) -> int:
    """Translate a MouseWheel / Button-4 / Button-5 event into scroll units.

    Handles three input cases correctly:
      • Linux         — Button-4 (up) / Button-5 (down), no delta
      • Windows/macOS mouse wheel — delta = ±120 per notch
      • macOS trackpad            — small continuous deltas (< ±120)
    """
    if event.num == 4:
        return -1
    if event.num == 5:
        return 1
    delta = getattr(event, "delta", 0)
    if not delta:
        return 0
    if _IS_MAC and abs(delta) < 120:
        # Trackpad: fires many small events — scale so ~40 delta ≈ 1 unit,
        # always scroll at least 1 unit so slow swipes still register.
        units = int(-delta / 8)
        return units if units != 0 else (-1 if delta > 0 else 1)
    # Standard mouse wheel: ±120 per notch on Windows and macOS
    return int(-delta / 120)


DEFAULT_PROFILE_NAME = "Default (Original)"
# On Linux the default install lives alongside the AppImage as clonehero-linux/
# On macOS it lives inside the /Applications/Clone Hero app bundle.
# On Windows it lives in ~/Documents/Clone Hero/
if _IS_LINUX:
    DEFAULT_DATA = str(_app_dir() / "clonehero-linux" / _CH_DATA_DIR)
elif _IS_MAC:
    DEFAULT_DATA = str(_MAC_CH_DATA_PATH)
else:
    DEFAULT_DATA = str(Path.home() / "Documents" / "Clone Hero" / _CH_DATA_DIR)

def _get_default_data():
    """Return the best known game data path (Clone Hero_Data on Windows, clonehero_Data on Linux).
    Priority:
      1. Explicitly saved default_data_path — returned as-is, no existence check
         (user set it deliberately; don't second-guess it)
      2. Game data dir (_CH_DATA_DIR) derived from ch_default_install / ch_install_dir
         (only used when default_data_path has never been set)
      3. Hardcoded Documents fallback
    """
    cfg = _load_json(CONFIG_FILE, {})
    saved = cfg.get("default_data_path", "")
    if saved:
        return saved
    for key in ("ch_default_install", "ch_install_dir"):
        install = cfg.get(key, "")
        if install:
            derived = os.path.join(install, _CH_DATA_DIR)
            if os.path.isdir(derived):
                return derived
    return DEFAULT_DATA

BACKGROUNDS = [
    "Spray", "Pastel Burst", "Groovy", "Grains",
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
        # Fallback: force-convert to RGBA32 (always encodable; avoids compressed-
        # format write failures that occur on macOS for textures like Light/Autumn)
        try:
            from UnityPy.enums import TextureFormat as TF
            d.m_TextureFormat = TF.RGBA32
            try:
                if hasattr(d, "set_image"):
                    d.set_image(rgba); d.save()
                    self._dirty.add(asset_name)
                    return True
            except Exception:
                pass
            d.image = rgba; d.save()
            self._dirty.add(asset_name)
            return True
        except Exception as e:
            _log(f"[WRITE FAIL] force-RGBA32 '{asset_name}': {e}")
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
        self.result = None   # game data path (Clone Hero_Data / clonehero_Data)

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
        tk.Label(hi, text="CHSuite", font=("Lato", 22, "bold"),
                 bg=C["panel"], fg=C["text"]).pack(side="left")
        tk.Label(hi, text="  by JURMR", font=("Lato", 13),
                 bg=C["panel"], fg=C["accent"]).pack(side="left", pady=(8, 0))

        # Patch status badge – top-right, updated after Confirm
        self._patch_badge = tk.Label(
            hi, text="", font=("Lato", 9, "bold"),
            bg=C["panel"], fg=C["text_dim"], padx=10, pady=4)
        self._patch_badge.pack(side="right", padx=(0, 4))
        self._update_patch_badge(None)

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self.win, bg=C["bg"], padx=28, pady=22)
        body.pack(fill="both")

        tk.Label(body,
                 text="Select your Clone Hero installation folder to get started.",
                 font=("Lato", 11), fg=C["text"], bg=C["bg"],
                 justify="left").pack(anchor="w", pady=(0, 18))

        # Path picker card
        pick_card = tk.Frame(body, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=18, pady=16)
        pick_card.pack(fill="x", pady=(0, 10))

        tk.Label(pick_card, text="CLONE HERO INSTALL FOLDER",
                 font=("Lato", 8, "bold"), fg=C["text_dim"],
                 bg=C["card"]).pack(anchor="w", pady=(0, 8))

        row = tk.Frame(pick_card, bg=C["card"]); row.pack(fill="x")
        self._path_var = tk.StringVar()
        self._path_entry = tk.Entry(row, textvariable=self._path_var,
                                    font=FTM)
        self._path_entry.pack(side="left", fill="x", expand=True)
        RoundedButton(row, "Browse…", self._browse,
                      bg_color=C["accent_dim"], hover_color=C["accent"],
                      text_color=C["text"], height=42, radius=14,
                      text_font=FT, canvas_bg=C["card"],
                      width=110).pack(side="left", padx=(8, 0))

        # Derived path preview
        self._derived_lbl = tk.Label(pick_card, text="",
                                      font=FTM, fg=C["text_dim"],
                                      bg=C["card"], anchor="w")
        self._derived_lbl.pack(fill="x", pady=(10, 0))
        self._path_var.trace_add("write", self._on_path_change)

        # Try to pre-fill with the most likely install location
        default = str(_app_dir() / "clonehero-linux") if _IS_LINUX \
                  else str(Path.home() / "Documents" / "Clone Hero")
        if os.path.isdir(default):
            self._path_var.set(default)

        # Info blurb
        info_card = tk.Frame(body, bg=C["card2"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=18, pady=14)
        info_card.pack(fill="x", pady=(4, 0))
        tk.Label(info_card,
                 text="This is the folder that contains \"Clone Hero.exe\".\n"
                      f"CHSuite will look for game assets inside the \"{_CH_DATA_DIR}\"\n"
                      "subfolder found within it.",
                 font=FT, fg=C["text_mid"], bg=C["card2"],
                 justify="left").pack(anchor="w")

        # ── Footer ────────────────────────────────────────────────────────────
        foot = tk.Frame(self.win, bg=C["panel"], padx=24, pady=14)
        foot.pack(fill="x")
        tk.Label(foot, text="Made by JURMR", font=FTS,
                 bg=C["panel"], fg=C["text_dim"]).pack(side="left")
        RoundedButton(foot, "Skip", self._skip,
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text_dim"], height=44, radius=18,
                      text_font=FT, canvas_bg=C["panel"],
                      width=108).pack(side="right", padx=(8, 0))
        self._confirm_btn = RoundedButton(foot, "Confirm  →", self._confirm,
                                          bg_color=C["accent"], hover_color=C["accent_dim"],
                                          text_color="white", height=44, radius=18,
                                          text_font=FTB, canvas_bg=C["panel"],
                                          width=152)
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
        data_path = os.path.join(p, _CH_DATA_DIR) if p else ""
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
        data_path = os.path.join(p, _CH_DATA_DIR)
        if not os.path.isdir(data_path):
            if not messagebox.askyesno(
                    "Folder not found",
                    f"\"{_CH_DATA_DIR}\" was not found inside:\n{p}\n\n"
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





# ─────────────────────────────────────────────────────────────────────────────
class CHMenuChangerMixin:
    """
    CHSuite mixin: methods that build and operate the CHMenuChanger page.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

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
        self._prof_cb  = StyledDropdown(pi, textvariable=self._prof_var,
                                        width=30, font=FT, state="readonly",
                                        canvas_bg=C["card2"], height=34)
        self._prof_cb.pack(side="left", padx=8)
        self._prof_cb.bind("<<ComboboxSelected>>", self._on_profile_combo)

        def pbtn(label, cmd, bg=C["border"]):
            _hov = "#5a2020" if bg == "#3d1a1a" else C["hover"]
            return RoundedButton(pi, label, cmd, bg_color=bg,
                                 hover_color=_hov, text_color=C["text"],
                                 height=38, radius=16, text_font=FT,
                                 canvas_bg=C["card2"])
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
                 font=("Lato", 8), bg=C["card2"], fg=C["text_dim"]).pack(side="right", padx=(14, 0))
        self._refresh_profile_combo()

        # ── Data folder bar ───────────────────────────────────────────────────
        ggm_bar = tk.Frame(page, bg=C["card"],
                           highlightbackground=C["border"], highlightthickness=1)
        ggm_bar.pack(fill="x")
        gi = tk.Frame(ggm_bar, bg=C["card"], padx=14, pady=9); gi.pack(fill="x")
        tk.Label(gi,
                 text="Clone Hero.app:" if _IS_MAC else f"{_CH_DATA_DIR} folder:",
                 font=FTB, bg=C["card"], fg=C["text_mid"]).pack(side="left")
        self._data_v = tk.StringVar(value=_get_default_data())
        tk.Entry(gi, textvariable=self._data_v,
                 width=56, font=FTM).pack(side="left", padx=8)
        RoundedButton(gi, "Browse…", self._browse_data,
                      bg_color=C["accent_dim"], hover_color=C["accent"],
                      text_color=C["text"], height=38, radius=14,
                      text_font=FT, canvas_bg=C["card"],
                      width=106).pack(side="left", padx=2)
        RoundedButton(gi, "Load & Scan", self._load_ggm,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="white", height=38, radius=14,
                      text_font=FTB, canvas_bg=C["card"],
                      width=120).pack(side="left", padx=2)
        self._backup_lbl = tk.Label(gi, text="", font=FTS, bg=C["card"], fg=C["text_dim"])
        self._backup_lbl.pack(side="right", padx=(0, 4))
        RoundedButton(gi, "Restore Backups", self._act_restore_backups,
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text_dim"], height=36, radius=14,
                      text_font=FTS, canvas_bg=C["card"],
                      width=140).pack(side="right", padx=4)

        # ── Main area ─────────────────────────────────────────────────────────
        main = tk.Frame(page, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=10, pady=8)

        # BG tree sidebar
        side = tk.Frame(main, bg=C["panel"], width=218)
        side.pack(side="left", fill="y", padx=(0, 8)); side.pack_propagate(False)
        tk.Label(side, text="BACKGROUNDS", font=("Lato", 8, "bold"),
                 bg=C["panel"], fg=C["accent"], pady=7).pack(fill="x", padx=12)
        lf  = tk.Frame(side, bg=C["panel"]); lf.pack(fill="both", expand=True, padx=6, pady=(0,6))
        vsb = ttk.Scrollbar(lf, orient="vertical")
        self._tree = ttk.Treeview(lf, selectmode="browse", show="tree",
                                   yscrollcommand=vsb.set, height=22,
                                   cursor="hand2")
        self._tree.column("#0", width=195)
        vsb.config(command=self._tree.yview)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Hover highlight for rows
        self._tree_hovered = None
        def _tree_hover(event):
            iid = self._tree.identify_row(event.y)
            if iid == self._tree_hovered:
                return
            if self._tree_hovered and self._tree_hovered not in self._tree.selection():
                self._tree.item(self._tree_hovered, tags=())
            self._tree_hovered = iid
            if iid and iid not in self._tree.selection():
                self._tree.item(iid, tags=("hover",))
        def _tree_leave(event):
            if self._tree_hovered and self._tree_hovered not in self._tree.selection():
                self._tree.item(self._tree_hovered, tags=())
            self._tree_hovered = None
        self._tree.tag_configure("hover", background=C["hover"])
        self._tree.bind("<Motion>", _tree_hover)
        self._tree.bind("<Leave>",  _tree_leave)

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

        ctrl = tk.Frame(right, bg=C["panel"], padx=14, pady=8)
        ctrl.pack(fill="x", pady=(8, 0))

        # Row 1: selection info
        info_row = tk.Frame(ctrl, bg=C["panel"])
        info_row.pack(fill="x", pady=(0, 6))
        self._sel_lbl = tk.Label(info_row, text="Selected: -",
                                  font=FTH, bg=C["panel"], fg=C["text"])
        self._sel_lbl.pack(side="left")
        self._req_lbl = tk.Label(info_row, text="", font=FTS, bg=C["panel"], fg=C["text_dim"])
        self._req_lbl.pack(side="left", padx=(10, 0))
        tk.Label(info_row, text="Ctrl+S = Apply & Save", font=FTS,
                 bg=C["panel"], fg=C["text_dim"]).pack(side="right")

        # Row 2: action buttons
        btn_row = tk.Frame(ctrl, bg=C["panel"])
        btn_row.pack(fill="x")
        def cbtn(t, cmd, bg=C["border"], fg=C["text"], bold=False):
            _hov = C["accent_dim"] if bg in (C["accent"], C["accent2"]) else C["hover"]
            return RoundedButton(btn_row, t, cmd, bg_color=bg,
                                 hover_color=_hov, text_color=fg,
                                 height=38, radius=14,
                                 text_font=(FTB if bold else FT),
                                 canvas_bg=C["panel"])
        self._apply_btn = cbtn("💾 Save and Apply", self._act_apply_all, C["accent2"], "white", True)
        self._apply_btn.pack(side="left", padx=(0, 6))
        cbtn("📂 Choose Replacement", self._act_choose_replacement, C["accent_dim"]).pack(side="left", padx=(0, 6))
        cbtn("✖ Clear",               self._act_clear_replacement).pack(side="left")

        # Status bar
        sbar = tk.Frame(page, bg=C["panel"], pady=5)
        sbar.pack(fill="x", side="bottom")
        tk.Label(sbar, textvariable=self._status_v, font=FTM,
                 bg=C["panel"], fg=C["text_mid"], padx=14).pack(side="left")

    def _make_bg_card(self, parent, label, label_fg):
        card = tk.Frame(parent, bg=C["card"],
                        highlightbackground=C["border"], highlightthickness=1)
        tk.Label(card, text=label, font=("Lato", 9, "bold"),
                 bg=C["card"], fg=label_fg, pady=5).pack(fill="x", padx=10)
        cv = tk.Canvas(card, bg=C["bg"], bd=0, highlightthickness=0, height=295)
        cv.pack(fill="both", expand=True, padx=6, pady=(0, 3))
        info = tk.Label(card, text="", font=FTS, bg=C["card"], fg=C["text_dim"])
        info.pack(pady=(0, 5))
        card._cv        = cv
        card._info      = info
        card._ph_text   = ""   # track current placeholder text so resize can redraw it
        cv.bind("<Configure>", lambda e, c=cv, k=card: self._on_bg_resize(c, k))

        # Right-click on the Current card -> Export context menu
        def _on_right_click(event, k=card):
            if k is not self._orig_card:
                return
            bg = self._selected_bg()
            if not bg or not self._asset_cache.get(bg):
                return
            m = tk.Menu(self, tearoff=0,
                        bg=C["card"], fg=C["text"],
                        activebackground=C["accent"], activeforeground="white",
                        bd=0, relief="flat")
            m.add_command(label="Export original as PNG…",
                          command=self._act_export_orig)
            m.tk_popup(event.x_root, event.y_root)
        cv.bind("<Button-3>", _on_right_click)

        # Don't draw placeholder at construction time — canvas has no real size yet.
        # It will be drawn correctly on the first <Configure> event once laid out.
        return card

    # ── BG profile management ─────────────────────────────────────────────────
    def _load_initial_profile(self):
        if DEFAULT_PROFILE_NAME not in self._profiles:
            self._profiles[DEFAULT_PROFILE_NAME] = _blank_profile(DEFAULT_PROFILE_NAME)
        self._profiles[DEFAULT_PROFILE_NAME]["locked"] = True
        self._profiles[DEFAULT_PROFILE_NAME]["replacements"] = {}
        # Always keep the Default profile's data_path in sync with the best
        # known path — otherwise a stale path baked in at first launch persists.
        self._profiles[DEFAULT_PROFILE_NAME]["data_path"] = _get_default_data()
        _save_profiles(self._profiles)
        last = self._cfg.get("last_profile", "")
        if last and last in self._profiles:
            self._switch_profile(last)
        elif self._profiles:
            self._switch_profile(next(iter(self._profiles)))

        # Show setup dialog on first launch to capture the CH install directory.
        # On macOS the path is fixed and well-known, so we skip the dialog and
        # auto-detect it silently instead.
        if not self._cfg.get("setup_done", False):
            if _IS_MAC:
                # Auto-detect /Applications/Clone Hero/Contents/Resources/Data
                mac_data = str(_MAC_CH_DATA_PATH)
                if os.path.isdir(mac_data):
                    self._data_v.set(mac_data)
                    if not self._is_default_profile():
                        self._active_prof["data_path"] = mac_data
                        _save_profiles(self._profiles)
                    self._cfg["default_data_path"] = mac_data
            else:
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
            # Auto-import any existing color profiles from the detected Colors folder
            if hasattr(self, "_ng_profiles"):
                self._ng_import_ini_files()
            # Auto-scan after setup so the user lands on a ready MenuChanger
            self.after(300, self._auto_scan_on_start)
        else:
            # Auto-scan on every normal launch too
            self.after(300, self._auto_scan_on_start)

        # On macOS, prompt once about Full Disk Access so file writes succeed
        if _IS_MAC:
            self.after(800, self._check_mac_permissions)

    def _check_mac_permissions(self):
        """Show a one-time prompt on macOS guiding the user to grant Full Disk Access."""
        if self._cfg.get("mac_permissions_prompted"):
            return
        self._cfg["mac_permissions_prompted"] = True
        _save_json(CONFIG_FILE, self._cfg)
        msg = (
            "CHSuite needs permission to modify Clone Hero game files.\n\n"
            "Please open:\n"
            "System Settings → Privacy & Security → Full Disk Access\n"
            "and add CHSuite to the list.\n\n"
            "Without this, background replacements and patches may not save correctly."
        )
        open_settings = messagebox.askokcancel(
            "Allow CHSuite to Make Changes",
            msg,
            parent=self
        )
        if open_settings:
            import subprocess
            subprocess.run([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
            ])

    def _auto_scan_on_start(self):
        """Silently trigger Load & Scan if deps are available and path is valid.
        Called after startup and after the setup dialog confirms."""
        if not _PIL_OK or not _UNITYPY_OK:
            return
        path = self._data_v.get().strip()
        if not os.path.isdir(path):
            return
        self._load_ggm()

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
        self._data_v.set(self._active_prof.get("data_path", "") or _get_default_data())
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
        # Auto-scan after creating a new profile so backgrounds are immediately available
        self.after(200, self._auto_scan_on_start)
        return name

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
        if _IS_MAC:
            # On macOS the user picks the Clone Hero.app bundle;
            # CHSuite automatically derives Contents/Resources/Data from it.
            p = filedialog.askdirectory(
                title="Select Clone Hero.app bundle",
                initialdir="/Applications")
            if p:
                data_candidate = Path(p) / "Contents" / "Resources" / "Data"
                self._data_v.set(str(data_candidate))
        elif _IS_LINUX:
            p = filedialog.askdirectory(title=f"Select {_CH_DATA_DIR} folder",
                                        initialdir=str(_app_dir() / "clonehero-linux"))
            if p: self._data_v.set(p)
        else:
            p = filedialog.askdirectory(title=f"Select {_CH_DATA_DIR} folder",
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
                f"\n\nPlease select your {_CH_DATA_DIR} folder."); return
        if not self._is_default_profile():
            self._active_prof["data_path"] = path
            _save_profiles(self._profiles)
        self._cfg["default_data_path"] = path
        _save_json(CONFIG_FILE, self._cfg)
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
                        f"\n\nMake sure you selected the {_CH_DATA_DIR} folder.")))
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
            messagebox.showwarning("No folder", f"Load a {_CH_DATA_DIR} folder first.f"); return
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
                                  f"Select and scan a {_CH_DATA_DIR} folder first.f")
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
            messagebox.showwarning("No folder", f"Select and scan a {_CH_DATA_DIR} folder first.f")
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
                created = self._profile_new()
                if not created:
                    return  # user cancelled the profile name dialog
                # Fall through — now on the new profile, open the file chooser
            else:
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
            messagebox.showwarning("No folder", f"Select and scan a {_CH_DATA_DIR} folder first.f")
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
                f"Apply these replacements directly to {_CH_DATA_DIR}:\n\n" +
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
