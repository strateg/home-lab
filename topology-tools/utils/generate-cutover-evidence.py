#!/usr/bin/env python3
"""Generate ADR0076 cutover evidence bundle under build/diagnostics/cutover."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate cutover strict-gate evidence files.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--output-dir", type=Path, default=Path("build/diagnostics/cutover"))
    parser.add_argument("--dry-run", action="store_true", help="Write placeholder evidence without running commands.")
    return parser.parse_args()


def _run_command(*, repo_root: Path, cmd: list[str], output_path: Path, dry_run: bool) -> int:
    if dry_run:
        if any("run-split-rehearsal.py" in token for token in cmd):
            try:
                idx = cmd.index("--summary-path")
                summary_path = Path(cmd[idx + 1])
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text(
                    json.dumps(
                        {
                            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "dry_run": True,
                            "status": "ok",
                            "steps": [],
                        },
                        indent=2,
                        ensure_ascii=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            except Exception:
                pass
        output_path.write_text(
            "DRY-RUN\n" + "COMMAND: " + " ".join(cmd) + "\n",
            encoding="utf-8",
        )
        return 0

    run = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, check=False)
    combined = (run.stdout or "") + (run.stderr or "")
    output_path.write_text(combined, encoding="utf-8")
    return int(run.returncode)


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    python = str(repo_root / ".venv" / "bin" / "python")
    commands = [
        (
            "verify_lock",
            [python, "topology-tools/verify-framework-lock.py", "--strict"],
            output_dir / "verify-lock.txt",
        ),
        (
            "verify_lock_package_trust_signature",
            [
                python,
                "topology-tools/verify-framework-lock.py",
                "--strict",
                "--enforce-package-trust",
                "--verify-package-artifact-files",
                "--verify-package-signature",
            ],
            output_dir / "verify-lock-package-trust-signature.txt",
        ),
        (
            "compile_strict",
            [
                python,
                "topology-tools/compile-topology.py",
                "--topology",
                "topology/topology.yaml",
                "--strict-model-lock",
                "--secrets-mode",
                "passthrough",
            ],
            output_dir / "compile.txt",
        ),
        (
            "compatibility_matrix",
            [python, "topology-tools/utils/validate-framework-compatibility-matrix.py"],
            output_dir / "compatibility.txt",
        ),
        (
            "audit_entrypoints",
            [python, "topology-tools/utils/audit-strict-runtime-entrypoints.py"],
            output_dir / "audit-entrypoints.txt",
        ),
        (
            "cutover_readiness_quick",
            [python, "topology-tools/utils/cutover-readiness-report.py", "--quick"],
            output_dir / "cutover-readiness.txt",
        ),
        (
            "split_rehearsal",
            [
                python,
                "topology-tools/utils/run-split-rehearsal.py",
                "--repo-root",
                str(repo_root),
                "--summary-path",
                str(output_dir / "split-rehearsal.json"),
            ]
            + (["--dry-run"] if args.dry_run else []),
            output_dir / "split-rehearsal.txt",
        ),
    ]

    summary: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "output_dir": str(output_dir),
        "dry_run": bool(args.dry_run),
        "checks": [],
    }

    exit_code = 0
    for check_name, cmd, output_path in commands:
        rc = _run_command(repo_root=repo_root, cmd=cmd, output_path=output_path, dry_run=bool(args.dry_run))
        summary["checks"].append(
            {
                "name": check_name,
                "return_code": rc,
                "output": str(output_path),
                "command": cmd,
            }
        )
        if rc != 0:
            exit_code = 1

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"output_dir": str(output_dir), "summary": str(summary_path), "exit_code": exit_code}, ensure_ascii=True
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
