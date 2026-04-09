#!/usr/bin/env python3
"""Run ADR0076/ADR0081 split rehearsal flow and emit machine-readable summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REQUIRED_HANDOVER_FILES = {
    "SYSTEM-SUMMARY.md",
    "NETWORK-SUMMARY.md",
    "ACCESS-RUNBOOK.md",
    "BACKUP-RUNBOOK.md",
    "RESTORE-RUNBOOK.md",
    "UPDATE-RUNBOOK.md",
    "INCIDENT-CHECKLIST.md",
    "ASSET-INVENTORY.csv",
    "CHANGELOG-SNAPSHOT.md",
}
_REQUIRED_REPORT_FILES = {
    "health-report.json",
    "drift-report.json",
    "backup-status.json",
    "restore-readiness.json",
    "operator-readiness.json",
    "support-bundle-manifest.json",
}
_ADR0091_D3_DOMAINS = {
    "greenfield-first-install",
    "brownfield-adoption",
    "router-replacement",
    "secret-rotation",
    "scheduled-update",
    "failed-update-rollback",
    "backup-and-restore",
    "operator-handover",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run split rehearsal lane for framework/project extraction flow.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--workspace-root", type=Path, default=Path("build/cutover/split-rehearsal/home-lab"))
    parser.add_argument("--summary-path", type=Path, default=Path("build/diagnostics/cutover/split-rehearsal.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-parity-check", action="store_true")
    return parser.parse_args()


def _hash_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[rel] = digest
    return out


def _run_command(*, cmd: list[str], cwd: Path, dry_run: bool) -> tuple[int, str]:
    if dry_run:
        return 0, "DRY-RUN: " + " ".join(cmd)
    run = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    output = (run.stdout or "") + (run.stderr or "")
    return int(run.returncode), output


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _evaluate_soho_artifacts(generated_artifacts_root: Path) -> dict[str, object]:
    product_root = generated_artifacts_root / "home-lab" / "product"
    handover_root = product_root / "handover"
    reports_root = product_root / "reports"

    handover_missing = sorted(name for name in _REQUIRED_HANDOVER_FILES if not (handover_root / name).exists())
    reports_missing = sorted(name for name in _REQUIRED_REPORT_FILES if not (reports_root / name).exists())

    operator_payload = _load_json(reports_root / "operator-readiness.json") or {}
    manifest_payload = _load_json(reports_root / "support-bundle-manifest.json") or {}
    evidence_payload = operator_payload.get("evidence", {})
    evidence_keys = set(evidence_payload.keys()) if isinstance(evidence_payload, dict) else set()
    missing_domains = sorted(_ADR0091_D3_DOMAINS - evidence_keys)
    diagnostics_payload = operator_payload.get("diagnostics", [])
    critical_e794x: list[str] = []
    if isinstance(diagnostics_payload, list):
        for row in diagnostics_payload:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code", "")).strip()
            severity = str(row.get("severity", "")).strip().lower()
            if severity == "error" and code.startswith("E794"):
                critical_e794x.append(code)
    critical_e794x = sorted(set(critical_e794x))

    manifest_state = str(manifest_payload.get("completeness_state", "unknown"))
    status = str(operator_payload.get("status", "unknown"))
    ok = (
        not handover_missing
        and not reports_missing
        and not missing_domains
        and manifest_state != "unknown"
        and not critical_e794x
    )
    return {
        "ok": ok,
        "handover_missing": handover_missing,
        "reports_missing": reports_missing,
        "missing_adr0091_domains": missing_domains,
        "critical_e794x": critical_e794x,
        "operator_status": status,
        "manifest_completeness_state": manifest_state,
    }


def _compare_operator_readiness_payloads(
    *,
    extracted_payload: dict,
    baseline_payload: dict,
) -> dict[str, object]:
    extracted_status = str(extracted_payload.get("status", "unknown"))
    baseline_status = str(baseline_payload.get("status", "unknown"))
    extracted_evidence = extracted_payload.get("evidence", {})
    baseline_evidence = baseline_payload.get("evidence", {})
    extracted_keys = set(extracted_evidence.keys()) if isinstance(extracted_evidence, dict) else set()
    baseline_keys = set(baseline_evidence.keys()) if isinstance(baseline_evidence, dict) else set()
    missing_in_extracted = sorted(baseline_keys - extracted_keys)
    extra_in_extracted = sorted(extracted_keys - baseline_keys)
    status_mismatch = extracted_status != baseline_status
    ok = not status_mismatch and not missing_in_extracted
    return {
        "ok": ok,
        "extracted_status": extracted_status,
        "baseline_status": baseline_status,
        "missing_evidence_keys_in_extracted": missing_in_extracted,
        "extra_evidence_keys_in_extracted": extra_in_extracted,
    }


def _evaluate_monorepo_parity(*, repo_root: Path, workspace_root: Path, dry_run: bool) -> dict[str, object]:
    if dry_run:
        return {
            "ok": True,
            "mode": "dry-run",
            "reason": "parity check skipped in dry-run",
        }

    python = str(repo_root / ".venv" / "bin" / "python")
    baseline_root = workspace_root.parent / "monorepo-baseline"
    if baseline_root.exists():
        shutil.rmtree(baseline_root)
    baseline_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        python,
        str(repo_root / "topology-tools" / "compile-topology.py"),
        "--repo-root",
        str(repo_root),
        "--topology",
        "topology/topology.yaml",
        "--secrets-mode",
        "passthrough",
        "--strict-model-lock",
        "--output-json",
        str(baseline_root / "effective.json"),
        "--diagnostics-json",
        str(baseline_root / "diagnostics.json"),
        "--diagnostics-txt",
        str(baseline_root / "diagnostics.txt"),
        "--artifacts-root",
        str(baseline_root / "generated-artifacts"),
    ]
    rc, output = _run_command(cmd=cmd, cwd=repo_root, dry_run=False)
    if rc != 0:
        return {
            "ok": False,
            "mode": "live",
            "reason": "monorepo compile failed",
            "return_code": rc,
            "output_preview": output[:1200],
        }

    extracted_operator = _load_json(
        workspace_root / "generated-artifacts" / "home-lab" / "product" / "reports" / "operator-readiness.json"
    )
    baseline_operator = _load_json(
        baseline_root / "generated-artifacts" / "home-lab" / "product" / "reports" / "operator-readiness.json"
    )
    if not isinstance(extracted_operator, dict) or not isinstance(baseline_operator, dict):
        return {
            "ok": False,
            "mode": "live",
            "reason": "operator-readiness payload missing in extracted or baseline output",
        }

    comparison = _compare_operator_readiness_payloads(
        extracted_payload=extracted_operator,
        baseline_payload=baseline_operator,
    )
    comparison["mode"] = "live"
    comparison["baseline_root"] = str(baseline_root)
    return comparison


def _seed_soho_catalogs(*, repo_root: Path, workspace_root: Path, dry_run: bool) -> tuple[int, str]:
    catalog_roots = ("product-bundles", "product-profiles")
    if dry_run:
        return 0, "DRY-RUN: seed topology catalogs " + ", ".join(catalog_roots)

    target_topology = workspace_root / "topology"
    target_topology.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in catalog_roots:
        source = repo_root / "topology" / name
        target = target_topology / name
        if not source.exists():
            return 1, f"missing source catalog directory: {source}"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        copied.append(str(target))
    return 0, "Copied catalogs: " + ", ".join(copied)


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    workspace_root = args.workspace_root if args.workspace_root.is_absolute() else repo_root / args.workspace_root
    summary_path = args.summary_path if args.summary_path.is_absolute() else repo_root / args.summary_path
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    workspace_root.parent.mkdir(parents=True, exist_ok=True)

    python = str(repo_root / ".venv" / "bin" / "python")
    bootstrap_script = str(repo_root / "topology-tools" / "utils" / "bootstrap-project-repo.py")
    run_steps: list[dict[str, object]] = []
    exit_code = 0

    steps: list[tuple[str, list[str], Path]] = [
        (
            "bootstrap_project_repo",
            [
                python,
                bootstrap_script,
                "--framework-root",
                str(repo_root),
                "--output-root",
                str(workspace_root),
                "--project-id",
                "home-lab",
                "--seed-project-root",
                str(repo_root / "projects" / "home-lab"),
                "--framework-submodule-url",
                str(repo_root),
                "--force",
            ],
            repo_root,
        ),
        (
            "generate_lock",
            [
                python,
                str(workspace_root / "framework" / "topology-tools" / "generate-framework-lock.py"),
                "--repo-root",
                str(workspace_root),
                "--project-root",
                str(workspace_root),
                "--project-manifest",
                str(workspace_root / "project.yaml"),
                "--framework-root",
                str(workspace_root / "framework"),
                "--framework-manifest",
                str(workspace_root / "framework" / "topology" / "framework.yaml"),
                "--lock-file",
                str(workspace_root / "framework.lock.yaml"),
                "--force",
            ],
            workspace_root,
        ),
        (
            "verify_lock",
            [
                python,
                str(workspace_root / "framework" / "topology-tools" / "verify-framework-lock.py"),
                "--repo-root",
                str(workspace_root),
                "--project-root",
                str(workspace_root),
                "--project-manifest",
                str(workspace_root / "project.yaml"),
                "--framework-root",
                str(workspace_root / "framework"),
                "--framework-manifest",
                str(workspace_root / "framework" / "topology" / "framework.yaml"),
                "--lock-file",
                str(workspace_root / "framework.lock.yaml"),
                "--strict",
            ],
            workspace_root,
        ),
        (
            "compile_strict",
            [
                python,
                str(workspace_root / "framework" / "topology-tools" / "compile-topology.py"),
                "--repo-root",
                str(workspace_root),
                "--topology",
                str(workspace_root / "topology.yaml"),
                "--secrets-mode",
                "passthrough",
                "--strict-model-lock",
                "--output-json",
                str(workspace_root / "generated" / "effective-topology.json"),
                "--diagnostics-json",
                str(workspace_root / "generated" / "diagnostics.json"),
                "--diagnostics-txt",
                str(workspace_root / "generated" / "diagnostics.txt"),
                "--artifacts-root",
                str(workspace_root / "generated-artifacts"),
            ],
            workspace_root,
        ),
    ]

    for step_name, cmd, cwd in steps:
        rc, output = _run_command(cmd=cmd, cwd=cwd, dry_run=bool(args.dry_run))
        run_steps.append(
            {
                "name": step_name,
                "return_code": rc,
                "cwd": str(cwd),
                "command": cmd,
                "output_preview": output[:1200],
            }
        )
        if rc != 0:
            exit_code = 1
            break

        if step_name == "bootstrap_project_repo":
            seed_rc, seed_output = _seed_soho_catalogs(
                repo_root=repo_root,
                workspace_root=workspace_root,
                dry_run=bool(args.dry_run),
            )
            run_steps.append(
                {
                    "name": "seed_soho_catalogs",
                    "return_code": seed_rc,
                    "cwd": str(workspace_root),
                    "command": ["copy", "topology/product-bundles", "topology/product-profiles"],
                    "output_preview": seed_output[:1200],
                }
            )
            if seed_rc != 0:
                exit_code = 1
                break

    generated_artifacts_hash = _hash_tree(workspace_root / "generated-artifacts")
    generated_hash = _hash_tree(workspace_root / "generated")
    soho_checks = _evaluate_soho_artifacts(workspace_root / "generated-artifacts")
    parity_check: dict[str, object]
    if args.skip_parity_check:
        parity_check = {
            "ok": True,
            "mode": "skipped",
            "reason": "--skip-parity-check is set",
        }
    else:
        parity_check = _evaluate_monorepo_parity(
            repo_root=repo_root,
            workspace_root=workspace_root,
            dry_run=bool(args.dry_run),
        )
    if not bool(soho_checks.get("ok")) and not args.dry_run:
        exit_code = 1
    if not bool(parity_check.get("ok")) and not args.dry_run:
        exit_code = 1
    summary: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "workspace_root": str(workspace_root),
        "dry_run": bool(args.dry_run),
        "status": "failed" if exit_code else "ok",
        "steps": run_steps,
        "soho_contract_checks": soho_checks,
        "operator_readiness_parity_check": parity_check,
        "generated_artifacts_file_count": len(generated_artifacts_hash),
        "generated_file_count": len(generated_hash),
        "generated_artifacts_hash": generated_artifacts_hash,
        "generated_hash": generated_hash,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "status": summary["status"]}, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
