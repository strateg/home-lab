"""
ADR 0083 scaffold: netinstall adapter baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AdapterContext, AdapterStatus, BootstrapAdapter, BootstrapResult, HandoverCheckResult, PreflightCheck


class NetinstallAdapter(BootstrapAdapter):
    @property
    def mechanism(self) -> str:
        return "netinstall"

    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        artifacts = _artifact_paths(node)
        checks = [PreflightCheck(name="artifacts_present", ok=bool(artifacts), details=f"artifacts={len(artifacts)}")]
        script_paths = [path for path in artifacts if path.name.endswith(".rsc")]
        checks.append(
            PreflightCheck(
                name="netinstall_script_present",
                ok=bool(script_paths),
                details=f"scripts={len(script_paths)}",
                remediation_hint="Ensure bundle manifest contains netinstall .rsc bootstrap artifact.",
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
            message="Netinstall adapter execution is not implemented yet (preflight baseline only).",
            error_code="E9730",
        )

    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        artifacts = _artifact_paths(node)
        script_paths = [path for path in artifacts if path.name.endswith(".rsc")]
        missing = _missing_paths(artifacts, context.bundle_path)
        return [
            HandoverCheckResult(
                name="netinstall_script_present",
                ok=bool(script_paths),
                details=f"scripts={len(script_paths)}",
                error_code="E9740" if not script_paths else "",
            ),
            HandoverCheckResult(
                name="artifacts_exist_in_bundle",
                ok=not missing,
                details=f"missing={len(missing)}",
                error_code="E9741" if missing else "",
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
