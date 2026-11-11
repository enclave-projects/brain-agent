"""Outbound redaction with deterministic placeholders, restored locally before tool execution.

Regex recognisers for now (email, Indian phone, Aadhaar-like, PAN-like, home dir).
Presidio NER (person names) is a Phase 8 addition; see docs/DECISIONS.md.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("AADHAAR", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+91[ -]?|0)?[6-9]\d{9}(?!\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
]
_PLACEHOLDER = re.compile(r"<(?:EMAIL|AADHAAR|PHONE|PAN|HOME)_[0-9a-f]{8}>")


def _tag(kind: str, value: str) -> str:
    return f"<{kind}_{hashlib.sha256(value.encode()).hexdigest()[:8]}>"


def redact(text: str, mapping: dict[str, str] | None = None) -> str:
    """Replace PII with stable placeholders. Adds placeholder -> original to `mapping`."""
    m = mapping if mapping is not None else {}
    home = str(Path.home())
    if len(home) > 3 and home in text:
        tag = _tag("HOME", home)
        m[tag] = home
        text = text.replace(home, tag)
    for kind, pat in _PATTERNS:

        def sub(match: re.Match[str], kind: str = kind) -> str:
            v = match.group(0)
            if _PLACEHOLDER.fullmatch(v):
                return v
            tag = _tag(kind, v)
            m[tag] = v
            return tag

        text = pat.sub(sub, text)
    return text


def restore(text: str, mapping: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda x: mapping.get(x.group(0), x.group(0)), text)
