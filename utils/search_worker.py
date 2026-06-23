# utils/search_worker.py - file search worker (runs in a background thread)

import os
from pathlib import Path


def run_search(roots, query, exact, search_type, skip_dirs,
               callback, done_cb, progress_cb, stop_event):
    """
    Recursively search roots for files/folders matching query.

    Args:
        roots:        list of root paths to search
        query:        space-separated keywords string
        exact:        if True, match exact filename/stem; else partial match
        search_type:  "both" | "files" | "folders"
        skip_dirs:    set of directory names to skip
        callback:     fn(kind, name, path, size) called for each match
        done_cb:      fn(total_count) called when search finishes
        progress_cb:  fn(root_idx, total_roots, dirs_in_root, current_path)
        stop_event:   threading.Event - set to cancel
    """
    keywords = [q.strip() for q in query.strip().split() if q.strip()]
    if not keywords:
        done_cb(0)
        return

    count = 0
    total_roots = len(roots)

    def matches(name: str) -> bool:
        name_l = name.lower()
        if exact:
            stem = Path(name).stem.lower()
            return any(kw.lower() == stem or kw.lower() == name_l for kw in keywords)
        return any(kw.lower() in name_l for kw in keywords)

    for root_idx, root in enumerate(roots):
        if stop_event.is_set():
            break
        dirs_in_root = 0
        try:
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                if stop_event.is_set():
                    break

                # Prune skipped and hidden directories in-place
                dirnames[:] = [
                    d for d in dirnames
                    if d not in skip_dirs and not d.startswith(".")
                ]
                dirs_in_root += 1
                current = Path(dirpath)

                progress_cb(root_idx, total_roots, dirs_in_root, str(current))

                if search_type in ("both", "folders"):
                    if matches(current.name) and str(current) != root:
                        try:
                            callback("folder", current.name, str(current), None)
                            count += 1
                        except Exception:
                            pass

                if search_type in ("both", "files"):
                    for fname in filenames:
                        if stop_event.is_set():
                            break
                        if matches(fname):
                            fpath = current / fname
                            try:
                                size = fpath.stat().st_size
                            except Exception:
                                size = None
                            callback("file", fname, str(fpath), size)
                            count += 1

        except (PermissionError, Exception):
            pass

    done_cb(count)