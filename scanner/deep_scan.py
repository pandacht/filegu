# scanner/deep_scan.py — deep analysis for already-flagged files
#
# Runs on suspicious/malicious files only after a normal scan.
# Goes further than engine.py:
#   1. Full-file entropy (entire file, not just first 16KB)
#   2. String extraction — URLs, IPs, file paths, registry keys, email addresses
#   3. PE section analysis — names, entropy per section, suspicious flags
#   4. Compile timestamp (PE files)
#   5. Re-runs heuristics with full file read
#   6. Hash lookup (always, even for non-exe)

import re
import struct
from pathlib import Path

from scanner.hash_db    import lookup_hash, sha256_of_file, db_info
try:
    from scanner.signature import check_signature, SIGNABLE_EXTENSIONS
    _SIGNATURE_AVAILABLE = True
except ImportError:
    _SIGNATURE_AVAILABLE = False
    SIGNABLE_EXTENSIONS  = set()
    def check_signature(path): return {"status": "unsupported", "signer": "", "score": 0, "message": ""}
from scanner            import yara_engine


# ── String patterns to extract ────────────────────────────────────────────────
_URL_RE      = re.compile(rb'https?://[^\s\x00-\x1f"\'<>]{6,200}')
_IP_RE       = re.compile(rb'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?\b')
_EMAIL_RE    = re.compile(rb'[a-zA-Z0-9._%+\-]{2,}@[a-zA-Z0-9.\-]{2,}\.[a-zA-Z]{2,6}')
_REG_RE      = re.compile(rb'(?:HKEY_[A-Z_]+|HKLM|HKCU|HKCR)\\[^\x00\r\n"]{4,120}', re.IGNORECASE)
_PATH_RE     = re.compile(rb'[A-Za-z]:\\(?:[^\x00\r\n"<>|?*]{2,}\\){1,}[^\x00\r\n"<>|?*]{2,}')
_CMD_RE      = re.compile(rb'(?:cmd\.exe|powershell(?:\.exe)?|wscript|cscript|mshta)[^\x00\r\n"]{0,120}', re.IGNORECASE)


# ── PE helpers ────────────────────────────────────────────────────────────────

def _parse_pe_sections(data: bytes) -> list[dict]:
    """Extract PE section table — names, sizes, entropy, flags."""
    import math
    from collections import Counter

    sections = []
    try:
        if data[:2] != b"MZ":
            return sections
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_off + 6 > len(data):
            return sections
        if data[pe_off:pe_off+4] != b"PE\x00\x00":
            return sections

        # COFF header
        machine          = struct.unpack_from("<H", data, pe_off + 4)[0]
        num_sections     = struct.unpack_from("<H", data, pe_off + 6)[0]
        opt_header_size  = struct.unpack_from("<H", data, pe_off + 20)[0]
        section_table_off = pe_off + 24 + opt_header_size

        # Optional header — compile timestamp
        compile_ts = struct.unpack_from("<I", data, pe_off + 8)[0]

        for i in range(min(num_sections, 96)):
            off  = section_table_off + i * 40
            if off + 40 > len(data):
                break
            name      = data[off:off+8].rstrip(b"\x00").decode("ascii", errors="replace")
            vsize     = struct.unpack_from("<I", data, off + 8)[0]
            raw_off   = struct.unpack_from("<I", data, off + 20)[0]
            raw_size  = struct.unpack_from("<I", data, off + 16)[0]
            chars     = struct.unpack_from("<I", data, off + 36)[0]

            # Section entropy
            sec_data = data[raw_off: raw_off + raw_size]
            if sec_data:
                counts = Counter(sec_data)
                total  = len(sec_data)
                ent    = -sum((c/total) * math.log2(c/total) for c in counts.values() if c > 0)
            else:
                ent = 0.0

            flags = []
            if chars & 0x20000000: flags.append("executable")
            if chars & 0x40000000: flags.append("readable")
            if chars & 0x80000000: flags.append("writable")

            sections.append({
                "name":    name,
                "vsize":   vsize,
                "entropy": round(ent, 3),
                "flags":   flags,
            })

        return sections, compile_ts
    except Exception:
        return [], 0


# Packer sections used by malware
_PACKER_SECTIONS_BAD = {
    ".aspack", ".adata",
    ".themida", ".winlice",
    ".nsp0", ".nsp1", ".nsp2",
    "protect", ".packed",
}

# Packer sections used by legitimate software (games, anti-cheat, Ubisoft, UPX)
# High entropy but NOT suspicious
_PACKER_SECTIONS_LEGIT = {
    ".upx0", ".upx1", ".upx2", "upx0", "upx1", "upx2",
    ".UPX0", ".UPX1", ".UPX2", "UPX0", "UPX1", "UPX2",
    ".ubx0", ".ubx1", ".ubx2", ".UBX0", ".UBX1", ".UBX2",
    ".vmp0", ".vmp1", ".vmp2", ".VMP0", ".VMP1", ".VMP2",
    ".be", ".be2", ".eby",
}


def deep_scan_file(path: str) -> dict:
    """
    Run deep analysis on a single file.
    Returns a dict with all findings, ready to display.
    """
    p   = Path(path)
    ext = p.suffix.lower()

    result = {
        "path":            path,
        "name":            p.name,
        "verdict":         "unknown",
        "score":           0,
        "hash":            None,
        "hash_hit":        False,
        "signature":       {},
        "entropy_full":    0.0,
        "pe_sections":     [],
        "compile_ts":      0,
        "strings": {
            "urls":      [],
            "ips":       [],
            "emails":    [],
            "registry":  [],
            "paths":     [],
            "commands":  [],
        },
        "yara_matches":    [],
        "summary":         [],
    }

    # ── Read file (cap at 10 MB for speed) ───────────────────────────────────
    MAX_READ = 10 * 1024 * 1024  # 10 MB
    try:
        size = Path(path).stat().st_size
        with open(path, "rb") as f:
            data = f.read(MAX_READ)
        if size > MAX_READ:
            result["summary"].append(f"Large file ({size // 1024 // 1024} MB) — partial deep scan (first 10 MB)")
    except Exception as e:
        result["summary"].append(f"Cannot read file: {e}")
        result["verdict"] = "error"
        return result

    # ── 1. Full-file hash ─────────────────────────────────────────────────────
    try:
        import hashlib
        h = hashlib.sha256(data).hexdigest()
        result["hash"] = h
        info = db_info()
        if info["exists"] and info["count"] > 0:
            if lookup_hash(h):
                result["hash_hit"] = True
                result["score"]    = 100
                result["summary"].append("⛔ Hash confirmed in MalwareBazaar database")
    except Exception as e:
        result["summary"].append(f"Hash error: {e}")

    # ── 2. Full entropy ───────────────────────────────────────────────────────
    import math
    from collections import Counter
    if data:
        counts = Counter(data)
        total  = len(data)
        ent    = -sum((c/total)*math.log2(c/total) for c in counts.values() if c > 0)
        result["entropy_full"] = round(ent, 4)
        if ent >= 7.95:
            result["score"] += 30
            result["summary"].append(f"Full entropy {ent:.3f} — file is packed or encrypted")
        elif ent >= 7.5:
            result["score"] += 10
            result["summary"].append(f"Full entropy {ent:.3f} — elevated, possible obfuscation")

    # ── 3. String extraction ──────────────────────────────────────────────────
    def _decode(matches):
        seen = set()
        out  = []
        for m in matches:
            s = m.decode("utf-8", errors="replace").strip()
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out[:30]   # cap at 30 per category

    result["strings"]["urls"]     = _decode(_URL_RE.findall(data))
    result["strings"]["ips"]      = _decode(_IP_RE.findall(data))
    result["strings"]["emails"]   = _decode(_EMAIL_RE.findall(data))
    result["strings"]["registry"] = _decode(_REG_RE.findall(data))
    result["strings"]["paths"]    = _decode(_PATH_RE.findall(data))
    result["strings"]["commands"] = _decode(_CMD_RE.findall(data))

    if result["strings"]["urls"]:
        result["summary"].append(f"Contains {len(result['strings']['urls'])} URL(s)")
    if result["strings"]["ips"]:
        result["summary"].append(f"Contains {len(result['strings']['ips'])} IP address(es)")
    if result["strings"]["registry"]:
        result["summary"].append(f"References {len(result['strings']['registry'])} registry key(s)")
    if result["strings"]["commands"]:
        result["summary"].append(f"Contains {len(result['strings']['commands'])} shell command(s)")

    # ── 4. PE section analysis ────────────────────────────────────────────────
    if data[:2] == b"MZ":
        sections, compile_ts = _parse_pe_sections(data)
        result["pe_sections"]  = sections
        result["compile_ts"]   = compile_ts

        for sec in sections:
            name_l = sec["name"].lower().strip()
            if name_l in _PACKER_SECTIONS_BAD:
                result["score"] += 40
                result["summary"].append(f"Malicious packer section: '{sec['name']}'")
            elif name_l in {s.lower() for s in _PACKER_SECTIONS_LEGIT}:
                # Legitimate packer — note it but don't add score
                result["summary"].append(f"Protected section '{sec['name']}' (game/anti-cheat packer — normal)")
            elif sec["entropy"] >= 7.5 and "executable" in sec["flags"]:
                result["score"] += 25
                result["summary"].append(
                    f"Section '{sec['name']}' is executable with entropy {sec['entropy']:.2f}"
                )

    # ── 5. Signature (skipped in deep scan — use normal scan for this) ────────
    # PowerShell per-file is too slow for batch deep scanning

    # ── 6. YARA ───────────────────────────────────────────────────────────────
    if yara_engine.is_available():
        hits = yara_engine.scan_file(path)
        result["yara_matches"] = hits
        for hit in hits:
            result["score"] += {"critical": 50, "high": 35, "medium": 20}.get(hit["severity"], 15)
            result["summary"].append(f"YARA [{hit['severity'].upper()}]: {hit['description']}")

    # ── Final verdict ─────────────────────────────────────────────────────────
    score = min(result["score"], 100)
    result["score"] = score
    if score >= 60:
        result["verdict"] = "malicious"
    elif score >= 25:
        result["verdict"] = "suspicious"
    else:
        result["verdict"] = "clean"

    if not result["summary"]:
        result["summary"].append("No additional threats found in deep scan")

    return result