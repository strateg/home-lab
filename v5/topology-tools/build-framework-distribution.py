#!/usr/bin/env python3
"""Build framework distribution archives from framework manifest."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BuildConfig:
    repo_root: Path
    framework_manifest: Path
    output_root: Path
    version: str
    archive_format: str
    keep_staging: bool


def _default_repo_root() -> Path:
    tools_dir = Path(__file__).resolve().parent
    parent = tools_dir.parent
    if (parent / "framework.yaml").exists():
        return parent
    if parent.name == "v5":
        return parent.parent
    return parent.parent


def _default_framework_manifest() -> Path:
    repo_root = _default_repo_root()
    extracted_manifest = repo_root / "framework.yaml"
    if extracted_manifest.exists():
        return extracted_manifest
    return repo_root / "v5" / "topology" / "framework.yaml"


def _default_output_root() -> Path:
    repo_root = _default_repo_root()
    if (repo_root / "v5").exists():
        return repo_root / "v5-dist" / "framework"
    return repo_root / "dist" / "framework"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping/object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _is_excluded(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _collect_sources(
    *,
    repo_root: Path,
    includes: list[str],
    excludes: list[str],
) -> list[Path]:
    collected: list[Path] = []
    seen: set[str] = set()

    for include in includes:
        include_path = (repo_root / include).resolve()
        if not include_path.exists():
            raise FileNotFoundError(f"Included path does not exist: {include}")
        if include_path.is_file():
            rel = include_path.relative_to(repo_root).as_posix()
            if _is_excluded(rel, excludes):
                continue
            if rel not in seen:
                collected.append(include_path)
                seen.add(rel)
            continue
        for path in sorted(include_path.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_root).as_posix()
            if _is_excluded(rel, excludes):
                continue
            if rel in seen:
                continue
            collected.append(path)
            seen.add(rel)
    return collected


def _copy_sources_to_staging(
    *,
    repo_root: Path,
    staging_root: Path,
    sources: list[Path],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in sources:
        rel = source.relative_to(repo_root)
        target = staging_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        result.append(
            {
                "path": rel.as_posix(),
                "size": target.stat().st_size,
                "sha256": _sha256_file(target),
            }
        )
    result.sort(key=lambda item: str(item["path"]))
    return result


def _write_manifest(
    *,
    output_dir: Path,
    framework_payload: dict[str, Any],
    version: str,
    files: list[dict[str, Any]],
) -> Path:
    manifest_path = output_dir / "framework-dist-manifest.json"
    payload = {
        "schema_version": 1,
        "framework_id": framework_payload.get("framework_id"),
        "framework_api_version": framework_payload.get("framework_api_version"),
        "framework_release_channel": framework_payload.get("framework_release_channel"),
        "supported_project_schema_range": framework_payload.get("supported_project_schema_range"),
        "distribution_version": version,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "files": files,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return manifest_path


def _build_zip(*, staging_root: Path, archive_path: Path, archive_prefix: str) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(staging_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(staging_root).as_posix()
            handle.write(path, arcname=f"{archive_prefix}/{rel}")


def _build_tar_gz(*, staging_root: Path, archive_path: Path, archive_prefix: str) -> None:
    with tarfile.open(archive_path, "w:gz") as handle:
        for path in sorted(staging_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(staging_root).as_posix()
            handle.add(path, arcname=f"{archive_prefix}/{rel}")


def _write_checksums(*, output_dir: Path, archives: list[Path]) -> Path:
    checksum_path = output_dir / "checksums.sha256"
    lines = [f"{_sha256_file(path)}  {path.name}" for path in archives]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def build_distribution(config: BuildConfig) -> int:
    framework_payload = _load_yaml(config.framework_manifest)
    framework_id = framework_payload.get("framework_id")
    if not isinstance(framework_id, str) or not framework_id.strip():
        raise ValueError("framework.yaml must contain non-empty framework_id")

    distribution_payload = framework_payload.get("distribution")
    if not isinstance(distribution_payload, dict):
        raise ValueError("framework.yaml must contain mapping 'distribution'")

    includes = distribution_payload.get("include")
    if not isinstance(includes, list) or not includes:
        raise ValueError("distribution.include must be non-empty list")
    include_values = [str(item).strip() for item in includes if isinstance(item, str) and item.strip()]
    if not include_values:
        raise ValueError("distribution.include contains no valid paths")

    excludes_raw = distribution_payload.get("exclude_globs", [])
    excludes = [str(item).strip() for item in excludes_raw if isinstance(item, str) and item.strip()]

    sources = _collect_sources(
        repo_root=config.repo_root,
        includes=include_values,
        excludes=excludes,
    )
    if not sources:
        raise ValueError("No files selected for distribution build")

    release_dir = config.output_root / framework_id / config.version
    staging_root = release_dir / "_staging_payload"
    archive_prefix = f"{framework_id}-{config.version}"

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    staging_root.mkdir(parents=True, exist_ok=True)

    files = _copy_sources_to_staging(
        repo_root=config.repo_root,
        staging_root=staging_root,
        sources=sources,
    )
    _write_manifest(
        output_dir=release_dir,
        framework_payload=framework_payload,
        version=config.version,
        files=files,
    )

    archives: list[Path] = []
    if config.archive_format in {"zip", "both"}:
        zip_path = release_dir / f"{archive_prefix}.zip"
        _build_zip(staging_root=staging_root, archive_path=zip_path, archive_prefix=archive_prefix)
        archives.append(zip_path)
    if config.archive_format in {"tar.gz", "both"}:
        tar_path = release_dir / f"{archive_prefix}.tar.gz"
        _build_tar_gz(staging_root=staging_root, archive_path=tar_path, archive_prefix=archive_prefix)
        archives.append(tar_path)

    _write_checksums(output_dir=release_dir, archives=archives)

    if not config.keep_staging:
        shutil.rmtree(staging_root)

    print(
        f"Framework distribution built: id={framework_id} version={config.version} "
        f"files={len(files)} output={release_dir}"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build framework distribution archives.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root used for include path resolution.",
    )
    parser.add_argument(
        "--framework-manifest",
        type=Path,
        default=_default_framework_manifest(),
        help="Path to framework.yaml.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_default_output_root(),
        help="Root directory for distribution artifacts.",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Distribution version (for example: 1.0.0 or 2026.03.20-dev).",
    )
    parser.add_argument(
        "--archive-format",
        choices=("zip", "tar.gz", "both"),
        default="both",
        help="Archive format to build.",
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Keep staging payload directory for inspection.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = BuildConfig(
        repo_root=args.repo_root.resolve(),
        framework_manifest=args.framework_manifest.resolve(),
        output_root=args.output_root.resolve(),
        version=str(args.version).strip(),
        archive_format=str(args.archive_format),
        keep_staging=bool(args.keep_staging),
    )
    return build_distribution(config)


if __name__ == "__main__":
    raise SystemExit(main())
