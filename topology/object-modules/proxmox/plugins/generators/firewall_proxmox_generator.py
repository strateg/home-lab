"""Generator plugin that emits Proxmox pve-firewall artifacts from security matrix.

ADR 0110: Security Matrix - Proxmox Enforcer

This generator creates:
- cluster.fw: Cluster-level firewall rules
- <vmid>.fw: Per-VM/LXC firewall rules
- Security groups from trust zones

Status: STUB - Not yet implemented. Created as placeholder for future development.
"""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator


class FirewallProxmoxGenerator(BaseGenerator):
    """Emit Proxmox pve-firewall files from security matrix.

    Proxmox VE firewall uses a different format than MikroTik/RouterOS:
    - Rules are stored in /etc/pve/firewall/ directory
    - cluster.fw: Cluster-wide rules and security groups
    - <vmid>.fw: Per-VM/container rules
    - Supports security groups (reusable rule sets)

    Rule format example:
        [RULES]
        IN ACCEPT -source 192.0.2.0/24 -dest 198.51.100.0/24 -p tcp -dport 443 -log nolog

    Security group format:
        [group zone-user]
        IN ACCEPT -source 192.0.2.0/24

    Reference: https://pve.proxmox.com/wiki/Firewall
    """

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="proxmox")

    def _publish_empty_contracts(self, ctx: PluginContext) -> None:
        """Publish empty contract outputs for migrating mode compatibility."""
        ctx.publish("firewall_proxmox_files", [])
        ctx.publish(
            "artifact_plan",
            {
                "plugin_id": self.plugin_id,
                "artifact_family": "firewall.proxmox",
                "status": "stub",
                "planned_outputs": [],
            },
        )
        ctx.publish(
            "artifact_generation_report",
            {
                "plugin_id": self.plugin_id,
                "artifact_family": "firewall.proxmox",
                "status": "stub",
                "generated": [],
            },
        )
        ctx.publish("artifact_contract_files", [])

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Generate Proxmox firewall artifacts from security matrix.

        TODO: Implement when Proxmox firewall management is needed.
        Current status: STUB returning success with no output.

        Implementation plan:
        1. Extract security_matrix from compiled_json via projections
        2. Build security groups from trust zones
        3. Generate cluster.fw with zone-based rules
        4. Generate per-VM/LXC .fw files for workloads
        5. Emit Ansible playbook for deployment (pve-firewall reload)
        """
        diagnostics: list[PluginDiagnostic] = []

        # Check if security matrix exists for Proxmox
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9301",
                    severity="info",
                    stage=stage,
                    message="No compiled_json available; skipping Proxmox firewall generation.",
                    path="generator:firewall_proxmox",
                )
            )
            # Publish empty contract outputs for migrating mode compatibility
            self._publish_empty_contracts(ctx)
            return self.make_result(diagnostics)

        # F01/R03 fix: Check for active Proxmox security matrix using canonical model structure
        # The canonical effective model uses instances.{group}[].instance.extends_object
        # We detect Proxmox enforcement via managed_by_ref pointing to a Proxmox host,
        # not by checking instance_id name (which is fragile and non-capability-based)
        proxmox_matrix_found = False
        proxmox_matrix_id = ""

        # F01: Get instances from canonical structure (instances.network, not network)
        instances = payload.get("instances", {})
        if not isinstance(instances, dict):
            instances = {}
        network_rows = instances.get("network", [])
        if not isinstance(network_rows, list):
            network_rows = []

        # Build index of Proxmox hosts from device instances
        # A host is Proxmox if it extends an object containing "proxmox" in the object ref
        device_rows = instances.get("device", [])
        if not isinstance(device_rows, list):
            device_rows = []
        proxmox_host_ids: set[str] = set()
        for dev_row in device_rows:
            if not isinstance(dev_row, dict):
                continue
            dev_instance_id = str(dev_row.get("instance_id", "")).strip()
            dev_instance_block = dev_row.get("instance", {})
            if not isinstance(dev_instance_block, dict):
                continue
            # F01: Use canonical extends_object field
            extends_obj = str(dev_instance_block.get("extends_object", "")).strip()
            # Check if device is Proxmox-based (extends proxmox object)
            if "proxmox" in extends_obj.lower():
                proxmox_host_ids.add(dev_instance_id)

        # Now check network instances for security_matrix managed by Proxmox hosts
        for row in network_rows:
            if not isinstance(row, dict):
                continue
            instance_id = str(row.get("instance_id", "")).strip()
            instance_block = row.get("instance", {})
            if not isinstance(instance_block, dict):
                continue
            # F01: Use canonical extends_object field
            extends_obj = str(instance_block.get("extends_object", "")).strip()
            if "security_matrix" not in extends_obj:
                continue

            # F01: Check managed_by_ref to determine enforcer
            # This is capability-based, not name-based detection
            inst_data = row.get("instance_data", {})
            if not isinstance(inst_data, dict):
                inst_data = {}
            managed_by_ref = str(inst_data.get("managed_by_ref", "")).strip()

            # Matrix is Proxmox-managed if managed_by_ref points to a Proxmox host
            if managed_by_ref and managed_by_ref in proxmox_host_ids:
                proxmox_matrix_found = True
                proxmox_matrix_id = instance_id
                break

        if proxmox_matrix_found:
            # Active matrix exists but enforcement not implemented - FAIL
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9303",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Proxmox security matrix '{proxmox_matrix_id}' is defined but "
                        "firewall generator is STUB. Cannot guarantee security enforcement. "
                        "Either implement the generator or remove the matrix definition."
                    ),
                    path="generator:firewall_proxmox",
                )
            )
            self._publish_empty_contracts(ctx)
            return self.make_result(
                diagnostics=diagnostics,
                output_data={
                    "status": "error",
                    "message": f"Active matrix {proxmox_matrix_id} requires implementation",
                },
            )

        # No active matrix - STUB info is acceptable
        diagnostics.append(
            self.emit_diagnostic(
                code="I9302",
                severity="info",
                stage=stage,
                message=("Proxmox firewall generator is a STUB. " "No active security matrix found - skipping."),
                path="generator:firewall_proxmox",
            )
        )

        # Publish empty contract outputs for migrating mode compatibility
        self._publish_empty_contracts(ctx)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "status": "stub",
                "message": "Proxmox firewall generator not yet implemented (no active matrix)",
            },
        )


# =============================================================================
# Proxmox Firewall Rule Format Reference (for future implementation)
# =============================================================================
#
# Cluster firewall (/etc/pve/firewall/cluster.fw):
#
#   [OPTIONS]
#   enable: 1
#   policy_in: DROP
#   policy_out: ACCEPT
#
#   [ALIASES]
#   zone_user = 192.0.2.0/24
#   zone_servers = 198.51.100.0/24
#   zone_guest = 203.0.113.0/24
#
#   [IPSET zone-user]
#   192.0.2.0/24
#
#   [group zone-user-to-servers]
#   IN ACCEPT -source zone_user -dest zone_servers -p tcp -dport 443,5432
#
#   [RULES]
#   GROUP zone-user-to-servers
#   IN DROP -source zone_guest -dest zone_servers -log warning
#
# VM/LXC firewall (/etc/pve/firewall/<vmid>.fw):
#
#   [OPTIONS]
#   enable: 1
#   policy_in: DROP
#   policy_out: ACCEPT
#
#   [RULES]
#   IN ACCEPT -p tcp -dport 22 # SSH
#   IN ACCEPT -p tcp -dport 80,443 # HTTP/HTTPS
#
# =============================================================================
