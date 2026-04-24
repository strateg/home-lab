#!/usr/bin/env python3
"""Audit strict-only runtime entrypoints for legacy/fallback behavior regressions."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

LEGACY_ROOT_DIRS = ("v4", "v5")


@dataclass(frozen=True)
class AuditCheckResult:
    name: str
    ok: bool
    detail: str


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def _check_legacy_pipeline_mode_rejected(compile_script: Path) -> AuditCheckResult:
    run = _run([sys.executable, str(compile_script), "--pipeline-mode", "legacy"])
    ok = run.returncode != 0 and "invalid choice" in (run.stderr or "")
    detail = (run.stdout + "\n" + run.stderr).strip()
    return AuditCheckResult(name="legacy_pipeline_mode_rejected", ok=ok, detail=detail)


def _check_disable_plugins_flag_retired(compile_script: Path) -> AuditCheckResult:
    run = _run([sys.executable, str(compile_script), "--disable-plugins"])
    ok = run.returncode != 0 and "unrecognized arguments" in (run.stderr or "")
    detail = (run.stdout + "\n" + run.stderr).strip()
    return AuditCheckResult(name="disable_plugins_flag_retired", ok=ok, detail=detail)


def _check_legacy_paths_rejected(compile_script: Path) -> AuditCheckResult:
    with tempfile.TemporaryDirectory(prefix="strict-audit-paths-") as tmp_dir:
        repo_root = Path(tmp_dir).resolve()
        topology_path = repo_root / "topology" / "topology.yaml"
        error_catalog = repo_root / "topology-tools" / "data" / "error-catalog.yaml"
        _write_yaml(
            topology_path,
            {
                "version": "5.0.0",
                "model": "class-object-instance",
                "paths": {
                    "class_modules_root": "topology/class-modules",
                    "object_modules_root": "topology/object-modules",
                },
            },
        )
        _write_yaml(error_catalog, {"version": 1, "tool": "topology-compiler", "codes": {}})
        run = _run(
            [
                sys.executable,
                str(compile_script),
                "--repo-root",
                str(repo_root),
                "--topology",
                str(topology_path),
                "--error-catalog",
                str(error_catalog),
                "--output-json",
                str(repo_root / "build" / "effective.json"),
                "--diagnostics-json",
                str(repo_root / "build" / "diagnostics.json"),
                "--diagnostics-txt",
                str(repo_root / "build" / "diagnostics.txt"),
            ]
        )
        diagnostics_text = ""
        diag_path = repo_root / "build" / "diagnostics.txt"
        if diag_path.exists():
            diagnostics_text = diag_path.read_text(encoding="utf-8", errors="ignore")
        merged = "\n".join([run.stdout, run.stderr, diagnostics_text]).strip()
        ok = run.returncode != 0 and "E7808" in merged
        return AuditCheckResult(name="legacy_paths_rejected_e7808", ok=ok, detail=merged)


def _check_missing_lock_rejected(verify_script: Path) -> AuditCheckResult:
    with tempfile.TemporaryDirectory(prefix="strict-audit-lock-") as tmp_dir:
        repo_root = Path(tmp_dir).resolve()
        topology_path = repo_root / "topology" / "topology.yaml"
        framework_manifest = repo_root / "topology" / "framework.yaml"
        project_manifest = repo_root / "projects" / "home-lab" / "project.yaml"
        _write_yaml(
            framework_manifest,
            {
                "schema_version": 1,
                "framework_id": "infra-topology-framework",
                "framework_api_version": "5.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {"layout_version": 1, "include": ["topology/framework.yaml"]},
            },
        )
        _write_yaml(
            topology_path,
            {
                "version": "5.0.0",
                "model": "class-object-instance",
                "framework": {
                    "class_modules_root": "topology/class-modules",
                    "object_modules_root": "topology/object-modules",
                    "model_lock": "topology/model.lock.yaml",
                    "profile_map": "topology/profile-map.yaml",
                    "layer_contract": "topology/layer-contract.yaml",
                    "capability_catalog": "topology/class-modules/L1-foundation/router/capability-catalog.yaml",
                    "capability_packs": "topology/class-modules/L1-foundation/router/capability-packs.yaml",
                },
                "project": {"active": "home-lab", "projects_root": "projects"},
            },
        )
        _write_yaml(
            project_manifest,
            {
                "schema_version": 1,
                "project_schema_version": "1.0.0",
                "project": "home-lab",
                "project_min_framework_version": "5.0.0",
                "project_contract_revision": 1,
                "instances_root": "topology/instances",
                "secrets_root": "secrets",
            },
        )
        run = _run(
            [
                sys.executable,
                str(verify_script),
                "--repo-root",
                str(repo_root),
                "--topology",
                str(topology_path),
                "--strict",
            ]
        )
        merged = "\n".join([run.stdout, run.stderr]).strip()
        ok = run.returncode != 0 and "E7822" in merged
        return AuditCheckResult(name="missing_lock_rejected_e7822", ok=ok, detail=merged)


def _check_no_legacy_root_dirs(repo_root: Path) -> AuditCheckResult:
    present = [name for name in LEGACY_ROOT_DIRS if (repo_root / name).exists()]
    if present:
        joined = ", ".join(present)
        return AuditCheckResult(
            name="no_legacy_root_dirs",
            ok=False,
            detail=f"Legacy root directories detected: {joined}",
        )
    return AuditCheckResult(name="no_legacy_root_dirs", ok=True, detail="Legacy root directories absent.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit strict-only runtime entrypoint behavior.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root where topology tools are located.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    compile_script = repo_root / "topology-tools" / "compile-topology.py"
    verify_script = repo_root / "topology-tools" / "verify-framework-lock.py"

    checks = [
        _check_no_legacy_root_dirs(repo_root),
        _check_legacy_pipeline_mode_rejected(compile_script),
        _check_disable_plugins_flag_retired(compile_script),
        _check_legacy_paths_rejected(compile_script),
        _check_missing_lock_rejected(verify_script),
    ]
    failed = [item for item in checks if not item.ok]
    for item in checks:
        status = "PASS" if item.ok else "FAIL"
        print(f"- {item.name}: {status}")
        if not item.ok:
            print(item.detail)

    if failed:
        print(f"Strict runtime audit failed: {len(failed)} check(s)")
        return 1

    print("Strict runtime audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
