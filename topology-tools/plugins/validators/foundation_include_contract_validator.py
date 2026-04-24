"""Foundation include contract validator for v5 project instance tree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorYamlPlugin
from yaml_loader import load_yaml_file


class FoundationIncludeContractValidator(ValidatorYamlPlugin):
    """Validate deterministic v5 project instances directory contract."""

    _DEFAULT_REQUIRED_INSTANCE_DIRS = (
        "meta",
        "devices",
        "firmware",
        "physical-links",
        "power",
        "data-channels",
        "firewall",
        "network",
        "qos",
        "pools",
        "data-assets",
        "docker",
        "lxc",
        "os",
        "vm",
        "services",
        "observability",
        "operations",
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
        required_dirs = self._resolve_required_instance_dirs(ctx=ctx, project_root=project_root)
        for rel_dir in required_dirs:
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

    def _resolve_required_instance_dirs(self, *, ctx: PluginContext, project_root: Path) -> tuple[str, ...]:
        topology_manifest = self._resolve_topology_manifest_path(ctx=ctx, project_root=project_root)
        if topology_manifest is None or not topology_manifest.exists() or not topology_manifest.is_file():
            return self._DEFAULT_REQUIRED_INSTANCE_DIRS

        topology_payload = self._safe_load_yaml_mapping(topology_manifest)
        if topology_payload is None:
            return self._DEFAULT_REQUIRED_INSTANCE_DIRS
        framework = topology_payload.get("framework")
        if not isinstance(framework, dict):
            return self._DEFAULT_REQUIRED_INSTANCE_DIRS
        layer_contract_raw = framework.get("layer_contract")
        if not isinstance(layer_contract_raw, str) or not layer_contract_raw.strip():
            return self._DEFAULT_REQUIRED_INSTANCE_DIRS

        layer_contract_path = Path(layer_contract_raw)
        if not layer_contract_path.is_absolute():
            layer_contract_path = (topology_manifest.parent / layer_contract_path).resolve()

        layer_payload = self._safe_load_yaml_mapping(layer_contract_path)
        if layer_payload is None:
            return self._DEFAULT_REQUIRED_INSTANCE_DIRS
        group_layers = layer_payload.get("group_layers")
        if not isinstance(group_layers, dict):
            return self._DEFAULT_REQUIRED_INSTANCE_DIRS

        resolved = tuple(
            sorted(group for group in group_layers.keys() if isinstance(group, str) and group.strip())
        )
        return resolved or self._DEFAULT_REQUIRED_INSTANCE_DIRS

    def _resolve_topology_manifest_path(self, *, ctx: PluginContext, project_root: Path) -> Path | None:
        topology_raw = str(ctx.topology_path).strip()
        if topology_raw:
            topology_path = Path(topology_raw)
            if topology_path.is_absolute():
                return topology_path.resolve()

            repo_root_raw = ctx.config.get("repo_root")
            if isinstance(repo_root_raw, str) and repo_root_raw.strip():
                return (Path(repo_root_raw) / topology_path).resolve()

            project_candidate = (project_root / topology_path).resolve()
            if project_candidate.exists():
                return project_candidate

            return topology_path.resolve()

        default_path = (project_root / "topology.yaml").resolve()
        if default_path.exists():
            return default_path
        return None

    @staticmethod
    def _safe_load_yaml_mapping(path: Path) -> dict[str, Any] | None:
        try:
            payload = load_yaml_file(path) or {}
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload
