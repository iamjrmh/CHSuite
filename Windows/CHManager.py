"""
CHManager.py — Clone Hero install manager (CHManager / gamemanager)
===================================================================
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



# ─────────────────────────────────────────────────────────────────────────────
class CHManagerMixin:
    """
    CHSuite mixin: methods that build and operate the CHManager page, including launcher/game-launch helpers.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

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
            _ft = [("Executable", "*.exe"), ("All files", "*.*")] if _IS_WINDOWS \
                  else [("All files", "*.*")]
            exe = filedialog.askopenfilename(
                title="Select Clone Hero executable",
                filetypes=_ft,
                initialdir=default_dir or str(Path.home()))
            if not exe:
                return
            found_dir = str(Path(exe).parent)
            self._cfg["ch_default_install"] = found_dir
            self._cfg["ch_install_dir"]     = found_dir
            data_path = os.path.join(found_dir, _CH_DATA_DIR)
            if os.path.isdir(data_path):
                self._cfg["default_data_path"] = data_path
                if hasattr(self, "_data_v"):
                    self._data_v.set(data_path)
            _save_json(CONFIG_FILE, self._cfg)

        self._do_launch_exe(exe)

    @staticmethod
    def _find_ch_exe(directory: str):
        """Return path to the Clone Hero executable in directory, or None.
        Windows: looks for .exe files.
        Linux:   looks for .AppImage first, then plain executables.
        """
        if not directory or not os.path.isdir(directory):
            return None
        if _IS_WINDOWS:
            for candidate in _CH_EXE_CANDIDATES_WIN:
                p = Path(directory) / candidate
                if p.is_file():
                    return str(p)
            for p in Path(directory).glob("*.exe"):
                if "clone" in p.stem.lower() and "hero" in p.stem.lower():
                    return str(p)
        elif _IS_LINUX:
            # ── Linux only ────────────────────────────────────────────────────
            # Priority 1: exact file named "clonehero" (the standard Linux build)
            ch_exact = Path(directory) / "clonehero"
            if ch_exact.is_file():
                # Ensure the file is executable before returning it
                if not os.access(str(ch_exact), os.X_OK):
                    try:
                        ch_exact.chmod(ch_exact.stat().st_mode | 0o111)
                    except Exception:
                        pass
                return str(ch_exact)
            # Priority 2: AppImage
            for p in sorted(Path(directory).glob("*.AppImage")):
                if "clone" in p.name.lower() or "hero" in p.name.lower():
                    return str(p)
            # Priority 3: other known Linux candidates
            for candidate in _CH_EXE_CANDIDATES_LIN:
                p = Path(directory) / candidate
                if p.is_file():
                    if not os.access(str(p), os.X_OK):
                        try:
                            p.chmod(p.stat().st_mode | 0o111)
                        except Exception:
                            pass
                    return str(p)
            # Priority 4: any executable matching name pattern
            for p in Path(directory).iterdir():
                if p.is_file() and os.access(str(p), os.X_OK):
                    if "clone" in p.name.lower() or "hero" in p.name.lower():
                        return str(p)
        elif _IS_MAC:
            # Priority 1: standard app bundle executable at Contents/MacOS/Clone Hero
            mac_exe = Path(directory) / "Contents" / "MacOS" / "Clone Hero"
            if mac_exe.is_file() and os.access(str(mac_exe), os.X_OK):
                return str(mac_exe)
            # Priority 2: any executable inside Contents/MacOS/ matching the name
            mac_macos = Path(directory) / "Contents" / "MacOS"
            if mac_macos.is_dir():
                for p in sorted(mac_macos.iterdir()):
                    if p.is_file() and os.access(str(p), os.X_OK):
                        if "clone" in p.name.lower() or "hero" in p.name.lower():
                            return str(p)
                # Fallback: first executable in MacOS/, whatever it's named
                for p in sorted(mac_macos.iterdir()):
                    if p.is_file() and os.access(str(p), os.X_OK):
                        return str(p)
            # Priority 3: known candidate names at the top level
            for candidate in _CH_EXE_CANDIDATES_MAC:
                p = Path(directory) / candidate
                if p.is_file() and os.access(str(p), os.X_OK):
                    return str(p)
            # Last resort: any executable in the folder matching the name pattern
            for p in Path(directory).iterdir():
                if p.is_file() and os.access(str(p), os.X_OK):
                    if "clone" in p.name.lower() or "hero" in p.name.lower():
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
        """Save path as the default Clone Hero install and refresh the list.
        Also syncs default_data_path so CHMenuChanger and NoteGen export
        work correctly even if the user skipped the initial setup dialog."""
        self._cfg["ch_default_install"] = path
        self._cfg["ch_install_dir"]     = path
        data_path = os.path.join(path, _CH_DATA_DIR)
        if os.path.isdir(data_path):
            self._cfg["default_data_path"] = data_path
            # Sync active profile data path
            if not self._is_default_profile():
                self._active_prof["data_path"] = data_path
                _save_profiles(self._profiles)
            # Update the MenuChanger data path entry live
            if hasattr(self, "_data_v"):
                self._data_v.set(data_path)
        _save_json(CONFIG_FILE, self._cfg)
        self._gm_refresh_installs()
        self._gm_status(f"Default set: {os.path.basename(path)}")

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 6 — SONG MANAGER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_page_gamemanager(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["gamemanager"] = page

        inner = tk.Frame(page, bg=C["bg"], padx=24, pady=20)
        inner.pack(fill="both", expand=True)

        # ── Header row: title left, Pre-Scanner right ─────────────────────────
        hdr_row = tk.Frame(inner, bg=C["bg"])
        hdr_row.pack(fill="x", pady=(0, 14))

        # Left: title + subtitle
        title_left = tk.Frame(hdr_row, bg=C["bg"])
        title_left.pack(side="left", fill="y")
        tk.Label(title_left, text="CHManager",
                 font=("Lato", 18, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(title_left,
                 text="Manage Clone Hero installations, download new versions, and patch installs.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 0))

        # Right: Pre-Scanner inline panel
        ps_card = tk.Frame(hdr_row, bg=C["card"],
                           highlightbackground=C["border"], highlightthickness=1)
        ps_card.pack(side="right", fill="y", padx=(16, 0))

        ps_top = tk.Frame(ps_card, bg=C["card"], padx=12, pady=6)
        ps_top.pack(fill="x")

        tk.Label(ps_top, text="⚡ PRE-SCANNER", font=("Lato", 8, "bold"),
                 fg=C["accent"], bg=C["card"]).pack(side="left")
        tk.Label(ps_top, text="songcache.bin builder", font=("Lato", 7),
                 fg=C["text_dim"], bg=C["card"]).pack(side="left", padx=(6, 0))

        _sep(ps_card, bg=C["border"]).pack(fill="x")

        ps_body = tk.Frame(ps_card, bg=C["card"], padx=12, pady=8)
        ps_body.pack(fill="both", expand=True)

        # Folder row
        ps_folder_row = tk.Frame(ps_body, bg=C["card"])
        ps_folder_row.pack(fill="x")

        self._ps_folder_var = tk.StringVar(value="")
        ps_entry = tk.Entry(
            ps_folder_row, textvariable=self._ps_folder_var,
            font=("Lato", 8), bg=C["panel"], fg=C["accent3"],
            insertbackground=C["accent3"], relief="flat",
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"], width=34
        )
        ps_entry.pack(side="left", ipady=4, padx=(0, 6))

        RoundedButton(ps_folder_row, "📂 Browse", self._ps_browse,
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text"], height=26, radius=8,
                      text_font=("Lato", 8), canvas_bg=C["card"],
                      width=80).pack(side="left")

        self._ps_scan_btn = RoundedButton(
            ps_folder_row, "⚡ Scan", self._ps_start_scan,
            bg_color=C["accent"], hover_color="#8a5bff",
            text_color="#fff", height=26, radius=8,
            text_font=("Lato", 8, "bold"), canvas_bg=C["card"],
            width=72)
        self._ps_scan_btn.pack(side="left", padx=(6, 0))

        # Live status / count row
        ps_status_row = tk.Frame(ps_body, bg=C["card"])
        ps_status_row.pack(fill="x", pady=(5, 0))

        self._ps_count_var = tk.StringVar(value="Select a songs folder, then click ⚡ Scan.")
        self._ps_count_lbl = tk.Label(
            ps_status_row, textvariable=self._ps_count_var,
            font=("Lato", 8), fg=C["text_dim"], bg=C["card"], anchor="w"
        )
        self._ps_count_lbl.pack(side="left", fill="x", expand=True)

        # Compact progress bar (hidden until scan starts)
        self._ps_progress_var = tk.IntVar(value=0)
        self._ps_progress = ttk.Progressbar(
            ps_body, variable=self._ps_progress_var,
            maximum=100, orient="horizontal", length=300,
            mode="indeterminate"
        )
        self._ps_scanning = False

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
        tk.Label(lh, text="LOCAL INSTALLS", font=("Lato", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(side="left")
        RoundedButton(lh, "↺ Refresh", self._gm_refresh_installs,
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text"], height=34, radius=12,
                      text_font=FTS, canvas_bg=C["card"],
                      width=100).pack(side="right")
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
            self._gm_inst_canvas.yview_scroll(_scroll_units(event), "units")
        self._inst_wheel = _inst_wheel
        self._gm_inst_canvas.bind("<MouseWheel>", _inst_wheel)
        self._gm_inst_canvas.bind("<Button-4>",   _inst_wheel)
        self._gm_inst_canvas.bind("<Button-5>",   _inst_wheel)
        self._gm_inst_inner.bind("<MouseWheel>",  _inst_wheel)
        self._gm_inst_inner.bind("<Button-4>",    _inst_wheel)
        self._gm_inst_inner.bind("<Button-5>",    _inst_wheel)

        # Add install buttons
        add_row = tk.Frame(left_card, bg=C["card"], padx=12, pady=8); add_row.pack(fill="x")
        RoundedButton(add_row, "+ Add Existing Install", self._gm_add_install,
                      bg_color=C["accent_dim"], hover_color=C["accent"],
                      text_color=C["text"], height=42, radius=16,
                      text_font=FT, canvas_bg=C["card"],
                      width=210).pack(side="left")
        if _IS_MAC:
            RoundedButton(add_row, "🔍 Auto-Detect", self._gm_auto_detect_installs,
                          bg_color=C["border"], hover_color=C["hover"],
                          text_color=C["text"], height=42, radius=16,
                          text_font=FT, canvas_bg=C["card"],
                          width=160).pack(side="left", padx=(8, 0))

        # ── RIGHT: Download ───────────────────────────────────────────────────
        right_col = tk.Frame(split, bg=C["bg"])
        right_col.grid(row=0, column=1, sticky="nsew")

        dl_card = tk.Frame(right_col, bg=C["card"],
                           highlightbackground=C["border"], highlightthickness=1)
        dl_card.pack(fill="both", expand=True)

        dh = tk.Frame(dl_card, bg=C["card"], padx=14, pady=10); dh.pack(fill="x")
        tk.Label(dh, text="DOWNLOAD", font=("Lato", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(side="left")
        RoundedButton(dh, "↺ Check", self._gm_check_releases,
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text"], height=34, radius=12,
                      text_font=FTS, canvas_bg=C["card"],
                      width=92).pack(side="right")
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
                            padding=[10, 4], font=("Lato", 9, "bold"))
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
                _cv.yview_scroll(_scroll_units(event), "units")
            cv.bind("<MouseWheel>", _on_wheel)
            cv.bind("<Button-4>",   _on_wheel)
            cv.bind("<Button-5>",   _on_wheel)
            inner_f.bind("<MouseWheel>", _on_wheel)
            inner_f.bind("<Button-4>",   _on_wheel)
            inner_f.bind("<Button-5>",   _on_wheel)
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
        """Rebuild the local installs list.
        Linux/macOS: reads from cfg['linux_installs'] (ignores game_installs.json entirely).
        Windows:     reads from game_installs.json as before.
        """
        for w in self._gm_inst_inner.winfo_children():
            w.destroy()
        self._gm_inst_canvas.yview_moveto(0)

        if _IS_LINUX or _IS_MAC:
            installs = list(self._cfg.get("linux_installs", []))
            _empty_msg = ("No installs found.\n"
                          "Add an install manually below,\n"
                          "or download one from GitHub above.")
        else:
            installs = _read_installs()
            _empty_msg = ("No installs found in game_installs.json.\n"
                          "Run the Clone Hero Launcher at least once,\n"
                          "or add an install manually below.")

        if not installs:
            tk.Label(self._gm_inst_inner,
                     text=_empty_msg,
                     font=FT, fg=C["text_dim"], bg=C["card"],
                     justify="left").pack(padx=14, pady=14, anchor="w")
            return

        default_dir = os.path.normcase(os.path.normpath(
            self._cfg.get("ch_default_install", "") or
            self._cfg.get("ch_install_dir", "")))

        # Auto-remove entries whose folder/exe is missing
        valid_installs = []
        for inst in installs:
            p = inst.get("directoryPath", "")
            if p and self._find_ch_exe(p) is None:
                if _IS_LINUX:
                    # Remove from cfg["linux_installs"] silently
                    norm = os.path.normcase(os.path.normpath(p))
                    self._cfg["linux_installs"] = [
                        i for i in self._cfg.get("linux_installs", [])
                        if os.path.normcase(os.path.normpath(
                            i.get("directoryPath", ""))) != norm
                    ]
                    _save_json(CONFIG_FILE, self._cfg)
                else:
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
                    except Exception as e:
                        _log(f"[gm] Could not remove missing entry: {e}")
                _log(f"[gm] Auto-removed missing install: {p}")
            else:
                valid_installs.append(inst)
        installs = valid_installs

        if not installs:
            tk.Label(self._gm_inst_inner,
                     text=_empty_msg,
                     font=FT, fg=C["text_dim"], bg=C["card"],
                     justify="left").pack(padx=14, pady=14, anchor="w")
            return

        for inst in installs:
            path     = inst.get("directoryPath", "?")
            ver      = inst.get("version") or ""
            # If version is missing/empty, try reading {_CH_DATA_DIR}/version.json
            if not ver:
                try:
                    ver_json_path = Path(path) / _CH_DATA_DIR / "version.json"
                    if ver_json_path.is_file():
                        ver_data = json.loads(ver_json_path.read_text(encoding="utf-8"))
                        ver = (ver_data.get("version") or "?").lstrip("v")
                    else:
                        ver = "?"
                except Exception:
                    ver = "?"
            is_man   = inst.get("isFromLauncher") is False
            disabled = inst.get("disabled", False)
            exe_path = self._find_ch_exe(path)
            exe_ok   = exe_path is not None
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

            # Display name: stored "displayName" or fallback to basename
            display_name = inst.get("displayName") or os.path.basename(path)

            # Default star badge
            if is_def:
                tk.Label(name_row, text="★", font=("Lato", 12),
                         fg=C["warn"], bg=row_bg).pack(side="left", padx=(0, 5))

            # Clickable name label — click to rename
            name_lbl = tk.Label(name_row, text=display_name, font=FTB,
                                fg=name_fg, bg=row_bg, cursor="hand2")
            name_lbl.pack(side="left")
            tk.Label(name_row, text=" ✎", font=FTS,
                     fg=C["text_dim"], bg=row_bg, cursor="hand2").pack(side="left")

            def _rename(p=path, lbl=name_lbl, i=inst):
                current = i.get("displayName") or os.path.basename(p)
                new_name = simpledialog.askstring(
                    "Rename Install", "Enter a new display name:",
                    initialvalue=current, parent=self)
                if new_name and new_name.strip() and new_name.strip() != current:
                    new_name = new_name.strip()
                    i["displayName"] = new_name
                    lbl.config(text=new_name)
                    if _IS_LINUX:
                        # Persist into cfg["linux_installs"]
                        for entry in self._cfg.get("linux_installs", []):
                            if os.path.normcase(os.path.normpath(
                                    entry.get("directoryPath", ""))) == \
                               os.path.normcase(os.path.normpath(p)):
                                entry["displayName"] = new_name
                                break
                        _save_json(CONFIG_FILE, self._cfg)
                    else:
                        # Persist into game_installs.json
                        try:
                            data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
                            for entry in data.get("installs", []):
                                if os.path.normcase(os.path.normpath(
                                        entry.get("directoryPath", ""))) == \
                                   os.path.normcase(os.path.normpath(p)):
                                    entry["displayName"] = new_name
                                    break
                            _INSTALLS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        except Exception as e:
                            _log(f"[gm] Could not save display name: {e}")

            name_lbl.bind("<Button-1>", lambda e, fn=_rename: fn())
            name_row.winfo_children()[-1].bind("<Button-1>", lambda e, fn=_rename: fn())

            # Truncated path — show up to 55 chars, ellipsis in the middle if longer
            _max = 45
            _short_path = (path[:_max] + "…") if len(path) > _max else path
            tk.Label(info, text=_short_path, font=FTM, fg=C["text_dim"],
                     bg=row_bg, anchor="w", wraplength=320).pack(anchor="w")

            tag_r = tk.Frame(info, bg=row_bg); tag_r.pack(anchor="w", pady=(2, 0))
            tk.Label(tag_r, text=f"v{ver}", font=FTS, fg=C["text_dim"],
                     bg=row_bg).pack(side="left", padx=(0, 8))
            if is_man:
                tk.Label(tag_r, text="Manual", font=FTS, fg=C["success"],
                         bg="#0d2e1a", padx=4).pack(side="left", padx=(0, 4))
            else:
                tk.Label(tag_r, text="Launcher", font=FTS, fg=C["warn"],
                         bg=C["card2"], padx=4).pack(side="left", padx=(0, 4))
            if is_def:
                tk.Label(tag_r, text="default", font=FTS, fg=C["warn"],
                         bg="#2a1200", padx=4).pack(side="left", padx=(0, 4))
            if disabled:
                tk.Label(tag_r, text="disabled", font=FTS, fg=C["error"],
                         bg=C["card2"], padx=4).pack(side="left")

            # Right: buttons
            # ── Buttons: 2-column grid, uniform width ────────────────────────
            btn_col = tk.Frame(ri, bg=row_bg)
            btn_col.pack(side="right", padx=(8, 12))

            def _rb(parent, text, cmd, bg, fg, row, col, rowspan=1, colspan=1, pad_l=0, pad_t=0):
                b = RoundedButton(parent, text, cmd,
                                  bg_color=bg, hover_color=C["hover"],
                                  text_color=fg, height=32, radius=12,
                                  text_font=FTS, canvas_bg=row_bg, width=98)
                b.grid(row=row, column=col, columnspan=colspan,
                       sticky="ew",
                       padx=(pad_l, 0) if pad_l else (0, 3) if col == 0 and colspan == 1 else 0,
                       pady=(pad_t, 0))
                return b

            # Row 0: Set as Default (spans both cols, only if not default)
            if not is_def:
                _rb(btn_col, "★ Default",
                    lambda p=path: self._gm_set_default_install(p),
                    C["card2"], C["warn"], row=0, col=0, colspan=2, pad_t=0)

            # Row 1: Launch | Open folder
            if exe_ok:
                launch_bg = C["success"] if is_def else C["border"]
                launch_fg = "#000" if is_def else C["text"]
                _rb(btn_col, "▶ Launch",
                    lambda p=str(exe_path): self._do_launch_exe(p),
                    launch_bg, launch_fg, row=1, col=0, pad_t=3)
            else:
                tk.Label(btn_col, text="missing", font=FTS,
                         fg=C["error"], bg=row_bg, width=10
                         ).grid(row=1, column=0, padx=(0, 3))
            _rb(btn_col, "📂 Folder",
                lambda p=path: self._gm_open_folder(p),
                C["border"], C["text"], row=1, col=1, pad_l=0, pad_t=3)

            # Row 2: Patch | Unpatch  (grayed out if game_installs.json is absent)
            _installs_exist = _INSTALLS_FILE.is_file()
            patch_btn = _rb(btn_col, "⚙ Patch",
                lambda p=path: self._gm_patch_install(p),
                "#1a2a1a", C["success"], row=2, col=0, pad_t=3)
            unpatch_btn = _rb(btn_col, "↺ Unpatch",
                lambda p=path: self._gm_unpatch_install(p),
                C["card2"], C["warn"], row=2, col=1, pad_l=0, pad_t=3)
            if not _installs_exist:
                patch_btn.set_state(False)
                unpatch_btn.set_state(False)

            # Row 3: Delete (spans both cols)
            _rb(btn_col, "🗑 Delete",
                lambda p=path: self._gm_delete_install(p),
                C["card2"], C["error"], row=3, col=0, colspan=2, pad_t=3)

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
        # Remove from the install registry
        norm = os.path.normcase(os.path.normpath(path))
        if _IS_LINUX:
            # Linux: remove from cfg["linux_installs"]
            self._cfg["linux_installs"] = [
                i for i in self._cfg.get("linux_installs", [])
                if os.path.normcase(os.path.normpath(
                    i.get("directoryPath", ""))) != norm
            ]
            _save_json(CONFIG_FILE, self._cfg)
        elif _INSTALLS_FILE.is_file():
            try:
                data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
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
        """Browse to a Clone Hero install folder and register it.
        macOS:   uses osascript to open a native .app-aware folder picker.
        Linux:   saves to cfg['linux_installs'] (ignores game_installs.json).
        Windows: saves to game_installs.json as before.
        """
        if _IS_MAC:
            # osascript gives a native Finder dialog that can select .app bundles
            script = (
                'POSIX path of (choose folder '
                'with prompt "Select your Clone Hero.app bundle" '
                'default location "/Applications")'
            )
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True)
                folder = result.stdout.strip().rstrip("/") if result.returncode == 0 else None
            except Exception:
                folder = None
            # Fallback to tkinter dialog if osascript unavailable
            if not folder:
                folder = filedialog.askdirectory(
                    title="Select Clone Hero.app bundle",
                    initialdir="/Applications")
        else:
            folder = filedialog.askdirectory(
                title="Select Clone Hero install folder",
                initialdir=str(Path.home()))
        if not folder:
            return

        exe = self._find_ch_exe(folder)
        _exe_label = ("Clone Hero.exe" if _IS_WINDOWS
                      else "Clone Hero.app executable" if _IS_MAC
                      else "Clone Hero executable")
        if not exe:
            if not messagebox.askyesno(
                    "Exe not found",
                    f"{_exe_label} was not found in:\n{folder}\n\n"
                    "Add it anyway?", parent=self):
                return

        if _IS_LINUX or _IS_MAC:
            # ── Linux / macOS: store in chsuite_config.json, never touch game_installs.json
            norm = os.path.normcase(os.path.normpath(folder))
            existing = [os.path.normcase(os.path.normpath(i.get("directoryPath", "")))
                        for i in self._cfg.get("linux_installs", [])]
            if norm in existing:
                messagebox.showinfo("Already registered",
                                    "That folder is already in the installs list.", parent=self)
                return
            self._cfg.setdefault("linux_installs", []).append({
                "directoryPath": folder,
                "isFromLauncher": False,
                "version": None,
                "disabled": False,
            })
            _save_json(CONFIG_FILE, self._cfg)
            self._gm_status(f"Added: {os.path.basename(folder)}")
        else:
            if not _INSTALLS_FILE.is_file():
                # No launcher file yet — create a minimal one so we can register
                try:
                    _INSTALLS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    _INSTALLS_FILE.write_text(
                        json.dumps({"installs": []}, indent=2), encoding="utf-8")
                except Exception as e:
                    messagebox.showerror(
                        "Error",
                        f"Could not create game_installs.json:\n{e}", parent=self)
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

    def _gm_auto_detect_installs(self):
        """Scan /Applications for .app bundles that have 'Clone Hero' in the name,
        excluding any with 'Launcher' in the name, and register any that aren't
        already in the installs list.  macOS only.
        """
        if not _IS_MAC:
            return
        apps_dir = Path("/Applications")
        found = []
        try:
            for p in sorted(apps_dir.glob("*.app")):
                name = p.stem
                if "clone hero" in name.lower() and "launcher" not in name.lower():
                    found.append(p)
        except Exception as e:
            messagebox.showerror("Auto-Detect Error",
                                 f"Could not scan /Applications:\n{e}", parent=self)
            return

        if not found:
            messagebox.showinfo("None Found",
                "No Clone Hero .app bundles were found in /Applications.\n\n"
                "Use '+ Add Existing Install' to locate a copy manually.",
                parent=self)
            return

        existing = {os.path.normcase(os.path.normpath(i.get("directoryPath", "")))
                    for i in self._cfg.get("linux_installs", [])}
        added = []
        for p in found:
            norm = os.path.normcase(os.path.normpath(str(p)))
            if norm not in existing:
                self._cfg.setdefault("linux_installs", []).append({
                    "directoryPath": str(p),
                    "isFromLauncher": False,
                    "version": None,
                    "disabled": False,
                })
                existing.add(norm)
                added.append(p.name)

        _save_json(CONFIG_FILE, self._cfg)
        self._gm_refresh_installs()

        if added:
            self._gm_status(f"Auto-detected and added {len(added)} install(s).")
            messagebox.showinfo("Auto-Detect Complete",
                f"Added {len(added)} install(s):\n\n" +
                "\n".join(f"  • {n}" for n in added),
                parent=self)
        else:
            self._gm_status("Auto-detect: all found installs already registered.")
            messagebox.showinfo("Already Registered",
                "Found " + str(len(found)) + " Clone Hero app(s), "
                "but all are already registered:\n\n" +
                "\n".join(f"  • {p.name}" for p in found),
                parent=self)

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

        def _linux_asset(release):
            """Return the Linux asset matching the host architecture.
            Priority: Standalone .tar.xz → Standalone .tar → .tar.xz → .tar → .7z → .AppImage.
            Launcher assets (any file with 'launcher' in the name) are always skipped.
            """
            LINUX_EXTS = (".appimage", ".tar.xz", ".tar", ".7z")
            arch_tag = "x86_64" if _is_64 else "x86"
            candidates, fallback = [], []
            for a in release.get("assets", []):
                n = a["name"].lower()
                if not any(n.endswith(ext) for ext in LINUX_EXTS):
                    continue
                if "launcher" in n:
                    continue          # skip ch_launcher and any other launcher assets
                if "win" in n or "windows" in n or "mac" in n or "osx" in n:
                    continue          # definitely not Linux
                # Arch filtering: use a word-boundary-aware check so "x86" doesn't
                # accidentally match the "x86" inside "x86_64".
                if _is_64 and re.search(r'x86(?!_64)', n):
                    continue          # 32-bit-only asset, skip on 64-bit host
                if not _is_64 and "x86_64" in n:
                    continue          # 64-bit-only asset, skip on 32-bit host
                if arch_tag in n or "linux" in n or "standalone" in n:
                    candidates.append(a)
                else:
                    fallback.append(a)
            pool = candidates if candidates else fallback
            # Rank: Standalone tarballs first (actual game), generic tarballs next,
            # then .7z, AppImage last (often the launcher on PTB).
            def _ext_rank_linux(a):
                n = a["name"].lower()
                if "standalone" in n and n.endswith(".tar.xz"):
                    return 0
                if "standalone" in n and n.endswith(".tar"):
                    return 1
                if n.endswith(".tar.xz"):
                    return 2
                if n.endswith(".tar"):
                    return 3
                if n.endswith(".7z"):
                    return 4
                if n.endswith(".appimage"):
                    return 5
                return 99
            pool.sort(key=_ext_rank_linux)
            return pool[0] if pool else None

        def _mac_asset(release):
            """Return the macOS Clone Hero asset: prefer .pkg, then .dmg."""
            MAC_EXTS = (".pkg", ".dmg")
            candidates = []
            for a in release.get("assets", []):
                n = a["name"].lower()
                if not any(n.endswith(ext) for ext in MAC_EXTS):
                    continue
                if "launcher" in n:
                    continue   # skip ch_launcher assets
                candidates.append(a)
            if not candidates:
                return None
            def _ext_rank_mac(a):
                n = a["name"].lower()
                if n.endswith(".pkg"): return 0
                if n.endswith(".dmg"): return 1
                return 99
            candidates.sort(key=_ext_rank_mac)
            return candidates[0]

        def _pick_asset(release):
            """Return the best release asset for the current OS."""
            if _IS_WINDOWS:
                return _win_asset(release)
            elif _IS_LINUX:
                return _linux_asset(release)
            elif _IS_MAC:
                return _mac_asset(release)
            else:
                return _linux_asset(release) or _win_asset(release)

        def _populate_frame(frame, releases):
            if not releases:
                tk.Label(frame, text="No releases found.", font=FT,
                         fg=C["text_dim"], bg=C["card"]).pack(padx=8, pady=8, anchor="w")
                return

            # Grab the canvas ancestor so we can re-bind wheel on new widgets
            cv = frame.master

            def _on_wheel(event, _cv=cv):
                _cv.yview_scroll(_scroll_units(event), "units")

            for rel in releases:
                asset = _pick_asset(rel)
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
                    w.bind("<Button-4>",   _on_wheel)
                    w.bind("<Button-5>",   _on_wheel)

                lbl_name = tk.Label(row, text=rname, font=FTB, fg=C["text"], bg=C["card"])
                lbl_name.pack(anchor="w")
                lbl_name.bind("<MouseWheel>", _on_wheel)
                lbl_name.bind("<Button-4>",   _on_wheel)
                lbl_name.bind("<Button-5>",   _on_wheel)

                lbl_info = tk.Label(row,
                    text=f"{pub}  ·  {size_mb:.1f} MB  ·  {asset['name']}",
                    font=FTS, fg=C["text_dim"], bg=C["card"])
                lbl_info.pack(anchor="w")
                lbl_info.bind("<MouseWheel>", _on_wheel)
                lbl_info.bind("<Button-4>",   _on_wheel)
                lbl_info.bind("<Button-5>",   _on_wheel)

                RoundedButton(row, "⬇ Download & Install",
                              lambda a=asset, r=rtag: self._gm_start_download(a, r),
                              bg_color=C["accent"], hover_color=C["accent_dim"],
                              text_color="white", height=42, radius=16,
                              text_font=("Lato", 9, "bold"), canvas_bg=C["card"],
                              width=210).pack(anchor="w", pady=(4, 0))

        _populate_frame(self._gm_rel_frame, full_rels)
        _populate_frame(self._gm_ptb_frame, ptb_rels)

    def _gm_start_download(self, asset: dict, tag: str):
        """Download a release zip and extract it to the chosen destination."""
        if not _REQUESTS_OK:
            return

        # Determine install destination — no dialog on either platform
        dest_dir = Path.home() / "Documents" / "Clone Hero" / tag
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
            # dest_dir is assigned in the .dmg branch below, which makes Python
            # treat it as a local variable throughout _worker even on other
            # platforms/file types, causing an UnboundLocalError.  nonlocal
            # tells Python to use the binding from _gm_start_download instead.
            nonlocal dest_dir
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
                    # Windows: flatten single subfolder (e.g. "Windows") after 7z extract
                    if _IS_WINDOWS:
                        _flatten_platform_subdir(dest_dir, "windows")
                elif fname_lower.endswith(".appimage"):
                    _log(f"[gm] Installing .AppImage {zip_path} → {dest_dir}")
                    # AppImages are self-contained — just ensure +x; no extraction
                    import stat
                    current = zip_path.stat().st_mode
                    zip_path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    # Leave the AppImage in dest_dir — do NOT delete it
                elif fname_lower.endswith(".pkg") and _IS_MAC:
                    _log(f"[gm] Running .pkg installer: {zip_path}")
                    self.after(0, lambda: self._gm_progress_lbl.config(
                        text="Running installer… (you may be prompted for your password)"))
                    result = subprocess.run(
                        ["sudo", "installer", "-pkg", str(zip_path), "-target", "/"],
                        timeout=300)
                    zip_path.unlink(missing_ok=True)
                    if result.returncode != 0:
                        raise RuntimeError(
                            f"pkg installer exited with code {result.returncode}.")
                elif fname_lower.endswith(".dmg") and _IS_MAC:
                    _log(f"[gm] Mounting .dmg and copying app: {zip_path}")
                    self.after(0, lambda: self._gm_progress_lbl.config(
                        text="Mounting disk image…"))
                    import plistlib
                    mount_result = subprocess.run(
                        ["hdiutil", "attach", str(zip_path), "-nobrowse",
                         "-readonly", "-plist"],
                        capture_output=True, text=True, timeout=60)
                    if mount_result.returncode != 0:
                        raise RuntimeError(
                            f"hdiutil attach failed:\n{mount_result.stderr}")
                    plist_data = plistlib.loads(mount_result.stdout.encode())
                    mount_point = None
                    for entity in plist_data.get("system-entities", []):
                        if "mount-point" in entity:
                            mount_point = entity["mount-point"]
                            break
                    if not mount_point:
                        raise RuntimeError("Could not determine DMG mount point.")
                    try:
                        self.after(0, lambda: self._gm_progress_lbl.config(
                            text="Copying app bundle…"))
                        apps = list(Path(mount_point).glob("*.app"))
                        if not apps:
                            raise RuntimeError("No .app bundle found inside the DMG.")
                        src_app = apps[0]
                        dst_app = dest_dir / src_app.name
                        if dst_app.exists():
                            shutil.rmtree(str(dst_app))
                        shutil.copytree(str(src_app), str(dst_app))
                        dest_dir = dst_app  # register the .app as the install dir
                    finally:
                        subprocess.run(
                            ["hdiutil", "detach", mount_point, "-quiet"],
                            capture_output=True, timeout=30)
                    zip_path.unlink(missing_ok=True)
                elif fname_lower.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tar")):
                    _log(f"[gm] Extracting {fname_lower} {zip_path} → {dest_dir}")
                    import tarfile
                    with tarfile.open(zip_path, "r:*") as tf:
                        tf.extractall(dest_dir)
                    zip_path.unlink(missing_ok=True)
                    # Linux: flatten single subfolder (e.g. "Linux") into dest_dir root
                    if _IS_LINUX:
                        _flatten_platform_subdir(dest_dir, "linux")
                else:
                    _log(f"[gm] Extracting .zip {zip_path} → {dest_dir}")
                    import zipfile
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(dest_dir)
                    zip_path.unlink(missing_ok=True)
                    # Windows: flatten single subfolder (e.g. "Windows") into dest_dir root
                    if _IS_WINDOWS:
                        _flatten_platform_subdir(dest_dir, "windows")

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
            if item.is_dir() and self._find_ch_exe(str(item)) is not None:
                actual = str(item)
                break
        # AppImage case: the asset IS the executable — chmod +x and keep in folder
        if actual == install_dir and self._find_ch_exe(install_dir) is None:
            for f in Path(install_dir).iterdir():
                if f.suffix.lower() == ".appimage":
                    f.chmod(f.stat().st_mode | 0o111)   # ensure +x
                    break

        # Register the new install
        norm_actual = os.path.normcase(os.path.normpath(actual))
        if _IS_LINUX or _IS_MAC:
            # Linux / macOS: save to cfg["linux_installs"] — never touch game_installs.json
            existing = {os.path.normcase(os.path.normpath(i.get("directoryPath", "")))
                        for i in self._cfg.get("linux_installs", [])}
            if norm_actual not in existing:
                self._cfg.setdefault("linux_installs", []).append({
                    "directoryPath": actual,
                    "isFromLauncher": False,
                    "version": tag.lstrip("v"),
                    "disabled": False,
                })
                _save_json(CONFIG_FILE, self._cfg)
                _log(f"[gm] Registered {actual} in linux_installs (cfg)")
        elif _INSTALLS_FILE.is_file():
            try:
                shutil.copy2(str(_INSTALLS_FILE), str(_INSTALLS_FILE) + ".bak")
                data = json.loads(_INSTALLS_FILE.read_text(encoding="utf-8"))
                existing = {os.path.normcase(os.path.normpath(i.get("directoryPath", "")))
                            for i in data.get("installs", [])}
                if norm_actual not in existing:
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
        self._cfg["ch_install_dir"]     = actual
        self._cfg["ch_default_install"] = actual
        data_path = os.path.join(actual, _CH_DATA_DIR)
        if os.path.isdir(data_path):
            self._cfg["default_data_path"] = data_path
            if hasattr(self, "_data_v"):
                self._data_v.set(data_path)
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

    # ── Pre-Scanner (embedded in CHManager title bar) ─────────────────────────

