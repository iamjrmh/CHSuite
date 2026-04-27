"""
CHCleaner.py — bad-songs.txt cleaner (CHCleaner)
================================================
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

# ── Module-level helpers ─────────────────────────────────────────────────────
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





# ─────────────────────────────────────────────────────────────────────────────
class CHCleanerMixin:
    """
    CHSuite mixin: methods that build and operate the CHCleaner page.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

    def _build_page_cleaner(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["cleaner"] = page
        inner = tk.Frame(page, bg=C["bg"], padx=24, pady=20)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="CHCleaner",
                 font=("Lato", 18, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(inner, text="Load your badsongs.txt, review ERROR folders, and delete them.",
                 font=FT, fg=C["text_dim"], bg=C["bg"]).pack(anchor="w", pady=(2, 16))

        # File picker card
        file_card = tk.Frame(inner, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=16, pady=14)
        file_card.pack(fill="x", pady=(0, 14))
        tk.Label(file_card, text="SELECTED FILE", font=("Lato", 8, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w")
        self._cl_file_lbl = tk.Label(file_card, text="No file selected",
                                     fg=C["text_dim"], bg=C["card"], font=FT_LABEL,
                                     wraplength=800, justify="left", anchor="w")
        self._cl_file_lbl.pack(fill="x", pady=(4, 10))
        RoundedButton(file_card, "📂  Select badsongs.txt", self._cl_select_file,
                      C["accent"], C["accent_dim"], height=50).pack(fill="x")

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
            RoundedButton(btn_grp, txt, cmd,
                          bg_color=C["border"], hover_color=C["hover"],
                          text_color=C["text"], height=36, radius=14,
                          text_font=FT_LABEL, canvas_bg=C["card"],
                          width=108).pack(side="left", padx=2)

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
                                          self._cl_delete, C["error"], "#dc2626", height=54)
        self._cl_del_btn.pack(fill="x", pady=(0, 8))
        self._cl_del_btn.set_state(False)

        # Status
        stat_card = tk.Frame(inner, bg=C["card"],
                             highlightbackground=C["border"], highlightthickness=1,
                             padx=14, pady=10)
        stat_card.pack(fill="x")
        tk.Label(stat_card, text="STATUS", font=("Lato", 8, "bold"),
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
                           font=("Lato", 9), anchor="w", relief="flat").pack(fill="x", padx=4)
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
