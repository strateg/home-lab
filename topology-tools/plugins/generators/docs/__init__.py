"""Domain-specific projections for ADR0079 docs/diagram migration."""

from .network_projection import build_network_projection
from .operations_projection import build_operations_projection
from .physical_projection import build_physical_projection
from .security_projection import build_security_projection
from .storage_projection import build_storage_projection

__all__ = [
    "build_network_projection",
    "build_operations_projection",
    "build_physical_projection",
    "build_security_projection",
    "build_storage_projection",
]
