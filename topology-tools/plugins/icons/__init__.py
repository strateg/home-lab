"""Icon mapping helpers for docs/diagram generators."""

from .icon_manager import IconManager
from .mappings import CLASS_ICON_BY_PREFIX, SERVICE_ICON_BY_PREFIX, ZONE_ICON_BY_NAME

__all__ = [
    "CLASS_ICON_BY_PREFIX",
    "SERVICE_ICON_BY_PREFIX",
    "ZONE_ICON_BY_NAME",
    "IconManager",
]
