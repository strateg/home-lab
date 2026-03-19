"""Generator plugin that emits baseline Orange Pi bootstrap artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_bootstrap_projection


class BootstrapOrangePiGenerator(BaseGenerator):
    """Emit baseline cloud-init bundle for Orange Pi nodes."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Orange Pi bootstrap artifacts.",
                    path="generator:bootstrap_orangepi",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_bootstrap_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9601",
                    severity="error",
                    stage=stage,
                    message=f"failed to build bootstrap projection: {exc}",
                    path="generator:bootstrap_orangepi",
                )
            )
            return self.make_result(diagnostics)

        nodes = projection.get("orangepi_nodes", [])
        written: list[str] = []
        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            cloud_init_root = self.resolve_output_path(ctx, "bootstrap", instance_id, "cloud-init")
            files = {
                cloud_init_root / "user-data.example": _user_data(instance_id),
                cloud_init_root / "meta-data": _meta_data(instance_id),
                cloud_init_root / "README.md": _readme(instance_id),
            }
            for path, content in files.items():
                self.write_text_atomic(path, content)
                written.append(str(path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9601",
                severity="info",
                stage=stage,
                message=f"generated baseline Orange Pi bootstrap artifacts: nodes={len(nodes)}",
                path=str(self.resolve_output_path(ctx, "bootstrap")),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bootstrap_orangepi_files": written},
        )


def _user_data(instance_id: str) -> str:
    return (
        "#cloud-config\n"
        f"hostname: {instance_id}\n"
        "users:\n"
        "  - default\n"
        "  - name: opi\n"
        "    sudo: ALL=(ALL) NOPASSWD:ALL\n"
        "    shell: /bin/bash\n"
        "    ssh_authorized_keys:\n"
        "      - <TODO_SSH_PUBLIC_KEY>\n"
        "package_update: true\n"
        "packages:\n"
        "  - curl\n"
        "  - git\n"
        "runcmd:\n"
        "  - echo \"baseline cloud-init placeholder\"\n"
    )


def _meta_data(instance_id: str) -> str:
    return (
        f"instance-id: {instance_id}\n"
        f"local-hostname: {instance_id}\n"
    )


def _readme(instance_id: str) -> str:
    return (
        f"# Orange Pi Cloud-Init: {instance_id}\n\n"
        "Generated files:\n"
        "- `user-data.example`\n"
        "- `meta-data`\n\n"
        "All values are examples/placeholders and are safe to commit.\n"
    )

