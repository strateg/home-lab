"""Generator plugin that emits baseline docs artifacts from compiled model."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projection_core import ProjectionError
from plugins.generators.projections.docs import build_docs_projection


class DocsGenerator(BaseGenerator):
    """Emit deterministic markdown docs from compiled model projection."""

    # Template sets (SPC STEP 6 / E2): each entry is (set_id, set_title, pages)
    # where pages are (template_name, output_name, page_title).
    _TEMPLATE_SETS: tuple[tuple[str, str, tuple[tuple[str, str, str], ...]], ...] = (
        (
            "core",
            "Core",
            (
                ("docs/overview.md.j2", "overview.md", "Overview"),
                ("docs/devices.md.j2", "devices.md", "Devices"),
                ("docs/services.md.j2", "services.md", "Services"),
            ),
        ),
        (
            "network",
            "Network",
            (
                ("docs/network-diagram.md.j2", "network-diagram.md", "Network Inventory"),
                ("docs/ip-allocation.md.j2", "ip-allocation.md", "IP Allocation"),
                ("docs/dns-dhcp-overview.md.j2", "dns-dhcp-overview.md", "DNS & DHCP Overview"),
                ("docs/vlan-topology.md.j2", "vlan-topology.md", "VLAN Topology"),
                ("docs/vpn-topology.md.j2", "vpn-topology.md", "VPN Topology"),
                ("docs/qos-topology.md.j2", "qos-topology.md", "QoS Topology"),
            ),
        ),
        (
            "security",
            "Security",
            (
                ("docs/trust-zones.md.j2", "trust-zones.md", "Trust Zones"),
                (
                    "docs/trust-zone-firewall-policy.md.j2",
                    "trust-zone-firewall-policy.md",
                    "Trust Zone Firewall Policy",
                ),
                ("docs/security-posture-matrix.md.j2", "security-posture-matrix.md", "Security Posture Matrix"),
            ),
        ),
        (
            "physical",
            "Physical",
            (
                ("docs/rack-layout.md.j2", "rack-layout.md", "Rack Layout"),
                ("docs/ups-topology.md.j2", "ups-topology.md", "UPS Topology"),
            ),
        ),
        (
            "services",
            "Service Dependencies",
            (("docs/service-dependencies.md.j2", "service-dependencies.md", "Service Dependencies"),),
        ),
        (
            "storage",
            "Storage",
            (
                ("docs/storage-topology.md.j2", "storage-topology.md", "Storage Topology"),
                ("docs/data-flow-topology.md.j2", "data-flow-topology.md", "Data Flow Topology"),
            ),
        ),
        (
            "operations",
            "Operations",
            (
                ("docs/monitoring-topology.md.j2", "monitoring-topology.md", "Monitoring Topology"),
                ("docs/backup-schedule.md.j2", "backup-schedule.md", "Backup Schedule"),
            ),
        ),
    )

    def _select_template_sets(
        self, ctx: PluginContext, stage: Stage, diagnostics: list[PluginDiagnostic]
    ) -> tuple[tuple[str, str, tuple[tuple[str, str, str], ...]], ...]:
        """Resolve template_sets config to ordered set selection (empty/invalid => all)."""
        raw = ctx.config.get("template_sets")
        if raw is None:
            return self._TEMPLATE_SETS
        if not isinstance(raw, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9702",
                    severity="warning",
                    stage=stage,
                    message="template_sets must be a list of set names; generating all docs sets.",
                    path="generator:docs:template_sets",
                )
            )
            return self._TEMPLATE_SETS
        known = {set_id for set_id, _, _ in self._TEMPLATE_SETS}
        requested: list[str] = []
        for idx, item in enumerate(raw):
            name = item.strip() if isinstance(item, str) else ""
            if name in known:
                if name not in requested:
                    requested.append(name)
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9702",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"template_sets[{idx}] references unknown docs set {item!r}; "
                        f"known sets: {', '.join(sorted(known))}."
                    ),
                    path=f"generator:docs:template_sets[{idx}]",
                )
            )
        if not requested:
            return self._TEMPLATE_SETS
        selected_ids = set(requested)
        return tuple(entry for entry in self._TEMPLATE_SETS if entry[0] in selected_ids)

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

        selected_sets = self._select_template_sets(ctx, stage, diagnostics)

        docs_root = self.resolve_output_path(ctx, "docs")
        generated_files: list[str] = []
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
        # Track relative names for _generated_files.txt (deterministic output)
        generated_relative_names: list[str] = []
        for _, _, pages in selected_sets:
            for template_name, output_name, _ in pages:
                output_path = docs_root / output_name
                content = self.render_template(ctx, template_name, template_ctx)
                self.write_text_atomic(output_path, content)
                generated_files.append(str(output_path))  # Absolute for validation/manifest
                generated_relative_names.append(output_name)  # Relative for determinism

        # Root docs index (SPC STEP 6 / D1) — always emitted, lists selected sets only.
        page_groups: list[dict[str, Any]] = [
            {
                "id": set_id,
                "title": set_title,
                "pages": [{"file": output_name, "title": page_title} for _, output_name, page_title in pages],
            }
            for set_id, set_title, pages in selected_sets
        ]
        index_path = docs_root / "index.md"
        index_content = self.render_template(
            ctx,
            "docs/index.md.j2",
            {
                **template_ctx,
                "page_groups": page_groups,
                "selected_set_ids": [set_id for set_id, _, _ in selected_sets],
                "all_sets_selected": len(selected_sets) == len(self._TEMPLATE_SETS),
            },
        )
        self.write_text_atomic(index_path, index_content)
        generated_files.append(str(index_path))
        generated_relative_names.append("index.md")

        generated_files_path = docs_root / "_generated_files.txt"
        generated_files_payload = "\n".join(sorted(generated_relative_names)) + "\n"
        self.write_text_atomic(generated_files_path, generated_files_payload)
        generated_files.append(str(generated_files_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9701",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline docs artifacts: "
                    f"devices={projection['counts']['devices']} services={projection['counts']['services']} "
                    f"template_sets={','.join(set_id for set_id, _, _ in selected_sets)}"
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
