"""Foundation file-placement validator for v5 instances tree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorYamlPlugin
from yaml_loader import load_yaml_file


class FoundationFilePlacementValidator(ValidatorYamlPlugin):
    """Validate policy taxonomy for instance YAML file placement."""

    _LAYER_DIRS = {
        "L0": "L0-meta",
        "L1": "L1-foundation",
        "L2": "L2-network",
        "L3": "L3-data",
        "L4": "L4-platform",
        "L5": "L5-application",
        "L6": "L6-observability",
        "L7": "L7-operations",
    }
    _ERROR_CODE = "E7900"
    _WARNING_CODE = "W7901"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        project_root_raw = ctx.config.get("project_root")
        if not isinstance(project_root_raw, str) or not project_root_raw.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message="project_root is required in plugin config for file placement validation.",
                    path="pipeline:config.project_root",
                )
            )
            return self.make_result(diagnostics)

        project_root = self._resolve_project_root(ctx=ctx, project_root_raw=project_root_raw)
        if not project_root.exists() or not project_root.is_dir():
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"project_root '{project_root_raw}' does not exist or is not a directory.",
                    path="pipeline:config.project_root",
                )
            )
            return self.make_result(diagnostics)

        instances_root = self._resolve_instances_root(ctx=ctx, project_root=project_root)
        if not instances_root.exists() or not instances_root.is_dir():
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"instances root is missing: '{instances_root}'.",
                    path=f"project:{instances_root}",
                )
            )
            return self.make_result(diagnostics)

        for file_path in sorted(path for path in instances_root.rglob("*.yaml") if path.is_file()):
            if file_path.name == "_index.yaml":
                continue

            rel = file_path.relative_to(instances_root).as_posix()
            payload = self._load_payload(file_path=file_path)
            if not isinstance(payload, dict):
                continue

            layer = payload.get("@layer")
            group = payload.get("group")
            instance_id = payload.get("@instance")
            if not isinstance(layer, str) or not isinstance(group, str) or not isinstance(instance_id, str):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Instance file '{rel}' should declare string fields: @layer, group, @instance "
                            "for placement checks."
                        ),
                        path=f"project:{file_path}",
                    )
                )
                continue

            expected_layer_dir = self._LAYER_DIRS.get(layer)
            if expected_layer_dir is None:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=f"Instance '{instance_id}' uses unknown layer '{layer}' for placement policy.",
                        path=f"project:{file_path}",
                    )
                )
                continue

            rel_parts = rel.split("/")
            if len(rel_parts) < 3:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Instance file '{rel}' should follow "
                            "'<layer-dir>/<group>/<instance>.yaml' placement pattern."
                        ),
                        path=f"project:{file_path}",
                    )
                )
                continue

            actual_layer_dir = rel_parts[0]
            actual_group_dir = rel_parts[1]
            actual_filename = rel_parts[-1]

            if actual_layer_dir != expected_layer_dir:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Instance '{instance_id}' layer '{layer}' should be placed under "
                            f"'{expected_layer_dir}/', got '{actual_layer_dir}/'."
                        ),
                        path=f"project:{file_path}",
                    )
                )

            if actual_group_dir != group:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Instance '{instance_id}' group '{group}' should be placed under "
                            f"'{expected_layer_dir}/{group}/', got '{actual_layer_dir}/{actual_group_dir}/'."
                        ),
                        path=f"project:{file_path}",
                    )
                )

            expected_filename = f"{instance_id}.yaml"
            if actual_filename != expected_filename:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Instance file '{rel}' should be named '{expected_filename}' " "to match instance id."
                        ),
                        path=f"project:{file_path}",
                    )
                )

        return self.make_result(diagnostics)

    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    def _resolve_instances_root(self, *, ctx: PluginContext, project_root: Path) -> Path:
        default_root = (project_root / "topology" / "instances").resolve()
        manifest_path = self._resolve_project_manifest_path(ctx=ctx)
        if manifest_path is None or not manifest_path.exists() or not manifest_path.is_file():
            return default_root
        try:
            payload = load_yaml_file(manifest_path) or {}
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

    @staticmethod
    def _load_payload(*, file_path: Path) -> dict[str, Any] | None:
        try:
            payload = load_yaml_file(file_path)
        except OSError:
            return None
        except yaml.YAMLError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload
