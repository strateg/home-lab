"""Docker container reference validator (ADR 0087 Phase 1)."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class DockerRefsValidator(ValidatorJsonPlugin):
    """Validate Docker container references and host capabilities.

    This validator enforces ADR 0087 Docker promotion requirements:
    - host_ref must target L1 device or L4 LXC container
    - Host must declare docker capability (cap.compute.runtime.container_host
      or vendor.runtime.docker.host)
    - Image reference must be valid format (if present)
    - Network references must resolve (if present)
    - Storage/volume references must resolve (if present)
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _DOCKER_CLASSES = {"class.compute.workload.docker"}
    _DOCKER_HOST_CAPABILITIES = {
        "cap.compute.runtime.container_host",
        "vendor.runtime.docker.host",
        "docker",  # Simplified capability name
    }
    _VALID_HOST_CLASSES = {
        # L1 devices that can host Docker
        "class.compute.edge_node",
        "class.compute.hypervisor",
        "class.compute.hypervisor.proxmox",
        "class.router",  # MikroTik with containerD
        # L4 LXC that can host Docker (Docker-in-LXC)
        "class.compute.workload.lxc",
    }

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
                    message=f"docker_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        # Build lookup
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # Validate each Docker container
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref not in self._DOCKER_CLASSES:
                continue

            row_id = row.get("instance")
            group = row.get("group", "docker")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = self._extensions(row)

            # Get host_ref
            host_ref = self._extract_host_ref(row)

            # Validate host_ref exists
            if not host_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7891",
                        severity="error",
                        stage=stage,
                        message=f"Docker container '{row_id}' requires host_ref.",
                        path=f"{row_prefix}.host_ref",
                    )
                )
                continue

            # Validate host_ref target exists
            host_row = row_by_id.get(host_ref)
            if not isinstance(host_row, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7891",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Docker container '{row_id}' host_ref '{host_ref}' " "does not reference a known instance."
                        ),
                        path=f"{row_prefix}.host_ref",
                    )
                )
                continue

            # Validate host is L1 device or L4 LXC
            host_layer = host_row.get("layer")
            host_class = host_row.get("class_ref")
            if host_layer not in ("L1", "L4"):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7891",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Docker container '{row_id}' host_ref '{host_ref}' "
                            f"must target L1 or L4 (got '{host_layer}')."
                        ),
                        path=f"{row_prefix}.host_ref",
                    )
                )
            elif host_layer == "L4" and host_class != "class.compute.workload.lxc":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7891",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Docker container '{row_id}' L4 host_ref '{host_ref}' "
                            f"must be class.compute.workload.lxc (got '{host_class}')."
                        ),
                        path=f"{row_prefix}.host_ref",
                    )
                )

            # Validate host has docker capability
            self._validate_host_docker_capability(
                row_id=row_id,
                host_ref=host_ref,
                host_row=host_row,
                row_by_id=row_by_id,
                row_prefix=row_prefix,
                stage=stage,
                diagnostics=diagnostics,
            )

            # Validate image reference (if present)
            image = None
            if "image" in extensions:
                image = extensions.get("image")
            elif "image" in row:
                image = row.get("image")
            if image is not None:
                self._validate_image_ref(
                    row_id=row_id,
                    image=image,
                    row_prefix=row_prefix,
                    stage=stage,
                    diagnostics=diagnostics,
                )

            # Validate network references (if present)
            networks = extensions.get("networks") or row.get("networks")
            if isinstance(networks, list):
                for idx, network in enumerate(networks):
                    if isinstance(network, dict):
                        self._validate_network_ref(
                            row_id=row_id,
                            network=network,
                            idx=idx,
                            row_by_id=row_by_id,
                            row_prefix=row_prefix,
                            stage=stage,
                            diagnostics=diagnostics,
                        )

            # Validate storage/volume references (if present)
            storage = extensions.get("storage") or row.get("storage")
            if isinstance(storage, dict):
                volumes = storage.get("volumes")
                if isinstance(volumes, list):
                    for idx, volume in enumerate(volumes):
                        if isinstance(volume, dict):
                            self._validate_volume_ref(
                                row_id=row_id,
                                volume=volume,
                                idx=idx,
                                row_by_id=row_by_id,
                                row_prefix=row_prefix,
                                stage=stage,
                                diagnostics=diagnostics,
                            )

        return self.make_result(diagnostics)

    def _extract_host_ref(self, row: dict[str, Any]) -> str | None:
        """Extract host_ref from row (extensions or top-level)."""
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            host_ref = extensions.get("host_ref")
            if isinstance(host_ref, str) and host_ref:
                return host_ref
            device_ref = extensions.get("device_ref")
            if isinstance(device_ref, str) and device_ref:
                return device_ref

        host_ref = row.get("host_ref")
        if isinstance(host_ref, str) and host_ref:
            return host_ref
        device_ref = row.get("device_ref")
        if isinstance(device_ref, str) and device_ref:
            return device_ref

        return None

    def _validate_host_docker_capability(
        self,
        *,
        row_id: Any,
        host_ref: str,
        host_row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        row_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate host has docker capability."""
        # Check capabilities on host row
        host_caps = self._get_capabilities(host_row)

        # For L4 LXC hosts, also check if it has docker feature enabled
        host_class = host_row.get("class_ref")
        if host_class == "class.compute.workload.lxc":
            extensions = self._extensions(host_row)
            features = extensions.get("features") or host_row.get("features")
            if isinstance(features, dict):
                nesting = features.get("nesting")
                if nesting is not True:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7892",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Docker container '{row_id}' host LXC '{host_ref}' "
                                "should have features.nesting=true for Docker-in-LXC."
                            ),
                            path=f"{row_prefix}.host_ref",
                        )
                    )

        # Check for docker capability
        if not self._has_docker_capability(host_caps):
            # Also check vendor capabilities
            vendor_caps = host_row.get("vendor_capabilities")
            if isinstance(vendor_caps, list):
                host_caps.extend(vendor_caps)

            if not self._has_docker_capability(host_caps):
                # ADR 0087 §5h: During migration period, emit WARNING instead of ERROR
                # This will become ERROR in Phase 3 when migration_mode=migrated
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7892",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Docker container '{row_id}' host '{host_ref}' lacks docker capability. "
                            f"Expected one of: {sorted(self._DOCKER_HOST_CAPABILITIES)}. "
                            "This will become ERROR in Phase 3."
                        ),
                        path=f"{row_prefix}.host_ref",
                    )
                )

    def _has_docker_capability(self, capabilities: list[Any]) -> bool:
        """Check if capabilities list contains docker capability."""
        for cap in capabilities:
            if not isinstance(cap, str):
                continue
            cap_lower = cap.strip().lower()
            if any(docker_cap.lower() in cap_lower for docker_cap in self._DOCKER_HOST_CAPABILITIES):
                return True
        return False

    def _get_capabilities(self, row: dict[str, Any]) -> list[Any]:
        """Get capabilities from row."""
        extensions = self._extensions(row)
        caps = extensions.get("capabilities") or row.get("capabilities")
        if isinstance(caps, list):
            return list(caps)
        return []

    def _validate_image_ref(
        self,
        *,
        row_id: Any,
        image: Any,
        row_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate Docker image reference format."""
        if isinstance(image, str):
            # Simple string format: "image:tag" or "registry/image:tag"
            if not image.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7893",
                        severity="error",
                        stage=stage,
                        message=f"Docker container '{row_id}' image must be non-empty.",
                        path=f"{row_prefix}.image",
                    )
                )
        elif isinstance(image, dict):
            # Structured format: {repository: "...", tag: "...", registry: "..."}
            repository = image.get("repository")
            if not isinstance(repository, str) or not repository.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7893",
                        severity="error",
                        stage=stage,
                        message=f"Docker container '{row_id}' image.repository must be non-empty string.",
                        path=f"{row_prefix}.image.repository",
                    )
                )
        else:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7893",
                    severity="error",
                    stage=stage,
                    message=f"Docker container '{row_id}' image must be string or object.",
                    path=f"{row_prefix}.image",
                )
            )

    def _validate_network_ref(
        self,
        *,
        row_id: Any,
        network: dict[str, Any],
        idx: int,
        row_by_id: dict[str, dict[str, Any]],
        row_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate network reference in Docker container."""
        network_ref = network.get("network_ref")
        if network_ref and isinstance(network_ref, str):
            target = row_by_id.get(network_ref)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7894",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Docker container '{row_id}' network_ref '{network_ref}' "
                            "does not reference a known instance."
                        ),
                        path=f"{row_prefix}.networks[{idx}].network_ref",
                    )
                )

    def _validate_volume_ref(
        self,
        *,
        row_id: Any,
        volume: dict[str, Any],
        idx: int,
        row_by_id: dict[str, dict[str, Any]],
        row_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate volume reference in Docker container."""
        volume_ref = volume.get("volume_ref") or volume.get("storage_ref")
        if volume_ref and isinstance(volume_ref, str):
            target = row_by_id.get(volume_ref)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7895",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Docker container '{row_id}' volume_ref '{volume_ref}' "
                            "does not reference a known instance."
                        ),
                        path=f"{row_prefix}.storage.volumes[{idx}].volume_ref",
                    )
                )

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        """Get extensions dict from row."""
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}
