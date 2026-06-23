# utils/cache_targets.py - defines all cache locations per OS

import os
import sys
from pathlib import Path


def build_cache_targets() -> list[tuple]:
    """
    Return a list of (group, label, [Path, ...], description) tuples
    representing known cache locations for the current OS.
    """
    home    = Path.home()
    win     = sys.platform == "win32"
    mac     = sys.platform == "darwin"
    lnx     = sys.platform.startswith("linux")
    local   = Path(os.environ.get("LOCALAPPDATA",  str(home / "AppData/Local")))   if win else None
    roaming = Path(os.environ.get("APPDATA",        str(home / "AppData/Roaming"))) if win else None
    tmp     = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))

    targets = []

    # ── System ────────────────────────────────────────────────────────────────
    if win:
        targets += [
            ("System", "Windows Temp files",  [tmp],
             "Temporary files created by Windows and apps"),
            ("System", "Windows Prefetch",    [Path("C:/Windows/Prefetch")],
             "App launch cache - speeds up startup but can grow large"),
            ("System", "Recent files list",   [home / "AppData/Roaming/Microsoft/Windows/Recent"],
             "Jump list / recently opened files shortcuts"),
            ("System", "Thumbnail cache",     [home / "AppData/Local/Microsoft/Windows/Explorer"],
             "Explorer thumbnail previews"),
        ]
    if mac:
        targets += [
            ("System", "macOS user cache",    [home / "Library/Caches"],
             "App caches stored per-user"),
            ("System", "macOS system logs",   [Path("/private/var/log")],
             "System log files"),
            ("System", "Trash",               [home / ".Trash"],
             "Files in your Trash bin"),
        ]
    if lnx:
        targets += [
            ("System", "Linux user cache",    [home / ".cache"],
             "App caches in ~/.cache"),
            ("System", "Linux temp",          [Path("/tmp")],
             "Global temp files"),
            ("System", "Journald logs",       [Path("/var/log/journal")],
             "Systemd journal logs"),
        ]

    # ── Browsers ──────────────────────────────────────────────────────────────
    if win:
        chrome_cache = local  / "Google/Chrome/User Data/Default/Cache"
        chrome_code  = local  / "Google/Chrome/User Data/Default/Code Cache"
        edge_cache   = local  / "Microsoft/Edge/User Data/Default/Cache"
        firefox_base = roaming / "Mozilla/Firefox/Profiles"
        opera_cache  = roaming / "Opera Software/Opera Stable/Cache"
        brave_cache  = local  / "BraveSoftware/Brave-Browser/User Data/Default/Cache"
    elif mac:
        chrome_cache = home / "Library/Caches/Google/Chrome/Default/Cache"
        chrome_code  = home / "Library/Caches/Google/Chrome/Default/Code Cache"
        edge_cache   = home / "Library/Caches/Microsoft Edge/Default/Cache"
        firefox_base = home / "Library/Application Support/Firefox/Profiles"
        opera_cache  = home / "Library/Caches/com.operasoftware.Opera"
        brave_cache  = home / "Library/Caches/BraveSoftware/Brave-Browser/Default/Cache"
    else:
        chrome_cache = home / ".cache/google-chrome/Default/Cache"
        chrome_code  = home / ".cache/google-chrome/Default/Code Cache"
        edge_cache   = home / ".cache/microsoft-edge/Default/Cache"
        firefox_base = home / ".mozilla/firefox"
        opera_cache  = home / ".cache/opera"
        brave_cache  = home / ".cache/BraveSoftware/Brave-Browser/Default/Cache"

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
        ("Browsers", "Chrome cache",   [chrome_cache, chrome_code],
         "HTTP cache + JS code cache for Google Chrome"),
        ("Browsers", "Edge cache",     [edge_cache],
         "HTTP cache for Microsoft Edge"),
        ("Browsers", "Firefox cache",  firefox_caches,
         "HTTP cache for all Firefox profiles"),
        ("Browsers", "Opera cache",    [opera_cache],
         "HTTP cache for Opera"),
        ("Browsers", "Brave cache",    [brave_cache],
         "HTTP cache for Brave Browser"),
    ]

    # ── Dev tools ─────────────────────────────────────────────────────────────
    targets += [
        ("Dev", "npm cache",        [home / ".npm/_cacache"],
         "npm package cache (~/.npm)"),
        ("Dev", "pip cache",        [home / ".cache/pip"],
         "pip wheel/package cache"),
        ("Dev", "Gradle cache",     [home / ".gradle/caches"],
         "Gradle build cache"),
        ("Dev", "Maven cache",      [home / ".m2/repository"],
         "Maven local repository (~/.m2)"),
        ("Dev", "Yarn cache",       [home / ".yarn/cache"],
         "Yarn package cache"),
        ("Dev", "pnpm cache",       [home / ".pnpm-store"],
         "pnpm content-addressable store"),
        ("Dev", "__pycache__",      [],
         "Python bytecode cache dirs (scanned from home)"),
        ("Dev", ".mypy_cache",      [],
         "mypy type-check cache dirs"),
        ("Dev", "Rust cargo cache", [home / ".cargo/registry/cache"],
         "Cargo downloaded crate cache"),
    ]

    # ── IDEs ──────────────────────────────────────────────────────────────────
    if win:
        idea_system  = local   / "JetBrains"
        vscode_cache = roaming / "Code/User/workspaceStorage"
    elif mac:
        idea_system  = home / "Library/Caches/JetBrains"
        vscode_cache = home / "Library/Application Support/Code/User/workspaceStorage"
    else:
        idea_system  = home / ".cache/JetBrains"
        vscode_cache = home / ".config/Code/User/workspaceStorage"

    targets += [
        ("IDEs", "JetBrains system cache",  [idea_system],
         "IntelliJ / PyCharm / WebStorm etc. caches"),
        ("IDEs", "VS Code workspace cache", [vscode_cache],
         "Per-workspace extension data & cache"),
    ]

    return targets