"""Framework lock generation and verification helpers (ADR 0076)."""

from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from yaml_loader import load_yaml_file

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
RANGE_TOKEN_RE = re.compile(r"^(>=|<=|>|<|==|=)?(0|[1-9]\d*\.[0-9]\d*\.[0-9]\d*)$")
PLACEHOLDER_TOKEN_RE = re.compile(r"^<[^>]+>$")


@dataclass(frozen=True)
class LockDiagnostic:
    code: str
    severity: str
    message: str
    path: str


@dataclass
class LockVerifyResult:
    ok: bool
    diagnostics: list[LockDiagnostic] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedPaths:
    repo_root: Path
    framework_root: Path
    framework_manifest_path: Path
    project_root: Path
    project_manifest_path: Path
    lock_path: Path
    project_id: str


def default_framework_manifest_path(framework_root: Path) -> Path:
    monorepo_manifest = framework_root / "topology" / "framework.yaml"
    extracted_manifest = framework_root / "framework.yaml"
    if monorepo_manifest.exists():
        return monorepo_manifest
    if extracted_manifest.exists():
        return extracted_manifest
    return monorepo_manifest


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = load_yaml_file(path) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping/object: {path}")
    return payload


def _parse_semver(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    match = SEMVER_RE.fullmatch(raw)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _compare_semver(a: str, b: str) -> int:
    sem_a = _parse_semver(a)
    sem_b = _parse_semver(b)
    if sem_a is None or sem_b is None:
        raise ValueError(f"Invalid semver compare: '{a}' vs '{b}'")
    if sem_a < sem_b:
        return -1
    if sem_a > sem_b:
        return 1
    return 0


def _satisfies_range(version: str, range_expr: str) -> bool:
    sem = _parse_semver(version)
    if sem is None:
        return False
    expression = str(range_expr).strip()
    if not expression:
        return True
    for token in expression.split():
        match = RANGE_TOKEN_RE.fullmatch(token)
        if match is None:
            return False
        op = match.group(1) or "=="
        target = match.group(2)
        cmp = _compare_semver(version, target)
        if op in {"==", "="} and cmp != 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<" and cmp >= 0:
            return False
        if op == ">=" and cmp < 0:
            return False
        if op == "<=" and cmp > 0:
            return False
    return True


def _git_revision(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    revision = (result.stdout or "").strip()
    return revision if revision else None


def _git_remote(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    remote = (result.stdout or "").strip()
    return remote if remote else None


def _git_toplevel(path: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    raw = (result.stdout or "").strip()
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except OSError:
        return None


def _read_canonical_file_bytes(path: Path) -> bytes:
    """Read file bytes with cross-platform text newline normalization.

    For text files (heuristic: no NUL byte), normalize line endings to LF so
    lock integrity stays stable across Windows/WSL checkouts.
    Binary files are hashed as-is.
    """

    data = path.read_bytes()
    if b"\x00" in data:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _canonical_file_row(path: Path) -> dict[str, Any]:
    normalized = _read_canonical_file_bytes(path)
    digest = hashlib.sha256(normalized).hexdigest()
    return {
        "size": len(normalized),
        "sha256": digest,
    }


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_placeholder_token(value: Any) -> bool:
    return isinstance(value, str) and PLACEHOLDER_TOKEN_RE.fullmatch(value.strip()) is not None


def _is_valid_uri(value: Any) -> bool:
    if not _is_non_empty_str(value):
        return False
    parsed = urlparse(str(value).strip())
    if not parsed.scheme:
        return False
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if parsed.scheme == "file":
        return bool(parsed.path)
    return bool(parsed.path or parsed.netloc)


def _is_sha256_digest(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"[0-9a-f]{64}", value.strip().lower()))


def _resolve_local_uri_path(value: str, *, base_dir: Path) -> Path | None:
    raw = str(value).strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme == "file":
        if not parsed.path:
            return None
        return Path(parsed.path).resolve()
    if parsed.scheme:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _excluded(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _normalize_target_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip().strip("/")
    if not normalized:
        raise ValueError("framework distribution include target path is empty")
    if ".." in PurePosixPath(normalized).parts:
        raise ValueError(f"framework distribution include target path must not contain '..': {value}")
    return normalized


def _parse_distribution_includes(includes: list[Any]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for item in includes:
        if isinstance(item, str):
            source = item.strip()
            if not source:
                continue
            parsed.append((source, _normalize_target_path(source)))
            continue
        if isinstance(item, dict):
            source_raw = item.get("from")
            target_raw = item.get("to")
            if not isinstance(source_raw, str) or not source_raw.strip():
                raise ValueError("framework distribution.include mapping requires non-empty 'from'")
            source = source_raw.strip()
            if isinstance(target_raw, str) and target_raw.strip():
                target = _normalize_target_path(target_raw)
            else:
                target = _normalize_target_path(source)
            parsed.append((source, target))
            continue
        raise ValueError("framework distribution.include entries must be string or mapping {from,to}")
    if not parsed:
        raise ValueError("framework distribution.include has no valid entries")
    return parsed


def collect_framework_files(
    *,
    framework_root: Path,
    framework_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    distribution = framework_manifest.get("distribution")
    if not isinstance(distribution, dict):
        raise ValueError("framework manifest missing mapping 'distribution'")
    includes = distribution.get("include")
    if not isinstance(includes, list) or not includes:
        raise ValueError("framework distribution.include must be non-empty list")
    include_paths = _parse_distribution_includes(includes)
    excludes = [str(item).strip() for item in distribution.get("exclude_globs", []) if isinstance(item, str)]

    rows: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for include_source, include_target in include_paths:
        candidate = (framework_root / include_source).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"framework include path does not exist: {include_source}")
        if candidate.is_file():
            source_rel = candidate.relative_to(framework_root).as_posix()
            if _excluded(source_rel, excludes):
                continue
            target_rel = include_target
            if target_rel in seen_targets:
                raise ValueError(f"duplicate framework distribution target path: {target_rel}")
            row = _canonical_file_row(candidate)
            rows.append({"path": target_rel, "size": row["size"], "sha256": row["sha256"]})
            seen_targets.add(target_rel)
            continue
        for path in sorted(candidate.rglob("*")):
            if not path.is_file():
                continue
            source_rel = path.relative_to(framework_root).as_posix()
            if _excluded(source_rel, excludes):
                continue
            rel_under_include = path.relative_to(candidate).as_posix()
            target_rel = PurePosixPath(include_target, rel_under_include).as_posix()
            if target_rel in seen_targets:
                raise ValueError(f"duplicate framework distribution target path: {target_rel}")
            row = _canonical_file_row(path)
            rows.append({"path": target_rel, "size": row["size"], "sha256": row["sha256"]})
            seen_targets.add(target_rel)
    rows.sort(key=lambda item: str(item["path"]))
    return rows


def compute_framework_integrity(
    *,
    framework_root: Path,
    framework_manifest: dict[str, Any],
) -> str:
    rows = collect_framework_files(framework_root=framework_root, framework_manifest=framework_manifest)
    digest = hashlib.sha256()
    for row in rows:
        digest.update(str(row["path"]).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(str(row["sha256"]).encode("ascii"))
        digest.update(b"\x00")
        digest.update(str(row["size"]).encode("ascii"))
        digest.update(b"\n")
    return f"sha256-{digest.hexdigest()}"


def resolve_paths(
    *,
    repo_root: Path,
    topology_path: Path | None,
    project_id: str | None,
    project_root: Path | None,
    project_manifest_path: Path | None,
    framework_root: Path | None,
    framework_manifest_path: Path | None,
    lock_path: Path | None,
) -> ResolvedPaths:
    resolved_repo_root = repo_root.resolve()

    resolved_framework_root = framework_root.resolve() if isinstance(framework_root, Path) else resolved_repo_root
    resolved_framework_manifest = (
        framework_manifest_path.resolve()
        if isinstance(framework_manifest_path, Path)
        else default_framework_manifest_path(resolved_framework_root)
    )

    resolved_project_root: Path | None = project_root.resolve() if isinstance(project_root, Path) else None
    resolved_project_id: str | None = project_id.strip() if isinstance(project_id, str) and project_id.strip() else None
    resolved_project_manifest: Path | None = (
        project_manifest_path.resolve() if isinstance(project_manifest_path, Path) else None
    )

    if isinstance(topology_path, Path):
        manifest = _load_yaml(topology_path.resolve())
        project_section = manifest.get("project")
        if not isinstance(project_section, dict):
            raise ValueError("topology manifest missing 'project' section")
        active = str(project_section.get("active", "")).strip()
        projects_root = str(project_section.get("projects_root", "")).strip()
        if not active or not projects_root:
            raise ValueError("topology project.active/projects_root must be non-empty")
        resolved_project_id = resolved_project_id or active
        if resolved_project_root is None:
            resolved_project_root = (resolved_repo_root / projects_root / resolved_project_id).resolve()
        if resolved_project_manifest is None:
            resolved_project_manifest = resolved_project_root / "project.yaml"

    if resolved_project_root is None:
        raise ValueError("project root is not resolved (provide topology or --project-root)")
    if resolved_project_manifest is None:
        resolved_project_manifest = resolved_project_root / "project.yaml"
    if resolved_project_id is None:
        payload = _load_yaml(resolved_project_manifest)
        project_value = payload.get("project")
        if not isinstance(project_value, str) or not project_value.strip():
            raise ValueError("project manifest missing non-empty 'project'")
        resolved_project_id = project_value.strip()

    resolved_lock_path = (
        lock_path.resolve() if isinstance(lock_path, Path) else resolved_project_root / "framework.lock.yaml"
    )

    return ResolvedPaths(
        repo_root=resolved_repo_root,
        framework_root=resolved_framework_root,
        framework_manifest_path=resolved_framework_manifest,
        project_root=resolved_project_root,
        project_manifest_path=resolved_project_manifest,
        lock_path=resolved_lock_path,
        project_id=resolved_project_id,
    )


def verify_framework_lock(
    *,
    paths: ResolvedPaths,
    strict: bool,
    enforce_package_trust: bool = False,
    verify_package_artifact_files: bool = False,
    verify_package_signature: bool = False,
    cosign_bin: str = "cosign",
) -> LockVerifyResult:
    diagnostics: list[LockDiagnostic] = []

    if not paths.framework_manifest_path.exists():
        diagnostics.append(
            LockDiagnostic(
                code="E7821",
                severity="error",
                message=f"Framework manifest not found: {paths.framework_manifest_path}",
                path=str(paths.framework_manifest_path),
            )
        )
        return LockVerifyResult(ok=False, diagnostics=diagnostics)

    if not paths.project_manifest_path.exists():
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message=f"Project manifest not found: {paths.project_manifest_path}",
                path=str(paths.project_manifest_path),
            )
        )
        return LockVerifyResult(ok=False, diagnostics=diagnostics)

    framework_manifest = _load_yaml(paths.framework_manifest_path)
    project_manifest = _load_yaml(paths.project_manifest_path)

    framework_id = framework_manifest.get("framework_id")
    framework_version = framework_manifest.get("framework_api_version")
    supported_project_range = framework_manifest.get("supported_project_schema_range")
    if not isinstance(framework_id, str) or not framework_id.strip():
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework manifest missing non-empty framework_id",
                path=str(paths.framework_manifest_path),
            )
        )
    if not isinstance(framework_version, str) or _parse_semver(framework_version) is None:
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework manifest framework_api_version must be SemVer",
                path=str(paths.framework_manifest_path),
            )
        )
    if not isinstance(supported_project_range, str) or not supported_project_range.strip():
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework manifest supported_project_schema_range must be non-empty string",
                path=str(paths.framework_manifest_path),
            )
        )

    project_schema_version = project_manifest.get("project_schema_version")
    if not isinstance(project_schema_version, str) or _parse_semver(project_schema_version) is None:
        diagnostics.append(
            LockDiagnostic(
                code="E7812",
                severity="error",
                message="project project_schema_version must be SemVer",
                path=str(paths.project_manifest_path),
            )
        )

    project_min_framework = project_manifest.get("project_min_framework_version")
    if not isinstance(project_min_framework, str) or _parse_semver(project_min_framework) is None:
        diagnostics.append(
            LockDiagnostic(
                code="E7811",
                severity="error",
                message="project project_min_framework_version must be SemVer",
                path=str(paths.project_manifest_path),
            )
        )

    project_max_framework = project_manifest.get("project_max_framework_version")
    if project_max_framework is not None and (
        not isinstance(project_max_framework, str) or _parse_semver(project_max_framework) is None
    ):
        diagnostics.append(
            LockDiagnostic(
                code="E7811",
                severity="error",
                message="project project_max_framework_version must be SemVer when set",
                path=str(paths.project_manifest_path),
            )
        )

    if not paths.lock_path.exists():
        severity = "error" if strict else "warning"
        diagnostics.append(
            LockDiagnostic(
                code="E7822",
                severity=severity,
                message=f"framework lock file is missing: {paths.lock_path}",
                path=str(paths.lock_path),
            )
        )
        return LockVerifyResult(ok=not strict, diagnostics=diagnostics)

    lock_payload = _load_yaml(paths.lock_path)
    if lock_payload.get("schema_version") != 1:
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework lock schema_version must be 1",
                path=str(paths.lock_path),
            )
        )

    lock_framework = lock_payload.get("framework")
    if not isinstance(lock_framework, dict):
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework lock must contain mapping key 'framework'",
                path=str(paths.lock_path),
            )
        )
        return LockVerifyResult(ok=False, diagnostics=diagnostics)

    lock_id = lock_framework.get("id")
    lock_version = lock_framework.get("version")
    lock_source = lock_framework.get("source")
    lock_revision = lock_framework.get("revision")
    lock_integrity = lock_framework.get("integrity")
    required = {
        "id": lock_id,
        "version": lock_version,
        "source": lock_source,
        "revision": lock_revision,
        "integrity": lock_integrity,
    }
    for key, value in required.items():
        if not isinstance(value, str) or not value.strip():
            diagnostics.append(
                LockDiagnostic(
                    code="E7827",
                    severity="error",
                    message=f"framework lock missing non-empty framework.{key}",
                    path=f"{paths.lock_path}:framework.{key}",
                )
            )

    if isinstance(lock_id, str) and isinstance(framework_id, str) and lock_id.strip() != framework_id.strip():
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message=f"framework lock id '{lock_id}' does not match framework manifest id '{framework_id}'",
                path=f"{paths.lock_path}:framework.id",
            )
        )

    if isinstance(lock_version, str) and _parse_semver(lock_version) is None:
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework lock framework.version must be SemVer",
                path=f"{paths.lock_path}:framework.version",
            )
        )

    if isinstance(framework_version, str) and isinstance(project_min_framework, str):
        if _parse_semver(framework_version) and _parse_semver(project_min_framework):
            if _compare_semver(framework_version, project_min_framework) < 0:
                diagnostics.append(
                    LockDiagnostic(
                        code="E7811",
                        severity="error",
                        message=(
                            f"framework version '{framework_version}' is below project minimum "
                            f"'{project_min_framework}'"
                        ),
                        path=str(paths.project_manifest_path),
                    )
                )
        if isinstance(project_max_framework, str) and _parse_semver(project_max_framework):
            if _compare_semver(framework_version, project_max_framework) > 0:
                diagnostics.append(
                    LockDiagnostic(
                        code="E7811",
                        severity="error",
                        message=(
                            f"framework version '{framework_version}' is above project maximum "
                            f"'{project_max_framework}'"
                        ),
                        path=str(paths.project_manifest_path),
                    )
                )

    if isinstance(project_schema_version, str) and isinstance(supported_project_range, str):
        if _parse_semver(project_schema_version):
            if not _satisfies_range(project_schema_version, supported_project_range):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7812",
                        severity="error",
                        message=(
                            f"project schema '{project_schema_version}' is outside framework supported range "
                            f"'{supported_project_range}'"
                        ),
                        path=str(paths.project_manifest_path),
                    )
                )

    project_contract_revision = project_manifest.get("project_contract_revision")
    lock_contract_revision = lock_payload.get("project_contract_revision")
    if isinstance(project_contract_revision, int):
        if not isinstance(lock_contract_revision, int):
            diagnostics.append(
                LockDiagnostic(
                    code="E7813",
                    severity="error",
                    message="framework lock missing integer project_contract_revision",
                    path=f"{paths.lock_path}:project_contract_revision",
                )
            )
        elif lock_contract_revision < project_contract_revision:
            diagnostics.append(
                LockDiagnostic(
                    code="E7813",
                    severity="error",
                    message=(
                        f"framework lock project_contract_revision '{lock_contract_revision}' is older than "
                        f"project required '{project_contract_revision}'"
                    ),
                    path=f"{paths.lock_path}:project_contract_revision",
                )
            )

    if isinstance(lock_integrity, str) and lock_integrity.startswith("sha256-"):
        expected_integrity = compute_framework_integrity(
            framework_root=paths.framework_root,
            framework_manifest=framework_manifest,
        )
        if expected_integrity != lock_integrity:
            diagnostics.append(
                LockDiagnostic(
                    code="E7824",
                    severity="error",
                    message=(
                        f"framework integrity mismatch: lock '{lock_integrity}' " f"!= computed '{expected_integrity}'"
                    ),
                    path=f"{paths.lock_path}:framework.integrity",
                )
            )
    elif isinstance(lock_integrity, str):
        diagnostics.append(
            LockDiagnostic(
                code="E7827",
                severity="error",
                message="framework.integrity must use 'sha256-<digest>' format",
                path=f"{paths.lock_path}:framework.integrity",
            )
        )

    current_revision = _git_revision(paths.framework_root)
    revision_scope = "enforced"
    if isinstance(lock_revision, str) and lock_revision and current_revision and lock_revision != current_revision:
        enforce_revision = True
        if isinstance(lock_source, str) and lock_source.strip() == "git":
            framework_git_root = _git_toplevel(paths.framework_root)
            lock_git_root = _git_toplevel(paths.lock_path.parent)
            if framework_git_root is not None and framework_git_root == lock_git_root:
                # Monorepo mode: lock file and framework share one git root,
                # commit SHA pinning is unstable because lock updates are part of same history.
                enforce_revision = False
                revision_scope = "monorepo-bypass"
        if enforce_revision:
            diagnostics.append(
                LockDiagnostic(
                    code="E7823",
                    severity="error",
                    message=(f"framework revision mismatch: lock '{lock_revision}' != git '{current_revision}'"),
                    path=f"{paths.lock_path}:framework.revision",
                )
            )

    if strict and isinstance(lock_source, str) and lock_source.strip() == "package":
        signature = lock_framework.get("signature")
        provenance = lock_payload.get("provenance")
        sbom = lock_payload.get("sbom")
        if not isinstance(signature, dict):
            diagnostics.append(
                LockDiagnostic(
                    code="E7825",
                    severity="error",
                    message="package lock requires framework.signature mapping",
                    path=f"{paths.lock_path}:framework.signature",
                )
            )
        if not isinstance(provenance, dict):
            diagnostics.append(
                LockDiagnostic(
                    code="E7826",
                    severity="error",
                    message="package lock requires provenance mapping",
                    path=f"{paths.lock_path}:provenance",
                )
            )
        if not isinstance(sbom, dict):
            diagnostics.append(
                LockDiagnostic(
                    code="E7828",
                    severity="error",
                    message="package lock requires sbom mapping",
                    path=f"{paths.lock_path}:sbom",
                )
            )
        if enforce_package_trust and isinstance(signature, dict):
            issuer = signature.get("issuer")
            subject = signature.get("subject")
            verified = signature.get("verified")
            if not _is_non_empty_str(issuer) or _is_placeholder_token(issuer):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7825",
                        severity="error",
                        message="framework.signature.issuer must be non-empty, non-placeholder string",
                        path=f"{paths.lock_path}:framework.signature.issuer",
                    )
                )
            if verify_package_artifact_files:
                signature_bundle_uri = signature.get("bundle_uri")
                signature_bundle_sha256 = signature.get("bundle_sha256")
                if not _is_valid_uri(signature_bundle_uri) or _is_placeholder_token(signature_bundle_uri):
                    diagnostics.append(
                        LockDiagnostic(
                            code="E7825",
                            severity="error",
                            message="framework.signature.bundle_uri must be a valid non-placeholder URI",
                            path=f"{paths.lock_path}:framework.signature.bundle_uri",
                        )
                    )
                if not _is_sha256_digest(signature_bundle_sha256):
                    diagnostics.append(
                        LockDiagnostic(
                            code="E7825",
                            severity="error",
                            message="framework.signature.bundle_sha256 must be a 64-char lowercase hex digest",
                            path=f"{paths.lock_path}:framework.signature.bundle_sha256",
                        )
                    )
                if _is_valid_uri(signature_bundle_uri) and _is_sha256_digest(signature_bundle_sha256):
                    resolved = _resolve_local_uri_path(str(signature_bundle_uri), base_dir=paths.lock_path.parent)
                    if resolved is None:
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7825",
                                severity="error",
                                message=(
                                    "framework.signature.bundle_uri must resolve to local file path "
                                    "in artifact verification mode"
                                ),
                                path=f"{paths.lock_path}:framework.signature.bundle_uri",
                            )
                        )
                    elif not resolved.exists():
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7825",
                                severity="error",
                                message=f"framework.signature bundle file not found: {resolved}",
                                path=f"{paths.lock_path}:framework.signature.bundle_uri",
                            )
                        )
                    else:
                        actual = _sha256_file(resolved)
                        if actual != str(signature_bundle_sha256).strip().lower():
                            diagnostics.append(
                                LockDiagnostic(
                                    code="E7825",
                                    severity="error",
                                    message=(
                                        "framework.signature bundle sha256 mismatch: "
                                        f"lock '{signature_bundle_sha256}' != actual '{actual}'"
                                    ),
                                    path=f"{paths.lock_path}:framework.signature.bundle_sha256",
                                )
                            )
            if verify_package_signature:
                signature_uri = signature.get("signature_uri")
                certificate_uri = signature.get("certificate_uri")
                signed_blob_uri = signature.get("signed_blob_uri")
                for key, value in (
                    ("signature_uri", signature_uri),
                    ("certificate_uri", certificate_uri),
                    ("signed_blob_uri", signed_blob_uri),
                ):
                    if not _is_valid_uri(value) or _is_placeholder_token(value):
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7825",
                                severity="error",
                                message=f"framework.signature.{key} must be a valid non-placeholder URI",
                                path=f"{paths.lock_path}:framework.signature.{key}",
                            )
                        )

                sig_path = (
                    _resolve_local_uri_path(str(signature_uri), base_dir=paths.lock_path.parent)
                    if _is_valid_uri(signature_uri)
                    else None
                )
                cert_path = (
                    _resolve_local_uri_path(str(certificate_uri), base_dir=paths.lock_path.parent)
                    if _is_valid_uri(certificate_uri)
                    else None
                )
                blob_path = (
                    _resolve_local_uri_path(str(signed_blob_uri), base_dir=paths.lock_path.parent)
                    if _is_valid_uri(signed_blob_uri)
                    else None
                )
                for name, path in (
                    ("signature_uri", sig_path),
                    ("certificate_uri", cert_path),
                    ("signed_blob_uri", blob_path),
                ):
                    if path is None:
                        continue
                    if not path.exists():
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7825",
                                severity="error",
                                message=f"framework.signature.{name} file not found: {path}",
                                path=f"{paths.lock_path}:framework.signature.{name}",
                            )
                        )
                if (
                    isinstance(issuer, str)
                    and issuer.strip()
                    and isinstance(subject, str)
                    and subject.strip()
                    and sig_path is not None
                    and cert_path is not None
                    and blob_path is not None
                    and sig_path.exists()
                    and cert_path.exists()
                    and blob_path.exists()
                ):
                    try:
                        verify_cmd = [
                            cosign_bin,
                            "verify-blob",
                            "--certificate",
                            str(cert_path),
                            "--signature",
                            str(sig_path),
                            "--certificate-oidc-issuer",
                            issuer.strip(),
                            "--certificate-identity",
                            subject.strip(),
                            str(blob_path),
                        ]
                        verify_run = subprocess.run(
                            verify_cmd,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    except OSError as exc:
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7825",
                                severity="error",
                                message=f"cosign verification failed to start: {exc}",
                                path=f"{paths.lock_path}:framework.signature",
                            )
                        )
                    else:
                        if verify_run.returncode != 0:
                            merged = ((verify_run.stdout or "") + (verify_run.stderr or "")).strip()
                            diagnostics.append(
                                LockDiagnostic(
                                    code="E7825",
                                    severity="error",
                                    message=f"cosign verify-blob failed: {merged[:300]}",
                                    path=f"{paths.lock_path}:framework.signature",
                                )
                            )
            if not _is_non_empty_str(subject) or _is_placeholder_token(subject):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7825",
                        severity="error",
                        message="framework.signature.subject must be non-empty, non-placeholder string",
                        path=f"{paths.lock_path}:framework.signature.subject",
                    )
                )
            if not isinstance(verified, bool) or not verified:
                diagnostics.append(
                    LockDiagnostic(
                        code="E7825",
                        severity="error",
                        message="framework.signature.verified must be true when package trust is enforced",
                        path=f"{paths.lock_path}:framework.signature.verified",
                    )
                )

        if enforce_package_trust and isinstance(provenance, dict):
            predicate_type = provenance.get("predicate_type")
            uri = provenance.get("uri")
            provenance_sha256 = provenance.get("sha256")
            if not _is_non_empty_str(predicate_type) or _is_placeholder_token(predicate_type):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7826",
                        severity="error",
                        message="provenance.predicate_type must be non-empty, non-placeholder string",
                        path=f"{paths.lock_path}:provenance.predicate_type",
                    )
                )
            if not _is_valid_uri(uri) or _is_placeholder_token(uri):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7826",
                        severity="error",
                        message="provenance.uri must be a valid non-placeholder URI",
                        path=f"{paths.lock_path}:provenance.uri",
                    )
                )
            if verify_package_artifact_files:
                if not _is_sha256_digest(provenance_sha256):
                    diagnostics.append(
                        LockDiagnostic(
                            code="E7826",
                            severity="error",
                            message="provenance.sha256 must be a 64-char lowercase hex digest",
                            path=f"{paths.lock_path}:provenance.sha256",
                        )
                    )
                if _is_valid_uri(uri) and _is_sha256_digest(provenance_sha256):
                    resolved = _resolve_local_uri_path(str(uri), base_dir=paths.lock_path.parent)
                    if resolved is None:
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7826",
                                severity="error",
                                message=(
                                    "provenance.uri must resolve to local file path " "in artifact verification mode"
                                ),
                                path=f"{paths.lock_path}:provenance.uri",
                            )
                        )
                    elif not resolved.exists():
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7826",
                                severity="error",
                                message=f"provenance file not found: {resolved}",
                                path=f"{paths.lock_path}:provenance.uri",
                            )
                        )
                    else:
                        actual = _sha256_file(resolved)
                        if actual != str(provenance_sha256).strip().lower():
                            diagnostics.append(
                                LockDiagnostic(
                                    code="E7826",
                                    severity="error",
                                    message=(
                                        "provenance sha256 mismatch: "
                                        f"lock '{provenance_sha256}' != actual '{actual}'"
                                    ),
                                    path=f"{paths.lock_path}:provenance.sha256",
                                )
                            )

        if enforce_package_trust and isinstance(sbom, dict):
            sbom_format = sbom.get("format")
            uri = sbom.get("uri")
            sbom_sha256 = sbom.get("sha256")
            if not _is_non_empty_str(sbom_format) or _is_placeholder_token(sbom_format):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7828",
                        severity="error",
                        message="sbom.format must be non-empty, non-placeholder string",
                        path=f"{paths.lock_path}:sbom.format",
                    )
                )
            if not _is_valid_uri(uri) or _is_placeholder_token(uri):
                diagnostics.append(
                    LockDiagnostic(
                        code="E7828",
                        severity="error",
                        message="sbom.uri must be a valid non-placeholder URI",
                        path=f"{paths.lock_path}:sbom.uri",
                    )
                )
            if verify_package_artifact_files:
                if not _is_sha256_digest(sbom_sha256):
                    diagnostics.append(
                        LockDiagnostic(
                            code="E7828",
                            severity="error",
                            message="sbom.sha256 must be a 64-char lowercase hex digest",
                            path=f"{paths.lock_path}:sbom.sha256",
                        )
                    )
                if _is_valid_uri(uri) and _is_sha256_digest(sbom_sha256):
                    resolved = _resolve_local_uri_path(str(uri), base_dir=paths.lock_path.parent)
                    if resolved is None:
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7828",
                                severity="error",
                                message="sbom.uri must resolve to local file path in artifact verification mode",
                                path=f"{paths.lock_path}:sbom.uri",
                            )
                        )
                    elif not resolved.exists():
                        diagnostics.append(
                            LockDiagnostic(
                                code="E7828",
                                severity="error",
                                message=f"sbom file not found: {resolved}",
                                path=f"{paths.lock_path}:sbom.uri",
                            )
                        )
                    else:
                        actual = _sha256_file(resolved)
                        if actual != str(sbom_sha256).strip().lower():
                            diagnostics.append(
                                LockDiagnostic(
                                    code="E7828",
                                    severity="error",
                                    message=("sbom sha256 mismatch: " f"lock '{sbom_sha256}' != actual '{actual}'"),
                                    path=f"{paths.lock_path}:sbom.sha256",
                                )
                            )

    has_errors = any(item.severity == "error" for item in diagnostics)
    context = {
        "project_id": paths.project_id,
        "project_root": str(paths.project_root),
        "framework_root": str(paths.framework_root),
        "lock_path": str(paths.lock_path),
        "current_framework_revision": _git_revision(paths.framework_root),
        "framework_repository": _git_remote(paths.framework_root),
        "revision_scope": revision_scope,
    }
    return LockVerifyResult(ok=not has_errors, diagnostics=diagnostics, context=context)
