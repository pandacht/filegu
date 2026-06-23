# utils/fs_helpers.py - filesystem utility functions

import os
from pathlib import Path


def dir_size(path: Path) -> int:
    """Recursively calculate total size of a directory in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    total += dir_size(Path(entry.path))
                else:
                    total += entry.stat().st_size
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def fmt_size(b) -> str:
    """Format a byte count as a human-readable string."""
    if b is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.0f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"