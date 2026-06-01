"""End-to-end smoke test: runs the 14-layer pipeline on a synthetic document.

Usage: python -m app.smoke_test
Exits non-zero if any foundational stage fails or the graph ends up empty.
"""
from __future__ import annotations

import json
import sys

from .pipeline import run_pipeline
from .layers import s13_graph_consistency

SAMPLE = b"""
Acme Corporation reported revenue of $4,200,000 on 12/31/2023.
Acme Corp employs Jane Doe. Acme Corporation is located in Berlin.
Globex Inc owns Acme Corporation. Globex Inc is based in New York.
Jane Doe joined Acme on 01/15/2021.
"""


def main() -> int:
    report = run_pipeline(filename="acme_report.txt", raw=SAMPLE, role="analyst", domain="finance")
    print(json.dumps(report["summary"], indent=2, default=str))

    stages = report["stages"]
    failed = {k: v for k, v in stages.items() if v != "ok"}
    if failed:
        print(f"\nFAILED stages: {failed}", file=sys.stderr)
        return 1

    consistency = s13_graph_consistency.validate_graph()
    print("\nGraph consistency:", json.dumps(consistency, indent=2, default=str))

    s = report["summary"]
    if not s.get("entities") or not s.get("graph", {}).get("graph_node_total"):
        print("\nFAIL: empty graph", file=sys.stderr)
        return 1
    print("\nSMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
