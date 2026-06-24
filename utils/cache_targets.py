# utils/cache_targets.py — defines all cache locations per OS

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
            ("System", "cache.item.win_temp",        [tmp],
             "cache.desc.win_temp"),
            ("System", "cache.item.win_prefetch",          [Path("C:/Windows/Prefetch")],
             "cache.desc.win_prefetch"),
            ("System", "cache.item.win_wer",   [Path("C:/ProgramData/Microsoft/Windows/WER"),
                                                     home / "AppData/Local/Microsoft/Windows/WER"],
             "cache.desc.win_wer"),
            ("System", "cache.item.win_update",      [Path("C:/Windows/SoftwareDistribution/Download")],
             "cache.desc.win_update"),
            ("System", "cache.item.win_delivery",     [Path("C:/Windows/ServiceProfiles/NetworkService/AppData/Local/Microsoft/Windows/DeliveryOptimization")],
             "cache.desc.win_delivery"),
            ("System", "cache.item.win_dx",      [local / "D3DSCache"],
             "cache.desc.win_dx"),
            ("System", "cache.item.win_recent",         [home / "AppData/Roaming/Microsoft/Windows/Recent"],
             "cache.desc.win_recent"),
            ("System", "cache.item.win_thumb",           [home / "AppData/Local/Microsoft/Windows/Explorer"],
             "cache.desc.win_thumb"),
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
        chrome_cache  = local  / "Google/Chrome/User Data/Default/Cache"
        chrome_code   = local  / "Google/Chrome/User Data/Default/Code Cache"
        chrome_gpu    = local  / "Google/Chrome/User Data/Default/GPUCache"
        edge_cache    = local  / "Microsoft/Edge/User Data/Default/Cache"
        edge_webview  = local  / "Microsoft/EdgeWebView/Application"
        firefox_base  = roaming / "Mozilla/Firefox/Profiles"
        opera_cache   = roaming / "Opera Software/Opera Stable/Cache"
        brave_cache   = local  / "BraveSoftware/Brave-Browser/User Data/Default/Cache"
    elif mac:
        chrome_cache  = home / "Library/Caches/Google/Chrome/Default/Cache"
        chrome_code   = home / "Library/Caches/Google/Chrome/Default/Code Cache"
        chrome_gpu    = home / "Library/Caches/Google/Chrome/Default/GPUCache"
        edge_cache    = home / "Library/Caches/Microsoft Edge/Default/Cache"
        edge_webview  = home / "Library/Caches/Microsoft/EdgeWebView"
        firefox_base  = home / "Library/Application Support/Firefox/Profiles"
        opera_cache   = home / "Library/Caches/com.operasoftware.Opera"
        brave_cache   = home / "Library/Caches/BraveSoftware/Brave-Browser/Default/Cache"
    else:
        chrome_cache  = home / ".cache/google-chrome/Default/Cache"
        chrome_code   = home / ".cache/google-chrome/Default/Code Cache"
        chrome_gpu    = home / ".cache/google-chrome/Default/GPUCache"
        edge_cache    = home / ".cache/microsoft-edge/Default/Cache"
        edge_webview  = home / ".cache/microsoft-edge-webview"
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
        ("Browsers", "cache.item.chrome",       [chrome_cache, chrome_code],
         "cache.desc.chrome"),
        ("Browsers", "cache.item.chrome_gpu",   [chrome_gpu],
         "cache.desc.chrome_gpu"),
        ("Browsers", "cache.item.edge",         [edge_cache],
         "cache.desc.edge"),
        ("Browsers", "cache.item.edge_webview",      [edge_webview],
         "cache.desc.edge_webview"),
        ("Browsers", "cache.item.firefox",      firefox_caches,
         "cache.desc.firefox"),
        ("Browsers", "cache.item.opera",        [opera_cache],
         "cache.desc.opera"),
        ("Browsers", "cache.item.brave",        [brave_cache],
         "cache.desc.brave"),
    ]

    # ── Dev tools ─────────────────────────────────────────────────────────────
    targets += [
        ("Dev", "cache.item.npm",            [home / ".npm/_cacache"],
         "cache.desc.npm"),
        ("Dev", "cache.item.pip",            [home / ".cache/pip"],
         "cache.desc.pip"),
        ("Dev", "cache.item.gradle",         [home / ".gradle/caches"],
         "cache.desc.gradle"),
        ("Dev", "cache.item.gradle_wrapper",       [home / ".gradle/wrapper/dists"],
         "cache.desc.gradle_wrapper"),
        ("Dev", "cache.item.maven",          [home / ".m2/repository"],
         "cache.desc.maven"),
        ("Dev", "cache.item.yarn",           [home / ".yarn/cache"],
         "cache.desc.yarn"),
        ("Dev", "cache.item.pnpm",           [home / ".pnpm-store"],
         "cache.desc.pnpm"),
        ("Dev", "cache.item.pycache",          [],
         "cache.desc.pycache"),
        ("Dev", "cache.item.mypy",          [],
         "cache.desc.mypy"),
        ("Dev", "cache.item.cargo",     [home / ".cargo/registry/cache"],
         "cache.desc.cargo"),
        ("Dev", "cache.item.docker",        [Path("C:/ProgramData/Docker/windowsfilter") if win
                                         else Path("/var/lib/docker/overlay2")],
         "cache.desc.docker"),
        ("Dev", "cache.item.android",    [home / ".android/avd"],
         "cache.desc.android"),
    ]

    # ── IDEs ──────────────────────────────────────────────────────────────────
    if win:
        idea_system   = local   / "JetBrains"
        vscode_ws     = roaming / "Code/User/workspaceStorage"
        vscode_cache  = local   / "Programs/Microsoft VS Code/resources/app/extensions"
    elif mac:
        idea_system   = home / "Library/Caches/JetBrains"
        vscode_ws     = home / "Library/Application Support/Code/User/workspaceStorage"
        vscode_cache  = home / "Library/Application Support/Code/CachedExtensionVSIXs"
    else:
        idea_system   = home / ".cache/JetBrains"
        vscode_ws     = home / ".config/Code/User/workspaceStorage"
        vscode_cache  = home / ".config/Code/CachedExtensionVSIXs"

    targets += [
        ("IDEs", "cache.item.jetbrains",   [idea_system],
         "cache.desc.jetbrains"),
        ("IDEs", "cache.item.vscode_ws",  [vscode_ws],
         "cache.desc.vscode_ws"),
        ("IDEs", "cache.item.vscode_ext",  [vscode_cache],
         "cache.desc.vscode_ext"),
    ]

    # ── Dev (extra) ───────────────────────────────────────────────────────────
    nuget = (local / "NuGet/Cache") if win else (home / ".nuget/packages")
    targets += [
        ("Dev", "cache.item.nuget",          [nuget],
         "cache.desc.nuget"),
        ("Dev", "cache.item.composer",       [roaming / "Composer/cache"] if win else home / ".composer/cache",
         "cache.desc.composer"),
        ("Dev", "cache.item.dotnet",          [home / ".dotnet"],
         "cache.desc.dotnet"),
        ("Dev", "cache.item.nextjs",        [],
         "cache.desc.nextjs"),
        ("Dev", "cache.item.parcel",         [],
         "cache.desc.parcel"),
        ("Dev", "cache.item.webpack",   [],
         "cache.desc.webpack"),
    ]

    # ── Apps ──────────────────────────────────────────────────────────────────
    if win:
        spotify_cache  = local   / "Spotify/Storage"
        discord_cache  = roaming / "discord/Cache"
        teams_cache    = roaming / "Microsoft/Teams/Cache"
        teams_blobs    = roaming / "Microsoft/Teams/blob_storage"
        zoom_cache     = roaming / "Zoom/data"
        slack_cache    = roaming / "Slack/Cache"
        slack_storage  = roaming / "Slack/storage"
        telegram_cache = roaming / "Telegram Desktop/tdata/user_data"
        whatsapp_cache = local   / "WhatsApp/Cache"
    elif mac:
        spotify_cache  = home / "Library/Caches/com.spotify.client"
        discord_cache  = home / "Library/Caches/discord"
        teams_cache    = home / "Library/Application Support/Microsoft/Teams/Cache"
        teams_blobs    = home / "Library/Application Support/Microsoft/Teams/blob_storage"
        zoom_cache     = home / "Library/Application Support/zoom.us/data"
        slack_cache    = home / "Library/Application Support/Slack/Cache"
        slack_storage  = home / "Library/Application Support/Slack/storage"
        telegram_cache = home / "Library/Application Support/Telegram Desktop/tdata"
        whatsapp_cache = home / "Library/Caches/WhatsApp"
    else:
        spotify_cache  = home / ".cache/spotify"
        discord_cache  = home / ".config/discord/Cache"
        teams_cache    = home / ".config/Microsoft/Microsoft Teams/Cache"
        teams_blobs    = home / ".config/Microsoft/Microsoft Teams/blob_storage"
        zoom_cache     = home / ".zoom/data"
        slack_cache    = home / ".config/Slack/Cache"
        slack_storage  = home / ".config/Slack/storage"
        telegram_cache = home / ".local/share/TelegramDesktop/tdata"
        whatsapp_cache = home / ".cache/whatsapp"

    targets += [
        ("Apps", "cache.item.spotify",       [spotify_cache],
         "cache.desc.spotify"),
        ("Apps", "cache.item.discord",       [discord_cache],
         "cache.desc.discord"),
        ("Apps", "cache.item.teams",         [teams_cache, teams_blobs],
         "cache.desc.teams"),
        ("Apps", "cache.item.zoom",          [zoom_cache],
         "cache.desc.zoom"),
        ("Apps", "cache.item.slack",         [slack_cache, slack_storage],
         "cache.desc.slack"),
        ("Apps", "cache.item.telegram",      [telegram_cache],
         "cache.desc.telegram"),
        ("Apps", "cache.item.whatsapp",      [whatsapp_cache],
         "cache.desc.whatsapp"),
    ]

    # ── Games ──────────────────────────────────────────────────────────────────
    if win:
        steam_shader  = Path("C:/Program Files (x86)/Steam/steamapps/shadercache")
        epic_cache    = Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/webcache")
        gog_cache     = Path("C:/ProgramData/GOG.com/Galaxy/webcache")
        riot_cache    = Path("C:/ProgramData/Riot Games/RiotClientServices/Data/Cache")
    elif mac:
        steam_shader  = home / "Library/Application Support/Steam/steamapps/shadercache"
        epic_cache    = home / "Library/Application Support/Epic/EpicGamesLauncher/webcache"
        gog_cache     = home / "Library/Application Support/GOG.com/Galaxy/webcache"
        riot_cache    = home / "Library/Application Support/Riot Games/cache"
    else:
        steam_shader  = home / ".steam/steam/steamapps/shadercache"
        epic_cache    = home / ".config/Epic/EpicGamesLauncher/webcache"
        gog_cache     = home / ".config/GOG.com/Galaxy/webcache"
        riot_cache    = home / ".config/Riot Games/cache"

    targets += [
        ("Games", "cache.item.steam_shader",  [steam_shader],
         "cache.desc.steam_shader"),
        ("Games", "cache.item.epic",    [epic_cache],
         "cache.desc.epic"),
        ("Games", "cache.item.gog",    [gog_cache],
         "cache.desc.gog"),
        ("Games", "cache.item.riot",    [riot_cache],
         "cache.desc.riot"),
    ]

    # ── Windows system (extra) ────────────────────────────────────────────────
    if win:
        targets += [
            ("System", "cache.item.win_fonts",    [Path("C:/Windows/ServiceProfiles/LocalService/AppData/Local/FontCache")],
             "cache.desc.win_fonts"),
            ("System", "cache.item.win_events",    [Path("C:/Windows/System32/winevt/Logs")],
             "cache.desc.win_events"),
            ("System", "cache.item.win_defender", [Path("C:/ProgramData/Microsoft/Windows Defender/Scans/History")],
             "cache.desc.win_defender"),
            ("System", "cache.item.win_iis",              [Path("C:/inetpub/logs")],
             "cache.desc.win_iis"),
        ]

    return targets