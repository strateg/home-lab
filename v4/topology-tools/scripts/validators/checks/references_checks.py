"""Class-based references validation checks (incremental migration).

This wraps the existing function-style checks in `references.py` into a
single class with an `execute` entrypoint, enabling cleaner registration
and future discovery-based invocation.
"""
from typing import Any, Dict, List, Set

from ..ids import collect_ids
from . import references as references_mod


class ReferencesChecks:
    """Encapsulate cross-layer reference validation checks.

    The execute method calls the existing reference check functions in the
    same order as the legacy runner to preserve behavior.
    """

    def execute(self, topology: Dict[str, Any], *, errors: List[str], warnings: List[str]) -> None:
        topology = topology or {}

        ids: Dict[str, Set[str]] = collect_ids(topology or {})

        # Host OS references
        try:
            references_mod.check_host_os_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_host_os_refs(topology or {}, errors=errors, warnings=warnings)

        # VM references
        try:
            references_mod.check_vm_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_vm_refs(topology or {}, errors=errors, warnings=warnings)

        # LXC references
        try:
            references_mod.check_lxc_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_lxc_refs(topology or {}, errors=errors, warnings=warnings)

        # Service / application references
        try:
            references_mod.check_service_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_service_refs(topology or {}, errors=errors, warnings=warnings)

        # DNS, certificates, backups, security policy refs
        try:
            references_mod.check_dns_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_dns_refs(topology or {}, errors=errors, warnings=warnings)

        try:
            references_mod.check_certificate_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_certificate_refs(topology or {}, errors=errors, warnings=warnings)

        try:
            references_mod.check_backup_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_backup_refs(topology or {}, errors=errors, warnings=warnings)

        try:
            references_mod.check_security_policy_refs(topology or {}, ids, errors=errors, warnings=warnings)
        except TypeError:
            references_mod.check_security_policy_refs(topology or {}, errors=errors, warnings=warnings)
