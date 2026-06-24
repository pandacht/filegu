# 🔍 Filegu

A desktop utility for Windows, macOS, and Linux — search files, clean cache, scan for malware. Dark-themed GUI built with Python and Tkinter. No external dependencies required to run.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Dependencies](https://img.shields.io/badge/Dependencies-none%20required-brightgreen)
![Languages](https://img.shields.io/badge/Languages-EN%20%7C%20RU%20%7C%20DE-orange)

---

## Features

### Search Tab
- Search across all drives or a specific folder
- **Keyword mode** — partial match (`disc` finds `Discord`, `DiscordSetup.exe`)
- **Exact mode** — only matches the exact filename
- Search files, folders, or both
- Live progress with drive counter, elapsed time, and current path
- Double-click to open file location in Explorer / Finder
- Right-click menu: open location, copy path, copy name, delete
- Delete files or folders directly from results (with confirmation)
- Save results to `.txt` report
- Reads default mode/type/drives from Settings

### Cache Cleaner Tab
- Scan sizes before deleting — see exactly how much each category takes
- Select/deselect entire categories with one click
- **System** — Temp files, Prefetch, Error Reporting, Windows Update cache, Delivery Optimization, DirectX Shader cache, Thumbnails, Font cache, Event logs, Defender history
- **Browsers** — Chrome, Chrome GPU, Edge, Edge WebView2, Firefox, Opera, Brave
- **Dev** — npm, pip, Gradle, Gradle wrapper, Maven, Yarn, pnpm, `__pycache__`, `.mypy_cache`, Cargo, Docker, Android AVD, NuGet, Composer, dotnet, Next.js, Parcel, Webpack/Vite
- **IDEs** — JetBrains, VS Code workspace, VS Code extensions
- **Apps** — Spotify, Discord, Teams, Zoom, Slack, Telegram, WhatsApp
- **Games** — Steam shader cache, Epic Games, GOG Galaxy, Riot Games

### Virus Scanner Tab
- **No API key required** — fully offline scanner
- **Parallel scanning** — configurable thread count
- **Two-phase progress**: bouncing bar while finding files → normal fill bar while scanning
- Results split into tabs: 🔴 Malicious · 🟡 Suspicious · 🟢 Clean (counter only) · 🌐 Online
- Double-click any result for full detail popup
- Right-click to open location, copy path, or delete

**Detection methods:**

| Method | What it does |
|---|---|
| Hash database | SHA-256 against 1M+ known malware hashes from MalwareBazaar |
| YARA rules | 9 built-in rules: PowerShell downloaders, keyloggers, ransomware, process injection, shellcode, obfuscated JS/VBS |
| Heuristics | Extension mismatch, suspicious API imports, network+exec combo, suspicious temp folder paths |
| Entropy analysis | Detects packed/encrypted/obfuscated files |
| Signature check | Authenticode verification — detects tampered signed files |

**Tiered scanning for speed:**

| File type | What runs |
|---|---|
| `.exe`, `.dll`, `.bat`, `.ps1`… | Hash + YARA + heuristics + entropy + signature |
| `.py`, `.php`, `.zip`, `.html`… | Heuristics only |
| Unknown extension | PE header check (4 bytes) |
| `.pak`, `.crp`, media, game assets | Instant skip |

**Deep Scan** — after a normal scan, re-scan flagged files with:
- Full-file entropy (entire file)
- String extraction — URLs, IPs, registry keys, shell commands
- PE section analysis — names, per-section entropy, packer detection
- SHA-256 hash lookup for all types

**Online Verification (VirusTotal)** — verify flagged files against 70+ antivirus engines using your free VirusTotal API key. Double-click any result to open the full VT report in browser. Free tier: 4 requests/minute.

### Settings Tab
- **Virus Scanner** — threads, scan depth, skip media, executables only, VirusTotal API key, extra extensions/folders to skip
- **Search** — default match mode, default search type
- **Interface** — default tab on startup, language
- Save / Reset to defaults

---

## Languages

Filegu supports multiple languages. Change in **Settings → Language**, restart to apply.

| Language | Status |
|---|---|
| English | ✅ Complete |
| Русский | ✅ Complete |
| Deutsch | ✅ Complete |

---

## Getting Started

**Requirements:** Python 3.10+. No `pip install` needed for core features.

```bash
git clone https://github.com/yourusername/filegu.git
cd filegu
python main.py
```

**Optional — enables YARA rule matching (recommended):**
```bash
pip install yara-python
```

---

## Project Structure

```
filegu/
├── main.py                      ← entry point, App class
├── config.json                  ← user settings (auto-created)
├── tabs/
│   ├── search_tab.py            ← Search tab
│   ├── cache_tab.py             ← Cache Cleaner tab
│   ├── virus_tab.py             ← Virus Scanner tab
│   └── settings_tab.py         ← Settings tab
├── scanner/
│   ├── engine.py                ← tiered scan pipeline
│   ├── entropy.py               ← Shannon entropy
│   ├── heuristics.py            ← behavioral/structural analysis
│   ├── hash_db.py               ← local malware hash database
│   ├── yara_engine.py           ← YARA + 9 bundled rules
│   ├── signature.py             ← Authenticode verification
│   └── deep_scan.py             ← deep analysis engine
└── utils/
    ├── constants.py             ← colors, DEFAULT_SKIP
    ├── drives.py                ← detect drives per OS
    ├── fs_helpers.py            ← dir_size, fmt_size
    ├── search_worker.py         ← background search thread
    ├── cache_targets.py         ← 50+ cache locations per OS
    ├── config.py                ← config manager (load/save)
    ├── lang.py                  ← i18n system, t() function
    └── virustotal.py            ← VirusTotal API helpers
```

---

## Threat Scoring (0–100)

| Finding | Score |
|---|---|
| Hash in MalwareBazaar DB | 100 (instant) |
| Signature tampered (hash mismatch) | +60 |
| YARA critical rule | +50 |
| Extension mismatch (PE in .txt) | +40 |
| YARA high rule | +35 |
| Script with network + exec combo | +35 |
| Signature not trusted | +30 |
| Entropy ≥ 7.95 (packed) | +30 |
| Suspicious strings | up to +40 |
| Dangerous API imports | up to +30 |

**Verdict:** 0–24 = Clean · 25–59 = Suspicious · 60–100 = Malicious

---

## Adding a Language

Open `utils/lang.py` and add a new block to `STRINGS`:

```python
"fr": {
    "app.subtitle": "Recherche · Suppression · Nettoyage · Analyse",
    "tab.search":   "Recherche",
    # ... translate all keys from the "en" block
}
```

Then add the display name to `available_languages()`. No other changes needed.

---

## Updating the Hash Database

In the Virus Scanner tab, click **Update Hash DB** to download ~1 million malware SHA-256 hashes from [MalwareBazaar](https://bazaar.abuse.ch) (free, no account needed). Stored locally, never sent anywhere.

---

## License

MIT — free to use, modify, and distribute.