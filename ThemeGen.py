import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
import json
import os

# Import the module carefully to access the global dictionary C
import CHSuite as CHS_Module 
from CHSuite import CHSuite

class ThemeLab:
    def __init__(self, lab_root, app_instance):
        self.root = lab_root
        self.app = app_instance
        self.root.title("CHSuite Theme Lab")
        self.root.geometry("420x800")
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#12141a")

        # Initial pull of hex colors
        self.current_theme = {k: v for k, v in CHS_Module.C.items() if isinstance(v, str) and v.startswith("#")}
        
        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="CHSUITE THEME DESIGNER", fg="#6c3bff", bg="#12141a", font=("Segoe UI", 12, "bold")).pack(pady=15)

        btn_frame = tk.Frame(self.root, bg="#12141a")
        btn_frame.pack(fill="x", padx=20, pady=5)
        
        tk.Button(btn_frame, text="📂 Load", command=self.import_theme, bg="#1c1f26", fg="white", relief="flat").pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(btn_frame, text="💾 Save", command=self.export_theme, bg="#1c1f26", fg="white", relief="flat").pack(side="left", expand=True, fill="x", padx=2)
        
        # ── THE INJECTION BUTTON ──────────────────────────────────────────
        refresh_btn = tk.Button(self.root, text="⚡ INJECT & REFRESH UI", font=("Segoe UI", 10, "bold"),
                                command=self.inject_theme, bg="#6c3bff", fg="white", 
                                pady=10, relief="flat", cursor="hand2")
        refresh_btn.pack(fill="x", padx=20, pady=10)

        # Scrollable List
        list_container = tk.Frame(self.root, bg="#12141a")
        list_container.pack(fill="both", expand=True, padx=20, pady=10)

        canvas = tk.Canvas(list_container, bg="#12141a", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        self.scroll_content = tk.Frame(canvas, bg="#12141a")

        self.scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_content, anchor="nw", width=360)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.refresh_color_list()

    def refresh_color_list(self):
        for widget in self.scroll_content.winfo_children():
            widget.destroy()
        for key in sorted(self.current_theme.keys()):
            val = self.current_theme[key]
            row = tk.Frame(self.scroll_content, bg="#12141a", pady=2)
            row.pack(fill="x")
            tk.Label(row, text=key, fg="#9aa3bf", bg="#12141a", font=("Consolas", 10), width=15, anchor="w").pack(side="left")
            btn = tk.Button(row, bg=val, width=12, relief="flat", command=lambda k=key: self.pick_color(k))
            btn.pack(side="right", padx=5)

    def pick_color(self, key):
        color = colorchooser.askcolor(initialcolor=self.current_theme[key])[1]
        if color:
            self.current_theme[key] = color
            self.inject_theme()
            self.refresh_color_list()

    def inject_theme(self):
        """Recursively walks through every widget and forces a color change"""
        # 1. Update the Global Dictionary for future widgets
        for k, v in self.current_theme.items():
            CHS_Module.C[k] = v

        # 2. Start the recursive injection on the main app
        self._update_widget_recursive(self.app)
        self.app.update_idletasks()
        print("[Lab] Injection Complete.")

    def _update_widget_recursive(self, widget):
        """The magic 'Injection' function"""
        try:
            # Map common widget attributes to your C dictionary keys
            # This is a 'best effort' injection
            w_type = widget.winfo_class()
            
            # Update Backgrounds
            if w_type in ("Frame", "Label", "Canvas", "Tk", "Toplevel"):
                widget.configure(bg=CHS_Module.C.get("bg"))
            
            # Update Buttons & Inputs
            if w_type in ("Button", "Entry", "Text"):
                widget.configure(bg=CHS_Module.C.get("card"), fg=CHS_Module.C.get("text"))

            # Update Labels
            if w_type == "Label":
                widget.configure(fg=CHS_Module.C.get("text"))

        except:
            pass

        # Recursively update all children of this widget
        for child in widget.winfo_children():
            self._update_widget_recursive(child)

    def import_theme(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            with open(path, 'r') as f:
                data = json.load(f)
                self.current_theme.update({k: v for k, v in data.items() if str(v).startswith("#")})
            self.inject_theme()
            self.refresh_color_list()

    def export_theme(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            theme_data = {"_name": os.path.basename(path).replace(".json", "")}
            theme_data.update(self.current_theme)
            with open(path, "w") as f:
                json.dump(theme_data, f, indent=2)
            messagebox.showinfo("Exported", "Theme Saved!")

if __name__ == "__main__":
    main_app = CHSuite()
    lab_root = tk.Toplevel(main_app)
    lab = ThemeLab(lab_root, main_app)
    main_app.mainloop()