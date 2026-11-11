"""Outbound redaction with deterministic placeholders, restored locally before tool execution.

Regex recognisers (email, Indian phone, Aadhaar-like, PAN-like, home dir) plus Presidio PERSON
detection (spaCy model from config), with always_redact / never_redact lists in config.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from brain.config import load_config

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("AADHAAR", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+91[ -]?|0)?[6-9]\d{9}(?!\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
]
_PLACEHOLDER = re.compile(r"<(?:EMAIL|AADHAAR|PHONE|PAN|HOME|PERSON)_[0-9a-f]{8}>")


def _tag(kind: str, value: str) -> str:
    return f"<{kind}_{hashlib.sha256(value.encode()).hexdigest()[:8]}>"


@lru_cache(maxsize=1)
def _analyzer() -> Any:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model = load_config()["privacy"]["ner_model"]
    nlp = NlpEngineProvider(
        nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": model}]}
    ).create_engine()
    return AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])


def _trim(probe: str, start: int, end: int, never: set[str]) -> tuple[int, int]:
    """Drop never_redact words (e.g. 'Downloads') from the edges of an NER span."""
    words = [(w.start() + start, w.end() + start) for w in re.finditer(r"\S+", probe[start:end])]
    while words and probe[words[0][0] : words[0][1]].lower() in never:
        words.pop(0)
    while words and probe[words[-1][0] : words[-1][1]].lower() in never:
        words.pop()
    return (words[0][0], words[-1][1]) if words else (start, start)


def _person_spans(text: str) -> list[tuple[int, int]]:
    cfg = load_config()["privacy"]
    never = {w.lower() for w in cfg.get("never_redact") or []}
    # same-length copy so "Rahul_Sharma_invoice.pdf" reads as words; spans still map 1:1
    probe = re.sub(r"[_\-./\\]", " ", text)
    spans = []
    for r in _analyzer().analyze(
        text=probe, language="en", entities=["PERSON"], score_threshold=cfg["ner_min_score"]
    ):
        start, end = _trim(probe, r.start, r.end, never)
        if start < end and not _PLACEHOLDER.search(text[start:end]):
            spans.append((start, end))
    for name in cfg.get("always_redact") or []:
        spans += [(m.start(), m.end()) for m in re.finditer(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)]
    return sorted(set(spans))


def _redact_persons(text: str, m: dict[str, str]) -> str:
    out, last = [], 0
    for start, end in _person_spans(text):
        if start < last:  # overlapping span
            continue
        v = text[start:end]
        tag = _tag("PERSON", v)
        m[tag] = v
        out += [text[last:start], tag]
        last = end
    return "".join(out) + text[last:]


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
    if load_config().get("privacy", {}).get("ner_model"):
        text = _redact_persons(text, m)
    return text


def restore(text: str, mapping: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda x: mapping.get(x.group(0), x.group(0)), text)
