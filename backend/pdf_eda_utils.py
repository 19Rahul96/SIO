from collections import Counter
from typing import Any, Dict, List


def _line_noise_ratio(line: str) -> float:
    if not line:
        return 0.0
    noisy = sum(1 for c in line if not c.isalnum() and c not in {" ", ".", ",", ":", ";", "-", "_", "(", ")", "/"})
    return noisy / max(1, len(line))


def analyze_pdf_quality(corpus: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    adapter = str(corpus.get("adapter") or "")
    blocks = corpus.get("text_blocks", []) or []
    if adapter != "pdf" or not blocks:
        return {
            "pdf_enabled": False,
            "page_confidence": [],
            "ocr_noise_regions": [],
            "repeated_headers_footers": {"headers": [], "footers": []},
            "malformed_table_extractions": [],
            "semantic_fragmentation": [],
            "entity_continuity": {"continuity_pairs": 0, "continuity_score": 1.0},
        }

    page_confidence = []
    ocr_noise = []
    malformed_tables = []
    headers = Counter()
    footers = Counter()
    page_entities: Dict[int, set] = {}

    for block in blocks:
        page = int(block.get("page") or 0)
        text = str(block.get("text") or "")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        char_len = len(text)
        alpha_ratio = sum(1 for c in text if c.isalnum() or c.isspace()) / max(1, char_len)
        confidence = min(1.0, (0.55 * min(1.0, char_len / 1200.0)) + (0.45 * alpha_ratio))
        page_confidence.append({"page": page, "confidence": round(confidence, 4), "char_count": char_len})

        if confidence < 0.45:
            ocr_noise.append({"page": page, "confidence": round(confidence, 4), "reason": "low_extraction_confidence"})

        noisy_lines = [ln for ln in lines if _line_noise_ratio(ln) > 0.35]
        if noisy_lines:
            ocr_noise.append({"page": page, "line_count": len(noisy_lines), "reason": "high_symbol_noise"})

        if lines:
            headers[lines[0].lower()] += 1
            footers[lines[-1].lower()] += 1

        table_like_lines = [ln for ln in lines if ln.count("|") >= 2 or ln.count("\t") >= 2]
        malformed = [ln for ln in table_like_lines if len(ln.split("|")) <= 2 and len(ln.split("\t")) <= 2]
        if malformed:
            malformed_tables.append({"page": page, "malformed_rows": malformed[:10]})

        pe = set()
        for ent in entities:
            preview = str(ent.get("chunk_preview") or "")
            if preview and preview in text:
                pe.add(str(ent.get("text") or "").strip().lower())
        page_entities[page] = pe

    rep_headers = [h for h, count in headers.items() if count > 1 and len(h) > 3]
    rep_footers = [f for f, count in footers.items() if count > 1 and len(f) > 3]

    pages = sorted(page_entities.keys())
    fragmentation = []
    continuity_pairs = 0
    for i in range(1, len(pages)):
        prev = page_entities.get(pages[i - 1], set())
        cur = page_entities.get(pages[i], set())
        if not prev and not cur:
            overlap = 1.0
        else:
            overlap = len(prev & cur) / max(1, len(prev | cur))
        if overlap < 0.1:
            fragmentation.append({"page_pair": [pages[i - 1], pages[i]], "overlap": round(overlap, 4)})
        if overlap >= 0.15:
            continuity_pairs += 1

    continuity_score = continuity_pairs / max(1, len(pages) - 1)

    return {
        "pdf_enabled": True,
        "page_confidence": page_confidence,
        "ocr_noise_regions": ocr_noise[:200],
        "repeated_headers_footers": {"headers": rep_headers[:25], "footers": rep_footers[:25]},
        "malformed_table_extractions": malformed_tables[:120],
        "semantic_fragmentation": fragmentation[:120],
        "entity_continuity": {
            "continuity_pairs": continuity_pairs,
            "adjacent_page_pairs": max(0, len(pages) - 1),
            "continuity_score": round(continuity_score, 4),
        },
    }
