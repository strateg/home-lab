#!/usr/bin/env python3
"""Generate framework.lock.yaml for project repositories."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from framework_lock import _git_remote, _git_revision, _load_yaml, compute_framework_integrity, resolve_paths


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_topology() -> Path:
    return _default_repo_root() / "topology" / "topology.yaml"


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
    parser.add_argument(
        "--package-trust-release-root",
        type=Path,
        default=None,
        help="Optional release artifact root used to populate package trust metadata.",
    )
    parser.add_argument(
        "--package-signature-issuer",
        default="https://token.actions.githubusercontent.com",
        help="Signature issuer value for package source metadata.",
    )
    parser.add_argument(
        "--package-signature-subject",
        default="https://github.com/UNKNOWN/.github/workflows/release.yml@refs/tags/UNKNOWN",
        help="Signature subject value for package source metadata.",
    )
    parser.add_argument(
        "--package-signature-verified",
        action="store_true",
        help="Mark package signature metadata as verified.",
    )
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_existing(root: Path, candidates: list[str]) -> Path | None:
    for pattern in candidates:
        hits = sorted(root.rglob(pattern))
        if hits:
            return hits[0]
    return None


def _build_package_trust_payload(
    *,
    release_root: Path,
    signature_issuer: str,
    signature_subject: str,
    signature_verified: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    if not release_root.exists():
        return None
    signature_path = _first_existing(release_root, ["checksums.sha256.sig", "*.sigstore"])
    certificate_path = _first_existing(release_root, ["checksums.sha256.crt", "*.crt"])
    signed_blob_path = _first_existing(release_root, ["checksums.sha256"])
    provenance_path = _first_existing(release_root, ["provenance.json", "provenance/provenance.json"])
    sbom_path = _first_existing(release_root, ["sbom.spdx.json"])
    if (
        signature_path is None
        or certificate_path is None
        or signed_blob_path is None
        or provenance_path is None
        or sbom_path is None
    ):
        return None

    signature = {
        "issuer": signature_issuer.strip(),
        "subject": signature_subject.strip(),
        "verified": bool(signature_verified),
        "bundle_uri": signature_path.resolve().as_uri(),
        "bundle_sha256": _sha256_file(signature_path),
        "signature_uri": signature_path.resolve().as_uri(),
        "certificate_uri": certificate_path.resolve().as_uri(),
        "signed_blob_uri": signed_blob_path.resolve().as_uri(),
    }
    provenance = {
        "predicate_type": "https://slsa.dev/provenance/v1",
        "uri": provenance_path.resolve().as_uri(),
        "sha256": _sha256_file(provenance_path),
    }
    sbom = {
        "format": "spdx-json",
        "uri": sbom_path.resolve().as_uri(),
        "sha256": _sha256_file(sbom_path),
    }
    return signature, provenance, sbom


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
    package_trust: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None,
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
        if package_trust is not None:
            signature, provenance, sbom = package_trust
            payload["framework"]["signature"] = signature
            payload["provenance"] = provenance
            payload["sbom"] = sbom
        else:
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
    package_trust = (
        _build_package_trust_payload(
            release_root=args.package_trust_release_root.resolve(),
            signature_issuer=str(args.package_signature_issuer),
            signature_subject=str(args.package_signature_subject),
            signature_verified=bool(args.package_signature_verified),
        )
        if isinstance(args.package_trust_release_root, Path)
        else None
    )
    if (
        args.source == "package"
        and isinstance(args.package_trust_release_root, Path)
        and package_trust is None
    ):
        print(
            "ERROR: package trust release root does not contain required files "
            "(checksums.sha256, checksums.sha256.sig|*.sigstore, checksums.sha256.crt|*.crt, "
            "provenance.json, sbom.spdx.json)"
        )
        return 2

    payload = _build_lock_payload(
        framework_manifest=framework_manifest,
        project_manifest=project_manifest,
        source=args.source,
        version_override=args.version,
        revision=revision,
        repository_override=args.repository,
        repository_detected=repository,
        integrity=integrity,
        package_trust=package_trust,
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
