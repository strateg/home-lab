"""Capability contract validation plugin for v5 topology (ADR 0063).

This plugin demonstrates inter-plugin communication via subscribe():
- Depends on base.compiler.capabilities
- Subscribes to "derived_capabilities" published by the compiler
- Validates that instances have required capabilities
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class CapabilityContractValidator(ValidatorJsonPlugin):
    """Validates capability contracts using data from compiler plugin.

    Demonstrates:
    - subscribe() to get data from dependency plugin
    - Using compiler-derived data in validation
    - Graceful handling of missing published data
    """

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Validate capability contracts using derived capabilities."""
        diagnostics: list[PluginDiagnostic] = []

        # Try to get derived capabilities from compiler plugin
        try:
            derived_caps = ctx.subscribe("base.compiler.capabilities", "derived_capabilities")
        except PluginDataExchangeError as e:
            # Compiler plugin didn't run or didn't publish data
            diagnostics.append(
                self.emit_diagnostic(
                    code="W4301",
                    severity="warning",
                    stage=stage,
                    message=f"Cannot validate capabilities: {e}",
                    path="plugin:base.compiler.capabilities",
                    hint="Ensure compile stage runs before validate stage",
                )
            )
            return self.make_result(diagnostics)

        # Get capability stats for info
        try:
            stats = ctx.subscribe("base.compiler.capabilities", "capability_stats")
            diagnostics.append(
                self.emit_diagnostic(
                    code="I4301",
                    severity="info",
                    stage=stage,
                    message=f"Validating {stats.get('total_capabilities', 0)} derived capabilities across {stats.get('objects_with_caps', 0)} objects",
                    path="plugin:capability_contract_validator",
                )
            )
        except PluginDataExchangeError:
            pass  # Stats are optional

        # Validate instance capability requirements
        bindings = ctx.instance_bindings.get("instance_bindings", {})

        for group_name, rows in bindings.items():
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue

                instance_id = row.get("id", "<unknown>")
                object_ref = row.get("object_ref")
                path = f"instance:{group_name}:{instance_id}"

                if not object_ref:
                    continue

                # Get object's derived capabilities
                object_caps = set(derived_caps.get(object_ref, []))

                # Check required capabilities from class
                class_ref = row.get("class_ref")
                if class_ref and class_ref in ctx.classes:
                    class_data = ctx.classes[class_ref]
                    required_caps = class_data.get("required_capabilities", [])

                    if isinstance(required_caps, list):
                        missing = [cap for cap in required_caps if cap not in object_caps]
                        if missing:
                            # Emit as warning since capability derivation is still evolving
                            # Change to "error" once capability definitions are complete
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="W4302",
                                    severity="warning",
                                    stage=stage,
                                    message=f"Object '{object_ref}' missing required capabilities: {missing}",
                                    path=path,
                                    hint=f"Object has: {sorted(object_caps)}" if object_caps else "Object has no derived capabilities",
                                )
                            )

        return self.make_result(diagnostics)
