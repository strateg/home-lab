"""Foundation include contract validator for v5 project instance tree."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorYamlPlugin


class FoundationIncludeContractValidator(ValidatorYamlPlugin):
    """Validate deterministic v5 project instances directory contract."""

    _REQUIRED_DIRS = (
        "topology/instances/L0-meta/meta",
        "topology/instances/L1-foundation/devices",
        "topology/instances/L1-foundation/firmware",
        "topology/instances/L1-foundation/os",
        "topology/instances/L1-foundation/physical-links",
        "topology/instances/L1-foundation/power",
        "topology/instances/L2-network/data-channels",
        "topology/instances/L2-network/network",
        "topology/instances/L3-data/storage",
        "topology/instances/L4-platform/lxc",
        "topology/instances/L4-platform/vms",
        "topology/instances/L5-application/services",
        "topology/instances/L6-observability/observability",
        "topology/instances/L7-operations/operations",
    )

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        project_root_raw = ctx.config.get("project_root")
        if not isinstance(project_root_raw, str) or not project_root_raw.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7845",
                    severity="error",
                    stage=stage,
                    message="project_root is required in plugin config for include contract validation.",
                    path="pipeline:config.project_root",
                )
            )
            return self.make_result(diagnostics)

        project_root = Path(project_root_raw).resolve()
        if not project_root.exists() or not project_root.is_dir():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7845",
                    severity="error",
                    stage=stage,
                    message=f"project_root '{project_root_raw}' does not exist or is not a directory.",
                    path="pipeline:config.project_root",
                )
            )
            return self.make_result(diagnostics)

        for rel_dir in self._REQUIRED_DIRS:
            target = project_root / rel_dir
            if not target.exists() or not target.is_dir():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7846",
                        severity="error",
                        stage=stage,
                        message=f"Required instances directory is missing: '{rel_dir}'.",
                        path=f"project:{project_root_raw}/{rel_dir}",
                    )
                )

        instances_root = project_root / "topology" / "instances"
        if instances_root.exists() and instances_root.is_dir():
            for manual_index in sorted(instances_root.rglob("_index.yaml")):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7847",
                        severity="error",
                        stage=stage,
                        message=(
                            "Manual index file is not allowed in deterministic v5 instances tree: "
                            f"'{manual_index}'."
                        ),
                        path=f"project:{manual_index}",
                    )
                )

        return self.make_result(diagnostics)
