# tabs/search_tab.py — Search tab UI and logic

import os
import sys
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

from utils.constants import (
    ACCENT, ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED,
    SUCCESS, DANGER, FOLDER_C, FILE_C, DEFAULT_SKIP,
)
from utils.fs_helpers import fmt_size
from utils.search_worker import run_search
from utils import config as cfg
from utils.lang import t


class SearchTab(tk.Frame):
    def __init__(self, parent, drives: list[str], app_ref):
        super().__init__(parent, bg=BG)
        self._drives   = drives
        self._app      = app_ref   # reference to root window for after() calls

        # State
        self._stop_event        = threading.Event()
        self._search_thread     = None
        self._result_count      = 0
        self._results           = []
        self._search_start_time = 0.0
        self._dirs_scanned      = 0
        self._current_root_idx  = 0
        self._total_roots       = 0
        self._timer_id          = None
        self._pending_results   = []
        self._pending_lock      = threading.Lock()

        self._build(self)
        self._apply_styles()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        left = tk.Frame(body, bg=SURFACE, width=280)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        self._build_controls(left)

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_results(right)

    def _build_controls(self, parent):
        tk.Label(parent, text=t("search.query_label"), font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(20, 2))

        self._query_var = tk.StringVar()
        qf = tk.Frame(parent, bg=SURFACE2, highlightbackground=ACCENT, highlightthickness=0)
        qf.pack(fill="x", padx=16, pady=(0, 4))
        self._query_entry = tk.Entry(qf, textvariable=self._query_var,
                                     font=("Segoe UI", 13), bg=SURFACE2, fg=TEXT,
                                     insertbackground=ACCENT, relief="flat", bd=8)
        self._query_entry.pack(fill="x")
        self._query_entry.bind("<Return>", lambda e: self._start_search())
        self._query_entry.bind("<FocusIn>",  lambda e: qf.config(highlightthickness=1))
        self._query_entry.bind("<FocusOut>", lambda e: qf.config(highlightthickness=0))

        tk.Label(parent, text=t("search.match_label"), font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(14, 4))
        conf = cfg.load()
        default_mode = conf["search"]["default_mode"]
        default_type = conf["search"]["default_type"]
        default_all  = conf["search"]["all_drives"]
        is_exact = default_mode == "exact"
        self._exact_var = tk.BooleanVar(value=is_exact)
        mf = tk.Frame(parent, bg=SURFACE)
        mf.pack(fill="x", padx=16)
        self._btn_keyword = self._toggle_btn(mf, t("search.match_keyword"),    lambda: self._set_mode(False), active=not is_exact)
        self._btn_keyword.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._btn_exact   = self._toggle_btn(mf, t("search.match_exact"), lambda: self._set_mode(True),  active=is_exact)
        self._btn_exact.pack(side="left", fill="x", expand=True)
        tk.Label(parent, text=t("search.match_hint"),
                 font=("Segoe UI", 9), bg=SURFACE, fg=MUTED, justify="left"
                 ).pack(anchor="w", padx=16, pady=(4, 0))

        tk.Label(parent, text=t("search.for_label"), font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(14, 4))
        self._type_var = tk.StringVar(value=default_type)
        tf = tk.Frame(parent, bg=SURFACE)
        tf.pack(fill="x", padx=16)
        for label, val in [(t("search.for_both"), "both"), (t("search.for_files"), "files"), (t("search.for_folders"), "folders")]:
            tk.Radiobutton(tf, text=label, variable=self._type_var, value=val,
                           font=("Segoe UI", 11), bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
                           activebackground=SURFACE, activeforeground=TEXT,
                           relief="flat", bd=0).pack(anchor="w", pady=1)

        tk.Label(parent, text=t("search.in_label"), font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(14, 4))
        dsf = tk.Frame(parent, bg=SURFACE)
        dsf.pack(fill="x", padx=16)
        self._drive_vars     = {}
        self._all_drives_var = tk.BooleanVar(value=default_all)
        tk.Checkbutton(dsf, text=t("search.all_drives"),
                       variable=self._all_drives_var, command=self._toggle_all_drives,
                       font=("Segoe UI", 11, "bold"), bg=SURFACE, fg=ACCENT2,
                       selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=ACCENT2, relief="flat").pack(anchor="w")
        self._drive_cbs = []
        for drive in self._drives:
            var = tk.BooleanVar(value=False)
            self._drive_vars[drive] = var
            cb = tk.Checkbutton(dsf, text=drive, variable=var, state="disabled",
                                font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                                selectcolor=SURFACE2, activebackground=SURFACE,
                                activeforeground=TEXT, relief="flat")
            cb.pack(anchor="w", padx=12)
            self._drive_cbs.append(cb)

        cf = tk.Frame(parent, bg=SURFACE)
        cf.pack(fill="x", padx=16, pady=(6, 0))
        self._custom_var   = tk.StringVar()
        self._custom_entry = tk.Entry(cf, textvariable=self._custom_var,
                                      font=("Segoe UI", 10), bg=SURFACE2, fg=TEXT,
                                      insertbackground=ACCENT, relief="flat", bd=6, state="disabled")
        self._custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._browse_btn = tk.Button(cf, text=t("search.btn_browse"), command=self._browse_folder,
                                     font=("Segoe UI", 10), bg=SURFACE2, fg=MUTED,
                                     relief="flat", bd=0, padx=10, cursor="hand2", state="disabled")
        self._browse_btn.pack(side="left")

        tk.Frame(parent, bg=SURFACE).pack(fill="y", expand=True)
        self._search_btn = tk.Button(parent, text=t("search.btn_search"), command=self._start_search,
                                     font=("Segoe UI", 13, "bold"), bg=ACCENT, fg="white",
                                     relief="flat", bd=0, pady=12, cursor="hand2",
                                     activebackground=ACCENT2, activeforeground="white")
        self._search_btn.pack(fill="x", padx=16, pady=(0, 16))

    def _build_results(self, parent):
        status_bar = tk.Frame(parent, bg=BG)
        status_bar.pack(fill="x", pady=(0, 4))
        self._status_var = tk.StringVar(value=t("search.status_ready"))
        tk.Label(status_bar, textvariable=self._status_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED, anchor="w").pack(side="left")
        self._count_var = tk.StringVar(value="")
        tk.Label(status_bar, textvariable=self._count_var,
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT2, anchor="e").pack(side="right")

        info_bar = tk.Frame(parent, bg=BG)
        info_bar.pack(fill="x", pady=(0, 4))
        self._pct_var = tk.StringVar(value="")
        tk.Label(info_bar, textvariable=self._pct_var,
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT, anchor="w").pack(side="left")
        self._elapsed_var = tk.StringVar(value="")
        tk.Label(info_bar, textvariable=self._elapsed_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED, anchor="w").pack(side="left", padx=(12, 0))
        self._dirs_var = tk.StringVar(value="")
        tk.Label(info_bar, textvariable=self._dirs_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED, anchor="e").pack(side="right")

        self._curpath_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._curpath_var,
                 font=("Segoe UI", 9), bg=BG, fg=SURFACE2, anchor="w",
                 wraplength=600, justify="left").pack(fill="x", pady=(0, 4))

        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 6))
        self._save_btn = tk.Button(toolbar, text=t("search.btn_save"), command=self._save_results,
                                   font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2", state="disabled")
        self._save_btn.pack(side="left", padx=(0, 8))
        tk.Button(toolbar, text=t("search.btn_clear"), command=self._clear_results,
                  font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                  relief="flat", bd=0, padx=12, pady=6, cursor="hand2").pack(side="left")
        self._stop_btn = tk.Button(toolbar, text=t("search.btn_stop"), command=self._stop_search,
                                   font=("Segoe UI", 10), bg=SURFACE, fg=DANGER,
                                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2", state="disabled")
        self._stop_btn.pack(side="right")
        self._delete_btn = tk.Button(toolbar, text=t("search.btn_delete"), command=self._delete_selected,
                                     font=("Segoe UI", 10), bg=SURFACE, fg=DANGER,
                                     relief="flat", bd=0, padx=12, pady=6, cursor="hand2", state="disabled")
        self._delete_btn.pack(side="right", padx=(0, 8))

        tree_frame = tk.Frame(parent, bg=BG)
        tree_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        self._tree = ttk.Treeview(tree_frame, columns=("type", "name", "path", "size"),
                                   show="headings", yscrollcommand=scrollbar.set, selectmode="browse")
        scrollbar.config(command=self._tree.yview)
        self._tree.heading("type", text=t("search.col_type"))
        self._tree.heading("name", text=t("search.col_name"))
        self._tree.heading("path", text=t("search.col_path"))
        self._tree.heading("size", text=t("search.col_size"))
        self._tree.column("type", width=70,  minwidth=60,  stretch=False)
        self._tree.column("name", width=200, minwidth=120, stretch=False)
        self._tree.column("path", width=500, minwidth=200, stretch=True)
        self._tree.column("size", width=80,  minwidth=60,  stretch=False, anchor="e")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", self._open_in_explorer)
        self._tree.bind("<Button-3>", self._right_click_menu)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self._progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self._progress.pack(fill="x", pady=(8, 0))

    def _apply_styles(self):
        self._tree.tag_configure("folder", foreground=FOLDER_C)
        self._tree.tag_configure("file",   foreground=FILE_C)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def on_tab_shown(self):
        """Called when this tab becomes visible — reload config defaults."""
        conf = cfg.load()
        is_exact     = conf["search"]["default_mode"] == "exact"
        default_type = conf["search"]["default_type"]
        default_all  = conf["search"]["all_drives"]
        self._exact_var.set(is_exact)
        self._set_mode(is_exact)
        self._type_var.set(default_type)
        self._all_drives_var.set(default_all)
        self._toggle_all_drives()

    def _toggle_btn(self, parent, text, cmd, active=False):
        return tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 9),
                         bg=ACCENT if active else SURFACE2,
                         fg="white" if active else MUTED,
                         relief="flat", bd=0, pady=7, cursor="hand2",
                         wraplength=115, justify="center")

    def _set_mode(self, exact):
        self._exact_var.set(exact)
        if exact:
            self._btn_exact.config(bg=ACCENT, fg="white")
            self._btn_keyword.config(bg=SURFACE2, fg=MUTED)
        else:
            self._btn_keyword.config(bg=ACCENT, fg="white")
            self._btn_exact.config(bg=SURFACE2, fg=MUTED)

    def _toggle_all_drives(self):
        use_all = self._all_drives_var.get()
        state   = "disabled" if use_all else "normal"
        for cb in self._drive_cbs:
            cb.config(state=state)
        self._custom_entry.config(state=state)
        self._browse_btn.config(state=state, fg=TEXT if not use_all else MUTED)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Choose a folder to search in")
        if folder:
            self._custom_var.set(folder)
            for var in self._drive_vars.values():
                var.set(False)

    def _get_roots(self):
        if self._all_drives_var.get():
            return self._drives if self._drives else [str(Path.home())]
        selected = [d for d, v in self._drive_vars.items() if v.get()]
        custom   = self._custom_var.get().strip()
        if custom and os.path.isdir(custom):
            selected.append(custom)
        return selected if selected else [str(Path.home())]

    @staticmethod
    def _fmt_elapsed(seconds):
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        m, s = divmod(seconds, 60)
        if m < 60:
            return f"{m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m"

    # ── Search ────────────────────────────────────────────────────────────────
    def _start_search(self):
        query = self._query_var.get().strip()
        if not query:
            messagebox.showwarning("No keyword", t("search.no_keyword"))
            return
        if self._search_thread and self._search_thread.is_alive():
            self._stop_search()
        self._clear_results()
        self._stop_event.clear()
        self._result_count      = 0
        self._dirs_scanned      = 0
        self._current_root_idx  = 0
        roots                   = self._get_roots()
        self._total_roots       = len(roots)
        self._search_start_time = time.time()

        self._status_var.set(f"{t('search.status_scanning', n=len(roots))}")
        self._pct_var.set("0%")
        self._elapsed_var.set(t("search.elapsed_zero"))
        self._search_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._progress["value"] = 0
        self._pending_results = []
        self._pending_lock    = threading.Lock()
        self._tick_timer()

        self._search_thread = threading.Thread(
            target=run_search,
            args=(roots, query, self._exact_var.get(), self._type_var.get(),
                  DEFAULT_SKIP, self._on_result, self._on_done,
                  self._on_progress, self._stop_event),
            daemon=True)
        self._search_thread.start()
        self._app.after(100, self._flush_results)

    def _flush_results(self):
        """Drain up to 100 pending results — called every 100ms."""
        with self._pending_lock:
            batch = self._pending_results[:100]
            del self._pending_results[:100]

        for kind, name, path, size in batch:
            icon     = t("search.type_folder") if kind == "folder" else t("search.type_file")
            size_str = fmt_size(size) if size is not None else ""
            iid      = self._tree.insert("", "end",
                                          values=(icon, name, path, size_str),
                                          tags=(kind,))
            self._result_count += 1
            self._results.append({"type": kind, "name": name, "path": path, "size": size})

        if batch:
            self._count_var.set(f"{t('search.status_results', n=self._result_count)}")
            self._tree.see(self._tree.get_children()[-1])

        if self._pending_results or self._search_thread.is_alive():
            self._app.after(100, self._flush_results)

    def _stop_timer(self):
        if self._timer_id:
            self._app.after_cancel(self._timer_id)
            self._timer_id = None

    def _stop_search(self):
        self._stop_event.set()
        self._stop_timer()
        self._status_var.set("Stopping…")

    def _on_progress(self, root_idx, total_roots, dirs_in_root, current_path):
        self._dirs_scanned += 1
        # Only update UI every 200 directories
        if self._dirs_scanned % 200 == 0:
            self._app.after(0, self._update_progress,
                            root_idx, total_roots, dirs_in_root, current_path)

    def _update_progress(self, root_idx, total_roots, dirs_in_root, current_path):
        self._current_root_idx = root_idx
        drive_progress = root_idx / total_roots
        within         = (1 - (1 / (1 + dirs_in_root / 800))) * 0.95
        pct            = min(int((drive_progress + within / total_roots) * 100), 99)
        self._progress["value"] = pct
        self._pct_var.set(f"{pct}%  ({t('search.drive_progress', i=root_idx+1, n=total_roots)})")
        self._dirs_var.set(f"{t('search.dirs_scanned', n=self._dirs_scanned):}")
        self._curpath_var.set(current_path if len(current_path) <= 80 else "…" + current_path[-77:])

    def _tick_timer(self):
        elapsed = time.time() - self._search_start_time
        self._elapsed_var.set(self._fmt_elapsed(elapsed))
        self._timer_id = self._app.after(1000, self._tick_timer)

    def _on_result(self, kind, name, path, size):
        with self._pending_lock:
            self._pending_results.append((kind, name, path, size))

    def _on_done(self, total):
        self._app.after(0, self._finish_search, total)

    def _finish_search(self, total):
        self._stop_timer()
        elapsed     = time.time() - self._search_start_time
        elapsed_str = self._fmt_elapsed(elapsed).replace(" elapsed", "")
        self._progress["value"] = 100
        self._search_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        if total > 0:
            self._save_btn.config(state="normal")
        msg = t("search.status_stopped") if self._stop_event.is_set() else t("search.status_complete")
        self._status_var.set(f"{msg} — {t('search.status_results', n=total)}")
        self._count_var.set(f"{total} results")
        self._elapsed_var.set(f"{t('search.took', t=elapsed_str)}")
        self._pct_var.set("100%" if not self._stop_event.is_set() else
                          f"{int(self._current_root_idx / max(self._total_roots, 1) * 100)}%")
        self._curpath_var.set("")

    def _clear_results(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._results        = []
        self._result_count   = 0
        self._dirs_scanned   = 0
        self._count_var.set("")
        self._pct_var.set("")
        self._elapsed_var.set("")
        self._dirs_var.set("")
        self._curpath_var.set("")
        self._progress["value"] = 0
        self._status_var.set(t("search.status_ready"))
        self._save_btn.config(state="disabled")
        self._delete_btn.config(state="disabled")

    # ── Tree interactions ─────────────────────────────────────────────────────
    def _on_tree_select(self, event):
        self._delete_btn.config(state="normal" if self._tree.selection() else "disabled")

    def _open_in_explorer(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        path   = self._tree.item(sel[0], "values")[2]
        target = path if os.path.isdir(path) else os.path.dirname(path)
        self._open_path(target)

    def _right_click_menu(self, event):
        sel = self._tree.identify_row(event.y)
        if not sel:
            return
        self._tree.selection_set(sel)
        values = self._tree.item(sel, "values")
        path   = values[2]
        menu   = tk.Menu(self._app, tearoff=0, bg=SURFACE2, fg=TEXT,
                         activebackground=ACCENT, activeforeground="white", relief="flat", bd=0)
        menu.add_command(label="Open location", command=lambda: self._open_path(os.path.dirname(path)))
        menu.add_command(label="Copy path",     command=lambda: self._copy_to_clipboard(path))
        menu.add_command(label="Copy name",     command=lambda: self._copy_to_clipboard(values[1]))
        menu.add_separator()
        menu.add_command(label="🗑  Delete this item",
                         command=lambda: self._delete_item(sel, path, values[0]))
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        self._delete_item(sel[0], values[2], values[0])

    def _delete_item(self, iid, path, type_label):
        is_folder = t("search.type_folder") in type_label
        kind_word = "folder and ALL its contents" if is_folder else "file"
        if not messagebox.askyesno("Confirm delete",
                                   f"Permanently delete this {kind_word}?\n\n{path}\n\nThis cannot be undone.",
                                   icon="warning", default="no"):
            return
        try:
            shutil.rmtree(path) if is_folder else os.remove(path)
            self._tree.delete(iid)
            self._results      = [r for r in self._results if r["path"] != path]
            self._result_count = len(self._results)
            self._count_var.set(f"{self._result_count} results")
            self._status_var.set(f"Deleted: {path}")
            self._delete_btn.config(state="disabled")
        except PermissionError:
            messagebox.showerror("Permission denied", f"Cannot delete:\n{path}")
        except FileNotFoundError:
            messagebox.showwarning("Already gone", f"No longer exists:\n{path}")
            self._tree.delete(iid)
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete:\n{path}\n\n{e}")

    def _open_path(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _copy_to_clipboard(self, text):
        self._app.clipboard_clear()
        self._app.clipboard_append(text)

    def _save_results(self):
        if not self._results:
            return
        query = self._query_var.get().strip().replace(" ", "_")
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        path  = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile=f"search_{query}_{ts}.txt", title="Save results as")
        if not path:
            return
        files   = [r for r in self._results if r["type"] == "file"]
        folders = [r for r in self._results if r["type"] == "folder"]
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"File Finder Results\n{'='*60}\n")
            f.write(f"Date:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Query:   {self._query_var.get()}\n")
            f.write(f"Mode:    {'Exact' if self._exact_var.get() else 'Keyword'}\n")
            f.write(f"Results: {len(self._results)} ({len(folders)} folders, {len(files)} files)\n\n")
            if folders:
                f.write(f"FOLDERS ({len(folders)})\n{'-'*60}\n")
                for r in folders:
                    f.write(f"  {r['name']}\n  → {r['path']}\n\n")
            if files:
                f.write(f"FILES ({len(files)})\n{'-'*60}\n")
                for r in files:
                    f.write(f"  {r['name']}  ({fmt_size(r['size'])})\n  → {r['path']}\n\n")
        messagebox.showinfo("Saved", f"Results saved to:\n{path}")