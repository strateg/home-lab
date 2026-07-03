"""Unified topology graph projection with cross-domain nodes and edges (ADR 0100 / ADR 0112)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from plugins.generators.projections.diagram import build_diagram_projection
from plugins.generators.projections.docs import build_docs_projection
from plugins.generators.projections.mermaid import _safe_id


def _append_topology_node(
    nodes: list[dict[str, Any]],
    *,
    instance_id: Any,
    node_type: str,
    domain: str,
    layer: str,
    label: str | None = None,
) -> None:
    if not isinstance(instance_id, str) or not instance_id:
        return
    nodes.append(
        {
            "instance_id": instance_id,
            "safe_id": _safe_id(instance_id),
            "node_type": node_type,
            "domain": domain,
            "layer": layer,
            "label": label or instance_id,
        }
    )


def _append_topology_edge(
    edges: list[dict[str, Any]],
    *,
    source_id: Any,
    target_id: Any,
    edge_type: str,
    domain: str,
    layer: str,
) -> None:
    if not isinstance(source_id, str) or not source_id:
        return
    if not isinstance(target_id, str) or not target_id:
        return
    edges.append(
        {
            "source_id": source_id,
            "target_id": target_id,
            "source_safe_id": _safe_id(source_id),
            "target_safe_id": _safe_id(target_id),
            "edge_type": edge_type,
            "domain": domain,
            "layer": layer,
        }
    )


def _collect_topology_nodes(
    diagram_projection: dict[str, Any],
    docs_projection: dict[str, Any],
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    for row in diagram_projection.get("devices", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="device",
            domain="physical",
            layer=str(row.get("layer") or "L1"),
        )

    for row in diagram_projection.get("lxc", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="lxc",
            domain="physical",
            layer=str(row.get("layer") or "L1"),
        )

    for row in docs_projection.get("vms", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="vm",
            domain="physical",
            layer=str(row.get("layer") or "L1"),
        )

    for row in docs_projection.get("services", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="service",
            domain="services",
            layer=str(row.get("layer") or "L4"),
        )

    for collection, node_type in (
        ("trust_zones", "trust_zone"),
        ("vlans", "vlan"),
        ("bridges", "bridge"),
    ):
        for row in diagram_projection.get(collection, []):
            if not isinstance(row, dict):
                continue
            _append_topology_node(
                nodes,
                instance_id=row.get("instance_id"),
                node_type=node_type,
                domain="network",
                layer="L2",
            )

    storage_projection = docs_projection.get("storage", {})
    if not isinstance(storage_projection, dict):
        storage_projection = {}
    for row in storage_projection.get("storage_pools", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="storage_pool",
            domain="storage",
            layer="L3",
        )
    for row in storage_projection.get("data_assets", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="data_asset",
            domain="storage",
            layer="L3",
        )

    operations_projection = docs_projection.get("operations", {})
    if not isinstance(operations_projection, dict):
        operations_projection = {}
    for collection, node_type in (
        ("backup_policies", "backup_policy"),
        ("healthchecks", "healthcheck"),
        ("alerts", "alert"),
        ("vpn_services", "vpn_service"),
        ("qos_policies", "qos_policy"),
        ("ups_inventory", "ups_device"),
    ):
        for row in operations_projection.get(collection, []):
            if not isinstance(row, dict):
                continue
            _append_topology_node(
                nodes,
                instance_id=row.get("instance_id"),
                node_type=node_type,
                domain="operations",
                layer="L6",
            )
    return nodes


def _extract_host_dependencies(
    diagram_projection: dict[str, Any],
    docs_projection: dict[str, Any],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in diagram_projection.get("lxc", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("host_ref"),
            edge_type="hosted_on",
            domain="physical",
            layer="L1",
        )

    for row in docs_projection.get("vms", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("host_ref"),
            edge_type="hosted_on",
            domain="physical",
            layer="L1",
        )

    network_projection = docs_projection.get("network", {})
    if not isinstance(network_projection, dict):
        network_projection = {}
    for row in network_projection.get("bridges", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("host_ref"),
            edge_type="hosted_on",
            domain="network",
            layer="L2",
        )

    storage_projection = docs_projection.get("storage", {})
    if not isinstance(storage_projection, dict):
        storage_projection = {}
    for collection in ("storage_pools", "data_assets"):
        for row in storage_projection.get(collection, []):
            if not isinstance(row, dict):
                continue
            _append_topology_edge(
                edges,
                source_id=row.get("instance_id"),
                target_id=row.get("host_ref"),
                edge_type="hosted_on",
                domain="storage",
                layer="L3",
            )
    return edges


def _extract_service_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in docs_projection.get("services", []):
        if not isinstance(row, dict):
            continue
        service_id = row.get("instance_id")
        _append_topology_edge(
            edges,
            source_id=service_id,
            target_id=row.get("runtime_target_ref"),
            edge_type="runtime_target",
            domain="services",
            layer="L4",
        )
        _append_topology_edge(
            edges,
            source_id=service_id,
            target_id=row.get("runtime_network_ref"),
            edge_type="runtime_network_binding",
            domain="services",
            layer="L4",
        )

    for row in docs_projection.get("service_dependencies", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("service_id"),
            target_id=row.get("depends_on"),
            edge_type="service_dependency",
            domain="services",
            layer="L7",
        )
    return edges


def _extract_network_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    network_projection = docs_projection.get("network", {})
    if not isinstance(network_projection, dict):
        network_projection = {}
    for row in network_projection.get("networks", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("managed_by_ref"),
            edge_type="managed_by",
            domain="network",
            layer="L2",
        )
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("trust_zone_ref"),
            edge_type="trust_zone_member",
            domain="network",
            layer="L2",
        )
    return edges


def _extract_data_link_dependencies(diagram_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in diagram_projection.get("data_links", []):
        if not isinstance(row, dict):
            continue
        endpoint_a = row.get("endpoint_a")
        endpoint_b = row.get("endpoint_b")
        source_id = endpoint_a.get("device_ref") if isinstance(endpoint_a, dict) else None
        target_id = endpoint_b.get("device_ref") if isinstance(endpoint_b, dict) else None
        if not isinstance(source_id, str) or not source_id:
            source_id = endpoint_a.get("external_ref") if isinstance(endpoint_a, dict) else None
        if not isinstance(target_id, str) or not target_id:
            target_id = endpoint_b.get("external_ref") if isinstance(endpoint_b, dict) else None
        _append_topology_edge(
            edges,
            source_id=source_id,
            target_id=target_id,
            edge_type="data_link",
            domain="physical",
            layer="L1",
        )
    return edges


def _extract_storage_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    storage_projection = docs_projection.get("storage", {})
    if not isinstance(storage_projection, dict):
        storage_projection = {}
    for row in storage_projection.get("mount_chains", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("target_ref"),
            target_id=row.get("storage_ref"),
            edge_type="uses_storage",
            domain="storage",
            layer="L3",
        )
        _append_topology_edge(
            edges,
            source_id=row.get("data_asset_ref"),
            target_id=row.get("storage_ref"),
            edge_type="stored_in",
            domain="storage",
            layer="L3",
        )
    return edges


def _extract_operations_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    operations_projection = docs_projection.get("operations", {})
    if not isinstance(operations_projection, dict):
        operations_projection = {}
    for row in operations_projection.get("backup_policies", []):
        if not isinstance(row, dict):
            continue
        policy_id = row.get("instance_id")
        _append_topology_edge(
            edges,
            source_id=policy_id,
            target_id=row.get("target_ref"),
            edge_type="backs_up_target",
            domain="operations",
            layer="L6",
        )
        _append_topology_edge(
            edges,
            source_id=policy_id,
            target_id=row.get("data_asset_ref"),
            edge_type="backs_up_data_asset",
            domain="operations",
            layer="L6",
        )
        _append_topology_edge(
            edges,
            source_id=policy_id,
            target_id=row.get("storage_ref"),
            edge_type="writes_to_storage",
            domain="operations",
            layer="L6",
        )
    return edges


def _materialize_missing_edge_endpoint_nodes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """Ensure edge endpoints always exist as nodes (external refs become synthetic nodes)."""
    known_ids = {
        row.get("instance_id")
        for row in nodes
        if isinstance(row, dict) and isinstance(row.get("instance_id"), str) and row.get("instance_id")
    }
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        for endpoint_key in ("source_id", "target_id"):
            endpoint_id = edge.get(endpoint_key)
            if not isinstance(endpoint_id, str) or not endpoint_id or endpoint_id in known_ids:
                continue
            nodes.append(
                {
                    "instance_id": endpoint_id,
                    "safe_id": _safe_id(endpoint_id),
                    "node_type": "external_ref",
                    "domain": str(edge.get("domain") or "physical"),
                    "layer": str(edge.get("layer") or "L1"),
                    "label": endpoint_id,
                }
            )
            known_ids.add(endpoint_id)


def build_topology_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build unified topology graph projection with cross-domain nodes and dependencies."""
    diagram_projection = build_diagram_projection(compiled_json)
    docs_projection = build_docs_projection(compiled_json)
    nodes = _collect_topology_nodes(diagram_projection, docs_projection)
    edges: list[dict[str, Any]] = []
    edges.extend(_extract_host_dependencies(diagram_projection, docs_projection))
    edges.extend(_extract_service_dependencies(docs_projection))
    edges.extend(_extract_network_dependencies(docs_projection))
    edges.extend(_extract_data_link_dependencies(diagram_projection))
    edges.extend(_extract_storage_dependencies(docs_projection))
    edges.extend(_extract_operations_dependencies(docs_projection))
    _materialize_missing_edge_endpoint_nodes(nodes, edges)

    unique_nodes: dict[str, dict[str, Any]] = {}
    for row in nodes:
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str) and instance_id and instance_id not in unique_nodes:
            unique_nodes[instance_id] = row

    deduped_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in edges:
        source_id = row.get("source_id")
        target_id = row.get("target_id")
        edge_type = row.get("edge_type")
        if not isinstance(source_id, str) or not isinstance(target_id, str) or not isinstance(edge_type, str):
            continue
        key = (source_id, target_id, edge_type)
        if key not in deduped_edges:
            deduped_edges[key] = row

    sorted_nodes = sorted(
        unique_nodes.values(),
        key=lambda row: (str(row.get("domain", "")), str(row.get("layer", "")), str(row.get("instance_id", ""))),
    )
    sorted_edges = sorted(
        deduped_edges.values(),
        key=lambda row: (
            str(row.get("domain", "")),
            str(row.get("layer", "")),
            str(row.get("source_id", "")),
            str(row.get("target_id", "")),
            str(row.get("edge_type", "")),
        ),
    )

    node_domains = sorted({str(row.get("domain", "")) for row in sorted_nodes if row.get("domain")})
    node_layers = sorted({str(row.get("layer", "")) for row in sorted_nodes if row.get("layer")})
    node_type_counts = dict(
        sorted(
            Counter(str(row.get("node_type", "")) for row in sorted_nodes if row.get("node_type")).items(),
            key=lambda item: item[0],
        )
    )
    edge_type_counts = dict(
        sorted(
            Counter(str(row.get("edge_type", "")) for row in sorted_edges if row.get("edge_type")).items(),
            key=lambda item: item[0],
        )
    )
    domain_counts = dict(
        sorted(
            Counter(str(row.get("domain", "")) for row in sorted_nodes if row.get("domain")).items(),
            key=lambda item: item[0],
        )
    )
    layer_counts = dict(
        sorted(
            Counter(str(row.get("layer", "")) for row in sorted_nodes if row.get("layer")).items(),
            key=lambda item: item[0],
        )
    )

    return {
        "nodes": sorted_nodes,
        "edges": sorted_edges,
        "metadata": {
            "total_nodes": len(sorted_nodes),
            "total_edges": len(sorted_edges),
            "available_domains": node_domains,
            "available_layers": node_layers,
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "domain_counts": domain_counts,
            "layer_counts": layer_counts,
        },
        "counts": {
            "nodes": len(sorted_nodes),
            "edges": len(sorted_edges),
        },
    }
