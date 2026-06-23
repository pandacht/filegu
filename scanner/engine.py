# scanner/engine.py — combines all scan methods into one result
#
# Scan pipeline per file:
#   1. Hash lookup  → only for executables/scripts
#   2. YARA rules   → only for executables/scripts/documents
#   3. Heuristics   → only for non-data files
#   4. Entropy      → only for executables/scripts

from pathlib import Path
from scanner.entropy    import file_entropy, entropy_verdict
from scanner.heuristics import heuristic_scan, DATA_EXTENSIONS
from scanner.hash_db    import lookup_hash, sha256_of_file, db_info
from scanner import yara_engine


MAX_SCAN_SIZE = 50 * 1024 * 1024  # 50 MB

# Only these get the full treatment (hash + YARA + heuristics + entropy)
HIGH_RISK_EXT = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jar", ".msi", ".scr", ".pif", ".com", ".hta", ".wsf",
    ".cpl", ".ocx", ".lnk", ".reg",
}

# These get heuristics + entropy only (no hash, no YARA — too slow for bulk)
MEDIUM_RISK_EXT = {
    ".py", ".rb", ".pl", ".sh", ".php", ".asp", ".aspx",
    ".html", ".htm", ".xml", ".svg",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".iso", ".img",
}

# Cache db_info so we don't hit disk on every file
_db_info_cache = None

def _get_db_info():
    global _db_info_cache
    if _db_info_cache is None:
        _db_info_cache = db_info()
    return _db_info_cache

def invalidate_db_cache():
    global _db_info_cache
    _db_info_cache = None


def scan_file(path: str, skip_media: bool = True) -> dict:
    p    = Path(path)
    name = p.name
    ext  = p.suffix.lower()

    base = {
        "path": path, "name": name, "verdict": "clean",
        "score": 0, "hash": None, "hash_hit": False,
        "entropy": 0.0, "entropy_label": "normal",
        "yara_matches": [], "heuristics": {},
        "summary": [], "size": 0,
    }

    # ── Fast skip: data/media/game files ─────────────────────────────────────
    if ext in DATA_EXTENSIONS:
        base["verdict"] = "skipped"
        base["summary"] = ["Skipped (data/media file)"]
        return base

    # ── File size ─────────────────────────────────────────────────────────────
    try:
        size = p.stat().st_size
        base["size"] = size
    except Exception as e:
        base["verdict"] = "error"
        base["summary"] = [f"Cannot access: {e}"]
        return base

    if size == 0:
        base["verdict"] = "skipped"
        base["summary"] = ["Empty file"]
        return base

    is_high_risk   = ext in HIGH_RISK_EXT
    is_medium_risk = ext in MEDIUM_RISK_EXT

    # ── 1. Hash lookup — executables only ────────────────────────────────────
    if is_high_risk:
        info = _get_db_info()
        if info["exists"] and info["count"] > 0:
            try:
                file_hash    = sha256_of_file(path)
                base["hash"] = file_hash
                if lookup_hash(file_hash):
                    base["hash_hit"] = True
                    base["score"]    = 100
                    base["verdict"]  = "malicious"
                    base["summary"].append("⛔ Hash found in malware database (MalwareBazaar)")
                    return base
            except Exception as e:
                base["summary"].append(f"Hash check failed: {e}")
        elif not info["exists"] or info["count"] == 0:
            base["summary"].append("Hash DB not downloaded — run 'Update Hash DB'")

    # ── 2. YARA — executables + scripts only ─────────────────────────────────
    if is_high_risk and yara_engine.is_available():
        yara_hits = yara_engine.scan_file(path)
        base["yara_matches"] = yara_hits
        if yara_hits:
            severities = {r["severity"] for r in yara_hits}
            yara_score = sum(
                {"critical": 50, "high": 35, "medium": 20, "low": 10}.get(s, 15)
                for s in severities
            )
            base["score"] += yara_score
            for hit in yara_hits:
                base["summary"].append(
                    f"YARA [{hit['severity'].upper()}]: {hit['description']}"
                )

    # ── 3. Heuristics — all non-data files ───────────────────────────────────
    if is_high_risk or is_medium_risk:
        heur = heuristic_scan(path)
        base["heuristics"] = heur
        base["score"]      = min(base["score"] + heur["score"], 100)
        for finding in heur["findings"]:
            base["summary"].append(f"Heuristic: {finding}")

    # ── 4. Entropy — executables + scripts only ───────────────────────────────
    if is_high_risk:
        entropy = file_entropy(path)
        e_label, e_desc = entropy_verdict(entropy)
        base["entropy"]       = entropy
        base["entropy_label"] = e_label
        if e_label in ("packed/encrypted", "suspicious"):
            base["score"] = min(base["score"] + (30 if e_label == "packed/encrypted" else 15), 100)
            base["summary"].append(f"Entropy: {e_desc}")

    # ── Unknown extension — light check only ──────────────────────────────────
    if not is_high_risk and not is_medium_risk:
        # Just check for obvious extension mismatch (PE header in wrong file type)
        try:
            with open(path, "rb") as f:
                header = f.read(4)
            if header[:2] == b"MZ":
                base["score"] += 40
                base["summary"].append(f"PE executable header in file with extension '{ext}'")
        except Exception:
            pass

    # ── Final verdict ─────────────────────────────────────────────────────────
    score = base["score"]
    if score >= 60:
        base["verdict"] = "malicious"
    elif score >= 25:
        base["verdict"] = "suspicious"
    else:
        base["verdict"] = "clean"

    if not base["summary"]:
        base["summary"].append("No threats detected")

    return base