"""Capability derivation compiler plugin for v5 topology (ADR 0063, ADR 0106).

This plugin implements capability-driven architecture:
- Runs in COMPILE stage before validators
- Derives capabilities from class/object definitions
- Publishes derived data for validators/generators to consume via subscribe()

ADR 0106 capability namespaces:
- cap.os.* — Platform/OS capabilities (derived from OS family/distribution)
- cap.bootstrap.* — Bootstrap mechanism capabilities (derived from initialization_contract.mechanism)
- cap.vendor.* — Vendor identity capabilities (derived from vendor field)
- cap.role.* — Device role capabilities (derived from enabled_capabilities)
- cap.arch.* — Architecture capabilities (derived from hardware/OS architecture)

Example of inter-plugin data exchange:
1. This plugin publishes "derived_capabilities"
2. Validators/generators subscribe to use this data
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class CapabilityCompiler(CompilerPlugin):
    """Derives capabilities from class and object definitions.

    ADR 0106: ALL-IN approach — strict errors when capabilities are missing.
    """

    # Bootstrap mechanism -> capability mapping (ADR 0106 D1)
    _BOOTSTRAP_MECHANISM_CAPS: dict[str, str] = {
        "cloud_init": "cap.bootstrap.cloud_init",
        "netinstall": "cap.bootstrap.netinstall",
        "unattended_install": "cap.bootstrap.unattended",
        "unattended": "cap.bootstrap.unattended",
        "manual": "cap.bootstrap.manual",
    }

    # Valid bootstrap mechanisms for error reporting
    _VALID_MECHANISMS: frozenset[str] = frozenset(_BOOTSTRAP_MECHANISM_CAPS.keys())

    # Role keywords -> capability mapping (ADR 0106 D2)
    _ROLE_CAPABILITY_MAP: dict[str, str] = {
        "hypervisor": "cap.role.hypervisor",
        "router": "cap.role.router",
        "edge_node": "cap.role.edge_node",
        "vpn_endpoint": "cap.role.vpn_endpoint",
        "container_host": "cap.role.container_host",
    }

    # OS family -> capability mapping
    _OS_FAMILY_CAPS: dict[str, list[str]] = {
        "linux": ["cap.os.linux", "cap.os.posix"],
        "bsd": ["cap.os.bsd", "cap.os.posix"],
        "windows": ["cap.os.windows"],
        "routeros": ["cap.os.routeros", "cap.os.proprietary"],
        "proxmox": ["cap.os.proxmox", "cap.os.linux", "cap.os.posix"],
    }

    # Architecture -> capability mapping
    _ARCH_CAPS: dict[str, list[str]] = {
        "x86_64": ["cap.arch.x86_64", "cap.arch.x86"],
        "amd64": ["cap.arch.x86_64", "cap.arch.x86"],
        "aarch64": ["cap.arch.aarch64", "cap.arch.arm"],
        "arm64": ["cap.arch.aarch64", "cap.arch.arm"],
        "armv7": ["cap.arch.armv7", "cap.arch.arm"],
    }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Derive capabilities from objects and publish for validators/generators."""
        diagnostics: list[PluginDiagnostic] = []

        # Derived capability sets per object
        derived_caps: dict[str, list[str]] = {}

        # Process each object
        for object_id, object_data in ctx.objects.items():
            caps: set[str] = set()
            path = f"object:{object_id}"

            # Extract properties
            properties = object_data.get("properties", {})
            if not isinstance(properties, dict):
                properties = {}

            # D1: Derive cap.bootstrap.* from initialization_contract.mechanism
            self._derive_bootstrap_capabilities(
                object_id=object_id,
                object_data=object_data,
                caps=caps,
                path=path,
                stage=stage,
                diagnostics=diagnostics,
            )

            # D2: Derive cap.os.* from OS family/distribution
            self._derive_os_capabilities(
                properties=properties,
                caps=caps,
            )

            # D2: Derive cap.arch.* from architecture
            architecture = properties.get("architecture")
            if isinstance(architecture, str) and architecture in self._ARCH_CAPS:
                caps.update(self._ARCH_CAPS[architecture])

            # D2: Derive cap.vendor.* from vendor field
            vendor = object_data.get("vendor")
            if isinstance(vendor, str) and vendor:
                caps.add(f"cap.vendor.{vendor.lower()}")

            # D2: Derive cap.role.* from enabled_capabilities
            self._derive_role_capabilities(
                object_data=object_data,
                caps=caps,
            )

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

        # Publish derived capabilities for validators/generators to consume
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

    def _derive_bootstrap_capabilities(
        self,
        *,
        object_id: str,
        object_data: dict[str, Any],
        caps: set[str],
        path: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Derive cap.bootstrap.* from initialization_contract.mechanism (ADR 0106 D1)."""
        init_contract = object_data.get("initialization_contract")
        if not isinstance(init_contract, dict):
            return

        mechanism = init_contract.get("mechanism")
        if not isinstance(mechanism, str) or not mechanism.strip():
            # E8001: Missing mechanism in initialization_contract
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8001",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Object '{object_id}' has initialization_contract but missing 'mechanism' field. "
                        f"Valid mechanisms: {', '.join(sorted(self._VALID_MECHANISMS))}"
                    ),
                    path=f"{path}.initialization_contract.mechanism",
                )
            )
            return

        mechanism_normalized = mechanism.strip().lower()
        if mechanism_normalized not in self._BOOTSTRAP_MECHANISM_CAPS:
            # E8002: Unknown mechanism value
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8002",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Object '{object_id}' has unknown initialization mechanism '{mechanism}'. "
                        f"Valid mechanisms: {', '.join(sorted(self._VALID_MECHANISMS))}"
                    ),
                    path=f"{path}.initialization_contract.mechanism",
                )
            )
            return

        # Add bootstrap capability
        caps.add(self._BOOTSTRAP_MECHANISM_CAPS[mechanism_normalized])

    def _derive_os_capabilities(
        self,
        *,
        properties: dict[str, Any],
        caps: set[str],
    ) -> None:
        """Derive cap.os.* from OS family and distribution."""
        family = properties.get("family")
        if isinstance(family, str) and family in self._OS_FAMILY_CAPS:
            caps.update(self._OS_FAMILY_CAPS[family])

        distribution = properties.get("distribution")
        if isinstance(distribution, str) and distribution:
            caps.add(f"cap.os.{distribution}")

    def _derive_role_capabilities(
        self,
        *,
        object_data: dict[str, Any],
        caps: set[str],
    ) -> None:
        """Derive cap.role.* from enabled_capabilities list (ADR 0106 D2)."""
        enabled_capabilities = object_data.get("enabled_capabilities")
        if not isinstance(enabled_capabilities, list):
            return

        for cap_item in enabled_capabilities:
            if not isinstance(cap_item, str):
                continue
            cap_lower = cap_item.strip().lower()
            # Check for role keywords
            for role_keyword, role_cap in self._ROLE_CAPABILITY_MAP.items():
                if role_keyword in cap_lower:
                    caps.add(role_cap)
                    break
