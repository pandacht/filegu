# utils/virustotal.py — VirusTotal API v3 helper functions

import hashlib
import json
import urllib.request
import urllib.error

VT_BASE = "https://www.virustotal.com/api/v3"


def sha256_of_file(path: str, chunk: int = 65536) -> str:
    """Calculate the SHA-256 hash of a file without loading it fully into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def vt_lookup_hash(api_key: str, file_hash: str) -> dict:
    """
    Query VirusTotal v3 /files/{hash} endpoint.
    Returns the parsed JSON response dict, or {"not_found": True} on 404.
    Raises urllib.error.HTTPError for other HTTP errors.
    """
    url = f"{VT_BASE}/files/{file_hash}"
    req = urllib.request.Request(url, headers={"x-apikey": api_key})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"not_found": True}
        raise


def vt_parse_result(data: dict) -> dict:
    """
    Extract scan summary from a raw VT file report.

    Returns a dict with keys:
        status       : "malicious" | "suspicious" | "clean" | "unknown"
        malicious    : int
        suspicious   : int
        undetected   : int
        total        : int  (total engines that ran)
        names        : list[str]  (threat names from flagging engines)
        threat_label : str  (VT's suggested label, e.g. "trojan.generickd")
    """
    if data.get("not_found"):
        return {
            "status": "unknown", "malicious": 0, "suspicious": 0,
            "undetected": 0, "total": 0, "names": [],
            "threat_label": "Not in database",
        }

    attrs   = data.get("data", {}).get("attributes", {})
    stats   = attrs.get("last_analysis_stats", {})
    results = attrs.get("last_analysis_results", {})

    mal   = stats.get("malicious",  0)
    susp  = stats.get("suspicious", 0)
    und   = stats.get("undetected", 0)
    total = sum(stats.values())

    names = sorted({
        r.get("result")
        for r in results.values()
        if r.get("category") in ("malicious", "suspicious") and r.get("result")
    })

    threat_label = (
        attrs
        .get("popular_threat_classification", {})
        .get("suggested_threat_label", "")
    )

    if mal > 0:
        status = "malicious"
    elif susp > 0:
        status = "suspicious"
    else:
        status = "clean"

    return {
        "status": status, "malicious": mal, "suspicious": susp,
        "undetected": und, "total": total, "names": names,
        "threat_label": threat_label,
    }