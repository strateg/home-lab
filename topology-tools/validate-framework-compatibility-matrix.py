#!/usr/bin/env python3
"""Validate framework/project compatibility matrix using strict lock verifier."""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml
from framework_lock import _git_revision, _load_yaml, resolve_paths, verify_framework_lock


@dataclass(frozen=True)
class MatrixCase:
    name: str
    mutate: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]
    expected_error_codes: set[str]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_topology() -> Path:
    return _default_repo_root() / "topology" / "topology.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate strict compatibility matrix for framework/project contracts."
    )
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


def _mutate_noop(_: dict[str, Any], __: dict[str, Any], ___: dict[str, Any]) -> None:
    return


def _mutate_framework_too_old(_: dict[str, Any], project_manifest: dict[str, Any], __: dict[str, Any]) -> None:
    project_manifest["project_min_framework_version"] = "99.0.0"


def _mutate_framework_too_new(_: dict[str, Any], project_manifest: dict[str, Any], __: dict[str, Any]) -> None:
    project_manifest["project_max_framework_version"] = "0.0.1"


def _mutate_project_schema_unsupported(_: dict[str, Any], project_manifest: dict[str, Any], __: dict[str, Any]) -> None:
    project_manifest["project_schema_version"] = "9.0.0"


def _mutate_contract_revision_required(
    _: dict[str, Any], project_manifest: dict[str, Any], lock_payload: dict[str, Any]
) -> None:
    project_manifest["project_contract_revision"] = 3
    lock_payload["project_contract_revision"] = 1


def _mutate_missing_lock(_: dict[str, Any], __: dict[str, Any], ___: dict[str, Any]) -> None:
    return


def _matrix_cases() -> list[MatrixCase]:
    return [
        MatrixCase(name="baseline_ok", mutate=_mutate_noop, expected_error_codes=set()),
        MatrixCase(name="framework_too_old", mutate=_mutate_framework_too_old, expected_error_codes={"E7811"}),
        MatrixCase(name="framework_too_new", mutate=_mutate_framework_too_new, expected_error_codes={"E7811"}),
        MatrixCase(
            name="project_schema_unsupported", mutate=_mutate_project_schema_unsupported, expected_error_codes={"E7812"}
        ),
        MatrixCase(
            name="contract_revision_required", mutate=_mutate_contract_revision_required, expected_error_codes={"E7813"}
        ),
        MatrixCase(name="missing_lock", mutate=_mutate_missing_lock, expected_error_codes={"E7822"}),
    ]


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _run_case(
    *,
    case: MatrixCase,
    baseline_paths: Any,
    framework_manifest_payload: dict[str, Any],
    project_manifest_payload: dict[str, Any],
    lock_payload: dict[str, Any],
) -> tuple[bool, set[str], list[str]]:
    with tempfile.TemporaryDirectory(prefix=f"framework-matrix-{case.name}-") as tmp_dir:
        temp_root = Path(tmp_dir).resolve()
        temp_framework_manifest = temp_root / "framework.yaml"
        temp_project_manifest = temp_root / "project" / "project.yaml"
        temp_lock = temp_root / "project" / "framework.lock.yaml"

        framework_payload = dict(framework_manifest_payload)
        project_payload = dict(project_manifest_payload)
        lock_copy = dict(lock_payload)
        case.mutate(framework_payload, project_payload, lock_copy)
        if case.name != "missing_lock":
            framework_block = lock_copy.get("framework")
            current_revision = _git_revision(baseline_paths.framework_root)
            if isinstance(framework_block, dict) and isinstance(current_revision, str) and current_revision:
                framework_block["revision"] = current_revision

        _write_yaml(temp_framework_manifest, framework_payload)
        _write_yaml(temp_project_manifest, project_payload)
        if case.name != "missing_lock":
            _write_yaml(temp_lock, lock_copy)

        temp_paths = resolve_paths(
            repo_root=baseline_paths.repo_root,
            topology_path=None,
            project_id=baseline_paths.project_id,
            project_root=temp_project_manifest.parent,
            project_manifest_path=temp_project_manifest,
            framework_root=baseline_paths.framework_root,
            framework_manifest_path=temp_framework_manifest,
            lock_path=temp_lock,
        )
        result = verify_framework_lock(paths=temp_paths, strict=True)
        actual_errors = {item.code for item in result.diagnostics if item.severity == "error"}
        expected = case.expected_error_codes
        ok = result.ok if not expected else (not result.ok and expected.issubset(actual_errors))
        diag_rows = [f"{item.severity.upper()} {item.code}: {item.message}" for item in result.diagnostics]
        return ok, actual_errors, diag_rows


def main() -> int:
    args = parse_args()
    topology_path = args.topology if isinstance(args.topology, Path) and args.topology.exists() else None
    baseline_paths = resolve_paths(
        repo_root=args.repo_root,
        topology_path=topology_path,
        project_id=args.project,
        project_root=args.project_root,
        project_manifest_path=args.project_manifest,
        framework_root=args.framework_root,
        framework_manifest_path=args.framework_manifest,
        lock_path=args.lock_file,
    )
    if not baseline_paths.lock_path.exists():
        print(f"ERROR: lock file is missing: {baseline_paths.lock_path}")
        return 2

    framework_manifest_payload = _load_yaml(baseline_paths.framework_manifest_path)
    project_manifest_payload = _load_yaml(baseline_paths.project_manifest_path)
    lock_payload = _load_yaml(baseline_paths.lock_path)

    failures: list[str] = []
    print("Framework compatibility matrix:")
    for case in _matrix_cases():
        ok, actual_errors, diag_rows = _run_case(
            case=case,
            baseline_paths=baseline_paths,
            framework_manifest_payload=framework_manifest_payload,
            project_manifest_payload=project_manifest_payload,
            lock_payload=lock_payload,
        )
        expected = sorted(case.expected_error_codes)
        got = sorted(actual_errors)
        status = "PASS" if ok else "FAIL"
        print(f"- {case.name}: {status} expected={expected} got={got}")
        if not ok:
            failures.append(case.name)
            for row in diag_rows:
                print(f"  {row}")

    if failures:
        print(f"Compatibility matrix failed: {', '.join(failures)}")
        return 1

    print("Compatibility matrix: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
