"""Foundation include contract validator for v5 project instance tree."""

from __future__ import annotations

from pathlib import Path

import yaml
from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorYamlPlugin


class FoundationIncludeContractValidator(ValidatorYamlPlugin):
    """Validate deterministic v5 project instances directory contract."""

    _REQUIRED_INSTANCE_DIRS = (
        "L0-meta/meta",
        "L1-foundation/devices",
        "L1-foundation/firmware",
        "L1-foundation/os",
        "L1-foundation/physical-links",
        "L1-foundation/power",
        "L2-network/data-channels",
        "L2-network/network",
        "L3-data/pools",
        "L3-data/data-assets",
        "L4-platform/lxc",
        "L5-application/services",
        "L6-observability/observability",
        "L7-operations/operations",
    )
    _REQUIRED_ONE_OF_INSTANCE_DIRS = (
        ("L4-platform/vm", "L4-platform/vms"),
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

        project_root = self._resolve_project_root(ctx=ctx, project_root_raw=project_root_raw)
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

        instances_root = self._resolve_instances_root(ctx=ctx, project_root=project_root)
        for rel_dir in self._REQUIRED_INSTANCE_DIRS:
            target = instances_root / rel_dir
            if not target.exists() or not target.is_dir():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7846",
                        severity="error",
                        stage=stage,
                        message=f"Required instances directory is missing: '{rel_dir}'.",
                        path=f"project:{instances_root}/{rel_dir}",
                    )
                )

        for candidate_dirs in self._REQUIRED_ONE_OF_INSTANCE_DIRS:
            if any((instances_root / rel_dir).is_dir() for rel_dir in candidate_dirs):
                continue
            expected = ", ".join(f"'{rel_dir}'" for rel_dir in candidate_dirs)
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7846",
                    severity="error",
                    stage=stage,
                    message=f"Required instances directory is missing: one of [{expected}].",
                    path=f"project:{instances_root}/{candidate_dirs[0]}",
                )
            )

        if instances_root.exists() and instances_root.is_dir():
            for manual_index in sorted(instances_root.rglob("_index.yaml")):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7847",
                        severity="error",
                        stage=stage,
                        message=(
                            "Manual index file is not allowed in deterministic v5 instances tree: " f"'{manual_index}'."
                        ),
                        path=f"project:{manual_index}",
                    )
                )

        return self.make_result(diagnostics)

    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    @staticmethod
    def _resolve_project_root(*, ctx: PluginContext, project_root_raw: str) -> Path:
        project_root_path = Path(project_root_raw)
        if project_root_path.is_absolute():
            return project_root_path.resolve()

        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            return (Path(repo_root_raw) / project_root_path).resolve()

        topology_path = Path(ctx.topology_path)
        if topology_path.parent:
            return (topology_path.parent / project_root_path).resolve()

        return project_root_path.resolve()

    def _resolve_instances_root(self, *, ctx: PluginContext, project_root: Path) -> Path:
        default_root = (project_root / "topology" / "instances").resolve()
        manifest_path = self._resolve_project_manifest_path(ctx=ctx)
        if manifest_path is None or not manifest_path.exists() or not manifest_path.is_file():
            return default_root
        try:
            payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except OSError:
            return default_root
        except yaml.YAMLError:
            return default_root
        if not isinstance(payload, dict):
            return default_root
        instances_root_raw = payload.get("instances_root")
        if not isinstance(instances_root_raw, str) or not instances_root_raw.strip():
            return default_root
        instances_root = Path(instances_root_raw)
        if not instances_root.is_absolute():
            instances_root = project_root / instances_root
        return instances_root.resolve()

    def _resolve_project_manifest_path(self, *, ctx: PluginContext) -> Path | None:
        manifest_path_raw = ctx.config.get("project_manifest_path")
        if not isinstance(manifest_path_raw, str) or not manifest_path_raw.strip():
            return None
        manifest_path = Path(manifest_path_raw)
        if manifest_path.is_absolute():
            return manifest_path.resolve()

        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            return (Path(repo_root_raw) / manifest_path).resolve()

        topology_path = Path(ctx.topology_path)
        return (topology_path.parent / manifest_path).resolve()
