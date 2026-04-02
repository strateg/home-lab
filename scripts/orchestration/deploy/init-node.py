#!/usr/bin/env python3
"""CLI wrapper for ADR 0083 init-node orchestrator scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow file-path invocation (`python scripts/.../init-node.py`) from repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.init_node import main

if __name__ == "__main__":
    raise SystemExit(main())
