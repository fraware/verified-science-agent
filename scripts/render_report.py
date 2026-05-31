#!/usr/bin/env python3
"""DEPRECATED: Use `vsa render` instead."""
import sys
print("DEPRECATED: use `vsa render <report.json> --format markdown`", file=sys.stderr)
from vsa.cli import main
args = ["vsa", "render"] + sys.argv[1:]
if "--out" not in sys.argv and "-o" not in sys.argv:
    args.extend(["--format", "markdown"])
sys.argv = args
raise SystemExit(main())
