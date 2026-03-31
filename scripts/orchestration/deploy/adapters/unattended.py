"""
ADR 0083 scaffold: unattended install adapter baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterStatus, BootstrapAdapter, BootstrapResult, HandoverCheckResult, PreflightCheck


class UnattendedInstallAdapter(BootstrapAdapter):
    @property
    def mechanism(self) -> str:
        return "unattended_install"

    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        artifacts = _artifact_paths(node)
        filenames = {path.name for path in artifacts}
        checks = [PreflightCheck(name="artifacts_present", ok=bool(artifacts), details=f"artifacts={len(artifacts)}")]
        checks.append(
            PreflightCheck(
                name="answer_file_present",
                ok="answer.toml" in filenames or "answer.toml.example" in filenames,
                details=f"files={sorted(filenames)}",
                remediation_hint="Ensure bundle contains Proxmox answer.toml bootstrap artifact.",
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
            message="Unattended install adapter execution is not implemented yet (preflight baseline only).",
            error_code="E9730",
        )

    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        return []


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
