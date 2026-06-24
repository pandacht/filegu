# tabs/virus_tab.py — Local Virus Scanner tab (no API, no rate limits)

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

from utils.constants import (
    ACCENT, ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED,
    SUCCESS, WARNING, DANGER, DEFAULT_SKIP,
)
from utils import config as cfg
from utils.lang import t
from utils.virustotal import vt_lookup_hash, vt_parse_result
from scanner.engine  import scan_file
from scanner.hash_db import db_info, update_database
from scanner         import yara_engine


class VirusTab(tk.Frame):
    def __init__(self, parent, app_ref, drives: list[str]):
        super().__init__(parent, bg=BG)
        self._app      = app_ref
        self._drives   = drives
        self._results  = []
        self._stop     = threading.Event()
        self._thread   = None
        self._start_time   = 0.0
        self._timer_id     = None
        self._pending_results = []
        self._pending_lock    = threading.Lock()
        self._result_counts   = {"clean": tk.IntVar(value=0)}
        self._clean_count_var = tk.StringVar(value=t("virus.clean_count", n=0))
        self._scan_done_flag  = False
        self._scan_done_total = 0
        self._scan_total      = [0]
        self._vt_key_var      = tk.StringVar()

        self._build(self)
        self._refresh_db_info()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self, parent):
        # ── Top info bar ──
        info_bar = tk.Frame(parent, bg=SURFACE2)
        info_bar.pack(fill="x")

        self._db_var = tk.StringVar(value="Checking database…")
        tk.Label(info_bar, textvariable=self._db_var,
                 font=("Segoe UI", 10), bg=SURFACE2, fg=MUTED).pack(side="left", padx=16, pady=8)

        self._yara_var = tk.StringVar(value="")
        tk.Label(info_bar, textvariable=self._yara_var,
                 font=("Segoe UI", 10), bg=SURFACE2, fg=MUTED).pack(side="left", padx=(0, 16))

        tk.Button(info_bar, text=t("virus.btn_update_db"),
                  command=self._update_db,
                  font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                  relief="flat", bd=0, padx=12, pady=6, cursor="hand2"
                  ).pack(side="right", padx=12, pady=6)

        # ── Scan target ──
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        # Left: drive selection
        left = tk.Frame(body, bg=SURFACE, width=240)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        self._build_drive_panel(left)

        # Right: options + progress + results
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_right_panel(right)

    def _build_drive_panel(self, parent):
        tk.Label(parent, text=t("virus.scan_in"), font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(16, 4))

        dsf = tk.Frame(parent, bg=SURFACE)
        dsf.pack(fill="x", padx=16)

        # All drives checkbox
        self._all_drives_var = tk.BooleanVar(value=True)
        self._all_drives_cb = tk.Checkbutton(dsf, text=t("virus.all_drives"),
                       variable=self._all_drives_var,
                       command=self._toggle_all_drives,
                       font=("Segoe UI", 11, "bold"), bg=SURFACE, fg=ACCENT2,
                       selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=ACCENT2, relief="flat")
        self._all_drives_cb.pack(anchor="w")

        # Individual drive checkboxes
        self._drive_vars = {}
        self._drive_cbs  = []
        for drive in self._drives:
            var = tk.BooleanVar(value=False)
            self._drive_vars[drive] = var
            cb = tk.Checkbutton(dsf, text=drive, variable=var, state="disabled",
                                font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                                selectcolor=SURFACE2, activebackground=SURFACE,
                                activeforeground=TEXT, relief="flat")
            cb.pack(anchor="w", padx=12)
            self._drive_cbs.append(cb)

        # Separator
        tk.Frame(parent, bg=SURFACE2, height=1).pack(fill="x", padx=16, pady=(12, 8))

        # Single file browse
        tk.Label(parent, text=t("virus.single_file"), font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(0, 4))

        self._file_var = tk.StringVar()
        ff = tk.Frame(parent, bg=SURFACE2)
        ff.pack(fill="x", padx=16)
        self._file_entry = tk.Entry(ff, textvariable=self._file_var,
                 font=("Segoe UI", 9), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", bd=6)
        self._file_entry.pack(fill="x")

        self._browse_btn = tk.Button(parent, text=t("virus.btn_browse"), command=self._browse_file,
                  font=("Segoe UI", 10), bg=SURFACE2, fg=TEXT,
                  relief="flat", bd=0, padx=10, pady=6, cursor="hand2")
        self._browse_btn.pack(fill="x", padx=16, pady=(6, 0))

        # Separator
        tk.Frame(parent, bg=SURFACE2, height=1).pack(fill="x", padx=16, pady=(12, 8))

        # Spacer + scan button
        tk.Frame(parent, bg=SURFACE).pack(fill="y", expand=True)

        self._scan_btn = tk.Button(parent, text=t("virus.btn_start"),
                                   command=self._start_scan,
                                   font=("Segoe UI", 13, "bold"), bg=ACCENT, fg="white",
                                   relief="flat", bd=0, pady=12, cursor="hand2",
                                   activebackground=ACCENT2, activeforeground="white")
        self._scan_btn.pack(fill="x", padx=16, pady=(8, 16))

    def _build_right_panel(self, parent):
        # Progress
        prog_frame = tk.Frame(parent, bg=BG)
        prog_frame.pack(fill="x", pady=(0, 4))
        self._status_var = tk.StringVar(value=t("virus.status_ready"))
        tk.Label(prog_frame, textvariable=self._status_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED, anchor="w").pack(side="left")
        self._elapsed_var = tk.StringVar(value="")
        tk.Label(prog_frame, textvariable=self._elapsed_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(side="right", padx=(8, 0))
        self._count_var = tk.StringVar(value="")
        tk.Label(prog_frame, textvariable=self._count_var,
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT2).pack(side="right")

        self._progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self._progress.pack(fill="x", pady=(0, 8))

        # Toolbar
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 8))
        self._stop_btn = tk.Button(toolbar, text=t("virus.btn_stop"),
                                   command=self._stop_scan,
                                   font=("Segoe UI", 10), bg=SURFACE, fg=DANGER,
                                   relief="flat", bd=0, padx=12, pady=8, cursor="hand2", state="disabled")
        self._stop_btn.pack(side="left")
        self._save_btn = tk.Button(toolbar, text=t("virus.btn_save"),
                                   command=self._save_report,
                                   font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                                   relief="flat", bd=0, padx=12, pady=8, cursor="hand2", state="disabled")
        self._save_btn.pack(side="left", padx=(8, 0))
        tk.Button(toolbar, text=t("virus.btn_clear"), command=self._clear,
                  font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                  relief="flat", bd=0, padx=12, pady=8, cursor="hand2").pack(side="left", padx=(8, 0))
        self._deepscan_btn = tk.Button(
            toolbar, text=t("virus.btn_deepscan"),
            command=self._start_deep_scan,
            font=("Segoe UI", 10, "bold"), bg=WARNING, fg="#0F1117",
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2", state="disabled"
        )
        self._deepscan_btn.pack(side="right")
        self._vt_verify_btn = tk.Button(
            toolbar, text=t("virus.btn_verify"),
            command=self._start_vt_verify,
            font=("Segoe UI", 10, "bold"), bg=ACCENT2, fg="white",
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2", state="disabled"
        )
        self._vt_verify_btn.pack(side="right", padx=(0, 8))

        # Results tabs
        tab_bar = tk.Frame(parent, bg=SURFACE2)
        tab_bar.pack(fill="x", pady=(4, 0))

        self._clean_count_var = tk.StringVar(value=t("virus.clean_count", n=0))
        tk.Label(tab_bar, textvariable=self._clean_count_var,
                 font=("Segoe UI", 10), bg=SURFACE2, fg=SUCCESS
                 ).pack(side="right", padx=16)

        results_container = tk.Frame(parent, bg=BG)
        results_container.pack(fill="both", expand=True)

        self._result_tabs   = {}
        self._result_trees  = {}
        self._result_counts = {}
        self._tab_btns      = {}
        self._active_tab    = "malicious"

        tab_defs = [
            ("malicious",  t("virus.tab_malicious"),  DANGER),
            ("suspicious", t("virus.tab_suspicious"), WARNING),
            ("vt",         t("virus.tab_online"),     ACCENT),
        ]

        for key, label, color in tab_defs:
            frame = tk.Frame(results_container, bg=BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._result_tabs[key] = frame

            count_var = tk.IntVar(value=0)
            self._result_counts[key] = count_var

            btn = tk.Button(
                tab_bar, text=f"{label}  (0)",
                font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                padx=16, pady=8, cursor="hand2",
                command=lambda k=key: self._switch_result_tab(k)
            )
            btn.pack(side="left")
            self._tab_btns[key] = btn

            if key == "vt":
                self._build_vt_tab(frame)
                continue

            # Build tree inside this frame
            tf  = tk.Frame(frame, bg=BG)
            tf.pack(fill="both", expand=True)
            vsb = ttk.Scrollbar(tf)
            vsb.pack(side="right", fill="y")
            tree = ttk.Treeview(
                tf,
                columns=("name", "score", "findings", "entropy"),
                show="headings",
                yscrollcommand=vsb.set,
                selectmode="browse"
            )
            vsb.config(command=tree.yview)
            tree.heading("name",     text=t("virus.col_file"))
            tree.heading("score",    text=t("virus.col_score"))
            tree.heading("findings", text=t("virus.col_finding"))
            tree.heading("entropy",  text=t("virus.col_entropy"))
            tree.column("name",     width=200, minwidth=120, stretch=False)
            tree.column("score",    width=70,  minwidth=50,  stretch=False, anchor="center")
            tree.column("findings", width=480, minwidth=200, stretch=True)
            tree.column("entropy",  width=80,  minwidth=60,  stretch=False, anchor="center")
            tree.pack(fill="both", expand=True)
            tree.tag_configure(key, foreground=color)
            tree.bind("<Double-1>", lambda e, k=key: self._show_details(e, k))
            tree.bind("<Button-3>", lambda e, k=key: self._right_click(e, k))
            self._result_trees[key] = tree

        self._switch_result_tab("malicious")

    def _switch_result_tab(self, key: str):
        self._active_tab = key
        for k, frame in self._result_tabs.items():
            frame.lower()
        self._result_tabs[key].lift()

        colors = {"malicious": DANGER, "suspicious": WARNING, "clean": SUCCESS, "vt": ACCENT}
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.config(bg=colors[k], fg="white")
            else:
                btn.config(bg=SURFACE2, fg=MUTED)

    def _update_tab_badge(self, key: str):
        count = self._result_counts[key].get()
        labels = {"malicious": t("virus.tab_malicious"), "suspicious": t("virus.tab_suspicious"), "clean": t("virus.clean_count", n=""), "vt": t("virus.tab_online")}
        self._tab_btns[key].config(text=f"{labels[key]}  ({count})")

    # ── Drive helpers ─────────────────────────────────────────────────────────
    def _toggle_all_drives(self):
        use_all = self._all_drives_var.get()
        state   = "disabled" if use_all else "normal"
        for cb in self._drive_cbs:
            cb.config(state=state)

    def _browse_file(self):
        p = filedialog.askopenfilename(title="Choose a file to scan")
        if p:
            self._file_var.set(p)
            # Uncheck all drives — single file mode
            self._all_drives_var.set(False)
            for var in self._drive_vars.values():
                var.set(False)
            self._toggle_all_drives()

    def _get_targets(self) -> list[str]:
        """Return list of root paths to scan."""
        # Single file takes priority if filled in
        single = self._file_var.get().strip()
        if single and os.path.isfile(single):
            return [single]

        if self._all_drives_var.get():
            return self._drives if self._drives else [str(Path.home())]

        selected = [d for d, v in self._drive_vars.items() if v.get()]
        return selected if selected else []
    def _refresh_db_info(self):
        info = db_info()
        if info["exists"]:
            upd = f"  ·  updated {info['updated']}" if info["updated"] else ""
            self._db_var.set(t("virus.hash_db", n=f"{info['count']:,}", date=info['updated'] or ""))
        else:
            self._db_var.set(t("virus.hash_db_none"))

        if yara_engine.is_available():
            self._yara_var.set(t("virus.yara_active"))
        else:
            self._yara_var.set(t("virus.yara_missing"))

    def _update_db(self):
        self._db_var.set("Downloading…")

        def worker():
            ok, msg = update_database(
                progress_cb=lambda m: self._app.after(0, self._db_var.set, m)
            )
            def finish():
                self._refresh_db_info()
                if not ok:
                    messagebox.showerror("Update failed", msg)
            self._app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ── Lock / unlock all settings during scan ────────────────────────────────
    def _lock_controls(self):
        self._all_drives_cb.config(state="disabled")
        for cb in self._drive_cbs:
            cb.config(state="disabled")
        self._file_entry.config(state="disabled")
        self._browse_btn.config(state="disabled")

    def _unlock_controls(self):
        self._all_drives_cb.config(state="normal")
        if not self._all_drives_var.get():
            for cb in self._drive_cbs:
                cb.config(state="normal")
        self._file_entry.config(state="normal")
        self._browse_btn.config(state="normal")

    # ── Timer ─────────────────────────────────────────────────────────────────
    def _fmt_elapsed(self, seconds: float) -> str:
        sec = t("virus.time_s")
        mnt = t("virus.time_m")
        hrs = t("virus.time_h")
        s = int(seconds)
        if s < 60:
            return f"{s}{sec}"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}{mnt} {s:02d}{sec}"
        h, m = divmod(m, 60)
        return f"{h}{hrs} {m:02d}{mnt} {s:02d}{sec}"

    def _tick_timer(self):
        """Ticks every second — keeps running until _stop_timer() is called."""
        elapsed = time.time() - self._start_time
        self._elapsed_var.set(f"{t('virus.elapsed', t=self._fmt_elapsed(elapsed))}")
        self._timer_id = self._app.after(1000, self._tick_timer)

    def _stop_timer(self):
        if self._timer_id:
            self._app.after_cancel(self._timer_id)
            self._timer_id = None

    # ── Scan ──────────────────────────────────────────────────────────────────

    # Extensions that are never dangerous — always skip regardless of options
    _ALWAYS_SKIP_EXT = {
        # Media
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".raw",
        ".mp3", ".mp4", ".wav", ".flac", ".ogg", ".mkv", ".avi", ".mov", ".wmv", ".m4a",
        # Fonts
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        # Pure data / text
        ".txt", ".log", ".csv", ".xml", ".json", ".yaml", ".yml", ".ini", ".cfg",
        ".md", ".rst", ".nfo",
        # Chromium / app data files
        ".pak", ".dat", ".db", ".sqlite", ".sqlite3",
        # Images / design
        ".svg", ".psd", ".ai", ".xcf",
        # Documents
        ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods",
        # Compiled assets / caches
        ".pyc", ".pyo", ".class",
        # Locale / translation files
        ".mo", ".po", ".pot",
        # Game asset formats
        ".crp",   # Cities: Skylines assets
        ".unity3d", ".assetbundle", ".assets",  # Unity
        ".uasset", ".umap", ".upk",             # Unreal Engine
        ".rpf",                                  # GTA / Rockstar
        ".bsa", ".ba2",                          # Bethesda (Skyrim, Fallout)
        ".vpk",                                  # Valve (CS:GO, TF2)
        ".wad", ".pk3", ".pk4",                  # id Software / Quake / Doom
        ".forge", ".big", ".mix",                # various game archives
        ".arc", ".pac", ".res",                  # generic game archives
        ".bnk",                                  # audio banks (Wwise)
        ".xnb",                                  # XNA/MonoGame content
    }

    _EXE_ONLY_EXT = {
        ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js",
        ".jar", ".msi", ".scr", ".pif", ".com", ".lnk", ".reg",
        ".hta", ".wsf", ".cpl", ".ocx",
    }

    def _collect_files(self, roots: list[str]) -> list[str]:
        conf       = cfg.load()
        exe_only   = conf["scanner"]["exe_only"]
        extra_ext  = set(conf["scanner"]["extra_skip_ext"])
        extra_dirs = set(conf["scanner"]["extra_skip_dirs"])
        skip_dirs  = DEFAULT_SKIP | extra_dirs

        files = []
        for root in roots:
            if os.path.isfile(root):
                files.append(root)
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for fname in filenames:
                    ext = Path(fname).suffix.lower()
                    if ext in extra_ext:
                        continue
                    if exe_only and ext not in self._EXE_ONLY_EXT:
                        continue
                    files.append(os.path.join(dirpath, fname))
        return files

    def _start_scan(self):
        targets = self._get_targets()
        if not targets:
            messagebox.showwarning(t("common.warning"),
                                   "Select at least one drive, or browse to a single file.")
            return

        self._clear()
        self._stop.clear()

        conf       = cfg.load()
        n_threads  = conf["scanner"]["threads"]
        skip_media = conf["scanner"]["skip_media"]

        # Lock UI and start immediately
        self._status_var.set(t("virus.status_finding"))
        self._count_var.set("0 done  ·  0 found")
        self._progress.config(mode="determinate", maximum=100)
        self._progress["value"] = 0
        self._scan_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._lock_controls()
        self._start_time = time.time()
        self._elapsed_var.set("⏱ 0s")

        # Phase 1: bouncing bar while finding files
        self._progress.config(mode="indeterminate")
        self._progress.start(10)

        done_counter  = [0]
        lock          = threading.Lock()
        # Batch queue — worker puts results here, UI drains every 100ms
        self._pending_results = []
        self._pending_lock    = threading.Lock()

        def scan_one(fpath):
            if self._stop.is_set():
                return None
            return scan_file(fpath, skip_media=skip_media)

        def worker():
            from concurrent.futures import ThreadPoolExecutor, as_completed

            conf_w     = cfg.load()
            exe_only   = conf_w["scanner"]["exe_only"]
            extra_ext  = set(conf_w["scanner"]["extra_skip_ext"])
            extra_dirs = set(conf_w["scanner"]["extra_skip_dirs"])
            skip_dirs  = DEFAULT_SKIP | extra_dirs

            # ── Phase 1: find all files ───────────────────────────────────────
            self._app.after(0, self._status_var.set, t("virus.status_finding"))
            files        = []
            last_ui_upd  = [time.time()]

            for root in targets:
                if self._stop.is_set():
                    break
                if os.path.isfile(root):
                    files.append(root)
                    continue
                for dirpath, dirnames, filenames in os.walk(root):
                    if self._stop.is_set():
                        dirnames.clear()
                        break
                    dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                    for fname in filenames:
                        if self._stop.is_set():
                            break
                        ext = Path(fname).suffix.lower()
                        if ext in extra_ext:
                            continue
                        if exe_only and ext not in self._EXE_ONLY_EXT:
                            continue
                        files.append(os.path.join(dirpath, fname))
                    # Update count label at most every 200ms
                    now = time.time()
                    if now - last_ui_upd[0] >= 0.2:
                        count = len(files)
                        self._app.after(0, self._count_var.set, f"{count:,} found")
                        last_ui_upd[0] = now

            if self._stop.is_set() or not files:
                def abort():
                    self._progress.stop()
                    self._progress.config(mode="determinate")
                    self._status_var.set("No files found." if not files else "Stopped.")
                    self._count_var.set("")
                    self._scan_btn.config(state="normal")
                    self._stop_btn.config(state="disabled")
                    self._unlock_controls()
                self._app.after(0, abort)
                return

            total = len(files)
            self._scan_total[0] = total

            # ── Switch to Phase 2: normal fill bar ────────────────────────────
            def start_phase2():
                self._progress.stop()
                self._progress.config(mode="determinate", maximum=total)
                self._progress["value"] = 0
                self._status_var.set(t("virus.status_scanning", n=total))
                self._count_var.set(f"0 / {total:,}")
            self._app.after(0, start_phase2)

            # ── Phase 2: scan all files ───────────────────────────────────────
            with ThreadPoolExecutor(max_workers=n_threads) as pool:
                futures = {pool.submit(scan_one, f): f for f in files}
                for future in as_completed(futures):
                    if self._stop.is_set():
                        break
                    result = future.result()
                    if result is None:
                        continue
                    with lock:
                        done_counter[0] += 1
                        done = done_counter[0]
                    self._results.append(result)
                    with self._pending_lock:
                        self._pending_results.append((result, done, total))

            # Signal done — flush loop will call _finish_scan once queue is empty
            self._scan_done_total = done_counter[0]
            self._scan_done_flag  = True

        self._scan_done_flag  = False
        self._scan_done_total = 0
        self._scan_total      = [0]   # shared container for total
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        self._app.after(100, self._flush_results)
        self._tick_timer()

    def _flush_results(self):
        """Drain up to 50 pending results — called every 100ms."""
        total = self._scan_total[0]
        with self._pending_lock:
            batch = self._pending_results[:50]
            del self._pending_results[:50]

        for result, done, t in batch:
            self._add_row(result, done, t)

        if batch and total > 0:
            last_done = batch[-1][1]
            self._count_var.set(f"{last_done:,} / {total:,}")
            self._progress["value"] = last_done

        if self._pending_results or not getattr(self, "_scan_done_flag", False):
            self._app.after(100, self._flush_results)
        else:
            self._app.after(0, self._finish_scan, self._scan_done_total)

    def _flush_deep_results(self):
        """Drain up to 50 pending deep scan results — called every 100ms."""
        total = self._scan_total[0]
        with self._pending_lock:
            batch = self._pending_results[:50]
            del self._pending_results[:50]

        for result, done, t in batch:
            self._add_deep_row(result, done, t)

        if batch and total > 0:
            last_done = batch[-1][1]
            self._count_var.set(f"{last_done:,} / {total:,}")
            self._progress["value"] = last_done

        if self._pending_results or not getattr(self, "_scan_done_flag", False):
            self._app.after(100, self._flush_deep_results)
        else:
            self._app.after(0, self._finish_scan, self._scan_done_total)

    def _update_scan_progress(self, result, done, total):
        self._add_row(result, done, total)
        self._count_var.set(f"{done:,} / {total:,}")
        self._progress["value"] = done

    def _finish_scan(self, total):
        # Short delay so timer gets one final tick before we cancel it
        self._app.after(1100, self._finish_scan_final, total)

    def _finish_scan_final(self, total):
        self._stop_timer()
        elapsed = time.time() - self._start_time
        self._elapsed_var.set(f"{t('virus.took', t=self._fmt_elapsed(elapsed))}")
        try:
            if str(self._progress.cget("mode")) == "indeterminate":
                self._progress.stop()
        except Exception:
            pass
        self._progress.config(mode="determinate", maximum=max(total, 1))
        self._progress["value"] = total
        malicious  = sum(1 for r in self._results if r["verdict"] == "malicious")
        suspicious = sum(1 for r in self._results if r["verdict"] == "suspicious")
        scanned    = sum(1 for r in self._results if r["verdict"] not in ("skipped", "error"))
        stopped    = self._stop.is_set()
        msg = t("virus.status_stopped_word") if stopped else t("virus.status_complete_word")
        self._status_var.set(
            f"{msg} — {scanned:,} {t('virus.word_scanned')}  ·  "
            f"{malicious} {t('virus.word_malicious')}  ·  {suspicious} {t('virus.word_suspicious')}"
        )
        self._count_var.set(f"{total:,} {t('virus.word_processed')}")
        self._scan_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._unlock_controls()
        if self._results:
            self._save_btn.config(state="normal")
        flagged = [r for r in self._results if r["verdict"] in ("malicious", "suspicious")]
        if flagged and not self._stop.is_set():
            self._deepscan_btn.config(state="normal")
            self._vt_verify_btn.config(state="normal")

    # ── Online Verification (VirusTotal) ──────────────────────────────────────
    def _build_vt_tab(self, parent):
        # Load saved key from config
        saved_key = cfg.load()["scanner"].get("virustotal_key", "")
        if saved_key:
            self._vt_key_var.set(saved_key)
        # API key row
        key_frame = tk.Frame(parent, bg=SURFACE2)
        key_frame.pack(fill="x", pady=(0, 1))

        tk.Label(key_frame, text=t("virus.vt_api_label"),
                 font=("Segoe UI", 10), bg=SURFACE2, fg=MUTED).pack(side="left", padx=12, pady=8)

        kf = tk.Frame(key_frame, bg=SURFACE2)
        kf.pack(side="left", fill="x", expand=True, pady=6)
        self._vt_key_entry = tk.Entry(kf, textvariable=self._vt_key_var,
                                       font=("Segoe UI", 10), bg=BG, fg=TEXT,
                                       insertbackground=ACCENT, relief="flat", bd=6, show="•")
        self._vt_key_entry.pack(fill="x")

        self._vt_show_btn = tk.Button(key_frame, text=t("virus.vt_show"),
                                       command=self._vt_toggle_key,
                                       font=("Segoe UI", 9), bg=SURFACE2, fg=MUTED,
                                       relief="flat", bd=0, padx=8, cursor="hand2")
        self._vt_show_btn.pack(side="left", padx=4)

        tk.Label(key_frame, text=t("virus.vt_api_hint"),
                 font=("Segoe UI", 9), bg=SURFACE2, fg=MUTED).pack(side="left", padx=(0, 12))

        # Status row
        vt_status_row = tk.Frame(parent, bg=BG)
        vt_status_row.pack(fill="x", pady=(6, 4))
        self._vt_status_var = tk.StringVar(value=t("virus.vt_status_ready"))
        tk.Label(vt_status_row, textvariable=self._vt_status_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(side="left")
        self._vt_count_var = tk.StringVar(value="")
        tk.Label(vt_status_row, textvariable=self._vt_count_var,
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT2).pack(side="right")

        self._vt_progress = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self._vt_progress.pack(fill="x", pady=(0, 6))

        # Results tree
        tf  = tk.Frame(parent, bg=BG)
        tf.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(tf)
        vsb.pack(side="right", fill="y")
        self._vt_tree = ttk.Treeview(
            tf,
            columns=("verdict", "name", "detections", "engines", "threat"),
            show="headings",
            yscrollcommand=vsb.set,
            selectmode="browse"
        )
        vsb.config(command=self._vt_tree.yview)
        self._vt_tree.heading("verdict",    text=t("virus.col_verdict"))
        self._vt_tree.heading("name",       text=t("virus.col_file"))
        self._vt_tree.heading("detections", text=t("virus.col_detections"))
        self._vt_tree.heading("engines",    text=t("virus.col_engines"))
        self._vt_tree.heading("threat",     text=t("virus.col_threat"))
        self._vt_tree.column("verdict",    width=120, minwidth=90,  stretch=False)
        self._vt_tree.column("name",       width=200, minwidth=120, stretch=False)
        self._vt_tree.column("detections", width=100, minwidth=80,  stretch=False, anchor="center")
        self._vt_tree.column("engines",    width=80,  minwidth=60,  stretch=False, anchor="center")
        self._vt_tree.column("threat",     width=300, minwidth=150, stretch=True)
        self._vt_tree.pack(fill="both", expand=True)
        self._vt_tree.tag_configure("malicious",  foreground=DANGER)
        self._vt_tree.tag_configure("suspicious", foreground=WARNING)
        self._vt_tree.tag_configure("clean",      foreground=SUCCESS)
        self._vt_tree.tag_configure("unknown",    foreground=MUTED)
        self._vt_tree.tag_configure("error",      foreground=MUTED)
        self._vt_tree.bind("<Double-1>", self._vt_open_browser)

    def _vt_toggle_key(self):
        show = self._vt_key_entry.cget("show")
        self._vt_key_entry.config(show="" if show == "•" else "•")
        self._vt_show_btn.config(text=t("virus.vt_hide") if show == "•" else t("virus.vt_show"))

    def _start_vt_verify(self):
        api_key = self._vt_key_var.get().strip()
        if not api_key:
            self._switch_result_tab("vt")
            messagebox.showwarning(t("virus.no_key"),
                                   "Enter your VirusTotal API key in the Online tab.")
            return

        # Only verify what's currently shown in malicious/suspicious trees
        flagged = []
        seen_hashes = set()
        for key in ("malicious", "suspicious"):
            tree = self._result_trees[key]
            for iid in tree.get_children():
                name = tree.item(iid, "values")[0]
                # Find matching result with a hash
                for r in self._results:
                    if r["name"] == name and r.get("hash") and r["hash"] not in seen_hashes:
                        flagged.append(r)
                        seen_hashes.add(r["hash"])
                        break

        if not flagged:
            messagebox.showinfo(t("common.warning"),
                                "No flagged files with computed hashes. Run a normal scan first.")
            return

        self._switch_result_tab("vt")
        for item in self._vt_tree.get_children():
            self._vt_tree.delete(item)

        total = len(flagged)
        self._vt_progress.config(maximum=total)
        self._vt_progress["value"] = 0
        self._vt_status_var.set(f"Querying VirusTotal for {total} file(s)…")
        self._vt_count_var.set(f"0 / {total}")
        self._vt_verify_btn.config(state="disabled")

        import time as _time

        def worker():
            for i, r in enumerate(flagged):
                if self._stop.is_set():
                    break
                file_hash = r.get("hash") or r.get("entropy_full") and None
                if not file_hash:
                    continue
                try:
                    raw    = vt_lookup_hash(api_key, file_hash)
                    result = vt_parse_result(raw)
                except Exception as e:
                    result = {"status": "error", "malicious": 0, "suspicious": 0,
                              "total": 0, "names": [], "threat_label": str(e)}

                self._app.after(0, self._vt_add_row, r["name"], r["path"],
                                result, i + 1, total)

                # Free tier: 4 req/min → wait 15s between requests
                if i < total - 1 and not self._stop.is_set():
                    for _ in range(15):
                        if self._stop.is_set():
                            break
                        _time.sleep(1)
                        remaining = 15 - _ - 1
                        self._app.after(0, self._vt_status_var.set,
                                        f"Waiting {remaining}s (free tier limit)…  {i+1}/{total} done")

            def finish():
                self._vt_status_var.set(f"Online verification complete — {total} file(s) checked")
                self._vt_verify_btn.config(state="normal")
                self._vt_progress["value"] = total
            self._app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _vt_add_row(self, name, path, result, done, total):
        status = result["status"]
        mal    = result["malicious"]
        tot    = result["total"]
        threat = result.get("threat_label") or ", ".join(result.get("names", [])[:2])

        icons = {
            "malicious":  t("virus.tab_malicious"),
            "suspicious": t("virus.tab_suspicious"),
            "clean":      "Clean",
            "unknown":    t("virus.vt_not_in_db"),
            "error":      t("virus.vt_error"),
        }
        verdict_label = icons.get(status, status)
        det_str       = f"{mal} / {tot}" if tot > 0 else "—"

        self._vt_tree.insert("", "end",
                              values=(verdict_label, name, det_str, tot, threat),
                              tags=(status,))
        self._vt_progress["value"] = done
        self._vt_count_var.set(f"{done} / {total}")

        # Update Online tab badge
        self._result_counts["vt"].set(done)
        self._update_tab_badge("vt")

        if status == "malicious":
            self._vt_status_var.set(f"{name} confirmed malicious by {mal} engines!")

    def _vt_open_browser(self, event):
        sel = self._vt_tree.selection()
        if not sel:
            return
        name = self._vt_tree.item(sel[0], "values")[1]
        # Find hash for this file
        for r in self._results:
            if r["name"] == name and r.get("hash"):
                import webbrowser
                webbrowser.open(f"https://www.virustotal.com/gui/file/{r['hash']}")
                return

    # ── Deep scan ─────────────────────────────────────────────────────────────
    def _start_deep_scan(self):
        flagged = [r for r in self._results if r["verdict"] in ("malicious", "suspicious")]
        if not flagged:
            return

        if not messagebox.askyesno(
            "Deep Scan",
            f"Run deep scan on {len(flagged)} flagged file(s)?\n\n"
            "Clean files will be removed from results.\n"
            "Each flagged file will be re-scanned with full entropy,\n"
            "string extraction, PE section analysis and more.",
            default="yes"
        ):
            return

        # Reset malicious/suspicious trees — will be re-populated
        for key in ("malicious", "suspicious"):
            tree = self._result_trees[key]
            for item in tree.get_children():
                tree.delete(item)
            self._result_counts[key].set(0)
            self._update_tab_badge(key)

        # Reset clean counter
        self._clean_count_var.set(t("virus.clean_count", n=0))

        self._results = []
        total = len(flagged)

        # UI setup
        self._deepscan_btn.config(state="disabled")
        self._save_btn.config(state="disabled")
        self._scan_btn.config(state="disabled")
        self._lock_controls()
        self._progress.config(mode="determinate", maximum=total)
        self._progress["value"] = 0
        self._status_var.set(f"Deep scanning {total} flagged file(s)…")
        self._count_var.set(f"0 / {total}")
        self._start_time = time.time()
        self._elapsed_var.set("⏱ 0s")
        self._stop.clear()
        self._stop_btn.config(state="normal")

        done_counter = [0]
        lock = threading.Lock()
        conf = cfg.load()
        n_threads = conf["scanner"]["threads"]

        from scanner.deep_scan import deep_scan_file

        def deep_scan_one(r):
            if self._stop.is_set():
                return None
            try:
                return deep_scan_file(r["path"])
            except Exception as e:
                return {
                    "path": r["path"], "name": Path(r["path"]).name,
                    "verdict": "error", "score": 0, "hash": None,
                    "hash_hit": False, "entropy_full": 0.0,
                    "pe_sections": [], "compile_ts": 0,
                    "strings": {}, "yara_matches": [],
                    "summary": [f"Deep scan error: {e}"], "signature": {},
                }

        with self._pending_lock:
            self._pending_results.clear()

        def worker():
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=n_threads) as pool:
                futures = {pool.submit(deep_scan_one, r): r for r in flagged}
                for future in as_completed(futures):
                    if self._stop.is_set():
                        break
                    result = future.result()
                    if result is None:
                        continue
                    with lock:
                        done_counter[0] += 1
                        done = done_counter[0]
                    self._results.append(result)
                    with self._pending_lock:
                        self._pending_results.append((result, done, total))

            self._scan_done_total = done_counter[0]
            self._scan_done_flag  = True

        self._scan_done_flag  = False
        self._scan_done_total = 0
        self._scan_total      = [total]
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        self._app.after(100, self._flush_deep_results)
        self._tick_timer()

    def _add_deep_row(self, result, done, total):
        verdict = result["verdict"]
        self._count_var.set(f"{done:,} / {total:,}")
        self._progress["value"] = done

        if verdict in ("skipped", "error", "unknown"):
            return

        score_str   = f"{result['score']}/100"
        entropy_str = f"{result['entropy_full']:.2f}" if result.get("entropy_full") else "—"
        top_finding = result["summary"][0] if result["summary"] else "No issues found"
        if len(top_finding) > 75:
            top_finding = top_finding[:72] + "…"

        tab_key = verdict if verdict in self._result_trees else "clean"
        if tab_key == "clean":
            self._result_counts["clean"].set(self._result_counts["clean"].get() + 1)
            self._clean_count_var.set(t("virus.clean_count", n=f"{self._result_counts['clean'].get():,}"))
            return
        tree = self._result_trees[tab_key]
        if len(tree.get_children()) < 500:
            tree.insert("", "end",
                        values=(result["name"], score_str, top_finding, entropy_str),
                        tags=(tab_key,))
        self._result_counts[tab_key].set(self._result_counts[tab_key].get() + 1)
        self._update_tab_badge(tab_key)

        if verdict == "malicious":
            if self._active_tab != "malicious":
                self._switch_result_tab("malicious")
            children = tree.get_children()
            if children:
                tree.see(children[-1])

    def _add_row(self, result, done, total):
        verdict = result["verdict"]
        self._count_var.set(f"{done} / {total}")
        self._progress["value"] = done

        if verdict in ("skipped", "error"):
            return

        score_str   = f"{result['score']}/100"
        entropy_str = f"{result['entropy']:.2f}" if result["entropy"] else "—"
        top_finding = result["summary"][0] if result["summary"] else "No issues found"
        if len(top_finding) > 75:
            top_finding = top_finding[:72] + "…"

        tab_key = verdict if verdict in self._result_trees else "clean"
        if tab_key == "clean":
            current = self._result_counts.get("clean", tk.IntVar(value=0))
            if "clean" not in self._result_counts:
                self._result_counts["clean"] = current
            self._result_counts["clean"].set(self._result_counts["clean"].get() + 1)
            self._clean_count_var.set(t("virus.clean_count", n=f"{self._result_counts['clean'].get():,}"))
            return
        tree = self._result_trees[tab_key]
        if len(tree.get_children()) < 500:
            tree.insert("", "end",
                        values=(result["name"], score_str, top_finding, entropy_str),
                        tags=(tab_key,))

        # Update badge count
        self._result_counts[tab_key].set(self._result_counts[tab_key].get() + 1)
        self._update_tab_badge(tab_key)

        # Auto-switch to malicious tab when first threat is found
        if verdict == "malicious":
            if self._active_tab != "malicious":
                self._switch_result_tab("malicious")
            children = tree.get_children()
            if children:
                tree.see(children[-1])
            self._status_var.set(f"⚠  Threat found: {result['name']}")

    def _stop_scan(self):
        self._stop.set()
        self._stop_timer()
        elapsed = time.time() - self._start_time
        self._elapsed_var.set(f"{t('virus.stopped_at', t=self._fmt_elapsed(elapsed))}")
        try:
            if str(self._progress.cget("mode")) == "indeterminate":
                self._progress.stop()
                self._progress.config(mode="determinate")
        except Exception:
            pass
        self._status_var.set(t("virus.btn_stop"))
        self._stop_btn.config(state="disabled")
        self._unlock_controls()

    def _clear(self):
        self._stop_timer()
        for tree in self._result_trees.values():
            for item in tree.get_children():
                tree.delete(item)
        # Clear VT tree too
        if hasattr(self, "_vt_tree"):
            for item in self._vt_tree.get_children():
                self._vt_tree.delete(item)
            self._vt_progress["value"] = 0
            self._vt_status_var.set(t("virus.vt_status_ready"))
            self._vt_count_var.set("")
        for key, var in self._result_counts.items():
            var.set(0)
            if key in self._tab_btns:
                self._update_tab_badge(key)
        self._clean_count_var.set(t("virus.clean_count", n=0))
        self._results        = []
        self._progress["value"] = 0
        self._status_var.set(t("virus.status_ready"))
        self._count_var.set("")
        self._elapsed_var.set("")
        self._save_btn.config(state="disabled")
        self._deepscan_btn.config(state="disabled")
        self._vt_verify_btn.config(state="disabled")

    # ── Detail popup ──────────────────────────────────────────────────────────
    def _show_details(self, event, tab_key: str):
        tree = self._result_trees[tab_key]
        sel  = tree.selection()
        if not sel:
            return
        idx     = tree.index(sel[0])
        results = [r for r in self._results if r["verdict"] == tab_key]
        if idx >= len(results):
            return
        self._open_detail_window(results[idx])

    def _open_detail_window(self, result):
        win = tk.Toplevel(self._app)
        win.title(f"Scan details — {result['name']}")
        is_deep = bool(result.get("pe_sections") or result.get("strings", {}).get("urls"))
        win.geometry("760x600" if is_deep else "640x480")
        win.configure(bg=BG)
        win.resizable(True, True)

        tk.Label(win, text=result["name"], font=("Segoe UI", 14, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=20, pady=(16, 4))
        tk.Label(win, text=result["path"], font=("Segoe UI", 9),
                 bg=BG, fg=MUTED, wraplength=600, justify="left").pack(anchor="w", padx=20)

        verdict_colors = {"malicious": DANGER, "suspicious": WARNING,
                          "clean": SUCCESS, "error": MUTED}
        color = verdict_colors.get(result["verdict"], TEXT)
        tk.Label(win, text=f"Verdict: {result['verdict'].upper()}   Score: {result['score']}/100",
                 font=("Segoe UI", 12, "bold"), bg=BG, fg=color).pack(anchor="w", padx=20, pady=(12, 4))

        # Details text
        txt_frame = tk.Frame(win, bg=SURFACE)
        txt_frame.pack(fill="both", expand=True, padx=20, pady=(8, 16))
        vsb = ttk.Scrollbar(txt_frame)
        vsb.pack(side="right", fill="y")
        txt = tk.Text(txt_frame, bg=SURFACE, fg=TEXT, font=("Consolas", 10),
                      relief="flat", bd=8, wrap="word", yscrollcommand=vsb.set)
        vsb.config(command=txt.yview)
        txt.pack(fill="both", expand=True)

        lines = []
        lines.append(f"SHA-256:  {result.get('hash') or 'not computed'}")
        size = result.get('size', 0)
        lines.append(f"Size:     {size:,} bytes" if size else "Size:     unknown")

        # Show full entropy if deep scan, else normal entropy
        if result.get("entropy_full"):
            lines.append(f"Entropy:  {result['entropy_full']:.4f} (full file — deep scan)")
        else:
            lines.append(f"Entropy:  {result.get('entropy', 0):.4f} ({result.get('entropy_label','normal')})")

        lines.append(f"Hash DB:  {'YES — known malware' if result.get('hash_hit') else 'No match'}")

        sig = result.get("signature", {})
        if sig.get("status") not in ("unsupported", "unknown", "", None):
            status_str = sig["status"].replace("_", " ").title()
            signer_str = f" — {sig['signer']}" if sig.get("signer") else ""
            lines.append(f"Signature: {status_str}{signer_str}")

        lines.append("")
        lines.append("── FINDINGS ─────────────────────────────────────────────")
        for s in result.get("summary", []):
            lines.append(f"  • {s}")

        if result.get("yara_matches"):
            lines.append("")
            lines.append("── YARA MATCHES ──────────────────────────────────────────")
            for m in result["yara_matches"]:
                lines.append(f"  [{m['severity'].upper()}] {m['rule']}: {m['description']}")

        # PE sections (deep scan only)
        if result.get("pe_sections"):
            lines.append("")
            lines.append("── PE SECTIONS ───────────────────────────────────────────")
            for sec in result["pe_sections"]:
                flags = ", ".join(sec["flags"]) if sec["flags"] else "—"
                lines.append(f"  {sec['name']:<12} entropy={sec['entropy']:.2f}  [{flags}]")

        # Extracted strings (deep scan only)
        strings = result.get("strings", {})
        for category, items in [
            ("URLs",           strings.get("urls", [])),
            ("IPs",            strings.get("ips", [])),
            ("Registry keys",  strings.get("registry", [])),
            ("Shell commands", strings.get("commands", [])),
            ("File paths",     strings.get("paths", [])),
            ("Emails",         strings.get("emails", [])),
        ]:
            if items:
                lines.append("")
                lines.append(f"── {category.upper()} " + "─" * max(1, 48 - len(category)))
                for item in items[:15]:
                    lines.append(f"  {item}")
        txt.insert("1.0", "\n".join(lines))
        txt.config(state="disabled")

        # Open location button
        tk.Button(win, text=t("virus.detail_open"),
                  command=lambda: self._open_path(os.path.dirname(result["path"])),
                  font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                  relief="flat", bd=0, padx=12, pady=6, cursor="hand2").pack(pady=(0, 12))

    # ── Right click ───────────────────────────────────────────────────────────
    def _right_click(self, event, tab_key: str):
        tree = self._result_trees[tab_key]
        sel  = tree.identify_row(event.y)
        if not sel:
            return
        tree.selection_set(sel)
        idx     = tree.index(sel)
        results = [r for r in self._results if r["verdict"] == tab_key]
        if idx >= len(results):
            return
        result = results[idx]
        path   = result["path"]

        menu = tk.Menu(self._app, tearoff=0, bg=SURFACE2, fg=TEXT,
                       activebackground=ACCENT, activeforeground="white", relief="flat", bd=0)
        menu.add_command(label=t("virus.detail_findings"),
                         command=lambda: self._open_detail_window(result))
        menu.add_command(label=t("common.open_location"),
                         command=lambda: self._open_path(os.path.dirname(path)))
        menu.add_command(label=t("common.copy_path"),
                         command=lambda: self._copy(path))
        if result["verdict"] in ("malicious", "suspicious"):
            menu.add_separator()
            menu.add_command(label="🗑  Delete this file",
                             command=lambda: self._delete_file(sel, path, tree))
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_file(self, iid, path, tree):
        if not messagebox.askyesno("Delete file",
                                   f"Permanently delete:\n{path}\n\nThis cannot be undone.",
                                   icon="warning", default="no"):
            return
        try:
            os.remove(path)
            tree.delete(iid)
            self._status_var.set(f"Deleted: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror(t("virus.vt_error"), str(e))

    def _open_path(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as e:
            messagebox.showerror(t("virus.vt_error"), str(e))

    def _copy(self, text):
        self._app.clipboard_clear()
        self._app.clipboard_append(text)

    # ── Save report ───────────────────────────────────────────────────────────
    def _save_report(self):
        if not self._results:
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile=f"scan_report_{ts}.txt", title="Save report"
        )
        if not path:
            return

        mal  = [r for r in self._results if r["verdict"] == "malicious"]
        susp = [r for r in self._results if r["verdict"] == "suspicious"]
        cln  = [r for r in self._results if r["verdict"] == "clean"]
        skip = [r for r in self._results if r["verdict"] == "skipped"]

        # Build target description from current drive selection
        if self._file_var.get().strip():
            target_desc = self._file_var.get().strip()
        elif self._all_drives_var.get():
            target_desc = t("virus.all_drives")
        else:
            selected = [d for d, v in self._drive_vars.items() if v.get()]
            target_desc = ", ".join(selected) if selected else "Unknown"

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"Local Virus Scanner Report\n{'='*60}\n")
                f.write(f"Date:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Target:     {target_desc}\n")
                f.write(f"Scanned:    {len(self._results) - len(skip)}\n")
                f.write(f"Malicious:  {len(mal)}\n")
                f.write(f"Suspicious: {len(susp)}\n")
                f.write(f"Clean:      {len(cln)}\n\n")

                for section, items in [
                    ("🔴 MALICIOUS", mal),
                    ("🟡 SUSPICIOUS", susp),
                    ("🟢 CLEAN", cln),
                ]:
                    if items:
                        f.write(f"{section} ({len(items)})\n{'-'*60}\n")
                        for r in items:
                            f.write(f"  File:    {r['name']}\n")
                            f.write(f"  Path:    {r['path']}\n")
                            f.write(f"  Score:   {r['score']}/100\n")
                            entropy = r.get('entropy_full') or r.get('entropy', 0)
                            entropy_label = r.get('entropy_label', 'full scan' if r.get('entropy_full') else 'normal')
                            f.write(f"  Entropy: {entropy:.4f} ({entropy_label})\n")
                            if r["hash"]:
                                f.write(f"  SHA-256: {r['hash']}\n")
                            for s in r["summary"]:
                                f.write(f"  → {s}\n")
                            f.write("\n")

            messagebox.showinfo("Saved", f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save report:\n{e}")