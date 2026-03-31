"""
ADR 0083 scaffold: cloud-init adapter baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterStatus, BootstrapAdapter, BootstrapResult, HandoverCheckResult, PreflightCheck


class CloudInitAdapter(BootstrapAdapter):
    @property
    def mechanism(self) -> str:
        return "cloud_init"

    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        artifacts = _artifact_paths(node)
        filenames = {path.name for path in artifacts}
        checks = [PreflightCheck(name="artifacts_present", ok=bool(artifacts), details=f"artifacts={len(artifacts)}")]
        checks.append(
            PreflightCheck(
                name="cloud_init_files_present",
                ok={"user-data", "meta-data"}.issubset(filenames),
                details=f"files={sorted(filenames)}",
                remediation_hint="Ensure bundle contains cloud-init user-data and meta-data artifacts.",
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
            message="Cloud-init adapter execution is not implemented yet (preflight baseline only).",
            error_code="E9730",
        )

    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        artifacts = _artifact_paths(node)
        filenames = {path.name for path in artifacts}
        missing = _missing_paths(artifacts, context.bundle_path)
        has_minimum = {"user-data", "meta-data"}.issubset(filenames)
        return [
            HandoverCheckResult(
                name="cloud_init_files_present",
                ok=has_minimum,
                details=f"files={sorted(filenames)}",
                error_code="E9744" if not has_minimum else "",
            ),
            HandoverCheckResult(
                name="artifacts_exist_in_bundle",
                ok=not missing,
                details=f"missing={len(missing)}",
                error_code="E9745" if missing else "",
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
