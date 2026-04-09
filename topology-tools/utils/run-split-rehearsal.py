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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run split rehearsal lane for framework/project extraction flow.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--workspace-root", type=Path, default=Path("build/phase13/split-rehearsal/home-lab"))
    parser.add_argument("--summary-path", type=Path, default=Path("build/diagnostics/phase13/split-rehearsal.json"))
    parser.add_argument("--dry-run", action="store_true")
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
    summary: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "workspace_root": str(workspace_root),
        "dry_run": bool(args.dry_run),
        "status": "failed" if exit_code else "ok",
        "steps": run_steps,
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
