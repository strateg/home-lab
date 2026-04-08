"""Docker Compose generator plugin (ADR 0087 Phase 6).

Produces docker-compose.yaml files from Docker stack instances.
Each stack instance generates one compose file grouping its member containers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.plugin_base import (
    PluginContext,
    PluginDiagnostic,
    PluginResult,
    Stage,
)
from plugins.generators.base_generator import BaseGenerator


class DockerComposeGenerator(BaseGenerator):
    """Generate docker-compose.yaml from stack and container topology instances."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    _STACK_CLASSES = {"class.compute.workload.docker.stack"}
    _DOCKER_CLASSES = {"class.compute.workload.docker"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        rows = self._collect_rows(ctx)

        # Build lookup
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # Find stack instances
        stacks = [
            row
            for row in rows
            if row.get("class_ref") in self._STACK_CLASSES
        ]

        if not stacks:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I7930",
                    severity="info",
                    stage=stage,
                    message="No Docker stack instances found; skipping compose generation.",
                    path="generator:docker_compose",
                )
            )
            return self.make_result(diagnostics)

        compose_root = self.resolve_output_path(ctx, "docker-compose")
        generated_files: list[str] = []

        for stack_row in sorted(stacks, key=lambda r: str(r.get("instance", ""))):
            stack_id = stack_row.get("instance", "unknown")
            extensions = self._extensions(stack_row)

            stack_name = (
                extensions.get("stack_name")
                or stack_row.get("stack_name")
                or stack_id
            )
            host_ref = (
                extensions.get("host_ref")
                or stack_row.get("host_ref")
                or "unknown"
            )
            member_refs = (
                extensions.get("member_refs")
                or stack_row.get("member_refs")
                or []
            )
            compose_version = (
                extensions.get("compose_version")
                or stack_row.get("compose_version")
                or "3.8"
            )
            shared_networks = (
                extensions.get("shared_networks")
                or stack_row.get("shared_networks")
                or []
            )
            shared_volumes = (
                extensions.get("shared_volumes")
                or stack_row.get("shared_volumes")
                or []
            )

            # Resolve member containers
            services: dict[str, Any] = {}
            for ref in member_refs:
                if not isinstance(ref, str):
                    continue
                member = row_by_id.get(ref)
                if not isinstance(member, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7931",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Stack '{stack_id}' member_ref '{ref}' "
                                "does not resolve to a known instance."
                            ),
                            path=f"instance:docker:{stack_id}.member_refs",
                        )
                    )
                    continue

                member_ext = self._extensions(member)
                runtime = member_ext.get("runtime") or member.get("runtime") or {}
                image = runtime.get("image") if isinstance(runtime, dict) else None
                if not isinstance(image, str):
                    image = f"{ref}:latest"

                service_def: dict[str, Any] = {"image": image}

                # Container name
                service_def["container_name"] = ref

                # Restart policy
                restart = runtime.get("restart_policy") if isinstance(runtime, dict) else None
                if isinstance(restart, str):
                    service_def["restart"] = restart
                else:
                    service_def["restart"] = "unless-stopped"

                # Ports from network config
                network_cfg = member_ext.get("network") or member.get("network") or {}
                ports = network_cfg.get("ports") if isinstance(network_cfg, dict) else None
                if isinstance(ports, list) and ports:
                    service_def["ports"] = [str(p) for p in ports]

                # Volumes
                volumes = member_ext.get("volumes") or member.get("volumes")
                if isinstance(volumes, list) and volumes:
                    vol_entries: list[str] = []
                    for vol in volumes:
                        if isinstance(vol, str):
                            vol_entries.append(vol)
                        elif isinstance(vol, dict):
                            src = vol.get("source", vol.get("host_path", ""))
                            dst = vol.get("target", vol.get("container_path", ""))
                            if src and dst:
                                vol_entries.append(f"{src}:{dst}")
                    if vol_entries:
                        service_def["volumes"] = vol_entries

                # Environment variables
                env = member_ext.get("environment") or member.get("environment")
                if isinstance(env, dict) and env:
                    service_def["environment"] = {
                        str(k): str(v) for k, v in env.items()
                    }
                elif isinstance(env, list) and env:
                    service_def["environment"] = [str(e) for e in env]

                # Networks
                member_networks = member_ext.get("networks") or member.get("networks")
                if isinstance(member_networks, list) and member_networks:
                    net_names: list[str] = []
                    for net in member_networks:
                        if isinstance(net, str):
                            net_names.append(net)
                        elif isinstance(net, dict):
                            name = net.get("name") or net.get("network_ref", "")
                            if isinstance(name, str) and name:
                                # Strip scope prefix if present
                                parts = name.split(".")
                                net_names.append(parts[-1] if parts else name)
                    if net_names:
                        service_def["networks"] = net_names

                services[ref] = service_def

            if not services:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7931",
                        severity="warning",
                        stage=stage,
                        message=f"Stack '{stack_id}' has no resolvable members; skipping.",
                        path=f"instance:docker:{stack_id}",
                    )
                )
                continue

            # Build compose document
            compose: dict[str, Any] = {"version": compose_version}
            compose["services"] = services

            # Networks section
            if isinstance(shared_networks, list) and shared_networks:
                nets_section: dict[str, Any] = {}
                for net in shared_networks:
                    if not isinstance(net, dict):
                        continue
                    name = net.get("name")
                    if not isinstance(name, str):
                        continue
                    net_def: dict[str, Any] = {}
                    driver = net.get("driver")
                    if isinstance(driver, str):
                        net_def["driver"] = driver
                    if net.get("external"):
                        net_def["external"] = True
                    nets_section[name] = net_def if net_def else None
                if nets_section:
                    compose["networks"] = nets_section

            # Volumes section
            if isinstance(shared_volumes, list) and shared_volumes:
                vols_section: dict[str, Any] = {}
                for vol in shared_volumes:
                    if not isinstance(vol, dict):
                        continue
                    name = vol.get("name")
                    if not isinstance(name, str):
                        continue
                    vol_def: dict[str, Any] = {}
                    driver = vol.get("driver")
                    if isinstance(driver, str) and driver != "local":
                        vol_def["driver"] = driver
                    if vol.get("external"):
                        vol_def["external"] = True
                    vols_section[name] = vol_def if vol_def else None
                if vols_section:
                    compose["volumes"] = vols_section

            # Write compose file
            host_dir = compose_root / host_ref / stack_name
            output_path = host_dir / "docker-compose.yaml"
            content = yaml.dump(
                compose,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
            self.write_text_atomic(output_path, content)
            generated_files.append(str(output_path))

            diagnostics.append(
                self.emit_diagnostic(
                    code="I7930",
                    severity="info",
                    stage=stage,
                    message=(
                        f"Generated docker-compose.yaml for stack '{stack_name}' "
                        f"on host '{host_ref}' with {len(services)} services."
                    ),
                    path=str(output_path),
                )
            )

        self.publish_if_possible(ctx, "compose_files", generated_files)
        self.publish_if_possible(ctx, "compose_dir", str(compose_root))

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "compose_dir": str(compose_root),
                "compose_files": generated_files,
            },
        )

    def _collect_rows(self, ctx: PluginContext) -> list[dict[str, Any]]:
        """Collect normalized rows from compiled_json or pipeline subscription."""
        # Prefer compiled_json (available in both pipeline and test contexts)
        payload = ctx.compiled_json
        if isinstance(payload, dict):
            instances = payload.get("instances")
            if isinstance(instances, dict):
                rows: list[dict[str, Any]] = []
                for group_rows in instances.values():
                    if isinstance(group_rows, list):
                        for row in group_rows:
                            if isinstance(row, dict):
                                rows.append(row)
                if rows:
                    return rows

        # Fallback: try pipeline subscription
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except Exception:
            rows_payload = None

        if isinstance(rows_payload, list):
            return [item for item in rows_payload if isinstance(item, dict)]
        return []

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}
