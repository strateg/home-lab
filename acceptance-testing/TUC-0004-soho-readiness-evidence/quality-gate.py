#!/usr/bin/env python3
"""Quality gate for TUC-0004 package structure."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    tuc_root = Path(__file__).resolve().parent
    analysis_dir = tuc_root / "analysis"
    artefacts_dir = tuc_root / "artefacts"

    required = [
        tuc_root / "TUC.md",
        tuc_root / "README.md",
        tuc_root / "TEST-MATRIX.md",
        tuc_root / "HOW-TO.md",
        analysis_dir / "IMPLEMENTATION-PLAN.md",
        analysis_dir / "EVIDENCE-LOG.md",
        analysis_dir / "PROJECT-STATUS-REPORT.md",
    ]

    missing = [path for path in required if not path.exists()]
    if missing:
        print("Quality gate failed: missing required files")
        for path in missing:
            print(f"- {path}")
        return 1

    artefacts_dir.mkdir(parents=True, exist_ok=True)
    print("Quality gate passed: TUC-0004 structure is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
