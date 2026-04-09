#!/usr/bin/env python3
"""Verify framework distribution artifact contents against ADR0081 runtime boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_REQUIRED_PATHS = {
    "framework.yaml",
    "topology/class-modules",
    "topology/object-modules",
    "topology/layer-contract.yaml",
    "topology/model.lock.yaml",
    "topology/profile-map.yaml",
    "topology/module-index.yaml",
    "topology/semantic-keywords.yaml",
    "topology-tools",
}

_FORBIDDEN_PREFIXES = (
    "tests/",
    "acceptance-testing/",
    "adr/",
    "docs/",
    "archive/",
    "projects/",
    "scripts/",
    "configs/",
    "generated/",
    "build/",
    "dist/",
    "taskfiles/",
    "topology-tools/docs/",
    "topology-tools/utils/",
    ".github/",
    ".claude/",
    ".codex/",
    ".idea/",
)


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify framework distribution content contract.")
    parser.add_argument("--dist-root", type=Path, default=Path("dist/framework"))
    parser.add_argument("--framework-id", default="infra-topology-framework")
    parser.add_argument("--version", default="")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("build/diagnostics/framework-artifact-contents.json"),
    )
    return parser.parse_args()


def _resolve_manifest(repo_root: Path, args: argparse.Namespace) -> Path:
    if isinstance(args.manifest, Path):
        return args.manifest if args.manifest.is_absolute() else repo_root / args.manifest

    dist_root = args.dist_root if args.dist_root.is_absolute() else repo_root / args.dist_root
    fw_dir = dist_root / str(args.framework_id).strip()
    if not fw_dir.exists():
        raise FileNotFoundError(f"framework dist directory not found: {fw_dir}")

    version = str(args.version).strip()
    if version:
        candidate = fw_dir / version / "framework-dist-manifest.json"
        if not candidate.exists():
            raise FileNotFoundError(f"manifest not found for version {version}: {candidate}")
        return candidate

    candidates = sorted(fw_dir.glob("*/framework-dist-manifest.json"))
    if not candidates:
        raise FileNotFoundError(f"no framework-dist-manifest.json found under: {fw_dir}")
    return candidates[-1]


def _has_path(files: set[str], required: str) -> bool:
    if required in files:
        return True
    prefix = required + "/"
    return any(path.startswith(prefix) for path in files)


def main() -> int:
    args = _parse_args()
    repo_root = _default_repo_root()
    output_json = args.output_json if args.output_json.is_absolute() else repo_root / args.output_json

    try:
        manifest_path = _resolve_manifest(repo_root, args)
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=True))
        return 2

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload.get("files", [])
    paths = {
        str(row.get("path", "")).strip()
        for row in files
        if isinstance(row, dict) and isinstance(row.get("path"), str) and str(row.get("path")).strip()
    }

    missing_required = sorted(req for req in _REQUIRED_PATHS if not _has_path(paths, req))
    forbidden_present = sorted(
        path for path in paths if any(path.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)
    )
    ok = not missing_required and not forbidden_present

    result = {
        "ok": ok,
        "manifest_path": str(manifest_path),
        "total_files": len(paths),
        "missing_required": missing_required,
        "forbidden_present": forbidden_present,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
