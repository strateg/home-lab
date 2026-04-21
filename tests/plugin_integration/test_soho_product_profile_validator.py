#!/usr/bin/env python3
"""Integration checks for SOHO product profile validator."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginRegistry, PluginStatus
from kernel.plugin_base import PluginContext, Stage
from plugins.validators.soho_product_profile_validator import SohoProductProfileValidator
from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test

_SOHO_RESOLVER_PLUGIN_ID = "base.compiler.soho_profile_resolver"


def _ctx(
    tmp_path: Path,
    project_payload: dict[str, Any],
    *,
    legacy_end_date: str = "2099-01-01",
    today: str | None = None,
) -> PluginContext:
    project_manifest = tmp_path / "project.yaml"
    project_manifest.write_text(yaml.safe_dump(project_payload, sort_keys=False), encoding="utf-8")
    policy_path = tmp_path / "soho-migration-state-policy.yaml"
    policy_path.write_text(
        """
schema_version: 1
states: [legacy, migrated-soft, migrated-hard]
allowed_transitions:
  legacy: [legacy, migrated-soft]
  migrated-soft: [migrated-soft, migrated-hard]
  migrated-hard: [migrated-hard]
blocking_on_invalid_transition: true
sunset_policy:
  legacy_end_date: "__LEGACY_END_DATE__"
""".strip() + "\n",
        encoding="utf-8",
    )
    policy_path.write_text(
        policy_path.read_text(encoding="utf-8").replace("__LEGACY_END_DATE__", legacy_end_date),
        encoding="utf-8",
    )
    config: dict[str, Any] = {
        "repo_root": str(tmp_path),
        "project_id": "home-lab",
        "project_manifest_path": str(project_manifest),
        "soho_migration_policy_path": str(policy_path),
    }
    if today:
        config["soho_migration_today"] = today
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        output_dir=str(tmp_path / "build"),
        config=config,
    )


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _publish(ctx: PluginContext, plugin_id: str, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        publish_for_test(ctx, plugin_id, key, value)


def _run_validator(validator: SohoProductProfileValidator, ctx: PluginContext):
    return run_plugin_for_test(
        validator,
        ctx,
        Stage.VALIDATE,
        consumes_keys={_SOHO_RESOLVER_PLUGIN_ID},
    )


def _seed_resolver_payloads(
    ctx: PluginContext,
    *,
    required_bundles: list[str],
    available_bundles: list[str] | None = None,
    missing_bundle_definitions: list[str] | None = None,
) -> None:
    _publish(
        ctx,
        _SOHO_RESOLVER_PLUGIN_ID,
        {
            "soho_profile_resolution": {
                "required_bundles": required_bundles,
                "available_bundles": available_bundles or required_bundles,
                "missing_bundle_definitions": missing_bundle_definitions or [],
            },
            "effective_product_bundles": required_bundles,
            "available_product_bundles": available_bundles or required_bundles,
        },
    )


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_soho_validator_manifest_requires_resolver_payloads() -> None:
    registry = _registry()
    consumes = registry.specs["base.validator.soho_product_profile"].consumes
    required = {
        (item["from_plugin"], item["key"])
        for item in consumes
        if item.get("required") is True
    }
    assert required >= {
        ("base.compiler.soho_profile_resolver", "soho_profile_resolution"),
        ("base.compiler.soho_profile_resolver", "effective_product_bundles"),
        ("base.compiler.soho_profile_resolver", "available_product_bundles"),
    }


def test_soho_validator_warns_when_product_profile_is_missing(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(tmp_path, {"project": "home-lab"})

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7941" for diag in result.diagnostics)
    report_path = tmp_path / "build" / "diagnostics" / "product-profile-state.json"
    assert report_path.exists()


def test_soho_validator_fails_for_migrated_hard_missing_bundles(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(
        tmp_path,
        {
            "project": "home-lab",
            "product_profile": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "managed-soho",
                "site_class": "single-site",
                "user_band": "1-25",
                "operator_mode": "single-operator",
                "release_channel": "stable",
                "migration_state": "migrated-hard",
            },
            "product_bundles": ["bundle.edge-routing", "bundle.network-segmentation"],
        },
    )
    _seed_resolver_payloads(
        ctx,
        required_bundles=[
            "bundle.edge-routing",
            "bundle.network-segmentation",
            "bundle.secrets-governance",
            "bundle.remote-access",
            "bundle.operator-workflows",
            "bundle.backup-restore",
            "bundle.observability",
            "bundle.update-management",
        ],
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7942" for diag in result.diagnostics)


def test_soho_validator_fails_on_invalid_state_transition(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(
        tmp_path,
        {
            "project": "home-lab",
            "product_profile": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "starter",
                "site_class": "single-site",
                "user_band": "1-25",
                "operator_mode": "single-operator",
                "release_channel": "stable",
                "migration_state": "migrated-soft",
                "previous_migration_state": "migrated-hard",
            },
            "product_bundles": [
                "bundle.edge-routing",
                "bundle.network-segmentation",
                "bundle.secrets-governance",
                "bundle.remote-access",
                "bundle.operator-workflows",
            ],
        },
    )
    _seed_resolver_payloads(
        ctx,
        required_bundles=[
            "bundle.edge-routing",
            "bundle.network-segmentation",
            "bundle.secrets-governance",
            "bundle.remote-access",
            "bundle.operator-workflows",
        ],
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7947" for diag in result.diagnostics)


def test_soho_validator_blocks_legacy_when_sunset_is_reached(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(
        tmp_path,
        {"project": "home-lab"},
        legacy_end_date="2026-04-01",
        today="2026-04-09",
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7948" for diag in result.diagnostics)
    state = result.output_data.get("product_profile_state", {})
    assert isinstance(state, dict)
    assert state.get("migration_state") == "legacy"
    assert state.get("effective_migration_state") == "migrated-hard"


def test_soho_validator_treats_legacy_profile_as_hard_after_sunset(tmp_path: Path) -> None:
    validator = SohoProductProfileValidator("base.validator.soho_product_profile")
    ctx = _ctx(
        tmp_path,
        {
            "project": "home-lab",
            "product_profile": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "starter",
                "site_class": "single-site",
                "user_band": "1-25",
                "operator_mode": "single-operator",
                "release_channel": "stable",
                "migration_state": "legacy",
            },
            "product_bundles": ["bundle.edge-routing"],
        },
        legacy_end_date="2026-04-01",
        today="2026-04-09",
    )
    _seed_resolver_payloads(
        ctx,
        required_bundles=[
            "bundle.edge-routing",
            "bundle.network-segmentation",
            "bundle.secrets-governance",
            "bundle.remote-access",
            "bundle.operator-workflows",
        ],
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    codes = {diag.code for diag in result.diagnostics}
    assert "E7948" in codes
    assert "E7942" in codes


def test_soho_validator_execute_stage_requires_committed_resolver_payloads(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.soho_profile_resolver",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/soho_profile_resolver_compiler.py').as_posix()}:SohoProfileResolverCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 55,
            },
            {
                "id": "base.validator.soho_product_profile",
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/soho_product_profile_validator.py').as_posix()}:SohoProductProfileValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "verify",
                "order": 187,
                "depends_on": ["base.compiler.soho_profile_resolver"],
                "consumes": [
                    {"from_plugin": "base.compiler.soho_profile_resolver", "key": "soho_profile_resolution", "required": True},
                    {"from_plugin": "base.compiler.soho_profile_resolver", "key": "effective_product_bundles", "required": True},
                    {"from_plugin": "base.compiler.soho_profile_resolver", "key": "available_product_bundles", "required": True},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"repo_root": str(tmp_path), "project_id": "home-lab"},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)
