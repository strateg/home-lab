"""Framework lock verification for V5Compiler.

Extracted from compile-topology.py to satisfy ADR 0069 thin orchestrator requirement.
Framework lock logic belongs outside the compiler orchestrator.

ADR Reference: ADR 0069 (thin orchestrator), ADR 0076/0081 (framework lock)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml
from framework_lock import _git_remote as framework_lock_git_remote
from framework_lock import _git_revision as framework_lock_git_revision
from framework_lock import _load_yaml as framework_lock_load_yaml
from framework_lock import (
    compute_framework_integrity,
    default_framework_manifest_path,
)
from framework_lock import resolve_paths as resolve_framework_lock_paths
from framework_lock import (
    verify_framework_lock,
)

if TYPE_CHECKING:
    from framework_lock import FrameworkLockPaths

# Error codes that belong to load stage vs validate stage
FRAMEWORK_LOCK_LOAD_CODES = {"E7821", "E7822"}


class FrameworkLockManager:
    """Manages framework lock verification and regeneration.

    Extracted from V5Compiler to maintain thin orchestrator pattern.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        manifest_path: Path,
        runtime_profile: str,
        add_diag: Callable[..., None],
        path_for_diag: Callable[[Path], str],
        resolve_repo_path: Callable[[str], Path],
    ) -> None:
        """Initialize framework lock manager.

        Args:
            repo_root: Repository root path
            manifest_path: Path to topology manifest
            runtime_profile: Runtime profile (production, dev, etc.)
            add_diag: Callback to add diagnostics to compiler
            path_for_diag: Callback to format paths for diagnostics
            resolve_repo_path: Callback to resolve relative paths
        """
        self.repo_root = repo_root
        self.manifest_path = manifest_path
        self.runtime_profile = runtime_profile
        self.add_diag = add_diag
        self.path_for_diag = path_for_diag
        self.resolve_repo_path = resolve_repo_path

    def verify(
        self,
        *,
        project_id: str,
        project_root: Path,
        project_manifest_path: Path,
        framework_paths: dict[str, Any],
    ) -> bool:
        """Verify framework lock integrity.

        Args:
            project_id: Active project identifier
            project_root: Project root directory
            project_manifest_path: Path to project manifest
            framework_paths: Framework paths from topology manifest

        Returns:
            True if verification passed, False otherwise
        """
        framework_root_value = framework_paths.get("root")
        if isinstance(framework_root_value, str) and framework_root_value.strip():
            lock_framework_root = self.resolve_repo_path(framework_root_value.strip())
        else:
            lock_framework_root = self.repo_root

        try:
            lock_paths = resolve_framework_lock_paths(
                repo_root=self.repo_root,
                topology_path=self.manifest_path,
                project_id=project_id,
                project_root=project_root,
                project_manifest_path=project_manifest_path,
                framework_root=lock_framework_root,
                framework_manifest_path=default_framework_manifest_path(lock_framework_root),
                lock_path=None,
            )
        except (OSError, ValueError) as exc:
            self.add_diag(
                code="E7827",
                severity="error",
                stage="load",
                message=f"framework lock path resolution failed: {exc}",
                path=self.path_for_diag(self.manifest_path),
            )
            return False

        try:
            verification = verify_framework_lock(paths=lock_paths, strict=True)
        except (OSError, ValueError) as exc:
            self.add_diag(
                code="E7827",
                severity="error",
                stage="validate",
                message=f"framework lock verification failed: {exc}",
                path=self.path_for_diag(lock_paths.lock_path),
            )
            return False

        # Dev profile: auto-regenerate lock on integrity mismatch (E7824)
        if not verification.ok and self.runtime_profile == "dev":
            has_integrity_mismatch = any(item.code == "E7824" for item in verification.diagnostics)
            if has_integrity_mismatch:
                try:
                    self._regenerate_lock(lock_paths, project_id)
                    # Retry verification after regeneration
                    verification = verify_framework_lock(paths=lock_paths, strict=True)
                except (OSError, ValueError) as exc:
                    self.add_diag(
                        code="E7827",
                        severity="error",
                        stage="validate",
                        message=f"dev profile: framework lock auto-regeneration failed: {exc}",
                        path=self.path_for_diag(lock_paths.lock_path),
                    )
                    return False

        for item in verification.diagnostics:
            stage = "load" if item.code in FRAMEWORK_LOCK_LOAD_CODES else "validate"
            self.add_diag(
                code=item.code,
                severity=item.severity,
                stage=stage,
                message=item.message,
                path=item.path,
            )
        return verification.ok

    def _regenerate_lock(
        self,
        lock_paths: FrameworkLockPaths,
        project_id: str,
    ) -> None:
        """Regenerate framework.lock.yaml in place (dev profile only).

        Args:
            lock_paths: Resolved framework lock paths
            project_id: Active project identifier
        """
        framework_manifest = framework_lock_load_yaml(lock_paths.framework_manifest_path)
        project_manifest = framework_lock_load_yaml(lock_paths.project_manifest_path)
        integrity = compute_framework_integrity(
            framework_root=lock_paths.framework_root,
            framework_manifest=framework_manifest,
        )
        revision = framework_lock_git_revision(lock_paths.framework_root)
        repository = framework_lock_git_remote(lock_paths.framework_root)

        framework_id = str(framework_manifest.get("framework_id", "")).strip()
        framework_version = str(framework_manifest.get("framework_api_version", "")).strip()
        project_schema_version = str(project_manifest.get("project_schema_version", "")).strip()
        project_contract_revision = project_manifest.get("project_contract_revision", 0)

        payload: dict[str, Any] = {
            "schema_version": 1,
            "project_schema_version": project_schema_version,
            "project_contract_revision": (
                project_contract_revision if isinstance(project_contract_revision, int) else 0
            ),
            "framework": {
                "id": framework_id,
                "version": framework_version,
                "source": "git",
                "repository": repository or "",
                "revision": revision or "UNKNOWN",
                "integrity": integrity,
            },
            "locked_at": datetime.now(UTC).isoformat(),
        }

        lock_paths.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_paths.lock_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )

        self.add_diag(
            code="I7829",
            severity="info",
            stage="validate",
            message=f"dev profile: auto-regenerated framework.lock.yaml for {project_id}",
            path=self.path_for_diag(lock_paths.lock_path),
        )
