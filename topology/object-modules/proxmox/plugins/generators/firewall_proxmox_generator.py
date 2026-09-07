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

        # R03 fix: Check for active Proxmox security matrix
        # If matrix exists but generator is STUB, this must FAIL to prevent
        # false sense of security from successful pipeline
        proxmox_matrix_found = False
        proxmox_matrix_id = ""
        network_rows = payload.get("network", [])
        if isinstance(network_rows, list):
            for row in network_rows:
                if not isinstance(row, dict):
                    continue
                instance_id = str(row.get("instance_id", "")).strip()
                object_ref = str(row.get("object_ref", "")).strip()
                # Check for security_matrix.proxmox instances
                if "security_matrix" in object_ref and "proxmox" in instance_id.lower():
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
                message=(
                    "Proxmox firewall generator is a STUB. "
                    "No active security matrix found - skipping."
                ),
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
