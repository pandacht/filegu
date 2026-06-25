# utils/constants.py — shared constants across the whole app

# ── UI Colors ─────────────────────────────────────────────────────────────────
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

# ── Folders to skip during file traversal ─────────────────────────────────────
DEFAULT_SKIP = {
    # Windows system — always skip, system files are trusted
    "$Recycle.Bin", "System Volume Information", "Windows",
    "WinSxS",           # Windows component store — thousands of DLLs
    "servicing",        # Windows servicing
    "assembly",         # .NET GAC
    "Microsoft.NET",    # .NET runtime
    # macOS
    ".Spotlight-V100", ".Trashes", ".fseventsd",
    # Linux
    "proc", "sys", "dev",
    # Dev tools / package managers
    "node_modules", "__pycache__", ".git", ".svn", "venv", ".venv",
    "chocolatey", ".p2",
    # Electron apps — all use packed asar/node — always high entropy
    "discord", "Discord",
    "slack", "Slack",
    "VSCode", "Microsoft VS Code",
    "code", "Code",
    "WhatsApp",
    "Telegram Desktop",
    "zoom", "Zoom",
    "Teams",
    "Figma",
    "Postman",
    "Obsidian",
    # Browsers — packed JS, high entropy
    "Google", "Chrome",
    "Microsoft", "Edge",
    "Mozilla", "Firefox",
    "BraveSoftware",
    "Opera",
    # IDEs / dev tools
    "JetBrains",
    "Android", "AndroidStudio",
    "dotnet", ".dotnet",
    "NuGet",
    # Game launchers & stores
    "SteamLibrary", "steamapps",
    "Ubisoft Game Launcher", "Ubisoft Connect",
    "Epic Games", "EpicGames",
    "GOG Galaxy", "GOG.com",
    "EA Games", "EA Desktop", "Origin",
    "Rockstar Games", "Launcher",
    "Battle.net", "Blizzard",
    "Xbox",
    # Anti-cheat
    "BattlEye", "BattlEye Installer",
    "EasyAntiCheat", "EasyAntiCheat_EOS",
    "AntiCheat", "PunkBuster",
    "Vanguard", "GameGuard",
    # Game engines
    "PhyreEngine", "Unreal Engine", "Unity",
}

# ── VirusTotal — file extensions ──────────────────────────────────────────────
# Almost never dangerous; skip to save API quota (except archives)
SAFE_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".flac", ".ogg", ".mkv", ".avi", ".mov",
    ".ttf", ".otf", ".woff", ".woff2",
    ".zip", ".tar", ".gz", ".7z", ".rar",  # archives can hide malware — still checked
}

# High-risk extensions worth scanning first
RISKY_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar",
    ".msi", ".scr", ".pif", ".com", ".lnk", ".reg", ".hta", ".wsf",
}