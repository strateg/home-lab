"""Validation domain package for topology-tools.

This package provides validation functionality for topology files:

- checks: Domain-specific validation checks (storage, network, references, etc.)
- ids: ID collection helpers for cross-reference validation

Usage:
    from scripts.validators import collect_ids
    from scripts.validators.checks import check_vlan_tags, check_bridge_refs
"""

from .ids import collect_ids

__all__ = [
    "collect_ids",
]
