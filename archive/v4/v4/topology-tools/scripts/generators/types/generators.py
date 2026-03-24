"""Type definitions for generator configuration and common data structures."""

from typing import Any, Dict, List, Literal, Optional, TypedDict


class DeviceSpec(TypedDict, total=False):
    """Device specification from topology."""

    id: str
    type: str
    name: str
    device_class: str  # 'class' is a Python keyword
    role: str
    location: str
    vendor: str
    model: str
    description: Optional[str]
    management_ip: Optional[str]
    # Additional fields as needed
    tags: Optional[List[str]]
    metadata: Optional[Dict[str, Any]]


class NetworkConfig(TypedDict, total=False):
    """Network configuration specification."""

    id: str
    name: str
    cidr: str
    gateway: Optional[str]
    vlan_id: Optional[int]
    description: Optional[str]
    layer: Optional[str]
    type: Optional[str]


class ResourceSpec(TypedDict, total=False):
    """Resource allocation specification for VMs/containers."""

    cpu: int
    cores: Optional[int]
    sockets: Optional[int]
    memory_mb: int
    disk_gb: Optional[int]
    storage: Optional[List[str]]


class StorageSpec(TypedDict, total=False):
    """Storage device specification."""

    id: str
    type: str
    size_gb: int
    device: Optional[str]
    mount_type: Optional[Literal["soldered", "replaceable", "removable"]]
    slot_id: Optional[str]
    media_id: Optional[str]


class MountSpec(TypedDict, total=False):
    """Filesystem mount specification."""

    mount_point: str
    filesystem: str
    size_gb: Optional[int]
    storage_endpoint_ref: Optional[str]


class LayerSpec(TypedDict, total=False):
    """Generic layer specification."""

    id: str
    type: str
    name: Optional[str]
    config: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]


class GeneratorConfig(TypedDict, total=False):
    """Generator runtime configuration."""

    topology_path: str
    output_dir: str
    templates_dir: str
    skip_components: List[str]
    dry_run: bool
    verbose: bool
    force: bool
    # Docs generator specific
    mermaid_icons: Optional[bool]
    mermaid_icon_nodes: Optional[bool]
    # Terraform generator specific
    provider: Optional[str]
    terraform_version: Optional[str]


class IconPackSpec(TypedDict, total=False):
    """Icon pack specification for documentation generation."""

    pack_id: str
    prefix: str
    name: str
    icons: Dict[str, Any]
    width: Optional[int]
    height: Optional[int]


class DiagramConfig(TypedDict, total=False):
    """Diagram generation configuration."""

    type: Literal["mermaid", "graphviz", "plantuml"]
    direction: Optional[Literal["TB", "BT", "LR", "RL"]]
    show_icons: bool
    show_labels: bool
    icon_mode: Optional[Literal["none", "compat", "icon-nodes"]]


class TemplateContext(TypedDict, total=False):
    """Context passed to Jinja2 templates."""

    topology: Dict[str, Any]
    devices: List[DeviceSpec]
    networks: List[NetworkConfig]
    generated_at: str
    generator_version: str
    config: GeneratorConfig
