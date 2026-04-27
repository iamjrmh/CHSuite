"""
CHNameGen.py — Clone Hero name-tag generator (CHNameGen)
========================================================
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
#  SECTION 2 — NAME GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

__namegen_version__ = "1.1.1"
GITHUB_REPO_OWNER   = "iamjrmh"
GITHUB_REPO_NAME    = "CHSuite"
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







# ─────────────────────────────────────────────────────────────────────────────
class CHNameGenMixin:
    """
    CHSuite mixin: methods that build and operate the CHNameGen page.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

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
        tk.Label(left_nav, text="MODE", font=("Lato", 7, "bold"),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(anchor="w", padx=16)
        _sep(left_nav, bg=C["border"]).pack(fill="x", padx=16, pady=(4, 0))

        ng_items = [
            ("gradient",   "◈", "Gradient"),
            ("individual", "✦", "Per-Letter"),
        ]
        for pid, icon, label in ng_items:
            btn_frame = tk.Frame(left_nav, bg=C["sidebar"], cursor="hand2")
            btn_frame.pack(fill="x")
            icon_lbl = tk.Label(btn_frame, text=icon, font=("Lato", 11),
                                width=2, anchor="center",
                                bg=C["sidebar"], fg=C["text_dim"])
            icon_lbl.pack(side="left", padx=(14, 0), pady=10)
            text_lbl = tk.Label(btn_frame, text=label, font=("Lato", 10),
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
                icon_lbl.config(bg=C["accent"], fg="white", font=("Lato", 11, "bold"))
                text_lbl.config(bg=C["accent"], fg="white", font=("Lato", 10, "bold"))
            else:
                frame.config(bg=C["sidebar"])
                icon_lbl.config(bg=C["sidebar"], fg=C["text_dim"], font=("Lato", 11))
                text_lbl.config(bg=C["sidebar"], fg=C["text_mid"], font=("Lato", 10))

    def _ng_section(self, parent, title):
        """A labelled section card."""
        wrap = tk.Frame(parent, bg=C["bg"]); wrap.pack(fill="x", pady=(0, 12))
        tk.Label(wrap, text=title, font=("Lato", 8, "bold"),
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
        e = tk.Entry(row, textvariable=var); e.pack(side="left", fill="x", expand=True, padx=4)
        if with_picker:
            RoundedButton(row, "Pick", lambda v=var: self._pick_color(v),
                          bg_color=C["border"], hover_color=C["hover"],
                          text_color=C["text"], height=34, radius=12,
                          text_font=FTS, canvas_bg=C["card"],
                          width=58).pack(side="left", padx=2)
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
            canvas.yview_scroll(_scroll_units(event), "units")

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
                 font=("Lato", 16, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w", pady=(0,16))

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
        self._grad_name_entry = tk.Entry(name_card, font=("Lato", 11))
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
                      C["accent"], C["accent_dim"], height=48).pack(side="left", padx=(0,8), fill="x", expand=True)
        RoundedButton(btn_row, "Export to profiles.ini", self._on_grad_export,
                      C["border"], C["hover"], height=48).pack(side="left", fill="x", expand=True)

        # Output
        out_card = self._ng_section(frame, "OUTPUT")
        self._grad_output = tk.Text(out_card, height=3, state=tk.DISABLED,
                                    wrap="word", relief="flat",
                                    bg=C["card2"], fg=C["text"], font=FTM,
                                    insertbackground=C["text"])
        self._grad_output.pack(fill="x", pady=(0,8))
        copy_btn = RoundedButton(out_card, "Copy to Clipboard",
                                 lambda: self._copy_text(self._grad_output),
                                 bg_color=C["border"], hover_color=C["hover"],
                                 text_color=C["text"], height=40, radius=16,
                                 text_font=FTS, canvas_bg=C["card"],
                                 width=150)
        copy_btn.pack(anchor="e")

        prev_card = self._ng_section(frame, "PREVIEW")
        self._grad_preview = tk.Text(prev_card, height=4, state=tk.DISABLED,
                                     wrap="word", relief="flat",
                                     bg=C["bg"], fg=C["text"], font=("Lato", 16))
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
            font_tuple = ("Lato", base_fs, " ".join(font_styles) if font_styles else "normal")
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
                 font=("Lato", 16, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w", pady=(0,16))

        self._indiv_size_var  = tk.StringVar()
        self._indiv_space_var = tk.StringVar()

        # Name entry
        name_card = self._ng_section(frame, "NAME")
        name_row = tk.Frame(name_card, bg=C["card"]); name_row.pack(fill="x")
        self._indiv_name_entry = tk.Entry(name_row, font=("Lato", 11))
        self._indiv_name_entry.pack(side="left", fill="x", expand=True)
        RoundedButton(name_row, "Update Letters", self._update_individual_letters,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="white", height=40, radius=16,
                      text_font=FTB, canvas_bg=C["card"],
                      width=130).pack(side="right", padx=(8, 0))

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
        RoundedButton(out_card, "Copy to Clipboard",
                      lambda: self._copy_text(self._indiv_output),
                      bg_color=C["border"], hover_color=C["hover"],
                      text_color=C["text"], height=40, radius=16,
                      text_font=FTS, canvas_bg=C["card"],
                      width=170).pack(anchor="e")

        prev_card = self._ng_section(frame, "PREVIEW")
        self._indiv_preview = tk.Text(prev_card, height=3, state=tk.DISABLED,
                                      wrap="word", relief="flat",
                                      bg=C["bg"], fg=C["text"], font=("Lato", 16))
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
                     font=("Lato", 11, "bold"), fg=C["accent2"], bg=C["card"]).pack(side="left", padx=4)
            color_var = tk.StringVar(value="#FFFFFF")
            color_swatch = tk.Label(row, bg="#FFFFFF", width=2)
            color_swatch.pack(side="left", padx=2)
            e = tk.Entry(row, textvariable=color_var, width=9)
            e.pack(side="left", padx=2)
            def _update_swatch(sv=color_var, sw=color_swatch):
                try: sw.config(bg=sv.get())
                except Exception: pass
            color_var.trace_add("write", lambda *_, sv=color_var, sw=color_swatch: _update_swatch(sv, sw))
            RoundedButton(row, "Pick",
                          lambda cv=color_var: self._pick_color(cv),
                          bg_color=C["border"], hover_color=C["hover"],
                          text_color=C["text"], height=34, radius=12,
                          text_font=FTS, canvas_bg=C["card"],
                          width=58).pack(side="left", padx=2)
            bold_var = tk.BooleanVar(); italic_var = tk.BooleanVar()
            ul_var   = tk.BooleanVar(); str_var    = tk.BooleanVar()
            for txt, var in [("B", bold_var),("I", italic_var),("U", ul_var),("S", str_var)]:
                tk.Checkbutton(row, text=txt, variable=var, width=2,
                               bg=C["card"], fg=C["text"], selectcolor=C["bg"],
                               activebackground=C["card"],
                               font=("Lato", 9, "bold"), relief="flat").pack(side="left", padx=2)
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
                    font=("Lato", base_fs, " ".join(font_styles) if font_styles else "normal"))
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
        # ── 1. Auto-locate profiles.ini ───────────────────────────────────────
        if _IS_MAC:
            auto_path = Path.home() / "Clone Hero" / "profiles.ini"
        elif _IS_LINUX:
            auto_path = Path.home() / "Clone Hero" / "profiles.ini"
        else:  # Windows
            # Portable install: PlayerData lives next to Clone Hero_Data in the
            # game folder.  Check that first; fall back to the typical Documents
            # location if PlayerData isn't present.
            _install_dir = (self._cfg.get("ch_default_install", "")
                            or self._cfg.get("ch_install_dir", ""))
            if _install_dir and (Path(_install_dir) / "PlayerData").is_dir():
                auto_path = Path(_install_dir) / "PlayerData" / "profiles.ini"
            else:
                auto_path = Path.home() / "Documents" / "Clone Hero" / "profiles.ini"

        if auto_path.exists():
            filepath = auto_path
        else:
            folder = filedialog.askdirectory(
                title="Locate your Clone Hero folder (contains profiles.ini)")
            if not folder:
                return
            filepath = Path(folder) / "profiles.ini"

        # ── 2. Parse Clone Hero's INI-style profiles.ini ─────────
        def _parse_profiles_ini(path):
            """Parse profiles.ini into a list of (section_name, [raw_lines]) tuples.
            Clone Hero uses standard INI format:
                [profile0]
                key = value
            Every raw line is preserved so the file can be written back with
            the minimum possible diff (only player_name changes)."""
            sections = []
            current  = None
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except Exception:
                return sections
            for line in text.splitlines(keepends=True):
                stripped = line.strip()
                if (stripped.startswith("[") and stripped.endswith("]")):
                    inner = stripped[1:-1]
                    if inner.startswith("profile") and inner[7:].isdigit():
                        current = [line]
                        sections.append((inner, current))
                        continue
                if current is not None:
                    current.append(line)
            return sections

        def _get_player_name(raw_lines):
            for line in raw_lines:
                stripped = line.strip()
                if stripped.startswith("player_name"):
                    idx = stripped.find("=")
                    if idx != -1:
                        return stripped[idx + 1:].strip().strip('"')
            return ""

        sections = _parse_profiles_ini(filepath)
        if not sections:
            # File doesn't exist yet or has no recognised [profileN] sections.
            # Create a minimal one rather than silently overwriting anything.
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"[profile0]\nplayer_name = {name_tagged}\n")
                messagebox.showinfo("Exported",
                    f"Created profiles.ini at:\n{filepath}\nwith your name in profile0.",
                    parent=self)
            except Exception as e:
                messagebox.showerror("Export Error", str(e), parent=self)
            return

        # ── 3. Ask the user which profile to replace ──────────────────────────
        import re as _re
        def _plain(name):
            """Strip <color=#...>...</color> tags, returning plain readable text."""
            return _re.sub(r'<color=[^>]*>|</color>', '', name)

        profile_labels = []
        for sec_name, raw_lines in sections:
            pname = _get_player_name(raw_lines)
            label = _plain(pname) if pname else sec_name
            profile_labels.append(label)
        # The index one past the last existing section is the "create new" slot.
        _NEW_PROFILE_IDX = len(sections)
        _new_profile_key = f"profile{_NEW_PROFILE_IDX}"

        dlg = tk.Toplevel(self)
        dlg.title("Replace Profile Name")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=C["bg"])

        tk.Label(dlg, text="Choose which profile to update:",
                 font=("Lato", 12, "bold"), fg=C["text"], bg=C["bg"]
                 ).pack(padx=20, pady=(16, 8))

        selected_idx = tk.IntVar(value=0)
        for i, lbl in enumerate(profile_labels):
            tk.Radiobutton(dlg, text=lbl, variable=selected_idx, value=i,
                           font=("Lato", 11), fg=C["text"], bg=C["bg"],
                           selectcolor=C.get("card", C["bg"]),
                           activebackground=C["bg"], activeforeground=C["text"]
                           ).pack(anchor="w", padx=32)

        # Always offer a "create new profile" option at the bottom
        tk.Radiobutton(dlg,
                       text=f"➕  Create new profile ({_new_profile_key})",
                       variable=selected_idx, value=_NEW_PROFILE_IDX,
                       font=("Lato", 11), fg=C.get("accent", C["text"]),
                       bg=C["bg"], selectcolor=C.get("card", C["bg"]),
                       activebackground=C["bg"], activeforeground=C["text"]
                       ).pack(anchor="w", padx=32, pady=(6, 0))

        btn_row = tk.Frame(dlg, bg=C["bg"])
        btn_row.pack(pady=(12, 16), padx=20, fill="x")

        # action[0]: 'replace' | 'delete' | None
        action = [None]

        def _confirm():
            action[0] = "replace"
            dlg.destroy()

        def _delete():
            action[0] = "delete"
            dlg.destroy()

        # Disable Delete when 'Create new' radio is active
        _del_btn_ref = [None]
        def _on_radio_change(*_):
            if _del_btn_ref[0] is None:
                return
            is_new = selected_idx.get() == _NEW_PROFILE_IDX
            try:
                _del_btn_ref[0].set_state("disabled" if is_new else "normal")
            except Exception:
                pass
        selected_idx.trace_add("write", _on_radio_change)

        RoundedButton(btn_row, "Replace", _confirm,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color=C["text"], height=36, radius=14,
                      text_font=("Lato", 10, "bold"),
                      canvas_bg=C["bg"], width=110
                      ).pack(side="right", padx=(8, 0))
        RoundedButton(btn_row, "Cancel", dlg.destroy,
                      bg_color=C["card"], hover_color=C["hover"],
                      text_color=C["text_mid"], height=36, radius=14,
                      text_font=("Lato", 10, "bold"),
                      canvas_bg=C["bg"], width=110
                      ).pack(side="right")
        _del_btn = RoundedButton(btn_row, "🗑  Delete", _delete,
                      bg_color=C.get("error", "#ef4444"), hover_color="#dc2626",
                      text_color="white", height=36, radius=14,
                      text_font=("Lato", 10, "bold"),
                      canvas_bg=C["bg"], width=110
                      )
        _del_btn.pack(side="left")
        _del_btn_ref[0] = _del_btn

        self.wait_window(dlg)
        if action[0] is None:
            return

        chosen = selected_idx.get()

        # Handle delete action
        if action[0] == "delete":
            if len(sections) <= 1:
                messagebox.showwarning("Cannot Delete",
                    "profiles.ini must keep at least one profile.",
                    parent=self)
                return
            del_name = profile_labels[chosen]
            if not messagebox.askyesno("Delete Profile",
                    f'Delete profile "{del_name}" from profiles.ini?\n\nThis cannot be undone.',
                    parent=self):
                return
            del sections[chosen]
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    for _, lines in sections:
                        f.writelines(lines)
                messagebox.showinfo("Deleted",
                    f'Removed profile "{del_name}" from:\n{filepath}',
                    parent=self)
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to save profiles.ini:\n{e}",
                                     parent=self)
            return

        # ── 4. Replace player_name in the chosen section, write back ──────────
        def _replace_player_name(raw_lines, new_name):
            out = []
            replaced = False
            for line in raw_lines:
                stripped = line.strip()
                if not replaced and stripped.startswith("player_name"):
                    sep = "\r\n" if line.endswith("\r\n") else "\n"
                    out.append(f"player_name = {new_name}{sep}")
                    replaced = True
                else:
                    out.append(line)
            if not replaced:  # key didn't exist — append it
                out.append(f"player_name = {new_name}\n")
            return out

        # If the user chose "Create new profile", append a fresh section
        if chosen == _NEW_PROFILE_IDX:
            _default_fields = (
                "default_sample_velocity = 80\n"
                "dynamics_threshold = 100\n"
                "midi_device_id = -1\n"
                "color_profile_name = DefaultColors\n"
                "highway_name = default\n"
                "highway_length = 100\n"
                "tilt_activation = 1\n"
                "note_speed = 7\n"
            )
            sections.append((_new_profile_key, [
                f"[{_new_profile_key}]\n",
                *_default_fields.splitlines(keepends=True),
                f"player_name = {name_tagged}\n",
            ]))
            profile_labels.append(_new_profile_key)
        else:
            sec_name, raw_lines = sections[chosen]
            sections[chosen] = (sec_name, _replace_player_name(raw_lines, name_tagged))

        # Reconstruct and write
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                for _, lines in sections:
                    f.writelines(lines)
            display_name = profile_labels[chosen]
            messagebox.showinfo("Exported",
                f"Updated player_name in profile \"{display_name}\":\n{filepath}",
                parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save profiles.ini:\n{e}",
                                 parent=self)

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 3 — NOTEGEN (CHNoteGen)
    # ══════════════════════════════════════════════════════════════════════════
