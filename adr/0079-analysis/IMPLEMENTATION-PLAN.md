# ADR 0079 Implementation Plan

**ADR:** `adr/0079-v5-documentation-and-diagram-generation-migration.md`
**Date:** 2026-03-24
**Status:** Planning
**Architecture:** Projection-First Rewrite (Alternative B)

---

## Overview

Migrate v4 documentation generator (19 templates) to v5 plugin architecture using projection-first design per ADR 0074.

### Current State

| Metric | V4 | V5 | Gap |
|--------|----|----|-----|
| Templates | 19 | 3 | 16 |
| Projections | N/A (direct access) | 1 | 5 new modules |
| Icon support | Full | None | Full system |
| Mermaid validation | Yes | No | New plugin |

### Architectural Decision

Selected **Alternative B: Projection-First Rewrite** per ADR 0079.

Key principles:
1. Templates consume projections, not compiled model directly
2. Icon system extracted to reusable module
3. Mermaid validation as separate plugin
4. Template sets enable selective generation

---

## V5 Model Mapping Reference

The v5 compiled model differs significantly from v4's flat layer structure. This section documents the mapping for projection development.

### Instance Group Access Pattern

```python
from plugins.generators.projection_core import (
    _instance_groups,
    _group_rows,
    _sorted_rows,
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_LXC,
    GROUP_VMS,
    GROUP_SERVICES,
)

def build_example_projection(compiled_json: dict) -> dict:
    """Example projection showing v5 access pattern."""
    groups = _instance_groups(compiled_json)

    # Get typed instance collections
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    networks = _group_rows(groups, canonical=GROUP_NETWORK)

    # Process rows - each row has standard fields
    for row in devices:
        instance_id = row.get("instance_id")      # Unique instance identifier
        object_ref = row.get("object_ref")        # Reference to object definition
        class_ref = row.get("class_ref")          # Reference to class definition
        status = row.get("status")                # active | draft | deprecated
        instance_data = row.get("instance_data", {})  # Instance-specific data

    return {"rows": _sorted_rows(processed_rows)}
```

### V4-to-V5 Mapping Table

| V4 Pattern | V5 Pattern | Notes |
|------------|------------|-------|
| `topology["L1_foundation"]["devices"]` | `groups.get("devices", [])` | Use GROUP_DEVICES constant |
| `topology["L2_network"]["networks"]` | `groups.get("network", [])` | Note: singular "network" |
| `topology["L2_network"]["bridges"]` | `groups.get("bridges", [])` | May be separate group |
| `topology["L2_network"]["trust_zones"]` | `groups.get("trust_zones", [])` | Or nested in L2 instances |
| `topology["L4_platform"]["lxc"]` | `groups.get("lxc", [])` | Use GROUP_LXC constant |
| `topology["L4_platform"]["vms"]` | `groups.get("vms", [])` | Use GROUP_VMS constant |
| `topology["L5_application"]["services"]` | `groups.get("services", [])` | Use GROUP_SERVICES constant |
| `topology["L6_observability"]["healthchecks"]` | `groups.get("healthchecks", [])` | New group name |
| `topology["L6_observability"]["alerts"]` | `groups.get("alerts", [])` | New group name |
| Direct field access (`device["id"]`) | `row.get("instance_id")` | Use instance_id |
| Inline data (`device["type"]`) | `row.get("instance_data", {}).get("type")` | Check both locations |

### Hierarchical Instance Groups

V5 supports hierarchical instance directories (e.g., `L6-observability/healthchecks`). The compiler flattens these into group names:

```python
# Instance location: topology/instances/L6-observability/healthchecks/*.yaml
# Group name in compiled_json: "healthchecks"

# Instance location: topology/instances/L3-data/data-assets/*.yaml
# Group name in compiled_json: "data-assets"
```

### Reference Resolution

V5 compiler resolves most references during compilation. However, some cross-group references may still be unresolved strings:

```python
def _resolve_device_for_lxc(lxc_row: dict, device_rows: list) -> dict | None:
    """Resolve device reference for LXC container."""
    instance_data = lxc_row.get("instance_data", {})
    device_ref = instance_data.get("device_ref")
    if not device_ref:
        return None
    # Find device by instance_id
    for device in device_rows:
        if device.get("instance_id") == device_ref:
            return device
    return None
```

---

## Directory Structure

```
v5/topology-tools/
├── plugins/
│   ├── generators/
│   │   ├── docs_generator.py              # Extended generator plugin
│   │   ├── projections.py                 # Existing (extended)
│   │   ├── projection_core.py             # Existing
│   │   └── docs/                          # NEW: Domain projections
│   │       ├── __init__.py
│   │       ├── network_projection.py
│   │       ├── physical_projection.py
│   │       ├── security_projection.py
│   │       ├── storage_projection.py
│   │       └── operations_projection.py
│   ├── validators/
│   │   └── mermaid_validator.py           # NEW: Post-generation validator
│   └── icons/                             # NEW: Icon system
│       ├── __init__.py
│       ├── icon_manager.py
│       ├── mappings.py
│       └── mermaid_helpers.py
├── templates/docs/
│   ├── _partials/                         # NEW: Shared macros
│   │   ├── mermaid_header.j2
│   │   ├── icon_node.j2
│   │   └── footer.j2
│   ├── overview.md.j2                     # Existing (in core/)
│   ├── devices.md.j2                      # Existing (in core/)
│   ├── services.md.j2                     # Existing (in core/)
│   ├── network-diagram.md.j2              # Phase A
│   ├── ip-allocation.md.j2                # Phase A
│   ├── physical-topology.md.j2            # Phase B
│   ├── data-links-topology.md.j2          # Phase B
│   ├── power-links-topology.md.j2         # Phase B
│   ├── vlan-topology.md.j2                # Phase C
│   ├── trust-zones.md.j2                  # Phase C
│   ├── service-dependencies.md.j2         # Phase D
│   ├── storage-topology.md.j2             # Phase D
│   ├── monitoring-topology.md.j2          # Phase E
│   ├── vpn-topology.md.j2                 # Phase E
│   ├── certificates-topology.md.j2        # Phase E
│   ├── qos-topology.md.j2                 # Phase E
│   ├── ups-topology.md.j2                 # Phase E
│   ├── icon-legend.md.j2                  # Phase F
│   └── diagrams-index.md.j2               # Phase F
└── validate-mermaid-render.py             # Phase F (standalone CLI)
```

---

## Projection Dataclass Specifications

Each projection module defines typed dataclasses for clear contracts. These are the normative specifications.

### Network Projection Dataclasses

```python
# File: v5/topology-tools/plugins/generators/docs/network_projection.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class NetworkRow:
    """Network instance for documentation."""
    instance_id: str
    object_ref: str
    name: str
    cidr: str
    vlan_tag: Optional[int] = None
    trust_zone_ref: Optional[str] = None
    gateway: Optional[str] = None
    ip_allocations: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class AllocationRow:
    """IP allocation for documentation."""
    network_id: str
    ip: str
    device_ref: Optional[str] = None
    interface: Optional[str] = None
    description: Optional[str] = None

@dataclass
class BridgeRow:
    """Bridge definition for documentation."""
    id: str
    name: str
    vlan_aware: bool = False
    network_refs: list[str] = field(default_factory=list)

@dataclass
class NetworkProjection:
    """Network documentation projection."""
    networks: list[NetworkRow]
    allocations: list[AllocationRow]
    bridges: list[BridgeRow]
    counts: dict[str, int]
```

### Physical Projection Dataclasses

```python
# File: v5/topology-tools/plugins/generators/docs/physical_projection.py
@dataclass
class DeviceRow:
    """Device instance for documentation."""
    instance_id: str
    object_ref: str
    class_ref: Optional[str] = None
    name: str = ""
    type: str = ""
    device_class: str = ""
    model: str = ""
    location: str = ""
    status: str = "active"
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    specs: dict[str, Any] = field(default_factory=dict)

@dataclass
class LinkRow:
    """Physical link for documentation."""
    id: str
    endpoint_a: dict[str, str]  # device_ref or external_ref
    endpoint_b: dict[str, str]
    link_type: str = ""  # ethernet, fiber, power
    speed: Optional[str] = None
    description: str = ""

@dataclass
class StorageSlotRow:
    """Storage slot view for device."""
    slot_id: str
    slot_bus: Optional[str] = None
    slot_name: Optional[str] = None
    attachment_id: Optional[str] = None
    attachment_state: str = "empty"
    media: Optional[dict[str, Any]] = None

@dataclass
class PhysicalProjection:
    """Physical topology projection."""
    devices: list[DeviceRow]
    data_links: list[LinkRow]
    power_links: list[LinkRow]
    storage_slots: dict[str, list[StorageSlotRow]]  # device_id -> slots
    locations: list[dict[str, Any]]
    external_refs: list[str]
    counts: dict[str, int]
```

### Security Projection Dataclasses

```python
# File: v5/topology-tools/plugins/generators/docs/security_projection.py
@dataclass
class TrustZoneRow:
    """Trust zone for documentation."""
    id: str
    name: str
    description: str = ""
    trust_level: int = 0

@dataclass
class VlanRow:
    """VLAN configuration for documentation."""
    tag: int
    network_id: str
    name: str = ""
    trust_zone_ref: Optional[str] = None

@dataclass
class FirewallPolicyRow:
    """Firewall policy for documentation."""
    id: str
    name: str
    priority: int = 999
    action: str = "drop"
    source_zone_ref: Optional[str] = None
    dest_zone_ref: Optional[str] = None
    source_network_ref: Optional[str] = None
    dest_network_ref: Optional[str] = None
    protocols: list[str] = field(default_factory=list)

@dataclass
class SecurityProjection:
    """Security topology projection."""
    trust_zones: list[TrustZoneRow]
    vlans: list[VlanRow]
    firewall_policies: list[FirewallPolicyRow]
    zone_network_bindings: dict[str, list[str]]  # zone_id -> network_ids
    network_policy_bindings: list[dict[str, Any]]
    counts: dict[str, int]
```

### Storage Projection Dataclasses

```python
# File: v5/topology-tools/plugins/generators/docs/storage_projection.py
@dataclass
class StoragePoolRow:
    """Storage pool/endpoint for documentation."""
    id: str
    name: str
    device_ref: Optional[str] = None
    path: Optional[str] = None
    media: Optional[str] = None  # nvme, ssd, hdd
    capacity_gb: Optional[int] = None
    purpose: str = ""

@dataclass
class DataAssetRow:
    """Data asset for documentation."""
    id: str
    name: str
    asset_type: str = ""  # backup, database, media, config
    storage_endpoint_refs: list[str] = field(default_factory=list)
    runtime_refs: list[str] = field(default_factory=list)
    mount_paths: list[str] = field(default_factory=list)
    backup_status: str = ""

@dataclass
class MountChainRow:
    """Mount chain for storage topology."""
    device_id: str
    pool_id: str
    asset_id: Optional[str] = None
    mount_path: Optional[str] = None

@dataclass
class StorageProjection:
    """Storage topology projection."""
    storage_pools: list[StoragePoolRow]
    data_assets: list[DataAssetRow]
    mount_chains: list[MountChainRow]
    device_blocks: list[dict[str, Any]]  # Grouped by device
    counts: dict[str, int]
```

### Operations Projection Dataclasses

```python
# File: v5/topology-tools/plugins/generators/docs/operations_projection.py
@dataclass
class HealthcheckRow:
    """Healthcheck for documentation."""
    id: str
    name: str
    check_type: str = ""
    target_ref: Optional[str] = None
    interval: str = ""
    timeout: str = ""
    tags: list[str] = field(default_factory=list)

@dataclass
class AlertRow:
    """Alert for documentation."""
    id: str
    name: str
    severity: str = "info"
    healthcheck_ref: Optional[str] = None
    notification_channels: list[str] = field(default_factory=list)

@dataclass
class VpnTunnelRow:
    """VPN tunnel for documentation."""
    id: str
    name: str
    vpn_type: str = ""  # wireguard, tailscale, openvpn
    network_ref: Optional[str] = None
    peer_count: int = 0

@dataclass
class CertificateRow:
    """Certificate for documentation."""
    id: str
    name: str
    cert_type: str = ""  # ca, server, client
    issuer: Optional[str] = None
    valid_days: int = 0
    distribution: list[str] = field(default_factory=list)

@dataclass
class QosPolicyRow:
    """QoS policy for documentation."""
    id: str
    name: str
    network_ref: Optional[str] = None
    download_limit: Optional[str] = None
    upload_limit: Optional[str] = None

@dataclass
class UpsPolicyRow:
    """UPS policy for documentation."""
    id: str
    name: str
    ups_device_ref: Optional[str] = None
    protected_devices: list[str] = field(default_factory=list)
    shutdown_delay: int = 0

@dataclass
class OperationsProjection:
    """Operations topology projection."""
    healthchecks: list[HealthcheckRow]
    alerts: list[AlertRow]
    dashboards: list[dict[str, Any]]
    vpn_tunnels: list[VpnTunnelRow]
    certificates: list[CertificateRow]
    qos_policies: list[QosPolicyRow]
    ups_policies: list[UpsPolicyRow]
    notification_channels: list[dict[str, Any]]
    counts: dict[str, int]
```

---

## Phase 0: Foundation (Pre-requisite)

### 0.1 Icon System Module

**File:** `v5/topology-tools/plugins/icons/__init__.py`

```python
"""Icon system for documentation generation."""
from .icon_manager import IconManager
from .mappings import (
    DEVICE_ICON_BY_TYPE,
    DEVICE_ICON_BY_CLASS,
    CLOUD_PROVIDER_ICON,
    ZONE_ICON_MAP,
    NETWORK_ICON_BY_ZONE,
    SERVICE_ICON_BY_TYPE,
    STORAGE_POOL_ICON_BY_MEDIA,
    DATA_ASSET_ICON_BY_TYPE,
    ALERT_ICON_BY_SEVERITY,
    CHANNEL_ICON_BY_TYPE,
    POWER_ICONS,
)

__all__ = [
    "IconManager",
    "DEVICE_ICON_BY_TYPE",
    # ... all exports
]
```

**File:** `v5/topology-tools/plugins/icons/mappings.py`

Port all icon mappings from `v4/topology-tools/scripts/generators/docs/diagrams/__init__.py`:

```python
"""Icon mappings for documentation diagrams.

Constants extracted from v4 DiagramDocumentationGenerator.
"""
from typing import Dict

# Device type to icon mapping
DEVICE_ICON_BY_TYPE: Dict[str, str] = {
    "hypervisor": "si:proxmox",
    "router": "mdi:router-network",
    "sbc": "mdi:chip",
    "switch": "mdi:switch",
    "ap": "mdi:access-point",
    "nas": "mdi:nas",
    "cloud-vm": "mdi:cloud-outline",
    "ups": "mdi:battery-charging-high",
    "pdu": "mdi:power-socket-eu",
    "firewall": "mdi:wall-fire",
    "load-balancer": "mdi:scale-balance",
    "container-host": "mdi:docker",
    "workstation": "mdi:desktop-tower-monitor",
    "laptop": "mdi:laptop",
    "phone": "mdi:cellphone",
    "iot-device": "mdi:home-automation",
}

DEVICE_ICON_BY_CLASS: Dict[str, str] = {
    "network": "mdi:router-network",
    "compute": "mdi:server",
    "storage": "mdi:database",
    "power": "mdi:flash",
    "external": "mdi:cloud-outline",
}

CLOUD_PROVIDER_ICON: Dict[str, str] = {
    "oracle": "si:oracle",
    "hetzner": "si:hetzner",
    "aws": "si:amazonaws",
    "gcp": "si:googlecloud",
    "azure": "si:microsoftazure",
    "digitalocean": "si:digitalocean",
}

ZONE_ICON_MAP: Dict[str, str] = {
    "untrusted": "mdi:earth",
    "guest": "mdi:account-question",
    "user": "mdi:account-group",
    "iot": "mdi:home-automation",
    "servers": "mdi:server",
    "management": "mdi:shield-crown",
}

NETWORK_ICON_BY_ZONE: Dict[str, str] = {
    "untrusted": "mdi:earth",
    "guest": "mdi:wifi-strength-1-alert",
    "user": "mdi:lan",
    "iot": "mdi:lan-pending",
    "servers": "mdi:server-network",
    "management": "mdi:shield-crown",
}

SERVICE_ICON_BY_TYPE: Dict[str, str] = {
    "database": "mdi:database",
    "cache": "mdi:database-clock",
    "web-application": "mdi:web",
    "web-ui": "mdi:view-dashboard",
    "media-server": "mdi:multimedia",
    "monitoring": "mdi:chart-line",
    "alerting": "mdi:bell-alert",
    "logging": "mdi:file-document-outline",
    "visualization": "mdi:chart-areaspline",
    "dns": "mdi:dns",
    "vpn": "mdi:vpn",
}

STORAGE_POOL_ICON_BY_MEDIA: Dict[str, str] = {
    "nvme": "mdi:memory",
    "ssd": "mdi:harddisk",
    "hdd": "mdi:harddisk-plus",
}

DATA_ASSET_ICON_BY_TYPE: Dict[str, str] = {
    "backup": "mdi:backup-restore",
    "database": "mdi:database",
    "media": "mdi:folder-music",
    "config": "mdi:file-cog-outline",
    "logs": "mdi:file-document-outline",
}

ALERT_ICON_BY_SEVERITY: Dict[str, str] = {
    "critical": "mdi:alert-octagon",
    "high": "mdi:alert",
    "warning": "mdi:alert-outline",
    "info": "mdi:information-outline",
}

CHANNEL_ICON_BY_TYPE: Dict[str, str] = {
    "telegram": "mdi:send",
    "email": "mdi:email-outline",
    "webhook": "mdi:webhook",
    "slack": "si:slack",
    "discord": "si:discord",
}

POWER_ICONS: Dict[str, str] = {
    "ups": "mdi:battery-charging-high",
    "pdu": "mdi:power-socket-eu",
    "utility-grid": "mdi:transmission-tower",
    "battery": "mdi:battery-high",
    "solar": "mdi:solar-power",
    "generator": "mdi:engine",
}

# Mermaid icon-node styling defaults
ICON_NODE_DEFAULTS: Dict[str, any] = {
    "form": "rounded",
    "pos": "b",
    "h": 46,
}

ICON_NODE_CIRCLE: Dict[str, any] = {
    "form": "circle",
    "pos": "b",
    "h": 42,
}
```

**File:** `v5/topology-tools/plugins/icons/icon_manager.py`

Port from `v4/topology-tools/scripts/generators/docs/icons/__init__.py`:

```python
"""Icon pack management and rendering.

Discovers @iconify-json packages, extracts SVG, generates data URIs.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from .mappings import (
    DEVICE_ICON_BY_TYPE,
    DEVICE_ICON_BY_CLASS,
    CLOUD_PROVIDER_ICON,
    ZONE_ICON_MAP,
    SERVICE_ICON_BY_TYPE,
)


class IconManager:
    """Manages icon packs and generates icon HTML/SVG."""

    DEFAULT_PACK_MAPPING = {
        "mdi": "mdi",
        "si": "simple-icons",
        "logos": "logos",
    }

    def __init__(
        self,
        search_roots: Optional[List[Path]] = None,
        pack_mapping: Optional[Dict[str, str]] = None,
    ):
        self.search_roots = search_roots or [Path.cwd()]
        self.pack_mapping = pack_mapping or self.DEFAULT_PACK_MAPPING
        self._pack_cache: Optional[Dict[str, Dict]] = None
        self._data_uri_cache: Dict[str, str] = {}

    def _discover_pack_dirs(self) -> List[Path]:
        """Find node_modules/@iconify-json directories."""
        dirs = []
        seen = set()
        for root in self.search_roots:
            for parent in [root, *root.parents]:
                candidate = parent / "node_modules" / "@iconify-json"
                key = str(candidate)
                if key not in seen:
                    seen.add(key)
                    dirs.append(candidate)
        return dirs

    def _load_packs(self) -> Dict[str, Dict]:
        """Load icon packs from local files."""
        if self._pack_cache is not None:
            return self._pack_cache

        packs = {}
        for base_dir in self._discover_pack_dirs():
            for prefix, package_dir in self.pack_mapping.items():
                if prefix in packs:
                    continue
                icon_file = base_dir / package_dir / "icons.json"
                if not icon_file.exists():
                    continue
                try:
                    data = json.loads(icon_file.read_text(encoding="utf-8"))
                    packs[prefix] = data
                except Exception:
                    continue

        self._pack_cache = packs
        return packs

    def get_loaded_packs(self) -> List[str]:
        """Return list of loaded pack prefixes."""
        return list(self._load_packs().keys())

    @staticmethod
    def extract_svg(pack: Dict, icon_name: str) -> str:
        """Extract SVG markup from icon pack."""
        icons = pack.get("icons", {})
        icon = icons.get(icon_name)
        if not isinstance(icon, dict):
            return ""
        body = icon.get("body")
        if not body:
            return ""
        width = icon.get("width", pack.get("width", 24))
        height = icon.get("height", pack.get("height", 24))
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{body}</svg>'

    def get_data_uri(self, icon_id: str) -> str:
        """Get base64 data URI for icon."""
        if icon_id in self._data_uri_cache:
            return self._data_uri_cache[icon_id]

        if ":" not in (icon_id or ""):
            return ""

        prefix, icon_name = icon_id.split(":", 1)
        packs = self._load_packs()
        pack = packs.get(prefix)
        if not pack:
            return ""

        svg = self.extract_svg(pack, icon_name)
        if not svg:
            return ""

        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data_uri = f"data:image/svg+xml;base64,{encoded}"
        self._data_uri_cache[icon_id] = data_uri
        return data_uri

    def icon_html(
        self, icon_id: str, height: int = 16, remote_fallback: bool = True
    ) -> str:
        """Generate HTML img tag for icon."""
        local_src = self.get_data_uri(icon_id)
        if local_src:
            return f"<img src='{local_src}' height='{height}'/>"
        if remote_fallback:
            safe = quote(icon_id or "mdi:help-circle-outline", safe="")
            return f"<img src='https://api.iconify.design/{safe}.svg' height='{height}'/>"
        return ""

    def icon_for_device(self, device: dict) -> str:
        """Get icon ID for device based on type/class/model."""
        device_type = (device.get("type") or "").lower()
        device_class = (device.get("class") or "").lower()
        device_model = (device.get("model") or "").lower()
        device_id = (device.get("instance_id") or device.get("id") or "").lower()

        # Cloud provider detection
        cloud = device.get("cloud") or {}
        provider = (cloud.get("provider") or "").lower()
        if device_type == "cloud-vm" and provider in CLOUD_PROVIDER_ICON:
            return CLOUD_PROVIDER_ICON[provider]

        # Vendor hints
        if "mikrotik" in device_id or "mikrotik" in device_model:
            return "si:mikrotik"
        if "proxmox" in device_model:
            return "si:proxmox"
        if "openwrt" in device_model or "gl-inet" in device_model:
            return "si:openwrt"

        # Type mapping
        if device_type in DEVICE_ICON_BY_TYPE:
            return DEVICE_ICON_BY_TYPE[device_type]

        # Class mapping
        if device_class in DEVICE_ICON_BY_CLASS:
            return DEVICE_ICON_BY_CLASS[device_class]

        return "mdi:devices"

    def icon_for_zone(self, zone_id: str) -> str:
        """Get icon ID for trust zone."""
        return ZONE_ICON_MAP.get(zone_id.lower(), "mdi:shield-outline")

    def icon_for_service(self, service: dict) -> str:
        """Get icon ID for service based on type."""
        service_type = (service.get("type") or "").lower()
        if service_type in SERVICE_ICON_BY_TYPE:
            return SERVICE_ICON_BY_TYPE[service_type]
        if service.get("vpn_type"):
            return "mdi:vpn"
        return "mdi:application-cog-outline"

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._pack_cache = None
        self._data_uri_cache.clear()
```

### 0.2 Template Partials

**File:** `v5/topology-tools/templates/docs/_partials/mermaid_header.j2`

```jinja2
{# Mermaid diagram header with icon mode hints #}
{% if use_mermaid_icons %}
> **Icon Mode**: {{ icon_mode }}
>
> {{ mermaid_icon_runtime_hint }}
{% endif %}
```

**File:** `v5/topology-tools/templates/docs/_partials/icon_node.j2`

```jinja2
{# Macro for generating Mermaid icon-node syntax #}
{% macro icon_node(node_id, icon_id, label, form="rounded", pos="b", h=46) %}
{% if use_mermaid_icons and mermaid_icon_nodes %}
{{ node_id }}@{ icon: "{{ icon_id }}", form: "{{ form }}", label: "{{ label }}", pos: "{{ pos }}", h: {{ h }} }
{% else %}
{{ node_id }}["{{ label }}"]
{% endif %}
{% endmacro %}
```

**File:** `v5/topology-tools/templates/docs/_partials/footer.j2`

```jinja2
---

*Generated by `base.generator.docs` from compiled topology model.*
```

### 0.3 Projection Module Package

**File:** `v5/topology-tools/plugins/generators/docs/__init__.py`

```python
"""Documentation-specific projection builders."""
from .network_projection import build_network_projection
from .physical_projection import build_physical_projection
from .security_projection import build_security_projection
from .storage_projection import build_storage_projection
from .operations_projection import build_operations_projection

__all__ = [
    "build_network_projection",
    "build_physical_projection",
    "build_security_projection",
    "build_storage_projection",
    "build_operations_projection",
]
```

---

## Phase A: Core Network Documentation

### A.1 Network Projection Module

**File:** `v5/topology-tools/plugins/generators/docs/network_projection.py`

```python
"""Network projection builder for documentation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from plugins.generators.projection_core import (
    ProjectionError,
    _instance_groups,
    _require_mapping,
    _sorted_rows,
)


@dataclass
class NetworkRow:
    """Network instance for documentation."""
    instance_id: str
    object_ref: str
    name: str
    cidr: str
    vlan_tag: Optional[int]
    trust_zone_ref: Optional[str]
    gateway: Optional[str]
    ip_allocations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AllocationRow:
    """IP allocation for documentation."""
    network_id: str
    ip: str
    device_ref: Optional[str]
    interface: Optional[str]
    description: Optional[str]


@dataclass
class BridgeRow:
    """Bridge definition for documentation."""
    id: str
    name: str
    vlan_aware: bool
    network_refs: List[str]


@dataclass
class NetworkProjection:
    """Network documentation projection."""
    networks: List[NetworkRow]
    allocations: List[AllocationRow]
    bridges: List[BridgeRow]
    counts: Dict[str, int]


def build_network_projection(compiled_json: Dict[str, Any]) -> NetworkProjection:
    """Build network diagram projection from compiled model.

    Extracts:
    - Networks from instances.network group
    - IP allocations from network instance data
    - Bridges from instances.bridges group (if present)

    Returns:
        NetworkProjection with sorted collections
    """
    groups = _instance_groups(compiled_json)

    # Extract networks
    networks: List[NetworkRow] = []
    allocations: List[AllocationRow] = []

    for row in groups.get("network", []):
        instance_id = row.get("instance_id", "")
        object_ref = row.get("object_ref", "")
        instance_data = row.get("instance_data", {}) or {}

        network = NetworkRow(
            instance_id=instance_id,
            object_ref=object_ref,
            name=instance_data.get("name", instance_id),
            cidr=instance_data.get("cidr", ""),
            vlan_tag=instance_data.get("vlan_tag"),
            trust_zone_ref=instance_data.get("trust_zone_ref"),
            gateway=instance_data.get("gateway"),
            ip_allocations=instance_data.get("ip_allocations", []),
        )
        networks.append(network)

        # Extract allocations
        for alloc in network.ip_allocations:
            allocations.append(AllocationRow(
                network_id=instance_id,
                ip=alloc.get("ip", ""),
                device_ref=alloc.get("device_ref"),
                interface=alloc.get("interface"),
                description=alloc.get("description"),
            ))

    # Extract bridges (if group exists)
    bridges: List[BridgeRow] = []
    for row in groups.get("bridges", []):
        instance_id = row.get("instance_id", "")
        instance_data = row.get("instance_data", {}) or {}
        bridges.append(BridgeRow(
            id=instance_id,
            name=instance_data.get("name", instance_id),
            vlan_aware=instance_data.get("vlan_aware", False),
            network_refs=instance_data.get("network_refs", []),
        ))

    # Sort deterministically
    networks_sorted = sorted(networks, key=lambda n: n.instance_id)
    allocations_sorted = sorted(allocations, key=lambda a: (a.network_id, a.ip))
    bridges_sorted = sorted(bridges, key=lambda b: b.id)

    return NetworkProjection(
        networks=networks_sorted,
        allocations=allocations_sorted,
        bridges=bridges_sorted,
        counts={
            "networks": len(networks_sorted),
            "allocations": len(allocations_sorted),
            "bridges": len(bridges_sorted),
        },
    )
```

### A.2 Network Diagram Template

**File:** `v5/topology-tools/templates/docs/network-diagram.md.j2`

Port from `v4/topology-tools/templates/docs/network-diagram.md.j2` with projection access:

```jinja2
# Network Topology

{% include '_partials/mermaid_header.j2' %}

```mermaid
flowchart TB
    subgraph Internet
        WAN[WAN]
    end

{% for network in projection.networks %}
    subgraph {{ network.instance_id | replace("-", "_") }}["{{ network.name }} ({{ network.cidr }})"]
{% for alloc in network.ip_allocations %}
        {{ alloc.device_ref | replace("-", "_") }}["{{ alloc.device_ref }}<br/>{{ alloc.ip }}"]
{% endfor %}
    end
{% endfor %}

{% for bridge in projection.bridges %}
{% for network_ref in bridge.network_refs %}
    {{ bridge.id | replace("-", "_") }} --- {{ network_ref | replace("-", "_") }}
{% endfor %}
{% endfor %}
```

## Network Summary

| Metric | Count |
|--------|-------|
| Networks | {{ projection.counts.networks }} |
| IP Allocations | {{ projection.counts.allocations }} |
| Bridges | {{ projection.counts.bridges }} |

{% include '_partials/footer.j2' %}
```

### A.3 IP Allocation Template

**File:** `v5/topology-tools/templates/docs/ip-allocation.md.j2`

```jinja2
# IP Allocation

{% include '_partials/mermaid_header.j2' %}

## Allocations by Network

{% for network in projection.networks %}
### {{ network.name }} ({{ network.cidr }})

| IP | Device | Interface | Description |
|----|--------|-----------|-------------|
{% for alloc in network.ip_allocations %}
| {{ alloc.ip }} | {{ alloc.device_ref or '-' }} | {{ alloc.interface or '-' }} | {{ alloc.description or '-' }} |
{% endfor %}

{% endfor %}

## Full Allocation Table

| Network | IP | Device | Interface | Description |
|---------|-----|--------|-----------|-------------|
{% for alloc in projection.allocations %}
| {{ alloc.network_id }} | {{ alloc.ip }} | {{ alloc.device_ref or '-' }} | {{ alloc.interface or '-' }} | {{ alloc.description or '-' }} |
{% endfor %}

{% include '_partials/footer.j2' %}
```

### A.4 Generator Integration

Update `v5/topology-tools/plugins/generators/docs_generator.py`:

```python
"""Generator plugin that emits docs artifacts from compiled model."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_docs_projection
from plugins.generators.docs.network_projection import build_network_projection
from plugins.icons import IconManager


class DocsGenerator(BaseGenerator):
    """Emit deterministic markdown docs from compiled model projection."""

    # Template sets configuration
    TEMPLATE_SETS: Dict[str, List[Tuple[str, str]]] = {
        "core": [
            ("docs/overview.md.j2", "overview.md"),
            ("docs/devices.md.j2", "devices.md"),
            ("docs/services.md.j2", "services.md"),
        ],
        "network": [
            ("docs/network-diagram.md.j2", "network-diagram.md"),
            ("docs/ip-allocation.md.j2", "ip-allocation.md"),
        ],
        # Additional sets added in later phases
    }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate docs artifacts.",
                    path="generator:docs",
                )
            )
            return self.make_result(diagnostics)

        # Get configuration
        config = ctx.config or {}
        template_sets = config.get("template_sets", ["all"])
        mermaid_icons = config.get("mermaid_icons", True)
        mermaid_icon_nodes = config.get("mermaid_icon_nodes", True)
        icon_packs = config.get("icon_packs", ["si", "mdi"])

        # Initialize icon manager
        icon_manager = IconManager(
            search_roots=[Path.cwd(), self.template_root(ctx)],
            pack_mapping={"si": "simple-icons", "mdi": "mdi"},
        )

        # Build projections
        try:
            docs_projection = build_docs_projection(payload)
            network_projection = build_network_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9701",
                    severity="error",
                    stage=stage,
                    message=f"failed to build docs projection: {exc}",
                    path="generator:docs",
                )
            )
            return self.make_result(diagnostics)

        # Determine active template sets
        if "all" in template_sets:
            active_sets = list(self.TEMPLATE_SETS.keys())
        else:
            active_sets = [s for s in template_sets if s in self.TEMPLATE_SETS]

        # Collect templates to render
        templates: List[Tuple[str, str]] = []
        for set_name in active_sets:
            templates.extend(self.TEMPLATE_SETS.get(set_name, []))

        # Build template context
        docs_root = self.resolve_output_path(ctx, "docs")
        generated_files: list[str] = []

        template_ctx = {
            "projection": docs_projection,
            "network_projection": network_projection,
            "counts": docs_projection.get("counts", {}),
            "devices": docs_projection.get("devices", []),
            "services": docs_projection.get("services", []),
            "groups": docs_projection.get("groups", {}),
            # Icon configuration
            "use_mermaid_icons": mermaid_icons,
            "mermaid_icon_nodes": mermaid_icon_nodes,
            "icon_mode": "icon-nodes" if mermaid_icon_nodes else ("compat" if mermaid_icons else "none"),
            "mermaid_icon_runtime_hint": self._icon_runtime_hint(icon_manager, mermaid_icons, mermaid_icon_nodes),
            "icon_manager": icon_manager,
        }

        # Render templates
        for template_name, output_name in templates:
            output_path = docs_root / output_name
            try:
                content = self.render_template(ctx, template_name, template_ctx)
                self.write_text_atomic(output_path, content)
                generated_files.append(str(output_path))
            except Exception as exc:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9702",
                        severity="error",
                        stage=stage,
                        message=f"failed to render template {template_name}: {exc}",
                        path=str(output_path),
                    )
                )

        # Write generated files manifest
        generated_files_path = docs_root / "_generated_files.txt"
        generated_files_payload = "\n".join(sorted(generated_files)) + "\n"
        self.write_text_atomic(generated_files_path, generated_files_payload)
        generated_files.append(str(generated_files_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9701",
                severity="info",
                stage=stage,
                message=(
                    f"generated docs artifacts: "
                    f"devices={docs_projection['counts']['devices']} "
                    f"services={docs_projection['counts']['services']} "
                    f"templates={len(templates)}"
                ),
                path=str(docs_root),
            )
        )

        self.publish_if_possible(ctx, "generated_dir", str(docs_root))
        self.publish_if_possible(ctx, "generated_files", generated_files)
        self.publish_if_possible(ctx, "docs_files", generated_files)
        self.publish_if_possible(ctx, "docs_projection", docs_projection)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "docs_dir": str(docs_root),
                "docs_files": generated_files,
            },
        )

    @staticmethod
    def _icon_runtime_hint(
        icon_manager: IconManager,
        mermaid_icons: bool,
        mermaid_icon_nodes: bool,
    ) -> str:
        """Generate Mermaid icon runtime hint text."""
        if not mermaid_icons:
            return "Icon mode disabled."
        if mermaid_icon_nodes:
            packs = icon_manager.get_loaded_packs()
            pack_hints = ", ".join(packs) if packs else "none loaded"
            return f"Icon-node mode enabled. Renderer must preload icon packs: {pack_hints}."
        return "Compatibility icon mode enabled. Icons are embedded inline."
```

### A.5 Tests

**File:** `v5/tests/plugin_integration/test_docs_network_projection.py`

```python
"""Tests for network projection builder."""
import pytest
from plugins.generators.docs.network_projection import (
    build_network_projection,
    NetworkProjection,
)
from plugins.generators.projection_core import ProjectionError


def test_build_network_projection_empty():
    """Empty compiled model returns empty projection."""
    result = build_network_projection({"instances": {}})
    assert isinstance(result, NetworkProjection)
    assert result.networks == []
    assert result.allocations == []
    assert result.counts["networks"] == 0


def test_build_network_projection_with_networks():
    """Networks are extracted and sorted."""
    compiled = {
        "instances": {
            "network": [
                {
                    "instance_id": "vlan-servers",
                    "object_ref": "obj.network.vlan",
                    "instance_data": {
                        "name": "Servers VLAN",
                        "cidr": "10.0.30.0/24",
                        "vlan_tag": 30,
                        "ip_allocations": [
                            {"ip": "10.0.30.5", "device_ref": "srv-opi5"},
                        ],
                    },
                },
                {
                    "instance_id": "vlan-mgmt",
                    "object_ref": "obj.network.vlan",
                    "instance_data": {
                        "name": "Management VLAN",
                        "cidr": "10.0.99.0/24",
                        "vlan_tag": 99,
                        "ip_allocations": [],
                    },
                },
            ]
        }
    }

    result = build_network_projection(compiled)

    assert len(result.networks) == 2
    assert result.networks[0].instance_id == "vlan-mgmt"  # Sorted
    assert result.networks[1].instance_id == "vlan-servers"
    assert len(result.allocations) == 1
    assert result.allocations[0].ip == "10.0.30.5"


def test_build_network_projection_allocations_sorted():
    """Allocations are sorted by network, then IP."""
    compiled = {
        "instances": {
            "network": [
                {
                    "instance_id": "net-b",
                    "object_ref": "obj.network.vlan",
                    "instance_data": {
                        "cidr": "10.0.2.0/24",
                        "ip_allocations": [
                            {"ip": "10.0.2.20"},
                            {"ip": "10.0.2.10"},
                        ],
                    },
                },
                {
                    "instance_id": "net-a",
                    "object_ref": "obj.network.vlan",
                    "instance_data": {
                        "cidr": "10.0.1.0/24",
                        "ip_allocations": [
                            {"ip": "10.0.1.5"},
                        ],
                    },
                },
            ]
        }
    }

    result = build_network_projection(compiled)

    # Sorted by network_id, then ip
    assert result.allocations[0].network_id == "net-a"
    assert result.allocations[0].ip == "10.0.1.5"
    assert result.allocations[1].network_id == "net-b"
    assert result.allocations[1].ip == "10.0.2.10"
    assert result.allocations[2].network_id == "net-b"
    assert result.allocations[2].ip == "10.0.2.20"
```

---

## Phase B: Physical Topology

### B.1 Physical Projection Module

**File:** `v5/topology-tools/plugins/generators/docs/physical_projection.py`

Extracts:
- Devices from `instances.devices`
- Data links from device instance `data_links`
- Power links from device instance `power_links`
- Storage slot views from device specs

### B.2 Templates

| Template | Port From | Key Changes |
|----------|-----------|-------------|
| physical-topology.md.j2 | v4 | Use `physical_projection.devices` |
| data-links-topology.md.j2 | v4 | Use `physical_projection.data_links` |
| power-links-topology.md.j2 | v4 | Use `physical_projection.power_links` |

---

## Phase C: Security Topology

### C.1 Security Projection Module

**File:** `v5/topology-tools/plugins/generators/docs/security_projection.py`

Extracts:
- Trust zones from `instances.trust_zones`
- VLANs from network instances with vlan_tag
- Firewall policies from `instances.firewall_policies`
- Zone-network bindings

### C.2 Templates

| Template | Port From | Key Changes |
|----------|-----------|-------------|
| vlan-topology.md.j2 | v4 | Use `security_projection.vlans` |
| trust-zones.md.j2 | v4 | Use `security_projection.trust_zones` |

---

## Phase D: Application Layer

### D.1 Storage Projection Module

**File:** `v5/topology-tools/plugins/generators/docs/storage_projection.py`

Extracts:
- Storage pools from `instances.storage_endpoints` or equivalent
- Data assets from `instances.data_assets`
- Mount chain resolution (device -> pool -> asset)

### D.2 Extended Service Projection

Update `build_docs_projection` to include service dependencies.

### D.3 Templates

| Template | Port From | Key Changes |
|----------|-----------|-------------|
| service-dependencies.md.j2 | v4 | Use extended docs_projection |
| storage-topology.md.j2 | v4 | Use storage_projection |

---

## Phase E: Operations Layer

### E.1 Operations Projection Module

**File:** `v5/topology-tools/plugins/generators/docs/operations_projection.py`

Extracts:
- Healthchecks from `instances.healthchecks`
- Alerts from `instances.alerts`
- Dashboards from `instances.dashboards`
- VPN tunnels from network instances
- Certificates from `instances.certificates`
- QoS policies from network instances
- UPS policies from `instances.ups_policies` or power_resilience

### E.2 Templates

| Template | Port From | Key Changes |
|----------|-----------|-------------|
| monitoring-topology.md.j2 | v4 | Use operations_projection |
| vpn-topology.md.j2 | v4 | Use operations_projection.vpn_tunnels |
| certificates-topology.md.j2 | v4 | Use operations_projection.certificates |
| qos-topology.md.j2 | v4 | Use operations_projection.qos_policies |
| ups-topology.md.j2 | v4 | Use operations_projection.ups_policies |

---

## Phase F: Meta and Tooling

### F.1 Icon Legend Template

**File:** `v5/topology-tools/templates/docs/icon-legend.md.j2`

Port from v4 with icon_manager access for dynamic legend generation.

### F.2 Diagrams Index Template

**File:** `v5/topology-tools/templates/docs/diagrams-index.md.j2`

Generate index from list of generated files.

### F.3 Mermaid Validator Plugin

**File:** `v5/topology-tools/plugins/validators/mermaid_validator.py`

```python
"""Mermaid render validation plugin."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import List

from kernel.plugin_base import (
    PluginContext,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorPlugin,
)


class MermaidValidator(ValidatorPlugin):
    """Validate Mermaid diagrams in generated docs."""

    MERMAID_BLOCK_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: List[PluginDiagnostic] = []
        config = ctx.config or {}
        fail_on_error = config.get("fail_on_error", True)

        # Get docs files from subscribed generator
        docs_files = ctx.subscribe("base.generator.docs", "docs_files")
        if not docs_files:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9801",
                    severity="warning",
                    stage=stage,
                    message="No docs files to validate",
                    path="validator:mermaid",
                )
            )
            return self.make_result(diagnostics)

        # Extract and validate Mermaid blocks
        errors = 0
        validated = 0
        for file_path in docs_files:
            path = Path(file_path)
            if not path.suffix == ".md":
                continue
            content = path.read_text(encoding="utf-8")
            for match in self.MERMAID_BLOCK_RE.finditer(content):
                mermaid_code = match.group(1)
                is_valid, error = self._validate_mermaid(mermaid_code)
                validated += 1
                if not is_valid:
                    errors += 1
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E9802" if fail_on_error else "W9802",
                            severity="error" if fail_on_error else "warning",
                            stage=stage,
                            message=f"Mermaid validation failed: {error}",
                            path=file_path,
                        )
                    )

        diagnostics.append(
            self.emit_diagnostic(
                code="I9801",
                severity="info",
                stage=stage,
                message=f"Validated {validated} Mermaid blocks, {errors} errors",
                path="validator:mermaid",
            )
        )

        return self.make_result(diagnostics)

    @staticmethod
    def _validate_mermaid(code: str) -> tuple[bool, str]:
        """Validate Mermaid code using mmdc CLI."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".mmd", delete=False
            ) as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    ["npx", "mmdc", "-i", f.name, "-o", "/dev/null"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    return False, result.stderr[:200]
                return True, ""
        except FileNotFoundError:
            return True, ""  # mmdc not available, skip validation
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)[:200]
```

---

## Testing Strategy

### Testing Principles

1. **Projection-first testing**: Test projections independently before templates
2. **Snapshot stability**: Golden tests for projection outputs
3. **Determinism verification**: Same input always produces same output
4. **V4 semantic parity**: V5 output semantically equivalent to v4

### Unit Tests

| Test File | Scope | Key Cases |
|-----------|-------|-----------|
| test_network_projection.py | Network projection logic | Empty model, networks with allocations, bridge mapping |
| test_physical_projection.py | Physical topology projection | Devices, data_links, power_links, external refs |
| test_security_projection.py | Security projection | Trust zones, VLANs, firewall policies |
| test_storage_projection.py | Storage projection | Pools, assets, mount chain resolution |
| test_operations_projection.py | Operations projection | Healthchecks, alerts, VPN, certs, QoS, UPS |
| test_icon_manager.py | Icon mapping and rendering | Local pack, remote fallback, cache |

### Integration Tests

| Test File | Scope | Key Cases |
|-----------|-------|-----------|
| test_docs_generator_full.py | Full docs generation | All template sets, selective sets |
| test_mermaid_validator.py | Mermaid validation | Valid diagrams, syntax errors |
| test_docs_generator_template_contract.py | Generator ADR 0074 compliance | Templates external, StrictUndefined |
| test_docs_generator_publish_contract.py | Generator publish contract | docs_files, docs_projection |

### Golden/Snapshot Tests

Projection snapshot tests in `v5/tests/plugin_integration/snapshots/docs/`:

```
snapshots/docs/
├── network_projection_snapshot.json
├── physical_projection_snapshot.json
├── security_projection_snapshot.json
├── storage_projection_snapshot.json
├── operations_projection_snapshot.json
└── full_docs_projection_snapshot.json
```

### Determinism Tests

```python
# test_docs_projection_determinism.py
def test_network_projection_determinism():
    """Verify projection is deterministic across multiple runs."""
    compiled = load_test_compiled_model()
    results = [build_network_projection(compiled) for _ in range(5)]
    # All results must be identical (not just equivalent)
    for r in results[1:]:
        assert r == results[0]
```

### V4 Parity Tests

```python
# test_docs_v4_parity.py
def test_network_diagram_semantic_parity():
    """Verify v5 network diagram semantically matches v4."""
    v4_output = load_v4_generated_doc("network-diagram.md")
    v5_output = generate_v5_doc("network-diagram.md")

    # Extract Mermaid blocks
    v4_mermaid = extract_mermaid_blocks(v4_output)
    v5_mermaid = extract_mermaid_blocks(v5_output)

    # Parse and compare graphs (node/edge equivalence, not string match)
    v4_graph = parse_mermaid_graph(v4_mermaid)
    v5_graph = parse_mermaid_graph(v5_mermaid)

    assert v4_graph.nodes == v5_graph.nodes
    assert v4_graph.edges == v5_graph.edges
```

### CI Gate Integration

```yaml
# .github/workflows/plugin-validation.yml (additions)
jobs:
  docs-validation:
    steps:
      - name: Run docs projection tests
        run: pytest v5/tests/plugin_integration/test_*_projection.py -v

      - name: Run docs generator integration tests
        run: pytest v5/tests/plugin_integration/test_docs_generator*.py -v

      - name: Verify projection snapshots
        run: pytest v5/tests/plugin_integration/test_projection_snapshots.py -v --snapshot-update

      - name: Run Mermaid validation (if mmdc available)
        run: |
          if command -v npx &> /dev/null; then
            python v5/topology-tools/validate-mermaid-render.py v5-generated/home-lab/docs/
          else
            echo "Skipping Mermaid validation (mmdc not available)"
          fi
```

---

## Migration Checklist

### Phase 0
- [ ] Create icons module package
- [ ] Port icon mappings from v4
- [ ] Port IconManager class
- [ ] Create template partials
- [ ] Create projection module package

### Phase A
- [ ] Create network_projection.py
- [ ] Port network-diagram.md.j2
- [ ] Port ip-allocation.md.j2
- [ ] Update docs_generator.py
- [ ] Add tests
- [ ] Validate output matches v4 semantically

### Phase B
- [ ] Create physical_projection.py
- [ ] Port physical-topology.md.j2
- [ ] Port data-links-topology.md.j2
- [ ] Port power-links-topology.md.j2
- [ ] Add tests

### Phase C
- [ ] Create security_projection.py
- [ ] Port vlan-topology.md.j2
- [ ] Port trust-zones.md.j2
- [ ] Add tests

### Phase D
- [ ] Extend docs_projection.py for dependencies
- [ ] Create storage_projection.py
- [ ] Port service-dependencies.md.j2
- [ ] Port storage-topology.md.j2
- [ ] Add tests

### Phase E
- [ ] Create operations_projection.py
- [ ] Port monitoring-topology.md.j2
- [ ] Port vpn-topology.md.j2
- [ ] Port certificates-topology.md.j2
- [ ] Port qos-topology.md.j2
- [ ] Port ups-topology.md.j2
- [ ] Add tests

### Phase F
- [ ] Port icon-legend.md.j2
- [ ] Port diagrams-index.md.j2
- [ ] Create mermaid_validator.py
- [ ] Add mermaid validation to plugins.yaml
- [ ] Add tests
- [ ] Update TEMPLATE-INVENTORY.md

---

## Effort Estimates

| Phase | Templates | Projections | Effort |
|-------|-----------|-------------|--------|
| 0 | 0 | 0 | 1-2 days |
| A | 2 | 1 | 2-3 days |
| B | 3 | 1 | 2-3 days |
| C | 2 | 1 | 2 days |
| D | 2 | 1 | 2 days |
| E | 5 | 1 | 3-4 days |
| F | 2 + tooling | 0 | 2-3 days |
| **Total** | **16** | **5** | **14-20 days** |

---

## Dependencies

### External
- Mermaid CLI (`@mermaid-js/mermaid-cli`) for validation
- Node.js for Mermaid CLI
- `@iconify-json/*` packages for icon packs

### Internal
- ADR 0074 generator plugin interface
- Compiled model with instance groups populated
- Instance refs resolution in projections

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Model mapping complexity | Projection snapshot tests, incremental migration |
| Icon pack availability | Remote fallback, graceful degradation |
| Template drift during migration | Semantic comparison tests, not byte-exact |
| Mermaid CLI dependency | Make validation optional, skip in constrained environments |

---

## Template Migration Path

### V4-to-V5 Template Transformation Rules

When porting templates from v4, apply these transformations:

| V4 Pattern | V5 Pattern |
|------------|------------|
| `{% for device in devices %}` | `{% for device in projection.devices %}` |
| `{{ device.id }}` | `{{ device.instance_id }}` |
| `{{ device.name }}` | `{{ device.name or device.instance_id }}` |
| `{{ network.trust_zone_ref }}` | `{{ network.trust_zone_ref or '' }}` |
| `topology_version` | Available via `projection.metadata.version` |
| `use_mermaid_icons` | Available via `icon_config.enabled` |
| `mermaid_icon_runtime_hint` | Available via `icon_config.runtime_hint` |

### Template Context Structure

All templates receive a standard context:

```python
template_ctx = {
    # Domain projection (varies by template set)
    "projection": NetworkProjection | PhysicalProjection | ...,

    # Icon configuration
    "icon_config": {
        "enabled": True,
        "icon_nodes": True,
        "mode": "icon-nodes",  # icon-nodes | compat | none
        "runtime_hint": "...",
        "packs": ["si", "mdi"],
    },

    # Icon manager for dynamic lookups
    "icon_manager": IconManager,

    # Metadata
    "metadata": {
        "version": "5.0.0",
        "generated_at": "2026-03-24T10:00:00Z",
    },

    # Counts (shortcut)
    "counts": projection.counts,
}
```

### Template File Layout

Templates may remain flat (as currently in v4) or be organized into subdirectories:

**Option A: Flat (simpler)**
```
templates/docs/
├── _partials/
├── overview.md.j2
├── network-diagram.md.j2
├── ...
```

**Option B: Categorized (matches template_sets)**
```
templates/docs/
├── _partials/
├── core/
├── network/
├── physical/
├── security/
├── application/
├── operations/
└── navigation/
```

**Recommendation**: Use Option A (flat) initially, reorganize to Option B only if template management becomes unwieldy.

---

## Success Criteria

### Phase Completion Criteria

| Phase | Criteria |
|-------|----------|
| 0 | IconManager loads packs, mappings compile, partials render |
| A | Network diagram + IP allocation render with correct data |
| B | Physical, data-links, power-links diagrams render correctly |
| C | VLAN and trust-zones diagrams render correctly |
| D | Service-deps and storage diagrams render correctly |
| E | All 5 operations diagrams render correctly |
| F | Icon legend accurate, index complete, Mermaid validation passes |

### Overall Success Criteria

1. **Template parity**: All 19 templates render without errors
2. **Projection stability**: All projection tests pass with golden snapshots
3. **Mermaid quality**: Mermaid validation passes for all diagrams (when mmdc available)
4. **Icon accuracy**: Icon legend documents all used icons correctly
5. **Determinism**: Identical input always produces identical output
6. **ADR 0074 compliance**: Generator passes template/publish contract tests
7. **V4 deprecation**: V4 docs generator marked deprecated in CLAUDE.md

### Acceptance Test

```bash
# Full acceptance test sequence
cd v5/topology-tools

# 1. Run projection unit tests
pytest tests/plugin_integration/test_*_projection.py -v

# 2. Run generator integration tests
pytest tests/plugin_integration/test_docs_generator*.py -v

# 3. Generate docs for test topology
python -m kernel.cli generate --project home-lab

# 4. Verify output files exist
ls -la ../v5-generated/home-lab/docs/

# 5. Run Mermaid validation (optional)
python validate-mermaid-render.py ../v5-generated/home-lab/docs/

# 6. Compare with v4 output (semantic parity)
pytest tests/plugin_regression/test_docs_v4_parity.py -v
```
