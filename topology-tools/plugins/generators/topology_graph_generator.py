"""Unified topology graph generator plugin (SPC STEP 6 / REQ-NEW)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_topology_projection


class TopologyGraphGenerator(BaseGenerator):
    """Emit unified Mermaid topology dependency graph with domain/layer filtering."""

    _VALID_GRAPH_DIRECTIONS = {"TB", "TD", "BT", "LR", "RL"}

    @staticmethod
    def _normalize_filter(raw: Any) -> set[str] | None:
        if isinstance(raw, str):
            values = [item.strip() for item in raw.split(",")]
        elif isinstance(raw, list):
            values = [item.strip() for item in raw if isinstance(item, str)]
        else:
            return None
        normalized = {item for item in values if item}
        return normalized or None

    def _graph_direction(self, ctx: PluginContext) -> str:
        raw = ctx.config.get("graph_direction")
        if not isinstance(raw, str):
            return "TB"
        direction = raw.strip().upper()
        if direction in self._VALID_GRAPH_DIRECTIONS:
            return direction
        return "TB"

    @staticmethod
    def _include_external_refs(ctx: PluginContext) -> bool:
        raw = ctx.config.get("include_external_refs")
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"false", "0", "no", "off"}:
                return False
            if lowered in {"true", "1", "yes", "on"}:
                return True
        return True

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9851",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate unified topology graph.",
                    path="generator:topology-graph",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_topology_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9852",
                    severity="error",
                    stage=stage,
                    message=f"failed to build topology projection: {exc}",
                    path="generator:topology-graph",
                )
            )
            return self.make_result(diagnostics)

        domain_filter = self._normalize_filter(ctx.config.get("domain_filter"))
        layer_filter = self._normalize_filter(ctx.config.get("layer_filter"))
        edge_type_filter = self._normalize_filter(ctx.config.get("edge_type_filter"))
        node_type_filter = self._normalize_filter(ctx.config.get("node_type_filter"))
        graph_direction = self._graph_direction(ctx)
        include_external_refs = self._include_external_refs(ctx)

        nodes = projection.get("nodes", [])
        edges = projection.get("edges", [])
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(edges, list):
            edges = []

        filtered_nodes = [
            row
            for row in nodes
            if isinstance(row, dict)
            and (
                domain_filter is None
                or (isinstance(row.get("domain"), str) and row.get("domain") in domain_filter)
            )
            and (
                layer_filter is None
                or (isinstance(row.get("layer"), str) and row.get("layer") in layer_filter)
            )
            and (
                node_type_filter is None
                or (isinstance(row.get("node_type"), str) and row.get("node_type") in node_type_filter)
            )
            and (
                include_external_refs
                or (isinstance(row.get("node_type"), str) and row.get("node_type") != "external_ref")
            )
        ]
        allowed_node_ids = {
            row.get("instance_id")
            for row in filtered_nodes
            if isinstance(row, dict) and isinstance(row.get("instance_id"), str)
        }

        filtered_edges = [
            row
            for row in edges
            if isinstance(row, dict)
            and isinstance(row.get("source_id"), str)
            and isinstance(row.get("target_id"), str)
            and row.get("source_id") in allowed_node_ids
            and row.get("target_id") in allowed_node_ids
            and (
                domain_filter is None
                or (isinstance(row.get("domain"), str) and row.get("domain") in domain_filter)
            )
            and (
                layer_filter is None
                or (isinstance(row.get("layer"), str) and row.get("layer") in layer_filter)
            )
            and (
                edge_type_filter is None
                or (isinstance(row.get("edge_type"), str) and row.get("edge_type") in edge_type_filter)
            )
        ]

        filtered_node_type_counts = dict(
            sorted(
                Counter(
                    str(row.get("node_type", ""))
                    for row in filtered_nodes
                    if isinstance(row, dict) and row.get("node_type")
                ).items(),
                key=lambda item: item[0],
            )
        )
        filtered_edge_type_counts = dict(
            sorted(
                Counter(
                    str(row.get("edge_type", ""))
                    for row in filtered_edges
                    if isinstance(row, dict) and row.get("edge_type")
                ).items(),
                key=lambda item: item[0],
            )
        )

        diagrams_root = self.resolve_output_path(ctx, "docs", "diagrams")
        output_path = diagrams_root / "unified-topology.md"
        content = self.render_template(
            ctx,
            "docs/diagrams/unified-topology.md.j2",
            {
                "projection": projection,
                "nodes": filtered_nodes,
                "edges": filtered_edges,
                "domain_filter": sorted(domain_filter) if domain_filter else [],
                "layer_filter": sorted(layer_filter) if layer_filter else [],
                "edge_type_filter": sorted(edge_type_filter) if edge_type_filter else [],
                "node_type_filter": sorted(node_type_filter) if node_type_filter else [],
                "filtered_node_type_counts": filtered_node_type_counts,
                "filtered_edge_type_counts": filtered_edge_type_counts,
                "graph_direction": graph_direction,
                "include_external_refs": include_external_refs,
            },
        )
        self.write_text_atomic(output_path, content)

        generated_files = [str(output_path)]
        diagnostics.append(
            self.emit_diagnostic(
                code="I9851",
                severity="info",
                stage=stage,
                message=(
                    "generated unified topology graph: "
                    f"nodes={len(filtered_nodes)} edges={len(filtered_edges)} "
                    f"domain_filter={','.join(sorted(domain_filter)) if domain_filter else 'all'} "
                    f"layer_filter={','.join(sorted(layer_filter)) if layer_filter else 'all'} "
                    f"edge_type_filter={','.join(sorted(edge_type_filter)) if edge_type_filter else 'all'} "
                    f"node_type_filter={','.join(sorted(node_type_filter)) if node_type_filter else 'all'} "
                    f"graph_direction={graph_direction} "
                    f"include_external_refs={str(include_external_refs).lower()}"
                ),
                path=str(output_path),
            )
        )

        ctx.publish("generated_dir", str(diagrams_root))
        ctx.publish("generated_files", generated_files)
        ctx.publish("topology_graph_files", generated_files)
        ctx.publish("topology_graph_projection", projection)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "topology_graph_dir": str(diagrams_root),
                "topology_graph_files": generated_files,
            },
        )

    def on_post(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
