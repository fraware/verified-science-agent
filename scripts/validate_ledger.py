#!/usr/bin/env python3
"""DEPRECATED: Use `vsa validate` instead."""
import sys
print("DEPRECATED: use `vsa validate <report.json>`", file=sys.stderr)
from vsa.cli import main
sys.argv = ["vsa", "validate"] + sys.argv[1:]
raise SystemExit(main())
