# File Finder

A desktop utility for Windows, macOS, and Linux that lets you search for files and folders by keyword, delete them directly, clean up system cache, and scan for malware — all from a clean dark-themed GUI.

Built with Python and Tkinter. No external dependencies required to run.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Dependencies](https://img.shields.io/badge/Dependencies-none%20required-brightgreen)

---

## Features

### 🔍 Search Tab
- Search across all drives or choose a specific drive / folder
- **Keyword mode** — partial match (`disc` finds `Discord`, `DiscordSetup.exe`, `old_discord_logs`)
- **Exact mode** — only matches the exact filename or folder name
- Search files, folders, or both
- Live progress bar with percentage, elapsed time, and directory counter
- Double-click a result to open its location in Explorer / Finder
- Right-click menu: open location, copy path, copy name, delete
- Delete files or folders directly from results (with confirmation dialog)
- Save results to a `.txt` report

### Cache Cleaner Tab
- Scan sizes before deleting — see exactly how much each category uses
- Choose exactly which categories to clean:
  - **System** — Temp files, Prefetch, Thumbnails (Windows) / user cache, Trash (macOS/Linux)
  - **Browsers** — Chrome, Edge, Firefox (all profiles), Opera, Brave
  - **Dev tools** — npm, pip, Gradle, Maven, Yarn, pnpm, `__pycache__`, `.mypy_cache`, Cargo
  - **IDEs** — JetBrains (IntelliJ / PyCharm / WebStorm), VS Code workspace cache
- Shows total size to be freed before cleaning
- Select all / Deselect all buttons

### Virus Scanner Tab
- **No API key required** — fully offline scanner
- **No rate limits** — scans as fast as your hardware allows
- Two-phase scanning: finds all files first, then scans with a normal progress bar
- Multi-threaded scanning (configurable in Settings)
- Results split into three tabs: 🔴 Malicious, 🟡 Suspicious, 🟢 Clean (count only)
- Double-click any result for a full detail popup
- Right-click to open location, copy path, or delete the file

**How it detects threats:**

| Method | What it does |
|---|---|
| Hash database | Checks SHA-256 against 1M+ known malware hashes from MalwareBazaar |
| YARA rules | 9 built-in rules covering PowerShell downloaders, keyloggers, ransomware, process injection, shellcode, obfuscated JS/VBS |
| Heuristics | Extension mismatch (PE header in `.txt`), suspicious API imports, script with network + execution combo, suspicious temp folder paths |
| Entropy analysis | Detects packed/encrypted/obfuscated files (score ≥ 7.5 = suspicious) |
| Signature check | Authenticode verification — detects tampered signed files (hash mismatch = +60 score) |

**Deep Scan** — after a normal scan, click "🔬 Deep scan flagged files" to run deeper analysis on suspicious/malicious files only:
- Full-file entropy (entire file, not just first 16KB sample)
- String extraction — URLs, IPs, registry keys, shell commands, file paths
- PE section analysis — names, per-section entropy, packer detection (UPX, Themida, VMProtect...)
- SHA-256 hash lookup for all file types

### Settings Tab
- Configure threads, scan depth, skip lists
- Add custom extensions to skip (e.g. `.crp`, `.pak`, `.unity3d`)
- Add custom folder names to skip (e.g. `Steam`, `Games`)
- Set default tab, window size, search mode
- Save / Reset to defaults

---

## Getting Started

**Requirements:** Python 3.10 or newer. No `pip install` needed for core features.

```bash
# Clone the repo
git clone https://github.com/yourusername/file-finder.git
cd file-finder

# Run
python main.py
```

**Optional — enables YARA rule matching (recommended):**
```bash
pip install yara-python
```

---

## Project Structure

```
file-finder/
├── main.py                      ← entry point
├── config.json                  ← user settings (auto-created)
├── tabs/
│   ├── search_tab.py            ← Search tab
│   ├── cache_tab.py             ← Cache Cleaner tab
│   ├── virus_tab.py             ← Virus Scanner tab
│   └── settings_tab.py         ← Settings tab
├── scanner/
│   ├── engine.py                ← combines all scan methods
│   ├── entropy.py               ← Shannon entropy calculation
│   ├── heuristics.py            ← behavioral/structural analysis
│   ├── hash_db.py               ← local malware hash database
│   ├── yara_engine.py           ← YARA rule matching + 9 bundled rules
│   ├── signature.py             ← Authenticode signature verification
│   ├── deep_scan.py             ← deep analysis engine
│   └── data/                   ← hash database (downloaded separately)
└── utils/
    ├── constants.py             ← colors, skip dirs, extension sets
    ├── drives.py                ← detect drives per OS
    ├── fs_helpers.py            ← dir_size, fmt_size
    ├── search_worker.py         ← background search thread
    ├── cache_targets.py         ← cache locations per OS
    └── config.py                ← config manager
```

---

## How the Virus Scanner Works

The scanner uses a **tiered approach** based on file type:

- **Executables** (`.exe`, `.dll`, `.bat`, `.ps1`...) — full pipeline: hash lookup + YARA + heuristics + entropy + signature
- **Scripts & archives** (`.py`, `.php`, `.zip`...) — heuristics only
- **Unknown extensions** — checks for PE header mismatch (4-byte read only)
- **Data/media/game files** (`.pak`, `.crp`, `.dat`, `.jpg`...) — instant skip

This tiered design means a scan of 50,000 files completes in minutes rather than hours.

**Threat scoring (0–100):**

| Finding | Score |
|---|---|
| Hash in MalwareBazaar DB | 100 (instant) |
| YARA critical rule | +50 |
| YARA high rule | +35 |
| Signature tampered (hash mismatch) | +60 |
| Extension mismatch (PE in .txt) | +40 |
| Suspicious strings | up to +40 |
| Dangerous API imports | up to +30 |
| Entropy ≥ 7.5 (packed) | +30 |
| Script with network + exec combo | +35 |

Verdict: 0–24 = Clean · 25–59 = Suspicious · 60–100 = Malicious

---

## Updating the Hash Database

In the Virus Scanner tab, click **⬇ Update Hash DB** to download the latest ~1 million malware SHA-256 hashes from [MalwareBazaar](https://bazaar.abuse.ch) (free, no account needed). The database is stored locally and never sent anywhere.

---

## License

MIT — free to use, modify, and distribute.