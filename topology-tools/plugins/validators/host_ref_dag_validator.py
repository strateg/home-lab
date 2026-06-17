"""Host reference DAG validator - cycle and depth detection (ADR 0087 AC-6).

Updated for ADR 0107 D11: Uses shared host_chain_utils for cycle detection.
"""

from __future__ import annotations

from typing import Any

from host_chain_utils import detect_cycle, extract_host_ref
from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class HostRefDagValidator(ValidatorJsonPlugin):
    """Validate host_ref forms a DAG with max depth 2.

    This validator enforces ADR 0087 §5 invariants:
    - host_ref graph must be a DAG (no cycles)
    - Maximum nesting depth: 2 levels (L1 -> L4 -> L4)

    Example valid: srv-gamayun (L1) <- lxc-docker (L4) <- docker-grafana (L4)
    Example invalid cycle: A.host_ref -> B, B.host_ref -> A
    Example invalid depth: L1 <- L4 <- L4 <- L4 (depth 3)
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _WORKLOAD_CLASSES = {
        "class.compute.workload.lxc",
        "class.compute.workload.docker",
        "class.compute.workload.vm",
    }
    _MAX_DEPTH = 2

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7890",
                    severity="error",
                    stage=stage,
                    message=f"host_ref_dag validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        # Build lookup and host_ref graph
        row_by_id: dict[str, dict[str, Any]] = {}
        host_ref_graph: dict[str, str | None] = {}  # node -> parent (host_ref target)

        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            row_by_id[row_id] = row

            # Only track workload classes for DAG validation
            class_ref = row.get("class_ref")
            if class_ref not in self._WORKLOAD_CLASSES:
                continue

            # ADR 0107 D9: host_ref now in _RESERVED_ROW_KEYS, read from top-level first
            host_ref = row.get("host_ref") or extract_host_ref(row)
            host_ref_graph[row_id] = host_ref

        # Validate each workload node
        for node_id, host_ref in host_ref_graph.items():
            row_payload = row_by_id.get(node_id)
            if not isinstance(row_payload, dict):
                continue

            group = row_payload.get("group", "workload")
            row_prefix = f"instance:{group}:{node_id}"

            # Check for cycles using shared utility (ADR 0107 D11)
            cycle_path = detect_cycle(host_ref_graph, node_id)
            if cycle_path:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7896",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Workload '{node_id}' has circular host_ref dependency: " f"{' -> '.join(cycle_path)}"
                        ),
                        path=f"{row_prefix}.host_ref",
                    )
                )
                continue  # Skip depth check if cycle detected

            # Check depth from L1 root
            depth = self._compute_depth(host_ref_graph, node_id, row_by_id)
            if depth > self._MAX_DEPTH:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7897",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Workload '{node_id}' exceeds maximum nesting depth: "
                            f"depth={depth}, max={self._MAX_DEPTH}. "
                            "ADR 0087 limits nesting to 2 levels (e.g., L1 -> L4 -> L4)."
                        ),
                        path=f"{row_prefix}.host_ref",
                    )
                )

        return self.make_result(diagnostics)

    def _compute_depth(
        self,
        graph: dict[str, str | None],
        node: str,
        row_by_id: dict[str, dict[str, Any]],
    ) -> int:
        """Compute depth from L1 root for given node.

        Depth 0: L1 device (not in workload graph)
        Depth 1: L4 workload directly on L1
        Depth 2: L4 workload on L4 workload (e.g., Docker-in-LXC)

        Returns the depth, or 0 if node is not found or has no host_ref.
        """
        depth = 0
        current = node
        visited: set[str] = set()

        while current and current not in visited:
            visited.add(current)

            if current not in graph:
                # Current node is not a workload (likely L1 device)
                break

            host_ref = graph.get(current)
            if not host_ref:
                # No host_ref, assume depth is from here
                break

            depth += 1
            current = host_ref

            # Check if host_ref target is L1 (not in workload graph)
            if current not in graph:
                # Reached L1 device, depth is complete
                break

        return depth

    def _is_l1_device(self, row_id: str, row_by_id: dict[str, dict[str, Any]]) -> bool:
        """Check if a row is an L1 device (not a workload)."""
        row = row_by_id.get(row_id)
        if not isinstance(row, dict):
            return False
        return row.get("layer") == "L1"
