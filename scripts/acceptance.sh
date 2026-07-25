#!/usr/bin/env bash
# Full test suite: demo build, companion quality gates, unit tests, benchmark.
# Offline-first: live connectors are never exercised (see skipped_live_connectors).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p reports
# Relative path: Git Bash $ROOT is /c/... which native Windows Python cannot open.
EXIT_CODES_FILE="reports/.acceptance_exit_codes.json"
trap 'rm -f "$EXIT_CODES_FILE"' EXIT
# Windows consoles default to cp1252; force UTF-8 for CLI Unicode messages.
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

record() {
  local name="$1"
  local code="$2"
  python - "$EXIT_CODES_FILE" "$name" "$code" <<'PY'
import json, sys
path, name, code = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
    data = json.loads(open(path, encoding="utf-8").read() or "{}")
except Exception:
    data = {}
data[name] = code
open(path, "w", encoding="utf-8").write(json.dumps(data))
PY
}

run_step() {
  local name="$1"
  shift
  echo "==> $name: $*"
  set +e
  "$@"
  local code=$?
  set -e
  record "$name" "$code"
  return "$code"
}

echo "{}" >"$EXIT_CODES_FILE"
OVERALL=0

run_step pip_install pip install -e ".[dev,ui,pdf,signing,api]" || OVERALL=1
run_step make_demo make demo || OVERALL=1
run_step make_lint make lint || OVERALL=1
run_step make_typecheck make typecheck || OVERALL=1
# Default pytest excludes live markers (pyproject addopts: -m 'not live')
run_step make_test make test || OVERALL=1
run_step make_decision_time make decision-time || OVERALL=1
run_step vsa_benchmark vsa benchmark --out reports/benchmark_summary.json || OVERALL=1

set +e
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
BENCH_CHECK=$?
set -e
record "benchmark_gate" "$BENCH_CHECK"
if [[ "$BENCH_CHECK" -ne 0 ]]; then
  OVERALL=1
fi

# Durable offline acceptance baseline (always written, including on failure)
python -m vsa.acceptance.skip_registry --exit-codes "$EXIT_CODES_FILE"
record "write_baseline" $?

if [[ "$OVERALL" -ne 0 ]]; then
  echo "Acceptance FAILED — see reports/acceptance_baseline.json for exit codes and skipped live connectors." >&2
  exit 1
fi

echo "All checks passed. Baseline: reports/acceptance_baseline.json"
exit 0
