# scanner/yara_engine.py - YARA rule-based scanning
#
# YARA is the industry standard for malware pattern matching.
# Install: pip install yara-python
#
# This module handles:
#   - Checking if yara-python is installed
#   - Loading bundled YARA rules
#   - Scanning files and returning matches

from pathlib import Path

RULES_DIR = Path(__file__).parent / "yara_rules"
YARA_AVAILABLE = False
yara = None

try:
    import yara as _yara
    yara = _yara
    YARA_AVAILABLE = True
except ImportError:
    pass


# ── Bundled YARA rules ────────────────────────────────────────────────────────
# These are written inline so the app works without any external rule downloads.
# Based on publicly available malware signatures.

BUNDLED_RULES = """

rule Suspicious_PowerShell_Download {
    meta:
        description = "PowerShell script that downloads and executes code"
        severity = "high"
    strings:
        $dl1 = "DownloadString" nocase
        $dl2 = "DownloadFile" nocase
        $dl3 = "WebClient" nocase
        $exec1 = "IEX" nocase
        $exec2 = "Invoke-Expression" nocase
        $exec3 = "Invoke-Command" nocase
    condition:
        any of ($dl*) and any of ($exec*)
}

rule Suspicious_PowerShell_Encoded {
    meta:
        description = "PowerShell with base64-encoded payload"
        severity = "high"
    strings:
        $enc1 = "-EncodedCommand" nocase
        $enc2 = "-enc " nocase
        $enc3 = "FromBase64String" nocase
        $ps   = "powershell" nocase
    condition:
        $ps and any of ($enc*)
}

rule Keylogger_Indicators {
    meta:
        description = "Possible keylogger - captures keystrokes or clipboard"
        severity = "high"
    strings:
        $k1 = "GetAsyncKeyState" nocase
        $k2 = "GetForegroundWindow" nocase
        $k3 = "SetWindowsHookEx" nocase
        $k4 = "GetClipboardData" nocase
    condition:
        2 of them
}

rule Process_Injection {
    meta:
        description = "Classic process injection technique"
        severity = "critical"
    strings:
        $i1 = "VirtualAllocEx" nocase
        $i2 = "WriteProcessMemory" nocase
        $i3 = "CreateRemoteThread" nocase
        $i4 = "NtUnmapViewOfSection" nocase
    condition:
        2 of them
}

rule Suspicious_Batch_Script {
    meta:
        description = "Batch script with obfuscation or download behavior"
        severity = "medium"
    strings:
        $b1 = "certutil" nocase
        $b2 = "bitsadmin" nocase
        $b3 = "regsvr32" nocase
        $b4 = "mshta" nocase
        $b5 = "wscript" nocase
        $b6 = "cscript" nocase
        $dl = "http" nocase
    condition:
        any of ($b*) and $dl
}

rule Ransomware_Indicators {
    meta:
        description = "Possible ransomware behavior"
        severity = "critical"
    strings:
        $r1 = "CryptEncrypt" nocase
        $r2 = "CryptGenKey" nocase
        $r3 = "DeleteShadowCopies" nocase
        $r4 = "vssadmin delete shadows" nocase
        $r5 = "bitcoin" nocase
        $r6 = "decrypt your files" nocase
        $r7 = "your files have been encrypted" nocase
    condition:
        2 of them
}

rule Suspicious_VBS_Script {
    meta:
        description = "VBScript with execution or download capability"
        severity = "high"
    strings:
        $v1 = "CreateObject" nocase
        $v2 = "WScript.Shell" nocase
        $v3 = "MSXML2.XMLHTTP" nocase
        $v4 = "Scripting.FileSystemObject" nocase
        $dl = "http" nocase
    condition:
        ($v1 or $v2) and ($v3 or $dl)
}

rule Executable_In_Temp {
    meta:
        description = "Executable file with suspicious temp/appdata path in strings"
        severity = "medium"
    strings:
        $t1 = "\\Temp\\" nocase
        $t2 = "\\tmp\\" nocase
        $t3 = "%TEMP%" nocase
        $t4 = "AppData\\Local\\Temp" nocase
    condition:
        uint16(0) == 0x5A4D and any of them
}

rule Shellcode_NOP_Sled {
    meta:
        description = "Long NOP sled - typical shellcode pattern"
        severity = "high"
    strings:
        $nop = { 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 }
    condition:
        $nop
}

rule Suspicious_JS_Obfuscation {
    meta:
        description = "JavaScript with common obfuscation patterns"
        severity = "medium"
    strings:
        $o1 = "eval(" nocase
        $o2 = "unescape(" nocase
        $o3 = "fromCharCode" nocase
        $o4 = "atob(" nocase
        $dl = "http" nocase
    condition:
        2 of ($o*) and $dl
}

"""


def is_available() -> bool:
    return YARA_AVAILABLE


def _compile_rules():
    """Compile all rules - bundled inline + any .yar files in rules dir."""
    if not YARA_AVAILABLE:
        return None

    sources = {"bundled": BUNDLED_RULES}

    # Load any extra .yar / .yara files from the rules directory
    if RULES_DIR.exists():
        for rule_file in RULES_DIR.glob("*.yar"):
            try:
                sources[rule_file.stem] = rule_file.read_text(encoding="utf-8")
            except Exception:
                pass
        for rule_file in RULES_DIR.glob("*.yara"):
            try:
                sources[rule_file.stem] = rule_file.read_text(encoding="utf-8")
            except Exception:
                pass

    try:
        return yara.compile(sources=sources)
    except Exception as e:
        # Fall back to bundled only
        try:
            return yara.compile(source=BUNDLED_RULES)
        except Exception:
            return None


# Compile once at import time
_compiled_rules = None


def scan_file(path: str) -> list[dict]:
    """
    Scan a file with YARA rules.
    Returns list of {rule, description, severity} dicts.
    Returns empty list if no matches or YARA not available.
    """
    global _compiled_rules

    if not YARA_AVAILABLE:
        return []

    if _compiled_rules is None:
        _compiled_rules = _compile_rules()
    if _compiled_rules is None:
        return []

    try:
        matches = _compiled_rules.match(path, timeout=10)
    except Exception:
        return []

    results = []
    for match in matches:
        meta = match.meta if hasattr(match, "meta") else {}
        results.append({
            "rule":        match.rule,
            "description": meta.get("description", match.rule),
            "severity":    meta.get("severity", "medium"),
        })
    return results


def reload_rules():
    """Force recompile rules (call after adding new .yar files)."""
    global _compiled_rules
    _compiled_rules = None