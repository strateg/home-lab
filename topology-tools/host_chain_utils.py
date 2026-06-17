"""Host chain utilities for @on directive resolution (ADR 0107 D11).

Shared utilities for host_ref chain traversal and cycle detection,
used by both instance_host_index_compiler and host_ref_dag_validator.
"""

from __future__ import annotations

from typing import Any


def extract_host_ref(row: dict[str, Any]) -> str | None:
    """Extract host_ref from instance row (extensions or top-level).

    Supports both normalized rows (host_ref at top-level) and raw
    instance bindings (host_ref in extensions or at top-level).

    Args:
        row: Instance row dict with potential host_ref field.

    Returns:
        The host_ref string value, or None if not present/invalid.
    """
    # Check extensions first (raw instance bindings)
    extensions = row.get("extensions")
    if isinstance(extensions, dict):
        host_ref = extensions.get("host_ref")
        if isinstance(host_ref, str) and host_ref:
            return host_ref
        # device_ref is an alias for host_ref in some workloads
        device_ref = extensions.get("device_ref")
        if isinstance(device_ref, str) and device_ref:
            return device_ref

    # Top-level fallback (normalized rows or direct fields)
    host_ref = row.get("host_ref")
    if isinstance(host_ref, str) and host_ref:
        return host_ref
    device_ref = row.get("device_ref")
    if isinstance(device_ref, str) and device_ref:
        return device_ref

    return None


def detect_cycle(
    graph: dict[str, str | None],
    start: str,
) -> list[str] | None:
    """DFS-based cycle detection in host_ref graph.

    Args:
        graph: Mapping of node_id -> host_ref target (or None).
        start: Starting node for DFS traversal.

    Returns:
        List of node IDs forming the cycle path if detected,
        or None if no cycle exists starting from this node.
    """
    visited: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        if node in visited:
            # Found cycle - return path from cycle start
            if node in path:
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            return None

        visited.add(node)
        path.append(node)

        # Get next node in chain
        next_node = graph.get(node)
        if next_node and next_node in graph:
            # next_node is also in the graph, follow the chain
            result = dfs(next_node)
            if result:
                return result

        path.pop()
        return None

    return dfs(start)


def traverse_host_chain(
    instance_id: str,
    instance_lookup: dict[str, dict[str, Any]],
    max_depth: int = 10,
) -> list[str]:
    """Traverse host_ref chain from instance to root device.

    Args:
        instance_id: Starting instance ID.
        instance_lookup: Mapping of instance_id -> instance data dict.
        max_depth: Maximum chain depth to prevent infinite loops.

    Returns:
        List of instance IDs in chain order [immediate_host, ..., root].
        Empty list if instance has no host_ref.
    """
    chain: list[str] = []
    current = instance_id
    visited: set[str] = set()

    for _ in range(max_depth):
        if current in visited:
            # Cycle detected - return what we have
            break
        visited.add(current)

        instance_data = instance_lookup.get(current)
        if not isinstance(instance_data, dict):
            break

        host_ref = extract_host_ref(instance_data)
        if not host_ref:
            break

        chain.append(host_ref)
        current = host_ref

    return chain


def get_host_at_level(
    instance_id: str,
    instance_lookup: dict[str, dict[str, Any]],
    level: int,
) -> str | None:
    """Get host at specific level up the host_ref chain.

    Level 1 = immediate host (host_ref target)
    Level 2 = parent of immediate host
    etc.

    Args:
        instance_id: Starting instance ID.
        instance_lookup: Mapping of instance_id -> instance data dict.
        level: Host level (1-indexed).

    Returns:
        Instance ID at that level, or None if level exceeds chain depth.
    """
    if level < 1:
        return None

    chain = traverse_host_chain(instance_id, instance_lookup, max_depth=level + 1)
    if len(chain) >= level:
        return chain[level - 1]
    return None


def get_root_host(
    instance_id: str,
    instance_lookup: dict[str, dict[str, Any]],
) -> str | None:
    """Get root physical device in host_ref chain.

    The root is the last instance in the chain that has no host_ref,
    typically an L1 physical device.

    Args:
        instance_id: Starting instance ID.
        instance_lookup: Mapping of instance_id -> instance data dict.

    Returns:
        Root instance ID, or None if instance has no host_ref chain.
    """
    chain = traverse_host_chain(instance_id, instance_lookup)
    if not chain:
        return None
    return chain[-1]


def build_host_ref_graph(
    instance_lookup: dict[str, dict[str, Any]],
    filter_fn: callable | None = None,
) -> dict[str, str | None]:
    """Build host_ref graph from instance lookup.

    Args:
        instance_lookup: Mapping of instance_id -> instance data dict.
        filter_fn: Optional callable(instance_id, instance_data) -> bool
                   to filter which instances to include in graph.

    Returns:
        Mapping of instance_id -> host_ref target (or None).
    """
    graph: dict[str, str | None] = {}

    for instance_id, instance_data in instance_lookup.items():
        if not isinstance(instance_data, dict):
            continue

        if filter_fn is not None and not filter_fn(instance_id, instance_data):
            continue

        host_ref = extract_host_ref(instance_data)
        graph[instance_id] = host_ref

    return graph


def topological_sort_hosts(
    instance_lookup: dict[str, dict[str, Any]],
    hosts_with_workload_defaults: set[str] | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Topologically sort hosts for workload_defaults resolution order.

    Returns hosts sorted leaf-to-root (physical devices first, then
    intermediate hosts, then deepest nested hosts last).

    Args:
        instance_lookup: Mapping of instance_id -> instance data dict.
        hosts_with_workload_defaults: Optional set of instance IDs that
            have workload_defaults. If None, all instances are considered.

    Returns:
        Tuple of (sorted_hosts, cycles):
        - sorted_hosts: List of instance IDs in resolution order.
        - cycles: List of cycle paths detected (each is list of IDs).
    """
    # Build dependency graph: host -> list of hosts that depend on it
    # A host depends on another if it has host_ref pointing to it
    graph: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {}

    # Initialize
    relevant_hosts = hosts_with_workload_defaults or set(instance_lookup.keys())
    for host_id in relevant_hosts:
        if host_id not in graph:
            graph[host_id] = []
        if host_id not in in_degree:
            in_degree[host_id] = 0

    # Build edges: if A.host_ref = B, then A depends on B
    # We want B before A, so edge is B -> A (B has to be resolved first)
    for host_id in relevant_hosts:
        instance_data = instance_lookup.get(host_id)
        if not isinstance(instance_data, dict):
            continue

        host_ref = extract_host_ref(instance_data)
        if host_ref and host_ref in relevant_hosts:
            # host_ref must be resolved before this host
            if host_ref not in graph:
                graph[host_ref] = []
            graph[host_ref].append(host_id)
            in_degree[host_id] = in_degree.get(host_id, 0) + 1

    # Kahn's algorithm for topological sort
    queue: list[str] = [node for node, degree in in_degree.items() if degree == 0]
    sorted_hosts: list[str] = []

    while queue:
        node = queue.pop(0)
        sorted_hosts.append(node)

        for dependent in graph.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Detect cycles - any nodes not in sorted_hosts are part of cycles
    cycles: list[list[str]] = []
    remaining = set(relevant_hosts) - set(sorted_hosts)
    if remaining:
        # Build graph for cycle detection
        cycle_graph: dict[str, str | None] = {}
        for host_id in remaining:
            instance_data = instance_lookup.get(host_id)
            if isinstance(instance_data, dict):
                cycle_graph[host_id] = extract_host_ref(instance_data)

        # Find cycles
        visited: set[str] = set()
        for start in remaining:
            if start in visited:
                continue
            cycle = detect_cycle(cycle_graph, start)
            if cycle:
                cycles.append(cycle)
                visited.update(cycle)

    return sorted_hosts, cycles
