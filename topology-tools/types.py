"""Type definitions for topology model (v4.0)."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set

# ============================================================================
# L0 - Meta
# ============================================================================


class SeverityLevel(str, Enum):
    """Severity levels for validation issues."""

    WARNING = "warning"
    ERROR = "error"


@dataclass
class Metadata:
    """L0 metadata layer."""

    version: str
    last_updated: str
    contract: str


# ============================================================================
# L1 - Foundation
# ============================================================================


@dataclass
class StorageSlot:
    """Storage slot definition."""

    id: str
    port_type: str
    form_factor: str
    capacity_gb: Optional[int] = None
    mount_type: Optional[str] = None


@dataclass
class DeviceSpecs:
    """Device specifications."""

    storage_slots: List[StorageSlot]
    network_interfaces: Optional[List[Dict[str, Any]]] = None


@dataclass
class Device:
    """L1 device definition."""

    id: str
    name: str
    role: Literal["router", "compute", "storage", "sensor"]
    substrate: Literal["provider-instance", "baremetal-owned", "baremetal-colo"]
    specs: DeviceSpecs


# ============================================================================
# L2 - Network
# ============================================================================


@dataclass
class IPAllocation:
    """IP allocation in network."""

    ip: str
    network_ref: str
    host_os_ref: Optional[str] = None
    device_ref: Optional[str] = None


@dataclass
class Network:
    """L2 network definition."""

    id: str
    name: str
    cidr: str
    gateway: str
    ip_allocations: List[IPAllocation]


# ============================================================================
# L3 - Data
# ============================================================================


class DataAssetCategory(str, Enum):
    """Data asset categories."""

    DATABASE = "database"
    CACHE = "cache"
    TIMESERIES = "timeseries"
    SEARCH_INDEX = "search-index"
    OBJECT_STORAGE = "object-storage"
    FILE_SHARE = "file-share"
    MEDIA_LIBRARY = "media-library"
    CONFIGURATION = "configuration"
    SECRETS = "secrets"  # pragma: allowlist secret
    LOGS = "logs"


class CriticalityLevel(str, Enum):
    """Data criticality levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DataAsset:
    """L3 data asset definition."""

    id: str
    name: str
    category: DataAssetCategory
    criticality: CriticalityLevel
    engine: Optional[str] = None
    engine_version: Optional[str] = None
    backup_policy_refs: Optional[List[str]] = None
    retention_days: Optional[int] = None
    encryption_at_rest: Optional[bool] = False


# ============================================================================
# L4 - Platform
# ============================================================================


@dataclass
class LxcNetwork:
    """LXC container network configuration."""

    network_ref: str
    ip: str
    bridge_ref: Optional[str] = None
    vlan_tag: Optional[int] = None


@dataclass
class Lxc:
    """L4 LXC container definition."""

    id: str
    name: str
    networks: List[LxcNetwork]


# ============================================================================
# L5 - Application
# ============================================================================


@dataclass
class IpRef:
    """IP reference for service (ADR-0044)."""

    lxc_ref: Optional[str] = None
    vm_ref: Optional[str] = None
    host_os_ref: Optional[str] = None
    service_ref: Optional[str] = None
    network_ref: Optional[str] = None


@dataclass
class Service:
    """L5 service definition."""

    id: str
    name: str
    config: Optional[Dict[str, Any]] = None
    ip_refs: Optional[Dict[str, IpRef]] = None
    runtime: Optional[Dict[str, Any]] = None


# ============================================================================
# Validation Results
# ============================================================================


@dataclass
class ValidationIssue:
    """Single validation issue."""

    severity: SeverityLevel
    code: str
    message: str
    layer: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of validation check."""

    passed: bool
    issues: List[ValidationIssue]

    def has_errors(self) -> bool:
        """Check if result contains errors."""
        return any(issue.severity == SeverityLevel.ERROR for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if result contains warnings."""
        return any(issue.severity == SeverityLevel.WARNING for issue in self.issues)


# ============================================================================
# Type Aliases
# ============================================================================

TopologyDict = Dict[str, Any]
"""Full topology dictionary (L0-L7)."""

GeneratedConfig = Dict[str, str]
"""Generated configuration: key=filename, value=content."""

DeviceRef = str
"""Reference to a device by ID."""

NetworkRef = str
"""Reference to a network by ID."""

ServiceRef = str
"""Reference to a service by ID."""
