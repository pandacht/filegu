# tabs/cache_tab.py - Cache Cleaner tab UI and logic

import os
import shutil
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from utils.constants import (
    ACCENT, ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED,
    SUCCESS, WARNING, DANGER,
)
from utils.fs_helpers import dir_size, fmt_size
from utils.cache_targets import build_cache_targets


class CacheTab(tk.Frame):
    def __init__(self, parent, app_ref):
        super().__init__(parent, bg=BG)
        self._app           = app_ref
        self._cache_targets = build_cache_targets()
        self._cache_vars         = {}   # label → BooleanVar
        self._cache_size_labels  = {}   # label → tk.Label

        self._build(self)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(top, text="Select what to clean, then press Scan to see sizes before deleting.",
                 font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(side="left")

        sel_frame = tk.Frame(top, bg=BG)
        sel_frame.pack(side="right")
        tk.Button(sel_frame, text="Select all",   command=self._select_all,
                  font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(sel_frame, text="Deselect all", command=self._deselect_all,
                  font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2").pack(side="left")

        # Scrollable list
        list_outer = tk.Frame(parent, bg=BG)
        list_outer.pack(fill="both", expand=True, padx=20)

        canvas = tk.Canvas(list_outer, bg=BG, highlightthickness=0)
        vsb    = tk.Scrollbar(list_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner        = tk.Frame(canvas, bg=BG)
        canvas_win   = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        current_group = None
        for group, label, paths, desc in self._cache_targets:
            if group != current_group:
                current_group = group
                gh = tk.Frame(inner, bg=BG)
                gh.pack(fill="x", pady=(16, 4))
                tk.Label(gh, text=group.upper(), font=("Segoe UI", 9, "bold"),
                         bg=BG, fg=ACCENT2).pack(side="left")
                tk.Frame(gh, bg=SURFACE2, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)
            self._build_row(inner, label, paths, desc)

        # Bottom action bar
        bottom = tk.Frame(parent, bg=SURFACE, pady=14)
        bottom.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._status_var,
                 font=("Segoe UI", 10), bg=SURFACE, fg=MUTED).pack(side="left", padx=20)
        self._total_var  = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._total_var,
                 font=("Segoe UI", 11, "bold"), bg=SURFACE, fg=SUCCESS).pack(side="left", padx=8)

        btn_frame = tk.Frame(bottom, bg=SURFACE)
        btn_frame.pack(side="right", padx=20)
        self._scan_btn = tk.Button(btn_frame, text="Scan sizes", command=self._scan,
                                   font=("Segoe UI", 11), bg=SURFACE2, fg=TEXT,
                                   relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        self._scan_btn.pack(side="left", padx=(0, 10))
        self._clean_btn = tk.Button(btn_frame, text="Clean selected", command=self._clean,
                                    font=("Segoe UI", 11, "bold"), bg=DANGER, fg="white",
                                    relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        self._clean_btn.pack(side="left")

    def _build_row(self, parent, label, paths, desc):
        var = tk.BooleanVar(value=False)
        self._cache_vars[label] = var

        row = tk.Frame(parent, bg=SURFACE, pady=0)
        row.pack(fill="x", pady=2)
        tk.Checkbutton(row, variable=var, text=label,
                       font=("Segoe UI", 11), bg=SURFACE, fg=TEXT,
                       selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=TEXT, relief="flat", anchor="w", width=22
                       ).pack(side="left", padx=(12, 0))
        tk.Label(row, text=desc, font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                 anchor="w").pack(side="left", padx=8, fill="x", expand=True)
        size_lbl = tk.Label(row, text="-", font=("Segoe UI", 10, "bold"),
                            bg=SURFACE, fg=MUTED, width=10, anchor="e")
        size_lbl.pack(side="right", padx=12)
        self._cache_size_labels[label] = size_lbl

    # ── Actions ───────────────────────────────────────────────────────────────
    def _select_all(self):
        for v in self._cache_vars.values():
            v.set(True)

    def _deselect_all(self):
        for v in self._cache_vars.values():
            v.set(False)

    def _scan(self):
        selected = [l for l, v in self._cache_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("Nothing selected", "Check at least one cache category to scan.")
            return
        self._status_var.set("Scanning…")
        self._total_var.set("")
        self._scan_btn.config(state="disabled")

        def worker():
            total = 0
            for group, label, paths, desc in self._cache_targets:
                if label not in selected:
                    continue
                size  = self._measure(label, paths)
                total += size
                color = WARNING if size > 50*1024*1024 else (SUCCESS if size > 0 else MUTED)
                disp  = fmt_size(size) if size > 0 else "not found"
                self._app.after(0, self._set_size_label, label, disp, color)

            def finish():
                self._status_var.set("Scan complete")
                self._total_var.set(f"Total: {fmt_size(total)}")
                self._scan_btn.config(state="normal")
            self._app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _clean(self):
        selected = [l for l, v in self._cache_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("Nothing selected", "Check at least one cache category to clean.")
            return
        if not messagebox.askyesno(
            "Confirm cache clean",
            f"Permanently delete cache for {len(selected)} selected categor{'y' if len(selected)==1 else 'ies'}?\n\n"
            + "\n".join(f"  • {s}" for s in selected)
            + "\n\nThis cannot be undone.",
            icon="warning", default="no"
        ):
            return
        self._status_var.set("Cleaning…")
        self._total_var.set("")
        self._clean_btn.config(state="disabled")
        self._scan_btn.config(state="disabled")

        def worker():
            freed  = 0
            errors = []
            for group, label, paths, desc in self._cache_targets:
                if label not in selected:
                    continue
                f, e = self._do_clean(label, paths)
                freed  += f
                errors.extend(e)
                self._app.after(0, self._set_size_label, label, "cleaned", SUCCESS)

            def finish():
                self._status_var.set(f"Done - {len(errors)} error(s)" if errors else "All done!")
                self._total_var.set(f"Freed: {fmt_size(freed)}")
                self._clean_btn.config(state="normal")
                self._scan_btn.config(state="normal")
                if errors:
                    messagebox.showwarning("Some errors",
                                           f"{len(errors)} items could not be deleted:\n\n"
                                           + "\n".join(errors[:10]))
            self._app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_size_label(self, label, text, color):
        lbl = self._cache_size_labels.get(label)
        if lbl:
            lbl.config(text=text, fg=color)

    def _measure(self, label, paths):
        if label in ("__pycache__", ".mypy_cache"):
            return self._scan_named_dirs(label)
        total = 0
        for p in paths:
            p = Path(p)
            if p.exists():
                total += dir_size(p)
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

    def _do_clean(self, label, paths):
        freed  = 0
        errors = []
        if label in ("__pycache__", ".mypy_cache"):
            home = Path.home()
            skip = {".git", "venv", ".venv", "node_modules"}
            try:
                for dirpath, dirnames, _ in os.walk(home):
                    dirnames[:] = [d for d in dirnames if d not in skip]
                    if label in dirnames:
                        target = Path(dirpath) / label
                        try:
                            freed += dir_size(target)
                            shutil.rmtree(target)
                        except Exception as e:
                            errors.append(str(e))
            except Exception:
                pass
            return freed, errors

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