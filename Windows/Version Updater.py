#!/usr/bin/env python3
"""
CHSuite  ·  Version Patcher  v2
================================
Drop next to CHSuite.py and run.
Patches version strings, What's New content, and metadata constants.
"""

import re
import sys
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
#  PATCH TARGETS
# ══════════════════════════════════════════════════════════════════════════════

TARGET_DEFAULT = Path(__file__).parent / "CHSuite.py"

# Each tuple: (regex, version_group_index)
# Group at version_group_index is replaced with the new version string.
VERSION_PATTERNS = [
    # Core version constant
    (r'(CURRENT = ")([0-9.]+(?:-PTB)?)(")',                            2),
    # Docstring header
    (r'(CHSuite  by JURMR  v)([0-9.]+(?:-PTB)?)',                      2),
    # last_seen_version comparisons
    (r'("last_seen_version"\) != ")([0-9.]+(?:-PTB)?)(")',             2),
    (r'("last_seen_version"\] = ")([0-9.]+(?:-PTB)?)(")',              2),
    # UI labels
    (r'(by JURMR  v)([0-9.]+(?:-PTB)?)',                               2),
    (r'(CHSuite v)([0-9.]+(?:-PTB)?)',                                  2),
    # What's New headings
    (r'(What\'s New in v)([0-9.]+(?:-PTB)?)',                          2),
    (r'(What\'s New in CHSuite v)([0-9.]+(?:-PTB)?)',                  2),
    (r'(dialog for v)([0-9.]+(?:-PTB)?)',                               2),
    # HTTP User-Agent strings
    (r'(UpdateChecker/)([0-9.]+(?:-PTB)?)',                             2),
    (r'(Updater/)([0-9.]+(?:-PTB)?)',                                   2),
    (r'("CHSuite/)([0-9.]+(?:-PTB)?)(" CHSongManager)',                2),  # CHSongManager UA
]

BUMP_PATTERNS = [
    r'(Version bump )v[0-9.]+ \u2192 v[0-9.]+',
    r'(Version bump \u2014 )v[0-9.]+ \u2192 v[0-9.]+',
]

# Metadata: label → (description, regex, value_group)
METADATA_FIELDS = {
    "discord_client_id": (
        "Discord App Client ID",
        r'(DISCORD_CLIENT_ID_DEFAULT\s*=\s*")([^"]+)(")',
        2,
    ),
    "discord_large_text": (
        "Discord Rich Presence — Large Image Text",
        r'(_DISCORD_LARGE_TEXT\s*=\s*")([^"]+)(")',
        2,
    ),
    "discord_server_url": (
        "Discord Server Invite URL",
        r'("Murrin\' it Central",\s*"url":\s*")([^"]+)(")',
        2,
    ),
    "github_repo_url": (
        'Discord RPC "Download" Button URL',
        r'("label":\s*"Download",\s*"url":\s*")([^"]+)(")',
        2,
    ),
    "github_owner": (
        "GitHub Repo Owner  (GITHUB_REPO_OWNER)",
        r'(GITHUB_REPO_OWNER\s*=\s*")([^"]+)(")',
        2,
    ),
    "github_repo_name": (
        "GitHub Repo Name  (GITHUB_REPO_NAME)",
        r'(GITHUB_REPO_NAME\s*=\s*")([^"]+)(")',
        2,
    ),
    "sidebar_github_url": (
        "Sidebar GitHub icon URL",
        r'(_GITHUB_URL\s*=\s*")(https?://[^"]+)(")',
        2,
    ),
    "sidebar_discord_url": (
        "Sidebar Discord icon URL",
        r'(_DISCORD_URL\s*=\s*")(https?://[^"]+)(")',
        2,
    ),
    "author_name": (
        'Author display name  (replaces "JURMR")',
        r'(by )([A-Za-z0-9_]+)(?= {2}v[0-9.]+)',
        2,
    ),
}

COLORS = [
    ("accent",   "Purple  (main accent)"),
    ("accent2",  "Pink / Red"),
    ("accent3",  "Teal / Green"),
    ("warn",     "Yellow / Orange"),
    ("success",  "Green"),
    ("error",    "Red"),
    ("text_mid", "Grey"),
]

COLOR_HEX = {
    "accent":   "#a78bfa",
    "accent2":  "#f472b6",
    "accent3":  "#2dd4bf",
    "warn":     "#fbbf24",
    "success":  "#4ade80",
    "error":    "#f87171",
    "text_mid": "#9ca3af",
}


# ── Patch helpers ─────────────────────────────────────────────────────────────

def detect_version(text: str) -> str | None:
    m = re.search(r'CURRENT = "([0-9.]+(?:-PTB)?)"', text)
    return m.group(1) if m else None


def _replacer(new_val, group_idx):
    def _fn(m):
        parts = list(m.groups())
        parts[group_idx - 1] = new_val
        return "".join(parts)
    return _fn


def apply_version_patches(text: str, old: str, new: str) -> tuple[str, int]:
    count = 0
    for pattern, grp in VERSION_PATTERNS:
        text, n = re.subn(pattern, _replacer(new, grp), text)
        count += n
    return text, count


def apply_bump_patches(text: str, bump_label: str) -> tuple[str, int]:
    count = 0
    for pattern in BUMP_PATTERNS:
        def fn(m, lbl=bump_label):
            return m.group(1) + lbl
        text, n = re.subn(pattern, fn, text)
        count += n
    return text, count


def apply_metadata_patches(text: str, values: dict) -> tuple[str, int]:
    """Apply non-version metadata patches. values = {field_key: new_value}."""
    count = 0
    for key, new_val in values.items():
        if key not in METADATA_FIELDS or not new_val:
            continue
        _, pattern, grp = METADATA_FIELDS[key]
        text, n = re.subn(pattern, _replacer(new_val, grp), text)
        count += n
    return text, count


def detect_metadata(text: str) -> dict:
    """Pull current metadata values from source text."""
    out = {}
    for key, (_, pattern, grp) in METADATA_FIELDS.items():
        m = re.search(pattern, text)
        out[key] = m.group(grp) if m else ""
    return out


def parse_tooltip_items(text: str):
    m = re.search(r'([ \t]+items = \[)(\n.*?)(\n[ \t]+\])', text, re.DOTALL)
    if not m:
        return None, []
    entries = re.findall(r'\(C\["(\w+)"\]\s*,\s*"([^"]*)"\)', m.group(2))
    return m, list(entries)


def parse_dialog_changes(text: str):
    m = re.search(r'([ \t]+changes = \[)(\n.*?)(\n[ \t]+\])', text, re.DOTALL)
    if not m:
        return None, []
    block = m.group(2)
    entries = []
    for em in re.finditer(r'\(C\["(\w+)"\]\s*,\s*"([^"]*)",(.*?)\)', block, re.DOTALL):
        body_parts = re.findall(r'"((?:[^"\\]|\\.)*)"', em.group(3))
        entries.append((em.group(1), em.group(2), " ".join(body_parts)))
    return m, entries


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _list_indent(m) -> str:
    raw = m.group(1)
    return " " * (len(raw) - len(raw.lstrip()))


def format_tooltip_items(entries, list_indent: str) -> str:
    ind = list_indent + "    "
    return "\n".join(f'{ind}(C["{ck}"],  "{_escape(txt)}"),' for ck, txt in entries)


def format_dialog_changes(entries, list_indent: str) -> str:
    ind = list_indent + "    "
    body_i = ind + " "
    lines = []
    for ck, heading, body in entries:
        h, b = _escape(heading), _escape(body)
        lines.append(f'{ind}(C["{ck}"],  "{h}",')
        if len(b) > 78:
            split = b.rfind(" ", 40, 79)
            if split == -1:
                split = 78
            lines.append(f'{body_i}"{b[:split]} "')
            lines.append(f'{body_i}"{b[split + 1:]}"),')
        else:
            lines.append(f'{body_i}"{b}"),')
    return "\n".join(lines)


def rebuild_tooltip(text: str, m, entries) -> str:
    li = _list_indent(m)
    repl = m.group(1) + "\n" + format_tooltip_items(entries, li) + m.group(3)
    return text[:m.start()] + repl + text[m.end():]


def rebuild_dialog(text: str, m, entries) -> str:
    li = _list_indent(m)
    repl = m.group(1) + "\n" + format_dialog_changes(entries, li) + m.group(3)
    return text[:m.start()] + repl + text[m.end():]


# ══════════════════════════════════════════════════════════════════════════════
#  THEME  (dark purple — matches CHSuite palette)
# ══════════════════════════════════════════════════════════════════════════════

BG       = "#0c0e13"
PANEL    = "#13161f"
CARD     = "#181c28"
CARD2    = "#1c2030"
BORDER   = "#252b3d"
BORDER2  = "#2e3650"
ACCENT   = "#6c3bff"
ACCENT_D = "#3d2299"
TEXT     = "#e9ecf8"
TEXT_DIM = "#636b82"
TEXT_MID = "#9aa3bf"
SUCCESS  = "#22c55e"
WARN     = "#f59e0b"
ERROR    = "#ef4444"
HOVER    = "#1e2235"
INPUT_BG = "#0f1118"

# Platform-appropriate font stack
_FF = "Segoe UI" if sys.platform == "win32" else ("SF Pro Display" if sys.platform == "darwin" else "DejaVu Sans")
_FC = "Consolas"   if sys.platform == "win32" else "Menlo" if sys.platform == "darwin" else "DejaVu Sans Mono"

FN  = (_FF, 9)
FNB = (_FF, 9, "bold")
FNS = (_FF, 8)
FH  = (_FF, 11, "bold")
FHH = (_FF, 14, "bold")
FM  = (_FC, 10)
FMS = (_FC, 9)


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGET HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _sep(parent, vertical=False):
    if vertical:
        return tk.Frame(parent, bg=BORDER, width=1)
    return tk.Frame(parent, bg=BORDER, height=1)


def _lbl(parent, text, font=FN, fg=TEXT, bg=None, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg,
                    bg=bg or parent["bg"], **kw)


def _entry(parent, var, width=22, font=FM, **kw):
    return tk.Entry(parent, textvariable=var, font=font, width=width,
                    bg=INPUT_BG, fg=TEXT, insertbackground=ACCENT,
                    relief="flat", bd=6, **kw)


def _btn(parent, text, cmd, fg=TEXT, bg=CARD, font=FN,
         padx=10, pady=5, **kw):
    b = tk.Button(parent, text=text, command=cmd, font=font,
                  bg=bg, fg=fg, activebackground=BORDER2,
                  activeforeground=TEXT, relief="flat",
                  cursor="hand2", padx=padx, pady=pady, bd=0, **kw)
    b.bind("<Enter>", lambda _: b.config(bg=HOVER if bg not in (ACCENT, ACCENT_D) else ACCENT_D))
    b.bind("<Leave>", lambda _: b.config(bg=bg))
    return b


def _section_hdr(parent, title: str, sub: str = ""):
    row = tk.Frame(parent, bg=parent["bg"])
    row.pack(fill="x", pady=(16, 6))
    _lbl(row, title, font=FNB, fg=TEXT_MID, bg=parent["bg"]).pack(side="left")
    _sep(row).pack(side="left", fill="x", expand=True, padx=(10, 0))
    if sub:
        _lbl(parent, sub, font=FNS, fg=TEXT_DIM, bg=parent["bg"]).pack(
            anchor="w", pady=(0, 4))


# ══════════════════════════════════════════════════════════════════════════════
#  COLOR PICKER
# ══════════════════════════════════════════════════════════════════════════════

class ColorPicker(tk.Toplevel):
    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.result = current
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.title("Choose Color Key")
        self.withdraw()

        _lbl(self, "Color key", font=FH, fg=TEXT).pack(pady=(18, 10), padx=20, anchor="w")

        for key, desc in COLORS:
            hex_col = COLOR_HEX.get(key, "#ffffff")
            row = tk.Frame(self, bg=BG)
            row.pack(fill="x", padx=20, pady=2)

            sw = tk.Canvas(row, width=16, height=16, bg=BG, highlightthickness=0)
            sw.create_oval(1, 1, 15, 15, fill=hex_col, outline="")
            sw.pack(side="left", padx=(0, 10))

            is_cur = key == current
            tk.Button(row, text=f"{key:<10}  {desc}",
                      font=FM if is_cur else FMS,
                      bg=ACCENT if is_cur else CARD,
                      fg="white", activebackground=ACCENT_D,
                      activeforeground="white", relief="flat",
                      anchor="w", padx=12, pady=5, cursor="hand2",
                      command=lambda k=key: self._pick(k)
                      ).pack(side="left", fill="x", expand=True)

        _sep(self).pack(fill="x", padx=20, pady=(14, 8))
        _btn(self, "Cancel", self.destroy, fg=TEXT_DIM).pack(pady=(0, 12))

        self.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx() + 60}+{parent.winfo_rooty() + 60}")
        self.deiconify()

    def _pick(self, key):
        self.result = key
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY EDITOR DIALOGS
# ══════════════════════════════════════════════════════════════════════════════

class _BaseEntryEditor(tk.Toplevel):
    def __init__(self, parent, title, color_key=None):
        super().__init__(parent)
        self.result     = None
        self.color_key  = color_key or "accent"
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.title(title)
        self._color_lbl = None

    def _color_row(self, parent):
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", padx=20, pady=(0, 12))
        _lbl(row, "Color:", font=FNB, bg=parent["bg"]).pack(side="left")
        self._color_lbl = _lbl(row, self.color_key, font=FM,
                               fg=COLOR_HEX.get(self.color_key, TEXT),
                               bg=parent["bg"])
        self._color_lbl.pack(side="left", padx=(8, 12))
        _btn(row, "Change…", self._pick_color, fg=TEXT_DIM,
             bg=parent["bg"], pady=3).pack(side="left")

    def _pick_color(self):
        d = ColorPicker(self, self.color_key)
        self.wait_window(d)
        if d.result:
            self.color_key = d.result
            self._color_lbl.configure(text=self.color_key,
                                      fg=COLOR_HEX.get(self.color_key, TEXT))

    def _footer(self, parent, save_cmd):
        _sep(parent).pack(fill="x", padx=20, pady=(4, 10))
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(pady=(0, 16), padx=20)
        _btn(row, "Save", save_cmd, fg="white", bg=ACCENT,
             font=FNB, padx=18, pady=7).pack(side="left", padx=(0, 8))
        _btn(row, "Cancel", self.destroy, fg=TEXT_DIM,
             padx=18, pady=7).pack(side="left")

    def _pos(self, parent):
        self.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}")


class TooltipItemEditor(_BaseEntryEditor):
    def __init__(self, parent, color_key=None, text=""):
        super().__init__(parent, "Edit Tooltip Item", color_key)
        _lbl(self, "Text", font=FNB).pack(pady=(16, 4), padx=20, anchor="w")
        self.txt_var = tk.StringVar(value=text)
        e = _entry(self, self.txt_var, width=44)
        e.pack(padx=20, pady=(0, 12))
        e.focus_set()
        self._color_row(self)
        self._footer(self, self._save)
        self._pos(parent)

    def _save(self):
        t = self.txt_var.get().strip()
        if not t:
            messagebox.showwarning("Empty", "Text cannot be empty.", parent=self)
            return
        self.result = (self.color_key, t)
        self.destroy()


class DialogEntryEditor(_BaseEntryEditor):
    def __init__(self, parent, color_key=None, heading="", body=""):
        super().__init__(parent, "Edit Dialog Entry", color_key)
        _lbl(self, "Heading", font=FNB).pack(pady=(16, 4), padx=20, anchor="w")
        self.hd_var = tk.StringVar(value=heading)
        e = _entry(self, self.hd_var, width=48)
        e.pack(padx=20, pady=(0, 12))
        e.focus_set()
        _lbl(self, "Body", font=FNB).pack(padx=20, anchor="w")
        self.body_txt = tk.Text(self, font=FN, bg=INPUT_BG, fg=TEXT,
                                insertbackground=ACCENT, relief="flat",
                                bd=6, width=48, height=4, wrap="word")
        self.body_txt.insert("1.0", body)
        self.body_txt.pack(padx=20, pady=(4, 12))
        self._color_row(self)
        self._footer(self, self._save)
        self._pos(parent)

    def _save(self):
        h = self.hd_var.get().strip()
        b = self.body_txt.get("1.0", "end-1c").strip()
        if not h:
            messagebox.showwarning("Empty", "Heading cannot be empty.", parent=self)
            return
        self.result = (self.color_key, h, b)
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY LIST PANEL
# ══════════════════════════════════════════════════════════════════════════════

class EntryListPanel(tk.Frame):
    def __init__(self, parent, mode="tooltip", height=5):
        super().__init__(parent, bg=CARD, bd=0)
        self.mode    = mode
        self.entries = []
        self._build(height)

    def _build(self, height):
        lb_wrap = tk.Frame(self, bg=BORDER, bd=1)
        lb_wrap.pack(fill="both", expand=True, padx=10, pady=(8, 4))

        self.listbox = tk.Listbox(
            lb_wrap, font=FMS, bg=INPUT_BG, fg=TEXT,
            selectbackground=ACCENT, selectforeground="white",
            relief="flat", bd=0, height=height,
            activestyle="none", highlightthickness=0)
        sb = tk.Scrollbar(lb_wrap, command=self.listbox.yview,
                          bg=CARD, troughcolor=BG, relief="flat", width=10)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda _: self._edit())

        bar = tk.Frame(self, bg=CARD)
        bar.pack(fill="x", padx=10, pady=(0, 8))

        for text, cmd, fg_ in [
            ("+ Add",  self._add,       WARN),
            ("Edit",   self._edit,      TEXT),
            ("Remove", self._delete,    ERROR),
            ("↑",      self._move_up,   TEXT_DIM),
            ("↓",      self._move_down, TEXT_DIM),
        ]:
            tk.Button(bar, text=text, command=cmd, font=FNS,
                      bg=BG, fg=fg_, activebackground=BORDER,
                      activeforeground=fg_, relief="flat",
                      cursor="hand2", padx=8, pady=3
                      ).pack(side="left", padx=(0, 2))

        tk.Button(bar, text="⬆ Export", command=self._export, font=FNS,
                  bg=BG, fg=TEXT_DIM, activebackground=BORDER,
                  activeforeground=TEXT_MID, relief="flat",
                  cursor="hand2", padx=8, pady=3
                  ).pack(side="right", padx=(2, 0))
        tk.Button(bar, text="⬇ Import", command=self._import, font=FNS,
                  bg=BG, fg=TEXT_DIM, activebackground=BORDER,
                  activeforeground=TEXT_MID, relief="flat",
                  cursor="hand2", padx=8, pady=3
                  ).pack(side="right", padx=(2, 0))

    # ── data ─────────────────────────────────────────────────────────────────

    def set_entries(self, entries):
        self.entries = list(entries)
        self._refresh()

    def get_entries(self):
        return list(self.entries)

    def _refresh(self):
        self.listbox.delete(0, "end")
        for e in self.entries:
            if self.mode == "tooltip":
                ck, txt = e
                self.listbox.insert("end", f"  [{ck:<8}]  {txt}")
            else:
                ck, hd, bd = e
                preview = bd[:50] + "…" if len(bd) > 50 else bd
                self.listbox.insert("end", f"  [{ck:<8}]  {hd}  —  {preview}")

    def _sel(self):
        s = self.listbox.curselection()
        return s[0] if s else None

    # ── actions ───────────────────────────────────────────────────────────────

    def _add(self):
        p = self.winfo_toplevel()
        Cls = TooltipItemEditor if self.mode == "tooltip" else DialogEntryEditor
        d = Cls(p)
        self.wait_window(d)
        if d.result:
            self.entries.append(d.result)
            self._refresh()
            self.listbox.selection_set("end")

    def _edit(self):
        idx = self._sel()
        if idx is None:
            return
        p = self.winfo_toplevel()
        if self.mode == "tooltip":
            ck, txt = self.entries[idx]
            d = TooltipItemEditor(p, ck, txt)
        else:
            ck, hd, bd = self.entries[idx]
            d = DialogEntryEditor(p, ck, hd, bd)
        self.wait_window(d)
        if d.result:
            self.entries[idx] = d.result
            self._refresh()
            self.listbox.selection_set(idx)

    def _delete(self):
        idx = self._sel()
        if idx is None:
            return
        name = self.entries[idx][1]
        if messagebox.askyesno("Remove", f'Remove "{name}"?',
                               parent=self.winfo_toplevel()):
            self.entries.pop(idx)
            self._refresh()

    def _move_up(self):
        idx = self._sel()
        if idx is None or idx == 0:
            return
        self.entries[idx - 1], self.entries[idx] = self.entries[idx], self.entries[idx - 1]
        self._refresh()
        self.listbox.selection_set(idx - 1)

    def _move_down(self):
        idx = self._sel()
        if idx is None or idx >= len(self.entries) - 1:
            return
        self.entries[idx], self.entries[idx + 1] = self.entries[idx + 1], self.entries[idx]
        self._refresh()
        self.listbox.selection_set(idx + 1)

    # ── import / export ───────────────────────────────────────────────────────

    def _to_json(self):
        if self.mode == "tooltip":
            return [{"color": ck, "text": txt} for ck, txt in self.entries]
        return [{"color": ck, "heading": hd, "body": bd}
                for ck, hd, bd in self.entries]

    def _from_json(self, data):
        out = []
        for item in data:
            if self.mode == "tooltip":
                out.append((item["color"], item["text"]))
            else:
                out.append((item["color"], item["heading"], item.get("body", "")))
        return out

    def _export(self):
        key  = "tooltip_items" if self.mode == "tooltip" else "dialog_entries"
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title=f"Export {key}",
            defaultextension=".json", initialfile=f"whats_new_{key}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        Path(path).write_text(
            json.dumps({key: self._to_json()}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        messagebox.showinfo("Exported",
                            f"Saved {len(self.entries)} entries to:\n{Path(path).name}",
                            parent=self.winfo_toplevel())

    def _import(self):
        key  = "tooltip_items" if self.mode == "tooltip" else "dialog_entries"
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title=f"Import {key}",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Import Error", f"Could not read JSON:\n{e}",
                                 parent=self.winfo_toplevel())
            return
        data = raw.get(key, raw) if isinstance(raw, dict) else raw
        try:
            entries = self._from_json(data)
        except (KeyError, TypeError) as e:
            messagebox.showerror("Import Error", f"Bad entry format:\n{e}",
                                 parent=self.winfo_toplevel())
            return
        action = messagebox.askyesnocancel(
            "Import",
            f"Found {len(entries)} entries.\n\n"
            "Yes = replace current list\nNo = append to current list",
            parent=self.winfo_toplevel())
        if action is None:
            return
        self.entries = entries if action else self.entries + entries
        self._refresh()


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKLIST WIDGET  (live patch preview in left panel)
# ══════════════════════════════════════════════════════════════════════════════

class PatchChecklist(tk.Frame):
    """Shows which parts of the patch are active / changed."""

    _ITEMS = [
        ("ver",  "Version strings"),
        ("bump", "Bump label"),
        ("tip",  "Tooltip items  (What's New)"),
        ("dlg",  "Dialog entries  (What's New)"),
        ("meta", "Metadata constants"),
    ]

    def __init__(self, parent):
        super().__init__(parent, bg=parent["bg"])
        self._rows = {}
        for key, label in self._ITEMS:
            row = tk.Frame(self, bg=parent["bg"])
            row.pack(fill="x", pady=1)
            dot  = tk.Label(row, text="●", font=FNS, bg=parent["bg"], fg=BORDER2, width=2)
            dot.pack(side="left")
            lbl  = tk.Label(row, text=label, font=FNS, bg=parent["bg"], fg=TEXT_DIM, anchor="w")
            lbl.pack(side="left")
            note = tk.Label(row, text="", font=FNS, bg=parent["bg"], fg=TEXT_DIM, anchor="w")
            note.pack(side="left", padx=(4, 0))
            self._rows[key] = (dot, lbl, note)

    def set(self, key: str, active: bool, note: str = ""):
        dot, lbl, note_lbl = self._rows[key]
        if active:
            dot.config(fg=SUCCESS)
            lbl.config(fg=TEXT)
        else:
            dot.config(fg=BORDER2)
            lbl.config(fg=TEXT_DIM)
        note_lbl.config(text=note, fg=TEXT_MID if note else TEXT_DIM)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CHSuite  ·  Version Patcher")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(860, 600)

        self.target_path = tk.StringVar(value=str(TARGET_DEFAULT))
        self.current_ver = tk.StringVar(value="—")
        self.new_ver     = tk.StringVar()
        self.bump_label  = tk.StringVar()
        self.ptb_var     = tk.BooleanVar(value=False)
        self.skip_ver_var = tk.BooleanVar(value=False)

        self._file_text   = None
        self._tip_match   = None
        self._dlg_match   = None
        self._tip_orig    = []
        self._dlg_orig    = []
        self._meta_orig   = {}        # detected from file
        self._meta_vars   = {}        # tk.StringVar per metadata key

        # Build metadata StringVars
        for key in METADATA_FIELDS:
            self._meta_vars[key] = tk.StringVar()

        self._build_ui()
        self._try_autoload()
        self._center()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        _sep(self).pack(fill="x")
        self._build_file_bar()
        _sep(self).pack(fill="x")

        # Two-column main area
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0, minsize=290)
        main.columnconfigure(1, weight=0)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_left_panel(main)
        _sep(main, vertical=True).grid(row=0, column=1, sticky="ns")
        self._build_right_panel(main)

        _sep(self).pack(fill="x")
        self._build_status_bar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=PANEL, pady=13)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CHSuite", font=(_FF, 16, "bold"),
                 fg=ACCENT, bg=PANEL).pack(side="left", padx=(18, 4))
        tk.Label(hdr, text="Version Patcher", font=(_FF, 11),
                 fg=TEXT_DIM, bg=PANEL).pack(side="left")
        tk.Label(hdr, text="v2", font=FNS,
                 fg=BORDER2, bg=PANEL).pack(side="left", padx=(6, 0), pady=(4, 0))

        # ── Right-side action cluster ─────────────────────────────────────────
        # Pack right-to-left: Export/Import → Apply → divider → Skip checkbox

        _btn(hdr, "⬆⬇  Export / Import All",
             self._show_io_menu, fg=TEXT_DIM, bg=CARD2,
             font=FNS, pady=6, padx=10).pack(side="right", padx=(4, 18))

        self._apply_btn = _btn(
            hdr, "Apply Version Patch", self._apply,
            fg="white", bg=ACCENT, font=FNB,
            padx=14, pady=6)
        self._apply_btn.pack(side="right", padx=(0, 4))

        tk.Frame(hdr, bg=BORDER, width=1).pack(side="right", fill="y", padx=(8, 8), pady=6)

        tk.Checkbutton(
            hdr,
            text="Skip version bump",
            variable=self.skip_ver_var, bg=PANEL, fg=TEXT_DIM,
            selectcolor=INPUT_BG, activebackground=PANEL,
            activeforeground=TEXT, font=FNS,
            command=self._on_skip_ver_toggle,
        ).pack(side="right", padx=(0, 4))

    def _build_file_bar(self):
        bar = tk.Frame(self, bg=PANEL, padx=16, pady=10)
        bar.pack(fill="x")

        tk.Label(bar, text="File", font=FNS, fg=TEXT_DIM,
                 bg=PANEL, width=4, anchor="w").pack(side="left")

        e = tk.Entry(bar, textvariable=self.target_path, font=FMS,
                     bg=INPUT_BG, fg=TEXT_MID, insertbackground=ACCENT,
                     relief="flat", bd=6)
        e.pack(side="left", fill="x", expand=True, padx=(0, 6))

        _btn(bar, "Browse…", self._browse, fg=TEXT_DIM,
             bg=CARD2, pady=6).pack(side="left", padx=(0, 4))
        _btn(bar, "Load", self._load, fg="white",
             bg=ACCENT, font=FNB, pady=6).pack(side="left")

    def _build_left_panel(self, parent):
        pnl = tk.Frame(parent, bg=BG, width=290)
        pnl.grid(row=0, column=0, sticky="nsew", padx=0)
        pnl.pack_propagate(False)

        inner = tk.Frame(pnl, bg=BG, padx=18, pady=10)
        inner.pack(fill="both", expand=True)

        # ── Version cards ─────────────────────────────────────────────────────
        _section_hdr(inner, "VERSION")

        cards = tk.Frame(inner, bg=BG)
        cards.pack(fill="x", pady=(0, 12))

        # Current
        cur_card = tk.Frame(cards, bg=CARD, padx=14, pady=10)
        cur_card.pack(fill="x")
        tk.Label(cur_card, text="CURRENT", font=(_FF, 7, "bold"),
                 fg=TEXT_DIM, bg=CARD).pack()
        tk.Label(cur_card, textvariable=self.current_ver,
                 font=(_FC, 20, "bold"), fg=WARN, bg=CARD).pack()

        tk.Label(cards, text="↓", font=(_FF, 14),
                 fg=BORDER2, bg=BG).pack(pady=(4, 4))

        # New
        new_card = tk.Frame(cards, bg=CARD, padx=14, pady=10)
        new_card.pack(fill="x")
        tk.Label(new_card, text="NEW", font=(_FF, 7, "bold"),
                 fg=TEXT_DIM, bg=CARD).pack()
        self._new_entry = tk.Entry(
            new_card, textvariable=self.new_ver,
            font=(_FC, 20, "bold"), bg=CARD, fg=ACCENT,
            insertbackground=ACCENT, relief="flat", bd=0,
            width=12, justify="center")
        self._new_entry.pack()
        self._new_entry.bind("<FocusIn>",
            lambda _: new_card.configure(bg=HOVER) or self._new_entry.configure(bg=HOVER))
        self._new_entry.bind("<FocusOut>",
            lambda _: new_card.configure(bg=CARD) or self._new_entry.configure(bg=CARD))
        self.new_ver.trace_add("write", self._auto_bump)

        # ── PTB toggle ────────────────────────────────────────────────────────
        ptb_row = tk.Frame(inner, bg=BG)
        ptb_row.pack(anchor="w", pady=(6, 0))
        tk.Checkbutton(
            ptb_row, text="PTB  (appends -PTB to version string)",
            variable=self.ptb_var, bg=BG, fg=TEXT_DIM,
            selectcolor=INPUT_BG, activebackground=BG,
            activeforeground=TEXT, font=FNS,
            command=self._on_ptb_toggle,
        ).pack(side="left")

        # ── Bump label ────────────────────────────────────────────────────────
        _section_hdr(inner, "BUMP LABEL",
                     sub='Text written into "Version bump …" comments in the source.')

        bump_row = tk.Frame(inner, bg=BG)
        bump_row.pack(fill="x", pady=(0, 4))
        self._bump_entry = _entry(bump_row, self.bump_label, width=22)
        self._bump_entry.pack(side="left", fill="x", expand=True)
        _btn(bump_row, "↺", self._reset_bump, fg=TEXT_DIM,
             bg=CARD, pady=6, padx=8).pack(side="left", padx=(6, 0))

        # ── Patch preview ──────────────────────────────────────────────────────
        _section_hdr(inner, "WHAT WILL BE PATCHED",
                     sub="Green = active in current patch.")

        self._checklist = PatchChecklist(inner)
        self._checklist.pack(fill="x", pady=(0, 12))
        self._update_checklist()

        # Traces to keep checklist live
        self.new_ver.trace_add("write",    lambda *_: self._update_checklist())
        self.bump_label.trace_add("write", lambda *_: self._update_checklist())

    def _build_right_panel(self, parent):
        pnl = tk.Frame(parent, bg=BG)
        pnl.grid(row=0, column=2, sticky="nsew")

        # ttk style for notebook tabs
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Patcher.TNotebook",
                        background=BG, borderwidth=0, tabmargins=0)
        style.configure("Patcher.TNotebook.Tab",
                        background=PANEL, foreground=TEXT_DIM,
                        font=FNB, padding=[16, 8],
                        borderwidth=0)
        style.map("Patcher.TNotebook.Tab",
                  background=[("selected", CARD2), ("active", HOVER)],
                  foreground=[("selected", TEXT), ("active", TEXT_MID)])

        nb = ttk.Notebook(pnl, style="Patcher.TNotebook")
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_whats_new_tab(nb)
        self._build_metadata_tab(nb)

    def _build_whats_new_tab(self, nb):
        tab = tk.Frame(nb, bg=BG)
        nb.add(tab, text="📋  What's New")

        inner = tk.Frame(tab, bg=BG, padx=18, pady=10)
        inner.pack(fill="both", expand=True)

        # ── Tooltip items (sidebar hover) ─────────────────────────────────────
        _section_hdr(inner, "TOOLTIP ITEMS",
                     sub="Shown in the sidebar hover tooltip when the user hovers the ⓘ icon.")
        self._tip_note = tk.Label(inner, text="Load a file first.",
                                  font=FNS, fg=TEXT_DIM, bg=BG, anchor="w")
        self._tip_note.pack(anchor="w", pady=(0, 4))

        self.tip_panel = EntryListPanel(inner, mode="tooltip", height=4)
        self.tip_panel.pack(fill="x")

        _sep(inner).pack(fill="x", pady=(14, 0))

        # ── Dialog changes (popup) ────────────────────────────────────────────
        _section_hdr(inner, "DIALOG ENTRIES",
                     sub='Shown in the "What\'s New" popup that appears once per version.')
        self._dlg_note = tk.Label(inner, text="Load a file first.",
                                  font=FNS, fg=TEXT_DIM, bg=BG, anchor="w")
        self._dlg_note.pack(anchor="w", pady=(0, 4))

        self.dlg_panel = EntryListPanel(inner, mode="dialog", height=4)
        self.dlg_panel.pack(fill="x")

    def _build_metadata_tab(self, nb):
        tab = tk.Frame(nb, bg=BG)
        nb.add(tab, text="⚙  Metadata")

        # Scrollable canvas
        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG, padx=18, pady=10)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))

        def _on_mousewheel(event):
            # Windows/macOS: event.delta; Linux: Button-4/5
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_scroll(widget):
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Button-4>",   _on_mousewheel, add="+")
            widget.bind("<Button-5>",   _on_mousewheel, add="+")
            for child in widget.winfo_children():
                _bind_scroll(child)

        _bind_scroll(canvas)

        _section_hdr(inner, "METADATA CONSTANTS",
                     sub="These are patched separately from the version bump. "
                         "Leave a field blank to skip that constant.")

        # Grouped fields
        groups = [
            ("Discord", [
                "discord_client_id",
                "discord_large_text",
                "discord_server_url",
            ]),
            ("GitHub / Links", [
                "github_owner",
                "github_repo_name",
                "github_repo_url",
                "sidebar_github_url",
                "sidebar_discord_url",
            ]),
            ("Author", [
                "author_name",
            ]),
        ]

        for group_title, keys in groups:
            grp = tk.Frame(inner, bg=CARD, padx=14, pady=10)
            grp.pack(fill="x", pady=(0, 10))

            tk.Label(grp, text=group_title, font=FNB,
                     fg=TEXT_MID, bg=CARD).pack(anchor="w", pady=(0, 8))

            for key in keys:
                desc, _, _ = METADATA_FIELDS[key]
                row = tk.Frame(grp, bg=CARD)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=desc, font=FNS, fg=TEXT_DIM,
                         bg=CARD, anchor="w", width=40).pack(side="left")
                e = _entry(row, self._meta_vars[key], width=28, font=FMS)
                e.pack(side="left", padx=(8, 0))

        _sep(inner).pack(fill="x", pady=(10, 6))

        btn_row = tk.Frame(inner, bg=BG)
        btn_row.pack(anchor="w", pady=(4, 0))
        _btn(btn_row, "Apply Metadata Patch", self._apply_metadata,
             fg="white", bg=ACCENT_D, font=FNB, padx=18, pady=8
             ).pack(side="left")
        _lbl(btn_row, "  Backs up file before patching.",
             font=FNS, fg=TEXT_DIM, bg=BG).pack(side="left")

        # Rebind scroll to all children now that they're all built
        inner.update_idletasks()
        _bind_scroll(canvas)

    def _build_status_bar(self):
        bar = tk.Frame(self, bg=PANEL, padx=16, pady=8)
        bar.pack(fill="x")
        self._status_lbl = tk.Label(bar, text="", font=FNS,
                                    fg=TEXT_DIM, bg=PANEL, anchor="w")
        self._status_lbl.pack(side="left", fill="x", expand=True)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _try_autoload(self):
        if TARGET_DEFAULT.exists():
            self._load()

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select CHSuite.py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if path:
            self.target_path.set(path)
            self._load()

    def _load(self):
        path = Path(self.target_path.get())
        if not path.exists():
            self._status(f"File not found: {path.name}", ERROR)
            return

        text = path.read_text(encoding="utf-8")
        ver  = detect_version(text)
        if not ver:
            self._status("Could not detect version in this file.", ERROR)
            return

        self._file_text = text
        self.current_ver.set(f"v{ver}")

        # What's New sections
        self._tip_match, self._tip_orig = parse_tooltip_items(text)
        self._dlg_match, self._dlg_orig = parse_dialog_changes(text)
        self.tip_panel.set_entries(self._tip_orig)
        self.dlg_panel.set_entries(self._dlg_orig)

        self._tip_note.configure(
            text=f"{len(self._tip_orig)} item(s) found" if self._tip_match
            else "Section 'items = [...]' not found in file",
            fg=TEXT_MID if self._tip_match else ERROR)
        self._dlg_note.configure(
            text=f"{len(self._dlg_orig)} entr(ies) found" if self._dlg_match
            else "Section 'changes = [...]' not found in file",
            fg=TEXT_MID if self._dlg_match else ERROR)

        # Metadata
        self._meta_orig = detect_metadata(text)
        for key, var in self._meta_vars.items():
            var.set(self._meta_orig.get(key, ""))

        self._update_checklist()
        self._status(f"Loaded  {path.name}  (currently v{ver})", SUCCESS)

    def _effective_new_ver(self) -> str:
        """Return new version string, appending -PTB if the toggle is on."""
        base = self.new_ver.get().strip()
        if base and self.ptb_var.get() and not base.endswith("-PTB"):
            return base + "-PTB"
        return base

    def _on_ptb_toggle(self, *_):
        self._auto_bump()
        self._update_checklist()

    def _on_skip_ver_toggle(self, *_):
        skip  = self.skip_ver_var.get()
        state = "disabled" if skip else "normal"
        self._new_entry.configure(state=state)
        self._bump_entry.configure(state=state)
        self._apply_btn.configure(
            text="Apply Patch  (no version bump)" if skip else "Apply Version Patch")
        self._update_checklist()

    def _auto_bump(self, *_):
        cur = self.current_ver.get().lstrip("v")
        new = self._effective_new_ver()
        if cur and cur != "—" and new:
            self.bump_label.set(f"v{cur} \u2192 v{new}")

    def _reset_bump(self):
        cur = self.current_ver.get().lstrip("v")
        new = self._effective_new_ver()
        self.bump_label.set(f"v{cur} \u2192 v{new}")

    def _update_checklist(self):
        loaded   = bool(self._file_text)
        skip_ver = self.skip_ver_var.get()
        has_ver  = bool(self.new_ver.get().strip()) and not skip_ver
        has_bump = bool(self.bump_label.get().strip()) and not skip_ver

        tip_entries = self.tip_panel.get_entries() if hasattr(self, "tip_panel") else []
        dlg_entries = self.dlg_panel.get_entries() if hasattr(self, "dlg_panel") else []
        tip_changed = tip_entries != self._tip_orig
        dlg_changed = dlg_entries != self._dlg_orig

        meta_changed = any(
            self._meta_vars[k].get().strip() != self._meta_orig.get(k, "")
            for k in METADATA_FIELDS
            if self._meta_vars[k].get().strip()
        )

        if skip_ver:
            ver_note  = "skipped"
            bump_note = "skipped"
        else:
            eff = self._effective_new_ver()
            ver_note  = f"→ v{eff}" if has_ver else "(enter new version)"
            bump_note = self.bump_label.get()[:30] or ""

        self._checklist.set("ver",  loaded and has_ver,  ver_note)
        self._checklist.set("bump", loaded and has_bump, bump_note)
        self._checklist.set("tip",  loaded and tip_changed,
                            "modified" if tip_changed else "unchanged")
        self._checklist.set("dlg",  loaded and dlg_changed,
                            "modified" if dlg_changed else "unchanged")
        self._checklist.set("meta", loaded and meta_changed,
                            "use ⚙ tab" if not meta_changed else "pending")

    def _apply(self):
        if not self._file_text:
            self._status("Load a file first.", ERROR)
            return

        skip_ver = self.skip_ver_var.get()
        new      = self._effective_new_ver()

        if not skip_ver:
            base = self.new_ver.get().strip()
            if not base:
                self._status("Enter a new version number.", ERROR)
                return
            if not re.fullmatch(r"[0-9]+(\.[0-9]+)*", base):
                self._status("Invalid version — use digits and dots only  (e.g. 5.1).", ERROR)
                return
            bump = self.bump_label.get().strip()
            if not bump:
                self._status("Bump label cannot be empty.", ERROR)
                return
        else:
            bump = ""

        cur         = self.current_ver.get().lstrip("v")
        tip_entries = self.tip_panel.get_entries()
        dlg_entries = self.dlg_panel.get_entries()
        tip_changed = tip_entries != self._tip_orig
        dlg_changed = dlg_entries != self._dlg_orig

        # Collect pending metadata changes
        meta_values  = {k: v.get().strip() for k, v in self._meta_vars.items() if v.get().strip()}
        meta_changed = {k: v for k, v in meta_values.items() if v != self._meta_orig.get(k, "")}

        if skip_ver and not tip_changed and not dlg_changed and not meta_changed:
            self._status("Nothing to patch — modify some content or metadata first.", WARN)
            return

        if skip_ver:
            summary = (
                f"Apply patch (no version bump)?\n\n"
                f"  Version strings  : skipped\n"
                f"  Bump label       : skipped\n"
                f"  Tooltip items    : {'MODIFIED' if tip_changed else 'unchanged'}\n"
                f"  Dialog entries   : {'MODIFIED' if dlg_changed else 'unchanged'}\n"
                f"  Metadata fields  : {len(meta_changed)} changed\n\n"
                f"A .bak backup will be created automatically."
            )
        else:
            summary = (
                f"Apply version patch?\n\n"
                f"  {self.current_ver.get()}  →  v{new}\n"
                f"  Bump label       : {bump}\n"
                f"  Tooltip items    : {'MODIFIED' if tip_changed else 'unchanged'}\n"
                f"  Dialog entries   : {'MODIFIED' if dlg_changed else 'unchanged'}\n\n"
                f"A .bak backup will be created automatically."
            )
        if not messagebox.askyesno("Confirm Patch", summary, parent=self):
            return

        path = Path(self.target_path.get())
        shutil.copy2(path, path.with_suffix(".py.bak"))

        patched  = self._file_text
        n_ver = n_bump = 0

        if not skip_ver:
            patched, n_ver  = apply_version_patches(patched, cur, new)
            patched, n_bump = apply_bump_patches(patched, bump)

        wn = 0
        if self._tip_match and tip_changed:
            m2, _ = parse_tooltip_items(patched)
            if m2:
                patched = rebuild_tooltip(patched, m2, tip_entries)
                wn += 1

        if self._dlg_match and dlg_changed:
            m2, _ = parse_dialog_changes(patched)
            if m2:
                patched = rebuild_dialog(patched, m2, dlg_entries)
                wn += 1

        n_meta = 0
        if meta_changed:
            patched, n_meta = apply_metadata_patches(patched, meta_changed)

        path.write_text(patched, encoding="utf-8")
        self._file_text = patched
        self._tip_orig  = tip_entries
        self._dlg_orig  = dlg_entries
        if meta_changed:
            self._meta_orig.update(meta_changed)
            # Refresh metadata fields to match saved state
            for k, v in meta_changed.items():
                self._meta_vars[k].set(v)

        if not skip_ver:
            self.current_ver.set(f"v{new}")
            self.new_ver.set("")
        self._update_checklist()

        if skip_ver:
            msg = f"✓  Patch applied (no version bump)"
            if wn:
                msg += f"  ·  {wn} What's New section(s) updated"
            if n_meta:
                msg += f"  ·  {n_meta} metadata replacement(s)"
        else:
            total = n_ver + n_bump
            msg   = f"✓  {total} replacement(s)  ({n_ver} version strings, {n_bump} bump label)"
            if wn:
                msg += f"  ·  {wn} What's New section(s) updated"
        msg += "  ·  backup saved"
        self._status(msg, SUCCESS)

    def _apply_metadata(self):
        if not self._file_text:
            self._status("Load a file first.", ERROR)
            return

        values = {k: v.get().strip() for k, v in self._meta_vars.items() if v.get().strip()}
        changed = {k: v for k, v in values.items() if v != self._meta_orig.get(k, "")}
        if not changed:
            self._status("No metadata fields have been changed.", WARN)
            return

        lines = "\n".join(f"  • {METADATA_FIELDS[k][0]}: {v}" for k, v in changed.items())
        if not messagebox.askyesno(
                "Confirm Metadata Patch",
                f"Apply metadata patch?\n\n{lines}\n\n"
                "A .bak backup will be created automatically.",
                parent=self):
            return

        path = Path(self.target_path.get())
        shutil.copy2(path, path.with_suffix(".py.bak"))

        patched, n = apply_metadata_patches(self._file_text, changed)
        path.write_text(patched, encoding="utf-8")
        self._file_text = patched
        self._meta_orig.update(changed)
        self._update_checklist()

        self._status(f"✓  {n} metadata replacement(s) applied  ·  backup saved", SUCCESS)

    def _status(self, msg: str, color: str = TEXT_DIM):
        self._status_lbl.configure(text=msg, fg=color)

    # ── Global import / export ────────────────────────────────────────────────

    def _show_io_menu(self):
        m = tk.Menu(self, tearoff=0, bg=CARD, fg=TEXT,
                    activebackground=ACCENT, activeforeground="white",
                    font=FN, relief="flat", bd=0)
        m.add_command(label="⬆  Export All  (JSON)",  command=self._export_all)
        m.add_command(label="⬇  Import All  (JSON)",  command=self._import_all)
        try:
            b = self.focus_get()
            x = b.winfo_rootx()
            y = b.winfo_rooty() - 60
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _export_all(self):
        ver  = self.current_ver.get().lstrip("v") or "unknown"
        path = filedialog.asksaveasfilename(
            parent=self, title="Export All — What's New Data",
            defaultextension=".json",
            initialfile=f"whats_new_v{ver}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        payload = {
            "version":        ver,
            "bump_label":     self.bump_label.get(),
            "tooltip_items":  self.tip_panel._to_json(),
            "dialog_entries": self.dlg_panel._to_json(),
        }
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                              encoding="utf-8")
        self._status(f"✓  Exported to {Path(path).name}", SUCCESS)

    def _import_all(self):
        path = filedialog.askopenfilename(
            parent=self, title="Import All — What's New Data",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Import Error", f"Could not read JSON:\n{e}", parent=self)
            return
        if not isinstance(raw, dict):
            messagebox.showerror("Import Error",
                                 "Expected a JSON object at the top level.", parent=self)
            return
        if "tooltip_items" in raw:
            self.tip_panel.set_entries(self.tip_panel._from_json(raw["tooltip_items"]))
        if "dialog_entries" in raw:
            self.dlg_panel.set_entries(self.dlg_panel._from_json(raw["dialog_entries"]))
        if "bump_label" in raw:
            self.bump_label.set(raw["bump_label"])
        self._status(f"✓  Imported from {Path(path).name}", SUCCESS)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    App().mainloop()
