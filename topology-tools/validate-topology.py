#!/usr/bin/env python3
"""
Validate topology.yaml against JSON Schema v7 (v4 layered topology)
Provides detailed error messages and validation reports

Usage:
    python3 topology-tools/validate-topology.py [--topology topology.yaml] [--schema topology-tools/schemas/topology-v4-schema.json] [--validator-policy topology-tools/schemas/validator-policy.yaml] [--no-topology-cache] [--strict|--compat] [--migration-report]

Requirements:
    pip install jsonschema pyyaml
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Import topology loader with !include support
from topology_loader import load_topology
from scripts.generators.common import load_topology_cached
from scripts.validators.checks.storage import (
    build_l1_storage_context,
    check_l3_storage_refs,
)
from scripts.validators.checks.network import (
    check_bridge_refs,
    check_data_links,
    check_mtu_consistency,
    check_network_refs,
    check_power_links,
    check_reserved_ranges,
    check_trust_zone_firewall_refs,
    check_vlan_tags,
    check_vlan_zone_consistency,
)
from scripts.validators.checks.references import (
    check_backup_refs,
    check_certificate_refs,
    check_dns_refs,
    check_lxc_refs,
    check_security_policy_refs,
    check_service_refs,
    check_vm_refs,
)
from scripts.validators.checks.foundation import (
    check_device_taxonomy,
    check_file_placement,
)
from scripts.validators.checks.governance import (
    check_ip_overlaps,
    check_l0_contracts,
    check_version,
)
from scripts.validators.ids import collect_ids

try:
    from jsonschema import Draft7Validator, ValidationError
except ImportError:
    print("ERROR Error: jsonschema library not installed")
    print("   Install with: pip install jsonschema")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = SCRIPT_DIR / "schemas" / "topology-v4-schema.json"
DEFAULT_VALIDATOR_POLICY_PATH = SCRIPT_DIR / "schemas" / "validator-policy.yaml"


class SchemaValidator:
    """Validate topology YAML against JSON Schema"""

    def __init__(
        self,
        topology_path: str,
        schema_path: str,
        validator_policy_path: Optional[str] = None,
        use_topology_cache: bool = True,
        strict_mode: bool = True,
        show_migration_report: bool = False,
    ):
        self.topology_path = Path(topology_path)
        self.schema_path = Path(schema_path)
        self.validator_policy_path = Path(validator_policy_path) if validator_policy_path else DEFAULT_VALIDATOR_POLICY_PATH
        self.use_topology_cache = use_topology_cache
        self.strict_mode = strict_mode
        self.show_migration_report = show_migration_report
        self.topology: Optional[Dict] = None
        self.schema: Optional[Dict] = None
        self.validator_policy: Dict[str, Any] = self._default_validator_policy()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @staticmethod
    def _default_validator_policy() -> Dict[str, Any]:
        """Built-in validator policy defaults (used if policy file is absent)."""
        return {
            'checks': {
                'file_placement': {
                    'enabled': True,
                    'severity': 'warning',
                    'filename_id_mismatch_severity': 'warning',
                }
            },
            'paths': {
                'l1_devices_root': 'topology/L1-foundation/devices/',
                'l1_data_links_root': 'topology/L1-foundation/data-links/',
                'l1_media_root': 'topology/L1-foundation/media/',
                'l1_media_attachments_root': 'topology/L1-foundation/media-attachments/',
                'l2_networks_root': 'topology/L2-network/networks/',
                'l2_bridges_root': 'topology/L2-network/bridges/',
                'l2_firewall_policies_root': 'topology/L2-network/firewall/policies/',
            },
            'l1_device_group_by_substrate': {
                'provider-instance': 'provider',
                'baremetal-owned': 'owned',
                'baremetal-colo': 'owned',
            },
        }

    def _policy_get(self, keys: List[str], default: Any = None) -> Any:
        """Safely read nested keys from validator policy."""
        current: Any = self.validator_policy
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def _emit_by_severity(self, severity: str, message: str) -> None:
        """Route validator message by severity."""
        if severity == 'error':
            self.errors.append(message)
        else:
            self.warnings.append(message)

    def load_files(self) -> bool:
        """Load topology YAML and schema JSON"""
        try:
            if self.use_topology_cache:
                self.topology = load_topology_cached(self.topology_path)
            else:
                self.topology = load_topology(str(self.topology_path))
            print(f"OK Loaded topology: {self.topology_path}")
        except FileNotFoundError:
            self.errors.append(f"Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error: {e}")
            return False

        try:
            with open(self.schema_path) as f:
                self.schema = json.load(f)
            print(f"OK Loaded schema: {self.schema_path}")
        except FileNotFoundError:
            self.errors.append(f"Schema file not found: {self.schema_path}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON schema parse error: {e}")
            return False

        if self.validator_policy_path.exists():
            try:
                with open(self.validator_policy_path, 'r', encoding='utf-8') as f:
                    loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    # shallow merge: loaded overrides defaults by top-level key
                    self.validator_policy.update(loaded)
                print(f"OK Loaded validator policy: {self.validator_policy_path}")
            except (OSError, yaml.YAMLError) as e:
                self.warnings.append(f"Validator policy load warning ({self.validator_policy_path}): {e}")
        else:
            self.warnings.append(
                f"Validator policy file not found: {self.validator_policy_path} (using built-in defaults)"
            )

        return True

    def validate_schema(self) -> bool:
        """Validate topology against schema"""
        if not self.topology or not self.schema:
            self.errors.append("Topology or schema not loaded")
            return False

        validator = Draft7Validator(self.schema)

        errors_found = False
        for error in sorted(validator.iter_errors(self.topology), key=str):
            errors_found = True
            self._format_error(error)

        return not errors_found

    def _format_error(self, error: ValidationError) -> None:
        """Format validation error for display"""
        path = " -> ".join([str(p) for p in error.absolute_path]) if error.absolute_path else "root"
        message = error.message

        if error.validator == "required":
            missing_props = error.message.split("'")[1::2]
            self.errors.append(f"Missing required field(s) at '{path}': {', '.join(missing_props)}")
        elif error.validator == "type":
            expected_type = error.validator_value
            self.errors.append(f"Type error at '{path}': expected {expected_type}, got {type(error.instance).__name__}")
        elif error.validator == "pattern":
            pattern = error.validator_value
            value = error.instance
            self.errors.append(f"Pattern mismatch at '{path}': '{value}' does not match pattern '{pattern}'")
        elif error.validator == "enum":
            allowed = error.validator_value
            value = error.instance
            self.errors.append(f"Invalid value at '{path}': '{value}' not in allowed values {allowed}")
        elif error.validator in ("minimum", "maximum"):
            limit = error.validator_value
            value = error.instance
            self.errors.append(f"Range error at '{path}': {value} violates {error.validator} {limit}")
        else:
            self.errors.append(f"Validation error at '{path}': {message}")

    def _collect_ids(self) -> Dict[str, Set[str]]:
        return collect_ids(self.topology or {})

    def check_references(self) -> None:
        """Check that all *_ref fields point to existing IDs"""
        if not self.topology:
            return

        ids = self._collect_ids()

        self._check_file_placement()
        self._check_device_taxonomy(ids)
        self._check_l0_contracts(ids)
        self._check_network_refs(ids)
        self._check_bridge_refs(ids)
        self._check_data_links(ids)
        self._check_power_links(ids)
        self._check_l3_storage_refs(ids)
        self._check_vm_refs(ids)
        self._check_lxc_refs(ids)
        self._check_service_refs(ids)
        self._check_dns_refs(ids)
        self._check_certificate_refs(ids)
        self._check_backup_refs(ids)
        self._check_security_policy_refs(ids)
        self._check_vlan_tags()
        self._check_mtu_consistency()
        self._check_vlan_zone_consistency()
        self._check_reserved_ranges()
        self._check_trust_zone_firewall_refs(ids)

    def _check_file_placement(self) -> None:
        check_file_placement(
            topology_path=self.topology_path,
            policy_get=self._policy_get,
            emit_by_severity=self._emit_by_severity,
            warnings=self.warnings,
        )

    def _check_device_taxonomy(self, ids: Dict[str, Set[str]]) -> None:
        check_device_taxonomy(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_l3_storage_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_l3_storage_refs(
            self.topology or {},
            ids,
            topology_path=self.topology_path,
            storage_ctx=build_l1_storage_context(self.topology or {}),
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_l0_contracts(self, ids: Dict[str, Set[str]]) -> None:
        check_l0_contracts(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_vlan_tags(self) -> None:
        check_vlan_tags(
            self.topology or {},
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_network_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_network_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_bridge_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_bridge_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_data_links(self, ids: Dict[str, Set[str]]) -> None:
        check_data_links(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_power_links(self, ids: Dict[str, Set[str]]) -> None:
        check_power_links(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_vm_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_vm_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_lxc_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_lxc_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_service_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_service_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_dns_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_dns_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_certificate_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_certificate_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_backup_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_backup_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_security_policy_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_security_policy_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_mtu_consistency(self) -> None:
        check_mtu_consistency(
            self.topology or {},
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_vlan_zone_consistency(self) -> None:
        check_vlan_zone_consistency(
            self.topology or {},
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_reserved_ranges(self) -> None:
        check_reserved_ranges(
            self.topology or {},
            errors=self.errors,
            warnings=self.warnings,
        )

    def _check_trust_zone_firewall_refs(self, ids: Dict[str, Set[str]]) -> None:
        check_trust_zone_firewall_refs(
            self.topology or {},
            ids,
            errors=self.errors,
            warnings=self.warnings,
        )

    def check_version(self) -> None:
        check_version(
            self.topology or {},
            errors=self.errors,
            warnings=self.warnings,
        )

    def check_ip_overlaps(self) -> None:
        check_ip_overlaps(
            self.topology or {},
            errors=self.errors,
            warnings=self.warnings,
        )

    def build_migration_report(self) -> List[str]:
        """Build a migration checklist for legacy-to-new model transition."""
        topology = self.topology or {}
        l3 = topology.get('L3_data', {}) or {}
        l4 = topology.get('L4_platform', {}) or {}
        l5 = topology.get('L5_application', {}) or {}

        items: List[str] = []

        storage_entries = len(l3.get('storage', []) or [])
        if storage_entries:
            items.append(
                f"L3_data.storage: {storage_entries} entr{'y' if storage_entries == 1 else 'ies'} -> migrate to storage_endpoints (+ chain entities)"
            )

        for idx, asset in enumerate(l3.get('data_assets', []) or []):
            if not isinstance(asset, dict):
                continue
            asset_id = asset.get('id', f"index-{idx}")
            placement_fields = [key for key in ("storage_ref", "storage_endpoint_ref", "mount_point_ref", "path") if asset.get(key)]
            if placement_fields:
                items.append(
                    f"L3_data.data_assets[{asset_id}]: placement fields {placement_fields} -> move placement to L4 storage.volumes"
                )

        for idx, lxc in enumerate(l4.get('lxc', []) or []):
            if not isinstance(lxc, dict):
                continue
            lxc_id = lxc.get('id', f"index-{idx}")
            if lxc.get('type'):
                items.append(f"L4_platform.lxc[{lxc_id}].type -> replace with platform_type + L5 service semantics")
            if lxc.get('role'):
                items.append(f"L4_platform.lxc[{lxc_id}].role -> replace with resource_profile_ref + L5 service semantics")
            if lxc.get('resources'):
                items.append(f"L4_platform.lxc[{lxc_id}].resources -> migrate to resource_profiles + resource_profile_ref")
            ansible_vars = ((lxc.get('ansible') or {}).get('vars') or {})
            if isinstance(ansible_vars, dict) and ansible_vars:
                items.append(f"L4_platform.lxc[{lxc_id}].ansible.vars -> move app config to L5 services[].config")

        for idx, service in enumerate(l5.get('services', []) or []):
            if not isinstance(service, dict):
                continue
            svc_id = service.get('id', f"index-{idx}")
            if service.get('ip'):
                items.append(f"L5_application.services[{svc_id}].ip -> derive from runtime target + network_binding_ref")
            legacy_refs = [ref for ref in ("device_ref", "vm_ref", "lxc_ref", "network_ref") if service.get(ref)]
            if legacy_refs:
                items.append(f"L5_application.services[{svc_id}] legacy refs {legacy_refs} -> migrate to runtime.*")
            if not service.get('runtime'):
                items.append(f"L5_application.services[{svc_id}] missing runtime -> add runtime.type + runtime.target_ref")

        ext_services = len(l5.get('external_services', []) or [])
        if ext_services:
            items.append(
                f"L5_application.external_services: {ext_services} entr{'y' if ext_services == 1 else 'ies'} -> fold into services[].runtime.type=docker"
            )

        return items

    def print_migration_report(self) -> None:
        """Print migration report section."""
        report_items = self.build_migration_report()
        print("\n" + "=" * 70)
        print("MIGRATION REPORT")
        print("=" * 70)
        if not report_items:
            print("\nOK No legacy migration items detected.")
            return
        print("\nLegacy fields requiring migration:")
        for item in report_items:
            print(f"  - {item}")

    def print_results(self) -> None:
        """Print validation results"""
        print("\n" + "="*70)

        if self.errors:
            print(f"ERROR Validation FAILED - {len(self.errors)} error(s) found")
            print("="*70)
            print("\nErrors:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        else:
            print("OK Validation PASSED")
            print("="*70)
            print("\nOK Topology version is compatible")
            print("OK Topology is valid according to JSON Schema v7")
            print("OK All references are consistent")
            print("OK No IP address conflicts")

        if self.warnings:
            print(f"\nWARN  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  - {warning}")

    def validate(self) -> bool:
        """Run full validation"""
        print("="*70)
        print("Topology Schema Validation (JSON Schema v7)")
        print("="*70)
        print()
        print(f"MODE Validation mode: {'strict' if self.strict_mode else 'compat'}")

        if not self.load_files():
            return False

        print("\nTAG  Step 1: Checking topology version...")
        self.check_version()
        version = self.topology.get('L0_meta', {}).get('version', 'unknown')
        print(f"OK Topology version: {version}")

        print("\nSTEP Step 2: Validating against JSON Schema...")
        schema_valid = self.validate_schema()

        if schema_valid:
            print("OK Schema validation passed")
        else:
            print(f"X Schema validation failed ({len(self.errors)} errors)")

        if schema_valid:
            print("\nREF Step 3: Checking reference consistency...")
            errors_before = len(self.errors)
            self.check_references()

            if len(self.errors) == errors_before:
                print("OK All references are valid")
            else:
                print(f"X Reference validation failed ({len(self.errors) - errors_before} errors)")

        if schema_valid:
            print("\nNET Step 4: Checking for IP address conflicts...")
            errors_before = len(self.errors)
            self.check_ip_overlaps()

            if len(self.errors) == errors_before:
                print("OK No IP address conflicts found")
            else:
                print(f"X IP conflicts found ({len(self.errors) - errors_before} errors)")

        if self.strict_mode and self.warnings:
            escalated = [f"[STRICT] {warning}" for warning in self.warnings]
            self.errors.extend(escalated)
            self.warnings.clear()
            print(f"\nSTRICT Strict mode enabled: escalated {len(escalated)} warning(s) to error(s)")

        if self.show_migration_report:
            self.print_migration_report()

        return len(self.errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate topology.yaml against JSON Schema v7 (v4 layered)"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help="Path to JSON Schema file"
    )
    parser.add_argument(
        "--validator-policy",
        default=str(DEFAULT_VALIDATOR_POLICY_PATH),
        help="Path to validator policy YAML file (non-domain validation settings)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--no-topology-cache",
        action="store_true",
        help="Disable shared topology cache and force direct YAML parse",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--strict",
        dest="strict_mode",
        action="store_true",
        help="Run strict mode: warnings are treated as errors (default).",
    )
    mode_group.add_argument(
        "--compat",
        dest="strict_mode",
        action="store_false",
        help="Run compatibility mode: warnings stay warnings.",
    )
    parser.set_defaults(strict_mode=True)
    parser.add_argument(
        "--migration-report",
        action="store_true",
        help="Print legacy-to-new model migration checklist",
    )

    args = parser.parse_args()

    validator = SchemaValidator(
        args.topology,
        args.schema,
        args.validator_policy,
        use_topology_cache=not args.no_topology_cache,
        strict_mode=args.strict_mode,
        show_migration_report=args.migration_report,
    )
    valid = validator.validate()
    validator.print_results()

    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
