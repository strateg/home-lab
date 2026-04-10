#!/usr/bin/env python3
"""Template quality gate for a TUC package."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    tuc_root = Path(__file__).resolve().parent
    artifacts_dir = tuc_root / "artifacts"
    analysis_dir = tuc_root / "analysis"

    required = [
        tuc_root / "TUC.md",
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

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    print("Quality gate passed: template structure is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
