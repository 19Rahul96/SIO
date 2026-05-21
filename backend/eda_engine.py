"""EDA Engine for DB profile outputs.

This stage is intentionally data-driven and local-only:
- Computes table/column behavior from profiler outputs.
- Produces anomaly flags and relationship evidence.
- Persists artifacts for audit and downstream scoring.
"""

import json
import os
import time
from collections import Counter
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


def run_eda_engine(profile_output: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    table_stats: Dict[str, Any] = {}
    anomaly_flags: Dict[str, Any] = {}
    relationship_evidence: Dict[str, Any] = {}

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

    artifact = {
        "status": "eda_complete",
        "generated_at": time.time(),
        "table_stats": table_stats,
        "anomaly_flags": anomaly_flags,
        "relationship_evidence": relationship_evidence,
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
