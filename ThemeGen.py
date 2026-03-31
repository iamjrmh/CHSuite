"""
ThemeGen — CHSuite live theme designer (standalone).

Drop this .py anywhere — it will auto-detect CHSuite.exe in its own folder
or in a running process, connect via a local socket, and push live colour
updates directly into the running CHSuite window.

No need to keep CHSuite as a .py file.
"""
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
import json, os, socket, struct, subprocess, sys, threading, time
from pathlib import Path

# ── constants (must match CHSuite.py) ─────────────────────────────────────────
IPC_PORT = 59832
EXE_NAME = "CHSuite.exe"

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
    return None

def _exe_is_running() -> bool:
    if os.name != "nt":
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH", "/FO", "CSV"],
            creationflags=0x08000000, stderr=subprocess.DEVNULL, timeout=5
        ).decode(errors="replace")
        return EXE_NAME.lower() in out.lower()
    except Exception:
        return False

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
        result = colorchooser.askcolor(initialcolor=old, title=f"Pick color — {key}")
        if result and result[1]:
            self.current_theme[key] = result[1].upper()
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
                    subprocess.Popen(
                        [str(self._exe_path)],
                        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
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
