"""Typed IR helpers for Terraform artifact families (ADR0092 Wave 2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TerraformPlannedFileIR:
    """One planned Terraform output in family-level IR."""

    filename: str
    template: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "template": self.template,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TerraformModuleFamilyIR:
    """Typed IR for a Terraform family generator run."""

    artifact_family: str
    projection_version: str
    ir_version: str
    planned_files: tuple[TerraformPlannedFileIR, ...]
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_family": self.artifact_family,
            "projection_version": self.projection_version,
            "ir_version": self.ir_version,
            "planned_files": [item.to_dict() for item in self.planned_files],
            "capabilities": list(self.capabilities),
        }


def build_terraform_module_family_ir(
    *,
    artifact_family: str,
    templates: dict[str, str],
    capability_templates: dict[str, str],
    remote_state_enabled: bool,
    capability_flags: list[str],
    projection_version: str = "1.0",
    ir_version: str = "1.0",
) -> TerraformModuleFamilyIR:
    """Build deterministic family IR from template plan inputs."""
    planned_files: list[TerraformPlannedFileIR] = []
    for filename in sorted(templates.keys()):
        reason = "base-family"
        if filename in capability_templates:
            reason = "capability-enabled"
        elif filename == "backend.tf" and remote_state_enabled:
            reason = "dependency-enabled"
        planned_files.append(
            TerraformPlannedFileIR(
                filename=filename,
                template=str(templates[filename]),
                reason=reason,
            )
        )
    return TerraformModuleFamilyIR(
        artifact_family=artifact_family,
        projection_version=projection_version,
        ir_version=ir_version,
        planned_files=tuple(planned_files),
        capabilities=tuple(sorted({str(item) for item in capability_flags if str(item).strip()})),
    )
