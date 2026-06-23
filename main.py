# main.py — File Finder entry point
# Run: python main.py

import os
import sys
import tkinter as tk
from tkinter import ttk

from utils.constants import ACCENT, ACCENT2, BG, SURFACE, SURFACE2, TEXT, MUTED
from utils.drives    import get_drives
from utils           import config as cfg
from tabs.search_tab   import SearchTab
from tabs.cache_tab    import CacheTab
from tabs.virus_tab    import VirusTab
from tabs.settings_tab import SettingsTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        conf = cfg.load()
        w    = conf["ui"]["window_width"]
        h    = conf["ui"]["window_height"]
        self.title("File Finder")
        self.geometry(f"{w}x{h}")
        self.minsize(720, 520)
        self.configure(bg=BG)

        drives          = get_drives()
        self._default_tab = conf["ui"]["default_tab"]

        self._build_header()
        self._build_tabs(drives, conf)
        self._apply_styles()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        header = tk.Frame(self, bg=SURFACE, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="🔍  File Finder",
                 font=("Segoe UI", 18, "bold"), bg=SURFACE, fg=TEXT
                 ).pack(side="left", padx=24)
        tk.Label(header, text="Search · Delete · Clean cache · Scan for threats",
                 font=("Segoe UI", 11), bg=SURFACE, fg=MUTED
                 ).pack(side="left", padx=4)

    # ── Tab bar ───────────────────────────────────────────────────────────────
    def _build_tabs(self, drives, conf):
        tab_bar = tk.Frame(self, bg=SURFACE2)
        tab_bar.pack(fill="x")

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True)

        self._tab_frames: dict[str, tk.Frame] = {}
        self._tab_btns:   dict[str, tk.Button] = {}

        tabs = {
            "Search":        SearchTab(content, drives, self),
            "Cache Cleaner": CacheTab(content, self),
            "Virus Scanner": VirusTab(content, self, drives),
            "Settings":      SettingsTab(content, self),
        }

        for name, widget in tabs.items():
            widget.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._tab_frames[name] = widget

            btn = tk.Button(
                tab_bar, text=name,
                font=("Segoe UI", 11), relief="flat", bd=0,
                padx=20, pady=10, cursor="hand2",
                command=lambda n=name: self._switch_tab(n)
            )
            btn.pack(side="left")
            self._tab_btns[name] = btn

        default = self._default_tab if self._default_tab in self._tab_frames else "Search"
        self._switch_tab(default)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        # Stop any running timers before destroying
        for frame in self._tab_frames.values():
            if hasattr(frame, "_stop_timer"):
                frame._stop_timer()
            if hasattr(frame, "_stop"):
                frame._stop.set()
        self.destroy()

    def _switch_tab(self, name: str):
        for n, frame in self._tab_frames.items():
            frame.lower()
        self._tab_frames[name].lift()
        for n, btn in self._tab_btns.items():
            btn.config(bg=ACCENT if n == name else SURFACE2,
                       fg="white"  if n == name else MUTED)

    # ── Styles ────────────────────────────────────────────────────────────────
    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                         background=SURFACE, foreground=TEXT,
                         fieldbackground=SURFACE, rowheight=28,
                         font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                         background=SURFACE2, foreground=MUTED,
                         font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.configure("TScrollbar",   background=SURFACE2, troughcolor=SURFACE)
        style.configure("TProgressbar", background=ACCENT,   troughcolor=SURFACE2)


if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("color")  # enable ANSI colors in Windows terminal
    app = App()
    app.mainloop()