"""Step 3 — Cleaning + Normalization.

WHY: standardize extracted data so semantics aren't polluted by surface noise.
PRODUCES: normalized text + a record of every transformation applied (explainable).
ORDERING: after extraction, before chunking — chunk boundaries should see clean text.
ENABLES: stable chunking, reliable entity matching, comparable numeric/temporal values.
"""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"[ \t]{2,}")
_NL = re.compile(r"\n{3,}")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CURRENCY = re.compile(r"(?P<sym>[$€£₹])\s?(?P<num>[\d,]+(?:\.\d+)?)")
_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")

_CURRENCY_CODE = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}


def normalize_corpus(corpus: dict) -> dict:
    text = corpus.get("plain_text", "")
    applied: list[str] = []

    # Encoding normalization (NFKC) — unify ligatures, full-width chars, etc.
    norm = unicodedata.normalize("NFKC", text)
    if norm != text:
        applied.append("encoding_nfkc")
    text = norm

    # Control-char + whitespace + newline normalization.
    if _CTRL.search(text):
        text = _CTRL.sub("", text)
        applied.append("strip_control_chars")
    text = _WS.sub(" ", text)
    text = _NL.sub("\n\n", text)
    applied.append("whitespace_collapse")

    # Currency normalization -> "<NUM> <CODE>".
    def _cur(m: re.Match) -> str:
        return f"{m.group('num').replace(',', '')} {_CURRENCY_CODE.get(m.group('sym'), m.group('sym'))}"

    if _CURRENCY.search(text):
        text = _CURRENCY.sub(_cur, text)
        applied.append("currency_iso")

    # Temporal normalization -> ISO-ish YYYY-MM-DD where unambiguous.
    def _date(m: re.Match) -> str:
        a, b, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = ("20" if int(y) < 70 else "19") + y
        return f"{y}-{int(a):02d}-{int(b):02d}"

    if _DATE.search(text):
        text = _DATE.sub(_date, text)
        applied.append("temporal_iso")

    text = text.strip()
    corpus = dict(corpus)
    corpus["plain_text"] = text
    corpus["normalization"] = {
        "applied": applied,
        "char_count": len(text),
    }
    return corpus
