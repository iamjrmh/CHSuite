"""
CHPatcher.py — launcher patcher (CHPatcher)
===========================================
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
class CHPatcherMixin:
    """
    CHSuite mixin: methods that build and operate the CHPatcher page.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

    def _build_page_patcher(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["patcher"] = page
        inner = tk.Frame(page, bg=C["bg"], padx=24, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="CHPatcher",
                 font=("Lato", 18, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner,
                 text="Mark installs as Manual so the launcher stops overwriting your game files.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 18))

        # ── Status card ───────────────────────────────────────────────────────
        stat_card = _card(inner, padx=18, pady=14)
        stat_card.pack(fill="x", pady=(0, 14))
        tk.Label(stat_card, text="LAUNCHER STATUS", font=("Lato", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w", pady=(0, 8))
        self._pt_status_lbl = tk.Label(
            stat_card, text="", font=("Lato", 11, "bold"),
            fg=C["text_dim"], bg=C["card"])
        self._pt_status_lbl.pack(anchor="w")
        self._pt_status_sub = tk.Label(
            stat_card, text="", font=FT, fg=C["text_dim"], bg=C["card"],
            wraplength=700, justify="left")
        self._pt_status_sub.pack(anchor="w", pady=(4, 0))

        RoundedButton(stat_card, "↺  Refresh", self._pt_refresh,
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text"], height=38, radius=14,
                      text_font=FT_LABEL, canvas_bg=C["card"],
                      width=118).pack(anchor="e", pady=(10, 0))

        # ── Installs list ─────────────────────────────────────────────────────
        list_card = _card(inner, padx=0, pady=0)
        list_card.pack(fill="both", expand=True, pady=(0, 14))
        lh = tk.Frame(list_card, bg=C["card"], padx=16, pady=10); lh.pack(fill="x")
        tk.Label(lh, text="INSTALLS IN game_installs.json",
                 font=("Lato", 8, "bold"), fg=C["text_dim"], bg=C["card"]).pack(side="left")
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
            self._pt_patch_selected, C["accent"], C["accent_dim"], height=54)
        self._pt_patch_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._pt_unpatch_btn = RoundedButton(
            btn_row, "↩  Unpatch Selected (Restore Launcher)",
            self._pt_unpatch_selected, C["border"], C["hover"], height=54)
        self._pt_unpatch_btn.pack(side="left", fill="x", expand=True)

        btn_row2 = tk.Frame(inner, bg=C["bg"]); btn_row2.pack(fill="x", pady=(0, 8))
        self._pt_remove_btn = RoundedButton(
            btn_row2, "✕  Remove Selected Entry from JSON",
            self._pt_remove_selected, "#3d1a1a", "#5a2020", height=46)
        self._pt_remove_btn.pack(fill="x")

        # Warning note
        warn_card = tk.Frame(inner, bg=C["card2"],
                             highlightbackground=C["warn"], highlightthickness=1,
                             padx=14, pady=10)
        warn_card.pack(fill="x")
        tk.Label(warn_card,
                 text="⚠  Close the Clone Hero Launcher before patching. "
                      "CHSuite will attempt to close it automatically if detected.",
                 font=FT_LABEL, fg=C["warn"], bg=C["card2"],
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
                         fg=C["error"], bg=C["card2"], padx=4).pack(side="left", padx=(0, 6))

            # Patch badge
            if is_man:
                badge_text, badge_fg, badge_bg = "✓ Manual", C["success"], "#0d2e1a"
            else:
                badge_text, badge_fg, badge_bg = "⚙ Launcher", C["warn"], "#2a1f0a"
            badge_lbl = tk.Label(inner_row, text=badge_text, font=("Lato", 9, "bold"),
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
