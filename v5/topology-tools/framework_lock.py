"""Framework lock generation and verification helpers (ADR 0076)."""

from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
RANGE_TOKEN_RE = re.compile(r"^(>=|<=|>|<|==|=)?(0|[1-9]\d*\.[0-9]\d*\.[0-9]\d*)$")


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


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
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


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _excluded(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


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
    include_paths = [str(item).strip() for item in includes if isinstance(item, str) and item.strip()]
    if not include_paths:
        raise ValueError("framework distribution.include has no valid entries")
    excludes = [str(item).strip() for item in distribution.get("exclude_globs", []) if isinstance(item, str)]

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for include in include_paths:
        candidate = (framework_root / include).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"framework include path does not exist: {include}")
        if candidate.is_file():
            rel = candidate.relative_to(framework_root).as_posix()
            if rel in seen or _excluded(rel, excludes):
                continue
            rows.append({"path": rel, "size": candidate.stat().st_size, "sha256": _hash_file(candidate)})
            seen.add(rel)
            continue
        for path in sorted(candidate.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(framework_root).as_posix()
            if rel in seen or _excluded(rel, excludes):
                continue
            rows.append({"path": rel, "size": path.stat().st_size, "sha256": _hash_file(path)})
            seen.add(rel)
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
        else resolved_framework_root / "v5" / "topology" / "framework.yaml"
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

    resolved_lock_path = lock_path.resolve() if isinstance(lock_path, Path) else resolved_project_root / "framework.lock.yaml"

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
                        f"framework integrity mismatch: lock '{lock_integrity}' "
                        f"!= computed '{expected_integrity}'"
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
                    message=(
                        f"framework revision mismatch: lock '{lock_revision}' != git '{current_revision}'"
                    ),
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
