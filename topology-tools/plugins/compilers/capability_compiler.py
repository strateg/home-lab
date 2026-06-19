"""Capability derivation compiler plugin for v5 topology (ADR 0063, ADR 0106).

This plugin implements capability-driven architecture:
- Runs in COMPILE stage before validators
- Derives capabilities from class/object definitions
- Publishes derived data for validators/generators to consume via subscribe()
- SINGLE SOURCE OF TRUTH for capability derivation (ADR 0106 + ADR 0104 integration)

ADR 0106 capability namespaces:
- cap.os.* — Platform/OS capabilities (derived from OS family/distribution)
- cap.bootstrap.* — Bootstrap mechanism capabilities (derived from initialization_contract.mechanism)
- cap.vendor.* — Vendor identity capabilities (derived from vendor field)
- cap.role.* — Device role capabilities (derived from enabled_capabilities)
- cap.arch.* — Architecture capabilities (derived from hardware/OS architecture)
- cap.firmware.* — Firmware capabilities (derived from firmware properties)

Example of inter-plugin data exchange:
1. This plugin publishes "derived_capabilities"
2. effective_model_compiler subscribes to use this data
3. Generators access derived capabilities via compiled_json
"""

from __future__ import annotations

from typing import Any

from capability_derivation import derive_firmware_capabilities as shared_derive_firmware
from capability_derivation import derive_os_capabilities as shared_derive_os
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
        """Derive capabilities from objects and publish for validators/generators.

        ADR 0106 + ADR 0104 integration: This is the SINGLE SOURCE OF TRUTH for
        capability derivation. effective_model_compiler subscribes to these results
        instead of deriving independently.
        """
        diagnostics: list[PluginDiagnostic] = []

        # Derived capability sets per object
        derived_caps: dict[str, list[str]] = {}
        # Effective OS/firmware metadata per object (for compiled output)
        effective_os_map: dict[str, dict[str, Any]] = {}
        effective_firmware_map: dict[str, dict[str, Any]] = {}

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

            # D2: Derive cap.os.* using shared module (ADR 0106 + ADR 0104)
            # This uses the comprehensive derivation from capability_derivation.py
            class_ref = object_data.get("class_ref")
            if class_ref != "class.firmware":
                effective_os = self._derive_os_capabilities_shared(
                    object_id=object_id,
                    object_data=object_data,
                    caps=caps,
                    path=path,
                    stage=stage,
                    diagnostics=diagnostics,
                )
                if effective_os:
                    effective_os_map[object_id] = effective_os
            else:
                # Firmware objects: derive firmware capabilities
                effective_fw = self._derive_firmware_capabilities_shared(
                    object_id=object_id,
                    object_data=object_data,
                    caps=caps,
                    path=path,
                    stage=stage,
                    diagnostics=diagnostics,
                )
                if effective_fw:
                    effective_firmware_map[object_id] = effective_fw

            # Fallback: simple OS/arch derivation for objects without software.os
            if not any(c.startswith("cap.os.") for c in caps):
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

            # D2: Derive cap.role.linux_host from OS capabilities (ADR 0104)
            self._derive_linux_host_capability(caps=caps)

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
        # effective_model_compiler subscribes to this data
        ctx.publish("derived_capabilities", derived_caps)
        ctx.publish("effective_os_map", effective_os_map)
        ctx.publish("effective_firmware_map", effective_firmware_map)
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
                "effective_os_map": effective_os_map,
                "effective_firmware_map": effective_firmware_map,
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

    def _derive_os_capabilities_shared(
        self,
        *,
        object_id: str,
        object_data: dict[str, Any],
        caps: set[str],
        path: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        """Derive cap.os.* using shared derivation module (ADR 0106 + ADR 0104).

        Uses capability_derivation.derive_os_capabilities for consistent derivation
        across the pipeline. Returns effective OS metadata for compiled output.
        """
        os_caps, effective_os = shared_derive_os(
            object_id=object_id,
            object_payload=object_data,
            catalog_ids=set(),  # Catalog validation done by capability_contract_validator
            path=path,
            add_diag=lambda **kwargs: diagnostics.append(
                self.emit_diagnostic(
                    code=kwargs.get("code", "W3201"),
                    severity=kwargs.get("severity", "warning"),
                    stage=stage,
                    message=kwargs.get("message", ""),
                    path=kwargs.get("path", path),
                )
            ),
            emit_diagnostics=True,
        )
        caps.update(os_caps)
        return effective_os

    def _derive_firmware_capabilities_shared(
        self,
        *,
        object_id: str,
        object_data: dict[str, Any],
        caps: set[str],
        path: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        """Derive cap.firmware.* using shared derivation module (ADR 0106 + ADR 0104).

        Uses capability_derivation.derive_firmware_capabilities for consistent derivation
        across the pipeline. Returns effective firmware metadata for compiled output.
        """
        fw_caps, effective_fw = shared_derive_firmware(
            object_id=object_id,
            object_payload=object_data,
            catalog_ids=set(),  # Catalog validation done by capability_contract_validator
            path=path,
            add_diag=lambda **kwargs: diagnostics.append(
                self.emit_diagnostic(
                    code=kwargs.get("code", "W3201"),
                    severity=kwargs.get("severity", "warning"),
                    stage=stage,
                    message=kwargs.get("message", ""),
                    path=kwargs.get("path", path),
                )
            ),
            emit_diagnostics=True,
        )
        caps.update(fw_caps)
        return effective_fw

    def _derive_os_capabilities(
        self,
        *,
        properties: dict[str, Any],
        caps: set[str],
    ) -> None:
        """Derive cap.os.* from OS family and distribution (legacy fallback)."""
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

    @staticmethod
    def _derive_linux_host_capability(*, caps: set[str]) -> None:
        """Derive cap.role.linux_host from OS capabilities (ADR 0104 Amendment A7).

        Linux hosts require common Ansible role configuration.
        """
        linux_os_caps = {"cap.os.debian", "cap.os.ubuntu", "cap.os.linux", "cap.os.nixos", "cap.os.alpine"}
        if caps & linux_os_caps:
            caps.add("cap.role.linux_host")
