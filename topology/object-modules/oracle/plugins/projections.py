#!/usr/bin/env python3
"""Oracle Cloud (OCI) projection helpers for object generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from plugins.generators.projection_core import (
    GROUP_VM,
    ProjectionError,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _require_object_ref,
    _resolved_object_ref,
    _sorted_rows,
)


# Default OCI agent plugins configuration (matching original Terraform)
DEFAULT_AGENT_PLUGINS = [
    {"name": "Vulnerability Scanning", "state": "DISABLED"},
    {"name": "OS Management Hub Agent", "state": "DISABLED"},
    {"name": "Management Agent", "state": "DISABLED"},
    {"name": "Custom Logs Monitoring", "state": "ENABLED"},
    {"name": "Compute RDMA GPU Monitoring", "state": "DISABLED"},
    {"name": "Compute Instance Monitoring", "state": "ENABLED"},
    {"name": "Compute HPC RDMA Auto-Configuration", "state": "DISABLED"},
    {"name": "Compute HPC RDMA Authentication", "state": "DISABLED"},
    {"name": "Cloud Guard Workload Protection", "state": "ENABLED"},
    {"name": "Block Volume Management", "state": "DISABLED"},
    {"name": "Bastion", "state": "DISABLED"},
]


@dataclass
class OCIInstance:
    """Typed OCI compute instance for Terraform generation."""

    id: str
    instance_id: str
    resource_name: str
    display_name: str
    region: str
    availability_domain: str
    shape: str
    ocpus: int
    memory_gb: int
    vnic_name: str
    public_ip: bool = True
    pv_encryption: bool = True
    agent_plugins: list[dict[str, str]] = field(default_factory=list)
    description: str = ""


def _is_oci_instance(row: dict[str, Any]) -> bool:
    """Check if row is an Oracle Cloud instance."""
    object_ref = _resolved_object_ref(row)
    return object_ref == "obj.oracle.cloud_vm"


def _safe_resource_name(instance_id: str) -> str:
    """Convert instance_id to valid Terraform resource name."""
    # Replace dots and dashes with underscores
    return instance_id.replace(".", "_").replace("-", "_")


def build_oci_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for OCI Terraform generator."""
    groups = _instance_groups(compiled_json)
    vm_rows = _group_rows(groups, canonical=GROUP_VM)

    oci_instances: list[dict[str, Any]] = []
    regions: set[str] = set()

    for idx, row in enumerate(vm_rows):
        if not _is_oci_instance(row):
            continue

        instance_id = _require_non_empty_str(
            row, field="instance_id", path=f"compiled_json.instances.vm[{idx}]"
        )
        _require_object_ref(row, path=f"compiled_json.instances.vm[{idx}]")

        # Extract OCI-specific configuration from instance_data
        instance_data_block = row.get("instance_data", {})
        if not isinstance(instance_data_block, dict):
            instance_data_block = {}
        oci_config = instance_data_block.get("oci", {})
        if not isinstance(oci_config, dict):
            raise ProjectionError(
                f"compiled_json.instances.vm[{idx}].instance_data.oci must be mapping/object"
            )

        region = oci_config.get("region", "")
        if region:
            regions.add(region)

        # Build instance data
        instance_data = {
            "instance_id": instance_id,
            "resource_name": _safe_resource_name(instance_id),
            "display_name": oci_config.get("display_name", instance_id),
            "region": region,
            "availability_domain": oci_config.get("availability_domain", ""),
            "shape": oci_config.get("shape", "VM.Standard.A1.Flex"),
            "ocpus": oci_config.get("ocpus", 1),
            "memory_gb": oci_config.get("memory_gb", 6),
            "vnic_name": oci_config.get("vnic_name", f"{instance_id}-vnic"),
            "public_ip": oci_config.get("public_ip", True),
            "pv_encryption": oci_config.get("pv_encryption", True),
            "agent_plugins": oci_config.get("agent_plugins", DEFAULT_AGENT_PLUGINS),
            "description": row.get("notes", ""),
        }
        oci_instances.append(instance_data)

    # Determine primary region for default availability domain
    primary_region = sorted(regions)[0] if regions else "eu-frankfurt-1"

    return {
        "instances": _sorted_rows(oci_instances),
        "regions": sorted(regions),
        "primary_region": primary_region,
        "counts": {
            "instances": len(oci_instances),
            "regions": len(regions),
        },
    }


def build_oci_instances_typed(compiled_json: dict[str, Any]) -> list[OCIInstance]:
    """Build typed OCI instance list for generator."""
    projection = build_oci_projection(compiled_json)
    result: list[OCIInstance] = []
    for row in projection["instances"]:
        result.append(
            OCIInstance(
                id=row["instance_id"],
                instance_id=row["instance_id"],
                resource_name=row["resource_name"],
                display_name=row["display_name"],
                region=row["region"],
                availability_domain=row["availability_domain"],
                shape=row["shape"],
                ocpus=row["ocpus"],
                memory_gb=row["memory_gb"],
                vnic_name=row["vnic_name"],
                public_ip=row["public_ip"],
                pv_encryption=row["pv_encryption"],
                agent_plugins=row.get("agent_plugins", DEFAULT_AGENT_PLUGINS),
                description=row.get("description", ""),
            )
        )
    return result
