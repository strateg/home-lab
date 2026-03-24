#!/usr/bin/env python3
"""Generate framework.lock.yaml for project repositories."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from framework_lock import _git_remote, _git_revision, _load_yaml, compute_framework_integrity, resolve_paths


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_topology() -> Path:
    return _default_repo_root() / "v5" / "topology" / "topology.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate framework.lock.yaml for active project.")
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
        help="Output lock file path (default: <project-root>/framework.lock.yaml).",
    )
    parser.add_argument(
        "--source",
        choices=("git", "local", "package"),
        default="git",
        help="Framework source type stored in lock.",
    )
    parser.add_argument(
        "--version",
        default="",
        help="Framework version override (default: framework_api_version from framework manifest).",
    )
    parser.add_argument(
        "--repository",
        default="",
        help="Repository URL override for source=git.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing lock file.",
    )
    return parser.parse_args()


def _build_lock_payload(
    *,
    framework_manifest: dict[str, Any],
    project_manifest: dict[str, Any],
    source: str,
    version_override: str,
    revision: str | None,
    repository_override: str,
    repository_detected: str | None,
    integrity: str,
) -> dict[str, Any]:
    framework_id = str(framework_manifest.get("framework_id", "")).strip()
    framework_version = version_override.strip() or str(framework_manifest.get("framework_api_version", "")).strip()
    project_schema_version = str(project_manifest.get("project_schema_version", "")).strip()
    project_contract_revision = project_manifest.get("project_contract_revision", 0)
    repository = repository_override.strip() or (repository_detected or "")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "project_schema_version": project_schema_version,
        "project_contract_revision": project_contract_revision if isinstance(project_contract_revision, int) else 0,
        "framework": {
            "id": framework_id,
            "version": framework_version,
            "source": source,
            "repository": repository,
            "revision": revision or "UNKNOWN",
            "integrity": integrity,
        },
        "locked_at": datetime.now(UTC).isoformat(),
    }

    if source == "package":
        payload["framework"]["signature"] = {
            "issuer": "<REQUIRED_ISSUER>",
            "subject": "<REQUIRED_SUBJECT>",
            "verified": False,
        }
        payload["provenance"] = {
            "predicate_type": "<REQUIRED_PREDICATE_TYPE>",
            "uri": "<REQUIRED_PROVENANCE_URI>",
        }
        payload["sbom"] = {
            "format": "<REQUIRED_SBOM_FORMAT>",
            "uri": "<REQUIRED_SBOM_URI>",
        }

    return payload


def main() -> int:
    args = parse_args()
    paths = resolve_paths(
        repo_root=args.repo_root,
        topology_path=args.topology if isinstance(args.topology, Path) and args.topology.exists() else None,
        project_id=args.project,
        project_root=args.project_root,
        project_manifest_path=args.project_manifest,
        framework_root=args.framework_root,
        framework_manifest_path=args.framework_manifest,
        lock_path=args.lock_file,
    )

    if paths.lock_path.exists() and not args.force:
        print(f"ERROR: lock file already exists: {paths.lock_path} (use --force to overwrite)")
        return 2

    framework_manifest = _load_yaml(paths.framework_manifest_path)
    project_manifest = _load_yaml(paths.project_manifest_path)
    integrity = compute_framework_integrity(
        framework_root=paths.framework_root,
        framework_manifest=framework_manifest,
    )
    revision = _git_revision(paths.framework_root)
    repository = _git_remote(paths.framework_root)
    payload = _build_lock_payload(
        framework_manifest=framework_manifest,
        project_manifest=project_manifest,
        source=args.source,
        version_override=args.version,
        revision=revision,
        repository_override=args.repository,
        repository_detected=repository,
        integrity=integrity,
    )

    paths.lock_path.parent.mkdir(parents=True, exist_ok=True)
    paths.lock_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    print(f"Generated framework lock: {paths.lock_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
