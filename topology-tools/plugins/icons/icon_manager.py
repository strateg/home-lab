"""Stateless icon resolver for docs/diagram generation."""

from __future__ import annotations

from plugins.icons.mappings import CLASS_ICON_BY_PREFIX, SERVICE_ICON_BY_PREFIX, ZONE_ICON_BY_NAME


class IconManager:
    """Resolve icon IDs by class/service/zone naming conventions."""

    def icon_for_class(self, class_ref: str, *, fallback: str = "mdi:devices") -> str:
        for prefix, icon in CLASS_ICON_BY_PREFIX:
            if class_ref.startswith(prefix):
                return icon
        return fallback

    def icon_for_service(self, class_ref: str, *, fallback: str = "mdi:cog") -> str:
        for prefix, icon in SERVICE_ICON_BY_PREFIX:
            if class_ref.startswith(prefix):
                return icon
        return self.icon_for_class(class_ref, fallback=fallback)

    def icon_for_zone(self, zone_id: str, *, fallback: str = "mdi:shield-half-full") -> str:
        key = zone_id.strip().lower()
        if key.startswith("inst.trust_zone."):
            key = key.rsplit(".", 1)[-1]
        return ZONE_ICON_BY_NAME.get(key, fallback)
