"""
ADR 0083 scaffold: ansible-bootstrap adapter baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterStatus, BootstrapAdapter, BootstrapResult, HandoverCheckResult, PreflightCheck


class AnsibleBootstrapAdapter(BootstrapAdapter):
    @property
    def mechanism(self) -> str:
        return "ansible_bootstrap"

    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        artifacts = _artifact_paths(node)
        playbook_like = [path for path in artifacts if path.suffix in {".yml", ".yaml", ".sh"}]
        checks = [PreflightCheck(name="artifacts_present", ok=bool(artifacts), details=f"artifacts={len(artifacts)}")]
        checks.append(
            PreflightCheck(
                name="ansible_artifact_present",
                ok=bool(playbook_like),
                details=f"candidate_files={len(playbook_like)}",
                remediation_hint="Ensure bundle contains ansible bootstrap/playbook artifacts.",
            )
        )
        missing = _missing_paths(artifacts, context.bundle_path)
        checks.append(
            PreflightCheck(
                name="artifacts_exist_in_bundle",
                ok=not missing,
                details=f"missing={len(missing)}",
                remediation_hint="Regenerate bundle to include bootstrap artifacts.",
            )
        )
        return checks

    def execute(self, node: dict[str, Any], context: AdapterContext) -> BootstrapResult:
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message="Ansible-bootstrap adapter execution is not implemented yet (preflight baseline only).",
            error_code="E9730",
        )

    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        artifacts = _artifact_paths(node)
        playbook_like = [path for path in artifacts if path.suffix in {".yml", ".yaml", ".sh"}]
        missing = _missing_paths(artifacts, context.bundle_path)
        return [
            HandoverCheckResult(
                name="ansible_artifact_present",
                ok=bool(playbook_like),
                details=f"candidate_files={len(playbook_like)}",
                error_code="E9746" if not playbook_like else "",
            ),
            HandoverCheckResult(
                name="artifacts_exist_in_bundle",
                ok=not missing,
                details=f"missing={len(missing)}",
                error_code="E9747" if missing else "",
            ),
        ]


def _artifact_paths(node: dict[str, Any]) -> list[Path]:
    artifacts = node.get("artifacts")
    result: list[Path] = []
    for row in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path", "")).strip()
        if rel:
            result.append(Path(rel))
    return result


def _missing_paths(paths: list[Path], bundle_path: Path) -> list[Path]:
    return [path for path in paths if not (bundle_path / path).exists()]
