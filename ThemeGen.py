"""
ThemeGen — CHSuite live theme designer (standalone).

Drop this .py anywhere — it will auto-detect CHSuite.exe in its own folder
or in a running process, connect via a local socket, and push live colour
updates directly into the running CHSuite window.

No need to keep CHSuite as a .py file.
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import colorsys
import json, os, socket, struct, subprocess, sys, threading, time
from pathlib import Path

# ── colour / font constants (used by _ColorPickerDialog) ──────────────────────

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

FT  = ("Lato", 10)
FTB = ("Lato", 10, "bold")
FTS = ("Lato", 8)

# ── constants (must match CHSuite.py) ─────────────────────────────────────────
IPC_PORT = 59832
EXE_NAME = "CHSuite.exe" if sys.platform == "win32" else "CHSuite"

_THEME_KEYS = (
    "bg", "panel", "card", "card2", "sidebar",
    "border", "border2",
    "accent", "accent_dim", "accent2", "accent3",
    "text", "text_dim", "text_mid",
    "success", "warn", "error",
    "selected", "hover", "nav_active", "nav_hover",
)

# Hardcoded defaults (same as the built-in C dict in CHSuite)
_DEFAULTS = {
    "bg":          "#12141a",
    "panel":       "#1a1d26",
    "card":        "#1c1f26",
    "card2":       "#1e212a",
    "sidebar":     "#161820",
    "border":      "#2a2d3a",
    "border2":     "#343748",
    "accent":      "#6c3bff",
    "accent_dim":  "#4e2bbb",
    "accent2":     "#3b9fff",
    "accent3":     "#3bffb0",
    "text":        "#e8eaf2",
    "text_dim":    "#7a7f9a",
    "text_mid":    "#b0b4c8",
    "success":     "#22c55e",
    "warn":        "#f59e0b",
    "error":       "#ef4444",
    "selected":    "#2a2d3a",
    "hover":       "#23263a",
    "nav_active":  "#6c3bff",
    "nav_hover":   "#2a2d3a",
}

# ── IPC helpers ────────────────────────────────────────────────────────────────

def _ipc_pack(data: dict) -> bytes:
    payload = json.dumps(data).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload

def _ipc_recv(conn, timeout: float = 5.0):
    conn.settimeout(timeout)
    try:
        raw = b""
        while len(raw) < 4:
            c = conn.recv(4 - len(raw))
            if not c:
                return None
            raw += c
        length = struct.unpack(">I", raw)[0]
        data = b""
        while len(data) < length:
            c = conn.recv(length - len(data))
            if not c:
                return None
            data += c
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None

# ── CHSuite discovery ──────────────────────────────────────────────────────────

def _find_exe() -> "Path | None":
    """Return path to CHSuite.exe: check beside ThemeGen first, then scan processes."""
    # 1. Same folder as this script / frozen exe
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    candidate = here / EXE_NAME
    if candidate.is_file():
        return candidate

    # 2. Running processes on Windows via wmic
    if os.name == "nt":
        for cmd in (
            ["wmic", "process", "where", f"name='{EXE_NAME}'", "get", "ExecutablePath", "/VALUE"],
        ):
            try:
                out = subprocess.check_output(
                    cmd, creationflags=0x08000000,
                    stderr=subprocess.DEVNULL, timeout=6
                ).decode(errors="replace")
                for line in out.splitlines():
                    if "ExecutablePath=" in line:
                        p = Path(line.split("=", 1)[1].strip())
                        if p.is_file():
                            return p
            except Exception:
                pass

    # 3. Running processes on Linux via /proc/*/exe symlinks
    if sys.platform.startswith("linux"):
        try:
            import glob
            for exe_link in glob.glob("/proc/*/exe"):
                try:
                    target = os.readlink(exe_link)
                    if os.path.basename(target) == EXE_NAME:
                        p = Path(target)
                        if p.is_file():
                            return p
                except (OSError, PermissionError):
                    pass
        except Exception:
            pass

    return None

def _exe_is_running() -> bool:
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH", "/FO", "CSV"],
                creationflags=0x08000000, stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="replace")
            return EXE_NAME.lower() in out.lower()
        except Exception:
            return False
    else:
        # Linux/macOS: use pgrep to check for a running CHSuite process.
        # -x matches the exact process name; fall back to a broader -f search
        # in case the binary runs under a slightly different argv[0].
        try:
            ret = subprocess.run(
                ["pgrep", "-x", EXE_NAME],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode
            if ret == 0:
                return True
        except Exception:
            pass
        try:
            ret = subprocess.run(
                ["pgrep", "-f", EXE_NAME],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode
            return ret == 0
        except Exception:
            return False

# ── colour helpers ─────────────────────────────────────────────────────────────

def _ng_hex_to_rgb(h: str):
    """int-based hex→(r,g,b)."""
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _ng_rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02X}{:02X}{:02X}".format(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


# ── custom colour picker (HSV square + hue bar) ────────────────────────────────

class _ColorPickerDialog(tk.Toplevel):
    """Full HSV square + hue bar colour picker — replaces tkinter's colorchooser."""
    _SQ = 220
    _HH = 20

    def __init__(self, parent, initial_hex: str, title: str = "Pick Color"):
        super().__init__(parent)
        self.title(title); self.resizable(False, False)
        self.configure(bg=C["bg"]); self.transient(parent); self.grab_set()
        self.result = None
        try: ri, gi, bi = _ng_hex_to_rgb(initial_hex)
        except Exception: ri, gi, bi = 255, 255, 255
        h, s, v = colorsys.rgb_to_hsv(ri / 255, gi / 255, bi / 255)
        self._h, self._s, self._v = h, s, v
        self._orig = _ng_rgb_to_hex(ri, gi, bi).upper()
        self._r = tk.IntVar(value=ri); self._g = tk.IntVar(value=gi); self._b = tk.IntVar(value=bi)
        self._hex_var = tk.StringVar(value=self._orig)
        self._busy = False; self._sq_cur_ids = []; self._hue_cur_ids = []
        self._sq_photo = None
        self._build_ui(); self._render_sq(); self._render_hue()
        self._refresh_cursors(); self._update_preview()
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        ww, wh = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{px + (pw - ww) // 2}+{py + (ph - wh) // 2}")
        self.wait_window()

    def _build_ui(self):
        SQ = self._SQ
        outer = tk.Frame(self, bg=C["bg"], padx=18, pady=16); outer.pack()
        left = tk.Frame(outer, bg=C["bg"]); left.pack(side="left", padx=(0, 20))
        sq_wrap = tk.Frame(left, bg="#252845", padx=1, pady=1); sq_wrap.pack()
        self._sq_cv = tk.Canvas(sq_wrap, width=SQ, height=SQ, highlightthickness=0, cursor="crosshair")
        self._sq_cv.pack()
        self._sq_cv.bind("<Button-1>", self._sq_drag)
        self._sq_cv.bind("<B1-Motion>", self._sq_drag)
        tk.Frame(left, bg=C["border"], height=1).pack(fill="x", pady=(10, 0))
        hue_wrap = tk.Frame(left, bg="#252845", padx=1, pady=1); hue_wrap.pack(pady=(8, 0))
        self._hue_cv = tk.Canvas(hue_wrap, width=SQ, height=self._HH, highlightthickness=0, cursor="sb_h_double_arrow")
        self._hue_cv.pack()
        self._hue_cv.bind("<Button-1>", self._hue_drag)
        self._hue_cv.bind("<B1-Motion>", self._hue_drag)
        right = tk.Frame(outer, bg=C["bg"]); right.pack(side="left", fill="both")
        pv = tk.Frame(right, bg=C["bg"]); pv.pack(fill="x", pady=(0, 14))
        tk.Label(pv, text="BEFORE", bg=C["bg"], fg=C["text_dim"], font=("Lato", 7, "bold")).pack(side="left")
        self._sw_old = tk.Frame(pv, bg=self._orig, width=54, height=36); self._sw_old.pack(side="left", padx=(5, 2)); self._sw_old.pack_propagate(False)
        self._sw_new = tk.Frame(pv, bg=self._orig, width=54, height=36); self._sw_new.pack(side="left", padx=(2, 5)); self._sw_new.pack_propagate(False)
        tk.Label(pv, text="AFTER", bg=C["bg"], fg=C["text_dim"], font=("Lato", 7, "bold")).pack(side="left")
        for label, var, trough in [("R", self._r, "#5c1212"), ("G", self._g, "#124a22"), ("B", self._b, "#12265c")]:
            row = tk.Frame(right, bg=C["bg"]); row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=C["bg"], fg=C["text"], font=FTB, width=2).pack(side="left")
            tk.Scale(row, variable=var, from_=0, to=255, orient="horizontal", length=200, showvalue=True,
                     bg=C["bg"], fg=C["text_mid"], troughcolor=trough, highlightthickness=0, bd=0,
                     sliderrelief="flat", font=("Lato", 8), command=lambda _v: self._on_rgb()).pack(side="left", padx=(4, 0))
        tk.Frame(right, bg=C["border"], height=1).pack(fill="x", pady=(10, 8))
        hx = tk.Frame(right, bg=C["bg"]); hx.pack(fill="x", pady=(0, 4))
        tk.Label(hx, text="HEX", bg=C["bg"], fg=C["text_dim"], font=("Lato", 7, "bold")).pack(side="left", padx=(0, 8))
        self._hex_entry = tk.Entry(hx, textvariable=self._hex_var, font=("Lato", 10), width=9,
                                   bg=C["card2"], fg=C["accent"], insertbackground=C["accent"],
                                   relief="flat", bd=0, highlightthickness=1,
                                   highlightbackground=C["border"], highlightcolor=C["accent"])
        self._hex_entry.pack(side="left", ipady=4, padx=4)
        self._hex_entry.bind("<Return>", self._on_hex); self._hex_entry.bind("<FocusOut>", self._on_hex)
        hsv_row = tk.Frame(right, bg=C["bg"]); hsv_row.pack(fill="x", pady=(8, 0))
        self._lh = tk.Label(hsv_row, text="H: 0°", bg=C["bg"], fg=C["text_dim"], font=FTS)
        self._ls = tk.Label(hsv_row, text="S: 0%", bg=C["bg"], fg=C["text_dim"], font=FTS)
        self._lv = tk.Label(hsv_row, text="V: 100%", bg=C["bg"], fg=C["text_dim"], font=FTS)
        for lbl in (self._lh, self._ls, self._lv): lbl.pack(side="left", padx=(0, 10))
        btn_row = tk.Frame(right, bg=C["bg"]); btn_row.pack(fill="x", pady=(18, 0))
        tk.Button(btn_row, text="Cancel", font=FT, bg=C["card2"], fg=C["text_mid"],
                  activebackground=C["border2"], activeforeground=C["text"],
                  relief="flat", bd=0, padx=12, pady=7, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(4, 0))
        tk.Button(btn_row, text="✓  Apply", font=FTB, bg=C["accent"], fg="#fff",
                  activebackground=C["accent_dim"], activeforeground="#fff",
                  relief="flat", bd=0, padx=16, pady=7, cursor="hand2",
                  command=self._ok).pack(side="right")

    def _render_sq(self):
        SQ = self._SQ
        try:
            import numpy as np
            from PIL import Image as _PI
            from PIL import ImageTk as _ITk
            xs = np.linspace(0, 1, SQ); ys = np.linspace(1, 0, SQ)
            S, V = np.meshgrid(xs, ys); h = self._h
            hi = np.floor(h * 6).astype(int) % 6; f = h * 6 - np.floor(h * 6)
            p = V * (1 - S); q = V * (1 - f * S); t_ = V * (1 - (1 - f) * S)
            cR = np.select([hi==0, hi==1, hi==2, hi==3, hi==4], [V, q, p, p, t_], V)
            cG = np.select([hi==0, hi==1, hi==2, hi==3, hi==4], [t_, V, V, q, p], p)
            cB = np.select([hi==0, hi==1, hi==2, hi==3, hi==4], [p, p, t_, V, V], q)
            rgb = (np.stack([cR, cG, cB], axis=2) * 255).astype(np.uint8)
            photo = _ITk.PhotoImage(_PI.fromarray(rgb, "RGB"))
        except Exception:
            photo = tk.PhotoImage(width=SQ, height=SQ)
            rows = []
            for y in range(SQ):
                v = 1. - y / max(SQ - 1, 1)
                cols = [_ng_rgb_to_hex(*[int(c * 255) for c in colorsys.hsv_to_rgb(self._h, x / max(SQ - 1, 1), v)]) for x in range(SQ)]
                rows.append("{" + ' '.join(cols) + "}")
            photo.put(' '.join(rows))
        self._sq_photo = photo
        self._sq_cv.delete("all")
        self._sq_cv.create_image(0, 0, anchor="nw", image=photo)

    def _render_hue(self):
        SQ = self._SQ; HH = self._HH
        try:
            import numpy as np
            from PIL import Image as _PI
            from PIL import ImageTk as _ITk
            xs = np.linspace(0, 1, SQ)
            r, g, b = np.vectorize(lambda h: colorsys.hsv_to_rgb(h, 1, 1))(xs)
            row = (np.stack([r, g, b], axis=1) * 255).astype(np.uint8)
            arr = np.tile(row[np.newaxis, :, :], (HH, 1, 1))
            photo = _ITk.PhotoImage(_PI.fromarray(arr, "RGB"))
        except Exception:
            photo = tk.PhotoImage(width=SQ, height=HH)
            rows = []
            for _ in range(HH):
                cols = [_ng_rgb_to_hex(*[int(c * 255) for c in colorsys.hsv_to_rgb(x / max(SQ - 1, 1), 1, 1)]) for x in range(SQ)]
                rows.append("{" + ' '.join(cols) + "}")
            photo.put(' '.join(rows))
        self._hue_photo = photo
        self._hue_cv.delete("all")
        self._hue_cv.create_image(0, 0, anchor="nw", image=photo)

    def _refresh_cursors(self):
        for iid in self._sq_cur_ids: self._sq_cv.delete(iid)
        for iid in self._hue_cur_ids: self._hue_cv.delete(iid)
        self._sq_cur_ids = []; self._hue_cur_ids = []
        SQ = self._SQ; cx = int(self._s * (SQ - 1)); cy = int((1. - self._v) * (SQ - 1)); cr = 8
        self._sq_cur_ids = [self._sq_cv.create_oval(cx-cr, cy-cr, cx+cr, cy+cr, outline="#ffffff", width=2),
                            self._sq_cv.create_oval(cx-cr+2, cy-cr+2, cx+cr-2, cy+cr-2, outline="#000000", width=1)]
        hx = int(self._h * (SQ - 1))
        self._hue_cur_ids = [self._hue_cv.create_line(hx, 0, hx, self._HH, fill="#ffffff", width=2),
                             self._hue_cv.create_line(hx, 0, hx, self._HH, fill="#000000", width=1, dash=(3, 3))]

    def _update_preview(self):
        hx = _ng_rgb_to_hex(self._r.get(), self._g.get(), self._b.get())
        self._sw_new.config(bg=hx); self._hex_var.set(hx.upper())
        self._lh.config(text=f"H: {int(self._h * 360)}°")
        self._ls.config(text=f"S: {int(self._s * 100)}%")
        self._lv.config(text=f"V: {int(self._v * 100)}%")

    def _sq_drag(self, ev):
        SQ = self._SQ; self._s = max(0., min(1., ev.x / (SQ - 1))); self._v = max(0., min(1., 1. - ev.y / (SQ - 1)))
        self._sq_cv.delete("all"); self._sq_cv.create_image(0, 0, anchor="nw", image=self._sq_photo)
        cx = int(self._s * (SQ - 1)); cy = int((1. - self._v) * (SQ - 1)); cr = 8
        self._sq_cv.create_oval(cx-cr, cy-cr, cx+cr, cy+cr, outline="#ffffff", width=2)
        self._sq_cv.create_oval(cx-cr+2, cy-cr+2, cx+cr-2, cy+cr-2, outline="#000000", width=1)
        r, g, b = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        self._busy = True; self._r.set(int(r*255+.5)); self._g.set(int(g*255+.5)); self._b.set(int(b*255+.5))
        self._busy = False; self._update_preview()

    def _hue_drag(self, ev):
        self._h = max(0., min(1., ev.x / (self._SQ - 1)))
        self._render_sq(); self._refresh_cursors()
        r, g, b = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        self._busy = True; self._r.set(int(r*255+.5)); self._g.set(int(g*255+.5)); self._b.set(int(b*255+.5))
        self._busy = False; self._update_preview()

    def _on_rgb(self):
        if self._busy: return
        self._busy = True
        self._h, self._s, self._v = colorsys.rgb_to_hsv(self._r.get()/255, self._g.get()/255, self._b.get()/255)
        self._render_sq(); self._render_hue(); self._refresh_cursors(); self._update_preview()
        self._busy = False

    def _on_hex(self, _ = None):
        val = self._hex_var.get().strip().lstrip("#")
        if len(val) == 6:
            try: ri, gi, bi = int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16)
            except ValueError: return
            if self._busy: return
            self._busy = True; self._r.set(ri); self._g.set(gi); self._b.set(bi)
            self._h, self._s, self._v = colorsys.rgb_to_hsv(ri/255, gi/255, bi/255)
            self._render_sq(); self._render_hue(); self._refresh_cursors(); self._update_preview()
            self._busy = False

    def _ok(self):
        self.result = _ng_rgb_to_hex(self._r.get(), self._g.get(), self._b.get()).upper()
        self.destroy()


# ── main app ──────────────────────────────────────────────────────────────────

class ThemeLab:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CHSuite — Theme Lab")
        self.root.geometry("460x840")
        self.root.resizable(False, True)
        self.root.configure(bg="#12141a")

        self._conn: "socket.socket | None" = None
        self._conn_lock = threading.Lock()
        self._themes_dir: "Path | None" = None
        self._exe_path: "Path | None" = None

        self.current_theme: dict = dict(_DEFAULTS)

        self._build_ui()
        # Kick off the connection loop right away
        threading.Thread(target=self._connection_loop, daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg="#12141a")
        hdr.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(hdr, text="CHSUITE THEME LAB", fg="#6c3bff", bg="#12141a",
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        # Status
        self._status_var = tk.StringVar(value="Searching for CHSuite\u2026")
        self._status_lbl = tk.Label(
            self.root, textvariable=self._status_var,
            fg="#f59e0b", bg="#12141a", font=("Segoe UI", 8), anchor="w", padx=20)
        self._status_lbl.pack(fill="x")

        # Top buttons
        btn_row = tk.Frame(self.root, bg="#12141a")
        btn_row.pack(fill="x", padx=20, pady=(8, 4))
        _btn_cfg = dict(bg="#1c1f26", fg="white", relief="flat",
                        font=("Segoe UI", 9), padx=8, pady=5, cursor="hand2",
                        activebackground="#2a2d3a", activeforeground="white")
        tk.Button(btn_row, text="\U0001f4c2  Load",
                  command=self._import_theme, **_btn_cfg
                  ).pack(side="left", expand=True, fill="x", padx=(0, 3))
        tk.Button(btn_row, text="\U0001f4be  Save",
                  command=self._export_theme, **_btn_cfg
                  ).pack(side="left", expand=True, fill="x", padx=3)
        tk.Button(btn_row, text="\U0001f504  Reconnect",
                  command=self._manual_reconnect, **_btn_cfg
                  ).pack(side="left", expand=True, fill="x", padx=(3, 0))

        # Push button
        self._push_btn = tk.Button(
            self.root, text="\u26a1  PUSH TO CHSUITE",
            font=("Segoe UI", 10, "bold"), command=self._push_theme,
            bg="#6c3bff", fg="white", pady=10, relief="flat", cursor="hand2",
            activebackground="#4e2bbb", activeforeground="white")
        self._push_btn.pack(fill="x", padx=20, pady=(4, 8))

        # Divider
        tk.Frame(self.root, bg="#2a2d3a", height=1).pack(fill="x", padx=20)

        # Scrollable colour list
        outer = tk.Frame(self.root, bg="#12141a")
        outer.pack(fill="both", expand=True, padx=20, pady=(8, 10))

        self._canvas = tk.Canvas(outer, bg="#12141a", highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._list_frame = tk.Frame(self._canvas, bg="#12141a")
        self._list_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._list_frame, anchor="nw", width=400)
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Mouse-wheel scroll
        self._canvas.bind("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._refresh_list()

    def _refresh_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        # Group keys visually
        groups = [
            ("Backgrounds", ("bg", "panel", "card", "card2", "sidebar")),
            ("Borders",     ("border", "border2")),
            ("Accents",     ("accent", "accent_dim", "accent2", "accent3")),
            ("Text",        ("text", "text_dim", "text_mid")),
            ("States",      ("success", "warn", "error")),
            ("Navigation",  ("selected", "hover", "nav_active", "nav_hover")),
        ]

        for group_name, keys in groups:
            # Group label
            glbl = tk.Label(self._list_frame, text=group_name.upper(),
                            fg="#4e2bbb", bg="#12141a",
                            font=("Segoe UI", 8, "bold"), anchor="w")
            glbl.pack(fill="x", pady=(10, 2))
            tk.Frame(self._list_frame, bg="#2a2d3a", height=1).pack(fill="x", pady=(0, 4))

            for key in keys:
                val = self.current_theme.get(key, "#888888")
                row = tk.Frame(self._list_frame, bg="#12141a", pady=2)
                row.pack(fill="x")

                tk.Label(row, text=key, fg="#9aa3bf", bg="#12141a",
                         font=("Consolas", 10), width=14, anchor="w").pack(side="left")
                tk.Label(row, text=val.upper(), fg="#7a7f9a", bg="#12141a",
                         font=("Consolas", 9), width=9, anchor="w").pack(side="left")

                # Colour swatch / picker
                tk.Button(
                    row, bg=val, width=5, relief="flat", cursor="hand2",
                    activebackground=val,
                    command=lambda k=key: self._pick_color(k)
                ).pack(side="right", padx=(0, 4), ipady=9)

    # ── colour picking ────────────────────────────────────────────────────────

    def _pick_color(self, key: str):
        old = self.current_theme.get(key, "#888888")
        dlg = _ColorPickerDialog(self.root, old, title=f"Pick color — {key}")
        if dlg.result:
            self.current_theme[key] = dlg.result.upper()
            self._push_theme()
            self._refresh_list()

    # ── IPC push ──────────────────────────────────────────────────────────────

    def _push_theme(self):
        with self._conn_lock:
            conn = self._conn
        if conn is None:
            self._set_status("Not connected \u2014 press \U0001f504 Reconnect", "#ef4444")
            return
        try:
            conn.sendall(_ipc_pack({"type": "apply", "colors": self.current_theme}))
        except Exception as exc:
            self._set_status(f"Push failed: {exc}", "#ef4444")
            with self._conn_lock:
                self._conn = None

    # ── connection ────────────────────────────────────────────────────────────

    def _connection_loop(self):
        """Background loop: try to (re)connect whenever not connected."""
        while True:
            with self._conn_lock:
                connected = self._conn is not None
            if not connected:
                self._try_connect()
            time.sleep(6)

    def _manual_reconnect(self):
        with self._conn_lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
            self._conn = None
        self._set_status("Reconnecting\u2026", "#f59e0b")
        threading.Thread(target=self._try_connect, daemon=True).start()

    def _try_connect(self):
        """Try once to find + connect to CHSuite. Updates status on all outcomes."""
        # Find exe if we don't have one
        if self._exe_path is None:
            self._exe_path = _find_exe()

        # Launch CHSuite if it isn't running yet
        if not _exe_is_running():
            if self._exe_path:
                self._set_status("Launching CHSuite\u2026", "#f59e0b")
                try:
                    if sys.platform == "win32":
                        subprocess.Popen(
                            [str(self._exe_path)],
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        subprocess.Popen(
                            [str(self._exe_path)],
                            start_new_session=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    time.sleep(3.5)   # let CHSuite open its socket
                except Exception as exc:
                    self._set_status(f"Launch failed: {exc}", "#ef4444")
                    return
            else:
                self._set_status(
                    f"{EXE_NAME} not found. Place ThemeGen beside it or launch it manually.",
                    "#ef4444")
                return

        # Try to connect (up to 8 attempts, 1.5 s apart)
        self._set_status("Connecting to CHSuite\u2026", "#f59e0b")
        for _ in range(8):
            try:
                conn = socket.create_connection(("127.0.0.1", IPC_PORT), timeout=3)
                hello = _ipc_recv(conn, timeout=6.0)
                if hello and hello.get("type") == "hello":
                    # Sync live colours from CHSuite
                    for k, v in hello.get("colors", {}).items():
                        if k in _THEME_KEYS and isinstance(v, str) and v.startswith("#"):
                            self.current_theme[k] = v.upper()
                    if hello.get("themes_dir"):
                        self._themes_dir = Path(hello["themes_dir"])

                with self._conn_lock:
                    self._conn = conn

                self._set_status("Connected to CHSuite  \u2713", "#22c55e")
                self.root.after(0, self._refresh_list)
                return
            except Exception:
                time.sleep(1.5)

        self._set_status(
            "Couldn't connect. Is CHSuite running? Press \U0001f504 Reconnect to retry.",
            "#ef4444")

    # ── status helper ─────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "#7a7f9a"):
        def _do():
            self._status_var.set(text)
            self._status_lbl.config(fg=color)
        self.root.after(0, _do)

    # ── import / export ───────────────────────────────────────────────────────

    def _import_theme(self):
        initial = str(self._themes_dir) if self._themes_dir and self._themes_dir.is_dir() \
                  else os.getcwd()
        path = filedialog.askopenfilename(
            initialdir=initial,
            filetypes=[("JSON theme", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            for k, v in raw.items():
                if k in _THEME_KEYS and isinstance(v, str) and v.startswith("#"):
                    self.current_theme[k] = v.upper()
            self._push_theme()
            self._refresh_list()
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc), parent=self.root)

    def _export_theme(self):
        initial = str(self._themes_dir) if self._themes_dir and self._themes_dir.is_dir() \
                  else os.getcwd()
        path = filedialog.asksaveasfilename(
            initialdir=initial,
            defaultextension=".json",
            filetypes=[("JSON theme", "*.json"), ("All files", "*.*")])
        if not path:
            return
        name = Path(path).stem
        data = {"_name": name}
        data.update({k: self.current_theme.get(k, _DEFAULTS.get(k, "#000000"))
                     for k in _THEME_KEYS})
        try:
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
            messagebox.showinfo("Saved", f"Theme '{name}' saved.\n\n{path}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc), parent=self.root)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    ThemeLab(root)
    root.mainloop()

if __name__ == "__main__":
    main()
