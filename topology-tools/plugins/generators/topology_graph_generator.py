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
    _DOMAIN_STYLES = {
        "physical": "fill:#e3f2fd,stroke:#1565c0,color:#0d47a1",
        "network": "fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20",
        "services": "fill:#fff8e1,stroke:#f9a825,color:#e65100",
        "storage": "fill:#f3e5f5,stroke:#8e24aa,color:#4a148c",
        "operations": "fill:#fce4ec,stroke:#c2185b,color:#880e4f",
        "external_ref": "fill:#eceff1,stroke:#546e7a,color:#263238",
    }

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
    def _int_config(ctx: PluginContext, key: str, *, default: int) -> int:
        raw = ctx.config.get(key)
        if isinstance(raw, int):
            return raw if raw >= 0 else default
        if isinstance(raw, str):
            try:
                value = int(raw.strip())
            except ValueError:
                return default
            return value if value >= 0 else default
        return default

    @staticmethod
    def _bool_config(ctx: PluginContext, key: str, *, default: bool) -> bool:
        raw = ctx.config.get(key)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"false", "0", "no", "off"}:
                return False
            if lowered in {"true", "1", "yes", "on"}:
                return True
        return default

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
        include_external_refs = self._bool_config(ctx, "include_external_refs", default=True)
        show_edge_labels = self._bool_config(ctx, "show_edge_labels", default=True)
        show_domain_styling = self._bool_config(ctx, "show_domain_styling", default=True)
        show_node_metadata = self._bool_config(ctx, "show_node_metadata", default=True)
        cross_domain_edges_dashed = self._bool_config(ctx, "cross_domain_edges_dashed", default=False)
        include_isolated_nodes = self._bool_config(ctx, "include_isolated_nodes", default=True)
        group_nodes_by_domain = self._bool_config(ctx, "group_nodes_by_domain", default=False)
        group_nodes_by_layer = self._bool_config(ctx, "group_nodes_by_layer", default=False)
        max_nodes = self._int_config(ctx, "max_nodes", default=0)
        max_edges = self._int_config(ctx, "max_edges", default=0)

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
            and (domain_filter is None or (isinstance(row.get("domain"), str) and row.get("domain") in domain_filter))
            and (layer_filter is None or (isinstance(row.get("layer"), str) and row.get("layer") in layer_filter))
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
            and (domain_filter is None or (isinstance(row.get("domain"), str) and row.get("domain") in domain_filter))
            and (layer_filter is None or (isinstance(row.get("layer"), str) and row.get("layer") in layer_filter))
            and (
                edge_type_filter is None
                or (isinstance(row.get("edge_type"), str) and row.get("edge_type") in edge_type_filter)
            )
        ]
        if not include_isolated_nodes:
            connected_ids = {
                edge_id
                for row in filtered_edges
                for edge_id in (row.get("source_id"), row.get("target_id"))
                if isinstance(edge_id, str) and edge_id
            }
            filtered_nodes = [
                row
                for row in filtered_nodes
                if isinstance(row, dict)
                and isinstance(row.get("instance_id"), str)
                and row.get("instance_id") in connected_ids
            ]
            allowed_node_ids = {
                row.get("instance_id")
                for row in filtered_nodes
                if isinstance(row, dict) and isinstance(row.get("instance_id"), str)
            }
            filtered_edges = [
                row
                for row in filtered_edges
                if isinstance(row, dict)
                and isinstance(row.get("source_id"), str)
                and isinstance(row.get("target_id"), str)
                and row.get("source_id") in allowed_node_ids
                and row.get("target_id") in allowed_node_ids
            ]

        filtered_node_domain_by_instance = {
            str(row.get("instance_id")): str(row.get("domain"))
            for row in filtered_nodes
            if isinstance(row, dict)
            and isinstance(row.get("instance_id"), str)
            and row.get("instance_id")
            and isinstance(row.get("domain"), str)
            and row.get("domain")
        }
        rendered_edges: list[dict[str, Any]] = []
        for row in filtered_edges:
            if not isinstance(row, dict):
                continue
            source_id = row.get("source_id")
            target_id = row.get("target_id")
            source_domain = filtered_node_domain_by_instance.get(source_id) if isinstance(source_id, str) else None
            target_domain = filtered_node_domain_by_instance.get(target_id) if isinstance(target_id, str) else None
            rendered = dict(row)
            rendered["is_cross_domain"] = (
                isinstance(source_domain, str) and isinstance(target_domain, str) and source_domain != target_domain
            )
            rendered_edges.append(rendered)

        truncated_nodes = False
        truncated_edges = False
        if max_nodes > 0 and len(filtered_nodes) > max_nodes:
            filtered_nodes = filtered_nodes[:max_nodes]
            truncated_nodes = True
            trimmed_node_ids = {
                row.get("instance_id")
                for row in filtered_nodes
                if isinstance(row, dict) and isinstance(row.get("instance_id"), str)
            }
            rendered_edges = [
                row
                for row in rendered_edges
                if isinstance(row, dict)
                and isinstance(row.get("source_id"), str)
                and isinstance(row.get("target_id"), str)
                and row.get("source_id") in trimmed_node_ids
                and row.get("target_id") in trimmed_node_ids
            ]
        if max_edges > 0 and len(rendered_edges) > max_edges:
            rendered_edges = rendered_edges[:max_edges]
            truncated_edges = True

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
                    for row in rendered_edges
                    if isinstance(row, dict) and row.get("edge_type")
                ).items(),
                key=lambda item: item[0],
            )
        )
        domain_class_map = {
            row.get("safe_id"): (
                "external_ref" if str(row.get("node_type") or "") == "external_ref" else str(row.get("domain") or "")
            )
            for row in filtered_nodes
            if isinstance(row, dict) and isinstance(row.get("safe_id"), str) and row.get("safe_id")
        }
        nodes_by_domain: dict[str, list[dict[str, Any]]] = {}
        for row in filtered_nodes:
            if not isinstance(row, dict):
                continue
            domain = row.get("domain")
            if not isinstance(domain, str) or not domain:
                domain = "unknown"
            nodes_by_domain.setdefault(domain, []).append(row)
        for domain, rows in nodes_by_domain.items():
            rows.sort(key=lambda item: str(item.get("instance_id", "")))
            nodes_by_domain[domain] = rows
        nodes_by_layer: dict[str, list[dict[str, Any]]] = {}
        for row in filtered_nodes:
            if not isinstance(row, dict):
                continue
            layer = row.get("layer")
            if not isinstance(layer, str) or not layer:
                layer = "unknown"
            nodes_by_layer.setdefault(layer, []).append(row)
        for layer, rows in nodes_by_layer.items():
            rows.sort(key=lambda item: str(item.get("instance_id", "")))
            nodes_by_layer[layer] = rows

        diagrams_root = self.resolve_output_path(ctx, "docs", "diagrams")
        output_path = diagrams_root / "unified-topology.md"
        content = self.render_template(
            ctx,
            "docs/diagrams/unified-topology.md.j2",
            {
                "projection": projection,
                "nodes": filtered_nodes,
                "edges": rendered_edges,
                "domain_filter": sorted(domain_filter) if domain_filter else [],
                "layer_filter": sorted(layer_filter) if layer_filter else [],
                "edge_type_filter": sorted(edge_type_filter) if edge_type_filter else [],
                "node_type_filter": sorted(node_type_filter) if node_type_filter else [],
                "filtered_node_type_counts": filtered_node_type_counts,
                "filtered_edge_type_counts": filtered_edge_type_counts,
                "graph_direction": graph_direction,
                "include_external_refs": include_external_refs,
                "show_edge_labels": show_edge_labels,
                "show_domain_styling": show_domain_styling,
                "show_node_metadata": show_node_metadata,
                "cross_domain_edges_dashed": cross_domain_edges_dashed,
                "include_isolated_nodes": include_isolated_nodes,
                "group_nodes_by_domain": group_nodes_by_domain,
                "group_nodes_by_layer": group_nodes_by_layer,
                "max_nodes": max_nodes,
                "max_edges": max_edges,
                "truncated_nodes": truncated_nodes,
                "truncated_edges": truncated_edges,
                "domain_styles": self._DOMAIN_STYLES,
                "domain_class_map": domain_class_map,
                "nodes_by_domain": nodes_by_domain,
                "nodes_by_layer": nodes_by_layer,
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
                    f"nodes={len(filtered_nodes)} edges={len(rendered_edges)} "
                    f"domain_filter={','.join(sorted(domain_filter)) if domain_filter else 'all'} "
                    f"layer_filter={','.join(sorted(layer_filter)) if layer_filter else 'all'} "
                    f"edge_type_filter={','.join(sorted(edge_type_filter)) if edge_type_filter else 'all'} "
                    f"node_type_filter={','.join(sorted(node_type_filter)) if node_type_filter else 'all'} "
                    f"graph_direction={graph_direction} "
                    f"include_external_refs={str(include_external_refs).lower()} "
                    f"show_edge_labels={str(show_edge_labels).lower()} "
                    f"show_domain_styling={str(show_domain_styling).lower()} "
                    f"show_node_metadata={str(show_node_metadata).lower()} "
                    f"cross_domain_edges_dashed={str(cross_domain_edges_dashed).lower()} "
                    f"include_isolated_nodes={str(include_isolated_nodes).lower()} "
                    f"group_nodes_by_domain={str(group_nodes_by_domain).lower()} "
                    f"group_nodes_by_layer={str(group_nodes_by_layer).lower()} "
                    f"max_nodes={max_nodes} "
                    f"max_edges={max_edges} "
                    f"truncated_nodes={str(truncated_nodes).lower()} "
                    f"truncated_edges={str(truncated_edges).lower()}"
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
