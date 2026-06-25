# tabs/cache_tab.py — Cache Cleaner tab UI and logic

import os
import shutil
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from utils.constants import (
    ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED,
    SUCCESS, WARNING, DANGER,
)
from utils.lang import t
from utils.fs_helpers import dir_size, fmt_size
from utils.cache_targets import build_cache_targets


class CacheTab(tk.Frame):
    def __init__(self, parent, app_ref):
        super().__init__(parent, bg=BG)
        self._app           = app_ref
        self._cache_targets = build_cache_targets()
        self._cache_vars        = {}   # label → BooleanVar
        self._cache_size_labels = {}   # label → tk.Label
        self._group_vars        = {}   # group → list of BooleanVar
        self._spinner_running   = False
        self._spinner_id        = None

        self._build(self)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(top, text=t("cache.hint"),
                 font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(side="left")

        sel_frame = tk.Frame(top, bg=BG)
        sel_frame.pack(side="right")
        tk.Button(sel_frame, text=t("cache.select_all"),   command=self._select_all,
                  font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(sel_frame, text=t("cache.deselect_all"), command=self._deselect_all,
                  font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2").pack(side="left")

        # Scrollable list
        list_outer = tk.Frame(parent, bg=BG)
        list_outer.pack(fill="both", expand=True, padx=20)

        from tkinter import ttk
        self._canvas = tk.Canvas(list_outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(list_outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        inner      = tk.Frame(self._canvas, bg=BG)
        canvas_win = self._canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(canvas_win, width=e.width))

        # Bind mousewheel to canvas AND inner frame so scrolling works anywhere
        self._bind_scroll(self._canvas)
        self._bind_scroll(inner)

        GROUP_KEYS = {
            "System":   "cache.group_system",
            "Browsers": "cache.group_browsers",
            "Dev":      "cache.group_dev",
            "IDEs":     "cache.group_ides",
            "Apps":     "cache.group_apps",
            "Games":    "cache.group_games",
        }

        current_group = None
        for group, label, paths, desc in self._cache_targets:
            if group != current_group:
                current_group = group
                self._group_vars[group] = []
                gh = tk.Frame(inner, bg=BG)
                gh.pack(fill="x", pady=(16, 4))

                group_label = t(GROUP_KEYS.get(group, group))
                tk.Label(gh, text=group_label.upper(), font=("Segoe UI", 9, "bold"),
                         bg=BG, fg=ACCENT2).pack(side="left")

                tk.Button(gh, text=t("cache.deselect"),
                          command=lambda g=group: self._group_deselect(g),
                          font=("Segoe UI", 8), bg=BG, fg=MUTED,
                          relief="flat", bd=0, padx=6, cursor="hand2").pack(side="right")
                tk.Button(gh, text=t("cache.select"),
                          command=lambda g=group: self._group_select(g),
                          font=("Segoe UI", 8), bg=BG, fg=ACCENT2,
                          relief="flat", bd=0, padx=6, cursor="hand2").pack(side="right")

                tk.Frame(gh, bg=SURFACE2, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

            self._build_row(inner, group, label, paths, desc)

        # Bottom action bar
        bottom = tk.Frame(parent, bg=SURFACE, pady=14)
        bottom.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._status_var,
                 font=("Segoe UI", 10), bg=SURFACE, fg=MUTED).pack(side="left", padx=20)
        self._total_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._total_var,
                 font=("Segoe UI", 11, "bold"), bg=SURFACE, fg=SUCCESS).pack(side="left", padx=8)

        btn_frame = tk.Frame(bottom, bg=SURFACE)
        btn_frame.pack(side="right", padx=20)
        self._scan_btn = tk.Button(btn_frame, text=t("cache.btn_scan"), command=self._scan,
                                   font=("Segoe UI", 11), bg=SURFACE2, fg=TEXT,
                                   relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        self._scan_btn.pack(side="left", padx=(0, 10))
        self._clean_btn = tk.Button(btn_frame, text=t("cache.btn_clean"), command=self._clean,
                                    font=("Segoe UI", 11, "bold"), bg=DANGER, fg="white",
                                    relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        self._clean_btn.pack(side="left")

    def _bind_scroll(self, widget):
        """Bind mousewheel scroll to a widget and all its children recursively."""
        widget.bind("<MouseWheel>",
                    lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        widget.bind("<Enter>",
                    lambda e: widget.bind_all("<MouseWheel>",
                    lambda ev: self._canvas.yview_scroll(int(-1*(ev.delta/120)), "units")))
        widget.bind("<Leave>",
                    lambda e: widget.unbind_all("<MouseWheel>"))

    def _build_row(self, parent, group, label_key, paths, desc_key):
        label = t(label_key) if label_key.startswith("cache.item.") else label_key
        desc  = t(desc_key)  if desc_key.startswith("cache.desc.")  else desc_key
        var = tk.BooleanVar(value=False)
        self._cache_vars[label_key] = var
        self._group_vars[group].append(var)

        row = tk.Frame(parent, bg=SURFACE, pady=0)
        row.pack(fill="x", pady=2)
        self._bind_scroll(row)

        tk.Checkbutton(row, variable=var, text=label,
                       font=("Segoe UI", 11), bg=SURFACE, fg=TEXT,
                       selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=TEXT, relief="flat", anchor="w"
                       ).pack(side="left", padx=(12, 0))
        tk.Label(row, text=desc, font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                 anchor="w").pack(side="left", padx=8, fill="x", expand=True)
        size_lbl = tk.Label(row, text="—", font=("Segoe UI", 10, "bold"),
                            bg=SURFACE, fg=MUTED, width=10, anchor="e")
        size_lbl.pack(side="right", padx=12)
        self._cache_size_labels[label_key] = size_lbl

    # ── Selection helpers ─────────────────────────────────────────────────────
    def _select_all(self):
        for v in self._cache_vars.values():
            v.set(True)

    def _deselect_all(self):
        for v in self._cache_vars.values():
            v.set(False)

    def _group_select(self, group):
        for v in self._group_vars.get(group, []):
            v.set(True)

    def _group_deselect(self, group):
        for v in self._group_vars.get(group, []):
            v.set(False)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _scan(self):
        selected = [l for l, v in self._cache_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning(t("common.warning"), t("cache.nothing_selected"))
            return
        self._status_var.set(t("cache.cleaning"))
        self._total_var.set("")
        self._scan_btn.config(state="disabled")
        self._start_spinner()

        def worker():
            total = 0
            for i, (group, label_key, paths, desc) in enumerate(self._cache_targets):
                if label_key not in selected:
                    continue
                label = t(label_key) if label_key.startswith("cache.item.") else label_key
                self._app.after(0, self._status_var.set,
                                f"{t('cache.scanning').format(label=label, i=list(self._cache_vars.keys()).index(label_key)+1, n=len(selected))}")
                size  = self._measure(label_key, paths)
                total += size
                color = WARNING if size > 50*1024*1024 else (SUCCESS if size > 0 else MUTED)
                disp  = fmt_size(size) if size > 0 else t("cache.not_found")
                self._app.after(0, self._set_size_label, label_key, disp, color)

            def finish():
                self._stop_spinner()
                self._status_var.set(t("cache.scan_complete"))
                self._total_var.set(f"Total: {fmt_size(total)}")
                self._scan_btn.config(state="normal")
            self._app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _clean(self):
        selected = [l for l, v in self._cache_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning(t("common.warning"), t("cache.nothing_selected"))
            return
        if not messagebox.askyesno(
            t("common.confirm_delete"),
            f"Permanently delete cache for {len(selected)} selected categor{'y' if len(selected)==1 else 'ies'}?\n\n"
            + "\n".join(f"  • {s}" for s in selected)
            + "\n\nThis cannot be undone.",
            icon="warning", default="no"
        ):
            return
        self._status_var.set(t("cache.cleaning"))
        self._total_var.set("")
        self._clean_btn.config(state="disabled")
        self._scan_btn.config(state="disabled")
        self._start_spinner()

        def worker():
            freed  = 0
            errors = []
            for group, label_key, paths, desc in self._cache_targets:
                if label_key not in selected:
                    continue
                f, e = self._do_clean(label_key, paths)
                freed  += f
                errors.extend(e)
                self._app.after(0, self._set_size_label, label_key, t("cache.cleaned"), SUCCESS)

            def finish():
                self._stop_spinner()
                self._status_var.set(f"Done — {len(errors)} error(s)" if errors else t("cache.done"))
                self._total_var.set(f"Freed: {fmt_size(freed)}")
                self._clean_btn.config(state="normal")
                self._scan_btn.config(state="normal")
                if errors:
                    messagebox.showwarning(t("cache.errors_title"),
                                           f"{len(errors)} items could not be deleted:\n\n"
                                           + "\n".join(errors[:10]))
            self._app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ── Spinner ───────────────────────────────────────────────────────────────
    def _start_spinner(self):
        self._spinner_running = True
        self._spinner_id      = None
        self._spin()

    def _spin(self):
        if not self._spinner_running:
            return
        current = self._status_var.get().rstrip(". ")
        # Strip old dots
        base = current.rstrip(".")
        dots = (len(current) - len(base)) % 3 + 1
        self._status_var.set(base + "." * dots)
        self._spinner_id = self._app.after(400, self._spin)

    def _stop_spinner(self):
        self._spinner_running = False
        if self._spinner_id:
            self._app.after_cancel(self._spinner_id)
            self._spinner_id = None

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_size_label(self, label, text, color):
        lbl = self._cache_size_labels.get(label)
        if lbl:
            lbl.config(text=text, fg=color)

    def _measure(self, label, paths):
        if label in ("__pycache__", ".mypy_cache", "cache.item.pycache", "cache.item.mypy"):
            dirname = "__pycache__" if "pycache" in label else ".mypy_cache"
            return self._scan_named_dirs(dirname)
        if label in ("Next.js cache", "cache.item.nextjs"):
            return self._scan_named_dirs(".next")
        if label in ("Parcel cache", "cache.item.parcel"):
            return self._scan_named_dirs(".parcel-cache")
        if label in ("Webpack/Vite cache", "cache.item.webpack"):
            return self._scan_named_dirs("node_modules/.cache") + self._scan_named_dirs(".vite")
        total = 0
        for p in paths:
            p = Path(p)
            try:
                if p.exists():
                    total += dir_size(p)
            except (PermissionError, OSError):
                pass
        return total

    def _scan_named_dirs(self, dirname):
        total = 0
        home  = Path.home()
        skip  = {".git", "venv", ".venv", "node_modules"}
        try:
            for dirpath, dirnames, _ in os.walk(home):
                dirnames[:] = [d for d in dirnames if d not in skip]
                if dirname in dirnames:
                    total += dir_size(Path(dirpath) / dirname)
        except Exception:
            pass
        return total

    def _clean_named_dirs(self, dirname):
        freed  = 0
        errors = []
        home   = Path.home()
        skip   = {".git", "venv", ".venv", "node_modules"}
        try:
            for dirpath, dirnames, _ in os.walk(home):
                dirnames[:] = [d for d in dirnames if d not in skip]
                if dirname in dirnames:
                    target = Path(dirpath) / dirname
                    try:
                        freed += dir_size(target)
                        shutil.rmtree(target)
                    except Exception as e:
                        errors.append(str(e))
        except Exception:
            pass
        return freed, errors

    def _do_clean(self, label, paths):
        freed  = 0
        errors = []
        if label in ("__pycache__", ".mypy_cache", "cache.item.pycache", "cache.item.mypy"):
            dirname = "__pycache__" if "pycache" in label else ".mypy_cache"
            home = Path.home()
            skip = {".git", "venv", ".venv", "node_modules"}
            try:
                for dirpath, dirnames, _ in os.walk(home):
                    dirnames[:] = [d for d in dirnames if d not in skip]
                    if dirname in dirnames:
                        target = Path(dirpath) / dirname
                        try:
                            freed += dir_size(target)
                            shutil.rmtree(target)
                        except Exception as e:
                            errors.append(str(e))
            except Exception:
                pass
            return freed, errors

        if label in ("Next.js cache", "cache.item.nextjs"):
            return self._clean_named_dirs(".next")
        if label in ("Parcel cache", "cache.item.parcel"):
            return self._clean_named_dirs(".parcel-cache")
        if label in ("Webpack/Vite cache", "cache.item.webpack"):
            f1, e1 = self._clean_named_dirs("node_modules/.cache")
            f2, e2 = self._clean_named_dirs(".vite")
            return f1 + f2, e1 + e2

        for p in paths:
            p = Path(p)
            if not p.exists():
                continue
            try:
                for child in p.iterdir():
                    try:
                        freed += dir_size(child) if child.is_dir() else child.stat().st_size
                        shutil.rmtree(child) if child.is_dir() else child.unlink()
                    except Exception as e:
                        errors.append(f"{child}: {e}")
            except Exception as e:
                errors.append(f"{p}: {e}")
        return freed, errors