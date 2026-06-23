# scanner/signature.py — Authenticode / digital signature verification
#
# Uses PowerShell's Get-AuthenticodeSignature on Windows (no extra libs needed).
# On macOS/Linux uses `codesign` for Mach-O binaries.
# Falls back gracefully on unsupported platforms.
#
# Signature statuses and what they mean:
#   Valid         → signed and trusted                    → score: 0 (good)
#   NotSigned     → no signature at all                  → score: +15 for .exe/.dll in risky locations
#   HashMismatch  → file was modified after signing      → score: +60 (very suspicious)
#   NotTrusted    → signed but cert chain not trusted    → score: +30
#   UnknownError  → couldn't verify                      → score: 0  (neutral)

import os
import sys
import subprocess
import json
from pathlib import Path


# Extensions that can carry Authenticode signatures on Windows
SIGNABLE_EXTENSIONS = {
    ".exe", ".dll", ".msi", ".cab", ".cat",
    ".ps1", ".psm1", ".psd1",               # PowerShell
    ".appx", ".msix",
}

# Risky locations — unsigned exe here is more suspicious
RISKY_LOCATIONS = {
    "temp", "tmp", "downloads", "appdata\\local\\temp",
    "desktop", "recycle",
}


def check_signature(path: str) -> dict:
    """
    Check the Authenticode signature of a file.

    Returns:
        {
            status:   str   — "valid" | "not_signed" | "hash_mismatch" |
                               "not_trusted" | "unknown" | "unsupported"
            signer:   str   — e.g. "Microsoft Corporation" or ""
            score:    int   — points to add to the threat score
            message:  str   — human-readable summary
        }
    """
    ext = Path(path).suffix.lower()

    if ext not in SIGNABLE_EXTENSIONS:
        return _result("unsupported", "", 0, "")

    if sys.platform == "win32":
        return _check_windows(path)
    elif sys.platform == "darwin":
        return _check_macos(path)
    else:
        return _result("unsupported", "", 0, "Signature check not supported on Linux")


def _check_windows(path: str) -> dict:
    """Use PowerShell Get-AuthenticodeSignature."""
    try:
        ps_script = (
            f"$s = Get-AuthenticodeSignature '{path.replace(chr(39), chr(34))}';"
            "$out = @{"
            "  status=$s.Status.ToString();"
            "  signer=if($s.SignerCertificate){{$s.SignerCertificate.Subject}}else{{''}};"
            "  thumbprint=if($s.SignerCertificate){{$s.SignerCertificate.Thumbprint}}else{{''}};"
            "};"
            "ConvertTo-Json $out"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip():
            return _result("unknown", "", 0, "Could not run signature check")

        data      = json.loads(result.stdout)
        status    = data.get("status", "UnknownError").lower()
        signer    = _extract_cn(data.get("signer", ""))

        return _interpret(status, signer, path)

    except subprocess.TimeoutExpired:
        return _result("unknown", "", 0, "Signature check timed out")
    except Exception as e:
        return _result("unknown", "", 0, f"Signature check error: {e}")


def _check_macos(path: str) -> dict:
    """Use codesign on macOS."""
    try:
        result = subprocess.run(
            ["codesign", "--verify", "--verbose=2", path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Try to get signer info
            info = subprocess.run(
                ["codesign", "-dv", path],
                capture_output=True, text=True, timeout=10
            )
            signer = ""
            for line in info.stderr.splitlines():
                if "Authority=" in line:
                    signer = line.split("Authority=", 1)[1].strip()
                    break
            return _result("valid", signer, 0,
                           f"Valid signature — {signer}" if signer else "Valid signature")
        else:
            stderr = result.stderr.lower()
            if "no signature" in stderr or "not signed" in stderr:
                return _interpret("notsigned", "", path)
            if "modified" in stderr or "invalid" in stderr:
                return _interpret("hashmismatch", "", path)
            return _result("unknown", "", 0, "Could not verify signature")

    except FileNotFoundError:
        return _result("unsupported", "", 0, "codesign not found")
    except Exception as e:
        return _result("unknown", "", 0, f"Signature check error: {e}")


def _interpret(status: str, signer: str, path: str) -> dict:
    """Convert a raw status string into a scored result."""
    path_lower = path.lower()
    in_risky   = any(r in path_lower for r in RISKY_LOCATIONS)

    if "valid" in status:
        msg = f"Valid signature — {signer}" if signer else "Valid signature"
        return _result("valid", signer, 0, msg)

    if "hashmismatch" in status or "hash_mismatch" in status:
        msg = (f"⚠ Signature INVALID — file was modified after signing"
               + (f" (originally by {signer})" if signer else ""))
        return _result("hash_mismatch", signer, 60, msg)

    if "nottrusted" in status or "not_trusted" in status:
        msg = (f"Signature not trusted"
               + (f" — signer: {signer}" if signer else ""))
        return _result("not_trusted", signer, 30, msg)

    if "notsigned" in status or "not_signed" in status:
        # Unsigned is normal for many legitimate tools
        # but riskier in temp/download locations
        score = 20 if in_risky else 0
        msg   = ("Unsigned executable in suspicious location" if in_risky
                 else "Not digitally signed")
        return _result("not_signed", "", score, msg)

    return _result("unknown", signer, 0, "Could not determine signature status")


def _extract_cn(subject: str) -> str:
    """Extract CN= value from a certificate subject string."""
    if not subject:
        return ""
    for part in subject.split(","):
        part = part.strip()
        if part.upper().startswith("CN="):
            return part[3:].strip()
    return subject.strip()


def _result(status: str, signer: str, score: int, message: str) -> dict:
    return {"status": status, "signer": signer, "score": score, "message": message}