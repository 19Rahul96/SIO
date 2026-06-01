"""Pure-Python statistical primitives ported from the legacy backend/eda_engine.py.

Used by the EDA Intelligence layer (s08) to produce numeric column statistics,
correlation matrices and consistency checks for tabular sources — no numpy/pandas
required (stdlib only) so it stays in the SIO standalone footprint.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from statistics import NormalDist
from typing import Any, Optional

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S")


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * pct
    low = int(k)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = k - low
    return sorted_vals[low] * (1.0 - frac) + sorted_vals[high] * frac


def _qq_points(sorted_vals: list[float], mean_val: float, std_val: float, max_points: int = 40) -> list[dict]:
    n = len(sorted_vals)
    if n == 0:
        return []
    if n <= max_points:
        indices = list(range(n))
    else:
        step = max(1, n // max_points)
        indices = list(range(0, n, step))[:max_points]
        indices[-1] = n - 1
    nd = NormalDist(mu=0.0, sigma=1.0)
    pts = []
    for i in indices:
        q = min(0.9999, max(0.0001, (i + 0.5) / n))
        z = nd.inv_cdf(q)
        pts.append({"expected": round(mean_val + (std_val * z if std_val > 0 else 0.0), 6), "actual": round(sorted_vals[i], 6)})
    return pts


def _pearson(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n <= 1:
        return 0.0
    xs, ys = x[:n], y[:n]
    mx, my = sum(xs) / n, sum(ys) / n
    vx = sum((v - mx) ** 2 for v in xs)
    vy = sum((v - my) ** 2 for v in ys)
    denom = (vx * vy) ** 0.5
    if denom <= 0:
        return 0.0
    return max(-1.0, min(1.0, sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / denom))


def _rank(values: list[float]) -> list[float]:
    indexed = sorted([(v, i) for i, v in enumerate(values)], key=lambda t: t[0])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][0] == indexed[i][0]:
            j += 1
        avg = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[indexed[k][1]] = avg
        i = j
    return ranks


def _spearman(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n <= 1:
        return 0.0
    return _pearson(_rank(x[:n]), _rank(y[:n]))


def _parse_dt(s: str) -> Optional[datetime]:
    txt = str(s or "").strip().replace("Z", "+00:00")
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt)
    except Exception:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(txt, fmt)
        except Exception:
            continue
    return None


def column_stats(name: str, raw_values: list[Any]) -> dict:
    """Full numeric/categorical profile for one column. Returns is_numeric flag."""
    values = [str(v).strip() for v in raw_values if str(v).strip() != ""]
    total = len(raw_values)
    null_count = total - len(values)
    nums = [f for f in (_to_float(v) for v in values) if f is not None]
    is_numeric = len(nums) >= max(3, int(0.6 * max(1, len(values))))

    base = {
        "column": name,
        "is_numeric": is_numeric,
        "count": len(values),
        "null_count": null_count,
        "null_rate": round(null_count / max(1, total), 4),
        "cardinality": len(set(values)),
        "most_common": [{"value": v, "count": c} for v, c in Counter(values).most_common(5)],
    }
    if not is_numeric or not nums:
        return base

    s = sorted(nums)
    n = len(s)
    mean_val = sum(nums) / n
    variance = sum((x - mean_val) ** 2 for x in nums) / n if n > 1 else 0.0
    std = variance ** 0.5
    q1, med, q3 = _percentile(s, 0.25), _percentile(s, 0.5), _percentile(s, 0.75)
    iqr = q3 - q1
    if std > 0 and n > 2:
        m3 = sum((x - mean_val) ** 3 for x in nums) / n
        m4 = sum((x - mean_val) ** 4 for x in nums) / n
        skewness, kurtosis = m3 / std**3, (m4 / std**4) - 3.0
    else:
        skewness = kurtosis = 0.0

    # Histogram (8 buckets).
    histogram = []
    if n:
        lo, hi = s[0], s[-1]
        width = (hi - lo) / 8 or 1.0
        for b in range(8):
            b_lo = lo + b * width
            b_hi = b_lo + width
            cnt = sum(1 for v in nums if (b_lo <= v < b_hi) or (b == 7 and v == hi))
            histogram.append({"min": round(b_lo, 6), "max": round(b_hi, 6), "count": cnt})

    # Z-score bins + outliers.
    z_bins = {"<-3": 0, "-3..-2": 0, "-2..2": 0, "2..3": 0, ">3": 0}
    z_outliers = []
    if std > 0:
        for v in nums:
            z = (v - mean_val) / std
            if z < -3:
                z_bins["<-3"] += 1
            elif z < -2:
                z_bins["-3..-2"] += 1
            elif z <= 2:
                z_bins["-2..2"] += 1
            elif z <= 3:
                z_bins["2..3"] += 1
            else:
                z_bins[">3"] += 1
            if abs(z) > 3:
                z_outliers.append(round(v, 6))
    lower_f, upper_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    iqr_outliers = [v for v in nums if v < lower_f or v > upper_f]
    whisker_lo = min((v for v in nums if v >= lower_f), default=s[0])
    whisker_hi = max((v for v in nums if v <= upper_f), default=s[-1])

    base.update({
        "min": round(s[0], 6), "max": round(s[-1], 6),
        "mean": round(mean_val, 6), "median": round(med, 6),
        "variance": round(variance, 6), "std_dev": round(std, 6),
        "q1": round(q1, 6), "q3": round(q3, 6), "iqr": round(iqr, 6),
        "p10": round(_percentile(s, 0.10), 6), "p90": round(_percentile(s, 0.90), 6),
        "skewness": round(skewness, 6), "kurtosis": round(kurtosis, 6),
        "histogram": histogram,
        "qq_points": _qq_points(s, mean_val, std),
        "box": {"lower_whisker": round(whisker_lo, 6), "q1": round(q1, 6), "median": round(med, 6),
                "q3": round(q3, 6), "upper_whisker": round(whisker_hi, 6)},
        "zscore_bins": z_bins,
        "outliers_iqr_count": len(iqr_outliers),
        "outliers_zscore_count": len(z_outliers),
        "outliers": sorted(set(z_outliers))[:25],
    })
    return base


def correlation(numeric_cols: dict[str, list[float]]) -> dict:
    """Pearson/Spearman matrices + ranked pair explorer over numeric columns (cap 10)."""
    keys = list(numeric_cols.keys())[:10]
    if len(keys) < 2:
        return {"available": False, "labels": keys, "pearson": [], "spearman": [], "pair_explorer": []}
    pearson, spearman, pairs = [], [], []
    for i, k1 in enumerate(keys):
        prow, srow = [], []
        for j, k2 in enumerate(keys):
            p = round(_pearson(numeric_cols[k1], numeric_cols[k2]), 4)
            sp = round(_spearman(numeric_cols[k1], numeric_cols[k2]), 4)
            prow.append(p)
            srow.append(sp)
            if j > i:
                pairs.append({"left": k1, "right": k2, "pearson": p, "spearman": sp})
        pearson.append(prow)
        spearman.append(srow)
    pairs.sort(key=lambda x: abs(x["pearson"]), reverse=True)
    strongest_pos = next((p for p in pairs if p["pearson"] > 0), None)
    strongest_neg = next((p for p in pairs if p["pearson"] < 0), None)
    return {
        "available": True, "labels": keys, "pearson": pearson, "spearman": spearman,
        "pair_explorer": pairs[:40], "strongest_positive": strongest_pos, "strongest_negative": strongest_neg,
    }


def consistency_checks(columns: list[dict], rows: list[dict]) -> dict:
    """Lightweight schema/quality checks across a tabular source."""
    invalid_dates = type_mismatches = enum_violations = null_key_violations = 0
    for col in columns:
        name = col["column"]
        label = col.get("semantic_label", "")
        vals = [str(r["cells"].get(name, "")).strip() for r in rows]
        nonnull = [v for v in vals if v]
        if label == "temporal" or col.get("datatype") == "date":
            invalid_dates += sum(1 for v in nonnull if _parse_dt(v) is None)
        if col.get("datatype") == "numeric":
            type_mismatches += sum(1 for v in nonnull if _to_float(v) is None)
        if label == "identifier" and "id" in name.lower():
            null_key_violations += len(vals) - len(nonnull)
    # Duplicate full rows.
    seen = Counter(tuple(sorted(r["cells"].items())) for r in rows)
    duplicates = sum(c - 1 for c in seen.values() if c > 1)
    return {
        "invalid_dates": invalid_dates,
        "type_mismatches": type_mismatches,
        "enum_violations": enum_violations,
        "null_key_violations": null_key_violations,
        "duplicates": duplicates,
    }
