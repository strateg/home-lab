#!/usr/bin/env python3
"""Rehearse framework lock rollback/regen flow in strict mode."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from framework_lock import _load_yaml, compute_framework_integrity, resolve_paths, verify_framework_lock


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_topology() -> Path:
    return _default_repo_root() / "topology" / "topology.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rehearse framework lock rollback flow.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root for path resolution.",
    )
    parser.add_argument(
        "--topology",
        type=Path,
        default=_default_topology(),
        help="Topology manifest path for project resolution.",
    )
    parser.add_argument(
        "--project",
        default="",
        help="Project id override (uses topology project.active when omitted).",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Explicit project root (alternative to topology-derived project path).",
    )
    parser.add_argument(
        "--project-manifest",
        type=Path,
        default=None,
        help="Explicit project manifest path (default: <project-root>/project.yaml).",
    )
    parser.add_argument(
        "--framework-root",
        type=Path,
        default=None,
        help="Framework root directory (default: repo root).",
    )
    parser.add_argument(
        "--framework-manifest",
        type=Path,
        default=None,
        help="Framework manifest path (default: <framework-root>/topology/framework.yaml).",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=None,
        help="Lock file path (default: <project-root>/framework.lock.yaml).",
    )
    return parser.parse_args()


def _run_generate(
    *,
    script_path: Path,
    repo_root: Path,
    topology_path: Path | None,
    project_id: str,
    project_root: Path,
    project_manifest_path: Path,
    framework_root: Path,
    framework_manifest_path: Path,
    output_lock_path: Path,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(script_path),
        "--repo-root",
        str(repo_root),
        "--project",
        project_id,
        "--project-root",
        str(project_root),
        "--project-manifest",
        str(project_manifest_path),
        "--framework-root",
        str(framework_root),
        "--framework-manifest",
        str(framework_manifest_path),
        "--lock-file",
        str(output_lock_path),
        "--force",
    ]
    if topology_path is not None and topology_path.exists():
        cmd.extend(["--topology", str(topology_path)])
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def _extract_contract(payload: dict[str, Any]) -> dict[str, Any]:
    framework = payload.get("framework", {})
    if not isinstance(framework, dict):
        framework = {}
    return {
        "project_schema_version": payload.get("project_schema_version"),
        "project_contract_revision": payload.get("project_contract_revision"),
        "framework.id": framework.get("id"),
        "framework.version": framework.get("version"),
        "framework.source": framework.get("source"),
        "framework.integrity": framework.get("integrity"),
    }


def main() -> int:
    args = parse_args()
    topology_path = args.topology if isinstance(args.topology, Path) and args.topology.exists() else None
    paths = resolve_paths(
        repo_root=args.repo_root,
        topology_path=topology_path,
        project_id=args.project,
        project_root=args.project_root,
        project_manifest_path=args.project_manifest,
        framework_root=args.framework_root,
        framework_manifest_path=args.framework_manifest,
        lock_path=args.lock_file,
    )

    current = verify_framework_lock(paths=paths, strict=True)
    if not current.ok:
        print("Rollback rehearsal failed: current lock is not strict-valid")
        for item in current.diagnostics:
            print(f"{item.severity.upper()} {item.code} {item.path}: {item.message}")
        return 1

    if not paths.lock_path.exists():
        print(f"Rollback rehearsal failed: missing lock file {paths.lock_path}")
        return 1

    current_payload = _load_yaml(paths.lock_path)
    expected_integrity = compute_framework_integrity(
        framework_root=paths.framework_root,
        framework_manifest=_load_yaml(paths.framework_manifest_path),
    )
    if _extract_contract(current_payload).get("framework.integrity") != expected_integrity:
        print("Rollback rehearsal failed: lock integrity does not match computed framework integrity")
        return 1

    generate_script = Path(__file__).resolve().parent / "generate-framework-lock.py"
    with tempfile.TemporaryDirectory(prefix="framework-rollback-rehearsal-") as tmp_dir:
        temp_lock = Path(tmp_dir) / "framework.lock.yaml"
        generated = _run_generate(
            script_path=generate_script,
            repo_root=paths.repo_root,
            topology_path=topology_path,
            project_id=paths.project_id,
            project_root=paths.project_root,
            project_manifest_path=paths.project_manifest_path,
            framework_root=paths.framework_root,
            framework_manifest_path=paths.framework_manifest_path,
            output_lock_path=temp_lock,
        )
        if generated.returncode != 0:
            print("Rollback rehearsal failed: cannot regenerate lock")
            print(generated.stdout)
            print(generated.stderr)
            return 1

        regen_paths = resolve_paths(
            repo_root=paths.repo_root,
            topology_path=topology_path,
            project_id=paths.project_id,
            project_root=paths.project_root,
            project_manifest_path=paths.project_manifest_path,
            framework_root=paths.framework_root,
            framework_manifest_path=paths.framework_manifest_path,
            lock_path=temp_lock,
        )
        regen_verify = verify_framework_lock(paths=regen_paths, strict=True)
        if not regen_verify.ok:
            print("Rollback rehearsal failed: regenerated lock failed strict verification")
            for item in regen_verify.diagnostics:
                print(f"{item.severity.upper()} {item.code} {item.path}: {item.message}")
            return 1

        regenerated_payload = _load_yaml(temp_lock)

    current_contract = _extract_contract(current_payload)
    regenerated_contract = _extract_contract(regenerated_payload)
    if current_contract != regenerated_contract:
        print("Rollback rehearsal failed: regenerated lock contract differs from current lock")
        print(f"current={current_contract}")
        print(f"regenerated={regenerated_contract}")
        return 1

    print("Framework rollback rehearsal: OK")
    print(f"project={paths.project_id}")
    print(f"lock={paths.lock_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
