# utils/config.py — persistent configuration manager
#
# Reads and writes config.json in the project root.
# All settings have sensible defaults so the app works even without a config file.

import json
import os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULTS = {
    "scanner": {
        "threads":         8,
        "depth":           "full",
        "skip_media":      True,
        "exe_only":        False,
        "extra_skip_ext":  [],
        "extra_skip_dirs": [],
        "virustotal_key":  "",
    },
    "search": {
        "default_mode":    "keyword",    # "keyword" | "exact"
        "default_type":    "both",       # "both" | "files" | "folders"
        "all_drives":      True,
    },
    "ui": {
        "default_tab":     "Search",
        "window_width":    1280,
        "window_height":   820,
        "language":        "en",
    }
}


def load() -> dict:
    """Load config from disk, filling in any missing keys with defaults."""
    config = _deep_copy(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            _deep_merge(config, saved)
        except Exception:
            pass  # corrupt file — use defaults
    return config


def save(config: dict) -> bool:
    """Save config to disk. Returns True on success."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


def get(key_path: str, fallback=None):
    """
    Get a single value by dot-path, e.g. get("scanner.threads") → 8
    Falls back to default or fallback if not found.
    """
    config = load()
    keys   = key_path.split(".")
    node   = config
    for k in keys:
        if isinstance(node, dict) and k in node:
            node = node[k]
        else:
            # Try defaults
            node = DEFAULTS
            for dk in keys:
                if isinstance(node, dict) and dk in node:
                    node = node[dk]
                else:
                    return fallback
            return node
    return node


def set_value(key_path: str, value) -> bool:
    """
    Set a single value by dot-path and save immediately.
    e.g. set_value("scanner.threads", 4)
    """
    config = load()
    keys   = key_path.split(".")
    node   = config
    for k in keys[:-1]:
        if k not in node:
            node[k] = {}
        node = node[k]
    node[keys[-1]] = value
    return save(config)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _deep_copy(d: dict) -> dict:
    """Simple deep copy of a dict (handles nested dicts and lists)."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def _deep_merge(base: dict, override: dict):
    """Merge override into base in-place, preserving base keys not in override."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v