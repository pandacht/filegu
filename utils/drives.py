# utils/drives.py - detect available drives / mount points on all platforms

import os
import sys
from pathlib import Path


def get_drives() -> list[str]:
    """Return a list of root paths to search (drive letters on Windows, mount points elsewhere)."""
    drives = []

    if sys.platform == "win32":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:
        drives.append("/")
        home = str(Path.home())
        if home != "/":
            drives.append(home)
        for vol in ["/Volumes", "/mnt", "/media"]:
            if os.path.isdir(vol):
                try:
                    for sub in os.listdir(vol):
                        full = os.path.join(vol, sub)
                        if os.path.isdir(full):
                            drives.append(full)
                except PermissionError:
                    pass

    return drives