#!/usr/bin/env python3
"""Template script for TUC performance baseline runs."""

from __future__ import annotations

import time
from pathlib import Path


def main() -> int:
    started = time.time()
    tuc_root = Path(__file__).resolve().parents[1]
    artefacts = tuc_root / "artefacts"
    artefacts.mkdir(parents=True, exist_ok=True)
    elapsed = time.time() - started
    print(f"Template performance baseline completed in {elapsed:.3f}s")
    print(f"Artefacts directory: {artefacts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
