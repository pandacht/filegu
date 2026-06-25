# tabs/settings_tab.py — Settings tab for persistent app configuration

import tkinter as tk
from tkinter import ttk, messagebox
from utils.constants import (
    ACCENT, ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED, SUCCESS
)
from utils import config as cfg
from utils.lang import t, available_languages


class SettingsTab(tk.Frame):
    def __init__(self, parent, app_ref):
        super().__init__(parent, bg=BG)
        self._app  = app_ref
        self._vars = {}
        self._placeholders = {}
        self._canvas = None
        self._build(self)

    def _build(self, parent):
        # Scrollable canvas
        self._canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        inner     = tk.Frame(self._canvas, bg=BG)
        canvas_win = self._canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            canvas_win, width=e.width))

        def _on_enter(e):
            self._canvas.bind_all("<MouseWheel>",
                lambda ev: self._canvas.yview_scroll(int(-1*(ev.delta/120)), "units"))
        def _on_leave(e):
            self._canvas.unbind_all("<MouseWheel>")

        self._canvas.bind("<Enter>", _on_enter)
        self._canvas.bind("<Leave>", _on_leave)
        inner.bind("<Enter>", _on_enter)
        inner.bind("<Leave>", _on_leave)

        conf = cfg.load()

        # ── Scanner ───────────────────────────────────────────────────────────
        self._section(inner, t("settings.section_virus"))
        self._row_spinbox(inner, t("settings.threads"),
                          t("settings.threads_desc"),
                          "scanner.threads", conf["scanner"]["threads"], from_=1, to=32)
        self._row_check(inner, t("settings.skip_media"),
                        t("settings.skip_media_desc"),
                        "scanner.skip_media", conf["scanner"]["skip_media"])
        self._row_check(inner, t("settings.exe_only"),
                        t("settings.exe_only_desc"),
                        "scanner.exe_only", conf["scanner"]["exe_only"])
        self._row_entry(inner, t("settings.vt_key"),
                        t("settings.vt_key_desc"),
                        "scanner.virustotal_key", conf["scanner"].get("virustotal_key", ""),
                        secret=True)
        self._row_tags(inner, t("settings.extra_ext"),
                       t("settings.extra_ext_desc"),
                       "scanner.extra_skip_ext", conf["scanner"]["extra_skip_ext"])
        self._row_tags(inner, t("settings.extra_dirs"),
                       t("settings.extra_dirs_desc"),
                       "scanner.extra_skip_dirs", conf["scanner"]["extra_skip_dirs"])

        # ── Search ────────────────────────────────────────────────────────────
        self._section(inner, t("settings.section_search"))
        self._row_radio(inner, t("settings.default_mode"), "",
                        "search.default_mode", conf["search"]["default_mode"],
                        [(t("settings.keyword"), "keyword"),
                         (t("settings.exact"), "exact")])
        self._row_radio(inner, t("settings.default_type"), "",
                        "search.default_type", conf["search"]["default_type"],
                        [(t("search.for_both"), "both"),
                         (t("search.for_files"), "files"),
                         (t("search.for_folders"), "folders")])

        # ── Interface ─────────────────────────────────────────────────────────
        self._section(inner, t("settings.section_ui"))
        self._row_radio(inner, t("settings.default_tab"), t("settings.default_tab_desc"),
                        "ui.default_tab", conf["ui"]["default_tab"],
                        [(t("tab.search"),  "Search"),
                         (t("tab.cache"),   "Cache Cleaner"),
                         (t("tab.virus"),   "Virus Scanner")])

        langs = available_languages()
        self._row_radio(inner, t("settings.language"), t("settings.language_desc"),
                        "ui.language", conf["ui"].get("language", "en"),
                        [(name, code) for code, name in langs])

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(24, 32))
        tk.Button(btn_row, text=t("settings.btn_save"),
                  command=self._save,
                  font=("Segoe UI", 12, "bold"), bg=ACCENT, fg="white",
                  relief="flat", bd=0, padx=20, pady=10, cursor="hand2",
                  activebackground=ACCENT2, activeforeground="white"
                  ).pack(side="left")
        tk.Button(btn_row, text=t("settings.btn_reset"),
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
        row.pack(fill="x", padx=24, pady=(20, 6))
        tk.Label(row, text=title, font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=ACCENT2).pack(side="left")
        tk.Frame(row, bg=SURFACE2, height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=6)

    # ── Row builders ──────────────────────────────────────────────────────────
    def _row_check(self, parent, label, desc, key, default):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        var = tk.BooleanVar(value=default)
        self._vars[key] = var
        cb = tk.Checkbutton(row, variable=var, text=label,
                             font=("Segoe UI", 11), bg=SURFACE, fg=TEXT,
                             selectcolor=SURFACE2, activebackground=SURFACE,
                             activeforeground=TEXT, relief="flat")
        cb.pack(side="left", padx=16, pady=8)
        if desc:
            tk.Label(row, text=desc, font=("Segoe UI", 9),
                     bg=SURFACE, fg=MUTED).pack(side="left", padx=(0, 16))

    def _row_spinbox(self, parent, label, desc, key, default, from_=1, to=32):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        tk.Label(row, text=label, font=("Segoe UI", 11),
                 bg=SURFACE, fg=TEXT, width=22, anchor="w").pack(side="left", padx=16, pady=8)
        var = tk.IntVar(value=default)
        self._vars[key] = var
        tk.Spinbox(row, from_=from_, to=to, textvariable=var, width=5,
                   font=("Segoe UI", 11), bg=SURFACE2, fg=TEXT,
                   buttonbackground=SURFACE2, relief="flat",
                   insertbackground=ACCENT).pack(side="left", pady=8)
        if desc:
            tk.Label(row, text=desc, font=("Segoe UI", 9),
                     bg=SURFACE, fg=MUTED).pack(side="left", padx=(12, 16))

    def _row_radio(self, parent, label, desc, key, default, options):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        tk.Label(row, text=label, font=("Segoe UI", 11),
                 bg=SURFACE, fg=TEXT, width=22, anchor="w").pack(side="left", padx=16, pady=8)
        var = tk.StringVar(value=default)
        self._vars[key] = var
        opts_frame = tk.Frame(row, bg=SURFACE)
        opts_frame.pack(side="left", pady=6)
        for text, val in options:
            tk.Radiobutton(opts_frame, text=text, variable=var, value=val,
                           font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                           selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=TEXT, relief="flat"
                           ).pack(side="left", padx=(0, 12))

    def _row_entry(self, parent, label, desc, key, default, secret=False):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        tk.Label(row, text=label, font=("Segoe UI", 11),
                 bg=SURFACE, fg=TEXT, width=22, anchor="w").pack(side="left", padx=16, pady=8)
        var = tk.StringVar(value=default)
        self._vars[key] = var
        ef = tk.Frame(row, bg=SURFACE2)
        ef.pack(side="left", fill="x", expand=True, pady=6, padx=(0, 16))
        entry = tk.Entry(ef, textvariable=var, font=("Segoe UI", 10),
                         bg=SURFACE2, fg=TEXT, insertbackground=ACCENT,
                         relief="flat", bd=6,
                         show="•" if secret else "")
        entry.pack(fill="x")
        if desc:
            tk.Label(row, text=desc, font=("Segoe UI", 9),
                     bg=SURFACE, fg=MUTED).pack(side="left", padx=(0, 16))

    def _row_tags(self, parent, label, desc, key, default):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=24, pady=2)
        hdr = tk.Frame(row, bg=SURFACE)
        hdr.pack(fill="x", padx=16, pady=(8, 2))
        tk.Label(hdr, text=label, font=("Segoe UI", 11),
                 bg=SURFACE, fg=TEXT).pack(side="left")
        txt_frame = tk.Frame(row, bg=SURFACE2)
        txt_frame.pack(fill="x", padx=16, pady=(0, 8))
        txt = tk.Text(txt_frame, font=("Consolas", 10), bg=SURFACE2,
                      insertbackground=ACCENT, relief="flat", bd=6,
                      height=3, wrap="none")
        txt.pack(fill="x")

        placeholder = desc

        if default:
            txt.insert("1.0", "\n".join(default))
            txt.config(fg=TEXT)
        else:
            txt.insert("1.0", placeholder)
            txt.config(fg=MUTED)

        def on_focus_in(e):
            if txt.get("1.0", "end-1c") == placeholder:
                txt.delete("1.0", "end")
                txt.config(fg=TEXT)

        def on_focus_out(e):
            if not txt.get("1.0", "end-1c").strip():
                txt.insert("1.0", placeholder)
                txt.config(fg=MUTED)

        txt.bind("<FocusIn>",  on_focus_in)
        txt.bind("<FocusOut>", on_focus_out)

        self._vars[key]          = txt
        self._placeholders[key]  = placeholder

    # ── Save / reset ──────────────────────────────────────────────────────────
    def _collect(self) -> dict:
        conf = cfg.load()
        for key, var in self._vars.items():
            parts   = key.split(".", 1)
            section = parts[0]
            field   = parts[1]
            if isinstance(var, tk.Text):
                raw = var.get("1.0", "end-1c").strip()
                # Don't save placeholder text
                if raw == self._placeholders.get(key, ""):
                    raw = ""
                items = [l.strip() for l in raw.splitlines() if l.strip()]
                conf[section][field] = items
            elif isinstance(var, tk.BooleanVar):
                conf[section][field] = var.get()
            elif isinstance(var, tk.IntVar):
                conf[section][field] = var.get()
            elif isinstance(var, tk.StringVar):
                conf[section][field] = var.get()
        return conf

    def _save(self):
        old_conf = cfg.load()
        old_lang = old_conf["ui"].get("language", "en")
        conf     = self._collect()
        if cfg.save(conf):
            new_lang = conf["ui"].get("language", "en")
            if old_lang != new_lang:
                self._status_var.set(t("settings.saved"))
                self._app.after(3000, lambda: self._status_var.set(""))
                messagebox.showinfo("Restart required",
                                    "Language changed. Please restart the app to apply.")
            else:
                self._status_var.set(t("settings.saved_no_restart"))
                self._app.after(3000, lambda: self._status_var.set(""))
        else:
            messagebox.showerror("Save failed", t("settings.save_failed"))

    def _reset(self):
        if not messagebox.askyesno("Reset settings",
                                   t("settings.reset_confirm"),
                                   default="no"):
            return
        if cfg.save(cfg._deep_copy(cfg.DEFAULTS)):
            for widget in self.winfo_children():
                widget.destroy()
            self._vars = {}
            self._build(self)
            self._status_var.set(t("settings.reset_done"))
            self._app.after(2500, lambda: self._status_var.set(""))