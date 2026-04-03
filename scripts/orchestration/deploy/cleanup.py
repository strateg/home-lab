#!/usr/bin/env python3
"""Deploy-plane cleanup utilities."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class BundleEntry:
    path: Path
    project: str
    created_at: str


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _iter_bundle_entries(*, bundles_root: Path, project_id: str) -> list[BundleEntry]:
    if not bundles_root.exists():
        return []

    entries: list[BundleEntry] = []
    for bundle_dir in bundles_root.iterdir():
        if not bundle_dir.is_dir():
            continue
        manifest_path = bundle_dir / "manifest.yaml"
        if not manifest_path.exists():
            continue
        manifest = _load_yaml(manifest_path)
        source = manifest.get("source", {})
        project = str(source.get("project", ""))
        if project_id and project != project_id:
            continue
        created_at = str(manifest.get("created_at", ""))
        entries.append(BundleEntry(path=bundle_dir.resolve(), project=project, created_at=created_at))
    entries.sort(key=lambda item: (item.created_at, item.path.name), reverse=True)
    return entries


def _remove_path(path: Path, *, dry_run: bool) -> bool:
    if not path.exists():
        return False
    if dry_run:
        return True
    if path.is_dir():
        shutil.rmtree(path)
        return True
    path.unlink()
    return True


def _ensure_dir(path: Path, *, dry_run: bool) -> bool:
    if path.exists():
        return False
    if dry_run:
        return True
    path.mkdir(parents=True, exist_ok=True)
    return True


def _require_confirmation(*, dry_run: bool, confirm: bool) -> None:
    if dry_run:
        return
    if not confirm:
        raise ValueError("Destructive cleanup requires --confirm (or use --dry-run).")


def _cleanup_bundles(*, repo_root: Path, project_id: str, keep: int, dry_run: bool) -> dict[str, Any]:
    bundles_root = (repo_root / ".work" / "deploy" / "bundles").resolve()
    entries = _iter_bundle_entries(bundles_root=bundles_root, project_id=project_id)
    if keep < 0:
        raise ValueError("--keep must be >= 0")

    to_delete = entries[keep:]
    deleted: list[str] = []
    for entry in to_delete:
        if _remove_path(entry.path, dry_run=dry_run):
            deleted.append(str(entry.path))

    return {
        "command": "bundles",
        "project_id": project_id,
        "bundles_root": str(bundles_root),
        "dry_run": dry_run,
        "keep": keep,
        "total_project_bundles": len(entries),
        "deleted_count": len(deleted),
        "deleted": deleted,
    }


def _cleanup_state(*, repo_root: Path, project_id: str, dry_run: bool) -> dict[str, Any]:
    state_root = (repo_root / ".work" / "deploy-state" / project_id).resolve()
    state_exists = state_root.exists()
    removed = _remove_path(state_root, dry_run=dry_run)

    if dry_run and state_exists:
        recreated = {"project": True, "nodes": True, "logs": True}
    else:
        recreated = {
            "project": _ensure_dir(state_root, dry_run=dry_run),
            "nodes": _ensure_dir(state_root / "nodes", dry_run=dry_run),
            "logs": _ensure_dir(state_root / "logs", dry_run=dry_run),
        }

    return {
        "command": "state",
        "project_id": project_id,
        "state_root": str(state_root),
        "dry_run": dry_run,
        "removed": bool(removed),
        "recreated": recreated,
    }


def _cleanup_runner_workspace(*, repo_root: Path, project_id: str, dry_run: bool) -> dict[str, Any]:
    targets = [
        (repo_root / ".work" / "native" / project_id).resolve(),
        (repo_root / ".work" / "deploy" / "workspaces" / project_id).resolve(),
        (repo_root / ".work" / "deploy" / "runner-workspaces" / project_id).resolve(),
    ]
    removed: list[str] = []
    for target in targets:
        if _remove_path(target, dry_run=dry_run):
            removed.append(str(target))
    return {
        "command": "runner-workspace",
        "project_id": project_id,
        "dry_run": dry_run,
        "targets": [str(path) for path in targets],
        "removed_count": len(removed),
        "removed": removed,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy-plane cleanup commands.")
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--project-id", default="home-lab")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundles_cmd = subparsers.add_parser("bundles", help="Clean project bundles under .work/deploy/bundles.")
    bundles_cmd.add_argument("--keep", type=int, default=0, help="Keep newest N project bundles.")

    subparsers.add_parser("state", help="Reset deploy-state for project and recreate scaffold dirs.")
    subparsers.add_parser("runner-workspace", help="Clean local deploy runner workspace caches for project.")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    dry_run = bool(args.dry_run)
    _require_confirmation(dry_run=dry_run, confirm=bool(args.confirm))

    if args.command == "bundles":
        payload = _cleanup_bundles(
            repo_root=repo_root,
            project_id=str(args.project_id),
            keep=int(args.keep),
            dry_run=dry_run,
        )
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    if args.command == "state":
        payload = _cleanup_state(repo_root=repo_root, project_id=str(args.project_id), dry_run=dry_run)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    if args.command == "runner-workspace":
        payload = _cleanup_runner_workspace(repo_root=repo_root, project_id=str(args.project_id), dry_run=dry_run)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
