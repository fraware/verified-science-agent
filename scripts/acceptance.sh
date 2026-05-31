#!/usr/bin/env bash
# Full acceptance bar for verified-science-agent (CI parity).
set -euo pipefail

pip install -e ".[dev,ui,pdf,signing,api]"
make demo
make test
vsa benchmark --out reports/benchmark_summary.json

COMMIT="$(git rev-parse HEAD)"
echo "ACCEPTANCE PASS commit=${COMMIT}"
echo "Update RELEASE_STATUS.md verified commit to: ${COMMIT}"
