"""Capability derivation compiler plugin for v5 topology (ADR 0063).

This plugin demonstrates the compiler plugin pattern:
- Runs in COMPILE stage before validators
- Derives capabilities from class/object definitions
- Publishes derived data for validators to consume via subscribe()

Example of inter-plugin data exchange:
1. This plugin publishes "derived_capabilities"
2. Validators can subscribe to use this data
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class CapabilityCompiler(CompilerPlugin):
    """Derives capabilities from class and object definitions.

    This plugin demonstrates:
    - CompilerPlugin base class
    - Running in COMPILE stage
    - Publishing data via ctx.publish() for other plugins
    - Emitting diagnostics for missing/invalid capabilities
    """

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Derive capabilities from objects and publish for validators."""
        diagnostics: list[PluginDiagnostic] = []

        # Derived capability sets per object
        derived_caps: dict[str, list[str]] = {}

        # OS family -> capability mapping
        os_family_caps = {
            "linux": ["cap.os.linux", "cap.os.posix"],
            "bsd": ["cap.os.bsd", "cap.os.posix"],
            "windows": ["cap.os.windows"],
            "routeros": ["cap.os.routeros", "cap.os.proprietary"],
        }

        # Architecture -> capability mapping
        arch_caps = {
            "x86_64": ["cap.arch.x86_64", "cap.arch.x86"],
            "aarch64": ["cap.arch.aarch64", "cap.arch.arm"],
            "arm64": ["cap.arch.aarch64", "cap.arch.arm"],
            "armv7": ["cap.arch.armv7", "cap.arch.arm"],
        }

        # Process each object
        for object_id, object_data in ctx.objects.items():
            caps: set[str] = set()
            path = f"object:{object_id}"

            # Extract properties
            properties = object_data.get("properties", {})
            if not isinstance(properties, dict):
                properties = {}

            # Derive from OS family
            family = properties.get("family")
            if isinstance(family, str) and family in os_family_caps:
                caps.update(os_family_caps[family])

            # Derive from architecture
            architecture = properties.get("architecture")
            if isinstance(architecture, str) and architecture in arch_caps:
                caps.update(arch_caps[architecture])

            # Derive from distribution
            distribution = properties.get("distribution")
            if isinstance(distribution, str) and distribution:
                caps.add(f"cap.os.{distribution}")

            # Check for vendor capabilities
            vendor = object_data.get("vendor")
            if isinstance(vendor, str) and vendor:
                caps.add(f"cap.vendor.{vendor.lower()}")

            # Store derived capabilities
            if caps:
                derived_caps[object_id] = sorted(caps)
                diagnostics.append(
                    self.emit_diagnostic(
                        code="I4201",
                        severity="info",
                        stage=stage,
                        message=f"Derived {len(caps)} capabilities for object '{object_id}'",
                        path=path,
                    )
                )

        # Publish derived capabilities for validators to consume
        ctx.publish("derived_capabilities", derived_caps)
        ctx.publish(
            "capability_stats",
            {
                "objects_processed": len(ctx.objects),
                "objects_with_caps": len(derived_caps),
                "total_capabilities": sum(len(caps) for caps in derived_caps.values()),
            },
        )

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "derived_capabilities": derived_caps,
                "stats": {
                    "objects_processed": len(ctx.objects),
                    "objects_with_caps": len(derived_caps),
                },
            },
        )
