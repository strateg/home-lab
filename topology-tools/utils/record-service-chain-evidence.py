#!/usr/bin/env python3
"""CLI entrypoint for service-chain evidence execution/reporting."""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from service_chain_evidence import main  # pylint: disable=import-error

if __name__ == "__main__":
    raise SystemExit(main())
