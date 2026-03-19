"""Generator plugin that emits baseline Proxmox bootstrap artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_bootstrap_projection


class BootstrapProxmoxGenerator(BaseGenerator):
    """Emit baseline bootstrap bundle for Proxmox nodes."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Proxmox bootstrap artifacts.",
                    path="generator:bootstrap_proxmox",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_bootstrap_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9401",
                    severity="error",
                    stage=stage,
                    message=f"failed to build bootstrap projection: {exc}",
                    path="generator:bootstrap_proxmox",
                )
            )
            return self.make_result(diagnostics)

        nodes = projection.get("proxmox_nodes", [])
        written: list[str] = []
        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            node_root = self.resolve_output_path(ctx, "bootstrap", instance_id)
            scripts_root = node_root / "post-install"

            files = {
                node_root / "answer.toml.example": _answer_toml(instance_id),
                node_root / "README.md": _readme(instance_id),
                scripts_root / "01-install-terraform.sh": _script("Install Terraform runtime (placeholder)."),
                scripts_root / "02-install-ansible.sh": _script("Install Ansible runtime (placeholder)."),
                scripts_root / "03-configure-storage.sh": _script("Configure storage pools (placeholder)."),
                scripts_root / "04-configure-network.sh": _script("Configure network bridge and VLANs (placeholder)."),
                scripts_root / "05-init-git-repo.sh": _script("Initialize git workspace (placeholder)."),
                scripts_root / "06-enable-zswap.sh": _script("Enable zswap tuning (placeholder)."),
                scripts_root / "README.md": _scripts_readme(),
            }
            for path, content in files.items():
                self.write_text_atomic(path, content)
                written.append(str(path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9401",
                severity="info",
                stage=stage,
                message=f"generated baseline Proxmox bootstrap artifacts: nodes={len(nodes)}",
                path=str(self.resolve_output_path(ctx, "bootstrap")),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bootstrap_proxmox_files": written},
        )


def _answer_toml(instance_id: str) -> str:
    return (
        "# Proxmox unattended install answer file (example)\n"
        f"# instance_id: {instance_id}\n\n"
        "[global]\n"
        'keyboard = "en-us"\n'
        'fqdn = "proxmox.local"\n'
        'mailto = "admin@example.local"\n'
        "timezone = \"UTC\"\n\n"
        "[network]\n"
        "source = \"from-dhcp\"\n\n"
        "[disks]\n"
        "filesystem = \"zfs\"\n"
        "disk_list = [\"/dev/sda\"]\n\n"
        "[first_boot]\n"
        "enabled = true\n"
    )


def _readme(instance_id: str) -> str:
    return (
        f"# Proxmox Bootstrap: {instance_id}\n\n"
        "This directory contains baseline bootstrap artifacts generated from v5 projections.\n\n"
        "Files:\n"
        "- `answer.toml.example`: unattended installer example values.\n"
        "- `post-install/`: placeholder post-install scripts package.\n\n"
        "All values are examples/placeholders and are safe to commit.\n"
    )


def _script(action: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f'echo "{action}"\n'
    )


def _scripts_readme() -> str:
    return (
        "# Post-install Script Package\n\n"
        "Baseline placeholder scripts are generated in deterministic order.\n"
        "Replace command bodies during parity implementation.\n"
    )

