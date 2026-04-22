"""Generator plugin that emits baseline docs artifacts from compiled model."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_docs_projection


class DocsGenerator(BaseGenerator):
    """Emit deterministic markdown docs from compiled model projection."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate docs artifacts.",
                    path="generator:docs",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_docs_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9701",
                    severity="error",
                    stage=stage,
                    message=f"failed to build docs projection: {exc}",
                    path="generator:docs",
                )
            )
            return self.make_result(diagnostics)

        docs_root = self.resolve_output_path(ctx, "docs")
        generated_files: list[str] = []
        templates = (
            ("docs/overview.md.j2", "overview.md"),
            ("docs/devices.md.j2", "devices.md"),
            ("docs/services.md.j2", "services.md"),
            ("docs/network-diagram.md.j2", "network-diagram.md"),
            ("docs/ip-allocation.md.j2", "ip-allocation.md"),
            ("docs/dns-dhcp-overview.md.j2", "dns-dhcp-overview.md"),
            ("docs/rack-layout.md.j2", "rack-layout.md"),
            ("docs/vlan-topology.md.j2", "vlan-topology.md"),
            ("docs/trust-zones.md.j2", "trust-zones.md"),
            ("docs/trust-zone-firewall-policy.md.j2", "trust-zone-firewall-policy.md"),
            ("docs/security-posture-matrix.md.j2", "security-posture-matrix.md"),
            ("docs/service-dependencies.md.j2", "service-dependencies.md"),
            ("docs/storage-topology.md.j2", "storage-topology.md"),
            ("docs/data-flow-topology.md.j2", "data-flow-topology.md"),
            ("docs/monitoring-topology.md.j2", "monitoring-topology.md"),
            ("docs/vpn-topology.md.j2", "vpn-topology.md"),
            ("docs/qos-topology.md.j2", "qos-topology.md"),
            ("docs/ups-topology.md.j2", "ups-topology.md"),
            ("docs/backup-schedule.md.j2", "backup-schedule.md"),
        )
        template_ctx = {
            "projection": projection,
            "counts": projection.get("counts", {}),
            "devices": projection.get("devices", []),
            "services": projection.get("services", []),
            "vms": projection.get("vms", []),
            "groups": projection.get("groups", {}),
            "service_dependencies": projection.get("service_dependencies", []),
            "network": projection.get("network", {}),
            "physical": projection.get("physical", {}),
            "security": projection.get("security", {}),
            "storage": projection.get("storage", {}),
            "operations": projection.get("operations", {}),
        }
        for template_name, output_name in templates:
            output_path = docs_root / output_name
            content = self.render_template(ctx, template_name, template_ctx)
            self.write_text_atomic(output_path, content)
            generated_files.append(str(output_path))

        generated_files_path = docs_root / "_generated_files.txt"
        generated_files_payload = "\n".join(sorted(generated_files)) + "\n"
        self.write_text_atomic(generated_files_path, generated_files_payload)
        generated_files.append(str(generated_files_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9701",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline docs artifacts: "
                    f"devices={projection['counts']['devices']} services={projection['counts']['services']}"
                ),
                path=str(docs_root),
            )
        )
        ctx.publish("generated_dir", str(docs_root))
        ctx.publish("generated_files", generated_files)
        ctx.publish("docs_files", generated_files)
        ctx.publish("docs_projection", projection)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "docs_dir": str(docs_root),
                "docs_files": generated_files,
            },
        )

    def on_post(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
