#!/usr/bin/env python3
"""Contract guard for ADR0062 cross-layer relation ownership and diagnostics."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml"
ERROR_CATALOG_PATH = REPO_ROOT / "topology-tools" / "data" / "error-catalog.yaml"

RELATION_OWNERS = {
    "storage.pool_ref": "base.validator.references",
    "storage.volume_ref": "base.validator.references",
    "network.bridge_ref": "base.validator.references",
    "network.vlan_ref": "base.validator.references",
    "observability.target_ref": "base.validator.references",
    "operations.target_ref": "base.validator.references",
    "power.source_ref": "base.validator.power_source_refs",
}

RELATION_ERROR_CODES = {
    "storage.pool_ref": {"E7401", "E7402", "E7403", "E7404"},
    "storage.volume_ref": {"E7401", "E7402", "E7403", "E7404"},
    "network.bridge_ref": {"E7501", "E7502", "E7503", "E7504"},
    "network.vlan_ref": {"E7511", "E7512", "E7513", "E7514"},
    "observability.target_ref": {"E7601", "E7602", "E7603", "E7604"},
    "operations.target_ref": {"E7701", "E7702", "E7703", "E7704"},
    "power.source_ref": {"E7801", "E7802", "E7803", "E7804", "E7805"},
}

ACCEPTANCE_TARGETS = (
    REPO_ROOT / "tests" / "plugin_integration" / "test_reference_validator.py",
    REPO_ROOT / "tests" / "plugin_integration" / "test_l1_power_source_refs.py",
)


def _load_manifest_plugins() -> dict[str, dict]:
    payload = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    return {
        plugin["id"]: plugin for plugin in plugins if isinstance(plugin, dict) and isinstance(plugin.get("id"), str)
    }


def _load_error_codes() -> set[str]:
    payload = yaml.safe_load(ERROR_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    codes = payload.get("codes", {}) if isinstance(payload, dict) else {}
    return {str(code) for code in codes if str(code).startswith("E")}


def test_adr0062_relation_owners_are_registered() -> None:
    plugins = _load_manifest_plugins()
    missing = sorted({owner for owner in RELATION_OWNERS.values() if owner not in plugins})
    assert not missing, f"Missing ADR0062 relation owner plugins: {missing}"


def test_adr0062_relation_diagnostic_codes_are_registered() -> None:
    catalog_codes = _load_error_codes()
    missing_by_relation: dict[str, list[str]] = {}
    for relation, expected_codes in RELATION_ERROR_CODES.items():
        missing = sorted(code for code in expected_codes if code not in catalog_codes)
        if missing:
            missing_by_relation[relation] = missing
    assert not missing_by_relation, f"Missing ADR0062 diagnostic codes: {missing_by_relation}"


def test_adr0062_acceptance_targets_exist() -> None:
    missing = [str(path.relative_to(REPO_ROOT)) for path in ACCEPTANCE_TARGETS if not path.exists()]
    assert not missing, f"Missing ADR0062 acceptance target files: {missing}"
