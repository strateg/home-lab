#!/usr/bin/env python3
"""Generate baseline strict/validate evidence snapshot for ADR0076/ADR0081 P0."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate baseline evidence snapshot.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--output-dir", type=Path, default=Path("build/diagnostics/baseline"))
    return parser.parse_args()


def _run(cmd: list[str], *, cwd: Path, output: Path) -> int:
    run = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    merged = (run.stdout or "") + (run.stderr or "")
    output.write_text(merged, encoding="utf-8")
    return int(run.returncode)


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, object]] = []
    exit_code = 0
    task = ["task"]
    commands = [
        ("lock_refresh", task + ["framework:lock-refresh"], output_dir / "lock-refresh.txt"),
        ("framework_strict", task + ["framework:strict"], output_dir / "framework-strict.txt"),
        ("validate_passthrough", task + ["validate:passthrough"], output_dir / "validate-passthrough.txt"),
    ]

    for name, cmd, out in commands:
        rc = _run(cmd, cwd=repo_root, output=out)
        checks.append({"name": name, "return_code": rc, "output": str(out), "command": cmd})
        if rc != 0:
            exit_code = 1

    summary = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "output_dir": str(output_dir),
        "exit_code": exit_code,
        "checks": checks,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "exit_code": exit_code}, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
