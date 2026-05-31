#!/usr/bin/env bash
# Full test suite: demo build, unit tests, and benchmark evaluation.
set -euo pipefail

pip install -e ".[dev,ui,pdf,signing,api]"
make demo
make test
vsa benchmark --out reports/benchmark_summary.json

python - <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path("reports/benchmark_summary.json").read_text(encoding="utf-8"))
if summary.get("regression"):
    print("FAIL: benchmark regression", file=sys.stderr)
    sys.exit(1)
gaps = summary.get("category_gaps") or {}
bad = {k: v for k, v in gaps.items() if v}
if bad:
    print(f"FAIL: benchmark category gaps: {bad}", file=sys.stderr)
    sys.exit(1)
if summary.get("total", 0) < 50:
    print(f"FAIL: expected at least 50 benchmark tasks, got {summary.get('total')}", file=sys.stderr)
    sys.exit(1)
print(f"Benchmark OK: {summary['passed']}/{summary['total']} tasks passed")
PY

echo "All checks passed."
