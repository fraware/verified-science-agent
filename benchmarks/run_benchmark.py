"""CLI entry for benchmark suite (delegates to vsa.benchmark)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vsa.benchmark.runner import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VSA benchmark tasks")
    parser.add_argument("--live", action="store_true", help="Use live connector retrieval (network required)")
    parser.add_argument("--cache-dir", default=".vsa_cache")
    parser.add_argument("--tasks", type=Path, default=None)
    args = parser.parse_args()
    summary = run_benchmark(args.tasks, offline=not args.live, cache_dir=args.cache_dir)
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
