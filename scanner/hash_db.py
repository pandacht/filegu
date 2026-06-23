# scanner/hash_db.py - local malware hash database
#
# Uses free hash lists from MalwareBazaar (abuse.ch).
# Hashes are stored in a simple text file - one SHA-256 per line.
# The database can be updated at any time by downloading a fresh list.

import hashlib
import os
import urllib.request
import zipfile
import io
from pathlib import Path
from datetime import datetime

# Where the hash database lives (relative to this file's directory)
DB_DIR  = Path(__file__).parent / "data"
DB_FILE = DB_DIR / "malware_hashes.txt"
META_FILE = DB_DIR / "db_meta.txt"

# MalwareBazaar full SHA-256 export (free, updated daily)
MALWAREBAZAAR_URL = "https://bazaar.abuse.ch/export/txt/sha256/full/"


def db_info() -> dict:
    """Return info about the current database."""
    if not DB_FILE.exists():
        return {"exists": False, "count": 0, "updated": None}
    count = 0
    try:
        with open(DB_FILE, "r") as f:
            count = sum(1 for line in f if line.strip() and not line.startswith("#"))
    except Exception:
        pass
    updated = None
    if META_FILE.exists():
        try:
            updated = META_FILE.read_text().strip()
        except Exception:
            pass
    return {"exists": True, "count": count, "updated": updated}


def lookup_hash(file_hash: str) -> bool:
    """
    Returns True if the SHA-256 hash is in the local database.
    Very fast - uses a set loaded into memory on first call.
    """
    db = _load_db()
    return file_hash.lower() in db


# Module-level cache so we only read the file once per session
_db_cache: set | None = None


def _load_db() -> set:
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    _db_cache = set()
    if not DB_FILE.exists():
        return _db_cache
    try:
        with open(DB_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    _db_cache.add(line.lower())
    except Exception:
        pass
    return _db_cache


def invalidate_cache():
    """Call after updating the database so next lookup reloads it."""
    global _db_cache
    _db_cache = None


def sha256_of_file(path: str, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def update_database(progress_cb=None) -> tuple[bool, str]:
    """
    Download fresh hash list from MalwareBazaar and save to DB_FILE.
    progress_cb(message: str) is called with status updates if provided.
    Returns (success: bool, message: str).
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)

    def report(msg):
        if progress_cb:
            progress_cb(msg)

    try:
        report("Connecting to MalwareBazaar…")
        req = urllib.request.Request(
            MALWAREBAZAAR_URL,
            headers={"User-Agent": "FileFinder/1.0 (local malware hash db)"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            report("Downloading hash list (this may take a moment)…")
            raw = resp.read()

        report("Extracting…")
        # MalwareBazaar returns a zip containing a .txt file
        count = 0
        lines = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for name in zf.namelist():
                    if name.endswith(".txt"):
                        with zf.open(name) as tf:
                            for line in tf:
                                line = line.decode("utf-8", errors="replace").strip()
                                if line and not line.startswith("#"):
                                    lines.append(line)
                                    count += 1
        except zipfile.BadZipFile:
            # Maybe it's a plain text file
            text = raw.decode("utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    lines.append(line)
                    count += 1

        if count == 0:
            return False, "Download succeeded but no hashes were found in the response."

        report(f"Writing {count:,} hashes to database…")
        with open(DB_FILE, "w") as f:
            f.write(f"# MalwareBazaar SHA-256 hash list\n")
            f.write(f"# Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Count: {count}\n")
            for line in lines:
                f.write(line + "\n")

        # Save metadata
        META_FILE.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        invalidate_cache()
        report(f"Done - {count:,} hashes saved.")
        return True, f"Database updated: {count:,} malware hashes."

    except urllib.error.URLError as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, f"Error: {e}"