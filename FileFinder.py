"""
filesearch_gui.py — File Finder + Cache Cleaner
Run: python filesearch_gui.py
Requires: Python 3.10+ (standard library only, no pip needed)
"""

import os
import sys
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime


# ── Colors ────────────────────────────────────────────────────────────────────
ACCENT   = "#5B6EF5"
ACCENT2  = "#8B9EFF"
BG       = "#0F1117"
SURFACE  = "#1A1D27"
SURFACE2 = "#22263A"
TEXT     = "#E8EAF6"
MUTED    = "#6B7280"
SUCCESS  = "#4ADE80"
WARNING  = "#FACC15"
DANGER   = "#F87171"
FOLDER_C = "#FACC15"
FILE_C   = "#93C5FD"


# ── Detect drives ─────────────────────────────────────────────────────────────
def get_drives():
    drives = []
    if sys.platform == "win32":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:
        drives.append("/")
        home = str(Path.home())
        if home != "/":
            drives.append(home)
        for vol in ["/Volumes", "/mnt", "/media"]:
            if os.path.isdir(vol):
                try:
                    for sub in os.listdir(vol):
                        full = os.path.join(vol, sub)
                        if os.path.isdir(full):
                            drives.append(full)
                except PermissionError:
                    pass
    return drives


DEFAULT_SKIP = {
    "$Recycle.Bin", "System Volume Information", "Windows",
    ".Spotlight-V100", ".Trashes", ".fseventsd",
    "proc", "sys", "dev",
    "node_modules", "__pycache__", ".git", ".svn", "venv", ".venv",
}


# ── Cache target definitions ──────────────────────────────────────────────────
def build_cache_targets():
    home = Path.home()
    win  = sys.platform == "win32"
    mac  = sys.platform == "darwin"
    lnx  = sys.platform.startswith("linux")

    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) if win else None
    roaming = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) if win else None
    tmp = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))

    targets = []

    # ── System / Windows ──
    if win:
        targets += [
            ("System", "Windows Temp files",      [tmp],                                          "Temporary files created by Windows and apps"),
            ("System", "Windows Prefetch",         [Path("C:/Windows/Prefetch")],                 "App launch cache — speeds up startup but can grow large"),
            ("System", "Recent files list",        [home / "AppData/Roaming/Microsoft/Windows/Recent"], "Jump list / recently opened files shortcuts"),
            ("System", "Thumbnail cache",          [home / "AppData/Local/Microsoft/Windows/Explorer"], "Explorer thumbnail previews"),
        ]
    if mac:
        targets += [
            ("System", "macOS user cache",         [home / "Library/Caches"],                     "App caches stored per-user"),
            ("System", "macOS system logs",        [Path("/private/var/log")],                    "System log files"),
            ("System", "Trash",                    [home / ".Trash"],                             "Files in your Trash bin"),
        ]
    if lnx:
        targets += [
            ("System", "Linux user cache",         [home / ".cache"],                             "App caches in ~/.cache"),
            ("System", "Linux temp",               [Path("/tmp")],                                "Global temp files"),
            ("System", "Journald logs",            [Path("/var/log/journal")],                    "Systemd journal logs"),
        ]

    # ── Browsers ──
    if win:
        chrome_cache  = local / "Google/Chrome/User Data/Default/Cache"
        chrome_code   = local / "Google/Chrome/User Data/Default/Code Cache"
        edge_cache    = local / "Microsoft/Edge/User Data/Default/Cache"
        firefox_base  = roaming / "Mozilla/Firefox/Profiles"
        opera_cache   = roaming / "Opera Software/Opera Stable/Cache"
        brave_cache   = local / "BraveSoftware/Brave-Browser/User Data/Default/Cache"
    elif mac:
        chrome_cache  = home / "Library/Caches/Google/Chrome/Default/Cache"
        chrome_code   = home / "Library/Caches/Google/Chrome/Default/Code Cache"
        edge_cache    = home / "Library/Caches/Microsoft Edge/Default/Cache"
        firefox_base  = home / "Library/Application Support/Firefox/Profiles"
        opera_cache   = home / "Library/Caches/com.operasoftware.Opera"
        brave_cache   = home / "Library/Caches/BraveSoftware/Brave-Browser/Default/Cache"
    else:
        chrome_cache  = home / ".cache/google-chrome/Default/Cache"
        chrome_code   = home / ".cache/google-chrome/Default/Code Cache"
        edge_cache    = home / ".cache/microsoft-edge/Default/Cache"
        firefox_base  = home / ".mozilla/firefox"
        opera_cache   = home / ".cache/opera"
        brave_cache   = home / ".cache/BraveSoftware/Brave-Browser/Default/Cache"

    # Collect Firefox profile caches dynamically
    firefox_caches = []
    if firefox_base.exists():
        try:
            for profile in firefox_base.iterdir():
                c = profile / "cache2"
                if c.exists():
                    firefox_caches.append(c)
        except Exception:
            pass
    if not firefox_caches:
        firefox_caches = [firefox_base / "*.default/cache2"]

    targets += [
        ("Browsers", "Chrome cache",      [chrome_cache, chrome_code], "HTTP cache + JS code cache for Google Chrome"),
        ("Browsers", "Edge cache",         [edge_cache],               "HTTP cache for Microsoft Edge"),
        ("Browsers", "Firefox cache",      firefox_caches,             "HTTP cache for all Firefox profiles"),
        ("Browsers", "Opera cache",        [opera_cache],              "HTTP cache for Opera"),
        ("Browsers", "Brave cache",        [brave_cache],              "HTTP cache for Brave Browser"),
    ]

    # ── Dev tools ──
    targets += [
        ("Dev", "npm cache",         [home / ".npm/_cacache"],           "npm package cache (~/.npm)"),
        ("Dev", "pip cache",         [home / ".cache/pip"],              "pip wheel/package cache"),
        ("Dev", "Gradle cache",      [home / ".gradle/caches"],          "Gradle build cache"),
        ("Dev", "Maven cache",       [home / ".m2/repository"],          "Maven local repository (~/.m2)"),
        ("Dev", "Yarn cache",        [home / ".yarn/cache"],             "Yarn package cache"),
        ("Dev", "pnpm cache",        [home / ".pnpm-store"],             "pnpm content-addressable store"),
        ("Dev", "__pycache__",       [],                                 "Python bytecode cache dirs (scanned from home)"),
        ("Dev", ".mypy_cache",       [],                                 "mypy type-check cache dirs"),
        ("Dev", "Rust cargo cache",  [home / ".cargo/registry/cache"],   "Cargo downloaded crate cache"),
    ]

    # ── IDEs ──
    if win:
        idea_system = local / "JetBrains"
        vscode_cache = roaming / "Code/User/workspaceStorage"
    elif mac:
        idea_system  = home / "Library/Caches/JetBrains"
        vscode_cache = home / "Library/Application Support/Code/User/workspaceStorage"
    else:
        idea_system  = home / ".cache/JetBrains"
        vscode_cache = home / ".config/Code/User/workspaceStorage"

    targets += [
        ("IDEs", "JetBrains system cache", [idea_system],  "IntelliJ / PyCharm / WebStorm etc. caches"),
        ("IDEs", "VS Code workspace cache", [vscode_cache], "Per-workspace extension data & cache"),
    ]

    return targets  # list of (group, label, [Path, ...], description)


# ── Dir size helper ───────────────────────────────────────────────────────────
def dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    total += dir_size(Path(entry.path))
                else:
                    total += entry.stat().st_size
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def fmt_size(b):
    if b is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.0f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ── Search worker ─────────────────────────────────────────────────────────────
def run_search(roots, query, exact, search_type, skip_dirs, callback, done_cb, progress_cb, stop_event):
    keywords = [q.strip() for q in query.strip().split() if q.strip()]
    if not keywords:
        done_cb(0)
        return
    count = 0
    total_roots = len(roots)

    def matches(name):
        name_l = name.lower()
        if exact:
            stem = Path(name).stem.lower()
            return any(kw.lower() == stem or kw.lower() == name_l for kw in keywords)
        return any(kw.lower() in name_l for kw in keywords)

    for root_idx, root in enumerate(roots):
        if stop_event.is_set():
            break
        dirs_in_root = 0
        try:
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                if stop_event.is_set():
                    break
                dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith('.')]
                dirs_in_root += 1
                current = Path(dirpath)

                # Report progress: (root_idx, total_roots, dirs_scanned, current_path)
                progress_cb(root_idx, total_roots, dirs_in_root, str(current))

                if search_type in ("both", "folders"):
                    if matches(current.name) and str(current) != root:
                        try:
                            callback("folder", current.name, str(current), None)
                            count += 1
                        except Exception:
                            pass
                if search_type in ("both", "files"):
                    for fname in filenames:
                        if stop_event.is_set():
                            break
                        if matches(fname):
                            fpath = current / fname
                            try:
                                size = fpath.stat().st_size
                            except Exception:
                                size = None
                            callback("file", fname, str(fpath), size)
                            count += 1
        except (PermissionError, Exception):
            pass

    done_cb(count)


# ══════════════════════════════════════════════════════════════════════════════
# Main App
# ══════════════════════════════════════════════════════════════════════════════
class FileSearchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Finder")
        self.geometry("980x720")
        self.minsize(720, 520)
        self.configure(bg=BG)

        self._stop_event    = threading.Event()
        self._search_thread = None
        self._result_count  = 0
        self._drives        = get_drives()
        self._cache_targets = build_cache_targets()
        self._cache_vars    = {}
        self._cache_size_labels = {}

        # Progress / timing
        self._search_start_time = 0.0
        self._dirs_scanned      = 0
        self._current_root_idx  = 0
        self._total_roots       = 0
        self._timer_id          = None

        self._build_ui()
        self._apply_styles()

    # ── Top-level layout ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=SURFACE, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="🔍  File Finder", font=("Segoe UI", 18, "bold"),
                 bg=SURFACE, fg=TEXT).pack(side="left", padx=24)
        tk.Label(header, text="Search · Delete · Clean cache",
                 font=("Segoe UI", 11), bg=SURFACE, fg=MUTED).pack(side="left", padx=4)

        # Tab bar
        tab_bar = tk.Frame(self, bg=SURFACE2)
        tab_bar.pack(fill="x")

        self._tab_frames = {}
        self._tab_btns   = {}

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True)

        for name in ("Search", "Cache Cleaner"):
            frame = tk.Frame(content, bg=BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._tab_frames[name] = frame

            btn = tk.Button(
                tab_bar, text=name,
                font=("Segoe UI", 11), relief="flat", bd=0,
                padx=20, pady=10, cursor="hand2",
                command=lambda n=name: self._switch_tab(n)
            )
            btn.pack(side="left")
            self._tab_btns[name] = btn

        self._build_search_tab(self._tab_frames["Search"])
        self._build_cache_tab(self._tab_frames["Cache Cleaner"])
        self._switch_tab("Search")

    def _switch_tab(self, name):
        for n, f in self._tab_frames.items():
            f.lower()
        self._tab_frames[name].lift()
        for n, b in self._tab_btns.items():
            if n == name:
                b.config(bg=ACCENT, fg="white")
            else:
                b.config(bg=SURFACE2, fg=MUTED)

    # ══════════════════════════════════════════════════════════════════════════
    # SEARCH TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_search_tab(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        left = tk.Frame(body, bg=SURFACE, width=280)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        self._build_search_controls(left)

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_results_panel(right)

    def _build_search_controls(self, parent):
        tk.Label(parent, text="SEARCH QUERY", font=("Segoe UI", 9, "bold"),
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

        tk.Label(parent, text="MATCH MODE", font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(14, 4))
        self._exact_var = tk.BooleanVar(value=False)
        mf = tk.Frame(parent, bg=SURFACE)
        mf.pack(fill="x", padx=16)
        self._btn_keyword = self._toggle_btn(mf, "Keyword",    lambda: self._set_mode(False), active=True)
        self._btn_keyword.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._btn_exact   = self._toggle_btn(mf, "Exact name", lambda: self._set_mode(True),  active=False)
        self._btn_exact.pack(side="left", fill="x", expand=True)
        tk.Label(parent, text="Keyword: 'disc' finds 'Discord'\nExact: 'discord' only finds 'discord'",
                 font=("Segoe UI", 9), bg=SURFACE, fg=MUTED, justify="left"
                 ).pack(anchor="w", padx=16, pady=(4, 0))

        tk.Label(parent, text="SEARCH FOR", font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(14, 4))
        self._type_var = tk.StringVar(value="both")
        tf = tk.Frame(parent, bg=SURFACE)
        tf.pack(fill="x", padx=16)
        for label, val in [("Files & folders", "both"), ("Files only", "files"), ("Folders only", "folders")]:
            tk.Radiobutton(tf, text=label, variable=self._type_var, value=val,
                           font=("Segoe UI", 11), bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
                           activebackground=SURFACE, activeforeground=TEXT,
                           relief="flat", bd=0).pack(anchor="w", pady=1)

        tk.Label(parent, text="SEARCH IN", font=("Segoe UI", 9, "bold"),
                 bg=SURFACE, fg=MUTED).pack(anchor="w", padx=16, pady=(14, 4))
        dsf = tk.Frame(parent, bg=SURFACE)
        dsf.pack(fill="x", padx=16)
        self._drive_vars = {}
        self._all_drives_var = tk.BooleanVar(value=True)
        tk.Checkbutton(dsf, text="All drives / entire system",
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
        self._custom_var = tk.StringVar()
        self._custom_entry = tk.Entry(cf, textvariable=self._custom_var,
                                      font=("Segoe UI", 10), bg=SURFACE2, fg=TEXT,
                                      insertbackground=ACCENT, relief="flat", bd=6, state="disabled")
        self._custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._browse_btn = tk.Button(cf, text="Browse", command=self._browse_folder,
                                     font=("Segoe UI", 10), bg=SURFACE2, fg=MUTED,
                                     relief="flat", bd=0, padx=10, cursor="hand2", state="disabled")
        self._browse_btn.pack(side="left")

        tk.Frame(parent, bg=SURFACE).pack(fill="y", expand=True)
        self._search_btn = tk.Button(parent, text="Search", command=self._start_search,
                                     font=("Segoe UI", 13, "bold"), bg=ACCENT, fg="white",
                                     relief="flat", bd=0, pady=12, cursor="hand2",
                                     activebackground=ACCENT2, activeforeground="white")
        self._search_btn.pack(fill="x", padx=16, pady=(0, 16))

    def _build_results_panel(self, parent):
        status_bar = tk.Frame(parent, bg=BG)
        status_bar.pack(fill="x", pady=(0, 4))
        self._status_var = tk.StringVar(value="Ready — enter a keyword and press Search")
        tk.Label(status_bar, textvariable=self._status_var,
                 font=("Segoe UI", 10), bg=BG, fg=MUTED, anchor="w").pack(side="left")
        self._count_var = tk.StringVar(value="")
        tk.Label(status_bar, textvariable=self._count_var,
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=ACCENT2, anchor="e").pack(side="right")

        # Progress info row: percent · elapsed · dirs
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

        # Current path being scanned
        self._curpath_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._curpath_var,
                 font=("Segoe UI", 9), bg=BG, fg=SURFACE2, anchor="w",
                 wraplength=600, justify="left").pack(fill="x", pady=(0, 4))

        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 6))
        self._save_btn = tk.Button(toolbar, text="💾  Save results", command=self._save_results,
                                   font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2", state="disabled")
        self._save_btn.pack(side="left", padx=(0, 8))
        self._clear_btn = tk.Button(toolbar, text="✕  Clear", command=self._clear_results,
                                    font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                                    relief="flat", bd=0, padx=12, pady=6, cursor="hand2")
        self._clear_btn.pack(side="left")
        self._stop_btn = tk.Button(toolbar, text="⏹  Stop", command=self._stop_search,
                                   font=("Segoe UI", 10), bg=SURFACE, fg=DANGER,
                                   relief="flat", bd=0, padx=12, pady=6, cursor="hand2", state="disabled")
        self._stop_btn.pack(side="right")
        self._delete_btn = tk.Button(toolbar, text="🗑  Delete selected", command=self._delete_selected,
                                     font=("Segoe UI", 10), bg=SURFACE, fg=DANGER,
                                     relief="flat", bd=0, padx=12, pady=6, cursor="hand2", state="disabled")
        self._delete_btn.pack(side="right", padx=(0, 8))

        tree_frame = tk.Frame(parent, bg=BG)
        tree_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        self._tree = ttk.Treeview(tree_frame, columns=("type", "name", "path", "size"),
                                   show="headings", yscrollcommand=scrollbar.set, selectmode="browse")
        scrollbar.config(command=self._tree.yview)
        self._tree.heading("type", text="Type")
        self._tree.heading("name", text="Name")
        self._tree.heading("path", text="Full path")
        self._tree.heading("size", text="Size")
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
        self._results = []

    # ══════════════════════════════════════════════════════════════════════════
    # CACHE CLEANER TAB
    # ══════════════════════════════════════════════════════════════════════════
    def _build_cache_tab(self, parent):
        # Top bar
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(top, text="Select what to clean, then press Scan to see sizes before deleting.",
                 font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(side="left")

        sel_frame = tk.Frame(top, bg=BG)
        sel_frame.pack(side="right")
        tk.Button(sel_frame, text="Select all",   command=self._cache_select_all,
                  font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(sel_frame, text="Deselect all", command=self._cache_deselect_all,
                  font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2").pack(side="left")

        # Scrollable checklist
        list_outer = tk.Frame(parent, bg=BG)
        list_outer.pack(fill="both", expand=True, padx=20)

        canvas = tk.Canvas(list_outer, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(list_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._cache_inner = tk.Frame(canvas, bg=BG)
        canvas_window = canvas.create_window((0, 0), window=self._cache_inner, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def on_canvas_resize(e):
            canvas.itemconfig(canvas_window, width=e.width)

        self._cache_inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_canvas_resize)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Group headers + rows
        current_group = None
        for group, label, paths, desc in self._cache_targets:
            if group != current_group:
                current_group = group
                gh = tk.Frame(self._cache_inner, bg=BG)
                gh.pack(fill="x", pady=(16, 4))
                tk.Label(gh, text=group.upper(), font=("Segoe UI", 9, "bold"),
                         bg=BG, fg=ACCENT2).pack(side="left")
                tk.Frame(gh, bg=SURFACE2, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

            self._build_cache_row(self._cache_inner, label, paths, desc)

        # Bottom action bar
        bottom = tk.Frame(parent, bg=SURFACE, pady=14)
        bottom.pack(fill="x", side="bottom")

        self._cache_status_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._cache_status_var,
                 font=("Segoe UI", 10), bg=SURFACE, fg=MUTED).pack(side="left", padx=20)

        self._cache_total_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._cache_total_var,
                 font=("Segoe UI", 11, "bold"), bg=SURFACE, fg=SUCCESS).pack(side="left", padx=8)

        btn_frame = tk.Frame(bottom, bg=SURFACE)
        btn_frame.pack(side="right", padx=20)

        self._scan_btn = tk.Button(btn_frame, text="Scan sizes",
                                   command=self._cache_scan,
                                   font=("Segoe UI", 11), bg=SURFACE2, fg=TEXT,
                                   relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        self._scan_btn.pack(side="left", padx=(0, 10))

        self._clean_btn = tk.Button(btn_frame, text="Clean selected",
                                    command=self._cache_clean,
                                    font=("Segoe UI", 11, "bold"), bg=DANGER, fg="white",
                                    relief="flat", bd=0, padx=16, pady=8, cursor="hand2")
        self._clean_btn.pack(side="left")

    def _build_cache_row(self, parent, label, paths, desc):
        var = tk.BooleanVar(value=False)
        self._cache_vars[label] = var

        row = tk.Frame(parent, bg=SURFACE, pady=0)
        row.pack(fill="x", pady=2)

        cb = tk.Checkbutton(row, variable=var, text=label,
                             font=("Segoe UI", 11), bg=SURFACE, fg=TEXT,
                             selectcolor=SURFACE2, activebackground=SURFACE,
                             activeforeground=TEXT, relief="flat", anchor="w",
                             width=22)
        cb.pack(side="left", padx=(12, 0))

        tk.Label(row, text=desc, font=("Segoe UI", 10), bg=SURFACE, fg=MUTED,
                 anchor="w").pack(side="left", padx=8, fill="x", expand=True)

        size_lbl = tk.Label(row, text="—", font=("Segoe UI", 10, "bold"),
                             bg=SURFACE, fg=MUTED, width=10, anchor="e")
        size_lbl.pack(side="right", padx=12)
        self._cache_size_labels[label] = size_lbl

    # ── Cache actions ─────────────────────────────────────────────────────────
    def _cache_select_all(self):
        for var in self._cache_vars.values():
            var.set(True)

    def _cache_deselect_all(self):
        for var in self._cache_vars.values():
            var.set(False)

    def _cache_scan(self):
        selected = [label for label, var in self._cache_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Nothing selected", "Check at least one cache category to scan.")
            return

        self._cache_status_var.set("Scanning…")
        self._cache_total_var.set("")
        self._scan_btn.config(state="disabled")

        def worker():
            total_bytes = 0
            for group, label, paths, desc in self._cache_targets:
                if label not in selected:
                    continue
                size = self._measure_cache(label, paths)
                total_bytes += size
                color = WARNING if size > 50 * 1024 * 1024 else (SUCCESS if size > 0 else MUTED)
                display = fmt_size(size) if size > 0 else "not found"
                self.after(0, self._update_size_label, label, display, color)

            def finish():
                self._cache_status_var.set("Scan complete")
                self._cache_total_var.set(f"Total: {fmt_size(total_bytes)}")
                self._scan_btn.config(state="normal")
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _measure_cache(self, label, paths):
        if label == "__pycache__":
            return self._scan_named_dirs("__pycache__")
        if label == ".mypy_cache":
            return self._scan_named_dirs(".mypy_cache")
        total = 0
        for p in paths:
            p = Path(p)
            if p.exists():
                total += dir_size(p)
        return total

    def _scan_named_dirs(self, dirname):
        total = 0
        home = Path.home()
        try:
            for dirpath, dirnames, _ in os.walk(home):
                dirnames[:] = [d for d in dirnames if d not in {".git", "venv", ".venv", "node_modules"}]
                if dirname in dirnames:
                    total += dir_size(Path(dirpath) / dirname)
        except Exception:
            pass
        return total

    def _update_size_label(self, label, text, color):
        lbl = self._cache_size_labels.get(label)
        if lbl:
            lbl.config(text=text, fg=color)

    def _cache_clean(self):
        selected = [label for label, var in self._cache_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Nothing selected", "Check at least one cache category to clean.")
            return

        confirmed = messagebox.askyesno(
            "Confirm cache clean",
            f"Permanently delete cache for {len(selected)} selected categor{'y' if len(selected)==1 else 'ies'}?\n\n"
            + "\n".join(f"  • {s}" for s in selected)
            + "\n\nThis cannot be undone.",
            icon="warning", default="no"
        )
        if not confirmed:
            return

        self._cache_status_var.set("Cleaning…")
        self._cache_total_var.set("")
        self._clean_btn.config(state="disabled")
        self._scan_btn.config(state="disabled")

        def worker():
            freed = 0
            errors = []
            for group, label, paths, desc in self._cache_targets:
                if label not in selected:
                    continue
                f, e = self._do_clean(label, paths)
                freed += f
                errors.extend(e)
                self.after(0, self._update_size_label, label, "cleaned", SUCCESS)

            def finish():
                self._cache_status_var.set(f"Done — {len(errors)} error(s)" if errors else "All done!")
                self._cache_total_var.set(f"Freed: {fmt_size(freed)}")
                self._clean_btn.config(state="normal")
                self._scan_btn.config(state="normal")
                if errors:
                    messagebox.showwarning("Some errors", f"{len(errors)} items could not be deleted:\n\n" +
                                           "\n".join(errors[:10]))
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _do_clean(self, label, paths):
        freed = 0
        errors = []

        if label in ("__pycache__", ".mypy_cache"):
            dirname = label
            home = Path.home()
            try:
                for dirpath, dirnames, _ in os.walk(home):
                    dirnames[:] = [d for d in dirnames if d not in {".git", "venv", ".venv", "node_modules"}]
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

        for p in paths:
            p = Path(p)
            if not p.exists():
                continue
            # Delete contents of the folder, not the folder itself
            try:
                for child in p.iterdir():
                    try:
                        freed += dir_size(child) if child.is_dir() else child.stat().st_size
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                    except Exception as e:
                        errors.append(f"{child}: {e}")
            except Exception as e:
                errors.append(f"{p}: {e}")

        return freed, errors

    # ══════════════════════════════════════════════════════════════════════════
    # SEARCH logic
    # ══════════════════════════════════════════════════════════════════════════
    def _toggle_btn(self, parent, text, cmd, active=False):
        return tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 10),
                         bg=ACCENT if active else SURFACE2, fg="white" if active else MUTED,
                         relief="flat", bd=0, pady=6, cursor="hand2")

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
        state = "disabled" if use_all else "normal"
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
        custom = self._custom_var.get().strip()
        if custom and os.path.isdir(custom):
            selected.append(custom)
        return selected if selected else [str(Path.home())]

    def _start_search(self):
        query = self._query_var.get().strip()
        if not query:
            messagebox.showwarning("No keyword", "Please enter at least one keyword.")
            return
        if self._search_thread and self._search_thread.is_alive():
            self._stop_search()
        self._clear_results()
        self._stop_event.clear()
        self._result_count = 0
        roots = self._get_roots()
        self._total_roots = len(roots)
        self._current_root_idx = 0
        self._dirs_scanned = 0
        self._search_start_time = time.time()

        self._status_var.set(f"Searching {len(roots)} location(s)…")
        self._count_var.set("")
        self._pct_var.set("0%")
        self._elapsed_var.set("0s elapsed")
        self._dirs_var.set("")
        self._curpath_var.set("")
        self._search_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._save_btn.config(state="disabled")
        self._progress["value"] = 0

        self._tick_timer()

        self._search_thread = threading.Thread(
            target=run_search,
            args=(roots, query, self._exact_var.get(), self._type_var.get(),
                  DEFAULT_SKIP, self._on_result, self._on_done,
                  self._on_progress, self._stop_event),
            daemon=True)
        self._search_thread.start()

    def _stop_search(self):
        self._stop_event.set()
        self._status_var.set("Stopping…")
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def _on_progress(self, root_idx, total_roots, dirs_in_root, current_path):
        # Called from worker thread — batch update via after()
        self.after(0, self._update_progress, root_idx, total_roots, dirs_in_root, current_path)

    def _update_progress(self, root_idx, total_roots, dirs_in_root, current_path):
        self._current_root_idx = root_idx
        self._dirs_scanned += 1
        pct = int((root_idx / total_roots) * 100) if total_roots > 0 else 0
        self._progress["value"] = pct
        self._pct_var.set(f"{pct}%  (drive {root_idx + 1}/{total_roots})")
        self._dirs_var.set(f"{self._dirs_scanned:,} dirs scanned")
        # Truncate long paths for display
        display_path = current_path if len(current_path) <= 80 else "…" + current_path[-77:]
        self._curpath_var.set(display_path)

    def _tick_timer(self):
        """Updates elapsed time label every second while searching."""
        if not self._stop_event.is_set() and self._search_thread and self._search_thread.is_alive():
            elapsed = time.time() - self._search_start_time
            self._elapsed_var.set(self._fmt_elapsed(elapsed))
            self._timer_id = self.after(1000, self._tick_timer)

    @staticmethod
    def _fmt_elapsed(seconds):
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s elapsed"
        m, s = divmod(seconds, 60)
        if m < 60:
            return f"{m}m {s:02d}s elapsed"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m elapsed"

    def _on_result(self, kind, name, path, size):
        self.after(0, self._add_row, kind, name, path, size)

    def _add_row(self, kind, name, path, size):
        icon = "📁" if kind == "folder" else "📄"
        size_str = fmt_size(size) if size is not None else ""
        iid = self._tree.insert("", "end",
                                 values=(f"{icon} {kind.capitalize()}", name, path, size_str),
                                 tags=(kind,))
        self._result_count += 1
        self._results.append({"type": kind, "name": name, "path": path, "size": size})
        self._count_var.set(f"{self._result_count} found")
        self._tree.see(iid)

    def _on_done(self, total):
        self.after(0, self._finish_search, total)

    def _finish_search(self, total):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        elapsed = time.time() - self._search_start_time
        elapsed_str = self._fmt_elapsed(elapsed).replace(" elapsed", "")

        self._progress["value"] = 100
        self._search_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        if total > 0:
            self._save_btn.config(state="normal")

        msg = "Search stopped" if self._stop_event.is_set() else "Search complete"
        self._status_var.set(f"{msg} — {total} result(s) found")
        self._count_var.set(f"{total} results")
        self._elapsed_var.set(f"took {elapsed_str}")
        self._pct_var.set("100%" if not self._stop_event.is_set() else f"{int((self._current_root_idx / max(self._total_roots,1)) * 100)}%")
        self._curpath_var.set("")

    def _clear_results(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._results = []
        self._result_count = 0
        self._dirs_scanned = 0
        self._count_var.set("")
        self._pct_var.set("")
        self._elapsed_var.set("")
        self._dirs_var.set("")
        self._curpath_var.set("")
        self._progress["value"] = 0
        self._status_var.set("Ready — enter a keyword and press Search")
        self._save_btn.config(state="disabled")
        self._delete_btn.config(state="disabled")

    def _on_tree_select(self, event):
        self._delete_btn.config(state="normal" if self._tree.selection() else "disabled")

    def _open_in_explorer(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        path = self._tree.item(sel[0], "values")[2]
        target = path if os.path.isdir(path) else os.path.dirname(path)
        self._open_path(target)

    def _right_click_menu(self, event):
        sel = self._tree.identify_row(event.y)
        if not sel:
            return
        self._tree.selection_set(sel)
        values = self._tree.item(sel, "values")
        path = values[2]
        menu = tk.Menu(self, tearoff=0, bg=SURFACE2, fg=TEXT,
                       activebackground=ACCENT, activeforeground="white", relief="flat", bd=0)
        menu.add_command(label="Open location", command=lambda: self._open_path(os.path.dirname(path)))
        menu.add_command(label="Copy path",     command=lambda: self._copy_to_clipboard(path))
        menu.add_command(label="Copy name",     command=lambda: self._copy_to_clipboard(values[1]))
        menu.add_separator()
        menu.add_command(label="🗑  Delete this item", command=lambda: self._delete_item(sel, path, values[0]))
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        self._delete_item(sel[0], values[2], values[0])

    def _delete_item(self, iid, path, type_label):
        is_folder = "Folder" in type_label
        kind_word = "folder and ALL its contents" if is_folder else "file"
        if not messagebox.askyesno("Confirm delete",
                                   f"Permanently delete this {kind_word}?\n\n{path}\n\nThis cannot be undone.",
                                   icon="warning", default="no"):
            return
        try:
            shutil.rmtree(path) if is_folder else os.remove(path)
            self._tree.delete(iid)
            self._results = [r for r in self._results if r["path"] != path]
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
        self.clipboard_clear()
        self.clipboard_append(text)

    def _save_results(self):
        if not self._results:
            return
        query = self._query_var.get().strip().replace(" ", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
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

    # ── Styles ────────────────────────────────────────────────────────────────
    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=SURFACE, foreground=TEXT,
                         fieldbackground=SURFACE, rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=SURFACE2, foreground=MUTED,
                         font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        style.configure("TScrollbar", background=SURFACE2, troughcolor=SURFACE)
        style.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE2)
        self._tree.tag_configure("folder", foreground=FOLDER_C)
        self._tree.tag_configure("file",   foreground=FILE_C)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("color")
    app = FileSearchApp()
    app.mainloop()