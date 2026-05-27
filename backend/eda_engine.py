"""EDA Engine for DB profile outputs.

This stage is intentionally data-driven and local-only:
- Computes table/column behavior from profiler outputs.
- Produces anomaly flags and relationship evidence.
- Persists artifacts for audit and downstream scoring.
"""

import json
import os
import time
from datetime import datetime
from collections import Counter
from statistics import NormalDist
from typing import Any, Dict, List, Optional, Tuple


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _normalize_samples(raw: List[Any]) -> List[str]:
    return [str(v).strip() for v in (raw or []) if str(v).strip()]


def _numeric_summary(samples: List[str]) -> Tuple[List[float], Optional[float], Optional[float], Optional[float]]:
    numeric_values: List[float] = []
    for item in samples:
        parsed = _to_float(item)
        if parsed is not None:
            numeric_values.append(parsed)
    if not numeric_values:
        return numeric_values, None, None, None

    mean_val = sum(numeric_values) / len(numeric_values)
    if len(numeric_values) > 1:
        variance = sum((x - mean_val) ** 2 for x in numeric_values) / len(numeric_values)
        std_val = variance ** 0.5
    else:
        std_val = 0.0
    return numeric_values, min(numeric_values), max(numeric_values), std_val


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * pct
    low = int(k)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = k - low
    return sorted_vals[low] * (1.0 - frac) + sorted_vals[high] * frac


def _sampled_qq_points(sorted_vals: List[float], mean_val: float, std_val: float, max_points: int = 40) -> List[Dict[str, float]]:
    n = len(sorted_vals)
    if n == 0:
        return []
    if n <= max_points:
        indices = list(range(n))
    else:
        step = max(1, n // max_points)
        indices = list(range(0, n, step))[:max_points]
        if indices[-1] != (n - 1):
            indices[-1] = n - 1

    nd = NormalDist(mu=0.0, sigma=1.0)
    points: List[Dict[str, float]] = []
    for i in indices:
        q = min(0.9999, max(0.0001, (i + 0.5) / n))
        z = nd.inv_cdf(q)
        expected = mean_val + (std_val * z if std_val > 0 else 0.0)
        points.append(
            {
                "expected": round(expected, 6),
                "actual": round(sorted_vals[i], 6),
            }
        )
    return points


def _covariance(x: List[float], y: List[float]) -> float:
    n = min(len(x), len(y))
    if n <= 1:
        return 0.0
    xs = x[:n]
    ys = y[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n


def _pearson(x: List[float], y: List[float]) -> float:
    n = min(len(x), len(y))
    if n <= 1:
        return 0.0
    xs = x[:n]
    ys = y[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    vx = sum((v - mx) ** 2 for v in xs)
    vy = sum((v - my) ** 2 for v in ys)
    denom = (vx * vy) ** 0.5
    if denom <= 0:
        return 0.0
    return max(-1.0, min(1.0, sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / denom))


def _rank(values: List[float]) -> List[float]:
    indexed = sorted([(v, i) for i, v in enumerate(values)], key=lambda t: t[0])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][0] == indexed[i][0]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[indexed[k][1]] = avg_rank
        i = j
    return ranks


def _spearman(x: List[float], y: List[float]) -> float:
    n = min(len(x), len(y))
    if n <= 1:
        return 0.0
    return _pearson(_rank(x[:n]), _rank(y[:n]))


def _parse_datetime(sample: str) -> Optional[datetime]:
    txt = str(sample or "").strip()
    if not txt:
        return None
    txt = txt.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(txt)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(txt, fmt)
        except Exception:
            continue
    return None


def _health_score(
    completeness: float,
    consistency: float,
    uniqueness: float,
    validity: float,
    anomaly_ratio: float,
) -> float:
    score = (
        0.30 * completeness
        + 0.22 * consistency
        + 0.20 * uniqueness
        + 0.18 * validity
        + 0.10 * max(0.0, 1.0 - anomaly_ratio)
    )
    return max(0.0, min(1.0, round(score, 4)))


def _build_time_series(datetime_columns: Dict[str, List[datetime]]) -> Dict[str, Any]:
    if not datetime_columns:
        return {
            "available": False,
            "series": [],
            "trend_points": [],
            "moving_average": [],
            "rolling_volatility": [],
            "event_spikes": [],
        }

    all_days: Dict[str, int] = {}
    for values in datetime_columns.values():
        for dt in values:
            key = dt.date().isoformat()
            all_days[key] = all_days.get(key, 0) + 1

    keys = sorted(all_days.keys())
    trend_points = [{"date": k, "count": all_days[k]} for k in keys]

    moving_average = []
    rolling_volatility = []
    event_spikes = []
    counts = [all_days[k] for k in keys]
    for i, key in enumerate(keys):
        left = max(0, i - 2)
        window = counts[left : i + 1]
        avg = sum(window) / max(1, len(window))
        var = sum((v - avg) ** 2 for v in window) / max(1, len(window))
        std = var ** 0.5
        moving_average.append({"date": key, "value": round(avg, 4)})
        rolling_volatility.append({"date": key, "value": round(std, 4)})
        if std > 0 and abs(counts[i] - avg) >= (2.0 * std):
            event_spikes.append({"date": key, "count": counts[i], "z_proxy": round(_safe_div(abs(counts[i] - avg), std), 4)})

    return {
        "available": True,
        "series": trend_points,
        "trend_points": trend_points,
        "moving_average": moving_average,
        "rolling_volatility": rolling_volatility,
        "event_spikes": event_spikes,
    }


def run_eda_engine(profile_output: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    table_stats: Dict[str, Any] = {}
    anomaly_flags: Dict[str, Any] = {}
    relationship_evidence: Dict[str, Any] = {}
    numeric_columns: Dict[str, List[float]] = {}
    numeric_meta: Dict[str, Dict[str, Any]] = {}
    datetime_columns: Dict[str, List[datetime]] = {}
    stats_profiles: Dict[str, Any] = {}
    validation_errors: List[Dict[str, Any]] = []
    total_missing = 0.0
    total_columns = 0
    total_duplicate_proxy = 0
    total_anomaly_columns = 0
    timestamp_detected_columns = 0
    total_numeric_values = 0

    tables = profile_output.get("tables", [])
    sample_lookup: Dict[Tuple[str, str], List[str]] = {}

    for table in tables:
        table_name = str(table.get("table_name") or "").strip()
        if not table_name:
            continue
        for col in table.get("columns", []):
            col_name = str(col.get("column") or col.get("name") or "").strip()
            if not col_name:
                continue
            sample_lookup[(table_name, col_name)] = _normalize_samples(col.get("sample_values", []))

    for table in tables:
        table_name = str(table.get("table_name") or "").strip()
        if not table_name:
            continue

        col_stats: Dict[str, Any] = {}
        col_anomalies: Dict[str, Any] = {}
        high_risk_columns = 0

        for col in table.get("columns", []):
            col_name = str(col.get("column") or col.get("name") or "").strip()
            if not col_name:
                continue

            null_pct = _to_float(col.get("null_pct")) or 0.0
            null_rate = max(0.0, min(1.0, null_pct / 100.0))
            cardinality = int(col.get("cardinality") or 0)
            samples = _normalize_samples(col.get("sample_values", []))
            value_counts = Counter(samples)
            most_common = value_counts.most_common(5)

            numeric_values, min_num, max_num, std_val = _numeric_summary(samples)
            col_key = f"{table_name}.{col_name}"
            total_columns += 1
            total_missing += null_rate
            total_numeric_values += len(numeric_values)
            outliers: List[float] = []
            if numeric_values and std_val is not None and std_val > 0:
                mean_val = sum(numeric_values) / len(numeric_values)
                for val in numeric_values:
                    z = abs(val - mean_val) / std_val
                    if z >= 3.0:
                        outliers.append(round(val, 6))

            unique_in_sample = len(set(samples))
            sample_size = len(samples)
            uniqueness_ratio = round((unique_in_sample / max(1, sample_size)), 4)
            duplicate_proxy = max(0, sample_size - unique_in_sample)
            total_duplicate_proxy += duplicate_proxy

            anomalies: List[str] = []
            if null_rate >= 0.5:
                anomalies.append("high_null_rate")
            if sample_size >= 5 and uniqueness_ratio <= 0.2:
                anomalies.append("low_sample_uniqueness")
            if outliers:
                anomalies.append("numeric_outliers")

            if anomalies:
                high_risk_columns += 1
                col_anomalies[col_name] = anomalies
                total_anomaly_columns += 1

            if numeric_values:
                numeric_columns[col_key] = numeric_values
                numeric_meta[col_key] = {
                    "null_rate": round(null_rate, 4),
                    "sample_size": sample_size,
                    "variance": round((std_val or 0.0) ** 2, 6),
                }

            semantic_label = str(col.get("semantic_label", "")).lower()
            is_datetime_candidate = semantic_label == "datetime" or any(x in col_name.lower() for x in ["date", "time", "timestamp"])
            if is_datetime_candidate:
                parsed_dates = [d for d in (_parse_datetime(v) for v in samples) if d is not None]
                invalid_dates = max(0, len(samples) - len(parsed_dates))
                timestamp_detected_columns += 1
                if parsed_dates:
                    datetime_columns[col_key] = parsed_dates
                if invalid_dates > 0:
                    validation_errors.append(
                        {
                            "table": table_name,
                            "column": col_name,
                            "check": "invalid_dates",
                            "count": invalid_dates,
                            "severity": "medium" if invalid_dates <= 3 else "high",
                        }
                    )

            if semantic_label in {"identifier", "unknown"} and null_rate > 0.0:
                validation_errors.append(
                    {
                        "table": table_name,
                        "column": col_name,
                        "check": "null_key_violations",
                        "count": int(round(null_rate * max(1, sample_size))),
                        "severity": "high" if null_rate >= 0.1 else "medium",
                    }
                )

            if sample_size >= 8 and cardinality <= 10:
                normalized = Counter(str(v).strip().lower() for v in samples)
                if len(normalized) >= 2:
                    rare = sum(1 for _, c in normalized.items() if c == 1)
                    if rare >= 2:
                        validation_errors.append(
                            {
                                "table": table_name,
                                "column": col_name,
                                "check": "enum_violations",
                                "count": rare,
                                "severity": "medium",
                            }
                        )

            if sample_size >= 6 and semantic_label in {"quantity", "score", "age", "monetary_value"}:
                parse_rate = _safe_div(len(numeric_values), sample_size)
                if parse_rate < 0.8:
                    validation_errors.append(
                        {
                            "table": table_name,
                            "column": col_name,
                            "check": "type_mismatches",
                            "count": int(round((1.0 - parse_rate) * sample_size)),
                            "severity": "medium",
                        }
                    )

            sorted_vals = sorted(numeric_values)
            if sorted_vals:
                q1 = _percentile(sorted_vals, 0.25)
                q2 = _percentile(sorted_vals, 0.50)
                q3 = _percentile(sorted_vals, 0.75)
                iqr = max(0.0, q3 - q1)
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                iqr_outliers = [v for v in sorted_vals if v < lower or v > upper]
                mean_val = sum(sorted_vals) / len(sorted_vals)
                variance = _safe_div(sum((v - mean_val) ** 2 for v in sorted_vals), len(sorted_vals))
                std_calc = variance ** 0.5
                if std_calc > 0:
                    m3 = _safe_div(sum((v - mean_val) ** 3 for v in sorted_vals), len(sorted_vals))
                    m4 = _safe_div(sum((v - mean_val) ** 4 for v in sorted_vals), len(sorted_vals))
                    skewness = m3 / (std_calc ** 3)
                    kurtosis = (m4 / (std_calc ** 4)) - 3.0
                else:
                    skewness = 0.0
                    kurtosis = 0.0

                qq_points = _sampled_qq_points(sorted_vals, mean_val, std_calc)
                z_values = [((v - mean_val) / std_calc) if std_calc > 0 else 0.0 for v in sorted_vals]
                z_anoms = [z for z in z_values if abs(z) >= 3.0]
                bucket_size = max(1, len(sorted_vals) // 8)
                histogram = []
                for i in range(0, len(sorted_vals), bucket_size):
                    chunk = sorted_vals[i : i + bucket_size]
                    histogram.append({"min": round(min(chunk), 6), "max": round(max(chunk), 6), "count": len(chunk)})
                stats_profiles[col_key] = {
                    "count": len(sorted_vals),
                    "min": round(sorted_vals[0], 6),
                    "max": round(sorted_vals[-1], 6),
                    "mean": round(mean_val, 6),
                    "median": round(q2, 6),
                    "variance": round(variance, 6),
                    "std_dev": round(std_calc, 6),
                    "q1": round(q1, 6),
                    "q3": round(q3, 6),
                    "iqr": round(iqr, 6),
                    "p10": round(_percentile(sorted_vals, 0.10), 6),
                    "p90": round(_percentile(sorted_vals, 0.90), 6),
                    "skewness": round(skewness, 6),
                    "kurtosis": round(kurtosis, 6),
                    "histogram": histogram,
                    "qq_points": qq_points,
                    "zscore_bins": [
                        {"band": "<-3", "count": sum(1 for z in z_values if z < -3)},
                        {"band": "-3..-2", "count": sum(1 for z in z_values if -3 <= z < -2)},
                        {"band": "-2..2", "count": sum(1 for z in z_values if -2 <= z <= 2)},
                        {"band": "2..3", "count": sum(1 for z in z_values if 2 < z <= 3)},
                        {"band": ">3", "count": sum(1 for z in z_values if z > 3)},
                    ],
                    "outliers_iqr_count": len(iqr_outliers),
                    "outliers_zscore_count": len(z_anoms),
                    "box": {
                        "lower_whisker": round(min(sorted_vals), 6),
                        "q1": round(q1, 6),
                        "median": round(q2, 6),
                        "q3": round(q3, 6),
                        "upper_whisker": round(max(sorted_vals), 6),
                    },
                }

            col_stats[col_name] = {
                "null_rate": round(null_rate, 4),
                "null_pct": round(null_pct, 2),
                "cardinality": cardinality,
                "sample_size": sample_size,
                "unique_in_sample": unique_in_sample,
                "uniqueness_ratio": uniqueness_ratio,
                "min": col.get("min") if col.get("min") is not None else min_num,
                "max": col.get("max") if col.get("max") is not None else max_num,
                "most_common": [[k, v] for k, v in most_common],
                "outlier_count": len(outliers),
                "outliers": outliers[:25],
            }

        table_stats[table_name] = {
            "columns": col_stats,
            "column_count": len(col_stats),
            "high_risk_column_count": high_risk_columns,
            "high_risk_ratio": round(high_risk_columns / max(1, len(col_stats)), 4),
        }
        if col_anomalies:
            anomaly_flags[table_name] = col_anomalies

    # Relationship evidence from implicit relationships and sample overlap.
    for rel in profile_output.get("implicit_relationships", []):
        st = str(rel.get("source_table") or "").strip()
        sc = str(rel.get("source_col") or "").strip()
        tt = str(rel.get("target_table") or "").strip()
        tc = str(rel.get("target_col") or "").strip()
        if not (st and sc and tt and tc):
            continue

        left = set(sample_lookup.get((st, sc), []))
        right = set(sample_lookup.get((tt, tc), []))
        overlap = left & right
        overlap_denom = min(len(left), len(right)) if left and right else 0
        overlap_pct = round(len(overlap) / overlap_denom, 4) if overlap_denom else 0.0

        key = f"{st}.{sc}->{tt}.{tc}"
        relationship_evidence[key] = {
            "basis": rel.get("basis", "implicit"),
            "prior_confidence": round(float(rel.get("confidence", 0.0) or 0.0), 4),
            "left_sample_count": len(left),
            "right_sample_count": len(right),
            "overlap_count": len(overlap),
            "overlap_pct": overlap_pct,
            "joinability_signal": "strong" if overlap_pct >= 0.7 else "medium" if overlap_pct >= 0.35 else "weak",
        }

    ranked_numeric = sorted(
        numeric_columns.items(),
        key=lambda kv: (
            numeric_meta.get(kv[0], {}).get("sample_size", 0),
            numeric_meta.get(kv[0], {}).get("variance", 0.0),
            -numeric_meta.get(kv[0], {}).get("null_rate", 0.0),
        ),
        reverse=True,
    )[:10]

    corr_labels = [k for k, _ in ranked_numeric]
    pearson_matrix: List[List[float]] = []
    spearman_matrix: List[List[float]] = []
    covariance_matrix: List[List[float]] = []
    strongest_positive = {"pair": None, "value": -1.0}
    strongest_negative = {"pair": None, "value": 1.0}
    pair_explorer: List[Dict[str, Any]] = []

    for i, (k1, v1) in enumerate(ranked_numeric):
        p_row: List[float] = []
        s_row: List[float] = []
        c_row: List[float] = []
        for j, (k2, v2) in enumerate(ranked_numeric):
            p = round(_pearson(v1, v2), 4)
            s = round(_spearman(v1, v2), 4)
            c = round(_covariance(v1, v2), 4)
            p_row.append(p)
            s_row.append(s)
            c_row.append(c)
            if i < j:
                pair_explorer.append({"left": k1, "right": k2, "pearson": p, "spearman": s, "covariance": c})
                if p > strongest_positive["value"]:
                    strongest_positive = {"pair": [k1, k2], "value": p}
                if p < strongest_negative["value"]:
                    strongest_negative = {"pair": [k1, k2], "value": p}
        pearson_matrix.append(p_row)
        spearman_matrix.append(s_row)
        covariance_matrix.append(c_row)

    pair_explorer.sort(key=lambda x: abs(float(x.get("pearson", 0.0))), reverse=True)
    vif_proxy = []
    for i, label in enumerate(corr_labels):
        row = pearson_matrix[i] if i < len(pearson_matrix) else []
        max_r2 = 0.0
        for j, r in enumerate(row):
            if i == j:
                continue
            max_r2 = max(max_r2, float(r) ** 2)
        vif = round(1.0 / max(1e-6, (1.0 - max_r2)), 4)
        vif_proxy.append({"feature": label, "vif": vif, "status": "high" if vif > 5 else "ok"})

    ts_payload = _build_time_series(datetime_columns)

    orphan_relationships = sum(1 for rel in relationship_evidence.values() if rel.get("joinability_signal") == "weak")
    foreign_key_issues = orphan_relationships
    schema_drift_count = sum(1 for t in tables if str(t.get("table_semantic_label", "unknown")).lower() == "unknown")

    consistency_checks = {
        "invalid_dates": sum(e.get("count", 0) for e in validation_errors if e.get("check") == "invalid_dates"),
        "broken_schema_entries": sum(e.get("count", 0) for e in validation_errors if e.get("check") == "type_mismatches"),
        "type_mismatches": sum(e.get("count", 0) for e in validation_errors if e.get("check") == "type_mismatches"),
        "enum_violations": sum(e.get("count", 0) for e in validation_errors if e.get("check") == "enum_violations"),
        "null_key_violations": sum(e.get("count", 0) for e in validation_errors if e.get("check") == "null_key_violations"),
        "duplicate_entity_ids": 0,
        "orphan_relationships": orphan_relationships,
        "foreign_key_issues": foreign_key_issues,
        "schema_drift": schema_drift_count,
        "inconsistent_category_labels": 0,
        "errors": validation_errors[:200],
    }

    completeness = max(0.0, min(1.0, 1.0 - _safe_div(total_missing, max(1, total_columns))))
    consistency = max(0.0, min(1.0, 1.0 - _safe_div(len(validation_errors), max(1, total_columns))))
    uniqueness = max(0.0, min(1.0, 1.0 - _safe_div(total_duplicate_proxy, max(1, total_numeric_values))))
    validity = max(0.0, min(1.0, 1.0 - _safe_div(consistency_checks["invalid_dates"], max(1, timestamp_detected_columns))))
    anomaly_ratio = _safe_div(total_anomaly_columns, max(1, total_columns))
    health = _health_score(completeness, consistency, uniqueness, validity, anomaly_ratio)

    dtype_distribution = Counter()
    for table in tables:
        for col in table.get("columns", []):
            semantic = str(col.get("semantic_label", "unknown"))
            dtype_distribution[semantic] += 1

    schema_tree = []
    for table in tables:
        table_name = str(table.get("table_name") or "").strip()
        if not table_name:
            continue
        schema_tree.append(
            {
                "table": table_name,
                "schema": table.get("schema"),
                "table_semantic_label": table.get("table_semantic_label", "unknown"),
                "columns": [
                    {
                        "name": str(col.get("column") or col.get("name") or ""),
                        "semantic_label": col.get("semantic_label", "unknown"),
                        "null_pct": round(float(col.get("null_pct", 0.0) or 0.0), 2),
                        "cardinality": int(col.get("cardinality", 0) or 0),
                    }
                    for col in table.get("columns", [])
                    if str(col.get("column") or col.get("name") or "").strip()
                ],
            }
        )

    outlier_columns = []
    for col_key, profile in stats_profiles.items():
        if profile.get("outliers_iqr_count", 0) or profile.get("outliers_zscore_count", 0):
            outlier_columns.append(
                {
                    "column": col_key,
                    "iqr_outliers": int(profile.get("outliers_iqr_count", 0) or 0),
                    "zscore_outliers": int(profile.get("outliers_zscore_count", 0) or 0),
                    "box": profile.get("box", {}),
                    "zscore_bins": profile.get("zscore_bins", []),
                }
            )

    executive_summary = []
    if (1.0 - completeness) > 0.1:
        executive_summary.append(
            {
                "message": f"Dataset has {round((1.0 - completeness) * 100, 1)}% missing values.",
                "severity": "medium" if (1.0 - completeness) < 0.25 else "high",
                "business_impact": "Data quality can reduce model and retrieval accuracy.",
                "recommendation": "Prioritize null-heavy columns for remediation.",
                "confidence": 0.9,
            }
        )
    if orphan_relationships > 0:
        executive_summary.append(
            {
                "message": f"Detected {orphan_relationships} weak relationship links with low joinability.",
                "severity": "medium",
                "business_impact": "Graph completeness and traceability may be reduced.",
                "recommendation": "Review FK mappings and implicit relationship rules.",
                "confidence": 0.86,
            }
        )
    if ts_payload.get("event_spikes"):
        executive_summary.append(
            {
                "message": f"Detected {len(ts_payload.get('event_spikes', []))} potential event spikes in timestamped samples.",
                "severity": "low",
                "business_impact": "Temporal volatility may indicate operational anomalies.",
                "recommendation": "Validate spikes against known business events.",
                "confidence": 0.78,
            }
        )
    if schema_drift_count > 0:
        executive_summary.append(
            {
                "message": f"Potential schema drift indicators found in {schema_drift_count} tables.",
                "severity": "medium",
                "business_impact": "Schema drift can break downstream mapping assumptions.",
                "recommendation": "Review unknown semantic table labels and update mappings.",
                "confidence": 0.8,
            }
        )

    capabilities = {
        "supports_time_series": bool(ts_payload.get("available")),
        "supports_correlation": len(corr_labels) >= 2,
        "supports_kg_metrics": True,
        "supports_feature_importance": False,
    }

    core_kpis = {
        "total_records": int(sum(max(0, int(stats.get("sample_size", 0) or 0)) for stats in [c for t in table_stats.values() for c in t.get("columns", {}).values()])),
        "total_columns": total_columns,
        "missing_pct": round((1.0 - completeness) * 100.0, 2),
        "duplicate_rows": int(total_duplicate_proxy),
        "anomaly_count": int(total_anomaly_columns),
        "file_size": 0,
        "entities_extracted": 0,
        "relationships_extracted": len(relationship_evidence),
        "schema_drift_count": int(schema_drift_count),
        "orphan_relationships": int(orphan_relationships),
        "processing_time_ms": 0,
        "timestamp_coverage_pct": round(100.0 * _safe_div(timestamp_detected_columns, max(1, total_columns)), 2),
    }

    data_health = {
        "schema_tree": schema_tree,
        "datatype_distribution": [{"type": k, "count": v} for k, v in dtype_distribution.most_common()],
        "completeness": {
            "complete_pct": round(completeness * 100.0, 2),
            "missing_pct": round((1.0 - completeness) * 100.0, 2),
            "null_matrix_summary": {
                "high_null_columns": sum(1 for t in table_stats.values() for c in t.get("columns", {}).values() if float(c.get("null_rate", 0.0)) >= 0.5),
                "medium_null_columns": sum(1 for t in table_stats.values() for c in t.get("columns", {}).values() if 0.2 <= float(c.get("null_rate", 0.0)) < 0.5),
                "low_null_columns": sum(1 for t in table_stats.values() for c in t.get("columns", {}).values() if float(c.get("null_rate", 0.0)) < 0.2),
            },
            "completeness_heatmap_summary": [
                {
                    "table": t,
                    "avg_missing_pct": round(100.0 * _safe_div(sum(float(c.get("null_rate", 0.0)) for c in s.get("columns", {}).values()), max(1, len(s.get("columns", {})))), 2),
                }
                for t, s in table_stats.items()
            ],
            "duplicate_distribution": [
                {
                    "table": t,
                    "duplicate_proxy": int(sum(max(0, int(c.get("sample_size", 0) or 0) - int(c.get("unique_in_sample", 0) or 0)) for c in s.get("columns", {}).values())),
                }
                for t, s in table_stats.items()
            ],
        },
        "health_score": {
            "score": health,
            "formula": {
                "completeness": 0.30,
                "consistency": 0.22,
                "uniqueness": 0.20,
                "validity": 0.18,
                "anomaly_ratio_inverse": 0.10,
            },
            "inputs": {
                "completeness": round(completeness, 4),
                "consistency": round(consistency, 4),
                "uniqueness": round(uniqueness, 4),
                "validity": round(validity, 4),
                "anomaly_ratio": round(anomaly_ratio, 4),
            },
        },
    }

    correlation = {
        "labels": corr_labels,
        "pearson": pearson_matrix,
        "spearman": spearman_matrix,
        "covariance": covariance_matrix,
        "pair_explorer": pair_explorer[:40],
        "strongest_positive": strongest_positive,
        "strongest_negative": strongest_negative,
        "vif": {
            "available": len(corr_labels) >= 3,
            "values": vif_proxy,
        },
    }

    outliers = {
        "summary": {
            "affected_columns": len(outlier_columns),
            "zscore_anomaly_count": sum(int(c.get("zscore_outliers", 0) or 0) for c in outlier_columns),
            "iqr_outlier_count": sum(int(c.get("iqr_outliers", 0) or 0) for c in outlier_columns),
        },
        "columns": outlier_columns[:30],
    }

    statistical_profiles = {
        "columns": stats_profiles,
        "available": bool(stats_profiles),
    }

    artifact = {
        "status": "eda_complete",
        "generated_at": time.time(),
        "table_stats": table_stats,
        "anomaly_flags": anomaly_flags,
        "relationship_evidence": relationship_evidence,
        "capabilities": capabilities,
        "core_kpis": core_kpis,
        "data_health": data_health,
        "correlation": correlation,
        "outliers": outliers,
        "consistency_checks": consistency_checks,
        "statistical_profiles": statistical_profiles,
        "time_series": ts_payload,
        "kg_analytics": {
            "relationship_type_distribution": [
                {"joinability": "strong", "count": sum(1 for r in relationship_evidence.values() if r.get("joinability_signal") == "strong")},
                {"joinability": "medium", "count": sum(1 for r in relationship_evidence.values() if r.get("joinability_signal") == "medium")},
                {"joinability": "weak", "count": sum(1 for r in relationship_evidence.values() if r.get("joinability_signal") == "weak")},
            ],
            "connected_components": len(table_stats),
            "graph_density": round(_safe_div(len(relationship_evidence), max(1, len(table_stats) * max(1, len(table_stats) - 1))), 4),
        },
        "executive_summary": executive_summary,
        "summary": {
            "table_count": len(table_stats),
            "anomalous_table_count": len(anomaly_flags),
            "relationship_evidence_count": len(relationship_evidence),
        },
    }

    artifact_path = os.path.join(output_dir, "eda_artifact.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f)

    return artifact
