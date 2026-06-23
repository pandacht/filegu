# scanner/heuristics.py — heuristic checks (no external libraries needed)
#
# Looks for suspicious patterns in file content, name, and location.
# These are the same kinds of checks real AV engines use as a first pass.

import os
import re
import struct
from pathlib import Path


# ── Suspicious locations ──────────────────────────────────────────────────────
SUSPICIOUS_DIRS = {
    "temp", "tmp", "%temp%", "appdata\\local\\temp",
    "downloads", "recycle", "$recycle.bin",
}

EXECUTABLE_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jar", ".msi", ".scr", ".pif", ".com", ".lnk", ".reg",
    ".hta", ".wsf", ".cpl", ".ocx",
}

# Extensions that are pure data — skip heuristic checks entirely
DATA_EXTENSIONS = {
    ".pak", ".dat", ".db", ".sqlite", ".sqlite3", ".bin",
    ".cache", ".blob", ".nib", ".lzma", ".xz",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico",
    ".mp3", ".mp4", ".wav", ".flac", ".ogg", ".mkv",
    ".ttf", ".otf", ".woff", ".woff2",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".pyc", ".pyo", ".class",
    # Game assets — binary compressed data, always high entropy, never malicious
    ".crp", ".unity3d", ".assetbundle", ".assets",
    ".uasset", ".umap", ".upk", ".rpf",
    ".bsa", ".ba2", ".vpk", ".wad", ".pk3", ".pk4",
    ".forge", ".big", ".arc", ".pac", ".res", ".bnk", ".xnb",
}

SCRIPT_EXTENSIONS = {".ps1", ".bat", ".cmd", ".vbs", ".js", ".hta", ".wsf"}

# ── Suspicious strings to look for in file content ───────────────────────────
# These appear frequently in malware but rarely in legitimate software.
SUSPICIOUS_STRINGS = [
    # PowerShell obfuscation / downloaders
    b"powershell -enc",
    b"powershell -e ",
    b"powershell -nop",
    b"iex(",
    b"invoke-expression",
    b"downloadstring(",
    b"downloadfile(",
    b"[convert]::frombase64string",
    # cmd obfuscation
    b"cmd /c",
    b"cmd.exe /c",
    # WMI abuse
    b"wmic process call create",
    b"win32_process",
    # Registry persistence
    b"currentversion\\run",
    b"software\\microsoft\\windows\\currentversion\\run",
    # Network
    b"http://",
    b"https://",
    # Common shellcode markers
    b"\x90\x90\x90\x90\x90\x90\x90\x90",  # NOP sled
    b"\xeb\xfe",                            # infinite loop (shellcode placeholder)
    # Encoding tricks
    b"base64",
    b"fromcharcode",
    b"unescape(",
    b"eval(",
    # Suspicious API imports as strings
    b"virtualalloc",
    b"writeprocessmemory",
    b"createremotethread",
    b"loadlibrary",
]

# PE imports that are almost exclusively used for malicious purposes
# when found together
DANGEROUS_IMPORTS = {
    "VirtualAlloc", "VirtualAllocEx",
    "WriteProcessMemory",
    "CreateRemoteThread",
    "NtUnmapViewOfSection",
    "ZwUnmapViewOfSection",
    "SetWindowsHookEx",
    "GetAsyncKeyState",       # keylogger
    "GetForegroundWindow",    # keylogger
    "InternetOpenUrl",
    "URLDownloadToFile",
    "ShellExecute",
    "WinExec",
    "CreateProcess",
}


# ── PE header check (pure Python, no pefile lib) ─────────────────────────────

def _read_pe_imports(data: bytes) -> list[str]:
    """
    Minimal PE import table parser — reads DLL/function name strings
    by scanning for the import directory. Not a full PE parser,
    but good enough to catch suspicious import names.
    """
    imports = []
    # Look for MZ header
    if len(data) < 64 or data[:2] != b"MZ":
        return imports
    try:
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 4 > len(data):
            return imports
        if data[pe_offset:pe_offset+4] != b"PE\x00\x00":
            return imports

        # Brute-force: scan the binary for known import name strings
        # This is simpler than parsing the full import table and works well in practice
        data_lower = data.lower()
        for name in DANGEROUS_IMPORTS:
            if name.lower().encode() in data_lower:
                imports.append(name)
    except Exception:
        pass
    return imports


# ── Extension mismatch check ──────────────────────────────────────────────────

# Magic bytes for common file types
MAGIC_BYTES = {
    b"MZ":               "PE executable",
    b"PK\x03\x04":       "ZIP/JAR/DOCX",
    b"\x7fELF":          "ELF executable",
    b"#!":               "Shell script",
    b"\xca\xfe\xba\xbe": "Java class",
    b"#!/":              "Script",
}


def _detect_magic(data: bytes) -> str | None:
    for magic, label in MAGIC_BYTES.items():
        if data[:len(magic)] == magic:
            return label
    return None


def check_extension_mismatch(path: str, data: bytes) -> str | None:
    """Returns a warning string if the file's true type doesn't match its extension."""
    ext    = Path(path).suffix.lower()
    magic  = _detect_magic(data[:8] if len(data) >= 8 else data)
    if not magic:
        return None

    if magic == "PE executable" and ext not in (".exe", ".dll", ".scr", ".cpl", ".ocx", ".sys"):
        return f"File has PE (executable) header but extension is '{ext}'"
    if magic == "ELF executable" and ext not in ("", ".elf", ".so", ".out"):
        return f"File has ELF (Linux executable) header but extension is '{ext}'"
    if magic == "Shell script" and ext not in (".sh", ".bash", ""):
        return f"File has shell script header but extension is '{ext}'"
    return None


# ── Main heuristic scan ───────────────────────────────────────────────────────

def heuristic_scan(path: str, sample_bytes: int = 32768) -> dict:
    """
    Run all heuristic checks on a file.

    Returns:
        {
            score:    int          — 0 (clean) to 100 (very suspicious)
            findings: list[str]    — human-readable descriptions of what was found
            verdict:  str          — "clean" | "suspicious" | "likely_malicious"
        }
    """
    findings = []
    score    = 0
    p        = Path(path)
    ext      = p.suffix.lower()

    # Pure data files — skip all heuristic checks, they always score 0
    if ext in DATA_EXTENSIONS:
        return {"score": 0, "findings": [], "verdict": "clean"}

    # ── 1. Suspicious location ────────────────────────────────────────────────
    path_lower = path.lower().replace("/", "\\")
    for sus_dir in SUSPICIOUS_DIRS:
        if sus_dir in path_lower:
            findings.append(f"Located in suspicious directory: …{sus_dir}…")
            score += 15
            break

    # ── 2. Executable in non-standard location ────────────────────────────────
    if ext in EXECUTABLE_EXTENSIONS:
        score += 5  # base risk for being executable

    # ── 3. Read file content ──────────────────────────────────────────────────
    try:
        with open(path, "rb") as f:
            data = f.read(sample_bytes)
    except (PermissionError, OSError):
        return {"score": 0, "findings": ["Could not read file"], "verdict": "unknown"}

    if not data:
        return {"score": 0, "findings": [], "verdict": "clean"}

    # ── 4. Extension mismatch ─────────────────────────────────────────────────
    mismatch = check_extension_mismatch(path, data)
    if mismatch:
        findings.append(mismatch)
        score += 40

    # ── 5. Suspicious strings ─────────────────────────────────────────────────
    data_lower = data.lower()
    string_hits = []
    for sus in SUSPICIOUS_STRINGS:
        if sus.lower() in data_lower:
            try:
                string_hits.append(sus.decode("utf-8", errors="replace").strip())
            except Exception:
                pass

    if string_hits:
        # Deduplicate and limit display
        unique_hits = list(dict.fromkeys(string_hits))[:5]
        findings.append(f"Contains suspicious strings: {', '.join(unique_hits)}")
        score += min(len(string_hits) * 8, 40)

    # ── 6. Dangerous PE imports ───────────────────────────────────────────────
    if data[:2] == b"MZ":  # only check PE files
        dangerous = _read_pe_imports(data)
        if dangerous:
            findings.append(f"Suspicious API imports: {', '.join(dangerous[:6])}")
            score += min(len(dangerous) * 6, 30)

    # ── 7. Script with network + execution combo ──────────────────────────────
    if ext in SCRIPT_EXTENSIONS:
        has_network = any(s in data_lower for s in [b"http://", b"https://", b"downloadstring"])
        has_exec    = any(s in data_lower for s in [b"iex(", b"invoke-expression", b"wmic", b"shellexecute"])
        if has_network and has_exec:
            findings.append("Script combines network download with code execution")
            score += 35

    # ── Verdict ───────────────────────────────────────────────────────────────
    score = min(score, 100)
    if score >= 60:
        verdict = "likely_malicious"
    elif score >= 25:
        verdict = "suspicious"
    else:
        verdict = "clean"

    return {"score": score, "findings": findings, "verdict": verdict}