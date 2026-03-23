"""Generator plugin that emits baseline Proxmox bootstrap artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_bootstrap_projection_module

_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()
ProjectionError = _BOOTSTRAP_PROJECTIONS.ProjectionError
build_bootstrap_projection = _BOOTSTRAP_PROJECTIONS.build_bootstrap_projection


class BootstrapProxmoxGenerator(BaseGenerator):
    """Emit baseline bootstrap bundle for Proxmox nodes."""

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="proxmox")

    def _get_bootstrap_files(self, ctx: PluginContext) -> list[dict]:
        """Get bootstrap file mappings from config (ADR0078)."""
        bootstrap_files = ctx.config.get("bootstrap_files")
        if isinstance(bootstrap_files, list):
            return bootstrap_files
        return []

    def _get_post_install_scripts(self, ctx: PluginContext) -> list[dict]:
        """Get post-install script mappings from config (ADR0078)."""
        scripts = ctx.config.get("post_install_scripts")
        if isinstance(scripts, list):
            return scripts
        return []

    def _get_post_install_readme(self, ctx: PluginContext) -> dict | None:
        """Get post-install README mapping from config (ADR0078)."""
        readme = ctx.config.get("post_install_readme")
        if isinstance(readme, dict):
            return readme
        return None

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Proxmox bootstrap artifacts.",
                    path="generator:bootstrap_proxmox",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_bootstrap_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9401",
                    severity="error",
                    stage=stage,
                    message=f"failed to build bootstrap projection: {exc}",
                    path="generator:bootstrap_proxmox",
                )
            )
            return self.make_result(diagnostics)

        nodes = projection.get("proxmox_nodes", [])
        written: list[str] = []

        # Get file mappings from config (ADR0078)
        bootstrap_files = self._get_bootstrap_files(ctx)
        post_install_scripts = self._get_post_install_scripts(ctx)

        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            node_root = self.resolve_output_path(ctx, "bootstrap", instance_id)
            scripts_root = node_root / "post-install"
            render_ctx = {"instance_id": instance_id}

            # Generate bootstrap files from config (ADR0078)
            for file_mapping in bootstrap_files:
                output_file = file_mapping.get("output_file", "")
                template = file_mapping.get("template", "")
                if not output_file or not template:
                    continue
                output_path = node_root / output_file
                self.write_text_atomic(
                    output_path,
                    self.render_template(ctx, template, render_ctx),
                )
                written.append(str(output_path))

            # Generate post-install scripts from config (ADR0078)
            for script_mapping in post_install_scripts:
                output_file = script_mapping.get("output_file", "")
                template = script_mapping.get("template", "")
                action = script_mapping.get("action", "")
                if not output_file or not template:
                    continue
                script_path = scripts_root / output_file
                self.write_text_atomic(
                    script_path,
                    self.render_template(ctx, template, {"action": action, **render_ctx}),
                )
                written.append(str(script_path))

            # Generate post-install README from config (ADR0078)
            readme_config = self._get_post_install_readme(ctx)
            if readme_config:
                readme_output = readme_config.get("output_file", "README.md")
                readme_template = readme_config.get("template", "")
                if readme_template:
                    readme_path = scripts_root / readme_output
                    self.write_text_atomic(
                        readme_path,
                        self.render_template(ctx, readme_template, render_ctx),
                    )
                    written.append(str(readme_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9401",
                severity="info",
                stage=stage,
                message=f"generated baseline Proxmox bootstrap artifacts: nodes={len(nodes)}",
                path=str(self.resolve_output_path(ctx, "bootstrap")),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(self.resolve_output_path(ctx, "bootstrap")))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "bootstrap_proxmox_files", written)
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bootstrap_proxmox_files": written},
        )
