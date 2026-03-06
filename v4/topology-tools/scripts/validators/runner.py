"""Runner for topology validation checks.

This module centralizes invocation of domain-specific validation functions
from scripts.validators.checks.* and provides a single entrypoint for the
validation pipeline. The implementation preserves the existing ordering used
by `validate-topology.py`.
"""
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from .checks import foundation, governance, network, references, storage
from .ids import collect_ids


def run_all(
    topology: Dict[str, Any],
    topology_path: Optional[Union[Path, str]],
    validator_policy: Dict[str, Any],
    policy_get: Callable[[List[str], Any], Any],
    emit_by_severity: Callable[[str, str], None],
    errors: List[str],
    warnings: List[str],
    strict_mode: bool = True,
) -> None:
    """Run the full ordered set of reference checks.

    Parameters mirror the older SchemaValidator usage. This function is
    intentionally imperative: it builds ids/storage_ctx once and then calls
    check functions in the original order.
    """

    # Normalize topology_path to Path object
    if topology_path is not None and not isinstance(topology_path, Path):
        topology_path = Path(topology_path)

    # Collect cross-reference ids once
    ids: Dict[str, Set[str]] = collect_ids(topology or {})

    # File placement check requires policy_get and emit_by_severity semantics
    foundation.check_file_placement(
        topology_path=topology_path,
        policy_get=policy_get,
        emit_by_severity=emit_by_severity,
        warnings=warnings,
    )

    # Modular include contract
    foundation.check_modular_include_contract(topology_path=topology_path, errors=errors)

    # Device taxonomy
    foundation.check_device_taxonomy(topology or {}, ids, errors=errors, warnings=warnings)

    # L0 governance checks
    governance.check_l0_contracts(topology or {}, ids, errors=errors, warnings=warnings)

    # Network domain checks
    network.check_network_refs(topology or {}, ids, errors=errors, warnings=warnings)
    network.check_firewall_policy_addressability(topology or {}, errors=errors, warnings=warnings)
    network.check_bridge_refs(topology or {}, ids, errors=errors, warnings=warnings)
    network.check_data_links(topology or {}, ids, errors=errors, warnings=warnings)
    network.check_power_links(topology or {}, ids, errors=errors, warnings=warnings)

    # Storage checks: prefer class-based implementation if available
    try:
        from .checks.storage_checks import StorageChecks

        storage_checks = StorageChecks()
        storage_checks.execute(topology or {}, errors=errors, warnings=warnings)
    except Exception:
        # Fallback to legacy function-style checks
        storage_ctx = storage.build_l1_storage_context(topology or {})
        storage.check_l3_storage_refs(
            topology or {}, ids, topology_path=topology_path, storage_ctx=storage_ctx, errors=errors, warnings=warnings
        )

    # References across L4-L7: prefer class-based implementation if available
    try:
        from .checks.references_checks import ReferencesChecks

        references_checks = ReferencesChecks()
        references_checks.execute(topology or {}, errors=errors, warnings=warnings)
    except Exception:
        # Fallback to legacy function-style checks
        references.check_host_os_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_vm_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_lxc_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_service_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_dns_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_certificate_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_backup_refs(topology or {}, ids, errors=errors, warnings=warnings)
        references.check_security_policy_refs(topology or {}, ids, errors=errors, warnings=warnings)

    # Additional network checks / misc
    network.check_vlan_tags(topology or {}, errors=errors, warnings=warnings)
    network.check_mtu_consistency(topology or {}, errors=errors, warnings=warnings)
    network.check_vlan_zone_consistency(topology or {}, errors=errors, warnings=warnings)
    network.check_reserved_ranges(topology or {}, errors=errors, warnings=warnings)
    network.check_trust_zone_firewall_refs(topology or {}, ids, errors=errors, warnings=warnings)
    network.check_ip_allocation_host_os_refs(topology or {}, ids, errors=errors, warnings=warnings)
    network.check_runtime_network_reachability(topology or {}, ids, errors=errors, warnings=warnings)
    network.check_single_active_os_per_device(topology or {}, errors=errors, warnings=warnings)

    # Governance checks that are typically run elsewhere can be invoked by caller
    # (e.g. check_version, check_ip_overlaps). This runner focuses on reference checks.
