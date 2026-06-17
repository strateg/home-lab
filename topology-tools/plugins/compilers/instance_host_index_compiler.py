"""Host workload defaults index compiler (ADR 0107 D12).

Builds host_workload_defaults_index from raw instance bindings during
init phase, using topological sort over host_ref DAG for nested hosts.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from host_chain_utils import (
    extract_host_ref,
    topological_sort_hosts,
    traverse_host_chain,
)
from kernel.plugin_base import (
    CompilerPlugin,
    PluginContext,
    PluginDiagnostic,
    PluginResult,
    Stage,
)

# Pattern for @on directive: @on:<source>.<path>[?][:<default>]
_ON_DIRECTIVE_RE = re.compile(
    r"^@on:(?P<source>host|root|host\[\d+\])\.(?P<path>[a-zA-Z0-9_.]+)"
    r"(?P<optional>\?)?(?::(?P<default>.+))?$"
)


class InstanceHostIndexCompiler(CompilerPlugin):
    """Build host_workload_defaults_index for @on directive resolution.

    This init-phase compiler:
    1. Scans ctx.instance_bindings for instances with workload_defaults
    2. Builds topological sort over host_ref DAG (leaf-to-root)
    3. Resolves @on markers in host workload_defaults (nested hosts)
    4. Publishes fully resolved host_workload_defaults_index
    """

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Extract all instances from bindings
        instance_lookup = self._build_instance_lookup(ctx.instance_bindings)

        # Find hosts with workload_defaults
        hosts_with_defaults = self._find_hosts_with_workload_defaults(instance_lookup)

        if not hosts_with_defaults:
            # No hosts with workload_defaults, publish empty index
            ctx.publish("host_workload_defaults_index", {})
            return self.make_result(
                diagnostics,
                output_data={"host_workload_defaults_index": {}},
            )

        # Topologically sort hosts (leaf-to-root for nested resolution)
        sorted_hosts, cycles = topological_sort_hosts(
            instance_lookup,
            hosts_with_workload_defaults=hosts_with_defaults,
        )

        # Report cycles
        for cycle in cycles:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6812",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Circular host_ref dependency in workload_defaults chain: "
                        f"{' -> '.join(cycle)}"
                    ),
                    path="instance_bindings",
                )
            )

        # Build index with resolved workload_defaults
        index = self._build_resolved_index(
            sorted_hosts=sorted_hosts,
            instance_lookup=instance_lookup,
            stage=stage,
            diagnostics=diagnostics,
        )

        ctx.publish("host_workload_defaults_index", index)
        return self.make_result(
            diagnostics,
            output_data={"host_workload_defaults_index": index},
        )

    def _build_instance_lookup(
        self,
        instance_bindings: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Build instance_id -> instance_data lookup from bindings."""
        lookup: dict[str, dict[str, Any]] = {}

        bindings_root = instance_bindings.get("instance_bindings")
        if not isinstance(bindings_root, dict):
            return lookup

        for group_rows in bindings_root.values():
            if not isinstance(group_rows, list):
                continue

            for row in group_rows:
                if not isinstance(row, dict):
                    continue

                # Try semantic keyword @instance first, then legacy 'instance'
                instance_id = row.get("@instance") or row.get("instance")
                if isinstance(instance_id, str) and instance_id:
                    lookup[instance_id] = row

        return lookup

    def _find_hosts_with_workload_defaults(
        self,
        instance_lookup: dict[str, dict[str, Any]],
    ) -> set[str]:
        """Find all instances that have workload_defaults section."""
        hosts: set[str] = set()

        for instance_id, instance_data in instance_lookup.items():
            if not isinstance(instance_data, dict):
                continue

            workload_defaults = instance_data.get("workload_defaults")
            if isinstance(workload_defaults, dict) and workload_defaults:
                hosts.add(instance_id)

        return hosts

    def _build_resolved_index(
        self,
        sorted_hosts: list[str],
        instance_lookup: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, dict[str, Any]]:
        """Build index with resolved workload_defaults.

        Processes hosts in topological order (leaf-to-root) so that
        nested hosts can resolve @on markers against already-resolved
        parent hosts.
        """
        index: dict[str, dict[str, Any]] = {}

        for host_id in sorted_hosts:
            instance_data = instance_lookup.get(host_id)
            if not isinstance(instance_data, dict):
                continue

            workload_defaults = instance_data.get("workload_defaults")
            if not isinstance(workload_defaults, dict):
                continue

            # Deep copy to avoid mutating original
            resolved_defaults = copy.deepcopy(workload_defaults)

            # Resolve any @on markers in this host's workload_defaults
            resolved_defaults = self._resolve_on_markers_in_defaults(
                host_id=host_id,
                defaults=resolved_defaults,
                instance_lookup=instance_lookup,
                resolved_index=index,
                stage=stage,
                diagnostics=diagnostics,
            )

            index[host_id] = resolved_defaults

        return index

    def _resolve_on_markers_in_defaults(
        self,
        host_id: str,
        defaults: dict[str, Any],
        instance_lookup: dict[str, dict[str, Any]],
        resolved_index: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any]:
        """Recursively resolve @on markers in workload_defaults.

        Used for nested host scenarios where intermediate host's
        workload_defaults may reference its own host's defaults.
        """

        def resolve_value(value: Any, path: str) -> Any:
            if isinstance(value, dict):
                return {
                    k: resolve_value(v, f"{path}.{k}" if path else k)
                    for k, v in value.items()
                }
            if isinstance(value, list):
                return [
                    resolve_value(item, f"{path}[{idx}]")
                    for idx, item in enumerate(value)
                ]
            if not isinstance(value, str):
                return value

            # Check if it's an @on directive
            match = _ON_DIRECTIVE_RE.fullmatch(value)
            if not match:
                return value

            source = match.group("source")
            field_path = match.group("path")
            optional = bool(match.group("optional"))
            default_value = match.group("default")

            # Resolve the host to lookup from
            target_host_id = self._resolve_source_host(
                host_id=host_id,
                source=source,
                instance_lookup=instance_lookup,
            )

            if not target_host_id:
                if optional:
                    return default_value if default_value is not None else None
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6811",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Cannot resolve @on source '{source}' for host '{host_id}' "
                            f"workload_defaults at '{path}': no valid host_ref"
                        ),
                        path=f"instance:{host_id}.workload_defaults.{path}",
                    )
                )
                return value

            # Lookup from already-resolved index (topological order ensures this)
            target_defaults = resolved_index.get(target_host_id, {})
            resolved_value = self._get_nested_value(target_defaults, field_path)

            if resolved_value is None:
                if optional:
                    return default_value if default_value is not None else None
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6810",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Path '{field_path}' not found in workload_defaults of "
                            f"host '{target_host_id}' for @on directive at '{path}'"
                        ),
                        path=f"instance:{host_id}.workload_defaults.{path}",
                    )
                )
                return value

            return resolved_value

        return resolve_value(defaults, "")

    def _resolve_source_host(
        self,
        host_id: str,
        source: str,
        instance_lookup: dict[str, dict[str, Any]],
    ) -> str | None:
        """Resolve @on source directive to target host instance ID.

        Args:
            host_id: Current host instance ID.
            source: Source directive (host, root, host[N]).
            instance_lookup: Instance data lookup.

        Returns:
            Target host instance ID, or None if unresolvable.
        """
        instance_data = instance_lookup.get(host_id)
        if not isinstance(instance_data, dict):
            return None

        if source == "host":
            return extract_host_ref(instance_data)

        if source == "root":
            chain = traverse_host_chain(host_id, instance_lookup)
            return chain[-1] if chain else None

        # host[N] syntax
        bracket_match = re.match(r"host\[(\d+)\]", source)
        if bracket_match:
            level = int(bracket_match.group(1))
            chain = traverse_host_chain(host_id, instance_lookup, max_depth=level + 1)
            if len(chain) >= level:
                return chain[level - 1]
            return None

        return None

    def _get_nested_value(
        self,
        data: dict[str, Any],
        path: str,
    ) -> Any:
        """Get nested value from dict using dotted path.

        Args:
            data: Source dictionary.
            path: Dotted path like "network.bridge_ref".

        Returns:
            Value at path, or None if not found.
        """
        current = data
        for key in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Init phase handler - delegates to execute."""
        return self.execute(ctx, stage)
