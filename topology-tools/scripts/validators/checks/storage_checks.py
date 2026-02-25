"""Class-based storage validation checks (incremental migration).

This module provides a `StorageChecks` class that centralizes storage-related
validation behavior while delegating most logic to the legacy function-style
implementations in `storage.py`. The goal is to enable incremental migration
to class-based checks without duplicating large bodies of logic.
"""
from typing import Any, Dict, List, Optional, Set

from ..ids import collect_ids
from . import storage as storage_mod


class StorageChecks:
    """Encapsulate storage checks as a ValidationCheck-like object.

    Public method:
        execute(topology, *, errors, warnings)
    """

    def execute(self, topology: Dict[str, Any], *, errors: List[str], warnings: List[str]) -> None:
        """Run storage checks using existing storage.* functions.

        This method preserves the previous validation semantics; it builds a
        storage context once and reuses it for per-device and global checks.
        """
        topology = topology or {}

        # Collect ids for reference validation
        ids: Dict[str, Set[str]] = collect_ids(topology or {})

        # Build L1 storage context once
        storage_ctx: Dict[str, Any] = storage_mod.build_l1_storage_context(topology or {})

        # Global L1 checks (media registry / attachments)
        try:
            storage_mod.check_l1_media_inventory(
                topology or {}, ids, storage_ctx=storage_ctx, errors=errors, warnings=warnings
            )
        except TypeError:
            # Backwards compatibility if signature differs
            storage_mod.check_l1_media_inventory(topology or {}, ids, errors=errors, warnings=warnings)

        # Per-device storage checks
        l1 = topology.get("L1_foundation", {}) or {}
        for device in l1.get("devices", []) or []:
            if not isinstance(device, dict):
                continue
            try:
                storage_mod.check_device_storage_taxonomy(
                    device, storage_ctx=storage_ctx, errors=errors, warnings=warnings
                )
            except TypeError:
                # Some legacy forms expect different param order
                storage_mod.check_device_storage_taxonomy(device, errors=errors, warnings=warnings)

        # L3 storage references
        try:
            storage_mod.check_l3_storage_refs(
                topology or {}, ids, topology_path=None, storage_ctx=storage_ctx, errors=errors, warnings=warnings
            )
        except TypeError:
            storage_mod.check_l3_storage_refs(topology or {}, ids, errors=errors, warnings=warnings)

    return storage_ctx
