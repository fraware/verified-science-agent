#!/usr/bin/env python3
"""DEPRECATED: Use `vsa hash` instead."""
import sys
print("DEPRECATED: use `vsa hash <report.json>`", file=sys.stderr)
from vsa.cli import main
sys.argv = ["vsa", "hash", "--json"] + sys.argv[1:]
raise SystemExit(main())
