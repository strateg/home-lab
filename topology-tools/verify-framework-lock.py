#!/usr/bin/env python3
"""Verify framework.lock.yaml against framework/project contracts."""

from __future__ import annotations

import argparse
from pathlib import Path

from framework_lock import resolve_paths, verify_framework_lock


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_topology() -> Path:
    return _default_repo_root() / "topology" / "topology.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify framework lock contract.")
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
        help="Framework manifest path (default: auto-detect <framework-root>/topology/framework.yaml or <framework-root>/framework.yaml).",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=None,
        help="Lock file path (default: <project-root>/framework.lock.yaml).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing lock and package trust metadata as hard errors.",
    )
    return parser.parse_args()


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
    result = verify_framework_lock(paths=paths, strict=bool(args.strict))
    if not result.diagnostics:
        print("Framework lock verification: OK")
        return 0

    for diag in result.diagnostics:
        print(f"{diag.severity.upper()} {diag.code} {diag.path}: {diag.message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
