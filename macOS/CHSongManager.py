"""
CHSongManager.py — Chorus Encore song downloader (CHSongManager) and embedded CHPreScanner
==========================================================================================
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

# ── CHSongManagerTab (class) ────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
"""
CHSongManagerTab — Bridge-faithful rebuild
==========================================
Drop this entire block into CHSuite.py, replacing the existing
CHSongManagerTab class and its helper constants/functions.

Layout mirrors Bridge exactly:
  • Tab bar at top: Browse | Settings  (no Tools tab)
  • Browse  → search-bar + result-table + sidebar (album-art, charter info,
              feature checkmarks, NPS stats, Download button)
  • Settings → chart library dir, folder-name format, download format,
               video-BG toggle, table layout  (no Discord / Patreon / GitHub)
"""

# ── stdlib ─────────────────────────────────────────────────────────────────────
import io
import os
import re
import threading
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ── optional deps ─────────────────────────────────────────────────────────────
try:
    import requests as _sm_requests
    _SM_HAS_REQUESTS = True
except ImportError:
    _sm_requests = None
    _SM_HAS_REQUESTS = False

try:
    from PIL import Image, ImageTk
    _SM_HAS_PIL = True
except ImportError:
    _SM_HAS_PIL = False

# ── API endpoints ─────────────────────────────────────────────────────────────
_SM_API_URL   = "https://api.enchor.us/search"
_SM_FILES_URL = "https://files.enchor.us"
_SM_ART_URL   = "https://files.enchor.us/{md5}.jpg"
_SM_PER_PAGE  = 25

# ── filter constants ──────────────────────────────────────────────────────────
_SM_INSTRUMENTS = [None, 'guitar', 'guitarcoop', 'rhythm', 'bass',
                   'drums', 'keys', 'guitarghl', 'guitarcoopghl',
                   'rhythmghl', 'bassghl']
_SM_INST_LABELS = ["Any Instrument", "Lead Guitar", "Co-op Guitar",
                   "Rhythm Guitar", "Bass Guitar", "Drums", "Keys",
                   "GHL Lead", "GHL Co-op", "GHL Rhythm", "GHL Bass"]
_SM_DIFFICULTIES = [None, 'expert', 'hard', 'medium', 'easy']
_SM_DIFF_LABELS  = ["Any Difficulty", "Expert", "Hard", "Medium", "Easy"]
_SM_DRUM_TYPES   = [None, 'fourLane', 'fourLanePro', 'fiveLane']
_SM_DRUM_LABELS  = ["Any Drum Type", "Four Lane", "Four Lane Pro", "Five Lane"]
_SM_SORT_PROPS   = [None, 'name', 'artist', 'album', 'genre',
                    'year', 'charter', 'length', 'modifiedTime']
_SM_SORT_LABELS  = ["Default Sort", "Name", "Artist", "Album", "Genre",
                    "Year", "Charter", "Length", "Modified"]

_SM_DIFF_KEYS = [
    ('diff_guitar',          'G'), ('diff_guitar_coop',     'GC'),
    ('diff_rhythm',          'R'), ('diff_bass',             'B'),
    ('diff_drums',           'D'), ('diff_keys',             'K'),
    ('diff_guitarghl',       'GL'),('diff_guitar_coop_ghl', 'GCL'),
    ('diff_rhythm_ghl',      'RL'),('diff_bassghl',         'BL'),
    ('diff_vocals',          'V'),
]

# ── colour palette (resolved at runtime from CHSuite's C dict) ────────────────
_BC_FALLBACK = dict(
    bg="#0c0e13", panel="#13161f", card="#181c28", card2="#1c2030",
    border="#252b3d", border2="#2e3650", accent="#6c3bff",
    accent_dim="#3d2299", accent2="#ff3b8a", accent3="#00d4aa",
    text="#e9ecf8", text_dim="#636b82", text_mid="#9aa3bf",
    success="#22c55e", warn="#f59e0b", error="#ef4444",
    selected="#341a7a", hover="#1e2235", neutral="#2a2e3d",
)

def _bc(key: str) -> str:
    try:
        from __main__ import C
        return C.get(key, _BC_FALLBACK.get(key, "#ffffff"))
    except Exception:
        return _BC_FALLBACK.get(key, "#ffffff")

_FT  = ("Lato", 10)
_FTB = ("Lato", 10, "bold")
_FTS = ("Lato", 8)
_FTH = ("Lato", 11, "bold")
_FTM = ("Lato", 9)

# ── table columns: (header, field_key, px_width, anchor) ─────────────────────
# (label, api_field, min_px_width, anchor, grid_col)
_COLS = [
    ("Name",   "name",   300, "w",      1),
    ("Artist", "artist", 180, "w",      2),
    ("Album",  "album",  180, "w",      3),
    ("Genre",  "genre",  130, "w",      4),
    ("Year",   "year",    60, "center", 5),
]
# Grid column 0 = checkbox, 1-5 = data cols, 6 = dl button
_CHK_COL    = 0
_DL_COL     = 6
_CHK_MINW   = 36    # px min-width for checkbox column
_DL_MINW    = 40    # px min-width for download button column
_COL_SORT = {
    "name":   "name",  "artist": "artist",
    "album":  "album", "genre":  "genre",
    "year":   "year",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def _sm_fmt_ms(ms) -> str:
    if ms is None: return "—"
    try:
        s = int(ms) // 1000
        return f"{s // 60}:{s % 60:02d}"
    except Exception: return "—"

def _sm_safe_name(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip()[:120]

def _sm_diff_label(chart: dict) -> str:
    return " ".join(ab for k, ab in _SM_DIFF_KEYS
                    if chart.get(k) is not None and chart[k] >= 0) or "—"

# ── difficulty badge colour map ───────────────────────────────────────────────
_DIFF_COLORS = {
    "Expert": "#ef4444", "Hard": "#f59e0b",
    "Medium": "#22c55e", "Easy": "#6c3bff",
}


# =============================================================================
class CHSongManagerTab(tk.Frame):
    """
    Bridge-faithful Clone Hero song browser / downloader.
    Tab bar:  Browse | Settings   (Tools tab removed)
    """

    def __init__(self, parent, cfg: dict = None, save_cfg_fn=None, **kw):
        super().__init__(parent, bg=_bc("bg"), **kw)
        self._cfg      = cfg if cfg is not None else {}
        self._save_cfg = save_cfg_fn or (lambda: None)

        # Search state
        self._songs:   list = []
        self._page:    int  = 1
        self._query:   str  = ""
        self._found:   int  = 0

        # Filter state
        self._filt_instrument: str | None = 'guitar'
        self._filt_difficulty: str | None = 'expert'
        self._filt_drum_type:  str | None = None
        self._filt_sort_prop:  str | None = "modifiedTime"
        self._filt_sort_dir:   str        = "desc"
        self._filt_drums_rev:  bool       = False

        # Row / selection / download
        self._selected:     set  = set()
        self._dl_threads:   dict = {}
        self._dl_bars:      dict = {}
        self._dl_labels:    dict = {}
        self._row_frames:   list = []
        self._row_chk_vars: list = []
        self._row_bg:       list = []

        # Virtual scroll
        self._virt_rendered: dict = {}   # idx → frame (currently live widgets)

        # Sidebar
        self._active_idx:    int | None  = None
        self._art_image_ref: object      = None   # keep PhotoImage alive

        # Sort
        self._sort_col: str | None = None
        self._sort_dir: str        = "desc"

        # Debounce tokens
        self._filter_after_id = None
        self._query_after_id  = None

        self._ui_ready = False
        self._build_ui()
        self._ui_ready = True
        self.after(150, self._initial_load)

    # =========================================================================
    #  TOP-LEVEL LAYOUT
    # =========================================================================

    # ── Canvas checkbox factory ───────────────────────────────────────────────

    _CHK_SZ = 15   # canvas pixel size

    def _make_chk_canvas(self, parent, var, on_toggle, bg_colour,
                          row_chk_fns=None):
        """
        Create a small canvas that draws a rounded-square checkbox.
        on_toggle() is called after the value flips.
        If row_chk_fns is provided, a bg-aware redraw lambda is appended to it
        so the canvas tracks row hover/select colour changes.
        """
        sz = self._CHK_SZ
        cv = tk.Canvas(parent, width=sz, height=sz,
                       bg=bg_colour, highlightthickness=0, bd=0, cursor="hand2")

        def _draw(bg=bg_colour):
            cv.config(bg=bg)
            cv.delete("all")
            r = 3  # corner radius
            checked = var.get()
            fill = _bc("accent") if checked else bg
            # Rounded rectangle via polygon
            x0, y0, x1, y1 = 1, 1, sz-1, sz-1
            cv.create_polygon(
                x0+r, y0,  x1-r, y0,  x1, y0,  x1, y0+r,
                x1, y1-r,  x1, y1,  x1-r, y1,  x0+r, y1,
                x0, y1,    x0, y1-r, x0, y0+r,  x0, y0,
                fill=fill, outline=_bc("border2"), smooth=True)
            if checked:
                # White tick: from (3,8) to (6,11) to (12,5)
                cv.create_line(3, 8, 6, 11, 12, 4,
                               fill="white", width=2,
                               capstyle="round", joinstyle="round")

        _draw(bg_colour)

        def _click(_e):
            var.set(not var.get())
            _draw(cv.cget("bg"))
            on_toggle()

        cv.bind("<Button-1>", _click)

        if row_chk_fns is not None:
            row_chk_fns.append(_draw)

        return cv

    def _redraw_hdr_chk(self):
        """Redraw the header select-all canvas checkbox."""
        cv = getattr(self, "_hdr_chk_cv", None)
        if cv:
            try:
                sz = self._CHK_SZ
                cv.delete("all")
                r = 3
                checked = self._chk_all_var.get()
                bg = _bc("panel")
                fill = _bc("accent") if checked else bg
                x0, y0, x1, y1 = 1, 1, sz-1, sz-1
                cv.create_polygon(
                    x0+r, y0,  x1-r, y0,  x1, y0,  x1, y0+r,
                    x1, y1-r,  x1, y1,  x1-r, y1,  x0+r, y1,
                    x0, y1,    x0, y1-r, x0, y0+r,  x0, y0,
                    fill=fill, outline=_bc("border2"), smooth=True)
                if checked:
                    cv.create_line(3, 8, 6, 11, 12, 4,
                                   fill="white", width=2,
                                   capstyle="round", joinstyle="round")
            except Exception:
                pass

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_tabbar()    # row 0 — Browse / Settings tabs
        self._browse_frame = tk.Frame(self, bg=_bc("bg"))
        self._browse_frame.grid(row=1, column=0, sticky="nsew")
        self._browse_frame.columnconfigure(0, weight=1)
        self._browse_frame.rowconfigure(1, weight=1)

        self._settings_frame = tk.Frame(self, bg=_bc("bg"))
        # not gridded yet — shown on demand

        self._build_browse_content()
        self._build_settings_content()

    # ─── tab bar ─────────────────────────────────────────────────────────────

    def _build_tabbar(self):
        bar = tk.Frame(self, bg=_bc("panel"))
        bar.grid(row=0, column=0, sticky="ew")

        inner = tk.Frame(bar, bg=_bc("panel"))
        inner.pack(fill="x")

        self._active_tab = tk.StringVar(value="browse")
        self._tab_btns   = {}

        for name, label in [("browse", "Browse"), ("settings", "Settings")]:
            btn = tk.Label(
                inner, text=label,
                font=_FT, relief="flat", bd=0,
                padx=20, pady=10, cursor="hand2")
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, n=name: self._switch_tab(n))
            self._tab_btns[name] = btn

        self._refresh_tab_btns()

    def _switch_tab(self, name: str):
        self._active_tab.set(name)
        if name == "browse":
            self._settings_frame.grid_remove()
            self._browse_frame.grid(row=1, column=0, sticky="nsew")
        else:
            self._browse_frame.grid_remove()
            self._settings_frame.grid(row=1, column=0, sticky="nsew")
        self._refresh_tab_btns()

    def _refresh_tab_btns(self):
        active = self._active_tab.get()
        for name, btn in self._tab_btns.items():
            if name == active:
                btn.config(bg=_bc("bg"), fg=_bc("text"))
            else:
                btn.config(bg=_bc("panel"), fg=_bc("text_dim"))
                def _make_hover(b, on_bg, off_bg):
                    b.bind("<Enter>", lambda e: b.config(bg=on_bg))
                    b.bind("<Leave>", lambda e: b.config(bg=off_bg))
                _make_hover(btn, _bc("hover"), _bc("panel"))

    # =========================================================================
    #  BROWSE TAB CONTENT
    # =========================================================================

    def _build_browse_content(self):
        self._build_search_bar(self._browse_frame)   # row 0
        self._build_body(self._browse_frame)          # row 1
        self._build_statusbar(self._browse_frame)     # row 2

    # ─── search bar (matches Bridge's search-bar component) ──────────────────

    def _build_search_bar(self, parent):
        bar = tk.Frame(parent, bg=_bc("panel"))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        inner = tk.Frame(bar, bg=_bc("panel"), padx=10, pady=6)
        inner.pack(fill="x")

        # ── Search input ─────────────────────────────────────────────────────
        q_border = tk.Frame(inner, bg=_bc("border"), padx=1, pady=1)
        q_border.pack(side="left", padx=(0, 6))
        q_inner = tk.Frame(q_border, bg=_bc("card"))
        q_inner.pack()

        self._q_var = tk.StringVar()
        q_ent = tk.Entry(
            q_inner, textvariable=self._q_var,
            font=_FT, bg=_bc("card"), fg=_bc("text"),
            insertbackground=_bc("text"),
            relief="flat", bd=6, width=24 if _IS_MAC else 32)
        q_ent.pack(side="left")
        q_ent.bind("<Return>", lambda _: self._do_search())
        self._q_var.trace_add("write", self._on_query_changed)

        self._search_loading_lbl = tk.Label(
            q_inner, text="", font=_FTS,
            fg=_bc("text_dim"), bg=_bc("card"), padx=4)
        self._search_loading_lbl.pack(side="left")

        # ── Instrument dropdown ───────────────────────────────────────────────
        _def_inst = self._cfg.get("sm_filt_instrument", "Lead Guitar")
        if _def_inst not in _SM_INST_LABELS: _def_inst = "Lead Guitar"
        self._inst_var = tk.StringVar(value=_def_inst)
        self._inst_btn = StyledDropdown(
            inner, textvariable=self._inst_var, values=_SM_INST_LABELS,
            font=_FTS, canvas_bg=_bc("panel"), height=28, width=12)
        self._inst_btn.pack(side="left", padx=(0, 2))
        self._inst_btn.bind("<<ComboboxSelected>>",
                            lambda _: self._on_filter_changed())

        # ── Difficulty dropdown ───────────────────────────────────────────────
        _def_diff = self._cfg.get("sm_filt_difficulty", "Any Difficulty")
        if _def_diff not in _SM_DIFF_LABELS: _def_diff = "Any Difficulty"
        self._diff_var = tk.StringVar(value=_def_diff)
        self._diff_btn = StyledDropdown(
            inner, textvariable=self._diff_var, values=_SM_DIFF_LABELS,
            font=_FTS, canvas_bg=_bc("panel"), height=28, width=13)
        self._diff_btn.pack(side="left", padx=(0, 6))
        self._diff_btn.bind("<<ComboboxSelected>>",
                            lambda _: self._on_filter_changed())

        # ── Sort property dropdown ────────────────────────────────────────────
        _def_sort = self._cfg.get("sm_filt_sort", "Modified")
        if _def_sort not in _SM_SORT_LABELS: _def_sort = "Modified"
        self._sort_prop_var = tk.StringVar(value=_def_sort)
        self._sort_btn = StyledDropdown(
            inner, textvariable=self._sort_prop_var, values=_SM_SORT_LABELS,
            font=_FTS, canvas_bg=_bc("panel"), height=28, width=9)
        self._sort_btn.pack(side="left", padx=(0, 2))
        self._sort_btn.bind("<<ComboboxSelected>>",
                            lambda _: self._on_filter_changed())

        # ── Sort direction dropdown ───────────────────────────────────────────
        _def_sortdir = self._cfg.get("sm_filt_sortdir", "desc")
        self._sortdir_var = tk.StringVar(value=_def_sortdir)
        self._sortdir_btn = StyledDropdown(
            inner, textvariable=self._sortdir_var, values=["asc", "desc"],
            font=_FTS, canvas_bg=_bc("panel"), height=28, width=5)
        self._sortdir_btn.pack(side="left", padx=(0, 6))
        self._sortdir_btn.bind("<<ComboboxSelected>>",
                               lambda _: self._on_filter_changed())

        # ── Refresh button ────────────────────────────────────────────────────
        self._refresh_btn = tk.Label(
            inner, text="⟳  Refresh",
            font=_FTS, bg=_bc("panel"), fg=_bc("text_mid"),
            relief="flat", padx=10, pady=6, cursor="hand2")
        self._refresh_btn.bind("<Button-1>", lambda e: self._force_refresh())
        self._refresh_btn.bind("<Enter>", lambda e: self._refresh_btn.config(bg=_bc("hover"), fg=_bc("text")))
        self._refresh_btn.bind("<Leave>", lambda e: self._refresh_btn.config(bg=_bc("panel"), fg=_bc("text_mid")))
        self._refresh_btn.pack(side="left", padx=(0, 6))

        # ── Advanced Search toggle ────────────────────────────────────────────
        self._adv_open = False
        self._adv_btn = tk.Label(
            inner, text="Advanced Search ▾",
            font=_FTS, bg=_bc("panel"), fg=_bc("text_mid"),
            relief="flat", padx=10, pady=6, cursor="hand2")
        self._adv_btn.bind("<Button-1>", lambda e: self._toggle_advanced())
        self._adv_btn.bind("<Enter>", lambda e: self._adv_btn.config(bg=_bc("hover"), fg=_bc("text")))
        self._adv_btn.bind("<Leave>", lambda e: self._adv_btn.config(bg=_bc("panel"), fg=_bc("text_mid")))
        self._adv_btn.pack(side="right")

        # ── Advanced search panel — lives inside bar, hidden by default ─────
        self._adv_frame = tk.Frame(bar, bg=_bc("card2"))
        # pack() called in _toggle_advanced when opened
        self._build_advanced_panel(self._adv_frame)

    def _mk_filter_btn(self, parent, var, choices, padx=(0, 2)):
        """A button that opens a small popup to pick a value from choices."""
        btn = tk.Button(
            parent, textvariable=var,
            font=_FTS, bg=_bc("neutral"), fg=_bc("text"),
            activebackground=_bc("hover"), activeforeground=_bc("text"),
            relief="flat", bd=0, padx=8, pady=5, cursor="hand2")
        btn.pack(side="left", padx=padx)

        def _open_menu():
            m = tk.Menu(parent, tearoff=0,
                        bg=_bc("card"), fg=_bc("text"),
                        activebackground=_bc("accent"),
                        activeforeground=_bc("text"),
                        font=_FTS, bd=0, relief="flat")
            for ch in choices:
                m.add_command(label=ch,
                              command=lambda v=ch: (var.set(v), self._on_filter_changed()))
            try:
                m.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
            finally:
                m.grab_release()

        btn.config(command=_open_menu)
        return btn

    def _toggle_advanced(self):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(fill="x")
            self._adv_btn.config(text="Advanced Search ▴")
        else:
            self._adv_frame.pack_forget()
            self._adv_btn.config(text="Advanced Search ▾")


    def _build_advanced_panel(self, parent):
        inner = tk.Frame(parent, bg=_bc("card2"), padx=18, pady=12)
        inner.pack(fill="x")

        fields = [("Name", "adv_name"), ("Artist", "adv_artist"),
                  ("Album", "adv_album"), ("Genre", "adv_genre"),
                  ("Year", "adv_year"), ("Charter", "adv_charter")]
        self._adv_vars: dict = {}
        col = tk.Frame(inner, bg=_bc("card2"))
        col.pack(side="left", padx=(0, 24))
        for label, key in fields:
            row_f = tk.Frame(col, bg=_bc("card2"), pady=2)
            row_f.pack(fill="x")
            tk.Label(row_f, text=label, font=_FTS, fg=_bc("text_dim"),
                     bg=_bc("card2"), width=8, anchor="w").pack(side="left")
            v = tk.StringVar()
            self._adv_vars[key] = v
            e = tk.Entry(row_f, textvariable=v, font=_FTS,
                         bg=_bc("card"), fg=_bc("text"),
                         insertbackground=_bc("text"),
                         relief="flat", bd=4, width=22)
            e.pack(side="left")

        # Search button
        btn_col = tk.Frame(inner, bg=_bc("card2"))
        btn_col.pack(side="left", padx=(12, 0), anchor="s")
        _s = tk.Label(btn_col, text="Search", font=_FTB,
                      bg=_bc("accent"), fg=_bc("text"),
                      relief="flat", padx=18, pady=6, cursor="hand2")
        _s.pack(pady=(16, 0))
        _s.bind("<Button-1>", lambda e: self._do_advanced_search())
        _s.bind("<Enter>", lambda e, w=_s: w.config(bg=_bc("accent_dim")))
        _s.bind("<Leave>", lambda e, w=_s: w.config(bg=_bc("accent")))

    def _do_advanced_search(self):
        # Build query from adv_vars — simple concatenation for now
        parts = []
        for key, var in self._adv_vars.items():
            v = var.get().strip()
            if v: parts.append(v)
        q = " ".join(parts)
        self._q_var.set(q)
        self._do_search()

    # ─── body: result table + sidebar ────────────────────────────────────────

    def _build_body(self, parent):
        body = tk.Frame(parent, bg=_bc("bg"))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=_bc("bg"))
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        self._build_col_headers(left)
        self._build_scroll_table(left)
        self._build_pagination_bar(left)

        # Divider
        tk.Frame(body, bg=_bc("border"), width=1).grid(row=0, column=1, sticky="ns")

        # Sidebar
        self._build_sidebar(body)

    def _build_col_headers(self, parent):
        hdr = tk.Frame(parent, bg=_bc("panel"))
        hdr.grid(row=0, column=0, sticky="ew")

        # Configure grid columns to match row grid exactly
        hdr.columnconfigure(_CHK_COL, minsize=_CHK_MINW)
        for (_, _, px, _, gcol) in _COLS:
            hdr.columnconfigure(gcol, minsize=px)
        hdr.columnconfigure(_DL_COL, minsize=_DL_MINW)

        # Select-all canvas checkbox
        self._chk_all_var = tk.BooleanVar(value=False)
        self._hdr_chk_cv = self._make_chk_canvas(
            hdr, self._chk_all_var,
            lambda: self._toggle_all(),
            _bc("panel"))
        self._hdr_chk_cv.grid(row=0, column=_CHK_COL, padx=(8, 4), pady=6)

        # Column header buttons
        self._col_header_btns = {}
        for (label, field, px, anchor, gcol) in _COLS:
            btn = tk.Label(
                hdr, text=label,
                font=_FTS, fg=_bc("text_dim"), bg=_bc("panel"),
                relief="flat", cursor="hand2",
                anchor=anchor, padx=6, pady=7)
            btn.grid(row=0, column=gcol, sticky="ew")
            btn.bind("<Button-1>", lambda e, f=field: self._col_header_clicked(f))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=_bc("hover"), fg=_bc("text")))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=_bc("panel"), fg=_bc("text_dim")))
            self._col_header_btns[field] = btn

    # ── Virtual scroll constants ──────────────────────────────────────────────
    _VROW_H      = 34    # estimated row height in pixels (pady=8 → ~34px)
    _VROW_BUFFER = 15    # extra rows to render above/below visible area

    def _build_scroll_table(self, parent):
        wrap = tk.Frame(parent, bg=_bc("card"))
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)

        vsb = ttk.Scrollbar(wrap, orient="vertical")
        vsb.grid(row=0, column=1, sticky="ns")

        self._canvas = tk.Canvas(
            wrap, bg=_bc("card"), highlightthickness=0,
            yscrollcommand=vsb.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vsb.config(command=self._vscroll_cmd)

        for w in (self._canvas,):
            w.bind("<MouseWheel>", self._on_mwheel)
            w.bind("<Button-4>",   self._on_mwheel)
            w.bind("<Button-5>",   self._on_mwheel)
            w.bind("<Button-2>",   self._on_mmb_click)

        # _table_inner is a plain frame; we position it manually.
        # For virtual scrolling we DON'T pack children into it —
        # instead we use place() so we control y-position ourselves.
        self._table_inner = tk.Frame(self._canvas, bg=_bc("card"))
        self._table_win   = self._canvas.create_window(
            (0, 0), window=self._table_inner, anchor="nw")

        self._canvas.bind(
            "<Configure>",
            self._on_canvas_configure)
        self._canvas.bind("<Enter>", lambda _: None)
        self._canvas.bind("<Leave>", lambda _: None)

        # Virtual scroll state
        self._virt_rendered: dict = {}   # idx → frame (currently live widgets)
        self._virt_scroll_y: int  = 0    # current pixel scroll offset

    def _vscroll_cmd(self, *args):
        """Intercept scrollbar commands to update virtual scroll state."""
        self._canvas.yview(*args)
        self._refresh_virtual_rows()

    def _on_canvas_configure(self, event):
        """Called when canvas is resized — update inner frame width + refresh."""
        self._canvas.itemconfig(self._table_win, width=event.width)
        self._refresh_virtual_rows()

    def _virt_total_height(self) -> int:
        return max(len(self._songs) * self._VROW_H, 1)

    def _update_virt_scrollregion(self):
        total = self._virt_total_height()
        self._table_inner.config(height=total)
        self._canvas.configure(scrollregion=(0, 0,
            self._canvas.winfo_width(), total))

    def _refresh_virtual_rows(self, _event=None):
        """
        Render only rows visible in the viewport (± _VROW_BUFFER).
        Destroy rows that have scrolled out of range.
        """
        if not self._songs:
            return
        canvas_h = self._canvas.winfo_height()
        if canvas_h <= 1:
            self.after(50, self._refresh_virtual_rows)
            return

        # Current scroll offset in pixels
        lo, hi = self._canvas.yview()
        total   = self._virt_total_height()
        y_top   = int(lo * total)
        y_bot   = int(hi * total)

        row_h   = self._VROW_H
        buf     = self._VROW_BUFFER
        n       = len(self._songs)

        vis_start = max(0, y_top  // row_h - buf)
        vis_end   = min(n - 1,  y_bot // row_h + buf)

        # Destroy rows outside visible range
        for idx in list(self._virt_rendered.keys()):
            if idx < vis_start or idx > vis_end:
                try:
                    self._virt_rendered[idx].destroy()
                except Exception:
                    pass
                del self._virt_rendered[idx]

        # Create rows that are now in range but not yet rendered
        for idx in range(vis_start, vis_end + 1):
            if idx not in self._virt_rendered:
                self._virt_render_row(idx)

    def _virt_render_row(self, idx: int):
        """Build and place a single row frame at its virtual y position."""
        if idx >= len(self._songs):
            return
        song = self._songs[idx]
        row  = self._build_row_frame(idx, song)
        row.place(x=0, y=idx * self._VROW_H,
                  relwidth=1.0, height=self._VROW_H)
        self._virt_rendered[idx] = row

    def _build_pagination_bar(self, parent):
        foot = tk.Frame(parent, bg=_bc("panel"), pady=6)
        foot.grid(row=2, column=0, sticky="ew")

        self._result_count_var = tk.StringVar(value="")
        tk.Label(foot, textvariable=self._result_count_var,
                 font=_FTS, fg=_bc("text_dim"),
                 bg=_bc("panel")).pack(side="left", padx=12)

        self._load_more_btn = tk.Label(
            foot, text="Load More  ↓", font=_FTS,
            bg=_bc("border2"), fg=_bc("text"),
            relief="flat", padx=14, pady=4, cursor="hand2")
        self._load_more_btn.pack(side="right", padx=12)
        self._load_more_btn._enabled = False
        def _lmb_click(e):
            if getattr(self._load_more_btn, "_enabled", False):
                self._load_more()
        self._load_more_btn.bind("<Button-1>", _lmb_click)
        self._load_more_btn.bind("<Enter>", lambda e: self._load_more_btn.config(bg=_bc("hover")) if getattr(self._load_more_btn, "_enabled", False) else None)
        self._load_more_btn.bind("<Leave>", lambda e: self._load_more_btn.config(bg=_bc("border2")))

    # ─── sidebar ─────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        SB_W = 300
        sb = tk.Frame(parent, bg=_bc("panel"), width=SB_W)
        sb.grid(row=0, column=2, sticky="nsew")
        sb.pack_propagate(False)
        self._sb = sb

        # ── Album art area ────────────────────────────────────────────────────
        _art_h = 220 if _IS_MAC else 300
        self._art_frame = tk.Frame(sb, bg=_bc("card"), height=_art_h)
        self._art_frame.pack(fill="x")
        self._art_frame.pack_propagate(False)

        self._art_lbl = tk.Label(
            self._art_frame, bg=_bc("card"),
            text="No song selected",
            font=_FTS, fg=_bc("text_dim"))
        self._art_lbl.pack(fill="both", expand=True)

        tk.Frame(sb, bg=_bc("border"), height=1).pack(fill="x")

        # ── Scrollable info area ──────────────────────────────────────────────
        info_wrap = tk.Frame(sb, bg=_bc("panel"))
        info_wrap.pack(fill="both", expand=True)
        info_vsb = ttk.Scrollbar(info_wrap, orient="vertical")
        info_vsb.pack(side="right", fill="y")
        info_cv = tk.Canvas(info_wrap, bg=_bc("panel"), highlightthickness=0,
                            yscrollcommand=info_vsb.set)
        info_cv.pack(side="left", fill="both", expand=True)
        info_vsb.config(command=info_cv.yview)
        self._info_inner = tk.Frame(info_cv, bg=_bc("panel"), padx=12, pady=8)
        info_win = info_cv.create_window((0, 0), window=self._info_inner, anchor="nw")
        self._info_inner.bind(
            "<Configure>",
            lambda _: info_cv.configure(scrollregion=info_cv.bbox("all")))
        info_cv.bind(
            "<Configure>",
            lambda e: info_cv.itemconfig(info_win, width=e.width))
        for w in (info_cv, self._info_inner):
            w.bind("<MouseWheel>", lambda e: info_cv.yview_scroll(_scroll_units(e), "units"))
            w.bind("<Button-4>",   lambda e: info_cv.yview_scroll(-1, "units"))
            w.bind("<Button-5>",   lambda e: info_cv.yview_scroll(1,  "units"))

        # ── Charter line ──────────────────────────────────────────────────────
        chtr_row = tk.Frame(self._info_inner, bg=_bc("panel"))
        chtr_row.pack(fill="x", pady=(0, 4))
        tk.Label(chtr_row, text="Charter: ", font=_FTB,
                 fg=_bc("text"), bg=_bc("panel")).pack(side="left")
        self._charter_lbl = tk.Label(chtr_row, text="—",
                                      font=_FT, fg=_bc("text_mid"),
                                      bg=_bc("panel"))
        self._charter_lbl.pack(side="left")

        # ── Length + Diff row ─────────────────────────────────────────────────
        meta_row = tk.Frame(self._info_inner, bg=_bc("panel"))
        meta_row.pack(fill="x", pady=(0, 6))
        tk.Label(meta_row, text="Length: ", font=_FTB,
                 fg=_bc("text"), bg=_bc("panel")).pack(side="left")
        self._length_lbl = tk.Label(meta_row, text="—",
                                     font=_FT, fg=_bc("text_mid"),
                                     bg=_bc("panel"))
        self._length_lbl.pack(side="left")
        # Diff badge on the right
        self._diff_badge = tk.Label(meta_row, text="",
                                     font=_FTB, fg=_bc("text"),
                                     bg=_bc("accent_dim"), padx=6, pady=2,
                                     relief="flat")
        self._diff_badge.pack(side="right")

        tk.Frame(self._info_inner, bg=_bc("border"), height=1).pack(fill="x", pady=(2, 8))

        # ── Feature checkmarks ────────────────────────────────────────────────
        tk.Label(self._info_inner, text="FEATURES",
                 font=("Lato", 7, "bold"), fg=_bc("text_dim"),
                 bg=_bc("panel")).pack(anchor="w")
        self._feat_frame = tk.Frame(self._info_inner, bg=_bc("panel"))
        self._feat_frame.pack(fill="x", pady=(4, 0))
        self._feat_rows: dict = {}   # feature_key → tk.Label (the ✓/✗)

        _FEATURES = [
            ("hasSoloSections",    "Solo Sections"),
            ("hasLyrics",          "Lyrics"),
            ("hasForcedNotes",     "Forced Notes"),
            ("hasTapNotes",        "Tap Notes"),
            ("hasOpenNotes",       "Open Notes"),
            ("hasVideoBackground", "Video Background"),
        ]
        for key, label in _FEATURES:
            r = tk.Frame(self._feat_frame, bg=_bc("panel"), pady=1)
            r.pack(fill="x")
            icon = tk.Label(r, text="✗", font=_FT, fg=_bc("error"),
                            bg=_bc("panel"), width=2, anchor="w")
            icon.pack(side="left")
            tk.Label(r, text=label, font=_FTS, fg=_bc("text_mid"),
                     bg=_bc("panel"), anchor="w").pack(side="left")
            self._feat_rows[key] = icon

        tk.Frame(self._info_inner, bg=_bc("border"), height=1).pack(fill="x", pady=(10, 6))

        # ── NPS stats ─────────────────────────────────────────────────────────
        def _stat_row(label):
            r = tk.Frame(self._info_inner, bg=_bc("panel"), pady=1)
            r.pack(fill="x")
            tk.Label(r, text=label + ": ", font=_FTB,
                     fg=_bc("text"), bg=_bc("panel")).pack(side="left")
            v = tk.StringVar(value="—")
            tk.Label(r, textvariable=v, font=_FT,
                     fg=_bc("text_mid"), bg=_bc("panel")).pack(side="left")
            return v

        self._avg_nps_var  = _stat_row("Average NPS")
        self._max_nps_var  = _stat_row("Maximum NPS")
        self._note_cnt_var = _stat_row("Note Count")

        tk.Frame(self._info_inner, bg=_bc("border"), height=1).pack(fill="x", pady=(6, 0))

        # ── Download buttons (pinned to bottom) ──────────────────────────────
        dl_row = tk.Frame(sb, bg=_bc("panel"))
        dl_row.pack(fill="x", padx=12, pady=(8, 4))
        RoundedButton(
            dl_row, "Download", self._info_download,
            bg_color=_bc("accent"), hover_color=_bc("accent_dim"),
            text_color=_bc("text"), height=38, radius=10,
            text_font=_FTB, canvas_bg=_bc("panel"),
        ).pack(fill="x", pady=(0, 4))
        RoundedButton(
            dl_row, "Download Selected Songs", self._batch_download,
            bg_color=_bc("border2"), hover_color=_bc("hover"),
            text_color=_bc("text"), height=34, radius=10,
            text_font=_FTS, canvas_bg=_bc("panel"),
        ).pack(fill="x", pady=(0, 8))

    # ─── status bar ──────────────────────────────────────────────────────────

    def _build_statusbar(self, parent):
        bar = tk.Frame(parent, bg=_bc("card2"))
        bar.grid(row=2, column=0, sticky="ew")

        inner = tk.Frame(bar, bg=_bc("card2"), padx=12, pady=4)
        inner.pack(fill="x")

        self._status_var = tk.StringVar(value="Ready — enter a search above.")
        self._status_lbl = tk.Label(
            inner, textvariable=self._status_var,
            font=_FTS, fg=_bc("text_dim"), bg=_bc("card2"), anchor="w")
        self._status_lbl.pack(side="left")

        # Download queue icon — hover to see active download progress
        self._queue_badge_var = tk.StringVar(value="")
        self._dl_hover_win   = None   # the lightweight popup (not a modal)
        self._dl_icon_lbl = tk.Label(
            inner, text="⬇", font=("Lato", 13),
            fg=_bc("text_dim"), bg=_bc("card2"),
            cursor="hand2", padx=6, pady=0)
        self._dl_icon_lbl.pack(side="right", padx=(6, 0))
        self._dl_icon_lbl.bind("<Enter>", self._dl_hover_show)
        self._dl_icon_lbl.bind("<Leave>", self._dl_hover_hide)
        self._queue_badge = tk.Label(
            inner, textvariable=self._queue_badge_var,
            font=_FTS, fg=_bc("accent3"), bg=_bc("card2"))
        self._queue_badge.pack(side="right")

        self._dl_count_var = tk.StringVar(value="")
        tk.Label(inner, textvariable=self._dl_count_var,
                 font=_FTS, fg=_bc("text_dim"), bg=_bc("card2"),
                 anchor="e").pack(side="right", padx=(0, 12))

    # =========================================================================
    #  DOWNLOAD QUEUE
    # =========================================================================

    # Queue state: {idx: {"name": str, "pct": int, "done": bool, "success": bool}}
    _queue: dict = {}

    def _queue_add(self, idx: int, name: str):
        self._queue[idx] = {"name": name, "pct": 0, "done": False, "success": False}
        self._queue_refresh_ui()

    def _queue_update(self, idx: int, pct: int, done):
        """pct=-1 means failed. done=True means success. done=None means progress."""
        if idx not in self._queue:
            return
        entry = self._queue[idx]
        if done is True:
            entry["pct"]     = 100
            entry["done"]    = True
            entry["success"] = True
        elif done is False or pct == -1:
            entry["done"]    = True
            entry["success"] = False
        else:
            entry["pct"] = pct
        self._queue_refresh_ui()

    def _queue_refresh_ui(self):
        """Update the badge counter and download icon colour. No widget churn."""
        active = [e for e in self._queue.values() if not e["done"]]
        done   = [e for e in self._queue.values() if e["done"]]
        total  = len(self._queue)

        if total == 0:
            self._queue_badge_var.set("")
            icon_col = _bc("text_dim")
        elif active:
            n_active = len(active)
            n_done   = len(done)
            avg_pct  = sum(e["pct"] for e in active) // max(n_active, 1)
            self._queue_badge_var.set(
                f"{n_active} active · {avg_pct}%  |  {n_done}/{total} done")
            icon_col = _bc("accent3")
        else:
            n_ok  = sum(1 for e in done if e["success"])
            n_err = sum(1 for e in done if not e["success"])
            self._queue_badge_var.set(f"All done — {n_ok} \u2713  {n_err} \u2717")
            icon_col = _bc("success") if not n_err else _bc("warn")

        if hasattr(self, "_dl_icon_lbl"):
            self._dl_icon_lbl.config(fg=icon_col)

        # Refresh hover popup content if it is currently visible
        if hasattr(self, "_dl_hover_win") and \
                self._dl_hover_win and self._dl_hover_win.winfo_exists():
            self._dl_hover_refresh()

    # =========================================================================
    #  DOWNLOAD HOVER POPUP  (replaces the old blocking modal)
    # =========================================================================

    def _dl_hover_show(self, _=None):
        """Build and position the lightweight hover popup above the icon."""
        if self._dl_hover_win and self._dl_hover_win.winfo_exists():
            return  # already visible

        icon = self._dl_icon_lbl
        win = tk.Toplevel(self)
        # Withdraw immediately so the OS never places it at a default/wrong
        # position.  We position it ourselves after update_idletasks().
        win.withdraw()
        win.wm_overrideredirect(True)
        win.configure(bg=_bc("border"))
        try:
            win.attributes("-topmost", True)  # best-effort; some Linux WMs ignore this
        except tk.TclError:
            pass
        self._dl_hover_win = win

        inner = tk.Frame(win, bg=_bc("card"), padx=14, pady=10)
        inner.pack(padx=1, pady=1)   # 1 px border via bg=_bc("border")

        # Header row
        hdr = tk.Frame(inner, bg=_bc("card"))
        hdr.pack(fill="x", anchor="w")
        tk.Label(hdr, text="⬇  Downloads", font=_FTH,
                 fg=_bc("text"), bg=_bc("card")).pack(side="left")

        tk.Frame(inner, bg=_bc("border"), height=1).pack(fill="x", pady=(6, 0))

        # Dynamic info area — updated by _dl_hover_refresh() via StringVar
        self._dl_hover_name_var  = tk.StringVar(value="")
        self._dl_hover_pct_var   = tk.StringVar(value="")
        self._dl_hover_stats_var = tk.StringVar(value="")

        info = tk.Frame(inner, bg=_bc("card"))
        info.pack(fill="x", pady=(6, 0), anchor="w")

        # Current song row
        name_row = tk.Frame(info, bg=_bc("card"))
        name_row.pack(fill="x", pady=(0, 2))
        tk.Label(name_row, text="Now:", font=_FTS, fg=_bc("text_dim"),
                 bg=_bc("card"), width=5, anchor="w").pack(side="left")
        tk.Label(name_row, textvariable=self._dl_hover_name_var,
                 font=_FTB, fg=_bc("text"), bg=_bc("card"),
                 anchor="w").pack(side="left", fill="x", expand=True)

        # Progress row
        pct_row = tk.Frame(info, bg=_bc("card"))
        pct_row.pack(fill="x", pady=(0, 4))
        tk.Label(pct_row, text="", font=_FTS, fg=_bc("text_dim"),
                 bg=_bc("card"), width=5, anchor="w").pack(side="left")
        self._dl_hover_pb = ttk.Progressbar(
            pct_row, length=220, mode="determinate", value=0)
        self._dl_hover_pb.pack(side="left", padx=(0, 8))
        tk.Label(pct_row, textvariable=self._dl_hover_pct_var,
                 font=_FTS, fg=_bc("accent3"), bg=_bc("card"),
                 width=5, anchor="w").pack(side="left")

        # Summary row
        tk.Label(inner, textvariable=self._dl_hover_stats_var,
                 font=_FTS, fg=_bc("text_dim"), bg=_bc("card"),
                 anchor="w").pack(fill="x", pady=(2, 0))

        # --- Position the popup now that all widgets have been laid out --------
        # update_idletasks() forces Tk to compute real widget sizes without
        # making the window visible (it is still withdrawn).
        win.update_idletasks()

        pw = win.winfo_reqwidth()
        ph = win.winfo_reqheight()

        # Icon geometry in *virtual-desktop* screen coordinates.
        # winfo_rootx/y are correct across all monitors on both Windows and Linux.
        ix = icon.winfo_rootx()
        iy = icon.winfo_rooty()
        iw = icon.winfo_width()

        # Right-align popup trailing edge with the icon's trailing edge.
        # Sit just above the icon.
        x = ix + iw - pw
        y = iy - ph - 6

        # NOTE: Do NOT clamp using winfo_screenwidth() / winfo_screenheight().
        # Those calls return the *primary* monitor's dimensions, which causes
        # the popup to be pinned to Screen 1's right/bottom edge even when the
        # app lives on a secondary monitor.
        # Instead, only guard against going off the virtual-desktop's left/top
        # edges (coordinates < 0) — the icon itself is already on a valid
        # screen, so aligning to it keeps us on the same monitor.
        x = max(0, x)
        y = max(0, y)

        win.geometry(f"+{x}+{y}")
        win.bind("<Leave>", self._dl_hover_hide)

        # Reveal at the correct position — no flash, no wrong-screen placement.
        win.deiconify()

        self._dl_hover_refresh()

    def _dl_hover_refresh(self):
        """Update the popup labels in-place — no widget destruction."""
        if not (self._dl_hover_win and self._dl_hover_win.winfo_exists()):
            return

        active = sorted(
            [(idx, e) for idx, e in self._queue.items() if not e["done"]],
            key=lambda kv: -kv[1]["pct"])
        done  = [e for e in self._queue.values() if e["done"]]
        total = len(self._queue)

        if active:
            # Show the most-progressed active download
            _, top = active[0]
            name = top["name"]
            pct  = top["pct"]
            self._dl_hover_name_var.set(name[:46] + ("…" if len(name) > 46 else ""))
            self._dl_hover_pct_var.set(f"{pct}%")
            self._dl_hover_pb.config(value=pct)
            n_more = len(active) - 1
            n_done = len(done)
            extras = f"  +{n_more} more queued" if n_more else ""
            self._dl_hover_stats_var.set(
                f"{n_done}/{total} done{extras}")
        elif done:
            n_ok  = sum(1 for e in done if e["success"])
            n_err = sum(1 for e in done if not e["success"])
            self._dl_hover_name_var.set(
                f"All done \u2014 {n_ok} \u2713  {n_err} \u2717")
            self._dl_hover_pct_var.set("")
            self._dl_hover_pb.config(value=100)
            self._dl_hover_stats_var.set("")
        else:
            self._dl_hover_name_var.set("No downloads yet.")
            self._dl_hover_pct_var.set("")
            self._dl_hover_pb.config(value=0)
            self._dl_hover_stats_var.set("")

    def _dl_hover_hide(self, _=None):
        """Destroy the popup — called on <Leave> or programmatically."""
        if self._dl_hover_win:
            try:
                self._dl_hover_win.destroy()
            except Exception:
                pass
            self._dl_hover_win = None

    def _queue_clear_done(self):
        """Remove completed entries from the queue."""
        self._queue = {k: v for k, v in self._queue.items() if not v["done"]}
        self._queue_refresh_ui()

    # =========================================================================
    #  SETTINGS TAB
    # =========================================================================

    def _build_settings_content(self):
        canvas = tk.Canvas(self._settings_frame, bg=_bc("bg"),
                           highlightthickness=0)
        vsb = ttk.Scrollbar(self._settings_frame, orient="vertical",
                            command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=_bc("bg"))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(win, width=e.width))

        pad = dict(padx=32, pady=0)

        # ── Chart library directory ───────────────────────────────────────────
        sec1 = self._settings_section(inner, "Chart library directory")
        dir_row = tk.Frame(sec1, bg=_bc("card"))
        dir_row.pack(fill="x", pady=(0, 8))

        dir_border = tk.Frame(dir_row, bg=_bc("border"), padx=1, pady=1)
        dir_border.pack(side="left", fill="x", expand=True, padx=(0, 8))
        dir_inner = tk.Frame(dir_border, bg=_bc("card2"))
        dir_inner.pack(fill="x")
        self._dir_var = tk.StringVar(value=self._cfg.get(
            "sm_songs_dir",
            str(Path.home() / "Clone Hero" / "Songs") if _IS_MAC else ""))
        tk.Entry(dir_inner, textvariable=self._dir_var,
                 font=_FTS, bg=_bc("card2"), fg=_bc("text"),
                 insertbackground=_bc("text"),
                 relief="flat", bd=6).pack(fill="x")

        def _lbl_btn(parent, text, cmd, bg, hover_bg, fg=None, font=None, padx=14, pady=6):
            fg = fg or _bc("text")
            font = font or _FTS
            lbl = tk.Label(parent, text=text, font=font, bg=bg, fg=fg,
                           relief="flat", padx=padx, pady=pady, cursor="hand2")
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e, w=lbl, hb=hover_bg: w.config(bg=hb))
            lbl.bind("<Leave>", lambda e, w=lbl, ob=bg: w.config(bg=ob))
            return lbl
        _lbl_btn(dir_row, "Open Folder", self._open_dir,
                 _bc("border2"), _bc("hover"), font=_FTS).pack(side="left", padx=(0, 6))
        _lbl_btn(dir_row, "Choose", self._browse_dir,
                 _bc("accent"), _bc("accent_dim"), font=_FTB).pack(side="left")

        # ── Download Settings ─────────────────────────────────────────────────
        sec2 = self._settings_section(inner, "Download Settings")
        skip_row = tk.Frame(sec2, bg=_bc("card"))
        skip_row.pack(anchor="w")
        self._skip_video_var = tk.BooleanVar(
            value=self._cfg.get("sm_skip_video", False))
        tk.Checkbutton(
            skip_row, variable=self._skip_video_var,
            font=("Lato", 13), fg=_bc("text"), bg=_bc("card"),
            activebackground=_bc("card"),
            selectcolor=_bc("accent_dim"),
            relief="flat", bd=0, highlightthickness=0, cursor="hand2",
            command=self._on_skip_video_changed
        ).pack(side="left")
        tk.Label(skip_row, text="Download Video Backgrounds",
                 font=_FT, fg=_bc("text"), bg=_bc("card")).pack(side="left")

        # ── Version tag (bottom-right) ────────────────────────────────────────
        ver_bar = tk.Frame(inner, bg=_bc("bg"))
        ver_bar.pack(fill="x", pady=(24, 8), padx=32)
        tk.Label(ver_bar, text="v3.4.5", font=_FTS, fg=_bc("text_dim"),
                 bg=_bc("bg")).pack(side="right")

    def _settings_section(self, parent, title: str) -> tk.Frame:
        """Renders a card-style settings section, returns the inner content frame."""
        outer = tk.Frame(parent, bg=_bc("card"),
                         highlightbackground=_bc("border"),
                         highlightthickness=1)
        outer.pack(fill="x", padx=32, pady=(24, 0))
        hdr = tk.Frame(outer, bg=_bc("card"), pady=14, padx=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=_FTH,
                 fg=_bc("text"), bg=_bc("card")).pack(anchor="w")
        tk.Frame(outer, bg=_bc("border"), height=1).pack(fill="x")
        body = tk.Frame(outer, bg=_bc("card"), padx=18, pady=14)
        body.pack(fill="x")
        return body

    # =========================================================================
    #  SCROLL
    # =========================================================================

    def _on_mwheel(self, event):
        if self._mmb_active:
            self._mmb_stop()
        self._canvas.yview_scroll(_scroll_units(event), "units")
        self._refresh_virtual_rows()
        self._check_scroll_bottom()

    # ── Middle-mouse-button click-to-drag scroll ──────────────────────────────
    _mmb_active:  bool   = False
    _mmb_start_y: int    = 0
    _mmb_ticker:  object = None

    def _on_mmb_click(self, event):
        """Single middle-click toggles auto-scroll mode."""
        if self._mmb_active:
            self._mmb_stop()
        else:
            self._mmb_active  = True
            self._mmb_start_y = event.y_root
            try:
                self._canvas.config(cursor="sb_v_double_arrow")
            except Exception:
                pass
            self._mmb_tick()

    def _mmb_tick(self):
        if not self._mmb_active:
            return
        try:
            cur_y = self._canvas.winfo_pointery()
            delta = cur_y - self._mmb_start_y
            dead  = 10
            if abs(delta) > dead:
                speed = (delta - (dead if delta > 0 else -dead)) / 25.0
                units = int(speed) or (1 if speed > 0 else -1)
                self._canvas.yview_scroll(units, "units")
                self._refresh_virtual_rows()
                self._check_scroll_bottom()
        except Exception:
            pass
        self._mmb_ticker = self.after(16, self._mmb_tick)

    def _mmb_stop(self, _event=None):
        self._mmb_active = False
        if self._mmb_ticker is not None:
            try:
                self.after_cancel(self._mmb_ticker)
            except Exception:
                pass
            self._mmb_ticker = None
        try:
            self._canvas.config(cursor="")
        except Exception:
            pass

    def _check_scroll_bottom(self):
        if not getattr(self._load_more_btn, "_enabled", False): return
        try:
            _, hi = self._canvas.yview()
            if hi >= 0.92:
                self._load_more_btn._enabled = False
                self._load_more_btn.config(bg=_bc("border2"), fg=_bc("text_dim"), cursor="arrow")
                self._status("Loading more...", _bc("text_dim"))
                threading.Thread(target=self._fetch, daemon=True).start()
        except Exception:
            pass

    # =========================================================================
    #  SETTINGS CALLBACKS
    # =========================================================================

    def _browse_dir(self):
        d = filedialog.askdirectory(
            title="Select Clone Hero songs folder",
            initialdir=self._dir_var.get() or os.path.expanduser("~"))
        if d:
            self._dir_var.set(d)
            self._cfg["sm_songs_dir"] = d
            self._save_cfg()

    def _open_dir(self):
        path = self._dir_var.get().strip()
        # Resolve to an absolute, normalised path so we never accidentally
        # hand a relative or malformed string to the shell.
        if path:
            path = os.path.normpath(os.path.abspath(path))
        if path and os.path.isdir(path):
            try:
                if _IS_WINDOWS:
                    # Explicitly invoke explorer.exe — avoids os.startfile /
                    # ShellExecute picking up a stale or wrong shell-verb
                    # association and running a batch file instead of the folder.
                    subprocess.Popen(["explorer.exe", path])
                elif _IS_MAC:
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception as exc:
                messagebox.showerror("Open Folder",
                                     f"Could not open folder:\n{exc}",
                                     parent=self)
        else:
            messagebox.showwarning("Folder not found",
                                   "The configured folder does not exist.\n\n"
                                   f"Path: {path or '(empty)'}",
                                   parent=self)

    def _songs_dir(self) -> str:
        return self._dir_var.get().strip()

    def _on_skip_video_changed(self):
        self._cfg["sm_skip_video"] = self._skip_video_var.get()
        self._save_cfg()

    def _on_fmt_changed(self):
        self._cfg["sm_dl_format"] = self._fmt_var.get()
        self._save_cfg()

    def _on_layout_changed(self):
        self._cfg["sm_table_layout"] = self._table_layout_var.get()
        self._save_cfg()

    def _save_filter_prefs(self):
        self._cfg["sm_filt_instrument"] = self._inst_var.get()
        self._cfg["sm_filt_difficulty"] = self._diff_var.get()
        self._cfg["sm_filt_sort"]       = self._sort_prop_var.get()
        self._cfg["sm_filt_sortdir"]    = self._sortdir_var.get()
        self._save_cfg()

    # =========================================================================
    #  FILTER / SEARCH CALLBACKS
    # =========================================================================

    _filter_after_id = None
    _query_after_id  = None

    def _on_query_changed(self, *_):
        if not getattr(self, "_ui_ready", False): return
        if getattr(self, "_suppress_query_trace", False): return
        if self._q_var.get().strip() == "":
            if self._query_after_id:
                self.after_cancel(self._query_after_id)
            self._query_after_id = self.after(450, self._initial_load)
        else:
            if self._query_after_id:
                self.after_cancel(self._query_after_id)
            self._query_after_id = None

    def _on_filter_changed(self, *_):
        if not getattr(self, "_ui_ready", False): return
        self._save_filter_prefs()
        if self._filter_after_id:
            self.after_cancel(self._filter_after_id)
        self._filter_after_id = self.after(120, self._refresh_from_filters)

    def _refresh_from_filters(self):
        self._filter_after_id = None
        if not _SM_HAS_REQUESTS: return
        self._sync_filter_state()
        self._reset_results()
        self._search_loading_lbl.config(text="⟳")
        self._status("Filtering...", _bc("text_dim"))
        threading.Thread(target=self._fetch, daemon=True).start()

    def _sync_filter_state(self):
        try:
            inst_idx = _SM_INST_LABELS.index(self._inst_var.get())
            self._filt_instrument = _SM_INSTRUMENTS[inst_idx]
        except ValueError:
            self._filt_instrument = None
        try:
            diff_idx = _SM_DIFF_LABELS.index(self._diff_var.get())
            self._filt_difficulty = _SM_DIFFICULTIES[diff_idx]
        except ValueError:
            self._filt_difficulty = None
        try:
            sort_idx = _SM_SORT_LABELS.index(self._sort_prop_var.get())
            self._filt_sort_prop = _SM_SORT_PROPS[sort_idx]
        except ValueError:
            self._filt_sort_prop = None
        self._filt_sort_dir  = self._sortdir_var.get()

    def _reset_results(self):
        self._page  = 1
        self._songs = []
        self._found = 0
        self._selected.clear()
        self._clear_rows()
        self._load_more_btn._enabled = False
        self._load_more_btn.config(bg=_bc("border2"), fg=_bc("text_dim"), cursor="arrow")

    def _initial_load(self):
        if not _SM_HAS_REQUESTS: return
        self._suppress_query_trace = True
        self._q_var.set("")
        self._suppress_query_trace = False
        self._query = ""
        self._reset_results()
        self._sync_filter_state()
        self._status("Loading songs...", _bc("text_dim"))
        self._search_loading_lbl.config(text="⟳")
        threading.Thread(target=self._fetch, daemon=True).start()


    def _force_refresh(self):
        """Hard-reset all state and re-fetch, identical to a fresh open."""
        self._page  = 1
        self._songs = []
        self._found = 0
        self._selected.clear()
        self._active_idx = None
        self._initial_load()
    # ─── column sort ─────────────────────────────────────────────────────────

    def _col_header_clicked(self, field: str):
        sp = _COL_SORT.get(field)
        if sp is None: return
        if self._sort_col == field:
            self._sort_dir = "asc" if self._sort_dir == "desc" else "desc"
        else:
            self._sort_col = field
            self._sort_dir = "asc"
        self._filt_sort_prop = sp
        self._filt_sort_dir  = self._sort_dir
        self._refresh_col_headers()
        if self._query:
            self._reset_results()
            self._status("Sorting…", _bc("text_dim"))
            threading.Thread(target=self._fetch, daemon=True).start()

    def _refresh_col_headers(self):
        for field, btn in self._col_header_btns.items():
            label = next((l for l, f, *_ in _COLS if f == field), field)
            if field == self._sort_col:
                arrow = " ↓" if self._sort_dir == "asc" else " ↑"
                btn.config(text=label + arrow, fg=_bc("text"))
            else:
                btn.config(text=label, fg=_bc("text_dim"))

    # =========================================================================
    #  SEARCH / FETCH
    # =========================================================================

    def _do_search(self):
        q = self._q_var.get().strip()
        if not q:
            self._initial_load()
            return
        if not _SM_HAS_REQUESTS:
            messagebox.showerror(
                "Missing dependency",
                "Install requests:  pip install requests",
                parent=self)
            return
        self._sync_filter_state()
        self._query = q
        self._reset_results()
        self._search_loading_lbl.config(text="⟳")
        self._status(f'Searching for "{q}"...', _bc("text_dim"))
        threading.Thread(target=self._fetch, daemon=True).start()

    def _load_more(self):
        self._status("Loading more...", _bc("text_dim"))
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        body = {
            "search":        self._query or "",
            "page":          self._page,
            "per_page":      _SM_PER_PAGE,
            "instrument":    self._filt_instrument,
            "difficulty":    self._filt_difficulty,
            "sort":          {"type": self._filt_sort_prop,
                              "direction": self._filt_sort_dir}
                             if self._filt_sort_prop else None,
            "source":        "bridge",
        }
        try:
            r = _sm_requests.post(
                _SM_API_URL, json=body, timeout=15,
                headers={"User-Agent": "CHSuite/5.0 CHSongManager"})
            r.raise_for_status()
            resp = r.json()
        except Exception as exc:
            self.after(0, lambda: self._search_loading_lbl.config(text=""))
            self.after(0, self._status, f"Search error: {exc}", _bc("error"))
            return
        batch = resp.get("data", [])
        found = resp.get("found", 0)
        self._songs.extend(batch)
        self._found = found
        has_more = len(self._songs) < found
        self._page += 1
        self.after(0, self._render_batch, batch, has_more, found)

    def _render_batch(self, batch, has_more, found):
        self._search_loading_lbl.config(text="")
        base = len(self._songs) - len(batch)
        for rel, song in enumerate(batch):
            self._add_row(base + rel, song)
        n = len(self._songs)
        self._result_count_var.set(
            f"{found:,} Results" if found else f"{n} charts loaded")
        self._status(
            f'Showing {n} of {found:,} results for "{self._query}"',
            _bc("success"))
        self._load_more_btn._enabled = has_more
        self._load_more_btn.config(
            bg=_bc("border2"),
            fg=_bc("text") if has_more else _bc("text_dim"),
            cursor="hand2" if has_more else "arrow")
        # Update scroll region + render newly visible rows
        self._update_virt_scrollregion()
        self._refresh_virtual_rows()

    # =========================================================================
    #  ROW RENDERING
    # =========================================================================

    def _clear_rows(self):
        # Destroy all currently rendered virtual row frames
        for frame in self._virt_rendered.values():
            try:
                frame.destroy()
            except Exception:
                pass
        self._virt_rendered.clear()
        # Legacy lists kept for compatibility with sidebar / toggle_all
        self._row_frames.clear()
        self._row_chk_vars.clear()
        self._row_bg.clear()
        self._dl_bars.clear()
        self._dl_labels.clear()
        self._chk_draws = []
        self._result_count_var.set("")
        # Uncheck header select-all
        self._chk_all_var.set(False)
        self._redraw_hdr_chk()
        # Reset virtual scroll region
        self._update_virt_scrollregion()

    def _add_row(self, idx: int, song: dict):
        """
        Record row metadata — does NOT build any widgets.
        Widget construction is deferred to _build_row_frame(), called
        on-demand by the virtual scroll engine as rows enter the viewport.
        """
        bg = _bc("card") if idx % 2 == 0 else _bc("card2")
        self._row_bg.append(bg)
        # Extend per-row state arrays so index lookups stay consistent
        self._row_frames.append(None)       # filled lazily when rendered
        self._row_chk_vars.append(None)     # filled lazily when rendered
        self._dl_bars[idx]   = None
        self._dl_labels[idx] = None
        if not hasattr(self, "_chk_draws"): self._chk_draws = []
        self._chk_draws.append([])          # placeholder; filled on render
        # Update virtual scroll region so the canvas knows the new total height
        self._update_virt_scrollregion()
        # Ask the virtual engine to render if this row is currently in view
        self._refresh_virtual_rows()

    def _build_row_frame(self, idx: int, song: dict) -> tk.Frame:
        """
        Construct all widgets for a single song row and return the frame.
        Called by the virtual scroll engine when the row enters the viewport.
        """
        bg = _bc("card") if idx % 2 == 0 else _bc("card2")

        row = tk.Frame(self._table_inner, bg=bg, pady=0, padx=0)

        def _is_active(): return self._active_idx == idx

        # ── Grid columns — same config as header ─────────────────────────────
        row.columnconfigure(_CHK_COL, minsize=_CHK_MINW)
        for (_, _, px, _, gcol) in _COLS:
            row.columnconfigure(gcol, minsize=px)
        row.columnconfigure(_DL_COL, minsize=_DL_MINW)

        # Collect all coloured widgets for hover repainting
        _row_widgets = [row]
        _row_chk_fns = []   # holds (bg_colour) → redraw lambdas for this row

        def _repaint(colour):
            for w in _row_widgets:
                try: w.config(bg=colour)
                except Exception: pass
            for fn in _row_chk_fns:
                try: fn(colour)
                except Exception: pass

        def _enter(_e):
            if not _is_active(): _repaint(_bc("hover"))
        def _leave(_e):
            _repaint(_bc("selected") if _is_active() else bg)

        row.bind("<Enter>", _enter)
        row.bind("<Leave>", _leave)
        row.bind("<Button-1>", lambda _, i=idx: self._row_clicked(i))
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            row.bind(ev, self._on_mwheel)
        row.bind("<Button-2>", self._on_mmb_click)

        # ── Canvas checkbox ───────────────────────────────────────────────────
        chk_v = tk.BooleanVar(value=idx in self._selected)
        # Store in the per-row arrays so toggle_all can reach them
        if idx < len(self._row_chk_vars):
            self._row_chk_vars[idx] = chk_v
        if idx < len(self._row_frames):
            self._row_frames[idx] = row

        def _on_chk(i=idx, v=chk_v):
            if v.get(): self._selected.add(i)
            else:        self._selected.discard(i)
            self._update_dl_count()

        chk_cv = self._make_chk_canvas(row, chk_v, _on_chk, bg,
                                        row_chk_fns=_row_chk_fns)
        chk_cv.grid(row=0, column=_CHK_COL, padx=(8, 4), pady=8)
        chk_cv.bind("<Enter>", _enter)
        chk_cv.bind("<Leave>", _leave)
        _row_widgets.append(chk_cv)

        # Update chk_draws for this index
        if idx < len(self._chk_draws):
            self._chk_draws[idx] = _row_chk_fns

        # ── Data cells via grid ───────────────────────────────────────────────
        def _cell(text, field, anchor, gcol):
            lbl = tk.Label(
                row, text=text,
                font=_FT if field == "name" else _FTS,
                fg=_bc("text") if field == "name" else _bc("text_mid"),
                bg=bg, anchor=anchor, padx=6)
            lbl.grid(row=0, column=gcol, sticky="ew", pady=8)
            lbl.bind("<Enter>", _enter)
            lbl.bind("<Leave>", _leave)
            lbl.bind("<Button-1>", lambda _, i=idx: self._row_clicked(i))
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                lbl.bind(ev, self._on_mwheel)
            _row_widgets.append(lbl)

        _cell((song.get("name")   or "Unknown")[:52], "name",   "w", 1)
        _cell((song.get("artist") or "—")[:28],        "artist", "w", 2)
        _cell((song.get("album")  or "—")[:28],        "album",  "w", 3)
        _cell((song.get("genre")  or "—")[:20],        "genre",  "w", 4)
        _cell(str(song["year"]) if song.get("year") else "—", "year", "center", 5)

        # Progress bar + done label (right side)
        pb = ttk.Progressbar(row, length=80, mode="determinate")
        self._dl_bars[idx] = pb
        done_lbl = tk.Label(row, text="", font=_FTS, fg=_bc("success"), bg=bg)
        self._dl_labels[idx] = done_lbl
        _row_widgets.append(done_lbl)

        # Restore progress bar / done label if download is in progress or done
        if idx in self._dl_bars and self._dl_bars[idx] is not None:
            pass  # pb already placed above

        # Download button
        dl = tk.Label(
            row, text="↓", font=_FTS,
            bg=_bc("accent_dim"), fg=_bc("text"),
            relief="flat", padx=6, pady=2, cursor="hand2")
        dl.bind("<Button-1>", lambda e, i=idx: self._start_download(i))
        dl.bind("<Enter>", lambda e, w=dl: w.config(bg=_bc("accent")))
        dl.bind("<Leave>", lambda e, w=dl: w.config(bg=_bc("accent_dim")))
        dl.grid(row=0, column=_DL_COL, padx=(2, 6), pady=3)
        _row_widgets.append(dl)

        # If this row is the active selection, paint it selected
        if self._active_idx == idx:
            _repaint(_bc("selected"))

        return row

    def _row_clicked(self, idx: int):
        old = self._active_idx
        self._active_idx = idx

        # Deselect old row visually — only if it's currently rendered
        if old is not None and old != idx:
            old_frame = self._virt_rendered.get(old)
            if old_frame is not None:
                oldbg = self._row_bg[old] if old < len(self._row_bg) else _bc("card")
                old_frame.config(bg=oldbg)
                for c in old_frame.winfo_children():
                    try: c.config(bg=oldbg)
                    except Exception: pass

        # Highlight new row — only if it's currently rendered
        new_frame = self._virt_rendered.get(idx)
        if new_frame is not None:
            selbg = _bc("selected")
            new_frame.config(bg=selbg)
            for c in new_frame.winfo_children():
                try: c.config(bg=selbg)
                except Exception: pass

        self._show_info(idx)

    # =========================================================================
    #  SIDEBAR POPULATION
    # =========================================================================

    def _show_info(self, idx: int):
        if idx >= len(self._songs): return
        song = self._songs[idx]
        nd   = song.get("notesData") or {}

        # Charter
        self._charter_lbl.config(text=song.get("charter") or "—")

        # Length + diff badge
        self._length_lbl.config(text=_sm_fmt_ms(song.get("song_length")))
        diff = self._diff_var.get().replace("Any Difficulty", "")
        if diff:
            self._diff_badge.config(
                text=diff,
                bg=_DIFF_COLORS.get(diff, _bc("accent_dim")))
            self._diff_badge.pack(side="right")
        else:
            self._diff_badge.pack_forget()

        # Feature checkmarks
        _FEAT_MAP = {
            "hasSoloSections":    nd.get("hasSoloSections"),
            "hasLyrics":          nd.get("hasLyrics"),
            "hasForcedNotes":     nd.get("hasForcedNotes"),
            "hasTapNotes":        nd.get("hasTapNotes"),
            "hasOpenNotes":       nd.get("hasOpenNotes"),
            "hasVideoBackground": song.get("hasVideoBackground"),
        }
        for key, val in _FEAT_MAP.items():
            icon = self._feat_rows.get(key)
            if icon:
                if val:
                    icon.config(text="✓", fg=_bc("success"))
                else:
                    icon.config(text="✗", fg=_bc("error"))

        # NPS / note count — from notesData
        avg = nd.get("averageNps") or nd.get("avgNps")
        mxn = nd.get("maxNps")
        cnt = nd.get("noteCount")
        self._avg_nps_var.set(f"{avg:.1f}" if avg is not None else "N/A")
        self._max_nps_var.set(str(mxn) if mxn is not None else "—")
        self._note_cnt_var.set(f"{cnt:,}" if cnt is not None else "—")

        # Album art (async)
        art_md5 = song.get("albumArtMd5")
        self._load_album_art(art_md5)

    def _load_album_art(self, md5: str | None):
        """Load album art from Enchor CDN in a background thread."""
        # Reset to placeholder
        self._art_lbl.config(image="", text="Loading art…" if md5 else "No album art",
                             compound="none")
        self._art_image_ref = None

        if not md5 or not _SM_HAS_PIL:
            if not _SM_HAS_PIL and md5:
                self._art_lbl.config(text="(Pillow not installed)")
            return

        url = _SM_ART_URL.format(md5=md5)

        def _fetch():
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "CHSuite/5.0 CHSongManager"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = resp.read()
                img = Image.open(io.BytesIO(data)).convert("RGB")
                # Fit to sidebar width (288px)
                W = 288
                ratio = W / img.width
                H = int(img.height * ratio)
                img = img.resize((W, H), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.after(0, lambda: self._set_art(photo, H))
            except Exception:
                self.after(0, lambda: self._art_lbl.config(
                    image="", text="No album art", compound="none"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _set_art(self, photo, h: int):
        self._art_image_ref = photo
        self._art_frame.config(height=h)
        self._art_lbl.config(image=photo, text="", compound="none")

    # =========================================================================
    #  SELECT ALL / DOWNLOAD
    # =========================================================================

    def _toggle_all(self):
        state = self._chk_all_var.get()
        draws = getattr(self, "_chk_draws", [])
        for i, v in enumerate(self._row_chk_vars):
            if v is None:
                # Row not yet rendered — update _selected directly
                if state: self._selected.add(i)
                else:      self._selected.discard(i)
                continue
            v.set(state)
            if state: self._selected.add(i)
            else:      self._selected.discard(i)
            if i < len(draws):
                row_colour = (_bc("selected") if self._active_idx == i
                              else (self._row_bg[i] if i < len(self._row_bg) else _bc("card")))
                for fn in draws[i]:
                    try: fn(row_colour)
                    except Exception: pass
        # Redraw header checkbox
        self._redraw_hdr_chk()
        self._update_dl_count()

    def _update_dl_count(self):
        n = len(self._selected)
        self._dl_count_var.set(f"{n} selected" if n else "")

    def _batch_download(self):
        if not self._selected:
            messagebox.showinfo("No songs selected",
                                "Tick the checkboxes next to songs to download.",
                                parent=self)
            return
        # Validate the songs directory exactly once before kicking off any
        # threads — avoids a warning dialog appearing for every selected song.
        if not _SM_HAS_REQUESTS:
            messagebox.showerror("Missing dependency",
                                 "Install requests:  pip install requests",
                                 parent=self)
            return
        sdir = self._songs_dir()
        if not sdir:
            messagebox.showwarning("No songs folder",
                                   "Set your Clone Hero songs folder in "
                                   "Settings first.",
                                   parent=self)
            return
        if not os.path.isdir(sdir):
            messagebox.showwarning("Folder not found",
                                   f"Songs folder does not exist:\n{sdir}",
                                   parent=self)
            return
        for idx in sorted(self._selected):
            self._start_download(idx)

    def _info_download(self):
        if self._active_idx is not None:
            self._start_download(self._active_idx)

    def _show_more_menu(self):
        """'···' menu stub — expand as needed."""
        m = tk.Menu(self, tearoff=0,
                    bg=_bc("card"), fg=_bc("text"),
                    activebackground=_bc("accent"),
                    activeforeground=_bc("text"),
                    font=_FTS, bd=0, relief="flat")
        m.add_command(label="Download as .sng",
                      command=lambda: self._info_download())
        m.add_command(label="Copy name to clipboard",
                      command=self._copy_name)
        try:
            x = self._sb.winfo_rootx() + 4
            y = self._sb.winfo_rooty() + self._sb.winfo_height() - 44
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _copy_name(self):
        if self._active_idx is not None and self._active_idx < len(self._songs):
            name = self._songs[self._active_idx].get("name", "")
            self.clipboard_clear()
            self.clipboard_append(name)

    def _dest_path(self, song: dict, songs_dir: str) -> str:
        """Return the canonical destination path for a song (always .sng)."""
        name   = song.get("name")   or "song"
        artist = song.get("artist") or "Unknown Artist"
        chtr   = song.get("charter") or "Unknown"
        dest_name = _sm_safe_name(f"{artist} - {name} ({chtr})")
        return os.path.join(songs_dir, dest_name + ".sng")

    # ── MD5 index for fast already-downloaded checks ──────────────────────────
    # Populated on first use, invalidated whenever a download completes.
    _md5_index:      set  = None   # set of md5 strings found in songs_dir
    _md5_index_dir:  str  = ""     # which dir was last scanned
    _md5_index_lock: object = None  # threading.Lock, created lazily

    def _get_md5_index(self, songs_dir: str) -> set:
        """
        Return (and cache) the set of MD5 hashes for every .sng in songs_dir.
        Re-scans whenever the songs dir changes or is explicitly invalidated.
        """
        if self._md5_index_lock is None:
            import threading as _t
            self.__class__._md5_index_lock = _t.Lock()
        with self._md5_index_lock:
            if self._md5_index is not None and self._md5_index_dir == songs_dir:
                return self._md5_index
            index = set()
            try:
                import zipfile
                for fname in os.listdir(songs_dir):
                    if not fname.lower().endswith(".sng"):
                        continue
                    fpath = os.path.join(songs_dir, fname)
                    # .sng files are zip archives; try to read the MD5 from
                    # the archive comment or from a known metadata entry
                    try:
                        with zipfile.ZipFile(fpath, "r") as z:
                            # Bridge stores md5 in the zip comment
                            comment = (z.comment or b"").decode("utf-8", errors="ignore").strip()
                            if comment and len(comment) == 32:
                                index.add(comment.lower())
                                continue
                            # Fallback: try reading "song.ini" or "notes.chart"
                            # for any identifying metadata (best-effort)
                    except Exception:
                        pass
                    # Last resort: derive a key from the filename itself
                    # (covers songs downloaded by CHSuite with standard naming)
                    stem = os.path.splitext(fname)[0].lower()
                    index.add(f"__file__{stem}")
            except Exception:
                pass
            self.__class__._md5_index     = index
            self.__class__._md5_index_dir = songs_dir
            return index

    def _invalidate_md5_index(self):
        """Call after a successful download so next check rescans the folder."""
        if self._md5_index_lock is None:
            return
        with self._md5_index_lock:
            self.__class__._md5_index = None

    def _is_already_downloaded(self, song: dict, songs_dir: str) -> bool:
        """
        Multi-layer check:
        1. Does the canonical dest path already exist as a file?
        2. Is the song's MD5 in our scanned index (covers renamed files)?
        3. Does any .sng in the dir contain artist+name (fuzzy filename match)?
        """
        if not songs_dir or not os.path.isdir(songs_dir):
            return False

        # Layer 1 – exact canonical filename
        dest = self._dest_path(song, songs_dir)
        if os.path.isfile(dest):
            return True

        # Layer 2 – MD5 match via index
        md5 = (song.get("md5") or "").lower()
        if md5:
            index = self._get_md5_index(songs_dir)
            if md5 in index:
                return True

        # Layer 3 – fuzzy filename scan
        name   = (song.get("name")   or "").lower().strip()
        artist = (song.get("artist") or "").lower().strip()
        if name and artist:
            try:
                for fname in os.listdir(songs_dir):
                    if not fname.lower().endswith(".sng"):
                        continue
                    fl = fname.lower()
                    if name[:20] in fl and artist[:12] in fl:
                        return True
            except Exception:
                pass

        return False

    def _start_download(self, idx: int):
        t = self._dl_threads.get(idx)
        if t and t.is_alive(): return
        if not _SM_HAS_REQUESTS:
            messagebox.showerror("Missing dependency",
                                 "Install requests:  pip install requests",
                                 parent=self)
            return
        sdir = self._songs_dir()
        if not sdir:
            messagebox.showwarning("No songs folder",
                                   "Set your Clone Hero songs folder in Settings first.",
                                   parent=self)
            return
        if not os.path.isdir(sdir):
            messagebox.showwarning("Folder not found",
                                   f"Songs folder does not exist:\n{sdir}",
                                   parent=self)
            return
        song = self._songs[idx]
        if self._is_already_downloaded(song, sdir):
            self.after(0, self._row_done, idx, True, "✓ Already here")
            self._status(f"Already downloaded: {song.get('name', '')}", _bc("success"))
            return
        t = threading.Thread(target=self._worker,
                             args=(idx, song, sdir), daemon=True)
        self._dl_threads[idx] = t
        t.start()

    # =========================================================================
    #  DOWNLOAD WORKER
    # =========================================================================

    def _worker(self, idx: int, song: dict, songs_dir: str):
        md5  = song.get("md5", "")
        name = song.get("name") or f"song_{idx}"
        dest = self._dest_path(song, songs_dir)

        if not md5:
            self.after(0, self._row_done, idx, False, "✗ No MD5")
            self.after(0, self._status, f"No download link: {name}", _bc("error"))
            return

        url = f"{_SM_FILES_URL}/{md5}.sng"
        self.after(0, self._row_pb_show, idx)
        self.after(0, self._queue_add, idx, name)
        self.after(0, self._status, f"Downloading: {name}", _bc("warn"))

        try:
            with _sm_requests.get(
                    url, stream=True, timeout=30,
                    headers={"User-Agent": "CHSuite/5.0 CHSongManager"}) as r:
                r.raise_for_status()
                total, downloaded = int(r.headers.get("content-length", 0)), 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                pct = downloaded * 100 // total
                                self.after(0, self._row_pb_set, idx, pct)
                                self.after(0, self._queue_update, idx, pct, None)

            # Optionally strip video
            skip_vid = not self._cfg.get("sm_skip_video", False)
            if skip_vid and song.get("hasVideoBackground"):
                self.after(0, self._status, f"Stripping video BG: {name}",
                           _bc("text_dim"))
                self._strip_video_from_sng(dest)

            self._invalidate_md5_index()
            self.after(0, self._queue_update, idx, 100, True)
            self.after(0, self._row_done, idx, True, "✓ Done")
            self.after(0, self._status, f"Installed: {name}", _bc("success"))
        except Exception as exc:
            try:
                if os.path.isfile(dest): os.remove(dest)
            except Exception: pass
            self.after(0, self._queue_update, idx, -1, False)
            self.after(0, self._row_done, idx, False, f"✗ {str(exc)[:38]}")
            self.after(0, self._status, f"Failed: {name} — {exc}", _bc("error"))

    @staticmethod
    def _strip_video_from_sng(path: str):
        import zipfile
        _VIDEO_EXTS = {'.mp4', '.webm', '.avi', '.mkv', '.mov', '.ogv', '.m4v'}
        tmp = path + ".novid.tmp"
        try:
            with zipfile.ZipFile(path, 'r') as zin:
                members = [m for m in zin.infolist()
                           if os.path.splitext(m.filename)[1].lower()
                           not in _VIDEO_EXTS]
                if len(members) == len(zin.infolist()): return
                with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                    for info in members:
                        zout.writestr(info, zin.read(info.filename))
            os.replace(tmp, path)
        except Exception:
            try:
                if os.path.isfile(tmp): os.remove(tmp)
            except Exception: pass

    # ── Row progress helpers ──────────────────────────────────────────────────

    def _row_pb_show(self, idx):
        pb = self._dl_bars.get(idx)
        try:
            if pb and pb.winfo_exists() and not pb.winfo_ismapped():
                pb.pack(side="right", padx=(0, 4))
        except Exception:
            pass

    def _row_pb_set(self, idx, pct):
        pb = self._dl_bars.get(idx)
        try:
            if pb and pb.winfo_exists():
                pb["value"] = pct
        except Exception:
            pass

    def _row_done(self, idx, success, label):
        pb = self._dl_bars.get(idx)
        try:
            if pb and pb.winfo_exists() and pb.winfo_ismapped():
                pb.pack_forget()
        except Exception:
            pass
        lbl = self._dl_labels.get(idx)
        try:
            if lbl and lbl.winfo_exists():
                lbl.config(text=label,
                           fg=_bc("success") if success else _bc("error"))
                lbl.pack(side="right", padx=(0, 4))
        except Exception:
            pass

    # =========================================================================
    #  HELPERS
    # =========================================================================

    def _status(self, msg: str, color: str = None):
        try:
            self._status_var.set(msg)
            if color:
                self._status_lbl.config(fg=color)
        except Exception:
            pass

    def _mk_btn(self, parent, text, command, bg, hover_bg,
                font=None, padx=12, pady=5):
        font = font or _FT
        btn = tk.Button(
            parent, text=text, command=command,
            font=font, bg=bg, fg=_bc("text"),
            activebackground=hover_bg,
            activeforeground=_bc("text"),
            relief="flat", padx=padx, pady=pady,
            cursor="hand2", bd=0)
        btn.bind("<Enter>", lambda _: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda _: btn.config(bg=bg))
        return btn



# ── CHPreScanner — songcache.bin builder ────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
#  CHPRESCANNER — songcache.bin builder (integrated, no separate window)
# ──────────────────────────────────────────────────────────────────────────────
import struct
import hashlib

_PS_MAGIC_HEADER = bytes([
    0x7b, 0x25, 0x35, 0x01, 0x52, 0x19, 0x0b, 0x1b,
    0x72, 0x2d, 0x9e, 0x9b, 0x08, 0x05, 0x88, 0xb7
])
_PS_TIMESTAMP_BYTES = bytes([0xb7, 0xa6, 0x2a, 0x58])
_PS_MAX_DIFF = 8
_PS_NO_DIFF  = 0xFF
_PS_FILETIME_EPOCH = datetime.datetime(1601, 1, 1)


def _ps_now_filetime() -> bytes:
    delta = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - _PS_FILETIME_EPOCH
    ticks = int(delta.total_seconds() * 10_000_000)
    return struct.pack('<Q', ticks)


def _ps_make_record_hash(path: str, song_name: str) -> bytes:
    return hashlib.md5((path + '\x00' + song_name).encode('utf-8')).digest()


def _ps_lp_str(s: str) -> bytes:
    enc = s.encode('utf-8')
    if len(enc) > 255:
        enc = enc[:255]
    return bytes([len(enc)]) + enc


def _ps_parse_ini(ini_path: str) -> dict:
    meta = {
        'name': '', 'artist': '', 'album': '', 'genre': '',
        'year': '', 'charter': 'Unknown', 'lyrics': False,
        'song_length': 0,
        'diff_guitar': _PS_NO_DIFF, 'diff_guitarghl': _PS_NO_DIFF,
        'diff_bass': _PS_NO_DIFF,   'diff_bassghl': _PS_NO_DIFF,
        'diff_rhythm': _PS_NO_DIFF, 'diff_drums': _PS_NO_DIFF,
        'diff_keys': _PS_NO_DIFF,
    }
    try:
        with open(ini_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        if not content.lstrip().startswith('['):
            content = '[song]\n' + content
        parser = configparser.RawConfigParser()
        parser.read_string(content)
        sec = parser.sections()[0] if parser.sections() else 'song'

        def gi(key, default=''):
            try:
                return parser.get(sec, key).strip().strip('"')
            except Exception:
                return default

        def gi_int(key, default=-1):
            try:
                return int(gi(key, str(default)))
            except Exception:
                return default

        def clamp(v):
            return _PS_NO_DIFF if v < 0 else min(v, _PS_MAX_DIFF)

        meta['name']    = gi('name')    or gi('Name',    '')
        meta['artist']  = gi('artist')  or gi('Artist',  '')
        meta['album']   = gi('album')   or gi('Album',   '')
        meta['genre']   = gi('genre')   or gi('Genre',   '')
        meta['charter'] = gi('charter') or gi('Charter', 'Unknown')
        yr_raw = gi('year') or gi('Year', '')
        yr_d   = re.sub(r'\D', '', yr_raw)
        meta['year']    = yr_d[:4] if yr_d else ''
        lyr = gi('lyrics', '0').lower()
        meta['lyrics']  = lyr in ('1', 'true', 'yes')
        meta['song_length'] = max(gi_int('song_length', 0), 0)
        meta['diff_guitar']    = clamp(gi_int('diff_guitar',    -1))
        meta['diff_guitarghl'] = clamp(gi_int('diff_guitarghl', -1))
        meta['diff_bass']      = clamp(gi_int('diff_bass',      -1))
        meta['diff_bassghl']   = clamp(gi_int('diff_bassghl',   -1))
        meta['diff_rhythm']    = clamp(gi_int('diff_rhythm',    -1))
        meta['diff_drums']     = clamp(gi_int('diff_drums',     -1))
        meta['diff_keys']      = clamp(gi_int('diff_keys',      -1))
    except Exception:
        pass
    return meta


def _ps_build_difficulty_block(meta: dict) -> bytes:
    g, b, ry = meta['diff_guitar'], meta['diff_bass'], meta['diff_rhythm']
    d, k      = meta['diff_drums'], meta['diff_keys']
    gg, gb    = meta['diff_guitarghl'], meta['diff_bassghl']
    has_rhythm = ry != _PS_NO_DIFF
    has_keys   = k  != _PS_NO_DIFF
    has_ghl_g  = gg != _PS_NO_DIFF
    has_ghl_b  = gb != _PS_NO_DIFF
    has_ghl    = has_ghl_g or has_ghl_b
    g0b1 = 0x0f if has_rhythm else 0x00
    if has_ghl_b and has_ghl_g:
        g0b2 = 0xff
    elif has_ghl_b:
        g0b2 = 0x88
    elif has_keys:
        g0b2 = 0x0f
    else:
        g0b2 = 0x00
    g0b3 = 0xff if has_keys else (0x0f if has_ghl else 0x00)
    g1b1 = 0x0f if (has_keys and has_ghl) else 0x00
    return bytes([
        0xff, g0b1, g0b2, g0b3,
        0xf0, g1b1, 0x00, 0x00,
        0x01 if meta['lyrics'] else 0x00, _PS_NO_DIFF, g, ry,
        0x00, b, d, d,
        k, gg, gb, 0xff,
    ])


def _ps_find_chart(song_dir: str):
    for fname in ('notes.chart', 'notes.mid'):
        p = os.path.join(song_dir, fname)
        if os.path.isfile(p):
            return fname, p
    return None, None


def _ps_scan_songs(root_dir: str, max_depth: int = 5, progress_cb=None):
    """
    Walk up to max_depth levels looking for Clone Hero song folders.
    Calls progress_cb(count) whenever a new song is discovered (for live counting).
    Yields (song_dir, chart_fname, chart_path, meta) tuples.
    """
    root_dir = os.path.abspath(root_dir)
    count = [0]

    def _walk(directory, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name.lower())
        except PermissionError:
            return
        fname, fpath = _ps_find_chart(directory)
        if fname:
            ini_path = os.path.join(directory, 'song.ini')
            meta = _ps_parse_ini(ini_path) if os.path.isfile(ini_path) else {}
            if not meta.get('name'):
                meta['name'] = os.path.basename(directory)
            count[0] += 1
            if progress_cb:
                progress_cb(count[0])
            yield directory, fname, fpath, meta
        else:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    yield from _walk(entry.path, depth + 1)

    yield from _walk(root_dir, 0)


def _ps_build_cache(songs: list, output_path: str, write_cb=None) -> int:
    """Build songcache.bin from list of (song_dir, chart_fname, chart_path, meta)."""
    import io as _io

    song_names, artist_names, album_names  = [], [], []
    genre_names, year_names, charter_names = [], [], []

    def _add(table, value):
        value = (value or '').strip()
        if value not in table:
            table.append(value)
        return table.index(value)

    s_idx, a_idx, al_idx, g_idx, y_idx, c_idx = [], [], [], [], [], []
    for (song_dir, _, _, meta) in songs:
        name = meta.get('name') or os.path.basename(song_dir)
        s_idx.append(_add(song_names,    name))
        a_idx.append(_add(artist_names,  meta.get('artist', '') or 'Unknown Artist'))
        al_idx.append(_add(album_names,  meta.get('album',  '') or ''))
        g_idx.append(_add(genre_names,   meta.get('genre',  '') or ''))
        y_idx.append(_add(year_names,    meta.get('year',   '') or ''))
        c_idx.append(_add(charter_names, meta.get('charter','') or 'Unknown'))

    def blob(lst):
        return b''.join(_ps_lp_str(s) for s in lst)

    def sec_hdr(sid, count):
        return bytes([sid]) + struct.pack('<H', count) + b'\x00\x00'

    out = _io.BytesIO()
    out.write(_PS_MAGIC_HEADER)
    out.write(_PS_TIMESTAMP_BYTES)
    out.write(bytes([0x00]))
    out.write(struct.pack('<H', len(song_names)))
    out.write(b'\x00\x00')
    out.write(blob(song_names))
    out.write(blob(artist_names))
    out.write(sec_hdr(0x02, len(album_names)));   out.write(blob(album_names))
    out.write(sec_hdr(0x03, len(genre_names)));   out.write(blob(genre_names))
    out.write(sec_hdr(0x04, len(year_names)));    out.write(blob(year_names))
    out.write(sec_hdr(0x05, len(charter_names))); out.write(blob(charter_names))

    for idx, (song_dir, chart_fname, chart_path, meta) in enumerate(songs):
        ci_         = c_idx[idx]
        charter_str = charter_names[ci_] if ci_ < len(charter_names) else 'Unknown'
        rec_hash    = _ps_make_record_hash(song_dir, song_names[s_idx[idx]])

        out.write(_ps_lp_str(charter_str))
        out.write(rec_hash)

        path_enc = song_dir.replace('/', '\\').encode('utf-8', errors='replace')
        if len(path_enc) > 255:
            path_enc = path_enc[:255]
        out.write(bytes([len(path_enc)]))
        out.write(path_enc)

        ts = _ps_now_filetime()
        out.write(ts); out.write(ts)
        out.write(_ps_lp_str(chart_fname))
        out.write(struct.pack('<H', 0x0001))
        out.write(struct.pack('<I', s_idx[idx]))
        out.write(struct.pack('<I', len(song_names) + a_idx[idx]))
        out.write(struct.pack('<I', len(song_names) + len(artist_names) + al_idx[idx]))
        out.write(struct.pack('<I', g_idx[idx]))
        out.write(struct.pack('<I', y_idx[idx]))
        out.write(struct.pack('<I', ci_))
        out.write(struct.pack('<I', 0x0b))
        out.write(_ps_build_difficulty_block(meta))

        chart_size  = os.path.getsize(chart_path) if os.path.isfile(chart_path) else 0
        duration_ms = meta.get('song_length', 0)
        out.write(b'\xff\x00')
        out.write(struct.pack('<I', chart_size))
        out.write(bytes([0x02, 0x63, 0x68]))
        out.write(struct.pack('<H', idx % 256))
        out.write(struct.pack('<I', idx))
        out.write(b'\x00\x00\x00')
        out.write(struct.pack('<I', duration_ms))
        out.write(ts)
        out.write(rec_hash)

        if write_cb:
            write_cb(idx + 1)

    data = out.getvalue()
    with open(output_path, 'wb') as f:
        f.write(data)
    return len(songs)




# ─────────────────────────────────────────────────────────────────────────────
class CHSongManagerMixin:
    """
    CHSuite mixin: SongManager page + embedded pre-scanner controls.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

    def _build_page_songmanager(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["songmanager"] = page

        self._song_manager_tab = CHSongManagerTab(
            page,
            cfg=self._cfg,
            save_cfg_fn=lambda: _save_json(CONFIG_FILE, self._cfg),
        )
        self._song_manager_tab.pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 7 — GAME MANAGER
    # ══════════════════════════════════════════════════════════════════════════
    def _ps_browse(self):
        folder = filedialog.askdirectory(title="Select Songs Root Folder", parent=self)
        if folder:
            self._ps_folder_var.set(folder)
            self._ps_count_var.set("Folder selected. Click ⚡ Scan to begin.")
            self._ps_count_lbl.config(fg=C["text_dim"])

    def _ps_start_scan(self):
        if self._ps_scanning:
            return
        folder = self._ps_folder_var.get().strip()
        if not folder:
            messagebox.showwarning("No Folder",
                "Please browse for a songs folder first.", parent=self)
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Invalid Folder",
                f"Folder not found:\n{folder}", parent=self)
            return
        self._ps_scanning = True
        self._ps_scan_btn.set_state(False)
        self._ps_progress.config(mode="indeterminate")
        self._ps_progress.pack(fill="x", pady=(4, 0))
        self._ps_progress.start(12)
        self._ps_count_lbl.config(fg=C["text_dim"])
        self._ps_count_var.set("Discovering songs…  0 found")
        threading.Thread(target=self._ps_do_scan, args=(folder,), daemon=True).start()

    def _ps_do_scan(self, folder: str):
        try:
            songs = []

            def on_found(count):
                label = f"Discovering…  {count} song{'s' if count != 1 else ''} found so far…"
                self.after(0, lambda c=label: self._ps_count_var.set(c))

            for item in _ps_scan_songs(folder, max_depth=5, progress_cb=on_found):
                songs.append(item)

            total = len(songs)
            if total == 0:
                self.after(0, lambda: self._ps_finish(
                    False, "No songs found (no notes.chart / notes.mid files)."))
                return

            self.after(0, lambda t=total: self._ps_count_var.set(
                f"Building cache for {t} song{'s' if t != 1 else ''}…"))

            # Switch progress bar to determinate for the write phase
            self.after(0, lambda t=total: (
                self._ps_progress.stop(),
                self._ps_progress.config(mode="determinate", maximum=t, value=0)
            ))

            def on_written(n):
                self.after(0, lambda c=n, t=total: (
                    self._ps_progress_var.set(c),
                    self._ps_count_var.set(
                        f"Writing cache…  {c} / {t} song{'s' if t != 1 else ''}")
                ))

            output = os.path.join(folder, "songcache.bin")
            _ps_build_cache(songs, output, write_cb=on_written)

            kb  = os.path.getsize(output) / 1024
            msg = f"✅  {total} songs cached  •  {kb:.1f} KB  →  {output}"
            self.after(0, lambda m=msg: self._ps_finish(True, m))

        except Exception as exc:
            self.after(0, lambda e=str(exc): self._ps_finish(False, f"Error: {e}"))

    def _ps_finish(self, success: bool, msg: str):
        self._ps_scanning = False
        self._ps_scan_btn.set_state(True)
        self._ps_progress.stop()
        self._ps_progress.pack_forget()
        self._ps_count_lbl.config(fg=C["success"] if success else C["error"])
        self._ps_count_var.set(msg)
        if not success:
            messagebox.showerror("Pre-Scan Failed", msg, parent=self)
        self.after(10000, lambda: (
            self._ps_count_lbl.config(fg=C["text_dim"])
        ) if not self._ps_scanning else None)

    # ── Reset to Default ──────────────────────────────────────────────────────
