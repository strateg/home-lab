#!/usr/bin/env python3
"""Validate cutover evidence bundle and emit Go/No-Go decision payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cutover evidence and derive Go/No-Go decision.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--summary-path", type=Path, default=Path("build/diagnostics/cutover/summary.json"))
    return parser.parse_args()


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    summary_path = args.summary_path if args.summary_path.is_absolute() else repo_root / args.summary_path
    summary = _load_json(summary_path)
    reasons: list[str] = []

    if not isinstance(summary, dict):
        reasons.append(f"missing or invalid summary file: {summary_path}")
    else:
        checks = summary.get("checks", [])
        if not isinstance(checks, list):
            reasons.append("cutover summary has invalid checks payload")
            checks = []
        for row in checks:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "unknown"))
            rc = int(row.get("return_code", 1))
            if rc != 0:
                reasons.append(f"cutover check failed: {name} (rc={rc})")

        split_row = next(
            (row for row in checks if isinstance(row, dict) and str(row.get("name", "")) == "split_rehearsal"),
            None,
        )
        if isinstance(split_row, dict):
            split_summary_path = None
            command = split_row.get("command", [])
            if isinstance(command, list) and "--summary-path" in command:
                idx = command.index("--summary-path")
                if idx + 1 < len(command):
                    split_summary_path = Path(str(command[idx + 1]))
            if split_summary_path and not split_summary_path.is_absolute():
                split_summary_path = repo_root / split_summary_path
            split_summary = _load_json(split_summary_path) if isinstance(split_summary_path, Path) else None
            if not isinstance(split_summary, dict):
                reasons.append("split rehearsal summary is missing or invalid")
            else:
                soho_checks = split_summary.get("soho_contract_checks", {})
                if not isinstance(soho_checks, dict) or not bool(soho_checks.get("ok")):
                    reasons.append("split rehearsal SOHO contract checks are not green")
                critical = soho_checks.get("critical_e794x", [])
                if isinstance(critical, list) and critical:
                    reasons.append("critical E794x diagnostics present: " + ", ".join(str(item) for item in critical))
                parity = split_summary.get("operator_readiness_parity_check", {})
                if not isinstance(parity, dict) or not bool(parity.get("ok")):
                    reasons.append("operator-readiness parity check failed")
        else:
            reasons.append("split_rehearsal check entry is missing from cutover summary")

    decision = "GO" if not reasons else "NO-GO"
    payload = {
        "decision": decision,
        "summary_path": str(summary_path),
        "reasons": reasons,
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if decision == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
