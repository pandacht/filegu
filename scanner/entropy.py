# scanner/entropy.py — Shannon entropy analysis
#
# High entropy = data is compressed, encrypted, or packed.
# Legitimate code rarely exceeds 7.0. Malware packers often push 7.5+.
# Pure random data = 8.0 (theoretical max).

import math
from collections import Counter


def file_entropy(path: str, sample_bytes: int = 16384) -> float:
    """
    Calculate Shannon entropy of a file (or first sample_bytes of it).
    Returns a float in range [0.0, 8.0].
    """
    try:
        with open(path, "rb") as f:
            data = f.read(sample_bytes)
    except (PermissionError, OSError):
        return 0.0

    if not data:
        return 0.0

    counts = Counter(data)
    total  = len(data)
    entropy = -sum(
        (c / total) * math.log2(c / total)
        for c in counts.values()
        if c > 0
    )
    return round(entropy, 4)


def entropy_verdict(entropy: float) -> tuple[str, str]:
    """
    Returns (label, explanation) based on entropy value.
    """
    if entropy >= 7.5:
        return ("packed/encrypted",
                f"Entropy {entropy:.2f} — extremely high. Likely packed, encrypted, or obfuscated.")
    if entropy >= 7.0:
        return ("suspicious",
                f"Entropy {entropy:.2f} — high. May be compressed payload or obfuscated code.")
    if entropy >= 6.0:
        return ("elevated",
                f"Entropy {entropy:.2f} — slightly elevated. Could be compressed data or normal.")
    return ("normal",
            f"Entropy {entropy:.2f} — normal range.")