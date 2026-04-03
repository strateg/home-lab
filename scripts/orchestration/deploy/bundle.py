"""
ADR 0085 Phase 2: deploy bundle assembly.

Bundle layout:
    .work/deploy/bundles/<bundle_id>/
      manifest.yaml
      metadata.yaml
      artifacts/
      checksums.sha256
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml

BUNDLE_SCHEMA_VERSION = "1.0"
CHECKSUM_FILE_NAME = "checksums.sha256"
MANIFEST_FILE_NAME = "manifest.yaml"
METADATA_FILE_NAME = "metadata.yaml"


class BundleError(RuntimeError):
    """Raised when bundle operations fail."""


@dataclass(frozen=True)
class BundleInfo:
    bundle_id: str
    bundle_path: Path
    created_at: str
    topology_hash: str
    secrets_hash: str
    existing: bool = False


def resolve_bundles_root(repo_root: Path) -> Path:
    return (repo_root.resolve() / ".work" / "deploy" / "bundles").resolve()


def resolve_bundle_schema_path(repo_root: Path) -> Path:
    return (repo_root.resolve() / "schemas" / "deploy-bundle-manifest.schema.json").resolve()


def create_bundle(
    *,
    project_id: str,
    generated_root: Path,
    bundles_root: Path,
    inject_secrets: bool = False,
    secrets_root: Path | None = None,
) -> BundleInfo:
    generated = generated_root.resolve()
    bundles = bundles_root.resolve()

    if not generated.exists():
        raise FileNotFoundError(f"Generated root not found: {generated}")
    if not generated.is_dir():
        raise NotADirectoryError(f"Generated root is not a directory: {generated}")

    topology_hash = hash_tree(generated)
    decrypted_secrets = _decrypt_secrets(secrets_root.resolve()) if inject_secrets and secrets_root else {}
    secrets_hash = hash_mapping(decrypted_secrets)
    bundle_id = compute_bundle_id(project_id=project_id, topology_hash=topology_hash, secrets_hash=secrets_hash)
    bundle_path = bundles / bundle_id
    if bundle_path.exists():
        if not bundle_path.is_dir():
            raise FileExistsError(f"Bundle path exists and is not a directory: {bundle_path}")
        payload = inspect_bundle(bundle_path, verify_checksums=True)
        existing_created_at = str(payload.get("manifest", {}).get("created_at", ""))
        return BundleInfo(
            bundle_id=bundle_id,
            bundle_path=bundle_path,
            created_at=existing_created_at or utc_now(),
            topology_hash=topology_hash,
            secrets_hash=secrets_hash,
            existing=True,
        )

    bundles.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bundle-", dir=str(bundles)) as tmp_dir:
        tmp_bundle = Path(tmp_dir) / bundle_id
        tmp_bundle.mkdir(parents=True, exist_ok=True)

        artifacts_root = tmp_bundle / "artifacts"
        generated_artifacts_root = artifacts_root / "generated"
        shutil.copytree(generated, generated_artifacts_root)

        if decrypted_secrets:
            for rel_path, content in decrypted_secrets.items():
                target = artifacts_root / "secrets" / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

        created_at = utc_now()
        manifest = build_manifest(
            bundle_id=bundle_id,
            created_at=created_at,
            project_id=project_id,
            topology_hash=topology_hash,
            secrets_hash=secrets_hash,
            bundle_root=tmp_bundle,
        )
        metadata = build_metadata(
            bundle_id=bundle_id,
            created_at=created_at,
            project_id=project_id,
            generated_root=generated,
            secrets_root=secrets_root.resolve() if secrets_root else None,
            topology_hash=topology_hash,
            secrets_hash=secrets_hash,
        )

        manifest_path = tmp_bundle / MANIFEST_FILE_NAME
        metadata_path = tmp_bundle / METADATA_FILE_NAME
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
        write_checksums(tmp_bundle)

        # Temporary directory and destination are under the same parent; rename is atomic.
        tmp_bundle.rename(bundle_path)

    return BundleInfo(
        bundle_id=bundle_id,
        bundle_path=bundle_path,
        created_at=created_at,
        topology_hash=topology_hash,
        secrets_hash=secrets_hash,
    )


def list_bundles(bundles_root: Path) -> list[dict[str, Any]]:
    bundles = bundles_root.resolve()
    if not bundles.exists():
        return []

    result: list[dict[str, Any]] = []
    for path in sorted((item for item in bundles.iterdir() if item.is_dir()), key=lambda p: p.name):
        manifest_path = path / MANIFEST_FILE_NAME
        metadata_path = path / METADATA_FILE_NAME
        if not manifest_path.exists() or not metadata_path.exists():
            continue
        manifest = _load_yaml_mapping(manifest_path)
        metadata = _load_yaml_mapping(metadata_path)
        result.append(
            {
                "bundle_id": str(manifest.get("bundle_id", path.name)),
                "created_at": str(manifest.get("created_at", metadata.get("created_at", ""))),
                "path": str(path),
                "project": str(manifest.get("source", {}).get("project", metadata.get("project", ""))),
            }
        )
    return result


def inspect_bundle(bundle_path: Path, *, verify_checksums: bool = True) -> dict[str, Any]:
    root = bundle_path.resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Bundle not found: {root}")

    manifest = _load_yaml_mapping(root / MANIFEST_FILE_NAME)
    metadata = _load_yaml_mapping(root / METADATA_FILE_NAME)
    checksums_ok, mismatches = verify_bundle_checksums(root)
    if verify_checksums and not checksums_ok:
        raise BundleError(f"Bundle checksum verification failed: {root}: {', '.join(mismatches)}")

    return {
        "bundle_id": str(manifest.get("bundle_id", root.name)),
        "path": str(root),
        "manifest": manifest,
        "metadata": metadata,
        "checksums_ok": checksums_ok,
        "checksum_mismatches": mismatches,
        "files_count": len(_iter_bundle_files(root)),
    }


def delete_bundle(bundle_path: Path) -> None:
    root = bundle_path.resolve()
    if not root.exists():
        return
    if not root.is_dir():
        raise NotADirectoryError(f"Bundle path is not directory: {root}")
    shutil.rmtree(root)


def build_manifest(
    *,
    bundle_id: str,
    created_at: str,
    project_id: str,
    topology_hash: str,
    secrets_hash: str,
    bundle_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "created_at": created_at,
        "source": {
            "project": project_id,
            "topology_hash": topology_hash,
            "secrets_hash": secrets_hash,
        },
        "nodes": _derive_nodes(bundle_root),
    }


def build_metadata(
    *,
    bundle_id: str,
    created_at: str,
    project_id: str,
    generated_root: Path,
    secrets_root: Path | None,
    topology_hash: str,
    secrets_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "created_at": created_at,
        "project": project_id,
        "generated_root": str(generated_root),
        "secrets_root": str(secrets_root) if secrets_root else "",
        "topology_hash": topology_hash,
        "secrets_hash": secrets_hash,
    }


def write_checksums(bundle_root: Path) -> None:
    root = bundle_root.resolve()
    entries: list[tuple[str, str]] = []
    for file_path in _iter_bundle_files(root):
        rel = file_path.relative_to(root).as_posix()
        entries.append((sha256_file(file_path), rel))
    entries.sort(key=lambda item: item[1])
    output = "\n".join(f"{digest}  {rel}" for digest, rel in entries) + "\n"
    (root / CHECKSUM_FILE_NAME).write_text(output, encoding="utf-8")


def verify_bundle_checksums(bundle_root: Path) -> tuple[bool, list[str]]:
    root = bundle_root.resolve()
    checksum_path = root / CHECKSUM_FILE_NAME
    if not checksum_path.exists():
        return False, [f"missing:{CHECKSUM_FILE_NAME}"]

    mismatches: list[str] = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item:
            continue
        digest, _, rel = item.partition("  ")
        if not digest or not rel:
            mismatches.append(f"malformed:{item}")
            continue
        file_path = root / rel
        if not file_path.exists():
            mismatches.append(f"missing:{rel}")
            continue
        actual = sha256_file(file_path)
        if actual != digest:
            mismatches.append(f"mismatch:{rel}")
    return len(mismatches) == 0, mismatches


def compute_bundle_id(*, project_id: str, topology_hash: str, secrets_hash: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(project_id.encode("utf-8"))
    hasher.update(b"\n")
    hasher.update(topology_hash.encode("utf-8"))
    hasher.update(b"\n")
    hasher.update(secrets_hash.encode("utf-8"))
    hasher.update(b"\n")
    hasher.update(BUNDLE_SCHEMA_VERSION.encode("utf-8"))
    return f"b-{hasher.hexdigest()[:12]}"


def hash_tree(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()), key=lambda p: p.relative_to(root).as_posix()
    ):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        hasher.update(rel)
        hasher.update(b"\0")
        hasher.update(sha256_file(path).encode("utf-8"))
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def hash_mapping(values: dict[str, str]) -> str:
    hasher = hashlib.sha256()
    for key, value in sorted(values.items(), key=lambda item: item[0]):
        hasher.update(key.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def load_bundle_manifest_schema(schema_path: Path) -> dict[str, Any]:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Bundle schema root must be object: {schema_path}")
    return payload


def validate_bundle_manifest(manifest_path: Path, schema_path: Path) -> None:
    schema = load_bundle_manifest_schema(schema_path.resolve())
    payload = _load_yaml_mapping(manifest_path.resolve())
    validator = jsonschema.validators.validator_for(schema)(schema)
    try:
        validator.validate(payload)
    except jsonschema.ValidationError as exc:
        raise BundleError(f"Bundle manifest validation failed for {manifest_path}: {exc.message}") from exc


def resolve_bundle_path(bundles_root: Path, bundle_ref: str) -> Path:
    candidate = Path(bundle_ref)
    if candidate.is_absolute() or candidate.exists():
        return candidate.resolve()
    return (bundles_root.resolve() / bundle_ref).resolve()


def _derive_nodes(bundle_root: Path) -> list[dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    node_mechanisms: dict[str, set[str]] = {}
    bootstrap_root = bundle_root / "artifacts" / "generated" / "bootstrap"
    if not bootstrap_root.exists():
        return []
    for file_path in sorted((item for item in bootstrap_root.rglob("*") if item.is_file()), key=lambda p: p.as_posix()):
        rel = file_path.relative_to(bundle_root).as_posix()
        bootstrap_rel = file_path.relative_to(bootstrap_root)
        if len(bootstrap_rel.parts) < 1:
            continue
        node_id = bootstrap_rel.parts[0]
        mechanism = _infer_mechanism_from_artifact(bootstrap_rel)
        entry = nodes.setdefault(
            node_id,
            {
                "id": node_id,
                "mechanism": "unknown",
                "artifacts": [],
            },
        )
        if mechanism != "unknown":
            node_mechanisms.setdefault(node_id, set()).add(mechanism)
        entry["artifacts"].append(
            {
                "path": rel,
                "checksum": f"sha256:{sha256_file(file_path)}",
            }
        )
    for node_id, entry in nodes.items():
        mechanisms = sorted(node_mechanisms.get(node_id, set()))
        if len(mechanisms) == 1:
            entry["mechanism"] = mechanisms[0]
        elif len(mechanisms) > 1:
            entry["mechanism"] = "mixed"
    return [nodes[key] for key in sorted(nodes.keys())]


def _infer_mechanism_from_artifact(bootstrap_rel: Path) -> str:
    parts = bootstrap_rel.parts
    if len(parts) > 2:
        return parts[1]
    leaf = parts[-1].lower() if parts else ""
    root_file_map = {
        "answer.toml": "unattended_install",
        "answer.toml.example": "unattended_install",
        "post-install-minimal.sh": "unattended_install",
        "user-data": "cloud_init",
        "meta-data": "cloud_init",
        "network-config": "cloud_init",
    }
    mapped = root_file_map.get(leaf)
    if mapped:
        return mapped
    if leaf.endswith(".rsc"):
        return "netinstall"
    return "unknown"


def _decrypt_secrets(secrets_root: Path) -> dict[str, str]:
    if not secrets_root.exists():
        return {}
    if not secrets_root.is_dir():
        raise NotADirectoryError(f"Secrets root is not directory: {secrets_root}")

    decrypted: dict[str, str] = {}
    candidates = sorted(
        [
            item
            for item in secrets_root.rglob("*")
            if item.is_file()
            and item.suffix.lower() in {".yaml", ".yml"}
            and item.name.lower() not in {".sops.yaml", ".sops.yml"}
        ],
        key=lambda path: path.relative_to(secrets_root).as_posix(),
    )
    for path in candidates:
        proc = subprocess.run(
            ["sops", "--decrypt", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise BundleError(
                f"Failed to decrypt secret file '{path}': sops exit={proc.returncode}. {(proc.stderr or '').strip()}"
            )
        decrypted[path.relative_to(secrets_root).as_posix()] = proc.stdout or ""
    return decrypted


def _iter_bundle_files(bundle_root: Path) -> list[Path]:
    return sorted(
        [
            item
            for item in bundle_root.rglob("*")
            if item.is_file() and item.name != CHECKSUM_FILE_NAME and ".tmp" not in item.parts
        ],
        key=lambda p: p.relative_to(bundle_root).as_posix(),
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping/object: {path}")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy bundle operations (ADR 0085 Phase 2).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create immutable deploy bundle from generated artifacts.")
    create.add_argument("--repo-root", default=".")
    create.add_argument("--project-id", default="home-lab")
    create.add_argument("--generated-root", default="")
    create.add_argument("--bundles-root", default="")
    create.add_argument("--inject-secrets", action="store_true")
    create.add_argument("--secrets-root", default="")

    list_cmd = subparsers.add_parser("list", help="List available deploy bundles.")
    list_cmd.add_argument("--repo-root", default=".")
    list_cmd.add_argument("--bundles-root", default="")

    inspect = subparsers.add_parser("inspect", help="Inspect bundle metadata and verify checksums.")
    inspect.add_argument("--repo-root", default=".")
    inspect.add_argument("--bundles-root", default="")
    inspect.add_argument("--bundle", required=True, help="Bundle id or absolute bundle path.")
    inspect.add_argument("--skip-checksums", action="store_true")

    delete = subparsers.add_parser("delete", help="Delete existing deploy bundle.")
    delete.add_argument("--repo-root", default=".")
    delete.add_argument("--bundles-root", default="")
    delete.add_argument("--bundle", required=True, help="Bundle id or absolute bundle path.")

    return parser.parse_args(argv)


def _resolved_bundles_root(*, repo_root: Path, bundles_root_raw: str) -> Path:
    if bundles_root_raw.strip():
        return Path(bundles_root_raw.strip()).resolve()
    return resolve_bundles_root(repo_root)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    bundles_root = _resolved_bundles_root(repo_root=repo_root, bundles_root_raw=getattr(args, "bundles_root", ""))

    if args.command == "create":
        generated_root = (
            Path(args.generated_root).resolve()
            if args.generated_root.strip()
            else (repo_root / "generated" / args.project_id).resolve()
        )
        secrets_root = (
            Path(args.secrets_root).resolve()
            if args.secrets_root.strip()
            else (repo_root / "projects" / args.project_id / "secrets").resolve()
        )
        info = create_bundle(
            project_id=args.project_id,
            generated_root=generated_root,
            bundles_root=bundles_root,
            inject_secrets=bool(args.inject_secrets),
            secrets_root=secrets_root,
        )
        print(
            json.dumps(
                {
                    "bundle_id": info.bundle_id,
                    "bundle_path": str(info.bundle_path),
                    "existing": bool(info.existing),
                },
                ensure_ascii=True,
            )
        )
        return 0

    if args.command == "list":
        print(json.dumps({"bundles": list_bundles(bundles_root)}, ensure_ascii=True, indent=2))
        return 0

    if args.command == "inspect":
        bundle_path = resolve_bundle_path(bundles_root, args.bundle)
        payload = inspect_bundle(bundle_path, verify_checksums=not bool(args.skip_checksums))
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    if args.command == "delete":
        bundle_path = resolve_bundle_path(bundles_root, args.bundle)
        delete_bundle(bundle_path)
        print(json.dumps({"deleted": str(bundle_path)}, ensure_ascii=True))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
