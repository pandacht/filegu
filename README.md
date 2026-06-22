# File Finder

A desktop utility for Windows, macOS, and Linux that lets you search for files and folders by keyword, delete them directly from the results, and clean up cache files — all from a clean dark-themed GUI.

Built with Python and Tkinter. No external dependencies required.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Dependencies](https://img.shields.io/badge/Dependencies-none-brightgreen)

---

## Features

### Search Tab
- Search across all drives or choose a specific drive / folder
- **Keyword mode** — partial match (`disc` finds `Discord`, `DiscordSetup.exe`, `old_discord_logs`)
- **Exact mode** — only matches the exact filename or folder name
- Search files, folders, or both
- Live progress bar with percentage, elapsed time, and directory counter
- Double-click a result to open its location in Explorer / Finder
- Right-click menu: open location, copy path, copy name, delete
- Delete files or folders directly from the results (with confirmation)
- Save results to a `.txt` report

### Cache Cleaner Tab
- One-click scan to see cache sizes before deleting anything
- Choose exactly which categories to clean:
  - **System** — Temp files, Prefetch, Thumbnails (Windows) / user cache, Trash (macOS/Linux)
  - **Browsers** — Chrome, Edge, Firefox, Opera, Brave
  - **Dev tools** — npm, pip, Gradle, Maven, Yarn, pnpm, `__pycache__`, `.mypy_cache`, Cargo
  - **IDEs** — JetBrains (IntelliJ / PyCharm / WebStorm), VS Code workspace cache
- Shows size per category (highlights large caches in yellow)
- Displays total freed space after cleaning

---

## Getting Started

**Requirements:** Python 3.10 or newer. No `pip install` needed — uses only the standard library.

```bash
# Clone the repo
git clone https://github.com/pandacht/file-finder.git
cd file-finder

# Run
python filesearch_gui.py
```

---

## Usage

### Searching
1. Type one or more keywords in the search box (e.g. `discord` or `discord setup`)
2. Choose **Keyword** or **Exact** match mode
3. Select what to search: files & folders, files only, or folders only
4. Choose where to search: all drives, a specific drive, or browse to a folder
5. Press **Search** or hit Enter

### Deleting search results
- Click a result row to select it, then press **🗑 Delete selected**
- Or right-click any row → **Delete this item**
- A confirmation dialog always appears before anything is deleted

### Cleaning cache
1. Switch to the **Cache Cleaner** tab
2. Check the categories you want to clean (or press **Select all**)
3. Press **Scan sizes** to see how much each category uses
4. Press **Clean selected** → confirm → done

---

## Project Structure

```
file-finder/
├── filesearch_gui.py   # Main application — UI, search logic, cache cleaner
└── README.md
```

---

## How It Works

- File traversal uses `os.walk` with a background thread so the UI never freezes
- Progress is estimated using a logarithmic curve per drive (since total directory count is unknown upfront)
- Cache paths are auto-detected per OS at startup
- All deletions use `os.remove` (files) and `shutil.rmtree` (folders) with full error handling

---

## License

MIT — free to use, modify, and distribute.
