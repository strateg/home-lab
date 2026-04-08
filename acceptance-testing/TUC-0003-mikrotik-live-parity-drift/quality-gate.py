#!/usr/bin/env python3
"""Quality gate for TUC-0003 (MikroTik live parity and drift)."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    tuc_root = Path(__file__).resolve().parent
    repo_root = tuc_root.parents[1]

    required = [
        tuc_root / "TUC.md",
        tuc_root / "README.md",
        tuc_root / "TEST-MATRIX.md",
        tuc_root / "HOW-TO.md",
        tuc_root / "quality-gate.py",
        tuc_root / "analysis" / "IMPLEMENTATION-PLAN.md",
        tuc_root / "analysis" / "EVIDENCE-LOG.md",
        tuc_root / "analysis" / "PROJECT-STATUS-REPORT.md",
        repo_root / "docs" / "runbooks" / "MIKROTIK-TERRAFORM-DRIFT-CHECK.md",
        repo_root / "tests" / "plugin_integration" / "test_tuc0003_mikrotik_live_parity.py",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        print("Quality gate failed: missing required files")
        for path in missing:
            print(f"- {path}")
        return 1

    artifacts_dir = tuc_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    marker = artifacts_dir / ".gitkeep"
    if not marker.exists():
        marker.write_text("", encoding="utf-8")

    print("Quality gate passed: TUC-0003 structure is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
