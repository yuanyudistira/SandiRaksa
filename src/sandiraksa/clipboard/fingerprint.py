"""
Clipboard content fingerprinting.

Design 18: use SHA-256 (or BLAKE2), never Python's builtin ``hash()`` which is
salted per-process and unsuitable for stable identity. Fingerprints are used
to detect self-writes (feedback-loop protection, design 19) and to reject
stale results (design 51, 52).

Fingerprint history is memory-only (design 18); nothing here writes to disk.
"""

from __future__ import annotations

import hashlib


def fingerprint_text(text: str) -> str:
    """
    Return a stable SHA-256 hex digest of clipboard text.

    ``surrogatepass`` is used so pathological/lone-surrogate Unicode (which a
    hostile clipboard may contain, design 5.4) does not raise during encoding.

    Args:
        text: Clipboard text to fingerprint.

    Returns:
        64-char lowercase hex SHA-256 digest.
    """
    return hashlib.sha256(
        text.encode("utf-8", errors="surrogatepass")
    ).hexdigest()


def length_bucket(n: int) -> str:
    """
    Coarse text-length bucket for privacy-safe metadata logging (design 59).

    Never log raw length of highly specific payloads; a bucket is enough for
    telemetry while leaking almost nothing about the content.
    """
    if n <= 0:
        return "0"
    if n < 100:
        return "<100"
    if n < 1_000:
        return "<1k"
    if n < 10_000:
        return "<10k"
    if n < 100_000:
        return "<100k"
    if n < 512_000:
        return "<512k"
    return ">=512k"


__all__ = ["fingerprint_text", "length_bucket"]
