"""Type definitions for topology generators."""

from .generators import (
    DeviceSpec,
    DiagramConfig,
    GeneratorConfig,
    IconPackSpec,
    LayerSpec,
    MountSpec,
    NetworkConfig,
    ResourceSpec,
    StorageSpec,
    TemplateContext,
)
from .topology import (
    L0Meta,
    L1Foundation,
    L2Network,
    L3Compute,
    L3Data,
    L4Platform,
    L5Application,
    L5Security,
    L6Governance,
    L6Observability,
    L7Operations,
    TopologyV4Structure,
)

__all__ = [
    # Generator types
    "DeviceSpec",
    "NetworkConfig",
    "ResourceSpec",
    "GeneratorConfig",
    "StorageSpec",
    "MountSpec",
    "LayerSpec",
    "IconPackSpec",
    "DiagramConfig",
    "TemplateContext",
    # Topology structure types
    "TopologyV4Structure",
    "L0Meta",
    "L1Foundation",
    "L2Network",
    "L3Compute",
    "L3Data",
    "L4Platform",
    "L5Security",
    "L5Application",
    "L6Governance",
    "L6Observability",
    "L7Operations",
]
