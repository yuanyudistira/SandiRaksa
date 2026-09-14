"""
Derive a plain-text representation from clipboard HTML (design 21).

Clipboard HTML is untrusted input (design 5.4): it may be huge, malformed, or
crafted to trigger pathological parsing. We therefore use a bounded, dependency
-free extraction (strip tags, unescape entities, collapse whitespace) rather
than a full HTML parser, and cap the input size before processing.
"""

from __future__ import annotations

import html as _html
import re

# Bound HTML input before regex work to avoid pathological cost (design 43).
_MAX_HTML_CHARS = 2_000_000

_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTINEWLINE_RE = re.compile(r"\n{3,}")


def html_to_plain_text(html_text: str) -> str:
    """Convert clipboard HTML to a best-effort plain-text representation."""
    if not html_text:
        return ""

    if len(html_text) > _MAX_HTML_CHARS:
        html_text = html_text[:_MAX_HTML_CHARS]

    # Drop script/style bodies entirely.
    text = _SCRIPT_STYLE_RE.sub(" ", html_text)
    # Turn common block boundaries into newlines so structure survives.
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", text)
    # Remove all remaining tags.
    text = _TAG_RE.sub("", text)
    # Unescape entities (&amp; -> &, &#123; -> ...).
    text = _html.unescape(text)
    # Normalize whitespace.
    text = _WS_RE.sub(" ", text)
    text = _MULTINEWLINE_RE.sub("\n\n", text)
    return text.strip()


__all__ = ["html_to_plain_text"]
