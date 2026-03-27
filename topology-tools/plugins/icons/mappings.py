"""Central icon mapping registry for ADR0079 migration."""

from __future__ import annotations

CLASS_ICON_BY_PREFIX: list[tuple[str, str]] = [
    ("class.network.router", "mdi:router-network"),
    ("class.network.trust_zone", "mdi:shield-half-full"),
    ("class.network.vlan", "mdi:lan"),
    ("class.network.bridge", "mdi:bridge"),
    ("class.network.physical_link", "mdi:ethernet-cable"),
    ("class.network.data_link", "mdi:ethernet"),
    ("class.network.qos", "mdi:speedometer"),
    ("class.compute.hypervisor", "si:proxmox"),
    ("class.compute.edge_node", "mdi:chip"),
    ("class.compute.cloud_vm", "mdi:cloud-outline"),
    ("class.compute.workload.container", "mdi:cube-outline"),
    ("class.compute.workload", "mdi:application"),
    ("class.storage.pool", "mdi:database"),
    ("class.storage.data_asset", "mdi:database-outline"),
    ("class.storage", "mdi:harddisk"),
    ("class.observability.alert", "mdi:alert"),
    ("class.observability.healthcheck", "mdi:heart-pulse"),
    ("class.operations.backup", "mdi:backup-restore"),
    ("class.power.ups", "mdi:battery-charging-high"),
    ("class.power.pdu", "mdi:power-socket-eu"),
    ("class.service", "mdi:cog"),
]

SERVICE_ICON_BY_PREFIX: list[tuple[str, str]] = [
    ("class.service.monitoring", "mdi:chart-line"),
    ("class.service.alerting", "mdi:bell-alert"),
    ("class.service.logging", "mdi:file-document-outline"),
    ("class.service.visualization", "mdi:chart-areaspline"),
    ("class.service.database", "mdi:database"),
    ("class.service.cache", "mdi:database-clock"),
    ("class.service.vpn", "mdi:vpn"),
    ("class.service.web_ui", "mdi:view-dashboard"),
    ("class.service.web_application", "mdi:web"),
    ("class.service.media_server", "mdi:multimedia"),
    ("class.service.home_automation", "mdi:home-automation"),
    ("class.service.dns", "mdi:dns"),
]

ZONE_ICON_BY_NAME: dict[str, str] = {
    "untrusted": "mdi:earth",
    "guest": "mdi:account-question",
    "user": "mdi:account-group",
    "iot": "mdi:home-automation",
    "servers": "mdi:server",
    "management": "mdi:shield-crown",
}
