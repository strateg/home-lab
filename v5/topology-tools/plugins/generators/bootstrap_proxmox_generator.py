"""Generator plugin that emits baseline Proxmox bootstrap artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_bootstrap_projection


class BootstrapProxmoxGenerator(BaseGenerator):
    """Emit baseline bootstrap bundle for Proxmox nodes."""

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
        script_actions = {
            "01-install-terraform.sh": "Install Terraform runtime (placeholder).",
            "02-install-ansible.sh": "Install Ansible runtime (placeholder).",
            "03-configure-storage.sh": "Configure storage pools (placeholder).",
            "04-configure-network.sh": "Configure network bridge and VLANs (placeholder).",
            "05-init-git-repo.sh": "Initialize git workspace (placeholder).",
            "06-enable-zswap.sh": "Enable zswap tuning (placeholder).",
        }
        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            node_root = self.resolve_output_path(ctx, "bootstrap", instance_id)
            scripts_root = node_root / "post-install"
            self.write_text_atomic(
                node_root / "answer.toml.example",
                self.render_template(
                    ctx,
                    "bootstrap/proxmox/answer.toml.example.j2",
                    {"instance_id": instance_id},
                ),
            )
            written.append(str(node_root / "answer.toml.example"))
            self.write_text_atomic(
                node_root / "README.md",
                self.render_template(
                    ctx,
                    "bootstrap/proxmox/readme.md.j2",
                    {"instance_id": instance_id},
                ),
            )
            written.append(str(node_root / "README.md"))
            for script_name, action in script_actions.items():
                script_path = scripts_root / script_name
                self.write_text_atomic(
                    script_path,
                    self.render_template(
                        ctx,
                        "bootstrap/proxmox/script.sh.j2",
                        {"action": action},
                    ),
                )
                written.append(str(script_path))
            self.write_text_atomic(
                scripts_root / "README.md",
                self.render_template(
                    ctx,
                    "bootstrap/proxmox/post-install-readme.md.j2",
                    {},
                ),
            )
            written.append(str(scripts_root / "README.md"))

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
