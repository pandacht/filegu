# tabs/settings_tab.py — Settings tab for persistent app configuration

import tkinter as tk
from tkinter import ttk, messagebox
from utils.constants import (
    ACCENT, ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED,
    SUCCESS, DANGER,
)
from utils import config as cfg


class SettingsTab(tk.Frame):
    def __init__(self, parent, app_ref):
        super().__init__(parent, bg=BG)
        self._app = app_ref
        self._vars = {}   # key_path → tk var
        self._build(self)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self, parent):
        # Scrollable canvas
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb    = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner     = tk.Frame(canvas, bg=BG)
        canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        conf = cfg.load()

        # ── Scanner settings ──────────────────────────────────────────────────
        self._section(inner, "VIRUS SCANNER")

        self._row_spinbox(inner, "Threads",
                          "How many files to scan in parallel. Higher = faster but uses more CPU.",
                          "scanner.threads", conf["scanner"]["threads"],
                          from_=1, to=32)

        self._row_radio(inner, "Scan depth",
                        "How deep into subfolders to go.",
                        "scanner.depth", conf["scanner"]["depth"],
                        [("Full (everything)", "full"),
                         ("3 levels deep",     "3"),
                         ("1 level only (fast)", "1")])

        self._row_check(inner, "Skip media & font files",
                        "Skip .jpg, .png, .mp4, .ttf etc. — they can't execute.",
                        "scanner.skip_media", conf["scanner"]["skip_media"])

        self._row_check(inner, "Executables & scripts only",
                        "Only scan .exe, .dll, .bat, .ps1, .js etc.",
                        "scanner.exe_only", conf["scanner"]["exe_only"])

        self._row_tags(inner, "Extra extensions to skip",
                       "Additional file extensions to never scan. One per line, with dot. e.g.  .crp  .pak  .unity3d",
                       "scanner.extra_skip_ext", conf["scanner"]["extra_skip_ext"])

        self._row_tags(inner, "Extra folders to skip",
                       "Folder names to skip during scan. e.g.  Steam  Games  node_modules",
                       "scanner.extra_skip_dirs", conf["scanner"]["extra_skip_dirs"])

        # ── Search settings ───────────────────────────────────────────────────
        self._section(inner, "SEARCH")

        self._row_radio(inner, "Default match mode",
                        "Which mode is selected when you open the Search tab.",
                        "search.default_mode", conf["search"]["default_mode"],
                        [("Keyword (partial match)", "keyword"),
                         ("Exact name",              "exact")])

        self._row_radio(inner, "Default search for",
                        "What to search for by default.",
                        "search.default_type", conf["search"]["default_type"],
                        [("Files & folders", "both"),
                         ("Files only",      "files"),
                         ("Folders only",    "folders")])

        # ── UI settings ───────────────────────────────────────────────────────
        self._section(inner, "INTERFACE")

        self._row_radio(inner, "Default tab on startup",
                        "Which tab opens first when you launch the app.",
                        "ui.default_tab", conf["ui"]["default_tab"],
                        [("Search",        "Search"),
                         ("Cache Cleaner", "Cache Cleaner"),
                         ("Virus Scanner", "Virus Scanner")])

        # ── Save / reset buttons ──────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(24, 32))

        tk.Button(btn_row, text="💾  Save settings",
                  command=self._save,
                  font=("Segoe UI", 12, "bold"), bg=ACCENT, fg="white",
                  relief="flat", bd=0, padx=20, pady=10, cursor="hand2",
                  activebackground=ACCENT2, activeforeground="white"
                  ).pack(side="left")

        tk.Button(btn_row, text="↺  Reset to defaults",
                  command=self._reset,
                  font=("Segoe UI", 11), bg=SURFACE, fg=MUTED,
                  relief="flat", bd=0, padx=16, pady=10, cursor="hand2"
                  ).pack(side="left", padx=(12, 0))

        self._status_var = tk.StringVar(value="")
        tk.Label(btn_row, textvariable=self._status_var,
                 font=("Segoe UI", 10), bg=BG, fg=SUCCESS).pack(side="left", padx=(16, 0))

    # ── Section header ────────────────────────────────────────────────────────
    def _section(self, parent, title):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=24, pady=(24, 8))
        tk.Label(row, text=title, font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=ACCENT2).pack(side="left")
        tk.Frame(row, bg=SURFACE2, height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=6)

    def _label_col(self, parent, label, desc):
        """Left column: setting name + description."""
        col = tk.Frame(parent, bg=SURFACE, width=300)
        col.pack(side="left", fill="y", padx=(16, 0), pady=10)
        col.pack_propagate(False)
        tk.Label(col, text=label, font=("Segoe UI", 11),
                 bg=SURFACE, fg=TEXT, anchor="w").pack(anchor="w")
        tk.Label(col, text=desc, font=("Segoe UI", 9),
                 bg=SURFACE, fg=MUTED, anchor="w", wraplength=280, justify="left"
                 ).pack(anchor="w", pady=(2, 0))
        return col

    # ── Row types ─────────────────────────────────────────────────────────────
    def _row_frame(self, parent):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        return row

    def _row_check(self, parent, label, desc, key, default):
        row = self._row_frame(parent)
        self._label_col(row, label, desc)
        var = tk.BooleanVar(value=default)
        self._vars[key] = var
        tk.Checkbutton(row, variable=var, bg=SURFACE, fg=TEXT,
                       selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=TEXT, relief="flat"
                       ).pack(side="left", padx=(20, 0))

    def _row_spinbox(self, parent, label, desc, key, default, from_=1, to=32):
        row = self._row_frame(parent)
        self._label_col(row, label, desc)
        var = tk.IntVar(value=default)
        self._vars[key] = var
        sb = tk.Spinbox(row, from_=from_, to=to, textvariable=var, width=5,
                        font=("Segoe UI", 11), bg=SURFACE2, fg=TEXT,
                        buttonbackground=SURFACE2, relief="flat",
                        insertbackground=ACCENT)
        sb.pack(side="left", padx=(20, 0), pady=10)

    def _row_radio(self, parent, label, desc, key, default, options):
        row = self._row_frame(parent)
        self._label_col(row, label, desc)
        var = tk.StringVar(value=default)
        self._vars[key] = var
        rb_col = tk.Frame(row, bg=SURFACE)
        rb_col.pack(side="left", padx=(20, 0), pady=10)
        for text, val in options:
            tk.Radiobutton(rb_col, text=text, variable=var, value=val,
                           font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                           selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=TEXT, relief="flat"
                           ).pack(anchor="w", pady=1)

    def _row_tags(self, parent, label, desc, key, default):
        """Multi-line text box for list values (extensions / folder names)."""
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        self._label_col(row, label, desc)

        txt_frame = tk.Frame(row, bg=SURFACE2)
        txt_frame.pack(side="left", fill="both", expand=True,
                       padx=(20, 16), pady=10)
        txt = tk.Text(txt_frame, font=("Consolas", 10), bg=SURFACE2, fg=TEXT,
                      insertbackground=ACCENT, relief="flat", bd=6,
                      height=4, wrap="none")
        txt.pack(fill="both", expand=True)
        # Pre-fill with existing values
        txt.insert("1.0", "\n".join(default))
        self._vars[key] = txt   # store the Text widget directly

    # ── Save / reset ──────────────────────────────────────────────────────────
    def _collect(self) -> dict:
        """Read all widgets and build a config dict."""
        conf = cfg.load()
        for key, var in self._vars.items():
            section, field = key.split(".", 1)
            if isinstance(var, tk.Text):
                # Parse multi-line text into a list
                raw   = var.get("1.0", "end").strip()
                items = [line.strip() for line in raw.splitlines() if line.strip()]
                conf[section][field] = items
            elif isinstance(var, tk.BooleanVar):
                conf[section][field] = var.get()
            elif isinstance(var, tk.IntVar):
                conf[section][field] = var.get()
            elif isinstance(var, tk.StringVar):
                conf[section][field] = var.get()
        return conf

    def _save(self):
        conf = self._collect()
        if cfg.save(conf):
            self._status_var.set("✓ Saved")
            self._app.after(2500, lambda: self._status_var.set(""))
        else:
            messagebox.showerror("Save failed",
                                 "Could not write config.json — check file permissions.")

    def _reset(self):
        if not messagebox.askyesno("Reset settings",
                                   "Reset all settings to defaults?",
                                   default="no"):
            return
        if cfg.save(cfg._deep_copy(cfg.DEFAULTS)):
            # Reload the tab
            for widget in self.winfo_children():
                widget.destroy()
            self._vars = {}
            self._build(self)
            self._status_var.set("✓ Reset to defaults")
            self._app.after(2500, lambda: self._status_var.set(""))